"""TTS 配音引擎：edge-tts 逐页合成，失败时用 FFmpeg 生成静音兜底。"""
import asyncio
import json
from pathlib import Path
from typing import Dict, List

import edge_tts

from ..subproc import run_quiet
from ..config import load_settings


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


def _synth_one(text: str, voice: str, rate: str, volume: str, out: Path) -> bool:
    async def run():
        tts = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        await tts.save(str(out))

    try:
        asyncio.run(run())
        return out.exists() and out.stat().st_size > 1000
    except Exception:
        return False


def synthesize_pages(
    pages: List[str],
    out_dir: str | Path,
    voice: str | None = None,
    rate: str | None = None,
    volume: str | None = None,
) -> Dict:
    """逐页合成音频，返回 {audio_paths, durations, engine}。

    某页合成失败（网络/配额）→ 用 6 秒静音兜底，保证流水线不断。
    """
    s = load_settings()
    voice = voice or s["tts_voice"]
    rate = rate or s["tts_rate"]
    volume = volume or s["tts_volume"]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio_paths: List[str] = []
    durations: List[float] = []
    ok_count = 0

    for i, text in enumerate(pages):
        p = out / f"page_{i:03d}.mp3"
        # 中文按 ~4.5 字/秒 估算兜底时长
        est = max(3.0, len(text) / 4.5 + 1.0)
        if text.strip() and _synth_one(text, voice, rate, volume, p):
            ok_count += 1
            d = _audio_duration(p)
            if d <= 0:
                _silence(p, est)
                d = est
            durations.append(d)
        else:
            _silence(p, est)
            durations.append(est)
        audio_paths.append(str(p))

    return {
        "audio_paths": audio_paths,
        "durations": durations,
        "engine": f"edge-tts ({ok_count}/{len(pages)} ok)",
    }
