"""mm_fields.py: two Mod Matrix fields, applied to the row outputs in the same matrix pass (live = exports).

1. REROUTE FIELD (2-D, any number of points). Every row sits on the rim at its home angle a_i = 2*pi*i/N.
   Each point k you place is a pole: its angle t_k is the direction it pushes, its radius r_k (0..1) its
   intensity, its spin s_k (wheel over the point, -1..1) turns the push clockwise / anticlockwise over time.
     w_ik  = r_k * ((1 + cos(a_i - t_k)) / 2) ** 2            (influence: strongest for rows facing the pole)
     shift = sum_k w_ik * sin(t_k + s_k * phase - a_i)          (signed direction shift)
     v'    = 0.5 + (v - 0.5) * cos(pi * shift)                 (a strong pole folds the direction through, a
                                                               weak one only bends it)
2. PERSPECTIVE FIELD (3-D rotation + one complex magnitude). Rows sit on a Fibonacci sphere. Drag to rotate the
   view (azimuth, elevation); the wheel sets the magnitude m in -1..1 (the complex angle is the view direction,
   its modulus |m|, its sign together / apart). Rows facing the view (weight = max(0, p_i . view)) are drawn
   TOGETHER toward the global mean (m > 0, the global perspective) or pushed APART from it (m < 0):
     v' = v + m * weight_i * (mean - v)        then clamped to 0..1.
   "follow canonicals" lets the active canonical level slowly orbit the view.

Both are scaled by the field level (default 0.72). Canonical rows feel the fields reduced by the active
canonical weight (fair canonical control, see mm_governor). Settings are saved with the project.
"""
from __future__ import annotations
import math

DEFAULTS = {"enabled": True, "level": 0.72, "points": [], "az": 0.0, "el": 0.35, "mag": 0.0, "follow": False}


def settings(app):
    s = getattr(app, "r101_mm_fields", None)
    if not isinstance(s, dict):
        s = app.r101_mm_fields = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    for k, v in DEFAULTS.items():
        s.setdefault(k, list(v) if isinstance(v, list) else v)
    return s


def _sphere(i, n):
    """Fibonacci-sphere position of row i of n (unit vector)."""
    if n <= 1:
        return (0.0, 0.0, 1.0)
    z = 1 - 2 * (i + 0.5) / n; r = math.sqrt(max(0.0, 1 - z * z)); a = i * math.pi * (3 - math.sqrt(5))
    return (r * math.cos(a), r * math.sin(a), z)


def view_vector(az, el):
    return (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))


def apply(app, rows, outs, beat=0.0, canon_weight=0.0):
    s = settings(app)
    if not s.get("enabled") or not outs:
        return outs
    lvl = max(0.0, min(1.0, float(s.get("level", 0.72))))
    if lvl <= 0:
        return outs
    n = len(outs); out = list(outs)
    try:
        import mm_governor
        canon = [mm_governor.is_canonical_row(r) for r in rows]
    except Exception:
        canon = [False] * n
    # 1 reroute field
    pts = s.get("points") or []
    if pts:
        phase = 2 * math.pi * (beat / 16.0)
        for i in range(n):
            a = 2 * math.pi * i / n; shift = 0.0
            for p in pts:
                x, y = float(p[0]), float(p[1]); spin = float(p[2]) if len(p) > 2 else 0.0
                r = min(1.0, math.hypot(x, y)); t = math.atan2(y, x)
                w = r * ((1 + math.cos(a - t)) / 2) ** 2
                shift += w * math.sin(t + spin * phase - a)
            k = lvl * (1 - canon_weight if canon[i] else 1.0)
            folded = 0.5 + (out[i] - 0.5) * math.cos(math.pi * shift)
            out[i] = (1 - k) * out[i] + k * folded
    # 2 perspective field
    m = max(-1.0, min(1.0, float(s.get("mag", 0.0))))
    if abs(m) > 1e-6:
        az, el = float(s.get("az", 0.0)), float(s.get("el", 0.35))
        if s.get("follow"):
            az += 2 * math.pi * canon_weight * (beat / 64.0)
        vx, vy, vz = view_vector(az, el); mean = sum(out) / n
        for i in range(n):
            px, py, pz = _sphere(i, n); w = max(0.0, px * vx + py * vy + pz * vz)
            k = lvl * (1 - canon_weight if canon[i] else 1.0)
            out[i] = max(0.0, min(1.0, out[i] + k * m * w * (mean - out[i]) * (2.0 if m < 0 else 1.0)))
    app._r101_fields_view = {"points": len(pts), "mag": m, "level": lvl}
    return out


