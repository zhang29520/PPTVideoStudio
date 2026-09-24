"""TTS 配音引擎：edge-tts 逐页合成，失败时用 FFmpeg 生成静音兜底。"""
import asyncio
import json
from pathlib import Path
from typing import Dict, List

import edge_tts

from ..subproc import run_quiet
from ..config import load_settings

# edge-tts 底层 aiohttp 默认不读系统代理环境变量（HTTP_PROXY），导致
# 代理环境下直连微软 TTS 失败。打补丁让所有 ClientSession 默认 trust_env。
import aiohttp

_orig_session = aiohttp.ClientSession


class _ProxyAwareSession(_orig_session):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("trust_env", True)
        super().__init__(*args, **kwargs)


aiohttp.ClientSession = _ProxyAwareSession


def speed_to_rate(speed: float) -> str:
    """语速倍数（1=正常，0.1~1 慢放，1.1~2 快放）→ edge-tts rate 百分比字符串。"""
    speed = max(0.1, min(2.0, float(speed)))
    pct = round((speed - 1) * 100)
    return f"+{pct}%" if pct >= 0 else f"{pct}%"


def _audio_duration(path: Path) -> float:
    try:
        out = run_quiet(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            timeout=30,
        )
        return float(json.loads(out.stdout.decode("utf-8", "ignore"))["format"]["duration"])
    except Exception:
        return 0.0


def _silence(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    run_quiet(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", str(max(2.0, seconds)), "-q:a", "9", str(path)],
        timeout=60,
    )


def _synth_one(text: str, voice: str, rate: str, volume: str, out: Path, retries: int = 2, err_out: list = None) -> bool:
    async def run():
        tts = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        await tts.save(str(out))

    last_err = None
    for attempt in range(retries + 1):
        try:
            asyncio.run(run())
            if out.exists() and out.stat().st_size > 1000:
                return True
            last_err = "合成结果为空"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < retries:
            import time
            time.sleep(1.2 * (attempt + 1))  # 网络抖动退避重试
    if err_out is not None and last_err:
        err_out.append(last_err)
    return False


def synthesize_pages(
    pages: List[str],
    out_dir: str | Path,
    voice: str | None = None,
    rate: str | None = None,
    volume: str | None = None,
    progress=None,
) -> Dict:
    """并行合成音频（5 路并发，network-bound 提速约 4~5 倍）。

    返回 {audio_paths, durations, engine}。
    某页合成失败（网络/配额）→ 用静音兜底，保证流水线不断。
    progress(ratio, message) 用于任务进度上报。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    s = load_settings()
    voice = voice or s["tts_voice"]
    rate = rate or s["tts_rate"]
    volume = volume or s["tts_volume"]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = max(1, len(pages))
    workers = min(5, total)
    if progress:
        progress(0.0, f"开始并行合成 {total} 页配音（{workers} 路并发）…")

    done_lock = threading.Lock()
    done_count = 0

    def job(i: int, text: str):
        nonlocal done_count
        p = out / f"page_{i:03d}.mp3"
        # 中文按 ~4.5 字/秒 估算兜底时长
        est = max(3.0, len(text) / 4.5 + 1.0)
        ok = bool(text.strip()) and _synth_one(text, voice, rate, volume, p)
        if ok:
            d = _audio_duration(p)
            if d <= 0:
                _silence(p, est)
                d = est
        else:
            _silence(p, est)
            d = est
        with done_lock:
            done_count += 1
            if progress:
                progress(done_count / total,
                         f"已完成 {done_count}/{total} 页配音…")
        return i, ok

    results: List[bool] = [False] * len(pages)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(job, i, t) for i, t in enumerate(pages)]
        for f in as_completed(futs):
            i, ok = f.result()
            results[i] = ok

    audio_paths = [str(out / f"page_{i:03d}.mp3") for i in range(len(pages))]
    durations = [_audio_duration(Path(p)) or 3.0 for p in audio_paths]
    ok_count = sum(1 for r in results if r)

    return {
        "audio_paths": audio_paths,
        "durations": durations,
        "engine": f"edge-tts ({ok_count}/{len(pages)} ok)",
    }
