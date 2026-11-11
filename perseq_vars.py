"""perseq_vars.py — GROOVEBOX_R32_PERSEQ_VARIABLES_20261110

PER-SEQUENCE WORKSPACE VARIABLES (canonical control over the playlist)
  • Blue button "Edit Local/PerSeq Global UI Variables" (panel synth area). While ON, every change you make to a
    global workspace variable (FX, EQ, synth engine, Mod Osc, mixers, expression, game macros … — every automation
    target) is stored as LOCAL state of the selected sequence (instrument # sequence). Turning it OFF puts the
    global values back exactly as they were, so local edits never leak into the global state.
  • At render (Play and every export) each playlist row morphs between the GLOBAL state and the LOCAL state of
    the sequences playing in it:  v = g + s·(mean(local) − g),  where s is the row's SHIFT VOTE (0…1).
    Votes are written into the playlist ("perseq_shift") — uniform, or canonical (seeded per row) — and default to
    the global morph amount. After the render the global state is restored.
OVERLAY (drawn over the main window, never takes clicks)
  • Blue glow + flag on every global-variable panel while blue editing is on ("GLOBAL → local for <seq>").
  • Edit Synth Per Seq ON: green wires from the sequencer to the panels that edit THIS sequence (local) and red
    wires to the panels that edit the GLOBAL mix, each with a flag naming what it edits.
  • 🧭 Flow labels (Quick Rack): every visible panel gets a plain-language flag (what it controls, where it routes),
    for the things too important for tooltips alone.
"""
from __future__ import annotations

import hashlib
import time

BLUE, GREEN, RED, GOLD = "#3aa0ff", "#2ecc71", "#ff5d6c", "#ffd166"


def state(app):
    st = getattr(app, "r32_perseq", None)
    if not isinstance(st, dict):
        st = app.r32_perseq = {"edit": False, "morph": 0.5, "seq": {}, "votes": "uniform"}
    st.setdefault("seq", {}); st.setdefault("morph", 0.5); st.setdefault("votes", "uniform")
    return st


def seq_key(app):
    try:
        inst = app.instrument_selector_dropdown.currentText()
    except Exception:
        inst = "?"
    sid = (getattr(app, "instrument_selected_sequence", {}) or {}).get(inst, 1)
    return "%s#%s" % (inst, sid)


def _targets(app):
    import automation_bus as ab
    out = {}
    for p in ab.targets(app)[:600]:
        d, k = ab._resolve(app, p)
        if d is not None and isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool):
            out[p] = d.get(k)
    return out


def _write(app, path, v):
    import automation_bus as ab
    d, k = ab._resolve(app, path)
    if d is not None:
        d[k] = int(round(v)) if isinstance(d.get(k), int) and not isinstance(d.get(k), bool) else v


# ---------------------------------------------------------------- edit mode ----------------
_EDIT = {"baseline": {}, "seen": {}, "timer": None}


def set_edit(app, on):
    from PyQt6.QtCore import QTimer
    st = state(app); st["edit"] = bool(on)
    if on:
        _EDIT["baseline"] = _targets(app); _EDIT["seen"] = dict(_EDIT["baseline"])
        t = _EDIT["timer"] = _EDIT["timer"] or QTimer(app)
        try:
            t.timeout.disconnect()
        except Exception:
            pass
        t.setInterval(300); t.timeout.connect(lambda: _capture(app)); t.start()
    else:
        if _EDIT["timer"] is not None:
            _EDIT["timer"].stop()
        _capture(app)
        for p, v in _EDIT["baseline"].items():          # globals back exactly as they were
            _write(app, p, v)
        app._shared_mixdown_cache = {}
    overlay(app).update()


def _capture(app):
    st = state(app); key = seq_key(app); loc = st["seq"].setdefault(key, {})
    now = _targets(app)
    for p, v in now.items():
        if v != _EDIT["seen"].get(p):
            loc[p] = v
    _EDIT["seen"] = now
    if not loc:
        st["seq"].pop(key, None)


def write_votes(app, mode=None):
    """Write a shift vote into every playlist row: uniform (= global morph) or canonical (seeded per row)."""
    st = state(app); mode = mode or st.get("votes", "uniform"); st["votes"] = mode
    rows = getattr(app, "master_playlist_data", None) or []
    try:
        sig = str(app._seed_program_signature())
    except Exception:
        sig = "0"
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        if mode == "canonical":
            u = int.from_bytes(hashlib.blake2b(("%s|row%d" % (sig, i)).encode(), digest_size=4).digest(), "little") / 2 ** 32
            r["perseq_shift"] = round(float(st["morph"]) * (0.5 + u), 4)
        else:
            r["perseq_shift"] = float(st["morph"])
    app._shared_mixdown_cache = {}
    return len(rows)


