"""Non-blocking, bounded FFmpeg screen-recorder session for Groovebox.

Qt owns frame capture. This module owns only a worker thread, bounded queue,
FFmpeg process, and file finalization; it never touches a QWidget or Qt object.
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional


class ScreenRecorderSession:
    """Stream packed RGBA frames to FFmpeg without blocking the Qt event loop.

    `submit_frame` is intentionally non-blocking. When the queue is full it
    discards the oldest not-yet-written frame so capture stays close to live.
    The worker drains accepted frames before closing FFmpeg on `stop()`.
    """

    FORMATS = {"mp4", "mkv", "webm", "gif"}

    def __init__(self, output_path: str, width: int, height: int, *,
                 fps: int = 10, ffmpeg: Optional[str] = None,
                 include_microphone: bool = False, audio_backend: str = "auto",
                 audio_device: str = "default", audio_gain: float = 1.0,
                 queue_depth: int = 4):
        self.output_path = str(Path(output_path).expanduser())
        self.width = int(width)
        self.height = int(height)
        self.fps = max(1, min(30, int(fps)))
        self.format = Path(self.output_path).suffix.lower().lstrip(".")
        if self.format not in self.FORMATS:
            raise ValueError(f"unsupported screen-recording format: {self.format}")
        if self.width < 16 or self.height < 16:
            raise ValueError("screen-recording dimensions must be at least 16×16")
        if self.format != "gif" and (self.width % 2 or self.height % 2):
            raise ValueError("MP4/MKV/WebM recording dimensions must be even")
        self.expected_frame_bytes = self.width * self.height * 4
        self.ffmpeg = str(ffmpeg or shutil.which("ffmpeg") or "")
        if not self.ffmpeg:
            raise FileNotFoundError("FFmpeg was not found; install or provision FFmpeg first")
        self.include_microphone = bool(include_microphone and self.format != "gif")
        self.audio_backend = str(audio_backend or "auto").lower()
        self.audio_device = str(audio_device or "default").strip()[:256] or "default"
        try:
            self.audio_gain = max(0.0, min(4.0, float(audio_gain)))
        except Exception:
            self.audio_gain = 1.0
        self._frames: queue.Queue[bytes] = queue.Queue(maxsize=max(1, min(12, int(queue_depth))))
        self._stop = threading.Event()
        self._done = threading.Event()
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._state = "idle"
        self._message = "Idle"
        self._error = ""
        self._returncode = None
        self._frames_accepted = 0
        self._frames_written = 0
        self._frames_dropped = 0
        self._audio_backend_used = None

    @property
    def state(self):
        with self._lock:
            return self._state

    @property
    def message(self):
        with self._lock:
            return self._message

    @property
    def error(self):
        with self._lock:
            return self._error

    @property
    def frames_dropped(self):
        with self._lock:
            return self._frames_dropped

    def stats(self):
        with self._lock:
            return {
                "state": self._state,
                "message": self._message,
                "error": self._error,
                "returncode": self._returncode,
                "frames_accepted": self._frames_accepted,
                "frames_written": self._frames_written,
                "frames_dropped": self._frames_dropped,
                "audio_backend": self._audio_backend_used,
                "output_path": self.output_path,
            }

    def _set_state(self, state: str, message: str = "", error: str = ""):
        with self._lock:
            self._state = state
            if message:
                self._message = message
            if error:
                self._error = error

    def start(self):
        with self._lock:
            if self._state != "idle":
                raise RuntimeError(f"screen recorder cannot start from state {self._state}")
            self._state = "starting"
            self._message = "Starting FFmpeg…"
        # Directory creation is filesystem work: leave it to the recorder
        # worker so starting capture never stalls the Qt event loop.
        self._thread = threading.Thread(target=self._run, name="groovebox-screen-recorder", daemon=True)
        self._thread.start()
        return self

    def submit_frame(self, rgba: bytes | bytearray | memoryview) -> bool:
        """Accept one tightly packed RGBA frame; never waits for encoder I/O."""
        if self.state != "recording" or self._stop.is_set():
            return False
        try:
            frame = bytes(rgba)
        except Exception:
            with self._lock:
                self._frames_dropped += 1
            return False
        if len(frame) != self.expected_frame_bytes:
            with self._lock:
                self._frames_dropped += 1
                self._error = (self._error + "; " if self._error else "") + (
                    f"bad frame size {len(frame)}; expected {self.expected_frame_bytes}")
            return False
        try:
            self._frames.put_nowait(frame)
        except queue.Full:
            # Prefer the newest picture to a stale backlog. Drop exactly one
            # oldest frame and retry once; if the writer remains saturated, drop
            # the incoming frame rather than blocking the UI.
            try:
                self._frames.get_nowait()
                with self._lock:
                    self._frames_dropped += 1
            except queue.Empty:
                pass
            try:
                self._frames.put_nowait(frame)
            except queue.Full:
                with self._lock:
                    self._frames_dropped += 1
                return False
        with self._lock:
            self._frames_accepted += 1
        return True

    def stop(self):
        """Request a graceful stop; finalization continues on the worker thread."""
        if self.state in ("idle", "finished", "failed"):
            return
        with self._lock:
            if self._state != "stopping":
                self._state = "stopping"
                self._message = "Finishing recording…"
        self._stop.set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for tests/command-line clients; GUI callers should poll `state`."""
        return self._done.wait(timeout)

    def _command(self, audio_backend=None):
        ext = self.format
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
               "-f", "rawvideo", "-pixel_format", "rgba",
               "-video_size", f"{self.width}x{self.height}",
               "-framerate", str(self.fps), "-i", "pipe:0"]
        has_audio = self.include_microphone and audio_backend is not None
        if has_audio:
            cmd += ["-thread_queue_size", "512", "-f", audio_backend, "-i", self.audio_device]
        cmd += ["-map", "0:v:0"]
        if has_audio:
            cmd += ["-map", "1:a:0?"]
        if ext in ("mp4", "mkv"):
            cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                    "-pix_fmt", "yuv420p", "-r", str(self.fps)]
            if ext == "mp4":
                cmd += ["-movflags", "+faststart"]
            if has_audio:
                cmd += ["-af", f"volume={self.audio_gain:.4f}", "-c:a", "aac", "-b:a", "160k", "-shortest"]
        elif ext == "webm":
            cmd += ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8",
                    "-row-mt", "1", "-threads", "2", "-b:v", "0", "-crf", "36",
                    "-pix_fmt", "yuv420p", "-r", str(self.fps)]
            if has_audio:
                cmd += ["-af", f"volume={self.audio_gain:.4f}", "-c:a", "libopus", "-b:a", "96k", "-shortest"]
        else:  # GIF has no microphone stream by design.
            cmd += ["-vf", f"fps={self.fps},scale={self.width}:{self.height}:flags=fast_bilinear",
                    "-loop", "0", "-an"]
        cmd.append(self.output_path)
        return cmd

    @staticmethod
    def _tail_log(log_file):
        try:
            log_file.flush()
            log_file.seek(0, os.SEEK_END)
            size = log_file.tell()
            log_file.seek(max(0, size - 5000))
            return log_file.read().decode("utf-8", errors="replace").strip()[-1200:]
        except Exception:
            return ""

    def _run_one(self, audio_backend):
        log_file = tempfile.TemporaryFile(mode="w+b")
        proc = None
        try:
            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
            cmd = self._command(audio_backend)
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=log_file, bufsize=0)
            # Let FFmpeg initialize demuxers/codecs before exposing the recording
            # state. Startup latency is paid on this worker, never on the UI.
            time.sleep(0.2)
            if proc.poll() is not None:
                return False, proc.returncode, self._tail_log(log_file), None
            self._audio_backend_used = audio_backend
            self._set_state("recording", "Recording")
            write_error = ""
            while True:
                try:
                    frame = self._frames.get(timeout=0.05)
                except queue.Empty:
                    if proc.poll() is not None:
                        write_error = "FFmpeg exited during recording"
                        break
                    if self._stop.is_set():
                        break
                    continue
                try:
                    if proc.poll() is not None:
                        write_error = "FFmpeg exited before all queued frames were written"
                        break
                    if proc.stdin is None:
                        write_error = "FFmpeg video input pipe is unavailable"
                        break
                    proc.stdin.write(frame)
                    with self._lock:
                        self._frames_written += 1
                except (BrokenPipeError, OSError, ValueError) as exc:
                    write_error = f"FFmpeg frame pipe failed: {exc}"
                    break
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                rc = proc.wait(timeout=45)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    rc = proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    rc = proc.wait(timeout=3)
                write_error = write_error or "FFmpeg finalization timed out; process was terminated"
            log_text = self._tail_log(log_file)
            return rc == 0 and not write_error, rc, (write_error + ("; " if write_error and log_text else "") + log_text), proc
        except Exception as exc:
            if proc is not None:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass
            return False, getattr(proc, "returncode", None), str(exc), proc
        finally:
            log_file.close()

    def _run(self):
        try:
            audio_attempts = [None]
            if self.include_microphone:
                if self.audio_backend == "auto":
                    audio_attempts = ["pulse", "alsa"]
                elif self.audio_backend in ("pulse", "alsa"):
                    audio_attempts = [self.audio_backend]
                else:
                    audio_attempts = [self.audio_backend]
            ok = False
            rc = None
            detail = ""
            for index, backend in enumerate(audio_attempts):
                if self._stop.is_set():
                    break
                # If an audio backend fails before recording begins, retry the
                # next Linux input backend. No frames can be submitted yet.
                ok, rc, detail, _proc = self._run_one(backend)
                if ok:
                    break
                if self.state == "recording":
                    break
                if index + 1 < len(audio_attempts):
                    continue
            with self._lock:
                self._returncode = rc
            if ok and os.path.isfile(self.output_path) and os.path.getsize(self.output_path) >= 64:
                suffix = f" · dropped {self._frames_dropped}" if self._frames_dropped else ""
                self._set_state("finished", f"Saved {Path(self.output_path).name}{suffix}")
            else:
                error = detail or "FFmpeg did not produce a valid recording"
                self._set_state("failed", "Recording failed", error)
                try:
                    if os.path.isfile(self.output_path):
                        os.remove(self.output_path)
                except OSError:
                    pass
        except Exception as exc:
            self._set_state("failed", "Recording failed", str(exc))
            try:
                if os.path.isfile(self.output_path):
                    os.remove(self.output_path)
            except OSError:
                pass
        finally:
            self._done.set()
