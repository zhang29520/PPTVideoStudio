"""大纲与幻灯片内容生成。

两级策略：
1. 配置了 LLM（OpenAI 兼容协议）→ 调用 LLM 生成结构化 JSON
2. 未配置 → 内置模板引擎，根据主题拼装大纲（可离线运行）
"""
import json
import re
import urllib.request
from typing import List, Dict

from ..config import load_settings

SYSTEM_PROMPT = (
    "你是一名专业的 PPT 策划师。根据用户给定的主题，输出一个 JSON 数组，"
    "每个元素形如 {\"title\": \"页面标题\", \"bullets\": [\"要点1\", \"要点2\", ...]}。"
    "第一页为封面（bullets 可为副标题），最后一页为总结/致谢。"
    "只输出 JSON 数组，不要输出任何其他文字。"
)

TEMPLATE_COVER_HINTS = [
    "背景与现状",
    "核心思路",
    "实施方案",
    "关键亮点",
    "数据与成效",
    "风险与对策",
    "下一步计划",
]


def _llm_generate(topic: str, slides_count: int, audience: str) -> List[Dict] | None:
    s = load_settings()
    if not (s.get("llm_api_base") and s.get("llm_model")):
        return None
    base = s["llm_api_base"].rstrip("/")
    url = f"{base}/chat/completions"
    payload = {
        "model": s["llm_model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"主题：{topic}\n页数：{slides_count}\n受众：{audience}",
            },
        ],
        "temperature": 0.7,
    }
    headers = {"Content-Type": "application/json"}
    if s.get("llm_api_key"):
        headers["Authorization"] = f"Bearer {s['llm_api_key']}"
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        m = re.search(r"\[.*\]", text, re.S)
        slides = json.loads(m.group(0)) if m else None
        if slides and isinstance(slides, list) and len(slides) >= 2:
            return [
                {
                    "title": str(it.get("title", "")).strip(),
                    "bullets": [str(b).strip() for b in it.get("bullets", []) if str(b).strip()],
                }
                for it in slides
            ]
    except Exception:
        return None
    return None


def _template_generate(topic: str, slides_count: int, audience: str) -> List[Dict]:
    """内置模板：封面 + 3~6 个内容页 + 总结页。"""
    slides: List[Dict] = [
        {"title": topic, "bullets": [f"面向{audience}", "汇报人：PPTVideoStudio"]}
    ]
    hints = TEMPLATE_COVER_HINTS[:]
    while len(hints) < max(0, slides_count - 2):
        hints.append(f"专题拓展 {len(hints) + 1}")
    for i in range(max(0, slides_count - 2)):
        h = hints[i]
        slides.append(
            {
                "title": h,
                "bullets": [
                    f"{h}：围绕「{topic}」的关键要点一",
                    f"{h}：落地路径与执行节奏",
                    f"{h}：衡量指标与预期效果",
                ],
            }
        )
    slides.append(
        {"title": "总结与展望", "bullets": ["回顾核心要点", "明确下一步行动", "感谢聆听"]}
    )
    return slides[:slides_count] if slides_count <= len(slides) else slides


def generate_outline(topic: str, slides_count: int = 8, audience: str = "通用受众") -> Dict:
    slides = _llm_generate(topic, slides_count, audience)
    source = "llm"
    if not slides:
        slides = _template_generate(topic, slides_count, audience)
        source = "template"
    return {"slides": slides, "source": source}
