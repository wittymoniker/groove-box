"""jam_tools.py: Live Jam modernisation + 23 inline accessories scattered where they are used.

LIVE JAM (12): tap tempo · scale lock · macro snapshots A/B with a morph fader · humanise (seeded jitter) ·
  macro LFO · XY pad (two macros) · motion looper (record and loop macro moves) · freeze · panic (back to
  centre) · session clock with bar counter · energy scope · event heat meter
MOD MATRIX (4): duplicate row · solo row · randomise amounts (seeded) · invert row
FILE MANAGER (2): copy path · provenance summary of the selected file
MULTIDIM MIRRORS (2): snapshot the mirror to PNG · sync mirrors to the matrix rate
TASK PAD (3): stopwatch · quick note (saved with the session) · colour picker that copies a hex code

All accessories work on the Qt thread with QTimers (no sleeps). They move the same sliders and rows a person
would, so the jam controller, the matrix and the exports see ordinary user input.
"""
from __future__ import annotations
import math
import random
import time

MODERN_CSS = """
QDialog { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #070c18, stop:1 #0d1426); color:#edf5ff; }
QGroupBox { border:1px solid rgba(120,110,230,110); border-radius:14px; margin-top:12px; padding:10px;
            color:#cdb8ff; font-weight:900; background:rgba(22,28,52,170); }
QGroupBox::title { subcontrol-origin: margin; left:12px; padding:0 6px; }
QPushButton { background:rgba(40,70,120,190); color:#f2f7ff; border:1px solid rgba(110,180,240,160); border-radius:10px;
              padding:8px 13px; font-weight:800; }
QPushButton:hover { background:rgba(60,100,170,220); border-color:#8fe8ff; }
QPushButton:checked { background:rgba(170,40,90,220); border:2px solid #ff7ca8; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background:rgba(14,26,48,220); border:1px solid rgba(80,150,200,170);
              border-radius:8px; color:#fff; padding:6px; }
QSlider::groove:horizontal { height:8px; background:rgba(50,70,110,200); border-radius:4px; }
QSlider::sub-page:horizontal { background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #3fd2c4, stop:1 #9b7bff); border-radius:4px; }
QSlider::handle:horizontal { width:18px; margin:-6px 0; border-radius:9px; background:#e8fffb; border:2px solid #55e0d0; }
QProgressBar { background:rgba(10,18,34,220); border:1px solid rgba(70,120,170,170); border-radius:7px; text-align:center;
               color:#fff; min-height:18px; }
QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #27c7ae, stop:0.7 #f7d046, stop:1 #ff5c7a); border-radius:6px; }
QLabel { color:#e3edfa; }
"""


def _seed_rng(host, salt):
    try:
        s = str(host.get_numeric_seed())
    except Exception:
        s = "0"
    return random.Random(s + "|" + salt)


