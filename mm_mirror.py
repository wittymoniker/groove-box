"""mm_mirror.py: the Mod Path Bay side panels of the Multidim synth (left: routing · right: perspective).

The Mod Matrix stage (3.5-D grid · GOAVA shapes · L-systems) is projected into side panels inside the Multidim
window: left (reflected), right (direct) or both. The panels are part of that window's own layout, so they follow
its position and size under every compositor (Wayland included). They also follow the synth: its selected
instrument (rows targeting it are highlighted), its mix, and that instrument's morph / chaos / fold macros.

Controls on each mirror: side (off · left · right · both) · flip · opacity · width · follow strength ·
open the Mod Matrix. Projects save the settings (project_schema: mod_matrix_mirror).
"""
from __future__ import annotations

# GROOVEBOX_R123_MOD_PATH_WIDEN_PHI_20261119: every Mod Path Bay panel / scroll area is drawn 1.618× (golden
# ratio) wider than its "width" setting — the setting keeps its old meaning and saved values stay valid.
WIDTH_PHI = 1.618
DEFAULTS = {"side": "both", "flip": False, "opacity": 0.92, "width": 320, "follow": 1.0}


def settings(app):
    s = getattr(app, "r101_mm_mirror", None)
    if not isinstance(s, dict):
        s = app.r101_mm_mirror = dict(DEFAULTS)
    for k, v in DEFAULTS.items():
        s.setdefault(k, v)
    return s


def _follow_fn(host, win):
    """What the Multidim synth is doing right now, scaled by the follow strength."""
    def f():
        s = settings(host); k = max(0.0, min(2.0, float(s.get("follow", 1.0))))
        try:
            name = win.cmb_inst.currentText()
        except Exception:
            name = ""
        md = {}
        try:
            md = ((getattr(host, "instrument_param_state", {}) or {}).get(name, {}) or {}).get("md_clones", {}) or {}
            if isinstance(md, dict) and md and not any(x in md for x in ("morph", "chaos", "fold_depth")):
                md = next((v for v in md.values() if isinstance(v, dict)), {})
        except Exception:
            md = {}
        try:
            mix = float(host._md_mix())
        except Exception:
            mix = 0.5
        morph = float(md.get("morph", 0.75) or 0.75); chaos = float(md.get("chaos", 0.0) or 0.0)
        fold = float(md.get("fold_depth", 1.0) or 1.0)
        return {"speed": 1.0 + k * (min(10.0, morph) - 0.75) * 0.25,
                "swing": 1.0 + k * min(1.0, chaos) * 1.5,
                "tilt": k * (min(16.0, fold) - 1.0) * 0.05,
                "glow": 1.0 + k * (mix - 0.5),
                "focus": name}
    return f


PANEL_CSS = """
QFrame#mpbPanel { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(10,16,30,235), stop:1 rgba(16,12,32,235));
                  border:1px solid rgba(120,150,255,110); border-radius:12px; }
QLabel { color:#cfe6ff; }
QLabel#mpbTitle { color:#9fe8ff; font-weight:900; font-size:10.5pt; }
QToolBox::tab { background: rgba(40,56,96,200); color:#e6f2ff; border-radius:7px; padding:5px 8px; font-weight:800; }
QToolBox::tab:selected { background: rgba(110,80,200,220); color:#fff; }
QWidget#mpbPage { background: transparent; }
QToolBox QScrollArea, QToolBox QScrollArea > QWidget, QToolBox QScrollArea > QWidget > QWidget { background: transparent; border: 0; }
QCheckBox::indicator { width:14px; height:14px; border:1px solid rgba(120,190,255,180); border-radius:3px; background: rgba(14,24,44,230); }
QCheckBox::indicator:checked { background: #55e0d0; }
QPushButton { background: rgba(36,62,104,210); color:#eef7ff; border:1px solid rgba(120,190,255,150); border-radius:8px;
              padding:5px 8px; font-weight:800; }
QPushButton:hover { background: rgba(60,100,170,230); border-color:#9fe8ff; }
QPushButton:checked { background: rgba(150,60,170,230); }
QDoubleSpinBox, QSpinBox, QComboBox { background: rgba(14,24,44,230); color:#fff; border:1px solid rgba(90,150,210,160);
              border-radius:6px; padding:3px 5px; }
QCheckBox { color:#dff0ff; }
QSlider::groove:horizontal { height:6px; background: rgba(50,70,120,200); border-radius:3px; }
QSlider::sub-page:horizontal { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #3fd2c4, stop:1 #9b7bff); border-radius:3px; }
QSlider::handle:horizontal { width:14px; margin:-5px 0; border-radius:7px; background:#e8fffb; border:2px solid #55e0d0; }
"""


