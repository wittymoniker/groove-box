"""playlist_view.py — GROOVEBOX_R32_PLAYLIST_VIEW_20261110

A graphical face on the EXISTING playlist (master_playlist_data rows with PLAYLIST_COLUMNS —
the same records the table and the CSV use; nothing about storage changes).

LANES     one lane per synth (from each row's operators_csv), in the synth's playlist colour.
BLOCKS    a row is drawn where it actually plays: x = time_offset (row units), width =
          coverage % of one row, height = velocity; overlap between rows is therefore visible as
          blocks sharing x; blend_partner is drawn as an arc to the partner's lane; multi_seq
          rows show stacked ticks; section names (Song Form) label the ruler.
EDIT      drag a block horizontally → time_offset; drag its right edge → coverage; wheel →
          velocity; double-click → the row inspector.
INSPECTOR every column of the row, with an editor chosen by the COLUMN TYPE REGISTRY
          (number / percent / text / tag / csv list / blob); blob columns get a wide multi-line
          editor, numbers a narrow spin box. New columns appended to PLAYLIST_COLUMNS appear
          automatically: unknown names get a type by inference from their values.
"""
from __future__ import annotations

import json
import re

from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QFormLayout, QLineEdit, QTextEdit,
                             QDoubleSpinBox, QPushButton, QSplitter, QSlider)

# name → (type, width weight).  Types: number, percent, text, tag, csv, blob
COLUMN_TYPES = {
    "time_marker": ("text", 2), "operators_csv": ("csv", 3), "script_tag": ("tag", 2), "domain_tag": ("tag", 2),
    "synth_tag": ("tag", 2), "patch_tag": ("tag", 2), "velocity": ("number", 1), "effect_target": ("tag", 2),
    "auto_amount": ("number", 1), "direction_vector": ("text", 1), "multi_seq": ("csv", 2), "coverage": ("percent", 1),
    "blend_partner": ("tag", 2), "live_parametrics": ("blob", 6), "sequence_ref": ("tag", 2), "sequence_attack": ("number", 1),
    "sequence_release": ("number", 1), "pitch_ratio": ("number", 1), "provenance": ("blob", 4), "section": ("tag", 1),
    "row_level": ("number", 1), "fx_send": ("number", 1), "time_fx_send": ("number", 1), "unison": ("number", 1),
    "sample_layer": ("number", 1), "mod_depth": ("number", 1), "expression": ("number", 1), "time_offset": ("number", 1),
    "perseq_shift": ("number", 1),
}


def column_type(name, sample=None):
    if name in COLUMN_TYPES:
        return COLUMN_TYPES[name]
    s = "" if sample is None else str(sample)
    if re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", s):
        return ("number", 1)
    if s.endswith("%"):
        return ("percent", 1)
    if len(s) > 80 or "\n" in s or s.startswith(("{", "[", "live_params")):
        return ("blob", 5)
    if "," in s:
        return ("csv", 2)
    return ("text", 2)


def _cov(v):
    try:
        s = str(v).strip().rstrip("%")
        x = float(s) / (100.0 if "%" in str(v) or float(s) > 1.0 else 1.0)
        return max(0.05, min(4.0, x))
    except Exception:
        return 1.0


def _num(v, d=0.0):
    try:
        return float(str(v).strip().rstrip("%"))
    except Exception:
        return d


