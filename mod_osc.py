"""mod_osc.py — GROOVEBOX_R32_SEEDED_MOD_OSC_20261110

SEEDED MOD OSC: one deterministic oscillator family across three frequency ranges.

  SUB-AUDIO   0.001 – 20 Hz (or a period in beats, tempo-locked): modulates any control in any
              window (touch it, then Assign), or a voice parameter (level, pitch) per block.
  AUDIO       20 Hz – 20 kHz: audio-rate AM (tremolo → sidebands), FM (vibrato → FM timbre),
              ring modulation, on the selected instrument (local) or every voice (global).
  SUPER-AUDIO above 20 kHz up to 8·sr: the oscillator is evaluated at the true frequency and
              sampled at the output rate, so it folds deterministically:
                  f_alias = | f − sr·round(f / sr) |
              Ring-modulating a voice with it gives a heterodyne whose beat lands back in the audible
              band — the "super-audio" range is heard as exactly reproducible difference tones.
              A readout shows where each super-audio setting folds to.

Shape (sine / triangle / saw / square / seeded S&H) and start phase come from the seed program
signature, so the same project always modulates the same way. Expression helpers: rate ×2/÷2,
"lock to tempo", depth curve (lin / exp), keytrack (rate follows the note frequency).
"""
from __future__ import annotations

import math
import time

import numpy as np

SHAPES = ("sine", "triangle", "saw", "square", "seeded S&H")
RANGES = ("sub-audio", "audio", "super-audio")
TARGETS = ("control (assign)", "voice level (AM)", "voice pitch (FM)", "ring", "voice level (sub-audio, per block)")


def _state(app):
    st = getattr(app, "r32_mod_osc", None)
    if not isinstance(st, dict):
        st = app.r32_mod_osc = {"global": {"on": False, "range": "audio", "hz": 220.0, "depth": 0.0, "shape": "sine",
                                           "target": "voice level (AM)", "keytrack": False, "beats": 0.0},
                                "local": {}}
    return st


def wave(shape, phase, seed=1):
    """phase in cycles (array). Deterministic for every shape."""
    u = np.mod(phase, 1.0)
    if shape == "triangle":
        return 4.0 * np.abs(u - 0.5) - 1.0
    if shape == "saw":
        return 2.0 * u - 1.0
    if shape == "square":
        return np.where(u < 0.5, 1.0, -1.0)
    if shape == "seeded S&H":
        k = np.floor(phase).astype(np.int64)
        h = (k * 0x9E3779B1 + int(seed) * 0x85EBCA6B) & 0xFFFFFFFF
        return (h / float(0xFFFFFFFF)) * 2.0 - 1.0
    return np.sin(2.0 * math.pi * u)


def alias_hz(f, sr):
    return abs(f - sr * round(f / float(sr)))


def effective_hz(st, hz_note, bpm):
    if st.get("beats"):
        return (bpm / 60.0) / max(1e-6, float(st["beats"]))
    f = float(st.get("hz", 1.0))
    if st.get("keytrack") and hz_note:
        f = f * float(hz_note) / 440.0
    return f


