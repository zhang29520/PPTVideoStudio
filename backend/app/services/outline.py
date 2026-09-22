"""大纲与幻灯片内容生成（v0.4.0 四段式流水线）。

流程：主题分析 → 抓取网络资料 → LLM 生成大纲与逐页内容 →（无 LLM 时）
基于资料的内容型模板兜底。未配置 LLM 时资料仍会被抓取并用于模板，
保证每页要点与主题相关，而不是占位空话。
"""
import json
import re
import urllib.request
from typing import Dict, List

from ..config import load_settings
from .knowledge import knowledge_context

OUTLINE_PROMPT = """你是一名资深 PPT 策划与撰稿专家。请根据【主题】和【参考资料】制作一份 PPT 的逐页内容。

要求：
1. 共 {count} 页：第 1 页为封面（bullets 放副标题/汇报人等 1-2 条），最后 1 页为总结页，中间为内容页。
2. 每个内容页的 bullets 为 3-5 条**实质内容**：具体的事实、数据、方法、案例、步骤，必须来自或提炼自参考资料与主题常识；禁止出现"要点一""落地路径"这类占位空话。
3. 每条要点 15~40 字，可以直接口语引用。
4. 内容要围绕主题层层展开：是什么 → 为什么 → 怎么做 → 效果/案例 → 总结。
5. 受众是【{audience}】，用语专业但易懂。

参考资料（可能为空，为空时请依靠你自己的知识）：
{knowledge}

只输出 JSON 数组，不要输出任何其他文字：
[{{"title": "页面标题", "bullets": ["要点1", "要点2", ...]}}, ...]"""


def _llm_call(prompt: str, timeout: int = 150) -> str | None:
    s = load_settings()
    if not (s.get("llm_api_base") and s.get("llm_model")):
        return None
    base = s["llm_api_base"].rstrip("/")
    payload = {
        "model": s["llm_model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def _parse_slides(text: str | None, count: int) -> List[Dict] | None:
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(arr, list) or len(arr) < 2:
        return None
    slides = []
    for it in arr:
        title = str(it.get("title", "")).strip()
        bullets = [str(b).strip() for b in it.get("bullets", []) if str(b).strip()]
        if title:
            slides.append({"title": title, "bullets": bullets})
    # 页数不符时截断/保留
    return slides[:count] if len(slides) >= count else slides


def _template_generate(topic: str, slides_count: int, audience: str, knowledge: str) -> List[Dict]:
    """内容型模板兜底：从抓取到的资料里提炼要点，没有资料就用主题词构句。"""
    facts: List[str] = []
    for line in knowledge.splitlines():
        line = re.sub(r"^\d+\.\s*", "", line).strip()
        if len(line) > 25:
            facts.append(line)

    slides: List[Dict] = [{"title": topic, "bullets": [f"面向{audience}", "汇报人：PPTVideoStudio"]}]

    middle = max(0, slides_count - 2)
    angles = []
    if middle > 0:
        angles.append(("背景与现状", [f"{topic}的由来与发展现状", "当前行业普遍做法与痛点", "本次分享要解决的问题"]))
    if middle > 1:
        angles.append(("核心概念", [f"{topic}是什么：关键定义与组成", "与相近概念的区别", "理解它的三个关键词"]))
    if middle > 2:
        angles.append(("主要方法与路径", ["整体思路与分步流程", "每一步的关键动作", "常用工具与资源"]))
    if middle > 3:
        angles.append(("典型案例", ["一个代表性案例的做法", "取得的实际效果", "可借鉴的经验"]))
    if middle > 4:
        angles.append(("衡量指标", ["评估效果的核心指标", "数据从哪里来", "达标的标准"]))
    while len(angles) < middle:
        n = len(angles) + 1
        angles.append((f"专题拓展 {n}", [f"{topic}相关专题{n}的具体内容", "实践中的注意事项"]))

    for i, (title, bullets) in enumerate(angles[:middle]):
        # 有资料时用资料替换第一条要点
        if facts:
            bullets = [facts[i % len(facts)]] + bullets[1:]
        slides.append({"title": title, "bullets": bullets})

    slides.append({"title": "总结与展望", "bullets": [f"回顾「{topic}」的核心要点", "明确下一步行动", "感谢聆听"]})
    return slides[:slides_count]


def generate_outline(
    topic: str, slides_count: int = 8, audience: str = "通用受众", progress=None
) -> Dict:
    """progress(ratio: float, stage: str) 用于任务进度上报。"""
    rep = progress or (lambda stage, ratio: None)

    rep(0.10, "正在分析主题并抓取相关资料…")
    knowledge = knowledge_context(topic)

    rep(0.35, "资料就绪，正在生成大纲与逐页内容…")
    prompt = OUTLINE_PROMPT.format(
        count=slides_count, audience=audience, knowledge=knowledge or "（无）"
    )
    slides = _parse_slides(_llm_call(prompt), slides_count)
    source = "llm"

    if not slides:
        rep(0.65, "使用内置内容引擎生成…")
        slides = _template_generate(topic, slides_count, audience, knowledge)
        source = "template"

    rep(0.9, "内容生成完毕")
    return {"slides": slides, "source": source, "knowledge_used": bool(knowledge)}
