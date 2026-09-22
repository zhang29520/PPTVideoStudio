"""自动配图服务：Bing 图片搜索（免 API key）→ 下载 → 压缩 → data URI。

每页幻灯片根据「主题核心词 + 页标题」搜索配图，下载成功后转成
data:image/jpeg;base64 直接内嵌进 slide["image"]，随项目 JSON 持久化，
HTML 渲染引擎与 PPTX 构建器都能直接使用，无需额外文件管理。

任何失败都静默跳过（该页退回纯文字排版），绝不阻塞 PPT 生成。
"""
import base64
import hashlib
import io
import json
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


def _unescape_json(s: str) -> str:
    s = s.replace("\\/", "/").replace('\\"', '"')
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def _clean_title(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)  # <em> 高亮标签
    import html as _html
    return _html.unescape(s).strip()


def _search_360(query: str, limit: int = 24) -> list:
    """360 图片 JSON 接口（国内可达、稳定、免 key），返回 [(url, title)]。"""
    u = ("https://image.so.com/j?q=" + urllib.parse.quote(query)
         + "&src=srp&correct=&pn=30&sn=0")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return []
    out = []
    for item in d.get("list", []):
        url = item.get("img") or ""
        if not url.startswith("http"):
            continue
        w, h = item.get("width") or 0, item.get("height") or 0
        if w and h and (w < MIN_W or h < MIN_H):
            continue  # 尺寸预筛，省一次下载
        out.append((url, _clean_title(item.get("title") or "")))
        if len(out) >= limit:
            break
    return out


def _search_bing(query: str, limit: int = 24) -> list:
    """Bing 图片搜索备用图源，返回 [(url, title)]。"""
    try:
        page = _fetch(IMAGE_SEARCH_URL.format(q=urllib.parse.quote(query)))
    except Exception:
        return []
    results = []
    for blk in page.split('class="iusc"')[1:]:
        mu = re.search(r'murl&quot;:&quot;(.*?)&quot;', blk)
        if not mu:
            mu = re.search(r'"murl":"(.*?)"', blk)
            if not mu:
                continue
            url = mu.group(1)
            tm = re.search(r'"t":"(.*?)"', blk)
        else:
            url = mu.group(1)
            tm = re.search(r'&quot;t&quot;:&quot;(.*?)&quot;', blk)
        url = _unescape_json(url)
        if not url.startswith("http") or "." not in url:
            continue
        title = _unescape_json(tm.group(1)) if tm else ""
        results.append((url, title))
        if len(results) >= limit:
            break
    return results


def _search_images(query: str) -> list:
    """多引擎图源：360 优先，Bing 兜底；返回首个有结果的引擎候选。"""
    for fn in (_search_360, _search_bing):
        try:
            res = fn(query)
        except Exception:
            res = []
        if res:
            return res
    return []


# 进程内查询缓存 + 全局限速（搜索引擎对突发请求会降级返回无关缓存页）
_qcache: dict = {}
_last_ts = [0.0]


def _search_images_cached(query: str) -> list:
    import time
    if query in _qcache:
        return _qcache[query]
    gap = 0.6 - (time.time() - _last_ts[0])
    if gap > 0:
        time.sleep(gap)
    res = _search_images(query)
    _last_ts[0] = time.time()
    if not res:  # 空结果重试一次（限流抖动）
        time.sleep(1.2)
        res = _search_images(query)
        _last_ts[0] = time.time()
    _qcache[query] = res
    return res


# 图片搜索通用词：单独命中不算相关（"方法""路径"什么图都能匹配上）
_IMG_GENERIC = {
    "方法", "路径", "核心", "概念", "解读", "分析", "总结", "案例", "实践",
    "步骤", "趋势", "背景", "现状", "展望", "要点", "对策", "建议", "资源",
    "工具", "风险", "数据", "指标", "问题", "主要", "关键", "常见", "类型",
}


def _query_keywords(query: str) -> tuple:
    """查询词 → (强关键词, 弱关键词)。

    强词：完整中文段（智能体/开发实战）与英文词（ai/agent）——命中 1 个即相关；
    弱词：中文 2-gram（剔除通用词）——需命中 ≥2 个才算相关。
    """
    strong, weak = [], []
    for run in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", query):
        run = run.lower()
        if len(run) >= 2 and run not in strong:
            strong.append(run)
        if re.match(r"[\u4e00-\u9fff]+$", run):
            for i in range(len(run) - 1):
                g = run[i:i + 2]
                if g not in _IMG_GENERIC and g not in weak:
                    weak.append(g)
    return strong, weak


def _title_relevant(title: str, strong: list, weak: list, relaxed: bool = False) -> bool:
    t = title.lower()
    if not t:
        return True  # 无标题信息的候选不过滤（由尺寸/比例兜底）
    if any(k in t for k in strong):
        return True
    return sum(1 for k in weak if k in t) >= (1 if relaxed else 2)


# ---------- 本地艺术图生成（配图失败时的兜底，保证页面永不裸奔） ----------

