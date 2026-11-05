"""Source-level R28.4.50 HF1 contracts: integration, output route and sOS packaging."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent


def test_master_volume_defaults_and_project_round_trip_preserve_zero():
    main = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    perf = (ROOT / "performance.py").read_text(encoding="utf-8")
    assert "self.master_volume = 0.72  # First-launch synth Master Volume default = 72%" in main
    assert "self.slider_master_vol.setValue(72)" in main
    assert '"master_volume_percent": round(max(0.0, min(1.0, float(getattr(self, "master_volume", 0.72)))) * 100.0, 3)' in main
    assert 'R28_HF1_MASTER_VOLUME_PROJECT_ROUNDTRIP' in main
    assert 'data.get("master_volume_percent", None)' in main
    assert 'self._on_master_vol_changed(int(round(max(0.0, min(100.0, float(_saved_mv))))))' in main
    assert 'initial_master_pct = 72' in perf
    assert 'getattr(self.host, "master_volume", 0.72)' in perf


def test_fractal_seed_and_explorer_are_wired_into_r28_gui():
    main = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    engine = ROOT / "groovebox_v3" / "fractal_seed_engine.py"
    explorer = ROOT / "docs" / "fractal-seed-mode" / "musical_explorer.html"
    assert "self.btn_fractal_seed_mode = QPushButton" in main
    assert "self._fractal_seed_event_plan()" in main
    assert "rasterize_sequence(fractal_plan, n)" in main
    assert '"fractal_seed_provenance"' in main
    assert '"fractal_seed_mode_enabled"' in main
    assert "btn_musical_explorer" in main and "def _open_musical_explorer(self)" in main
    assert "docs" in main and "musical_explorer.html" in main
    assert engine.is_file() and explorer.is_file() and explorer.stat().st_size > 10_000


def test_math_lab_has_scroll_and_certain_trigger_gate():
    lab = (ROOT / "mathematical_composition_lab.py").read_text(encoding="utf-8")
    assert "QScrollArea" in lab
    assert 'step_automation["trigger_probability"] = [1.0] * steps' in lab
    assert 'event["probability"] = 1.0  # compatibility field; never a stochastic gate' in lab
    assert 'deterministic_trigger_profile' in lab


def test_audio_helper_does_not_reinitialize_mixer_on_live_volume_changes():
    helper = (ROOT / "BUILD_ISO" / "v35_22zz" / "sos-hardware-volume-v35_22zz_r23h").read_text(encoding="utf-8")
    router = (ROOT / "media_output_router.py").read_text(encoding="utf-8")
    widget = (ROOT / "hardware_volume.py").read_text(encoding="utf-8")
    boot = (ROOT / "BUILD_ISO" / "sos-system-media-ready-v35_22zs").read_text(encoding="utf-8")
    assert "DEFAULT_VOLUME=72" in helper
    assert 'alsactl init "$c"' not in helper
    set_block = helper.split("  set)\n", 1)[1].split("  up|down)", 1)[0]
    assert 'prepare_route "$c"' not in set_block
    assert "saved_volume" in helper and 'volume=$pct' in helper
    assert "_pending_value=int(value)" in widget
    assert "state={'volume':72" in widget
    assert 'if shutil.which("alsactl"):\n        qrun(["alsactl","init"' not in router
    route = router.split("def _prepare_physical_alsa_output(device: str) -> bool:", 1)[1].split("def _real_pulse_sink_available", 1)[0]
    assert 'qrun(["alsactl","init"' not in route
    assert 'if shutil.which("alsactl"):' not in route
    assert "capture" in route and "hardware-volume.state" in route
    assert "BOOT_VOLUME=72" in boot
    assert '[ "$saved" -ge 0 ]' in boot  # explicit saved zero remains valid
    assert "alsactl init" in boot        # one-time boot initialization retained


def test_sos_launcher_and_iso_stamp_package_the_gui_dependencies():
    launcher = (ROOT / "LAUNCH_GROOVEBOX_SOS.sh").read_text(encoding="utf-8")
    stamp = (ROOT / "BUILD_ISO" / "stamp_final_initramfs_v35_22zz.sh").read_text(encoding="utf-8")
    builder = (ROOT / "BUILD_KIT" / "build.py").read_text(encoding="utf-8")
    assert '"$ROOT/run_groovebox.py"' in launcher
    assert '"$ROOT/launch_groovebox.py"' not in launcher
    assert "groovebox_v3/fractal_seed_engine.py" in stamp
    assert "docs/fractal-seed-mode" in stamp
    assert "mathematical_composition_lab.py" in stamp
    assert "groovebox_v3.fractal_seed_engine" in builder
    assert '"docs/fractal-seed-mode"' in builder
    crc_bundle = ROOT / "BUILD_ISO" / "bundle_crc32c_modules_v35_22zq.py"
    crc_verify = ROOT / "BUILD_ISO" / "verify_crc32c_install_v35_22zq.py"
    build_checks = (ROOT / "BUILD_ISO" / "RUN_ME_v35_22.sh").read_text(encoding="utf-8")
    assert crc_bundle.is_file() and crc_verify.is_file()
    assert "GROOVEBOX_V35_22ZQ_CRC32C_EXT4_MOUNT_PREFLIGHT_20260924" in build_checks


def test_active_overlay_matches_root_for_all_modified_runtime_files():
    overlay = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz"
    for rel in ("groovebox.py", "performance.py", "media_output_router.py", "hardware_volume.py", "mathematical_composition_lab.py"):
        assert (ROOT / rel).read_bytes() == (overlay / rel).read_bytes(), rel
    for rel in ("__init__.py", "fractal_seed_engine.py", "cli.py"):
        assert (ROOT / "groovebox_v3" / rel).read_bytes() == (overlay / "groovebox_v3" / rel).read_bytes(), rel
    for rel in ("README.md", "musical_explorer.html"):
        assert (ROOT / "docs" / "fractal-seed-mode" / rel).read_bytes() == (overlay / "docs" / "fractal-seed-mode" / rel).read_bytes(), rel
    manifest = json.loads((ROOT / "APPLIANCE_FEATURE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["release_candidate"]["base_release"] == "R28.4.50"
    assert manifest["release_candidate"]["fresh_iso_built"] is False
    assert manifest["sos_audio_volume_contract"]["fresh_hardware_default_percent"] == 72
