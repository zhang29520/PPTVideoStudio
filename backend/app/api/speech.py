from fastapi import APIRouter, HTTPException

from .. import store
from ..services.ppt_builder import build_pptx
from ..services.script_gen import generate_script

router = APIRouter()


def _sync_notes(project: dict) -> None:
    """把解说词写入每页演讲者备注，并重建 PPTX。"""
    from pathlib import Path

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
    result = generate_script(project["topic"], project["slides"], tone=tone)
    project["script"] = result["pages"]
    project["script_source"] = result["source"]
    _sync_notes(project)
    store.save_project(project)
    return {"pages": result["pages"], "source": result["source"], "message": "解说词已生成"}


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
