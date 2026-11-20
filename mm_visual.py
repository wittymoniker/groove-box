"""mm_visual.py: the Mod Matrix stage. A 3.5-D grid (rows x time x depth, plus each row's live value lifting
its ribbon) with moving GOAVA shapes, and L-system branches growing inside and outside them.

Restrained on purpose: about 0.19758 of the Multidim synth's showiness (low alpha, thin lines, slow motion).
It paints only while visible, at about 24 fps, and reads the matrix's last outputs (never evaluates it).
"""
from __future__ import annotations
import math
import sys
import time

SHOW = 0.19758          # showiness relative to the Multidim synth
HIST = 72               # samples of history per row ribbon
MEUM = 1.1975807343385265     # Metta M


def _goava(i, t, nums):
    """GOAVA getNote when the app exposes it, else the same irrational-stream shape (MEUM powers, phi steps)."""
    for m in (sys.modules.get("groovebox"), sys.modules.get("__main__")):
        f = getattr(m, "goava_get_note", None) if m is not None else None
        if callable(f):
            try:
                return float(f(float(i + 1), t * MEUM, nums))
            except Exception:
                break
    phi = 1.6180339887
    return math.sin(t * phi + i * phi * phi) * math.cos(t / phi + i * MEUM) + 0.3 * math.sin(3 * t + i)


def _qc(r, g, b, alpha):
    """QColor with the alpha clamped to 0..255 (an out-of-range alpha makes Qt draw black)."""
    from PyQt6.QtGui import QColor
    return QColor(int(r), int(g), int(b), max(0, min(255, int(alpha))))


def _lsystem(depth=3):
    s = "X"
    for _ in range(depth):
        s = "".join({"X": "F[+X][-X]FX", "F": "FF"}.get(c, c) for c in s)
    return s


_LS = _lsystem(3)


