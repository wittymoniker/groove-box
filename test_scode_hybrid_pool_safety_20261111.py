from pathlib import Path
import threading

import thread_budget

ROOT = Path(__file__).resolve().parent


def test_managed_worker_detection_is_specific_to_shared_pool_threads(monkeypatch):
    monkeypatch.setattr(threading, "current_thread", lambda: type("T", (), {"name": "groovebox-work_2"})())
    assert thread_budget.is_managed_worker_thread() is True
    monkeypatch.setattr(threading, "current_thread", lambda: type("T", (), {"name": "MainThread"})())
    assert thread_budget.is_managed_worker_thread() is False


def test_native_rust_inner_parallelism_is_disabled_inside_shared_workers():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    block = source[source.index("def _native_tune_workers("):source.index("def _native_boxcar_abs_same(")]
    assert "is_managed_worker_thread()" in block
    assert "want = 1" in block


def test_julia_object_construction_never_initializes_runtime_inline():
    source = (ROOT / "julia_bridge.py").read_text(encoding="utf-8")
    block = source[source.index("class JuliaMeumOscillator:"):source.index("    @staticmethod", source.index("class JuliaMeumOscillator:"))]
    assert "if not _jl_ready" in block
    assert "schedule_julia_warmup() first" in block
    assert "_init_julia()" not in block


def test_scode_host_closes_window_scopes_on_qt_shutdown():
    source = (ROOT / "scode/window_host.py").read_text(encoding="utf-8")
    assert "app.aboutToQuit.connect(self.close)" in source


def test_alternate_scode_launcher_installs_same_queued_ui_dispatcher():
    source = (ROOT / "scode/runtime.py").read_text(encoding="utf-8")
    assert "install_ui_runtime(app)" in source
    assert "UI dispatcher unavailable" in source
    assert "install_scode_window_host(app)" in source
