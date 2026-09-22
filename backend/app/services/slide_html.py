"""HTML 幻灯片主题引擎 v2：结构化要点 + 多版式自动选择。

v2 核心（对标千问/Gamma 级观感）：
- 要点结构化「关键词 k + 描述 v」（k：v 格式字符串，渲染时拆分）
- 版式自动选择：数据强调（大数字）/ 2×2 卡片 / 左文右图 / 列表
- 右上角幽灵页码、章节感排版

由 Electron 离屏窗口截图出 PNG（Marp/Slidev 同思路）。
"""
import html
import re
from typing import Dict, List

W, H = 1920, 1080


def _hex_to_rgb(c: str):
    c = (c or "#1a3a5c").lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (26, 58, 92)


def _mix(c1, c2, t: float):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def _shade(c: str, t: float) -> str:
    """t>0 变暗，t<0 变亮。"""
    rgb = _hex_to_rgb(c)
    dst = (0, 0, 0) if t > 0 else (255, 255, 255)
    r, g, b = _mix(rgb, dst, abs(t))
    return f"#{r:02x}{g:02x}{b:02x}"


def _alpha(c: str, a: float) -> str:
    r, g, b = _hex_to_rgb(c)
    return f"rgba({r},{g},{b},{a})"


_FONT_STACK = (
    "'PingFang SC','Microsoft YaHei','Hiragino Sans GB','Noto Sans CJK SC',sans-serif"
)

# ---------- 要点结构化 ----------

_KV_RE = re.compile(r"([^，,。：:|]{2,8})[：:|]\s*(.+)", re.S)
_KV_SOFT_RE = re.compile(r"([^，,]{2,6})[，,]\s*(.+)", re.S)


def split_point(b) -> Dict:
    """要点字符串 → {k, v}；已是 dict 直接规范化。"""
    if isinstance(b, dict):
        return {"k": str(b.get("k", "")).strip(), "v": str(b.get("v", "")).strip()}
    s = str(b).strip()
    m = _KV_RE.match(s)
    if m:
        return {"k": m.group(1).strip(), "v": m.group(2).strip()}
    m = _KV_SOFT_RE.match(s)
    if m:
        return {"k": m.group(1).strip(), "v": m.group(2).strip()}
    return {"k": "", "v": s}


def _points(bullets) -> List[Dict]:
    pts = [split_point(b) for b in (bullets or [])]
    return [p for p in pts if p["v"]]


_NUM_RE = re.compile(r"\d+\.?\d*\s*(?:%|％|亿|万|千|倍|[xX×]|美元|元|人|家|城)")


def _pick_layout(pts: List[Dict], image: str | None) -> str:
    """版式自动选择：数据强调 / 左文右图 / 2×2 卡片 / 列表。"""
    if not pts:
        return "list"
    if image:
        return "split"
    n_num = sum(1 for p in pts if _NUM_RE.search(p["v"]) or _NUM_RE.search(p["k"]))
    if n_num >= 2 and len(pts) <= 4:
        return "stats"
    if len(pts) >= 4:
        return "grid"
    return "list"


# ---------- 每种风格的差异 CSS（primary 由变量注入） ----------

