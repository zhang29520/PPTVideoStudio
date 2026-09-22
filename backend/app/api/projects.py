from fastapi import APIRouter, HTTPException

from .. import store

router = APIRouter()


@router.get("/api/projects")
def list_projects():
    return store.list_projects()


@router.post("/api/projects")
def create_project(payload: dict):
    topic = (payload or {}).get("topic", "").strip()
    if not topic:
        raise HTTPException(400, "主题不能为空")
    project = store.create_project(topic)
    return {"id": project["id"], "topic": project["topic"]}


@router.get("/api/projects/{project_id}")
def get_project(project_id: str):
    p = store.load_project(project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    return p
