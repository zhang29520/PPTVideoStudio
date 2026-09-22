"""TTS 配音 API：逐页合成 + 音频文件服务。"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import store
from ..services.tts import synthesize_pages

router = APIRouter()


@router.post("/api/tts/generate/{project_id}")
def generate_tts(project_id: str, payload: dict = None):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    pages = project.get("script", [])
    if not pages:
        raise HTTPException(400, "请先生成解说词")

    payload = payload or {}
    result = synthesize_pages(
        pages,
        Path(store.project_dir(project_id)) / "audio",
        voice=payload.get("voice"),
        rate=payload.get("rate"),
        volume=payload.get("volume"),
    )
    project["files"]["audio"] = [Path(p).name for p in result["audio_paths"]]
    project["audio_durations"] = result["durations"]
    store.save_project(project)
    return {
        "audio": project["files"]["audio"],
        "durations": result["durations"],
        "engine": result["engine"],
        "message": "配音已生成",
    }


@router.get("/api/tts/{project_id}/audio/{filename}")
def get_audio(project_id: str, filename: str):
    path = Path(store.project_dir(project_id)) / "audio" / filename
    if not path.exists():
        raise HTTPException(404, "音频不存在")
    return FileResponse(path, media_type="audio/mpeg")
