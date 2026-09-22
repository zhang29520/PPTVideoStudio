"""可编辑 PPTX 构建：用 python-pptx 生成真正的文本框/形状。

深蓝 #1a3a5c + 金色 #c9a96e 主题；slide["image"]（data URI）存在时
内容页自动切换为左文右图版式。
"""
import base64
import io
import re
from pathlib import Path
from typing import Dict, List

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

SLIDE_W = Emu(12192000)  # 13.333in (16:9)
SLIDE_H = Emu(6858000)

NAVY = RGBColor(0x1A, 0x3A, 0x5C)
GOLD = RGBColor(0xC9, 0xA9, 0x6E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x33, 0x33, 0x33)
# Slidev 极客暗黑
SLV_BG = RGBColor(0x0E, 0x11, 0x17)
SLV_CARD = RGBColor(0x1C, 0x23, 0x32)
SLV_TEXT = RGBColor(0xC6, 0xD2, 0xE2)

FONT = "微软雅黑"


def _set_text(tf, text: str, size: int, color, bold=False, align=PP_ALIGN.LEFT):
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT


def build_pptx(slides: List[Dict], out_path: str | Path, theme: Dict | None = None) -> Path:
    # 主题色：用户选择的 primary + 由它派生的强调色
    primary_hex = (theme or {}).get("primary") or "1a3a5c"
    slidev = (theme or {}).get("style") == "Slidev 极客"
    primary_hex = primary_hex.lstrip("#")
    if len(primary_hex) == 3:
        primary_hex = "".join(x * 2 for x in primary_hex)
    try:
        nav = [int(primary_hex[i:i + 2], 16) for i in (0, 2, 4)]
        NAVY = RGBColor(*nav)
        GOLD = RGBColor(*[min(255, round(c + (255 - c) * 0.45)) for c in nav])
    except Exception:
        pass  # 解析失败沿用默认深蓝+金

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    for i, s in enumerate(slides):
        slide = prs.slides.add_slide(blank)
        title = s.get("title", "")
        bullets = s.get("bullets", []) or []
        is_cover = i == 0

        # 配图（data URI → 内存流）
        img_stream = None
        uri = s.get("image") if isinstance(s.get("image"), str) else ""
        if uri.startswith("data:image") and "," in uri:
            try:
                img_stream = io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))
            except Exception:
                img_stream = None

        # 背景
        bg = slide.shapes.add_shape(1, 0, 0, SLIDE_W, SLIDE_H)
        bg.fill.solid()
        bg.fill.fore_color.rgb = (SLV_BG if slidev else NAVY) if is_cover else \
            (SLV_BG if slidev else WHITE)
        bg.line.fill.background()
        bg.shadow.inherit = False
        if slidev and not is_cover:
            # 左侧强调竖条
            bar_l = slide.shapes.add_shape(1, 0, 0, Emu(140000), SLIDE_H)
            bar_l.fill.solid()
            bar_l.fill.fore_color.rgb = GOLD
            bar_l.line.fill.background()
            bar_l.shadow.inherit = False

        if is_cover:
            if img_stream:
                # 封面右半幅配图
                pic = slide.shapes.add_picture(
                    img_stream, Emu(int(SLIDE_W * 0.60)), 0,
                    width=Emu(int(SLIDE_W * 0.40)), height=SLIDE_H)
                pic.shadow.inherit = False
            bar = slide.shapes.add_shape(1, Emu(914400), Emu(2743200), Emu(365760), Emu(1371600))
            bar.fill.solid()
            bar.fill.fore_color.rgb = GOLD
            bar.line.fill.background()
            bar.shadow.inherit = False

            tb = slide.shapes.add_textbox(Emu(1554480), Emu(2514600), Emu(9144000), Emu(1828800))
            _set_text(tb.text_frame, title, 40, WHITE, bold=True)

            if bullets:
                sub = slide.shapes.add_textbox(Emu(1554480), Emu(4114800), Emu(9144000), Emu(914400))
                _set_text(sub.text_frame, " / ".join(bullets), 18, GOLD)
        else:
            # 标题区
            tb = slide.shapes.add_textbox(Emu(822960), Emu(548640), Emu(10515600), Emu(1005840))
            _set_text(tb.text_frame, f"// {title}" if slidev else title, 30,
                      GOLD if slidev else NAVY, bold=True)
            lead = str(s.get("lead", "")).strip()
            if lead:
                lt = slide.shapes.add_textbox(Emu(822960), Emu(1560000), Emu(10515600), Emu(420000))
                _set_text(lt.text_frame, lead, 13, SLV_TEXT if slidev else RGBColor(0x8A, 0x94, 0xA2))
            line = slide.shapes.add_shape(1, Emu(822960), Emu(1554480), Emu(1828800), Emu(91440))
            line.fill.solid()
            line.fill.fore_color.rgb = GOLD
            line.line.fill.background()
            line.shadow.inherit = False

            if img_stream:
                # 左文右图版式
                pic = slide.shapes.add_picture(
                    img_stream, Emu(int(SLIDE_W * 0.615)), Emu(int(SLIDE_H * 0.24)),
                    width=Emu(int(SLIDE_W * 0.335)), height=Emu(int(SLIDE_H * 0.62)))
                pic.shadow.inherit = False
                body = slide.shapes.add_textbox(Emu(822960), Emu(2011680), Emu(6500000), Emu(4114800))
            else:
                body = slide.shapes.add_textbox(Emu(822960), Emu(2011680), Emu(10515600), Emu(4114800))
            # 要点区
            if bullets:
                tf = body.text_frame
                tf.word_wrap = True
                for j, b in enumerate(bullets):
                    p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                    # 结构化要点「关键词：描述」→ 关键词加粗强调
                    k, v = b, ""
                    if "：" in b[:10] or "|" in b[:10] or ":" in b[:10]:
                        for sep in ("：", ":", "|"):
                            if sep in b[:10]:
                                k, v = b.split(sep, 1)
                                break
                    run = p.add_run()
                    run.text = f"• {k}" + ("：" if v else "")
                    run.font.size = Pt(18)
                    run.font.bold = bool(v)
                    run.font.color.rgb = (SLV_TEXT if slidev else NAVY) if v else (SLV_TEXT if slidev else DARK)
                    run.font.name = FONT
                    if v:
                        run2 = p.add_run()
                        run2.text = v
                        run2.font.size = Pt(18)
                        run2.font.color.rgb = SLV_TEXT if slidev else DARK
                        run2.font.name = FONT
                    p.space_after = Pt(10)

        # 演讲者备注
        notes = s.get("notes", "")
        if notes:
            slide.notes_slide.notes_text_frame.text = notes

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


def parse_pptx(file_path: str | Path) -> List[Dict]:
    """解析已有 PPTX：提取每页标题/文本/备注（占位形状顺序优先）。"""
    prs = Presentation(str(file_path))
    slides: List[Dict] = []
    for slide in prs.slides:
        texts: List[str] = []
        title = ""
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                t = "".join(r.text for r in para.runs).strip()
                if t:
                    texts.append(t)
        if texts:
            title = re.sub(r"^[•\-\s]+", "", texts[0])[:40]
            body = texts[1:]
        else:
            title, body = f"第 {len(slides) + 1} 页", []
        notes = ""
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        slides.append({"title": title, "bullets": body, "notes": notes})
    return slides