DIALOG_CSS = PANEL_CSS + """
QDialog { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #070c18, stop:1 #120c26); color:#e6f2ff; }
QGroupBox { border:1px solid rgba(120,150,255,110); border-radius:12px; margin-top:12px; padding:8px;
            background: rgba(18,24,46,190); color:#c9b8ff; font-weight:900; }
QGroupBox::title { subcontrol-origin: margin; left:12px; padding:0 6px; }
QTableWidget { background: rgba(10,16,30,225); alternate-background-color: rgba(20,28,52,225); color:#e6f2ff;
               gridline-color: rgba(70,100,160,120); border:1px solid rgba(100,140,220,120); border-radius:8px; }
QHeaderView::section { background: rgba(40,56,96,230); color:#bfe8ff; border:0; padding:4px; font-weight:800; }
QTableCornerButton::section { background: rgba(40,56,96,230); border:0; }
QListWidget, QPlainTextEdit, QLineEdit { background: rgba(14,24,44,230); color:#fff; border:1px solid rgba(90,150,210,160); border-radius:6px; }
"""


def _spin(lo, hi, step, val, prefix, tip, cb, dec=3):
    from PyQt6.QtWidgets import QDoubleSpinBox
    w = QDoubleSpinBox(); w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(dec); w.setValue(float(val))
    w.setPrefix(prefix + " "); w.setToolTip(tip); w.valueChanged.connect(cb); return w


def _governor_page(host):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QComboBox, QLabel
    import mm_governor as G
    g = G.settings(host); w = QWidget(); w.setObjectName("mpbPage"); v = QVBoxLayout(w); v.setSpacing(4)
    on = QCheckBox("Governor on"); on.setChecked(bool(g["enabled"])); on.toggled.connect(lambda x: g.__setitem__("enabled", bool(x))); v.addWidget(on)
    for key, lo, hi, st, lab, tip in (("budget", 0.05, 16, 0.1, "budget", "Total modulation depth the matrix may use"),
                                      ("knee", 0.05, 1, 0.05, "knee", "Where the sine soft-knee starts"),
                                      ("slew", 0.1, 60, 0.5, "slew/s", "Fastest change per second of any row"),
                                      ("carrier_follow", 0, 1, 0.05, "carrier follow", "Depth breathes with the carrier"),
                                      ("canonical_share", 0, 1, 0.05, "canonical share", "Fair canonical control: the canonicals' part of the budget")):
        v.addWidget(_spin(lo, hi, st, g[key], lab, tip, lambda x, key=key: g.__setitem__(key, float(x))))
    cc = QComboBox(); cc.setEditable(True); cc.addItems([x[8:] for x in G.carrier_sources(host)]); cc.setCurrentText(str(g["carrier"]))
    cc.setToolTip("Which carrier the depth follows"); cc.currentTextChanged.connect(lambda x: g.__setitem__("carrier", x)); v.addWidget(cc)
    view = QLabel(""); view.setWordWrap(True); v.addWidget(view); v.addStretch(1)
    w._r101_view = view
    return w


def _reroute_page(host, pad):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton
    import mm_fields as F
    f = F.settings(host); w = QWidget(); w.setObjectName("mpbPage"); v = QVBoxLayout(w); v.setSpacing(4)
    pad.setMinimumSize(200, 200); v.addWidget(pad, 1)
    r = QHBoxLayout(); v.addLayout(r)
    on = QCheckBox("Fields on"); on.setChecked(bool(f["enabled"])); on.toggled.connect(lambda x: f.__setitem__("enabled", bool(x))); r.addWidget(on)
    r.addWidget(_spin(0, 1, 0.02, f["level"], "level", "How strongly both fields act (default 0.72)", lambda x: f.__setitem__("level", float(x)), 2))
    clr = QPushButton("Clear poles"); clr.clicked.connect(lambda: (f["points"].clear(), pad.update())); v.addWidget(clr)
    return w


def _perspective_page(host, pad):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QPushButton
    import mm_fields as F
    f = F.settings(host); w = QWidget(); w.setObjectName("mpbPage"); v = QVBoxLayout(w); v.setSpacing(4)
    pad.setMinimumSize(200, 200); v.addWidget(pad, 1)
    mag = _spin(-1, 1, 0.05, f["mag"], "magnitude", "+ together toward the global mean · − apart", lambda x: (f.__setitem__("mag", float(x)), pad.update()), 2)
    v.addWidget(mag)
    fo = QCheckBox("follows canonicals"); fo.setChecked(bool(f["follow"])); fo.toggled.connect(lambda x: f.__setitem__("follow", bool(x))); v.addWidget(fo)
    ctr = QPushButton("Centre view"); ctr.clicked.connect(lambda: (f.update(az=0.0, el=0.35, mag=0.0), mag.setValue(0.0), pad.update())); v.addWidget(ctr)
    return w


