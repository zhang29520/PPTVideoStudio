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
    from ..config import llm_settings

    cfg = llm_settings("ppt")
    if not (cfg["api_base"] and cfg["model"]):
        return None
    base = cfg["api_base"].rstrip("/")
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
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
    """内容型模板兜底：把抓取到的资料逐条分配到各页，没有资料就用主题词构句。"""
    facts: List[str] = []
    for line in knowledge.splitlines():
        line = re.sub(r"^\d+\.\s*", "", line).strip()
        # 清理资料来源装饰：开头【标题】、日期前缀、来源符号
        line = re.sub(r"^【([^】]{0,40})】\s*", "", line)
        line = re.sub(r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?\s*[·•]?\s*", "", line)
        line = re.sub(r"^[\s·•\-]+", "", line).strip()
        # 去掉与标题重复的开头（如 "PFAS的介绍PFAS为..." 这类拼接）
        if 25 <= len(line) <= 90:
            facts.append(line)

    slides: List[Dict] = [{"title": topic, "bullets": [f"面向{audience}", "汇报人：PPTVideoStudio"]}]

    middle = max(0, slides_count - 2)
    angle_titles = ["背景与现状", "核心概念解读", "主要方法与路径", "典型案例分析",
                    "关键数据与指标", "常见问题与对策", "实践要点", "行业趋势",
                    "工具与资源", "风险与合规", "实施步骤建议"]
    angle_pool = (angle_titles * ((middle // len(angle_titles)) + 1))[:middle]

    # 把资料均摊到各内容页：每页尽量 2 条资料；资料不足时用自然衔接句
    per_page = max(1, (len(facts) + middle - 1) // max(1, middle)) if facts else 0
    fi = 0
    fillers = [
        "这一部分我们将结合具体场景展开说明",
        "下面通过实际案例进一步讲解",
        "这里重点关注方法与落地路径",
        "这部分内容与整体目标密切相关",
        "接下来看实践中的具体做法",
    ]
    for i, title in enumerate(angle_pool):
        bullets: List[str] = []
        for _ in range(per_page):
            if fi < len(facts):
                bullets.append(facts[fi])
                fi += 1
        if not bullets:
            bullets = [f"围绕「{title}」，{topic}的核心做法与要点"]
        if len(bullets) == 1:
            bullets.append(fillers[i % len(fillers)])
        slides.append({"title": title, "bullets": bullets[:4]})

    closing = [f"回顾「{topic}」的核心要点"]
    if facts:
        closing.append(facts[-1])
    closing += ["明确下一步行动", "感谢聆听"]
    slides.append({"title": "总结与展望", "bullets": closing})
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
