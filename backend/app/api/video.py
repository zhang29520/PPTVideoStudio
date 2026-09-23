"""视频导出 API：后台任务 + 进度查询 + 下载。"""
import json
from hashlib import md5
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import store, tasks
from ..services.video import compose_video

router = APIRouter()


def _cached_real(project: dict):
    """预览阶段已转换的原始页面缓存（thumbs_real/<sig>/page_*.png + .done）。

    返回 (pngs, transitions) 或 None。命中后视频合成零转换开销（省 2~5 分钟）。
    """
    rel = project.get("files", {}).get("pptx")
    if rel != "upload.pptx":
        return None
    d = Path(store.project_dir(project["id"]))
    pptx = d / rel
    if not pptx.exists():
        return None
    sig = md5(f"{pptx.name}|{pptx.stat().st_size}".encode("utf-8")).hexdigest()[:12]
    out = d / "thumbs_real" / sig
    pngs = sorted(out.glob("page_*.png"))
    if not (pngs and (out / ".done").exists()):
        return None
    transitions = []
    tj = out / "transitions.json"
    if tj.exists():
        try:
            transitions = json.loads(tj.read_text(encoding="utf-8"))
        except Exception:
            transitions = []
    return pngs, transitions


@router.post("/api/video/export/{project_id}")
def export_video(project_id: str, payload: dict = None):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if not project.get("slides"):
        raise HTTPException(400, "请先生成或导入 PPT")
    script = project.get("script", [])
    audio = project.get("files", {}).get("audio", [])
    durations = project.get("audio_durations", [])
    if not audio or len(audio) != len(project["slides"]):
        raise HTTPException(400, "请先生成与页面数一致的配音")

    payload = payload or {}
    # 仅导入型项目（upload.pptx）走 Office/LibreOffice 渲染原始画面；
    # 生成型项目用内置版式 HTML 渲染——与预览画面完全一致，
    # 且避免 LibreOffice 重绘丢失主题样式（绿卡片变白底）+ 省去整轮转换。
    pptx_rel = project.get("files", {}).get("pptx")
    pptx_path = str(Path(store.project_dir(project_id)) / pptx_rel) if pptx_rel == "upload.pptx" else None
    # 补齐解说词长度（导入型项目可能没有 script）
    while len(script) < len(project["slides"]):
        script.append(project["slides"][len(script)].get("title", ""))
    while len(durations) < len(audio):
        durations.append(5.0)

    # 复用预览阶段的原始页面缓存（页数与幻灯片一致才复用，避免错位）
    cached = _cached_real(project)
    if cached and len(cached[0]) == len(project["slides"]):
        real_pngs, real_transitions = cached
    else:
        real_pngs, real_transitions = None, None

    def job(progress):
        progress(0.05, "渲染页面图")
        result = compose_video(
            slides=project["slides"],
            script_pages=script,
            audio_paths=[str(Path(store.project_dir(project_id)) / "audio" / a) for a in audio],
            durations=durations,
            out_dir=Path(store.project_dir(project_id)),
            project_id=project_id,
            resolution=payload.get("resolution", "1080p"),
            fps=int(payload.get("fps", 30)),
            transition=float(payload.get("transition", 0.5)),
            subtitle=bool(payload.get("subtitle", True)),
            progress=progress,
            pptx_path=pptx_path,
            follow_transition=bool(payload.get("follow_transition", False)),
            theme=project.get("theme"),
            effects=bool(payload.get("effects", project.get("effects", False))),
            bgm=bool(payload.get("bgm", True)),
            bgm_style=str(payload.get("bgm_style") or "calm"),
            real_pngs=real_pngs,
            real_transitions=real_transitions,
        )
        project["files"]["video"] = Path(result["video_path"]).name
        project["files"]["srt"] = Path(result["srt_path"]).name
        store.save_project(project)
        return {
            "video": project["files"]["video"],
            "duration": result["duration"],
            "engine": result.get("engine", ""),
        }

    tid = tasks.start(job)
    return {"taskId": tid, "message": "视频合成任务已启动"}


@router.get("/api/video/task/{task_id}")
def video_task(task_id: str):
    return tasks.get(task_id)


@router.get("/api/bgm/list")
def bgm_list():
    """内置背景音乐风格列表（全部为本项目程序化生成，可商用）。"""
    from ..services.video import BGM_STYLES, ASSETS_DIR

    out = []
    for key, (name, fname) in BGM_STYLES.items():
        out.append({"id": key, "name": name,
                    "file": f"/api/bgm/{key}/file",
                    "exists": (ASSETS_DIR / fname).exists()})
    return {"styles": out}


@router.get("/api/bgm/{style_id}/file")
def bgm_file(style_id: str):
    from ..services.video import BGM_STYLES, ASSETS_DIR

    item = BGM_STYLES.get(style_id)
    if not item:
        raise HTTPException(404, "风格不存在")
    path = ASSETS_DIR / item[1]
    if not path.exists():
        raise HTTPException(404, "音乐文件缺失")
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


@router.get("/api/video/{project_id}/download")
def download_video(project_id: str):
    project = store.load_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    rel = project.get("files", {}).get("video")
    if not rel:
        raise HTTPException(404, "尚未导出视频")
    path = Path(store.project_dir(project_id)) / rel
    if not path.exists():
        raise HTTPException(404, "视频文件不存在")
    return FileResponse(path, filename=f"{project['topic'][:20] or project_id}.mp4")