def _response_page(host):
    """Edit one row's trigonometric response and its carrier routing from the side panel."""
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSpinBox, QComboBox, QLabel
    import mod_matrix as mm, mm_governor as G
    w = QWidget(); w.setObjectName("mpbPage"); v = QVBoxLayout(w); v.setSpacing(4)
    pick = QSpinBox(); pick.setRange(1, 999); pick.setPrefix("row "); v.addWidget(pick)
    lab = QLabel(""); lab.setWordWrap(True); v.addWidget(lab)
    resp = QComboBox(); resp.addItems(list(G.RESPONSES)); v.addWidget(resp)
    st = {"busy": False}

    def row():
        rs = mm.rows(host); i = pick.value() - 1
        return rs[i] if 0 <= i < len(rs) else None

    freq = _spin(0.0625, 16, 0.25, 1.0, "freq", "Cycles of the response curve", lambda x: (not st["busy"]) and row() is not None and row().__setitem__("resp_freq", float(x)))
    phase = _spin(0, 1, 0.05, 0.0, "phase", "Turn of the response curve", lambda x: (not st["busy"]) and row() is not None and row().__setitem__("resp_phase", float(x)))
    spread = _spin(0, 1, 0.05, 0.25, "spread", "Phase spread across route targets", lambda x: (not st["busy"]) and row() is not None and row().__setitem__("spread", float(x)))
    for x in (freq, phase, spread):
        v.addWidget(x)
    resp.currentTextChanged.connect(lambda t: (not st["busy"]) and row() is not None and row().__setitem__("response", t))

    def load(*_):
        r = row(); st["busy"] = True
        try:
            if r is None:
                lab.setText("no such row — add rows with ⊕ Multidim lanes or in the full bay"); return
            lab.setText("%s → %s" % (r.get("source"), str(r.get("target", "")).split("/")[-1]))
            resp.setCurrentText(str(r.get("response", "linear"))); freq.setValue(float(r.get("resp_freq", 1.0)))
            phase.setValue(float(r.get("resp_phase", 0.0))); spread.setValue(float(r.get("spread", 0.25)))
        finally:
            st["busy"] = False
    pick.valueChanged.connect(load); load(); v.addStretch(1)
    w._r101_load = load
    return w


def _lanes_page(host, win):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
    import mod_matrix as mm
    w = QWidget(); w.setObjectName("mpbPage"); v = QVBoxLayout(w); v.setSpacing(4)
    info = QLabel(""); info.setWordWrap(True); v.addWidget(info)

    def add():
        try:
            n = mm.multidim_lanes(host, win.cmb_inst.currentText())
        except Exception:
            n = mm.multidim_lanes(host)
        info.setText("added %d Multidim lanes" % n if n else "this instrument's Multidim macros are already routed (or it has none yet)")
    b1 = QPushButton("⊕ Multidim lanes for this instrument"); b1.clicked.connect(add); v.addWidget(b1)
    b2 = QPushButton("🧬 Open the full Mod Path Bay"); b2.clicked.connect(lambda: mm.open_window(host)); v.addWidget(b2)
    b3 = QPushButton("⟲ Restore targets"); b3.clicked.connect(lambda: mm.restore_bases(host)); v.addWidget(b3)
    v.addStretch(1)
    w._r101_info = info
    return w


