"""HTML 幻灯片主题引擎：生成自包含 HTML，由 Electron 离屏窗口截图出 PNG。

这是对标 Marp / Slidev / banana-slides 等 HTML 幻灯片开源项目的渲染思路，
比 Pillow 逐像素绘制的效果好一个量级（渐变/卡片/圆角/阴影/现代排版）。
"""
import html
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

# 每种风格的差异 CSS（primary 由变量注入）
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
    """,
}

_DEFAULT_STYLE_CSS = _STYLE_CSS["简约商务"]


def _cover_slide(topic: str, bullets: List[str]) -> str:
    chips = "".join(f'<span class="chip">{html.escape(b)}</span>' for b in bullets[:3])
    return f"""
    <div class="slide cover">
      <div class="deco1"></div><div class="deco2"></div>
      <div class="cover-inner">
        <div class="kicker">PRESENTATION</div>
        <div class="cover-title">{html.escape(topic)}</div>
        <div class="rule"></div>
        <div class="chips">{chips}</div>
      </div>
    </div>"""


def _content_slide(idx: int, total: int, topic: str, title: str, bullets: List[str], last: bool) -> str:
    if last:
        items = "".join(f'<div class="card"><div class="card-t">{html.escape(b)}</div></div>' for b in bullets[:3])
        return f"""
        <div class="slide closing">
          <div class="cover-inner">
            <div class="kicker">SUMMARY</div>
            <div class="cover-title">{html.escape(title)}</div>
            <div class="rule"></div>
            <div class="grid wide">{items}</div>
            <div class="thanks">感谢观看 · THANKS</div>
          </div>
        </div>"""
    rows = "".join(
        f'<div class="card"><div class="num">{j + 1:02d}</div><div class="card-t">{html.escape(b)}</div></div>'
        for j, b in enumerate(bullets)
    )
    single = " single" if len(bullets) <= 3 else ""
    return f"""
    <div class="slide content">
      <div class="head-band"></div>
      <div class="content-inner{single}">
        <div class="slide-title">{html.escape(title)}</div>
        <div class="head-bar"></div>
        <div class="grid">{rows}</div>
      </div>
      <div class="foot"><span>{html.escape(topic)}</span><span>{idx + 1} / {total}</span></div>
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
        if i == 0:
            parts.append(_cover_slide(title, bullets))
        else:
            parts.append(
                _content_slide(i, total, topic, title, bullets, last=(i == total - 1))
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
/* ---------- 内容页 ---------- */
.content{{background:#F7F9FC;color:#2B3440;}}
.content-inner{{padding:96px 130px 120px;display:flex;flex-direction:column;position:relative;z-index:2;height:100%;}}
.content-inner.single{{justify-content:center;}}
.slide-title{{font-size:58px;font-weight:800;color:#1E2833;margin-bottom:26px;}}
.head-bar{{margin-bottom:44px;}}
.grid{{display:grid;grid-template-columns:1fr;gap:24px;align-content:start;}}
.grid.wide{{grid-template-columns:1fr 1fr;margin-top:10px;width:100%;max-width:1500px;}}
.card{{display:flex;align-items:center;gap:26px;padding:28px 36px;border-radius:16px;
    box-shadow:0 4px 18px rgba(30,40,60,.06);}}
.card-t{{font-size:32px;line-height:1.5;}}
.num{{flex-shrink:0;width:58px;height:58px;border-radius:14px;color:#fff;display:flex;
    align-items:center;justify-content:center;font-size:26px;font-weight:700;}}
.thanks{{margin-top:70px;font-size:30px;letter-spacing:6px;color:{_alpha(primary, 0.7)};}}
.foot{{position:absolute;bottom:36px;left:130px;right:130px;display:flex;
    justify-content:space-between;font-size:22px;color:#9AA4B0;z-index:2;}}
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
