"""PPT 生成 / 编辑 / 导入 / 下载 / 缩略图。"""
from hashlib import md5
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from .. import store, tasks
from ..services.outline import generate_outline
from ..services.ppt_builder import build_pptx, parse_pptx
from ..services.render import render_slides

router = APIRouter()

THUMB_W, THUMB_H = 480, 270


def _rebuild_pptx(project: dict) -> str:
    """根据当前 slides 重建 PPTX，返回相对文件名。"""
    d = Path(store.project_dir(project["id"]))
    out = d / "output.pptx"
    build_pptx(project["slides"], out, theme=project.get("theme"))
    project["files"]["pptx"] = "output.pptx"
    return "output.pptx"


def _slides_hash(slides: list) -> str:
    return md5(repr(slides).encode("utf-8")).hexdigest()[:12]


@router.post("/api/ppt/generate/{project_id}")
def generate_ppt(project_id: str, payload: dict = None):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    payload = payload or {}
    count = int(payload.get("slides", 8))
    audience = payload.get("audience", "通用受众")
    theme = {
        "primary": payload.get("color") or "#1a3a5c",
        "style": payload.get("style") or "简约商务",
    }
    project["theme"] = theme

    def job(progress):
        progress(0.05, "准备生成…")
        outline = generate_outline(
            project["topic"], slides_count=count, audience=audience, progress=progress
        )
        project["slides"] = outline["slides"]
        project["outline_source"] = outline["source"]
        project["knowledge_used"] = outline.get("knowledge_used", False)
        project["llm_error"] = outline.get("llm_error")
        progress(0.95, "正在构建 PPTX 文件…")
        _rebuild_pptx(project)
        store.save_project(project)
        return {"source": outline["source"], "slides": len(project["slides"]),
                "warning": outline.get("llm_error")}

    tid = tasks.start(job)
    return {"taskId": tid, "message": "PPT 生成任务已启动"}


@router.get("/api/ppt/{project_id}")
def get_slides(project_id: str):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return {"slides": project.get("slides", [])}


@router.put("/api/ppt/{project_id}")
def save_slides(project_id: str, payload: dict):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    slides = (payload or {}).get("slides")
    if not isinstance(slides, list) or not slides:
        raise HTTPException(400, "slides 不能为空")
    project["slides"] = slides
    # 同步裁剪解说词长度
    script = project.get("script", [])
    if len(script) > len(slides):
        project["script"] = script[: len(slides)]
    _rebuild_pptx(project)
    store.save_project(project)
    return {"message": "已保存并重建 PPTX", "slides": project["slides"]}


@router.post("/api/ppt/import")
async def import_ppt(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pptx"):
        raise HTTPException(400, "仅支持 .pptx 文件")
    project = store.create_project(topic=file.filename.rsplit(".", 1)[0])
    d = Path(store.project_dir(project["id"]))
    upload = d / "upload.pptx"
    upload.write_bytes(await file.read())
    project["slides"] = parse_pptx(upload)
    project["files"]["pptx"] = "upload.pptx"
    store.save_project(project)
    return {
        "projectId": project["id"],
        "slides": project["slides"],
        "message": f"导入成功，共 {len(project['slides'])} 页",
    }


@router.get("/api/ppt/{project_id}/download")
def download_ppt(project_id: str):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    rel = project.get("files", {}).get("pptx")
    if not rel:
        raise HTTPException(404, "尚未生成 PPT")
    path = Path(store.project_dir(project_id)) / rel
    if not path.exists():
        raise HTTPException(404, "PPT 文件不存在")
    return FileResponse(path, filename=f"{project['topic'][:20] or project_id}.pptx")


@router.get("/api/ppt/{project_id}/thumb/{index}.png")
def slide_thumb(project_id: str, index: int):
    """单页缩略图（按 slides 内容哈希缓存）。"""
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    slides = project.get("slides", [])
    if index < 0 or index >= len(slides):
        raise HTTPException(404, "页码不存在")

    h = _slides_hash(slides) + "_" + (project.get("theme", {}).get("primary", "def")).lstrip("#")
    d = Path(store.project_dir(project_id))
    thumb_dir = d / "thumbs" / h
    thumb = thumb_dir / f"page_{index:03d}.png"
    if not thumb.exists():
        pngs = render_slides(slides, d / "thumbs_render" / h, theme=project.get("theme"))
        thumb_dir.mkdir(parents=True, exist_ok=True)
        from PIL import Image

        img = Image.open(pngs[index])
        img.thumbnail((THUMB_W, THUMB_H))
        img.save(thumb)
    return FileResponse(thumb, media_type="image/png")


@router.get("/api/ppt/{project_id}/page/{index}.png")
def slide_page_full(project_id: str, index: int):
    """全尺寸单页图（点击放大预览用）。"""
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    slides = project.get("slides", [])
    if index < 0 or index >= len(slides):
        raise HTTPException(404, "页码不存在")

    h = _slides_hash(slides) + "_" + (project.get("theme", {}).get("primary", "def")).lstrip("#")
    d = Path(store.project_dir(project_id))
    pngs = render_slides(slides, d / "thumbs_render" / h, theme=project.get("theme"))
    return FileResponse(pngs[index], media_type="image/png")
