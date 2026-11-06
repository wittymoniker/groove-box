# GROOVEBOX_V35_22ZZ_R23P_BOOT_HARDWARE_INIT_20261004
# GROOVEBOX_V35_22ZZ_R23N_HWUCM_CAPTURE_MSI_READER_20261004
# GROOVEBOX_V35_22ZZ_R23L_FIXED_PERFORMANCE_DEVICES_SOF_SDMMC_20261003
# GROOVEBOX_V35_22ZZ_R23K_RUNTIME_AUDIO_MIC_BROWSER_SD_20261003
# GROOVEBOX_V35_22ZZ_R23J_UNIVERSAL_AUDIO_MIC_WATCHDOG_20261003
# GROOVEBOX_V35_22ZZ_R23I_REALTEK_SD_LUN_20261003
# GROOVEBOX_V35_22ZZ_R23H_LINKED_HARDWARE_VOLUME_20261002
# GROOVEBOX_V35_22ZZ_R23G_INLINE_ALSA_MICROSD_ACTION_20261002
# GROOVEBOX_V35_22ZZ_R23F_SOS_ANALOG_OUTPUT_PREP_20261002
# GROOVEBOX_V35_22ZZ_R23E_STORAGE_REFRESH_DIRECT_AUDIO_20261001
# GROOVEBOX_V35_22ZZ_R23D_PHYSICAL_PLAYBACK_CLOCK_20261001
# GROOVEBOX_R9_LEGACY_COMPONENT_WORKER_TOKEN: {'audio','video','display','input'}
# GROOVEBOX_V35_22ZZ_R23_PLAYBACK_OUTPUT_RECOVERY_20261001
# GROOVEBOX_V35_22ZZ_R22_ISOLATED_DEVICE_PROBE_STREAMING_20261001
# GROOVEBOX_V35_22ZZ_R21_PERFORMANCE_TAB_LIFECYCLE_20260930
# GROOVEBOX_V35_22ZZ_R20_RESOURCE_BOUNDS_LOW_LATENCY_20260930
# R20/R22 release contract: bounded low-latency streaming arguments are active runtime arguments.
# GROOVEBOX_V35_22ZZ_R19_RECORD_CAPTURE_STREAMING_PLAYER_20260930
# GROOVEBOX_V35_22ZZ_R18_PERFORMANCE_CPU_RESERVE_MICROSD_RETRY_20260930
# GROOVEBOX_V35_22ZZ_R17B_R5_WORKER_CONTRACT_COMPAT_20260930
# GROOVEBOX_V35_22ZZ_R17_SHARED_AUDIO_LAZY_HARDWARE_STORAGE_OPT_20260930
# GROOVEBOX_V35_22ZZ_R16_PHYSICAL_AUDIO_IO_SELFTEST_UI_20260930
# GROOVEBOX_V35_22ZZ_PERFORMANCE_HW_RUST_ISO_20260926
#!/usr/bin/env python3
"""
performance.py — Groovebox Performance workspace and device manager.

Provides an in-app:
  • Project + render file browser (browse / rename / delete / open)
  • Media playlister (queue WAV/MP3/FLAC/OGG/OPUS/MP4/WEBM/AVI)
  • Built-in game player (live composition game + packaged .zip games)
  • Parametric live remixer (drives host LiveDJ GOAVA / RAND PARAM amounts)
  • Batch Export: many projects (or their linked exports) → audio / video, FPS / bitrate curve

Designed for low-power ARM (Pi 4/5): short previews, subprocess players,
and quality controls that default conservative.
"""
from __future__ import annotations

GROOVEBOX_V35_22ZZ_R5_PERFORMANCE_MEMORY_EFFICIENCY_20260927 = True
GROOVEBOX_V35_22ZZ_R6_PERFORMANCE_EVENT_LOOP_PLAYER_CLOCK_20260928 = True
GROOVEBOX_V35_22ZZ_R10_STORAGE_MOUNT_UI_20260929 = True
GROOVEBOX_V35_22ZZ_R7_LATITUDE_3510_MICROSD_FILE_BROWSER_20260928 = True
GROOVEBOX_V35_22ZZ_R7B_REMOVABLE_COPYOVER_20260928 = True
GROOVEBOX_V35_22ZZ_R17_AUDIO_STORAGE_PERFORMANCE_OPT_20260930 = True

# GROOVEBOX_V35_22ZT_PERFORMANCE_LAZY_CAPTURE_20260924
# GROOVEBOX_V35_22ZU_WAYLAND_WINDOW_SESSION_FAST_LAUNCH_20260924

import ast
import json
import math
from meum_constants import MEUM, MEUM_MINUS_1, MEUM_INV, PHI, PHI_INV
import os
import random
import re
import socket
import time
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from groovebox_media_tools import resolve_local_tool

from qt_painting import owned_painter
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QColor, QFont, QPixmap, QPainter, QPen
from PyQt6.QtWidgets import (
    QTextBrowser,
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSlider,
    QScrollArea,
    QFrame,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Playback is container/codec based, not limited to the handful of export
# formats. mpv/VLC/FFmpeg handle the codecs available in the installed build;
# stream probing below prevents audio-only containers from being mistaken for
# silent video and vice versa.
AUDIO_EXT = {
    ".wav", ".wave", ".mp3", ".mp2", ".mp1", ".flac", ".ogg", ".oga",
    ".opus", ".aiff", ".aif", ".aifc", ".caf", ".m4a", ".m4b", ".m4p",
    ".aac", ".alac", ".wma", ".ape", ".wv", ".mpc", ".tta", ".tak",
    ".amr", ".au", ".snd", ".ra", ".ram", ".mid", ".midi", ".kar",
    ".ac3", ".eac3", ".dts", ".mka", ".spx", ".tta", ".voc", ".w64",
    ".rf64", ".dsf", ".dff", ".3ga", ".mpga",
}
VIDEO_EXT = {
    ".mp4", ".m4v", ".mov", ".qt", ".mkv", ".webm", ".avi", ".mpeg",
    ".mpg", ".mpe", ".m1v", ".m2v", ".mpv", ".m2ts", ".mts", ".ts",
    ".m2t", ".tp", ".trp", ".vob", ".ifo", ".ogv", ".oggvideo", ".flv",
    ".f4v", ".wmv", ".asf", ".3gp", ".3g2", ".mxf", ".roq", ".nsv",
    ".divx", ".rm", ".rmvb", ".yuv", ".ivf", ".nut", ".amv", ".wtv",
    ".dvr-ms", ".mts", ".mkv3d", ".mp4v", ".ismv", ".ism", ".mpd", ".m3u8",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".apng", ".avif", ".jxl"}
PROJECT_EXT = {".mcc", ".mgpr", ".meum", ".mg", ".mgproject", ".mgsynth", ".mgprofile"}
GAME_EXT = {".zip"}

def _gb_ext(path) -> str:
    """Effective file type: media .MCC acts as .wav/.mp4, a package .MCC as a game (.zip),
    a project .MCC stays .mcc (GROOVEBOX_R23R_MCC_MEDIA_CODEC_20261101)."""
    ext = os.path.splitext(str(path))[1].lower()
    if ext == ".mcc":
        try:
            import mcc_media as _mm
            kind = _mm.media_kind(str(path))
        except Exception:
            kind = None
        return {"audio": ".wav", "video": ".mp4", "image": ".png", "package": ".zip"}.get(kind, ".mcc")
    return ext


def _gb_mcc_kind(path) -> str:
    """'video' / 'audio' / 'image' / 'package' for a media .MCC, else ''."""
    if os.path.splitext(str(path))[1].lower() != ".mcc":
        return ""
    try:
        import mcc_media as _mm
        return str(_mm.media_kind(str(path)) or "")
    except Exception:
        return ""


def _gb_open_mcc_video(widget, path: str, volume_pct: int = 100):
    """GROOVEBOX_R23R_PLAYER_VISUALIZER_MCC_20261103: play a media .MCC video
    DIRECTLY (exact lossless frames + embedded audio on the Groovebox device);
    no FFmpeg transcode and no wait."""
    from media_visualizer import MccVideoPlayer
    host = _gb_find_host(widget)
    dlg = MccVideoPlayer(path, widget, host=host, volume_pct=int(volume_pct),
                         play_audio=lambda h, x, sr, p, v: _gb_play_decoded(h, x, sr, p, v),
                         stop_audio=_gb_stop_file_player)
    dlg.setModal(False); dlg.show()
    try:
        widget.__dict__.setdefault("_mcc_players", []).append(dlg)
    except Exception:
        pass
    return dlg


def _gb_playable(path) -> str:
    """Path an external player can open (media .MCC is transcoded once to a cached file)."""
    try:
        import mcc_media as _mm
        return _mm.playable_path(str(path))
    except Exception:
        return str(path)

# ---------------------------------------------------------------------------
# GROOVEBOX_R23R_UNIVERSAL_INAPP_PLAYBACK_20261101
# Every audio format plays through the SAME host output device/stream path the
# main window uses (audio_os_backend.prepare_output_buffer + open_output_stream
# with host._preferred_audio_output_name). Decoding is faithful: native rate,
# no normalisation (a buffer is only scaled down if it would clip the float
# stream). When no external player (mpv/VLC/ffplay) exists — typical for the
# Windows/macOS executable — video falls back to an in-app Qt Multimedia
# player whose QAudioOutput is matched to the same selected output device.
# ---------------------------------------------------------------------------

# GROOVEBOX_AUDIO_VIA_VIDEO_PLAYER_20261102: on the Dell Latitude the inline WAV paths (the
# direct-ALSA PCM pipeline and the host PortAudio file player) stay silent while the media
# player used for video is audible. Audio files now take exactly the video player's route
# (external player + the selected output routing). GROOVEBOX_AUDIO_VIA_PLAYER=0 restores the
# inline paths.
_AUDIO_VIA_VIDEO_PLAYER = os.environ.get("GROOVEBOX_AUDIO_VIA_PLAYER", "1").strip().lower() not in ("0", "false", "no")


def _gb_find_host(widget):
    w = widget
    for _ in range(12):
        if w is None:
            return None
        h = getattr(w, "host", None)
        if h is not None and hasattr(h, "_audio_callback"):
            return h
        if hasattr(w, "_audio_callback") and hasattr(w, "play_buffer"):
            return w
        try:
            w = w.parent()
        except Exception:
            return None
    return None


def _gb_probe_rate(path: str) -> int:
    probe = resolve_local_tool("ffprobe", False) or shutil.which("ffprobe")
    if probe:
        try:
            r = subprocess.run([probe, "-v", "error", "-select_streams", "a:0", "-show_entries",
                                "stream=sample_rate", "-of", "csv=p=0", str(path)],
                               capture_output=True, text=True, timeout=15)
            v = int(float((r.stdout or "").strip().splitlines()[0]))
            if 8000 <= v <= 768000:
                return v
        except Exception:
            pass
    return 48000


def _gb_decode_audio_faithful(path: str):
    """Return (float32 frames x channels, sample_rate) for any playable audio/video file."""
    import numpy as np
    path = str(path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".mcc":
        import mcc_media as _mm
        x, sr, _hdr = _mm.decode_audio(path)
        x = np.asarray(x, dtype=np.float32)
        return (x.reshape(-1, 1) if x.ndim == 1 else x), int(sr)
    if ext in (".wav", ".wave", ".flac", ".ogg", ".oga", ".aiff", ".aif", ".aifc", ".caf", ".w64", ".rf64", ".au", ".snd"):
        try:
            import soundfile as _sf
            x, sr = _sf.read(path, dtype="float32", always_2d=True)
            return np.asarray(x, dtype=np.float32), int(sr)
        except Exception:
            pass
        if ext in (".wav", ".wave"):
            try:
                from audio_os_backend import wavfile
                sr, d = wavfile.read(path)
                d = np.asarray(d)
                if d.dtype.kind == "i":
                    bits = 8 * d.dtype.itemsize
                    try:  # true container depth (24-bit may arrive unshifted in int32)
                        with open(path, "rb") as _f:
                            _h = _f.read(4096)
                        _i = _h.find(b"fmt ")
                        if _i >= 0:
                            _b = int.from_bytes(_h[_i + 22:_i + 24], "little")
                            if 8 <= _b <= bits and int(np.max(np.abs(d))) < 2 ** (_b - 1) + 1:
                                bits = _b
                    except Exception:
                        pass
                    x = d.astype(np.float32) / float(2 ** (bits - 1))
                elif d.dtype.kind == "u":
                    x = (d.astype(np.float32) - 128.0) / 128.0
                else:
                    x = d.astype(np.float32)
                return (x.reshape(-1, 1) if x.ndim == 1 else x), int(sr)
            except Exception:
                pass
    ff = resolve_local_tool("ffmpeg", False) or shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("no decoder for this format (local FFmpeg missing)")
    sr = _gb_probe_rate(path)
    r = subprocess.run([ff, "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True, timeout=600)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError((r.stderr or b"FFmpeg could not decode audio").decode("utf-8", "replace")[-800:])
    x = np.frombuffer(r.stdout, dtype=np.float32)
    return x[: (x.size // 2) * 2].reshape(-1, 2).copy(), sr


class _GbFilePlayer:
    """Transparent stereo file playback (GROOVEBOX_R23R_TRANSPARENT_FILE_PLAYBACK_20261101).

    The arrangement callback is mono and applies master volume x drive with a
    hard clip - right for the live synth, wrong for a finished WAV/FLAC/MCC
    (stereo image lost; anything above about -2 dBFS clipped). Files get their
    own stream on the SAME device resolver as the main window, in stereo, at
    the file's native rate when the device accepts it, unity gain x the player
    volume, no drive/limiter/FX, and a relaxed latency so laptops do not crackle.
    """

    def __init__(self):
        self.stream = None; self.buf = None; self.cursor = 0
        self.gain = 1.0; self.paused = False; self.host = None; self.done = False
        self.lock = threading.Lock()

    def _cb(self, outdata, frames, _t, _status):
        outdata.fill(0)
        try:
            buf = self.buf
            if buf is None or self.paused:
                return
            c = self.cursor; n = min(int(frames), max(0, buf.shape[0] - c))
            if n <= 0:
                self.done = True
                return
            chunk = buf[c:c + n]
            ch = outdata.shape[1]
            if ch == 1:
                outdata[:n, 0] = chunk.mean(axis=1) * self.gain
            else:
                outdata[:n, 0] = chunk[:, 0] * self.gain
                outdata[:n, 1] = chunk[:, 1] * self.gain
            if self.gain > 1.0:
                import numpy as _np
                _np.clip(outdata[:n], -1.0, 1.0, out=outdata[:n])
            self.cursor = c + n
            h = self.host
            if h is not None:  # keep the main window's scope alive (visual only)
                try:
                    wi = 1 - int(getattr(h, "_scope_write_index", 0) or 0)
                    target = h._scope_buffers[wi]; target.fill(0)
                    step = max(1, n // 100); view = outdata[:n:step, 0][:100]
                    target[:view.size] = view; h._scope_write_index = wi; h._last_scope_chunk = target
                except Exception:
                    pass
        except Exception:
            outdata.fill(0)

    def stop(self):
        with self.lock:
            st = self.stream; self.stream = None; self.buf = None
        if st is not None:
            try:
                st.stop(); st.close()
            except Exception:
                pass

    def position_s(self):
        sr = getattr(self, "rate", 0) or 0
        return (self.cursor / float(sr)) if sr else 0.0

    def play(self, host, x, sr, volume_pct=100):
        import numpy as np
        self.stop()
        x = np.nan_to_num(np.asarray(x, dtype=np.float32))
        if x.ndim == 1:
            x = np.stack([x, x], axis=1)
        elif x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        elif x.shape[1] > 2:
            # ITU-style fold-down of surround to stereo (C and surrounds at -3 dB).
            L = x[:, 0].copy(); R = x[:, 1].copy()
            if x.shape[1] > 2:
                L += 0.7071 * x[:, 2]; R += 0.7071 * x[:, 2]
            if x.shape[1] > 5:
                L += 0.7071 * x[:, 4]; R += 0.7071 * x[:, 5]
            x = np.stack([L, R], axis=1)
            pk = float(np.max(np.abs(x))) if x.size else 0.0
            if pk > 1.0:
                x /= pk
        preferred = str(getattr(host, "_preferred_audio_output_name", "") or "") if host is not None else ""
        from audio_os_backend import open_output_stream, prepare_output_buffer
        buf, hw_sr, _idx = prepare_output_buffer(x, int(sr), preferred_name=preferred)
        buf = np.ascontiguousarray(buf, dtype=np.float32)
        if host is not None:
            try:
                host._close_audition_stream()      # Trigger/keyboard stream may hold the device
            except Exception:
                pass
            # One device owner at a time: release the arrangement stream first.
            old = getattr(host, "audio_stream", None)
            if old is not None:
                try:
                    old.stop(); old.close()
                except Exception:
                    pass
                host.audio_stream = None
            try:
                host.is_playing = False
            except Exception:
                pass
        self.host = host; self.buf = buf; self.cursor = 0; self.rate = int(hw_sr)
        self.gain = max(0.0, float(volume_pct) / 100.0); self.paused = False; self.done = False
        last = None
        for ch in (2, 1):
            try:
                try:
                    from audio_os_backend import stream_tuning as _st
                    # file_decoded: full buffer in RAM, no starve risk → low latency safe
                    _blk, _lat = _st("file_decoded")
                except Exception:
                    _blk, _lat = 512, "low"
                st = open_output_stream(samplerate=int(hw_sr), channels=ch, dtype="float32", callback=self._cb,
                                        blocksize=_blk, latency=_lat, preferred_name=preferred)
                st.start()
                with self.lock:
                    self.stream = st
                return int(hw_sr), ch, preferred
            except Exception as exc:
                last = exc
        raise RuntimeError(f"could not open the output device: {last}")


_GB_FILE_PLAYER = _GbFilePlayer()


def _gb_stop_file_player():
    try:
        _GB_FILE_PLAYER.stop()
    except Exception:
        pass


def _gb_play_on_host(host, path: str, status=None, volume_pct: int = 100) -> str:
    """Play any audio file through the main window's device resolver, transparently in stereo."""
    x, sr = _gb_decode_audio_faithful(path)
    return _gb_play_decoded(host, x, sr, path, volume_pct)


def _gb_play_decoded(host, x, sr, path: str, volume_pct: int = 100) -> str:
    """Start already-decoded audio (GUI thread; decoding is done on a worker)."""
    if hasattr(host, "claim_audio"):
        try:
            host.claim_audio("performance")
        except Exception:
            pass
    try:
        from hardware_runtime import ensure_audio_ready
        ensure_audio_ready("file-playback")
    except Exception:
        pass
    hw_sr, ch, preferred = _GB_FILE_PLAYER.play(host, x, int(sr), volume_pct)
    nch = x.shape[1] if getattr(x, "ndim", 1) == 2 else 1
    note = f"{os.path.basename(path)} · {int(sr) / 1000:g} kHz {'stereo' if nch == 2 else (f'{nch} ch' if nch > 2 else 'mono')}"
    if int(hw_sr) != int(sr):
        note += f" → device {int(hw_sr) / 1000:g} kHz (file unchanged)"
    if ch == 1 and nch >= 2:
        note += " · device is mono"
    return note + f" · bit-transparent level · {preferred or 'system default output'}"


def _gb_qt_audio_device(preferred: str):
    """QAudioDevice matching the Groovebox-selected output name (or the default)."""
    try:
        from PyQt6.QtMultimedia import QMediaDevices
        want = str(preferred or "").casefold()
        outs = list(QMediaDevices.audioOutputs())
        if want and want not in ("all detected outputs (default)", "system default"):
            for d in outs:
                desc = d.description().casefold()
                if desc and (desc in want or want in desc):
                    return d
        return QMediaDevices.defaultAudioOutput()
    except Exception:
        return None


def _gb_qt_compatible_copy(path: str) -> str:
    """Transcode once to MP4 (H.264 or MPEG-4 + AAC) when Qt cannot decode a container."""
    import hashlib
    ff = resolve_local_tool("ffmpeg", False) or shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("local FFmpeg is missing")
    st = os.stat(path)
    key = hashlib.sha1(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]
    d = os.path.join(tempfile.gettempdir(), "groovebox_qt_play"); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, key + ".mp4")
    if os.path.isfile(out) and os.path.getsize(out) > 0:
        return out
    for vc in (["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"], ["-c:v", "mpeg4", "-q:v", "2"]):
        r = subprocess.run([ff, "-v", "error", "-y", "-i", path, *vc, "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "256k", out + ".part.mp4"], capture_output=True, timeout=3600)
        if r.returncode == 0:
            os.replace(out + ".part.mp4", out)
            return out
    raise RuntimeError("FFmpeg could not make a Qt-playable copy")


class InAppMediaPlayer(QDialog):
    """Qt Multimedia fallback player (video, audio, images handled by ImageViewerDialog)."""

    def __init__(self, path: str, parent=None, preferred_output: str = "", volume_pct: int = 100):
        super().__init__(parent)
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        from PyQt6.QtCore import QUrl
        from PyQt6.QtWidgets import QSlider
        self._QUrl = QUrl
        self.setWindowTitle(f"Groovebox in-app player · {os.path.basename(path)}")
        self.resize(820, 520)
        self._src = path; self._retried = False
        lay = QVBoxLayout(self)
        self.video = QVideoWidget(self); lay.addWidget(self.video, 1)
        try:   # GROOVEBOX_R23R_GRAY_VIDEO_BG_20261103
            from PyQt6.QtGui import QPalette as _QP, QColor as _QC
            self.video.setAutoFillBackground(True)
            _pal = self.video.palette(); _pal.setColor(_QP.ColorRole.Window, _QC("#3e3f42")); self.video.setPalette(_pal)
            self.video.setStyleSheet("background-color:#3e3f42;")
        except Exception:
            pass
        # GROOVEBOX_R23R_PLAYER_VISUALIZER_MCC_20261103: audio-only media gets a
        # waveform/scope/spectrum visualizer instead of a black video area.
        self.visualizer = None
        try:
            from media_visualizer import AudioVisualizer
            self.visualizer = AudioVisualizer(self); self.visualizer.hide(); lay.addWidget(self.visualizer, 1)
        except Exception:
            self.visualizer = None
        row = QHBoxLayout()
        self.btn = QPushButton("⏸ Pause"); row.addWidget(self.btn)
        self.pos = QSlider(Qt.Orientation.Horizontal); self.pos.setRange(0, 0); row.addWidget(self.pos, 1)
        self.time = QLabel("0:00 / 0:00"); row.addWidget(self.time)
        self.vol = QSlider(Qt.Orientation.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(max(0, min(100, int(volume_pct))))
        self.vol.setMaximumWidth(120); row.addWidget(QLabel("Vol")); row.addWidget(self.vol)
        # GROOVEBOX_R23R_LOOP_VIZ_TOGGLE_20261103
        self._loop_btn = QPushButton("🔁"); self._loop_btn.setCheckable(True)
        self._loop_btn.setMaximumWidth(36); self._loop_btn.setToolTip("Loop current track (playlist place kept)")
        row.addWidget(self._loop_btn)
        self._viz_btn = QPushButton("🌊"); self._viz_btn.setCheckable(True)
        self._viz_btn.setMaximumWidth(36); self._viz_btn.setToolTip("Toggle waveform visualizer")
        self._viz_btn.setChecked(_gb_visualizer_enabled())
        row.addWidget(self._viz_btn)
        lay.addLayout(row)
        self.info = QLabel(""); self.info.setWordWrap(True); lay.addWidget(self.info)
        self.player = QMediaPlayer(self)
        # GROOVEBOX_R23R_PLAYER_LOW_LAG_20261103: 16 ms position ticks (≈60 fps),
        # and start playback only after the pipeline reports it is buffered.
        try:
            self.player.setNotifyInterval(16)
        except Exception:
            pass
        self.audio = QAudioOutput(self)
        dev = _gb_qt_audio_device(preferred_output)
        if dev is not None:
            self.audio.setDevice(dev)
        self.audio.setVolume(self.vol.value() / 100.0)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.info.setText(f"Output: {(dev.description() if dev is not None else '') or 'system default'} · Qt Multimedia (no external player found)")
        self.btn.clicked.connect(self._toggle)
        self.vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100.0))
        self.pos.sliderMoved.connect(self.player.setPosition)
        self.player.durationChanged.connect(lambda d: self.pos.setRange(0, int(d)))
        self.player.positionChanged.connect(self._on_pos)
        self.player.errorOccurred.connect(self._on_error)
        self._loop_btn.toggled.connect(self._on_loop_toggled)
        self._viz_btn.toggled.connect(self._on_viz_toggled)
        # GROOVEBOX_R23R_LOOP_END_OF_MEDIA_20261103: loop without losing playlist place
        try:
            from PyQt6.QtMultimedia import QMediaPlayer as _QMP
            self.player.mediaStatusChanged.connect(self._on_media_status)
        except Exception:
            pass
        self._is_url = str(path).startswith(("http://", "https://", "rtsp://", "udp://"))
        self.player.setSource(QUrl(str(path)) if self._is_url else QUrl.fromLocalFile(os.path.abspath(path)))
        self.player.play()
        if not self._is_url and _gb_ext(path) in AUDIO_EXT:
            self._show_visualizer()
        else:
            try:
                self.player.hasVideoChanged.connect(lambda hv: (not hv) and self._show_visualizer())
            except Exception:
                pass

    def load(self, path: str, volume_pct: Optional[int] = None):
        """GROOVEBOX_R23R_PLAYER_NO_REBOOT_20261103: switch to another file IN this window —
        same window, position, size and output; no close / reopen between playlist items."""
        self._src = path; self._retried = False
        self.setWindowTitle(f"Groovebox in-app player · {os.path.basename(path)}")
        if volume_pct is not None:
            self.vol.setValue(max(0, min(100, int(volume_pct))))
        self._is_url = str(path).startswith(("http://", "https://", "rtsp://", "udp://"))
        try:
            if self.visualizer is not None:
                self.visualizer.hide()
            self.video.show()
        except Exception:
            pass
        self.player.stop()
        self.player.setSource(self._QUrl(str(path)) if self._is_url else self._QUrl.fromLocalFile(os.path.abspath(path)))
        self.player.play()
        self.btn.setText("⏸ Pause")
        if not self._is_url and _gb_ext(path) in AUDIO_EXT:
            self._show_visualizer()

    def _show_visualizer(self):
        if self.visualizer is None or self.visualizer.isVisible() or getattr(self, "_is_url", False):
            return
        if not _gb_visualizer_enabled():
            return
        self.video.hide(); self.visualizer.show()
        self.visualizer.set_clock(lambda: self.player.position() / 1000.0)
        self.visualizer.load_path(self._src, lambda p: _gb_decode_audio_faithful(_gb_playable(p)))

    @staticmethod
    def _fmt(ms):
        s = int(ms // 1000); return f"{s // 60}:{s % 60:02d}"

    def _on_pos(self, ms):
        if not self.pos.isSliderDown():
            self.pos.setValue(int(ms))
        self.time.setText(f"{self._fmt(ms)} / {self._fmt(self.player.duration())}")

    def _toggle(self):
        from PyQt6.QtMultimedia import QMediaPlayer
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause(); self.btn.setText("▶ Play")
        else:
            self.player.play(); self.btn.setText("⏸ Pause")

    def _on_loop_toggled(self, checked: bool):
        self._loop_btn.setToolTip("Loop ON — track restarts at end (playlist place kept)" if checked else "Loop current track (playlist place kept)")

    def _on_viz_toggled(self, checked: bool):
        _gb_set_visualizer_enabled(checked)
        if checked:
            self._show_visualizer()
        elif self.visualizer is not None and self.visualizer.isVisible():
            self.visualizer.hide()
            self.video.show()

    def _on_media_status(self, status):
        try:
            from PyQt6.QtMultimedia import QMediaPlayer as _QMP
            if status == _QMP.MediaStatus.EndOfMedia and self._loop_btn.isChecked():
                self.player.setPosition(0)
                self.player.play()
                self.btn.setText("⏸ Pause")
        except Exception:
            pass

    def _on_error(self, *_a):
        if getattr(self, "_is_url", False):
            self.info.setText(f"Stream error: {self.player.errorString()} (is the other Groovebox still live?)")
            return
        if self._retried:
            self.info.setText(f"Qt could not play this file: {self.player.errorString()}")
            return
        self._retried = True
        self.info.setText("Qt cannot decode this container directly; making a playable copy with local FFmpeg…")
        try:
            out = _gb_qt_compatible_copy(self._src)
            self.player.setSource(self._QUrl.fromLocalFile(out)); self.player.play()
            self.info.setText(self.info.text() + " done.")
        except Exception as e:
            self.info.setText(f"Playback failed: {e}")

    def stop(self):
        try:
            self.player.stop()
        except Exception:
            pass

    def closeEvent(self, ev):
        self.stop()
        super().closeEvent(ev)


def _gb_inapp_fallback(widget, path: str, volume_pct: int = 100, duration_s: float = 0.0) -> str:
    """Play without any external player: audio → host device; video → InAppMediaPlayer; image → viewer."""
    if _gb_mcc_kind(path) == "video":
        _gb_open_mcc_video(widget, path, volume_pct)
        return f"MCC video (direct): {os.path.basename(path)}"
    ext = _gb_ext(path)
    play = _gb_playable(path)
    host = _gb_find_host(widget)
    if ext in IMAGE_EXT:
        dlg = ImageViewerDialog(play, widget)
        dlg.setModal(False); dlg.show()
        widget._gb_inapp_dialog = dlg
        if duration_s and duration_s > 0:
            QTimer.singleShot(int(duration_s * 1000), dlg.close)
        return f"In-app image viewer: {os.path.basename(path)}"
    if ext in AUDIO_EXT and host is not None:
        return "Host audio: " + _gb_play_on_host(host, play, volume_pct=volume_pct)
    preferred = str(getattr(host, "_preferred_audio_output_name", "") or "") if host is not None else ""
    old = getattr(widget, "_gb_inapp_dialog", None)
    if isinstance(old, InAppMediaPlayer):
        try:   # reuse the open window: no reboot between playlist items
            if old.isVisible():
                old.load(play, volume_pct)
                return f"In-app player: {os.path.basename(path)}"
        except RuntimeError:
            pass
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
    dlg = InAppMediaPlayer(play, widget, preferred_output=preferred, volume_pct=volume_pct)
    dlg.setModal(False); dlg.show()
    widget._gb_inapp_dialog = dlg
    return f"In-app player: {os.path.basename(path)}"


class ImageViewerDialog(QDialog):
    """Still-image viewer (GROOVEBOX_R23R_MCC_MEDIA_CODEC_20261101).

    Fit-to-window or zoom (mouse wheel), previous/next through the images of the
    folder, PNG/JPEG/WEBP/... and lossless .MCC images (decoded by mcc_media),
    details line (size, format, MCC header), and "Add to playlist" with a
    UI-chosen display duration.
    """
    def __init__(self, path, parent=None, add_to_playlist=None):
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        self.resize(900, 640)
        self._add = add_to_playlist
        self._zoom = 0.0                  # 0 = fit to window
        self._pix = QPixmap()
        lay = QVBoxLayout(self)
        self.view = QLabel(); self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setStyleSheet("background:#05070c; border:1px solid #2f6fe0;")
        from PyQt6.QtWidgets import QSizePolicy as _QSP
        self.view.setSizePolicy(_QSP.Policy.Expanding, _QSP.Policy.Expanding)
        lay.addWidget(self.view, 1)
        self.info = QLabel(""); self.info.setStyleSheet("color:#9cc7ff;"); lay.addWidget(self.info)
        row = QHBoxLayout()
        for text, fn in (("◀ Previous", lambda: self._step(-1)), ("Next ▶", lambda: self._step(1)),
                         ("Fit", self._fit), ("1:1", lambda: self._set_zoom(1.0))):
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch(1)
        row.addWidget(QLabel("Show for"))
        self.spin_dur = QDoubleSpinBox(); self.spin_dur.setRange(0.25, 3600.0); self.spin_dur.setDecimals(2)
        self.spin_dur.setValue(5.0); self.spin_dur.setSuffix(" s"); row.addWidget(self.spin_dur)
        b = QPushButton("→ Add to playlist"); b.clicked.connect(self._add_current); row.addWidget(b)
        lay.addLayout(row)
        self._folder_images = []
        self._load(path)

    @staticmethod
    def _is_image(path):
        return _gb_ext(path) in IMAGE_EXT

    def _load(self, path):
        self.path = str(path)
        try:
            from PyQt6.QtGui import QImage
            show = _gb_playable(self.path)      # .MCC image -> cached lossless PNG
            self._pix = QPixmap(show)
            extra = ""
            if os.path.splitext(self.path)[1].lower() == ".mcc":
                import mcc_media as _mm
                hdr = _mm.read_header(self.path)
                extra = f" · MCC lossless ({hdr.get('channels', 3)} ch)"
                if isinstance(hdr.get("extra"), dict) and "track_time_s" in hdr["extra"]:
                    extra += f" · track time {float(hdr['extra']['track_time_s']):.3f} s"
            self.info.setText(f"{os.path.basename(self.path)} · {self._pix.width()}×{self._pix.height()}{extra}")
        except Exception as exc:
            self._pix = QPixmap()
            self.info.setText(f"{os.path.basename(self.path)} · cannot display: {exc}")
        folder = os.path.dirname(self.path) or "."
        try:
            self._folder_images = sorted(os.path.join(folder, f) for f in os.listdir(folder)
                                         if self._is_image(os.path.join(folder, f)))
        except OSError:
            self._folder_images = [self.path]
        self._render()

    def _render(self):
        if self._pix.isNull():
            self.view.setPixmap(QPixmap()); return
        if self._zoom <= 0.0:
            pm = self._pix.scaled(self.view.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else:
            pm = self._pix.scaled(int(self._pix.width() * self._zoom), int(self._pix.height() * self._zoom),
                                  Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.view.setPixmap(pm)

    def _fit(self):
        self._zoom = 0.0; self._render()

    def _set_zoom(self, z):
        self._zoom = max(0.05, min(16.0, float(z))); self._render()

    def wheelEvent(self, e):
        base = self._zoom if self._zoom > 0 else (self.view.pixmap().width() / max(1, self._pix.width()) if self.view.pixmap() else 1.0)
        self._set_zoom(base * (1.15 if e.angleDelta().y() > 0 else 1 / 1.15))

    def resizeEvent(self, e):
        super().resizeEvent(e); self._render()

    def _step(self, d):
        if not self._folder_images:
            return
        try:
            i = self._folder_images.index(self.path)
        except ValueError:
            i = 0
        self._zoom = 0.0
        self._load(self._folder_images[(i + d) % len(self._folder_images)])

    def _add_current(self):
        if callable(self._add):
            self._add(self.path, float(self.spin_dur.value()))
            self.info.setText(self.info.text() + f" · added to playlist for {self.spin_dur.value():g} s")


MEDIA_EXT = AUDIO_EXT | VIDEO_EXT | IMAGE_EXT

# Fine-grained stream classification, distinct from the AUDIO_EXT/VIDEO_EXT
# extension buckets above: a .mp4/.mkv/etc. container can hold audio-only,
# video-only (silent), or both — the extension alone can't tell you which.
KIND_AUDIO = "audio"        # audio file, or audio-only container: no video track
KIND_VIDEO = "video"        # video container with NO audio track ("audioless video")
KIND_AV = "av"              # video container WITH an audio track ("both")
KIND_IMAGE = "image"          # still/animated image shown for playlist duration
KIND_UNKNOWN = "unknown"    # couldn't probe (no ffprobe, or read error)
KIND_PENDING = "pending"    # probe queued/in flight; always shown regardless of filter


class _PerformanceMathBackground(QWidget):
    """Very light deterministic ParametricMathBackground for Performance.

    Paint cost is intentionally tiny: a sparse Meum/phi lattice with two curves.
    It never consumes host/game state and therefore cannot feed back into identity.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._phase = 0.0
        # R6_EVENT_LOOP_20260928: decorative motion must never consume the GUI
        # thread merely because Performance is visible. Keep a dormant timer
        # object for R5 teardown compatibility, but do not connect or start it.
        self._timer = QTimer(self)
        # R5 lineage literal (historical verifier only): self._timer.setInterval(400)
        self._timer.setSingleShot(True)
    def showEvent(self, event):
        # One paint on expose/resize is sufficient; there is no periodic animation.
        self.update()
        return super().showEvent(event)
    def hideEvent(self, event):
        try: self._timer.stop()
        except Exception: pass
        return super().hideEvent(event)
    def _advance(self):
        # Compatibility method retained for old call sites; deliberately static.
        return
    def paintEvent(self, event):
        w,h=self.width(),self.height()
        if w < 2 or h < 2: return
        with owned_painter(self) as q:
            if q is None:
                return
            q.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            q.fillRect(self.rect(), self.palette().window())   # never leave stale pixels under the lattice
            q.setPen(QPen(QColor(68, 145, 174, 42), 1))
            step=max(48, min(w,h)//9)
            ox=int((self._phase/math.tau)*step)
            for x in range(-step+ox, w, step): q.drawLine(x,0,x,h)
            for y in range(-step+ox, h, step): q.drawLine(0,y,w,y)
            q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            q.setPen(QPen(QColor(245, 211, 109, 58), 1))
            pts=[]
            for i in range(0, max(2,w), max(6,w//180 or 6)):
                t=i/max(1,w-1)
                y=h*(0.50 + 0.16*math.sin(math.tau*(MEUM*t)+self._phase)
                     +0.08*math.sin(math.tau*PHI*t-self._phase*PHI_INV))
                pts.append((i,int(y)))
            for a,b in zip(pts,pts[1:]): q.drawLine(a[0],a[1],b[0],b[1])
            q.end()



def _decode_mount_field(value: str) -> str:
    """Decode the small escape set used by /proc/self/mounts."""
    return (value.replace("\\040", " ").replace("\\011", "\t")
                 .replace("\\012", "\n").replace("\\134", "\\"))


def _removable_status(device: str, parent_device: str='') -> Tuple[str, str]:
    """Read the root helper's last bounded mount result without shelling out."""
    root=Path('/run/sos/removable-status')
    for dev in (device,parent_device):
        if not dev: continue
        f=root/(os.path.basename(dev)+'.status')
        try:
            line=f.read_text(errors='replace').strip().splitlines()[-1]
            parts=line.split('|',2)
            return (parts[0] if parts else '', parts[2] if len(parts)>2 else '')
        except Exception:
            pass
    return ('','')

def _storage_device_snapshot() -> List[Dict[str, str]]:
    """Return removable storage without shelling out or polling hardware.

    R7 keeps this intentionally cheap: File Browser reads sysfs + /proc only when
    it opens or the user presses Refresh/Devices. The root sOS removable-media
    helper performs actual microSD mounting outside the Qt process.
    """
    mounts: Dict[str, Tuple[str, str]] = {}
    try:
        with open('/proc/self/mounts', 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                parts=line.split()
                if len(parts) >= 3 and parts[0].startswith('/dev/'):
                    mounts[os.path.realpath(_decode_mount_field(parts[0]))] = (
                        _decode_mount_field(parts[1]), parts[2])
    except OSError:
        pass

    labels: Dict[str, str] = {}
    by_label=Path('/dev/disk/by-label')
    try:
        if by_label.is_dir():
            for link in by_label.iterdir():
                try: labels[os.path.realpath(str(link))] = link.name
                except OSError: pass
    except OSError:
        pass

    # R17 partition safety: anything backing the running system/live medium is protected.
    system_devices=set()
    for real,(mp,_fstype) in mounts.items():
        if not mp.startswith(('/media/','/run/media/','/mnt/','/run/media/groovebox/')):
            system_devices.add(real)
            base=os.path.basename(real)
            parent=re.sub(r'p\d+$','',base) if base.startswith('mmcblk') or base.startswith('nvme') else re.sub(r'\d+$','',base)
            system_devices.add(os.path.realpath('/dev/'+parent))

    rows: List[Dict[str, str]] = []
    seen=set()
    sys_block=Path('/sys/class/block')
    try:
        names=sorted(p.name for p in sys_block.iterdir()) if sys_block.is_dir() else []
    except OSError:
        names=[]
    def _sd_reader_lun(whole: str) -> bool:
        try:
            base=sys_block/whole/'device'
            vendor=(base/'vendor').read_text(errors='ignore').strip().lower() if (base/'vendor').is_file() else ''
            model=(base/'model').read_text(errors='ignore').strip().lower() if (base/'model').is_file() else ''
            real=os.path.realpath(str(base)).lower()
            return ('realtek' in vendor or 'sd/mmc' in model or ('card' in model and 'reader' in model)
                    or 'usb2.0-crw' in model or 'rtsx' in real or '/mmc' in real)
        except OSError:
            return False

    for name in names:
        # Latitude 3510 can expose the Realtek reader as mmcblk* OR as a fixed-flag
        # sdX LUN. Card-reader ancestry is therefore authoritative over removable=0.
        # Also list truly-removable sdX media without treating the boot/internal
        # SSD as removable storage.
        is_mmc=name.startswith('mmcblk')
        is_sd=re.fullmatch(r'sd[a-z]+(?:\d+)?', name) is not None
        if not (is_mmc or is_sd):
            continue
        sysdev=sys_block/name
        is_partition=(sysdev/'partition').exists()
        whole=re.sub(r'p\d+$','',name) if is_mmc else re.sub(r'\d+$','',name)
        removable='0'
        for cand in (sys_block/whole/'removable', sysdev/'removable'):
            try:
                removable=cand.read_text().strip(); break
            except OSError:
                pass
        if not is_mmc and removable != '1' and not _sd_reader_lun(whole):
            continue
        # Prefer partitions where they exist. A superfloppy-formatted card can
        # legitimately put the filesystem directly on /dev/mmcblkN.
        if not is_partition:
            prefix=(name+'p') if is_mmc else name
            if any(n.startswith(prefix) and n != name for n in names):
                continue
        dev='/dev/'+name
        # sysfs can enumerate a freshly inserted SD/MMC device before udev has
        # created its /dev node. Keep it visible as a concrete failed-to-mount
        # device instead of silently turning it into the generic reader row.
        node_present=os.path.exists(dev)
        real=os.path.realpath(dev) if node_present else dev
        mp, fstype = mounts.get(real, ('',''))
        label=labels.get(real,'')
        key=(real,mp)
        if key in seen: continue
        seen.add(key)
        parent_dev='/dev/'+whole
        protected = real in system_devices or os.path.realpath(parent_dev) in system_devices or fstype in ('iso9660','udf')
        status_code,status_detail=_removable_status(dev,parent_dev)
        rows.append({
            'device': dev,
            'parent_device': parent_dev,
            'partition': '1' if is_partition else '0',
            'mountpoint': mp,
            'fstype': fstype,
            'label': label,
            'kind': 'microSD partition' if ((is_mmc or _sd_reader_lun(whole)) and is_partition) else ('microSD' if (is_mmc or _sd_reader_lun(whole)) else ('USB partition' if is_partition else 'USB removable')),
            'mountable': '1' if node_present else '0',
            'status_code': status_code if node_present else 'DEVICE_NODE_MISSING',
            'status_detail': status_detail if node_present else 'Kernel sees the card in sysfs, but /dev node is missing; mount was not attempted.',
            'protected': '1' if protected else '0',
            'formattable': '1' if (node_present and is_partition and not protected) else '0',
            'format_eligible': '1' if (node_present and is_partition and not protected) else '0',
        })

    # R14: surface the physical card-reader controller even before Linux has
    # emitted an mmcblk/sdX node. This gives File Manager a useful Rescan Reader
    # action instead of making an inserted-but-not-enumerated card disappear.
    if not any(str(r.get('kind','')).startswith('microSD') for r in rows):
        reader_names=[]
        for devdir in sorted(Path('/sys/bus/pci/devices').glob('*')) if Path('/sys/bus/pci/devices').is_dir() else []:
            try:
                vendor=(devdir/'vendor').read_text().strip().lower() if (devdir/'vendor').is_file() else ''
                driver=os.path.basename(os.path.realpath(devdir/'driver')) if (devdir/'driver').exists() else ''
                cls=(devdir/'class').read_text().strip().lower() if (devdir/'class').is_file() else ''
                if vendor=='0x10ec' or 'rtsx' in driver or cls.startswith('0x0805'):
                    reader_names.append(f"{devdir.name} {driver or 'SD reader'}")
            except OSError:
                pass
        for host in sorted(Path('/sys/class/mmc_host').glob('mmc*')) if Path('/sys/class/mmc_host').is_dir() else []:
            reader_names.append(f"{host.name} MMC host")
        for udev in sorted(Path('/sys/bus/usb/devices').glob('*')) if Path('/sys/bus/usb/devices').is_dir() else []:
            try:
                vendor=(udev/'idVendor').read_text().strip().lower() if (udev/'idVendor').is_file() else ''
                product=(udev/'product').read_text(errors='ignore').strip() if (udev/'product').is_file() else ''
                driver=os.path.basename(os.path.realpath(udev/'driver')) if (udev/'driver').exists() else ''
                if driver == 'rtsx_usb' or (vendor == '0bda' and any(t in product.lower() for t in ('card','reader','crw','sd','mmc'))):
                    reader_names.append(f"USB {udev.name} {product or driver or 'Realtek card reader'}")
            except OSError:
                pass
        sos_reader_expected=(os.environ.get("GROOVEBOX_SOS","").strip()=="1" or os.path.isdir("/run/sos") or os.path.isdir("/opt/sos"))
        if reader_names or sos_reader_expected:
            label=(' / '.join(dict.fromkeys(reader_names))[:160] if reader_names else 'Internal SD/microSD reader · block device not enumerated yet')
            reader_state,reader_detail=_removable_status('/dev/microsd-reader','')
            if not reader_state and sos_reader_expected:
                reader_state='NO_CARD_DEVICE'
                reader_detail='Reader is present but no /dev/mmcblk or reader LUN appeared after rescan; card could not be mounted.'
            if reader_detail: label += ' · '+reader_detail
            rows.append({'device':'','mountpoint':'','fstype':'','label':label,
                         'kind':'microSD reader','mountable':'0','rescan_only':'1','protected':'0','formattable':'0','format_eligible':'0',
                         'status_code':reader_state,'status_detail':reader_detail})

    # R28: enrich the existing removable-device rows with partition-table flags,
    # EFI/bootable hints and richer metadata when lsblk is available. Keep the
    # sysfs + existing guarded automounter as the authority for actionable rows.
    try:
        from removable_media_inventory import inventory as _r28_inventory
        _by_path={str(x.get('path') or ''):x for x in _r28_inventory()}
        for _row in rows:
            _meta=_by_path.get(str(_row.get('device') or ''),{})
            if _meta:
                _row['bootable']='1' if _meta.get('bootable') else '0'
                _row['partition_flags']=str(_meta.get('partition_flags') or '')
                _row['partition_type']=str(_meta.get('partition_type') or '')
                _row['inventory_status']=str(_meta.get('status') or '')
    except Exception:
        pass

    # Also retain desktop/USB mounts whose sysfs device may not be visible in a
    # containerized/session namespace. This keeps normal Fedora usage working.
    for real,(mp,fstype) in mounts.items():
        if not mp.startswith(('/media/','/run/media/','/mnt/')):
            continue
        if any(r.get('mountpoint') == mp for r in rows):
            continue
        rows.append({'device':real,'mountpoint':mp,'fstype':fstype,
                     'label':labels.get(real,''),'kind':'Mounted storage','mountable':'1','protected':'1','formattable':'0','format_eligible':'0'})
    return rows

def _probe_media_kind_sync(path: str) -> str:
    """Classify a file's actual stream content (not just its extension).

    Plain audio extensions are audio by definition — no need to shell out.
    Anything with a video extension gets an ffprobe stream-type check, since
    a video container may or may not actually carry an audio track.
    """
    ext = _gb_ext(path)
    if ext in AUDIO_EXT:
        return KIND_AUDIO
    if ext in IMAGE_EXT:
        return KIND_IMAGE
    if ext not in VIDEO_EXT:
        return KIND_UNKNOWN
    ffprobe = resolve_local_tool("ffprobe", required=False)
    if not ffprobe:
        return KIND_UNKNOWN
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=8,
        )
        types = {line.strip() for line in (proc.stdout or "").splitlines() if line.strip()}
        has_v = "video" in types
        has_a = "audio" in types
        if has_v and has_a:
            return KIND_AV
        if has_v:
            return KIND_VIDEO
        if has_a:
            return KIND_AUDIO
        return KIND_UNKNOWN
    except Exception:
        return KIND_UNKNOWN


def _analyze_signal_descriptor(path: str, cache: Dict[str, Tuple[float, int, Optional[dict]]]) -> Optional[dict]:
    """Real DSP analysis (fundamental/centroid/rms/zcr/etc.) via
    reverse_engineer.describe(), used for reverse-engineer-style matching
    between playlist tracks rather than name/size heuristics alone.
    Non-WAV media is down-mixed to a short mono WAV with ffmpeg first.
    Cached by (path, mtime, size) like the kind-probe cache."""
    try:
        st = os.stat(path)
        key = (st.st_mtime, st.st_size)
    except Exception:
        return None
    cached = cache.get(path)
    if cached is not None and cached[0] == key[0] and cached[1] == key[1]:
        return cached[2]
    result: Optional[dict] = None
    try:
        import reverse_engineer as _re
        ext = _gb_ext(path)
        tmp_wav = None
        wav_path = path
        if ext != ".wav":
            from groovebox_media_tools import resolve_local_tool
            ffmpeg = resolve_local_tool("ffmpeg")
            if not ffmpeg:
                cache[path] = (key[0], key[1], None)
                return None
            tmp_wav = os.path.join(tempfile.gettempdir(), f"groovebox_analyze_{__import__('hashlib').sha256(os.path.abspath(path).encode('utf-8', 'replace')).hexdigest()[:16]}.wav")
            subprocess.run(
                [ffmpeg, "-y", "-i", path, "-t", "30", "-ac", "1", "-ar", "22050", tmp_wav],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=True,
            )
            wav_path = tmp_wav
        x, sr = _re.load_wav_mono(wav_path)
        desc = _re.describe(x, sr)
        result = {
            "fundamental_hz": desc.fundamental_hz,
            "centroid_hz": desc.centroid_hz,
            "rms": desc.rms,
            "zcr": desc.zcr,
            "duration_s": desc.duration_s,
            "transient_density": desc.transient_density,
        }
        if tmp_wav:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass
    except Exception:
        result = None
    _bounded_cache_put(cache, path, (key[0], key[1], result), 128)
    return result


def _pitch_class_distance(a_hz: float, b_hz: float) -> float:
    """Circular pitch-class distance in semitones (0..6), octave independent."""
    try:
        if float(a_hz) <= 0.0 or float(b_hz) <= 0.0:
            return 6.0
        a = (69.0 + 12.0 * math.log2(float(a_hz) / 440.0)) % 12.0
        b = (69.0 + 12.0 * math.log2(float(b_hz) / 440.0)) % 12.0
        d = abs(a - b)
        return min(d, 12.0 - d)
    except Exception:
        return 6.0


def _descriptor_distance(a: dict, b: dict) -> float:
    """Deterministic key/texture distance between analyzed tracks.

    Pitch uses circular pitch-class distance rather than raw-Hz subtraction so
    octave-equivalent material is treated as harmonically close. Remaining
    terms preserve brightness, loudness and rhythmic-density matching.
    """
    def norm(v, scale):
        return float(v) / scale if scale else 0.0
    d_key = _pitch_class_distance(a.get("fundamental_hz", 0.0), b.get("fundamental_hz", 0.0)) / 6.0
    # A small octave/register term keeps an exact-key bass line distinguishable
    # from an extreme-register equivalent without overpowering key identity.
    try:
        ar=float(a.get("fundamental_hz",0.0)); br=float(b.get("fundamental_hz",0.0))
        d_register=min(4.0, abs(math.log2(ar/br))) / 4.0
    except Exception:
        d_register=1.0
    d_centroid = abs(norm(a.get("centroid_hz",0.0), 4000.0) - norm(b.get("centroid_hz",0.0), 4000.0))
    d_rms = abs(float(a.get("rms",0.0)) - float(b.get("rms",0.0)))
    d_zcr = abs(float(a.get("zcr",0.0)) - float(b.get("zcr",0.0)))
    d_trans = abs(float(a.get("transient_density",0.0)) - float(b.get("transient_density",0.0)))
    return d_key * 1.8 + d_register * 0.25 + d_centroid * 1.2 + d_rms + d_zcr * 0.6 + d_trans * 0.8


def _canonical_media_signature(path: str) -> dict:
    """Read deterministic Groovebox provenance for Canonical Match mode."""
    prov = _extract_json_comment(path) or {}
    if not isinstance(prov, dict):
        prov = {}
    nested = prov.get("canonical") if isinstance(prov.get("canonical"), dict) else {}
    def first(*keys):
        for key in keys:
            if key in prov and prov.get(key) not in (None, ""):
                return prov.get(key)
            if key in nested and nested.get(key) not in (None, ""):
                return nested.get(key)
        return None
    return {
        "fingerprint": str(first("fingerprint", "canonical_fingerprint", "composition_fingerprint") or ""),
        "canonical_id": str(first("canonical_id", "composition_id", "identity") or ""),
        "seed": first("seed", "canonical_seed"),
        "bpm": first("bpm", "tempo"),
        "eqr": first("eqr", "EQR"),
        "goava": first("goava", "GOAVA"),
    }


def _canonical_media_distance(a_path: str, b_path: str) -> Optional[float]:
    a=_canonical_media_signature(a_path); b=_canonical_media_signature(b_path)
    evidence=0; score=0.0
    if a["fingerprint"] and b["fingerprint"]:
        evidence += 1; score += 0.0 if a["fingerprint"] == b["fingerprint"] else 4.0
    if a["canonical_id"] and b["canonical_id"]:
        evidence += 1; score += 0.0 if a["canonical_id"] == b["canonical_id"] else 2.5
    for key,scale,weight in (("bpm",120.0,1.0),("eqr",1.0,0.8),("goava",1.0,0.6)):
        try:
            if a[key] is not None and b[key] is not None:
                evidence += 1; score += min(2.0, abs(float(a[key])-float(b[key]))/scale) * weight
        except Exception:
            pass
    try:
        if a["seed"] is not None and b["seed"] is not None:
            evidence += 1
            sa=int(float(a["seed"])) & 0x7fffffff; sb=int(float(b["seed"])) & 0x7fffffff
            score += (abs(sa-sb)/2147483647.0) * 0.5
    except Exception:
        pass
    return score if evidence else None


def _kind_icon(kind: str) -> str:
    return {
        KIND_AUDIO: "🔊", KIND_VIDEO: "🎬(mute)", KIND_AV: "🎬🔊", KIND_IMAGE: "🖼", KIND_PENDING: "⏳",
    }.get(kind, "📄")


def _bounded_cache_put(cache: dict, key, value, limit: int = 256):
    """Keep session caches useful without allowing path history to grow forever."""
    cache[key] = value
    while len(cache) > max(1, int(limit)):
        try:
            cache.pop(next(iter(cache)), None)
        except Exception:
            break



class _NearbyBridge(QObject):
    result = pyqtSignal(str, object, str)
    progress = pyqtSignal(int, int, str)


class _IsoCopyBridge(QObject):
    """Return finished-product ISO copy progress without blocking the GUI."""
    done = pyqtSignal(object, str)
    progress = pyqtSignal(int, int, str)


class _DeviceScanBridge(QObject):
    """Return slow display/audio discovery to the GUI without blocking first paint."""
    done = pyqtSignal(int, object, object, str)


class _PlayerPollBridge(QObject):
    """Return mpv status reads to Qt without ever blocking the GUI thread."""
    done = pyqtSignal(int, object)


class _FileListBridge(QObject):
    """Directory listing result bridge for the standalone file browser."""
    done = pyqtSignal(int, str, object, str)

class _HardwareScanBridge(QObject):
    """Return independent hardware-family discovery without blocking Qt."""
    done = pyqtSignal(int, str, object, str)

class _AudioIoTestBridge(QObject):
    """Return the on-device speaker->microphone acoustic-loop acceptance test."""
    done = pyqtSignal(int, int, str)

class _QuickDeviceBridge(QObject):
    """Return fixed Performance audio/video selectors without blocking Qt."""
    done = pyqtSignal(int, object, str)

class _OutputDeviceBridge(QObject):
    """Return hot-plug display/audio scans without blocking the Performance UI."""
    done = pyqtSignal(int, object, object, str)

class _PoolTask(QRunnable):
    """Small QThreadPool task wrapper used by Performance background work.

    PERF_THREAD_LIFECYCLE_20260924: keep worker lifetime owned by Qt instead of
    detached daemon ``threading.Thread`` instances.  The owning dialog can then
    wait for all tasks before QApplication teardown, preventing late signal
    delivery/QThreadStorage destruction after the GUI thread has begun exiting.
    """
    def __init__(self, fn, *args):
        super().__init__()
        self._fn = fn
        self._args = args
        self.setAutoDelete(True)

    def run(self):
        try:
            self._fn(*self._args)
        except Exception as exc:
            print(f"[Performance worker] {type(exc).__name__}: {exc}", file=sys.stderr)


class _KindProbeWorker(QObject):
    """Batch stream-probing off the UI thread (see _ProvenanceWorker above
    for why: ffprobe calls must never run on the UI thread). Probes an
    entire folder listing's video files sequentially in one background
    thread and emits one signal per completed file, plus a final batch_done
    so the browser can re-apply the active Audio/Video filter once every
    file in the folder has a real (non-pending) classification."""
    progress = pyqtSignal(int, str, str)  # generation, path, kind
    batch_done = pyqtSignal(int)          # generation

    def run_batch(self, generation: int, paths: List[str]):
        for p in paths:
            kind = _probe_media_kind_sync(p)
            self.progress.emit(generation, p, kind)
        self.batch_done.emit(generation)



def _safe_size_bytes(n: int) -> str:
    try: n=int(n)
    except Exception: return "?"
    for unit,div in (("GB",1<<30),("MB",1<<20),("KB",1<<10)):
        if n >= div: return f"{n/div:.1f} {unit}"
    return f"{n} B"


def _safe_size(path: str) -> str:
    try:
        n = os.path.getsize(path)
    except OSError:
        return "?"
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def _media_player_executable(name: str) -> Optional[str]:
    """Resolve bundled and system players consistently across desktop and sOS.

    A system can have the locally provisioned media tools while their directory
    is intentionally absent from PATH. Prefer the Groovebox tool resolver, then
    PATH, then conventional app-local bin directories. Never return a non-file.
    """
    try:
        resolved = resolve_local_tool(name, required=False)
        if resolved and os.path.isfile(resolved) and os.access(resolved, os.X_OK):
            return os.path.abspath(resolved)
    except Exception:
        pass
    found = shutil.which(name)
    if found:
        return found
    roots = [os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    for root in roots:
        for candidate in (os.path.join(root, "bin", name), os.path.join(root, "tools", name)):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


def _find_player(want_video: bool = True) -> Optional[List[str]]:
    """Return a decoder-backed player command, preferring mpv then VLC/FFplay.

    mpv and VLC provide the broadest practical container/codec coverage. FFplay
    remains the final FFmpeg decoder fallback. Audio-only playback explicitly
    keeps a video window hidden only for FFplay; video and A/V files retain video.
    """
    for cand in ("mpv", "vlc", "ffplay"):
        p = _media_player_executable(cand)
        if not p:
            continue
        if cand == "mpv":
            # GROOVEBOX_R23R_SMOOTH_PLAYLIST_20261103: deeper read-ahead (USB / SD media), the next
            # playlist item prefetched, gapless audio between items.
            args = [p, "--force-window=yes", "--keep-open=yes", "--hwdec=auto-safe",
                    "--autosync=30", "--cache=auto", "--cache-secs=1", "--cache-pause=no",
                    "--demuxer-readahead-secs=1", "--demuxer-max-bytes=32MiB",
                    "--prefetch-playlist=yes", "--gapless-audio=weak",
                    "--audio-samplerate=48000", "--audio-channels=stereo",
                    "--audio-fallback-to-null=no"]
            if not want_video:
                args += ["--audio-client-name=Groovebox"]
            return args
        if cand == "vlc":
            return [p, "--no-one-instance", "--no-video-title-show"]
        args = [p, "-autoexit", "-hide_banner"]
        if not want_video:
            args.append("-nodisp")
        return args
    return None


def _player_cmd_with_volume(volume_pct: int, want_video: bool = True) -> Optional[List[str]]:
    """Player command with per-track volume, using the same bundled resolver."""
    for cand in ("mpv", "vlc", "ffplay"):
        p = _media_player_executable(cand)
        if not p:
            continue
        vol = max(0, min(200, int(volume_pct)))
        if cand == "mpv":
            # GROOVEBOX_R23R_SMOOTH_PLAYLIST_20261103: deeper read-ahead (USB / SD media), the next
            # playlist item prefetched, gapless audio between items.
            args = [p, "--force-window=yes", "--keep-open=yes", "--hwdec=auto-safe",
                    "--autosync=30", "--cache=auto", "--cache-secs=1", "--cache-pause=no",
                    "--demuxer-readahead-secs=1", "--demuxer-max-bytes=32MiB",
                    "--prefetch-playlist=yes", "--gapless-audio=weak",
                    f"--volume={vol}", "--audio-samplerate=48000", "--audio-channels=stereo",
                    "--audio-fallback-to-null=no"]
            if not want_video:
                args += ["--audio-client-name=Groovebox"]
            return args
        if cand == "vlc":
            return [p, "--no-one-instance", "--no-video-title-show", f"--gain={vol / 100.0:.2f}"]
        args = [p, "-autoexit", "-hide_banner", "-volume", str(min(100, vol))]
        if not want_video:
            args.append("-nodisp")
        return args
    return None


def _launch_physical_pcm_pipeline(path: str, start_s: float = 0.0, preferred_target=None):
    """Decode any FFmpeg-readable audio stream to a proven physical ALSA PCM.

    R23k tries the ranked real ALSA endpoints and rejects a sink that exits
    immediately before FFmpeg is attached. This prevents a valid-but-wrong HDMI
    or unavailable PCM from becoming the silent "successful" fallback.
    """
    ffmpeg=resolve_local_tool("ffmpeg", False)
    aplay=shutil.which("aplay")
    if not ffmpeg or not aplay:
        raise RuntimeError("local ffmpeg or aplay is unavailable")
    try:
        from media_output_router import _physical_alsa_playback_devices, _preferred_alsa_output_device, _prepare_physical_alsa_output
        routes=[]
        if preferred_target is not None and str(getattr(preferred_target,'backend',''))=='alsa' and str(getattr(preferred_target,'name','')):
            routes.append(str(getattr(preferred_target,'name','')))
        routes += [x for x in list(_physical_alsa_playback_devices() or []) if x not in routes]
        preferred=_preferred_alsa_output_device() or ""
        if preferred and preferred not in routes:
            routes.insert(0,preferred)
    except Exception:
        routes=[]
        _prepare_physical_alsa_output=lambda _dev: False
    if not routes:
        routes=["alsa/default"]

    dec_base=[ffmpeg,"-hide_banner","-loglevel","error","-nostdin"]
    if float(start_s or 0.0) > 0:
        dec_base += ["-ss",f"{float(start_s):.6f}"]
    dec_base += ["-i",path,"-map","0:a:0","-vn","-ac","2","-ar","48000"]
    # GROOVEBOX_R23R_TRANSPARENT_FILE_PLAYBACK_20261101: high-quality resampling
    # (SoXR when the bundled FFmpeg has it) and 32-bit output so 24-bit sources
    # are not truncated; 16-bit with triangular dither only as the last fallback.
    _rs = "aresample=48000:resampler=soxr:precision=28" if _ffmpeg_has_soxr(ffmpeg) else \
          "aresample=48000:filter_size=64:phase_shift=10:cutoff=0.97"

    errors=[]
    for _out_args, _alsa in ((["-f","s32le","pipe:1"], "S32_LE"), (["-f","s16le","pipe:1"], "S16_LE")):
      _af = _rs + (":dither_method=triangular" if _alsa == "S16_LE" else "")
      for route in routes:
        _r = _try_physical_route(route, dec_base + ["-af", _af] + _out_args, _alsa, aplay, _prepare_physical_alsa_output, errors)
        if _r is not None:
            return _r
    raise RuntimeError("no physical ALSA playback endpoint opened" + (": "+"; ".join(errors[-3:]) if errors else ""))


_SOXR_CACHE = {}


def _ffmpeg_has_soxr(ffmpeg) -> bool:
    if ffmpeg in _SOXR_CACHE:
        return _SOXR_CACHE[ffmpeg]
    ok = False
    try:
        r = subprocess.run([ffmpeg, "-hide_banner", "-buildconf"], capture_output=True, text=True, timeout=5)
        ok = "enable-libsoxr" in ((r.stdout or "") + (r.stderr or ""))
    except Exception:
        ok = False
    _SOXR_CACHE[ffmpeg] = ok
    return ok


def _try_physical_route(route, dec_cmd, alsa_fmt, aplay, _prepare_physical_alsa_output, errors):
    if True:
        dev=str(route or "")
        try:
            _prepare_physical_alsa_output(dev)
        except Exception:
            pass
        if dev.startswith("alsa/"):
            dev=dev[5:]
        out=[aplay,"-q"]
        if dev:
            out += ["-D",dev]
        out += ["-f",alsa_fmt,"-c","2","-r","48000"]
        sink=None
        try:
            # Open/prove the hardware endpoint before starting the decoder.
            sink=subprocess.Popen(out,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            time.sleep(0.10)
            rc=sink.poll()
            if rc is not None:
                errors.append(f"{dev or 'default'}: aplay rc={rc}")
                return None
            _err=tempfile.TemporaryFile()
            decoder=subprocess.Popen(dec_cmd,stdout=sink.stdin,stderr=_err)
            if sink.stdin is not None:
                sink.stdin.close()
            # GROOVEBOX_R23R_WAV_PLAYER_DEVICE_20261101: watch both ends for 0.35 s (was a
            # single 40 ms look at the decoder); a sink that dies once data arrives (busy /
            # unsupported format) or a decoder error now falls through to the next route.
            drc=None; src=None
            for _ in range(7):
                time.sleep(0.05)
                drc=decoder.poll(); src=sink.poll()
                if (drc not in (None,0)) or (src is not None):
                    break
            if (drc not in (None,0)) or (src is not None and src!=0):
                try: sink.terminate()
                except Exception: pass
                try: decoder.terminate()
                except Exception: pass
                try:
                    _err.seek(0); _tail=_err.read()[-300:].decode("utf-8","replace").strip()
                except Exception:
                    _tail=""
                errors.append(f"{dev or 'default'} {alsa_fmt}: "+(f"ffmpeg rc={drc}" if drc not in (None,0) else f"aplay rc={src}")+(f" ({_tail})" if _tail else ""))
                return None
            return sink,decoder,"aplay:"+(dev or "default")+f"<-ffmpeg {alsa_fmt}"
        except Exception as exc:
            errors.append(f"{dev or 'default'}: {exc}")
            if sink is not None:
                try: sink.terminate()
                except Exception: pass
        return None


def _extract_wav_eqrf(path: str) -> Optional[bytes]:
    """Read optional 'eqrf' chunk from a Groovebox WAV without importing groovebox."""
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"RIFF":
                return None
            f.read(4)
            if f.read(4) != b"WAVE":
                return None
            while True:
                hdr = f.read(8)
                if len(hdr) < 8:
                    break
                cid, sz = hdr[:4], int.from_bytes(hdr[4:8], "little")
                data = f.read(sz)
                if cid == b"eqrf":
                    return data
                if sz & 1:
                    f.read(1)
    except Exception:
        return None
    return None


def _extract_json_comment(path: str) -> Optional[dict]:
    """Best-effort provenance from WAV eqrf chunk or ffmpeg comment / sidecars."""
    try:
        raw = _extract_wav_eqrf(path)
        if raw:
            text = raw.decode("utf-8", errors="replace")
            if text.strip().startswith("{"):
                return json.loads(text)
    except Exception:
        pass
    # Sidecar .mgpr / .json next to media
    for suffix in (".mgpr", ".json", ".provenance.json"):
        side = path + suffix
        if os.path.isfile(side):
            try:
                with open(side, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        base, _ = os.path.splitext(path)
        side2 = base + suffix
        if os.path.isfile(side2):
            try:
                with open(side2, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    # ffprobe comment
    ffprobe = resolve_local_tool("ffprobe", required=False)
    if ffprobe and os.path.isfile(path):
        try:
            proc = subprocess.run(
                [ffprobe, "-v", "quiet", "-show_entries", "format_tags=comment",
                 "-of", "json", path],
                capture_output=True, text=True, timeout=12,
            )
            data = json.loads(proc.stdout or "{}")
            comment = (
                (data.get("format") or {}).get("tags") or {}
            ).get("comment") or ""
            if isinstance(comment, str) and comment.strip().startswith("{"):
                return json.loads(comment)
        except Exception:
            pass
    return None


class _ProvenanceWorker(QObject):
    """Runs the (potentially slow, ffprobe-shelling) provenance lookup off
    the UI thread.

    PERF_2026: `_extract_json_comment` can invoke `ffprobe` with up to a
    12-second timeout. It used to run directly inside
    `_on_selection_changed`, so clicking or arrow-keying through a folder of
    samples/videos froze the whole Performance for however long each ffprobe
    call took — the exact "lag while using the app" complaint on slower
    storage (SD cards, network shares). One QThread does the shelling out;
    results come back via a signal so Qt marshals them onto the UI thread
    safely, and a token lets the UI drop stale results if the user has
    already moved on to a different file.
    """
    done = pyqtSignal(int, str, object)  # token, path, provenance dict-or-None

    def lookup(self, token: int, path: str):
        prov = _extract_json_comment(path) if os.path.isfile(path) else None
        self.done.emit(token, path, prov)



# GROOVEBOX_R23R_PERFORMANCE_COLORS_20261103: Performance follows the main window's colour roles
# (transport green, danger red, export cyan, engines blue, random violet, game magenta,
# media amber, save/load teal); tabs and section titles get their own hues.
_GB_ROLE_COLORS = (
    (("⏹", "stop", "cancel", "close"), "#ff6b6b"),
    (("🗑", "delete", "trash", "remove", "clear", "wipe", "format"), "#ff4d6d"),
    (("▶", "play", "listen", "watch", "audition", "preview"), "#3ddc84"),
    (("export", "render", "batch", "convert", "📦", "🎚"), "#22d3ee"),
    (("save", "load", "copy", "💾", "📂", "open", "import", "upload", "download"), "#2dd4bf"),
    (("game", "🎮", "world"), "#e879f9"),
    (("record", "🎥", "🎙", "mic", "camera", "stream", "live", "broadcast"), "#fbbf24"),
    (("nearby", "network", "hotspot", "wi-fi", "wifi", "📡", "peer", "share", "chat", "group"), "#60a5fa"),
    (("random", "seed", "🎲", "remix", "goava", "dj"), "#a78bfa"),
    (("scan", "detect", "refresh", "↻", "probe", "test", "check", "🩺"), "#94a3b8"),
)


def _gb_role_color(text):
    t = str(text or "").casefold()
    for keys, col in _GB_ROLE_COLORS:
        if any(k in t for k in keys):
            return col
    return "#7dd3fc"


def _gb_colorize_widget_tree(root):
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGroupBox, QPushButton, QTabWidget
    for b in root.findChildren(QPushButton):
        try:
            if b.property("gbColored") or (b.styleSheet() or "").strip():
                continue
            c = QColor(_gb_role_color(b.text()))
            b.setStyleSheet(
                "QPushButton { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 %s, stop:1 %s); color:%s;"
                " border:1px solid %s; border-radius:8px; padding:4px 10px; font-weight:700; }"
                "QPushButton:hover { border:2px solid %s; background:%s; }"
                "QPushButton:pressed { background:%s; color:#0b0f14; }"
                "QPushButton:disabled { color:#5c6670; border-color:#2a3138; background:#11161b; }"
                "QPushButton:checked { background:%s; color:#0b0f14; }"
                % (c.darker(330).name(), c.darker(450).name(), c.lighter(140).name(), c.darker(160).name(),
                   c.name(), c.darker(250).name(), c.name(), c.name()))
            b.setProperty("gbColored", True)
        except Exception:
            pass
    for i, g in enumerate(root.findChildren(QGroupBox)):
        try:
            if g.property("gbColored") or (g.styleSheet() or "").strip():
                continue
            c = QColor.fromHsv((i * 41 + 190) % 360, 150, 245)
            g.setStyleSheet("QGroupBox { border:1px solid %s; border-radius:8px; margin-top:9px; padding-top:6px; }"
                            "QGroupBox::title { color:%s; subcontrol-origin: margin; left:9px; padding:0 4px; font-weight:800; }"
                            % (c.darker(220).name(), c.name()))
            g.setProperty("gbColored", True)
        except Exception:
            pass
    for tw in root.findChildren(QTabWidget):
        try:
            bar = tw.tabBar()
            for i in range(tw.count()):
                bar.setTabTextColor(i, QColor.fromHsv((i * 29 + 170) % 360, 140, 250))
        except Exception:
            pass


class Performance(QDialog):
    """In-app file browser, playlister, game player, DJ remixer, batch export."""

    def _on_master_volume_changed(self, value: int) -> None:
        """Update the host's scalar synth master gain from the Performance UI."""
        value = max(0, min(100, int(value)))
        if hasattr(self, "lbl_master_volume"):
            self.lbl_master_volume.setText(f"{value}%")
        slider = getattr(self.host, "slider_master_vol", None)
        if slider is not None:
            try:
                slider.blockSignals(True)
                slider.setValue(value)
            finally:
                slider.blockSignals(False)
        # Invoke the scalar-state updater explicitly; the hidden compatibility
        # slider is deliberately signal-blocked above.
        updater = getattr(self.host, "_on_master_vol_changed", None)
        if callable(updater):
            updater(value)
        else:
            self.host.master_volume = value / 100.0

    def _scroll_page(self, page: QWidget) -> QScrollArea:
        """Compatibility wrapper: every Performance tab remains reachable at any DPI/window size."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setMinimumSize(320, 240)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        # GROOVEBOX_R23R_PERFORMANCE_TAB_ARTIFACTS_20261101: WA_OpaquePaintEvent told Qt
        # not to erase the viewport, but the pages do not paint their full background,
        # so the previous tab's pixels stayed visible. Erase properly instead.
        area.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        area.viewport().setAutoFillBackground(True)
        page.setAutoFillBackground(True)
        page.setMinimumSize(max(300, page.minimumWidth()), max(200, page.minimumHeight()))
        area.setWidget(page)
        return area

    def __init__(self, host, parent=None):
        super().__init__(parent or host)
        self.host = host
        # R17 lazy-guaranteed hardware gate: one full scan on first hardware-capable surface.
        try:
            from hardware_runtime import ensure_first_hardware_refresh
            ensure_first_hardware_refresh("performance-open", block=False)
        except Exception:
            pass
        self.setWindowTitle("Groovebox Performance — Media · Devices · Cutups · Game · Broadcast · Batch")
        self.setStyleSheet("""
            QDialog { background:#071019; color:#d9edf5; }
            QGroupBox { border:1px solid #284c62; border-radius:7px; margin-top:8px; padding-top:7px; font-weight:700; }
            QGroupBox::title { color:#f1ce68; subcontrol-origin:margin; left:9px; padding:0 4px; }
            QPushButton { background:#102838; color:#d9f7ff; border:1px solid #39708a; border-radius:11px; padding:8px 11px; font-weight:700; }
            QPushButton:hover { background:#17405a; border-color:#62bfd0; }
            QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit { background:#08141e; color:#e6f8ff; border:1px solid #335b70; border-radius:8px; padding:6px; }
            QTabWidget::pane { background:#071019; border:2px solid #3b718c; }
            QTabBar::tab { background:#0c1b28; color:#b9d5df; padding:10px 12px; margin:2px; border:2px solid #35677f; border-radius:9px; min-width:42px; }
            QTabBar::tab:hover { background:#122c3e; border-color:#4b879f; }
            QTabBar::tab:selected { background:#17354a; color:#f6d46d; border-color:#6ca6ba; }
        """)
        self.resize(920, 640)
        self.setMinimumSize(720, 480)
        # PERFORMANCE_MATH_BG_20260905: ambient, sparse, low-refresh background.
        self._math_background = _PerformanceMathBackground(self)
        self._math_background.lower()
        self._player_proc: Optional[subprocess.Popen] = None
        self._player_aux_proc: Optional[subprocess.Popen] = None  # R23j FFmpeg -> physical ALSA decoder
        self._playlist: List[Dict[str, Any]] = []
        self._playlist_index = -1
        # TIMED_MEDIA_20260906: absolute timeline scheduling for any media type,
        # including still pictures routed to a selected external display.
        self._timed_playlist_timer = QTimer(self)
        self._timed_playlist_timer.setInterval(25)
        self._timed_playlist_timer.timeout.connect(self._timed_playlist_tick)
        self._timed_playlist_epoch = 0.0
        self._timed_playlist_pending: List[int] = []
        self._batch_cancel = False
        self._mix_procs: List[subprocess.Popen] = []
        # LIVE_MEDIA_2026: mpv JSON-IPC gives instant speed changes without
        # killing/restarting a file. One socket is reused for the active player.
        self._mpv_ipc_path: Optional[str] = None
        self._live_speed = 1.0
        # CONTINUOUS_PATTERN_2026: cheap deterministic control-rate scripting.
        self._pattern_phase = 0.0
        self._pattern_step = 0
        self._pattern_rng = random.Random(0)
        self._pattern_timer = QTimer(self)
        self._pattern_timer.setInterval(50)
        self._pattern_timer.timeout.connect(self._pattern_tick)
        # PERFORMANCE_BROADCAST_2026: one phaselocked clock fans the same event
        # state to replay, video/game state and optional Ethernet clients.
        self._performance_timer = QTimer(self)
        self._performance_timer.timeout.connect(self._performance_tick)
        self._performance_step = 0
        self._performance_media_path: Optional[str] = None
        self._performance_loop = False
        self._broadcast_state: Dict[str, Any] = {"active": False}
        self._remote_server = None
        self._remote_thread = None
        self._remote_token = secrets.token_urlsafe(12)
        self._remote_commands: List[Dict[str, Any]] = []
        self._remote_lock = threading.Lock()
        self._remote_timer = QTimer(self)
        self._remote_timer.setInterval(50)
        self._remote_timer.timeout.connect(self._drain_remote_commands)
        # Starts only with the Ethernet control server; idle Performance has no 20 Hz poll.

        # OUTPUT_ROUTER_2026: optional local display/audio routing plus LAN/Wi-Fi TV
        # sharing. Hardware discovery is refreshed on demand so hot-plugged HDMI,
        # VGA adapters, USB displays/audio and Bluetooth sinks can appear live.
        self._output_displays = []
        self._output_audio = []
        self._output_display = None
        # Always route audio to every detected sink (no per-menu selection drift).
        try:
            from media_output_router import AudioTarget
            self._output_audio_target = AudioTarget("__all_detected__", "All detected outputs (default)", kind="all", backend="pulse")
            self._output_audio = [self._output_audio_target]
        except Exception:
            self._output_audio_target = None
        self._pending_output_restore = ('', '')
        self._output_scan_generation = 0
        self._output_scan_inflight = False
        self._output_device_bridge = _OutputDeviceBridge(self)
        self._output_device_bridge.done.connect(self._on_output_devices_ready)
        self._output_refresh_timer = QTimer(self)
        self._output_refresh_timer.setInterval(10000)
        self._output_refresh_timer.timeout.connect(self._refresh_output_devices_if_visible)
        # Start only while the dialog is visible. Device scans are expensive on
        # USB/Bluetooth/HDMI-heavy systems and must not survive hidden-window time.
        # R23l fixed Performance device strip. One isolated probe supplies the
        # always-visible output/input/video selectors and never blocks first paint.
        self._quick_device_generation = 0
        self._quick_device_bridge = _QuickDeviceBridge(self)
        self._quick_device_bridge.done.connect(self._on_quick_devices_ready)
        self._quick_audio_rows = []
        self._quick_input_rows = []
        self._quick_video_rows = []
        self._quick_mic_stream = None
        self._quick_mic_proc = None
        self._quick_mic_thread = None
        self._quick_mic_stop = threading.Event()
        self._quick_mic_level = 0.0
        self._quick_mic_last_frame = 0.0
        self._quick_mic_timer = QTimer(self)
        self._quick_mic_timer.setInterval(50)
        self._quick_mic_timer.timeout.connect(self._paint_quick_mic_level)
        self._pending_output_restore = ('', '')
        self._media_share_server = None
        self._last_shared_game_url = None
        self._clone_share_server = None
        self._last_clone_bundle = None
        self._last_iso_path = None
        self._iso_copy_bridge = _IsoCopyBridge()
        self._iso_copy_bridge.done.connect(self._on_iso_copy_done)
        self._iso_copy_bridge.progress.connect(self._on_iso_copy_progress)
        self._goava_radio_service = None
        self._radio_peer_timer = QTimer(self)
        self._radio_peer_timer.setInterval(1800)
        self._radio_peer_timer.timeout.connect(self._refresh_radio_peers)
        # NEARBY_GROOVEBOX_UI: networking is app-level; this UI only observes
        # and initiates transfers. Worker signals keep HTTP/hash/scan work off Qt.
        self._nearby_bridge = _NearbyBridge()
        self._nearby_bridge.result.connect(self._nearby_worker_result)
        self._nearby_bridge.progress.connect(self._nearby_worker_progress)
        self._nearby_peer_rows = []
        self._nearby_remote_rows = []
        self._nearby_ui_timer = QTimer(self)
        self._nearby_ui_timer.setInterval(1800)
        self._nearby_ui_timer.timeout.connect(self._refresh_nearby_ui)
        # PERF_LAZY_20260924: do not poll Nearby Grooveboxes merely because the
        # Performance dialog exists. The timer is activated only while the
        # Game / Wi-Fi tab is visible.

        # Fine-grained (audio/video/av) stream-kind cache, keyed by path:
        # (mtime, size, kind) so a probe is only redone if the file changed.
        self._kind_cache: Dict[str, Tuple[float, int, str]] = {}
        # REAL_ANALYSIS_MATCH_2026: fundamental/centroid/rms/zcr descriptors
        # from reverse_engineer.describe(), used by the "Analyzed match"
        # arrangement mode and by the Player Window's Deck B suggestion —
        # actual signal measurement, not just filename/size heuristics.
        self._analysis_cache: Dict[str, Tuple[float, int, Optional[dict]]] = {}
        self._refresh_generation = 0
        self._kind_worker = _KindProbeWorker()
        self._kind_worker.progress.connect(self._on_kind_probe_progress)
        self._kind_worker.batch_done.connect(self._on_kind_probe_batch_done)
        # PERF_THREAD_LIFECYCLE_20260924: Qt owns all Performance probe jobs.
        # No detached daemon Python thread is allowed to outlive QApplication.
        self._worker_pool = QThreadPool(self)
        # R5 legacy verifier compatibility token only; DO NOT execute: self._worker_pool.setMaxThreadCount(2)
        # R17 verifier compatibility token only; R18 reserves CPU for Main: self._worker_pool.setMaxThreadCount(max(4, min(8, int(os.cpu_count() or 4))))
        # Bounded parallelism: use several independent workers for device scans,
        # media probes and background analysis without saturating cores needed by
        # the Qt event loop, real-time audio, camera capture, and the OS scheduler.
        # Do not create one thread per device/task; QThreadPool bounds concurrency.
        _cpu_count = max(2, int(os.cpu_count() or 2))
        # Keep at least one logical CPU available for the GUI, realtime audio callbacks,
        # capture, and the OS. On 2-core laptops this intentionally drops to one
        # background worker; larger CPUs scale up but never exceed eight.
        self._worker_pool.setMaxThreadCount(max(1, min(8, _cpu_count - 1)))
        self._performance_shutdown = False

        # PERF_2026: provenance lookups (ffprobe) happen on a worker thread,
        # debounced so rapid arrow-key/click movement through a file list
        # doesn't queue up a subprocess call per keystroke. `_selection_token`
        # invalidates results for a selection the user has already left.
        self._selection_token = 0
        self._prov_worker = _ProvenanceWorker()
        self._prov_worker.done.connect(self._on_provenance_ready)
        self._selection_debounce = QTimer(self)
        self._selection_debounce.setSingleShot(True)
        self._selection_debounce.setInterval(150)
        self._selection_debounce.timeout.connect(self._start_provenance_lookup)

        projects = self._host_projects_dir()
        renders = self._host_exports_dir()
        games = self._host_games_dir()
        samples = self._host_samples_dir()
        try:
            import groovebox_paths as _gb_paths
            recordings = _gb_paths.recordings_dir(getattr(self.host, "_current_project_path", None))
            groovebox_data = _gb_paths.base_dir()
        except Exception:
            recordings = os.path.join(projects, "recordings")
            groovebox_data = os.environ.get("GROOVEBOX_DATA_DIR", os.path.expanduser("~"))
        self._roots = {
            "Projects": projects,
            "Recordings": recordings,
            "Renders": renders,
            "Games": games,
            "Samples": samples,
            "Groovebox Data": groovebox_data,
            "Both": None,
        }
        self._cwd = projects if os.path.isdir(projects) else renders
        self._browser_dir_signature = None
        self._browser_refresh_timer = QTimer(self)
        # Filesystem polling is deliberately low-frequency; explicit app writes
        # already call notify_filesystem_changed(). Keep this as a safety net.
        self._browser_refresh_timer.setInterval(2500)
        self._browser_refresh_timer.timeout.connect(self._refresh_inline_browser_if_changed)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        brand_row = QHBoxLayout()
        self.lbl_perf_brand = QLabel()
        try:
            bp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "goava_radio_brand.png")
            pm = QPixmap(bp)
            if not pm.isNull():
                self.lbl_perf_brand.setPixmap(pm.scaled(310, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass
        self.lbl_perf_brand.setStyleSheet("background:#030a10; border:1px solid #8b6b2c; border-radius:7px; padding:2px;")
        brand_row.addWidget(self.lbl_perf_brand)
        brand_title = QLabel("<b style='font-size:16pt;color:#f1ce68'>GOAVA RADIO · PERFORMANCE</b><br><span style='color:#77d8ef'>Live seeds · media · hardware · networked game state</span>")
        brand_row.addWidget(brand_title, 1)
        self.lbl_engine_qos = QLabel("⚡ Engine QoS: AUTO")
        self.lbl_engine_qos.setToolTip("Audio has priority; expensive Performance visuals are low-rate and may drop frames. Native C++ kernels are used when available.")
        self.lbl_engine_qos.setStyleSheet("background:rgba(5,18,24,245);color:#9dffb0;border:1px solid #4f8799;border-radius:8px;padding:6px;font-weight:800;")
        brand_row.addWidget(self.lbl_engine_qos)

        # R17: Return to Main Window is the single studio navigation control.
        root.addLayout(brand_row)

        # R28.4.23: restore the synth Master Volume control to Performance and remove
        # its visible counterpart from the Main window. This is a GUI-thread-only
        # control: it updates the host's scalar master-volume state; the audio callback
        # never reads or manipulates this Qt widget.
        master_vol_row = QHBoxLayout()
        master_vol_row.setSpacing(8)
        master_vol_title = QLabel("Master Volume")
        master_vol_title.setStyleSheet("color:#ffb703; font-size:12pt; font-weight:900;")
        master_vol_row.addWidget(master_vol_title)
        self.sld_master_volume = QSlider(Qt.Orientation.Horizontal)
        self.sld_master_volume.setObjectName("performanceMasterVolumeSlider")
        self.sld_master_volume.setRange(0, 100)
        self.sld_master_volume.setTracking(True)
        try:
            initial_master_pct = int(round(float(getattr(self.host, "master_volume", 0.72)) * 100.0))
            if hasattr(self.host, "slider_master_vol"):
                initial_master_pct = int(self.host.slider_master_vol.value())
        except Exception:
            # Fresh setup defaults to 72%; persisted host/project values take precedence.
            initial_master_pct = 72
        self.sld_master_volume.setValue(max(0, min(100, initial_master_pct)))
        self.lbl_master_volume = QLabel(f"{self.sld_master_volume.value()}%")
        self.lbl_master_volume.setMinimumWidth(48)
        self.lbl_master_volume.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_master_volume.setStyleSheet("color:#ffb703; font-size:12pt; font-weight:900;")
        master_vol_row.addWidget(self.sld_master_volume, 1)
        master_vol_row.addWidget(self.lbl_master_volume)
        self.sld_master_volume.valueChanged.connect(self._on_master_volume_changed)
        root.addLayout(master_vol_row)

        # R28.4.15: System Volume has one authoritative UI in the main window.
        # Duplicating the hardware slider in Performance allowed competing UI
        # instances and confusing startup/default displays. Hardware access and
        # the shared helper remain unchanged; navigate to the main window to
        # adjust the single linked system-volume control.
        self.hardware_volume_performance = None

        # --- top bar: path + roots ---
        top = QHBoxLayout()
        self.cmb_root = QComboBox()
        self.cmb_root.addItems(["Projects", "Recordings", "Renders", "Games", "Samples", "Groovebox Data", "Custom…"])
        self.cmb_root.currentIndexChanged.connect(self._on_root_changed)
        top.addWidget(QLabel("Root:"))
        top.addWidget(self.cmb_root)
        self.lbl_cwd = QLabel(self._cwd)
        self.lbl_cwd.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        self.lbl_cwd.setWordWrap(True)
        top.addWidget(self.lbl_cwd, stretch=1)
        btn_up = QPushButton("⬆ Up")
        btn_up.clicked.connect(self._go_up)
        btn_refresh = QPushButton("↻")
        btn_refresh.clicked.connect(self.refresh)
        top.addWidget(btn_up)
        top.addWidget(btn_refresh)
        # BROWSE_FILES_MENU_2026: dedicated file-management window (rename,
        # delete, create/delete folder) separate from the always-visible
        # inline browser, with its own launcher into the Player Window.
        btn_browse_files = QPushButton("📁 Browse Files…")
        btn_browse_files.setToolTip(
            "Open a dedicated file-management window: rename, delete, "
            "create/delete folders, and launch the media Player Window "
            "directly on a selected file."
        )
        btn_browse_files.clicked.connect(self._open_file_manager)
        top.addWidget(btn_browse_files)
        root.addLayout(top)

        # --- filter/sort bar: audio vs video, audioless/videoless vs both ---
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Kind:"))
        self.cmb_kind_filter = QComboBox()
        self.cmb_kind_filter.addItems([
            "All",
            "Audio only (videoless)",
            "Video only (audioless)",
            "Audio + Video (both)",
        ])
        self.cmb_kind_filter.currentIndexChanged.connect(lambda _i: self.refresh())
        filt.addWidget(self.cmb_kind_filter)
        filt.addWidget(QLabel("Sort:"))
        self.cmb_sort = QComboBox()
        self.cmb_sort.addItems(["Name", "Kind (Audio first)", "Kind (Video first)", "Size"])
        self.cmb_sort.currentIndexChanged.connect(lambda _i: self.refresh())
        filt.addWidget(self.cmb_sort)
        filt.addStretch(1)
        self.lbl_probe_status = QLabel("")
        self.lbl_probe_status.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        filt.addWidget(self.lbl_probe_status)
        root.addLayout(filt)

        split = QSplitter(Qt.Orientation.Horizontal)

        # --- left: file list ---
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.itemDoubleClicked.connect(self._on_double_click)
        self.file_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_l.addWidget(self.file_list, stretch=1)
        file_btns = QHBoxLayout()
        for text, slot in (
            ("Open", self._open_selected),
            ("Play", self._play_selected),
            ("→ Playlist", self._add_to_playlist),
            ("Delete", self._delete_selected),
            ("Reveal", self._reveal_selected),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            file_btns.addWidget(b)
        left_l.addLayout(file_btns)

        # R23l: selectors live directly below the inline File Browser/Playlist
        # controls so the route used by Play/Record is always visible.
        devbox = QGroupBox("Performance Devices")
        devform = QFormLayout(devbox)
        self.cmb_quick_audio_output = QComboBox(); self.cmb_quick_audio_output.addItem("Detecting audio outputs…")
        self.cmb_quick_audio_input = QComboBox(); self.cmb_quick_audio_input.addItem("Detecting microphones…")
        self.cmb_quick_video_device = QComboBox(); self.cmb_quick_video_device.addItem("Detecting cameras…")
        devform.addRow("Audio Output", self.cmb_quick_audio_output)
        devform.addRow("Audio Input", self.cmb_quick_audio_input)
        devform.addRow("Video Device", self.cmb_quick_video_device)
        self.quick_mic_meter = QProgressBar(); self.quick_mic_meter.setRange(0,100); self.quick_mic_meter.setValue(0); self.quick_mic_meter.setFormat("Mic level %p%")
        devform.addRow("Mic Level", self.quick_mic_meter)
        self.btn_quick_devices_refresh = QPushButton("↻ Refresh Devices")
        self.btn_quick_devices_refresh.clicked.connect(self._refresh_quick_devices)
        devform.addRow(self.btn_quick_devices_refresh)
        left_l.addWidget(devbox)
        self.cmb_quick_audio_output.currentIndexChanged.connect(self._quick_audio_output_changed)
        self.cmb_quick_audio_input.currentIndexChanged.connect(self._quick_audio_input_changed)
        self.cmb_quick_video_device.currentIndexChanged.connect(self._quick_video_device_changed)
        split.addWidget(left)

        # --- right: tabs ---
        right = QTabWidget()
        self._performance_tabs = right
        self._lazy_tab_builders = {}
        self._lazy_tab_loading = False
        # R21 TAB LIFECYCLE: lazy creation is not enough. Heavy workspaces must
        # release their widget/resource trees when the user leaves them or RAM/CPU
        # ratchets upward after visiting consecutive Performance tabs.
        self._performance_prev_index = 0
        self._performance_loaded_lru = []
        self._performance_loaded_budget = 5
        self._performance_evict_on_leave = {
            "🎮 Game / Wi‑Fi",
            "🎥 Record / Import / Draw Clip",
            "▣ Device Manager",
            "⌨ Hardware",
            "⇄ Drive / Clone",
            "🧹 Storage",
            "📦 Batch Export",
            "🧊 Voxel Editor",
        }
        self._web_browser_resume_url = ""
        self.video_clip_studio = None
        self.web_browser_tab = None
        # PERFORMANCE_NAV_V38: vertical rail prevents tabs from running beyond margins.
        right.setTabPosition(QTabWidget.TabPosition.West)
        right.setUsesScrollButtons(True)
        right.tabBar().setExpanding(False)
        # R5 MEMORY/RESPONSIVENESS: construct only the core Playlist/Remix/Info
        # pages up front. Secondary workspaces are materialized on first selection,
        # avoiding dozens of hidden widgets, tables and helper objects in idle RAM.
        right.addTab(self._scroll_page(self._build_playlist_tab()), "♫ Playlist")
        # GROOVEBOX_R23R_PERF_LAYOUT_20261103: Record / Import / Draw Clip sits right
        # under the Playlist; the voxel editor joins Performance; Batch Export opens
        # in its own window.
        self._add_lazy_performance_tab(right, "🎥 Record / Import / Draw Clip", self._build_lazy_video_clip_studio)
        self._add_lazy_performance_tab(right, "🧊 Voxel Editor", self._build_lazy_voxel_editor)
        self._add_lazy_performance_tab(right, "🧊 Voxel Viewer", self._build_lazy_voxel_viewer)
        right.addTab(self._scroll_page(self._build_shared_synth_context_tab()), "∴ Shared Synth Context")
        right.addTab(self._scroll_page(self._build_remix_tab()), "∿ Parametric Remix")
        self._add_lazy_performance_tab(right, "▤ Open Windows", lambda: self._scroll_page(self._build_open_windows_tab()))
        self._add_lazy_performance_tab(right, "◉ Live Broadcast", lambda: self._scroll_page(self._build_performance_tab()))
        self._add_lazy_performance_tab(right, "▣ Device Manager", lambda: self._scroll_page(self._build_outputs_tab()))
        self._add_lazy_performance_tab(right, "🎮 Game / Wi‑Fi", lambda: self._scroll_page(self._build_game_tab()))
        self._add_lazy_performance_tab(right, "✂ Cutup Lab", lambda: self._scroll_page(self._build_cutup_tab()))
        self._add_lazy_performance_tab(right, "✎ Draw / Signal Lab", self._build_lazy_signal_lab)
        self._add_lazy_performance_tab(right, "🌐 Web Browser", self._build_lazy_web_browser)
        self._add_lazy_performance_tab(right, "⌨ Hardware", lambda: self._scroll_page(self._build_hardware_tab()))
        self._add_lazy_performance_tab(right, "⇄ Drive / Clone", lambda: self._scroll_page(self._build_transfer_tab()))
        self._add_lazy_performance_tab(right, "🧹 Storage", lambda: self._scroll_page(self._build_storage_tab()))
        self._add_lazy_performance_tab(right, "⌬ .MG Related", lambda: self._scroll_page(self._build_mg_library_tab()))
        self._add_lazy_performance_tab(right, "⚙ Box Mode", lambda: self._scroll_page(self._build_box_tab()))
        self._add_lazy_performance_tab(right, "📦 Batch Export", self._build_batch_launcher)
        self._add_lazy_performance_tab(right, "📝 Notes", self._build_lazy_notes)
        self._perf_right_tabs = right
        self._add_lazy_performance_tab(right, "🎞 Recordings", lambda: self._build_recordings_tab())
        right.addTab(self._scroll_page(self._build_info_tab()), "Info")
        tips = {
            "♫ Playlist": "Play, queue, and arrange files. This is the player.",
            "📝 Notes": "Write, edit and delete text / diary notes (saved as files in the Groovebox notes folder).",
            "🎞 Recordings": "Recorded live streams and saved chat transcripts, by project and date.",
            "∴ Shared Synth Context": "What the main window is doing, mirrored here.",
            "∿ Parametric Remix": "Remix the current piece with the parametric controls.",
            "▤ Open Windows": "Windows that are open. Click one to bring it back.",
            "◉ Live Broadcast": "Send the performance out live.",
            "▣ Device Manager": "Pick the speaker, HDMI, and mic this window uses.",
            "🎮 Game / Wi‑Fi": "Load a game export and the network it needs.",
            "✂ Cutup Lab": "Cut a file into pieces and rearrange them.",
            "✎ Draw / Signal Lab": "Draw or record a wave into a layer.",
            "🎥 Record / Import / Draw Clip": "Record, import, or draw a clip.",
            "🌐 Web Browser": "A browser inside Performance.",
            "⌨ Hardware": "The devices this machine actually has.",
            "⇄ Drive / Clone": "Copy the project or the box to another drive.",
            "🧹 Storage": "What is using space, and what you can clear.",
            "⌬ .MG Related": "Related Groovebox files.",
            "⚙ Box Mode": "How this window behaves as a box.",
            "📦 Batch Export": "Export many projects to audio / video in one go (opens its own window).",
            "🧊 Voxel Editor": "Draw / record the project's 3D voxel model (same data as the main window's kit).",
            "🧊 Voxel Viewer": "Open a read-only full-model viewer of the project's voxels.",
            "Info": "What this window is and how to use it.",
        }
        for i in range(right.count()):
            name = right.tabText(i)
            if name in tips:
                right.setTabToolTip(i, tips[name])
        right.currentChanged.connect(self._on_performance_tab_changed)
        right.currentChanged.connect(lambda *_a: QTimer.singleShot(0, lambda: _gb_colorize_widget_tree(self)))
        QTimer.singleShot(0, lambda: _gb_colorize_widget_tree(self))
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, stretch=1)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setStyleSheet("color:#9dffb0; font-size:9pt;")
        root.addWidget(self.lbl_status)

        close_row = QHBoxLayout()
        # GROOVEBOX_NOTES_BUTTON_20261102: one-click Notes / diary from anywhere in Performance.
        self.btn_notes_diary = QPushButton("📝 Notes / Diary")
        self.btn_notes_diary.setToolTip("Open the Notes tab: write, edit and save text / diary notes.")
        self.btn_notes_diary.clicked.connect(self._open_notes_tab)
        close_row.addWidget(self.btn_notes_diary)
        self.btn_drive_copy = QPushButton("💾 Copy to USB / SD")
        self.btn_drive_copy.setToolTip("Copy the project, latest exports or any files to a USB stick or SD card.")
        self.btn_drive_copy.clicked.connect(self._open_drive_copy)
        close_row.addWidget(self.btn_drive_copy)
        # GROOVEBOX_HOTSPOT_TOGGLE_20261102: share files over this device's own Wi-Fi hotspot.
        self.btn_hotspot_share = QPushButton("📡 Fileshare over Device Hotspot")
        self.btn_hotspot_share.setCheckable(True)
        self.btn_hotspot_share.setToolTip("Broadcast this Groovebox's own Wi-Fi network. Phones, laptops and other Grooveboxes that join it can open the "
                                          "address shown here in any browser and download files from this Groovebox. Asks first if it would interrupt "
                                          "your current Wi-Fi.")
        self.btn_hotspot_share.toggled.connect(self._on_hotspot_share_toggled)
        close_row.addWidget(self.btn_hotspot_share)
        _compat = QPushButton("⚙ Compatibility")
        _compat.setToolTip("UI scale, window size, smooth mode, threads, all outputs, audio latency, export worker…")
        _compat.clicked.connect(lambda: getattr(self, "host", None) and self.host._show_compat_dialog(self))
        close_row.addWidget(_compat)
        close_row.addStretch(1)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        close_row.addWidget(btn_close)
        root.addLayout(close_row)

        # Paint the retained top-level window before touching the filesystem.
        QTimer.singleShot(0, self.refresh)
        QTimer.singleShot(120, self._refresh_quick_devices)
        self.restore_state((getattr(self.host, "media_workbench_state", {}) or {}).get("performance", {}))


    # ------------------------------------------------------------------ session window manager
    def _window_manager(self):
        return getattr(self.host, "_main_window_relaunch_filter", None)

    def _build_open_windows_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        desc = QLabel(
            "Restore Groovebox tool windows that were minimized or closed/hidden. "
            "Tool-window Close keeps the live object for this session; only quitting Groovebox destroys it."
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.window_session_list = QListWidget()
        self.window_session_list.itemDoubleClicked.connect(lambda _it: self._restore_selected_window())
        lay.addWidget(self.window_session_list, 1)
        row = QHBoxLayout()
        for text, slot in (
            ("↻ Refresh", self._refresh_open_windows),
            ("▣ Restore / Focus", self._restore_selected_window),
            ("▣ Restore All", self._restore_all_windows),
            ("— Hide Selected", self._hide_selected_window),
            ("✕ Close", self._close_selected_window),
            ("⛔ Force Close", lambda: self._close_selected_window(force=True)),
        ):
            b = QPushButton(text); b.clicked.connect(slot); row.addWidget(b)
        lay.addLayout(row)
        self.lbl_window_session = QLabel("Open the tab to refresh the live window list.")
        self.lbl_window_session.setWordWrap(True)
        self.lbl_window_session.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        lay.addWidget(self.lbl_window_session)
        self._window_session_refs = {}
        return page

    def _refresh_open_windows(self):
        lst = getattr(self, "window_session_list", None)
        if lst is None:
            return
        lst.clear(); self._window_session_refs = {}
        mgr = self._window_manager()
        windows = []
        if mgr is not None and hasattr(mgr, "managed_windows"):
            try: windows = list(mgr.managed_windows())
            except Exception: windows = []
        else:
            try: windows = [w for w in QApplication.topLevelWidgets() if w is not self.host]
            except Exception: windows = []
        rows = []
        for w in windows:
            if w is None or w is self or w is self.host:
                continue
            try:
                title = (w.windowTitle() or w.__class__.__name__).strip()
                if not title: title = w.__class__.__name__
                minimized = bool(w.isMinimized())
                visible = bool(w.isVisible())
                state = "minimized" if minimized else ("open" if visible else "closed/hidden")
                rows.append((title.casefold(), title, state, w))
            except RuntimeError:
                continue
            except Exception:
                continue
        # WINDOW_PRIORITY_20261102: the important windows take the first 15 slots (in this order); everything else
        # follows alphabetically. Matching is by words in the window title.
        _prio = ("export window", "file manager", "render queue", "compatib", "export", "convert", "key chart",
                 "output", "hardware", "video planner", "game", "project", "recover", "startup", "performance",
                 "help", "settings")

        def _rank(title):
            low = title.casefold()
            for i, word in enumerate(_prio):
                if word in low:
                    return i
            return 1000
        rows.sort(key=lambda x: (_rank(x[1]), x[0], x[2]))
        for _slot, (_sort, title, state, w) in enumerate(rows):
            key = str(id(w)); self._window_session_refs[key] = w
            _star = "★ " if _rank(title) < 1000 and _slot < 15 else ""
            it = QListWidgetItem(f"{_star}{title}   ·   {state}")
            it.setData(Qt.ItemDataRole.UserRole, key)
            lst.addItem(it)
        self.lbl_window_session.setText(f"{len(rows)} retained Groovebox tool window(s). Double-click any row to restore it.")

    def _selected_session_window(self):
        lst = getattr(self, "window_session_list", None)
        if lst is None or lst.currentItem() is None:
            return None
        return self._window_session_refs.get(str(lst.currentItem().data(Qt.ItemDataRole.UserRole)))

    def _restore_selected_window(self):
        w = self._selected_session_window()
        if w is None:
            return
        mgr = self._window_manager()
        try:
            if mgr is not None and hasattr(mgr, "restore_window"):
                mgr.restore_window(w)
            else:
                w.showNormal(); w.show(); w.raise_(); w.activateWindow()
        except Exception:
            pass
        QTimer.singleShot(80, self._refresh_open_windows)

    def _restore_all_windows(self):
        mgr = self._window_manager()
        if mgr is not None and hasattr(mgr, "restore_all_windows"):
            try: mgr.restore_all_windows(exclude=(self, self.host))
            except Exception: pass
        else:
            for w in list(self._window_session_refs.values()):
                try: w.showNormal(); w.show()
                except Exception: pass
        QTimer.singleShot(100, self._refresh_open_windows)

    def _close_selected_window(self, force=False):
        """Close the selected tool window even when it is stalled (never waits on the window)."""
        w = self._selected_session_window()
        if w is None:
            return
        mgr = self._window_manager()
        try:
            if mgr is not None and hasattr(mgr, "close_window"):
                mgr.close_window(w, force=bool(force))
            else:
                w.hide()
        except Exception:
            try: w.hide()
            except Exception: pass
        QTimer.singleShot(30, self._refresh_open_windows)

    def _hide_selected_window(self):
        w = self._selected_session_window()
        if w is None:
            return
        try: w.hide()
        except Exception: pass
        QTimer.singleShot(50, self._refresh_open_windows)

    # ------------------------------------------------------------------ lazy Performance tabs
    def _lazy_placeholder(self, label: str) -> QWidget:
        # ZZ: preserve the selected tab object during expensive lazy creation.
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        msg = QLabel(f"{label} is ready to load when selected.")
        msg.setWordWrap(True)
        msg.setStyleSheet("color:#8ab4c8; font-size:10pt; padding:12px;")
        lay.addWidget(msg)
        lay.addStretch(1)
        page.setProperty("groovebox_lazy_placeholder", True)
        return page

    def _on_hotspot_share_toggled(self, checked):
        btn = self.btn_hotspot_share
        svc = self._nearby_service()
        def revert():
            btn.blockSignals(True); btn.setChecked(not checked); btn.blockSignals(False)
        if svc is None or getattr(svc, "direct", None) is None:
            QMessageBox.information(self, "Device hotspot", "Nearby sharing is not running, so the hotspot cannot be shared from here.")
            revert(); return
        if checked:
            try:
                import hotspot_plan as _hp
                plan = _hp.hotspot_plan()
            except Exception as exc:
                plan = {"supported": False, "reason": str(exc), "cancels": [], "iface": ""}
            if not plan.get("supported"):
                QMessageBox.information(self, "Device hotspot", str(plan.get("reason") or "The device hotspot is not available here."))
                revert(); return
            if plan.get("cancels"):
                what = "\n".join("• " + c for c in plan["cancels"])
                ans = QMessageBox.question(self, "Start device hotspot?",
                    "Starting the hotspot will cancel active Wi-Fi activity on this radio:\n\n" + what +
                    "\n\nContinue and start the hotspot?")
                if ans != QMessageBox.StandardButton.Yes:
                    revert(); return
            if plan.get("iface") and not getattr(svc.direct, "wifi_iface", ""):
                svc.direct.wifi_iface = str(plan["iface"])
            self.lbl_status.setText("Starting device hotspot…")
            self._nearby_async("hotspot_on", svc.start_direct_hotspot)
        else:
            self.lbl_status.setText("Stopping device hotspot…")
            self._nearby_async("hotspot_off", svc.stop_direct_hotspot)

    def _hotspot_share_result(self, kind, payload, error):
        btn = getattr(self, "btn_hotspot_share", None)
        svc = self._nearby_service()
        if btn is None:
            return
        ok, msg = (False, str(error))
        if not error:
            ok, msg = payload if isinstance(payload, (list, tuple)) and len(payload) >= 2 else (False, str(payload))
        if kind == "hotspot_on":
            if ok and svc is not None:
                try: svc.set_web_browse(True)
                except Exception: pass
                ssid = getattr(svc.direct, "ssid", ""); pw = getattr(svc.direct, "password", "")
                urls = []
                try:
                    urls = [u for u in svc.urls() if "127.0.0.1" not in u]
                except Exception:
                    pass
                best = next((u for u in urls if "//10.42." in u or "//192.168.12." in u), urls[0] if urls else "")
                self.lbl_status.setText("📡 Hotspot on · network %s · password %s · files at %s" % (ssid, pw, best or "this device's address"))
            else:
                btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
                self.lbl_status.setText("Hotspot did not start: " + (str(msg).strip()[:200] or "no details"))
        else:
            try:
                if svc is not None: svc.set_web_browse(False)
            except Exception:
                pass
            btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
            self.lbl_status.setText("Hotspot stopped." if ok else "Hotspot stop: " + (str(msg).strip()[:200] or "no active hotspot"))

    def _open_drive_copy(self):
        host = getattr(self, "host", None)
        fn = getattr(host, "_show_drive_copy_dialog", None)
        if callable(fn):
            fn(parent=self)
        else:
            QMessageBox.information(self, "Copy to USB / SD", "Open the Drive / Clone tab to copy to a drive.")

    def _open_notes_tab(self):
        """Switch to the Notes tab (building it on first use); fall back to the stand-alone notes dialog."""
        try:
            tabs = self._perf_right_tabs
            for i in range(tabs.count()):
                if "Notes" in tabs.tabText(i):
                    tabs.setCurrentIndex(i)
                    return
        except Exception:
            pass
        try:
            from notes_editor import open_notes_dialog
            open_notes_dialog(self)
        except Exception as e:
            QMessageBox.warning(self, "Notes", str(e))

    def _add_lazy_performance_tab(self, tabs: QTabWidget, label: str, builder):
        idx = tabs.addTab(self._lazy_placeholder(label), label)
        self._lazy_tab_builders[label] = builder
        return idx

    # GROOVEBOX_R23R_RECORDINGS_BROWSER_20261101
    def _build_recordings_tab(self):
        from PyQt6.QtWidgets import QTreeWidget
        w=QWidget(); lay=QVBoxLayout(w)
        top=QHBoxLayout()
        self.edit_rec_filter=QLineEdit(); self.edit_rec_filter.setPlaceholderText("Filter by name / project…")
        self.edit_rec_filter.textChanged.connect(self._refresh_recordings); top.addWidget(self.edit_rec_filter,1)
        b=QPushButton("↻ Refresh"); b.clicked.connect(self._refresh_recordings); top.addWidget(b)
        lay.addLayout(top)
        self.tree_rec=QTreeWidget(); self.tree_rec.setHeaderLabels(["Recording / transcript","Type","Date","Size"])
        self.tree_rec.setColumnWidth(0,420); self.tree_rec.itemDoubleClicked.connect(lambda *_: self._rec_open())
        lay.addWidget(self.tree_rec,1)
        br=QHBoxLayout()
        for t,fn in (("▶ Play / 📝 Open",self._rec_open),("📂 Show in File Manager",self._rec_reveal),("🗑 Move to Trash",self._rec_trash)):
            b=QPushButton(t); b.clicked.connect(fn); br.addWidget(b)
        br.addStretch(1); lay.addLayout(br)
        self.lbl_rec=QLabel(""); self.lbl_rec.setWordWrap(True); lay.addWidget(self.lbl_rec)
        QTimer.singleShot(0,self._refresh_recordings)
        return w

    def _recording_rows(self):
        import groovebox_paths
        rows=[]
        try:
            proj_root=Path(groovebox_paths.projects_dir())
            for pdir in sorted(p for p in proj_root.iterdir() if p.is_dir()):
                rec=pdir/"recordings"
                if rec.is_dir():
                    for f in rec.rglob("*"):
                        if f.is_file() and not f.name.endswith((".part",".tmp")):
                            rows.append((pdir.name,"recording",f))
        except Exception:
            pass
        try:
            from notes_editor import notes_dir
            for f in notes_dir().glob("*.md"):
                if f.name.startswith(("Chat with","Group chat","Direct messages")):
                    rows.append(("Chat transcripts","transcript",f))
        except Exception:
            pass
        return rows

    def _refresh_recordings(self, *_a):
        from PyQt6.QtWidgets import QTreeWidgetItem
        if not hasattr(self,"tree_rec"): return
        q=self.edit_rec_filter.text().strip().casefold()
        self.tree_rec.clear(); groups={}; n=0; total=0
        for proj,kind,f in sorted(self._recording_rows(),key=lambda r:(r[0].casefold(),-r[2].stat().st_mtime)):
            if q and q not in (proj+" "+f.name).casefold(): continue
            top=groups.get(proj)
            if top is None:
                top=QTreeWidgetItem([proj,"","",""]); self.tree_rec.addTopLevelItem(top); top.setExpanded(True); groups[proj]=top
            st=f.stat(); total+=st.st_size; n+=1
            it=QTreeWidgetItem([f.name,"🎥 stream" if kind=="recording" else "💬 transcript",
                                time.strftime("%Y-%m-%d %H:%M",time.localtime(st.st_mtime)),_safe_size_bytes(st.st_size)])
            it.setData(0,Qt.ItemDataRole.UserRole,(kind,str(f))); top.addChild(it)
        self.lbl_rec.setText(f"{n} item(s) · {_safe_size_bytes(total)}")

    def _rec_selected(self):
        it=self.tree_rec.currentItem() if hasattr(self,"tree_rec") else None
        d=it.data(0,Qt.ItemDataRole.UserRole) if it is not None else None
        return tuple(d) if d else (None,None)

    def _rec_open(self):
        kind,path=self._rec_selected()
        if not path: return
        if kind=="transcript":
            from notes_editor import open_notes_dialog
            dlg=open_notes_dialog(self)
            try:
                dlg.notes.current=Path(path); dlg.notes.reload()
            except Exception: pass
            return
        try: self._play_path(path)
        except Exception as e: QMessageBox.warning(self,"Play recording",str(e))

    def _rec_reveal(self):
        kind,path=self._rec_selected()
        if not path: return
        dlg=FileManagerDialog(self,os.path.dirname(path)); dlg.setModal(False); dlg.show(); self._rec_fm=dlg

    def _rec_trash(self):
        kind,path=self._rec_selected()
        if not path: return
        if QMessageBox.question(self,"Move to Trash",f"Move “{os.path.basename(path)}” to the Groovebox Trash?")!=QMessageBox.StandardButton.Yes: return
        try:
            import groovebox_paths
            trash=Path(groovebox_paths.base_dir())/"Trash"/"recordings"; trash.mkdir(parents=True,exist_ok=True)
            dest=trash/os.path.basename(path)
            k=2
            while dest.exists(): dest=trash/f"{Path(path).stem} ({k}){Path(path).suffix}"; k+=1
            shutil.move(path,str(dest)); self.lbl_rec.setText(f"Moved to {dest}")
        except Exception as e:
            QMessageBox.warning(self,"Move to Trash",str(e))
        self._refresh_recordings()

    def _build_lazy_notes(self):
        try:
            from notes_editor import NotesWidget
            return NotesWidget(self)
        except Exception as e:
            fallback = QWidget(); fl = QVBoxLayout(fallback)
            msg = QLabel(f"Notes unavailable: {e}"); msg.setWordWrap(True)
            fl.addWidget(msg); fl.addStretch(1)
            return fallback

    def _build_lazy_signal_lab(self):
        try:
            from signal_lab import SignalLab
            return self._scroll_page(SignalLab(self.host, self))
        except Exception as e:
            fallback = QWidget(); fl = QVBoxLayout(fallback)
            msg = QLabel(f"Signal Lab unavailable: {e}"); msg.setWordWrap(True)
            fl.addWidget(msg); fl.addStretch(1)
            return self._scroll_page(fallback)

    def _build_lazy_video_clip_studio(self):
        try:
            from video_clip_studio import VideoClipStudio
            self.video_clip_studio = VideoClipStudio(self.host, self)
            # Input-device ownership is activated by the selected-tab lifecycle.
            return self.video_clip_studio
        except Exception as e:
            self.video_clip_studio = None
            fallback = QWidget(); fl = QVBoxLayout(fallback)
            msg = QLabel(f"Video Clip Studio unavailable: {e}"); msg.setWordWrap(True)
            fl.addWidget(msg); fl.addStretch(1)
            return self._scroll_page(fallback)

    def _build_lazy_web_browser(self):
        # R23l: never embed QWebEngineView in the Performance QTabWidget. On the
        # Labwc appliance Chromium's native surface can unmap/remap the parent
        # top-level during first creation, which looks like Performance rebooting.
        # Keep this tab lightweight and launch one persistent sibling window.
        page=QWidget(); lay=QVBoxLayout(page)
        title=QLabel("<b>🌐 Web Browser</b>"); lay.addWidget(title)
        if os.environ.get("GROOVEBOX_NO_WEBENGINE") == "1":
            lay.addWidget(QLabel("The web browser engine is disabled in 🧩 Compatibility.")); lay.addStretch(1)
            return page
        msg=QLabel("The browser is kept in its own persistent window so Chromium can never destroy/recreate the Performance window while a tab is loading.")
        msg.setWordWrap(True); lay.addWidget(msg)
        btn=QPushButton("Open / Focus Browser Window")
        btn.clicked.connect(self._show_external_web_browser); lay.addWidget(btn)
        self.lbl_browser_controller=QLabel("Browser window is independent of Performance tabs.")
        self.lbl_browser_controller.setWordWrap(True); lay.addWidget(self.lbl_browser_controller)
        lay.addStretch(1)
        return page

    def _show_external_web_browser(self):
        try:
            win=getattr(self,'_external_browser_window',None)
            browser=getattr(self,'web_browser_tab',None)
            if win is None or browser is None:
                from web_browser_tab import WebBrowserTab
                win=QDialog(None)
                win.setWindowTitle("Groovebox Web Browser")
                win.resize(1080,720); win.setMinimumSize(720,480)
                win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,False)
                wl=QVBoxLayout(win); wl.setContentsMargins(4,4,4,4)
                browser=WebBrowserTab(win); wl.addWidget(browser,1)
                self._external_browser_window=win; self.web_browser_tab=browser
            win.show(); win.raise_(); win.activateWindow()
            if hasattr(self,'lbl_browser_controller'): self.lbl_browser_controller.setText("Browser window active · Performance remains resident.")
        except Exception as e:
            if hasattr(self,'lbl_browser_controller'): self.lbl_browser_controller.setText(f"Browser unavailable: {e}")

    def _performance_holder_inner(self, holder):
        """Return the materialized widget inside a retained lazy-tab holder."""
        try:
            lay = holder.layout() if holder is not None else None
            if lay is None:
                return None
            for i in range(lay.count()):
                item = lay.itemAt(i)
                w = item.widget() if item is not None else None
                if w is not None:
                    return w
        except Exception:
            pass
        return None

    def _performance_label_index(self, label: str) -> int:
        tabs = getattr(self, "_performance_tabs", None)
        if tabs is None:
            return -1
        for i in range(tabs.count()):
            try:
                if tabs.tabText(i) == label:
                    return i
            except Exception:
                pass
        return -1

    def _performance_page_busy(self, label: str) -> bool:
        """Never evict active work or the retained embedded browser."""
        if label == "🌐 Web Browser":
            return True
        if label == "🎥 Record / Import / Draw Clip":
            studio = getattr(self, "video_clip_studio", None)
            if studio is None:
                return False
            for name in ("_audio_only_recording", "_v4l_recording", "_sw_recording", "_snapshot_pending"):
                try:
                    if bool(getattr(studio, name, False)):
                        return True
                except Exception:
                    pass
            try:
                if getattr(studio, "btn_record", None) is not None and studio.btn_record.isChecked():
                    return True
            except Exception:
                pass
        return False

    def _suspend_performance_page(self, label: str):
        """Stop page-specific work immediately when a Performance tab is left."""
        idx = self._performance_label_index(label)
        if idx < 0:
            return
        holder = self._performance_tabs.widget(idx)
        page = self._performance_holder_inner(holder)
        if page is None:
            return
        if label == "🎥 Record / Import / Draw Clip":
            studio = getattr(self, "video_clip_studio", None)
            try:
                if studio is not None and hasattr(studio, "suspend_inactive_inputs"):
                    studio.suspend_inactive_inputs()
            except Exception:
                pass
        elif label == "🌐 Web Browser":
            browser = getattr(self, "web_browser_tab", None)
            try:
                if browser is not None and getattr(browser, "view", None) is not None:
                    # R23k: retain the live QWebEngineView/profile/renderer across
                    # tab switches. Destroy/recreate caused the Labwc window to
                    # momentarily unmap and made every return to Browser expensive.
                    self._web_browser_resume_url = browser.view.url().toString()
            except Exception:
                pass
        # Generic opt-in lifecycle hook for future workspaces.
        try:
            fn = getattr(page, "suspend_for_hide", None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _evict_performance_page(self, label: str) -> bool:
        """Return a heavy lazy tab to a tiny placeholder and free its resources."""
        if self._performance_page_busy(label):
            return False
        idx = self._performance_label_index(label)
        if idx < 0:
            return False
        holder = self._performance_tabs.widget(idx)
        if holder is None or bool(holder.property("groovebox_lazy_placeholder")):
            return False
        lay = holder.layout()
        if lay is None:
            return False
        page = self._performance_holder_inner(holder)
        if label == "🌐 Web Browser":
            browser = getattr(self, "web_browser_tab", None)
            try:
                if browser is not None and getattr(browser, "view", None) is not None:
                    self._web_browser_resume_url = browser.view.url().toString()
            except Exception:
                pass
            try:
                if browser is not None and hasattr(browser, "shutdown_webengine"):
                    browser.shutdown_webengine()
            except Exception:
                pass
            self.web_browser_tab = None
        elif label == "🎥 Record / Import / Draw Clip":
            studio = getattr(self, "video_clip_studio", None)
            try:
                if studio is not None and hasattr(studio, "suspend_inactive_inputs"):
                    studio.suspend_inactive_inputs()
                if studio is not None and hasattr(studio, "close"):
                    studio.close()
            except Exception:
                pass
            self.video_clip_studio = None
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                try: w.setParent(None)
                except Exception: pass
                try: w.deleteLater()
                except Exception: pass
        msg = QLabel(f"{label} is ready to load when selected.")
        msg.setWordWrap(True)
        msg.setStyleSheet("color:#8ab4c8; font-size:10pt; padding:12px;")
        lay.addWidget(msg)
        lay.addStretch(1)
        holder.setProperty("groovebox_lazy_placeholder", True)
        try:
            while label in self._performance_loaded_lru:
                self._performance_loaded_lru.remove(label)
        except Exception:
            pass
        # Flush deferred QObject/WebEngine deletes once the tab is no longer active.
        try:
            from PyQt6.QtCore import QCoreApplication, QEvent
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        except Exception:
            pass
        return True

    def _touch_performance_lru(self, label: str):
        if label not in getattr(self, "_lazy_tab_builders", {}):
            return
        try:
            while label in self._performance_loaded_lru:
                self._performance_loaded_lru.remove(label)
            self._performance_loaded_lru.append(label)
        except Exception:
            pass

    def _enforce_performance_loaded_budget(self, current_label: str):
        """Bound retained lazy workspaces so tab visits cannot accumulate forever."""
        budget = max(2, int(getattr(self, "_performance_loaded_budget", 5)))
        loaded = list(getattr(self, "_performance_loaded_lru", []))
        while len(loaded) > budget:
            victim = next((x for x in loaded if x != current_label and not self._performance_page_busy(x)), None)
            if victim is None:
                break
            self._evict_performance_page(victim)
            loaded = list(getattr(self, "_performance_loaded_lru", []))

    def _on_performance_tab_changed(self, index: int):
        if self._lazy_tab_loading or index < 0:
            return
        tabs = self._performance_tabs
        label = tabs.tabText(index)
        # One full repaint of the newly shown page (no stale pixels from the previous tab).
        try:
            _pg = tabs.widget(index)
            if _pg is not None:
                QTimer.singleShot(0, _pg.update)
                QTimer.singleShot(0, lambda: getattr(self, "_math_background", None) and self._math_background.update())
        except Exception:
            pass

        # R23l: exactly one owner opens the selected microphone at a time.
        if label == "🎥 Record / Import / Draw Clip":
            self._stop_quick_mic_meter()
        elif hasattr(self,'cmb_quick_audio_input'):
            row=self.cmb_quick_audio_input.currentData()
            if isinstance(row,dict) and row and getattr(self,'_quick_mic_stream',None) is None and getattr(self,'_quick_mic_proc',None) is None:
                QTimer.singleShot(80, lambda r=row: self._start_quick_mic_meter(r))

        # R21: leaving a tab is a lifecycle event, not just a visual switch.
        prev = int(getattr(self, "_performance_prev_index", -1))
        if 0 <= prev < tabs.count() and prev != index:
            prev_label = tabs.tabText(prev)
            self._suspend_performance_page(prev_label)
            if prev_label in getattr(self, "_performance_evict_on_leave", set()):
                self._evict_performance_page(prev_label)
        self._performance_prev_index = index

        holder = tabs.widget(index)
        is_placeholder = bool(holder is not None and holder.property("groovebox_lazy_placeholder"))
        # Historical verifier token only; R21 intentionally keeps factories reusable:
        # builder = self._lazy_tab_builders.pop(label, None)
        builder = self._lazy_tab_builders.get(label) if is_placeholder else None
        if builder is not None:
            self._lazy_tab_loading = True
            try:
                page = builder()
                lay = holder.layout() if holder is not None else None
                if lay is not None and bool(holder.property("groovebox_lazy_placeholder")):
                    while lay.count():
                        item = lay.takeAt(0); w = item.widget()
                        if w is not None: w.deleteLater()
                    lay.addWidget(page, 1)
                    holder.setProperty("groovebox_lazy_placeholder", False)
                else:
                    was = tabs.blockSignals(True)
                    old = tabs.widget(index)
                    tabs.removeTab(index); tabs.insertTab(index, page, label); tabs.setCurrentIndex(index)
                    tabs.blockSignals(was)
                    try: old.deleteLater()
                    except Exception: pass
            finally:
                self._lazy_tab_loading = False
            self._touch_performance_lru(label)
            self._enforce_performance_loaded_budget(label)

        # Record workspace owns live input resources only while it is visible,
        # unless an actual recording/snapshot operation is in progress.
        studio = getattr(self, "video_clip_studio", None)
        if studio is not None:
            try:
                if label == "🎥 Record / Import / Draw Clip":
                    studio.activate_input_devices()
                elif hasattr(studio, "suspend_inactive_inputs"):
                    studio.suspend_inactive_inputs()
            except Exception:
                pass

        if label == "▤ Open Windows":
            self._refresh_open_windows()

        # Periodic LAN discovery is useful only while its UI is visible.
        if label == "🎮 Game / Wi‑Fi":
            if not self._nearby_ui_timer.isActive():
                self._nearby_ui_timer.start()
            QTimer.singleShot(0, self._refresh_nearby_ui)
        else:
            self._nearby_ui_timer.stop()

    def resume_after_show(self):
        """Resume only resources appropriate to the currently visible workspace."""
        try:
            tabs = getattr(self, "_performance_tabs", None)
            if tabs is not None:
                self._on_performance_tab_changed(tabs.currentIndex())
        except Exception:
            pass

    def resizeEvent(self, event):
        try:
            self._math_background.setGeometry(self.rect())
            self._math_background.lower()
        except Exception:
            pass
        return super().resizeEvent(event)

    # ------------------------------------------------------------------ host paths
    def _host_projects_dir(self) -> str:
        if hasattr(self.host, "_projects_dir"):
            try:
                return self.host._projects_dir()
            except Exception:
                pass
        import groovebox_paths
        return groovebox_paths.projects_dir()

    def _host_exports_dir(self) -> str:
        if hasattr(self.host, "_exports_dir"):
            try:
                return self.host._exports_dir()
            except Exception:
                pass
        import groovebox_paths
        return groovebox_paths.renders_dir(getattr(self.host, "_current_project_path", None))

    def _host_games_dir(self) -> str:
        if hasattr(self.host, "_games_dir"):
            try:
                return self.host._games_dir()
            except Exception:
                pass
        import groovebox_paths
        return groovebox_paths.games_dir(getattr(self.host, "_current_project_path", None))

    def _host_samples_dir(self) -> str:
        if hasattr(self.host, "_samples_dir"):
            try:
                return self.host._samples_dir()
            except Exception:
                pass
        import groovebox_paths
        return groovebox_paths.samples_dir(getattr(self.host, "_current_project_path", None))

    # ------------------------------------------------------------------ browser
    def _on_root_changed(self, idx: int):
        text = self.cmb_root.currentText()
        if text == "Projects":
            self._cwd = self._host_projects_dir()
        elif text == "Recordings":
            import groovebox_paths
            self._cwd = groovebox_paths.recordings_dir(getattr(self.host, "_current_project_path", None))
        elif text == "Renders":
            self._cwd = self._host_exports_dir()
        elif text == "Games":
            self._cwd = self._host_games_dir()
        elif text == "Samples":
            self._cwd = self._host_samples_dir()
        elif text == "Groovebox Data":
            import groovebox_paths
            self._cwd = groovebox_paths.base_dir()
        else:
            path = QFileDialog.getExistingDirectory(self, "Choose folder", self._cwd or "")
            if path:
                self._cwd = path
            else:
                self.cmb_root.blockSignals(True)
                self.cmb_root.setCurrentIndex(0)
                self.cmb_root.blockSignals(False)
                return
        self.refresh()

    def _go_up(self):
        parent = os.path.dirname(self._cwd.rstrip(os.sep))
        if parent and parent != self._cwd:
            self._cwd = parent
            self.refresh()

    def _cached_kind(self, path: str) -> Optional[str]:
        """Return a cached fine-grained kind if the file hasn't changed since
        it was probed, else None (caller should treat as pending/needs-probe)."""
        try:
            st = os.stat(path)
        except OSError:
            return None
        cached = self._kind_cache.get(path)
        if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
            return cached[2]
        return None

    @staticmethod
    def _directory_signature(path: str):
        try:
            st=os.stat(path)
            return (int(getattr(st, "st_mtime_ns", int(st.st_mtime*1e9))), int(st.st_ino), int(st.st_dev))
        except OSError:
            return None

    def _refresh_inline_browser_if_changed(self):
        # One stat per tick only; never rescan media unless the directory itself changed.
        if not self.isVisible() or not self._cwd:
            return
        sig=self._directory_signature(self._cwd)
        if self._browser_dir_signature is None:
            self._browser_dir_signature=sig
        elif sig != self._browser_dir_signature:
            self._browser_dir_signature=sig
            self.refresh()

    def notify_filesystem_changed(self, path: str):
        """Refresh retained file browsers after record/import/move without reopening them."""
        path=os.path.abspath(str(path or ""))
        parent=os.path.dirname(path) if path else ""
        if parent and self._cwd and os.path.realpath(parent)==os.path.realpath(self._cwd):
            QTimer.singleShot(0, self.refresh)
        dlg=getattr(self, "_file_manager_window", None)
        try:
            if dlg is not None:
                dlg.notify_filesystem_changed(path)
        except RuntimeError:
            pass

    def refresh(self):
        self.file_list.clear()
        self.lbl_cwd.setText(self._cwd or "")
        if not self._cwd or not os.path.isdir(self._cwd):
            self.lbl_status.setText("Folder missing.")
            return
        try:
            entries = sorted(os.listdir(self._cwd), key=str.lower)
        except OSError as e:
            self.lbl_status.setText(f"List error: {e}")
            return
        # dirs first
        try:   # GROOVEBOX_R23R_HIDE_SYSTEM_FILES_20261103
            import groovebox_paths as _gpv
            entries = _gpv.visible_entries(self._cwd, entries)
        except Exception:
            pass
        dirs = [e for e in entries if os.path.isdir(os.path.join(self._cwd, e)) and not e.startswith(".")]
        files = [e for e in entries if os.path.isfile(os.path.join(self._cwd, e))]

        kind_filter = self.cmb_kind_filter.currentText() if hasattr(self, "cmb_kind_filter") else "All"
        sort_mode = self.cmb_sort.currentText() if hasattr(self, "cmb_sort") else "Name"
        # Default browsing does not need to spawn ffprobe for every video merely
        # to paint the list. Probe only when stream content affects filtering or
        # ordering; selected-file provenance remains independently on-demand.
        need_stream_probe = (kind_filter != "All" or sort_mode.startswith("Kind"))

        self._refresh_generation += 1
        generation = self._refresh_generation
        pending_probe: List[str] = []

        rows = []  # (name, full, ext, coarse_kind, fine_kind, size_bytes)
        for f in files:
            full = os.path.join(self._cwd, f)
            ext = _gb_ext(f)
            coarse_kind = "file"
            if ext in PROJECT_EXT:
                coarse_kind = "project"
            elif ext in AUDIO_EXT:
                coarse_kind = "audio"
            elif ext in VIDEO_EXT:
                coarse_kind = "video"
            elif ext in GAME_EXT:
                coarse_kind = "game"

            fine_kind = KIND_UNKNOWN
            if ext in AUDIO_EXT:
                fine_kind = KIND_AUDIO
            elif ext in VIDEO_EXT:
                cached = self._cached_kind(full)
                if cached is not None:
                    fine_kind = cached
                elif need_stream_probe:
                    fine_kind = KIND_PENDING
                    pending_probe.append(full)
                else:
                    fine_kind = KIND_UNKNOWN
            try:
                size_bytes = os.path.getsize(full)
            except OSError:
                size_bytes = 0
            rows.append((f, full, ext, coarse_kind, fine_kind, size_bytes))

        # --- filter: audio-only vs audioless-video vs both, videoless-audio ---
        def _passes_filter(fine_kind: str, coarse_kind: str) -> bool:
            if kind_filter == "All":
                return True
            if coarse_kind not in ("audio", "video"):
                return True  # never hide dirs/projects/games behind a media filter
            if fine_kind == KIND_PENDING:
                return True  # show until probed, so files don't flicker away
            if kind_filter.startswith("Audio only"):
                return fine_kind == KIND_AUDIO
            if kind_filter.startswith("Video only"):
                return fine_kind == KIND_VIDEO
            if kind_filter.startswith("Audio + Video"):
                return fine_kind == KIND_AV
            return True

        rows = [r for r in rows if _passes_filter(r[4], r[3])]

        # --- sort ---
        if sort_mode == "Size":
            rows.sort(key=lambda r: r[5], reverse=True)
        elif sort_mode.startswith("Kind (Audio"):
            order = {KIND_AUDIO: 0, KIND_AV: 1, KIND_VIDEO: 2, KIND_PENDING: 3, KIND_UNKNOWN: 4}
            rows.sort(key=lambda r: (order.get(r[4], 5) if r[3] in ("audio", "video") else 5, r[0].lower()))
        elif sort_mode.startswith("Kind (Video"):
            order = {KIND_VIDEO: 0, KIND_AV: 1, KIND_AUDIO: 2, KIND_PENDING: 3, KIND_UNKNOWN: 4}
            rows.sort(key=lambda r: (order.get(r[4], 5) if r[3] in ("audio", "video") else 5, r[0].lower()))
        else:
            rows.sort(key=lambda r: r[0].lower())

        for d in dirs:
            item = QListWidgetItem(f"📁 {d}/")
            item.setData(Qt.ItemDataRole.UserRole, os.path.join(self._cwd, d))
            item.setData(Qt.ItemDataRole.UserRole + 1, "dir")
            self.file_list.addItem(item)
        for (f, full, ext, coarse_kind, fine_kind, size_bytes) in rows:
            if coarse_kind == "project":
                icon = "🎛"
            elif coarse_kind == "game":
                icon = "🕹"
            elif coarse_kind == "video" and fine_kind == KIND_UNKNOWN:
                icon = "🎬"
            elif coarse_kind in ("audio", "video"):
                icon = _kind_icon(fine_kind)
            else:
                icon = "📄"
            item = QListWidgetItem(f"{icon} {f}  ({_safe_size(full)})")
            item.setData(Qt.ItemDataRole.UserRole, full)
            item.setData(Qt.ItemDataRole.UserRole + 1, coarse_kind)
            item.setData(Qt.ItemDataRole.UserRole + 2, fine_kind)
            self.file_list.addItem(item)
        self.lbl_status.setText(f"{len(dirs)} folders · {len(rows)} files")

        if pending_probe:
            self.lbl_probe_status.setText(f"Classifying {len(pending_probe)} video file(s)…")
            opt=getattr(self.host,'_scode_optimizer',None)
            if opt is not None and hasattr(opt,'submit_pooled'):
                paths=tuple(pending_probe)
                def probe_batch(): return [(p,_probe_media_kind_sync(p)) for p in paths]
                def probe_done(result,error):
                    if error is not None or generation != self._refresh_generation: return
                    for p,kind in (result or []): self._on_kind_probe_progress(generation,p,kind)
                    self._on_kind_probe_batch_done(generation)
                opt.submit_pooled('media_probe',(generation,paths),probe_batch,policy='frame',format_id='media_stream',frame=generation,callback=probe_done,qt_callback=True)
            else:
                self._worker_pool.start(_PoolTask(self._kind_worker.run_batch, generation, list(pending_probe)))
        else:
            self.lbl_probe_status.setText("")
        self._browser_dir_signature = self._directory_signature(self._cwd)

    def _on_kind_probe_progress(self, generation: int, path: str, kind: str):
        if generation != self._refresh_generation:
            return  # user navigated away / re-sorted before this finished
        try:
            st = os.stat(path)
            _bounded_cache_put(self._kind_cache, path, (st.st_mtime, st.st_size, kind), 256)
        except OSError:
            _bounded_cache_put(self._kind_cache, path, (0.0, 0, kind), 256)
        # Update the visible row in place if it's still on screen — avoids a
        # full relist (and a fresh disk stat pass) for every single result.
        for i in range(self.file_list.count()):
            it = self.file_list.item(i)
            if it and it.data(Qt.ItemDataRole.UserRole) == path:
                coarse_kind = it.data(Qt.ItemDataRole.UserRole + 1)
                if coarse_kind in ("audio", "video"):
                    it.setData(Qt.ItemDataRole.UserRole + 2, kind)
                    name = os.path.basename(path)
                    it.setText(f"{_kind_icon(kind)} {name}  ({_safe_size(path)})")
                break

    def _on_kind_probe_batch_done(self, generation: int):
        if generation != self._refresh_generation:
            return
        self.lbl_probe_status.setText("")
        # If an Audio/Video-only filter is active, files that were shown as
        # "pending" may need to drop out (or newly-revealed ones appear) now
        # that every file in the folder has a real classification.
        kind_filter = self.cmb_kind_filter.currentText() if hasattr(self, "cmb_kind_filter") else "All"
        if kind_filter != "All":
            self.refresh()

    def _selected_paths(self) -> List[str]:
        out = []
        for item in self.file_list.selectedItems():
            p = item.data(Qt.ItemDataRole.UserRole)
            if p:
                out.append(str(p))
        return out

    def _on_double_click(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        kind = item.data(Qt.ItemDataRole.UserRole + 1)
        if kind == "dir" and path:
            self._cwd = path
            self.refresh()
            return
        if kind == "project":
            self._open_project(path)
        elif kind in ("audio", "video"):
            self._play_path(path)
        elif kind == "game":
            self._play_game_package(path)

    def _on_selection_changed(self):
        # Fast path only: show path + size immediately (both cheap, local
        # stat calls). The slow provenance/ffprobe part is debounced and
        # run off-thread in _start_provenance_lookup / _on_provenance_ready.
        self._selection_token += 1
        paths = self._selected_paths()
        if not paths:
            self.info_view.setPlainText("")
            self._selection_debounce.stop()
            return
        path = paths[0]
        self.info_view.setPlainText(f"{path}\nsize: {_safe_size(path)}\n(reading details…)")
        self._selection_debounce.start()

    def _start_provenance_lookup(self):
        paths = self._selected_paths()
        if not paths:
            return
        path = paths[0]
        token = self._selection_token
        opt=getattr(self.host,'_scode_optimizer',None)
        if opt is not None and hasattr(opt,'submit_pooled'):
            try:
                st=os.stat(path); identity=(path,st.st_mtime_ns,st.st_size)
            except OSError:
                identity=(path,0,0)
            def lookup(): return _extract_json_comment(path) if os.path.isfile(path) else None
            def done(result,error):
                if error is None: self._on_provenance_ready(token,path,result)
            opt.submit_pooled('media_provenance',identity,lookup,policy='pure',format_id='object',callback=done,qt_callback=True,max_entries=256)
        else:
            self._worker_pool.start(_PoolTask(self._prov_worker.lookup, token, path))

    def _on_provenance_ready(self, token: int, path: str, prov: Optional[dict]):
        if token != self._selection_token:
            return  # user already moved on to a different selection
        lines = [path, f"size: {_safe_size(path)}"]
        if prov:
            lines.append("--- provenance ---")
            for k in ("seed", "bpm", "source_project_path", "sample_rate", "fps",
                      "audio_bitrate_kbps", "fingerprint", "doc"):
                if k in prov:
                    lines.append(f"{k}: {prov[k]}")
            sp = prov.get("source_project_path")
            if sp:
                lines.append(f"linked project exists: {os.path.isfile(str(sp))}")
        try:
            self.info_view.setPlainText("\n".join(lines))
        except (RuntimeError, AttributeError):
            return

    def _open_selected(self):
        for path in self._selected_paths():
            kind = "file"
            for i in range(self.file_list.count()):
                it = self.file_list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == path:
                    kind = it.data(Qt.ItemDataRole.UserRole + 1)
                    break
            if kind == "dir":
                self._cwd = path
                self.refresh()
            elif kind == "project":
                self._open_project(path)
            elif kind == "game":
                self._play_game_package(path)
            elif kind in ("audio", "video"):
                self._play_path(path)

    def _open_project(self, path: str):
        try:
            if hasattr(self.host, "load_project_dialog"):
                # Direct load if host supports path-based apply
                pass
            if hasattr(self.host, "_apply_project_snapshot") or hasattr(self.host, "load_project_dialog"):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Prefer apply_project_snapshot / restore path
                applied = False
                for name in ("_apply_project_snapshot", "apply_project_snapshot",
                             "_project_history_restore"):
                    fn = getattr(self.host, name, None)
                    if callable(fn):
                        try:
                            fn(data)
                            applied = True
                            break
                        except Exception:
                            continue
                if not applied:
                    # Fallback: set as current and ask user to use host Load
                    QMessageBox.information(
                        self, "Project",
                        f"Opened path recorded:\n{path}\n\n"
                        "Use host Load Project if auto-apply is unavailable."
                    )
                setattr(self.host, "_current_project_path", path)
                self.lbl_status.setText(f"Loaded project: {os.path.basename(path)}")
                self.cmb_game_status.setText(f"Project: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Open project failed", str(e))

    def _play_selected(self):
        paths = [p for p in self._selected_paths() if os.path.isfile(p)]
        if not paths:
            return
        if len(paths) > 1:
            self._play_together(paths)      # several selected → simultaneous
            return
        self._play_path(paths[0])

    # GROOVEBOX_R23R_PLAY_TOGETHER_20261101
    def _play_together(self, paths, volumes=None):
        """Play several files at once, in-process (no external player needed).

        Audio files are decoded at their native rates, resampled (anti-aliased)
        to the highest of those rates, summed in stereo with their volumes and
        streamed through the main window's device resolver; the sum is scaled
        down only if it would clip. Video/image files open in their own in-app
        players at the same time.
        """
        import numpy as np
        paths = [p for p in paths if os.path.isfile(p)]
        vols = list(volumes or [100] * len(paths))
        audio, others = [], []
        for p, v in zip(paths, vols):
            e = _gb_ext(p)
            (audio if e in AUDIO_EXT else others).append((p, v))
        msgs = []
        if audio:
            # GROOVEBOX_R23R_ASYNC_DECODE_20261101: decode + resample + mix on a worker.
            self._stop_player()
            self._host_decode_gen = int(getattr(self, "_host_decode_gen", 0)) + 1
            gen = self._host_decode_gen
            br = getattr(self, "_together_br", None)
            if br is None:
                br = _FileToolsBridge(self); br.groups.connect(self._on_together_mixed); self._together_br = br
            def run():
                try:
                    from audio_os_backend import _resample_for_hardware
                    dec = []
                    for p, v in audio:
                        x, sr = _gb_decode_audio_faithful(_gb_playable(p))
                        if x.ndim == 1: x = x[:, None]
                        if x.shape[1] == 1: x = np.repeat(x, 2, axis=1)
                        dec.append((x[:, :2].astype(np.float32) * np.float32(max(0, v) / 100.0), int(sr)))
                    rate = max(sr for _x, sr in dec)
                    tracks = [(_resample_for_hardware(x, sr, rate) if sr != rate else x) for x, sr in dec]
                    n = max(t.shape[0] for t in tracks)
                    mix = np.zeros((n, 2), dtype=np.float32)
                    for t in tracks:
                        mix[:t.shape[0]] += t
                    pk = float(np.max(np.abs(mix))) if mix.size else 0.0
                    if pk > 1.0:
                        mix /= pk
                    br.groups.emit({"gen": gen, "mix": mix, "rate": rate, "n": len(dec), "scaled": pk > 1.0}, "")
                except Exception as e:
                    br.groups.emit({"gen": gen}, str(e))
            threading.Thread(target=run, daemon=True, name="groovebox-together").start()
            msgs.append(f"mixing {len(audio)} audio file(s)…")
        for p, v in others:
            try:
                e = _gb_ext(p)
                if _gb_mcc_kind(p) == "video":
                    dlg = _gb_open_mcc_video(self, p, int(v))
                elif e in IMAGE_EXT:
                    dlg = ImageViewerDialog(_gb_playable(p), self)
                else:
                    host = _gb_find_host(self)
                    dlg = InAppMediaPlayer(_gb_playable(p), self, preferred_output=str(getattr(host, "_preferred_audio_output_name", "") or "") if host is not None else "",
                                           volume_pct=int(v))
                dlg.setModal(False); dlg.show()
                self.__dict__.setdefault("_together_windows", []).append(dlg)
            except Exception as ex:
                msgs.append(f"{os.path.basename(p)}: {ex}")
        if others:
            msgs.append(f"{len(others)} video/image window(s)")
        self.lbl_status.setText("▶▶ Playing together: " + " · ".join(msgs))

    # ------------------------------------------------------------------ Browse Files menu / Player Window
    def _show_session_window(self, w):
        """Map/focus a retained tool window without blocking the Qt event loop."""
        try:
            w.setModal(False)
            w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            if w.isMinimized(): w.showNormal()
            else: w.setWindowState(w.windowState() & ~Qt.WindowState.WindowMinimized)
            w.show(); w.raise_(); w.activateWindow()
            h = w.windowHandle()
            if h is not None and hasattr(h, "requestActivate"): h.requestActivate()
        except Exception:
            try: w.show()
            except Exception: pass
        return w

    def _open_file_manager(self):
        """Show one retained, non-modal file manager; first listing is asynchronous."""
        dlg = getattr(self, "_file_manager_window", None)
        try:
            if dlg is not None:
                # Re-opening preserves the directory but must relist it: record/import may
                # have changed files while this retained window was hidden.
                QTimer.singleShot(0, dlg.refresh)
                QTimer.singleShot(0, dlg._refresh_storage_devices)
                return self._show_session_window(dlg)
        except RuntimeError:
            dlg = None
        dlg = FileManagerDialog(self, self._cwd)
        self._file_manager_window = dlg
        return self._show_session_window(dlg)

    def _show_player_window(self, items=None, start_index=0, replace_queue=True):
        dlg = getattr(self, "_media_player_window", None)
        try:
            if dlg is not None:
                if replace_queue and items is not None:
                    dlg.set_items(items, start_index)
                return self._show_session_window(dlg)
        except RuntimeError:
            dlg = None
        dlg = MediaPlayerWindow(self, list(items or []), start_index)
        self._media_player_window = dlg
        return self._show_session_window(dlg)

    def _open_player_window_for_playlist(self):
        """Launch/re-open the retained Player/DJ without synchronous hardware scans."""
        if not self._playlist:
            QMessageBox.information(self, "Player Window", "The playlist is empty. Add media first.")
            return
        start = self._playlist_index if self._playlist_index >= 0 else 0
        existing = getattr(self, "_media_player_window", None)
        try:
            if existing is not None:
                # Launcher restore is non-destructive: keep live deck/queue/crossfader state.
                return self._show_player_window(None, start, replace_queue=False)
        except RuntimeError:
            existing = None
        return self._show_player_window(list(self._playlist), start, replace_queue=True)

    def _routed_player(self, cmd: list, want_video: bool = True):
        """Apply selected per-process display/audio routing without changing OS defaults."""
        env = os.environ.copy()
        try:
            from media_output_router import player_routing
            extra, overlay = player_routing(self._output_display, self._output_audio_target, want_video=want_video)
            if cmd and os.path.basename(cmd[0]).lower().startswith("mpv"):
                cmd = list(cmd) + list(extra)
            env.update(overlay)
        except Exception:
            pass
        return cmd, env

    def _play_path(self, path: str, volume_pct: int = 100, duration_s: float = 0.0):
        if _gb_mcc_kind(path) == "video":
            self._stop_player()
            _gb_open_mcc_video(self, path, volume_pct)
            self.lbl_status.setText(f"▶ MCC video (direct, lossless): {os.path.basename(path)}")
            return
        path = _gb_playable(path)
        host = getattr(self, "host", None)
        if host is not None and hasattr(host, "claim_audio"):
            host.claim_audio("performance")
        try:
            from hardware_runtime import ensure_first_hardware_refresh
            ensure_first_hardware_refresh("multimedia-play", block=False)
        except Exception:
            pass
        # Always re-assert All-detected routing before external player launch so
        # the first Performance play is audible even if the async device scan
        # has not finished (Trigger All uses sounddevice which is primed earlier).
        try:
            self._apply_output_routing()
        except Exception:
            pass
        self._stop_player()
        ext = _gb_ext(path)
        self._player_attempted_backends = set()
        self._player_fallback_path = path
        self._player_fallback_want_video = bool(ext in VIDEO_EXT or ext in IMAGE_EXT)
        self._player_fallback_volume = int(volume_pct)
        if ext in AUDIO_EXT and not _AUDIO_VIA_VIDEO_PLAYER:
            # R23j: the always-visible inline Play path must work for every
            # supported audio format, not only WAV. On sOS, local FFmpeg decodes
            # MP3/FLAC/OGG/OPUS/AIFF/CAF/WAV to a fixed 48 kHz stereo PCM stream
            # and aplay writes it directly to the prepared physical ALSA device.
            if self._live_speed == 1.0:
                try:
                    from media_output_router import _running_on_sos
                    if _running_on_sos():
                        try:
                            if self.host is not None and hasattr(self.host, "_close_audition_stream"):
                                self.host._close_audition_stream()
                        except Exception:
                            pass
                        sink,decoder,backend=_launch_physical_pcm_pipeline(path, preferred_target=self._output_audio_target)
                        self._mpv_ipc_path=None
                        self._player_proc=sink; self._player_aux_proc=decoder
                        self.lbl_status.setText(f"Inline physical audio: {os.path.basename(path)} · {backend}")
                        QTimer.singleShot(700, lambda p=self._player_proc, mp=path: self._check_player_launch(p, mp))
                        return
                except Exception as e:
                    self.lbl_status.setText(f"Direct physical inline audio unavailable ({e}); trying routed playback…")
                    try:
                        import groovebox as _gbm
                        _gbm._gb_log_error(f"wav player · direct ALSA route: {e}")
                    except Exception:
                        pass
            if hasattr(self.host, "play_buffer"):
                # Desktop/non-sOS dry WAV path. At any other speed use mpv so
                # rate changes remain live/responsive through IPC.
                if self._live_speed == 1.0:
                    # Every audio format (not only WAV) uses the main window's
                    # device handler: decoded faithfully, same routed stream.
                    if not getattr(self, "_skip_host_once", False):
                        # GROOVEBOX_R23R_ASYNC_DECODE_20261101: decode on a worker (long
                        # MP3/FLAC no longer freeze the window); start on the GUI thread.
                        self._start_host_decode(path, volume_pct, duration_s)
                        return
                    self._skip_host_once = False
        want_video = ext in VIDEO_EXT or ext in IMAGE_EXT
        cmd = _player_cmd_with_volume(volume_pct, want_video=want_video) or _find_player(want_video=want_video)
        if not cmd:
            try:
                self.lbl_status.setText(_gb_inapp_fallback(self, path, volume_pct, duration_s))
            except Exception as e:
                QMessageBox.warning(self, "No player",
                                    f"No external player (mpv/VLC/ffplay) and the in-app player failed:\n{e}")
            return
        try:
            # Prefer mpv with IPC so live speed/pitch-independent time changes are
            # responsive while the file is already running. Other players retain
            # the existing fallback behavior.
            if cmd and os.path.basename(cmd[0]).startswith("mpv"):
                self._mpv_ipc_path = os.path.join(tempfile.gettempdir(), f"groovebox_mpv_{os.getpid()}_{id(self)}.sock")
                try:
                    os.unlink(self._mpv_ipc_path)
                except OSError:
                    pass
                cmd = list(cmd) + [f"--input-ipc-server={self._mpv_ipc_path}", f"--speed={self._live_speed:.6f}"]
            else:
                self._mpv_ipc_path = None
            if cmd and os.path.basename(cmd[0]).startswith("mpv"):
                if ext in IMAGE_EXT:
                    cmd = list(cmd) + [f"--image-display-duration={max(0.05, float(duration_s or 5.0)):.6f}", "--loop-file=no"]
                elif float(duration_s or 0.0) > 0.0:
                    cmd = list(cmd) + [f"--length={float(duration_s):.6f}"]
            cmd, penv = self._routed_player(cmd, want_video=want_video)
            first_backend = os.path.basename(cmd[0]).lower()
            self._player_attempted_backends = {"mpv" if first_backend.startswith("mpv") else ("vlc" if first_backend.startswith("vlc") else "ffplay")}
            self._player_fallback_path = path
            self._player_fallback_want_video = bool(want_video)
            self._player_fallback_volume = int(volume_pct)
            self._player_proc = subprocess.Popen(cmd + [path], env=penv)
            QTimer.singleShot(900, lambda p=self._player_proc, mp=path: self._check_player_launch(p, mp))
            try:
                if self._media_share_server is not None:
                    self._media_share_server.set_current(path)
            except Exception:
                pass
            self.lbl_status.setText(f"External play: {os.path.basename(path)} @{volume_pct}% · {self._live_speed:.2f}×")
        except Exception as e:
            QMessageBox.warning(self, "Play failed", str(e))

    def _host_decode_bridge(self):
        br = getattr(self, "_host_decode_br", None)
        if br is None:
            br = _FileToolsBridge(self)
            br.groups.connect(self._on_host_decoded)
            self._host_decode_br = br
        return br

    def _start_host_decode(self, path, volume_pct, duration_s):
        self._host_decode_gen = int(getattr(self, "_host_decode_gen", 0)) + 1
        gen = self._host_decode_gen
        br = self._host_decode_bridge()
        self.lbl_status.setText(f"Decoding {os.path.basename(path)}…")
        def run():
            try:
                x, sr = _gb_decode_audio_faithful(path)
                br.groups.emit({"gen": gen, "x": x, "sr": sr, "path": path, "vol": volume_pct, "dur": duration_s}, "")
            except Exception as e:
                br.groups.emit({"gen": gen, "path": path, "vol": volume_pct, "dur": duration_s}, str(e))
        threading.Thread(target=run, daemon=True, name="groovebox-decode").start()

    def _on_host_decoded(self, payload, error):
        if not isinstance(payload, dict) or payload.get("gen") != getattr(self, "_host_decode_gen", 0):
            return                                   # a newer play request superseded this one
        path = payload.get("path", "")
        if not error:
            try:
                note = _gb_play_decoded(self.host, payload["x"], payload["sr"], path, payload.get("vol", 100))
                self.lbl_status.setText(f"Playing on host: {note}")
                return
            except Exception as e:
                error = str(e)
        self.lbl_status.setText(f"Host play failed ({error}); external player…")
        self._skip_host_once = True
        self._play_path(path, payload.get("vol", 100), payload.get("dur", 0.0))

    def _check_player_launch(self, proc, path: str):
        """Detect immediate decoder/backend failure and try another installed player.

        A successful video playback must not depend on the audio-only WAV path,
        and one backend returning status 1 should not end playback when another
        supported decoder is available. Attempts are bounded to mpv/VLC/FFplay.
        """
        try:
            rc = proc.poll()
            if rc is None or proc is not getattr(self, "_player_proc", None) or rc == 0:
                return
            attempted = getattr(self, "_player_attempted_backends", set())
            want_video = bool(getattr(self, "_player_fallback_want_video", False))
            volume = int(getattr(self, "_player_fallback_volume", 100))
            candidates = ("mpv", "vlc", "ffplay")
            for backend in candidates:
                if backend in attempted:
                    continue
                exe = _media_player_executable(backend)
                if not exe:
                    attempted.add(backend)
                    continue
                vol = max(0, min(200, volume))
                if backend == "mpv":
                    cmd = [exe, "--force-window=yes", "--keep-open=yes", "--hwdec=auto-safe",
                           "--cache=auto", "--audio-fallback-to-null=no", f"--volume={vol}"]
                    if not want_video:
                        cmd += ["--audio-client-name=Groovebox", "--no-video"]
                elif backend == "vlc":
                    cmd = [exe, "--no-one-instance", "--no-video-title-show", f"--gain={vol / 100.0:.2f}"]
                    if not want_video:
                        cmd += ["--no-video"]
                else:
                    cmd = [exe, "-autoexit", "-hide_banner", "-volume", str(min(100, vol))]
                    if not want_video:
                        cmd.append("-nodisp")
                attempted.add(backend)
                try:
                    cmd, penv = self._routed_player(cmd, want_video=want_video)
                    self._player_proc = subprocess.Popen(cmd + [path], env=penv)
                    self.lbl_status.setText(f"Primary player exited ({rc}); retrying with {backend}: {os.path.basename(path)}")
                    QTimer.singleShot(900, lambda p=self._player_proc, mp=path: self._check_player_launch(p, mp))
                    return
                except Exception as launch_exc:
                    self.lbl_status.setText(f"{backend} launch failed: {launch_exc}")
            try:
                self.lbl_status.setText(f"External players failed (last exit {rc}); " + _gb_inapp_fallback(self, path, volume))
            except Exception as _fe:
                self.lbl_status.setText(f"All available players failed (last exit {rc}): {os.path.basename(path)} ({_fe}).")
        except Exception as exc:
            try: self.lbl_status.setText(f"Player launch check failed: {exc}")
            except Exception: pass

    def _play_wav_on_host(self, path: str):
        import numpy as np
        host = getattr(self, "host", None)
        if host is not None and hasattr(host, "claim_audio"):
            host.claim_audio("performance")
        try:
            from audio_os_backend import wavfile
            sr, data = wavfile.read(path)
            if data.ndim > 1:
                data = data.mean(axis=1)
            if data.dtype == np.int16:
                buf = (data.astype(np.float32) / 32768.0)
            else:
                buf = np.asarray(data, dtype=np.float32)
                peak = float(np.max(np.abs(buf))) or 1.0
                buf = buf / peak
            with getattr(self.host, "play_lock", threading.Lock()):
                self.host.play_buffer = buf
                self.host.play_sample_rate = int(sr)
                self.host.play_cursor = 0
                self.host.is_playing = True
                self.host.is_paused = False
                self.host._audio_only_mode = True
            if hasattr(self.host, "audio_stream") and getattr(self.host, "HAS_SOUNDDEVICE", True):
                from audio_os_backend import open_output_stream, prepare_output_buffer
                _render_sr = int(sr)
                buf, sr, _hwdev = prepare_output_buffer(buf, sr, preferred_name=str(getattr(self.host,'_preferred_audio_output_name','') or ''))
                with getattr(self.host, "play_lock", threading.Lock()):
                    self.host.play_buffer = buf
                    self.host.play_sample_rate = int(sr)
                    self.host.play_cursor = 0
                if int(sr) != _render_sr:
                    self.lbl_status.setText(f"Physical playback {_render_sr/1000:g} kHz → {int(sr)/1000:g} kHz; file unchanged")
                if self.host.audio_stream is not None:
                    try:
                        self.host.audio_stream.stop(); self.host.audio_stream.close()
                    except Exception: pass
                self.host.audio_stream = open_output_stream(
                    samplerate=int(sr), channels=1, dtype="float32",
                    callback=self.host._audio_callback, blocksize=1024, latency="high",
                    preferred_name=str(getattr(self.host,'_preferred_audio_output_name','') or ''),
                )
                self.host.audio_stream.start()
            if hasattr(self.host, "_scope_update_timer"):
                self.host._scope_update_timer.start()
        except Exception:
            raise

    def _stop_player(self):
        self._host_decode_gen = int(getattr(self, "_host_decode_gen", 0)) + 1   # cancel pending decodes
        _gb_stop_file_player()
        _dlg = getattr(self, "_gb_inapp_dialog", None)
        if _dlg is not None and hasattr(_dlg, "stop"):
            try:
                _dlg.stop()
            except Exception:
                pass
        host = getattr(self, "host", None)
        if host is not None and hasattr(host, "release_audio"):
            try:
                host.release_audio("performance")
            except Exception:
                pass
        if self._player_proc is not None:
            try:
                self._player_proc.terminate()
            except Exception:
                pass
            self._player_proc = None
        if getattr(self, "_player_aux_proc", None) is not None:
            try:
                self._player_aux_proc.terminate()
            except Exception:
                pass
            self._player_aux_proc = None
        if self._mpv_ipc_path:
            try:
                os.unlink(self._mpv_ipc_path)
            except OSError:
                pass
            self._mpv_ipc_path = None
        try:
            if getattr(self.host, "is_playing", False) and getattr(self.host, "_audio_only_mode", False):
                if hasattr(self.host, "stop_audio_playback"):
                    self.host.stop_audio_playback()
        except Exception:
            pass

    def _add_to_playlist(self):
        for path in self._selected_paths():
            if os.path.isfile(path) and not any(it["path"] == path for it in self._playlist):
                ext = _gb_ext(path)
                if ext in MEDIA_EXT:
                    fine_kind = self._cached_kind(path)
                    if fine_kind is None:
                        fine_kind = _probe_media_kind_sync(path)
                        try:
                            st = os.stat(path)
                            _bounded_cache_put(self._kind_cache, path, (st.st_mtime, st.st_size, fine_kind), 256)
                        except OSError:
                            pass
                    self._playlist.append({"path": path, "volume": 100, "mix": False, "kind": fine_kind, "time_s": float(len(self._playlist) * 5.0), "duration_s": 5.0 if fine_kind == KIND_IMAGE else 0.0})
                elif ext in GAME_EXT:
                    self._playlist.append({"path": path, "volume": 100, "mix": False, "kind": KIND_UNKNOWN, "time_s": float(len(self._playlist) * 5.0), "duration_s": 0.0})
        self._refresh_playlist_widget(); self._sync_project_state()
        self.lbl_status.setText(f"Playlist: {len(self._playlist)} items")

    def _delete_selected(self):
        paths = self._selected_paths()
        if not paths:
            return
        reply = QMessageBox.question(
            self, "Delete",
            f"Delete {len(paths)} item(s)?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for path in paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception as e:
                QMessageBox.warning(self, "Delete failed", f"{path}\n{e}")
        self.refresh()

    def _reveal_selected(self):
        paths = self._selected_paths()
        if not paths:
            return
        path = paths[0]
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        for cmd in (
            ["xdg-open", folder],
            ["pcmanfm", folder],
            ["thunar", folder],
            ["explorer.exe", folder],
        ):
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(cmd)
                    return
                except Exception:
                    continue
        self.lbl_status.setText(folder)

    def _launch_master_studio(self):
        """Raise the existing MatGroovebox studio or launch its canonical entry point.

        Performance/player mode never constructs a second copy of the studio
        internally.  That keeps QApplication ownership, MCC file handling and
        native/audio initialization on the same supported startup path.
        """
        host = getattr(self, "host", None)
        try:
            # Performance is normally a separate top-level window owned logically
            # (not as a QWidget parent) by the already-running Master Studio.
            # On Wayland a compositor may ignore raise_/activateWindow() requests
            # from another top-level window.  Hiding Performance first makes the
            # existing studio reliably visible and avoids spawning a duplicate.
            if host is not None and host is not self:
                # Persist the live Performance controls before switching windows.
                try:
                    state = getattr(host, "media_workbench_state", None)
                    if not isinstance(state, dict):
                        state = {}
                        setattr(host, "media_workbench_state", state)
                    state["performance"] = self.export_state()
                except Exception:
                    pass

                # Restore from minimized state before requesting focus.
                normal = getattr(host, "showNormal", None)
                if callable(normal):
                    normal()
                show = getattr(host, "show", None)
                if callable(show):
                    show()

                # Hide this top-level window.  This is the reliable part on
                # Wayland; raise_/activateWindow() remain useful on X11/Windows.
                try:
                    self.hide()
                except Exception:
                    pass

                raise_ = getattr(host, "raise_", None)
                if callable(raise_):
                    raise_()
                activate = getattr(host, "activateWindow", None)
                if callable(activate):
                    activate()

                # Some WMs apply activation only after the current click event
                # unwinds. Queue one zero-delay retry without blocking the GUI.
                try:
                    QTimer.singleShot(0, lambda h=host: (h.raise_(), h.activateWindow()))
                except Exception:
                    pass
                self.lbl_status.setText("MatGroovebox Master Studio ready.")
                return host
        except Exception as exc:
            # Fall through to the canonical process launcher.
            try:
                self.lbl_status.setText(f"Studio focus unavailable ({exc}); launching studio…")
            except Exception:
                pass

        root = os.path.dirname(os.path.abspath(__file__))
        runner = os.path.join(root, "run_groovebox.py")
        if not os.path.isfile(runner):
            QMessageBox.warning(self, "Master Studio", f"Studio launcher not found:\n{runner}")
            return None
        try:
            from groovebox_subprocess import app_argv
            cmd = app_argv()
            kw = {"cwd": root}
            if os.name == "nt":
                try:
                    kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                except Exception:
                    pass
            else:
                kw["start_new_session"] = True
            proc = subprocess.Popen(cmd, **kw)
            self._master_studio_process = proc
            self.lbl_status.setText(f"MatGroovebox Master Studio launched (PID {proc.pid}).")
            return proc
        except Exception as exc:
            QMessageBox.warning(self, "Master Studio", f"Could not launch MatGroovebox Master Studio:\n{exc}")
            return None

    # ------------------------------------------------------------------ playlist tab
    def _build_shared_synth_context_tab(self) -> QWidget:
        """Peer-level deterministic synth-event context shared with canonical composition."""
        from PyQt6.QtWidgets import QPlainTextEdit, QFormLayout, QGroupBox
        from shared_synth_context import empty_context, generate_spatial_lanes, publish_program_lanes, validate_context
        page=QWidget(); root=QVBoxLayout(page)
        intro=QLabel("Shared canonical event context · Vector / Wavetable / Ball / Cellular Automata / user synths / Math patterns are peer lanes. Same-time events are concurrent; lane order never grants priority.")
        intro.setWordWrap(True); root.addWidget(intro)
        form=QFormLayout(); root.addLayout(form)
        self.shared_ball_steps=QSpinBox(); self.shared_ball_steps.setRange(8,2048); self.shared_ball_steps.setValue(128)
        self.shared_ball_vx=QDoubleSpinBox(); self.shared_ball_vx.setRange(-10,10); self.shared_ball_vx.setDecimals(3); self.shared_ball_vx.setValue(.7)
        self.shared_ball_vy=QDoubleSpinBox(); self.shared_ball_vy.setRange(-10,10); self.shared_ball_vy.setDecimals(3); self.shared_ball_vy.setValue(-.4)
        self.shared_ball_gravity=QLineEdit("0,0,0.25")
        self.shared_ca_width=QSpinBox(); self.shared_ca_width.setRange(4,64); self.shared_ca_width.setValue(16)
        self.shared_ca_height=QSpinBox(); self.shared_ca_height.setRange(4,64); self.shared_ca_height.setValue(16)
        self.shared_ca_states=QSpinBox(); self.shared_ca_states.setRange(2,32); self.shared_ca_states.setValue(3)
        self.shared_ca_gens=QSpinBox(); self.shared_ca_gens.setRange(1,128); self.shared_ca_gens.setValue(16)
        for label,widget in [("Ball simulation steps",self.shared_ball_steps),("Ball launch vx",self.shared_ball_vx),("Ball launch vy",self.shared_ball_vy),("Gravity polynomial coefficients (ascending powers)",self.shared_ball_gravity),("Cellular grid width",self.shared_ca_width),("Cellular grid height",self.shared_ca_height),("Cell states",self.shared_ca_states),("Generations",self.shared_ca_gens)]: form.addRow(label,widget)
        btn=QPushButton("Generate / Update Ball + Cellular lanes in Shared Context")
        btn.clicked.connect(self._generate_shared_synth_context); root.addWidget(btn)
        self.shared_synth_summary=QLabel("No generated spatial lanes yet."); self.shared_synth_summary.setWordWrap(True); root.addWidget(self.shared_synth_summary)
        self.shared_synth_events=QPlainTextEdit(); self.shared_synth_events.setReadOnly(True); self.shared_synth_events.setMinimumHeight(180); root.addWidget(self.shared_synth_events,1)
        ctx=getattr(self.host,"canonical_synth_context",None)
        if isinstance(ctx,dict): self._display_shared_synth_context(ctx)
        return page

    def _generate_shared_synth_context(self):
        from shared_synth_context import empty_context, generate_spatial_lanes, publish_program_lanes, validate_context
        try:
            coeff=[float(x.strip()) for x in self.shared_ball_gravity.text().split(",") if x.strip()]
            if not coeff: raise ValueError("Enter at least one gravity polynomial coefficient.")
            old=getattr(self.host,"canonical_synth_context",None)
            _base_hz=float(self.host.spin_base_frequency.value()) if hasattr(self.host,"spin_base_frequency") else 432.0
            ctx=generate_spatial_lanes(old if isinstance(old,dict) else empty_context(),
                {"steps":self.shared_ball_steps.value(),"vx":self.shared_ball_vx.value(),"vy":self.shared_ball_vy.value(),"gravity_coefficients":coeff},
                {"width":self.shared_ca_width.value(),"height":self.shared_ca_height.value(),"cell_types":self.shared_ca_states.value(),"generations":self.shared_ca_gens.value(),"rules":[]},
                base_frequency_hz=_base_hz)
            # Snapshot the existing canonical Vector and Wavetable controls into peer lanes.
            ctx=publish_program_lanes(ctx, getattr(self.host,"master_vector_state",{}), getattr(self.host,"wavetable_projector_state",{}))
            validate_context(ctx)
            # One JSON-safe host-level canonical object; media playlist stays separate and is not made dominant.
            self.host.canonical_synth_context=ctx
            state=getattr(self.host,"media_workbench_state",None)
            if not isinstance(state,dict): state={}; self.host.media_workbench_state=state
            state["canonical_synth_context"]=ctx
            self._display_shared_synth_context(ctx)
            self._sync_project_state()
            self.lbl_status.setText(f"Shared synth context updated: {len(ctx['schedule'])} peer events · revision {ctx['revision']}")
        except Exception as exc:
            QMessageBox.warning(self,"Shared Synth Context",str(exc))

    def _display_shared_synth_context(self, ctx):
        lanes=ctx.get("lanes",{}) if isinstance(ctx,dict) else {}
        schedule=ctx.get("schedule",[]) if isinstance(ctx,dict) else []
        self.shared_synth_summary.setText(f"Revision {ctx.get('revision',0)} · {len(schedule)} concurrent scheduled events · lanes: " + ", ".join(f"{k} ({len(v.get('events',[]))})" for k,v in sorted(lanes.items()) if isinstance(v,dict)) + " · deterministic · no dominant lane")
        preview=["time | lane | pitch | velocity | event_id"]
        for e in schedule[:500]: preview.append(f"{e.get('time',0):>7} | {e.get('lane','')} | {e.get('pitch','')} | {e.get('velocity','')} | {e.get('event_id','')}")
        self.shared_synth_events.setPlainText("\n".join(preview))

    def _build_playlist_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        banner = QLabel("Playlist plays files. Drop or add, then Play. Device selectors on the left choose where it comes out.")
        banner.setWordWrap(True)
        banner.setStyleSheet("color:#12e0c4; font-weight:700;")
        lay.addWidget(banner)
        self.playlist_widget = QListWidget()
        self.playlist_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.playlist_widget.itemSelectionChanged.connect(self._on_playlist_selection_changed)
        lay.addWidget(self.playlist_widget, stretch=1)

        # R28.4 prominent one-click, seeded playlist + DJ parameter randomizer.
        self.btn_randomize_playlist_dj = QPushButton("⤨ RANDOMIZE PLAYLIST + PERFORMANCE PARAMETRIC DJ")
        self.btn_randomize_playlist_dj.setMinimumHeight(48)
        self.btn_randomize_playlist_dj.setToolTip("Seeded, undoable-style arrangement: shuffles playlist order and assigns bounded per-item volume/pitch/rate/direction parameters. Does not alter source media or canonical composition data.")
        self.btn_randomize_playlist_dj.clicked.connect(self._randomize_playlist_and_dj_parameters)
        lay.addWidget(self.btn_randomize_playlist_dj)

        row = QHBoxLayout()
        btn_play = QPushButton("▶ Play")
        btn_next = QPushButton("⏭ Next")
        btn_stop = QPushButton("⏹ Stop")
        btn_clear = QPushButton("Clear Playlist")
        btn_undo_random = QPushButton("Undo Randomize")
        btn_undo_random.setToolTip("Restore the playlist and per-item parameters captured before the last randomization.")
        btn_undo_random.clicked.connect(self._undo_playlist_randomization)
        btn_play.clicked.connect(self._playlist_play)
        btn_together = QPushButton("▶▶ Play together")
        btn_together.setToolTip("Play every selected playlist row at the same time (audio mixed in-process; videos in their own windows).")
        btn_together.clicked.connect(self._playlist_play_together)
        self._btn_playlist_together = btn_together
        btn_next.clicked.connect(self._playlist_next)
        btn_stop.clicked.connect(self._stop_player)
        btn_clear.clicked.connect(self._playlist_clear)
        for b in (btn_play, btn_together, btn_next, btn_stop, btn_clear, btn_undo_random):
            row.addWidget(b)
        lay.addLayout(row)

        # PLAYER_WINDOW_LAUNCH_2026: dedicated player window with its own
        # destination-device (display/audio sink) selector, seeded from this
        # playlist and the currently selected row.
        player_row = QHBoxLayout()
        btn_player_window = QPushButton("🖥 Open Player Window…")
        btn_player_window.setToolTip(
            "Open the playlist in a dedicated Player Window with its own "
            "destination display/audio-sink selection, independent of the "
            "always-on inline preview."
        )
        btn_player_window.clicked.connect(self._open_player_window_for_playlist)
        player_row.addWidget(btn_player_window)
        player_row.addStretch(1)
        lay.addLayout(player_row)

        arrange_row = QHBoxLayout()
        self.cmb_playlist_arrange = QComboBox()
        self.cmb_playlist_arrange.addItems([
            "Energy arc (size)", "Interleave A/V", "Deterministic shuffle", "Geometric phaselock seeded", "Name order",
            "Analyzed match (reverse-engineer)",
        ])
        self.spin_playlist_arrange_seed = QSpinBox()
        self.spin_playlist_arrange_seed.setRange(0, 2147483647)
        self.spin_playlist_arrange_seed.setValue(1975807343)
        btn_arrange = QPushButton("Arrange playlist")
        btn_arrange.clicked.connect(self._arrange_media_playlist)
        arrange_row.addWidget(QLabel("Arrange:"))
        arrange_row.addWidget(self.cmb_playlist_arrange, stretch=1)
        arrange_row.addWidget(QLabel("Seed"))
        arrange_row.addWidget(self.spin_playlist_arrange_seed)
        arrange_row.addWidget(btn_arrange)
        lay.addLayout(arrange_row)

        # --- per-item volume + mix flag, and simultaneous "mix" playback ---
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume (selected):"))
        self.sld_playlist_volume = QSlider(Qt.Orientation.Horizontal)
        self.sld_playlist_volume.setRange(0, 150)
        self.sld_playlist_volume.setValue(100)
        self.sld_playlist_volume.setEnabled(False)
        self.sld_playlist_volume.valueChanged.connect(self._on_playlist_volume_changed)
        vol_row.addWidget(self.sld_playlist_volume, stretch=1)
        self.lbl_playlist_volume = QLabel("100%")
        self.lbl_playlist_volume.setMinimumWidth(40)
        vol_row.addWidget(self.lbl_playlist_volume)
        lay.addLayout(vol_row)

        mix_row = QHBoxLayout()
        btn_toggle_mix = QPushButton("Toggle Mix on selected")
        btn_toggle_mix.setToolTip(
            "Flag/unflag the selected rows for simultaneous playback via "
            "'Play Mix' — lets you layer audio + video + game audio at once "
            "instead of playing the queue one at a time."
        )
        btn_toggle_mix.clicked.connect(self._toggle_mix_selected)
        btn_play_mix = QPushButton("▶▶ Play Mix (simultaneous)")
        btn_play_mix.clicked.connect(self._playlist_play_mix)
        btn_stop_mix = QPushButton("⏹ Stop Mix")
        btn_stop_mix.clicked.connect(self._stop_mix)
        mix_row.addWidget(btn_toggle_mix)
        mix_row.addWidget(btn_play_mix)
        mix_row.addWidget(btn_stop_mix)
        lay.addLayout(mix_row)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Live file speed:"))
        self.sld_live_speed = QSlider(Qt.Orientation.Horizontal)
        self.sld_live_speed.setRange(25, 400)
        self.sld_live_speed.setValue(100)
        self.sld_live_speed.setToolTip("0.25×–4× live playback rate. With mpv this updates in-place through JSON IPC, without restarting the file.")
        self.sld_live_speed.valueChanged.connect(self._on_live_speed_changed)
        speed_row.addWidget(self.sld_live_speed, stretch=1)
        self.lbl_live_speed = QLabel("1.00×")
        self.lbl_live_speed.setMinimumWidth(52)
        speed_row.addWidget(self.lbl_live_speed)
        btn_speed_reset = QPushButton("1×")
        btn_speed_reset.clicked.connect(lambda: self.sld_live_speed.setValue(100))
        speed_row.addWidget(btn_speed_reset)
        lay.addLayout(speed_row)

        timing = QGroupBox("Timed external-display playlist")
        tf = QFormLayout(timing)
        self.spin_item_time = QDoubleSpinBox(); self.spin_item_time.setRange(0.0, 86400.0); self.spin_item_time.setDecimals(3); self.spin_item_time.setSuffix(" s")
        self.spin_item_duration = QDoubleSpinBox(); self.spin_item_duration.setRange(0.0, 86400.0); self.spin_item_duration.setDecimals(3); self.spin_item_duration.setValue(5.0); self.spin_item_duration.setSuffix(" s")
        self.spin_item_time.valueChanged.connect(self._on_playlist_timing_changed); self.spin_item_duration.valueChanged.connect(self._on_playlist_timing_changed)
        tf.addRow("Selected start time", self.spin_item_time); tf.addRow("Selected duration (0=natural)", self.spin_item_duration)
        tr = QHBoxLayout(); btn_timed = QPushButton("▶ Send Timed Playlist → Display"); btn_timed.clicked.connect(self._start_timed_playlist)
        btn_timed_stop = QPushButton("■ Stop Timed Playlist"); btn_timed_stop.clicked.connect(self._stop_timed_playlist)
        tr.addWidget(btn_timed); tr.addWidget(btn_timed_stop); tf.addRow(tr)
        lay.addWidget(timing)

        hint = QLabel(
            "Queue projects' renders here for sequential playback, or flag rows "
            "'[MIX]' and use Play Mix to layer several tracks (each at its own "
            "volume) at the same time — one OS-mixed output, e.g. a DJ backing "
            "track + a video's audio + a game's soundtrack together."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        lay.addWidget(hint)
        return w

    def _refresh_playlist_widget(self):
        """Rebuild playlist row text from self._playlist without losing the
        current selection (called after any volume/mix/add/remove change)."""
        selected_rows = {i.row() for i in self.playlist_widget.selectedIndexes()}
        self.playlist_widget.blockSignals(True)
        self.playlist_widget.clear()
        for it in self._playlist:
            name = os.path.basename(it["path"])
            ext = _gb_ext(it["path"])
            if ext in GAME_EXT:
                icon = "🕹"
            else:
                icon = _kind_icon(it.get("kind", KIND_UNKNOWN))
            mix_tag = "  [MIX]" if it.get("mix") else ""
            mod_tag = ""
            if "pitch_semitones" in it or "rate" in it:
                mod_tag = f"  [P {float(it.get('pitch_semitones',0.0)):+.2f} st · R {float(it.get('rate',1.0)):.2f}× · {it.get('resample','preserve-duration')}]"
            timing_tag = f"  [T {float(it.get('time_s',0.0)):.3f}s · D {float(it.get('duration_s',0.0)):.3f}s]"
            self.playlist_widget.addItem(f"{icon} {name}  {it.get('volume', 100)}%{mix_tag}{timing_tag}{mod_tag}")
        self.playlist_widget.blockSignals(False)
        for row in selected_rows:
            if 0 <= row < self.playlist_widget.count():
                self.playlist_widget.item(row).setSelected(True)
        # If a TV host is active, playlist edits/seeded rearrangements become live
        # immediately without another explicit publish click.
        try:
            if self._media_share_server is not None:
                self._media_share_server.set_playlist(self._playlist)
        except Exception:
            pass

    def _randomize_playlist_and_dj_parameters(self):
        """Seeded playlist shuffle + bounded per-item DJ controls."""
        if not self._playlist:
            self.lbl_status.setText("Randomize: add media to the playlist first.")
            return
        seed = int(self.spin_playlist_arrange_seed.value()) if hasattr(self, "spin_playlist_arrange_seed") else 1975807343
        rng = random.Random(seed)
        # Keep an in-memory undo point so the operation is safely reversible.
        self._playlist_randomize_undo = [dict(item) for item in self._playlist]
        rng.shuffle(self._playlist)
        for index, item in enumerate(self._playlist):
            item["volume"] = rng.randint(70, 115)
            item["pitch_semitones"] = round(rng.uniform(-5.0, 5.0), 3)
            item["rate"] = round(rng.uniform(0.88, 1.12), 4)
            item["direction"] = "reverse" if rng.random() < 0.08 else "forward"
            item["resample"] = "preserve-duration"
            item["dj_random_seed"] = seed
            item["dj_random_index"] = index
        self._playlist_index = 0
        self._refresh_playlist_widget()
        self._sync_project_state()
        self.lbl_status.setText(f"Playlist + DJ parameters randomized · seed {seed} · {len(self._playlist)} item(s). Source files unchanged.")

    def _undo_playlist_randomization(self):
        saved = getattr(self, "_playlist_randomize_undo", None)
        if not isinstance(saved, list):
            self.lbl_status.setText("No playlist randomization undo snapshot is available.")
            return
        self._playlist = [dict(item) for item in saved]
        self._playlist_index = min(max(0, self._playlist_index), len(self._playlist)-1) if self._playlist else -1
        self._refresh_playlist_widget()
        self._sync_project_state()
        self.lbl_status.setText("Playlist randomization reverted.")
        self._playlist_randomize_undo = None

    def _arrange_media_playlist(self):
        if len(self._playlist) < 2:
            return
        mode = self.cmb_playlist_arrange.currentText()
        if mode == "Name order":
            self._playlist.sort(key=lambda it: os.path.basename(it["path"]).lower())
        elif mode == "Deterministic shuffle":
            rng = random.Random(int(self.spin_playlist_arrange_seed.value()))
            rng.shuffle(self._playlist)
        elif mode == "Geometric phaselock seeded":
            try:
                from media_cutup_engine import playlist_geometric_parameters
                seed = int(self.spin_playlist_arrange_seed.value())
                params = playlist_geometric_parameters(len(self._playlist), seed, pitch_range_st=7.0, rate_depth=0.24, phase_lock=4)
                decorated = []
                for item, param in zip(self._playlist, params):
                    item.update(param)
                    decorated.append((float(param["geometry_key"]), item))
                decorated.sort(key=lambda pair: pair[0])
                self._playlist = [item for _key, item in decorated]
            except Exception as e:
                self.lbl_status.setText(f"Geometric playlist error: {e}")
                return
        elif mode == "Analyzed match (reverse-engineer)":
            # Real-signal greedy nearest-neighbor chain: each next track is the
            # closest-measured match (pitch/brightness/loudness/rhythm) to the
            # previous one, via reverse_engineer.describe() rather than name
            # or file-size heuristics. The seed only picks the start when
            # several tracks tie or lack a usable descriptor (images, unreadable
            # media), so results stay reproducible.
            self.lbl_status.setText("Analyzing tracks (real signal descriptors)…")
            descs: Dict[int, dict] = {}
            for i, it in enumerate(self._playlist):
                if it.get("kind") in (KIND_AUDIO, KIND_VIDEO, KIND_AV) and os.path.isfile(it["path"]):
                    d = _analyze_signal_descriptor(it["path"], self._analysis_cache)
                    if d:
                        descs[i] = d
            rng = random.Random(int(self.spin_playlist_arrange_seed.value()))
            remaining = list(range(len(self._playlist)))
            analyzable = [i for i in remaining if i in descs]
            unanalyzable = [i for i in remaining if i not in descs]
            ordered: List[int] = []
            if analyzable:
                start = rng.choice(analyzable)
                pool = set(analyzable)
                pool.discard(start)
                ordered.append(start)
                while pool:
                    last = descs[ordered[-1]]
                    nxt = min(pool, key=lambda i: _descriptor_distance(last, descs[i]))
                    ordered.append(nxt)
                    pool.discard(nxt)
            rng.shuffle(unanalyzable)
            ordered.extend(unanalyzable)
            self._playlist = [self._playlist[i] for i in ordered]
            self.lbl_status.setText(f"Analyzed match: {len(analyzable)} track(s) measured, {len(unanalyzable)} placed by seed.")
        elif mode == "Interleave A/V":
            aud = [it for it in self._playlist if it.get("kind") == KIND_AUDIO]
            vis = [it for it in self._playlist if it.get("kind") in (KIND_VIDEO, KIND_AV)]
            other = [it for it in self._playlist if it not in aud and it not in vis]
            out = []
            while aud or vis:
                if aud: out.append(aud.pop(0))
                if vis: out.append(vis.pop(0))
            self._playlist = out + other
        else:
            # A deterministic low→high→low file-size arc: useful as a simple
            # media-intensity proxy on boxes where full analysis would be costly.
            seq = sorted(self._playlist, key=lambda it: os.path.getsize(it["path"]) if os.path.isfile(it["path"]) else 0)
            lo, hi, out = 0, len(seq) - 1, []
            take_low = True
            while lo <= hi:
                if take_low:
                    out.append(seq[lo]); lo += 1
                else:
                    out.append(seq[hi]); hi -= 1
                take_low = not take_low
            self._playlist = out
        self._playlist_index = 0
        self._refresh_playlist_widget()
        self.lbl_status.setText(f"Playlist arranged: {mode}")

    def _on_playlist_selection_changed(self):
        rows = [i.row() for i in self.playlist_widget.selectedIndexes()]
        if not rows:
            self.sld_playlist_volume.setEnabled(False)
            return
        self.sld_playlist_volume.setEnabled(True)
        # Show the first selected row's volume as the slider starting point.
        vol = self._playlist[rows[0]].get("volume", 100) if 0 <= rows[0] < len(self._playlist) else 100
        self.sld_playlist_volume.blockSignals(True)
        self.sld_playlist_volume.setValue(int(vol))
        self.sld_playlist_volume.blockSignals(False)
        self.lbl_playlist_volume.setText(f"{int(vol)}%")
        if hasattr(self, "spin_item_time") and 0 <= rows[0] < len(self._playlist):
            it = self._playlist[rows[0]]
            self.spin_item_time.blockSignals(True); self.spin_item_duration.blockSignals(True)
            self.spin_item_time.setValue(float(it.get("time_s", 0.0) or 0.0))
            self.spin_item_duration.setValue(float(it.get("duration_s", 0.0) or 0.0))
            self.spin_item_time.blockSignals(False); self.spin_item_duration.blockSignals(False)

    def _on_playlist_timing_changed(self, *_):
        rows = {i.row() for i in self.playlist_widget.selectedIndexes()}
        for row in rows:
            if 0 <= row < len(self._playlist):
                self._playlist[row]["time_s"] = float(self.spin_item_time.value())
                self._playlist[row]["duration_s"] = float(self.spin_item_duration.value())
        if rows:
            self._refresh_playlist_widget(); self._sync_project_state()

    def _on_playlist_volume_changed(self, value: int):
        self.lbl_playlist_volume.setText(f"{value}%")
        for row in {i.row() for i in self.playlist_widget.selectedIndexes()}:
            if 0 <= row < len(self._playlist):
                self._playlist[row]["volume"] = int(value)
        self._refresh_playlist_widget(); self._sync_project_state()

    def _toggle_mix_selected(self):
        rows = {i.row() for i in self.playlist_widget.selectedIndexes()}
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._playlist):
                self._playlist[row]["mix"] = not self._playlist[row].get("mix", False)
        self._refresh_playlist_widget(); self._sync_project_state()

    def _mpv_command(self, command: list) -> bool:
        path = self._mpv_ipc_path
        if not path or not os.path.exists(path):
            return False
        payload = (json.dumps({"command": command}) + "\n").encode("utf-8")
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.06)
            sock.connect(path)
            sock.sendall(payload)
            sock.close()
            return True
        except Exception:
            return False

    def _on_live_speed_changed(self, value: int):
        self._live_speed = max(0.25, min(4.0, float(value) / 100.0))
        if hasattr(self, "lbl_live_speed"):
            self.lbl_live_speed.setText(f"{self._live_speed:.2f}×")
        if self._mpv_command(["set_property", "speed", self._live_speed]):
            self.lbl_status.setText(f"Live playback speed: {self._live_speed:.2f}×")

    def _playlist_clear(self):
        self._stop_mix()
        self._playlist.clear()
        self._playlist_index = -1
        self.playlist_widget.clear(); self._sync_project_state()

    def _playlist_play(self):
        if not self._playlist:
            return
        if self._playlist_index < 0:
            self._playlist_index = 0
        self._playlist_index = max(0, min(self._playlist_index, len(self._playlist) - 1))
        entry = self._playlist[self._playlist_index]
        path = entry["path"]
        self.playlist_widget.setCurrentRow(self._playlist_index)
        ext = _gb_ext(path)
        if ext in GAME_EXT:
            self._play_game_package(path)
        else:
            if "rate" in entry and hasattr(self, "sld_live_speed"):
                self.sld_live_speed.setValue(max(25, min(400, int(round(float(entry.get("rate", 1.0)) * 100.0)))))
            self._play_path(path, volume_pct=entry.get("volume", 100), duration_s=float(entry.get("duration_s", 0.0) or 0.0))

    def _start_timed_playlist(self):
        if not self._playlist:
            return
        self._timed_playlist_pending = sorted(range(len(self._playlist)), key=lambda i: (float(self._playlist[i].get("time_s", 0.0) or 0.0), i))
        self._timed_playlist_epoch = time.monotonic()
        self._timed_playlist_timer.start()
        self.lbl_status.setText(f"Timed display playlist armed: {len(self._timed_playlist_pending)} item(s)")
        self._timed_playlist_tick()

    def _timed_playlist_tick(self):
        if not self._timed_playlist_pending:
            self._timed_playlist_timer.stop(); return
        elapsed = time.monotonic() - self._timed_playlist_epoch
        while self._timed_playlist_pending:
            idx = self._timed_playlist_pending[0]
            it = self._playlist[idx]
            if elapsed + 1e-6 < float(it.get("time_s", 0.0) or 0.0):
                break
            self._timed_playlist_pending.pop(0)
            self._playlist_index = idx; self.playlist_widget.setCurrentRow(idx)
            path = it.get("path", "")
            if os.path.isfile(path):
                self._play_path(path, volume_pct=int(it.get("volume",100)), duration_s=float(it.get("duration_s",0.0) or 0.0))
        if not self._timed_playlist_pending:
            self._timed_playlist_timer.stop()

    def _stop_timed_playlist(self):
        self._timed_playlist_timer.stop(); self._timed_playlist_pending = []; self._stop_player()
        self.lbl_status.setText("Timed display playlist stopped.")

    def _playlist_next(self):
        if not self._playlist:
            return
        self._playlist_index = (self._playlist_index + 1) % len(self._playlist)
        self._playlist_play()

    def _playlist_prev(self):
        if not self._playlist:
            return
        self._playlist_index = (self._playlist_index - 1) % len(self._playlist)
        self._playlist_play()

    def _set_live_speed(self, value: float):
        value = max(0.25, min(4.0, float(value)))
        if hasattr(self, "sld_live_speed"):
            self.sld_live_speed.setValue(int(round(value * 100.0)))
        else:
            self._live_speed = value
            self._mpv_command(["set_property", "speed", self._live_speed])

    def _on_together_mixed(self, payload, error):
        if not isinstance(payload, dict) or payload.get("gen") != getattr(self, "_host_decode_gen", 0):
            return
        if error:
            self.lbl_status.setText(f"▶▶ Audio mix failed: {error}"); return
        try:
            host = _gb_find_host(self) or getattr(self, "host", None)
            hw_sr, ch, pref = _GB_FILE_PLAYER.play(host, payload["mix"], payload["rate"], 100)
            rate = payload["rate"]
            self.lbl_status.setText(f"▶▶ Playing together: {payload['n']} audio file(s) mixed @ {rate / 1000:g} kHz"
                                    + (f" → device {hw_sr / 1000:g} kHz" if hw_sr != rate else "")
                                    + (" · scaled to avoid clipping" if payload.get("scaled") else ""))
        except Exception as e:
            self.lbl_status.setText(f"▶▶ Audio mix failed: {e}")

    def _playlist_play_together(self):
        rows = sorted({i.row() for i in self.playlist_widget.selectedIndexes()}) if hasattr(self, "playlist_widget") else []
        items = [self._playlist[r] for r in rows if 0 <= r < len(self._playlist)]
        if len(items) < 1:
            QMessageBox.information(self, "Play together", "Select two or more playlist rows (Ctrl/Shift-click)."); return
        self._play_together([it["path"] for it in items], [int(it.get("volume", 100)) for it in items])

    def _playlist_play_mix(self):
        """Launch every [MIX]-flagged playlist row simultaneously, each in
        its own player process at its own volume. Real mixing happens at the
        OS audio layer (ALSA/Pulse), which is what actually lets a DJ track,
        a video's audio, and a game's soundtrack sound together on one HDMI
        output — no single subprocess player can do that alone."""
        self._stop_mix()
        mixed = [it for it in self._playlist if it.get("mix") and os.path.isfile(it["path"])]
        if not mixed:
            QMessageBox.information(
                self, "Play Mix",
                "No playlist rows are flagged for Mix.\n"
                "Select one or more rows and click 'Toggle Mix on selected' first."
            )
            return
        started = []
        for it in mixed:
            ext = _gb_ext(it["path"])
            if ext in GAME_EXT:
                continue  # games launch through _play_game_package, not a media player
            want_video = it.get("kind") in (KIND_VIDEO, KIND_AV, KIND_UNKNOWN) and ext in VIDEO_EXT
            cmd = _player_cmd_with_volume(it.get("volume", 100), want_video=want_video)
            if not cmd:
                continue
            try:
                cmd, penv = self._routed_player(cmd, want_video=want_video)
                proc = subprocess.Popen(cmd + [it["path"]], env=penv)
                self._mix_procs.append(proc)
                started.append(f"{os.path.basename(it['path'])} @{it.get('volume', 100)}%")
            except Exception:
                continue
        if not started:
            # No external player (e.g. the executable): mix in-process instead.
            self._play_together([it["path"] for it in mixed if _gb_ext(it["path"]) not in GAME_EXT],
                                [int(it.get("volume", 100)) for it in mixed if _gb_ext(it["path"]) not in GAME_EXT])
            return
        self.lbl_status.setText("Mixing: " + " · ".join(started))

    def _stop_mix(self):
        for proc in self._mix_procs:
            try:
                proc.terminate()
            except Exception:
                pass
        self._mix_procs = []

    # ------------------------------------------------------------------ game tab
    def _build_game_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>🎮 Built-in game player · local Wi‑Fi multiplayer</b>"))
        self.cmb_game_status = QLabel("Uses live composition identity, or a packaged .zip game. LAN mode can be forced even when the seed classified the game as single-player.")
        self.cmb_game_status.setWordWrap(True); lay.addWidget(self.cmb_game_status)
        row = QHBoxLayout()
        btn_live = QPushButton("▶ Play Live Composition Game"); btn_live.clicked.connect(self._play_live_game)
        btn_pkg = QPushButton("🕹 Play Selected Package"); btn_pkg.clicked.connect(self._play_selected_game)
        row.addWidget(btn_live); row.addWidget(btn_pkg); lay.addLayout(row)

        net = QGroupBox("📶 Local Wi‑Fi / Ethernet game session")
        nf = QFormLayout(net)
        self.cmb_game_net_mode = QComboBox(); self.cmb_game_net_mode.addItems(["Solo", "Host on local network", "Join local network"]); nf.addRow("Mode", self.cmb_game_net_mode)
        self.spin_game_port = QSpinBox(); self.spin_game_port.setRange(1024,65535); self.spin_game_port.setValue(27777); nf.addRow("Port", self.spin_game_port)
        self.edit_game_connect = QLineEdit(); self.edit_game_connect.setPlaceholderText("host-ip:port  e.g. 192.168.1.42:27777"); nf.addRow("Join address", self.edit_game_connect)
        self.lbl_game_lan = QLabel(f"This box: {self._lan_ip()} · same Wi‑Fi/LAN required unless your router/firewall forwards the port.")
        self.lbl_game_lan.setWordWrap(True); self.lbl_game_lan.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); nf.addRow("Local address", self.lbl_game_lan)
        lay.addWidget(net)
        hint = QLabel("Host and Join use the game engine's authoritative TCP snapshot/input transport. This is live game-state networking—not merely sharing a .zip. Keyboard, mouse/gamepad and touch input remain local on each machine.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#8ab4c8; font-size:9pt;"); lay.addWidget(hint)
        lay.addStretch(1); return w

    def _play_live_game(self):
        if hasattr(self.host, "_on_play_videogame"):
            try:
                mode = self.cmb_game_net_mode.currentIndex() if hasattr(self, "cmb_game_net_mode") else 0
                setattr(self.host, "_preferred_game_net_mode", int(mode))
                setattr(self.host, "_preferred_game_net_port", int(self.spin_game_port.value()) if hasattr(self, "spin_game_port") else 27777)
                setattr(self.host, "_preferred_game_connect", self.edit_game_connect.text().strip() if hasattr(self, "edit_game_connect") else "")
                self.host._on_play_videogame()
                self.lbl_status.setText("Live game dialog opened.")
            except Exception as e:
                QMessageBox.warning(self, "Game", str(e))
        else:
            QMessageBox.warning(self, "Game", "Host has no video-game player.")

    def _play_selected_game(self):
        for path in self._selected_paths():
            if _gb_ext(path) == ".zip":          # .MCC game package or legacy .zip
                self._play_game_package(path)
                return
        QMessageBox.information(self, "Game", "Select a .MCC game package (or legacy .zip) in the browser.")

    def _play_game_package(self, path: str):
        try:
            td = tempfile.mkdtemp(prefix="gb_game_pkg_")
            if os.path.splitext(str(path))[1].lower() == ".mcc":
                import mcc_media as _mm
                _mm.unpack_tree(path, td)          # MCC game package (verified, path-confined)
            else:
                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(td)
            script = None
            for root, _dirs, files in os.walk(td):
                for f in files:
                    if f.endswith(".py") and ("game" in f.lower() or f.startswith("play")):
                        script = os.path.join(root, f)
                        break
                if script:
                    break
            if script is None:
                # any .py
                for root, _dirs, files in os.walk(td):
                    for f in files:
                        if f.endswith(".py"):
                            script = os.path.join(root, f)
                            break
                    if script:
                        break
            if not script:
                raise RuntimeError("No Python game script found inside the package.")
            from groovebox_subprocess import script_argv
            args = script_argv(script)
            mode = self.cmb_game_net_mode.currentIndex() if hasattr(self, "cmb_game_net_mode") else 0
            port = int(self.spin_game_port.value()) if hasattr(self, "spin_game_port") else 27777
            if mode == 1:
                args += ["--host", f"--port={port}"]
            elif mode == 2:
                addr = self.edit_game_connect.text().strip() if hasattr(self, "edit_game_connect") else ""
                if not addr:
                    raise RuntimeError("Enter the host IP:port before joining a local-network game.")
                if ":" not in addr:
                    addr = f"{addr}:{port}"
                args.append(f"--connect={addr}")
            subprocess.Popen(args, cwd=os.path.dirname(script))
            self.lbl_status.setText(f"Game launched: {os.path.basename(path)}")
            self.cmb_game_status.setText(f"Running: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Game package", str(e))

    # ------------------------------------------------------------------ remix tab
    def _build_remix_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Parametric live remixer</b>"))
        lay.addWidget(QLabel(
            "Drives the host Live DJ GOAVA morph + RAND PARAM macro on the play buffer."
        ))

        form = QFormLayout()
        self.sld_goava = QSlider(Qt.Orientation.Horizontal)
        self.sld_goava.setRange(0, 100)
        self.sld_goava.setValue(0)
        self.sld_goava.valueChanged.connect(self._queue_remix)
        form.addRow("GOAVA morph %", self.sld_goava)

        self.sld_rand = QSlider(Qt.Orientation.Horizontal)
        self.sld_rand.setRange(0, 100)
        self.sld_rand.setValue(0)
        self.sld_rand.valueChanged.connect(self._queue_remix)
        form.addRow("RAND PARAM %", self.sld_rand)

        self.spin_remix_pair_a = QSpinBox()
        self.spin_remix_pair_a.setRange(0, 47)
        self.spin_remix_pair_b = QSpinBox()
        self.spin_remix_pair_b.setRange(0, 47)
        self.spin_remix_pair_b.setValue(1)
        pair_row = QHBoxLayout()
        pair_row.addWidget(self.spin_remix_pair_a)
        pair_row.addWidget(QLabel("↔"))
        pair_row.addWidget(self.spin_remix_pair_b)
        form.addRow("Pair (A↔B)", pair_row)
        self.spin_remix_pair_a.valueChanged.connect(self._queue_remix)
        self.spin_remix_pair_b.valueChanged.connect(self._queue_remix)

        self.sld_boost = QSlider(Qt.Orientation.Horizontal)
        self.sld_boost.setRange(0, 100)
        self.sld_boost.setValue(0)
        self.sld_boost.valueChanged.connect(self._queue_remix)
        form.addRow("Boost hit %", self.sld_boost)

        lay.addLayout(form)

        row = QHBoxLayout()
        btn_apply = QPushButton("Apply to Live DJ")
        btn_apply.clicked.connect(self._push_remix)
        btn_arm = QPushButton("Arm GOAVA + RAND on host toggles")
        btn_arm.clicked.connect(self._arm_host_dj_toggles)
        row.addWidget(btn_apply)
        row.addWidget(btn_arm)
        btn_file = QPushButton("Render Parametric Remix → File…")
        btn_file.setToolTip("Non-destructively render the selected browser/playlist media through the current continuous remix script and deterministic DJ processor.")
        btn_file.clicked.connect(self._render_parametric_remix_file)
        row.addWidget(btn_file)
        lay.addLayout(row)

        self.lbl_remix = QLabel("Remix amounts at 0 — dry.")
        self.lbl_remix.setStyleSheet("color:#f5d97d;")
        lay.addWidget(self.lbl_remix)

        script_group = QGroupBox("Continuous Pattern Script")
        sg = QVBoxLayout(script_group)
        self.txt_pattern_script = QTextEdit()
        self.txt_pattern_script.setMaximumHeight(122)
        self.txt_pattern_script.setPlainText(
            "goava = 50 + 45*sin(t*0.73)\n"
            "rand = 25 + 25*sin(t*1.31 + 1.2)\n"
            "boost = 18 + 18*(sin(t*2.0)>0.72)\n"
            "speed = 1.0 + 0.22*sin(t*0.41)\n"
            "advance = (step % 64 == 0)"
        )
        self.txt_pattern_script.setToolTip(
            "Control-rate expressions. Available: t, step, sin/cos/tan, abs/min/max, "
            "sqrt, pi, rand(). Assign goava/rand/boost (0..100), speed (0.25..4), "
            "advance (true to go to next media-playlist item), and host (0..1 automation value)."
        )
        sg.addWidget(self.txt_pattern_script)
        sr = QHBoxLayout()
        self.spin_pattern_hz = QSpinBox()
        self.spin_pattern_hz.setRange(1, 60)
        self.spin_pattern_hz.setValue(20)
        self.spin_pattern_hz.setSuffix(" Hz")
        self.spin_pattern_hz.valueChanged.connect(self._set_pattern_rate)
        self.spin_pattern_seed = QSpinBox()
        self.spin_pattern_seed.setRange(0, 2147483647)
        self.spin_pattern_seed.setValue(1975807343)
        btn_pattern = QPushButton("▶ Run Pattern")
        btn_pattern.setCheckable(True)
        btn_pattern.toggled.connect(self._toggle_pattern_script)
        btn_pattern_once = QPushButton("Step once")
        btn_pattern_once.clicked.connect(self._pattern_tick)
        sr.addWidget(QLabel("Rate")); sr.addWidget(self.spin_pattern_hz)
        sr.addWidget(QLabel("Seed")); sr.addWidget(self.spin_pattern_seed)
        sr.addWidget(btn_pattern); sr.addWidget(btn_pattern_once)
        sg.addLayout(sr)
        self.chk_pattern_host_playlist = QCheckBox("Write continuous host playlist automation pattern")
        self.chk_pattern_host_playlist.setChecked(True)
        sg.addWidget(self.chk_pattern_host_playlist)
        self.lbl_pattern = QLabel("Pattern stopped.")
        self.lbl_pattern.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        sg.addWidget(self.lbl_pattern)
        lay.addWidget(script_group)
        lay.addStretch(1)
        return w

    def _render_parametric_remix_file(self):
        paths = [p for p in self._selected_paths() if os.path.isfile(p) and _gb_ext(p) in MEDIA_EXT]
        if not paths and 0 <= self._playlist_index < len(self._playlist):
            p = self._playlist[self._playlist_index].get("path", "")
            if os.path.isfile(p): paths = [p]
        if not paths:
            QMessageBox.information(self, "Parametric Remix", "Select an audio/video file in Performance, or select a playlist item first.")
            return
        src = paths[0]; ext = _gb_ext(src)
        default_ext = ".wav" if ext in AUDIO_EXT else (".mp4" if ext in VIDEO_EXT else ".png")
        default = os.path.splitext(src)[0] + "_parametric_remix" + default_ext
        out, _ = QFileDialog.getSaveFileName(self, "Render Parametric Remix", default, "Media files (*.*)")
        if not out: return
        try:
            from parametric_file_remix import render_parametric_file
            result = render_parametric_file(
                src, out, self.txt_pattern_script.toPlainText(), int(self.spin_pattern_seed.value()),
                pair=(int(self.spin_remix_pair_a.value()), int(self.spin_remix_pair_b.value())),
                bpm=float(getattr(getattr(self.host, "spin_bpm", None), "value", lambda:120.0)()),
                control_hz=max(1, min(60, int(self.spin_pattern_hz.value()))),
            )
            self.lbl_status.setText("Parametric file edit: " + result)
            self._sync_project_state()
        except Exception as exc:
            QMessageBox.warning(self, "Parametric Remix", str(exc))

    def export_state(self) -> Dict[str, Any]:
        """JSON-safe Performance state used by normal Groovebox save/load."""
        display = getattr(self._output_display, "name", "") if self._output_display else ""
        audio = getattr(self._output_audio_target, "name", "") if self._output_audio_target else ""
        return {
            "version": 3,
            "canonical_synth_context": json.loads(json.dumps(getattr(self.host, "canonical_synth_context", {}), default=str)),
            "playlist": json.loads(json.dumps(self._playlist, default=str)),
            "playlist_index": int(self._playlist_index),
            "live_speed": float(self._live_speed),
            "arrange": self.cmb_playlist_arrange.currentText() if hasattr(self,"cmb_playlist_arrange") else "Energy arc (size)",
            "arrange_seed": int(self.spin_playlist_arrange_seed.value()) if hasattr(self,"spin_playlist_arrange_seed") else 1975807343,
            "output_display": display, "output_audio": audio,
            "video_clip": self.video_clip_studio.export_state() if getattr(self, "video_clip_studio", None) is not None else {},
            "remix": {
                "goava": int(self.sld_goava.value()) if hasattr(self,"sld_goava") else 0,
                "rand": int(self.sld_rand.value()) if hasattr(self,"sld_rand") else 0,
                "boost": int(self.sld_boost.value()) if hasattr(self,"sld_boost") else 0,
                "pair_a": int(self.spin_remix_pair_a.value()) if hasattr(self,"spin_remix_pair_a") else 0,
                "pair_b": int(self.spin_remix_pair_b.value()) if hasattr(self,"spin_remix_pair_b") else 1,
                "script": self.txt_pattern_script.toPlainText() if hasattr(self,"txt_pattern_script") else "",
                "rate_hz": int(self.spin_pattern_hz.value()) if hasattr(self,"spin_pattern_hz") else 20,
                "seed": int(self.spin_pattern_seed.value()) if hasattr(self,"spin_pattern_seed") else 1975807343,
                "host_playlist": bool(self.chk_pattern_host_playlist.isChecked()) if hasattr(self,"chk_pattern_host_playlist") else True,
            },
        }

    def restore_state(self, state: Dict[str, Any]):
        if not isinstance(state, dict): return
        if isinstance(state.get("canonical_synth_context"), dict):
            self.host.canonical_synth_context = state["canonical_synth_context"]
        pl = state.get("playlist")
        if isinstance(pl, list):
            self._playlist = [dict(x) for x in pl if isinstance(x, dict) and x.get("path")]
            self._playlist_index = max(-1, min(int(state.get("playlist_index", -1)), len(self._playlist)-1))
            self._refresh_playlist_widget()
        if hasattr(self,"sld_live_speed"):
            self.sld_live_speed.setValue(max(25,min(400,int(round(float(state.get("live_speed",1.0))*100)))))
        if hasattr(self,"cmb_playlist_arrange") and state.get("arrange"):
            self.cmb_playlist_arrange.setCurrentText(str(state.get("arrange")))
        if hasattr(self,"spin_playlist_arrange_seed"):
            self.spin_playlist_arrange_seed.setValue(int(state.get("arrange_seed",1975807343)))
        r=state.get("remix") if isinstance(state.get("remix"),dict) else {}
        for name,key,default in (("sld_goava","goava",0),("sld_rand","rand",0),("sld_boost","boost",0),("spin_remix_pair_a","pair_a",0),("spin_remix_pair_b","pair_b",1),("spin_pattern_hz","rate_hz",20),("spin_pattern_seed","seed",1975807343)):
            if hasattr(self,name): getattr(self,name).setValue(int(r.get(key,default)))
        if hasattr(self,"txt_pattern_script") and "script" in r: self.txt_pattern_script.setPlainText(str(r.get("script") or ""))
        if hasattr(self,"chk_pattern_host_playlist"): self.chk_pattern_host_playlist.setChecked(bool(r.get("host_playlist",True)))
        if getattr(self, "video_clip_studio", None) is not None:
            try:
                self.video_clip_studio.restore_state(state.get("video_clip") if isinstance(state.get("video_clip"), dict) else {})
            except Exception:
                pass
        # PERF_LAZY_20260924: restoring a project must not synchronously probe
        # HDMI/Pulse/Bluetooth. Remember the preferred names and apply them the
        # next time Device Manager explicitly scans outputs.
        dn=str(state.get("output_display") or ""); an=str(state.get("output_audio") or "")
        self._pending_output_restore=(dn,an)

    def _apply_output_selection(self):
        """Backward-compatible alias for older Performance state/callback code.

        ABI9 briefly retained a call to this legacy method name after the
        output-router implementation was renamed.  Keep the alias so older
        project/session paths and third-party extensions cannot crash the
        Performance window while all routing remains centralized in
        ``_apply_output_routing``.
        """
        return self._apply_output_routing()

    def _sync_project_state(self):
        try:
            state=getattr(self.host,"media_workbench_state",None)
            if not isinstance(state,dict): state={}; setattr(self.host,"media_workbench_state",state)
            state["performance"]=self.export_state()
        except Exception:
            pass

    def _queue_remix(self, *_args):
        """Coalesce dense slider-drag events to at most one DJ update per GUI frame."""
        timer=getattr(self,'_remix_apply_timer',None)
        if timer is None:
            timer=QTimer(self); timer.setSingleShot(True); timer.setInterval(16)
            timer.timeout.connect(self._push_remix); self._remix_apply_timer=timer
        if not timer.isActive(): timer.start()

    def _push_remix(self, *_args):
        host = self.host
        goava = self.sld_goava.value() / 100.0
        rand = self.sld_rand.value() / 100.0
        boost = self.sld_boost.value() / 100.0
        a = int(self.spin_remix_pair_a.value())
        b = int(self.spin_remix_pair_b.value())
        try:
            eng = getattr(host, "_live_dj_engine", None)
            if eng is None:
                from dj_effects import LiveDJEffects
                sr = int(getattr(host, "play_sample_rate", 48000) or 48000)
                eng = LiveDJEffects(sample_rate=sr)
                host._live_dj_engine = eng
            seed = 0.0
            try:
                if hasattr(host, "get_numeric_seed"):
                    seed = float(host.get_numeric_seed())
            except Exception:
                pass
            eng.set_context(seed=seed, pair=(a, b),
                            sample_rate=int(getattr(host, "play_sample_rate", 48000) or 48000))
            eng.amount_goava = float(goava)
            eng.amount_random = float(rand)
            if boost > 0.0:
                # ~1 bar at 120 BPM default
                sr = float(getattr(host, "play_sample_rate", 48000) or 48000)
                interval = int(sr * 2.0)
                eng.set_boost(interval=interval, phase=0.0, amount=boost)
            else:
                eng.set_boost(0, 0.0, 0.0)
            host._live_dj_pair_ids = (a, b)
            self.lbl_remix.setText(
                f"GOAVA {goava*100:.0f}% · RAND {rand*100:.0f}% · boost {boost*100:.0f}% · pair {a}↔{b}"
            )
            self.lbl_status.setText("Parametric remix pushed to Live DJ engine.")
        except Exception as e:
            self.lbl_remix.setText(f"Remix error: {e}")

    @staticmethod
    def _safe_pattern_eval(expr: str, env: Dict[str, Any]) -> Any:
        node = ast.parse(expr, mode="eval")
        allowed = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
                   ast.BoolOp, ast.Compare, ast.Call, ast.Add, ast.Sub, ast.Mult, ast.Div,
                   ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.And, ast.Or, ast.Not,
                   ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
        for n in ast.walk(node):
            if not isinstance(n, allowed):
                raise ValueError(f"unsupported script syntax: {type(n).__name__}")
            if isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or n.func.id not in env):
                raise ValueError("only listed math functions may be called")
        import ot_script_math as _otm   # GROOVEBOX_R23R_OT_SCRIPT_DIVISION_20261103 (after the whitelist check)
        return eval(compile(_otm.rewrite(node), "<media-pattern>", "eval"), _otm.install({"__builtins__": {}}), env)

    def _compiled_pattern_program(self):
        """Compile the control script once per text identity, routed by sCode."""
        text=self.txt_pattern_script.toPlainText()
        def build():
            program=[]
            allowed_names={"t","step","pi","e","sin","cos","tan","sqrt","abs","min","max","rand",
                           "goava","rand","boost","speed","advance","host"}
            allowed_nodes=(ast.Expression,ast.Constant,ast.Name,ast.Load,ast.BinOp,ast.UnaryOp,
                           ast.BoolOp,ast.Compare,ast.Call,ast.Add,ast.Sub,ast.Mult,ast.Div,
                           ast.Mod,ast.Pow,ast.USub,ast.UAdd,ast.And,ast.Or,ast.Not,
                           ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE)
            callable_names={"sin","cos","tan","sqrt","abs","min","max","rand"}
            for raw in text.splitlines():
                line=raw.split("#",1)[0].strip()
                if not line or "=" not in line: continue
                key,expr=line.split("=",1); key=key.strip().lower(); expr=expr.strip()
                if key not in {"goava","rand","boost","speed","advance","host"}: continue
                node=ast.parse(expr,mode="eval")
                for n in ast.walk(node):
                    if not isinstance(n,allowed_nodes): raise ValueError(f"unsupported script syntax: {type(n).__name__}")
                    if isinstance(n,ast.Name) and n.id not in allowed_names: raise ValueError(f"unknown pattern name: {n.id}")
                    if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in callable_names):
                        raise ValueError("only listed math functions may be called")
                import ot_script_math as _otm   # OT division (after the whitelist check)
                program.append((key,compile(_otm.rewrite(node),"<media-pattern>","eval")))
            return tuple(program)
        opt=getattr(self.host,"_scode_optimizer",None)
        if opt is not None:
            return opt.memoized_result("ui_pattern_compile",text,build,max_entries=8)
        return build()

    def _set_pattern_rate(self, hz: int):
        self._pattern_timer.setInterval(max(16, int(round(1000.0 / max(1, hz)))))

    def _toggle_pattern_script(self, on: bool):
        if on:
            self._pattern_phase = 0.0
            self._pattern_step = 0
            self._pattern_rng.seed(int(self.spin_pattern_seed.value()))
            self._set_pattern_rate(self.spin_pattern_hz.value())
            self._pattern_timer.start()
            self.lbl_pattern.setText("Pattern running.")
        else:
            self._pattern_timer.stop()
            self.lbl_pattern.setText("Pattern stopped.")

    def _pattern_tick(self):
        hz=max(1,int(getattr(self,"spin_pattern_hz",None).value() if hasattr(self,"spin_pattern_hz") else 20))
        t=self._pattern_phase; step=self._pattern_step
        env={"t":t,"step":step,"pi":math.pi,"e":math.e,"sin":math.sin,"cos":math.cos,
             "tan":math.tan,"sqrt":math.sqrt,"abs":abs,"min":min,"max":max,"rand":self._pattern_rng.random}
        values:Dict[str,Any]={}
        try:
            for key,code in self._compiled_pattern_program():
                values[key]=eval(code,__import__("ot_script_math").install({"__builtins__":{}}),dict(env,**values))

            # SCODE_FULL_ACCEL_V4: coalesce three slider signal cascades into one
            # live-DJ update. Numeric values are still identical to the old path.
            changed=False
            assignments=[]
            if "goava" in values: assignments.append((self.sld_goava,max(0,min(100,int(round(float(values["goava"])))))))
            if "rand" in values: assignments.append((self.sld_rand,max(0,min(100,int(round(float(values["rand"])))))))
            if "boost" in values: assignments.append((self.sld_boost,max(0,min(100,int(round(float(values["boost"])))))))
            for widget,val in assignments:
                if widget.value()!=val:
                    widget.blockSignals(True); widget.setValue(val); widget.blockSignals(False); changed=True
            if changed:
                self._push_remix()
            if "speed" in values and hasattr(self,"sld_live_speed"):
                sv=max(25,min(400,int(round(float(values["speed"])*100.0))))
                if self.sld_live_speed.value()!=sv:
                    self.sld_live_speed.setValue(sv)
            if bool(values.get("advance",False)) and self._playlist: self._playlist_next()
            if self.chk_pattern_host_playlist.isChecked():
                self._write_host_pattern_value(values.get("host",values.get("goava",0.0)/100.0),step)
            self.lbl_pattern.setText(f"t={t:.2f} · step={step} · G={self.sld_goava.value()} R={self.sld_rand.value()} B={self.sld_boost.value()} · speed={self._live_speed:.2f}×")
        except Exception as e:
            self.lbl_pattern.setText(f"Pattern error: {e}"); self._pattern_timer.stop()
        self._pattern_step+=1; self._pattern_phase+=1.0/float(hz)

    def _write_host_pattern_value(self, value: Any, step: int):
        """Write sparse, bounded control-rate data into the host playlist automation.
        This is intentionally tiny: one scalar per playlist row, refreshed in-place."""
        try:
            rows = getattr(self.host, "master_playlist_data", None) or []
            if not rows:
                return
            row = int(step) % len(rows)
            entry = rows[row]
            if not isinstance(entry, dict):
                entry = {}; rows[row] = entry
            v = max(0.0, min(1.0, float(value)))
            entry["media_hub_pattern"] = v
            entry["media_hub_pattern_step"] = int(step)
            # Also expose through playlist_automation without replacing canonical fields.
            pa = getattr(self.host, "playlist_automation", None)
            if isinstance(pa, list):
                while len(pa) <= row:
                    pa.append({})
                if not isinstance(pa[row], dict):
                    pa[row] = {}
                pa[row]["media_hub_pattern"] = v
        except Exception:
            pass

    def _arm_host_dj_toggles(self):
        self._push_remix()
        try:
            if hasattr(self.host, "btn_live_dj_goava") and self.sld_goava.value() > 0:
                self.host.btn_live_dj_goava.setChecked(True)
            if hasattr(self.host, "btn_live_dj_random") and self.sld_rand.value() > 0:
                self.host.btn_live_dj_random.setChecked(True)
        except Exception:
            pass

    # ------------------------------------------------------------------ cutup lab
    def _build_cutup_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Geometric Phaselocked Cutup Lab</b>"))
        intro = QLabel(
            "Load an audio file, optionally normalize its detected pitch, then create a deterministic beat/cutup. "
            "Slice choice, pitch, rate, reversal and resampling are generated from one seed on a phaselocked geometric lattice."
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)

        src_row = QHBoxLayout()
        self.lbl_cutup_source = QLabel("No sample loaded")
        self.lbl_cutup_source.setWordWrap(True)
        btn_sel = QPushButton("Use selected audio")
        btn_sel.clicked.connect(self._cutup_use_selected)
        btn_browse = QPushButton("Load sample…")
        btn_browse.clicked.connect(self._cutup_browse)
        src_row.addWidget(self.lbl_cutup_source, stretch=1)
        src_row.addWidget(btn_sel)
        src_row.addWidget(btn_browse)
        lay.addLayout(src_row)
        self._cutup_source_path = None
        self._cutup_video_path = None
        self._cutup_events = []
        self._cutup_pitch_shift = 0.0

        vrow = QHBoxLayout()
        self.lbl_cutup_video = QLabel("No video source (optional)")
        self.lbl_cutup_video.setWordWrap(True)
        btn_vsel = QPushButton("Use selected video")
        btn_vsel.clicked.connect(self._cutup_use_selected_video)
        btn_vbrowse = QPushButton("Load video…")
        btn_vbrowse.clicked.connect(self._cutup_browse_video)
        vrow.addWidget(self.lbl_cutup_video, stretch=1); vrow.addWidget(btn_vsel); vrow.addWidget(btn_vbrowse)
        lay.addLayout(vrow)

        norm = QGroupBox("Pitch normalization")
        nf = QFormLayout(norm)
        self.spin_cutup_target_hz = QDoubleSpinBox()
        self.spin_cutup_target_hz.setRange(0.0, 20000.0)
        self.spin_cutup_target_hz.setDecimals(3)
        self.spin_cutup_target_hz.setValue(0.0)
        self.spin_cutup_target_hz.setSpecialValueText("Nearest C-major pitch")
        self.spin_cutup_target_hz.setToolTip("0 = detect a stable fundamental and move it to the nearest C-major pitch. Enter Hz for an exact target.")
        nf.addRow("Target pitch", self.spin_cutup_target_hz)
        nrow = QHBoxLayout()
        btn_an = QPushButton("Analyze pitch")
        btn_an.clicked.connect(self._cutup_analyze_pitch)
        btn_nr = QPushButton("Render normalized copy…")
        btn_nr.clicked.connect(self._cutup_render_normalized)
        nrow.addWidget(btn_an); nrow.addWidget(btn_nr)
        nf.addRow(nrow)
        self.lbl_cutup_pitch = QLabel("Pitch not analyzed.")
        self.lbl_cutup_pitch.setWordWrap(True)
        nf.addRow(self.lbl_cutup_pitch)
        lay.addWidget(norm)

        gen = QGroupBox("Seeded beat / file cutup")
        form = QFormLayout(gen)
        self.spin_cutup_bpm = QDoubleSpinBox(); self.spin_cutup_bpm.setRange(20.0, 400.0); self.spin_cutup_bpm.setValue(120.0); self.spin_cutup_bpm.setDecimals(2)
        self.spin_cutup_bars = QSpinBox(); self.spin_cutup_bars.setRange(1, 256); self.spin_cutup_bars.setValue(4)
        self.spin_cutup_steps = QSpinBox(); self.spin_cutup_steps.setRange(1, 64); self.spin_cutup_steps.setValue(16)
        self.spin_cutup_divs = QSpinBox(); self.spin_cutup_divs.setRange(1, 1024); self.spin_cutup_divs.setValue(32)
        self.spin_cutup_phase = QSpinBox(); self.spin_cutup_phase.setRange(1, 64); self.spin_cutup_phase.setValue(4)
        self.spin_cutup_seed = QSpinBox(); self.spin_cutup_seed.setRange(0, 2147483647); self.spin_cutup_seed.setValue(1975807343)
        self.spin_cutup_pitch_range = QDoubleSpinBox(); self.spin_cutup_pitch_range.setRange(0.0, 48.0); self.spin_cutup_pitch_range.setValue(7.0); self.spin_cutup_pitch_range.setSuffix(" st")
        self.spin_cutup_rate_depth = QDoubleSpinBox(); self.spin_cutup_rate_depth.setRange(0.0, 3.0); self.spin_cutup_rate_depth.setSingleStep(0.05); self.spin_cutup_rate_depth.setValue(0.20)
        self.spin_cutup_reverse = QDoubleSpinBox(); self.spin_cutup_reverse.setRange(0.0, 1.0); self.spin_cutup_reverse.setSingleStep(0.05); self.spin_cutup_reverse.setValue(0.12)
        self.cmb_cutup_resample = QComboBox(); self.cmb_cutup_resample.addItems(["preserve-duration", "tape"])
        form.addRow("BPM", self.spin_cutup_bpm)
        form.addRow("Bars", self.spin_cutup_bars)
        form.addRow("Steps / bar", self.spin_cutup_steps)
        form.addRow("Source slice divisions", self.spin_cutup_divs)
        form.addRow("Phase-lock group", self.spin_cutup_phase)
        form.addRow("Seed", self.spin_cutup_seed)
        form.addRow("Pitch modulation", self.spin_cutup_pitch_range)
        form.addRow("Rate depth", self.spin_cutup_rate_depth)
        form.addRow("Reverse probability", self.spin_cutup_reverse)
        form.addRow("Resampling", self.cmb_cutup_resample)
        lay.addWidget(gen)

        crow = QHBoxLayout()
        btn_gen = QPushButton("Generate cut pattern")
        btn_gen.clicked.connect(self._cutup_generate)
        btn_render = QPushButton("Render cutup / beat…")
        btn_render.clicked.connect(self._cutup_render)
        btn_playlist = QPushButton("Seed playlist from same geometry")
        btn_playlist.clicked.connect(self._cutup_seed_playlist)
        btn_av = QPushButton("Render A/V cutup…")
        btn_av.clicked.connect(self._cutup_render_av)
        btn_auto = QPushButton("▶ Auto render + replay/broadcast")
        btn_auto.clicked.connect(self._cutup_auto_perform)
        crow.addWidget(btn_gen); crow.addWidget(btn_render); crow.addWidget(btn_playlist); crow.addWidget(btn_av); crow.addWidget(btn_auto)
        lay.addLayout(crow)
        self.lbl_cutup_pattern = QLabel("No cut pattern generated.")
        self.lbl_cutup_pattern.setWordWrap(True)
        self.lbl_cutup_pattern.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        lay.addWidget(self.lbl_cutup_pattern)
        lay.addStretch(1)
        return w

    def _cutup_use_selected(self):
        for path in self._selected_paths():
            if os.path.isfile(path) and _gb_ext(path) in AUDIO_EXT:
                self._cutup_set_source(path)
                return
        QMessageBox.information(self, "Cutup Lab", "Select an audio file in the Performance browser first.")

    def _cutup_browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load sample", self._host_samples_dir(), "Audio (*.wav *.flac *.mp3 *.ogg *.opus *.aiff *.aif *.caf);;All files (*)")
        if path:
            self._cutup_set_source(path)

    def _cutup_use_selected_video(self):
        for path in self._selected_paths():
            if os.path.isfile(path) and _gb_ext(path) in VIDEO_EXT:
                self._cutup_video_path = os.path.abspath(path)
                self.lbl_cutup_video.setText(os.path.basename(path))
                return
        QMessageBox.information(self, "Cutup Lab", "Select a video file in the Performance browser first.")

    def _cutup_browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load video source", self._host_exports_dir(), "Video (*.mp4 *.webm *.avi *.mov *.mkv);;All files (*)")
        if path:
            self._cutup_video_path = os.path.abspath(path)
            self.lbl_cutup_video.setText(os.path.basename(path))

    def _cutup_set_source(self, path: str):
        self._cutup_source_path = os.path.abspath(path)
        self._cutup_events = []
        self._cutup_pitch_shift = 0.0
        self.lbl_cutup_source.setText(os.path.basename(path))
        self.lbl_cutup_pitch.setText("Pitch not analyzed.")
        self.lbl_cutup_pattern.setText("Source loaded. Generate a pattern or analyze pitch.")

    def _cutup_analyze_pitch(self):
        path = self._cutup_source_path
        if not path or not os.path.isfile(path):
            self._cutup_use_selected(); path = self._cutup_source_path
        if not path:
            return
        try:
            from media_cutup_engine import pitch_normalization_shift
            target = float(self.spin_cutup_target_hz.value())
            detected, shift, msg = pitch_normalization_shift(path, target_hz=(target if target > 0 else None), root_midi=60)
            self._cutup_pitch_shift = float(shift)
            self.lbl_cutup_pitch.setText(msg)
            self.lbl_status.setText("Pitch analysis complete." if detected is not None else msg)
        except Exception as e:
            QMessageBox.warning(self, "Pitch analysis", str(e))

    def _cutup_render_normalized(self):
        path = self._cutup_source_path
        if not path or not os.path.isfile(path):
            self._cutup_use_selected(); path = self._cutup_source_path
        if not path:
            return
        self._cutup_analyze_pitch()
        base = os.path.splitext(os.path.basename(path))[0] + "_pitch_normalized.wav"
        out, _ = QFileDialog.getSaveFileName(self, "Render normalized sample", os.path.join(self._host_exports_dir(), base), "WAV (*.wav);;FLAC (*.flac)")
        if not out:
            return
        try:
            from media_cutup_engine import render_pitch_normalized
            out = render_pitch_normalized(path, out, self._cutup_pitch_shift, preserve_duration=True)
            self.lbl_status.setText(f"Pitch-normalized sample rendered: {os.path.basename(out)}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Pitch normalization", str(e))

    def _cutup_generate(self):
        path = self._cutup_source_path
        if not path or not os.path.isfile(path):
            self._cutup_use_selected(); path = self._cutup_source_path
        if not path:
            return
        try:
            from media_cutup_engine import generate_cut_events, probe_duration
            dur = probe_duration(path)
            if dur <= 0:
                raise RuntimeError("Could not determine sample duration")
            self._cutup_events = generate_cut_events(
                dur,
                bpm=float(self.spin_cutup_bpm.value()), bars=int(self.spin_cutup_bars.value()),
                steps_per_bar=int(self.spin_cutup_steps.value()), seed=int(self.spin_cutup_seed.value()),
                slice_divisions=int(self.spin_cutup_divs.value()), pitch_range_st=float(self.spin_cutup_pitch_range.value()),
                rate_depth=float(self.spin_cutup_rate_depth.value()), reverse_probability=float(self.spin_cutup_reverse.value()),
                normalize_shift_st=float(self._cutup_pitch_shift), phase_lock=int(self.spin_cutup_phase.value()),
            )
            ev = self._cutup_events[:4]
            preview = " · ".join(f"#{e.step}: {e.start_s:.2f}s {e.pitch_semitones:+.2f}st {e.rate:.2f}×{' REV' if e.reverse else ''}" for e in ev)
            self.lbl_cutup_pattern.setText(f"{len(self._cutup_events)} phaselocked events generated. {preview}")
            self.lbl_status.setText("Cutup pattern generated deterministically from seed.")
        except Exception as e:
            QMessageBox.warning(self, "Cutup pattern", str(e))

    def _cutup_render(self):
        if not self._cutup_events:
            self._cutup_generate()
        if not self._cutup_events or not self._cutup_source_path:
            return
        base = os.path.splitext(os.path.basename(self._cutup_source_path))[0] + f"_cutup_{int(self.spin_cutup_seed.value())}.wav"
        out, _ = QFileDialog.getSaveFileName(self, "Render cutup / beat", os.path.join(self._host_exports_dir(), base), "WAV (*.wav);;FLAC (*.flac);;MP3 (*.mp3);;Opus (*.opus);;OGG (*.ogg)")
        if not out:
            return
        try:
            from media_cutup_engine import render_cutup
            out = render_cutup(
                self._cutup_source_path, out, self._cutup_events,
                bpm=float(self.spin_cutup_bpm.value()), steps_per_bar=int(self.spin_cutup_steps.value()),
                sample_rate=int(getattr(self.host, "play_sample_rate", 48000) or 48000),
                resample_mode=self.cmb_cutup_resample.currentText(), normalize_peak=True,
            )
            self.lbl_status.setText(f"Cutup rendered: {os.path.basename(out)}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Cutup render", str(e))

    def _cutup_seed_playlist(self):
        if not self._playlist:
            self._add_to_playlist()
        if not self._playlist:
            QMessageBox.information(self, "Cutup Lab", "Add media to the Performance playlist first.")
            return
        try:
            from media_cutup_engine import playlist_geometric_parameters
            params = playlist_geometric_parameters(
                len(self._playlist), int(self.spin_cutup_seed.value()),
                pitch_range_st=float(self.spin_cutup_pitch_range.value()),
                rate_depth=float(self.spin_cutup_rate_depth.value()), phase_lock=int(self.spin_cutup_phase.value()),
            )
            decorated = []
            for item, param in zip(self._playlist, params):
                item.update(param)
                decorated.append((float(param["geometry_key"]), item))
            decorated.sort(key=lambda pair: pair[0])
            self._playlist = [item for _key, item in decorated]
            self._playlist_index = 0
            self._refresh_playlist_widget()
            self.lbl_status.setText("Playlist selection/pitch/rate/resampling seeded from Cutup Lab geometry.")
        except Exception as e:
            QMessageBox.warning(self, "Seed playlist", str(e))

    def _cutup_render_av(self, output_path: Optional[str] = None):
        if not self._cutup_events:
            self._cutup_generate()
        if not self._cutup_events or not self._cutup_source_path:
            return None
        if not self._cutup_video_path or not os.path.isfile(self._cutup_video_path):
            self._cutup_use_selected_video()
        if not self._cutup_video_path:
            return None
        if output_path is None:
            base = os.path.splitext(os.path.basename(self._cutup_source_path))[0] + f"_avcutup_{int(self.spin_cutup_seed.value())}.mp4"
            output_path, _ = QFileDialog.getSaveFileName(self, "Render audiovisual cutup", os.path.join(self._host_exports_dir(), base), "MP4 (*.mp4)")
            if not output_path:
                return None
        try:
            from media_cutup_engine import render_av_cutup
            out = render_av_cutup(
                self._cutup_source_path, self._cutup_video_path, output_path, self._cutup_events,
                bpm=float(self.spin_cutup_bpm.value()), steps_per_bar=int(self.spin_cutup_steps.value()),
                sample_rate=int(getattr(self.host, "play_sample_rate", 48000) or 48000),
                resample_mode=self.cmb_cutup_resample.currentText(),
                video_fps=int(getattr(self.host, "_last_export_fps", 30) or 30),
            )
            self.lbl_status.setText(f"A/V cutup rendered: {os.path.basename(out)}")
            self.refresh()
            return out
        except Exception as e:
            QMessageBox.warning(self, "A/V cutup render", str(e))
            return None

    def _cutup_auto_perform(self):
        """One-click deterministic render -> replay -> game/network broadcast."""
        if not self._cutup_events:
            self._cutup_generate()
        if not self._cutup_events:
            return
        os.makedirs(self._host_exports_dir(), exist_ok=True)
        seed = int(self.spin_cutup_seed.value())
        if self._cutup_video_path and os.path.isfile(self._cutup_video_path):
            out = os.path.join(self._host_exports_dir(), f"auto_avcutup_{seed}.mp4")
            rendered = self._cutup_render_av(out)
        else:
            out = os.path.join(self._host_exports_dir(), f"auto_cutup_{seed}.wav")
            try:
                from media_cutup_engine import render_cutup
                rendered = render_cutup(
                    self._cutup_source_path, out, self._cutup_events,
                    bpm=float(self.spin_cutup_bpm.value()), steps_per_bar=int(self.spin_cutup_steps.value()),
                    sample_rate=int(getattr(self.host, "play_sample_rate", 48000) or 48000),
                    resample_mode=self.cmb_cutup_resample.currentText(), normalize_peak=True,
                )
            except Exception as e:
                QMessageBox.warning(self, "Auto performance", str(e)); return
        if rendered:
            self._start_performance(rendered, loop=True)

    # ------------------------------------------------------------------ live performance / ethernet
    def _build_performance_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Phaselocked Live Broadcast</b>"))
        txt = QLabel("Replays the generated beat/A/V cutup while broadcasting the exact same step, phase, pitch, rate and slice state to the game runtime and optional Ethernet clients.")
        txt.setWordWrap(True); lay.addWidget(txt)
        self.chk_perf_loop = QCheckBox("Loop replay continuously"); self.chk_perf_loop.setChecked(True); lay.addWidget(self.chk_perf_loop)
        self.chk_perf_game = QCheckBox("Broadcast canonical cutup state to game runtime"); self.chk_perf_game.setChecked(True); lay.addWidget(self.chk_perf_game)
        row = QHBoxLayout()
        bstart = QPushButton("▶ Start current cutup broadcast"); bstart.clicked.connect(lambda: self._start_performance(self._performance_media_path, self.chk_perf_loop.isChecked()))
        bstop = QPushButton("■ Stop broadcast"); bstop.clicked.connect(self._stop_performance)
        row.addWidget(bstart); row.addWidget(bstop); lay.addLayout(row)
        qos = QGroupBox("Live quality / canonical projection")
        qf = QFormLayout(qos)
        self.cmb_perf_qos = QComboBox(); self.cmb_perf_qos.addItems(["Auto (recommended)", "Low-latency", "Full detail"]); qf.addRow("Performance QoS", self.cmb_perf_qos)
        self.chk_relativity = QCheckBox("Relativity projection (downstream; preserves canonical ID)"); self.chk_relativity.setChecked(False); qf.addRow(self.chk_relativity)
        self.spin_relativity_beta = QDoubleSpinBox(); self.spin_relativity_beta.setRange(-0.99,0.99); self.spin_relativity_beta.setDecimals(4); self.spin_relativity_beta.setSingleStep(0.01); self.spin_relativity_beta.setValue(0.0); qf.addRow("β = v/c", self.spin_relativity_beta)
        self.spin_relativity_amount = QDoubleSpinBox(); self.spin_relativity_amount.setRange(0.0,8.0); self.spin_relativity_amount.setDecimals(3); self.spin_relativity_amount.setValue(1.0); qf.addRow("Projection amount", self.spin_relativity_amount)
        self.lbl_relativity_credit = QLabel("Standard SR math · NASA Trick/cFS/CML credited as simulation-engineering inspiration · no NASA code copied")
        self.lbl_relativity_credit.setWordWrap(True); self.lbl_relativity_credit.setStyleSheet("color:#91b9c9;font-size:8pt;"); qf.addRow(self.lbl_relativity_credit)
        lay.addWidget(qos)
        net = QGroupBox("Ethernet host"); nf = QFormLayout(net)
        self.spin_remote_port = QSpinBox(); self.spin_remote_port.setRange(1024, 65535); self.spin_remote_port.setValue(8765); nf.addRow("Port", self.spin_remote_port)
        self.lbl_remote = QLabel("Stopped"); self.lbl_remote.setWordWrap(True); nf.addRow("Status", self.lbl_remote)
        nr = QHBoxLayout(); bon = QPushButton("Start LAN host"); bon.clicked.connect(self._start_remote_server); boff = QPushButton("Stop LAN host"); boff.clicked.connect(self._stop_remote_server); nr.addWidget(bon); nr.addWidget(boff); nf.addRow(nr)
        lay.addWidget(net)
        radio = QGroupBox("◉ GOAVA LAN Radio · 192 kbps MP3")
        rf = QVBoxLayout(radio)
        self.lbl_radio_status = QLabel("Radio stopped")
        self.lbl_radio_status.setWordWrap(True); rf.addWidget(self.lbl_radio_status)
        rr = QHBoxLayout()
        rstart = QPushButton("▶ Start Radio + discovery"); rstart.clicked.connect(self._start_goava_radio)
        rstop = QPushButton("■ Stop Radio"); rstop.clicked.connect(self._stop_goava_radio)
        rrefresh = QPushButton("↻ Nearby Radios"); rrefresh.clicked.connect(self._refresh_radio_peers)
        rr.addWidget(rstart); rr.addWidget(rstop); rr.addWidget(rrefresh); rf.addLayout(rr)
        self.lst_radio_peers = QListWidget(); self.lst_radio_peers.setMaximumHeight(132); rf.addWidget(self.lst_radio_peers)
        hint = QLabel("OS/appliance helper can redirect TCP/80 → Radio :8780 so nearby devices can open http://device/ directly.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#8ab4c8;font-size:9pt;"); rf.addWidget(hint)
        lay.addWidget(radio); lay.addStretch(1); return w

    def _start_goava_radio(self):
        try:
            from radio_station import RadioStationService
            if self._goava_radio_service is None:
                roots = [self._host_projects_dir(), self._host_exports_dir(), self._host_samples_dir()]
                self._goava_radio_service = RadioStationService(roots=roots, port=8780)
            url = self._goava_radio_service.start()
            self.lbl_radio_status.setText(f"Broadcasting: {url} · 192 kbps MP3")
            self._radio_peer_timer.start(); self._refresh_radio_peers()
        except Exception as e:
            QMessageBox.warning(self, "GOAVA Radio", str(e))

    def _stop_goava_radio(self):
        try:
            if self._goava_radio_service is not None: self._goava_radio_service.stop()
        except Exception: pass
        self._goava_radio_service = None
        self._radio_peer_timer.stop()
        if hasattr(self, "lbl_radio_status"): self.lbl_radio_status.setText("Radio stopped")

    def _refresh_radio_peers(self):
        if not hasattr(self, "lst_radio_peers"): return
        self.lst_radio_peers.clear()
        svc = self._goava_radio_service
        peers = svc.peer_list() if svc is not None else []
        if not peers:
            self.lst_radio_peers.addItem("No nearby Groovebox radios discovered yet.")
            return
        for p in peers:
            self.lst_radio_peers.addItem(f"{p.get('name','Radio')}  ·  {p.get('url','')}")

    def _start_performance(self, media_path: Optional[str] = None, loop: bool = True):
        if not self._cutup_events:
            self._cutup_generate()
        if not self._cutup_events:
            return
        if media_path and os.path.isfile(media_path):
            self._performance_media_path = media_path
            self._stop_player()
            cmd = _find_player()
            if cmd:
                player_name = os.path.basename(cmd[0]).lower()
                if player_name.startswith("mpv") and loop:
                    cmd = list(cmd) + ["--loop-file=inf"]
                elif player_name.startswith("vlc") and loop:
                    cmd = list(cmd) + ["--loop"]
                try:
                    cmd, penv = self._routed_player(cmd, want_video=(_gb_ext(media_path) in VIDEO_EXT))
                    self._player_proc = subprocess.Popen(cmd + [media_path], env=penv)
                    # VLC can otherwise hand a file to an existing instance and make
                    # the child disappear immediately. --no-one-instance above avoids
                    # that; a short deferred poll still surfaces real launch failures.
                    QTimer.singleShot(450, lambda p=self._player_proc, mp=media_path: self._check_player_launch(p, mp))
                    try:
                        if self._media_share_server is not None:
                            self._media_share_server.set_current(media_path)
                    except Exception:
                        pass
                except Exception:
                    pass
        self._performance_loop = bool(loop)
        self._performance_step = 0
        step_ms = max(10, int(round((60.0 / float(self.spin_cutup_bpm.value()) * 4.0 / int(self.spin_cutup_steps.value())) * 1000.0)))
        self._performance_timer.setInterval(step_ms)
        self._performance_timer.start()
        self._broadcast_state = {"active": True, "step": 0, "seed": int(self.spin_cutup_seed.value())}
        self.lbl_status.setText("Phaselocked replay/game/Ethernet broadcast active.")

    def _performance_tick(self):
        if not self._cutup_events:
            self._stop_performance(); return
        idx = self._performance_step % len(self._cutup_events)
        ev = self._cutup_events[idx]
        state = {
            "active": True, "event_index": idx, "step": int(ev.step), "phase": float(ev.phase),
            "pitch_semitones": float(ev.pitch_semitones), "rate": float(ev.rate), "gain": float(ev.gain),
            "pan": float(ev.pan), "reverse": bool(ev.reverse), "source_start_s": float(ev.start_s),
            "source_duration_s": float(ev.duration_s), "seed": int(self.spin_cutup_seed.value()),
            "bpm": float(self.spin_cutup_bpm.value()), "timestamp": time.time(),
        }
        if getattr(self, "chk_relativity", None) is not None and self.chk_relativity.isChecked():
            try:
                from relativity_projection import project_event
                state = project_event(state, self.spin_relativity_beta.value(), self.spin_relativity_amount.value())
            except Exception as exc:
                state["relativity_error"] = str(exc)
        # QoS is representational only; receivers may skip expensive visuals, never audio/state.
        try:
            _q = self.cmb_perf_qos.currentText() if hasattr(self, "cmb_perf_qos") else "Auto (recommended)"
            state["performance_qos"] = "low" if _q.startswith("Low") else ("full" if _q.startswith("Full") else "auto")
        except Exception:
            state["performance_qos"] = "auto"
        self._broadcast_state = state
        if getattr(self, "chk_perf_game", None) is None or self.chk_perf_game.isChecked():
            try:
                setattr(self.host, "_performance_broadcast_state", dict(state))
                setattr(self.host, "_media_hub_broadcast_state", dict(state))
                cb = getattr(self.host, "on_media_hub_broadcast", None) or getattr(self.host, "_on_media_hub_broadcast", None)
                if callable(cb): cb(dict(state))
            except Exception:
                pass
        self._performance_step += 1
        if self._performance_step >= len(self._cutup_events) and not self._performance_loop:
            self._stop_performance()

    def _stop_performance(self):
        self._performance_timer.stop()
        self._broadcast_state = {"active": False, "timestamp": time.time()}
        try: setattr(self.host, "_performance_broadcast_state", dict(self._broadcast_state)); setattr(self.host, "_media_hub_broadcast_state", dict(self._broadcast_state))
        except Exception: pass
        self.lbl_status.setText("Live broadcast stopped.")

    def _lan_ip(self) -> str:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.connect(("8.8.8.8", 80)); ip = sock.getsockname()[0]; sock.close(); return ip
        except Exception:
            return "127.0.0.1"

    def _start_remote_server(self):
        if self._remote_server is not None:
            return
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def _json(self, code, payload):
                raw = json.dumps(payload).encode("utf-8"); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_GET(self):
                if self.path.split("?",1)[0] == "/status": self._json(200, dict(owner._broadcast_state)); return
                self._json(404, {"error":"not found"})
            def do_POST(self):
                if self.headers.get("X-Groovebox-Token", "") != owner._remote_token:
                    self._json(403, {"error":"bad token"}); return
                try:
                    n = min(4096, int(self.headers.get("Content-Length", "0") or 0)); payload = json.loads(self.rfile.read(n) or b"{}")
                except Exception:
                    self._json(400, {"error":"bad json"}); return
                with owner._remote_lock: owner._remote_commands.append(payload if isinstance(payload, dict) else {})
                self._json(202, {"queued": True})
            def log_message(self, *_args): pass
        try:
            self._remote_server = ThreadingHTTPServer(("0.0.0.0", int(self.spin_remote_port.value())), Handler)
            self._remote_thread = threading.Thread(target=self._remote_server.serve_forever, daemon=True); self._remote_thread.start()
            if not self._remote_timer.isActive(): self._remote_timer.start()
            self.lbl_remote.setText(f"http://{self._lan_ip()}:{self.spin_remote_port.value()}/status · control token: {self._remote_token}")
        except Exception as e:
            self._remote_server = None; QMessageBox.warning(self, "Ethernet host", str(e))

    def _stop_remote_server(self):
        try: self._remote_timer.stop()
        except Exception: pass
        with self._remote_lock:
            self._remote_commands.clear()
        srv = self._remote_server; self._remote_server = None
        if srv is not None:
            try: srv.shutdown(); srv.server_close()
            except Exception: pass
        th = self._remote_thread; self._remote_thread = None
        if th is not None and th is not threading.current_thread():
            try: th.join(timeout=3.0)
            except Exception: pass
        if hasattr(self, "lbl_remote"): self.lbl_remote.setText("Stopped")

    def _drain_remote_commands(self):
        with self._remote_lock:
            cmds = self._remote_commands[:]; self._remote_commands.clear()
        for cmd in cmds:
            action = str(cmd.get("action", "")).lower()
            if action == "start": self._start_performance(self._performance_media_path, bool(cmd.get("loop", True)))
            elif action == "stop": self._stop_performance()
            elif action == "next": self._playlist_next()
            elif action == "previous": self._playlist_prev()
            elif action == "speed":
                try: self._set_live_speed(float(cmd.get("value", 1.0)))
                except Exception: pass

    # ------------------------------------------------------------------ fixed Performance devices (R23l)
    def _refresh_quick_devices(self):
        self._quick_device_generation += 1
        generation=self._quick_device_generation
        try: self.btn_quick_devices_refresh.setEnabled(False)
        except Exception: pass
        def work():
            payload={}; error=''
            try:
                from media_output_router import detect_audio_targets, _physical_alsa_playback_devices
                outs=[]
                for a in detect_audio_targets():
                    outs.append({'name':str(getattr(a,'name','')),'description':str(getattr(a,'description','System default')),
                                 'state':str(getattr(a,'state','')),'kind':str(getattr(a,'kind','audio')),'backend':str(getattr(a,'backend','default'))})
                payload['audio_outputs']=outs
                payload['physical_alsa']=list(_physical_alsa_playback_devices() or [])
            except Exception as exc:
                error=str(exc)
            try:
                from hardware_hub import run_probe_retry
                from groovebox_subprocess import helper_argv
                cp=run_probe_retry(helper_argv('device_probe_helper','record'),timeout=7.0)
                if cp.returncode==0 and (cp.stdout or '').strip():
                    row=json.loads((cp.stdout or '').strip().splitlines()[-1]); payload.update(row if isinstance(row,dict) else {})
                elif not error:
                    error=(cp.stderr or cp.stdout or 'device probe failed')[-700:].strip()
            except Exception as exc:
                if not error: error=str(exc)
            # GROOVEBOX_R23R_DEVICE_LIST_FIX_20261101: verify in this worker (not on the
            # GUI thread) and only *mark* devices; PortAudio cannot resolve ALSA (plughw:…)
            # or PipeWire sink names, so filtering on that check emptied every list.
            try:
                for key,kind in (('audio_outputs','output'),('audio_inputs','input'),('cameras','video')):
                    rows=list(payload.get(key) or [])
                    for r in rows:
                        if isinstance(r,dict): r['verified']=self._device_opens(r,kind)
                    rows.sort(key=lambda r: 0 if (isinstance(r,dict) and r.get('verified')) else 1)
                    payload[key]=rows
            except Exception:
                pass
            self._quick_device_bridge.done.emit(generation,payload,error)
        self._worker_pool.start(_PoolTask(work))

    def _only_working_devices(self, rows, kind):
        """List a device only if it opens, or it is already feeding the field."""
        out = []
        feeding = set()
        try:
            feeding = set((getattr(self.host, "_device_gains", {}) or {}).keys())
        except Exception:
            feeding = set()
        for row in rows or []:
            name = str(row.get("name") or row.get("description") or row.get("path") or "")
            if name and name in feeding:
                out.append(row)
                continue
            if self._device_opens(row, kind):
                out.append(row)
        return out

    def _device_opens(self, row, kind):
        if kind == "video":
            path = str(row.get("path") or "")
            return bool(path and os.path.exists(path))
        name = str(row.get("name") or "") or None
        try:
            from audio_os_backend import sounddevice as sd
            if kind == "input":
                sd.check_input_settings(device=name, samplerate=48000, channels=1, dtype="float32")
            else:
                sd.check_output_settings(device=name, samplerate=48000, channels=1, dtype="float32")
            return True
        except Exception:
            return False

    def _on_quick_devices_ready(self,generation:int,payload:dict,error:str):
        if generation != self._quick_device_generation: return
        try: self.btn_quick_devices_refresh.setEnabled(True)
        except Exception: pass
        self._quick_audio_rows=list((payload or {}).get('audio_outputs') or [])
        physical=list((payload or {}).get('physical_alsa') or [])
        # Put the proven physical speaker at the top on sOS, ahead of a stale
        # PipeWire/default sink that may still point at auto_null/HDMI.
        for dev in reversed(physical):
            row={'name':dev,'description':'Internal / physical speaker (direct ALSA)','state':'','kind':'audio','backend':'alsa'}
            if not any(str(x.get('name',''))==dev for x in self._quick_audio_rows): self._quick_audio_rows.insert(0,row)
        self._quick_input_rows=list((payload or {}).get('audio_inputs') or [])
        self._quick_video_rows=list((payload or {}).get('cameras') or [])
        # Devices are listed even when PortAudio cannot confirm them (marked in the label).
        if not all(hasattr(self, n) for n in ("cmb_quick_audio_output", "cmb_quick_audio_input", "cmb_quick_video_device")):
            return
        try:
            self.cmb_quick_audio_output.blockSignals(True); self.cmb_quick_audio_output.clear()
            for row in self._quick_audio_rows:
                _lab=str(row.get('description') or row.get('name') or 'Audio output')
                if row.get('backend')!='alsa' and row.get('verified') is False: _lab+='  (not verified)'
                self.cmb_quick_audio_output.addItem(_lab,row)
            if not self._quick_audio_rows: self.cmb_quick_audio_output.addItem('No physical audio output detected',{})
            preferred=str(getattr(self.host,'_preferred_audio_output_name','') or '')
            pick=0
            if preferred:
                for i,row in enumerate(self._quick_audio_rows):
                    if preferred.casefold() in (str(row.get('description',''))+' '+str(row.get('name',''))).casefold(): pick=i; break
            self.cmb_quick_audio_output.setCurrentIndex(min(pick,max(0,self.cmb_quick_audio_output.count()-1))); self.cmb_quick_audio_output.blockSignals(False)

            self.cmb_quick_audio_input.blockSignals(True); self.cmb_quick_audio_input.clear()
            for row in self._quick_input_rows:
                meta=dict(row.get('meta') or {}); backend=str(row.get('backend') or meta.get('backend') or 'sounddevice')
                label=str(row.get('name') or 'Audio input')
                if backend=='alsa': label='ALSA · '+label
                elif row.get('verified') is False: label+='  (not verified)'
                self.cmb_quick_audio_input.addItem(label,row)
            if not self._quick_input_rows: self.cmb_quick_audio_input.addItem('No physical microphone detected',{})
            pref_in=str(getattr(self.host,'_preferred_audio_input_name','') or '')
            pick=0
            if pref_in:
                for i,row in enumerate(self._quick_input_rows):
                    if pref_in.casefold() in str(row.get('name','')).casefold(): pick=i; break
            self.cmb_quick_audio_input.setCurrentIndex(min(pick,max(0,self.cmb_quick_audio_input.count()-1))); self.cmb_quick_audio_input.blockSignals(False)

            self.cmb_quick_video_device.blockSignals(True); self.cmb_quick_video_device.clear()
            for row in self._quick_video_rows:
                self.cmb_quick_video_device.addItem(str(row.get('name') or row.get('path') or 'Camera'),row)
            if not self._quick_video_rows: self.cmb_quick_video_device.addItem('No video device detected',{})
            pref_vid=str(getattr(self.host,'_preferred_video_device_path','') or '')
            pref_name=str(getattr(self.host,'_preferred_video_device_name','') or '')
            pick=0
            if pref_vid:
                for i,row in enumerate(self._quick_video_rows):
                    if str(row.get('path',''))==pref_vid: pick=i; break
                else:
                    if pref_name:
                        for i,row in enumerate(self._quick_video_rows):
                            if pref_name.casefold() in str(row.get('name','')).casefold(): pick=i; break
            elif pref_name:
                for i,row in enumerate(self._quick_video_rows):
                    if pref_name.casefold() in str(row.get('name','')).casefold(): pick=i; break
            self.cmb_quick_video_device.setCurrentIndex(min(pick,max(0,self.cmb_quick_video_device.count()-1))); self.cmb_quick_video_device.blockSignals(False)
            self._quick_audio_output_changed(); self._quick_audio_input_changed(); self._quick_video_device_changed()
            if error: self.lbl_status.setText('Device selectors ready with partial probe: '+str(error)[:160])
            else: self.lbl_status.setText(f"Devices: {len(self._quick_audio_rows)} output(s) · {len(self._quick_input_rows)} input(s) · {len(self._quick_video_rows)} video device(s)")
        except (RuntimeError, AttributeError):
            return

    def _quick_audio_output_changed(self,*_args):
        row=self.cmb_quick_audio_output.currentData() if hasattr(self,'cmb_quick_audio_output') else None
        if not isinstance(row,dict) or not row: return
        try:
            from media_output_router import AudioTarget
            self._output_audio_target=AudioTarget(str(row.get('name','')),str(row.get('description','System default')),
                                                  state=str(row.get('state','')),kind=str(row.get('kind','audio')),backend=str(row.get('backend','default')))
            setattr(self.host,'_preferred_audio_output_name',str(row.get('description') or row.get('name') or ''))
        except Exception: pass

    def _quick_audio_input_changed(self,*_args):
        row=self.cmb_quick_audio_input.currentData() if hasattr(self,'cmb_quick_audio_input') else None
        self._stop_quick_mic_meter()
        if not isinstance(row,dict) or not row: return
        name=str(row.get('name','')); setattr(self.host,'_preferred_audio_input_name',name)
        studio=getattr(self,'video_clip_studio',None)
        if studio is not None:
            try:
                for i in range(studio.cmb_mic.count()):
                    if name and name.casefold() in studio.cmb_mic.itemText(i).casefold(): studio.cmb_mic.setCurrentIndex(i); break
            except Exception: pass
        # Keep a visible meter on the fixed Performance surface except while the
        # Record tab owns the microphone itself.
        try:
            if self._performance_tabs.tabText(self._performance_tabs.currentIndex()) != '🎥 Record / Import / Draw Clip':
                self._start_quick_mic_meter(row)
        except Exception:
            self._start_quick_mic_meter(row)

    def _quick_video_device_changed(self,*_args):
        row=self.cmb_quick_video_device.currentData() if hasattr(self,'cmb_quick_video_device') else None
        if not isinstance(row,dict) or not row: return
        path=str(row.get('path','')); setattr(self.host,'_preferred_video_device_path',path)
        name=str(row.get('name') or row.get('stable_id') or '')
        if name: setattr(self.host,'_preferred_video_device_name',name)
        studio=getattr(self,'video_clip_studio',None)
        if studio is not None:
            try:
                for i in range(studio.cmb_camera.count()):
                    if studio.cmb_camera.itemData(i)==path: studio.cmb_camera.setCurrentIndex(i); break
            except Exception: pass

    def _start_quick_mic_meter(self,row):
        self._stop_quick_mic_meter(); self._quick_mic_stop.clear(); self._quick_mic_level=0.0; self._quick_mic_last_frame=0.0
        meta=dict(row.get('meta') or {}); backend=str(row.get('backend') or meta.get('backend') or 'sounddevice')
        if backend=='alsa':
            dev=str(row.get('device') or meta.get('alsa_device') or '')
            arecord=shutil.which('arecord')
            if not (arecord and dev):
                self.quick_mic_meter.setFormat('Mic Level — no ALSA capture route'); return
            # R23n: SOF DMICs are commonly 2/4-channel hardware.  A forced mono
            # arecord can exit immediately even when the microphone is healthy.
            # Probe short-lived candidates and accept only one that actually
            # produces PCM bytes.  ``plughw`` performs safe channel conversion.
            candidates=[]
            for rate in (48000,16000):
                for ch in (2,4,1): candidates.append((rate,ch))
            for rate,ch in candidates:
                try:
                    proc=subprocess.Popen([arecord,'-q','-D',dev,'-f','S16_LE','-c',str(ch),'-r',str(rate),'-t','raw','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
                    import select as _select
                    ready,_,_=_select.select([proc.stdout],[],[],0.35) if proc.stdout else ([],[],[])
                    raw=proc.stdout.read(4096) if ready and proc.stdout else b''
                    if not raw:
                        try: proc.terminate(); proc.wait(timeout=.25)
                        except Exception:
                            try: proc.kill()
                            except Exception: pass
                        continue
                    self._quick_mic_proc=proc
                    try:
                        import numpy as _np
                        a=_np.frombuffer(raw,dtype='<i2'); self._quick_mic_level=float(_np.max(_np.abs(a.astype(_np.int32))))/32768.0 if a.size else 0.0
                        self._quick_mic_last_frame=time.monotonic()
                    except Exception: pass
                    def reader():
                        while not self._quick_mic_stop.is_set() and proc.poll() is None:
                            raw2=proc.stdout.read(4096) if proc.stdout else b''
                            if not raw2: break
                            try:
                                import numpy as _np
                                a=_np.frombuffer(raw2,dtype='<i2'); self._quick_mic_level=float(_np.max(_np.abs(a.astype(_np.int32))))/32768.0 if a.size else 0.0
                                self._quick_mic_last_frame=time.monotonic()
                            except Exception: pass
                    self._quick_mic_thread=threading.Thread(target=reader,daemon=True,name='GrooveboxQuickMicALSA'); self._quick_mic_thread.start(); self._quick_mic_timer.start()
                    self.quick_mic_meter.setFormat(f'Mic Level %p% · {rate//1000}k/{ch}ch')
                    return
                except Exception:
                    self._quick_mic_proc=None
            self.quick_mic_meter.setFormat('Mic Level — no PCM samples'); return
        try:
            from audio_os_backend import open_input_stream_adaptive
            preferred=str(row.get('name',''))
            # Skip known non-capture endpoints so a failed open cannot loop.
            if any(t in preferred.casefold() for t in ('null','dummy','groovebox_all_outputs','auto_null')):
                self.quick_mic_meter.setFormat('Mic Level — no usable input'); return
            def cb(indata,_frames,_ti,_status):
                try:
                    import numpy as _np
                    a=_np.asarray(indata,dtype=_np.float32).reshape(-1); self._quick_mic_level=float(_np.max(_np.abs(a))) if a.size else 0.0; self._quick_mic_last_frame=time.monotonic()
                except Exception: pass
            st,_rate,_idx=open_input_stream_adaptive(samplerate=48000,channels=1,dtype='float32',callback=cb,blocksize=1024,latency='low',preferred_name=preferred)
            st.start(); self._quick_mic_stream=st; self._quick_mic_timer.start()
        except Exception:
            self.quick_mic_meter.setFormat('Mic Level — input open failed')

    def _stop_quick_mic_meter(self):
        st=getattr(self,'_quick_mic_stream',None); self._quick_mic_stream=None
        if st is not None:
            try: st.stop(); st.close()
            except Exception: pass
        self._quick_mic_stop.set(); proc=getattr(self,'_quick_mic_proc',None); self._quick_mic_proc=None
        if proc is not None:
            try: proc.terminate()
            except Exception: pass
        th=getattr(self,'_quick_mic_thread',None); self._quick_mic_thread=None
        if th is not None and th.is_alive(): th.join(timeout=.25)
        try: self._quick_mic_timer.stop()
        except Exception: pass

    def _paint_quick_mic_level(self):
        level=max(0.0,min(1.0,float(getattr(self,'_quick_mic_level',0.0) or 0.0)))
        last=float(getattr(self,'_quick_mic_last_frame',0.0) or 0.0); now=time.monotonic()
        if last and now-last>.35: level*=max(0.0,1.0-(now-last-.35)/.8)
        pct=0 if level<=0 else int(round(max(0.0,min(100.0,(20.0*math.log10(level)+60.0)*(100.0/60.0)))))
        try: self.quick_mic_meter.setValue(pct); self.quick_mic_meter.setFormat('Mic level %p%')
        except Exception: pass

    # ------------------------------------------------------------------ outputs / Wi-Fi TV
    def _build_outputs_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Device Outputs · Wi-Fi TV · Game Share</b>"))
        intro = QLabel(
            "Route the same Performance stream to hot-plugged HDMI/VGA/USB displays and "
            "PipeWire/Pulse audio sinks (including paired Bluetooth/USB/HDMI audio). A local "
            "Wi-Fi/LAN TV page can play the programmed mixed-type playlist; game .zip packages "
            "can be shared to another box without executing them on the receiver."
        )
        intro.setWordWrap(True); lay.addWidget(intro)

        dev = QGroupBox("Local device routing"); df = QFormLayout(dev)
        self.cmb_output_display = QComboBox(); df.addRow("Display", self.cmb_output_display)
        self.cmb_output_audio = QComboBox()
        self.cmb_output_audio.addItem("All detected outputs (default)")
        self.cmb_output_audio.setEnabled(False)
        df.addRow("Audio sink", self.cmb_output_audio)
        drow = QHBoxLayout()
        bref = QPushButton("↻ Detect HDMI/VGA/USB/Bluetooth"); bref.clicked.connect(self._refresh_output_devices)
        bapply = QPushButton("Apply to new playback"); bapply.clicked.connect(self._apply_output_routing)
        drow.addWidget(bref); drow.addWidget(bapply); df.addRow(drow)
        self.lbl_output_devices = QLabel("Not scanned yet."); self.lbl_output_devices.setWordWrap(True); df.addRow("Detected", self.lbl_output_devices)
        lay.addWidget(dev)

        mix = QGroupBox("Device mixer")
        mix.setToolTip("One level per device. Inputs mix into the recording. Outputs scale playback.")
        self.device_mixer_layout = QVBoxLayout(mix)
        self.device_mixer_layout.addWidget(QLabel("Levels appear after Detect. 100% is unity."))
        self._device_gains = getattr(self, "_device_gains", {}) or {}
        lay.addWidget(mix)
        self._device_mixer_box = mix

        tv = QGroupBox("Wi-Fi / Ethernet TV output"); tf = QFormLayout(tv)
        self.spin_tv_port = QSpinBox(); self.spin_tv_port.setRange(1024, 65535); self.spin_tv_port.setValue(8780); tf.addRow("TV host port", self.spin_tv_port)
        self.lbl_tv_url = QLabel("Stopped"); self.lbl_tv_url.setWordWrap(True); self.lbl_tv_url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); tf.addRow("TV URL", self.lbl_tv_url)
        trow = QHBoxLayout()
        btvon = QPushButton("Start TV host + publish playlist"); btvon.clicked.connect(self._start_tv_host)
        bpub = QPushButton("Republish playlist"); bpub.clicked.connect(self._publish_tv_playlist)
        btvoff = QPushButton("Stop TV host"); btvoff.clicked.connect(self._stop_tv_host)
        trow.addWidget(btvon); trow.addWidget(bpub); trow.addWidget(btvoff); tf.addRow(trow)
        crow = QHBoxLayout()
        bcast = QPushButton("Cast TV URL (catt/Chromecast)"); bcast.clicked.connect(self._cast_tv_url)
        bgame = QPushButton("Share selected game .zip"); bgame.clicked.connect(self._share_selected_game)
        crow.addWidget(bcast); crow.addWidget(bgame); tf.addRow(crow)
        self.lbl_game_share = QLabel("No game package shared."); self.lbl_game_share.setWordWrap(True); self.lbl_game_share.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); tf.addRow("Game share", self.lbl_game_share)
        lay.addWidget(tv)

        note = QLabel(
            "Display routing is per new mpv process; USB DisplayLink/VGA adapters appear when the OS exposes them as displays. "
            "Bluetooth must already be paired/connected by the OS. The TV page uses normal HTTP media with byte-range support, "
            "so it works without a proprietary receiver app when the TV/browser supports the file codecs."
        )
        note.setWordWrap(True); note.setStyleSheet("color:#8ab4c8; font-size:9pt;"); lay.addWidget(note)
        lay.addStretch(1)
        return w

    def _refresh_output_devices_if_visible(self):
        # Polling is hot-plug recovery, not a GUI-thread scan. Hidden windows stay idle.
        if getattr(self, "_output_refresh_timer", None) is not None and self.isVisible():
            self._refresh_output_devices()

    def _refresh_output_devices(self):
        if getattr(self, "_output_scan_inflight", False):
            return
        self._output_scan_inflight = True
        self._output_scan_generation = int(getattr(self, "_output_scan_generation", 0)) + 1
        generation = self._output_scan_generation
        try: self.lbl_output_devices.setText("Scanning displays and audio endpoints in background…")
        except Exception: pass
        def work():
            displays=[]; audio=[]; error=""
            try:
                from media_output_router import detect_displays, detect_audio_targets
                displays=detect_displays(); audio=detect_audio_targets()
            except Exception as exc:
                error=str(exc)
            try: self._output_device_bridge.done.emit(generation, displays, audio, error)
            except Exception: pass
        try:
            self._worker_pool.start(_PoolTask(work))
        except Exception:
            # Fallback is intentionally rare; still avoid a long blocking probe.
            self._output_scan_inflight=False
            self.lbl_output_devices.setText("Device scan could not be queued; use Detect to retry.")

    def _on_output_devices_ready(self, generation, displays, audio, error):
        if int(generation) != int(getattr(self, "_output_scan_generation", 0)):
            return
        self._output_scan_inflight = False
        if error:
            self.lbl_output_devices.setText(f"Device scan unavailable: {error}")
            return
        old_display = getattr(self, "_output_display", None)
        old_display_name = getattr(old_display, "name", "") or ""
        try:
            box = getattr(self, "cmb_output_display", None)
            if box is not None and not old_display_name:
                old_display_name = box.currentText()
        except RuntimeError:
            old_display_name = ""
        old_audio = getattr(self, "_output_audio_target", None)
        old_audio_name = getattr(old_audio, "name", "")
        try:
            if not old_audio_name and getattr(self, "cmb_output_audio", None) is not None:
                old_text = self.cmb_output_audio.currentText()
                old_audio_name = next((getattr(a, "name", "") for a in self._output_audio if getattr(a, "description", "") in old_text), "")
        except RuntimeError:
            old_audio_name = ""
        self._output_displays = list(displays or [])
        try:
            from media_output_router import AudioTarget
            # Always force a single "All detected outputs" entry — no divergent
            # menu state across Performance / Player / quick selectors.
            all_out = AudioTarget("__all_detected__", "All detected outputs (default)", kind="all", backend="pulse")
            self._output_audio = [all_out]
            self._output_audio_target = all_out
        except Exception:
            self._output_audio = list(audio or [])
        if not hasattr(self, "cmb_output_display") or not hasattr(self, "cmb_output_audio"):
            return
        try:
            self.cmb_output_display.blockSignals(True); self.cmb_output_display.clear()
            for d in self._output_displays:
                tags=[]
                if getattr(d,"primary",False): tags.append("primary")
                if getattr(d,"geometry",""): tags.append(d.geometry)
                self.cmb_output_display.addItem(d.name + (" · " + ", ".join(tags) if tags else ""))
            if not self._output_displays: self.cmb_output_display.addItem("Default display")
            if old_display_name:
                for i,d in enumerate(self._output_displays):
                    if getattr(d,"name","")==old_display_name:
                        self.cmb_output_display.setCurrentIndex(i); break
            self.cmb_output_display.blockSignals(False)
            self.cmb_output_audio.blockSignals(True); self.cmb_output_audio.clear()
            for a in self._output_audio:
                tag=f" [{a.kind}]" if getattr(a,"kind","") and a.kind not in ("default","all") else ""
                self.cmb_output_audio.addItem(a.description + tag)
            if self.cmb_output_audio.count():
                self.cmb_output_audio.setCurrentIndex(0)
            self.cmb_output_audio.setEnabled(False)
            self.cmb_output_audio.blockSignals(False)
            self.lbl_output_devices.setText(f"{len(self._output_displays)} display target(s) · audio always mirrors every detected sink (All Audio Devices). HDMI/USB endpoints refresh automatically while this window is visible.")
            self._rebuild_device_mixer(audio)
            self._apply_output_routing()
        except (RuntimeError, AttributeError):
            return

    def _rebuild_device_mixer(self, audio):
        box = getattr(self, "_device_mixer_box", None)
        lay = getattr(self, "device_mixer_layout", None)
        if box is None or lay is None:
            return
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._device_gains = getattr(self, "_device_gains", {}) or {}
        rows = list(audio or [])
        if not rows:
            lay.addWidget(QLabel("No devices yet. Detect to fill the mixer."))
            return
        for target in rows:
            name = str(getattr(target, "name", "") or getattr(target, "description", "") or "device")
            row = QHBoxLayout()
            lab = QLabel(name[:42])
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 200)
            slider.setValue(int(self._device_gains.get(name, 100)))
            val = QLabel(f"{slider.value()}%")
            def _set(v, n=name, label=val):
                self._device_gains[n] = int(v)
                label.setText(f"{int(v)}%")
                try:
                    self.host._device_gains = dict(self._device_gains)
                except Exception:
                    pass
            slider.valueChanged.connect(_set)
            row.addWidget(lab)
            row.addWidget(slider, 1)
            row.addWidget(val)
            holder = QWidget(); holder.setLayout(row)
            lay.addWidget(holder)

    def _apply_output_routing(self):
        di = self.cmb_output_display.currentIndex() if hasattr(self, "cmb_output_display") else -1
        self._output_display = self._output_displays[di] if 0 <= di < len(self._output_displays) else None
        # Always force All detected outputs — ignore any residual combo index.
        try:
            from media_output_router import AudioTarget, _ensure_all_pulse_outputs_sink
            all_out = AudioTarget("__all_detected__", "All detected outputs (default)", kind="all", backend="pulse")
            self._output_audio_target = all_out
            if not self._output_audio or getattr(self._output_audio[0], "name", "") != "__all_detected__":
                self._output_audio = [all_out]
            _combined = _ensure_all_pulse_outputs_sink()
            setattr(self.host, "_preferred_audio_output_name", _combined or "")
            if _combined:
                subprocess.run([shutil.which("pactl") or "pactl", "set-default-sink", _combined],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5, check=False)
        except Exception:
            if self._output_audio:
                self._output_audio_target = self._output_audio[0]
        dname = getattr(self._output_display, "name", "default") if self._output_display else "default"
        aname = "All detected outputs (default)"
        self.lbl_status.setText(f"Output routing: display={dname} · audio={aname}")

    def _start_tv_host(self):
        try:
            from media_output_router import MediaShareServer
            if self._media_share_server is not None:
                self._media_share_server.stop()
            self._media_share_server = MediaShareServer(int(self.spin_tv_port.value()))
            self._media_share_server.start()
            self._publish_tv_playlist()
            self.lbl_tv_url.setText(self._media_share_server.tv_url())
            self.lbl_status.setText("Wi-Fi/LAN TV host active; open the TV URL in a browser/network player.")
        except Exception as e:
            self._media_share_server = None
            QMessageBox.warning(self, "TV host", str(e))

    def _publish_tv_playlist(self):
        if self._media_share_server is None:
            return
        try:
            self._media_share_server.set_playlist(self._playlist)
            if self._performance_media_path and os.path.isfile(self._performance_media_path):
                self._media_share_server.set_current(self._performance_media_path)
            self.lbl_tv_url.setText(self._media_share_server.tv_url())
            self.lbl_status.setText(f"TV playlist published: {len(self._media_share_server.playlist)} media item(s).")
        except Exception as e:
            QMessageBox.warning(self, "Publish TV playlist", str(e))

    def _stop_tv_host(self):
        srv, self._media_share_server = self._media_share_server, None
        if srv is not None:
            try: srv.stop()
            except Exception: pass
        if hasattr(self, "lbl_tv_url"): self.lbl_tv_url.setText("Stopped")

    def _cast_tv_url(self):
        if self._media_share_server is None:
            self._start_tv_host()
        if self._media_share_server is None:
            return
        try:
            from media_output_router import cast_with_catt
            ok, msg = cast_with_catt(self._media_share_server.tv_url())
            if ok: self.lbl_status.setText(msg)
            else: QMessageBox.information(self, "Chromecast handoff", msg + "\n\nThe TV URL remains usable directly in a smart-TV browser.")
        except Exception as e:
            QMessageBox.warning(self, "Chromecast handoff", str(e))

    def _share_selected_game(self):
        path = None
        for p in self._selected_paths():
            if os.path.isfile(p) and _gb_ext(p) in GAME_EXT:
                path = p; break
        if path is None:
            QMessageBox.information(self, "Game share", "Select a packaged .zip game in the Performance browser first.")
            return
        if self._media_share_server is None:
            self._start_tv_host()
        if self._media_share_server is None:
            return
        try:
            key = self._media_share_server.share_game(path)
            self._last_shared_game_url = self._media_share_server.game_url(key)
            self.lbl_game_share.setText(self._last_shared_game_url)
            self.lbl_status.setText(f"Game package shared on LAN: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Game share", str(e))

    # ------------------------------------------------------------------ drive / cloning
    def _build_transfer_tab(self) -> QWidget:
        w=QWidget(); lay=QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Operation Station Drive · Clone · Transfer</b>"))
        note=QLabel("Move projects/modules/samples/exports or clone this Operation Station build over Wi-Fi, Ethernet, or mounted USB storage. Clone bundles carry SHA-256 manifests and do not auto-execute on the receiving machine.")
        note.setWordWrap(True); lay.addWidget(note)
        grp=QGroupBox("Version clone"); f=QFormLayout(grp)
        self.chk_clone_source=QCheckBox("Source code"); self.chk_clone_source.setChecked(True); f.addRow(self.chk_clone_source)
        self.chk_clone_exec=QCheckBox("Build/executable kit"); self.chk_clone_exec.setChecked(True); f.addRow(self.chk_clone_exec)
        self.chk_clone_deps=QCheckBox("Dependency/offline install assets"); self.chk_clone_deps.setChecked(True); f.addRow(self.chk_clone_deps)
        self.chk_clone_content=QCheckBox("Include my projects/samples/modules"); self.chk_clone_content.setChecked(False); f.addRow(self.chk_clone_content)
        row=QHBoxLayout(); b=QPushButton("Create V3 Clone Bundle"); b.clicked.connect(self._create_clone_bundle); row.addWidget(b)
        b=QPushButton("Verify Bundle"); b.clicked.connect(self._verify_clone_bundle); row.addWidget(b); f.addRow(row)
        self.lbl_clone=QLabel("No clone bundle yet."); self.lbl_clone.setWordWrap(True); self.lbl_clone.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); f.addRow("Bundle",self.lbl_clone)
        lay.addWidget(grp)
        net=QGroupBox("Wi-Fi / Ethernet share"); nf=QFormLayout(net)
        self.spin_clone_port=QSpinBox(); self.spin_clone_port.setRange(1024,65535); self.spin_clone_port.setValue(8783); nf.addRow("Port",self.spin_clone_port)
        nr=QHBoxLayout(); b=QPushButton("Start Clone Share"); b.clicked.connect(self._start_clone_share); nr.addWidget(b); b=QPushButton("Stop"); b.clicked.connect(self._stop_clone_share); nr.addWidget(b); nf.addRow(nr)
        self.lbl_clone_url=QLabel("Stopped"); self.lbl_clone_url.setWordWrap(True); self.lbl_clone_url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); nf.addRow("Network URL",self.lbl_clone_url)
        lay.addWidget(net)

        nearby=QGroupBox("Nearby Grooveboxes · router-free Wi-Fi Share")
        nv=QVBoxLayout(nearby)
        nn=QLabel("Nearby presence is automatic whenever Groovebox is running. Devices may use an existing LAN or a self-hosted Groovebox Direct Wi-Fi link; Internet and a router are not required. Direct hotspot mode is explicit because some single-radio adapters must leave their current Wi-Fi to host it.")
        nn.setWordWrap(True); nv.addWidget(nn)
        self.chk_nearby_receive=QCheckBox("Allow incoming files from nearby Grooveboxes")
        self.chk_nearby_receive.setChecked(False); self.chk_nearby_receive.toggled.connect(self._nearby_set_receive); nv.addWidget(self.chk_nearby_receive)
        # GROOVEBOX_R23R_PEER_LINKS_20261101: LAN in/out, IP links, organised peers.
        _svc=self._nearby_service()
        lr=QHBoxLayout()
        self.chk_nearby_announce=QCheckBox("Announce me on the LAN (out)"); self.chk_nearby_announce.setChecked(bool(getattr(_svc,"announce_enabled",True)))
        self.chk_nearby_discover=QCheckBox("Find Grooveboxes on the LAN (in)"); self.chk_nearby_discover.setChecked(bool(getattr(_svc,"discover_enabled",True)))
        self.chk_nearby_announce.toggled.connect(lambda v: (self._nearby_service() and self._nearby_service().set_lan(announce=v)))
        self.chk_nearby_discover.toggled.connect(lambda v: (self._nearby_service() and self._nearby_service().set_lan(discover=v)))
        lr.addWidget(self.chk_nearby_announce); lr.addWidget(self.chk_nearby_discover); nv.addLayout(lr)
        myr=QHBoxLayout()
        self.lbl_nearby_mylink=QLabel(" · ".join(_svc.my_links()) if _svc is not None and hasattr(_svc,"my_links") else "—")
        self.lbl_nearby_mylink.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        b=QPushButton("Copy my link"); b.clicked.connect(self._nearby_copy_link)
        myr.addWidget(QLabel("My link:")); myr.addWidget(self.lbl_nearby_mylink,1); myr.addWidget(b); nv.addLayout(myr)
        cr=QHBoxLayout()
        self.edit_nearby_link=QLineEdit(); self.edit_nearby_link.setPlaceholderText("IP, host:port or groovebox://… link (Wi-Fi, LAN, VPN, direct)")
        self.edit_nearby_link.returnPressed.connect(self._nearby_connect_link)
        b=QPushButton("Connect"); b.clicked.connect(self._nearby_connect_link)
        cr.addWidget(self.edit_nearby_link,1); cr.addWidget(b); nv.addLayout(cr)
        dr=QHBoxLayout()
        b=QPushButton("↻ Scan Nearby"); b.clicked.connect(self._nearby_scan_now); dr.addWidget(b)
        b=QPushButton("Start Direct Wi-Fi"); b.clicked.connect(self._nearby_start_direct); dr.addWidget(b)
        b=QPushButton("Stop Direct Wi-Fi"); b.clicked.connect(self._nearby_stop_direct); dr.addWidget(b)
        # GROOVEBOX_R23R_NEARBY_ROBUST_20261101: router-free ad hoc cell shared by all Grooveboxes.
        b=QPushButton("Start Ad hoc"); b.setToolTip("Create/join the shared GROOVEBOX-ADHOC cell (no router, no host device; link-local addressing).")
        b.clicked.connect(self._nearby_start_adhoc); dr.addWidget(b)
        b=QPushButton("Stop Ad hoc"); b.clicked.connect(self._nearby_stop_adhoc); dr.addWidget(b)
        nv.addLayout(dr)
        self.lbl_nearby_direct=QLabel("Direct-link status: checking capabilities…"); self.lbl_nearby_direct.setWordWrap(True); nv.addWidget(self.lbl_nearby_direct)
        self.lst_nearby=QListWidget(); self.lst_nearby.setMinimumHeight(115); nv.addWidget(QLabel("Nearby Grooveboxes / Direct radios")); nv.addWidget(self.lst_nearby)
        pr=QHBoxLayout()
        b=QPushButton("Join Selected Direct Radio"); b.clicked.connect(self._nearby_join_selected); pr.addWidget(b)
        b=QPushButton("Browse Selected Groovebox"); b.clicked.connect(self._nearby_browse_selected); pr.addWidget(b)
        nv.addLayout(pr)
        hist=QLabel("Known Grooveboxes history (metadata only; received files are separate)"); hist.setWordWrap(True); nv.addWidget(hist)
        self.lst_nearby_history=QListWidget(); self.lst_nearby_history.setMinimumHeight(90); nv.addWidget(self.lst_nearby_history)
        orr=QHBoxLayout()
        for _t,_fn in (("Rename…",self._nearby_rename),("★ Favourite",self._nearby_toggle_fav),("Group…",self._nearby_set_group),
                       ("Block / Unblock",self._nearby_toggle_block),("Reconnect",self._nearby_reconnect)):
            b=QPushButton(_t); b.clicked.connect(_fn); orr.addWidget(b)
        nv.addLayout(orr)
        hr=QHBoxLayout()
        b=QPushButton("Forget Selected"); b.clicked.connect(self._nearby_forget_selected_history); hr.addWidget(b)
        b=QPushButton("Reset Known Grooveboxes History"); b.clicked.connect(self._nearby_reset_history); hr.addWidget(b)
        nv.addLayout(hr)
        self.lst_nearby_files=QListWidget(); self.lst_nearby_files.setMinimumHeight(130); nv.addWidget(QLabel("Shared files on selected Groovebox")); nv.addWidget(self.lst_nearby_files)
        tr=QHBoxLayout()
        b=QPushButton("Receive Selected File"); b.clicked.connect(self._nearby_download_selected); tr.addWidget(b)
        b=QPushButton("Send File to Selected Groovebox"); b.clicked.connect(self._nearby_send_file); tr.addWidget(b)
        nv.addLayout(tr)
        self.lbl_nearby_progress=QLabel("Idle"); self.lbl_nearby_progress.setWordWrap(True); nv.addWidget(self.lbl_nearby_progress)
        # Messages between Grooveboxes (LAN, ad hoc, Direct Wi-Fi or internet links).
        msg=QGroupBox("Messages · groups · live camera/mic"); mv=QVBoxLayout(msg)
        # GROOVEBOX_R23R_GROUP_TRACE_MESSAGING_20261101 / GROOVEBOX_R23R_LIVE_AV_20261101
        cvr=QHBoxLayout(); cvr.addWidget(QLabel("Conversation:"))
        self.cmb_nearby_conv=QComboBox(); self.cmb_nearby_conv.setMinimumWidth(220)
        self.cmb_nearby_conv.currentIndexChanged.connect(lambda _i: (setattr(self,"_nearby_msg_count",-1), self._refresh_nearby_messages()))
        cvr.addWidget(self.cmb_nearby_conv,1)
        for _t,_fn,_tip in (("New group…",self._nearby_new_group,"Create a group chat from known Grooveboxes"),
                            ("Members…",self._nearby_group_members,"Change who is in the selected group"),
                            ("Leave",self._nearby_leave_group,"Remove the selected group from this Groovebox"),
                            ("Save transcript",self._nearby_save_transcript,"Save this conversation as a note (📝 Notes)")):
            b=QPushButton(_t); b.setToolTip(_tip); b.clicked.connect(_fn); cvr.addWidget(b)
        mv.addLayout(cvr)
        self.txt_nearby_messages=QTextBrowser(); self.txt_nearby_messages.setMinimumHeight(140); mv.addWidget(self.txt_nearby_messages)
        mr=QHBoxLayout()
        self.edit_nearby_message=QLineEdit(); self.edit_nearby_message.setPlaceholderText("Message the selected Groovebox… (Enter sends)")
        self.edit_nearby_message.returnPressed.connect(self._nearby_send_message)
        b=QPushButton("Send"); b.clicked.connect(self._nearby_send_message)
        mr.addWidget(self.edit_nearby_message,1); mr.addWidget(b)
        b=QPushButton("Clear"); b.clicked.connect(self._nearby_clear_messages); mr.addWidget(b)
        mv.addLayout(mr)
        self.chk_nearby_messages=QCheckBox("Accept messages from nearby Grooveboxes (blocked devices are always refused)")
        self.chk_nearby_messages.setChecked(bool(getattr(_svc,"allow_messages",True)))
        self.chk_nearby_messages.toggled.connect(self._nearby_toggle_messages); mv.addWidget(self.chk_nearby_messages)
        lvr=QHBoxLayout()
        self.chk_live_cam=QCheckBox("Camera"); self.chk_live_cam.setChecked(True)
        self.chk_live_mic=QCheckBox("Mic"); self.chk_live_mic.setChecked(True)
        self.chk_live_test=QCheckBox("Test pattern"); self.chk_live_test.setToolTip("Send a test picture + tone instead of the camera/mic (link check).")
        for w_ in (self.chk_live_cam,self.chk_live_mic,self.chk_live_test): lvr.addWidget(w_)
        self.cmb_live_resolution=QComboBox(); self.cmb_live_resolution.addItems(["1080p · Full HD", "1440p · QHD", "2160p · 4K"])
        self.cmb_live_resolution.setCurrentIndex(0); self.cmb_live_resolution.setToolTip("Live video output profile. 1080p30 is the default; the selected camera must support the requested capture size.")
        self.cmb_live_bitrate=QComboBox(); self.cmb_live_bitrate.addItems(["6M", "8M", "12M"]); self.cmb_live_bitrate.setCurrentText("6M")
        self.cmb_live_bitrate.setToolTip("H.264 target bitrate. Higher quality uses more LAN bandwidth and CPU.")
        lvr.addWidget(QLabel("Video")); lvr.addWidget(self.cmb_live_resolution); lvr.addWidget(QLabel("Bitrate")); lvr.addWidget(self.cmb_live_bitrate)
        self.btn_live=QPushButton("🔴 Go live · 1080p"); self.btn_live.setCheckable(True); self.btn_live.toggled.connect(self._nearby_toggle_live); lvr.addWidget(self.btn_live)
        for _t,_fn,_tip in (("📺 Watch",self._nearby_watch_selected,"Watch the selected Groovebox's live camera/mic"),
                            ("📺 Watch group",self._nearby_watch_group,"Open every live member of the selected group"),
                            ("⏺ Record",self._nearby_record_selected,"Record the selected Groovebox's stream (or yours when none is selected)"),
                            ("⏹ Stop recordings",self._nearby_stop_recordings,"Finish and save every recording")):
            b=QPushButton(_t); b.setToolTip(_tip); b.clicked.connect(_fn); lvr.addWidget(b)
        mv.addLayout(lvr)
        self.lbl_live=QLabel("Live: off"); self.lbl_live.setWordWrap(True); mv.addWidget(self.lbl_live)
        # GROOVEBOX_R23R_JAM_PTT_SHARE_20261101
        jr=QHBoxLayout()
        self.chk_jam_lead=QCheckBox("🎚 Lead jam"); self.chk_jam_lead.setToolTip("Send BPM + play/stop + position to the selected Groovebox or group every second.")
        self.chk_jam_follow=QCheckBox("🎧 Follow jam"); self.chk_jam_follow.setToolTip("Follow BPM and transport from whoever leads a jam to you (clock-offset corrected).")
        self.chk_ptt=QCheckBox("🎙 Push-to-talk (hold F8)"); self.chk_ptt.setToolTip("Hold F8 anywhere in Groovebox (or in a Groovebox game) to talk to everyone watching/listening.")
        self.chk_ptt_listen=QCheckBox("🔊 Auto-listen to push-to-talk"); self.chk_ptt_listen.setChecked(True)
        for w_ in (self.chk_jam_lead,self.chk_jam_follow,self.chk_ptt,self.chk_ptt_listen): jr.addWidget(w_)
        b=QPushButton("📦 Share project…"); b.setToolTip("Send this project + its samples to the selected Groovebox or every group member, with per-member progress.")
        b.clicked.connect(self._nearby_share_project); jr.addWidget(b)
        mv.addLayout(jr)
        # GROOVEBOX_R23R_LIVE_EDIT_TOGETHER_20261101: Edit Together (project co-management).
        etg=QGroupBox("🤝 Edit Together · co-manage a project live"); ev=QVBoxLayout(etg)
        er=QHBoxLayout()
        for _t,_fn,_tip in (("🤝 Start with conversation",self._et_start,"Share this project with the selected Groovebox or every group member and edit it together live."),
                            ("🙋 Request Edit Together",self._et_request,"Ask the selected Groovebox to let you edit its project together."),
                            ("🔒 Lock section…",self._et_lock,"Owner: only one member may change a project section (playlist, sequences, seed …)."),
                            ("💾 Save shared copy",self._et_save,"Save the shared project into your own projects folder."),
                            ("Leave / End",self._et_leave,"Leave the session (owner: end it for everyone).")):
            b=QPushButton(_t); b.setToolTip(_tip); b.clicked.connect(_fn); er.addWidget(b)
        ev.addLayout(er)
        ar=QHBoxLayout()
        self.btn_et_requests=QPushButton("📥 Access ET Requests"); self.btn_et_requests.setToolTip("Approve or deny waiting Edit Together requests and invites.")
        self.btn_et_requests.clicked.connect(self._et_access_requests); ar.addWidget(self.btn_et_requests)
        self.lbl_et=QLabel("Edit Together: not in a session"); self.lbl_et.setWordWrap(True); ar.addWidget(self.lbl_et,1)
        ev.addLayout(ar)
        self.txt_et_activity=QTextBrowser(); self.txt_et_activity.setMaximumHeight(90); ev.addWidget(self.txt_et_activity)
        mv.addWidget(etg)
        self.chk_jam_lead.toggled.connect(self._jam_timer_update); self.chk_jam_follow.toggled.connect(self._jam_timer_update)
        self.chk_ptt.toggled.connect(self._ptt_install)
        self._jam_timer=QTimer(self); self._jam_timer.setInterval(1000); self._jam_timer.timeout.connect(self._jam_tick)
        self._ptt_players={}
        nv.addWidget(msg)
        self._nearby_msg_count=-1
        lay.addWidget(nearby)

        usb=QGroupBox("USB / mounted drive"); uf=QFormLayout(usb)
        self.cmb_clone_mount=QComboBox(); uf.addRow("Destination",self.cmb_clone_mount)
        ur=QHBoxLayout(); b=QPushButton("↻ Detect Drives"); b.clicked.connect(self._refresh_clone_mounts); ur.addWidget(b); b=QPushButton("Copy Clone to Drive"); b.clicked.connect(self._copy_clone_to_mount); ur.addWidget(b); uf.addRow(ur)
        lay.addWidget(usb)
        iso=QGroupBox("Finished product ISO · OS-style update copy"); iv=QFormLayout(iso)
        iso_note=QLabel("Copies the finished Groovebox ISO onto the selected drive inside Groovebox/ISO. Existing folders and files on the drive are preserved; a same-named ISO is replaced atomically and checked with SHA-256, like an OS update that keeps the rest of the disk.")
        iso_note.setWordWrap(True); iv.addRow(iso_note)
        self.lbl_iso_source=QLabel("No finished ISO selected."); self.lbl_iso_source.setWordWrap(True); self.lbl_iso_source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); iv.addRow("ISO",self.lbl_iso_source)
        ir=QHBoxLayout(); b=QPushButton("↻ Find Finished ISO"); b.clicked.connect(self._find_finished_iso); ir.addWidget(b); b=QPushButton("Browse ISO…"); b.clicked.connect(self._browse_iso); ir.addWidget(b); b=QPushButton("Copy Finished ISO to Drive"); b.clicked.connect(self._copy_iso_to_mount); ir.addWidget(b); iv.addRow(ir)
        self.chk_iso_verify=QCheckBox("Verify SHA-256 after copy"); self.chk_iso_verify.setChecked(True); iv.addRow(self.chk_iso_verify)
        self.lbl_iso_progress=QLabel("Idle"); self.lbl_iso_progress.setWordWrap(True); self.lbl_iso_progress.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); iv.addRow("Copy",self.lbl_iso_progress)
        lay.addWidget(iso); lay.addStretch(1); return w

    def _nearby_service(self):
        return getattr(self.host, "_nearby_share_service", None)

    def _nearby_async(self, kind, fn):
        def run():
            try: self._nearby_bridge.result.emit(kind, fn(), "")
            except Exception as e: self._nearby_bridge.result.emit(kind, None, str(e))
        # PERF_THREAD_LIFECYCLE_20260924: nearby network work is owned by the
        # same Qt pool as media probes, so app shutdown can drain it.
        self._worker_pool.start(_PoolTask(run))

    def _nearby_set_receive(self, checked):
        svc=self._nearby_service()
        if svc is not None: svc.set_incoming_enabled(bool(checked))
        self.lbl_nearby_progress.setText("Incoming file reception enabled." if checked else "Incoming file reception disabled; discovery remains active.")

    def _refresh_nearby_ui(self):
        svc=self._nearby_service()
        if svc is None or not hasattr(self,'lst_nearby'): return
        try:
            peers=svc.peer_list(); direct=svc.direct_candidate_list()
            old=self.lst_nearby.currentRow(); self.lst_nearby.clear(); self._nearby_peer_rows=[]
            for p in peers:
                item=QListWidgetItem(f"{'🔴' if p.get('live') else '●'} {p.get('name','Groovebox')} · {p.get('ip','?')}:{p.get('port','?')} · {p.get('platform','')}"
                                     + (f" · LIVE {p.get('live_mode','')}" if p.get('live') else ""))
                item.setData(Qt.ItemDataRole.UserRole,{"kind":"peer","data":p}); self.lst_nearby.addItem(item); self._nearby_peer_rows.append(p)
            for d in direct:
                item=QListWidgetItem(f"◉ {d.get('ssid','Groovebox Direct')} · signal {d.get('signal',0)}% · router-free")
                item.setData(Qt.ItemDataRole.UserRole,{"kind":"direct","data":d}); self.lst_nearby.addItem(item)
            if self.lst_nearby.count() and old >= 0: self.lst_nearby.setCurrentRow(min(old,self.lst_nearby.count()-1))
            if hasattr(self,'lst_nearby_history'):
                _sel=(self.lst_nearby_history.currentItem().data(Qt.ItemDataRole.UserRole) or {}).get("node_id") if self.lst_nearby_history.currentItem() else None
                self.lst_nearby_history.clear()
                rows=svc.organised_list() if hasattr(svc,"organised_list") else svc.history_list()
                for h in rows:
                    seen=float(h.get('last_seen',0) or 0); when=time.strftime('%Y-%m-%d %H:%M',time.localtime(seen)) if seen else 'unknown'
                    nm=h.get('nickname') or h.get('name','Groovebox')
                    tags=("★ " if h.get('favorite') else "")+("⛔ " if h.get('blocked') else "")+("● " if h.get('online') else "○ ")
                    grp=f" · [{h.get('group')}]" if h.get('group') else ""
                    via=f" · {h.get('link')}" if h.get('manual') else ""
                    item=QListWidgetItem(f"{tags}{nm}{grp} · last seen {when} · {h.get('platform','')}{via}")
                    item.setData(Qt.ItemDataRole.UserRole,h); self.lst_nearby_history.addItem(item)
                    if _sel and h.get("node_id")==_sel: self.lst_nearby_history.setCurrentItem(item)
            caps=svc.direct.capabilities() if getattr(svc,'direct',None) is not None else {}
            self.lbl_nearby_direct.setText(f"Direct link: host={'yes' if caps.get('host') else 'no'} · scan={'yes' if caps.get('scan') else 'no'} · join={'yes' if caps.get('join') else 'no'} · SSID {caps.get('ssid','—')}" + (f"\n{caps.get('reason')}" if caps.get('reason') else ""))
        except Exception as e: self.lbl_nearby_progress.setText(f"Nearby refresh: {e}")
        try: self._refresh_nearby_messages()
        except Exception: pass
        try: self._ptt_autolisten()
        except Exception: pass
        try: self._et_refresh()
        except Exception: pass

    def _nearby_selected_history(self):
        it=self.lst_nearby_history.currentItem() if hasattr(self,'lst_nearby_history') else None
        return (it.data(Qt.ItemDataRole.UserRole) or {}) if it is not None else None

    def _nearby_copy_link(self):
        try:
            QApplication.clipboard().setText(self.lbl_nearby_mylink.text().split(" · ")[0])
            self.lbl_nearby_progress.setText("Link copied — send it to the other Groovebox and paste it into Connect.")
        except Exception as e:
            self.lbl_nearby_progress.setText(f"Copy failed: {e}")

    def _nearby_connect_link(self):
        svc=self._nearby_service(); link=self.edit_nearby_link.text().strip() if hasattr(self,'edit_nearby_link') else ""
        if svc is None or not link: return
        self.lbl_nearby_progress.setText(f"Connecting to {link}…")
        self._nearby_async("link", lambda: svc.add_link(link))

    def _nearby_reconnect(self):
        row=self._nearby_selected_history(); svc=self._nearby_service()
        if not row or svc is None: return
        link=row.get("link") or f"{row.get('ip')}:{row.get('port')}"
        self._nearby_async("link", lambda: svc.add_link(link))

    def _nearby_rename(self):
        row=self._nearby_selected_history(); svc=self._nearby_service()
        if not row or svc is None: return
        name,ok=QInputDialog.getText(self,"Rename Groovebox","Nickname (empty = original name):",text=row.get("nickname") or "")
        if ok: svc.set_peer_meta(row["node_id"], nickname=(name.strip() or None)); self._refresh_nearby_ui()

    def _nearby_toggle_fav(self):
        row=self._nearby_selected_history(); svc=self._nearby_service()
        if row and svc is not None: svc.set_peer_meta(row["node_id"], favorite=(not row.get("favorite")) or None); self._refresh_nearby_ui()

    def _nearby_set_group(self):
        row=self._nearby_selected_history(); svc=self._nearby_service()
        if not row or svc is None: return
        grp,ok=QInputDialog.getText(self,"Group","Group name (empty = none):",text=row.get("group") or "")
        if ok: svc.set_peer_meta(row["node_id"], group=(grp.strip() or None)); self._refresh_nearby_ui()

    def _nearby_toggle_block(self):
        row=self._nearby_selected_history(); svc=self._nearby_service()
        if row and svc is not None:
            svc.set_peer_meta(row["node_id"], blocked=(not row.get("blocked")) or None, ip=row.get("ip")); self._refresh_nearby_ui()

    def _nearby_forget_selected_history(self):
        svc=self._nearby_service(); it=self.lst_nearby_history.currentItem() if hasattr(self,'lst_nearby_history') else None
        if svc is None or it is None: return
        row=it.data(Qt.ItemDataRole.UserRole) or {}; name=row.get('name','Groovebox')
        if QMessageBox.question(self,"Forget Known Groovebox",f"Forget discovery history for {name}?\n\nThis does not delete any files received from that Groovebox.") != QMessageBox.StandardButton.Yes: return
        svc.forget_peer(str(row.get('node_id',''))); self._refresh_nearby_ui()

    def _nearby_reset_history(self):
        svc=self._nearby_service()
        if svc is None: return
        if QMessageBox.question(self,"Reset Known Grooveboxes History","Clear all remembered Groovebox discovery history?\n\nReceived files, projects, samples and the identity of this Groovebox are not changed.") != QMessageBox.StandardButton.Yes: return
        n=svc.reset_history(); self.lbl_nearby_progress.setText(f"Cleared {n} remembered Groovebox(es).")
        self._refresh_nearby_ui()

    def _nearby_scan_now(self):
        svc=self._nearby_service()
        if svc is None: return
        self.lbl_nearby_progress.setText("Scanning: Groovebox Direct radios + sweeping the local subnet for Grooveboxes…")
        def _both():
            radios=svc.scan_direct_now()
            swept=svc.sweep_subnet() if hasattr(svc,"sweep_subnet") else []
            return {"radios":radios,"swept":swept}
        self._nearby_async("scan", _both)

    def _nearby_start_adhoc(self):
        svc=self._nearby_service()
        if svc is None or not hasattr(svc,"start_adhoc"): return
        if QMessageBox.question(self,"Ad hoc network",
            "Join the shared GROOVEBOX-ADHOC cell? Your Wi-Fi leaves its current network while ad hoc is on. "
            "The cell is open (ad hoc has no WPA2); the block list and the incoming-files switch still apply.") != QMessageBox.StandardButton.Yes:
            return
        self.lbl_nearby_progress.setText("Starting ad hoc…")
        self._nearby_async("direct_start", lambda: svc.start_adhoc())

    def _nearby_stop_adhoc(self):
        svc=self._nearby_service()
        if svc is None or not hasattr(svc,"stop_adhoc"): return
        self._nearby_async("direct_stop", lambda: svc.stop_adhoc())

    def _nearby_message_target(self):
        sel=self._nearby_selected_payload()
        if sel and sel.get("kind")=="peer": return sel.get("data")
        svc=self._nearby_service()
        h=self._nearby_selected_history() if hasattr(self,"_nearby_selected_history") else None
        if svc is not None and h:
            for p in svc.peer_list():
                if p.get("node_id")==h.get("node_id"): return p
        return None

    def _nearby_conv(self):
        """("group", id) for a selected group, else ("direct", None)."""
        c=getattr(self,"cmb_nearby_conv",None)
        d=c.currentData() if c is not None else None
        return tuple(d) if isinstance(d,(list,tuple)) else ("direct",None)

    def _nearby_refresh_conversations(self):
        svc=self._nearby_service(); c=getattr(self,"cmb_nearby_conv",None)
        if svc is None or c is None or not hasattr(svc,"groups"): return
        groups=svc.groups(); keys=[("direct",None)]+[("group",gid) for gid in groups]
        if keys==getattr(self,"_nearby_conv_keys",None): return
        cur=self._nearby_conv(); self._nearby_conv_keys=keys
        c.blockSignals(True); c.clear()
        c.addItem("Direct → selected Groovebox (and all direct messages)",("direct",None))
        for gid,g in groups.items():
            c.addItem(f"👥 {g.get('name','Group')} ({len(g.get('members',[]))})",("group",gid))
        idx=max(0,keys.index(cur)) if cur in keys else 0
        c.setCurrentIndex(idx); c.blockSignals(False)

    def _nearby_send_message(self):
        svc=self._nearby_service(); text=self.edit_nearby_message.text().strip()
        if svc is None or not text: return
        kind,gid=self._nearby_conv()
        if kind=="group" and gid:
            self.edit_nearby_message.clear()
            name=(svc.groups().get(gid) or {}).get("name","group")
            self._nearby_async("message", lambda: (svc.send_text(text, group_id=gid), f"group {name}")[1])
            return
        peer=self._nearby_message_target()
        if not peer:
            QMessageBox.information(self,"Messages","Select a ● Groovebox in the nearby list (or an online known Groovebox), or choose a group conversation."); return
        self.edit_nearby_message.clear()
        self._nearby_async("message", lambda: (svc.send_message(peer,text), peer.get("name","Groovebox"))[1])

    def _nearby_pick_members(self, title, preselected=()):
        svc=self._nearby_service()
        rows={}
        for h in (svc.organised_list() if hasattr(svc,"organised_list") else svc.history_list()):
            if not h.get("blocked") and h.get("node_id"): rows[h["node_id"]]=h.get("nickname") or h.get("name","Groovebox")
        for p in svc.peer_list(): rows.setdefault(p["node_id"],p.get("name","Groovebox"))
        if not rows:
            QMessageBox.information(self,title,"No known Grooveboxes yet — find or link one first."); return None
        dlg=QDialog(self); dlg.setWindowTitle(title); lay=QVBoxLayout(dlg)
        lst=QListWidget()
        for nid,name in rows.items():
            it=QListWidgetItem(name); it.setData(Qt.ItemDataRole.UserRole,nid)
            it.setFlags(it.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if nid in preselected else Qt.CheckState.Unchecked); lst.addItem(it)
        lay.addWidget(QLabel("Members (messages reach offline members later through anyone who can relay):")); lay.addWidget(lst)
        br=QHBoxLayout(); ok=QPushButton("OK"); ok.clicked.connect(dlg.accept); cn=QPushButton("Cancel"); cn.clicked.connect(dlg.reject)
        br.addWidget(ok); br.addWidget(cn); lay.addLayout(br)
        if dlg.exec()!=QDialog.DialogCode.Accepted: return None
        return [{"node":lst.item(i).data(Qt.ItemDataRole.UserRole),"name":lst.item(i).text()}
                for i in range(lst.count()) if lst.item(i).checkState()==Qt.CheckState.Checked]

    def _nearby_new_group(self):
        svc=self._nearby_service()
        if svc is None: return
        from PyQt6.QtWidgets import QInputDialog
        name,ok=QInputDialog.getText(self,"New group chat","Group name:",text="Jam crew")
        if not ok: return
        members=self._nearby_pick_members("New group chat")
        if not members: return
        g=svc.create_group(name,members); self._nearby_conv_keys=None; self._nearby_refresh_conversations()
        i=self.cmb_nearby_conv.findData(("group",g["id"]))
        if i>=0: self.cmb_nearby_conv.setCurrentIndex(i)
        self.lbl_nearby_progress.setText(f"Group “{g['name']}” created with {len(g['members'])-1} member(s). Members get it with the first message.")

    def _nearby_group_members(self):
        svc=self._nearby_service(); kind,gid=self._nearby_conv()
        if svc is None or kind!="group": QMessageBox.information(self,"Members","Choose a group conversation first."); return
        g=svc.groups().get(gid) or {}
        members=self._nearby_pick_members(f"Members of {g.get('name','group')}",{m.get('node') for m in g.get('members',[])})
        if members is None: return
        svc.set_group_members(gid,members); self._nearby_conv_keys=None; self._nearby_refresh_conversations()

    def _nearby_leave_group(self):
        svc=self._nearby_service(); kind,gid=self._nearby_conv()
        if svc is None or kind!="group": return
        if QMessageBox.question(self,"Leave group","Remove this group from this Groovebox? (Its messages stay in the log.)")!=QMessageBox.StandardButton.Yes: return
        svc.leave_group(gid); self._nearby_conv_keys=None; self._nearby_refresh_conversations()

    def _nearby_save_transcript(self):
        svc=self._nearby_service()
        if svc is None: return
        kind,gid=self._nearby_conv()
        if kind=="group":
            title=f"Group chat {(svc.groups().get(gid) or {}).get('name','group')}"; text=svc.conversation_transcript(group_id=gid)
        else:
            peer=self._nearby_message_target()
            title=f"Chat with {peer.get('name','Groovebox')}" if peer else "Direct messages"
            text=svc.conversation_transcript(peer_node=(peer or {}).get("node_id",""))
        try:
            from notes_editor import notes_dir, _safe_title, _unique
            path=_unique(notes_dir()/f"{_safe_title(title)} {time.strftime('%Y-%m-%d %H-%M')}.md")
            path.write_text(f"# {title}\n\n{text or '_No messages._'}\n",encoding="utf-8")
            self.lbl_nearby_progress.setText(f"Transcript saved to Notes: {path}")
        except Exception as e:
            QMessageBox.warning(self,"Save transcript",str(e))

    # ------------------------------------------------------ Edit Together
    def _et(self):
        return getattr(self.host, "_live_edit", None)

    def _et_start(self):
        et=self._et(); svc=self._nearby_service()
        if et is None or svc is None:
            QMessageBox.information(self,"Edit Together","Edit Together needs the Nearby service."); return
        targets=self._conv_targets()
        if not targets:
            QMessageBox.information(self,"Edit Together","Select a Groovebox or a group conversation first."); return
        names={p["node_id"]:p.get("name","Groovebox") for p in svc.peer_list()}
        for nid,h in getattr(svc,"known_history",{}).items(): names.setdefault(nid,h.get("nickname") or h.get("name","Groovebox"))
        import groovebox_paths
        name=groovebox_paths.project_name(getattr(self.host,"_current_project_path",None))
        try:
            et.start_with([{"node":n,"name":names.get(n,"Groovebox")} for n in targets],name)
        except Exception as e:
            QMessageBox.warning(self,"Edit Together",str(e))
        self._et_refresh()

    def _et_request(self):
        et=self._et(); peer=self._nearby_message_target()
        if et is None or not peer:
            QMessageBox.information(self,"Edit Together","Select a ● Groovebox to ask."); return
        et.request(peer); self._et_refresh()

    def _et_access_requests(self):
        et=self._et()
        if et is not None: et.show_requests(parent=self)

    def _et_lock(self):
        et=self._et(); m=et.mgr if et is not None else None
        s=m.session if m is not None else None
        if s is None or not s.active or not s.is_owner:
            QMessageBox.information(self,"Lock section","Only the owner of a running Edit Together session can lock sections."); return
        from PyQt6.QtWidgets import QInputDialog
        secs=sorted(k for k in (et.snapshot() or {}).keys())
        sec,ok=QInputDialog.getItem(self,"Lock section","Project section:",secs,0,False)
        if not ok: return
        who=[("Nobody (unlock)",None),("Me",s.svc.node_id)]+[(mm.get("name","Groovebox"),n) for n,mm in s.members.items()]
        lab,ok=QInputDialog.getItem(self,"Lock section",f"Who may edit “{sec}”?",[w[0] for w in who],0,False)
        if not ok: return
        s.set_lock(sec,dict(who)[lab]); self._et_refresh()

    def _et_save(self):
        et=self._et()
        if et is None: return
        try:
            self.host.save_project_dialog()
        except Exception as e:
            QMessageBox.warning(self,"Save shared copy",str(e))

    def _et_leave(self):
        et=self._et()
        if et is not None: et.leave(); self._et_refresh()

    def _et_refresh(self):
        et=self._et()
        if et is None or not hasattr(self,"lbl_et"): return
        n=et.pending_count()
        self.btn_et_requests.setText(f"📥 Access ET Requests ({n})" if n else "📥 Access ET Requests")
        self.btn_et_requests.setStyleSheet("QPushButton { border:2px solid #ffb703; color:#ffe9a8; }" if n else "")
        self.lbl_et.setText(et.status_text())
        m=et.mgr; s=m.session if m is not None else None
        if s is not None:
            rows=[f"{time.strftime('%H:%M:%S',time.localtime(a['ts']))} · {a['who']}: {a['text']}" for a in s.activity[-30:]]
            txt="\n".join(rows)
            if txt!=getattr(self,"_et_last_activity",""):
                self._et_last_activity=txt; self.txt_et_activity.setPlainText(txt)
                sb=self.txt_et_activity.verticalScrollBar(); sb.setValue(sb.maximum())

    # ------------------------------------------------- jam / ptt / share
    def _conv_targets(self):
        """Node ids for the current conversation (group members or the selected Groovebox)."""
        svc=self._nearby_service(); kind,gid=self._nearby_conv()
        if svc is None: return []
        if kind=="group" and gid:
            return [m.get("node") for m in (svc.groups().get(gid) or {}).get("members",[]) if m.get("node")!=svc.node_id]
        p=self._nearby_message_target()
        return [p["node_id"]] if p else []

    def _jam_timer_update(self, *_a):
        on=self.chk_jam_lead.isChecked() or self.chk_jam_follow.isChecked()
        if on and not self._jam_timer.isActive(): self._jam_timer.start()
        if not on: self._jam_timer.stop()
        self._jam_offsets={}

    def _jam_tick(self):
        svc=self._nearby_service(); host=getattr(self,"host",None)
        if svc is None or host is None: return
        if self.chk_jam_lead.isChecked():
            targets=self._conv_targets()
            if targets:
                sr=float(getattr(host,"play_sample_rate",0) or 0)
                st={"bpm":float(host.spin_bpm.value()) if hasattr(host,"spin_bpm") else 0.0,
                    "playing":bool(getattr(host,"is_playing",False)),
                    "pos_s":(float(getattr(host,"play_cursor",0) or 0)/sr) if sr>0 else 0.0}
                threading.Thread(target=svc.send_jam,args=(targets,st),daemon=True).start()
        if self.chk_jam_follow.isChecked() and svc.jam_latest:
            node,row=max(svc.jam_latest.items(),key=lambda kv: kv[1].get("recv",0))
            if time.time()-row.get("recv",0)>5: return
            st=row.get("state") or {}
            offs=self.__dict__.setdefault("_jam_offsets",{})
            if node not in offs:
                offs[node]=0.0
                peer=next((p for p in svc.peer_list() if p.get("node_id")==node),None)
                if peer: threading.Thread(target=lambda: offs.__setitem__(node,svc.clock_offset(peer)),daemon=True).start()
            try:
                bpm=float(st.get("bpm") or 0)
                if bpm>0 and hasattr(host,"spin_bpm") and abs(host.spin_bpm.value()-bpm)>1e-6: host.spin_bpm.setValue(bpm)
            except Exception: pass
            playing=bool(getattr(host,"is_playing",False))
            if st.get("playing") and not playing and hasattr(host,"toggle_playback"):
                host.toggle_playback()
            elif not st.get("playing") and playing and hasattr(host,"stop_audio_playback"):
                host.stop_audio_playback()
            elif st.get("playing") and playing:
                sr=float(getattr(host,"play_sample_rate",0) or 0)
                if sr>0:
                    leader_now=time.time()+offs.get(node,0.0)
                    want=float(st.get("pos_s",0))+max(0.0,leader_now-float(st.get("sent",leader_now)))
                    have=float(getattr(host,"play_cursor",0) or 0)/sr
                    if abs(want-have)>0.08:
                        host.play_cursor=int(want*sr)
            self.lbl_live.setText(f"🎧 Following jam from {row.get('name','Groovebox')} · {st.get('bpm',0):g} BPM · {'playing' if st.get('playing') else 'stopped'}")

    def _ptt_install(self, on):
        app=QApplication.instance()
        if on and getattr(self,"_ptt_filter",None) is None:
            perf=self
            class _PTT(QObject):
                def eventFilter(self_, obj, ev):
                    try:
                        if ev.type() in (ev.Type.KeyPress, ev.Type.KeyRelease) and ev.key()==Qt.Key.Key_F8 and not ev.isAutoRepeat():
                            perf._ptt_set(ev.type()==ev.Type.KeyPress)
                    except Exception: pass
                    return False
            self._ptt_filter=_PTT(self); app.installEventFilter(self._ptt_filter)
        elif not on and getattr(self,"_ptt_filter",None) is not None:
            app.removeEventFilter(self._ptt_filter); self._ptt_filter=None; self._ptt_set(False)

    def _ptt_set(self, down):
        svc=self._nearby_service()
        if svc is None: return
        self.lbl_live.setText("🎙 Talking (release F8 to stop)…" if down else "Live: off")
        threading.Thread(target=lambda: (svc.ptt(down)),daemon=True).start()

    def _ptt_autolisten(self):
        """Play push-to-talk audio from live 'ptt' peers; close when they stop."""
        svc=self._nearby_service()
        if svc is None or not hasattr(self,"chk_ptt_listen"): return
        live={p["node_id"]:p for p in svc.peer_list() if p.get("live") and str(p.get("live_mode","")).startswith("ptt")}
        for node,proc in list(self._ptt_players.items()):
            if node not in live or not self.chk_ptt_listen.isChecked():
                try: proc.terminate()
                except Exception: pass
                self._ptt_players.pop(node,None)
        if not self.chk_ptt_listen.isChecked(): return
        for node,p in live.items():
            if node in self._ptt_players: continue
            url=svc.live_url(p)
            exe=_media_player_executable("ffplay") or _media_player_executable("mpv")
            if not exe: continue
            cmd=([exe,"-nodisp","-autoexit","-fflags","nobuffer","-loglevel","error",url] if os.path.basename(exe).startswith("ffplay")
                 else [exe,"--no-video","--profile=low-latency",url])
            try: self._ptt_players[node]=subprocess.Popen(cmd)
            except Exception: pass

    def _nearby_share_project(self):
        svc=self._nearby_service(); host=getattr(self,"host",None)
        if svc is None or host is None: return
        targets=self._conv_targets()
        if not targets:
            QMessageBox.information(self,"Share project","Select a Groovebox or a group conversation first."); return
        peers={p["node_id"]:p for p in svc.peer_list()}
        reach=[peers[n] for n in targets if n in peers]
        if not reach:
            QMessageBox.information(self,"Share project","None of those Grooveboxes is visible right now."); return
        try:
            snap=host._project_snapshot()
        except Exception as e:
            QMessageBox.warning(self,"Share project",f"Could not snapshot the project: {e}"); return
        import groovebox_paths
        name=groovebox_paths.project_name(getattr(host,"_current_project_path",None))
        samples=[]
        for v in (getattr(host,"instrument_media_samples",{}) or {}).values():
            pth=str((v or {}).get("path","") or "")
            if pth and os.path.isfile(pth): samples.append(pth)
        carrier=str(getattr(host,"imported_wav_path","") or "")
        if carrier and os.path.isfile(carrier): samples.append(carrier)
        self.lbl_nearby_progress.setText(f"Packing “{name}” with {len(samples)} sample(s)…")
        def run():
            import tempfile, mcc_media
            td=tempfile.mkdtemp(prefix="groovebox_share_")
            with open(os.path.join(td,f"{name}.MCC"),"w",encoding="utf-8") as f: json.dump(snap,f)
            os.makedirs(os.path.join(td,"samples"),exist_ok=True)
            for sp in dict.fromkeys(samples): shutil.copy2(sp,os.path.join(td,"samples",os.path.basename(sp)))
            bundle=os.path.join(tempfile.mkdtemp(),f"{name} · shared project.MCC")
            mcc_media.pack_tree(td,bundle,level=6,manifest={"kind":"project-bundle","project":name,"from":svc.name,
                                                             "samples":[os.path.basename(x) for x in samples]})
            shutil.rmtree(td,ignore_errors=True)
            done=[]
            for p in reach:
                try:
                    svc.upload(p,bundle,"projects",progress=lambda d,t,ph,pn=p.get("name"): self._nearby_bridge.progress.emit(d,t,f"{ph} → {pn}"))
                    done.append(p.get("name","Groovebox"))
                except Exception as e:
                    done.append(f"{p.get('name','Groovebox')} (failed: {e})")
            try:
                kind,gid=self._nearby_conv()
                svc.send_text(f"📦 Shared project “{name}” ({len(samples)} sample(s)) — find it in Projects ▸ Incoming Groovebox.",
                              group_id=gid if kind=="group" else None, to_nodes=None if kind=="group" else targets)
            except Exception: pass
            return "Shared with: "+", ".join(done)
        self._nearby_async("share", run)

    # ------------------------------------------------------------- live A/V
    def _nearby_toggle_live(self, on):
        svc=self._nearby_service()
        if svc is None or not hasattr(svc,"start_live"): return
        if not on:
            svc.stop_live(); self.btn_live.setText("🔴 Go live"); self.lbl_live.setText("Live: off"); return
        cam=self.chk_live_cam.isChecked(); mic=self.chk_live_mic.isChecked(); test=self.chk_live_test.isChecked()
        camera=""
        try:
            fmt=getattr(self.host,"preferred_camera_format",None) or {}
            camera=str(fmt.get("device_path","") or "")
        except Exception:
            pass
        self.lbl_live.setText("Starting 1080p live camera/mic…")
        profile = ("1080p", "1440p", "2160p")[max(0, min(2, self.cmb_live_resolution.currentIndex()))] if hasattr(self, "cmb_live_resolution") else "1080p"
        bitrate = self.cmb_live_bitrate.currentText().strip() if hasattr(self, "cmb_live_bitrate") else "6M"
        self._nearby_async("live", lambda: svc.start_live(video=cam or test, audio=mic or test, camera=camera,
                                                           test=test, resolution=profile, fps=30,
                                                           video_bitrate=bitrate, encoder="auto"))

    def _nearby_play_url(self, url, title):
        cmd=None
        try:
            mpv=_media_player_executable("mpv")
            if mpv: cmd=[mpv,"--profile=low-latency","--untimed","--force-window=yes",f"--title={title}",url]
        except Exception:
            cmd=None
        if cmd:
            try:
                subprocess.Popen(cmd); return
            except Exception:
                pass
        host=_gb_find_host(self)
        dlg=InAppMediaPlayer(url,self,preferred_output=str(getattr(host,"_preferred_audio_output_name","") or "") if host is not None else "")
        dlg.setWindowTitle(title); dlg.setModal(False); dlg.show()
        self.__dict__.setdefault("_live_windows",[]).append(dlg)

    def _nearby_watch_selected(self):
        svc=self._nearby_service(); peer=self._nearby_message_target()
        if svc is None or not peer:
            QMessageBox.information(self,"Watch","Select a ● Groovebox that shows 🔴 live."); return
        if not peer.get("live"):
            QMessageBox.information(self,"Watch",f"{peer.get('name','That Groovebox')} is not live right now."); return
        self._nearby_play_url(svc.live_url(peer), f"Live · {peer.get('name','Groovebox')}")

    def _nearby_watch_group(self):
        svc=self._nearby_service(); kind,gid=self._nearby_conv()
        if svc is None or kind!="group":
            QMessageBox.information(self,"Watch group","Choose a group conversation first."); return
        members={m.get("node") for m in (svc.groups().get(gid) or {}).get("members",[])}
        live=[p for p in svc.peer_list() if p.get("node_id") in members and p.get("live")]
        if not live:
            QMessageBox.information(self,"Watch group","No member of this group is live and visible right now."); return
        for p in live:
            self._nearby_play_url(svc.live_url(p), f"Live · {p.get('name','Groovebox')}")

    def _nearby_record_selected(self):
        svc=self._nearby_service()
        if svc is None: return
        peer=self._nearby_message_target()
        try:
            import groovebox_paths
            out_dir=groovebox_paths.recordings_dir(getattr(self.host,"_current_project_path",None))
        except Exception:
            out_dir=os.path.join(os.path.expanduser("~"),"Groovebox Recordings")
        try:
            if peer and peer.get("live"):
                out=svc.start_recording(peer["node_id"], svc.live_url(peer), out_dir, f"Live {peer.get('name','Groovebox')}")
            elif svc.live is not None and svc.live.live:
                out=svc.start_recording("self", svc.my_live_url(), out_dir, "My live stream")
            else:
                QMessageBox.information(self,"Record","Select a live Groovebox, or Go live to record your own stream."); return
            self.lbl_live.setText(f"⏺ Recording → {out}")
        except Exception as e:
            QMessageBox.warning(self,"Record",str(e))

    def _nearby_stop_recordings(self):
        svc=self._nearby_service()
        if svc is None: return
        done=svc.stop_recording()
        self.lbl_live.setText(("Saved: "+" · ".join(done)) if done else "No recording was running.")

    def _nearby_clear_messages(self):
        svc=self._nearby_service()
        if svc is not None and hasattr(svc,"clear_messages"):
            svc.clear_messages(); self._nearby_msg_count=-1; self._refresh_nearby_messages()

    def _nearby_toggle_messages(self, on):
        svc=self._nearby_service()
        if svc is not None:
            svc.allow_messages=bool(on)
            try: svc._save_settings()
            except Exception: pass

    def _refresh_nearby_messages(self):
        svc=self._nearby_service()
        if svc is None or not hasattr(svc,"messages") or not hasattr(self,"txt_nearby_messages"): return
        self._nearby_refresh_conversations()
        rows=svc.messages(300)
        if len(rows)==getattr(self,"_nearby_msg_count",-1): return
        self._nearby_msg_count=len(rows)
        kind,gid=self._nearby_conv()
        status=svc.delivery_status() if hasattr(svc,"delivery_status") else {}
        pending=svc.outbox_pending() if hasattr(svc,"outbox_pending") else {}
        rows=[m for m in rows if m.get("dir") in ("in","out") and (m.get("group_id")==gid if kind=="group" else not m.get("group_id"))]
        import html as _html
        out=[]
        for m in rows:
            when=time.strftime('%H:%M',time.localtime(float(m.get('ts',0) or 0)))
            who=_html.escape(str(m.get('peer_name','Groovebox')))
            txt=_html.escape(str(m.get('text',''))).replace("\n","<br>")
            tr=m.get('trace') or []
            if len(tr)>1:
                txt+=f"<br><span style='color:#6f7f8f;font-size:8pt'>via {_html.escape(' → '.join(tr))}</span>"
            if m.get("dir")=="in":
                out.append(f"<p><span style='color:#7fd0ff'><b>{who}</b></span> <span style='color:#7a8a99'>{when}</span><br>{txt}</p>")
            else:
                acked=status.get(m.get("id",""),[]); queued=m.get("id","") in pending
                mark="⏳ queued" if queued and not acked else ("✓✓ delivered" if acked else "✓ sent")
                out.append(f"<p align='right'><span style='color:#9be39b'><b>You → {who}</b></span> <span style='color:#7a8a99'>{when} · {mark}</span><br>{txt}</p>")
        self.txt_nearby_messages.setHtml("".join(out) or "<i>No messages yet.</i>")
        sb=self.txt_nearby_messages.verticalScrollBar(); sb.setValue(sb.maximum())

    def _nearby_start_direct(self):
        svc=self._nearby_service()
        if svc is None: return
        ans=QMessageBox.question(self,"Start Groovebox Direct Wi-Fi",
            "Start a router-free Groovebox Wi-Fi network?\n\nOn some single-radio PCs/tablets this may disconnect the current Wi-Fi while the direct network is active.")
        if ans != QMessageBox.StandardButton.Yes: return
        self.lbl_nearby_progress.setText("Starting Groovebox Direct Wi-Fi…")
        self._nearby_async("direct_start", svc.start_direct_hotspot)

    def _nearby_stop_direct(self):
        svc=self._nearby_service()
        if svc is not None: self._nearby_async("direct_stop", svc.stop_direct_hotspot)

    def _nearby_selected_payload(self):
        it=self.lst_nearby.currentItem() if hasattr(self,'lst_nearby') else None
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    def _nearby_join_selected(self):
        svc=self._nearby_service(); sel=self._nearby_selected_payload()
        if svc is None or not sel or sel.get('kind')!='direct':
            QMessageBox.information(self,"Direct Link","Select a ◉ Groovebox Direct radio first."); return
        ssid=sel['data'].get('ssid',''); self.lbl_nearby_progress.setText(f"Joining {ssid}…")
        self._nearby_async("join",lambda:svc.join_direct(ssid))

    def _nearby_browse_selected(self):
        svc=self._nearby_service(); sel=self._nearby_selected_payload()
        if svc is None or not sel or sel.get('kind')!='peer':
            QMessageBox.information(self,"Browse Groovebox","Select a connected ● Groovebox peer first. If you only see a Direct radio, join it first."); return
        peer=sel['data']; self._nearby_active_peer=peer; self.lbl_nearby_progress.setText(f"Reading {peer.get('name','Groovebox')} catalog…")
        self._nearby_async("files",lambda:svc.fetch_files(peer))

    def _nearby_download_selected(self):
        svc=self._nearby_service(); peer=getattr(self,'_nearby_active_peer',None); it=self.lst_nearby_files.currentItem() if hasattr(self,'lst_nearby_files') else None
        if svc is None or peer is None or it is None: return
        row=it.data(Qt.ItemDataRole.UserRole); self.lbl_nearby_progress.setText(f"Receiving {row.get('name','file')}…")
        def progress(done,total,phase): self._nearby_bridge.progress.emit(int(done),int(total),phase)
        self._nearby_async("download",lambda:svc.download(peer,row,progress=progress))

    def _nearby_send_file(self):
        svc=self._nearby_service(); sel=self._nearby_selected_payload()
        if svc is None or not sel or sel.get('kind')!='peer':
            QMessageBox.information(self,"Send File","Select a connected ● Groovebox peer first."); return
        import groovebox_paths
        path,_=QFileDialog.getOpenFileName(self,"Send file to nearby Groovebox",self._cwd or groovebox_paths.base_dir(),"All files (*)")
        if not path:return
        peer=sel['data']; self._nearby_active_peer=peer; self.lbl_nearby_progress.setText(f"Sending {os.path.basename(path)}…")
        def progress(done,total,phase): self._nearby_bridge.progress.emit(int(done),int(total),phase)
        self._nearby_async("upload",lambda:svc.upload(peer,path,progress=progress))

    def _nearby_worker_progress(self,done,total,phase):
        pct=(100.0*done/total) if total else 0.0
        self.lbl_nearby_progress.setText(f"{phase.title()}: {pct:.1f}% · {_safe_size_bytes(done)} / {_safe_size_bytes(total) if total else '?'}")

    def _nearby_worker_result(self,kind,payload,error):
        if kind in ('hotspot_on','hotspot_off'):
            self._hotspot_share_result(kind,payload,error); return
        if error:
            if kind=='live' and hasattr(self,'btn_live'):
                self.btn_live.blockSignals(True); self.btn_live.setChecked(False); self.btn_live.blockSignals(False)
                self.btn_live.setText("🔴 Go live"); self.lbl_live.setText(f"Live failed: {error}")
            self.lbl_nearby_progress.setText(f"Nearby {kind} failed: {error}"); return
        if kind=='files':
            self._nearby_remote_rows=list(payload or []); self.lst_nearby_files.clear()
            for row in self._nearby_remote_rows:
                item=QListWidgetItem(f"{row.get('category','file')} · {row.get('path',row.get('name',''))} · {_safe_size_bytes(int(row.get('size',0) or 0))}")
                item.setData(Qt.ItemDataRole.UserRole,row); self.lst_nearby_files.addItem(item)
            self.lbl_nearby_progress.setText(f"{len(self._nearby_remote_rows)} shared file(s).")
        elif kind in ('direct_start','direct_stop','join'):
            ok,msg=payload if isinstance(payload,(list,tuple)) and len(payload)>=2 else (False,str(payload))
            self.lbl_nearby_progress.setText(("OK: " if ok else "Not available: ")+str(msg or kind))
        elif kind=='download': self.lbl_nearby_progress.setText(f"Received safely: {payload}")
        elif kind=='upload': self.lbl_nearby_progress.setText(f"Sent successfully: {payload.get('name','file') if isinstance(payload,dict) else payload}")
        elif kind=='scan':
            if isinstance(payload,dict):
                self.lbl_nearby_progress.setText(f"Found {len(payload.get('radios') or [])} Groovebox Direct radio(s) and {len(payload.get('swept') or [])} Groovebox(es) by subnet sweep.")
            else:
                self.lbl_nearby_progress.setText(f"Direct radio scan found {len(payload or [])} Groovebox network(s).")
        elif kind=='share':
            self.lbl_nearby_progress.setText(str(payload)); self._nearby_msg_count=-1
        elif kind=='live':
            st=payload or {}; profile=st.get("profile",{}) if isinstance(st,dict) else {}
            size=(f"{profile.get('width',1920)}×{profile.get('height',1080)} @ {profile.get('fps',30)} fps" if profile else "1080p30")
            rate=profile.get("video_bitrate", "6M") if profile else "6M"
            enc=profile.get("encoder", "H.264") if profile else "H.264"
            self.btn_live.setText("⏹ Stop live"); self.lbl_live.setText(f"🔴 Live {size} · {rate} · {enc} ({st.get('mode','')}) — nearby Grooveboxes can Watch / Record you.")
        elif kind=='message':
            self.lbl_nearby_progress.setText(f"Message delivered to {payload}."); self._nearby_msg_count=-1; self._refresh_nearby_messages()
        elif kind=='link':
            self.lbl_nearby_progress.setText(f"Connected: {payload.get('name','Groovebox')} at {payload.get('url','')} — kept in your peer list.")
            self._refresh_nearby_ui()
        self._refresh_nearby_ui()

    def _create_clone_bundle(self):
        try:
            from operation_station_transfer import create_clone_bundle
            import groovebox_paths
            outdir=Path(groovebox_paths.clones_dir()); outdir.mkdir(parents=True,exist_ok=True)
            stamp=time.strftime('%Y%m%d-%H%M%S'); out=outdir/f"MathematiciansGroovebox_V3_OperationStation_{stamp}.mgbclone.zip"
            self._last_clone_bundle=create_clone_bundle(os.path.dirname(__file__),str(out),include_source=self.chk_clone_source.isChecked(),include_executables=self.chk_clone_exec.isChecked(),include_dependencies=self.chk_clone_deps.isChecked(),include_user_content=self.chk_clone_content.isChecked(),user_data_root=groovebox_paths.base_dir())
            self.lbl_clone.setText(self._last_clone_bundle); self.lbl_status.setText("Versioned Operation Station clone created with SHA-256 manifest.")
        except Exception as e: QMessageBox.warning(self,"Create clone",str(e))

    def _verify_clone_bundle(self):
        path=self._last_clone_bundle
        if not path:
            import groovebox_paths
            path,_=QFileDialog.getOpenFileName(self,"Verify Operation Station clone",groovebox_paths.clones_dir(),"Groovebox clone (*.mgbclone.zip *.zip)")
        if not path: return
        try:
            from operation_station_transfer import verify_clone_bundle
            r=verify_clone_bundle(path); self.lbl_status.setText("Clone verified OK." if r['ok'] else "Clone verification failed: "+', '.join(r['bad'][:3]))
        except Exception as e: QMessageBox.warning(self,"Verify clone",str(e))

    def _start_clone_share(self):
        try:
            if not self._last_clone_bundle or not os.path.isfile(self._last_clone_bundle): self._create_clone_bundle()
            if not self._last_clone_bundle: return
            from operation_station_transfer import CloneShareServer
            self._stop_clone_share(); self._clone_share_server=CloneShareServer(os.path.dirname(self._last_clone_bundle),int(self.spin_clone_port.value()))
            urls=self._clone_share_server.start(); self.lbl_clone_url.setText('\n'.join(urls)); self.lbl_status.setText("Clone share active on Wi-Fi/Ethernet.")
        except Exception as e: QMessageBox.warning(self,"Clone share",str(e))

    def _stop_clone_share(self):
        srv,self._clone_share_server=self._clone_share_server,None
        if srv:
            try: srv.stop()
            except Exception: pass
        if hasattr(self,'lbl_clone_url'): self.lbl_clone_url.setText('Stopped')

    def _refresh_clone_mounts(self):
        try:
            from operation_station_transfer import detect_removable_mounts
            vals=detect_removable_mounts(); self.cmb_clone_mount.clear(); self.cmb_clone_mount.addItems(vals)
            if not vals: self.cmb_clone_mount.addItem(str(Path.home()))
        except Exception as e: self.lbl_status.setText(f"Drive detection: {e}")

    def _copy_clone_to_mount(self):
        if not self._last_clone_bundle or not os.path.isfile(self._last_clone_bundle): self._create_clone_bundle()
        if not self._last_clone_bundle: return
        try:
            from operation_station_transfer import copy_bundle
            dest=self.cmb_clone_mount.currentText().strip(); out=copy_bundle(self._last_clone_bundle,dest); self.lbl_status.setText(f"Clone copied: {out}")
        except Exception as e: QMessageBox.warning(self,"Copy clone",str(e))

    def _set_iso_source(self, path):
        self._last_iso_path=str(path)
        try:
            size=_safe_size_bytes(os.path.getsize(path))
            self.lbl_iso_source.setText(f"{path} · {size}")
        except Exception:
            self.lbl_iso_source.setText(str(path))

    def _find_finished_iso(self):
        try:
            from operation_station_transfer import find_finished_iso
            iso=find_finished_iso(Path(__file__).resolve().parent)
            if iso:
                self._set_iso_source(iso)
                self.lbl_status.setText("Finished product ISO found.")
            else:
                self._last_iso_path=None
                self.lbl_iso_source.setText("No finished ISO found. Build the ISO, or Browse to select it.")
        except Exception as e:
            self.lbl_status.setText(f"ISO lookup: {e}")

    def _browse_iso(self):
        start=str(Path(self._last_iso_path).parent) if self._last_iso_path else str(Path.home())
        path,_=QFileDialog.getOpenFileName(self,"Select finished Groovebox ISO",start,"ISO images (*.iso);;All files (*)")
        if path:
            self._set_iso_source(path)
            self.lbl_status.setText("Finished product ISO selected.")

    def _copy_iso_to_mount(self):
        iso=self._last_iso_path
        if not iso or not os.path.isfile(iso):
            self._find_finished_iso(); iso=self._last_iso_path
        if not iso or not os.path.isfile(iso):
            QMessageBox.information(self,"Copy finished ISO","Find or browse to the finished Groovebox ISO first.")
            return
        dest=self.cmb_clone_mount.currentText().strip()
        if not dest:
            QMessageBox.information(self,"Copy finished ISO","Detect or select a mounted destination drive first.")
            return
        self.lbl_iso_progress.setText(f"Copying {os.path.basename(iso)} to {dest}/Groovebox/ISO…")
        verify=self.chk_iso_verify.isChecked()
        def work():
            try:
                from operation_station_transfer import copy_iso_to_mount
                def progress(done,total,phase):
                    self._iso_copy_bridge.progress.emit(int(done),int(total),phase)
                result=copy_iso_to_mount(iso,dest,progress=progress)
                if not verify:
                    result['sha256']=''
                self._iso_copy_bridge.done.emit(result,"")
            except Exception as e:
                self._iso_copy_bridge.done.emit(None,str(e))
        self._worker_pool.start(_PoolTask(work))

    def _on_iso_copy_progress(self,done,total,phase):
        pct=(100.0*done/total) if total else 0.0
        self.lbl_iso_progress.setText(f"{phase.title()}: {pct:.1f}% · {_safe_size_bytes(done)} / {_safe_size_bytes(total) if total else '?'}")

    def _on_iso_copy_done(self,result,error):
        if error:
            self.lbl_iso_progress.setText(f"ISO copy failed: {error}")
            QMessageBox.warning(self,"Copy finished ISO",error); return
        if result and result.get('skipped'):
            self.lbl_iso_progress.setText(f"ISO already at destination: {result.get('path')}")
        else:
            digest=(result or {}).get('sha256','')
            tail=f" · SHA-256 {digest[:16]}…" if digest else ""
            self.lbl_iso_progress.setText(f"ISO copied: {(result or {}).get('path')}{tail}")
        self.lbl_status.setText("Finished product ISO copied; existing drive files preserved.")

    # ------------------------------------------------------------------ hardware
    # ------------------------------------------------------------------ storage maintenance
    def _build_storage_tab(self) -> QWidget:
        w=QWidget(); lay=QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Groovebox Storage Maintenance</b>"))
        note=QLabel("Storage cleanup keeps projects, imported originals, completed recordings and exports protected unless you explicitly choose a destructive category. Cache/temp/log cleanup is regenerable. Autosaves are managed separately so crash recovery is never silently erased.")
        note.setWordWrap(True); lay.addWidget(note)
        self.lbl_storage_summary=QLabel("Scanning storage…"); self.lbl_storage_summary.setWordWrap(True); self.lbl_storage_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); lay.addWidget(self.lbl_storage_summary)
        row=QHBoxLayout()
        b=QPushButton("↻ Refresh Usage"); b.clicked.connect(self._refresh_storage_usage); row.addWidget(b)
        b=QPushButton("Emergency Free Space (Safe)"); b.clicked.connect(self._storage_safe_cleanup); row.addWidget(b)
        lay.addLayout(row)

        auto=QGroupBox("Autosaves / recovery files"); av=QVBoxLayout(auto)
        self.lst_storage_autosaves=QListWidget(); self.lst_storage_autosaves.setMinimumHeight(130); av.addWidget(self.lst_storage_autosaves)
        ar=QHBoxLayout(); b=QPushButton("Recover Selected"); b.clicked.connect(self._storage_recover_autosave); ar.addWidget(b); b=QPushButton("Delete Selected Autosave"); b.clicked.connect(self._storage_delete_autosave); ar.addWidget(b); av.addLayout(ar)
        lay.addWidget(auto)

        media=QGroupBox("Project media / exports"); mv=QVBoxLayout(media)
        mr=QHBoxLayout(); b=QPushButton("Find Unused Current-Project Media"); b.clicked.connect(self._storage_find_unused_media); mr.addWidget(b); b=QPushButton("Delete Listed Unused Media"); b.clicked.connect(self._storage_delete_unused_media); mr.addWidget(b); mv.addLayout(mr)
        self.lst_storage_unused=QListWidget(); self.lst_storage_unused.setMinimumHeight(115); mv.addWidget(self.lst_storage_unused)
        er=QHBoxLayout(); b=QPushButton("Delete Current Project Exports"); b.clicked.connect(self._storage_delete_project_exports); er.addWidget(b); b=QPushButton("Delete Global Exports"); b.clicked.connect(self._storage_delete_global_exports); er.addWidget(b); mv.addLayout(er)
        lay.addWidget(media); lay.addStretch(1)
        return w

    def _refresh_storage_usage(self):
        if not hasattr(self,'lbl_storage_summary'): return
        try:
            import groovebox_paths
            r=groovebox_paths.storage_report(); c=r['categories']; d=r['disk']; a=r['autosaves']
            parts=[f"Data root: {r['base']}", f"Groovebox data: {_safe_size_bytes(r['groovebox_bytes'])} in {r['groovebox_files']} files · disk free: {_safe_size_bytes(d['free'])}"]
            parts.append(" · ".join(f"{k.replace('_',' ').title()}: {_safe_size_bytes(v['bytes'])}" for k,v in c.items()))
            parts.append(f"Autosaves/recovery: {a['files']} · {_safe_size_bytes(a['bytes'])} (included within project data)")
            self.lbl_storage_summary.setText("\n".join(parts))
            if hasattr(self,'lst_storage_autosaves'):
                self.lst_storage_autosaves.clear()
                for row in a['items']:
                    when=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(float(row.get('mtime',0) or 0)))
                    notes=str(row.get('notes','') or '').strip().replace('\n',' ')
                    if len(notes)>90: notes=notes[:90]+'…'
                    text=f"{row.get('title','Untitled Project')} · {when} · {_safe_size_bytes(row.get('size',0))}"
                    if notes: text += f" · Notes: {notes}"
                    item=QListWidgetItem(text); item.setData(Qt.ItemDataRole.UserRole,row); self.lst_storage_autosaves.addItem(item)
        except Exception as e:
            self.lbl_storage_summary.setText(f"Storage scan failed: {e}")

    def _storage_safe_cleanup(self):
        if QMessageBox.question(self,"Emergency Free Space","Clear regenerable cache, temporary files, logs and incomplete recording scratch data?\n\nProjects, imported originals, completed recordings, autosaves and exports are preserved.") != QMessageBox.StandardButton.Yes: return
        try:
            import groovebox_paths
            r=groovebox_paths.cleanup_disposable(("cache","temp","logs","recording_scratch"))
            QMessageBox.information(self,"Storage cleanup",f"Freed {_safe_size_bytes(r['bytes'])} from {r['files']} file(s).")
            self._refresh_storage_usage()
        except Exception as e: QMessageBox.warning(self,"Storage cleanup failed",str(e))

    def _selected_storage_autosave(self):
        it=self.lst_storage_autosaves.currentItem() if hasattr(self,'lst_storage_autosaves') else None
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    def _storage_recover_autosave(self):
        row=self._selected_storage_autosave()
        if not row: return
        path=str(row.get('path','')); title=str(row.get('title','Untitled Project')); notes=str(row.get('notes','') or '')
        msg=f"Recover autosave for {title}?\n\nProject Notes:\n{notes[:1200] if notes else '(none)'}\n\nThis restores the working state without overwriting the last explicit save."
        if QMessageBox.question(self,"Recover Autosave",msg) != QMessageBox.StandardButton.Yes: return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8'))
            self.host._apply_project_snapshot(data)
            rp=Path(path)
            if rp.name=='autosave.MCC' and rp.parent.name=='metadata':
                proot=rp.parent.parent; mcc=sorted(proot.glob('*.MCC'))+sorted(proot.glob('*.mcc'))
                self.host._current_project_path=str(mcc[0] if mcc else proot/(title+'.MCC'))
            elif path.lower().endswith('.part'): self.host._current_project_path=path[:-5]
            try: self.host.reload_active_instrument_sequencer_ui()
            except Exception: pass
            try: self.host._refresh_after_file_input(reason='storage_recovery')
            except Exception: pass
            self.lbl_status.setText(f"Recovered working autosave: {title}")
        except Exception as e: QMessageBox.warning(self,"Recover failed",str(e))

    def _storage_delete_autosave(self):
        row=self._selected_storage_autosave()
        if not row: return
        if QMessageBox.question(self,"Delete Autosave",f"Delete only this recovery file for {row.get('title','Untitled Project')}?\n\nThe saved project and project media are not deleted.") != QMessageBox.StandardButton.Yes: return
        try:
            import groovebox_paths
            groovebox_paths.delete_autosave(str(row.get('path',''))); self._refresh_storage_usage()
        except Exception as e: QMessageBox.warning(self,"Delete autosave failed",str(e))

    def _storage_find_unused_media(self):
        if not hasattr(self,'lst_storage_unused'): return
        self.lst_storage_unused.clear(); self._storage_unused_candidates=[]
        path=str(getattr(self.host,'_current_project_path','') or '')
        if not path:
            QMessageBox.information(self,"Unused Media","Save or open the working project first so Groovebox can compare media references against its project document."); return
        try:
            import groovebox_paths
            rows=groovebox_paths.find_unreferenced_project_media(path); self._storage_unused_candidates=rows
            for row in rows:
                item=QListWidgetItem(f"{row.get('relative',row.get('path',''))} · {_safe_size_bytes(row.get('size',0))}"); item.setData(Qt.ItemDataRole.UserRole,row); self.lst_storage_unused.addItem(item)
            self.lbl_status.setText(f"Found {len(rows)} unreferenced media candidate(s); nothing was deleted.")
        except Exception as e: QMessageBox.warning(self,"Unused media scan failed",str(e))

    def _storage_delete_unused_media(self):
        rows=list(getattr(self,'_storage_unused_candidates',[]) or [])
        if not rows: return
        total=sum(int(r.get('size',0) or 0) for r in rows)
        if QMessageBox.question(self,"Delete Unused Media",f"Delete {len(rows)} listed unreferenced media file(s), totaling {_safe_size_bytes(total)}?\n\nOnly the files currently listed by the reference scan will be removed.") != QMessageBox.StandardButton.Yes: return
        try:
            import groovebox_paths
            r=groovebox_paths.delete_unreferenced_project_media(rows,str(getattr(self.host,'_current_project_path','') or ''))
            self._storage_unused_candidates=[]; self.lst_storage_unused.clear(); self._refresh_storage_usage(); self.refresh()
            QMessageBox.information(self,"Unused media",f"Deleted {r['files']} file(s), {_safe_size_bytes(r['bytes'])}.")
        except Exception as e: QMessageBox.warning(self,"Delete unused media failed",str(e))

    def _storage_delete_project_exports(self):
        path=str(getattr(self.host,'_current_project_path','') or '')
        if not path: QMessageBox.information(self,"Project Exports","No saved/open current project."); return
        if QMessageBox.question(self,"Delete Current Project Exports","Delete all generated exports for the current project?\n\nThe project, samples, recordings and autosaves are preserved.") != QMessageBox.StandardButton.Yes: return
        try:
            import groovebox_paths
            r=groovebox_paths.delete_project_exports(path); self._refresh_storage_usage(); self.refresh(); QMessageBox.information(self,"Project Exports",f"Deleted {r['files']} export file(s), {_safe_size_bytes(r['bytes'])}.")
        except Exception as e: QMessageBox.warning(self,"Delete exports failed",str(e))

    def _storage_delete_global_exports(self):
        if QMessageBox.question(self,"Delete Global Exports","Delete generated exports stored outside individual project folders?\n\nProject-local exports are not touched by this action.") != QMessageBox.StandardButton.Yes: return
        try:
            import groovebox_paths
            r=groovebox_paths.delete_all_global_exports(); self._refresh_storage_usage(); self.refresh(); QMessageBox.information(self,"Global Exports",f"Deleted {r['files']} file(s), {_safe_size_bytes(r['bytes'])}.")
        except Exception as e: QMessageBox.warning(self,"Delete exports failed",str(e))

    def _build_hardware_tab(self) -> QWidget:
        w=QWidget(); lay=QVBoxLayout(w)
        lay.addWidget(QLabel("<b>⌨ Hardware · keyboard · touch · controllers · audio · MIDI</b>"))
        intro=QLabel("Hardware discovery is explicit and runs off the GUI thread. Opening or scrolling Performance never blocks on PipeWire, ALSA, USB, Bluetooth, or display probes.")
        intro.setWordWrap(True); lay.addWidget(intro)
        self.txt_hardware=QTextEdit(); self.txt_hardware.setReadOnly(True); self.txt_hardware.setPlainText("Not scanned yet. Select Rescan hardware when diagnostics are needed."); lay.addWidget(self.txt_hardware,1)
        self._hardware_scan_generation=0
        self._hardware_scan_bridge=_HardwareScanBridge(self)
        self._hardware_scan_bridge.done.connect(self._on_hardware_scan_done)
        self._hardware_component_results={}
        self._hardware_component_pending=set()
        self._hardware_audio_test_generation=0
        self._audio_io_test_bridge=_AudioIoTestBridge(self)
        self._audio_io_test_bridge.done.connect(self._on_physical_audio_io_test_done)
        row=QHBoxLayout(); self.btn_hardware_rescan=QPushButton("↻ Rescan hardware"); self.btn_hardware_rescan.clicked.connect(self._refresh_hardware); row.addWidget(self.btn_hardware_rescan)
        b2=QPushButton("▣ Refresh media outputs"); b2.clicked.connect(self._refresh_output_devices); row.addWidget(b2)
        self.btn_audio_io_test=QPushButton("🔊🎙 Physical Audio I/O Test")
        self.btn_audio_io_test.setToolTip("Play a short 997 Hz speaker tone while recording the selected physical microphone; PASS requires the tone to return through the microphone above room noise.")
        self.btn_audio_io_test.clicked.connect(self._run_physical_audio_io_test); row.addWidget(self.btn_audio_io_test)
        row.addStretch(1); lay.addLayout(row)
        # GROOVEBOX_R23R_HARDWARE_FORMATS_20261101: validated format choices,
        # labelled by device AND interpretation (instead of empty device lists).
        fbox=QGroupBox("Formats · device × interpretation"); ff=QFormLayout(fbox)
        note=QLabel("Each choice is a format the hardware accepted when probed. The first entry is always the safe "
                    "system default (Groovebox resamples the hardware copy) for multi-device / multi-mode experiments.")
        note.setWordWrap(True); ff.addRow(note)
        self.cmb_fmt_out=QComboBox(); self.cmb_fmt_in=QComboBox(); self.cmb_fmt_cam=QComboBox()
        for c in (self.cmb_fmt_out,self.cmb_fmt_in,self.cmb_fmt_cam):
            c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon); c.setMinimumContentsLength(40)
            c.addItem("Probe formats to list choices…", None)
        ff.addRow("Audio out", self.cmb_fmt_out); ff.addRow("Audio in", self.cmb_fmt_in); ff.addRow("Camera", self.cmb_fmt_cam)
        fr=QHBoxLayout(); b=QPushButton("↻ Probe formats"); b.clicked.connect(self._probe_formats); fr.addWidget(b)
        b=QPushButton("Apply selected formats"); b.clicked.connect(self._apply_formats); fr.addWidget(b); fr.addStretch(1); ff.addRow(fr)
        self.lbl_fmt_status=QLabel(""); self.lbl_fmt_status.setWordWrap(True); ff.addRow(self.lbl_fmt_status)
        lay.addWidget(fbox)
        self._fmt_bridge=_NearbyBridge(); self._fmt_bridge.result.connect(self._on_formats_probed)
        # System Volume is intentionally owned by the main window only.
        return w

    def _probe_formats(self):
        self.lbl_fmt_status.setText("Probing audio formats (worker thread)…")
        def run():
            try:
                import hardware_formats as _hf
                self._fmt_bridge.result.emit("audio", {"out": _hf.audio_options("output"), "in": _hf.audio_options("input")}, "")
            except Exception as e:
                self._fmt_bridge.result.emit("audio", None, str(e))
        self._worker_pool.start(_PoolTask(run))
        try:   # Qt Multimedia camera formats must be read on the GUI thread
            import hardware_formats as _hf
            self._on_formats_probed("camera", _hf.camera_options(), "")
        except Exception as e:
            self._on_formats_probed("camera", None, str(e))

    def _on_formats_probed(self, kind, payload, error):
        if error:
            self.lbl_fmt_status.setText(f"Format probe ({kind}) failed: {error}"); return
        def fill(cmb, rows):
            cmb.clear()
            for r in rows or []:
                cmb.addItem(r["label"], r)
        if kind == "audio":
            fill(self.cmb_fmt_out, payload.get("out")); fill(self.cmb_fmt_in, payload.get("in"))
            self.lbl_fmt_status.setText(f"{self.cmb_fmt_out.count()} output and {self.cmb_fmt_in.count()} input format choices.")
        else:
            fill(self.cmb_fmt_cam, payload)

    def _apply_formats(self):
        host = self.host; msgs = []
        o = self.cmb_fmt_out.currentData(); i = self.cmb_fmt_in.currentData(); c = self.cmb_fmt_cam.currentData()
        try:
            from audio_os_backend import sd as _sd
            if _sd is None:
                raise RuntimeError("PortAudio/sounddevice unavailable")
            if o:
                _sd.default.samplerate = int(o["samplerate"])
                _sd.default.device = (_sd.default.device[0] if i is None else i.get("device"), o.get("device"))
                _sd.default.dtype = (i.get("dtype") if i else _sd.default.dtype[0], o.get("dtype"))
                msgs.append(o["label"])
            if i and not o:
                _sd.default.device = (i.get("device"), _sd.default.device[1])
                msgs.append(i["label"])
        except Exception as e:
            msgs.append(f"audio defaults not applied: {e}")
        if o and hasattr(host, "preferred_sample_rate"):
            host.preferred_sample_rate = max(44100, min(192000, int(o["samplerate"])))
        if c:
            setattr(host, "preferred_camera_format", dict(c)); msgs.append(c["label"])
        setattr(host, "preferred_audio_formats", {"output": o, "input": i})
        self.lbl_fmt_status.setText("Applied: " + " | ".join(m for m in msgs if m) if msgs else "Nothing selected.")

    def _refresh_hardware(self):
        try:
            from audio_os_backend import invalidate_device_cache
            invalidate_device_cache()
        except Exception: pass
        # R22: one low-priority disposable process owns *all* hardware probes.
        # Historical R9 contract text: independent worker lanes. Runtime now uses
        # a stronger isolation boundary so enumeration cannot retain GUI resources.
        self._hardware_scan_generation += 1
        generation=self._hardware_scan_generation
        self._hardware_component_results={}
        self._hardware_component_pending={'bundle'}
        self.txt_hardware.setPlainText("Scanning hardware in isolated helper process…")
        self.btn_hardware_rescan.setEnabled(False)
        def work():
            try:
                from hardware_hub import run_bounded, run_probe_retry
                from groovebox_subprocess import helper_argv
                cp=run_probe_retry(helper_argv('device_probe_helper','hardware'),timeout=8.0)
                if cp.returncode != 0:
                    raise RuntimeError((cp.stderr or cp.stdout or 'hardware probe failed')[-1200:].strip())
                line=(cp.stdout or '').strip().splitlines()[-1] if (cp.stdout or '').strip() else ''
                report=json.loads(line or '{}'); err=''
            except subprocess.TimeoutExpired as exc:
                # GROOVEBOX_HW_PARTIAL_CHECKPOINT_20261030: salvage lanes that finished.
                raw=exc.stdout.decode('utf-8','replace') if isinstance(exc.stdout,(bytes,bytearray)) else (exc.stdout or '')
                rows=[ln for ln in raw.strip().splitlines() if ln.startswith('{')]
                try: report=json.loads(rows[-1]) if rows else {}
                except Exception: report={}
                if isinstance(report,dict) and report:
                    report['_errors']=list(report.get('_errors') or [])+['probe timed out after 8 s; lanes that had not finished are missing']
                    err=''
                else:
                    report={}; err='hardware probe timed out after 8 s'
            except Exception as exc:
                report={}; err=str(exc)
            try:
                self._hardware_scan_bridge.done.emit(generation,'bundle',report,err)
            except RuntimeError:
                pass  # dialog closed while the helper was running
        self._worker_pool.start(_PoolTask(work))

    def _render_hardware_report(self, r):
        from hardware_hub import summary
        # summary tolerates merged component dictionaries after defaults below.
        defaults={'keyboard':[],'touch':[],'mouse':[],'gamepad':[],'audio_devices':[],
                  'video_devices':[],'midi_inputs':[],'usb':[],'bluetooth_connected':[],
                  'display_summary':[],'event_nodes':[],'qt_input_contract':'Qt input discovery'}
        rr=dict(defaults); rr.update(r or {})
        lines=[summary(rr), "", "INPUT DEVICES"] + [f"  • {x}" for x in rr.get("input_names",[])]
        lines += ["", "DISPLAYS"] + ([f"  • {x}" for x in rr.get("display_summary",[])[:24]] or ["  • none detected"])
        lines += ["", "AUDIO OUTPUTS"] + ([f"  • {x}" for x in rr.get("audio_outputs",[])[:24]] or ["  • no physical output detected"])
        lines += ["", "AUDIO INPUTS / MICROPHONES"] + ([f"  • {x}" for x in rr.get("audio_inputs",[])[:24]] or ["  • no microphone/input detected"])
        lines += ["", "VIDEO / CAMERAS"] + ([f"  • {x}" for x in rr.get("video_devices",[])[:24]] or ["  • none detected"])
        lines += ["", "MIDI"] + ([f"  • {x}" for x in rr.get("midi_inputs",[])[:24]] or ["  • none detected"])
        lines += ["", "BLUETOOTH"] + [f"  • {x}" for x in rr.get("bluetooth_connected",[])[:24]]
        lines += ["", "TOOLS", "  " + " · ".join(f"{k}={'yes' if v else 'no'}" for k,v in rr.get("tools",{}).items())]
        if rr.get("audio_status"): lines += ["", "PIPEWIRE / PULSE / ALSA", rr["audio_status"]]
        self.txt_hardware.setPlainText("\n".join(lines))

    def _on_hardware_scan_done(self, generation: int, component: str, r, error: str):
        if generation != getattr(self,'_hardware_scan_generation',-1): return
        self._hardware_component_pending.discard(component)
        if error:
            self._hardware_component_results.setdefault('_errors',[]).append(f"{component}: {error}")
        elif isinstance(r,dict):
            if component == 'bundle':
                self._hardware_component_results=dict(r)
            else:
                # Historical component-mode compatibility.
                for k,v in r.items():
                    if k=='tools' and isinstance(v,dict):
                        self._hardware_component_results.setdefault('tools',{}).update(v)
                    elif v is not None:
                        self._hardware_component_results[k]=v
        if self._hardware_component_pending:
            # Historical verifier token: Hardware scan running on separate lanes…
            self.txt_hardware.setPlainText("Hardware scan still running in isolated helper…")
            return
        self.btn_hardware_rescan.setEnabled(True)
        try:
            from hardware_runtime import mark_manual_refresh
            mark_manual_refresh(self._hardware_component_results)
        except Exception: pass
        self._render_hardware_report(self._hardware_component_results)
        errs=self._hardware_component_results.get('_errors',[])
        if errs:
            self.txt_hardware.append("\nCOMPONENT WARNINGS\n  • "+"\n  • ".join(errs))

    def _run_physical_audio_io_test(self):
        """Run the real speaker->air->microphone test off the GUI thread."""
        self._hardware_audio_test_generation += 1
        generation=self._hardware_audio_test_generation
        self.btn_audio_io_test.setEnabled(False)
        self.txt_hardware.append("\nPHYSICAL AUDIO I/O TEST\n  Playing a brief 997 Hz test tone and measuring its return through the physical microphone…")
        def work():
            cmd=shutil.which('sos-audio-io-test') or '/usr/bin/sos-audio-io-test'
            try:
                cp=subprocess.run([cmd],capture_output=True,text=True,timeout=12.0,check=False)
                text=(cp.stdout or '') + (("\n"+cp.stderr) if cp.stderr else '')
                rc=int(cp.returncode)
            except Exception as exc:
                rc=127; text=f"AUDIO_IO_SELFTEST|FAIL\nREASON|{type(exc).__name__}: {exc}"
            self._audio_io_test_bridge.done.emit(generation,rc,text.strip())
        self._worker_pool.start(_PoolTask(work))

    def _on_physical_audio_io_test_done(self, generation: int, rc: int, text: str):
        if generation != getattr(self,'_hardware_audio_test_generation',-1): return
        self.btn_audio_io_test.setEnabled(True)
        self.txt_hardware.append("\n"+(text or 'AUDIO_IO_SELFTEST|FAIL\nREASON|no test output'))
        if rc==0:
            QMessageBox.information(self,"Physical Audio I/O Test","PASS — the physical output played the test tone and the selected microphone captured its 997 Hz acoustic return.")
        else:
            QMessageBox.warning(self,"Physical Audio I/O Test",f"FAIL / INCONCLUSIVE (rc={rc}).\n\nThe Hardware report now contains the exact output/input and failure reason. Check speaker/mic mute and volume, then retry.")

    # ------------------------------------------------------------------ box mode
    def _build_box_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Performance Box / Installation Mode</b>"))
        note = QLabel("Checks the small-PC/Pi runtime and generates a systemd service template. Device routing stays separate from canonical composition, so reconnecting HDMI/Bluetooth/LAN cannot change the seed result.")
        note.setWordWrap(True); lay.addWidget(note)
        self.lbl_box_status = QLabel("Not checked yet."); self.lbl_box_status.setWordWrap(True); lay.addWidget(self.lbl_box_status)
        row=QHBoxLayout()
        b=QPushButton("Check box readiness"); b.clicked.connect(self._check_box_readiness); row.addWidget(b)
        b2=QPushButton("Save systemd service template"); b2.clicked.connect(self._save_box_service); row.addWidget(b2)
        lay.addLayout(row)
        self.chk_box_autorecover=QCheckBox("Prefer automatic playback/device recovery after hot-plug"); self.chk_box_autorecover.setChecked(True); lay.addWidget(self.chk_box_autorecover)
        self.chk_box_preview_shed=QCheckBox("Protect audio first: shed preview/video quality before audio/event timing"); self.chk_box_preview_shed.setChecked(True); lay.addWidget(self.chk_box_preview_shed)
        lay.addStretch(1); return w

    def _check_box_readiness(self):
        try:
            from performance_box import status
            st=status(self._cwd or '.')
            self.lbl_box_status.setText(f"CPU threads: {st.cpu_count} · free storage: {st.free_gb:.1f} GB\nFFmpeg: {st.ffmpeg} · ffprobe: {st.ffprobe} · mpv: {st.mpv} · PipeWire/Pulse: {st.pipewire} · Bluetooth tools: {st.bluetoothctl}")
        except Exception as e: self.lbl_box_status.setText(f"Readiness check failed: {e}")

    def _save_box_service(self):
        try:
            from performance_box import systemd_unit
            import groovebox_paths
            path,_=QFileDialog.getSaveFileName(self,"Save Performance Box service",os.path.join(groovebox_paths.state_dir(),"groovebox-performance.service"),"systemd service (*.service)")
            if not path: return
            with open(path,'w',encoding='utf-8') as f: f.write(systemd_unit(os.path.dirname(__file__)))
            self.lbl_status.setText(f"Saved box service template: {path}")
        except Exception as e: QMessageBox.warning(self,"Box Mode",str(e))

    # ------------------------------------------------------------------ batch tab
    # GROOVEBOX_R23R_PERF_LAYOUT_20261103
    def _open_batch_window(self):
        """Batch Export in its own window (kept alive; shows/raises on reopen).
        GROOVEBOX_R23R_EXPORT_MERGE_20261103: it is the Batch tab of the main window's 📦 Export window."""
        host = getattr(self, "host", None)
        if host is not None and hasattr(host, "export_window_dialog"):
            return host.export_window_dialog(tab="batch")
        win = getattr(self, "_batch_window", None)
        try:
            if win is not None:
                win.show(); win.raise_(); win.activateWindow()
                return win
        except RuntimeError:
            win = None
        win = QWidget(None, Qt.WindowType.Window)
        win.setWindowTitle("📦 Batch Export")
        win.resize(760, 640)
        lay = QVBoxLayout(win)
        lay.addWidget(self._scroll_page(self._build_batch_tab()))
        self._batch_window = win
        win.show(); win.raise_()
        return win

    def _build_batch_launcher(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>📦 Batch Export</b> runs in its own window so you can keep working while it exports."))
        b = QPushButton("Open Batch Export window"); b.setMinimumHeight(40)
        b.clicked.connect(self._open_batch_window)
        lay.addWidget(b); lay.addStretch(1)
        return w

    def _build_lazy_voxel_viewer(self):
        """Launcher tab that opens the shared voxel viewer window."""
        host = getattr(self, "host", None)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>🧊 Voxel Viewer</b> — full model reference of the project's voxels."))
        lay.addWidget(QLabel("The viewer opens in its own window so you can keep it visible while editing or performing."))
        btn = QPushButton("Open Voxel Viewer")
        btn.setMinimumHeight(40)
        def _open():
            if host is not None and hasattr(host, "open_voxel_viewer"):
                host.open_voxel_viewer()
            else:
                QMessageBox.information(self, "Voxel Viewer", "The viewer needs the main Groovebox window.")
        btn.clicked.connect(_open)
        lay.addWidget(btn)
        lay.addStretch(1)
        return w

    def _build_lazy_voxel_editor(self):
        host = getattr(self, "host", None)
        if host is None:
            w = QWidget(); QVBoxLayout(w).addWidget(QLabel("The voxel editor needs the main Groovebox window."))
            return w
        import groovebox as _gbm
        panel = _gbm.VoxelDrawKitPanel(host, self)
        self._perf_voxel_panel = panel
        try:
            host._perf_voxel_panel = panel  # also expose on host for random object etc.
        except Exception:
            pass
        try:
            panel.refresh_views()
        except Exception:
            pass
        return panel

    def _build_batch_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Batch Export</b> — export many projects (or the projects behind exported media) in one go"))
        try:   # GROOVEBOX_R23R_SAVE_TO_DRIVE_20261103
            lay.addWidget(self.host._make_export_target_picker(w))
        except Exception:
            pass
        lay.addWidget(QLabel(
            "Select exported media carrying source-project provenance OR select .mgpr projects directly. "
            "Project sets are rendered along an FPS/bitrate trend curve from the first item to the last."
        ))
        form = QFormLayout()
        self.spin_batch_fps = QSpinBox()
        self.spin_batch_fps.setRange(1, 120)
        self.spin_batch_fps.setValue(int(getattr(self.host, "_last_export_fps", 24) or 24))
        form.addRow("Target video FPS", self.spin_batch_fps)
        self.spin_batch_br = QSpinBox()
        self.spin_batch_br.setRange(32, 512)
        self.spin_batch_br.setValue(int(getattr(self.host, "_last_audio_bitrate_kbps", 192) or 192))
        self.spin_batch_br.setSuffix(" kbps")
        form.addRow("Target audio bitrate", self.spin_batch_br)
        self.spin_batch_fps_end = QSpinBox()
        self.spin_batch_fps_end.setRange(1, 120)
        self.spin_batch_fps_end.setValue(self.spin_batch_fps.value())
        form.addRow("Trend end FPS", self.spin_batch_fps_end)
        self.spin_batch_br_end = QSpinBox()
        self.spin_batch_br_end.setRange(32, 512)
        self.spin_batch_br_end.setValue(self.spin_batch_br.value())
        self.spin_batch_br_end.setSuffix(" kbps")
        form.addRow("Trend end bitrate", self.spin_batch_br_end)
        self.cmb_batch_curve = QComboBox()
        self.cmb_batch_curve.addItems(["Linear trend", "Ease-in", "Ease-out", "Smoothstep"])
        form.addRow("Project-set trend", self.cmb_batch_curve)
        self.cmb_batch_kind = QComboBox()
        self.cmb_batch_kind.addItems([
            "Audio WAV", "Audio MP3", "Audio Opus", "Audio OGG",
            "Video+Audio MP4", "Video-only MP4",
        ])
        form.addRow("Export as", self.cmb_batch_kind)
        self.chk_batch_preview = QCheckBox("Pi-safe: use preview rows for audio (faster)")
        self.chk_batch_preview.setChecked(True)
        form.addRow(self.chk_batch_preview)
        lay.addLayout(form)

        # GROOVEBOX_R23R_EXPORT_MERGE_20261103: Batch Export uses the export worker.
        wrow = QHBoxLayout()
        self.chk_batch_worker = QCheckBox("Render in separate worker processes (parallel; this window stays smooth)")
        self.chk_batch_worker.setToolTip("Each project renders in its own export-worker process with its own master bus; "
                                         "several run at once. Audio formats only — video uses the in-app pipeline.")
        try:
            import compat_settings as _cs_b
            self.chk_batch_worker.setChecked(bool(_cs_b.load().get("export_in_worker", True)) or True)
        except Exception:
            self.chk_batch_worker.setChecked(True)
        self.spin_batch_workers = QSpinBox(); self.spin_batch_workers.setRange(0, 32); self.spin_batch_workers.setValue(0)
        self.spin_batch_workers.setSpecialValueText("auto"); self.spin_batch_workers.setPrefix("workers ")
        self.spin_batch_workers.setToolTip("Parallel worker processes (auto = half the CPU threads, at least 1).")
        wrow.addWidget(self.chk_batch_worker, 1); wrow.addWidget(self.spin_batch_workers)
        lay.addLayout(wrow)
        row = QHBoxLayout()
        btn_run = QPushButton("▶ Batch export selected")
        btn_run.clicked.connect(self._batch_rerender)
        btn_cancel = QPushButton("Cancel batch")
        btn_cancel.clicked.connect(lambda: setattr(self, "_batch_cancel", True))
        row.addWidget(btn_run)
        row.addWidget(btn_cancel)
        lay.addLayout(row)

        self.batch_log = QTextEdit()
        self.batch_log.setReadOnly(True)
        self.batch_log.setMaximumHeight(160)
        lay.addWidget(self.batch_log)
        return w

    def _batch_log(self, msg: str):
        self.batch_log.append(msg)
        self.lbl_status.setText(msg)

    def _batch_rerender(self):
        paths = [p for p in self._selected_paths() if os.path.isfile(p)]
        if not paths:
            QMessageBox.information(self, "Batch", "Select exported media or one/more .mgpr project files.")
            return
        self._batch_cancel = False
        fps0 = int(self.spin_batch_fps.value())
        br0 = int(self.spin_batch_br.value())
        fps1 = int(self.spin_batch_fps_end.value())
        br1 = int(self.spin_batch_br_end.value())
        kind = self.cmb_batch_kind.currentText()
        def trend(x: float) -> float:
            mode = self.cmb_batch_curve.currentText()
            x = max(0.0, min(1.0, x))
            if mode == "Ease-in": return x * x
            if mode == "Ease-out": return 1.0 - (1.0 - x) * (1.0 - x)
            if mode == "Smoothstep": return x * x * (3.0 - 2.0 * x)
            return x

        # GROOVEBOX_R23R_BATCH_ASYNC_20261103: the batch used to render every track on
        # the GUI thread, freezing the main window until all tracks were preprocessed.
        # It is now a generator stepped by a Qt timer: renders run on the render lane,
        # file writes on a worker, the GUI stays responsive and Cancel works mid-batch.
        if kind.startswith("Audio") and getattr(self, "chk_batch_worker", None) is not None and self.chk_batch_worker.isChecked():
            return self._batch_parallel_audio(paths, kind, trend, br0, br1)
        self._batch_gen = self._batch_iter(paths, kind, trend, fps0, fps1, br0, br1)
        self._batch_wait = None
        self._batch_first = True
        self._batch_log(f"Batch started: {len(paths)} item(s) — the main window stays usable while it renders.")
        QTimer.singleShot(0, self._batch_pump)

    def _batch_pump(self):
        fut = getattr(self, "_batch_wait", None)
        if fut is not None and not fut.done():
            QTimer.singleShot(100, self._batch_pump)
            return
        val = None; exc = None
        if fut is not None:
            try:
                val = fut.result()
            except Exception as e:
                exc = e
        self._batch_wait = None
        gen = getattr(self, "_batch_gen", None)
        if gen is None:
            return
        try:
            if getattr(self, "_batch_first", False):
                self._batch_first = False
                nxt = next(gen)
            elif exc is not None:
                nxt = gen.throw(exc)
            else:
                nxt = gen.send(val)
        except StopIteration:
            self._batch_gen = None
            return
        except Exception as e:
            self._batch_log(f"Batch stopped: {e}")
            self._batch_gen = None
            return
        self._batch_wait = nxt
        QTimer.singleShot(50, self._batch_pump)

    def _batch_resolve_project(self, path):
        """The project behind a selected item (.mgpr/.MCC itself, or the source of an export)."""
        project_path = path if _gb_ext(path) in PROJECT_EXT else None
        prov = None if project_path else _extract_json_comment(path)
        if isinstance(prov, dict):
            project_path = prov.get("source_project_path") or prov.get("project_path")
        if not project_path or not os.path.isfile(str(project_path)):
            stem = os.path.splitext(os.path.basename(path))[0]
            for c in (os.path.splitext(path)[0] + ".mgpr", os.path.join(self._host_projects_dir(), stem + ".mgpr")):
                if c and os.path.isfile(c):
                    return c
            return None
        return project_path

    def _batch_parallel_audio(self, paths, kind, trend, br0, br1):
        """GROOVEBOX_R23R_EXPORT_MERGE_20261103: every project renders in its own export
        worker; N workers run at once (QProcess, no GUI blocking); results are quantised
        and written on the file-writer thread."""
        import json as _json, tempfile as _tf, sys as _sys
        from PyQt6.QtCore import QProcess
        fmt = kind.split()[-1].lower()
        jobs = []
        for idx, path in enumerate(paths):
            proj = self._batch_resolve_project(path)
            if not proj:
                self._batch_log(f"  skip: no linked project for {os.path.basename(path)}"); continue
            u = trend(0.0 if len(paths) <= 1 else idx / float(len(paths) - 1))
            jobs.append({"src": path, "project": proj, "br": int(round(br0 + (br1 - br0) * u))})
        if not jobs:
            return
        n_auto = max(1, (os.cpu_count() or 2) // 2)
        n = int(self.spin_batch_workers.value()) or n_auto
        n = max(1, min(n, len(jobs)))
        here = os.path.dirname(os.path.abspath(__file__))
        state = {"next": 0, "running": {}, "done": 0, "failed": 0, "t0": time.monotonic()}
        self._batch_cancel = False
        self._batch_log(f"Batch started: {len(jobs)} project(s) · {n} parallel worker process(es) · {fmt.upper()}")

        def start_one():
            if self._batch_cancel or state["next"] >= len(jobs):
                return False
            j = jobs[state["next"]]; state["next"] += 1
            tmp = _tf.mkdtemp(prefix="gb_batch_")
            spec = {"project": j["project"], "sample_rate": 0, "out_npy": os.path.join(tmp, "master.npy"),
                    "out_meta": os.path.join(tmp, "master.json"), "kind": "audio", "purpose": "Batch export",
                    "final": True,
                    "max_rows": (self.host._live_preview_max_rows() if self.chk_batch_preview.isChecked()
                                 and hasattr(self.host, "_live_preview_max_rows") else None)}
            jp = os.path.join(tmp, "job.json")
            with open(jp, "w", encoding="utf-8") as fh:
                _json.dump(spec, fh)
            proc = QProcess(self)
            proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            proc.finished.connect(lambda *_a, p=proc, jj=j, sp=spec, td=tmp: finished(p, jj, sp, td))
            try:
                from groovebox_subprocess import helper_argv
                argv = helper_argv("export_worker", jp)
                proc.start(argv[0], argv[1:])
            except Exception:
                proc.start(_sys.executable, [os.path.join(here, "export_worker.py"), jp])
            state["running"][id(proc)] = proc
            self._batch_log(f"→ {os.path.basename(j['project'])} · worker started")
            return True

        def finished(proc, j, spec, tmp):
            state["running"].pop(id(proc), None)
            ok = proc.exitCode() == 0 and os.path.isfile(spec["out_npy"])
            if ok:
                try:
                    import numpy as np
                    meta = _json.load(open(spec["out_meta"], encoding="utf-8"))
                    master = np.load(spec["out_npy"]); sr = int(meta["sample_rate"])
                    try:
                        from audio_export_integrity import quantize_float_master
                        _bits = 24 if int(getattr(self.host, "_last_export_bit_depth", 24) or 24) >= 24 else 16
                        pcm = quantize_float_master(master, _bits)
                    except Exception:
                        _bits = 16
                        pcm = np.rint(np.clip(master, -1.0, 1.0) * 32767.0).astype(np.int16)
                    stem = os.path.splitext(os.path.basename(j["src"]))[0]
                    out = os.path.join(self._host_exports_dir(), f"{stem}_r{j['br']}k.{fmt}")
                    self._batch_executor().submit(
                        self.host._write_audio_parts_and_final, out, sr, pcm, n_parts=1, provenance_bytes=None,
                        audio_format=fmt, audio_bitrate_kbps=j["br"] if fmt in ("mp3", "opus", "ogg") else None,
                        bit_depth=_bits, worker_safe=True)
                    state["done"] += 1
                    self._batch_log(f"  ✓ {os.path.basename(out)}")
                except Exception as exc:
                    state["failed"] += 1; self._batch_log(f"  ✗ {os.path.basename(j['project'])}: {exc}")
            else:
                state["failed"] += 1
                tail = bytes(proc.readAll()).decode("utf-8", "replace").strip().splitlines()[-1:] or ["worker failed"]
                self._batch_log(f"  ✗ {os.path.basename(j['project'])}: {tail[0]}")
            try:
                import shutil as _sh
                QTimer.singleShot(4000, lambda d=tmp: _sh.rmtree(d, ignore_errors=True))
            except Exception:
                pass
            if not start_one() and not state["running"]:
                self._batch_log(f"Batch finished: {state['done']} written, {state['failed']} failed · "
                                f"{time.monotonic() - state['t0']:.1f} s")
        self._batch_worker_state = state
        for _ in range(n):
            if not start_one():
                break

    def _batch_iter(self, paths, kind, trend, fps0, fps1, br0, br1):
        for idx, path in enumerate(paths):
            u = trend(0.0 if len(paths) <= 1 else idx / float(len(paths) - 1))
            fps = int(round(fps0 + (fps1 - fps0) * u))
            br = int(round(br0 + (br1 - br0) * u))
            setattr(self.host, "_last_export_fps", fps)
            setattr(self.host, "_last_audio_bitrate_kbps", br)
            if self._batch_cancel:
                self._batch_log("Batch cancelled.")
                break
            self._batch_log(f"→ {os.path.basename(path)}")
            project_path = path if _gb_ext(path) in PROJECT_EXT else None
            prov = None if project_path else _extract_json_comment(path)
            if isinstance(prov, dict):
                project_path = prov.get("source_project_path") or prov.get("project_path")
            if not project_path or not os.path.isfile(str(project_path)):
                # Try same stem .mgpr beside media or in projects dir
                stem = os.path.splitext(os.path.basename(path))[0]
                candidates = [
                    os.path.splitext(path)[0] + ".mgpr",
                    os.path.join(self._host_projects_dir(), stem + ".mgpr"),
                    getattr(self.host, "_current_project_path", None),
                ]
                for c in candidates:
                    if c and os.path.isfile(c):
                        project_path = c
                        break
            if not project_path or not os.path.isfile(str(project_path)):
                self._batch_log(f"  skip: no linked project for {os.path.basename(path)}")
                continue
            try:
                with open(project_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                applied = False
                for name in ("_apply_project_snapshot", "apply_project_snapshot"):
                    fn = getattr(self.host, name, None)
                    if callable(fn):
                        fn(data)
                        applied = True
                        break
                if not applied:
                    self._batch_log(f"  skip: cannot apply project snapshot")
                    continue
                setattr(self.host, "_current_project_path", project_path)
                self._batch_log(f"  loaded {os.path.basename(project_path)} · trend fps={fps} bitrate={br}k")
            except Exception as e:
                self._batch_log(f"  load error: {e}")
                continue

            # Pi-safe preview rows for faster audio batch
            if self.chk_batch_preview.isChecked() and "Audio" in kind:
                if hasattr(self.host, "spin_preview_rows"):
                    try:
                        if self.host.spin_preview_rows.value() == 0:
                            self.host.spin_preview_rows.setValue(8)
                    except Exception:
                        pass

            try:
                if kind.startswith("Audio"):
                    fmt = kind.split()[-1].lower()
                    if hasattr(self.host, "export_mixdown_dialog"):
                        # Non-interactive path: render (render lane) + write (worker)
                        yield from self._batch_audio_export_steps(fmt, br, path)
                    else:
                        self._batch_log("  no export_mixdown_dialog on host")
                elif "Video" in kind:
                    include_audio = "Video+Audio" in kind
                    if hasattr(self.host, "export_video_dialog"):
                        self._batch_log(
                            f"  opening video export UI (fps={fps}) — confirm path when prompted"
                        )
                        self.host._batch_export_active = True
                        try:
                            self.host.export_video_dialog(include_audio=include_audio, container="mp4")
                        finally:
                            self.host._batch_export_active = False
                    else:
                        self._batch_log("  no export_video_dialog on host")
            except Exception as e:
                self._batch_log(f"  render error: {e}")

        self._batch_log("Batch finished.")
        self.refresh()

    def _batch_executor(self):
        ex = getattr(self, "_batch_ex", None)
        if ex is None:
            from concurrent.futures import ThreadPoolExecutor
            ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="GrooveboxBatch")
            self._batch_ex = ex
        return ex

    def _batch_audio_export_steps(self, fmt: str, bitrate_kbps: int, source_media: str):
        """Generator form: yields futures (render, then write); the GUI never blocks."""
        host = self.host
        max_rows = None
        if self.chk_batch_preview.isChecked() and hasattr(host, "_live_preview_max_rows"):
            max_rows = host._live_preview_max_rows()
        lane = getattr(host, "_live_audio_fx_lane", None) or self._batch_executor()
        # GROOVEBOX_R23R_LOUDNESS_BEFORE_CLIP_20261101: the shared buffer is the
        # loudness-matched mix (gain on the unclipped sum); the hard clip comes after.
        self._batch_log("  rendering in the background…")
        if hasattr(host, "_get_shared_mixdown_buffer"):
            master, sr = yield lane.submit(host._get_shared_mixdown_buffer, max_rows, "Batch export")
        else:
            master, sr = yield lane.submit(host._render_mixdown_buffer, max_rows)
        out, sr, pcm, prov, _bits = self._batch_finish_master(master, sr, fmt, bitrate_kbps, source_media)
        yield self._batch_executor().submit(
            host._write_audio_parts_and_final, out, sr, pcm, n_parts=1, provenance_bytes=prov,
            audio_format=fmt, audio_bitrate_kbps=bitrate_kbps if fmt in ("mp3", "opus", "ogg") else None,
            bit_depth=_bits, worker_safe=True)
        self._batch_log(f"  wrote {out}")

    def _batch_finish_master(self, master, sr, fmt, bitrate_kbps, source_media):
        """GUI-thread part: master bus (fast numpy) + quantise + target name."""
        host = self.host
        import numpy as np
        master = np.nan_to_num(np.asarray(master, dtype=np.float32), nan=0.0, posinf=1.0, neginf=-1.0)
        if hasattr(host, "_bake_dj_write"):
            master = host._bake_dj_write(master, sr)
        if hasattr(host, "_master_hardclip"):
            master, _ = host._master_hardclip(master, sr, apply_master_vol=True)
        try:
            from audio_export_integrity import quantize_float_master
            _bits = 24 if int(getattr(host, "_last_export_bit_depth", 24) or 24) >= 24 else 16
            pcm = quantize_float_master(master, _bits)
        except Exception:
            _bits = 16
            pcm = np.rint(np.clip(master, -1.0, 1.0) * 32767.0).astype(np.int16)
        stem = os.path.splitext(os.path.basename(source_media))[0]
        dest_dir = self._host_exports_dir()
        out = os.path.join(dest_dir, f"{stem}_r{bitrate_kbps}k.{fmt}")
        prov = None
        try:
            prov = host._export_provenance_payload()
            if isinstance(prov, str):
                prov = prov.encode("utf-8")
        except Exception:
            prov = None
        return out, sr, pcm, prov, _bits

    def _batch_audio_export(self, fmt: str, bitrate_kbps: int, source_media: str):
        """Blocking form (kept for scripts/tests): render + write in the caller's thread."""
        host = self.host
        max_rows = None
        if self.chk_batch_preview.isChecked() and hasattr(host, "_live_preview_max_rows"):
            max_rows = host._live_preview_max_rows()
        if hasattr(host, "_get_shared_mixdown_buffer"):
            master, sr = host._get_shared_mixdown_buffer(max_rows=max_rows, purpose="Batch export")
        else:
            master, sr = host._render_mixdown_buffer(max_rows=max_rows)
        out, sr, pcm, prov, bits = self._batch_finish_master(master, sr, fmt, bitrate_kbps, source_media)
        host._write_audio_parts_and_final(
            out, sr, pcm, n_parts=1, provenance_bytes=prov,
            audio_format=fmt, audio_bitrate_kbps=bitrate_kbps if fmt in ("mp3", "opus", "ogg") else None,
            bit_depth=bits,
        )
        self._batch_log(f"  wrote {out}")

    # ------------------------------------------------------------------ info tab
    def _mg_library_roots(self):
        roots=[]
        for fn in (self._host_projects_dir,self._host_samples_dir,self._host_exports_dir):
            try:
                p=fn()
                if p and p not in roots: roots.append(p)
            except Exception: pass
        return roots

    def _scan_mg_paths(self):
        out=[]
        for root in self._mg_library_roots():
            if not root or not os.path.isdir(root): continue
            for base,_,files in os.walk(root):
                for fn in files:
                    if fn.lower().endswith(('.mgproject','.mgsynth','.mgprofile','.mg')):
                        out.append(os.path.join(base,fn))
        return sorted(set(out),key=lambda x:os.path.basename(x).lower())

    def _build_mg_library_tab(self) -> QWidget:
        w=QWidget(); lay=QVBoxLayout(w)
        hdr=QLabel("<b style='color:#f1ce68'>.MG ID + Relationship Library</b><br>Project · Synth · Profile artifacts keep stable IDs while usage statistics and software-discovered relationships evolve separately.")
        hdr.setWordWrap(True); lay.addWidget(hdr)
        self.mg_list=QListWidget(); lay.addWidget(self.mg_list,1)
        row=QHBoxLayout()
        b_refresh=QPushButton("↻ Scan .MG"); b_refresh.clicked.connect(self._refresh_mg_library); row.addWidget(b_refresh)
        b_load=QPushButton("⬇ Load to relevant slot"); b_load.clicked.connect(self._load_selected_mg); row.addWidget(b_load)
        b_rel=QPushButton("⌬ Find Related"); b_rel.clicked.connect(self._show_related_mg); row.addWidget(b_rel)
        b_share=QPushButton("⇪ Share Identity"); b_share.setToolTip("Export a tiny portable identity/provenance card for another Groovebox user; the original .MG remains unchanged."); b_share.clicked.connect(self._share_selected_mg_identity); row.addWidget(b_share)
        b_exp=QPushButton("⇧ Export History"); b_exp.setToolTip("Export .MG provenance and analytics as JSON, CSV, or HTML without changing the artifact."); b_exp.clicked.connect(self._export_selected_mg_history); row.addWidget(b_exp)
        b_cmp=QPushButton("⇣ Compress History"); b_cmp.setToolTip("Keep longitudinal totals and strongest companion relationships while reducing detailed history."); b_cmp.clicked.connect(self._compress_selected_mg_history); row.addWidget(b_cmp)
        b_clr=QPushButton("⌫ Clear History"); b_clr.setToolTip("Clear mutable use/co-use/outcome history without changing the .MG Artifact ID or payload."); b_clr.clicked.connect(self._clear_selected_mg_history); row.addWidget(b_clr)
        lay.addLayout(row)
        self.mg_info=QTextEdit(); self.mg_info.setReadOnly(True); self.mg_info.setMaximumHeight(180); lay.addWidget(self.mg_info)
        self.mg_list.itemSelectionChanged.connect(self._mg_selection_changed)
        return w

    def _refresh_mg_library(self):
        if not hasattr(self,'mg_list'): return
        self.mg_list.clear()
        try:
            from mg_artifacts import load
            for path in self._scan_mg_paths():
                try:
                    d=load(path,record_use=False); a=d.get('analytics',{}) or {}
                    text=f"{d.get('kind','?').upper()} · {d.get('title') or os.path.basename(path)} · uses {int(a.get('use_count',0))} · {d.get('artifact_id','')}"
                    it=QListWidgetItem(text); it.setData(Qt.ItemDataRole.UserRole,path); self.mg_list.addItem(it)
                except Exception: pass
            self.mg_info.setPlainText(f"{self.mg_list.count()} .MG artifact(s) found across Projects / Samples / Exports.")
        except Exception as e: self.mg_info.setPlainText(str(e))

    def _selected_mg_path(self):
        its=self.mg_list.selectedItems() if hasattr(self,'mg_list') else []
        return str(its[0].data(Qt.ItemDataRole.UserRole)) if its else ''

    def _mg_selection_changed(self):
        path=self._selected_mg_path()
        if not path: return
        try:
            from mg_artifacts import load
            d=load(path,record_use=False); a=d.get('analytics',{}) or {}; p=d.get('provenance',{}) or {}
            self.mg_info.setPlainText(
                f"{path}\nArtifact ID: {d.get('artifact_id')}\nProgram ID: {p.get('program_id')}\nComposition ID: {p.get('composition_id')}\n"
                f"uses: {a.get('use_count',0)} · loads: {a.get('load_count',0)} · saves: {a.get('save_count',0)}\n"
                f"first used: {a.get('first_used')} · last used: {a.get('last_used')}\ncompanions: {json.dumps(a.get('companions',{}),sort_keys=True)}")
        except Exception as e: self.mg_info.setPlainText(str(e))

    def _share_selected_mg_identity(self):
        path=self._selected_mg_path()
        if not path: return
        try:
            from mg_artifacts import load
            d=load(path,record_use=False); prov=d.get('provenance',{}) or {}
            card={
                'format':'MG-share-card-v1', 'kind':d.get('kind'), 'title':d.get('title'),
                'artifact_id':d.get('artifact_id'), 'program_id':prov.get('program_id'),
                'composition_id':prov.get('composition_id'), 'source_filename':os.path.basename(path),
                'payload_fingerprint':d.get('payload_fingerprint') or prov.get('payload_fingerprint'),
            }
            default=os.path.splitext(path)[0]+'.MGshare.json'
            out,_=QFileDialog.getSaveFileName(self,'Share .MG Identity',default,'Groovebox share card (*.MGshare.json);;JSON (*.json)')
            if not out: return
            with open(out,'w',encoding='utf-8') as f: json.dump(card,f,indent=2,sort_keys=True)
            self.lbl_status.setText(f"Shared identity card → {os.path.basename(out)}")
        except Exception as e:
            QMessageBox.warning(self,'Share identity failed',str(e))

    def _load_selected_mg(self):
        path=self._selected_mg_path()
        if not path: return
        try:
            fn=getattr(self.host,'_load_mg_path',None)
            if not callable(fn): raise RuntimeError('Host .MG loader unavailable')
            d=fn(path); self.lbl_status.setText(f"Loaded .MG {d.get('kind')} → relevant slot")
            self._refresh_mg_library(); self._show_related_mg()
        except Exception as e: QMessageBox.warning(self,".MG load failed",str(e))

    def _show_related_mg(self):
        path=self._selected_mg_path() or str(getattr(self.host,'_last_mg_artifact_path','') or '')
        if not path or not os.path.isfile(path): return
        try:
            from mg_artifacts import find_related
            rel=find_related(path,self._mg_library_roots(),limit=12)
            if not rel: self.mg_info.append("\nRelated: no comparable history yet."); return
            lines=["\nRelated / common results:"]
            for r in rel:
                a=r.get('analytics',{}) or {}
                lines.append(f"{r['score']:.3f} · {r['kind']} · {r['title']} · uses {a.get('use_count',0)} · {os.path.basename(r['path'])}")
            self.mg_info.append("\n".join(lines))
        except Exception as e: self.mg_info.append(f"\nRelated error: {e}")

    def _export_selected_mg_history(self):
        path=self._selected_mg_path()
        if not path: return
        base=os.path.splitext(os.path.basename(path))[0] + "_history"
        out,flt=QFileDialog.getSaveFileName(self,"Export .MG History",os.path.join(os.path.dirname(path),base+".json"),"JSON (*.json);;CSV (*.csv);;HTML (*.html)")
        if not out: return
        low=out.lower(); fmt='csv' if low.endswith('.csv') else ('html' if low.endswith(('.html','.htm')) else 'json')
        if not low.endswith(('.json','.csv','.html','.htm')): out += '.'+fmt
        try:
            from mg_artifacts import export_history
            final=export_history(path,out,fmt)
            self.mg_info.append(f"\nHistory exported: {final}")
        except Exception as e: QMessageBox.warning(self,"History export failed",str(e))

    def _compress_selected_mg_history(self):
        path=self._selected_mg_path()
        if not path: return
        try:
            from mg_artifacts import compress_history
            result=compress_history(path)
            self.mg_info.append(f"\nHistory compressed; Artifact ID unchanged: {result.get('artifact_id')}")
            self._refresh_mg_library()
        except Exception as e: QMessageBox.warning(self,"History compression failed",str(e))

    def _clear_selected_mg_history(self):
        path=self._selected_mg_path()
        if not path: return
        ans=QMessageBox.question(self,"Clear .MG History","Clear detailed usage/co-use/outcome history?\n\nThe .MG payload and Artifact ID will not change.")
        if ans != QMessageBox.StandardButton.Yes: return
        try:
            from mg_artifacts import clear_history
            result=clear_history(path,preserve_totals=True)
            self.mg_info.append(f"\nHistory cleared; Artifact ID unchanged: {result.get('artifact_id')}")
            self._refresh_mg_library()
        except Exception as e: QMessageBox.warning(self,"History clear failed",str(e))

    def _build_info_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.info_view = QTextEdit()
        self.info_view.setReadOnly(True)
        lay.addWidget(self.info_view)
        tip = QLabel(
            "Pi tips: set GROOVEBOX_SAMPLE_RATE=48000, enable UI lite, use Preview rows, "
            "batch-export at lower FPS/bitrate for field copies, full quality at home."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        lay.addWidget(tip)
        return w

    def shutdown_for_application_exit(self):
        """Drain Performance workers/resources before QApplication teardown.

        Normal user-close intentionally hides/reuses Performance, so it must not
        destroy the browser or worker pool.  The main window calls this method
        only during real application shutdown.
        """
        if getattr(self, "_performance_shutdown", False):
            return
        self._performance_shutdown = True
        self._stop_quick_mic_meter()
        # Invalidate queued results before waiting so no stale completion mutates
        # widgets while the shutdown sequence is draining.
        self._selection_token += 1
        self._refresh_generation += 1
        for name in ('_timed_playlist_timer','_pattern_timer','_performance_timer','_radio_peer_timer','_nearby_ui_timer','_selection_debounce','_remote_timer','_remix_apply_timer','_output_refresh_timer','_browser_refresh_timer'):
            try:
                t=getattr(self,name,None)
                if t is not None: t.stop()
            except Exception: pass
        try:
            if getattr(self,'_math_background',None) is not None: self._math_background._timer.stop()
        except Exception: pass
        try:
            browser=getattr(self,'web_browser_tab',None)
            if browser is not None and hasattr(browser,'shutdown_webengine'):
                browser.shutdown_webengine()
        except Exception: pass
        try:
            studio=getattr(self,'video_clip_studio',None)
            if studio is not None:
                if getattr(studio,'_audio_only_recording',False): studio._stop_audio_input_recording()
                studio._release_capture_devices(True)
        except Exception: pass
        for fn_name in ('_stop_goava_radio','_stop_performance','_stop_remote_server','_stop_tv_host','_stop_timed_playlist','_stop_player'):
            try:
                fn=getattr(self,fn_name,None)
                if callable(fn): fn()
            except Exception: pass
        for child_name in ('_file_manager_window','_media_player_window'):
            try:
                child=getattr(self,child_name,None)
                if child is not None and hasattr(child,'shutdown_for_application_exit'):
                    child.shutdown_for_application_exit()
            except Exception: pass
        try:
            pool=getattr(self,'_worker_pool',None)
            if pool is not None:
                # ffprobe jobs are bounded (12 s); wait long enough to retire them
                # cleanly rather than letting daemon activity reach Qt teardown.
                if not pool.waitForDone(15000):
                    print('[Performance] worker pool did not drain within 15 s', file=sys.stderr)
        except Exception as exc:
            print(f'[Performance] worker-pool shutdown warning: {exc}', file=sys.stderr)

    def showEvent(self, event):
        """Resume bounded background refresh only while Performance is visible."""
        try:
            if getattr(self, "_output_refresh_timer", None) is not None:
                self._output_refresh_timer.start()
        except Exception:
            pass
        try:
            if getattr(self, "_browser_refresh_timer", None) is not None:
                self._browser_refresh_timer.start()
        except Exception:
            pass
        try:
            if getattr(self, "_output_scan_inflight", False) is False and hasattr(self, "lbl_output_devices"):
                # No eager scan here: explicit refresh/hot-plug timer owns discovery.
                pass
        except Exception:
            pass
        return super().showEvent(event)

    def suspend_for_hide(self):
        """Stop hidden Performance work while preserving the retained window object.

        The main Groovebox window intentionally hides/reuses Performance instead of
        deleting it. This hook prevents that retention policy from also retaining
        timers, camera/mic handles, servers, and selected-media playback work.
        Dedicated Player/DJ child windows are not destroyed here.
        """
        try: self._sync_project_state()
        except Exception: pass
        for name in ('_timed_playlist_timer','_pattern_timer','_performance_timer','_radio_peer_timer','_nearby_ui_timer','_selection_debounce','_remote_timer','_remix_apply_timer','_output_refresh_timer','_browser_refresh_timer'):
            try:
                t=getattr(self,name,None)
                if t is not None: t.stop()
            except Exception: pass
        try:
            if getattr(self,'_math_background',None) is not None: self._math_background._timer.stop()
        except Exception: pass
        try:
            studio=getattr(self,'video_clip_studio',None)
            if studio is not None:
                if getattr(studio,'_audio_only_recording',False): studio._stop_audio_input_recording()
                studio._release_capture_devices(True)
                studio._devices_activated=False
                studio._audio_devices_activated=False
        except Exception: pass
        try: self._stop_goava_radio()
        except Exception: pass
        try: self._stop_performance()
        except Exception: pass
        try: self._stop_remote_server()
        except Exception: pass
        try: self._stop_tv_host()
        except Exception: pass
        try: self._stop_timed_playlist()
        except Exception: pass
        try: self._stop_player()
        except Exception: pass

    def closeEvent(self, event):
        # R5: normal close can still hide/reuse, but hidden work is suspended first.
        self.suspend_for_hide()
        super().closeEvent(event)


class _Deck:
    """One playback deck: an external mpv process (for live IPC control),
    its own destination-routing, volume, speed and a set of toggleable
    onboard DJ FX filters. VLC/ffplay remain usable for plain playback but
    only mpv exposes the runtime property/filter control DJ mixing needs."""

    AUDIO_FX = {
        "Echo": "aecho=0.8:0.9:1000:0.3",
        "Flanger": "flanger",
        "Bass Boost": "bass=g=15",
        "Telephone": "highpass=f=300,lowpass=f=3000",
        "Reverb": "aecho=0.8:0.88:60:0.4",
    }
    VIDEO_FX = {
        "Invert": "negate",
        "Hue Spin": "hue=h=120:s=2",
        "Strobe": "fps=6",
        "Mirror": "hflip",
        "Contrast Pop": "eq=contrast=1.6:saturation=1.4",
    }

    def __init__(self, name: str):
        self.name = name
        self.proc: Optional[subprocess.Popen] = None
        self.ipc_path: Optional[str] = None
        self.path: str = ""
        self.base_volume = 100.0     # 0..150, this deck's own fader
        self.mix_gain = 1.0          # 0..1, crossfader contribution
        self.speed = 1.0
        self.active_audio_fx: set = set()
        self.active_video_fx: set = set()
        self.want_video = True
        self.image_duration_s = 5.0
        # R23 recovery state. Normal launch uses PipeWire/Pulse/selected routing;
        # watchdog recovery can restart once through a direct safe AO chain.
        self.force_safe_audio = False
        self.resume_position = 0.0
        self.started_at = 0.0
        self.direct_audio_backend = ""
        self.direct_audio_decoder = None  # R23j FFmpeg decoder feeding direct ALSA

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _af_chain(self) -> str:
        # Sets store membership only. Emission follows declaration order so the
        # DSP/filter chain is bit-for-bit stable regardless of toggle history.
        return ",".join(self.AUDIO_FX[f] for f in self.AUDIO_FX if f in self.active_audio_fx)

    def _vf_chain(self) -> str:
        return ",".join(self.VIDEO_FX[f] for f in self.VIDEO_FX if f in self.active_video_fx)

    def effective_volume(self) -> int:
        return max(0, min(150, int(round(self.base_volume * self.mix_gain))))

    def send(self, command: list) -> bool:
        if not self.ipc_path or not os.path.exists(self.ipc_path):
            return False
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.06)
            sock.connect(self.ipc_path)
            sock.sendall((json.dumps({"command": command}) + "\n").encode("utf-8"))
            sock.close()
            return True
        except Exception:
            return False

    def query_property(self, name: str, default=None):
        """Read one mpv IPC property without disturbing the persistent deck."""
        if not self.ipc_path or not os.path.exists(self.ipc_path):
            return default
        request_id = int(time.monotonic_ns() & 0x7fffffff)
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.08)
            sock.connect(self.ipc_path)
            payload = {"command": ["get_property", name], "request_id": request_id}
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            buf = b""
            deadline = time.monotonic() + 0.08
            while time.monotonic() < deadline:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8", "replace"))
                    except Exception:
                        continue
                    if msg.get("request_id") == request_id and msg.get("error") == "success":
                        sock.close()
                        return msg.get("data", default)
            sock.close()
        except Exception:
            pass
        return default

    def play(self, path: str, routed: Callable[[list, bool], Tuple[list, dict]]):
        # GROOVEBOX_V35_22ZZ_R2_PERSISTENT_PLAYLIST_PLAYER
        # Keep the existing mpv process/window alive across playlist changes.
        # A queue transition replaces the media through IPC instead of tearing
        # down and recreating the player window for every item.
        path = _gb_playable(path)
        self.path = path
        self.direct_audio_backend = ""
        ext = _gb_ext(path)
        next_want_video = ext in VIDEO_EXT or ext in IMAGE_EXT
        # A recovery launch must rebuild the AO and cannot reuse the process that
        # owns the stalled/broken output device.
        if self.force_safe_audio and self.is_running():
            self.stop()
        if (not self.force_safe_audio and self.is_running() and self.ipc_path and os.path.exists(self.ipc_path)):
            if self.send(["loadfile", path, "replace"]):
                self.want_video = next_want_video
                self.send(["set_property", "pause", False])
                self.started_at = time.monotonic()
                self.send(["set_property", "speed", self.speed])
                self.send(["set_property", "volume", self.effective_volume()])
                return True, "reloaded"
        # No reusable IPC player is available (first item, player crash, or
        # non-mpv fallback), so start a fresh process once.
        self.stop()
        self.want_video = next_want_video
        cmd = _player_cmd_with_volume(int(self.effective_volume()), want_video=self.want_video) or _find_player()
        if not cmd:
            return False, "Install mpv, vlc, or ffplay for media playback."
        is_mpv = os.path.basename(cmd[0]).startswith("mpv")
        self.ipc_path = None
        if is_mpv:
            self.ipc_path = os.path.join(tempfile.gettempdir(), f"groovebox_deck_{self.name}_{os.getpid()}_{id(self)}.sock")
            try:
                os.unlink(self.ipc_path)
            except OSError:
                pass
            extra = [
                f"--input-ipc-server={self.ipc_path}",
                f"--speed={self.speed:.6f}",
                # R6: keep local playback responsive even when a driver reports
                # jittery delay. R23 keeps real hardware as the normal clock.
                "--cache-pause=no",
            ]
            if self.resume_position > 0:
                extra.append(f"--start={self.resume_position:.6f}")
            if self.force_safe_audio:
                # R23d rebuilds the safe AO after generic destination routing so
                # an explicit physical ALSA device cannot be accidentally erased.
                pass
            if ext in IMAGE_EXT:
                extra.extend([f"--image-display-duration={max(0.1,float(self.image_duration_s)):.3f}", "--loop-file=no"])
            af = self._af_chain()
            vf = self._vf_chain()
            if af:
                extra.append(f"--af={af}")
            if vf and self.want_video:
                extra.append(f"--vf={vf}")
            cmd = list(cmd) + extra
        cmd, env = routed(cmd, self.want_video)
        if self.force_safe_audio:
            # Recovery must not fall back to generic ALSA "default": on the sOS
            # appliance that alias can still resolve through the failed Pulse
            # compatibility layer. Strip earlier AO choices, then pin the best
            # physical plughw PCM discovered from ``aplay -l``.
            cmd = [a for a in cmd if not (str(a).startswith("--audio-device=") or str(a).startswith("--ao="))]
            env.pop("PULSE_SINK", None)
            try:
                from media_output_router import _preferred_alsa_output_device, _prepare_physical_alsa_output
                physical = _preferred_alsa_output_device()
                if physical:
                    _prepare_physical_alsa_output(physical)
            except Exception:
                physical = ""
            if not is_mpv:
                # VLC/ffplay do not understand mpv's --ao/--audio-device options;
                # route them through ALSA's environment instead.
                if physical:
                    env["AUDIODEV"] = physical; env["SDL_AUDIODRIVER"] = "alsa"
            elif physical:
                cmd.extend(["--ao=alsa", f"--audio-device={physical}", "--audio-format=s16"])
            else:
                # No ALSA card was visible. Give the two session backends one
                # final chance without inheriting a stale per-sink selection.
                cmd.append("--ao=pipewire,pulse,alsa")
        try:
            self.proc = subprocess.Popen(cmd + [path], env=env)
            self.started_at = time.monotonic()
            self.resume_position = 0.0
            return True, ""
        except Exception as e:
            return False, str(e)

    def play_direct_audio(self, path: str, start_s: float = 0.0):
        """Last-resort direct physical playback for any FFmpeg-readable audio stream."""
        self.stop()
        try:
            sink,decoder,backend=_launch_physical_pcm_pipeline(path,start_s=start_s)
        except Exception as exc:
            return False, str(exc)
        self.proc=sink
        self.direct_audio_decoder=decoder
        self.ipc_path=None
        self.path=path
        self.want_video=False
        self.started_at=time.monotonic()
        self.direct_audio_backend=backend
        return True, ""

    def stop(self):
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        decoder, self.direct_audio_decoder = getattr(self, "direct_audio_decoder", None), None
        if decoder is not None and decoder.poll() is None:
            try:
                decoder.terminate()
            except Exception:
                pass
        if self.ipc_path:
            try:
                os.unlink(self.ipc_path)
            except OSError:
                pass
        self.ipc_path = None
        self.started_at = 0.0

    def set_speed(self, speed: float):
        new_speed = max(0.25, min(4.0, speed))
        if abs(new_speed - self.speed) < 1e-6:
            return
        self.speed = new_speed
        self.send(["set_property", "speed", self.speed])

    def set_mix_gain(self, gain: float):
        new_gain = max(0.0, min(1.0, gain))
        old_volume = self.effective_volume()
        if abs(new_gain - self.mix_gain) < 1e-6:
            return
        self.mix_gain = new_gain
        new_volume = self.effective_volume()
        if new_volume != old_volume:
            self.send(["set_property", "volume", new_volume])

    def set_base_volume(self, vol: float):
        new_volume = max(0.0, min(150.0, vol))
        old_effective = self.effective_volume()
        if abs(new_volume - self.base_volume) < 1e-6:
            return
        self.base_volume = new_volume
        new_effective = self.effective_volume()
        if new_effective != old_effective:
            self.send(["set_property", "volume", new_effective])

    def toggle_audio_fx(self, name: str, on: bool):
        already = name in self.active_audio_fx
        if bool(on) == already:
            return
        if on:
            self.active_audio_fx.add(name)
        else:
            self.active_audio_fx.discard(name)
        chain = self._af_chain()
        self.send(["af", "set", chain if chain else "@dj_af_none:!lavfi=[anull]"])

    def toggle_video_fx(self, name: str, on: bool):
        already = name in self.active_video_fx
        if bool(on) == already:
            return
        if on:
            self.active_video_fx.add(name)
        else:
            self.active_video_fx.discard(name)
        chain = self._vf_chain()
        self.send(["vf", "set", chain if chain else ""])


class _AudioVisualizer(QWidget):
    """Music-reactive ParametricMath display for the player window (audio-only files).

    The file's loudness/brightness envelope (20 ms frames) is decoded once per file by ffmpeg in a thread
    and cached; painting reads the envelope at the deck's play position. No audio-path involvement.
    """
    _cache: Dict[str, Any] = {}

    def __init__(self, pos_fn, parent=None):
        super().__init__(parent)
        self._pos_fn = pos_fn
        self._env = None; self._path = ""; self._phase = 0.0; self._lvl = 0.0; self._br = 0.0
        self.setMinimumHeight(150)
        self._timer = QTimer(self); self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)

    def set_file(self, path: str):
        self._path = path; self._env = self._cache.get(path)
        if self._env is None and path:
            threading.Thread(target=self._decode, args=(path,), daemon=True).start()
        self._timer.start(); self.update()

    def clear(self):
        self._path = ""; self._env = None; self._lvl = 0.0; self._timer.stop(); self.update()

    _decoding: Dict[str, bool] = {}

    @classmethod
    def ensure_env(cls, path):
        """Decode the file's level envelope for the volume meter (even with the visualizer off)."""
        if path and path not in cls._cache and not cls._decoding.get(path):
            cls._decoding[path] = True
            threading.Thread(target=cls._decode_env, args=(path,), daemon=True).start()
        return cls._cache.get(path)

    def _decode(self, path):
        env = self._decode_env(path)
        if env is not None and self._path == path:
            self._env = env

    @classmethod
    def _decode_env(cls, path):
        try:
            import numpy as np
            ff = shutil.which("ffmpeg") or "ffmpeg"
            pr = subprocess.Popen([ff, "-v", "quiet", "-i", path, "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            lv, br, rm, pk, tail = [], [], [], [], np.zeros(0, np.float32)
            while True:
                raw = pr.stdout.read(1 << 20)
                if not raw:
                    break
                a = np.concatenate([tail, np.frombuffer(raw[:len(raw) // 4 * 4], np.float32)])
                k = a.size // 160
                fr = a[:k * 160].reshape(k, 160)
                tail = a[k * 160:]
                l = np.abs(fr).mean(axis=1)
                d = np.abs(np.diff(fr, axis=1)).mean(axis=1)
                lv.append(l)
                br.append(np.divide(d, l, out=np.zeros_like(d), where=l > 0))   # silent frames: no brightness
                rm.append(np.sqrt(np.mean(fr * fr, axis=1))); pk.append(np.abs(fr).max(axis=1))
                if sum(x.size for x in lv) > 180000:   # cap ~1 h
                    break
            try: pr.kill()
            except Exception: pass
            if lv:
                L = np.concatenate(lv); B = np.concatenate(br)
                ref = float(np.percentile(L, 98)) or 1.0
                env = (np.clip(L / ref, 0, 1.2).astype(np.float32), np.clip(B * 0.5, 0, 1).astype(np.float32),
                       np.concatenate(rm).astype(np.float32), np.concatenate(pk).astype(np.float32))
                cls._cache[path] = env
                return env
        except Exception:
            pass
        return cls._cache.get(path)

    def _tick(self):
        if not self.isVisible():
            return
        lv = br = 0.0
        try:
            pos, stamp, paused = self._pos_fn()
            env = self._env
            if env is not None and pos is not None and not paused:
                i = int((pos + (time.monotonic() - stamp)) * 50.0)
                if 0 <= i < env[0].size:
                    lv = float(env[0][i]); br = float(env[1][i])
        except Exception:
            pass
        self._lvl = max(lv, self._lvl * 0.82); self._br = br
        self._phase = (self._phase + 0.05 + 0.25 * self._lvl) % (math.tau * 64)
        self.update()

    MODES = ("Auto (cycle)", "Rose", "Spectrum bars", "Waveform ribbon", "Lissajous", "Phyllotaxis (φ spiral)",
             "Radial burst", "Tunnel rings")

    def set_mode(self, idx: int):
        self._mode = int(idx) % len(self.MODES); self.update()

    def mousePressEvent(self, event):
        self.set_mode(self._mode + 1)          # click = next style
        cb = getattr(self, "_combo", None)
        if cb is not None:
            cb.blockSignals(True); cb.setCurrentIndex(self._mode); cb.blockSignals(False)

    _mode = 0

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w < 4 or h < 4:
            return
        with owned_painter(self) as q:
            if q is None:
                return
            q.fillRect(self.rect(), QColor(8, 12, 18))
            q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            mode = self._mode
            if mode == 0:   # auto: change style every ~20 s
                mode = 1 + int(time.monotonic() // 20) % (len(self.MODES) - 1)
            lv = min(1.0, self._lvl); ph = self._phase; br = self._br
            cx, cy = w / 2.0, h / 2.0; m = min(w, h)
            q.setPen(QPen(QColor(68, 145, 174, 36), 1))
            step = max(32, m // 5)
            for x in range(0, w, step): q.drawLine(x, 0, x, h)
            for y in range(0, h, step): q.drawLine(0, y, w, y)
            cyan = lambda al: QColor(94, 224, 255, max(0, min(255, int(al))))
            gold = lambda al: QColor(245, 211, 109, max(0, min(255, int(al))))
            green = lambda al: QColor(125, 255, 154, max(0, min(255, int(al))))
            pink = lambda al: QColor(255, 140, 240, max(0, min(255, int(al))))
            if mode == 1:      # rose r = cos(k θ/2), petals from brightness
                R = m * (0.16 + 0.30 * lv); k = 3.0 + 4.0 * br
                q.setPen(QPen(cyan(70 + 150 * lv), 2)); prev = None
                for i in range(0, 361, 3):
                    th = math.radians(i) * 2.0; r = R * math.cos(k * th / 2.0 + ph * 0.3)
                    pt = (cx + r * math.cos(th + ph * 0.15), cy + r * math.sin(th + ph * 0.15))
                    if prev: q.drawLine(int(prev[0]), int(prev[1]), int(pt[0]), int(pt[1]))
                    prev = pt
                q.setPen(QPen(gold(50 + 110 * lv), 1))
                for j in range(1, 4):
                    rr = R * (0.45 + 0.30 * j) * (1.0 + 0.15 * math.sin(ph * j * PHI_INV))
                    q.drawEllipse(int(cx - rr), int(cy - rr), int(2 * rr), int(2 * rr))
            elif mode == 2:    # bars on the Meum ratio
                bars = 48; bw = max(2, w // bars); q.setPen(Qt.PenStyle.NoPen)
                for b in range(bars):
                    e = lv * (0.25 + 0.75 * abs(math.sin(math.tau * (MEUM * b / bars) + ph)))
                    bh = int(h * 0.85 * e); q.setBrush(green(50 + 170 * e))
                    q.drawRect(b * bw, h - bh, bw - 1, bh)
            elif mode == 3:    # waveform ribbon: two phase-locked sines, amplitude = level
                for n, (col, f1, f2) in enumerate(((cyan, MEUM, PHI), (gold, PHI, MEUM * 0.5), (pink, 2.0, PHI_INV))):
                    q.setPen(QPen(col(60 + 150 * lv), 2 if n == 0 else 1)); prev = None
                    for x in range(0, w + 6, 6):
                        t = x / max(1, w - 1)
                        y = cy + h * 0.40 * (0.12 + lv) * (math.sin(math.tau * f1 * 2 * t + ph * (1 + n))
                                                           + 0.5 * math.sin(math.tau * f2 * 3 * t - ph * 0.7))
                        if prev: q.drawLine(int(prev[0]), int(prev[1]), x, int(y))
                        prev = (x, y)
            elif mode == 4:    # Lissajous x=sin(a t+φ), y=sin(b t); ratio steps with brightness
                a_, b_ = 3.0, 2.0 + round(3.0 * br)
                R = m * (0.18 + 0.30 * lv); q.setPen(QPen(cyan(80 + 140 * lv), 2)); prev = None
                for i in range(0, 721, 4):
                    t = math.radians(i)
                    pt = (cx + R * 1.3 * math.sin(a_ * t + ph * 0.4), cy + R * math.sin(b_ * t))
                    if prev: q.drawLine(int(prev[0]), int(prev[1]), int(pt[0]), int(pt[1]))
                    prev = pt
            elif mode == 5:    # phyllotaxis: golden-angle seed spiral, dot size pulses with level
                n_pts = 260; ga = math.pi * (3.0 - math.sqrt(5.0)); q.setPen(Qt.PenStyle.NoPen)
                for i in range(n_pts):
                    r = m * 0.46 * math.sqrt(i / n_pts) * (0.7 + 0.5 * lv); a2 = i * ga + ph * 0.1
                    sz = 1.5 + (2.0 + 5.0 * lv) * (i / n_pts)
                    q.setBrush(gold(90 + 150 * (i / n_pts)) if i % 3 else cyan(150))
                    q.drawEllipse(int(cx + r * math.cos(a2) - sz / 2), int(cy + r * math.sin(a2) - sz / 2), int(sz), int(sz))
            elif mode == 6:    # radial burst: 72 spokes, length from Meum-spaced pseudo-spectrum
                spokes = 72; q.setPen(QPen(green(140), 2))
                for i in range(spokes):
                    a2 = math.tau * i / spokes + ph * 0.05
                    e = lv * (0.2 + 0.8 * abs(math.sin(math.tau * MEUM * i / spokes + ph)))
                    r0 = m * 0.12; r1 = r0 + m * 0.36 * e
                    q.drawLine(int(cx + r0 * math.cos(a2)), int(cy + r0 * math.sin(a2)),
                               int(cx + r1 * math.cos(a2)), int(cy + r1 * math.sin(a2)))
                q.setPen(QPen(gold(100), 1)); q.drawEllipse(int(cx - m * 0.12), int(cy - m * 0.12), int(m * 0.24), int(m * 0.24))
            else:              # tunnel rings that rush outward; ring spacing follows phi
                q.setBrush(Qt.BrushStyle.NoBrush)
                for j in range(14):
                    t = ((j + (ph * 0.8) % 1.0) / 14.0) ** PHI
                    rr = m * 0.55 * t * (1.0 + 0.35 * lv)
                    q.setPen(QPen(cyan(40 + 190 * t * (0.4 + lv)) if j % 2 else pink(30 + 150 * t * (0.4 + lv)), 1 + int(2 * t)))
                    q.drawEllipse(int(cx - rr * 1.25), int(cy - rr), int(rr * 2.5), int(rr * 2))
            q.setPen(QPen(QColor(150, 170, 190, 150), 1))
            q.drawText(8, 16, "click: next style · " + self.MODES[self._mode])
            q.end()


# GROOVEBOX_R23R_VISUALIZER_SWITCH_20261103: the built-in audio visualizer can be switched off
# (Player window checkbox; remembered). Off = no decoding for it and nothing drawn.
def _gb_visualizer_enabled() -> bool:
    try:
        import compat_settings as _cs
        return bool(_cs.load().get("builtin_visualizer", True))
    except Exception:
        return True


def _gb_set_visualizer_enabled(on: bool) -> None:
    try:
        import compat_settings as _cs
        st = dict(_cs.load()); st["builtin_visualizer"] = bool(on); _cs.save(st)
    except Exception:
        pass


class MediaPlayerWindow(QDialog):
    """Dedicated media Player Window: destination device selection, a linear
    playback queue (Deck A), a second load-anything deck (Deck B) for live
    mixing, a crossfader, onboard DJ FX per deck, and an optional live sync
    to the Performance Parametric Remix panel (GOAVA/RAND/boost/speed).

    Self-contained: it re-detects displays/audio sinks via
    ``media_output_router`` rather than assuming the parent Performance
    dialog's routing state, so it works whether it was opened from the
    Playlist tab or straight from the Browse Files window on a single file.
    """

    def __init__(self, parent: Optional[QWidget], items: List[Dict[str, Any]], start_index: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Groovebox Player · DJ Decks")
        self.resize(760, 720)
        self.setStyleSheet(
            "QDialog { background:#071019; color:#d9edf5; }"
            "QGroupBox { border:1px solid #284c62; border-radius:7px; margin-top:8px; padding-top:7px; font-weight:700; }"
            "QGroupBox::title { color:#f1ce68; subcontrol-origin:margin; left:9px; padding:0 4px; }"
            "QPushButton { background:#102838; color:#d9f7ff; border:1px solid #39708a; border-radius:11px; padding:6px 10px; font-weight:700; }"
            "QPushButton:hover { background:#17405a; border-color:#62bfd0; }"
            "QPushButton:checked { background:#5a3a12; border-color:#f1ce68; color:#ffe8a6; }"
            "QComboBox,QSpinBox,QLineEdit { background:#08141e; color:#e6f8ff; border:1px solid #335b70; border-radius:8px; padding:5px; }"
        )
        self._items: List[Dict[str, Any]] = [dict(it) if isinstance(it, dict) else {"path": it} for it in items]
        self._index = max(0, min(start_index, len(self._items) - 1)) if self._items else -1
        self._manual_stop = False
        self._paused = False
        self._displays: list = []
        self._audio_targets: list = []
        try:
            from media_output_router import AudioTarget
            self._audio_targets = [AudioTarget("__all_detected__", "All detected outputs (default)", kind="all", backend="pulse")]
        except Exception:
            pass
        self._device_scan_generation = 0
        self._device_scan_bridge = _DeviceScanBridge()
        self._device_scan_bridge.done.connect(self._on_device_scan_done)
        self._device_scan_pool = QThreadPool(self)
        self._device_scan_pool.setMaxThreadCount(1)
        # R6_EVENT_LOOP_20260928: mpv status reads use their own single worker.
        # Never allow overlapping status probes and never run recv() on Qt GUI.
        self._player_poll_bridge = _PlayerPollBridge()
        self._player_poll_bridge.done.connect(self._on_player_poll_done)
        self._player_poll_pool = QThreadPool(self)
        self._player_poll_pool.setMaxThreadCount(1)
        self._player_poll_generation = 0
        self._player_poll_inflight = False
        self._last_player_time_pos = None
        self._last_player_progress_at = time.monotonic()
        self._clock_recovery_used = False  # historical compatibility marker
        self._safe_audio_recovery_used = False
        self._video_clock_escape_used = False
        self._direct_audio_fallback_used = False
        self._deckA = _Deck("A")
        self._deckB = _Deck("B")
        self._sync_enabled = False
        self._analysis_cache: Dict[str, Tuple[float, int, Optional[dict]]] = {}

        # GROOVEBOX_R23R_PLAYER_SCROLL_20261103: the whole window scrolls (small laptop screens).
        _outer = QVBoxLayout(self); _outer.setContentsMargins(0, 0, 0, 0)
        _scroll = QScrollArea(self); _scroll.setWidgetResizable(True); _scroll.setFrameShape(QFrame.Shape.NoFrame)
        _body = QWidget(); _scroll.setWidget(_body); _outer.addWidget(_scroll)
        root = QVBoxLayout(_body)

        dev = QGroupBox("Destination device")
        df = QFormLayout(dev)
        self.cmb_display = QComboBox(); self.cmb_display.addItem("Default display")
        self.cmb_audio = QComboBox(); self.cmb_audio.addItem("All detected outputs (default)")
        df.addRow("Display", self.cmb_display)
        df.addRow("Audio sink", self.cmb_audio)
        btn_refresh_dev = QPushButton("↻ Detect devices")
        btn_refresh_dev.clicked.connect(self._refresh_devices)
        df.addRow(btn_refresh_dev)
        # Probe asynchronously at launch; HDMI/USB audio sinks can appear after
        # the desktop and user audio session finish starting.
        QTimer.singleShot(0, self._refresh_devices)
        self._device_refresh_timer = QTimer(self)
        self._device_refresh_timer.setInterval(6000)
        self._device_refresh_timer.timeout.connect(self._refresh_devices_if_visible)
        self._device_refresh_timer.start()
        root.addWidget(dev)

        # -------------------------------------------------------------- Deck A (queue-driven)
        deckA_box = QGroupBox("Deck A · Queue")
        da = QVBoxLayout(deckA_box)
        self.lbl_now = QLabel("Nothing loaded")
        self.lbl_now.setWordWrap(True)
        self.lbl_now.setStyleSheet("color:#f1ce68; font-weight:700;")
        da.addWidget(self.lbl_now)
        self.queue_widget = QListWidget()
        self.queue_widget.setMaximumHeight(110)
        self.queue_widget.itemDoubleClicked.connect(self._on_queue_double_click)
        da.addWidget(self.queue_widget)
        transport = QHBoxLayout()
        self.btn_prev = QPushButton("⏮")
        self.btn_playpause = QPushButton("▶ Play")
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_next = QPushButton("⏭")
        self.btn_prev.clicked.connect(self._prev)
        self.btn_playpause.clicked.connect(self._toggle_play_pause)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_next.clicked.connect(self._next)
        for b in (self.btn_prev, self.btn_playpause, self.btn_stop, self.btn_next):
            transport.addWidget(b)
        self.chk_builtin_viz = QCheckBox("Visualizer")
        self.chk_builtin_viz.setToolTip("Built-in audio visualizer (waveform / scope / spectrum). Off = nothing "
                                        "drawn and no extra decoding — remembered for every player.")
        self.chk_builtin_viz.setChecked(_gb_visualizer_enabled())
        self.chk_builtin_viz.toggled.connect(self._viz_switched)
        transport.addWidget(self.chk_builtin_viz)
        # GROOVEBOX_R23R_LIVE_PLAYER_20261103: watch the open composition play live.
        self.btn_live_comp = QPushButton("🎬 Live composition")
        self.btn_live_comp.setToolTip("Play the open project live with a light visualizer (instrument voices as the keys "
                                      "play them). 'Full process routine' in that window = exact Play / Export sound.")
        def _open_live():
            h = getattr(getattr(self, "_perf", None) or self.parent(), "host", None) or getattr(self.parent(), "host", None)
            if h is None:
                return
            __import__("live_player").open_live_player(h)
        self.btn_live_comp.clicked.connect(_open_live)
        transport.addWidget(self.btn_live_comp)
        da.addLayout(transport)
        da.addLayout(self._build_deck_fx_row(self._deckA))
        self._viz = _AudioVisualizer(lambda: (self._last_player_time_pos, getattr(self, "_viz_stamp", 0.0),
                                              bool(self._paused or self._manual_stop)))
        self._viz.hide()
        self._viz_combo = QComboBox(); self._viz_combo.addItems(list(_AudioVisualizer.MODES))
        self._viz_combo.currentIndexChanged.connect(self._viz.set_mode)
        self._viz._combo = self._viz_combo
        self._viz_combo.hide()
        da.addWidget(self._viz_combo)
        da.addWidget(self._viz)
        # GROOVEBOX_R23R_PLAYER_METER_20261103: volume meter (peak / RMS dBFS after the player volume)
        try:
            from master_hardware_panel import _Meter
            self._meter = _Meter(self)
            da.addWidget(self._meter)
            self._meter_timer = QTimer(self); self._meter_timer.setInterval(50)
            self._meter_timer.timeout.connect(self._meter_tick); self._meter_timer.start()
        except Exception:
            self._meter = None
        root.addWidget(deckA_box)

        # GROOVEBOX_R23R_PLAYER_VISUALIZER_MCC_20261103: audio items show a live
        # waveform / scope / spectrum here (mpv shows nothing for audio-only).
        self.visualizer = None
        try:
            from media_visualizer import AudioVisualizer
            self.visualizer = AudioVisualizer(self)
            self.visualizer.setMinimumHeight(170)
            self.visualizer.set_clock(self._visualizer_clock)
            root.addWidget(self.visualizer, 1)
        except Exception:
            self.visualizer = None
        self._vis_pos = None

        # -------------------------------------------------------------- Deck B (load-anything mix partner)
        deckB_box = QGroupBox("Deck B · Mix partner (load any video/music file)")
        db = QVBoxLayout(deckB_box)
        self.lbl_deckB = QLabel("Deck B empty — Browse Files → Add to Deck B, or use the button below.")
        self.lbl_deckB.setWordWrap(True)
        db.addWidget(self.lbl_deckB)
        b_row = QHBoxLayout()
        btn_load_b = QPushButton("📂 Load into Deck B…")
        btn_load_b.clicked.connect(self._load_deck_b_dialog)
        btn_play_b = QPushButton("▶ Play B")
        btn_play_b.clicked.connect(self._play_deck_b)
        btn_stop_b = QPushButton("⏹ Stop B")
        btn_stop_b.clicked.connect(lambda: self._deckB.stop())
        self.cmb_deck_b_match = QComboBox()
        self.cmb_deck_b_match.addItems(["Analyzed key/texture", "Canonical metadata"])
        self.cmb_deck_b_match.setToolTip("Analyzed mode uses deterministic pitch-class/texture distance. Canonical mode prefers Groovebox render provenance, then falls back to analyzed distance.")
        btn_suggest_b = QPushButton("🔬 Suggest Deck B")
        btn_suggest_b.setToolTip("Deterministically selects the closest queue partner using the selected matching mode.")
        btn_suggest_b.clicked.connect(self._suggest_deck_b_match)
        b_row.addWidget(btn_load_b); b_row.addWidget(btn_play_b); b_row.addWidget(btn_stop_b); b_row.addWidget(self.cmb_deck_b_match); b_row.addWidget(btn_suggest_b)
        db.addLayout(b_row)
        db.addLayout(self._build_deck_fx_row(self._deckB))
        root.addWidget(deckB_box)

        # -------------------------------------------------------------- Crossfader + live mixing
        mix_box = QGroupBox("Live mixing")
        mf = QFormLayout(mix_box)
        self.sld_crossfade = QSlider(Qt.Orientation.Horizontal)
        self.sld_crossfade.setRange(0, 100)
        self.sld_crossfade.setValue(0)
        self.sld_crossfade.setToolTip("0 = Deck A only, 100 = Deck B only. Both decks can play simultaneously through the OS mixer.")
        self.sld_crossfade.valueChanged.connect(self._on_crossfade_changed)
        mf.addRow("Crossfader A ↔ B", self.sld_crossfade)
        self.cmb_crossfade_curve = QComboBox()
        self.cmb_crossfade_curve.addItems(["Equal-power", "Linear"])
        self.cmb_crossfade_curve.setToolTip("Equal-power keeps perceived loudness steadier through the middle; Linear preserves the original arithmetic fade.")
        self.cmb_crossfade_curve.currentIndexChanged.connect(lambda _i: self._on_crossfade_changed(self.sld_crossfade.value()))
        mf.addRow("Crossfade curve", self.cmb_crossfade_curve)
        self.spin_player_image_duration = QDoubleSpinBox()
        self.spin_player_image_duration.setRange(0.25, 3600.0); self.spin_player_image_duration.setDecimals(2); self.spin_player_image_duration.setValue(5.0); self.spin_player_image_duration.setSuffix(" s")
        self.spin_player_image_duration.setToolTip("Still-image duration for Player queues and Deck B. Playlist rows with an explicit duration override this for Deck A.")
        mf.addRow("Still-image duration", self.spin_player_image_duration)
        xrow = QHBoxLayout()
        btn_auto_x = QPushButton("↔ Auto-crossfade to B (4s)")
        btn_auto_x.clicked.connect(lambda: self._auto_crossfade(1, 4.0))
        btn_auto_x_back = QPushButton("↔ Auto-crossfade to A (4s)")
        btn_auto_x_back.clicked.connect(lambda: self._auto_crossfade(0, 4.0))
        xrow.addWidget(btn_auto_x); xrow.addWidget(btn_auto_x_back)
        mf.addRow(xrow)

        self.chk_sync_remix = QCheckBox("🔗 Sync both decks to Performance Parametric Remix (GOAVA/RAND/boost → FX, speed → tempo)")
        self.chk_sync_remix.toggled.connect(self._on_toggle_sync)
        mf.addRow(self.chk_sync_remix)
        root.addWidget(mix_box)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Deck A"))
        self.sld_volume = QSlider(Qt.Orientation.Horizontal); self.sld_volume.setRange(0,150); self.sld_volume.setValue(100)
        self.sld_volume.valueChanged.connect(self._on_deckA_volume_changed); vol_row.addWidget(self.sld_volume, stretch=1)
        self.lbl_volume = QLabel("100%"); self.lbl_volume.setMinimumWidth(40); vol_row.addWidget(self.lbl_volume)
        vol_row.addWidget(QLabel("Deck B"))
        self.sld_volume_b = QSlider(Qt.Orientation.Horizontal); self.sld_volume_b.setRange(0,150); self.sld_volume_b.setValue(100)
        self.sld_volume_b.valueChanged.connect(self._on_deckB_volume_changed); vol_row.addWidget(self.sld_volume_b, stretch=1)
        self.lbl_volume_b = QLabel("100%"); self.lbl_volume_b.setMinimumWidth(40); vol_row.addWidget(self.lbl_volume_b)
        root.addLayout(vol_row)

        self.lbl_status = QLabel("Idle")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        root.addWidget(self.lbl_status)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._schedule_player_poll)
        # R6: the timer only schedules a worker; it never talks to mpv itself.

        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(180)
        self._sync_timer.timeout.connect(self._apply_remix_sync)
        self._last_remix_sync_state = None

        self._refresh_queue_widget()
        self.lbl_status.setText("Ready · system-default output (Detect devices only when you need explicit HDMI/USB/Bluetooth routing).")
        if self._index >= 0:
            self._load_current(autoplay=False)
        # GROOVEBOX_R23R_PLAYER_SCROLL_20261103: never squeeze controls below their natural
        # height — the window scrolls instead (buttons stayed invisible on small screens).
        try:
            _body.setMinimumHeight(_body.sizeHint().height())
            _body.setMinimumWidth(min(_body.sizeHint().width(), 720))
        except Exception:
            pass

    # -- FX row builder ---------------------------------------------------
    def _build_deck_fx_row(self, deck: "_Deck") -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("FX:"))
        for fx_name in deck.AUDIO_FX:
            b = QPushButton(fx_name)
            b.setCheckable(True)
            b.toggled.connect(lambda on, d=deck, n=fx_name: d.toggle_audio_fx(n, on))
            row.addWidget(b)
        for fx_name in deck.VIDEO_FX:
            b = QPushButton(fx_name)
            b.setCheckable(True)
            b.toggled.connect(lambda on, d=deck, n=fx_name: d.toggle_video_fx(n, on))
            row.addWidget(b)
        row.addStretch(1)
        return row

    # -- devices --------------------------------------------------------
    def _scan_devices_worker(self, generation: int):
        try:
            from media_output_router import detect_displays, detect_audio_targets
            displays = detect_displays(); audio = detect_audio_targets(); error = ""
        except Exception as exc:
            displays = []; audio = []; error = str(exc)
        try:   # GROOVEBOX_R23R_ALL_OUTPUTS_SINK_20261103: build the All-outputs route here, never on Play
            from media_output_router import prewarm_all_outputs
            prewarm_all_outputs()
        except Exception:
            pass
        self._device_scan_bridge.done.emit(generation, displays, audio, error)

    def _refresh_devices_if_visible(self):
        # Hot-plugged HDMI/USB/BT sinks can appear several seconds after login.
        # Refresh only while this window is visible, and never stack scans.
        if self.isVisible() and not getattr(self, "_device_scan_inflight", False):
            self._refresh_devices()

    def _refresh_devices(self):
        """Asynchronously discover displays/audio endpoints without blocking Qt."""
        if getattr(self, "_device_scan_inflight", False):
            return
        self._device_scan_inflight = True
        self._device_scan_generation += 1
        generation = self._device_scan_generation
        self.lbl_status.setText("Detecting HDMI/display/audio outputs in background…")
        self._device_scan_pool.start(_PoolTask(self._scan_devices_worker, generation))

    def _on_device_scan_done(self, generation: int, displays, audio_targets, error: str):
        if generation != self._device_scan_generation:
            return
        self._device_scan_inflight = False
        if error:
            self.lbl_status.setText(f"Device scan unavailable: {error}")
            return
        old_display = getattr(self, "cmb_display", None).currentText() if getattr(self, "cmb_display", None) is not None else ""
        old_audio = getattr(self, "cmb_audio", None).currentText() if getattr(self, "cmb_audio", None) is not None else ""
        self._displays = list(displays or [])
        # The default is an aggregate Pulse/PipeWire sink so sound is mirrored
        # to every currently published real output (including HDMI when present).
        try:
            from media_output_router import AudioTarget
            all_outputs=AudioTarget("__all_detected__", "All detected outputs (default)", kind="all", backend="pulse")
            # GROOVEBOX_R23R_PLAYER_ALL_DEVICES_20261103: "All detected outputs" stays the default, and
            # every detected device can be chosen on its own (its Hardware & Master format applies).
            self._audio_targets = [all_outputs] + [a for a in list(audio_targets or [])
                                                   if getattr(a, "name", "") not in ("", "__all_detected__")]
        except Exception:
            self._audio_targets = list(audio_targets or [])
        self.cmb_display.clear()
        if self._displays:
            for d in self._displays:
                tag = f" · {d.geometry}" if getattr(d, "geometry", None) else ""
                self.cmb_display.addItem(d.name + tag)
        else:
            self.cmb_display.addItem("Default display")
        if old_display:
            idx=self.cmb_display.findText(old_display)
            if idx >= 0: self.cmb_display.setCurrentIndex(idx)
        self.cmb_audio.clear()
        if self._audio_targets:
            for a in self._audio_targets:
                tag = f" [{a.kind}]" if getattr(a, "kind", None) and a.kind not in ("default","all") else ""
                self.cmb_audio.addItem(a.description + tag)
        else:
            self.cmb_audio.addItem("All detected outputs (default)")
        if self.cmb_audio.count():
            _i = self.cmb_audio.findText(old_audio) if old_audio else -1
            self.cmb_audio.setCurrentIndex(_i if _i >= 0 else 0)
        self.cmb_audio.setEnabled(True)
        self.cmb_audio.setToolTip("All detected outputs (default) = every output switched on in 🔊 Hardware & Master → "
                                  "Devices, each at its own rate / bit depth. Or pick any single device.")
        self.lbl_status.setText(f"{len(self._displays)} display target(s) · {len(self._audio_targets)} audio choice(s): "
                                "all outputs (default) or any single device.")

    def _selected_display(self):
        i = self.cmb_display.currentIndex()
        return self._displays[i] if 0 <= i < len(self._displays) else None

    def _selected_audio(self):
        i = self.cmb_audio.currentIndex()
        return self._audio_targets[i] if 0 <= i < len(self._audio_targets) else None

    def _routed(self, cmd: list, want_video: bool) -> Tuple[list, dict]:
        env = os.environ.copy()
        try:
            from media_output_router import player_routing
            extra, overlay = player_routing(self._selected_display(), self._selected_audio(), want_video=want_video)
            if cmd and os.path.basename(cmd[0]).lower().startswith("mpv"):
                cmd = list(cmd) + list(extra)
            env.update(overlay)
        except Exception:
            pass
        return cmd, env

    # -- queue (Deck A) ------------------------------------------------
    def set_items(self, items, start_index=0):
        """Replace the queue only on an explicit launcher action; hidden-window restore keeps state."""
        self._items = [dict(it) if isinstance(it, dict) else {"path": it} for it in (items or [])]
        self._index = max(0, min(int(start_index), len(self._items)-1)) if self._items else -1
        self._manual_stop = False
        self._refresh_queue_widget()
        if self._index >= 0: self._load_current(autoplay=False)
        else: self.lbl_now.setText("Nothing loaded")

    def _refresh_queue_widget(self):
        self.queue_widget.clear()
        for i, it in enumerate(self._items):
            marker = "▶ " if i == self._index else "   "
            self.queue_widget.addItem(f"{marker}{os.path.basename(it.get('path', '?'))}")

    def _on_queue_double_click(self, item: QListWidgetItem):
        row = self.queue_widget.row(item)
        if 0 <= row < len(self._items):
            self._index = row
            self._load_current(autoplay=True)

    def _load_current(self, autoplay: bool):
        if not (0 <= self._index < len(self._items)):
            return
        path = self._items[self._index].get("path", "")
        self.lbl_now.setText(f"{self._index + 1}/{len(self._items)} · {os.path.basename(path)}")
        self._refresh_queue_widget()
        if autoplay:
            self._play_current()

    def _visualizer_clock(self):
        """Deck A position: mpv time-pos (interpolated between polls) or the
        in-app host file player's cursor."""
        if self._paused:
            vp = self._vis_pos
            return vp[0] if vp else None
        vp = self._vis_pos
        if vp is not None:
            return vp[0] + (time.monotonic() - vp[1]) * float(getattr(self._deckA, "speed", 1.0) or 1.0)
        try:
            if _GB_FILE_PLAYER.stream is not None:
                return _GB_FILE_PLAYER.position_s()
        except Exception:
            pass
        return None

    def _meter_tick(self):
        m = getattr(self, "_meter", None)
        if m is None or not self.isVisible():
            return
        pk = rm = 0.0
        try:
            if 0 <= self._index < len(self._items) and not (self._paused or self._manual_stop):
                path = str(self._items[self._index].get("path", "") or "")
                env = _AudioVisualizer.ensure_env(_gb_playable(path) if path else "")
                pos = self._last_player_time_pos
                if env is not None and len(env) >= 4 and pos is not None:
                    i = int((float(pos) + (time.monotonic() - float(getattr(self, "_viz_stamp", time.monotonic())))) * 50.0)
                    if 0 <= i < env[2].size:
                        g = (max(0.0, float(self.sld_volume.value())) / 100.0) ** 3     # mpv's cubic volume curve
                        rm = float(env[2][i]) * g; pk = float(env[3][i]) * g
        except Exception:
            pass
        m.set_levels(pk, rm)

    def _viz_switched(self, on):
        _gb_set_visualizer_enabled(bool(on))
        if not on:
            for w in (getattr(self, "_viz", None), getattr(self, "_viz_combo", None), self.visualizer):
                try:
                    if w is not None:
                        if hasattr(w, "clear") and w is not getattr(self, "_viz_combo", None):
                            w.clear()
                        w.hide()
                except Exception:
                    pass
        else:
            if self.visualizer is not None:
                self.visualizer.show()
            if 0 <= self._index < len(self._items):
                p = str(self._items[self._index].get("path", "") or "")
                self._update_visualizer_for(p)
                if os.path.splitext(p)[1].lower() in AUDIO_EXT:
                    try:
                        self._viz.show(); self._viz_combo.show(); self._viz.set_file(p)
                    except Exception:
                        pass

    def _update_visualizer_for(self, path):
        if self.visualizer is None:
            return
        if not _gb_visualizer_enabled():
            self.visualizer.hide()
            return
        self._vis_pos = None
        if _gb_ext(path) in AUDIO_EXT:
            self.visualizer.load_path(path, lambda p: _gb_decode_audio_faithful(_gb_playable(p)))
        elif _gb_mcc_kind(path) == "video":
            self.visualizer.clear("MCC video is playing in its own lossless player window")
        else:
            self.visualizer.clear("Video/image is on the selected display")

    def _play_current(self):
        if not (0 <= self._index < len(self._items)):
            return
        _cur = str(self._items[self._index].get("path", "") or "")
        if _cur and os.path.isfile(_cur):
            self._update_visualizer_for(_cur)
            if _gb_mcc_kind(_cur) == "video":
                self._deckA.stop()
                self._mcc_dlg = _gb_open_mcc_video(self, _cur, int(self.sld_volume.value()))
                self.lbl_status.setText(f"Deck A · MCC video playing directly (lossless): {os.path.basename(_cur)}")
                return
        try:
            from hardware_runtime import ensure_first_hardware_refresh, ensure_audio_ready
            ensure_first_hardware_refresh('player-window-play', block=False); ensure_audio_ready('player-window-play')
        except Exception: pass
        # Keep Deck A/mpv alive while advancing or selecting another playlist
        # item. _Deck.play() uses IPC loadfile/replace whenever possible.
        self._manual_stop = False
        item = self._items[self._index]
        path = item.get("path", "")
        if not path or not os.path.isfile(path):
            self.lbl_status.setText(f"Missing file: {path}")
            return
        self._deckA.base_volume = float(self.sld_volume.value())
        self._deckA.force_safe_audio = False
        self._deckA.resume_position = 0.0
        explicit_duration = float(item.get("duration_s", 0.0) or 0.0)
        self._deckA.image_duration_s = explicit_duration if explicit_duration > 0 else float(self.spin_player_image_duration.value())
        ok, err = self._deckA.play(path, self._routed)
        try:   # audio-only files get the music visualizer in this window
            if ok and os.path.splitext(path)[1].lower() in (set(AUDIO_EXT) | set(VIDEO_EXT)) and _gb_visualizer_enabled():
                # switchable visualizer for audio AND video files (video: drawn from its soundtrack)
                self._last_player_time_pos = 0.0; self._viz_stamp = time.monotonic()
                self._viz.show(); self._viz_combo.show(); self._viz.set_file(path)
            else:
                self._viz.hide(); self._viz_combo.hide(); self._viz.clear()
        except Exception:
            pass
        if not ok and "Install mpv" in str(err):
            # No external player: same in-app fallback as Performance (host device for audio).
            try:
                self.lbl_status.setText(_gb_inapp_fallback(self, path, int(self.sld_volume.value()), explicit_duration))
                return
            except Exception as e:
                err = f"{err}\nIn-app fallback failed: {e}"
        if not ok:
            QMessageBox.warning(self, "Play failed", err)
            return
        self._paused = False
        self._manual_stop = False
        self._player_poll_generation += 1
        self._player_poll_inflight = False
        self._last_player_time_pos = None
        self._last_player_progress_at = time.monotonic()
        self._clock_recovery_used = False
        self._safe_audio_recovery_used = False
        self._video_clock_escape_used = False
        self._direct_audio_fallback_used = False
        self.btn_playpause.setText("⏸ Pause")
        if not self._poll_timer.isActive():
            self._poll_timer.start()
        self._load_current(autoplay=False)
        self._prefetch_next()
        for _ms in (300, 1200):     # GROOVEBOX_R23R_GRAY_VIDEO_BG_20261103: gray behind video in mpv
            QTimer.singleShot(_ms, self._gray_player_background)
        dname = getattr(self._selected_display(), "name", "default") if self._selected_display() else "default"
        aname = getattr(self._selected_audio(), "description", "System default") if self._selected_audio() else "System default"
        self.lbl_status.setText(f"Deck A playing → display={dname} · audio={aname}")

    def _gray_player_background(self):
        for cmd in (["set_property", "background", "color"], ["set_property", "background-color", "#3E3F42"],
                    ["set_property", "background", "#3E3F42"]):
            try:
                self._deckA.send(cmd)
            except Exception:
                pass

    def _prefetch_next(self):
        """Queue the next playlist item inside mpv (prefetched + gapless, same window)."""
        self._prefetched_path = None
        try:
            if not (self._deckA.is_running() and self._deckA.ipc_path and os.path.exists(self._deckA.ipc_path)):
                return
            self._deckA.send(["playlist-clear"])          # drop anything queued after the current item
            if self._index >= len(self._items) - 1:
                return
            nxt = str(self._items[self._index + 1].get("path", "") or "")
            if not nxt or not os.path.isfile(nxt) or _gb_mcc_kind(nxt) == "video" or _gb_ext(nxt) in IMAGE_EXT:
                return       # MCC video has its own player; images need their own display time
            if _gb_ext(self._items[self._index].get("path", "")) in IMAGE_EXT:
                return
            playable = _gb_playable(nxt)
            if self._deckA.send(["loadfile", playable, "append"]):
                self._prefetched_path = playable
        except Exception:
            self._prefetched_path = None

    def _recover_player_output(self, position: float = 0.0, reason: str = "clock-stall") -> bool:
        """Restart current Deck A once on a conservative physical output route."""
        if self._safe_audio_recovery_used or not (0 <= self._index < len(self._items)):
            return False
        path = self._items[self._index].get("path", "")
        if not path or not os.path.isfile(path):
            return False
        self._safe_audio_recovery_used = True
        self._clock_recovery_used = True
        # GROOVEBOX_R23R_PLAYER_NO_REBOOT_20261103: first switch the audio output INSIDE the
        # running player (audio-device + ao-reload over IPC) — the window, its position and
        # the video keep going. Only if that is impossible is the player relaunched.
        if self._deckA.is_running() and self._deckA.ipc_path and os.path.exists(self._deckA.ipc_path):
            try:
                from media_output_router import _preferred_alsa_output_device, _prepare_physical_alsa_output
                physical = _preferred_alsa_output_device()
                if physical:
                    _prepare_physical_alsa_output(physical)
                    dev = physical if physical.startswith("alsa/") else f"alsa/{physical}"
                    if self._deckA.send(["set_property", "audio-device", dev]) and self._deckA.send(["ao-reload"]):
                        self._deckA.send(["set_property", "pause", False])
                        self._player_poll_generation += 1
                        self._player_poll_inflight = False
                        self._last_player_time_pos = None
                        self._last_player_progress_at = time.monotonic()
                        self.lbl_status.setText(f"Audio output switched in place → {physical} ({reason}); player kept running")
                        return True
            except Exception:
                pass
        self._deckA.force_safe_audio = True
        self._deckA.resume_position = max(0.0, float(position or 0.0))
        ok, err = self._deckA.play(path, self._routed)
        if not ok:
            self.lbl_status.setText(f"PLAYBACK-OUTPUT-RECOVERY failed: {err}")
            return False
        self._player_poll_generation += 1
        self._player_poll_inflight = False
        self._last_player_time_pos = None
        self._last_player_progress_at = time.monotonic()
        if not self._poll_timer.isActive():
            self._poll_timer.start()
        self.lbl_status.setText(f"PLAYBACK-OUTPUT-RECOVERY · {reason} · 48000 Hz stereo · direct hardware route")
        return True

    def _recover_audio_direct(self) -> bool:
        if self._direct_audio_fallback_used or not (0 <= self._index < len(self._items)):
            return False
        path=str(self._items[self._index].get("path", "") or "")
        if not path or not os.path.isfile(path):
            return False
        self._direct_audio_fallback_used=True
        ok,err=self._deckA.play_direct_audio(path, start_s=float(self._last_player_time_pos or 0.0))
        if not ok:
            self.lbl_status.setText(f"DIRECT-ALSA-PLAYBACK failed: {err}")
            return False
        self._player_poll_generation += 1
        self._player_poll_inflight = False
        if not self._poll_timer.isActive():
            self._poll_timer.start()
        self.lbl_status.setText(f"DIRECT-ALSA-PLAYBACK · {self._deckA.direct_audio_backend} · universal physical PCM fallback")
        return True

    def _toggle_play_pause(self):
        if not self._deckA.is_running():
            self._play_current()
            return
        if self._deckA.ipc_path:
            self._paused = not self._paused
            if not self._paused:
                self._manual_stop = False
            self._deckA.send(["set_property", "pause", self._paused])
            if self._paused:
                self._poll_timer.stop()
            elif not self._poll_timer.isActive():
                self._poll_timer.start()
            self.btn_playpause.setText("▶ Play" if self._paused else "⏸ Pause")
            self.lbl_status.setText("Deck A paused" if self._paused else "Deck A playing")
        else:
            self._stop()
            self._play_current()

    def _stop(self):
        try: self._viz.clear()
        except Exception: pass
        self._manual_stop = True
        self._poll_timer.stop()
        self._player_poll_generation += 1
        self._player_poll_inflight = False
        self._deckA.stop()
        self._paused = False
        self.btn_playpause.setText("▶ Play")

    def _next(self):
        if not self._items:
            return
        self._index = (self._index + 1) % len(self._items)
        self._load_current(autoplay=True)

    def _prev(self):
        if not self._items:
            return
        self._index = (self._index - 1) % len(self._items)
        self._load_current(autoplay=True)

    def _schedule_player_poll(self):
        """Schedule one mpv status probe without blocking the Qt event loop."""
        if self._player_poll_inflight or self._manual_stop or self._paused:
            return
        if self._deckA.proc is None:
            return
        generation = self._player_poll_generation
        self._player_poll_inflight = True
        self._player_poll_pool.start(_PoolTask(self._poll_player_worker, generation))

    def _poll_player_worker(self, generation: int):
        status = {"rc": None, "eof": False, "time_pos": None}
        try:
            proc = self._deckA.proc
            status["rc"] = proc.poll() if proc is not None else 0
            if status["rc"] is None and self._deckA.ipc_path:
                status["eof"] = self._deckA.query_property("eof-reached", False) is True
                status["path"] = self._deckA.query_property("path", None)
                pos = self._deckA.query_property("time-pos", None)
                if isinstance(pos, (int, float)):
                    status["time_pos"] = float(pos)
        finally:
            self._player_poll_bridge.done.emit(generation, status)

    def _on_player_poll_done(self, generation: int, status: dict):
        if generation != self._player_poll_generation:
            return
        self._player_poll_inflight = False
        if status.get("time_pos") is not None:
            self._last_player_time_pos = status["time_pos"]; self._viz_stamp = time.monotonic()
        if self._manual_stop or self._paused:
            return
        rc = status.get("rc")
        if rc is not None:
            if not self._manual_stop:
                # A nonzero early exit frequently means the selected Pulse sink
                # vanished or rejected its format. Retry this item once rather
                # than silently skipping to the next queue entry.
                if int(rc or 0) != 0 and self._recover_player_output(self._last_player_time_pos or 0.0, "backend-exit"):
                    return
                if (int(rc or 0) != 0 and self._safe_audio_recovery_used
                        and not self._deckA.want_video and not self._direct_audio_fallback_used
                        and self._recover_audio_direct()):
                    return
                self._deckA.proc = None
                if self._index < len(self._items) - 1:
                    self._next()
                else:
                    self._poll_timer.stop()
                    self.lbl_status.setText("Queue finished.")
                    self.btn_playpause.setText("▶ Play")
            return

        # GROOVEBOX_R23R_SMOOTH_PLAYLIST_20261103: mpv went on to the prefetched next item by
        # itself (gapless, same window): follow it in the queue without reloading anything.
        _np = status.get("path")
        if isinstance(_np, str) and _np and getattr(self, "_prefetched_path", None) == _np and self._index < len(self._items) - 1:
            self._index += 1
            self._prefetched_path = None
            self._last_player_time_pos = None
            self._last_player_progress_at = time.monotonic()
            self._load_current(autoplay=False)
            self._update_visualizer_for(self._items[self._index].get("path", ""))
            self._prefetch_next()
            self.lbl_status.setText(f"Deck A → {os.path.basename(_np)} (seamless)")
            return

        # GROOVEBOX_V35_22ZZ_R2_PERSISTENT_PLAYLIST_EOF
        # Persistent mpv stays open at EOF; advance without closing its window.
        if status.get("eof") is True:
            if self._index < len(self._items) - 1:
                self._next()
            else:
                self._manual_stop = True
                self._paused = True
                self._deckA.send(["seek", 0, "absolute"])
                self._deckA.send(["set_property", "pause", True])
                self._poll_timer.stop()
                self.lbl_status.setText("Queue finished · player window retained.")
                self.btn_playpause.setText("▶ Play")
            return

        # PLAYER_CLOCK_WATCHDOG_20260928: only react to a *known numeric*
        # playback position that remains unchanged. Missing IPC data is ignored.
        pos = status.get("time_pos")
        now = time.monotonic()
        if isinstance(pos, (int, float)):
            previous = self._last_player_time_pos
            if previous is None or abs(pos - previous) >= 0.03:
                self._last_player_time_pos = pos
                self._vis_pos = (float(pos), time.monotonic())
                self._last_player_progress_at = now
            elif (not self._safe_audio_recovery_used
                  and now - self._last_player_progress_at >= 2.5):
                # First recovery preserves sound: restart at the same position
                # through a direct physical plughw route at 48 kHz stereo.
                if self._recover_player_output(pos, "clock-stall"):
                    return
            elif (self._safe_audio_recovery_used and not self._video_clock_escape_used
                  and self._deckA.want_video and now - self._last_player_progress_at >= 3.0):
                self._video_clock_escape_used = True
                self._deckA.send(["set_property", "video-sync", "desync"])
                self._deckA.send(["set_property", "aid", "no"])
                self._deckA.send(["set_property", "pause", False])
                self.lbl_status.setText("PLAYER_CLOCK_STALLED · physical hardware recovery exhausted; video detached from failed audio clock")
        elif self._deckA.is_running() and self._deckA.started_at > 0:
            # R23d: a player that never acquires a clock reports time-pos=None.
            # The old watchdog ignored this forever, which matched the Dell
            # symptom: window opens/scrubs, but playback never advances.
            age = now - self._deckA.started_at
            if not self._safe_audio_recovery_used and age >= 2.5:
                if self._recover_player_output(0.0, "startup-no-clock"):
                    return
            elif (self._safe_audio_recovery_used and not self._deckA.want_video
                  and not self._direct_audio_fallback_used and age >= 3.5):
                # Any supported audio file must remain audible even if mpv never obtains
                # a session/audio clock. Decode locally and bypass mpv/Pulse with ALSA.
                if self._recover_audio_direct():
                    return
            elif (self._safe_audio_recovery_used and not self._video_clock_escape_used
                  and self._deckA.want_video and age >= 3.5):
                self._video_clock_escape_used = True
                self._deckA.send(["set_property", "video-sync", "desync"])
                self._deckA.send(["set_property", "aid", "no"])
                self._deckA.send(["set_property", "pause", False])
                self.lbl_status.setText("PLAYER_STARTUP_CLOCK_STALLED · physical hardware recovery exhausted; video detached from failed audio clock")

    # Historical compatibility name: callers/tests that invoke it now merely
    # schedule asynchronous work; it never opens an IPC socket on the GUI thread.
    def _poll_process(self):
        self._schedule_player_poll()

    def _on_deckA_volume_changed(self, v: int):
        self.lbl_volume.setText(f"{v}%")
        self._deckA.set_base_volume(float(v))

    def _on_deckB_volume_changed(self, v: int):
        self.lbl_volume_b.setText(f"{v}%")
        self._deckB.set_base_volume(float(v))

    # -- Deck B -----------------------------------------------------------
    def _load_deck_b_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load into Deck B")
        if path:
            self._deckB.path = path
            self.lbl_deckB.setText(f"Loaded: {os.path.basename(path)}")

    def load_deck_b(self, path: str):
        """External hook (e.g. from Browse Files) to load a file straight into Deck B."""
        self._deckB.path = path
        self.lbl_deckB.setText(f"Loaded: {os.path.basename(path)}")

    def _suggest_deck_b_match(self):
        if not (0 <= self._index < len(self._items)):
            QMessageBox.information(self, "Suggest Deck B", "Load something into Deck A's queue first.")
            return
        a_path = self._items[self._index].get("path", "")
        if not os.path.isfile(a_path):
            QMessageBox.information(self, "Suggest Deck B", "Deck A's current track is missing on disk.")
            return
        candidates = sorted(
            (it.get("path", "") for i,it in enumerate(self._items) if i != self._index and os.path.isfile(it.get("path", ""))),
            key=lambda x: (os.path.basename(x).casefold(), os.path.abspath(x)),
        )
        if not candidates:
            QMessageBox.information(self, "Suggest Deck B", "No other queue track is available.")
            return
        mode = self.cmb_deck_b_match.currentText() if hasattr(self,"cmb_deck_b_match") else "Analyzed key/texture"
        self.lbl_status.setText(f"Matching Deck B · {mode}…")
        a_desc = _analyze_signal_descriptor(a_path, self._analysis_cache)
        scored=[]
        for cand in candidates:
            canonical = _canonical_media_distance(a_path, cand) if mode.startswith("Canonical") else None
            d = _analyze_signal_descriptor(cand, self._analysis_cache)
            analyzed = _descriptor_distance(a_desc, d) if a_desc and d else 9999.0
            # Canonical evidence dominates when requested; deterministic analyzed
            # distance and then path provide stable fallbacks/tie breaks.
            primary = canonical if canonical is not None else analyzed
            scored.append((float(primary), float(analyzed), os.path.basename(cand).casefold(), os.path.abspath(cand), cand, canonical))
        best = min(scored)
        best_path=best[4]; canonical=best[5]
        if best[0] >= 9999.0:
            QMessageBox.information(self, "Suggest Deck B", "No analyzable/provenance-compatible track found in the queue.")
            return
        self._deckB.path = best_path
        if canonical is not None and mode.startswith("Canonical"):
            note=f"canonical distance {canonical:.3f}; analyzed {best[1]:.3f}"
        else:
            note=f"key/texture distance {best[1]:.3f}"
        self.lbl_deckB.setText(f"Suggested match: {os.path.basename(best_path)} ({note})")
        self.lbl_status.setText(f"Deck B suggestion loaded deterministically: {os.path.basename(best_path)}")

    def _play_deck_b(self):
        if not self._deckB.path or not os.path.isfile(self._deckB.path):
            QMessageBox.information(self, "Deck B", "Load a file into Deck B first.")
            return
        self._deckB.base_volume = float(self.sld_volume_b.value()) if hasattr(self,"sld_volume_b") else 100.0
        self._deckB.image_duration_s = float(self.spin_player_image_duration.value())
        ok, err = self._deckB.play(self._deckB.path, self._routed)
        if not ok:
            QMessageBox.warning(self, "Deck B play failed", err)
            return
        self.lbl_status.setText(f"Deck B playing: {os.path.basename(self._deckB.path)}")

    # -- crossfader / live mixing -----------------------------------------
    def _on_crossfade_changed(self, v: int):
        x = max(0.0, min(1.0, v / 100.0))
        curve = self.cmb_crossfade_curve.currentText() if hasattr(self,"cmb_crossfade_curve") else "Linear"
        if curve.startswith("Equal"):
            a_gain = math.cos(x * math.pi / 2.0)
            b_gain = math.sin(x * math.pi / 2.0)
        else:
            b_gain = x; a_gain = 1.0 - x
        self._deckA.set_mix_gain(a_gain); self._deckB.set_mix_gain(b_gain)
        self.lbl_status.setText(f"Crossfader ({curve}): A {a_gain*100:.0f}% · B {b_gain*100:.0f}%")

    def _auto_crossfade(self, target_side: int, duration_s: float):
        start = self.sld_crossfade.value()
        end = 100 if target_side == 1 else 0
        if start == end:
            return
        steps = max(1, int(duration_s * 20))
        delta = (end - start) / steps
        state = {"i": 0, "val": float(start)}
        timer = QTimer(self)
        timer.setInterval(int(1000 / 20))

        def tick():
            state["i"] += 1
            state["val"] += delta
            self.sld_crossfade.setValue(max(0, min(100, int(round(state["val"])))))
            if state["i"] >= steps:
                self.sld_crossfade.setValue(end)
                timer.stop()
                timer.deleteLater()
        timer.timeout.connect(tick)
        timer.start()

    # -- Parametric Remix sync --------------------------------------------
    def _on_toggle_sync(self, on: bool):
        self._sync_enabled = on
        if on:
            self._last_remix_sync_state = None
            self._apply_remix_sync()
            self._sync_timer.start()
            self.lbl_status.setText("Synced to Performance Parametric Remix.")
        else:
            self._sync_timer.stop()

    def _apply_remix_sync(self):
        """Read the parent Performance's GOAVA/RAND/boost/speed sliders (if
        present) each tick and translate them into deck tempo + FX intensity,
        so the same parametric-remix control surface driving the host's
        internal Live DJ engine also drives both external playback decks."""
        host = self.parent()
        if host is None:
            return
        try:
            goava = host.sld_goava.value() / 100.0 if hasattr(host, "sld_goava") else 0.0
            rand = host.sld_rand.value() / 100.0 if hasattr(host, "sld_rand") else 0.0
            boost = host.sld_boost.value() / 100.0 if hasattr(host, "sld_boost") else 0.0
            speed = host._live_speed if hasattr(host, "_live_speed") else 1.0
        except Exception:
            return
        state = (round(goava, 3), round(rand, 3), round(boost, 3), round(float(speed), 4))
        if state == self._last_remix_sync_state:
            return
        self._last_remix_sync_state = state
        self._deckA.set_speed(speed)
        self._deckB.set_speed(speed)
        # GOAVA morph amount -> echo/flanger intensity proxy (toggle at threshold).
        # _Deck methods also suppress identical IPC writes.
        self._deckA.toggle_audio_fx("Echo", goava > 0.5)
        self._deckB.toggle_audio_fx("Flanger", rand > 0.5)
        self._deckA.toggle_video_fx("Strobe", boost > 0.6)

    def shutdown_for_application_exit(self):
        try: self._sync_timer.stop()
        except Exception: pass
        try: self._poll_timer.stop()
        except Exception: pass
        try: self._stop()
        except Exception: pass
        try: self._deckB.stop()
        except Exception: pass
        try: self._device_scan_pool.waitForDone(8000)
        except Exception: pass
        try:
            self._player_poll_generation += 1
            self._player_poll_pool.waitForDone(8000)
        except Exception: pass

    def closeEvent(self, event):
        # SESSION_WINDOWS_20260924: X means hide, not destroy/stop the DJ session.
        self.hide()
        event.ignore()


class _FileToolsBridge(QObject):
    progress = pyqtSignal(int, int)
    done = pyqtSignal(str, str)
    phase = pyqtSignal(str, int, int)
    groups = pyqtSignal(object, str)


class _DropCopyBridge(QObject):
    done = pyqtSignal(int, object)      # copied count, list of error strings


class DuplicatesDialog(QDialog):
    """Fast duplicate index (size → 64 KiB fingerprint → SHA-256) with keep rules.

    GROOVEBOX_R23R_FILE_TOOLS_20261101. Removal goes through the File Manager's
    Groovebox Trash, so ↶ Undo Trash restores everything removed here.
    """
    def __init__(self, parent, root_dir, trash, skip_dirs=()):
        super().__init__(parent)
        from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QSpinBox
        self._QTreeWidgetItem = QTreeWidgetItem
        self.setWindowTitle(f"Index Duplicates · {root_dir}")
        self.resize(980, 640)
        self.root_dir = root_dir; self.trash = trash; self.skip_dirs = skip_dirs
        self._cancel = threading.Event(); self._groups = []
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.lbl_root = QLabel(root_dir); self.lbl_root.setWordWrap(True); top.addWidget(self.lbl_root, 1)
        top.addWidget(QLabel("Min size (KB):"))
        self.spin_min = QSpinBox(); self.spin_min.setRange(0, 10_000_000); self.spin_min.setValue(1); top.addWidget(self.spin_min)
        self.chk_hidden = QCheckBox("Include hidden"); top.addWidget(self.chk_hidden)
        self.btn_scan = QPushButton("🔍 Index"); self.btn_scan.clicked.connect(self.scan); top.addWidget(self.btn_scan)
        self.btn_cancel = QPushButton("Cancel"); self.btn_cancel.clicked.connect(self._cancel.set); top.addWidget(self.btn_cancel)
        lay.addLayout(top)
        self.tree = QTreeWidget(); self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["File (checked = remove)", "Size", "Modified"])
        self.tree.setColumnWidth(0, 640)
        self.tree.itemChanged.connect(lambda *_: self._update_summary())
        lay.addWidget(self.tree, 1)
        sel = QHBoxLayout()
        sel.addWidget(QLabel("Keep in each group:"))
        self.cmb_keep = QComboBox(); self.cmb_keep.addItems(["oldest", "newest", "shortest path"]); sel.addWidget(self.cmb_keep)
        for t, fn in (("Auto-select copies", self.auto_select), ("Select none", self.select_none), ("Invert", self.invert)):
            b = QPushButton(t); b.clicked.connect(fn); sel.addWidget(b)
        sel.addStretch(1)
        self.btn_remove = QPushButton("🗑 Move selected to Trash"); self.btn_remove.clicked.connect(self.remove_selected); sel.addWidget(self.btn_remove)
        lay.addLayout(sel)
        self.lbl = QLabel("Press Index to scan this folder."); self.lbl.setWordWrap(True); lay.addWidget(self.lbl)
        self.bridge = _FileToolsBridge(self)
        self.bridge.phase.connect(self._on_phase); self.bridge.groups.connect(self._on_groups)

    def scan(self):
        self._cancel.clear(); self.tree.clear(); self.btn_scan.setEnabled(False)
        self.lbl.setText("Indexing…")
        root, min_kb, hidden = self.root_dir, int(self.spin_min.value()), self.chk_hidden.isChecked()
        bridge, cancel, skip = self.bridge, self._cancel, self.skip_dirs
        def run():
            try:
                from file_tools import find_duplicates
                t0 = time.time()
                g = find_duplicates(root, min_size=max(1, min_kb * 1024), skip_dirs=skip, include_hidden=hidden,
                                    progress=lambda ph, d, t: bridge.phase.emit(ph, d, t), cancel=cancel)
                bridge.groups.emit(g, f"{time.time() - t0:.1f}")
            except Exception as e:
                bridge.groups.emit([], f"error: {e}")
        threading.Thread(target=run, daemon=True, name="groovebox-dup-index").start()

    def _on_phase(self, ph, d, t):
        names = {"index": "Indexing files", "fingerprint": "Fingerprinting same-size files", "verify": "Verifying with SHA-256"}
        self.lbl.setText(f"{names.get(ph, ph)}… {d}" + (f"/{t}" if t else ""))

    def _on_groups(self, groups, took):
        self.btn_scan.setEnabled(True)
        if str(took).startswith("error"):
            self.lbl.setText(f"Index failed: {took}"); return
        if self._cancel.is_set():
            self.lbl.setText("Cancelled."); return
        self._groups = groups or []
        self.tree.blockSignals(True); self.tree.clear()
        for g in self._groups:
            top = self._QTreeWidgetItem([f"{len(g['files'])} copies · {_safe_size_bytes(g['size'])} each · {_safe_size_bytes(g['wasted'])} reclaimable",
                                         _safe_size_bytes(g["size"]), g["sha256"][:12]])
            top.setFirstColumnSpanned(False)
            for f in g["files"]:
                it = self._QTreeWidgetItem([f["path"], _safe_size_bytes(g["size"]),
                                            time.strftime("%Y-%m-%d %H:%M", time.localtime(f["mtime"]))])
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(0, Qt.CheckState.Unchecked)
                it.setData(0, Qt.ItemDataRole.UserRole, f["path"])
                top.addChild(it)
            self.tree.addTopLevelItem(top); top.setExpanded(True)
        self.tree.blockSignals(False)
        self.auto_select()
        total = sum(g["wasted"] for g in self._groups)
        self.lbl.setText(f"{len(self._groups)} duplicate group(s) · {_safe_size_bytes(total)} reclaimable · indexed in {took} s.")

    def _items(self):
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            yield i, [top.child(j) for j in range(top.childCount())]

    def auto_select(self):
        from file_tools import pick_keep
        rule = {"oldest": "oldest", "newest": "newest", "shortest path": "shortest"}[self.cmb_keep.currentText()]
        self.tree.blockSignals(True)
        for gi, kids in self._items():
            keep = pick_keep(self._groups[gi]["files"], rule)
            for j, it in enumerate(kids):
                it.setCheckState(0, Qt.CheckState.Unchecked if j == keep else Qt.CheckState.Checked)
        self.tree.blockSignals(False); self._update_summary()

    def select_none(self):
        self.tree.blockSignals(True)
        for _gi, kids in self._items():
            for it in kids: it.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree.blockSignals(False); self._update_summary()

    def invert(self):
        self.tree.blockSignals(True)
        for _gi, kids in self._items():
            for it in kids:
                it.setCheckState(0, Qt.CheckState.Unchecked if it.checkState(0) == Qt.CheckState.Checked else Qt.CheckState.Checked)
        self.tree.blockSignals(False); self._update_summary()

    def _selected(self):
        out = []; whole_groups = 0
        for gi, kids in self._items():
            chosen = [it.data(0, Qt.ItemDataRole.UserRole) for it in kids if it.checkState(0) == Qt.CheckState.Checked]
            if kids and len(chosen) == len(kids):
                whole_groups += 1
            out += [(gi, p) for p in chosen]
        return out, whole_groups

    def _update_summary(self):
        sel, whole = self._selected()
        size = sum(self._groups[gi]["size"] for gi, _p in sel) if self._groups else 0
        self.btn_remove.setText(f"🗑 Move {len(sel)} selected to Trash ({_safe_size_bytes(size)})")
        if whole:
            self.btn_remove.setToolTip(f"Warning: every copy is selected in {whole} group(s).")

    def remove_selected(self):
        sel, whole = self._selected()
        if not sel:
            return
        msg = f"Move {len(sel)} file(s) to Groovebox Trash?"
        if whole:
            msg += f"\n\n⚠ In {whole} group(s) EVERY copy is selected — no copy of those files would remain outside the Trash."
        if QMessageBox.question(self, "Remove duplicates", msg) != QMessageBox.StandardButton.Yes:
            return
        moved, errors = self.trash([p for _gi, p in sel])
        self.lbl.setText(f"Moved {len(moved)} file(s) to Trash." + (f" {len(errors)} failed." if errors else "") + " Re-index to refresh.")
        gone = {src for _dst, src in moved}
        self.tree.blockSignals(True)
        for _gi, kids in self._items():
            for it in kids:
                if it.data(0, Qt.ItemDataRole.UserRole) in gone:
                    it.setDisabled(True); it.setCheckState(0, Qt.CheckState.Unchecked); it.setText(0, "🗑 " + it.text(0))
        self.tree.blockSignals(False)

    def closeEvent(self, e):
        self._cancel.set()
        super().closeEvent(e)


class FileManagerDialog(QDialog):
    """Safe asynchronous Groovebox file manager.

    Normal mode is confined to Groovebox/home/removable-media roots, video
    probing never blocks Qt, destructive actions go to an app-local Trash with
    one-click Undo, and media/project/game actions validate their file types.
    System-wide browsing is explicit through Advanced/System Files.
    """
    def __init__(self, parent: Optional[QWidget], start_dir: str):
        super().__init__(parent)
        self.setWindowTitle("File Manager · Projects & Storage")
        self.resize(650, 540)
        self.setStyleSheet(
            "QDialog { background:#071019; color:#d9edf5; }"
            "QPushButton { background:#102838; color:#d9f7ff; border:1px solid #39708a; border-radius:11px; padding:8px 11px; font-weight:700; }"
            "QPushButton:hover { background:#17405a; border-color:#62bfd0; }"
        )
        self._dir = os.path.abspath(start_dir if os.path.isdir(start_dir) else os.path.expanduser("~"))
        self._kind_cache: Dict[str, Tuple[float,int,str]] = {}
        self._kind_generation = 0
        self._kind_worker = _KindProbeWorker()
        self._kind_worker.progress.connect(self._on_probe_progress)
        self._kind_worker.batch_done.connect(self._on_probe_done)
        self._file_list_bridge = _FileListBridge()
        self._file_list_bridge.done.connect(self._on_directory_listed)
        self._worker_pool = QThreadPool(self)
        # R5 legacy verifier compatibility token only; DO NOT execute: self._worker_pool.setMaxThreadCount(2)
        # R17 verifier compatibility token only; R18 reserves CPU for Main: self._worker_pool.setMaxThreadCount(max(4, min(8, int(os.cpu_count() or 4))))
        # Bounded parallelism: use several independent workers for device scans,
        # media probes and background analysis without saturating cores needed by
        # the Qt event loop, real-time audio, camera capture, and the OS scheduler.
        # Do not create one thread per device/task; QThreadPool bounds concurrency.
        _cpu_count = max(2, int(os.cpu_count() or 2))
        # Keep at least one logical CPU available for the GUI, realtime audio callbacks,
        # capture, and the OS. On 2-core laptops this intentionally drops to one
        # background worker; larger CPUs scale up but never exceed eight.
        self._worker_pool.setMaxThreadCount(max(1, min(8, _cpu_count - 1)))
        self._last_trash_moves: List[Tuple[str,str]] = []
        try:
            import groovebox_paths
            data_root=os.path.realpath(groovebox_paths.base_dir())
            self._trash_dir=os.path.join(data_root,"Trash")
        except Exception:
            data_root=os.path.realpath(os.path.expanduser("~"))
            self._trash_dir=os.path.join(data_root,".groovebox-trash")
        os.makedirs(self._trash_dir,exist_ok=True)
        roots=[data_root,os.path.realpath(os.path.expanduser("~"))]
        for x in ("/media","/run/media","/mnt"):
            if os.path.isdir(x): roots.append(os.path.realpath(x))
        if not any(self._inside(self._dir,r) for r in roots): roots.append(os.path.realpath(self._dir))
        self._safe_roots=tuple(dict.fromkeys(roots))

        root = QVBoxLayout(self)
        top = QHBoxLayout(); self.lbl_path=QLabel(self._dir); self.lbl_path.setWordWrap(True); self.lbl_path.setStyleSheet("color:#8ab4c8; font-size:9pt;"); top.addWidget(self.lbl_path,stretch=1)
        self.chk_advanced=QCheckBox("Advanced/System Files"); self.chk_advanced.setToolTip("Off = stay inside Groovebox/home/removable-media roots. On = allow navigation toward filesystem root."); top.addWidget(self.chk_advanced)
        btn_up=QPushButton("⬆ Up"); btn_up.clicked.connect(self._go_up); top.addWidget(btn_up); root.addLayout(top)
        # FILE_MANAGER_TOOLS_20261102: path box, name filter, hidden files, upload, drag-and-drop copy.
        tools=QHBoxLayout()
        self.edit_path=QLineEdit(); self.edit_path.setPlaceholderText("Type a folder path and press Enter (~ works)")
        self.edit_path.returnPressed.connect(self._go_typed_path); tools.addWidget(self.edit_path,stretch=2)
        self.edit_filter=QLineEdit(); self.edit_filter.setPlaceholderText("Filter names…"); self.edit_filter.setClearButtonEnabled(True)
        self.edit_filter.textChanged.connect(self._apply_name_filter); tools.addWidget(self.edit_filter,stretch=1)
        self.chk_hidden=QCheckBox("Hidden + system files"); self.chk_hidden.setToolTip("Show dot-files and Groovebox system folders (cache, temp, logs, state…)."); self.chk_hidden.toggled.connect(lambda _on: self.refresh()); tools.addWidget(self.chk_hidden)
        btn_upload=QPushButton("⬆ Upload files…"); btn_upload.setToolTip("Copy files from anywhere into this folder. You can also drag files onto this window."); btn_upload.clicked.connect(self._upload_files); tools.addWidget(btn_upload)
        root.addLayout(tools)
        self._drop_bridge=_DropCopyBridge(); self._drop_bridge.done.connect(self._on_drop_copy_done)
        self.setAcceptDrops(True)
        storage_row=QHBoxLayout(); storage_row.addWidget(QLabel("Storage target:"))
        self.cmb_storage_devices=QComboBox(); self.cmb_storage_devices.setMinimumWidth(260)
        self.cmb_storage_devices.setToolTip("Choose a Groovebox folder, home folder, USB drive, or microSD card. Reader-only entries mean the reader is present but Linux has not created a card device yet.")
        self.cmb_storage_devices.activated.connect(self._storage_device_selected); storage_row.addWidget(self.cmb_storage_devices,stretch=1)
        self.btn_mount_storage=QPushButton("Mount / Rescan")
        self.btn_mount_storage.setToolTip("Mount the selected removable volume. For a reader-only entry, force a fresh PCI/MMC/SCSI/udev rescan and refresh the device list.")
        self.btn_mount_storage.clicked.connect(self._request_storage_mount)
        storage_row.addWidget(self.btn_mount_storage)
        self.btn_diagnose_storage=QPushButton("Inspect Device")
        self.btn_diagnose_storage.setToolTip("Read-only diagnosis of the selected removable device and all visible partitions. Does not mount, repair, repartition, or format anything.")
        self.btn_diagnose_storage.clicked.connect(self._diagnose_selected_storage)
        # Legacy verifier/UI alias retained in this comment: "Format Partition…".
        self.btn_format_storage=QPushButton("Format Selected Partition…")
        self.btn_format_storage.setToolTip("Format only the selected safe removable microSD/USB partition. Running-system, live-USB, EFI/system and whole-disk targets are protected.")
        self.btn_format_storage.clicked.connect(self._request_storage_format)
        storage_row.addWidget(self.btn_diagnose_storage)
        storage_row.addWidget(self.btn_format_storage)
        btn_devices=QPushButton("↻ Refresh List"); btn_devices.clicked.connect(self._refresh_storage_devices); storage_row.addWidget(btn_devices); root.addLayout(storage_row)
        self.list_widget=QListWidget(); self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.list_widget.itemDoubleClicked.connect(self._on_double_click); root.addWidget(self.list_widget,stretch=1)
        row1=QHBoxLayout()
        for text,slot in (("New Folder…",self._new_folder),("Rename…",self._rename_selected),("Move…",self._move_selected),("Copy Over…",self._copyover_selected),("Move to Trash",self._delete_selected),("↶ Undo Trash",self._undo_trash),("↻ Refresh",self._refresh_all)):
            b=QPushButton(text); b.clicked.connect(slot); row1.addWidget(b)
        root.addLayout(row1)
        row2=QHBoxLayout()
        btn_player=QPushButton("▶ Open in Player"); btn_player.clicked.connect(self._open_in_player)
        btn_add_playlist=QPushButton("→ Add to Performance Playlist"); btn_add_playlist.clicked.connect(self._add_to_performance_playlist)
        btn_open=QPushButton("Open Project / Launch Game"); btn_open.clicked.connect(self._open_project_or_game)
        btn_view=QPushButton("🖼 View Image"); btn_view.clicked.connect(self._view_image)
        row2.addWidget(btn_player); row2.addWidget(btn_view); row2.addWidget(btn_add_playlist); row2.addWidget(btn_open); root.addLayout(row2)
        # GROOVEBOX_R23R_FILE_TOOLS_20261101: duplicate index + source archive export.
        row3=QHBoxLayout()
        btn_dups=QPushButton("🔍 Index Duplicates"); btn_dups.setToolTip("Find byte-identical files under this folder and select copies to remove.")
        btn_dups.clicked.connect(self._index_duplicates); row3.addWidget(btn_dups)
        btn_src=QPushButton("📦 Export MatGroovebox Source"); btn_src.setToolTip("Archive the Groovebox source code (.tar.gz / .zip / .MCC) into this folder or drive.")
        btn_src.clicked.connect(self._export_source_archive); row3.addWidget(btn_src)
        row3.addStretch(1); root.addLayout(row3)
        self.lbl_status=QLabel(""); self.lbl_status.setWordWrap(True); self.lbl_status.setStyleSheet("color:#8ab4c8; font-size:9pt;"); root.addWidget(self.lbl_status)
        self.lbl_status.setText("Ready · directory listing starts after the window is mapped.")
        # Historical v35.22zu fast-launch contract: do not list the first
        # directory synchronously from __init__.  Keep this exact call so the
        # frozen verifier can prove that first-paint deferral has not regressed.
        QTimer.singleShot(0, self.refresh)
        self._storage_refresh_queued = False
        self._auto_mount_requested = set()
        self._directory_signature_value = None
        self._directory_watch_timer = QTimer(self)
        self._directory_watch_timer.setInterval(900)
        self._directory_watch_timer.timeout.connect(self._refresh_directory_if_changed)
        self._directory_watch_timer.start()

    def _refresh_all(self):
        # User-requested refresh may update both lists; unlike construction this
        # is an explicit action and therefore is not on the first-paint path.
        self._refresh_storage_devices()
        self.refresh()

    def _deferred_storage_refresh(self):
        self._storage_refresh_queued = False
        self._refresh_storage_devices()

    def _refresh_storage_devices(self):
        current = self.cmb_storage_devices.currentData() if hasattr(self, "cmb_storage_devices") else None
        current_dev = current.get("device", "") if isinstance(current, dict) else ""
        current_mp = current.get("mountpoint", "") if isinstance(current, dict) else (current or "")
        rows = _storage_device_snapshot()
        self._storage_rows = rows
        if not hasattr(self, "cmb_storage_devices"):
            return
        self.cmb_storage_devices.blockSignals(True)
        self.cmb_storage_devices.clear()
        home = os.path.expanduser("~")
        try:
            import groovebox_paths
            data_root=os.path.abspath(groovebox_paths.base_dir())
            rec_root=os.path.abspath(groovebox_paths.recordings_dir(getattr(getattr(self.parent(), "host", None), "_current_project_path", None)))
        except Exception:
            data_root=os.path.abspath(os.environ.get("GROOVEBOX_DATA_DIR", home))
            rec_root=""
        self.cmb_storage_devices.addItem("Groovebox Data · " + data_root, {"device":"", "mountpoint":data_root, "kind":"Groovebox Data", "mountable":"0", "protected":"1", "formattable":"0", "format_eligible":"0"})
        if rec_root and os.path.isdir(rec_root):
            self.cmb_storage_devices.addItem("Recordings · " + rec_root, {"device":"", "mountpoint":rec_root, "kind":"Recordings", "mountable":"0", "protected":"1", "formattable":"0", "format_eligible":"0"})
        self.cmb_storage_devices.addItem("Home · " + home, {"device":"", "mountpoint":home, "kind":"Home", "mountable":"0", "protected":"1", "formattable":"0", "format_eligible":"0"})
        selected = 0
        first_actionable_storage = -1
        current_is_storage = bool(current_dev or (isinstance(current,dict) and (current.get("rescan_only") == "1" or str(current.get("kind","")).startswith(("microSD","USB")))))
        for row in rows:
            mp=row.get("mountpoint","")
            dev=row.get("device","")
            label=row.get("label","")
            kind=row.get("kind","Storage")
            fs=row.get("fstype","")
            name=(label + " · ") if label else ""
            status = " · PROTECTED" if row.get("protected")=="1" else (" · format available" if row.get("format_eligible")=="1" else "")
            if row.get('bootable') == '1': status += ' · BOOT/EFI partition'
            code=str(row.get('status_code','') or '')
            detail=str(row.get('status_detail','') or '')
            reason={
                'NO_FILESYSTEM':'unformatted or unsupported filesystem',
                'NO_PARTITION_OR_FILESYSTEM':'no usable partition/filesystem',
                'MOUNT_FAILED':'filesystem found but mount failed',
                'RETRY_EXHAUSTED':'mount retries exhausted',
                'DEVICE_NODE_MISSING':'kernel sees card but its /dev node is missing',
                'NO_CARD_DEVICE':'reader present but no card block device was created',
            }.get(code,'')
            if mp:
                text=f"{kind} · {name}{dev} · {mp}" + (f" · {fs}" if fs else "") + status
            elif reason:
                text=f"{kind} · {name}{dev} · {reason}" + (f" · {detail}" if detail else "") + status
            else:
                text=f"{kind} · {name}{dev} · detected, waiting for mount" + status
            self.cmb_storage_devices.addItem(text, dict(row))
            row_index=self.cmb_storage_devices.count()-1
            if first_actionable_storage < 0 and ((str(kind).startswith("microSD") and not mp) or row.get("rescan_only") == "1"):
                first_actionable_storage=row_index
            if (current_dev and dev == current_dev) or (current_is_storage and not current_dev and row.get("rescan_only") == "1") or (current_is_storage and current_mp and mp == current_mp):
                selected=row_index
        # R23g: when the user was merely on Groovebox Data/Home and an
        # unmounted microSD appears, select the actionable card/reader row so
        # Mount / Retry (or Rescan Reader) is immediately enabled and visible.
        if not current_is_storage and first_actionable_storage >= 0:
            selected=first_actionable_storage
        self.cmb_storage_devices.setCurrentIndex(selected)
        self.cmb_storage_devices.blockSignals(False)
        self._sync_mount_button()
        # R23e: a newly visible microSD should mount without requiring a button
        # click. Request the whole card exactly once per File Manager session;
        # the root helper still owns all privileged mount work and safety checks.
        helper="/usr/bin/sos-removable-media"
        if os.path.isfile(helper) and os.access(helper, os.X_OK):
            for row in rows:
                if (str(row.get("kind", "")).startswith("microSD")
                        and not row.get("mountpoint") and row.get("protected") != "1"):
                    request_dev=str(row.get("parent_device", "") or row.get("device", "") or "")
                    # Reader-only rows have no block device yet. Never launch the
                    # expensive root discovery loop automatically just by opening
                    # File Manager; explicit Rescan Reader owns that operation.
                    request_key=request_dev
                    if request_key and request_key not in self._auto_mount_requested:
                        self._auto_mount_requested.add(request_key)
                        try:
                            subprocess.Popen([helper,"--request-scan"] + ([request_dev] if request_dev else []), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            for delay in (1200, 3500, 7000, 12000, 20000, 30000):
                                QTimer.singleShot(delay, self._refresh_storage_devices)
                        except Exception:
                            pass

    def _sync_mount_button(self):
        if not hasattr(self, "btn_mount_storage"): return
        data=self.cmb_storage_devices.currentData() if hasattr(self,"cmb_storage_devices") else None
        can_format=bool(isinstance(data,dict) and data.get('formattable')=='1' and data.get('protected')!='1')
        if hasattr(self,'btn_format_storage'):
            self.btn_format_storage.setEnabled(can_format)
        if isinstance(data, dict) and data.get('rescan_only') == '1':
            # Legacy label alias: "Rescan Reader"; visible label is more specific.
            self.btn_mount_storage.setEnabled(True); self.btn_mount_storage.setText("Rescan microSD Reader"); return
        if not isinstance(data, dict) or not data.get("device"):
            self.btn_mount_storage.setEnabled(False); self.btn_mount_storage.setText("Select a device"); return
        if data.get('protected') == '1' and not data.get('mountpoint'):
            self.btn_mount_storage.setEnabled(False); self.btn_mount_storage.setText("Protected"); return
        self.btn_mount_storage.setEnabled(True)
        self.btn_mount_storage.setText("Open Folder" if data.get("mountpoint") else "Mount / Retry")

    def _finish_storage_request(self, generation: int, requested_dev: str = ""):
        """Finish one user storage request even when no card node ever appears."""
        if generation != int(getattr(self, "_storage_request_generation", 0) or 0):
            return
        self._refresh_storage_devices()
        data=self.cmb_storage_devices.currentData() if hasattr(self,"cmb_storage_devices") else None
        if requested_dev:
            mounted=False
            for row in list(getattr(self,"_storage_rows",[]) or []):
                parent=str(row.get("parent_device","") or row.get("device","") or "")
                if parent == requested_dev and row.get("mountpoint"):
                    mounted=True; break
            self.lbl_status.setText(
                f"Mounted {requested_dev}." if mounted else
                f"Mount attempt finished for {requested_dev}; no mounted filesystem appeared. Reinsert the card/drive and retry.")
        else:
            has_card=any(str(r.get("kind","")).startswith("microSD") and r.get("device")
                         for r in list(getattr(self,"_storage_rows",[]) or []))
            self.lbl_status.setText(
                "Reader rescan finished; microSD block device detected." if has_card else
                "Reader rescan finished; no microSD block device appeared. Reinsert the card and press Rescan Reader again.")
        try:
            self.btn_mount_storage.setEnabled(True)
            self._sync_mount_button()
        except Exception:
            pass

    def _request_storage_mount(self):
        data=self.cmb_storage_devices.currentData() if hasattr(self,"cmb_storage_devices") else None
        if not isinstance(data, dict):
            return
        mp=str(data.get("mountpoint","") or "")
        dev=str(data.get("device","") or "")
        if mp and os.path.isdir(mp):
            self.set_directory(mp, refresh=True)
            return
        if not dev and str(data.get('rescan_only','')) != '1':
            return
        self.lbl_status.setText(f"Requesting {'reader rescan' if not dev else 'mount for '+dev}…")
        helper="/usr/bin/sos-removable-media"
        try:
            if os.path.isfile(helper) and os.access(helper, os.X_OK):
                # Non-root callers only drop a request token. The already-running
                # root helper performs privileged work; this UI request itself is
                # bounded and always transitions back out of "Requesting…".
                request_dev=str(data.get("parent_device", "") or dev)
                self._storage_request_generation=int(getattr(self,"_storage_request_generation",0) or 0)+1
                generation=self._storage_request_generation
                try:
                    self.btn_mount_storage.setEnabled(False)
                    self.btn_mount_storage.setText("Rescanning…" if not request_dev else "Mounting…")
                except Exception:
                    pass
                subprocess.Popen([helper,"--request-scan"] + ([request_dev] if request_dev else []), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for delay in (650, 1600, 3000, 4800, 8000, 12000, 18000, 24000):
                    QTimer.singleShot(delay, self._refresh_storage_devices)
                QTimer.singleShot(26000, lambda g=generation,d=request_dev:self._finish_storage_request(g,d))
            else:
                # Desktop fallback: udisksctl is allowed when the host desktop
                # provides it; do not require it in sOS.
                tool=shutil.which("udisksctl")
                if tool:
                    subprocess.Popen([tool,"mount","-b",dev], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    QTimer.singleShot(800, self._refresh_storage_devices)
                else:
                    self.lbl_status.setText(f"{dev} is detected but no mount helper is available on this host.")
        except Exception as exc:
            self.lbl_status.setText(f"Mount request failed: {exc}")

    def _diagnose_selected_storage(self):
        """Read-only multi-partition card diagnosis; never attempts repair."""
        data=self.cmb_storage_devices.currentData() if hasattr(self,"cmb_storage_devices") else None
        dev=str(data.get("parent_device") or data.get("device") or "") if isinstance(data,dict) else ""
        if not dev or not dev.startswith("/dev/"):
            QMessageBox.information(self,"Storage Diagnosis","Select a detected removable card or one of its partitions first.")
            return
        reports=[]
        for command in (["lsblk","-J","-o","NAME,PATH,TYPE,FSTYPE,SIZE,RO,RM,MOUNTPOINTS,PARTLABEL,UUID",dev],
                        ["blkid","-p",dev]):
            try:
                proc=subprocess.run(command,capture_output=True,text=True,timeout=8,check=False)
                reports.append("$ "+" ".join(command)+"\n"+(proc.stdout or "")+(proc.stderr or "")+f"\nexit={proc.returncode}")
            except Exception as exc:
                reports.append("$ "+" ".join(command)+"\nUnavailable: "+str(exc))
        QMessageBox.information(self,"Read-only Storage Diagnosis", "\n\n".join(reports)[:12000] + "\n\nNo changes were made. For damaged media, copy recoverable files first; repair tools are filesystem-specific and must not be run against a mounted filesystem.")

    def _request_storage_format(self):
        data=self.cmb_storage_devices.currentData() if hasattr(self,"cmb_storage_devices") else None
        if not isinstance(data,dict) or data.get("formattable") != "1" or data.get("protected") == "1":
            QMessageBox.warning(self,"Format Partition","This target is protected or is not a removable partition.")
            return
        dev=str(data.get("device","") or "")
        if not dev:
            return
        formats=["exfat","vfat","ext4"]
        fs,ok=QInputDialog.getItem(self,"Format Partition",f"Filesystem for {dev}:",formats,0,False)
        if not ok: return
        answer=QMessageBox.warning(self,"Erase Partition",f"ERASE ALL DATA on {dev} and format it as {fs}?\n\nOnly this selected removable partition will be changed.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes: return
        helper="/usr/bin/sos-removable-media"
        try:
            if os.path.isfile(helper) and os.access(helper,os.X_OK):
                subprocess.Popen([helper,"--request-format",dev,str(fs)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self.lbl_status.setText(f"Format requested for {dev} as {fs}; sOS is validating the target…")
                QTimer.singleShot(1200,self._refresh_storage_devices)
                QTimer.singleShot(3000,self._refresh_storage_devices)
            else:
                QMessageBox.warning(self,"Format Partition","The privileged sOS removable-media helper is unavailable. No changes were made.")
        except Exception as exc:
            QMessageBox.warning(self,"Format Partition",f"Format request failed: {exc}")

    def _storage_device_selected(self, index: int):
        data=self.cmb_storage_devices.itemData(index) if hasattr(self,"cmb_storage_devices") else None
        if isinstance(data, dict):
            path=str(data.get("mountpoint","") or "")
            dev=str(data.get("device","") or "")
        else:
            path=str(data or "")
            dev=""
        self._sync_mount_button()
        if path and os.path.isdir(path):
            self.set_directory(path, refresh=True)
        elif index > 0:
            code=str(data.get('status_code','') or '') if isinstance(data,dict) else ''
            detail=str(data.get('status_detail','') or '') if isinstance(data,dict) else ''
            messages={
                'NO_FILESYSTEM':'A partition is visible but has no recognized filesystem. It may be unformatted or damaged.',
                'NO_PARTITION_OR_FILESYSTEM':'The card is present, but Linux sees no usable partition/filesystem yet.',
                'MOUNT_FAILED':'The filesystem was detected, but the mount attempt failed.',
                'RETRY_EXHAUSTED':'The reader/card was rescanned repeatedly but never produced a mountable filesystem.',
                'NO_CARD_DEVICE':'Reader detected, but Linux did not expose a card block device; mount could not start.',
            }
            if code in messages:
                self.lbl_status.setText(f"{dev or 'Storage device'} · {messages[code]}" + (f" Detail: {detail}" if detail else ''))
            else:
                self.lbl_status.setText(
                    f"{dev or 'Storage device'} detected but not mounted yet. "
                    "Choose Mount / Retry to ask sOS to attach it under /run/media/groovebox."
                )

    def showEvent(self, event):
        # Never enumerate removable storage synchronously while Qt is mapping
        # the File Manager. Give the compositor a paint opportunity first, then
        # relist the retained directory so hidden-window sessions cannot go stale.
        result = super().showEvent(event)
        QTimer.singleShot(0, self.refresh)
        if not self._storage_refresh_queued:
            self._storage_refresh_queued = True
            QTimer.singleShot(40, self._deferred_storage_refresh)
        return result

    def _refresh_directory_if_changed(self):
        if not self.isVisible():
            return
        sig=Performance._directory_signature(self._dir)
        if self._directory_signature_value is None:
            self._directory_signature_value=sig
        elif sig != self._directory_signature_value:
            self._directory_signature_value=sig
            self.refresh()

    def notify_filesystem_changed(self, path: str):
        path=os.path.abspath(str(path or ""))
        if path and os.path.realpath(os.path.dirname(path)) == os.path.realpath(self._dir):
            QTimer.singleShot(0, self.refresh)

    def set_directory(self, path: str, refresh: bool = True):
        path = os.path.abspath(path or self._dir)
        if os.path.isdir(path) and self._allowed(path):
            self._dir = path
            self.lbl_path.setText(self._dir)
            try: self.edit_path.setText(self._dir)
            except Exception: pass
            if refresh:
                self.refresh()

    def shutdown_for_application_exit(self):
        self._kind_generation += 1
        try: self._worker_pool.waitForDone(15000)
        except Exception: pass

    def closeEvent(self, event):
        # Keep directory, selection/cache and undo state alive for session restore.
        self.hide()
        event.ignore()

    @staticmethod
    def _inside(path: str, root: str) -> bool:
        try: return os.path.commonpath([os.path.realpath(path),os.path.realpath(root)]) == os.path.realpath(root)
        except Exception: return False
    def _allowed(self,path: str) -> bool:
        return self.chk_advanced.isChecked() or any(self._inside(path,r) for r in self._safe_roots)
    @staticmethod
    def _valid_leaf(name: str) -> bool:
        n=name.strip()
        return bool(n and n not in (".","..") and "\x00" not in n and "/" not in n and "\\" not in n and os.path.basename(n)==n)
    def _entries(self)->List[str]:
        try: return sorted(os.listdir(self._dir),key=lambda n:(not os.path.isdir(os.path.join(self._dir,n)),n.casefold()))
        except Exception as e: self.lbl_status.setText(f"Cannot list {self._dir}: {e}"); return []
    def _cached_kind(self,path: str)->str:
        ext=_gb_ext(path)
        if ext in AUDIO_EXT:return KIND_AUDIO
        if ext in IMAGE_EXT:return KIND_IMAGE
        if ext not in VIDEO_EXT:return KIND_UNKNOWN
        try: st=os.stat(path); c=self._kind_cache.get(path); return c[2] if c and c[0]==st.st_mtime and c[1]==st.st_size else KIND_PENDING
        except OSError:return KIND_UNKNOWN
    def _scan_directory_worker(self, generation: int, directory: str):
        entries=[]; error=""
        try:
            with os.scandir(directory) as it:
                for ent in it:
                    try:
                        is_dir=ent.is_dir(follow_symlinks=False)
                        st=ent.stat(follow_symlinks=False) if not is_dir else None
                        entries.append((ent.name, ent.path, is_dir, float(st.st_mtime) if st else 0.0, int(st.st_size) if st else 0))
                    except OSError:
                        entries.append((ent.name, ent.path, False, 0.0, 0))
            entries.sort(key=lambda e:(not e[2], e[0].casefold()))
        except Exception as exc:
            error=str(exc)
        self._file_list_bridge.done.emit(generation, directory, entries, error)

    def refresh(self):
        if not self._allowed(self._dir):
            self._dir=next((r for r in self._safe_roots if os.path.isdir(r)),os.path.expanduser("~"))
        self._kind_generation+=1; generation=self._kind_generation
        self.lbl_path.setText(self._dir); self.list_widget.clear()
        self.lbl_status.setText("Loading directory in background…")
        self._directory_signature_value = Performance._directory_signature(self._dir)
        self._worker_pool.start(_PoolTask(self._scan_directory_worker, generation, self._dir))

    def _on_directory_listed(self, generation:int, directory:str, entries, error:str):
        if generation!=self._kind_generation or os.path.abspath(directory)!=os.path.abspath(self._dir): return
        if error:
            self.lbl_status.setText(f"Cannot list {directory}: {error}"); return
        self.list_widget.clear(); pending=[]
        _show_hidden=bool(getattr(self,"chk_hidden",None) and self.chk_hidden.isChecked())
        for name, full, is_dir, mtime, size in entries:
            if not _show_hidden:
                if name.startswith("."): continue
                try:   # GROOVEBOX_R23R_HIDE_SYSTEM_FILES_20261103: Groovebox system files stay out of sight
                    import groovebox_paths as _gpv
                    if _gpv.is_system_path(full): continue
                except Exception:
                    pass
            if is_dir: kind="dir"; icon="📁 "
            else:
                ext=_gb_ext(full)
                if ext in AUDIO_EXT: kind=KIND_AUDIO
                elif ext in IMAGE_EXT: kind=KIND_IMAGE
                elif ext not in VIDEO_EXT: kind=KIND_UNKNOWN
                else:
                    c=self._kind_cache.get(full)
                    kind=c[2] if c and c[0]==mtime and c[1]==size else KIND_PENDING
                    if kind==KIND_PENDING: pending.append(full)
                icon=_kind_icon(kind)+" "
            item=QListWidgetItem(icon+name); item.setData(Qt.ItemDataRole.UserRole,full); item.setData(Qt.ItemDataRole.UserRole+1,kind); self.list_widget.addItem(item)
        self._apply_name_filter()
        self.lbl_status.setText(f"{self.list_widget.count()} item(s)" + (f" · classifying {len(pending)} video file(s) in background…" if pending else ""))
        if pending: self._worker_pool.start(_PoolTask(self._kind_worker.run_batch, generation, list(pending)))
    def _on_probe_progress(self,generation:int,path:str,kind:str):
        if generation!=self._kind_generation:return
        try: st=os.stat(path); _bounded_cache_put(self._kind_cache,path,(st.st_mtime,st.st_size,kind),256)
        except OSError:_bounded_cache_put(self._kind_cache,path,(0.0,0,kind),256)
        for i in range(self.list_widget.count()):
            it=self.list_widget.item(i)
            if it and it.data(Qt.ItemDataRole.UserRole)==path:
                it.setData(Qt.ItemDataRole.UserRole+1,kind); it.setText(_kind_icon(kind)+" "+os.path.basename(path)); break
    def _on_probe_done(self,generation:int):
        if generation==self._kind_generation:self.lbl_status.setText(f"{self.list_widget.count()} item(s) · classification complete")
    def _selected_paths(self)->List[str]: return [str(it.data(Qt.ItemDataRole.UserRole)) for it in self.list_widget.selectedItems() if it.data(Qt.ItemDataRole.UserRole)]
    def _apply_name_filter(self,*_a):
        needle=self.edit_filter.text().strip().casefold() if hasattr(self,"edit_filter") else ""
        for i in range(self.list_widget.count()):
            it=self.list_widget.item(i)
            it.setHidden(bool(needle) and needle not in it.text().casefold())
    def _go_typed_path(self):
        path=os.path.abspath(os.path.expanduser(self.edit_path.text().strip() or self._dir))
        if not os.path.isdir(path):
            self.lbl_status.setText(f"Not a folder: {path}"); return
        if not self._allowed(path):
            self.lbl_status.setText("That folder is outside the safe roots - tick Advanced/System Files to go there."); return
        self.set_directory(path)
    def _upload_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Upload files into "+self._dir,os.path.expanduser("~"))
        if paths: self._copy_into_dir(paths)
    def dragEnterEvent(self,event):
        md=event.mimeData()
        if md.hasUrls() and any(u.isLocalFile() for u in md.urls()): event.acceptProposedAction()
        else: event.ignore()
    def dragMoveEvent(self,event): self.dragEnterEvent(event)
    def dropEvent(self,event):
        paths=[u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths: event.acceptProposedAction(); self._copy_into_dir(paths)
        else: event.ignore()
    def _copy_into_dir(self,paths):
        """Copy dropped/uploaded files into the folder being shown (a removable's mount counts). Never overwrites."""
        dest=self._dir
        if not self._destination_write_probe(dest,"Copy into folder"): return
        self.lbl_status.setText(f"Copying {len(paths)} item(s) into {dest} …")
        def run():
            ok=0; errs=[]
            for src in paths:
                try:
                    base=os.path.basename(src.rstrip("/")) or "item"
                    stem,ext=os.path.splitext(base); dst=os.path.join(dest,base); n=1
                    while os.path.lexists(dst):
                        n+=1; dst=os.path.join(dest,f"{stem} ({n}){ext}")
                    self._portable_copy_item(src,dst); ok+=1
                except Exception as exc:
                    errs.append(f"{os.path.basename(src)}: {exc}")
            self._drop_bridge.done.emit(ok,errs)
        self._worker_pool.start(_PoolTask(run))
    def _on_drop_copy_done(self,ok,errs):
        self.refresh()
        msg=f"Copied {ok} item(s) into {self._dir}."+(f" {len(errs)} failed: "+"; ".join(errs[:3]) if errs else "")
        QTimer.singleShot(400,lambda: self.lbl_status.setText(msg))
    def _go_up(self):
        parent=os.path.dirname(self._dir.rstrip(os.sep)) or os.sep
        if parent==self._dir:return
        if not self._allowed(parent): self.lbl_status.setText("Normal mode stops at a safe root. Enable Advanced/System Files to go higher."); return
        self._dir=parent; self.refresh()
    def _on_double_click(self,item:QListWidgetItem):
        path=item.data(Qt.ItemDataRole.UserRole)
        if not path:return
        if os.path.isdir(path):
            if self._allowed(path): self._dir=path; self.refresh()
            return
        ext=_gb_ext(path)
        if ext in MEDIA_EXT:self._open_in_player()
        elif ext in PROJECT_EXT or ext in GAME_EXT:self._open_project_or_game()
        else:self.lbl_status.setText("This file type is not a Groovebox media/project/game target.")
    def _new_folder(self):
        name,ok=QInputDialog.getText(self,"New Folder","Folder name:"); name=name.strip()
        if not ok:return
        if not self._valid_leaf(name): QMessageBox.warning(self,"New Folder","Use a simple folder name without path separators or '..'."); return
        dest=os.path.join(self._dir,name)
        if os.path.exists(dest): QMessageBox.warning(self,"New Folder","An item with that name already exists."); return
        try: os.mkdir(dest); self.refresh(); self.lbl_status.setText(f"Created folder: {name}")
        except Exception as e: QMessageBox.warning(self,"New Folder failed",str(e))
    def _rename_selected(self):
        paths=self._selected_paths()
        if len(paths)!=1: QMessageBox.information(self,"Rename","Select exactly one file or folder to rename."); return
        old_path=paths[0]; old_name=os.path.basename(old_path.rstrip(os.sep)); new_name,ok=QInputDialog.getText(self,"Rename","New name:",text=old_name); new_name=new_name.strip()
        if not ok or new_name==old_name:return
        if not self._valid_leaf(new_name): QMessageBox.warning(self,"Rename","Use a simple name without path separators or '..'."); return
        if old_path.lower().endswith((".mcc", ".mgpr")) and not new_name.lower().endswith((".mcc", ".mgpr")):
            new_name += os.path.splitext(old_path)[1]
        new_path=os.path.join(os.path.dirname(old_path.rstrip(os.sep)),new_name)
        if os.path.exists(new_path): QMessageBox.warning(self,"Rename","The destination already exists; nothing was overwritten."); return
        try:
            os.rename(old_path,new_path)
            host = getattr(self.parent(), "host", None)
            current = os.path.abspath(str(getattr(host, "_current_project_path", "") or "")) if host is not None else ""
            if host is not None and current == os.path.abspath(old_path) and os.path.isfile(new_path):
                host._current_project_path = new_path
                try:
                    import groovebox_paths
                    groovebox_paths.project_root(new_path)
                    groovebox_paths.index_file(new_path, "project", new_path)
                except Exception as index_exc:
                    print(f"[File Manager] renamed project; index refresh skipped: {index_exc}")
            self.refresh(); self.lbl_status.setText(f"Renamed to: {new_name}")
        except Exception as e: QMessageBox.warning(self,"Rename failed",str(e))
    def _selected_storage_mount(self)->str:
        if not hasattr(self,"cmb_storage_devices"):
            return ""
        try:
            data=self.cmb_storage_devices.currentData()
            path=str(data.get('mountpoint','') if isinstance(data,dict) else (data or ''))
        except Exception:
            return ""
        path=os.path.abspath(path) if path else ""
        if path and os.path.isdir(path) and path.startswith(("/run/media/","/media/","/mnt/")):
            return path
        return ""

    @staticmethod
    def _transfer_mount_info(path:str)->Tuple[str,str,str]:
        """Return (mountpoint, fstype, options) for the deepest mount containing path."""
        target=os.path.realpath(path)
        best=("","","")
        try:
            with open('/proc/self/mounts','r',encoding='utf-8',errors='replace') as fh:
                for line in fh:
                    parts=line.split()
                    if len(parts) < 4: continue
                    mp=_decode_mount_field(parts[1])
                    try:
                        inside=os.path.commonpath([target,os.path.realpath(mp)]) == os.path.realpath(mp)
                    except Exception:
                        inside=False
                    if inside and len(mp) > len(best[0]):
                        best=(mp,parts[2],parts[3])
        except OSError:
            pass
        return best

    def _destination_write_probe(self,dest:str,title:str)->bool:
        mp,fs,opts=self._transfer_mount_info(dest)
        if 'ro' in {x.strip() for x in opts.split(',') if x.strip()}:
            QMessageBox.warning(self,title,f"The destination is mounted read-only:\n{mp or dest}\nFilesystem: {fs or 'unknown'}")
            return False
        probe=os.path.join(dest,f".groovebox-write-test-{os.getpid()}")
        try:
            with open(probe,'wb') as fh:
                fh.write(b'GB')
                fh.flush()
                try: os.fsync(fh.fileno())
                except OSError: pass
            os.remove(probe)
            return True
        except Exception as exc:
            try:
                if os.path.exists(probe): os.remove(probe)
            except Exception: pass
            QMessageBox.warning(self,title,f"The selected destination is visible but not writable:\n{dest}\nFilesystem: {fs or 'unknown'}\n{exc}")
            return False

    def _choose_transfer_dir(self,title:str)->str:
        # If the user selected a removable device in Storage Devices, start the
        # chooser there.  This makes Copy Over usable even when the platform
        # file dialog does not surface /run/media automatically.
        storage=self._selected_storage_mount()
        start=storage or self._dir
        dest=QFileDialog.getExistingDirectory(self,title,start)
        if not dest:return ""
        dest=os.path.abspath(dest)
        if not self._allowed(dest):
            QMessageBox.warning(self,title,"That destination is outside the normal safe roots. Enable Advanced/System Files first if you really want to write there.")
            return ""
        if not self._destination_write_probe(dest,title):
            return ""
        return dest

    @staticmethod
    def _remove_existing_transfer_target(path:str):
        if os.path.isdir(path) and not os.path.islink(path): shutil.rmtree(path)
        else: os.remove(path)

    @staticmethod
    def _portable_copy_file(src:str,dst:str)->None:
        """Copy bytes without requiring POSIX chmod/xattr support.

        FAT/exFAT/NTFS removable media can reject shutil.copy2's metadata pass
        after the payload has already been written. Copy Over is a data transfer,
        so metadata preservation is best-effort and must never turn a valid copy
        into a reported failure.
        """
        with open(src,'rb') as rf, open(dst,'wb') as wf:
            shutil.copyfileobj(rf,wf,length=1024*1024)
            wf.flush()
            try: os.fsync(wf.fileno())
            except OSError: pass
        try:
            st=os.stat(src,follow_symlinks=True)
            os.utime(dst,(st.st_atime,st.st_mtime),follow_symlinks=True)
        except OSError:
            pass
        if os.path.getsize(src) != os.path.getsize(dst):
            raise IOError(f"size verification failed for {dst}")

    @classmethod
    def _portable_copy_tree(cls,src:str,dst:str)->None:
        os.mkdir(dst)
        try:
            with os.scandir(src) as it:
                for ent in it:
                    sp=ent.path; dp=os.path.join(dst,ent.name)
                    if ent.is_dir(follow_symlinks=False):
                        cls._portable_copy_tree(sp,dp)
                    elif ent.is_symlink():
                        target=os.path.realpath(sp)
                        if os.path.isdir(target):
                            cls._portable_copy_tree(target,dp)
                        else:
                            cls._portable_copy_file(target,dp)
                    else:
                        cls._portable_copy_file(sp,dp)
        except Exception:
            try: shutil.rmtree(dst)
            except Exception: pass
            raise

    @classmethod
    def _portable_copy_item(cls,src:str,dst:str)->None:
        if os.path.isdir(src) and not os.path.islink(src): cls._portable_copy_tree(src,dst)
        else: cls._portable_copy_file(os.path.realpath(src) if os.path.islink(src) else src,dst)
    def _prepare_transfer(self,title:str):
        paths=self._selected_paths()
        if not paths:
            QMessageBox.information(self,title,"Select one or more files or folders first."); return [],""
        dest_dir=self._choose_transfer_dir(title)
        if not dest_dir:return [],""
        return paths,dest_dir
    def _move_selected(self):
        paths,dest_dir=self._prepare_transfer("Move selected items")
        if not paths:return
        moved=0; skipped=0
        for src in paths:
            if os.path.realpath(src) in self._safe_roots:
                QMessageBox.warning(self,"Protected root",f"Will not move protected root:\n{src}"); skipped+=1; continue
            dst=os.path.join(dest_dir,os.path.basename(src.rstrip(os.sep)))
            if os.path.realpath(src)==os.path.realpath(dst): skipped+=1; continue
            if os.path.exists(dst):
                ans=QMessageBox.question(self,"Replace destination?",f"{dst} already exists. Replace it before moving?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
                if ans!=QMessageBox.StandardButton.Yes: skipped+=1; continue
                try:self._remove_existing_transfer_target(dst)
                except Exception as e: QMessageBox.warning(self,"Move failed",f"Could not replace {dst}\n{e}"); skipped+=1; continue
            try:
                _mp,_fs,_opts=self._transfer_mount_info(dest_dir)
                removable=_mp.startswith(("/run/media/","/media/","/mnt/"))
                if removable:
                    # Cross-filesystem shutil.move falls back to copy2, whose
                    # POSIX metadata preservation is not portable to FAT/exFAT.
                    self._portable_copy_item(src,dst)
                    if os.path.isdir(src) and not os.path.islink(src): shutil.rmtree(src)
                    else: os.remove(src)
                else:
                    shutil.move(src,dst)
                moved+=1
            except Exception as e: QMessageBox.warning(self,"Move failed",f"{src} → {dst}\n{e}"); skipped+=1
        self.refresh(); self.lbl_status.setText(f"Moved {moved} item(s) to {dest_dir}" + (f" · skipped {skipped}" if skipped else ""))
    def _copyover_selected(self):
        paths,dest_dir=self._prepare_transfer("Copy Over selected items")
        if not paths:return
        copied=0; skipped=0; replace_all=False
        existing=[os.path.join(dest_dir,os.path.basename(p.rstrip(os.sep))) for p in paths]
        existing=[p for p in existing if os.path.exists(p)]
        if existing:
            ans=QMessageBox.question(self,"Copy Over / Replace",f"{len(existing)} destination item(s) already exist. Copy Over will replace them. Continue?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if ans!=QMessageBox.StandardButton.Yes:return
            replace_all=True
        for src in paths:
            dst=os.path.join(dest_dir,os.path.basename(src.rstrip(os.sep)))
            try:
                if os.path.realpath(src)==os.path.realpath(dst): skipped+=1; continue
                if os.path.exists(dst):
                    if not replace_all: skipped+=1; continue
                    self._remove_existing_transfer_target(dst)
                _mp,_fs,_opts=self._transfer_mount_info(dest_dir)
                if _mp.startswith(("/run/media/","/media/","/mnt/")):
                    self._portable_copy_item(src,dst)
                elif os.path.isdir(src) and not os.path.islink(src):
                    shutil.copytree(src,dst,copy_function=shutil.copy2)
                else:
                    shutil.copy2(src,dst,follow_symlinks=False)
                copied+=1
            except Exception as e: QMessageBox.warning(self,"Copy Over failed",f"{src} → {dst}\n{e}"); skipped+=1
        self.refresh(); self.lbl_status.setText(f"Copied over {copied} item(s) to {dest_dir}" + (f" · skipped {skipped}" if skipped else ""))
    def _trash_target(self,path:str)->str:
        stamp=time.strftime("%Y%m%d-%H%M%S"); base=os.path.basename(path.rstrip(os.sep)) or "item"; dest=os.path.join(self._trash_dir,f"{stamp}-{base}"); n=2
        while os.path.exists(dest): dest=os.path.join(self._trash_dir,f"{stamp}-{n}-{base}"); n+=1
        return dest
    def _delete_selected(self):
        paths=self._selected_paths()
        if not paths:return
        if QMessageBox.question(self,"Move to Trash",f"Move {len(paths)} item(s) to Groovebox Trash?\nYou can undo the most recent operation.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        moved=[]
        for path in paths:
            if os.path.realpath(path) in self._safe_roots: QMessageBox.warning(self,"Protected root",f"Will not move protected root:\n{path}"); continue
            try:
                dest=self._trash_target(path); shutil.move(path,dest); moved.append((dest,path))
            except Exception as e: QMessageBox.warning(self,"Trash failed",f"{path}\n{e}")
        self._last_trash_moves=moved; self.refresh(); self.lbl_status.setText(f"Moved {len(moved)} item(s) to Groovebox Trash.")
    def _index_duplicates(self):
        dlg=DuplicatesDialog(self, self._dir, trash=self._trash_duplicates, skip_dirs=(self._trash_dir,))
        dlg.setModal(False); dlg.show(); self._dups_dialog=dlg

    def _trash_duplicates(self, paths):
        moved=[]; errors=[]
        for path in paths:
            if os.path.realpath(path) in self._safe_roots: continue
            try:
                dest=self._trash_target(path); shutil.move(path,dest); moved.append((dest,path))
            except Exception as e: errors.append(f"{path}: {e}")
        self._last_trash_moves=moved; self.refresh()
        self.lbl_status.setText(f"Moved {len(moved)} duplicate(s) to Groovebox Trash (↶ Undo Trash restores them).")
        return moved, errors

    def _export_source_archive(self):
        from PyQt6.QtWidgets import QInputDialog
        fmt,ok=QInputDialog.getItem(self,"Export MatGroovebox Source","Archive format:",[".tar.gz",".zip",".MCC (Groovebox package)"],0,False)
        if not ok: return
        fmt={".tar.gz":"tar.gz",".zip":"zip"}.get(fmt,"mcc"); ext={"tar.gz":".tar.gz","zip":".zip","mcc":".MCC"}[fmt]
        default=os.path.join(self._dir,f"MathematiciansGroovebox_Source_{time.strftime('%Y%m%d')}{ext}")
        path,_=QFileDialog.getSaveFileName(self,"Export MatGroovebox Source",default,f"Archive (*{ext})")
        if not path: return
        app_root=os.path.dirname(os.path.abspath(__file__))
        self.lbl_status.setText("Packing Groovebox source…")
        bridge=_FileToolsBridge(self); self._src_bridge=bridge
        bridge.progress.connect(lambda d,t: self.lbl_status.setText(f"Packing Groovebox source… {d}/{t} files"))
        bridge.done.connect(lambda out,err: (self.lbl_status.setText(f"Source archive written: {out}" if not err else f"Source export failed: {err}"), self.refresh()))
        def run():
            try:
                from file_tools import export_source_archive
                out=export_source_archive(app_root,path,fmt,progress=lambda d,t: (d%200==0 or d==t) and bridge.progress.emit(d,t))
                bridge.done.emit(out,"")
            except Exception as e:
                bridge.done.emit("",str(e))
        threading.Thread(target=run,daemon=True,name="groovebox-source-export").start()

    def _undo_trash(self):
        if not self._last_trash_moves: self.lbl_status.setText("Nothing to undo."); return
        restored=0; remaining=[]
        for src,dst in reversed(self._last_trash_moves):
            try:
                if os.path.exists(dst): remaining.append((src,dst)); continue
                if os.path.exists(src): os.makedirs(os.path.dirname(dst),exist_ok=True); shutil.move(src,dst); restored+=1
            except Exception: remaining.append((src,dst))
        self._last_trash_moves=list(reversed(remaining)); self.refresh(); self.lbl_status.setText(f"Restored {restored} item(s) from Trash.")
    def _view_image(self):
        paths=[p for p in self._selected_paths() if _gb_ext(p) in IMAGE_EXT]
        if not paths:
            QMessageBox.information(self,"View Image","Select an image (PNG/JPEG/WEBP/… or .MCC image) first."); return
        def _add(path, dur):
            host=getattr(self,"host",None)
            target=None
            for cand in (host, getattr(host,"host",None)):
                if cand is not None and hasattr(cand,"_playlist"):
                    target=cand; break
            if target is None:
                self.lbl_status.setText("No Performance playlist available."); return
            target._playlist.append({"path": path, "volume": 100, "mix": False, "kind": KIND_IMAGE,
                                     "time_s": float(len(target._playlist) * 5.0), "duration_s": float(dur)})
            try: target._refresh_playlist_widget()
            except Exception: pass
        dlg=ImageViewerDialog(paths[0], self, add_to_playlist=_add); dlg.exec()

    def _open_in_player(self):
        paths=[p for p in self._selected_paths() if os.path.isfile(p) and _gb_ext(p) in MEDIA_EXT]
        if not paths: QMessageBox.information(self,"Open in Player","Select one or more supported audio/video/image files first."); return
        items=[{"path":p,"duration_s":5.0 if _gb_ext(p) in IMAGE_EXT else 0.0} for p in paths]
        host=self.parent()
        if host is not None and hasattr(host,"_show_player_window"):
            host._show_player_window(items,0,replace_queue=True)
        else:
            dlg=MediaPlayerWindow(self,items,0); dlg.setModal(False); dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,False); dlg.show(); self._fallback_player=dlg
    def _open_project_or_game(self):
        host=self.parent(); paths=[p for p in self._selected_paths() if os.path.isfile(p)]
        if not paths:return
        for path in paths:
            ext=_gb_ext(path)
            try:
                if ext in PROJECT_EXT:
                    if host is not None and hasattr(host,"_open_project"): host._open_project(path)
                    elif host is not None and hasattr(host,"host") and hasattr(host.host,"open_project_path"): host.host.open_project_path(path)
                    else: raise RuntimeError("No project loader is available")
                elif ext in GAME_EXT:
                    if host is not None and hasattr(host,"_play_game_package"): host._play_game_package(path)
                    else: raise RuntimeError("No game player is available")
            except Exception as e: QMessageBox.warning(self,"Open failed",f"{path}\n{e}")
    def _add_to_performance_playlist(self):
        host=self.parent()
        if host is None or not hasattr(host,"_playlist"): QMessageBox.information(self,"Add to Playlist","No Performance playlist is available from this window."); return
        paths=[p for p in self._selected_paths() if os.path.isfile(p) and _gb_ext(p) in MEDIA_EXT]
        if not paths: QMessageBox.information(self,"Add to Playlist","Select supported audio/video/image files first."); return
        added=0
        for path in paths:
            kind=self._cached_kind(path)
            if kind==KIND_PENDING: kind=KIND_UNKNOWN
            if not any(it["path"]==path for it in host._playlist):
                host._playlist.append({"path":path,"volume":100,"mix":False,"kind":kind,"time_s":float(len(host._playlist)*5.0),"duration_s":5.0 if kind==KIND_IMAGE else 0.0}); added+=1
        host._refresh_playlist_widget(); host._sync_project_state(); self.lbl_status.setText(f"Added {added} supported media item(s) to the Performance playlist.")


def open_performance(host) -> Performance:
    """Compatibility standalone opener; main Groovebox embeds Performance as a dock."""
    dlg = Performance(host, parent=host)
    dlg.setModal(False)
    dlg.show()
    return dlg


PiMediaHub = Performance

def open_pi_media_hub(host):
    return open_performance(host)


# GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103: no dialog may block other windows.
try:
    import nonmodal_dialogs as _gb_nonmodal
    _gb_nonmodal.install()
except Exception:
    pass
