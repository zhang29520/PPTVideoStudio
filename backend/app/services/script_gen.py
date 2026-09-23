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

# 「关键词：描述」结构（用于把要点改写成口语句）；排除 URL 误匹配
_KV_RE = re.compile(r"^(?!https?://)([^：:]{1,24})[：:]\s*(.+)$", re.S)

SCRIPT_PROMPT = """你是一名专业的演讲撰稿人。下面是一份 PPT 的逐页内容（JSON），请为每一页写口语讲解词。

硬性要求：
1. **分析式讲解，不是朗读**：把每页要点当作论据素材，解读它的意义、原因、影响或对比；禁止把页面上的文字一字不差地念出来。要点里的数字和结论可以引用，但必须融入你自己的分析语句。
2. 每页讲解词必须基于该页主题展开，与页面内容强相关；禁止无关套话。
3. 每页 60~150 字；页与页之间有自然过渡（不要每页都用"接下来，我们来看"）。
4. 第一页是开场白（问候+主题+预告结构）；最后一页是收尾（总结+致谢）。
5. **页数严格一致**：输入共 {n} 页，你的输出数组必须恰好 {n} 个字符串元素，按输入顺序一一对应；目录页、章节过渡页也要写（可用一句承上启下的过渡语，禁止跳过或合并任何页）。
6. 只输出 JSON 数组（字符串数组，与页面对应），不要输出任何其他文字。

主题：{topic}
语气：{tone}

页面内容：
{pages}"""


def _llm_call(payload_prompt: str, timeout: int = 180) -> str | None:
    """兼容旧签名：只返回内容（错误丢弃，用 _llm_call_err 取错误）。"""
    text, _ = _llm_call_err(payload_prompt, timeout)
    return text


def _llm_call_err(payload_prompt: str, timeout: int = 180) -> tuple[str | None, str | None]:
    from ..config import llm_settings

    cfg = llm_settings("script")
    if not (cfg["api_base"] and cfg["model"]):
        return None, None
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
        return data["choices"][0]["message"]["content"], None
    except Exception as e:
        detail = ""
        if hasattr(e, "read"):
            try:
                detail = e.read().decode("utf-8", "ignore")[:200]
            except Exception:
                pass
        return None, detail or str(e)[:200]


def _parse_llm_pages(text: str, n_slides: int) -> tuple[List[str] | None, str | None]:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None, "AI 返回格式异常（未找到 JSON 数组）"
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return None, "AI 返回格式异常（JSON 解析失败）"
    if isinstance(arr, list) and len(arr) == n_slides:
        return [str(x).strip() for x in arr], None
    return None, f"AI 返回页数不符（{len(arr) if isinstance(arr, list) else '?'} / {n_slides}）"


def _llm_pages(topic: str, slides: List[Dict], tone: str) -> tuple[List[str] | None, str | None]:
    content = json.dumps(
        [{"title": x.get("title", ""), "bullets": x.get("bullets", [])} for x in slides],
        ensure_ascii=False,
    )
    prompt = SCRIPT_PROMPT.format(topic=topic, tone=tone, pages=content, n=len(slides))
    text, err = _llm_call_err(prompt)
    if not text:
        return None, err
    pages, perr = _parse_llm_pages(text, len(slides))
    if pages:
        return pages, None
    # 页数不符：带着错误原因重试一次（强调严格页数），仍失败才兜底
    retry_prompt = (
        f"你上次的输出{perr}。请重新完成任务：输出数组必须恰好 {len(slides)} 个元素，"
        f"与输入页面按顺序一一对应，禁止跳过、合并或增删页面。\n\n{prompt}"
    )
    text2, err2 = _llm_call_err(retry_prompt)
    if text2:
        pages2, _ = _parse_llm_pages(text2, len(slides))
        if pages2:
            return pages2, None
    return None, perr if perr else err2


# ---------------------------------------------------------------------------
# 内容型模板兜底
# ---------------------------------------------------------------------------

_TRANSITIONS = ["", "首先，", "接下来，", "然后，", "再来看", "另一方面，", "此外，", "最后来看"]

# 口播垃圾行：网页导航/协议文字等不适合念出来的内容
_SPOKEN_JUNK = (
    "用户协议", "隐私政策", "登录政策", "立即注册", "忘记密码", "扫码",
    "版权所有", "ICP", "收藏本站", "设为首页", "下载客户端", "关注我们",
    "联系客服", "意见反馈", "退出登录", "汇报人：",
)


def _is_junk_spoken(s: str) -> bool:
    return any(w in s for w in _SPOKEN_JUNK)


