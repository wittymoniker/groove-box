from __future__ import annotations

import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_compat_settings():
    path = ROOT / "compat_settings.py"
    spec = importlib.util.spec_from_file_location("compat_settings_r97_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_compatibility_enum_and_party_feel_settings_round_trip_cleanly():
    cs = load_compat_settings()
    raw = {
        "quick_rack_side": "left", "projects_bar_side": "right", "deck_side": "bottom",
        "thread_quality": "max", "compat_profile": "studio", "hardware_class": "desktop",
        "dev_overlay_rollback": "manual", "party_feel": "rave",
    }
    clean = cs._clean(raw)
    for key, value in raw.items():
        assert clean[key] == value
    assert cs._clean({"party_feel": "not-a-mode"})["party_feel"] == cs.DEFAULTS["party_feel"]


def test_untouched_default_migration_preserves_explicit_and_canonical_ownership():
    from groovebox_runtime.default_migrations import migrate_untouched_defaults
    settings = {"auto_scale": 100, "user_scale": 100, "canonical_field": 100}
    policies = {key: {"from": 100, "to": 0, "rationale": "display-aware automatic scaling"}
                for key in settings}
    result, audit = migrate_untouched_defaults(
        settings, policies, touched={"user_scale"}, canonical_owned={"canonical_field"})
    assert result == {"auto_scale": 0, "user_scale": 100, "canonical_field": 100}
    assert audit["count"] == 1 and len(audit["sha256"]) == 64


def test_labwc_source_and_runtime_config_have_fast_window_shortcuts():
    rc = ROOT / "iso_wm/labwc/rc.xml"
    tree = ET.parse(rc)
    keys = [node.attrib["key"] for node in tree.findall(".//keybind")]
    assert len(keys) == len(set(keys)), "duplicate labwc key bindings"
    actions = {node.attrib.get("name") for node in tree.findall(".//keybind/action")}
    assert {"NextWindowImmediate", "PreviousWindowImmediate", "MoveToEdge", "ToggleFullscreen"}.issubset(actions)
    launcher = (ROOT / "BUILD_ISO/groovebox-appliance-wayland-v35_22u").read_text()
    block = launcher.split("cat > \"$LABWC_CFG/rc.xml\" <<'EOF_R23H_LABWC'", 1)[1].split("EOF_R23H_LABWC", 1)[0]
    runtime_keys = [node.attrib["key"] for node in ET.fromstring(block.lstrip()).findall(".//keybind")]
    assert len(runtime_keys) == len(set(runtime_keys))
    assert "W-Tab" in runtime_keys and "W-S-Tab" in runtime_keys
    assert "cleanup_labwc" in launcher and "trap 'cleanup_labwc' EXIT" in launcher


def test_pid1_boot_quieting_and_emergency_console_are_present():
    init = (ROOT / "BUILD_ISO/init-v33a").read_text()
    recovery = (ROOT / "BUILD_ISO/sos-recovery-shell-v35_22u").read_text()
    for token in ("SOS_BOOT_LOG=/var/log/sos/boot.log", "echo 4 > /proc/sys/kernel/printk",
                  "pid1_emergency_console()", "trap 'emergency_rc=$?; pid1_emergency_console",
                  "exec 1>/dev/console 2>&1", "/usr/bin/sos-recovery-shell"):
        assert token in init
    for token in ("prepare", "reconnect", "debug", "status", "logs", "groovebox-appliance"):
        assert token in recovery


def test_runtime_modules_match_active_iso_overlay():
    for rel in ("groovebox_runtime/app_services.py", "groovebox_runtime/performance_budget.py",
                "groovebox_runtime/adaptive_scheduler.py", "groovebox_runtime/default_migrations.py",
                "compat_settings.py"):
        source = ROOT / rel
        staged = ROOT / "BUILD_ISO/app-overlay-v35.22zz" / rel
        assert source.is_file() and staged.is_file()
        assert source.read_bytes() == staged.read_bytes(), rel



def test_iso_pid1_patcher_uses_canonical_source_and_builds_recovery_surface():
    patcher = (ROOT / "BUILD_ISO/patch_live_boot_v32w.py").read_text()
    build = (ROOT / "BUILD_ISO/build_from_v31c_layered_cache_v32x.sh").read_text()
    init = (ROOT / "BUILD_ISO/init-v33a").read_text()
    assert "with_name('init-v33a')" in patcher
    assert "new_init = canonical_init.read_text" in patcher
    assert "canonical_init.read_text" in patcher
    assert 'python3 "$HERE/patch_live_boot_v32w.py" "$ROOTFS"' in build
    assert "run_pid1_child /usr/bin/sos-recovery-shell" in init
    assert "pid1_emergency_console()" in init


def test_explicit_party_mode_false_survives_final_migration_marker():
    cs = load_compat_settings()
    clean = cs._clean({"party_mode": False, "party_defaults_r6": True, "party_defaults_final": False})
    assert clean["party_mode"] is False
    assert clean["party_defaults_final"] is True
