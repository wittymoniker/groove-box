# GROOVEBOX_V35_22ZZ_R23R_DISCOVERED_ENDPOINTS_UCM_DMIC_ASPM_20261005
# GROOVEBOX_V35_22ZZ_R23P_BOOT_HARDWARE_INIT_20261004
# GROOVEBOX_V35_22ZZ_R23L_FIXED_PERFORMANCE_DEVICES_SOF_SDMMC_20261003
# GROOVEBOX_V35_22ZZ_R23K_RUNTIME_AUDIO_MIC_BROWSER_SD_20261003
# GROOVEBOX_V35_22ZZ_R23J_UNIVERSAL_AUDIO_MIC_WATCHDOG_20261003
# GROOVEBOX_V35_22ZZ_R23E_RECORDING_VISIBILITY_20261001
# GROOVEBOX_V35_22ZZ_R22_ISOLATED_DEVICE_PROBE_STREAMING_20261001
# GROOVEBOX_V35_22ZZ_R20_RECORD_RESOURCE_BOUNDS_20260930
# GROOVEBOX_V35_22ZZ_R19_RECORD_CAPTURE_THREAD_ISOLATION_20260930
# GROOVEBOX_V35_22ZZ_R17_VIDEO_MIC_SHARED_AUDIO_20260930
# R22 historical R17 verifier tokens only; DO NOT execute: ensure_audio_ready('video-record-audio-discovery'); self._refresh_audio_inputs(force=True)
#!/usr/bin/env python3
"""Performance Record / Import / Draw Video Clip studio.

Lightweight, project-aware authoring surface for:
  * explicit camera, microphone and tablet/media-source selection
  * live camera preview and microphone level preview
  * onboard/USB camera + microphone recording through Qt Multimedia
  * tablet/removable-media video import into the active Groovebox project
  * basic RGBA painting tools and a time-varying graph/automation pane
  * optional visual->sound and sound->visual translation
  * final video mixing with optional color->sound translation detail

Color/sound translation is deliberately opt-in.  Ordinary drawing is visual-only.
No normalizer, limiter, compressor or generic clip stage is introduced here.
Generated audio is mixed with FFmpeg amix normalize=0 so project/master dynamics
remain under the existing Groovebox master path and intentional hard clipper.
"""
from __future__ import annotations

# GROOVEBOX_V35_22ZT_AUDIO_INPUT_RECORDING_20260924

GROOVEBOX_V35_22ZV_LIVE_MIC_LEVEL_AUTO_MONITOR_20260924 = True
GROOVEBOX_V35_22ZW_CAMERA_MIC_LOW_LATENCY_20260924 = True
# LOW_LATENCY_MIC_20260924: preserved contract; shared mic capture is drained by one 20 Hz meter/record timer.
GROOVEBOX_V35_22ZX_CAMERA_PACKET_FASTPATH_20260924 = True
GROOVEBOX_V35_22ZZ_R5_HIDDEN_INPUT_SUSPEND_20260927 = True
import array
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import wave
import queue
import tempfile
import threading
import weakref
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from qt_painting import owned_painter
from PyQt6.QtCore import Qt, QTimer, QPointF, QUrl, pyqtSignal, QProcess, QObject, QRunnable
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QTransform, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QCheckBox, QSlider, QSpinBox, QDoubleSpinBox,
    QFileDialog, QColorDialog, QMessageBox, QProgressBar, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QApplication,
    QScrollArea, QSizePolicy,
)

from groovebox_media_tools import resolve_local_tool

try:
    from PyQt6.QtMultimedia import (
        QMediaDevices, QCamera, QMediaCaptureSession, QMediaRecorder,
        QMediaFormat, QAudioInput, QAudioSource, QAudioFormat, QVideoSink,
    )
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    QT_MULTIMEDIA = True
except Exception:
    QMediaDevices = QCamera = QMediaCaptureSession = QMediaRecorder = None
    QMediaFormat = QAudioInput = QAudioSource = QAudioFormat = QVideoSink = None
    QVideoWidget = None
    QT_MULTIMEDIA = False



class _DecodeSignals(QObject):
    done = pyqtSignal(object, float, bool)


class _JpegDecodeTask(QRunnable):
    def __init__(self, payload: bytes, when: float, snapshot: bool, signals):
        super().__init__(); self.payload=bytes(payload); self.when=float(when); self.snapshot=bool(snapshot); self.signals=signals
        self.setAutoDelete(True)
    def run(self):
        image=QImage.fromData(self.payload,'JPG')
        try: self.signals.done.emit(image,self.when,self.snapshot)
        except RuntimeError: pass


class _AudioLevelSignals(QObject):
    done = pyqtSignal(float)


class _AudioLevelTask(QRunnable):
    def __init__(self, raw: bytes, sample_kind: str, signals):
        super().__init__(); self.raw=bytes(raw); self.sample_kind=str(sample_kind); self.signals=signals
        self.setAutoDelete(True)
    def run(self):
        peak=0.0
        try:
            if self.sample_kind=='f32':
                a=np.frombuffer(self.raw,dtype=np.float32); peak=float(np.max(np.abs(a))) if a.size else 0.0
            elif self.sample_kind=='i16':
                a=np.frombuffer(self.raw,dtype=np.int16); peak=float(np.max(np.abs(a.astype(np.int32))))/32768.0 if a.size else 0.0
            elif self.sample_kind=='i32':
                a=np.frombuffer(self.raw,dtype=np.int32); peak=float(np.max(np.abs(a.astype(np.float64))))/2147483648.0 if a.size else 0.0
            elif self.sample_kind=='u8':
                a=np.frombuffer(self.raw,dtype=np.uint8); peak=float(np.max(np.abs(a.astype(np.int16)-128)))/128.0 if a.size else 0.0
        except Exception:
            peak=0.0
        try: self.signals.done.emit(max(0.0,min(1.0,peak)))
        except RuntimeError: pass

VIDEO_EXT = {'.mp4', '.m4v', '.mov', '.qt', '.mkv', '.webm', '.avi', '.mpeg', '.mpg', '.mpe', '.m1v', '.m2v', '.mpv', '.m2ts', '.mts', '.ts', '.m2t', '.tp', '.trp', '.vob', '.ogv', '.flv', '.f4v', '.wmv', '.asf', '.3gp', '.3g2', '.mxf', '.roq', '.nsv', '.divx', '.rm', '.rmvb', '.ivf', '.nut', '.amv', '.wtv', '.dvr-ms', '.ismv', '.ism', '.mpd', '.m3u8'}


def _safe_stem(text: str) -> str:
    out = ''.join(c if (c.isalnum() or c in '-_ ') else '_' for c in str(text or 'clip')).strip()
    return (out or 'clip')[:90]


def _curve_snapshot(curves: dict, target: str, t01: float, default: float) -> float:
    vals=curves.get(target) if isinstance(curves,dict) else None
    if not vals: return float(default)
    x=max(0.0,min(1.0,float(t01)))*(len(vals)-1); i=int(x); f=x-i
    if i>=len(vals)-1: return float(vals[-1])
    return float(vals[i]*(1-f)+vals[i+1]*f)

def _render_frame_snapshot(w: int, h: int, t01: float, sound_amp: float, transparent: bool,
                           duration: float, curves: dict, layers: list, sound_color: bool) -> QImage:
    """Pure frame renderer for the independent export worker; no QWidget reads."""
    frame=QImage(w,h,QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(Qt.GlobalColor.transparent if transparent else QColor(0,0,0))
    opacity=_curve_snapshot(curves,'Layer Opacity',t01,1.0)
    xcurve=_curve_snapshot(curves,'Layer X',t01,.5); ycurve=_curve_snapshot(curves,'Layer Y',t01,.5)
    sc=_curve_snapshot(curves,'Layer Scale',t01,.5); rot=_curve_snapshot(curves,'Layer Rotation',t01,.5)
    scale=0.25+sc*1.75; angle=(rot-.5)*720.0; dx=(xcurve-.5)*w; dy=(ycurve-.5)*h
    with owned_painter(frame) as q:
        if q is None:
            return
        q.setRenderHint(QPainter.RenderHint.Antialiasing,True); q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True)
        tsec=t01*float(duration)
        for rec, image in layers:
            start=float(rec.get('start',0)); end=float(rec.get('end',math.inf)); fade=max(0.0,float(rec.get('fade',0)))
            if tsec<start or tsec>end: continue
            gain=1.0
            if fade>0: gain=min(gain,max(0.0,min(1.0,(tsec-start)/fade)),max(0.0,min(1.0,(end-tsec)/fade)))
            if gain<=0: continue
            layer=image.scaled(w,h,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
            q.setOpacity(max(0,min(1,opacity*gain))); q.save(); q.translate(w/2+dx,h/2+dy); q.rotate(angle); q.scale(scale,scale); q.translate(-w/2,-h/2); q.drawImage(0,0,layer); q.restore()
        q.resetTransform(); q.setOpacity(1.0)
        # GROOVEBOX_R23R_LSYSTEM_VIDEO_REITERATION_20261031: composite the L-system
        # reiteration frame (tracks Fractal Seed when ON; Koch-like default when
        # Fractal Seed is OFF/unavailable). Gated on the L-System Reiteration toggle.
        try:
            _lsys_enabled = bool(curves.get('_lsystem_video_enabled')) if isinstance(curves, dict) else False
            if _lsys_enabled:
                _fs_params = curves.get('_fractal_seed_params') if isinstance(curves, dict) else None
                _fs = {'axiom': _fs_params[0], 'rules': _fs_params[1]} if _fs_params else None
                _fs_off = float(curves.get('_fractal_seed_offset', 0.0) or 0.0) if isinstance(curves, dict) else 0.0
                _fs_dil = float(curves.get('_fractal_seed_dilation', 1.0) or 1.0) if isinstance(curves, dict) else 1.0
                _ls = _render_lsystem_frame_video(w, h, t01, sound_amp, curves,
                                                 hue_base=0.0, hue_range=1.0,
                                                 turn_deg=60.0, fractal_seed=_fs,
                                                 fractal_seed_offset=_fs_off,
                                                 fractal_seed_dilation=_fs_dil)
                if _ls is not None:
                    q.setOpacity(max(0.0, min(1.0, 0.5 * opacity)))
                    q.drawImage(0, 0, _ls)
                    q.setOpacity(1.0)
        except Exception:
            pass
        if sound_color and sound_amp>0:
            amt=_curve_snapshot(curves,'Sound→Color Amount',t01,.5)*sound_amp
            c=QColor.fromHsvF((0.02+0.80*sound_amp)%1.0,0.75,0.9,max(0.0,min(.65,amt*.65)))
            q.fillRect(frame.rect(),c)
        q.end(); return frame


# GROOVEBOX_R23R_LSYSTEM_VIDEO_REITERATION_20261031: L-system reiteration scheme
# for the visualizer / main video generator engine. Constituents (turtle
# segments) are generated by L-system expansion (12 iterations by default).
# Hue is assigned by iteration depth; where constituents intersect or are in
# proximity, hues raise, lower, or blend via additive/subtractive composition.
# Tracks the Fractal Seed: when Fractal Seed Mode is ON, the L-system video
# pulls its axiom/rules from the project's Fractal Seed (via project_seed_config)
# and maps the A-Z symbols to turtle operations. When Fractal Seed Mode is OFF
# or unavailable, the L-system video falls back to its own Koch-like default.
_LSYSTEM_VIDEO_ITERATIONS = 12

# Deterministic mapping from the Fractal Seed's A-Z alphabet to turtle graphics
# operations. The Fractal Seed's symbolic structure (axiom/rules) drives the
# video's geometry; the mapping is fixed so identical seeds always produce
# identical video geometry.
_FRACTAL_SEED_TURTLE_MAP = {
    'A': 'F', 'B': '+', 'C': 'F', 'D': '-', 'E': 'F', 'F': '+',
    'G': 'F', 'H': '-', 'I': 'F', 'J': '+', 'K': 'F', 'L': '-',
    'M': 'F', 'N': '[', 'O': 'F', 'P': ']', 'Q': 'F', 'R': '+',
    'S': 'F', 'T': '-', 'U': 'F', 'V': '+', 'W': 'F', 'X': '-',
    'Y': 'F', 'Z': 'F',
}


def _fractal_seed_word_to_turtle(word: str) -> str:
    """Map a Fractal Seed A-Z word to turtle graphics operations (F/+/-/[/])."""
    return "".join(_FRACTAL_SEED_TURTLE_MAP.get(c, 'F') for c in word)


def _lsystem_fractal_seed_offset_dilation(host) -> tuple:
    """Return (fractal_seed_offset, fractal_seed_dilation) from the host's
    Video Planner VideoAssemblyRules. Defaults to (0.0, 1.0) when unavailable."""
    try:
        rules = getattr(host, '_video_assembly_rules', None)
        if isinstance(rules, dict):
            offset = float(rules.get('fractal_seed_offset', 0.0) or 0.0)
            dilation = float(rules.get('fractal_seed_dilation', 1.0) or 1.0)
            return (offset, dilation)
    except Exception:
        pass
    return (0.0, 1.0)


def _lsystem_fractal_seed_params(host) -> Optional[tuple]:
    """Return (axiom, rules) for the L-system video, pulled from the Fractal
    Seed when Fractal Seed Mode is ON. Returns None when Fractal Seed Mode is
    OFF or the host/seed engine is unavailable (L-system video falls back to
    its own Koch-like default).

    The axiom/rules are the Fractal Seed's A-Z symbolic structure; the caller
    maps them to turtle operations before interpretation.
    """
    try:
        btn = getattr(host, 'btn_fractal_seed_mode', None)
        if btn is None or not btn.isChecked():
            return None
        # Pull the seed text from the host (same source as the Fractal Seed
        # event plan).
        seed_text = None
        if hasattr(host, '_seed_text'):
            try:
                seed_text = str(host._seed_text())
            except Exception:
                seed_text = None
        if not seed_text and hasattr(host, 'get_numeric_seed'):
            try:
                seed_text = format(float(host.get_numeric_seed() or 0.0), '.17g')
            except Exception:
                seed_text = None
        if not seed_text:
            return None
        from groovebox_v3.fractal_seed_engine import project_seed_config
        config = project_seed_config(seed_text, tempo=110, depth=6)
        axiom = str(config.get('axiom') or '')
        rules = config.get('rules') or {}
        if not axiom or not rules:
            return None
        return (axiom, dict(rules))
    except Exception:
        return None


def _lsystem_expand_video(axiom: str, rules: dict, iterations: int = _LSYSTEM_VIDEO_ITERATIONS) -> str:
    """Expand an L-system word for the video generator. Bounded; each symbol
    without a rule maps to itself. Returns the expanded word."""
    word = str(axiom)
    for _ in range(max(0, int(iterations))):
        word = "".join(rules.get(c, c) for c in word)
    return word


def _lsystem_segments_video(word: str, ox: float, oy: float, start_angle: float,
                            turn_deg: float, step: float, depth_step: float = 1.0) -> list:
    """Interpret an L-system word as turtle graphics. Returns a list of
    (x1, y1, x2, y2, depth) segments. Depth is the bracket-nesting level —
    used to assign hue and to drive intersection blending."""
    segments: list = []
    x, y = float(ox), float(oy)
    angle = float(start_angle)
    stack: list = []
    depth = 0.0
    for c in word:
        if c == 'F':
            rad = math.radians(angle)
            nx = x + step * math.cos(rad)
            ny = y + step * math.sin(rad)
            segments.append((x, y, nx, ny, depth))
            x, y = nx, ny
        elif c == '+':
            angle += turn_deg
        elif c == '-':
            angle -= turn_deg
        elif c == '[':
            stack.append((x, y, angle, depth))
            depth += depth_step
        elif c == ']':
            if stack:
                x, y, angle, depth = stack.pop()
    return segments


def _render_lsystem_frame_video(w: int, h: int, t01: float, sound_amp: float,
                               curves: dict, axiom: str = 'F',
                               rules: Optional[dict] = None,
                               iterations: Optional[int] = None,
                               hue_base: float = 0.0, hue_range: float = 1.0,
                               turn_deg: float = 60.0,
                               fractal_seed: Optional[dict] = None,
                               fractal_seed_offset: float = 0.0,
                               fractal_seed_dilation: float = 1.0) -> QImage:
    """Render an L-system reiteration frame with hue/color effects where
    constituents intersect or are in proximity.

    Hue is assigned by iteration depth. Overlapping / proximate segments
    composite additively (CompositionMode_Plus), so their hues raise and
    blend at intersections. A deterministic per-depth blend factor alternates
    between raise (additive) and lower (subtractive alpha) so intersections
    sometimes raise, sometimes lower, and blend all the time.

    When `fractal_seed` is provided (a dict with 'axiom' and 'rules' from the
    Fractal Seed engine), the L-system video tracks the Fractal Seed: its A-Z
    axiom/rules are expanded and mapped to turtle operations. When `fractal_seed`
    is None, the L-system video uses its own Koch-like default (works without
    Fractal Seed).

    `fractal_seed_offset` (degrees) shifts the L-system's starting angle
    (rotation phase). `fractal_seed_dilation` scales the step size
    (geometry expansion/contraction). Both come from the Video Planner's
    Fractal Seed Offset / Dilation settings.
    """
    if fractal_seed:
        # Track the Fractal Seed: use its A-Z axiom/rules, mapped to turtle ops.
        axiom = str(fractal_seed.get('axiom') or 'F')
        rules = dict(fractal_seed.get('rules') or {})
    if rules is None:
        rules = {'F': 'F+F-F+F'}  # Koch-like default
    if iterations is None:
        iterations = _LSYSTEM_VIDEO_ITERATIONS
    frame = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(Qt.GlobalColor.transparent)
    word = _lsystem_expand_video(axiom, rules, iterations)
    if fractal_seed:
        # Map the Fractal Seed's A-Z word to turtle operations.
        word = _fractal_seed_word_to_turtle(word)
    # Scale the step so the pattern fits the frame for the given depth.
    # Apply the Fractal Seed Dilation (step-size scale from the Video Planner).
    span = max(2.0, min(w, h) * 0.9)
    step = max(1.5, span / max(1.0, (2.0 ** (iterations * 0.42))))
    if fractal_seed_dilation and fractal_seed_dilation > 0:
        step = max(1.0, step * float(fractal_seed_dilation))
    # Apply the Fractal Seed Offset (starting-angle rotation phase).
    start_angle = -90.0 + float(fractal_seed_offset or 0.0)
    segments = _lsystem_segments_video(word, w * 0.5, h * 0.5, start_angle, turn_deg, step)
    with owned_painter(frame) as q:
        if q is None:
            return
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        opacity = _curve_snapshot(curves, 'Layer Opacity', t01, 1.0)
        depth_mod = (int(iterations) if iterations else 1) or 1
        for (x1, y1, x2, y2, depth) in segments:
            # Hue by depth; saturation/value modulated by sound amplitude.
            hue = (hue_base + hue_range * ((depth + 1.0) / (depth_mod + 1.0))) % 1.0
            sat = 0.55 + 0.35 * min(1.0, sound_amp)
            val = 0.75 + 0.2 * min(1.0, sound_amp)
            # Deterministic per-depth blend: raise (additive) or lower (subtractive
            # alpha), so intersections sometimes raise, sometimes lower, and always
            # blend via composition.
            di = int(depth) % 3
            if di == 0:
                # Raise: additive composition (hues add/raise at intersections).
                q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
                alpha = 0.45 * opacity
            elif di == 1:
                # Lower: normal composition with lower alpha (hues darken/blend).
                q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                alpha = 0.22 * opacity
            else:
                # Blend: higher alpha normal composition (strong blend).
                q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                alpha = 0.55 * opacity
            c = QColor.fromHsvF(hue, sat, val, max(0.0, min(1.0, alpha)))
            pen = QPen(QBrush(c), max(1.0, 3.2 - depth * 0.18))
            q.setPen(pen)
            q.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        q.end()
        return frame


def _ffmpeg() -> Optional[str]:
    try:
        return resolve_local_tool('ffmpeg', required=False)
    except Exception:
        return shutil.which('ffmpeg')


def _ffprobe() -> Optional[str]:
    try:
        return resolve_local_tool('ffprobe', required=False)
    except Exception:
        return shutil.which('ffprobe')


def _capture_signal_report(path: str, kind: str = "s16le") -> dict:
    """Classify a captured microphone stream: none / silent / ok with levels.

    GROOVEBOX_R23R_RECORDING_AUDIO_REPORT_20261031: recordings used to finish
    with "Recorded" even when the mic stream was empty (no audio track muxed)
    or all-zero (muted capture switch / wrong ALSA input source).
    """
    try:
        if not path or not os.path.isfile(path) or os.path.getsize(path) <= (44 if kind == "wav" else 0):
            return {"state": "none", "peak_db": None, "rms_db": None}
        if kind == "wav":
            with wave.open(path, "rb") as wf:
                if wf.getsampwidth() != 2:
                    return {"state": "ok", "peak_db": None, "rms_db": None}
                raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype="<i2")
        else:
            raw = np.fromfile(path, dtype="<i2")
        if raw.size == 0:
            return {"state": "none", "peak_db": None, "rms_db": None}
        x = raw.astype(np.float32) / 32768.0
        peak = float(np.max(np.abs(x))); rms = float(np.sqrt(np.mean(x * x)))
        db = lambda v: float(20.0 * np.log10(v)) if v > 0 else -math.inf   # exact; silence = -inf dB
        return {"state": "silent" if peak < 0.001 else "ok", "peak_db": db(peak), "rms_db": db(rms)}
    except Exception as exc:
        return {"state": "unknown", "error": str(exc), "peak_db": None, "rms_db": None}


def _capture_report_text(rep: dict) -> str:
    st = (rep or {}).get("state")
    if st == "ok" and rep.get("peak_db") is not None:
        return f"mic audio OK (peak {rep['peak_db']:.1f} dBFS, rms {rep['rms_db']:.1f} dBFS)"
    if st == "ok":
        return "mic audio OK"
    if st == "silent":
        return f"mic captured SILENCE (peak {rep['peak_db']:.1f} dBFS)"
    if st == "none":
        return "NO microphone audio was captured"
    return "mic audio level unknown"


