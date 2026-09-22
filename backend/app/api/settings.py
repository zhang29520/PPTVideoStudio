from fastapi import APIRouter

from ..config import load_settings, llm_settings, save_settings

router = APIRouter()


@router.get("/api/settings")
def get_settings():
    s = load_settings()
    # 旧版单 AI 配置迁移为列表并落盘，前端列表 UI 直接可用
    from ..config import _migrate_legacy

    migrated = _migrate_legacy(s)
    if migrated != s:
        save_settings(migrated)
        s = migrated
    return s


@router.put("/api/settings")
def update_settings(payload: dict):
    merged = save_settings(payload or {})
    return {"message": "设置已保存", "settings": merged}


@router.post("/api/settings/test_llm")
def test_llm(payload: dict = None):
    """用指定（或默认）AI 配置发一条测试消息，返回连通结果。"""
    import json
    import urllib.request

    profile_id = (payload or {}).get("profile_id")
    cfg = llm_settings("ppt", profile_id=profile_id)
    if not (cfg["api_base"] and cfg["model"]):
        return {"ok": False, "error": "请先填写 API 地址和模型名"}
    base = cfg["api_base"].rstrip("/")
    payload = {"model": cfg["model"],
               "messages": [{"role": "user", "content": "请回复：连通正常"}],
               "max_tokens": 16}
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    try:
        req = urllib.request.Request(f"{base}/chat/completions",
                                     data=json.dumps(payload).encode("utf-8"),
                                     headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"]
        return {"ok": True, "reply": reply[:50], "model": data.get("model", cfg["model"])}
    except Exception as e:
        detail = ""
        if hasattr(e, "read"):
            try:
                detail = e.read().decode("utf-8", "ignore")[:200]
            except Exception:
                pass
        return {"ok": False, "error": detail or str(e)[:200]}
