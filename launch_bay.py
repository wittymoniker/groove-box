"""launch_bay.py: big launchers beside the Multidim sphere, in the ring view's side areas (with the Mod Path Bay).

Left bay  · Multidim: 🌀 Multidim Synth · ✎ Script · ∂ Domain · ⧉ Patch  (+ 🧬 Master Mod Path Matrix)
Right bay · Geometrics: ◆ Vector · 〰 Wavetable · ● Ball · ▦ Cellular  (+ ⤓ Dock all)

The editor launchers open the Multidim window and scroll to / focus / flash the matching editor. Each Geometrics
launcher pops that editor out into its own window; closing the window docks it back exactly where it was. The
buttons show where each editor is (docked / in window). Shortcuts: Ctrl+Alt+M Multidim · Ctrl+Alt+P Mod Path Matrix ·
Ctrl+Alt+1…4 Vector / Wavetable / Ball / Cellular.
"""
from __future__ import annotations

GEOMETRICS = (("master_vector_group", "◆ Vector", "Vector synth"),
              ("wavetable_projector_group", "〰 Wavetable", "Wavetable synth · draw"),
              ("ball_synth_group", "● Ball", "Bouncing ball synth"),
              ("cellular_synth_group", "▦ Cellular", "Cellular automata synth"))
EDITORS = (("multidim", "🌀 Multidim Synth", "Open the Multidim synth window"),
           ("script", "✎ Script editor", "Open the Multidim window at the script (k) editor"),
           ("domain", "∂ Domain editor", "Open the Multidim window at the domain-equation editor"),
           ("patch", "⧉ Patch editor", "Open the Multidim window at the modular patch"))

BAY_CSS = """
QFrame#launchBay { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(12,20,38,235), stop:1 rgba(26,14,44,235));
                   border:1px solid rgba(120,150,255,120); border-radius:14px; }
QLabel#launchTitle { color:#9fe8ff; font-weight:900; font-size:11pt; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(40,74,124,235), stop:1 rgba(26,44,82,235));
              color:#eef7ff; border:2px solid rgba(110,190,255,170); border-radius:12px; padding:10px 12px;
              font-weight:900; font-size:12.5pt; text-align:left; }
QPushButton:hover { border-color:#9fe8ff; background: rgba(64,110,180,240); }
QPushButton:pressed { background:#ff9f1c; color:#16110a; }
QPushButton[geoOut="true"] { border-color:#ffbd78; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(110,64,30,235), stop:1 rgba(70,36,20,235)); }
QPushButton#bayWide { font-size:11pt; text-align:center; padding:8px; background: rgba(110,60,170,230); border-color:#c9a6ff; }
"""


# ------------------------------------------------------------------ Multidim editors
def open_editor(host, which):
    """Open the Multidim window; for script / domain / patch scroll to that editor, focus it and flash it."""
    try:
        import multidim_ui
        w = multidim_ui.open_multidim_window(host)
    except Exception as exc:
        print("[launch bay] Multidim window unavailable:", exc)
        return None
    if w is None or which == "multidim":
        return w
    target = {"script": getattr(w, "ed_script", None), "domain": getattr(w, "ed_domain", None)}.get(which)
    if which == "patch":
        sl = getattr(w, "patch_sl", {}) or {}
        first = next(iter(sl.values()), None)
        target = first.parentWidget() if first is not None else None
    if target is None:
        return w
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QScrollArea

    def reveal():
        p = target.parentWidget()
        while p is not None:
            if isinstance(p, QScrollArea):
                p.ensureWidgetVisible(target, 40, 80)
            p = p.parentWidget()
        try:
            target.setFocus()
        except Exception:
            pass
        old = target.styleSheet()
        target.setStyleSheet(old + "\n* { border:2px solid #ff9f1c; }")
        QTimer.singleShot(1400, lambda: target.setStyleSheet(old))
    QTimer.singleShot(60, reveal)          # after the window has laid itself out
    return w


# ------------------------------------------------------------------ Geometrics pop-out / dock
def _dock_info(host):
    return host.__dict__.setdefault("_r102_geo_popouts", {})


def is_out(host, attr):
    d = _dock_info(host).get(attr)
    return bool(d and d.get("dialog") is not None)


