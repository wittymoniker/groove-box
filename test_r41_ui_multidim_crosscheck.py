"""R41 source/runtime contracts for the corrected workstation and multidimensional continuum.

Static UI checks deliberately run without Qt; DSP checks execute the actual NumPy engine.
"""
from pathlib import Path
import ast
import numpy as np
import multidim_synth as md

ROOT = Path(__file__).parent
GROOVE = (ROOT / "groovebox.py").read_text(encoding="utf-8", errors="ignore")
MDUI = (ROOT / "multidim_ui.py").read_text(encoding="utf-8", errors="ignore")
MDSYN = (ROOT / "multidim_synth.py").read_text(encoding="utf-8", errors="ignore")
_GROOVE_TREE = ast.parse(GROOVE)


def _class_src(source, class_name):
    tree = _GROOVE_TREE if source is GROOVE else ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    lines = source.splitlines()
    return "\n".join(lines[node.lineno - 1:node.end_lineno])


def _method_src(source, class_name, method_name):
    tree = _GROOVE_TREE if source is GROOVE else ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    method = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name)
    lines = source.splitlines()
    return "\n".join(lines[method.lineno - 1:method.end_lineno])


def test_background_is_single_central_widget_child_and_transparent():
    assert "_ensure_single_math_background(" in GROOVE and "show=not self._math_background_deferred" in GROOVE
    assert 'cw.setObjectName("GrooveboxCentral")' in GROOVE
    assert 'self.parametric_background = _ensure_single_math_background' in GROOVE
    assert 'QWidget#GrooveboxCentral {\n                background: transparent;\n            }' in GROOVE
    bg = _class_src(GROOVE, "ParametricMathBackground")
    assert "self.host.installEventFilter(self)" in bg
    assert "self.setGeometry(self.host.rect())" in bg
    assert "self.lower()" in bg
    assert "def paintEvent" in bg and "QPainter" in bg
    assert "def showEvent" in bg and "self._timer.start()" in bg


def test_background_first_show_gate_and_no_constructor_timer_start():
    bg = _class_src(GROOVE, "ParametricMathBackground")
    init = bg[bg.index("def __init__"):bg.index("def eventFilter")]
    assert "self._timer.start()" not in init
    main = _class_src(GROOVE, "MathematiciansGrooveboxApp")
    assert "QTimer.singleShot(750, self._activate_startup_math_background)" in main
    ensure = GROOVE[GROOVE.index("def _ensure_single_math_background"):GROOVE.index("def _low_power_mode")]
    assert "if show:" in ensure and "bg.hide()" in ensure


def test_main_window_has_no_custom_resize_event_and_background_tracks_central_resize():
    main = _class_src(GROOVE, "MathematiciansGrooveboxApp")
    assert "def resizeEvent" not in main
    bg = _class_src(GROOVE, "ParametricMathBackground")
    assert "event.type() == QEvent.Type.Resize" in bg
    assert "self.setGeometry(self.host.rect())" in bg


def test_fixed_pixel_monitors_lead_the_biaxial_bottom_canvas():
    assert '(self.visual_oscilloscope, "GLOBAL · MEUM WAVEFORM", False)' in GROOVE
    assert '(self.video_synth_viewer, "GLOBAL · MEUM SCENOGRAPH", True)' in GROOVE
    assert '(self.spectrum_analyzer, "GLOBAL · MEUM SPECTRUM", False)' in GROOVE
    assert "widget.setFixedSize(480, 480)" in GROOVE
    assert "widget.setFixedSize(360, 480)" in GROOVE
    assert "bottom_scroll.setWidgetResizable(False)" in GROOVE
    assert "bottom_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)" in GROOVE
    assert "bottom_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)" in GROOVE
    stage = GROOVE.index("bottom_layout.addLayout(vis_row)")
    transport = GROOVE.index("bottom_layout.addWidget(_scope_holder, 0)")
    assert stage < transport
    assert "_bottom_shell_layout.addWidget(bottom_scroll, 8024)" in GROOVE
    assert "_bottom_shell_layout.addStretch(988)" in GROOVE


