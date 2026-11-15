"""Bounded 3D-video probe, stereo-layout conversion, transcode and audio mux.

This module handles rendered 3D video assets and frame-preserving post-processing.
It never invokes a shell; all media paths are passed as individual argv entries.
Stereo layout conversions preserve the left/right views. Mono-to-stereo duplication
is opt-in and explicitly documented as 2D duplication, not depth reconstruction.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any


class Media3DError(RuntimeError):
    """Invalid media, unavailable toolchain, or failed media operation."""


_LAYOUTS = {"mono", "sbs", "tb"}
_CODECS = {"libx264"}
_PRESETS = {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"}


def _tool(explicit: str | None, name: str) -> str:
    found = explicit or shutil.which(name)
    if not found:
        raise Media3DError(f"{name} is required for 3D video processing")
    return str(found)


def probe_video(path: str | os.PathLike, *, ffprobe: str | None = None,
                timeout: int = 20) -> dict[str, Any]:
    """Return stable video/audio metadata without decoding the full stream."""
    src = Path(path).expanduser().resolve()
    if not src.is_file():
        raise Media3DError(f"video file does not exist: {src}")
    exe = _tool(ffprobe, "ffprobe")
    cmd = [exe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(src)]
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=max(1, min(120, int(timeout))),
                              check=False)
    except subprocess.TimeoutExpired as exc:
        raise Media3DError("video probe timed out") from exc
    if proc.returncode != 0:
        raise Media3DError(proc.stderr.decode("utf-8", "replace")[-1000:] or "ffprobe failed")
    try:
        data = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Media3DError("ffprobe returned invalid metadata") from exc
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise Media3DError("input contains no video stream")
    fmt = data.get("format", {})
    duration = _float_or_none(video.get("duration")) or _float_or_none(fmt.get("duration"))
    return {
        "path": str(src),
        "container": str(fmt.get("format_name", "unknown")),
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "frame_rate": str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "unknown"),
        "video_codec": str(video.get("codec_name") or "unknown"),
        "pixel_format": str(video.get("pix_fmt") or "unknown"),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "audio_streams": sum(1 for s in streams if s.get("codec_type") == "audio"),
        "streams": len(streams),
    }


def _float_or_none(value):
    try:
        result = float(value)
        return result if result >= 0 else None
    except (TypeError, ValueError):
        return None


def _layout_filter(source: str, target: str, *, width: int, height: int,
                   duplicate_mono: bool) -> str:
    """Convert layout by splitting/scaling individual eyes, never the composite."""
    if source not in _LAYOUTS or target not in _LAYOUTS:
        raise Media3DError("layout must be mono, sbs (side-by-side), or tb (top-bottom)")
    width, height = int(width), int(height)
    if target == "mono":
        eye_w, eye_h = width, height
    elif target == "sbs":
        if width % 4:
            raise Media3DError("side-by-side output width must be divisible by 4")
        eye_w, eye_h = width // 2, height
    else:
        if height % 4:
            raise Media3DError("top-bottom output height must be divisible by 4")
        eye_w, eye_h = width, height // 2
    scale = (f"scale={eye_w}:{eye_h}:force_original_aspect_ratio=decrease:flags=lanczos,"
             f"pad={eye_w}:{eye_h}:(ow-iw)/2:(oh-ih)/2,setsar=1")

    if source == "mono":
        if target == "mono":
            return f"[0:v:0]{scale}[vbase]"
        if not duplicate_mono:
            raise Media3DError("mono input cannot become true stereo; render two camera views or explicitly enable duplicate_mono")
        graph = f"[0:v:0]split=2[left0][right0];[left0]{scale}[left];[right0]{scale}[right];"
    else:
        if target == "mono":
            if source == "sbs":
                return f"[0:v:0]crop=iw/2:ih:0:0,{scale}[vbase]"
            return f"[0:v:0]crop=iw:ih/2:0:0,{scale}[vbase]"
        if source == "sbs":
            split = ("[0:v:0]split=2[a][b];"
                     "[a]crop=iw/2:ih:0:0[left0];"
                     "[b]crop=iw/2:ih:iw/2:0[right0];")
        else:
            split = ("[0:v:0]split=2[a][b];"
                     "[a]crop=iw:ih/2:0:0[left0];"
                     "[b]crop=iw:ih/2:0:ih/2[right0];")
        graph = split + f"[left0]{scale}[left];[right0]{scale}[right];"

    if target == "sbs":
        return graph + "[left][right]hstack=inputs=2,setsar=1[vbase]"
    if target == "tb":
        return graph + "[left][right]vstack=inputs=2,setsar=1[vbase]"
    # Mono is returned above; this is defensive against future layout additions.
    raise Media3DError(f"unsupported stereo layout conversion: {source} -> {target}")


def process_video(source: str | os.PathLike, destination: str | os.PathLike, *,
                  source_layout: str = "mono", output_layout: str | None = None,
                  width: int = 1280, height: int = 720, fps: float = 30.0,
                  start_seconds: float = 0.0, end_seconds: float | None = None,
                  audio_path: str | os.PathLike | None = None,
                  audio_policy: str = "keep", duplicate_mono: bool = False,
                  codec: str = "libx264", preset: str = "medium", crf: int = 18,
                  ffmpeg: str | None = None, ffprobe: str | None = None,
                  timeout: int = 7200) -> dict[str, Any]:
    """Transcode a rendered 3D clip, preserve/convert stereo layout, optionally mux audio.

    ``width``/``height`` are the complete encoded frame dimensions. For SBS the
    per-eye width is half of ``width``; for TB the per-eye height is half of ``height``.
    An external audio file replaces the source audio. The source's audio is kept by
    default, or can be muted with ``audio_policy='mute'``.
    """
    src = Path(source).expanduser().resolve()
    dst = Path(destination).expanduser().resolve()
    if not src.is_file():
        raise Media3DError(f"source video does not exist: {src}")
    if src == dst:
        raise Media3DError("source and destination must be different files")
    if dst.suffix.lower() not in {".mp4", ".m4v", ".mov", ".mkv"}:
        raise Media3DError("destination container must be MP4, M4V, MOV, or MKV")
    layout_out = output_layout or source_layout
    if source_layout not in _LAYOUTS or layout_out not in _LAYOUTS:
        raise Media3DError("unsupported stereo layout")
    width, height = int(width), int(height)
    if width < 320 or height < 180 or width > 7680 or height > 4320:
        raise Media3DError("output dimensions must be between 320x180 and 7680x4320")
    if width % 2 or height % 2:
        raise Media3DError("output dimensions must be even for 4:2:0 encoding")
    if layout_out == "sbs" and width % 4:
        raise Media3DError("side-by-side output width must be divisible by 4")
    if layout_out == "tb" and height % 4:
        raise Media3DError("top-bottom output height must be divisible by 4")
    fps = float(fps)
    if not math.isfinite(fps) or not 1 <= fps <= 120:
        raise Media3DError("frame rate must be finite and between 1 and 120 FPS")
    start = float(start_seconds)
    if not math.isfinite(start) or start < 0:
        raise Media3DError("start_seconds must be finite and nonnegative")
    if end_seconds is not None:
        end_seconds = float(end_seconds)
        if not math.isfinite(end_seconds) or end_seconds <= start:
            raise Media3DError("end_seconds must be finite and after start_seconds")
    if audio_policy not in {"keep", "replace", "mute"}:
        raise Media3DError("audio_policy must be keep, replace, or mute")
    if audio_path is not None and audio_policy == "keep":
        audio_policy = "replace"
    if audio_policy == "replace" and audio_path is None:
        raise Media3DError("replace audio policy requires audio_path")
    if codec not in _CODECS or preset not in _PRESETS or not 0 <= int(crf) <= 35:
        raise Media3DError("unsupported encoder options")
    if layout_out == "sbs" and width < 640:
        raise Media3DError("side-by-side output needs at least 320 pixels per eye")
    if layout_out == "tb" and height < 360:
        raise Media3DError("top-bottom output needs at least 180 pixels per eye")

    meta = probe_video(src, ffprobe=ffprobe)
    if meta["duration"] is not None and start >= meta["duration"]:
        raise Media3DError("trim start is beyond the end of the source video")
    audio_src = Path(audio_path).expanduser().resolve() if audio_path is not None else None
    if audio_src is not None and not audio_src.is_file():
        raise Media3DError(f"audio file does not exist: {audio_src}")

    ff = _tool(ffmpeg, "ffmpeg")
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(f".{dst.stem}.{uuid.uuid4().hex}.part{dst.suffix}")
    filters = [_layout_filter(source_layout, layout_out, width=width, height=height,
                              duplicate_mono=bool(duplicate_mono))]
    filters.append(f"[vbase]fps={fps:.6f},format=yuv420p,setsar=1[vout]")
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
    if audio_src is not None:
        cmd += ["-i", str(audio_src)]
    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if audio_policy == "keep":
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]
    elif audio_policy == "replace":
        cmd += ["-map", "1:a:0?", "-af", "apad", "-c:a", "aac", "-b:a", "192k"]
        cmd += ["-shortest"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", codec, "-preset", preset, "-crf", str(int(crf)),
            "-pix_fmt", "yuv420p"]
    if dst.suffix.lower() in {".mp4", ".m4v", ".mov"}:
        cmd += ["-movflags", "+faststart"]
    if start:
        cmd += ["-ss", f"{start:.6f}"]
    if end_seconds is not None:
        cmd += ["-t", f"{float(end_seconds) - start:.6f}"]
    cmd.append(str(part))
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=max(30, min(43200, int(timeout))),
                              check=False)
        if proc.returncode != 0:
            raise Media3DError(proc.stderr.decode("utf-8", "replace")[-1600:] or "FFmpeg transcode failed")
        if not part.is_file() or part.stat().st_size < 1024:
            raise Media3DError("FFmpeg produced an empty or incomplete output")
        os.replace(part, dst)
    except subprocess.TimeoutExpired as exc:
        raise Media3DError("3D video processing exceeded its time limit") from exc
    finally:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
    out_meta = probe_video(dst, ffprobe=ffprobe)
    return {"output": str(dst), "source": meta, "result": out_meta,
            "source_layout": source_layout, "output_layout": layout_out,
            "audio_policy": audio_policy}