def process_voice(app, name, hz_note, t, y, sr):
    st = dict(_state(app)["global"]); st.update((_state(app)["local"].get(str(name)) or {}))
    try:
        import r32_rowctx
        dv = r32_rowctx.num("mod_depth", None, 0.0, 1.0)
        if dv is not None:
            st["depth"] = dv; st["on"] = st.get("on") or dv > 0
    except Exception:
        pass
    if not st.get("on") or float(st.get("depth", 0)) <= 0:
        return y
    tgt = st.get("target", "voice level (AM)")
    if tgt == "control (assign)":
        return y
    try:
        bpm = float(app.spin_bpm.value())
    except Exception:
        bpm = 120.0
    try:
        seed = int(app._seed_program_signature() or 1)
    except Exception:
        seed = 1
    f = effective_hz(st, hz_note, bpm)
    t = np.asarray(t, dtype=np.float64)
    ph0 = (seed % 1000) / 1000.0
    m = wave(st.get("shape", "sine"), f * t + ph0, seed)          # true frequency → folds if > sr/2
    d = float(st["depth"])
    try:   # R32.8: canonicals scale modulation unless "Bind to Modulation Levels" is unchecked
        import r32_finish as _rf
        if _rf.bind_mod_levels(app):
            lv = _rf.canonical_level(app)
            if lv > 0:
                d = min(1.0, d * (0.5 + lv))
    except Exception:
        pass
    y = np.asarray(y, dtype=np.float64)
    if y.ndim != 1 or y.size != t.size:
        return y
    if tgt.startswith("voice level"):
        out = y * (1.0 - 0.5 * d + 0.5 * d * m)
    elif tgt == "ring":
        out = (1.0 - d) * y + d * y * m
    else:   # FM: phase-modulate by resampling with a modulated read position
        dev = d * 0.02 * (1.0 if f < 20 else 0.25)                # vibrato depth / FM index
        idx = np.arange(y.size, dtype=np.float64) + dev * sr * np.cumsum(m) / max(1.0, f * 2.0 * math.pi) * (2 * math.pi * f / sr)
        out = np.interp(np.clip(idx, 0, y.size - 1), np.arange(y.size), y)
    return out.astype(np.float32)


def install(app):
    if getattr(app, "_r32_modosc_hooked", False):
        return
    orig = getattr(app, "_render_instrument_voice", None)
    if not callable(orig):
        return

    def _voice(name, hz, t, dur, sr, _orig=orig):
        out = _orig(name, hz, t, dur, sr)
        try:
            return process_voice(app, name, hz, t, out, sr)
        except Exception:
            return out
    app._render_instrument_voice = _voice
    app._r32_modosc_hooked = True


