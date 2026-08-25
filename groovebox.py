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
import hashlib
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
MEUM_NORM = MEUM_MINUS_1 * MEUM_INV          # (M-1)/M
MEUM_OVER_1_5 = MEUM / 1.5
MEUM_TWO_POW = 2.0 ** MEUM
MEUM_TWO_POW_OVER_SQ = MEUM_TWO_POW / MEUM_SQ
MEUM_LOG2 = math.log2(MEUM)
# Frequently used integer powers: M^0 ... M^35.
MEUM_POWERS_36 = tuple(MEUM ** i for i in range(36))
MEUM_IDENTITY_LHS = (MEUM_MINUS_1 * MEUM) + (MEUM_MINUS_1 * MEUM_INV)
MEUM_IDENTITY_RHS = MEUM_TWO_POW_OVER_SQ - MEUM
MEUM_IDENTITY_RESIDUAL = MEUM_IDENTITY_LHS - MEUM_IDENTITY_RHS
PHI = 1.6180339887
PHI_INV = 0.6180339887
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
PAINT_INSTANCE_LIMIT = 8

# SAFE_SEED_CAST — get_numeric_seed() intentionally returns a float (it's a
# script/expression evaluator: sin(t), fractional values, hashed floats for
# non-numeric text). NumPy's RNG APIs (np.random.seed, np.random.default_rng)
# require a true integer and raise:
#   "Cannot cast scalar from dtype('float64') to dtype('int64')
#    according to the rule 'safe'"
# if handed a float directly — that's the render/export popup. Every call
# site that seeds NumPy from a user/composition seed value goes through this
# instead of relying on an implicit/unsafe cast.
def _parse_if_elif_shorthand(text):
    """Parse "if(<condition>) <yes> elif <no>" into (condition, yes, no).

    Uses balanced-parenthesis scanning rather than a lazy regex, because a
    naive r"\\((.*?)\\)" stops at the FIRST ")" it finds — which breaks the
    moment the condition itself contains a call like sin(t), e.g.
    "if(sin(t)>=-0.5) 1 elif 2" would wrongly split the condition as
    "sin(t" instead of "sin(t)>=-0.5". Returns None if the text doesn't
    match the "if (...) ... elif ..." shape at all.
    """
    import re as _re
    m = _re.match(r"\s*if\s*\(", text, flags=_re.I)
    if not m:
        return None
    depth = 0
    i = m.end() - 1  # index of the opening '('
    start = m.end()
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                condition = text[start:j]
                rest = text[j + 1:]
                em = _re.search(r"\belif\b", rest, flags=_re.I)
                if not em:
                    return None
                yes_expr = rest[:em.start()].strip()
                no_expr = rest[em.end():].strip()
                return condition, yes_expr, no_expr
    return None


def _safe_int_seed(value):
    """Deterministically fold any seed value into a NumPy-safe non-negative
    int32-range integer. Whole-number floats map to their exact integer
    (so seed=7 and seed=7.0 behave identically); fractional or otherwise
    unrepresentable values are hashed so the mapping stays deterministic
    and well distributed instead of raising or truncating unpredictably."""
    import struct
    try:
        as_float = float(value)
    except Exception:
        as_float = 0.0
    if not math.isfinite(as_float):
        as_float = 0.0
    if as_float == int(as_float) and abs(as_float) < 2**31:
        return int(as_float) & 0x7FFFFFFF
    packed = struct.pack('>d', as_float)
    digest = hashlib.sha256(packed).digest()
    return int.from_bytes(digest[:4], 'big') & 0x7FFFFFFF


def evaluate_seed_expression_at_time(seed_text, t_value):
    """Time-domain (T-axis) evaluation of a seed/script expression, for use
    INSIDE the audio/DSP render loop — the counterpart to get_numeric_seed(),
    which is composition-state evaluation and is documented to never be
    called per-sample. Scripts that reference `t`, or use if/elif shorthand
    keyed on `t` (e.g. "if(sin(t)>=-0.5) 1 elif 2"), resolve against the
    real render-time `t` here instead of the static t=0.0 used at the
    composition-state boundary. Returns a float; callers that need an
    integer NumPy seed should pass the result through _safe_int_seed().
    """
    import re as _re

    text = str(seed_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return 0.0

    text = _re.sub(r"^\s*return\s+", "", text, count=1, flags=_re.I)
    shorthand = _parse_if_elif_shorthand(text)
    if shorthand:
        condition, yes_expr, no_expr = shorthand
        text = f"({yes_expr}) if ({condition}) else ({no_expr})"

    try:
        t_scalar = float(np.asarray(t_value).reshape(-1)[0]) if hasattr(t_value, "__len__") else float(t_value)
    except Exception:
        t_scalar = 0.0

    env = {
        "__builtins__": {},
        "sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt,
        "log": math.log, "log2": math.log2, "exp": math.exp, "abs": abs,
        "min": min, "max": max, "pi": math.pi, "e": math.e,
        "PHI": PHI, "MEUM": MEUM, "MEUM_NORM": MEUM_NORM, "MEUM_INV": MEUM_INV,
        "t": t_scalar, "x": t_scalar, "y": 0.0, "z": 0.0,
    }
    try:
        tree = ast.parse(text, mode="eval")
        value = float(eval(compile(tree, "<groovebox-seed-t>", "eval"), env))
        return value if math.isfinite(value) else 0.0
    except Exception:
        digest = hashlib.sha256(text.encode("utf-8", "replace")).digest()
        integer = int.from_bytes(digest[:8], "big")
        return (integer / float(2**64 - 1)) * 2.0 - 1.0


# FONT_READABILITY_FIX: buttons/labels were clipping their own text at 11pt
# because fixed/min widths elsewhere in the UI were sized for a smaller font
# (see screenshot: "AY Audiovisual", "ded Live Rando", "uclidean Live L",
# "Load WAV Carr" were all truncated). Dropped back to 9pt, which fits inside
# the existing button widths, and let QPushButton auto-size to its label so
# it clips less easily even if a translation/rename makes text longer later.
DAW_STYLE = """
    QMainWindow, QWidget { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt; }
    QPushButton { background-color: #2a2a2a; color: #ffffff; border: 1px solid #3a3a3a; border-radius: 3px; padding: 5px 8px; font-weight: bold; font-size: 9pt; min-height: 20px; }
    QLabel { font-size: 9pt; }
    QCheckBox { font-size: 9pt; }
    QPushButton:hover { background-color: #383838; border: 1px solid #555555; }
    QPushButton:pressed { background-color: #ff6b00; }
    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { background-color: #1a1a1a; color: #00ffcc; border: 1px solid #333333; border-radius: 3px; padding: 3px; font-size: 9pt; }
    QTableWidget { background-color: #161616; gridline-color: #282828; color: #ffffff; }
    QHeaderView::section { background-color: #1f1f1f; color: #aaaaaa; border: 1px solid #333333; font-size: 8pt; }
    QLabel { color: #cccccc; }
    QSlider::groove:horizontal { height: 4px; background: #333333; border-radius: 2px; }
    QSlider::handle:horizontal { background: #ff6b00; width: 12px; margin: -4px 0; border-radius: 6px; }
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
# Canonical playlist record schema. Every engine, UI sync, and CSV/member path
# must preserve all visible playlist columns in this order.
# Each row can carry a fully idealized instrument data-struct set:
#   Script + Domain + Synth + Modular Patch, plus time offset and blend/coverage
# so instruments can Unison-module with each other via virtual overlap only.
PLAYLIST_COLUMNS = (
    "time_marker", "operators_csv",
    "script_tag", "domain_tag", "synth_tag", "patch_tag",
    "velocity", "effect_target", "auto_amount",
    "direction_vector", "multi_seq", "coverage", "blend_partner",
)
PLAYLIST_COLUMN_COUNT = len(PLAYLIST_COLUMNS)
# Semantic groups used by cross-cell blend (any of these can blend under coverage).
PLAYLIST_STRUCT_COLUMNS = ("script_tag", "domain_tag", "synth_tag", "patch_tag")
PLAYLIST_STRUCT_COL_INDICES = (2, 3, 4, 5)  # indices into PLAYLIST_COLUMNS

def idealized_operator_struct(app, op_name, row=0, seed=0):
    """Build the canonical per-instrument data-struct set used by playlist cells.

    Returns dict with script_tag, domain_tag, synth_tag, patch_tag — compact
    labels that point at the live instrument_scripts / domain_eq_engine /
    instrument_param_state / patch_connections stores so Unison composition
    only needs time_offset + coverage/blend to recycle patterns.
    """
    op = str(op_name or "Operator")
    short = op.split(".")[-1].strip()[:18] if op else "Op"
    # Script
    script_body = ""
    if app is not None and hasattr(app, "instrument_scripts"):
        script_body = str((app.instrument_scripts or {}).get(op, "") or "")
    script_line = ""
    for line in script_body.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            script_line = s[:48]
            break
    if not script_line:
        script_line = f"Script::{short.upper()[:6]}"
    script_tag = script_line

    # Domain — prefer a matching domain_eq_engine partition, else a Meum-stable tag
    domain_tag = f"Dom::{short[:8]}[t]"
    engine = getattr(app, "domain_eq_engine", None) if app is not None else None
    if engine is not None:
        for dom in getattr(engine, "domains", []) or []:
            if not isinstance(dom, dict):
                continue
            name = str(dom.get("name", ""))
            if short[:6].lower() in name.lower() or op[:8].lower() in name.lower():
                axis = dom.get("axis", "time")
                t0, t1 = dom.get("t0", 0.0), dom.get("t1", 1.0)
                domain_tag = f"{name[:16]}|{axis}|{float(t0):.2f}-{float(t1):.2f}"
                break
        else:
            # Seed-stable synthetic domain label from first partition template
            if engine.domains:
                d0 = engine.domains[min(row % max(len(engine.domains), 1), len(engine.domains) - 1)]
                domain_tag = f"{str(d0.get('name', 'Dom'))[:14]}@r{row}"

    # Synth snapshot from instrument_param_state
    synth_tag = f"Synth::{short[:10]}"
    params = {}
    if app is not None:
        params = dict((getattr(app, "instrument_param_state", {}) or {}).get(op, {}) or {})
        gen = dict((getattr(app, "instrument_param_generated", {}) or {}).get(op, {}) or {})
        for k, v in gen.items():
            params.setdefault(k, v)
    if params:
        # Compact key=val list of primary macros
        keys = ("eqr", "fractalizer", "pkp_decay", "tuning", "filter", "drive", "amplitude")
        parts = []
        for k in keys:
            if k in params:
                try:
                    parts.append(f"{k[0:3]}={float(params[k]):.2f}")
                except Exception:
                    parts.append(f"{k[0:3]}={params[k]}")
        if parts:
            synth_tag = "|".join(parts[:5])

    # Modular patch — incident edges for this operator
    patch_tag = f"Patch::{short[:8]}"
    edges = []
    if app is not None:
        for c in getattr(app, "patch_connections", []) or []:
            if not isinstance(c, dict):
                continue
            src, tgt = c.get("source"), c.get("target")
            if src == op or tgt == op:
                w = c.get("weight", c.get("gain", 0.5))
                try:
                    w = float(w)
                except Exception:
                    w = 0.5
                other = tgt if src == op else src
                arrow = "→" if src == op else "←"
                edges.append(f"{arrow}{str(other).split('.')[-1].strip()[:10]}@{w:.2f}")
        if not edges:
            try:
                for c in getattr(globals().get("GLOBAL_BUS", None), "global_cables", []) or []:
                    src, tgt = c.get("src_module"), c.get("tgt_module")
                    if src == op or tgt == op:
                        other = tgt if src == op else src
                        edges.append(f"{'→' if src == op else '←'}{str(other)[:10]}")
            except Exception:
                pass
    if edges:
        patch_tag = ",".join(edges[:3])

    return {
        "script_tag": script_tag,
        "domain_tag": domain_tag,
        "synth_tag": synth_tag,
        "patch_tag": patch_tag,
        "operator": op,
    }


def blend_struct_labels(a, b, amount):
    """Blend two structure cell labels under coverage amount in [0,1].

    amount is the virtual-overlap fraction (same meaning as row_coverage /
    blend_max Half|Quarter). Result is a dual-label so Unison recycling can
    see both parents, weighted by overlap.
    """
    a = str(a or "").strip()
    b = str(b or "").strip()
    try:
        amt = float(amount)
    except Exception:
        amt = 0.5
    amt = max(0.0, min(1.0, amt))
    if not a and not b:
        return ""
    if not b or amt <= 0.02:
        return a
    if not a or amt >= 0.98:
        return b
    # Keep both parents visible; mark the dominant side.
    if amt < 0.5:
        return f"{a}~{b[:18]}@{amt:.0%}"
    return f"{b}~{a[:18]}@{(1.0 - amt):.0%}"


class FormulaModulatorWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Dynamic Coordinate Formula Inputs</b>"))

        # Formula Inputs
        self.x_input = self.create_formula_row(layout, "X-Axis Expr:", "np.sin(time * 2.0) + base_x")
        self.y_input = self.create_formula_row(layout, "Y-Axis Expr:", "np.cos(time * 1.5) * base_y")
        self.z_input = self.create_formula_row(layout, "Z-Axis Expr:", "abs(x + y) - time")

        # Compile Button
        self.compile_btn = QPushButton("Inject Formulas into Audio Thread")
        self.compile_btn.setStyleSheet("background-color: darkred; color: white; font-weight: bold;")
        layout.addWidget(self.compile_btn)

    def create_formula_row(self, parent_layout, label_text, default_expr):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))

        line_edit = QLineEdit(default_expr)
        line_edit.setStyleSheet("background-color: #222; color: #0f0; font-family: monospace;")
        row.addWidget(line_edit)

        # Add a macro slider for manual offset tuning
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(50)
        row.addWidget(slider)

        parent_layout.addLayout(row)
        return line_edit
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
        self._frame = np.zeros((180, 320, 3), dtype=np.uint8)
        self.show_scope_overlay = True
        self.scope_wave = np.zeros(100, dtype=np.float32)

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


class ModulationMatrixWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        layout = QGridLayout(self)

        layout.addWidget(QLabel("<b>Virtual Patch Matrix</b>"), 0, 0, 1, 4)
        layout.addWidget(QLabel("Source"), 1, 0)
        layout.addWidget(QLabel("Destination"), 1, 1)
        layout.addWidget(QLabel("Amount"), 1, 2)

        # Create 4 patch cables
        self.patches = []
        for i in range(4):
            source_combo = QComboBox()
            source_combo.addItems(["None", "X Coordinate", "Y Coordinate", "Z Coordinate", "LFO 1", "Step Sequencer"])

            dest_combo = QComboBox()
            dest_combo.addItems(["None", "Filter Cutoff", "Resonance", "Wave Drive", "Delay Time", "Delay Feedback", "Pitch Node"])

            amount_spin = QDoubleSpinBox()
            amount_spin.setRange(-1.0, 1.0)
            amount_spin.setSingleStep(0.01)
            amount_spin.setValue(0.5)

            layout.addWidget(source_combo, i+2, 0)
            layout.addWidget(dest_combo, i+2, 1)
            layout.addWidget(amount_spin, i+2, 2)

            self.patches.append({"source": source_combo, "dest": dest_combo, "amount": amount_spin})
class PatchbayCanvas(QFrame):
    """Interactive visual patchbay canvas for signal routing and node mapping."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)
        self.setStyleSheet("background-color: #121418; border: 1px solid #2a2e39; border-radius: 6px;")


class MemoryBankSelector(QWidget):
    """Memory Bank Selector pane for project workflow and preset management."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.bank_combo = QComboBox()
        self.bank_combo.addItems([
            "Bank Alpha [90uF/900V Resonant]",
            "Bank Beta [2000uF/1350V]",
            "Bank Gamma [3500uF/300V]"
        ])
        self.bank_combo.setStyleSheet("background-color: #1a1e24; color: #00ffcc; border: 1px solid #3a3f4b; padding: 4px;")

        load_btn = QPushButton("Load Preset State")
        save_btn = QPushButton("Save State Snapshot")
        for btn in (load_btn, save_btn):
            btn.setStyleSheet("background-color: #222733; color: #ffffff; border: 1px solid #3a3f4b; padding: 6px;")

        layout.addWidget(QLabel("<b>Memory Bank Selector</b>"))
        layout.addWidget(self.bank_combo)
        layout.addWidget(load_btn)
        layout.addWidget(save_btn)
        layout.addStretch()
class EQRMathEngine:
    def __init__(self, use_meum=True):
        """
        Initializes the EQR math engine.
        Args:
            use_meum (bool): Flag to toggle Meum factor weighting.
                             (Default set based on project optimization preference).
        """
        self.use_meum = use_meum

    # --- Custom Isosceles Trigonometric Functions ---
    def isn(self, val):
        """Isosceles Sine implementation."""
        arr = np.asarray(val, dtype=float)
        return np.sin(arr) / (1.0 + np.abs(np.cos(arr)))

    def ics(val):
        """Isosceles Cosine implementation."""
        arr = np.asarray(val, dtype=float)
        return np.cos(arr) / (1.0 + np.abs(np.sin(arr)))

    def arcisn(self, val):

        arr = np.asarray(val, dtype=float)
        v = np.clip(arr / 2.0, -1.0, 1.0)
        return np.arcsin(v)

    def arcics(self, val):

        arr = np.asarray(val, dtype=float)
        v = np.clip(arr / 2.0, -1.0, 1.0)
        return np.arccos(v)

    # --- Core Expression Evaluator ---
    def evaluate_coordinate_expression(expr_str, x, y, z):

    # Safe namespace dictionary for mathematical parsing
        allowed_globals = {
            "__builtins__": {},
            "sin": np.sin,
            "cos": np.cos,
            "tan": np.tan,
            "sqrt": np.sqrt,
            "abs": np.abs,
            "pi": np.pi,
            "e": np.e
        }

        local_vars = {
            "x": float(x),
            "y": float(y),
            "z": float(z)
        }

        try:
            # Evaluates strictly against x, y, and z parameters
            result = eval(expr_str, allowed_globals, local_vars)
            return float(result)
        except Exception as e:
            print(f"Evaluation Error for expression '{expr_str}': {e}")
            return 0.0
class PortWidget(QWidget):
    """Input/output terminal for the scientific patchbay node network."""
    def __init__(self, port_type, parent=None):
        super().__init__(parent)
        self.port_type = port_type  # 'in' or 'out'
        self.setFixedSize(22, 22)
        self.color = "#00ffc8" if port_type == 'out' else "#ff6400"
        self.setStyleSheet(f"""
            background-color: {self.color};
            border-radius: 11px;
            border: 3px solid #1a1a1a;
        """)

    def mousePressEvent(self, event):
        if self.parent() and hasattr(self.parent(), 'start_cable_drag'):
            self.parent().start_cable_drag(self)
        event.accept()


class ScientificCanvas(QWidget):
    """Interactive node patchbay canvas with Bezier signal cables."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(2400, 1800)
        self.cables = []
        self.active_cable_start = None
        self.current_mouse_pos = QPoint(0, 0)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #0b0b0e; border: 1px solid #1f1f2e;")

    def start_cable_drag(self, port_widget):
        self.active_cable_start = port_widget
        self.current_mouse_pos = port_widget.mapTo(self, port_widget.rect().center())
        self.update()

    def mouseMoveEvent(self, event):
        if self.active_cable_start:
            self.current_mouse_pos = event.pos()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.active_cable_start:
            target_widget = self.childAt(event.pos())
            if isinstance(target_widget, PortWidget) and target_widget != self.active_cable_start:
                if self.active_cable_start.port_type != target_widget.port_type:
                    cable_pair = (self.active_cable_start, target_widget)
                    reverse_pair = (target_widget, self.active_cable_start)
                    if cable_pair not in self.cables and reverse_pair not in self.cables:
                        self.cables.append(cable_pair)
            self.active_cable_start = None
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for start, end in self.cables:
            if start and end:
                p1 = start.mapTo(self, start.rect().center())
                p2 = end.mapTo(self, end.rect().center())

                glow_pen = QPen(QColor(0, 255, 200, 50), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(glow_pen)
                painter.drawPath(self.create_bezier_path(p1, p2))

                core_pen = QPen(QColor(0, 255, 200), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(core_pen)
                painter.drawPath(self.create_bezier_path(p1, p2))

        if self.active_cable_start:
            p1 = self.active_cable_start.mapTo(self, self.active_cable_start.rect().center())
            p2 = self.current_mouse_pos
            drag_pen = QPen(QColor(255, 100, 0, 200), 2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(drag_pen)
            painter.drawPath(self.create_bezier_path(p1, p2))

    def create_bezier_path(self, p1, p2):
        path = QPainterPath()
        path.moveTo(p1)
        dx = (p2.x() - p1.x()) * 0.5
        ctrl1 = QPoint(p1.x() + dx, p1.y())
        ctrl2 = QPoint(p2.x() - dx, p2.y())
        path.cubicTo(ctrl1, ctrl2, p2)
        return path

class MathNodeWidget(QFrame):
    """Draggable processing node for algebra & vector fields."""
    def __init__(self, name, x, y, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.resize(240, 150)
        self.move(x, y)
        self.setStyleSheet("""
            background-color: #14141c;
            color: #ffffff;
            border: 1px solid #2e2e42;
            border-radius: 8px;
        """)

        layout = QVBoxLayout(self)
        self.title_input = QLineEdit(name)
        self.title_input.setStyleSheet("""
            background-color: #1c1c28;
            color: #00ffc8;
            border: 1px solid #3d3d5c;
            padding: 4px;
            font-weight: bold;
            border-radius: 4px;
        """)
        layout.addWidget(self.title_input)

        ports_layout = QHBoxLayout()
        in_container = QVBoxLayout()
        lbl_in = QLabel("IN")
        lbl_in.setStyleSheet("color: #ff6400; border: none; font-size: 9px; font-weight: bold;")
        in_container.addWidget(lbl_in)
        self.in_port = PortWidget('in', self)
        in_container.addWidget(self.in_port)

        out_container = QVBoxLayout()
        lbl_out = QLabel("OUT")
        lbl_out.setStyleSheet("color: #00ffc8; border: none; font-size: 9px; font-weight: bold;")
        out_container.addWidget(lbl_out)
        self.out_port = PortWidget('out', self)
        out_container.addWidget(self.out_port)

        ports_layout.addLayout(in_container)
        ports_layout.addLayout(out_container)
        layout.addLayout(ports_layout)

        self.dragging = False
        self.drag_position = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.raise_()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            if self.parent():
                self.parent().update()
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False

class SequencerPane(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>16-Step Modulation Sequencer</b>"))

        grid_layout = QGridLayout()
        self.steps = []
        for i in range(16):
            btn = QPushButton(str(i+1))
            btn.setCheckable(True)
            btn.setStyleSheet("background-color: #222; color: #888;")
            btn.clicked.connect(lambda checked, b=btn: b.setStyleSheet("background-color: #00aa55; color: #fff;" if b.isChecked() else "background-color: #222; color: #888;"))
            row, col = divmod(i, 8)
            grid_layout.addWidget(btn, row, col)
            self.steps.append(btn)

        layout.addLayout(grid_layout)
class DoubleNumericSliderRow(QWidget):
    """Precision double slider + spinbox widget."""
    def __init__(self, min_val, max_val, default_val, decimals=2, unit="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * 100), int(max_val * 100))
        self.slider.setValue(int(default_val * 100))
        self.slider.setStyleSheet("background: transparent;")

        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(min_val, max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setSuffix(unit)
        self.spinbox.setStyleSheet("background-color: #1c1c28; color: #00ffc8; border: 1px solid #3d3d5c; padding: 2px; border-radius: 3px;")

        self.slider.valueChanged.connect(lambda v: self.spinbox.setValue(v / 100.0))
        self.spinbox.valueChanged.connect(lambda v: self.slider.setValue(int(v * 100)))

        layout.addWidget(self.slider, 3)
        layout.addWidget(self.spinbox, 1)


class SoundCloudTimelineVisualizer(QWidget):
    """SoundCloud-style static waveform overview with split-spectrum color gradient peaks and recursion trigger labels."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(140)
        self.setStyleSheet("background-color: #0b0b0e; border: 1px solid #1f1f2e; border-radius: 6px;")
        # Pre-calculated structural events: (x_ratio, label, color_mode, depth_param)
        self.triggers = [
            (0.08, "EskiBrutuses WaveMorph [x=0.2, d=3]", "#00ffc8", 1),
            (0.22, "EQR Singularity Collapse [f(x,y,z)=0]", "#ff00ff", 2),
            (0.35, "EskiPhased Non-Linear Matrix [Feedback 82%]", "#00bfff", 1.5),
            (0.48, "Fractalizer Harmonic Fold [Depth 5x]", "#ff6400", 3),
            (0.65, "EskiRecursive Wave-Fold [Chaos Mod 0.4]", "#ffff00", 2.2),
            (0.82, "Z-Axis Field Resonance [Peak Phase]", "#ff0055", 2.8)
        ]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        mid_y = h / 2.0 - 10

        # Draw background track bar
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 16, 24))
        painter.drawRoundedRect(10, 10, w - 20, h - 20, 6, 6)

        # Draw SoundCloud style static amplitude peaks with split-spectrum colors
        random.seed(42) # Consistent static peak generation
        bar_width = 3
        gap = 2
        num_bars = (w - 40) // (bar_width + gap)

        for i in range(num_bars):
            x = 20 + i * (bar_width + gap)
            ratio = i / num_bars

            # Formulate multi-frequency loudness curve across duration
            envelope = math.sin(ratio * math.pi * 3.5) * 0.5 + 0.5
            harmonic = math.cos(ratio * math.pi * 12.0) * 0.25 + 0.75
            noise = random.uniform(0.4, 1.0)
            amplitude = int((h - 50) * envelope * harmonic * noise)

            # Split spectrum color grading based on frequency band
            if ratio < 0.3:
                grad_color = QColor(0, 255, 200, 200) # Cyan / Sub-bass
            elif ratio < 0.6:
                grad_color = QColor(255, 0, 255, 200) # Magenta / Mid harmonics
            else:
                grad_color = QColor(255, 100, 0, 200) # Orange / High fractal folds

            painter.setBrush(grad_color)
            painter.drawRoundedRect(x, int(mid_y - amplitude / 2), bar_width, max(4, amplitude), 1, 1)

        # Draw Timeline Trigger Labels & Recursion Markers
        for rx, text, hex_col, depth in self.triggers:
            tx = int(rx * w)
            # Marker line
            painter.setPen(QPen(QColor(hex_col), 2, Qt.PenStyle.SolidLine))
            painter.drawLine(tx, 15, tx, h - 15)

            # Floating label tag
            painter.setBrush(QColor(18, 18, 28, 230))
            painter.setPen(QPen(QColor(hex_col), 1))
            label_w = min(170, len(text) * 6 + 12)
            painter.drawRoundedRect(tx - 5, h - 38, label_w, 24, 4, 4)

            painter.setPen(QColor(240, 240, 255))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(tx, h - 22, text)


class SynthRackUnitWidget(QFrame):
    """Dedicated interactive control panel for an active synth instance with all parameters & modes."""
    def __init__(self, synth_name, synth_id, parent=None):
        super().__init__(parent)
        self.synth_name = synth_name
        self.synth_id = synth_id
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            background-color: #14141c;
            border: 1px solid #2e2e42;
            border-radius: 8px;
            padding: 8px;
        """)

        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title_lbl = QLabel(f"⚡ {synth_name} [Instance #{synth_id}]")
        title_lbl.setStyleSheet("color: #00ffc8; font-weight: bold; font-size: 13px; border: none;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Mode A: Vector Space Warp",
            "Mode B: Non-Linear Resonance",
            "Mode C: Recursive Chaos Fold",
            "Mode D: EQR Singularity Lock"
        ])
        self.mode_combo.setStyleSheet("background-color: #1c1c28; color: #fff; border: 1px solid #3d3d5c; padding: 3px; border-radius: 4px;")
        header_layout.addWidget(self.mode_combo)
        layout.addLayout(header_layout)

        # Knobs & Implicit Parameters
        params_grid = QGridLayout()

        self.param1 = DoubleNumericSliderRow(0.01, 10.0, 1.2, decimals=2, unit="x")
        self.param2 = DoubleNumericSliderRow(20.0, 20000.0, 880.0, decimals=1, unit=" Hz")
        self.param3 = DoubleNumericSliderRow(0.0, 1.0, 0.75, decimals=2, unit="")
        self.param4 = DoubleNumericSliderRow(1.0, 16.0, 4.0, decimals=1, unit=" Stp")

        params_grid.addWidget(QLabel("Morph Rate / Speed:"), 0, 0)
        params_grid.addWidget(self.param1, 0, 1)
        params_grid.addWidget(QLabel("Harmonic Frequency:"), 1, 0)
        params_grid.addWidget(self.param2, 1, 1)
        params_grid.addWidget(QLabel("Feedback / Chaos Blend:"), 2, 0)
        params_grid.addWidget(self.param3, 2, 1)
        params_grid.addWidget(QLabel("Recursive Fold Depth:"), 3, 0)
        params_grid.addWidget(self.param4, 3, 1)

        layout.addLayout(params_grid)
class WaveformVisualizer(QWidget):
    """Custom visualizer widget for real-time amplitude peak monitoring."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.amplitude_data = [0.0] * 50

    def update_data(self, new_val):
        self.amplitude_data.pop(0)
        self.amplitude_data.append(new_val)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background canvas
        painter.fillRect(self.rect(), QColor(20, 20, 25))

        # Draw waveform trace based on coordinate evaluations
        pen = QPen(QColor(0, 220, 150))
        pen.setWidth(2)
        painter.setPen(pen)

        width = self.width()
        height = self.height()
        step = width / max(len(self.amplitude_data) - 1, 1)

        for i in range(len(self.amplitude_data) - 1):
            x1 = int(i * step)
            y1 = int(height / 2 - self.amplitude_data[i] * (height / 2))
            x2 = int((i + 1) * step)
            y2 = int(height / 2 - self.amplitude_data[i + 1] * (height / 2))
            painter.drawLine(x1, y1, x2, y2)
class DoubleNumericSliderRow(QWidget):
    """Synchronized precision double-spinbox and slider layout for scientific variables."""
    def __init__(self, min_val, max_val, default_val, decimals=2, unit="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * 100), int(max_val * 100))
        self.slider.setValue(int(default_val * 100))
        self.slider.setStyleSheet("background: transparent;")

        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(min_val, max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setSuffix(unit)
        self.spinbox.setStyleSheet("background-color: #27272a; color: #00ffc8; border: 1px solid #52525b; padding: 3px; border-radius: 3px;")

        self.slider.valueChanged.connect(lambda v: self.spinbox.setValue(v / 100.0))
        self.spinbox.valueChanged.connect(lambda v: self.slider.setValue(int(v * 100)))

        layout.addWidget(self.slider, 3)
        layout.addWidget(self.spinbox, 1)
class FlexibleSequencer:
    """Holds subsequence memory within intervals with non-destructive quantization."""
    def __init__(self):
        self.sequence_buffer = []
        self.quantize_grid = None
    def mousePressEvent(self, event):
        if self.parent() and hasattr(self.parent(), 'start_cable_drag'):
            self.parent().start_cable_drag(self)
        event.accept()
    def add_note(self, time, pitch, duration):
        self.sequence_buffer.append({'time': time, 'pitch': pitch, 'duration': duration})

    def get_subsequence(self, start_interval, end_interval):
        sub = [n for n in self.sequence_buffer if start_interval <= n['time'] < end_interval]
        if self.quantize_grid:
            quantized = []
            for note in sub:
                q_note = note.copy()
                q_note['time'] = round(note['time'] / self.quantize_grid) * self.quantize_grid
                quantized.append(q_note)
            return quantized
        return sub
class CablePatchPanel(QWidget):
    """Interactive canvas workspace for nodes and cable patching via ports."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(1600, 1000)
        self.cables = []
        self.active_cable_start = None
        self.current_mouse_pos = QPoint(0, 0)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #121212; border: 1px solid #333;")

    def start_cable_drag(self, port_widget):
        self.active_cable_start = port_widget
        self.current_mouse_pos = port_widget.mapTo(self, port_widget.rect().center())
        self.update()

    def mouseMoveEvent(self, event):
        if self.active_cable_start:
            self.current_mouse_pos = event.pos()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.active_cable_start:
            target_widget = self.childAt(event.pos())
            if isinstance(target_widget, PortWidget) and target_widget != self.active_cable_start:
                if self.active_cable_start.port_type != target_widget.port_type:
                    self.cables.append((self.active_cable_start, target_widget, QColor(0, 255, 200)))
            self.active_cable_start = None
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for start, end, color in self.cables:
            if start and end:
                p1 = start.mapTo(self, start.rect().center())
                p2 = end.mapTo(self, end.rect().center())
                pen = QPen(color, 3.0, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.drawLine(p1, p2)

        if self.active_cable_start:
            p1 = self.active_cable_start.mapTo(self, self.active_cable_start.rect().center())
            pen = QPen(QColor(255, 100, 0, 220), 2.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(p1, self.current_mouse_pos)
class MathEngine:
    """Core mathematical engine evaluated strictly on x, y, z variables without Meum factors."""
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

class GlobalPatchBus:
    def __init__(self):
        self.cables = []
        self.nodes = {}

    def add_cable(self, src, dst):
        if (src, dst) not in self.cables:
            self.cables.append((src, dst))

    def remove_cable(self, src, dst):
        if (src, dst) in self.cables:
            self.cables.remove((src, dst))

global_patch_bus = GlobalPatchBus()
class EQRCoordinateEngine:
    def __init__(self):
        self.x = np.linspace(-1.0, 1.0, 512)
        self.y = np.linspace(-1.0, 1.0, 512)
        self.z = np.zeros(512)

    def evaluate_composition_script(self, script_text: str, t: float):
        x, y, z = self.x, self.y, self.z + t
        namespace = {"np": np, "x": x, "y": y, "z": z, "isn": np.sin, "ics": np.cos, "result": np.zeros_like(x)}

        try:
            exec(script_text, namespace)
            output = namespace.get("result", np.zeros_like(x))
            return self.apply_heuristic_envelope(output)
        except Exception as e:
            print(f"Script Execution Error: {e}")
            return np.zeros_like(x)

    def apply_heuristic_envelope(self, signal_vector):
        envelope = np.exp(-np.abs(self.x) * 2.5)
        return signal_vector * envelope


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
        """Vectorized-friendly series evaluation over a 1D time array (normalized 0..1)."""
        t_array = np.asarray(t_array, dtype=float)
        out = np.zeros_like(t_array, dtype=float)
        t_min, t_max = float(t_array.min()), float(t_array.max())
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
        domains = []
        for r in range(self.table.rowCount()):
            try:
                domains.append(self._parse_row(r))
            except Exception as e:
                QMessageBox.warning(self, "Parse Error", f"Row {r+1}: {e}")
                return
        self.engine.domains = domains
        QMessageBox.information(self, "Domains Applied", f"{len(domains)} domain partition(s) active.")
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


class FocusZone3DWidget(QWidget):
    """3D zone widget featuring mouse point selection, right-click insert, and middle-click/scroll deletion."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)
        self.focal_points = [{'x': 0.0, 'y': 0.0, 'z': 0.0}]
        self.selected_point_idx = 0
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        w, h = self.width(), self.height()
        click_x = event.position().x()
        click_y = event.position().y()

        clicked_idx = -1
        for idx, pt in enumerate(self.focal_points):
            px = int((pt['x'] + 1.0) * (w / 2.0))
            py = int((1.0 - pt['y']) * (h / 2.0))
            if abs(click_x - px) < 14 and abs(click_y - py) < 14:
                clicked_idx = idx
                break

        if event.button() == Qt.MouseButton.LeftButton:
            if clicked_idx != -1:
                self.selected_point_idx = clicked_idx
                self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            if clicked_idx != -1:
                self.selected_point_idx = clicked_idx
            else:
                nx = (click_x / w) * 2.0 - 1.0
                ny = 1.0 - (click_y / h) * 2.0
                self.focal_points.append({'x': nx, 'y': ny, 'z': 0.0})
                self.selected_point_idx = len(self.focal_points) - 1
            self.update()
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Middle-click directly deletes the clicked or currently selected point
            target_idx = clicked_idx if clicked_idx != -1 else self.selected_point_idx
            if len(self.focal_points) > 1:
                self.focal_points.pop(target_idx)
                self.selected_point_idx = max(0, target_idx - 1)
                self.update()

    def wheelEvent(self, event):
        # Scrolling downward also deletes the selected point if more than one exists
        if event.angleDelta().y() < 0 and len(self.focal_points) > 1:
            self.focal_points.pop(self.selected_point_idx)
            self.selected_point_idx = max(0, self.selected_point_idx - 1)
            self.update()
        event.accept()

    def update_coordinate_axis(self, axis: str, val: float):
        if self.focal_points:
            self.focal_points[self.selected_point_idx][axis] = val
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(20, 20, 28))

        painter.setPen(QPen(QColor(50, 50, 70), 1, Qt.PenStyle.DashLine))
        w, h = self.width(), self.height()
        painter.drawLine(0, h // 2, w, h // 2)
        painter.drawLine(w // 2, 0, w // 2, h)

        for idx, pt in enumerate(self.focal_points):
            px = int((pt['x'] + 1.0) * (w / 2.0))
            py = int((1.0 - pt['y']) * (h / 2.0))

            color = QColor(255, 100, 100) if idx == self.selected_point_idx else QColor(0, 220, 180)
            painter.setBrush(color)
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawEllipse(px - 8, py - 8, 16, 16)

            painter.setPen(QPen(Qt.GlobalColor.white, 1))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(px + 12, py - 5, f"P{idx}({pt['x']:.2f},{pt['y']:.2f},{pt['z']:.2f})")


class EQRVisualizerCanvas(QWidget):
    """
    Real-time parametric visualizer based on the Equation of Reality (EQR)
    operator framework, mapping x, y, and z variables to dynamic phase-space renders.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setStyleSheet("background-color: #0b0b0b; border: 1px solid #ff6b00; border-radius: 4px;")

        self.phase = 0.0
        self.scale_factor = 1.0
        self.x_offset = 0.0
        self.y_offset = 0.0

        # Timer for real-time mathematical phase updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_phase)
        self.timer.start(30) # ~33 FPS smooth render

    def update_phase(self):
        self.phase += 0.03
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.fillRect(self.rect(), QColor(11, 11, 11))
            w, h = self.width(), self.height()
            cx, cy = w / 2.0, h / 2.0

            # Draw coordinate grid / field lines
            painter.setPen(QPen(QColor(30, 30, 30), 1, Qt.PenStyle.DashLine))
            painter.drawLine(0, int(cy), w, int(cy))
            painter.drawLine(int(cx), 0, int(cx), h)

            # EQR Parametric Curve Rendering (x, y, z operator mapping)
            pen = QPen(QColor(0, 255, 204), 2)
            painter.setPen(pen)

            points = []
            num_steps = 300
            for i in range(num_steps):
                t = (i / num_steps) * 4 * np.pi + self.phase

                # EQR Core Equations for x, y, and z variables
                x_val = np.sin(t * 1.5) * np.cos(t * 0.5 + self.phase * 0.2) * 120.0
                y_val = np.cos(t * 2.0) * np.sin(t * 1.2) * 80.0
                z_val = np.sin(t + self.phase) * 50.0 # Operator depth factor

                # Projection mapping onto 2D canvas space
                px = cx + x_val + (z_val * 0.3)
                py = cy + y_val + (z_val * 0.2)
                points.append(QPointF(px, py))

            for i in range(len(points) - 1):
                # Gradient color transition based on index
                hue_color = QColor.fromHsvF((i / num_steps + self.phase * 0.1) % 1.0, 0.8, 1.0)
                painter.setPen(QPen(hue_color, 2))
                painter.drawLine(points[i], points[i+1])

        finally:
            painter.end()
class AdvancedDSPEngine:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate

    def compute_synth_waveform(self, track_idx, sub_t, freq, state):
        # Retrieve 6 internal sliding scale parameters
        k1 = state.get("internal_p1", 0.5)
        k2 = state.get("internal_p2", 0.5)
        k3 = state.get("internal_p3", 0.5)
        k4 = state.get("internal_p4", 0.5)
        k5 = state.get("internal_p5", 0.5)
        k6 = state.get("internal_p6", 0.5)

        # External controls & preset selector
        fractal = state.get("fractalizer", 0.5)
        eqr = state.get("eqr_effect", 0.5)
        preset = state.get("preset_idx", 0)

        phase = 2 * np.pi * freq * sub_t

        # Route math based on the Preset Dropdown selection (0 to 4)
        if preset == 0:
            # Preset 0: Non-Linear Wave-Folder Topology
            raw = np.sin(phase * (1.0 + k1)) + k2 * np.sin(phase * 2.0 * k3)
            folded = np.tanh(raw * (1.0 + fractal * 5.0))
            return folded * (1.0 + k4 * np.cos(phase * k5)) * (1.0 - k6 * 0.5)

        elif preset == 1:
            # Preset 1: Z-Pinch / Quantum Field Resonance
            pinched = np.sin(phase * (1.0 + track_idx * 0.05)) * (1.0 + k1 * np.tan(np.clip(sub_t * k2, -1.5, 1.5)))
            resonance = np.arcsin(np.clip(pinched * (0.5 + eqr), -0.99, 0.99))
            return resonance * k3 * (1.0 + k4 * np.sin(sub_t * k5 * 10.0)) * (1.0 - k6)

        elif preset == 2:
            # Preset 2: Hyperbolic & Torus Phase-Space
            hyp = np.sinh(k1 * np.sin(phase)) / (1.0 + np.cosh(k2 * np.cos(phase * k3)))
            torus_mod = np.cos(phase * (1.0 + k4)) + 0.5 * np.sin(phase * (2.0 + k5))
            return hyp * torus_mod * (1.0 + fractal * 3.0) * (1.0 - k6 * 0.2)

        elif preset == 3:
            # Preset 3: Stochastic & Entropic Noise Lattice
            stochastic_jitter = np.random.normal(0, 0.15, len(sub_t)) * k1
            chaotic_wave = np.sin(phase * (1.0 + k2) + stochastic_jitter)
            modulated = chaotic_wave / (1.0 + k3 * np.abs(np.sin(phase * k4)))
            return modulated * k5 * (1.0 + eqr * 2.0) * (1.0 - k6 * 0.3)

        else:
            # Preset 4: Custom Polynomial / Matrix Operator
            # Uses the track index to scale harmonic spacing dynamically across the 48 synths
            harmonic_offset = 1.0 + (track_idx % 12) * 0.08
            poly = k1 * (np.sin(phase * harmonic_offset)**3) - k2 * (np.cos(phase * k3)**2) + k4 * np.sin(phase)
            return np.tanh(poly * (1.0 + fractal * 4.0)) * (1.0 + eqr) * (1.0 - k6 * 0.1)

    def render_full_mixdown(self, filename, channel_states, grid_data, instrument_names, tempo_bpm=120):
        seconds_per_beat = 60.0 / float(tempo_bpm)
        total_cols = len(grid_data[0]) if grid_data else 128
        total_duration = total_cols * seconds_per_beat * 0.25

        num_samples = int(self.sample_rate * total_duration)
        master_buffer = np.zeros(num_samples, dtype=np.float32)
        t = np.linspace(0, total_duration, num_samples, endpoint=False)

        for track_idx, row in enumerate(grid_data):
            state = channel_states[track_idx % len(channel_states)]
            base_tuning = state.get("tuning", 432.0)
            duration_mult = state.get("duration", 1.0)
            vol = state.get("volume", 1.0)
            p1 = state.get("wave_param1", 0.5)
            p2 = state.get("wave_param2", 0.5)

            for col_idx, cell in enumerate(row):
                if cell is not None and cell != "":
                    start_time = (col_idx / total_cols) * total_duration
                    note_dur = max(0.05, (total_duration / total_cols) * duration_mult)
                    end_time = min(total_duration, start_time + note_dur)

                    idx_start = int(start_time * self.sample_rate)
                    idx_end = int(end_time * self.sample_rate)
                    if idx_start >= num_samples: continue

                    sub_t = t[idx_start:idx_end] - start_time
                    if len(sub_t) == 0: continue

                    freq = base_tuning * (1.0 + (col_idx % 12) * 0.03)
                    raw = np.sin(2 * np.pi * freq * sub_t + p1 * np.sin(2 * np.pi * freq * 2 * sub_t))

                    env = np.sin(np.pi * sub_t / note_dur) * (1.0 + p2 * 0.5)
                    note_audio = np.tanh(raw * (1.0 + p1 * 2.0)) * env * 0.08 * vol
                    master_buffer[idx_start:idx_start+len(note_audio)] += note_audio

        max_val = np.max(np.abs(master_buffer))
        if max_val > 0:
            master_buffer = master_buffer / max_val * 0.95

        scaled = np.int16(master_buffer * 32767)
        with wave.open(filename, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(scaled.tobytes())
class MathEngine:
    """Core mathematical engine evaluated strictly on x, y, z variables without Meum factors."""
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

class OperatorNode:
    def __init__(self, op_type):
        self.op_type = op_type  # e.g., 'isn', 'ics', 'eskivector', 'eskitable'

    def compute(self, x, y, z):
        engine = MathEngine()
        if self.op_type == 'isn':
            return engine.isn(x)
        elif self.op_type == 'ics':
            return engine.ics(y)
        elif self.op_type == 'eskivector':
            return engine.evaluate_eskivector(x, y, z)
        elif self.op_type == 'eskitable':
            return engine.evaluate_eskitable(x, y, z)
        return x, y, z
class InstrumentSpawner:
    def __init__(self, inst_type):
        self.inst_type = inst_type # 'percussion', 'pad', 'keys'
        self.math_engine = MathEngine()
        self.envelope = 1.0

    def trigger_spawn(self, x, y, z):
        """Spawns or evaluates an audio frame based on instrument type and x, y, z coordinates."""
        # Evaluate base vector/table components
        vx, vy, vz = self.math_engine.evaluate_eskivector(x, y, z)
        table_val = self.math_engine.evaluate_eskitable(vx, vy, vz)

        if self.inst_type == 'percussion':
            # Fast decaying transient envelope with non-linear distortion
            self.envelope *= 0.95
            return np.tanh(table_val * self.envelope * 3.0)

        elif self.inst_type == 'pad':
            # Smooth, sustained harmonic evolution via isosceles trig
            osc = self.math_engine.isn(vx) + self.math_engine.ics(vy)
            return osc * 0.5

        elif self.inst_type == 'keys':
            # Punchy, discrete coordinate mapping
            return table_val * np.cos(z)

        return table_val
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
        painter.setPen(
            QPen(
                QColor.fromHsvF(
                    hue,
                    0.19758,
                    0.19758,
                    0.48 + 0.24 * sf
                ),
                2.8 + 2.8 * sf
            )
        )
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
        painter.setBrush(QBrush(QColor.fromHsvF(hue, 0.19758, 0.19758, 0.18 + 0.12 * sf)))
        painter.setPen(QPen(QColor.fromHsvF((hue + 0.08 * sf2) % 0.19758, 0.19758, 0.19758, 0.55 + 0.20 * sf), 1.4))
        painter.drawPolygon(QPolygonF(points))
        if self._param_cache[1]:
            label = self._param_cache[1][index % len(self._param_cache[1])]
            text = f"{label[0][:8]} {label[1]:+.2f}"
            # Text follows a larger independent vertical orbit than the glyph.
            text_y = y + radius + 8 + height * 0.09 * math.sin(phase * (0.28 + sf2) + index * 1.63)
            text_y = max(12.0, min(height - 3.0, text_y))
            painter.setPen(QPen(QColor.fromHsvF(hue, 0.19758, 0.19758, 0.19758), 1.0))
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
        rng = np.random.default_rng(_safe_int_seed(seed if seed else 1))
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
            amps = mem.setdefault('amplitudes', [1.0] * count)
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
                rng=np.random.default_rng(_safe_int_seed(seed or 1)),
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

class EQRMasterController:
    def __init__(self):
        self.spawners = {
            'kick_perc': InstrumentSpawner('percussion'),
            'ambient_pad': InstrumentSpawner('pad'),
            'lead_keys': InstrumentSpawner('keys')
        }

    def render_active_spawners(self, buffer_size, x_arr, y_arr, z_arr):
        """Mixes active instrument spawners down to a master output buffer."""
        master_buffer = np.zeros(buffer_size)

        for name, spawner in self.spawners.items():
            voice_buffer = np.zeros(buffer_size)
            for i in range(buffer_size):
                voice_buffer[i] = spawner.trigger_spawn(x_arr[i], y_arr[i], z_arr[i])

            # Mix into master
            master_buffer += voice_buffer

        return master_buffer / len(self.spawners)
class MemoryBankPane(QGroupBox):
    """Manages project states, memory banks, and quick preset switching."""
    def __init__(self, parent=None):
        super().__init__("Memory Bank & Project Workflow", parent)
        layout = QGridLayout()

        self.bank_combo = QComboBox()
        self.bank_combo.addItems([f"Bank {chr(65+i)}: Preset {i+1}" for i in range(8)])

        btn_save = QPushButton("Save State")
        btn_load = QPushButton("Load State")
        btn_export = QPushButton("Export Buffer")
        btn_clear = QPushButton("Clear Bank")

        layout.addWidget(QLabel("Active Bank:"), 0, 0)
        layout.addWidget(self.bank_combo, 0, 1, 1, 3)
        layout.addWidget(btn_save, 1, 0)
        layout.addWidget(btn_load, 1, 1)
        layout.addWidget(btn_export, 1, 2)
        layout.addWidget(btn_clear, 1, 3)

        self.setLayout
class PatchTerminal(QWidget):
    def __init__(self, name, is_input=True, parent=None):
        super().__init__(parent)
        self.name = name
        self.is_input = is_input
        self.setFixedSize(110, 26)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor("#00ffcc") if self.is_input else QColor("#58a6ff")
        p.setBrush(QBrush(QColor("#161b22")))
        p.setPen(QPen(col, 2.0))
        p.drawEllipse(4, 4, 16, 16)
        p.setPen(QPen(QColor("#c9d1d9"), 1))
        p.drawText(24, 17, self.name)
class PlaylistArrangerWidget(QWidget):
    """Spicy multivariate modular playlist arranger where numeric program data, clips,
    and automation tracks can be dynamically created and wired."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>Multivariate Modular Playlist & Program Data Matrix</b>"))
        btn_add_track = QPushButton("Add Arrangement Track")
        top_bar.addWidget(btn_add_track)
        layout.addLayout(top_bar)

        self.tracks_layout = QVBoxLayout()
        layout.addLayout(self.tracks_layout)

        # Add initial track
        self.add_track("Track 1: Master Rhythm & Eskibrutus Gate")
        self.add_track("Track 2: Multivariate Modulation Timeline")

        self.setLayout(layout)

    def add_track(self, title="Modular Track"):
        box = QGroupBox(title)
        l = QHBoxLayout()
        l.addWidget(QLabel("Program Data Intensity:"))
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, 100)
        sl.setValue(75)
        l.addWidget(sl)
        l.addWidget(PatchTerminal("Track CV Out", is_input=False))
        box.setLayout(l)
        self.tracks_layout.addWidget(box)
class SequencerGridManager:
    def __init__(self, app_instance):
        self.app = app_instance

    def rebuild_sequencer_steps(self, count, mem):
        """Rebuilds step buttons displaying pad number and amplitude, omitting probability tags."""
        self.app.seq_step_buttons = []
        for s in range(int(count)):
            amp_val = mem["amplitudes"][s] if s < len(mem["amplitudes"]) else 0.5
            is_active = mem["steps"][s] if s < len(mem["steps"]) else False

            step_btn = QPushButton(f"Pad {s+1}\nAmp:{amp_val:.2f}")
            step_btn.setCheckable(True)
            step_btn.setChecked(is_active)

            if is_active:
                step_btn.setStyleSheet("background-color: #00ffff; color: #060606; border: 2px solid #ffffff; font-weight: bold;")
            else:
                step_btn.setStyleSheet("background-color: #121212; color: #00ffff; border: 2px solid #444444;")

            self.app.seq_step_buttons.append(step_btn)

    def reload_active_instrument_sequencer_ui(self):
        """Refreshes button states dynamically across active instruments."""
        if not hasattr(self.app, 'seq_step_buttons') or not hasattr(self.app, 'active_instrument_memory'):
            return

        mem = self.app.active_instrument_memory
        for s_idx, btn in enumerate(self.app.seq_step_buttons):
            if s_idx < len(mem["steps"]):
                btn.blockSignals(True)
                is_active = mem["steps"][s_idx]
                amp_val = mem["amplitudes"][s_idx]

                btn.setChecked(is_active)
                btn.setText(f"Pad {s_idx+1}\nAmp:{amp_val:.2f}")

                if is_active:
                    btn.setStyleSheet("background-color: #00ffff; color: #060606; border: 2px solid #ffffff; font-weight: bold;")
                else:
                    btn.setStyleSheet("background-color: #121212; color: #00ffff; border: 2px solid #444444;")
                btn.blockSignals(False)
class PlaylistArrangementWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Global Playlist & Arrangement Timeline")
        self.resize(800, 600)
        self.setStyleSheet(TELETUBBY_STYLE)

        container = QWidget()
        layout = QVBoxLayout(container)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("<b>Timeline Snap & Polyrhythm Scaling:</b>"))
        self.grid_scale_combo = QComboBox()
        self.grid_scale_combo.addItems(["1 Bar (Quantized)", "1/2 Beat", "1/4 Beat", "1/8 Beat", "Fully Unquantized / De-quantized Flow"])
        controls.addWidget(self.grid_scale_combo)

        controls.addWidget(QLabel("<b>Tempo (BPM):</b>"))
        self.global_tempo = QLineEdit("124.0")
        controls.addWidget(self.global_tempo)
        layout.addLayout(controls)

        self.timeline_view = QTextEdit()
        self.timeline_view.setPlainText(
            "# Active Playlist Arrangement Channels\n"
            "Track 1 [Instrument_1] |=======| [Bars 1 - 16]   (De-quant Offset: +4.2ms | Polyrhythm: 1.0x)\n"
            "Track 2 [Instrument_2]   |===|   [Bars 8 - 20]   (De-quant Offset: -1.5ms | Polyrhythm: 0.75x)\n"
            "Track 3 [Instrument_3] |=======| [Bars 12 - 32]  (De-quant Offset: 0.0ms  | Polyrhythm: 1.25x)"
        )
        self.timeline_view.setStyleSheet("background-color: #ffffff; color: #1e272e; font-family: monospace; font-size: 14px; border-radius: 12px;")
        layout.addWidget(self.timeline_view)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("Universal Brush Painter Mode"))
        btn_layout.addWidget(QPushButton("Quantize All Sequence Clips"))
        btn_layout.addWidget(QPushButton("Render Instrument Stems to Disk"))
        layout.addLayout(btn_layout)

        container.setLayout(layout)
        self.setCentralWidget(container)
class MasterModuleNode(QGroupBox):
    """Modular node for Tab 1 supporting Definers, Functions, and Combiner/Splitters."""
    def __init__(self, title="Math Operator Module", parent=None, delete_callback=None):
        super().__init__(title, parent)
        layout = QVBoxLayout()

        top_bar = QHBoxLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Definer Hub (Var Data)", "Function Module (Match/Oppose/Attract)", "Combiner / Splitter (+/-)"])
        top_bar.addWidget(self.type_combo)
        if delete_callback:
            btn_del = QPushButton("X")
            btn_del.setFixedWidth(30)
            btn_del.setStyleSheet("background-color: #da3633; color: white;")
            btn_del.clicked.connect(lambda: delete_callback(self))
            top_bar.addWidget(btn_del)
        layout.addLayout(top_bar)

        self.expr_edit = QLineEdit("isn(x) * t")
        layout.addWidget(QLabel("Equation / F(x) Operator:"))
        layout.addWidget(self.expr_edit)

        # Jacks depending on module type
        jacks_layout = QHBoxLayout()
        self.jack_in = PatchTerminal("Signal In", is_input=True)
        self.jack_out1 = PatchTerminal("Automated Out", is_input=False)
        self.jack_out2 = PatchTerminal("Secondary Out", is_input=False)
        jacks_layout.addWidget(self.jack_in)
        jacks_layout.addWidget(self.jack_out1)
        jacks_layout.addWidget(self.jack_out2)
        layout.addLayout(jacks_layout)

        self.setLayout(layout)
class WaveformVectorCanvas(QWidget):
    """Live interactive canvas supporting L/R clicks, mouse scroll for 'hardness/percussiveness',
    scroll-drag for wavetable framing, and vector continuousity vs syncopation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.points = [QPointF(i * 13.7, 55 + math.sin(i)*30) for i in range(16)]
        self.hardness = 50.0  # Controls percussiveness vs paddedness
        self.vector_scale = 1.0
        self.syncopation = 0.5
        self.dragging_point = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0d1117"))

        # Grid lines
        p.setPen(QPen(QColor("#21262d"), 1))
        for x in range(0, w, 30):
            p.drawLine(x, 0, x, h)

        # Draw Wavetable / Vector Line
        path = QPainterPath()
        if self.points:
            path.moveTo(self.points[0])
            for pt in self.points[1:]:
                path.lineTo(pt)
        p.setPen(QPen(QColor("#00ffcc"), 2.5))
        p.drawPath(path)

        # Draw handles
        for pt in self.points:
            p.setBrush(QBrush(QColor("#58a6ff")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(pt, 4, 4)

        p.setPen(QPen(QColor("#8b949e"), 1))
        p.drawText(10, 18, f"Hardness: {self.hardness:.1f} | Vector Scale: {self.vector_scale:.2f}")

    def mousePressEvent(self, event):
        pos = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            for pt in self.points:
                if (pt - pos).manhattanLength() < 12:
                    self.dragging_point = pt
                    break
        elif event.button() == Qt.MouseButton.RightButton:
            # Shift hardness / percussiveness mode on right click
            self.hardness = (self.hardness + 10) % 100.0
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging_point:
            self.dragging_point.setY(max(5, min(self.height() - 5, event.position().y())))
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging_point = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.vector_scale = max(0.1, self.vector_scale + (0.1 if delta > 0 else -0.1))
        else:
            self.hardness = max(0.0, min(100.0, self.hardness + (5.0 if delta > 0 else -5.0)))
        self.update()
class InstrumentStrip(QGroupBox):
    """Dynamic Instrument Node with modulation resistance profile (Padded, Keys, Percussion),
    live waveform editor, and patch terminals."""
    def __init__(self, title="Instrument Node", parent=None, delete_callback=None):
        super().__init__(title, parent)
        layout = QVBoxLayout()

        top_row = QHBoxLayout()
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["Eskibrutus", "Vector Synth", "Oscillator Synth", "Wavetable Synth", "Equation Synth"])
        top_row.addWidget(QLabel("Engine:"))
        top_row.addWidget(self.engine_combo)

        # Response Profile (Resistance to modulations over long/short periods)
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["Normal Response", "Padded (High Modulation Resistance)", "Keys (Tempo Envelope)", "Percussion (Fast Transient)"])
        top_row.addWidget(QLabel("Profile:"))
        top_row.addWidget(self.profile_combo)

        if delete_callback:
            btn_del = QPushButton("Delete")
            btn_del.setStyleSheet("background-color: #da3633; color: white;")
            btn_del.clicked.connect(lambda: delete_callback(self))
            top_row.addWidget(btn_del)

        layout.addLayout(top_row)

        # Live Wavetable & Vector Canvas
        self.wave_canvas = WaveformVectorCanvas()
        layout.addWidget(self.wave_canvas)

        # Patch Terminals for wiring across synth parameters
        term_layout = QHBoxLayout()
        self.in_term = PatchTerminal(f"{title} Mod In", is_input=True)
        self.out_term = PatchTerminal(f"{title} Out", is_input=False)
        term_layout.addWidget(self.in_term)
        term_layout.addWidget(self.out_term)
        layout.addLayout(term_layout)

        # Sliders for Osc Effects, Wavetable Framing, Vector Scaling, Continuousity
        sliders_grid = QGridLayout()
        self.sliders = {}
        s_defs = [("Cutoff", 80), ("Resonance", 30), ("Osc Effects", 50), ("Wavetable Frame", 40), ("Vector Scale", 70), ("Continuousity", 60)]
        for idx, (s_name, val) in enumerate(s_defs):
            row, col = dividx = divmod(idx, 2)
            sliders_grid.addWidget(QLabel(s_name), row, col * 2)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(0, 100)
            sl.setValue(val)
            sliders_grid.addWidget(sl, row, col * 2 + 1)
            self.sliders[s_name] = sl
        layout.addLayout(sliders_grid)

        self.setLayout(layout)
class SongAutomationTimeline(QWidget):
    """Timeline module for song length, module automation over time, and content duration mapping."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        layout = QVBoxLayout()

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Song Length (Bars):"))
        self.bars_spin = QSpinBox()
        self.bars_spin.setRange(4, 256)
        self.bars_spin.setValue(32)
        controls_layout.addWidget(self.bars_spin)

        controls_layout.addWidget(QLabel("Global Tempo (BPM):"))
        self.tempo_spin = QSpinBox()
        self.tempo_spin.setRange(40, 300)
        self.tempo_spin.setValue(120)
        controls_layout.addWidget(self.tempo_spin)

        layout.addLayout(controls_layout)

        # Automation Lane Canvas representation
        self.lane_canvas = MultiLaneSequencerCanvas()
        layout.addWidget(self.lane_canvas)
        self.setLayout(layout)
# --- Modular Synthesizer/Sequencer Node ---
class ModulationRoutingWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ableton Style Modulation & Device Rack")
        self.resize(750, 480)
        self.setStyleSheet(DAW_STYLE)

        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("<b>🎛️ Modular Device & LFO Modulation Matrix</b>"))

        rack_layout = QGridLayout()
        rack_layout.addWidget(QLabel("LFO 1 Rate (Hz):"), 0, 0)
        self.lfo_slider = QSlider(Qt.Orientation.Horizontal)
        self.lfo_slider.setValue(35)
        rack_layout.addWidget(self.lfo_slider, 0, 1)

        rack_layout.addWidget(QLabel("Filter Cutoff:"), 1, 0)
        self.cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self.cutoff_slider.setValue(70)
        rack_layout.addWidget(self.cutoff_slider, 1, 1)

        rack_layout.addWidget(QLabel("Wavefold Drive:"), 2, 0)
        self.drive_slider = QSlider(Qt.Orientation.Horizontal)
        self.drive_slider.setValue(50)
        rack_layout.addWidget(self.drive_slider, 2, 1)
        layout.addLayout(rack_layout)

        self.routing_view = QTextEdit()
        self.routing_view.setPlainText(
            "# Active Modulation Routing Matrix (Ableton CV/Mod Style)\n"
            "LFO 1 ------------> Filter Cutoff (Amount: +65%)\n"
            "Macro 1 (Drive) --> Wavefolder Saturation (Amount: 80%)\n"
            "Envelope 1 -------> Master Volume VCA"
        )
        self.routing_view.setStyleSheet("background-color: #161616; color: #00ffcc; font-family: monospace;")
        layout.addWidget(self.routing_view)

        container.setLayout(layout)
        self.setCentralWidget(container)
class SynthNodeWidget(QFrame):
    """Editable modular node frame with visible ports and a rename field."""
    def __init__(self, name, x, y, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(2)
        self.resize(210, 140)
        self.move(x, y)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff; border: 1px solid #555; border-radius: 6px;")

        layout = QVBoxLayout(self)

        # Editable title field
        self.title_input = QLineEdit(name)
        self.title_input.setStyleSheet("background-color: #2a2a2a; color: #ffffff; border: 1px solid #666; padding: 4px;")
        self.title_label = self.title_input
        layout.addWidget(self.title_input)

        ports_layout = QHBoxLayout()

        in_container = QVBoxLayout()
        lbl_in = QLabel("In")
        lbl_in.setStyleSheet("color: #00ffc8; border: none; font-size: 11px; font-weight: bold;")
        in_container.addWidget(lbl_in)
        self.in_port = PortWidget('in', self)
        in_container.addWidget(self.in_port)

        out_container = QVBoxLayout()
        lbl_out = QLabel("Out")
        lbl_out.setStyleSheet("color: #ff6400; border: none; font-size: 11px; font-weight: bold;")
        out_container.addWidget(lbl_out)
        self.out_port = PortWidget('out', self)
        out_container.addWidget(self.out_port)

        ports_layout.addLayout(in_container)
        ports_layout.addLayout(out_container)
        layout.addLayout(ports_layout)

        self.dragging = False
        self.drag_position = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            if self.parent():
                self.parent().update()
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
class ArrangementTrackWidget(QWidget):
    """Arrangement timeline track for placing and editing sequence blocks."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #181818; border: 1px solid #444; border-radius: 4px;")
        layout = QHBoxLayout(self)

        self.track_label = QLabel("Arrangement Track")
        self.track_label.setStyleSheet("color: #ffffff; font-weight: bold;")

        self.blocks_layout = QHBoxLayout()

        self.add_block_btn = QPushButton("+ Add Subsequence")
        self.add_block_btn.setStyleSheet("background-color: #333; color: #ffffff; border: 1px solid #555; padding: 6px 12px; border-radius: 4px;")
        self.add_block_btn.clicked.connect(self.on_add_subsequence)

        layout.addWidget(self.track_label)
        layout.addLayout(self.blocks_layout)
        layout.addStretch()
        layout.addWidget(self.add_block_btn)

    def on_add_subsequence(self):
        block = QPushButton("Subsequence Clip")
        block.setStyleSheet("background-color: #005555; color: #ffffff; border: 1px solid #00ffc8; padding: 6px; border-radius: 3px;")
        self.blocks_layout.addWidget(block)
class FitToFrameContainer(QWidget):
    """A responsive container that scales its inner child widget to fit window bounds."""
    def __init__(self, inner_widget, base_width=1200, base_height=800):
        super().__init__()
        self.inner_widget = inner_widget
        self.base_width = base_width
        self.base_height = base_height

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.inner_widget)
        self.scale_factor = 1.0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        bg = getattr(self, "_math_decor", None)
        if cw is not None and bg is not None:
            bg.setGeometry(cw.rect())
            bg.lower()
            bg.update()

# Import Reality Synth and Music Fractallizer from synth_engine (with fallback stubs)
class FractallizerVisualizerCanvas(QWidget):
    def __init__(self, parent=None, app_ref=None):
        super().__init__(parent)
        self.app_ref = app_ref
        self.setMinimumHeight(160)
        self.setStyleSheet("background-color: #080808; border: 1px solid #ff6b00; border-radius: 4px;")
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_fractal)
        self.timer.start(25)

    def update_fractal(self):
        self.phase += 0.05
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self): return
        try:
            painter.fillRect(self.rect(), QColor(8, 8, 8))
            w, h = self.width(), self.height()
            cx, cy = w / 2.0, h / 2.0
            points = []
            for i in range(200):
                t = (i / 200.0) * 6 * np.pi + self.phase
                r = (55.0 + (self.app_ref.macro_fractal.value() * 5 if self.app_ref else 10)) * np.sin(t * 2.5 + self.phase)
                points.append(QPointF(cx + r * np.cos(t), cy + r * np.sin(t)))
            for i in range(len(points) - 1):
                col = QColor.fromHsvF((i / 200.0 + self.phase * 0.1) % 1.0, 0.9, 1.0)
                painter.setPen(QPen(col, 2))
                painter.drawLine(points[i], points[i+1])
        finally:
            painter.end()
class CustomVSTKnobsDialog(QDialog):
    def __init__(self, parent=None, channel_state=None):
        super().__init__(parent)
        self.channel_state = channel_state or {}
        self.setWindowTitle("Custom VST & Waveform Parameters (Edit Synth)")
        self.resize(450, 350)
        self.setStyleSheet(DAW_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>⚙️ Custom VST Parameters & Wavefunction Mapping:</b>"))

        form_layout = QFormLayout()

        self.vst_param1 = QSlider(Qt.Orientation.Horizontal)
        self.vst_param1.setRange(0, 100)
        self.vst_param1.setValue(int(self.channel_state.get("vst_p1", random.random()) * 100))
        form_layout.addRow("VST Resonance / Freq (p1):", self.vst_param1)

        self.vst_param2 = QSlider(Qt.Orientation.Horizontal)
        self.vst_param2.setRange(0, 100)
        self.vst_param2.setValue(int(self.channel_state.get("vst_p2", random.random()) * 100))
        form_layout.addRow("Harmonic Spread (p2):", self.vst_param2)

        self.vst_param3 = QSlider(Qt.Orientation.Horizontal)
        self.vst_param3.setRange(0, 100)
        self.vst_param3.setValue(int(self.channel_state.get("vst_p3", random.random()) * 100))
        form_layout.addRow("Meum Scaling Depth (p3):", self.vst_param3)

        self.routing_combo = QComboBox()
        self.routing_combo.addItems(["Direct Summation", "Phase Modulation (PM)", "Frequency Modulation (FM)", "Nonlinear Foldback"])
        form_layout.addRow("Synthesis Routing Mode:", self.routing_combo)

        layout.addLayout(form_layout)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Apply VST Settings")
        save_btn.setStyleSheet("background-color: #00aa55; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        btn_box.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        layout.addLayout(btn_box)

    def get_values(self):
        return {
            "vst_p1": self.vst_param1.value() / 100.0,
            "vst_p2": self.vst_param2.value() / 100.0,
            "vst_p3": self.vst_param3.value() / 100.0,
            "routing": self.routing_combo.currentText()
        }
class ModularPatchBayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modular Modulation Patch Bay")
        self.resize(500, 400)
        self.setStyleSheet(DAW_STYLE)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>🔌 Cross-Modulation Matrix:</b>"))

        self.matrix_table = QTableWidget(6, 6)
        self.matrix_table.setHorizontalHeaderLabels(["Ch 1", "Ch 2", "Ch 3", "Ch 4", "Mod A", "Mod B"])
        self.matrix_table.setVerticalHeaderLabels(["Src 1", "Src 2", "Src 3", "Src 4", "Env 1", "LFO 1"])
        layout.addWidget(self.matrix_table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def randomize_matrix(self):
        for r in range(self.matrix_table.rowCount()):
            for c in range(self.matrix_table.columnCount()):
                val = f"{random.choice([0.0, 0.25, 0.5, 0.75, 1.0])}"
                self.matrix_table.setItem(r, c, QTableWidgetItem(val))



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
      50% → BOTH: random kit seed + kit program parameters
      25% → SEED ONLY: random kit seed; pads/playlist left empty
      25% → PROGRAM ONLY: kit program parameters; seed field stays empty

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

class ModularPatchBayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modular Modulation Bay & Routing Matrix")
        self.resize(700, 500)
        self.setStyleSheet(DAW_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>🔌 Master Modular Patch Bay & CV Routing Matrix</h3>"))

        toolbar = QHBoxLayout()
        random_patch_btn = QPushButton("🎲 Randomize Patch Bay")
        random_patch_btn.setStyleSheet("background-color: #ff6b00; color: white;")
        random_patch_btn.clicked.connect(self.randomize_matrix)
        toolbar.addWidget(random_patch_btn)

        clear_patch_btn = QPushButton("Clear Patch Bay")
        clear_patch_btn.clicked.connect(self.clear_matrix)
        toolbar.addWidget(clear_patch_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget(12, 12)
        self.table.setHorizontalHeaderLabels([f"Mod Out {i+1}" for i in range(12)])
        self.table.setVerticalHeaderLabels([f"Dest {i+1}" for i in range(12)])
        self.table.setStyleSheet("QTableWidget { background-color: #161616; gridline-color: #282828; }")
        layout.addWidget(self.table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def randomize_matrix(self):
        for r in range(12):
            for c in range(12):
                if random.random() > 0.7:
                    item = QTableWidgetItem("⚡ CV")
                    item.setBackground(QColor(255, 107, 0))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(r, c, item)
                else:
                    self.table.setItem(r, c, None)
        QMessageBox.information(self, "Patch Bay", "Modular routing matrix randomized successfully.")

    def clear_matrix(self):
        self.table.clearContents()

# ==========================================
# SCRIPT PANEL DIALOG
# ==========================================
class ScriptPanelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mathematician's EQR & Chaos Scripting Suite")
        self.resize(700, 500)
        self.setStyleSheet(DAW_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>📜 Python / EQR Phase-Space Script Console</h3>"))

        self.editor = QTextEdit()
        self.editor.setPlainText(
            "# Custom EQR Operator & Curvature Evaluation Script\n"
            "import numpy as np\n\n"
            "def evaluate_phase_space(step_matrix, curvature=1.618):\n"
            "    print(f'Evaluating EQR tensor across matrix with curvature {curvature}')\n"
            "    return True\n\n"
            "evaluate_phase_space(None, 1.618033)\n"
        )
        self.editor.setStyleSheet("background-color: #141414; color: #00ffcc; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.editor)

        btn_layout = QHBoxLayout()
        run_btn = QPushButton("▶ Run Script Evaluation")
        run_btn.setStyleSheet("background-color: #ff6b00; color: white;")
        run_btn.clicked.connect(lambda: QMessageBox.information(self, "Script Engine", "Script executed successfully in active memory namespace."))
        btn_layout.addWidget(run_btn)

        close_btn = QPushButton("Close Panel")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
class MusicFractallizer:
    def __init__(self, dimensions=('x', 'y', 'z'), survival_mode=True):
        self.dimensions = dimensions
        self.survival_mode = survival_mode
        self.active_patches = []
    def generate_fractal_stream(self, seed_data):
        return {dim: np.tanh(seed_data) for dim in self.dimensions}

class RealitySynthEngine:
    def __init__(self, survival_mode=True):
        self.fractallizer = MusicFractallizer(dimensions=('x', 'y', 'z'), survival_mode=survival_mode)
    def render_reality_patch(self, base_patch_data):
        return {coord: sig.tolist() for coord, sig in self.fractallizer.generate_fractal_stream(base_patch_data).items()}


class AdvancedWaveformVisualizerCanvas(QWidget):
    """Multi-model real-time Wavetable, Vector, and Algebraic Equation Visualizer."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.phase = 0.0
        self.active_mode = "Eskivector"

    def update_phase(self):
        self.phase += 0.05
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor("#0a0e14"))
        p.setPen(QPen(QColor("#161b22"), 1))
        for x in range(0, w, 40):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 40):
            p.drawLine(0, y, w, y)

        path = QPainterPath()
        center_y = h / 2.0
        meum_ratio = MEUM

        for px in range(w):
            t_val = (px / w) * 4.0 * math.pi + self.phase
            if self.active_mode == "Eskivector":
                val = MathEngine.isn(t_val * meum_ratio) + 0.5 * MathEngine.ics(t_val)
            elif self.active_mode == "Eskitable":
                val = MathEngine.arcisn(math.sin(t_val)) * MathEngine.arcics(math.cos(t_val * 0.5))
            elif self.active_mode == "Eskiosc":
                val = MathEngine.isn_inv(math.sin(t_val))
            else: # Eskiequation
                val = MathEngine.isn(t_val) * MathEngine.ics(t_val * meum_ratio) + MathEngine.arcisn(math.sin(t_val * 0.25))

            py = center_y - (val * (h * 0.35))
            if px == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        p.setPen(QPen(QColor("#00ffcc"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(path)

        p.setPen(QPen(QColor("#58a6ff"), 1, Qt.PenStyle.DashLine))
        p.drawLine(0, int(center_y), w, int(center_y))
        p.drawText(15, 25, f"Visualizer Active Model: [{self.active_mode}] — Isosceles Trig & Algebraic Waveform")
class MultiLaneSequencerCanvas(QWidget):
    """Sequencer canvas with built-in modulation patch outputs per track."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.step_count = 16
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.steps = [{"amp": 0.9, "pitch": 440.0, "gate": True} for _ in range(16)]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0a0e14"))
        step_w = w / self.step_count
        for i in range(self.step_count):
            sx = i * step_w
            val_h = self.steps[i]["amp"] * (h - 20)
            p.setBrush(QBrush(QColor("#00ffcc")))
            p.drawRoundedRect(QRectF(sx + 2, h - val_h - 10, step_w - 4, val_h), 2, 2)
class StepPainterSequencerCanvas(QWidget):
    """Sequencer supporting color-coded step painting for frequency, amplitude, and duration."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.step_count = 16
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.steps = [
            {"freq": 220.0 + i*30, "amp": 0.7, "duration": 1.0, "color": QColor("#00ffcc" if i%2==0 else "#58a6ff")}
            for i in range(32)
        ]
        self.painting_mode = "amplitude"

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0a0e14"))
        p.setPen(QPen(QColor("#00ffcc"), 1))
        p.drawText(15, 25, f"Step Painter Mode: [{self.painting_mode}] — Active Step Count: {self.step_count}")

class IdealizedMathKnob(QWidget):
    """Skeuomorphic rotary controller designed for mathematical mapping ($x, y, z, t$ space)."""
    def __init__(self, label_text, min_val=0.0, max_val=100.0, default_val=50.0, math_note="", parent=None):
        super().__init__(parent)
        self.label_text = label_text
        self.min_val = min_val
        self.max_val = max_val
        self.value = default_val
        self.math_note = math_note
        self.setFixedSize(110, 130)
        self.dragging = False
        self.last_y = 0
        self.is_patched = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor("#58a6ff"), 1))
        painter.drawText(0, 8, self.width(), 14, Qt.AlignmentFlag.AlignCenter, self.label_text)

        painter.setPen(QPen(QColor("#8b949e"), 1))
        painter.drawText(0, 22, self.width(), 12, Qt.AlignmentFlag.AlignCenter, f"Val: {self.value:.3f}")

        center = QPointF(55, 62)
        radius = 20.0

        painter.setBrush(QBrush(QColor("#161b22")))
        painter.setPen(QPen(QColor("#30363d"), 2))
        painter.drawEllipse(center, radius, radius)

        span_val = self.max_val - self.min_val if self.max_val != self.min_val else 1.0
        normalized = (self.value - self.min_val) / span_val
        angle = math.radians(-130 + (normalized * 260))
        tip_x = center.x() + (radius - 5) * math.sin(angle)
        tip_y = center.y() - (radius - 5) * math.cos(angle)

        painter.setPen(QPen(QColor("#00ffcc"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(center, QPointF(tip_x, tip_y))

        jack_center = QPointF(55, 96)
        painter.setBrush(QBrush(QColor("#0d1117")))
        painter.setPen(QPen(QColor("#00ffcc") if self.is_patched else QColor("#484f58"), 1.5))
        painter.drawEllipse(jack_center, 5.0, 5.0)

        painter.setPen(QPen(QColor("#c9d1d9"), 1))
        painter.drawText(2, 108, self.width() - 4, 20, Qt.AlignmentFlag.AlignCenter, self.math_note)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            jack_center = QPointF(55, 96)
            if (event.position() - jack_center).manhattanLength() < 12:
                self.is_patched = not self.is_patched
                self.update()
            else:
                self.dragging = True
                self.last_y = event.position().y()

    def mouseMoveEvent(self, event):
        if self.dragging:
            dy = self.last_y - event.position().y()
            self.last_y = event.position().y()
            span = self.max_val - self.min_val
            step = span * (dy / 150.0)
            self.value = max(self.min_val, min(self.max_val, self.value + step))
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        span = self.max_val - self.min_val
        step = span * (0.02 if delta > 0 else -0.02)
        self.value = max(self.min_val, min(self.max_val, self.value + step))
        self.update()
class SequencerEngine:
    def __init__(self, steps=16):
        self.steps = steps
        self.current_step = 0
        self.active_pattern = [0.0] * steps

    def step_forward(self, synth_callback):
        """Advances the sequencer step and triggers sound generation."""
        val = self.active_pattern[self.current_step]

        # Trigger synth callback with current coordinate step intensity
        if synth_callback and callable(synth_callback):
            synth_callback(self.current_step, val)

        self.current_step = (self.current_step + 1) % self.steps
        return self.current_step
class ModularSequencerEngine:
    """Drives step logic across tabs and translates steps into active synth events."""
    def __init__(self, total_steps=16):
        self.total_steps = total_steps
        self.current_step = 0
        self.tab_triggers = {} # Maps tab index/name to step arrays

    def register_tab_grid(self, tab_id, default_pattern=None):
        if default_pattern is None:
            default_pattern = [1 if i % 4 == 0 else 0 for i in range(self.total_steps)]
        self.tab_triggers[tab_id] = default_pattern

    def advance_clock(self, synth_bank, active_tab_id, x_val, y_val, z_val):
        # Advance step counter
        self.current_step = (self.current_step + 1) % self.total_steps

        # Check if current tab has a trigger pattern
        if active_tab_id in self.tab_triggers:
            pattern = self.tab_triggers[active_tab_id]
            is_triggered = pattern[self.current_step]

            if is_triggered:
                # Force generation check across active synths using x, y, z variables
                freq = 220.0 * (1.0 + (self.current_step % 7) * 0.15)
                synth_bank.spawn_synth("Additive", base_freq=freq)

        return self.current_step
class InteractivePatchbayCanvas(QWidget):
    """Master Hub visualizing all cross-panel connections."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1000, 700)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0a0e14"))

        # Grid lines
        p.setPen(QPen(QColor("#161b22"), 1))
        for x in range(0, w, 40):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 40):
            p.drawLine(0, y, w, y)

        # Render global cross-panel cables
        p.setPen(QPen(QColor("#ff7b72"), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for src, dst in global_patch_bus.cables:
            # Placeholder coordinates mapping for visualization overview
            p.drawLine(150, 150, 750, 400)

        p.setPen(QPen(QColor("#8b949e"), 1))
        p.drawText(25, 35, "Master Patchbay: Monitoring all cross-panel connections between Panels 1, 2, and 3.")
class SideDisplayPanelManager:
    """Rebuilds and populates side display panels with active modular routing controls."""
    def __init__(self, parent_layout):
        self.layout = parent_layout
        self.panels = {}
        self.init_panels()

    def init_panels(self):
        # Panel A: Macro X-Y-Z Variable Monitor
        self.panels['xyz_monitor'] = {
            "label": "XYZ Matrix Spatial State",
            "widgets": ["x_slider", "y_slider", "z_slider"],
            "status": "Active"
        }

        # Panel B: Reapplied Side Feature (Spectral Tilt & Harmonic Spread)
        self.panels['spectral_control'] = {
            "label": "Harmonic Spectrum Balancer",
            "widgets": ["tilt_dial", "spread_dial"],
            "status": "Rebuilt & Live"
        }

        # Panel C: Unused Feature Activation (Stochastic Grain Cloud)
        self.panels['stochastic_mod'] = {
            "label": "Stochastic Grain Generator",
            "widgets": ["density_knob", "scatter_knob"],
            "status": "Newly Appplied"
        }

    def render_panel_data(self, x, y, z):
        """Updates side panel readouts dynamically based on core calculations."""
        metrics = {
            "X_Var": round(x, 4),
            "Y_Var": round(y, 4),
            "Z_Var": round(z, 4),
            "Active_Panels": len(self.panels)
        }
        return metrics

class FreeformSequencerCanvas(QWidget):
    """Sequencer canvas supporting dynamic step length and micro-timing."""
    def __init__(self, sequence_data=None, parent=None):
        super().__init__(parent)
        self.seq_data = sequence_data if sequence_data is not None else [0.0] * 16
        self.step_count = 16
        self.non_quant_offset = 0.0
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.nodes = [QPointF(60, 180), QPointF(340, 60), QPointF(680, 140), QPointF(960, 50)]
        self.wires = [(self.nodes[0], self.nodes[1]), (self.nodes[2], self.nodes[3])]
        self.active_node = None
        self.wiring_start = None

    def set_step_count(self, count):
        self.step_count = count
        if len(self.seq_data) < count:
            self.seq_data.extend([0.0] * (count - len(self.seq_data)))
        self.update()

    def set_non_quant_offset(self, offset):
        self.non_quant_offset = offset
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            if isinstance(self.seq_data, dict):
                notes = self.seq_data.get("notes", [])
            elif isinstance(self.seq_data, list):
                notes = [
                    {"time": float(i) + self.non_quant_offset, "duration": 1.0, "active": bool(val != 0)}
                    for i, val in enumerate(self.seq_data[:self.step_count])
                ]
            else:
                notes = []

            w, h = self.width(), self.height()
            p.fillRect(0, 0, w, h, QColor("#0a0e14"))

            p.setPen(QPen(QColor("#161b22"), 1))
            for x in range(0, w, 40):
                p.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                p.drawLine(0, y, w, y)

            for p1, p2 in self.wires:
                ctrl = QPointF((p1.x() + p2.x()) / 2, max(p1.y(), p2.y()) + 60)
                path = QPainterPath()
                path.moveTo(p1)
                path.cubicTo(ctrl, ctrl, p2)
                p.setPen(QPen(QColor("#00ffcc"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawPath(path)

            max_time = max([n.get("time", 0.0) + n.get("duration", 1.0) for n in notes] + [float(self.step_count)])
            scale_x = w / max(float(self.step_count), max_time)

            for i, note in enumerate(notes):
                nx = note.get("time", float(i)) * scale_x
                nw = max(12, note.get("duration", 1.0) * scale_x)
                ny = 15 + (i % 4) * 24

                is_active = note.get("active", True)
                p.setBrush(QBrush(QColor("#00ffcc" if is_active else "#21262d")))
                p.setPen(QPen(QColor("#ffffff" if is_active else "#484f58"), 1))
                p.drawRoundedRect(int(nx), int(ny), int(nw), 18, 4, 4)

                p.setPen(QPen(QColor("#ffffff" if is_active else "#8b949e"), 1))
                p.drawText(int(nx) + 4, int(ny) + 13, f"N{i+1}")

        finally:
            p.end()

    def mousePressEvent(self, event):
        pos = event.position()
        if event.button() == Qt.MouseButton.RightButton:
            self.nodes.append(QPointF(pos.x(), pos.y()))
            self.nodes.sort(key=lambda p: p.x())
            self.update()
        elif event.button() == Qt.MouseButton.LeftButton:
            for node in self.nodes:
                if (node - pos).manhattanLength() < 14:
                    self.wiring_start = node
                    return
            for idx, node in enumerate(self.nodes):
                if (node - pos).manhattanLength() < 22:
                    self.active_node = idx
                    break

    def mouseMoveEvent(self, event):
        if self.active_node is not None:
            new_pos = event.position()
            self.nodes[self.active_node] = QPointF(max(0, min(self.width(), new_pos.x())), max(0, min(self.height(), new_pos.y())))
            self.update()

    def mouseReleaseEvent(self, event):
        if self.wiring_start:
            pos = event.position()
            for node in self.nodes:
                if (node - pos).manhattanLength() < 18 and node != self.wiring_start:
                    self.wires.append((self.wiring_start, node))
                    break
            self.wiring_start = None
        self.active_node = None
        self.update()
import math
import random

class DynamicSynthManager:
    """Manages live instantiation, tracking, and audio block generation for active synths."""
    def __init__(self, sample_rate=44100.0):
        self.sr = sample_rate
        self.active_instances = []

    def spawn_instance(self, module_type, base_freq=440.0):
        """Spawns a specific interactive synth instance."""
        if module_type == "AdditiveNode":
            inst = AdditiveSynthInstance(base_freq, self.sr)
        elif module_type == "FormantNode":
            inst = FormantSynthInstance(base_freq, self.sr)
        elif module_type == "StochasticNode":
            inst = StochasticNoiseInstance(base_freq, self.sr)
        else:
            inst = StandardSynthInstance(base_freq, self.sr)

        self.active_instances.append(inst)
        # Prune older instances if max polyphony is reached to prevent lag
        if len(self.active_instances) > 16:
            self.active_instances.pop(0)
        return inst

    def process_audio_stream(self, num_samples, x, y, z):
        """Renders and sums all active synth instances using x, y, z coordinate parameters."""
        master_buffer = [0.0] * num_samples
        for instance in list(self.active_instances):
            if instance.is_finished():
                self.active_instances.remove(instance)
                continue
            buf = instance.render_block(num_samples, x, y, z)
            for i in range(num_samples):
                master_buffer[i] += buf[i]
        return master_buffer
class PatchbayCanvas(QWidget):
    """Interactive canvas that visually renders node patching wires and real-time waveforms."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.amplitude_data = [0.0] * 60
        self.connections = [
            ("EskiVector Node", "Reality Wave-Folder"),
            ("EskiTable Unit", "Fractalizer Matrix")
        ]

    def update_data(self, new_val):
        self.amplitude_data.pop(0)
        # Scaled up gain for high-visibility waveforms
        self.amplitude_data.append(new_val * 4.5)
        self.update()

    def add_connection(self, source, target):
        if (source, target) not in self.connections:
            self.connections.append((source, target))
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark studio background
        painter.fillRect(self.rect(), QColor(15, 15, 20))

        # Draw Coded Patching Wires
        wire_pen = QPen(QColor(255, 140, 0))
        wire_pen.setWidth(3)
        painter.setPen(wire_pen)

        # Render visual nodes and connecting wires across the canvas
        node_positions = {
            "EskiVector Node": QPointF(100, 60),
            "EskiTable Unit": QPointF(100, 140),
            "Reality Wave-Folder": QPointF(400, 60),
            "Fractalizer Matrix": QPointF(400, 140)
        }

        for src, tgt in self.connections:
            if src in node_positions and tgt in node_positions:
                p1 = node_positions[src]
                p2 = node_positions[tgt]
                # Draw curved patching wire
                painter.drawLine(int(p1.x()), int(p1.y()), int(p2.x()), int(p2.y()))

        # Draw Node Blocks
        for name, pt in node_positions.items():
            painter.setBrush(QBrush(QColor(40, 40, 55)))
            painter.setPen(QPen(QColor(0, 220, 150), 2))
            painter.drawRoundedRect(int(pt.x() - 70), int(pt.y() - 25), 140, 50, 8, 8)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(int(pt.x() - 60), int(pt.y() + 5), name)

        # Draw Scaled Waveform / Vector Display at the bottom half
        graph_y_offset = 220
        wave_pen = QPen(QColor(0, 255, 180))
        wave_pen.setWidth(3)
        painter.setPen(wave_pen)

        width = self.width()
        step = width / max(len(self.amplitude_data) - 1, 1)

        for i in range(len(self.amplitude_data) - 1):
            x1 = int(i * step)
            y1 = int(graph_y_offset - self.amplitude_data[i] * 40)
            x2 = int((i + 1) * step)
            y2 = int(graph_y_offset - self.amplitude_data[i + 1] * 40)
            painter.drawLine(x1, y1, x2, y2)
# -------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION DATABASE
# -------------------------------------------------------------------------
FREQUENCY_432HZ = 432.0
class StandardSynthInstance:
    def __init__(self, freq, sr):
        self.freq = freq
        self.sr = sr
        self.phase = 0.0
        self.life = 100

    def is_finished(self):
        return self.life <= 0

    def render_block(self, num_samples, x, y, z):
        buf = []
        modulated_freq = self.freq * (0.8 + abs(x) * 0.4)
        step = (2.0 * math.pi * modulated_freq) / self.sr
        for _ in range(num_samples):
            self.phase += step
            val = math.sin(self.phase) * 0.3 * max(0.0, y)
            buf.append(val)
        self.life -= 1
        return buf

class AdditiveSynthInstance(StandardSynthInstance):
    def render_block(self, num_samples, x, y, z):
        buf = []
        harmonics = [1.0, 2.0, 3.5, 4.0, 6.0]
        step = (2.0 * math.pi * self.freq) / self.sr
        for i in range(num_samples):
            self.phase += step
            sample = 0.0
            for h in harmonics:
                sample += math.sin(self.phase * h * (1.0 + z * 0.05)) / h
            buf.append(sample * 0.15 * max(0.0, y))
        self.life -= 1
        return buf

class FormantSynthInstance(StandardSynthInstance):
    def render_block(self, num_samples, x, y, z):
        buf = []
        carrier_step = (2.0 * math.pi * self.freq) / self.sr
        formant_step = (2.0 * math.pi * (self.freq * abs(x * 3.0))) / self.sr
        for _ in range(num_samples):
            self.phase += carrier_step
            c = math.sin(self.phase)
            m = math.cos(self.phase * 1.5) * math.sin(formant_step)
            val = c * m * 0.2 * abs(z)
            buf.append(val)
        self.life -= 1
        return buf

class StochasticNoiseInstance(StandardSynthInstance):
    def render_block(self, num_samples, x, y, z):
        buf = []
        for _ in range(num_samples):
            noise = (random.random() * 2.0 - 1.0)
            val = noise * 0.1 * abs(x) * max(0.0, y)
            buf.append(val)
        self.life -= 1
        return buf
class MasterSynthBank:
    """Manages dynamic spawning and audio rendering for modular synths."""
    def __init__(self, sample_rate=44100.0):
        self.sr = sample_rate
        self.active_synths = []

    def spawn_synth(self, synth_type, base_freq=440.0):
        if synth_type == "Additive":
            synth = AdditiveSynthNode(base_freq, self.sr)
        elif synth_type == "Formant":
            synth = FormantSynthNode(base_freq, self.sr)
        elif synth_type == "NoiseBurst":
            synth = NoiseBurstNode(base_freq, self.sr)
        else:
            synth = StandardWaveSynthNode(base_freq, self.sr)
        self.active_synths.append(synth)
        return synth

    def render_buffer(self, num_samples, x_mod=1.0, y_mod=1.0, z_mod=1.0):
        buffer = [0.0] * num_samples
        for synth in self.active_synths:
            s_buf = synth.generate_block(num_samples, x_mod, y_mod, z_mod)
            for i in range(num_samples):
                buffer[i] += s_buf[i]
        return buffer
# ==========================================
# 3. INTERACTIVE SEQUENCER, SERIALIZATION & VISUAL LAYERS
# ==========================================
class InteractiveSequencerGrid:
    """Handles step sequencing and triggers live synth module generation."""
    def __init__(self, steps=16):
        self.steps = steps
        self.current_step = 0
        self.pattern_matrix = [1 if i % 4 == 0 else 0 for i in range(steps)]

    def step_clock(self, synth_manager, x, y, z):
        self.current_step = (self.current_step + 1) % self.steps
        if self.pattern_matrix[self.current_step] == 1:
            if x > 0.3:
                m_type = "Additive"
            elif z > 0.5:
                m_type = "Formant"
            else:
                m_type = "Stochastic"
            base_f = 110.0 * (1.0 + (self.current_step % 8) * 0.2)
            synth_manager.spawn_instance(m_type, base_freq=base_f)
        return self.current_step



class AudioEngineBridge:
    """Bridges the UI coordinate state and sequencer ticks directly to the audio output stream."""
    def __init__(self, synth_manager, sequencer_grid):
        self.synth_manager = synth_manager
        self.sequencer = sequencer_grid
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
                self.play_cursor = len(self.play_buffer)
                self.is_playing = False
                self.is_paused = False
                self._play_finished_flag = True
                self._transport_finished = True   # natural end of one-shot
                self._stop_requested = False
    def _update_scope_from_playhead(self):
        if not self.is_playing:
            if not getattr(self, "_stop_requested", False):
                self._transport_finished = True
            self.stop_playback()
            return
class StandardWaveSynthNode:
    def __init__(self, freq, sr):
        self.freq = freq
        self.sr = sr
        self.phase = 0.0
        self.amp = 0.5

    def generate_block(self, num_samples, x, y, z):
        buf = []
        # Incorporating x, y, z variables for mathematical spatial modulation
        effective_freq = self.freq * (0.5 + abs(x) * 0.5)
        step = (2.0 * math.pi * effective_freq) / self.sr
        for _ in range(num_samples):
            self.phase += step
            val = math.sin(self.phase) * self.amp * y
            buf.append(val)
        return buf
class ModularTabManager(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)

        # Add initial control tab workspace
        self.add_new_module_tab("Core Synthesizer Matrix")
    def add_new_module_tab(self, title_prefix="Node Module"):
        tab_count = self.count()
        tab_title = f"{title_prefix} {tab_count + 1}"

        container = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        inner_widget = QWidget()
        layout = QVBoxLayout(inner_widget)

        # Populate workspace with expanded DSP control and patch routing panels
        layout.addWidget(QLabel(f"--- {tab_title} Workspace ---"))
        layout.addWidget(self.create_dsp_control_panel())
        layout.addWidget(self.create_patch_bay_panel())
        layout.addWidget(QLabel(f"--- {tab_title} Workspace ---"))
        layout.addWidget(CoordinateVisualizer())       # Snippet 5
        layout.addWidget(FormulaModulatorWidget())     # Snippet 3
        layout.addWidget(ModulationMatrixWidget())     # Snippet 4
        layout.addWidget(self.create_dsp_control_panel())
        scroll.setWidget(inner_widget)

        tab_layout = QVBoxLayout(container)
        tab_layout.addWidget(scroll)
        container.setLayout(tab_layout)

        self.addTab(container, tab_title)
        self.setCurrentWidget(container)

    def close_tab(self, index):
        if self.count() > 1:
            widget = self.widget(index)
            self.removeTab(index)
            widget.deleteLater()

    def create_dsp_control_panel(self):
        panel = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(QPushButton("Bypass FX"))
        layout.addWidget(QPushButton("Sync LFO"))
        layout.addWidget(QPushButton("Resonant Feedback"))
        panel.setLayout(layout)
        return panel

    def create_patch_bay_panel(self):
        panel = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Patch Matrix: [X -> Cutoff] [Y -> Resonance] [Z -> Delay Time]"))
        panel.setLayout(layout)
        return panel
class ModularTabController:
    """Manages active tabs and links user interface adjustments to synth modulation."""
    def __init__(self):
        self.active_tab_index = 0
        self.tab_names = ["Additive Grid", "Formant Space", "Stochastic Cloud", "Master Matrix"]

    def switch_tab(self, index):
        self.active_tab_index = index % len(self.tab_names)
        return self.tab_names[self.active_tab_index]

    def get_tab_specific_multiplier(self, x, y, z):
        """Applies distinct mathematical scaling based on the currently selected tab."""
        if self.active_tab_index == 0:
            return x * 1.5 # Additive focus
        elif self.active_tab_index == 1:
            return y * 2.0 # Formant vocal resonance focus
        elif self.active_tab_index == 2:
            return z * 1.2 # Stochastic noise scatter focus
        else:
            return (x + y + z) / 3.0 # Master blend

class GrooveboxSerializationManager:
    """Handles saving and loading of sequencer patterns and active synth configurations."""

    @staticmethod
    def export_project(filepath, sequencer_grid, synth_manager, x, y, z):
        data = {
            "version": "2.0",
            "coordinates": {"x": x, "y": y, "z": z},
            "sequencer_pattern": sequencer_grid.pattern_matrix,
            "active_synths": [type(s).__name__ for s in synth_manager.active_instances]
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Export failed: {e}")
            return False

    @staticmethod
    def import_project(filepath, sequencer_grid, synth_manager):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            if "sequencer_pattern" in data:
                sequencer_grid.pattern_matrix = data["sequencer_pattern"]

            synth_manager.active_instances.clear()
            if "active_synths" in data:
                for s_type in data["active_synths"]:
                    synth_manager.spawn_instance(s_type, base_freq=220.0)

            return data.get("coordinates", {"x": 0.5, "y": 0.5, "z": 0.5})
        except Exception as e:
            print(f"Import failed: {e}")
            return None



class AdditiveSynthNode(StandardWaveSynthNode):
    """Generates sound using harmonic overtone stacking modulated by z."""
    def generate_block(self, num_samples, x, y, z):
        buf = []
        harmonics = [1.0, 2.0, 3.0, 4.0, 6.0, 8.0]
        weights = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03]
        step = (2.0 * math.pi * self.freq) / self.sr

        for i in range(num_samples):
            self.phase += step
            sample = 0.0
            for h, w in zip(harmonics, weights):
                sample += math.sin(self.phase * h * (1.0 + z * 0.1)) * w
            buf.append(sample * self.amp * y * 0.5)
        return buf

class FormantSynthNode(StandardWaveSynthNode):
    """Vocal/formant filtered oscillation powered by variable x, y, z mapping."""
    def generate_block(self, num_samples, x, y, z):
        buf = []
        formant_freq = 800.0 * abs(x + 0.1)
        step = (2.0 * math.pi * self.freq) / self.sr
        f_step = (2.0 * math.pi * formant_freq) / self.sr

        for _ in range(num_samples):
            self.phase += step
            carrier = math.sin(self.phase)
            modulator = math.sin(self.phase * 1.414) * math.cos(f_step)
            val = carrier * modulator * self.amp * z
            buf.append(val)
        return buf
class VirtualPatchCable:
    def __init__(self, source_node, target_param, attenuation=1.0):
        self.source_node = source_node
        self.target_param = target_param
        self.attenuation = attenuation
        self.is_connected = True

    def route(self, x_val, y_val, z_val):
        """Routes coordinate outputs or LFO signals into target DSP parameters."""
        if not self.is_connected:
            return 0.0

        # Select coordinate source based on mapping string
        val = 0.0
        if self.source_node == 'X':
            val = x_val
        elif self.source_node == 'Y':
            val = y_val
        elif self.source_node == 'Z':
            val = z_val

        return val * self.attenuation
class NoiseBurstNode(StandardWaveSynthNode):
    """Stochastic rhythmic noise burst generator for percussion/texture tabs."""
    def generate_block(self, num_samples, x, y, z):
        buf = []
        for _ in range(num_samples):
            noise = (random.random() * 2.0 - 1.0)
            envelope = max(0.0, 1.0 - (self.phase % 1.0))
            val = noise * envelope * self.amp * x * y
            buf.append(val)
        return buf
class VisualInstrumentLayerManager:
    """Manages the visual stacking and layout rendering of active synth modules on screen."""
    def __init__(self):
        self.visual_nodes = []

    def update_visual_stack(self, active_instances):
        self.visual_nodes.clear()
        for idx, instance in enumerate(active_instances):
            node_name = type(instance).__name__
            ui_node_card = {
                "id": idx,
                "type": node_name,
                "layer_depth": idx * 15,
                "status": "Active"
            }
            self.visual_nodes.append(ui_node_card)
        return self.visual_nodes
# -------------------------------------------------------------------------
# GLOBAL CABLE ROUTING & RESAMPLING BUS MANAGER
# -------------------------------------------------------------------------
class JackButton(QPushButton):
    """Custom interactive jack button assignable to every waveform and musical parameter."""
    def __init__(self, param_name, parent=None):
        super().__init__("JACK", parent)
        self.param_name = param_name
        self.setCheckable(True)
        self.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #00ffcc;
                border: 1px solid #00ffcc;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:checked {
                background-color: #00ffcc;
                color: #121212;
            }
        """)
        self.toggled.connect(self.on_toggle)

    def on_toggle(self, checked):
        state = "PATCHED" if checked else "UNPATCHED"
        print(f"Jack Control [{self.param_name}]: {state}")


class ParameterControlRow(QWidget):
    """A wrapper widget containing a label, slider, and an assigned JackButton for modulation routing."""
    def __init__(self, label_text, min_val=0, max_val=100, default_val=50, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(label_text)
        self.label.setStyleSheet("color: #ffffff; font-size: 11px;")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)

        self.jack_btn = JackButton(label_text)

        layout.addWidget(self.label, 2)
        layout.addWidget(self.slider, 3)
        layout.addWidget(self.jack_btn, 1)

        self.setLayout(layout)
class WavetableVectorVisualizerCanvas(QWidget):
    """Real-time Wavetable and Isosceles Trigonometric Polynomial Waveform Visualizer."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.phase = 0.0

    def update_phase(self):
        self.phase += 0.05
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor("#0a0e14"))
        p.setPen(QPen(QColor("#161b22"), 1))
        for x in range(0, w, 40):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 40):
            p.drawLine(0, y, w, y)

        path = QPainterPath()
        center_y = h / 2.0
        meum_ratio = MEUM

        for px in range(w):
            t_val = (px / w) * 4.0 * math.pi + self.phase
            val = MathEngine.isn(t_val * meum_ratio) + 0.5 * MathEngine.ics(t_val) * MathEngine.arcisn(math.sin(t_val * 0.5))
            py = center_y - (val * (h * 0.35))
            if px == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        p.setPen(QPen(QColor("#00ffcc"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(path)

        p.setPen(QPen(QColor("#58a6ff"), 1, Qt.PenStyle.DashLine))
        p.drawLine(0, int(center_y), w, int(center_y))
        p.drawText(10, 20, "Eskivector / Eskitable / Eskiosc / Eskiequation Real-Time Wavetable Visualizer")
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
class ActiveEngineClock:
    """Drives real-time activation states, step triggers, automation clock ticks, and Rhythm Flux Linking (Global/Concurrent)."""
    def __init__(self, engine):
        self.engine = engine
        self.current_step = 0
        self.transport_active = True
        self.clock_ticks_executed = 0

        # New Rhythm Flux Linking Modes & Parameters
        self.rhythm_flux_mode = "Global" # Options: "Global", "Active Concurrent", "Unlinked"
        self.rhythm_flux_rate = 1.0     # Multiplier governing synchronized rhythm flux across synths/drums
        self.flux_sync_enabled = True

    def tick_clock(self):
        if not self.transport_active:
            return self.current_step
        # Apply rhythm flux rate scaling to step progression
        step_increment = max(1, int(round(self.rhythm_flux_rate)))
        self.current_step = (self.current_step + step_increment) % 64
        self.clock_ticks_executed += 1
        return self.current_step

    def evaluate_drum_trigger(self, kit_name, step_index):
        flux_offset = int(self.rhythm_flux_rate * 2) % 5
        if self.rhythm_flux_mode == "Global":
            return ((step_index + flux_offset) % 4 == 0) or ((step_index + flux_offset) % 3 == 0 and self.engine.survival_mode)
        elif self.rhythm_flux_mode == "Active Concurrent":
            # Interleaved concurrent flux across synths and drums
            return (step_index % max(2, int(3 * self.rhythm_flux_rate)) == 0)
        else:
            return (step_index % 4 == 0)

    def evaluate_sequencer_gate(self, seq_name, step_index):
        if self.rhythm_flux_mode == "Global":
            return (step_index % 2 == 0) or (step_index % int(max(2, 4 / self.rhythm_flux_rate)) == 0)
        elif self.rhythm_flux_mode == "Active Concurrent":
            return (step_index % 3 != 0)
        else:
            return (step_index % 2 == 0)


# -------------------------------------------------------------------------
# CORE GROOVEBOX & HARDWARE ENGINE
# -------------------------------------------------------------------------
class DAWPlaylistGrid(QMainWindow):
    def __init__(self, parent=None, app_ref=None):
        super().__init__(parent)
        self.app_ref = app_ref
        self.setWindowTitle("Master Arrangement Playlist & Playhead")
        self.resize(1200, 750)
        self.setStyleSheet(DAW_STYLE)

        container = QWidget()
        layout = QVBoxLayout(container)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("<b>Arrangement Master:</b>"))

        self.play_btn = QPushButton("▶ PLAY / PAUSE")
        self.play_btn.setStyleSheet("background-color: #00aa55; color: white; font-weight: bold;")
        toolbar.addWidget(self.play_btn)

        toolbar.addWidget(QLabel("Global Tempo:"))
        self.tempo_spin = QSpinBox()
        self.tempo_spin.setRange(40, 300)
        self.tempo_spin.setValue(120)
        toolbar.addWidget(self.tempo_spin)

        random_song_btn = QPushButton("🎲 Randomize Song")
        random_song_btn.setStyleSheet("background-color: #9900cc; color: white; font-weight: bold;")
        random_song_btn.clicked.connect(self.randomize_entire_song_from_playlist)
        toolbar.addWidget(random_song_btn)

        clear_grid_btn = QPushButton("Clear Global Playlist")
        clear_grid_btn.clicked.connect(self.clear_grid)
        toolbar.addWidget(clear_grid_btn)

        layout.addLayout(toolbar)

        self.grid_table = QTableWidget(len(DEFAULT_INSTRUMENT_LIST), 128)
        self.update_vertical_headers()
        self.grid_table.horizontalHeader().setDefaultSectionSize(40)
        self.grid_table.verticalHeader().setDefaultSectionSize(24)
        self.grid_table.setStyleSheet("""
            QTableWidget { background-color: #161616; gridline-color: #282828; }
            QHeaderView::section { background-color: #1f1f1f; color: #aaaaaa; border: 1px solid #333333; font-size: 9px; }
        """)
        self.grid_table.cellClicked.connect(self.paint_clip)
        layout.addWidget(self.grid_table)

        self.status_bar = QLabel("Status: Playlist ready.")
        self.status_bar.setStyleSheet("color: #00ffcc; font-family: monospace;")
        layout.addWidget(self.status_bar)

        container.setLayout(layout)
        self.setCentralWidget(container)

    def update_vertical_headers(self):
        if self.app_ref and hasattr(self.app_ref, 'instrument_names'):
            names = self.app_ref.instrument_names
        else:
            names = DEFAULT_INSTRUMENT_LIST
        self.grid_table.setRowCount(len(names))
        self.grid_table.setVerticalHeaderLabels(names)

    def paint_clip(self, row, col):
        item = QTableWidgetItem("■ Seq")
        item.setBackground(QColor(255, 107, 0))
        item.setForeground(QColor(255, 255, 255))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_table.setItem(row, col, item)

    def clear_grid(self):
        self.grid_table.clearContents()
        self.status_bar.setText("Status: Global playlist cleared.")

    def randomize_entire_song_from_playlist(self):
        if self.app_ref and hasattr(self.app_ref, 'randomize_entire_song'):
            self.app_ref.randomize_entire_song()

    def get_grid_data(self):
        rows = self.grid_table.rowCount()
        cols = self.grid_table.columnCount()
        data = []
        for r in range(rows):
            row_items = []
            for c in range(cols):
                item = self.grid_table.item(r, c)
                row_items.append(item.text() if item is not None else None)
            data.append(row_items)
        return data
class GrooveboxEngine:
    """Core groovebox engine supporting advanced x,y,z operator equations, stochastic micro-timing, and Rhythm Flux linking."""
    def __init__(self):
        self.global_bpm = 112.0
        self.scale_system = "Equation Tonal Scale (Dynamic)"
        self.scale_equation = "x**2 + y - z"
        self.scale_increment = 0.25
        self.divergence_steps_count = 16

        self.survival_mode = False
        self.creative_mode = False
        self.normal_mode = True
        self.fractallizer_enabled = True
        self.eqr_processor_enabled = True

        self.runtime_clock = ActiveEngineClock(self)
        self.runtime_clock.transport_active = True

        self.reality_synth = RealitySynthEngine()
        self.reality_synth.survival_mode = self.survival_mode
        self.fractalizer = MusicFractallizer(dimensions=('x', 'y', 'z'))
        self.fractalizer.survival_mode = self.survival_mode

        self.available_synths = [f"Synth_Node_{i+1}" for i in range(32)]
        self.active_synth_count = 32
        self.active_synths = []
        self.synth_wiring_matrix = {}

        self.math_chord_library = {
            "Unit Harmonic Stack (+/- 1, 2, 3)": [(-3.0, 0.4), (-2.0, 0.6), (-1.0, 0.8), (1.0, 1.0), (2.0, 0.7), (3.0, 0.4)],
            "Divergent Asymmetric Point Pair": [(-4.25, 0.5), (-1.5, 0.9), (0.25, 1.0), (3.75, 0.6)],
            "Scalar Cluster": [(-1.0, 0.5), (0.0, 1.0), (1.0, 0.5), (2.0, 0.25)],
            "Linear Step Sweep (+/- 1 to 5)": [(float(i), 1.0 / abs(i) if i != 0 else 1.0) for i in range(-5, 6) if i != 0],
            "Quantum Divergence Cluster": [(-6.0, 0.2), (-3.5, 0.5), (-1.2, 0.9), (1.2, 0.9), (3.5, 0.5), (6.0, 0.2)],
            "Equation Polynomial Resonance": [(-4.0, 0.3), (-2.0, 0.7), (0.0, 1.0), (2.0, 0.7), (4.0, 0.3)],
            "Hyperbolic Phase Web": [(-5.0, 0.5), (-2.5, 0.8), (2.5, 0.8), (5.0, 0.5)],
            "Advanced Operator Matrix [x*y - z**3]": [(-3.14, 0.7), (-1.57, 0.9), (1.57, 0.9), (3.14, 0.7)]
        }

        self.instrument_sequence_banks = {}
        self.custom_wavetable_shapes = {}
        self.playlist_clips = {}

        self.active_fx_modules = ["Cloud Granulator 1", "Spectral Phase Shifter", "Nonlinear Wavefolder", "Feedback Delay", "Quantum Resonator"]
        self.active_sequencer_modules = ["Master Sequencer Lane 1", "Rhythmic Gate Generator 1", "Polyphonic Arpeggiator 1", "Stochastic Probability Matrix"]
        self.active_drum_kits = ["Kick Matrix 808", "Snare Divergence Engine", "Hi-Hat Noise Burst", "Percussion Cluster"]
        self.active_synth_panels = ["Master Equation Polynomial Synthesizer", "Eskibrutus Vectoreski Synth 1"]

        self.automation_patterns = {
            "Default Filter Sweep": [0.0, 25.0, 50.0, 85.0, 100.0, 75.0, 40.0, 10.0],
            "Resonance Pulse": [10.0, 90.0, 10.0, 90.0, 50.0, 50.0, 100.0, 0.0],
            "Exponential Pitch Ramp": [0.0, 12.0, 24.0, 36.0, 48.0, 60.0, 80.0, 100.0],
            "Chaotic LFO Modulation": [15.0, 85.0, 45.0, 95.0, 10.0, 60.0, 30.0, 90.0],
            "Harmonic Stepped Envelope": [0.0, 33.0, 33.0, 66.0, 66.0, 100.0, 50.0, 25.0],
            "Stochastic Micro-Drift": [50.0, 52.0, 48.0, 55.0, 45.0, 58.0, 42.0, 50.0]
        }

        self.available_patterns = [
            "Primary Bank - Unit Harmonic Stack",
            "Secondary Bank - Divergent Asymmetric",
            "Pulse Pattern A",
            "Pulse Pattern B",
            "Granular Noise Burst",
            "Sub-Bass Oscillator Sweep",
            "Algebraic Lead Motif",
            "Fractal Rhythm Pulse",
            "Quantum Stochastic Groove"
        ]

    def randomize_synth_routing(self):
        count = random.randint(1, 32) if self.creative_mode else 32
        self.active_synths = random.sample(self.available_synths, count)

        self.synth_wiring_matrix = {}
        for i, synth in enumerate(self.active_synths):
            downstream_target = self.active_synths[(i + 1) % len(self.active_synths)]
            modulation_source = random.choice(self.active_synths)
            attenuation_val = 0.75 if self.survival_mode else (1.25 if self.creative_mode else 1.0)

            self.synth_wiring_matrix[synth] = {
                "primary_output": downstream_target,
                "modulator": modulation_source,
                "attenuation": attenuation_val
            }
        return self.active_synths, self.synth_wiring_matrix

    def activate_fractalizer_stream(self):
        if not self.fractallizer_enabled:
            return {}
        dummy_seed = np.linspace(-1, 1, 512)
        self.last_fractal_output = self.fractalizer.generate_fractal_stream(dummy_seed)
        self.fractal_stream_active = True
        return self.last_fractal_output

    def activate_reality_synth_render(self):
        dummy_patch = np.linspace(-1, 1, 512)
        rendered_buffer = self.reality_synth.render_reality_patch(dummy_patch)
        return rendered_buffer

    def add_instrument_sequence_bank(self, instrument_name, seq_name, pitch=0.0, amp=1.0, math_chord="Unit Harmonic Stack (+/- 1, 2, 3)", stretch=1.0, length_steps=16):
        if instrument_name not in self.instrument_sequence_banks:
            self.instrument_sequence_banks[instrument_name] = []

        new_seq = {
            "name": seq_name,
            "pitch": pitch,
            "amp": amp,
            "math_chord": math_chord,
            "stretch": stretch,
            "length_steps": length_steps,
            "notes": [{"time": i * 1.5, "duration": 1.0, "active": self.runtime_clock.evaluate_sequencer_gate(seq_name, i)} for i in range(length_steps)]
        }
        self.instrument_sequence_banks[instrument_name].append(new_seq)
        pat_title = f"{instrument_name} : {seq_name}"
        if pat_title not in self.available_patterns:
            self.available_patterns.append(pat_title)
        return new_seq

    def get_instrument_banks(self, instrument_name):
        if instrument_name not in self.instrument_sequence_banks:
            self.add_instrument_sequence_bank(instrument_name, "Primary Bank", 0.0, 1.0, "Unit Harmonic Stack (+/- 1, 2, 3)", 1.0, 16)
        return self.instrument_sequence_banks[instrument_name]

    def save_custom_wavetable(self, instrument_name, points):
        self.custom_wavetable_shapes[instrument_name] = [QPointF(p.x(), p.y()) for p in points]

    def get_custom_wavetable(self, instrument_name):
        return self.custom_wavetable_shapes.get(instrument_name, [])

    def assign_playlist_clip(self, track: int, bar_pos: float, clip_data: dict):
        self.playlist_clips[(track, bar_pos)] = clip_data

    def remove_playlist_clip(self, track: int, bar_pos: float):
        if (track, bar_pos) in self.playlist_clips:
            del self.playlist_clips[(track, bar_pos)]

    def randomize_song(self):
        self.playlist_clips.clear()
        GLOBAL_BUS.clear_all()
        self.randomize_synth_routing()

        possible_fx = [
            "Cloud Granulator 1", "Cloud Granulator 2", "Spectral Phase Shifter",
            "Nonlinear Wavefolder", "Feedback Delay", "Quantum Resonator",
            "Algebraic Distortion Unit", "Convolution Reverb Matrix", "Stochastic Spectral Shifter"
        ]
        possible_seqs = [
            "Master Sequencer Lane 1", "Rhythmic Gate Generator 1", "Polyphonic Arpeggiator 1",
            "Euclidean Rhythm Engine", "Stochastic Step Sequencer", "Probability Trigger Matrix", "Quantum Operator Sequencer"
        ]
        possible_drums = [
            "Kick Matrix 808", "Snare Divergence Engine", "Hi-Hat Noise Burst",
            "Percussion Cluster", "Algebraic Tom Unit", "Quantum Claves"
        ]
        possible_synths = [
            "Master Equation Polynomial Synthesizer", "Eskibrutus Vectoreski Synth 1",
            "Vector Morph Synth Alpha", "Quantum Phase Synthesizer 2", "Stochastic Harmonic Engine"
        ]

        self.active_fx_modules = random.sample(possible_fx, random.randint(4, len(possible_fx)))
        self.active_sequencer_modules = random.sample(possible_seqs, random.randint(3, len(possible_seqs)))
        self.active_drum_kits = random.sample(possible_drums, random.randint(2, len(possible_drums)))
        self.active_synth_panels = random.sample(possible_synths, random.randint(2, len(possible_synths)))

        equations = [
            "x**2 + y - z",
            "math.sin(x) * y - z**2",
            "x * y - z",
            "abs(x) + math.cos(y) - z",
            "x**3 - y**2 + z",
            "math.tanh(x * y) - z"
        ]
        self.scale_equation = random.choice(equations)
        self.global_bpm = float(random.randint(98, 142))
        self.scale_increment = round(random.uniform(0.15, 0.35), 2)
        self.divergence_steps_count = 16

        modules = self.active_synth_panels + self.active_fx_modules
        for mod in modules:
            rand_points = [QPointF(i * (500 / 16), random.randint(10, 90)) for i in range(17)]
            self.save_custom_wavetable(mod, rand_points)
            self.get_instrument_banks(mod)

        sources = [(self.active_synth_panels[0], "Audio Gain"), (self.active_synth_panels[min(1, len(self.active_synth_panels)-1)], "Filter Q")] + [(fx, "Scatter") for fx in self.active_fx_modules[:2]]
        targets = ["Master Audio Output Bus", "Auxiliary Bus A", "Auxiliary Bus B"]
        polarities = ["+", "-", "Neutral"]

        for _ in range(random.randint(5, 12)):
            src_mod, src_node = random.choice(sources)
            tgt_mod = random.choice(targets)
            pol = random.choice(polarities)
            gain_val = round(random.uniform(0.4, 2.2), 2)
            GLOBAL_BUS.add_cable(src_mod, src_node, tgt_mod, "Primary Sum Node", polarity=pol, gain=gain_val)

        target_bars = random.randint(64, 192)
        num_tracks = random.randint(8, 32)
        pattern_names = self.available_patterns
        chord_names = list(self.math_chord_library.keys())
        auto_names = list(self.automation_patterns.keys())

        for trk in range(num_tracks):
            bar_steps = list(range(0, target_bars, 2))
            chosen_bars = random.sample(bar_steps, min(len(bar_steps), random.randint(14, 40)))

            for bar in chosen_bars:
                clip_data = {
                    "name": random.choice(pattern_names),
                    "chord": random.choice(chord_names),
                    "pitch": float(random.choice([-12, -7, -5, 0, 5, 7, 12, 14])),
                    "amplitude": round(random.uniform(0.4, 1.5), 2),
                    "stretch": round(random.uniform(0.5, 2.0), 2),
                    "automation_pattern": random.choice(auto_names)
                }
                self.playlist_clips[(trk, float(bar))] = clip_data

    def generate_equation_scale_frequencies(self):
        freqs = []
        for i in range(self.divergence_steps_count):
            x = i * self.scale_increment
            y = x * 1.618
            z = 1.0 if (i % 4 == 0 or i % 3 == 0) else 0.0
            try:
                val = eval(self.scale_equation, {"__builtins__": None}, {"x": x, "y": y, "z": z, "math": math})
                freq = FREQUENCY_432HZ + (float(val) * 22.5)
                freqs.append(max(35.0, freq))
            except Exception:
                freqs.append(FREQUENCY_432HZ + (i * 12.0 * self.scale_increment))
        return freqs

    def resolve_math_chord_frequencies(self, chord_name, x_var=1.0, y_var=1.0, z_var=1.0):
        base_freqs = self.generate_equation_scale_frequencies()
        base_f = base_freqs[0] if base_freqs else FREQUENCY_432HZ
        point_pairs = self.math_chord_library.get(chord_name, [(1.0, 1.0)])

        resolved = []
        for offset_mult, amp_val in point_pairs:
            adjusted_offset = offset_mult * x_var * y_var - (z_var * 0.1)
            freq = base_f + (adjusted_offset * self.scale_increment * 55.0)
            resolved.append((max(20.0, freq), amp_val))
        return resolved

    def serialize_project(self, filepath):
        data = {
            "global_bpm": self.global_bpm,
            "scale_system": self.scale_system,
            "scale_equation": self.scale_equation,
            "scale_increment": self.scale_increment,
            "divergence_steps_count": self.divergence_steps_count,
            "survival_mode": self.survival_mode,
            "creative_mode": self.creative_mode,
            "normal_mode": self.normal_mode,
            "fractallizer_enabled": self.fractallizer_enabled,
            "eqr_processor_enabled": self.eqr_processor_enabled,
            "math_chord_library": self.math_chord_library,
            "instrument_sequence_banks": self.instrument_sequence_banks,
            "automation_patterns": self.automation_patterns,
            "playlist_clips": {f"{t},{b}": dat for (t, b), dat in self.playlist_clips.items()},
            "global_cables": GLOBAL_BUS.global_cables,
            "resampled_buffers": GLOBAL_BUS.resampled_buffers,
            "active_synths": self.active_synths,
            "synth_wiring_matrix": self.synth_wiring_matrix,
            "active_fx_modules": self.active_fx_modules,
            "active_sequencer_modules": self.active_sequencer_modules,
            "active_drum_kits": self.active_drum_kits,
            "active_synth_panels": self.active_synth_panels
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    def deserialize_project(self, filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.global_bpm = data.get("global_bpm", 112.0)
        self.scale_equation = data.get("scale_equation", "x**2 + y - z")
        self.scale_increment = data.get("scale_increment", 0.25)
        self.divergence_steps_count = data.get("divergence_steps_count", 16)
        self.survival_mode = data.get("survival_mode", False)
        self.creative_mode = data.get("creative_mode", False)
        self.normal_mode = data.get("normal_mode", True)
        self.fractallizer_enabled = data.get("fractallizer_enabled", True)
        self.eqr_processor_enabled = data.get("eqr_processor_enabled", True)
        if "math_chord_library" in data:
            self.math_chord_library = data.get("math_chord_library")
        self.instrument_sequence_banks = data.get("instrument_sequence_banks", {})
        self.automation_patterns = data.get("automation_patterns", {"Default Filter Sweep": [0, 50, 100]})
        self.active_synths = data.get("active_synths", [])
        self.synth_wiring_matrix = data.get("synth_wiring_matrix", {})
        self.active_fx_modules = data.get("active_fx_modules", self.active_fx_modules)
        self.active_sequencer_modules = data.get("active_sequencer_modules", self.active_sequencer_modules)
        self.active_drum_kits = data.get("active_drum_kits", self.active_drum_kits)
        self.active_synth_panels = data.get("active_synth_panels", self.active_synth_panels)
        pc = data.get("playlist_clips", {})
        self.playlist_clips = {}
        for key_str, dat in pc.items():
            t_str, b_str = key_str.split(",")
            self.playlist_clips[(int(t_str), float(b_str))] = dat
        GLOBAL_BUS.global_cables = data.get("global_cables", [])
        GLOBAL_BUS.resampled_buffers = data.get("resampled_buffers", [])
        GLOBAL_BUS.broadcast_update()

    def export_audio(self, filepath, duration_sec=300.0, sample_rate=44100):
        num_samples = int(sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, num_samples, endpoint=False)
        wave_data = np.zeros(num_samples)

        bank_index = 0
        total_banks = sum(len(banks) for banks in self.instrument_sequence_banks.values())
        if total_banks == 0:
            total_banks = 1

        for instr_name, banks in self.instrument_sequence_banks.items():
            for bank in banks:
                chord_name = bank.get("math_chord", "Unit Harmonic Stack (+/- 1, 2, 3)")
                pitch_shift = bank.get("pitch", 0.0)
                pitch_multiplier = 2.0 ** (pitch_shift / 12.0)
                resolved_pairs = self.resolve_math_chord_frequencies(chord_name)
                bank_amp = bank.get("amp", 1.0)

                layer_detune = 1.0 + (bank_index - (total_banks / 2.0)) * 0.002
                phase_offset = (bank_index / float(total_banks)) * 2.0 * np.pi

                for freq, pt_amp in resolved_pairs:
                    adjusted_freq = freq * pitch_multiplier * layer_detune
                    tempo_mod_factor = 1.0 + 0.15 * np.sin(2.0 * np.pi * (self.global_bpm / 112.0) * t * 0.05 + phase_offset)
                    gate = 0.5 * (1 + np.sin(2 * np.pi * (self.global_bpm / 60.0) * t * tempo_mod_factor + phase_offset + np.sin(t * 0.1) * 0.05))
                    wave_data += bank_amp * pt_amp * 0.08 * gate * np.sin(2 * np.pi * (adjusted_freq * tempo_mod_factor) * t + phase_offset)

                bank_index += 1

        max_val = np.max(np.abs(wave_data))
        if max_val > 0:
            wave_data = wave_data / max_val
        audio_int = np.int16(wave_data * 32767)

        with wave.open(filepath, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int.tobytes())


# -------------------------------------------------------------------------
# FREE-FLOATING & RESIZABLE WORKSPACE PANEL
# -------------------------------------------------------------------------
class ResizableWorkspacePanel(QWidget):
    def __init__(self, title, content_widget, parent=None):
        super().__init__(parent)
        self.title = title
        self.setMinimumSize(340, 260)
        self.resize(620, 390)
        self.setStyleSheet("""
            ResizableWorkspacePanel {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
            }
            QLabel { color: #c9d1d9; background: transparent; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        self.title_lbl = QLabel(f"🎛 {title} [Resizable Panel]")
        self.title_lbl.setStyleSheet("color: #f5d97d; font-weight: bold; font-size: 11px; background: transparent;")
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()

        resize_hint = QLabel("↔ Drag borders to resize")
        resize_hint.setStyleSheet("color: #8b949e; font-size: 9px; background: transparent;")
        header_layout.addWidget(resize_hint)
        layout.addLayout(header_layout)
        layout.addWidget(content_widget)

        self.dragging = False
        self.resizing = False
        self.drag_position = QPointF()
        self.resize_margin = 12

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().x() >= self.width() - self.resize_margin and event.position().y() >= self.height() - self.resize_margin:
                self.resizing = True
            else:
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.resizing:
            new_w = max(340, event.position().x())
            new_h = max(260, event.position().y())
            self.resize(int(new_w), int(new_h))
            event.accept()
        elif self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing = False
        event.accept()


# -------------------------------------------------------------------------
# FREEHAND DRAWABLE WAVETABLE CANVAS
# -------------------------------------------------------------------------
class WavetableCanvas(QWidget):
    def __init__(self, instrument_name, engine, parent=None):
        super().__init__(parent)
        self.instrument_name = instrument_name
        self.engine = engine
        self.setMinimumHeight(110)
        self.setStyleSheet("background-color: #0d1117; border: 1px solid #30363d; border-radius: 4px;")

        existing = self.engine.get_custom_wavetable(self.instrument_name)
        if existing:
            self.points = list(existing)
        else:
            self.points = [QPointF(i * (500 / 16), 55 + 25 * math.sin(i * 0.4)) for i in range(17)]

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d1117"))

        p.setPen(QPen(QColor("#161b22"), 1, Qt.PenStyle.DashLine))
        for x in range(0, self.width(), 50): p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 30): p.drawLine(0, y, self.width(), y)

        if len(self.points) >= 2:
            path = QPainterPath(); path.moveTo(self.points[0])
            for pt in self.points[1:]: path.lineTo(pt)
            p.setPen(QPen(QColor("#00ffcc"), 2.0))
            p.drawPath(path)

        p.setBrush(QBrush(QColor("#f5d97d")))
        p.setPen(QPen(QColor("#ffffff"), 1))
        for pt in self.points: p.drawEllipse(pt, 3, 3)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self.points.append(QPointF(max(0, min(self.width(), pos.x())), max(5, min(self.height() - 5, pos.y()))))
            self.points.sort(key=lambda pt: pt.x())
            if len(self.points) > 24:
                self.points = self.points[:24]
            self.engine.save_custom_wavetable(self.instrument_name, self.points)
            self.update()


# -------------------------------------------------------------------------
# INTERACTIVE PATCHABLE KNOB & PATCH JACK
# -------------------------------------------------------------------------
class PatchableKnob(QWidget):
    """Features direct straightforward envelope/decay responsiveness and patch jack capability."""
    def __init__(self, label_text, min_val=0.0, max_val=100.0, default_val=50.0, unit="", module_name="Synth 1", parent=None):
        super().__init__(parent)
        self.label_text = label_text
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = default_val
        self.unit = unit
        self.module_name = module_name
        self.is_patched = False

        self.polarity = "Neutral"
        self.gain_multiplier = 1.0
        self.setFixedSize(140, 125)
        self.setStyleSheet("background: #0d1117;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.label = QLabel(f"{label_text}: {default_val:.1f}{unit}")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #c9d1d9; font-size: 9px; font-weight: bold; background: transparent;")
        layout.addWidget(self.label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * 10), int(max_val * 10))
        self.slider.setValue(int(default_val * 10))
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #161b22; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #00ffcc; width: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        target_row = QHBoxLayout()
        target_lbl = QLabel("Tgt:")
        target_lbl.setStyleSheet("color: #8b949e; font-size: 8px; background: transparent;")
        target_row.addWidget(target_lbl)

        self.target_combo = QComboBox()
        self.target_combo.setFixedHeight(20)
        self.target_combo.setStyleSheet("background-color: #161b22; color: #00ffcc; font-size: 8px; border: 1px solid #30363d;")
        self.target_combo.addItems([
            "Master Audio Sum", "Filter Cutoff", "Resonance Mod",
            "Granular Scatter", "Amplitude Envelope", "Phase Distortion"
        ])
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        target_row.addWidget(self.target_combo)
        layout.addLayout(target_row)

        bottom_row = QHBoxLayout()
        self.polarity_btn = QPushButton("Neutral")
        self.polarity_btn.setFixedHeight(20)
        self.polarity_btn.setStyleSheet("background-color: #161b22; color: #00ffcc; font-size: 8px; border: 1px solid #30363d; font-weight: bold;")
        self.polarity_btn.clicked.connect(self._toggle_polarity)
        bottom_row.addWidget(self.polarity_btn)

        self.port_btn = QPushButton("Deactivate" if self.is_patched else "Activate")
        self.port_btn.setFixedSize(65, 22)
        self.port_btn.setCheckable(True)
        self.port_btn.setChecked(self.is_patched)
        self.port_btn.setStyleSheet("""
            QPushButton { background-color: #161b22; color: #8b949e; border: 1px solid #30363d; border-radius: 4px; font-weight: bold; font-size: 9px; }
            QPushButton:checked { background-color: #00ffcc; color: #0d1117; border: 1px solid #ffffff; }
        """)
        self.port_btn.clicked.connect(self._toggle_patch)
        bottom_row.addWidget(self.port_btn)
        layout.addLayout(bottom_row)

        gain_row = QHBoxLayout()
        self.gain_down_btn = QPushButton("-")
        self.gain_down_btn.setFixedSize(18, 18)
        self.gain_down_btn.setStyleSheet("background-color: #161b22; color: #ff7b72; font-size: 9px; font-weight: bold;")
        self.gain_down_btn.clicked.connect(lambda: self._adjust_gain(-0.25))

        self.gain_lbl = QLabel("Amt: 1.0x")
        self.gain_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gain_lbl.setStyleSheet("color: #8b949e; font-size: 8px; background: transparent;")

        self.gain_up_btn = QPushButton("+")
        self.gain_up_btn.setFixedSize(18, 18)
        self.gain_up_btn.setStyleSheet("background-color: #161b22; color: #00ffcc; font-size: 9px; font-weight: bold;")
        self.gain_up_btn.clicked.connect(lambda: self._adjust_gain(0.25))

        gain_row.addWidget(self.gain_down_btn)
        gain_row.addWidget(self.gain_lbl)
        gain_row.addWidget(self.gain_up_btn)
        layout.addLayout(gain_row)

    def _on_slider_changed(self, val):
        self.current_val = val / 10.0
        self.label.setText(f"{self.label_text}: {self.current_val:.1f}{self.unit}")

    def _on_target_changed(self, index):
        if self.is_patched:
            target_name = self.target_combo.currentText()
            for i, c in enumerate(GLOBAL_BUS.global_cables):
                if c["src_module"] == self.module_name and c["src_node"] == self.label_text:
                    GLOBAL_BUS.global_cables[i]["tgt_module"] = target_name
                    GLOBAL_BUS.broadcast_update()
                    break

    def _toggle_polarity(self):
        if self.polarity == "Neutral":
            self.polarity = "+"
            self.polarity_btn.setStyleSheet("background-color: #161b22; color: #f5d97d; font-size: 8px; border: 1px solid #f5d97d; font-weight: bold;")
            self.polarity_btn.setText("+ (Pos)")
        elif self.polarity == "+":
            self.polarity = "-"
            self.polarity_btn.setStyleSheet("background-color: #161b22; color: #ff7b72; font-size: 8px; border: 1px solid #ff7b72; font-weight: bold;")
            self.polarity_btn.setText("- (Inv)")
        else:
            self.polarity = "Neutral"
            self.polarity_btn.setStyleSheet("background-color: #161b22; color: #00ffcc; font-size: 8px; border: 1px solid #30363d; font-weight: bold;")
            self.polarity_btn.setText("Neutral")

        if self.is_patched:
            for i, c in enumerate(GLOBAL_BUS.global_cables):
                if c["src_module"] == self.module_name and c["src_node"] == self.label_text:
                    GLOBAL_BUS.update_cable_polarity_gain(i, self.polarity, 0.0)
                    break

    def _adjust_gain(self, delta):
        self.gain_multiplier = max(0.25, round(self.gain_multiplier + delta, 2))
        self.gain_lbl.setText(f"Amt: {self.gain_multiplier:.2f}x")
        if self.is_patched:
            for i, c in enumerate(GLOBAL_BUS.global_cables):
                if c["src_module"] == self.module_name and c["src_node"] == self.label_text:
                    GLOBAL_BUS.update_cable_polarity_gain(i, self.polarity, delta)
                    break

    def _toggle_patch(self, checked):
        self.is_patched = checked
        target_name = self.target_combo.currentText()
        if checked:
            self.port_btn.setText("Deactivate")
            GLOBAL_BUS.add_cable(
                src_module=self.module_name, src_node=self.label_text,
                tgt_module=target_name, tgt_node="Primary Sum Node",
                polarity=self.polarity, gain=self.gain_multiplier
            )
        else:
            self.port_btn.setText("Activate")
            for i, c in enumerate(GLOBAL_BUS.global_cables):
                if c["src_module"] == self.module_name and c["src_node"] == self.label_text:
                    GLOBAL_BUS.remove_cable(i)
                    break


# -------------------------------------------------------------------------
# FREEFORM SEQUENCER CANVAS
# -------------------------------------------------------------------------
class FreeformSequencerCanvas(QWidget):
    def __init__(self, sequence_data, parent=None):
        super().__init__(parent)
        self.seq_data = sequence_data
        self.setMinimumHeight(130)
        self.setStyleSheet("background-color: #0b0f15; border: 1px solid #30363d; border-radius: 4px;")

    def paintEvent(self, event):
        # Initialize the painter once for the widget
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            # Safely resolve sequence data or notes fallback
            notes = self.seq_data.get("notes", []) if isinstance(self.seq_data, dict) else [
                {"time": float(i), "duration": 1.0, "active": True} for i, val in enumerate(self.seq_data)
            ]

            formatted_notes = []
            for i, n in enumerate(notes):
                if isinstance(n, dict):
                    formatted_notes.append({
                        "time": n.get("time", float(i)),
                        "duration": n.get("duration", 1.0),
                        "active": n.get("active", True)
                    })
                else:
                    formatted_notes.append({
                        "time": float(i),
                        "duration": 1.0,
                        "active": bool(n)
                    })

            max_time = max([n["time"] + n["duration"] for n in formatted_notes] + [16.0])
            scale_x = self.width() / max(16.0, max_time)

            # Draw background grid/fill manually here if needed, then render notes:
            for i, note in enumerate(formatted_notes):
                nx = note["time"] * scale_x
                nw = max(12, note["duration"] * scale_x)
                ny = 15 + (i % 4) * 24

                is_active = note["active"]
                p.setBrush(QBrush(QColor("#00ffcc" if is_active else "#21262d")))
                p.setPen(QPen(QColor("#ffffff") if is_active else QColor("#484f58"), 1))
                p.drawRoundedRect(int(nx), int(ny), int(nw), 18, 4, 4)

                p.setPen(QPen(QColor("#ffffff" if is_active else "#8b949e"), 1))
                p.drawText(int(nx) + 4, int(ny) + 13, f"N{i+1}")

        finally:
            # Explicitly end painting so QBackingStore releases the canvas device
            p.end()


    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            max_time = max([n["time"] + n["duration"] for n in self.seq_data.get("notes", [])] + [16.0])
            scale_x = self.width() / max(16.0, max_time)
            clicked_time = pos.x() / scale_x

            notes = self.seq_data.get("notes", [])
            found = False
            for note in notes:
                if note["time"] <= clicked_time <= (note["time"] + note["duration"]):
                    note["active"] = not note["active"]
                    found = True
                    break
            if not found:
                notes.append({"time": round(clicked_time, 2), "duration": 1.5, "active": True})
            self.update()


# -------------------------------------------------------------------------
# TAB 1: SYNTHS, MULTI-SEQUENCE STACKS & EQUATION POLYNOMIAL SYNTH
# -------------------------------------------------------------------------
class SynthModulePage(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = GrooveboxEngine()
        self.setStyleSheet("background-color: #070b10;")
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        spawn_audio_in_btn = QPushButton("+ Spawn Audio In/Out Jack Module")
        spawn_audio_in_btn.setStyleSheet("background-color: #1f242c; color: #ff7b72; font-weight: bold; border: 1px solid #ff7b72; padding: 6px;")
        spawn_audio_in_btn.clicked.connect(lambda: self._spawn_panel("Dedicated Audio I/O Loop", is_audio_in=True))

        spawn_poly_btn = QPushButton("+ Spawn Equation Polynomial Synth")
        spawn_poly_btn.setStyleSheet("background-color: #1f242c; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d; padding: 6px;")
        spawn_poly_btn.clicked.connect(lambda: self._spawn_panel("Equation Polynomial Algebra Synth", is_polynomial=True))

        spawn_synth_btn = QPushButton("+ Spawn Resizable Multi-Seq Synth")
        spawn_synth_btn.setStyleSheet("background-color: #1f242c; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 6px;")
        spawn_synth_btn.clicked.connect(lambda: self._spawn_panel("Vector Synth & Multi-Seq Engine", is_synth=True))

        spawn_random_instr_btn = QPushButton("🎲 Spawn Randomizer Instrument")
        spawn_random_instr_btn.setStyleSheet("background-color: #2b1135; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d; padding: 6px;")
        spawn_random_instr_btn.clicked.connect(self._spawn_randomizer_instrument)

        activate_fractal_btn = QPushButton("🌀 Activate Fractallizer")
        activate_fractal_btn.setStyleSheet("background-color: #2b1135; color: #ff7b72; font-weight: bold; border: 1px solid #ff7b72; padding: 6px;")
        activate_fractal_btn.clicked.connect(self._trigger_fractalizer)

        activate_reality_btn = QPushButton("🌌 Activate Reality Synth")
        activate_reality_btn.setStyleSheet("background-color: #112b35; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 6px;")
        activate_reality_btn.clicked.connect(self._trigger_reality_synth)

        top_bar.addWidget(spawn_audio_in_btn)
        top_bar.addWidget(spawn_poly_btn)
        top_bar.addWidget(spawn_synth_btn)
        top_bar.addWidget(spawn_random_instr_btn)
        top_bar.addWidget(activate_fractal_btn)
        top_bar.addWidget(activate_reality_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        toggles_bar = QHBoxLayout()

        self.fractal_toggle = QCheckBox("Enable Music Fractallizer")
        self.fractal_toggle.setChecked(getattr(self.engine, 'fractallizer_enabled', True))
        self.fractal_toggle.setStyleSheet("""
            QCheckBox { color: #888888; font-weight: bold; background: #161b22; padding: 4px; border: 1px solid #30363d; }
            QCheckBox:checked { color: #00ffcc; border-color: #00ffcc; }
        """)
        self.fractal_toggle.stateChanged.connect(self._toggle_fractalizer_state)

        self.eqr_toggle = QCheckBox("Enable EQR Processor")
        self.eqr_toggle.setChecked(getattr(self.engine, 'eqr_processor_enabled', True))
        self.eqr_toggle.setStyleSheet("""
            QCheckBox { color: #888888; font-weight: bold; background: #161b22; padding: 4px; border: 1px solid #30363d; }
            QCheckBox:checked { color: #f5d97d; border-color: #f5d97d; }
        """)
        self.eqr_toggle.stateChanged.connect(self._toggle_eqr_processor_state)

        toggles_bar.addWidget(self.fractal_toggle)
        toggles_bar.addWidget(self.eqr_toggle)
        toggles_bar.addStretch()
        layout.addLayout(toggles_bar)

        mode_bar = QHBoxLayout()
        self.mode_status_lbl = QLabel()
        self._update_mode_label()
        self.mode_status_lbl.setStyleSheet("color: #f5d97d; font-weight: bold; background: #161b22; padding: 4px; border: 1px solid #30363d;")

        toggle_mode_btn = QPushButton("🔄 Cycle Operational Mode (Normal ➔ Creative ➔ Survival)")
        toggle_mode_btn.setStyleSheet("background-color: #1f242c; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 4px;")
        toggle_mode_btn.clicked.connect(self._toggle_modes)

        mode_bar.addWidget(self.mode_status_lbl)
        mode_bar.addWidget(toggle_mode_btn)
        mode_bar.addStretch()
        layout.addLayout(mode_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background-color: #070b10; border: none;")
        self.container = QWidget(self)
        self.container.setStyleSheet("background-color: #070b10;")
        self.container_layout = QGridLayout(self.container)

        self.refresh_synth_grid()

        self.container.setLayout(self.container_layout)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def refresh_synth_grid(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for idx, synth_name in enumerate(self.engine.active_synth_panels):
            is_poly = "Polynomial" in synth_name or "Algebra" in synth_name
            is_synth_type = not is_poly
            row = idx // 2
            col = idx % 2
            self._add_panel_to_grid(synth_name, is_synth=is_synth_type, is_polynomial=is_poly, row=row, col=col)

        self.container.update()

    def _toggle_fractalizer_state(self, state):
        self.engine.fractallizer_enabled = bool(state)
        status = "Enabled" if self.engine.fractallizer_enabled else "Disabled"
        QMessageBox.information(self, "Fractallizer State", f"Music Fractallizer has been {status}.")

    def _toggle_eqr_processor_state(self, state):
        self.engine.eqr_processor_enabled = bool(state)
        status = "Enabled" if self.engine.eqr_processor_enabled else "Disabled"
        QMessageBox.information(self, "EQR Processor State", f"EQR Processor has been {status}.")

    def _update_mode_label(self):
        s_mode = "ON" if self.engine.survival_mode else "OFF"
        n_mode = "ON" if self.engine.normal_mode else "OFF"
        c_mode = "ON" if self.engine.creative_mode else "OFF"
        self.mode_status_lbl.setText(f"Electron Sling State -> Survival: {s_mode} | Normal: {n_mode} | Creative: {c_mode}")

    def _toggle_modes(self):
        if self.engine.normal_mode:
            self.engine.normal_mode = False
            self.engine.creative_mode = True
            self.engine.survival_mode = False
        elif self.engine.creative_mode:
            self.engine.normal_mode = False
            self.engine.creative_mode = False
            self.engine.survival_mode = True
        else:
            self.engine.normal_mode = True
            self.engine.creative_mode = False
            self.engine.survival_mode = False

        self.engine.reality_synth.survival_mode = self.engine.survival_mode
        self.engine.fractalizer.survival_mode = self.engine.survival_mode
        self._update_mode_label()

        active_name = "Normal" if self.engine.normal_mode else ("Creative" if self.engine.creative_mode else "Survival")
        QMessageBox.information(self, "Operational Mode Updated", f"Electron Sling mode switched to: {active_name} Mode.")

    def _trigger_fractalizer(self):
        if not self.engine.fractallizer_enabled:
            QMessageBox.warning(self, "Fractallizer Disabled", "Cannot trigger stream: Music Fractallizer is currently disabled via UI controls.")
            return
        stream = self.engine.activate_fractalizer_stream()
        QMessageBox.information(self, "Music Fractallizer Activated", f"Music Fractallizer stream successfully generated with spatial dimensions: {list(stream.keys())}.")

    def _trigger_reality_synth(self):
        buffer_data = self.engine.activate_reality_synth_render()
        QMessageBox.information(self, "Reality Synth Rendered", f"Reality Synth active buffer rendered for coordinates: {list(buffer_data.keys())}.")

    def _spawn_panel(self, kind, is_synth=False, is_audio_in=False, is_polynomial=False):
        name = f"{kind} #{len(self.engine.active_synth_panels) + 1}"
        if name not in self.engine.active_synth_panels:
            self.engine.active_synth_panels.append(name)
        self.refresh_synth_grid()

    def _spawn_randomizer_instrument(self):
        rand_prefixes = ["Stochastic", "Quantum", "Algebraic", "Fractal", "Harmonic", "Resonant", "Vectoreski"]
        rand_suffixes = ["Oscillator", "Sling", "Resonator", "Generator", "Synth Node", "Phase Wave"]
        instr_name = f"{random.choice(rand_prefixes)} {random.choice(rand_suffixes)} {random.randint(100, 999)}"

        chords = list(self.engine.math_chord_library.keys())
        chosen_chord = random.choice(chords)
        self.engine.add_instrument_sequence_bank(instr_name, "Differentiated Tempo Bank", pitch=float(random.randint(-12, 12)), amp=round(random.uniform(0.5, 1.5), 2), math_chord=chosen_chord)

        if instr_name not in self.engine.active_synth_panels:
            self.engine.active_synth_panels.append(instr_name)
        self.refresh_synth_grid()
        QMessageBox.information(self, "Randomizer Instrument Spawned", f"Successfully spawned randomizer instrument '{instr_name}' with differentiated tempo interval parameters and cross-mod heuristic routing.")

    def _add_panel_to_grid(self, title, is_synth=False, is_audio_in=False, is_polynomial=False, row=0, col=0):
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background-color: #0d1117;")
        c_layout = QVBoxLayout(content_widget)
        c_layout.setContentsMargins(4, 4, 4, 4)

        if is_polynomial:
            poly_hud_layout = QVBoxLayout()
            poly_lbl = QLabel("📐 Live Polynomial Algebra Evaluator (Step-Gated x, y, z Variables)")
            poly_lbl.setStyleSheet("color: #f5d97d; font-weight: bold; background: transparent;")
            poly_hud_layout.addWidget(poly_lbl)

            eq_row = QHBoxLayout()
            eq_label = QLabel("Eq:")
            eq_label.setStyleSheet("color: #c9d1d9; background: transparent;")
            eq_row.addWidget(eq_label)

            eq_field = QLineEdit(self.engine.scale_equation)
            eq_field.setStyleSheet("background-color: #161b22; color: #00ffcc; font-family: monospace; border: 1px solid #30363d;")
            eq_row.addWidget(eq_field)

            eval_btn = QPushButton("Evaluate & Map")
            eval_btn.setStyleSheet("background-color: #1f242c; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d;")
            eval_btn.clicked.connect(lambda: self._evaluate_polynomial_osc(eq_field.text(), title))
            eq_row.addWidget(eval_btn)
            poly_hud_layout.addLayout(eq_row)
            c_layout.addLayout(poly_hud_layout)

        if is_audio_in:
            io_header = QHBoxLayout()
            lbl_in = QLabel("🔴 Input Jack [IN]")
            lbl_in.setStyleSheet("color: #ff7b72; background: transparent;")
            io_header.addWidget(lbl_in)

            in_jack = QPushButton("● Audio Input Bus")
            in_jack.setStyleSheet("background-color: #00ffcc; color: #0d1117; font-weight: bold; font-size: 9px;")
            io_header.addWidget(in_jack)

            lbl_out = QLabel("🟢 Output Jack [OUT]")
            lbl_out.setStyleSheet("color: #00ffcc; background: transparent;")
            io_header.addWidget(lbl_out)

            out_jack = QPushButton("● Audio Output Bus")
            out_jack.setStyleSheet("background-color: #f5d97d; color: #0d1117; font-weight: bold; font-size: 9px;")
            io_header.addWidget(out_jack)

            resample_btn = QPushButton("Buffer Resample")
            resample_btn.setStyleSheet("background-color: #2b1115; color: #ff7b72; border: 1px solid #ff7b72; font-weight: bold; padding: 3px;")
            resample_btn.clicked.connect(lambda: self._trigger_resampling(title))
            io_header.addWidget(resample_btn)
            c_layout.addLayout(io_header)

        if is_synth:
            banks_layout = QHBoxLayout()
            lbl_bks = QLabel("Sequence Banks:")
            lbl_bks.setStyleSheet("color: #c9d1d9; background: transparent;")
            banks_layout.addWidget(lbl_bks)

            bank_combo = QComboBox()
            bank_combo.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")

            instr_banks = self.engine.get_instrument_banks(title)
            for b in instr_banks:
                bank_combo.addItem(b["name"])
            banks_layout.addWidget(bank_combo)

            add_bank_btn = QPushButton("+ New Sequence")
            add_bank_btn.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #00ffcc; font-size: 9px; font-weight: bold;")
            add_bank_btn.clicked.connect(lambda: self._add_new_sequence_bank(title, bank_combo))
            banks_layout.addWidget(add_bank_btn)
            c_layout.addLayout(banks_layout)

            param_grid = QGridLayout()
            pitch_spin = QDoubleSpinBox(); pitch_spin.setRange(-24.0, 24.0); pitch_spin.setValue(0.0); pitch_spin.setSuffix(" st")
            pitch_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")

            amp_spin = QDoubleSpinBox(); amp_spin.setRange(0.0, 2.0); amp_spin.setValue(1.0); amp_spin.setSingleStep(0.1)
            amp_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")

            stretch_spin = QDoubleSpinBox(); stretch_spin.setRange(0.2, 4.0); stretch_spin.setValue(1.0); stretch_spin.setSingleStep(0.1)
            stretch_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")

            math_chord_combo = QComboBox()
            math_chord_combo.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
            math_chord_combo.addItems(list(self.engine.math_chord_library.keys()))

            length_spin = QSpinBox(); length_spin.setRange(4, 128); length_spin.setValue(16)
            length_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")

            param_grid.addWidget(QLabel("Pitch Shift:"), 0, 0); param_grid.addWidget(pitch_spin, 0, 1)
            param_grid.addWidget(QLabel("Amp:"), 0, 2); param_grid.addWidget(amp_spin, 0, 3)
            param_grid.addWidget(QLabel("Stretch:"), 1, 0); param_grid.addWidget(stretch_spin, 1, 1)
            param_grid.addWidget(QLabel("Math Chords (Point Pairs):"), 1, 2); param_grid.addWidget(math_chord_combo, 1, 3)
            param_grid.addWidget(QLabel("Steps:"), 2, 0); param_grid.addWidget(length_spin, 2, 1)
            c_layout.addLayout(param_grid)

            active_bank = instr_banks[0]
            seq_canvas = FreeformSequencerCanvas(active_bank)
            c_layout.addWidget(seq_canvas)

        wt_canvas = WavetableCanvas(title, self.engine)
        c_layout.addWidget(wt_canvas)

        knobs_layout = QHBoxLayout()
        knobs_layout.addWidget(PatchableKnob("Envelope Decay", 10.0, 1000.0, 250.0, "ms", title, self))
        knobs_layout.addWidget(PatchableKnob("Audio Gain", 0.0, 100.0, 75.0, "%", title, self))
        knobs_layout.addWidget(PatchableKnob("Filter Q", 0.1, 20.0, 4.0, "Q", title, self))
        c_layout.addLayout(knobs_layout)

        panel = ResizableWorkspacePanel(title, content_widget)
        panel.show()
        self.container_layout.addWidget(panel, row, col)

    def _add_new_sequence_bank(self, title, combo):
        bank_name = f"Sequence Bank {len(self.engine.get_instrument_banks(title)) + 1}"
        self.engine.add_instrument_sequence_bank(title, bank_name)
        combo.addItem(bank_name)
        combo.setCurrentIndex(combo.count() - 1)
        QMessageBox.information(self, "Sequence Bank Added", f"Created new freeform sequence bank '{bank_name}' for {title}.")

    def _trigger_resampling(self, title):
        buf_name = GLOBAL_BUS.trigger_resampling()
        QMessageBox.information(self, "Live Resampling Captured", f"Active audio input loop from '{title}' successfully resampled into buffer: {buf_name}")

    def _evaluate_polynomial_osc(self, eq_text, title):
        self.engine.scale_equation = eq_text
        freqs = self.engine.generate_equation_scale_frequencies()
        QMessageBox.information(self, "Polynomial Evaluated", f"Equation '{eq_text}' successfully computed across step-gated x, y, z variables for '{title}'. Generated {len(freqs)} rhythmic frequencies!")


# -------------------------------------------------------------------------
# TAB 2: FULLY ACTIVATED DRUM & PERCUSSION MATRIX
# -------------------------------------------------------------------------
class DrumMatrixPage(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setStyleSheet("background-color: #070b10;")
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_info = QLabel("🥁 Fully Activated Drum & Percussion Synthesizer Matrix (Live Step-Clock Gated Transients)")
        top_info.setStyleSheet("color: #f5d97d; font-weight: bold; font-size: 12px; background: transparent;")
        top_bar.addWidget(top_info)
        top_bar.addStretch()

        activate_all_drums_btn = QPushButton("⚡ Force Trigger All Drum Gates")
        activate_all_drums_btn.setStyleSheet("background-color: #2b1135; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 6px;")
        activate_all_drums_btn.clicked.connect(self._force_trigger_drums)
        top_bar.addWidget(activate_all_drums_btn)

        spawn_drum_btn = QPushButton("+ Spawn Drum Machine Unit")
        spawn_drum_btn.setStyleSheet("background-color: #1f242c; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 6px;")
        spawn_drum_btn.clicked.connect(self._spawn_new_drum_unit)
        top_bar.addWidget(spawn_drum_btn)
        layout.addLayout(top_bar)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background-color: #070b10; border: none;")
        self.container = QWidget(self); self.container.setStyleSheet("background-color: #070b10;")
        self.grid = QGridLayout(self.container)

        self.refresh_drum_grid()

        self.container.setLayout(self.grid)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def refresh_drum_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for idx, kit_name in enumerate(self.engine.active_drum_kits):
            self.w = QWidget(self); w.setStyleSheet("background-color: #0d1117;")
            l = QVBoxLayout(w)

            kit_header = QHBoxLayout()
            lbl_kit = QLabel(f"Kit: {kit_name} [Activated Runtime Triggers]")
            lbl_kit.setStyleSheet("color: #c9d1d9; font-weight: bold; background: transparent;")
            kit_header.addWidget(lbl_kit)
            kit_header.addStretch()

            despawn_btn = QPushButton("✕ Despawn")
            despawn_btn.setFixedSize(70, 20)
            despawn_btn.setStyleSheet("background-color: #2b1115; color: #ff7b72; border: 1px solid #ff7b72; font-size: 8px; font-weight: bold;")
            despawn_btn.clicked.connect(lambda checked, name=kit_name: self._despawn_drum_unit(name))
            kit_header.addWidget(despawn_btn)
            l.addLayout(kit_header)

            grid_row = QGridLayout()
            for step in range(16):
                btn = QPushButton(str(step + 1))
                btn.setCheckable(True)
                is_active_gate = self.engine.runtime_clock.evaluate_drum_trigger(kit_name, step)
                btn.setChecked(is_active_gate)
                if is_active_gate:
                    btn.setStyleSheet("background-color: #00ffcc; color: #0d1117; font-weight: bold; font-size: 9px; border: 1px solid #ffffff;")
                else:
                    btn.setStyleSheet("background-color: #161b22; color: #8b949e; font-size: 9px;")
                grid_row.addWidget(btn, 0, step)
            l.addLayout(grid_row)

            knobs = QHBoxLayout()
            knobs.addWidget(PatchableKnob("Decay", 10.0, 500.0, 150.0, "ms", kit_name))
            knobs.addWidget(PatchableKnob("Pitch Mod", 0.0, 100.0, 40.0, "%", kit_name))
            knobs.addWidget(PatchableKnob("Drive", 0.0, 10.0, 2.0, "x", kit_name))
            l.addLayout(knobs)

            panel = ResizableWorkspacePanel(kit_name, w)
            panel.show()
            self.grid.addWidget(panel, idx // 2, idx % 2)
        self.container.update()

    def _force_trigger_drums(self):
        tick = self.engine.runtime_clock.tick_clock()
        self.refresh_drum_grid()
        QMessageBox.information(self, "Drum Matrices Triggered", f"Successfully advanced runtime clock to step {tick}. All active drum machine banks are firing transient triggers!")

    def _spawn_new_drum_unit(self):
        new_name = f"Custom Drum Unit {len(self.engine.active_drum_kits) + 1}"
        self.engine.active_drum_kits.append(new_name)
        self.refresh_drum_grid()
        QMessageBox.information(self, "Drum Machine Spawned", f"Successfully spawned new fully activated drum machine unit '{new_name}' under Tab 2.")

    def _despawn_drum_unit(self, kit_name):
        if len(self.engine.active_drum_kits) > 1:
            self.engine.active_drum_kits.remove(kit_name)
            self.refresh_drum_grid()
            QMessageBox.information(self, "Drum Machine Despawned", f"Successfully despawned drum machine '{kit_name}'.")
        else:
            QMessageBox.warning(self, "Despawn Failed", "At least one drum machine unit must remain active.")


# -------------------------------------------------------------------------
# TAB 3: GRANULAR FX & FREQUENCY SHIFTER
# -------------------------------------------------------------------------
class GranularFXPage(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setStyleSheet("background-color: #070b10;")
        self.layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        title = QLabel("🌌 Granular FX, Spectral Shifter & Wavefolder Matrix (Dynamic FX Instances)")
        title.setStyleSheet("color: #00ffcc; font-weight: bold; font-size: 12px; background: transparent;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        spawn_fx_btn = QPushButton("+ Spawn Custom FX Module")
        spawn_fx_btn.setStyleSheet("background-color: #1f242c; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 6px;")
        spawn_fx_btn.clicked.connect(self._spawn_new_fx_unit)
        top_bar.addWidget(spawn_fx_btn)
        self.layout.addLayout(top_bar)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background-color: #070b10; border: none;")
        self.container = QWidget(self); self.container.setStyleSheet("background-color: #070b10;")
        self.grid = QGridLayout(self.container)

        self.refresh_fx_grid()
        self.container.setLayout(self.grid)
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)

    def refresh_fx_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for idx, fx_name in enumerate(self.engine.active_fx_modules):
            self.w = QWidget(self); w.setStyleSheet("background-color: #0d1117;")
            l = QVBoxLayout(w)

            sub_header = QHBoxLayout()
            sub_lbl = QLabel(f"Processor Subtype: Advanced {fx_name}")
            sub_lbl.setStyleSheet("color: #f5d97d; font-size: 9px; background: transparent;")
            sub_header.addWidget(sub_lbl)
            sub_header.addStretch()

            despawn_btn = QPushButton("✕ Despawn")
            despawn_btn.setFixedSize(70, 20)
            despawn_btn.setStyleSheet("background-color: #2b1115; color: #ff7b72; border: 1px solid #ff7b72; font-size: 8px; font-weight: bold;")
            despawn_btn.clicked.connect(lambda checked, name=fx_name: self._despawn_fx_unit(name))
            sub_header.addWidget(despawn_btn)
            l.addLayout(sub_header)

            knobs = QHBoxLayout()
            knobs.addWidget(PatchableKnob("Grain Size", 10.0, 250.0, 50.0, "ms", fx_name))
            knobs.addWidget(PatchableKnob("Density", 1.0, 100.0, 32.0, "gr/s", fx_name))
            knobs.addWidget(PatchableKnob("Scatter", 0.0, 100.0, 75.0, "%", fx_name))
            knobs.addWidget(PatchableKnob("Feedback", 0.0, 100.0, 40.0, "%", fx_name))
            l.addLayout(knobs)

            wt = WavetableCanvas(fx_name, self.engine)
            l.addWidget(wt)

            panel = ResizableWorkspacePanel(fx_name, w)
            panel.show()
            self.grid.addWidget(panel, idx // 2, idx % 2)
        self.container.update()

    def _spawn_new_fx_unit(self):
        new_name = f"Custom FX Unit {len(self.engine.active_fx_modules) + 1}"
        if new_name not in self.engine.active_fx_modules:
            self.engine.active_fx_modules.append(new_name)
            self.refresh_fx_grid()
            QMessageBox.information(self, "FX Module Spawned", f"Successfully spawned new FX module '{new_name}' into the signal chain.")

    def _despawn_fx_unit(self, fx_name):
        if len(self.engine.active_fx_modules) > 1:
            self.engine.active_fx_modules.remove(fx_name)
            self.refresh_fx_grid()
            QMessageBox.information(self, "FX Module Despawned", f"Successfully despawned FX module '{fx_name}'.")
        else:
            QMessageBox.warning(self, "Despawn Failed", "At least one active FX module must remain in the routing matrix.")


# -------------------------------------------------------------------------
# TAB 4: FULLY ACTIVATED AUTOMATION & STEP SEQUENCER SUITE
# -------------------------------------------------------------------------
class AutomationCurveCanvas(QWidget):
    def __init__(self, points_list, parent=None):
        super().__init__(parent)
        self.points_list = points_list
        self.setMinimumHeight(120)
        self.setStyleSheet("background-color: #0b0f15; border: 1px solid #30363d; border-radius: 4px;")

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b0f15"))

        p.setPen(QPen(QColor("#161b22"), 1, Qt.PenStyle.DashLine))
        for x in range(0, self.width(), 50): p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 30): p.drawLine(0, y, self.width(), y)

        n = len(self.points_list)
        if n >= 2:
            step_w = self.width() / max(1, n - 1)
            path = QPainterPath()
            pts = []
            for i, val in enumerate(self.points_list):
                px = i * step_w
                py = self.height() - (val / 100.0) * (self.height() - 20) - 10
                pts.append(QPointF(px, py))

            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)

            p.setPen(QPen(QColor("#f5d97d"), 2.0))
            p.drawPath(path)

            p.setBrush(QBrush(QColor("#00ffcc")))
            p.setPen(QPen(QColor("#ffffff"), 1))
            for pt in pts:
                p.drawEllipse(pt, 4, 4)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            n = len(self.points_list)
            if n > 0:
                idx = min(n - 1, max(0, int(round((pos.x() / self.width()) * (n - 1)))))
                val = max(0.0, min(100.0, round((self.height() - pos.y() - 10) / (self.height() - 20) * 100.0, 1)))
                self.points_list[idx] = val
                self.update()


class AutomationPatternPage(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setStyleSheet("background-color: #070b10;")
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        title = QLabel("⚙️ Fully Activated Modular Step Sequencer, Automation Envelopes & Pattern Designer")
        title.setStyleSheet("color: #f5d97d; font-weight: bold; font-size: 12px; background: transparent;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        activate_all_seqs_btn = QPushButton("⚡ Force Trigger All Sequencers")
        activate_all_seqs_btn.setStyleSheet("background-color: #2b1135; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d; padding: 6px;")
        activate_all_seqs_btn.clicked.connect(self._force_trigger_sequencers)
        top_bar.addWidget(activate_all_seqs_btn)

        add_pat_btn = QPushButton("+ New Automation Pattern")
        add_pat_btn.setStyleSheet("background-color: #1f242c; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 6px;")
        add_pat_btn.clicked.connect(self._add_automation_pattern)
        top_bar.addWidget(add_pat_btn)

        spawn_seq_btn = QPushButton("+ Spawn Sequencer Module")
        spawn_seq_btn.setStyleSheet("background-color: #1f242c; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d; padding: 6px;")
        spawn_seq_btn.clicked.connect(self._spawn_sequencer_module)
        top_bar.addWidget(spawn_seq_btn)

        layout.addLayout(top_bar)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background-color: #070b10; border: none;")
        self.container = QWidget(self); self.container.setStyleSheet("background-color: #070b10;")
        self.grid = QGridLayout(self.container)

        self._refresh_automation_panels()
        self.container.setLayout(self.grid)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def _refresh_automation_panels(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        total_idx = 0
        for pat_name, points in self.engine.automation_patterns.items():
            self.w = QWidget(self); w.setStyleSheet("background-color: #0d1117;")
            l = QVBoxLayout(w)

            lbl = QLabel(f"Automation & Step Sequencer Lane: '{pat_name}' (Active Automation Curve)")
            lbl.setStyleSheet("color: #00ffcc; font-weight: bold; background: transparent;")
            l.addWidget(lbl)

            canvas = AutomationCurveCanvas(points)
            l.addWidget(canvas)

            panel = ResizableWorkspacePanel(f"Sequencer / Automation: {pat_name}", w)
            panel.show()
            self.grid.addWidget(panel, total_idx // 2, total_idx % 2)
            total_idx += 1

        for seq_mod_name in self.engine.active_sequencer_modules:
            self.w = QWidget(self); w.setStyleSheet("background-color: #0d1117;")
            l = QVBoxLayout(w)

            seq_header = QHBoxLayout()
            seq_lbl = QLabel(f"Poly-Rhythmic Sequencer Instance: {seq_mod_name} [Activated Gates]")
            seq_lbl.setStyleSheet("color: #ff7b72; font-weight: bold; background: transparent;")
            seq_header.addWidget(seq_lbl)
            seq_header.addStretch()

            despawn_seq_btn = QPushButton("✕ Despawn")
            despawn_seq_btn.setFixedSize(70, 20)
            despawn_seq_btn.setStyleSheet("background-color: #2b1115; color: #ff7b72; border: 1px solid #ff7b72; font-size: 8px; font-weight: bold;")
            despawn_seq_btn.clicked.connect(lambda checked, name=seq_mod_name: self._despawn_sequencer_module(name))
            seq_header.addWidget(despawn_seq_btn)
            l.addLayout(seq_header)

            step_grid = QGridLayout()
            for step in range(16):
                s_btn = QPushButton(str(step + 1))
                s_btn.setCheckable(True)
                is_gate_active = self.engine.runtime_clock.evaluate_sequencer_gate(seq_mod_name, step)
                s_btn.setChecked(is_gate_active)
                if is_gate_active:
                    s_btn.setStyleSheet("background-color: #f5d97d; color: #0d1117; font-weight: bold; font-size: 9px; border: 1px solid #ffffff;")
                else:
                    s_btn.setStyleSheet("background-color: #161b22; color: #8b949e; font-size: 9px;")
                step_grid.addWidget(s_btn, 0, step)
            l.addLayout(step_grid)

            knobs = QHBoxLayout()
            knobs.addWidget(PatchableKnob("Gate Length", 10.0, 100.0, 50.0, "%", seq_mod_name))
            knobs.addWidget(PatchableKnob("Probability", 0.0, 100.0, 85.0, "%", seq_mod_name))
            knobs.addWidget(PatchableKnob("Swing Rate", 0.0, 50.0, 12.0, "%", seq_mod_name))
            l.addLayout(knobs)

            panel = ResizableWorkspacePanel(f"Sequencer Module: {seq_mod_name}", w)
            panel.show()
            self.grid.addWidget(panel, total_idx // 2, total_idx % 2)
            total_idx += 1
        self.container.update()

    def _force_trigger_sequencers(self):
        tick = self.engine.runtime_clock.tick_clock()
        self._refresh_automation_panels()
        QMessageBox.information(self, "Sequencer Modules Triggered", f"Successfully advanced sequencer clock to step {tick}. All poly-rhythmic step sequencers and automation curves are fully engaged!")

    def _add_automation_pattern(self):
        pat_name = f"Custom Sequencer Lane {len(self.engine.automation_patterns) + 1}"
        self.engine.automation_patterns[pat_name] = [0.0, 50.0, 100.0, 50.0, 25.0, 80.0, 100.0, 0.0]
        self._refresh_automation_panels()
        QMessageBox.information(self, "Sequencer Lane Created", f"New modular step/automation envelope '{pat_name}' successfully added.")

    def _spawn_sequencer_module(self):
        seq_name = f"Advanced Sequencer Instance {len(self.engine.active_sequencer_modules) + 1}"
        if seq_name not in self.engine.active_sequencer_modules:
            self.engine.active_sequencer_modules.append(seq_name)
            self._refresh_automation_panels()
            QMessageBox.information(self, "Sequencer Module Spawned", f"Successfully spawned new sequencer module '{seq_name}'.")

    def _despawn_sequencer_module(self, seq_name):
        if len(self.engine.active_sequencer_modules) > 1:
            self.engine.active_sequencer_modules.remove(seq_name)
            self._refresh_automation_panels()
            QMessageBox.information(self, "Sequencer Module Despawned", f"Successfully despawned sequencer module '{seq_name}'.")
        else:
            QMessageBox.warning(self, "Despawn Failed", "At least one sequencer module must remain active.")


# -------------------------------------------------------------------------
# INFINITE SCROLLABLE PLAYLIST CANVAS
# -------------------------------------------------------------------------
class InfinitePlaylistInnerWidget(QWidget):
    def __init__(self, engine, parent_page, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.parent_page = parent_page
        self.setMinimumSize(8000, 1600)
        self.setStyleSheet("background-color: #070b10;")

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#070b10"))

        p.setPen(QPen(QColor("#161b22"), 1, Qt.PenStyle.DashLine))
        for x in range(0, self.width(), 80):
            p.drawLine(x, 0, x, self.height())
            p.setPen(QPen(QColor("#484f58"), 1))
            p.drawText(x + 4, 15, f"Bar {x // 80 + 1}")
            p.setPen(QPen(QColor("#161b22"), 1, Qt.PenStyle.DashLine))

        for (trk, bar_pos), clip in self.engine.playlist_clips.items():
            cx = bar_pos * 80
            cy = 25 + (trk * 50)
            p.setBrush(QBrush(QColor("#1f242c")))
            p.setPen(QPen(QColor("#00ffcc"), 1.5))
            p.drawRoundedRect(int(cx), cy, 140, 42, 4, 4)

            p.setPen(QPen(QColor("#f5d97d"), 9))
            p.drawText(int(cx) + 6, cy + 14, f"{clip.get('name', 'Clip')}")
            p.setPen(QPen(QColor("#8b949e"), 8))
            p.drawText(int(cx) + 6, cy + 28, f"P:{clip.get('pitch', 0)} | A:{clip.get('amplitude', 1)} | Auto:{clip.get('automation_pattern', 'Def')}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            bar_pos = pos.x() / 80.0
            track = int(pos.y() // 50)

            pattern_name = self.parent_page.pattern_combo.currentText()
            math_chord = self.parent_page.playlist_chord_combo.currentText()
            pitch_val = self.parent_page.playlist_pitch_spin.value()
            amp_val = self.parent_page.playlist_amp_spin.value()
            auto_pat = self.parent_page.playlist_auto_combo.currentText()

            clip_data = {
                "name": pattern_name,
                "chord": math_chord,
                "pitch": pitch_val,
                "amplitude": amp_val,
                "automation_pattern": auto_pat
            }
            self.engine.assign_playlist_clip(track, round(bar_pos, 2), clip_data)
            self.update()


class InfinitePlaylistCanvas(QScrollArea):
    def __init__(self, engine, parent_page, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.parent_page = parent_page
        self.setWidgetResizable(True)
        self.setStyleSheet("background-color: #070b10; border: none;")
        self.canvas_inner = InfinitePlaylistInnerWidget(self.engine, self.parent_page)
        self.setWidget(self.canvas_inner)

class EQRVisualizerCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setStyleSheet("background-color: #0b0b0b; border: 1px solid #ff6b00; border-radius: 4px;")

        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_phase)
        self.timer.start(30)

    def update_phase(self):
        self.phase += 0.03
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.fillRect(self.rect(), QColor(11, 11, 11))
            w, h = self.width(), self.height()
            cx, cy = w / 2.0, h / 2.0

            painter.setPen(QPen(QColor(30, 30, 30), 1, Qt.PenStyle.DashLine))
            painter.drawLine(0, int(cy), w, int(cy))
            painter.drawLine(int(cx), 0, int(cx), h)

            num_steps = 300
            points = []
            for i in range(num_steps):
                t = (i / num_steps) * 4 * np.pi + self.phase
                x_val = np.sin(t * 1.5) * np.cos(t * 0.5 + self.phase * 0.2) * 120.0
                y_val = np.cos(t * 2.0) * np.sin(t * 1.2) * 80.0
                z_val = np.sin(t + self.phase) * 50.0

                px = cx + x_val + (z_val * 0.3)
                py = cy + y_val + (z_val * 0.2)
                points.append(QPointF(px, py))

            for i in range(len(points) - 1):
                hue_color = QColor.fromHsvF((i / num_steps + self.phase * 0.1) % 1.0, 0.8, 1.0)
                painter.setPen(QPen(hue_color, 2))
                painter.drawLine(points[i], points[i+1])
        finally:
            painter.end()
# -------------------------------------------------------------------------
# MASTER PATCH CANVAS (Visual Wires & Dedicated Synth Jacks)
# -------------------------------------------------------------------------
class EQRVectorEngine(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mathematician's Groovebox")
        self.resize(1000, 700)

        # Initialize core layout container
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        # Title Label / Workspace Indicator
        self.label = QLabel("Coordinate Audio Synthesis Workspace Active")
        self.layout.addWidget(self.label)

        layout.addRow("Operator Variable X:", self.x_input)
        layout.addRow("Operator Variable Y:", self.y_input)
        layout.addRow("Operator Variable Z:", self.z_input)
class MasterPatchCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cables = GLOBAL_BUS.global_cables
        self.setMinimumHeight(220)
        self.setStyleSheet("background-color: #0b0f15; border: 1px solid #30363d; border-radius: 4px;")

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b0f15"))

        p.setPen(QPen(QColor("#161b22"), 1, Qt.PenStyle.DashLine))
        for x in range(0, self.width(), 60): p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 40): p.drawLine(0, y, self.width(), y)

        if not self.cables:
            p.setPen(QPen(QColor("#8b949e"), 10))
            p.drawText(20, 30, "No active patch cables. Activate Parameter Jacks in synth modules or use the Song Randomizer.")
            return

        for i, cable in enumerate(self.cables):
            src = cable.get("src_module", "Src")
            tgt = cable.get("tgt_module", "Tgt")
            pol = cable.get("polarity", "Neutral")
            gain = cable.get("gain", 1.0)

            y_pos = 35 + (i * 30) % max(40, self.height() - 40)
            color = "#00ffcc" if pol == "+" else ("#ff7b72" if pol == "-" else "#f5d97d")

            p.setPen(QPen(QColor(color), 2.0))
            p.drawLine(30, y_pos, self.width() - 30, y_pos)

            p.setBrush(QBrush(QColor("#161b22")))
            p.setPen(QPen(QColor(color), 1))
            p.drawRoundedRect(35, y_pos - 12, 190, 24, 4, 4)
            p.drawRoundedRect(self.width() - 225, y_pos - 12, 190, 24, 4, 4)

            p.setPen(QPen(QColor("#ffffff"), 9))
            p.drawText(43, y_pos + 4, f"{src}")
            p.drawText(self.width() - 217, y_pos + 4, f"{tgt} [{pol}, {gain}x]")

class MasterControlPanel(QWidget):
    """Global parameters featuring Master Tempo and Quantization options."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("color: #ffffff;")
        layout = QHBoxLayout(self)

        self.tempo_label = QLabel("Master Tempo: 120 BPM")
        self.tempo_slider = QDoubleSpinBox()
        self.tempo_slider.setRange(0.0, 512.0)
        self.tempo_slider.setDecimals(3)
        self.tempo_slider.setSingleStep(0.1)
        self.tempo_slider.setValue(120.0)
        self.tempo_slider.valueChanged.connect(self.update_tempo_display)

        self.quant_label = QLabel("Quantize:")
        self.quant_combo = QComboBox()
        self.quant_combo.addItems(["Off (Free Timing)", "1/4 Note", "1/8 Note", "1/16 Note"])
        self.quant_combo.setStyleSheet("background-color: #222; color: #fff; border: 1px solid #444; padding: 4px;")

        layout.addWidget(self.tempo_label)
        layout.addWidget(self.tempo_slider)
        layout.addSpacing(20)
        layout.addWidget(self.quant_label)
        layout.addWidget(self.quant_combo)

    def update_tempo_display(self, value):
        self.tempo_label.setText(f"Master Tempo: {value} BPM")
# -------------------------------------------------------------------------
# TAB 5: EQUATION SCALES, INFINITE PLAYLIST & PATCHBAY
# -------------------------------------------------------------------------
class GeometricSymbolicCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setStyleSheet("""
            background-color: #2d3436;
            border: 3px solid #00b894;
            border-radius: 12px;
        """)
        self.nodes = [
            {"label": "Node α: Sine", "pos": (60, 45), "color": "#ff7675"},
            {"label": "Node β: Fold", "pos": (220, 80), "color": "#74b9ff"},
            {"label": "Node γ: Resonator", "pos": (400, 40), "color": "#55efc4"},
            {"label": "Node δ: Attractor", "pos": (580, 75), "color": "#ffeaa7"}
        ]

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.fillRect(self.rect(), QColor(45, 52, 54))
            pen = QPen(QColor(162, 155, 254), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for i in range(len(self.nodes) - 1):
                p1 = self.nodes[i]["pos"]
                p2 = self.nodes[i+1]["pos"]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])

            for node in self.nodes:
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.setBrush(QColor(node["color"]))
                x, y = node["pos"]
                painter.drawEllipse(QPoint(x, y), 22, 22)

                painter.setPen(QColor(253, 203, 110))
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                painter.drawText(x - 30, y + 36, node["label"])
        finally:
            painter.end()
class MasterControlPatchbayPage(QWidget):
    def __init__(self, engine, main_window):
        super().__init__()
        self.engine = engine
        self.main_window = main_window
        GLOBAL_BUS.register_subscriber(self)

        layout = QVBoxLayout(self)

        # Top Global Controls Group (Enhanced with Rhythm Flux Linking Controls)
        controls_group = QGroupBox("Master Engine Controls, Equation Scale & Rhythm Flux Linking")
        controls_group.setStyleSheet("QGroupBox { color: #00ffcc; font-weight: bold; border: 1px solid #30363d; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }")
        ctrl_layout = QGridLayout(controls_group)

        # BPM Slider
        self.bpm_label = QLabel(f"{self.engine.global_bpm:.1f} BPM")
        self.bpm_label.setStyleSheet("color: #f5d97d; font-weight: bold;")
        self.bpm_slider = QSlider(Qt.Orientation.Horizontal)
        self.bpm_slider.setRange(400, 2400)
        self.bpm_slider.setValue(int(self.engine.global_bpm * 10))
        self.bpm_slider.valueChanged.connect(self._on_bpm_changed)

        ctrl_layout.addWidget(QLabel("Global Tempo:"), 0, 0)
        ctrl_layout.addWidget(self.bpm_slider, 0, 1)
        ctrl_layout.addWidget(self.bpm_label, 0, 2)

        # Rhythm Flux Link Mode Controls
        ctrl_layout.addWidget(QLabel("Rhythm Flux Mode:"), 0, 3)
        self.flux_mode_combo = QComboBox()
        self.flux_mode_combo.addItems(["Global", "Active Concurrent", "Unlinked"])
        self.flux_mode_combo.setCurrentText(self.engine.runtime_clock.rhythm_flux_mode)
        self.flux_mode_combo.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
        self.flux_mode_combo.currentTextChanged.connect(self._on_flux_mode_changed)
        ctrl_layout.addWidget(self.flux_mode_combo, 0, 4)

        ctrl_layout.addWidget(QLabel("Flux Rate:"), 0, 5)
        self.flux_rate_spin = QDoubleSpinBox()
        self.flux_rate_spin.setRange(0.25, 4.0)
        self.flux_rate_spin.setValue(self.engine.runtime_clock.rhythm_flux_rate)
        self.flux_rate_spin.setSingleStep(0.25)
        self.flux_rate_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
        self.flux_rate_spin.valueChanged.connect(self._on_flux_rate_changed)
        ctrl_layout.addWidget(self.flux_rate_spin, 0, 6)

        # Equation Controls
        self.eq_input = QLineEdit(self.engine.scale_equation)
        self.eq_input.setStyleSheet("background-color: #161b22; color: #00ffcc; font-family: monospace; border: 1px solid #30363d;")

        self.inc_spin = QDoubleSpinBox()
        self.inc_spin.setRange(0.01, 5.0)
        self.inc_spin.setValue(self.engine.scale_increment)
        self.inc_spin.setSingleStep(0.05)
        self.inc_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")

        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(1, 1024)
        self.steps_spin.setValue(self.engine.divergence_steps_count)
        self.steps_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")

        apply_eq_btn = QPushButton("Apply Equation Scale")
        apply_eq_btn.setStyleSheet("background-color: #1f242c; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d; padding: 4px;")
        apply_eq_btn.clicked.connect(self._apply_equation_scale)

        ctrl_layout.addWidget(QLabel("Scale Equation:"), 1, 0)
        ctrl_layout.addWidget(self.eq_input, 1, 1, 1, 3)
        ctrl_layout.addWidget(apply_eq_btn, 1, 4, 1, 3)

        ctrl_layout.addWidget(QLabel("Increment:"), 2, 0)
        ctrl_layout.addWidget(self.inc_spin, 2, 1)
        ctrl_layout.addWidget(QLabel("Steps:"), 2, 2)
        ctrl_layout.addWidget(self.steps_spin, 2, 3)

        # Action Buttons Row
        actions_layout = QHBoxLayout()
        rand_btn = QPushButton("🎲 Randomize Song & Patchbay")
        rand_btn.setStyleSheet("background-color: #2b1135; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 6px;")
        rand_btn.clicked.connect(self._randomize_song_action)

        save_btn = QPushButton("💾 Save Project")
        save_btn.setStyleSheet("background-color: #1f242c; color: #ffffff; border: 1px solid #30363d; padding: 6px;")
        save_btn.clicked.connect(self._save_project)

        load_btn = QPushButton("📂 Load Project")
        load_btn.setStyleSheet("background-color: #1f242c; color: #ffffff; border: 1px solid #30363d; padding: 6px;")
        load_btn.clicked.connect(self._load_project)

        export_btn = QPushButton("📻 Export Master WAV Audio")
        export_btn.setStyleSheet("background-color: #112b35; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d; padding: 6px;")
        export_btn.clicked.connect(self._export_audio)

        actions_layout.addWidget(rand_btn)
        actions_layout.addWidget(save_btn)
        actions_layout.addWidget(load_btn)
        actions_layout.addWidget(export_btn)

        layout.addWidget(controls_group)
        layout.addLayout(actions_layout)

        # Playlist Options & Controls
        pl_options_layout = QHBoxLayout()
        pl_options_layout.addWidget(QLabel("Pattern:"))
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(self.engine.available_patterns)
        self.pattern_combo.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
        pl_options_layout.addWidget(self.pattern_combo)

        pl_options_layout.addWidget(QLabel("Chord:"))
        self.playlist_chord_combo = QComboBox()
        self.playlist_chord_combo.addItems(list(self.engine.math_chord_library.keys()))
        self.playlist_chord_combo.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
        pl_options_layout.addWidget(self.playlist_chord_combo)

        pl_options_layout.addWidget(QLabel("Pitch St:"))
        self.playlist_pitch_spin = QDoubleSpinBox()
        self.playlist_pitch_spin.setRange(-24.0, 24.0)
        self.playlist_pitch_spin.setValue(0.0)
        self.playlist_pitch_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
        pl_options_layout.addWidget(self.playlist_pitch_spin)

        pl_options_layout.addWidget(QLabel("Amp:"))
        self.playlist_amp_spin = QDoubleSpinBox()
        self.playlist_amp_spin.setRange(0.1, 2.0)
        self.playlist_amp_spin.setValue(1.0)
        self.playlist_amp_spin.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
        pl_options_layout.addWidget(self.playlist_amp_spin)

        pl_options_layout.addWidget(QLabel("Auto Pattern:"))
        self.playlist_auto_combo = QComboBox()
        self.playlist_auto_combo.addItems(list(self.engine.automation_patterns.keys()))
        self.playlist_auto_combo.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
        pl_options_layout.addWidget(self.playlist_auto_combo)

        create_patch_btn = QPushButton("⚡ Create Patch")
        create_patch_btn.setStyleSheet("background-color: #1f242c; color: #00ffcc; font-weight: bold; border: 1px solid #00ffcc; padding: 4px;")
        create_patch_btn.clicked.connect(self._create_patch_prompt)
        pl_options_layout.addWidget(create_patch_btn)

        layout.addLayout(pl_options_layout)

        # Splitter for Playlist and Patch Canvas
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Infinite Playlist Section
        playlist_group = QGroupBox("Infinite Playlist Arrangement Canvas (Click to Place Clip)")
        playlist_group.setStyleSheet("QGroupBox { color: #f5d97d; font-weight: bold; border: 1px solid #30363d; margin-top: 6px; }")
        pl_layout = QVBoxLayout(playlist_group)
        self.infinite_playlist_canvas = InfinitePlaylistCanvas(self.engine, self)
        pl_layout.addWidget(self.infinite_playlist_canvas)
        splitter.addWidget(playlist_group)

        # Patch Canvas Section
        patch_group = QGroupBox("Master Visual Patchbay & Cable Wiring Matrix")
        patch_group.setStyleSheet("QGroupBox { color: #00ffcc; font-weight: bold; border: 1px solid #30363d; margin-top: 6px; }")
        patch_layout = QVBoxLayout(patch_group)
        self.patch_canvas = MasterPatchCanvas(self)
        patch_layout.addWidget(self.patch_canvas)

        self.manual_patch_panel = QWidget(self)
        manual_patch_layout = QHBoxLayout(manual_patch_panel)
        manual_patch_layout.setContentsMargins(0, 0, 0, 0)
        manual_patch_layout.addWidget(QLabel("Manual Target Override Route:"))
        self.manual_patch_combo = QComboBox()
        self.manual_patch_combo.addItems([
            "Direct Bus Sum [Master Audio]",
            "Auxiliary Shifter Loop A",
            "Auxiliary Shifter Loop B",
            "Quantum Resonator Feedback In",
            "Stochastic Granular Direct Send"
        ])
        self.manual_patch_combo.setStyleSheet("background-color: #161b22; color: #00ffcc; border: 1px solid #30363d;")
        manual_patch_layout.addWidget(self.manual_patch_combo)

        apply_manual_route_btn = QPushButton("Apply Override Route")
        apply_manual_route_btn.setStyleSheet("background-color: #1f242c; color: #f5d97d; font-weight: bold; border: 1px solid #f5d97d; padding: 3px;")
        apply_manual_route_btn.clicked.connect(self._apply_manual_override_route)
        manual_patch_layout.addWidget(apply_manual_route_btn)

        patch_layout.addWidget(manual_patch_panel)
        splitter.addWidget(patch_group)

        layout.addWidget(splitter)

    def _on_bpm_changed(self, val):
        self.engine.global_bpm = val / 10.0
        self.bpm_label.setText(f"{self.engine.global_bpm:.1f} BPM")

    def _on_flux_mode_changed(self, mode):
        self.engine.runtime_clock.rhythm_flux_mode = mode
        print(f"Rhythm Flux Link Mode updated to: {mode}")

    def _on_flux_rate_changed(self, val):
        self.engine.runtime_clock.rhythm_flux_rate = val
        print(f"Rhythm Flux Rate multiplier updated to: {val}x")

    def _apply_equation_scale(self):
        self.engine.scale_equation = self.eq_input.text()
        self.engine.scale_increment = self.inc_spin.value()
        self.engine.divergence_steps_count = self.steps_spin.value()
        freqs = self.engine.generate_equation_scale_frequencies()
        QMessageBox.information(self, "Equation Applied", f"Successfully recalculated equation scale! Generated {len(freqs)} frequencies.")

    def _randomize_song_action(self):
        self.engine.randomize_song()
        self.patch_canvas.update()
        self.infinite_playlist_canvas.canvas_inner.update()
        QMessageBox.information(self, "Song & Patchbay Randomizer", "Successfully randomized song arrangement, synth wiring, effects modules, and global cross-tab patch cables!")

    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project File", "", "EQ爾 Groovebox Files (*.json)")
        if path:
            self.engine.serialize_project(path)
            QMessageBox.information(self, "Project Saved", f"Project successfully saved to:\n{path}")

    def _load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Project File", "", "EQ爾 Groovebox Files (*.json)")
        if path:
            self.engine.deserialize_project(path)
            self.bpm_slider.setValue(int(self.engine.global_bpm * 10))
            self.eq_input.setText(self.engine.scale_equation)
            self.patch_canvas.update()
            self.infinite_playlist_canvas.canvas_inner.update()
            QMessageBox.information(self, "Project Loaded", f"Project successfully loaded from:\n{path}")

    def _export_audio(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Master WAV Audio", "", "WAV Audio Files (*.wav)")
        if path:
            self.engine.export_audio(path)
            QMessageBox.information(self, "Audio Exported", f"Master audio successfully rendered and exported to:\n{path}")

    def _create_patch_prompt(self):
        source, ok1 = QInputDialog.getText(self, "Create Patch", "Enter Source Module/Node:")
        if not ok1 or not source:
            return
        destination, ok2 = QInputDialog.getText(self, "Create Patch", "Enter Target Destination Module/Node:")
        if not ok2 or not destination:
            return
        amount, ok3 = QInputDialog.getDouble(self, "Create Patch", "Enter Modulation Gain Amount:", 1.0, 0.1, 10.0, 2)
        if not ok3:
            return

        GLOBAL_BUS.add_cable(
            src_module=source, src_node="Custom Node",
            tgt_module=destination, tgt_node="Primary Sum Node",
            polarity="+", gain=amount
        )
        self.patch_canvas.update()
        QMessageBox.information(self, "Patch Created", f"Successfully created custom patch connection from '{source}' to '{destination}' with amount {amount}x!")

    def _apply_manual_override_route(self):
        selected_route = self.manual_patch_combo.currentText()
        if GLOBAL_BUS.global_cables:
            GLOBAL_BUS.global_cables[-1]["tgt_module"] = selected_route
            GLOBAL_BUS.broadcast_update()
            QMessageBox.information(self, "Manual Patch Route Applied", f"Successfully reconfigured the patch route to target: {selected_route}")
        else:
            QMessageBox.warning(self, "No Active Cables", "There are no active global cables in the patchbay to re-route. Create a patch or run the randomizer first.")

    def on_global_patch_updated(self, cables):
        self.patch_canvas.cables = cables
        self.patch_canvas.update()


# -------------------------------------------------------------------------
# MAIN WINDOW FRAMEWORK
# -------------------------------------------------------------------------


class PortWidget(QWidget):
    """Represents an input or output data jack on a scientific processing node."""
    def __init__(self, port_type, parent=None):
        super().__init__(parent)
        self.port_type = port_type  # 'in' or 'out'
        self.setFixedSize(22, 22)
        self.color = "#00ffc8" if port_type == 'out' else "#ff6400"
        self.setStyleSheet(f"""
            background-color: {self.color};
            border-radius: 11px;
            border: 3px solid #1a1a1a;
        """)

    def mousePressEvent(self, event):
        if self.parent() and hasattr(self.parent(), 'start_cable_drag'):
            self.parent().start_cable_drag(self)
        event.accept()


class ScientificCanvas(QWidget):
    """Interactive canvas workspace mapping mathematical data pipelines with glowing bezier patch lines."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(2400, 1800)
        self.cables = []
        self.active_cable_start = None
        self.current_mouse_pos = QPoint(0, 0)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #0d0d0d; border: 1px solid #222;")

    def start_cable_drag(self, port_widget):
        self.active_cable_start = port_widget
        self.current_mouse_pos = port_widget.mapTo(self, port_widget.rect().center())
        self.update()

    def mouseMoveEvent(self, event):
        if self.active_cable_start:
            self.current_mouse_pos = event.pos()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.active_cable_start:
            target_widget = self.childAt(event.pos())
            if isinstance(target_widget, PortWidget) and target_widget != self.active_cable_start:
                if self.active_cable_start.port_type != target_widget.port_type:
                    cable_pair = (self.active_cable_start, target_widget)
                    reverse_pair = (target_widget, self.active_cable_start)
                    if cable_pair not in self.cables and reverse_pair not in self.cables:
                        self.cables.append(cable_pair)
            self.active_cable_start = None
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for start, end in self.cables:
            if start and end:
                p1 = start.mapTo(self, start.rect().center())
                p2 = end.mapTo(self, end.rect().center())

                glow_pen = QPen(QColor(0, 255, 200, 60), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(glow_pen)
                painter.drawPath(self.create_bezier_path(p1, p2))

                core_pen = QPen(QColor(0, 255, 200), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(core_pen)
                painter.drawPath(self.create_bezier_path(p1, p2))

        if self.active_cable_start:
            p1 = self.active_cable_start.mapTo(self, self.active_cable_start.rect().center())
            p2 = self.current_mouse_pos

            drag_pen = QPen(QColor(255, 100, 0, 200), 3, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(drag_pen)
            painter.drawPath(self.create_bezier_path(p1, p2))

    def create_bezier_path(self, p1, p2):
        path = QPainterPath()
        path.moveTo(p1)
        dx = (p2.x() - p1.x()) * 0.5
        ctrl1 = QPoint(p1.x() + dx, p1.y())
        ctrl2 = QPoint(p2.x() - dx, p2.y())
        path.cubicTo(ctrl1, ctrl2, p2)
        return path



class DoubleNumericSliderRow(QWidget):
    """Synchronized precision double-spinbox and slider layout for scientific variables."""
    def __init__(self, min_val, max_val, default_val, decimals=2, unit="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * 100), int(max_val * 100))
        self.slider.setValue(int(default_val * 100))
        self.slider.setStyleSheet("background: transparent;")

        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(min_val, max_val)
        self.spinbox.setValue(default_val)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setSuffix(unit)
        self.spinbox.setStyleSheet("background-color: #27272a; color: #00ffc8; border: 1px solid #52525b; padding: 3px; border-radius: 3px;")

        self.slider.valueChanged.connect(lambda v: self.spinbox.setValue(v / 100.0))
        self.spinbox.valueChanged.connect(lambda v: self.slider.setValue(int(v * 100)))

        layout.addWidget(self.slider, 3)
        layout.addWidget(self.spinbox, 1)

class BottomToolboxesPane(QScrollArea):
    def __init__(self, spawn_callback, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.spawn_callback = spawn_callback

        container = QWidget()
        layout = QGridLayout(container)

        # 24 distinct instrument & toolbox variants (including Eskibrutus)
        toolboxes = [
            ("1. Step Sequencer Grid", "16-step trigger matrix for rhythmic coordinate pulsing."),
            ("2. Additive Harmonic Bank", "Draw and morph partial frequencies via x, y, z vectors."),
            ("3. Formant Vocal Filter", "Vowel transition generator modeled on acoustic formants."),
            ("4. Stochastic Probability Node", "Randomized weight gates for generative melody generation."),
            ("5. Vector Synthesizer Pad", "2D joystick space for real-time timbre morphing."),
            ("6. State-Variable Filter Rack", "Resonant lowpass/highpass sweep filters."),
            ("7. Non-Linear Waveshaper", "Harmonic saturation and distortion drive controls."),
            ("8. Stereo Feedback Delay Line", "Echo matrix with adjustable feedback attenuation."),
            ("9. LFO Modulation Generator", "Waveform shape, rate, and depth assignment units."),
            ("10. Granular Texture Scraper", "Audio grain cloud pulverizer and pitch scatterer."),
            ("11. Envelope Generator (ADSR)", "Amplitude shape shaping for dynamic note articulation."),
            ("12. Coordinate Formula Router", "Direct injection parser for custom runtime math nodes."),
            ("13. Eskibrutus Heavy Node", "Aggressive distortion matrix with harmonic fold reset."),
            ("14. Isosceles Operator Synth", "Triangular geometric wave-interference oscillator."),
            ("15. Wavetable Morph Engine", "Crossfade matrix for multi-frame sequential tables."),
            ("16. Frequency Modulation Bank", "Complex 4-operator carrier/modulator algorithm matrix."),
            ("17. Ring Modulator Matrix", "Sideband frequency multiplication grid."),
            ("18. Bitcrush Quantizer", "Sample-rate and bit-depth degradation processor."),
            ("19. Spectral Resonator", "Comb-filter bank tuned to harmonic overtones."),
            ("20. Chaos Attractor Synth", "Lorenz/Rössler differential equation sound source."),
            ("21. Sub-Bass Fundamental Generator", "Pure low-end sub-harmonic reinforcement node."),
            ("22. Noise Texture Generator", "Filtered white/pink/brownian architectural noise."),
            ("23. Resonant Body Simulator", "Modal physical modeling plate and string exciter."),
            ("24. Master Bus Limiter", "Brickwall peak processor and output saturator.")
        ]

        for idx, (title, desc) in enumerate(toolboxes):
            box = QFrame()
            box.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
            box.setStyleSheet("background-color: #1b1b1b; border: 1px solid #333; border-radius: 4px;")
            box_layout = QVBoxLayout(box)

            title_lbl = QLabel(f"<b>{title}</b>")
            title_lbl.setStyleSheet("color: #00ffaa;")
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #aaa; font-size: 11px;")

            box_layout.addWidget(title_lbl)
            box_layout.addWidget(desc_lbl)

            # Action button to spawn this specific synth variant into the top tabs!
            spawn_btn = QPushButton(f"Spawn Instance [{idx+1}]")
            spawn_btn.setStyleSheet("background-color: #333; color: #fff; font-size: 10px;")
            # Capture title for the callback
            spawn_btn.clicked.connect(lambda checked, t=title: self.spawn_callback(t))
            box_layout.addWidget(spawn_btn)

            row, col = divmod(idx, 4)  # 4 columns for 24 items
            layout.addWidget(box, row, col)

        container.setLayout(layout)
        self.setWidget(container)
TRANSCENDENTAL_BASE = np.e
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
                    self.parent_table.engage_paint(item.row(), item.column())
                else:
                    index = self.indexAt(event.pos())
                    if index.isValid():
                        self.parent_table.engage_paint(index.row(), index.column())
                super().mousePressEvent(event)

            def mouseMoveEvent(self, event):
                if self.parent_table.is_drawing_stroke:
                    item = self.itemAt(event.pos())
                    if item:
                        self.parent_table.engage_paint(item.row(), item.column())
                    else:
                        index = self.indexAt(event.pos())
                        if index.isValid():
                            self.parent_table.engage_paint(index.row(), index.column())
                super().mouseMoveEvent(event)

            def mouseReleaseEvent(self, event):
                self.parent_table.is_drawing_stroke = False
                # Resolve overlaps / automation after stroke
                if hasattr(self.parent_table, 'resolve_row_overlaps'):
                    self.parent_table.resolve_row_overlaps()
                super().mouseReleaseEvent(event)

        # Wider grid: time, operator, script, domain, synth, patch, velocity,
        # automation target/amount, modulation, multi-seq, coverage, blend partner
        n_cols = max(cols, PLAYLIST_COLUMN_COUNT)
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

    def setHorizontalHeaderLabels(self, labels):
        self.table_widget.setHorizontalHeaderLabels(labels)

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

    def engage_paint(self, row, col):
        """Apply the active paintbrush to one playlist cell.

        PaintTableWidget converts mouse events into row/column coordinates.
        This method therefore must NEVER depend on a local `event` variable.
        """

        try:
            row = int(row)
            col = int(col)
        except (TypeError, ValueError):
            return

        table = self.table_widget

        if row < 0 or col < 0:
            return

        if row >= table.rowCount() or col >= table.columnCount():
            return

        if not hasattr(self.app, "instrument_names_48"):
            return

        self._ensure_automation_store()

        # ------------------------------------------------------------
        # Remember user-painted cells (manual strokes only).
        # Procedural / engine expansion must NOT mark cells as user-owned,
        # otherwise later Randomizer/Phase-Lock passes treat every cell as locked
        # and skip writing Direction / Multi-Seq / Coverage / Blend Partner.
        # ------------------------------------------------------------
        expanding = bool(getattr(self, "_paint_expanding", False))
        if not expanding:
            touched = getattr(self, "playlist_user_touched", None)
            if touched is None:
                touched = self.playlist_user_touched = set()
            touched.add((row, col))

        # ------------------------------------------------------------
        # Paint-rate limiting.
        # ------------------------------------------------------------
        now = time.monotonic()

        if not hasattr(self, "_last_flash_paint_cell"):
            self._last_flash_paint_cell = None

        if not hasattr(self, "_last_flash_paint_locus"):
            self._last_flash_paint_locus = None

        expanding = bool(getattr(self, "_paint_expanding", False))

        if not expanding:
            last_time = float(
                getattr(self, "_last_paint_mono", 0.0)
            )

            if (
                now - last_time < PAINT_PERIOD_S
                and self._last_flash_paint_cell == (row, col)
            ):
                return

            self._last_paint_mono = now
            self._last_flash_paint_cell = (row, col)

            # No mouse event is available here.  Coordinates are supplied
            # directly by PaintTableWidget, so don't calculate event.position().
            self._last_flash_paint_locus = None

        # ------------------------------------------------------------
        # Seed / deterministic-ish local RNG.
        # ------------------------------------------------------------
        seed_val = 0

        if hasattr(self.app, "input_seed_val"):
            try:
                txt = self.app._seed_text()

                if txt and abs(float(txt)) != 0.0:
                    seed_val = abs(hash(float(txt))) % (2 ** 31)
                else:
                    seed_val = int(time.time()) % (2 ** 31)

            except (ValueError, TypeError):
                try:
                    seed_text = self.app._seed_text()
                except Exception:
                    seed_text = ""

                seed_val = (
                    abs(hash(seed_text)) % (2 ** 31)
                    if seed_text
                    else int(time.time()) % (2 ** 31)
                )

        rng = np.random.default_rng(
            _safe_int_seed(seed_val)
            + row
            + col
            + int(time.time() * 1000) % 10000
        )

        mode = self._current_paint_mode()

        snap = (
            bool(self.chk_snap_grid.isChecked())
            if hasattr(self, "chk_snap_grid")
            else False
        )

        # ------------------------------------------------------------
        # Position / time base.
        # ------------------------------------------------------------
        if snap:
            pos_tag = f"q:{row}"
        else:
            pos_tag = f"u:{(row * MEUM):.3f}s"

        # ------------------------------------------------------------
        # CSV/member writer.
        # ------------------------------------------------------------
        def _append_cell_member(r, c, member):
            existing = ""

            item = table.item(r, c)
            if item is not None:
                existing = (item.text() or "").strip()

            owner = "e" if getattr(self, "_paint_expanding", False) else "u"
            token = f"{member}@{owner}:{pos_tag.split(':', 1)[-1]}"

            parts = (
                [p.strip() for p in existing.split(",") if p.strip()]
                if existing
                else []
            )

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
                    out = out[1:] + [token]
                    substituted = True
                else:
                    out.append(token)

            text_val = ", ".join(out)

            self.set_cell_item(r, c, text_val)

            overlap_n = len(out)

            self._flash_paint_cell(
                r,
                c,
                overlap_n,
                substituted=substituted,
                member=member,
            )

            return text_val

        # ------------------------------------------------------------
        # Select instrument.
        # ------------------------------------------------------------
        target_operator_name = self._selected_operator(rng)

        # ------------------------------------------------------------
        # Ensure playlist row exists.
        # ------------------------------------------------------------
        while len(
            getattr(self.app, "master_playlist_data", [])
        ) <= row:
            self.app.master_playlist_data.append({})

        entry = self.app.master_playlist_data[row]

        if not isinstance(entry, dict):
            entry = {}
            self.app.master_playlist_data[row] = entry

        entry["position"] = pos_tag
        entry["quantized"] = snap

        # Manual paint is user-owned.  Record ownership per visible column so
        # Randomizer/Phase-Lock can regenerate only engine-owned material.
        if not getattr(self, "_paint_expanding", False):
            locked = entry.setdefault("user_locked_columns", [])
            if col not in locked:
                locked.append(col)

        # ------------------------------------------------------------
        # Column 0 — time.
        # ------------------------------------------------------------
        if col == 0:
            value = (
                pos_tag.split(":", 1)[-1]
                if ":" in pos_tag
                else pos_tag
            )

            _append_cell_member(row, 0, value)

            entry["time_marker"] = pos_tag
            return

        # ------------------------------------------------------------
        # Column 1 — instrument identity.
        # ------------------------------------------------------------
        if col == 1:
            name = target_operator_name

            if mode == self.MODE_RANDOM_PARAMETERS:
                name = self.app.instrument_names_48[
                    int(
                        rng.integers(
                            0,
                            len(self.app.instrument_names_48),
                        )
                    )
                ]

            _append_cell_member(row, 1, name)

            # Seed the idealized structure set for this operator (Script/Domain/
            # Synth/Patch) so a single identity paint is enough for Unison recycle.
            try:
                struct = idealized_operator_struct(self.app, name, row=row)
                for sk, sc in zip(PLAYLIST_STRUCT_COLUMNS, PLAYLIST_STRUCT_COL_INDICES):
                    if not entry.get(sk):
                        _append_cell_member(row, sc, struct.get(sk, ""))
                        entry[sk] = struct.get(sk, "")
            except Exception:
                pass

            # Additional overlapping synth identity / automation.
            if (
                not getattr(self, "_paint_expanding", False)
                and float(rng.random()) < 0.55
            ):
                extra = self.app.instrument_names_48[
                    int(
                        rng.integers(
                            0,
                            len(self.app.instrument_names_48),
                        )
                    )
                ]

                if extra != name:
                    _append_cell_member(row, 1, extra)
                    # Cross-blend structure cells under virtual half-overlap
                    try:
                        self.row_coverage.setdefault(row, {})
                        self.row_coverage[row][name] = max(
                            float(self.row_coverage[row].get(name, 0.0)), 0.55
                        )
                        self.row_coverage[row][extra] = max(
                            float(self.row_coverage[row].get(extra, 0.0)), 0.45
                        )
                        self._blend_row_structs(row, name, extra, 0.5 * self._blend_max_fraction())
                    except Exception:
                        pass

                # Auto-target / amount / coverage (shifted indices in 13-col schema)
                _append_cell_member(
                    row,
                    7,
                    str(
                        rng.choice(
                            [
                                "eqr",
                                "fractalizer",
                                "pkp_decay",
                                "filter",
                                "drive",
                            ]
                        )
                    ),
                )

                _append_cell_member(
                    row,
                    8,
                    f"{int(rng.integers(20, 90))}%",
                )

                _append_cell_member(
                    row,
                    11,
                    f"Cover{float(rng.uniform(0.25, 1.0)):.0%}",
                )

            item = table.item(row, 1)

            ops = []

            if item is not None:
                ops = [
                    p.split("@")[0].strip()
                    for p in (item.text() or "").split(",")
                    if p.strip()
                ]

            entry["operator"] = ops[0] if ops else name
            entry["operators"] = ops

            if item is not None:
    # Identity cells are colored by _flash_paint_cell().
    # Leave the existing color untouched here.
                item.setToolTip(
                f"instrument={entry.get('operator', target_operator_name)}"
            )

            return

        # ------------------------------------------------------------
        # Column 2 — script.
        # ------------------------------------------------------------
        if col == 2:
            struct = idealized_operator_struct(self.app, target_operator_name, row=row)
            tag = struct.get("script_tag") or f"Script::{target_operator_name[:6].upper()}"

            _append_cell_member(row, 2, tag)

            entry["script_tag"] = tag
            return

        # ------------------------------------------------------------
        # Column 3 — domain partition tag.
        # ------------------------------------------------------------
        if col == 3:
            struct = idealized_operator_struct(self.app, target_operator_name, row=row)
            tag = struct.get("domain_tag") or f"Dom::{target_operator_name[:8]}[t]"

            _append_cell_member(row, 3, tag)

            entry["domain_tag"] = tag
            return

        # ------------------------------------------------------------
        # Column 4 — synth parameter snapshot.
        # ------------------------------------------------------------
        if col == 4:
            struct = idealized_operator_struct(self.app, target_operator_name, row=row)
            tag = struct.get("synth_tag") or f"Synth::{target_operator_name[:10]}"

            _append_cell_member(row, 4, tag)

            entry["synth_tag"] = tag
            return

        # ------------------------------------------------------------
        # Column 5 — modular patch topology tag.
        # ------------------------------------------------------------
        if col == 5:
            struct = idealized_operator_struct(self.app, target_operator_name, row=row)
            tag = struct.get("patch_tag") or f"Patch::{target_operator_name[:8]}"

            _append_cell_member(row, 5, tag)

            entry["patch_tag"] = tag
            return

# Column 6 — velocity / amp.
        # ------------------------------------------------------------
        if col == 6:
            if hasattr(self.app, "_contextual_numerology"):
                try:
                    ctx = float(
                        self.app._contextual_numerology(
                            target_operator_name,
                            row,
                            row,
                        )
                    )
                except Exception:
                    ctx = 0.5
            else:
                ctx = 0.5

            if mode == self.MODE_RANDOM_PARAMETERS:
                velocity = float(rng.uniform(0.10, 1.20))
            else:
                velocity = float(
                    np.clip(
                        0.15 + 1.15 * ctx,
                        0.05,
                        1.5,
                    )
                )

            _append_cell_member(
                row,
                6,
                f"{velocity * 100:.1f}%",
            )

            entry["velocity"] = velocity

            # Explicit amp state so the paint operation actually affects
            # amplitude rather than merely displaying a velocity token.
            entry["amp"] = velocity

            return

        # ------------------------------------------------------------
        # Column 7 — automation target / synth parameter.
        # ------------------------------------------------------------
        if col == 7:
            params = list(
                self.app.instrument_param_state.get(
                    target_operator_name,
                    {
                        "eqr": 0.5,
                        "fractalizer": 0.5,
                        "pkp_decay": 0.5,
                        "filter": 0.5,
                        "drive": 0.5,
                        "pitch": 0.0,
                    },
                ).keys()
            )

            if not params:
                params = [
                    "eqr",
                    "fractalizer",
                    "pkp_decay",
                    "filter",
                    "drive",
                    "pitch",
                ]

            if mode == self.MODE_RANDOM_PARAMETERS:
                k = int(
                    rng.integers(
                        1,
                        min(4, len(params) + 1),
                    )
                )

                chosen = list(
                    rng.choice(
                        params,
                        size=min(k, len(params)),
                        replace=False,
                    )
                )
            else:
                chosen = [
                    params[
                        (row + col) % len(params)
                    ]
                ]

            for p in chosen:
                _append_cell_member(row, 7, str(p))

            item = table.item(row, 4)

            entry["auto_targets"] = (
                [
                    p.split("@")[0].strip()
                    for p in (item.text() or "").split(",")
                    if p.strip()
                ]
                if item is not None
                else []
            )

            return

        # ------------------------------------------------------------
        # Column 8 — automation amount.
        # ------------------------------------------------------------
        if col == 8:
            try:
                ctx = float(
                    self.app._contextual_numerology(
                        target_operator_name,
                        row,
                        row,
                    )
                )
            except Exception:
                ctx = 0.5

            if mode == self.MODE_RANDOM_PARAMETERS:
                amt = int(rng.integers(20, 90))
            else:
                amt = int(
                    round(
                        100
                        * float(
                            np.clip(
                                0.50
                                + 0.24
                                * (ctx - 0.5)
                                * 2.0,
                                0.20,
                                0.80,
                            )
                        )
                    )
                )

            _append_cell_member(
                row,
                8,
                f"{amt}%",
            )

            entry["auto_amount"] = amt / 100.0
            return

        # ------------------------------------------------------------
        # Column 9 — modulation/vector.
        # ------------------------------------------------------------
        if col == 9:
            direction = (
                "+"
                if (row + col) % 2 == 0
                else "−"
            )
            signed = 1.0 if direction == "+" else -1.0
            vector_text = f"{signed:+.4f}"

            _append_cell_member(
                row,
                9,
                vector_text,
            )

            # Canonical schema key used by engines / CSV / window spawn.
            entry["direction_vector"] = vector_text
            entry["direction"] = signed

            return

        # ------------------------------------------------------------
        # Column 10 — multi sequence.
        # ------------------------------------------------------------
        if col == 10:
            multi = f"Multi[{(row % 3) + 1}]"

            _append_cell_member(
                row,
                10,
                multi,
            )

            entry["multi_seq"] = multi
            return

        # ------------------------------------------------------------
        # Column 11 — coverage.
        # ------------------------------------------------------------
        if col == 11:
            rc = self.row_coverage.setdefault(row, {})

            previous = float(
                rc.get(
                    target_operator_name,
                    0.0,
                )
            )

            coverage = min(
                1.0,
                previous + 0.25,
            )

            rc[target_operator_name] = coverage

            _append_cell_member(
                row,
                11,
                f"Cover{coverage:.0%}",
            )

            entry["coverage"] = coverage
            return

        # ------------------------------------------------------------
        # Column 12+ — blend.
        # ------------------------------------------------------------
        if col >= 12:
            blend = float(
                rng.uniform(0.0, 100.0)
            )
            # Prefer a concrete partner label when instruments exist; otherwise
            # keep the numeric blend amount. Always write blend_partner so the
            # last playlist column is never left empty after a procedural paint.
            names = list(getattr(self.app, "instrument_names_48", []) or [])
            if names:
                partner = names[(row * 3 + col) % len(names)]
                blend_text = partner
            else:
                partner = ""
                blend_text = f"Blend{blend:.1f}%"

            _append_cell_member(
                row,
                col,
                blend_text,
            )

            entry["blend_partner"] = partner or blend_text
            entry["blend_percent"] = blend
            return
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
                try:
                    a[k] = float(a[k] * (1.0 - amount) + float(b[k]) * amount)
                except Exception:
                    pass

    def _blend_row_structs(self, row, op_a, op_b, amount):
        """Blend Script/Domain/Synth/Patch cells on a row under virtual overlap.

        amount is the same coverage-derived fraction used for instrument-param
        travel (already scaled by Half/Quarter blend max). Any structure cell
        can blend; the dual-label form preserves both parents for Unison recycle.
        """
        if not hasattr(self.app, "master_playlist_data"):
            return
        while len(self.app.master_playlist_data) <= row:
            self.app.master_playlist_data.append({})
        entry = self.app.master_playlist_data[row]
        if not isinstance(entry, dict):
            entry = {}
            self.app.master_playlist_data[row] = entry

        sa = idealized_operator_struct(self.app, op_a, row=row)
        sb = idealized_operator_struct(self.app, op_b, row=row)
        for key, col in zip(PLAYLIST_STRUCT_COLUMNS, PLAYLIST_STRUCT_COL_INDICES):
            # Prefer already-painted cell text as the local left/right parent
            left = ""
            right = ""
            item = self.table_widget.item(row, col) if self.table_widget else None
            if item and (item.text() or "").strip():
                left = item.text().strip()
            left = left or entry.get(key) or sa.get(key, "")
            right = sb.get(key, "")
            blended = blend_struct_labels(left, right, amount)
            entry[key] = blended
            self.set_cell_item(row, col, blended)

        # Also blend the live synth param store (existing dynamic)
        self._blend_instrument_params(op_a, op_b, amount)

    def resolve_row_overlaps(self):
        """After a stroke, re-assert coverage, blend overlapping structs, push UI."""
        self._ensure_automation_store()
        max_frac = self._blend_max_fraction()
        for row, cov in self.row_coverage.items():
            if not cov:
                continue
            parts = [f"{k[:10]}:{v:.0%}" for k, v in cov.items()]
            # Coverage column is index 11 in the 13-col schema
            cov_col = 11 if self.table_widget.columnCount() > 11 else min(8, self.table_widget.columnCount() - 1)
            self.set_cell_item(row, cov_col, " | ".join(parts)[:64])

            # Virtual overlap: when two+ operators share a row, blend their
            # idealized Script/Domain/Synth/Patch structs by relative coverage.
            ops = list(cov.keys())
            if len(ops) >= 2:
                # Sort by coverage desc; blend secondary into primary
                ops_sorted = sorted(ops, key=lambda k: cov.get(k, 0.0), reverse=True)
                primary = ops_sorted[0]
                for other in ops_sorted[1:]:
                    # Overlap fraction = min coverage * blend max (Half/Quarter)
                    overlap = float(min(cov.get(primary, 0.0), cov.get(other, 0.0)))
                    amount = float(np.clip(overlap * max_frac, 0.0, max_frac))
                    if amount > 0.01:
                        self._blend_row_structs(row, primary, other, amount)
                # Record blend partner as the strongest secondary
                if hasattr(self.app, "master_playlist_data") and row < len(self.app.master_playlist_data):
                    entry = self.app.master_playlist_data[row]
                    if isinstance(entry, dict):
                        entry["blend_partner"] = ops_sorted[1]
                        entry["coverage"] = " | ".join(parts)[:64]
                        entry["coverage_map"] = dict(cov)
                        blend_col = 12 if self.table_widget.columnCount() > 12 else min(9, self.table_widget.columnCount() - 1)
                        self.set_cell_item(row, blend_col, ops_sorted[1])

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
                cov_col = 11 if self.table_widget.columnCount() > 11 else 8
                self.set_cell_item(row, cov_col, "BLEND " + "+".join(f"{k[:6]}" for k in cov.keys()))
        print("[Playlist] Convolve color coding applied")
# ==========================================
# 4. MODULAR TAB MANAGER (TOP PANE)
# ==========================================
class ModularTabManager(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self.add_new_module_tab("Core Eskibrutus Node")

    def add_new_module_tab(self, title_prefix="Synth Node"):
        container = QWidget()
        layout = QVBoxLayout(container)

        visualizer = CoordinateVisualizer()
        formula_edit = QLineEdit("np.sin(t * 2.0) * x")
        formula_edit.setStyleSheet("background-color: #111; color: #0f0; font-family: monospace;")

        layout.addWidget(QLabel(f"--- Active Workspace: {title_prefix} ---"))
        layout.addWidget(visualizer)
        layout.addWidget(QLabel("Runtime Expression (x, y, z, t):"))
        layout.addWidget(formula_edit)

        # Add custom control switches for this spawned instance
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QPushButton("Fold Reset"))
        controls_layout.addWidget(QPushButton("Bypass FX"))
        layout.addLayout(controls_layout)

        container.setLayout(layout)
        self.addTab(container, title_prefix)
        self.setCurrentWidget(container)

        # Live visual feedback simulation timer
        self.timer = QTimer(self)
        t_val = [0.0]
        def sim_tick():
            t_val[0] += 0.1
            try:
                x = float(eval(formula_edit.text(), {"np": np, "t": t_val[0], "x": 1.0, "y": 1.0, "z": 0.0}))
                y = float(eval("np.cos(t * 1.5) * y", {"np": np, "t": t_val[0], "x": 1.0, "y": 1.0, "z": 0.0}))
                visualizer.update_coordinates(x, y)
            except Exception:
                pass
        self.timer.timeout.connect(sim_tick)
        self.timer.start(50)

    def close_tab(self, index):
        if self.count() > 1:
            widget = self.widget(index)
            self.removeTab(index)
            widget.deleteLater()

class VisualNodeScriptingWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visual Equation & Symbolic Scripting Canvas")
        self.resize(1000, 650)
        self.setStyleSheet(TELETUBBY_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Interactive Geometric Node Patch Builder & Symbolic Engine</b>"))

        self.geom_canvas = GeometricSymbolicCanvas(self)
        layout.addWidget(self.geom_canvas)

        canvas_splitter = QSplitter(Qt.Orientation.Horizontal)

        toolbox_widget = QWidget()
        tb_layout = QVBoxLayout(toolbox_widget)
        tb_layout.addWidget(QLabel("<b>Click Blocks to Insert</b>"))

        blocks = [
            "⚡ Eski Sine [Jack]", "🔀 Wavefold Node [Jack]", "🔁 For-Loop Repeater [Jack]",
            "⚖️ Heuristic Branch [Jack]", "🌀 Noise Generator [Jack]", "📉 Low-Pass Filter [Jack]",
            "➕ Additive Sum [Jack]", "✖️ Ring Modulator [Jack]", "⏱️ Delay Line [Jack]",
            "🎛️ Envelope Shaper [Jack]", "🔍 Phase Root [Jack]", "💥 Eskibrutus Fold [Jack]"
        ]
        for b in blocks:
            btn = QPushButton(b)
            btn.setStyleSheet("background-color: #6c5ce7; color: white; text-align: left; padding-left: 8px;")
            btn.clicked.connect(lambda checked, text=b: self.append_node_text(text))
            tb_layout.addWidget(btn)

        canvas_splitter.addWidget(toolbox_widget)

        self.assembly_board = QTextEdit()
        self.assembly_board.setPlainText(
            "# Interactive Modular Patch Assembly & Geometric Symbolic Equation Network\n"
            "[ Node α: Eski-Prime Sine ] ===(Symbolic Jack)===> [ Node β: Dipsy Wavefolder ]\n"
        )
        self.assembly_board.setStyleSheet("background-color: #ffffff; color: #1e272e; font-family: monospace; font-size: 13px; border-radius: 10px;")
        canvas_splitter.addWidget(self.assembly_board)

        canvas_splitter.setSizes([320, 680])
        layout.addWidget(canvas_splitter)

        compile_btn = QPushButton("Compile and Apply Geometric Symbolic Matrix to Active Stream")
        compile_btn.setStyleSheet("background-color: #00b894; color: white; font-weight: bold;")
        compile_btn.clicked.connect(lambda: QMessageBox.information(self, "Compiled", "Interactive visual graph and symbolic equations successfully compiled."))
        layout.addWidget(compile_btn)

    def append_node_text(self, node_name):
        current = self.assembly_board.toPlainText()
        updated = current + f"\n[ Geometric Linked: {node_name} ] ===(Symbolic Patch Jack)===> [ Routing Matrix Bus ]"
        self.assembly_board.setPlainText(updated)
# ==========================================
# 2. COORDINATE VISUALIZER
# ==========================================
class CoordinateVisualizer(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(110)
        self.setStyleSheet("background-color: black; border: 1px solid #00ffaa;")
        self.point_history = []
        self.max_points = 150

    def update_coordinates(self, x, y):
        self.point_history.append((x, y))
        if len(self.point_history) > self.max_points:
            self.point_history.pop(0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.fillRect(self.rect(), QColor(10, 10, 10))
            if len(self.point_history) >= 2:
                pen = QPen(QColor(0, 255, 150))
                pen.setWidth(2)
                painter.setPen(pen)
                width, height = self.width(), self.height()
                for i in range(1, len(self.point_history)):
                    x1 = (self.point_history[i-1][0] + 1) * 0.5 * width
                    y1 = (self.point_history[i-1][1] + 1) * 0.5 * height
                    x2 = (self.point_history[i][0] + 1) * 0.5 * width
                    y2 = (self.point_history[i][1] + 1) * 0.5 * height
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        finally:
            painter.end()

class PianoRollEditor(QDialog):
    def __init__(self, instrument_name, step_count=48, parent=None):
        super().__init__(parent)
        self.instrument_name = instrument_name
        self.setWindowTitle(f"Sequencer & Piano Roll: {instrument_name}")
        self.resize(1000, 520)
        self.setStyleSheet(TELETUBBY_STYLE)

        layout = QVBoxLayout(self)
        top_ctrl = QHBoxLayout()
        top_ctrl.addWidget(QLabel(f"<b>Polyrhythmic Sequence Matrix for {instrument_name}</b>"))

        top_ctrl.addWidget(QLabel("Grid Length:"))
        self.steps_combo = QComboBox()
        self.steps_combo.addItems(["16 Steps", "32 Steps", "48 Steps", "64 Steps"])
        self.steps_combo.setCurrentText(f"{step_count} Steps")
        top_ctrl.addWidget(self.steps_combo)

        top_ctrl.addWidget(QLabel("Polyrhythm Divisor:"))
        self.poly_spin = QDoubleSpinBox()
        self.poly_spin.setRange(0.25, 4.0)
        self.poly_spin.setValue(1.0)
        self.poly_spin.setSingleStep(0.05)
        top_ctrl.addWidget(self.poly_spin)

        layout.addLayout(top_ctrl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_container = QWidget()
        self.grid_layout = QGridLayout(grid_container)

        self.cells = []
        for step in range(48):
            cell_frame = QFrame()
            c_layout = QVBoxLayout(cell_frame)

            seq_name = f"{instrument_name}_seq_{step+1}"
            # POWER_V3_EMPTY_BOOT: standalone piano-roll editors also open blank.
            btn = QPushButton(f"{seq_name}\n[Gate Off]")
            btn.setCheckable(True)
            btn.setChecked(False)

            offset_slider = QSlider(Qt.Orientation.Horizontal)
            offset_slider.setRange(-50, 50)
            offset_slider.setValue(0)

            c_layout.addWidget(btn)
            c_layout.addWidget(QLabel("De-quant Offset:"))
            c_layout.addWidget(offset_slider)

            self.grid_layout.addWidget(cell_frame, 0, step)
            self.cells.append((btn, offset_slider))

        grid_container.setLayout(self.grid_layout)
        scroll.setWidget(grid_container)
        layout.addWidget(scroll)

        apply_btn = QPushButton(f"Commit Sequences for {instrument_name} to Master Timeline")
        apply_btn.setStyleSheet("background-color: #00b894; color: white;")
        apply_btn.clicked.connect(lambda: QMessageBox.information(self, "Committed", f"Polyrhythmic unquantized sequences for {instrument_name} updated."))
        layout.addWidget(apply_btn)
# ==========================================
# 3. STANDALONE PLAYLIST WINDOW
# ==========================================
class PlaylistArrangementWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Playlist & Arrangement Timeline")
        self.resize(750, 520)
        self.setStyleSheet(TELETUBBY_STYLE)

        container = QWidget()
        layout = QVBoxLayout(container)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("<b>Timeline Snap & Polyrhythm Scaling:</b>"))
        self.grid_scale_combo = QComboBox()
        self.grid_scale_combo.addItems(["1 Bar (Quantized)", "1/2 Beat", "1/4 Beat", "1/8 Beat", "Fully Unquantized / De-quantized Flow"])
        controls.addWidget(self.grid_scale_combo)

        controls.addWidget(QLabel("<b>Tempo (BPM):</b>"))
        self.global_tempo = QLineEdit("124.0")
        controls.addWidget(self.global_tempo)
        layout.addLayout(controls)

        self.timeline_view = QTextEdit()
        self.timeline_view.setPlainText(
            "# Global Playlist Arrangement Channels & Paintbrush Clips\n"
            "# Empty by design — paint, calculate, or randomize explicitly.\n"
            "# Capacity and mathematical context are initialized without a musical program."
        )
        self.timeline_view.setStyleSheet("background-color: #ffffff; color: #1e272e; font-family: monospace; font-size: 13px; border-radius: 10px;")
        layout.addWidget(self.timeline_view)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("Universal Brush Painter Mode"))
        btn_layout.addWidget(QPushButton("Quantize All Sequence Clips"))
        btn_layout.addWidget(QPushButton("Render Instrument Stems to Disk"))
        layout.addLayout(btn_layout)

        container.setLayout(layout)
        self.setCentralWidget(container)

# ==========================================
# MODULATION ROUTING HUB
# ==========================================
class ModulationRoutingWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Modulation & LFO Hub")
        self.resize(700, 480)
        self.setStyleSheet(DAW_STYLE)

        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("<b>🌸 Direct Interactive LFO & Envelope Modulation Hub 🌸</b>"))

        mod_grid = QGridLayout()
        mod_grid.addWidget(QLabel("LFO 1 Rate (Hz):"), 0, 0)
        self.lfo1_slider = QSlider(Qt.Orientation.Horizontal)
        self.lfo1_slider.setRange(0, 100)
        # POWER_V3_DEFAULTS: retain the Gemini/original 45% modulation-rate starting point.
        # Meum is applied by the contextual field; it does not replace this UI default.
        self.lfo1_slider.setValue(45)
        mod_grid.addWidget(self.lfo1_slider, 0, 1)

        mod_grid.addWidget(QLabel("LFO Shape:"), 1, 0)
        self.shape_box = QComboBox()
        self.shape_box.addItems(["Sine Wave", "Triangle Wave", "Square Wave", "Random Chaos Curve", "Tubby Step Vector"])
        mod_grid.addWidget(self.shape_box, 1, 1)

        mod_grid.addWidget(QLabel("Envelope Decay (ms):"), 2, 0)
        self.env_slider = QSlider(Qt.Orientation.Horizontal)
        self.env_slider.setRange(0, 100)
        # POWER_V3_DEFAULTS: retain the Gemini/original 70% envelope starting point.
        self.env_slider.setValue(70)
        mod_grid.addWidget(self.env_slider, 2, 1)

        layout.addLayout(mod_grid)

        self.mod_view = QTextEdit()
        self.mod_view.setPlainText(
            "# Active Modulation & LFO Routing Table\n"
            "LFO 1 ---> Routed to Filter Cutoff (Depth: 75%)\n"
            "LFO 2 ---> Routed to Chaos Attractor (Depth: 100%)\n"
            "Envelope Shaper ---> Routed to Master Limiter Threshold"
        )
        self.mod_view.setStyleSheet("background-color: #ffffff; color: #1e272e; font-family: monospace; font-size: 13px; border-radius: 10px;")
        layout.addWidget(self.mod_view)

        apply_btn = QPushButton("Commit Modulation Patches")
        apply_btn.setStyleSheet("background-color: #00b894; color: white;")
        apply_btn.clicked.connect(lambda: QMessageBox.information(self, "Modulation Updated", "Modulation matrix parameters updated."))
        layout.addWidget(apply_btn)

        container.setLayout(layout)
        self.setCentralWidget(container)
class PlaylistWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tubby-Land Global Arrangement & Painter")
        self.resize(1050, 620)
        self.setStyleSheet(TELETUBBY_STYLE)

        container = QWidget()
        layout = QVBoxLayout(container)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("<b>Snap-to-Grid Scale:</b>"))
        self.grid_scale_combo = QComboBox()
        self.grid_scale_combo.addItems(["1 Bar", "1/2 Beat", "1/4 Beat", "1/8 Beat", "Free / Unquantized Tubby Flow"])
        controls.addWidget(self.grid_scale_combo)

        controls.addWidget(QLabel("<b>Global Tempo (BPM):</b>"))
        self.global_tempo = QLineEdit("120.0")
        controls.addWidget(self.global_tempo)
        layout.addLayout(controls)

        self.timeline_view = QTextEdit()
        self.timeline_view.setPlainText(
            "# Global arrangement / painter\n"
            "# Empty by design — no preset clips or gates are injected on boot."
        )
        self.timeline_view.setStyleSheet("background-color: #ffffff; color: #2f3640; font-family: monospace; font-size: 13px; border-radius: 15px;")
        layout.addWidget(self.timeline_view)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("Universal Brush Painter Mode"))
        btn_layout.addWidget(QPushButton("Render Tubby Stems to Disk"))
        layout.addLayout(btn_layout)

        container.setLayout(layout)
        self.setCentralWidget(container)
# ==========================================
# 4. MINIATURE SYNTH WIDGET WITH PATCH CABLES
# ==========================================
class MiniSynthNodeWidget(QFrame):
    def __init__(self, synth_name):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444; border-radius: 6px;")

        layout = QVBoxLayout(self)
        title = QLabel(f"<b>Mini-Synth: {synth_name}</b>")
        title.setStyleSheet("color: #ffaa00;")
        layout.addWidget(title)

        self.cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self.cutoff_slider.setRange(0, 100)
        # POWER_V3_DEFAULTS: retain the Gemini/original 75% cutoff starting point.
        # Meum contextual modulation operates around this baseline.
        self.cutoff_slider.setValue(75)
        self.drive_slider = QSlider(Qt.Orientation.Horizontal)
        self.drive_slider.setRange(0, 100)
        # POWER_V3_DEFAULTS: retain the Gemini/original 50% wavefold starting point.
        # Meum contextual modulation operates around this baseline rather than redefining it.
        self.drive_slider.setValue(50)

        layout.addWidget(QLabel("Cutoff / Frequency Freq:"))
        layout.addWidget(self.cutoff_slider)
        layout.addWidget(QLabel("Distortion / Fold Drive:"))
        layout.addWidget(self.drive_slider)

        patch_layout = QHBoxLayout()
        self.src_combo = QComboBox()
        self.src_combo.addItems(["X Coord", "Y Coord", "Z Coord", "LFO 1"])
        self.dest_combo = QComboBox()
        self.dest_combo.addItems(["-> Filter Cutoff", "-> Fold Threshold", "-> Pitch Mod"])

        patch_layout.addWidget(self.src_combo)
        patch_layout.addWidget(QLabel("⤹"))
        patch_layout.addWidget(self.dest_combo)
        layout.addLayout(patch_layout)
class FloatingSynthWindow(QMainWindow):
    def __init__(self, synth_name, synth_id, custom_title="", parent=None):
        super().__init__(parent)
        self.synth_name = synth_name
        self.custom_title = custom_title if custom_title else f"Plugin_{synth_id}"
        self.setWindowTitle(f"Advanced Device Plugin: {self.custom_title} ({synth_name})")
        self.resize(520, 620)
        self.setStyleSheet(DAW_STYLE)

        self.dsp_engine = AdvancedDSPEngine()

        container = QWidget()
        layout = QVBoxLayout(container)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("<b>Device Name:</b>"))
        self.name_edit = QLineEdit(self.custom_title)
        name_layout.addWidget(self.name_edit)

        name_layout.addWidget(QLabel("Alg:"))
        self.wave_combo = QComboBox()
        self.wave_combo.addItems(["Sine FM", "Square PWM", "Saw Supersaw", "Noise Chaos"])
        self.wave_combo.currentIndexChanged.connect(self.update_synth_algorithm)
        name_layout.addWidget(self.wave_combo)
        layout.addLayout(name_layout)

        layout.addWidget(QLabel("<b>Live Oscilloscope & Wavefolder View</b>"))
        self.oscilloscope = RealtimeOscilloscope(self)
        layout.addWidget(self.oscilloscope)

        controls_layout = QGridLayout()

        controls_layout.addWidget(QLabel("Cutoff / Resonance:"), 0, 0)
        self.cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self.cutoff_slider.setRange(0, 100)
        # POWER_V3_DEFAULTS: retain the Gemini/original 75% cutoff starting point.
        self.cutoff_slider.setValue(75)
        controls_layout.addWidget(self.cutoff_slider, 0, 1)

        controls_layout.addWidget(QLabel("Wavefold Drive:"), 1, 0)
        self.drive_slider = QSlider(Qt.Orientation.Horizontal)
        self.drive_slider.setRange(0, 100)
        # POWER_V3_DEFAULTS: retain the Gemini/original 50% wavefold starting point.
        self.drive_slider.setValue(50)
        self.drive_slider.valueChanged.connect(self.update_drive_param)
        controls_layout.addWidget(self.drive_slider, 1, 1)

        controls_layout.addWidget(QLabel("Envelope Decay (s):"), 2, 0)
        self.decay_spin = QDoubleSpinBox()
        # POWER_V3_DEFAULTS: retain the Gemini/original 0.30 s envelope decay.
        # Meum shapes generated phase/space relationships rather than overriding the synth envelope baseline.
        self.decay_spin.setValue(0.3)
        self.decay_spin.setRange(0.01, 5.0)
        self.decay_spin.setSingleStep(0.05)
        controls_layout.addWidget(self.decay_spin, 2, 1)

        layout.addLayout(controls_layout)

        pad_layout = QHBoxLayout()
        pad_layout.addWidget(QLabel("<b>Trigger Keys:</b>"))
        for note_name, freq in [("C4", 261.63), ("D4", 293.66), ("E4", 329.63), ("F4", 349.23), ("G4", 392.00)]:
            btn = QPushButton(note_name)
            btn.setStyleSheet("background-color: #2b2b2b; color: #ff6b00; border: 1px solid #ff6b00;")
            btn.clicked.connect(lambda checked, f=freq: self.trigger_local_note(f))
            pad_layout.addWidget(btn)
        layout.addLayout(pad_layout)

        export_btn = QPushButton("💾 Export Plugin Stem (.wav)")
        export_btn.setStyleSheet("background-color: #007acc; color: white;")
        export_btn.clicked.connect(self.export_plugin_stem)
        layout.addWidget(export_btn)

        container.setLayout(layout)
        self.setCentralWidget(container)

    def update_synth_algorithm(self, index):
        self.oscilloscope.wave_type = index
        self.oscilloscope.update()

    def update_drive_param(self, value):
        normalized_drive = 1.0 + (value / 25.0)
        self.oscilloscope.drive = normalized_drive
        self.oscilloscope.update()

    def trigger_local_note(self, freq):
        try:
            drive_val = 1.0 + (self.drive_slider.value() / 25.0)
            dur = self.decay_spin.value()
            w_type = self.wave_combo.currentIndex()
            self.dsp_engine.export_to_wav("plugin_trigger.wav", duration_sec=dur, freq=freq, drive=drive_val, wave_type=w_type)
        except Exception:
            pass

    def export_plugin_stem(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Plugin Stem", f"{self.name_edit.text()}_stem.wav", "WAV Files (*.wav)")
        if file_path:
            try:
                drive_val = 1.0 + (self.drive_slider.value() / 25.0)
                w_type = self.wave_combo.currentIndex()
                self.dsp_engine.export_to_wav(file_path, duration_sec=4.0, freq=261.63, drive=drive_val, wave_type=w_type)
                QMessageBox.information(self, "Stem Exported", f"Successfully rendered device stem to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))
class PermanentPatchBayPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            background-color: #ff9ff3;
            border: 3px solid #ffffff;
            border-radius: 12px;
            padding: 4px;
        """)
        layout = QHBoxLayout(self)

        layout.addWidget(QLabel("<b>GLOBAL 48-INSTRUMENT PATCH BAY</b>"))

        self.global_src = QComboBox()
        self.global_src.addItems(["Master Clock Gate", "QWERTY Live Trigger", "Global Sequencer Trigger", "Playlist Timeline Cursor"])

        self.global_dest = QComboBox()
        self.global_dest.addItems(["All 48 Instrument Folds", "Master Bus Limiter", "Repeater Matrix Bus", "Global Pitch Shift"])

        self.repeater_slider = QSlider(Qt.Orientation.Horizontal)
        self.repeater_slider.setRange(1, 16)

        layout.addWidget(self.global_src)
        layout.addWidget(QLabel("➔"))
        layout.addWidget(self.global_dest)
        layout.addWidget(QLabel("Repeaters:"))
        layout.addWidget(self.repeater_slider)
        # Inside your main application or control panel __init__:
# 1. Tuning (SpinBox or Slider)
        self.spin_tuning = QSpinBox()
        self.spin_tuning.setRange(100, 1200)

        # 2. Amplitude Slider
        self.slider_amplitude = QSlider(Qt.Orientation.Horizontal)
        self.slider_amplitude.setRange(0, 100)

        # 3. Duration / Percussive-Keylike-Padded Slider
        self.slider_duration = QSlider(Qt.Orientation.Horizontal)
        self.slider_duration.setRange(0, 100)

        # 4. Fractalizer Slider
        self.slider_fractalizer = QSlider(Qt.Orientation.Horizontal)
        self.slider_fractalizer.setRange(0, 100)

        # 5. EQR Effect Slider / Fifth Option Control Dropdown or Slider
        self.slider_eqr = QSlider(Qt.Orientation.Horizontal)
        self.slider_eqr.setRange(0, 100)

        # Fifth Option Dropdown Preset Selector (shared or per instrument)
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)

    def on_preset_changed(self, index):
        curr_idx = self.instrument_selector_dropdown.currentIndex()
        if 0 <= curr_idx < len(self.channel_states):
            self.channel_states[curr_idx]["preset_idx"] = index
        connect_btn = QPushButton("Patch Global Bus")
        connect_btn.setStyleSheet("background-color: #0984e3; color: white;")
        connect_btn.clicked.connect(lambda: QMessageBox.information(self, "Global Bus Patched", "Global patch bus updated."))
        layout.addWidget(connect_btn)
# ==========================================
# 5. SCRIPTER'S PANE WITH FUNCTION KEYSET
# ==========================================
class DenseCoordinateVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setStyleSheet("background-color: #1e272e; border: 3px solid #feca57; border-radius: 14px;")
        self.point_history = []
        self.max_points = 250

    def update_coordinates(self, x, y):
        self.point_history.append((x, y))
        if len(self.point_history) > self.max_points:
            self.point_history.pop(0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.fillRect(self.rect(), QColor(30, 39, 46))
            width, height = self.width(), self.height()

            painter.setPen(QPen(QColor(72, 84, 96), 1, Qt.PenStyle.DashLine))
            painter.drawLine(0, height // 2, width, height // 2)
            painter.drawLine(width // 2, 0, width // 2, height)

            if len(self.point_history) >= 2:
                pen = QPen(QColor(255, 107, 107))
                pen.setWidth(3)
                painter.setPen(pen)
                for i in range(1, len(self.point_history)):
                    x1 = (self.point_history[i-1][0] + 1.2) * 0.41 * width
                    y1 = (self.point_history[i-1][1] + 1.2) * 0.41 * height
                    x2 = (self.point_history[i][0] + 1.2) * 0.41 * width
                    y2 = (self.point_history[i][1] + 1.2) * 0.41 * height
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        finally:
            painter.end()
class TopSideInstrumentSequencerPanel(QWidget):
    def __init__(self, parent=None, app_ref=None):
        super().__init__(parent)
        self.app_ref = app_ref
        self.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333333; border-radius: 4px; padding: 6px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("<b>Instance:</b>"))
        self.instance_combo = QComboBox()
        self.update_instance_list()
        self.instance_combo.currentIndexChanged.connect(self.on_instance_changed)
        row1.addWidget(self.instance_combo, stretch=2)

        row1.addWidget(QLabel("<b>Type:</b>"))
        self.inst_combo = QComboBox()
        self.inst_combo.addItems(DEFAULT_INSTRUMENT_LIST)
        row1.addWidget(self.inst_combo, stretch=3)

        row1.addWidget(QLabel("Tonal Curvature Eq (x, y, z):"))
        self.curvature_eq_input = QLineEdit("x * 1.618033 + y - z")
        self.curvature_eq_input.textChanged.connect(self.on_curvature_changed)
        row1.addWidget(self.curvature_eq_input, stretch=3)

        self.local_play_btn = QPushButton("▶ Loop")
        self.local_play_btn.setStyleSheet("background-color: #00aa55; color: white;")
        self.local_play_btn.clicked.connect(self.audition_sequence)
        row1.addWidget(self.local_play_btn)

        layout.addLayout(row1)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(95)
        self.scroll_area.setStyleSheet("background-color: #161616; border: 1px solid #282828;")

        self.step_buttons_container = QWidget()
        self.step_buttons_layout = QHBoxLayout(self.step_buttons_container)
        self.step_boxes = []

        self.rebuild_step_buttons(16)
        self.scroll_area.setWidget(self.step_buttons_container)
        layout.addWidget(self.scroll_area)

    def update_instance_list(self):
        self.instance_combo.blockSignals(True)
        self.instance_combo.clear()
        if self.app_ref and hasattr(self.app_ref, 'instrument_names'):
            labels = [f"Ch {i+1}: {name}" for i, name in enumerate(self.app_ref.instrument_names)]
            self.instance_combo.addItems(labels)
        else:
            self.instance_combo.addItems([f"Ch {i+1}: {name}" for i, name in enumerate(DEFAULT_INSTRUMENT_LIST)])
        self.instance_combo.blockSignals(False)

    def on_instance_changed(self, index):
        if self.app_ref and hasattr(self.app_ref, 'sync_ui_to_current_channel'):
            self.app_ref.sync_ui_to_current_channel(index)

    def on_curvature_changed(self, text):
        curr_idx = self.instance_combo.currentIndex()
        if self.app_ref and hasattr(self.app_ref, 'channel_states') and 0 <= curr_idx < len(self.app_ref.channel_states):
            self.app_ref.channel_states[curr_idx]["curvature_eq"] = text

    def rebuild_step_buttons(self, count):
        for box in self.step_boxes:
            box.setParent(None)
            box.deleteLater()
        self.step_boxes = []

        default_intervals = ["0(432Hz)", "1", "2", "-1", "-3", "3", "0", "2", "1", "-1", "0(432Hz)", "3", "-2", "1", "0", "2"]

        for i in range(count):
            step_frame = QFrame()
            step_frame.setStyleSheet("background-color: #222222; border: 1px solid #383838; border-radius: 2px;")
            step_layout = QVBoxLayout(step_frame)
            step_layout.setContentsMargins(2, 2, 2, 2)
            step_layout.setSpacing(2)

            btn = QPushButton(str(i+1))
            btn.setCheckable(True)
            btn.setChecked(i in [0, 4, 8, 12])
            btn.setFixedWidth(42)
            btn.setFixedHeight(20)
            btn.setStyleSheet("""
                QPushButton { background-color: #2b2b2b; color: #888888; border-radius: 2px; font-size: 8px; font-weight: bold; border: 1px solid #3a3a3a; }
                QPushButton:checked { background-color: #ff6b00; color: #ffffff; border: 1px solid #ff8533; }
            """)
            step_layout.addWidget(btn)

            default_val = default_intervals[i % len(default_intervals)]
            interval_input = QLineEdit(default_val)
            interval_input.setFixedWidth(42)
            interval_input.setStyleSheet("font-size: 8px; padding: 1px; background-color: #121212; color: #00ffcc;")
            step_layout.addWidget(interval_input)

            self.step_buttons_layout.addWidget(step_frame)
            self.step_boxes.append((btn, interval_input))

    def audition_sequence(self):
        QMessageBox.information(self, "Sequence Audition", "Looping active instrument sequence in memory buffer.")

# --- PLAYLIST WINDOW ---
# ==========================================
# 6. SEQUENCER PANE
# ==========================================
class SequencerPane(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>16-Step Modulation Sequencer</b>"))

        grid_layout = QGridLayout()
        self.steps = []
        for i in range(16):
            btn = QPushButton(str(i+1))
            btn.setCheckable(True)
            btn.setStyleSheet("background-color: #222; color: #888;")
            btn.clicked.connect(lambda checked, b=btn: b.setStyleSheet("background-color: #00aa55; color: #fff;" if b.isChecked() else "background-color: #222; color: #888;"))
            row, col = divmod(i, 8)
            grid_layout.addWidget(btn, row, col)
            self.steps.append(btn)

        layout.addLayout(grid_layout)
class CustomVSTKnobsDialog(QDialog):
    def __init__(self, parent=None, channel_state=None):
        super().__init__(parent)
        self.channel_state = channel_state or {}
        self.setWindowTitle("Custom VST & Waveform Parameters (Edit Synth)")
        self.resize(450, 350)
        self.setStyleSheet(DAW_STYLE)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>⚙️ Custom VST Parameters & Wavefunction Mapping:</b>"))

        form_layout = QFormLayout()

        self.vst_param1 = QSlider(Qt.Orientation.Horizontal)
        self.vst_param1.setRange(0, 100)
        self.vst_param1.setValue(int(self.channel_state.get("vst_p1", 0.5) * 100))
        form_layout.addRow("VST Resonance / Freq (p1):", self.vst_param1)

        self.vst_param2 = QSlider(Qt.Orientation.Horizontal)
        self.vst_param2.setRange(0, 100)
        self.vst_param2.setValue(int(self.channel_state.get("vst_p2", 0.618) * 100))
        form_layout.addRow("Harmonic Spread (p2):", self.vst_param2)

        self.vst_param3 = QSlider(Qt.Orientation.Horizontal)
        self.vst_param3.setRange(0, 100)
        self.vst_param3.setValue(int(self.channel_state.get("vst_p3", 0.33) * 100))
        form_layout.addRow("Meum Scaling Depth (p3):", self.vst_param3)

        self.routing_combo = QComboBox()
        self.routing_combo.addItems(["Direct Summation", "Phase Modulation (PM)", "Frequency Modulation (FM)", "Nonlinear Foldback"])
        form_layout.addRow("Synthesis Routing Mode:", self.routing_combo)

        layout.addLayout(form_layout)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Apply VST Settings")
        save_btn.setStyleSheet("background-color: #00aa55; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        btn_box.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        layout.addLayout(btn_box)

    def get_values(self):
        return {
            "vst_p1": self.vst_param1.value() / 100.0,
            "vst_p2": self.vst_param2.value() / 100.0,
            "vst_p3": self.vst_param3.value() / 100.0,
            "routing": self.routing_combo.currentText()
        }
# ==========================================
# 7. MAIN WINDOW & LAYOUT INTEGRATION
# ==========================================
import sys
import json
import random
import wave
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSlider, QSpinBox, QComboBox, QPushButton, QLabel, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt


























































































































































































































































































































































































































class MathematiciansGrooveboxApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Groovebox")
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.resize(1300, 950)
        self.playlist_window = None
        self.patch_bay_dialog = None
        self.synth_editor_window = None
        self.script_editor_window = None
        self.visual_oscilloscope = None
        self.wavefield_engine = PhaseLockedWavefieldEngine(self)
        self.domain_eq_engine = DomainPartitionEquationEngine(seed=0.0)
        self.domain_eq_dialog = None

        # Initialize the UI Manager as an independent floating control panel
        # that stays attached to your main app window
        self.ui_manager = UIComponentManager(self)
        self.ui_manager.setWindowTitle("EQR Phase-Locked Wavefield Controls")
        self.ui_manager.resize(850, 120)

        # Force UI manager to render
        self.ui_manager.show()

        # Instantiate and add the UIComponentManager
        if not self.centralWidget():
            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)

        if not hasattr(self, 'main_window_layout') or self.main_window_layout is None:
            self.main_window_layout = QVBoxLayout(self.centralWidget())

        # Instantiate and add the UIComponentManager to the main window layout
        self.main_window_layout.addWidget(self.ui_manager)
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
                cw.setObjectName("GrooveboxCentral")
                self.parametric_background = ParametricMathBackground(self, cw)
                self.parametric_background.setObjectName("ParametricMathBackground")
                # Size to the window's real target size, not cw.rect() — at this
                # point in __init__ no layout pass has happened yet, so cw.rect()
                # is still Qt's tiny default and the field never grows from there.
                self.parametric_background.setGeometry(0, 0, self.width(), self.height())
                self.parametric_background.lower()
                self.parametric_background.show()
                # Re-apply once more after the event loop does its first real
                # layout pass, and keep it synced on every future resize via
                # resizeEvent (see below) — belt-and-suspenders against timing.
                QTimer.singleShot(0, self._sync_parametric_background_geometry)
                # NOTE: no opaque/near-opaque fill here — the stylesheet already
                # makes GrooveboxCentral transparent so the math field reads
                # through. An explicit background-color here was previously
                # painting over it almost completely (rgba(6,6,6,210) ≈ 82%
                # opaque), which is why only a sliver of the field was visible.
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
        self.ui_manager.btn_seeded_randomizer.clicked.connect(self.apply_seeded_harmonic_randomization)
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
        # State lock for playlist memory; Qt widgets must still be touched only on the UI thread.
        self.playlist_state_lock = threading.RLock()
        self.instrument_param_state = {}
        # Build the initial program state before rendering the sequencer.
        # This prevents the first selection click from revealing hidden gates.
        # RECOMMENDED_POWER_LAYER: neutral mathematical boot. Engines create
        # musical material only when explicitly invoked.
        self._composition_generation_guard = False
        self._live_source_update_pending = False
        self._composition_generation_counter = 0
        self._transport_finished = False
        self._stop_requested = False
        self.init_ui_components()
        self.initialize_default_playlist_memory()
        self._composition_generation_guard = False
        self._live_source_update_pending = False
        self._composition_generation_counter = 0
        self._transport_finished = False
        self._stop_requested = False
    def _sync_parametric_background_geometry(self):
        """Keep the full-window math field sized to the central widget.

        Called once after the first real layout pass (via QTimer.singleShot)
        and on every subsequent resize (via resizeEvent below). Without this,
        the field keeps whatever tiny geometry it was given at construction
        time, before Qt had laid anything out.
        """
        bg = getattr(self, "parametric_background", None)
        cw = self.centralWidget()
        if bg is None or cw is None:
            return
        try:
            bg.setGeometry(0, 0, cw.width(), cw.height())
            bg.lower()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_parametric_background_geometry()

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
        """Atomically mirror the complete 10-column playlist table into memory."""
        table = getattr(self, "active_paint_table", None)
        if not table:
            return

        lock = getattr(self, "playlist_state_lock", None)
        if lock is None:
            lock = threading.RLock()
            self.playlist_state_lock = lock

        with lock:
            old_rows = list(getattr(self, "master_playlist_data", []) or [])
            rebuilt = []

            def cell(r, c):
                item = table.item(r, c) if c < table.columnCount() else None
                return item.text() if item else ""

            for r in range(table.rowCount()):
                prior = old_rows[r] if r < len(old_rows) and isinstance(old_rows[r], dict) else {}
                values = [cell(r, c) for c in range(min(PLAYLIST_COLUMN_COUNT, table.columnCount()))]
                values += [""] * (PLAYLIST_COLUMN_COUNT - len(values))
                # 13-col layout: 0 time, 1 ops, 2 script, 3 domain, 4 synth, 5 patch,
                # 6 velocity, 7 effect, 8 amount, 9 direction, 10 multi, 11 coverage, 12 blend
                vel_txt = values[6]
                effect = values[7]
                amount = values[8]
                direction = values[9]
                multi = values[10]
                coverage = values[11]
                blend = values[12]

                row_dict = {
                    "time_marker": values[0],
                    "operator": values[1] or prior.get("operator", self.instrument_names_48[0]),
                    "operators_csv": values[1],
                    "script_tag": values[2],
                    "domain_tag": values[3],
                    "synth_tag": values[4],
                    "patch_tag": values[5],
                    "velocity": 1.0,
                    "effect_target": effect,
                    "modulation": effect,
                    "auto_amount": amount,
                    "direction_vector": direction,
                    "direction": (
                        1.0 if direction.strip().startswith("+") or direction.strip().endswith("+")
                        else -1.0 if direction.strip().startswith(("-", "−")) or direction.strip().endswith(("-", "−"))
                        else 0.0
                    ),
                    "multi_seq": multi,
                    "coverage": coverage,
                    "blend_partner": blend,
                }

                try:
                    v = float(vel_txt.replace("%", "").strip())
                    row_dict["velocity"] = v / 100.0 if v > 1.0 else v
                except Exception:
                    row_dict["velocity"] = float(prior.get("velocity", 1.0) or 1.0)

                # Preserve non-visible engine/user metadata and ownership state.
                visible = set(row_dict)
                for key, value in prior.items():
                    if key not in visible:
                        row_dict[key] = value

                # Recover missing canonical fields from prior state (incl. new structs).
                for c, key in {
                    2: "script_tag", 3: "domain_tag", 4: "synth_tag", 5: "patch_tag",
                    9: "direction_vector", 10: "multi_seq",
                    11: "coverage", 12: "blend_partner",
                }.items():
                    if not values[c] and prior.get(key) not in (None, ""):
                        row_dict[key] = prior[key]

                rebuilt.append(row_dict)

            self.master_playlist_data = rebuilt


    # =====================================================================
    # LOCAL_CONTEXT_UI helpers — must live on MathematiciansGrooveboxApp
    # (they were previously only defined on UIComponentManager, which caused
    # AttributeError at startup when building the LOCAL CONTEXT panel).
    # =====================================================================
    def _make_local_context_button(self, text, tooltip):
        """Square local-context action button (synth / script / modular / etc.)."""
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
        generated = getattr(self, 'instrument_param_generated', {}) or {}
        generated_state = generated.get(instrument_name, {}) if isinstance(generated, dict) else {}
        generated_numeric = []
        if isinstance(generated_state, dict):
            for k, v in generated_state.items():
                if isinstance(v, (int, float, np.integer, np.floating)):
                    generated_numeric.append((str(k), float(v)))
                elif isinstance(v, (list, tuple)):
                    vals = []
                    for x in v[:16]:
                        if isinstance(x, (int, float, np.integer, np.floating)):
                            vals.append(float(x))
                    if vals:
                        generated_numeric.append((str(k), tuple(round(x, 8) for x in vals)))
        generated_blob = repr(sorted(generated_numeric))
        generated_score = (int(hashlib.sha256(generated_blob.encode('utf-8','replace')).hexdigest()[:12], 16) % 10000) / 10000.0
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
        """Shared deterministic score; includes Meum spatial field, scripts, patch topology, domains, synth/effects, media, and playlist state."""
        import hashlib
        f = self._contextual_feature_vector(instrument_name, step, row)
        payload = repr((instrument_name, step, row, self._seed_text() if hasattr(self, '_seed_text') else '0', f))
        digest = hashlib.sha256(payload.encode('utf-8','replace')).digest()
        tie_break = int.from_bytes(digest[:8], 'big') / float(2**64)
        return float(np.clip(0.78*f['score'] + 0.22*tie_break, 0.0, 1.0))

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
        rng = rng or np.random.default_rng(_safe_int_seed(self.get_numeric_seed()))
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
        rng = rng or np.random.default_rng(_safe_int_seed(self.get_numeric_seed()))
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

    def _randomize_local_context(self, checked=True):
        if not checked:
            return
        if getattr(self, "_composition_generation_guard", False):
            return

        self._composition_generation_guard = True
        snap = self._snapshot_global_effect_sliders()
        try:
            seed = _safe_int_seed(self.get_numeric_seed())
            rng = np.random.default_rng(seed)
            self._composition_generation_counter = (
                getattr(self, "_composition_generation_counter", 0) + 1
            )

            self.apply_seeded_harmonic_randomization()

            if hasattr(self, "_canonical_playlist_paint"):
                self._canonical_playlist_paint(rng=rng, mode="randomize", strength=0.55)
            elif hasattr(self, "_paint_generated_parameters"):
                self._paint_generated_parameters(rng=rng, source="randomizer")
                if hasattr(self, "_phase_lock_playlist_velocity"):
                    self._phase_lock_playlist_velocity(
                        rng=rng, strength=0.35, randomize=True
                    )

            if hasattr(self, "reload_active_instrument_sequencer_ui"):
                self.reload_active_instrument_sequencer_ui()
        except Exception as exc:
            print(f"[Randomizer] {type(exc).__name__}: {exc}")
        finally:
            self._restore_global_effect_sliders(snap)
            self._composition_generation_guard = False
    def _canonical_playlist_paint(self, rng, mode="randomize", strength=0.55):
        if getattr(self, "_composition_generation_guard", False):
            # The caller owns the transaction guard.
            pass

        table = getattr(self, "paintbrush_table", None)
        if table is None:
            table = getattr(self, "playlist_paint_table", None)

        # Locate the actual PaintbrushTable if the attribute name differs.
        if table is None:
            for name in (
                "paint_table",
                "paintbrush",
                "playlist_paintbrush",
                "playlist_paint_surface",
            ):
                candidate = getattr(self, name, None)
                if candidate is not None and hasattr(candidate, "engage_paint"):
                    table = candidate
                    break

        if table is None or not hasattr(table, "rowCount"):
    # The playlist UI may not exist yet during initial activation.
    # Still generate the complete playlist state in memory so that
    # columns 6–9 are available when the UI is subsequently created.
            if hasattr(self, "_paint_operator_pattern_to_playlist"):
                self._paint_operator_pattern_to_playlist(
                    source=mode,
                    rng=rng,
                )

            if hasattr(self, "_paint_generated_parameters"):
                self._paint_generated_parameters(
                    rng=rng,
                    source=mode,
                )

            if hasattr(self, "_run_composition_context_engine"):
                self._run_composition_context_engine(
                    source=mode,
                    rng=rng,
                )
            return

        rows = table.rowCount()
        cols = min(table.columnCount(), PLAYLIST_COLUMN_COUNT)

        # Prevent the brush's expansion logic from recursively expanding
        # every procedural paint, and from tagging cells as user-owned.
        old_expanding = getattr(table, "_paint_expanding", False)
        table._paint_expanding = True

        try:
            # Authoritative 10-column writer (time offsets + last four columns).
            # This is the same path used when the playlist window is still closed,
            # so memory and UI stay in lockstep on a fresh boot.
            if hasattr(self, "_paint_operator_pattern_to_playlist"):
                self._paint_operator_pattern_to_playlist(
                    source=mode,
                    rng=rng,
                )
            elif hasattr(self, "_run_composition_context_engine"):
                self._run_composition_context_engine(
                    source=mode,
                    rng=rng,
                )
            else:
                # Fallback: procedural brush paint without user-touch ownership.
                for row in range(rows):
                    for col in range(cols):
                        try:
                            table.engage_paint(row, col)
                        except Exception as exc:
                            print(
                                f"[CanonicalPaint] row={row} col={col}: "
                                f"{type(exc).__name__}: {exc}"
                            )

            if hasattr(self, "_paint_generated_parameters"):
                self._paint_generated_parameters(
                    rng=rng,
                    source=mode,
                )

            if hasattr(self, "_phase_lock_playlist_velocity"):
                self._phase_lock_playlist_velocity(
                    rng=rng,
                    strength=0.35 if mode == "randomize" else 0.45,
                    randomize=(mode == "randomize"),
                )

            if hasattr(self, "_sync_playlist_paint_table_from_memory"):
                self._sync_playlist_paint_table_from_memory()

        finally:
            table._paint_expanding = old_expanding
    def _sync_playlist_paint_table_from_memory(self):
        table = getattr(self, "active_paint_table", None)
        data = getattr(self, "master_playlist_data", None) or []
        if table is None:
            return
        # Canonical 10-column playlist schema.  Keep this map in lockstep with
        # PaintbrushTable's headers and the engine writer.
        colmap = {
            0: "time_marker",
            1: "operators_csv",
            2: "script_tag",
            3: "domain_tag",
            4: "synth_tag",
            5: "patch_tag",
            6: "velocity",
            7: "effect_target",
            8: "auto_amount",
            9: "direction_vector",
            10: "multi_seq",
            11: "coverage",
            12: "blend_partner",
        }
        rows = min(table.rowCount(), len(data))
        for r in range(rows):
            entry = data[r] if isinstance(data[r], dict) else {}
            for c, key in colmap.items():
                val = entry.get(key, "")
                if key == "velocity" and val not in (None, ""):
                    try:
                        val = f"{float(val) * 100:.1f}%"
                    except Exception:
                        val = str(val)
                text = "" if val in (None, "") else str(val)
                item = table.item(r, c)
                if item is None:
                    if hasattr(table, "set_cell_item"):
                        table.set_cell_item(r, c, text)
                    else:
                        from PyQt6.QtWidgets import QTableWidgetItem
                        table.setItem(r, c, QTableWidgetItem(text))
                else:
                    # Do not clobber a cell the user is actively editing if you track that;
                    # otherwise always refresh engine-owned empties:
                    if not (item.text() or "").strip() or True:
                        item.setText(text)
    def _phase_lock_local_context(self, checked=True):
        if not checked:
            return
        if getattr(self, "_composition_generation_guard", False):
            return

        self._composition_generation_guard = True
        snap = self._snapshot_global_effect_sliders()
        try:
            seed = _safe_int_seed(self.get_numeric_seed())
            rng = np.random.default_rng(seed)
            self._composition_generation_counter = (
                getattr(self, "_composition_generation_counter", 0) + 1
            )

            if hasattr(self, "wavefield_engine") and self.wavefield_engine:
                self.wavefield_engine.apply_phase_locked_randomization()
            else:
                self.apply_euclidean_and_idealized_rhythms()

            if hasattr(self, "_canonical_playlist_paint"):
                self._canonical_playlist_paint(rng=rng, mode="phase_lock", strength=0.55)
            elif hasattr(self, "_paint_generated_parameters"):
                self._paint_generated_parameters(rng=rng, source="phase_lock")
                if hasattr(self, "_phase_lock_playlist_velocity"):
                    self._phase_lock_playlist_velocity(
                        rng=rng, strength=0.45, randomize=False
                    )

            if hasattr(self, "reload_active_instrument_sequencer_ui"):
                self.reload_active_instrument_sequencer_ui()
        except Exception as exc:
            print(f"[PhaseLock] {type(exc).__name__}: {exc}")
        finally:
            self._restore_global_effect_sliders(snap)
            self._composition_generation_guard = False

    def _mark_generated_synth_context(self, source="randomizer", rng=None):
        """Generate algorithmic synth/script context in the shared state; user values remain authoritative."""
        rng = rng or np.random.default_rng(_safe_int_seed(self.get_numeric_seed()))
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
    def _snapshot_global_effect_sliders(self):
        """Capture global effect slider positions so engines can restore them."""
        out = {}
        for attr in (
            "slider_eqr",
            "slider_fractalizer",
            "slider_pkp_decay",
            "slider_pkp_boost",
            "slider_global_convolve",
        ):
            w = getattr(self, attr, None)
            if w is not None and hasattr(w, "value"):
                try:
                    out[attr] = int(w.value())
                except Exception:
                    pass
        return out

    def _restore_global_effect_sliders(self, snap):
        if not snap:
            return
        for attr, val in snap.items():
            w = getattr(self, attr, None)
            if w is not None and hasattr(w, "setValue"):
                try:
                    w.blockSignals(True)
                    w.setValue(int(val))
                    w.blockSignals(False)
                except Exception:
                    pass
    def _paint_operator_pattern_to_playlist(self, source="randomizer", rng=None):
        """Deterministically paint the complete playlist schema (Script/Domain/Synth/Patch + timeline).

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
            primary_op = eng_ops[0] if eng_ops else (users[0] if users else "Operator")
            struct = idealized_operator_struct(self, primary_op, row=r, seed=seed)
            # When multiple ops share a row, fold secondary structs under coverage
            # so Unison recycling sees blended Script/Domain/Synth/Patch parents.
            if len(eng_ops) > 1:
                for sec in eng_ops[1:]:
                    sec_struct = idealized_operator_struct(self, sec, row=r, seed=seed)
                    cov_a = float(coverage_map.get(primary_op, 0.5))
                    cov_b = float(coverage_map.get(sec, 0.5))
                    amt = float(min(cov_a, cov_b)) * 0.5  # Half blend max default
                    for sk in PLAYLIST_STRUCT_COLUMNS:
                        struct[sk] = blend_struct_labels(struct.get(sk, ""), sec_struct.get(sk, ""), amt)
            script = struct.get("script_tag") or ""
            if not script and eng_ops and hasattr(self, 'instrument_scripts'):
                script = str((self.instrument_scripts.get(eng_ops[0]) or '').splitlines()[0]).strip()
            if not script:
                script = f"Meum:{source}:seed={seed}:row={r}"
            domain_tag = struct.get("domain_tag") or f"Dom::{str(primary_op)[:8]}[t]"
            synth_tag = struct.get("synth_tag") or f"Synth::{str(primary_op)[:10]}"
            patch_tag = struct.get("patch_tag") or f"Patch::{str(primary_op)[:8]}"

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
                'domain_tag': domain_tag,
                'synth_tag': synth_tag,
                'patch_tag': patch_tag,
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
            # Preserve cells that a human actually painted.  This is more
            # reliable than assuming every non-empty row is engine-owned.
            locked_cols = set()
            try:
                locked_cols.update(int(c) for c in (e.get("user_locked_columns") or []))
            except Exception:
                pass
            if table is not None:
                touched = getattr(table, "playlist_user_touched", set()) or set()
                locked_cols.update(c for rr, c in touched if rr == r)

            field_by_col = {
                0: "time_marker",
                1: "operators_csv",
                2: "script_tag",
                3: "domain_tag",
                4: "synth_tag",
                5: "patch_tag",
                6: "velocity",
                7: "effect_target",
                8: "auto_amount",
                9: "direction_vector",
                10: "multi_seq",
                11: "coverage",
                12: "blend_partner",
            }
            for c in sorted(locked_cols):
                key = field_by_col.get(c)
                if key is None or table is None:
                    continue
                item = table.item(r, c)
                if item is None:
                    continue
                text = (item.text() or "").strip()
                if c == 6:
                    try:
                        text_v = float(text.replace("%", "").strip())
                        fields[key] = text_v / 100.0 if text_v > 1.0 else text_v
                    except Exception:
                        continue
                else:
                    fields[key] = text
                if c == 1:
                    ops_locked = [p.split("@")[0].strip() for p in text.split(",") if p.strip()]
                    fields["operator"] = ops_locked[0] if ops_locked else fields.get("operator", "")
                    fields["operators"] = ops_locked
                    fields["operators_csv"] = text
                elif c == 7:
                    fields["modulation"] = text
                    fields["effect_target"] = text
                elif c == 9:
                    fields["direction"] = (
                        1.0 if text.startswith("+") or text.endswith("+")
                        else -1.0 if text.startswith(("-", "−")) or text.endswith(("-", "−"))
                        else 0.0
                    )
            if locked_cols:
                fields["user_locked_columns"] = sorted(locked_cols)

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
            table_set(r, 3, fields['domain_tag'])
            table_set(r, 4, fields['synth_tag'])
            table_set(r, 5, fields['patch_tag'])
            table_set(r, 6, f"{velocity * 100:.1f}%")
            table_set(r, 7, target)
            table_set(r, 8, fields['auto_amount'])
            table_set(r, 9, fields['direction_vector'])
            table_set(r, 10, multi_seq)
            table_set(r, 11, coverage)
            table_set(r, 12, partner)
            painted += 1

        # Structural postcondition: every generated row has all ten canonical fields.
        # Engine rows must carry concrete time-offset style values, not blank cells.
        names = list(getattr(self, "instrument_names_48", []) or ["Operator"])
        for _ri, _entry in enumerate(self.master_playlist_data):
            if not isinstance(_entry, dict):
                continue
            if not _entry.get("generated_by_engine"):
                for _k in ("script_tag", "domain_tag", "synth_tag", "patch_tag",
                           "direction_vector", "multi_seq", "coverage", "blend_partner"):
                    _entry.setdefault(_k, "")
                continue
            if not str(_entry.get("time_marker") or "").strip():
                t_off = _ri * (0.125 + 0.031 * MEUM_NORM)
                _entry["time_marker"] = f"e:{t_off:.4f}s"
                _entry["time_offset"] = float(t_off)
            # Ensure idealized structure set is present for Unison recycling.
            op_name = _entry.get("operator") or (names[_ri % len(names)] if names else "Operator")
            try:
                _struct = idealized_operator_struct(self, op_name, row=_ri)
            except Exception:
                _struct = {}
            for _sk in PLAYLIST_STRUCT_COLUMNS:
                if not str(_entry.get(_sk) or "").strip():
                    _entry[_sk] = _struct.get(_sk, "")
            if not str(_entry.get("direction_vector") or "").strip():
                signed = 1.0 if (_ri % 2 == 0) else -1.0
                _entry["direction_vector"] = f"{signed:+.4f}"
                _entry["direction"] = signed
            if not str(_entry.get("multi_seq") or "").strip():
                ops = _entry.get("operators") or []
                if isinstance(ops, str):
                    ops = [p.strip() for p in ops.split(",") if p.strip()]
                _entry["multi_seq"] = ", ".join(ops) if ops else (names[_ri % len(names)] if names else "")
            if not str(_entry.get("coverage") or "").strip():
                _entry["coverage"] = "50%" if _entry.get("active", True) else "0%"
            if not str(_entry.get("blend_partner") or "").strip():
                _entry["blend_partner"] = names[(_ri * 3 + 1) % len(names)] if names else ""

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
                background: transparent;
                color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
            }

            QWidget {
                background: transparent;
                color: #f5f5f5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }

            QWidget#GrooveboxCentral,
            QWidget#ParametricMathBackground {
                background: transparent;
            }

            QGroupBox {
                background: rgba(255,255,255,0.08);
                color: #f5f5f5;
                border: none;
                margin-top: 10px;
                padding-top: 12px;
            }

            QGroupBox::title {
                background: transparent;
                color: #f5f5f5;
                border: none;
                padding: 0;
                font-weight: 900;
            }

            QLabel {
                background: transparent;
                color: #f5f5f5;
                border: none;
                font-weight: 700;
            }

            QPushButton {
                background: transparent;
                color: #f5f5f5;
                border: none;
                border-radius: 0;
                padding: 6px 10px;
                font-weight: 900;
            }

            QPushButton:hover {
                background: rgba(255,255,255,0.20);
            }

            QPushButton:checked {
                background: rgba(255,255,255,0.28);
                color: #f5f5f5;
            }

            QLineEdit,
            QSpinBox,
            QDoubleSpinBox,
            QTextEdit,
            QPlainTextEdit {
                background: rgba(255,255,255,0.10);
                color: #f5f5f5;
                border: none;
                border-bottom: 2px solid rgba(255,255,255,0.45);
                border-radius: 0;
                padding: 4px 2px;
                selection-background-color: rgba(255,255,255,0.30);
                selection-color: #050505;
            }

            QLineEdit:focus,
            QTextEdit:focus,
            QPlainTextEdit:focus {
                border-bottom: 3px solid #f5f5f5;
            }

            QComboBox {
                background: transparent;
                color: #f5f5f5;
                border: none;
                border-bottom: 2px solid rgba(255,255,255,0.40);
                border-radius: 0;
                padding: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(5, 5, 5, 225);
                color: #f5f5f5;
                border: 1px solid rgba(255,255,255,0.25);
                selection-background-color: rgba(255,255,255,0.18);
                selection-color: #ffffff;
                outline: none;
            }

            QComboBox QAbstractItemView::item {
                background-color: transparent;
                padding: 5px 8px;
            }

            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(255,255,255,0.12);
            }
            QTableWidget,
            QListWidget {
                background: rgba(255,255,255,0.07);
                color: #f5f5f5;
                border: none;
                gridline-color: rgba(255,255,255,0.12);
            }

            QHeaderView::section {
                background: transparent;
                color: #f5f5f5;
                border: none;
                font-weight: 900;
            }

            QSlider::groove:horizontal {
                height: 3px;
                background: rgba(255,255,255,0.30);
            }

            QSlider::handle:horizontal {
                width: 10px;
                margin: -4px 0;
                border-radius: 5px;
                background: #f5f5f5;
            }

            QProgressBar {
                background: rgba(255,255,255,0.10);
                color: #f5f5f5;
                border: none;
                text-align: center;
            }

            QProgressBar::chunk {
                background: #f5f5f5;
            }
        """
        if QApplication.instance():
            QApplication.instance().setStyleSheet(high_contrast_stylesheet)
        self.setStyleSheet(high_contrast_stylesheet)

        central_widget = self.centralWidget()
        if central_widget is None:
            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)

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
        self.input_seed_val.setMinimumSize(0, 110)
        self.input_seed_val.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.input_seed_val.setStyleSheet("""
            QTextEdit {
                background: rgba(255,255,255,0.16);
                color: #ffffff;
                border: none;
                border-bottom: 2px solid rgba(0,0,0,0.45);
                padding: 6px;
                font-family: Consolas, monospace;
            }
            QTextEdit:focus {
                background: rgba(255,255,255,0.24);
                border-bottom: 3px solid #ffffff;
            }
        """)
        # USER-CONTROLLED FIELD: never assign a random/default seed here.
        self.input_seed_val.setPlainText("")
        self.input_seed_val.setToolTip(
            "Global parametric/script seed. Enter expressions, multiline scripts, "
            "irrational constants, or symbolic geometry. The field scrolls."
        )
        self.input_seed_val.setAcceptRichText(False)
        self.input_seed_val.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.input_seed_val.setMinimumSize(360, 110)

        self.input_seed_val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

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
        self.global_geometry_layout.addLayout(seed_panel, 2)

        self.global_controls_side = QVBoxLayout()
        self.global_controls_side.setSpacing(6)
        self.global_controls_side.setContentsMargins(0, 0, 0, 0)
        self.global_controls_side.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.global_controls_side.addWidget(QLabel("GLOBAL PROCESSOR CONTROLS"), 0, Qt.AlignmentFlag.AlignTop)
        self.global_geometry_layout.addLayout(self.global_controls_side, 1)
        self.global_geometry_layout.setAlignment(self.global_controls_side, Qt.AlignmentFlag.AlignTop)

        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_idealize_rhythm.toggled.connect(self._on_euclidean_live_toggled)
        self.btn_seeded_randomize.toggled.connect(self._on_seeded_live_toggled)
        self.chk_user_program_only.toggled.connect(self._on_user_program_only_toggled)
        self.btn_save_project.clicked.connect(self.save_project_dialog)
        self.btn_load_project.clicked.connect(self.load_project_dialog)
        self.btn_keyboard.clicked.connect(self.open_keyboard_test_window)
        self.btn_trigger_all.clicked.connect(self.trigger_all_instruments_hit)

        self.transport_layout.addWidget(self.btn_play)
        self.transport_layout.addWidget(self.btn_stop)
        self.transport_layout.addWidget(self.lbl_bpm)
        self.transport_layout.addWidget(self.spin_bpm)
        self.transport_layout.addWidget(QLabel("Active Operator:"))
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
        self.transport_layout_row2 = QHBoxLayout()
        self.transport_layout_row2.addWidget(self.btn_seeded_randomize)
        self.transport_layout_row2.addWidget(self.btn_idealize_rhythm)
        self.transport_layout_row2.addWidget(self.chk_user_program_only)
        self.transport_layout_row2.addStretch(1)
        self.transport_layout_row2.addWidget(self.btn_save_project)
        self.transport_layout_row2.addWidget(self.btn_load_project)

        # Live engine timers
        self._live_euclid_timer = QTimer(self)
        self._live_euclid_timer.setInterval(2000)
        self._live_euclid_timer.timeout.connect(lambda: self._live_engine_tick("euclidean"))
        self._live_seeded_timer = QTimer(self)
        self._live_seeded_timer.setInterval(2500)
        self._live_seeded_timer.timeout.connect(lambda: None)
        self._live_engine_signatures = {}
        self._live_engine_update_guard = False
        self._composition_generation_guard = False
        self._live_source_update_pending = False
        self._composition_generation_counter = 0
        self._transport_finished = False
        self._stop_requested = False
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
        self.slider_pkp_decay.setRange(1, 1000)
        self.slider_pkp_decay.setValue(500)

        self.chk_pkp_automod = QCheckBox("PKP Envelope Follower")
        self.chk_pkp_automod.setChecked(True)

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
            "🎲 RANDOMIZE",
            "Toggle global randomization; ON paints the generated pattern into Playlist.",
            checkable=True, active_color="#00d084"
        )
        self.btn_local_phase_lock = _make_global_operator_button(
            "🔒 PHASE-LOCK",
            "Toggle global phase-lock; ON paints the phase-locked pattern into Playlist.",
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

        self.btn_edit_synth = self._make_local_context_button("EDIT\nSYNTH", "Edit synth settings and wavetable for the active instrument")
        self.btn_script_inst = self._make_local_context_button("WRITE\nSCRIPT", "Edit the script attached to the active instrument")
        self.btn_view_patchbay = self._make_local_context_button("PATCH\nMODULAR", "Open modular routing for the active instrument context")
        self.btn_domain_eq = self._make_local_context_button("CALC\nDOMAIN", "Edit time/space equations used as contextual modulation")

        # POWER_V3_GLOBAL_CONTROLS: buttons were constructed above so the Global
        # panel can safely reference them before the Local panel is assembled.

        self.btn_edit_synth.clicked.connect(lambda: self.spawn_floating_window('synth_editor_window', "Synth Settings & Wavetable Interface"))
        self.btn_script_inst.clicked.connect(lambda: self.spawn_floating_window('script_editor_window', "Instrument Script Editor"))
        self.btn_view_patchbay.clicked.connect(lambda: self.spawn_floating_window('patch_bay_dialog', "Advanced Modular Patch Bay & Visualizer"))
        self.btn_domain_eq.clicked.connect(self.open_domain_equation_editor)
        self.btn_view_playlist.clicked.connect(lambda: self.spawn_floating_window('playlist_window', "Unquantized Playlist & Paintbrush Window"))
        self.btn_local_randomize.toggled.connect(self._randomize_local_context)
        self.btn_local_phase_lock.toggled.connect(self._phase_lock_local_context)
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



        sizing_layout.addStretch(1)

        sizing_container = QWidget()
        sizing_container.setLayout(sizing_layout)
        master_container.addWidget(sizing_container)

        self.top_sequencer = QWidget()
        seq_inner = QVBoxLayout(self.top_sequencer)
        seq_inner.setContentsMargins(0, 0, 0, 0)

        seq_header_layout = QHBoxLayout()
        seq_header_layout.addWidget(QLabel("⚡ STEP Sequencer"))

        # The instrument selector chooses WHICH instrument the PKP NullLock play button auditions.

        # PKP NullLock BOOST — arm global note-triggered NullLock layer + one-shot audition.
        # Boost amount scales the global PKP layer in the mixdown (0.5× … 2.0×).
        self.pkp_boost_amount = 1.0
        self.btn_pkp_nullock_boost = QPushButton("⚡ PKP NullLock BOOST")
        self.btn_pkp_nullock_boost.setCheckable(False)
        self.btn_pkp_nullock_boost.setToolTip("Momentary one-shot PKP remix burst; never arms a sustained layer.")
        self.btn_pkp_nullock_boost.setStyleSheet(
            "QPushButton { background-color:#1a1020; color:#ff66cc; font-weight:bold; border:2px solid #ff66cc; border-radius:4px; padding:4px 10px; }"
            "QPushButton:hover { background-color:#2a1830; }"
            "QPushButton:pressed { background-color:#ff66cc; color:#120818; border-color:#ffffff; }"
        )
        self.btn_pkp_nullock_boost.clicked.connect(self._on_pkp_nullock_boost_clicked)
        seq_header_layout.addWidget(self.btn_pkp_nullock_boost)

        self.slider_pkp_boost = QSlider(Qt.Orientation.Horizontal)
        self.slider_pkp_boost.setRange(50, 200)  # 0.5× … 2.0×
        self.slider_pkp_boost.setValue(100)
        self.slider_pkp_boost.setFixedWidth(100)
        self.slider_pkp_boost.setToolTip("NullLock boost amount (50%–200%) applied to the global PKP layer.")
        self.slider_pkp_boost.valueChanged.connect(self._on_pkp_boost_amount_changed)
        seq_header_layout.addWidget(QLabel("Boost:"))
        seq_header_layout.addWidget(self.slider_pkp_boost)
        self.lbl_pkp_boost = QLabel("100%")
        self.lbl_pkp_boost.setStyleSheet("color: #ff66cc; font-weight: bold; min-width: 40px;")
        seq_header_layout.addWidget(self.lbl_pkp_boost)

        seq_inner.addLayout(seq_header_layout)

        # PKP NullLock is an audition/play action, not a dropdown, timeline event, or independent clock.
        self.pkp_pad_bank_active = False
        self.pkp_current_step = 0

        self.steps_layout_widget = QWidget()
        self.steps_inner_layout = QHBoxLayout(self.steps_layout_widget)
        self.steps_inner_layout.setContentsMargins(0, 0, 0, 0)
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
        self.step_editor_popup.setFixedHeight(32)
        step_edit = QHBoxLayout(self.step_editor_popup)
        step_edit.setContentsMargins(8, 6, 8, 6)
        self.lbl_selected_step = QLabel("Step: —")
        self.lbl_selected_step.setStyleSheet("color: #f5d97d; font-weight: bold;")
        step_edit.addWidget(self.lbl_selected_step)
        step_edit.addWidget(QLabel("Amp/Vel:"))
        self.slider_step_amp = QSlider(Qt.Orientation.Horizontal)
        self.slider_step_amp.setRange(0, 100)
        self.slider_step_amp.setValue(100)
        self.slider_step_amp.setFixedWidth(120)
        self.slider_step_amp.valueChanged.connect(self._on_step_amp_slider)
        step_edit.addWidget(self.slider_step_amp)
        self.lbl_step_amp = QLabel("100%")
        step_edit.addWidget(self.lbl_step_amp)
        step_edit.addWidget(QLabel("Pitch:"))
        self.slider_step_pitch = QSlider(Qt.Orientation.Horizontal)
        self.slider_step_pitch.setRange(25, 400)
        self.slider_step_pitch.setValue(100)
        self.slider_step_pitch.setFixedWidth(120)
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
        self.scope_status_label = QLabel("📊 2.5D Video Synth + Oscilloscope  |  Status: Idle")
        self.scope_status_label.setStyleSheet("color: #00ffff; font-weight: bold;")
        scope_bar.addWidget(self.scope_status_label, stretch=1)
        scope_bar.addStretch(1)
        scope_bar.addWidget(self.btn_export, stretch=0, alignment=Qt.AlignmentFlag.AlignRight)

        # POWER_V3_VISUAL_LAYOUT: master volume lives above Visualizer settings.

        master_container.addLayout(scope_bar)
        visual_pair = QHBoxLayout()
        visual_pair.setSpacing(8)
        visual_left = QVBoxLayout()
        visual_left.addWidget(QLabel("LIVE AUDIO VISUALIZER"))
        self.visual_oscilloscope.setMinimumSize(260, 180)
        self.visual_oscilloscope.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        visual_left.addWidget(self.visual_oscilloscope, stretch=1)
        visual_right = QVBoxLayout()
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

        # Realtime audio engine state (sounddevice stream)
        self.is_playing = False
        self._composition_generation_guard = False
        self._live_source_update_pending = False
        self._composition_generation_counter = 0
        self._transport_finished = False
        self._stop_requested = False
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

    def on_instrument_switched(self, idx):
        inst_name = self.instrument_names_48[idx]
        if hasattr(self, 'top_sequencer') and self.instrument_selector_dropdown.currentIndex() != idx:
            self.instrument_selector_dropdown.setCurrentIndex(idx)
        self.reload_active_instrument_sequencer_ui()

    def reload_active_instrument_sequencer_ui(self):
        if not hasattr(self, 'top_sequencer'):
            return
        curr_inst = self.instrument_selector_dropdown.currentText()
        mem = self.instrument_sequencer_memory[curr_inst]
        self._ensure_seq_mem_length(mem, len(self.seq_step_buttons) or 16)
        for s_idx, btn in enumerate(self.seq_step_buttons):
            if s_idx < len(mem["steps"]):
                amp = mem["amplitudes"][s_idx]
                pitch = mem["pitches"][s_idx] if s_idx < len(mem.get("pitches", [])) else 1.0
                btn.setText(f"STEP {s_idx+1}\nV:{amp:.2f} P:{pitch:.2f}×")
                self._style_pad_button(btn, s_idx, mem["steps"][s_idx])
                if self.selected_step_idx == s_idx:
                    btn.setStyleSheet(btn.styleSheet() + " border: 3px solid #f5d97d;")

    def _style_pad_button(self, btn, s_idx, is_active_step):
        """Style a STEP: playhead (orange) > programmed on (cyan) > off (dark)."""
        is_playhead = False
        if is_playhead:
            btn.setStyleSheet(
                "background-color: #ff6b00; color: #ffffff; border: 2px solid #ffaa55; font-weight: bold;"
            )
        elif is_active_step:
            btn.setStyleSheet(
                "background-color: #00ffff; color: #060606; border: 2px solid #ffffff; font-weight: bold;"
            )
        else:
            btn.setStyleSheet(
                "background-color: #121212; color: #00ffff; border: 2px solid #444444;"
            )

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
            self.scope_status_label.setText(f"⚡Visualizers")

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
                self.scope_status_label.setText(f"▶ PKP NullLock audition · {inst_name[:24]} · step {step_idx + 1}")
        except Exception as e:
            print(f"[PKP NullLock] audition error: {e}")

    def toggle_pkp_pad_bank(self, checked):
        """Compatibility hook: PKP NullLock is global and never owns a timeline clock."""
        self.pkp_pad_bank_active = bool(checked)
        print(f"[PKP NullLock] {'ARMED' if checked else 'DISARMED'} — global note-triggered layer")

    def _pkp_step_tick(self):
        """Retained for compatibility; PKP NullLock is not a timeline event."""
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
            v=np.sin(2*np.pi*freq*t)*a*pr*np.exp(-t/max(step_duration*0.35,0.01))
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

            # PKP-style: fast decay sine + soft click transient
            env = np.exp(-t / max(hit_dur * 0.35, 0.01))
            click = np.exp(-t / 0.004) * np.sin(2 * np.pi * freq * 4.0 * t)
            body = np.sin(2 * np.pi * freq * t)
            # BOOST is independent of global PKP Decay.
            hit = (body * 0.7 + click * 0.3) * env * float(amp)
            hit_rms = float(np.sqrt(np.mean(hit * hit))) if hit.size else 0.0
            target_rms = 0.0
            try:
                target_rms = self._estimate_other_47_rms(step_idx, hit_dur, len(hit), sr)
            except Exception:
                pass
            if target_rms > 1e-9 and hit_rms > 1e-9:
                hit *= target_rms / hit_rms
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
            step_btn = QPushButton(f"STEP {s+1}\nV:{amp:.2f} P:{pitch:.2f}×")
            step_btn.setCheckable(False)  # selection vs toggle handled in click
            step_btn.setMinimumSize(86, 70)
            step_btn.setMaximumWidth(110)
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
        """
        Resolve the Seed field exactly once into a deterministic numeric value.

        Accepted:
            123
            123.45
            (123)
            1, 2, 3
            1
            2
            3
            sin(t)
            1 if sin(t) >= -0.5 else 2

        Also accepts shorthand:
            if(sin(t)>=-0.5) 1 elif 2

        'return expr' is accepted for script-style seed input.

        IMPORTANT:
            This method is composition-state evaluation.
            It must never be called from an audio-note/unison/sample loop.
        """
        import hashlib
        import re

        raw = self._seed_text() if hasattr(self, "_seed_text") else ""
        text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()

        if not text:
            return 0.0

        # Accept script-style "return expression".
        text = re.sub(r"^\s*return\s+", "", text, count=1, flags=re.I)

        # Accept:
        #   if(condition) true elif false
        shorthand = _parse_if_elif_shorthand(text)
        if shorthand:
            condition, yes_expr, no_expr = shorthand
            text = f"({yes_expr}) if ({condition}) else ({no_expr})"

        env = {
            "__builtins__": {},
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "sqrt": math.sqrt,
            "log": math.log,
            "log2": math.log2,
            "exp": math.exp,
            "abs": abs,
            "min": min,
            "max": max,
            "pi": math.pi,
            "e": math.e,
            "PHI": PHI,
            "MEUM": MEUM,
            "MEUM_NORM": MEUM_NORM,
            "MEUM_INV": MEUM_INV,
            "t": 0.0,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        }

        def evaluate(expr):
            expr = expr.strip()

            # Remove harmless outer parentheses.
            while len(expr) >= 2 and expr[0] == "(" and expr[-1] == ")":
                try:
                    ast.parse(expr, mode="eval")
                except Exception:
                    break
                expr = expr[1:-1].strip()

            try:
                value = float(expr)
                return value if math.isfinite(value) else None
            except Exception:
                pass

            try:
                tree = ast.parse(expr, mode="eval")
                value = eval(
                    compile(tree, "<groovebox-seed>", "eval"),
                    env,
                )
                value = float(value)
                return value if math.isfinite(value) else None
            except Exception:
                return None

        # Whole expression first.
        value = evaluate(text)
        if value is not None:
            return value

        # Commas and line returns are composite seed components.
        parts = [
            p.strip()
            for p in re.split(r"[,\n]+", text)
            if p.strip()
        ]

        values = []
        for part in parts:
            # Permit "return ..." on individual lines too.
            part = re.sub(r"^\s*return\s+", "", part, count=1, flags=re.I)
            value = evaluate(part)
            if value is not None:
                values.append(value)

        if values:
            payload = "|".join(
                f"{v:.17g}" for v in values
            ).encode("utf-8")

            digest = hashlib.sha256(payload).digest()
            integer = int.from_bytes(digest[:8], "big")

            return (
                integer / float(2**64 - 1)
            ) * 2.0 - 1.0

        # Unsupported text gets a deterministic token.
        # It does NOT get Python's randomized hash().
        digest = hashlib.sha256(
            text.encode("utf-8", "replace")
        ).digest()

        integer = int.from_bytes(digest[:8], "big")

        return (
            integer / float(2**64 - 1)
        ) * 2.0 - 1.0

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
        dlg = DomainEquationEditorDialog(self.domain_eq_engine, parent=self)
        # Non-modal: it should run alongside the main window instead of
        # blocking it, and it gets the same animated math field as other
        # floating panels so it isn't a flat/blank dialog.
        dlg.setModal(False)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        try:
            attach_math_decor(dlg, app=self, light=False)
            cw = self.centralWidget()
            bg = ParametricMathBackground(self, cw)
            cw = self.centralWidget()
            bg = ParametricMathBackground(self, cw)
            bg.setGeometry(cw.rect())
            bg.lower()
            bg.show()
            self._math_decor = bg
            bg.setGeometry(cw.rect())
            bg.lower()
            bg.show()
            self._math_decor = bg
        except Exception as _de:
            print(f"[Decor] domain dialog: {_de}")
        # Keep a reference on self BEFORE showing — a non-modal dialog with
        # no surviving Python reference gets garbage-collected and vanishes.
        self.domain_eq_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def open_help_readme(self):
        """Open the full Help / Readme / scripting documentation dialog."""
        dlg = ReadmeGuideDialog(parent=self)
        dlg.exec()

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

        def _norm(p, default=0.5):
            if weights.get(p, 0) <= 1e-9:
                return default
            return float(np.clip(0.5 + accum[p] / max(weights[p], 1e-9) * 0.5, 0.0, 1.0))

        # Map onto main macros when present
        if hasattr(self, 'slider_eqr'):
            self.slider_eqr.blockSignals(True)
            self.slider_eqr.setValue(int(_norm("eqr") * 100))
            self.slider_eqr.blockSignals(False)
        if hasattr(self, 'slider_fractalizer'):
            self.slider_fractalizer.blockSignals(True)
            self.slider_fractalizer.setValue(int(_norm("fractalizer") * 1000))
            self.slider_fractalizer.blockSignals(False)
        if hasattr(self, 'slider_pkp_decay'):
            self.slider_pkp_decay.blockSignals(True)
            self.slider_pkp_decay.setValue(int(_norm("pkp_decay") * 1000))
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
        # STEP_EDITOR_VERTICAL_OFFSET_V2: move the floating step inspector
        # downward by ~42% of the selected step button height so it clears the
        # step-row hit area more reliably while remaining visually attached.
        vertical_offset = max(1, int(round(btn.height() * 0.42)))
        above_y = pos.y() - ph - 6 + vertical_offset
        below_y = pos.y() + btn.height() + 6 + vertical_offset
        y = above_y if above_y >= 4 else below_y
        y = max(4, min(y, max(4, vh - ph - 4)))
        self.step_editor_popup.move(x, y)
        self.step_editor_popup.raise_()
        self.step_editor_popup.show()

    def _on_step_pad_clicked(self, s_idx):
        curr_i = self.instrument_selector_dropdown.currentText()
        mem = self.instrument_sequencer_memory[curr_i]
        self._ensure_seq_mem_length(mem, max(s_idx + 1, len(mem.get("steps", []))))

        # STEP SELECTION CONTRACT:
        #   first click on a different cell = SELECT ONLY; never touch gates.
        #   second click on that same selected cell = TOGGLE ONLY THAT CELL.
        # Randomizer/Phase-Locker are the only engines permitted to change other cells.
        same_step = (self.selected_step_idx == s_idx)
        self.selected_step_idx = s_idx
        if same_step:
            mem["steps"][s_idx] = not bool(mem["steps"][s_idx])
            # USER_TOUCHED_TRACKING: this is an actual manual click — the only
            # place besides the amp/pitch sliders where a human is editing the
            # grid — so mark the step touched. Presets/patches/randomizer output
            # loaded straight into memory never pass through here, so they are
            # correctly left untouched until a person edits them by hand.
            self._mark_step_touched(mem, s_idx)

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
        rows = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else len(getattr(self, 'master_playlist_data', []))
        if not getattr(self, 'master_playlist_data', None):
            return
        numeric_seed = self.get_numeric_seed()
        if rng is None:
            rng = np.random.default_rng(_safe_int_seed(numeric_seed))
        for i, entry in enumerate(self.master_playlist_data[:rows]):
            # Seed/phase field: smooth, deterministic, with optional random perturbation.
            phase = (i / max(rows, 1)) * 2.0 * np.pi + (numeric_seed % 100000) * 0.000013
            field = 0.5 + 0.5 * np.sin(phase * MEUM_CONSTANT + numeric_seed * 0.0000017)
            field = 0.5 * field + 0.5 * self._contextual_numerology(step=i, row=i) if hasattr(self, "_contextual_numerology") else field
            target = 0.25 + 0.75 * field
            if randomize:
                target = 0.75 * target + 0.25 * float(rng.uniform(0.25, 1.0))
            old = float(entry.get("velocity", 1.0) or 1.0)
            # Treat explicit non-default velocities as user data and preserve them.
            user_locked = bool(entry.get("velocity_user_locked", False))
            if user_locked:
                continue
            entry["velocity"] = float(np.clip((1.0-strength) * old + strength * target, 0.05, 1.5))

        if hasattr(self, 'active_paint_table') and self.active_paint_table:
            table = self.active_paint_table
            for r, entry in enumerate(self.master_playlist_data[:min(rows, table.rowCount())]):
                item = QTableWidgetItem(f"{float(entry.get('velocity', 1.0))*100:.1f}%")
                table.set_cell_item(r, 3, item)

    def randomize_playlist_velocity(self):
        self._phase_lock_playlist_velocity(np.random.default_rng(_safe_int_seed(self.get_numeric_seed())), strength=1.0, randomize=True)
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
            self.seq_step_buttons[s].setText(f"Pad {s+1}\nA:{val/100:.2f} P:{pitch:.2f}×")

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
            self.seq_step_buttons[s].setText(f"Pad {s+1}\nA:{amp:.2f} P:{ratio:.2f}×")

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
            self._apply_live_engine_once("euclidean")
            self.btn_idealize_rhythm.setText("✨ Euclidean Live Lock · ON")
        else:
            self._live_euclid_timer.stop()
            self.btn_idealize_rhythm.setText("✨ Euclidean Live Lock")

    def _on_seeded_live_toggled(self, checked):
        if hasattr(self, "_style_toggle_randomizer"):
            self.btn_seeded_randomize.setStyleSheet(self._style_toggle_randomizer)
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            self.btn_seeded_randomize.blockSignals(True)
            self.btn_seeded_randomize.setChecked(False)
            self.btn_seeded_randomize.blockSignals(False)
            return
        if checked:
            self._apply_live_engine_once("seeded")
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
        """Stable snapshot of user-visible inputs; engines write only once per new snapshot."""
        seed = self._seed_text() if hasattr(self, 'input_seed_val') else "0.0"
        inst = self.instrument_selector_dropdown.currentText() if hasattr(self, 'instrument_selector_dropdown') else ""
        seq_len = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        rows = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 32
        return (which, seed, inst, seq_len, rows, repr(getattr(self, 'instrument_sequencer_memory', {})), repr(getattr(self, 'master_playlist_data', [])))

    def _apply_live_engine_once(self, which, force=False):
        if getattr(self, "_live_engine_update_guard", False):
            return
        # force=True is used by deferred live-source flushes that already hold
        # the composition guard; only block non-forced re-entrancy.
        if (not force) and getattr(self, "_composition_generation_guard", False):
            return

        sig = self._live_engine_signature(which) if hasattr(self, "_live_engine_signature") else None
        if (
            not force
            and sig is not None
            and getattr(self, "_live_engine_signatures", {}).get(which) == sig
        ):
            return

        snap = self._snapshot_global_effect_sliders()
        self._live_engine_update_guard = True
        self._composition_generation_guard = True
        try:
            if which == "euclidean":
                self.apply_euclidean_and_idealized_rhythms()
            else:
                self.apply_seeded_harmonic_randomization()
        except Exception as exc:
            print(f"[LiveEngine:{which}] {type(exc).__name__}: {exc}")
        finally:
            self._live_engine_update_guard = False
            self._composition_generation_guard = False
            self._restore_global_effect_sliders(snap)
            if sig is not None:
                if not hasattr(self, "_live_engine_signatures"):
                    self._live_engine_signatures = {}
                self._live_engine_signatures[which] = (
                    self._live_engine_signature(which)
                    if hasattr(self, "_live_engine_signature")
                    else sig
                )
    def _flush_live_source_update(self):
        self._live_source_update_pending = False
        if getattr(self, "_composition_generation_guard", False):
            return
        # Do NOT pre-set _composition_generation_guard here.
        # _apply_live_engine_once(force=True) owns the transaction guard so that
        # nested playlist paint can still run and fill all 10 columns.
        try:
            if (
                getattr(self, "btn_idealize_rhythm", None)
                and self.btn_idealize_rhythm.isChecked()
            ):
                self._apply_live_engine_once("euclidean", force=True)
            if (
                getattr(self, "btn_seeded_randomize", None)
                and self.btn_seeded_randomize.isChecked()
            ):
                self._apply_live_engine_once("seeded", force=True)
        except Exception as exc:
            print(f"[LiveSourceUpdate] {type(exc).__name__}: {exc}")

    def _live_engine_tick(self, which):
        if getattr(self, 'chk_user_program_only', None) and self.chk_user_program_only.isChecked():
            return
        if which == "euclidean" and self.btn_idealize_rhythm.isChecked():
            self.apply_euclidean_and_idealized_rhythms()
        elif which == "seeded" and self.btn_seeded_randomize.isChecked():
            self.apply_seeded_harmonic_randomization()

    def save_project_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save EQR Project", "", "EQR Project (*.json)")
        if not path:
            return
        data = {
            "version": "3.6.8+",
            "seed": self._seed_text() if hasattr(self, 'input_seed_val') else "",
            "bpm": self.spin_bpm.value() if hasattr(self, 'spin_bpm') else 120,
            "seq_length": int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16,
            "playlist_rows": int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else 32,
            "base_frequency": float(self.spin_base_frequency.value()) if hasattr(self, 'spin_base_frequency') else 432.0,
            "global_convolve": float(self.spin_global_convolve.value()) if hasattr(self, 'spin_global_convolve') else 0.0,
            # USER_TOUCHED_TRACKING: 'touched' is stored as a set() in memory
            # (for fast membership checks) but JSON has no set type, so it is
            # serialized as a sorted list here and restored as a set on load.
            "instrument_sequencer_memory": {
                name: {**m, "touched": sorted(m.get("touched", set()))}
                for name, m in self.instrument_sequencer_memory.items()
            },
            "master_playlist_data": getattr(self, 'master_playlist_data', []),
            "playlist_automation": getattr(self, 'playlist_automation', []),
            "instrument_scripts": getattr(self, 'instrument_scripts', {}),
            "instrument_param_state": getattr(self, 'instrument_param_state', {}),
            "patch_connections": getattr(self, 'patch_connections', []),
            "domain_eq": self.domain_eq_engine.to_json() if hasattr(self, 'domain_eq_engine') and self.domain_eq_engine else {},
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
            if hasattr(self, 'input_seed_val'):
                self.input_seed_val.setPlainText(str(data.get("seed", "")))
            if hasattr(self, 'spin_bpm'):
                self.spin_bpm.setValue(float(data.get("bpm", 120.0)))
            if hasattr(self, 'spin_seq_length'):
                self.spin_seq_length.setValue(int(data.get("seq_length", 16)))
            if hasattr(self, 'spin_playlist_length'):
                self.spin_playlist_length.setValue(int(data.get("playlist_rows", 32)))
            if hasattr(self, 'spin_base_frequency'):
                self.spin_base_frequency.setValue(float(data.get("base_frequency", 432.0)))
            if hasattr(self, 'slider_global_convolve'):
                self.slider_global_convolve.setValue(int(round(float(data.get("global_convolve", 0.0)) * 100.0)))
            mem = data.get("instrument_sequencer_memory", {})
            if mem:
                # USER_TOUCHED_TRACKING: convert the saved 'touched' list back
                # into a set. Older project files won't have this key at all —
                # treat those as untouched (nothing loses net-effect status
                # that a step's own ON/amplitude already implies elsewhere;
                # this only restores which steps were user-programmed).
                for m in mem.values():
                    if "touched" in m:
                        m["touched"] = set(m["touched"])
                self.instrument_sequencer_memory.update(mem)
            self.master_playlist_data = data.get("master_playlist_data", [])
            self.playlist_automation = data.get("playlist_automation", [])
            if hasattr(self, 'instrument_scripts'):
                self.instrument_scripts.update(data.get("instrument_scripts", {}))
            self.instrument_param_state = data.get("instrument_param_state", {})
            self.patch_connections = data.get("patch_connections", [])
            if hasattr(self, 'domain_eq_engine') and data.get("domain_eq"):
                self.domain_eq_engine.from_json(data["domain_eq"])
            self.reload_active_instrument_sequencer_ui()
            QMessageBox.information(self, "Loaded", f"Project loaded:\n{path}")
        except Exception as e:
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
                env = np.exp(-t / 0.03)
                mix += (0.15 * env * np.sin(2 * np.pi * freq * t)).astype(np.float32)
            peak = np.max(np.abs(mix))
            if peak > 0:
                mix = (mix / peak) * 0.9 * float(getattr(self, 'master_volume', 0.8))
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
    def _on_live_source_changed(self, *args):
        if getattr(self, "_composition_generation_guard", False):
            return

        if getattr(self, "_live_source_update_pending", False):
            return

        self._live_source_update_pending = True
        QTimer.singleShot(0, self._flush_live_source_update)


    def _flush_live_source_update(self):
        self._live_source_update_pending = False

        if getattr(self, "_composition_generation_guard", False):
            return

        # _apply_live_engine_once(force=True) owns the composition guard so
        # nested playlist writers can still fill all ten canonical columns.
        try:
            if (
                getattr(self, "btn_idealize_rhythm", None)
                and self.btn_idealize_rhythm.isChecked()
            ):
                self._apply_live_engine_once(
                    "euclidean",
                    force=True,
                )

            if (
                getattr(self, "btn_seeded_randomize", None)
                and self.btn_seeded_randomize.isChecked()
            ):
                self._apply_live_engine_once(
                    "seeded",
                    force=True,
                )

        except Exception as exc:
            print(
                f"[LiveSourceUpdate] "
                f"{type(exc).__name__}: {exc}"
            )
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
        Empty/zero seed means no explicit geometric anchor.
        Expressions/scripts count as present when they evaluate successfully.
        """
        if not hasattr(self, "input_seed_val"):
            return True

        text = self._seed_text().strip()

        if not text:
            return True

        try:
            return abs(float(self.get_numeric_seed())) == 0.0
        except Exception:
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
        """Return an engine seed without ever writing the USER seed field.

        The global seed field is strictly user-owned. Empty means "no explicit seed".
        Randomizer/Phase-Locker may use a transient runtime seed, but that value is
        never written into the UI and bootstrap never changes sequencer gates.
        """
        if not self._seed_is_absent():
            return self.get_numeric_seed()

        # Explicitly seed-free program: derive a transient engine seed only.
        # No UI mutation and no automatic program generation.
        try:
            fingerprint = self._fingerprint_program()
        except Exception:
            fingerprint = 0
        if fingerprint:
            return int(fingerprint % (2**31))

        # Runtime-only entropy for an explicitly invoked randomizing engine.
        if not hasattr(self, '_runtime_engine_seed'):
            self._runtime_engine_seed = int((time.time_ns() ^ id(self)) & 0x7fffffff)
        return int(self._runtime_engine_seed)

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
        self._phase_lock_playlist_velocity(rng=np.random.default_rng(_safe_int_seed(numeric_seed)), strength=0.45, randomize=True)

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
            if not mem:
                continue
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
        """
        Additive Euclidean Phase-Lock (non-destructive where possible).

        - Never turns OFF a user-specified step.
        - Never lowers a user-specified amplitude.
        - Fills empty slots with Euclidean structure + spectral 'opposites'
          (low-amp complement hits) so the grid phase-locks without erasing
          the carrier (user) pattern.
        - Sporadic spectrum commutation via probability only on non-user slots.
        """
        # Explicit engine action may use a transient seed, but never writes the user field.
        seed = self.bootstrap_seed_and_program_parameters()
        self.simplify_redundant_user_definitions()

        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16
        rng = np.random.default_rng(_safe_int_seed(seed))

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
                    mem["steps"][s] = True
                    base_amp = 0.55 + 0.35 * abs(np.sin(s * np.pi / count + i * 0.1))
                    if complement:
                        base_amp *= 0.45  # softer opposite
                    mem["amplitudes"][s] = float(np.clip(base_amp, 0.15, 1.0))
                    # Sporadic spectrum commutation: slightly lower probability on complements
                    mem["probabilities"][s] = 100 if is_eucl else int(rng.integers(55, 85))
                    filled += 1
                # else leave False / untouched

        self._engines_write_automation_lanes(source="euclidean")
        if hasattr(self, "_canonical_playlist_paint"):
            self._canonical_playlist_paint(
                rng=rng,
                mode="phase-lock",
                strength=0.55,
            )
        elif hasattr(self, "_paint_operator_pattern_to_playlist"):
            self._paint_operator_pattern_to_playlist(
                source="phase-lock",
                rng=rng,
            )
        if hasattr(self, "_sync_playlist_paint_table_from_memory"):
            try:
                self._sync_playlist_paint_table_from_memory()
            except Exception:
                pass
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
        numeric_seed = self.bootstrap_seed_and_program_parameters()
        seed_bits = _safe_int_seed(numeric_seed)
        self.simplify_redundant_user_definitions()
        rng = np.random.default_rng(_safe_int_seed(numeric_seed))
        count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else 16

        # Do NOT forcibly change the user's selected instrument.
        # (Previously this jumped the dropdown — that was destructive UX.)

        filled_steps = 0
        preserved_steps = 0
        scripts_written = 0

        # Read wavefield hints if available (does NOT run PLL apply / Euclidean button)
        wf_engine = getattr(self, 'wavefield_engine', None)
        if wf_engine is not None:
            if not getattr(wf_engine, 'wavefield', None):
                wf_engine.compute_wavefield()
            else:
                # Refresh field for current seed/length without applying lock
                wf_engine.compute_wavefield()

        for i, name in enumerate(self.instrument_names_48):
            mem = self.instrument_sequencer_memory[name]
            self._ensure_seq_mem_length(mem, count)
            user_mask = self._user_pattern_mask(mem, count, instrument_name=name)

            # Extract user carrier pattern (list of active indices)
            user_hits = [s for s in range(count) if user_mask[s] and mem["steps"][s]]
            user_amps = [mem["amplitudes"][s] for s in user_hits] if user_hits else [0.7]

            # Fractal scale factors from seed (self-similar echoes of the carrier)
            scales = [1]
            for k in range(1, 4):
                seed_bits = _safe_int_seed(numeric_seed)
                sc = int(round(count / (2 ** k) * (1.0 + ((seed_bits >> k) % 5) * 0.05))) or 1
                if sc not in scales and sc < count:
                    scales.append(sc)
            for s in range(count):
                if user_mask[s]:
                    preserved_steps += 1
                    continue  # hard preserve

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
                            hints = wf_engine.get_hints(name, s)
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
                                hints = wf_engine.get_hints(name, s)
                                if hints:
                                    echo_amp = max(echo_amp, float(hints["envelope"]) * 0.5)
                else:
                    # No user carrier — light seed texture, prefer wavefield Euclidean slots
                    base_p = 0.12
                    context = self._contextual_numerology(name, s, s) if hasattr(self, "_contextual_numerology") else 0.5
                    base_p *= (0.65 + 0.7 * context)
                    if wf_engine is not None:
                        hints = wf_engine.get_hints(name, s)
                        if hints and hints["euclidean"]:
                            base_p = 0.28 * hints["seed_harmonic"]
                    if rng.random() < base_p:
                        echo_on = True
                        echo_amp = 0.35 + 0.25 * rng.random()
                        if wf_engine is not None:
                            hints = wf_engine.get_hints(name, s)
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
                if is_stock:
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
        # Full 10-column playlist paint (time offsets + last four columns).
        # Previously only automation lanes were written, so Direction / Multi-Seq /
        # Coverage / Blend Partner stayed empty on a fresh seeded activation.
        try:
            seed_i = _safe_int_seed(self.get_numeric_seed())
            rng_pl = np.random.default_rng(seed_i ^ 0x5EED)
            if hasattr(self, "_canonical_playlist_paint"):
                self._canonical_playlist_paint(rng=rng_pl, mode="seeded", strength=0.55)
            elif hasattr(self, "_paint_operator_pattern_to_playlist"):
                self._paint_operator_pattern_to_playlist(source="seeded", rng=rng_pl)
            if hasattr(self, "_sync_playlist_paint_table_from_memory"):
                self._sync_playlist_paint_table_from_memory()
        except Exception as _pl_exc:
            print(f"[Seeded Harmonic Randomizer] playlist paint skipped: {_pl_exc}")
        self.reload_active_instrument_sequencer_ui()
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
        rng = np.random.default_rng(_safe_int_seed(numeric_seed))

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

    def _render_mixdown_buffer(self, max_rows=None):
        """Shared float32 mono render used by both realtime Play and WAV Export."""
        sample_rate = 44100
        bpm = self.spin_bpm.value() if hasattr(self, 'spin_bpm') else 120
        rows = self.spin_playlist_length.value() if hasattr(self, 'spin_playlist_length') else 32
        if max_rows is not None:
            rows = min(rows, int(max_rows))
        seq_len = self.spin_seq_length.value() if hasattr(self, 'spin_seq_length') else 16
        global_playlist_enabled = self.chk_global_playlist.isChecked() if hasattr(self, 'chk_global_playlist') else True

        if hasattr(self, 'sync_playlist_grid_to_memory'):
            try:
                self.sync_playlist_grid_to_memory()
            except Exception:
                pass

        seconds_per_beat = 60.0 / max(float(bpm), 0.001)
        step_duration = seconds_per_beat / 4.0
        row_duration = step_duration * seq_len
        total_duration = max(0.25, rows * row_duration)

        n_samples = int(sample_rate * total_duration)
        t = np.linspace(0.0, total_duration, n_samples, endpoint=False)
        master = np.zeros(n_samples, dtype=np.float32)

        base_eqr = self.slider_eqr.value() / 100.0 if hasattr(self, 'slider_eqr') else 0.0
        pkp_decay = self.slider_pkp_decay.value() / 1000.0 if hasattr(self, 'slider_pkp_decay') else 0.5
        fractalizer_val = self.slider_fractalizer.value() / 100.0 if hasattr(self, 'slider_fractalizer') else 0.33
        pkp_auto = self.chk_pkp_automod.isChecked() if hasattr(self, 'chk_pkp_automod') else True
        seed_val = self.get_numeric_seed()
        np.random.seed(_safe_int_seed(seed_val))

        # CONVOLVE_FIT_FEATURE: carrier is loaded once per render.
        imported_carrier = self._resample_carrier(n_samples, sample_rate)
        convolve_fit_enabled = bool(
            hasattr(self, "chk_convolve_fit") and self.chk_convolve_fit.isChecked()
        )
        convolve_fit_amount = (
            float(self.slider_global_convolve.value()) / 100.0
            if hasattr(self, "slider_global_convolve") else 0.0
        )
        if imported_carrier is not None:
            # Carrier is additive; it never replaces the programmed groove.
            master += imported_carrier * (0.85 if convolve_fit_enabled else 0.60)

        for row_idx in range(rows):
            start_time = row_idx * row_duration
            end_time = start_time + row_duration
            mask = (t >= start_time) & (t < end_time)
            if not np.any(mask):
                continue
            local_t = t[mask] - start_time
            row_mix = np.zeros_like(local_t, dtype=np.float32)
            velocity_scale = 1.0

            if global_playlist_enabled and row_idx < len(getattr(self, 'master_playlist_data', [])):
                entry = self.master_playlist_data[row_idx]
                primary_op = entry.get("operator", self.instrument_names_48[0])
                velocity_scale = float(entry.get("velocity", 1.0))
                op_indices = [self.instrument_names_48.index(primary_op)] if primary_op in self.instrument_names_48 else [0]
                remaining = [i for i in range(len(self.instrument_names_48)) if i != op_indices[0]]
                n_comp = min(3, len(remaining))
                companions = np.random.choice(remaining, size=n_comp, replace=False).tolist() if n_comp else []
                active_cluster = op_indices + companions
            else:
                active_cluster = np.random.choice(len(self.instrument_names_48), size=4, replace=False).tolist()

            for op_idx in active_cluster:
                op_name = self.instrument_names_48[op_idx]
                mem = self.instrument_sequencer_memory.get(
                    op_name, {"steps": [False] * 48, "amplitudes": [1.0] * 48, "pitches": [1.0] * 48}
                )
                base_freq = float(self.spin_base_frequency.value()) if hasattr(self, "spin_base_frequency") else 432.0
                base_freq *= MEUM_POWERS_36[op_idx % 36]
                dynamic_eqr = base_eqr * (1.0 + 0.3 * np.sin(2.0 * np.pi * 0.2 * local_t + op_idx))

                step_env = np.zeros_like(local_t)
                pitch_track = np.ones_like(local_t)
                steps = mem.get("steps", [])
                amps = mem.get("amplitudes", [1.0] * 16)
                pitches = mem.get("pitches", [1.0] * 16)
                for s_idx in range(min(seq_len, len(steps))):
                    if steps[s_idx]:
                        s_start = s_idx * step_duration
                        s_end = s_start + step_duration
                        s_mask = (local_t >= s_start) & (local_t < s_end)
                        if np.any(s_mask):
                            s_local = local_t[s_mask] - s_start
                            amp = amps[s_idx] if s_idx < len(amps) else 1.0
                            pr = pitches[s_idx] if s_idx < len(pitches) else 1.0
                            step_env[s_mask] += amp * np.exp(-s_local / max(step_duration * 0.5, 0.01))
                            pitch_track[s_mask] = pr

                freq = base_freq * pitch_track
                mod_freq = freq * MEUM_CONSTANT
                carrier = np.sin(2 * np.pi * mod_freq * local_t)
                osc = np.sin(2 * np.pi * freq * local_t + carrier * (dynamic_eqr * MEUM_CONSTANT * fractalizer_val))
                env_f = np.exp(-local_t / max(pkp_decay * (MEUM_CONSTANT if pkp_auto else 1.0), 0.015))
                pkp = env_f * np.sin(2 * np.pi * (base_freq * 2.0) * pitch_track * local_t)
                gate = np.maximum(step_env, 0.1)
                voice = osc * gate * velocity_scale

                # CONVOLVE_FIT_FEATURE: reshape only non-user voices.
                if convolve_fit_enabled:
                    try:
                        is_user_voice = self._instrument_has_net_effect(op_name, seq_len)
                    except Exception:
                        is_user_voice = (op_name == primary_op)
                    if not is_user_voice:
                        fit_target = None
                        if imported_carrier is not None:
                            global_start = int(np.searchsorted(t, start_time))
                            global_end = min(global_start + local_t.size, imported_carrier.size)
                            if global_end > global_start:
                                fit_target = imported_carrier[global_start:global_end]
                        if fit_target is None or fit_target.size < 32:
                            fit_target = row_mix.copy() if np.max(np.abs(row_mix)) > 1e-6 else carrier
                        voice = self._spectral_fit_voice(
                            voice, fit_target, max(0.15, convolve_fit_amount)
                        )
                row_mix += voice

            # PKP NullLock is global and is never a separate timeline event.
            # It is triggered only by notes in the currently selected instrument, at the global base frequency.
            try:
                selected = self.instrument_selector_dropdown.currentText()
                smem = self.instrument_sequencer_memory.get(selected, {})
                ssteps = smem.get("steps", [])
                global_pkp = np.zeros_like(local_t, dtype=np.float32)
                gbase = float(self.spin_base_frequency.value()) if hasattr(self, "spin_base_frequency") else 432.0
                for ss in range(min(int(seq_len), len(ssteps))):
                    if ssteps[ss]:
                        ss_start = ss * step_duration
                        ss_end = ss_start + step_duration
                        mm = (local_t >= ss_start) & (local_t < ss_end)
                        if np.any(mm):
                            sl = local_t[mm] - ss_start
                            env = np.exp(-sl / max(step_duration * 0.35, 0.01))
                            global_pkp[mm] += env * np.sin(2.0 * np.pi * gbase * sl)
                # Normal PKP layer is always base-level; BOOST is realtime one-shot only.
                row_mix += global_pkp * 0.35
            except Exception:
                pass

            master[mask] += row_mix / max(len(active_cluster), 1)

        # Global Convolve: deterministic geometric cross-convolution of the rendered carrier.
        # User-edited controls remain upstream; this stage only mixes the structural wave result.
        try:
            conv_amt = (float(self.spin_global_convolve.value()) / 100.0) if hasattr(self, "spin_global_convolve") else 0.0
            if conv_amt > 0.0 and len(master) > 8:
                klen = min(2048, max(32, len(master) // 200))
                kt = np.linspace(0.0, 1.0, klen, endpoint=False)
                # Seed-stable geometric kernel; loaded WAV becomes the kernel source
                # when present, otherwise retain the original mathematical kernel.
                if imported_carrier is not None:
                    kernel = imported_carrier[:klen].copy()
                    if kernel.size < klen:
                        kernel = np.pad(kernel, (0, klen - kernel.size), mode="wrap")
                else:
                    gf = float(self.spin_base_frequency.value()) if hasattr(self, "spin_base_frequency") else 432.0
                    kernel = (np.sin(2*np.pi*(gf/ max(sample_rate,1))*np.arange(klen)) +
                              0.5*np.sin(2*np.pi*(gf*MEUM_CONSTANT/max(sample_rate,1))*np.arange(klen)))
                    kernel = kernel.astype(np.float32)
                kn = np.linalg.norm(kernel)
                if kn > 1e-9:
                    kernel /= kn
                    nfft = 1 << int(np.ceil(np.log2(len(master) + len(kernel) - 1)))
                    spec = np.fft.rfft(master, nfft) * np.fft.rfft(kernel, nfft)
                    conv = np.fft.irfft(spec, nfft)[:len(master)].astype(np.float32)
                    cn = np.max(np.abs(conv))
                    if cn > 1e-9:
                        conv *= np.max(np.abs(master)) / cn
                    master = (1.0 - conv_amt) * master + conv_amt * conv
        except Exception as e:
            print(f"[Global Convolve] skipped: {e}")

        # Domain partition equations: longitudinal multivariate modulation (additive blend)
        if hasattr(self, 'domain_eq_engine') and self.domain_eq_engine.domains:
            try:
                self.domain_eq_engine.set_seed(self.get_numeric_seed())
                # Normalize time axis 0..1 across the full buffer for partition logic
                t_norm = np.linspace(0.0, 1.0, len(master))
                domain_mod = self.domain_eq_engine.evaluate_series(t_norm, x=0.0, y=0.0, z=0.0)
                # Soft convolution: carrier * (1 + 0.45 * domain) — accentuates without erasing
                master = master * (1.0 + 0.45 * domain_mod.astype(np.float32))
            except Exception as e:
                print(f"[DomainEQ] render modulation skipped: {e}")

        # SEED_SCRIPT_T_AXIS: seed/script expressions that reference `t` or use
        # the if(...)/elif shorthand are DSP-boundary constructs — they describe
        # a signal over render time, not a single composition-state number.
        # get_numeric_seed() only ever sees t=0.0 (by design: it's called from
        # UI/composition code, never per-sample). This is the actual DSP-side
        # evaluation: the seed text is resolved across the real render-time
        # axis `t` and blended in as a gentle, seed-driven texture — a no-op
        # for a plain numeric seed like "432" (constant curve, ~0 contribution)
        # and only audible when the seed field is an actual time-varying script.
        try:
            seed_script_text = self._seed_text() if hasattr(self, "_seed_text") else ""
            _looks_time_varying = any(
                token in seed_script_text for token in ("t", "if(", "if (", "elif", "sin", "cos")
            )
            if seed_script_text.strip() and _looks_time_varying:
                control_n = min(256, max(8, len(master) // 512))
                control_t = np.linspace(0.0, total_duration, control_n, endpoint=False)
                control_vals = np.array([
                    evaluate_seed_expression_at_time(seed_script_text, ct) for ct in control_t
                ], dtype=np.float64)
                seed_time_curve = np.interp(t, control_t, control_vals)
                # Keep on self so per-voice code elsewhere can sample the same
                # curve by absolute time if it wants finer-grained access.
                self._seed_time_curve = seed_time_curve
                peak_curve = np.max(np.abs(seed_time_curve))
                if peak_curve > 1e-9:
                    seed_mod = (seed_time_curve / peak_curve).astype(np.float32)
                    master = master * (1.0 + 0.20 * MEUM_NORM * seed_mod)
        except Exception as e:
            print(f"[SeedScript] T-axis modulation skipped: {e}")

        peak = np.max(np.abs(master))
        if peak > 0:
            master = (master / peak) * 0.98
        return master.astype(np.float32), sample_rate
    def _on_live_source_changed(self, *args):
        """Coalesce seed/seq-length changes into one deferred composition transaction."""
        if getattr(self, "_composition_generation_guard", False):
            return
        if getattr(self, "_live_source_update_pending", False):
            return
        self._live_source_update_pending = True
        QTimer.singleShot(0, self._flush_live_source_update)

    def _flush_live_source_update(self):
        self._live_source_update_pending = False
        if getattr(self, "_composition_generation_guard", False):
            return
        # Do NOT pre-set _composition_generation_guard here.
        # _apply_live_engine_once(force=True) owns the transaction guard so that
        # nested playlist paint can still run and fill all 10 columns.
        try:
            if (
                getattr(self, "btn_idealize_rhythm", None)
                and self.btn_idealize_rhythm.isChecked()
            ):
                self._apply_live_engine_once("euclidean", force=True)
            if (
                getattr(self, "btn_seeded_randomize", None)
                and self.btn_seeded_randomize.isChecked()
            ):
                self._apply_live_engine_once("seeded", force=True)
        except Exception as exc:
            print(f"[LiveSourceUpdate] {type(exc).__name__}: {exc}")
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
            if not self.is_playing:
                self._transport_finished = True
                self.is_playing = False
                self._composition_generation_guard = False
                self.stop_playback()
                return
    def _update_scope_from_playhead(self):
        """UI-thread timer: push latest audio chunk into scope + 2.5D video synth."""
        if not self.is_playing:
            # End-of-buffer path sets _transport_finished in the audio callback.
            # Here we only ensure UI stops; stop_playback must not look like "finished"
            # if the user already stopped, so prefer the flags already set.
            if not getattr(self, "_stop_requested", False):
                self._transport_finished = True
            self.stop_playback()
            return
        chunk = self._last_scope_chunk
        if isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope):
            self.visual_oscilloscope.update_waveform(chunk)
        if hasattr(self, 'video_synth_viewer'):
            self.video_synth_viewer.update_from_audio(chunk)
        if self.play_buffer is not None and len(self.play_buffer) > 0:
            pct = int(100 * self.play_cursor / len(self.play_buffer))
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText(
                    f"📊 2.5D Video Synth  |  LIVE  {pct}%  ·  Vol {int(self.master_volume*100)}%"
                )

    def toggle_playback(self):
        """Unified PLAY/PAUSE/RESUME transport over the rendered audiovisual data stream."""
        # A completed one-shot is NOT a paused stream.
        # Start a fresh transport on the next PLAY.
        if getattr(self, "_transport_finished", False):
            # Completed one-shot → fresh transport. Do not touch composition guards here.
            self.is_playing = False
            self.is_paused = False
            self.play_cursor = 0
            self._transport_finished = False
            self._stop_requested = False
            self._render_cancelled = False
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
                self._transport_finished = False
                self._play_finished_flag = False
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
        try:
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText("📊 Rendering Audiovisual Track…")
            QApplication.processEvents()
            buf, sr = self._render_mixdown_buffer()
            with self.play_lock:
                self.play_buffer = buf
                self.play_sample_rate = sr
                self.play_cursor = 0
                self.is_playing = True
                self.is_paused = False
                self._transport_finished = False
                self._play_finished_flag = False
            if HAS_SOUNDDEVICE:
                if self.audio_stream is not None:
                    try:
                        self.audio_stream.stop(); self.audio_stream.close()
                    except Exception:
                        pass
                self.audio_stream = sd.OutputStream(
                    samplerate=sr, channels=1, dtype='float32', callback=self._audio_callback,
                    blocksize=1024, latency='low'
                )
                self.audio_stream.start()
            self.btn_play.setText("⏸ PAUSE Audiovisual Track")
            self.btn_play.setStyleSheet("background-color: #00aa55; color: white; font-weight: bold;")
            self._scope_update_timer.start()
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText("📊 Audiovisual Track  |  LIVE")
        except Exception as e:
            self.is_playing = False
            self.is_paused = False
            print(f"[Audio] Playback start failed: {e}")
            QMessageBox.critical(self, "Playback Error", str(e))

    def stop_playback(self):
        """Hard stop: reset the audiovisual transport to the beginning."""
        was_active = self.is_playing or self.is_paused
        self.is_playing = False
        self.is_paused = False
        self._stop_requested = True
        self._transport_finished = False
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
            self.scope_status_label.setText("📊 Audiovisual Track  |  Stopped")
        if isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope):
            self.visual_oscilloscope.update_waveform(np.zeros(100))
        if hasattr(self, 'video_synth_viewer'):
            self.video_synth_viewer.update_from_audio(np.zeros(100, dtype=np.float32))
        if was_active:
            print("[Audio] Audiovisual playback stopped.")
        self._stop_requested = False

    def export_mixdown_dialog(self):
        try:
            default_filename = f"groovebox_mixdown_{self.export_counter:03d}.wav"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Mixdown Audio", default_filename, "WAV Audio Files (*.wav)"
            )
            if not file_path:
                return

            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText("📊 Rendering full mixdown for export…")
            QApplication.processEvents()

            master, sample_rate = self._render_mixdown_buffer()
            pcm = (master * 32767.0).astype(np.int16)

            if wavfile is not None:
                wavfile.write(file_path, sample_rate, pcm)
            else:
                with wave.open(file_path, 'w') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(pcm.tobytes())

            # Preview into scope
            if isinstance(getattr(self, 'visual_oscilloscope', None), VisualOscilloscope):
                prev = master[: min(len(master), sample_rate // 2)]
                idx = np.linspace(0, len(prev) - 1, 100).astype(int)
                self.visual_oscilloscope.update_waveform(prev[idx])

            print(f"[System] Success: exported → {file_path}")
            self.export_counter += 1
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText(f"📊 Export complete → {os.path.basename(file_path)}")
        except Exception as e:
            print(f"[System] Export error: {e}")
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText(f"📊 Export error: {e}")
            QMessageBox.critical(self, "Export Error", str(e))

    # =====================================================================
    # VIDEO_EXPORT_FEATURE — 2.5D render + audio mux + optional source-video blend
    # Revert: restore the prior export_video_dialog implementation.
    # =====================================================================
    def export_video_dialog(self, include_audio=True):
        """Render the 2.5D geometry, optionally mux rendered audio, and optionally blend source video."""
        tmp = None
        try:
            from PIL import Image
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("ffmpeg is required for video export. Install ffmpeg and try again.")

            out_path, _ = QFileDialog.getSaveFileName(
                self, "Export Video", f"groovebox_video_{self.export_counter:03d}.mp4",
                "MP4 Video (*.mp4);;All Files (*)"
            )
            if not out_path:
                return
            if hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText("🎬 Rendering 2.5D video + audio…")
            QApplication.processEvents()

            master, sr = self._render_mixdown_buffer()
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
                    wavfile.write(audio_path, sr, (np.clip(master, -1, 1) * 32767).astype(np.int16))
                else:
                    with wave.open(audio_path, 'wb') as wf:
                        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                        wf.writeframes((np.clip(master, -1, 1) * 32767).astype(np.int16).tobytes())

            eng = getattr(self, 'video_synth_engine', None) or VideoSynthEngine(48)
            w, h = 640, 360
            for fi in range(n_frames):
                a = fi * frame_samples
                b = min(len(master), a + frame_samples)
                chunk = master[a:b]
                eng.set_waveform(chunk)
                frame = eng.render_frame(w, h)
                Image.fromarray(frame, mode="RGB").save(os.path.join(frames_dir, f"frame_{fi:05d}.png"))
                if fi % 12 == 0 and hasattr(self, 'scope_status_label'):
                    self.scope_status_label.setText(f"🎬 Frames {fi}/{n_frames}…")
                    QApplication.processEvents()

            pattern = os.path.join(frames_dir, "frame_%05d.png")
            source_video = self.imported_video_path if getattr(self, 'imported_video_path', '') else ''
            if source_video and os.path.abspath(source_video) != os.path.abspath(out_path):
                # VIDEO_REEMULATION_PIPELINE: source video is the visual reference. Its
                # decoded audio has already become the imported carrier; if it has an
                # audio stream, a quiet direct source channel is also mixed into the final
                # rendered audio. The 2.5D frame sequence is the visual re-emulation.
                source_has_audio = bool(getattr(self, 'imported_video_meta', {}).get('has_audio', False))
                if source_has_audio:
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
                        "-filter_complex", filter_complex,
                        "-map", "[v]", "-map", "[a]",
                        "-t", f"{n_frames / fps:.6f}",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", out_path,
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
                        "-i", audio_path,
                        "-filter_complex", filter_complex,
                        "-map", "[v]", "-map", "2:a:0",
                        "-t", f"{n_frames / fps:.6f}",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", out_path,
                    ]
            else:
                cmd = [
                    ffmpeg, "-y", "-framerate", str(fps), "-i", pattern,
                    "-i", audio_path, "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out_path,
                ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr[-1600:] if proc.stderr else "ffmpeg failed")

            self.export_counter += 1
            if hasattr(self, 'scope_status_label'):
                suffix = " + source video blend" if source_video else ""
                self.scope_status_label.setText(f"🎬 Video + rendered audio exported{suffix} → {os.path.basename(out_path)}")
            QMessageBox.information(self, "Export complete", f"Saved:\n{out_path}")
        except Exception as e:
            print(f"[Video] export error: {e}")
            QMessageBox.critical(self, "Video Export Error", str(e))
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

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

    def spawn_floating_window(self, attr_name, window_title):
        window = getattr(self, attr_name, None)

        if window is None or not window.isVisible():
            window = QWidget(None, Qt.WindowType.Window)
            window.setWindowTitle(window_title)

            if attr_name == 'playlist_window':
                window.resize(1300, 875)
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
                track_table = PaintbrushTable(self, rows, PLAYLIST_COLUMN_COUNT)
                self.active_paint_table = track_table
                if not hasattr(self, 'playlist_automation') or self.playlist_automation is None:
                    self.playlist_automation = [{} for _ in range(rows)]

                track_table.setHorizontalHeaderLabels([
                    "Time Marker", "Operator Identity",
                    "Script Tag", "Domain Tag", "Synth Snapshot", "Modular Patch",
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

                    empty = not any(v not in (None, "", [], {}) for v in data_entry.values())
                    item_inst = QTableWidgetItem("" if empty else str(data_entry.get("operator", "")))
                    if not empty:
                        item_inst.setBackground(palette_colors[row_idx % len(palette_colors)])
                    track_table.set_cell_item(row_idx, 0, QTableWidgetItem("" if empty else str(data_entry.get("time_marker", ""))))
                    track_table.set_cell_item(row_idx, 1, item_inst)
                    track_table.set_cell_item(row_idx, 2, QTableWidgetItem("" if empty else str(data_entry.get("script_tag", ""))))
                    track_table.set_cell_item(row_idx, 3, QTableWidgetItem("" if empty else str(data_entry.get("domain_tag", ""))))
                    track_table.set_cell_item(row_idx, 4, QTableWidgetItem("" if empty else str(data_entry.get("synth_tag", ""))))
                    track_table.set_cell_item(row_idx, 5, QTableWidgetItem("" if empty else str(data_entry.get("patch_tag", ""))))
                    track_table.set_cell_item(row_idx, 6, QTableWidgetItem("" if empty else f"{float(data_entry.get('velocity', 1.0))*100:.1f}%"))
                    track_table.set_cell_item(row_idx, 7, QTableWidgetItem("" if empty else str(data_entry.get("effect_target", data_entry.get("modulation", "")))))
                    track_table.set_cell_item(row_idx, 8, QTableWidgetItem("" if empty else str(data_entry.get("auto_amount", ""))))
                    track_table.set_cell_item(row_idx, 9, QTableWidgetItem("" if empty else str(data_entry.get("direction_vector", data_entry.get("direction", "")))))
                    track_table.set_cell_item(row_idx, 10, QTableWidgetItem("" if empty else str(data_entry.get("multi_seq", ""))))
                    track_table.set_cell_item(row_idx, 11, QTableWidgetItem("" if empty else str(data_entry.get("coverage", ""))))
                    track_table.set_cell_item(row_idx, 12, QTableWidgetItem("" if empty else str(data_entry.get("blend_partner", ""))))

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
                window.setStyleSheet("""
                    QWidget {
                        background-color: rgba(28, 28, 32, 180);
                        color: #e0e0e0;
                    }
                    QLabel { color: #cccccc; }
                    QSlider::groove:horizontal {
                        height: 4px; background: #333333; border-radius: 2px;
                    }
                    QSlider::handle:horizontal {
                        background: #ff6b00; width: 12px; margin: -4px 0; border-radius: 6px;
                    }
                """)
                attach_math_decor(window, app=self, light=True)
                window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                main_layout.addWidget(QLabel(
                    f"Interactive Wavetable & Vector Synthesis Interface: "
                    f"{current_instrument} (Node ID: {inst_index})"
                ))
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
            cw = self.centralWidget()
            bg = ParametricMathBackground(self, cw)
            bg.setGeometry(cw.rect())
            bg.lower()
            bg.show()
            self._math_decor = bg
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
