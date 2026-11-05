"""Live camera + microphone streaming between Grooveboxes.

GROOVEBOX_R23R_LIVE_AV_20261101

One FFmpeg process captures the local camera and/or microphone and encodes a
low-latency MPEG-TS stream (H.264 + AAC; MPEG-4 + MP2 when x264 is missing).
The bytes are fanned out to every viewer by the Nearby share server at
/api/v1/live, so it works over the same LAN / Wi-Fi / ad hoc / Direct / IPv6
links as file sharing. Viewers play the URL; recorders store it with stream
copy (no re-encode). Blocked Grooveboxes are refused by the server.
"""
from __future__ import annotations

import os
import platform
import queue
import re
import shutil
import subprocess
import threading
import time
from typing import Dict, List, Optional

CHUNK = 188 * 64            # whole MPEG-TS packets
# At 1080p/6 Mbit this is ~1.5 seconds of queued transport per viewer.
# A slow viewer is disconnected rather than allowed to build unbounded latency.
MAX_VIEWER_BACKLOG = 96
DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_FPS = 1920, 1080, 30
MAX_WIDTH, MAX_HEIGHT = 3840, 2160


def normalize_video_size(resolution="1080p"):
    """Return a validated (width, height) profile; 1080p is the safe default."""
    if isinstance(resolution, (tuple, list)) and len(resolution) == 2:
        width, height = int(resolution[0]), int(resolution[1])
    else:
        value = str(resolution or "1080p").strip().lower().replace(" ", "")
        aliases = {"720p": (1280, 720), "1080p": (1920, 1080),
                   "1440p": (2560, 1440), "2k": (2560, 1440),
                   "2160p": (3840, 2160), "4k": (3840, 2160)}
        if value in aliases:
            width, height = aliases[value]
        else:
            import re as _re
            match = _re.fullmatch(r"(\d{3,4})x(\d{3,4})", value)
            if not match:
                raise ValueError("resolution must be 720p, 1080p, 1440p, 2160p, or WIDTHxHEIGHT")
            width, height = int(match.group(1)), int(match.group(2))
    if width < 320 or height < 240 or width > MAX_WIDTH or height > MAX_HEIGHT:
        raise ValueError(f"video size must be between 320x240 and {MAX_WIDTH}x{MAX_HEIGHT}")
    if width % 2 or height % 2:
        raise ValueError("H.264 YUV420 video dimensions must be even")
    return width, height


def _clean_bitrate(value, default="6M"):
    raw = str(value or default).strip().upper()
    if not re.fullmatch(r"[1-9]\d{0,2}(K|M)?", raw):
        raise ValueError("video bitrate must look like 6000K or 6M")
    return raw if raw.endswith(("K", "M")) else raw + "K"


def _ffmpeg() -> Optional[str]:
    try:
        from groovebox_media_tools import resolve_local_tool
        p = resolve_local_tool("ffmpeg", False)
        if p:
            return p
    except Exception:
        pass
    return shutil.which("ffmpeg")


def _encoders(ff: str) -> str:
    try:
        return subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return ""


