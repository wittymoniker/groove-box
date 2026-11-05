"""GROOVEBOX_R23R_MULTIDIM_UI_20261103 — 🌀 Multidimensional synth window.

Deformable geodesic sphere mesh driven by CA state + wavetable amplitudes.
Mouse velocity inertia, scroll = yaw, proximity scaling (1.333× <100 px,
0.75× >300 px), arc-curved slider layout, near-transparent MainMDPanel bg,
animated ghost "Synths Master Engine" label, bezier wires to edit buttons,
and a full SynthsMasterPanel with live 2D graphs.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np
from qt_painting import owned_painter
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, QRect, QLineF, QSize
from PyQt6.QtGui import (QColor, QPainter, QPen, QBrush, QPolygon, QPolygonF, QRadialGradient,
                          QLinearGradient, QFont, QPainterPath, QRegion)
from PyQt6.QtWidgets import (
    QPlainTextEdit,QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                              QComboBox, QLineEdit, QSpinBox, QSlider, QLabel, QPushButton,
                              QScrollArea, QSplitter, QGroupBox, QTabWidget, QCheckBox,
                              QDoubleSpinBox, QFrame, QSizePolicy, QLayout, QLayoutItem,
                              QWidgetItem, QSpacerItem, QDial, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QProgressBar)
from PyQt6.QtGui import QStandardItemModel, QStandardItem

try:
    from PyQt6 import sip as _sip
except Exception:  # pragma: no cover - PyQt6 always provides sip in supported builds
    try:
        import sip as _sip  # type: ignore
    except Exception:
        _sip = None


def _alive(obj) -> bool:
    """True when a Python wrapper still points at a live C++ object."""
    if obj is None:
        return False
    if _sip is not None:
        try:
            return not _sip.isdeleted(obj)
        except Exception:
            pass
    try:
        obj.objectName()
        return True
    except RuntimeError:
        return False
    except Exception:
        return True


try:
    from ot_symbol_notation import Role as _OTRole, ROLE_COLORS as _OT_ROLE_COLORS
except Exception:  # keep the multidim view usable in isolation
    _OTRole = None
    _OT_ROLE_COLORS = {
        "independent_variable": "#ff4d4d",
        "independent_constant": "#30d158",
        "result": "#5ac8fa",
        "dependent_constant": "#1c1c1e",
        "dependent_variable": "#f2f2f7",
    }

_ROLE_ORDER = [
    "independent_variable",
    "independent_constant",
    "result",
    "dependent_variable",
    "dependent_constant",
]

_ROLE_FOR_PARAM = {
    "gravity": "independent_constant",
    "restitution": "dependent_variable",
    "rot_hz": "independent_variable",
    "lo": "independent_constant",
    "hi": "independent_constant",
    "up": "result",
    "down": "result",
    "phase_shift": "dependent_variable",
    "block_ms": "dependent_constant",
    "res_q": "result",
    "res_mix": "dependent_variable",
}


def _role_color(role) -> QColor:
    key = getattr(role, "value", role)
    if _OTRole is not None:
        try:
            key = _OTRole(str(key))
        except Exception:
            pass
    return QColor(_OT_ROLE_COLORS.get(key, _OT_ROLE_COLORS.get(str(getattr(key, "value", key)), "#5ac8fa")))


def _rescale_pt(base: QColor, pt: float) -> QColor:
    """Rescale a project role color by a normalized slider point (0..1)."""
    try:
        pt = max(0.0, min(1.0, float(pt)))
    except Exception:
        pt = 0.5
    h, s, v, a = base.getHsv()
    v = int(max(95, min(255, 95 + 160 * pt)))
    if s < 60:
        s = int(max(0, min(255, 0.5 * s + 15 * pt)))
    else:
        s = int(max(70, min(255, 0.55 * s + 0.45 * (120 + 135 * pt))))
    return QColor.fromHsv(h, s, v, a)


def _style_role_slider(slider, base, value, lo, hi):
    try:
        t = (float(value) - lo) / max(1.0, float(hi - lo))
        c = _rescale_pt(base, t)
        light = c.lighter(160)
        dark = c.darker(260)
        slider.setStyleSheet(
            "QSlider::groove:horizontal { background:#1a2230; height:5px; border-radius:2px; }"
            f"QSlider::sub-page:horizontal {{ background:{c.name()}; border-radius:2px; }}"
            f"QSlider::handle:horizontal {{ background:{light.name()}; border:1px solid {dark.name()};"
            " width:12px; margin:-4px 0; border-radius:6px; }"
        )
    except Exception:
        pass


def _mirror_multidim_user(host, name):
    """Keep the authored MD dict inside the canonical macro user store.

    Canonical reconciliation drops param keys it cannot find in the pristine
    user store, which would otherwise erase every MD slider value as soon as
    the live debounce commits.
    """
    try:
        ps = getattr(host, "instrument_param_state", None)
        if not isinstance(ps, dict):
            return
        u = (ps.get(name) or {}).get("multidim")
        if not isinstance(u, dict):
            return
        store = getattr(host, "_canonical_macro_user_store", None)
        if not isinstance(store, dict):
            store = host._canonical_macro_user_store = {}
        rec = store.setdefault(name, {})
        if isinstance(rec, dict):
            rec["multidim"] = dict(u)
    except Exception:
        pass


def _bind_role_slider(slider, role, lo=None, hi=None):
    base = _role_color(role)
    if lo is None:
        lo = slider.minimum()
    if hi is None:
        hi = slider.maximum()
    _style_role_slider(slider, base, slider.value(), lo, hi)
    slider.valueChanged.connect(
        lambda v, b=base, l=lo, h=hi, s=slider: _style_role_slider(s, b, v, l, h)
    )
    return base


import multidim_synth as md

NUM_CONTROLS = (  # key, label, lo, hi, scale (slider int → value)
    ("gravity",     "Ball gravity",       0, 400, 0.1),
    ("restitution", "Ball restitution",   0,  99, 0.01),
    ("rot_hz",      "Vector rotation Hz", 0, 200, 0.005),
    ("lo",          "Quiet threshold",    0, 100, 0.01),
    ("hi",          "Loud threshold",     0, 100, 0.01),
    ("up",          "Loud → freq ×",     50, 400, 0.01),
    ("down",        "Quiet → freq ×",    10, 200, 0.01),
    ("phase_shift", "Phase turn (rad)",   0, 628, 0.01),
    ("block_ms",    "Block ms",           2, 200, 1.0),
    ("res_q",       "Resonator Q",        1, 200, 1.0),
    ("res_mix",     "Resonator mix",      0, 100, 0.01),
)

MD_FIELD_CONTROLS = (  # bottom stochastic / lock / fractal field controls
    ("stochastic",       "Stochastic field",   0, 100, 0.01),
    ("variation",        "Stochastic drift",   0, 100, 0.01),
    ("fractal_depth",    "Fractal depth",      0, 100, 0.01),
    ("lock_ms",          "Trigger lock ms",    0, 2000, 1.0),
    ("trigger_response", "Trigger response",   0, 100, 0.01),
    ("field_rate",       "Field evolution",    0, 100, 0.01),
)

MD_CLONE_TARGETS = (("panel", "PANEL"), ("geometric", "GEOMETRIC"), ("multidim", "MULTIDIM"))
MD_CLONE_SOURCES = ("Off", "Panel", "Geometric", "Multidim")


def _md_clone_defaults():
    # Minimal canonical macro set (the five visible Synth Rack generators) plus
    # local mix / EQ / sidechain. Every clone is fully determined by these keys
    # so randomizers, profiles, and playlist cells can drive them deterministically.
    return {
        "enabled": False,
        "volume": 1.0,
        "low_db": 0.0, "mid_db": 0.0, "high_db": 0.0,
        "source": "Off", "depth": 0.0,
        "attack_ms": 8.0, "release_ms": 120.0,
        # Five generator macros (canonical_macro_defaults / Synth Rack)
        "morph": 0.75,
        "harmonic_freq": 432.0,
        "chaos": 0.0,
        "fold_depth": 1.0,
        "harmonic_lattice": 0.35,
    }

# ---------------------------------------------------------------------------
# Meum Phyllotaxis Sphere  (replaces UV grid)
#
# Meum ≈ 1.1975807343… is the unique root in (1,2) of  2^M = M^4 + M^2 − M.
# The Meum angle  2π·M⁻¹ ≈ 300.5°  spaces successive points on the sphere
# the same way the golden angle (≈ 137.5°) does in sunflower/pine-cone
# phyllotaxis — but with Meum's irrational character, so adjacent spirals
# carry a different winding number.
#
# Point k (k = 0…N-1):
#   latitude  θ_k = arccos(1 − 2k/(N−1))          uniform cosine-spaced
#   longitude φ_k = k · 2π · M⁻¹  (mod 2π)         Meum phyllotaxis
#   x = sin θ · cos φ,  y = cos θ,  z = sin θ · sin φ
#
# Edges: spiral path (k → k+1) plus two "skip" links (k → k+⌈M⌉) and
# (k → k+⌈M²⌉) that form the two visible families of Meum spirals.
# ---------------------------------------------------------------------------

try:
    from meum_constants import MEUM as _M, MEUM_INV as _M_INV, MEUM_SQ as _M_SQ
except Exception:
    _M     = 1.1975807343385265
    _M_INV = 0.8350381703  # 1/M
    _M_SQ  = 1.4342003397  # M²

_MEUM_ANGLE = math.tau * _M_INV          # ≈ 5.248 rad ≈ 300.5°
_SPHERE_N   = 220                        # total lattice points
_SPHERE_K1  = int(round(_M))            # 1  — nearest spiral family
_SPHERE_K2  = int(round(_M_SQ))         # 1  — second spiral family (use M²≈1.43→2)
# recompute as the two Meum-convergent skip distances
_SPHERE_K1  = max(1, int(round(_M)))          # 1
_SPHERE_K2  = max(2, int(round(_M_SQ)))       # 1 → use 2 for visible spirals
_SPHERE_K3  = max(3, int(round(_M_SQ * _M)))  # M³ ≈ 1.717 → 2, pick 3

_sphere_base: "np.ndarray | None" = None


def _make_sphere_base() -> "np.ndarray":
    """Meum phyllotaxis point distribution on the unit sphere."""
    global _sphere_base
    if _sphere_base is not None:
        return _sphere_base
    N = _SPHERE_N
    pts = []
    for k in range(N):
        # cosine-uniform latitude (avoids pole bunching)
        cos_th = 1.0 - 2.0 * k / max(1, N - 1)
        sin_th = math.sqrt(max(0.0, 1.0 - cos_th * cos_th))
        phi    = (k * _MEUM_ANGLE) % math.tau
        pts.append([sin_th * math.cos(phi), cos_th, sin_th * math.sin(phi)])
    _sphere_base = np.array(pts, dtype=np.float64)
    return _sphere_base


# Keep legacy name so callers that reference _SPHERE_U/_SPHERE_V still compile.
_SPHERE_U, _SPHERE_V = _SPHERE_N, 1


def _sphere_displaced(amps_n: "np.ndarray", ca_row: "np.ndarray", ball_h: float,
                      vec: "np.ndarray", t: float) -> "np.ndarray":
    base = _make_sphere_base().copy()
    N    = _SPHERE_N
    vnorm = vec / (float(np.linalg.norm(vec)) + 1e-9)
    for k in range(N):
        amp    = float(amps_n[k % len(amps_n)]) if len(amps_n) else 0.0
        gate   = float(ca_row[k % len(ca_row)]) if len(ca_row) else 1.0
        # Meum-weighted squeeze: ball height modulates each layer by M^(k/N)
        meum_w = (_M ** (k / max(1, N - 1) - 0.5))  # ∈ [M^-0.5, M^0.5]
        squeeze = 0.10 * math.sin(math.pi * ball_h) * meum_w
        v_dot   = float(np.dot(base[k], vnorm))
        # pulsation: phase = k * M⁻¹ so successive points drift irationally
        pulse   = 0.035 * math.sin(t * 1.4 + k * _M_INV)
        disp    = 0.20 * amp * gate + squeeze + 0.07 * v_dot + pulse
        base[k] *= (1.0 + disp)
    return base


def _sphere_edges() -> "list[tuple[int,int]]":
    """Meum spiral edges: consecutive path + two skip families."""
    N   = _SPHERE_N
    sk2 = max(2, int(round(_M_SQ)))
    sk3 = max(3, int(round(_M_SQ * _M)))
    pairs: list = []
    for k in range(N - 1):
        pairs.append((k, k + 1))                           # spiral path
    for k in range(N - sk2):
        pairs.append((k, k + sk2))                         # M² skip
    for k in range(N - sk3):
        pairs.append((k, k + sk3))                         # M³ skip
    return pairs


_SPHERE_EDGES = _sphere_edges()


class MD3DView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        # Slightly closer camera keeps the geodesic sphere legible in the enlarged frame.
        self.yaw = 0.7; self.pitch = 0.45; self.dist = 4.2
        self._drag = None
        self._vel_hist: deque = deque(maxlen=8)   # (time, dx, dy)
        self._inertia = (0.0, 0.0)                # (dyaw, dpitch) per frame
        self.params = md.preset_params("Prism")
        self.seed_int = 0; self.slot = 0
        self.t = 0.0
        self._rebuild()

    def set_params(self, p, seed_int=0, slot=0):
        self.params, self.seed_int, self.slot = p, int(seed_int), int(slot)
        self._rebuild()

    def _rebuild(self):
        p = self.params
        try:
            self.amps = md.table_amplitudes(p.get("script", "1/k"))
        except Exception:
            self.amps = np.zeros(md.H)
        m = float(np.max(np.abs(self.amps))) if self.amps.size else 0.0
        self.amps_n = self.amps / m if m > 0 else self.amps
        cells = np.array([((self.seed_int >> (k % 31)) & 1) ^ ((self.slot + k) % 2)
                          for k in range(md.H)], dtype=np.uint8)
        if not cells.any():
            cells[md.H // 2] = 1
        self.ca = md._ca_rows(p.get("ca_rule", 90), 64, cells)
        self.ball = md._ball(400, 0.02, p.get("gravity", 9.8), p.get("restitution", 0.8))
        ratios = ()
        for part in str(p.get("resonators", "harmonic")).split("+"):
            ratios = ratios + tuple(r for r in md.RESONATOR_RULES.get(part.strip(), ()) if r not in ratios)
        self.res = ratios
        self.update()

    def tick(self, dt):
        self.t += dt
        # apply inertia
        iy, ip = self._inertia
        if abs(iy) > 0.0001 or abs(ip) > 0.0001:
            self.yaw += iy
            self.pitch = max(-1.4, min(1.4, self.pitch + ip))
            self._inertia = (iy * 0.92, ip * 0.92)
        self.update()

    # ---- camera controls
    def mousePressEvent(self, e):
        self._drag = e.position()
        self._vel_hist.clear()
        self._inertia = (0.0, 0.0)
        import time as _t
        self._vel_hist.append((_t.monotonic(), 0.0, 0.0))

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            import time as _t
            d = e.position() - self._drag
            self._drag = e.position()
            dx, dy = float(d.x()), float(d.y())
            # proximity scaling
            cx, cy = self.width() / 2.0, self.height() / 2.0
            dist_px = math.hypot(e.position().x() - cx, e.position().y() - cy)
            if dist_px < 100:
                scale = 1.333
            elif dist_px > 300:
                scale = 0.75
            else:
                t = (dist_px - 100) / 200.0
                scale = 1.333 + (0.75 - 1.333) * t
            self.yaw += dx * 0.01 * scale
            self.pitch = max(-1.4, min(1.4, self.pitch + dy * 0.01 * scale))
            self._vel_hist.append((_t.monotonic(), dx * 0.01 * scale, dy * 0.01 * scale))
            self.update()

    def mouseReleaseEvent(self, _e):
        self._drag = None
        # compute release inertia from velocity history
        if len(self._vel_hist) >= 2:
            dy_sum = dx_sum = 0.0
            for _, dx, dy in self._vel_hist:
                dx_sum += dx; dy_sum += dy
            n = len(self._vel_hist)
            self._inertia = (dx_sum / n, dy_sum / n)
        else:
            self._inertia = (0.0, 0.0)

    def wheelEvent(self, e):
        # Passive: adjust yaw but let scroll propagate so parent can scroll past.
        delta = e.angleDelta().y()
        self.yaw += (delta / 120.0) * 0.06
        self.update()
        e.ignore()  # do NOT consume — parent scroll areas still work

    def _proj(self, P):
        P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        x =  cy * P[:, 0] - sy * P[:, 2]
        z =  sy * P[:, 0] + cy * P[:, 2]
        y =  cp * P[:, 1] - sp * z
        z =  sp * P[:, 1] + cp * z + self.dist
        # Fill the usable stage, not a small island inside it. The ring may
        # lightly intersect the animation, but it must not shrink the sphere.
        f = min(self.width(), self.height()) * 1.65
        ok = z > 0.05
        zs = np.where(ok, z, 1.0)
        sx = self.width()  / 2 + f * x / zs
        sy_ = self.height() / 2 - f * y / zs
        return np.stack([sx, sy_], axis=1), z, ok

    def paintEvent(self, _e):
        with owned_painter(self) as qp:
            if qp is None:
                return
            try:
                qp.setRenderHint(QPainter.RenderHint.Antialiasing)
                w, h = self.width(), self.height()
                # near-transparent dark bg with subtle radial glow
                g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.72)
                g.setColorAt(0.0, QColor(18, 28, 42, 220))
                g.setColorAt(1.0, QColor(6, 10, 18, 240))
                qp.fillRect(self.rect(), QBrush(g))
                p = self.params
                # OPTICAL PHYSICS SYMPTOMATICS — the field's stochastic / lock / fractal state
                # is rendered as coherence, chromatic dispersion, caustics, diffraction and
                # polarization, so the engine's condition is visible, not just audible.
                stoch = max(0.0, min(1.0, float(p.get("stochastic", 0.0) or 0.0)))
                frac = max(0.0, min(1.0, float(p.get("fractal_depth", 0.0) or 0.0)))
                lock_ms = max(0.0, min(2000.0, float(p.get("lock_ms", 0.0) or 0.0)))
                field_rate = max(0.0, min(1.0, float(p.get("field_rate", 0.5) or 0.0)))
                coherence = max(0.0, min(1.0, 0.92 - 0.55 * stoch + 0.30 * (lock_ms / 2000.0)))
                dispersion = max(0.0, min(1.0, 0.12 + 0.85 * stoch + 0.35 * frac))
                caustic = max(0.0, min(1.0, 0.20 + 0.55 * frac + 0.25 * stoch))
                polarization = max(0.0, min(1.0, 0.18 + 0.72 * field_rate))
                phase = self.t * (0.45 + 2.6 * field_rate)
                cxp, cyp = w / 2.0, h / 2.0
                base_r = min(w, h)
                for shell in range(4):
                    path = QPainterPath()
                    for i in range(121):
                        a = math.tau * i / 120.0
                        wob = 1.0 + 0.035 * math.sin(7.0 * a + phase + shell * 0.9)
                        rr = base_r * (0.18 + 0.075 * shell + 0.025 * math.sin(phase * 0.7 + shell))
                        x = cxp + rr * wob * math.cos(a) * (1.0 + 0.18 * dispersion)
                        y = cyp + rr * wob * math.sin(a) * (0.72 + 0.10 * coherence)
                        if i == 0:
                            path.moveTo(x, y)
                        else:
                            path.lineTo(x, y)
                    hue = int((185 + shell * 26 + 40 * dispersion) % 360)
                    col = QColor.fromHsv(hue, 150, 255, int(18 + 50 * caustic * (1.0 - shell / 5.0)))
                    qp.setBrush(Qt.BrushStyle.NoBrush)
                    qp.setPen(QPen(col, 1.0 + 0.8 * dispersion))
                    qp.drawPath(path)
                fan = int(10 + 10 * dispersion)
                for k in range(fan):
                    a = math.tau * k / max(1, fan) + phase * 0.08
                    r0 = base_r * (0.08 + 0.02 * math.sin(phase + k))
                    r1 = base_r * (0.30 + 0.16 * polarization) * (0.7 + 0.3 * math.sin(phase * 0.6 + k * 1.7))
                    qp.setPen(QPen(QColor.fromHsv(int((190 + 90 * k / max(1, fan)) % 360), 180, 255,
                                                  int(12 + 34 * caustic)), 0.8))
                    qp.drawLine(QPointF(cxp + r0 * math.cos(a), cyp + r0 * math.sin(a)),
                                QPointF(cxp + r1 * math.cos(a), cyp + r1 * math.sin(a)))
                gen = int(self.t * 1000.0 / max(2.0, float(p.get("block_ms", 12.0)))) % max(1, len(self.ca))
                ca_row = self.ca[gen % len(self.ca)] if len(self.ca) else np.zeros(md.H, np.uint8)
                ball_h = float(self.ball[int(self.t / 0.02) % len(self.ball)])
                vx, vy, vz = (list(p.get("vector") or [0.5, 0.5, 0.5]) + [0.5] * 3)[:3]
                rot = float(p.get("rot_hz", 0.1)) * math.tau * self.t
                vec = np.array([vx * math.cos(rot) - vy * math.sin(rot),
                                vz * math.cos(0.5 * rot),
                                vx * math.sin(rot) + vy * math.cos(rot)])
                # --- MEUM PHYLLOTAXIS SPHERE MESH
                sphere_pts = _sphere_displaced(self.amps_n, ca_row, ball_h, vec, self.t)
                S, Z, ok = self._proj(sphere_pts)
                n_body = _SPHERE_N
                # chromatic ghost edges: refractive dispersion splits the mesh spectrally
                if dispersion > 0.05:
                    split = 0.7 + 2.6 * dispersion
                    for gi, (i, j) in enumerate(_SPHERE_EDGES):
                        if gi % 3:
                            continue
                        if i >= len(S) or j >= len(S) or not (ok[i] and ok[j]):
                            continue
                        dxe, dye = S[j][0] - S[i][0], S[j][1] - S[i][1]
                        inv = 1.0 / max(1e-6, math.hypot(dxe, dye))
                        nx, ny = -dye * inv, dxe * inv
                        for off, col in ((-split, QColor(255, 50, 70, int(25 + 65 * dispersion))),
                                         (split, QColor(40, 90, 255, int(25 + 65 * dispersion)))):
                            qp.setPen(QPen(col, 0.7))
                            qp.drawLine(QPointF(S[i][0] + nx * off, S[i][1] + ny * off),
                                        QPointF(S[j][0] + nx * off, S[j][1] + ny * off))
                # draw edges — Meum spiral path + cross-links
                for i, j in _SPHERE_EDGES:
                    if i >= len(S) or j >= len(S):
                        continue
                    if not (ok[i] and ok[j]):
                        continue
                    depth = (Z[i] + Z[j]) * 0.5
                    brightness = int(max(30, min(200, 180 / depth)))
                    # hue: position along Meum spiral (index / N mapped to 200..320)
                    hue = int((200 + 120 * i / max(1, n_body)) % 360)
                    col = QColor.fromHsv(hue, 90, brightness, 140)
                    qp.setPen(QPen(col, 0.8))
                    qp.drawLine(QPointF(*S[i]), QPointF(*S[j]))
                # draw CA-active vertex dots
                for idx in range(min(n_body, len(S))):
                    if ca_row[idx % len(ca_row)] and ok[idx]:
                        hue = int((200 + 120 * idx / max(1, n_body)) % 360)
                        col = QColor.fromHsv(hue, 200, 255, 220)
                        qp.setPen(Qt.PenStyle.NoPen); qp.setBrush(col)
                        r = max(1.5, 5.0 / float(Z[idx]))
                        qp.drawEllipse(QPointF(*S[idx]), r, r)
                        if caustic > 0.05:
                            spike = r * (2.0 + 3.0 * caustic)
                            qp.setPen(QPen(QColor(185, 240, 255, int(35 + 90 * caustic)), 0.6))
                            qp.drawLine(QPointF(S[idx][0] - spike, S[idx][1]), QPointF(S[idx][0] + spike, S[idx][1]))
                            qp.drawLine(QPointF(S[idx][0], S[idx][1] - spike), QPointF(S[idx][0], S[idx][1] + spike))
                # fixed resonators: rings
                if self.res:
                    rmax = max(self.res)
                    for r in self.res:
                        yy = -1.0 + 2.0 * (math.log(r) / math.log(rmax) if rmax > 1 else 0.5)
                        ang = np.linspace(0, math.tau, 48)
                        ring = np.stack([1.3 * np.cos(ang), np.full_like(ang, yy), 1.3 * np.sin(ang)], axis=1)
                        Sr, _z, okr = self._proj(ring)
                        qp.setPen(QPen(QColor(255, 209, 102, 130), 1.4))
                        for i in range(len(ang) - 1):
                            if okr[i] and okr[i + 1]:
                                qp.drawLine(QPointF(*Sr[i]), QPointF(*Sr[i + 1]))
                # bouncing ball
                Sb, Zb, okb = self._proj([[0.0, -1.3 + 1.6 * ball_h, 0.0], [0.0, -1.3, 0.0]])
                if okb.all():
                    rad = max(5.0, 52.0 / float(Zb[0]))
                    qp.setPen(QPen(QColor(0, 0, 0, 80), 1)); qp.setBrush(QColor(0, 0, 0, 60))
                    qp.drawEllipse(QPointF(*Sb[1]), rad * 0.85, rad * 0.28)
                    gg = QRadialGradient(QPointF(Sb[0][0] - rad / 3, Sb[0][1] - rad / 3), rad * 1.4)
                    gg.setColorAt(0.0, QColor("#ffffff")); gg.setColorAt(1.0, QColor("#ff6b9a"))
                    qp.setPen(Qt.PenStyle.NoPen); qp.setBrush(QBrush(gg))
                    qp.drawEllipse(QPointF(*Sb[0]), rad, rad)
                    if coherence > 0.05:
                        qp.setBrush(Qt.BrushStyle.NoBrush)
                        for ring_i in range(3):
                            qp.setPen(QPen(QColor.fromHsv((200 + ring_i * 55) % 360, 180, 255,
                                                          int(55 + 95 * coherence)), 1.1))
                            rr = rad * (1.16 + 0.12 * ring_i)
                            qp.drawEllipse(QPointF(*Sb[0]), rr, rr)
                # vector arrow
                nv = float(np.linalg.norm(vec))
                if nv > 0:
                    v = vec / nv * 1.1
                    Sv, _z, okv = self._proj([[0, 0, 0], v])
                    if okv.all():
                        qp.setPen(QPen(QColor("#7dd3fc"), 2.5, cap=Qt.PenCapStyle.RoundCap))
                        qp.drawLine(QPointF(*Sv[0]), QPointF(*Sv[1]))
                        qp.setBrush(QColor("#7dd3fc")); qp.setPen(Qt.PenStyle.NoPen)
                        qp.drawEllipse(QPointF(*Sv[1]), 4, 4)
                qp.setPen(QColor(190, 235, 255, 210))
                qp.setFont(QFont("Sans", 7, QFont.Weight.Bold))
                qp.drawText(8, 14, f"OPTICS · coh {coherence:.2f} · disp {dispersion:.2f} · caustic {caustic:.2f} · pol {polarization:.2f} · lock {lock_ms:.0f}ms")
                qp.setPen(QColor(180, 210, 230, 160))
                qp.setFont(QFont("Sans", 8))
                qp.drawText(8, h - 8, "drag = orbit · scroll = yaw (passive) · M≈1.1976")
            finally:
                if qp.isActive():
                    qp.end()


# ---------------------------------------------------------------------------
# SynthsMasterPanel — full status/graph dialog
# ---------------------------------------------------------------------------

class SynthsMasterPanel(QDialog):
    """Real-time SynthsMasterEngine status with interactive 2D graphs."""

    def __init__(self, host, parent=None):
        super().__init__(parent or host)
        self.host = host
        self.setWindowTitle("🌀 Synths Master Engine — Live Status & Control")
        self.setModal(False)
        self.resize(1360, 900)
        self.setMinimumSize(640, 480)
        lay = QVBoxLayout(self)
        self.canvas_scroll = QScrollArea(self)
        self.canvas_scroll.setObjectName("synthsMasterCanvasScroll")
        self.canvas_scroll.setWidgetResizable(True)
        self.canvas_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.canvas_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        lay.addWidget(self.canvas_scroll)
        tabs = QTabWidget()
        tabs.setMinimumSize(1280, 840)
        self.canvas_scroll.setWidget(tabs)

        # -- Tab: Pool hit rates
        t0 = QWidget(); QVBoxLayout(t0)
        self._pool_view = _GraphWidget(t0, title="Pool Hit Rate  (blue=FI-exact  green=3D-prox  red=miss)",
                                       colors=["#3aa8ff", "#44cc88", "#ff4444"], n_series=3, maxpts=200)
        t0.layout().addWidget(self._pool_view)
        _pool_lbl = QLabel(
            "blue = scalar FI hit (L1) · green = 3D proximity hit (L2/L3) · red = full miss\n"
            "Pool 3D index size shown in brackets. Higher hit% = faster canonical inference.", t0)
        _pool_lbl.setStyleSheet("color:#9ff5dc; font-size:7pt;")
        t0.layout().addWidget(_pool_lbl)
        self._pool_3d_lbl = QLabel("3D index: —", t0)
        self._pool_3d_lbl.setStyleSheet("color:#44cc88; font-size:7pt;")
        t0.layout().addWidget(self._pool_3d_lbl)
        self._gate_lbl = QLabel("Gate: tol_L2 — · tol_axis — · hit rate —", t0)
        self._gate_lbl.setStyleSheet("color:#ffcc44; font-size:7pt;")
        t0.layout().addWidget(self._gate_lbl)
        tabs.addTab(t0, "Pool Hits")

        # -- Tab: Wavetable spectra
        t1 = QWidget(); QVBoxLayout(t1)
        self._spec_view = _GraphWidget(t1, title="Wavetable Partial Amplitudes  (12 partials)",
                                       colors=["#00ffcc"], n_series=1, mode="bar", maxpts=md.H)
        t1.layout().addWidget(self._spec_view)
        self._chk_log = QCheckBox("Log scale"); self._chk_log.setChecked(True)
        t1.layout().addWidget(self._chk_log)
        tabs.addTab(t1, "Wavetable Spectra")

        # -- Tab: CA evolution
        t2 = QWidget(); QVBoxLayout(t2)
        self._ca_view = _CAWidget(t2)
        t2.layout().addWidget(self._ca_view)
        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel("CA Rule:"))
        self._rule_spin = QSpinBox(); self._rule_spin.setRange(0, 255); self._rule_spin.setValue(90)
        self._rule_spin.valueChanged.connect(lambda v: self._ca_view.set_rule(v))
        rule_row.addWidget(self._rule_spin)
        t2.layout().addLayout(rule_row)
        tabs.addTab(t2, "CA Evolution")

        # -- Tab: Finite-infinity series
        t3 = QWidget(); QVBoxLayout(t3)
        self._fi_view = _GraphWidget(t3, title="Finite-Infinity Pool Mix Series  (n mod 134 964 356)",
                                     colors=["#ffd166", "#a0f8c0", "#7dd3fc"], n_series=3, maxpts=256)
        t3.layout().addWidget(self._fi_view)
        from_row = QHBoxLayout()
        from_row.addWidget(QLabel("seed:"))
        self._fi_seed = QSpinBox(); self._fi_seed.setRange(0, 999999); self._fi_seed.setValue(0)
        self._fi_seed.valueChanged.connect(self._refresh_fi)
        from_row.addWidget(self._fi_seed)
        from_row.addStretch(1)
        t3.layout().addLayout(from_row)
        tabs.addTab(t3, "Finite-Infinity")

        # -- Tab: Hardware clock
        t4 = QWidget(); QVBoxLayout(t4)
        self._hw_view = _GraphWidget(t4, title="Hardware Clock Drift (ppm)",
                                     colors=["#ff9f43"], n_series=1, maxpts=120)
        t4.layout().addWidget(self._hw_view)
        self._hw_lbl = QLabel("No clock monitor data yet"); t4.layout().addWidget(self._hw_lbl)
        tabs.addTab(t4, "HW Clock")

        # -- Tab: Settings
        t5 = QWidget(); fl = QFormLayout(t5)
        self._chk_canon = QCheckBox("Canonical lead influences all engines")
        self._chk_canon.setChecked(True)
        fl.addRow("Canon influence", self._chk_canon)
        self._mix_sl = QSlider(Qt.Orientation.Horizontal); self._mix_sl.setRange(0, 100); self._mix_sl.setValue(50)
        fl.addRow("Lead carrier mix %", self._mix_sl)
        self._chk_fi = QCheckBox("Enable finite-infinity GREP in pool decisions")
        self._chk_fi.setChecked(True)
        fl.addRow("FI-GREP", self._chk_fi)
        self._workers_spin = QSpinBox(); self._workers_spin.setRange(1, 64)
        import os as _os
        self._workers_spin.setValue(min(32, max(2, int(_os.cpu_count() or 8))))
        fl.addRow("sCode work threads", self._workers_spin)
        apply_btn = QPushButton("Apply settings")
        apply_btn.clicked.connect(self._apply_settings)
        fl.addRow(apply_btn)
        tabs.addTab(t5, "Settings")

        self._timer = QTimer(self); self._timer.setInterval(200)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._refresh_fi()

    def _tick(self):
        if not _alive(self):
            self._timer.stop()
            return
        host = self.host
        opt = getattr(host, "_scode_optimizer", None)
        if opt is not None:
            try:
                st = dict(opt._stats)
                total = st.get("completion_submitted", 0) or 1
                hit_pct  = 100.0 * st.get("pool_hits", 0)         / total
                hit3d    = 100.0 * st.get("fi_grep_3d_hits", 0)   / total
                miss_pct = 100.0 * st.get("pool_misses", 0)       / total
                self._pool_view.push([hit_pct, hit3d, miss_pct])
                try:
                    ps = opt.pool_stats()
                    n3d = ps.get("pool_3d_index", 0)
                    self._pool_3d_lbl.setText(
                        f"3D index: {n3d} entries  "
                        f"L2/L3 hits: {int(st.get('fi_grep_3d_hits',0))}  "
                        f"misses: {int(st.get('fi_grep_3d_misses',0))}")
                    tl2  = ps.get("gate_tol_l2",   0.0)
                    tax  = ps.get("gate_tol_axis",  0.0)
                    ghr  = ps.get("gate_hit_rate",  0.0)
                    gwin = ps.get("gate_window",    0)
                    if hasattr(self, "_gate_lbl"):
                        self._gate_lbl.setText(
                            f"Gate: tol_L2 {tl2:.4f} · tol_axis {tax:.4f} · "
                            f"hit rate {ghr*100:.1f}% (n={gwin})")
                except Exception:
                    pass
            except Exception:
                pass
        # wavetable spectrum
        try:
            name = host.instrument_selector_dropdown.currentText()
            slot = host._instance_slot(name)
            p, _ = host._md_params(name, slot)
            amps = md.table_amplitudes(p.get("script", "1/k"))
            m = float(np.max(np.abs(amps))) or 1.0
            if self._chk_log.isChecked():
                vals = np.clip(20.0 * np.log10(np.abs(amps) / m + 1e-9) / 60.0 + 1.0, 0.0, 1.0)
            else:
                vals = np.abs(amps) / m
            self._spec_view.set_bars(vals.tolist())
        except Exception:
            pass
        # hardware clock
        try:
            mon = getattr(host, "_hw_clock_monitor", None)
            if mon is not None:
                ppm = mon.drift_ppm()
                self._hw_view.push([ppm])
                self._hw_lbl.setText(f"Drift: {ppm:.2f} ppm  |  hw ticks: {mon.hw_ticks()}")
        except Exception:
            pass

    def _refresh_fi(self):
        try:
            from scode_optimizer_bridge import SCodeOptimizerBridge
            finite_infinity = int(getattr(SCodeOptimizerBridge, "FINITE_INFINITY", 134964356))
        except Exception:
            finite_infinity = 134964356
        finite_infinity = max(1, finite_infinity)
        seed = self._fi_seed.value()
        rng = np.random.default_rng(seed)
        a = rng.integers(0, finite_infinity, 256) % finite_infinity
        b = rng.integers(0, finite_infinity, 256) % finite_infinity
        c = (a + b) % finite_infinity
        self._fi_view.set_lines([
            (a / finite_infinity).tolist(),
            (b / finite_infinity).tolist(),
            (c / finite_infinity).tolist(),
        ])

    def _apply_settings(self):
        try:
            opt = getattr(self.host, "_scode_optimizer", None)
            if opt is not None:
                new_max = int(self._workers_spin.value())
                try:
                    if hasattr(opt._work_workers, "set_max_workers"):
                        opt._work_workers.set_max_workers(new_max)
                    elif hasattr(opt._work_workers, "_max_workers"):
                        opt._work_workers._max_workers = new_max
                except Exception:
                    pass
            if self._chk_fi.isChecked():
                try:
                    getattr(self.host, "_scode_optimizer", None) and setattr(
                        self.host._scode_optimizer, "_fi_grep_enabled", True)
                except Exception:
                    pass
        except Exception:
            pass

    def closeEvent(self, e):
        self._timer.stop()
        super().closeEvent(e)


class _GraphWidget(QWidget):
    def __init__(self, parent, title="", colors=None, n_series=1, mode="line", maxpts=200):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._title = title
        self._colors = colors or ["#00ffcc"]
        self._n = n_series
        self._mode = mode
        self._maxpts = maxpts
        self._series: list[list[float]] = [[] for _ in range(n_series)]

    def push(self, values: list):
        for i, v in enumerate(values[:self._n]):
            self._series[i].append(float(v))
            if len(self._series[i]) > self._maxpts:
                self._series[i] = self._series[i][-self._maxpts:]
        self.update()

    def set_bars(self, values: list):
        self._series[0] = [float(v) for v in values]
        self.update()

    def set_lines(self, series: list):
        for i, vals in enumerate(series[:self._n]):
            self._series[i] = [float(v) for v in vals]
        self.update()

    def wheelEvent(self, e):
        e.ignore()

    def paintEvent(self, _e):
        with owned_painter(self) as qp:
            if qp is None:
                return
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            qp.fillRect(self.rect(), QColor("#0a1420"))
            W, H = self.width(), self.height()
            if self._title:
                qp.setPen(QColor("#9ab8cc"))
                qp.setFont(QFont("Sans", 8))
                qp.drawText(6, 14, self._title)
            bh = H - 22; by = 18
            if self._mode == "bar":
                vals = self._series[0]
                if not vals:
                    qp.end(); return
                bw = W / len(vals)
                col = QColor(self._colors[0] if self._colors else "#00ffcc")
                for i, v in enumerate(vals):
                    hgt = float(v) * bh
                    qp.fillRect(QRectF(i * bw + 1, by + bh - hgt, max(1.0, bw - 2), hgt), col)
            else:
                for si in range(self._n):
                    vals = self._series[si]
                    if len(vals) < 2:
                        continue
                    col = QColor(self._colors[si % len(self._colors)])
                    qp.setPen(QPen(col, 1.5))
                    mn = min(vals); mx = max(vals)
                    rng = (mx - mn) or 1.0
                    path = QPainterPath()
                    for xi, v in enumerate(vals):
                        x = xi * W / (len(vals) - 1)
                        y = by + bh - (v - mn) / rng * bh
                        path.moveTo(QPointF(x, y)) if xi == 0 else path.lineTo(QPointF(x, y))
                    qp.drawPath(path)
            qp.end()


class _CAWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._rule = 90
        self._rows = None

    def set_rule(self, rule: int):
        self._rule = int(rule) & 255
        self._rows = None
        self.update()

    def wheelEvent(self, e):
        e.ignore()

    def paintEvent(self, _e):
        with owned_painter(self) as qp:
            if qp is None:
                return
            qp.fillRect(self.rect(), QColor("#0a1420"))
            W, H = self.width(), self.height()
            rows = 48; cols = max(1, min(W, 128))
            if self._rows is None or self._rows.shape != (rows, cols):
                cells = np.zeros(cols, dtype=np.uint8); cells[cols // 2] = 1
                self._rows = md._ca_rows(self._rule, rows, cells)
            cw = W / cols; ch = (H - 4) / rows
            col_on = QColor("#00ffcc"); col_off = QColor("#0d2030")
            for r in range(rows):
                for c in range(cols):
                    x = int(c * cw); y = int(4 + r * ch)
                    qp.fillRect(x, y, max(1, int(cw) - 1), max(1, int(ch) - 1),
                                 col_on if self._rows[r, c] else col_off)
            qp.setPen(QColor("#9ab8cc")); qp.setFont(QFont("Sans", 8))
            qp.drawText(4, H - 2, f"Rule {self._rule} · {cols} cells · {rows} generations")
            qp.end()


# ---------------------------------------------------------------------------
# ParamPicker / MasterExchangePanel — master synth ↔ geometric/panel exchange + I/O
# ---------------------------------------------------------------------------

class ParamPicker(QWidget):
    """Instrument(s) → section → parameter. Ticking several instruments acts exactly like one
    (inputs read their mean, outputs drive all of them). Reusable wherever a modulation needs a source/target."""

    def __init__(self, host, sections, parent=None):
        super().__init__(parent)
        self.host = host
        self._sections = dict(sections)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(3)
        self.cmb_inst = QComboBox(); self.cmb_inst.setMinimumWidth(130)
        self._inst_model = QStandardItemModel(self.cmb_inst)
        head = QStandardItem("(selected instrument)"); head.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._inst_model.appendRow(head)
        for n in list(getattr(host, "instrument_names_48", []) or []):
            it = QStandardItem(n)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            it.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
            self._inst_model.appendRow(it)
        self.cmb_inst.setModel(self._inst_model)
        self.cmb_sec = QComboBox(); self.cmb_sec.addItems(list(self._sections))
        self.cmb_par = QComboBox(); self.cmb_par.setMinimumWidth(110)
        self.cmb_sec.currentTextChanged.connect(self._fill_params)
        self._fill_params(self.cmb_sec.currentText())
        for w in (self.cmb_inst, self.cmb_sec, self.cmb_par):
            lay.addWidget(w)

    def _fill_params(self, sec):
        self.cmb_par.blockSignals(True)
        self.cmb_par.clear(); self.cmb_par.addItems(list(self._sections.get(sec, ())))
        self.cmb_par.blockSignals(False)

    def instruments(self):
        out = []
        for r in range(1, self._inst_model.rowCount()):
            it = self._inst_model.item(r)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.text())
        return out

    def set_value(self, insts, sec, par):
        wanted = set(insts or ())
        for r in range(1, self._inst_model.rowCount()):
            it = self._inst_model.item(r)
            it.setCheckState(Qt.CheckState.Checked if it.text() in wanted else Qt.CheckState.Unchecked)
        if sec in self._sections:
            self.cmb_sec.setCurrentText(sec)
        if par:
            self.cmb_par.setCurrentText(par)
        self.cmb_inst.setCurrentIndex(0)
        n = len(wanted)
        self._inst_model.item(0).setText("(selected instrument)" if not n else f"{n} instrument(s)")


class MasterExchangePanel(QGroupBox):
    """Exchange rules between the master synth and the geometric/panel pair, with the triad knob in
    the centre, plus the master synth's 3 inputs and 3 outputs. Untouched = canonical (Meum)."""

    _SLIDERS = (("amount", "Modulation amount", 0, 100), ("g2m", "Geometric → Panel  (− / +)", -100, 100),
                ("m2g", "Panel → Geometric  (− / +)", -100, 100), ("bi", "Bidirectional exchange", -100, 100),
                ("flux", "Meum geometric flux", 0, 100))

    def __init__(self, host, parent=None):
        super().__init__("MASTER SYNTH ⇄ GEOMETRIC / PANEL · EXCHANGE & I/O", parent)
        self.host = host
        self._loading = False
        self.setStyleSheet("QGroupBox { color:#9ff5dc; font-weight:900; border:1px solid #2f6f66; border-radius:6px; margin-top:8px; padding-top:10px; }")
        root = QVBoxLayout(self)
        center = QHBoxLayout()
        center.addStretch(1)
        knob_box = QVBoxLayout()
        self.dial_talk = QDial(); self.dial_talk.setRange(0, 100); self.dial_talk.setNotchesVisible(True)
        self.dial_talk.setFixedSize(92, 92)
        self.dial_talk.setToolTip("Triad knob: how much geometric and panel communicate while the master synth sounds (→ right) "
                                  "versus while it is silent (← left). Centre = always equally.")
        self.dial_talk.valueChanged.connect(lambda v: self._set_ex("talk", v / 100.0))
        knob_box.addWidget(self.dial_talk, 0, Qt.AlignmentFlag.AlignHCenter)
        knob_box.addWidget(QLabel("TRIAD · talk while master sounds ⇄ silent"), 0, Qt.AlignmentFlag.AlignHCenter)
        center.addLayout(knob_box)
        center.addStretch(1)
        root.addLayout(center)
        grid = QGridLayout(); grid.setHorizontalSpacing(6)
        self.ex_sl = {}
        for r, (key, label, lo, hi) in enumerate(self._SLIDERS):
            s = QSlider(Qt.Orientation.Horizontal); s.setRange(lo, hi)
            s.valueChanged.connect(lambda v, k=key: self._set_ex(k, v / 100.0))
            grid.addWidget(QLabel(label), r, 0); grid.addWidget(s, r, 1)
            self.ex_sl[key] = s
        root.addLayout(grid)
        self.lbl_ex = QLabel(""); self.lbl_ex.setStyleSheet("color:#8da5b8; font-size:8pt;")
        root.addWidget(self.lbl_ex)
        io = QGridLayout(); io.setHorizontalSpacing(4)
        self.io_rows = []
        sections = getattr(host, "MD_IO_SECTIONS", {"Synth": ("morph",)})
        for kind, modes in (("inputs", ("canonical", "off", "mix", "sustain")), ("outputs", ("canonical", "off", "drive"))):
            for j in range(3):
                r = len(self.io_rows)
                cmb_mode = QComboBox(); cmb_mode.addItems(modes)
                picker = ParamPicker(host, sections)
                amt = QDoubleSpinBox(); amt.setRange(-1.0, 1.0); amt.setSingleStep(0.05); amt.setDecimals(2)
                eff = QLabel("—"); eff.setMinimumWidth(52)
                io.addWidget(QLabel(("IN " if kind == "inputs" else "OUT ") + str(j + 1)), r, 0)
                for c, w in enumerate((cmb_mode, picker, amt, eff), start=1):
                    io.addWidget(w, r, c)
                row = (kind, j, cmb_mode, picker, amt, eff)
                for sig in (cmb_mode.currentTextChanged, picker.cmb_sec.currentTextChanged,
                            picker.cmb_par.currentTextChanged, amt.valueChanged):
                    sig.connect(lambda *_a, rr=row: self._store_io(rr))
                picker._inst_model.itemChanged.connect(lambda *_a, rr=row: self._store_io(rr))
                self.io_rows.append(row)
        root.addLayout(io)
        note = QLabel("Inputs mix into / sustain the lead; outputs drive their target (EQ = boost). The six always sum to "
                      "master volume ÷ 2 by absolute amount while preserving each route’s sign. Negative values reverse modulation; zero is neutral. 'canonical' = Meum-picked routes while engines run.")
        note.setWordWrap(True); note.setStyleSheet("color:#8da5b8; font-size:8pt;")
        root.addWidget(note)
        self._load()
        self._sync = QTimer(self); self._sync.setInterval(400); self._sync.timeout.connect(self._show_effective); self._sync.start()

    def _load(self):
        self._loading = True
        try:
            ex = self.host._md_exchange_store()
            self.dial_talk.setValue(int(round(float(ex.get("talk", 0.5)) * 100)))
            for k, s in self.ex_sl.items():
                s.setValue(int(round(float(ex.get(k, 0.0)) * 100)))
            io = self.host._md_io_store()
            for kind, j, cmb_mode, picker, amt, _eff in self.io_rows:
                e = io[kind][j]
                cmb_mode.setCurrentText(str(e.get("mode", "canonical")))
                picker.set_value(e.get("inst") or [], e.get("section"), e.get("param"))
                amt.setValue(float(e.get("amount", 0.0) or 0.0))
        finally:
            self._loading = False
        self._show_effective()

    def _set_ex(self, key, value):
        if self._loading:
            return
        st = self.host._md_exchange_store()
        st[key] = float(value)
        touched = set(st.get("touched") or ()); touched.add(key); st["touched"] = sorted(touched)
        self._changed()

    def _store_io(self, row):
        if self._loading:
            return
        kind, j, cmb_mode, picker, amt, _eff = row
        insts = picker.instruments()
        n = len(insts)
        picker._inst_model.item(0).setText("(selected instrument)" if not n else f"{n} instrument(s)")
        self.host._md_io_store()[kind][j] = {"mode": cmb_mode.currentText(), "inst": insts,
                                             "section": picker.cmb_sec.currentText(),
                                             "param": picker.cmb_par.currentText(), "amount": float(amt.value())}
        self._changed()

    def _changed(self):
        try:
            self.host._on_live_source_changed()
        except Exception:
            pass
        self._show_effective()

    def _show_effective(self):
        if not _alive(self) or not self.isVisible():
            return
        try:
            ex = self.host._md_exchange_effective()
            self.lbl_ex.setText("effective · " + "  ".join(f"{k} {ex[k]:+.2f}" for k in self.host.MD_EXCHANGE_KEYS))
            rows = self.host._md_io_effective()
            by = {}
            for r in rows:
                by.setdefault(r["kind"], []).append(r)
            canon_on = bool(self.host._md_canonical_on())
            for kind, j, cmb_mode, _p, _a, eff in self.io_rows:
                mode = cmb_mode.currentText()
                if mode == "off" or (mode == "canonical" and not canon_on):
                    eff.setText("off" if mode == "off" else "idle")
                    continue
                lst = by.get(kind, [])
                eff.setText(f"{lst.pop(0)['amount']:.3f}" if lst else "—")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# MultidimWindow — the full editor dialog
