"""大纲与幻灯片内容生成。

LLM 可用时走两阶段：① 大纲（页标题+每页方向）→ ② 逐页扩写成实质要点
（结合抓取资料，要求数据/案例/动作），比单次生成深度明显更好。
LLM 失败时回退内容型模板，并把失败原因带回去显式提示用户。
"""
import json
import re
import urllib.request
from typing import Dict, List

from ..config import load_settings
from .knowledge import knowledge_context

OUTLINE_PROMPT = """你是一名资深 PPT 策划专家。请为主题「{topic}」设计一份 {count} 页的 PPT 大纲（受众：{audience}）。

要求：
1. 第 1 页为封面（title=主题本身），最后 1 页为总结页，中间内容页结构多样（背景/现状数据/核心概念/方法路径/案例/对比/问题对策/趋势建议等，按主题特点选择）。
2. 每页输出 title（12 字内）和 focus（这一页要讲什么方向，20~40 字，具体到要点维度，禁止空话）。

参考资料（可能为空）：
{knowledge}

只输出 JSON 数组：[{{"title": "...", "focus": "..."}}, ...]"""

CONTENT_PROMPT = """你是一名资深行业分析师兼 PPT 撰稿人。请把下面的大纲扩写成内容详实的 PPT。

主题：{topic}（受众：{audience}）

大纲：
{outline}

参考资料：
{knowledge}

硬性要求：
1. 保持大纲的页数与标题不变。
2. 每页必须有 lead 字段：一句 25~45 字的导语，概括本页核心观点（放标题下方作副标题）。
3. 每个内容页 4~5 条 bullets；每条必须是「关键词：描述」格式——
   关键词 2~8 字（如"市场规模""政策红利""落地三步"），冒号用中文"："，
   描述 30~60 字，必须包含具体数据、案例、时间、对比或步骤等至少两项实质信息。
   示例："市场规模：2026 年全国智慧文旅市场规模预计突破 800 亿元，近五年复合增长率达 21.5%，夜游细分赛道增速领先大盘"
4. 信息密度红线：每页至少出现 2 个具体数字（金额/百分比/年份/数量级），不足就用参考资料补齐或用公认行业常识补充，但禁止编造精确数据。
5. 封面页 bullets 放 1~2 条副标题；总结页放 3~4 条核心回顾（带关键词前缀）。
6. 禁止"要点一""核心内容""效果显著"这类空话；每条描述读完必须让人带走一个信息点。

只输出 JSON 数组：[{{"title": "...", "lead": "...", "bullets": ["...", ...]}}, ...]"""


def _chat(base: str, key: str, model: str, prompt: str, temperature: float,
          timeout: int = 150) -> tuple[str | None, str | None]:
    """调用 OpenAI 兼容接口，返回 (content, error)。"""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
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