def popout(host, attr, title):
    """Move one geometric editor into its own window (or raise it). Closing the window docks it back."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QFrame
    info = _dock_info(host); cur = info.get(attr)
    if cur and cur.get("dialog") is not None:
        cur["dialog"].raise_(); cur["dialog"].activateWindow(); return cur["dialog"]
    g = getattr(host, attr, None)
    if g is None:
        return None
    parent = g.parentWidget(); lay = parent.layout() if parent is not None else None
    idx = lay.indexOf(g) if lay is not None else -1
    dlg = QDialog(host); dlg.setWindowTitle("Geometrics · " + title); dlg.setWindowModality(Qt.WindowModality.NonModal)
    dlg.setStyleSheet("QDialog { background:#0a0f1c; }")
    v = QVBoxLayout(dlg); v.setContentsMargins(8, 8, 8, 8)
    sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame); v.addWidget(sa)
    hint = g.sizeHint()
    info[attr] = {"dialog": dlg, "parent": parent, "layout": lay, "index": idx, "scroll": sa}
    sa.setWidget(g); g.show()
    dlg.resize(max(560, hint.width() + 40), max(520, min(1100, hint.height() + 60)))

    def dock(*_):
        d = info.get(attr) or {}
        if d.get("dialog") is None:
            return
        try:
            d["scroll"].takeWidget()
        except Exception:
            pass
        pl, i = d.get("layout"), d.get("index", -1)
        try:
            if pl is not None and hasattr(pl, "insertWidget"):
                pl.insertWidget(i if i >= 0 else pl.count(), g)
            elif d.get("parent") is not None:
                g.setParent(d["parent"])
            g.show()
        except Exception as exc:
            print("[launch bay] could not dock %s back: %s" % (attr, exc))
        d["dialog"] = None
        refresh(host)
    dlg.finished.connect(dock)
    dlg.show(); refresh(host)
    return dlg


def dock_all(host):
    for attr, *_ in GEOMETRICS:
        d = _dock_info(host).get(attr)
        if d and d.get("dialog") is not None:
            d["dialog"].close()


# ------------------------------------------------------------------ the two bays
def refresh(host):
    for attr, label, _t in GEOMETRICS:
        b = (getattr(host, "_r102_geo_buttons", {}) or {}).get(attr)
        if b is None:
            continue
        out = is_out(host, attr)
        b.setText("%s\n   %s" % (label, "in a window · raise" if out else "docked · pop out"))
        b.setProperty("geoOut", "true" if out else "false"); b.style().unpolish(b); b.style().polish(b)


def _bay(title):
    from PyQt6.QtWidgets import QFrame, QVBoxLayout, QGridLayout, QLabel
    fr = QFrame(); fr.setObjectName("launchBay"); fr.setStyleSheet(BAY_CSS)
    v = QVBoxLayout(fr); v.setContentsMargins(10, 8, 10, 10); v.setSpacing(8)
    t = QLabel(title); t.setObjectName("launchTitle"); v.addWidget(t)
    grid = QGridLayout(); grid.setSpacing(8); v.addLayout(grid)
    return fr, v, grid


def _big(text, tip, cb):
    from PyQt6.QtWidgets import QPushButton, QSizePolicy
    b = QPushButton(text); b.setToolTip(tip); b.setMinimumHeight(66)
    b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed); b.clicked.connect(cb)
    return b


def attach(host, arc):
    """Put the two launch bays at the top of the ring view's left / right areas (idempotent)."""
    if getattr(arc, "_r102_launch_bay", None):
        return arc._r102_launch_bay
    left_l, right_l = getattr(arc, "left_layout", None), getattr(arc, "right_layout", None)
    if left_l is None or right_l is None:
        return None
    from PyQt6.QtWidgets import QPushButton
    lf, lv, lg = _bay("🌀 Multidim · launchers")
    for i, (which, text, tip) in enumerate(EDITORS):
        lg.addWidget(_big(text, tip + ("  (Ctrl+Alt+M)" if which == "multidim" else ""),
                          lambda _=False, w=which: open_editor(host, w)), i // 2, i % 2)
    mpm = QPushButton("🧬 Master Mod Path Matrix  (Ctrl+Alt+P)"); mpm.setObjectName("bayWide")
    mpm.clicked.connect(lambda: __import__("mod_matrix").open_window(host)); lv.addWidget(mpm)

    rf, rv, rg = _bay("◆ Geometrics · settings")
    host._r102_geo_buttons = {}
    for i, (attr, label, title) in enumerate(GEOMETRICS):
        b = _big(label, "%s: pop out into its own window; close it to dock back  (Ctrl+Alt+%d)" % (title, i + 1),
                 lambda _=False, a=attr, t=title: popout(host, a, t))
        if getattr(host, attr, None) is None:
            b.setEnabled(False); b.setToolTip(title + " is not available in this build")
        rg.addWidget(b, i // 2, i % 2); host._r102_geo_buttons[attr] = b
    da = QPushButton("⤓ Dock all geometrics"); da.setObjectName("bayWide"); da.clicked.connect(lambda: dock_all(host)); rv.addWidget(da)

    left_l.insertWidget(0, lf); right_l.insertWidget(0, rf)
    _shortcuts(host)
    refresh(host)
    # the sphere's small lower-left buttons are superseded by the bay
    host._r102_launch_bay = True
    md = getattr(arc, "_md", None)
    for n in ("_btn_toggle", "_btn_panel_script", "_btn_panel_domain", "_btn_panel_patch"):
        b = getattr(md, n, None)
        if b is not None:
            b.hide()
    arc._r102_launch_bay = (lf, rf)
    return arc._r102_launch_bay


def _shortcuts(host):
    if getattr(host, "_r102_bay_shortcuts", None):
        return
    try:
        from PyQt6.QtGui import QKeySequence, QShortcut
    except Exception:
        return
    keys = [("Ctrl+Alt+M", lambda: open_editor(host, "multidim")),
            ("Ctrl+Alt+P", lambda: __import__("mod_matrix").open_window(host))]
    for i, (attr, _l, title) in enumerate(GEOMETRICS):
        keys.append(("Ctrl+Alt+%d" % (i + 1), lambda a=attr, t=title: popout(host, a, t)))
    sc = []
    for k, fn in keys:
        s = QShortcut(QKeySequence(k), host); s.activated.connect(fn); sc.append(s)
    host._r102_bay_shortcuts = sc
