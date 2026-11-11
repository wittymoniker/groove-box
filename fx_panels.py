"""fx_panels.py — GROOVEBOX_R32_FX_PANELS_20261110

LOCAL ▸ FX (per instrument) and GLOBAL ▸ FX (master bus) panels, placed under the
geometric columns left and right of the Multidim panel.  Hardcoded FX only, fixed order:
PKP Envelope → Fractallizer (+tilt) → EQR → ∞M HyperDrive.  All 0 = exact bypass.

Each panel has a mode: "user" (your values), "canonical" (values derived from the seed
program signature + instrument slot, deterministic) or "mix" (50 / 50).

Audio hooks:
  * local  — wraps app._render_instrument_voice(name, hz, t, dur, sr): the voice of that
    instrument passes through its local chain;
  * global — app._r32_global_fx(master, sr) is called at the top of _master_hardclip,
    before volume / clip, so the master bus contract (volume × factors → hard clip) holds.
"""
from __future__ import annotations

import numpy as np

KEYS = (("pkp", "PKP Envelope", 0.0, 1.0), ("fractal", "Fractallizer", 0.0, 1.0), ("tilt", "Tilt sub↔super", -1.0, 1.0),
        ("eqr", "EQR", 0.0, 1.0), ("hyper", "∞M HyperDrive", 0.0, 1.0))
ZERO = {k: 0.0 for k, *_ in KEYS}
MODES = ("user", "canonical", "mix")


def _canonical(app, slot):
    """Deterministic chain values from the seed program signature and slot."""
    try:
        import groovebox as gb
        sig = int(app._seed_program_signature() or gb._safe_int_seed(app.get_numeric_seed()))
        rng = np.random.default_rng(gb.seed_child(sig, "fx", int(slot)))
    except Exception:
        rng = np.random.default_rng(int(slot) + 1)
    u = rng.random(5)
    return {"pkp": float(0.4 * u[0] * (u[0] > 0.6)), "fractal": float(0.35 * u[1]), "tilt": float(2 * u[2] - 1),
            "eqr": float(0.3 * u[3]), "hyper": float(0.25 * u[4] * (u[4] > 0.5))}


def _send(key):
    try:
        import r32_rowctx
        return r32_rowctx.num(key, 1.0, 0.0, 2.0)
    except Exception:
        return 1.0


def effective(app, scope, name=""):
    v = _effective_raw(app, scope, name)
    k = _send("fx_send")
    return v if k == 1.0 else {kk: (vv * k if kk != "tilt" else vv) for kk, vv in v.items()}


def _effective_raw(app, scope, name=""):
    st = getattr(app, "r32_fx_state", None) or {}
    rec = (st.get("global") if scope == "global" else (st.get("local", {}) or {}).get(name)) or {}
    mode = rec.get("mode", "user")
    user = {k: float(rec.get(k, 0.0)) for k, *_ in KEYS}
    if mode == "user":
        return user
    slot = 999 if scope == "global" else (abs(hash(name)) % 997 if not name else sum(map(ord, name)) % 997)
    can = _canonical(app, slot)
    if mode == "canonical":
        return can
    return {k: 0.5 * user[k] + 0.5 * can[k] for k in user}


def active(v):
    return any(abs(float(v.get(k, 0.0))) > 1e-6 for k in ("pkp", "fractal", "eqr", "hyper"))


def process(x, sr, v, bpm=120.0):
    import hardcoded_fx as hfx
    import groovebox as gb
    y = np.asarray(x, dtype=np.float32)
    shp = y.shape
    y = y.ravel() if y.ndim == 1 else y
    if y.ndim == 2:
        return np.stack([process(y[:, c], sr, v, bpm) for c in range(y.shape[1])], axis=1)
    n = y.size
    if n < 32:
        return np.asarray(x, dtype=np.float32)
    if v["pkp"] > 0:
        g, _ = hfx.pkp_gate(n, sr, bpm, 0.25, float(v["pkp"]), 0, 0.5)
        y = y * g
    if v["fractal"] > 0:
        y = hfx.fractallize(y, sr, float(v["fractal"]), float(v["tilt"]))
    if v["eqr"] > 0:
        y = hfx.eqr_mix(y, float(v["eqr"]), getattr(gb, "eqr_tensor_audio_z_vec", None))
    if v["hyper"] > 0:
        y = hfx.fi_hyperdrive(y, sr, float(v["hyper"]), float(getattr(hfx, "MEUM_MINUS_1", 0.0595)) * 4.0)
    return np.asarray(y, dtype=np.float32).reshape(shp)


