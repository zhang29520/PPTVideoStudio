"""视频合成引擎（FFmpeg）。

链路：slides JSON → Pillow 渲染 PNG → 每页段落(画面+配音+淡入淡出) → concat → MP4。
同时产出 SRT 字幕；若本机 FFmpeg 支持 subtitles 滤镜则直接烧录字幕。

effects=True 时启用「随机镜头动效」：每页随机 Ken Burns（推近/拉远/横移）
+ 随机淡入淡出时长，成片更有观感。
"""
import json
import random
import shutil
from pathlib import Path
from typing import Dict, List

from ..subproc import run_quiet
from .render import render_slides

RES_MAP = {"720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}

# 内置可商用背景音乐（本项目程序化生成，无第三方版权）
BGM_PATH = Path(__file__).resolve().parent.parent / "assets" / "bgm_calm.mp3"


def _run(cmd: List[str], timeout: int = 300) -> bool:
    try:
        r = run_quiet(cmd, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


def _fmt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(pages: List[str], durations: List[float], out_path: Path) -> Path:
    lines = []
    t = 0.0
    for i, (text, dur) in enumerate(zip(pages, durations)):
        start = t
        end = t + dur
        lines.append(f"{i + 1}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{text}\n")
        t = end
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _has_subtitles_filter() -> bool:
    try:
        r = run_quiet(["ffmpeg", "-filters"], timeout=30)
        return "subtitles" in r.stdout.decode("utf-8", "ignore")
    except Exception:
        return False


def _ken_burns_filter(variant: int, width: int, height: int, fps: int, dur: float) -> str:
    """随机镜头动效滤镜（zoompan）：0 推近 1 拉远 2 右移 3 左移。"""
    frames = max(1, int(dur * fps) + 1)
    if variant == 0:  # 缓慢推近
        z = f"min(zoom+{0.10 / frames:.6f},1.10)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif variant == 1:  # 缓慢拉远
        z = f"if(lte(on,1),1.10,max(1.0,zoom-{0.10 / frames:.6f}))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif variant == 2:  # 放大 + 向右平移
        z = f"min(zoom+{0.08 / frames:.6f},1.08)"
        x = "(iw-iw/zoom)*on/" + str(frames)
        y = "ih/2-(ih/zoom/2)"
    else:  # 放大 + 向左平移
        z = f"min(zoom+{0.08 / frames:.6f},1.08)"
        x = "(iw-iw/zoom)*(1-on/" + str(frames) + ")"
        y = "ih/2-(ih/zoom/2)"
    return (f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={fps}")


def compose_video(
    slides: List[Dict],
    script_pages: List[str],
    audio_paths: List[str],
    durations: List[float],
    out_dir: str | Path,
    project_id: str,
    resolution: str = "1080p",
    fps: int = 30,
    transition: float = 0.5,
    subtitle: bool = True,
    progress=None,
    pptx_path: str | Path | None = None,
    follow_transition: bool = False,
    theme: dict | None = None,
    effects: bool = False,
    bgm: bool = True,
) -> Dict:
    """合成最终 MP4。返回 {video_path, srt_path, duration, pages, engine}。

    - pptx_path 存在时优先用 PowerPoint/WPS/LibreOffice 渲染原始 PPT 页面；
      失败回退内置文字版式。
    - follow_transition=True 时按 PPT 自带的切换动效处理转场
      （硬切→无转场；其他动效→按其时长淡入淡出近似）。
    """
    rep = progress or (lambda r, m: None)
    out = Path(out_dir)
    tmp = out / "tmp"
    (tmp / "png").mkdir(parents=True, exist_ok=True)
    (tmp / "seg").mkdir(parents=True, exist_ok=True)

    width, height = RES_MAP.get(resolution, RES_MAP["1080p"])

    # 1. 渲染页面：优先原始 PPT 画面
    pngs = None
    transitions: List[Dict] | None = None
    engine = "内置版式"
    if pptx_path:
        rep(0.03, "正在调用 PPT 引擎导出原始页面…")
        from .pptx_render import render_pptx_real

        real = render_pptx_real(pptx_path, tmp / "real")
        if real:
            pngs, transitions, engine = real[0], real[1], real[2]
            rep(0.08, f"已获取原始画面（{engine}，{len(pngs)} 页）")
    if pngs is None:
        rep(0.06, "正在渲染页面画面…")
        pngs = render_slides(slides, tmp / "png", theme=theme, html_timeout=45.0)

    # 2. 字幕 —— 关键：与每页段落的实际时长（配音+0.6s 缓冲）严格一致，
    #    否则字幕随页数累积漂移，出现"解说讲到下一页了字幕还在上一页"
    rep(0.15, "正在生成字幕文件…")
    srt_path = out / f"{project_id}.srt"
    padded = [max(2.0, d + 0.6) for d in durations]
    build_srt(script_pages, padded, srt_path)

    # 3. 每页段落
    rng = random.Random(project_id)  # 同项目每次生成动效一致
    seg_files: List[Path] = []
    td = max(0.0, min(transition, 1.0))
    total = max(1, len(pngs))
    for i, png in enumerate(pngs):
        rep(0.15 + 0.65 * i / total, f"正在合成第 {i + 1}/{total} 页画面与配音…")
        dur = padded[i]
        seg = tmp / "seg" / f"seg_{i:03d}.mp4"
        # 转场时长：跟随 PPT 动效 or 全局；随机动效模式下每页微调
        eff_td = td
        if effects:
            eff_td = min(1.0, max(0.3, rng.uniform(0.35, 0.7)))
        elif follow_transition and transitions and i < len(transitions):
            eff = transitions[i].get("effect", "global")
            if eff == "none":
                eff_td = 0.0
            elif eff not in ("global",):
                eff_td = max(0.0, min(1.5, float(transitions[i].get("duration", td))))
        fade_out_st = max(0.0, dur - eff_td)
        if effects:
            # 随机 Ken Burns 镜头：先放大 2 倍渲染保证 zoompan 平滑不糊
            filters = [f"scale={width * 2}:{height * 2}",
                       _ken_burns_filter(rng.randrange(4), width, height, fps, dur)]
        else:
            filters = [f"scale={width}:{height}"]
        if eff_td > 0:
            fade_in_color = "white" if (effects and rng.random() < 0.3) else "black"
            filters.append(f"fade=t=in:st=0:d={eff_td:.2f}:color={fade_in_color}")
            filters.append(f"fade=t=out:st={fade_out_st:.2f}:d={eff_td:.2f}")
        vf = ",".join(filters)
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(fps), "-i", str(png),
            "-i", audio_paths[i],
            "-vf", vf,
            "-af", "apad",
            "-t", f"{dur:.2f}",
            "-c:v", "libx264", "-preset", "fast", "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            str(seg),
        ]
        if not _run(cmd):
            raise RuntimeError(f"段落 {i} 合成失败（FFmpeg）")
        seg_files.append(seg)

    # 4. concat
    rep(0.82, "正在拼接视频片段…")
    concat_list = tmp / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in seg_files), encoding="utf-8"
    )
    merged = tmp / "merged.mp4"
    if not _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(merged),
    ]):
        raise RuntimeError("视频拼接失败（FFmpeg concat）")

    # 5. 背景音乐（可选）：整片铺一层轻音乐，音量压低不抢解说，结尾淡出
    total_dur = sum(padded)
    if bgm and BGM_PATH.exists():
        rep(0.86, "正在混入背景音乐…")
        fade_st = max(0.0, total_dur - 2.5)
        bgm_mixed = tmp / "bgm_mixed.mp4"
        ok = _run([
            "ffmpeg", "-y", "-i", str(merged),
            "-stream_loop", "-1", "-i", str(BGM_PATH),
            "-filter_complex",
            (f"[1:a]volume=0.16,afade=t=out:st={fade_st:.2f}:d=2.5[bg];"
             f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]"),
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            str(bgm_mixed),
        ], timeout=300)
        if ok and bgm_mixed.exists():
            merged = bgm_mixed

    # 6. 烧录字幕（可选，依赖 libass）
    rep(0.88, "正在处理字幕与最终封装…")
    final = out / f"{project_id}.mp4"
    if subtitle and _has_subtitles_filter():
        srt_escaped = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
        if not _run([
            "ffmpeg", "-y", "-i", str(merged),
            "-vf", f"subtitles={srt_escaped}:force_style='FontSize=16,Outline=1'",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "copy", str(final),
        ], timeout=600):
            shutil.copy(merged, final)
    else:
        shutil.copy(merged, final)

    return {"video_path": str(final), "srt_path": str(srt_path), "duration": total_dur, "pages": len(pngs), "engine": engine}
