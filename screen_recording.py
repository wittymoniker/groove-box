"""Non-blocking FFmpeg screen recorder backend.

The GUI captures immutable RGB24 frames (QWidget/QScreen capture must remain on
Qt's UI thread) and submits them to a bounded queue.  This worker owns FFmpeg's
stdin, process lifetime, and final file validation; no pipe writes or waits are
performed by the UI thread.
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional


class ScreenRecorderWorker:
    def __init__(self, command, output_path, *, max_queue=4,
                 on_ready: Optional[Callable[[], None]] = None,
                 on_finished: Optional[Callable[[str, str, int, int], None]] = None):
        self.command = list(command)
        self.output_path = str(output_path)
        self._queue = queue.Queue(maxsize=max(1, int(max_queue)))
        self._stop = threading.Event()
        self._thread = None
        self._process = None
        self._on_ready = on_ready
        self._on_finished = on_finished
        self.frames_written = 0
        self.frames_dropped = 0
        self._error = ""
        self._lock = threading.Lock()

    @property
    def alive(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self):
        if self._thread is not None:
            raise RuntimeError("screen recorder worker already started")
        self._thread = threading.Thread(target=self._run, name="ScreenRecorder-FFmpeg", daemon=True)
        self._thread.start()

    def submit_frame(self, rgb24: bytes) -> bool:
        """Submit one complete immutable RGB24 frame without blocking."""
        if self._stop.is_set() or not isinstance(rgb24, (bytes, bytearray, memoryview)):
            return False
        frame = bytes(rgb24)
        try:
            self._queue.put_nowait(frame)
            return True
        except queue.Full:
            # Drop the oldest queued frame to keep capture close to live time.
            try:
                self._queue.get_nowait()
                self.frames_dropped += 1
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame)
                return True
            except queue.Full:
                self.frames_dropped += 1
                return False

    def stop(self):
        """Stop accepting frames and let the worker drain its bounded queue."""
        self._stop.set()

    def _run(self):
        err_file = None
        proc = None
        try:
            exe = self.command[0]
            if os.path.sep not in exe and not shutil.which(exe):
                raise FileNotFoundError("FFmpeg was not found; install ffmpeg or configure its executable path")
            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
            err_file = tempfile.TemporaryFile(mode="w+b")
            proc = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL, stderr=err_file,
                                    bufsize=0)
            self._process = proc
            if self._on_ready:
                self._on_ready()
            while True:
                try:
                    frame = self._queue.get(timeout=0.10)
                except queue.Empty:
                    if self._stop.is_set():
                        break
                    if proc.poll() is not None:
                        raise RuntimeError("FFmpeg exited while recording")
                    continue
                if frame is None:
                    break
                if proc.poll() is not None:
                    raise RuntimeError("FFmpeg stopped before the next frame could be written")
                proc.stdin.write(frame)
                self.frames_written += 1
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                return_code = proc.wait(timeout=30.0)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    return_code = proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    return_code = proc.wait(timeout=2.0)
                raise RuntimeError("FFmpeg did not finalize in time; the recorder stopped it")
            if return_code != 0:
                raise RuntimeError(f"FFmpeg exited with status {return_code}")
            if self.frames_written <= 0:
                raise RuntimeError("No screen frames were captured")
            if not os.path.isfile(self.output_path) or os.path.getsize(self.output_path) <= 0:
                raise RuntimeError("FFmpeg finished without producing a non-empty recording")
        except BrokenPipeError:
            self._error = "FFmpeg closed its input unexpectedly"
        except Exception as exc:
            self._error = str(exc)
        finally:
            if proc is not None:
                try:
                    if proc.stdin and not proc.stdin.closed:
                        proc.stdin.close()
                except Exception:
                    pass
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=2.0)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
            if err_file is not None:
                try:
                    err_file.flush()
                    err_file.seek(0)
                    log = err_file.read()[-6000:].decode("utf-8", "replace").strip()
                    if log and self._error:
                        self._error += ": " + log[-1600:]
                except Exception:
                    pass
                try:
                    err_file.close()
                except Exception:
                    pass
            if self._on_finished:
                try:
                    self._on_finished(self.output_path, self._error,
                                      int(self.frames_written), int(self.frames_dropped))
                except Exception:
                    pass


def build_ffmpeg_command(ffmpeg, output_path, width, height, fps, fmt, *, system_audio=False):
    """Build a checked deterministic FFmpeg command for RGB24 screen frames."""
    width, height, fps = int(width), int(height), int(fps)
    if width < 64 or height < 64 or fps not in (10, 15, 20, 24, 30):
        raise ValueError("unsupported screen recorder dimensions or frame rate")
    if width % 2 or height % 2:
        raise ValueError("screen recorder dimensions must be even")
    fmt = str(fmt).lower()
    if fmt not in ("mp4", "mkv", "webm", "gif"):
        raise ValueError("unsupported screen recorder format")
    if system_audio and fmt == "gif":
        raise ValueError("GIF recordings cannot include audio")

    cmd = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
           "-thread_queue_size", "64", "-f", "rawvideo", "-pixel_format", "rgb24",
           "-video_size", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0"]
    if system_audio:
        # This input is supported on the Linux OS build when FFmpeg has
        # libavdevice/PulseAudio enabled. It is only offered by the UI there.
        cmd += ["-thread_queue_size", "512", "-f", "pulse", "-i", "default"]
    if fmt == "gif":
        cmd += ["-filter_complex",
                "[0:v]fps=10,scale=min(960\\,iw):-2:flags=lanczos,split[a][b];"
                "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer",
                "-loop", "0", "-f", "gif", str(output_path)]
    elif fmt == "webm":
        cmd += ["-map", "0:v:0"]
        if system_audio:
            cmd += ["-map", "1:a:0?"]
        cmd += ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8",
                "-row-mt", "1", "-b:v", "2M"]
        if system_audio:
            cmd += ["-c:a", "libopus", "-b:a", "128k", "-shortest"]
        cmd += ["-f", "webm", str(output_path)]
    else:
        cmd += ["-map", "0:v:0"]
        if system_audio:
            cmd += ["-map", "1:a:0?"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                "-crf", "23", "-pix_fmt", "yuv420p"]
        if system_audio:
            cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
        if fmt == "mp4":
            cmd += ["-movflags", "+faststart"]
        cmd += ["-f", "matroska" if fmt == "mkv" else "mp4", str(output_path)]
    return cmd
