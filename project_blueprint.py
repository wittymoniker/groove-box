"""project_blueprint.py — GROOVEBOX_R32_PROJECT_BLUEPRINT_20261109

A Startup / Main window tool that builds a *master project configuration* from a small set
of precise inputs, and keeps four PROJECT MACROS live afterwards.

Inputs (all exact, all explained in the panel):
    character      Tonal · Rhythmic · Textural · Cinematic · Chaotic · Minimal
    energy         0..1          density, drive, motion
    tempo          BPM (20..300) or "from energy"
    base frequency Hz (the project's harmonic anchor)
    length         bars
    instruments    1..16
    canonical mode protected · global50 · direct       (canonical_mode)
    divergence     0..1                                 (seed_divergence)
    visual weight  0..1   game weight 0..1              (multidim mixer / playability)
    seed           a number, or "generate" → a validated 64–256 line seed program

Output: one dict (``build(...)``) and ``apply(app, cfg)`` which writes it through the
existing fields (bpm spin, seed editor, canonical_mode, mixer state, ball/cellular
parameters, playability) so every older mechanism sees ordinary edits.

PROJECT MACROS (``MacroPanel``): ENERGY · COLOUR · SPACE · DRIVE — each one moves a
fixed set of project parameters together, live, through the same fields.
"""
from __future__ import annotations

import math
import random

CHARACTERS = ("Tonal", "Rhythmic", "Textural", "Cinematic", "Chaotic", "Minimal")
CHAR_PROFILE = {
    #           mixer: vector wavetable ball cellular multidim | ball gravity | ca rule | fx: fractal eqr hyper
    "Tonal":     dict(vector=.85, wavetable=.9, ball=.35, cellular=.3, md=1.0, gravity=.15, rule=90, fractal=.08, eqr=.15, hyper=.03),
    "Rhythmic":  dict(vector=.6, wavetable=.5, ball=.9, cellular=.8, md=1.0, gravity=.9, rule=30, fractal=.15, eqr=.1, hyper=.2),
    "Textural":  dict(vector=.7, wavetable=.8, ball=.4, cellular=.9, md=1.0, gravity=.25, rule=110, fractal=.3, eqr=.35, hyper=.08),
    "Cinematic": dict(vector=.9, wavetable=.85, ball=.5, cellular=.5, md=1.0, gravity=.2, rule=54, fractal=.2, eqr=.4, hyper=.05),
    "Chaotic":   dict(vector=.8, wavetable=.6, ball=.95, cellular=.95, md=1.0, gravity=1.6, rule=45, fractal=.45, eqr=.25, hyper=.4),
    "Minimal":   dict(vector=.5, wavetable=.6, ball=.2, cellular=.2, md=1.0, gravity=.1, rule=150, fractal=.0, eqr=.08, hyper=.0),
}