# ---------------------------------------------------------------------------


class MultidimControlMatrix(QWidget):
    """Miniaturized multidim surface: domain, script, local mod patch, five
    generator macros, EQ, sidechain, and the logical/mathematical resonator
    matrix.  Canonicals write through the same state keys so activation drives
    every control deterministically.
    """

    _FIVE = (
        ("morph", "Morph", 1, 1000, 0.01, 0.75),
        ("harmonic_freq", "HarmHz", 20, 20000, 1.0, 432.0),
        ("chaos", "Chaos", 0, 100, 0.01, 0.0),
        ("fold_depth", "Fold", 1, 1600, 0.01, 1.0),
        ("harmonic_lattice", "Lattice", 0, 100, 0.01, 0.35),
    )

    def __init__(self, host, get_name, get_user, set_user_key, parent=None):
        super().__init__(parent)
        self.host = host
        self._get_name = get_name
        self._get_user = get_user
        self._set_user_key = set_user_key
        self._loading = False
        self.setStyleSheet("background:#0e1624;")
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(3)

        # --- Script + Domain editors ---
        ed_row = QHBoxLayout()
        g_script = QGroupBox("Script editor (k)")
        g_script.setStyleSheet("QGroupBox{color:#9fd4ff;font-size:7pt;font-weight:900;}")
        ls = QVBoxLayout(g_script)
        self.ed_script = QPlainTextEdit()
        self.ed_script.setPlaceholderText('e.g. 1/k   (k%2)/k   sin(k)/k')
        self.ed_script.setMinimumSize(360, 140)
        self.ed_script.setStyleSheet("font-size:7pt;background:#10182a;color:#c8f7ed;")
        self.ed_script.textChanged.connect(self._script_changed)
        ls.addWidget(self.ed_script)
        ed_row.addWidget(g_script, 1)

        g_domain = QGroupBox("Domain editor (t,b,h,a,x,y,z,live)")
        g_domain.setStyleSheet("QGroupBox{color:#9fd4ff;font-size:7pt;font-weight:900;}")
        ld = QVBoxLayout(g_domain)
        self.ed_domain = QPlainTextEdit()
        self.ed_domain.setPlaceholderText("domain equation · structure blend")
        self.ed_domain.setMinimumSize(360, 140)
        self.ed_domain.setStyleSheet("font-size:7pt;background:#10182a;color:#c8f7ed;")
        self.ed_domain.textChanged.connect(self._domain_changed)
        ld.addWidget(self.ed_domain)
        ed_row.addWidget(g_domain, 1)
        root.addLayout(ed_row)

        # --- Local mod patch editor ---
        g_patch = QGroupBox("Local mod patch editor")
        g_patch.setStyleSheet("QGroupBox{color:#ffd977;font-size:7pt;font-weight:900;}")
        gp = QGridLayout(g_patch)
        gp.setContentsMargins(3, 6, 3, 3)
        gp.setHorizontalSpacing(3)
        gp.setVerticalSpacing(1)
        self.patch_sl = {}
        keys = list(getattr(md, "PATCH_KEYS", ()) or (
            "ball->pitch", "ball->amp", "vector->phase", "amp->freq", "amp->phase", "ca->harmonics"
        ))
        for i, k in enumerate(keys):
            lab = QLabel(k)
            lab.setStyleSheet("color:#9fdcca;font-size:6pt;background:transparent;")
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(0, 100)
            s.setFixedHeight(12)
            s.setToolTip(f"Patch route {k}")
            s.valueChanged.connect(lambda v, kk=k: self._patch_changed(kk, v / 100.0))
            r, c = divmod(i, 3)
            gp.addWidget(lab, r * 2, c)
            gp.addWidget(s, r * 2 + 1, c)
            self.patch_sl[k] = s
        root.addWidget(g_patch)

        # --- Five generator macros ---
        g_five = QGroupBox("Five generator macros (canonical)")
        g_five.setStyleSheet("QGroupBox{color:#7dd3fc;font-size:7pt;font-weight:900;}")
        gf = QGridLayout(g_five)
        gf.setContentsMargins(3, 6, 3, 3)
        self.five_sl = {}
        for c, (mkey, mlab, lo, hi, scale, default) in enumerate(self._FIVE):
            lab = QLabel(mlab)
            lab.setStyleSheet("color:#9fdcca;font-size:6pt;background:transparent;")
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(lo, hi)
            s.setValue(max(lo, min(hi, int(round(default / scale)))))
            s.setFixedHeight(12)
            s.setToolTip(f"{mlab} · {mkey}")
            s.valueChanged.connect(lambda v, kk=mkey, sc=scale: self._macro_changed(kk, v * sc))
            gf.addWidget(lab, 0, c)
            gf.addWidget(s, 1, c)
            self.five_sl[mkey] = (s, scale)
            gf.setColumnStretch(c, 1)
        root.addWidget(g_five)

        # --- EQ + sidechain ---
        g_eq = QGroupBox("EQ · Sidechain")
        g_eq.setStyleSheet("QGroupBox{color:#c8f7ed;font-size:7pt;font-weight:900;}")
        ge = QGridLayout(g_eq)
        ge.setContentsMargins(3, 6, 3, 3)
        self.eq_sl = {}
        for c, (key, lab, lo, hi, default) in enumerate((
            ("low_db", "LOW", -18, 18, 0),
            ("mid_db", "MID", -18, 18, 0),
            ("high_db", "HIGH", -18, 18, 0),
            ("sc_depth", "SC depth", 0, 100, 0),
        )):
            l = QLabel(lab)
            l.setStyleSheet("color:#9fdcca;font-size:6pt;background:transparent;")
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(lo, hi)
            s.setValue(default)
            s.setFixedHeight(12)
            s.valueChanged.connect(lambda _v: self._eq_changed())
            ge.addWidget(l, 0, c)
            ge.addWidget(s, 1, c)
            self.eq_sl[key] = s
            ge.setColumnStretch(c, 1)
        self.cmb_sc = QComboBox()
        self.cmb_sc.addItems(list(MD_CLONE_SOURCES))
        self.cmb_sc.currentTextChanged.connect(lambda _v: self._eq_changed())
        ge.addWidget(QLabel("SC src"), 0, 4)
        ge.addWidget(self.cmb_sc, 1, 4)
        root.addWidget(g_eq)

        # --- Logical / mathematical resonator matrix ---
        g_res = QGroupBox("Logical / mathematical resonator matrix")
        g_res.setStyleSheet("QGroupBox{color:#ffb0e0;font-size:7pt;font-weight:900;}")
        gr = QGridLayout(g_res)
        gr.setContentsMargins(3, 6, 3, 3)
        rules = list(getattr(md, "RESONATOR_RULES", {}).keys()) or [
            "harmonic", "platonic", "fibonacci", "triangular", "square", "golden"
        ]
        self.res_chk = {}
        self.res_mix = {}
        for i, rule in enumerate(rules):
            r, c = divmod(i, 3)
            cell = QVBoxLayout()
            chk = QCheckBox(rule)
            chk.setStyleSheet("color:#e8d0ff;font-size:6pt;")
            chk.setToolTip(f"Enable fixed resonator rule «{rule}»")
            mix = QSlider(Qt.Orientation.Horizontal)
            mix.setRange(0, 100)
            mix.setValue(100 if rule == "harmonic" else 0)
            mix.setFixedHeight(10)
            mix.setToolTip(f"{rule} mix 0–100%")
            chk.toggled.connect(lambda _v: self._res_changed())
            mix.valueChanged.connect(lambda _v: self._res_changed())
            cell.addWidget(chk)
            cell.addWidget(mix)
            wrap = QWidget()
            wrap.setLayout(cell)
            gr.addWidget(wrap, r, c)
            self.res_chk[rule] = chk
            self.res_mix[rule] = mix
        root.addWidget(g_res)

    def _notify(self):
        try:
            name = self._get_name()
            _mirror_multidim_user(self.host, name)
        except Exception:
            pass
        try:
            self.host._on_live_source_changed()
        except Exception:
            pass

    def _script_changed(self):
        if self._loading:
            return
        self._set_user_key("script", self.ed_script.toPlainText().strip() or None)

    def _domain_changed(self):
        if self._loading:
            return
        self._set_user_key("domain", self.ed_domain.toPlainText().strip() or None)

    def _patch_changed(self, key, val):
        if self._loading:
            return
        u = self._get_user(create=True)
        u.setdefault("patch", {})[key] = float(val)
        self._notify()

    def _macro_changed(self, key, val):
        if self._loading:
            return
        self._set_user_key(key, float(val))
        # also mirror into md_clones.multidim for canonical interlink
        try:
            name = self._get_name()
            st = self.host.instrument_param_state.setdefault(name, {})
            clones = st.setdefault("md_clones", {})
            multi = clones.setdefault("multidim", _md_clone_defaults())
            multi[key] = float(val)
            multi["enabled"] = True
        except Exception:
            pass
        self._notify()

    def _eq_changed(self):
        if self._loading:
            return
        try:
            name = self._get_name()
            st = self.host.instrument_param_state.setdefault(name, {})
            clones = st.setdefault("md_clones", {})
            multi = clones.setdefault("multidim", _md_clone_defaults())
            multi["low_db"] = float(self.eq_sl["low_db"].value())
            multi["mid_db"] = float(self.eq_sl["mid_db"].value())
            multi["high_db"] = float(self.eq_sl["high_db"].value())
            multi["depth"] = float(self.eq_sl["sc_depth"].value()) / 100.0
            multi["source"] = str(self.cmb_sc.currentText())
            multi["enabled"] = True
            self._set_user_key("eq", {
                "low_db": multi["low_db"], "mid_db": multi["mid_db"], "high_db": multi["high_db"],
                "sidechain_source": multi["source"], "sidechain_depth": multi["depth"],
            })
        except Exception:
            pass
        self._notify()

    def _res_changed(self):
        if self._loading:
            return
        active = []
        mixes = {}
        for rule, chk in self.res_chk.items():
            if chk.isChecked():
                active.append(rule)
                mixes[rule] = float(self.res_mix[rule].value()) / 100.0
        self._set_user_key("resonators", "+".join(active) if active else None)
        self._set_user_key("resonator_mix", mixes)

    def load_from_state(self, p, u):
        """Populate controls from programme p + user override u."""
        self._loading = True
        try:
            script = str(u.get("script", p.get("script", "")) or "")
            domain = str(u.get("domain", p.get("domain", "")) or "")
            self.ed_script.setPlainText(script)
            self.ed_domain.setPlainText(domain)
            patch = dict(p.get("patch") or {})
            patch.update(u.get("patch") or {})
            for k, s in self.patch_sl.items():
                s.setValue(int(round(float(patch.get(k, 0.0)) * 100)))
            for mkey, (s, scale) in self.five_sl.items():
                val = float(u.get(mkey, p.get(mkey, self._FIVE[[x[0] for x in self._FIVE].index(mkey)][5])))
                s.setValue(max(s.minimum(), min(s.maximum(), int(round(val / scale)))))
            eq = dict(u.get("eq") or {})
            self.eq_sl["low_db"].setValue(int(eq.get("low_db", 0)))
            self.eq_sl["mid_db"].setValue(int(eq.get("mid_db", 0)))
            self.eq_sl["high_db"].setValue(int(eq.get("high_db", 0)))
            self.eq_sl["sc_depth"].setValue(int(round(float(eq.get("sidechain_depth", 0.0)) * 100)))
            src = str(eq.get("sidechain_source", "Off"))
            if self.cmb_sc.findText(src) >= 0:
                self.cmb_sc.setCurrentText(src)
            res = str(u.get("resonators", p.get("resonators", "harmonic")) or "harmonic")
            active = set(x.strip() for x in res.split("+") if x.strip())
            mixes = dict(u.get("resonator_mix") or {})
            for rule, chk in self.res_chk.items():
                chk.setChecked(rule in active)
                self.res_mix[rule].setValue(int(round(float(mixes.get(rule, 1.0 if rule in active else 0.0)) * 100)))
        finally:
            self._loading = False



