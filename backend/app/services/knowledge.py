"""主题知识抓取：DuckDuckGo HTML 搜索（免 API key），失败静默降级。

流程：主题 → 搜索关键词 → 抓取摘要片段（去重、清洗）→ 作为 LLM 生成
大纲/内容/解说词的事实上下文，避免"关键要点一"式的空话。
"""
import html
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SEARCH_URLS = [
    # 必应中国：大陆可直连，结果在 <li class="b_algo">
    "https://cn.bing.com/search?q={q}",
    # DuckDuckGo 轻量版：海外网络环境可用
    "https://html.duckduckgo.com/html/?q={q}",
    "https://lite.duckduckgo.com/lite/?q={q}",
]


def _fetch(url: str, timeout: int = 8) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def search_snippets(topic: str, max_items: int = 6, timeout: int = 8) -> list:
    """返回 [{title, snippet}]；任何失败返回 []。"""
    q = urllib.parse.quote(topic)
    for tpl in SEARCH_URLS:
        try:
            page = _fetch(tpl.format(q=q), timeout=timeout)
        except Exception:
            continue
        items = []

        # cn.bing.com: <li class="b_algo"> 内 <h2><a>标题</a></h2> + <p>摘要</p>
        for m in re.finditer(
            r'<li class="b_algo".*?<h2[^>]*>\s*<a[^>]*>(.*?)</a>.*?<p[^>]*>(.*?)</p>',
            page, re.S,
        ):
            title = _strip_tags(m.group(1))
            snippet = _strip_tags(m.group(2))
            if title and snippet and len(snippet) > 20:
                items.append({"title": title, "snippet": snippet[:220]})
            if len(items) >= max_items:
                break

        # html.duckduckgo.com: 结果在 class="result__snippet" 的块里，标题在 result__a
        for m in re.finditer(
            r'<a[^>]+class="result__a"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
            page, re.S,
        ):
            title = _strip_tags(m.group(1))
            snippet = _strip_tags(m.group(2))
            if title and snippet and len(snippet) > 20:
                items.append({"title": title, "snippet": snippet[:220]})
            if len(items) >= max_items:
                break

        # lite.duckduckgo.com: 表格结构，逐行 <tr> 里含链接文本与摘要
        if not items:
            rows = re.findall(r"<tr>(.*?)</tr>", page, re.S)
            for row in rows:
                tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
                if len(tds) >= 2:
                    title = _strip_tags(tds[0])
                    snippet = _strip_tags(tds[-1])
                    if title and snippet and len(snippet) > 20 and "duckduckgo" not in snippet.lower():
                        items.append({"title": title, "snippet": snippet[:220]})
                if len(items) >= max_items:
                    break

        if items:
            return items
    return []


def knowledge_context(topic: str, max_items: int = 6) -> str:
    """把搜索结果拼成一段可供 prompt 使用的资料文本；无结果返回空串。"""
    items = search_snippets(topic, max_items=max_items)
    if not items:
        return ""
    lines = []
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. 【{it['title']}】{it['snippet']}")
    return "\n".join(lines)
