"""幻灯片页面渲染：Pillow 直接绘制 16:9 PNG（不依赖 LibreOffice/PowerPoint）。

生成型 PPT 用结构化 slides JSON 高保真渲染；
导入型 PPT 解析出的文本也会用同一套版式渲染（Windows 端可替换为
PowerPoint COM / LibreOffice 渲染钩子，见 render_with_soffice）。
"""
import shutil
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

from ..subproc import run_quiet

W, H = 1920, 1080
NAVY = (26, 58, 92)
GOLD = (201, 169, 110)
WHITE = (255, 255, 255)
DARK = (51, 51, 51)
LIGHT_BG = (247, 249, 252)

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


def _draw_cover(img: ImageDraw.ImageDraw, title: str, bullets: List[str]):
    img.rectangle([0, 0, W, H], fill=NAVY)
    img.rectangle([140, 440, 210, 640], fill=GOLD)
    f_title = _font(84)
    f_sub = _font(36)
    # 标题自动降字号
    size = 84
    while size > 40 and f_title.getlength(title) > W - 400:
        size -= 4
        f_title = _font(size)
    img.text((280, 460), title, font=f_title, fill=WHITE)
    if bullets:
        sub = " / ".join(bullets)
        img.text((280, 660), sub, font=f_sub, fill=GOLD)


def _draw_content(img: ImageDraw.ImageDraw, index: int, total: int, title: str, bullets: List[str]):
    img.rectangle([0, 0, W, H], fill=LIGHT_BG)
    img.rectangle([0, 0, W, 8], fill=NAVY)
    f_title = _font(60)
    f_body = _font(38)
    f_page = _font(24)
    img.text((120, 90), title, font=f_title, fill=NAVY)
    img.rectangle([120, 190, 430, 202], fill=GOLD)
    y = 280
    for b in bullets:
        img.ellipse([124, y + 18, 140, y + 34], fill=GOLD)
        # 简单换行
        max_w = W - 320
        line = ""
        lines = []
        for ch in b:
            if f_body.getlength(line + ch) > max_w:
                lines.append(line)
                line = ch
            else:
                line += ch
        lines.append(line)
        for li, ln in enumerate(lines):
            img.text((170, y + (li * 56)), ln, font=f_body, fill=DARK)
        y += 56 * len(lines) + 34
        if y > H - 160:
            break
    img.text((W - 160, H - 70), f"{index + 1} / {total}", font=f_page, fill=(150, 150, 150))


def render_slides(slides: List[Dict], out_dir: str | Path) -> List[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    total = len(slides)
    for i, s in enumerate(slides):
        img = Image.new("RGB", (W, H), WHITE)
        d = ImageDraw.Draw(img)
        if i == 0:
            _draw_cover(d, s.get("title", ""), s.get("bullets", []) or [])
        else:
            _draw_content(d, i, total, s.get("title", ""), s.get("bullets", []) or [])
        p = out / f"page_{i:03d}.png"
        img.save(p)
        paths.append(p)
    return paths


def render_with_soffice(pptx_path: str | Path, out_dir: str | Path) -> List[Path] | None:
    """高保真渲染钩子：本机装有 LibreOffice 时用 soffice 转 PNG。

    Windows 端可替换为 PowerPoint COM 导出（EditView/文档已说明）。
    """
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