class MultidimWindow(QDialog):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setWindowTitle("🌀 Multidimensional synth — geodesic sphere · canonical engine")
        self.setModal(False)
        self.resize(1480, 900)
        self.setMinimumSize(640, 480)
        self._loading = False
        window_layout = QVBoxLayout(self)
        self.canvas_scroll = QScrollArea(self)
        self.canvas_scroll.setObjectName("multidimCanvasScroll")
        self.canvas_scroll.setWidgetResizable(True)
        self.canvas_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.canvas_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        window_layout.addWidget(self.canvas_scroll)
        canvas = QWidget()
        canvas.setMinimumSize(2200, 1280)
        outer = QVBoxLayout(canvas)
        self.canvas_scroll.setWidget(canvas)
        top = QHBoxLayout()
        self.cmb_inst = QComboBox()
        self.cmb_inst.addItems(list(getattr(host, "instrument_names_48", []) or []))
        try:
            self.cmb_inst.setCurrentText(host.instrument_selector_dropdown.currentText())
        except Exception:
            pass
        self.cmb_inst.currentTextChanged.connect(lambda *_a: self._load())
        self.lbl_owner = QLabel("")
        self.sld_mix = QSlider(Qt.Orientation.Horizontal)
        self.sld_mix.setRange(33, 66); self.sld_mix.setFixedWidth(160)
        self.sld_mix.setValue(int(round(host._md_mix() * 100)))
        _bind_role_slider(self.sld_mix, "result")
        self.lbl_mix = QLabel(f"{self.sld_mix.value()}%")
        self.sld_mix.valueChanged.connect(self._mix_changed)
        b_aud = QPushButton("▶ Audition"); b_aud.clicked.connect(self._audition)
        b_reset = QPushButton("Reset to canonical"); b_reset.clicked.connect(self._reset)
        b_master = QPushButton("🌀 Master Engine…"); b_master.clicked.connect(self._open_master)
        _editor_btn_css = (
            "QPushButton{background:#1a2f48;color:#9fe8ff;border:2px solid #3d7ea6;"
            "border-radius:8px;padding:10px 16px;font-weight:900;font-size:11pt;min-height:36px;min-width:110px;}"
            "QPushButton:hover{background:#254a6e;border-color:#7ce7ff;}"
            "QPushButton:pressed{background:#ff9f1c;color:#16110a;}"
        )
        for _b in (b_aud, b_reset, b_master):
            _b.setStyleSheet(_editor_btn_css)
            _b.setMinimumHeight(40)
            _b.setMinimumWidth(128)
        for wdg in (QLabel("Instrument"), self.cmb_inst, self.lbl_owner,
                    QLabel("   Mix"), self.sld_mix, self.lbl_mix,
                    b_aud, b_reset, b_master):
            top.addWidget(wdg)
        top.addStretch(1)
        outer.addLayout(top)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.view = MD3DView(); split.addWidget(self.view)
        self.view.setMinimumSize(1120, 1120)
        split.setChildrenCollapsible(False)
        sc = QScrollArea(); sc.setWidgetResizable(True)
        sc.setObjectName("multidimParameterScroll")
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sc.setMinimumWidth(1000)
        panel = QWidget(); form = QFormLayout(panel)
        panel.setMinimumWidth(960)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        # R41.2g: geometrics master at the very top of the multidim control column
        try:
            _geo_top = QWidget(panel)
            _geo_l = QHBoxLayout(_geo_top)
            _geo_l.setContentsMargins(0, 0, 0, 4)
            _geo_lab = QLabel("GEOMETRICS · PKP / EQR / FRACTALLIZER")
            _geo_lab.setStyleSheet("color:#7dd3fc;font-size:7pt;font-weight:900;background:transparent;")
            self.sld_window_geometrics = QSlider(Qt.Orientation.Horizontal)
            self.sld_window_geometrics.setRange(0, 1000)
            self.sld_window_geometrics.setValue(500)
            self.sld_window_geometrics.setToolTip(
                "Combined Geometrics master (panel-geometrics underlying ratio). "
                "Mirrors main-window geometrics master."
            )
            self.sld_window_geometrics.valueChanged.connect(self._on_window_geometrics)
            _geo_l.addWidget(_geo_lab)
            _geo_l.addWidget(self.sld_window_geometrics, 1)
            form.addRow(_geo_top)
        except Exception as _geo_exc:
            print(f"[Multidim] top geometrics: {_geo_exc}")
        try:
            form.addRow(MasterExchangePanel(host, panel))
        except Exception as _exc:
            print(f"[Multidim] exchange panel: {_exc}")
        self.cmb_preset = QComboBox(); self.cmb_preset.addItem("(canonical programme)", "")
        for n in md.PRESET_NAMES:
            self.cmb_preset.addItem(n, n)
        self.cmb_preset.currentIndexChanged.connect(lambda *_a: self._set("preset", self.cmb_preset.currentData() or None))
        form.addRow("Preset", self.cmb_preset)
        self.ed_script = QLineEdit()
        self.ed_script.editingFinished.connect(lambda: self._set("script", self.ed_script.text().strip() or None))
        form.addRow("Script (k)", self.ed_script)
        self.ed_domain = QLineEdit()
        self.ed_domain.editingFinished.connect(lambda: self._set("domain", self.ed_domain.text().strip() or None))
        form.addRow("Domain equation", self.ed_domain)
        self.spin_rule = QSpinBox(); self.spin_rule.setRange(0, 255)
        self.spin_rule.valueChanged.connect(lambda v: self._set("ca_rule", int(v)))
        form.addRow("CA rule", self.spin_rule)
        self.cmb_res = QComboBox(); self.cmb_res.addItems(list(md.RESONATOR_RULES))
        self.cmb_res.currentTextChanged.connect(lambda v: self._set("resonators", v))
        form.addRow("Fixed resonators", self.cmb_res)
        gpatch = QGroupBox("Modular patch"); fp = QFormLayout(gpatch)
        self.patch_sl = {}
        for _i, k in enumerate(md.PATCH_KEYS):
            s = QSlider(Qt.Orientation.Horizontal); s.setRange(0, 100)
            s.valueChanged.connect(lambda v, kk=k: self._set_patch(kk, v / 100.0))
            _bind_role_slider(s, _ROLE_ORDER[_i % len(_ROLE_ORDER)])
            fp.addRow(k, s); self.patch_sl[k] = s
        form.addRow(gpatch)
        gvec = QGroupBox("Vector"); fv = QFormLayout(gvec)
        self.vec_sl = []
        for i, a in enumerate("xyz"):
            s = QSlider(Qt.Orientation.Horizontal); s.setRange(-100, 100)
            s.valueChanged.connect(lambda _v, ii=i: self._set_vector())
            _bind_role_slider(s, ("independent_variable", "result", "dependent_variable")[i])
            fv.addRow(a, s); self.vec_sl.append(s)
        form.addRow(gvec)
        self.num_sl = {}
        for _i, (key, label, lo, hi, sc_) in enumerate(NUM_CONTROLS):
            s = QSlider(Qt.Orientation.Horizontal); s.setRange(lo, hi)
            s.valueChanged.connect(lambda v, kk=key, f=sc_: self._set(kk, v * f))
            _bind_role_slider(s, _ROLE_FOR_PARAM.get(key, _ROLE_ORDER[_i % len(_ROLE_ORDER)]), lo, hi)
            form.addRow(label, s); self.num_sl[key] = (s, sc_)


        # R41.2e: miniaturized domain/script/patch/5-macro/EQ/sidechain/resonator matrix
        try:
            self.control_matrix = MultidimControlMatrix(
                self.host,
                get_name=self._name,
                get_user=self._user,
                set_user_key=lambda k, v: self._set(k, v),
                parent=panel,
            )
            form.addRow(self.control_matrix)
        except Exception as _mx_exc:
            print(f"[Multidim] control matrix: {_mx_exc}")
            self.control_matrix = None

        self.engine_tabs = QTabWidget()
        self.engine_tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid #405074;background:#10172a;}"
            "QTabBar::tab{background:#1b2540;color:#9fdcca;font-size:8pt;font-weight:900;padding:5px 9px;}"
            "QTabBar::tab:selected{background:#32436a;color:#ffd977;}"
        )
        field_page = QWidget(); field_form = QFormLayout(field_page)
        self.field_sl = {}
        _field_defaults = {"stochastic":0.0,"variation":0.0,"fractal_depth":0.0,
                           "lock_ms":0.0,"trigger_response":0.0,"field_rate":0.5}
        for _i, (key, label, lo, hi, scale) in enumerate(MD_FIELD_CONTROLS):
            slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(lo, hi)
            slider.valueChanged.connect(lambda v, kk=key, f=scale: self._set(kk, v * f))
            _bind_role_slider(slider, _ROLE_ORDER[_i % len(_ROLE_ORDER)], lo, hi)
            field_form.addRow(label, slider)
            self.field_sl[key] = (slider, scale, _field_defaults.get(key, 0.0))
        self.engine_tabs.addTab(field_page, "FRACTALITY / FIELD")

        canonical_page = QWidget(); canonical_form = QVBoxLayout(canonical_page)
        goava_form = QFormLayout()
        self.cmb_goava_mode = QComboBox()
        self.cmb_goava_mode.addItem("Seeded · project seed + instrument slot", "seeded")
        self.cmb_goava_mode.addItem("I/O-derived · live main-synth envelope", "io")
        self.cmb_goava_mode.setToolTip(
            "Seeded is repeatable from the project seed and instrument slot. "
            "I/O-derived bends the GOAVA Golden field from the live main-synth input envelope; "
            "when no input is present it falls back to the seeded field."
        )
        self.cmb_goava_mode.currentIndexChanged.connect(
            lambda *_: self._set("goava_mode", self.cmb_goava_mode.currentData())
        )
        goava_form.addRow("GOAVA basis", self.cmb_goava_mode)
        canonical_form.addLayout(goava_form)
        self.lbl_canonical_map = QLabel("")
        self.lbl_canonical_map.setWordWrap(True)
        self.lbl_canonical_map.setStyleSheet(
            "color:#d7c9f3;background:#171327;border:1px solid #7655a8;"
            "border-radius:6px;padding:8px;font-size:8pt;"
        )
        canonical_form.addWidget(self.lbl_canonical_map)
        canonical_form.addStretch(1)
        self.engine_tabs.addTab(canonical_page, "CANONICALS / GOAVA")

        # R41.2g: dedicated Multidim tab for geometrics control + panel-geo visualization
        try:
            geo_page = QWidget()
            geo_lay = QVBoxLayout(geo_page)
            geo_lay.setContentsMargins(4, 4, 4, 4)
            geo_lay.addWidget(QLabel("Panel ↔ Geometrics underlying blend (canonical ratio)"))
            self.sld_tab_geometrics = QSlider(Qt.Orientation.Horizontal)
            self.sld_tab_geometrics.setRange(0, 1000)
            self.sld_tab_geometrics.setValue(500)
            self.sld_tab_geometrics.valueChanged.connect(self._on_window_geometrics)
            geo_lay.addWidget(self.sld_tab_geometrics)
            self.lbl_geo_viz = QLabel("panel ████████░░░░ geometrics")
            self.lbl_geo_viz.setStyleSheet("color:#9fd4ff;font-family:monospace;font-size:8pt;")
            geo_lay.addWidget(self.lbl_geo_viz)
            self.geo_viz_bar = QProgressBar()
            self.geo_viz_bar.setRange(0, 1000)
            self.geo_viz_bar.setValue(500)
            self.geo_viz_bar.setTextVisible(False)
            self.geo_viz_bar.setFixedHeight(14)
            self.geo_viz_bar.setStyleSheet(
                "QProgressBar{background:#1a2838;border:1px solid #2a4058;border-radius:3px;}"
                "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #3aa8ff, stop:0.5 #7dd3fc, stop:1 #44cc88);}"
            )
            geo_lay.addWidget(self.geo_viz_bar)
            geo_lay.addStretch(1)
            self.engine_tabs.addTab(geo_page, "GEOMETRICS")
        except Exception as _gt:
            print(f"[Multidim] geometrics tab: {_gt}")

        form.addRow(self.engine_tabs)
        panel.setMinimumHeight(form.sizeHint().height())
        sc.setWidget(panel); split.addWidget(sc); split.setStretchFactor(0, 1); split.setStretchFactor(1, 1)
        split.setSizes([1120, 1040])
        outer.addWidget(split, 1)
        note = QLabel("Every voice = (panel × geometrics) against this synth. "
                      "Controls you set mix 50 / 50 with the canonical programme (U50).")
        note.setWordWrap(True); note.setStyleSheet("color:#8da5b8;")
        outer.addWidget(note)
        self._timer = QTimer(self); self._timer.setInterval(33)
        self._timer.timeout.connect(lambda: self.view.tick(0.033))
        self._timer.start()
        self._master_panel: SynthsMasterPanel | None = None
        self._load()

    def set_activity_enabled(self, enabled):
        if not hasattr(self, "_timer"):
            return
        if bool(enabled) and self.isVisible():
            if not self._timer.isActive(): self._timer.start(33)
        else:
            self._timer.stop()

    def wheelEvent(self, e):
        e.ignore()

    def _open_master(self):
        try:
            if not _alive(self._master_panel):
                self._master_panel = SynthsMasterPanel(self.host, self)
            if not self._master_panel.isVisible():
                self._master_panel.show()
            self._master_panel.raise_()
        except Exception:
            pass

    def _name(self):
        return self.cmb_inst.currentText()

    def _user(self, create=False):
        ps = self.host.instrument_param_state
        st = ps.setdefault(self._name(), {}) if create else (ps.get(self._name()) or {})
        u = st.get("multidim")
        if u is None and create:
            u = st["multidim"] = {}
        return u if isinstance(u, dict) else {}

    def _merged(self):
        try:
            slot = self.host._instance_slot(self._name())
        except Exception:
            slot = 0
        p, seed_int = self.host._md_params(self._name(), slot)
        return p, seed_int, slot

    def _load(self):
        self._loading = True
        try:
            p, seed_int, slot = self._merged()
            u = self._user()
            self.cmb_preset.setCurrentIndex(max(0, self.cmb_preset.findData(u.get("preset", ""))))
            self.ed_script.setText(str(u.get("script", p.get("script", ""))))
            self.ed_domain.setText(str(u.get("domain", p.get("domain", ""))))
            try:
                if getattr(self, "control_matrix", None) is not None:
                    self.control_matrix.load_from_state(p, u)
            except Exception as _lm:
                print(f"[Multidim] matrix load: {_lm}")
            self.spin_rule.setValue(int(u.get("ca_rule", p.get("ca_rule", 90))) & 255)
            self.cmb_res.setCurrentText(str(u.get("resonators", p.get("resonators", "harmonic"))).split("+")[0])
            patch = dict(p.get("patch") or {}); patch.update(u.get("patch") or {})
            for k, s in self.patch_sl.items():
                s.setValue(int(round(float(patch.get(k, 0.0)) * 100)))
            vec = list(u.get("vector", p.get("vector") or [0.5, 0.5, 0.5]))
            for i, s in enumerate(self.vec_sl):
                s.setValue(int(round(float(vec[i]) * 100)))
            for key, (s, f) in self.num_sl.items():
                s.setValue(int(round(float(u.get(key, p.get(key, 0.0))) / f)))
            for key, (s, f, default) in self.field_sl.items():
                s.setValue(int(round(float(u.get(key, p.get(key, default))) / f)))
            goava_mode = str(u.get("goava_mode", p.get("goava_mode", "seeded"))).lower()
            self.cmb_goava_mode.setCurrentIndex(max(0, self.cmb_goava_mode.findData(
                "io" if goava_mode in ("io", "input", "signal") else "seeded")))
            self._refresh(p, seed_int, slot)
        finally:
            self._loading = False

    def _refresh(self, p=None, seed_int=None, slot=None):
        if p is None:
            p, seed_int, slot = self._merged()
        self.view.set_params(p, seed_int, slot)
        mode = p.get("_mode", "canonical")
        if str(mode).startswith("U"):
            txt = f"🟣 {mode} ({mode[1:]} % yours · {100 - int(mode[1:] or 50)} % canonical)"
        else:
            txt = {"canonical": "🔵 canonical", "user": "🟢 yours"}.get(mode, mode)
        engines = ", ".join(p.get("_engines") or []) if isinstance(p, dict) else ""
        self.lbl_owner.setText(txt + (f" · {engines}" if engines else ""))
        if hasattr(self, "lbl_canonical_map"):
            active = set(str(e).lower() for e in (p.get("_engines") or []))
            rows = (
                ("EUCLIDEAN", "Cellular rhythm / CA rule", bool(active & {"euclidean", "euclid"})),
                ("GOAVA", "Golden spiral table + golden resonators", "goava" in active),
                ("PHASE LOCK", "Vector-phase lock + trigger timing", bool(active & {"phase_lock", "phaselock", "lock"})),
                ("SEEDED / RANDOMIZER", "Seed-slot ball geometry + deterministic field modulation", bool(active & {"randomizer", "seeded", "seeded_randomizer", "random"})),
                ("FRACTAL SEED", "Rule-90 cellular structure + fractal depth", bool(active & {"fractal_seed", "fractal"})),
            )
            self.lbl_canonical_map.setText("\n".join(
                f"{name}: {'ACTIVE' if on else 'idle'} — {meaning}" for name, meaning, on in rows
            ))

    def _changed(self):
        _mirror_multidim_user(self.host, self._name())
        try:
            self.host._on_live_source_changed()
        except Exception:
            pass
        self._refresh()

    def _set(self, key, val):
        if self._loading:
            return
        u = self._user(create=True)
        if val is None:
            u.pop(key, None)
        else:
            u[key] = val
        self._changed()

    def _set_patch(self, key, val):
        if self._loading:
            return
        self._user(create=True).setdefault("patch", {})[key] = float(val)
        self._changed()

    def _set_vector(self):
        if self._loading:
            return
        self._user(create=True)["vector"] = [s.value() / 100.0 for s in self.vec_sl]
        self._changed()

    def _reset(self):
        st = self.host.instrument_param_state.get(self._name()) or {}
        st.pop("multidim", None)
        self._load(); self._changed()

    def _on_window_geometrics(self, value):
        """Drive main-window geometrics master + local panel-geo visualization."""
        try:
            v = int(value)
            for attr in ("sld_window_geometrics", "sld_tab_geometrics"):
                w = getattr(self, attr, None)
                if w is not None and w is not self.sender():
                    w.blockSignals(True); w.setValue(v); w.blockSignals(False)
            if hasattr(self, "geo_viz_bar") and self.geo_viz_bar is not None:
                self.geo_viz_bar.setValue(v)
            if hasattr(self, "lbl_geo_viz") and self.lbl_geo_viz is not None:
                filled = max(0, min(16, int(round(v / 1000.0 * 16))))
                self.lbl_geo_viz.setText(
                    "panel " + "█" * (16 - filled) + "░" * filled + " geometrics"
                )
            host = self.host
            master = getattr(host, "slider_geometrics_master", None)
            if master is not None:
                master.blockSignals(True)
                master.setValue(v)
                master.blockSignals(False)
            if hasattr(host, "_on_geometrics_master_changed"):
                host._on_geometrics_master_changed(v)
        except Exception as _exc:
            print(f"[Multidim] geometrics: {_exc}")

    def _mix_changed(self, v):
        self.lbl_mix.setText(f"{v}%")
        sl = getattr(self.host, "slider_multidim_mix", None)
        if sl is not None:
            sl.setValue(int(v))
        else:
            self.host._on_multidim_slider("multidim", v, None)

    def _audition(self):
        try:
            self.host.instrument_selector_dropdown.setCurrentText(self._name())
            self.host.trigger_selected_note()
        except Exception:
            pass

    def closeEvent(self, e):
        self._timer.stop()
        super().closeEvent(e)


