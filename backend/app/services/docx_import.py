"""Word (.docx) 导入解析：按标题层级切分为 PPT 结构。

策略：
- Heading 1/2（或样式名含"标题"）→ 章节页标题；Heading 2 归属于最近的 H1
- 正文段落 → 该章节的要点素材（每段压缩到 ≤90 字，取前 5 条）
- 无任何标题时按段落长度自动分页（每 3~4 段一页）
- 每页自动生成 lead 导语（取该节第一句）
"""
import re
from pathlib import Path

from docx import Document


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def parse_docx(file_path: str | Path, max_pages: int = 24) -> dict:
    """返回 {title, sections: [{heading, level, paras[]}, ...]}"""
    doc = Document(str(file_path))
    title = ""
    sections: list = []
    cur: dict | None = None

    for p in doc.paragraphs:
        text = _clean(p.text)
        if not text:
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        is_title_style = ("heading" in style or "标题" in (p.style.name or ""))
        # Word 标题级别
        lvl = 1
        m = re.search(r"(\d)", style)
        if m:
            lvl = min(2, int(m.group(1)))

        if is_title_style and len(text) <= 60:
            if not title and lvl <= 1:
                title = text
                continue
            cur = {"heading": text, "level": lvl, "paras": []}
            sections.append(cur)
            continue

        if cur is None:
            # 正文出现在第一个标题前：若文档还没有标题，把它当标题
            if not title and len(text) <= 40 and len(sections) == 0:
                title = text
                cur = {"heading": text, "level": 1, "paras": []}
                sections.append(cur)
                cur["paras"].append(text)
                continue
            cur = {"heading": "", "level": 1, "paras": []}
            sections.append(cur)
        elif len(cur["paras"]) >= 4:
            # 任何一节段落过多（尤其无标题样式的长文档）都自动分页，
            # 避免全文挤进一节导致只生成极少页数
            cur = {"heading": "", "level": 1, "paras": []}
            sections.append(cur)
        cur["paras"].append(text)

    if not title:
        title = Path(file_path).stem
    return {"title": title, "sections": sections[:max_pages]}


def docx_to_slides(file_path: str | Path, max_pages: int = 24) -> list:
    """docx → slides JSON（与内置引擎同构）。"""
    data = parse_docx(file_path, max_pages)
    slides: list = []

    # 封面
    cover_sub = []
    if data["sections"]:
        first = data["sections"][0]
        if first["paras"]:
            cover_sub.append(_clean(first["paras"][0])[:40])
    slides.append({
        "title": data["title"],
        "lead": "",
        "bullets": cover_sub or ["由 Word 文档智能生成"],
    })

    for sec in data["sections"]:
        heading = sec["heading"] or ""
        # 合并 H2 到当前页要点
        pts: list = []
        for para in sec["paras"]:
            para = _clean(para)
            if len(para) < 8:
                continue
            pts.append(_condense(para))
        if not pts and sec["paras"]:
            pts.append(_condense(_clean(sec["paras"][0])))
        if not pts:
            continue
        # 无标题的自动分段：取第一条正文前 16 字当页标题
        if not heading:
            heading = re.sub(r"[，。：；！？,.:;!?…\s].*$", "", _clean(sec["paras"][0]))[:16] or "正文摘要"
        lead = ""
        # 导语取第一条完整句
        raw = sec["paras"][0] if sec["paras"] else ""
        m = re.search(r"^(.{20,60}?[。！？；])", raw)
        if m:
            lead = m.group(1)
        slides.append({
            "title": heading[:24],
            "lead": lead,
            "bullets": pts[:5],
        })

    # 总结页
    if len(slides) >= 3:
        slides.append({
            "title": "总结与展望",
            "lead": f"回顾「{data['title']}」的核心内容",
            "bullets": [
                "核心回顾：全文要点已按章节结构化呈现",
                "下一步：明确落地计划与责任分工",
                "感谢聆听：欢迎讨论与指正",
            ],
        })
    return slides[:max_pages]


def _condense(s: str) -> str:
    """正文段 → 要点：截断到 90 字并在句末断句。"""
    if len(s) <= 90:
        if s[-1] in "。！？；":
            return s
        return s + ("。" if len(s) >= 12 else "")
    cut = s[:90]
    for p in ("。", "！", "？", "；"):
        i = cut.rfind(p)
        if i > 40:
            return cut[:i + 1]
    i = cut.rfind("，")
    return (cut[:i] + "。") if i > 40 else cut + "…"
