"""跨平台子进程工具：Windows 无控制台程序调用子进程时避免闪黑框。"""
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def run_quiet(cmd, timeout: int = 300):
    """subprocess.run 的静默封装：Windows 下不弹黑框。"""
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )
