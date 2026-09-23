"""PPT 生成 / 编辑 / 导入 / 下载 / 缩略图。"""
import threading
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
    """根据当前 slides 重建 PPTX，返回相对文件名。

    导入型项目（upload.pptx）：绝不覆盖用户上传的原始文件，
    重建结果写到 output.pptx 仅作备注/备份；原始画面渲染仍指向 upload.pptx。
    """
    d = Path(store.project_dir(project["id"]))
    is_import = project.get("files", {}).get("pptx") == "upload.pptx"
    out = d / "output.pptx"
    build_pptx(project["slides"], out, theme=project.get("theme"),
               effects=bool(project.get("effects")))
    if not is_import:
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
    failed_marker = out / ".failed"
    pngs = sorted(out.glob("page_*.png"))
    if pngs and marker.exists():
        return pngs
    if failed_marker.exists():
        return None  # 已确认失败，不再反复尝试昂贵转换
    from ..services.pptx_render import render_pptx_real

    res = render_pptx_real(pptx, out)
    if res:
        pngs, _trans, _engine = res
        if pngs:
            marker.write_text("ok", encoding="utf-8")
            # 转场信息一并缓存，供视频合成复用（免去二次转换 PPT）
            try:
                import json as _json
                (out / "transitions.json").write_text(
                    _json.dumps(_trans, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
            return sorted(out.glob("page_*.png"))
    failed_marker.write_text("convert failed", encoding="utf-8")
    return None


# 正在后台预热原始画面的项目签名集合（防重复起线程）
_warming: set = set()
_warm_lock = threading.Lock()


def _ensure_warm(project: dict) -> dict:
    """确保原始画面转换线程在跑（幂等），返回状态供前端展示进度。

    {active, ready, failed, done, total}；
    active=False 表示非导入项目（无原始画面概念）。
    """
    total = len(project.get("slides", []))
    rel = project.get("files", {}).get("pptx")
    if rel != "upload.pptx":
        return {"active": False, "ready": True, "failed": False,
                "done": total, "total": total}
    d = Path(store.project_dir(project["id"]))
    pptx = d / rel
    if not pptx.exists():
        return {"active": False, "ready": True, "failed": True,
                "done": 0, "total": total}
    sig = md5(f"{pptx.name}|{pptx.stat().st_size}".encode("utf-8")).hexdigest()[:12]
    out = d / "thumbs_real" / sig
    done = len(list(out.glob("page_*.png"))) if out.exists() else 0
    failed = (out / ".failed").exists()
    ready = (out / ".done").exists() or failed
    # 阶段：convert=soffice 整体转 PDF（无逐页进度）；render=逐页出图（有进度）
    stage = "done" if ready else ("render" if done > 0 else "convert")
    if not ready and sig not in _warming:
        with _warm_lock:
            if sig not in _warming:
                _warming.add(sig)

                def _run(p=project, s=sig):
                    try:
                        _real_pages(p)
                    finally:
                        _warming.discard(s)

                threading.Thread(target=_run, daemon=True).start()
    return {"active": True, "ready": ready, "failed": failed,
            "done": done, "total": total, "stage": stage}


@router.get("/api/ppt/{project_id}/real-status")
def real_status(project_id: str):
    """原始画面提取进度（前端轮询展示进度条）。"""
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return _ensure_warm(project)


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
        # 预渲染预览页：预览缩略图即点即有（免去打开预览后逐页灰块等待）
        try:
            progress(0.97, "正在渲染页面预览…")
            h = _slides_hash(project["slides"]) + "_" + (theme.get("primary") or "#1a3a5c").lstrip("#")
            render_slides(project["slides"], Path(store.project_dir(project["id"])) / "thumbs_render" / h,
                          theme=theme)
        except Exception:
            pass  # 预渲染失败不阻塞生成，缩略图会走懒加载
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
    # 解析放线程池：大 PPT 解析耗时数秒，不能阻塞事件循环（否则全应用卡死）
    from fastapi.concurrency import run_in_threadpool

    project["slides"] = await run_in_threadpool(parse_pptx, upload)
    project["files"]["pptx"] = "upload.pptx"
    store.save_project(project)
    # 后台预热原始页面渲染：大 PPT 转 PDF 耗时较长，提前跑，
    # 用户进预览时缩略图可直接命中缓存
    import threading

    threading.Thread(target=_real_pages, args=(project,), daemon=True).start()
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
    # 解析与素材提取放线程池：大文档解析耗时，不能阻塞事件循环
    from fastapi.concurrency import run_in_threadpool

    def _parse_docx():
        slides = docx_to_slides(upload)
        full = ""
        try:
            from docx import Document as _Doc

            paras = [_clean_text(p.text) for p in _Doc(str(upload)).paragraphs]
            full = "\n".join(x for x in paras if x.strip())
        except Exception:
            full = ""
        return slides, full[:6000]

    try:
        slides, docx_text = await run_in_threadpool(_parse_docx)
    except Exception as e:
        raise HTTPException(400, f"Word 解析失败：{e}")
    if len(slides) < 2:
        raise HTTPException(400, "文档内容太少，无法生成 PPT（请确认有正文段落）")
    project["slides"] = slides
    project["docx_text"] = docx_text
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
    #    转换未就绪时立即返回 202（不阻塞请求线程），前端自动重试
    st = _ensure_warm(project)
    if st["active"] and not st["ready"]:
        return Response(status=202)
    real = None if st["failed"] else _real_pages(project)
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
    st = _ensure_warm(project)
    if st["active"] and not st["ready"]:
        return Response(status=202)
    real = None if st["failed"] else _real_pages(project)
    if real:
        return FileResponse(real[index], media_type="image/png")

    h = _slides_hash(slides) + "_" + (project.get("theme", {}).get("primary", "def")).lstrip("#")
    pngs = render_slides(slides, d / "thumbs_render" / h, theme=project.get("theme"))
    return FileResponse(pngs[index], media_type="image/png")
