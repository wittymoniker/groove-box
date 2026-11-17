"""edit_glow.py — Edit Synth Per Seq visibility. ON: the sequence selector and the synth panels glow in the selected
sequence's colour (set per sequence: 🎨 next to the selector, or right-click it), a hint says which sequence you are
editing and control tooltips are prefixed with it. OFF: a white MAIN hint and the normal tooltips."""
from __future__ import annotations
import sys


def _gb(app):
    return sys.modules.get(type(app).__module__)


def color(app, name, sid):
    try:
        mem = (app.instrument_sequence_banks.get(name) or {}).get(int(sid)) or {}
        if mem.get("glow_color"): return str(mem["glow_color"])
    except Exception:
        pass
    try:
        return _gb(app)._r89_orig_sequence_color(sid)
    except Exception:
        return "#5aa9ff"


def _targets(app):
    out = [getattr(app, "sequence_selector", None), getattr(app, "btn_edit_panels_per_sequence", None)]
    try: out += [g for g in app._geo_groups() if g is not None]
    except Exception: pass
    md = getattr(app, "main_md_panel", None)
    if md is not None: out.append(getattr(md, "control_rack", None))
    return [w for w in out if w is not None]


def refresh(app):
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QSlider, QAbstractSpinBox
    try: per = bool(app._panels_per_sequence_enabled())
    except Exception: per = False
    try:
        name = app._current_instrument_name(); sid = int(app._current_sequence_index(name))
    except Exception:
        return
    col = color(app, name, sid)
    lab = getattr(app, "lbl_edit_mode_hint", None)
    disp = app.instrument_label(name) if hasattr(app, "instrument_label") else name
    for w in _targets(app):
        try:
            if per:
                e = QGraphicsDropShadowEffect(w); e.setBlurRadius(22); e.setOffset(0, 0); e.setColor(QColor(col)); w.setGraphicsEffect(e)
            else:
                w.setGraphicsEffect(None)
            for c in w.findChildren(QSlider) + w.findChildren(QAbstractSpinBox):
                base = c.property("_r89_tip")
                if base is None:
                    base = c.toolTip(); c.setProperty("_r89_tip", base)
                c.setToolTip(("✎ SEQ #%d · %s (local) — %s" % (sid, disp, base)) if per else base)
        except RuntimeError:
            pass
    if lab is not None:
        if per:
            lab.setText("✎ PER-SEQ EDIT · %s · SEQ #%d — synth / FX / panel changes go to this sequence only" % (disp, sid))
            lab.setStyleSheet("color:#0b0d12;background:%s;font-weight:900;padding:2px 6px;border-radius:4px;" % col)
        else:
            lab.setText("MAIN EDIT · %s — changes apply to the instrument (all its sequences)" % disp)
            lab.setStyleSheet("color:#ffffff;background:#2b3446;font-weight:900;padding:2px 6px;border-radius:4px;")


def pick(app):
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QColorDialog
    name = app._current_instrument_name(); sid = int(app._current_sequence_index(name))
    d = QColorDialog(QColor(color(app, name, sid)), app); d.setWindowTitle("Glow colour · SEQ #%d" % sid)

    def done(c):
        try:
            app.instrument_sequence_banks.setdefault(name, {}).setdefault(sid, {})["glow_color"] = c.name()
        except Exception:
            pass
        try: app._refresh_connector_links()
        except Exception: refresh(app)
    d.colorSelected.connect(done); d.open(); app._glow_dialog = d


def install(app):
    if getattr(app, "_edit_glow", False): return
    app._edit_glow = True
    gb = _gb(app)
    if gb is not None and hasattr(gb, "sequence_color") and not hasattr(gb, "_r89_orig_sequence_color"):
        gb._r89_orig_sequence_color = gb.sequence_color

        def _seq_color(n, _app=app):
            try:
                return color(_app, _app._current_instrument_name(), n)
            except Exception:
                return gb._r89_orig_sequence_color(n)
        gb.sequence_color = _seq_color
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel, QToolButton, QLayout, QMenu
    sel = getattr(app, "sequence_selector", None)
    if sel is not None:
        app.lbl_edit_mode_hint = QLabel("")
        b = QToolButton(); b.setText("🎨"); b.setToolTip("Glow colour of the selected sequence"); b.clicked.connect(lambda: pick(app))
        try:
            par = sel.parentWidget()
            for lay in [par.layout()] + par.findChildren(QLayout):
                if lay is not None and lay.indexOf(sel) >= 0:
                    i = lay.indexOf(sel); lay.insertWidget(i + 1, b); lay.insertWidget(i + 2, app.lbl_edit_mode_hint); break
        except Exception:
            pass
        sel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def menu(pos):
            m = QMenu(sel); m.addAction("🎨 Glow colour…", lambda: pick(app))

            def reset():
                name = app._current_instrument_name(); sid = int(app._current_sequence_index(name))
                (app.instrument_sequence_banks.get(name) or {}).get(sid, {}).pop("glow_color", None); refresh(app)
            m.addAction("Reset glow colour", reset); m.exec(sel.mapToGlobal(pos))
        sel.customContextMenuRequested.connect(menu)
    orig = getattr(app, "_refresh_per_seq_styling", None)
    if callable(orig):
        def wrapped(*a, **k):
            r = orig(*a, **k)
            try: refresh(app)
            except Exception: pass
            return r
        app._refresh_per_seq_styling = wrapped
    refresh(app)