def install_hooks(app):
    if getattr(app, "_r32_fx_hooked", False):
        return
    app.r32_fx_state = getattr(app, "r32_fx_state", None) or {"global": {"mode": "user", **ZERO}, "local": {}}
    orig = getattr(app, "_render_instrument_voice", None)
    if callable(orig):
        def _voice(name, hz, t, dur, sr, _orig=orig):
            out = _orig(name, hz, t, dur, sr)
            try:
                v = effective(app, "local", str(name))
                if active(v):
                    dtype = np.asarray(out).dtype
                    out = process(out, sr, v, float(getattr(app, "global_bpm", 120.0) or 120.0)).astype(dtype)
            except Exception:
                pass
            return out
        app._render_instrument_voice = _voice

    def _global(master, sr):
        try:
            v = effective(app, "global")
            if active(v):
                return process(master, sr or 48000, v, float(getattr(app, "global_bpm", 120.0) or 120.0))
        except Exception:
            pass
        return master
    app._r32_global_fx = _global
    app._r32_fx_hooked = True


def make_panel(app, scope):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QSlider, QComboBox, QPushButton
    install_hooks(app)
    title = "LOCAL ▸ FX · selected instrument" if scope == "local" else "GLOBAL ▸ FX · master bus"
    color = "#f6c177" if scope == "local" else "#c4a7e7"
    box = QGroupBox(title)
    box.setStyleSheet("QGroupBox{color:%s;background:#000000;border:1px solid %s;border-radius:7px;margin-top:6px;"
                      "padding-top:10px;font-weight:900;}QLabel{color:#ffffff;font-size:8pt;}" % (color, color))
    g = QGridLayout(box); g.setContentsMargins(5, 9, 5, 4)
    mode = QComboBox(); mode.addItems(["User", "Canonical (seeded)", "Mix 50/50"])
    g.addWidget(QLabel("Mode"), 0, 0); g.addWidget(mode, 0, 1)
    sliders = {}

    def rec():
        st = app.r32_fx_state
        if scope == "global":
            return st.setdefault("global", {"mode": "user", **ZERO})
        name = app.instrument_selector_dropdown.currentText() if hasattr(app, "instrument_selector_dropdown") else ""
        return st.setdefault("local", {}).setdefault(name, {"mode": "user", **ZERO})

    def load(*_):
        r = rec()
        mode.blockSignals(True); mode.setCurrentIndex(MODES.index(r.get("mode", "user"))); mode.blockSignals(False)
        for k, sl in sliders.items():
            sl.blockSignals(True); sl.setValue(int(round(float(r.get(k, 0.0)) * 100))); sl.blockSignals(False)

    def changed(*_):
        r = rec()
        r["mode"] = MODES[mode.currentIndex()]
        for k, sl in sliders.items():
            r[k] = sl.value() / 100.0
        f = getattr(app, "_on_live_source_changed", None)
        if callable(f):
            try:
                f()
            except Exception:
                pass

    for i, (k, cap, lo, hi) in enumerate(KEYS, 1):
        sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(int(lo * 100), int(hi * 100)); sl.valueChanged.connect(changed)
        sliders[k] = sl
        g.addWidget(QLabel(cap), i, 0); g.addWidget(sl, i, 1)
    mode.currentIndexChanged.connect(changed)
    b = QPushButton("Bypass all"); b.clicked.connect(lambda: [s.setValue(0) for s in sliders.values()])
    g.addWidget(b, len(KEYS) + 1, 0, 1, 2)
    if scope == "local" and hasattr(app, "instrument_selector_dropdown"):
        app.instrument_selector_dropdown.currentIndexChanged.connect(load)
    load()
    return box