# ------------------------------------------------------------------ Live Jam
def modernize_live_jam(dlg):
    """Restyle the Live Jam dialog and add the accessories group (idempotent)."""
    if getattr(dlg, "_r101_jam_tools", False):
        return
    dlg._r101_jam_tools = True
    from PyQt6.QtCore import Qt, QTimer, QPointF
    from PyQt6.QtGui import QPainter, QColor, QPen
    from PyQt6.QtWidgets import (QGroupBox, QGridLayout, QPushButton, QLabel, QComboBox, QSlider, QCheckBox, QWidget,
                                 QProgressBar, QDoubleSpinBox)
    dlg.setStyleSheet(MODERN_CSS)
    for bar in (getattr(dlg, "level_meter", None), getattr(dlg, "peak_meter", None)):
        if bar is not None:
            bar.setMinimumHeight(22)
    host = dlg.host; sliders = getattr(dlg, "macro_sliders", {}) or {}; keys = list(sliders)
    body = getattr(dlg, "_scroll_body", None); lay = body.layout() if body is not None else dlg.layout()
    box = QGroupBox("ACCESSORIES · tempo · scale · snapshots · motion · performance"); g = QGridLayout(box)
    st = {"taps": [], "A": None, "B": None, "loop": [], "rec": False, "rec_t0": 0.0, "play": False, "frozen": None,
          "t0": time.monotonic(), "events": 0, "energy": [0.0] * 120}

    def vals():
        return {k: s.value() for k, s in sliders.items()}

    def setv(d):
        for k, v in d.items():
            if k in sliders and (st["frozen"] is None):
                sliders[k].setValue(int(round(v)))

    # 1 tap tempo
    tap = QPushButton("👆 Tap tempo"); tap_lab = QLabel("—")

    def do_tap():
        now = time.monotonic(); st["taps"] = [t for t in st["taps"] if now - t < 3.0] + [now]
        if len(st["taps"]) >= 3:
            iv = [b - a for a, b in zip(st["taps"], st["taps"][1:])]; bpm = 60.0 / (sum(iv) / len(iv))
            tap_lab.setText("%.1f BPM" % bpm)
            try: host.spin_bpm.setValue(round(bpm, 1))
            except Exception: pass
    tap.clicked.connect(do_tap); g.addWidget(tap, 0, 0); g.addWidget(tap_lab, 0, 1)
    # 2 scale lock
    scale = QComboBox(); scale.addItems(["off", "major", "minor", "dorian", "pentatonic", "minor-pent", "lydian", "hirajoshi"])
    scale.setToolTip("Scale lock: jam pitches are snapped to this scale (stored on the jam controller)")
    scale.currentTextChanged.connect(lambda v: setattr(dlg.controller, "scale_lock", None if v == "off" else v))
    g.addWidget(QLabel("Scale lock"), 0, 2); g.addWidget(scale, 0, 3)
    # 3 snapshots A/B + morph
    ba, bb = QPushButton("Store A"), QPushButton("Store B"); morph = QSlider(Qt.Orientation.Horizontal); morph.setRange(0, 100)
    ba.clicked.connect(lambda: st.__setitem__("A", vals())); bb.clicked.connect(lambda: st.__setitem__("B", vals()))

    def do_morph(v):
        if st["A"] and st["B"]:
            u = v / 100.0; setv({k: (1 - u) * st["A"][k] + u * st["B"].get(k, st["A"][k]) for k in st["A"]})
    morph.valueChanged.connect(do_morph)
    g.addWidget(ba, 1, 0); g.addWidget(bb, 1, 1); g.addWidget(QLabel("A ⇄ B"), 1, 2); g.addWidget(morph, 1, 3)
    # 4 humanise
    hum = QPushButton("🎲 Humanise"); hum.setToolTip("Seeded small jitter on every macro")

    def do_hum():
        r = _seed_rng(host, "humanise-%d" % int(time.time() * 10)); setv({k: max(0, min(100, v + r.uniform(-7, 7))) for k, v in vals().items()})
    hum.clicked.connect(do_hum); g.addWidget(hum, 2, 0)
    # 5 macro LFO
    lfo_k = QComboBox(); lfo_k.addItems(["(none)"] + keys); lfo_r = QDoubleSpinBox(); lfo_r.setRange(0.02, 4.0); lfo_r.setValue(0.25); lfo_r.setSuffix(" Hz")
    g.addWidget(QLabel("Macro LFO"), 2, 1); g.addWidget(lfo_k, 2, 2); g.addWidget(lfo_r, 2, 3)
    # 6 XY pad
    xy_a = QComboBox(); xy_a.addItems(keys); xy_b = QComboBox(); xy_b.addItems(keys)
    if len(keys) > 1: xy_b.setCurrentIndex(1)

    class Pad(QWidget):
        def __init__(self):
            super().__init__(); self.setMinimumSize(180, 120); self.p = QPointF(0.5, 0.5)

        def paintEvent(self, _e):
            q = QPainter(self); q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.fillRect(self.rect(), QColor(14, 24, 44, 220)); q.setPen(QPen(QColor(90, 160, 220, 90)))
            for i in range(1, 4):
                q.drawLine(int(self.width() * i / 4), 0, int(self.width() * i / 4), self.height())
                q.drawLine(0, int(self.height() * i / 4), self.width(), int(self.height() * i / 4))
            q.setBrush(QColor(85, 224, 208)); q.setPen(Qt.PenStyle.NoPen)
            q.drawEllipse(QPointF(self.p.x() * self.width(), (1 - self.p.y()) * self.height()), 7, 7); q.end()

        def mouseMoveEvent(self, e):
            x = max(0.0, min(1.0, e.position().x() / max(1, self.width()))); y = max(0.0, min(1.0, 1 - e.position().y() / max(1, self.height())))
            self.p = QPointF(x, y); self.update(); setv({xy_a.currentText(): x * 100, xy_b.currentText(): y * 100})
            if st["rec"]: st["loop"].append((time.monotonic() - st["rec_t0"], vals()))
        mousePressEvent = mouseMoveEvent
    pad = Pad(); g.addWidget(QLabel("XY pad"), 3, 0); g.addWidget(xy_a, 3, 1); g.addWidget(xy_b, 3, 2); g.addWidget(pad, 4, 0, 2, 4)
    # 7 motion looper
    rec = QPushButton("⏺ Record motion"); rec.setCheckable(True); play = QPushButton("🔁 Loop motion"); play.setCheckable(True)
    rec.toggled.connect(lambda on: st.update(rec=on, rec_t0=time.monotonic(), loop=[] if on else st["loop"]))
    play.toggled.connect(lambda on: st.update(play=on, play_t0=time.monotonic()))
    for k, s in sliders.items():
        s.valueChanged.connect(lambda _v: st["rec"] and st["loop"].append((time.monotonic() - st["rec_t0"], vals())))
    g.addWidget(rec, 6, 0); g.addWidget(play, 6, 1)
    # 8 freeze · 9 panic
    frz = QCheckBox("❄ Freeze"); frz.toggled.connect(lambda on: st.__setitem__("frozen", vals() if on else None))
    pan = QPushButton("⛑ Panic (centre)"); pan.clicked.connect(lambda: (frz.setChecked(False), setv({k: 50 for k in keys})))
    g.addWidget(frz, 6, 2); g.addWidget(pan, 6, 3)
    # 10 session clock · 11 energy scope · 12 heat
    clock = QLabel("00:00 · bar 1"); clock.setStyleSheet("color:#8be2d7;font-weight:900;font-size:12pt;")
    heat = QProgressBar(); heat.setRange(0, 100); heat.setFormat("event heat %p%")

    class Scope(QWidget):
        def __init__(self):
            super().__init__(); self.setMinimumHeight(54)

        def paintEvent(self, _e):
            q = QPainter(self); q.setRenderHint(QPainter.RenderHint.Antialiasing); q.fillRect(self.rect(), QColor(10, 16, 30, 200))
            e = st["energy"]; w = self.width() / max(1, len(e) - 1); q.setPen(QPen(QColor(155, 123, 255, 200), 1.5))
            for i in range(1, len(e)):
                q.drawLine(int((i - 1) * w), int(self.height() * (1 - e[i - 1])), int(i * w), int(self.height() * (1 - e[i])))
            q.end()
    scope = Scope(); g.addWidget(clock, 7, 0, 1, 2); g.addWidget(heat, 7, 2, 1, 2); g.addWidget(scope, 8, 0, 1, 4)
    for k, s in sliders.items():
        s.valueChanged.connect(lambda _v: st.__setitem__("events", st["events"] + 1))
    lay.addWidget(box)

    def tick():
        if not dlg.isVisible():
            return
        now = time.monotonic()
        if lfo_k.currentText() in sliders and st["frozen"] is None:
            sliders[lfo_k.currentText()].setValue(int(50 + 45 * math.sin(2 * math.pi * lfo_r.value() * (now - st["t0"]))))
        if st["play"] and st["loop"] and not st["rec"]:
            span = st["loop"][-1][0] or 1.0; u = (now - st.get("play_t0", now)) % span
            frame = min(st["loop"], key=lambda f: abs(f[0] - u)); setv(frame[1])
        if st["frozen"] is not None:
            for k, v in st["frozen"].items():
                if sliders[k].value() != v:
                    sliders[k].blockSignals(True); sliders[k].setValue(v); sliders[k].blockSignals(False)
        el = now - st["t0"]
        try: bpm = float(host.spin_bpm.value())
        except Exception: bpm = 120.0
        clock.setText("%02d:%02d · bar %d" % (el // 60, el % 60, 1 + int(el * bpm / 240.0)))
        try: lv = dlg.level_meter.value() / 1000.0
        except Exception: lv = 0.0
        st["energy"] = st["energy"][1:] + [lv]; scope.update()
        heat.setValue(min(100, st["events"] * 4)); st["events"] = max(0, st["events"] - 1)
    t = QTimer(dlg); t.setInterval(50); t.timeout.connect(tick); t.start(); dlg._r101_jam_timer = t


# ------------------------------------------------------------------ Mod Matrix
def matrix_accessories(app, layout, refresh):
    from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QSpinBox, QLabel
    import mod_matrix as mm
    row = QHBoxLayout(); layout.addLayout(row)
    pick = QSpinBox(); pick.setRange(1, 999); pick.setPrefix("row "); row.addWidget(QLabel("Row tools")); row.addWidget(pick)

    def sel():
        rs = mm.rows(app); i = pick.value() - 1
        return (rs, i) if 0 <= i < len(rs) else (rs, None)

    def dup():
        rs, i = sel()
        if i is not None:
            rs.insert(i + 1, {k: v for k, v in rs[i].items() if not k.startswith("_") and k != "base"}); refresh()

    def solo():
        rs, i = sel()
        if i is not None:
            on = not rs[i].get("_solo")
            for j, r in enumerate(rs):
                r["_solo"] = (j == i and on); r["enabled"] = (not on) or j == i
            refresh()

    def rand():
        r = _seed_rng(app, "matrix-amounts")
        for x in mm.rows(app):
            x["amount"] = round(r.uniform(0.1, 0.9), 3)
        refresh()

    def inv():
        rs, i = sel()
        if i is not None:
            rs[i]["amount"] = -float(rs[i].get("amount", 0.5)); refresh()
    for text, fn in (("⧉ Duplicate", dup), ("◎ Solo", solo), ("🎲 Amounts", rand), ("± Invert", inv)):
        b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
    row.addStretch(1)


# ------------------------------------------------------------------ File Manager
def file_accessories(dialog, layout):
    from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QApplication
    row = QHBoxLayout(); layout.addLayout(row)

    def copy_path():
        ps = dialog._selected_paths(); QApplication.clipboard().setText("\n".join(ps)); dialog.lbl_status.setText("copied %d path(s)" % len(ps))

    def prov():
        ps = dialog._selected_paths()
        if ps:
            import provenance
            dialog.lbl_status.setText(provenance.summary(provenance.lookup(ps[0])))
    for text, fn in (("📋 Copy path", copy_path), ("🧾 Provenance", prov)):
        b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
    row.addStretch(1)


# ------------------------------------------------------------------ Multidim mirrors
def mirror_accessories(app, panel, stage):
    from PyQt6.QtWidgets import QPushButton
    lay = panel.layout()

    def snap():
        import os, groovebox_paths
        p = os.path.join(groovebox_paths.base_dir(), "mirror-%s.png" % time.strftime("%Y%m%d-%H%M%S")); stage.grab().save(p)
        try: __import__("notify_center").notify(app, "mirror saved: " + p)
        except Exception: pass

    def sync():
        try: stage._phase = 0.0
        except Exception: pass
    for text, fn in (("📸", snap), ("⟲", sync)):
        b = QPushButton(text); b.setFixedWidth(30); b.clicked.connect(fn); b.setToolTip({"📸": "Save this mirror as PNG", "⟲": "Re-sync the mirror's motion"}[text])
        lay.itemAt(0).layout().addWidget(b)


# ------------------------------------------------------------------ Task Pad
def taskpad_accessories(app, layout):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QLabel, QLineEdit, QColorDialog, QApplication
    row = QHBoxLayout(); layout.addLayout(row)
    sw = QPushButton("⏱ 00:00"); sw.setCheckable(True); st = {"t0": 0.0}
    tm = QTimer(sw); tm.setInterval(500)
    tm.timeout.connect(lambda: sw.setText("⏱ %02d:%02d" % divmod(int(time.monotonic() - st["t0"]), 60)))
    sw.toggled.connect(lambda on: (st.__setitem__("t0", time.monotonic()), tm.start()) if on else tm.stop())
    note = QLineEdit(getattr(app, "r101_quick_note", "")); note.setPlaceholderText("quick note (saved with the session)")
    note.textChanged.connect(lambda t: setattr(app, "r101_quick_note", t))
    col = QPushButton("🎨")

    def pick():
        c = QColorDialog.getColor(parent=app)
        if c.isValid():
            QApplication.clipboard().setText(c.name()); col.setStyleSheet("background:%s;" % c.name())
    col.clicked.connect(pick); col.setToolTip("Pick a colour; its hex code is copied")
    row.addWidget(sw); row.addWidget(note, 1); row.addWidget(col)