# ------------------------------------------------------------------ widgets
def make_pads(app):
    """(reroute pad, perspective pad) as two independent widgets (the Multidim side panels use one each)."""
    from PyQt6.QtCore import Qt, QPointF, QTimer
    from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
    from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QCheckBox, QDoubleSpinBox, QPushButton
    s = settings(app)

    def nrows():
        try:
            import mod_matrix
            return max(1, len(mod_matrix.rows(app)))
        except Exception:
            return 8

    class Reroute(QWidget):
        """Click: add a pole · drag: move it · right-click: remove · wheel over a pole: spin."""
        def __init__(self):
            super().__init__(); self.setMinimumSize(220, 220); self.drag = None
            self.setToolTip("REROUTE FIELD: click adds a pole, drag moves it (angle = direction, distance from centre = "
                            "intensity), right-click removes, right-drag on a pole sets its spin, right-drag on empty space turns the "
                            "perspective view, wheel over a pole sets its spin (after a click). Rows are the ticks on the rim.")

        def _xy(self, pos):
            c = min(self.width(), self.height()) / 2.0
            return ((pos.x() - self.width() / 2.0) / (c * 0.9), -(pos.y() - self.height() / 2.0) / (c * 0.9))

        def _nearest(self, pos):
            x, y = self._xy(pos)
            best = min(range(len(s["points"])), key=lambda k: (s["points"][k][0] - x) ** 2 + (s["points"][k][1] - y) ** 2, default=None)
            if best is not None and math.hypot(s["points"][best][0] - x, s["points"][best][1] - y) < 0.12:
                return best
            return None

        # GROOVEBOX_R123_MODPATH_RIGHT_DRAG_20261119: right-drag drives the other Mod Path features:
        # on a pole = its spin (vertical), on empty space = the perspective view (az/el).
        # A right-click without dragging still removes the pole under the cursor.
        def mousePressEvent(self, e):
            k = self._nearest(e.position())
            if __import__("touch_compat").right_like(e):
                self.rdrag = (e.position(), e.position(), k, False)
                return
            # touch fallbacks (touch_compat): sticky Alt-drag, or touch-and-hold, = right-drag
            hold = self._hold()
            if hold is not None and hold.press(e):
                self.rdrag = (e.position(), e.position(), k, False)
                return
            self._new_pole = k is None
            if k is None:
                x, y = self._xy(e.position()); r = math.hypot(x, y)
                if r > 1: x, y = x / r, y / r
                s["points"].append([x, y, 0.0]); self.drag = len(s["points"]) - 1
            else:
                self.drag = k
            self.update()

        def _hold(self):
            h = getattr(self, "_hold_g", None)
            if h is None:
                try:
                    import touch_compat
                    def _on_alt(start):
                        # the press became a hold: undo a just-added pole, then act as a right press
                        if getattr(self, "_new_pole", False) and self.drag is not None and self.drag < len(s["points"]):
                            s["points"].pop(self.drag)
                        self.drag = None
                        self.rdrag = (start, start, self._nearest(start), False); self.update()
                    h = self._hold_g = touch_compat.HoldGesture(self, app, _on_alt)
                except Exception:
                    h = None
            return h

        def mouseMoveEvent(self, e):
            if getattr(self, "_hold_g", None) is not None:
                self._hold_g.move(e)
            rd = getattr(self, "rdrag", None)
            if rd is not None:
                start, last, k, moved = rd
                d = e.position() - last
                moved = moved or (e.position() - start).manhattanLength() > 4
                if moved:
                    if k is not None and k < len(s["points"]):
                        p = s["points"][k]
                        while len(p) < 3: p.append(0.0)
                        p[2] = round(max(-1.0, min(1.0, p[2] - d.y() * 0.01)), 3)
                    else:
                        s["az"] = (float(s["az"]) + d.x() * 0.012) % (2 * math.pi)
                        s["el"] = max(-1.5, min(1.5, float(s["el"]) - d.y() * 0.012))
                self.rdrag = (start, e.position(), k, moved); self.update(); return
            if self.drag is not None and self.drag < len(s["points"]):
                x, y = self._xy(e.position()); r = math.hypot(x, y)
                if r > 1: x, y = x / r, y / r
                s["points"][self.drag][:2] = [x, y]; self.update()

        def mouseReleaseEvent(self, _e):
            rd = getattr(self, "rdrag", None)
            if rd is not None:
                _start, _last, k, moved = rd
                if not moved and k is not None and k < len(s["points"]):
                    s["points"].pop(k)
                self.rdrag = None; self.update()
            if getattr(self, "_hold_g", None) is not None:
                self._hold_g.release()
            self.drag = None; self._new_pole = False

        def contextMenuEvent(self, e):
            e.accept()

        def wheelEvent(self, e):
            k = self._nearest(e.position())
            if k is None:
                e.ignore(); return
            p = s["points"][k]
            while len(p) < 3: p.append(0.0)
            p[2] = max(-1.0, min(1.0, p[2] + (0.1 if e.angleDelta().y() > 0 else -0.1))); self.update()

        def paintEvent(self, _e):
            q = QPainter(self); q.setRenderHint(QPainter.RenderHint.Antialiasing)
            W, H = self.width(), self.height(); c = QPointF(W / 2, H / 2); R = min(W, H) / 2 * 0.9
            q.fillRect(self.rect(), QColor(8, 14, 26, 220))
            q.setPen(QPen(QColor(80, 140, 190, 90), 1))
            for f in (0.25, 0.5, 0.75, 1.0):
                q.drawEllipse(c, R * f, R * f)
            n = nrows()
            for i in range(n):
                a = 2 * math.pi * i / n; q.setPen(QPen(QColor(250, 190, 90, 200), 2))
                q.drawLine(QPointF(c.x() + R * 0.95 * math.cos(a), c.y() - R * 0.95 * math.sin(a)),
                           QPointF(c.x() + R * 1.04 * math.cos(a), c.y() - R * 1.04 * math.sin(a)))
            for p in s["points"]:
                x, y = p[0], p[1]; spin = p[2] if len(p) > 2 else 0.0; r = min(1.0, math.hypot(x, y))
                pt = QPointF(c.x() + x * R, c.y() - y * R)
                q.setPen(QPen(QColor(120, 240, 255, 160), 1)); q.drawLine(c, pt)
                q.setBrush(QBrush(QColor(90, 220, 240, int(80 + 170 * r)))); q.drawEllipse(pt, 5 + 6 * r, 5 + 6 * r)
                if spin:
                    q.setPen(QPen(QColor(200, 140, 255, 200), 2)); q.setBrush(Qt.BrushStyle.NoBrush)
                    q.drawArc(int(pt.x() - 14), int(pt.y() - 14), 28, 28, 90 * 16, int(-spin * 300 * 16))
                q.setBrush(Qt.BrushStyle.NoBrush)
            q.setPen(QColor(150, 190, 210, 170)); q.drawText(6, 14, "reroute · %d poles" % len(s["points"])); q.end()

    class Perspective(QWidget):
        """Drag: rotate the view · wheel: magnitude (+ together · − apart)."""
        def __init__(self):
            super().__init__(); self.setMinimumSize(220, 220); self.last = None
            self.setToolTip("PERSPECTIVE FIELD: drag to rotate the view (the complex angle), wheel for the magnitude "
                            "(+ draws rows facing the view together toward the global mean, − pushes them apart). Right-drag: up/down = "
                            "magnitude, left/right = rotate all reroute poles.")

        # GROOVEBOX_R123_MODPATH_RIGHT_DRAG_20261119: right-drag drives the other Mod Path features:
        # vertical = magnitude (+ together / − apart), horizontal = rotate every reroute pole about the centre.
        def mousePressEvent(self, e):
            self.last = e.position()
            self.right = __import__("touch_compat").right_like(e)
            if not self.right:
                try:
                    import touch_compat
                    if getattr(self, "_hold_g", None) is None:
                        self._hold_g = touch_compat.HoldGesture(self, app, lambda _p: setattr(self, "right", True))
                    if self._hold_g.press(e):
                        self.right = True
                except Exception:
                    pass

        def mouseMoveEvent(self, e):
            if self.last is None: return
            if getattr(self, "_hold_g", None) is not None:
                self._hold_g.move(e)
            d = e.position() - self.last; self.last = e.position()
            if getattr(self, "right", False):
                s["mag"] = round(max(-1.0, min(1.0, float(s["mag"]) - d.y() * 0.005)), 3)
                ang = d.x() * 0.012
                if ang:
                    ca, sa = math.cos(ang), math.sin(ang)
                    for p in s["points"]:
                        p[0], p[1] = p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca
                self.update(); return
            s["az"] = (float(s["az"]) + d.x() * 0.012) % (2 * math.pi)
            s["el"] = max(-1.5, min(1.5, float(s["el"]) - d.y() * 0.012)); self.update()

        def mouseReleaseEvent(self, _e):
            self.last = None; self.right = False
            if getattr(self, "_hold_g", None) is not None:
                self._hold_g.release()

        def contextMenuEvent(self, e):
            e.accept()

        def wheelEvent(self, e):
            s["mag"] = round(max(-1.0, min(1.0, float(s["mag"]) + (0.05 if e.angleDelta().y() > 0 else -0.05))), 3); self.update()

        def paintEvent(self, _e):
            q = QPainter(self); q.setRenderHint(QPainter.RenderHint.Antialiasing)
            W, H = self.width(), self.height(); c = QPointF(W / 2, H / 2); R = min(W, H) / 2 * 0.8
            q.fillRect(self.rect(), QColor(8, 14, 26, 220))
            az, el, m = float(s["az"]), float(s["el"]), float(s["mag"])
            ca, sa, ce, se = math.cos(-az), math.sin(-az), math.cos(-el), math.sin(-el)

            def proj(p):
                x, y, z = p; x, y = x * ca - y * sa, x * sa + y * ca      # rotate so the view looks out of the screen
                x, z = x * ce - z * se, x * se + z * ce
                return QPointF(c.x() + y * R, c.y() - z * R), x
            q.setPen(QPen(QColor(70, 120, 170, 90), 1))
            for k in range(-2, 3):                                        # latitude rings
                pts = [proj((math.cos(k * 0.5) * math.cos(t), math.cos(k * 0.5) * math.sin(t), math.sin(k * 0.5)))[0]
                       for t in [j * 2 * math.pi / 48 for j in range(49)]]
                for a, b in zip(pts, pts[1:]): q.drawLine(a, b)
            n = nrows(); vx, vy, vz = view_vector(az, el)
            for i in range(n):
                p = _sphere(i, n); pt, depth = proj(p); w = max(0.0, p[0] * vx + p[1] * vy + p[2] * vz)
                col = QColor(90, 220, 240) if m >= 0 else QColor(255, 120, 160); col.setAlpha(int(60 + 190 * w))
                q.setBrush(QBrush(col)); q.setPen(Qt.PenStyle.NoPen); q.drawEllipse(pt, 2.5 + 4 * w, 2.5 + 4 * w)
            q.setPen(QPen(QColor(255, 220, 120, 220), 2)); q.setBrush(Qt.BrushStyle.NoBrush)
            q.drawEllipse(c, R * abs(m) * 0.25 + 3, R * abs(m) * 0.25 + 3)       # magnitude ring at the view centre
            q.setPen(QColor(150, 190, 210, 170))
            q.drawText(6, 14, "perspective · az %.0f° el %.0f° · %s %.2f" % (math.degrees(az), math.degrees(el), "together" if m >= 0 else "apart", abs(m)))
            q.end()

    a, b = Reroute(), Perspective()
    for w in (a, b):                       # repaint while visible (rows and canonicals move underneath)
        t = QTimer(w); t.setInterval(200); t.timeout.connect(lambda w=w: w.update() if w.isVisible() else None); t.start()
    return a, b


