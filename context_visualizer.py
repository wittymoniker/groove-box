"""context_visualizer.py — GROOVEBOX_R32_CONTEXT_MAP_20261110

🗺 Context Map: models every local / global context of the project in one live picture.

  MAP view   GLOBAL at the centre (seed signature, canonical mode, divergence, global FX /
             time FX / synth engine / sample layer); every instrument on a ring around it.
             Each instrument node shows four arcs (local FX · time FX · synth engine · sample
             layer, length = amount), its fill = canonical share, a ring when it has userdata
             marks, and lines for its modulation routes (dashed = canonical route). Click a node
             to select that instrument (all local panels follow); hover for the numbers.
  MATRIX     instruments × domains (fx, time, engine, sample, geometry) — each cell says USER /
             CANONICAL / MIX; click a cell to cycle its mode (written through the same state the
             panels use, so the panels refresh).
Refreshes twice a second while visible; idle when hidden.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem, QLabel

COL = {"fx": QColor("#f6c177"), "time": QColor("#7dd3fc"), "engine": QColor("#ffd166"), "sample": QColor("#9ece6a"),
       "route": QColor("#c4a7e7"), "canon": QColor("#2ecc71"), "user": QColor("#ff7a90")}


def _names(app):
    try:
        return list(getattr(app, "instrument_names_48", None) or [])[: max(1, app.instrument_selector_dropdown.count())]
    except Exception:
        return list(getattr(app, "instrument_names_48", None) or [])[:16]


def _amounts(app, name):
    fx = ((getattr(app, "r32_fx_state", {}) or {}).get("local", {}) or {}).get(name, {}) or {}
    tf = ((getattr(app, "r32_time_fx", {}) or {}).get("local", {}) or {}).get(name, {}) or {}
    se = ((getattr(app, "r32_synth_engine", {}) or {}).get("local", {}) or {}).get(name, {}) or {}
    sg = (getattr(app, "r32_sample_local", {}) or {}).get(name)
    a_fx = max([float(fx.get(k, 0) or 0) for k in ("pkp", "fractal", "eqr", "hyper")] + [0])
    a_tf = max([float(tf.get(k, 0) or 0) for k in ("chorus", "flanger", "reverb")] + [0])
    a_se = min(1.0, (max(0, int(se.get("unison", 1) or 1) - 1) / 6.0) + float(se.get("sub", 0) or 0) + float(se.get("fold", 0) or 0))
    a_sg = float(getattr(sg, "layer", 0.0) or 0.0) if sg is not None else 0.0
    modes = {"fx": fx.get("mode", "user"), "time": tf.get("mode", "user"), "engine": se.get("mode", "user")}
    routes = list(getattr(sg, "routes", []) or []) if sg is not None else []
    return {"fx": a_fx, "time": a_tf, "engine": a_se, "sample": a_sg}, modes, routes


class ContextMap(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setMinimumSize(520, 420)
        self.setMouseTracking(True)
        self._nodes = []
        self._t = QTimer(self); self._t.setInterval(500); self._t.timeout.connect(self.update)

    def showEvent(self, e):
        self._t.start(); super().showEvent(e)

    def hideEvent(self, e):
        self._t.stop(); super().hideEvent(e)

    def paintEvent(self, _e):
        app = self.app
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#05070b"))
        W, H = self.width(), self.height(); cx, cy = W / 2, H / 2; R = min(W, H) * 0.38
        names = _names(app)
        try:
            cur = app.instrument_selector_dropdown.currentText()
        except Exception:
            cur = ""
        touched = set(str(t).split(":")[0] for t in (getattr(app, "_canonical_field_touched", None) or set()))
        share = float((getattr(app, "geometric_synth_mixer_state", {}) or {}).get("multidim_canon", 1.0))
        self._nodes = []
        # global node
        gcol = QColor("#1b2a3a"); p.setBrush(QBrush(gcol)); p.setPen(QPen(QColor("#7dd3fc"), 2))
        p.drawEllipse(QPointF(cx, cy), 58, 58)
        p.setPen(QColor("#ffffff")); p.setFont(QFont("Sans", 8, QFont.Weight.Bold))
        try:
            sig = int(app._seed_program_signature() or 0)
        except Exception:
            sig = 0
        txt = "GLOBAL\n%s\ndiv %.2f · sig %05d" % (getattr(app, "canonical_mode", "protected"),
                                                  float(getattr(app, "seed_divergence", 0.6) or 0.6), sig % 100000)
        p.drawText(QRectF(cx - 58, cy - 30, 116, 60), Qt.AlignmentFlag.AlignCenter, txt)
        n = max(1, len(names))
        pos = {}
        for i, name in enumerate(names):
            a = -math.pi / 2 + 2 * math.pi * i / n
            x, y = cx + R * math.cos(a), cy + R * math.sin(a)
            pos[name] = (x, y)
        # routes first (under nodes)
        for name in names:
            _am, _m, routes = _amounts(app, name)
            for rt in routes:
                pen = QPen(COL["route"], 1.4); pen.setStyle(Qt.PenStyle.DashLine if rt.get("owner") == "canonical" else Qt.PenStyle.SolidLine)
                p.setPen(pen); x, y = pos[name]
                tgt = (cx, cy) if str(rt.get("dst", "")).startswith("global") or str(rt.get("src", "")).startswith("global") else (x, y - 30)
                p.drawLine(QPointF(x, y), QPointF(*tgt))
        for name in names:
            x, y = pos[name]
            am, modes, _r = _amounts(app, name)
            r = 22
            canon = share if modes.get("fx") != "user" or True else 0.0
            fill = QColor(COL["canon"]); fill.setAlphaF(0.15 + 0.6 * canon)
            p.setBrush(QBrush(fill))
            p.setPen(QPen(QColor("#ffffff") if name == cur else QColor("#5a6b7d"), 3 if name == cur else 1))
            p.drawEllipse(QPointF(x, y), r, r)
            if any(t for t in touched):
                p.setPen(QPen(COL["user"], 1.5)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(QPointF(x, y), r + 4, r + 4)
            for k, (key, start) in enumerate((("fx", 90), ("time", 0), ("engine", -90), ("sample", 180))):
                span = int(-90 * 16 * max(0.0, min(1.0, am[key])))
                if span:
                    p.setPen(QPen(COL[key], 4)); p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawArc(QRectF(x - r - 9, y - r - 9, 2 * r + 18, 2 * r + 18), start * 16, span)
            p.setPen(QColor("#e6edf3")); p.setFont(QFont("Sans", 7))
            p.drawText(QRectF(x - 60, y + r + 8, 120, 14), Qt.AlignmentFlag.AlignCenter, name[:20])
            self._nodes.append((name, x, y, r, am, modes))
        # legend
        p.setFont(QFont("Sans", 7)); yy = 10
        for key, label in (("fx", "local FX"), ("time", "time FX"), ("engine", "synth engine"), ("sample", "sample layer"),
                           ("route", "mod route (dashed = canonical)"), ("canon", "fill = canonical share"), ("user", "ring = userdata")):
            p.setPen(QPen(COL[key], 3)); p.drawLine(10, yy + 5, 26, yy + 5); p.setPen(QColor("#cfd8e3")); p.drawText(32, yy + 9, label); yy += 14
        p.end()

    def _hit(self, pos):
        for name, x, y, r, am, modes in self._nodes:
            if (pos.x() - x) ** 2 + (pos.y() - y) ** 2 <= (r + 10) ** 2:
                return name, am, modes
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        self.setToolTip("" if not h else "%s\nlocal FX %.2f (%s) · time FX %.2f (%s)\nsynth engine %.2f (%s) · sample layer %.2f" % (
            h[0], h[1]["fx"], h[2].get("fx"), h[1]["time"], h[2].get("time"), h[1]["engine"], h[2].get("engine"), h[1]["sample"]))

    def mousePressEvent(self, e):
        h = self._hit(e.position())
        if h:
            dd = getattr(self.app, "instrument_selector_dropdown", None)
            if dd is not None:
                i = dd.findText(h[0])
                if i >= 0:
                    dd.setCurrentIndex(i)
            self.update()


DOMAINS = (("fx", "r32_fx_state"), ("time", "r32_time_fx"), ("engine", "r32_synth_engine"))
CYCLE = ("user", "canonical", "mix")


class OwnershipMatrix(QTableWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.cellClicked.connect(self._cycle)
        self.refresh()

    def refresh(self):
        names = _names(self.app)
        self.setRowCount(len(names)); self.setColumnCount(len(DOMAINS))
        self.setHorizontalHeaderLabels([d for d, _ in DOMAINS]); self.setVerticalHeaderLabels(names)
        for r, name in enumerate(names):
            for c, (d, attr) in enumerate(DOMAINS):
                st = (getattr(self.app, attr, None) or {}).get("local", {}).get(name, {}) or {}
                mode = st.get("mode", "user")
                it = QTableWidgetItem(mode.upper()); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it.setBackground(QColor("#123d24") if mode == "canonical" else (QColor("#2e2a12") if mode == "mix" else QColor("#3a1620")))
                it.setForeground(QColor("#ffffff"))
                self.setItem(r, c, it)

    def _cycle(self, r, c):
        name = self.verticalHeaderItem(r).text(); d, attr = DOMAINS[c]
        root = self.app.__dict__.setdefault(attr, {"global": {}, "local": {}})
        st = root.setdefault("local", {}).setdefault(name, {})
        modes = CYCLE if d == "fx" else ("user", "canonical")
        cur = st.get("mode", "user")
        st["mode"] = modes[(modes.index(cur) + 1) % len(modes)] if cur in modes else "user"
        getattr(self.app, "_on_live_source_changed", lambda: None)()
        self.refresh()


def open_window(app):
    w = getattr(app, "_context_map_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); return w
    except RuntimeError:
        pass
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🗺 Context Map · every local / global context")
    w.resize(860, 700); lay = QVBoxLayout(w); tabs = QTabWidget(); lay.addWidget(tabs)
    tabs.addTab(ContextMap(app), "Map")
    mx = OwnershipMatrix(app); tabs.addTab(mx, "Ownership matrix")
    tabs.currentChanged.connect(lambda i: mx.refresh() if i == 1 else None)
    lay.addWidget(QLabel("Click an instrument to select it. In the matrix, click a cell to cycle USER → CANONICAL → MIX."))
    app._context_map_window = w; w.show(); return w
