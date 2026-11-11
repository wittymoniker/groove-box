"""cam_mic_recorder.py — GROOVEBOX_R32_CAM_MIC_RECORDER_20261110

One-button camera + microphone take (used by the Clip Editor "⏺ New Cam/Mic recording" button
and available to any tool).  FFmpeg captures straight to disk (no Python frame handling, so the
GUI never stalls); stop sends "q" so the file is finalised cleanly, and the finished file is
handed back to the caller (the Clip Editor drops it on the timeline).

Inputs per OS:  Linux v4l2 + PulseAudio/PipeWire (ALSA fallback) · Windows dshow · macOS avfoundation.
Modes: "cam+mic", "cam", "mic".  Uses the camera chosen in Hardware (preferred_camera_format).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time


def _ffmpeg(host):
    try:
        ff = host._resolve_ffmpeg_binary()
        if ff:
            return ff
    except Exception:
        pass
    return shutil.which("ffmpeg")


def _camera(host):
    cam = str((getattr(host, "preferred_camera_format", None) or {}).get("device_path", "") or "")
    if sys.platform.startswith("linux"):
        if not cam:
            for i in range(8):
                if os.path.exists("/dev/video%d" % i):
                    cam = "/dev/video%d" % i; break
        return cam or None
    return cam or None


def build_cmd(host, out_path, mode="cam+mic"):
    ff = _ffmpeg(host)
    if not ff:
        raise RuntimeError("recording needs ffmpeg")
    want_v, want_a = "cam" in mode, "mic" in mode
    args = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    if sys.platform.startswith("linux"):
        if want_v:
            cam = _camera(host)
            if not cam:
                raise RuntimeError("no camera found (/dev/video*)")
            args += ["-thread_queue_size", "512", "-f", "v4l2", "-framerate", "30", "-video_size", "1280x720", "-i", cam]
        if want_a:
            if shutil.which("pactl") or os.environ.get("PULSE_SERVER"):
                args += ["-thread_queue_size", "1024", "-f", "pulse", "-i", "default"]
            else:
                args += ["-thread_queue_size", "1024", "-f", "alsa", "-i", "default"]
    elif sys.platform == "win32":
        src = []
        if want_v:
            src.append('video=%s' % (_camera(host) or "Integrated Camera"))
        if want_a:
            src.append('audio=%s' % (os.environ.get("GROOVEBOX_DSHOW_MIC") or "Microphone"))
        args += ["-f", "dshow", "-i", ":".join(src)]
    else:
        args += ["-f", "avfoundation", "-framerate", "30", "-i", "%s:%s" % ("0" if want_v else "none", "0" if want_a else "none")]
    if want_v:
        args += ["-c:v", "mjpeg", "-q:v", "3", "-pix_fmt", "yuvj420p"]
    if want_a:
        args += ["-c:a", "flac", "-ar", "48000"]
    args += [out_path]
    return args


class CamMicRecorder:
    def __init__(self, host, mode="cam+mic", folder=None):
        self.host, self.mode = host, mode
        try:
            d = folder or str(host._exports_dir())
        except Exception:
            import groovebox_paths
            d = groovebox_paths.default_dir("export")
        os.makedirs(d, exist_ok=True)
        ext = ".mkv" if "cam" in mode else ".flac"
        self.path = os.path.join(d, "camrec-%s%s" % (time.strftime("%Y%m%d-%H%M%S"), ext))
        self.proc = None; self.t0 = 0.0; self.error = ""

    def start(self):
        cmd = build_cmd(self.host, self.path, self.mode)
        self._log = open(self.path + ".log", "wb")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self._log)
        self.t0 = time.monotonic()
        return self

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def elapsed(self):
        return time.monotonic() - self.t0 if self.t0 else 0.0

    def stop(self, timeout=10.0):
        """Finalise the file; returns its path or None (error in .error). Blocking: call off the GUI thread."""
        p, self.proc = self.proc, None
        if p is None:
            return None
        try:
            if p.poll() is None:
                p.stdin.write(b"q"); p.stdin.flush(); p.stdin.close()
                p.wait(timeout=timeout)
        except Exception:
            try:
                p.terminate(); p.wait(timeout=3)
            except Exception:
                p.kill()
        try:
            self._log.close()
        except Exception:
            pass
        if os.path.isfile(self.path) and os.path.getsize(self.path) > 1024:
            try:
                os.remove(self.path + ".log")
            except Exception:
                pass
            return self.path
        try:
            with open(self.path + ".log", "rb") as f:
                self.error = f.read().decode(errors="replace").strip()[-300:] or "nothing was recorded"
        except Exception:
            self.error = "nothing was recorded"
        return None
