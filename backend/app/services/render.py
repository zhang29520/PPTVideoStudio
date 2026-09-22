"""幻灯片页面渲染。

优先走 HTML 主题引擎（Electron 离屏截图，Marp/Slidev 同思路）；
Electron 不在线或超时 → 回退 Pillow 直接绘制（同样应用主题色）。
导入型 PPT 在 Windows 端可替换为 PowerPoint COM / LibreOffice 渲染钩子。
"""
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

from ..subproc import run_quiet
from . import render_queue
from .slide_html import build_slides_html

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


def _draw_cover(img: ImageDraw.ImageDraw, title: str, bullets: List[str], primary, dark):
    img.rectangle([0, 0, W, H], fill=primary)
    # 装饰圆
    img.ellipse([W - 420, -220, W + 260, 460], fill=dark)
    img.ellipse([W - 620, H - 320, W - 180, H + 120], fill=dark)
    f_title = _font(92)
    size = 92
    while size > 40 and f_title.getlength(title) > W - 420:
        size -= 4
        f_title = _font(size)
    img.rectangle([160, 470, 320, 486], fill=(255, 255, 255))
    img.text((160, 540), title, font=f_title, fill=(255, 255, 255))
    if bullets:
        f_sub = _font(34)
        img.text((160, 760), " / ".join(bullets[:3]), font=f_sub, fill=light_bg_of(primary))


def light_bg_of(primary):
    return tuple(min(255, round(c + (255 - c) * 0.55)) for c in primary)


def _draw_content(img: ImageDraw.ImageDraw, index: int, total: int, topic: str,
                  title: str, bullets: List[str], primary, text):
    img.rectangle([0, 0, W, H], fill=(247, 249, 252))
    img.rectangle([0, 0, W, 12], fill=primary)
    f_title = _font(60)
    f_body = _font(36)
    f_page = _font(24)
    f_num = _font(26)
    img.text((120, 90), title, font=f_title, fill=primary)
    img.rectangle([120, 186, 240, 198], fill=primary)
    y = 280
    for j, b in enumerate(bullets):
        # 要点卡片
        img.rounded_rectangle([110, y - 14, W - 120, y + 74], radius=16,
                              fill=(255, 255, 255), outline=(228, 233, 240), width=2)
        img.rounded_rectangle([138, y + 2, 206, y + 58], radius=12, fill=primary)
        num_txt = f"{j + 1:02d}"
        nw = f_num.getlength(num_txt)
        img.text((172 - nw / 2, y + 14), num_txt, font=f_num, fill=(255, 255, 255))
        max_w = W - 460
        line, lines = "", []
        for ch in b:
            if f_body.getlength(line + ch) > max_w:
                lines.append(line)
                line = ch
            else:
                line += ch
        lines.append(line)
        for li, ln in enumerate(lines[:2]):
            img.text((240, y + 6 + li * 46), ln, font=f_body, fill=text)
        y += 108
        if y > H - 180:
            break
    img.text((120, H - 64), topic[:24], font=f_page, fill=(150, 150, 150))
    img.text((W - 180, H - 64), f"{index + 1} / {total}", font=f_page, fill=(150, 150, 150))


def _render_pillow(slides: List[Dict], out_dir: Path, theme: Dict | None) -> List[Path]:
    primary, dark, _, text = _theme_colors(theme)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    total = len(slides)
    topic = slides[0].get("title", "") if slides else ""
    for i, s in enumerate(slides):
        img = Image.new("RGB", (W, H), (255, 255, 255))
        d = ImageDraw.Draw(img)
        if i == 0:
            _draw_cover(d, s.get("title", ""), s.get("bullets", []) or [], primary, dark)
        else:
            _draw_content(d, i, total, topic, s.get("title", ""),
                          s.get("bullets", []) or [], primary, text)
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
