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
    # 已保存的 AI 配置列表：[{id, name, base, key, model}]
    "ai_profiles": [],
    # 默认 AI 配置的 id
    "default_profile": "",
    # 解说词 AI（讲稿撰写）；same=True 时沿用默认 AI 配置
    "script_llm_same": True,
    "script_llm_api_base": "",
    "script_llm_api_key": "",
    "script_llm_model": "",
    # 旧版单 AI 配置（向后兼容；首次加载时迁移为 ai_profiles）
    "ppt_llm_api_base": "",
    "ppt_llm_api_key": "",
    "ppt_llm_model": "",
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


def _migrate_legacy(s: dict) -> dict:
    """旧版单 AI 配置 → ai_profiles 列表（只迁移一次）。"""
    if s.get("ai_profiles"):
        return s
    base = s.get("ppt_llm_api_base") or s.get("llm_api_base") or ""
    model = s.get("ppt_llm_model") or s.get("llm_model") or ""
    if base and model:
        s["ai_profiles"] = [{
            "id": "legacy",
            "name": f"我的 AI（{model}）",
            "base": base,
            "key": s.get("ppt_llm_api_key") or s.get("llm_api_key") or "",
            "model": model,
        }]
        s["default_profile"] = "legacy"
    return s


def _profile_by_id(s: dict, profile_id: str | None) -> dict | None:
    profiles = s.get("ai_profiles") or []
    if profile_id:
        for p in profiles:
            if p.get("id") == profile_id:
                return p
        return None
    defk = s.get("default_profile") or ""
    for p in profiles:
        if p.get("id") == defk:
            return p
    return profiles[0] if profiles else None


def llm_settings(kind: str, profile_id: str | None = None) -> Dict[str, str]:
    """按用途解析 LLM 配置。kind: "ppt" | "script"。

    解析优先级：
    1. kind="ppt" 且指定 profile_id → 对应的 AI 配置
    2. ai_profiles（默认配置）
    3. 旧版 ppt_llm_* / llm_*
    script：script_llm_same=True → 与 ppt 相同；否则用 script_llm_*
    """
    s = load_settings()
    _migrate_legacy(s)

    def pick(base_k, key_k, model_k):
        return {
            "api_base": s.get(base_k) or "",
            "api_key": s.get(key_k) or "",
            "model": s.get(model_k) or "",
        }

    prof = _profile_by_id(s, profile_id if kind == "ppt" else None)
    if prof and prof.get("base") and prof.get("model"):
        return {"api_base": prof["base"], "api_key": prof.get("key", ""),
                "model": prof["model"]}

    ppt = pick("ppt_llm_api_base", "ppt_llm_api_key", "ppt_llm_model")
    if not (ppt["api_base"] and ppt["model"]):
        ppt = pick("llm_api_base", "llm_api_key", "llm_model")

    if kind == "ppt":
        return ppt
    if s.get("script_llm_same", True):
        return ppt
    sc = pick("script_llm_api_base", "script_llm_api_key", "script_llm_model")
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
