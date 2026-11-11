"""predictive_fx.py — GROOVEBOX_R32_PREDICTIVE_FX_20261110

Effects that act BEFORE a note hits, DURING it, or AFTER it — any one, two or all three.
They know the note in advance because a voice is rendered whole, so "predictive" is exact,
not estimated:

  BEFORE  anticipation: a reversed, isn-swelled copy of the note's first `pre_ms` rises into
          the onset (a reverse-swell / pre-echo), and an optional "breath" dip of the previous
          tail. Amount `pre`.
  DURING  look-ahead dynamics: the gain at each instant is computed from the envelope `look_ms`
          AHEAD (signal_integration.Integrator over the future block), so peaks are tamed before
          they arrive and quiet parts lifted — no overshoot, no pumping lag. Amount `during`.
  AFTER   decay echoes: the note's tail is re-entered `echoes` times at Meum-spaced delays with a
          geometric decay inside the voice buffer (no IIR). Amount `post`.

Global or per instrument; canonical mode seeds all three amounts per instrument.
"""
from __future__ import annotations

import math

import numpy as np

MEUM = 2.0 ** (1.0 / 12.0)
DEFAULT = {"pre": 0.0, "pre_ms": 120.0, "during": 0.0, "look_ms": 15.0, "post": 0.0, "echoes": 3, "post_ms": 90.0, "mode": "user"}


def _state(app):
    st = getattr(app, "r32_predictive", None)
    if not isinstance(st, dict):
        st = app.r32_predictive = {"global": dict(DEFAULT), "local": {}}
    return st


def settings(app, name):
    st = _state(app)
    s = dict(DEFAULT); s.update(st["global"]); s.update(st["local"].get(str(name)) or {})
    if s.get("mode") == "seeded":
        try:
            import groovebox as gb
            r = np.random.default_rng(gb.seed_child(int(app._seed_program_signature() or 1), "predictive", str(name)))
            s.update({"pre": float(r.uniform(0, .35)), "during": float(r.uniform(0, .5)), "post": float(r.uniform(0, .35))})
        except Exception:
            pass
    return s


def _ramp(n):
    return (np.sin(np.linspace(0, math.pi / 2, max(1, n))) ** 2)


def process(y, sr, s):
    x = np.asarray(y, dtype=np.float64)
    if x.ndim != 1 or x.size < 64:
        return y
    out = x.copy(); n = x.size
    if s["pre"] > 0:                                   # BEFORE
        m = min(n // 2, int(s["pre_ms"] * sr / 1000.0))
        if m > 8:
            swell = x[:m][::-1] * _ramp(m)
            out[:m] = out[:m] * (1.0 - s["pre"] * _ramp(m)[::-1] * 0.6) + s["pre"] * swell * 0.7
    if s["during"] > 0:                                # DURING (look-ahead gain)
        blk = max(8, int(s["look_ms"] * sr / 1000.0))
        nb = n // blk
        if nb > 2:
            env = np.abs(out[: nb * blk]).reshape(nb, blk).max(axis=1)
            fut = np.maximum(env, np.concatenate([env[1:], env[-1:]]))          # the next block, known exactly
            tgt = 0.5 * float(np.max(fut)) + 1e-9
            g = (tgt / np.maximum(fut, 1e-9)) ** (0.6 * s["during"])
            g = np.clip(g, 0.25, 4.0)
            gs = np.interp(np.arange(n), (np.arange(nb) + 0.5) * blk, g)
            out = out * gs
    if s["post"] > 0:                                  # AFTER (decay echoes inside the buffer)
        d0 = int(s["post_ms"] * sr / 1000.0)
        acc = np.zeros(n)
        for k in range(1, int(s["echoes"]) + 1):
            d = int(d0 * MEUM ** (k * 3))
            if d >= n:
                break
            acc[d:] += out[: n - d] * (s["post"] * 0.55 ** k)
        out = out + acc
    pk = float(np.max(np.abs(out))) or 1.0; pk0 = float(np.max(np.abs(x))) or 1.0
    if pk > pk0 * 1.5:
        out *= pk0 * 1.5 / pk
    return out.astype(np.asarray(y).dtype)


def install(app):
    if getattr(app, "_r32_pred_hooked", False):
        return
    orig = getattr(app, "_render_instrument_voice", None)
    if not callable(orig):
        return

    def _voice(name, hz, t, dur, sr, _orig=orig):
        out = _orig(name, hz, t, dur, sr)
        try:
            s = settings(app, name)
            if s["pre"] > 0 or s["during"] > 0 or s["post"] > 0:
                return process(out, sr, s)
        except Exception:
            pass
        return out
    app._render_instrument_voice = _voice
    app._r32_pred_hooked = True


def make_panel(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QSlider, QComboBox, QSpinBox
    install(app)
    b = QGroupBox("🔮 PREDICTIVE FX · before · during · after the note")
    b.setStyleSheet("QGroupBox{color:#f472b6;background:#000000;border:1px solid #f472b6;border-radius:7px;margin-top:6px;"
                    "padding-top:10px;font-weight:900;}QLabel{color:#ffffff;font-size:8pt;}")
    g = QGridLayout(b); g.setSpacing(2)
    scope = QComboBox(); scope.addItems(["Global", "Selected instrument"]); mode = QComboBox(); mode.addItems(["user", "seeded"])
    g.addWidget(scope, 0, 0, 1, 2); g.addWidget(mode, 0, 2, 1, 2)
    keys = (("pre", "Before · anticipation", 0, 100), ("pre_ms", "  swell ms", 10, 500), ("during", "During · look-ahead", 0, 100),
            ("look_ms", "  look ms", 2, 80), ("post", "After · decay echoes", 0, 100), ("post_ms", "  echo ms", 20, 600))
    w = {}
    for r, (k, cap, lo, hi) in enumerate(keys, 1):
        s = QSlider(Qt.Orientation.Horizontal); s.setRange(lo, hi); w[k] = s
        g.addWidget(QLabel(cap), r, 0, 1, 2); g.addWidget(s, r, 2, 1, 2)
    ech = QSpinBox(); ech.setRange(1, 8); ech.setPrefix("echoes "); g.addWidget(ech, len(keys) + 1, 2, 1, 2)
    PCT = ("pre", "during", "post")

    def rec():
        st = _state(app)
        if scope.currentIndex() == 0:
            return st["global"]
        n = app.instrument_selector_dropdown.currentText() if hasattr(app, "instrument_selector_dropdown") else ""
        return st["local"].setdefault(n, {})

    def load(*_):
        r = dict(DEFAULT); r.update(rec())
        for k, s in w.items():
            s.blockSignals(True); s.setValue(int(round(float(r[k]) * (100 if k in PCT else 1)))); s.blockSignals(False)
        ech.blockSignals(True); ech.setValue(int(r["echoes"])); ech.blockSignals(False)
        mode.blockSignals(True); mode.setCurrentText(r.get("mode", "user")); mode.blockSignals(False)

    def save(*_):
        r = rec()
        for k, s in w.items():
            r[k] = s.value() / 100.0 if k in PCT else float(s.value())
        r["echoes"] = ech.value(); r["mode"] = mode.currentText()
        getattr(app, "_on_live_source_changed", lambda: None)()
    for s in w.values():
        s.valueChanged.connect(save)
    ech.valueChanged.connect(save); mode.currentIndexChanged.connect(save); scope.currentIndexChanged.connect(load)
    load()
    return b