def _clean_spoken(b: str) -> str:
    """清理不适合口播的符号：抓取资料的【标题】包装、日期/相对时间前缀、markdown 残留。"""
    b = re.sub(r"^[\s\-•·\d.、]+", "", str(b)).strip()
    b = re.sub(r"^【([^】]{0,40})】\s*", "", b)          # 去掉开头【...】
    b = re.sub(r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?\s*[·•]?\s*", "", b)  # 去日期前缀
    b = re.sub(r"\d+\s*(天|小时|分钟|周|个月|月|年)前\s*[·•]?\s*", "", b)  # 去相对时间
    b = re.sub(r"^[\s·•]+", "", b)
    return b.strip()


def _bullet_to_sentence(b: str, first: bool = False) -> str:
    """把要点文本改写成口语句（带分析框架，避免逐字念 PPT）。"""
    b = _clean_spoken(b)
    if not b:
        return ""
    m = _KV_RE.match(b)
    if m:  # 「关键词：描述」→「在关键词方面，描述」
        k, v = m.group(1).strip(), m.group(2).strip()
        conj = "首先，" if first else "同时，"
        if v.endswith(("。", "！", "？", "；")):
            return f"{conj}在{k}方面，{v}"
        return f"{conj}在{k}方面，{v}。"
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
        bullets = [b for b in bullets if not _is_junk_spoken(str(b))]

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
            # 内容页：把要点织进分析式口播里（不逐字念原文）
            parts = [_bullet_to_sentence(str(b), first=(j == 0)) for j, b in enumerate(bullets[:3])]
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


ONE_PAGE_PROMPT = """你是一名专业的演讲撰稿人。下面是一份 PPT 中某一页的内容，请为这一页写口语讲解词。

硬性要求：
1. **分析式讲解，不是朗读**：把要点当作论据，解读意义、原因或影响；禁止把页面文字一字不差地念出来，数字和结论可引用但必须融入分析语句。
2. 60~150 字，口语化，可直接朗读。
{ctx}3. 只输出讲解词正文，不要输出任何其他文字（不要序号、不要标题、不要引号）。

主题：{topic}
语气：{tone}
这一页是第 {index} 页（共 {total} 页，{pos}）。

页面内容：
{page}"""


def generate_one_script(topic: str, slide: Dict, index: int, total: int,
                        tone: str = "专业", prev_text: str = "") -> str:
    """为单独一页生成解说词：LLM 优先，模板兜底。index 从 0 计。"""
    pos = "开场页" if index == 0 else ("收尾页" if index == total - 1 else "内容页")
    ctx = ""
    if prev_text:
        ctx = f"上一页解说词结尾是「…{prev_text[-40:]}」，请自然衔接。\n"
    page_json = json.dumps(
        {"title": slide.get("title", ""), "bullets": slide.get("bullets", [])},
        ensure_ascii=False,
    )
    prompt = ONE_PAGE_PROMPT.format(
        ctx=ctx, topic=topic, tone=tone, index=index + 1, total=total,
        pos=pos, page=page_json,
    )
    text, _err = _llm_call_err(prompt, timeout=60)
    if text:
        cleaned = text.strip().strip('"“”「」').strip()
        cleaned = re.sub(r"^\d+[.、]\s*", "", cleaned)  # 去掉 AI 可能加的序号
        if cleaned:
            return cleaned
    # 模板兜底
    return _template_single(topic, slide, index, total)


def _template_single(topic: str, slide: Dict, index: int, total: int) -> str:
    """单页模板兜底（与整篇模板同一套口播规则）。"""
    title = (slide.get("title", "") or "").strip()
    bullets = [b for b in (slide.get("bullets", []) or []) if str(b).strip()]
    bullets = [b for b in bullets if not _is_junk_spoken(str(b))]
    if index == 0:
        if bullets:
            preview = "、".join(_clean_spoken(str(b)).split("：")[0] for b in bullets[:3])
            text = f"大家好，欢迎来到今天的分享。今天的主题是「{topic}」。我们会从{preview}等方面展开。"
        else:
            text = f"大家好，欢迎来到今天的分享。今天的主题是「{topic}」，下面正式开始。"
    elif index == total - 1:
        key = _clean_spoken(str(bullets[0])) if bullets else title
        tail = _bullet_to_sentence(key) if key else ""
        text = f"最后做个总结。{tail}以上就是今天分享的全部内容，感谢大家的聆听。"
    else:
        parts = [_bullet_to_sentence(str(b)) for b in bullets[:3]]
        body = "".join(parts) if parts else f"这一页讲的是{title}。"
        text = f"接下来看{title}。{body}"
    return re.sub(r"\s+", " ", text).strip()


def generate_script(topic: str, slides: List[Dict], tone: str = "专业", progress=None) -> Dict:
    rep = progress or (lambda stage, ratio: None)

    rep(0.2, "AI 正在通读 PPT 内容并撰写解说词…")
    pages, llm_error = _llm_pages(topic, slides, tone)
    source = "llm"
    if not pages:
        if llm_error:
            rep(0.6, f"AI 调用失败，使用模板兜底…")
        else:
            rep(0.6, "使用内容模板撰写解说词…")
        pages = _template_pages(topic, slides, tone)
        source = "template"
    rep(0.95, "解说词完成")
    return {"pages": pages, "source": source, "llm_error": llm_error}
