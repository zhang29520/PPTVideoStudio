"""可编辑 PPTX 构建：用 python-pptx 生成真正的文本框/形状。

深蓝 #1a3a5c + 金色 #c9a96e 主题。
"""
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


def build_pptx(slides: List[Dict], out_path: str | Path) -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    for i, s in enumerate(slides):
        slide = prs.slides.add_slide(blank)
        title = s.get("title", "")
        bullets = s.get("bullets", []) or []
        is_cover = i == 0

        # 背景
        bg = slide.shapes.add_shape(1, 0, 0, SLIDE_W, SLIDE_H)
        bg.fill.solid()
        bg.fill.fore_color.rgb = NAVY if is_cover else WHITE
        bg.line.fill.background()
        bg.shadow.inherit = False

        if is_cover:
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
            _set_text(tb.text_frame, title, 30, NAVY, bold=True)
            line = slide.shapes.add_shape(1, Emu(822960), Emu(1554480), Emu(1828800), Emu(91440))
            line.fill.solid()
            line.fill.fore_color.rgb = GOLD
            line.line.fill.background()
            line.shadow.inherit = False

            # 要点区
            if bullets:
                body = slide.shapes.add_textbox(Emu(822960), Emu(2011680), Emu(10515600), Emu(4114800))
                tf = body.text_frame
                tf.word_wrap = True
                for j, b in enumerate(bullets):
                    p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                    run = p.add_run()
                    run.text = f"• {b}"
                    run.font.size = Pt(18)
                    run.font.color.rgb = DARK
                    run.font.name = FONT
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
