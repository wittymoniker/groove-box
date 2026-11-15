from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_julia_bridge_loads_the_bundled_module_without_package_instantiation():
    source = (ROOT / "julia_bridge.py").read_text(encoding="utf-8")
    assert '"julia", "GrooveboxHybrid.jl"' in source
    assert 'include(raw"{source}")' in source
    assert "Pkg.instantiate()" not in source
    assert "using GrooveboxMeumOT" not in source


def test_julia_installers_use_the_bundled_smoke_test():
    for name in (
        "scripts/install_hybrid_linux.sh",
        "scripts/install_hybrid_macos.sh",
        "scripts/install_hybrid_windows.ps1",
    ):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "smoke_test.jl" in source
        assert "GrooveboxMeumOT" not in source
        assert "Pkg.instantiate()" not in source


def test_iso_runtime_sync_includes_bundled_julia_sources():
    source = (ROOT / "scripts/sync_runtime_payload.py").read_text(encoding="utf-8")
    assert 'Path("julia")' in source
    assert (ROOT / "BUILD_ISO/app-overlay-v35.22zz/julia/GrooveboxHybrid.jl").is_file()
    assert (ROOT / "BUILD_ISO/app-overlay-v35.22zz/julia/smoke_test.jl").is_file()


def test_build_doctor_checks_julia_when_available_without_making_it_mandatory():
    source = (ROOT / "BUILD_KIT/build.py").read_text(encoding="utf-8")
    assert 'shutil.which("julia")' in source
    assert "Julia source smoke: SKIPPED" in source
