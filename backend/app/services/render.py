"""幻灯片页面渲染。

优先走 HTML 主题引擎（Electron 离屏截图，Marp/Slidev 同思路）；
Electron 不在线或超时 → 回退 Pillow 直接绘制（同样应用主题色）。
导入型 PPT 在 Windows 端可替换为 PowerPoint COM / LibreOffice 渲染钩子。
"""
import io
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

from ..subproc import run_quiet
from . import render_queue
from .slide_html import build_slides_html, split_point, _pick_layout, _extract_num

W, H = 1920, 1080

_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    # Linux
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _theme_colors(theme: Dict | None):
    """(primary, primary_dark, light_bg, text) 四元组。"""
    hexc = (theme or {}).get("primary") or "#1a3a5c"
    hexc = hexc.lstrip("#")
    if len(hexc) == 3:
        hexc = "".join(x * 2 for x in hexc)
    try:
        r, g, b = (int(hexc[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        r, g, b = 26, 58, 92
    primary = (r, g, b)
    dark = tuple(round(c * 0.62) for c in primary)
    light = tuple(min(255, round(c + (255 - c) * 0.55)) for c in primary)
    return primary, dark, (247, 249, 252), (51, 51, 51)


def _slide_image(s: Dict):
    """slide["image"] data URI → PIL Image（失败返回 None）。"""
    uri = s.get("image") if isinstance(s.get("image"), str) else ""
    if not uri.startswith("data:image") or "," not in uri:
        return None
    try:
        import base64
        return Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))).convert("RGB")
    except Exception:
        return None


def _paste_cover_bg(img: Image.Image, pic: Image.Image, primary):
    """封面全幅背景图：cover 裁切铺满 + 主色调深色蒙版保证文字可读。"""
    scale = max(W / pic.width, H / pic.height)
    pw, ph = round(pic.width * scale) + 1, round(pic.height * scale) + 1
    pic = pic.resize((pw, ph), Image.LANCZOS)
    left, top = (pw - W) // 2, (ph - H) // 2
    pic = pic.crop((left, top, left + W, top + H))
    overlay = Image.new("RGB", (W, H), primary)
    img.paste(Image.blend(pic, overlay, 0.72), (0, 0))


def _paste_content_img(d: ImageDraw.ImageDraw, img: Image.Image, pic: Image.Image, primary):
    """内容页右半幅配图（圆角矩形）。"""
    x0, y0, x1, y1 = int(W * 0.60), 250, W - 130, H - 170
    rw, rh = x1 - x0, y1 - y0
    scale = max(rw / pic.width, rh / pic.height)
    pw, ph = round(pic.width * scale) + 1, round(pic.height * scale) + 1
    pic = pic.resize((pw, ph), Image.LANCZOS)
    left, top = (pw - rw) // 2, (ph - rh) // 2
    pic = pic.crop((left, top, left + rw, top + rh))
    mask = Image.new("L", (rw, rh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, rw - 1, rh - 1], radius=22, fill=255)
    img.paste(pic, (x0, y0), mask)
    d.rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=22,
                        outline=light_bg_of(primary), width=2)


def _draw_cover(img: Image.Image, d: ImageDraw.ImageDraw, title: str, bullets: List[str],
                primary, dark, pic: Image.Image | None = None, slidev: bool = False):
    if pic is not None:
        _paste_cover_bg(img, pic, primary)
    elif slidev:
        # Slidev：暗黑平板底 + 左侧强调竖条
        d.rectangle([0, 0, W, H], fill=(14, 17, 23))
        d.rectangle([0, 0, 16, H], fill=light_bg_of(primary))
        d.ellipse([W - 480, H - 420, W + 240, H + 300], fill=(22, 28, 40))
    else:
        d.rectangle([0, 0, W, H], fill=primary)
        # 装饰圆
        d.ellipse([W - 420, -220, W + 260, 460], fill=dark)
        d.ellipse([W - 620, H - 320, W - 180, H + 120], fill=dark)
    f_title = _font(92)
    size = 92
    while size > 40 and f_title.getlength(("> " if slidev else "") + title) > W - 420:
        size -= 4
        f_title = _font(size)
    if not slidev:
        d.rectangle([160, 470, 320, 486], fill=(255, 255, 255))
    d.text((160, 540), ("> " if slidev else "") + title, font=f_title, fill=(255, 255, 255))
    if bullets:
        f_sub = _font(34)
        d.text((160, 760), " / ".join(bullets[:3]), font=f_sub, fill=light_bg_of(primary))