def _parse_json_array(text: str | None):
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _template_generate(topic: str, slides_count: int, audience: str, knowledge: str) -> List[Dict]:
    """内容型模板兜底：把抓取到的资料逐条分配到各页，没有资料就用主题词构句。"""
    facts: List[str] = []
    for line in knowledge.splitlines():
        line = re.sub(r"^\d+\.\s*", "", line).strip()
        # 清理资料来源装饰：开头【标题】、日期前缀、来源符号
        line = re.sub(r"^【([^】]{0,40})】\s*", "", line)
        line = re.sub(r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?\s*[·•]?\s*", "", line)
        line = re.sub(r"^[\s·•\-]+", "", line).strip()
        if 25 <= len(line) <= 90:
            facts.append(line)

    slides: List[Dict] = [{"title": topic, "bullets": [f"面向{audience}", "汇报人：PPTVideoStudio"]}]

    middle = max(0, slides_count - 2)
    angle_titles = ["背景与现状", "核心概念解读", "主要方法与路径", "典型案例分析",
                    "关键数据与指标", "常见问题与对策", "实践要点", "行业趋势",
                    "工具与资源", "风险与合规", "实施步骤建议"]
    angle_pool = (angle_titles * ((middle // len(angle_titles)) + 1))[:middle]

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
            bullets = [f"核心要点：围绕「{title}」，{topic}的核心做法与实施路径"]
        if len(bullets) == 1:
            bullets.append(fillers[i % len(fillers)])
        # 结构化为「关键词：描述」，供版式引擎拆分渲染
        bullets = [_structure_line(b, i) for b in bullets[:4]]
        slides.append({"title": title, "bullets": bullets,
                       "lead": f"从「{title}」看{topic.replace('分析报告', '').replace('汇报', '')}的关键事实与行动要点"})

    closing = [f"回顾「{topic}」的核心要点"]
    if facts:
        closing.append(facts[-1])
    closing += ["明确下一步行动", "感谢聆听"]
    slides.append({"title": "总结与展望", "bullets": closing})
    return slides[:slides_count]


def _structure_line(line: str, page_idx: int) -> str:
    """模板路径的要点行 →「关键词：描述」结构（已有前缀则原样保留）。"""
    import re as _re
    if _re.match(r"^[^，,。：:|]{2,8}[：:|]", line):
        return line
    m = _re.match(r"([^，,]{2,6})[，,]", line)
    if m:
        return f"{m.group(1)}：{line[m.end():].strip()}"
    return f"核心要点：{line}"


def _llm_generate(topic: str, slides_count: int, audience: str, knowledge: str,
                  progress=None, profile_id: str | None = None) -> tuple[List[Dict] | None, str | None]:
    """两阶段 LLM 生成：大纲 → 逐页扩写。失败返回 (None, error)。"""
    from ..config import llm_settings

    rep = progress or (lambda stage, ratio: None)
    cfg = llm_settings("ppt", profile_id=profile_id)
    if not (cfg["api_base"] and cfg["model"]):
        return None, None  # 未配置不算错误

    base = cfg["api_base"].rstrip("/")

    # 阶段 1：大纲
    rep(0.40, "AI 正在策划大纲…")
    text, err = _chat(base, cfg["api_key"], cfg["model"],
                      OUTLINE_PROMPT.format(topic=topic, count=slides_count,
                                            audience=audience,
                                            knowledge=knowledge or "（无）"),
                      temperature=0.5)
    if err:
        return None, f"AI 大纲生成失败：{err}"
    outline = _parse_json_array(text)
    if not isinstance(outline, list) or len(outline) < 2:
        return None, "AI 返回的大纲格式异常"

    outline = outline[:slides_count]
    outline_text = json.dumps(outline, ensure_ascii=False, indent=1)

    # 阶段 2：逐页扩写
    rep(0.60, "AI 正在逐页撰写内容…")
    text, err = _chat(base, cfg["api_key"], cfg["model"],
                      CONTENT_PROMPT.format(topic=topic, audience=audience,
                                            outline=outline_text,
                                            knowledge=knowledge or "（无）"),
                      temperature=0.6, timeout=240)
    if err:
        return None, f"AI 内容生成失败：{err}"
    arr = _parse_json_array(text)
    if not isinstance(arr, list) or len(arr) < 2:
        return None, "AI 返回的内容格式异常"

    slides = []
    for it in arr:
        title = str(it.get("title", "")).strip()
        bullets = [str(b).strip() for b in it.get("bullets", []) if str(b).strip()]
        if title:
            s = {"title": title, "bullets": bullets}
            lead = str(it.get("lead", "")).strip()
            if lead:
                s["lead"] = lead
            slides.append(s)
    if len(slides) < 2:
        return None, "AI 返回的内容页数不足"
    return slides[:slides_count], None


# ---------- 主题分析：场景识别 → 封面设计模板 ----------

_SCENE_KEYWORDS = {
    "gov": ("党建", "政府", "政务", "法治", "安全", "宣传", "文明", "主题教", "纪委",
            "公安", "检察", "财政", "民生", "乡村振兴", "红色"),
    "tech": ("AI", "科技", "数字", "智能", "互联网", "软件", "数据", "云计算",
             "区块链", "5G", "芯片", "机器人", "算法", "大模型", "agent", "it", "系统"),
    "culture": ("文化", "艺术", "历史", "传统", "国潮", "非遗", "旅游", "文创",
                "博物馆", "书画", "国学", "文旅"),
    "education": ("教育", "教学", "课程", "学校", "培训", "学生", "校园", "课件",
                  "招生", "毕业"),
    "fresh": ("健康", "环保", "生态", "农业", "食品", "医疗", "绿色", "公益"),
}


def analyze_topic(topic: str) -> str:
    """主题 → 设计方案 key（tech/gov/culture/education/fresh/business）。"""
    t = (topic or "").lower()
    best, hits = "business", 0
    for key, words in _SCENE_KEYWORDS.items():
        n = sum(1 for w in words if w.lower() in t)
        if n > hits:
            best, hits = key, n
    return best


def generate_outline(
    topic: str, slides_count: int = 8, audience: str = "通用受众", progress=None,
    use_llm: bool = True, profile_id: str | None = None, material: str | None = None,
) -> Dict:
    """progress(stage: str, ratio: float) 用于任务进度上报。

    use_llm=False 时跳过 LLM 直接用内置引擎（首页可选择生成引擎）。
    profile_id 指定使用哪个已保存的 AI 配置（空=默认）。
    material 非空时（Word 导入）跳过网络资料抓取，直接以文档内容为素材生成。
    返回 {slides, source, knowledge_used, llm_error}：
    llm_error 非 None 表示配置了 LLM 但调用失败（已回退内置引擎）。
    """
    rep = progress or (lambda stage, ratio: None)

    if material:
        rep(0.10, "正在分析 Word 文档内容…")
        knowledge = "以下是用 Word 文档导入的原始素材，大纲与内容必须基于这份材料展开：\n" + material
    else:
        rep(0.10, "正在分析主题并抓取相关资料…")
        knowledge = knowledge_context(topic)

    slides, llm_error = (
        _llm_generate(topic, slides_count, audience, knowledge, progress, profile_id)
        if use_llm else (None, None)
    )
    if slides:
        rep(0.9, "AI 内容生成完毕")
        return {"slides": slides, "source": "llm", "knowledge_used": bool(knowledge),
                "llm_error": None}

    if llm_error:
        rep(0.65, "AI 调用失败，使用内置引擎兜底…")
    else:
        rep(0.65, "使用内置内容引擎生成…")
    slides = _template_generate(topic, slides_count, audience, knowledge)
    rep(0.9, "内容生成完毕")
    return {"slides": slides, "source": "template", "knowledge_used": bool(knowledge),
            "llm_error": llm_error}
