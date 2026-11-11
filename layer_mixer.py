"""layer_mixer.py — GROOVEBOX_R32_LAYER_MIXER_20261110

LAYER MIXER: individual levels for every synthesis layer + a 3-band EQ per instrument voice.

  Levels   panel synth · vector · wavetable · ball · cellular · multidim — these are the very
           fields the renderer already mixes (geometric_synth_mixer_state + the geometric/panel
           balance), so the mixer is a clearer face on the existing engine, not a parallel one.
  3-band   low (shelf < 250 Hz) · mid (bell at 1 kHz) · high (shelf > 4 kHz), ±18 dB, global or
           per instrument; applied to the finished voice as an exact zero-phase magnitude response
           (FFT, hardcoded_fx.apply_magnitude_response) — the same method the per-step EQ uses.
  Canonical  "seeded" gives each instrument a deterministic gentle EQ tilt from the seed signature.
"""
from __future__ import annotations

import numpy as np

LEVELS = (("panel", "Panel synth"), ("vector", "Vector"), ("wavetable", "Wavetable"), ("ball", "Ball"),
          ("cellular", "Cellular"), ("multidim", "Multidim"))


def _eq_state(app):
    st = getattr(app, "r32_eq", None)
    if not isinstance(st, dict):
        st = app.r32_eq = {"global": {"low": 0.0, "mid": 0.0, "high": 0.0, "mode": "user"}, "local": {}}
    return st


def gains(app, name):
    st = _eq_state(app)
    g = dict(st["global"]); g.update({k: v for k, v in (st["local"].get(str(name)) or {}).items()})
    if g.get("mode") == "seeded":
        try:
            import groovebox as gb
            r = np.random.default_rng(gb.seed_child(int(app._seed_program_signature() or 1), "eq3", str(name)))
            g.update({"low": float(r.uniform(-4, 4)), "mid": float(r.uniform(-3, 3)), "high": float(r.uniform(-4, 4))})
        except Exception:
            pass
    return float(g.get("low", 0)), float(g.get("mid", 0)), float(g.get("high", 0))


def eq3(y, sr, low, mid, high):
    if not (low or mid or high):
        return y
    import hardcoded_fx as hfx
    x = np.asarray(y, dtype=np.float64)
    n = x.shape[0]
    f = np.fft.rfftfreq(n, 1.0 / sr)
    lf = np.log2(np.maximum(f, 1.0))
    db = (low * (1.0 / (1.0 + np.exp((lf - np.log2(250.0)) * 4.0))) +
          mid * np.exp(-0.5 * ((lf - np.log2(1000.0)) / 0.9) ** 2) +
          high * (1.0 / (1.0 + np.exp(-(lf - np.log2(4000.0)) * 4.0))))
    return hfx.apply_magnitude_response(x, 10.0 ** (db / 20.0)).astype(np.asarray(y).dtype)


def install(app):
    if getattr(app, "_r32_eq_hooked", False):
        return
    orig = getattr(app, "_render_instrument_voice", None)
    if not callable(orig):
        return

    def _voice(name, hz, t, dur, sr, _orig=orig):
        out = _orig(name, hz, t, dur, sr)
        try:
            lo, mi, hi = gains(app, name)
            if lo or mi or hi:
                return eq3(out, sr, lo, mi, hi)
        except Exception:
            pass
        return out
    app._render_instrument_voice = _voice
    app._r32_eq_hooked = True


def make_panel(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QSlider, QComboBox
    install(app)
    b = QGroupBox("🎚 LAYER MIXER · levels · 3-band EQ")
    b.setStyleSheet("QGroupBox{color:#ff9e64;background:#000000;border:1px solid #ff9e64;border-radius:7px;margin-top:6px;"
                    "padding-top:10px;font-weight:900;}QLabel{color:#ffffff;font-size:8pt;}")
    g = QGridLayout(b); g.setSpacing(2)
    st = getattr(app, "geometric_synth_mixer_state", None) or {}
    for c, (k, cap) in enumerate(LEVELS):
        s = QSlider(Qt.Orientation.Vertical); s.setRange(0, 100); s.setMinimumHeight(70)
        if k == "panel":
            # The renderer's own Panel ◀ ▶ Geometric balance (25–75): this fader drives that slider.
            ps = getattr(app, "slider_geo_panel_mix", None)
            s.setRange(25, 75); s.setInvertedAppearance(False)
            s.setValue(100 - int(ps.value()) if ps is not None else 50)
            s.setToolTip("Panel synth share against the four geometric synths (the main window's Panel ◀ ▶ Geometric slider)")
            if ps is not None:
                s.valueChanged.connect(lambda v, _ps=ps: _ps.setValue(100 - int(v)))
        else:
            s.setValue(int(round(100 * float(st.get(k, 0.7)))))
            s.valueChanged.connect(lambda v, kk=k: (app.geometric_synth_mixer_state.__setitem__(kk, v / 100.0), getattr(app, "_on_live_source_changed", lambda: None)()))
        g.addWidget(s, 0, c, alignment=Qt.AlignmentFlag.AlignHCenter); g.addWidget(QLabel(cap), 1, c, alignment=Qt.AlignmentFlag.AlignHCenter)
    scope = QComboBox(); scope.addItems(["EQ: global", "EQ: selected instrument"]); mode = QComboBox(); mode.addItems(["user", "seeded"])
    g.addWidget(scope, 2, 0, 1, 3); g.addWidget(mode, 2, 3, 1, 3)
    eqs = {}
    for c, k in enumerate(("low", "mid", "high")):
        s = QSlider(Qt.Orientation.Horizontal); s.setRange(-180, 180); eqs[k] = s
        g.addWidget(QLabel(k + " dB"), 3 + c, 0); g.addWidget(s, 3 + c, 1, 1, 5)

    def rec():
        e = _eq_state(app)
        if scope.currentIndex() == 0:
            return e["global"]
        n = app.instrument_selector_dropdown.currentText() if hasattr(app, "instrument_selector_dropdown") else ""
        return e["local"].setdefault(n, {})

    def load(*_):
        r = rec()
        for k, s in eqs.items():
            s.blockSignals(True); s.setValue(int(round(10 * float(r.get(k, 0))))); s.blockSignals(False)
        mode.blockSignals(True); mode.setCurrentText(r.get("mode", "user")); mode.blockSignals(False)

    def save(*_):
        r = rec(); r.update({k: s.value() / 10.0 for k, s in eqs.items()}); r["mode"] = mode.currentText()
        getattr(app, "_on_live_source_changed", lambda: None)()
    for s in eqs.values():
        s.valueChanged.connect(save)
    mode.currentIndexChanged.connect(save); scope.currentIndexChanged.connect(load)
    if hasattr(app, "instrument_selector_dropdown"):
        app.instrument_selector_dropdown.currentIndexChanged.connect(lambda *_: scope.currentIndex() and load())
    load()
    return b
