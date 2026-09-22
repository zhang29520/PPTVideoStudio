"""导入型 PPTX 的原始画面渲染（视频里显示用户 PPT 的真实页面）。

优先级：
1. Windows COM：PowerPoint（Office）或 WPS（Kwpp）逐页导出 PNG —— 最高保真，
   同时可读取每页的切换动效
2. LibreOffice（soffice）转 PDF → PyMuPDF 栅格化 —— 跨平台备选
3. 失败返回 None，由调用方回退到内置文字版式渲染
"""
import sys
from pathlib import Path
from typing import Dict, List

from ..subproc import run_quiet

TARGET_W, TARGET_H = 1920, 1080


def _render_com(pptx: Path, out_dir: Path) -> tuple[List[Path], List[Dict]] | None:
    """Windows COM：Office PowerPoint 或 WPS。返回 (pngs, transitions)。"""
    if sys.platform != "win32":
        return None
    try:
        import win32com.client
        import pythoncom
    except Exception:
        return None

    pythoncom.CoInitialize()
    app = None
    opened = False
    try:
        for prog_id in ("PowerPoint.Application", "KWPP.Application"):
            try:
                app = win32com.client.Dispatch(prog_id)
                break
            except Exception:
                continue
        if app is None:
            return None
        pres = app.Presentations.Open(
            str(pptx.resolve()), ReadOnly=True, WithWindow=False
        )
        opened = True
        out_dir.mkdir(parents=True, exist_ok=True)
        pngs: List[Path] = []
        transitions: List[Dict] = []
        for i in range(1, pres.Slides.Count + 1):
            slide = pres.Slides(i)
            p = out_dir / f"page_{i - 1:03d}.png"
            slide.Export(str(p.resolve()), "PNG", TARGET_W, TARGET_H)
            pngs.append(p)
            # 读取切换动效
            t = {"effect": "fade", "duration": 0.5}
            try:
                st = slide.SlideShowTransition
                entry = int(st.EntryEffect)
                if entry in (0, 1, 2):  # 无动效 / 硬切
                    t["effect"] = "none"
                try:
                    t["duration"] = max(0.1, min(1.5, float(st.Duration)))
                except Exception:
                    pass
            except Exception:
                pass
            transitions.append(t)
        return pngs, transitions
    except Exception:
        return None
    finally:
        try:
            if opened:
                pres.Close()
        except Exception:
            pass
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def _render_soffice(pptx: Path, out_dir: Path) -> List[Path] | None:
    """LibreOffice：pptx → pdf → PyMuPDF 栅格化。"""
    import shutil

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None
    tmp = out_dir / "_pdf"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        r = run_quiet(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(pptx)],
            timeout=180,
        )
        if r.returncode != 0:
            return None
        pdfs = list(tmp.glob("*.pdf"))
        if not pdfs:
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        pngs: List[Path] = []
        doc = fitz.open(pdfs[0])
        zoom = TARGET_W / doc[0].rect.width
        mat = fitz.Matrix(zoom, zoom)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat)
            p = out_dir / f"page_{i:03d}.png"
            pix.save(str(p))
            pngs.append(p)
        doc.close()
        return pngs if pngs else None
    except Exception:
        return None


def render_pptx_real(pptx: str | Path, out_dir: str | Path) -> tuple[List[Path], List[Dict], str] | None:
    """尝试用原始 PPT 渲染每页画面。

    返回 (pngs, transitions, engine)；全部失败返回 None。
    transitions 仅 COM 路径有效（soffice 路径统一返回全局默认）。
    """
    pptx = Path(pptx)
    out_dir = Path(out_dir)
    if not pptx.exists():
        return None

    com = _render_com(pptx, out_dir)
    if com:
        pngs, transitions = com
        if pngs:
            return pngs, transitions, "PowerPoint/WPS 原始画面"

    soffice_pngs = _render_soffice(pptx, out_dir)
    if soffice_pngs:
        return soffice_pngs, [{"effect": "global", "duration": 0.5}] * len(soffice_pngs), "LibreOffice 原始画面"

    return None
