"""PPT 生成 / 编辑 / 导入 / 下载。"""
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .. import store
from ..services.outline import generate_outline
from ..services.ppt_builder import build_pptx, parse_pptx

router = APIRouter()


def _rebuild_pptx(project: dict) -> str:
    """根据当前 slides 重建 PPTX，返回相对文件名。"""
    from pathlib import Path

    d = Path(store.project_dir(project["id"]))
    out = d / "output.pptx"
    build_pptx(project["slides"], out)
    project["files"]["pptx"] = "output.pptx"
    return "output.pptx"


@router.post("/api/ppt/generate/{project_id}")
def generate_ppt(project_id: str, payload: dict = None):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    payload = payload or {}
    count = int(payload.get("slides", 8))
    audience = payload.get("audience", "通用受众")
    outline = generate_outline(project["topic"], slides_count=count, audience=audience)
    project["slides"] = outline["slides"]
    project["outline_source"] = outline["source"]
    _rebuild_pptx(project)
    store.save_project(project)
    return {
        "projectId": project_id,
        "source": outline["source"],
        "slides": project["slides"],
        "message": "PPT 已生成（可编辑 PPTX）",
    }


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
    import tempfile
    from pathlib import Path

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
    from pathlib import Path

    rel = project.get("files", {}).get("pptx")
    if not rel:
        raise HTTPException(404, "尚未生成 PPT")
    path = Path(store.project_dir(project_id)) / rel
    if not path.exists():
        raise HTTPException(404, "PPT 文件不存在")
    return FileResponse(path, filename=f"{project['topic'][:20] or project_id}.pptx")
