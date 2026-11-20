from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parent


def _load_app_hub():
    spec = importlib.util.spec_from_file_location("gb_test_app_hub", ROOT / "app_hub.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_disables_bytecode_before_importing_application_modules():
    source = (ROOT / "run_groovebox.py").read_text(encoding="utf-8")
    assert source.index("sys.dont_write_bytecode = True") < source.index("from runtime_contract import")
    assert source.index('os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")') < source.index("from runtime_contract import")


def test_all_shared_launch_paths_disable_bytecode_before_python_preflight():
    for rel in ("run_hybrid.sh", "LAUNCH_GROOVEBOX_SOS.sh", "LAUNCH_GROOVEBOX_WINDOWS.bat", "scripts/launch_entry.sh"):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "PYTHONDONTWRITEBYTECODE" in source, rel
    launch_py = (ROOT / "launch_groovebox.py").read_text(encoding="utf-8")
    assert launch_py.index("PYTHONDONTWRITEBYTECODE") < launch_py.index("runpy.run_path")


def test_shared_runner_claims_or_activates_before_constructing_a_second_window():
    source = (ROOT / "run_groovebox.py").read_text(encoding="utf-8")
    assert source.index("acquire_or_activate(app") < source.index("player = MathematiciansGrooveboxApp()")
    assert 'if _SINGLE_INSTANCE_GUARD is None:' in source
    assert 'raise SystemExit(0)' in source
    assert '_SINGLE_INSTANCE_GUARD.set_main_window(player)' in source
    assert 'raise SystemExit(73)' in source


def test_single_instance_endpoint_is_user_session_scoped_and_uses_qt_local_server():
    source = (ROOT / "groovebox_single_instance.py").read_text(encoding="utf-8")
    assert "QLocalServer" in source and "QLocalSocket" in source and "QLockFile" in source
    assert '"XDG_SESSION_ID"' in source and '"XDG_RUNTIME_DIR"' in source
    assert "independent of install path" in source
    assert 'sock.write(b"ACTIVATE\\n")' in source
    assert "server.newConnection.connect" in source
    assert "window.raise_()" in source and "window.activateWindow()" in source


def test_apps_launcher_filters_the_current_groovebox_desktop_entries():
    hub = _load_app_hub()
    assert hub._is_this_groovebox_entry(
        "Mathematician's Groovebox", "/usr/share/applications/io.github.wittymoniker.MathematiciansGroovebox.desktop",
        "mathematicians-groovebox %F")
    assert hub._is_this_groovebox_entry(
        "Groovebox", "/usr/share/applications/app.wasmer.eski19758.Groovebox.desktop",
        "flatpak run app.wasmer.eski19758.Groovebox %F")
    assert hub._is_this_groovebox_entry("Groovebox", "/usr/share/applications/groovebox.desktop", "groovebox %F")
    assert not hub._is_this_groovebox_entry("Ardour", "/usr/share/applications/org.ardour.Ardour.desktop", "ardour %F")


def test_active_iso_overlay_matches_single_instance_runner_modules():
    overlay = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz"
    for rel in ("run_groovebox.py", "groovebox_single_instance.py", "app_hub.py"):
        assert (ROOT / rel).read_bytes() == (overlay / rel).read_bytes()


def test_iso_prepares_the_program_builder_language_runtimes():
    setup = (ROOT / "BUILD_ISO" / "runtime_setup_v35_22q.sh").read_text(encoding="utf-8")
    assert "build-essential golang-go" in setup
    assert "versions.json" in setup and "sha256sum -c" in setup
    assert "juliacall>=0.9.37,<0.10" in setup   # R114 pin (binary-dir discovery fix)
    assert 'PYTHON_JULIACALL_LIB="$JULIA_LIBJULIA"' in setup
    assert 'Pkg.add("PythonCall")' in setup
    sos = (ROOT / "LAUNCH_GROOVEBOX_SOS.sh").read_text(encoding="utf-8")
    assert "PYTHON_JULIACALL_EXE=/opt/sos/julia/bin/julia" in sos
    assert 'export PYTHON_JULIACALL_LIB="$JULIA_LIBJULIA"' in sos
    assert "JULIA_PKG_OFFLINE=true" in sos
    stamp = (ROOT / "BUILD_ISO" / "stamp_final_initramfs_v35_22zz.sh").read_text(encoding="utf-8")
    assert "rust-host.tar.gz" in stamp and "groovebox-rust-toolchain.sh" in stamp
    # R107/R108: syntax gates compile in memory; no compileall/py_compile bytecode writes into the image (R123 gate).
    assert "GROOVEBOX_R123_HOST_SYNTAX_GATE_NO_BYTECODE_20261119" in stamp and "py_compile" not in stamp and "smoke_test.jl" in stamp
    assert "R108: purge stale bytecode caches" in stamp
    assert "FAIL: bytecode cache remains in deployed app/helper tree" in stamp
    assert "JULIA_DEPOT_PATH=/tmp/groovebox-julia-depot:/opt/sos/julia-depot" in stamp
    assert 'PYTHON_JULIACALL_LIB="$JULIA_LIB_TARGET"' in stamp
    assert "R111_JULIACALL_EXPLICIT_LIB" in stamp


def test_julia_bridge_prefers_preinstalled_system_julia():
    source = (ROOT / "julia_bridge.py").read_text(encoding="utf-8")
    assert "shutil.which(\"julia\")" in source
    assert 'os.environ["PYTHON_JULIACALL_EXE"] = _system_julia' in source
    assert 'os.environ["PYTHON_JULIACALL_LIB"] = _julia_lib' in source