def make_widget(app, parent=None, mirror=False, follow=None):
    """mirror: draw reflected (for the left-side mirror). follow(): optional dict from the Multidim synth
    {"speed", "swing", "tilt", "glow", "focus"} so the stage moves with that window's instrument and macros."""
    from PyQt6.QtCore import QTimer, QPointF, Qt
    from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath, QLinearGradient
    from PyQt6.QtWidgets import QWidget

    class Stage(QWidget):
        def __init__(self):
            super().__init__(parent)
            self.setMinimumHeight(190)
            self.setToolTip("Mod Matrix stage: each row is a ribbon in a 3.5-D grid (time × depth × live value). Canonical rows "
                            "glow cyan, user rows amber. GOAVA shapes drift through it; L-systems grow inside and outside them. "
                            "The floor tilts with the governor depth. Right-drag: routing side rotates the reroute poles (left/right) and "
                            "sets the perspective magnitude (up/down); perspective side turns the perspective view.")
            self.hist = {}; self.t0 = time.monotonic(); self.mirror = bool(mirror); self.follow = follow
            self.flip_v = False; self._phase = 0.0; self._last = time.monotonic()
            self.timer = QTimer(self); self.timer.setInterval(42); self.timer.timeout.connect(self._tick); self.timer.start()
            try:
                self.nums = list(app.get_seed_values(t_value=0.0) or [])[:8] or [MEUM]
            except Exception:
                self.nums = [MEUM]

        # GROOVEBOX_R123_MODPATH_RIGHT_DRAG_20261119: right-drag on a Mod Path Bay stage drags the other
        # Mod Path features. Routing stage (left): left/right rotates every reroute pole, up/down sets the
        # perspective magnitude. Perspective stage (right): drag turns the perspective view (az / el).
        def mousePressEvent(self, e):
            if __import__("touch_compat").right_like(e):
                self._rlast = e.position(); e.accept(); return
            # touch fallbacks: sticky Alt-drag = right-drag at once; touch-and-hold then drag = right-drag
            try:
                import touch_compat
                if getattr(self, "_hold_g", None) is None:
                    self._hold_g = touch_compat.HoldGesture(self, app, lambda p: setattr(self, "_rlast", p))
                if self._hold_g.press(e):
                    self._rlast = e.position(); e.accept(); return
            except Exception:
                pass
            super().mousePressEvent(e)

        def mouseMoveEvent(self, e):
            if getattr(self, "_hold_g", None) is not None:
                self._hold_g.move(e)
            last = getattr(self, "_rlast", None)
            if last is None:
                return super().mouseMoveEvent(e)
            d = e.position() - last; self._rlast = e.position()
            try:
                import mm_fields
                st = mm_fields.settings(app)
                dx = -d.x() if self.mirror else d.x()
                if self.mirror:
                    ang = dx * 0.012
                    ca, sa = math.cos(ang), math.sin(ang)
                    for q in st.get("points") or []:
                        q[0], q[1] = q[0] * ca - q[1] * sa, q[0] * sa + q[1] * ca
                    st["mag"] = round(max(-1.0, min(1.0, float(st.get("mag", 0.0)) - d.y() * 0.005)), 3)
                else:
                    st["az"] = (float(st.get("az", 0.0)) + dx * 0.012) % (2 * math.pi)
                    st["el"] = max(-1.5, min(1.5, float(st.get("el", 0.35)) - d.y() * 0.012))
            except Exception:
                pass
            e.accept(); self.update()

        def mouseReleaseEvent(self, e):
            self._rlast = None
            if getattr(self, "_hold_g", None) is not None:
                self._hold_g.release()
            super().mouseReleaseEvent(e)

        def contextMenuEvent(self, e):
            e.accept()

        def _tick(self):
            if not self.isVisible():
                return
            try:
                import mod_matrix as mm
                rs = mm.rows(app)
                outs = getattr(app, "_r101_mm_out", None) or getattr(app, "_r101_mm_raw", None) or []
                for i in range(len(rs)):
                    h = self.hist.setdefault(i, [0.5] * HIST)
                    h.append(float(outs[i]) if i < len(outs) else 0.5); del h[0]
                for k in [k for k in self.hist if k >= len(rs)]:
                    self.hist.pop(k)
            except Exception:
                pass
            self.update()

        def _proj(self, x, y, z, W, H, tilt):
            """x 0..1 across, y 0..1 depth (into the screen), z lift 0..1 -> screen point (perspective)."""
            d = 1.0 + 1.8 * y
            sx = W * 0.5 + (x - 0.5) * W * 0.92 / d
            sy = H * (0.30 + 0.62 / d) - z * H * 0.30 / d - tilt * y * H * 0.06
            return QPointF(sx, sy)

        def paintEvent(self, _ev):
            W, H = self.width(), self.height()
            fo = {}
            if callable(self.follow):
                try: fo = self.follow() or {}
                except Exception: fo = {}
            now = time.monotonic(); self._phase += (now - self._last) * float(fo.get("speed", 1.0)); self._last = now
            t = self._phase
            p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            g = QLinearGradient(0, 0, 0, H); g.setColorAt(0, QColor(6, 10, 18)); g.setColorAt(1, QColor(12, 22, 34)); p.fillRect(self.rect(), g)
            if self.mirror:
                p.translate(W, 0); p.scale(-1, 1)
            if self.flip_v:
                p.translate(0, H); p.scale(1, -1)
            view = getattr(app, "_r101_governor_view", None) or {}
            tilt = float(view.get("depth", 1.0)) + float(fo.get("tilt", 0.0)); a = int(255 * SHOW * float(fo.get("glow", 1.0)))
            a = max(80, min(170, int(a * 2.2))); self._swing = float(fo.get("swing", 1.0)); focus = fo.get("focus")
            # floor grid (3-D) with a slow drift (the half dimension: time scrolls through depth)
            # slow starfield (seeded positions, gentle twinkle) under the grid
            # R102 speed: stars grouped into 4 twinkle levels (one brush each), grid drawn in one call
            p.setPen(Qt.PenStyle.NoPen); levels = ([], [], [], [])
            for k in range(70):
                tw = 0.5 + 0.5 * math.sin(t * 0.6 + k)
                levels[min(3, int(tw * 4))].append(QPointF(((k * 7919) % 997) / 997.0 * W, ((k * 104729) % 991) / 991.0 * H * 0.55))
            for lv, pts_ in enumerate(levels):
                if not pts_: continue
                tw = (lv + 0.5) / 4.0; rr = 0.8 + 0.8 * tw
                p.setBrush(_qc(200, 220, 255, int(40 + 90 * tw)))
                for q in pts_: p.drawEllipse(q, rr, rr)
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(_qc(80, 150, 200, int(a * 0.8))); pen.setWidthF(0.9); p.setPen(pen)
            drift = (t * 0.04) % (1.0 / 12); from PyQt6.QtCore import QLineF as _QL; grid = []
            for j in range(13):
                y = j / 12.0 + drift
                if y > 1: continue
                grid.append(_QL(self._proj(0, y, 0, W, H, tilt), self._proj(1, y, 0, W, H, tilt)))
            for i in range(17):
                x = i / 16.0; grid.append(_QL(self._proj(x, 0, 0, W, H, tilt), self._proj(x, 1, 0, W, H, tilt)))
            p.drawLines(grid)
            # row ribbons
            try:
                import mod_matrix as mm, mm_governor as G
                rs = mm.rows(app)
            except Exception:
                rs = []; G = None
            n = max(1, len(rs))
            for i, row in enumerate(rs):
                h = self.hist.get(i)
                if not h: continue
                canon = G.is_canonical_row(row) if G else False
                col = _qc(90, 220, 240, int(a * 2.2)) if canon else _qc(250, 190, 90, int(a * 2.2))
                if not row.get("enabled", True): col.setAlpha(max(0, min(255, int(a * 0.6))))
                foc = bool(focus) and str(focus) in str(row.get("target", ""))
                if foc: col.setAlpha(max(0, min(255, int(a * 3.6))))
                glow = QColor(col); glow.setAlpha(max(0, min(255, int(col.alpha() * 0.28))))
                gp = QPen(glow); gp.setWidthF(7.0 if foc else 5.0); gp.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen = QPen(col); pen.setWidthF(2.4 if foc else 1.6); p.setPen(pen)
                x = (i + 0.5) / n; path = QPainterPath()
                for k, v in enumerate(h):
                    pt = self._proj(x, 1 - k / (HIST - 1), v, W, H, tilt)
                    path.moveTo(pt) if k == 0 else path.lineTo(pt)
                p.setPen(gp); p.drawPath(path)            # soft glow pass
                p.setPen(pen); p.drawPath(path)
                head = self._proj(x, 0, h[-1], W, H, tilt); p.setBrush(col); p.drawEllipse(head, 2.2, 2.2); p.setBrush(Qt.BrushStyle.NoBrush)
            # GOAVA shapes: 1-D trace ring, 2-D phase portrait, 3-D space curve projected; drifting through the grid
            for s in range(3):
                cx = 0.5 + 0.33 * math.sin(t * 0.07 * (s + 1) + s * 2.1); cy = 0.5 + 0.35 * math.sin(t * 0.05 + s * 1.3)
                pts = []
                for k in range(48):
                    u = 2 * math.pi * k / 48
                    gv = _goava(k % 12, t * 0.25 + k / 48.0 + s, self.nums)
                    r = 0.07 * (1 + 0.35 * gv * getattr(self, "_swing", 1.0))
                    if s == 0:
                        x, y, z = cx + r * math.cos(u), cy + r * 0.6 * math.sin(u), 0.25
                    elif s == 1:
                        x, y, z = cx + r * math.sin(2 * u), cy + r * 0.6 * math.sin(3 * u + t * 0.2), 0.35 + 0.1 * gv
                    else:
                        x, y, z = cx + r * math.cos(u) * math.cos(3 * u), cy + r * 0.6 * math.sin(u), 0.3 + 0.15 * math.sin(2 * u + t * 0.3)
                    pts.append(self._proj(x, y, z, W, H, tilt))
                path = QPainterPath(pts[0])
                for q in pts[1:]: path.lineTo(q)
                path.closeSubpath()
                pen = QPen(_qc(200, 140, 255, int(a * 1.6))); pen.setWidthF(1.0); p.setPen(pen)
                edge = QPen(_qc(220, 170, 255, int(a * 0.5))); edge.setWidthF(5.0); p.setPen(edge); p.drawPath(path)   # soft glowing rim
                p.setPen(pen); p.setBrush(_qc(140, 90, 220, int(a * 0.55))); p.drawPath(path); p.setBrush(Qt.BrushStyle.NoBrush)
                # L-systems: inward (small, from the centre) and outward (from two vertices)
                c = self._proj(cx, cy, 0.3, W, H, tilt)
                self._branch(p, c, -90 + 20 * math.sin(t * 0.3 + s), 2.4, _qc(120, 255, 170, int(a * 1.4)))
                for v in (pts[s * 7 % 48], pts[(s * 7 + 24) % 48]):
                    ang = math.degrees(math.atan2(v.y() - c.y(), v.x() - c.x()))
                    self._branch(p, v, ang, 3.4, _qc(150, 230, 255, int(a * 1.2)))
            # caption (never mirrored)
            p.resetTransform()
            p.setPen(_qc(150, 190, 210, 150))
            p.drawText(8, 14, "rows %d · depth %.2f · canonical ×%.2f · user ×%.2f" % (
                len(rs), float(view.get("depth", 1.0)), float(view.get("scale_canonical", 1.0)), float(view.get("scale_user", 1.0))))
            p.end()

        def _branch(self, p, origin, angle, step, col):
            # R102 speed: one drawLines call per stack depth (same pens/widths as before) instead of a pen per segment
            from PyQt6.QtCore import QLineF
            x, y, a = origin.x(), origin.y(), angle; st = []; by_depth = {}
            for ch in _LS:
                if ch == "F":
                    r = math.radians(a); nx, ny = x + step * math.cos(r), y + step * math.sin(r)
                    by_depth.setdefault(len(st), []).append(QLineF(x, y, nx, ny)); x, y = nx, ny
                elif ch == "+": a += 24
                elif ch == "-": a -= 24
                elif ch == "[": st.append((x, y, a))
                elif ch == "]" and st: x, y, a = st.pop()
            for depth, lines in by_depth.items():
                pen = QPen(col); pen.setWidthF(max(0.6, 1.8 - 0.4 * depth)); p.setPen(pen)   # thicker near the root
                p.drawLines(lines)

    return Stage()
