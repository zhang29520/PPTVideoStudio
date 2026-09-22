"""全局配置与路径。"""
import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = Path(os.environ.get("PVS_DATA_DIR", BASE_DIR / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    # LLM（OpenAI 兼容协议；留空则用内置模板生成）
    "llm_api_base": "",
    "llm_api_key": "",
    "llm_model": "",
    # TTS
    "tts_voice": "zh-CN-XiaoxiaoNeural",
    "tts_rate": "+0%",
    "tts_volume": "+0%",
    # 视频默认值
    "resolution": "1080p",
    "fps": 30,
    "subtitle": True,
    "transition": 0.5,
}


def ensure_dirs() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> dict:
    merged = {**DEFAULT_SETTINGS, **settings}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return merged