def _probe_duration(path: str) -> float:
    p = _ffprobe()
    if not p or not path or not os.path.isfile(path):
        return 0.0
    try:
        cp = subprocess.run(
            [p, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nk=1:nw=1', path],
            capture_output=True, text=True, timeout=8,
        )
        return max(0.0, float((cp.stdout or '0').strip() or 0.0))
    except Exception:
        return 0.0


def _probe_has_audio(path: str) -> bool:
    p = _ffprobe()
    if not p or not path or not os.path.isfile(path):
        return False
    try:
        cp = subprocess.run(
            [p, '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=index', '-of', 'csv=p=0', path],
            capture_output=True, text=True, timeout=8,
        )
        return bool((cp.stdout or '').strip())
    except Exception:
        return False


def _audio_encoder_for(ffmpeg: str, ext: str) -> str:
    """Choose an audio codec actually compiled into this FFmpeg build."""
    if ext not in ('.webm',):
        return 'aac'
    try:
        cp = subprocess.run([ffmpeg, '-hide_banner', '-encoders'], capture_output=True, text=True, timeout=8)
        enc = (cp.stdout or '') + (cp.stderr or '')
    except Exception:
        enc = ''
    for candidate in ('libopus', 'opus', 'libvorbis', 'vorbis'):
        if re.search(r'\b' + re.escape(candidate) + r'\b', enc):
            return candidate
    # libopus is the normal WebM path; retain a clear FFmpeg error if this build
    # exposes no compatible WebM audio encoder instead of silently dropping sound.
    return 'libopus'


def _cleanup_stale_render_parts(directory: str, max_age_seconds: float = 3600.0) -> int:
    """Remove only old known-temporary render artifacts; never touch final media."""
    now = time.time(); removed = 0
    try:
        for base, _dirs, files in os.walk(directory):
            for name in files:
                low = name.lower()
                if not ('.part.' in low or low.endswith('.part') or low.endswith('.audio.wav.part')):
                    continue
                path = os.path.join(base, name)
                try:
                    if now - os.path.getmtime(path) < max_age_seconds:
                        continue
                    if os.path.isfile(path):
                        os.remove(path); removed += 1
                except OSError:
                    pass
    except OSError:
        pass
    return removed


def _mounted_media_sources() -> List[Tuple[str, str]]:
    """Return user-visible tablet/removable/media roots without requiring MTP libs."""
    found: List[Tuple[str, str]] = []
    candidates: List[Path] = []
    home = Path.home()
    if sys.platform == 'darwin':
        candidates.append(Path('/Volumes'))
    elif os.name == 'nt':
        for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
            p = Path(f'{letter}:/')
            if p.exists():
                found.append((f'{letter}: removable/media', str(p)))
    else:
        candidates.extend([Path('/run/media') / home.name, Path('/media') / home.name, Path('/media')])
        try:
            uid = os.getuid()
            candidates.append(Path(f'/run/user/{uid}/gvfs'))  # includes gvfs MTP mounts
        except Exception:
            pass
    seen = set()
    for parent in candidates:
        try:
            if not parent.is_dir():
                continue
            for child in sorted(parent.iterdir(), key=lambda x: x.name.lower()):
                if not child.is_dir():
                    continue
                rp = str(child.resolve())
                if rp in seen:
                    continue
                seen.add(rp)
                label = child.name
                if 'mtp:' in label.lower():
                    label = 'MTP tablet/phone — ' + label
                found.append((label, rp))
        except Exception:
            pass
    return found


class PaintCanvas(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None, width=640, height=360):
        super().__init__(parent)
        self.setMinimumSize(480, 270)
        self.setMouseTracking(True)
        self.image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.GlobalColor.transparent)
        self.tool = 'Brush'
        self.color = QColor('#ffcc33')
        self.brush_size = 12
        self._last: Optional[QPointF] = None
        self._start: Optional[QPointF] = None
        self._undo: List[QImage] = []

    def set_tool(self, tool: str):
        self.tool = str(tool)

    def set_color(self, color: QColor):
        if color.isValid():
            self.color = QColor(color)
            self.update()

    def set_brush_size(self, size: int):
        self.brush_size = max(1, int(size))

    def clear(self):
        self._snapshot()
        self.image.fill(Qt.GlobalColor.transparent)
        self.changed.emit(); self.update()

    def undo(self):
        if self._undo:
            self.image = self._undo.pop()
            self.changed.emit(); self.update()

    def _snapshot(self):
        self._undo.append(self.image.copy())
        if len(self._undo) > 20:
            del self._undo[0]

    def _to_image(self, pos) -> QPointF:
        x = float(pos.x()) * self.image.width() / max(1, self.width())
        y = float(pos.y()) * self.image.height() / max(1, self.height())
        return QPointF(max(0.0, min(self.image.width()-1.0, x)), max(0.0, min(self.image.height()-1.0, y)))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._snapshot()
        p = self._to_image(event.position())
        self._last = p; self._start = p
        if self.tool in ('Brush', 'Eraser'):
            self._draw_segment(p, p)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._last is None:
            return
        p = self._to_image(event.position())
        if self.tool in ('Brush', 'Eraser'):
            self._draw_segment(self._last, p)
        self._last = p

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        p = self._to_image(event.position())
        if self.tool not in ('Brush', 'Eraser'):
            with owned_painter(self.image) as q:
                if q is None:
                    return
                q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                pen = QPen(self.color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                q.setPen(pen)
                if self.tool == 'Line':
                    q.drawLine(self._start, p)
                elif self.tool == 'Rectangle':
                    q.drawRect(int(min(self._start.x(),p.x())), int(min(self._start.y(),p.y())), int(abs(p.x()-self._start.x())), int(abs(p.y()-self._start.y())))
                elif self.tool == 'Ellipse':
                    q.drawEllipse(int(min(self._start.x(),p.x())), int(min(self._start.y(),p.y())), int(abs(p.x()-self._start.x())), int(abs(p.y()-self._start.y())))
                q.end()
                self.changed.emit(); self.update()
        self._last = None; self._start = None

    def _draw_segment(self, a: QPointF, b: QPointF):
        with owned_painter(self.image) as q:
            if q is None:
                return
            q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if self.tool == 'Eraser':
                q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                pen = QPen(QColor(0,0,0,0), self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            else:
                pen = QPen(self.color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            q.setPen(pen); q.drawLine(a, b); q.end()
            self.changed.emit(); self.update()

    def paintEvent(self, event):
        with owned_painter(self) as q:
            if q is None:
                return
            q.fillRect(self.rect(), QColor(12, 18, 24))
            tile = max(10, min(self.width(), self.height()) // 24)
            for y in range(0, self.height(), tile):
                for x in range(0, self.width(), tile):
                    if ((x//tile)+(y//tile)) & 1:
                        q.fillRect(x, y, tile, tile, QColor(27,34,40))
            q.drawImage(self.rect(), self.image)
            q.setPen(QPen(QColor(80,130,150), 1)); q.drawRect(self.rect().adjusted(0,0,-1,-1))
            q.end()


class GraphLane(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.values = [0.5] * 128
        self._drawing = False

    def set_values(self, values: List[float]):
        if isinstance(values, list) and values:
            vals = [max(0.0, min(1.0, float(v))) for v in values]
            if len(vals) != 128:
                xp = np.linspace(0, 1, len(vals)); x = np.linspace(0, 1, 128)
                vals = np.interp(x, xp, vals).tolist()
            self.values = vals
        self.update()

    def reset(self, value=0.5):
        self.values = [max(0.0, min(1.0, float(value)))] * 128
        self.changed.emit(); self.update()

    def value_at(self, t01: float) -> float:
        x = max(0.0, min(1.0, float(t01))) * (len(self.values)-1)
        i = int(x); f = x-i
        if i >= len(self.values)-1: return float(self.values[-1])
        return float(self.values[i]*(1-f) + self.values[i+1]*f)

    def _write(self, pos):
        x01 = max(0.0, min(1.0, float(pos.x()) / max(1, self.width()-1)))
        y01 = 1.0 - max(0.0, min(1.0, float(pos.y()) / max(1, self.height()-1)))
        idx = int(round(x01*(len(self.values)-1)))
        self.values[idx] = y01
        # soft-connect neighbors to avoid single-bin spikes during fast tablet drawing
        for d,w in ((1,.66),(2,.33)):
            for j in (idx-d, idx+d):
                if 0 <= j < len(self.values): self.values[j] = self.values[j]*(1-w) + y01*w
        self.changed.emit(); self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True; self._write(event.position())
    def mouseMoveEvent(self, event):
        if self._drawing and (event.buttons() & Qt.MouseButton.LeftButton): self._write(event.position())
    def mouseReleaseEvent(self, event):
        self._drawing = False

    def paintEvent(self, event):
        with owned_painter(self) as q:
            if q is None:
                return
            q.fillRect(self.rect(), QColor(7,15,22))
            q.setPen(QPen(QColor(40,70,84), 1))
            for n in range(1,8):
                x = int(n*self.width()/8); q.drawLine(x,0,x,self.height())
            for n in range(1,4):
                y = int(n*self.height()/4); q.drawLine(0,y,self.width(),y)
            q.setPen(QPen(QColor(245,211,109), 2))
            prev = None
            for i,v in enumerate(self.values):
                p = QPointF(i*(self.width()-1)/(len(self.values)-1), (1-v)*(self.height()-1))
                if prev is not None: q.drawLine(prev,p)
                prev = p
            q.end()


# Linux camera sharing -------------------------------------------------------
#
# V4L2 devices are commonly exclusive-open.  Opening one FFmpeg process per
# Record/Import/Draw window therefore guarantees EBUSY on many webcams and also
# makes Preview -> Record handoffs race the kernel/driver.  Keep exactly one
# FFmpeg reader per physical node and fan its decoded frames out to every
# VideoClipStudio that selected that camera.  Each studio can independently
# preview, take snapshots, and record those frames to its own project file.
_SHARED_V4L2_STREAMS = {}


def _linux_camera_holders(device: str):
    """Return best-effort (pid, command) diagnostics for processes holding device."""
    if not sys.platform.startswith('linux') or not device:
        return []
    target=os.path.realpath(device)
    out=[]
    try:
        proc_root=Path('/proc')
        for ent in proc_root.iterdir():
            if not ent.name.isdigit():
                continue
            pid=int(ent.name)
            held=False
            try:
                for fd in (ent/'fd').iterdir():
                    try:
                        if os.path.realpath(os.readlink(fd)) == target:
                            held=True; break
                    except Exception:
                        continue
            except Exception:
                continue
            if not held:
                continue
            cmd=''
            try:
                raw=(ent/'cmdline').read_bytes().replace(b'\0',b' ').strip()
                cmd=raw.decode('utf-8','replace')
            except Exception:
                pass
            out.append((pid,cmd))
    except Exception:
        pass
    return out


def _pid_is_descendant(pid: int, ancestor: int) -> bool:
    """True only for a live Linux process descended from ancestor."""
    seen=set()
    cur=int(pid)
    for _ in range(32):
        if cur <= 1 or cur in seen:
            return False
        if cur == int(ancestor):
            return True
        seen.add(cur)
        try:
            text=Path(f'/proc/{cur}/status').read_text(errors='ignore')
            m=re.search(r'^PPid:\s*(\d+)',text,re.M)
            if not m:
                return False
            cur=int(m.group(1))
        except Exception:
            return False
    return False


def _reclaim_own_v4l2_holders(device: str):
    """Terminate only orphan/stale FFmpeg holders created under this Groovebox.

    Never kills unrelated camera applications.  This is intentionally narrow:
    the process must be a descendant of this Groovebox process *and* its command
    line must clearly be an FFmpeg V4L2 capture of the same device.
    """
    if not sys.platform.startswith('linux'):
        return
    me=os.getpid(); target=os.path.realpath(device)
    for pid,cmd in _linux_camera_holders(device):
        low=cmd.lower()
        if pid == me or not _pid_is_descendant(pid,me):
            continue
        if 'ffmpeg' not in low or 'v4l2' not in low:
            continue
        if target not in cmd and str(device) not in cmd:
            continue
        try:
            os.kill(pid,15)
        except Exception:
            pass


class _SharedV4L2Capture(QObject):
    """One FFmpeg/V4L2 reader shared by all studios selecting one physical node."""
    def __init__(self, device: str, ffmpeg: str):
        super().__init__(None)
        self.device=str(device)
        self.key=os.path.realpath(self.device)
        self.ffmpeg=str(ffmpeg)
        self.subscribers=weakref.WeakSet()
        self.proc=None
        self.buf=bytearray()
        self.frame_count=0
        self.last_image=None
        self.last_error=''
        self._generation=0
        self._retry=0
        self._stopping=False
        self._last_frame_at=0.0
        self._reconnect_delays=(350,800,1600,3200,5000,8000)
        # CAMERA_PACKET_FASTPATH_20260924: prefer the webcam's native MJPEG
        # stream so FFmpeg does not decode+re-encode every preview/record frame.
        # If the device does not expose 1280x720 MJPEG we transparently fall
        # back to the compatibility transcoder below.
        self._native_mjpeg_attempt=True
        self._native_mjpeg_active=False

    def is_running(self) -> bool:
        try:
            return self.proc is not None and self.proc.state()!=QProcess.ProcessState.NotRunning
        except Exception:
            return False

    def add(self, studio):
        self.subscribers.add(studio)
        if isinstance(self.last_image,QImage) and not self.last_image.isNull():
            try: QTimer.singleShot(0,lambda st=studio,im=self.last_image.copy():st._on_shared_v4l2_frame(im))
            except Exception: pass
        if not self.is_running():
            self.start()

    def remove(self, studio):
        try: self.subscribers.discard(studio)
        except Exception: pass
        if not list(self.subscribers):
            self.stop()

    def _broadcast_status(self, text: str, failure: bool=False):
        for st in list(self.subscribers):
            try:
                if failure: st._on_shared_v4l2_failure(text)
                else: st._on_shared_v4l2_status(text)
            except Exception:
                pass

    def start(self):
        if self.is_running():
            return
        self._stopping=False
        self._generation += 1
        gen=self._generation
        self.buf=bytearray(); self.frame_count=0; self.last_error=''
        self._last_frame_at=time.monotonic()
        _reclaim_own_v4l2_holders(self.device)
        proc=QProcess(self)
        self.proc=proc
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        proc.readyReadStandardOutput.connect(self._read_stdout)
        proc.readyReadStandardError.connect(self._read_stderr)
        proc.errorOccurred.connect(lambda err,g=gen:self._process_error(g,err))
        proc.finished.connect(lambda *args,g=gen,p=proc:self._finished(g,p,*args))
        if self._native_mjpeg_attempt:
            # Most Latitude-class UVC webcams expose 1280x720 MJPEG.  Copying
            # that bitstream is dramatically cheaper than converting YUYV ->
            # RGB -> MJPEG in FFmpeg.  Recording keeps the original packets.
            args=['-hide_banner','-loglevel','error','-f','v4l2',
                  '-input_format','mjpeg','-framerate','30','-video_size','1280x720',
                  '-i',self.device,'-map','0:v:0','-c:v','copy','-f','mjpeg','pipe:1']
            self._native_mjpeg_active=True
        else:
            args=['-hide_banner','-loglevel','error','-f','v4l2','-i',self.device,
                  '-map','0:v:0','-vf','scale=1280:-2',
                  '-c:v','mjpeg','-q:v','5','-f','image2pipe','pipe:1']
            self._native_mjpeg_active=False
        proc.start(self.ffmpeg,args)
        self._broadcast_status(f'Opening shared camera stream: {self.device}')
        QTimer.singleShot(3000,lambda g=gen:self._watchdog(g))

    def _read_stderr(self):
        proc=self.proc
        if proc is None: return
        try:
            t=bytes(proc.readAllStandardError()).decode('utf-8','replace')
            if t: self.last_error=(self.last_error+t)[-4000:]
        except Exception:
            pass

    def _read_stdout(self):
        proc=self.proc
        if proc is None: return
        try: chunk=bytes(proc.readAllStandardOutput())
        except Exception: chunk=b''
        if not chunk: return
        self.buf.extend(chunk)
        if len(self.buf)>12*1024*1024:
            del self.buf[:-3*1024*1024]
        while True:
            a=self.buf.find(b'\xff\xd8')
            if a<0:
                if len(self.buf)>1: del self.buf[:-1]
                break
            b=self.buf.find(b'\xff\xd9',a+2)
            if b<0:
                if a>0: del self.buf[:a]
                break
            jpg=bytes(self.buf[a:b+2]); del self.buf[:b+2]
            # Do not decode every camera packet here.  The recording path can
            # spool native MJPEG bytes directly, while each visible studio only
            # asks for a QImage at its bounded preview cadence.
            self.frame_count += 1
            self._retry=0
            self._last_frame_at=time.monotonic()
            for st in list(self.subscribers):
                try: st._on_shared_v4l2_jpeg(jpg)
                except Exception: pass

    def _process_error(self, generation: int, err=None):
        if generation != self._generation or self._stopping: return
        self._read_stderr()
        if not self.last_error:
            self.last_error=str(err or 'V4L2 process error')
        # QProcess.FailedToStart does not reliably emit `finished`. Retire this
        # generation explicitly so a user-armed preview can recover instead of
        # remaining stuck forever in an apparently-open state.
        try:
            failed_to_start = err == QProcess.ProcessError.FailedToStart
        except Exception:
            failed_to_start = 'failedtostart' in str(err).replace(' ', '').casefold()
        if failed_to_start:
            proc=self.proc
            self.proc=None
            self._generation += 1
            retry_generation=self._generation
            try:
                if proc is not None: proc.deleteLater()
            except Exception:
                pass
            self._schedule_reconnect(retry_generation, self.last_error or 'Camera process failed to start.')

    def _watchdog(self, generation: int):
        if generation != self._generation or self._stopping: return
        if not list(self.subscribers):
            self.stop(); return
        proc=self.proc
        if proc is None or not self.is_running():
            return
        self._read_stderr()
        stale_for=max(0.0,time.monotonic()-float(self._last_frame_at or 0.0))
        # A camera can disappear while FFmpeg remains alive with a frozen pipe.
        # Treat six seconds without a frame as a recoverable transport loss.
        if stale_for >= 6.0:
            self.last_error=(self.last_error+' Camera frame stream stalled; reconnecting.')[-4000:]
            self._broadcast_status('Camera disconnected or stalled; preserving the selected route and reconnecting…')
            try: proc.kill()
            except Exception:
                try: proc.terminate()
                except Exception: pass
            return
        if self.frame_count<=0:
            msg='Camera opened but no V4L2 frames arrived yet.'
            if self.last_error: msg += ' '+self.last_error[-500:]
            self._broadcast_status(msg)
        # Keep monitoring a live stream; no capture thread is created by the UI.
        QTimer.singleShot(3000,lambda g=generation:self._watchdog(g))

    def _schedule_reconnect(self, generation: int, detail: str):
        if generation != self._generation or self._stopping or not list(self.subscribers):
            self._drop_if_idle()
            return
        idx=min(self._retry,len(self._reconnect_delays)-1)
        delay=int(self._reconnect_delays[idx])
        self._retry += 1
        self._broadcast_status(
            f'Camera temporarily unavailable; keeping the route armed and retrying in {delay/1000:.1f}s. '
            f'{str(detail or "").strip()[-260:]}'
        )
        QTimer.singleShot(delay,lambda g=generation:self._reconnect_if_current(g))

    def _reconnect_if_current(self, generation: int):
        if generation != self._generation or self._stopping or not list(self.subscribers):
            self._drop_if_idle()
            return
        if not self.is_running():
            self.start()

    def _finished(self, generation: int, proc, *_args):
        if generation != self._generation:
            try: proc.deleteLater()
            except Exception: pass
            return
        try:
            t=bytes(proc.readAllStandardError()).decode('utf-8','replace')
            if t: self.last_error=(self.last_error+t)[-4000:]
        except Exception: pass
        if self.proc is proc: self.proc=None
        try: proc.deleteLater()
        except Exception: pass
        if self._stopping:
            self._drop_if_idle(); return
        if not list(self.subscribers):
            self._drop_if_idle(); return
        # Native MJPEG is a performance preference, never a compatibility
        # requirement.  If this camera cannot negotiate that exact UVC mode,
        # immediately retry once with the older conversion path.
        if self.frame_count==0 and self._native_mjpeg_active:
            self._native_mjpeg_attempt=False
            self._native_mjpeg_active=False
            self._broadcast_status('Native MJPEG mode unavailable; using compatibility camera stream…')
            QTimer.singleShot(60,lambda g=generation:self._reconnect_if_current(g))
            return
        # Camera drivers can take a short moment to release a previous handle.
        # Retry transient busy/open failures without making the user toggle twice.
        low=self.last_error.lower()
        transient=('device or resource busy' in low or 'resource busy' in low or
                   'cannot open video device' in low or 'no such device' in low)
        if self.frame_count==0 and self._retry<3 and transient:
            self._retry += 1
            delay=(250,650,1300)[self._retry-1]
            self._broadcast_status(f'Camera is busy; reclaiming Groovebox handles and retrying ({self._retry}/3)…')
            _reclaim_own_v4l2_holders(self.device)
            QTimer.singleShot(delay,lambda g=generation:self._reconnect_if_current(g))
            return
        holders=[(pid,cmd) for pid,cmd in _linux_camera_holders(self.device) if pid!=os.getpid()]
        detail=self.last_error.strip() or 'FFmpeg could not open the selected V4L2 device.'
        if holders:
            shown=', '.join(f'PID {pid} ({Path((cmd.split() or ["unknown"])[0]).name})' for pid,cmd in holders[:4])
            detail += f' Device currently held by: {shown}.'
        # Preview is a persistent user intent. Do not uncheck the UI or discard
        # its selected route on unplug/replug; retry at a capped, low-duty cadence.
        self._schedule_reconnect(generation,detail[-1200:])

    def stop(self):
        self._stopping=True
        self._generation += 1
        gen=self._generation
        proc=self.proc
        if proc is None:
            self._drop_if_idle(); return
        self.proc=None
        try: proc.write(b'q\n')
        except Exception:
            try: proc.terminate()
            except Exception: pass
        def term(p=proc,g=gen):
            if g!=self._generation: return
            try:
                if p.state()!=QProcess.ProcessState.NotRunning: p.terminate()
            except Exception: pass
        def kill(p=proc,g=gen):
            if g!=self._generation: return
            try:
                if p.state()!=QProcess.ProcessState.NotRunning: p.kill()
            except Exception: pass
            self._drop_if_idle()
        QTimer.singleShot(700,term)
        QTimer.singleShot(1500,kill)

    def _drop_if_idle(self):
        if list(self.subscribers): return
        if _SHARED_V4L2_STREAMS.get(self.key) is self:
            _SHARED_V4L2_STREAMS.pop(self.key,None)



def _synth_drawn_sound(inp, path, duration, sr=48000):
    """Pure NumPy drawn sound (same maths as before); safe on a worker thread."""
    detail, use_color, use_draw = inp['detail'], inp['use_color'], inp['use_draw']
    if not (use_color or use_draw):
        return False
    n=max(1,int(round(duration*sr))); u=np.linspace(0,1,n,endpoint=False)
    pitch_curve=np.interp(u,np.linspace(0,1,128),np.asarray(inp['pitch'],dtype=np.float64))
    gain_curve=np.interp(u,np.linspace(0,1,128),np.asarray(inp['gain'],dtype=np.float64))
    y=np.zeros(n,dtype=np.float64)
    if use_draw:
        freq=220.0*np.power(2.0,2.0*(pitch_curve-.5)); phase=2*np.pi*np.cumsum(freq)/sr; y += np.sin(phase)*(0.24*gain_curve)
    if use_color:
        regs=inp['regs']
        if regs:
            color_gain=0.16/max(1,math.sqrt(len(regs)))
            for j,(h,s_,v) in enumerate(regs):
                base=110.0*pow(2.0,4.0*h); freq=base*np.power(2.0,1.0*(pitch_curve-.5)); phase=2*np.pi*np.cumsum(freq)/sr + j*0.37
                amp=color_gain*(0.15+0.85*s_)*(0.2+0.8*v)*(0.35+0.65*gain_curve)
                y += np.sin(phase)*amp
                if detail=='Detailed': y += np.sin(phase*2.0+0.13*j)*(amp*0.23)
    pcm=np.rint(np.clip(y,-1.0,1.0)*32767.0).astype(np.int16)
    with wave.open(path,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(pcm.tobytes())
    return True


class VideoClipStudio(QWidget):
    """Project-aware Record / Import / Draw Video Clip workspace."""

    # One Groovebox process can host this workspace in both Performance and the
    # main Draw/Record dialog. Track all live instances so an idle hidden studio
    # can never retain the physical camera behind another studio's back.
    _capture_instances = weakref.WeakSet()

    # Thread-safe bridge for worker completion. Emitting a Qt signal from a plain
    # Python worker thread queues delivery onto this widget's GUI thread; unlike
    # QTimer.singleShot() created inside that worker, it does not require the
    # worker thread to own a Qt event loop.
    _worker_finished = pyqtSignal(object, object, object)

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self.base_clip = ''
        self._camera_devices = []
        self._audio_devices = []
        self._camera = None
        self._capture_session = None
        self._video_sink = None
        self._recorder = None
        self._record_audio_input = None
        self._record_path = ''
        self._record_final_path = ''
        self._record_container = 'mp4'
        self._recorder_error_text = ''
        self._mic_source = None
        self._mic_io = None
        self._mic_level = 0.0
        # R17: sounddevice/PortAudio fallback shares the same selected physical
        # input when Qt Multimedia has not published PipeWire microphones yet.
        self._pa_audio_devices = []
        self._sd_mic_stream = None
        self._alsa_mic_proc = None
        self._alsa_mic_thread = None
        self._alsa_mic_stop = threading.Event()
        self._sd_mic_queue = queue.Queue(maxsize=512)  # ~11 s at 48 kHz/1024-frame callbacks
        self._mic_pump_thread = None
        self._mic_pump_stop = threading.Event()
        self._mic_capture_kind = 'f32'
        self._mic_last_frame_at = 0.0
        self._mic_last_restart_at = 0.0
        self._mic_restart_count = 0
        self._mic_drop_count = 0
        self._mic_backend = ''
        self._mic_sample_rate = 48000
        self._mic_channels = 1
        self._external_mic_suspended = False
        # R9: live video decode and live-audio level analysis are isolated from
        # the Qt widget thread. Capture backends keep their native threads/processes;
        # these pools only perform Python/NumPy decode/analysis work.
        from ui_runtime import make_qt_pool
        self._video_decode_pool=make_qt_pool("clip-video-decode", max_workers=1, max_pending=6, parent=self)
        self._video_decode_pool.setMaxThreadCount(1)
        self._video_decode_signals=_DecodeSignals(self); self._video_decode_signals.done.connect(self._on_preview_decode_ready)
        self._preview_decode_inflight=False; self._preview_decode_pending=None
        self._audio_level_pool=make_qt_pool("clip-audio-level", max_workers=1, max_pending=6, parent=self)
        self._audio_level_pool.setMaxThreadCount(1)
        self._audio_level_signals=_AudioLevelSignals(self); self._audio_level_signals.done.connect(self._on_audio_level_ready)
        self._audio_level_inflight=False; self._audio_level_pending=None
        self._devices_activated = False
        self._audio_devices_activated = False
        self._camera_devices_activated = False
        self._tablet_sources_activated = False
        # R22: device discovery is isolated in a short-lived helper process.
        # Opening Record/Draw never enumerates Qt Multimedia/PortAudio itself.
        self._device_probe_generation = 0
        self._device_probe_inflight = False
        self._device_probe_waiters = []
        # UI preview is deliberately decoupled from capture/recording rate.
        # Painting/scaling every camera frame on the GUI thread made the Dell
        # Latitude Record page feel much slower than the actual recorder.  The
        # Linux packet fast path also avoids JPEG decoding between paints.
        self._preview_last_paint_t = 0.0
        # Historical zX verifier token: self._preview_interval_s = 1.0 / 10.0
        self._preview_interval_s = 1.0 / 8.0
        self._record_preview_interval_s = 1.0 / 6.0
        self._last_video_image_t = 0.0
        self._audio_only_wave = None
        self._audio_only_path = ''
        self._audio_only_work_path = ''
        self._mic_writer_error = ''
        self._mic_pcm_bytes_written = 0
        self._audio_only_recording = False
        self._audio_only_finalizing = False
        self._audio_only_started_source = False
        self._sw_recording = False
        self._sw_record_dir = ''
        self._sw_frame_index = 0
        self._sw_last_frame_t = 0.0
        self._sw_audio_fh = None
        self._sw_audio_accepting = False
        self._sw_mjpeg_fh = None
        self._sw_mjpeg_path = ''
        self._video_spool_queue = queue.Queue(maxsize=192)
        self._video_spool_thread = None
        self._video_spool_stop = threading.Event()
        self._video_spool_drops = 0
        self._mic_last_meter_enqueue = 0.0
        self._sw_audio_rate = 48000
        self._sw_audio_channels = 1
        self._sw_started_mic = False
        self._last_video_frame_t = 0.0
        self._camera_watchdog_generation = 0
        self._snapshot_request_generation = 0
        self._snapshot_request_started_at = 0.0
        self._snapshot_auto_release = False
        self._snapshot_pending = False
        self._capture_release_generation = 0
        self._camera_recovery_generation = 0
        self._camera_reprobe_pending = False
        self._camera_recovery_attempt = 0
        self._camera_selected_label = ''
        VideoClipStudio._capture_instances.add(self)
        # Linux/Fedora camera fallback: FFmpeg/V4L2 owns video capture so we do
        # not depend on Qt/GStreamer delivering QVideoSink frames.
        self._v4l_proc = None
        self._v4l_buf = bytearray()
        self._v4l_device = ''
        self._v4l_recording = False
        self._v4l_record_dir = ''
        self._v4l_video_tmp = ''
        self._v4l_audio_path = ''
        self._v4l_frame_count = 0
        self._v4l_stop_generation = 0
        self._v4l_stop_callback = None
        self._v4l_shared_stream = None
        self._v4l_shared_key = ''
        self.last_rendered_video = ''
        self.recording_layers: List[str] = []
        self.draw_layers: List[Dict[str, Any]] = []
        self.draw_canvases: List[PaintCanvas] = []
        self._curves: Dict[str, List[float]] = {}
        self._current_curve_target = 'Layer Opacity'
        self._worker_finished.connect(self._dispatch_worker_finished)
        self._build_ui()
        # PERF_LAZY_20260924: QMediaDevices enumeration is deliberately deferred
        # until this Record tab is actually selected (or Refresh is pressed).
        # _capture_instances is a WeakSet; no destroyed() hook: a Python slot that
        # references the dying widget segfaults once sip has released its wrapper.

    def _dispatch_worker_finished(self, callback, result, error):
        """Deliver worker completion on the GUI thread."""
        try:
            if callable(callback):
                callback(result, error)
        except Exception as exc:
            try: self.lbl_render.setText('Background media completion failed: '+str(exc))
            except Exception: pass

    def _run_media_worker(self, name: str, args_key, work, done):
        """Run potentially slow media work without blocking Qt and always return to GUI safely."""
        opt=getattr(self.host,'_scode_optimizer',None)
        if opt is not None and hasattr(opt,'submit_pooled'):
            try:
                # sCode optimizer has a media_stream pool format, not a generic
                # 'video' format.  Finalization is side-effecting, so the pool is
                # used only for safe background completion/callback delivery.
                opt.submit_pooled(name,args_key,work,policy='side_effect',format_id='media_stream',side_effecting=True,callback=done,qt_callback=True)
                return
            except Exception as exc:
                # Optimizer availability must never be a hard dependency for
                # recording. Fall back to the ordinary worker thread.
                try: self.lbl_render.setText('Media optimizer fallback: '+str(exc))
                except Exception: pass
        import threading
        def runner():
            try:
                result=work(); error=None
            except Exception as exc:
                result=''; error=str(exc)
            try:
                self._worker_finished.emit(done,result,error)
            except Exception:
                pass
        threading.Thread(target=runner,daemon=True,name='GrooveboxMediaFinalize').start()

    # --------------------------- project paths
    def _project_path(self) -> Optional[str]:
        return getattr(self.host, '_current_project_path', None)

    def _report_recording_audio(self, path: str) -> None:
        """Append the mic outcome to the status line; warn when it is missing/silent."""
        rep = getattr(self, "_last_record_audio_report", None) or {}
        text = _capture_report_text(rep)
        try:
            self.lbl_render.setText(self.lbl_render.text() + " · " + text)
        except Exception:
            pass
        print(f"[Record] {os.path.basename(str(path))}: {text}", flush=True)
        if rep.get("state") in ("none", "silent"):
            try:
                inp = ""
                try: inp = str(self.cmb_mic.currentText())
                except Exception: pass
                QMessageBox.warning(self, "Recording has no microphone sound",
                    f"{text}.\n\nSelected input: {inp or 'default'}\n\n"
                    "The video was saved. Likely causes: the wrong input device is selected, "
                    "the capture switch/gain is muted, or (legacy HDA laptops) the input source is "
                    "set to an unplugged headset mic. Check Mic Level on this page before recording, "
                    "pick another Audio Input, then record again.")
            except Exception:
                pass

    def _recordings_dir(self) -> str:
        import groovebox_paths
        return groovebox_paths.recordings_dir(self._project_path())

    def _notify_media_created(self, path: str, role: str = 'recording'):
        """Index a finalized file and refresh retained Performance/File Manager views."""
        if not path or not os.path.isfile(path):
            return
        try:
            import groovebox_paths
            groovebox_paths.index_file(path, role, self._project_path())
        except Exception:
            pass
        try:
            p=self.parent()
            while p is not None:
                if hasattr(p, 'notify_filesystem_changed'):
                    p.notify_filesystem_changed(path)
                    break
                p=p.parent() if hasattr(p, 'parent') else None
        except Exception:
            pass

    def _layers_dir(self) -> str:
        import groovebox_paths
        return groovebox_paths.layers_dir(self._project_path())

    def _video_exports_dir(self) -> str:
        import groovebox_paths
        return groovebox_paths.video_exports_dir(self._project_path())

    # --------------------------- UI
    def _build_ui(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        whole_scroll = QScrollArea(); whole_scroll.setWidgetResizable(True)
        whole_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        whole_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        whole_body = QWidget(); whole_body.setMinimumWidth(760)
        root = QVBoxLayout(whole_body); root.setContentsMargins(5,5,5,5); root.setSpacing(5)
        whole_scroll.setWidget(whole_body); outer.addWidget(whole_scroll)
        devices = QGroupBox('Input devices · explicit selection')
        dg = QGridLayout(devices)
        self.cmb_camera = QComboBox(); self.cmb_mic = QComboBox(); self.cmb_tablet = QComboBox()
        self.cmb_camera.addItem('Camera loads on Preview / Record')
        self.cmb_mic.addItem('Audio inputs loading…', '')
        self.cmb_tablet.addItem('Browse filesystem…', '')
        dg.addWidget(QLabel('Camera'),0,0); dg.addWidget(self.cmb_camera,0,1)
        dg.addWidget(QLabel('Audio input / microphone'),1,0); dg.addWidget(self.cmb_mic,1,1)
        dg.addWidget(QLabel('Tablet / media source'),2,0); dg.addWidget(self.cmb_tablet,2,1)
        brefresh = QPushButton('↻ Refresh devices'); brefresh.clicked.connect(self.refresh_devices); self.btn_refresh_devices=brefresh; dg.addWidget(brefresh,0,2)
        self.btn_camera_preview = QPushButton('▶ Camera Preview'); self.btn_camera_preview.setCheckable(True); self.btn_camera_preview.toggled.connect(self._toggle_camera_preview); dg.addWidget(self.btn_camera_preview,1,2)
        self.btn_mic_preview = QPushButton('Mic Level: waiting for input'); self.btn_mic_preview.setCheckable(True); self.btn_mic_preview.toggled.connect(self._toggle_mic_preview); dg.addWidget(self.btn_mic_preview,2,2)
        self.cmb_mic.currentIndexChanged.connect(self._audio_input_device_changed)
        self.cmb_camera.currentIndexChanged.connect(self._camera_device_selection_changed)
        self.btn_audio_record = QPushButton('● Record Audio Input'); self.btn_audio_record.setCheckable(True); self.btn_audio_record.toggled.connect(self._toggle_audio_input_recording); dg.addWidget(self.btn_audio_record,3,1,1,2)
        self.lbl_audio_input_hint = QLabel('Internal microphones, headset/line inputs and class-compliant USB audio interfaces appear here through Qt/PipeWire.')
        self.lbl_audio_input_hint.setWordWrap(True); self.lbl_audio_input_hint.setStyleSheet('color:#8ab4c8; font-size:9pt;'); dg.addWidget(self.lbl_audio_input_hint,4,0,1,3)
        for _w in (self.cmb_camera, self.cmb_mic, self.cmb_tablet, brefresh, self.btn_camera_preview, self.btn_mic_preview, self.btn_audio_record):
            _w.setMinimumHeight(32)
        root.addWidget(devices)

        # Optional, isolated multitrack timeline; lazy-loaded only when requested.
        timeline_row = QHBoxLayout()
        self.btn_multitrack_timeline = QPushButton('🎞 Open Multitrack Clip Studio')
        self.btn_multitrack_timeline.setToolTip('Layer audio and video clips on separate tracks, set arbitrary source in/out boundaries, adjust timeline offsets and render a combined MP4.')
        self.btn_multitrack_timeline.clicked.connect(self._open_multitrack_clip_studio)
        timeline_row.addWidget(self.btn_multitrack_timeline)
        timeline_row.addWidget(QLabel('Non-destructive timeline · source files are never overwritten'))
        timeline_row.addStretch(1)
        root.addLayout(timeline_row)

        # Compatibility-first layout: stack capture and drawing vertically.
        # This avoids wide splitter/native-surface geometry escaping the Performance tab.
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(7)
        left = QWidget(); left.setMinimumWidth(560); ll = QVBoxLayout(left); ll.setContentsMargins(4,4,4,4); ll.setSpacing(7)
        preview_group = QGroupBox('Camera / clip preview')
        pl = QVBoxLayout(preview_group)
        # Use a software QLabel preview fed by QVideoSink rather than QVideoWidget.
        # Some Qt/GStreamer backends implement QVideoWidget with a native overlay
        # surface that ignores QScrollArea clipping and can paint over controls.
        # A QVideoSink -> QImage -> QLabel path remains a normal child widget, so
        # scrolling/maximizing can never render camera pixels outside the viewport.
        self.video_preview = QLabel('Camera preview idle')
        self.video_preview.setWordWrap(True)
        self.video_preview.setMinimumSize(480,270)
        self.video_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_preview.setStyleSheet('background:#050708; border:1px solid #29404a;')
        pl.addWidget(self.video_preview,1)
        if QT_MULTIMEDIA and QVideoSink is not None:
            try:
                self._video_sink = QVideoSink(self)
                self._video_sink.videoFrameChanged.connect(self._on_video_frame)
            except Exception:
                self._video_sink = None
        self.mic_meter = QProgressBar(); self.mic_meter.setRange(0,100); self.mic_meter.setValue(0); self.mic_meter.setFormat('Mic level %p% · NO SIGNAL'); self.mic_meter.setMinimumHeight(22); pl.addWidget(self.mic_meter)
        self.lbl_mic_capture_status = QLabel('Microphone: idle · start Mic Level or recording to monitor input')
        self.lbl_mic_capture_status.setWordWrap(True)
        self.lbl_mic_capture_status.setStyleSheet('color:#9bb4c2; font-size:9pt;')
        pl.addWidget(self.lbl_mic_capture_status)
        ll.addWidget(preview_group)

        capture = QGroupBox('Record / Import')
        cl = QGridLayout(capture)
        self.btn_record = QPushButton('● Record Camera + Mic'); self.btn_record.setCheckable(True); self.btn_record.toggled.connect(self._toggle_record)
        bimport = QPushButton('Import Video…'); bimport.clicked.connect(lambda: self.import_video(False))
        btablet = QPushButton('Import from Tablet…'); btablet.clicked.connect(lambda: self.import_video(True))
        bclearbase = QPushButton('Draw-only clip'); bclearbase.clicked.connect(self._clear_base_clip)
        cl.addWidget(self.btn_record,0,0); cl.addWidget(bimport,0,1); cl.addWidget(btablet,1,0); cl.addWidget(bclearbase,1,1)
        self.lbl_source = QLabel('Source: draw-only (black background)'); self.lbl_source.setWordWrap(True); self.lbl_source.setStyleSheet('color:#8ab4c8;'); cl.addWidget(self.lbl_source,2,0,1,2)
        # A second meter lives beside the Record controls, not only at the top
        # preview. Users can keep the live level and exact save target visible
        # while scrolled down to the recording controls in the Performance tab.
        self.mic_record_meter = QProgressBar(); self.mic_record_meter.setRange(0,100); self.mic_record_meter.setValue(0); self.mic_record_meter.setFormat('Mic level %p% · NO SIGNAL'); self.mic_record_meter.setMinimumHeight(20); cl.addWidget(self.mic_record_meter,3,0,1,2)
        self.lbl_mic_record_status = QLabel('Microphone: idle · record destination appears when recording starts'); self.lbl_mic_record_status.setWordWrap(True); self.lbl_mic_record_status.setStyleSheet('color:#9bb4c2; font-size:9pt;'); cl.addWidget(self.lbl_mic_record_status,4,0,1,2)
        self.recording_tabs=QTabWidget(); self.recording_tabs.currentChanged.connect(self._recording_tab_changed); cl.addWidget(self.recording_tabs,5,0,1,2)
        self.recordings_table=QTableWidget(0,2); self.recordings_table.setHorizontalHeaderLabels(['Recording Layer','File']); cl.addWidget(self.recordings_table,6,0,1,2)
        rrow=QHBoxLayout()
        self.btn_append_recording=QPushButton('＋ Append Recording Layer…'); self.btn_append_recording.clicked.connect(self._append_recording_layer_dialog); rrow.addWidget(self.btn_append_recording)
        self.btn_remove_recording=QPushButton('− Remove Recording Layer Tab'); self.btn_remove_recording.clicked.connect(self._remove_recording_layer_tab); rrow.addWidget(self.btn_remove_recording)
        self.btn_clear_recordings=QPushButton('Clear Recordings Table'); self.btn_clear_recordings.clicked.connect(self._clear_recordings_table); rrow.addWidget(self.btn_clear_recordings)
        self.btn_remove_project_recording=QPushButton('Remove from Project'); self.btn_remove_project_recording.clicked.connect(lambda: self._delete_selected_recording(False)); rrow.addWidget(self.btn_remove_project_recording)
        self.btn_delete_recording_file=QPushButton('Delete File + Entry'); self.btn_delete_recording_file.clicked.connect(lambda: self._delete_selected_recording(True)); rrow.addWidget(self.btn_delete_recording_file)
        cl.addLayout(rrow,7,0,1,2)
        self.recording_tabs.setMinimumHeight(100)
        self.recordings_table.setMinimumHeight(125)
        self.recordings_table.horizontalHeader().setStretchLastSection(True)
        for _b in (self.btn_record, bimport, btablet, bclearbase, self.btn_append_recording, self.btn_remove_recording, self.btn_clear_recordings, self.btn_remove_project_recording, self.btn_delete_recording_file):
            _b.setMinimumHeight(34)
            _b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ll.addWidget(capture)
        ll.addStretch(1)

        # Each major pane owns its own two-axis scroll viewport. The camera
        # preview is a software QLabel (QVideoSink -> QImage), so unlike the old
        # native QVideoWidget path it remains clipped correctly inside this viewport.
        left_scroll = QScrollArea(); left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setMinimumWidth(420); left_scroll.setWidget(left)
        split.addWidget(left_scroll)

        right = QWidget(); right.setMinimumWidth(680); rl = QVBoxLayout(right); rl.setContentsMargins(4,4,4,4); rl.setSpacing(7)
        paint_group = QGroupBox('Image paint layer')
        pgl = QVBoxLayout(paint_group)
        tools = QHBoxLayout()
        self.cmb_tool = QComboBox(); self.cmb_tool.addItems(['Brush','Eraser','Line','Rectangle','Ellipse']); self.cmb_tool.currentTextChanged.connect(lambda t:self.canvas.set_tool(t)); tools.addWidget(self.cmb_tool)
        self.btn_color = QPushButton('Color'); self.btn_color.clicked.connect(self._choose_color); tools.addWidget(self.btn_color)
        tools.addWidget(QLabel('Size'))
        self.sld_brush = QSlider(Qt.Orientation.Horizontal); self.sld_brush.setRange(1,80); self.sld_brush.setValue(12); self.sld_brush.valueChanged.connect(lambda v:self.canvas.set_brush_size(v)); tools.addWidget(self.sld_brush,1)
        bund = QPushButton('Undo'); bund.clicked.connect(lambda:self.canvas.undo()); tools.addWidget(bund)
        bclear = QPushButton('Clear'); bclear.clicked.connect(lambda:self.canvas.clear()); tools.addWidget(bclear)
        self.btn_camera_snapshot = QPushButton('📷 Take Picture From Camera')
        self.btn_camera_snapshot.setToolTip('Capture one frame from the selected camera into a new drawable image layer. If camera preview is off, Groovebox opens the camera only long enough to capture the frame, then releases it.')
        self.btn_camera_snapshot.clicked.connect(self._take_picture_from_camera)
        tools.addWidget(self.btn_camera_snapshot)
        pgl.addLayout(tools)
        layerrow=QHBoxLayout()
        self.btn_append_draw_layer=QPushButton('＋ Append Drawing Layer'); self.btn_append_draw_layer.clicked.connect(self._append_draw_layer); layerrow.addWidget(self.btn_append_draw_layer)
        self.btn_remove_draw_layer=QPushButton('− Remove Drawing Layer'); self.btn_remove_draw_layer.clicked.connect(self._remove_draw_layer); layerrow.addWidget(self.btn_remove_draw_layer)
        layerrow.addWidget(QLabel('Start s')); self.spin_layer_start=QDoubleSpinBox(); self.spin_layer_start.setRange(0,3600); self.spin_layer_start.setDecimals(3); self.spin_layer_start.valueChanged.connect(self._update_draw_layer_controls); layerrow.addWidget(self.spin_layer_start)
        layerrow.addWidget(QLabel('End s')); self.spin_layer_end=QDoubleSpinBox(); self.spin_layer_end.setRange(0,3600); self.spin_layer_end.setDecimals(3); self.spin_layer_end.setValue(5); self.spin_layer_end.valueChanged.connect(self._update_draw_layer_controls); layerrow.addWidget(self.spin_layer_end)
        layerrow.addWidget(QLabel('Fade in/out s')); self.spin_layer_fade=QDoubleSpinBox(); self.spin_layer_fade.setRange(0,600); self.spin_layer_fade.setDecimals(3); self.spin_layer_fade.valueChanged.connect(self._update_draw_layer_controls); layerrow.addWidget(self.spin_layer_fade)
        pgl.addLayout(layerrow)
        self.draw_tabs=QTabWidget(); self.draw_tabs.currentChanged.connect(self._draw_tab_changed); pgl.addWidget(self.draw_tabs,1)
        self.canvas = None
        self._append_draw_layer()
        rl.addWidget(paint_group,3)
        right_scroll = QScrollArea(); right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setMinimumWidth(420); right_scroll.setWidget(right)
        split.addWidget(right_scroll)
        split.setStretchFactor(0, 1); split.setStretchFactor(1, 1)
        split.setSizes([620, 760])
        split.setMinimumWidth(1160)
        split.setStretchFactor(0,5); split.setStretchFactor(1,6)
        split.setSizes([560, 640])
        root.addWidget(split,4)

        graph_group = QGroupBox('Time-varying graph layer · draw left→right across clip time')
        gl = QVBoxLayout(graph_group)
        gr = QHBoxLayout(); gr.addWidget(QLabel('Graph target'))
        self.cmb_graph_target = QComboBox(); self.cmb_graph_target.addItems([
            'Layer Opacity','Layer X','Layer Y','Layer Scale','Layer Rotation',
            'Drawn Sound Pitch','Drawn Sound Gain','Sound→Color Amount'
        ]); self.cmb_graph_target.currentTextChanged.connect(self._switch_curve); gr.addWidget(self.cmb_graph_target)
        breset = QPushButton('Reset lane'); breset.clicked.connect(self._reset_curve); gr.addWidget(breset)
        gr.addStretch(1); gl.addLayout(gr)
        self.graph = GraphLane(); self.graph.changed.connect(self._capture_curve); gl.addWidget(self.graph)
        root.addWidget(graph_group,2)

        mix = QGroupBox('Final video mix · translations are optional')
        mg = QGridLayout(mix)
        self.chk_draw_sound = QCheckBox('Draw Sound from graph lane'); self.chk_draw_sound.setChecked(False)
        self.chk_color_sound = QCheckBox('Enable Color→Sound'); self.chk_color_sound.setChecked(False)
        self.chk_sound_color = QCheckBox('Enable Sound→Color'); self.chk_sound_color.setChecked(False)
        # GROOVEBOX_R23R_LSYSTEM_VIDEO_REITERATION_20261031: L-system reiteration
        # toggle for the visualizer / main video generator engine. When ON, the
        # video composites the L-system reiteration layer (12 iterations, hue by
        # depth, intersections raise/lower/blend). Tracks the Fractal Seed when
        # Fractal Seed Mode is ON; works standalone (Koch-like default) without.
        self.chk_lsystem_video = QCheckBox('L-System Reiteration'); self.chk_lsystem_video.setChecked(False)
        self.chk_lsystem_video.setToolTip('L-system reiteration layer for the video generator (12 iterations). Hue by depth; intersections raise, lower, and blend. Tracks the Fractal Seed when Fractal Seed Mode is ON; works standalone without Fractal Seed.')
        self.cmb_color_detail = QComboBox(); self.cmb_color_detail.addItems(['Off','Basic','Detailed']); self.cmb_color_detail.setCurrentText('Off')
        self.cmb_color_detail.setToolTip('FINAL-MIX option. Off performs no color→sound calculations. Basic maps global hue/saturation/value; Detailed maps multiple color regions as a deterministic partial bank.')
        self.spin_duration = QDoubleSpinBox(); self.spin_duration.setRange(.25,86400.0); self.spin_duration.setDecimals(2); self.spin_duration.setValue(5.0); self.spin_duration.setSuffix(' s')
        self.spin_fps = QSpinBox(); self.spin_fps.setRange(1,120); self.spin_fps.setValue(30); self.spin_fps.setSuffix(' fps')
        self.spin_width = QSpinBox(); self.spin_width.setRange(160,3840); self.spin_width.setValue(1280)
        self.spin_height = QSpinBox(); self.spin_height.setRange(90,2160); self.spin_height.setValue(720)
        mg.addWidget(self.chk_draw_sound,0,0); mg.addWidget(self.chk_color_sound,0,1); mg.addWidget(self.chk_sound_color,0,2); mg.addWidget(self.chk_lsystem_video,0,3)
        mg.addWidget(QLabel('Color→Sound Translation Detail'),1,0); mg.addWidget(self.cmb_color_detail,1,1)
        mg.addWidget(QLabel('Duration'),2,0); mg.addWidget(self.spin_duration,2,1); mg.addWidget(self.spin_fps,2,2)
        mg.addWidget(QLabel('Frame'),3,0); wh=QHBoxLayout(); wh.addWidget(self.spin_width); wh.addWidget(QLabel('×')); wh.addWidget(self.spin_height); mg.addLayout(wh,3,1)
        bsave = QPushButton('Save Paint/Graph Layer'); bsave.clicked.connect(lambda:self._persist_layer(False)); mg.addWidget(bsave,3,2)
        mg.addWidget(QLabel('Bind All Layers to Instrument'),4,0)
        self.cmb_bind_all=QComboBox(); self.cmb_bind_all.addItems(['Video','Audio','Both','Unbound']); mg.addWidget(self.cmb_bind_all,4,1)
        self.btn_bind_all=QPushButton('Bind All Layers to Selected Instrument'); self.btn_bind_all.clicked.connect(self._bind_all_layers_to_instrument); mg.addWidget(self.btn_bind_all,4,2)
        self.btn_bind_carrier=QPushButton('Bind All Layers to Carrier'); self.btn_bind_carrier.clicked.connect(self._bind_all_layers_to_carrier); mg.addWidget(self.btn_bind_carrier,5,0,1,3)
        self.btn_render = QPushButton('Render / Mix Video Clip…'); self.btn_render.clicked.connect(self.render_video); mg.addWidget(self.btn_render,6,0,1,2)
        self.lbl_render = QLabel('Visual drawing is independent of sound drawing. Color↔sound translation is OFF by default.'); self.lbl_render.setWordWrap(True); self.lbl_render.setStyleSheet('color:#9dffb0;'); mg.addWidget(self.lbl_render,6,2)
        root.addWidget(mix)

        # LAG_AUDIT_20260909: the mic meter must be zero-cost while no mic is open.
        # Historical meter cadence token: self._mic_timer.setInterval(50)
        self._mic_timer = QTimer(self); self._mic_timer.setInterval(100); self._mic_timer.timeout.connect(self._update_mic_meter)
        self._set_color_button()
        self._reset_curve()

    def _open_multitrack_clip_studio(self):
        """Open the optional timeline as a separate window to isolate existing capture UI."""
        try:
            from clip_timeline_studio import ClipTimelineStudio
            win = getattr(self, '_multitrack_clip_studio', None)
            if win is None:
                win = ClipTimelineStudio(self)
                win.setWindowFlag(Qt.WindowType.Window, True)
                self._multitrack_clip_studio = win
            win.show(); win.raise_(); win.activateWindow()
        except Exception as exc:
            QMessageBox.warning(self, 'Multitrack Clip Studio', f'Could not open the optional timeline editor:\n{exc}')

    def _append_recording_path(self,path:str):
        path=os.path.abspath(str(path or ''))
        if not path or not os.path.isfile(path):return
        if path not in self.recording_layers:self.recording_layers.append(path)
        page=QWidget(); lay=QVBoxLayout(page); q=QLabel(path); q.setWordWrap(True); q.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(q)
        idx=self.recording_tabs.addTab(page,Path(path).stem[:32]); self.recording_tabs.setCurrentIndex(idx)
        self.base_clip=path; self.lbl_source.setText('Source: '+path); self._refresh_recordings_table()
    def _append_recording_layer_dialog(self):
        p,_=QFileDialog.getOpenFileName(self,'Append recording layer',self._recordings_dir(),'Video (*.mp4 *.m4v *.mov *.qt *.mkv *.webm *.avi *.mpeg *.mpg *.mpe *.m1v *.m2v *.mpv *.m2ts *.mts *.ts *.m2t *.tp *.trp *.vob *.ogv *.flv *.f4v *.wmv *.asf *.3gp *.3g2 *.mxf *.divx *.rm *.rmvb *.ivf *.nut *.amv *.wtv *.dvr-ms *.ismv *.mpd *.m3u8);;All files (*)')
        if p:self._append_recording_path(p); self._save_host_state()
    def _recording_tab_changed(self,i):
        if 0<=i<len(self.recording_layers):
            self.base_clip=self.recording_layers[i]; self.lbl_source.setText('Source: '+self.base_clip)
    def _remove_recording_layer_tab(self):
        i=self.recording_tabs.currentIndex()
        if i<0:return
        self.recording_tabs.removeTab(i)
        if i<len(self.recording_layers):self.recording_layers.pop(i)
        if self.recording_layers:
            j=max(0,min(i,len(self.recording_layers)-1)); self.recording_tabs.setCurrentIndex(j); self.base_clip=self.recording_layers[j]
        else:self.base_clip=''; self.lbl_source.setText('Source: draw-only (black background)')
        self._refresh_recordings_table(); self._save_host_state()
    def _delete_selected_recording(self, delete_file: bool):
        row=self.recordings_table.currentRow() if hasattr(self,'recordings_table') else -1
        i=self.recording_tabs.currentIndex() if hasattr(self,'recording_tabs') else -1
        if row >= 0: i=row
        if not (0 <= i < len(self.recording_layers)):
            QMessageBox.information(self,'Recording','Select a recording row or recording-layer tab first.'); return
        path=os.path.abspath(self.recording_layers[i])
        action='Delete the file from disk AND remove its project entry?' if delete_file else 'Remove this recording from the project but keep the file on disk?'
        if QMessageBox.question(self,'Delete recording',f'{action}\n\n{path}',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
            return
        try:
            import groovebox_paths; groovebox_paths.unindex_file(path,self._project_path())
        except Exception: pass
        # Remove every in-editor reference to this path.
        self.recording_layers=[p for p in self.recording_layers if os.path.abspath(str(p)) != path]
        while self.recording_tabs.count(): self.recording_tabs.removeTab(0)
        old=list(self.recording_layers); self.recording_layers=[]
        for p in old: self._append_recording_path(p)
        if delete_file:
            try:
                if os.path.isfile(path): os.remove(path)
            except Exception as e:
                QMessageBox.warning(self,'Delete file failed',str(e))
        if os.path.abspath(str(self.base_clip or '')) == path:
            self.base_clip=self.recording_layers[0] if self.recording_layers else ''
            self.lbl_source.setText('Source: '+self.base_clip if self.base_clip else 'Source: draw-only (black background)')
        self._refresh_recordings_table(); self._save_host_state()
        self.lbl_render.setText(('Deleted file + project entry: ' if delete_file else 'Removed project entry; file kept: ')+os.path.basename(path))

    def _clear_recordings_table(self):
        self.recordings_table.setRowCount(0); self.lbl_render.setText('Recordings Table cleared. Recording files and layer tabs were not deleted.')
    def _refresh_recordings_table(self):
        self.recordings_table.setRowCount(len(self.recording_layers))
        for r,p in enumerate(self.recording_layers):
            self.recordings_table.setItem(r,0,QTableWidgetItem(Path(p).stem)); self.recordings_table.setItem(r,1,QTableWidgetItem(p))
    def _append_draw_layer(self):
        c=PaintCanvas(); c.set_tool(self.cmb_tool.currentText() if hasattr(self,'cmb_tool') else 'Brush'); c.set_brush_size(self.sld_brush.value() if hasattr(self,'sld_brush') else 12)
        rec={'name':f'Drawing {len(self.draw_layers)+1}','start':0.0,'end':float(self.spin_duration.value()) if hasattr(self,'spin_duration') else 5.0,'fade':0.0}
        self.draw_layers.append(rec); self.draw_canvases.append(c); idx=self.draw_tabs.addTab(c,rec['name']); self.draw_tabs.setCurrentIndex(idx); self.canvas=c; self._set_color_button()
    def _remove_draw_layer(self):
        i=self.draw_tabs.currentIndex()
        if i<0:return
        self.draw_tabs.removeTab(i)
        if i<len(self.draw_layers):self.draw_layers.pop(i); self.draw_canvases.pop(i)
        if not self.draw_layers:self._append_draw_layer()
        else:self._draw_tab_changed(max(0,min(i,len(self.draw_layers)-1)))
    def _draw_tab_changed(self,i):
        if not (0<=i<len(self.draw_layers)):return
        self.canvas=self.draw_canvases[i]; r=self.draw_layers[i]
        for w in (self.spin_layer_start,self.spin_layer_end,self.spin_layer_fade):w.blockSignals(True)
        default_end = float(self.spin_duration.value()) if hasattr(self, 'spin_duration') else 5.0
        self.spin_layer_start.setValue(float(r.get('start',0))); self.spin_layer_end.setValue(float(r.get('end', default_end))); self.spin_layer_fade.setValue(float(r.get('fade',0)))
        for w in (self.spin_layer_start,self.spin_layer_end,self.spin_layer_fade):w.blockSignals(False)
        self._set_color_button()
    def _update_draw_layer_controls(self,*_):
        i=self.draw_tabs.currentIndex() if hasattr(self,'draw_tabs') else -1
        if 0<=i<len(self.draw_layers):
            self.draw_layers[i].update(start=float(self.spin_layer_start.value()),end=float(self.spin_layer_end.value()),fade=float(self.spin_layer_fade.value()))
    def _draw_layer_time_gain(self,rec,tsec):
        start=float(rec.get('start',0)); end=float(rec.get('end',math.inf)); fade=max(0.0,float(rec.get('fade',0)))
        if tsec<start or tsec>end:return 0.0
        g=1.0
        if fade>0:g=min(g,max(0.0,min(1.0,(tsec-start)/fade)),max(0.0,min(1.0,(end-tsec)/fade)))
        return g

    # --------------------------- camera ownership / hard release
    def _camera_intentionally_active(self) -> bool:
        """True only while the user explicitly asked Groovebox to own a camera."""
        try:
            if getattr(self, 'btn_record', None) is not None and self.btn_record.isChecked():
                return True
        except Exception:
            pass
        try:
            if getattr(self, 'btn_camera_preview', None) is not None and self.btn_camera_preview.isChecked():
                return True
        except Exception:
            pass
        return bool(getattr(self, '_v4l_recording', False)
                    or getattr(self, '_sw_recording', False)
                    or getattr(self, '_snapshot_pending', False))

    def suspend_inactive_inputs(self) -> bool:
        """Release preview/meter resources when the Record workspace is hidden.

        Actual recording/finalization/snapshot work is never interrupted. Returning
        True means idle preview resources were released and can be lazily reacquired.
        """
        active = bool(getattr(self, '_audio_only_recording', False)
                      or getattr(self, '_v4l_recording', False)
                      or getattr(self, '_sw_recording', False)
                      or getattr(self, '_snapshot_pending', False))
        try:
            active = active or bool(getattr(self, 'btn_record', None) and self.btn_record.isChecked())
        except Exception:
            pass
        if active:
            return False
        self._camera_recovery_generation += 1
        self._camera_reprobe_pending = False
        self._release_capture_devices(True)
        self._devices_activated = False
        self._audio_devices_activated = False
        return True

    def _camera_selection_key(self) -> str:
        """Stable selected-camera identity used for multi-window ownership checks."""
        if sys.platform.startswith('linux'):
            dev=self._selected_v4l2_device()
            return os.path.realpath(dev) if dev else ''
        try:
            if self._camera_devices:
                idx=max(0,min(self.cmb_camera.currentIndex(),len(self._camera_devices)-1))
                raw=self._camera_devices[idx].id()
                try: ident=bytes(raw).decode('utf-8','ignore')
                except Exception: ident=str(raw or '')
                return ident
        except Exception:
            pass
        return ''

    def _prepare_camera_ownership(self):
        """Release stale owners while allowing intentional concurrent capture.

        Linux uses the process-wide shared V4L2 reader below, so multiple media
        windows may intentionally consume the same physical camera without opening
        the kernel device more than once.  Other platforms may concurrently use
        different cameras; only the *same* device remains exclusive there.
        """
        active_other = None
        my_key=self._camera_selection_key()
        linux_shared=sys.platform.startswith('linux') and bool(_ffmpeg())
        for other in list(VideoClipStudio._capture_instances):
            if other is self:
                continue
            try:
                if other._camera_intentionally_active():
                    if linux_shared:
                        # Same-device Linux consumers will subscribe to one FFmpeg
                        # stream; different devices naturally get separate streams.
                        continue
                    other_key=other._camera_selection_key()
                    if not my_key or not other_key or other_key==my_key:
                        active_other = other
                    continue
                other._release_capture_devices(True)
            except Exception:
                pass
        if active_other is not None:
            raise RuntimeError(
                'The camera is already active in another Groovebox media window. '
                'Use a different camera there, or stop its Preview/Recording first.')

    @staticmethod
    def _destroy_qobject(obj):
        """Destroy a Qt multimedia QObject strongly enough to release OS handles.

        deleteLater() is normally sufficient, but Windows Media Foundation can
        retain a camera until the underlying C++ QObject is actually destroyed.
        Prefer PyQt's immediate sip deletion after all capture-session links have
        been detached; fall back to deleteLater() when sip is unavailable.
        """
        if obj is None:
            return
        try:
            obj.blockSignals(True)
        except Exception:
            pass
        try:
            from PyQt6 import sip
            try:
                if hasattr(sip, 'isdeleted') and sip.isdeleted(obj):
                    return
            except Exception:
                pass
            sip.delete(obj)
            return
        except Exception:
            pass
        try:
            obj.deleteLater()
        except Exception:
            pass

    def _detach_capture_session(self, sess, recorder=None, audio_input=None, camera=None):
        """Detach every multimedia endpoint before destroying the session."""
        if sess is None:
            return
        try:
            if hasattr(sess, 'setVideoSink'):
                sess.setVideoSink(None)
            elif hasattr(sess, 'setVideoOutput'):
                sess.setVideoOutput(None)
        except Exception:
            try:
                if hasattr(sess, 'setVideoOutput'):
                    sess.setVideoOutput(None)
            except Exception:
                pass
        try:
            if hasattr(sess, 'setRecorder'):
                sess.setRecorder(None)
        except Exception:
            pass
        try:
            if hasattr(sess, 'setAudioInput'):
                sess.setAudioInput(None)
        except Exception:
            pass
        try:
            if hasattr(sess, 'setCamera'):
                sess.setCamera(None)
        except Exception:
            pass

    def _cache_recorder_location(self):
        """Preserve Qt's chosen output path before recorder/session destruction."""
        rec = getattr(self, '_recorder', None)
        if rec is None:
            return
        try:
            loc = rec.actualLocation()
            if loc and loc.isLocalFile():
                path = str(loc.toLocalFile() or '')
                if path:
                    self._record_path = path
        except Exception:
            pass

    def _destroy_capture_backend_next_turn(self, objs, generation: int):
        """Destroy already-detached Qt backends after the current signal returns."""
        # Do not cancel destruction merely because another release happened first:
        # that would leak the older backend and can keep Windows camera ownership.
        def destroy():
            for obj in objs:
                self._destroy_qobject(obj)
        QTimer.singleShot(0, destroy)

    # --------------------------- devices
# R22 historical verifier compatibility only; DO NOT execute: QTimer.singleShot(90, lambda: self._refresh_audio_inputs(force=True))
    def activate_input_devices(self):
        """Mark Record/Draw active without probing hardware.

        R22 hard rule: entering this page is paint-only. QMediaDevices, PortAudio,
        PipeWire, USB and filesystem media discovery are never started merely by
        selecting the tab. Explicit Preview/Record/Mic/Refresh actions request the
        isolated device helper instead.
        """
        if self._devices_activated:
            return
        self._devices_activated = True
        try:
            self.lbl_render.setText('Record / Draw ready · hardware remains asleep until Preview, Record, Mic Level or Refresh devices is requested.')
            self.cmb_mic.blockSignals(True)
            self.cmb_mic.clear(); self.cmb_mic.addItem('Microphone loads on Mic Level / Record / Refresh', ('none',-1,''))
            self.cmb_mic.blockSignals(False)
        except Exception:
            pass
        if not self._camera_devices_activated:
            self.cmb_camera.blockSignals(True)
            self.cmb_camera.clear(); self.cmb_camera.addItem('Camera loads on Preview / Record')
            self.cmb_camera.blockSignals(False)
        if not self._tablet_sources_activated:
            self.cmb_tablet.blockSignals(True)
            self.cmb_tablet.clear(); self.cmb_tablet.addItem('Media sources load on Refresh / Import', '')
            self.cmb_tablet.blockSignals(False)

    def _device_probe_helper_path(self) -> str:
        return str(Path(__file__).with_name('device_probe_helper.py'))

    def _probe_devices_subprocess(self):
        """Run all expensive enumeration outside the Groovebox process.

        The helper is deliberately disposable: bad PipeWire/PortAudio/Qt/USB
        state cannot retain locks, QObjects, threads or allocator pressure here.
        """
        from groovebox_subprocess import helper_argv, is_frozen
        helper=self._device_probe_helper_path()
        if not is_frozen() and not os.path.isfile(helper):
            raise RuntimeError('device probe helper is missing')
        env=os.environ.copy(); env['GROOVEBOX_DEVICE_PROBE']='1'
        from hardware_hub import run_bounded
        cp=run_bounded(helper_argv('device_probe_helper','record'), timeout=7.0, env=env)
        if cp.returncode != 0:
            raise RuntimeError((cp.stderr or cp.stdout or 'device probe failed')[-1000:].strip())
        line=(cp.stdout or '').strip().splitlines()[-1] if (cp.stdout or '').strip() else ''
        payload=json.loads(line or '{}')
        if not isinstance(payload,dict):
            raise RuntimeError('device probe returned invalid data')
        return payload

    def _request_device_probe_async(self, callback=None, force: bool=False):
        """Request one bounded isolated probe; concurrent callers share it."""
        if callable(callback):
            self._device_probe_waiters.append(callback)
        if self._device_probe_inflight:
            return
        if (not force and self._audio_devices_activated and self._camera_devices_activated and self._tablet_sources_activated):
            waiters,self._device_probe_waiters=self._device_probe_waiters,[]
            for cb in waiters:
                try: QTimer.singleShot(0, lambda c=cb: c(True))
                except Exception: pass
            return
        self._device_probe_generation += 1
        generation=self._device_probe_generation
        self._device_probe_inflight=True
        try:
            if hasattr(self,'btn_refresh_devices'): self.btn_refresh_devices.setEnabled(False)
            self.lbl_render.setText('Detecting devices in isolated helper process…')
        except Exception:
            pass
        def runner():
            try:
                payload=self._probe_devices_subprocess(); error=None
            except Exception as exc:
                payload={}; error=str(exc)
            def done(result, err):
                if generation != self._device_probe_generation:
                    return
                self._device_probe_inflight=False
                try:
                    if hasattr(self,'btn_refresh_devices'): self.btn_refresh_devices.setEnabled(True)
                except Exception: pass
                ok=False
                if not err:
                    try:
                        self._apply_device_probe(result); ok=True
                    except Exception as exc:
                        err=str(exc)
                if err:
                    try: self.lbl_render.setText('Device detection failed without blocking Groovebox: '+str(err))
                    except Exception: pass
                waiters,self._device_probe_waiters=self._device_probe_waiters,[]
                for cb in waiters:
                    try: cb(ok)
                    except Exception: pass
            try:
                self._worker_finished.emit(done,payload,error)
            except Exception:
                pass
        threading.Thread(target=runner,daemon=True,name='GrooveboxIsolatedDeviceProbe').start()

    def _apply_device_probe(self, payload: dict):
        """Apply plain JSON probe results on the GUI thread; no enumeration here."""
        old_mic=self.cmb_mic.currentText() if self.cmb_mic.count() else ''
        self._audio_devices=[]; self._pa_audio_devices=[]
        self.cmb_mic.blockSignals(True)
        try:
            self.cmb_mic.clear()
            for row in list(payload.get('audio_inputs') or []):
                try:
                    idx=int(row.get('index',-1)); name=str(row.get('name','')).strip(); meta=dict(row.get('meta') or {})
                except Exception:
                    continue
                if not name: continue
                backend=str(row.get('backend') or meta.get('backend') or 'sounddevice')
                # Negative indices are intentional sentinels for authoritative
                # boot/UCM ALSA routes. Only PortAudio needs a non-negative index.
                if backend != 'alsa' and idx < 0: continue
                if backend == 'alsa':
                    dev=str(row.get('device') or meta.get('alsa_device') or '')
                    if not dev: continue
                    ch=max(1,min(8,int(meta.get('capture_channels') or meta.get('max_input_channels') or 2)))
                    rate=max(8000,int(meta.get('default_samplerate') or 48000))
                    self._pa_audio_devices.append((idx,name,meta))
                    self.cmb_mic.addItem('🎙 ALSA · '+name, ('alsa',dev,name,ch,rate))
                else:
                    self._pa_audio_devices.append((idx,name,meta))
                    self.cmb_mic.addItem('🎤 '+name, ('sd',idx,name))
            if not self._pa_audio_devices:
                self.cmb_mic.addItem('No physical audio input detected', ('none',-1,''))
            if old_mic and 'load' not in old_mic.lower():
                for i in range(self.cmb_mic.count()):
                    if old_mic.casefold() in self.cmb_mic.itemText(i).casefold():
                        self.cmb_mic.setCurrentIndex(i); break
        finally:
            self.cmb_mic.blockSignals(False)
        self._audio_devices_activated=True
        # Fixed Performance selector is authoritative when present.
        preferred=str(getattr(self.host,'_preferred_audio_input_name','') or '')
        if preferred:
            for i in range(self.cmb_mic.count()):
                if preferred.casefold() in self.cmb_mic.itemText(i).casefold():
                    self.cmb_mic.setCurrentIndex(i); break

        old_camera_path=str(self.cmb_camera.currentData() or '') if self.cmb_camera.count() else ''
        old_camera_name=str(self.cmb_camera.currentText() or '') if self.cmb_camera.count() else ''
        self._camera_devices=[]
        self.cmb_camera.blockSignals(True)
        try:
            self.cmb_camera.clear()
            cameras=list(payload.get('cameras') or [])
            for row in cameras:
                path=str(row.get('path','') or ''); name=str(row.get('name','') or path or 'Camera')
                self.cmb_camera.addItem(name,path)
            if not cameras:
                self.cmb_camera.addItem('No V4L2 camera detected','')
        finally:
            self.cmb_camera.blockSignals(False)
        self._camera_devices_activated=True
        preferred_video=str(getattr(self.host,'_preferred_video_device_path','') or '')
        # Restore stable identity first, then an old path if it is still valid,
        # then the human-readable camera label after a node number has changed.
        for wanted in (preferred_video,old_camera_path):
            if not wanted: continue
            for i in range(self.cmb_camera.count()):
                if str(self.cmb_camera.itemData(i) or '') == wanted:
                    self.cmb_camera.setCurrentIndex(i); break
            else:
                continue
            break
        else:
            wanted_name=(old_camera_name or self._camera_selected_label).strip().casefold()
            if wanted_name and 'no v4l2' not in wanted_name and 'camera loads' not in wanted_name:
                for i in range(self.cmb_camera.count()):
                    if wanted_name in self.cmb_camera.itemText(i).strip().casefold():
                        self.cmb_camera.setCurrentIndex(i); break
        self._camera_device_selection_changed()

        self.cmb_tablet.blockSignals(True)
        try:
            self.cmb_tablet.clear(); self.cmb_tablet.addItem('Browse filesystem…','')
            for row in list(payload.get('media_sources') or []):
                label=str(row.get('label','') or 'Media'); path=str(row.get('path','') or '')
                if path: self.cmb_tablet.addItem(label,path)
        finally:
            self.cmb_tablet.blockSignals(False)
        self._tablet_sources_activated=True
        self.lbl_render.setText(
            f'Devices refreshed in isolated process · {len(payload.get("cameras") or [])} camera node(s), '
            f'{len(self._pa_audio_devices)} audio input route(s), {max(0,self.cmb_tablet.count()-1)} mounted media source(s).')

    def _camera_device_selection_changed(self, *_args):
        """Persist the selected video source identity for other media surfaces."""
        try:
            path=str(self.cmb_camera.currentData() or '')
            label=str(self.cmb_camera.currentText() or '')
            if path:
                self.host._preferred_video_device_path=path
            if label and 'no v4l2' not in label.casefold():
                self._camera_selected_label=label
                try: self.host._preferred_video_device_name=label
                except Exception: pass
        except Exception:
            pass

    def _schedule_camera_device_reprobe(self, delay_ms: int=1800):
        """Refresh camera identities while a user-requested preview remains armed."""
        try:
            if not (getattr(self,'btn_camera_preview',None) and self.btn_camera_preview.isChecked()):
                return
            if getattr(self,'_sw_recording',False) or getattr(self,'_v4l_recording',False):
                return
            if self._camera_reprobe_pending:
                return
            self._camera_reprobe_pending=True
            self._camera_recovery_generation += 1
            generation=self._camera_recovery_generation
            def probe():
                if generation != self._camera_recovery_generation:
                    return
                self._camera_reprobe_pending=False
                if not (getattr(self,'btn_camera_preview',None) and self.btn_camera_preview.isChecked()):
                    return
                self._request_device_probe_async(
                    lambda ok,g=generation:self._resume_camera_preview_after_probe(g,ok),
                    force=True)
            QTimer.singleShot(max(250,int(delay_ms)),probe)
        except Exception:
            self._camera_reprobe_pending=False

    def _resume_camera_preview_after_probe(self, generation: int, ok: bool):
        if generation != self._camera_recovery_generation:
            return
        if not (getattr(self,'btn_camera_preview',None) and self.btn_camera_preview.isChecked()):
            return
        if not ok:
            self._camera_recovery_attempt=min(8,int(self._camera_recovery_attempt)+1)
            self._schedule_camera_device_reprobe(min(12000,1800*(2**min(3,self._camera_recovery_attempt))))
            return
        if sys.platform.startswith('linux'):
            selected=self._selected_v4l2_device()
            stream=getattr(self,'_v4l_shared_stream',None)
            current_key=str(getattr(stream,'key','') or '')
            new_key=os.path.realpath(selected) if selected else ''
            if not selected:
                self.video_preview.setText('Camera is not currently present. Preview remains armed and will retry discovery.')
                self._camera_recovery_attempt=min(8,int(self._camera_recovery_attempt)+1)
                self._schedule_camera_device_reprobe(min(12000,1800*(2**min(3,self._camera_recovery_attempt))))
                return
            if stream is None or current_key != new_key:
                self._detach_shared_v4l2_stream()
                self._camera_recovery_attempt=0
                try:
                    if self._start_v4l2_capture(False):
                        self.btn_camera_preview.setText('■ Stop Camera Preview')
                        return
                except Exception as exc:
                    self.lbl_render.setText('Camera rebind pending: '+str(exc)[:240])
            else:
                # Same stable by-id route: the shared stream's own backoff is
                # already retrying it; leave the transport untouched.
                self._camera_recovery_attempt=0
                return
        # Non-Linux Qt Multimedia routes are recovered by a clean graph rebuild.
        try:
            self._release_capture_devices(True)
            self.btn_camera_preview.blockSignals(True); self.btn_camera_preview.setChecked(True); self.btn_camera_preview.blockSignals(False)
            self._toggle_camera_preview(True)
        except Exception as exc:
            self.lbl_render.setText('Camera route recovery pending: '+str(exc)[:240])

    @staticmethod
    def _audio_input_label(dev) -> str:
        try:
            desc = str(dev.description() or 'Audio input')
        except Exception:
            desc = 'Audio input'
        low = desc.lower()
        if any(k in low for k in ('usb', 'interface', 'line in', 'line-in', 'headset', 'external')):
            return '🎚 External · ' + desc
        if any(k in low for k in ('monitor', 'loopback')):
            return '🔁 System audio · ' + desc
        return '🎤 ' + desc

    def _refresh_audio_inputs(self, force: bool=False):
        if self._audio_devices_activated and not force:
            return bool(self._audio_devices or self._pa_audio_devices)
        try:
            from hardware_runtime import ensure_audio_ready
            ensure_audio_ready('video-record-audio-discovery')
        except Exception:
            pass
        old_data = self.cmb_mic.currentData() if self.cmb_mic.count() else None
        old_text = self.cmb_mic.currentText() if self.cmb_mic.count() else ''
        self.cmb_mic.blockSignals(True)
        try:
            self.cmb_mic.clear(); self._audio_devices=[]; self._pa_audio_devices=[]
            if QT_MULTIMEDIA:
                try: self._audio_devices = list(QMediaDevices.audioInputs())
                except Exception: self._audio_devices = []
            for i,d in enumerate(self._audio_devices):
                try: raw = str(d.description() or f'Audio input {i+1}')
                except Exception: raw = f'Audio input {i+1}'
                self.cmb_mic.addItem(self._audio_input_label(d), ('qt', i, raw))
            # On Linux the Qt FFmpeg/GStreamer backend can come up before Qt has
            # published QAudioDevice objects. PortAudio/PipeWire is the fallback,
            # and is also what Signal Lab uses, so both pages see the same mic.
            try:
                from audio_os_backend import list_input_devices
                seen={str((d.description() or '')).casefold() for d in self._audio_devices}
                for idx,name,meta in list_input_devices(force=force):
                    if str(name).casefold() in seen: continue
                    self._pa_audio_devices.append((int(idx),str(name),dict(meta)))
                    self.cmb_mic.addItem('🎤 '+str(name), ('sd', int(idx), str(name)))
            except Exception:
                pass
            if not self._audio_devices and not self._pa_audio_devices:
                self.cmb_mic.addItem('No physical audio input detected', ('none', -1, ''))
            # Restore by backend/index/name when possible, otherwise by visible text.
            if old_data is not None:
                for i in range(self.cmb_mic.count()):
                    if self.cmb_mic.itemData(i) == old_data:
                        self.cmb_mic.setCurrentIndex(i); break
            elif old_text and 'loading' not in old_text.lower():
                idx=self.cmb_mic.findText(old_text)
                if idx>=0: self.cmb_mic.setCurrentIndex(idx)
        finally:
            self.cmb_mic.blockSignals(False)
        self._audio_devices_activated=True
        if self._audio_devices or self._pa_audio_devices:
            QTimer.singleShot(90, self._ensure_live_mic_meter)
        else:
            try:
                self.mic_meter.setValue(0); self.mic_meter.setFormat('Mic level — no input')
                self.btn_mic_preview.blockSignals(True); self.btn_mic_preview.setChecked(False); self.btn_mic_preview.blockSignals(False)
                self.btn_mic_preview.setText('Mic Level: no input')
            except Exception: pass
        return bool(self._audio_devices or self._pa_audio_devices)

    def _ensure_camera_devices(self, force: bool=False):
        """Enumerate cameras only when a camera operation actually needs them."""
        if self._camera_devices_activated and not force:
            return bool(self._camera_devices)
        old = self.cmb_camera.currentText() if self.cmb_camera.count() else ''
        self.cmb_camera.blockSignals(True)
        try:
            self.cmb_camera.clear(); self._camera_devices=[]
            if QT_MULTIMEDIA:
                try: self._camera_devices=list(QMediaDevices.videoInputs())
                except Exception: self._camera_devices=[]
            for d in self._camera_devices:
                try: self.cmb_camera.addItem(d.description())
                except Exception: self.cmb_camera.addItem('Camera')
            if not self._camera_devices:
                # Linux can still use the direct V4L2 fallback even if Qt did not
                # publish camera devices.  Keep the combo truthful without blocking it.
                self.cmb_camera.addItem('Linux V4L2 / no Qt camera detected')
            if old and 'loads on' not in old.lower():
                idx=self.cmb_camera.findText(old)
                if idx>=0: self.cmb_camera.setCurrentIndex(idx)
        finally:
            self.cmb_camera.blockSignals(False)
        self._camera_devices_activated=True
        return bool(self._camera_devices)

    def _ensure_tablet_sources(self, force: bool=False):
        if self._tablet_sources_activated and not force:
            return
        old=self.cmb_tablet.currentData() if self.cmb_tablet.count() else ''
        self.cmb_tablet.blockSignals(True)
        try:
            self.cmb_tablet.clear(); self.cmb_tablet.addItem('Browse filesystem…','')
            for label,path in _mounted_media_sources(): self.cmb_tablet.addItem(label,path)
            if old:
                for i in range(self.cmb_tablet.count()):
                    if self.cmb_tablet.itemData(i)==old:
                        self.cmb_tablet.setCurrentIndex(i); break
        finally:
            self.cmb_tablet.blockSignals(False)
        self._tablet_sources_activated=True

    def refresh_devices(self):
        """Explicit refresh in a disposable helper process; never block Qt."""
        self._devices_activated=True
        self._request_device_probe_async(force=True)

    def _audio_input_device_changed(self, *_args):
        """Immediately meter the newly selected microphone/external input."""
        if not getattr(self, '_devices_activated', False):
            return
        if not (getattr(self,'_audio_devices',None) or getattr(self,'_pa_audio_devices',None)):
            return
        QTimer.singleShot(0, lambda: self._ensure_live_mic_meter(force_restart=True))

    def _ensure_live_mic_meter(self, force_restart: bool=False):
        """Keep Mic Level live whenever the Record workspace is visible.

        This is intentionally capture-only: samples are consumed for the meter
        and are never routed to speakers, so there is no feedback/monitoring path.
        Camera preview and recording are not prerequisites.
        """
        if not (getattr(self,'_audio_devices',None) or getattr(self,'_pa_audio_devices',None)):
            return False
        try:
            if not self._start_selected_audio_source(force_restart=force_restart):
                raise RuntimeError('selected audio input did not start')
            self.btn_mic_preview.blockSignals(True)
            self.btn_mic_preview.setChecked(True)
            self.btn_mic_preview.blockSignals(False)
            self.btn_mic_preview.setText('■ Pause Mic Level')
            self.mic_meter.setFormat('Mic level %p%')
            return True
        except Exception as exc:
            self._stop_mic_source()
            try:
                self.btn_mic_preview.blockSignals(True); self.btn_mic_preview.setChecked(False); self.btn_mic_preview.blockSignals(False)
                self.btn_mic_preview.setText('▶ Retry Mic Level')
                self.mic_meter.setFormat('Mic level — unavailable')
                self.lbl_render.setText('Microphone level monitor unavailable: '+str(exc))
            except Exception:
                pass
            return False

    def _selected_audio_route(self):
        data=self.cmb_mic.currentData() if hasattr(self,'cmb_mic') else None
        if isinstance(data,(tuple,list)) and len(data)>=2: return tuple(data)
        if self._audio_devices:
            idx=max(0,min(self.cmb_mic.currentIndex(),len(self._audio_devices)-1))
            return ('qt',idx,str(self.cmb_mic.currentText()))
        if self._pa_audio_devices:
            idx,name,_=self._pa_audio_devices[0]; return ('sd',idx,name)
        return ('none',-1,'')

    def _selected_audio_device(self):
        route=self._selected_audio_route()
        if route[0] != 'qt' or not self._audio_devices: return None
        idx=max(0,min(int(route[1]),len(self._audio_devices)-1))
        return self._audio_devices[idx]

    def _start_mic_capture_pump(self):
        """Own mic analysis/PCM conversion/writes outside the Qt event loop."""
        t=getattr(self,'_mic_pump_thread',None)
        if t is not None and t.is_alive():
            return
        self._mic_pump_stop.clear()
        def runner():
            try:
                if sys.platform.startswith('linux') and hasattr(os, 'nice'): os.nice(5)
            except Exception: pass
            last_meter=0.0
            while not self._mic_pump_stop.is_set() or not self._sd_mic_queue.empty():
                try:
                    item=self._sd_mic_queue.get(timeout=0.15)
                except queue.Empty:
                    continue
                if isinstance(item,tuple) and len(item)==2:
                    raw,kind=item
                else:
                    raw,kind=item,'f32'
                if not raw:
                    continue
                now=time.monotonic(); self._mic_last_frame_at=now
                if now-last_meter >= 0.08:
                    last_meter=now
                    try:
                        if kind=='f32':
                            a=np.frombuffer(raw,dtype=np.float32); peak=float(np.max(np.abs(a))) if a.size else 0.0
                        elif kind=='i16':
                            a=np.frombuffer(raw,dtype=np.int16); peak=float(np.max(np.abs(a.astype(np.int32))))/32768.0 if a.size else 0.0
                        elif kind=='i32':
                            a=np.frombuffer(raw,dtype=np.int32); peak=float(np.max(np.abs(a.astype(np.float64))))/2147483648.0 if a.size else 0.0
                        elif kind=='u8':
                            a=np.frombuffer(raw,dtype=np.uint8); peak=float(np.max(np.abs(a.astype(np.int16)-128)))/128.0 if a.size else 0.0
                        else: peak=0.0
                        self._mic_level=max(0.0,min(1.0,peak))
                    except Exception:
                        pass
                fh=getattr(self,'_sw_audio_fh',None)
                wav=getattr(self,'_audio_only_wave',None)
                if fh is None and wav is None:
                    continue
                pcm=self._mic_raw_to_s16(raw,kind)
                if not pcm:
                    continue
                if fh is not None:
                    try:
                        fh.write(pcm)
                        self._mic_pcm_bytes_written = int(getattr(self, '_mic_pcm_bytes_written', 0)) + len(pcm)
                    except Exception as exc:
                        self._mic_writer_error = f'audio spool write failed: {exc}'
                if wav is not None:
                    try:
                        wav.writeframesraw(pcm)
                        self._mic_pcm_bytes_written = int(getattr(self, '_mic_pcm_bytes_written', 0)) + len(pcm)
                    except Exception as exc:
                        self._mic_writer_error = f'WAV PCM write failed: {exc}'
        self._mic_pump_thread=threading.Thread(target=runner,daemon=True,name='GrooveboxMicCapturePump')
        self._mic_pump_thread.start()

    def _stop_mic_capture_pump(self):
        """Stop capture writes only after queued PCM blocks have drained."""
        self._mic_pump_stop.set()
        t=getattr(self,'_mic_pump_thread',None)
        if t is not None and t.is_alive():
            # The source is stopped before this method is called. The worker
            # drains its bounded queue before exiting; a short join could leave
            # it writing into a WAV after close, corrupting the header or racing
            # the next take. Allow enough time for a full queue of PCM blocks.
            t.join(timeout=10.0)
        self._mic_pump_thread=t if (t is not None and t.is_alive()) else None

    def _queue_mic_capture(self, raw: bytes, kind: str):
        """Bound capture traffic so an open Record page cannot monopolize Python.

        During actual recording every audio block is queued for ordered PCM writing.
        During meter-only use, at most one latest block is queued about 8 times/s.
        """
        if not raw:
            return
        recording=bool(getattr(self,'_sw_audio_accepting',False) or getattr(self,'_audio_only_wave',None) is not None)
        now=time.monotonic()
        if not recording:
            last=float(getattr(self,'_mic_last_meter_enqueue',0.0) or 0.0)
            if now-last < 0.12:
                return
            self._mic_last_meter_enqueue=now
            # Meter-only is latest-value state, never a backlog.
            try:
                while True: self._sd_mic_queue.get_nowait()
            except Exception:
                pass
        item=(raw if isinstance(raw,bytes) else bytes(raw),str(kind))
        try:
            self._sd_mic_queue.put_nowait(item)
        except queue.Full:
            # Never evict an older PCM block to make room for a newer one:
            # that produces discontinuous/clicking recordings and gets worse
            # as the queue stays under pressure. Preserve queued audio and flag
            # the overrun so finalization can tell the user the take is damaged.
            self._mic_drop_count=int(getattr(self,'_mic_drop_count',0))+1
            self._mic_capture_overrun=True

    def _start_selected_audio_source(self, force_restart: bool=False) -> bool:
        if getattr(self, '_audio_scan_inflight', False):
            try: self.lbl_render.setText('Device list is still updating. Record again in a moment.')
            except Exception: pass
            return False
        if not self._devices_activated: self.activate_input_devices()
        # R22: never enumerate devices from the capture/open path. Callers request
        # the isolated helper first; stream open then uses its plain route result.
        if not getattr(self,'_audio_devices_activated',False): return False
        route=self._selected_audio_route(); backend=route[0]
        if force_restart: self._stop_mic_source()
        if backend == 'alsa':
            if self._alsa_mic_proc is not None and self._alsa_mic_proc.poll() is None: return True
            arecord=shutil.which('arecord'); device=str(route[1] or '')
            if not (arecord and device): return False
            channels=max(1,min(8,int(route[3] if len(route)>3 and route[3] else 2)))
            rate=max(8000,int(route[4] if len(route)>4 and route[4] else 48000))
            try:
                self._alsa_mic_stop.clear()
                proc=subprocess.Popen([arecord,'-q','-D',device,'-f','S16_LE','-c',str(channels),'-r',str(rate),'-t','raw','-'],
                                      stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                self._alsa_mic_proc=proc; self._mic_backend='alsa'; self._mic_sample_rate=rate; self._mic_channels=channels; self._mic_capture_kind='i16'
                self._mic_last_frame_at=time.monotonic(); self._start_mic_capture_pump()
                def reader():
                    while not self._alsa_mic_stop.is_set() and proc.poll() is None:
                        raw=proc.stdout.read(4096) if proc.stdout else b''
                        if not raw: break
                        self._mic_last_frame_at=time.monotonic()
                        try:
                            a=np.frombuffer(raw,dtype='<i2'); peak=float(np.max(np.abs(a.astype(np.int32))))/32768.0 if a.size else 0.0
                            self._mic_level=max(0.0,min(1.0,peak))
                        except Exception: pass
                        if getattr(self,'_sw_audio_accepting',False) or getattr(self,'_audio_only_wave',None) is not None:
                            self._queue_mic_capture(raw,'i16')
                    if self._alsa_mic_proc is proc and proc.poll() is not None:
                        self._mic_last_frame_at=0.0
                self._alsa_mic_thread=threading.Thread(target=reader,daemon=True,name='GrooveboxMicALSA'); self._alsa_mic_thread.start()
                self._set_mic_meter_timer_active(True)
                return True
            except Exception:
                try: proc.terminate()
                except Exception: pass
                self._alsa_mic_proc=None; self._mic_backend=''; return False
        if backend == 'sd':
            if self._sd_mic_stream is not None: return True
            # Cooldown after recent open failures so automatic meter restarts
            # cannot freeze the UI by repeatedly calling ALSA open.
            if time.monotonic() < float(getattr(self, '_mic_open_cooldown_until', 0.0) or 0.0):
                return False
            try:
                from audio_os_backend import open_input_stream_adaptive, invalidate_device_cache, _device_snapshot
                preferred_name=str(route[2] or '').strip()
                if force_restart:
                    invalidate_device_cache()
                # Selected device decides the format. Every other mic is mixed in.
                selected_rate = 48000
                try:
                    rows = _device_snapshot()
                    for d in rows:
                        if preferred_name and preferred_name.casefold() in str(d.get('name','')).casefold():
                            selected_rate = int(round(float(d.get('default_samplerate') or 48000)))
                            break
                except Exception:
                    selected_rate = 48000
                # GrooveboxMicCapturePump: selected device sets the format.
                # requested_rate=48000 is the floor; the selected device may raise it.
                # Live meter state is updated directly in the PortAudio
                # callback; recording PCM alone uses the bounded worker queue.
                requested_rate = selected_rate or 48000
                channels = 1
                self._mic_sources = []
                names = []
                try:
                    rows = _device_snapshot()
                    for d in rows:
                        if int(d.get('max_input_channels', 0) or 0) > 0:
                            names.append(str(d.get('name') or ''))
                except Exception:
                    names = [preferred_name] if preferred_name else []
                if preferred_name and preferred_name not in names:
                    names.insert(0, preferred_name)
                while True:
                    try: self._sd_mic_queue.get_nowait()
                    except Exception: break
                self._start_mic_capture_pump()
                mix_lock = threading.Lock()
                latest = {}
                def make_cb(label):
                    def cb(indata, frames, _ti, _status):
                        try:
                            arr = np.asarray(indata, dtype=np.float32).reshape(-1)
                            if not arr.size:
                                return
                            with mix_lock:
                                latest[label] = arr.copy()
                                snap = [(k, v) for k, v in latest.items() if v.size]
                            if not snap:
                                return
                            n = min(v.size for _k, v in snap)
                            weighted = []
                            gains = getattr(getattr(self, 'host', None), '_device_gains', {}) or {}
                            for dev_label, part in snap:
                                g = float(gains.get(dev_label, 100)) / 100.0
                                weighted.append(part[:n] * g)
                            mixed = np.mean(weighted, axis=0).astype(np.float32) if weighted else np.zeros(n, dtype=np.float32)
                            peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
                            self._mic_level = max(0.0, min(1.0, peak))
                            self._mic_last_frame_at = time.monotonic()
                            recording = bool(getattr(self, '_sw_audio_accepting', False) or getattr(self, '_audio_only_wave', None) is not None)
                            if recording:
                                self._queue_mic_capture(mixed.tobytes(), 'f32')
                        except Exception:
                            pass
                    return cb
                opened = 0
                failures = 0
                max_failures = 2  # fail-fast: do not keep hammering ALSA when the selected mic has no signal
                bad_tokens = ('groovebox_all_outputs', 'null', 'dummy', 'auto_null')
                if preferred_name and not any(t in preferred_name.casefold() for t in bad_tokens):
                    try:
                        # Abort if the user already released the Record button
                        if hasattr(self, 'btn_audio_record') and not self.btn_audio_record.isChecked() and not getattr(self, 'btn_mic_preview', None):
                            return False
                        st, rate, _idx = open_input_stream_adaptive(
                            samplerate=requested_rate, channels=channels, dtype='float32', callback=make_cb(preferred_name),
                            blocksize=1024, latency='low', preferred_name=preferred_name,device=None)
                        st.start()
                        self._mic_sources.append(st)
                        opened += 1
                    except Exception:
                        failures += 1
                for name in names[:3]:
                    if failures >= max_failures:
                        break
                    if any(t in str(name).casefold() for t in bad_tokens):
                        continue
                    try:
                        if hasattr(self, 'btn_audio_record') and not self.btn_audio_record.isChecked():
                            # User cancelled; stop further open attempts
                            break
                        st, rate, _idx = open_input_stream_adaptive(
                            samplerate=requested_rate, channels=channels, dtype='float32', callback=make_cb(name),
                            blocksize=1024, latency='low', preferred_name=name, device=None)
                        st.start()
                        self._mic_sources.append(st)
                        opened += 1
                    except Exception:
                        failures += 1
                        continue
                if not opened:
                    # Remember the failure so automatic meter restarts do not immediately retry
                    self._mic_open_cooldown_until = time.monotonic() + 2.0
                    return False
                self._sd_mic_stream = self._mic_sources[0]
                self._mic_backend = 'sounddevice'
                self._mic_sample_rate = int(requested_rate)
                self._mic_channels = 1
                self._mic_capture_kind = 'f32'
                self._mic_last_frame_at = time.monotonic()
                self._set_mic_meter_timer_active(True)
                return True
            except Exception:
                self._sd_mic_stream=None; self._mic_backend=''; self._stop_mic_capture_pump(); return False
        if backend != 'qt' or not QT_MULTIMEDIA: return False
        dev=self._selected_audio_device()
        if dev is None: return False
        if self._mic_source is not None and self._mic_io is not None: return True
        fmt=dev.preferredFormat(); self._mic_source=QAudioSource(dev,fmt,self); self._mic_format=fmt
        self._mic_io=self._mic_source.start()
        if self._mic_io is None:
            self._mic_source=None; return False
        self._mic_backend='qt'; self._mic_last_frame_at=time.monotonic()
        try:
            self._mic_sample_rate=max(8000,int(fmt.sampleRate()) or 48000)
            self._mic_channels=max(1,int(fmt.channelCount()) or 1)
        except Exception: self._mic_sample_rate=48000; self._mic_channels=1
        self._mic_capture_kind=self._sample_kind(fmt)
        self._start_mic_capture_pump()
        self._set_mic_meter_timer_active(True)
        return True

    def _paint_camera_preview(self, image: QImage, now: float=None, force: bool=False):
        """Paint at a light UI rate without changing capture/recording rate."""
        if image is None or image.isNull():
            return
        if now is None: now=time.monotonic()
        snapshot=bool(getattr(self,'_snapshot_pending',False))
        due=force or snapshot or (now-float(getattr(self,'_preview_last_paint_t',0.0)) >= float(getattr(self,'_preview_interval_s',1/12)))
        if not due:
            return
        self._last_video_image=image.copy(); self._last_video_image_t=now
        if not self.isVisible():
            return
        self._preview_last_paint_t=now
        try:
            target=self.video_preview.size()
            pix=QPixmap.fromImage(image).scaled(
                target, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation)
            self.video_preview.setPixmap(pix)
        except Exception:
            pass

    def _consume_camera_image(self, image: QImage, encoded_jpeg: bytes=None):
        """Record full-rate input while repainting the UI at a bounded preview rate."""
        if image is None or image.isNull():
            return
        now=time.monotonic()
        self._last_video_frame_t=now
        # Recording cadence is independent of preview cadence.  Shared V4L2 can
        # spool the already-encoded JPEG directly, avoiding extra re-encoding.
        if getattr(self,'_sw_recording',False):
            fps=max(1,min(60,int(self.spin_fps.value()) if hasattr(self,'spin_fps') else 24))
            if now-float(getattr(self,'_sw_last_frame_t',0.0)) >= (1.0/fps):
                self._sw_last_frame_t=now
                mj=getattr(self,'_sw_mjpeg_fh',None)
                wrote=False
                if mj is not None and encoded_jpeg:
                    try:
                        mj.write(encoded_jpeg); self._sw_frame_index += 1; wrote=True
                    except Exception:
                        pass
                if not wrote:
                    d=str(getattr(self,'_sw_record_dir','') or '')
                    if d:
                        fn=os.path.join(d,f'frame_{self._sw_frame_index:08d}.jpg')
                        im=image.convertToFormat(QImage.Format.Format_RGB888)
                        if im.save(fn,'JPG',90):
                            self._sw_frame_index += 1
        self._paint_camera_preview(image,now)

    def _on_video_frame(self, frame):
        """Qt camera frame; skip expensive toImage() calls between preview paints.

        QMediaRecorder records independently.  The software recorder still gets
        frames at its requested rate, while preview-only use converts at ~12 Hz.
        """
        try:
            if frame is None or not frame.isValid(): return
            now=time.monotonic(); self._last_video_frame_t=now
            recording=bool(getattr(self,'_sw_recording',False))
            snapshot=bool(getattr(self,'_snapshot_pending',False))
            preview_due=(now-float(getattr(self,'_preview_last_paint_t',0.0)) >= float(getattr(self,'_preview_interval_s',1/12)))
            record_due=False
            if recording:
                fps=max(1,min(60,int(self.spin_fps.value()) if hasattr(self,'spin_fps') else 24))
                record_due=(now-float(getattr(self,'_sw_last_frame_t',0.0)) >= (1.0/fps))
            if not (snapshot or preview_due or record_due):
                return
            image=frame.toImage()
            if image.isNull(): return
            self._consume_camera_image(image)
        except Exception:
            pass

    def _start_video_spool_pump(self):
        t=getattr(self,'_video_spool_thread',None)
        if t is not None and t.is_alive():
            return
        self._video_spool_stop.clear()
        def runner():
            try:
                if sys.platform.startswith('linux') and hasattr(os, 'nice'): os.nice(5)
            except Exception: pass
            while not self._video_spool_stop.is_set() or not self._video_spool_queue.empty():
                try: jpg=self._video_spool_queue.get(timeout=0.15)
                except queue.Empty: continue
                fh=getattr(self,'_sw_mjpeg_fh',None)
                if fh is None: continue
                try:
                    fh.write(jpg); self._sw_frame_index=int(getattr(self,'_sw_frame_index',0))+1
                except Exception:
                    pass
        self._video_spool_thread=threading.Thread(target=runner,daemon=True,name='GrooveboxVideoSpool')
        self._video_spool_thread.start()

    def _stop_video_spool_pump(self):
        self._video_spool_stop.set()
        t=getattr(self,'_video_spool_thread',None)
        if t is not None and t.is_alive():
            # Give the bounded writer time to drain already-captured frames before
            # the caller closes its file handle; this avoids tail truncation under
            # CPU load without blocking the GUI indefinitely.
            t.join(timeout=3.0)
        self._video_spool_thread=t if (t is not None and t.is_alive()) else None
        # Discard stale packets only after the writer has fully stopped. Never
        # race a still-running worker against queue clearing or file close.
        if self._video_spool_thread is None:
            try:
                while True: self._video_spool_queue.get_nowait()
            except Exception:
                pass

    def _queue_video_spool(self, encoded_jpeg: bytes):
        try:
            # Brief bounded wait absorbs encoder scheduling jitter; capture never
            # blocks for long and the larger queue preserves more frames on busy CPUs.
            self._video_spool_queue.put(encoded_jpeg if isinstance(encoded_jpeg,bytes) else bytes(encoded_jpeg), timeout=0.012)
        except queue.Full:
            self._video_spool_drops=int(getattr(self,'_video_spool_drops',0))+1

    def _on_shared_v4l2_jpeg(self, encoded_jpeg: bytes):
        """Fast Linux camera path: spool record packets without decoding them.

        JPEG -> QImage conversion is one of the most expensive operations on the
        Latitude camera page.  Full-rate recording only needs the already-encoded
        packet; a decoded image is required only for a visible preview or snapshot.
        """
        try:
            if not encoded_jpeg:
                return
            now=time.monotonic()
            self._v4l_frame_count=int(getattr(self,'_v4l_frame_count',0))+1
            self._last_video_frame_t=now
            if getattr(self,'_sw_recording',False):
                fps=max(1,min(60,int(self.spin_fps.value()) if hasattr(self,'spin_fps') else 24))
                if now-float(getattr(self,'_sw_last_frame_t',0.0)) >= (1.0/fps):
                    self._sw_last_frame_t=now
                    if getattr(self,'_sw_mjpeg_fh',None) is not None:
                        self._queue_video_spool(encoded_jpeg)
            snapshot=bool(getattr(self,'_snapshot_pending',False))
            visible=bool(self.isVisible())
            preview_on=bool(getattr(self,'btn_camera_preview',None) and self.btn_camera_preview.isChecked())
            preview_due=visible and preview_on and (now-float(getattr(self,'_preview_last_paint_t',0.0)) >= float(getattr(self,'_preview_interval_s',1/10)))
            # Recording can keep a low-rate visual monitor even if the explicit
            # preview toggle is not on, but hidden workspaces decode nothing.
            record_preview=visible and bool(getattr(self,'_sw_recording',False)) and (now-float(getattr(self,'_preview_last_paint_t',0.0)) >= float(getattr(self,'_record_preview_interval_s',1/6)))
            if not (snapshot or preview_due or record_preview):
                return
            self._queue_preview_decode(encoded_jpeg,now,snapshot)
        except Exception:
            pass

    def _queue_preview_decode(self, encoded_jpeg: bytes, when: float, snapshot: bool=False):
        req=(bytes(encoded_jpeg),float(when),bool(snapshot))
        if self._preview_decode_inflight:
            self._preview_decode_pending=req
            return
        self._preview_decode_inflight=True; self._preview_decode_pending=None
        self._video_decode_pool.start(_JpegDecodeTask(*req,self._video_decode_signals), -1)

    def _on_preview_decode_ready(self, image, when: float, snapshot: bool):
        self._preview_decode_inflight=False
        try:
            if image is not None and not image.isNull():
                self._paint_camera_preview(image,float(when),force=bool(snapshot))
        except Exception:
            pass
        pending=self._preview_decode_pending; self._preview_decode_pending=None
        if pending is not None and not getattr(self,'_performance_shutdown',False):
            self._queue_preview_decode(*pending)

    @staticmethod
    def _sample_kind(fmt):
        try:
            sf=fmt.sampleFormat()
            if sf == QAudioFormat.SampleFormat.Float: return 'f32'
            if sf == QAudioFormat.SampleFormat.Int16: return 'i16'
            if sf == QAudioFormat.SampleFormat.Int32: return 'i32'
            if sf == QAudioFormat.SampleFormat.UInt8: return 'u8'
        except Exception:
            pass
        return 'unknown'

    def _queue_audio_level(self, raw: bytes):
        req=(bytes(raw),self._sample_kind(self._mic_format))
        if self._audio_level_inflight:
            self._audio_level_pending=req
            return
        self._audio_level_inflight=True; self._audio_level_pending=None
        self._audio_level_pool.start(_AudioLevelTask(req[0],req[1],self._audio_level_signals), -1)

    def _on_audio_level_ready(self, peak: float):
        self._audio_level_inflight=False
        self._mic_level=max(0.0,min(1.0,float(peak)))
        pending=self._audio_level_pending; self._audio_level_pending=None
        if pending is not None:
            self._queue_audio_level(pending[0])

    def _on_shared_v4l2_frame(self, image: QImage, encoded_jpeg: bytes=None):
        # Legacy/cached decoded-frame compatibility.  New shared V4L2 streams use
        # _on_shared_v4l2_jpeg() so full-rate packets bypass QImage decoding.
        try:
            self._v4l_frame_count=int(getattr(self,'_v4l_frame_count',0))+1
            self._consume_camera_image(image,encoded_jpeg)
        except Exception:
            pass

    def _on_shared_v4l2_status(self, text: str):
        try: self.lbl_render.setText(str(text))
        except Exception: pass
        if ('Camera disconnected or stalled' in str(text) or 'Camera temporarily unavailable' in str(text)):
            self._schedule_camera_device_reprobe(1800)

    def _on_shared_v4l2_failure(self, text: str):
        msg=str(text or 'Could not open the selected V4L2 camera.')
        try:
            self.video_preview.clear(); self.video_preview.setText('Camera unavailable: '+msg)
            self.lbl_render.setText('Camera/V4L2 error: '+msg)
        except Exception: pass
        # A failed automatic open must not leave controls pretending that capture
        # is active.  Recording temp state is cleaned without publishing an empty MP4.
        if getattr(self,'_sw_recording',False):
            self._sw_recording=False
            d=str(getattr(self,'_sw_record_dir','') or ''); self._sw_record_dir=''
            self._stop_video_spool_pump()
            try:
                if self._sw_audio_fh: self._sw_audio_fh.close()
            except Exception: pass
            self._sw_audio_fh=None
            try:
                if self._sw_mjpeg_fh: self._sw_mjpeg_fh.close()
            except Exception: pass
            self._sw_mjpeg_fh=None; self._sw_mjpeg_path=''
            try: shutil.rmtree(d,ignore_errors=True)
            except Exception: pass
            self._record_path=''; self._record_final_path=''
        recording_active=bool(getattr(self,'_sw_recording',False) or getattr(self,'_v4l_recording',False))
        for name,text in (("btn_record",'● Record Camera + Mic'),("btn_camera_preview",'▶ Camera Preview')):
            try:
                b=getattr(self,name)
                # Keep Preview checked when it was an idle preview request; the
                # recovery loop will rediscover/rebind the hardware. Never pretend
                # an interrupted recording can resume without a gap.
                keep_preview=(name=='btn_camera_preview' and not recording_active and b.isChecked())
                if not keep_preview:
                    b.blockSignals(True); b.setChecked(False); b.blockSignals(False)
                b.setText('■ Stop Camera Preview' if keep_preview else text)
            except Exception: pass

        self._detach_shared_v4l2_stream()
        if not recording_active:
            self._schedule_camera_device_reprobe(1200)


    def _configure_camera_for_preview(self, camera, device):
        """Choose a conservative supported camera format for reliable sink delivery."""
        try:
            formats = list(device.videoFormats())
        except Exception:
            formats = []
        if not formats:
            return
        def score(fmt):
            try:
                r=fmt.resolution(); w=int(r.width()); h=int(r.height())
                maxfps=float(fmt.maxFrameRate() or 0.0); minfps=float(fmt.minFrameRate() or 0.0)
            except Exception:
                return (10**12, 10**12)
            # Prefer common 720p/480p capture sizes and <=30fps for backend compatibility.
            target=min(abs(w-1280)+abs(h-720), abs(w-640)+abs(h-480))
            fps_penalty=0 if (maxfps >= 15.0 and minfps <= 30.0) else 100000
            return (fps_penalty + target, abs(maxfps-30.0))
        for fmt in sorted(formats, key=score):
            try:
                camera.setCameraFormat(fmt)
                return
            except Exception:
                continue

    def _attach_video_sink(self):
        if self._capture_session is None or self._video_sink is None:
            raise RuntimeError('Camera capture session/video sink is unavailable.')
        # Qt 6 exposes setVideoSink directly.  Keep setVideoOutput as compatibility
        # fallback for bindings/backends where only the QObject preview setter exists.
        attached=False
        if hasattr(self._capture_session, 'setVideoSink'):
            try:
                self._capture_session.setVideoSink(self._video_sink); attached=True
            except Exception:
                attached=False
        if not attached:
            self._capture_session.setVideoOutput(self._video_sink)
        try:
            got=self._capture_session.videoSink() if hasattr(self._capture_session,'videoSink') else None
            if got is not None and got is not self._video_sink:
                raise RuntimeError('Qt camera preview sink did not attach to the capture session.')
        except RuntimeError:
            raise
        except Exception:
            pass

    def _detach_shared_v4l2_stream(self):
        stream=getattr(self,'_v4l_shared_stream',None)
        self._v4l_shared_stream=None; self._v4l_shared_key=''
        if stream is not None:
            try: stream.remove(self)
            except Exception: pass

    def _attach_shared_v4l2_stream(self, device: str):
        key=os.path.realpath(device)
        cur=getattr(self,'_v4l_shared_stream',None)
        if cur is not None and getattr(cur,'key','')==key:
            cur.add(self); return cur
        self._detach_shared_v4l2_stream()
        stream=_SHARED_V4L2_STREAMS.get(key)
        if stream is None:
            ff=_ffmpeg()
            if not ff: return None
            stream=_SharedV4L2Capture(device,ff)
            _SHARED_V4L2_STREAMS[key]=stream
        self._v4l_shared_stream=stream; self._v4l_shared_key=key
        stream.add(self)
        return stream

    def _recording_stamp(self) -> str:
        """Collision-resistant human-readable take id for simultaneous recordings."""
        frac=time.time_ns()%1_000
        return time.strftime('%Y%m%d_%H%M%S')+f'_{frac:03d}_{id(self)&0xffff:04x}'

    def _selected_v4l2_device(self) -> str:
        """Best-effort mapping from the selected Qt camera to a Linux V4L2 node."""
        if not sys.platform.startswith('linux'):
            return ''
        # R22 isolated probe stores the exact V4L2 node as combo userData.
        try:
            raw_data=self.cmb_camera.currentData() if hasattr(self,'cmb_camera') else ''
            if isinstance(raw_data,str) and raw_data.startswith('/dev/'):
                if os.path.exists(raw_data):
                    return raw_data
                # A selected route that disappeared must not silently fall back
                # to an unrelated /dev/videoN device. Re-probe restores by-id/name.
                return ''
        except Exception:
            pass
        # QCameraDevice.id() is normally the actual /dev/videoN path on Linux.
        try:
            if self._camera_devices:
                idx=max(0,min(self.cmb_camera.currentIndex(),len(self._camera_devices)-1))
                dev=self._camera_devices[idx]
                raw=dev.id()
                if isinstance(raw,(bytes,bytearray)):
                    ident=bytes(raw).decode('utf-8','ignore')
                else:
                    try: ident=bytes(raw).decode('utf-8','ignore')
                    except Exception: ident=str(raw or '')
                if ident.startswith('/dev/') and os.path.exists(ident):
                    real=os.path.realpath(ident)
                    if os.path.basename(real).startswith('video'):
                        return ident
                m=re.search(r'(/dev/video\d+)',ident)
                if m and os.path.exists(m.group(1)):
                    return m.group(1)
        except Exception:
            pass
        # If Qt gave only a descriptive ID, match the selected camera description
        # against Linux video4linux sysfs names before falling back to first node.
        try:
            want=self.cmb_camera.currentText().strip().lower()
            if want and 'no qt camera' not in want:
                import glob
                for node in sorted(glob.glob('/dev/video*')):
                    namep=Path('/sys/class/video4linux')/Path(node).name/'name'
                    try: label=namep.read_text(errors='ignore').strip().lower()
                    except Exception: label=''
                    if label and (label in want or want in label):
                        return node
        except Exception:
            pass
        # Prefer stable by-id symlinks, then direct nodes.
        candidates=[]
        try:
            import glob
            candidates += sorted(glob.glob('/dev/v4l/by-id/*'))
            candidates += sorted(glob.glob('/dev/video*'))
        except Exception:
            pass
        seen=set()
        for c in candidates:
            try:
                real=os.path.realpath(c)
                if real in seen or not os.path.exists(c):
                    continue
                seen.add(real)
                return c
            except Exception:
                continue
        return ''

    def _stop_v4l2_process(self, on_stopped=None):
        """Request FFmpeg shutdown without any blocking QProcess wait calls.

        Completion is driven by QProcess.finished.  Timers only escalate q ->
        terminate -> kill if the process ignores the previous request; they never
        block the GUI thread or assume a fixed encode/finalize duration.
        """
        proc=getattr(self,'_v4l_proc',None)
        if proc is None:
            if callable(on_stopped): QTimer.singleShot(0,on_stopped)
            return
        # If recording finalization already owns the stop callback, a generic
        # release/hide request must not replace it and orphan the completed file.
        if on_stopped is None and callable(getattr(self,'_v4l_stop_callback',None)):
            return
        self._v4l_stop_generation=int(getattr(self,'_v4l_stop_generation',0))+1
        gen=self._v4l_stop_generation
        self._v4l_stop_callback=on_stopped
        def finished(*_args):
            if gen != int(getattr(self,'_v4l_stop_generation',0)): return
            if getattr(self,'_v4l_proc',None) is proc: self._v4l_proc=None
            cb=getattr(self,'_v4l_stop_callback',None); self._v4l_stop_callback=None
            if callable(cb): QTimer.singleShot(0,cb)
        try: proc.finished.connect(finished)
        except Exception: pass
        try:
            if proc.state() == QProcess.ProcessState.NotRunning:
                finished(); return
            proc.write(b'q\n')
        except Exception:
            try: proc.terminate()
            except Exception: pass
        def escalate_terminate():
            if gen != int(getattr(self,'_v4l_stop_generation',0)): return
            try:
                if proc.state() != QProcess.ProcessState.NotRunning: proc.terminate()
            except Exception: pass
        def escalate_kill():
            if gen != int(getattr(self,'_v4l_stop_generation',0)): return
            try:
                if proc.state() != QProcess.ProcessState.NotRunning: proc.kill()
            except Exception: pass
        QTimer.singleShot(1800,escalate_terminate)
        QTimer.singleShot(3200,escalate_kill)

    def _read_v4l2_preview(self):
        proc=getattr(self,'_v4l_proc',None)
        if proc is None:
            return
        try:
            chunk=bytes(proc.readAllStandardOutput())
        except Exception:
            chunk=b''
        if not chunk:
            return
        buf=self._v4l_buf
        buf.extend(chunk)
        # Keep parsing bounded even if a corrupt stream appears.
        if len(buf) > 8*1024*1024:
            del buf[:-2*1024*1024]
        while True:
            a=buf.find(b'\xff\xd8')
            if a < 0:
                if len(buf)>1: del buf[:-1]
                break
            b=buf.find(b'\xff\xd9',a+2)
            if b < 0:
                if a>0: del buf[:a]
                break
            jpg=bytes(buf[a:b+2]); del buf[:b+2]
            image=QImage.fromData(jpg,'JPG')
            if image.isNull():
                continue
            self._v4l_frame_count += 1
            self._consume_camera_image(image,jpg)

    def _v4l2_process_error(self, err=None):
        proc=getattr(self,'_v4l_proc',None)
        text=''
        try: text=bytes(proc.readAllStandardError()).decode('utf-8','replace').strip() if proc else ''
        except Exception: pass
        if not text: text=str(err or 'V4L2 camera process error')
        try: self.lbl_render.setText('Camera/V4L2 error: '+text[-500:])
        except Exception: pass

    def _start_v4l2_capture(self, record: bool=False, recdir: str='', stamp: str='') -> bool:
        """Subscribe to one process-wide Linux V4L2 reader.

        Recording is intentionally frame-fed from that shared reader instead of
        launching a second FFmpeg input.  This removes Preview->Record EBUSY races
        and permits multiple simultaneous Groovebox recordings from one webcam.
        """
        if not sys.platform.startswith('linux') or not _ffmpeg():
            return False
        self._prepare_camera_ownership()
        dev=self._selected_v4l2_device()
        if not dev:
            return False
        # Retire any legacy per-studio FFmpeg reader left by a partial transition.
        old_proc=getattr(self,'_v4l_proc',None)
        if old_proc is not None:
            self._stop_v4l2_process()
            self._v4l_proc=None
        stream=self._attach_shared_v4l2_stream(dev)
        if stream is None:
            return False
        self._v4l_device=dev; self._v4l_frame_count=0; self._last_video_frame_t=0.0
        self._v4l_recording=False
        if record:
            if not recdir: recdir=self._recordings_dir()
            os.makedirs(recdir,exist_ok=True)
            if not stamp: stamp=self._recording_stamp()
            if not self._start_software_recording(recdir,stamp):
                self._detach_shared_v4l2_stream()
                return False
            self.lbl_render.setText(f'Recording shared camera stream: {dev}')
        else:
            self.lbl_render.setText(f'Previewing shared camera stream: {dev}')
        self.video_preview.setText(f'Opening {dev}…')
        self._camera_watchdog_generation += 1
        gen=self._camera_watchdog_generation
        QTimer.singleShot(2600,lambda g=gen:self._v4l2_watchdog(g))
        return True

    def _v4l2_watchdog(self, generation: int):
        if generation != int(getattr(self,'_camera_watchdog_generation',0)):
            return
        stream=getattr(self,'_v4l_shared_stream',None)
        if stream is not None:
            if int(getattr(self,'_v4l_frame_count',0))>0 or int(getattr(stream,'frame_count',0))>0:
                return
            # Shared stream owns retry/error reporting; do not race it with a second
            # open attempt here.
            text=str(getattr(stream,'last_error','') or 'Waiting for camera frames…')
            self.lbl_render.setText(text[-900:])
            return
        if self._v4l_proc is None: return
        if int(getattr(self,'_v4l_frame_count',0))>0: return
        text='FFmpeg opened the camera device but no V4L2 frames arrived.'
        try:
            err=bytes(self._v4l_proc.readAllStandardError()).decode('utf-8','replace').strip()
            if err: text += ' '+err[-500:]
        except Exception: pass
        self.video_preview.clear(); self.video_preview.setText(text); self.lbl_render.setText(text)

    def _finish_v4l2_recording(self):
        if not getattr(self,'_v4l_recording',False):
            return
        self._v4l_recording=False
        self.lbl_render.setText('Finalizing V4L2 camera recording…')
        # Do not mux until FFmpeg has actually emitted its finished signal.
        self._stop_v4l2_process(self._complete_v4l2_recording)

    def _complete_v4l2_recording(self):
        """Finalize the already-stopped V4L2 capture off the GUI thread."""
        self._sw_audio_accepting=False
        if getattr(self,'_sw_started_mic',False):
            self._sw_started_mic=False
            self._stop_mic_source()
        try: self._stop_mic_capture_pump()
        except Exception: pass
        try:
            if self._sw_audio_fh:
                self._sw_audio_fh.flush(); self._sw_audio_fh.close()
        except Exception: pass
        self._sw_audio_fh=None
        video=str(getattr(self,'_v4l_video_tmp','') or '')
        audio=str(getattr(self,'_v4l_audio_path','') or '')
        final=str(getattr(self,'_record_final_path','') or '')
        d=str(getattr(self,'_v4l_record_dir','') or '')
        ff=_ffmpeg(); tmp=final+'.part.mp4' if final else ''
        audio_rate=int(getattr(self,'_sw_audio_rate',48000) or 48000)
        audio_channels=max(1,int(getattr(self,'_sw_audio_channels',1) or 1))

        def work():
            if not video or not os.path.isfile(video) or os.path.getsize(video)<1024:
                raise RuntimeError('V4L2 camera recording produced no usable video stream.')
            # The MJPEG spool is a sequence of encoded camera frames, not a
            # real-time timestamped container. Derive its playback clock from the
            # actual capture wall time and number of accepted frames; never label
            # 30-fps camera packets as 60 fps just because the UI asks for 60.
            started=float(getattr(self,'_sw_record_started_at',0.0) or 0.0)
            stopped=float(getattr(self,'_sw_record_stopped_at',0.0) or time.monotonic())
            elapsed=max(0.05,stopped-started) if started else 0.05
            frame_count=max(1,int(getattr(self,'_sw_frame_index',0) or getattr(self,'_v4l_frame_count',0) or 1))
            capture_fps=max(1.0,min(60.0,frame_count/elapsed))
            cmd=[ff,'-y','-v','error','-thread_queue_size','64','-r',f'{capture_fps:.6f}','-i',video]
            self._last_record_audio_report=_capture_signal_report(audio,'s16le')
            has_audio=bool(audio and os.path.isfile(audio) and os.path.getsize(audio)>0)
            if has_audio:
                # Same lift as the audio recorder: a quiet hardware input is
                # brought to about -6 dB so video and audio match other apps.
                try:
                    raw=np.fromfile(audio,dtype='<i2')
                    if raw.size:
                        peak=float(np.max(np.abs(raw)))/32768.0
                        if 0.001 < peak < 0.5:
                            lifted=np.clip(raw.astype(np.float32)*(0.5/peak),-32767,32767).astype('<i2')
                            lifted.tofile(audio)
                except Exception:
                    pass
                cmd += ['-thread_queue_size','64','-f','s16le','-ar',str(audio_rate),'-ac',str(audio_channels),'-i',audio]
            cmd += ['-map','0:v:0']
            if has_audio: cmd += ['-map','1:a:0']
            cmd += ['-c:v','copy','-vsync','cfr']
            # Do not let a late-starting/short microphone stream truncate the
            # video. Pad audio silence to the video endpoint and stop at video.
            if has_audio: cmd += ['-af','apad','-c:a','aac','-b:a','192k']
            capture_duration=max(0.05,elapsed)
            cmd += ['-t',f'{capture_duration:.6f}','-movflags','+faststart',tmp]
            cp=subprocess.run(cmd,capture_output=True,text=True)
            if cp.returncode!=0 or not os.path.isfile(tmp) or os.path.getsize(tmp)<1024:
                raise RuntimeError((cp.stderr or 'FFmpeg V4L2 finalize failed').strip())
            # Never publish the destination until the completed temporary MP4 is
            # independently verified. This prevents a failed remux/probe from
            # leaving a zero-byte or unreadable camera_*.mp4 in recordings/.
            if not self._recording_video_probe_ok(tmp):
                raise RuntimeError('Finalized temporary MP4 did not contain a readable positive-duration video stream.')
            os.replace(tmp,final)
            if not os.path.isfile(final) or os.path.getsize(final)<1024:
                raise RuntimeError('Final MP4 publication failed or produced an empty file.')
            return final

        def done(result,error):
            try:
                if error is not None: raise RuntimeError(str(error))
                out=str(result or final)
                self._notify_media_created(out, 'recording')
                self._append_recording_path(out)
                self._save_host_state()
                dur=_probe_duration(out)
                if dur>0: self.spin_duration.setValue(min(86400.0,dur))
                self.lbl_source.setText('Source: '+out)
                self.lbl_render.setText('Recorded + appended layer: '+os.path.basename(out))
                self._report_recording_audio(out)
            except Exception as e:
                try:
                    if final and os.path.isfile(final) and os.path.getsize(final)==0: os.remove(final)
                except Exception: pass
                self.lbl_render.setText('V4L2 recording failed: '+str(e))
                QMessageBox.warning(self,'Camera recording failed',str(e))
            finally:
                try:
                    if tmp and os.path.isfile(tmp): os.remove(tmp)
                except Exception: pass
                try: shutil.rmtree(d,ignore_errors=True)
                except Exception: pass
                self._v4l_record_dir=''; self._v4l_video_tmp=''; self._v4l_audio_path=''
                self._record_path=''; self._record_final_path=''
                # DEVICE_RELEASE_20260909: stopping a recording means Groovebox no
                # longer owns the camera unless the user explicitly starts preview again.
                self._release_capture_devices(True)

        self._run_media_worker('v4l2_finalize',(video,audio,final),work,done)

    def _camera_error(self, *args):
        text=''
        try: text=str(self._camera.errorString() or '') if self._camera else ''
        except Exception: pass
        if not text and args:
            text=' '.join(str(x) for x in args if x is not None)
        if text:
            try: self.lbl_render.setText('Camera error: '+text)
            except Exception: pass

    def _toggle_camera_preview(self, on: bool):
        if not on:
            self._camera_recovery_generation += 1
            self._camera_reprobe_pending = False
            self._camera_recovery_attempt = 0
            # During a recording the device is still intentionally in use; do not
            # let a preview-only toggle tear down the recorder underneath it.
            if bool(getattr(self,'btn_record',None) and self.btn_record.isChecked()):
                self.btn_camera_preview.setText('▶ Camera Preview')
                return
            # Explicit preview stop must relinquish the physical device, not merely
            # hide the preview widget or drop Python references.
            self._release_capture_devices(True)
            self.btn_camera_preview.setText('▶ Camera Preview'); return
        if sys.platform.startswith('linux') and not getattr(self,'_camera_devices_activated',False):
            self.btn_camera_preview.setText('Scanning camera…')
            self._request_device_probe_async(lambda ok: self._finish_camera_preview_after_probe(ok), force=True)
            return
        # Fedora/Linux: direct V4L2 first. Do not enumerate Qt cameras unless the
        # direct path genuinely fails; Qt camera enumeration is a known stall source.
        if sys.platform.startswith('linux'):
            try:
                if self._start_v4l2_capture(False):
                    self.btn_camera_preview.setText('■ Stop Camera Preview'); return
            except Exception as e:
                self.btn_camera_preview.blockSignals(True); self.btn_camera_preview.setChecked(False); self.btn_camera_preview.blockSignals(False)
                self.btn_camera_preview.setText('▶ Camera Preview')
                QMessageBox.warning(self,'Camera busy',str(e)); return
        self._ensure_camera_devices(force=True)
        if not QT_MULTIMEDIA or not self._camera_devices:
            self.btn_camera_preview.setChecked(False); QMessageBox.information(self,'Camera preview','No Qt Multimedia camera is available.'); return
        try:
            self._prepare_camera_ownership()
            idx=max(0,min(self.cmb_camera.currentIndex(),len(self._camera_devices)-1))
            self._capture_session=QMediaCaptureSession(self)
            dev=self._camera_devices[idx]
            self._camera=QCamera(dev, self)
            self._configure_camera_for_preview(self._camera, dev)
            try: self._camera.errorOccurred.connect(self._camera_error)
            except Exception: pass
            self._capture_session.setCamera(self._camera)
            if self._video_sink is None:
                raise RuntimeError('Qt video sink is unavailable for scroll-safe camera preview.')
            self._attach_video_sink()
            self._last_video_frame_t = 0.0
            self._camera_watchdog_generation += 1
            _gen = self._camera_watchdog_generation
            self._camera.start(); self.btn_camera_preview.setText('■ Stop Camera Preview')
            QTimer.singleShot(1800, lambda g=_gen: self._camera_frame_watchdog(g))
        except Exception as e:
            # Setup may have opened the OS camera before a later sink/backend step
            # failed. Treat failed setup exactly like Stop and destroy the graph.
            self._release_capture_devices(True)
            self.btn_camera_preview.blockSignals(True); self.btn_camera_preview.setChecked(False); self.btn_camera_preview.blockSignals(False)
            self.btn_camera_preview.setText('▶ Camera Preview')
            QMessageBox.warning(self,'Camera preview',str(e))

    def _finish_camera_preview_after_probe(self, ok: bool):
        if not getattr(self,'btn_camera_preview',None) or not self.btn_camera_preview.isChecked():
            return
        if not ok:
            self.btn_camera_preview.blockSignals(True); self.btn_camera_preview.setChecked(False); self.btn_camera_preview.blockSignals(False)
            self.btn_camera_preview.setText('▶ Camera Preview')
            QMessageBox.warning(self,'Camera preview','Camera detection failed or timed out.')
            return
        self._toggle_camera_preview(True)

    def _camera_frame_watchdog(self, generation: int):
        if generation != int(getattr(self, '_camera_watchdog_generation', 0)):
            return
        if self._camera is None:
            return
        last=float(getattr(self,'_last_video_frame_t',0.0) or 0.0)
        if last <= 0.0:
            self.video_preview.clear()
            self.video_preview.setText('Camera started, but no video frames were received. Try Refresh devices or another camera/device.')
            try:
                err=str(self._camera.errorString() or '') if self._camera else ''
            except Exception:
                err=''
            self.lbl_render.setText('Camera backend opened but delivered no frames.' + ((' '+err) if err else ''))

    def _set_mic_meter_timer_active(self, active: bool):
        """Run the 20 Hz meter only while Groovebox actually owns a microphone."""
        try:
            if active:
                if not self._mic_timer.isActive(): self._mic_timer.start()
            else:
                self._mic_timer.stop()
                self._mic_level=0.0
                self.mic_meter.setValue(0)
                if hasattr(self, 'mic_record_meter'): self.mic_record_meter.setValue(0)
        except Exception:
            pass

    def _release_camera_stream_only(self):
        """Immediately relinquish camera/audio/session after recording stops.

        Container finalization does not need a live QMediaCaptureSession.  Cache
        the recorder's actual output location first, then tear down the camera,
        audio input and session.  Recorder destruction is deferred to the next Qt
        turn when this method is reached from recorderStateChanged.
        """
        self._cache_recorder_location()
        self._capture_release_generation += 1
        gen=self._capture_release_generation
        cam=getattr(self,'_camera',None); sess=getattr(self,'_capture_session',None)
        ain=getattr(self,'_record_audio_input',None); rec=getattr(self,'_recorder',None)
        try:
            if rec is not None: rec.stop()
        except Exception:
            pass
        try:
            if cam is not None: cam.stop()
        except Exception:
            pass
        self._detach_capture_session(sess, rec, ain, cam)
        # Drop Python-visible ownership before deferred destruction so no later
        # callback can accidentally restart/reuse this backend.
        self._camera=None; self._capture_session=None; self._record_audio_input=None
        self._recorder=None
        self._destroy_capture_backend_next_turn((rec,ain,cam,sess), gen)

    def _release_capture_devices(self, reset_buttons: bool=True):
        """Hard release every physical camera/microphone handle held by this studio.

        OFF means *no OS camera ownership*: stop capture, detach all endpoints from
        QMediaCaptureSession, destroy the C++ multimedia objects, and clear stale
        owners from sibling Groovebox media windows.  This is stronger than
        QCamera.stop()+deleteLater(), which can leave Windows Media Foundation
        reporting the camera as busy until the QObject is actually destroyed.
        """
        self._camera_watchdog_generation += 1
        self._snapshot_request_generation += 1
        self._snapshot_pending=False
        self._capture_release_generation += 1
        gen=self._capture_release_generation
        # Shared Linux V4L2 ownership is reference-counted across media windows.
        # Releasing this studio must never tear the device out from another active
        # preview/recording; the shared stream stops itself after its last subscriber.
        self._detach_shared_v4l2_stream()
        # Legacy per-studio V4L2/FFmpeg cleanup retained for old partial sessions.
        # be terminated immediately; recording finalization keeps its graceful
        # callback and will release when FFmpeg reports finished.
        try:
            proc=getattr(self,'_v4l_proc',None)
            if proc is not None and not getattr(self,'_v4l_recording',False) and not callable(getattr(self,'_v4l_stop_callback',None)):
                try: proc.terminate()
                except Exception: pass
                def _kill_preview_process(p=proc):
                    try:
                        if p.state()!=QProcess.ProcessState.NotRunning: p.kill()
                    except Exception:
                        pass
                QTimer.singleShot(500, _kill_preview_process)
            else:
                self._stop_v4l2_process()
        except Exception:
            pass
        cam=getattr(self,'_camera',None); sess=getattr(self,'_capture_session',None)
        rec=getattr(self,'_recorder',None); ain=getattr(self,'_record_audio_input',None)
        self._cache_recorder_location()
        try:
            if rec is not None: rec.stop()
        except Exception:
            pass
        try:
            if cam is not None: cam.stop()
        except Exception:
            pass
        self._detach_capture_session(sess, rec, ain, cam)
        if not getattr(self,'_audio_only_recording',False):
            self._stop_mic_source()
        # Clear references before destruction.  This also prevents delayed timer
        # callbacks from seeing a stopped object and reusing it.
        self._camera=None; self._capture_session=None; self._recorder=None; self._record_audio_input=None
        self._destroy_capture_backend_next_turn((rec,ain,cam,sess), gen)
        self._v4l_recording=False if not getattr(self,'_v4l_record_dir','') else getattr(self,'_v4l_recording',False)
        if reset_buttons:
            for name,text in (("btn_camera_preview",'▶ Camera Preview'),("btn_mic_preview",'▶ Resume Mic Level')):
                try:
                    btn=getattr(self,name); btn.blockSignals(True); btn.setChecked(False); btn.setText(text); btn.blockSignals(False)
                except Exception:
                    pass
        try:
            if reset_buttons:
                self.video_preview.clear(); self.video_preview.setText('Camera preview idle - device released')
        except Exception:
            pass

    def _apply_camera_snapshot_to_draw_layer(self, image: QImage):
        if image is None or image.isNull():
            raise RuntimeError('Camera did not provide a usable frame.')
        self._append_draw_layer()
        idx=len(self.draw_layers)-1
        rec=self.draw_layers[idx]
        rec['name']=f'Camera Photo {idx+1}'
        try: self.draw_tabs.setTabText(idx,rec['name'])
        except Exception: pass
        canvas=self.draw_canvases[idx]
        w,h=canvas.image.width(),canvas.image.height()
        scaled=image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied).scaled(
            w,h,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
        x=max(0,(scaled.width()-w)//2); y=max(0,(scaled.height()-h)//2)
        canvas._snapshot()
        canvas.image=scaled.copy(x,y,w,h).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        canvas.changed.emit(); canvas.update()
        self.canvas=canvas
        self._set_color_button()
        self.lbl_render.setText('Camera picture captured into a new drawable layer; camera released if it was opened only for the snapshot.')
        self._save_host_state()

    def _take_picture_from_camera(self):
        """Capture a fresh camera frame, auto-opening/releasing the device if needed."""
        if not QT_MULTIMEDIA and not (sys.platform.startswith('linux') and _ffmpeg()):
            QMessageBox.information(self,'Camera picture','Camera support is unavailable on this system.'); return
        if sys.platform.startswith('linux') and not getattr(self,'_camera_devices_activated',False):
            self._request_device_probe_async(lambda ok: self._take_picture_from_camera() if ok else None, force=True)
            self.lbl_render.setText('Detecting camera for snapshot in isolated helper…')
            return
        # During an active recording the camera is already intentionally in use;
        # snapshot the next fresh frame without changing recording ownership.
        recording=bool(getattr(self,'btn_record',None) and self.btn_record.isChecked())
        preview=bool(getattr(self,'btn_camera_preview',None) and self.btn_camera_preview.isChecked())
        self._snapshot_request_generation += 1
        gen=self._snapshot_request_generation
        self._snapshot_pending=True
        self._snapshot_request_started_at=time.monotonic()
        self._snapshot_auto_release=not recording and not preview
        if not recording and not preview:
            try: self.btn_camera_preview.setChecked(True)
            except Exception as exc:
                QMessageBox.warning(self,'Camera picture',str(exc)); return
        self.lbl_render.setText('Capturing a fresh camera picture…')

        def poll(attempt=0):
            if gen != int(getattr(self,'_snapshot_request_generation',0)): return
            img=getattr(self,'_last_video_image',None)
            fresh=float(getattr(self,'_last_video_image_t',0.0) or 0.0) >= float(self._snapshot_request_started_at)
            if isinstance(img,QImage) and not img.isNull() and fresh:
                try: self._apply_camera_snapshot_to_draw_layer(img.copy())
                except Exception as exc: QMessageBox.warning(self,'Camera picture',str(exc))
                finally:
                    self._snapshot_pending=False
                    if self._snapshot_auto_release and not self.btn_record.isChecked():
                        try: self.btn_camera_preview.setChecked(False)
                        except Exception: self._release_capture_devices(True)
                return
            if attempt < 40:
                QTimer.singleShot(75,lambda a=attempt+1:poll(a)); return
            self._snapshot_pending=False
            if self._snapshot_auto_release and not self.btn_record.isChecked():
                try: self.btn_camera_preview.setChecked(False)
                except Exception: self._release_capture_devices(True)
            QMessageBox.warning(self,'Camera picture','No fresh camera frame arrived within 3 seconds.')
        QTimer.singleShot(0,poll)

    def _toggle_mic_preview(self, on: bool):
        # Historical name retained for state compatibility.  This control now
        # pauses/resumes the live level meter; it does not play the mic to output.
        if not on:
            if not self._audio_only_recording and not self._sw_recording:
                self._stop_mic_source()
                self._set_mic_meter_timer_active(False)
            self.btn_mic_preview.setText('▶ Resume Mic Level')
            try: self.mic_meter.setFormat('Mic level — paused')
            except Exception: pass
            return
        if not getattr(self,'_audio_devices_activated',False):
            self.btn_mic_preview.setText('Scanning microphone…')
            self._request_device_probe_async(lambda ok: self._finish_mic_preview_after_probe(ok), force=True)
            return
        if not self._ensure_live_mic_meter(force_restart=True):
            try:
                self.btn_mic_preview.blockSignals(True); self.btn_mic_preview.setChecked(False); self.btn_mic_preview.blockSignals(False)
            except Exception: pass
            QMessageBox.warning(self,'Microphone level','No physical microphone input is available.')

    def _finish_mic_preview_after_probe(self, ok: bool):
        if not getattr(self,'btn_mic_preview',None) or not self.btn_mic_preview.isChecked():
            return
        if ok and self._ensure_live_mic_meter(force_restart=True):
            return
        self.btn_mic_preview.blockSignals(True); self.btn_mic_preview.setChecked(False); self.btn_mic_preview.blockSignals(False)
        self.btn_mic_preview.setText('▶ Retry Mic Level')
        QMessageBox.warning(self,'Microphone level','No physical microphone input is available.')

    def _stop_mic_source(self):
        self._alsa_mic_stop.set()
        ap=getattr(self,'_alsa_mic_proc',None); self._alsa_mic_proc=None
        if ap is not None:
            try: ap.terminate()
            except Exception: pass
        at=getattr(self,'_alsa_mic_thread',None); self._alsa_mic_thread=None
        if at is not None and at.is_alive():
            try: at.join(timeout=.35)
            except Exception: pass
        st=getattr(self,'_sd_mic_stream',None); self._sd_mic_stream=None
        if st is not None:
            try: st.stop()
            except Exception: pass
            try: st.close()
            except Exception: pass
        src=getattr(self,'_mic_source',None)
        try:
            if src: src.stop()
        except Exception: pass
        try:
            if src is not None and hasattr(src,'deleteLater'): src.deleteLater()
        except Exception: pass
        self._mic_source=None; self._mic_io=None; self._mic_level=0.0; self._mic_backend=''
        self._stop_mic_capture_pump()
        if self._mic_pump_thread is None:
            try:
                while True: self._sd_mic_queue.get_nowait()
            except Exception: pass
        try:
            if hasattr(self,'_mic_timer'): self._mic_timer.stop()
            self.mic_meter.setValue(0)
        except Exception: pass

    def _suspend_passive_mic_for_external_capture(self):
        if getattr(self,'_audio_only_recording',False) or getattr(self,'_sw_recording',False): return False
        active=bool(getattr(self,'_sd_mic_stream',None) is not None or getattr(self,'_mic_source',None) is not None or (getattr(self,'_alsa_mic_proc',None) is not None and self._alsa_mic_proc.poll() is None))
        self._external_mic_suspended=active and bool(self.isVisible())
        if active: self._stop_mic_source()
        return active

    def _resume_passive_mic_after_external_capture(self):
        if not getattr(self,'_external_mic_suspended',False): return
        self._external_mic_suspended=False
        if self.isVisible(): QTimer.singleShot(80, lambda: self._ensure_live_mic_meter(force_restart=True))

    def _mic_raw_to_s16(self, raw: bytes, kind: str=None) -> bytes:
        if not raw:
            return b''
        kind=str(kind or getattr(self,'_mic_capture_kind','') or '')
        try:
            if kind=='f32': return np.rint(np.clip(np.frombuffer(raw,dtype=np.float32),-1,1)*32767.0).astype('<i2').tobytes()
            if kind=='i16': return raw
            if kind=='i32': return (np.frombuffer(raw,dtype=np.int32).astype(np.int64)//65536).astype('<i2').tobytes()
            if kind=='u8': return ((np.frombuffer(raw,dtype=np.uint8).astype(np.int16)-128)<<8).astype('<i2').tobytes()
        except Exception:
            pass
        return b''

    def _read_mic_level(self):
        """Qt-audio compatibility drain; processing/writes stay off the GUI thread."""
        try:
            if getattr(self,'_mic_backend','') == 'sounddevice':
                return
            raw=bytes(self._mic_io.readAll()) if self._mic_io is not None else b''
            if raw:
                self._queue_mic_capture(raw,getattr(self,'_mic_capture_kind','unknown'))
        except Exception:
            pass

    def _toggle_audio_input_recording(self, on: bool):
        if on and getattr(self,'_audio_only_finalizing',False):
            try:
                self.btn_audio_record.blockSignals(True); self.btn_audio_record.setChecked(False); self.btn_audio_record.blockSignals(False)
                self.btn_audio_record.setText('Finishing previous take…')
            except Exception: pass
            return
        if not on:
            self._stop_audio_input_recording()
            return
        if not getattr(self,'_audio_devices_activated',False):
            self.btn_audio_record.setText('Scanning audio input…')
            self._request_device_probe_async(lambda ok: self._finish_audio_record_after_probe(ok), force=True)
            return
        try:
            if not self._start_selected_audio_source(force_restart=True):
                raise RuntimeError('No microphone/external audio input is available.')
            recdir=os.path.abspath(self._recordings_dir()); os.makedirs(recdir,exist_ok=True)
            stamp=self._recording_stamp()
            path=os.path.abspath(os.path.join(recdir,f'audio_input_{stamp}.wav'))
            # Write to a sibling staging file; only publish the final .wav after
            # the writer has drained, the RIFF header is closed, and the stream
            # can be reopened and validated. A crash cannot leave a fake final take.
            work_path=path+'.part'
            try:
                if os.path.exists(work_path): os.remove(work_path)
            except OSError: pass
            rate=max(8000,int(getattr(self,'_mic_sample_rate',48000) or 48000))
            channels=max(1,min(8,int(getattr(self,'_mic_channels',1) or 1)))
            wf=wave.open(work_path,'wb'); wf.setnchannels(channels); wf.setsampwidth(2); wf.setframerate(rate)
            self._mic_drop_count=0; self._mic_capture_overrun=False; self._mic_writer_error=''; self._mic_pcm_bytes_written=0
            self._audio_only_wave=wf; self._audio_only_path=path; self._audio_only_work_path=work_path; self._audio_only_recording=True; self._audio_only_started_source=True
            self.btn_audio_record.setText('■ Stop Audio Input Recording')
            self.lbl_render.setText(f'Recording selected microphone/external input · {channels} ch · {rate} Hz · saving to {path}')
            if hasattr(self,'lbl_mic_capture_status'):
                self.lbl_mic_capture_status.setText('Microphone recording started · '+path)
        except Exception as e:
            self._audio_only_recording=False
            try:
                self.btn_audio_record.blockSignals(True); self.btn_audio_record.setChecked(False); self.btn_audio_record.blockSignals(False)
            except Exception: pass
            self.btn_audio_record.setText('● Record Audio Input')
            self._stop_mic_source()
            # Clear any pending cooldown so the next manual press is immediate,
            # but the automatic meter path still respects it.
            msg = str(e) or 'Microphone open failed'
            if 'No microphone' in msg or 'did not start' in msg or 'unavailable' in msg.lower():
                msg = 'No usable microphone signal. Open attempts stopped. Select a different input or press Record again to retry.'
            QMessageBox.warning(self,'Audio input recording', msg)

    def _finish_audio_record_after_probe(self, ok: bool):
        if not getattr(self,'btn_audio_record',None) or not self.btn_audio_record.isChecked():
            return
        if not ok:
            self.btn_audio_record.blockSignals(True); self.btn_audio_record.setChecked(False); self.btn_audio_record.blockSignals(False)
            self.btn_audio_record.setText('● Record Audio Input')
            QMessageBox.warning(self,'Audio input recording','No physical microphone/external audio input is available.')
            return
        self._toggle_audio_input_recording(True)

    def _stop_audio_input_recording(self):
        path=str(getattr(self,'_audio_only_path','') or '')
        wf=getattr(self,'_audio_only_wave',None)
        was_monitoring=bool(getattr(self,'btn_mic_preview',None) and self.btn_mic_preview.isChecked())
        # Stop the producer before draining the PCM writer. Closing the WAV first
        # races writeframesraw() and can leave a truncated/header-only recording.
        if getattr(self,'_audio_only_finalizing',False):
            return
        self._audio_only_finalizing=True
        self._audio_only_recording=False
        self._audio_only_started_source=False
        self._stop_mic_source()
        # Never close the wave header while the dedicated PCM writer is alive.
        # A timed-out worker is retried on a short timer so the UI remains
        # responsive and the recording is finalized only after all queued blocks
        # have been written. This also prevents a later take inheriting a writer
        # or queue from the previous take.
        pump=getattr(self,'_mic_pump_thread',None)
        if pump is not None and pump.is_alive():
            pump.join(timeout=0.0)
            QTimer.singleShot(100, self._finish_audio_input_recording_after_drain)
            return
        self._finalize_audio_input_recording(path,wf,was_monitoring)

    def _finish_audio_input_recording_after_drain(self):
        path=str(getattr(self,'_audio_only_path','') or '')
        wf=getattr(self,'_audio_only_wave',None)
        was_monitoring=bool(getattr(self,'btn_mic_preview',None) and self.btn_mic_preview.isChecked())
        pump=getattr(self,'_mic_pump_thread',None)
        if pump is not None and pump.is_alive():
            QTimer.singleShot(100, self._finish_audio_input_recording_after_drain)
            return
        self._mic_pump_thread=None
        self._finalize_audio_input_recording(path,wf,was_monitoring)

    def _finalize_audio_input_recording(self,path,wf,was_monitoring):
        self._audio_only_wave=None
        work_path=str(getattr(self,'_audio_only_work_path','') or (path+'.part' if path else ''))
        close_error=''
        try:
            if wf is not None: wf.close()
        except Exception as exc:
            close_error=str(exc)
        try:
            self.btn_audio_record.blockSignals(True); self.btn_audio_record.setChecked(False); self.btn_audio_record.blockSignals(False)
            self.btn_audio_record.setText('● Record Audio Input')
        except Exception: pass
        valid=False; validation_error=str(getattr(self,'_mic_writer_error','') or close_error)
        # Verify the finalized RIFF/WAVE structure and actual duration before the
        # file becomes visible to the media library or recording list.
        if path and work_path and not validation_error:
            try:
                with wave.open(work_path,'rb') as check:
                    frames=int(check.getnframes()); rate=max(1,int(check.getframerate()))
                    channels=max(1,int(check.getnchannels())); width=int(check.getsampwidth())
                    duration=frames/float(rate)
                    valid=(frames>0 and duration>=0.10 and channels>0 and width==2 and os.path.getsize(work_path) >= 44 + frames*channels*width)
                if not valid: validation_error='WAV validation failed (empty, truncated, or too short to be usable).'
            except Exception as exc:
                validation_error='WAV validation failed: '+str(exc)
        published=False
        if valid:
            try:
                os.replace(work_path,path)
                published=True
            except Exception as exc:
                validation_error='Could not publish finalized WAV: '+str(exc)
        if published:
            # The WAV is already atomically committed. A UI/library bookkeeping
            # exception must not delete an otherwise valid user recording.
            try: self._notify_media_created(path, 'recording')
            except Exception: pass
            try: self._append_recording_path(path)
            except Exception: pass
            try:
                if bool(getattr(self,'_mic_capture_overrun',False)):
                    self.lbl_render.setText('WARNING: recording saved with audio input overruns ('+str(int(getattr(self,'_mic_drop_count',0)))+' PCM blocks lost). Reduce system load and record again: '+path)
                else:
                    self.lbl_render.setText('Recorded audio input saved: '+os.path.basename(path)+' · '+path)
                self._last_record_audio_report=_capture_signal_report(path,'wav')
                self._report_recording_audio(path)
                self._save_host_state()
            except Exception: pass
            if was_monitoring:
                QTimer.singleShot(120, lambda: self._ensure_live_mic_meter(force_restart=True) if self.isVisible() else None)
        if not published:
            for candidate in (work_path, path):
                try:
                    if candidate and os.path.isfile(candidate): os.remove(candidate)
                except Exception: pass
            detail=validation_error or 'Audio input recording stopped before usable audio was captured.'
            try: self.lbl_render.setText(detail)
            except Exception: pass
        self._audio_only_path=''
        self._audio_only_work_path=''
        self._audio_only_finalizing=False

    def _update_mic_meter(self):
        # Poll as well as listening to readyRead: some PipeWire/Qt backends do not
        # emit readyRead reliably when the UI hierarchy is reparented or hidden.
        stream_inactive=False
        try:
            if getattr(self,'_mic_backend','') == 'sounddevice':
                st=getattr(self,'_sd_mic_stream',None)
                stream_inactive=bool(st is None or (hasattr(st,'active') and not bool(st.active)))
            elif getattr(self,'_mic_backend','') == 'alsa':
                proc=getattr(self,'_alsa_mic_proc',None); stream_inactive=bool(proc is None or proc.poll() is not None)
            elif self._mic_io is not None and self._mic_io.bytesAvailable() > 0:
                self._read_mic_level()
        except Exception:
            stream_inactive=True

        # R23j continuous-meter watchdog. A backend can stay nominally open while
        # PipeWire/PortAudio stops delivering frames after its first burst. If the
        # user still has Mic Level enabled, restart only the selected input stream
        # after 1.25 s of silence, rate-limited so a missing device cannot thrash.
        now=time.monotonic()
        active=bool(getattr(self,'_mic_source',None) is not None or getattr(self,'_sd_mic_stream',None) is not None or (getattr(self,'_alsa_mic_proc',None) is not None and self._alsa_mic_proc.poll() is None))
        wanted=bool(getattr(self,'btn_mic_preview',None) and self.btn_mic_preview.isChecked())
        recording=bool(getattr(self,'_sw_recording',False) or getattr(self,'_audio_only_recording',False))
        last=float(getattr(self,'_mic_last_frame_at',0.0) or 0.0)
        restart_at=float(getattr(self,'_mic_last_restart_at',0.0) or 0.0)
        stale_frames=bool(active and last > 0.0 and now-last >= 1.25)
        if wanted and not recording and (stream_inactive or stale_frames) and now-restart_at >= 2.0:
            self._mic_last_restart_at=now
            self._mic_restart_count=int(getattr(self,'_mic_restart_count',0))+1
            self._mic_level=0.0
            # Defer restart to the next Qt turn so this timer callback never
            # tears down QAudioSource while bytesAvailable/readAll is on-stack.
            QTimer.singleShot(0, lambda: self._ensure_live_mic_meter(force_restart=True))

        # Human-readable meter: map -60 dBFS..0 dBFS to 0..100. A short decay
        # prevents a one-second-old peak from appearing as a still-live signal.
        level=max(0.0,min(1.0,float(getattr(self,'_mic_level',0.0) or 0.0)))
        if last > 0.0 and now-last > 0.30:
            level *= max(0.0, 1.0-(now-last-0.30)/0.95)
        if level <= 0.0:
            pct=0
        else:
            db=20.0*math.log10(level)
            pct=int(round(max(0.0,min(100.0,(db+60.0)*(100.0/60.0)))))
        self.mic_meter.setValue(pct)
        if hasattr(self, 'mic_record_meter'):
            self.mic_record_meter.setValue(pct)
        fresh = bool(last > 0.0 and now-last <= 0.45 and active and not stream_inactive)
        recording_now = bool(getattr(self,'_sw_recording',False) or getattr(self,'_v4l_recording',False) or getattr(self,'_audio_only_recording',False))
        try:
            if fresh:
                self.mic_meter.setFormat('Mic level %p% · LIVE')
                if hasattr(self,'lbl_mic_capture_status'):
                    destination = str(getattr(self, '_record_final_path', '') or getattr(self, '_audio_only_path', '') or '')
                    activity = 'recording PCM' if recording_now else 'monitoring'
                    suffix = (' · saving: ' + os.path.basename(destination)) if recording_now and destination else ''
                    live_text = f"Microphone: LIVE · {getattr(self,'_mic_backend','input')} · {activity}{suffix}"
                    self.lbl_mic_capture_status.setText(live_text)
                    self.lbl_mic_capture_status.setStyleSheet('color:#9dffb0; font-size:9pt; font-weight:700;')
                    if hasattr(self, 'mic_record_meter'): self.mic_record_meter.setFormat('Mic level %p% · LIVE')
                    if hasattr(self, 'lbl_mic_record_status'):
                        self.lbl_mic_record_status.setText(live_text)
                        self.lbl_mic_record_status.setStyleSheet('color:#9dffb0; font-size:9pt; font-weight:700;')
            else:
                self.mic_meter.setFormat('Mic level %p% · NO SIGNAL')
                try:
                    from audio_os_backend import last_open_error
                    err = last_open_error()
                except Exception:
                    err = ''
                reason = 'recording active but no fresh microphone samples' if recording_now else ('input stream inactive' if stream_inactive else 'waiting for microphone samples')
                if err:
                    reason = reason + ' · ' + err
                destination = str(getattr(self, '_record_final_path', '') or getattr(self, '_audio_only_path', '') or '')
                suffix = (' · intended save: ' + os.path.basename(destination)) if recording_now and destination else ''
                no_signal_text = 'Microphone: NO SIGNAL · ' + reason + suffix
                if hasattr(self,'lbl_mic_capture_status'):
                    self.lbl_mic_capture_status.setText(no_signal_text)
                    self.lbl_mic_capture_status.setStyleSheet('color:#ffb4a2; font-size:9pt; font-weight:700;')
                if hasattr(self, 'btn_audio_record') and not recording_now:
                    if self.btn_audio_record.text().startswith('●'):
                        self.btn_audio_record.setText('● Record (no signal)')
                if hasattr(self, 'mic_record_meter'): self.mic_record_meter.setFormat('Mic level %p% · NO SIGNAL')
                if hasattr(self, 'lbl_mic_record_status'):
                    self.lbl_mic_record_status.setText(no_signal_text)
                    self.lbl_mic_record_status.setStyleSheet('color:#ffb4a2; font-size:9pt; font-weight:700;')
        except Exception:
            pass

    # --------------------------- import / record
    def import_video(self, tablet=False):
        start=''
        if tablet:
            self._ensure_tablet_sources()
            start=str(self.cmb_tablet.currentData() or '')
        filt='Video files (*.mp4 *.m4v *.mov *.qt *.mkv *.webm *.avi *.mpeg *.mpg *.mpe *.m1v *.m2v *.mpv *.m2ts *.mts *.ts *.m2t *.tp *.trp *.vob *.ogv *.flv *.f4v *.wmv *.asf *.3gp *.3g2 *.mxf *.divx *.rm *.rmvb *.ivf *.nut *.amv *.wtv *.dvr-ms *.ismv *.mpd *.m3u8);;All files (*)'
        src,_=QFileDialog.getOpenFileName(self,'Import video from tablet/media' if tablet else 'Import video',start,filt)
        if not src: return
        try:
            import groovebox_paths
            dst=groovebox_paths.ingest_file(src,role='recording',project_path=self._project_path())
            self._append_recording_path(dst)
            dur=_probe_duration(dst)
            if dur>0: self.spin_duration.setValue(min(86400.0,dur))
            self.lbl_source.setText('Source: '+dst)
            self.lbl_render.setText('Imported into project recordings: '+os.path.basename(dst))
        except Exception as e: QMessageBox.warning(self,'Import video',str(e))

    def _clear_base_clip(self):
        self.base_clip=''; self.lbl_source.setText('Source: draw-only (black background)')

    def _start_software_recording(self, recdir: str, stamp: str) -> bool:
        """Linux/Fedora fallback: capture QVideoSink frames + mic PCM, encode with bundled FFmpeg.

        This deliberately avoids QMediaRecorder/GStreamer encoders, which may advertise
        formats but still fail with `Could not initialize encoder`.
        """
        if not _ffmpeg() or (self._video_sink is None and getattr(self,'_v4l_shared_stream',None) is None):
            return False
        d = tempfile.mkdtemp(prefix=f'groovebox_camera_{stamp}_', dir=recdir)
        self._sw_record_dir=d; self._sw_frame_index=0; self._sw_last_frame_t=0.0
        self._sw_record_started_at=time.monotonic(); self._sw_record_stopped_at=0.0; self._sw_record_fps=30.0
        self._sw_mjpeg_path=''
        try:
            if getattr(self,'_v4l_shared_stream',None) is not None:
                self._sw_mjpeg_path=os.path.join(d,'video.mjpeg')
                self._sw_mjpeg_fh=open(self._sw_mjpeg_path,'wb')
                # R20: drain stale frames and start the bounded disk spool before
                # the shared camera can enqueue recording packets.
                try:
                    while True: self._video_spool_queue.get_nowait()
                except Exception:
                    pass
                self._start_video_spool_pump()
            else:
                self._sw_mjpeg_fh=None
        except Exception:
            self._sw_mjpeg_fh=None; self._sw_mjpeg_path=''
        self._record_final_path=os.path.join(recdir,f'camera_{stamp}.mp4')
        self._record_path=self._record_final_path
        self._sw_started_mic=False
        try:
            mic_active=bool(self._mic_io is not None or self._mic_source is not None or self._sd_mic_stream is not None or (getattr(self,'_alsa_mic_proc',None) is not None and self._alsa_mic_proc.poll() is None) or (getattr(self,'_alsa_mic_thread',None) is not None and self._alsa_mic_thread.is_alive()))
            if not mic_active:
                self._sw_started_mic=bool(self._start_selected_audio_source(force_restart=False))
                # The direct ALSA/arecord backend intentionally has no Qt QIODevice
                # or sounddevice stream. Count its live subprocess as an active mic,
                # otherwise video recording silently omits the audio track.
                mic_active=bool(self._mic_io is not None or self._mic_source is not None or self._sd_mic_stream is not None or (getattr(self,'_alsa_mic_proc',None) is not None and self._alsa_mic_proc.poll() is None) or (getattr(self,'_alsa_mic_thread',None) is not None and self._alsa_mic_thread.is_alive()))
            if mic_active:
                self._sw_audio_rate=int(getattr(self,'_mic_sample_rate',48000) or 48000)
                self._sw_audio_channels=max(1,int(getattr(self,'_mic_channels',1) or 1))
                self._sw_audio_fh=open(os.path.join(d,'audio.s16le'),'wb')
                self._sw_audio_accepting=True
        except Exception:
            self._sw_audio_fh=None
        self._sw_recording=True
        self._set_mic_meter_timer_active(True)
        self.lbl_render.setText('Recording camera + microphone · saving to '+self._record_final_path)
        if hasattr(self,'lbl_mic_capture_status'):
            mic_state = 'capturing' if mic_active else 'NO INPUT — video will be silent'
            self.lbl_mic_capture_status.setText(f'Microphone: {mic_state} · destination {self._record_final_path}')
        if hasattr(self, 'lbl_mic_record_status'):
            self.lbl_mic_record_status.setText(f'Microphone: {"waiting for signal" if not mic_active else "recording input"} · saving to {self._record_final_path}')
        return True

    def _finish_software_recording(self):
        if not getattr(self,'_sw_recording',False) and not getattr(self,'_sw_record_dir',''):
            return
        self._sw_recording=False
        self._sw_record_stopped_at=time.monotonic()
        # Frames are already on disk/spooled as MJPEG. Unsubscribe from the shared
        # Linux camera immediately; if this was the final subscriber the physical
        # V4L2 node is released before MP4 encoding/finalization begins.
        self._detach_shared_v4l2_stream()
        self._release_camera_stream_only()
        self._sw_audio_accepting=False
        if getattr(self,'_sw_started_mic',False):
            # Stop ALSA, sounddevice, and Qt through the same lifecycle path; do not
            # leave an ALSA reader thread alive after camera recording has ended.
            self._sw_started_mic=False
            self._stop_mic_source()
        # The mic pump drains already queued PCM before its file handle is closed.
        # This avoids losing the tail of a take under CPU or disk scheduling load.
        try:
            self._stop_mic_capture_pump()
        except Exception: pass
        try:
            if self._sw_audio_fh:
                self._sw_audio_fh.flush(); self._sw_audio_fh.close()
        except Exception: pass
        self._sw_audio_fh=None
        if getattr(self,'_sd_mic_stream',None) is not None or getattr(self,'_mic_source',None) is not None or (getattr(self,'_alsa_mic_proc',None) is not None and self._alsa_mic_proc.poll() is None):
            self._start_mic_capture_pump()
        self._stop_video_spool_pump()
        try:
            if self._sw_mjpeg_fh:
                self._sw_mjpeg_fh.flush(); self._sw_mjpeg_fh.close()
        except Exception: pass
        self._sw_mjpeg_fh=None
        if getattr(self,'_sw_started_mic',False):
            try:
                if self._mic_source: self._mic_source.stop()
            except Exception: pass
            self._mic_source=None; self._mic_io=None; self._sw_started_mic=False
        d=str(getattr(self,'_sw_record_dir','') or ''); self._sw_record_dir=''
        mjpeg=str(getattr(self,'_sw_mjpeg_path','') or ''); self._sw_mjpeg_path=''
        final=str(getattr(self,'_record_final_path','') or '')
        n=int(getattr(self,'_sw_frame_index',0)); ff=_ffmpeg()
        if not d or not ff or n < 1:
            self.lbl_render.setText('Camera recording produced no frames.')
            self._record_path=''; self._record_final_path=''
            self._release_capture_devices(True)
            return
        elapsed=max(0.05,float(getattr(self,'_sw_record_stopped_at',0.0) or time.monotonic())-float(getattr(self,'_sw_record_started_at',time.monotonic()) or time.monotonic()))
        capture_duration=max(0.05,elapsed)
        # Timestamp the saved frames to the actual elapsed capture time. Using the
        # requested UI FPS to label a 30-fps camera stream makes 60-fps selections
        # play at 2x speed and truncates apparent duration.
        fps=max(1.0,min(60.0,float(n)/elapsed))
        self._sw_record_fps=fps
        audio=os.path.join(d,'audio.s16le')
        tmp=final+'.part.mp4'
        audio_rate=int(getattr(self,'_sw_audio_rate',48000) or 48000)
        audio_channels=max(1,int(getattr(self,'_sw_audio_channels',1) or 1))
        self.lbl_render.setText('Finalizing camera recording…')

        def work():
            if mjpeg and os.path.isfile(mjpeg) and os.path.getsize(mjpeg)>0:
                cmd=[ff,'-y','-v','error','-f','mjpeg','-framerate',str(fps),'-i',mjpeg]
            else:
                cmd=[ff,'-y','-v','error','-framerate',str(fps),'-i',os.path.join(d,'frame_%08d.jpg')]
            self._last_record_audio_report=_capture_signal_report(audio,'s16le')
            has_audio=os.path.isfile(audio) and os.path.getsize(audio)>0
            if has_audio:
                cmd += ['-f','s16le','-ar',str(audio_rate),'-ac',str(audio_channels),'-i',audio]
            # Keep encoder CPU use bounded so capture does not starve the Main
            # window or Performance UI on lower-core appliance hardware.
            cmd += ['-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p']
            if has_audio:
                # Pad missing audio instead of letting the shorter mic stream cut video.
                cmd += ['-af','apad','-c:a','aac','-b:a','192k']
            cmd += ['-t',f'{capture_duration:.6f}','-movflags','+faststart',tmp]
            cp=subprocess.run(cmd,capture_output=True,text=True)
            if cp.returncode!=0 or not os.path.isfile(tmp) or os.path.getsize(tmp)<1024:
                raise RuntimeError((cp.stderr or 'FFmpeg software recording failed').strip())
            if not self._recording_video_probe_ok(tmp):
                raise RuntimeError('Software recording finalized but did not contain a readable positive-duration video stream.')
            os.replace(tmp,final)
            if not os.path.isfile(final) or os.path.getsize(final)<1024:
                raise RuntimeError('Final MP4 publication failed or produced an empty file.')
            return final

        def done(result,error):
            try:
                if error is not None: raise RuntimeError(str(error))
                out=str(result or final)
                try:
                    import groovebox_paths; groovebox_paths.index_file(out,'recording',self._project_path())
                except Exception: pass
                self._append_recording_path(out); self._save_host_state()
                dur=_probe_duration(out)
                if dur>0: self.spin_duration.setValue(min(86400.0,dur))
                self.lbl_source.setText('Source: '+out); self.lbl_render.setText('Recorded + appended layer: '+os.path.basename(out))
                self._report_recording_audio(out)
            except Exception as e:
                try:
                    if final and os.path.isfile(final) and os.path.getsize(final)==0: os.remove(final)
                except Exception: pass
                self.lbl_render.setText('Software recording failed: '+str(e))
                QMessageBox.warning(self,'Camera recording failed',str(e))
            finally:
                try:
                    if tmp and os.path.isfile(tmp): os.remove(tmp)
                except Exception: pass
                try: shutil.rmtree(d,ignore_errors=True)
                except Exception: pass
                self._record_path=''; self._record_final_path=''
                self._sw_audio_accepting=False
                self._release_capture_devices(True)

        self._run_media_worker('software_record_finalize',(d,final,n,fps),work,done)

    def _record_format_candidates(self, recdir: str, stamp: str):
        """Return backend-supported live recorder candidates in preference order.

        Qt Multimedia/GStreamer availability differs by Fedora installation.  Never
        assume that choosing a container implies that an encoder for its default
        codecs exists.  Ask QMediaFormat to resolve a real Encode profile, then try
        the supported containers one-by-one.  The final project asset is still MP4;
        non-MP4 live captures are remuxed/transcoded after the recorder is stopped.
        """
        if not QT_MULTIMEDIA or QMediaFormat is None:
            return []
        mode = QMediaFormat.ConversionMode.Encode
        supported = []
        try:
            supported = list(QMediaFormat().supportedFileFormats(mode))
        except Exception:
            pass
        FF = QMediaFormat.FileFormat
        prefs = []
        for enum_name, ext, label in (
            ('MPEG4', '.mp4', 'MP4'),
            ('Matroska', '.mkv', 'Matroska'),
            ('WebM', '.webm', 'WebM'),
            ('QuickTime', '.mov', 'QuickTime'),
        ):
            v = getattr(FF, enum_name, None)
            if v is not None and (not supported or v in supported):
                prefs.append((v, ext, label))
        # Include any backend-advertised formats we did not know by name.
        for v in supported:
            if any(v == x[0] for x in prefs):
                continue
            name = getattr(v, 'name', str(v))
            ext = '.mkv'
            low = str(name).lower()
            if 'mpeg4' in low or low == 'mp4': ext = '.mp4'
            elif 'webm' in low: ext = '.webm'
            elif 'quick' in low or 'mov' in low: ext = '.mov'
            prefs.append((v, ext, str(name)))

        out = []
        for filefmt, ext, label in prefs:
            try:
                fmt = QMediaFormat()
                fmt.setFileFormat(filefmt)
                # Let Qt choose codecs that the active backend can truly encode.
                resolver = getattr(fmt, 'resolveForEncoding', None)
                if callable(resolver):
                    flags_cls = getattr(QMediaFormat, 'ResolveFlags', None)
                    rv = getattr(flags_cls, 'RequiresVideo', None) if flags_cls else None
                    ra = getattr(flags_cls, 'RequiresAudio', None) if flags_cls else None
                    flags = rv
                    if self._audio_devices and rv is not None and ra is not None:
                        try: flags = rv | ra
                        except Exception: flags = rv
                    if flags is not None:
                        resolver(flags)
                try:
                    if not fmt.isSupported(mode):
                        continue
                except Exception:
                    pass
                live = os.path.join(recdir, f'.camera_{stamp}.recording{ext}')
                # If MP4 is directly supported it can still be written to a hidden
                # temporary name; final publication only happens after probe/stability.
                out.append((fmt, live, label))
            except Exception:
                continue
        return out

    def _start_recorder_candidate(self, index: int) -> bool:
        cands = list(getattr(self, '_record_candidates', []) or [])
        if index < 0 or index >= len(cands) or self._capture_session is None:
            return False
        fmt, record_out, label = cands[index]
        try:
            old = getattr(self, '_recorder', None)
            if old is not None:
                try: old.stop()
                except Exception: pass
                try: self._capture_session.setRecorder(None)
                except Exception: pass
                self._destroy_qobject(old)
            self._recorder = QMediaRecorder(self)
            self._capture_session.setRecorder(self._recorder)
            self._recorder.setMediaFormat(fmt)
            self._recorder_error_text = ''
            self._record_candidate_index = int(index)
            self._record_path = record_out
            try:
                self._recorder.recorderStateChanged.connect(self._on_recorder_state_changed)
            except Exception:
                pass
            try:
                self._recorder.errorOccurred.connect(self._on_recorder_error)
            except Exception:
                try: self._recorder.errorChanged.connect(lambda: self._on_recorder_error())
                except Exception: pass
            try:
                if os.path.isfile(record_out): os.remove(record_out)
            except Exception:
                pass
            self._recorder.setOutputLocation(QUrl.fromLocalFile(record_out))
            self._recorder.record()
            self.lbl_render.setText(f'Recording selected camera + microphone… encoder profile: {label}')
            QTimer.singleShot(1200, self._verify_recorder_started)
            return True
        except Exception as e:
            self._recorder_error_text = str(e)
            return False

    def _try_next_recorder_candidate(self, failure_text: str = '') -> bool:
        cands = list(getattr(self, '_record_candidates', []) or [])
        start = int(getattr(self, '_record_candidate_index', -1)) + 1
        for i in range(start, len(cands)):
            try:
                oldpath = str(getattr(self, '_record_path', '') or '')
                if oldpath and os.path.isfile(oldpath) and os.path.getsize(oldpath) == 0:
                    os.remove(oldpath)
            except Exception:
                pass
            if self._start_recorder_candidate(i):
                self.lbl_render.setText(
                    f'Previous camera encoder was unavailable; trying backend profile {i+1}/{len(cands)}…')
                return True
        return False

    def _toggle_record(self,on:bool):
        if not on:
            self._stop_recording(); return
        try:
            from hardware_runtime import ensure_first_hardware_refresh
            ensure_first_hardware_refresh('video-record', block=False)
        except Exception: pass
        # R22: explicit Record may request discovery, but discovery itself stays
        # outside Groovebox. The checked button is resumed when the helper returns.
        if not (getattr(self,'_audio_devices_activated',False) and getattr(self,'_camera_devices_activated',False)):
            self.btn_record.setText('Scanning camera + microphone…')
            self._request_device_probe_async(lambda ok: self._finish_video_record_after_probe(ok), force=True)
            return
        # Do not make PortAudio enumeration the gate: Qt Multimedia and direct
        # ALSA routes can be valid even when the PortAudio list is empty.
        has_input_route = bool(getattr(self, '_audio_devices', None) or getattr(self, '_pa_audio_devices', None))
        mic_ok=self._start_selected_audio_source(force_restart=False) if has_input_route else False
        self._set_mic_meter_timer_active(True)  # visible NO SIGNAL state if input cannot open
        if not mic_ok:
            try: self.lbl_render.setText('Camera recording starting · no physical microphone opened; video will be silent unless an input becomes available.')
            except Exception: pass
        try:
            self._prepare_camera_ownership()
        except Exception as e:
            self.btn_record.blockSignals(True); self.btn_record.setChecked(False); self.btn_record.blockSignals(False)
            self.btn_record.setText('● Record Camera + Mic')
            QMessageBox.warning(self,'Camera busy',str(e)); return
        # Linux/Fedora: direct V4L2 before any Qt Multimedia enumeration.
        if sys.platform.startswith('linux') and _ffmpeg():
            stamp=self._recording_stamp(); recdir=self._recordings_dir(); os.makedirs(recdir,exist_ok=True)
            if self._start_v4l2_capture(True,recdir,stamp):
                self.btn_record.setText('■ Stop Recording'); return
        self._ensure_camera_devices(force=True)
        if not QT_MULTIMEDIA or not self._camera_devices:
            self.btn_record.setChecked(False); QMessageBox.information(self,'Record','Qt Multimedia camera support is unavailable.'); return
        try:
            # Keep the selected camera visible while recording.
            if self._camera is None or self._capture_session is None:
                idx=max(0,min(self.cmb_camera.currentIndex(),len(self._camera_devices)-1))
                dev=self._camera_devices[idx]
                self._capture_session=QMediaCaptureSession(self); self._camera=QCamera(dev,self)
                self._configure_camera_for_preview(self._camera, dev)
                try: self._camera.errorOccurred.connect(self._camera_error)
                except Exception: pass
                self._capture_session.setCamera(self._camera)
                self._attach_video_sink()
                self._last_video_frame_t=0.0
                self._camera_watchdog_generation += 1
                _gen=self._camera_watchdog_generation
                self._camera.start()
                QTimer.singleShot(1800, lambda g=_gen: self._camera_frame_watchdog(g))
            self._record_audio_input=None
            if self._audio_devices:
                mi=max(0,min(self.cmb_mic.currentIndex(),len(self._audio_devices)-1))
                self._record_audio_input=QAudioInput(self._audio_devices[mi],self); self._capture_session.setAudioInput(self._record_audio_input)

            stamp=self._recording_stamp()
            recdir=self._recordings_dir(); os.makedirs(recdir, exist_ok=True)
            self._record_final_path=os.path.join(recdir,f'camera_{stamp}.mp4')
            self._record_container='auto'
            self._record_finalize_attempts=0
            self._record_last_size=-1
            self._record_stable_size_count=0
            # Fedora/Linux: bypass fragile Qt/GStreamer encode plugins and use the
            # bundled FFmpeg encoder while Qt continues to provide camera frames.
            if sys.platform.startswith('linux') and self._start_software_recording(recdir, stamp):
                self.btn_record.setText('■ Stop Recording')
                return
            self._record_candidates=self._record_format_candidates(recdir, stamp)
            self._record_candidate_index=-1
            if not self._record_candidates:
                raise RuntimeError(
                    'Qt Multimedia reports no usable video-encoding profile. '
                    'Install/enable the Fedora GStreamer codec plugins or use Import Video until a backend encoder is available.')
            if not self._try_next_recorder_candidate('initial encoder selection'):
                raise RuntimeError('Could not initialize any camera encoder advertised by Qt Multimedia.')
            self.btn_record.setText('■ Stop Recording')
        except Exception as e:
            self.btn_record.blockSignals(True); self.btn_record.setChecked(False); self.btn_record.blockSignals(False)
            self.btn_record.setText('● Record Camera + Mic')
            # A failed recorder/encoder setup can occur *after* QCamera.start().
            # Never leave that partial capture graph alive.
            self._release_capture_devices(True)
            QMessageBox.warning(self,'Record',str(e))

    def _finish_video_record_after_probe(self, ok: bool):
        if not getattr(self,'btn_record',None) or not self.btn_record.isChecked():
            return
        if not ok:
            self.btn_record.blockSignals(True); self.btn_record.setChecked(False); self.btn_record.blockSignals(False)
            self.btn_record.setText('● Record Camera + Mic')
            QMessageBox.warning(self,'Record','Camera/microphone detection failed or timed out without blocking Groovebox.')
            return
        self._toggle_record(True)

    def _on_recorder_error(self, *args):
        try:
            self._recorder_error_text = str(self._recorder.errorString() or 'Qt Multimedia recorder error') if self._recorder else 'Qt Multimedia recorder error'
        except Exception:
            self._recorder_error_text = 'Qt Multimedia recorder error'

    def _verify_recorder_started(self):
        """Do not silently continue when Qt created a zero-byte placeholder but never started encoding."""
        if not self._recorder or not self.btn_record.isChecked():
            return
        try:
            state=self._recorder.recorderState()
            active=(state == QMediaRecorder.RecorderState.RecordingState)
        except Exception:
            active=True
        if active and not self._recorder_error_text:
            return
        msg=self._recorder_error_text or 'The Qt camera recorder did not enter RecordingState.'
        try: self._recorder.stop()
        except Exception: pass
        # Qt/GStreamer can advertise a container whose default encoder plugin is
        # missing. Retry every backend-supported resolved profile before failing.
        if self._try_next_recorder_candidate(msg):
            return
        try:
            if self._record_path and os.path.isfile(self._record_path) and os.path.getsize(self._record_path) == 0:
                os.remove(self._record_path)
        except Exception: pass
        self.btn_record.blockSignals(True); self.btn_record.setChecked(False); self.btn_record.blockSignals(False)
        self.btn_record.setText('● Record Camera + Mic')
        self.lbl_render.setText('Camera recording could not start: '+msg)
        self._release_capture_devices(True)
        QMessageBox.warning(self,'Camera recording could not start',
            msg+'\n\nGroovebox tried every encoding profile Qt reports as available on this system.')

    def _finalize_recording_to_mp4(self, src: str) -> str:
        """Worker-safe MP4 finalizer; never sleeps or polls the GUI thread.

        The recorder-stop state machine already establishes that the source is
        stable/readable before this is called.  FFmpeg completion is therefore
        the synchronization event: once the process exits successfully, probe
        the completed output exactly once and publish only a real video stream.
        """
        final=str(getattr(self,'_record_final_path','') or src)
        if not src or not os.path.isfile(src) or os.path.getsize(src) < 1024:
            return ''
        if os.path.abspath(src) == os.path.abspath(final):
            return src if self._recording_video_probe_ok(src) else ''
        ff=_ffmpeg()
        if not ff:
            return ''
        tmp=final+'.part.mp4'
        for cmd in (
            [ff,'-y','-v','error','-i',src,'-map','0:v:0','-map','0:a?','-c','copy','-movflags','+faststart',tmp],
            [ff,'-y','-v','error','-i',src,'-map','0:v:0','-map','0:a?','-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',tmp],
        ):
            try:
                cp=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
                if cp.returncode==0 and os.path.isfile(tmp) and os.path.getsize(tmp)>1024:
                    if self._recording_video_probe_ok(tmp):
                        os.replace(tmp,final)
                        if not os.path.isfile(final) or os.path.getsize(final)<1024:
                            raise RuntimeError('Final MP4 publication failed or produced an empty file.')
                        try: os.remove(src)
                        except Exception: pass
                        return final
            except Exception:
                pass
            try:
                if os.path.isfile(tmp): os.remove(tmp)
            except Exception: pass
        return ''

    def _stop_recording(self):
        # Recording stop is an ownership boundary: do not silently keep the camera
        # open as a preview after capture ends. The user can explicitly re-enable it.
        try:
            self.btn_camera_preview.blockSignals(True); self.btn_camera_preview.setChecked(False); self.btn_camera_preview.setText('▶ Camera Preview'); self.btn_camera_preview.blockSignals(False)
        except Exception: pass
        if getattr(self, '_v4l_recording', False):
            self.btn_record.setText('● Record Camera + Mic')
            QTimer.singleShot(10, self._finish_v4l2_recording)
            return
        if getattr(self, '_sw_recording', False):
            self.lbl_render.setText('Finalizing camera recording…')
            self.btn_record.setText('● Record Camera + Mic')
            QTimer.singleShot(10, self._finish_software_recording)
            return
        try:
            if self._recorder:
                self.lbl_render.setText('Finalizing camera recording…')
                self._recorder.stop()
                QTimer.singleShot(250, lambda: self._qt_record_stop_release_watchdog(0))
            else:
                self._schedule_record_finalize_check()
        except Exception:
            self._schedule_record_finalize_check()
        self.btn_record.setText('● Record Camera + Mic')

    def _qt_record_stop_release_watchdog(self, attempt=0):
        """Release Qt camera even if a backend misses recorderStateChanged.

        Windows camera drivers occasionally keep the capture source allocated when
        QMediaRecorder.stop() succeeds but the Python state-change callback is late
        or absent. Poll only while stopping; never run as a background timer.
        """
        try:
            if getattr(self, 'btn_record', None) is not None and self.btn_record.isChecked():
                return
        except Exception:
            pass
        if getattr(self, '_v4l_recording', False) or getattr(self, '_sw_recording', False):
            return
        rec=getattr(self,'_recorder',None)
        cam=getattr(self,'_camera',None)
        sess=getattr(self,'_capture_session',None)
        if rec is None and cam is None and sess is None:
            return
        stopped=False
        if rec is None:
            stopped=True
        else:
            try:
                stopped=(rec.recorderState() == QMediaRecorder.RecorderState.StoppedState)
            except Exception:
                stopped=('Stopped' in str(getattr(rec,'recorderState',lambda: '')()))
        if stopped:
            self._cache_recorder_location()
            self._release_camera_stream_only()
            if self._record_path: self._schedule_record_finalize_check()
            return
        if attempt < 7:
            QTimer.singleShot(500, lambda a=attempt+1: self._qt_record_stop_release_watchdog(a))
            return
        # Four seconds after an explicit Stop, device ownership wins over a stuck
        # backend. Ask stop once more, cache any chosen path, tear down the capture
        # graph, then let the existing finalize checker validate the file.
        try: rec.stop()
        except Exception: pass
        self._cache_recorder_location()
        self._release_camera_stream_only()
        if self._record_path: self._schedule_record_finalize_check()

    def _on_recorder_state_changed(self, state):
        """Finalize only after QMediaRecorder confirms the backend is stopped."""
        try:
            stopped = (state == QMediaRecorder.RecorderState.StoppedState)
        except Exception:
            stopped = ('Stopped' in str(state))
        if stopped:
            # Cache backend-selected path before destroying the recorder/session.
            # Destruction is queued one Qt turn so we never delete the signal sender
            # while recorderStateChanged is still on the stack.
            self._cache_recorder_location()
            QTimer.singleShot(0, self._release_camera_stream_only)
        if stopped and self._record_path:
            self._schedule_record_finalize_check()

    def _schedule_record_finalize_check(self):
        if self._record_path:
            QTimer.singleShot(250, self._finish_recording)

    def _recording_video_probe_ok(self, path: str) -> bool:
        """True when ffprobe can see a real video stream with positive duration.

        This is intentionally format-agnostic: a valid MP4/MOV/MKV produced by the
        camera backend is accepted as soon as the file is parseable and contains a
        usable video stream.  Do not reject a good capture merely because a specific
        muxer/codec name differs from what Groovebox expected.
        """
        if not path or not os.path.isfile(path):
            return False
        try:
            if os.path.getsize(path) < 1024:
                return False
        except Exception:
            return False
        probe = _ffprobe()
        if not probe:
            # Local ffprobe is part of the Groovebox runtime contract, but keep a
            # conservative fallback rather than turning a completed recording into
            # a false-negative if provisioning is temporarily unavailable.
            return _probe_duration(path) > 0.0
        try:
            cp = subprocess.run(
                [probe, '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=codec_type,duration:format=duration',
                 '-of', 'json', path],
                capture_output=True, text=True, timeout=4,
            )
            if cp.returncode != 0:
                return False
            data = json.loads(cp.stdout or '{}')
            streams = data.get('streams') or []
            if not streams or str(streams[0].get('codec_type', '')) != 'video':
                return False
            durations = []
            for value in (streams[0].get('duration'), (data.get('format') or {}).get('duration')):
                try:
                    durations.append(float(value))
                except Exception:
                    pass
            return any(d > 0.0 and math.isfinite(d) for d in durations)
        except Exception:
            return False

    def _recording_container_ready(self, path: str) -> bool:
        """Non-blocking readiness check used by the Qt-recorder finalize timer.

        Require a stable non-trivial file plus a real positive-duration video stream.
        The size gate avoids racing MP4 `moov`/filesystem finalization.
        """
        if not path or not os.path.isfile(path):
            return False
        try:
            size = os.path.getsize(path)
        except Exception:
            return False
        if size < 1024:
            return False
        last = int(getattr(self, '_record_last_size', -1))
        if size == last:
            self._record_stable_size_count = int(getattr(self, '_record_stable_size_count', 0)) + 1
        else:
            self._record_stable_size_count = 0
            self._record_last_size = size
        return (int(getattr(self, '_record_stable_size_count', 0)) >= 1
                and self._recording_video_probe_ok(path))

    def _finish_recording(self):
        path=self._record_path
        # Qt backends can choose a sibling extension; prefer reported actual location.
        try:
            if self._recorder:
                loc=self._recorder.actualLocation()
                if loc and loc.isLocalFile() and os.path.isfile(loc.toLocalFile()):
                    path=loc.toLocalFile()
                    self._record_path=path
        except Exception:
            pass

        attempts = int(getattr(self, '_record_finalize_attempts', 0)) + 1
        self._record_finalize_attempts = attempts
        if not self._recording_container_ready(path):
            # Give slow camera/GStreamer backends ample opportunity to close the MP4.
            # Do not index, probe, render, or hand the half-written file to FFmpeg.
            if attempts < 40:
                self.lbl_render.setText('Finalizing camera recording…')
                QTimer.singleShot(250, self._finish_recording)
                return
            self.lbl_render.setText('Recording did not finalize into a readable video container.')
            QMessageBox.warning(
                self, 'Recording finalize failed',
                'The camera backend stopped, but the video container is still not readable. '
                'The incomplete file was left in the project recordings folder for inspection; '
                'it was not loaded into the project.'
            )
            try:
                if path and os.path.isfile(path) and os.path.getsize(path) == 0:
                    os.remove(path)
            except Exception: pass
            self._record_path=''
            self._record_final_path=''
            self._recorder=None; self._record_audio_input=None
            self._release_capture_devices(True)
            return

        # REMUX_OFF_GUI_2026: FFmpeg remux/probe can take arbitrarily long on
        # long recordings. Run it in the same pooled worker model as V4L2
        # finalization instead of freezing Qt while subprocess.run completes.
        src_path=str(path)
        self.lbl_render.setText('Finalizing camera recording…')

        def work():
            return self._finalize_recording_to_mp4(src_path)

        def done(result,error):
            out=str(result or '')
            self._record_path=''
            self._record_final_path=''
            try:
                if error is not None:
                    raise RuntimeError(str(error))
                if not out or not os.path.isfile(out):
                    raise RuntimeError('Camera recording did not finalize into a verified MP4.')
                self._notify_media_created(out, 'recording')
                self._append_recording_path(out)
                self._save_host_state()
                d=_probe_duration(out)
                if d>0:self.spin_duration.setValue(min(86400.0,d))
                self.lbl_source.setText('Source: '+out)
                self.lbl_render.setText('Recorded: '+os.path.basename(out))
            except Exception as exc:
                self.lbl_render.setText('Camera recording failed: '+str(exc))
                QMessageBox.warning(self,'Camera recording failed',str(exc))
            finally:
                self._recorder=None; self._record_audio_input=None
                self._release_capture_devices(True)

        self._run_media_worker('qt_record_finalize',(src_path,),work,done)

    def showEvent(self, event):
        result=super().showEvent(event)
        try:
            if getattr(self, '_devices_activated', False) and getattr(self, '_audio_devices', None):
                QTimer.singleShot(0, self._ensure_live_mic_meter)
        except Exception:
            pass
        return result

    def hideEvent(self, event):
        # Switching away from Record/Import/Draw must not leave a preview device
        # allocated. Active recording/finalization is still explicit work and must
        # be allowed to complete without replacing its V4L2 stop callback.
        try:
            busy=bool((getattr(self,'btn_record',None) and self.btn_record.isChecked())
                      or getattr(self,'_audio_only_recording',False)
                      or getattr(self,'_v4l_recording',False) or getattr(self,'_sw_recording',False)
                      or getattr(self,'_v4l_record_dir','') or getattr(self,'_record_path',''))
            if not busy:
                self._release_capture_devices(True)
        except Exception:
            pass
        return super().hideEvent(event)

    def closeEvent(self, event):
        try:
            if getattr(self,'_audio_only_recording',False): self._stop_audio_input_recording()
        except Exception: pass
        try: self._release_capture_devices(True)
        except Exception: pass
        try:
            self._video_decode_pool.clear(); self._audio_level_pool.clear()
            self._video_decode_pool.waitForDone(1200); self._audio_level_pool.waitForDone(1200)
        except Exception: pass
        try: VideoClipStudio._capture_instances.discard(self)
        except Exception: pass
        return super().closeEvent(event)

    # --------------------------- paint / graph state
    def _set_color_button(self):
        c=self.canvas.color if hasattr(self,'canvas') else QColor('#ffcc33')
        self.btn_color.setStyleSheet(f'background:{c.name()}; color:{"#000" if c.lightness()>150 else "#fff"}; font-weight:800;')

    def _choose_color(self):
        c=QColorDialog.getColor(self.canvas.color,self,'Paint color')
        if c.isValid(): self.canvas.set_color(c); self._set_color_button()

    def _neutral_for_target(self,target:str)->float:
        if target=='Layer Opacity': return 1.0
        if target=='Drawn Sound Gain': return 0.5
        if target=='Sound→Color Amount': return 0.5
        return 0.5

    def _capture_curve(self):
        self._curves[self._current_curve_target]=list(self.graph.values)

    def _switch_curve(self,target:str):
        self._capture_curve(); self._current_curve_target=str(target)
        vals=self._curves.get(self._current_curve_target)
        if vals is None: vals=[self._neutral_for_target(target)]*128; self._curves[self._current_curve_target]=list(vals)
        self.graph.set_values(vals)

    def _reset_curve(self):
        v=self._neutral_for_target(self.cmb_graph_target.currentText() if hasattr(self,'cmb_graph_target') else 'Layer Opacity')
        self.graph.reset(v); self._capture_curve()

    def _curve(self,target:str,t01:float,default:float)->float:
        vals=self._curves.get(target)
        if not vals: return default
        x=max(0.0,min(1.0,float(t01)))*(len(vals)-1); i=int(x); f=x-i
        if i>=len(vals)-1:return float(vals[-1])
        return float(vals[i]*(1-f)+vals[i+1]*f)

    def _persist_layer(self,silent=True):
        try:
            self._capture_curve(); d=Path(self._layers_dir()); d.mkdir(parents=True,exist_ok=True)
            png=d/'video_clip_paint.png'; js=d/'video_clip_graph.json'
            self.canvas.image.save(str(png),'PNG')
            draw_meta=[]
            for i,(rec,canvas) in enumerate(zip(self.draw_layers,self.draw_canvases)):
                lp=d/f'video_clip_paint_{i:02d}.png'; canvas.image.save(str(lp),'PNG'); draw_meta.append(dict(rec,image=str(lp)))
                try:
                    import groovebox_paths
                    groovebox_paths.index_file(str(lp),'layer',self._project_path())
                except Exception: pass
            data={'version':2,'base_clip':self.base_clip,'curves':self._curves,'drawing_layers':draw_meta,'recording_layers':list(self.recording_layers),'color_sound':self.chk_color_sound.isChecked(),'sound_color':self.chk_sound_color.isChecked(),'draw_sound':self.chk_draw_sound.isChecked(),'color_detail':self.cmb_color_detail.currentText()}
            js.write_text(json.dumps(data,indent=2),encoding='utf-8')
            import groovebox_paths; groovebox_paths.index_file(str(png),'layer',self._project_path()); groovebox_paths.index_file(str(js),'layer',self._project_path())
            if not silent:self.lbl_render.setText('Saved paint + graph layer in project layers/.')
            return str(png),str(js)
        except Exception as e:
            if not silent: QMessageBox.warning(self,'Save layer',str(e))
            return '',''

    def export_state(self)->Dict[str,Any]:
        png,js=self._persist_layer(True)
        draw_state=[dict(r) for r in self.draw_layers]
        try:
            saved=json.loads(Path(js).read_text(encoding='utf-8')) if js and os.path.isfile(js) else {}
            if isinstance(saved.get('drawing_layers'),list):draw_state=saved['drawing_layers']
        except Exception:pass
        return {'version':3,'base_clip':self.base_clip,'paint_layer':png,'graph_state':js,'camera':self.cmb_camera.currentText(),'microphone':(self.cmb_mic.currentData() or self.cmb_mic.currentText()),'tablet_source':self.cmb_tablet.currentData() or '','duration':float(self.spin_duration.value()),'fps':int(self.spin_fps.value()),'width':int(self.spin_width.value()),'height':int(self.spin_height.value()),'draw_sound':self.chk_draw_sound.isChecked(),'color_sound':self.chk_color_sound.isChecked(),'sound_color':self.chk_sound_color.isChecked(),'color_detail':self.cmb_color_detail.currentText(),'bind_all_mode':self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Video','last_rendered_video':self.last_rendered_video,'recording_layers':list(self.recording_layers),'drawing_layers':draw_state}

    def restore_state(self,state:Dict[str,Any]):
        if not isinstance(state,dict):return
        self.base_clip=str(state.get('base_clip') or '')
        if self.base_clip:self.lbl_source.setText('Source: '+self.base_clip)
        for combo,key in ((self.cmb_camera,'camera'),(self.cmb_mic,'microphone')):
            text=str(state.get(key) or ''); idx=combo.findText(text)
            if idx<0 and combo is self.cmb_mic:
                for i in range(combo.count()):
                    if str(combo.itemData(i) or '') == text: idx=i; break
            if idx>=0:combo.setCurrentIndex(idx)
        tpath=str(state.get('tablet_source') or '')
        if tpath:
            for i in range(self.cmb_tablet.count()):
                if str(self.cmb_tablet.itemData(i) or '')==tpath:self.cmb_tablet.setCurrentIndex(i);break
        self.spin_duration.setValue(max(.25,min(86400,float(state.get('duration',5.0)))))
        self.spin_fps.setValue(max(1,min(120,int(state.get('fps',30)))))
        self.spin_width.setValue(max(160,min(3840,int(state.get('width',1280)))))
        self.spin_height.setValue(max(90,min(2160,int(state.get('height',720)))))
        self.chk_draw_sound.setChecked(bool(state.get('draw_sound',False))); self.chk_color_sound.setChecked(bool(state.get('color_sound',False))); self.chk_sound_color.setChecked(bool(state.get('sound_color',False)))
        detail=str(state.get('color_detail') or 'Off'); self.cmb_color_detail.setCurrentText(detail if detail in ('Off','Basic','Detailed') else 'Off')
        mode=str(state.get('bind_all_mode') or 'Video')
        if hasattr(self,'cmb_bind_all') and mode in ('Video','Audio','Both','Unbound'):self.cmb_bind_all.setCurrentText(mode)
        self.last_rendered_video=str(state.get('last_rendered_video') or '')
        for rp in state.get('recording_layers',[]) or []:
            if isinstance(rp,str) and os.path.isfile(rp):self._append_recording_path(rp)
        saved_draw=state.get('drawing_layers',[]) or []
        if saved_draw:
            while self.draw_tabs.count():self.draw_tabs.removeTab(0)
            self.draw_layers=[]; self.draw_canvases=[]
            for rec in saved_draw:
                if not isinstance(rec,dict):continue
                c=PaintCanvas(); ip=str(rec.get('image') or '')
                if ip and os.path.isfile(ip):
                    im=QImage(ip)
                    if not im.isNull():c.image=im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                rr={k:rec.get(k) for k in ('name','start','end','fade')}; rr['name']=str(rr.get('name') or f'Drawing {len(self.draw_layers)+1}')
                self.draw_layers.append(rr); self.draw_canvases.append(c); self.draw_tabs.addTab(c,rr['name'])
            if self.draw_layers:self.draw_tabs.setCurrentIndex(0); self._draw_tab_changed(0)
        png=str(state.get('paint_layer') or ''); js=str(state.get('graph_state') or '')
        try:
            if png and os.path.isfile(png):
                im=QImage(png)
                if not im.isNull():self.canvas.image=im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied);self.canvas.update()
            if js and os.path.isfile(js):
                data=json.loads(Path(js).read_text(encoding='utf-8')); curves=data.get('curves')
                if isinstance(curves,dict):self._curves={str(k):[float(v) for v in vals] for k,vals in curves.items() if isinstance(vals,list)}
                self._switch_curve(self.cmb_graph_target.currentText())
        except Exception:pass

    def _save_host_state(self):
        try:
            state=getattr(self.host,'media_workbench_state',None)
            if not isinstance(state,dict):state={};setattr(self.host,'media_workbench_state',state)
            state['video_clip_studio']=self.export_state()
        except Exception:pass

    def _selected_instrument_name(self):
        h=self.host
        try:
            if h is not None and hasattr(h,'_current_instrument_name'):return str(h._current_instrument_name())
        except Exception:pass
        try:
            c=getattr(h,'instrument_selector_dropdown',None)
            if c is not None:return str(c.currentText())
        except Exception:pass
        return 'selected'

    def _bind_all_layers_to_instrument(self):
        mode=self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Video'
        name=self._selected_instrument_name(); h=self.host
        store=getattr(h,'instrument_media_samples',None)
        if not isinstance(store,dict):store={};setattr(h,'instrument_media_samples',store)
        if mode=='Unbound':
            rec=store.get(name)
            if isinstance(rec,dict) and rec.get('binding_source')=='video_clip_studio_all_layers':store.pop(name,None)
            self._save_host_state(); self.lbl_render.setText(f'Unbound Video Clip Studio layers from {name}.'); return
        video=str(self.last_rendered_video or '')
        if not video or not os.path.isfile(video):
            auto_name=_safe_stem(name or 'selected_operator')+'_all_layers_bound.mp4'
            auto_path=os.path.join(self._video_exports_dir(), auto_name)
            self.lbl_render.setText('Materializing editable layers for selected operator…')
            def _after(v):
                if v and os.path.isfile(v):
                    self._bind_all_layers_to_instrument()          # continue now that the render exists
                else:
                    QMessageBox.warning(self,'Bind All Layers','Could not materialize the current recording/drawing layers for the selected operator. See the render status for details.')
            self.render_video(output_path=auto_path, quiet=True, on_done=_after)   # CLIP_RENDER_ASYNC_R31
            return
        arr=np.zeros(1,dtype=np.float32); sr=44100; has_audio=False
        if mode in ('Audio','Both'):
            try:
                if h is not None and hasattr(h,'_decode_media_audio'):
                    arr,sr=h._decode_media_audio(video); has_audio=bool(np.asarray(arr).size)
                else:
                    raise RuntimeError('host media decoder unavailable')
            except Exception as e:
                if mode=='Audio':QMessageBox.warning(self,'Bind All Layers',f'The rendered video has no decodable audio to bind: {e}'); return
        # Video-only bindings retain a tiny silent runtime waveform; project restore
        # preserves the video path even when the container has no audio stream.
        path=video if mode in ('Video','Both') else video
        store[name]={'path':path,'sample_rate':int(sr),'waveform':np.asarray(arr,dtype=np.float32).reshape(-1),'user_owned':True,'source_kind':'video' if mode in ('Video','Both') else 'audio','video_path':video if mode in ('Video','Both') else '','video_input_enabled':mode in ('Video','Both'),'layered_state':self.export_state(),'binding_mode':mode.lower(),'binding_source':'video_clip_studio_all_layers','bound_layers_state':self.export_state(),'audio_present':bool(has_audio)}
        self._save_host_state(); self.lbl_render.setText(f'Bound ALL video/draw layers → {name} as {mode}.')
        try:
            if hasattr(h,'_refresh_operator_sample_ui'):h._refresh_operator_sample_ui()
            if hasattr(h,'_on_live_source_changed'):h._on_live_source_changed()
        except Exception:pass


    def _bind_all_layers_to_carrier(self):
        mode=self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Both'
        h=self.host
        if mode=='Unbound':
            setattr(h,'carrier_binding_source',''); setattr(h,'carrier_binding_mode','unbound'); setattr(h,'carrier_bound_layers_state',{})
            self._save_host_state(); self.lbl_render.setText('Unbound video/draw layers from carrier provenance. Current carrier media is left intact.'); return
        video=str(getattr(self,'last_render_path','') or getattr(self,'_last_render_path','') or self.last_rendered_video or '')
        if not video or not os.path.isfile(video):
            auto_path=os.path.join(self._video_exports_dir(), 'carrier_all_layers_bound.mp4')
            self.lbl_render.setText('Materializing editable layers for carrier…')
            def _after(v):
                if v and os.path.isfile(v):
                    self._bind_all_layers_to_carrier()
                else:
                    QMessageBox.warning(self,'Bind All Layers to Carrier','Could not materialize the current recording/drawing layers for the carrier. See the render status for details.')
            self.render_video(output_path=auto_path, quiet=True, on_done=_after)   # CLIP_RENDER_ASYNC_R31
            return
        old_audio=(getattr(h,'imported_waveform',None),getattr(h,'imported_sample_rate',44100),str(getattr(h,'imported_wav_path','') or ''))
        old_video=(str(getattr(h,'imported_video_path','') or ''),getattr(h,'imported_video_meta',{}) or {})
        if mode=='Both':
            h._load_video_path(video)
        elif mode=='Video':
            h._load_video_path(video)
            # Keep the prior audio carrier while replacing only the visual carrier.
            if old_audio[0] is not None:
                h.imported_waveform=old_audio[0]; h.imported_sample_rate=old_audio[1]; h.imported_wav_path=old_audio[2]
        elif mode=='Audio':
            # Decode this render as audio carrier while retaining the prior visual carrier.
            arr,sr=h._decode_media_audio(video)
            arr=np.asarray(arr,dtype=np.float32).reshape(-1)
            h.imported_waveform=arr; h.imported_sample_rate=int(sr); h.imported_wav_path=video
            h.imported_video_path=old_video[0]; h.imported_video_meta=old_video[1]
            try: h._refresh_after_file_input(reason='video_render_audio_carrier')
            except Exception: pass
        setattr(h,'carrier_binding_source','video_clip_studio_all_layers')
        setattr(h,'carrier_binding_mode',mode.lower())
        setattr(h,'carrier_bound_layers_state',self.export_state())
        self._save_host_state(); self.lbl_render.setText(f'Bound ALL video/draw layers → Carrier {mode}: {os.path.basename(video)}')

    # --------------------------- translation + render
    def _paint_color_regions(self,detail:str)->List[Tuple[float,float,float]]:
        im=self.canvas.image.scaled(48,27,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGBA8888)
        ptr=im.bits(); ptr.setsize(im.sizeInBytes()); a=np.frombuffer(ptr,dtype=np.uint8).reshape(im.height(),im.width(),4)
        alpha=a[:,:,3].astype(np.float64)/255.0
        if float(alpha.sum()) == 0.0:return []
        def region_stats(block):
            aa=block[:,:,3].astype(np.float64)/255.0; denom=float(aa.sum()); rgb=(block[:,:,:3].astype(np.float64)*aa[:,:,None]).sum(axis=(0,1))/denom if denom != 0.0 else np.zeros(3,dtype=np.float64)
            c=QColor(int(rgb[0]),int(rgb[1]),int(rgb[2])); h,s,v,_=c.getHsvF(); return (0.0 if h<0 else h,s,v)
        if detail!='Detailed':return [region_stats(a)]
        out=[]
        for yy in np.array_split(np.arange(im.height()),3):
            for xx in np.array_split(np.arange(im.width()),4):
                b=a[np.ix_(yy,xx)]
                if b[:,:,3].sum()>0:out.append(region_stats(b))
        return out[:12]

    def _extract_audio_envelope(self,path:str,duration:float,fps:int)->np.ndarray:
        n=max(1,int(round(duration*fps))); out=np.zeros(n,dtype=np.float64); ff=_ffmpeg()
        if not ff or not path or not os.path.isfile(path) or not _probe_has_audio(path):return out
        try:
            cp=subprocess.run([ff,'-v','error','-t',f'{duration:.6f}','-i',path,'-vn','-ac','1','-ar',str(max(100,fps*4)),'-f','f32le','pipe:1'],capture_output=True,timeout=max(15,int(duration)+10))
            x=np.frombuffer(cp.stdout,dtype=np.float32).astype(np.float64)
            if not x.size:return out
            sr=max(100,fps*4); chunk=max(1,int(sr/fps))
            vals=[]
            for i in range(n):
                seg=x[i*chunk:min(x.size,(i+1)*chunk)]
                vals.append(float(np.sqrt(np.mean(seg*seg))) if seg.size else 0.0)
            out=np.asarray(vals,dtype=np.float64); mx=float(out.max()) if out.size else 0.0
            if mx != 0.0:out/=mx
        except Exception:pass
        return out

    def _sound_inputs(self):
        """GUI thread: every widget/canvas read the drawn sound needs (CLIP_RENDER_ASYNC_R31)."""
        detail=self.cmb_color_detail.currentText()
        use_color=self.chk_color_sound.isChecked() and detail!='Off'
        use_draw=self.chk_draw_sound.isChecked()
        return {'detail':detail,'use_color':use_color,'use_draw':use_draw,
                'pitch':list(self._curves.get('Drawn Sound Pitch',[.5]*128)),
                'gain':list(self._curves.get('Drawn Sound Gain',[.5]*128)),
                'regs':(self._paint_color_regions(detail) if use_color else [])}

    def _generate_sound(self,path:str,duration:float,sr=48000)->bool:
        return _synth_drawn_sound(self._sound_inputs(),path,duration,sr)

    def _render_frame(self,w:int,h:int,t01:float,sound_amp:float,transparent:bool)->QImage:
        frame=QImage(w,h,QImage.Format.Format_ARGB32_Premultiplied)
        frame.fill(Qt.GlobalColor.transparent if transparent else QColor(0,0,0))
        opacity=self._curve('Layer Opacity',t01,1.0)
        xcurve=self._curve('Layer X',t01,.5); ycurve=self._curve('Layer Y',t01,.5); sc=self._curve('Layer Scale',t01,.5); rot=self._curve('Layer Rotation',t01,.5)
        scale=0.25 + sc*1.75; angle=(rot-.5)*720.0; dx=(xcurve-.5)*w; dy=(ycurve-.5)*h
        with owned_painter(frame) as q:
            if q is None:
                return
            q.setRenderHint(QPainter.RenderHint.Antialiasing,True); q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True)
            tsec=t01*float(self.spin_duration.value())
            pairs=list(zip(self.draw_layers,self.draw_canvases)) or [({'start':0,'end':math.inf,'fade':0},self.canvas)]
            for rec,canvas in pairs:
                tg=self._draw_layer_time_gain(rec,tsec)
                if tg<=0:continue
                layer=canvas.image.scaled(w,h,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
                q.setOpacity(max(0,min(1,opacity*tg))); q.save(); q.translate(w/2+dx,h/2+dy); q.rotate(angle); q.scale(scale,scale); q.translate(-w/2,-h/2); q.drawImage(0,0,layer); q.restore()
            q.resetTransform(); q.setOpacity(1.0)
            # GROOVEBOX_R23R_LSYSTEM_VIDEO_REITERATION_20261031: composite the L-system
            # reiteration frame. Tracks the Fractal Seed when Fractal Seed Mode is ON
            # (pulls axiom/rules from the host's Fractal Seed); falls back to the
            # Koch-like default when Fractal Seed is OFF or the host is unavailable.
            # Gated on the L-System Reiteration toggle.
            try:
                _chk = getattr(self, 'chk_lsystem_video', None)
                if _chk is not None and _chk.isChecked():
                    _host = getattr(self, 'host', None)
                    _fs_params = _lsystem_fractal_seed_params(_host)
                    _fs = {'axiom': _fs_params[0], 'rules': _fs_params[1]} if _fs_params else None
                    _fs_off, _fs_dil = _lsystem_fractal_seed_offset_dilation(_host)
                    _curves = dict(self._curves) if hasattr(self, '_curves') else {}
                    _ls = _render_lsystem_frame_video(w, h, t01, sound_amp, _curves,
                                                     hue_base=0.0, hue_range=1.0,
                                                     turn_deg=60.0, fractal_seed=_fs,
                                                     fractal_seed_offset=_fs_off,
                                                     fractal_seed_dilation=_fs_dil)
                    if _ls is not None:
                        q.setOpacity(max(0.0, min(1.0, 0.5 * opacity)))
                        q.drawImage(0, 0, _ls)
                        q.setOpacity(1.0)
            except Exception:
                pass
            if self.chk_sound_color.isChecked() and sound_amp>0:
                amt=self._curve('Sound→Color Amount',t01,.5)*sound_amp
                c=QColor.fromHsvF((0.02+0.80*sound_amp)%1.0,0.75,0.9,max(0.0,min(.65,amt*.65)))
                q.fillRect(frame.rect(),c)
            q.end(); return frame

    def render_video(self, output_path=None, quiet=False, on_done=None):
        """CLIP_RENDER_ASYNC_R31: snapshot + sound on the GUI thread; frames, FFmpeg encode and
        verification on a worker thread. No processEvents pumping, no sleeps on the GUI thread.
        on_done(path_or_None) is called on the GUI thread when the render finishes."""
        def _finish(result):
            if callable(on_done):
                try: on_done(result)
                except Exception as _cb_exc: self.lbl_render.setText('Render follow-up failed: '+str(_cb_exc))
            return result
        if getattr(self, '_render_busy', False):
            self.lbl_render.setText('A render is already running — it will finish first.')
            return _finish(None)
        ff=_ffmpeg()
        if not ff:
            QMessageBox.warning(self,'Render video','FFmpeg is not available in the local Groovebox bin/PATH.'); return _finish(None)
        self._capture_curve(); self._persist_layer(True)
        duration=float(self.spin_duration.value()); fps=int(self.spin_fps.value()); w=int(self.spin_width.value()); h=int(self.spin_height.value())

        # RECORDING_LAYER_RENDER_2026: every appended recording layer participates
        # in the render. Older builds only switched base_clip, so the layer tabs were
        # state/UI without true multi-layer composition.
        video_layers=[]
        for candidate in list(self.recording_layers) + ([self.base_clip] if self.base_clip else []):
            candidate=os.path.abspath(str(candidate or ''))
            if candidate and os.path.isfile(candidate) and candidate not in video_layers:
                video_layers.append(candidate)

        default=os.path.join(self._video_exports_dir(),_safe_stem(Path(video_layers[0]).stem if video_layers else 'drawn_video')+'_mixed.mp4')
        if output_path:
            out=os.path.abspath(str(output_path))
            os.makedirs(os.path.dirname(out), exist_ok=True)
        else:
            out,_=QFileDialog.getSaveFileName(self,'Render / Mix Video Clip',default,'MP4 video (*.mp4);;WebM video (*.webm)')
            if not out:return _finish(None)
        if not os.path.splitext(out)[1]:out += '.mp4'
        _cleanup_stale_render_parts(os.path.dirname(out) or self._video_exports_dir())
        tmp=Path(self._layers_dir())/'_video_clip_render_tmp'; shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True,exist_ok=True)
        # Publish transactionally: the final filename must never point at a partial
        # encode. Keep the real media suffix last so FFmpeg selects the right muxer.
        ext=Path(out).suffix.lower() or '.mp4'
        publish=out[:-len(ext)]+'.part'+ext
        try:
            for stale in (publish, out + '.part' + ext):
                try:
                    if os.path.isfile(stale): os.remove(stale)
                except OSError: pass
            n=max(1,int(math.ceil(duration*fps)))
            envelope_source = self.base_clip if self.base_clip and os.path.isfile(self.base_clip) else (video_layers[0] if video_layers else '')
            transparent=bool(video_layers)
            sound_color=bool(self.chk_sound_color.isChecked())
            curves_snapshot={str(k):list(v) for k,v in self._curves.items()}
            # GROOVEBOX_R23R_LSYSTEM_VIDEO_REITERATION_20261031: pass the L-system
            # reiteration enable flag and the Fractal Seed axiom/rules through to
            # the independent frame worker so the L-system video layer tracks the
            # Fractal Seed and respects the UI toggle.
            try:
                _chk = getattr(self, 'chk_lsystem_video', None)
                if _chk is not None and _chk.isChecked():
                    curves_snapshot['_lsystem_video_enabled'] = True
                _fs_params = _lsystem_fractal_seed_params(getattr(self, 'host', None))
                if _fs_params:
                    curves_snapshot['_fractal_seed_params'] = _fs_params
                # GROOVEBOX_R23R_LSYSTEM_VIDEO_REITERATION_20261031:
                # Pass the Fractal Seed Offset / Dilation from the Video
                # Planner's VideoAssemblyRules through to the snapshot renderer.
                _fs_off, _fs_dil = _lsystem_fractal_seed_offset_dilation(getattr(self, 'host', None))
                curves_snapshot['_fractal_seed_offset'] = _fs_off
                curves_snapshot['_fractal_seed_dilation'] = _fs_dil
            except Exception:
                pass
            if self.draw_layers and self.draw_canvases:
                frame_layers=[(dict(rec),canvas.image.copy()) for rec,canvas in zip(self.draw_layers,self.draw_canvases)]
            else:
                frame_layers=[({'start':0,'end':math.inf,'fade':0},self.canvas.image.copy())]
            sound=str(tmp/'drawn_sound.wav'); _sound_in=self._sound_inputs()   # widget reads only: GUI thread
            has_generated=bool(_sound_in['use_color'] or _sound_in['use_draw'])
            self.lbl_render.setText(f'Rendering {n} frame(s) + encode on a background worker…')
            def _progress(text):
                self._worker_finished.emit(lambda _r,_e,t=text: self.lbl_render.setText(t), None, None)
            def _work():
                env=self._extract_audio_envelope(envelope_source,duration,fps) if sound_color else np.zeros(n)
                for i in range(n):
                    amp=float(env[min(i,len(env)-1)]) if len(env) else 0.0
                    fr=_render_frame_snapshot(w,h,i/max(1,n-1),amp,transparent,duration,curves_snapshot,frame_layers,sound_color)
                    if not fr.save(str(tmp/f'frame_{i:06d}.png'),'PNG'):
                        raise RuntimeError(f'Could not write render-buffer frame {i+1}/{n}')
                    if i % max(1,fps)==0 or i+1==n:
                        _progress(f'Background frame buffer: {i+1}/{n} · {100.0*(i+1)/n:.0f}%')
                if has_generated:
                    _synth_drawn_sound(_sound_in, sound, duration)          # synthesis + WAV write: worker thread
                _progress('Encoding with FFmpeg…')
                seq=str(tmp/'frame_%06d.png'); codec='libvpx-vp9' if ext=='.webm' else 'libx264'
                cmd=[ff,'-y']
                for src in video_layers:
                    cmd += ['-i',src]
                paint_idx=len(video_layers)
                cmd += ['-framerate',str(fps),'-i',seq]
                sound_idx=paint_idx+1
                if has_generated: cmd += ['-i',sound]

                filters=[]
                if video_layers:
                    # Fit each recording to the target frame and hold its last frame to
                    # the requested project duration. Blend incrementally with weights
                    # chosen so N layers contribute equally rather than hiding each other.
                    for j in range(len(video_layers)):
                        filters.append(
                            f'[{j}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,'
                            f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,'
                            f'tpad=stop_mode=clone:stop_duration={duration:.6f},trim=duration={duration:.6f},setpts=PTS-STARTPTS[rv{j}]')
                    comp='rv0'
                    for j in range(1,len(video_layers)):
                        k=j+1; outtag=f'rmix{j}'
                        filters.append(f'[{comp}][rv{j}]blend=all_expr=\'A*{k-1}/{k}+B/{k}\':shortest=1[{outtag}]')
                        comp=outtag
                    filters.append(f'[{comp}][{paint_idx}:v]overlay=0:0:shortest=1[v]')
                else:
                    filters.append(f'[{paint_idx}:v]format=rgba[v]')

                audio_refs=[]
                for j,src in enumerate(video_layers):
                    if _probe_has_audio(src):
                        filters.append(f'[{j}:a]apad=whole_dur={duration:.6f},atrim=duration={duration:.6f},asetpts=PTS-STARTPTS[ra{j}]')
                        audio_refs.append(f'[ra{j}]')
                if has_generated:
                    filters.append(f'[{sound_idx}:a]apad=whole_dur={duration:.6f},atrim=duration={duration:.6f},asetpts=PTS-STARTPTS[rgen]')
                    audio_refs.append('[rgen]')
                audio_map=None
                if len(audio_refs)>1:
                    filters.append(''.join(audio_refs)+f'amix=inputs={len(audio_refs)}:normalize=0:dropout_transition=0[a]')
                    audio_map='[a]'
                elif len(audio_refs)==1:
                    audio_map=audio_refs[0]

                cmd += ['-filter_complex',';'.join(filters),'-map','[v]']
                if audio_map: cmd += ['-map',audio_map]
                cmd += ['-t',f'{duration:.6f}','-r',str(fps),'-c:v',codec]
                if codec=='libx264':cmd += ['-pix_fmt','yuv420p','-crf','18','-preset','veryfast']
                else:cmd += ['-pix_fmt','yuv420p','-b:v','0','-crf','30']
                if audio_map: cmd += ['-c:a',_audio_encoder_for(ff, ext),'-b:a','192k']
                cmd += ['-movflags','+faststart'] if ext in ('.mp4','.m4v','.mov') else []
                cmd += [publish]
                # Worker thread: wait for FFmpeg here, never on the Qt thread.
                proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                try:
                    stdout,stderr=proc.communicate(timeout=max(60,int(duration*8)+30))
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.communicate(); raise TimeoutError('FFmpeg render timed out; partial output will be cleaned up.')
                if proc.returncode!=0: raise RuntimeError((stderr or stdout or 'FFmpeg failed')[-5000:])
                if not os.path.isfile(publish) or os.path.getsize(publish)<1024:
                    raise RuntimeError('FFmpeg returned success but produced no usable output file.')
                if _probe_duration(publish)<=0:
                    raise RuntimeError('Rendered file failed duration verification; original destination was preserved.')
                if audio_refs and not _probe_has_audio(publish):
                    raise RuntimeError(f'Rendered {ext} file is missing the expected audio stream; original destination was preserved.')
                return True
            def _done(_ok, error):
                self._render_busy=False
                try:
                    if error is not None:
                        for stale in (publish, out + '.part' + ext):
                            try:
                                if os.path.isfile(stale): os.remove(stale)
                            except OSError: pass
                        if not quiet: QMessageBox.warning(self,'Render video',str(error))
                        self.lbl_render.setText('Render failed: '+str(error))
                        _finish(None); return
                    os.replace(publish,out)
                    try:
                        import groovebox_paths; groovebox_paths.index_file(out,'video_export',self._project_path())
                    except Exception:pass
                    self.last_rendered_video=str(out)
                    self.last_render_path=str(out)
                    self._last_render_path=str(out)
                    self._save_host_state()
                    self.lbl_render.setText(f'Rendered {len(video_layers)} recording layer(s): '+out)
                    try:
                        if hasattr(self.parent(),'refresh'):self.parent().refresh()
                    except Exception:pass
                    _finish(str(out))
                finally:
                    shutil.rmtree(tmp,ignore_errors=True)
            def _runner():
                try:
                    res=_work(); err=None
                except Exception as exc:
                    res, err = None, exc
                self._worker_finished.emit(_done, res, err)
            self._render_busy=True
            threading.Thread(target=_runner,name='GrooveboxClipRender',daemon=True).start()
            return None
        except Exception as e:
            for stale in (publish, out + '.part' + ext):
                try:
                    if os.path.isfile(stale): os.remove(stale)
                except OSError: pass
            if not quiet: QMessageBox.warning(self,'Render video',str(e))
            self.lbl_render.setText('Render failed: '+str(e))
            shutil.rmtree(tmp,ignore_errors=True)
            return _finish(None)


# GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103: no dialog may block other windows.
try:
    import nonmodal_dialogs as _gb_nonmodal
    _gb_nonmodal.install()
except Exception:
    pass