def make_panel(app, touch=None):
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import (QGroupBox, QGridLayout, QLabel, QComboBox, QDoubleSpinBox, QCheckBox, QPushButton,
                                 QAbstractSlider)
    install(app)
    b = QGroupBox("〰 SEEDED MOD OSC · sub-audio · audio · super-audio")
    b.setStyleSheet("QGroupBox{color:#9ece6a;background:#000000;border:1px solid #9ece6a;border-radius:7px;margin-top:6px;"
                    "padding-top:10px;font-weight:900;}QLabel,QCheckBox{color:#ffffff;font-size:8pt;}")
    g = QGridLayout(b); g.setSpacing(2)
    scope = QComboBox(); scope.addItems(["Global", "Local (selected)"])
    on = QCheckBox("On"); rng = QComboBox(); rng.addItems(RANGES)
    hz = QDoubleSpinBox(); hz.setDecimals(3); hz.setSuffix(" Hz")
    beats = QDoubleSpinBox(); beats.setRange(0, 64); beats.setDecimals(2); beats.setSpecialValueText("free (Hz)"); beats.setSuffix(" beats")
    depth = QDoubleSpinBox(); depth.setRange(0, 1); depth.setSingleStep(0.05)
    shape = QComboBox(); shape.addItems(SHAPES); target = QComboBox(); target.addItems(TARGETS)
    key = QCheckBox("Keytrack"); fold = QLabel("")
    x2 = QPushButton("×2"); d2 = QPushButton("÷2"); assign = QPushButton("Assign to last touched control")
    rows = (("Scope", scope), ("Range", rng), ("Rate", hz), ("Tempo lock", beats), ("Depth", depth), ("Shape", shape), ("Target", target))
    for r, (cap, w) in enumerate(rows):
        g.addWidget(QLabel(cap), r, 0); g.addWidget(w, r, 1, 1, 2)
    g.addWidget(on, 0, 3); g.addWidget(key, 1, 3); g.addWidget(x2, 2, 3); g.addWidget(d2, 3, 3)
    g.addWidget(assign, len(rows), 0, 1, 4); g.addWidget(fold, len(rows) + 1, 0, 1, 4)

    def rec():
        st = _state(app)
        if scope.currentIndex() == 0:
            return st["global"]
        n = app.instrument_selector_dropdown.currentText() if hasattr(app, "instrument_selector_dropdown") else ""
        return st["local"].setdefault(n, dict(st["global"], on=False))

    def set_range(name):
        lo, hi = {"sub-audio": (0.001, 20.0), "audio": (20.0, 20000.0), "super-audio": (20000.0, 384000.0)}[name]
        hz.blockSignals(True); hz.setRange(lo, hi); hz.setValue(max(lo, min(hi, float(rec().get("hz", lo))))); hz.blockSignals(False)

    def load(*_):
        r = rec()
        for w in (on, rng, hz, beats, depth, shape, target, key):
            w.blockSignals(True)
        on.setChecked(bool(r.get("on"))); rng.setCurrentText(r.get("range", "audio")); set_range(rng.currentText())
        hz.setValue(float(r.get("hz", 220))); beats.setValue(float(r.get("beats", 0) or 0)); depth.setValue(float(r.get("depth", 0)))
        shape.setCurrentText(r.get("shape", "sine")); target.setCurrentText(r.get("target", "voice level (AM)")); key.setChecked(bool(r.get("keytrack")))
        for w in (on, rng, hz, beats, depth, shape, target, key):
            w.blockSignals(False)
        readout()

    def save(*_):
        r = rec()
        r.update({"on": on.isChecked(), "range": rng.currentText(), "hz": hz.value(), "beats": beats.value(), "depth": depth.value(),
                  "shape": shape.currentText(), "target": target.currentText(), "keytrack": key.isChecked()})
        readout()
        getattr(app, "_on_live_source_changed", lambda: None)()

    def readout():
        f = hz.value(); sr = float(getattr(app, "play_sample_rate", 48000) or 48000)
        if rng.currentText() == "super-audio":
            fold.setText("folds at %.0f Hz output → heard at %.1f Hz (ring = difference tones)" % (sr, alias_hz(f, sr)))
        elif rng.currentText() == "sub-audio":
            fold.setText("period %.3f s%s" % (1.0 / max(1e-6, f), " · tempo-locked" if beats.value() else ""))
        else:
            fold.setText("audio-rate: AM / FM / ring sidebands at ±%.1f Hz" % f)
    rng.currentTextChanged.connect(lambda n: (set_range(n), save()))
    for w in (on, key):
        w.toggled.connect(save)
    for w in (hz, beats, depth):
        w.valueChanged.connect(save)
    for w in (shape, target):
        w.currentIndexChanged.connect(save)
    scope.currentIndexChanged.connect(load)
    x2.clicked.connect(lambda: hz.setValue(min(hz.maximum(), hz.value() * 2)))
    d2.clicked.connect(lambda: hz.setValue(max(hz.minimum(), hz.value() / 2)))

    ctl = app.__dict__.setdefault("_r32_modosc_controls", [])

    def do_assign():
        w = getattr(touch, "last", None)
        if w is None:
            fold.setText("touch a slider or spin box first"); return
        ctl.append({"w": w, "base": float(w.value())}); fold.setText("%d control(s) modulated" % len(ctl))
    assign.clicked.connect(do_assign)

    def tick():
        if not ctl:
            return
        r = _state(app)["global"]
        try:
            bpm = float(app.spin_bpm.value())
        except Exception:
            bpm = 120.0
        f = min(20.0, effective_hz(r, 0, bpm)) if r.get("range") != "sub-audio" else effective_hz(r, 0, bpm)
        try:
            seed = int(app._seed_program_signature() or 1)
        except Exception:
            seed = 1
        v = float(wave(r.get("shape", "sine"), np.array([f * time.monotonic() + (seed % 1000) / 1000.0]), seed)[0])
        d = float(r.get("depth", 0.25) or 0.25)
        for c in list(ctl):
            w = c["w"]
            try:
                span = float(w.maximum() - w.minimum())
                nv = max(w.minimum(), min(w.maximum(), c["base"] + v * d * 0.5 * span))
                w.setValue(int(round(nv)) if isinstance(w, QAbstractSlider) or isinstance(w.value(), int) else nv)
            except RuntimeError:
                ctl.remove(c)
    t = QTimer(b); t.setInterval(40); t.timeout.connect(lambda: tick() if ctl else None); t.start()   # R32.8 sweep: idle = no work
    if hasattr(app, "instrument_selector_dropdown"):
        app.instrument_selector_dropdown.currentIndexChanged.connect(lambda *_: scope.currentIndex() and load())
    load()
    return b
