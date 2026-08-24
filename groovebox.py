# =============================================================================
# EQR Groovebox Engine v3.6.8+ — stable media/convolve-fit build
# Mathematician's / Scientist's Groovebox — mathematical specification for
# maximum initial harmonic diversity; simple and complex projects with equal ease.
#
# Credits / collaboration:
#   - Core architecture & original EQR design: project author
#   - Implementation assistance (realtime audio, additive engines, domain
#     partitions, bootstrap/simplify, Help system): Grok (xAI), Gemini (Google),
#     Claude (Anthropic) and ChatGPT (OpenAI)
#
# Notable systems in this build:
#   sounddevice realtime I/O, PKP pad bank, additive Euclidean/seeded engines,
#   non-destructive patch optimizer, domain time/space equations, seed bootstrap
#   (empty/0 = no seed; 50/50 both vs alone when free), net-effect user detection.
# =============================================================================

import random
import struct
import math
import ast
import copy
import wave
import time
import json
import os
import threading
import queue
import subprocess
import tempfile
import shutil
import colorsys
import numpy as np
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QPainterPath, QLinearGradient, QBrush, QFont, QPolygonF,
    QAction, QPalette, QKeyEvent, QKeySequence, QImage
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout,
    QHBoxLayout, QLabel, QSlider, QPushButton, QComboBox, QScrollArea,
    QTabWidget, QLineEdit, QListWidget, QFormLayout, QSpinBox, QDoubleSpinBox,
    QGridLayout, QFileDialog, QSplitter, QGroupBox, QTextEdit, QMenu,
    QMessageBox, QTableWidget, QTableWidgetItem, QCheckBox, QDial, QMenuBar,
    QDialog, QInputDialog, QHeaderView, QProgressBar, QSizePolicy, QToolButton
)  # QToolButton is required by the global EXPORT menu control.


try:
    import scipy.io.wavfile as wavfile
except ImportError:
    wavfile = None

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    sd = None
    HAS_SOUNDDEVICE = False

# POWER_V3_MEUM_CORE — canonical Meum spatial-dynamic constant.
# M = 1.19758073433... is treated as an invariant mathematical constant,
# not as an arbitrary synth-control percentage. Derived values below are
# reusable shortcuts so the DSP/visualizer/context engines do not repeatedly
# re-encode the same Meum arithmetic.
MEUM = 1.1975807343385265188
MEUM_CONSTANT = MEUM  # backwards-compatible alias used throughout the codebase
MEUM_MINUS_1 = MEUM - 1.0
MEUM_INV = 1.0 / MEUM
MEUM_SQ = MEUM * MEUM
MEUM_CUBE = MEUM_SQ * MEUM
MEUM_FOURTH = MEUM_SQ * MEUM_SQ
MEUM_NORM = MEUM_MINUS_1 * MEUM_INV          # (M-1)/M ≈ soft weight / pane opacity seed
MEUM_OVER_1_5 = MEUM / 1.5
MEUM_TWO_POW = 2.0 ** MEUM
MEUM_TWO_POW_OVER_SQ = MEUM_TWO_POW / MEUM_SQ
MEUM_LOG2 = math.log2(MEUM)
# Frequently used integer powers: M^0 ... M^35.
MEUM_POWERS_36 = tuple(MEUM ** i for i in range(36))
MEUM_IDENTITY_LHS = (MEUM_MINUS_1 * MEUM) + (MEUM_MINUS_1 * MEUM_INV)
MEUM_IDENTITY_RHS = MEUM_TWO_POW_OVER_SQ - MEUM
MEUM_IDENTITY_RESIDUAL = MEUM_IDENTITY_LHS - MEUM_IDENTITY_RHS
# Relational aesthetic scales (UI + field motion). Meum-first; secondary book irrationals second.
PHI = (1.0 + math.sqrt(5.0)) * 0.5          # golden ratio φ
PHI_INV = PHI - 1.0                           # 1/φ = φ-1
E_IRR = math.e
PI_IRR = math.pi
SQRT2 = math.sqrt(2.0)
SQRT3 = math.sqrt(3.0)
SILVER = 1.0 + SQRT2                          # silver ratio δ_s
# UI design tokens derived from M (self-similar spacing / translucency)
UI_OPACITY = max(0.12, min(0.42, MEUM_NORM * PHI))          # pane glass
UI_RADIUS = max(4, int(round(3.0 * MEUM)))                    # corner radius
UI_TICK_MS = max(28, int(round(1000.0 / (MEUM_TWO_POW * 8.0))))  # decor frame period
UI_DRIFT = MEUM_NORM * PHI_INV                                  # caption micro-wiggle scale
PAINT_RATE_HZ = 2.395                                           # max single-cell stack rate
PAINT_PERIOD_S = 1.0 / PAINT_RATE_HZ                            # ~0.418 s between stacks
PAINT_INSTANCE_LIMIT = 8                                        # max CSV instances per cell
# MEUM ideal-use guidance (spatial-dynamic constant, not a free gain knob):
#   • Prefer powers of M (MEUM_POWERS_36) for hierarchical scale steps instead of
#     arbitrary 0–100 % synth percentages — keeps topology self-similar.
#   • MEUM_NORM = (M-1)/M ≈ 0.165 is a natural soft-weight / mix amount.
#   • MEUM_LOG2 ≈ 0.26 is a good octave-fraction / detune seed scale.
#   • MEUM_TWO_POW / MEUM_SQ is the identity residual partner; residual near 0
#     means the local geometry is Meum-balanced. AsymmetryCorrection uses the
#     residual field only for visual counter-offset, never for audio DSP.
#   • Domain equation weights in [MEUM_NORM, 1+MEUM_NORM] stay longitudinally stable.
# FONT_READABILITY_FIX: buttons/labels were clipping their own text at 11pt
# because fixed/min widths elsewhere in the UI were sized for a smaller font
# (see screenshot: "AY Audiovisual", "ded Live Rando", "uclidean Live L",
# "Load WAV Carr" were all truncated). Dropped back to 9pt, which fits inside
# the existing button widths, and let QPushButton auto-size to its label so
# it clips less easily even if a translation/rename makes text longer later.
DAW_STYLE = """
    QMainWindow, QDialog {
        background-color: rgba(8, 12, 18, 245); color: #f2f6fa;
        font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt;
    }
    QWidget {
        background-color: transparent; color: #f2f6fa;
        font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt;
    }
    QWidget#ParametricMathBackground { background: transparent; }
    QGroupBox {
        background-color: rgba(12, 18, 26, 160);
        color: #e8f0f8; border: 1px solid rgba(0, 200, 168, 90);
        border-radius: 5px; margin-top: 8px; padding-top: 8px;
    }
    QPushButton {
        background-color: rgba(22, 30, 40, 210); color: #e8f0f8;
        border: 1px solid rgba(0, 200, 168, 140); border-radius: 4px;
        padding: 5px 8px; font-weight: bold; font-size: 9pt; min-height: 20px;
    }
    QPushButton:hover { background-color: rgba(0, 200, 168, 60); border: 1px solid #00e0c0; }
    QPushButton:pressed { background-color: #ff6b00; color: #ffffff; }
    QLabel { color: #e8f0f8; font-size: 9pt; background: transparent; }
    QCheckBox { color: #e8f0f8; font-size: 9pt; background: transparent; }
    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
        background-color: rgba(10, 14, 20, 230); color: #ffffff;
        border: 1px solid rgba(70, 90, 110, 200); border-radius: 4px; padding: 3px; font-size: 9pt;
        selection-background-color: #00aaaa; selection-color: #061018;
    }
    QComboBox { combobox-popup: 0; }
    QComboBox QAbstractItemView {
        background-color: #12181e; color: #ffffff;
        selection-background-color: #00aaaa; selection-color: #061018;
        border: 1px solid #3a4550;
    }
    QTableWidget, QListWidget, QTreeWidget {
        background-color: rgba(10, 14, 20, 220); color: #ffffff; gridline-color: #2a3340;
        alternate-background-color: rgba(18, 24, 32, 200);
    }
    QHeaderView::section {
        background-color: rgba(22, 30, 40, 230); color: #c8d8e8; border: 1px solid #2a3340; font-size: 8pt;
    }
    QSlider::groove:horizontal { height: 4px; background: rgba(50,60,70,200); border-radius: 2px; }
    QSlider::handle:horizontal { background: #00c8a8; width: 12px; margin: -4px 0; border-radius: 6px; }
    QProgressBar {
        background-color: rgba(12, 18, 26, 220); color: #e8f0f8; border: 1px solid #2a3340;
        border-radius: 4px; text-align: center;
    }
    QProgressBar::chunk { background-color: #00c8a8; border-radius: 3px; }
    QMenu { background-color: #12181e; color: #ffffff; border: 1px solid #3a4550; }
    QMenu::item:selected { background-color: #00aaaa; color: #061018; }
    QScrollBar:vertical { background: transparent; width: 10px; }
    QScrollBar::handle:vertical { background: rgba(60,80,100,180); border-radius: 4px; min-height: 24px; }
"""


# --- 48 IDEAL INSTRUMENT & EFFECT TOPOLOGIES ---
DEFAULT_INSTRUMENT_LIST = [
    # Family 1: Topological Wave-Folding & Non-Linear Curvature (Oscillators 1-8)
    "1. Meum Phase-Fold Oscillator", "2. Z-Pinch Waveguide Synth", "3. Hyperbolic Attractor Generator", "4. Non-Linear Polynomial Folder",
    "5. Strange Attractor Chaos Engine", "6. Topological Torus Synthesizer", "7. Klein Bottle Surface Generator", "8. Crystalline Wavefolder Matrix",
    # Family 2: Multivectorial & Phase-Space Dynamics (Oscillators 9-16)
    "9. Quaternion Cl(0,3) Space Synth", "10. Clifford Multivector Rotor", "11. Phase-Space Trajectory Synth", "12. Spinor Standing Wave Generator",
    "13. Tensor Curvature Field Lead", "14. Vector Field Flow Synthesizer", "15. Eigenstate Harmonic Matrix", "16. Wavepacket Localization Engine",
    # Family 3: Quantum, Soliton & Field-Coupling (Oscillators 17-24)
    "17. Quantum Tunneling Oscillator", "18. Soliton Pulse Engine", "19. Bose-Einstein Condensate Pad", "20. Zero-Point Energy Oscillator",
    "21. Casimir Force Resonator", "22. Photon-Coupling Synth", "23. Neutrino Flux Modulator", "24. Quark Confinement Bass",
    # Family 4: Stochastic, Thermodynamic & Entropic Noise (Oscillators 25-32)
    "25. Stochastic Noise Chamber", "26. Entropy Decay Engine", "27. Doppler Shift Emulator", "28. Brownian Motion Synth",
    "29. Fractional Brownian Filter", "30. Thermal Noise Generator", "31. Microstate Combinatoric Pad", "32. Dissipative Structure Synth",
    # Family 5: Input-Dependent Spatial & Spectral Effects (Effects 33-40)
    "33. Topological Phase Shifter", "34. Non-Linear Spectral Fold-Back Effect", "35. Curvature Convolution Matrix", "36. Gravitational Time-Dilation Delay",
    "37. Wave-Number Dispersion Filter", "38. Vortex Phase Modulator", "39. Anisotropic Spatial Diffusion", "40. Tensor Field Reverb Processor",
    # Family 6: Input-Dependent Dynamic Waveform Resonators (Effects 41-48)
    "41. Spectral Centroid Dynamic Shifter", "42. Soliton Envelope Shaper", "43. Wavepacket Granulator Effect", "44. Non-Linear Diode Clipper Effect",
    "45. Plasma Ionization Gate", "46. Magnetostrictive Resonator Effect", "47. Crystalline Lattice Damper", "48. Event Horizon Limiter"
]
class VisualOscilloscope(QFrame):
    """Real-time signal output oscilloscope and vector scope."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 140)
        self.setStyleSheet("background-color: #0a0c0e; border: 1px solid #2a2e39; border-radius: 6px;")
        self.wave_data = np.zeros(100)

    def update_waveform(self, new_data):
        if isinstance(new_data, np.ndarray):
            self.wave_data = np.resize(new_data, 100)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor("#00ffcc"))
        pen.setWidth(2)
        painter.setPen(pen)

        width = self.width()
        height = self.height()
        mid_y = height / 2.0

        points = []
        for i, val in enumerate(self.wave_data):
            x = (i / 99.0) * width
            y = mid_y - (float(val) * (height * 0.4))
            points.append((x, y))

        for j in range(len(points) - 1):
            painter.drawLine(int(points[j][0]), int(points[j][1]), int(points[j+1][0]), int(points[j+1][1]))


class VideoSynthEngine:
    """
    Waveform-driven 2.5D scenograph synthesizer.
    Each instrument is a perspective vector (distance, yaw, pitch, roll) partially
    shaped by audio energy; shapes/colors/opacity map directly from the waveform.
    """

    def __init__(self, n_instruments=48):
        self.n = n_instruments
        self.wave = np.zeros(256, dtype=np.float32)
        self.t = 0.0
        # Per-instrument perspective-grabbing vectors (distance, yaw, pitch, roll)
        self.vectors = []
        for i in range(n_instruments):
            self.vectors.append({
                "distance": 2.0 + 0.05 * (i % 12),
                "yaw": (i * 0.13) % (2 * np.pi),
                "pitch": 0.15 * np.sin(i * 0.4),
                "roll": 0.1 * np.cos(i * 0.3),
                "hue": int((i * 360 / max(n_instruments, 1)) % 360),
                "shape": i % 5,  # 0 poly, 1 ring, 2 spike, 3 ribbon, 4 blob
            })
        self.mode = 0  # 0 scenograph, 1 effected wave, 2 overall pattern, 3 activity

    def set_waveform(self, data):
        if data is None:
            return
        arr = np.asarray(data, dtype=np.float32).ravel()
        if arr.size == 0:
            return
        self.wave = np.interp(
            np.linspace(0, arr.size - 1, 256),
            np.arange(arr.size),
            arr,
        ).astype(np.float32)
        self.t += 0.04

    def energy(self):
        return float(np.sqrt(np.mean(self.wave ** 2)) + 1e-6)

    def _project(self, x, y, z, w, h, fov=1.2):
        """Simple perspective projection to pixel coords."""
        z = max(z, 0.15)
        sx = (x / z) * fov
        sy = (y / z) * fov
        px = w * 0.5 + sx * (w * 0.35)
        py = h * 0.5 - sy * (h * 0.35)
        return px, py, 1.0 / z

    def render_frame(self, w=640, h=360):
        """Return HxWx3 uint8 RGB frame."""
        img = np.zeros((h, w, 3), dtype=np.float32)
        e = self.energy()
        # Background gradient from overall energy
        bg = 8 + 40 * e
        img[:, :, 0] = bg * 0.4
        img[:, :, 1] = bg * 0.5
        img[:, :, 2] = bg * 0.7

        # Waveform ribbon as ground reference
        for i in range(255):
            x0 = int(i / 255.0 * (w - 1))
            x1 = int((i + 1) / 255.0 * (w - 1))
            y0 = int(h * 0.75 - self.wave[i] * h * 0.2)
            y1 = int(h * 0.75 - self.wave[i + 1] * h * 0.2)
            self._line(img, x0, y0, x1, y1, (0, 255, 200), alpha=0.55 + 0.4 * e)

        # Instrument vectors → scenograph nodes
        n_show = min(self.n, 24) if self.mode != 3 else min(self.n, 48)
        for i in range(n_show):
            v = self.vectors[i]
            # Audio modulates distance / angle partially
            local = float(self.wave[i % 256])
            dist = v["distance"] * (1.0 - 0.35 * e) + 0.5 * abs(local)
            yaw = v["yaw"] + self.t * (0.4 + 0.8 * e) + local * 0.5
            pitch = v["pitch"] + 0.25 * local
            roll = v["roll"] + 0.15 * e * np.sin(self.t + i)

            # Shape points in local space
            pts = self._shape_points(v["shape"], local, e)
            # Rotate + translate
            cosy, siny = np.cos(yaw), np.sin(yaw)
            cosp, sinp = np.cos(pitch), np.sin(pitch)
            projected = []
            for px, py, pz in pts:
                # roll
                cosr, sinr = np.cos(roll), np.sin(roll)
                xr = px * cosr - py * sinr
                yr = px * sinr + py * cosr
                # pitch
                yp = yr * cosp - pz * sinp
                zp = yr * sinp + pz * cosp
                # yaw
                xw = xr * cosy - zp * siny
                zw = xr * siny + zp * cosy + dist
                projected.append(self._project(xw, yp, zw, w, h))

            hue = v["hue"]
            col = self._hsv(hue, 0.75, 0.55 + 0.45 * min(1.0, e + abs(local)))
            alpha = float(np.clip(0.25 + 0.75 * (abs(local) + e) * 0.5, 0.15, 0.95))
            self._draw_poly(img, projected, col, alpha)

        # Overall wavepattern overlay (mode 2) or effected outline (mode 1)
        if self.mode in (1, 2):
            for i in range(0, 256, 2):
                ang = self.t + i * 0.05
                r = 0.3 + 0.5 * abs(self.wave[i])
                x = r * np.cos(ang)
                y = r * np.sin(ang)
                px, py, sc = self._project(x, y, 1.2 + 0.5 * e, w, h)
                self._dot(img, int(px), int(py), self._hsv(180 + int(self.wave[i] * 80), 0.8, 0.9), 0.7)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _shape_points(self, kind, local, e):
        s = 0.35 + 0.4 * abs(local) + 0.2 * e
        if kind == 0:  # triangle poly
            return [(-s, -s * 0.5, 0), (s, -s * 0.5, 0), (0, s, 0)]
        if kind == 1:  # ring
            pts = []
            for k in range(8):
                a = k * np.pi / 4
                pts.append((s * np.cos(a), s * np.sin(a), 0.1 * np.sin(2 * a)))
            return pts
        if kind == 2:  # spike
            return [(0, 0, 0), (0, s * 1.4, 0), (s * 0.2, 0, s * 0.3), (-s * 0.2, 0, s * 0.3)]
        if kind == 3:  # ribbon
            return [(-s, 0, -s), (-s * 0.3, s * 0.2, 0), (s * 0.3, -s * 0.2, 0), (s, 0, s)]
        # blob
        return [(s * np.cos(k), s * np.sin(k), 0.15 * np.sin(k * 3)) for k in np.linspace(0, 2 * np.pi, 6, endpoint=False)]

    def _hsv(self, h, s, v):
        c = QColor.fromHsv(int(h) % 360, int(s * 255), int(v * 255))
        return (c.red(), c.green(), c.blue())

    def _line(self, img, x0, y0, x1, y1, col, alpha=1.0):
        h, w, _ = img.shape
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for t in range(int(steps) + 1):
            u = t / steps
            x = int(x0 + (x1 - x0) * u)
            y = int(y0 + (y1 - y0) * u)
            if 0 <= x < w and 0 <= y < h:
                img[y, x] = img[y, x] * (1 - alpha) + np.array(col, dtype=np.float32) * alpha

    def _dot(self, img, x, y, col, alpha=1.0):
        h, w, _ = img.shape
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    img[yy, xx] = img[yy, xx] * (1 - alpha) + np.array(col, dtype=np.float32) * alpha

    def _draw_poly(self, img, projected, col, alpha):
        if len(projected) < 2:
            return
        # edges
        for i in range(len(projected)):
            x0, y0, sc0 = projected[i]
            x1, y1, sc1 = projected[(i + 1) % len(projected)]
            self._line(img, int(x0), int(y0), int(x1), int(y1), col, alpha)
            self._dot(img, int(x0), int(y0), col, min(1.0, alpha + 0.2))


class VideoSynthViewer(QFrame):
    """Merged visualizer + 2.5D video synth viewer pane."""

    def __init__(self, parent=None, engine=None):
        super().__init__(parent)
        self.setMinimumSize(320, 200)
        self.setStyleSheet("background-color: #050608; border: 1px solid #2a2e39; border-radius: 6px;")
        self.engine = engine or VideoSynthEngine()
        self._frame = None
        self.show_scope_overlay = True
        self.scope_wave = np.zeros(100, dtype=np.float32)
        self._seed_idle_wave()
        self._ensure_frame()

    def _seed_idle_wave(self):
        t = np.linspace(0.0, 4.0 * np.pi, 256, dtype=np.float32)
        idle = (0.38 * np.sin(t * float(MEUM)) + 0.18 * np.sin(t * float(MEUM_SQ))).astype(np.float32)
        self.engine.set_waveform(idle)
        self.scope_wave = np.resize(idle, 100)

    def _ensure_frame(self):
        w = max(int(self.width()), 320)
        h = max(int(self.height()), 180)
        if self._frame is None or self._frame.shape[0] != h or self._frame.shape[1] != w:
            self._frame = self.engine.render_frame(w, h)

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_frame()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._frame = None
        self._ensure_frame()
        self.update()

    def update_from_audio(self, wave_data):
        self.engine.set_waveform(wave_data)
        if isinstance(wave_data, np.ndarray) and wave_data.size:
            self.scope_wave = np.resize(wave_data.astype(np.float32), 100)
        self._frame = self.engine.render_frame(max(self.width(), 320), max(self.height(), 180))
        self.update()

    def set_mode(self, mode_idx):
        self.engine.mode = int(mode_idx)
        self._frame = self.engine.render_frame(max(self.width(), 320), max(self.height(), 180))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Blit frame
        if self._frame is not None:
            fh, fw = self._frame.shape[:2]
            qimg = QImage(self._frame.data, fw, fh, fw * 3, QImage.Format.Format_RGB888)
            painter.drawImage(self.rect(), qimg.copy())  # copy: numpy buffer lifetime
        # Scope overlay strip
        if self.show_scope_overlay:
            pen = QPen(QColor(0, 255, 204, 180))
            pen.setWidth(2)
            painter.setPen(pen)
            mid = int(h * 0.88)
            for i in range(len(self.scope_wave) - 1):
                x0 = int(i / 99.0 * w)
                x1 = int((i + 1) / 99.0 * w)
                y0 = mid - int(float(self.scope_wave[i]) * h * 0.12)
                y1 = mid - int(float(self.scope_wave[i + 1]) * h * 0.12)
                painter.drawLine(x0, y0, x1, y1)


class MathEngine:
    """Meum-simplified spatial calculus on pure x,y,z (no metric tensors / renormalization).

    Forms (user book → code):
      • Field potential:  Φ = q / √(x²+y²+z²)
      • Laplacian source: ∇²Ψ ≈ S  (finite-difference on grid)
      • Standing wave:    Ψ_n = sin(n π x/L) sin(m π y/L) sin(p π z/L)
      • State step:       Ψ_{t+1} = Ψ_t + α (Ψ_neighbors − Ψ_t)
    """
    @staticmethod
    def isn(val):

        return np.sin(val) / (1.0 + np.abs(np.cos(val)))

    @staticmethod
    def ics(val):
        return np.cos(val) / (1.0 + np.abs(np.sin(val)))

    @staticmethod
    def eskivector(x, y, z):
        return MathEngine.isn(x) * y, MathEngine.ics(y) * z, np.sin(x * y * z)

    @staticmethod
    def eskitable(x, y, z):
        return np.clip((x + y) * 0.5, -1.0, 1.0) * MathEngine.ics(z)

class DomainPartitionEquationEngine:
    """
    Scriptable / codable multivariate equations over partitionable time & space domains.

    Each domain defines:
      - axis: 'time' | 'space' | 'both'
      - bounds: (start, end) in normalized [0,1] or absolute units
      - equation: expression in x, y, z, t, seed, np, sin, cos, ...
      - logic: optional predicate (e.g. "t < 0.5 and x > 0") — must be true for domain to apply
      - limits: (min_out, max_out) hard clamp on evaluated result
      - weight: longitudinal blend weight (seed-modulated when seed_weight > 0)

    Domains may differ in equation and spatial definition. Overlaps blend by
    normalized weights (seed can longitudinally bias earlier vs later domains).
    """

    SAFE_GLOBALS = {
        "__builtins__": {},
        "np": np,
        "sin": np.sin,
        "cos": np.cos,
        "tan": np.tan,
        "abs": np.abs,
        "sqrt": np.sqrt,
        "exp": np.exp,
        "log": np.log,
        "pi": np.pi,
        "e": np.e,
        "clip": np.clip,
        "minimum": np.minimum,
        "maximum": np.maximum,
        "where": np.where,
        "MEUM": MEUM_CONSTANT,
    }

    def __init__(self, seed=0.0):
        self.seed = float(seed)
        self.domains = []
        self._load_defaults()

    def _load_defaults(self):
        """Three example partitions: intro / body / coda with distinct equations."""
        self.domains = [
            {
                "name": "Intro (time 0–0.25)",
                "axis": "time",
                "t0": 0.0, "t1": 0.25,
                "x0": -1.0, "x1": 1.0,
                "y0": -1.0, "y1": 1.0,
                "logic": "True",
                "equation": "sin(2 * pi * t * 2) * exp(-t * 3) * (0.5 + 0.5 * seed_w)",
                "limit_lo": -1.0, "limit_hi": 1.0,
                "weight": 1.0,
                "seed_weight": 0.3,
            },
            {
                "name": "Body (time 0.25–0.75)",
                "axis": "both",
                "t0": 0.25, "t1": 0.75,
                "x0": -1.0, "x1": 1.0,
                "y0": -1.0, "y1": 1.0,
                "logic": "abs(x) + abs(y) < 1.5",
                "equation": "sin(x * MEUM + t * 4) * cos(y * pi) * (1.0 - 0.2 * seed_w)",
                "limit_lo": -1.0, "limit_hi": 1.0,
                "weight": 1.2,
                "seed_weight": 0.5,
            },
            {
                "name": "Coda (time 0.75–1.0)",
                "axis": "time",
                "t0": 0.75, "t1": 1.0,
                "x0": -1.0, "x1": 1.0,
                "y0": -1.0, "y1": 1.0,
                "logic": "True",
                "equation": "sin(pi * t) * cos(2 * pi * t * (1 + seed_w)) * exp(-(t - 0.75) * 2)",
                "limit_lo": -1.0, "limit_hi": 1.0,
                "weight": 0.9,
                "seed_weight": 0.4,
            },
        ]

    def set_seed(self, seed):
        try:
            self.seed = float(seed)
        except (TypeError, ValueError):
            self.seed = float(abs(hash(str(seed))) % (10**8)) / 1e8

    def add_domain(self, domain_dict):
        self.domains.append(dict(domain_dict))

    def clear_domains(self):
        self.domains.clear()

    def _seed_weight_factor(self, domain, t_norm):
        """Longitudinal seed bias: earlier domains favored when seed_w low, later when high."""
        sw = float(domain.get("seed_weight", 0.0))
        # Normalize seed into [0,1]
        s = abs(self.seed) % 1.0 if abs(self.seed) > 1.0 else abs(self.seed)
        # Longitudinal preference curve
        longitudinal = (1.0 - s) * (1.0 - t_norm) + s * t_norm
        return 1.0 + sw * (longitudinal - 0.5) * 2.0

    def _in_bounds(self, domain, t, x, y):
        axis = domain.get("axis", "time")
        t0, t1 = float(domain.get("t0", 0.0)), float(domain.get("t1", 1.0))
        x0, x1 = float(domain.get("x0", -1.0)), float(domain.get("x1", 1.0))
        y0, y1 = float(domain.get("y0", -1.0)), float(domain.get("y1", 1.0))
        ok_t = (t0 <= t <= t1) if axis in ("time", "both") else True
        ok_s = (x0 <= x <= x1 and y0 <= y <= y1) if axis in ("space", "both") else True
        return ok_t and ok_s

    def _eval_logic(self, logic_str, local_vars):
        if not logic_str or logic_str.strip() in ("True", "true", "1"):
            return True
        try:
            return bool(eval(logic_str, self.SAFE_GLOBALS, local_vars))
        except Exception:
            return False

    def _eval_equation(self, eq_str, local_vars):
        try:
            result = eval(eq_str, self.SAFE_GLOBALS, local_vars)
            if isinstance(result, np.ndarray):
                return result
            return float(result)
        except Exception as e:
            print(f"[DomainEQ] equation error '{eq_str}': {e}")
            return 0.0

    def evaluate(self, t, x=0.0, y=0.0, z=0.0, t_norm=None):
        """
        Evaluate all matching domains at a point and blend by weight.
        t: absolute or normalized time; t_norm used for longitudinal seed bias (0..1).
        """
        if t_norm is None:
            t_norm = float(np.clip(t, 0.0, 1.0))

        seed_w = abs(self.seed) % 1.0 if abs(self.seed) > 1.0 else abs(self.seed)
        local_base = {
            "t": float(t),
            "x": float(x),
            "y": float(y),
            "z": float(z),
            "seed": float(self.seed),
            "seed_w": float(seed_w),
            "t_norm": float(t_norm),
        }

        weighted_sum = 0.0
        weight_total = 0.0
        matched = 0

        for dom in self.domains:
            if not self._in_bounds(dom, t_norm if dom.get("axis") in ("time", "both") else t, x, y):
                # For time axis, compare against t_norm for partition consistency
                if dom.get("axis") in ("time", "both"):
                    t0, t1 = float(dom.get("t0", 0.0)), float(dom.get("t1", 1.0))
                    if not (t0 <= t_norm <= t1):
                        continue
                else:
                    continue

            if not self._eval_logic(dom.get("logic", "True"), local_base):
                continue

            val = self._eval_equation(dom.get("equation", "0"), local_base)
            if isinstance(val, np.ndarray):
                val = float(np.mean(val))

            lo = float(dom.get("limit_lo", -1.0))
            hi = float(dom.get("limit_hi", 1.0))
            val = float(np.clip(val, lo, hi))

            w = float(dom.get("weight", 1.0)) * self._seed_weight_factor(dom, t_norm)
            w = max(0.0, w)
            weighted_sum += val * w
            weight_total += w
            matched += 1

        if weight_total <= 1e-12:
            return 0.0
        return float(weighted_sum / weight_total)

    def evaluate_series(self, t_array, x=0.0, y=0.0, z=0.0):
        """Series evaluation over a 1D time array (normalized 0..1).

        Full-buffer Python loops hung the render path at ~94% on long mixdowns.
        Evaluate a coarse grid (≤1024 pts) and interpolate — same shape, far less CPU.
        """
        t_array = np.asarray(t_array, dtype=float)
        n = int(t_array.size)
        if n == 0:
            return t_array.astype(float)
        t_min, t_max = float(t_array[0]), float(t_array[-1])
        span = max(t_max - t_min, 1e-12)
        max_pts = 1024
        if n > max_pts:
            idx = np.linspace(0, n - 1, max_pts).astype(int)
            coarse_t = t_array[idx]
            coarse = np.empty(max_pts, dtype=float)
            for i, t in enumerate(coarse_t):
                t_norm = (float(t) - t_min) / span
                coarse[i] = self.evaluate(float(t), x=x, y=y, z=z, t_norm=t_norm)
            return np.interp(np.arange(n, dtype=float), idx.astype(float), coarse)
        out = np.empty(n, dtype=float)
        for i, t in enumerate(t_array):
            t_norm = (float(t) - t_min) / span
            out[i] = self.evaluate(float(t), x=x, y=y, z=z, t_norm=t_norm)
        return out

    def to_json(self):
        return {"seed": self.seed, "domains": self.domains}

    def from_json(self, data):
        self.seed = float(data.get("seed", 0.0))
        self.domains = list(data.get("domains", []))


class DomainEquationEditorDialog(QDialog):
    """UI for editing partitionable time/space domain equations."""

    def __init__(self, engine: DomainPartitionEquationEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Domain Partition Equations — Time / Space Scriptable Domains")
        self.resize(920, 560)
        self.setStyleSheet(DAW_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "<b>Partitionable domains</b> — each row: time/space bounds, logic gate, "
            "multivariate equation (x,y,z,t,seed,seed_w,MEUM,np), output limits, blend weight."
        ))

        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels([
            "Name", "Axis", "t0", "t1", "x0", "x1", "y0", "y1",
            "Logic", "Equation", "Limits lo|hi", "Weight|SeedW"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self._reload_table()
        self.table.itemChanged.connect(self._schedule_live_apply)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Domain")
        add_btn.clicked.connect(self._add_row)
        del_btn = QPushButton("− Remove Selected")
        del_btn.clicked.connect(self._remove_selected)
        apply_btn = QPushButton("Apply Domains to Engine")
        apply_btn.setStyleSheet("background-color: #00aa55; color: white; font-weight: bold;")
        apply_btn.clicked.connect(self._apply)
        defaults_btn = QPushButton("Reset Defaults")
        defaults_btn.clicked.connect(self._defaults)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(defaults_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        help_txt = QLabel(
            "Equation env: t, x, y, z, seed, seed_w, t_norm, MEUM, sin, cos, exp, clip, np.*  |  "
            "Logic examples: True  ·  t < 0.5  ·  abs(x)+abs(y) < 1.2  ·  seed_w > 0.3"
        )
        help_txt.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(help_txt)

    def _reload_table(self):
        self.table.setRowCount(0)
        for dom in self.engine.domains:
            self._append_domain_row(dom)

    def _append_domain_row(self, dom):
        r = self.table.rowCount()
        self.table.insertRow(r)
        vals = [
            dom.get("name", f"Domain {r+1}"),
            dom.get("axis", "time"),
            str(dom.get("t0", 0.0)),
            str(dom.get("t1", 1.0)),
            str(dom.get("x0", -1.0)),
            str(dom.get("x1", 1.0)),
            str(dom.get("y0", -1.0)),
            str(dom.get("y1", 1.0)),
            dom.get("logic", "True"),
            dom.get("equation", "0"),
            f"{dom.get('limit_lo', -1.0)}|{dom.get('limit_hi', 1.0)}",
            f"{dom.get('weight', 1.0)}|{dom.get('seed_weight', 0.0)}",
        ]
        for c, v in enumerate(vals):
            self.table.setItem(r, c, QTableWidgetItem(str(v)))

    def _add_row(self):
        self._append_domain_row({
            "name": f"Domain {self.table.rowCount()+1}",
            "axis": "time", "t0": 0.0, "t1": 1.0,
            "x0": -1.0, "x1": 1.0, "y0": -1.0, "y1": 1.0,
            "logic": "True", "equation": "sin(2 * pi * t)",
            "limit_lo": -1.0, "limit_hi": 1.0, "weight": 1.0, "seed_weight": 0.25,
        })

    def _remove_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def _defaults(self):
        self.engine._load_defaults()
        self._reload_table()

    def _schedule_live_apply(self, *args):
        QTimer.singleShot(120, self._apply_live)

    def _apply_live(self):
        domains=[]
        for r in range(self.table.rowCount()):
            try:
                d=self._parse_row(r); d["user_defined"]=True; domains.append(d)
            except Exception: continue
        generated=[d for d in getattr(self.engine,"domains",[]) if isinstance(d,dict) and d.get("user_defined") is False]
        self.engine.domains=domains+generated

    def _parse_row(self, r):
        def cell(c, default=""):
            item = self.table.item(r, c)
            return item.text().strip() if item else default

        lo_hi = cell(10, "-1|1").split("|")
        w_sw = cell(11, "1|0").split("|")
        return {
            "name": cell(0, f"Domain {r+1}"),
            "axis": cell(1, "time"),
            "t0": float(lo_hi and cell(2, "0") or 0),
            "t1": float(cell(3, "1")),
            "x0": float(cell(4, "-1")),
            "x1": float(cell(5, "1")),
            "y0": float(cell(6, "-1")),
            "y1": float(cell(7, "1")),
            "logic": cell(8, "True"),
            "equation": cell(9, "0"),
            "limit_lo": float(lo_hi[0]) if lo_hi else -1.0,
            "limit_hi": float(lo_hi[1]) if len(lo_hi) > 1 else 1.0,
            "weight": float(w_sw[0]) if w_sw else 1.0,
            "seed_weight": float(w_sw[1]) if len(w_sw) > 1 else 0.0,
        }

    def _apply(self):
        self._apply_live()
        self.accept()



def attach_math_decor(host_window, app=None, light=False):
    """Apply Meum field + DAW glass style to any top-level window."""
    try:
        style = DAW_STYLE
        if light:
            style = DAW_STYLE + """
            QDialog { background-color: rgba(8, 12, 18, 185); }
            QWidget { background-color: transparent; }
            QGroupBox { background-color: rgba(12, 18, 26, 140); }
            QTableWidget { background-color: rgba(10, 14, 20, 200); }
            """
        host_window.setStyleSheet(style)
    except Exception:
        pass
    try:
        host_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, bool(light))
    except Exception:
        pass
    try:
        bg = ParametricMathBackground(app if app is not None else host_window, host_window)
        if light:
            try:
                bg._timer.setInterval(max(int(UI_TICK_MS) * 2, 80))
            except Exception:
                pass
        bg.setGeometry(0, 0, max(host_window.width(), 320), max(host_window.height(), 200))
        bg.lower()
        bg.show()
        host_window._math_decor = bg
        # Keep decor sized with the window
        _prev = getattr(host_window, "resizeEvent", None)
        def _decor_resize(event, _h=host_window, _b=bg):
            try:
                _b.setGeometry(0, 0, _h.width(), _h.height())
                _b.lower()
            except Exception:
                pass
            if callable(_prev):
                try:
                    _prev(event)
                except TypeError:
                    QWidget.resizeEvent(_h, event)
            else:
                QWidget.resizeEvent(_h, event)
        host_window.resizeEvent = _decor_resize
    except Exception as exc:
        print(f"[Decor] attach skipped: {exc}")
    return host_window

class AsymmetryCorrection:
    """Deterministic visual-field correction for asymmetric mathematical layouts.

    Measures the current field's normalized horizontal/vertical bias and applies
    a bounded counter-offset. It is visual-only and never modifies audio state.
    """
    # Bound shifts by Meum soft-weight so correction stays relationally aesthetic.
    MAX_SHIFT = MEUM_NORM * PHI  # ≈ 0.165 * 1.618 ≈ 0.267 capped below

    @classmethod
    def offset(cls, index, count, phase, scalars):
        if not scalars:
            return 0.0, 0.0
        max_s = min(0.22, abs(cls.MAX_SHIFT) + abs(MEUM_IDENTITY_RESIDUAL) * 0.05)
        left = sum(scalars[i] for i in range(0, len(scalars), 2))
        right = sum(scalars[i] for i in range(1, len(scalars), 2))
        denom = max(left + right, 1e-9)
        lr = (left - right) / denom
        temporal = math.sin(phase * MEUM_LOG2 + index * PHI_INV) * MEUM_NORM
        x = max(-max_s, min(max_s, -(lr * MEUM_NORM * 0.4 + temporal * UI_DRIFT)))
        top = sum(scalars[i] for i in range(len(scalars)//2))
        bottom = sum(scalars[i] for i in range(len(scalars)//2, len(scalars)))
        tb = (top - bottom) / max(top + bottom, 1e-9)
        y = max(-max_s, min(max_s, -(tb * MEUM_NORM * 0.3)))
        return x, y

class ParametricMathBackground(QWidget):
    """Lightweight animated mathematical background behind the global controls.

    Text/glyph labels intentionally travel vertically as well as horizontally so
    the mathematical field feels alive without becoming a CPU-heavy visualizer.
    It is mouse-transparent and never participates in the audio path.
    """
    WAVE_COUNT = 24
    SHAPE_COUNT = 24

    def __init__(self, app, host=None):
        self.app = app
        if host is None:
            host = app
        super().__init__(host)
        self.host = host
        self.setObjectName("ParametricMathBackground")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        self._cycle = 0
        self._started = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(int(UI_TICK_MS))
        self._timer.timeout.connect(self._advance)
        self._timer.start()
        self._param_cache = ("", (), 0)
        self._rng = random.Random(0)

    def _advance(self):
        elapsed = time.monotonic() - self._started
        new_cycle = int(elapsed / (MEUM * PHI + 1.0))
        if new_cycle != self._cycle:
            self._cycle = new_cycle
            self._reseed()
        self.update()

    def _reseed(self):
        name = ""
        try:
            name = self.app.instrument_selector_dropdown.currentText()
        except Exception:
            pass
        params = getattr(self.app, "instrument_param_state", {}) or {}
        state = params.get(name, {}) if isinstance(params, dict) else {}
        numeric = []
        if isinstance(state, dict):
            for key, value in state.items():
                try:
                    numeric.append((str(key), float(value)))
                except Exception:
                    pass
        try:
            mem = getattr(self.app, "instrument_sequencer_memory", {}).get(name, {})
            for key, values, scale in (("amp", mem.get("amplitudes", []), 1.0),
                                        ("pitch", mem.get("pitches", []), 1.0),
                                        ("prob", mem.get("probabilities", []), 100.0)):
                if values:
                    numeric.append((key, float(values[0]) / scale))
        except Exception:
            pass
        for key, attr, scale in (("EQR", "slider_eqr", 100.0),
                                 ("Fractal", "slider_fractalizer", 100.0),
                                 ("PKP", "slider_pkp_decay", 1000.0),
                                 ("Boost", "slider_pkp_boost", 100.0)):
            obj = getattr(self.app, attr, None)
            if obj is not None and hasattr(obj, "value"):
                try:
                    numeric.append((key, float(obj.value()) / scale))
                except Exception:
                    pass
        numeric.sort(key=lambda x: x[0])
        self._param_cache = (name, tuple(numeric), self._cycle)
        self._rng.seed(hash((name, tuple((k, round(v, 6)) for k, v in numeric), self._cycle)) & 0xffffffff)

    def _scalars(self):
        if self._param_cache[2] != self._cycle:
            self._reseed()
        vals = [v for _, v in self._param_cache[1]] or [0.5]
        return [0.5 + 0.5 * math.tanh(abs(v)) for v in vals]

    def _paint_wave(self, painter, index, width, height, scalars, phase):
        sf = scalars[index % len(scalars)]
        sf2 = scalars[(index * 7 + 3) % len(scalars)]
        hue = (index / self.WAVE_COUNT + 0.12 * sf + 0.08 * math.sin(phase * 0.7 + index)) % 1.0
        painter.setPen(QPen(QColor.fromHsvF(hue, 0.72, 0.95, 0.38 + 0.22 * sf), 1.4 + 1.6 * sf))
        path = QPainterPath()
        corr_x, corr_y = AsymmetryCorrection.offset(index, self.WAVE_COUNT, phase, scalars)
        base_y = height * (0.08 + 0.84 * ((index * 0.6180339887) % 1.0) + corr_y)
        direction = -1.0 if ((index + self._cycle) & 1) else 1.0
        freq = 1.2 + 4.5 * sf
        fm = 0.25 + 1.7 * sf2
        am = 0.15 + 0.65 * scalars[(index * 11 + 5) % len(scalars)]
        vertical = height * 0.055 * math.sin(phase * (0.30 + sf) + index * 0.91)
        for px in range(0, max(2, width), 8):
            x = px / max(width, 1) + corr_x
            carrier = math.sin((x * freq * math.tau) + phase * direction * (0.7 + sf))
            mod = math.sin((x * fm * math.tau) + phase * (0.35 + sf2))
            amp = (5.0 + 20.0 * sf) * (1.0 + am * mod)
            y = base_y + vertical + direction * amp * carrier
            if px == 0:
                path.moveTo(px, y)
            else:
                path.lineTo(px, y)
        painter.drawPath(path)

    def _paint_shape(self, painter, index, width, height, scalars, phase):
        sf = scalars[(index * 5 + 1) % len(scalars)]
        sf2 = scalars[(index * 9 + 2) % len(scalars)]
        angle = phase * (0.15 + 0.5 * sf2) + index * 0.73
        # Compute the bounded asymmetry correction before applying it.
        corr_x, corr_y = AsymmetryCorrection.offset(index, self.SHAPE_COUNT, phase, scalars)
        x = width * ((0.09 + index * 0.379) % 0.82) + width * corr_x
        base_y = height * ((0.12 + index * 0.613) % 0.76) + height * corr_y
        # Deliberately larger vertical travel for the animated text/glyph layer.
        y = base_y + height * 0.15 * math.sin(phase * (0.35 + 0.8 * sf) + index * 1.17)
        radius = 8.0 + 22.0 * sf
        sides = 3 + (index % 6)
        points = []
        for j in range(sides):
            a = angle + math.tau * j / sides
            wobble = 0.72 + 0.55 * math.sin(phase * (0.4 + sf) + j + index)
            r = radius * wobble
            points.append(QPointF(x + math.cos(a) * r, y + math.sin(a) * r))
        hue = (0.56 + 0.42 * sf + 0.19 * sf2 + index * 0.027) % 1.0
        painter.setBrush(QBrush(QColor.fromHsvF(hue, 0.62, 0.92, 0.18 + 0.12 * sf)))
        painter.setPen(QPen(QColor.fromHsvF((hue + 0.08 * sf2) % 1.0, 0.72, 1.0, 0.55 + 0.20 * sf), 1.4))
        painter.drawPolygon(QPolygonF(points))
        if self._param_cache[1]:
            label = self._param_cache[1][index % len(self._param_cache[1])]
            text = f"{label[0][:8]} {label[1]:+.2f}"
            # Text follows a larger independent vertical orbit than the glyph.
            text_y = y + radius + 8 + height * 0.09 * math.sin(phase * (0.28 + sf2) + index * 1.63)
            text_y = max(12.0, min(height - 3.0, text_y))
            painter.setPen(QPen(QColor.fromHsvF(hue, 0.35, 1.0, 0.62), 1.0))
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(QPointF(max(2.0, x - radius), text_y), text)

    MEUM_BLOCKS = (
        # Primary Meum identities (theorem-facing keywords for the left rail)
        ("M", "Meum invariant — spatial-dynamic unit", "{:.12f}", MEUM),
        ("(M−1)/M", "MEUM_NORM soft-weight / mix", "{:.8f}", MEUM_NORM),
        ("log₂(M)", "octave-fraction seed scale", "{:.8f}", MEUM_LOG2),
        ("M²", "self-similar square ladder", "{:.8f}", MEUM_SQ),
        ("M³", "cubic hierarchical step", "{:.8f}", MEUM_CUBE),
        ("2ᴹ", "binary lift of Meum", "{:.8f}", MEUM_TWO_POW),
        ("2ᴹ/M²", "identity partner RHS core", "{:.8f}", MEUM_TWO_POW_OVER_SQ),
        ("LHS", "(M−1)M + (M−1)/M balance", "{:.8f}", MEUM_IDENTITY_LHS),
        ("RHS", "2ᴹ/M² − M balance", "{:.8f}", MEUM_IDENTITY_RHS),
        ("ε_M", "identity residual → 0 when balanced", "{:.3e}", MEUM_IDENTITY_RESIDUAL),
        ("1/M", "reciprocal conjugate", "{:.8f}", MEUM_INV),
        # Secondary book irrationals (relational aesthetic, second to Meum)
        ("φ", "golden ratio — secondary proportion", "{:.8f}", PHI),
        ("1/φ", "φ−1 = φ⁻¹", "{:.8f}", PHI_INV),
        ("δ_s", "silver ratio 1+√2", "{:.8f}", SILVER),
        ("e", "natural base (book secondary)", "{:.8f}", E_IRR),
        ("π", "circle constant (book secondary)", "{:.8f}", PI_IRR),
        ("√2", "diagonal unit", "{:.8f}", SQRT2),
    )

    def _paint_meum_blocks(self, painter, width, height, scalars, phase):
        """Left-hanging floating text blocks: hardcoded Meum identities.

        These are the same constants the DSP/domain/visual engines use.
        They hang on the left rail, float on Meum-timed orbits, and take
        AsymmetryCorrection so the field stays balanced.
        """
        n = len(self.MEUM_BLOCKS)
        col_w = min(280.0, max(168.0, width * 0.22))
        left_rail = 10.0
        for i, (sym, meaning, fmt, value) in enumerate(self.MEUM_BLOCKS):
            corr_x, corr_y = AsymmetryCorrection.offset(i, n, phase, scalars)
            # Meum-phased vertical stack with independent float.
            t = phase * MEUM_LOG2 + i * MEUM
            y = height * (0.06 + (i / max(n, 1)) * 0.86)
            y += height * 0.028 * math.sin(t * MEUM + i * 0.41)
            y += height * corr_y
            x = left_rail + 10.0 * math.sin(t * MEUM_NORM + i) + width * corr_x * 0.35
            x = max(6.0, min(width * 0.34, x))
            y = max(8.0, min(height - 46.0, y))
            rect = QRectF(x, y, col_w, 40.0)
            hue = (0.48 + i * MEUM_NORM * 0.08 + 0.04 * math.sin(t)) % 1.0
            fill = QColor.fromHsvF(hue, 0.35, 0.12, 0.42)
            edge = QColor.fromHsvF(hue, 0.55, 0.95, 0.55)
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(edge, 1.0))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor.fromHsvF(hue, 0.25, 1.0, 0.92))
            title = QFont("Consolas", 9)
            title.setBold(True)
            painter.setFont(title)
            painter.drawText(rect.adjusted(8, 3, -8, -16), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), sym)
            painter.setPen(QColor.fromHsvF(hue, 0.20, 0.92, 0.78))
            body = QFont("Consolas", 7)
            painter.setFont(body)
            val = fmt.format(value)
            painter.drawText(rect.adjusted(8, 18, -8, -3), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), f"{meaning}  {val}")

    def paintEvent(self, event):
        if self.width() < 10 or self.height() < 10:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(self.rect(), QColor(6, 10, 16, 22))
            if not self._param_cache[1]:
                self._reseed()
            scalars = self._scalars()
            phase = time.monotonic() - self._started
            w, h = self.width(), self.height()
            for i in range(self.WAVE_COUNT):
                self._paint_wave(painter, i, w, h, scalars, phase)
            for i in range(self.SHAPE_COUNT):
                self._paint_shape(painter, i, w, h, scalars, phase)
            self._paint_meum_blocks(painter, w, h, scalars, phase)
        finally:
            if painter.isActive():
                painter.end()

class UIComponentManager(QWidget):
    """Minimal compatibility stub — full controls live on the main window.

    Keeps btn_seeded_randomizer so existing connect() paths keep working without
    a second floating control panel competing for space.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.btn_seeded_randomizer = QPushButton("🎲 Phase-Locked Harmonic Randomizer")
        self.parametric_background = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.btn_seeded_randomizer)

class PhaseLockedWavefieldEngine:
    """Sensor → director → transducer for phase-coherent field fills.

    Reads Euclidean + seed-harmonic geometry, writes only non-user slots.
    """
    def __init__(self, app_instance):
        self.app = app_instance
        self.wavefield = {}
        self.last_coherence = 0.0
        self.goal_coherence = 0.92

    def get_numeric_seed(self):
        return int(self.app.get_numeric_seed()) if hasattr(self.app, 'get_numeric_seed') else 0

    def compute_wavefield(self):
        app = self.app
        count = int(app.spin_seq_length.value()) if hasattr(app, 'spin_seq_length') else 16
        seed = self.get_numeric_seed()
        rng = np.random.default_rng(seed if seed else 1)
        names = list(getattr(app, 'instrument_names_48', []) or [])
        self.wavefield = {}
        for i, name in enumerate(names):
            # Meum-spaced Euclidean hits
            period = 2 + int((i * MEUM + seed * 0.01) % 5)
            offset = int((i * 3 + seed) % max(period, 1))
            euc = [((s + offset) % period) == 0 for s in range(count)]
            t = np.linspace(0, 1, count, endpoint=False)
            env = 0.45 + 0.45 * np.sin(2 * np.pi * t * MEUM + i * 0.17)
            har = 0.5 + 0.4 * np.sin(2 * np.pi * t * MEUM_LOG2 + i * 0.31)
            self.wavefield[name] = {
                "euclidean": euc,
                "envelope": env.astype(float).tolist(),
                "seed_harmonics": har.astype(float).tolist(),
            }
        return self.wavefield


    def get_hints(self, instrument_name, step_index):
        """Per-step wavefield hints for randomizer / phase-lock bias.

        Returns dict with euclidean (bool), envelope (float), seed_harmonic (float),
        or None if the field is not ready for that instrument.
        """
        if not getattr(self, 'wavefield', None):
            try:
                self.compute_wavefield()
            except Exception:
                return None
        wf = self.wavefield.get(instrument_name) if self.wavefield else None
        if not wf:
            return None
        s = int(step_index)
        euc = wf.get("euclidean") or []
        env = wf.get("envelope") or []
        har = wf.get("seed_harmonics") or []
        return {
            "euclidean": bool(euc[s]) if s < len(euc) else False,
            "envelope": float(env[s]) if s < len(env) else 0.5,
            "seed_harmonic": float(har[s]) if s < len(har) else 0.5,
        }

    def evaluate_wavefront(self):
        if not self.wavefield:
            self.compute_wavefield()
        app = self.app
        count = int(app.spin_seq_length.value()) if hasattr(app, 'spin_seq_length') else 16
        hits = total = 0
        for name, wf in self.wavefield.items():
            mem = app.instrument_sequencer_memory.get(name, {})
            steps = mem.get('steps', [])
            euc = wf.get('euclidean', [])
            for s in range(min(count, len(euc))):
                total += 1
                on = bool(steps[s]) if s < len(steps) else False
                if on == bool(euc[s]):
                    hits += 1
        self.last_coherence = (hits / total) if total else 0.0
        return self.last_coherence

    def apply_phase_locked_randomization(self):
        """Correct non-user slots toward a seed-specific harmonic/geometric field."""
        app = self.app
        count = int(app.spin_seq_length.value()) if hasattr(app, 'spin_seq_length') else 16
        self.compute_wavefield()
        before = self.evaluate_wavefront()
        seed = int(self.get_numeric_seed()) if hasattr(self, "get_numeric_seed") else 1
        preserved = corrected = 0
        for name, wf in self.wavefield.items():
            mem = app.instrument_sequencer_memory.get(name)
            if not mem:
                continue
            if hasattr(app, '_ensure_seq_mem_length'):
                app._ensure_seq_mem_length(mem, count)
            user_mask = (
                app._user_pattern_mask(mem, count, instrument_name=name)
                if hasattr(app, '_user_pattern_mask') else [False] * count
            )
            euc, env, har = wf['euclidean'], wf['envelope'], wf['seed_harmonics']
            steps = mem.setdefault('steps', [False] * count)
            amps = mem.setdefault('amplitudes', [0.5] * count)
            pitches = mem.setdefault('pitches', [1.0] * count)
            probs = mem.setdefault('probabilities', [100] * count)

            try:
                op_idx = app.instrument_names_48.index(name)
            except Exception:
                op_idx = 0

            for s in range(count):
                if s < len(user_mask) and user_mask[s]:
                    preserved += 1
                    continue
                on = bool(euc[s]) if s < len(euc) else False
                e = float(env[s]) if s < len(env) else 0.5
                h = float(har[s]) if s < len(har) else 0.5

                # Seed-specific phase geometry. Meum is the invariant metric;
                # seed coordinates choose the actual harmonic cell.
                q = (
                    seed * 0.0000017
                    + (op_idx + 1) * PHI_INV
                    + (s + 1) * MEUM_LOG2
                )
                seed_coord = 0.5 + 0.5 * math.sin(
                    2.0 * math.pi * q + (op_idx + 1) * MEUM
                )
                seed_pitch = 2.0 ** (
                    (seed_coord - 0.5) * 0.72
                    + (h - 0.5) * 0.24
                )

                steps[s] = on
                amps[s] = float(np.clip(0.35 + 0.55 * e * h, 0.12, 1.0)) if on else 0.0
                pitches[s] = float(np.clip(seed_pitch, 0.56, 1.78))
                probs[s] = int(np.clip(55 + 45 * e, 20, 100)) if on else 0
                corrected += 1

        if hasattr(app, '_phase_lock_playlist_velocity'):
            app._phase_lock_playlist_velocity(
                rng=np.random.default_rng(seed or 1),
                strength=0.62, randomize=False,
            )
        if hasattr(app, 'reload_active_instrument_sequencer_ui'):
            app.reload_active_instrument_sequencer_ui()
        after = self.evaluate_wavefront()
        print(f"[Wavefield] preserved={preserved} corrected={corrected} "
              f"coherence {before:.3f}→{after:.3f}")

    def generate_ideal_patch_bay_routing(self):
        if hasattr(self.app, 'generate_ideal_patch_bay_routing'):
            type(self.app).generate_ideal_patch_bay_routing(self.app)

class ReadmeGuideDialog(QDialog):
    """Full Help / Readme: philosophy, workflow, scripting syntax, disclaimer."""

    HELP_TEXT = r"""
================================================================================
  EQR GROOVEBOX — Mathematician's / Scientist's Groovebox
  Full Documentation, Scripting Syntax & Design Philosophy
================================================================================
  Credits: core EQR design — project author; implementation assistance —
  Grok (xAI), Gemini (Google), and ChatGPT (OpenAI).

--------------------------------------------------------------------------------
1. GOAL OF THE SOFTWARE
--------------------------------------------------------------------------------
EQR Groovebox uses *mathematical specification* to maximize initial harmonic
diversity while letting you program simple or complicated music with the same
ease:

  • Simple: paint a few pads → Play. Engines fill, phase-lock, and balance
    around your carrier without overwriting it.
  • Complex: domains, scripts, patch topology, seeds, Euclidean lock, and
    fractal randomization scale up without changing the basic model
    (pads, playlist, seed, transport).

Design pillars:
  1) User data is the *carrier wave* — engines add around it; they do not wipe it.
  2) Seeds (irrationals: pi, e, Meum ≈ 1.1975807343, …) are geometric anchors.
  3) Empty slots are for convergent harmonic fill, not noise dumps.
  4) Redundant definitions are simplified first so fill engines have free capacity.
  5) Only inputs with *net effect* on the playlist timeline are treated as
     protected user data; silent or off-timeline data may be reshaped.

--------------------------------------------------------------------------------
2. DISCLAIMER — ADVANCED INSTRUMENT
--------------------------------------------------------------------------------
This is intentionally more advanced than many consumer synthesizers or DAW
step-sequencers. It exposes multivariate equations, domain partitions, modular
patch topology, Euclidean phase geometry, and seed-driven fractal composition.

You do *not* need a research background to start — pads + Play + Export work
immediately. Opening Domain Equations or Instrument Scripts puts you in a
mathematician/scientist-oriented workspace. Expect experimental behavior and
listen critically.

Not a full commercial DAW replacement. Specialized groovebox for exploration,
generative structure, and mathematically guided composition.

--------------------------------------------------------------------------------
3. QUICK START
--------------------------------------------------------------------------------
  1. Set BPM and sequence length.
  2. Select an instrument; toggle PKP pads (cyan = on).
  3. Optional: enter a *non-zero* Seed (blank or 0 / 0.0 = no seed).
  4. Optional: open Playlist and paint operators into the timeline.
  5. Press ▶ Live Audio Play (sounddevice) or Export .wav.
  6. Optional: Euclidean Phase-Lock and/or Seeded Harmonic Randomizer
     to additive-fill empty structure around your carrier.

--------------------------------------------------------------------------------
4. SEED RULES
--------------------------------------------------------------------------------
  • Empty field, 0, and 0.0 all mean **no seed** (same treatment).
  • Any non-zero number is a real geometric anchor.
  • Non-numeric text is hashed into a seed token.

--------------------------------------------------------------------------------
5. BOOTSTRAP (missing seed and/or program)
--------------------------------------------------------------------------------
Runs automatically before Euclidean lock / Seeded randomizer.

  Program = net-effect data only (playlist-effective instruments with audible steps).

  Case A — no seed AND no program (system is free to assign):
      25% → BOTH: random kit seed + kit program/sequences
      25% → SEED ONLY: random kit seed; pads/playlist left empty
      25% → SEQUENCES ONLY: kit program/sequences; seed field stays empty
      25% → NEITHER: no kit seed, no sequences (fully empty boot)

  Case B — program present, no seed:
      Derive seed from fingerprint of net-effect steps (simplifies playlist superwrite)

  Case C — non-zero seed present, no program:
      Provide seed-derived program parameters on pads + blank playlist fields only

  Case D — non-zero seed AND program:
      No bootstrap changes

--------------------------------------------------------------------------------
6. NET-EFFECT USER INPUT (INCLUDING DEPENDENCIES)
--------------------------------------------------------------------------------
Protected "user" data must be able to change the mix at some playlist time t:

  • Step ON with amplitude > ~0.02 (not near-silent)
  • Instrument is a playlist operator OR feeds one (directly or transitively)
    through user-accessible patch / GLOBAL_BUS routing — because changing that
    parameter changes another path that *does* hit the timeline
  • If playlist is empty/off, all instruments are in scope

Ignored for protection (engines may reshape freely):
  • Instruments with no playlist presence and no dependency path into one
  • Silent ON steps, empty patterns with no audible contribution

Fingerprint / "program present" checks use the same net-effect rules.

--------------------------------------------------------------------------------
7. SIMPLIFY (before additive fill)
--------------------------------------------------------------------------------
  • Quantize ON amplitudes to ladder {0.25, 0.5, 0.75, 1.0}
  • Link identical cross-instrument patterns to one canonical setting
  • Deduplicate patch cables (app + GLOBAL_BUS)
  • Merge domain partitions with identical bounds/logic/equation
  • Count identical scripts as shared definitions

Order:  Bootstrap → Simplify → Additive fill / phase-lock / patch optimize

--------------------------------------------------------------------------------
8. ADDITIVE ENGINES (NON-DESTRUCTIVE)
--------------------------------------------------------------------------------
Euclidean Phase-Lock
  • Never turns OFF protected user steps; never lowers user amps
  • Fills empty slots with Euclidean structure + soft spectral opposites
  • Sporadic probability commutation only on non-user slots

Seeded Harmonic Randomizer
  • Fractal echoes of your carrier into empty slots
  • Scripts updated only if still stock templates
  • Triggers additive patch optimizer

Patch Bay Optimizer
  • Never removes user cables or changes their gain/polarity
  • Sparse links only to unserved targets (activity + family + golden-ratio score)
  • Mirrors into GLOBAL_BUS only when edge is new

--------------------------------------------------------------------------------
9. DOMAIN TIME / SPACE EQUATIONS  (∫ button)
--------------------------------------------------------------------------------
Partitionable domains; each row:

  Name | Axis (time|space|both) | t0 t1 | x0 x1 | y0 y1
  Logic | Equation | Limits lo|hi | Weight|SeedW

Equation environment (safe):
  t, x, y, z, seed, seed_w, t_norm
  MEUM, sin, cos, tan, abs, sqrt, exp, log, pi, e
  clip, minimum, maximum, where, np

Logic examples:
  True
  t < 0.5
  abs(x) + abs(y) < 1.2
  seed_w > 0.3

Equation examples:
  sin(2 * pi * t * 2) * exp(-t * 3)
  sin(x * MEUM + t * 4) * cos(y * pi) * (1.0 - 0.2 * seed_w)
  sin(pi * t) * cos(2 * pi * t * (1 + seed_w))

Overlaps blend by weight; seed_weight longitudinally biases early vs late
partitions. Render modulation (additive):
  master *= (1 + 0.45 * domain_modulation)

--------------------------------------------------------------------------------
10. INSTRUMENT SCRIPTS  (📝 button)
--------------------------------------------------------------------------------
Per-operator script workspace. Typical form:

  def evaluate_wave(x, y, z):
      return np.sin(x * 3.0) * np.cos(y) - z

Custom scripts are preserved by the randomizer; only stock auto-templates
are replaced during seeded fill.

--------------------------------------------------------------------------------
11. PLAYLIST PAINTBRUSH & AUTOMATION
--------------------------------------------------------------------------------
  Wide unquantized grid (48 free rows by default) — not hard-bound to one instrument.

  Columns:
    Time Marker | Operator Identity | Script Tag | Velocity |
    Auto Target | Auto Amount | Direction Vector | Multi-Seq | Coverage | Blend Partner

  Paint subject menu:
    1. Identity + Steps + Automation (default)
    2. Selected instrument identity only
    3. Selected instrument step sequence (no automation)
    4. Step sequence + Automation
    5. Automation of selected instrument

  Draw Random Synth ON/OFF still chooses random vs selected identity when identity is painted.

  Snap to grid: OFF by default (fully unquantized). Enable checkbox to snap time markers.

  Overlap / blend:
    • Painting over existing paint builds per-operator coverage on that row
    • Full cover → automation applies at 100%; half cover → ~50%, etc.
    • Overlapping identities blend synth param snapshots up to Half (50%) or Quarter (25%)
      of the distance between the two instruments' settings (Blend max menu)

  Automation:
    • Written by paint modes that include Automation
    • Randomizer / Euclidean may fill *empty* automation lanes only (never overwrite yours)
    • apply_playlist_automation_to_ui pushes amounts onto EQR / Fractalizer / PKP knobs
      and gently scales patch gains (direction vector = sign)

--------------------------------------------------------------------------------
12. MAIN CONTROLS

--------------------------------------------------------------------------------
Transport
  ▶ Live Audio Play / ⏸ Stop   Realtime stream (sounddevice) + scope
  BPM, Seed field              Tempo + geometric anchor
  ✨ Euclidean & Geometry Global Lock
  🎲 Seeded Harmonic Global Randomizer
  💾 Save & Export .wav

Macros
  EQR Mod, Fractalizer, PKP Decay, PKP Envelope Follower, Tuning
  Master Vol (beside oscilloscope)

PKP Pad Bank (toggle)
  Independent 16th-note clock; orange playhead; short hits on programmed steps

Windows
  🛠 Synth / Wavetable     📜 Playlist Paintbrush
  🔌 Modular Patch Bay     📝 Instrument Script Editor
  ∫ Domain Time/Space Equations
  ❓ Help / Readme (this document)

--------------------------------------------------------------------------------
13. AUDIO
--------------------------------------------------------------------------------
  Realtime: sounddevice OutputStream callback; master volume live
  Export: shared _render_mixdown_buffer → WAV; 2.5D MP4 includes rendered audio
  PKP hits: non-blocking sd.play blips when pad bank is armed

  Install:
    pip install numpy PyQt6 sounddevice scipy
    python groovebox.py

--------------------------------------------------------------------------------
14. 48 OPERATORS
--------------------------------------------------------------------------------
Families span topological wave-folding, multivector/phase-space, quantum/soliton,
stochastic/entropic, spatial/spectral effects, and dynamic resonators.
Each has sequencer memory (steps, amplitudes, gates, probabilities) and optional script.

--------------------------------------------------------------------------------
15. RECOMMENDED WORKFLOW
--------------------------------------------------------------------------------
  A. Sketch carrier pads on one or more instruments
  B. Paint playlist rows if arranging over time
  C. Set a non-zero seed — or leave blank/0 for bootstrap
  D. Run Euclidean lock and/or Seeded randomizer (bootstrap + simplify auto-run)
  E. Optional: Domain equations for sectional form
  F. Optional: Patch bay for modular routing accents
  G. Play → refine → Export

================================================================================

--------------------------------------------------------------------------------
16. SEQUENCER AMP / PITCH & LIVE ENGINES
--------------------------------------------------------------------------------
  Step pads: click once = select (Amp/Vel + Pitch sliders). Click again = toggle on/off.
  Amp = velocity / step-trigger blend. Pitch = frequency ratio (automation param for steps).
  Euclidean + Seeded are LIVE TOGGLES (periodic regenerate against user carrier).
  "User program only" suspends both live engines.
  Save/Load Project (JSON). Keyboard/Test + Trigger All (global).
  Playlist: Convolve Color Coding for per-instrument hues + blend labels.
  Visualizer dropdown: master / effected / overall pattern / per-instrument activity.
  Global Cross-Loaded mode is default.

  End of Help — EQR Groovebox
  Assisted by Grok (xAI), Gemini (Google), Claude (Anthropic) and ChatGPT (OpenAI)
================================================================================
"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EQR Groovebox — Help, Readme & Scripting Guide")
        self.resize(900, 680)
        self.setStyleSheet(DAW_STYLE)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "<h3>📖 EQR Groovebox — Full Documentation</h3>"
            "<p style='color:#aaa;'>Mathematician's / Scientist's groovebox · "
            "maximize harmonic diversity · same ease for simple or complex projects</p>"
        ))

        text_view = QTextEdit()
        text_view.setReadOnly(True)
        text_view.setPlainText(self.HELP_TEXT)
        text_view.setStyleSheet(
            "background-color: #0d1117; color: #00ffcc; font-family: 'Consolas', monospace; font-size: 11px;"
        )
        layout.addWidget(text_view)

        close_btn = QPushButton("Close Guide")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

class GlobalCrossTabBusManager:
    """Manages universal inter-synth wiring, dedicated synth input/output jacks, master audio routing, and resampling."""
    def __init__(self):
        self.global_cables = []
        self.subscribers = []
        self.resampling_active = False
        self.resampled_buffers = []

    def register_subscriber(self, widget):
        if widget not in self.subscribers:
            self.subscribers.append(widget)

    def add_cable(self, src_module, src_node, tgt_module, tgt_node, polarity="Neutral", gain=1.0):
        cable = {
            "src_module": src_module, "src_node": src_node,
            "tgt_module": tgt_module, "tgt_node": tgt_node,
            "polarity": polarity, "gain": gain
        }
        self.global_cables.append(cable)
        self.broadcast_update()

    def remove_cable(self, index):
        if 0 <= index < len(self.global_cables):
            self.global_cables.pop(index)
            self.broadcast_update()

    def update_cable_polarity_gain(self, index, polarity, gain_delta):
        if 0 <= index < len(self.global_cables):
            self.global_cables[index]["polarity"] = polarity
            self.global_cables[index]["gain"] = max(0.1, round(self.global_cables[index]["gain"] + gain_delta, 2))
            self.broadcast_update()

    def trigger_resampling(self):
        self.resampling_active = True
        captured_signature = f"Resampled_Loop_{len(self.resampled_buffers) + 1}_{random.randint(1000, 9999)}"
        self.resampled_buffers.append(captured_signature)
        self.broadcast_update()
        return captured_signature

    def clear_all(self):
        self.global_cables.clear()
        self.resampled_buffers.clear()
        self.resampling_active = False
        self.broadcast_update()

    def broadcast_update(self):
        for sub in self.subscribers:
            if hasattr(sub, "on_global_patch_updated"):
                sub.on_global_patch_updated(self.global_cables)

GLOBAL_BUS = GlobalCrossTabBusManager()


# -------------------------------------------------------------------------
# ACTIVATED DRUM & SEQUENCER RUNTIME CONTROLLER WITH RHYTHM FLUX LINKING
# -------------------------------------------------------------------------
class PaintbrushTable(QWidget):
    """
    Wide unquantized playlist paint surface.
    Paint subject modes control whether identity, steps, and/or automation are written.
    Overlapping paints blend synth identities / automation by coverage (full=100%, half=50%).
    """

    # Paint subject menu options (user-specified)
    MODE_IDENTITY_STEPS_AUTO = "Identity + Steps + Automation (default)"
    MODE_IDENTITY_ONLY = "Selected instrument identity only"
    MODE_STEPS_ONLY = "Selected instrument step sequence (no automation)"
    MODE_STEPS_AUTO = "Step sequence + Automation"
    MODE_AUTO_ONLY = "Automation of selected instrument"
    MODE_RANDOM_PARAMETERS = "Random Parameters (velocity + automation)"
    MODE_CALCULATED_PARAMETERS = "Calculated Parameters (context field)"

    def __init__(self, parent=None, rows=0, cols=0):
        super().__init__(parent)
        self.app = parent
        self.is_drawing_stroke = False
        # Per-cell flash deadlines used by the paint visual feedback.
        # Kept as instance state so the flash routine is safe on first paint.
        self._cell_flash_until = {}
        # Per-row coverage map for overlap blending: row -> {op_name: coverage 0..1}
        self.row_coverage = {}
        self.init_ui(rows, cols)

    def init_ui(self, rows, cols):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        toolbar = QHBoxLayout()
        self.chk_draw_random_synth = QPushButton("🎨 Draw Random Synth: OFF")
        self.chk_draw_random_synth.setCheckable(True)
        self.chk_draw_random_synth.setStyleSheet(
            "background-color: #121212; color: #ff5555; border: 1px solid #444; font-weight: bold; padding: 6px;"
        )
        self.chk_draw_random_synth.clicked.connect(self.toggle_draw_random_synth_style)
        toolbar.addWidget(self.chk_draw_random_synth)

        toolbar.addWidget(QLabel("Paint subject:"))
        self.paint_mode_combo = QComboBox()
        self.paint_mode_combo.addItems([
            self.MODE_IDENTITY_STEPS_AUTO,
            self.MODE_IDENTITY_ONLY,
            self.MODE_STEPS_ONLY,
            self.MODE_STEPS_AUTO,
            self.MODE_AUTO_ONLY,
            self.MODE_RANDOM_PARAMETERS,
            self.MODE_CALCULATED_PARAMETERS,
        ])
        self.paint_mode_combo.setMinimumWidth(280)
        toolbar.addWidget(self.paint_mode_combo)

        self.chk_snap_grid = QCheckBox("Snap to grid")
        self.chk_snap_grid.setChecked(False)  # unquantized by default
        self.chk_snap_grid.setToolTip("Off = fully unquantized free-time. On = snap time markers to grid.")
        toolbar.addWidget(self.chk_snap_grid)

        toolbar.addWidget(QLabel("Blend max:"))
        self.blend_max_combo = QComboBox()
        self.blend_max_combo.addItems(["Half (50%)", "Quarter (25%)"])
        self.blend_max_combo.setToolTip("Max parameter travel when two instrument paints fully overlap.")
        toolbar.addWidget(self.blend_max_combo)
        self.btn_convolve_colors = QPushButton("🎨 Convolve Color Coding")
        self.btn_convolve_colors.setToolTip("Assign distinct cross-labeled colors per instrument across the playlist.")
        self.btn_convolve_colors.clicked.connect(self.convolve_color_coding)
        toolbar.addWidget(self.btn_convolve_colors)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # Custom inner table to intercept raw mouse events for continuous drag-painting
        class PaintTableWidget(QTableWidget):
            def __init__(self, parent_table, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.parent_table = parent_table
                self.setMouseTracking(True)

            def mousePressEvent(self, event):
                self.parent_table.is_drawing_stroke = True
                item = self.itemAt(event.pos())
                if item:
                    self.parent_table.engage_paint(item.row(), item.column(), event=event, table=self)
                else:
                    index = self.indexAt(event.pos())
                    if index.isValid():
                        self.parent_table.engage_paint(index.row(), index.column(), event=event, table=self)
                super().mousePressEvent(event)

            def mouseMoveEvent(self, event):
                if self.parent_table.is_drawing_stroke:
                    item = self.itemAt(event.pos())
                    if item:
                        self.parent_table.engage_paint(item.row(), item.column(), event=event, table=self)
                    else:
                        index = self.indexAt(event.pos())
                        if index.isValid():
                            self.parent_table.engage_paint(index.row(), index.column(), event=event, table=self)
                super().mouseMoveEvent(event)

            def mouseReleaseEvent(self, event):
                self.parent_table.is_drawing_stroke = False
                # Resolve overlaps / automation after stroke
                if hasattr(self.parent_table, 'resolve_row_overlaps'):
                    self.parent_table.resolve_row_overlaps()
                super().mouseReleaseEvent(event)

        # Wider grid: time, operator, script, velocity, automation target, auto amount,
        # modulation, multi-seq, coverage, blend partner
        n_cols = max(cols, 10)
        self.table_widget = PaintTableWidget(self, rows, n_cols)
        self.table_widget.setMinimumWidth(1200)
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table_widget)

    def rowCount(self):
        return self.table_widget.rowCount()

    def columnCount(self):
        return self.table_widget.columnCount()

    def item(self, row, col):
        return self.table_widget.item(row, col)

    def set_cell_item(self, row, col, item_or_text, bg_color=None):
        if isinstance(item_or_text, QTableWidgetItem):
            text = item_or_text.text()
            bg = item_or_text.background()
        else:
            text = str(item_or_text)
            bg = bg_color

        item = self.table_widget.item(row, col)
        if item is None:
            item = QTableWidgetItem(text)
            if bg and bg.color().isValid():
                item.setBackground(bg)
            self.table_widget.setItem(row, col, item)
        else:
            item.setText(text)
            if bg and bg.color().isValid():
                item.setBackground(bg)

    def setItem(self, row, col, item):
        """Compatibility shim: PaintbrushTable wraps a QTableWidget.

        Older/generated code may treat the wrapper like QTableWidget and call
        setItem() directly. Delegate that operation to the real inner table.
        """
        self.table_widget.setItem(row, col, item)

    def setHorizontalHeaderLabels(self, labels):
        self.table_widget.setHorizontalHeaderLabels(labels)

    def viewport(self):
        """Expose the wrapped QTableWidget viewport to legacy/generated code."""
        return self.table_widget.viewport()

    def clearContents(self):
        """Delegate QTableWidget-style clearing to the wrapped table."""
        return self.table_widget.clearContents()

    def toggle_draw_random_synth_style(self):
        is_active = self.chk_draw_random_synth.isChecked()
        if is_active:
            self.chk_draw_random_synth.setText("🎨 Draw Random Synth: ON")
            self.chk_draw_random_synth.setStyleSheet(
                "background-color: #00ffff; color: #060606; border: 1px solid #fff; font-weight: bold; padding: 6px;"
            )
        else:
            self.chk_draw_random_synth.setText("🎨 Draw Random Synth: OFF")
            self.chk_draw_random_synth.setStyleSheet(
                "background-color: #121212; color: #ff5555; border: 1px solid #444; font-weight: bold; padding: 6px;"
            )

    def _current_paint_mode(self):
        return self.paint_mode_combo.currentText() if hasattr(self, 'paint_mode_combo') else self.MODE_IDENTITY_STEPS_AUTO

    def _blend_max_fraction(self):
        txt = self.blend_max_combo.currentText() if hasattr(self, 'blend_max_combo') else "Half"
        return 0.25 if "Quarter" in txt else 0.5

    def _selected_operator(self, rng):
        if self.chk_draw_random_synth.isChecked():
            return str(rng.choice(self.app.instrument_names_48))
        if hasattr(self.app, 'instrument_selector_dropdown'):
            return self.app.instrument_selector_dropdown.currentText()
        return self.app.instrument_names_48[0]

    def _ensure_automation_store(self):
        if not hasattr(self.app, 'playlist_automation') or self.app.playlist_automation is None:
            self.app.playlist_automation = []
        while len(self.app.playlist_automation) <= self.table_widget.rowCount():
            self.app.playlist_automation.append({})
        if not hasattr(self.app, 'instrument_param_state') or not self.app.instrument_param_state:
            # Lightweight per-instrument synth knob snapshot (EQR/Fractalizer/PKP/tuning style)
            self.app.instrument_param_state = {}
            for i, name in enumerate(getattr(self.app, 'instrument_names_48', [])):
                self.app.instrument_param_state[name] = {
                    "eqr": 0.5 + 0.01 * (i % 7),
                    "fractalizer": 0.3 + 0.02 * (i % 5),
                    "pkp_decay": 0.25 + 0.01 * (i % 9),
                    "tuning": 1.0,
                    "filter": 0.5,
                    "drive": 0.2,
                }

    def engage_paint(self, row, col, event=None, table=None):
        """Paint one cell at up to PAINT_RATE_HZ; stack CSV instances with multidimensional overlaps.

        Ordinary drag paint: if the pointer stays within 50% of the cell width/height of the
        previous paint locus on the same cell, overlap is cancelled (no new stack entry).
        Successful paints flash the cell; reaching PAINT_INSTANCE_LIMIT substitutes and
        convolves color to show the replacement.
        """
        if not hasattr(self.app, 'instrument_names_48'):
            return
        self._ensure_automation_store()
        rows = self.table_widget.rowCount()
        cols = self.table_widget.columnCount()
        if row < 0 or col < 0 or row >= rows or col >= cols:
            return
        # Explicitly remember user-painted playlist cells so additive engines
        # can fill every other cell without ever overwriting a human edit.
        touched = getattr(self, "playlist_user_touched", None)
        if touched is None:
            touched = self.playlist_user_touched = set()
        touched.add((int(row), int(col)))

        now = time.monotonic()
        if not hasattr(self, "_last_flash_paint_cell"):
            self._last_flash_paint_cell = None
        if not hasattr(self, "_last_flash_paint_locus"):
            self._last_flash_paint_locus = None
        # Rate-limit stacking to 2.395 Hz (except mode-expansion internal calls)
        expanding = bool(getattr(self, '_paint_expanding', False))
        if not expanding:
            if (now - float(getattr(self, '_last_paint_mono', 0.0))) < PAINT_PERIOD_S:
                if self._last_flash_paint_cell == (row, col):
                    return  # too soon on same cell
            # Proximity cancel: same cell, within 50% of cell size of last locus
            local = None
            if event is not None and table is not None:
                try:
                    pos = event.position().toPoint()
                    idx = table.indexAt(pos)
                    rect = table.visualRect(idx) if idx.isValid() else None
                    if rect is not None and rect.width() > 0 and rect.height() > 0:
                        local = (
                            (pos.x() - rect.x()) / max(rect.width(), 1),
                            (pos.y() - rect.y()) / max(rect.height(), 1),
                        )
                except Exception:
                    local = None
            if (
                self._last_flash_paint_cell == (row, col)
                and local is not None
                and self._last_flash_paint_locus is not None
            ):
                dx = abs(local[0] - self._last_flash_paint_locus[0])
                dy = abs(local[1] - self._last_flash_paint_locus[1])
                # 50% of cell length/width is enough to cancel any overlap
                if dx < 0.50 and dy < 0.50:
                    return
            self._last_paint_mono = now
            self._last_flash_paint_cell = (row, col)
            self._last_flash_paint_locus = local

        seed_val = 42
        if hasattr(self.app, 'get_numeric_seed'):
            seed_val = int(self.app.get_numeric_seed()) % (2**31)
        elif hasattr(self.app, 'input_seed_val'):
            try:
                txt = self.app._seed_text()
                seed_val = int(struct.unpack(">Q", struct.pack(">d", float(txt)))[0] % (2**31)) if txt else 42
            except Exception:
                seed_val = 42
        # Deterministic per cell — no wall clock
        rng = np.random.default_rng((seed_val + row * 131 + col * 17) % (2**31))
        mode = self._current_paint_mode()
        snap = bool(self.chk_snap_grid.isChecked()) if hasattr(self, 'chk_snap_grid') else False
        # Position along the row (unquantized free-time uses Meum spacing)
        if snap:
            pos_tag = f"q:{row}"
        else:
            pos_tag = f"u:{(row * MEUM):.3f}s"

        def _append_cell_member(r, c, member):
            """CSV members with limit, substitution, flash, and overlap data-points."""
            existing = ""
            item = self.table_widget.item(r, c)
            if item is not None:
                existing = (item.text() or "").strip()
            token = f"{member}@{pos_tag}"
            parts = [p.strip() for p in existing.split(",") if p.strip()] if existing else []
            base = member.split("@")[0].strip()
            out = []
            replaced = False
            substituted = False
            for p in parts:
                pbase = p.split("@")[0].strip()
                if pbase == base:
                    out.append(token)
                    replaced = True
                else:
                    out.append(p)
            if not replaced:
                if len(out) >= PAINT_INSTANCE_LIMIT:
                    # Limit reached: substitute oldest instance, mark substitution
                    out = out[1:] + [token]
                    substituted = True
                else:
                    out.append(token)
            text_val = ", ".join(out)
            self.set_cell_item(r, c, text_val)
            overlap_n = len(out)
            # Flash + overlap data-points on the programmed cell
            self._flash_paint_cell(
                r, c, overlap_n,
                substituted=substituted,
                member=member
            )
            return text_val

        target_operator_name = self._selected_operator(rng)
        palette_colors = [
            QColor(20, 90, 100), QColor(70, 30, 90), QColor(20, 90, 40),
            QColor(90, 50, 20), QColor(90, 20, 30), QColor(30, 40, 90)
        ]

        # Ensure playlist row dict exists
        while len(getattr(self.app, 'master_playlist_data', [])) <= row:
            self.app.master_playlist_data.append({})
        entry = self.app.master_playlist_data[row]
        if not isinstance(entry, dict):
            entry = {}
            self.app.master_playlist_data[row] = entry
        entry['position'] = pos_tag
        entry['quantized'] = snap

        # --- Only the clicked cell is painted ---
        if col == 0:
            _append_cell_member(row, 0, pos_tag.split(":", 1)[-1] if ":" in pos_tag else pos_tag)
            entry['time_marker'] = pos_tag
            return

        if col == 1:
            # identity column — accumulate operators comma-separated
            name = target_operator_name
            if mode == self.MODE_RANDOM_PARAMETERS:
                name = self.app.instrument_names_48[int(rng.integers(0, len(self.app.instrument_names_48)))]
            _append_cell_member(row, 1, name)
            # Random multidimensional overlaps: stack secondary instances on related cells
            if not getattr(self, '_paint_expanding', False) and float(rng.random()) < 0.55:
                extra = self.app.instrument_names_48[int(rng.integers(0, len(self.app.instrument_names_48)))]
                if extra != name:
                    _append_cell_member(row, 1, extra)
                # random axes of automation overlap
                _append_cell_member(row, 4, str(rng.choice(["eqr", "fractalizer", "pkp_decay", "filter", "drive"])))
                _append_cell_member(row, 5, f"{int(rng.integers(20, 90))}%")
                _append_cell_member(row, 8, f"Cover{float(rng.uniform(0.25, 1.0)):.0%}")
            # multi-op list on the row
            ops = [p.split("@")[0].strip() for p in (self.table_widget.item(row, 1).text() or "").split(",") if p.strip()]
            entry['operator'] = ops[0] if ops else name
            entry['operators'] = ops
            item = self.table_widget.item(row, 1)
            if item is not None:
                item.setBackground(palette_colors[row % len(palette_colors)])
            return

        if col == 2:
            tag = f"Script::{target_operator_name[:6].upper()}"
            _append_cell_member(row, 2, tag)
            entry['script_tag'] = tag
            return

        if col == 3:
            ctx = self.app._contextual_numerology(target_operator_name, row, row) if hasattr(self.app, '_contextual_numerology') else 0.5
            if mode == self.MODE_RANDOM_PARAMETERS:
                velocity = float(rng.uniform(0.10, 1.20))
            else:
                velocity = float(np.clip(0.15 + 1.15 * ctx, 0.05, 1.5))
            _append_cell_member(row, 3, f"{velocity * 100:.1f}%")
            entry['velocity'] = velocity
            return

        if col == 4:
            params = list(self.app.instrument_param_state.get(target_operator_name, {"eqr": 0.5, "fractal": 0.5, "pkp": 0.5}).keys()) or ["eqr"]
            # any combination of param names can accumulate
            if mode == self.MODE_RANDOM_PARAMETERS:
                k = int(rng.integers(1, min(4, len(params) + 1)))
                chosen = list(rng.choice(params, size=min(k, len(params)), replace=False))
            else:
                chosen = [params[(row + col) % len(params)]]
            for p in chosen:
                _append_cell_member(row, 4, str(p))
            entry['auto_targets'] = [p.split("@")[0].strip() for p in (self.table_widget.item(row, 4).text() or "").split(",") if p.strip()]
            return

        if col == 5:
            ctx = 0.5
            try:
                ctx = float(self.app._contextual_numerology(target_operator_name, row, row))
            except Exception:
                pass
            if mode == self.MODE_RANDOM_PARAMETERS:
                amt = int(rng.integers(20, 90))
            else:
                amt = int(round(100 * float(np.clip(0.50 + 0.24 * (ctx - 0.5) * 2.0, 0.20, 0.80))))
            _append_cell_member(row, 5, f"{amt}%")
            entry['auto_amount'] = amt / 100.0
            return

        if col == 6:
            direction = "+" if (row + col) % 2 == 0 else "−"
            _append_cell_member(row, 6, f"Vector{direction}")
            entry['direction'] = 1.0 if direction == "+" else -1.0
            return

        if col == 7:
            multi = f"Multi[{(row % 3) + 1}]"
            _append_cell_member(row, 7, multi)
            entry['multi_seq'] = multi
            return

        if col == 8:
            cov = 0.25
            rc = self.row_coverage.setdefault(row, {})
            prev = float(rc.get(target_operator_name, 0.0))
            cov = min(1.0, prev + 0.25)
            rc[target_operator_name] = cov
            _append_cell_member(row, 8, f"Cover{cov:.0%}")
            entry['coverage'] = cov
            return

        if col >= 9:
            blend = float(rng.uniform(0.0, 100.0))
            _append_cell_member(row, col, f"Blend{blend:.1f}%")
            entry['blend_percent'] = blend
            return

        # Mode-driven subjects: ensure every relevant cell type can be painted
        mode_cols = set()
        if mode in (self.MODE_IDENTITY_STEPS_AUTO, self.MODE_IDENTITY_ONLY):
            mode_cols.update([1])
        if mode in (self.MODE_IDENTITY_STEPS_AUTO, self.MODE_STEPS_ONLY, self.MODE_STEPS_AUTO):
            mode_cols.update([2, 3])
        if mode in (self.MODE_IDENTITY_STEPS_AUTO, self.MODE_STEPS_AUTO, self.MODE_AUTO_ONLY,
                    self.MODE_RANDOM_PARAMETERS, self.MODE_CALCULATED_PARAMETERS):
            mode_cols.update([4, 5, 6, 8, 9])
        # Paint additional mode columns once (avoid infinite recursion: only expand from primary click)
        if not getattr(self, '_paint_expanding', False):
            self._paint_expanding = True
            try:
                for mc in sorted(mode_cols):
                    if mc != col:
                        self.engage_paint(row, mc)
            finally:
                self._paint_expanding = False


    def _flash_paint_cell(self, row, col, overlap_n, substituted=False, member=""):
        """Flash cell color; encode overlap count; convolve on substitution."""
        item = self.table_widget.item(row, col)
        if item is None:
            item = QTableWidgetItem("")
            self.table_widget.setItem(row, col, item)
        # Base hue from member hash / row; shift by overlap and substitution
        h = (hash(member or f"{row}:{col}") % 360)
        if substituted:
            # Distinct convolution: rotate hue + desaturate fill to signal replacement
            h = (h + 137) % 360  # golden-angle step
            color = QColor.fromHsv(h, 200, 255)
            item.setToolTip(f"SUBSTITUTED · overlap={overlap_n} · {member}")
        else:
            # Brighter with more overlap instances
            sat = min(255, 140 + overlap_n * 18)
            val = min(255, 180 + overlap_n * 8)
            color = QColor.fromHsv(h % 360, sat, val)
            item.setToolTip(f"overlap={overlap_n} · {member}")
        item.setBackground(color)
        # Brief flash to white-ish then settle.  Lazily initialize as a
        # defensive guard in case this method is reached before __init__
        # completed or an older PaintbrushTable instance is reused.
        if not hasattr(self, "_cell_flash_until"):
            self._cell_flash_until = {}
        self._cell_flash_until[(row, col)] = time.monotonic() + 0.18
        flash = QColor(255, 255, 255, 210)
        item.setBackground(flash)
        # Restore programmed color after flash window
        def _restore(_r=row, _c=col, _col=QColor(color), _n=overlap_n):
            it = self.table_widget.item(_r, _c)
            if it is None:
                return
            # draw overlap data-points as trailing markers in tooltip / status
            it.setBackground(_col)
            it.setForeground(QColor("#061018") if _col.value() > 160 else QColor("#f2f6fa"))
        QTimer.singleShot(120, _restore)
        # Status line data-points
        try:
            if hasattr(self.app, 'scope_status_label'):
                mark = "↻SUB" if substituted else ("●" * min(overlap_n, 6))
                self.app.scope_status_label.setText(
                    f"🖌 cell[{row},{col}] overlap={overlap_n} {mark} {member[:24]}"
                )
        except Exception:
            pass

    def _blend_instrument_params(self, op_a, op_b, amount):
        """Move op_a params up to `amount` of the way toward op_b (amount already scaled by max blend)."""
        a = self.app.instrument_param_state.get(op_a)
        b = self.app.instrument_param_state.get(op_b)
        if not a or not b:
            return
        for k in a:
            if k in b:
                a[k] = float(a[k] * (1.0 - amount) + b[k] * amount)

    def resolve_row_overlaps(self):
        """After a stroke, re-assert coverage labels and push automation UI state."""
        self._ensure_automation_store()
        for row, cov in self.row_coverage.items():
            if not cov:
                continue
            parts = [f"{k[:10]}:{v:.0%}" for k, v in cov.items()]
            self.set_cell_item(row, 8, " | ".join(parts)[:48])
        # Reflect automation into global macros lightly (UI update)
        if hasattr(self.app, 'apply_playlist_automation_to_ui'):
            self.app.apply_playlist_automation_to_ui()

    def convolve_color_coding(self):
        """Distinct hue per instrument + cross-label on operator column for blend visibility."""
        names = list(getattr(self.app, 'instrument_names_48', []))
        n = max(len(names), 1)
        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, 1)
            if not item:
                continue
            op = item.text().strip()
            if op not in names:
                continue
            idx = names.index(op)
            # HSV-style distinct colors spread across 48 operators
            h = int((idx * 360 / n) % 360)
            color = QColor.fromHsv(h, 180, 160)
            item.setBackground(color)
            # Cross-label: short family tag + index
            fam = idx // 6
            item.setText(f"{op}  ·F{fam}/#{idx+1}")
            # Coverage multi-color note in col 8
            cov = self.row_coverage.get(row, {})
            if len(cov) > 1:
                self.set_cell_item(row, 8, "BLEND " + "+".join(f"{k[:6]}" for k in cov.keys()))
        print("[Playlist] Convolve color coding applied")
# ==========================================
# 4. MODULAR TAB MANAGER (TOP PANE)
# ==========================================
class MathematiciansGrooveboxApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Groovebox")
        self.resize(1300, 950)

        self.playlist_window = None
        self.patch_bay_dialog = None
        self.synth_editor_window = None
        self.script_editor_window = None
        self.visual_oscilloscope = None
        self.wavefield_engine = PhaseLockedWavefieldEngine(self)
        self.domain_eq_engine = DomainPartitionEquationEngine(seed=0.0)
        self.domain_eq_dialog = None

        # IMPORTED_PROJECT_AUTHORITY:
        # A loaded project is a user-authored source of truth.  Engine output may
        # decorate it only when explicitly armed; loading/rendering must never
        # bootstrap, randomize, or phase-lock an imported empty/partial state.
        self._project_imported_user_state = False
        self._project_audio_data_loaded = False
        self._engine_generated_playlist_rows = set()
        self._engine_generated_automation_rows = set()

        # Initialize the UI Manager as an independent floating control panel
        # that stays attached to your main app window
        # Hidden compatibility stub (btn_seeded_randomizer only). No floating panel.
        self.ui_manager = UIComponentManager(self)
        if not self.centralWidget():
            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)
        if not hasattr(self, 'main_window_layout') or self.main_window_layout is None:
            self.main_window_layout = QVBoxLayout(self.centralWidget())

        # ----------------------------------------------------------------
        # FULL-WINDOW parametric math background (asking-for.txt fix).
        # Previously the background lived only on UIComponentManager, which
        # is resized to 850×120 — so the field was effectively invisible.
        # Parent it to the central widget, fill it, lower behind controls,
        # and keep it mouse-transparent. Opacity is low so UI stays readable.
        # ----------------------------------------------------------------
        try:
            cw = self.centralWidget()
            if cw is not None:
                self.parametric_background = ParametricMathBackground(self, cw)
                self.parametric_background.setGeometry(cw.rect())
                self.parametric_background.lower()
                self.parametric_background.show()
                # Soften the central fill so the math field reads through
                # without washing out the high-contrast controls.
                existing = cw.styleSheet() or ""
                if "background-color" not in existing:
                    cw.setStyleSheet(
                        "background-color: rgba(6, 6, 6, 210);"
                    )
                # Reseed glyphs when the active instrument changes
                if hasattr(self, "instrument_selector_dropdown"):
                    try:
                        self.instrument_selector_dropdown.currentIndexChanged.connect(
                            lambda _i: self.parametric_background._reseed()
                        )
                    except Exception:
                        pass
        except Exception as _bg_exc:
            print(f"[Background] attach skipped: {_bg_exc}")

        # Seeded randomizer button → randomizer ONLY (never chains phase-lock)
        try:
            self.ui_manager.btn_seeded_randomizer.clicked.disconnect()
        except TypeError:
            pass
        self.ui_manager.btn_seeded_randomizer.clicked.connect(lambda: self.apply_unified_randomizer(live=False))
        self.instrument_names_48 = [f"Operator_{i+1}" for i in range(48)]
        self.instrument_sequencer_memory = {}
        default_seq_len = 48

        for name in self.instrument_names_48:
            self.instrument_sequencer_memory[name] = {
                "steps": [False] * default_seq_len,
                "amplitudes": [0.5] * default_seq_len
            }

        # Set an active instrument pointer for the UI sequencer grid
        self.active_instrument_memory = self.instrument_sequencer_memory[self.instrument_names_48[0]]
        self.instrument_names_48 = [
            "Z-Pinch Resonator", "Topological Fold", "Quantum Soliton", "Harmonic Phase-Shift",
            "Sub-Harmonic Drone", "Micro-Transient Click", "Stochastic Noise Matrix", "Voltage Controlled Crystal",
            "Resonant Cavity Feedback", "Plasma Streamer Node", "Frequency Divider Array", "Complex Waveguide",
            "Anomalous Sine Core", "Hyperbolic Sawtooth", "Additive Formant Synth", "Granular Cloud Emitter",
            "Metallic Tines", "Glass Resonance", "Sub-Bass Ionizer", "Electrostatic Discharge",
            "Vector Morph Oscillator", "Ring Modulator Bank", "Spectral Smear Filter", "Formant Sweep Matrix",
            "Bit-Crushed Impulse", "Phase Distortion Core", "Resonant Comb Filter", "Complex FM Modulator",
            "Analog Drift Oscillator", "Vacuum Tube Saturation", "Tape Flutter Emulator", "Spring Reverb Tank",
            "Binaural Drone Generator", "Chaotic Attractor Node", "Percolating Noise Burst", "Harmonic Overdrive",
            "Sub-Audio LFO", "Pulse Width Modulator", "Sync-Lead Synthesizer", "Formant Vocalizer",
            "Acoustic Plate Simulation", "Piezo Transducer Click", "Thermal Noise Generator", "Galactic Cosmic Ray",
            "Magnetic Flux Modulator", "Eddy Current Oscillator", "Standing Wave Matrix", "Quantum Entanglement Node"
        ]

        self.instrument_sequencer_memory = {
            name: {
                "steps": [False] * 48,
                "gates": [True] * 48,
                "amplitudes": [1.0] * 48,
                "pitches": [1.0] * 48,
                "probabilities": [100] * 48
            }
            for name in self.instrument_names_48
        }

        self.instrument_scripts = {
            name: f"# Script workspace for {name} based on operator rules\ndef evaluate_wave(x, y, z):\n    return np.sin(x * {((i)%12)+1}.0) * np.cos(y) - z"
            for i, name in enumerate(self.instrument_names_48)
        }

        # No musical programs are injected at boot.
        # Harmonic/script/patch/domain defaults remain available as neutral context.
        # RECOMMENDED_POWER_LAYER: compatibility hook only; no musical presets.
        self.hardcoded_compositions = {}

        # Master storage mirroring the unquantized playlist rows for audio rendering
        self.master_playlist_data = []

        self.export_counter = 1

        # =====================================================================
        # USER-REQUESTED WAV CARRIER / CONVOLVE-FIT FEATURE
        # Revert marker: remove this state block plus the blocks tagged
        # CONVOLVE_FIT_FEATURE to restore the previous behavior.
        # =====================================================================
        self.imported_waveform = None
        self.imported_sample_rate = 44100
        self.imported_wav_path = ""
        # MEDIA_IMPORT_FEATURE: optional video carrier + parsed stream metadata.
        # Revert: remove this state block and the MEDIA_IMPORT_FEATURE methods/UI.
        self.imported_video_path = ""
        self.imported_video_meta = {}

        self.playlist_automation = []
        self.instrument_param_state = {}
        # Build the initial program state before rendering the sequencer.
        # This prevents the first selection click from revealing hidden gates.
        # RECOMMENDED_POWER_LAYER: neutral mathematical boot. Engines create
        # musical material only when explicitly invoked.
        self.init_ui_components()
        self.initialize_default_playlist_memory()
        self._composition_generation_counter = 0

    def apply_hardcoded_compositions(self):
        # POWER_V3_EMPTY_BOOT: compatibility hook intentionally does nothing.
        # The application may keep idealized harmonic/synth/domain defaults, but
        # it never injects a musical composition into sequencer memory at boot.
        return 0

    def initialize_default_playlist_memory(self):
        # Playlist capacity is present, but the musical program is empty on boot.
        rows = 96
        # POWER_V3_EMPTY_BOOT: capacity exists, but there is no musical program.
        self.master_playlist_data = [{} for _ in range(rows)]
        self.playlist_automation = [{} for _ in range(rows)]

    def sync_playlist_grid_to_memory(self):
        """Round-trip ALL ten playlist cell types without erasing engine metadata."""
        if not (hasattr(self, 'active_paint_table') and self.active_paint_table):
            return
        table = self.active_paint_table
        old_rows = list(getattr(self, "master_playlist_data", []) or [])
        rebuilt = []
        for r in range(table.rowCount()):
            prior = old_rows[r] if r < len(old_rows) and isinstance(old_rows[r], dict) else {}
            def cell(c):
                item = table.item(r, c)
                return item.text().strip() if item else ""
            row_dict = dict(prior)  # preserve generated/user ownership and hidden fields
            row_dict.update({
                "time_marker": cell(0),
                "operator": cell(1),
                "script_tag": cell(2),
                "auto_target": cell(4),
                "effect_target": cell(4),
                "auto_amount": cell(5),
                "direction_vector": cell(6),
                "multi_seq": cell(7),
                "coverage": cell(8),
                "blend_partner": cell(9),
            })
            # Column 3 is velocity; never silently reset a generated/user value.
            if cell(3):
                try:
                    v = float(cell(3).replace("%", "").strip())
                    row_dict["velocity"] = v / 100.0 if v > 1.0 else v
                except Exception:
                    row_dict["velocity"] = prior.get("velocity", 1.0)
            else:
                row_dict["velocity"] = prior.get("velocity", 1.0)
            # Preserve the complete multi-instance identity string when present.
            row_dict["operators_csv"] = cell(1)
            row_dict["user_defined"] = bool(prior.get("user_defined", False))
            rebuilt.append(row_dict)
        self.master_playlist_data = rebuilt


    # =====================================================================
    # LOCAL_CONTEXT_UI helpers — must live on MathematiciansGrooveboxApp
    # (they were previously only defined on UIComponentManager, which caused
    # AttributeError at startup when building the LOCAL CONTEXT panel).
    # =====================================================================
    def _make_local_context_button(self, text, tooltip):
        """Square local-context action button (synth / script / modular). Classic single-label."""
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(92, 92)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(
            "QPushButton { background-color:#121212; color:#00ffff; "
            "border:2px solid #00ffff; border-radius:8px; padding:6px; "
            "font-weight:bold; } QPushButton:hover { background-color:#202830; } "
            "QPushButton:pressed { background-color:#ff6b00; color:white; }"
        )
        return btn

    def _make_integral_domain_button(self, tooltip):
        """Self-contained ∫ Domain control.

        The button paints its own ∫ glyph and DOMAIN caption. No nested
        labels, no newlines, no user-supplied "Domain" text. Synth / Script /
        Modular still use the classic helper and stay 92×92.
        """
        class IntegralDomainButton(QPushButton):
            def __init__(self, tip, parent=None):
                super().__init__(parent)
                self.setToolTip(tip)
                self.setFixedSize(92, 92)
                self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                self.setText("")
                self.setStyleSheet(
                    "QPushButton { background-color:#121212; color:#00ffff; "
                    "border:2px solid #00ffff; border-radius:8px; padding:0; } "
                    "QPushButton:hover { background-color:#202830; } "
                    "QPushButton:pressed { background-color:#ff6b00; }"
                )

            def paintEvent(self, event):
                super().paintEvent(event)
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                pressed = self.isDown()
                color = QColor("#ffffff") if pressed else QColor("#00ffff")
                p.setPen(color)
                glyph = QFont(self.font())
                glyph.setPointSize(26)
                glyph.setBold(True)
                p.setFont(glyph)
                r = self.rect().adjusted(4, 4, -4, -22)
                p.drawText(r, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), "∫")
                cap = QFont(self.font())
                cap.setPointSize(8)
                cap.setBold(True)
                cap.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
                p.setFont(cap)
                cr = self.rect().adjusted(4, self.height() - 24, -4, -6)
                p.drawText(cr, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), "DOMAIN")
                p.end()

        return IntegralDomainButton(tooltip)

    # =====================================================================
    # RECOMMENDED_POWER_LAYER_V1 — CONTEXT FIELD + PARAMETER PAINT
    # Revert: delete this entire block. The rest of the groovebox remains usable.
    # Purpose: make Randomizer / Euclidean Phase-Lock reason over the current
    # mathematical instrument state instead of treating every step as isolated.
    # =====================================================================
    def _contextual_feature_vector(self, instrument_name="", step=0, row=0):
        """Return a deterministic structural field from live software state.

        This is intentionally a *planning signal*, not a hidden preset. It is
        evaluated only when an engine is invoked, so boot remains musically empty.
        """
        import hashlib
        scripts = getattr(self, 'instrument_scripts', {}) or {}
        script = str(scripts.get(instrument_name, ''))
        cables = getattr(self, 'patch_connections', []) or []
        gb = getattr(globals().get('GLOBAL_BUS', None), 'global_cables', []) or []
        playlist = getattr(self, 'master_playlist_data', []) or []
        active = [r for r in playlist if isinstance(r, dict) and any(v not in (None, '', [], {}) for v in r.values())]

        # POWER_V3_CONTEXT_FIELD: synth/wavetable state participates without
        # becoming a preset. Snapshot only scalar/numeric state for stability.
        synth_state = getattr(self, 'instrument_param_state', {}).get(instrument_name, {}) if instrument_name else {}
        if not isinstance(synth_state, dict):
            synth_state = {}
        numeric_synth = []
        for k, v in synth_state.items():
            try:
                numeric_synth.append((str(k), float(v)))
            except Exception:
                pass
        synth_blob = repr(sorted(numeric_synth))
        synth_score = (int(hashlib.sha256(synth_blob.encode('utf-8','replace')).hexdigest()[:12], 16) % 10000) / 10000.0

        # Imported WAV/video is a shared carrier. Its coarse energy is context,
        # not a command to invent a musical program at boot.
        media = getattr(self, 'media_carrier_slot', {}) or {}
        media_wave = media.get('waveform') if isinstance(media, dict) else None
        if media_wave is not None and np.asarray(media_wave).size:
            arr = np.asarray(media_wave, dtype=np.float32).ravel()
            edges = np.linspace(0, arr.size, max(2, 49)).astype(int)
            mi = min(max(int(step), 0), len(edges)-2)
            seg = arr[edges[mi]:max(edges[mi+1], edges[mi]+1)]
            media_score = float(np.clip(np.sqrt(np.mean(seg*seg)) if seg.size else 0.0, 0.0, 1.0))
        else:
            media_score = 0.0

        # Global effect state is another mathematical coordinate.
        effect_vals = []
        for attr in ('slider_eqr','slider_fractalizer','slider_pkp_decay','spin_base_frequency','spin_global_convolve'):
            obj = getattr(self, attr, None)
            try:
                val = float(obj.value()) if obj is not None and hasattr(obj, 'value') else 0.0
                effect_vals.append((attr, val))
            except Exception:
                pass
        effect_blob = repr(effect_vals)
        effect_score = (int(hashlib.sha256(effect_blob.encode('utf-8','replace')).hexdigest()[:12], 16) % 10000) / 10000.0

        # Script complexity: length + mathematical/operator density.
        digits = sum(ch.isdigit() for ch in script)
        ops = sum(script.count(op) for op in ('sin','cos','tan','exp','log','sqrt','evaluate','return'))
        script_score = float(np.clip(len(script)/1400.0 + digits/180.0 + ops/40.0, 0.0, 1.0))

        # Patch topology: fan-in/fan-out and gain density become structural bias.
        patch_count = len(cables)
        global_count = len(gb)
        gains = [abs(float(c.get('gain', 1.0))) for c in cables if isinstance(c, dict)]
        gain_score = min(float(np.mean(gains)) if gains else 0.5, 2.0) / 2.0
        topology_score = float(np.clip(0.55*patch_count/24.0 + 0.25*global_count/24.0 + 0.20*gain_score, 0.0, 1.0))

        # Domain state is represented by a stable signature; arbitrary scripts are
        # not executed here, which keeps the generator deterministic and safe.
        try:
            domain = self.domain_eq_engine.to_json() if getattr(self, 'domain_eq_engine', None) else {}
        except Exception:
            domain = {}
        domain_blob = repr(domain)
        domain_score = (int(hashlib.sha256(domain_blob.encode('utf-8','replace')).hexdigest()[:12], 16) % 10000) / 10000.0

        # Playlist feedback: density and the current row's velocity influence the
        # field. Empty boot therefore stays empty, but an invoked engine can grow
        # an arrangement in response to what has already been painted.
        density = float(np.clip(len(active) / max(len(playlist), 1), 0.0, 1.0))
        row_velocity = 0.5
        if 0 <= row < len(playlist) and isinstance(playlist[row], dict):
            try:
                row_velocity = float(np.clip(float(playlist[row].get('velocity', 0.5) or 0.5) / 1.5, 0.0, 1.0))
            except Exception:
                pass

        seed = self.get_numeric_seed() if hasattr(self, 'get_numeric_seed') else 42
        # POWER_V3_MEUM_FIELD: use the invariant M spatial ratio as a genuine
        # contextual coordinate. The golden-ratio and sqrt(2) phase terms remain
        # available elsewhere as their own mathematical constants; they are not Meum.
        meum_phase = ((step + 1) * MEUM + (row + 1) * MEUM_INV + (seed % 997) * MEUM_NORM) % 1.0
        meum_field = 0.5 + 0.5 * math.sin(2.0 * math.pi * meum_phase)
        # POWER_V3_CONTEXT_FIELD: all subsystems contribute to one reproducible field.
        score = float(np.clip(
            0.22*script_score + 0.20*topology_score + 0.16*domain_score +
            0.12*synth_score + 0.10*effect_score + 0.08*media_score +
            0.04*meum_field + 0.03*density + 0.02*row_velocity +
            0.03*meum_phase, 0.0, 1.0
        ))
        return {
            'score': score, 'script': script_score, 'topology': topology_score,
            'domain': float(domain_score), 'synth': float(synth_score),
            'effects': float(effect_score), 'media': float(media_score),
            'playlist_density': density, 'row_velocity': row_velocity,
            'phase': float(meum_phase), 'meum_field': float(meum_field)
        }

    def _seed_geometry(self, salt=""):
        """Return three uniform deterministic coordinates for the literal seed token."""
        import hashlib
        seed_text = self._seed_text() if hasattr(self, "_seed_text") else str(
            self.get_numeric_seed() if hasattr(self, "get_numeric_seed") else 0
        )
        digest = hashlib.sha256(f"{seed_text}|{salt}".encode("utf-8", "replace")).digest()
        return tuple(
            int.from_bytes(digest[i:i+8], "big") / float(2**64)
            for i in (0, 8, 16)
        )

    def _contextual_numerology(self, instrument_name="", step=0, row=0):
        """Seed-first deterministic field; Meum is an invariant, not the identity of every seed."""
        import hashlib
        f = self._contextual_feature_vector(instrument_name, step, row)
        seed_text = self._seed_text() if hasattr(self, "_seed_text") else "0"
        seed_num = int(self.get_numeric_seed()) if hasattr(self, "get_numeric_seed") else 0

        # Independent irrational coordinates keep distinct seed values geometrically
        # separated even when the surrounding project topology is identical.
        payload = f"{seed_text}|{seed_num}|{instrument_name}|{int(step)}|{int(row)}"
        d = hashlib.sha256(payload.encode("utf-8", "replace")).digest()
        u0 = int.from_bytes(d[0:8], "big") / float(2**64)
        u1 = int.from_bytes(d[8:16], "big") / float(2**64)
        u2 = int.from_bytes(d[16:24], "big") / float(2**64)

        # Meum remains part of the field, but it is only one coordinate among
        # phi/e/pi/sqrt(2). This prevents "every seed == Meum" behavior.
        phase = (
            u0 * 2.0 * math.pi
            + u1 * PHI
            + u2 * MEUM_LOG2
            + (seed_num % 1000003) * 1.7e-6
            + (int(step) + 1) * MEUM
            + (int(row) + 1) * PHI_INV
        )
        seed_field = 0.5 + 0.5 * math.sin(phase)
        harmonic_field = 0.5 + 0.5 * math.cos(
            phase * SQRT2 + (int(step) + 1) * MEUM_NORM
        )
        # A low-amplitude deterministic interaction term adds geometric
        # differentiation without turning the field into unconstrained noise.
        interaction = 0.5 + 0.5 * math.sin(
            phase * PHI + seed_field * math.pi + harmonic_field * MEUM
        )
        seed_score = float(np.clip(
            0.50 * seed_field + 0.32 * harmonic_field + 0.18 * interaction,
            0.0, 1.0
        ))

        # Existing contextual state remains useful, but no longer dominates.
        # This makes Randomizer/Phase-Lock respond to the actual seed first.
        tie_break = u0 * 0.35 + u1 * 0.25 + u2 * 0.40
        return float(np.clip(
            0.62 * seed_score + 0.28 * f["score"] + 0.10 * tie_break,
            0.0, 1.0
        ))

    def _paint_generated_parameters(self, rng=None, rows=None, source='context'):
        """Paint calculated/random playlist parameters, including velocity.

        RECOMMENDED_POWER_LAYER: called only by explicit generation actions.
        User-locked velocity and existing automation remain authoritative.
        """
        capacity = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 96
        rows = capacity if rows is None else max(0, min(int(rows), capacity))
        if not hasattr(self, 'master_playlist_data'):
            self.master_playlist_data = []
        while len(self.master_playlist_data) < rows:
            self.master_playlist_data.append({})
        rng = rng or np.random.default_rng(self.get_numeric_seed())
        painted = 0
        for r in range(rows):
            entry = self.master_playlist_data[r]
            if not isinstance(entry, dict):
                entry = {}; self.master_playlist_data[r] = entry
            if entry.get('velocity_user_locked'):
                continue
            inst = entry.get('operator', self.instrument_names_48[r % len(self.instrument_names_48)] if self.instrument_names_48 else '')
            f = self._contextual_feature_vector(inst, r, r)
            # Velocity is a true paintable field. The engine can generate it, but
            # once the user locks/paints it, later passes must leave it alone.
            jitter = float(rng.uniform(-0.06, 0.06))
            entry['velocity'] = float(np.clip(0.20 + 1.15*f['score'] + jitter, 0.05, 1.5))
            entry['velocity_source'] = source
            entry['calculated_context'] = {k: round(v, 6) for k, v in f.items()}
            painted += 1
        return painted

    # POWER_V3_PARAMETER_PAINT: one non-destructive interface for calculated or
    # random step parameters. Velocity is represented by amplitude in the pad UI
    # and by the explicit velocity field in the global playlist. No ownership
    # hierarchy is imposed; explicit user edits remain the strongest local signal.
    def _paint_step_parameters(self, rng=None, instrument_name=None, randomize=False,
                               strength=1.0, include_velocity=True, include_pitch=True,
                               include_probability=True):
        name = instrument_name or (self.instrument_selector_dropdown.currentText()
                                   if hasattr(self, 'instrument_selector_dropdown') else self.instrument_names_48[0])
        mem = self.instrument_sequencer_memory.get(name)
        if not isinstance(mem, dict):
            return 0
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 48
        self._ensure_seq_mem_length(mem, count)
        rng = rng or np.random.default_rng(self.get_numeric_seed())
        changed = 0
        for i in range(count):
            ctx = self._contextual_numerology(name, i, i)
            jitter = float(rng.uniform(-0.08, 0.08)) if randomize else 0.0
            target_amp = float(np.clip(0.18 + 0.78*ctx + jitter, 0.05, 1.0))
            target_pitch = float(np.clip(0.82 + 0.36*ctx + (rng.uniform(-0.05,0.05) if randomize else 0.0), 0.5, 1.5))
            target_prob = int(np.clip(round(55 + 45*ctx + (rng.uniform(-8,8) if randomize else 0)), 1, 100))
            if include_velocity:
                mem['amplitudes'][i] = float(np.clip((1-strength)*float(mem['amplitudes'][i]) + strength*target_amp, 0.0, 1.0))
            if include_pitch:
                mem['pitches'][i] = float(np.clip((1-strength)*float(mem['pitches'][i]) + strength*target_pitch, 0.5, 1.5))
            if include_probability:
                mem['probabilities'][i] = int(round((1-strength)*float(mem['probabilities'][i]) + strength*target_prob))
            changed += 1
        self.reload_active_instrument_sequencer_ui()
        return changed

    def _snapshot_global_effect_sliders(self):
        """Capture user-owned global macro values before composition operators run."""
        snap = {}
        for attr in ("slider_eqr", "slider_fractalizer", "slider_pkp_decay"):
            obj = getattr(self, attr, None)
            if obj is not None and hasattr(obj, "value"):
                try:
                    snap[attr] = int(obj.value())
                except Exception:
                    pass
        return snap

    def _restore_global_effect_sliders(self, snap):
        """Restore global macro values without retriggering their signals."""
        for attr, value in (snap or {}).items():
            obj = getattr(self, attr, None)
            if obj is not None and hasattr(obj, "setValue"):
                try:
                    obj.blockSignals(True)
                    obj.setValue(int(value))
                finally:
                    obj.blockSignals(False)

    def _randomize_local_context(self, checked=True):
        if hasattr(self, 'btn_local_randomize') and self.btn_local_randomize.isCheckable() and not checked and "randomizer"=="randomizer": return
        if hasattr(self, 'btn_local_phase_lock') and self.btn_local_phase_lock.isCheckable() and not checked and "randomizer"=="phase-lock": return
        self._composition_generation_counter=getattr(self,"_composition_generation_counter",0)+1
        snap=self._snapshot_global_effect_sliders()
        try:
            live_seed=int(self.get_numeric_seed())%(2**31)
            rng=np.random.default_rng(live_seed)
            if "randomizer"=="randomizer": self.apply_seeded_harmonic_randomization()
            elif hasattr(self,"wavefield_engine") and self.wavefield_engine is not None: self.wavefield_engine.apply_phase_locked_randomization()
            self._paint_step_parameters(rng=rng, randomize=("randomizer"=="randomizer"), strength=.55 if "randomizer"=="randomizer" else .70, include_velocity=True, include_pitch=True, include_probability=True)
            self._paint_generated_parameters(rng=rng, source="randomizer")
            self._phase_lock_playlist_velocity(rng,strength=.35 if "randomizer"=="randomizer" else .70,randomize=("randomizer"=="randomizer"))
            self._run_composition_context_engine(source="randomizer",rng=rng)
            self.reload_active_instrument_sequencer_ui()
        except Exception as e: print(f"[randomizer] skipped: {e}")
        finally: self._restore_global_effect_sliders(snap)

    def _phase_lock_local_context(self, checked=True):
        if hasattr(self, 'btn_local_randomize') and self.btn_local_randomize.isCheckable() and not checked and "phase-lock"=="randomizer": return
        if hasattr(self, 'btn_local_phase_lock') and self.btn_local_phase_lock.isCheckable() and not checked and "phase-lock"=="phase-lock": return
        self._composition_generation_counter=getattr(self,"_composition_generation_counter",0)+1
        snap=self._snapshot_global_effect_sliders()
        try:
            live_seed=int(self.get_numeric_seed())%(2**31)
            rng=np.random.default_rng(live_seed)
            if "phase-lock"=="randomizer": self.apply_seeded_harmonic_randomization()
            elif hasattr(self,"wavefield_engine") and self.wavefield_engine is not None: self.wavefield_engine.apply_phase_locked_randomization()
            self._paint_step_parameters(rng=rng, randomize=("phase-lock"=="randomizer"), strength=.55 if "phase-lock"=="randomizer" else .70, include_velocity=True, include_pitch=True, include_probability=True)
            self._paint_generated_parameters(rng=rng, source="phase-lock")
            self._phase_lock_playlist_velocity(rng,strength=.35 if "phase-lock"=="randomizer" else .70,randomize=("phase-lock"=="randomizer"))
            self._run_composition_context_engine(source="phase-lock",rng=rng)
            self.reload_active_instrument_sequencer_ui()
        except Exception as e: print(f"[phase-lock] skipped: {e}")
        finally: self._restore_global_effect_sliders(snap)

    def _mark_generated_synth_context(self, source="randomizer", rng=None):
        """Generate algorithmic synth/script context in the shared state; user values remain authoritative."""
        rng = rng or np.random.default_rng(self.get_numeric_seed())
        self.instrument_param_generated = getattr(self, "instrument_param_generated", {})
        if not hasattr(self, "instrument_scripts") or self.instrument_scripts is None: self.instrument_scripts = {}
        for i,name in enumerate(getattr(self,"instrument_names_48",[])):
            user=self.instrument_param_state.setdefault(name,{})
            ctx=float(self._contextual_numerology(name,i,i))
            gen={"tuning":float(np.clip(.9+.2*ctx,.75,1.15)),"filter":float(np.clip(.2+.7*ctx,.02,.98)),"drive":float(np.clip(.05+.55*ctx,0,.9)),"amplitude":float(np.clip(.3+.65*ctx,.05,1.0)),"duration":float(np.clip(.15+.8*(1-ctx),.03,1.0))}
            self.instrument_param_generated[name]=gen
            for k,v in gen.items(): user.setdefault(k,v)
            marker=f"# --- GENERATED {source.upper()} CONTEXT: {name} ---"
            old=str(self.instrument_scripts.get(name,"") or "")
            if marker not in old:
                self.instrument_scripts[name]=old.rstrip()+"\n\n"+marker+f"\ngenerated_ctx={ctx:.8f}\ngenerated_tuning={gen['tuning']:.8f}\ngenerated_filter={gen['filter']:.8f}\ngenerated_drive={gen['drive']:.8f}\ngenerated_amplitude={gen['amplitude']:.8f}\ngenerated_duration={gen['duration']:.8f}\n"
        return len(getattr(self,"instrument_names_48",[]))

    def _write_generated_domain_context(self, source="randomizer"):
        engine=getattr(self,"domain_eq_engine",None)
        if engine is None: return 0
        seed=self.get_numeric_seed(); n=getattr(self,"_composition_generation_counter",0)
        generated=[]
        for i,name in enumerate(getattr(self,"instrument_names_48",[])):
            q=(seed+n*7919+i*104729)%1000003
            generated.append({"name":f"{source}::{name}::{n}","axis":"time","t0":0.0,"t1":1.0,"x0":-1.0,"x1":1.0,"y0":-1.0,"y1":1.0,"logic":f"sin(t*{i%11+1}+{q}e-5)>0","equation":f"sin({i%13+1}*x+{q}e-6)*cos({i%7+1}*y+t*MEUM)","limit_lo":-1.0,"limit_hi":1.0,"weight":.2+.55*((i+n)%17)/16.0,"seed_weight":((i+n)%9)/8.0,"user_defined":False,"source":source})
        engine.domains=[d for d in engine.domains if d.get("user_defined",True)]+generated
        self.generated_domains=generated
        return len(generated)

    def _write_generated_patch_context(self, source="randomizer"):
        if not hasattr(self,"patch_connections") or self.patch_connections is None: self.patch_connections=[]
        names=list(getattr(self,"instrument_names_48",[])); n=getattr(self,"_composition_generation_counter",0)
        if not names: return 0
        existing={(c.get("source"),c.get("target")) for c in self.patch_connections if isinstance(c,dict)}
        added=0
        for i,name in enumerate(names):
            target=names[(i*7+n+1)%len(names)]
            if target==name: target=names[(i+1)%len(names)]
            if (name,target) in existing: continue
            self.patch_connections.append({"source":name,"target":target,"weight":.2+.55*((i+n)%13)/12.0,"origin":f"generated_{source}","user_defined":False})
            existing.add((name,target)); added+=1
        return added

    def _paint_operator_pattern_to_playlist(self, source="randomizer", rng=None):
        """Deterministically paint the complete 10-column playlist schema.

        User cells (``@u:`` instances) are immutable. Engine-owned material is
        regenerated from the seed + source and is fully tagged, so Randomizer /
        Phase-Lock can be removed without leaving stale cells or automation.
        Every generated row receives a value for every playlist column; inactive
        rows are explicit ``none``/zero values rather than undefined cells.
        """
        seed = int(self.get_numeric_seed() or 1)
        if rng is None:
            channel = 0x51 if "random" in source else (0xA7 if "phase" in source else 0xD3)
            rng = np.random.default_rng((seed ^ channel) & 0x7FFFFFFF)
        rows = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 32
        rows = max(1, min(1024, rows))
        if hasattr(self, 'spin_playlist_length'):
            try:
                self.spin_playlist_length.blockSignals(True)
                self.spin_playlist_length.setValue(rows)
            finally:
                self.spin_playlist_length.blockSignals(False)
        if not hasattr(self, 'master_playlist_data') or self.master_playlist_data is None:
            self.master_playlist_data = []
        while len(self.master_playlist_data) < rows:
            self.master_playlist_data.append({})
        if not hasattr(self, 'playlist_automation') or self.playlist_automation is None:
            self.playlist_automation = []
        while len(self.playlist_automation) < rows:
            self.playlist_automation.append({})
        if not hasattr(self, '_engine_generated_playlist_rows'):
            self._engine_generated_playlist_rows = set()

        names = list(getattr(self, 'instrument_names_48', []) or ["Operator"])
        table = getattr(self, 'active_paint_table', None)
        painted = 0
        source_code = {"randomizer":"R", "phase-lock":"P", "midpoint":"M", "euclidean":"E", "seeded":"S"}.get(source, "G")

        def user_tokens(cell):
            return [p.strip() for p in str(cell or '').split(',') if '@u:' in p]

        def table_set(r, c, text):
            if table is None:
                return
            tw = getattr(table, 'table_widget', table)
            try:
                if hasattr(table, 'set_cell_item'):
                    table.set_cell_item(r, c, QTableWidgetItem(str(text)))
                elif hasattr(tw, 'setItem'):
                    tw.setItem(r, c, QTableWidgetItem(str(text)))
            except Exception:
                pass

        for r in range(rows):
            e = self.master_playlist_data[r]
            if not isinstance(e, dict):
                e = {}
                self.master_playlist_data[r] = e

            # Preserve only explicitly user-owned instances from the previous row.
            users = list(e.get('user_instances') or [])
            old_ops = e.get('operators_csv', e.get('operator', ''))
            if not users:
                users = user_tokens(old_ops)

            # Remove previous engine automation/identity before regeneration.
            if e.get('generated_by_engine'):
                for k in list(e.keys()):
                    if k not in ('user_instances',):
                        e.pop(k, None)
            if isinstance(self.playlist_automation[r], dict) and self.playlist_automation[r].get('generated_by_engine'):
                self.playlist_automation[r] = {}

            # Seed-stable but musically varied density, operator count, and timing.
            source_hash = sum((j + 1) * ord(ch) for j, ch in enumerate(str(source))) & 0x7FFFFFFF
            row_key = (seed ^ ((r + 1) * 0x9E3779B1) ^ source_hash) & 0x7FFFFFFF
            rr = np.random.default_rng(row_key)
            active = bool(rr.random() < (0.62 if source == 'midpoint' else 0.70))
            n_inst = int(rr.integers(2, min(6, len(names)) + 1)) if names else 1
            idxs = list(rr.choice(len(names), size=min(n_inst, len(names)), replace=False)) if names else [0]
            eng_ops = [names[i] for i in idxs]
            tag = f"@e:{source[:4]}:{seed & 0xFFFFF:05x}:{r:03d}"
            t_off = (r * (0.125 + 0.031 * MEUM_NORM) + float(rr.uniform(-0.045, 0.045)))
            if not active:
                t_off = r * (0.125 + 0.031 * MEUM_NORM)
            velocity = float(np.clip(0.42 + 0.48 * (0.5 + 0.5 * np.sin((r + 1) * MEUM + (seed % 997) * 0.017)), 0.08, 0.98)) if active else 0.0
            target = ("eqr", "fractalizer", "pkp_decay", "filter", "drive")[int(rr.integers(0, 5))] if active else "none"
            amount = float(np.clip(0.22 + 0.62 * rr.random(), 0.0, 0.95)) if active else 0.0
            direction = float(np.sin((r + 1) * MEUM_INV + (seed % 991) * 0.013)) if active else 0.0
            coverage_map = {op: float(np.clip(0.30 + 0.55 * rr.random(), 0.0, 1.0)) for op in eng_ops}
            coverage = "|".join(f"{k}:{v:.0%}" for k, v in coverage_map.items()) if active else "0%"
            partner = eng_ops[1] if active and len(eng_ops) > 1 else ""
            script = ""
            if eng_ops and hasattr(self, 'instrument_scripts'):
                script = str((self.instrument_scripts.get(eng_ops[0]) or '').splitlines()[0]).strip()
            if not script:
                script = f"Meum:{source}:seed={seed}:row={r}"

            engine_csv = ", ".join(f"{op}{tag}" for op in eng_ops)
            combined_csv = ", ".join(users + ([engine_csv] if engine_csv else []))
            multi_seq = ", ".join(eng_ops)
            position = f"e:{t_off:.4f}s"
            fields = {
                'time_marker': position,
                'operator': (users[0] if users else (eng_ops[0] if eng_ops else '')),
                'operators': list(dict.fromkeys(users + eng_ops)),
                'operators_csv': combined_csv,
                'script_tag': script,
                'velocity': velocity,
                'effect_target': target,
                'auto_amount': f"{amount * 100:.1f}%",
                'direction_vector': f"{direction:+.4f}",
                'multi_seq': multi_seq,
                'coverage_map': coverage_map,
                'coverage': coverage,
                'blend_partner': partner,
                'time_offset': float(t_off),
                'position': position,
                'generated_source': source,
                'generated_by_engine': True,
                'velocity_user_locked': False,
                'active': active,
            }
            e.update(fields)
            if users:
                e['user_instances'] = users
            self._engine_generated_playlist_rows.add(r)

            self.playlist_automation[r] = {
                'generated_by_engine': True,
                'operator': eng_ops[0] if eng_ops else '',
                'operators': list(eng_ops),
                'param': target,
                'amount': amount,
                'direction': 1.0 if direction >= 0 else -1.0,
                'coverage': float(np.mean(list(coverage_map.values()))) if coverage_map else 0.0,
                'overlap': float(min(coverage_map.values())) if len(coverage_map) > 1 else 0.0,
                'blend_percent': float(np.clip(50.0 + 35.0 * np.sin((r + 1) * MEUM_NORM + seed * 0.001), 0.0, 100.0)),
                'partner': partner,
                'mode': f"engine:{source}",
                'position': position,
                'seed': seed,
                'row': r,
            }

            # Paint every playlist cell, even before the window has been opened.
            table_set(r, 0, fields['time_marker'])
            table_set(r, 1, fields['operators_csv'])
            table_set(r, 2, fields['script_tag'])
            table_set(r, 3, f"{velocity * 100:.1f}%")
            table_set(r, 4, target)
            table_set(r, 5, fields['auto_amount'])
            table_set(r, 6, fields['direction_vector'])
            table_set(r, 7, multi_seq)
            table_set(r, 8, coverage)
            table_set(r, 9, partner)
            painted += 1

        if table is not None:
            try:
                getattr(table, 'table_widget', table).viewport().update()
            except Exception:
                pass
        return painted

    def _run_composition_context_engine(self, source="randomizer", rng=None):
        # Generated wave/effect topology exists only as an explicit engine output.
        # Plain Play/Export never inserts hidden synth effects, domains, or patches.
        explicit_engine = source in ("randomizer", "phase-lock", "midpoint", "euclidean", "seeded")
        if explicit_engine:
            self._mark_generated_synth_context(source=source, rng=rng)
            self._write_generated_domain_context(source=source)
            self._write_generated_patch_context(source=source)
        return self._paint_operator_pattern_to_playlist(source=source, rng=rng)

    def init_ui_components(self):
        high_contrast_stylesheet = """
            QMainWindow, QDialog {
                background-color: #060606;
                color: #e8eef4;
                font-family: sans-serif;
                font-size: 10pt;
            }
            QWidget#GrooveboxCentral, QWidget#ParametricMathBackground {
                background: transparent;
            }
            QGroupBox {
                background-color: rgba(8, 10, 14, 150);
                color: #e8eef4;
                border: 1px solid #2a3340;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QPushButton {
                background-color: #121212;
                color: #00ffff;
                border: 2px solid #00ffff;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00ffff;
                color: #060606;
            }
            QPushButton:checked {
                background-color: #00ffff;
                color: #060606;
                border: 2px solid #ffffff;
            }
            QLabel { color: #e8eef4; font-weight: bold; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
                background-color: #12181e;
                color: #ffffff;
                border: 2px solid #444444;
                border-radius: 3px;
                padding: 3px;
                selection-background-color: #00aaaa;
                selection-color: #061018;
            }
            QComboBox {
                background-color: #181818;
                color: #e8eef4;
                border: 2px solid #444444;
                border-radius: 3px;
                padding: 3px 8px;
                combobox-popup: 0;
                min-height: 22px;
            }
            QComboBox:on { background-color: #222830; color: #e8eef4; }
            QComboBox QAbstractItemView {
                background-color: #181818;
                color: #e8eef4;
                selection-background-color: #00aaaa;
                selection-color: #061018;
                border: 1px solid #444444;
                outline: 0;
            }
            QComboBox QAbstractItemView::item {
                min-height: 22px;
                color: #e8eef4;
                background-color: #181818;
                padding: 3px 8px;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #00aaaa;
                color: #061018;
            }
            QComboBox::drop-down {
                background-color: #242a32;
                border-left: 1px solid #555555;
                width: 22px;
            }
            QProgressBar {
                background-color: #12181e;
                color: #e8eef4;
                border: 1px solid #2a3340;
                border-radius: 4px;
                text-align: center;
                min-height: 16px;
                max-height: 18px;
            }
            QProgressBar#playProgressBar::chunk { background-color: #00c8a8; border-radius: 3px; }
            QProgressBar#exportProgressBar::chunk { background-color: #ff9a3c; border-radius: 3px; }
            QProgressBar::chunk { background-color: #00c8a8; border-radius: 3px; }
        """
        if QApplication.instance():
            QApplication.instance().setStyleSheet(high_contrast_stylesheet)
        self.setStyleSheet(high_contrast_stylesheet)

        central_widget = self.centralWidget()
        if central_widget is None:
            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)
        central_widget.setObjectName("GrooveboxCentral")
        central_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        central_widget.setAutoFillBackground(False)
        central_widget.setStyleSheet("background: transparent;")

        master_container = central_widget.layout()
        if master_container is None:
            master_container = QVBoxLayout(central_widget)
        else:
            while master_container.count():
                item = master_container.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        master_container.setSpacing(6)
        master_container.setContentsMargins(8, 8, 8, 8)

        self.transport_layout = QHBoxLayout()
        self.btn_play = QPushButton("▶ PLAY Audiovisual Track")
        self.btn_stop = QPushButton("⏹ Stop")
        self.lbl_bpm = QLabel("BPM:")
        self.spin_bpm = QDoubleSpinBox()
        self.spin_bpm.setRange(0.0, 512.0)
        self.spin_bpm.setDecimals(3)
        self.spin_bpm.setSingleStep(0.1)
        self.spin_bpm.setValue(120.0)

        self.instrument_selector_dropdown = QComboBox()
        self.instrument_selector_dropdown.addItems(self.instrument_names_48)
        self.instrument_selector_dropdown.currentIndexChanged.connect(self.on_instrument_switched)
        # READABILITY_FIX: an uncapped QComboBox in this QHBoxLayout was
        # expanding to fill available space and squeezing the neighboring
        # buttons' text (e.g. "Seeded Live Randomizer" clipping to
        # "ded Live Rando"). Capping its width lets siblings keep their labels.
        self.instrument_selector_dropdown.setMaximumWidth(220)

        # Live regenerating toggles (not one-shot masks).
        # Styles use QPushButton:checked so ON/OFF color-shifts without clearing the sheet.
        self._style_toggle_euclidean = (
            "QPushButton { background-color: #0f1a14; color: #66ffaa; font-weight: bold; "
            "border: 2px solid #66ffaa; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:checked { background-color: #00aa55; color: #ffffff; border-color: #ffffff; }"
            "QPushButton:hover { background-color: #1a2e22; }"
        )
        self._style_toggle_randomizer = (
            "QPushButton { background-color: #1a1608; color: #f5d97d; font-weight: bold; "
            "border: 2px solid #f5d97d; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:checked { background-color: #e6a800; color: #120800; border-color: #ffffff; }"
            "QPushButton:hover { background-color: #2a2210; }"
        )
        self._style_toggle_nullock = (
            "QPushButton { background-color: #1a1020; color: #ff66cc; font-weight: bold; "
            "border: 2px solid #ff66cc; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:checked { background-color: #ff66cc; color: #120818; border-color: #ffffff; }"
            "QPushButton:hover { background-color: #2a1830; }"
        )

        self.btn_idealize_rhythm = QPushButton("✨ Euclidean Live Lock")
        self.btn_idealize_rhythm.setCheckable(True)
        self.btn_idealize_rhythm.setChecked(False)
        self.btn_idealize_rhythm.setStyleSheet(self._style_toggle_euclidean)
        self.btn_idealize_rhythm.setToolTip("Toggle live Euclidean / phase-lock fill. Green = ON.")

        self.btn_seeded_randomize = QPushButton("🎲 Seeded Live Randomizer")
        self.btn_seeded_randomize.setCheckable(True)
        self.btn_seeded_randomize.setChecked(False)
        self.btn_seeded_randomize.setStyleSheet(self._style_toggle_randomizer)
        self.btn_seeded_randomize.setToolTip("Toggle live seeded harmonic randomizer. Amber = ON.")

        self.chk_user_program_only = QCheckBox("User program only")
        self.chk_user_program_only.setToolTip(
            "When ON, live randomizer/phase-lock engines are suspended — hear only what you wrote."
        )
        self.btn_save_project = QPushButton("💾 Save Project")
        self.btn_load_project = QPushButton("📂 Load Project")
        self.btn_keyboard = QPushButton("🎹 Keyboard / Test")
        self.btn_trigger_all = QPushButton("⚡ Trigger All")

        # =====================================================================
        # SEED_SCRIPT_EDITOR_FEATURE
        # The global seed is intentionally a large, scrollable script field.
        # Revert this block to QLineEdit if a compact single-line seed is ever
        # preferred again. All code reads the field through _seed_text().
        # =====================================================================
        self.input_seed_val = QTextEdit()
        # USER-CONTROLLED FIELD: never assign a random/default seed here.
        self.input_seed_val.setPlainText("")
        self.input_seed_val.setToolTip(
            "Global parametric/script seed. Enter expressions, multiline scripts, "
            "irrational constants, or symbolic geometry. The field scrolls."
        )
        self.input_seed_val.setAcceptRichText(False)
        self.input_seed_val.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.input_seed_val.setMinimumSize(360, 110)
        self.input_seed_val.setMaximumWidth(520)
        self.input_seed_val.setMaximumHeight(150)
        self.input_seed_val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # White seed text on dark field so boot seeds and scripts are readable.
        self.input_seed_val.setStyleSheet(
            "QTextEdit {"
            " background-color: #12181e;"
            " color: #ffffff;"
            " border: 2px solid #3a4550;"
            " border-radius: 4px;"
            " padding: 6px;"
            " font-family: Consolas, 'Courier New', monospace;"
            " font-size: 11pt;"
            " selection-background-color: #00aaaa;"
            " selection-color: #061018;"
            "}"
        )

        # NOTE: transport-bar WAV-only export button removed — the single
        # EXPORT control lives next to the 2.5D video panel (self.btn_export,
        # built later as a QToolButton with an Export Video action).
        self.btn_help = QPushButton("❓ README / Help")
        self.btn_help.setStyleSheet("background-color: #1f242c; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d; padding: 4px 10px;")

        # Left: square-ish script editor. Right: all other global controls.
        self.global_geometry_layout = QHBoxLayout()
        seed_panel = QVBoxLayout()
        seed_panel.addWidget(QLabel("GLOBAL SEED / PARAMETRIC SCRIPT (USER CONTROLLED):"))
        seed_panel.addWidget(self.input_seed_val, 1)
        seed_panel.addWidget(self.btn_help)
        self.global_geometry_layout.addLayout(seed_panel, 1)

        self.global_controls_side = QVBoxLayout()
        self.global_controls_side.setSpacing(6)
        self.global_controls_side.setContentsMargins(0, 0, 0, 0)
        self.global_controls_side.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.global_controls_side.addWidget(QLabel("GLOBAL CONTROLS"), 0, Qt.AlignmentFlag.AlignTop)
        self.global_geometry_layout.addLayout(self.global_controls_side, 1)
        self.global_geometry_layout.setAlignment(self.global_controls_side, Qt.AlignmentFlag.AlignTop)

        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_idealize_rhythm.toggled.connect(self._on_unified_phase_lock_toggled)
        self.btn_seeded_randomize.toggled.connect(self._on_unified_randomizer_toggled)
        self.chk_user_program_only.toggled.connect(self._on_user_program_only_toggled)
        self.btn_save_project.clicked.connect(self.save_project_dialog)
        self.btn_load_project.clicked.connect(self.load_project_dialog)
        self.btn_keyboard.clicked.connect(self.open_keyboard_test_window)
        self.btn_trigger_all.clicked.connect(self.trigger_all_instruments_hit)

        self.transport_layout.addWidget(self.btn_play)
        self.transport_layout.addWidget(self.btn_stop)
        self.transport_layout.addWidget(self.lbl_bpm)
        self.transport_layout.addWidget(self.spin_bpm)
        self.transport_layout.addWidget(QLabel("Select Instrument"))
        self.instrument_selector_dropdown.setMinimumWidth(260)
        self.instrument_selector_dropdown.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.transport_layout.addWidget(self.instrument_selector_dropdown)
        self.transport_layout.addWidget(self.btn_keyboard)
        self.transport_layout.addWidget(self.btn_trigger_all)
        self.transport_layout.addStretch(1)

        # LAYOUT_WRAP_FIX: this row used to hold every remaining transport
        # control (randomizer/lock toggles, checkbox, save/load) on one single
        # QHBoxLayout, which forced Qt to clip button/label text once the
        # window was narrower than the sum of everything's natural width
        # (visible as "ded Live Rando", "uclidean Live L", etc). Splitting the
        # tail onto its own row fixes that regardless of font size.
        # MERGED_ENGINE_UI: one Randomizer + one Phase-Lock live in GLOBAL COMPOSITION.
        # Transport row keeps user-program / save-load only (no duplicate engine toggles).
        self.transport_layout_row2 = QHBoxLayout()
        self.transport_layout_row2.addWidget(self.chk_user_program_only)
        self.transport_layout_row2.addStretch(1)
        self.transport_layout_row2.addWidget(self.btn_save_project)
        self.transport_layout_row2.addWidget(self.btn_load_project)
        # Keep buttons alive for any legacy signal paths, but hidden
        self.btn_seeded_randomize.setVisible(False)
        self.btn_idealize_rhythm.setVisible(False)

        # Live engine timers
        self._live_euclid_timer = QTimer(self)
        self._live_euclid_timer.setInterval(2000)
        self._live_euclid_timer.timeout.connect(self._live_composition_tick)
        self._live_seeded_timer = QTimer(self)
        self._live_seeded_timer.setInterval(2500)
        self._live_seeded_timer.timeout.connect(self._live_composition_tick)
        self._live_engine_signatures = {}
        self._live_engine_update_guard = False

        # Keep transport/global controls beside the script field rather than
        # consuming the width needed by the large script editor.
        self.global_controls_side.addLayout(self.transport_layout)
        self.global_controls_side.addLayout(self.transport_layout_row2)
        master_container.addLayout(self.global_geometry_layout)

        self.top_layout = QHBoxLayout()
        # LAYOUT_WRAP_FIX: this used to be one QHBoxLayout holding every
        # global-media/arrangement control, which clipped text such as
        # "Global Playli", "Base Global Frequ", "Load WAV Carr" once the
        # window got narrower than the sum of all widget widths. Split into
        # two stacked rows instead.
        self.top_layout_row2 = QHBoxLayout()
        self.mode_combo = QComboBox()
        # Global / all instruments active is the default
        self.mode_combo.addItems(["Mode: Cross-Loaded Ecosystem (Global)", "Mode: Single Instrument"])
        self.mode_combo.setCurrentIndex(0)

        # Global Playlist Switch added to main layout
        self.chk_global_playlist = QCheckBox("🌐 Global Playlist Arrangement Drive")
        self.chk_global_playlist.setChecked(True)
        self.chk_global_playlist.setStyleSheet("color: #00ffff; font-weight: bold;")


        self.slider_eqr = QSlider(Qt.Orientation.Horizontal)
        self.slider_eqr.setRange(0, 100)
        self.slider_eqr.setValue(0)
        self.slider_fractalizer = QSlider(Qt.Orientation.Horizontal)
        self.slider_fractalizer.setRange(0, 100)
        self.slider_fractalizer.setValue(33)
        self.slider_pkp_decay = QSlider(Qt.Orientation.Horizontal)
        self.slider_pkp_decay.setRange(0, 1000)
        self.slider_pkp_decay.setValue(500)

        self.chk_pkp_automod = QCheckBox("PKP Envelope Follower")
        self.chk_pkp_automod.setChecked(False)
        self.chk_pkp_automod.setStyleSheet("QCheckBox { color: #ffffff; }")

        self.top_layout.addWidget(self.mode_combo)
        self.top_layout.addWidget(self.chk_global_playlist)
        self.top_layout.addWidget(QLabel("Base Global Frequency:"))
        self.spin_base_frequency = QDoubleSpinBox()
        self.spin_base_frequency.setRange(0.0, 50000.0)
        self.spin_base_frequency.setDecimals(4)
        self.spin_base_frequency.setSingleStep(0.1)
        self.spin_base_frequency.setValue(432.0)
        self.spin_tuning = self.spin_base_frequency  # compatibility alias
        self.top_layout.addWidget(self.spin_base_frequency)
        # Keep the primary effect sliders in their own visible row so they cannot
        # be squeezed out by the long global transport/media controls.
        global_fx_group = QGroupBox("GLOBAL EFFECTS")
        global_fx_group.setToolTip("Global EQR, Fractallizer, and PKP effect controls.")
        global_fx_layout = QHBoxLayout(global_fx_group)
        global_fx_layout.setContentsMargins(8, 4, 8, 4)
        global_fx_layout.setSpacing(8)
        global_fx_layout.addWidget(QLabel("EQR:"))
        global_fx_layout.addWidget(self.slider_eqr, 1)
        global_fx_layout.addWidget(QLabel("Fractallizer:"))
        global_fx_layout.addWidget(self.slider_fractalizer, 1)
        global_fx_layout.addWidget(QLabel("PKP Decay:"))
        global_fx_layout.addWidget(self.slider_pkp_decay, 1)
        global_fx_layout.addWidget(self.chk_pkp_automod)
        self.global_effects_group = global_fx_group

        # POWER_V3_GLOBAL_CONTROLS: construct global composition controls BEFORE
        # any layout references them. Playlist, Randomizer, and Phase-Lock are
        # global operators on the whole composition state, never local widgets.
        def _make_global_operator_button(text, tooltip, checkable=False, active_color="#00ffcc"):
            b = QPushButton(text)
            b.setToolTip(tooltip)
            b.setMinimumHeight(38)
            b.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            b.setCheckable(bool(checkable))
            if checkable:
                b.setStyleSheet(
                    "QPushButton { background-color:#121212; color:#f5d97d; border:2px solid #f5d97d; border-radius:6px; padding:6px 10px; font-weight:bold; } "
                    f"QPushButton:checked {{ background-color:{active_color}; color:#101010; border:2px solid {active_color}; }} "
                    "QPushButton:hover { background-color:#282018; } QPushButton:pressed { background-color:#ff6b00; color:white; }"
                )
            else:
                b.setStyleSheet(
                    "QPushButton { background-color:#121212; color:#f5d97d; border:2px solid #f5d97d; border-radius:6px; padding:6px 10px; font-weight:bold; } "
                    "QPushButton:hover { background-color:#282018; } QPushButton:pressed { background-color:#ff6b00; color:white; }"
                )
            return b

        self.btn_view_playlist = _make_global_operator_button(
            "📜 PLAYLIST",
            "Open the global arrangement, velocity, automation, and paint context"
        )
        self.btn_local_randomize = _make_global_operator_button(
            "🎲 RANDOMIZER",
            "Unified randomizer (seeded harmonics + multi-instance playlist paint). One predictive step.",
            checkable=True, active_color="#00d084"
        )
        self.btn_local_phase_lock = _make_global_operator_button(
            "🔒 PHASE-LOCK",
            "Unified phase-lock (Euclidean geometry + wavefield). One coordinated step.",
            checkable=True, active_color="#00bfff"
        )

        global_context_group = QGroupBox("GLOBAL COMPOSITION")
        global_context_group.setToolTip("Global playlist, randomization, and Euclidean phase-lock controls.")
        global_context_layout = QHBoxLayout(global_context_group)
        global_context_layout.setContentsMargins(8, 4, 8, 4)
        global_context_layout.setSpacing(8)
        global_context_layout.addWidget(self.btn_view_playlist)
        global_context_layout.addWidget(self.btn_local_randomize)
        global_context_layout.addWidget(self.btn_local_phase_lock)
        global_context_layout.addStretch(1)
        self.global_composition_group = global_context_group

        self.global_controls_side.addWidget(self.global_effects_group, 0, Qt.AlignmentFlag.AlignTop)
        self.global_controls_side.addWidget(self.global_composition_group, 0, Qt.AlignmentFlag.AlignTop)
        self.global_controls_side.addLayout(self.top_layout)
        self.global_controls_side.addLayout(self.top_layout_row2)

        # =====================================================================
        # LOCAL_CONTEXT_UI — only instrument-local controls remain here.
        # They are deliberately square and visually separated from GLOBAL.
        # Domain equations live here too because they are most useful as a
        # contextual modulation layer; their engine remains global-capable.
        # =====================================================================
        local_context_group = QGroupBox("LOCAL CONTEXT — ACTIVE INSTRUMENT")
        local_context_group.setToolTip(
            "Controls in this panel address the selected instrument/context. "
            "They do not belong to the global transport plane."
        )
        local_context_layout = QHBoxLayout(local_context_group)
        local_context_layout.setSpacing(8)

        self.btn_edit_synth = self._make_local_context_button("∿\nSYNTH", "Edit synth settings and wavetable for the active instrument")
        self.btn_script_inst = self._make_local_context_button("λ\nSCRIPT", "Edit the script attached to the active instrument")
        self.btn_view_patchbay = self._make_local_context_button("⬡\nMODULAR", "Open modular routing for the active instrument context")
        self.btn_domain_eq = self._make_integral_domain_button("Edit time/space equations used as contextual modulation")

        # POWER_V3_GLOBAL_CONTROLS: buttons were constructed above so the Global
        # panel can safely reference them before the Local panel is assembled.

        self.btn_edit_synth.clicked.connect(lambda: self.spawn_floating_window('synth_editor_window', "Synth Settings & Wavetable Interface"))
        self.btn_script_inst.clicked.connect(lambda: self.spawn_floating_window('script_editor_window', "Instrument Script Editor"))
        self.btn_view_patchbay.clicked.connect(lambda: self.spawn_floating_window('patch_bay_dialog', "Advanced Modular Patch Bay & Visualizer"))
        self.btn_domain_eq.clicked.connect(self.open_domain_equation_editor)
        self.btn_view_playlist.clicked.connect(lambda: self.spawn_floating_window('playlist_window', "Unquantized Playlist & Paintbrush Window"))
        self.btn_local_randomize.toggled.connect(self._on_unified_randomizer_toggled)
        self.btn_local_phase_lock.toggled.connect(self._on_unified_phase_lock_toggled)
        self.btn_help.clicked.connect(self.open_help_readme)

        for b in (self.btn_edit_synth, self.btn_script_inst, self.btn_view_patchbay, self.btn_domain_eq):
            local_context_layout.addWidget(b)
        local_context_layout.addStretch(1)
        master_container.addWidget(local_context_group)

        # Global playlist capacity belongs with global variables, not the pattern editor.
        self.spin_playlist_length = QSpinBox()
        self.spin_playlist_length.setRange(1, 1024)
        self.spin_playlist_length.setValue(96)
        self.top_layout_row2.addWidget(QLabel("Playlist Rows:"))
        self.top_layout_row2.addWidget(self.spin_playlist_length)
        self.top_layout_row2.addWidget(QLabel("Global Convolve:"))
        self.spin_global_convolve = QDoubleSpinBox()
        self.spin_global_convolve.setRange(0.0, 100.0)
        self.spin_global_convolve.setDecimals(2)
        self.spin_global_convolve.setSuffix("%")
        self.spin_global_convolve.setValue(0.0)
        self.spin_global_convolve.setFixedWidth(82)
        self.spin_global_convolve.setToolTip("Cross-convolve the structural wave result; user-edited material remains protected.")
        self.top_layout_row2.addWidget(self.spin_global_convolve)
        self.slider_global_convolve = self.spin_global_convolve  # compatibility alias

        # =====================================================================
        # CONVOLVE_FIT_FEATURE — global WAV carrier + adaptive spectral fitting
        # =====================================================================
        self.chk_convolve_fit = QCheckBox("convolve fit")
        self.chk_convolve_fit.setChecked(False)
        self.chk_convolve_fit.setToolTip(
            "Fit voices without net-effect user activity toward the loaded WAV "
            "carrier/reference. User-defined voices remain protected."
        )
        self.top_layout_row2.addWidget(self.chk_convolve_fit)

        self.btn_load_wav = QPushButton("📂 Load WAV Carrier")
        self.btn_load_wav.setToolTip("Load a WAV file as the global carrier/reference waveform.")
        self.btn_load_wav.clicked.connect(self.load_wav_carrier_dialog)
        self.top_layout_row2.addWidget(self.btn_load_wav)

        self.lbl_wav_carrier = QLabel("WAV: none")
        self.lbl_wav_carrier.setMinimumWidth(130)
        self.top_layout_row2.addWidget(self.lbl_wav_carrier)

        # MEDIA_IMPORT_FEATURE — one global entry point for WAV or video carriers.
        self.btn_load_media = QPushButton("🎞 Load WAV / Video")
        self.btn_load_media.setToolTip(
            "Load WAV audio or a video file. Video audio becomes the spectral carrier; "
            "the video stream can be blended back into the final MP4 export."
        )
        self.btn_load_media.clicked.connect(self.load_media_dialog)
        self.top_layout_row2.addWidget(self.btn_load_media)
        self.top_layout_row2.addStretch(1)

        sizing_layout = QHBoxLayout()
        sizing_layout.addWidget(QLabel("Pattern / STEP Length:"))
        self.spin_seq_length = QSpinBox()
        self.spin_seq_length.setRange(1, 1024)
        self.spin_seq_length.setValue(48)
        sizing_layout.addWidget(self.spin_seq_length)

        self.chk_multi_seq_load = QCheckBox("Allow Multiple Sequence Load & Paint")
        self.chk_multi_seq_load.setChecked(True)
        self.chk_multi_seq_load.setToolTip(
            "When on, load/paint may write into more than one sequence slot. "
            "Reserved control — wiring is not invented here."
        )
        sizing_layout.addWidget(self.chk_multi_seq_load)
        sizing_layout.addStretch(1)

        sizing_container = QWidget()
        sizing_container.setLayout(sizing_layout)
        master_container.addWidget(sizing_container)

        self.top_sequencer = QWidget()
        seq_inner = QVBoxLayout(self.top_sequencer)
        seq_inner.setContentsMargins(0, 0, 0, 0)

        seq_header_layout = QHBoxLayout()
        # Compact live-jam controls: the instrument selector lives in the global transport above.
        # Keep the PKP NullLock Boost button and its live-jam amount control here.

        # PKP BOOST — arm global note-triggered NullLock layer + one-shot audition.
        # Boost amount scales the global PKP layer in the mixdown (0.5× … 2.0×).
        self.pkp_boost_amount = 1.0
        self.btn_pkp_nullock_boost = QPushButton("PKP Nulllock Boost (using Current Instrument, for Live Playback Effect)")
        self.btn_pkp_nullock_boost.setMinimumWidth(390)
        self.btn_pkp_nullock_boost.setCheckable(False)
        self.btn_pkp_nullock_boost.setToolTip("Momentary one-shot PKP remix burst; never arms a sustained layer.")
        self.btn_pkp_nullock_boost.setStyleSheet(
            "QPushButton { background-color:#1a1020; color:#ff66cc; font-weight:bold; border:2px solid #ff66cc; border-radius:4px; padding:4px 10px; }"
            "QPushButton:hover { background-color:#2a1830; }"
            "QPushButton:pressed { background-color:#ff66cc; color:#120818; border-color:#ffffff; }"
        )
        self.btn_pkp_nullock_boost.clicked.connect(self._on_pkp_nullock_boost_clicked)
        seq_header_layout.setSpacing(6)
        seq_header_layout.setContentsMargins(0, 0, 0, 0)
        seq_header_layout.addWidget(self.btn_pkp_nullock_boost, 0, Qt.AlignmentFlag.AlignVCenter)

        self.slider_pkp_boost = QSlider(Qt.Orientation.Horizontal)
        self.slider_pkp_boost.setRange(50, 200)  # 0.5× … 2.0×
        self.slider_pkp_boost.setValue(100)
        self.slider_pkp_boost.setFixedWidth(88)
        self.slider_pkp_boost.setToolTip("NullLock boost amount (50%–200%) applied to the global PKP layer.")
        self.slider_pkp_boost.valueChanged.connect(self._on_pkp_boost_amount_changed)
        seq_header_layout.addWidget(self.slider_pkp_boost, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lbl_pkp_boost = QLabel("100%")
        self.lbl_pkp_boost.setStyleSheet("color: #ff66cc; font-weight: bold; min-width: 40px;")
        seq_header_layout.addWidget(self.lbl_pkp_boost)

        seq_inner.addLayout(seq_header_layout)

        # PKP is an audition/play action, not a dropdown, timeline event, or independent clock.
        self.pkp_pad_bank_active = False
        self.pkp_current_step = 0

        self.steps_layout_widget = QWidget()
        self.steps_inner_layout = QHBoxLayout(self.steps_layout_widget)
        self.steps_inner_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_inner_layout.setSpacing(3)
        self.seq_step_buttons = []

        self.rebuild_sequencer_steps(self.spin_seq_length.value())
        self.spin_seq_length.valueChanged.connect(lambda val: self.rebuild_sequencer_steps(val))
        self.spin_seq_length.valueChanged.connect(self._on_live_source_changed)
        self.spin_playlist_length.valueChanged.connect(self._on_live_source_changed)
        self.spin_bpm.valueChanged.connect(self._on_live_source_changed)
        self.input_seed_val.textChanged.connect(self._on_live_source_changed)
        # LOCAL_CONTEXT_ISOLATION: changing the active instrument only changes context;
        # it must never re-randomize or phase-fill the sequence.

        self.steps_scroll = QScrollArea()
        self.steps_scroll.setWidgetResizable(True)
        self.steps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.steps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.steps_scroll.setWidget(self.steps_layout_widget)
        self.steps_scroll.setMinimumHeight(112)
        seq_inner.addWidget(self.steps_scroll, stretch=1)

        # Step editor is a floating/teleporting inspector. It follows the selected
        # pad and places itself above or below the pad so the controls remain visible.
        self.step_editor_popup = QWidget(self.steps_scroll.viewport())
        self.step_editor_popup.setObjectName("stepEditorPopup")
        self.step_editor_popup.setStyleSheet(
            "#stepEditorPopup { background:#0b1116; border:2px solid #f5d97d; "
            "border-radius:8px; padding:6px; } QLabel { color:#ffffff; font-weight:bold; }"
        )
        self.step_editor_popup.setFixedSize(430, 42)
        step_edit = QHBoxLayout(self.step_editor_popup)
        step_edit.setContentsMargins(8, 6, 8, 6)
        self.lbl_selected_step = QLabel("Step: —")
        self.lbl_selected_step.setStyleSheet("color: #f5d97d; font-weight: bold;")
        step_edit.addWidget(self.lbl_selected_step)
        step_edit.addWidget(QLabel("Amp/Vel:"))
        self.slider_step_amp = QSlider(Qt.Orientation.Horizontal)
        self.slider_step_amp.setRange(0, 100)
        self.slider_step_amp.setValue(100)
        self.slider_step_amp.setFixedWidth(78)
        self.slider_step_amp.valueChanged.connect(self._on_step_amp_slider)
        step_edit.addWidget(self.slider_step_amp)
        self.lbl_step_amp = QLabel("100%")
        step_edit.addWidget(self.lbl_step_amp)
        step_edit.addWidget(QLabel("Pitch:"))
        self.slider_step_pitch = QSlider(Qt.Orientation.Horizontal)
        self.slider_step_pitch.setRange(25, 400)
        self.slider_step_pitch.setValue(100)
        self.slider_step_pitch.setFixedWidth(78)
        self.slider_step_pitch.valueChanged.connect(self._on_step_pitch_slider)
        step_edit.addWidget(self.slider_step_pitch)
        self.lbl_step_pitch = QLabel("1.00×")
        step_edit.addWidget(self.lbl_step_pitch)
        self.step_editor_popup.hide()
        self.selected_step_idx = None

        # POWER_V3_VISUAL_LAYOUT: master volume is directly above the shorter
        # visualizer selector so the two controls read as one visual monitoring group.
        master_vol_row = QHBoxLayout()
        master_vol_row.addWidget(QLabel("Master Volume:"))
        self.slider_master_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_master_vol.setRange(0, 100)
        self.slider_master_vol.setValue(80)
        self.slider_master_vol.setFixedWidth(180)
        self.slider_master_vol.valueChanged.connect(self._on_master_vol_changed)
        master_vol_row.addWidget(self.slider_master_vol)
        self.lbl_master_vol = QLabel("80%")
        self.lbl_master_vol.setStyleSheet("color: #f5d97d;")
        master_vol_row.addWidget(self.lbl_master_vol)
        master_vol_row.addStretch(1)
        seq_inner.addLayout(master_vol_row)

        vis_row = QHBoxLayout()
        vis_row.addWidget(QLabel("Visualizer:"))
        self.viz_mode_combo = QComboBox()
        self.viz_mode_combo.addItems([
            "Master Oscilloscope",
            "Current Effected Waveform",
            "Overall Wave Pattern",
            "Per-Instrument Activity",
        ])
        self.viz_mode_combo.setFixedWidth(190)
        self.viz_mode_combo.currentIndexChanged.connect(self._on_viz_mode_changed)
        vis_row.addWidget(self.viz_mode_combo)
        vis_row.addStretch(1)
        seq_inner.addLayout(vis_row)

        master_container.addWidget(self.top_sequencer)

        # Merged visualizer + 2.5D video synth viewer
        self.video_synth_engine = VideoSynthEngine(n_instruments=48)
        self.video_synth_viewer = VideoSynthViewer(self, engine=self.video_synth_engine)
        self.video_synth_viewer.setMinimumHeight(220)
        self.video_synth_viewer.set_mode(0)
        if not isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope):
            self.visual_oscilloscope = VisualOscilloscope(self)
            self.visual_oscilloscope.setMinimumHeight(100)
            self.visual_oscilloscope.setMaximumHeight(120)

        # EXPORT control is placed at the top of the 2D/2.5D video panel row.
        # Offers three export modes via a dropdown menu on one button:
        #   - Video only (no audio track muxed in)
        #   - Audio only (.wav mixdown, reuses export_mixdown_dialog)
        #   - Video + Audio (video with the rendered mixdown muxed in)
        scope_bar = QHBoxLayout()

        self.btn_export = QToolButton()
        self.btn_export.setText("⬇ EXPORT")
        self.btn_export.setStyleSheet("QToolButton { color: #ffffff; font-weight: bold; } QMenu { color: #ffffff; } QMenu::item { color: #ffffff; }")
        self.btn_export.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        export_menu = QMenu(self.btn_export)
        export_video_only_action = export_menu.addAction("Video only")
        export_audio_only_action = export_menu.addAction("Audio only (.wav)")
        export_video_audio_action = export_menu.addAction("Video + Audio")
        export_video_only_action.triggered.connect(lambda: self.export_video_dialog(include_audio=False))
        export_audio_only_action.triggered.connect(self.export_mixdown_dialog)
        export_video_audio_action.triggered.connect(lambda: self.export_video_dialog(include_audio=True))
        self.btn_export.setMenu(export_menu)
        self.btn_export_video = self.btn_export  # compatibility alias
        self.btn_clear_memory = QPushButton("🧹 CLEAR MEMORY")
        self.btn_clear_memory.setFixedSize(160, 32)
        self.btn_clear_memory.setToolTip("Clear user data and reset the user-edit tracker.")
        self.btn_clear_memory.clicked.connect(self.clear_user_memory)
        utility_bar=QHBoxLayout(); utility_bar.addStretch(1);
        master_container.insertLayout(0, utility_bar)
        self.scope_status_label = QLabel("📊 2.5D Video Synth + Oscilloscope  |  Status: Idle")
        self.scope_status_label.setStyleSheet("color: #00ffff; font-weight: bold;")
        scope_bar.addWidget(self.scope_status_label, stretch=1)
        self.lbl_boot_mode = QLabel("Boot: —")
        self.lbl_boot_mode.setStyleSheet(
            "color:#f5d97d; font-weight:bold; padding:2px 8px; "
            "background:#1a1810; border:1px solid #5a4a20; border-radius:4px;"
        )
        self.lbl_boot_mode.setToolTip(
            "Case A empty boot rolls 25% each: BOTH / SEED only / SEQUENCES only / NEITHER."
        )
        scope_bar.addWidget(self.lbl_boot_mode)
        # Two independent bars: play/DSP can run while export runs (and vice versa).
        self.play_progress_bar = QProgressBar()
        self.play_progress_bar.setObjectName("playProgressBar")
        self.play_progress_bar.setRange(0, 100)
        self.play_progress_bar.setValue(0)
        self.play_progress_bar.setFormat("Play %p%")
        self.play_progress_bar.setFixedWidth(140)
        self.play_progress_bar.setTextVisible(True)
        self.play_progress_bar.setVisible(False)
        self.lbl_play_progress = QLabel("Play")
        self.lbl_play_progress.setVisible(False)
        scope_bar.addWidget(self.lbl_play_progress)
        scope_bar.addWidget(self.play_progress_bar)
        self.render_progress_bar = self.play_progress_bar
        scope_bar.addStretch(1)
        self.export_progress_bar = None
        self.lbl_export_progress = None

        # POWER_V3_VISUAL_LAYOUT: master volume lives above Visualizer settings.

        master_container.addLayout(scope_bar)
        visual_pair = QHBoxLayout()
        visual_pair.setSpacing(8)
        visual_left = QVBoxLayout()
        visual_left.addWidget(self.btn_clear_memory)
        visual_left.addWidget(QLabel("LIVE AUDIO VISUALIZER"))
        self.visual_oscilloscope.setMinimumSize(260, 180)
        self.visual_oscilloscope.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        visual_left.addWidget(self.visual_oscilloscope, stretch=1)
        visual_right = QVBoxLayout()
        export_row = QHBoxLayout()
        export_row.addWidget(self.btn_export)
        self.lbl_export_progress = QLabel("Export")
        self.lbl_export_progress.setVisible(False)
        self.export_progress_bar = QProgressBar()
        self.export_progress_bar.setObjectName("exportProgressBar")
        self.export_progress_bar.setRange(0, 100)
        self.export_progress_bar.setValue(0)
        self.export_progress_bar.setFormat("Export %p%")
        self.export_progress_bar.setFixedWidth(160)
        self.export_progress_bar.setTextVisible(True)
        self.export_progress_bar.setVisible(False)
        export_row.addWidget(self.lbl_export_progress)
        export_row.addWidget(self.export_progress_bar)
        export_row.addStretch(1)
        visual_right.addLayout(export_row)
        visual_right.addWidget(QLabel("2.5D VIDEO GEOMETRY"))
        self.video_synth_viewer.setMinimumSize(320, 320)
        self.video_synth_viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        visual_right.addWidget(self.video_synth_viewer, stretch=1)
        visual_pair.addLayout(visual_left, stretch=1)
        visual_pair.addLayout(visual_right, stretch=1)
        visual_container = QWidget()
        visual_container.setLayout(visual_pair)
        visual_container.setMinimumHeight(330)
        master_container.addWidget(visual_container, stretch=1)
        QTimer.singleShot(0, lambda: self._on_viz_mode_changed(int(self.viz_mode_combo.currentIndex()) if hasattr(self, "viz_mode_combo") else 0))

        # Realtime audio engine state (sounddevice stream)
        self.is_playing = False
        self.is_paused = False
        self.play_buffer = None
        self.play_sample_rate = 44100
        self.play_cursor = 0
        self.play_lock = threading.Lock()
        self.audio_stream = None
        self.master_volume = 0.80
        self._scope_update_timer = QTimer(self)
        self._scope_update_timer.setInterval(33)
        self._scope_update_timer.timeout.connect(self._update_scope_from_playhead)
        self._last_scope_chunk = np.zeros(100, dtype=np.float32)

        # ASYNC_RENDER: never build the full DSP mixdown on the Qt GUI thread.
        # The worker only produces data; all Qt widgets/audio-stream operations
        # remain on the GUI thread via the polling timer below.
        self._mixdown_lock = threading.Lock()
        self._render_result_queue = queue.Queue()
        self._render_thread = None
        self._render_generation = 0
        self._render_poll_timer = QTimer(self)
        self._render_poll_timer.setInterval(40)
        self._render_poll_timer.timeout.connect(self._poll_async_render_result)
        self._render_progress = 0
        self._play_progress = 0
        self._export_progress = 0
        self._export_stage = "Idle"
        self._render_stage = "Idle"
        self._export_result_queue = queue.Queue()
        self._export_thread = None
        self._export_poll_timer = QTimer(self)
        self._export_poll_timer.setInterval(50)
        self._export_poll_timer.timeout.connect(self._poll_export_result)

        # ------------------------------------------------------------------
        # Re-attach full-window parametric background AFTER the central
        # layout was rebuilt (init_ui_components clears/recreates children).
        # Without this, the earlier __init__ attach is destroyed.
        # ------------------------------------------------------------------
        try:
            cw = self.centralWidget()
            if cw is not None:
                bg = getattr(self, "parametric_background", None)
                if bg is None or bg.parent() is not cw:
                    self.parametric_background = ParametricMathBackground(self, cw)
                    bg = self.parametric_background
                bg.setParent(cw)
                bg.setGeometry(cw.rect())
                bg.lower()
                bg.show()
                if hasattr(self, "instrument_selector_dropdown"):
                    try:
                        self.instrument_selector_dropdown.currentIndexChanged.connect(
                            lambda _i, b=bg: b._reseed()
                        )
                    except Exception:
                        pass
        except Exception as _bg_exc:
            print(f"[Background] post-init attach: {_bg_exc}")
        # Startup Case A/B/C/D roll so seed/sequences probability is real at boot.
        try:
            self.bootstrap_seed_and_program_parameters()
            if hasattr(self, "reload_active_instrument_sequencer_ui"):
                self.reload_active_instrument_sequencer_ui()
            # Persistent boot-mode readout so the 25% Case A roll is visible.
            mode = getattr(self, "_bootstrap_mode", "")
            if hasattr(self, "lbl_boot_mode"):
                labels = {
                    "CASE_A_BOTH": "Boot 25%: seed + sequences",
                    "CASE_A_SEED": "Boot 25%: seed only",
                    "CASE_A_SEQUENCES": "Boot 25%: sequences only",
                    "CASE_A_NEITHER": "Boot 25%: neither (empty)",
                    "CASE_B_FINGERPRINT": "Boot: program present → derived seed",
                    "CASE_C_SEED_PROGRAM": "Boot: seed present → sparse sequences",
                    "CASE_D_UNCHANGED": "Boot: seed + program kept",
                }
                self.lbl_boot_mode.setText(f"🎲 {labels.get(mode, mode or '—')}")
            elif hasattr(self, "scope_status_label") and mode:
                self.scope_status_label.setText(f"🎲 Boot: {mode}")
        except Exception as _boot_exc:
            print(f"[Bootstrap] startup: {_boot_exc}")



    def _sync_floating_windows_to_instrument(self, inst_name):
        """Open floating editors immediately reflect the selected instrument."""
        if not inst_name:
            return
        for attr, prefix in (
            ('synth_editor_window', 'Synth'),
            ('script_editor_window', 'Script'),
            ('patch_bay_dialog', 'Modular'),
        ):
            win = getattr(self, attr, None)
            if win is None:
                continue
            try:
                if not win.isVisible():
                    continue
            except Exception:
                continue
            try:
                win.setWindowTitle(f"{prefix} — {inst_name}")
            except Exception:
                pass
            try:
                for child in win.findChildren(QLabel):
                    txt = child.text() or ""
                    if any(k in txt for k in ("Instrument", "Operator", "Workspace", "Synth Settings")):
                        if "Workspace" in txt:
                            child.setText(f"Instrument Script Workspace: {inst_name}")
                        elif ":" in txt:
                            child.setText(txt.split(":")[0] + f": {inst_name}")
            except Exception:
                pass
            if attr == 'script_editor_window':
                try:
                    scripts = getattr(self, 'instrument_scripts', {})
                    for child in win.findChildren(QTextEdit):
                        child.setPlainText(scripts.get(inst_name, child.toPlainText()))
                        break
                except Exception:
                    pass

    def on_instrument_switched(self, idx):
        inst_name = self.instrument_names_48[idx] if 0 <= idx < len(self.instrument_names_48) else ""
        if hasattr(self, 'instrument_selector_dropdown') and self.instrument_selector_dropdown.currentIndex() != idx:
            self.instrument_selector_dropdown.blockSignals(True)
            self.instrument_selector_dropdown.setCurrentIndex(idx)
            self.instrument_selector_dropdown.blockSignals(False)
        self.reload_active_instrument_sequencer_ui()
        try:
            self._sync_floating_windows_to_instrument(inst_name)
        except Exception as exc:
            print(f"[Sync] {exc}")

    def reload_active_instrument_sequencer_ui(self):
        if getattr(self, '_composition_ui_batch', False):
            self._seq_ui_pending = True
            return
        if not hasattr(self, 'top_sequencer'):
            return
        # Debounce: live engines were rewriting styles every 2s → visible flicker
        now = time.monotonic()
        if getattr(self, '_seq_ui_guard', False):
            return
        if now - float(getattr(self, '_seq_ui_last', 0.0)) < 0.12:
            self._seq_ui_pending = True
            return
        self._seq_ui_last = now
        self._seq_ui_pending = False
        curr_inst = self.instrument_selector_dropdown.currentText()
        mem = self.instrument_sequencer_memory.get(curr_inst)
        if not mem:
            return
        self._ensure_seq_mem_length(mem, len(self.seq_step_buttons) or 16)
        for s_idx, btn in enumerate(self.seq_step_buttons):
            if s_idx >= len(mem["steps"]):
                continue
            amp = float(mem["amplitudes"][s_idx]) if s_idx < len(mem.get("amplitudes", [])) else 1.0
            pitch = float(mem["pitches"][s_idx]) if s_idx < len(mem.get("pitches", [])) else 1.0
            is_on = bool(mem["steps"][s_idx])
            label = "□" if is_on else "■"
            selected = (self.selected_step_idx == s_idx)
            # Only touch Qt when something actually changed (stops flicker)
            prev = getattr(btn, '_seq_cache', None)
            cache = (label, is_on, selected)
            if prev == cache:
                continue
            btn._seq_cache = cache
            if btn.text() != label:
                btn.setText(label)
            self._style_pad_button(btn, s_idx, is_on, selected=selected)

    def _style_pad_button(self, btn, s_idx, is_active_step, selected=False):
        """Style a STEP: selected gold > programmed on (cyan) > off (dark). No stylesheet appends."""
        if selected:
            sheet = "background-color: #1a1810; color: #f5d97d; border: 3px solid #f5d97d; font-weight: bold; font-size: 20pt;"
        elif is_active_step:
            sheet = "background-color: #00ffff; color: #060606; border: 2px solid #ffffff; font-weight: bold; font-size: 20pt;"
        else:
            sheet = "background-color: #121212; color: #00ffff; border: 2px solid #444444; font-size: 20pt;"
        if getattr(btn, '_seq_sheet', None) != sheet:
            btn._seq_sheet = sheet
            btn.setStyleSheet(sheet)

    def _on_pkp_boost_amount_changed(self, val):
        self.pkp_boost_amount = float(val) / 100.0
        if hasattr(self, "lbl_pkp_boost"):
            self.lbl_pkp_boost.setText(f"{val}%")

    def _on_pkp_nullock_boost_clicked(self, checked=False):
        """Momentary PKP remix burst; never arm a persistent envelope."""
        self.pkp_pad_bank_active = False
        self._play_selected_instrument_pkp()
        if hasattr(self, "scope_status_label"):
            boost=int(getattr(self,"pkp_boost_amount",1.0)*100)
            self.scope_status_label.setText(f"⚡ PKP one-shot remix · {boost}%")

    def _play_selected_instrument_pkp(self):
        """One-shot audition of a modified PKP/Null-Lock instance of the selected instrument."""
        try:
            inst_name = self.instrument_selector_dropdown.currentText()
            mem = self.instrument_sequencer_memory.get(inst_name, {})
            steps = mem.get("steps", [])
            active = [i for i, on in enumerate(steps) if on]
            if not active:
                active = [self.selected_step_idx if self.selected_step_idx is not None else 0]
            step_idx = active[0] % max(1, int(self.spin_seq_length.value()))
            amp = 1.0
            if self.selected_step_idx is not None and self.selected_step_idx < len(mem.get("amplitudes", [])):
                amp = float(mem["amplitudes"][self.selected_step_idx])
            elif step_idx < len(mem.get("amplitudes", [])):
                amp = float(mem["amplitudes"][step_idx])
            self._pkp_fire_step_hit(inst_name, step_idx, amp=max(0.0, min(1.0, amp)))
            if hasattr(self, "scope_status_label"):
                self.scope_status_label.setText(f"▶ PKP audition · {inst_name[:24]} · step {step_idx + 1}")
        except Exception as e:
            print(f"[PKP] audition error: {e}")

    def toggle_pkp_pad_bank(self, checked):
        """Compatibility hook: PKP is global and never owns a timeline clock."""
        self.pkp_pad_bank_active = bool(checked)
        print(f"[PKP] {'ARMED' if checked else 'DISARMED'} — global note-triggered layer")

    def _pkp_step_tick(self):
        """Retained for compatibility; PKP is not a timeline event."""
        return

    def _estimate_other_47_rms(self, selected_step, step_duration, n_samples, sample_rate):
        """Estimate combined RMS power of all non-selected operators for one step."""
        selected=self.instrument_selector_dropdown.currentText()
        total=0.0
        t=np.linspace(0.0, step_duration, n_samples, endpoint=False)
        base=float(self.spin_base_frequency.value()) if hasattr(self,'spin_base_frequency') else 432.0
        for idx,name in enumerate(getattr(self,'instrument_names_48',[])):
            if name==selected: continue
            mem=self.instrument_sequencer_memory.get(name,{})
            steps=mem.get('steps',[])
            if not steps or not steps[int(selected_step)%len(steps)]: continue
            amps=mem.get('amplitudes',[]); probs=mem.get('probabilities',[])
            a=float(np.clip(amps[int(selected_step)%len(amps)],0,1)) if amps else 1.0
            pr=float(np.clip(probs[int(selected_step)%len(probs)]/100.0,0,1)) if probs else 1.0
            freq=base*MEUM_POWERS_36[idx%len(MEUM_POWERS_36)]
            v=np.sin(2*np.pi*freq*t)*a*pr
            total += float(np.mean(v*v))
        return float(np.sqrt(total))

    def _pkp_fire_step_hit(self, inst_name, step_idx, amp=1.0):
        """Generate a short percussive hit for the active pad and push it to scope (+ optional audio)."""
        try:
            sr = 44100
            # One-shot duration = one non-sustained note/step.
            bpm = self.spin_bpm.value() if hasattr(self, 'spin_bpm') else 120
            hit_dur = max(0.02, min(0.50, (60.0 / max(bpm, 1) / 4.0)))
            n = int(sr * hit_dur)
            t = np.linspace(0.0, hit_dur, n, endpoint=False)

            # Instrument-coloured frequency from index in the 48 list
            try:
                op_idx = self.instrument_names_48.index(inst_name)
            except ValueError:
                op_idx = step_idx
            base_freq = float(self.spin_base_frequency.value()) if hasattr(self, "spin_base_frequency") else 432.0
            base_freq *= MEUM_POWERS_36[op_idx % 36]
            # Slight pitch offset per step so the sequence is musical
            freq = base_freq * (1.0 + (step_idx % 12) * 0.03)

            # PKP manual trigger is a direct user event: no synthetic envelope,
            # click layer, or RMS matching. The actual pad amplitude is authoritative.
            hit = np.sin(2 * np.pi * freq * t) * float(amp)
            peak = float(np.max(np.abs(hit))) if hit.size else 0.0
            if peak > 0.98:
                hit *= 0.98 / peak
            hit *= float(getattr(self, 'master_volume', 1.0))

            # Scope preview
            if isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope):
                idx = np.linspace(0, len(hit) - 1, 100).astype(int)
                self.visual_oscilloscope.update_waveform(hit[idx])
                if hasattr(self, 'scope_status_label'):
                    self.scope_status_label.setText(
                        f"📊 PKP Hit  ·  {inst_name[:18]}  STEP {step_idx+1}  ·  {freq:.1f} Hz"
                    )

            # Non-blocking one-shot audio (does not interfere with main stream)
            if HAS_SOUNDDEVICE:
                try:
                    sd.play(hit.astype(np.float32), sr, blocking=False)
                except Exception:
                    pass
        except Exception as e:
            print(f"[PKP] step hit error: {e}")

    def _refresh_pad_playhead(self):
        """Re-style all pads so only the current playhead step is highlighted orange."""
        if not hasattr(self, 'seq_step_buttons') or not self.seq_step_buttons:
            return
        curr_inst = self.instrument_selector_dropdown.currentText() if hasattr(self, 'top_sequencer') else None
        mem = self.instrument_sequencer_memory.get(curr_inst, {"steps": []}) if curr_inst else {"steps": []}
        for s_idx, btn in enumerate(self.seq_step_buttons):
            is_on = mem["steps"][s_idx] if s_idx < len(mem.get("steps", [])) else False
            self._style_pad_button(btn, s_idx, is_on)

    def rebuild_sequencer_steps(self, count):
        while self.steps_inner_layout.count():
            item = self.steps_inner_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.seq_step_buttons.clear()
        self.selected_step_idx = None

        curr_inst = self.instrument_selector_dropdown.currentText() if hasattr(self, 'top_sequencer') else self.instrument_names_48[0]
        mem = self.instrument_sequencer_memory[curr_inst]
        self._ensure_seq_mem_length(mem, count)
        if "pitches" not in mem:
            mem["pitches"] = [1.0] * count
        elif len(mem["pitches"]) < count:
            mem["pitches"].extend([1.0] * (count - len(mem["pitches"])))

        for s in range(count):
            amp = mem["amplitudes"][s]
            pitch = mem["pitches"][s] if s < len(mem["pitches"]) else 1.0
            step_btn = QPushButton(f"{'□' if mem['steps'][s] else '■'}")
            step_btn.setCheckable(False)  # selection vs toggle handled in click
            step_btn.setMinimumSize(42, 52)
            step_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._style_pad_button(step_btn, s, mem["steps"][s])

            def make_handler(s_idx):
                def on_click():
                    self._on_step_pad_clicked(s_idx)
                return on_click

            step_btn.clicked.connect(make_handler(s))
            self.steps_inner_layout.addWidget(step_btn)
            self.seq_step_buttons.append(step_btn)

    def _seed_text(self):
        """Return the complete scrollable seed/script field as plain text."""
        if not hasattr(self, 'input_seed_val'):
            return "0.0"
        try:
            return self.input_seed_val.toPlainText().strip()
        except AttributeError:
            return self.input_seed_val.text().strip()

    def get_numeric_seed(self):
        """Stable integer seed — same text always → same song (incl. 1337, MEUM)."""
        seed_text = self._seed_text() if hasattr(self, 'input_seed_val') else "42"
        t = (seed_text or "").strip()
        if not t:
            return 0
        tl = t.lower().replace(" ", "")
        if tl in ("meum", "m"):
            return int(round(MEUM * 1_000_000_000_000_000)) % (2**31)
        try:
            val = float(t)
            if abs(val) == 0.0:
                return 0
            # Mix IEEE bits with magnitude so integer seeds (1337, 1024, …) are non-zero
            bits = struct.unpack(">Q", struct.pack(">d", float(val)))[0]
            mag = int(abs(val) * 1_000_000) & 0x7FFFFFFF
            mixed = (bits ^ (bits >> 33) ^ (mag * 2654435761)) & 0x7FFFFFFF
            return int(mixed) if mixed else (mag or 1)
        except ValueError:
            h = 2166136261
            for b in t.encode("utf-8", "replace"):
                h ^= b
                h = (h * 16777619) & 0xFFFFFFFF
            return int(h % (2**31)) or 1

    def open_domain_equation_editor(self):
        """Open the partitionable time/space domain equation editor dialog."""
        if not hasattr(self, 'domain_eq_engine') or self.domain_eq_engine is None:
            self.domain_eq_engine = DomainPartitionEquationEngine(seed=0.0)
        # Sync seed from UI into the engine (longitudinal weighting)
        try:
            seed_txt = self._seed_text() if hasattr(self, 'input_seed_val') else "0"
            self.domain_eq_engine.set_seed(float(seed_txt) if seed_txt not in ("",) else 0.0)
        except ValueError:
            self.domain_eq_engine.set_seed(self.get_numeric_seed() / 1e9)
        # Non-modal: Domain must never freeze the main panel (exec() blocked UI).
        if getattr(self, "domain_eq_dialog", None) is not None:
            try:
                if self.domain_eq_dialog.isVisible():
                    self.domain_eq_dialog.raise_()
                    self.domain_eq_dialog.activateWindow()
                    return
            except Exception:
                pass
        dlg = DomainEquationEditorDialog(self.domain_eq_engine, parent=self)
        dlg.setModal(False)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        try:
            attach_math_decor(dlg, app=self, light=True)
        except Exception:
            try:
                dlg.setStyleSheet(DAW_STYLE)
            except Exception:
                pass
        self.domain_eq_dialog = dlg
        dlg.show()
        dlg.raise_()

    def open_help_readme(self):
        """Open the full Help / Readme / scripting documentation dialog."""
        dlg = ReadmeGuideDialog(parent=self)
        dlg.setModal(False)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        try:
            attach_math_decor(dlg, app=self)
        except Exception:
            pass
        dlg.show()

    def apply_playlist_automation_to_ui(self):
        """
        Push playlist-painted automation onto live synth macros / patch gains.
        Coverage scales depth; direction vector sets sign. Updates UI knobs when present.
        """
        if not getattr(self, 'playlist_automation', None):
            return
        # Aggregate latest per-param influence
        accum = {}  # param -> weighted sum of signed amounts
        weights = {}
        for lane in self.playlist_automation:
            if not lane:
                continue
            param = lane.get("param", "eqr")
            amt = float(lane.get("amount", 0.0)) * float(lane.get("direction", 1.0))
            # Overlap reduces exclusive authority but still contributes
            ov = float(lane.get("overlap", 0.0))
            w = max(0.05, abs(amt) * (1.0 - 0.3 * ov))
            accum[param] = accum.get(param, 0.0) + amt * w
            weights[param] = weights.get(param, 0.0) + w

        def _norm(p, default=None):
            if weights.get(p, 0) <= 1e-9:
                if default is not None:
                    return float(default)
                current = {
                    "eqr": (self.slider_eqr.value() / 100.0) if hasattr(self, "slider_eqr") else 0.0,
                    "fractalizer": (self.slider_fractalizer.value() / 100.0) if hasattr(self, "slider_fractalizer") else 0.33,
                    "pkp_decay": (self.slider_pkp_decay.value() / 1000.0) if hasattr(self, "slider_pkp_decay") else 0.50,
                }
                return float(current.get(p, 0.0))
            return float(np.clip(0.5 + accum[p] / max(weights[p], 1e-9) * 0.5, 0.0, 1.0))

        # Map onto main macros with their actual slider scales.
        # Fractallizer is 0..100, not 0..1000.
        if hasattr(self, 'slider_eqr'):
            self.slider_eqr.blockSignals(True)
            self.slider_eqr.setValue(int(round(_norm("eqr") * 100)))
            self.slider_eqr.blockSignals(False)
        if hasattr(self, 'slider_fractalizer'):
            self.slider_fractalizer.blockSignals(True)
            self.slider_fractalizer.setValue(int(round(_norm("fractalizer") * 100)))
            self.slider_fractalizer.blockSignals(False)
        if hasattr(self, 'slider_pkp_decay'):
            self.slider_pkp_decay.blockSignals(True)
            self.slider_pkp_decay.setValue(int(round(_norm("pkp_decay") * 1000)))
            self.slider_pkp_decay.blockSignals(False)

        # Patch bay cable gains: scale by automation "drive" if any
        drive = _norm("drive", 0.2)
        try:
            for c in getattr(self, 'patch_connections', []) or []:
                if c.get("origin") == "additive_optimizer":
                    # Keep optimizer cables; nudge weight gently
                    c["weight"] = float(np.clip(c.get("weight", 0.5) * (0.85 + 0.3 * drive), 0.1, 1.0))
            for c in getattr(GLOBAL_BUS, 'global_cables', []) or []:
                if "gain" in c:
                    base = float(c.get("gain", 1.0))
                    c["gain"] = float(np.clip(base * (0.9 + 0.2 * drive), 0.1, 2.0))
            GLOBAL_BUS.broadcast_update()
        except Exception:
            pass

    def _ensure_seq_mem_length(self, mem, count):
        """Grow sequencer arrays to `count` without shrinking or wiping existing entries."""
        for key, default in (
            ("steps", False),
            ("amplitudes", 1.0),
            ("pitches", 1.0),
            ("gates", True),
            ("probabilities", 100),
        ):
            if key not in mem:
                mem[key] = [default] * count
            elif len(mem[key]) < count:
                mem[key].extend([default] * (count - len(mem[key])))

    # =====================================================================
    # STEP_ISOLATION_FIX
    # A click changes exactly one step. Selection and activation are no longer
    # a two-click state machine, which prevents a Step 3 click from visually
    # propagating activation across the sequence.
    # =====================================================================
    def _position_step_editor(self, s_idx):
        """Teleport the selected-step editor above/below the selected pad."""
        if not hasattr(self, 'step_editor_popup') or s_idx >= len(getattr(self, 'seq_step_buttons', [])):
            return
        btn = self.seq_step_buttons[s_idx]
        viewport = self.steps_scroll.viewport()
        self.steps_scroll.ensureWidgetVisible(btn, 24, 24)
        # Geometry is valid after the scroll adjustment; clamp popup into viewport.
        pos = btn.mapTo(viewport, btn.rect().topLeft())
        pw = self.step_editor_popup.width()
        ph = self.step_editor_popup.height()
        vw = viewport.width()
        vh = viewport.height()
        x = max(4, min(pos.x() + (btn.width() - pw) // 2, max(4, vw - pw - 4)))
        # Keep the inspector in the strip immediately below the step row and
        # immediately above the QScrollArea horizontal scrollbar. It no longer
        # teleports over the pads themselves.
        y = max(2, vh - ph - 2)
        self.step_editor_popup.move(x, y)
        self.step_editor_popup.raise_()
        self.step_editor_popup.show()

    def _on_step_pad_clicked(self, s_idx):
        curr_i = self.instrument_selector_dropdown.currentText()
        mem = self.instrument_sequencer_memory[curr_i]
        self._ensure_seq_mem_length(mem, max(s_idx + 1, len(mem.get("steps", []))))

        # Two-click state machine:
        #   1st click on a pad → select it (amp/pitch inspector)
        #   2nd click on the *already selected* pad → toggle active/inactive
        # Clicking a different pad only moves selection (does not toggle that pad).
        if self.selected_step_idx == s_idx:
            mem["steps"][s_idx] = not bool(mem["steps"][s_idx])
            self._mark_step_touched(mem, s_idx)
        else:
            self.selected_step_idx = s_idx

        if hasattr(self, 'lbl_selected_step'):
            self.lbl_selected_step.setText(f"Step: {s_idx + 1}")
        amp = float(mem["amplitudes"][s_idx]) if s_idx < len(mem.get("amplitudes", [])) else 1.0
        pitch = float(mem["pitches"][s_idx]) if s_idx < len(mem.get("pitches", [])) else 1.0
        if hasattr(self, 'slider_step_amp'):
            self.slider_step_amp.blockSignals(True)
            self.slider_step_amp.setValue(int(round(amp * 100)))
            self.slider_step_amp.blockSignals(False)
            self.lbl_step_amp.setText(f"{int(round(amp * 100))}%")
        if hasattr(self, 'slider_step_pitch'):
            self.slider_step_pitch.blockSignals(True)
            self.slider_step_pitch.setValue(int(round(pitch * 100)))
            self.slider_step_pitch.blockSignals(False)
            self.lbl_step_pitch.setText(f"{pitch:.2f}×")

        # A normal click never invokes Randomizer/Phase-Locker or changes other pads.
        self.reload_active_instrument_sequencer_ui()
        self._position_step_editor(s_idx)

    # =====================================================================
    # PLAYLIST_VELOCITY_PHASELOCK — playlist velocity participates in the same
    # seeded/random/phase-locked field as sequencer activity. User-edited rows
    # are preserved; only rows marked/recognized as available are fitted.
    # =====================================================================
    def _phase_lock_playlist_velocity(self, rng=None, strength=0.65, randomize=False):
        """Generate stable playlist velocity without recursively fading user rows.

        User/imported rows are authoritative.  Engine rows are recomputed from the
        seeded field instead of blending against their previous value, so repeated
        Randomizer + Phase-Lock passes cannot drift toward silence.
        """
        rows = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else len(getattr(self, 'master_playlist_data', []))
        if not getattr(self, 'master_playlist_data', None):
            return
        numeric_seed = self.get_numeric_seed()
        if rng is None:
            rng = np.random.default_rng(numeric_seed)

        for i, entry in enumerate(self.master_playlist_data[:rows]):
            if not isinstance(entry, dict):
                continue
            generated = bool(entry.get("generated_by_engine") or entry.get("generated_source"))
            user_locked = bool(entry.get("velocity_user_locked") or entry.get("user_defined"))
            # Never touch an explicitly user-owned/imported row.
            if user_locked and not generated:
                continue

            phase = (i / max(rows, 1)) * 2.0 * np.pi + (numeric_seed % 100000) * 0.000013
            field = 0.5 + 0.5 * np.sin(phase * MEUM_CONSTANT + numeric_seed * 0.0000017)
            if hasattr(self, "_contextual_numerology"):
                field = 0.5 * field + 0.5 * self._contextual_numerology(step=i, row=i)
            target = 0.25 + 0.75 * field
            if randomize:
                target = 0.75 * target + 0.25 * float(rng.uniform(0.25, 1.0))

            # Generated rows are absolute/stable for this seed/pass, not feedback.
            if generated:
                entry["velocity"] = float(np.clip(target, 0.05, 1.5))
                entry["velocity_user_locked"] = False
            else:
                entry["velocity"] = float(np.clip(target, 0.05, 1.5))
                entry["velocity_user_locked"] = False

        if hasattr(self, 'active_paint_table') and self.active_paint_table:
            table = self.active_paint_table
            for r, entry in enumerate(self.master_playlist_data[:min(rows, table.rowCount())]):
                item = QTableWidgetItem(f"{float(entry.get('velocity', 1.0))*100:.1f}%")
                table.set_cell_item(r, 3, item)

    def randomize_playlist_velocity(self):
        self._phase_lock_playlist_velocity(np.random.default_rng(self.get_numeric_seed()), strength=1.0, randomize=True)
        self._live_engine_signatures.pop("playlist", None)

    def _on_step_amp_slider(self, val):
        if hasattr(self, 'lbl_step_amp'):
            self.lbl_step_amp.setText(f"{val}%")
        if self.selected_step_idx is None:
            return
        curr_i = self.instrument_selector_dropdown.currentText()
        mem = self.instrument_sequencer_memory[curr_i]
        s = self.selected_step_idx
        self._ensure_seq_mem_length(mem, s + 1)
        mem["amplitudes"][s] = val / 100.0
        self._mark_step_touched(mem, s)  # USER_TOUCHED_TRACKING: manual slider edit
        # Amp is velocity / step-trigger blend amount into painted together steps
        if mem["steps"][s] and s < len(self.seq_step_buttons):
            pitch = mem["pitches"][s] if s < len(mem.get("pitches", [])) else 1.0
            self.seq_step_buttons[s].setText("□" if mem["steps"][s] else "■")

    def _on_step_pitch_slider(self, val):
        ratio = val / 100.0
        if hasattr(self, 'lbl_step_pitch'):
            self.lbl_step_pitch.setText(f"{ratio:.2f}×")
        if self.selected_step_idx is None:
            return
        curr_i = self.instrument_selector_dropdown.currentText()
        mem = self.instrument_sequencer_memory[curr_i]
        s = self.selected_step_idx
        self._ensure_seq_mem_length(mem, s + 1)
        mem["pitches"][s] = ratio
        if s < len(self.seq_step_buttons):
            amp = mem["amplitudes"][s] if s < len(mem["amplitudes"]) else 1.0
            self.seq_step_buttons[s].setText("□" if mem["steps"][s] else "■")

    def _on_euclidean_live_toggled(self, checked):
        # Keep persistent :checked stylesheet — never clear to "" (would lose OFF look).
        if hasattr(self, "_style_toggle_euclidean"):
            self.btn_idealize_rhythm.setStyleSheet(self._style_toggle_euclidean)
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            self.btn_idealize_rhythm.blockSignals(True)
            self.btn_idealize_rhythm.setChecked(False)
            self.btn_idealize_rhythm.blockSignals(False)
            return
        if checked:
            try:
                self._apply_live_engine_once("euclidean")
            except Exception as exc:
                print(f"[euclidean-toggle] {exc}")
            self.btn_idealize_rhythm.setText("✨ Euclidean Live Lock · ON")
        else:
            self._live_euclid_timer.stop()
            self.btn_idealize_rhythm.setText("✨ Euclidean Live Lock")


    def _composition_snapshot(self):
        """Deep snapshot of generated composition state for finite live-mode states."""
        snap = {}
        for key in (
            "instrument_sequencer_memory", "master_playlist_data", "playlist_automation",
            "instrument_scripts", "instrument_param_state", "instrument_param_generated",
            "patch_connections", "generated_domains", "playlist_generated_overlay",
        ):
            if hasattr(self, key):
                snap[key] = copy.deepcopy(getattr(self, key))
        try:
            if hasattr(self, "domain_eq_engine") and self.domain_eq_engine:
                snap["domain_eq"] = copy.deepcopy(self.domain_eq_engine.to_json())
        except Exception:
            pass
        return snap

    def _restore_composition_snapshot(self, snap):
        """Restore a previously generated composition without invoking any engine."""
        if not snap:
            return False
        for key, value in snap.items():
            if key == "domain_eq":
                try:
                    if hasattr(self, "domain_eq_engine") and self.domain_eq_engine:
                        self.domain_eq_engine.from_json(copy.deepcopy(value))
                except Exception:
                    pass
                continue
            setattr(self, key, copy.deepcopy(value))
        try:
            self.reload_active_instrument_sequencer_ui()
        except Exception:
            pass
        return True

    def _invalidate_live_composition_cache(self, *keys):
        cache = getattr(self, "_live_composition_cache", None)
        if cache is None:
            cache = self._live_composition_cache = {}
        if keys:
            for key in keys:
                cache.pop(key, None)
        else:
            cache.clear()

    def _cache_live_composition(self, key):
        if not hasattr(self, "_live_composition_cache") or self._live_composition_cache is None:
            self._live_composition_cache = {}
        self._live_composition_cache[key] = self._composition_snapshot()

    def _on_unified_randomizer_toggled(self, checked):
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            for b in (getattr(self, 'btn_local_randomize', None), getattr(self, 'btn_seeded_randomize', None)):
                if b is not None:
                    b.blockSignals(True); b.setChecked(False); b.blockSignals(False)
            return
        for b in (getattr(self, 'btn_local_randomize', None), getattr(self, 'btn_seeded_randomize', None)):
            if b is not None and b.isChecked() != checked:
                b.blockSignals(True); b.setChecked(checked); b.blockSignals(False)

        if checked:
            # A Randomizer ON edge is the ONLY thing allowed to create a fresh
            # random composition. It creates once, then remains stable.
            self._invalidate_live_composition_cache("both")
            try:
                self._apply_live_engine_once("seeded", force=True)
                self._cache_live_composition("randomizer")
                self._invalidate_live_composition_cache("phase_base", "phase_locked")
                if self._engines_both_live()[1]:
                    self._apply_live_midpoint_once(force=True)
                    self._cache_live_composition("both")
            except Exception as exc:
                print(f"[Randomizer toggle] {exc}")
            if hasattr(self, '_live_seeded_timer'):
                self._live_seeded_timer.stop()
            if hasattr(self, '_live_euclid_timer') and self._engines_both_live()[1]:
                self._live_euclid_timer.stop()
        else:
            if hasattr(self, '_live_seeded_timer'):
                self._live_seeded_timer.stop()
            # Removing Randomizer does not create another random composition.
            # If Phase-Lock is still ON, make/restore its one stable state.
            self._invalidate_live_composition_cache("both")
            if self._engines_both_live()[1]:
                try:
                    self._apply_live_engine_once("euclidean", force=True)
                    self._cache_live_composition("phase")
                except Exception as exc:
                    print(f"[Randomizer off] {exc}")
                if hasattr(self, '_live_euclid_timer'):
                    self._live_euclid_timer.start(2000)

    def _on_unified_phase_lock_toggled(self, checked):
        """Phase-Lock is a strict two-state toggle over the current base pattern.

        Base can be any of:
          • raw user data
          • randomizer output (with or without user data underneath)
          • free user data without randomizer

        ON  → snapshot base as ``phase_base``, build phase-locked variant, show it
        OFF → restore ``phase_base`` exactly (no re-roll)

        Re-arming ON after the base changed (e.g. new randomizer pass) resnapshots
        and builds a fresh locked variant of that new base.
        """
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            for b in (getattr(self, 'btn_local_phase_lock', None), getattr(self, 'btn_idealize_rhythm', None)):
                if b is not None:
                    b.blockSignals(True); b.setChecked(False); b.blockSignals(False)
            return
        for b in (getattr(self, 'btn_local_phase_lock', None), getattr(self, 'btn_idealize_rhythm', None)):
            if b is not None and b.isChecked() != checked:
                b.blockSignals(True); b.setChecked(checked); b.blockSignals(False)

        # stop autonomous live timers — phase-lock is finite two-state, not evolving
        if hasattr(self, '_live_euclid_timer'):
            self._live_euclid_timer.stop()
        if hasattr(self, '_live_seeded_timer'):
            self._live_seeded_timer.stop()

        if not hasattr(self, '_live_composition_cache') or self._live_composition_cache is None:
            self._live_composition_cache = {}

        if checked:
            try:
                # 1) Snapshot the CURRENT composition as the unlocked base
                #    (user data / raw random / random+user — whatever is showing)
                self._cache_live_composition("phase_base")
                r_on, _ = self._engines_both_live()
                # 2) Build the phase-locked variant of that base
                if r_on:
                    # randomizer still armed → midpoint-locked variant of random+user base
                    self.apply_composition_midpoint(live=True)
                else:
                    # phase-lock alone over user data or prior random residue
                    self.apply_unified_phase_lock(live=True)
                # 3) Cache locked variant so re-toggling ON without base change restores it
                self._cache_live_composition("phase_locked")
                print("[Phase-Lock] ON — showing phase-locked variant of current base")
            except Exception as exc:
                print(f"[Phase-Lock toggle ON] {exc}")
        else:
            try:
                base = self._live_composition_cache.get("phase_base")
                if base:
                    self._restore_composition_snapshot(base)
                    print("[Phase-Lock] OFF — restored pre-lock base pattern")
                else:
                    # No base cached (first-run edge): leave current state as-is
                    print("[Phase-Lock] OFF — no base snapshot; leaving current pattern")
                # Drop locked cache so next ON rebuilds from whatever base exists then
                self._live_composition_cache.pop("phase_locked", None)
            except Exception as exc:
                print(f"[Phase-Lock toggle OFF] {exc}")


    def _on_seeded_live_toggled(self, checked):
        if hasattr(self, "_style_toggle_randomizer"):
            self.btn_seeded_randomize.setStyleSheet(self._style_toggle_randomizer)
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            self.btn_seeded_randomize.blockSignals(True)
            self.btn_seeded_randomize.setChecked(False)
            self.btn_seeded_randomize.blockSignals(False)
            return
        if checked:
            try:
                self._apply_live_engine_once("seeded")
            except Exception as exc:
                print(f"[seeded-toggle] {exc}")
            self.btn_seeded_randomize.setText("🎲 Seeded Live Randomizer · ON")
        else:
            self._live_seeded_timer.stop()
            self.btn_seeded_randomize.setText("🎲 Seeded Live Randomizer")

    def _on_user_program_only_toggled(self, checked):
        if checked:
            # Suspend live engines — user carrier only; restore OFF styles via :checked
            for btn, timer, style_attr, off_label in (
                (self.btn_idealize_rhythm, self._live_euclid_timer, "_style_toggle_euclidean", "✨ Euclidean Live Lock"),
                (self.btn_seeded_randomize, self._live_seeded_timer, "_style_toggle_randomizer", "🎲 Seeded Live Randomizer"),
            ):
                timer.stop()
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                if hasattr(self, style_attr):
                    btn.setStyleSheet(getattr(self, style_attr))
                btn.setText(off_label)
            print("[User program only] Live engines suspended — carrier only")
        else:
            print("[User program only] OFF — live engines may be re-armed")

    def _live_engine_signature(self, which):
        """Snapshot only *sources* owned by the user. Generated engine output is excluded.

        The previous implementation included the entire sequencer memory and playlist in
        the signature. Every live pass changes those structures, so the next timer tick
        necessarily looked like a new user input and recomposed again. That feedback loop
        was the direct cause of the Phase-Lock flicker/recomposition.
        """
        seed = self._seed_text() if hasattr(self, 'input_seed_val') else "0.0"
        inst = self.instrument_selector_dropdown.currentText() if hasattr(self, 'instrument_selector_dropdown') else ""
        seq_len = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        rows = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 32
        bpm = float(self.spin_bpm.value()) if hasattr(self, 'spin_bpm') else 120.0
        base_freq = float(self.spin_base_frequency.value()) if hasattr(self, 'spin_base_frequency') else 432.0
        convolve = float(self.slider_global_convolve.value()) if hasattr(self, 'slider_global_convolve') else 0.0

        # Only manually-touched step data belongs in the live source signature.
        # Generated pads, generated playlist rows, generated scripts, etc. are deliberately
        # ignored because they are outputs of the engine rather than new instructions.
        touched = []
        memories = getattr(self, 'instrument_sequencer_memory', {}) or {}
        for name in sorted(memories):
            mem = memories.get(name) or {}
            indices = sorted(int(i) for i in (mem.get('touched', set()) or set()))
            for i in indices:
                if i >= seq_len:
                    continue
                steps = mem.get('steps', [])
                amps = mem.get('amplitudes', [])
                pitches = mem.get('pitches', [])
                probs = mem.get('probabilities', [])
                touched.append((
                    name, i,
                    bool(steps[i]) if i < len(steps) else False,
                    round(float(amps[i]), 6) if i < len(amps) else 1.0,
                    round(float(pitches[i]), 6) if i < len(pitches) else 1.0,
                    int(probs[i]) if i < len(probs) else 100,
                ))

        return (which, seed, inst, seq_len, rows, bpm, base_freq, convolve, tuple(touched))

    def _store_live_engine_signature(self, which):
        if not hasattr(self, '_live_engine_signatures') or self._live_engine_signatures is None:
            self._live_engine_signatures = {}
        self._live_engine_signatures[which] = self._live_engine_signature(which)

    def _apply_live_engine_once(self, which, force=False):
        if getattr(self, '_live_engine_update_guard', False):
            return False
        sig = self._live_engine_signature(which)
        if not force and getattr(self, '_live_engine_signatures', {}).get(which) == sig:
            return False
        self._live_engine_update_guard = True
        try:
            self._composition_generation_counter = getattr(self, "_composition_generation_counter", 0) + 1
            if which == "euclidean":
                self.apply_unified_phase_lock(live=True)
            else:
                self.apply_unified_randomizer(live=True)
            # Store the source signature, not a signature of the newly generated output.
            self._store_live_engine_signature(which)
            return True
        except Exception as exc:
            print(f"[live-engine] {which} skipped: {exc}")
            return False
        finally:
            self._live_engine_update_guard = False

    def _apply_live_midpoint_once(self, force=False):
        """Run the combined Randomizer+Phase-Lock composition at most once per source state."""
        if getattr(self, '_live_engine_update_guard', False):
            return False
        sig = self._live_engine_signature("midpoint")
        if not force and getattr(self, '_live_engine_signatures', {}).get("midpoint") == sig:
            return False
        self._live_engine_update_guard = True
        try:
            self._composition_generation_counter = getattr(self, "_composition_generation_counter", 0) + 1
            self.apply_composition_midpoint(live=True)
            self._store_live_engine_signature("midpoint")
            return True
        except Exception as exc:
            print(f"[live-engine] midpoint skipped: {exc}")
            return False
        finally:
            self._live_engine_update_guard = False

    def _on_live_source_changed(self, *args):
        """One recomposition per genuine user source change; no autonomous evolution."""
        if getattr(self, '_live_engine_update_guard', False):
            return
        r_on, p_on = self._engines_both_live()
        self._invalidate_live_composition_cache()
        try:
            if r_on and p_on:
                # Build the Randomizer-only base once, then the combined state once.
                self._apply_live_engine_once("seeded", force=True)
                self._cache_live_composition("randomizer")
                self._apply_live_midpoint_once(force=True)
                self._cache_live_composition("both")
            elif r_on:
                self._apply_live_engine_once("seeded", force=True)
                self._cache_live_composition("randomizer")
            elif p_on:
                self._apply_live_engine_once("euclidean", force=True)
                self._cache_live_composition("phase")
        except Exception as exc:
            print(f"[live-source] {exc}")

    def _live_engine_tick(self, which):
        """Compatibility heartbeat: deliberately does not mutate composition."""
        return

    def _remove_engine_generated_playlist_writes(self):
        """Remove only Randomizer/Phase-Lock-owned playlist state.

        User-painted/imported rows, automation lanes, and @u: tokens survive.
        This is intentionally idempotent so either engine can be switched off in
        any order, including the combined Randomizer+Phase-Lock state.
        """
        rows = len(getattr(self, "master_playlist_data", []) or [])
        generated_rows = set(getattr(self, "_engine_generated_playlist_rows", set()) or set())

        def keep_user_tokens(value):
            if not isinstance(value, str):
                return value
            return ", ".join(
                tok.strip() for tok in value.split(",")
                if tok.strip() and "@u:" in tok
            )

        for r in range(rows):
            entry = self.master_playlist_data[r]
            if not isinstance(entry, dict):
                continue
            if r in generated_rows or entry.get("generated_by_engine") or entry.get("generated_source"):
                user_inst = list(entry.get("user_instances") or [])
                if user_inst:
                    entry.clear()
                    entry.update({
                        "user_instances": user_inst,
                        "operators": list(user_inst),
                        "operator": user_inst[0],
                        "user_defined": True,
                    })
                else:
                    self.master_playlist_data[r] = {}
            else:
                # Strip engine-only CSV residue while preserving explicit @u: data.
                for key in ("operator", "operators_csv", "coverage", "blend_partner"):
                    if key in entry and isinstance(entry[key], str) and "@e:" in entry[key]:
                        entry[key] = keep_user_tokens(entry[key])

            if r < len(getattr(self, "playlist_automation", []) or []):
                lane = self.playlist_automation[r]
                if isinstance(lane, dict) and (
                    r in getattr(self, "_engine_generated_automation_rows", set())
                    or lane.get("generated_by_engine")
                    or str(lane.get("mode", "")).startswith("engine:")
                ):
                    self.playlist_automation[r] = {}

        self._engine_generated_playlist_rows.clear()
        self._engine_generated_automation_rows.clear()

        table = getattr(self, "active_paint_table", None)
        if table is not None:
            try:
                tw = getattr(table, "table_widget", table)
                for r in range(tw.rowCount()):
                    for c in (1, 3, 4, 5, 8, 9):
                        item = tw.item(r, c)
                        if item is not None and "@e:" in (item.text() or ""):
                            kept = keep_user_tokens(item.text())
                            if hasattr(table, "set_cell_item"):
                                table.set_cell_item(r, c, kept)
                            else:
                                item.setText(kept)
                tw.viewport().update()
            except Exception as exc:
                print(f"[Playlist cleanup] UI refresh skipped: {exc}")

    def clear_user_memory(self):
        self._remove_engine_generated_playlist_writes()
        self._project_imported_user_state = False
        self._project_audio_data_loaded = False
        rows=int(self.spin_playlist_length.value()) if hasattr(self,"spin_playlist_length") else 96
        self.master_playlist_data=[{} for _ in range(rows)]; self.playlist_automation=[{} for _ in range(rows)]; self.playlist_user_touched=set()
        for mem in getattr(self,"instrument_sequencer_memory",{}).values():
            n=int(self.spin_seq_length.value()) if hasattr(self,"spin_seq_length") else len(mem.get("steps",[]))
            mem["steps"]=[False]*n; mem["amplitudes"]=[1.0]*n; mem["pitches"]=[1.0]*n; mem["probabilities"]=[100]*n; mem["touched"]=set()
        self.instrument_scripts={name:"" for name in getattr(self,"instrument_names_48",[])}
        self.instrument_param_state={}; self.instrument_param_generated={}; self.patch_connections=[]
        try:
            if hasattr(GLOBAL_BUS,"global_cables"): GLOBAL_BUS.global_cables=[]
        except Exception: pass
        if getattr(self,"domain_eq_engine",None): self.domain_eq_engine._load_defaults()
        self.generated_domains=[]; self.playlist_generated_overlay={}; self._composition_generation_counter=0
        self.reload_active_instrument_sequencer_ui()
        if getattr(self,"active_paint_table",None): self.active_paint_table.clearContents(); self.active_paint_table.viewport().update()

    def save_project_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save EQR Project", "", "EQR Project (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        # Snapshot full playback state so Load → Play reproduces the same track
        def _ser_mem(m):
            out = {
                "steps": [bool(x) for x in (m.get("steps") or [])],
                "amplitudes": [float(x) for x in (m.get("amplitudes") or [])],
                "pitches": [float(x) for x in (m.get("pitches") or [])],
                "probabilities": [int(x) for x in (m.get("probabilities") or [])],
                "touched": sorted(int(i) for i in (m.get("touched") or set())),
            }
            if "gates" in m:
                out["gates"] = [bool(x) for x in (m.get("gates") or [])]
            return out
        data = {
            "version": "3.6.8+",
            "seed": self._seed_text() if hasattr(self, 'input_seed_val') else "",
            "bpm": float(self.spin_bpm.value()) if hasattr(self, 'spin_bpm') else 120.0,
            "seq_length": int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16,
            "playlist_rows": int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 32,
            "base_frequency": float(self.spin_base_frequency.value()) if hasattr(self, 'spin_base_frequency') else 432.0,
            "eqr": float(self.slider_eqr.value()) if hasattr(self, 'slider_eqr') else 0.0,
            "fractalizer": float(self.slider_fractalizer.value()) if hasattr(self, 'slider_fractalizer') else 33.0,
            "pkp_decay": float(self.slider_pkp_decay.value()) if hasattr(self, 'slider_pkp_decay') else 500.0,
            "global_convolve": float(self.spin_global_convolve.value()) if hasattr(self, 'spin_global_convolve') else (
                float(self.slider_global_convolve.value()) if hasattr(self, 'slider_global_convolve') else 0.0
            ),
            "global_playlist": bool(self.chk_global_playlist.isChecked()) if hasattr(self, 'chk_global_playlist') else True,
            "mode_index": int(self.mode_combo.currentIndex()) if hasattr(self, 'mode_combo') else 0,
            "active_instrument": self.instrument_selector_dropdown.currentText() if hasattr(self, 'instrument_selector_dropdown') else "",
            "instrument_sequencer_memory": {
                name: _ser_mem(m) for name, m in (self.instrument_sequencer_memory or {}).items()
            },
            "master_playlist_data": copy.deepcopy(getattr(self, 'master_playlist_data', []) or []),
            "playlist_automation": copy.deepcopy(getattr(self, 'playlist_automation', []) or []),
            "instrument_scripts": dict(getattr(self, 'instrument_scripts', {}) or {}),
            "instrument_param_state": copy.deepcopy(getattr(self, 'instrument_param_state', {}) or {}),
            "patch_connections": copy.deepcopy(getattr(self, 'patch_connections', []) or []),
            "domain_eq": self.domain_eq_engine.to_json() if hasattr(self, 'domain_eq_engine') and self.domain_eq_engine else {},
            "instrument_param_generated": copy.deepcopy(getattr(self, 'instrument_param_generated', {}) or {}),
            "generation_counter": int(getattr(self, '_composition_generation_counter', 0)),
            "project_user_authoritative": True,
            "imported_wav_path": str(getattr(self, "imported_wav_path", "") or ""),
            "imported_sample_rate": int(getattr(self, "imported_sample_rate", 44100)),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Saved", f"Project saved:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Save failed", str(e))

    def load_project_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load EQR Project", "", "EQR Project (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Imported project files are user-authored source material.  Do not let
            # live/seed engines reinterpret them during or immediately after load.
            self._project_imported_user_state = True
            self._project_audio_data_loaded = False
            self._engine_generated_playlist_rows.clear()
            self._engine_generated_automation_rows.clear()

            # Restore an optional WAV carrier referenced by the project.
            imported_wav = str(data.get("imported_wav_path", "") or "")
            if imported_wav and os.path.isfile(imported_wav):
                try:
                    self._load_wav_path(imported_wav)
                    self._project_audio_data_loaded = True
                except Exception as _iw:
                    print(f"[Project] imported WAV restore skipped: {_iw}")

            # Guard live engines from reacting mid-load
            self._live_engine_update_guard = True
            self._step_ui_guard = True
            try:
                if hasattr(self, 'input_seed_val'):
                    try:
                        self.input_seed_val.blockSignals(True)
                        self.input_seed_val.setPlainText(str(data.get("seed", "")))
                    finally:
                        self.input_seed_val.blockSignals(False)
                if hasattr(self, 'spin_bpm'):
                    self.spin_bpm.blockSignals(True)
                    self.spin_bpm.setValue(float(data.get("bpm", 120.0)))
                    self.spin_bpm.blockSignals(False)
                seq_len = int(data.get("seq_length", 16))
                if hasattr(self, 'spin_seq_length'):
                    self.spin_seq_length.blockSignals(True)
                    self.spin_seq_length.setValue(seq_len)
                    self.spin_seq_length.blockSignals(False)
                rows = int(data.get("playlist_rows", 32))
                if hasattr(self, 'spin_playlist_length'):
                    self.spin_playlist_length.blockSignals(True)
                    self.spin_playlist_length.setValue(rows)
                    self.spin_playlist_length.blockSignals(False)
                if hasattr(self, 'spin_base_frequency'):
                    self.spin_base_frequency.setValue(float(data.get("base_frequency", 432.0)))
                if hasattr(self, 'slider_eqr') and "eqr" in data:
                    self.slider_eqr.setValue(int(round(float(data["eqr"]))))
                if hasattr(self, 'slider_fractalizer') and "fractalizer" in data:
                    self.slider_fractalizer.setValue(int(round(float(data["fractalizer"]))))
                if hasattr(self, 'slider_pkp_decay') and "pkp_decay" in data:
                    self.slider_pkp_decay.setValue(int(round(float(data["pkp_decay"]))))
                gc = float(data.get("global_convolve", 0.0))
                if hasattr(self, 'spin_global_convolve'):
                    # spin may be 0–100 or 0–1 depending on build — clamp sensibly
                    self.spin_global_convolve.setValue(gc if gc <= 100 else gc)
                if hasattr(self, 'slider_global_convolve'):
                    self.slider_global_convolve.setValue(int(round(gc if gc <= 100 else gc * 100)))
                if hasattr(self, 'chk_global_playlist'):
                    self.chk_global_playlist.setChecked(bool(data.get("global_playlist", True)))
                if hasattr(self, 'mode_combo'):
                    self.mode_combo.setCurrentIndex(int(data.get("mode_index", 0)))

                # Full replace sequencer memory (not update) so empty instruments stay empty
                raw_mem = data.get("instrument_sequencer_memory", {}) or {}
                new_mem = {}
                for name, m in raw_mem.items():
                    if not isinstance(m, dict):
                        continue
                    steps = [bool(x) for x in (m.get("steps") or [])]
                    # pad / trim to seq_len
                    if len(steps) < seq_len:
                        steps.extend([False] * (seq_len - len(steps)))
                    else:
                        steps = steps[:seq_len]
                    amps = [float(x) for x in (m.get("amplitudes") or [])]
                    pitches = [float(x) for x in (m.get("pitches") or [])]
                    probs = [int(x) for x in (m.get("probabilities") or [])]
                    while len(amps) < seq_len:
                        amps.append(1.0)
                    while len(pitches) < seq_len:
                        pitches.append(1.0)
                    while len(probs) < seq_len:
                        probs.append(100)
                    touched = m.get("touched", [])
                    if isinstance(touched, list):
                        touched = set(int(i) for i in touched)
                    elif not isinstance(touched, set):
                        touched = set()
                    entry = {
                        "steps": steps,
                        "amplitudes": amps[:seq_len],
                        "pitches": pitches[:seq_len],
                        "probabilities": probs[:seq_len],
                        "touched": touched,
                    }
                    if "gates" in m:
                        entry["gates"] = [bool(x) for x in m["gates"]]
                    new_mem[name] = entry
                # Ensure every known instrument exists
                for name in getattr(self, 'instrument_names_48', []):
                    if name not in new_mem:
                        new_mem[name] = {
                            "steps": [False] * seq_len,
                            "amplitudes": [1.0] * seq_len,
                            "pitches": [1.0] * seq_len,
                            "probabilities": [100] * seq_len,
                            "touched": set(),
                        }
                self.instrument_sequencer_memory = new_mem

                # Every active module in an imported project is user-owned unless
                # explicitly absent.  This makes old projects behave like hand-built
                # programs even if their older file format lacked touched/lock flags.
                for _name, _mem in self.instrument_sequencer_memory.items():
                    _steps = _mem.get("steps", [])
                    _mem["touched"] = set(range(min(seq_len, len(_steps)))) if any(_steps) else set()
                    _mem["user_defined"] = bool(any(_steps))

                self.master_playlist_data = list(data.get("master_playlist_data", []) or [])
                while len(self.master_playlist_data) < rows:
                    self.master_playlist_data.append({})
                self.playlist_automation = list(data.get("playlist_automation", []) or [])
                while len(self.playlist_automation) < rows:
                    self.playlist_automation.append({})
                for _r, _entry in enumerate(self.master_playlist_data):
                    if isinstance(_entry, dict) and _entry:
                        _entry["user_defined"] = True
                        _entry["velocity_user_locked"] = True
                for _r, _lane in enumerate(self.playlist_automation):
                    if isinstance(_lane, dict) and _lane:
                        _lane["user_defined"] = True
                if hasattr(self, 'instrument_scripts'):
                    self.instrument_scripts = dict(data.get("instrument_scripts", {}) or {})
                self.instrument_param_state = dict(data.get("instrument_param_state", {}) or {})
                for _name, _state in self.instrument_param_state.items():
                    if isinstance(_state, dict) and _state:
                        _state["user_locked"] = True
                self.patch_connections = list(data.get("patch_connections", []) or [])
                self.instrument_param_generated = dict(data.get("instrument_param_generated", {}) or {})
                self._composition_generation_counter = int(data.get("generation_counter", 0))
                if hasattr(self, 'domain_eq_engine') and data.get("domain_eq"):
                    try:
                        self.domain_eq_engine.from_json(data["domain_eq"])
                    except Exception:
                        pass

                # Rebuild pad grid to match seq_length, then paint from memory
                if hasattr(self, 'rebuild_sequencer_steps'):
                    self.rebuild_sequencer_steps(seq_len)
                if hasattr(self, 'reload_active_instrument_sequencer_ui'):
                    self.reload_active_instrument_sequencer_ui()
                # Restore active instrument selection after rebuild
                act = data.get("active_instrument") or ""
                if act and hasattr(self, 'instrument_selector_dropdown'):
                    idx = self.instrument_selector_dropdown.findText(act)
                    if idx >= 0:
                        self.instrument_selector_dropdown.setCurrentIndex(idx)
                # Invalidate play buffer so next Play re-renders from loaded state
                with getattr(self, 'play_lock', threading.Lock()):
                    self.play_buffer = None
                    self.play_cursor = 0
                try:
                    self._refresh_visualizers_meum_playlist()
                except Exception:
                    pass
            finally:
                self._live_engine_update_guard = False
                self._step_ui_guard = False
            QMessageBox.information(
                self, "Loaded",
                f"Project loaded:\n{path}\n\n"
                f"BPM {data.get('bpm')} · {seq_len} steps · {rows} playlist rows\n"
                f"Global playlist: {'ON' if data.get('global_playlist', True) else 'OFF'}\n"
                f"Hit ▶ PLAY to render this arrangement."
            )
        except Exception as e:
            self._live_engine_update_guard = False
            self._step_ui_guard = False
            QMessageBox.warning(self, "Load failed", str(e))

    def open_keyboard_test_window(self):

        """One-shot keyboard / pad test for selected or global instruments."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard / Instrument Test")
        dlg.resize(520, 220)
        dlg.setStyleSheet(DAW_STYLE)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Play short hits — Selected instrument or All (global)."))
        row = QHBoxLayout()
        btn_sel = QPushButton("▶ Play Selected")
        btn_all = QPushButton("▶ Play All (Global)")
        row.addWidget(btn_sel)
        row.addWidget(btn_all)
        lay.addLayout(row)
        grid = QGridLayout()
        notes = ["C", "D", "E", "F", "G", "A", "B"]
        for i, n in enumerate(notes):
            b = QPushButton(n)
            b.clicked.connect(lambda checked=False, idx=i: self._keyboard_note_hit(idx, global_mode=False))
            grid.addWidget(b, 0, i)
        lay.addLayout(grid)
        btn_sel.clicked.connect(lambda: self._keyboard_note_hit(0, global_mode=False))
        btn_all.clicked.connect(lambda: self.trigger_all_instruments_hit())
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec()

    def _keyboard_note_hit(self, note_idx, global_mode=False):
        if global_mode:
            self.trigger_all_instruments_hit()
            return
        name = self.instrument_selector_dropdown.currentText() if hasattr(self, 'instrument_selector_dropdown') else self.instrument_names_48[0]
        amp = 1.0
        if hasattr(self, 'slider_step_amp'):
            amp = self.slider_step_amp.value() / 100.0
        self._pkp_fire_step_hit(name, note_idx % 16, amp)

    def trigger_all_instruments_hit(self):
        """DJ-style: fire a short hit on every operator at once (staggered micro-delay via single mixed buffer)."""
        try:
            sr = 44100
            n = int(sr * 0.08)
            t = np.linspace(0, 0.08, n, endpoint=False)
            mix = np.zeros(n, dtype=np.float32)
            for i, name in enumerate(self.instrument_names_48):
                freq = 44.0 * MEUM_POWERS_36[i % 36]
                mix += (0.15 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
            mix *= float(getattr(self, 'master_volume', 0.8))
            if isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope):
                idx = np.linspace(0, len(mix) - 1, 100).astype(int)
                self.visual_oscilloscope.update_waveform(mix[idx])
            if HAS_SOUNDDEVICE:
                sd.play(mix, sr, blocking=False)
            print("[DJ] Trigger All — global instrument hit")
        except Exception as e:
            print(f"[DJ] trigger all error: {e}")

    def _on_viz_mode_changed(self, idx):
        labels = [
            "📊 2.5D Scenograph + Scope",
            "📊 Effected Waveform Scene",
            "📊 Overall Wave Pattern",
            "📊 Per-Instrument Activity Vectors",
        ]
        if hasattr(self, 'scope_status_label') and 0 <= idx < len(labels):
            self.scope_status_label.setText(labels[idx] + "  |  Status: Live")
        if hasattr(self, 'video_synth_viewer'):
            self.video_synth_viewer.set_mode(idx)

    def _direct_playlist_operators(self):
        """Operators named on playlist rows / paint table (no dependency closure)."""
        names = set()
        for row in getattr(self, 'master_playlist_data', []) or []:
            op = (row.get("operator") or "").strip()
            if op:
                names.add(op)
        if hasattr(self, 'active_paint_table') and self.active_paint_table:
            table = self.active_paint_table
            for r in range(table.rowCount()):
                item = table.item(r, 1)
                if item and item.text().strip():
                    names.add(item.text().strip())
        return names

    def _patch_dependency_sources(self):
        """
        Build reverse adjacency: target → set of sources that feed it
        (user patch_connections + GLOBAL_BUS cables). A user parameter on a
        source can affect the timeline if the target is playlist-effective.
        """
        rev = {}
        for c in getattr(self, 'patch_connections', []) or []:
            src = (c.get("source") or "").strip()
            tgt = (c.get("target") or "").strip()
            if src and tgt:
                rev.setdefault(tgt, set()).add(src)
        try:
            for c in getattr(GLOBAL_BUS, 'global_cables', []) or []:
                src = (c.get("src_module") or "").strip()
                tgt = (c.get("tgt_module") or "").strip()
                if src and tgt:
                    rev.setdefault(tgt, set()).add(src)
        except Exception:
            pass
        return rev

    def _playlist_effective_instruments(self):
        """
        Instruments with net effect on the playlist timeline, including
        *dependency closure*: any instrument that feeds a playlist operator
        (directly or transitively) via user-accessible patch routing is
        included, because changing its parameters changes the timeline mix.
        If the playlist is empty / disabled, all instruments are in scope.
        """
        global_pl = True
        if hasattr(self, 'chk_global_playlist'):
            global_pl = bool(self.chk_global_playlist.isChecked())

        roots = self._direct_playlist_operators()
        if not global_pl or not roots:
            return set(getattr(self, 'instrument_names_48', []))

        # BFS backward along patch edges: anything that feeds a root can affect t
        rev = self._patch_dependency_sources()
        effective = set(roots)
        stack = list(roots)
        while stack:
            node = stack.pop()
            for src in rev.get(node, ()):
                if src not in effective:
                    effective.add(src)
                    stack.append(src)
        return effective

    def _mark_step_touched(self, mem, s):
        """
        USER_TOUCHED_TRACKING: record that a human actually edited this step
        (via pad click or the amp/pitch slider), as opposed to it merely being
        ON because a default instrument, saved project, or additive engine
        (Randomizer/PLL/Patch-Bay Optimizer) set it that way.

        Without this, `_step_has_net_effect` had no way to distinguish "user
        programmed this" from "this shipped/loaded already on at amplitude
        1.0" — which is why default/preset content was being reported as
        user-defined (amps_quantized counting preset steps) even when nothing
        had been edited. Only _on_step_pad_clicked and _on_step_amp_slider
        (the real manual-edit entry points) call this.
        """
        touched = mem.setdefault("touched", set())
        touched.add(s)

    def _step_has_net_effect(self, mem, s):
        """
        Step counts as effective *user* input only if:
          - it was actually touched by the user (pad click / amp slider), AND
          - it is ON with non-negligible amplitude.

        Steps that are ON purely because a default preset, saved project, or
        an additive engine (Randomizer/PLL/Optimizer) set them are NOT user
        net-effect — they remain free for those engines to reshape until a
        person actually edits them.
        """
        steps = mem.get("steps", [])
        amps = mem.get("amplitudes", [])
        touched = mem.get("touched", ())
        if s >= len(steps) or not steps[s]:
            return False
        if s not in touched:
            return False
        amp = float(amps[s]) if s < len(amps) else 1.0
        return abs(amp) > 0.02  # near-zero amp → no audible net effect

    def _instrument_has_net_effect(self, name, count=None):
        """
        True if this instrument can affect the timeline (playlist root or
        dependency source into one) and has at least one audible step.
        """
        if count is None:
            count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        effective = self._playlist_effective_instruments()
        if name not in effective:
            return False
        mem = self.instrument_sequencer_memory.get(name, {})
        return any(self._step_has_net_effect(mem, s) for s in range(count))

    def _user_pattern_mask(self, mem, count, instrument_name=None):
        """
        A step is protected 'user-specified' only when it has net effect:
          - step is ON with amplitude above near-silence
          - and the instrument is playlist-effective *or* reaches the timeline
            through a dependency (patch/bus into a playlist operator)

        If changing this parameter can change the mix at any playlist time t
        via another user-accessible control path, it is protected.
        Otherwise additive engines may freely reshape the slot.
        """
        effective_ok = True
        if instrument_name is not None:
            effective_ok = instrument_name in self._playlist_effective_instruments()

        mask = []
        for s in range(count):
            if not effective_ok:
                mask.append(False)
                continue
            mask.append(self._step_has_net_effect(mem, s))
        return mask

    def _seed_is_absent(self):
        """
        True when seed field is empty/whitespace OR numeric zero (0, 0.0, 0.00…).
        Empty and zero are treated the same for bootstrap: no geometric anchor is
        considered present, so seed may be derived or kit-assigned. Non-zero values
        (incl. tiny irrationals) count as a real seed.
        """
        if not hasattr(self, 'input_seed_val'):
            return True
        text = self._seed_text()
        if text == "":
            return True
        try:
            return abs(float(text)) == 0.0
        except ValueError:
            # Non-numeric text still counts as a seed token (hashed later)
            return False

    def _fingerprint_program(self):
        """Fingerprint only steps with net effect on the playlist timeline."""
        parts = []
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        effective = self._playlist_effective_instruments()
        for name in getattr(self, 'instrument_names_48', []):
            if name not in effective:
                continue
            mem = self.instrument_sequencer_memory.get(name, {})
            for s in range(count):
                if self._step_has_net_effect(mem, s):
                    amp = float(mem.get("amplitudes", [1.0])[s]) if s < len(mem.get("amplitudes", [])) else 1.0
                    parts.append(f"{name}:{s}:{amp:.2f}")
        return abs(hash("|".join(parts) or "empty")) % (10**12)

    def _program_has_net_effect(self):
        """True only if some instrument both appears on the playlist and has audible steps."""
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        for name in getattr(self, 'instrument_names_48', []):
            if self._instrument_has_net_effect(name, count):
                return True
        return False

    def bootstrap_seed_and_program_parameters(self):
        """Case-driven seed/program bootstrap (documented 4-way empty boot).

        When both seed and program are absent (Case A), pick one of four
        outcomes with equal 25% likelihood:

          BOTH      — kit seed into the seed field + sparse program/sequences
          SEED      — kit seed only; pads/playlist stay empty
          SEQUENCES — kit program/sequences only; seed field stays empty
          NEITHER   — no kit write; engines get transient runtime entropy only

        Case B (program, no seed): derive seed from program fingerprint (no UI write).
        Case C (seed, no program): seed-derived sparse program on empty slots only.
        Case D (seed + program): no bootstrap changes.
        """
        seed_absent = self._seed_is_absent()
        try:
            program_present = bool(self._program_has_net_effect())
        except Exception:
            program_present = False

        # Case D
        if (not seed_absent) and program_present:
            self._bootstrap_mode = "CASE_D_UNCHANGED"
            return self.get_numeric_seed()

        # Case B — program present, no seed: fingerprint only (never write seed field)
        if seed_absent and program_present:
            try:
                fingerprint = self._fingerprint_program()
            except Exception:
                fingerprint = 0
            self._bootstrap_mode = "CASE_B_FINGERPRINT"
            if fingerprint:
                return int(fingerprint % (2**31))
            if not hasattr(self, "_runtime_engine_seed"):
                self._runtime_engine_seed = int((time.time_ns() ^ id(self)) & 0x7fffffff)
            return int(self._runtime_engine_seed)

        # Case C — seed present, no program: fill sparse sequences from seed
        if (not seed_absent) and (not program_present):
            numeric = self.get_numeric_seed()
            self._bootstrap_mode = "CASE_C_SEED_PROGRAM"
            try:
                self._provide_seed_program_parameters(numeric)
            except Exception as exc:
                print(f"[Bootstrap] Case C program fill skipped: {exc}")
            return numeric

        # Case A — no seed, no program: equal 25% for BOTH / SEED / SEQUENCES / NEITHER
        if not hasattr(self, "_case_a_roll"):
            # Stable per-session roll so repeated engine calls don't flip modes.
            rng = random.Random(int((time.time_ns() ^ id(self)) & 0x7fffffff))
            self._case_a_roll = rng.randrange(4)

        roll = int(getattr(self, "_case_a_roll", 3))
        modes = ("BOTH", "SEED", "SEQUENCES", "NEITHER")
        mode = modes[roll % 4]
        self._bootstrap_mode = f"CASE_A_{mode}"

        kit_seed = int((time.time_ns() ^ (id(self) * 2654435761)) & 0x7fffffff)
        if kit_seed == 0:
            kit_seed = 1

        if mode in ("BOTH", "SEED"):
            # Write a visible kit seed so the user can see startup chose one.
            try:
                if hasattr(self, "input_seed_val"):
                    if hasattr(self.input_seed_val, "setPlainText"):
                        self.input_seed_val.setPlainText(str(kit_seed))
                    elif hasattr(self.input_seed_val, "setText"):
                        self.input_seed_val.setText(str(kit_seed))
            except Exception as exc:
                print(f"[Bootstrap] seed field write skipped: {exc}")

        if mode in ("BOTH", "SEQUENCES"):
            try:
                self._provide_seed_program_parameters(kit_seed)
            except Exception as exc:
                print(f"[Bootstrap] sequences fill skipped: {exc}")

        if mode == "NEITHER":
            if not hasattr(self, "_runtime_engine_seed"):
                self._runtime_engine_seed = kit_seed
            numeric = int(self._runtime_engine_seed)
        elif mode == "SEQUENCES":
            # Seed field stays empty; engines still need a number.
            numeric = kit_seed
            if not hasattr(self, "_runtime_engine_seed"):
                self._runtime_engine_seed = kit_seed
        else:
            numeric = kit_seed

        try:
            labels = {
                "BOTH": "Boot 25%: seed + sequences",
                "SEED": "Boot 25%: seed only",
                "SEQUENCES": "Boot 25%: sequences only",
                "NEITHER": "Boot 25%: neither (empty)",
            }
            msg = labels.get(mode, mode)
            if hasattr(self, "lbl_boot_mode"):
                self.lbl_boot_mode.setText(f"🎲 {msg}")
            if hasattr(self, "scope_status_label"):
                self.scope_status_label.setText(f"🎲 {msg}")
        except Exception:
            pass
        print(f"[Bootstrap] Case A → {mode} (roll={roll})")
        return int(numeric % (2**31))

    def _provide_seed_program_parameters(self, numeric_seed):
        """
        Kit-provided program parameters from seed — sparse Euclidean-ish carriers
        so the playlist editor has structure to write against. Only fills empty fields.
        """
        rng = np.random.default_rng(int(numeric_seed) % (2**31))
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        names = list(getattr(self, 'instrument_names_48', []))

        for i, name in enumerate(names):
            mem = self.instrument_sequencer_memory.setdefault(name, {
                "steps": [False] * count,
                "amplitudes": [1.0] * count,
                "gates": [True] * count,
                "probabilities": [100] * count,
            })
            self._ensure_seq_mem_length(mem, count)
            pulses = max(1, int((i * MEUM_CONSTANT + (numeric_seed % 5) + 2) % 5) + 1)
            pulses = min(pulses, max(1, count // 2))
            for s in range(count):
                on = ((s * pulses) % count) < pulses and (rng.random() < 0.85)
                mem["steps"][s] = bool(on)
                if on:
                    ladder = [0.5, 0.75, 1.0]
                    mem["amplitudes"][s] = float(ladder[(i + s + int(numeric_seed)) % len(ladder)])
                    mem["probabilities"][s] = 100

        rows = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 32
        if not hasattr(self, 'master_playlist_data') or self.master_playlist_data is None:
            self.master_playlist_data = []
        while len(self.master_playlist_data) < rows:
            self.master_playlist_data.append({})
        for row_idx in range(rows):
            op_name = names[(row_idx + int(numeric_seed % max(len(names), 1))) % max(len(names), 1)] if names else "Operator"
            entry = self.master_playlist_data[row_idx]
            if not entry.get("operator"):
                entry["operator"] = op_name
            if not entry.get("time_marker"):
                entry["time_marker"] = f"T + {row_idx * 3.5:.1f}s"
            if not entry.get("script_tag"):
                entry["script_tag"] = f"Script::{op_name[:4].upper()}-X{row_idx}"
            if entry.get("velocity") is None:
                entry["velocity"] = 1.0
            if not entry.get("modulation"):
                entry["modulation"] = "Geometric Nullifier Lock"
            if not entry.get("multi_seq"):
                entry["multi_seq"] = f"Multi-Load Active [{row_idx % 3 + 1}]"
            self.master_playlist_data[row_idx] = entry

        if hasattr(self, 'active_paint_table') and self.active_paint_table:
            table = self.active_paint_table
            for row_idx in range(min(rows, table.rowCount())):
                entry = self.master_playlist_data[row_idx]
                if table.item(row_idx, 1) is None or not (table.item(row_idx, 1).text() or "").strip():
                    table.set_cell_item(row_idx, 1, entry.get("operator", ""))
                if table.item(row_idx, 0) is None or not (table.item(row_idx, 0).text() or "").strip():
                    table.set_cell_item(row_idx, 0, entry.get("time_marker", ""))
                if table.item(row_idx, 3) is None or not (table.item(row_idx, 3).text() or "").strip():
                    table.set_cell_item(row_idx, 3, "100%")

        # Playlist velocity follows the seeded harmonic field as well.
        self._phase_lock_playlist_velocity(rng=np.random.default_rng(numeric_seed), strength=0.45, randomize=True)

        if hasattr(self, 'reload_active_instrument_sequencer_ui'):
            self.reload_active_instrument_sequencer_ui()

    def simplify_redundant_user_definitions(self):
        """
        Pre-pass before additive fill: collapse redundant user definitions to the
        simplest identical parameter settings so convergent engines have free
        slots to work with — without destroying intentional unique design.

        Does:
          1. Quantize amplitudes on user steps to a minimal discrete set (simplest identical values)
          2. Deduplicate identical consecutive runs of OFF steps (no-op) / normalize default amps on OFF steps
          3. Across instruments: if two operators share an identical pattern, keep canonical
             amps on the first and snap the duplicate to the same simplest values (linked)
          4. Deduplicate patch_connections and GLOBAL_BUS cables (identical edges → one)
          5. Merge domain partitions that share identical equation+logic+bounds
          6. Collapse stock-identical instrument scripts to a single shared template text
        """
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        stats = {"amps_quantized": 0, "patterns_linked": 0, "patches_deduped": 0,
                 "domains_merged": 0, "scripts_collapsed": 0}

        # --- 1/2 Sequencer: quantize ON-step amps to simplest identical ladder ---
        # Ladder: 0.25, 0.5, 0.75, 1.0 (minimal distinct set)
        ladder = np.array([0.25, 0.5, 0.75, 1.0])
        pattern_index = {}  # fingerprint -> first instrument name

        for name in self.instrument_names_48:
            mem = self.instrument_sequencer_memory.get(name)
            if not isinstance(mem, dict):
                mem = {"steps": [False] * count, "amplitudes": [1.0] * count, "pitches": [1.0] * count, "gates": [True] * count, "probabilities": [100] * count, "touched": set()}
                self.instrument_sequencer_memory[name] = mem
            self._ensure_seq_mem_length(mem, count)

            # Normalize OFF steps to default amp 1.0 (frees "touched" false positives)
            for s in range(count):
                if not mem["steps"][s]:
                    if abs(float(mem["amplitudes"][s]) - 1.0) > 1e-6 and abs(float(mem["amplitudes"][s]) - 0.5) > 1e-6:
                        # Only reset amp on OFF if it wasn't meaningfully unique — keep if far from defaults
                        pass
                    else:
                        mem["amplitudes"][s] = 1.0

            # Quantize ON-step amplitudes to nearest ladder value
            for s in range(count):
                if mem["steps"][s]:
                    amp = float(mem["amplitudes"][s])
                    nearest = float(ladder[np.argmin(np.abs(ladder - amp))])
                    if abs(nearest - amp) > 1e-9:
                        mem["amplitudes"][s] = nearest
                        stats["amps_quantized"] += 1
                    else:
                        mem["amplitudes"][s] = nearest  # exact ladder snap

            # Fingerprint pattern for cross-instrument linking
            fp = tuple(
                (bool(mem["steps"][s]), round(float(mem["amplitudes"][s]), 2))
                for s in range(count)
            )
            if any(mem["steps"][s] for s in range(count)):
                if fp in pattern_index:
                    # Snap this instrument's amps exactly to the canonical instrument's ladder values
                    canon = self.instrument_sequencer_memory[pattern_index[fp]]
                    for s in range(count):
                        mem["steps"][s] = bool(canon["steps"][s])
                        mem["amplitudes"][s] = float(canon["amplitudes"][s])
                    stats["patterns_linked"] += 1
                else:
                    pattern_index[fp] = name

        # --- 4 Patch connections dedupe ---
        if hasattr(self, 'patch_connections') and self.patch_connections:
            seen = set()
            unique = []
            for c in self.patch_connections:
                key = (c.get("source"), c.get("target"))
                if key in seen or not key[0] or not key[1]:
                    stats["patches_deduped"] += 1
                    continue
                seen.add(key)
                unique.append(c)
            self.patch_connections = unique

        try:
            if GLOBAL_BUS.global_cables:
                seen_bus = set()
                unique_bus = []
                for c in GLOBAL_BUS.global_cables:
                    key = (c.get("src_module"), c.get("tgt_module"), c.get("src_node"), c.get("tgt_node"))
                    if key in seen_bus:
                        stats["patches_deduped"] += 1
                        continue
                    seen_bus.add(key)
                    unique_bus.append(c)
                if len(unique_bus) != len(GLOBAL_BUS.global_cables):
                    GLOBAL_BUS.global_cables = unique_bus
                    GLOBAL_BUS.broadcast_update()
        except Exception:
            pass

        # --- 5 Domain partitions: merge identical equation+logic+bounds ---
        if hasattr(self, 'domain_eq_engine') and self.domain_eq_engine.domains:
            seen_dom = {}
            merged = []
            for dom in self.domain_eq_engine.domains:
                key = (
                    dom.get("axis"),
                    round(float(dom.get("t0", 0)), 4),
                    round(float(dom.get("t1", 1)), 4),
                    round(float(dom.get("x0", -1)), 4),
                    round(float(dom.get("x1", 1)), 4),
                    round(float(dom.get("y0", -1)), 4),
                    round(float(dom.get("y1", 1)), 4),
                    (dom.get("logic") or "True").strip(),
                    (dom.get("equation") or "0").strip(),
                    round(float(dom.get("limit_lo", -1)), 4),
                    round(float(dom.get("limit_hi", 1)), 4),
                )
                if key in seen_dom:
                    # Keep simplest: max weight, max seed_weight of the pair
                    prev = seen_dom[key]
                    prev["weight"] = max(float(prev.get("weight", 1)), float(dom.get("weight", 1)))
                    prev["seed_weight"] = max(float(prev.get("seed_weight", 0)), float(dom.get("seed_weight", 0)))
                    stats["domains_merged"] += 1
                else:
                    seen_dom[key] = dom
                    merged.append(dom)
            self.domain_eq_engine.domains = merged

        # --- 6 Scripts: collapse identical stock/custom texts to one canonical string ---
        if hasattr(self, 'instrument_scripts') and self.instrument_scripts:
            text_to_names = {}
            for name, script in self.instrument_scripts.items():
                norm = (script or "").strip()
                text_to_names.setdefault(norm, []).append(name)
            for norm, names in text_to_names.items():
                if len(names) > 1 and norm:
                    # All already identical — just count as collapsed (single shared definition)
                    stats["scripts_collapsed"] += len(names) - 1

        print(
            f"[Simplify] Redundant user defs collapsed — "
            f"amps_quantized={stats['amps_quantized']}, patterns_linked={stats['patterns_linked']}, "
            f"patches_deduped={stats['patches_deduped']}, domains_merged={stats['domains_merged']}, "
            f"scripts_collapsed={stats['scripts_collapsed']}"
        )
        if hasattr(self, 'reload_active_instrument_sequencer_ui'):
            self.reload_active_instrument_sequencer_ui()
        return stats

    def apply_euclidean_and_idealized_rhythms(self):
        """Euclidean idealization — may touch any combination of step geometry subsystems."""

        numeric_seed = self.get_numeric_seed()
        rng = np.random.default_rng(numeric_seed if numeric_seed else 1)
        combo = int(rng.integers(1, 16))
        do_steps = bool(combo & 1)
        do_amps = bool(combo & 2)
        do_pitches = bool(combo & 4)
        do_probs = bool(combo & 8)
        # Explicit engine action may use a transient seed, but never writes the user field.
        seed = self.bootstrap_seed_and_program_parameters()
        self.simplify_redundant_user_definitions()

        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        rng = np.random.default_rng(seed)

        filled = 0
        preserved = 0

        for i, name in enumerate(self.instrument_names_48):
            mem = self.instrument_sequencer_memory[name]
            self._ensure_seq_mem_length(mem, count)
            user_mask = self._user_pattern_mask(mem, count, instrument_name=name)

            # Per-instrument Euclidean pulse count (golden-ish, seed-stable)
            pulses = max(2, int((i * MEUM_CONSTANT + (seed % 5) + 3) % 7) + 2)
            pulses = min(pulses, count)
            euclidean = [((s * pulses) % count) < pulses for s in range(count)]

            # Spectral opposite of user density: prefer filling where user is sparse
            user_density = sum(user_mask) / max(count, 1)

            for s in range(count):
                if user_mask[s]:
                    # Preserve user step; may only gently raise amp toward phase-lock envelope
                    preserved += 1
                    lock_env = 0.5 + 0.5 * abs(np.sin(s * np.pi / count))
                    mem["amplitudes"][s] = float(max(mem["amplitudes"][s], lock_env * 0.85))
                    mem["probabilities"][s] = max(int(mem["probabilities"][s]), 100)
                    continue

                # Empty / unspecified slot — additive fill only
                is_eucl = euclidean[s]
                # Opposite / complement: occasionally place a soft hit where Euclidean is OFF
                # when user density is high (fill the sparse complement)
                complement = (not is_eucl) and (user_density > 0.35) and (rng.random() < 0.18)

                if is_eucl or complement:
                    if do_steps:
                        mem["steps"][s] = True
                    base_amp = 0.55 + 0.35 * abs(np.sin(s * np.pi / count + i * 0.1))
                    if complement:
                        base_amp *= 0.45  # softer opposite
                    if do_amps:
                        mem["amplitudes"][s] = float(np.clip(base_amp, 0.15, 1.0))
                    if do_probs:
                        mem["probabilities"][s] = 100 if is_eucl else int(rng.integers(55, 85))
                    filled += 1
                # else leave False / untouched

        self._engines_write_automation_lanes(source="euclidean")
        self.reload_active_instrument_sequencer_ui()
        print(
            f"[Euclidean Phase-Lock] Additive fill complete. "
            f"Preserved user steps≈{preserved}, filled empty slots={filled}. "
            f"Seed={self._seed_text() if hasattr(self, 'input_seed_val') else seed}"
        )

    def _engines_write_automation_lanes(self, source="seeded"):
        """
        Randomizer / Euclidean may envelope automation amounts on empty playlist
        automation slots only — never overwrites user-painted automation lanes.
        """
        if not hasattr(self, 'playlist_automation') or self.playlist_automation is None:
            self.playlist_automation = []
        rows = min(1024, max(1, int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 96))
        while len(self.playlist_automation) < rows:
            self.playlist_automation.append({})
        names = list(getattr(self, 'instrument_names_48', []))
        params = ["eqr", "fractalizer", "pkp_decay", "filter", "drive"]
        seed = self.get_numeric_seed() if hasattr(self, 'get_numeric_seed') else 1
        rng = np.random.default_rng(int(seed) % (2**31) + (0 if source == "seeded" else 17))
        written = 0
        for r in range(rows):
            if self.playlist_automation[r]:
                continue  # user lane present — leave alone
            if rng.random() > 0.35:
                continue
            op = names[(r + int(seed)) % len(names)] if names else "Operator"
            param = params[(r + (0 if source == "seeded" else 2)) % len(params)]
            amt = float(0.35 + 0.5 * rng.random())
            self.playlist_automation[r] = {
                "generated_by_engine": True,
                "operator": op,
                "param": param,
                "amount": amt,
                "direction": 1.0 if rng.random() > 0.5 else -1.0,
                "overlap": 0.0,
                "blend_percent": float(rng.uniform(0.0, 100.0)),
                "partner": "",
                "mode": f"engine:{source}",
                "write_steps": False,
            }
            self._engine_generated_automation_rows.add(r)
            written += 1
        # RECOMMENDED_POWER_LAYER: couple automation generation to calculated
        # velocity painting. This remains opt-in because this method is called by
        # explicit Randomizer / Euclidean actions, never during boot.
        painted_velocity = self._paint_generated_parameters(rng, rows=rows, source=source)
        if written:
            # Engine-generated automation is composition metadata, not permission
            # to move user-owned GLOBAL EQR / Fractallizer / PKP Decay controls.
            # It remains available to the renderer/context engine without pushing
            # itself back into the live global slider UI.
            print(f"[Automation] {source} wrote {written} playlist automation lane(s); velocity paint={painted_velocity}")
        elif painted_velocity:
            print(f"[Automation] {source} velocity paint={painted_velocity}")



    def _engines_both_live(self):
        r = bool(getattr(self, 'btn_local_randomize', None) and self.btn_local_randomize.isChecked())
        r = r or bool(getattr(self, 'btn_seeded_randomize', None) and self.btn_seeded_randomize.isChecked())
        p = bool(getattr(self, 'btn_local_phase_lock', None) and self.btn_local_phase_lock.isChecked())
        p = p or bool(getattr(self, 'btn_idealize_rhythm', None) and self.btn_idealize_rhythm.isChecked())
        return r, p

    def _ideal_randomizer_pattern(self, name, count, rng):
        """Non-writing seed-first ideal for the Randomizer/Phase-Lock midpoint."""
        import hashlib
        seed = int(self.get_numeric_seed()) if hasattr(self, "get_numeric_seed") else 1
        mem = self.instrument_sequencer_memory.get(name, {})
        steps = [False] * count
        amps = [0.0] * count
        pitches = [1.0] * count

        try:
            user_mask = self._user_pattern_mask(mem, count, instrument_name=name)
        except Exception:
            user_mask = [False] * count

        user_hits = [
            s for s in range(count)
            if s < len(mem.get("steps", []))
            and s < len(user_mask)
            and user_mask[s]
            and mem["steps"][s]
        ]

        try:
            op_idx = self.instrument_names_48.index(name)
        except Exception:
            op_idx = 0

        if not user_hits:
            for s in range(count):
                stable = hashlib.sha256(
                    f"R|{seed}|{name}|{op_idx}|{s}".encode("utf-8", "replace")
                ).digest()
                u = int.from_bytes(stable[:8], "big") / float(2**64)
                v = int.from_bytes(stable[8:16], "big") / float(2**64)
                # Seed-dependent but convergent density; no Meum-only identity.
                density = 0.18 + 0.18 * (
                    0.5 + 0.5 * math.sin(
                        2.0 * math.pi * (u * PHI + seed * 1.3e-6)
                        + (s + 1) * MEUM_LOG2
                    )
                )
                if v < density:
                    steps[s] = True
                    amps[s] = float(np.clip(0.30 + 0.55 * u, 0.20, 0.95))
                    pitch_field = 0.5 + 0.5 * math.cos(
                        2.0 * math.pi * (v * SQRT2 + u * MEUM)
                    )
                    pitches[s] = float(np.clip(
                        2.0 ** ((pitch_field - 0.5) * 0.62),
                        0.60, 1.55
                    ))
            return steps, amps, pitches

        # Fractal echoes preserve the carrier while changing the geometric scale
        # according to the actual seed.
        scales = [1]
        for k in (1, 2, 3):
            sc = int(round(count / (2 ** k) * (
                1.0 + (((seed >> k) % 7) - 3) * 0.035
            )))
            if 1 <= sc < count and sc not in scales:
                scales.append(sc)

        for s in range(count):
            for sc in scales:
                src = user_hits[(s * sc + seed) % len(user_hits)]
                stable = hashlib.sha256(
                    f"R|{seed}|{name}|{s}|{sc}".encode("utf-8", "replace")
                ).digest()
                u = int.from_bytes(stable[:8], "big") / float(2**64)
                if u < 0.20 + 0.10 * ((sc % 5) / 5.0):
                    steps[s] = True
                    src_amp = float(mem.get("amplitudes", [0.7] * count)[src]) if src < len(mem.get("amplitudes", [])) else 0.7
                    amps[s] = max(amps[s], float(np.clip(src_amp * (0.55 / sc), 0.15, 1.0)))
                    v = int.from_bytes(stable[8:16], "big") / float(2**64)
                    pitches[s] = float(np.clip(
                        2.0 ** ((v - 0.5) * 0.56) * (0.96 + 0.04 * MEUM_NORM),
                        0.60, 1.55
                    ))
                    break
        return steps, amps, pitches

    def _ideal_phaselock_pattern(self, name, count, i, seed):
        """Non-writing Euclidean + seed-specific wavefield ideal for midpoint merge."""
        import hashlib
        seed = int(seed)
        steps = [False] * count
        amps = [0.0] * count
        pitches = [1.0] * count

        # Seed chooses both pulse count and phase origin; Meum supplies the metric.
        seed_u, seed_v, seed_w = self._seed_geometry(f"phase|{name}|{i}")
        pulse_field = 0.5 + 0.5 * math.sin(
            2.0 * math.pi * (seed_u * PHI + seed_v * PHI_INV + i * MEUM_LOG2) + seed_w * MEUM
        )
        pulses = max(2, min(
            count,
            int(round(2 + pulse_field * max(2, min(6, count - 2))))
        ))
        phase0 = 2.0 * math.pi * (
            seed_u * SQRT2 + seed_v * PHI_INV + (i + 1) * MEUM_LOG2
        )

        euc = [
            bool(((s * pulses + int(seed % max(count, 1))) % count) < pulses)
            for s in range(count)
        ]

        wf = None
        eng = getattr(self, "wavefield_engine", None)
        if eng is not None:
            try:
                if not getattr(eng, "wavefield", None):
                    eng.compute_wavefield()
                wf = eng.wavefield.get(name) if eng.wavefield else None
            except Exception:
                wf = None

        for s in range(count):
            on = bool(euc[s])
            if wf and s < len(wf.get("euclidean", [])):
                # Union the field with the seed-rotated Euclidean carrier.
                on = on or bool(wf["euclidean"][s])
            if on:
                env = float(wf["envelope"][s]) if wf and s < len(wf.get("envelope", [])) else 0.55
                har = float(wf["seed_harmonics"][s]) if wf and s < len(wf.get("seed_harmonics", [])) else 0.5
                seed_h = 0.5 + 0.5 * math.sin(
                    phase0 + (s + 1) * MEUM_LOG2 + har * math.pi
                )
                amps[s] = float(np.clip(
                    0.30 + 0.52 * env * (0.72 + 0.28 * seed_h),
                    0.15, 1.0
                ))
                pitches[s] = float(np.clip(
                    2.0 ** (
                        (seed_h - 0.5) * 0.58
                        + (har - 0.5) * 0.20
                    ),
                    0.60, 1.60
                ))
        return steps, amps, pitches

    def _midpoint_merge_patterns(self, r_steps, r_amps, r_pitches, l_steps, l_amps, l_pitches, count, rng):
        """Combine randomizer + phase-lock ideals at the midpoint — not additive stack.

        Predictive unison:
          • both ON  → keep, average amp/pitch (shared conviction)
          • one ON   → soft keep at Meum soft-weight (not full force of either alone)
          • both OFF → stay off
        Trigger preference shifts toward averaged density (no double hits).
        """
        steps, amps, pitches = [False] * count, [0.0] * count, [1.0] * count
        for s in range(count):
            ro, lo = bool(r_steps[s]), bool(l_steps[s])
            ra = float(r_amps[s]) if ro else 0.0
            la = float(l_amps[s]) if lo else 0.0
            rp = float(r_pitches[s]) if ro else 1.0
            lp = float(l_pitches[s]) if lo else 1.0
            if ro and lo:
                steps[s] = True
                amps[s] = 0.5 * (ra + la)
                pitches[s] = 0.5 * (rp + lp)
            elif ro or lo:
                # midpoint: partial acceptance, not full additive from one engine
                # Deterministic Meum acceptance: the disagreement is resolved from
                # the two source fields, never from a mutable/random sequence.
                # This keeps the seed-only composition invariant across renders.
                source_amp = ra if ro else la
                source_pitch = rp if ro else lp
                coherence = 0.5 + 0.5 * np.cos((s + 1) * MEUM_NORM * np.pi)
                keep_p = float(np.clip(0.48 + 0.22 * coherence, 0.30, 0.72))
                selector = 0.5 + 0.5 * np.sin((s + 1) * MEUM_INV + MEUM_NORM)
                if selector < keep_p:
                    steps[s] = True
                    amps[s] = float(np.clip(source_amp * (0.72 + 0.18 * (0.5 + 0.5 * coherence)), 0.08, 0.95))
                    pitches[s] = float(source_pitch)
            else:
                # UNISON BRIDGE: when both fields agree on "no hit", do not permit
                # an audible dead zone while both engines are live.  The shared
                # deterministic field supplies a lower-energy bridge note so the
                # composition remains continuously resonant rather than sputtering.
                bridge = 0.5 + 0.5 * math.sin((s + 1) * MEUM + seed * MEUM_NORM)
                steps[s] = True
                amps[s] = float(np.clip(0.22 + 0.20 * bridge, 0.18, 0.42))
                pitches[s] = float(np.clip(2.0 ** ((bridge - 0.5) * 0.34), 0.78, 1.28))
        return steps, amps, pitches

    def apply_composition_midpoint(self, live=False):
        """When BOTH engines are live: one idealization pass (midpoint), not A then B stacked."""
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            return
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        seed = self.get_numeric_seed() if hasattr(self, 'get_numeric_seed') else 1
        self._composition_generation_counter = getattr(self, '_composition_generation_counter', 0) + 1
        # Pure seed RNG — midpoint is a function of seed + current user pads only
        rng = np.random.default_rng(int(seed) % (2**31))
        multi = bool(getattr(self, 'chk_multi_seq_load', None) and self.chk_multi_seq_load.isChecked())
        active = ""
        try:
            active = self.instrument_selector_dropdown.currentText()
        except Exception:
            pass
        names = list(getattr(self, 'instrument_names_48', []) or [])
        for i, name in enumerate(names):
            seed_only = (not any(any((m or {}).get("steps") or []) for m in (getattr(self, "instrument_sequencer_memory", {}) or {}).values()))
            if not multi and active and name != active and not seed_only:
                continue
            mem = self.instrument_sequencer_memory.get(name)
            if not mem:
                continue
            self._ensure_seq_mem_length(mem, count)
            user_mask = (
                self._user_pattern_mask(mem, count, instrument_name=name)
                if hasattr(self, '_user_pattern_mask') else [False] * count
            )
            r_s, r_a, r_p = self._ideal_randomizer_pattern(name, count, rng)
            l_s, l_a, l_p = self._ideal_phaselock_pattern(name, count, i, seed)
            m_s, m_a, m_p = self._midpoint_merge_patterns(r_s, r_a, r_p, l_s, l_a, l_p, count, rng)
            for s in range(count):
                if s < len(user_mask) and user_mask[s]:
                    continue  # never overwrite user defs
                mem['steps'][s] = bool(m_s[s])
                if s < len(mem.get('amplitudes', [])):
                    mem['amplitudes'][s] = float(m_a[s]) if m_s[s] else 0.0
                if s < len(mem.get('pitches', [])):
                    mem['pitches'][s] = float(m_p[s])
                if s < len(mem.get('probabilities', [])):
                    mem['probabilities'][s] = 100 if m_s[s] else 0
        try:
            self._paint_operator_pattern_to_playlist(source="midpoint", rng=rng)
            try:
                self._apply_meum_ideal_hierarchy(rng=rng)
            except Exception as _mh:
                print(f"[Meum hierarchy] {_mh}")
            try:
                self._refresh_visualizers_meum_playlist()
            except Exception:
                pass
        except Exception as e:
            print(f"[Midpoint] playlist: {e}")
        self.reload_active_instrument_sequencer_ui()
        print("[Composition] midpoint unison (randomizer ∧ phase-lock) — not additive stack")

    def _live_composition_tick(self):
        """Heartbeat only: recompute when a real source changed, otherwise do nothing."""
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            return
        r_on, p_on = self._engines_both_live()
        try:
            if r_on and p_on:
                self._apply_live_midpoint_once()
            elif r_on:
                # Compatibility path only; the Randomizer timer is intentionally stopped.
                self._apply_live_engine_once("seeded")
            elif p_on:
                self._apply_live_engine_once("euclidean")
        except Exception as e:
            print(f"[live-composition] {e}")
        if getattr(self, '_seq_ui_pending', False) and not getattr(self, '_live_engine_update_guard', False):
            self._seq_ui_last = 0.0
            self.reload_active_instrument_sequencer_ui()

    def apply_unified_randomizer(self, live=False):
        """Single randomizer path: seeded harmonic fill + multi-instance playlist paint.

        Replaces the dual Seeded Live / GLOBAL RANDOMIZE split so both controls
        share one predictive step (patternology + playlist instances together).
        """
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            return
        snap = self._snapshot_global_effect_sliders() if hasattr(self, '_snapshot_global_effect_sliders') else None
        self._composition_ui_batch = True
        try:
            # Deterministic: same seed → same composition (no generation counter drift)
            self._composition_generation_counter = getattr(self, '_composition_generation_counter', 0) + 1
            rng = np.random.default_rng(int(self.get_numeric_seed()) % (2**31))
            # Patternology (sequencer memory) first
            self.apply_seeded_harmonic_randomization()
            # Playlist multi-instance paint (velocity, blends, overlaps, time offsets)
            try:
                n = self._paint_operator_pattern_to_playlist(source="randomizer", rng=rng)
                print(f"[Randomizer] playlist multi-instance paint → {n} rows")
                try:
                    self._apply_meum_ideal_hierarchy(rng=rng)
                except Exception as _mh:
                    print(f"[Meum hierarchy] {_mh}")
                try:
                    self._refresh_visualizers_meum_playlist()
                except Exception:
                    pass
                # New random base invalidates any prior phase-lock pair
                self._invalidate_live_composition_cache("phase_base", "phase_locked", "phase", "both")
            except Exception as pe:
                print(f"[Randomizer] playlist paint: {pe}")
            try:
                self._paint_step_parameters(
                    rng=rng, randomize=True, strength=0.55,
                    include_velocity=True, include_pitch=True, include_probability=True,
                )
            except Exception:
                pass
            try:
                self._run_composition_context_engine(source="randomizer", rng=rng)
            except Exception as ce:
                print(f"[Randomizer] context: {ce}")
            if hasattr(self, 'reload_active_instrument_sequencer_ui'):
                self.reload_active_instrument_sequencer_ui()
        except Exception as e:
            print(f"[Randomizer] unified skipped: {e}")
        finally:
            self._composition_ui_batch = False
            if snap is not None and hasattr(self, '_restore_global_effect_sliders'):
                self._restore_global_effect_sliders(snap)
            if getattr(self, '_seq_ui_pending', False):
                self._seq_ui_last = 0.0
                self.reload_active_instrument_sequencer_ui()

    def apply_unified_phase_lock(self, live=False):
        """Single phase-lock path: Euclidean geometry + wavefield transducer in one step.

        Replaces Euclidean Live Lock / GLOBAL PHASE-LOCK split so both share one
        coordinated arrangement (geometry + field coherence together).
        """
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            return
        snap = self._snapshot_global_effect_sliders() if hasattr(self, '_snapshot_global_effect_sliders') else None
        self._composition_ui_batch = True
        try:
            self._composition_generation_counter = getattr(self, '_composition_generation_counter', 0) + 1
            rng = np.random.default_rng(int(self.get_numeric_seed()) % (2**31))
            # Euclidean additive structure
            self.apply_euclidean_and_idealized_rhythms()
            # Wavefield sensor→director on the same snapshot
            wf = getattr(self, 'wavefield_engine', None)
            if wf is not None:
                try:
                    wf.apply_phase_locked_randomization()
                except Exception as we:
                    print(f"[Phase-Lock] wavefield: {we}")
            try:
                n = self._paint_operator_pattern_to_playlist(source="phase-lock", rng=rng)
                print(f"[Phase-Lock] playlist multi-instance paint → {n}")
                try:
                    self._apply_meum_ideal_hierarchy(rng=rng)
                except Exception as _mh:
                    print(f"[Meum hierarchy] {_mh}")
                try:
                    self._refresh_visualizers_meum_playlist()
                except Exception:
                    pass
            except Exception as pe:
                print(f"[Phase-Lock] playlist: {pe}")
            try:
                self._paint_step_parameters(
                    rng=rng, randomize=False, strength=0.70,
                    include_velocity=True, include_pitch=True, include_probability=True,
                )
            except Exception:
                pass
            try:
                self._phase_lock_playlist_velocity(rng, strength=0.70, randomize=False)
            except Exception:
                pass
            try:
                self._run_composition_context_engine(source="phase-lock", rng=rng)
            except Exception as ce:
                print(f"[Phase-Lock] context: {ce}")
            if hasattr(self, 'reload_active_instrument_sequencer_ui'):
                self.reload_active_instrument_sequencer_ui()
        except Exception as e:
            print(f"[Phase-Lock] unified skipped: {e}")
        finally:
            self._composition_ui_batch = False
            if snap is not None and hasattr(self, '_restore_global_effect_sliders'):
                self._restore_global_effect_sliders(snap)
            if getattr(self, '_seq_ui_pending', False):
                self._seq_ui_last = 0.0
                self.reload_active_instrument_sequencer_ui()

    def apply_seeded_harmonic_randomization(self):
        """
        Additive Seeded Harmonic Randomizer (non-destructive where possible).

        - Treats user ON steps + non-default amps as a carrier pattern.
        - Never turns OFF user steps; never overwrites user scripts that look customized.
        - Fractally echoes the user pattern into empty slots (self-similar repetition
          at seed-derived scales).
        - Only writes parameters the user has not specified.
        """
        # Explicit engine action may use a transient seed, but never writes the user field.
        numeric_seed = int(self.bootstrap_seed_and_program_parameters()) % (2**31)
        self.simplify_redundant_user_definitions()
        rng = np.random.default_rng(numeric_seed)
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16

        # Do NOT forcibly change the user's selected instrument.
        # (Previously this jumped the dropdown — that was destructive UX.)

        filled_steps = 0
        preserved_steps = 0
        scripts_written = 0

        # Any non-empty combination of subsystems (predictive, seed-stable per call):
        # bit0 steps  bit1 amps  bit2 pitches  bit3 probs  bit4 scripts  bit5 playlist-vel
        combo = int(rng.integers(1, 64))
        do_steps = bool(combo & 1)
        do_amps = bool(combo & 2)
        do_pitches = bool(combo & 4)
        do_probs = bool(combo & 8)
        do_scripts = bool(combo & 16)
        do_playlist = bool(combo & 32)
        # Multi-seq load: when checkbox on, randomizer may touch several instruments' slots
        multi = bool(getattr(self, 'chk_multi_seq_load', None) and self.chk_multi_seq_load.isChecked())
        active_name = ""
        try:
            active_name = self.instrument_selector_dropdown.currentText()
        except Exception:
            pass

        # Read wavefield hints if available (does NOT run PLL apply / Euclidean button)
        wf_engine = getattr(self, 'wavefield_engine', None)
        if wf_engine is not None:
            wf_engine.compute_wavefield()

        for i, name in enumerate(self.instrument_names_48):
            if not multi and active_name and name != active_name:
                # Single-seq mode: only the active instrument is rewritten
                continue
            mem = self.instrument_sequencer_memory[name]
            self._ensure_seq_mem_length(mem, count)
            user_mask = self._user_pattern_mask(mem, count, instrument_name=name)

            # Extract user carrier pattern (list of active indices)
            user_hits = [s for s in range(count) if user_mask[s] and mem["steps"][s]]
            user_amps = [mem["amplitudes"][s] for s in user_hits] if user_hits else [0.7]

            # Fractal scale factors from seed (self-similar echoes of the carrier)
            scales = [1]
            for k in range(1, 4):
                sc = int(round(count / (2 ** k) * (1.0 + ((numeric_seed >> k) % 5) * 0.05))) or 1
                if sc not in scales and sc < count:
                    scales.append(sc)

            for s in range(count):
                if user_mask[s]:
                    preserved_steps += 1
                    continue  # hard preserve
                if not (do_steps or do_amps or do_pitches or do_probs):
                    continue

                # Fractal echo: map step s back onto the user carrier at each scale
                echo_on = False
                echo_amp = 0.0
                if user_hits:
                    for sc in scales:
                        # fold s into a carrier-relative index
                        src = user_hits[(s * sc + (numeric_seed % count)) % len(user_hits)]
                        # stochastic gate — denser when seed modulus is high, but still sparse
                        gate_p = 0.22 + 0.15 * ((numeric_seed + i + sc) % 5) / 5.0
                        # Wavefield communication: bias gate toward Euclidean + seed-harmonic slots
                        if wf_engine is not None:
                            hints = wf_engine.get_hints(name, s) if hasattr(wf_engine, "get_hints") else None
                            if hints:
                                context = self._contextual_numerology(name, s, s) if hasattr(self, "_contextual_numerology") else 0.5
                                gate_p *= (0.75 + 0.5 * context)
                                if hints["euclidean"]:
                                    gate_p = min(0.85, gate_p + 0.2 * hints["seed_harmonic"])
                                else:
                                    gate_p *= 0.55
                        if rng.random() < gate_p:
                            echo_on = True
                            # amplitude inherits fractally from source user amp, attenuated by scale
                            src_amp = mem["amplitudes"][src] if src < len(mem["amplitudes"]) else 0.7
                            echo_amp = max(echo_amp, float(src_amp) * (0.55 / sc))
                            if wf_engine is not None:
                                hints = wf_engine.get_hints(name, s) if hasattr(wf_engine, "get_hints") else None
                                if hints:
                                    echo_amp = max(echo_amp, float(hints["envelope"]) * 0.5)
                else:
                    # No user carrier — light seed texture, prefer wavefield Euclidean slots
                    base_p = 0.12
                    context = self._contextual_numerology(name, s, s) if hasattr(self, "_contextual_numerology") else 0.5
                    base_p *= (0.65 + 0.7 * context)
                    if wf_engine is not None:
                        hints = wf_engine.get_hints(name, s) if hasattr(wf_engine, "get_hints") else None
                        if hints and hints["euclidean"]:
                            base_p = 0.28 * hints["seed_harmonic"]
                    if rng.random() < base_p:
                        echo_on = True
                        echo_amp = 0.35 + 0.25 * rng.random()
                        if wf_engine is not None:
                            hints = wf_engine.get_hints(name, s) if hasattr(wf_engine, "get_hints") else None
                            if hints:
                                echo_amp = max(echo_amp, float(hints["envelope"]) * 0.55)

                if echo_on:
                    mem["steps"][s] = True
                    mem["amplitudes"][s] = float(np.clip(echo_amp, 0.12, 1.0))
                    mem["probabilities"][s] = int(rng.integers(70, 100))
                    if s < len(mem.get("pitches", [])):
                        ctx = self._contextual_numerology(name, s, s) if hasattr(self, "_contextual_numerology") else 0.5
                        mem["pitches"][s] = float(np.clip(0.85 + 0.35 * ctx + rng.uniform(-0.06, 0.06), 0.5, 1.5))
                    filled_steps += 1

            # Scripts: only write if missing or still the stock auto-template
            if hasattr(self, 'instrument_scripts'):
                existing = self.instrument_scripts.get(name, "")
                is_stock = (
                    not existing
                    or existing.strip().startswith("# Script workspace for")
                    or "Seeded Geometric Resonance Script" in existing
                )
                if do_scripts and is_stock:
                    harmonic_multiplier = float((i % 7) + 1) * MEUM_OVER_1_5
                    self.instrument_scripts[name] = (
                        f"# Seeded Geometric Resonance Script [{self._seed_text()}] for {name}\n"
                        f"# (additive — user carrier preserved; fractal fill only)\n"
                        f"def evaluate_wave(x, y, z):\n"
                        f"    m = {harmonic_multiplier}\n"
                        f"    return np.sin(x * m) * np.cos(y / m) - np.tanh(z * 0.5)"
                    )
                    scripts_written += 1

        # Patch bay: rebuild routing graph only (does not touch sequencer/user pads)
        self.generate_ideal_patch_bay_routing()
        self._engines_write_automation_lanes(source="seeded")
        self.reload_active_instrument_sequencer_ui()
        try:
            self._apply_meum_ideal_hierarchy(rng=rng)
        except Exception as _mh:
            print(f"[Meum hierarchy] {_mh}")
        print(
            f"[Seeded Harmonic Randomizer] Additive fractal fill. "
            f"Preserved≈{preserved_steps}, filled={filled_steps}, scripts_updated={scripts_written}. "
            f"Seed='{self._seed_text()}'"
        )
    def generate_ideal_patch_bay_routing(self):
        """
        Additive modular patch optimizer (non-destructive).

        - Never removes or rewires user-created cables.
        - Never changes gain/polarity on existing links.
        - Only inserts sparse, non-redundant feedforward links into gaps
          (targets with no primary input), scored by seed-stable harmonic fit.
        - Also mirrors safe additive fills into GLOBAL_BUS when present.
        """
        # Deduplicate / simplify before gap-fill (idempotent if already simplified upstream)
        if not getattr(self, '_simplify_in_progress', False):
            self._simplify_in_progress = True
            try:
                self.simplify_redundant_user_definitions()
            finally:
                self._simplify_in_progress = False

        if not hasattr(self, 'patch_connections') or self.patch_connections is None:
            self.patch_connections = []

        names = list(self.instrument_names_48)
        n = len(names)
        numeric_seed = self.get_numeric_seed()
        rng = np.random.default_rng(numeric_seed)

        # --- Snapshot user topology (do not clear) ---
        existing_edges = set()
        targets_with_input = set()
        sources_used = set()
        for c in self.patch_connections:
            src = c.get("source")
            tgt = c.get("target")
            if src and tgt:
                existing_edges.add((src, tgt))
                targets_with_input.add(tgt)
                sources_used.add(src)

        # Absorb GLOBAL_BUS user cables into the same occupancy sets
        try:
            for c in getattr(GLOBAL_BUS, 'global_cables', []) or []:
                src = c.get("src_module")
                tgt = c.get("tgt_module")
                if src and tgt:
                    existing_edges.add((src, tgt))
                    targets_with_input.add(tgt)
                    sources_used.add(src)
        except Exception:
            pass

        preserved_count = len(existing_edges)

        # Which instruments look "active" (have user-programmed pads)?
        active_ops = set()
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        for name in names:
            mem = self.instrument_sequencer_memory.get(name, {})
            steps = mem.get("steps", [])
            if any(steps[s] for s in range(min(count, len(steps)))):
                active_ops.add(name)

        # Family buckets (8 families of 6) for harmonic accentuation scoring
        def family(idx):
            return idx // 6

        # --- Candidate generation: only targets that still lack a primary input ---
        unserved = [i for i, nm in enumerate(names) if nm not in targets_with_input]
        if not unserved:
            print(
                f"[Patch Bay Optimizer] Additive pass: all targets already served "
                f"({len(existing_edges)} user/prior links preserved). No changes."
            )
            return

        added = 0
        # Sparse fill budget: at most ~1/3 of unserved, seed-modulated (stabilizing, not dense)
        budget = max(1, int(len(unserved) * (0.25 + 0.15 * ((numeric_seed % 5) / 5.0))))

        # Score each (source, target) candidate; pick best under stochastic soft-max
        for tgt_idx in unserved:
            if added >= budget:
                break
            tgt_name = names[tgt_idx]
            candidates = []
            for src_idx, src_name in enumerate(names):
                if src_idx == tgt_idx:
                    continue
                if (src_name, tgt_name) in existing_edges:
                    continue
                # Prefer active sources; slight preference for same/adjacent family
                score = 0.0
                if src_name in active_ops:
                    score += 2.0
                if tgt_name in active_ops:
                    score += 1.0
                fam_dist = abs(family(src_idx) - family(tgt_idx))
                score += max(0.0, 1.5 - 0.35 * fam_dist)
                # Golden-ratio geometric bias (deterministic, seed-shifted)
                geo = abs(((src_idx * 1.61803398875 + numeric_seed) % n) - tgt_idx)
                score += max(0.0, 1.0 - geo / max(n * 0.5, 1))
                # Mild entropy so ties resolve stochastically but repeatably
                score += float(rng.uniform(0.0, 0.35))
                candidates.append((score, src_idx, src_name))

            if not candidates:
                continue
            candidates.sort(key=lambda x: -x[0])
            # Soft pick among top-3 for generalized, non-brittle choice
            top = candidates[: min(3, len(candidates))]
            weights = np.array([c[0] for c in top], dtype=float)
            weights = np.maximum(weights, 1e-6)
            weights = weights / weights.sum()
            pick = int(rng.choice(len(top), p=weights))
            _, src_idx, src_name = top[pick]

            # Stabilizing gain: moderate, never extreme
            weight = float(np.clip(0.35 + 0.4 * ((numeric_seed + src_idx + tgt_idx) % 7) / 7.0, 0.2, 0.85))

            connection = {
                "source": src_name,
                "target": tgt_name,
                "weight": weight,
                "origin": "additive_optimizer",
            }
            self.patch_connections.append(connection)
            existing_edges.add((src_name, tgt_name))
            targets_with_input.add(tgt_name)
            added += 1

            # Mirror into GLOBAL_BUS without touching existing bus cables
            try:
                already = any(
                    c.get("src_module") == src_name and c.get("tgt_module") == tgt_name
                    for c in getattr(GLOBAL_BUS, 'global_cables', [])
                )
                if not already:
                    GLOBAL_BUS.add_cable(
                        src_module=src_name,
                        src_node="Out",
                        tgt_module=tgt_name,
                        tgt_node="Primary Sum Node",
                        polarity="+",
                        gain=weight,
                    )
            except Exception:
                pass

        print(
            f"[Patch Bay Optimizer] Additive convolution: preserved={preserved_count}, "
            f"added={added}, budget={budget}, seed='{self._seed_text()}'"
        )
    def _on_master_vol_changed(self, val):
        self.master_volume = val / 100.0
        if hasattr(self, 'lbl_master_vol'):
            self.lbl_master_vol.setText(f"{val}%")

    # =====================================================================
    # CONVOLVE_FIT_FEATURE — WAV carrier loading and spectral-fit helpers
    # =====================================================================
    def load_wav_carrier_dialog(self):
        """Load a WAV file as the global carrier/reference waveform."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Load WAV Carrier", "",
                "WAV Audio Files (*.wav);;All Files (*)"
            )
            if not file_path:
                return
            self._load_wav_path(file_path)
        except Exception as e:
            print(f"[WAV Carrier] Load failed: {e}")
            QMessageBox.critical(self, "WAV Load Error", str(e))

    # =====================================================================
    # MEDIA_IMPORT_FEATURE — WAV/video import and stream parsing
    # Revert: delete this marked method block and the marked global UI/state.
    # =====================================================================
    def load_media_dialog(self):
        """Load WAV audio or a video file and parse its usable streams."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Load WAV / Video Carrier", "",
                "Media Files (*.wav *.mp4 *.mov *.mkv *.webm *.avi *.m4v);;"
                "WAV Audio (*.wav);;Video Files (*.mp4 *.mov *.mkv *.webm *.avi *.m4v);;"
                "All Files (*)"
            )
            if not file_path:
                return
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".wav":
                self._load_wav_path(file_path)
            else:
                self._load_video_path(file_path)
        except Exception as e:
            print(f"[Media] Load failed: {e}")
            QMessageBox.critical(self, "Media Load Error", str(e))

    def _load_wav_path(self, file_path):
        """Shared WAV loader used by both the WAV button and media importer."""
        data = None
        sample_rate = None
        if wavfile is not None:
            sample_rate, data = wavfile.read(file_path)
        else:
            with wave.open(file_path, "rb") as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                width = wf.getsampwidth()
                raw = wf.readframes(wf.getnframes())
                if width == 1:
                    data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                elif width == 2:
                    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                elif width == 4:
                    data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
                else:
                    raise RuntimeError("Unsupported PCM WAV sample width without scipy.")
                if channels > 1:
                    data = data.reshape(-1, channels).mean(axis=1)
        arr = np.asarray(data)
        if arr.ndim > 1:
            arr = arr.mean(axis=1)
        # Normalize integer/float WAVs without changing their relative waveform structure.
        if np.issubdtype(arr.dtype, np.integer):
            info = np.iinfo(arr.dtype)
            denom = float(max(abs(info.min), info.max)) or 1.0
            arr = arr.astype(np.float32) / denom
        else:
            arr = arr.astype(np.float32, copy=False)
        arr = np.nan_to_num(arr.ravel(), nan=0.0, posinf=0.0, neginf=0.0)
        if arr.size == 0:
            raise RuntimeError("The selected WAV contains no audio samples.")
        peak = float(np.max(np.abs(arr)))
        if peak > 1e-9:
            arr /= peak
        self.imported_waveform = arr
        self.imported_sample_rate = int(sample_rate)
        self.imported_wav_path = file_path
        # A new WAV carrier supersedes a previous video carrier, but keeps its audio behavior.
        self.imported_video_path = ""
        self.imported_video_meta = {}
        self._update_imported_media_ui(file_path, sample_rate, arr.size, is_video=False)
        print(f"[WAV Carrier] Loaded {file_path} ({sample_rate} Hz, {arr.size} samples)")

    def _load_video_path(self, file_path):
        """Parse a video file: probe video metadata and extract mono PCM audio as carrier."""
        ffprobe = shutil.which("ffprobe")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required for video import. Install ffmpeg and try again.")

        meta = {}
        if ffprobe:
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", file_path],
                capture_output=True, text=True, check=True
            )
            info = json.loads(probe.stdout or "{}")
            streams = info.get("streams", [])
            v = next((x for x in streams if x.get("codec_type") == "video"), None)
            a = next((x for x in streams if x.get("codec_type") == "audio"), None)
            if v:
                fps_txt = v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"
                try:
                    n, d = fps_txt.split("/", 1)
                    fps = float(n) / max(float(d), 1.0)
                except Exception:
                    fps = 0.0
                meta.update({
                    "width": int(v.get("width") or 0),
                    "height": int(v.get("height") or 0),
                    "fps": fps,
                    "codec": v.get("codec_name", ""),
                    "duration": float(v.get("duration") or info.get("format", {}).get("duration") or 0.0),
                })
            meta["has_audio"] = bool(a)
            meta["audio_codec"] = a.get("codec_name", "") if a else ""

        # Extract float32 mono PCM at the groovebox's native render rate.
        cmd = [
            ffmpeg, "-v", "error", "-i", file_path,
            "-vn", "-ac", "1", "-ar", "44100", "-f", "f32le", "pipe:1"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode(errors="replace")[-1200:] or "ffmpeg could not decode the video audio stream.")
        arr = np.frombuffer(proc.stdout, dtype=np.float32).copy()
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        if arr.size == 0:
            # Video-only files are still valid visual carriers; use a silent audio stream.
            duration = float(meta.get("duration", 0.0))
            arr = np.zeros(max(1, int(duration * 44100.0)), dtype=np.float32)
        peak = float(np.max(np.abs(arr)))
        if peak > 1e-9:
            arr /= peak
        self.imported_waveform = arr
        self.imported_sample_rate = 44100
        self.imported_wav_path = file_path
        self.imported_video_path = file_path
        self.imported_video_meta = meta
        self._update_imported_media_ui(file_path, 44100, arr.size, is_video=True)
        print(f"[Video Carrier] Parsed {file_path}: {meta}; audio samples={arr.size}")

    def _update_imported_media_ui(self, file_path, sample_rate, sample_count, is_video=False):
        name = os.path.basename(file_path)
        tag = "VIDEO" if is_video else "WAV"
        if hasattr(self, "lbl_wav_carrier"):
            self.lbl_wav_carrier.setText(f"{tag}: {name[:22]}")
            self.lbl_wav_carrier.setToolTip(file_path)
        if hasattr(self, "scope_status_label"):
            extra = ""
            if is_video:
                m = self.imported_video_meta
                extra = f" · {m.get('width',0)}×{m.get('height',0)} · {m.get('fps',0.0):.2f} fps"
            self.scope_status_label.setText(
                f"📂 {tag} carrier loaded · {name} · {sample_rate} Hz{extra}"
            )
        if hasattr(self, "visual_oscilloscope"):
            preview = self.imported_waveform[:min(self.imported_waveform.size, max(1, int(sample_rate * 0.5)))]
            if preview.size:
                idx = np.linspace(0, preview.size - 1, 100).astype(int)
                self.visual_oscilloscope.update_waveform(preview[idx])
                if hasattr(self, "video_synth_viewer"):
                    self.video_synth_viewer.update_from_audio(preview[idx])

    def _resample_carrier(self, target_len, target_rate):
        """Return the loaded carrier resampled/looped to the render duration."""
        if self.imported_waveform is None or target_len <= 0:
            return None
        src = np.asarray(self.imported_waveform, dtype=np.float32).ravel()
        if src.size == 0:
            return None
        src_duration = src.size / max(float(self.imported_sample_rate), 1.0)
        target_duration = target_len / max(float(target_rate), 1.0)
        desired = max(2, int(round(target_duration * self.imported_sample_rate)))
        if src_duration < target_duration:
            src = np.tile(src, int(np.ceil(target_duration / max(src_duration, 1e-9))))
        src = src[:desired] if src.size >= desired else np.pad(src, (0, desired - src.size))
        x_old = np.linspace(0.0, 1.0, src.size, endpoint=False)
        x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
        return np.interp(x_new, x_old, src).astype(np.float32)

    # =====================================================================
    # CONVOLVE_FIT_PHASELOCK_EXTENSION — conservative spectral + phase fitting
    # Revert: replace this helper with the prior _spectral_fit_voice body.
    # This block is intentionally isolated so the core oscillator remains unchanged.
    # =====================================================================
    def _spectral_fit_voice(self, voice, target, amount=1.0):
        """Fit broad target spectrum and gently phase-lock the generated voice to it."""
        voice = np.asarray(voice, dtype=np.float32)
        target = np.asarray(target, dtype=np.float32)
        n = min(voice.size, target.size)
        if n < 32:
            return voice
        v = voice[:n]
        t = target[:n]
        nfft = 1 << int(np.ceil(np.log2(n)))
        v_spec = np.fft.rfft(v, nfft)
        t_spec = np.fft.rfft(t, nfft)
        v_mag = np.abs(v_spec)
        t_mag = np.abs(t_spec)
        smooth = max(3, min(63, int(nfft / 2048) * 2 + 3))
        kernel = np.ones(smooth, dtype=np.float32) / float(smooth)
        t_mag = np.convolve(t_mag, kernel, mode="same")
        ratio = np.clip(t_mag / (v_mag + 1e-4), 0.15, 6.0)

        # Phase-lock is deliberately bounded: at 100% fit the target guides phase,
        # while the oscillator's own phase remains the carrier at lower settings.
        fit_amt = float(np.clip(amount, 0.0, 1.0))
        v_unit = v_spec / (np.abs(v_spec) + 1e-7)
        t_unit = t_spec / (np.abs(t_spec) + 1e-7)
        phase_unit = (1.0 - 0.35 * fit_amt) * v_unit + (0.35 * fit_amt) * t_unit
        phase_unit /= (np.abs(phase_unit) + 1e-7)
        fitted_spec = (v_mag * (1.0 + fit_amt * (ratio - 1.0))) * phase_unit
        fitted = np.fft.irfft(fitted_spec, nfft)[:n].astype(np.float32)
        peak = max(float(np.max(np.abs(fitted))), 1e-9)
        original_peak = max(float(np.max(np.abs(v))), 1e-9)
        fitted *= original_peak / peak
        if n < voice.size:
            out = voice.copy(); out[:n] = fitted; return out
        return fitted


    @staticmethod
    def _as_scalar(value, default=0.0):
        """Safe Python float from scalar / length-1 array / nested list (export crash fix)."""
        try:
            if value is None:
                return float(default)
            if isinstance(value, (list, tuple)):
                if not value:
                    return float(default)
                return MathematiciansGrooveboxApp._as_scalar(value[0], default)
            arr = np.asarray(value)
            if arr.size == 0:
                return float(default)
            if arr.size == 1:
                return float(arr.reshape(-1)[0])
            # multi-element: average (pitch stacks, velocity blends)
            return float(np.mean(arr.astype(np.float64)))
        except Exception:
            try:
                return float(value)
            except Exception:
                return float(default)

    def _render_mixdown_buffer(self, max_rows=None, progress="play"):
        """Shared deterministic audio render.

        The DSP keeps the newer build's click-safe, phase-continuous transport and
        explicit-module rules, while restoring the older engine's strongest audio
        ideas: additive harmonic voices, geometric detune/phase separation,
        stable 432 Hz anchoring, and conservative spectral fitting.

        Important invariant:
          Meum is the metric. The *seed* selects the geometric cell.
          Therefore seed A, seed B, and the literal text "Meum" are different
          compositions even when the carrier sequence is identical.
        """
        sample_rate = 44100

        def _prog(value, stage=None):
            if progress == "play":
                self._set_play_progress(value, stage)
            elif progress == "export":
                self._set_export_progress(value, stage)

        bpm = self.spin_bpm.value() if hasattr(self, "spin_bpm") else 120
        rows = self.spin_playlist_length.value() if hasattr(self, "spin_playlist_length") else 32
        if max_rows is not None:
            rows = min(rows, int(max_rows))
        seq_len = self.spin_seq_length.value() if hasattr(self, "spin_seq_length") else 16
        global_playlist_enabled = (
            self.chk_global_playlist.isChecked()
            if hasattr(self, "chk_global_playlist") else True
        )

        if hasattr(self, "sync_playlist_grid_to_memory"):
            try:
                self.sync_playlist_grid_to_memory()
            except Exception:
                pass

        # Keep the newest build's seed-only commissioning, but do it once.
        try:
            seed_txt = (self._seed_text() if hasattr(self, "_seed_text") else "") or ""
            seed_present = bool(seed_txt.strip()) and seed_txt.strip() not in ("0", "0.0")
            any_steps = any(
                any((mem or {}).get("steps") or [])
                for mem in (getattr(self, "instrument_sequencer_memory", {}) or {}).values()
            )
            r_on, p_on = self._engines_both_live() if hasattr(self, "_engines_both_live") else (False, False)
            if seed_present and not any_steps and r_on and p_on and not getattr(self, "_project_imported_user_state", False):
                if hasattr(self, "apply_composition_midpoint"):
                    self.apply_composition_midpoint(live=False)
                elif hasattr(self, "_apply_meum_ideal_hierarchy"):
                    self._apply_meum_ideal_hierarchy()
        except Exception as exc:
            print(f"[Mixdown] auto-commission: {exc}")

        seconds_per_beat = 60.0 / max(float(bpm), 0.001)
        step_duration = seconds_per_beat / 4.0
        row_duration = step_duration * seq_len
        total_duration = max(0.25, rows * row_duration)
        n_samples = int(sample_rate * total_duration)
        t = np.linspace(0.0, total_duration, n_samples, endpoint=False)
        master = np.zeros(n_samples, dtype=np.float32)

        base_eqr = self.slider_eqr.value() / 100.0 if hasattr(self, "slider_eqr") else 0.5
        pkp_decay = self.slider_pkp_decay.value() / 1000.0 if hasattr(self, "slider_pkp_decay") else 0.50
        fractalizer_val = self.slider_fractalizer.value() / 100.0 if hasattr(self, "slider_fractalizer") else 0.33
        pkp_auto = self.chk_pkp_automod.isChecked() if hasattr(self, "chk_pkp_automod") else True
        seed_val = int(self.get_numeric_seed()) if hasattr(self, "get_numeric_seed") else 0
        np.random.seed(seed_val)

        # Seed geometry: several irrational coordinates, not a single Meum mapping.
        seed_u0, seed_u1, seed_u2 = self._seed_geometry("audio")
        seed_phase = 2.0 * np.pi * (
            0.52 * seed_u0 + 0.31 * seed_u1 * PHI_INV + 0.17 * seed_u2 * MEUM_LOG2
        )
        seed_axis = float(np.clip(
            0.37 * seed_u0 + 0.33 * seed_u1 + 0.30 * seed_u2,
            0.0, 1.0
        ))

        imported_carrier = self._resample_carrier(n_samples, sample_rate)
        convolve_fit_enabled = bool(
            hasattr(self, "chk_convolve_fit") and self.chk_convolve_fit.isChecked()
        )
        convolve_fit_amount = (
            float(self.slider_global_convolve.value()) / 100.0
            if hasattr(self, "slider_global_convolve") else 0.0
        )
        if convolve_fit_enabled and imported_carrier is not None:
            master += imported_carrier * 0.35

        _prog(0, "Mixdown")
        self._render_stage = "DSP render"

        # Stable phase state is continuous across rows for each operator.
        phase_offsets = {}

        for row_idx in range(rows):
            start_time = row_idx * row_duration
            end_time = start_time + row_duration
            mask = (t >= start_time) & (t < end_time)
            if not np.any(mask):
                continue
            local_t = t[mask] - start_time
            row_mix = np.zeros_like(local_t, dtype=np.float64)
            velocity_scale = 1.0
            op_indices = []
            primary_op = self.instrument_names_48[0] if self.instrument_names_48 else ""

            if global_playlist_enabled and row_idx < len(getattr(self, "master_playlist_data", [])):
                entry = self.master_playlist_data[row_idx]
                if isinstance(entry, dict):
                    primary_op = entry.get("operator", primary_op)
                    velocity_scale = self._as_scalar(entry.get("velocity", 1.0), 1.0)
                    ops = list(entry.get("operators") or [])
                    if not ops and primary_op:
                        for tok in str(primary_op).split(","):
                            name = tok.split("@")[0].strip()
                            if name:
                                ops.append(name)
                    for op in ops:
                        if op in self.instrument_names_48:
                            op_indices.append(self.instrument_names_48.index(op))

            # Hear every instrument that actually acts. No random companion selection:
            # this was one of the old renderer's least predictable behaviors.
            active_cluster = []
            seen = set()
            for i, name in enumerate(self.instrument_names_48):
                mem = self.instrument_sequencer_memory.get(name)
                acting = bool(mem and any(mem.get("steps", []))) or (i in op_indices)
                if acting and i not in seen:
                    active_cluster.append(i)
                    seen.add(i)

            if not active_cluster:
                try:
                    cur = self.instrument_selector_dropdown.currentText()
                    active_cluster = [self.instrument_names_48.index(cur)] if cur in self.instrument_names_48 else [0]
                except Exception:
                    active_cluster = [0]

            # Keep the mix sparse enough that RMS remains controlled while preserving
            # broad harmonic/geometric separation.
            if len(active_cluster) > 24:
                active_cluster = [
                    active_cluster[int(round(j * (len(active_cluster) - 1) / 23.0))]
                    for j in range(24)
                ]

            for op_idx in active_cluster:
                op_name = self.instrument_names_48[op_idx]
                mem = self.instrument_sequencer_memory.get(
                    op_name,
                    {"steps": [False] * 48, "amplitudes": [1.0] * 48,
                     "pitches": [1.0] * 48, "probabilities": [100] * 48},
                )

                # Legacy-good 432 Hz anchor + Meum ladder, now with a seed-selected
                # geometric cell. This is the key distinction between seeds.
                base_freq = float(self.spin_base_frequency.value()) if hasattr(self, "spin_base_frequency") else 432.0
                if abs(base_freq - 110.0) < 0.5:
                    base_freq = 432.0

                op_phase = (
                    seed_phase * PHI
                    + (op_idx + 1) * 2.0 * np.pi * PHI_INV
                    + row_idx * MEUM_LOG2
                )
                op_field = 0.5 + 0.5 * math.sin(op_phase)
                op_field2 = 0.5 + 0.5 * math.cos(op_phase * SQRT2 + MEUM)
                # Seed-selected pitch cell: ±~0.36 octave, deterministic and bounded.
                seed_ratio = 2.0 ** (
                    (seed_axis - 0.5) * 0.32
                    + (op_field - 0.5) * 0.22
                    + (op_field2 - 0.5) * 0.12
                )
                meum_ratio = float(MEUM_POWERS_36[op_idx % 12])
                base_freq *= meum_ratio * seed_ratio

                while base_freq > 1800.0:
                    base_freq *= 0.5
                base_freq = float(np.clip(base_freq, 55.0, 1800.0))

                # Explicit FM/AM only when a connected/selected module actually says so.
                module_names = [str(op_name)]
                for cable in (getattr(self, "patch_connections", []) or []):
                    if isinstance(cable, dict):
                        if cable.get("source") == op_name:
                            module_names.append(str(cable.get("target", "")))
                        if cable.get("target") == op_name:
                            module_names.append(str(cable.get("source", "")))
                module_text = " ".join(module_names).lower()
                fm_enabled = ("fm" in module_text or "frequency mod" in module_text)
                am_enabled = ("am" in module_text or "amplitude mod" in module_text)

                step_env = np.zeros_like(local_t, dtype=np.float64)
                pitch_track = np.ones_like(local_t, dtype=np.float64)
                wave_track = np.full_like(local_t, 0.5, dtype=np.float64)
                harm_track = np.full_like(local_t, 0.5, dtype=np.float64)

                steps = list(mem.get("steps", []) or [])
                amps = list(mem.get("amplitudes", []) or [])
                pitches = list(mem.get("pitches", []) or [])
                probs = list(mem.get("probabilities", []) or [])

                for s_idx in range(min(int(seq_len), len(steps) if steps else int(seq_len))):
                    if not (steps[s_idx] if s_idx < len(steps) else False):
                        continue
                    s_start = s_idx * step_duration
                    s_end = s_start + step_duration
                    s_mask = (local_t >= s_start) & (local_t < s_end)
                    if not np.any(s_mask):
                        continue

                    s_local = local_t[s_mask] - s_start
                    amp = float(amps[s_idx]) if s_idx < len(amps) else 1.0
                    pr = float(pitches[s_idx]) if s_idx < len(pitches) else 1.0
                    prob = float(probs[s_idx]) / 100.0 if s_idx < len(probs) else 1.0
                    prob = float(np.clip(prob, 0.0, 1.0))

                    # UNISON_RENDER_FIELD: no synthetic ADSR/fade and no hidden
                    # loudness normalizer. Amplitude, pitch, waveform and harmonic
                    # geometry are derived from USER <-> RANDOMIZER <-> PHASE-LOCK
                    # <-> CONTEXT as one deterministic field. This value is held for
                    # the actual musical step, not invented as a time-envelope.
                    try:
                        r_live, p_live = self._engines_both_live()
                    except Exception:
                        r_live, p_live = False, False
                    try:
                        cf = self._contextual_feature_vector(op_name, s_idx, row_idx)
                        ctx_score = float(cf.get("score", 0.5))
                        ctx_phase = float(cf.get("phase", 0.5))
                    except Exception:
                        ctx_score, ctx_phase = 0.5, 0.5
                    su, sv, sw = self._seed_geometry(f"unison|{op_name}|{s_idx}|{row_idx}")
                    try:
                        um = self._user_pattern_mask(mem, int(seq_len), instrument_name=op_name)
                        user_hit = 1.0 if s_idx < len(um) and um[s_idx] else 0.0
                    except Exception:
                        user_hit = 0.0
                    random_field = 0.5 + 0.5 * math.sin(2.0 * math.pi * (su * PHI + sv * MEUM + (s_idx + 1) * MEUM_LOG2) + ctx_phase * math.pi)
                    phase_field = 0.5 + 0.5 * math.cos(2.0 * math.pi * (sv * SQRT2 + sw * PHI_INV + (s_idx + 1) * MEUM_NORM) + ctx_score * math.pi)
                    if r_live and p_live:
                        unison_field = 0.30 * random_field + 0.30 * phase_field + 0.25 * ctx_score + 0.15 * user_hit
                    elif r_live:
                        unison_field = 0.55 * random_field + 0.30 * ctx_score + 0.15 * user_hit
                    elif p_live:
                        unison_field = 0.55 * phase_field + 0.30 * ctx_score + 0.15 * user_hit
                    else:
                        unison_field = 0.65 * ctx_score + 0.20 * su + 0.15 * user_hit
                    unison_field = float(np.clip(unison_field, 0.0, 1.0))
                    gain_field = float(np.clip(0.78 + 0.30 * unison_field, 0.60, 1.0))
                    wave_field = float(np.clip(0.5 * random_field + 0.5 * phase_field, 0.0, 1.0))
                    harm_field = float(np.clip(0.45 * random_field + 0.35 * phase_field + 0.20 * ctx_score, 0.0, 1.0))
                    step_env[s_mask] += amp * prob * gain_field
                    pitch_track[s_mask] = pr * (0.985 + 0.030 * (phase_field - 0.5))
                    wave_track[s_mask] = wave_field
                    harm_track[s_mask] = harm_field

                if float(np.max(step_env)) < 1e-7:
                    continue

                freq = np.clip(base_freq * pitch_track, 40.0, 9000.0)

                # Continuous phase prevents step-boundary discontinuities.
                phase = 2.0 * np.pi * np.cumsum(freq, dtype=np.float64) / float(sample_rate)
                phase -= phase[0] if phase.size else 0.0
                # Golden-angle / Meum phase dispersion lowers coherent summation
                # (therefore lower RMS) without making the result stochastic.
                phase0 = float(np.mod(
                    seed_phase * MEUM
                    + (op_idx + 1) * 2.0 * np.pi * PHI_INV
                    + row_idx * MEUM_LOG2,
                    2.0 * np.pi,
                ))
                phase += phase0
                osc = np.sin(phase)

                # Restore the older engine's useful additive harmonic character, but
                # normalize partial energy so adding harmonics does not simply inflate RMS.
                # Harmonic geometry is directly driven by the shared unison field.
                # No RMS/voice normalization is performed here.
                w = wave_track
                h = harm_track
                partials = (
                    (0.72 + 0.18 * (1.0 - w)) * np.sin(phase)
                    + (0.20 + 0.16 * w) * np.sin(phase * (2.0 + 0.035 * (h - 0.5)) + phase0 * MEUM_NORM)
                    + (0.08 + 0.12 * h) * np.sin(phase * (3.0 + 0.05 * (w - 0.5)) + phase0 * PHI_INV)
                    + (0.025 + 0.075 * (1.0 - h)) * np.sin(phase * (4.0 + 0.06 * (h - 0.5)) + phase0 * SQRT2)
                )
                triangle_like = (2.0 / np.pi) * np.arcsin(np.sin(phase * (1.0 + 0.01 * (w - 0.5))))
                saw_like = 2.0 * ((phase / (2.0 * np.pi)) % 1.0) - 1.0
                osc = (1.0 - 0.22 * w - 0.18 * h) * partials + 0.12 * w * triangle_like + 0.08 * h * saw_like

                if fm_enabled:
                    mod_freq = freq * MEUM_CONSTANT
                    fm_mod = np.sin(2.0 * np.pi * mod_freq * local_t + phase0)
                    fm_index = np.clip(
                        base_eqr * MEUM_CONSTANT * max(fractalizer_val, 0.15),
                        0.05, 3.5
                    )
                    osc = np.sin(phase + fm_mod * fm_index)

                if am_enabled:
                    am_depth = float(np.clip(
                        0.15 + 0.25 * base_eqr * MEUM_NORM, 0.08, 0.45
                    ))
                    am_rate = np.maximum(freq * MEUM_NORM * 0.5, 0.5)
                    am_env = (
                        1.0 - am_depth
                        + am_depth * (
                            0.5 + 0.5 * np.sin(
                                2.0 * np.pi * am_rate * local_t
                                + op_idx * MEUM
                                + seed_phase
                            )
                        )
                    )
                    osc *= am_env

                voice = osc * np.maximum(step_env, 0.0) * float(velocity_scale)

                # Optional old-build spectral/phase fitting remains available, but only
                # when explicitly enabled by the user.
                if convolve_fit_enabled:
                    try:
                        is_user_voice = self._instrument_has_net_effect(op_name, seq_len)
                    except Exception:
                        is_user_voice = op_idx in op_indices
                    if not is_user_voice:
                        fit_target = None
                        if imported_carrier is not None:
                            global_start = int(np.searchsorted(t, start_time))
                            global_end = min(global_start + local_t.size, imported_carrier.size)
                            if global_end > global_start:
                                fit_target = imported_carrier[global_start:global_end]
                        if fit_target is None or fit_target.size < 32:
                            fit_target = row_mix.copy() if np.max(np.abs(row_mix)) > 1e-7 else osc
                        voice = self._spectral_fit_voice(
                            voice.astype(np.float32),
                            fit_target.astype(np.float32),
                            max(0.15, convolve_fit_amount),
                        ).astype(np.float64)

                # REAL STACK: preserve actual voice amplitudes; no synthetic cluster RMS normalization.
                row_mix += voice

            # Explicit PKP layer; no hidden transient beyond its macro.
            try:
                selected = self.instrument_selector_dropdown.currentText()
                smem = self.instrument_sequencer_memory.get(selected, {})
                ssteps = smem.get("steps", []) or []
                global_pkp = np.zeros_like(local_t, dtype=np.float64)
                gbase = float(self.spin_base_frequency.value()) if hasattr(self, "spin_base_frequency") else 432.0
                if abs(gbase - 110.0) < 0.5:
                    gbase = 432.0
                for ss in range(min(int(seq_len), len(ssteps))):
                    if ssteps[ss]:
                        ss_start = ss * step_duration
                        ss_end = ss_start + step_duration
                        mm = (local_t >= ss_start) & (local_t < ss_end)
                        if np.any(mm):
                            sl = local_t[mm] - ss_start
                            # PKP is a real user-programmed layer: no hidden decay envelope.
                            pkp_phase = 2.0 * np.pi * gbase * sl + seed_phase
                            global_pkp[mm] += np.sin(pkp_phase)
                row_mix += global_pkp * (0.35 * float(np.clip(pkp_decay, 0.0, 1.0)))
            except Exception:
                pass

            master[mask] += row_mix.astype(np.float32)
            _prog(min(85, int(((row_idx + 1) / max(rows, 1)) * 85)), "Mixdown")

        # Keep the older build's geometric global convolution, but make its kernel
        # explicitly seed-specific so it cannot collapse every seed into one timbre.
        self._render_stage = "Global convolution"
        try:
            conv_amt = (
                float(self.spin_global_convolve.value()) / 100.0
                if hasattr(self, "spin_global_convolve") else 0.0
            )
            if conv_amt > 0.0 and len(master) > 8:
                klen = min(2048, max(32, len(master) // 200))
                idx = np.arange(klen, dtype=np.float64)
                gf = float(self.spin_base_frequency.value()) if hasattr(self, "spin_base_frequency") else 432.0
                kphase = seed_phase + idx * (2.0 * np.pi * MEUM_LOG2 / max(klen, 1))
                kernel = (
                    np.sin(2.0 * np.pi * (gf / sample_rate) * idx + kphase)
                    + 0.5 * np.sin(
                        2.0 * np.pi * (gf * MEUM_CONSTANT / sample_rate) * idx
                        + kphase * PHI
                    )
                ).astype(np.float32)
                if imported_carrier is not None:
                    # Blend the carrier into the kernel rather than replacing the
                    # seed-specific mathematical kernel.
                    carrier_k = imported_carrier[:klen].copy()
                    if carrier_k.size < klen:
                        carrier_k = np.pad(carrier_k, (0, klen - carrier_k.size), mode="wrap")
                    kernel = 0.70 * kernel + 0.30 * carrier_k

                kn = np.linalg.norm(kernel)
                if kn > 1e-9:
                    kernel /= kn
                    nfft = 1 << int(np.ceil(np.log2(len(master) + len(kernel) - 1)))
                    spec = np.fft.rfft(master, nfft) * np.fft.rfft(kernel, nfft)
                    conv = np.fft.irfft(spec, nfft)[:len(master)].astype(np.float32)
                    # Keep convolution's real contribution; do not rescale it to the master.
                    master = (1.0 - conv_amt) * master + conv_amt * conv
        except Exception as exc:
            print(f"[Global Convolve] skipped: {exc}")

        _prog(max(getattr(self, "_play_progress", 0), 94), "Mixdown")
        self._render_stage = "Domain modulation"

        if hasattr(self, "domain_eq_engine") and self.domain_eq_engine.domains:
            try:
                engines_active = (
                    bool(self._engines_both_live()[0] or self._engines_both_live()[1])
                    if hasattr(self, "_engines_both_live") else False
                )
                domains = [
                    d for d in self.domain_eq_engine.domains
                    if d.get("user_defined", True) or engines_active
                ]
                if domains:
                    old_domains = self.domain_eq_engine.domains
                    self.domain_eq_engine.domains = domains
                    self.domain_eq_engine.set_seed(self.get_numeric_seed())
                    t_norm = np.linspace(0.0, 1.0, len(master))
                    domain_mod = self.domain_eq_engine.evaluate_series(
                        t_norm, x=0.0, y=0.0, z=0.0
                    )
                    master = master * (1.0 + 0.30 * domain_mod.astype(np.float32))
                    self.domain_eq_engine.domains = old_domains
            except Exception as exc:
                print(f"[DomainEQ] render modulation skipped: {exc}")

        _prog(98, "Mixdown")
        self._render_stage = "Finalizing"
        # FINAL ACTUAL EXTREMA: the only output scaling is based on the real stacked waveform.
        if master.size:
            lo = float(np.min(master))
            hi = float(np.max(master))
            extrema = max(abs(lo), abs(hi))
            if extrema > 1e-12:
                master = (master / extrema) * 0.98
        master = np.clip(master, -0.98, 0.98).astype(np.float32)
        _prog(100, "Mixdown")
        self._render_stage = "Complete"
        return master, sample_rate



    def _apply_meum_ideal_hierarchy(self, rng=None):
        """Geometric Meum hierarchy over synth, playlist, domain, modular, scripts.

        Levels (self-similar powers of M):
          L0  seed          — root
          L1  domain weights — MEUM_POWERS longitudinal
          L2  playlist density / velocity — potential Φ geometry
          L3  sequencer steps — standing-wave harmonics
          L4  modular patches — feedforward along M-step indices
          L5  scripts         — evaluate_wave from Meum potential × standing wave

        Only fills empty / engine-owned slots; preserves user @u: and touched steps.
        """
        seed = int(self.get_numeric_seed()) if hasattr(self, 'get_numeric_seed') else 1
        if rng is None:
            rng = np.random.default_rng(seed)
        names = list(getattr(self, 'instrument_names_48', []) or [])
        n = max(len(names), 1)
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16

        # L1 — Domain equation weights (longitudinal Meum)
        try:
            eng = getattr(self, 'domain_eq_engine', None)
            if eng is not None and hasattr(eng, 'domains'):
                for di, dom in enumerate(eng.domains):
                    if not isinstance(dom, dict):
                        continue
                    # only soft-adjust weight if unmarked user
                    if dom.get('user_locked'):
                        continue
                    w = float(MEUM_POWERS_36[di % 36] * MEUM_NORM + MEUM_NORM)
                    dom['weight'] = float(np.clip(w, 0.05, 2.5))
                    dom['seed_weight'] = float(np.clip(MEUM_NORM * (1.0 + 0.5 * np.sin(di * MEUM)), 0.05, 1.0))
        except Exception as exc:
            print(f"[Meum hierarchy] domain: {exc}")

        # L2 — Playlist velocity / coverage from Φ = 1/r style falloff along row
        try:
            rows = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 32
            pl = getattr(self, 'master_playlist_data', None)
            if pl is not None:
                while len(pl) < rows:
                    pl.append({})
                for r in range(rows):
                    e = pl[r] if isinstance(pl[r], dict) else {}
                    # skip rows that only have user instances
                    if e.get('user_instances') and not e.get('generated_source'):
                        continue
                    # geometric falloff along playlist axis
                    x = (r + 1) / max(rows, 1)
                    phi = 1.0 / max(np.sqrt(x * x + MEUM_NORM * MEUM_NORM), 1e-6)
                    phi = float(np.clip(phi * MEUM_NORM * 2.0, 0.15, 1.35))
                    if not e.get('velocity_user_locked'):
                        e['velocity'] = phi
                    if not e.get('operators') and names:
                        # sparse ideal operators by Meum step on the ring
                        seed_phase = (seed % 1000003) / 1000003.0
                        k = int(((r + 1) * MEUM + seed_phase * 17.0) * 7) % n
                        picks = [names[k]]
                        k2 = (k + int(round(MEUM * 5))) % n
                        if k2 != k:
                            picks.append(names[k2])
                        e['operators'] = picks
                        e['operator'] = ','.join(picks)
                        e['generated_source'] = e.get('generated_source') or 'meum_hierarchy'
                    pl[r] = e
        except Exception as exc:
            print(f"[Meum hierarchy] playlist: {exc}")

        # L3 — Sequencer: standing-wave step masks for untouched pads
        try:
            for i, name in enumerate(names):
                mem = self.instrument_sequencer_memory.setdefault(name, {
                    "steps": [False] * count,
                    "amplitudes": [1.0] * count,
                    "pitches": [1.0] * count,
                    "probabilities": [100] * count,
                    "touched": set(),
                })
                self._ensure_seq_mem_length(mem, count)
                touched = mem.get('touched') or set()
                # harmonic indices from Meum standing wave n,m
                n_h = 1 + (i % 5)
                for s in range(count):
                    if s in touched:
                        continue
                    # Ψ = sin(n π s/L) threshold
                    seed_phase = 2.0 * np.pi * ((seed % 1000003) / 1000003.0)
                    n_h_seed = 1 + ((i + seed) % 7)
                    m_h_seed = 1 + ((i * 3 + seed // 11) % 5)
                    psi = np.sin(n_h_seed * np.pi * (s + 0.5) / max(count, 1) + seed_phase)
                    psi *= np.sin(m_h_seed * np.pi * ((s + i + (seed % count if count else 0)) % count) / max(count, 1) + seed_phase * MEUM_NORM)
                    threshold = 0.48 + 0.18 * np.sin(seed_phase + i * MEUM_INV)
                    on = bool(abs(psi) > threshold)
                    # only write empty (False) slots — additive
                    if not mem['steps'][s] and on:
                        mem['steps'][s] = True
                        mem['amplitudes'][s] = float(np.clip(abs(psi) * MEUM, 0.25, 1.2))
                        mem['pitches'][s] = float(np.clip((MEUM ** ((s % 7) - 3)) * (2.0 ** ((((seed + i * 17 + s * 31) % 1009) / 1008.0 - 0.5) * 0.42)) * 0.15 + 1.0, 0.5, 2.0))
        except Exception as exc:
            print(f"[Meum hierarchy] sequencer: {exc}")

        # L4 — Patch routing is generated only by an explicit Randomizer / Phase-Lock
        # context pass.  The hierarchy itself never silently inserts wave-effect modules.

        # L5 — Scripts: Meum potential × standing wave template when empty
        try:
            if not hasattr(self, 'instrument_scripts') or self.instrument_scripts is None:
                self.instrument_scripts = {}
            for i, name in enumerate(names):
                cur = (self.instrument_scripts.get(name) or "").strip()
                # treat default-ish / empty as fillable
                if cur and "Meum hierarchy" not in cur and "operator rules" not in cur and len(cur) > 80:
                    continue
                seed_phase = 2.0 * np.pi * ((seed % 1000003) / 1000003.0)
                n_h = 1 + ((i + seed) % 7)
                m_h = 1 + ((i * 3 + seed // 11) % 5)
                harmonic = 1 + ((seed + i * 13) % 9)
                self.instrument_scripts[name] = (
                    f"# Meum hierarchy L5 — seed-locked potential × standing wave\n"
                    f"def evaluate_wave(x, y, z, t=0.0, seed=0.0):\n"
                    f"    r = (x*x + y*y + z*z) ** 0.5 + 1e-9\n"
                    f"    phi = 1.0 / r\n"
                    f"    phase = {seed_phase:.12f} + seed * {MEUM_NORM:.12f}\n"
                    f"    psi = np.sin({n_h}*np.pi*np.clip(x,-1,1) + phase) * np.sin({m_h}*np.pi*np.clip(y,-1,1) + phase*{MEUM_NORM:.8f})\n"
                    f"    return float(np.clip(phi * psi * np.sin(t * {MEUM:.8f} * {harmonic} + phase), -1, 1))\n"
                )
        except Exception as exc:
            print(f"[Meum hierarchy] scripts: {exc}")

        # Synth macros: soft Meum defaults when no user param state
        try:
            if not hasattr(self, 'instrument_param_state'):
                self.instrument_param_state = {}
            for i, name in enumerate(names):
                st = self.instrument_param_state.setdefault(name, {})
                if not st.get('user_locked'):
                    st.setdefault('eqr', float(np.clip(MEUM_NORM * (1 + (i % 5) * 0.1), 0.05, 1.0)))
                    st.setdefault('fractalizer', float(np.clip(MEUM_INV * (0.8 + 0.05 * (i % 7)), 0.05, 1.0)))
        except Exception as exc:
            print(f"[Meum hierarchy] synth: {exc}")

        # Refresh visualizers from playlist-simultaneous Meum wave
        try:
            self._refresh_visualizers_meum_playlist()
        except Exception:
            pass
        return True

    def _meum_wave_from_playlist(self, n_samples=512, sample_rate=44100):
        """Assemble a visualizer wave from the *final* commission path.

        Same explicit-module / Meum spatial structure as ``_render_mixdown_buffer``, but
        coarse (few samples) so the 2.5D graph tracks the finished audio form
        rather than pre-mix engine fragments. Uses playlist operators + sequencer
        steps when present; otherwise a deterministic Meum standing field.
        """
        n_samples = max(64, int(n_samples))
        t = np.linspace(0.0, n_samples / float(sample_rate), n_samples, endpoint=False)
        master = np.zeros(n_samples, dtype=np.float64)
        seed = int(self.get_numeric_seed()) if hasattr(self, 'get_numeric_seed') else 1
        rng = np.random.default_rng(seed)
        base_eqr = (self.slider_eqr.value() / 100.0) if hasattr(self, 'slider_eqr') else 0.5
        frac = (self.slider_fractalizer.value() / 100.0) if hasattr(self, 'slider_fractalizer') else 0.85
        gbase = float(self.spin_base_frequency.value()) if hasattr(self, 'spin_base_frequency') else 432.0
        names = list(getattr(self, 'instrument_names_48', []) or [])
        # Prefer playlist-commissioned operators (final arrangement)
        ops = []
        pl = getattr(self, 'master_playlist_data', None) or []
        for entry in pl:
            if not isinstance(entry, dict):
                continue
            for key in ('operators', 'operator'):
                val = entry.get(key)
                if isinstance(val, list):
                    ops.extend([o for o in val if o in names])
                elif isinstance(val, str) and val:
                    for tok in val.split(','):
                        name = tok.split('@')[0].strip()
                        if name in names:
                            ops.append(name)
        if not ops:
            # fall back to instruments with active steps (post-engine commission)
            for name in names:
                mem = (getattr(self, 'instrument_sequencer_memory', {}) or {}).get(name) or {}
                if any(mem.get('steps') or []):
                    ops.append(name)
        if not ops:
            ops = names[:8] if names else []
        # Unique, stable order
        seen = set()
        ordered = []
        for o in ops:
            if o not in seen:
                seen.add(o)
                ordered.append(o)
        ordered = ordered[:16]
        for i, op_name in enumerate(ordered):
            try:
                op_idx = names.index(op_name)
            except ValueError:
                op_idx = i
            mem = (getattr(self, 'instrument_sequencer_memory', {}) or {}).get(op_name) or {}
            steps = mem.get('steps') or []
            amps = mem.get('amplitudes') or [1.0]
            pitches = mem.get('pitches') or [1.0]
            # duty from step density (Meum-weighted)
            density = (sum(1 for s in steps if s) / max(len(steps), 1)) if steps else (0.35 + 0.1 * (i % 3))
            density = float(np.clip(density * MEUM, 0.08, 0.95))
            pr = float(pitches[0]) if pitches else 1.0
            amp = float(amps[0]) if amps else 1.0
            freq = float(np.clip(gbase * (MEUM ** (op_idx % 12)) * pr, 40.0, 4800.0))
            # Preview follows the same explicit-module rule as audio render: no
            # automatic AM/FM or drifting EQR modulation is inserted into a plain
            # seed composition.  The seed/Meum geometry controls phase and gating.
            module_names = [str(op_name)]
            for _c in (getattr(self, "patch_connections", []) or []):
                if isinstance(_c, dict):
                    if _c.get("source") == op_name:
                        module_names.append(str(_c.get("target", "")))
                    if _c.get("target") == op_name:
                        module_names.append(str(_c.get("source", "")))
            module_text = " ".join(module_names).lower()
            fm_enabled = ("fm" in module_text or "frequency mod" in module_text)
            am_enabled = ("am" in module_text or "amplitude mod" in module_text)
            phase = 2.0 * np.pi * freq * t
            carrier = np.sin(phase)
            if fm_enabled:
                fm_mod = np.sin(2.0 * np.pi * (freq * MEUM_CONSTANT) * t)
                fm_index = np.clip(base_eqr * MEUM_CONSTANT * max(frac, 0.15), 0.05, 3.5)
                carrier = np.sin(phase + fm_mod * fm_index)
            am_env = 1.0
            if am_enabled:
                am_depth = float(np.clip(0.15 + 0.25 * base_eqr * MEUM_NORM, 0.08, 0.45))
                am_rate = max(freq * MEUM_NORM * 0.5, 0.5)
                am_env = 1.0 - am_depth + am_depth * (0.5 + 0.5 * np.sin(2.0 * np.pi * am_rate * t + op_idx * MEUM))
            phase_g = (t * (2.0 + density * 6.0 * MEUM) + seed * 1e-9 * op_idx) % 1.0
            gate = (phase_g < density).astype(np.float64) * (0.5 + 0.5 * amp)
            master += (carrier * am_env * gate) * (0.08 + 0.04 * (i % 3))
        # Visual-only preview: preserve actual extrema; do not normalize the preview mix.
        return master.astype(np.float32)

    def _refresh_visualizers_meum_playlist(self):
        """Idle/pre-play: same explicit-module Meum structure as final mix, from playlist."""
        try:
            wave = self._meum_wave_from_playlist(n_samples=1024)
            self._push_visualizers_from_wave(wave)
        except Exception as exc:
            print(f"[Viz] meum playlist preview: {exc}")

    def _push_visualizers_from_wave(self, wave):

        """Feed scope + 2.5D from one wave buffer (final form only)."""
        if wave is None:
            return
        arr = np.asarray(wave, dtype=np.float32).ravel()
        if arr.size == 0:
            return
        if arr.size >= 100:
            idx = np.linspace(0, arr.size - 1, 100).astype(int)
            chunk = arr[idx]
        else:
            chunk = np.zeros(100, dtype=np.float32)
            chunk[:arr.size] = arr
        if isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope):
            self.visual_oscilloscope.update_waveform(chunk)
        if hasattr(self, 'video_synth_viewer'):
            self.video_synth_viewer.update_from_audio(arr)

    def _audio_callback(self, outdata, frames, time_info, status):
        """sounddevice stream callback — pulls from play_buffer under lock."""
        if status:
            pass  # underrun etc. ignored for now
        with self.play_lock:
            if self.play_buffer is None or not self.is_playing:
                outdata.fill(0)
                return
            remaining = len(self.play_buffer) - self.play_cursor
            n = min(frames, remaining)
            if n > 0:
                chunk = self.play_buffer[self.play_cursor:self.play_cursor + n] * self.master_volume
                outdata[:n, 0] = chunk
                # stash a short window for the UI scope
                if n >= 100:
                    self._last_scope_chunk = chunk[::max(1, n // 100)][:100].copy()
                else:
                    pad = np.zeros(100, dtype=np.float32)
                    pad[:n] = chunk
                    self._last_scope_chunk = pad
                self.play_cursor += n
            if n < frames:
                outdata[n:, 0] = 0
            if self.play_cursor >= len(self.play_buffer):
                self.is_playing = False
                self._play_finished_flag = True

    def _update_scope_from_playhead(self):
        """UI timer: graph always follows the *final* commissioned play_buffer."""
        if getattr(self, "_play_finished_flag", False):
            self._play_finished_flag = False
            try:
                if self.audio_stream is not None:
                    self.audio_stream.stop(); self.audio_stream.close()
            except Exception:
                pass
            self.audio_stream = None
            if hasattr(self, "btn_play"):
                self.btn_play.setText("▶ PLAY Audiovisual Track")
                self.btn_play.setStyleSheet("")
            if hasattr(self, "scope_status_label"):
                self.scope_status_label.setText("📊 Audiovisual Track  |  Finished")
            if hasattr(self, "_scope_update_timer"):
                self._scope_update_timer.stop()
            return
        if not self.is_playing:
            self.stop_playback()
            return
        # Prefer a window of the final mix at the playhead (not pre-mix engine parts)
        wave = None
        buf = getattr(self, 'play_buffer', None)
        if buf is not None and len(buf) > 0:
            cur = int(getattr(self, 'play_cursor', 0))
            win = min(2048, len(buf))
            a = max(0, min(cur, len(buf) - win))
            wave = buf[a:a + win] * float(getattr(self, 'master_volume', 1.0))
        elif getattr(self, '_last_scope_chunk', None) is not None:
            wave = self._last_scope_chunk
        if wave is not None:
            self._push_visualizers_from_wave(wave)
        elif not self.is_playing:
            # Simultaneous Meum playlist path — same structure as final mix
            try:
                self._refresh_visualizers_meum_playlist()
            except Exception:
                pass
        if buf is not None and len(buf) > 0:
            pct = int(100 * self.play_cursor / len(buf))
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText(
                    f"📊 2.5D Video Synth  |  LIVE  {pct}%  ·  Vol {int(self.master_volume*100)}%"
                )

    def _start_async_play_render(self):
        """Start the expensive DSP mixdown off the Qt GUI thread."""
        if self._render_thread is not None and self._render_thread.is_alive():
            return

        # Keep the existing playlist synchronization on the GUI thread; the
        # renderer then works from the synchronized application state.
        try:
            self.sync_playlist_grid_to_memory()
        except Exception as e:
            print(f"[Audio] Playlist sync before render skipped: {e}")

        self._render_generation += 1
        generation = self._render_generation
        self._render_result_queue = queue.Queue()
        self._render_thread = threading.Thread(
            target=self._render_mixdown_worker,
            args=(generation,),
            name="groovebox-dsp-render",
            daemon=True,
        )
        self._show_play_progress()
        self._render_poll_timer.start()
        self._render_thread.start()

    def _render_mixdown_worker(self, generation):
        """Worker-side DSP render. Never touches Qt widgets directly."""
        try:
            with self._mixdown_lock:
                buf, sr = self._render_mixdown_buffer(progress="play")
            self._render_result_queue.put((generation, buf, sr, None))
        except Exception as e:
            self._render_result_queue.put((generation, None, None, e))

    def _poll_async_render_result(self):
        """GUI-thread handoff from the DSP worker into sounddevice playback."""
        bar = getattr(self, 'play_progress_bar', getattr(self, 'render_progress_bar', None))
        if bar is not None:
            pct = int(getattr(self, '_play_progress', getattr(self, '_render_progress', 0)))
            bar.setValue(pct)
            if getattr(self, '_render_stage', '') and not getattr(self, 'is_playing', False):
                self.scope_status_label.setText(f"📊 {self._render_stage}… {pct}%")
        try:
            generation, buf, sr, error = self._render_result_queue.get_nowait()
        except queue.Empty:
            return

        self._render_poll_timer.stop()
        self._render_thread = None

        # A Stop pressed while rendering invalidates the completed worker.
        if generation != self._render_generation or not self.is_paused and getattr(self, '_render_cancelled', False):
            return
        self._render_cancelled = False

        if error is not None:
            self.is_playing = False
            self.is_paused = False
            print(f"[Audio] Background render failed: {error}")
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText(f"📊 Render error: {error}")
            QMessageBox.critical(self, "Playback Render Error", str(error))
            return

        try:
            with self.play_lock:
                self.play_buffer = np.asarray(buf, dtype=np.float32)
                # Visualizers lock to final mix immediately (not intermediate engine waves)
                try:
                    self._push_visualizers_from_wave(self.play_buffer[:min(4096, len(self.play_buffer))])
                except Exception:
                    pass
                self.play_sample_rate = int(sr)
                self.play_cursor = 0
                self.is_playing = True
                self.is_paused = False
            if HAS_SOUNDDEVICE:
                if self.audio_stream is not None:
                    try:
                        self.audio_stream.stop(); self.audio_stream.close()
                    except Exception:
                        pass
                self.audio_stream = sd.OutputStream(
                    samplerate=sr, channels=1, dtype='float32',
                    callback=self._audio_callback, blocksize=1024, latency='low'
                )
                self.audio_stream.start()
            self.btn_play.setText("⏸ PAUSE Audiovisual Track")
            self.btn_play.setStyleSheet("background-color: #00aa55; color: white; font-weight: bold;")
            self._scope_update_timer.start()
            if hasattr(self, 'scope_status_label'):
                self._hide_play_progress(); self.scope_status_label.setText("📊 Audiovisual Track  |  LIVE")
            if hasattr(self, 'play_progress_bar'):
                self.play_progress_bar.setValue(100)
            self._play_finished_flag = False
        except Exception as e:
            self.is_playing = False
            self.is_paused = False
            print(f"[Audio] Playback start failed after render: {e}")
            QMessageBox.critical(self, "Playback Error", str(e))

    def toggle_playback(self):
        """Unified PLAY/PAUSE/RESUME transport over the rendered audiovisual data stream."""
        # Playing -> pause without destroying the rendered buffer/cursor.
        if self.is_playing:
            self.is_playing = False
            self.is_paused = True
            if getattr(self, 'audio_stream', None) is not None:
                try:
                    self.audio_stream.stop()
                    self.audio_stream.close()
                except Exception:
                    pass
                self.audio_stream = None
            if hasattr(self, '_scope_update_timer'):
                self._scope_update_timer.stop()
            self.btn_play.setText("▶ RESUME Audiovisual Track")
            self.btn_play.setStyleSheet("background-color: #b8860b; color: white; font-weight: bold;")
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText("📊 Audiovisual Track  |  PAUSED")
            return

        # Paused -> resume exactly where the audio cursor stopped.
        if self.is_paused and self.play_buffer is not None and self.play_cursor < len(self.play_buffer):
            try:
                self.is_playing = True
                self.is_paused = False
                if HAS_SOUNDDEVICE:
                    self.audio_stream = sd.OutputStream(
                        samplerate=self.play_sample_rate, channels=1, dtype='float32',
                        callback=self._audio_callback, blocksize=1024, latency='low'
                    )
                    self.audio_stream.start()
                self.btn_play.setText("⏸ PAUSE Audiovisual Track")
                self.btn_play.setStyleSheet("background-color: #00aa55; color: white; font-weight: bold;")
                self._scope_update_timer.start()
                return
            except Exception as e:
                self.is_playing = False
                self.is_paused = False
                print(f"[Audio] Resume failed: {e}")

        if not HAS_SOUNDDEVICE:
            QMessageBox.warning(self, "Audio Engine", "sounddevice is not available. Install with: pip install sounddevice")
            return

        if self._render_thread is not None and self._render_thread.is_alive():
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText("📊 Rendering Audiovisual Track…")
            return

        self._render_cancelled = False
        if hasattr(self, 'scope_status_label'):
            self.scope_status_label.setText("📊 Rendering Audiovisual Track in background…")
        self.btn_play.setText("⏳ RENDERING…")
        self.btn_play.setStyleSheet("background-color: #6b5b00; color: white; font-weight: bold;")
        self._start_async_play_render()

    def stop_playback(self):
        """Hard stop: reset the audiovisual transport to the beginning."""
        self._render_generation += 1
        self._render_cancelled = True
        if hasattr(self, '_render_poll_timer'):
            self._render_poll_timer.stop()
        was_active = self.is_playing or self.is_paused
        self.is_playing = False
        self.is_paused = False
        if hasattr(self, '_scope_update_timer') and self._scope_update_timer.isActive():
            self._scope_update_timer.stop()
        if getattr(self, 'audio_stream', None) is not None:
            try:
                self.audio_stream.stop(); self.audio_stream.close()
            except Exception:
                pass
            self.audio_stream = None
        with getattr(self, 'play_lock', threading.Lock()):
            self.play_cursor = 0
        if hasattr(self, 'btn_play'):
            self.btn_play.setText("▶ PLAY Audiovisual Track")
            self.btn_play.setStyleSheet("")
        if hasattr(self, 'scope_status_label'):
            self._hide_play_progress(); self.scope_status_label.setText("📊 Audiovisual Track  |  Stopped")
        if isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope):
            self.visual_oscilloscope.update_waveform(np.zeros(100))
        if hasattr(self, 'video_synth_viewer'):
            self.video_synth_viewer.update_from_audio(np.zeros(100, dtype=np.float32))
        if was_active:
            print("[Audio] Audiovisual playback stopped.")

    def export_mixdown_dialog(self):
        """Queue WAV rendering/writing off the Qt GUI thread."""
        try:
            if self._export_thread is not None and self._export_thread.is_alive():
                if hasattr(self, 'scope_status_label'):
                    self.scope_status_label.setText("📊 Export already running…")
                return
            default_filename = f"groovebox_mixdown_{self.export_counter:03d}.wav"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Mixdown Audio", default_filename, "WAV Audio Files (*.wav)"
            )
            if not file_path:
                return
            self._export_progress = 0
            self._export_stage = "Rendering WAV"
            if hasattr(self, "export_progress_bar"):
                self.export_progress_bar.setValue(0)
            if hasattr(self, "scope_status_label"):
                self.scope_status_label.setText("📤 Rendering WAV in background… 0%")
            self._export_result_queue = queue.Queue()
            self._export_thread = threading.Thread(
                target=self._export_wav_worker, args=(file_path,),
                name="groovebox-wav-export", daemon=True
            )
            self._show_export_progress()
            self._export_poll_timer.start()
            self._export_thread.start()
        except Exception as e:
            print(f"[System] Export setup error: {e}")
            QMessageBox.critical(self, "Export Error", str(e))

    def _show_play_progress(self):
        bar = getattr(self, "play_progress_bar", None)
        if bar is not None:
            bar.setVisible(True)
        lbl = getattr(self, "lbl_play_progress", None)
        if lbl is not None:
            lbl.setVisible(True)

    def _hide_play_progress(self):
        bar = getattr(self, "play_progress_bar", None)
        if bar is not None:
            bar.setVisible(False)
            bar.setValue(0)
        lbl = getattr(self, "lbl_play_progress", None)
        if lbl is not None:
            lbl.setVisible(False)

    def _show_export_progress(self):
        bar = getattr(self, "export_progress_bar", None)
        if bar is not None:
            bar.setVisible(True)
        lbl = getattr(self, "lbl_export_progress", None)
        if lbl is not None:
            lbl.setVisible(True)

    def _hide_export_progress(self):
        bar = getattr(self, "export_progress_bar", None)
        if bar is not None:
            bar.setVisible(False)
            bar.setValue(0)
        lbl = getattr(self, "lbl_export_progress", None)
        if lbl is not None:
            lbl.setVisible(False)

    def _set_play_progress(self, value, stage=None):

        """Drive the Play bar only — never touches Export progress."""
        self._play_progress = int(max(0, min(100, value)))
        self._render_progress = self._play_progress  # legacy alias for play path
        if stage is not None:
            self._render_stage = stage

    def _set_export_progress(self, value, stage=None):
        """Drive the Export bar only — never touches Play progress."""
        self._export_progress = int(max(0, min(100, value)))
        if stage is not None:
            self._export_stage = stage
        bar = getattr(self, "export_progress_bar", None)
        # Worker threads must not touch Qt; poller updates the bar.

    def _export_wav_worker(self, file_path):

        try:
            with getattr(self, "_mixdown_lock", threading.Lock()):
                master, sample_rate = self._render_mixdown_buffer(progress="export")
            self._set_export_progress(98, "Writing WAV")
            master = np.asarray(master, dtype=np.float32).ravel()
            # _render_mixdown_buffer already scales to the actual stacked extrema.
            # Export performs only the unavoidable PCM safety clip.
            pcm = (np.clip(master, -1.0, 1.0) * 32767.0).astype(np.int16)
            if wavfile is not None:
                wavfile.write(file_path, sample_rate, pcm)
            else:
                with wave.open(file_path, 'wb') as wf:
                    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate)
                    wf.writeframes(pcm.tobytes())
            self._export_result_queue.put(("wav", file_path, None, master, sample_rate))
        except Exception as e:
            self._export_result_queue.put(("wav", file_path, e, None, None))

    def _poll_export_result(self):
        bar = getattr(self, 'export_progress_bar', None)
        pct = int(getattr(self, '_export_progress', 0))
        if bar is not None:
            bar.setValue(pct)
        stage = getattr(self, '_export_stage', getattr(self, '_render_stage', 'Export'))
        if hasattr(self, 'scope_status_label') and self._export_thread is not None and self._export_thread.is_alive():
            self.scope_status_label.setText(f"📤 {stage}… {pct}%")
        try:
            kind, path, error, master, sr = self._export_result_queue.get_nowait()
        except queue.Empty:
            return
        self._export_poll_timer.stop()
        self._export_thread = None
        if error is not None:
            self.scope_status_label.setText(f"📊 Export error: {error}")
            QMessageBox.critical(self, "Export Error", str(error))
            return
        if kind == "wav":
            getattr(self, "export_progress_bar", self.render_progress_bar).setValue(100)
            self._export_progress = 100
            if isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope) and master is not None:
                prev = master[: min(len(master), int(sr) // 2)]
                if len(prev):
                    idx = np.linspace(0, len(prev) - 1, min(100, len(prev))).astype(int)
                    self.visual_oscilloscope.update_waveform(prev[idx])
            self.export_counter += 1
            self._hide_export_progress(); self.scope_status_label.setText(f"📊 Export complete → {os.path.basename(path)}")
            print(f"[System] Success: exported → {path}")

    # =====================================================================
    # VIDEO_EXPORT_FEATURE — 2.5D render + audio mux + optional source-video blend
    # Revert: restore the prior export_video_dialog implementation.
    # =====================================================================
    def export_video_dialog(self, include_audio=True):
        """Start 2.5D video export off the Qt GUI thread."""
        try:
            if self._export_thread is not None and self._export_thread.is_alive():
                self.scope_status_label.setText("🎬 Export already running…")
                return
            out_path, _ = QFileDialog.getSaveFileName(
                self, "Export Video", f"groovebox_video_{self.export_counter:03d}.mp4",
                "MP4 Video (*.mp4);;All Files (*)"
            )
            if not out_path:
                return
            self._export_progress = 0
            self._export_stage = "Rendering video audio"
            if hasattr(self, "export_progress_bar"):
                self.export_progress_bar.setValue(0)
            if hasattr(self, "scope_status_label"):
                self.scope_status_label.setText("🎬 Rendering video + audio in background… 0%")
            self._export_result_queue = queue.Queue()
            self._export_thread = threading.Thread(
                target=self._export_video_worker, args=(out_path, bool(include_audio)),
                name="groovebox-video-export", daemon=True
            )
            self._show_export_progress()
            self._export_poll_timer.start()
            self._export_thread.start()
        except Exception as e:
            print(f"[Video] export setup error: {e}")
            QMessageBox.critical(self, "Video Export Error", str(e))

    def _export_video_worker(self, out_path, include_audio):
        tmp = None
        try:
            from PIL import Image
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("ffmpeg is required for video export. Install ffmpeg and try again.")
            self._export_progress = 0
            self._render_stage = "Rendering video audio"
            master, sr = self._render_mixdown_buffer(progress="export")
            self._export_progress = 50
            self._render_stage = "Rendering video frames"
            fps = 24
            frame_samples = max(1, int(sr / fps))
            n_frames = max(1, int(np.ceil(len(master) / frame_samples)))
            n_frames = min(n_frames, fps * 60)
            tmp = tempfile.mkdtemp(prefix="eqr_vid_")
            frames_dir = os.path.join(tmp, "frames")
            os.makedirs(frames_dir, exist_ok=True)
            audio_path = os.path.join(tmp, "groovebox_audio.wav")
            if include_audio:
                if wavfile is not None:
                    wavfile.write(audio_path, sr, (np.clip(np.asarray(master, dtype=np.float32).ravel(), -1, 1) * 32767).astype(np.int16))
                else:
                    with wave.open(audio_path, 'wb') as wf:
                        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                        wf.writeframes((np.clip(master, -1, 1) * 32767).astype(np.int16).tobytes())
            self._render_stage = "Rendering video frames"
            eng = getattr(self, 'video_synth_engine', None) or VideoSynthEngine(48)
            w, h = 640, 360
            for fi in range(n_frames):
                a = fi * frame_samples; b = min(len(master), a + frame_samples)
                eng.set_waveform(master[a:b])
                frame = eng.render_frame(w, h)
                Image.fromarray(frame, mode="RGB").save(os.path.join(frames_dir, f"frame_{fi:05d}.png"))
                self._export_progress = 60 + int(((fi + 1) / max(n_frames, 1)) * 30)
            self._export_progress = 92
            self._render_stage = "Encoding MP4"
            pattern = os.path.join(frames_dir, "frame_%05d.png")
            source_video = self.imported_video_path if getattr(self, 'imported_video_path', '') else ''
            source_has_audio = bool(getattr(self, 'imported_video_meta', {}).get('has_audio', False))
            duration = f"{n_frames / fps:.6f}"
            if source_video and os.path.abspath(source_video) != os.path.abspath(out_path):
                if include_audio and source_has_audio:
                    filter_complex = (
                        "[1:v]scale=640:360:force_original_aspect_ratio=increase,"
                        "crop=640:360,setsar=1,format=yuv420p[iv];"
                        "[0:v][iv]blend=all_mode=screen:all_opacity=0.35[v];"
                        "[2:a]volume=0.35[srca];[3:a]volume=1.0[gena];"
                        "[srca][gena]amix=inputs=2:duration=longest:normalize=0[a]"
                    )
                    cmd = [
                        ffmpeg, "-y", "-framerate", str(fps), "-i", pattern,
                        "-stream_loop", "-1", "-i", source_video,
                        "-i", audio_path, "-i", source_video,
                        "-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]",
                        "-t", duration, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", out_path
                    ]
                elif include_audio:
                    filter_complex = (
                        "[1:v]scale=640:360:force_original_aspect_ratio=increase,"
                        "crop=640:360,setsar=1,format=yuv420p[iv];"
                        "[0:v][iv]blend=all_mode=screen:all_opacity=0.35[v]"
                    )
                    cmd = [
                        ffmpeg, "-y", "-framerate", str(fps), "-i", pattern,
                        "-stream_loop", "-1", "-i", source_video, "-i", audio_path,
                        "-filter_complex", filter_complex, "-map", "[v]", "-map", "2:a:0",
                        "-t", duration, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", out_path
                    ]
                else:
                    filter_complex = (
                        "[1:v]scale=640:360:force_original_aspect_ratio=increase,"
                        "crop=640:360,setsar=1,format=yuv420p[iv];"
                        "[0:v][iv]blend=all_mode=screen:all_opacity=0.35[v]"
                    )
                    cmd = [
                        ffmpeg, "-y", "-framerate", str(fps), "-i", pattern,
                        "-stream_loop", "-1", "-i", source_video,
                        "-filter_complex", filter_complex, "-map", "[v]",
                        "-t", duration, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", out_path
                    ]
            elif include_audio:
                cmd = [
                    ffmpeg, "-y", "-framerate", str(fps), "-i", pattern, "-i", audio_path,
                    "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-c:v", "libx264",
                    "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", out_path
                ]
            else:
                cmd = [
                    ffmpeg, "-y", "-framerate", str(fps), "-i", pattern,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", out_path
                ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr[-1600:] if proc.stderr else "ffmpeg failed")
            self._export_progress = 100
            self._render_stage = "Complete"
            self._export_result_queue.put(("video", out_path, None, None, None))
        except Exception as e:
            self._export_result_queue.put(("video", out_path, e, None, None))
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        canvas = getattr(self, "parametric_background", None)
        if canvas is None and hasattr(self, "ui_manager"):
            canvas = getattr(self.ui_manager, "parametric_background", None)
        if canvas is not None and cw is not None:
            try:
                canvas.setParent(cw)
                canvas.setGeometry(cw.rect())
                canvas.lower()
                canvas.show()
            except Exception:
                pass

    def closeEvent(self, event):
        """Ensure audio stream and PKP pad clock are torn down on close."""
        try:
            self.stop_playback()
        except Exception:
            pass
        try:
            self.pkp_pad_bank_active = False
        except Exception:
            pass
        super().closeEvent(event)


    def changeEvent(self, event):
        """Bring main window back when restored from minimized / under floating windows."""
        try:
            from PyQt6.QtCore import QEvent
            if event.type() == QEvent.Type.WindowStateChange:
                if not self.isMinimized():
                    self.showNormal()
                    self.raise_()
                    self.activateWindow()
        except Exception:
            pass
        try:
            super().changeEvent(event)
        except Exception:
            pass

    def showEvent(self, event):
        try:
            super().showEvent(event)
        except Exception:
            pass
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def focusInEvent(self, event):
        try:
            super().focusInEvent(event)
        except Exception:
            pass
        try:
            self.raise_()
        except Exception:
            pass

    def _bring_main_to_front(self):
        """Call when user needs the main DAW above floating editors."""
        try:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
            self.showNormal()
            self.raise_()
            self.activateWindow()
        except Exception as exc:
            print(f"[Window] restore: {exc}")

    def spawn_floating_window(self, attr_name, window_title):
        window = getattr(self, attr_name, None)

        if window is None or not window.isVisible():
            window = QWidget(None, Qt.WindowType.Window)
            window.setWindowTitle(window_title)

            if attr_name == 'playlist_window':
                window.resize(1100, 750)
            elif attr_name == 'patch_bay_dialog':
                window.resize(950, 700)
            else:
                window.resize(750, 550)

            main_layout = QVBoxLayout(window)

            current_instrument = self.instrument_selector_dropdown.currentText() if hasattr(self, 'instrument_selector_dropdown') else "Z-Pinch Resonator"
            inst_index = self.instrument_names_48.index(current_instrument) + 1 if current_instrument in self.instrument_names_48 else 1

            if attr_name == 'playlist_window':
                main_layout.addWidget(QLabel(
                    "📜 Unquantized Global Playlist — 96 blank rows · paint identity / steps / automation · "
                    "overlap blends synth params · snap-to-grid optional"
                ))

                time_scale_layout = QHBoxLayout()
                time_scale_layout.addWidget(QLabel("Row time base (unquantized unless Snap):"))
                time_scale_combo = QComboBox()
                time_scale_combo.addItems(["Unquantized Free-Time", "1.0s", "3.5s (Standard)", "15.0s", "30.0s", "60.0s (1 Minute)"])
                time_scale_combo.setCurrentIndex(0)  # unquantized default
                time_scale_layout.addWidget(time_scale_combo)
                time_scale_layout.addStretch(1)
                main_layout.addLayout(time_scale_layout)

                # 48 rows unbound to a fixed instrument — activity painted freely
                rows = min(1024, max(1, int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 96))
                if hasattr(self, 'spin_playlist_length'):
                    self.spin_playlist_length.setValue(rows)
                track_table = PaintbrushTable(self, rows, 10)
                self.active_paint_table = track_table
                if not hasattr(self, 'playlist_automation') or self.playlist_automation is None:
                    self.playlist_automation = [{} for _ in range(rows)]

                track_table.setHorizontalHeaderLabels([
                    "Time Marker", "Operator Identity", "Script Tag",
                    "Velocity", "Auto Target", "Auto Amount",
                    "Direction Vector", "Multi-Seq", "Coverage", "Blend Partner"
                ])

                palette_colors = [
                    QColor(20, 90, 100), QColor(70, 30, 90), QColor(20, 90, 40),
                    QColor(90, 50, 20), QColor(90, 20, 30), QColor(30, 40, 90)
                ]

                def safe_set_cell(r, c, text, bg_color=None):
                    # Safe helper to populate table cells bypassing binding strictness
                    item = track_table.item(r, c)
                    if item is None:
                        item = QTableWidgetItem(text)
                        if bg_color:
                            item.setBackground(bg_color)
                        track_table.model().setData(track_table.model().index(r, c), text, Qt.ItemDataRole.DisplayRole)
                        # Ensure cell background is correctly set via model if item is created raw
                        track_table.setItem(r, c, item)
                    else:
                        item.setText(text)
                        if bg_color:
                            item.setBackground(bg_color)

                def update_time_markers():
                    selection_text = time_scale_combo.currentText()
                    # POWER_V3_EMPTY_PLAYLIST: timing is generated only for rows that
                    # actually contain a painted/programmed event. Opening the editor
                    # therefore does not silently turn 96 blank rows into playlist data.
                    for row_idx in range(rows):
                        data_entry = self.master_playlist_data[row_idx] if row_idx < len(self.master_playlist_data) else {}
                        has_content = isinstance(data_entry, dict) and any(
                            v not in (None, "", [], {}) for k, v in data_entry.items()
                            if k not in ("time_marker",)
                        )
                        if not has_content:
                            continue
                        if "Unquantized" in selection_text:
                            time_str = f"Free-Time [{row_idx * MEUM_CONSTANT:.2f}s]"
                        else:
                            step_seconds = 60.0 if "60.0s" in selection_text else (30.0 if "30.0s" in selection_text else (15.0 if "15.0s" in selection_text else (3.5 if "3.5s" in selection_text else 1.0)))
                            total_seconds = row_idx * step_seconds
                            time_str = f"T + {int(total_seconds // 60)}m {int(total_seconds % 60)}s" if total_seconds >= 60 else f"T + {total_seconds:.1f}s"
                        track_table.set_cell_item(row_idx, 0, QTableWidgetItem(time_str))
                    self.sync_playlist_grid_to_memory()

                time_scale_combo.currentIndexChanged.connect(update_time_markers)

                for row_idx in range(rows):
                    data_entry = self.master_playlist_data[row_idx] if row_idx < len(self.master_playlist_data) else {}
                    auto_list = getattr(self, 'playlist_automation', None) or []
                    auto_entry = auto_list[row_idx] if row_idx < len(auto_list) and isinstance(auto_list[row_idx], dict) else {}

                    empty = not any(v not in (None, "", [], {}) for v in data_entry.values())

                    # Column 1 identity: two schemas can land here.
                    #  - Randomizer/Phase-Lock/midpoint boots (_paint_operator_pattern_to_playlist)
                    #    store the full multi-instance CSV in 'operators_csv' (preferred) or
                    #    the raw 'operators' list.
                    #  - Plain seed/sequence boots (_provide_seed_program_parameters) only ever
                    #    set the single legacy 'operator' field.
                    # Previously this always read 'operator' alone, so a boot with both engines
                    # active showed just the first picked instrument instead of the full
                    # comma-separated list.
                    operators_csv = ""
                    if not empty:
                        operators_csv = data_entry.get("operators_csv") or ""
                        if not operators_csv:
                            ops_list = data_entry.get("operators") or []
                            operators_csv = ", ".join(str(o) for o in ops_list) if ops_list else str(data_entry.get("operator", ""))
                    item_inst = QTableWidgetItem(operators_csv)
                    if not empty:
                        item_inst.setBackground(palette_colors[row_idx % len(palette_colors)])
                    track_table.set_cell_item(row_idx, 0, QTableWidgetItem("" if empty else str(data_entry.get("time_marker", ""))))
                    track_table.set_cell_item(row_idx, 1, item_inst)
                    track_table.set_cell_item(row_idx, 2, QTableWidgetItem("" if empty else str(data_entry.get("script_tag", ""))))
                    track_table.set_cell_item(row_idx, 3, QTableWidgetItem("" if empty else f"{float(data_entry.get('velocity', 1.0))*100:.1f}%"))
                    # Paint all ten cell parameters from the authoritative row/automation state.
                    track_table.set_cell_item(row_idx, 4, QTableWidgetItem("" if empty else str(data_entry.get("effect_target") or data_entry.get("auto_target") or data_entry.get("modulation", ""))))
                    track_table.set_cell_item(row_idx, 5, QTableWidgetItem("" if empty else str(data_entry.get("auto_amount", ""))))
                    direction_text = data_entry.get("direction_vector", "")
                    if not direction_text and not empty:
                        direction_text = "+1" if float(auto_entry.get("direction", 1.0) or 1.0) >= 0 else "-1"
                    track_table.set_cell_item(row_idx, 6, QTableWidgetItem("" if empty else str(direction_text)))
                    track_table.set_cell_item(row_idx, 7, QTableWidgetItem("" if empty else str(data_entry.get("multi_seq", ""))))
                    track_table.set_cell_item(row_idx, 8, QTableWidgetItem("" if empty else str(data_entry.get("coverage", ""))))
                    track_table.set_cell_item(row_idx, 9, QTableWidgetItem("" if empty else str(data_entry.get("blend_partner", ""))))

                update_time_markers()
                main_layout.addWidget(track_table)

            elif attr_name == 'patch_bay_dialog':
                main_layout.addWidget(QLabel("🔌 Advanced Modular Patch Bay & Resonance Nullifier Visualizer"))
                patch_container = QWidget()
                patch_layout = QHBoxLayout(patch_container)

                source_list = QComboBox()
                source_list.addItems([f"{name} Out" for name in self.instrument_names_48])
                patch_layout.addWidget(source_list)

                btn_patch = QPushButton("Connect Operator Cable ⟷")
                patch_layout.addWidget(btn_patch)

                target_list = QComboBox()
                target_list.addItems([f"{name} In" for name in self.instrument_names_48] + ["PKP Envelope Follower Bus", "Geometric Resonance Nullifier Core"])
                patch_layout.addWidget(target_list)
                main_layout.addWidget(patch_container)

                patch_log = QTextEdit()
                patch_log.setReadOnly(True)
                patch_log.setPlainText("# Resonance Nullifier Matrix:\n- Z-Pinch Resonator Out ---> Topological Fold In (Phase-Locked)\n- Stochastic Noise Matrix Out ---> Geometric Resonance Nullifier Core (Engaged)")
                main_layout.addWidget(patch_log)

                btn_patch.clicked.connect(lambda: patch_log.append(f"- {source_list.currentText()} ====> {target_list.currentText()} (Geometric Link Established)"))

            elif attr_name == 'synth_editor_window':
                main_layout.addWidget(QLabel(f"Interactive Wavetable & Vector Synthesis Interface: {current_instrument} (Node ID: {inst_index})"))
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_content = QWidget()
                scroll_layout = QVBoxLayout(scroll_content)

                for param in [f"[{current_instrument}] Wavetable Morph Position", f"[{current_instrument}] Vector 3D Phase Spread (x,y,z)", f"[{current_instrument}] Fractalizer Core Gain", f"[{current_instrument}] Geometric Nullifier Weight"]:
                    row = QHBoxLayout()
                    row.addWidget(QLabel(f"{param}:"))
                    slider = QSlider(Qt.Orientation.Horizontal)
                    slider.setRange(0, 100)
                    slider.setValue(int((inst_index * MEUM_CONSTANT * 10) % 100))
                    row.addWidget(slider)
                    scroll_layout.addLayout(row)

                scroll_content.setLayout(scroll_layout)
                scroll_area.setWidget(scroll_content)
                main_layout.addWidget(scroll_area)

            elif attr_name == 'script_editor_window':
                main_layout.addWidget(QLabel(f"Instrument Script Workspace: {current_instrument}"))
                script_text_area = QTextEdit()
                script_text_area.setPlainText(self.instrument_scripts[current_instrument])
                main_layout.addWidget(script_text_area)

                btn_layout = QHBoxLayout()
                btn_save_script = QPushButton("💾 Save Script to Instrument Memory")

                def save_current_script():
                    self.instrument_scripts[current_instrument] = script_text_area.toPlainText()
                    print(f"[Script] Saved custom code script for operator '{current_instrument}'")

                btn_save_script.clicked.connect(save_current_script)
                btn_layout.addWidget(QPushButton("▶ Execute Script Patch"))
                btn_layout.addWidget(btn_save_script)
                main_layout.addLayout(btn_layout)
            else:
                main_layout.addWidget(QLabel(f"Active Panel: {window_title}"))

            setattr(self, attr_name, window)

        try:
            attach_math_decor(window, app=self)
        except Exception as _de:
            print(f"[Decor] floating: {_de}")
        window.show()
        window.raise_()
        window.activateWindow()
# ============================================================================
# STARTUP_DIAGNOSTIC — protects against the exact QSizePolicy crash reported
# by the user. Keep this import at module scope; do not move it into the UI.
# Revert: remove only this 3-line diagnostic block if a host app supplies its
# own PyQt6 import audit.
# ============================================================================
_REQUIRED_QT_SYMBOLS = (QSizePolicy, QCheckBox, QFileDialog, QProgressBar)
assert all(sym is not None for sym in _REQUIRED_QT_SYMBOLS), "Required PyQt6 UI symbols are unavailable."

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    player = MathematiciansGrooveboxApp()
    player.show()
    sys.exit(app.exec())
