"""synth_engine_panel.py — GROOVEBOX_R32_SYNTH_ENGINE_20261110

MASTER SYNTH ▸ ENGINE: voice-level settings for every instrument (global) or the selected one
(local), applied inside the instrument voice render. All defaults are exact identity.

  Unison 1–7 voices · Detune (cents, symmetric) · Analog drift (deterministic slow pitch wander)
  Sub-octave mix · Octave-up mix · Fifth mix · Wavefold (sine fold, synthesis not FX)
  Attack / Release (ms, isn curves) · Velocity curve (level ↔ seed index)
  Quality: render the voice at 2× and decimate by pair-averaging (cleaner highs)
Canonical mode: the selected values can be seeded per instrument (deterministic).
"""
from __future__ import annotations

import math

import numpy as np

DEFAULTS = {"unison": 1, "detune": 0.0, "drift": 0.0, "sub": 0.0, "oct": 0.0, "fifth": 0.0, "fold": 0.0,
            "attack_ms": 0.0, "release_ms": 0.0, "velocity": 0.0, "quality2x": False, "mode": "user"}
CONTROLS = (("unison", "Unison voices", 1, 7, 1), ("detune", "Detune (cents)", 0, 50, 1), ("drift", "Analog drift", 0, 100, 1),
            ("sub", "Sub-octave mix", 0, 100, 1), ("oct", "Octave-up mix", 0, 100, 1), ("fifth", "Fifth mix", 0, 100, 1),
            ("fold", "Wavefold", 0, 100, 1), ("attack_ms", "Attack ms", 0, 2000, 5), ("release_ms", "Release ms", 0, 4000, 5),
            ("velocity", "Velocity spread", 0, 100, 1))
PCT = {"drift", "sub", "oct", "fifth", "fold", "velocity"}


def _state(app, scope, name=""):
    st = app.__dict__.setdefault("r32_synth_engine", {"global": dict(DEFAULTS), "local": {}})
    return st["global"] if scope == "global" else st["local"].setdefault(name, {})


def effective(app, name):
    g = _effective_raw(app, name)
    try:
        import r32_rowctx
        u = r32_rowctx.num("unison", None, 1, 7)
        if u is not None:
            g["unison"] = int(u)
    except Exception:
        pass
    return g


def _effective_raw(app, name):
    g = dict(DEFAULTS); g.update(_state(app, "global"))
    g.update({k: v for k, v in _state(app, "local", name).items() if k != "mode"})
    if g.get("mode") == "canonical" or _state(app, "local", name).get("mode") == "canonical":
        try:
            import groovebox as gb
            r = np.random.default_rng(gb.seed_child(int(app._seed_program_signature() or 1), "synth_engine", name))
            g.update({"unison": int(r.integers(1, 4)), "detune": float(r.uniform(0, 14)), "drift": float(r.uniform(0, .3)),
                      "sub": float(r.uniform(0, .3)), "fold": float(r.uniform(0, .25))})
        except Exception:
            pass
    return g


def _identity(s):
    return (int(s["unison"]) <= 1 and not s["drift"] and not s["sub"] and not s["oct"] and not s["fifth"] and not s["fold"]
            and not s["attack_ms"] and not s["release_ms"] and not s["velocity"] and not s["quality2x"])


def _isn_ramp(n):
    return (np.sin(np.linspace(0, math.pi / 2, max(1, n))) ** 2)