class PlaylistCanvas(QWidget):
    LANE_H = 28
    ROW_W = 64

    def __init__(self, app, on_select):
        super().__init__()
        self.app = app; self.on_select = on_select
        self.setMouseTracking(True)
        self._drag = None; self._hit = []; self.selected = -1

    def rows(self):
        return getattr(self.app, "master_playlist_data", None) or []

    def lanes(self):
        names = []
        for e in self.rows():
            if isinstance(e, dict):
                for n in str(e.get("operators_csv") or e.get("operator") or "").split(","):
                    n = n.strip()
                    if n and n not in names:
                        names.append(n)
        return names or ["(no operators)"]

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(max(800, 140 + self.ROW_W * (len(self.rows()) + 2)), 40 + self.LANE_H * len(self.lanes()))

    def _color(self, name):
        try:
            return QColor(self.app._r32_instrument_color(name))
        except Exception:
            return QColor("#7dd3fc")

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#05070b"))
        rows, lanes = self.rows(), self.lanes()
        self.setMinimumSize(self.sizeHint())
        x0, y0, LH, RW = 130, 26, self.LANE_H, self.ROW_W
        # ruler + sections
        p.setFont(QFont("Sans", 7))
        last_sec = None
        for i in range(len(rows) + 1):
            x = x0 + i * RW
            p.setPen(QPen(QColor("#1d2a33"), 1)); p.drawLine(x, y0, x, y0 + LH * len(lanes))
            p.setPen(QColor("#8b98a5")); p.drawText(x + 2, 12, str(i + 1))
            sec = rows[i].get("section") if i < len(rows) and isinstance(rows[i], dict) else None
            if sec and sec != last_sec:
                p.setPen(QColor("#ffd166")); p.drawText(x + 2, 23, str(sec)); last_sec = sec
        for li, name in enumerate(lanes):
            y = y0 + li * LH
            c = self._color(name); c2 = QColor(c); c2.setAlpha(28)
            p.fillRect(QRectF(0, y, self.width(), LH), c2)
            p.setPen(c); p.drawText(QRectF(4, y, x0 - 8, LH), Qt.AlignmentFlag.AlignVCenter, name[:18])
        self._hit = []
        lane_y = {n: y0 + i * LH for i, n in enumerate(lanes)}
        for r, e in enumerate(rows):
            if not isinstance(e, dict):
                continue
            ops = [n.strip() for n in str(e.get("operators_csv") or e.get("operator") or "").split(",") if n.strip()]
            off = _num(e.get("time_offset", r), r); cov = _cov(e.get("coverage", "100%"))
            vel = max(0.1, min(1.5, _num(e.get("velocity", 1.0), 1.0)))
            x = x0 + off * RW; wpx = max(6.0, cov * RW)
            for op in ops:
                y = lane_y.get(op, y0)
                h = (LH - 6) * min(1.0, vel)
                c = self._color(op); fill = QColor(c); fill.setAlpha(170 if r == self.selected else 110)
                rect = QRectF(x + 1, y + (LH - h) / 2, wpx - 2, h)
                p.setBrush(QBrush(fill)); p.setPen(QPen(QColor("#ffffff") if r == self.selected else c, 1.5 if r == self.selected else 1))
                p.drawRoundedRect(rect, 4, 4)
                ms = [m for m in str(e.get("multi_seq") or "").split(",") if m.strip()]
                for k in range(min(6, len(ms))):
                    p.drawLine(QPointF(rect.left() + 3 + 4 * k, rect.bottom() - 2), QPointF(rect.left() + 3 + 4 * k, rect.bottom() - 7))
                self._hit.append((rect, r))
            bp = str(e.get("blend_partner") or "").strip()
            if bp and bp in lane_y and ops and bp not in ops:
                ya, yb = lane_y.get(ops[0], y0) + LH / 2, lane_y[bp] + LH / 2
                path = QPainterPath(QPointF(x + wpx / 2, ya)); path.cubicTo(x + wpx, ya, x + wpx, yb, x + wpx / 2, yb)
                pen = QPen(QColor(255, 255, 255, 90), 1); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
        p.end()

    def _row_at(self, pos):
        for rect, r in reversed(self._hit):
            if rect.contains(pos):
                return r, rect
        return None, None

    def mousePressEvent(self, ev):
        r, rect = self._row_at(ev.position())
        if r is None:
            return
        self.selected = r; self.on_select(r)
        edge = abs(ev.position().x() - rect.right()) < 6
        e = self.rows()[r]
        self._drag = (r, ev.position().x(), _num(e.get("time_offset", r), r), _cov(e.get("coverage", "100%")), edge)
        self.update()

    def mouseMoveEvent(self, ev):
        if not self._drag:
            r, rect = self._row_at(ev.position())
            self.setCursor(Qt.CursorShape.SizeHorCursor if rect is not None and abs(ev.position().x() - rect.right()) < 6 else Qt.CursorShape.ArrowCursor)
            return
        r, x0, off0, cov0, edge = self._drag
        dx = (ev.position().x() - x0) / self.ROW_W
        e = self.rows()[r]
        if edge:
            e["coverage"] = "%d%%" % int(round(100 * max(0.05, cov0 + dx)))
        else:
            e["time_offset"] = round(max(0.0, off0 + dx) * 4) / 4.0
        self.update()

    def mouseReleaseEvent(self, ev):
        if self._drag:
            self._drag = None
            self._commit()

    def wheelEvent(self, ev):
        r, _rect = self._row_at(ev.position())
        if r is None:
            return super().wheelEvent(ev)
        e = self.rows()[r]
        e["velocity"] = round(max(0.0, min(1.5, _num(e.get("velocity", 1.0), 1.0) + (0.05 if ev.angleDelta().y() > 0 else -0.05))), 3)
        self.update(); self._commit()

    def mouseDoubleClickEvent(self, ev):
        r, _ = self._row_at(ev.position())
        if r is not None:
            self.on_select(r, focus=True)

    def _commit(self):
        for fn in ("_push_restored_playlist_to_table", "_on_live_source_changed"):
            f = getattr(self.app, fn, None)
            if callable(f):
                try:
                    f()
                except Exception:
                    pass


