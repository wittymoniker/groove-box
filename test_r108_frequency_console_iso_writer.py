from pathlib import Path
import importlib.util
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def _load_recent_selector():
    path = ROOT / "BUILD_ISO" / "select_recent_isos.py"
    spec = importlib.util.spec_from_file_location("gb_recent_iso_selector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fractal_seed_frequency_setting_is_normalized_and_persistable():
    from groovebox_v3.fractal_seed_engine import normalize_playable_settings
    settings = normalize_playable_settings({"base_frequency_hz": 440.0})
    assert settings["base_frequency_hz"] == 440.0
    assert normalize_playable_settings({"base_frequency_hz": -1})["base_frequency_hz"] == 432.0


def test_fractal_seed_root_frequency_reaches_canonical_pitch_ratio():
    from groovebox_v3.fractal_seed_engine import project_seed_config, evaluate_seed, rasterize_sequence
    config = project_seed_config("frequency-test", tempo=110, depth=1)
    config.update({"steps_per_bar": 16, "bars": 4, "root_midi": 60,
                   "base_frequency_hz": 440.0, "reference_frequency_hz": 432.0,
                   "scale": "minor_pentatonic", "symbol_budget": 16384,
                   "scenario": "none", "canonical_controls": True})
    plan = evaluate_seed(config)
    raster = rasterize_sequence(plan, 64)
    active = [i for i, on in enumerate(raster["steps"]) if on]
    assert active
    # At least one event is the root note; its pitch ratio must carry 440/432.
    assert any(abs(raster["pitches"][i] - (440.0 / 432.0)) < 1e-9 for i in active)


def test_fractal_frequency_is_in_canonical_plan_cache_key_and_projection():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert 'settings["base_frequency_hz"]' in source
    assert '"base_frequency_hz": settings["base_frequency_hz"]' in source
    assert 'mem["pitches"][j] = float(fractal_raster["pitches"][j])' in source
    assert '"base_frequency_hz": (fractal_plan.get("interpretation") or {})' in source
    assert 'float(_fr_interp.get("base_frequency_hz", 432.0)' in source
    assert 'float(_fr_interp.get("reference_frequency_hz", 432.0)' in source


def test_goava_amplitudes_are_user_adjustable_and_reach_canonical_rows():
    from goava_voices import voice_parameters
    voice = voice_parameters(432.0, {"spectrum_offset": 0.5, "amplitudes": [0.8, 0.4, 0.2]})
    assert voice["amplitudes"] == [0.8, 0.4, 0.2]
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    perf = (ROOT / "performance.py").read_text(encoding="utf-8")
    assert '"voice_amplitudes": list(_voices["amplitudes"])' in source
    assert 'e["goava_voice_amplitudes"] = _voice_amps' in source
    assert 'chord_amps = ev.get("chord_amps")' in source
    assert 'amp = float(a) * (1.0 - blend * 0.6)' in source
    assert "self.goava_voice_amp_spins" in perf
    assert "_apply_goava_voice_settings" in source


def test_console_positional_arguments_are_forwarded_and_shortcut_is_installed():
    console = (ROOT / "command_console.py").read_text(encoding="utf-8")
    app = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert "return fn(app=app, **kwargs)" in console
    assert "install_shortcut(self, self)" in app
    assert "Command Console…   Ctrl+Shift+`" in app
    assert "@command(\"canonicals\"" in console and "@command(\"runtime\"" in console


def test_program_builder_has_no_manual_julia_installer_button():
    source = (ROOT / "program_builder.py").read_text(encoding="utf-8")
    assert "Install Julia" not in source
    assert "Julia runtime is unavailable. This appliance should provide Julia automatically" in source
    assert '"Julia": bool(which("julia"))' in source
    assert '"JuliaCall": bool(juliacall_ready)' in source


def test_iso_selector_returns_five_newest_complete_isos(tmp_path):
    selector = _load_recent_selector()
    files = []
    for i in range(7):
        p = tmp_path / f"build-{i}.iso"
        payload = bytearray(b"x" * (1024 * 1024))
        payload[32768:32775] = b"\x01CD001\x01"
        p.write_bytes(payload)
        os.utime(p, ns=(1_000_000_000 + i * 1_000_000, 1_000_000_000 + i * 1_000_000))
        files.append(p)
    selected = selector.select_recent([tmp_path], 5)
    assert selected == list(reversed(files[-5:]))


def test_seven_partition_writer_has_five_iso_slots_and_destructive_safeguards():
    writer = (ROOT / "BUILD_ISO" / "write_five_isos_7part.sh").read_text(encoding="utf-8")
    assert "--new=7:" in writer
    assert "for n in {1..7}" in writer
    assert "--count 5" in writer
    assert "Type ERASE-USB" in writer
    assert "active swap" in writer
    assert "running root filesystem" in writer
    assert "GROOVEBOX-ISO-$((i+1)).iso" in writer
    preflight = (ROOT / "BUILD_ISO" / "RUN_ME_ZERO_STATE.sh").read_text(encoding="utf-8")
    assert "R108: the removable-media writer" in preflight


def test_active_overlay_has_frequency_and_console_changes_after_sync():
    overlay = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz"
    for rel in ("groovebox.py", "performance.py", "command_console.py", "program_builder.py",
                "goava_voices.py", "groovebox_v3/fractal_seed_engine.py"):
        assert (overlay / rel).is_file()
        assert (overlay / rel).read_bytes() == (ROOT / rel).read_bytes(), rel


def test_rand_automation_uses_the_captured_engine_rng():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert 'def _engines_write_automation_lanes(self, source="seeded", rng=None):' in source
    assert '_engines_write_automation_lanes(source="randomizer", rng=rng)' in source
    assert 'if rng is None:' in source


def test_dialog_fit_clamps_minimums_to_the_available_screen():
    source = (ROOT / "compat_settings.py").read_text(encoding="utf-8")
    assert 'max_w = max(240, int(ag.width()) - 24)' in source
    assert 'min_w_fit = min(max(240, int(min_w)), max_w)' in source
    assert 'dlg.setMaximumSize(max_w, max_h)' in source


def test_fractal_seed_ui_exposes_only_supported_steps_and_bars():
    source = (ROOT / "performance.py").read_text(encoding="utf-8")
    assert "for value in (8, 12, 16, 24, 32, 48, 64)" not in source
    assert "for value in (4, 8, 12, 16, 24, 32, 48, 64)" in source
    from groovebox_v3.fractal_seed_engine import project_seed_config, evaluate_seed
    config = project_seed_config("wide-window", depth=1)
    config.update({"steps_per_bar": 48, "bars": 64, "symbol_budget": 16384})
    plan = evaluate_seed(config)
    assert plan["interpretation"]["window_steps"] == 48 * 64


def test_console_has_fifteen_new_operator_and_diagnostic_tools():
    source = (ROOT / "command_console.py").read_text(encoding="utf-8")
    for command in ("canonicals", "runtime", "windows", "status", "project", "seed", "goava",
                    "fractal", "audio", "exports", "threads", "ui", "caches", "focus", "save"):
        assert f'@command("{command}"' in source
    assert "shlex.split(line)" in source


def test_console_parser_preserves_quoted_multiword_arguments():
    spec = importlib.util.spec_from_file_location("gb_console_parser_test", ROOT / "command_console.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    @module.command("echoargs_test", "test parser")
    def _echo(app=None, **kw):
        return "|".join(kw.get("_args", []))
    assert module._run_line('echoargs_test "Latitude Performance Window"', None) == "Latitude Performance Window"


def test_startup_selector_uses_opaque_scrollable_and_finally_clamped_window():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert "WA_TranslucentBackground, False" in source
    assert "_scroll.viewport().setAutoFillBackground(True)" in source
    assert "_body.setAutoFillBackground(True)" in source
    assert "_cs_fit_final.fit_dialog_to_screen(dlg" in source
    assert "_outer.setContentsMargins(8, 8, 8, 8)" in source