_STYLE_CSS = {
    "简约商务": """
        .slide.cover{background:linear-gradient(135deg,{p} 0%,{p_dark} 100%);}
        .slide.cover .deco1{position:absolute;right:-180px;top:-180px;width:560px;height:560px;
            border-radius:50%;background:{p_light12};}
        .slide.cover .deco2{position:absolute;right:120px;bottom:-220px;width:420px;height:420px;
            border-radius:50%;background:{p_light08};}
        .content{background:#F7F9FC;}
        .head-bar{width:96px;height:10px;border-radius:5px;background:{p};}
        .card{background:#fff;border-left:8px solid {p};}
        .num{background:{p};}
        .cover .rule{background:{p_light60};}
        .stat .n{color:{p};}
    """,
    "科技渐变": """
        .slide{background:radial-gradient(1200px 800px at 78% 18%,{p_light30},transparent 60%),
            linear-gradient(140deg,#0c1220 0%,{p_dark} 90%);}
        .slide:before{content:'';position:absolute;inset:0;
            background-image:linear-gradient({p_light10} 1px,transparent 1px),
                linear-gradient(90deg,{p_light10} 1px,transparent 1px);
            background-size:64px 64px;opacity:.35;}
        .card{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.14);
            border-radius:18px;}
        .num{background:linear-gradient(135deg,{p_light40},{p_light20});color:#fff;}
        .slide-title{color:#fff;}
        .content{color:#E8EDF5;}
        .foot{color:rgba(255,255,255,.45);}
        .cover .rule{background:{p_light60};}
        .badge{background:{p_light20};color:{p_light60};}
        .ghost{color:rgba(255,255,255,.055);}
        .pk{color:{p_light60};}
        .pc .pk,.stat .k{color:#fff;}
        .pc .pv,.stat .v{color:#A9B6C9;}
        .stat .n{color:{p_light60};}
    """,
    "清新留白": """
        .slide.cover{background:#fff;}
        .slide.cover .cover-title{color:{p_dark};}
        .slide.cover .deco1{position:absolute;left:0;right:0;top:0;height:14px;background:{p};}
        .slide.cover .deco2{position:absolute;left:0;right:0;bottom:0;height:14px;background:{p};opacity:.25;}
        .content{background:#fff;}
        .head-bar{width:64px;height:4px;background:{p};}
        .card{background:{p_light06};border:none;border-radius:14px;}
        .num{background:transparent;color:{p};font-weight:700;}
        .cover .rule{background:{p};}
        .stat .n{color:{p};}
        .card{box-shadow:none;}
    """,
    "图文并茂": """
        .slide.cover{background:linear-gradient(160deg,{p} 0%,{p_dark} 78%);}
        .slide.cover .deco1{position:absolute;left:-140px;bottom:-140px;width:460px;height:460px;
            border-radius:50%;border:52px solid {p_light12};}
        .content{background:#fff;}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:22px 26px;align-content:start;}
        .card{background:{p_light08};border:none;border-radius:16px;}
        .num{background:{p};}
        .head-band{position:absolute;top:0;left:0;right:0;height:14px;background:{p};}
        .cover .rule{background:{p_light60};}
        .stat .n{color:{p};}
    """,
    # Slidev 二开移植（MIT）：暗黑平板底 + 左侧强调竖条 + 底部进度条 + 极客等宽字体
    "Slidev 极客": """
        .slide{background:linear-gradient(115deg,#0e1117 0%,#131926 55%,{p_dark} 165%);}
        .slide:before{content:'';position:absolute;inset:0;
            background-image:radial-gradient(rgba(255,255,255,.045) 1.5px,transparent 1.5px);
            background-size:52px 52px;opacity:.5;}
        .slide.cover .deco1{left:0;top:0;bottom:0;right:auto;width:16px;height:auto;
            border-radius:0;background:linear-gradient(180deg,{p_light40},{p_light20});}
        .slide.cover .deco2{display:none;}
        .content .head-band{right:auto;width:16px;height:100%;
            background:linear-gradient(180deg,{p_light40},{p_light20});}
        .prog{display:block;position:absolute;bottom:0;left:0;height:9px;z-index:6;
            background:linear-gradient(90deg,{p_light40},{p_light60});
            box-shadow:0 0 18px {p_light40};}
        .card{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.10);
            border-radius:14px;box-shadow:none;}
        .num{background:linear-gradient(135deg,{p_light40},{p_light20});color:#0d1117;
            font-family:'SF Mono',Menlo,Consolas,monospace;}
        .slide-title{color:#fff;}
        .slide-title:before{content:'// ';color:{p_light60};
            font-family:'SF Mono',Menlo,Consolas,monospace;font-weight:600;}
        .content{color:#C6D2E2;}
        .cover .kicker{font-family:'SF Mono',Menlo,Consolas,monospace;letter-spacing:6px;
            color:{p_light60};}
        .cover .kicker:before{content:'> ';color:{p_light40};}
        .chip{font-family:'SF Mono',Menlo,Consolas,monospace;background:rgba(255,255,255,.07);}
        .foot{color:rgba(255,255,255,.38);font-family:'SF Mono',Menlo,Consolas,monospace;}
        .cover .rule{background:{p_light60};}
        .thanks{color:{p_light60};font-family:'SF Mono',Menlo,Consolas,monospace;}
        .img-wrap{border-color:rgba(255,255,255,.14);box-shadow:0 18px 48px rgba(0,0,0,.45);}
        .ghost{color:rgba(255,255,255,.06);
            font-family:'SF Mono',Menlo,Consolas,monospace;}
        .pk{color:{p_light60};}
        .pc .pk,.stat .k{color:#fff;}
        .pc .pv,.stat .v{color:#A9B6C9;}
        .stat .n{color:{p_light60};}
    """,
}