def _art_uri(seed_text: str, primary: str = "#1a3a5c", variant: int = -1) -> str:
    """按主题色生成抽象装饰图（渐变 + 几何图形），data URI 返回。

    千问/Gamma 页面好看很大程度靠这类抽象图形；搜索失败时用它兜底，
    网络零依赖。variant 指定风格（-1 = 按 seed 自动轮换）。
    """
    import hashlib as _hl
    import random

    rng = random.Random(_hl.md5(seed_text.encode("utf-8")).hexdigest())
    if variant < 0:
        variant = rng.randrange(4)

    W, H = 1280, 900
    # 主色 → 渐变端色（同色系深浅）
    h = primary.lstrip("#")
    if len(h) == 3:
        h = "".join(x * 2 for x in h)
    try:
        pr, pg, pb = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        pr, pg, pb = 26, 58, 92
    dark = (max(0, round(pr * 0.28)), max(0, round(pg * 0.30)), max(0, round(pb * 0.34)))
    lite = (min(255, round(pr + (255 - pr) * 0.55)),
            min(255, round(pg + (255 - pg) * 0.55)),
            min(255, round(pb + (255 - pb) * 0.55)))

    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img, "RGBA")
    # 纵向/对角渐变
    for y in range(H):
        t = y / H
        c0 = (round(pr + (dark[0] - pr) * t), round(pg + (dark[1] - pg) * t),
              round(pb + (dark[2] - pb) * t))
        d.line([(0, y), (W, y)], fill=c0)

    accent = (255, 255, 255)
    warm = (255, 190, 120)

    if variant == 0:  # 光环 + 散点
        cx, cy = rng.randint(700, 1000), rng.randint(180, 380)
        for r, a in ((340, 36), (250, 52), (160, 78)):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*accent, a), width=26)
        for _ in range(46):
            x, y = rng.randint(40, W - 40), rng.randint(40, H - 40)
            rr = rng.randint(3, 10)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(*accent, rng.randint(28, 90)))
    elif variant == 1:  # 层叠圆弧（声波感）
        for i in range(7):
            r = 160 + i * 105
            a = 90 - i * 11
            d.arc([200 - r, 450 - r, 200 + r, 450 + r], -62, 62,
                  fill=(*lite, max(a, 16)), width=30)
        d.ellipse([1080 - 60, 200 - 60, 1080 + 60, 200 + 60], fill=(*warm, 200))
    elif variant == 2:  # 数据条 + 网格
        for gx in range(0, W, 80):
            d.line([(gx, 0), (gx, H)], fill=(*accent, 14), width=2)
        for gy in range(0, H, 80):
            d.line([(0, gy), (W, gy)], fill=(*accent, 14), width=2)
        base = rng.randint(380, 520)
        for i in range(7):
            bh = rng.randint(70, 330)
            x0 = 140 + i * 150
            c = (*lite, 150) if i % 2 else (*accent, 110)
            d.rounded_rectangle([x0, base + 260 - bh, x0 + 92, base + 260],
                                radius=14, fill=c)
    else:  # 山峦层叠
        for i, (yy, a) in enumerate(((620, 60), (520, 84), (420, 110))):
            pts = [(0, H)]
            step = 160
            for x in range(0, W + step, step):
                pts.append((x, yy + rng.randint(-90, 90)))
            pts.append((W, H))
            d.polygon(pts, fill=(*(lite if i == 2 else accent), a))
        d.ellipse([W - 330, 90, W - 130, 290], fill=(*warm, 210))

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=84)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


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


def attach_images(topic: str, slides: list, progress=None, per_page_timeout: float = 14.0,
                  primary: str = "#1a3a5c") -> int:
    """为主题幻灯片逐页配图，写入 slide["image"]=data URI。返回成功页数。

    - 封面用主题核心词搜大图（做全幅背景）
    - 内容页用「核心词+页标题」搜索
    - 跨页去重（同一张图不会重复使用）
    - 搜索失败的页用本地生成的主题色抽象艺术图兜底，页面永不裸奔
    """
    rep = progress or (lambda stage, ratio: None)
    if not slides:
        return 0

    used_hashes: set = set()
    pool: list = []  # 本次运行抓到的全部候选 (url, title)，供最后兜底复用
    topic_strong, topic_weak = _query_keywords(topic)
    ok = 0
    total = len(slides)

    for i, s in enumerate(slides):
        if not isinstance(s, dict):
            continue
        rep(0.88 + 0.05 * i / max(1, total), f"正在为第 {i + 1}/{total} 页配图…")
        queries = _slide_query(topic, s.get("title", ""))
        got = None
        for q in queries[:3]:  # 每页最多 3 个搜索词
            res = _search_images_cached(q)
            pool.extend((u, t) for u, t in res)
            strong, weak = _query_keywords(q)
            # 两轮过滤：先严格（弱词需 2 命中），不够再放宽（弱词 1 命中）
            for relaxed in (False, True):
                for u, t in res:
                    if not _title_relevant(t, strong, weak, relaxed=relaxed):
                        continue
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
                break
        if got:
            s["image"] = got
            ok += 1

    # 终轮兜底：没配到图的页从本主题候选池里挑未使用的相关图（不发新搜索请求）
    for i, s in enumerate(slides):
        if not isinstance(s, dict) or s.get("image"):
            continue
        for u, t in pool:
            if not _title_relevant(t, topic_strong, topic_weak, relaxed=True):
                continue
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
            s["image"] = uri
            ok += 1
            break

    # 最终兜底：本地生成主题色抽象艺术图（零网络依赖，封面必配）
    for i, s in enumerate(slides):
        if not isinstance(s, dict) or s.get("image"):
            continue
        seed = f"{topic}|{s.get('title', '')}|{i}"
        s["image"] = _art_uri(seed, primary)
        ok += 1
    return ok
