"""项目本地存储：每个项目一个目录 + project.json。"""
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from .config import PROJECTS_DIR


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def load_project(project_id: str) -> Optional[dict]:
    path = project_dir(project_id) / "project.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_project(project: dict) -> dict:
    d = project_dir(project["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "project.json").write_text(
        json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return project


def create_project(topic: str) -> dict:
    pid = time.strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    project = {
        "id": pid,
        "topic": topic,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        # 幻灯片内容（结构化，可编辑）
        "slides": [],
        # 逐页解说词，index 与 slides 对齐
        "script": [],
        # 产物文件相对路径
        "files": {"pptx": None, "audio": [], "video": None, "srt": None},
    }
    save_project(project)
    return project


def list_projects() -> list:
    out = []
    if not PROJECTS_DIR.exists():
        return out
    for d in sorted(PROJECTS_DIR.iterdir(), reverse=True):
        pj = d / "project.json"
        if pj.exists():
            try:
                data = json.loads(pj.read_text(encoding="utf-8"))
                out.append(
                    {
                        "id": data["id"],
                        "topic": data.get("topic", ""),
                        "created_at": data.get("created_at", ""),
                        "slides": len(data.get("slides", [])),
                        "has_video": bool(data.get("files", {}).get("video")),
                    }
                )
            except Exception:
                continue
    return out
