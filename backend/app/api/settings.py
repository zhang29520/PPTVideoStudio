from fastapi import APIRouter

from ..config import load_settings, save_settings

router = APIRouter()


@router.get("/api/settings")
def get_settings():
    return load_settings()


@router.put("/api/settings")
def update_settings(payload: dict):
    merged = save_settings(payload or {})
    return {"message": "设置已保存", "settings": merged}
