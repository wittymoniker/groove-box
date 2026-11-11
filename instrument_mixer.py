"""instrument_mixer.py — GROOVEBOX_R32_INSTRUMENT_MIXER_20261110

Per-instrument channel strips: gain (dB), mute, solo, and a CANONICAL balance option where the
seed program sets each instrument's level (deterministic: same seed → same balance).  Applied
in the voice render chain (live keys, Play, every export), saved with the project
(project_schema key "inst_mix"), part of the mixdown cache key.

State  app.r32_inst_mix = {"mode": "user"|"canonical", "depth": 0..1,
                           "strips": {name: {"db": 0.0, "mute": False, "solo": False}}}
Defaults are neutral (0 dB, nothing muted) — the mixer changes nothing until touched.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np


def state(app):
    st = getattr(app, "r32_inst_mix", None)
    if not isinstance(st, dict):
        st = app.r32_inst_mix = {"mode": "user", "depth": 0.5, "strips": {}}
    st.setdefault("mode", "user"); st.setdefault("depth", 0.5); st.setdefault("strips", {})
    return st


def names(app):
    for attr in ("instrument_names_48", "instrument_names"):
        v = getattr(app, attr, None)
        if isinstance(v, (list, tuple)) and v:
            return list(v)
    return list((getattr(app, "instrument_sequencer_memory", {}) or {}).keys())


def _canonical_db(app, name, depth):
    try:
        sig = str(app._seed_program_signature())
    except Exception:
        sig = str(getattr(app, "seed", 0))
    h = hashlib.blake2b(("%s|%s" % (sig, name)).encode(), digest_size=4).digest()
    u = int.from_bytes(h, "little") / 2 ** 32                 # 0..1
    return (u - 0.5) * 24.0 * float(depth)                     # ±12 dB at depth 1


def gain(app, name):
    st = state(app); strips = st["strips"]
    if not strips and st["mode"] == "user" and not st.get("canonical_follow", True):
        return 1.0
    soloed = [n for n, s in strips.items() if s.get("solo")]
    s = strips.get(name, {})
    if s.get("mute") or (soloed and name not in soloed):
        return 0.0
    db = float(s.get("db", 0.0) or 0.0)
    if st["mode"] == "canonical":
        db += _canonical_db(app, name, st.get("depth", 0.5))
    elif st.get("canonical_follow", True):
        try:   # R32.8: active canonicals drive the master / local mixers in proportion to their level
            import r32_finish as _rf
            lv = _rf.canonical_level(app)
            if lv > 0:
                db += _canonical_db(app, name, 0.5 * lv)
        except Exception:
            pass
    return 10.0 ** (db / 20.0)


def install(app):
    if getattr(app, "_r32_inst_mix_hooked", False):
        return
    state(app)
    orig = app._render_instrument_voice

    def _voice(name, hz, t, dur, sr, _orig=orig):
        y = _orig(name, hz, t, dur, sr)
        g = gain(app, name)
        return y if g == 1.0 else np.asarray(y) * g
    app._render_instrument_voice = _voice
    app._r32_inst_mix_hooked = True


def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QSlider, QCheckBox, QComboBox,
                                 QScrollArea, QPushButton, QDoubleSpinBox)
    old = getattr(app, "_inst_mix_window", None)
    try:
        if old is not None:
            old.show(); old.raise_(); return old
    except RuntimeError:
        pass
    install(app)
    st = state(app)
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🎚 Instrument Mixer · gain · mute · solo · canonical balance")
    w.resize(980, 420); lay = QVBoxLayout(w)

    def changed():
        app._shared_mixdown_cache = {}
    top = QHBoxLayout(); mode = QComboBox(); mode.addItems(["user", "canonical"]); mode.setCurrentText(st["mode"])
    mode.setToolTip("canonical: the seed program sets a deterministic balance on top of your faders.")
    depth = QDoubleSpinBox(); depth.setRange(0, 1); depth.setSingleStep(0.05); depth.setValue(float(st["depth"]))
    depth.setToolTip("How far the canonical balance spreads levels (1 = ±12 dB).")
    reset = QPushButton("Reset all (0 dB, unmute, unsolo)")
    follow = QCheckBox("Canonicals drive the mixers"); follow.setChecked(bool(st.get("canonical_follow", True)))
    follow.toggled.connect(lambda v: (st.__setitem__("canonical_follow", bool(v)), changed()))
    bind = QCheckBox("Bind to Modulation Levels"); bind.setChecked(bool(st.get("bind_mod", True)))
    bind.setToolTip("Active canonicals also scale the modulation depth (Mod Osc) by their level. Uncheck to keep modulation fixed.")
    bind.toggled.connect(lambda v: (st.__setitem__("bind_mod", bool(v)), changed()))
    for x in (QLabel("Mode"), mode, QLabel("Canonical depth"), depth, follow, bind, reset):
        top.addWidget(x)
    top.addStretch(1); lay.addLayout(top)
    sc = QScrollArea(); sc.setWidgetResizable(True); holder = QWidget(); grid = QGridLayout(holder); sc.setWidget(holder)
    lay.addWidget(sc, 1)
    ctl = {}

    def strip(n):
        return st["strips"].setdefault(n, {"db": 0.0, "mute": False, "solo": False})

    for col, n in enumerate(names(app)[:128]):
        s = st["strips"].get(n, {})
        lab = QLabel(n[:10]); lab.setToolTip(n); lab.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        f = QSlider(Qt.Orientation.Vertical); f.setRange(-600, 120); f.setValue(int(10 * float(s.get("db", 0.0))))
        f.setFixedHeight(180); f.setToolTip("%s gain (dB)" % n)
        v = QLabel("%.1f" % float(s.get("db", 0.0))); v.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        m = QCheckBox("M"); m.setChecked(bool(s.get("mute"))); so = QCheckBox("S"); so.setChecked(bool(s.get("solo")))
        f.valueChanged.connect(lambda x, n=n, v=v: (strip(n).__setitem__("db", x / 10.0), v.setText("%.1f" % (x / 10.0)), changed()))
        m.toggled.connect(lambda x, n=n: (strip(n).__setitem__("mute", bool(x)), changed()))
        so.toggled.connect(lambda x, n=n: (strip(n).__setitem__("solo", bool(x)), changed()))
        for r, x in enumerate((lab, f, v, m, so)):
            grid.addWidget(x, r, col, Qt.AlignmentFlag.AlignHCenter)
        ctl[n] = (f, m, so)
    mode.currentTextChanged.connect(lambda t: (st.__setitem__("mode", t), changed()))
    depth.valueChanged.connect(lambda x: (st.__setitem__("depth", float(x)), changed()))

    def do_reset():
        st["strips"].clear()
        for f, m, so in ctl.values():
            f.setValue(0); m.setChecked(False); so.setChecked(False)
        st["strips"].clear(); changed()
    reset.clicked.connect(do_reset)
    app._inst_mix_window = w; w.show(); return w