def build(character="Tonal", energy=0.5, tempo=None, base_hz=432.0, bars=32, instruments=8, canonical_mode="protected",
          divergence=0.6, visual=0.5, game=0.3, seed="generate", app=None, rng=None):
    """The master configuration dict."""
    rng = rng or random.Random()
    prof = CHAR_PROFILE.get(character, CHAR_PROFILE["Tonal"])
    energy = max(0.0, min(1.0, float(energy)))
    bpm = float(tempo) if tempo not in (None, "", "from energy", 0) else round(70.0 + 110.0 * energy ** 1.2, 1)
    bpm = max(20.0, min(300.0, bpm))
    cfg = {
        "character": character, "energy": energy, "bpm": bpm, "base_hz": max(20.0, min(2000.0, float(base_hz))),
        "bars": max(1, int(bars)), "instruments": max(1, min(128, int(instruments))), "canonical_mode": canonical_mode,
        "divergence": max(0.0, min(1.0, float(divergence))), "visual": max(0.0, min(1.0, float(visual))),
        "game": max(0.0, min(1.0, float(game))),
        "mixer": {"vector": prof["vector"], "wavetable": prof["wavetable"], "ball": min(1.0, prof["ball"] * (0.6 + 0.8 * energy)),
                  "cellular": min(1.0, prof["cellular"] * (0.6 + 0.8 * energy)), "multidim": prof["md"],
                  "cross_mod": round(0.0024 * (0.5 + energy), 5), "ensemble_mod_amt": round(0.08 + 0.3 * energy, 3),
                  "inharmonic": round(0.5 * energy * (1.0 if character in ("Chaotic", "Textural") else 0.3), 3)},
        "ball": {"gravity": round(prof["gravity"] * (0.5 + energy), 3), "radius": round(1.0 - 0.6 * energy, 2),
                 "vx": round(0.3 + 1.5 * energy, 2), "vy": round(-0.2 - 1.2 * energy, 2)},
        "cellular": {"rule": prof["rule"], "generations": 8 + int(24 * energy), "cell_types": 2 + int(3 * energy)},
        "post": {"fractal": prof["fractal"], "eqr": prof["eqr"], "hyper": round(prof["hyper"] * (0.5 + energy), 3),
                 "volume": 1.0, "clip_ratio": round(30.0 * energy, 1), "normalize": True, "target_peak": 0.97},
        "playability": {"speed": round(0.7 + 0.8 * cfg_game_speed(game, energy), 2), "gravity": round(0.6 + 0.9 * game, 2),
                        "assist": round(0.6 - 0.5 * game, 2), "lives": 3 + int(3 * (1 - game))},
        "video": {"weight": round(visual, 3), "scene_size": "1080p" if visual > 0.66 else ("720p" if visual > 0.33 else "auto")},
    }
    if isinstance(seed, (int, float)):
        cfg["seed_text"] = repr(float(seed))
    elif isinstance(seed, str) and seed.strip() and seed.strip().lower() != "generate":
        cfg["seed_text"] = seed
    else:
        cfg["seed_text"] = _seed_for(cfg, app, rng)
    return cfg


def cfg_game_speed(game, energy):
    return max(0.0, min(1.0, 0.5 * game + 0.5 * energy))


def _seed_for(cfg, app, rng):
    """A validated seed program whose scale follows energy (long for high energy)."""
    try:
        import seed_gen
        gb = __import__("groovebox")
        ctx = None
        try:
            ctx = app._canonical_input_context() if app is not None else None
        except Exception:
            ctx = None
        ws = gb.seed_workspace_variables(ctx if isinstance(ctx, dict) else None)
        probe = dict(gb._seed_probe_context(ws))
        probe.update({"bpm": cfg["bpm"], "graph_energy": cfg["energy"]})

        def env(tt):
            return gb._seed_script_env(t_scalar=float(tt), canonical_context=probe)

        lines = int(24 + 232 * cfg["energy"])
        text = seed_gen.generate(env, ws, rng=rng, target_lines=lines)
        header = ("# Blueprint · %s · energy %.2f · %.0f BPM · base %.1f Hz · %d bars · %d instruments\n"
                  % (cfg["character"], cfg["energy"], cfg["bpm"], cfg["base_hz"], cfg["bars"], cfg["instruments"]))
        return header + text if len(text.split("\n")) < 256 else text
    except Exception:
        return "%d * (1 + 0.25 * isn(t * MEUM)) + %d * ics(t_norm * PHI)" % (int(cfg["base_hz"]), int(40 + 200 * cfg["energy"]))


