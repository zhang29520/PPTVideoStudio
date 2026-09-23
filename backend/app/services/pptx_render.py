"""导入型 PPTX 的原始画面渲染（视频里显示用户 PPT 的真实页面）。

优先级：
1. Windows COM：PowerPoint（Office）或 WPS（Kwpp）逐页导出 PNG —— 最高保真，
   同时可读取每页的切换动效
2. LibreOffice（soffice）转 PDF → PyMuPDF 栅格化 —— 跨平台备选
3. 失败返回 None，由调用方回退到内置文字版式渲染
"""
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Dict, List

from ..subproc import run_quiet

TARGET_W, TARGET_H = 1920, 1080

# soffice 全局串行锁：避免并发转换（多个缩略图请求同时到达）互相冲突；
# 同时 render_pptx_real 内部有"双检"——前一个转换完成后，排队的直接复用结果
_SOFFICE_LOCK = threading.Lock()


def _log_soffice_fail(cmd: str, r, reason: str):
    """soffice 转换失败时落盘日志，便于排查环境问题。"""
    try:
        log = Path(os.path.expanduser("~/Library/Application Support/PPTVideoStudio"))
        log.mkdir(parents=True, exist_ok=True)
        with open(log / "soffice_error.log", "a", encoding="utf-8") as f:
            import time
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {reason}\n")
            f.write(f"cmd: {cmd}\n")
            f.write(f"returncode: {getattr(r, 'returncode', 'N/A')}\n")
            f.write(f"stdout: {getattr(r, 'stdout', b'')!r}\n")
            f.write(f"stderr: {getattr(r, 'stderr', b'')!r}\n")
    except Exception:
        pass


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
    """LibreOffice：pptx → pdf → PyMuPDF 栅格化。

    每次转换使用一次性临时 profile（用完即删）：
    - 共享 profile 一旦被强杀/崩溃污染就会持续报 DeploymentException 启动崩溃
    - 独立 profile 天然规避实例冲突，代价仅是每次 2~3 秒的初始化
    """
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        # macOS cask 安装不在 PATH 上，探测标准位置
        for cand in (
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        ):
            if os.path.exists(cand):
                soffice = cand
                break
    if not soffice:
        return None
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None
    tmp = out_dir / "_pdf"
    tmp.mkdir(parents=True, exist_ok=True)
    with _SOFFICE_LOCK:
        # 双检：并发请求排队后，前一个已完成转换则直接复用，不重复转换
        existing = sorted(out_dir.glob("page_*.png")) if out_dir.exists() else []
        if existing:
            return existing
        prof_dir = None
        try:
            cmd = [soffice, "--headless", "--convert-to", "pdf",
                   "--outdir", str(tmp), str(pptx)]
            if sys.platform == "darwin":
                # 路径必须 URL 编码（空格 → %20），否则 soffice 启动即崩
                from urllib.parse import quote

                prof_dir = Path(tempfile.mkdtemp(prefix="pvs_lo_"))
                cmd.insert(1, "-env:UserInstallation=file://" + quote(str(prof_dir)))
            r = run_quiet(cmd, timeout=600)
            if r.returncode != 0:
                _log_soffice_fail(soffice, r, "convert returncode!=0")
                return None
            pdfs = list(tmp.glob("*.pdf"))
            if not pdfs:
                _log_soffice_fail(soffice, r, "no pdf produced")
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
        except Exception as e:
            try:
                log = Path(os.path.expanduser(
                    "~/Library/Application Support/PPTVideoStudio"))
                log.mkdir(parents=True, exist_ok=True)
                with open(log / "soffice_error.log", "a", encoding="utf-8") as f:
                    import time
                    f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] exception: {e!r}\n")
            except Exception:
                pass
            return None
        finally:
            if prof_dir:
                shutil.rmtree(prof_dir, ignore_errors=True)


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