def install(app, arc_host=None):
    """Add the two panels under the geometric columns (left = local, right = global)."""
    try:
        # The synth engine (unison / sub / fold …) must wrap the raw voice FIRST, so FX, time FX and
        # generated-sample layers are applied once to the finished voice, not once per unison voice.
        try:
            import synth_engine_panel
            synth_engine_panel.install(app)
        except Exception as exc:
            print(f"[Synth engine] {exc}")
        left, right = make_panel(app, "local"), make_panel(app, "global")
        app.r32_local_fx_group, app.r32_global_fx_group = left, right
        extra_l, extra_r = [], []
        try:
            import sample_generator
            extra_l.append(sample_generator.make_panel(app))
        except Exception as exc:
            print(f"[Sample generator] {exc}")
        try:
            import synth_engine_panel
            extra_l.insert(0, synth_engine_panel.make_panel(app))
        except Exception as exc:
            print(f"[Synth engine] {exc}")
        try:
            extra_r.append(make_time_panel(app))
        except Exception as exc:
            print(f"[Time FX] {exc}")
        from PyQt6.QtWidgets import QSizePolicy as _SP
        for _b in [left, right] + extra_l + extra_r:
            make_collapsible(_b, collapsed=_b not in (left, right))
            _b.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Preferred)     # R32.8: fill the column width
            try:   # R32.9: global panels join the blue glow / red wires of perseq_vars
                if "global" in (_b.title() or "").lower():
                    _b.setProperty("r32GlobalPanel", True)
            except Exception:
                pass
        if arc_host is not None and hasattr(arc_host, "add_left_widget"):
            for w in [left] + extra_l:
                arc_host.add_left_widget(w)
            for w in [right] + extra_r:
                arc_host.add_right_widget(w)
            return True
        lay = getattr(app, "below_seq_operator_layer", None)
        if lay is not None:
            for w in [left] + extra_l + [right] + extra_r:
                lay.addWidget(w, 1)
            return True
    except Exception as exc:
        print(f"[FX panels] {exc}")
    return False


# ---------------------------------------------------------------------------
# R32.4: POST ▸ TIME FX (granular chorus / flanger, forward/backward reverb) — right column
# ---------------------------------------------------------------------------
TIME_KEYS = (("chorus", "Granular chorus", 0, 100), ("chorus_rate", "Chorus rate Hz", 5, 300),
             ("flanger", "Granular flanger", 0, 100), ("flanger_rate", "Flanger rate Hz", 2, 200),
             ("flanger_fb", "Flanger feedback", 0, 95), ("reverb", "Time reverb", 0, 100),
             ("reverb_size", "Reverb size", 0, 100), ("reverb_decay", "Reverb decay", 0, 100),
             ("reverb_dir", "Direction  −1 rev · 0 both · +1 fwd", -1, 1))


def _time_state(app, scope, name=""):
    st = app.__dict__.setdefault("r32_time_fx", {"global": {"mode": "user"}, "local": {}})
    if scope == "global":
        return st["global"]
    return st["local"].setdefault(name, {"mode": "user"})


def _time_effective(app, scope, name=""):
    rec = _time_effective_raw(app, scope, name)
    k = _send("time_fx_send")
    if k != 1.0:
        for kk in ("chorus", "flanger", "reverb"):
            if kk in rec:
                rec[kk] = float(rec.get(kk, 0) or 0) * k
    return rec


def _time_effective_raw(app, scope, name=""):
    rec = dict(_time_state(app, scope, name))
    if rec.get("mode") == "canonical":
        c = _canonical(app, 555 if scope == "global" else sum(map(ord, name)) % 997)
        rec.update({"chorus": c["fractal"], "flanger": c["hyper"], "reverb": c["eqr"], "reverb_size": 0.5,
                    "reverb_decay": 0.5, "reverb_dir": 1 if c["tilt"] >= 0 else -1})
    return rec


def _time_active(rec):
    return any(float(rec.get(k, 0) or 0) > 0 for k in ("chorus", "flanger", "reverb"))