class RowInspector(QWidget):
    def __init__(self, app, canvas):
        super().__init__(); self.app = app; self.canvas = canvas
        self.lay = QVBoxLayout(self); self.title = QLabel("Select a block"); self.lay.addWidget(self.title)
        self.sc = QScrollArea(); self.sc.setWidgetResizable(True); self.lay.addWidget(self.sc, 1)
        self.row = -1

    def show_row(self, r, focus=False):
        import groovebox as gb
        self.row = r; e = self.canvas.rows()[r] if 0 <= r < len(self.canvas.rows()) else {}
        self.title.setText("Row %d" % (r + 1))
        host = QWidget(); f = QFormLayout(host)
        cols = list(gb.PLAYLIST_COLUMNS) + [k for k in e if k not in gb.PLAYLIST_COLUMNS and not k.startswith("_")]
        for c in cols:
            typ, width = column_type(c, e.get(c))
            v = e.get(c, "")
            if typ == "number":
                w = QDoubleSpinBox(); w.setRange(-1e6, 1e6); w.setDecimals(4); w.setValue(_num(v, 0.0)); w.setMaximumWidth(120)
                w.valueChanged.connect(lambda val, k=c: self._set(k, round(val, 6)))
            elif typ == "percent":
                w = QDoubleSpinBox(); w.setRange(0, 400); w.setSuffix(" %"); w.setValue(_cov(v) * 100); w.setMaximumWidth(120)
                w.valueChanged.connect(lambda val, k=c: self._set(k, "%g%%" % val))
            elif typ == "blob":
                w = QTextEdit(); w.setPlainText(v if isinstance(v, str) else json.dumps(v, default=str)); w.setMinimumHeight(30 * width)
                w.setStyleSheet("font-family:Consolas,monospace;font-size:8pt;")
                w.textChanged.connect(lambda k=c, ww=w: self._set(k, ww.toPlainText()))
            else:
                w = QLineEdit(str(v)); w.setMinimumWidth(60 * width)
                w.editingFinished.connect(lambda k=c, ww=w: self._set(k, ww.text()))
            f.addRow("%s  [%s]" % (c, typ), w)
        self.sc.setWidget(host)

    def _set(self, key, val):
        rows = self.canvas.rows()
        if 0 <= self.row < len(rows) and isinstance(rows[self.row], dict):
            rows[self.row][key] = val
            self.canvas.update()
            t = getattr(self, "_t", None)
            if t is None:
                t = self._t = QTimer(self); t.setSingleShot(True); t.timeout.connect(self.canvas._commit)
            t.start(300)


def open_window(app):
    w = getattr(app, "_playlist_view_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); w._canvas.update(); return w
    except RuntimeError:
        pass
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🗂 Playlist · graphical view (same rows as the table / CSV)"); w.resize(1200, 640)
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel("Drag a block = time offset · drag its right edge = coverage · wheel = velocity · double-click = all columns. "
                         "Arcs = blend partners · ticks = multi-seq · gold = Song Form sections."))
    sp = QSplitter()
    insp = None

    def sel(r, focus=False):
        insp.show_row(r, focus)
    canvas = PlaylistCanvas(app, sel)
    sc = QScrollArea(); sc.setWidget(canvas); sc.setWidgetResizable(False)
    insp = RowInspector(app, canvas)
    sp.addWidget(sc); sp.addWidget(insp); sp.setSizes([820, 380]); lay.addWidget(sp, 1)
    row = QHBoxLayout()
    z = QSlider(Qt.Orientation.Horizontal); z.setRange(24, 200); z.setValue(canvas.ROW_W)
    z.valueChanged.connect(lambda v: (setattr(canvas, "ROW_W", int(v)), canvas.setMinimumSize(canvas.sizeHint()), canvas.update()))
    row.addWidget(QLabel("Zoom")); row.addWidget(z)
    b = QPushButton("↻ Refresh"); b.clicked.connect(lambda: (canvas.setMinimumSize(canvas.sizeHint()), canvas.update())); row.addWidget(b)
    lay.addLayout(row)
    w._canvas = canvas; app._playlist_view_window = w; w.show(); return w