def open_multidim_window(host):
    w = getattr(host, "_multidim_window", None)
    if not _alive(w):
        w = None
    if w is None:
        w = MultidimWindow(host)
        host._multidim_window = w
    else:
        w._load(); w._timer.start()
    w.show(); w.raise_(); w.activateWindow()
    return w


class MDCloneRack(QWidget):
    """Panel / geometric / multidim synth clones.

    Minimal canonical surface: ON + volume + 3-band EQ + sidechain, plus the
    five generator macros that the main Synth Rack exposes (morph, harmonic_freq,
    chaos, fold_depth, harmonic_lattice).  All values live under
    instrument_param_state[name]["md_clones"] and are also mirrored into the
    canonical macro user store so randomizers, profiles, and playlist cells
    can drive them deterministically.
    """

    _FIVE = (
        ("morph", "Morph", 1, 1000, 0.01, 0.75),          # 0.01–10.0
        ("harmonic_freq", "Harm Hz", 20, 20000, 1.0, 432.0),
        ("chaos", "Chaos", 0, 100, 0.01, 0.0),
        ("fold_depth", "Fold", 1, 1600, 0.01, 1.0),       # 0.01–16.0
        ("harmonic_lattice", "Lattice", 0, 100, 0.01, 0.35),
    )

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self.setStyleSheet("background:#10172a;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(5, 4, 5, 4)
        outer.setSpacing(3)
        head = QLabel("PANEL SYNTH CLONES · 5 GENERATORS · EQ · SIDECHAIN")
        head.setStyleSheet("color:#ffd977;font-size:7pt;font-weight:900;background:transparent;")
        outer.addWidget(head)

        # Row 1: core mix / EQ / sidechain
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)
        headers = ("TARGET", "ON", "VOL", "LOW", "MID", "HIGH", "SIDECHAIN", "DEPTH")
        for c, text in enumerate(headers):
            lab = QLabel(text)
            lab.setStyleSheet("color:#9fdcca;font-size:8pt;font-weight:900;background:transparent;")
            grid.addWidget(lab, 0, c)
        self.rows = {}
        for r, (key, label) in enumerate(MD_CLONE_TARGETS, start=1):
            name = QLabel(label)
            name.setStyleSheet("color:#c8f7ed;font-size:9pt;font-weight:900;background:transparent;")
            enabled = QCheckBox()
            enabled.setToolTip(f"Enable the {label.lower()} clone")
            volume = QSlider(Qt.Orientation.Horizontal); volume.setRange(0, 200); volume.setValue(100)
            low = QSlider(Qt.Orientation.Horizontal); low.setRange(-18, 18); low.setValue(0)
            mid = QSlider(Qt.Orientation.Horizontal); mid.setRange(-18, 18); mid.setValue(0)
            high = QSlider(Qt.Orientation.Horizontal); high.setRange(-18, 18); high.setValue(0)
            source = QComboBox(); source.addItems(MD_CLONE_SOURCES)
            depth = QSlider(Qt.Orientation.Horizontal); depth.setRange(0, 100); depth.setValue(0)
            for w in (volume, low, mid, high, depth):
                w.setMinimumWidth(64)
                w.setFixedHeight(18)
            volume.setToolTip("Clone local volume (0–200%)")
            low.setToolTip("Clone low band (dB)")
            mid.setToolTip("Clone mid band (dB)")
            high.setToolTip("Clone high band (dB)")
            depth.setToolTip("Clone sidechain depth (0–100%)")
            source.setToolTip("Clone sidechain source")
            source.setStyleSheet("QComboBox{font-size:6pt;background:#18233a;color:#d8f8ee;border:1px solid #405074;}")
            grid.addWidget(name, r, 0)
            grid.addWidget(enabled, r, 1)
            grid.addWidget(volume, r, 2)
            grid.addWidget(low, r, 3)
            grid.addWidget(mid, r, 4)
            grid.addWidget(high, r, 5)
            grid.addWidget(source, r, 6)
            grid.addWidget(depth, r, 7)
            self.rows[key] = {
                "enabled": enabled, "volume": volume, "low": low, "mid": mid,
                "high": high, "source": source, "depth": depth,
            }
            enabled.toggled.connect(lambda _v, k=key: self._changed(k))
            volume.valueChanged.connect(lambda _v, k=key: self._changed(k))
            low.valueChanged.connect(lambda _v, k=key: self._changed(k))
            mid.valueChanged.connect(lambda _v, k=key: self._changed(k))
            high.valueChanged.connect(lambda _v, k=key: self._changed(k))
            source.currentTextChanged.connect(lambda _v, k=key: self._changed(k))
            depth.valueChanged.connect(lambda _v, k=key: self._changed(k))
        for c in (2, 3, 4, 5, 7):
            grid.setColumnStretch(c, 1)
        outer.addLayout(grid)

        # Row 2: the five canonical generator macros
        gen_head = QLabel("GENERATOR MACROS (canonical · deterministic)")
        gen_head.setStyleSheet("color:#9fd4ff;font-size:6pt;font-weight:900;background:transparent;margin-top:4px;")
        outer.addWidget(gen_head)
        gen_grid = QGridLayout()
        gen_grid.setContentsMargins(0, 0, 0, 0)
        gen_grid.setHorizontalSpacing(3)
        gen_grid.setVerticalSpacing(1)
        for c, (_, lab, *_) in enumerate(self._FIVE):
            h = QLabel(lab)
            h.setStyleSheet("color:#9fdcca;font-size:6pt;font-weight:900;background:transparent;")
            gen_grid.addWidget(h, 0, c)
        for r, (key, label) in enumerate(MD_CLONE_TARGETS, start=1):
            for c, (mkey, mlab, lo, hi, scale, default) in enumerate(self._FIVE):
                s = QSlider(Qt.Orientation.Horizontal)
                s.setRange(lo, hi)
                s.setValue(max(lo, min(hi, int(round(default / scale)))))
                s.setMinimumWidth(42)
                s.setFixedHeight(12)
                s.setToolTip(f"{mlab} · {mkey} (canonical macro)")
                gen_grid.addWidget(s, r, c)
                self.rows[key][mkey] = (s, scale)
                s.valueChanged.connect(lambda _v, k=key: self._changed(k))
            for c in range(5):
                gen_grid.setColumnStretch(c, 1)
        outer.addLayout(gen_grid)
        outer.addStretch(1)
        self._syncing = False

    def _state(self, target):
        controls = self.rows[target]
        st = {
            "enabled": bool(controls["enabled"].isChecked()),
            "volume": float(controls["volume"].value()) / 100.0,
            "low_db": float(controls["low"].value()),
            "mid_db": float(controls["mid"].value()),
            "high_db": float(controls["high"].value()),
            "source": str(controls["source"].currentText()),
            "depth": float(controls["depth"].value()) / 100.0,
            "attack_ms": 8.0,
            "release_ms": 120.0,
        }
        for mkey, _, _, _, scale, _ in self._FIVE:
            s, sc = controls[mkey]
            st[mkey] = float(s.value()) * sc
        return st

    def _changed(self, target):
        if self._syncing:
            return
        try:
            name = self.host.instrument_selector_dropdown.currentText()
            st = self.host.instrument_param_state.setdefault(name, {})
            clones = st.setdefault("md_clones", {})
            clones[target] = self._state(target)
            try:
                store = getattr(self.host, "_canonical_macro_user_store", None)
                if isinstance(store, dict):
                    store.setdefault(name, {})["md_clones"] = dict(clones)
            except Exception:
                pass
            self.host._on_live_source_changed()
        except Exception:
            pass

    def sync_from_host(self, name=None):
        try:
            if name is None:
                name = self.host.instrument_selector_dropdown.currentText()
            st = ((getattr(self.host, "instrument_param_state", {}) or {}).get(name, {}) or {})
            clones = st.get("md_clones") if isinstance(st.get("md_clones"), dict) else {}
            self._syncing = True
            for key, ctrls in self.rows.items():
                cfg = dict(_md_clone_defaults())
                cfg.update(clones.get(key) or {})
                ctrls["enabled"].setChecked(bool(cfg.get("enabled", False)))
                ctrls["volume"].setValue(max(0, min(200, int(round(float(cfg.get("volume", 1.0)) * 100.0)))))
                ctrls["low"].setValue(max(-18, min(18, int(round(float(cfg.get("low_db", 0.0)))))))
                ctrls["mid"].setValue(max(-18, min(18, int(round(float(cfg.get("mid_db", 0.0)))))))
                ctrls["high"].setValue(max(-18, min(18, int(round(float(cfg.get("high_db", 0.0)))))))
                ctrls["source"].setCurrentText(str(cfg.get("source", "Off") or "Off"))
                ctrls["depth"].setValue(max(0, min(100, int(round(float(cfg.get("depth", 0.0)) * 100.0)))))
                for mkey, _, lo, hi, scale, default in self._FIVE:
                    s, sc = ctrls[mkey]
                    val = float(cfg.get(mkey, default))
                    s.setValue(max(lo, min(hi, int(round(val / sc)))))
        except Exception:
            pass
        finally:
            self._syncing = False


