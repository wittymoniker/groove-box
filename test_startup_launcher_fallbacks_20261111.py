from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_all_source_launchers_converge_on_validated_shared_entry():
    for name in (
        "START_GROOVEBOX.sh", "LAUNCH_GROOVEBOX_LINUX.sh",
        "launch_desktop.sh", "launch_mobile.sh", "LAUNCH_GROOVEBOX_MACOS.command",
    ):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "scripts/launch_entry.sh" in source, name


def test_shared_entry_prefers_full_runtime_then_uses_runner_preflight_fallback():
    source = (ROOT / "scripts/launch_entry.sh").read_text(encoding="utf-8")
    assert 'if [[ -s "$ROOT/run_hybrid.sh" ]]' in source
    assert 'exec bash "$ROOT/run_hybrid.sh" "$@"' in source
    assert 'exec "$PY" "$ROOT/run_groovebox.py" "$@"' in source
    assert "GROOVEBOX_PYTHON" in source
    assert "No usable startup entry point" in source


def test_appliance_launcher_keeps_preinstalled_runtime_and_never_runs_desktop_installer():
    source = (ROOT / "LAUNCH_GROOVEBOX_SOS.sh").read_text(encoding="utf-8")
    assert 'GROOVEBOX_APPLIANCE=1' in source
    assert 'GROOVEBOX_PROFILE=sos' in source
    assert 'run_groovebox.py' in source
    assert 'run_hybrid.sh' not in source
    assert '/opt/pyvenv/bin/python3' in source
    assert '/usr/bin/python3' in source
    assert 'from runtime_contract import REQUIRED' in source


def test_runner_keeps_required_preflight_before_qt_and_window_construction():
    source = (ROOT / "run_groovebox.py").read_text(encoding="utf-8")
    assert source.index("_ensure_qt_webengine_runtime()") < source.index("from groovebox import")
    assert source.index("_LOCAL_FFMPEG = _require_local_ffmpeg()") < source.index("from groovebox import")
    assert source.index("_SCODE_PREFLIGHT = require_scode_runtime()") < source.index("from groovebox import")
    assert source.index("app = QApplication(sys.argv)") < source.index("player = MathematiciansGrooveboxApp()")
    assert source.index("_install_ui_runtime(app)") < source.index("player = MathematiciansGrooveboxApp()")


def test_startup_selector_failure_reveals_main_window_and_keeps_event_loop_alive():
    source = (ROOT / "run_groovebox.py").read_text(encoding="utf-8")
    selector = source[source.index("try:\n            _startup_choice = launch_startup_mode_selector"):source.index('print(f"[Startup] selector complete', source.index("try:\n            _startup_choice = launch_startup_mode_selector"))]
    assert 'except Exception as _selector_exc' in selector
    assert 'player.showNormal()' in selector and 'player.show()' in selector
    assert 'player._install_project_autosave()' in selector
    assert '_startup_choice = "main-fallback"' in selector


def test_flatpak_and_installed_linux_launchers_use_shared_runner_with_fallbacks():
    flatpak = (ROOT / "packaging/flathub/flatpak-launch").read_text(encoding="utf-8")
    assert 'run_groovebox.py' in flatpak
    assert 'GROOVEBOX_FLATPAK=1' in flatpak
    install = (ROOT / "packaging/linux/install_desktop.sh").read_text(encoding="utf-8")
    assert 'if [[ -s "$APPROOT/run_hybrid.sh" ]]' in install
    assert 'scripts/launch_entry.sh' in install
    relaunch = (ROOT / "relaunch_groovebox.sh").read_text(encoding="utf-8")
    assert 'scripts/launch_entry.sh' in relaunch