def test_global_dj_and_patcher_are_mounted_once_in_color_matched_top_suites():
    assert 'perf_box = QGroupBox("LIVE PERFORMANCE / DJ")' in GROOVE
    assert '_dj.setObjectName("globalLiveDJPanel")' in GROOVE
    assert "background:#241633" in GROOVE and "#a66cff" in GROOVE
    assert 'green_parent = QGroupBox("GREEN · SEQUENCER / AUTOMATION")' in GROOVE
    assert '_gp.setObjectName("globalPlayPatcherGroup")' in GROOVE
    assert "background:#0b3024" in GROOVE and "#20b879" in GROOVE
    green = _method_src(GROOVE, "MathematiciansGrooveboxApp", "_build_panel2_tools")
    assert green.count('green_parent_layout.addWidget(_gp)') == 1
    assert 'outer.addWidget(green_parent, 0, 0)' in green


def test_vector_rail_precedes_bouncing_ball():
    app = _class_src(GROOVE, "MathematiciansGrooveboxApp")
    assert app.index("_arc_host.add_left_widget(self.master_vector_group)") < app.index("_arc_host.add_left_widget(self.ball_synth_group)")


def test_multidim_engine_is_the_panel_geometry_third_leg_with_canonical_effects():
    assert "_md_triad(main, geo, gpw" in GROOVE
    assert '"instrument_param_state": _safe_json(getattr(self, "instrument_param_state", {}))' in GROOVE
    triad = MDSYN[MDSYN.index("def triad("):MDSYN.index("def ", MDSYN.index("def triad(") + 10)]
    assert "inner = (1.0 - gpw) * main + gpw * geo" in triad
    assert "return (1.0 - mix) * inner + mix * md_out" in triad
    for label in ("EUCLIDEAN", "GOAVA", "PHASE LOCK", "SEEDED / RANDOMIZER", "FRACTAL SEED"):
        assert label in MDUI
    assert 'self.engine_tabs.addTab(field_page, "FRACTALITY / FIELD")' in MDUI
    assert 'self.engine_tabs.addTab(canonical_page, "CANONICALS / GOAVA")' in MDUI


def test_goava_seeded_and_io_modes_are_deterministic_and_input_derived():
    assert '"goava_mode")' in MDSYN
    assert 'p.setdefault("goava_mode", "seeded")' in MDSYN
    assert 'str(p.get("goava_mode", "seeded")).lower()' in MDSYN
    n, sr, seed, slot = 8192, 44100, 12345, 2
    phase = np.cumsum(np.full(n, 2.0 * np.pi * 220.0 / sr))
    t = np.arange(n, dtype=np.float64) / sr
    main = (0.1 + 0.9 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 3.0 * t))) * np.sin(phase * 0.5)
    p = md.canonical_params(seed, slot, ["goava"], density=0.55, convolve=0.35)
    p["goava_mode"] = "seeded"
    y1 = md.voice(phase, sr, p, t=t, seed_int=seed, slot=slot, main=main)
    y2 = md.voice(phase, sr, p, t=t, seed_int=seed, slot=slot, main=main)
    assert np.array_equal(y1, y2)
    pio = dict(p); pio["patch"] = dict(p["patch"]); pio["goava_mode"] = "io"
    yio = md.voice(phase, sr, pio, t=t, seed_int=seed, slot=slot, main=main)
    assert np.isfinite(yio).all() and not np.allclose(y1, yio)


def test_five_canonical_engines_have_distinct_seeded_programs_and_convolution():
    seed, slot = 8421, 7
    expected = {
        "euclidean": lambda p: p["ca_rule"] in (184, 226, 170, 240),
        "goava": lambda p: p["resonators"] == "golden",
        "phase_lock": lambda p: p["patch"]["vector->phase"] == 1.0,
        "seeded": lambda p: p["stochastic"] > 0 and p["gravity"] >= 4.0,
        "fractal_seed": lambda p: p["ca_rule"] == 90 and p["fractal_depth"] > 0,
    }
    for engine, predicate in expected.items():
        p = md.canonical_params(seed, slot, [engine], density=0.5, convolve=0.0)
        assert engine in p["_engines"] and predicate(p), (engine, p)
    p0 = md.canonical_params(seed, slot, ["goava"], density=0.5, convolve=0.0)
    p1 = md.canonical_params(seed, slot, ["goava"], density=0.5, convolve=0.7)
    assert p0["res_q"] != p1["res_q"] and p0["block_ms"] != p1["block_ms"]
    all_on = md.canonical_params(seed, slot, list(expected), density=0.5, convolve=0.2)
    assert set(expected).issubset(set(all_on["_engines"]))


