#!/usr/bin/env python3
"""
Groovebox Format Converter (R28.4.9 companion tool)
---------------------------------------------------
Lightweight, FFmpeg-backed media format converter for audio, video, and
image files. Intended as a practical utility alongside the main Groovebox
composition / export pipeline.

Does NOT replace the canonical audio renderer, sidechain, or export path.
It simply makes common container/codec conversions convenient for users
who already have FFmpeg available (or can fetch it via get_ffmpeg_linux.sh).

Usage examples:
  python format_converter.py input.wav -o output.mp3
  python format_converter.py input.mp4 -o output.webm --video-codec libvpx-vp9
  python format_converter.py photo.png -o photo.jpg --quality 85
  python format_converter.py --list-formats

Requires ffmpeg / ffprobe on PATH (or in ./bin relative to this script).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# FFmpeg discovery
# ---------------------------------------------------------------------------

def find_ffmpeg(exit_on_missing: bool = True) -> Tuple[str, str]:
    """Return (ffmpeg, ffprobe) paths. Prefer local bin/ then PATH. Library callers pass exit_on_missing=False and
    get a RuntimeError instead of the process exiting."""
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "bin",
        script_dir.parent / "bin",
        Path.cwd() / "bin",
    ]
    for d in candidates:
        ff = d / "ffmpeg"
        fp = d / "ffprobe"
        if ff.is_file() and os.access(ff, os.X_OK):
            return str(ff), str(fp) if fp.is_file() else "ffprobe"
    # Fall back to PATH
    ff = __import__("sos_tools").which("ffmpeg")
    fp = __import__("sos_tools").which("ffprobe")
    if not ff and not exit_on_missing:
        raise RuntimeError("ffmpeg not found (install ffmpeg or run get_ffmpeg_linux.sh)")
    if not ff:
        print(
            "ERROR: ffmpeg not found.\n"
            "  • Run get_ffmpeg_linux.sh (or equivalent) to install a local copy, or\n"
            "  • Ensure ffmpeg is on your PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    return ff, fp or "ffprobe"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMMON_AUDIO = {
    "mp3":  ["-c:a", "libmp3lame", "-q:a", "2"],
    "wav":  ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "ogg":  ["-c:a", "libvorbis", "-q:a", "5"],
    "opus": ["-c:a", "libopus", "-b:a", "128k"],
    "aac":  ["-c:a", "aac", "-b:a", "192k"],
    "m4a":  ["-c:a", "aac", "-b:a", "192k"],
    "aiff": ["-c:a", "pcm_s16be"],
    "aif":  ["-c:a", "pcm_s16be"],
    "caf":  ["-c:a", "pcm_s24le"],
    "w64":  ["-c:a", "pcm_s24le"],
    "mka":  ["-c:a", "flac"],
    "ac3":  ["-c:a", "ac3", "-b:a", "384k"],
    "wv":   ["-c:a", "wavpack"],
    "alac": ["-c:a", "alac"],
}

COMMON_VIDEO = {
    "mp4":  ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus", "-b:a", "128k"],
    "mkv":  ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac"],
    "mov":  ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac"],
    "avi":  ["-c:v", "libx264", "-c:a", "mp3"],
    "m4v":  ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac"],
    "ts":   ["-c:v", "libx264", "-c:a", "aac", "-f", "mpegts"],
    "mpg":  ["-c:v", "mpeg2video", "-q:v", "4", "-c:a", "mp2"],
    "ogv":  ["-c:v", "libtheora", "-q:v", "7", "-c:a", "libvorbis"],
    "flv":  ["-c:v", "libx264", "-c:a", "aac"],
    "3gp":  ["-c:v", "libx264", "-profile:v", "baseline", "-c:a", "aac", "-ar", "44100"],
}

COMMON_IMAGE = {
    "jpg":  ["-q:v", "2"],
    "jpeg": ["-q:v", "2"],
    "png":  [],
    "webp": ["-quality", "85"],
    "bmp":  [],
    "tiff": [],
    "tif":  [],
    "tga":  [],
    "ico":  ["-vf", "scale=256:-1"],
    "gif":  ["-vf", "fps=12,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", "-loop", "0"],
}


def make_background_gif(src, dst=None, width=640, fps=12, seconds=8.0, start=0.0):
    """Any video / animated image / still image / folder of frames → a looping GIF sized for window backgrounds.
    ffmpeg two-pass palette (good colour, small file); Pillow fallback for stills and frame folders."""
    src = Path(str(src))
    if dst is None:
        base = Path(os.path.expanduser("~")) / "Pictures" / "Groovebox Backgrounds"
        base.mkdir(parents=True, exist_ok=True)
        dst = base / (src.stem + "_bg.gif")
    dst = Path(str(dst))
    width, fps, seconds = max(64, int(width)), max(1, min(30, int(fps))), max(0.5, float(seconds))
    if src.is_dir():
        frames = sorted(p for p in src.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".webp"))
        return _pil_gif([str(p) for p in frames[: int(fps * seconds)]], dst, width, fps)
    try:
        ff, _fp = find_ffmpeg(exit_on_missing=False)
    except RuntimeError:
        return _pil_gif([str(src)], dst, width, fps)
    vf = "fps=%d,scale=%d:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer" % (fps, width)
    cmd = [ff, "-y", "-ss", "%.3f" % float(start), "-t", "%.3f" % seconds, "-i", str(src), "-vf", vf, "-loop", "0", str(dst)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return str(dst)


def _pil_gif(paths, dst, width, fps):
    from PIL import Image
    frames = []
    for p in paths:
        im = Image.open(p)
        try:
            n = getattr(im, "n_frames", 1)
        except Exception:
            n = 1
        for i in range(n):
            im.seek(i)
            fr = im.convert("RGB")
            fr = fr.resize((width, max(1, int(fr.height * width / max(1, fr.width)))))
            frames.append(fr.convert("P", palette=Image.Palette.ADAPTIVE, colors=255))
    if not frames:
        raise ValueError("no frames to write")
    frames[0].save(str(dst), save_all=True, append_images=frames[1:], loop=0, duration=int(1000 / max(1, fps)))
    return str(dst)


def make_background_gif_dialog(parent=None):
    """File Converter → 🎞 GIF background: choose a video / image / frame folder, write a looping GIF, return its path."""
    from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
    src, _f = QFileDialog.getOpenFileName(parent, "Make a GIF from…", os.path.expanduser("~"),
                                          "Video or image (*.mp4 *.mkv *.webm *.mov *.avi *.m4v *.gif *.webp *.png *.jpg *.jpeg);;All files (*)")
    if not src:
        return None
    secs, ok = QInputDialog.getDouble(parent, "GIF length", "Seconds (from the start):", 8.0, 0.5, 60.0, 1)
    if not ok:
        return None
    try:
        out = make_background_gif(src, seconds=secs)
    except Exception as exc:
        QMessageBox.warning(parent, "GIF", "Could not make the GIF: %s" % exc)
        return None
    QMessageBox.information(parent, "GIF", "Saved " + out)
    return out


def probe(path: str, ffprobe: str) -> str:
    try:
        out = subprocess.check_output(
            [ffprobe, "-v", "error", "-show_entries", "format=format_name",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            text=True, stderr=subprocess.STDOUT,
        ).strip()
        return out or "unknown"
    except Exception:
        return "unknown"


def build_cmd(
    ffmpeg: str,
    src: Path,
    dst: Path,
    video_codec: Optional[str],
    audio_codec: Optional[str],
    quality: Optional[int],
    extra: List[str],
) -> List[str]:
    ext = dst.suffix.lstrip(".").lower()
    cmd = [ffmpeg, "-y", "-i", str(src)]

    if ext in COMMON_AUDIO and not video_codec:
        cmd += COMMON_AUDIO[ext]
    elif ext in COMMON_VIDEO:
        if video_codec:
            cmd += ["-c:v", video_codec]
        else:
            cmd += COMMON_VIDEO[ext]
        if audio_codec:
            # replace default audio if user overrode
            cmd = [c for c in cmd if c not in ("-c:a", "aac", "libopus", "mp3", "libvorbis")]
            cmd += ["-c:a", audio_codec]
    elif ext in COMMON_IMAGE:
        cmd += COMMON_IMAGE[ext]
        if quality is not None and ext in ("jpg", "jpeg", "webp"):
            if ext in ("jpg", "jpeg"):
                # FFmpeg -q:v 1-31 (lower = better); map 1-100 roughly
                q = max(1, min(31, int(31 - (quality / 100) * 30)))
                cmd = [c for c in cmd if c != "-q:v"]
                cmd += ["-q:v", str(q)]
            else:
                cmd += ["-quality", str(quality)]
    else:
        # generic copy / re-mux attempt
        cmd += ["-c", "copy"]

    if extra:
        cmd += extra
    cmd.append(str(dst))
    return cmd


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Groovebox Format Converter – FFmpeg-backed media conversion helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", nargs="?", help="Source file")
    parser.add_argument("-o", "--output", help="Destination file (extension selects format)")
    parser.add_argument("--video-codec", help="Override video codec (e.g. libx264, libvpx-vp9)")
    parser.add_argument("--audio-codec", help="Override audio codec (e.g. aac, libmp3lame)")
    parser.add_argument("--quality", type=int, help="Quality hint 1-100 (images / some codecs)")
    parser.add_argument("--extra", nargs="*", default=[], help="Extra raw ffmpeg arguments")
    parser.add_argument("--list-formats", action="store_true", help="Show built-in format presets")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Print the ffmpeg command only")
    args = parser.parse_args()

    if args.list_formats:
        print("Built-in audio presets :", ", ".join(sorted(COMMON_AUDIO)))
        print("Built-in video presets :", ", ".join(sorted(COMMON_VIDEO)))
        print("Built-in image presets :", ", ".join(sorted(COMMON_IMAGE)))
        return 0

    if not args.input or not args.output:
        parser.error("input and -o/--output are required (or use --list-formats)")

    src = Path(args.input).expanduser().resolve()
    dst = Path(args.output).expanduser().resolve()
    if not src.is_file():
        print(f"ERROR: input file not found: {src}", file=sys.stderr)
        return 1

    ffmpeg, ffprobe = find_ffmpeg()
    print(f"Source format (probe): {probe(str(src), ffprobe)}")
    print(f"Target              : {dst}  (ext={dst.suffix})")

    cmd = build_cmd(
        ffmpeg, src, dst,
        args.video_codec, args.audio_codec, args.quality, args.extra,
    )
    print("Command:", " ".join(cmd))

    if args.dry_run:
        return 0

    try:
        subprocess.check_call(cmd)
        print(f"Wrote: {dst}")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg failed with exit code {e.returncode}", file=sys.stderr)
        return e.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