def install(app):
    if getattr(app, "_r32_engine_hooked", False):
        return
    orig = getattr(app, "_render_instrument_voice", None)
    if not callable(orig):
        return

    def _voice(name, hz, t, dur, sr, _orig=orig):
        # Blueprint "active instruments": instruments past the count stay silent.
        n_act = getattr(app, "r32_active_instruments", None)
        if n_act:
            try:
                if (getattr(app, "instrument_names_48", None) or []).index(str(name)) >= int(n_act):
                    return np.zeros(np.asarray(t).shape, dtype=np.float32)
            except ValueError:
                pass
        s = effective(app, str(name))
        if _identity(s):
            return _orig(name, hz, t, dur, sr)
        try:
            t = np.asarray(t, dtype=np.float64)
            if s["quality2x"] and t.size > 1:
                t2 = np.linspace(t[0], t[-1] + (t[1] - t[0]) / 2, t.size * 2)
                base = np.asarray(_orig(name, hz, t2, dur, sr * 2), dtype=np.float64)
                base = base.reshape(-1, 2).mean(axis=1) if base.size == t.size * 2 else np.asarray(_orig(name, hz, t, dur, sr), dtype=np.float64)
            else:
                base = np.asarray(_orig(name, hz, t, dur, sr), dtype=np.float64)
            if base.ndim != 1:
                return base
            out = base.copy()
            n = int(max(1, min(7, s["unison"])))
            if n > 1:
                cents = np.linspace(-1, 1, n) * float(s["detune"])
                out = np.zeros_like(base)
                for c in cents:
                    out += np.asarray(_orig(name, hz * 2 ** (c / 1200.0), t, dur, sr), dtype=np.float64) if c else base
                out /= math.sqrt(n)
            if s["drift"]:
                try:
                    import signal_integration as si
                    w = np.array([si.det_noise(hash(name) & 0xFFFF, tt, 0.7) for tt in t[:: max(1, t.size // 256)]])
                    w = np.interp(np.arange(t.size), np.linspace(0, t.size - 1, w.size), w)
                    shift = 1.0 + float(s["drift"]) * 0.006 * w
                    idx = np.clip(np.cumsum(shift) - shift[0], 0, out.size - 1)
                    out = np.interp(idx, np.arange(out.size), out)
                except Exception:
                    pass
            for key, ratio in (("sub", 0.5), ("oct", 2.0), ("fifth", 1.5)):
                if s[key] and hz * ratio < sr / 2:
                    out = out + float(s[key]) * np.asarray(_orig(name, hz * ratio, t, dur, sr), dtype=np.float64)
            if s["fold"]:
                k = 1.0 + 6.0 * float(s["fold"])
                out = np.sin(out * k * math.pi / 2) / max(1.0, k * 0.35)
            if s["velocity"]:
                try:
                    vi = (int(app._instance_slot(str(name))) * 0.618034) % 1.0
                except Exception:
                    vi = 0.5
                out *= 1.0 - float(s["velocity"]) * vi * 0.6
            a = int(float(s["attack_ms"]) * sr / 1000.0); r = int(float(s["release_ms"]) * sr / 1000.0)
            if a > 1:
                a = min(a, out.size); out[:a] *= _isn_ramp(a)
            if r > 1:
                r = min(r, out.size); out[-r:] *= _isn_ramp(r)[::-1]
            return out.astype(np.asarray(base).dtype)
        except Exception:
            return _orig(name, hz, t, dur, sr)
    app._render_instrument_voice = _voice
    app._r32_engine_hooked = True


def make_panel(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QSlider, QComboBox, QCheckBox, QPushButton
    install(app)
    box = QGroupBox("MASTER SYNTH ▸ ENGINE · unison · drift · sub/oct/fifth · fold · envelope · quality")
    box.setStyleSheet("QGroupBox{color:#ffd166;background:#000000;border:1px solid #ffd166;border-radius:7px;margin-top:6px;"
                      "padding-top:10px;font-weight:900;}QLabel,QCheckBox{color:#ffffff;font-size:8pt;}")
    g = QGridLayout(box); g.setContentsMargins(5, 9, 5, 4)
    scope = QComboBox(); scope.addItems(["Global (every instrument)", "Local (selected instrument)"])
    mode = QComboBox(); mode.addItems(["User", "Canonical (seeded)"])
    q2 = QCheckBox("Quality 2× (cleaner highs, 2× render cost)")
    g.addWidget(QLabel("Scope"), 0, 0); g.addWidget(scope, 0, 1); g.addWidget(QLabel("Mode"), 0, 2); g.addWidget(mode, 0, 3)
    sl = {}

    def rec():
        if scope.currentIndex() == 0:
            return _state(app, "global")
        name = app.instrument_selector_dropdown.currentText() if hasattr(app, "instrument_selector_dropdown") else ""
        return _state(app, "local", name)

    def load(*_):
        r = dict(DEFAULTS); r.update(rec())
        mode.blockSignals(True); mode.setCurrentIndex(1 if r.get("mode") == "canonical" else 0); mode.blockSignals(False)
        q2.blockSignals(True); q2.setChecked(bool(r.get("quality2x"))); q2.blockSignals(False)
        for k, w in sl.items():
            w.blockSignals(True); w.setValue(int(round(float(r.get(k, 0)) * (100 if k in PCT else 1)))); w.blockSignals(False)

    def changed(*_):
        r = rec(); r["mode"] = "canonical" if mode.currentIndex() else "user"; r["quality2x"] = q2.isChecked()
        for k, w in sl.items():
            r[k] = w.value() / 100.0 if k in PCT else (int(w.value()) if k == "unison" else float(w.value()))
        f = getattr(app, "_on_live_source_changed", None)
        if callable(f):
            try: f()
            except Exception: pass

    for i, (k, cap, lo, hi, step) in enumerate(CONTROLS):
        w = QSlider(Qt.Orientation.Horizontal); w.setRange(lo, hi); w.setSingleStep(step); w.valueChanged.connect(changed)
        sl[k] = w; r, c = 1 + i // 2, (i % 2) * 2
        g.addWidget(QLabel(cap), r, c); g.addWidget(w, r, c + 1)
    row = 2 + len(CONTROLS) // 2
    g.addWidget(q2, row, 0, 1, 2)
    b = QPushButton("Reset (identity)"); b.clicked.connect(lambda: (rec().clear(), rec().update(DEFAULTS) if scope.currentIndex() == 0 else None, load(), changed()))
    g.addWidget(b, row, 2, 1, 2)
    mode.currentIndexChanged.connect(changed); q2.toggled.connect(changed); scope.currentIndexChanged.connect(load)
    if hasattr(app, "instrument_selector_dropdown"):
        app.instrument_selector_dropdown.currentIndexChanged.connect(load)
    load()
    return box