def _mirror_page(host, apply_cb):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QCheckBox, QSlider, QSpinBox, QLabel
    s = settings(host); w = QWidget(); w.setObjectName("mpbPage"); v = QVBoxLayout(w); v.setSpacing(4)
    cmb = QComboBox(); cmb.addItems(["both", "left", "right", "off"]); cmb.setCurrentText(str(s["side"])); v.addWidget(QLabel("panels")); v.addWidget(cmb)
    flip = QCheckBox("flip vertically"); flip.setChecked(bool(s["flip"])); v.addWidget(flip)
    v.addWidget(QLabel("opacity")); op = QSlider(Qt.Orientation.Horizontal); op.setRange(15, 100); op.setValue(int(float(s["opacity"]) * 100)); v.addWidget(op)
    wd = QSpinBox(); wd.setRange(220, 720); wd.setSingleStep(20); wd.setValue(int(s["width"])); wd.setSuffix(" px"); wd.setPrefix("width "); v.addWidget(wd)
    v.addWidget(QLabel("follow the Multidim synth")); fol = QSlider(Qt.Orientation.Horizontal); fol.setRange(0, 200); fol.setValue(int(float(s["follow"]) * 100)); v.addWidget(fol)
    cmb.currentTextChanged.connect(lambda x: (s.__setitem__("side", x), apply_cb()))
    flip.toggled.connect(lambda x: (s.__setitem__("flip", bool(x)), apply_cb()))
    op.valueChanged.connect(lambda x: (s.__setitem__("opacity", x / 100.0), apply_cb()))
    wd.valueChanged.connect(lambda x: (s.__setitem__("width", int(x)), apply_cb()))
    fol.valueChanged.connect(lambda x: s.__setitem__("follow", x / 100.0))
    v.addStretch(1)
    return w


def _panel_builder(host, win, follow, reroute_pad, perspective_pad, panels, apply_cb):
    """Shared factory for one Mod Path Bay panel ("left" = routing, mirrored; "right" = perspective)."""
    from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QFrame, QLabel, QToolBox, QGraphicsOpacityEffect
    import mm_visual
    s = settings(host)
    apply = apply_cb
    def make(side):
        fr = QFrame(); fr.setObjectName("mpbPanel"); fr.setStyleSheet(PANEL_CSS)
        v = QVBoxLayout(fr); v.setContentsMargins(8, 8, 8, 8); v.setSpacing(6)
        bar = QHBoxLayout(); v.addLayout(bar)
        t = QLabel("🧬 Mod Path Bay · " + ("routing ⟲" if side == "left" else "perspective")); t.setObjectName("mpbTitle"); bar.addWidget(t, 1)
        stage = mm_visual.make_widget(host, fr, mirror=(side == "left"), follow=follow)
        stage.setMinimumHeight(230)
        eff = QGraphicsOpacityEffect(stage); eff.setOpacity(float(s["opacity"])); stage.setGraphicsEffect(eff)
        v.addWidget(stage, 2)
        box = QToolBox(); v.addWidget(box, 3)
        pages = {}
        if side == "left":
            pages["gov"] = _governor_page(host); box.addItem(pages["gov"], "⚖ Governor · budget · slew · canonical share")
            box.addItem(_reroute_page(host, reroute_pad), "🧭 Reroute field · 2-D poles")
            pages["lanes"] = _lanes_page(host, win); box.addItem(pages["lanes"], "⊕ Multidim lanes · full bay")
        else:
            box.addItem(_perspective_page(host, perspective_pad), "🌐 Perspective field · 3-D view + magnitude")
            pages["resp"] = _response_page(host); box.addItem(pages["resp"], "∿ Row response · routing spread")
            box.addItem(_mirror_page(host, apply_cb), "🪞 Panels · side · opacity · follow")
        panels[side] = {"frame": fr, "stage": stage, "effect": eff, "pages": pages, "box": box}
        # R102: collapse to the title bar (remembered per side), so the ring view can give space to the geometrics
        from PyQt6.QtWidgets import QPushButton as _QPB
        col = _QPB("▾"); col.setFixedWidth(30); col.setToolTip("Collapse / expand this Mod Path Bay panel")
        def _collapse(side=side, col=col, stage=stage, box=box):
            hide = bool(settings(host).get("collapsed_" + side, False))
            stage.setVisible(not hide); box.setVisible(not hide); col.setText("▸" if hide else "▾")
        def _toggle(_=False, side=side):
            st = settings(host); st["collapsed_" + side] = not bool(st.get("collapsed_" + side, False)); _collapse()
        col.clicked.connect(_toggle)
        try:  # GROOVEBOX_R123_TOUCH_FALLBACKS_20261119: touch fallback for right-drag
            import touch_compat
            alt = touch_compat.alt_toggle_button(host); alt.setMinimumHeight(0); bar.addWidget(alt)
        except Exception:
            pass
        bar.addWidget(col); _collapse()
        try:
            __import__("jam_tools").mirror_accessories(host, fr, stage)
        except Exception:
            pass
        return fr

    return make