_DEFAULT_STYLE_CSS = _STYLE_CSS["简约商务"]


def _cover_slide(topic: str, bullets: List[Dict], image: str | None = None) -> str:
    chips = "".join(f'<span class="chip">{html.escape(p["v"] if not p["k"] else p["k"] + " · " + p["v"])}</span>'
                    for p in bullets[:3])
    img_html = ""
    if image:
        img_html = (f'<img class="cover-img" src="{image}" alt="">'
                    f'<div class="cover-shade"></div>')
    return f"""
    <div class="slide cover{' has-img' if image else ''}">
      {img_html}
      <div class="deco1"></div><div class="deco2"></div>
      <div class="cover-inner">
        <div class="kicker">PRESENTATION</div>
        <div class="cover-title">{html.escape(topic)}</div>
        <div class="rule"></div>
        <div class="chips">{chips}</div>
      </div>
    </div>"""


def _pt_card(j: int, p: Dict, k_size: str = "") -> str:
    kv = (f'<span class="pk">{html.escape(p["k"])}</span>' if p["k"] else "")
    return (f'<div class="card"><div class="num">{j + 1:02d}</div>'
            f'<div class="card-t">{kv}<span class="pv">{html.escape(p["v"])}</span></div></div>')


def _stat_html(p: Dict, num: str) -> str:
    return (f'<div class="card stat"><div class="n">{html.escape(num)}</div>'
            f'<div class="k">{html.escape(p["k"] or "关键数据")}</div>'
            f'<div class="v">{html.escape(p["v"])}</div></div>')


def _pc_html(p: Dict) -> str:
    return (f'<div class="card pc"><div class="pk">{html.escape(p["k"] or "要点")}</div>'
            f'<div class="pv">{html.escape(p["v"])}</div></div>')


def _ghost(idx: int) -> str:
    return f'<div class="ghost">{idx + 1:02d}</div>'


def _extract_num(v: str) -> str:
    m = _NUM_RE.search(v)
    if not m:
        m = re.search(r"\d+\.?\d*", v)
    return m.group(0).strip() if m else ""


def _content_slide(idx: int, total: int, topic: str, title: str, bullets,
                   last: bool, image: str | None = None) -> str:
    pts = _points(bullets)
    foot = (f'<div class="foot"><span>{html.escape(topic)}</span>'
            f'<span>{idx + 1} / {total}</span></div>'
            f'<div class="prog" style="width:{(idx + 1) / total * 100:.1f}%"></div>')

    if last:
        items = "".join(_pc_html(p) for p in pts[:3]) or ""
        return f"""
        <div class="slide closing">
          {_ghost(idx)}
          <div class="cover-inner">
            <div class="kicker">SUMMARY</div>
            <div class="cover-title">{html.escape(title)}</div>
            <div class="rule"></div>
            <div class="grid wide">{items}</div>
            <div class="thanks">感谢观看 · THANKS</div>
          </div>
        </div>"""

    head = (f'<div class="slide-title">{html.escape(title)}</div>'
            f'<div class="head-bar"></div>')
    layout = _pick_layout(pts, image)

    if layout == "split":
        rows = "".join(_pt_card(j, p) for j, p in enumerate(pts))
        body = f"""
      <div class="content-inner with-img">
        {head}
        <div class="txt-col"><div class="grid">{rows}</div></div>
        <div class="img-wrap"><img src="{image}" alt=""></div>
      </div>"""
    elif layout == "stats":
        stats = []
        for p in pts[:4]:
            num = _extract_num(p["v"]) or _extract_num(p["k"])
            if num:
                stats.append(_stat_html(p, num))  # 保留完整描述，数字仅作强调
            else:
                stats.append(_pc_html(p))
        four = " four" if len(stats) >= 4 else ""
        body = f"""
      <div class="content-inner">
        {head}
        <div class="stats{four}">{''.join(stats)}</div>
      </div>"""
    elif layout == "grid":
        cells = "".join(_pc_html(p) for p in pts[:4])
        body = f"""
      <div class="content-inner">
        {head}
        <div class="g2">{cells}</div>
      </div>"""
    else:  # list
        rows = "".join(_pt_card(j, p) for j, p in enumerate(pts))
        single = " single" if len(pts) <= 3 else ""
        body = f"""
      <div class="content-inner{single}">
        {head}
        <div class="grid">{rows}</div>
      </div>"""

    return f"""
    <div class="slide content">
      <div class="head-band"></div>
      {_ghost(idx)}
      {body}
      {foot}
    </div>"""


