"""逐页解说词生成：模板引擎 + 可选 LLM（OpenAI 兼容协议）。"""
import json
import re
import urllib.request
from typing import Dict, List

from ..config import load_settings

SYSTEM_PROMPT = (
    "你是一名专业的演讲撰稿人。根据 PPT 每页的标题和要点，为每一页写一段口语化讲解词。"
    "输出 JSON 数组，元素为字符串，与页面对应，每页 60~150 字，含自然过渡。只输出 JSON 数组。"
)


def _llm_pages(topic: str, slides: List[Dict], tone: str) -> List[str] | None:
    s = load_settings()
    if not (s.get("llm_api_base") and s.get("llm_model")):
        return None
    base = s["llm_api_base"].rstrip("/")
    content = json.dumps(
        [{"title": x.get("title", ""), "bullets": x.get("bullets", [])} for x in slides],
        ensure_ascii=False,
    )
    payload = {
        "model": s["llm_model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"主题：{topic}\n语气：{tone}\n页面：{content}"},
        ],
        "temperature": 0.7,
    }
    headers = {"Content-Type": "application/json"}
    if s.get("llm_api_key"):
        headers["Authorization"] = f"Bearer {s['llm_api_key']}"
    try:
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        m = re.search(r"\[.*\]", text, re.S)
        arr = json.loads(m.group(0)) if m else None
        if arr and isinstance(arr, list) and len(arr) == len(slides):
            return [str(x).strip() for x in arr]
    except Exception:
        return None
    return None


def _template_pages(topic: str, slides: List[Dict], tone: str) -> List[str]:
    pages: List[str] = []
    total = len(slides)
    for i, s in enumerate(slides):
        title = s.get("title", "")
        bullets = s.get("bullets", []) or []
        if i == 0:
            text = (
                f"大家好，欢迎来到今天的分享。本次的主题是「{title}」，"
                f"接下来我会用几页内容，为大家讲清楚核心思路和落地方案。"
            )
        elif i == total - 1:
            text = (
                "以上就是今天的全部内容。我们回顾了核心要点，也明确了下一步的行动计划。"
                "感谢大家的聆听，欢迎交流讨论。"
            )
        else:
            detail = "；".join(bullets[:2]) if bullets else title
            trans = "首先" if i == 1 else ("最后" if i == total - 2 else "接下来")
            text = f"{trans}，我们来看「{title}」这一部分。{detail}。这一块是整体方案中承上启下的关键环节。"
        pages.append(text)
    return pages


def generate_script(topic: str, slides: List[Dict], tone: str = "专业") -> Dict:
    pages = _llm_pages(topic, slides, tone)
    source = "llm"
    if not pages:
        pages = _template_pages(topic, slides, tone)
        source = "template"
    return {"pages": pages, "source": source}
