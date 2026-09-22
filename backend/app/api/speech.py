from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import store, tasks
from ..services.ppt_builder import build_pptx
from ..services.script_gen import generate_script

router = APIRouter()


def _sync_notes(project: dict) -> None:
    """把解说词写入每页演讲者备注，并重建 PPTX。"""
    for i, s in enumerate(project["slides"]):
        if i < len(project["script"]):
            s["notes"] = project["script"][i]
    if project.get("files", {}).get("pptx"):
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