def build_slides_html(slides: List[Dict], theme: Dict | None) -> str:
    """slides JSON → 自包含 HTML（Electron 加载后逐页截图）。"""
    primary = (theme or {}).get("primary") or "#1a3a5c"
    style = (theme or {}).get("style") or "简约商务"
    css = _STYLE_CSS.get(style, _DEFAULT_STYLE_CSS)
    for key, val in {
        "{p}": primary,
        "{p_dark}": _shade(primary, 0.38),
        "{p_light06}": _alpha(primary, 0.06),
        "{p_light08}": _alpha(primary, 0.08),
        "{p_light10}": _alpha(primary, 0.10),
        "{p_light12}": _alpha(primary, 0.12),
        "{p_light20}": _alpha(primary, 0.20),
        "{p_light30}": _alpha(primary, 0.30),
        "{p_light40}": _alpha(primary, 0.40),
        "{p_light60}": _alpha(primary, 0.60),
    }.items():
        css = css.replace(key, val)

    total = len(slides)
    topic = slides[0].get("title", "") if slides else ""
    parts = []
    for i, s in enumerate(slides):
        title = s.get("title", "")
        bullets = [b for b in (s.get("bullets") or []) if str(b).strip()]
        img = s.get("image") if isinstance(s.get("image"), str) and s.get("image").startswith("data:image") else None
        if i == 0:
            parts.append(_cover_slide(title, [split_point(b) for b in bullets], img))
        else:
            parts.append(
                _content_slide(i, total, topic, title, bullets, last=(i == total - 1), image=img)
            )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:{W}px;height:{H}px;overflow:hidden;font-family:{_FONT_STACK};background:#000;}}
