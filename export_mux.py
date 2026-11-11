"""Lightweight, restartable final mux for parallel Groovebox video exports.

This module deliberately has no Qt or Groovebox import.  It only concatenates
already-rendered .part video files, optionally muxes a pre-rendered audio WAV,
validates the staged output, and atomically publishes it.  Keeping this final
memory peak out of the synthesis worker prevents a second project engine from
competing with FFmpeg while a large MP4 is assembled.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def _tail(path: str, limit: int = 2400) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - limit))
            return f.read().decode("utf-8", "replace").strip()
    except OSError:
        return ""


def _concat_quote(path: str) -> str:
    # FFmpeg concat-demuxer quoting: close quote, escape apostrophe, reopen.
    return "'" + str(Path(path).resolve()).replace("'", "'\\''") + "'"


def _pdeathsig(parent_pid: int):
    """Return a POSIX pre-exec hook so FFmpeg dies if its mux worker is killed."""
    def apply():
        if os.name != "posix":
            return
        try:
            import ctypes
            libc = ctypes.CDLL(None, use_errno=True)
            # Linux PR_SET_PDEATHSIG = 1.  If the parent has already changed,
            # terminate immediately instead of leaving an orphaned encoder.
            libc.prctl(1, int(signal.SIGTERM), 0, 0, 0)
            if os.getppid() != int(parent_pid):
                os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            pass
    return apply


def _run(cmd, timeout: float, log_path: str) -> tuple[int, str]:
    parent_pid = os.getpid()
    kwargs = {}
    if os.name == "posix":
        kwargs["start_new_session"] = True
        kwargs["preexec_fn"] = _pdeathsig(parent_pid)
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=log, close_fds=True, **kwargs)
        try:
            rc = proc.wait(timeout=max(1.0, float(timeout)))
        except subprocess.TimeoutExpired:
            try:
                if os.name == "posix":
                    os.killpg(proc.pid, signal.SIGTERM)
                else:
                    proc.terminate()
            except Exception:
                try: proc.terminate()
                except Exception: pass
            try:
                rc = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    if os.name == "posix": os.killpg(proc.pid, signal.SIGKILL)
                    else: proc.kill()
                except Exception:
                    try: proc.kill()
                    except Exception: pass
                rc = proc.wait(timeout=5)
            return int(rc), "process timed out; " + _tail(log_path)
    return int(rc), _tail(log_path)


def _probe(ffprobe: str, path: str, want_audio: bool) -> tuple[bool, str]:
    if not ffprobe:
        return (os.path.isfile(path) and os.path.getsize(path) > 1024, "ffprobe unavailable")
    cmd = [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height",
           "-of", "json", path]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout or "ffprobe failed")[-1200:]
        data = json.loads(p.stdout or "{}")
        kinds = {str(x.get("codec_type", "")) for x in data.get("streams", [])}
        if "video" not in kinds:
            return False, "no video stream found"
        if want_audio and "audio" not in kinds:
            return False, "audio stream missing from final container"
        return True, "streams verified"
    except Exception as exc:
        return False, f"ffprobe validation error: {type(exc).__name__}: {exc}"


def run(options: dict) -> dict:
    """Assemble one export. Raises on failure and never deletes recoverable parts."""
    o = dict(options or {})
    raw_out = str(o.get("out_file") or "").strip()
    if not raw_out:
        raise ValueError("final video output path is missing")
    out = os.path.abspath(raw_out)
    preset = dict(o.get("preset") or {})
    container = str(o.get("container") or Path(out).suffix.lstrip(".") or "mp4").lower().lstrip(".")
    if container not in ("mp4", "webm", "avi"):
        raise ValueError(f"unsupported final video container: {container}")
    ffmpeg = str(o.get("ffmpeg") or "")
    if not ffmpeg or not os.path.isfile(ffmpeg):
        ffmpeg = shutil.which("ffmpeg") or ""
    if not ffmpeg:
        raise FileNotFoundError("FFmpeg is unavailable to the lightweight mux worker")
    ffprobe = str(o.get("ffprobe") or "")
    if not ffprobe:
        ffprobe = shutil.which("ffprobe") or ""

    n_parts = max(1, min(128, int(preset.get("parts", 1) or 1)))
    directory = os.path.dirname(out) or os.getcwd()
    stem = os.path.splitext(os.path.basename(out))[0]
    part_paths = [os.path.join(directory, f"{stem}.part{i:02d}.{container}") for i in range(n_parts)]
    missing = [p for p in part_paths if not os.path.isfile(p) or os.path.getsize(p) <= 64]
    if missing:
        raise RuntimeError("final mux is waiting for missing/invalid video part(s): " + ", ".join(os.path.basename(x) for x in missing[:12]))

    include_audio = bool(o.get("include_audio", False))
    audio_path = str(o.get("audio_path") or "")
    if include_audio and (not audio_path or not os.path.isfile(audio_path) or os.path.getsize(audio_path) <= 44):
        raise RuntimeError("final mux audio master is missing or empty; video parts were kept")
    integrity = bool(preset.get("integrity", True))
    # Validate the independently committed segments before assembling them. A
    # truncated segment is much cheaper to diagnose here than after a long mux.
    if integrity:
        for part in part_paths:
            ok_part, part_report = _probe(ffprobe, part, False)
            if not ok_part:
                raise RuntimeError(f"video part validation failed ({os.path.basename(part)}): {part_report}")
    master_rms = float(o.get("master_rms", 0.0) or 0.0)
    if include_audio and integrity and master_rms < 1e-4:
        raise RuntimeError("integrity gate: soundtrack is effectively silent; video parts were kept")

    list_path = os.path.join(directory, f".{stem}.concat.part.txt")
    final_tmp = out + ".part"
    log_path = os.path.join(directory, f".{stem}.mux.log.part")
    muxer = {"mp4": "mp4", "webm": "webm", "avi": "avi"}[container]
    provenance = str(o.get("provenance") or "")[:12000].replace("\r", " ").replace("\n", " ")
    acodec = str(o.get("audio_codec") or ("libopus" if container == "webm" else "libmp3lame" if container == "avi" else "aac"))
    abitrate = max(32, min(512, int(o.get("audio_bitrate_kbps", 160) or 160)))
    aargs = ["-b:a", f"{abitrate}k"]

    if not bool(preset.get("stitch", True)):
        # User intentionally requested recoverable part files only. Preserve
        # them, but publish the completed audio master beside them using the
        # normal sidecar name so the export is useful and discoverable.
        sidecar = os.path.join(directory, stem + ".audio.wav") if include_audio else ""
        if include_audio:
            os.replace(audio_path, sidecar)
        result = {"file_path": "", "part_paths": part_paths, "container": container,
                  "part_count": n_parts, "audio": include_audio,
                  "audio_sidecar": sidecar, "validated": True,
                  "validation": "all part streams verified", "finished_at": time.time()}
        meta = str(o.get("out_meta") or "")
        if meta:
            os.makedirs(os.path.dirname(os.path.abspath(meta)), exist_ok=True)
            tmp = meta + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(result, f, sort_keys=True)
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp, meta)
        print("DONE parts-only", flush=True)
        return result

    with open(list_path, "w", encoding="utf-8") as lf:
        for path in part_paths:
            lf.write("file " + _concat_quote(path) + "\n")

    common = [ffmpeg, "-hide_banner", "-y", "-fflags", "+genpts",
              "-f", "concat", "-safe", "0", "-i", list_path]
    if include_audio:
        common += ["-i", audio_path, "-map", "0:v:0", "-map", "1:a:0"]
    else:
        common += ["-map", "0:v:0"]
    duration = float(o.get("duration_s", 0.0) or 0.0)
    if duration > 0.0:
        common += ["-t", f"{duration:.6f}"]
    metadata = ["-metadata", "comment=" + provenance] if provenance else []
    if include_audio:
        cmd = common + ["-c:v", "copy", "-c:a", acodec, *aargs,
                        *metadata, "-shortest", "-f", muxer, final_tmp]
    else:
        cmd = common + ["-c:v", "copy", "-an", *metadata, "-f", muxer, final_tmp]
    print("PROGRESS 96 final mux", flush=True)
    rc, detail = _run(cmd, float(o.get("timeout_s", 7200)), log_path)
    if rc != 0:
        # Re-encode only the final concatenation when stream-copy fails. Force a
        # single codec thread so this recovery path remains memory-bounded.
        vcodec = str(o.get("video_codec") or ("libvpx-vp9" if container == "webm" else "mpeg4" if container == "avi" else "libx264"))
        v_args = list(o.get("video_args") or [])
        v_args = [str(x) for x in v_args]
        # Don't let a preset's thread flag defeat the isolated mux resource cap.
        filtered = []
        skip = False
        for value in v_args:
            if skip:
                skip = False; continue
            if value == "-threads":
                skip = True; continue
            filtered.append(value)
        if vcodec == "libx264":
            # Remove the dialog's potentially expensive preset and use a
            # bounded recovery encode. Preserve its quality/pixel-format flags.
            normalized = []
            skip = False
            for value in filtered:
                if skip:
                    skip = False
                    continue
                if value == "-preset":
                    skip = True
                    continue
                normalized.append(value)
            filtered = normalized + ["-preset", "ultrafast"]
        fallback = common + ["-c:v", vcodec, *filtered, "-threads", "1"]
        if include_audio:
            fallback += ["-c:a", acodec, *aargs, *metadata, "-shortest", "-f", muxer, final_tmp]
        else:
            fallback += ["-an", *metadata, "-f", muxer, final_tmp]
        rc2, detail2 = _run(fallback, float(o.get("timeout_s", 7200)), log_path)
        if rc2 != 0:
            try: os.remove(final_tmp)
            except OSError: pass
            raise RuntimeError("final mux failed; recoverable video/audio parts were retained. "
                               f"copy attempt rc={rc}; fallback rc={rc2}; {detail2 or detail}")

    if not os.path.isfile(final_tmp) or os.path.getsize(final_tmp) <= 1024:
        raise RuntimeError("final mux created an empty/undersized file; recoverable parts were retained")
    valid, report = _probe(ffprobe, final_tmp, include_audio)
    if integrity and not valid:
        raise RuntimeError("final mux validation failed; recoverable parts were retained: " + report)
    os.replace(final_tmp, out)

    # Preserve the independently generated master as the canonical sidecar;
    # the final container has its own encoded audio stream as well.
    audio_sidecar = ""
    if include_audio:
        audio_sidecar = os.path.join(directory, stem + ".audio.wav")
        try:
            os.replace(audio_path, audio_sidecar)
        except OSError:
            # The MP4 is already validated and published. Keep the staged WAV
            # at its original path rather than converting a sidecar failure
            # into a false report that the final export itself failed.
            audio_sidecar = audio_path

    # Only discard video recovery inputs after the destination is validated
    # and atomically published. Any failure above leaves every .part file.
    for path in part_paths:
        try: os.remove(path)
        except OSError: pass
    try: os.remove(list_path)
    except OSError: pass
    try: os.remove(log_path)
    except OSError: pass
    result = {"file_path": out, "container": container, "part_count": n_parts,
              "size_bytes": int(os.path.getsize(out)), "audio": include_audio,
              "audio_sidecar": audio_sidecar,
              "validated": bool(valid), "validation": report, "finished_at": time.time()}
    meta = str(o.get("out_meta") or "")
    if meta:
        os.makedirs(os.path.dirname(os.path.abspath(meta)), exist_ok=True)
        tmp = meta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, sort_keys=True)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, meta)
    print("DONE " + out, flush=True)
    return result
