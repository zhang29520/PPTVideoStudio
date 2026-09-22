"""主题知识抓取：Bing/DuckDuckGo 搜索（免 API key），失败静默降级。

流程：主题 → 搜索 → 摘要片段 → 相关性过滤（主题词命中）→ 垃圾行黑名单
→ 清洗（来源包装/日期/相对时间）→ 作为 LLM/模板的事实上下文。
"""
import html
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SEARCH_URLS = [
    "https://cn.bing.com/search?q={q}",
    "https://html.duckduckgo.com/html/?q={q}",
    "https://lite.duckduckgo.com/lite/?q={q}",
]

# 垃圾行黑名单：导航/登录页/页脚文字，出现在摘要里即丢弃
JUNK_WORDS = (
    "用户协议", "隐私政策", "登录政策", "立即注册", "忘记密码", "扫码登录",
    "版权所有", "ICP备", "ICP证", "免责声明", "收藏本站", "设为首页",
    "下载客户端", "扫码下载", "关注我们", "联系我们", "官方客服",
    "意见反馈", "网站导航", "网站地图", "无障碍", "退出登录",
)

# 常见通用词：即使命中也不算主题相关
GENERIC_GRAMS = {
    "分析", "报告", "介绍", "说明", "情况", "现状", "汇报", "关于", "如何",
    "什么", "应用", "方案", "案例", "背景", "意义", "影响", "总结", "解读",
    "大全", "汇总", "指南", "攻略", "一个", "这个", "一种", "以及", "可以",
    "平台", "系统", "管理", "服务", "内容", "信息", "相关", "进行",
}


def _fetch(url: str, timeout: int = 8) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _keywords(topic: str) -> list:
    """从主题提取关键词：CJK 连续段整体 + 其所有 2-gram；过滤通用词。"""
    kws = set()
    for run in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", topic):
        if len(run) >= 2:
            kws.add(run.lower())
            for i in range(len(run) - 1):
                g = run[i:i + 2].lower()
                if g not in GENERIC_GRAMS:
                    kws.add(g)
    # 去掉被更长关键词包含的短词没有意义（命中即算），保留全部即可
    return sorted(kws)


def _relevant(text: str, kws: list, min_hits: int = 2) -> bool:
    """text 至少命中 min_hits 个不同关键词（单字/通用词不算）。"""
    t = text.lower()
    hits = sum(1 for k in kws if k in t)
    return hits >= min_hits


def _clean_text(s: str) -> str:
    """清洗摘要：来源包装 / 绝对日期 / 相对时间 / 垃圾符号 / 截断尾巴。"""
    s = re.sub(r"^【([^】]{0,40})】\s*", "", s)
    s = re.sub(r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?\s*[·•]?\s*", "", s)
    s = re.sub(r"\d+\s*(天|小时|分钟|周|个月|月|年)前\s*[·•]?\s*", "", s)
    s = re.sub(r"^\d{1,2}[、.．]\s*", "", s)          # 列表序号 "01 " "3、"
    s = re.sub(r"^[\s\u201c\u201d\u300c\u300e·•\-–—]+", "", s)  # 开头引号/装饰符
    s = s.strip()
    # 去掉截断省略号，并在最后一个完整句末断句，避免"升级 …"这类半句
    s = re.sub(r"[\s.…]*…\s*$", "", s)
    s = re.sub(r"\s+$", "", s)
    if s and s[-1] not in "。！？；":
        for p in ("。", "！", "？", "；"):
            i = s.rfind(p)
            if i > 20:
                s = s[:i + 1]
                break
        else:
            i = s.rfind("，")
            if i > 20:
                s = s[:i + 1]
    return s


def _clip_sentence(s: str, limit: int) -> str:
    """在 limit 内于最近的句末标点处截断（找不到就原样保留）。"""
    if len(s) <= limit:
        return s
    cut = s[:limit]
    for p in ("。", "；", "！", "？"):
        i = cut.rfind(p)
        if i > limit * 0.5:
            return cut[:i + 1]
    i = cut.rfind("，")
    if i > limit * 0.5:
        return cut[:i] + "等。"
    return cut


def _is_junk(s: str) -> bool:
    return any(w in s for w in JUNK_WORDS)


def search_snippets(topic: str, max_items: int = 8, timeout: int = 5) -> list:
    """返回 [{title, snippet}]；任何失败返回 []。带相关性过滤与换词重试。

    搜索引擎常把长主题拆散导致跑题结果（如"智慧文旅夜游分析报告"被按
    "智慧"匹配到教育平台）。策略：先搜原主题；过滤后不足时去掉
    "分析/报告"类后缀再搜核心词，再不足最后试"核心词 现状 发展"。
    """
    # 相关性始终以用户输入的主题为准
    kws = _keywords(topic)

    # 主题去掉通用后缀得到核心词，如 "智慧文旅夜游分析报告" → "智慧文旅夜游"
    core = re.sub(r"(分析报告|可行性分析|需求分析|分析|报告|汇报|解读|介绍|方案|PPT|ppt|pptx)$", "", topic).strip()

    # 渐进式查询阶梯：主题 → 核心词 → 逐段放宽（左边每次去 2 字）
    # "智慧文旅夜游" 这类冷门组合会被搜索引擎拆词跑题，放宽后才能命中真实资料
    queries = [topic]
    if core and core != topic:
        queries.append(core)
        cur = core
        while len(cur) > 3:
            cur = cur[2:]
            queries.append(cur)
            if len(queries) >= 6:
                break
        if queries[-1] != core:
            queries.append(f"{queries[-1]} 现状 发展")

    seen: set = set()
    for q in queries:
        for tpl in SEARCH_URLS:
            try:
                page = _fetch(tpl.format(q=urllib.parse.quote(q)), timeout=timeout)
            except Exception:
                continue
            items = []

            def add(title, snippet):
                if len(items) >= max_items:
                    return
                snippet = _clean_text(snippet)
                if not title or len(snippet) < 20 or _is_junk(title + snippet):
                    return
                # 记者引语/访谈片段：成对引号的内容不能当事实
                if snippet.count("\u201c") >= 2 or snippet.count('"') >= 2:
                    return
                if any(w in title + snippet for w in ("记者", "写道", "撰文")):
                    return
                if not _relevant(title + snippet, kws):
                    return
                key = snippet[:40]
                if key in seen:
                    return
                seen.add(key)
                items.append({"title": title, "snippet": _clip_sentence(snippet, 150)})

            # cn.bing.com
            for m in re.finditer(
                r'<li class="b_algo".*?<h2[^>]*>\s*<a[^>]*>(.*?)</a>.*?<p[^>]*>(.*?)</p>',
                page, re.S,
            ):
                add(_strip_tags(m.group(1)), _strip_tags(m.group(2)))
            # html.duckduckgo.com
            if not items:
                for m in re.finditer(
                    r'<a[^>]+class="result__a"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
                    page, re.S,
                ):
                    add(_strip_tags(m.group(1)), _strip_tags(m.group(2)))
            # lite.duckduckgo.com
            if not items:
                for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
                    tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
                    if len(tds) >= 2:
                        t, sn = _strip_tags(tds[0]), _strip_tags(tds[-1])
                        if "duckduckgo" not in sn.lower():
                            add(t, sn)

            if items:
                return items
    return []


def knowledge_context(topic: str, max_items: int = 8) -> str:
    """把搜索结果拼成一段可供 prompt 使用的资料文本；无结果返回空串。"""
    items = search_snippets(topic, max_items=max_items)
    if not items:
        return ""
    lines = []
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. 【{it['title']}】{it['snippet']}")
    return "\n".join(lines)