def install_time_hooks(app):
    if getattr(app, "_r32_time_hooked", False):
        return
    import time_fx
    orig = getattr(app, "_render_instrument_voice", None)
    if callable(orig):
        def _voice(name, hz, t, dur, sr, _orig=orig):
            out = _orig(name, hz, t, dur, sr)
            try:
                rec = _time_effective(app, "local", str(name))
                if _time_active(rec):
                    out = time_fx.process(out, sr, rec, seed=sum(map(ord, str(name)))).astype(np.asarray(out).dtype)
            except Exception:
                pass
            return out
        app._render_instrument_voice = _voice
    prev = getattr(app, "_r32_global_fx", None)

    def _global(master, sr, _prev=prev):
        if callable(_prev):
            master = _prev(master, sr)
        try:
            rec = _time_effective(app, "global")
            if _time_active(rec):
                return time_fx.process(master, sr or 48000, rec, seed=555)
        except Exception:
            pass
        return master
    app._r32_global_fx = _global
    app._r32_time_hooked = True


def make_time_panel(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QSlider, QComboBox
    install_time_hooks(app)
    box = QGroupBox("POST ▸ TIME FX · granular chorus / flanger · fwd / reverse reverb")
    box.setStyleSheet("QGroupBox{color:#7dd3fc;background:#000000;border:1px solid #7dd3fc;border-radius:7px;margin-top:6px;"
                      "padding-top:10px;font-weight:900;}QLabel{color:#ffffff;font-size:8pt;}")
    g = QGridLayout(box); g.setContentsMargins(5, 9, 5, 4)
    scope = QComboBox(); scope.addItems(["Local (selected instrument)", "Global (master)"])
    mode = QComboBox(); mode.addItems(["User (non-canonical)", "Canonical (seeded)"])
    g.addWidget(QLabel("Scope"), 0, 0); g.addWidget(scope, 0, 1)
    g.addWidget(QLabel("Mode"), 1, 0); g.addWidget(mode, 1, 1)
    sl = {}

    def rec():
        if scope.currentIndex() == 1:
            return _time_state(app, "global")
        name = app.instrument_selector_dropdown.currentText() if hasattr(app, "instrument_selector_dropdown") else ""
        return _time_state(app, "local", name)

    def scale(k):
        return 1.0 if k == "reverb_dir" else 100.0

    def load(*_):
        r = rec()
        mode.blockSignals(True); mode.setCurrentIndex(1 if r.get("mode") == "canonical" else 0); mode.blockSignals(False)
        for k, w in sl.items():
            dflt = {"chorus_rate": .6, "flanger_rate": .25, "flanger_fb": .4, "reverb_size": .5, "reverb_decay": .5, "reverb_dir": 1}.get(k, 0)
            w.blockSignals(True); w.setValue(int(round(float(r.get(k, dflt)) * scale(k)))); w.blockSignals(False)

    def changed(*_):
        r = rec(); r["mode"] = "canonical" if mode.currentIndex() == 1 else "user"
        for k, w in sl.items():
            r[k] = w.value() / scale(k)
        f = getattr(app, "_on_live_source_changed", None)
        if callable(f):
            try: f()
            except Exception: pass

    for i, (k, cap, lo, hi) in enumerate(TIME_KEYS, 2):
        w = QSlider(Qt.Orientation.Horizontal); w.setRange(lo, hi); w.valueChanged.connect(changed)
        sl[k] = w; g.addWidget(QLabel(cap), i, 0); g.addWidget(w, i, 1)
    mode.currentIndexChanged.connect(changed); scope.currentIndexChanged.connect(load)
    if hasattr(app, "instrument_selector_dropdown"):
        app.instrument_selector_dropdown.currentIndexChanged.connect(load)
    load()
    return box


def make_collapsible(box, collapsed=False):
    """Compatibility shim: main-window engine/FX panels are permanently expanded.

    Keep the historical helper name so callers and third-party panel installers do
    not break, but never turn a QGroupBox into a checkable/collapsible control.
    A panel's visibility is owned by its parent layout, not by its title bar.
    """
    try:
        box.setCheckable(False)
        box.setChecked(True)
        box.setMaximumHeight(16777215)
        for child in box.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QWidget"]).QWidget,
                                      options=__import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.FindChildOption.FindDirectChildrenOnly):
            child.setVisible(True)
    except Exception:
        pass
    return box
