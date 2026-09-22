"""HTML 渲染任务队列：后端出任务，Electron 离屏窗口截图回传 PNG。

流程：
1. render_slides() 把 slides HTML 存盘并登记任务（pending）
2. Electron main.js 每 2.5s GET /api/render/jobs/next 领任务
3. Electron 加载 /api/render/{jid}.html，逐页 capturePage → POST png/{i}
4. 全部传完 POST done；后端等待方检查 status / 收到的 PNG 数
5. 超时或 fail → 调用方回退 Pillow 渲染
"""
import threading
import time
import uuid
from pathlib import Path

_JOBS: dict = {}
_LOCK = threading.Lock()


def enqueue(html_path: str | Path, count: int, out_dir: str | Path) -> str:
    jid = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[jid] = {
            "id": jid,
            "html_path": str(html_path),
            "count": int(count),
            "out_dir": Path(out_dir),
            "status": "pending",  # pending → rendering → done / failed
            "received": set(),
            "created": time.time(),
        }
    return jid


def take_next() -> dict | None:
    with _LOCK:
        for j in _JOBS.values():
            if j["status"] == "pending":
                j["status"] = "rendering"
                return {"id": j["id"], "count": j["count"]}
    return None


def get_html_path(jid: str) -> str | None:
    with _LOCK:
        j = _JOBS.get(jid)
        return j["html_path"] if j else None


def save_png(jid: str, index: int, data: bytes) -> bool:
    with _LOCK:
        j = _JOBS.get(jid)
        if not j:
            return False
        out = j["out_dir"]
        out.mkdir(parents=True, exist_ok=True)
        (out / f"page_{index:03d}.png").write_bytes(data)
        j["received"].add(index)
        return True


def mark(jid: str, status: str):
    with _LOCK:
        if jid in _JOBS:
            _JOBS[jid]["status"] = status


def wait(jid: str, count: int, timeout: float = 30.0) -> bool:
    """阻塞等待任务完成；成功返回 True（PNG 齐全）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        with _LOCK:
            j = _JOBS.get(jid)
            if not j:
                return False
            if j["status"] == "failed":
                return False
            if len(j["received"]) >= count and j["status"] in ("done", "rendering"):
                j["status"] = "done"
                return True
            if j["status"] == "done":
                return len(j["received"]) >= count
        time.sleep(0.4)
    with _LOCK:
        if jid in _JOBS:
            _JOBS[jid]["status"] = "failed"
    return False


def cleanup(keep: int = 30):
    """清理旧任务，防内存泄漏。"""
    with _LOCK:
        if len(_JOBS) <= keep:
            return
        for jid in sorted(_JOBS, key=lambda k: _JOBS[k]["created"])[:-keep]:
            _JOBS.pop(jid, None)