def apply(app, cfg):
    """Write the configuration into the running app through its ordinary fields."""
    rep = []

    def step(name, fn):
        try:
            fn()
            rep.append("✓ " + name)
        except Exception as exc:
            rep.append("· %s skipped (%s)" % (name, exc))

    def _bpm():
        sp = getattr(app, "spin_bpm", None)
        if sp is None:
            raise RuntimeError("no tempo control")
        sp.setValue(max(sp.minimum(), min(sp.maximum(), float(cfg["bpm"]))))
    step("tempo", _bpm)

    def _base():
        value = max(20.0, min(2000.0, float(cfg["base_hz"])))
        sp = getattr(app, "spin_base_frequency", None)
        if sp is not None:
            sp.setValue(max(sp.minimum(), min(sp.maximum(), value)))
        else:
            # Keep the canonical value available to non-UI/headless consumers.
            app.global_base_frequency_hz = value
    step("base frequency", _base)

    def _length():
        # Groovebox's sequencer is a 16-step 4/4 grid. Convert Blueprint bars
        # into its canonical pattern-length control instead of storing a bars
        # value that never reaches the running project.
        sp = getattr(app, "spin_seq_length", None)
        if sp is None:
            raise RuntimeError("no sequencer-length control")
        steps = max(1, int(cfg["bars"]) * 16)
        sp.setValue(max(sp.minimum(), min(sp.maximum(), steps)))
    step("pattern length", _length)

    def _count():
        # The roster is fixed (48 by default); the Blueprint chooses how many of them SOUND.
        # synth_engine_panel's voice hook silences instruments past this count.
        total = len(getattr(app, "instrument_names_48", []) or [])
        n = max(1, min(int(cfg["instruments"]), total or int(cfg["instruments"])))
        app.r32_active_instruments = n
        try:
            import synth_engine_panel
            synth_engine_panel.install(app)
        except Exception:
            pass
        return n
    step("active instruments", _count)

    def _seed():
        ed = getattr(app, "input_seed_val", None)
        if ed is not None:
            ed.setPlainText(str(cfg["seed_text"]))
    step("seed program", _seed)

    def _mode():
        import canonical_mode
        canonical_mode.apply(app, cfg["canonical_mode"], refresh=False)
    step("canonical mode", _mode)

    def _div():
        app.seed_divergence = float(cfg["divergence"])
        sp = getattr(app, "spin_seed_divergence", None)
        if sp is not None:
            sp.blockSignals(True); sp.setValue(float(cfg["divergence"])); sp.blockSignals(False)
    step("divergence", _div)

    def _mixer():
        st = getattr(app, "geometric_synth_mixer_state", None)
        if isinstance(st, dict):
            st.update(cfg["mixer"])
    step("geometric mixer", _mixer)

    def _ball():
        bl = getattr(app, "ball_synth_params", None)
        if isinstance(bl, dict):
            bl.update(cfg["ball"])
        ca = getattr(app, "cellular_synth_params", None)
        if isinstance(ca, dict):
            ca.update(cfg["cellular"])
    step("ball / cellular", _ball)

    def _play():
        import game_playability as gp
        gp.SETTINGS.update(gp.clean(cfg["playability"]))
        gp.save()
    step("playability", _play)

    def _post():
        app.blueprint_post_settings = dict(cfg["post"])
    step("post-process preset", _post)

    def _video():
        app.blueprint_video_settings = dict(cfg["video"])
        app.blueprint_visual_weight = float(cfg["visual"])
    step("video / visual preset", _video)

    def _refresh():
        done = 0
        for fn in ("_sync_canonical_widgets_from_state", "_geo_refresh_widgets", "_r32_geo_refresh_soon", "_on_live_source_changed"):
            f = getattr(app, fn, None)
            if callable(f):
                f(); done += 1
        if not done:
            raise RuntimeError("no refresh hooks found")
    step("refresh", _refresh)
    app.project_blueprint = dict(cfg)
    return rep


# ---------------------------------------------------------------------------
# PROJECT MACROS
# ---------------------------------------------------------------------------
PROJECT_MACROS = (
    ("ENERGY", "#f6c177", "tempo feel, ball/cellular drive, ensemble modulation"),
    ("COLOUR", "#7dd3fc", "inharmonic content, fractal amount, wavetable share"),
    ("SPACE", "#9ece6a", "EQR amount, vector share, cross-modulation"),
    ("DRIVE", "#ff7a90", "HyperDrive, clip ratio, multidim share"),
)


def apply_project_macro(app, name, value):
    v = max(0.0, min(1.0, float(value)))
    st = getattr(app, "geometric_synth_mixer_state", None)
    post = getattr(app, "blueprint_post_settings", None)
    if post is None:
        post = app.blueprint_post_settings = {}
    bl = getattr(app, "ball_synth_params", None)
    if name == "ENERGY":
        if isinstance(st, dict):
            st["ball"] = 0.2 + 0.8 * v; st["cellular"] = 0.2 + 0.8 * v; st["ensemble_mod_amt"] = 0.05 + 0.4 * v
        if isinstance(bl, dict):
            bl["gravity"] = 0.1 + 1.5 * v; bl["vx"] = 0.3 + 1.7 * v
    elif name == "COLOUR":
        if isinstance(st, dict):
            st["inharmonic"] = 0.6 * v; st["wavetable"] = 0.4 + 0.6 * v
        post["fractal"] = 0.5 * v
    elif name == "SPACE":
        if isinstance(st, dict):
            st["vector"] = 0.4 + 0.6 * v; st["cross_mod"] = 0.02 * v
        post["eqr"] = 0.6 * v
    elif name == "DRIVE":
        if isinstance(st, dict):
            st["multidim"] = 0.5 + 0.5 * v
        post["hyper"] = 0.6 * v; post["clip_ratio"] = 60.0 * v
    for fn in ("_sync_canonical_widgets_from_state", "_on_live_source_changed"):
        f = getattr(app, fn, None)
        if callable(f):
            try:
                f()
            except Exception:
                pass


