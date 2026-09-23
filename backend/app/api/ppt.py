"""PPT 生成 / 编辑 / 导入 / 下载 / 缩略图。"""
from hashlib import md5
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from .. import store, tasks
from ..services.images import attach_images
from ..services.outline import analyze_topic, generate_outline
from ..services.ppt_builder import build_pptx, parse_pptx
from ..services.render import render_slides
from ..services.docx_import import docx_to_slides

router = APIRouter()

THUMB_W, THUMB_H = 480, 270


def _rebuild_pptx(project: dict) -> str:
    """根据当前 slides 重建 PPTX，返回相对文件名。"""
    d = Path(store.project_dir(project["id"]))
    out = d / "output.pptx"
    build_pptx(project["slides"], out, theme=project.get("theme"),
               effects=bool(project.get("effects")))
    project["files"]["pptx"] = "output.pptx"
    return "output.pptx"


def _slides_hash(slides: list) -> str:
    return md5(repr(slides).encode("utf-8")).hexdigest()[:12]


def _real_pages(project: dict):
    """导入型项目（upload.pptx）：用本机 Office/WPS/LibreOffice 渲染原始页面。

    返回 PNG 路径列表；无转换器或失败返回 None（调用方回退内置版式渲染）。
    结果按文件签名缓存，二次访问零开销。
    """
    rel = project.get("files", {}).get("pptx")
    if rel != "upload.pptx":
        return None
    d = Path(store.project_dir(project["id"]))
    pptx = d / rel
    if not pptx.exists():
        return None
    sig = md5(f"{pptx.name}|{pptx.stat().st_size}".encode("utf-8")).hexdigest()[:12]
    out = d / "thumbs_real" / sig
    marker = out / ".done"
    pngs = sorted(out.glob("page_*.png"))
    if pngs and marker.exists():
        return pngs
    from .services.pptx_render import render_pptx_real

    res = render_pptx_real(pptx, out)
    if res:
        pngs, _trans, _engine = res
        if pngs:
            marker.write_text("ok", encoding="utf-8")
            return sorted(out.glob("page_*.png"))
    return None


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
        # 主题分析：自动匹配封面设计模板（科技/政务/商务/清新/文化/暗黑）
        "design": payload.get("design") or analyze_topic(project["topic"]),
    }
    project["theme"] = theme
    use_llm = payload.get("engine", "ai") != "builtin"
    profile_id = payload.get("profile_id") or None
    with_images = bool(payload.get("with_images", True))
    project["effects"] = bool(payload.get("effects", False))  # 随机切换动效
    # Word 导入项目：可选基于文档内容生成（而非网络资料）
    material = project.get("docx_text") if payload.get("use_docx") else None

    def job(progress):
        progress(0.05, "准备生成…")
        outline = generate_outline(
            project["topic"], slides_count=count, audience=audience, progress=progress,
            use_llm=use_llm, profile_id=profile_id, material=material,
        )
        project["slides"] = outline["slides"]
        project["outline_source"] = outline["source"]
        project["knowledge_used"] = outline.get("knowledge_used", False)
        project["llm_error"] = outline.get("llm_error")
        img_count = 0
        if with_images:
            try:
                img_count = attach_images(project["topic"], project["slides"], progress,
                                          primary=theme.get("primary") or "#1a3a5c")
            except Exception:
                img_count = 0  # 配图失败不阻塞生成
        progress(0.95, "正在构建 PPTX 文件…")
        _rebuild_pptx(project)
        store.save_project(project)
        return {"source": outline["source"], "slides": len(project["slides"]),
                "images": img_count, "warning": outline.get("llm_error")}

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


@router.post("/api/ppt/import-docx")
async def import_docx(file: UploadFile = File(...)):
    """上传 Word：AI 分析文档结构 → 自动生成 PPT 页面。"""
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(400, "仅支持 .docx 文件")
    project = store.create_project(topic=file.filename.rsplit(".", 1)[0])
    d = Path(store.project_dir(project["id"]))
    upload = d / "upload.docx"
    upload.write_bytes(await file.read())
    try:
        slides = docx_to_slides(upload)
    except Exception as e:
        raise HTTPException(400, f"Word 解析失败：{e}")
    if len(slides) < 2:
        raise HTTPException(400, "文档内容太少，无法生成 PPT（请确认有正文段落）")
    project["slides"] = slides
    # 全文素材：供后续「AI 分析 → 框架设计 → 生成」使用
    try:
        from docx import Document as _Doc

        paras = [_clean_text(p.text) for p in _Doc(str(upload)).paragraphs]
        full = "\n".join(x for x in paras if x.strip())
        project["docx_text"] = full[:6000]
    except Exception:
        project["docx_text"] = ""
    project["theme"] = {
        "primary": "#1a3a5c",
        "style": "简约商务",
        "design": analyze_topic(project["topic"]),
    }
    project["docx_source"] = True
    store.save_project(project)
    return {
        "projectId": project["id"],
        "slides": slides,
        "message": f"Word 解析成功，已按文档结构生成 {len(slides)} 页",
    }


def _clean_text(s: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", s or "").strip()


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
    """单页缩略图（按 slides 内容哈希缓存；导入型项目优先用原始 PPT 画面）。"""
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    slides = project.get("slides", [])
    if index < 0 or index >= len(slides):
        raise HTTPException(404, "页码不存在")

    d = Path(store.project_dir(project_id))
    # 1. 导入型项目：优先渲染原始 PPT 页面（所见即所得）
    real = _real_pages(project)
    if real:
        h = "real_" + md5(str(real[index]).encode("utf-8")).hexdigest()[:8]
        thumb_dir = d / "thumbs" / h
        thumb = thumb_dir / f"page_{index:03d}.png"
        if not thumb.exists():
            thumb_dir.mkdir(parents=True, exist_ok=True)
            from PIL import Image

            img = Image.open(real[index])
            img.thumbnail((THUMB_W, THUMB_H))
            img.save(thumb)
        return FileResponse(thumb, media_type="image/png")

    # 2. 生成型项目：内置版式渲染
    h = _slides_hash(slides) + "_" + (project.get("theme", {}).get("primary", "def")).lstrip("#")
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
    """全尺寸单页图（点击放大预览用；导入型项目优先原始 PPT 画面）。"""
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    slides = project.get("slides", [])
    if index < 0 or index >= len(slides):
        raise HTTPException(404, "页码不存在")

    d = Path(store.project_dir(project_id))
    real = _real_pages(project)
    if real:
        return FileResponse(real[index], media_type="image/png")

    h = _slides_hash(slides) + "_" + (project.get("theme", {}).get("primary", "def")).lstrip("#")
    pngs = render_slides(slides, d / "thumbs_render" / h, theme=project.get("theme"))
    return FileResponse(pngs[index], media_type="image/png")
