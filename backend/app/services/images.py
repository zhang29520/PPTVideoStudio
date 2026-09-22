"""自动配图服务：Bing 图片搜索（免 API key）→ 下载 → 压缩 → data URI。

每页幻灯片根据「主题核心词 + 页标题」搜索配图，下载成功后转成
data:image/jpeg;base64 直接内嵌进 slide["image"]，随项目 JSON 持久化，
HTML 渲染引擎与 PPTX 构建器都能直接使用，无需额外文件管理。

任何失败都静默跳过（该页退回纯文字排版），绝不阻塞 PPT 生成。
"""
import base64
import hashlib
import io
import re
import urllib.parse
import urllib.request

from PIL import Image

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")

IMAGE_SEARCH_URL = "https://cn.bing.com/images/search?q={q}&first=1&count=30"

# 抓取图片的尺寸/体积限制
MIN_W, MIN_H = 480, 270
MAX_W = 1280          # 压缩到最大宽 1280，JPEG q82 单张 ~150KB
MAX_BYTES = 6 * 1024 * 1024
JPEG_QUALITY = 82

# 通用后缀，搜索配图时去掉（"分析报告"搜不出图）
_TOPIC_SUFFIX = re.compile(r"(分析报告|可行性分析|需求分析|汇报材料|汇报|分析|报告|解读|介绍|方案|PPT|ppt)$")


def _fetch(url: str, timeout: int = 6) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _download(url: str, timeout: int = 8) -> bytes | None:
    """下载图片字节；过大/非图片/失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": url})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(MAX_BYTES + 1)
        if not data or len(data) > MAX_BYTES:
            return None
        return data
    except Exception:
        return None


def _compress(data: bytes) -> str | None:
    """校验 + 压缩为 JPEG，返回 data URI；不合规返回 None。"""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    w, h = img.size
    if w < MIN_W or h < MIN_H:
        return None
    if not (0.45 <= w / h <= 2.6):  # 过窄/过扁的横幅广告图直接丢弃
        return None
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    if w > MAX_W:
        img = img.resize((MAX_W, round(h * MAX_W / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _search_urls(query: str, limit: int = 12) -> list:
    """Bing 图片搜索，返回候选原图 URL 列表（按相关性排序）。"""
    try:
        page = _fetch(IMAGE_SEARCH_URL.format(q=urllib.parse.quote(query)))
    except Exception:
        return []
    urls = []
    # m="{&quot;murl&quot;:&quot;https://...&quot;,...} 原图地址
    for m in re.finditer(r'murl&quot;:&quot;(.*?)&quot;', page):
        u = m.group(1).replace("\\u002f", "/")
        if u.startswith("http") and "." in u:
            urls.append(u)
    # 部分 CDN 返回未转义版本
    if not urls:
        for m in re.finditer(r'"murl":"(.*?)"', page):
            u = m.group(1).replace("\\/", "/")
            if u.startswith("http"):
                urls.append(u)
    # 去重
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out


def _slide_query(topic: str, title: str) -> list:
    """构造搜索词阶梯：核心词+页标题 → 核心词 → 主题。"""
    core = _TOPIC_SUFFIX.sub("", topic).strip() or topic
    qs = []
    t = re.sub(r"^\d+[\.、]\s*", "", title or "").strip()
    # 过于通用的页标题（总结与展望/背景与现状）不参与组词，避免搜出无关图
    generic = {"总结与展望", "总结", "展望", "感谢观看", "背景与现状", "目录"}
    if t and t not in generic and t != core:
        qs.append(f"{core} {t}")
    qs.append(core)
    if topic != core:
        qs.append(topic)
    return qs


def attach_images(topic: str, slides: list, progress=None, per_page_timeout: float = 14.0) -> int:
    """为主题幻灯片逐页配图，写入 slide["image"]=data URI。返回成功页数。

    - 封面用主题核心词搜大图（做全幅背景）
    - 内容页用「核心词+页标题」搜索
    - 跨页去重（同一张图不会重复使用）
    """
    rep = progress or (lambda stage, ratio: None)
    if not slides:
        return 0

    used_hashes: set = set()
    ok = 0
    total = len(slides)

    for i, s in enumerate(slides):
        if not isinstance(s, dict):
            continue
        rep(0.88 + 0.05 * i / max(1, total), f"正在为第 {i + 1}/{total} 页配图…")
        queries = _slide_query(topic, s.get("title", ""))
        got = None
        deadline_queries = queries[:2]  # 每页最多 2 个搜索词
        for q in deadline_queries:
            urls = _search_urls(q)
            for u in urls:
                data = _download(u)
                if not data:
                    continue
                digest = hashlib.md5(data).hexdigest()
                if digest in used_hashes:
                    continue
                uri = _compress(data)
                if not uri:
                    continue
                used_hashes.add(digest)
                got = uri
                break
            if got:
                break
        if got:
            s["image"] = got
            ok += 1
    return ok
