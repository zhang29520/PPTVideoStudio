"""PPTVideoStudio 本地后端服务入口。

运行：cd backend && python -m app.main  （127.0.0.1:8000）
"""
from fastapi import FastAPI
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


def run():
    import os
    import uvicorn

    port = int(os.environ.get("PVS_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    run()