# ---------------------------------------------------------------- render morph -------------
_RENDER = {"global": None}


def render_row(app, row_idx):
    """Called by the offline render at each playlist row: morph global → the row's sequences' local state."""
    st = state(app)
    if not st["seq"]:
        return False
    if _RENDER["global"] is None:
        _RENDER["global"] = _targets(app)
    g = _RENDER["global"]
    rows = getattr(app, "_render_playlist_snapshot", None) or getattr(app, "master_playlist_data", None) or []
    row = rows[row_idx] if 0 <= row_idx < len(rows) and isinstance(rows[row_idx], dict) else {}
    ops = set(str(x) for x in (row.get("operators") or [])) or {str(row.get("operator") or "")}
    s = float(row.get("perseq_shift", st["morph"]) or 0.0)
    agg = {}
    for key, loc in st["seq"].items():
        if key.split("#")[0] in ops:
            for p, v in loc.items():
                agg.setdefault(p, []).append(float(v))
    for p, g0 in g.items():
        if p in agg:
            _write(app, p, g0 + s * (sum(agg[p]) / len(agg[p]) - g0))
        else:
            _write(app, p, g0)
    return True


def render_done(app):
    g = _RENDER["global"]; _RENDER["global"] = None
    if g:
        for p, v in g.items():
            _write(app, p, v)


# ---------------------------------------------------------------- overlay -------------------
def _boxes(app):
    from PyQt6.QtWidgets import QGroupBox
    glob, local = [], []
    sc = getattr(app, "_r32_deck_scroll", None)
    if sc is not None and sc.widget() is not None:
        glob += [b for b in sc.widget().findChildren(QGroupBox) if b.parentWidget() is sc.widget()]
    for b in app.findChildren(QGroupBox):
        if b.property("r32GlobalPanel"):
            glob.append(b)
    for name in ("leftSynthLaneScroll", "rightSynthLaneScroll"):
        for sa in app.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QScrollArea"]).QScrollArea, name):
            if sa.widget() is not None:
                local += [b for b in sa.widget().findChildren(QGroupBox) if b.parentWidget() is sa.widget()]
    return glob, local


def _role(b):
    t = (b.title() or "").strip()
    tip = (b.toolTip() or "").strip().split("\n")[0]
    return (t + (" — " + tip if tip else ""))[:90]


class _Overlay:
    pass