def attach(host, win):
    """Insert the Mod Path Bay side panels into a MultidimWindow (idempotent)."""
    if getattr(win, "_r101_mirrors", None):
        return win._r101_mirrors
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QFrame, QLabel, QWidget, QToolBox, QGraphicsOpacityEffect, QPushButton
    import mm_fields
    lay = win.layout(); scroll = getattr(win, "canvas_scroll", None)
    if lay is None or scroll is None:
        return None
    lay.removeWidget(scroll)
    row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(6)
    holder = QWidget(); holder.setLayout(row); lay.insertWidget(0, holder, 1)
    s = settings(host); follow = _follow_fn(host, win)
    reroute_pad, perspective_pad = mm_fields.make_pads(host)
    panels = {}

    make = _panel_builder(host, win, follow, reroute_pad, perspective_pad, panels, lambda: apply())

    row.addWidget(make("left")); row.addWidget(scroll, 1); row.addWidget(make("right"))
    tog = QPushButton("🧬"); tog.setToolTip("Show / hide the Mod Path Bay panels"); tog.setFixedWidth(34)

    def apply():
        side = str(s.get("side", "both"))
        for name, pn in panels.items():
            show = side == "both" or side == name
            pn["frame"].setVisible(show); pn["frame"].setFixedWidth(int(round(int(s["width"]) * WIDTH_PHI)))
            pn["effect"].setOpacity(float(s["opacity"])); pn["stage"].flip_v = bool(s["flip"])

    def toggle():
        s["side"] = "off" if s.get("side", "both") != "off" else "both"; apply()
    tog.clicked.connect(toggle)
    lay.addWidget(tog)                     # always reachable, even with both panels hidden

    def refresh():
        if not win.isVisible():
            return
        g = panels.get("left", {}).get("pages", {}).get("gov")
        v_ = getattr(host, "_r101_governor_view", None)
        if g is not None and v_:
            g._r101_view.setText("depth %.2f · canonical ×%.2f · user ×%.2f · canonical weight %.2f"
                                 % (v_["depth"], v_["scale_canonical"], v_["scale_user"], v_["canonical_weight"]))
    tm = QTimer(win); tm.setInterval(300); tm.timeout.connect(refresh); tm.start()
    apply()
    win._r101_mirrors = panels
    return panels


class _HostInstrument:
    """Adapter: the main window's instrument selector stands in for MultidimWindow.cmb_inst."""
    def __init__(self, host):
        self._host = host

    @property
    def cmb_inst(self):
        return getattr(self._host, "instrument_selector_dropdown", None) or _NoCombo()

    def isVisible(self):
        return True


class _NoCombo:
    def currentText(self):
        return ""


def attach_arc(host, arc):
    """Mod Path Bay panels inside the main workspace's ring view: on the left and right sides between the sequencer
    (upper) and automator (lower) arc rows, above the geometric-synth editors. Same settings as the Multidim window
    panels (side · flip · opacity · width · follow), so either place controls both. Idempotent."""
    if getattr(arc, "_r102_mpb", None):
        return arc._r102_mpb
    left_l, right_l = getattr(arc, "left_layout", None), getattr(arc, "right_layout", None)
    if left_l is None or right_l is None:
        return None
    from PyQt6.QtCore import QTimer
    import mm_fields
    s = settings(host); win = _HostInstrument(host); follow = _follow_fn(host, win)
    reroute_pad, perspective_pad = mm_fields.make_pads(host)
    panels = {}

    def apply():
        side = str(s.get("side", "both"))
        for name, pn in panels.items():
            show = side == "both" or side == name
            pn["frame"].setVisible(show)
            pn["frame"].setMinimumWidth(min(int(round(int(s["width"]) * WIDTH_PHI)), 841)); pn["frame"].setMaximumWidth(874)
            pn["effect"].setOpacity(float(s["opacity"])); pn["stage"].flip_v = bool(s["flip"])

    make = _panel_builder(host, win, follow, reroute_pad, perspective_pad, panels, apply)
    for side, lay in (("left", left_l), ("right", right_l)):
        fr = make(side)
        fr.setMinimumHeight(860)  # R123: geometrics moved to their own row — the Mod Path Bay gets the room
        lay.insertWidget(0, fr)

    def refresh():
        g = panels.get("left", {}).get("pages", {}).get("gov")
        v_ = getattr(host, "_r101_governor_view", None)
        if g is not None and v_ and hasattr(g, "_r101_view"):
            g._r101_view.setText("depth %.2f · canonical ×%.2f · user ×%.2f · canonical weight %.2f"
                                 % (v_["depth"], v_["scale_canonical"], v_["scale_user"], v_["canonical_weight"]))
    tm = QTimer(arc); tm.setInterval(300); tm.timeout.connect(refresh); tm.start()
    apply()
    arc._r102_mpb = panels
    host._r102_mpb_apply = apply
    return panels
