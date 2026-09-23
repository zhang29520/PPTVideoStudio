from pathlib import Path
import re

from fastapi import APIRouter, HTTPException

from .. import store, tasks
from ..services.ppt_builder import build_pptx
from ..services.script_gen import generate_script

router = APIRouter()


def _sync_notes(project: dict) -> None:
    """把解说词写入每页演讲者备注，并重建 PPTX。

    导入型项目（upload.pptx）绝不覆盖用户上传的原始文件。
    """
    for i, s in enumerate(project["slides"]):
        if i < len(project["script"]):
            s["notes"] = project["script"][i]
    if project.get("files", {}).get("pptx") and project["files"]["pptx"] != "upload.pptx":
        build_pptx(project["slides"], Path(store.project_dir(project["id"])) / project["files"]["pptx"])


@router.post("/api/speech/generate/{project_id}")
def generate_speech(project_id: str, payload: dict = None):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if not project.get("slides"):
        raise HTTPException(400, "请先生成或导入 PPT")
    tone = (payload or {}).get("tone", "专业")
    slides_snapshot = [dict(s) for s in project["slides"]]
    topic = project["topic"]

    def job(progress):
        result = generate_script(topic, slides_snapshot, tone=tone, progress=progress)
        # 任务线程内重新加载最新项目，避免覆盖并发编辑
        p = store.load_project(project_id) or project
        p["script"] = result["pages"]
        p["script_source"] = result["source"]
        p["script_llm_error"] = result.get("llm_error")
        _sync_notes(p)
        store.save_project(p)
        return {"source": result["source"], "pages": result["pages"],
                "warning": result.get("llm_error")}

    tid = tasks.start(job)
    return {"taskId": tid, "message": "解说词生成任务已启动"}


@router.post("/api/speech/generate-one/{project_id}")
def generate_one_speech(project_id: str, payload: dict = None):
    """只重新生成某一页的解说词（index 从 0 计），同步更新备注与 PPTX。"""
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if not project.get("slides"):
        raise HTTPException(400, "请先生成或导入 PPT")
    payload = payload or {}
    try:
        index = int(payload.get("index", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "index 无效")
    if not (0 <= index < len(project["slides"])):
        raise HTTPException(400, f"index 超出范围（0~{len(project['slides']) - 1}）")
    tone = payload.get("tone", "专业")
    topic = project["topic"]
    slide = dict(project["slides"][index])
    prev_text = ""
    if index > 0 and project.get("script"):
        prev = project["script"][index - 1] if index - 1 < len(project["script"]) else ""
        prev_text = str(prev or "")

    from ..services.script_gen import generate_one_script

    text = generate_one_script(topic, slide, index, len(project["slides"]), tone=tone,
                               prev_text=prev_text)
    # 重新加载最新项目，避免覆盖并发编辑
    p = store.load_project(project_id) or project
    script = list(p.get("script") or [])
    while len(script) < len(p["slides"]):
        script.append("")
    script[index] = text
    p["script"] = script
    _sync_notes(p)
    store.save_project(p)
    return {"index": index, "page": text}


@router.post("/api/speech/use-notes/{project_id}")
def use_notes_speech(project_id: str, payload: dict = None):
    """使用上传 PPT 自带的演讲者备注作为解说词（有备注的页用备注，无备注的页保留现值）。"""
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if not project.get("slides"):
        raise HTTPException(400, "请先生成或导入 PPT")
    used = 0
    script = list(project.get("script") or [])
    while len(script) < len(project["slides"]):
        script.append("")
    for i, s in enumerate(project["slides"]):
        note = str((s or {}).get("notes", "") or "").strip()
        if note:
            script[i] = re.sub(r"\s+", " ", note)
            used += 1
    if not used:
        raise HTTPException(400, "该 PPT 没有自带演讲稿（演讲者备注为空）")
    project["script"] = script
    project["script_source"] = "ppt_notes"
    _sync_notes(project)
    store.save_project(project)
    return {"script": script, "used": used}


@router.put("/api/speech/{project_id}")
def save_speech(project_id: str, payload: dict):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    pages = (payload or {}).get("pages")
    if not isinstance(pages, list):
        raise HTTPException(400, "pages 必须为数组")
    project["script"] = [str(x) for x in pages]
    _sync_notes(project)
    store.save_project(project)
    return {"message": "解说词已保存"}