# ---------------------------------------------------------------------------
# MainMDPanel — embedded panel in the main window
# ---------------------------------------------------------------------------

class MainMDPanel(QWidget):
    """Large centered animation with native-size, value-bearing editors."""

    def __init__(self, host, parent=None):
        super().__init__(parent if parent is not None else host)
        self.host = host
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        _pal = self.palette(); _pal.setColor(self.backgroundRole(), QColor("#0b111b")); self.setPalette(_pal)
        self.setStyleSheet("background-color:#0b111b;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.view = MD3DView(self)
        self.view.show()

        # All master-dimensional parameters live on this panel (not the side rails).
        # Four rows of three keep labels and live values readable at normal window widths.
        self.control_rack = QFrame(self)
        self.control_rack.setObjectName("mainDimensionalControlRack")
        self.control_rack.setStyleSheet(
            "QFrame#mainDimensionalControlRack { background:#15172f; border:2px solid #6c55b8; border-radius:10px; }"
            "QLabel { color:#c8f7ed; font-size:8pt; font-weight:900; background:transparent; border:0; }"
            "QLabel[role='value'] { color:#ffd977; font-size:7pt; font-weight:900; }"
        )
        rack = QGridLayout(self.control_rack)
        rack.setContentsMargins(10, 8, 10, 8); rack.setHorizontalSpacing(12); rack.setVerticalSpacing(8)
        self._sliders = []
        self._slider_values = {}
        self._slider_labels = {}
        _defaults = {"gravity":9.8, "restitution":0.8, "rot_hz":0.1, "lo":0.0, "hi":1.0,
                     "up":2.0, "down":0.5, "phase_shift":0.0, "block_ms":12.0, "res_q":10.0, "res_mix":0.0,
                     "stochastic":0.0, "variation":0.0, "fractal_depth":0.0, "lock_ms":0.0,
                     "trigger_response":0.0, "field_rate":0.5}
        for idx, (key, label, lo, hi, scale) in enumerate(NUM_CONTROLS):
            cell = QWidget(self.control_rack)
            cell_lay = QVBoxLayout(cell); cell_lay.setContentsMargins(2, 0, 2, 0); cell_lay.setSpacing(0)
            name_lab = QLabel(label, cell); name_lab.setToolTip(f"Master dimensional parameter · {key}")
            name_lab.setStyleSheet("color:#9fdcca;font-size:7pt;font-weight:800;")
            line = QHBoxLayout(); line.setContentsMargins(0, 0, 0, 0); line.setSpacing(3)
            slider = QSlider(Qt.Orientation.Horizontal, cell); slider.setRange(lo, hi)
            initial = int(round(float(_defaults.get(key, 0.0)) / scale))
            slider.setValue(max(lo, min(hi, initial)))
            value_lab = QLabel(f"{slider.value()*scale:.3g}", cell); value_lab.setProperty("role", "value")
            value_lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_lab.setMinimumWidth(34)
            slider.setMinimumWidth(108)
            slider.setToolTip(f"{label} · stored per instrument")
            base = _role_color(_ROLE_FOR_PARAM.get(key, _ROLE_ORDER[idx % len(_ROLE_ORDER)]))
            _style_role_slider(slider, base, slider.value(), lo, hi)
            slider.valueChanged.connect(lambda v, k=key, sc=scale, lab=value_lab, sl=slider, b=base, l=lo, h=hi:
                                        self._on_param_slider_changed(k, v, sc, lab, sl, b, l, h))
            line.addWidget(slider, 1); line.addWidget(value_lab)
            cell_lay.addWidget(name_lab); cell_lay.addLayout(line)
            cell.setMinimumHeight(48)
            cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            rack.addWidget(cell, idx // 3, idx % 3)
            self._sliders.append((key, slider, scale, base, lo, hi, value_lab))
            self._slider_values[key] = value_lab; self._slider_labels[key] = name_lab
        for col in range(3): rack.setColumnStretch(col, 1)

        # Bottom-side field sliders and the panel/geometric/multidim clone rack.
        # ArcSequencerView reserves this dock's height before drawing its rings,
        # so the sequencer/automator bands never overlap these controls.
        self.top_geo_strip = QFrame(self)
        self.top_geo_strip.setObjectName("mainDimensionalTopGeoStrip")
        self.top_geo_strip.setStyleSheet(
            "QFrame#mainDimensionalTopGeoStrip { background:#121a2c; border:2px solid #4a8ab8; border-radius:8px; }"
        )
        _tg_lay = QHBoxLayout(self.top_geo_strip)
        _tg_lay.setContentsMargins(6, 3, 6, 3)
        _tg_lay.setSpacing(6)
        _tg_lab = QLabel("GEOMETRICS · PKP / EQR / FRACTALLIZER (canonical ratio)")
        _tg_lab.setStyleSheet("color:#9fd4ff;font-size:7pt;font-weight:900;background:transparent;")
        _tg_lay.addWidget(_tg_lab)
        self.sld_top_geometrics = QSlider(Qt.Orientation.Horizontal)
        self.sld_top_geometrics.setRange(0, 1000)
        self.sld_top_geometrics.setValue(500)
        self.sld_top_geometrics.setMinimumWidth(180)
        self.sld_top_geometrics.setToolTip(
            "Top Geometrics master · same combined PKP/EQR/Fractallizer ratio as the main window. "
            "Lives above the step arc so the two never intersect."
        )
        self.sld_top_geometrics.valueChanged.connect(self._on_top_geometrics_changed)
        _tg_lay.addWidget(self.sld_top_geometrics, 1)
        self.top_geo_strip.setMinimumHeight(36)

        self.bottom_dock = QFrame(self)
        self.bottom_dock.setObjectName("mainDimensionalBottomDock")
        self.bottom_dock.setStyleSheet(
            "QFrame#mainDimensionalBottomDock { background:#10172a; border:2px solid #6c55b8; border-radius:10px; }"
        )
        dock_lay = QVBoxLayout(self.bottom_dock)
        dock_lay.setContentsMargins(4, 3, 4, 3)
        dock_lay.setSpacing(2)
        self.bottom_tabs = QTabWidget(self.bottom_dock)
        self.bottom_tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #405074; background:#10172a; }"
            "QTabBar::tab { background:#1b2540; color:#9fdcca; font-size:9pt; font-weight:900; padding:6px 12px; min-height:28px; }"
            "QTabBar::tab:selected { background:#2c3f66; color:#ffd977; }"
        )
        field_page = QWidget(self.bottom_tabs)
        field_page.setStyleSheet("background:#10172a;")
        field_lay = QGridLayout(field_page)
        field_lay.setContentsMargins(6, 4, 6, 4)
        field_lay.setHorizontalSpacing(10)
        field_lay.setVerticalSpacing(1)
        for idx, (key, label, lo, hi, scale) in enumerate(MD_FIELD_CONTROLS):
            cell = QWidget(field_page)
            cell_lay = QVBoxLayout(cell); cell_lay.setContentsMargins(1, 0, 1, 0); cell_lay.setSpacing(0)
            name_lab = QLabel(label, cell)
            name_lab.setStyleSheet("color:#9fdcca;font-size:6pt;font-weight:800;background:transparent;")
            line = QHBoxLayout(); line.setContentsMargins(0, 0, 0, 0); line.setSpacing(3)
            slider = QSlider(Qt.Orientation.Horizontal, cell); slider.setRange(lo, hi)
            initial = int(round(float(_defaults.get(key, 0.0)) / scale))
            slider.setValue(max(lo, min(hi, initial)))
            value_lab = QLabel(f"{slider.value()*scale:.3g}", cell); value_lab.setProperty("role", "value")
            value_lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_lab.setMinimumWidth(34)
            slider.setMinimumWidth(92)
            slider.setToolTip(f"{label} · stored per instrument")
            base = _role_color(_ROLE_FOR_PARAM.get(key, _ROLE_ORDER[idx % len(_ROLE_ORDER)]))
            _style_role_slider(slider, base, slider.value(), lo, hi)
            slider.valueChanged.connect(lambda v, k=key, sc=scale, lab=value_lab, sl=slider, b=base, l=lo, h=hi:
                                        self._on_param_slider_changed(k, v, sc, lab, sl, b, l, h))
            line.addWidget(slider, 1); line.addWidget(value_lab)
            cell_lay.addWidget(name_lab); cell_lay.addLayout(line)
            field_lay.addWidget(cell, idx // 3, idx % 3)
            self._sliders.append((key, slider, scale, base, lo, hi, value_lab))
            self._slider_values[key] = value_lab; self._slider_labels[key] = name_lab
        for col in range(3): field_lay.setColumnStretch(col, 1)
        self.bottom_tabs.addTab(field_page, "STOCHASTIC / LOCK / FRACTAL FIELD")
        self.clone_rack = MDCloneRack(self.host, self.bottom_tabs)
        self.bottom_tabs.addTab(self.clone_rack, "PANEL SYNTH CLONES")
        dock_lay.addWidget(self.bottom_tabs, 1)

        self.overlay = QLabel("Synths Master Engine", self)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.overlay.setVisible(False)
        self.overlay.mousePressEvent = self._open_status
        self._wire_anchors = []
        _panel_btn_css = (
            "QPushButton{background:#1a2f48;color:#9fe8ff;border:2px solid #3d7ea6;"
            "border-radius:8px;padding:10px 14px;font-weight:900;font-size:11pt;}"
            "QPushButton:hover{background:#254a6e;border-color:#7ce7ff;}"
            "QPushButton:pressed{background:#ff9f1c;color:#16110a;}"
        )
        self._btn_toggle = QPushButton("🌀 Multidim Synth", self)
        self._btn_toggle.setToolTip("Open multidimensional synth editor window")
        self._btn_toggle.clicked.connect(lambda: open_multidim_window(self.host))
        self._btn_toggle.setStyleSheet(_panel_btn_css)
        self._btn_toggle.setMinimumHeight(42)
        self._btn_toggle.setMinimumWidth(150)
        # Lower-left Panel Synth editor shortcuts (Script / Domain / Patch)
        self._btn_panel_script = QPushButton("Script editor", self)
        self._btn_panel_domain = QPushButton("Domain editor", self)
        self._btn_panel_patch = QPushButton("Patch editor", self)
        for _b, _tab in (
            (self._btn_panel_script, "script"),
            (self._btn_panel_domain, "domain"),
            (self._btn_panel_patch, "patch"),
        ):
            _b.setStyleSheet(_panel_btn_css)
            _b.setMinimumHeight(42)
            _b.setMinimumWidth(130)
            _b.setToolTip(f"Open Multidim window focused on the {_tab} editor")
            _b.clicked.connect(lambda _=False, t=_tab: self._open_multidim_editor(t))
        self._hover = False; self._ghost_phase = 0.0
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(40)
        self._master_panel = None
        self.live_dj_panel = None
        self.setMinimumSize(self.sizeHint())

    def sizeHint(self):
        """Keep a full animation stage after accounting for real control sizes."""
        rack = self.control_rack.minimumSizeHint()
        strip = self.top_geo_strip.minimumSizeHint()
        dock = self.bottom_dock.minimumSizeHint()
        return QSize(
            max(1280, rack.width() + 12, strip.width() + 12, dock.width() + 12),
            max(36, strip.height()) + max(240, rack.height())
            + 1120 + max(280, dock.height()) + 36,
        )

    def install_live_dj_panel(self, panel, title="🌐 GLOBAL LIVE DJ PANEL"):
        if panel is None:
            return
        try:
            idx = self.bottom_tabs.indexOf(self.clone_rack)
            if idx >= 0:
                self.bottom_tabs.removeTab(idx)
            self.clone_rack.hide()
            self.live_dj_panel = panel
            self.bottom_tabs.insertTab(0, panel, title)
            self.bottom_tabs.setCurrentIndex(0)
            self.setMinimumSize(self.sizeHint())
            self.updateGeometry()
            parent = self.parentWidget()
            refresh = getattr(parent, "_refresh_native_canvas", None)
            if callable(refresh):
                refresh()
        except Exception:
            pass

    def _on_param_slider_changed(self, key, value, scale, value_lab, slider, base, lo, hi):
        _style_role_slider(slider, base, value, lo, hi)
        value_lab.setText(f"{float(value)*scale:.3g}")
        try:
            name = self.host.instrument_selector_dropdown.currentText()
            st = self.host.instrument_param_state.setdefault(name, {})
            st.setdefault("multidim", {})[key] = float(value) * scale
            _mirror_multidim_user(self.host, name)
            self.host._on_live_source_changed()
        except Exception:
            pass

    def _sync_control_values(self, params, user_params):
        user_params = user_params if isinstance(user_params, dict) else {}
        for key, slider, scale, base, lo, hi, value_lab in self._sliders:
            if slider.isSliderDown():
                continue
            try:
                val = float(user_params.get(key, params.get(key, 0.0)))
                raw = max(lo, min(hi, int(round(val / scale))))
                slider.blockSignals(True); slider.setValue(raw); slider.blockSignals(False)
                value_lab.setText(f"{val:.3g}")
                _style_role_slider(slider, base, raw, lo, hi)
            except Exception:
                try: slider.blockSignals(False)
                except Exception: pass

    def set_activity_enabled(self, enabled):
        if not hasattr(self, "_timer"):
            return
        if bool(enabled) and self.isVisible():
            if not self._timer.isActive(): self._timer.start(200)
        else:
            self._timer.stop()

    def _tick(self):
        if not _alive(self):
            self._timer.stop(); return
        if not _alive(self.view):
            return
        self.view.tick(0.04)
        try:
            name = self.host.instrument_selector_dropdown.currentText()
            slot = self.host._instance_slot(name)
            params, seed = self.host._md_params(name, slot)
            user_params = ((getattr(self.host, "instrument_param_state", {}) or {}).get(name, {}) or {}).get("multidim", {})
            self._sync_control_values(params, user_params)
            self.clone_rack.sync_from_host(name)
            self.view.set_params(params, seed, slot)
        except Exception:
            pass
        if self._hover and _alive(self.overlay):
            self._ghost_phase = (self._ghost_phase + 0.08) % (2 * math.pi)
            self.update()

    def enterEvent(self, e):
        self._hover = True; self.overlay.setVisible(True); super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False; self.overlay.setVisible(False); self.update(); super().leaveEvent(e)

    def resizeEvent(self, e):
        W, H = self.width(), self.height()
        strip_h = max(36, self.top_geo_strip.minimumSizeHint().height())
        rack_h = max(240, self.control_rack.minimumSizeHint().height())
        dock_h = max(280, self.bottom_dock.minimumSizeHint().height())
        rack_y = 4 + strip_h + 8
        stage_y = rack_y + rack_h + 8
        dock_y = max(stage_y + 1120, H - dock_h - 5)
        self.top_geo_strip.setGeometry(6, 4, max(0, W - 12), strip_h)
        self.control_rack.setGeometry(6, rack_y, max(0, W - 12), rack_h)
        self.bottom_dock.setGeometry(6, dock_y, max(0, W - 12), max(0, H - dock_y - 5))
        self.view.setGeometry(0, stage_y, W, max(1120, dock_y - stage_y - 8))
        ow = min(260, int(W * 0.60)); oh = 36
        self.overlay.setGeometry(W // 2 - ow // 2, self.view.geometry().center().y() - oh // 2, ow, oh)
        # R41.2i: enlarged Panel Synth editor buttons — lower left of multidim panel
        try:
            btn_h, gap, x0 = 42, 6, 8
            y0 = max(stage_y + 12, dock_y - btn_h - 10)
            x = x0
            for _b in (
                getattr(self, "_btn_toggle", None),
                getattr(self, "_btn_panel_script", None),
                getattr(self, "_btn_panel_domain", None),
                getattr(self, "_btn_panel_patch", None),
            ):
                if _b is None:
                    continue
                bw = max(130, _b.minimumWidth())
                _b.setGeometry(x, y0, bw, btn_h)
                _b.show()
                _b.raise_()
                x += bw + gap
        except Exception:
            pass
        super().resizeEvent(e)

    def _open_multidim_editor(self, which="script"):
        """Open MultidimWindow and surface the panel synth editor (script/domain/patch)."""
        try:
            w = open_multidim_window(self.host)
            # Matrix / form editors live on the scroll side; raise window is enough.
            # Future: scroll to MultidimControlMatrix section by objectName.
            if w is not None:
                w.raise_(); w.activateWindow()
                if hasattr(w, "engine_tabs") and which == "geometrics":
                    for i in range(w.engine_tabs.count()):
                        if "GEOMETRIC" in str(w.engine_tabs.tabText(i)).upper():
                            w.engine_tabs.setCurrentIndex(i)
                            break
        except Exception as _exc:
            print(f"[MainMDPanel] open editor: {_exc}")

    def _on_top_geometrics_changed(self, value):
        """Forward top geometric master to the host main-window combined control when present."""
        try:
            host = self.host
            master = getattr(host, "slider_geometrics_master", None)
            if master is not None:
                master.blockSignals(True)
                master.setValue(int(value))
                master.blockSignals(False)
                if hasattr(host, "_on_geometrics_master_changed"):
                    host._on_geometrics_master_changed(int(value))
            elif hasattr(host, "_on_geometrics_master_changed"):
                host._on_geometrics_master_changed(int(value))
        except Exception:
            pass


    def paintEvent(self, e):
        with owned_painter(self) as qp:
            if qp is None:
                return
            try:
                qp.setRenderHint(QPainter.RenderHint.Antialiasing)
                qp.fillRect(self.rect(), QColor("#0b111b"))
                if self._hover and _alive(self.overlay):
                    alpha = int(100 + 60 * math.sin(self._ghost_phase)); r = self.overlay.geometry()
                    g = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
                    g.setColorAt(0.0, QColor(20, 100, 180, alpha)); g.setColorAt(1.0, QColor(0, 200, 160, alpha))
                    qp.fillRect(r, QBrush(g)); qp.setPen(QColor(200, 240, 255, alpha + 40))
                    qp.setFont(QFont("Sans", 13, QFont.Weight.Bold)); qp.drawText(r, Qt.AlignmentFlag.AlignCenter, "Synths Master Engine")
            finally:
                if qp.isActive(): qp.end()

    def wheelEvent(self, e): e.ignore()

    def _open_status(self, _e=None):
        try:
            if not _alive(self._master_panel): self._master_panel = SynthsMasterPanel(self.host, self)
            if not self._master_panel.isVisible(): self._master_panel.show()
            self._master_panel.raise_()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ArcSequencerView — ring of step wedges wrapping around the MD sphere
# ---------------------------------------------------------------------------

import weakref as _weakref
from math import sin, cos, radians, degrees, hypot, atan2, pi as _PI
from PyQt6.QtCore import pyqtSignal

_ARC_WIDTH   = 86   # wide enough for real step/automation buttons
_ARC_IN_PAD  = 18
_GAP_DEG     = 1.6

_COL_OFF_BG   = QColor(18, 36, 36)
_COL_OFF_BD   = QColor(40, 80, 80)
_COL_ON_BG    = QColor(0, 170, 150, 150)  # More translucent green background
_COL_ON_BD    = QColor(0, 212, 190)
_COL_HEAD_BG  = QColor(255, 140, 0)
_COL_HEAD_BD  = QColor(255, 215, 0)
_COL_TEXT_OFF = QColor(80, 160, 150)
_COL_TEXT_ON  = QColor(220, 255, 250)
_COL_TEXT_HD  = QColor(255, 230, 100)


class ArcStepLayout(QLayout):
    """Lay real step/automation buttons along a half-circle arc band."""

    def __init__(self, parent, band):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.band = band

    def addItem(self, item):
        self._items.append(item)

    def addWidget(self, widget, stretch=0):
        if widget is None:
            return
        self.addChildWidget(widget)
        self.addItem(QWidgetItem(widget))

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return False

    def heightForWidth(self, _width):
        return 0

    def minimumSize(self):
        return QSize(0, 0)

    def sizeHint(self):
        return QSize(0, 0)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect)

    def _do_layout(self, rect):
        band = self.parentWidget()
        host = getattr(band, "arc_host", None)
        if host is None or not self._items:
            return
        try:
            cx, cy, rx, ry, start, end, thickness = host._band_arc(self.band)
        except Exception:
            return
        n = len(self._items)
        span = abs(math.radians(end - start))
        arc_len = max(1.0, span * max(rx, ry))
        per_lane = max(1, int(arc_len / 104.0))
        lanes = max(1, int(math.ceil(n / per_lane)))
        for i, item in enumerate(self._items):
            child = item.widget()
            if child is None or not _alive(child):
                continue
            lane = i // per_lane
            lane_i = i % per_lane
            lane_n = min(per_lane, n - lane * per_lane)
            t = 0.5 if lane_n <= 1 else lane_i / float(lane_n - 1)
            ang = math.radians(start + (end - start) * t)
            lane_off = (lane - (lanes - 1) / 2.0) * 15.0
            lane_rx, lane_ry = rx + lane_off, ry + lane_off
            x = cx + lane_rx * math.cos(ang) - band.x()
            y = cy - lane_ry * math.sin(ang) - band.y()
            bw = min(108.0, max(86.0, arc_len / max(1, lane_n) * 0.82))
            # Real step and automation buttons are 58 px tall.  A 54 px
            # geometry silently clips their top/bottom even when the band mask
            # is correct, so reserve a little breathing room around them.
            bh = 66.0
            center = host._center_rect()
            side_pad = bw / 2.0 + 5.0
            x_lo = center.left() + side_pad
            x_hi = center.right() - side_pad
            if x_hi < x_lo:
                x_lo, x_hi = bw / 2.0 + 4.0, band.width() - bw / 2.0 - 4.0
            x = min(max(x, x_lo), x_hi)
            y = min(max(y, bh / 2.0 + 4.0), max(bh / 2.0 + 4.0, band.height() - bh / 2.0 - 4.0))
            try:
                child.setMinimumSize(0, 0)
                child.setMaximumSize(16777215, 16777215)
                child.setGeometry(int(x - bw / 2), int(y - bh / 2), int(bw), int(bh))
            except RuntimeError:
                continue
        try:
            band.setMask(host._band_mask(band))
        except Exception:
            pass


class _ArcBand(QWidget):
    def __init__(self, host, band):
        super().__init__(host)
        self.arc_host = host
        self.band = band
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._arc_layout = ArcStepLayout(self, band)
        self.setLayout(self._arc_layout)

    def wheelEvent(self, e):
        e.ignore()


class ArcSequencerView(QWidget):
    """Double-arc sequencer/automator wrapped around the MD sphere.

    The real sequencer buttons ride the upper arc and the real automation
    buttons ride the lower arc.  The left/right areas are live containers for
    existing geometric-synth panels, so the ring level is no longer empty.
    """

    stepClicked = pyqtSignal(int)

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self._host_ref = _weakref.ref(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        _pal = self.palette()
        _pal.setColor(self.backgroundRole(), QColor("#080f18"))
        self.setPalette(_pal)
        self.setStyleSheet("background-color: #080f18;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Native wide workspace, independent of the screen. Outer panes scroll
        # instead of reducing the central sphere to a thin column.
        self._md_intended_width = 2800
        self._md_intended_height = 1720
        self.setMinimumSize(self._md_intended_width, self._md_intended_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # state
        self._n    = 16
        self._on   = [False] * 16
        self._amp  = [1.0]   * 16
        self._head = -1
        self._pulse = 0.0

        # embed MD sphere in centre
        try:
            self._md = MainMDPanel(host, self)
        except Exception:
            self._md = None
        self._refresh_native_canvas()

        # real button bands: upper = sequencer, lower = automator
        self.step_band = _ArcBand(self, "top")
        self.auto_band = _ArcBand(self, "bottom")

        # live side panels (populated by groovebox with existing UI groups)
        self.left_side = self._make_side_panel("left")
        self.left_layout = self.left_side._content_layout
        self.right_side = self._make_side_panel("right")
        self.right_layout = self.right_side._content_layout
        # Parameter controls were moved into MainMDPanel's labelled rack.
        # The old left/right rails now contain only the four geometric editors.
        self._param_sliders = {}
        self._syncing_params = False

        # 100 ms state pull
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(100)
        self._sync_timer.timeout.connect(self.update_from_host)
        self._sync_timer.start()

        # 40 ms pulse animation
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(40)
        self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start()

    def _refresh_native_canvas(self):
        if _alive(self._md):
            native = self._md.sizeHint()
            self._md_intended_width = max(2800, native.width() + 1120)
            self._md_intended_height = max(1720, native.height())
        self.setMinimumSize(self._md_intended_width, self._md_intended_height)
        self.updateGeometry()

    def sizeHint(self):
        return QSize(self._md_intended_width, self._md_intended_height)

    def set_activity_enabled(self, enabled):
        active = bool(enabled) and self.isVisible()
        if active:
            if not self._sync_timer.isActive(): self._sync_timer.start(100)
            if not self._pulse_timer.isActive(): self._pulse_timer.start(40)
        else:
            self._sync_timer.stop()
            self._pulse_timer.stop()
        md_panel = getattr(self, "_md", None)
        setter = getattr(md_panel, "set_activity_enabled", None)
        if callable(setter):
            setter(active)

    def _host(self):
        return self._host_ref()

    def _prepare_side_widget(self, widget):
        try:
            widget.setMinimumWidth(520)
            widget.setMaximumWidth(2800)
            lay = widget.layout()
            if lay is not None:
                lay.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
            for lab in widget.findChildren(QLabel):
                lab.setWordWrap(True)
        except Exception:
            pass
        return widget

    def _sync_side_content(self, panel):
        try:
            content = panel._content
            lay = panel._content_layout
            lay.invalidate(); lay.activate()
            hint = lay.sizeHint()
            content.setMinimumWidth(max(panel.width(), hint.width(), 320))
            content.setMinimumHeight(max(panel.height(), hint.height()))
            content.resize(content.minimumSize())
        except Exception:
            pass

    def add_left_widget(self, widget):
        self._prepare_side_widget(widget)
        self.left_layout.insertWidget(max(0, self.left_layout.count() - 1), widget)
        self._sync_side_content(self.left_side)
        return widget

    def add_right_widget(self, widget):
        self._prepare_side_widget(widget)
        self.right_layout.insertWidget(max(0, self.right_layout.count() - 1), widget)
        self._sync_side_content(self.right_side)
        return widget

    def _make_side_panel(self, side):
        panel = QWidget(self)
        panel.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        content = QWidget(panel)
        content.setStyleSheet("background: transparent;")
        content.setMinimumWidth(0)
        content.setMaximumWidth(805)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(4)
        lay.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        lay.addStretch(1)
        scroll = QScrollArea(panel)
        scroll.setObjectName(f"{side}SynthLaneScroll")
        scroll.setWidgetResizable(False)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:0; } QScrollBar:vertical { width:10px; background:#101827; } QScrollBar::handle:vertical { background:#536b8a; min-height:28px; border-radius:4px; }")
        scroll.setWidget(content)
        content.setMinimumSize(max(1, content.sizeHint().width()), max(1, content.sizeHint().height()))
        outer.addWidget(scroll, 1)
        panel._content_layout = lay
        panel._scroll = scroll
        panel._content = content
        panel.side = side
        return panel

    def _build_param_rails(self):
        header = QLabel("MD PARAMETERS · OT ROLE COLORS")
        header.setStyleSheet("color:#b8f7e6; font-size:8pt; font-weight:900;")
        self.left_layout.addWidget(header)
        left_n = (len(NUM_CONTROLS) + 1) // 2
        for idx, (key, label, lo, hi, scale) in enumerate(NUM_CONTROLS):
            role = _ROLE_FOR_PARAM.get(key, _ROLE_ORDER[idx % len(_ROLE_ORDER)])
            base = _role_color(role)
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_lay = QVBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(1)
            lab = QLabel(label)
            lab.setStyleSheet(
                f"color:{_rescale_pt(base, 0.75).lighter(115).name()};"
                " font-size:7pt; font-weight:800;"
            )
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(lo, hi)
            dv = {"gravity": int(9.8 / scale), "restitution": int(0.8 / scale)}.get(key, 0)
            sl.setValue(dv)
            sl.setToolTip(f"{label} · {str(role).replace('_', ' ')}")
            sl.valueChanged.connect(
                lambda v, k=key, sc=scale, s=sl, lo_=lo, hi_=hi, b=base:
                self._on_param_slider_changed(k, v, sc, s, lo_, hi_, b)
            )
            row_lay.addWidget(lab)
            row_lay.addWidget(sl)
            target = self.left_layout if idx < left_n else self.right_layout
            target.addWidget(row)
            self._param_sliders[key] = (sl, scale, base, lo, hi, lab)
            self._apply_slider_color(sl, base, sl.value(), lo, hi)
        self.left_layout.addStretch(1)
        self.right_layout.addStretch(1)

    def _apply_slider_color(self, slider, base, value, lo, hi):
        _style_role_slider(slider, base, value, lo, hi)

    def _on_param_slider_changed(self, key, value, scale, slider, lo, hi, base):
        self._apply_slider_color(slider, base, value, lo, hi)
        if self._syncing_params:
            return
        host = self._host()
        if host is None:
            return
        try:
            name = host.instrument_selector_dropdown.currentText()
            st = host.instrument_param_state.setdefault(name, {})
            st.setdefault("multidim", {})[key] = float(value) * scale
            _mirror_multidim_user(host, name)
            host._on_live_source_changed()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Arc geometry                                                       #
    # ------------------------------------------------------------------ #

    def _content_width(self):
        # The parent preserves the native canvas, including on small displays.
        return max(1.0, float(self.width()))

    def _content_left(self):
        return (self.width() - self._content_width()) / 2.0

    def _side_width(self):
        # Symmetric native editor rails; surplus width belongs to the animation.
        width = max(1.0, self._content_width())
        return max(520, min(560, int(width * 0.20)))

    def _center_rect(self):
        """Region between the side panels; the sphere lives here and the ring frames it."""
        side_w = self._side_width()
        x0 = self._content_left() + side_w
        return QRectF(x0, 0.0, max(120.0, self._content_width() - 2.0 * side_w), float(self.height()))

    def _stage_rect(self):
        """One coordinate source for the sphere, arc, glow and click geometry."""
        if _alive(self._md) and _alive(self._md.view):
            rect = QRectF(self._md.view.geometry())
            rect.translate(self._md.x(), self._md.y())
            return rect
        return self._center_rect()

    def _ring_reserve(self):
        return max(0.0, self.height() - self._stage_rect().height())

    def _ring_cy(self):
        return self._stage_rect().center().y()

    def _ring_radii(self):
        c = self._stage_rect()
        h = max(180.0, c.height())
        return (max(80.0, c.width() / 2.0 - _ARC_WIDTH / 2.0 - 4.0),
                max(60.0, h / 2.0 - _ARC_WIDTH / 2.0 - 6.0))

    def _band_arc(self, band):
        cx = self._content_left() + self._content_width() / 2.0
        cy = self._ring_cy()
        rx, ry = self._ring_radii()
        if band == "top":
            start, end = 160.0, 20.0
        else:
            start, end = 200.0, 340.0
        return cx, cy, rx, ry, start, end, _ARC_WIDTH

    def _band_rect(self, band):
        # The arc's rectangular widget used to hug only the painted ring.  The
        # step/automation buttons are taller and wider than that path, so Qt
        # clipped the corners and text at the parent boundary.  Give the band
        # the full host coordinate space and use a precise mask below instead.
        return QRect(0, 0, max(1, self.width()), max(1, self.height()))

    def _band_mask(self, band_widget):
        """Arc-shaped region (band-local) so the band only takes clicks on the arc itself."""
        cx, cy, rx, ry, start, end, thickness = self._band_arc(band_widget.band)
        off = band_widget.geometry().topLeft()
        pad = 18.0
        rox, roy = rx + thickness / 2.0 + pad, ry + thickness / 2.0 + pad
        rix, riy = max(1.0, rx - thickness / 2.0 - pad), max(1.0, ry - thickness / 2.0 - pad)
        steps = 48
        pts = []
        for i in range(steps + 1):
            a = math.radians(start + (end - start) * i / steps)
            pts.append(QPoint(int(cx + rox * math.cos(a)) - off.x(), int(cy - roy * math.sin(a)) - off.y()))
        for i in range(steps, -1, -1):
            a = math.radians(start + (end - start) * i / steps)
            pts.append(QPoint(int(cx + rix * math.cos(a)) - off.x(), int(cy - riy * math.sin(a)) - off.y()))
        region = QRegion(QPolygon(pts))
        try:
            layout = band_widget.layout()
            for i in range(layout.count()):
                item = layout.itemAt(i)
                child = item.widget() if item is not None else None
                if child is not None and _alive(child) and child.isVisible():
                    region = region.united(QRegion(child.geometry().adjusted(-5, -5, 5, 5)))
        except Exception:
            pass
        # Arc widgets sit above the master widget. Do not let their masks steal
        # editing clicks, even where a decorative band grazes a control.
        if _alive(self._md):
            for control in (
                self._md.top_geo_strip, self._md.control_rack, self._md.bottom_dock,
                self._md._btn_toggle, self._md._btn_panel_script,
                self._md._btn_panel_domain, self._md._btn_panel_patch,
            ):
                rect = control.geometry().translated(self._md.pos() - off)
                region = region.subtracted(QRegion(rect.adjusted(-2, -2, 2, 2)))
        return region

    def _oval_radii(self):
        rx, ry = self._ring_radii()
        return max(10, int(rx - _ARC_WIDTH)), max(10, int(ry - _ARC_WIDTH)), int(rx), int(ry)

    def _md_oval_geometry(self):
        stage = self._stage_rect()
        return stage.center().x(), stage.center().y(), stage.width() / 2.0, stage.height() / 2.0

    def _tick_pulse(self):
        if not _alive(self):
            self._pulse_timer.stop()
            return
        self._pulse = (self._pulse + 0.18) % (2 * _PI)
        if self._head >= 0:
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_count = getattr(self, "_resize_count", 0) + 1
        h = float(self.height())
        if _alive(self._md):
            # The sphere stays inside the center region. It used to span past the whole view and
            # sit on top, covering (dimming, and eating clicks for) the side panels and arc bands.
            self._md.setGeometry(self._center_rect().toRect())
        for band in (self.step_band, self.auto_band):
            band.setGeometry(self._band_rect(band.band))
            band.layout().activate()
            band.setMask(self._band_mask(band))
        side_w = int(self._side_width())
        side_h = max(280, int(h - 16))
        side_y = 8
        left_x = int(self._content_left()) + 6
        right_x = int(self._content_left() + self._content_width() - side_w) + 6
        self.left_side.setGeometry(left_x, int(side_y), side_w - 12, side_h)
        self.right_side.setGeometry(right_x, int(side_y), side_w - 12, side_h)
        self._sync_side_content(self.left_side)
        self._sync_side_content(self.right_side)
        if _alive(self._md):
            self._md.show(); self._md.lower()
        # Side rails sit below the arc overlays.  The previous order raised the
        # side panels last, covering the left/right ends of both arcs and making
        # steps/automation look truncated on otherwise valid geometry.
        self.left_side.raise_(); self.right_side.raise_()
        self.step_band.raise_(); self.auto_band.raise_()
        self.left_side.show(); self.right_side.show()
        self.step_band.show(); self.auto_band.show()
        self.update()

    def refresh_band_layouts(self):
        """Reflow both real button arcs and rebuild their masks after step-count changes."""
        for band in (self.step_band, self.auto_band):
            try:
                band.layout().invalidate()
                band.layout().activate()
                band.setMask(self._band_mask(band))
                band.update()
            except Exception:
                pass
        self.update()

    def update_from_host(self):
        if not _alive(self):
            self._sync_timer.stop()
            return
        host = self._host()
        if host is None:
            return
        try:
            cur = host.instrument_selector_dropdown.currentText()
            mem = host._current_sequence_mem(cur)
            self._n   = max(1, len(mem.get("steps", [])) or 16)
            self._on  = list(mem.get("steps", [False] * self._n))
            self._amp = list(mem.get("amplitudes", [1.0] * self._n))
        except Exception:
            pass
        try:
            self._head = int(getattr(host, "_playhead_step", -1) or -1)
        except Exception:
            self._head = -1
        try:
            name = host.instrument_selector_dropdown.currentText()
            slot = host._instance_slot(name)
            p, _seed = host._md_params(name, slot)
            _u = ((getattr(host, "instrument_param_state", {}) or {}).get(name, {}) or {}).get("multidim")
            _u = _u if isinstance(_u, dict) else {}
            self._syncing_params = True
            for key, (sl, scale, base, lo, hi, _lab) in self._param_sliders.items():
                try:
                    if sl.isSliderDown():
                        continue
                    _val = _u.get(key, p.get(key, 0.0))
                    sl.setValue(int(round(float(_val) / scale)))
                    self._apply_slider_color(sl, base, sl.value(), lo, hi)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._syncing_params = False
        try:
            self.update()
        except RuntimeError:
            pass

    def _draw_arc_band(self, qp, band, fill, border):
        cx, cy, rx, ry, start, end, thickness = self._band_arc(band)
        rox, roy = rx + thickness / 2.0, ry + thickness / 2.0
        rix, riy = rx - thickness / 2.0, ry - thickness / 2.0
        steps = 72
        pts = []
        for i in range(steps + 1):
            a = math.radians(start + (end - start) * i / steps)
            pts.append(QPointF(cx + rox * math.cos(a), cy - roy * math.sin(a)))
        for i in range(steps, -1, -1):
            a = math.radians(start + (end - start) * i / steps)
            pts.append(QPointF(cx + rix * math.cos(a), cy - riy * math.sin(a)))
        qp.setPen(QPen(border, 1.4))
        qp.setBrush(QBrush(fill))
        qp.drawPolygon(QPolygonF(pts))

    def paintEvent(self, event):
        with owned_painter(self) as qp:
            if qp is None:
                return
            try:
                qp.setRenderHint(QPainter.RenderHint.Antialiasing)
                w, h = self.width(), self.height()
                cx, _cy0, rx, ry, _s0, _e0, _t0 = self._band_arc("top")
                cy = self._ring_cy()

                glow_rx = rx - _ARC_WIDTH + _ARC_IN_PAD * 0.6
                glow_ry = ry - _ARC_WIDTH + _ARC_IN_PAD * 0.6
                grad = QRadialGradient(QPointF(cx, cy), max(60.0, max(glow_rx, glow_ry)))
                grad.setColorAt(0.0, QColor(0, 210, 190, 55))
                grad.setColorAt(0.55, QColor(0, 160, 140, 28))
                grad.setColorAt(1.0,  QColor(0, 0, 0, 0))
                qp.fillRect(QRectF(cx - glow_rx, cy - glow_ry, glow_rx * 2, glow_ry * 2), QBrush(grad))

                self._draw_arc_band(qp, "top", _COL_ON_BG, _COL_ON_BD)
                self._draw_arc_band(qp, "bottom", QColor(255, 140, 0, 30), QColor(255, 190, 70, 120))

                qp.setFont(QFont("Sans", 9, QFont.Weight.Bold))
                qp.setPen(_COL_ON_BD)
                qp.drawText(QRectF(cx - 120, cy - ry - 22, 240, 18),
                            Qt.AlignmentFlag.AlignCenter, "SEQUENCER ARC")
                qp.setPen(QColor(255, 190, 70, 180))
                qp.drawText(QRectF(cx - 120, cy + ry + 4, 240, 18),
                            Qt.AlignmentFlag.AlignCenter, "AUTOMATOR ARC")
            finally:
                if qp.isActive():
                    qp.end()

    def wheelEvent(self, e):
        e.ignore()

    def mousePressEvent(self, e):
        cx, cy, rx, ry, start, end, thickness = self._band_arc("top")
        dx = e.position().x() - cx
        dy = e.position().y() - cy
        norm_out = (dx / max(1.0, rx + thickness / 2.0 + 6)) ** 2 + (dy / max(1.0, ry + thickness / 2.0 + 6)) ** 2
        norm_in = (dx / max(1.0, rx - thickness / 2.0 - 6)) ** 2 + (dy / max(1.0, ry - thickness / 2.0 - 6)) ** 2
        if norm_out <= 1.0 and norm_in >= 1.0:
            ang = math.degrees(math.atan2(-dy / max(1.0, ry), dx / max(1.0, rx))) % 360.0
            lo, hi = min(start, end), max(start, end)
            if lo <= ang <= hi:
                t = (start - ang) / (start - end) if start != end else 0.0
                idx = int(round(max(0.0, min(1.0, t)) * max(0, self._n - 1)))
                self.stepClicked.emit(idx)
                e.accept()
                return
        super().mousePressEvent(e)

    def closeEvent(self, e):
        self._sync_timer.stop()
        self._pulse_timer.stop()
        super().closeEvent(e)
