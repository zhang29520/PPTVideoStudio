"""PPTVideoStudio 本地后端服务入口。

运行：cd backend && python -m app.main  （127.0.0.1:8000）
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import ensure_dirs
from .api import ppt, projects, settings, speech, tts, video

ensure_dirs()

app = FastAPI(title="PPTVideoStudio Backend", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(ppt.router)
app.include_router(speech.router)
app.include_router(tts.router)
app.include_router(video.router)
app.include_router(settings.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    from . import tasks

    return tasks.get(task_id)


# ---- HTML 渲染任务端点（Electron 渲染工作器对接） ----
@app.get("/api/render/jobs/next")
def render_next_job():
    """Electron 渲染进程轮询领取任务。"""
    from .services import render_queue

    render_queue.cleanup()
    job = render_queue.take_next()
    return job or {}


@app.get("/api/render/jobs/{job_id}.html")
def render_job_html(job_id: str):
    from fastapi.responses import HTMLResponse

    from .services import render_queue

    path = render_queue.get_html_path(job_id)
    if not path:
        raise HTTPException(404, "job not found")
    return HTMLResponse(Path(path).read_text(encoding="utf-8"))


@app.post("/api/render/jobs/{job_id}/png/{index}")
async def render_job_png(job_id: str, index: int, request: Request):
    from .services import render_queue

    data = await request.body()
    if not render_queue.save_png(job_id, index, data):
        raise HTTPException(404, "job not found")
    return {"ok": True}


@app.post("/api/render/jobs/{job_id}/done")
def render_job_done(job_id: str):
    from .services import render_queue

    render_queue.mark(job_id, "done")
    return {"ok": True}


@app.post("/api/render/jobs/{job_id}/fail")
def render_job_fail(job_id: str):
    from .services import render_queue

    render_queue.mark(job_id, "failed")
    return {"ok": True}


def run():
    import os
    import uvicorn

    port = int(os.environ.get("PVS_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    run()