def test_multidim_triad_contains_panel_and_geometry_and_is_finite():
    n, sr = 2048, 48000
    phase = np.cumsum(np.full(n, 2.0 * np.pi * 330.0 / sr))
    main = 0.2 * np.sin(phase)
    geo = 0.15 * np.sin(phase * 0.83 + 0.2)
    params = md.canonical_params(29, 1, ["goava", "phase_lock"], density=0.4, convolve=0.25)
    params["patch"] = dict(params["patch"])
    params["patch"]["->main.amp"] = 0.2
    params["patch"]["->geo.amp"] = 0.2
    md_out = md.voice(phase, sr, params, seed_int=29, slot=1, main=main)
    with_geometry = md.triad(main, geo, 0.5, 0.5, md_out, params, sr)
    panel_only = md.triad(main, None, 0.5, 0.5, md_out, params, sr)
    assert with_geometry.shape == panel_only.shape == (n,)
    assert np.isfinite(with_geometry).all()
    assert not np.allclose(with_geometry, panel_only)


def test_project_snapshot_persists_md_routes_and_canonical_mix():
    assert '"md_exchange_state": _safe_json(self._md_exchange_store()' in GROOVE
    assert '"md_io_state": _safe_json(self._md_io_store()' in GROOVE
    assert 'if isinstance(data.get("md_exchange_state"), dict):' in GROOVE
    assert 'self.md_exchange_state = copy.deepcopy(data["md_exchange_state"])' in GROOVE
    assert 'self.md_io_state = copy.deepcopy(data["md_io_state"])' in GROOVE
    assert '"geometric_synth_mixer_state": _safe_json(getattr(self, "geometric_synth_mixer_state", {}))' in GROOVE
    assert '"instrument_param_state": _safe_json(getattr(self, "instrument_param_state", {}))' in GROOVE
    assert '"master_vector_state": _safe_json(getattr(self, "master_vector_state", {}))' in GROOVE


def test_foreground_governor_pauses_main_both_transports_and_resumes_cursor():
    body = _method_src(GROOVE, "MathematiciansGrooveboxApp", "_set_foreground_activity")
    assert "self._pause_audio_only_for_focus()" in body
    assert "self.toggle_playback()" in body
    assert "self._resume_audio_only_for_focus()" in body
    pause = _method_src(GROOVE, "MathematiciansGrooveboxApp", "_pause_audio_only_for_focus")
    assert "self.play_cursor" not in pause or "preserving its exact cursor" in pause
    resume = _method_src(GROOVE, "MathematiciansGrooveboxApp", "_resume_audio_only_for_focus")
    assert "callback=self._audio_callback" in resume and 'getattr(self, "play_cursor"' in resume
    assert "_audio_owner\", None) in (None, \"main\")" in body


def test_shared_worker_modes_are_bounded_and_audio_callback_is_not_reassigned():
    import compat_settings as cs
    assert cs.DEFAULTS["worker_mode"] == "adaptive"
    assert cs.env_for({"worker_mode": "balanced"})["GROOVEBOX_WORKERS"] == "14"
    assert cs.env_for({"worker_mode": "video"})["GROOVEBOX_WORKERS"] == "16"
    assert cs.env_for({"worker_mode": "memory"})["GROOVEBOX_WORKERS"] == "8"
    ui = _method_src(GROOVE, "MathematiciansGrooveboxApp", "_show_compat_dialog")
    assert '"Video / streaming · 16 shared worker slots"' in ui
    assert "does not change the audio callback" in ui or "audio callback" in ui