def make_macro_panel(app, parent=None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QSlider
    box = QGroupBox("PROJECT MACROS", parent)
    lay = QHBoxLayout(box)
    app.project_macro_values = getattr(app, "project_macro_values", {}) or {}
    for name, color, tip in PROJECT_MACROS:
        lab = QLabel(name); lab.setToolTip(tip); lab.setStyleSheet("color:%s;font-weight:900;" % color)
        sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, 1000); sl.setToolTip(tip)
        sl.setValue(int(round(float(app.project_macro_values.get(name, 0.5)) * 1000)))
        sl.setStyleSheet("QSlider::sub-page:horizontal{background:%s;}QSlider::handle:horizontal{background:%s;border:1px solid #fff;width:12px;margin:-4px 0;border-radius:6px;}" % (color, color))
        sl.valueChanged.connect(lambda val, n=name: (app.project_macro_values.__setitem__(n, val / 1000.0), apply_project_macro(app, n, val / 1000.0)))
        lay.addWidget(lab); lay.addWidget(sl, 1)
    return box


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------
def open_window(app, parent=None, on_applied=None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit,
                                 QPushButton, QLabel, QTextEdit, QHBoxLayout, QScrollArea)
    import canonical_mode
    win = getattr(app, "_blueprint_window", None) if app is not None else None
    try:
        if win is not None:
            win.isVisible()
    except RuntimeError:
        win = None
    if win is not None:
        win.show(); win.raise_(); win.activateWindow()
        return win
    win = QWidget(parent or app, Qt.WindowType.Window)
    win.setWindowTitle("📐 Project Blueprint · master configuration from a few precise inputs")
    win.resize(760, 720)
    outer = QVBoxLayout(win)
    scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); scroll.setWidget(body); outer.addWidget(scroll)
    lay = QVBoxLayout(body)
    lay.addWidget(QLabel("Ten exact inputs → tempo, seed program, canonical mode, mixer, geometrics, finishing preset and game feel. "
                         "Apply writes through the ordinary fields, so Undo, autosave and every older mechanism see normal edits."))
    form = QFormLayout()
    cb_char = QComboBox(); cb_char.addItems(CHARACTERS)
    sp_energy = QDoubleSpinBox(); sp_energy.setRange(0, 1); sp_energy.setSingleStep(0.05); sp_energy.setValue(0.5)
    sp_tempo = QDoubleSpinBox(); sp_tempo.setRange(0, 300); sp_tempo.setSpecialValueText("from energy"); sp_tempo.setValue(0)
    sp_base = QDoubleSpinBox(); sp_base.setRange(20, 2000); sp_base.setDecimals(2); sp_base.setValue(float(getattr(app, "global_base_frequency_hz", 432.0) or 432.0))
    sp_bars = QSpinBox(); sp_bars.setRange(1, 999); sp_bars.setValue(32)
    _total = max(1, len(getattr(app, "instrument_names_48", []) or []) or 48)
    sp_inst = QSpinBox(); sp_inst.setRange(1, _total); sp_inst.setValue(int(getattr(app, "r32_active_instruments", _total) or _total))
    sp_inst.setSuffix(" of %d sounding" % _total)
    sp_inst.setToolTip("How many instruments of the roster sound (the rest stay silent; nothing is deleted)")
    cb_mode = QComboBox()
    for key, label, _s, _p in canonical_mode.MODES:
        cb_mode.addItem(label, key)
    sp_div = QDoubleSpinBox(); sp_div.setRange(0, 1); sp_div.setSingleStep(0.05); sp_div.setValue(float(getattr(app, "seed_divergence", 0.6) or 0.6))
    sp_vis = QDoubleSpinBox(); sp_vis.setRange(0, 1); sp_vis.setSingleStep(0.05); sp_vis.setValue(0.5)
    sp_game = QDoubleSpinBox(); sp_game.setRange(0, 1); sp_game.setSingleStep(0.05); sp_game.setValue(0.3)
    ed_seed = QLineEdit("generate"); ed_seed.setToolTip("a number, a seed expression, or 'generate'")
    for cap, w in (("Character", cb_char), ("Energy 0..1", sp_energy), ("Tempo (0 = from energy)", sp_tempo),
                   ("Base frequency Hz", sp_base), ("Length (bars)", sp_bars), ("Active instruments", sp_inst),
                   ("Canonical mode", cb_mode), ("Divergence 0..1", sp_div), ("Visual weight", sp_vis),
                   ("Game weight", sp_game), ("Seed", ed_seed)):
        form.addRow(cap, w)
    lay.addLayout(form)
    preview = QTextEdit(); preview.setReadOnly(True); preview.setMinimumHeight(220)
    preview.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;")
    lay.addWidget(QLabel("Configuration preview")); lay.addWidget(preview)
    row = QHBoxLayout()
    b_prev = QPushButton("👁 Preview"); b_apply = QPushButton("✅ Apply to project"); b_rand = QPushButton("🎲 Random inputs")
    row.addWidget(b_prev); row.addWidget(b_rand); row.addStretch(1); row.addWidget(b_apply)
    lay.addLayout(row)
    lay.addWidget(make_macro_panel(app, body))
    state = {"cfg": None, "inputs": None}

    def _inputs():
        seed = ed_seed.text().strip()
        try:
            seed = float(seed)
        except ValueError:
            pass
        return dict(character=cb_char.currentText(), energy=sp_energy.value(), tempo=sp_tempo.value() or None,
                    base_hz=sp_base.value(), bars=sp_bars.value(), instruments=sp_inst.value(),
                    canonical_mode=cb_mode.currentData(), divergence=sp_div.value(), visual=sp_vis.value(),
                    game=sp_game.value(), seed=seed)

    def do_preview():
        inputs = _inputs()
        try:
            cfg = build(app=app, **inputs)
        except Exception as exc:
            state["cfg"] = None; state["inputs"] = None
            preview.setPlainText("Blueprint could not be built: %s: %s" % (type(exc).__name__, exc))
            return
        state["cfg"] = cfg
        state["inputs"] = dict(inputs)
        import json
        show = dict(cfg); st = show.pop("seed_text")
        preview.setPlainText(json.dumps(show, indent=1) + "\n\n# seed program (%d lines)\n%s" % (len(st.split("\n")), st[:1600]))

    def do_apply():
        # Use the previewed configuration only when the inputs are unchanged.
        # Previously editing a slider after Preview and pressing Apply silently
        # applied stale values from the earlier preview.
        inputs = _inputs()
        if state["cfg"] is None or state.get("inputs") != inputs:
            try:
                cfg = build(app=app, **inputs)
            except Exception as exc:
                preview.setPlainText("Blueprint apply failed: %s: %s" % (type(exc).__name__, exc))
                return
            state["cfg"] = cfg; state["inputs"] = dict(inputs)
        cfg = state["cfg"]
        rep = apply(app, cfg)
        preview.append("\n" + "\n".join(rep))
        if on_applied:
            try:
                on_applied(cfg)
            except Exception:
                pass

    def do_random():
        r = random.Random()
        cb_char.setCurrentIndex(r.randrange(len(CHARACTERS))); sp_energy.setValue(round(r.random(), 2))
        sp_tempo.setValue(0); sp_inst.setValue(r.randint(1, max(1, min(16, sp_inst.maximum())))); sp_div.setValue(round(0.3 + 0.7 * r.random(), 2))
        sp_vis.setValue(round(r.random(), 2)); sp_game.setValue(round(r.random(), 2)); ed_seed.setText("generate")
        do_preview()

    b_prev.clicked.connect(do_preview); b_apply.clicked.connect(do_apply); b_rand.clicked.connect(do_random)
    if app is not None:
        app._blueprint_window = win
    win.show(); win.raise_(); win.activateWindow()
    return win