def list_devices() -> Dict[str, List[str]]:
    """Best-effort camera / microphone names for the capture backends FFmpeg uses."""
    ff = _ffmpeg(); sysname = platform.system().lower()
    cams: List[str] = []; mics: List[str] = []
    if sysname == "linux":
        import glob
        cams = sorted(glob.glob("/dev/video*"))
        mics = ["default"]
    elif sysname == "windows" and ff:
        try:
            out = subprocess.run([ff, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                                 capture_output=True, text=True, timeout=10).stderr
            for ln in out.splitlines():
                m = re.search(r'"([^"]+)"\s+\((video|audio)\)', ln)
                if m:
                    (cams if m.group(2) == "video" else mics).append(m.group(1))
        except Exception:
            pass
    elif sysname == "darwin" and ff:
        try:
            out = subprocess.run([ff, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                                 capture_output=True, text=True, timeout=10).stderr
            section = None
            for ln in out.splitlines():
                if "video devices" in ln.lower():
                    section = "v"; continue
                if "audio devices" in ln.lower():
                    section = "a"; continue
                m = re.search(r"\[(\d+)\]\s+(.+)$", ln)
                if m and section:
                    (cams if section == "v" else mics).append(f"{m.group(1)}:{m.group(2).strip()}")
        except Exception:
            pass
    return {"cameras": cams, "microphones": mics}


class LiveBroadcaster:
    """Owns the capture/encode process and the viewer fan-out."""

    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.viewers: List[queue.Queue] = []
        self.lock = threading.Lock()
        self.mode = ""
        self.started = 0.0
        self.error = ""
        self._reader = None
        self._err_tail: List[str] = []
        self.profile = {"width": DEFAULT_WIDTH, "height": DEFAULT_HEIGHT,
                        "fps": DEFAULT_FPS, "video_bitrate": "6M", "encoder": "libx264"}
        self.viewer_drops = 0
        self.bytes_out = 0

    @property
    def live(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def status(self) -> Dict:
        with self.lock:
            viewers = len(self.viewers)
        return {"live": self.live, "mode": self.mode, "since": self.started, "viewers": viewers,
                "error": self.error, "profile": dict(self.profile),
                "viewer_drops": int(self.viewer_drops), "bytes_out": int(self.bytes_out)}

    def _input_args(self, video: bool, audio: bool, camera: str, mic: str, test: bool,
                    width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT,
                    fps: int = DEFAULT_FPS) -> List[str]:
        sysname = platform.system().lower(); args: List[str] = []
        size = f"{int(width)}x{int(height)}"
        if test:
            if video:
                args += ["-re", "-thread_queue_size", "256", "-f", "lavfi", "-i",
                         f"testsrc2=size={size}:rate={int(fps)}"]
            if audio:
                args += ["-re", "-thread_queue_size", "256", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
            return args
        if sysname == "linux":
            if video:
                args += ["-thread_queue_size", "256", "-f", "v4l2", "-framerate", str(int(fps)),
                         "-video_size", size, "-i", camera or "/dev/video0"]
            if audio:
                args += ["-thread_queue_size", "256"]
                if shutil.which("pactl") or os.environ.get("PULSE_SERVER") or os.environ.get("PIPEWIRE_RUNTIME_DIR"):
                    args += ["-f", "pulse", "-i", mic or "default"]
                else:
                    args += ["-f", "alsa", "-i", mic or "default"]
        elif sysname == "windows":
            devs = list_devices()
            cam = camera or (devs["cameras"][0] if devs["cameras"] else "")
            m = mic or (devs["microphones"][0] if devs["microphones"] else "")
            spec = []
            if video and cam:
                spec.append(f"video={cam}")
            if audio and m:
                spec.append(f"audio={m}")
            if not spec:
                raise RuntimeError("no camera/microphone found (DirectShow)")
            args += ["-thread_queue_size", "256", "-f", "dshow", "-rtbufsize", "128M"]
            if video:
                args += ["-framerate", str(int(fps)), "-video_size", size]
            args += ["-i", ":".join(spec)]
        elif sysname == "darwin":
            v = (camera.split(":")[0] if camera else "0") if video else "none"
            a = (mic.split(":")[0] if mic else "0") if audio else "none"
            args += ["-thread_queue_size", "256", "-f", "avfoundation"]
            if video:
                args += ["-framerate", str(int(fps)), "-video_size", size]
            args += ["-i", f"{v}:{a}"]
        else:
            raise RuntimeError("live capture is not implemented for this OS")
        return args

    def start(self, video=True, audio=True, camera="", mic="", test=False, *,
              resolution="1080p", fps=30, video_bitrate="6M", encoder="auto") -> Dict:
        if self.live:
            return self.status()
        if not (video or audio):
            raise ValueError("choose camera and/or microphone")
        ff = _ffmpeg()
        if not ff:
            raise RuntimeError("Groovebox-local FFmpeg is not available")
        width, height = normalize_video_size(resolution)
        fps = max(1, min(60, int(fps)))
        bitrate = _clean_bitrate(video_bitrate)
        enc = _encoders(ff)
        enc_names = set(re.findall(r"\b(h264_[a-z0-9_]+|libx264|mpeg4)\b", enc))
        requested_encoder = str(encoder or "auto").strip().lower()
        encoder_aliases = {"software": "libx264", "x264": "libx264", "qsv": "h264_qsv",
                           "nvenc": "h264_nvenc", "videotoolbox": "h264_videotoolbox"}
        requested_encoder = encoder_aliases.get(requested_encoder, requested_encoder)
        if requested_encoder == "auto":
            # Prefer broadly available software H.264 for predictable startup;
            # hardware encoders are selectable when the local FFmpeg exposes them.
            selected_encoder = "libx264" if "libx264" in enc_names else ("mpeg4" if "mpeg4" in enc_names else "")
        else:
            selected_encoder = requested_encoder
        if video and selected_encoder not in enc_names:
            raise RuntimeError(f"FFmpeg encoder {selected_encoder or requested_encoder!r} is not available")
        gop = max(1, fps * 2)
        if selected_encoder == "libx264":
            vcodec = ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                      "-threads", str(max(1, min(4, (os.cpu_count() or 4) // 2))),
                      "-g", str(gop), "-keyint_min", str(gop), "-b:v", bitrate,
                      "-maxrate", bitrate, "-bufsize", bitrate, "-pix_fmt", "yuv420p"]
        elif selected_encoder == "h264_qsv":
            vcodec = ["-c:v", selected_encoder, "-preset", "veryfast", "-b:v", bitrate,
                      "-maxrate", bitrate, "-bufsize", bitrate, "-g", str(gop), "-pix_fmt", "nv12"]
        elif selected_encoder == "h264_nvenc":
            vcodec = ["-c:v", selected_encoder, "-preset", "p2", "-tune", "ull", "-b:v", bitrate,
                      "-maxrate", bitrate, "-bufsize", bitrate, "-g", str(gop), "-pix_fmt", "yuv420p"]
        elif selected_encoder == "h264_videotoolbox":
            vcodec = ["-c:v", selected_encoder, "-realtime", "1", "-b:v", bitrate,
                      "-maxrate", bitrate, "-bufsize", bitrate, "-g", str(gop), "-pix_fmt", "yuv420p"]
        elif selected_encoder == "h264_amf":
            vcodec = ["-c:v", selected_encoder, "-quality", "speed", "-b:v", bitrate,
                      "-maxrate", bitrate, "-bufsize", bitrate, "-g", str(gop), "-pix_fmt", "yuv420p"]
        elif selected_encoder == "mpeg4":
            vcodec = ["-c:v", "mpeg4", "-q:v", "4", "-g", str(gop), "-pix_fmt", "yuv420p"]
        else:
            raise RuntimeError(f"Unsupported live video encoder: {selected_encoder}")
        acodec = (["-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"] if " aac " in enc
                  else ["-c:a", "mp2", "-b:a", "192k", "-ar", "48000", "-ac", "2"])
        cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-fflags", "nobuffer"]
        cmd += self._input_args(video, audio, camera, mic, test, width, height, fps)
        if video:
            vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                  f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}")
            cmd += ["-vf", vf, "-fps_mode", "cfr"] + vcodec
        else:
            cmd += ["-vn"]
        if audio:
            cmd += acodec
        else:
            cmd += ["-an"]
        cmd += ["-max_interleave_delta", "0", "-flush_packets", "1", "-f", "mpegts",
                "-muxdelay", "0.05", "-muxpreload", "0", "pipe:1"]
        self.profile = {"width": width if video else 0, "height": height if video else 0,
                        "fps": fps if video else 0, "video_bitrate": bitrate if video else "off",
                        "encoder": selected_encoder if video else "off"}
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        self.error = ""; self._err_tail = []
        self.viewer_drops = 0; self.bytes_out = 0
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
        self.mode = ("test pattern " if test else "") + "+".join(x for x, on in (("camera", video), ("mic", audio)) if on)
        self.started = time.time()
        self._reader = threading.Thread(target=self._pump, daemon=True, name="groovebox-live-pump"); self._reader.start()
        threading.Thread(target=self._stderr, daemon=True, name="groovebox-live-err").start()
        time.sleep(0.6)
        if not self.live:
            self.error = " ".join(self._err_tail)[-600:] or "capture device could not be opened"
            raise RuntimeError(self.error)
        return self.status()

    def _stderr(self):
        p = self.proc
        try:
            for ln in iter(p.stderr.readline, b""):
                self._err_tail = (self._err_tail + [ln.decode("utf-8", "replace").strip()])[-8:]
        except Exception:
            pass

    def _pump(self):
        p = self.proc
        try:
            while True:
                b = p.stdout.read(CHUNK)
                if not b:
                    break
                self.bytes_out += len(b)
                with self.lock:
                    viewers = list(self.viewers)
                for q in viewers:
                    try:
                        q.put_nowait(b)
                    except queue.Full:
                        self.viewer_drops += 1
                        self.remove_viewer(q)       # too slow: drop rather than stall everyone
        except Exception:
            pass
        with self.lock:
            for q in self.viewers:
                try:
                    q.put_nowait(None)
                except Exception:
                    pass

    def add_viewer(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=MAX_VIEWER_BACKLOG)
        with self.lock:
            self.viewers.append(q)
        return q

    def remove_viewer(self, q):
        with self.lock:
            if q in self.viewers:
                self.viewers.remove(q)
        try:
            q.put_nowait(None)
        except Exception:
            pass

    def stop(self):
        p, self.proc = self.proc, None
        if p is not None:
            try:
                p.terminate(); p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self.mode = ""


class StreamRecorder:
    """Record a live URL (any Groovebox, including this one) to .mkv by stream copy."""

    def __init__(self, url: str, out_path: str):
        self.url = url; self.out = out_path; self.proc = None

    def start(self):
        ff = _ffmpeg()
        if not ff:
            raise RuntimeError("Groovebox-local FFmpeg is not available")
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        self.proc = subprocess.Popen([ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", self.url,
                                      "-map", "0", "-c", "copy", self.out],
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        return self.out

    @property
    def active(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        p, self.proc = self.proc, None
        if p is None:
            return self.out
        try:
            p.stdin.write(b"q"); p.stdin.flush()      # graceful: finalises the container
            p.wait(timeout=6)
        except Exception:
            try:
                p.terminate(); p.wait(timeout=3)
            except Exception:
                pass
        return self.out