def light_bg_of(primary):
    return tuple(min(255, round(c + (255 - c) * 0.55)) for c in primary)


def _wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int = 2) -> List[str]:
    line, lines = "", []
    for ch in text:
        if font.getlength(line + ch) > max_w:
            lines.append(line)
            line = ch
            if len(lines) >= max_lines:
                return lines
        else:
            line += ch
    if line:
        lines.append(line)
    return lines


def _draw_content(img: Image.Image, d: ImageDraw.ImageDraw, index: int, total: int, topic: str,
                  title: str, bullets: List, primary, text,
                  pic: Image.Image | None = None, slidev: bool = False, lead: str = ""):
    if slidev:
        bg, card_fill, card_edge, foot_c = (14, 17, 23), (28, 35, 50), (52, 62, 80), (120, 132, 150)
        d.rectangle([0, 0, W, H], fill=bg)
        d.rectangle([0, 0, 16, H], fill=light_bg_of(primary))
        title_c = light_bg_of(primary)
        pw = int(W * (index + 1) / total)
        d.rectangle([0, H - 9, pw, H], fill=light_bg_of(primary))
    else:
        bg, card_fill, card_edge, foot_c = (247, 249, 252), (255, 255, 255), (228, 233, 240), (150, 150, 150)
        d.rectangle([0, 0, W, H], fill=bg)
        d.rectangle([0, 0, W, 12], fill=primary)
        title_c = primary
    accent = light_bg_of(primary)

    pts = [split_point(b) for b in bullets]
    pts = [p for p in pts if p["v"]]
    layout = _pick_layout(pts, "img" if pic is not None else None)

    f_title = _font(60)
    f_page = _font(24)
    f_num = _font(26)
    d.text((130, 90), title, font=f_title, fill=title_c)
    y0 = 280
    if lead:
        f_lead = _font(27)
        d.text((130, 190), lead[:56], font=f_lead, fill=(110, 122, 138))
        d.rectangle([130, 262, 250, 272], fill=accent)
        y0 = 350
    else:
        d.rectangle([130, 186, 250, 198], fill=accent)
    if pic is not None:
        _paste_content_img(d, img, pic, primary)

    if layout in ("list", "split"):
        max_card_w = W - 460 if pic is None else int(W * 0.56)
        f_body = _font(30)
        f_k = _font(33)
        y = y0
        for j, p in enumerate(pts):
            d.rounded_rectangle([110, y - 14, max_card_w + 40, y + 88], radius=16,
                                fill=card_fill, outline=card_edge, width=2)
            d.rounded_rectangle([138, y + 8, 202, y + 66], radius=12, fill=accent)
            num_txt = f"{j + 1:02d}"
            d.text((170 - f_num.getlength(num_txt) / 2, y + 22), num_txt, font=f_num,
                   fill=(13, 17, 23) if slidev else (255, 255, 255))
            tx = 236
            if p["k"]:
                d.text((tx, y + 12), p["k"], font=f_k, fill=accent)
                tx += f_k.getlength(p["k"]) + 18
            for li, ln in enumerate(_wrap(d, p["v"], f_body, max_card_w - tx + 40, 2)):
                d.text((tx if li == 0 else 236, y + 16 + li * 40), ln, font=f_body, fill=text)
            y += 122
            if y > H - 200:
                break
    elif layout == "stats":
        items = pts[:4]
        n = len(items)
        gap = 30
        bw = (W - 240 - gap * (n - 1)) // n
        f_big = _font(92 if n <= 3 else 70)
        f_k = _font(32)
        f_v = _font(25)
        top = y0
        bh = min(460, H - 180 - top)
        for j, p in enumerate(items):
            x0 = 120 + j * (bw + gap)
            d.rounded_rectangle([x0, top, x0 + bw, top + bh], radius=22,
                                fill=card_fill, outline=card_edge, width=2)
            num = _extract_num(p["v"]) or _extract_num(p["k"]) or "—"
            d.text((x0 + 40, top + 50), num, font=f_big, fill=accent)
            d.text((x0 + 40, top + 190), (p["k"] or "关键数据")[:10], font=f_k, fill=text)
            for li, ln in enumerate(_wrap(d, p["v"], f_v, bw - 80, 3)):
                d.text((x0 + 40, top + 245 + li * 36), ln, font=f_v, fill=(110, 122, 138))
    else:  # grid 2×2
        f_k = _font(40)
        f_v = _font(28)
        bw = (W - 240 - 40) // 2
        bh = min(280, (H - 180 - y0 - 36) // 2)
        for j, p in enumerate(pts[:4]):
            x0 = 120 + (j % 2) * (bw + 40)
            cy = y0 + (j // 2) * (bh + 36)
            d.rounded_rectangle([x0, cy, x0 + bw, cy + bh], radius=20,
                                fill=card_fill, outline=card_edge, width=2)
            d.text((x0 + 40, cy + 36), (p["k"] or "要点")[:12], font=f_k, fill=accent)
            for li, ln in enumerate(_wrap(d, p["v"], f_v, bw - 80, 3)):
                d.text((x0 + 40, cy + 104 + li * 42), ln, font=f_v, fill=text)

    d.text((130, H - 64), topic[:24], font=f_page, fill=foot_c)
    d.text((W - 180, H - 64), f"{index + 1} / {total}", font=f_page, fill=foot_c)


def _NUM_strip(v: str) -> str:
    import re as _re
    from .slide_html import _NUM_RE
    return _NUM_RE.sub("", v, count=1).strip("，,。 ；：:：-—") or v


def _render_pillow(slides: List[Dict], out_dir: Path, theme: Dict | None) -> List[Path]:
    primary, dark, _, text = _theme_colors(theme)
    slidev = (theme or {}).get("style") == "Slidev 极客"
    if slidev:
        # Slidev 暗黑配色
        text = (198, 210, 226)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    total = len(slides)
    topic = slides[0].get("title", "") if slides else ""
    for i, s in enumerate(slides):
        img = Image.new("RGB", (W, H), (255, 255, 255))
        d = ImageDraw.Draw(img)
        pic = _slide_image(s)
        if i == 0:
            _draw_cover(img, d, s.get("title", ""), s.get("bullets", []) or [], primary, dark, pic,
                        slidev=slidev)
        else:
            _draw_content(img, d, i, total, topic, s.get("title", ""),
                          s.get("bullets", []) or [], primary, text, pic, slidev=slidev,
                          lead=str(s.get("lead", "")).strip())
        p = out_dir / f"page_{i:03d}.png"
        img.save(p)
        paths.append(p)
    return paths


def render_slides(
    slides: List[Dict],
    out_dir: str | Path,
    theme: Dict | None = None,
    html_timeout: float = 30.0,
) -> List[Path]:
    """渲染每页 PNG。优先 Electron HTML 引擎，失败回退 Pillow。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    existing = sorted(out.glob("page_*.png"))
    if len(existing) >= len(slides):
        return existing[: len(slides)]

    # 1) HTML 路线
    try:
        html_text = build_slides_html(slides, theme)
        html_path = out / "slides.html"
        html_path.write_text(html_text, encoding="utf-8")
        jid = render_queue.enqueue(html_path, len(slides), out)
        if render_queue.wait(jid, len(slides), timeout=html_timeout):
            pngs = sorted(out.glob("page_*.png"))
            if len(pngs) >= len(slides):
                return pngs[: len(slides)]
    except Exception:
        pass

    # 2) Pillow 兜底
    return _render_pillow(slides, out, theme)


def render_with_soffice(pptx_path: str | Path, out_dir: str | Path) -> List[Path] | None:
    """高保真渲染钩子：本机装有 LibreOffice 时用 soffice 转 PNG。"""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        run_quiet(
            [soffice, "--headless", "--convert-to", "png", "--outdir", str(out), str(pptx_path)],
            timeout=120,
        )
        pngs = sorted(out.glob("*.png"))
        return pngs if pngs else None
    except Exception:
        return None
