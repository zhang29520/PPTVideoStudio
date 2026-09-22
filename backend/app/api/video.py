"""视频导出 API：后台任务 + 进度查询 + 下载。"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import store, tasks
from ..services.video import compose_video

router = APIRouter()


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
    # 原始 PPT 文件（导入型项目为 upload.pptx；生成型为重建的 output.pptx）
    pptx_rel = project.get("files", {}).get("pptx")
    pptx_path = str(Path(store.project_dir(project_id)) / pptx_rel) if pptx_rel else None
    # 补齐解说词长度（导入型项目可能没有 script）
    while len(script) < len(project["slides"]):
        script.append(project["slides"][len(script)].get("title", ""))
    while len(durations) < len(audio):
        durations.append(5.0)

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