def overlay(app):
    ov = getattr(app, "_r32_flow_overlay", None)
    if ov is not None:
        return ov
    from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
    from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush
    from PyQt6.QtWidgets import QWidget

    host = app.centralWidget() or app

    class Ov(QWidget):
        def __init__(self):
            super().__init__(host)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.flow = False
            self._t = QTimer(self); self._t.setInterval(400); self._t.timeout.connect(self._tick); self._t.start()

        def _modes(self):
            st = state(app)
            per = bool(getattr(getattr(app, "btn_edit_panels_per_sequence", None), "isChecked", lambda: False)())
            return bool(st.get("edit")), per, bool(self.flow)

        def _tick(self):
            on = any(self._modes())
            self.setVisible(on)
            if on:
                self.setGeometry(host.rect()); self.raise_(); self.update()

        def _rect(self, w):
            try:
                if not w.isVisible() or w.visibleRegion().isEmpty():
                    return None
                tl = w.mapTo(host, w.rect().topLeft())
                return QRectF(tl.x(), tl.y(), w.width(), w.height())
            except Exception:
                return None

        def _flag(self, qp, r, text, col):
            qp.setFont(QFont("Sans", 8, QFont.Weight.Bold))
            fm = qp.fontMetrics(); wdt = min(int(r.width()) + 40, fm.horizontalAdvance(text) + 12)
            fr = QRectF(r.left() + 6, r.top() - 15, wdt, 16)
            c = QColor(col); c.setAlpha(225); qp.setBrush(QBrush(c)); qp.setPen(Qt.PenStyle.NoPen)
            qp.drawRoundedRect(fr, 4, 4); qp.setPen(QColor("#06101a")); qp.drawText(fr.adjusted(6, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, text)

        def paintEvent(self, _e):
            edit, per, flow = self._modes()
            qp = QPainter(self); qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            glob, local = _boxes(app)
            key = seq_key(app)
            if edit:                                     # blue glow + flags on every global-variable panel
                for b in glob:
                    r = self._rect(b)
                    if r is None:
                        continue
                    for wdt, a in ((7, 50), (3, 140), (1.5, 255)):
                        c = QColor(BLUE); c.setAlpha(a); qp.setPen(QPen(c, wdt)); qp.setBrush(Qt.BrushStyle.NoBrush)
                        qp.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 8, 8)
                    n = len((state(app)["seq"].get(key) or {}))
                    self._flag(qp, r, "GLOBAL → local for %s%s" % (key, (" · %d stored" % n) if n else ""), BLUE)
            if per:                                      # green = this sequence (local), red = global mix
                seq_w = getattr(app, "top_sequencer", None)
                sr = self._rect(seq_w) if seq_w is not None else None
                src = QPointF(sr.center().x(), sr.bottom()) if sr is not None else QPointF(self.width() / 2, 40)
                for group, col, label in ((local, GREEN, "PER-SEQ · edits %s" % key), (glob, RED, "GLOBAL · all sequences")):
                    for b in group:
                        r = self._rect(b)
                        if r is None:
                            continue
                        c = QColor(col); c.setAlpha(190); qp.setPen(QPen(c, 2.2, Qt.PenStyle.DashLine))
                        dst = QPointF(r.center().x(), r.top())
                        mid = QPointF((src.x() + dst.x()) / 2, min(src.y(), dst.y()) - 30)
                        from PyQt6.QtGui import QPainterPath
                        path = QPainterPath(src); path.quadTo(mid, dst); qp.drawPath(path)
                        qp.setBrush(QBrush(c)); qp.drawEllipse(dst, 4, 4); qp.setBrush(Qt.BrushStyle.NoBrush)
                        self._flag(qp, r, "%s · %s" % (label, (b.title() or "")[:28]), col)
            if flow:                                     # plain-language flags on every visible panel
                from PyQt6.QtWidgets import QGroupBox
                n = 0
                for b in app.findChildren(QGroupBox):
                    if n >= 80:
                        break
                    if b.window() is not app or not (b.title() or "").strip():
                        continue
                    r = self._rect(b)
                    if r is None or r.width() < 60:
                        continue
                    if (edit and b in glob) or (per and (b in glob or b in local)):
                        continue
                    self._flag(qp, r, _role(b), GOLD); n += 1
            qp.end()

    ov = app._r32_flow_overlay = Ov(); ov.hide()
    return ov


def make_button(app):
    """The blue panel-synth-area button (+ morph amount, votes)."""
    from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QDoubleSpinBox, QComboBox
    w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(2)
    b = QPushButton("Edit Local/PerSeq\nGlobal UI Variables"); b.setCheckable(True); b.setMinimumSize(128, 56)
    b.setToolTip("ON: changes to global workspace variables are stored for the selected sequence (blue panels). "
                 "OFF: the global values come back. The playlist morphs global → per-sequence by each row's shift vote.")
    b.setStyleSheet("QPushButton{background:#0f2a4a;color:#bfe1ff;border:2px solid #3aa0ff;border-radius:8px;font-weight:900;}"
                    "QPushButton:checked{background:#1d5fa8;color:#ffffff;border:2px solid #9fd0ff;}")
    b.setChecked(bool(state(app).get("edit")))
    b.toggled.connect(lambda on: set_edit(app, on))
    row = QHBoxLayout(); m = QDoubleSpinBox(); m.setRange(0, 1); m.setSingleStep(0.05); m.setValue(float(state(app)["morph"]))
    m.setToolTip("Global morph amount: 0 = rows play the global state, 1 = the sequences' local state.")
    m.valueChanged.connect(lambda v: (state(app).__setitem__("morph", float(v)), setattr(app, "_shared_mixdown_cache", {})))
    mode = QComboBox(); mode.addItems(["uniform", "canonical"]); mode.setCurrentText(state(app)["votes"])
    vb = QPushButton("Write shift votes"); vb.setToolTip("Write a morph vote into every playlist row (uniform, or seeded per row).")
    vb.clicked.connect(lambda: write_votes(app, mode.currentText()))
    for x in (m, mode, vb):
        row.addWidget(x)
    lay.addWidget(b); lay.addLayout(row)
    app._r32_perseq_button = b
    overlay(app)
    return w