.slide{{position:absolute;inset:0;display:none;flex-direction:column;}}
.slide.active{{display:flex;}}
/* ---------- 封面 / 结尾 ---------- */
.cover,.closing{{justify-content:center;}}
.cover-inner{{padding:0 160px;position:relative;z-index:2;}}
.kicker{{font-size:22px;letter-spacing:10px;color:{_alpha(primary, 0.75)};font-weight:600;margin-bottom:34px;}}
.cover-title{{font-size:92px;font-weight:800;color:#fff;line-height:1.22;max-width:1400px;}}
.closing .cover-title{{font-size:72px;}}
.rule{{width:150px;height:12px;border-radius:6px;margin:46px 0;}}
.chips{{display:flex;gap:18px;flex-wrap:wrap;}}
.chip{{padding:12px 30px;border-radius:999px;background:{_alpha("#ffffff", 0.14)};
    border:1px solid {_alpha("#ffffff", 0.25)};color:#fff;font-size:26px;}}
.deco1,.deco2{{position:absolute;}}
/* ---------- 内容页通用 ---------- */
.content{{background:#F7F9FC;color:#2B3440;}}
.content-inner{{padding:96px 130px 120px;display:flex;flex-direction:column;position:relative;z-index:2;height:100%;}}
.content-inner.single{{justify-content:center;}}
.slide-title{{font-size:58px;font-weight:800;color:#1E2833;margin-bottom:26px;}}
.head-bar{{margin-bottom:44px;}}
.ghost{{position:absolute;top:40px;right:96px;font-size:180px;font-weight:800;line-height:1;
    color:{_alpha(primary, 0.09)};z-index:1;pointer-events:none;}}
.foot{{position:absolute;bottom:36px;left:130px;right:130px;display:flex;
    justify-content:space-between;font-size:22px;color:#9AA4B0;z-index:2;}}
.prog{{display:none;}}
/* ---------- 版式：列表 ---------- */
.grid{{display:grid;grid-template-columns:1fr;gap:24px;align-content:start;}}
.grid.wide{{grid-template-columns:1fr 1fr;margin-top:10px;width:100%;max-width:1500px;}}
.card{{display:flex;align-items:center;gap:26px;padding:28px 36px;border-radius:16px;
    box-shadow:0 4px 18px rgba(30,40,60,.06);}}
.card-t{{font-size:31px;line-height:1.55;}}
.num{{flex-shrink:0;width:58px;height:58px;border-radius:14px;color:#fff;display:flex;
    align-items:center;justify-content:center;font-size:26px;font-weight:700;}}
.pk{{font-weight:800;color:{primary};margin-right:14px;}}
.pv{{color:inherit;}}
/* ---------- 版式：2×2 卡片 ---------- */
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:26px;align-content:start;}}
.pc{{display:block;padding:38px 42px;}}
.pc .pk{{display:block;font-size:34px;font-weight:800;color:#1E2833;margin:0 0 14px;}}
.pc .pv{{display:block;font-size:26px;line-height:1.68;color:#5A6572;}}
/* ---------- 版式：数据强调 ---------- */
.stats{{display:flex;gap:30px;align-content:start;}}
.stat{{flex:1;display:block;padding:56px 44px;border-radius:20px;}}
.stat .n{{font-size:104px;font-weight:800;line-height:1.02;color:{primary};letter-spacing:-2px;}}
.stat .k{{font-size:31px;font-weight:800;margin-top:22px;color:#1E2833;}}
.stat .v{{font-size:24px;line-height:1.65;margin-top:12px;color:#6B7686;}}
.stats.four .stat{{padding:40px 34px;}}
.stats.four .n{{font-size:74px;}}
.stats.four .k{{font-size:27px;margin-top:16px;}}
.stats.four .v{{font-size:22px;}}
/* ---------- 版式：左文右图 ---------- */
.cover-img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;}}
.cover-shade{{position:absolute;inset:0;z-index:1;
    background:linear-gradient(95deg,rgba(8,14,24,.88) 0%,rgba(8,14,24,.62) 48%,rgba(8,14,24,.28) 100%);}}
.cover.has-img .deco1,.cover.has-img .deco2{{display:none;}}
.content-inner.with-img{{display:grid;grid-template-columns:1.05fr .95fr;gap:52px;
    align-content:start;}}
.content-inner.with-img .slide-title,.content-inner.with-img .head-bar{{grid-column:1 / -1;}}
.txt-col{{display:flex;flex-direction:column;gap:22px;}}
.txt-col .grid{{gap:18px;}}
.txt-col .card{{padding:22px 30px;}}
.txt-col .card-t{{font-size:27px;}}
.txt-col .pk{{font-size:29px;}}
.img-wrap{{border-radius:24px;overflow:hidden;box-shadow:0 18px 48px rgba(20,32,52,.18);
    min-height:560px;align-self:stretch;border:1px solid rgba(120,140,170,.18);}}
.img-wrap img{{width:100%;height:100%;object-fit:cover;display:block;}}
.thanks{{margin-top:70px;font-size:30px;letter-spacing:6px;color:{_alpha(primary, 0.7)};}}
/* ---------- 风格 ---------- */
{css}
</style></head><body>
{''.join(parts)}
<script>
const slides=[...document.querySelectorAll('.slide')];
window.__COUNT__=slides.length;
window.__READY__=true;
window.__goto=(i)=>{{slides.forEach((s,k)=>s.classList.toggle('active',k===i));}};
window.__goto(0);
</script>
</body></html>"""