def make_panel(app):
    """Both fields side by side with their shared controls (used inside the full Mod Path Bay window)."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QCheckBox, QDoubleSpinBox, QPushButton
    s = settings(app)
    box = QGroupBox("Fields · reroute (2-D poles) · perspective (3-D rotation + magnitude)"); v = QVBoxLayout(box)
    h = QHBoxLayout(); v.addLayout(h); a, b = make_pads(app); h.addWidget(a, 1); h.addWidget(b, 1)
    ctl = QHBoxLayout(); v.addLayout(ctl)
    on = QCheckBox("On"); on.setChecked(bool(s["enabled"])); on.toggled.connect(lambda x: s.__setitem__("enabled", bool(x)))
    lv = QDoubleSpinBox(); lv.setRange(0, 1); lv.setSingleStep(0.02); lv.setDecimals(2); lv.setValue(float(s["level"])); lv.setPrefix("level ")
    lv.valueChanged.connect(lambda x: s.__setitem__("level", float(x)))
    fo = QCheckBox("perspective follows canonicals"); fo.setChecked(bool(s["follow"])); fo.toggled.connect(lambda x: s.__setitem__("follow", bool(x)))
    clr = QPushButton("Clear poles"); clr.clicked.connect(lambda: (s["points"].clear(), a.update()))
    ctr = QPushButton("Centre view"); ctr.clicked.connect(lambda: (s.update(az=0.0, el=0.35, mag=0.0), b.update()))
    for w_ in (on, lv, fo, clr, ctr):
        ctl.addWidget(w_)
    ctl.addStretch(1)
    return box
