"""逐页解说词生成（v0.4.0）。

核心原则：解说词必须以每页的标题和要点为素材展开，禁止与页面内容无关的套话。
LLM 可用时：整篇统筹（过渡自然、口语化）；不可用时：内容型模板兜底，
把要点改写成口语句子，而不是复读标题。
"""
import json
import re
import urllib.request
from typing import Dict, List

from ..config import load_settings

SCRIPT_PROMPT = """你是一名专业的演讲撰稿人。下面是一份 PPT 的逐页内容（JSON），请为每一页写口语讲解词。

硬性要求：
1. 每页讲解词必须**基于该页的实际内容**（标题+要点）展开：把要点改写成自然的口语，补充一两句解释或衔接；禁止只复读标题，禁止使用与页面内容无关的套话。
2. 每页 60~150 字；页与页之间有自然过渡（不要每页都用"接下来，我们来看"）。
3. 第一页是开场白（问候+主题+预告结构）；最后一页是收尾（总结+致谢）。
4. 只输出 JSON 数组（字符串数组，与页面对应），不要输出任何其他文字。

主题：{topic}
语气：{tone}

页面内容：
{pages}"""


def _llm_call(payload_prompt: str, timeout: int = 180) -> str | None:
    from ..config import llm_settings

    cfg = llm_settings("script")
    if not (cfg["api_base"] and cfg["model"]):
        return None
    base = cfg["api_base"].rstrip("/")
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": payload_prompt}],
        "temperature": 0.7,
    }
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    try:
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def _llm_pages(topic: str, slides: List[Dict], tone: str) -> List[str] | None:
    content = json.dumps(
        [{"title": x.get("title", ""), "bullets": x.get("bullets", [])} for x in slides],
        ensure_ascii=False,
    )
    text = _llm_call(SCRIPT_PROMPT.format(topic=topic, tone=tone, pages=content))
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return None
    if isinstance(arr, list) and len(arr) == len(slides):
        return [str(x).strip() for x in arr]
    return None


# ---------------------------------------------------------------------------
# 内容型模板兜底
# ---------------------------------------------------------------------------

_TRANSITIONS = ["", "首先，", "接下来，", "然后，", "再来看", "另一方面，", "此外，", "最后来看"]


def _clean_spoken(b: str) -> str:
    """清理不适合口播的符号：抓取资料的【标题】包装、日期前缀、markdown 残留。"""
    b = re.sub(r"^[\s\-•·\d.、]+", "", str(b)).strip()
    b = re.sub(r"^【([^】]{0,40})】\s*", "", b)          # 去掉开头【...】
    b = re.sub(r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?\s*[·•]?\s*", "", b)  # 去日期前缀
    b = re.sub(r"^[\s·•]+", "", b)
    return b.strip()


def _bullet_to_sentence(b: str) -> str:
    """把要点文本改写成口语句。"""
    b = _clean_spoken(b)
    if not b:
        return ""
    if b.endswith(("。", "！", "？", "；")):
        return b
    return b + "。"


def _template_pages(topic: str, slides: List[Dict], tone: str) -> List[str]:
    pages: List[str] = []
    total = len(slides)
    section_titles = [s.get("title", "") for s in slides[1:-1] if s.get("title")]

    for i, s in enumerate(slides):
        title = (s.get("title", "") or "").strip()
        bullets = [b for b in (s.get("bullets", []) or []) if str(b).strip()]

        if i == 0:
            # 封面：问候 + 主题 + 预告章节（不念副标题/汇报人）
            if section_titles:
                preview = "、".join(section_titles[:3])
                text = f"大家好，欢迎来到今天的分享。今天的主题是「{topic}」。我们会从{preview}等几个部分，把这件事讲清楚。"
            else:
                text = f"大家好，欢迎来到今天的分享。今天的主题是「{topic}」，下面正式开始。"
        elif i == total - 1:
            # 总结页：回顾要点 + 收尾
            key = _clean_spoken(str(bullets[0])) if bullets else title
            tail = _bullet_to_sentence(key) if key else ""
            text = f"最后做个总结。{tail}以上就是今天分享的全部内容，感谢大家的聆听，欢迎会后交流讨论。"
        else:
            # 内容页：把要点织进口语里
            parts = [_bullet_to_sentence(str(b)) for b in bullets[:3]]
            body = "".join(parts) if parts else f"这一页讲的是{title}。"
            trans = _TRANSITIONS[min(i, len(_TRANSITIONS) - 1)]
            if i == 1:
                text = f"首先进入正题——{title}。{body}"
            elif i == total - 2:
                text = f"在收尾之前，重点看一下{title}。{body}"
            else:
                text = f"{trans}{title}。{body}" if trans else f"{title}。{body}"

        pages.append(re.sub(r"\s+", " ", text).strip())

    return pages


def generate_script(topic: str, slides: List[Dict], tone: str = "专业", progress=None) -> Dict:
    rep = progress or (lambda stage, ratio: None)

    rep(0.2, "正在通读 PPT 内容…")
    pages = _llm_pages(topic, slides, tone)
    source = "llm"
    if not pages:
        rep(0.6, "使用内容模板撰写解说词…")
        pages = _template_pages(topic, slides, tone)
        source = "template"
    rep(0.95, "解说词完成")
    return {"pages": pages, "source": source}
