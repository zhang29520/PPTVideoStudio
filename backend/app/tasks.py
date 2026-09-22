"""进程内后台任务注册表（MVP：单机单进程足够）。"""
import threading
import time
import uuid

_tasks: dict = {}
_lock = threading.Lock()


def start(fn) -> str:
    tid = uuid.uuid4().hex[:12]

    def runner():
        with _lock:
            _tasks[tid] = {"status": "running", "progress": 0.0, "message": "", "result": None, "error": None}
        try:
            result = fn(lambda p, msg: _update(tid, p, msg))
            with _lock:
                _tasks[tid].update(status="done", progress=1.0, result=result)
        except Exception as e:  # noqa: BLE001
            with _lock:
                _tasks[tid].update(status="error", error=str(e))

    threading.Thread(target=runner, daemon=True).start()
    return tid


def _update(tid: str, progress: float, message: str):
    with _lock:
        if tid in _tasks:
            _tasks[tid].update(progress=round(progress, 3), message=message)


def get(tid: str) -> dict:
    with _lock:
        return _tasks.get(tid, {"status": "not_found"})


def cleanup(max_age_s: int = 3600):
    with _lock:
        now = time.time()
        for k in list(_tasks.keys()):
            pass  # MVP：不做过期清理，重启即清空
