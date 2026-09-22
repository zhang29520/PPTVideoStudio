"""全局配置与路径。"""
import os
import json
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = Path(os.environ.get("PVS_DATA_DIR", BASE_DIR / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    # PPT 生成 AI（大纲 + 逐页内容）
    "ppt_llm_api_base": "",
    "ppt_llm_api_key": "",
    "ppt_llm_model": "",
    # 解说词 AI（讲稿撰写）；same=True 时沿用 PPT 生成 AI 的配置
    "script_llm_same": True,
    "script_llm_api_base": "",
    "script_llm_api_key": "",
    "script_llm_model": "",
    # 旧版统一 LLM 配置（向后兼容，读取时作为兜底）
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


def llm_settings(kind: str) -> Dict[str, str]:
    """按用途解析 LLM 配置。kind: "ppt" | "script"。

    - ppt:   优先 ppt_llm_*，为空时回退旧版 llm_*
    - script: script_llm_same=True → 与 ppt 相同；否则用 script_llm_*（空时回退 ppt）
    """
    s = load_settings()
    def pick(base_k, key_k, model_k, legacy):
        base = s.get(base_k) or s.get(legacy[0]) or ""
        key = s.get(key_k) or s.get(legacy[1]) or ""
        model = s.get(model_k) or s.get(legacy[2]) or ""
        return {"api_base": base, "api_key": key, "model": model}

    ppt = pick("ppt_llm_api_base", "ppt_llm_api_key", "ppt_llm_model",
               ("llm_api_base", "llm_api_key", "llm_model"))
    if kind == "ppt":
        return ppt
    if s.get("script_llm_same", True):
        return ppt
    sc = pick("script_llm_api_base", "script_llm_api_key", "script_llm_model",
              ("llm_api_base", "llm_api_key", "llm_model"))
    return sc if sc["api_base"] and sc["model"] else ppt


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
