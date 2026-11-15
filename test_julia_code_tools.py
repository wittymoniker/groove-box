from pathlib import Path

import julia_code


def test_julia_code_project_is_packaged():
    assert julia_code.julia_project_dir().is_dir()
    assert (julia_code.julia_project_dir() / "Project.toml").is_file()
    assert (julia_code.julia_project_dir() / "src" / "GrooveboxMeumOT.jl").is_file()


def test_julia_code_missing_runtime_is_graceful():
    if julia_code.julia_executable():
        return
    status = julia_code.runtime_status()
    assert status["available"] is False
    assert "not found" in status["message"].lower()
    checked = julia_code.check_source("println(1)")
    assert checked.ok is False
    assert "deferred" in checked.error.lower()
    executed = julia_code.run_source("println(1)")
    assert executed.ok is False
    assert "not installed" in executed.error.lower()


def test_shared_julia_executable_override(monkeypatch, tmp_path):
    fake = tmp_path / "julia"
    fake.write_text("#!/bin/sh\necho Julia version 1.10.0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("GROOVEBOX_JULIA_EXECUTABLE", str(fake))
    assert julia_code.julia_executable() == str(fake.resolve())


def test_dsp_julia_module_uses_canonical_inverse_and_no_placeholder():
    source = (Path(__file__).parent / "julia" / "src" / "GrooveboxMeumOT.jl").read_text(encoding="utf-8")
    assert "const MEUM_INV = 1.0 / MEUM" in source
    assert "0.834?" not in source


def test_dsp_bridge_does_not_instantiate_packages_at_startup():
    source = (Path(__file__).parent / "julia_bridge.py").read_text(encoding="utf-8")
    assert "Pkg.instantiate()" not in source
    assert "julia_executable" in source


def test_developer_overlay_uses_shared_julia_project():
    source = (Path(__file__).parent / "dev_overlay.py").read_text(encoding="utf-8")
    assert "julia_code.julia_executable()" in source
    assert "julia_code.check_source" in source
    assert "julia_code.command_for_file(path)" in source


def test_juliacode_ide_is_exposed_in_script_studio_and_dev_overlay():
    root = Path(__file__).parent
    script = (root / "script_studio.py").read_text(encoding="utf-8")
    dev = (root / "dev_overlay_ui.py").read_text(encoding="utf-8")
    actions = (root / "window_bar_tools.py").read_text(encoding="utf-8")
    assert "JuliaCode IDE" in script and "julia_code_studio.open_window" in script
    assert "JuliaCode IDE" in dev and "julia_code_studio.open_window" in dev
    assert "_open_juliacode" in actions


def test_julia_code_process_is_project_scoped_and_no_startup_file():
    source = (Path(__file__).parent / "julia_code.py").read_text(encoding="utf-8")
    assert '"--startup-file=no"' in source
    assert 'f"--project={PROJECT_DIR}"' in source
    assert "MAX_SOURCE_BYTES" in source


def test_startup_splash_is_opt_out_and_updates_without_event_pump():
    root = Path(__file__).parent
    splash = (root / "startup_loading.py").read_text(encoding="utf-8")
    main = (root / "groovebox.py").read_text(encoding="utf-8")
    launcher = (root / "run_groovebox.py").read_text(encoding="utf-8")
    assert "GROOVEBOX_NO_STARTUP_LOADING" in splash
    assert "self.repaint()" in splash
    assert "processEvents" not in splash.split("def update_startup_loading", 1)[-1]
    assert "_groovebox_startup_progress" in main
    assert "show_startup_loading" in launcher and "close_startup_loading" in launcher
