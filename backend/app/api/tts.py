"""TTS 配音 API：后台任务逐页合成 + 试听 + 音频文件服务。"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import store, tasks
from ..config import load_settings
from ..services.tts import speed_to_rate, synthesize_pages

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
    voice = payload.get("voice")
    speed = payload.get("speed")
    try:
        speed = float(speed) if speed is not None else None
    except (TypeError, ValueError):
        speed = None
    rate = speed_to_rate(speed) if speed else payload.get("rate")
    volume = payload.get("volume")
    audio_dir = Path(store.project_dir(project_id)) / "audio"

    def job(progress):
        result = synthesize_pages(
            pages, audio_dir, voice=voice, rate=rate, volume=volume, progress=progress
        )
        p = store.load_project(project_id) or project
        p["files"]["audio"] = [Path(x).name for x in result["audio_paths"]]
        p["audio_durations"] = result["durations"]
        p["tts_settings"] = {"voice": voice, "speed": speed, "rate": rate}
        store.save_project(p)
        return {"audio": p["files"]["audio"], "durations": result["durations"], "engine": result["engine"]}

    tid = tasks.start(job)
    return {"taskId": tid, "message": "配音任务已启动"}


@router.get("/api/tts/preview")
def tts_preview(voice: str = "", speed: str = "1.0"):
    """按当前音色+语速合成一句试听音频。参数全部手工解析，避免 422 校验错误。"""
    from ..services.tts import _synth_one

    try:
        speed = max(0.1, min(2.0, float(speed)))
    except (TypeError, ValueError):
        speed = 1.0
    rate = speed_to_rate(speed)
    v = (voice or "").strip() or load_settings()["tts_voice"]
    text = "您好，这是当前语速的试听效果，生成视频时每页配音都会使用这个语速。"
    fd, path = tempfile.mkstemp(suffix=".mp3")
    Path(path).unlink(missing_ok=True)
    if not _synth_one(text, v, rate, "+0%", Path(path)):
        raise HTTPException(500, "试听合成失败，请检查网络")
    return FileResponse(path, media_type="audio/mpeg", filename="preview.mp3")


@router.get("/api/tts/{project_id}/audio/{filename}")
def get_audio(project_id: str, filename: str):
    path = Path(store.project_dir(project_id)) / "audio" / filename
    if not path.exists():
        raise HTTPException(404, "音频不存在")
    return FileResponse(path, media_type="audio/mpeg")
