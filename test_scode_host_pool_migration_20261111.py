from pathlib import Path
import threading

import thread_budget
from scode.window_host import WindowTaskScope


class _Window:
    pass


def test_aggregate_worker_budget_reserves_interactive_without_oversubscribing(monkeypatch):
    monkeypatch.setattr(thread_budget, "lane_workers", lambda: 4)
    assert thread_budget.interactive_workers() == 1
    assert thread_budget.bulk_workers() == 3
    budget = thread_budget.scheduler_budget()
    assert budget["total_workers"] == 4
    assert budget["bulk_workers"] + budget["interactive_workers"] == 4


def test_single_worker_budget_uses_one_shared_class_without_extra_pool(monkeypatch):
    monkeypatch.setattr(thread_budget, "lane_workers", lambda: 1)
    assert thread_budget.interactive_workers() == 0
    assert thread_budget.bulk_workers() == 1
    assert thread_budget.scheduler_budget()["total_workers"] == 1


def test_window_task_scope_delivers_results_and_tracks_generation():
    window = _Window()
    scope = WindowTaskScope(window, "wtest")
    seen = []
    future = scope.submit(lambda x: x * 3, 7, callback=lambda result, error: seen.append((result, error)))
    assert future.result(timeout=5) == 21
    # The non-Qt fallback executes the callback on completion; the Qt host
    # relays the same payload through a queued GUI-thread signal.
    assert seen == [(21, None)]
    old_generation = scope.generation
    scope.invalidate()
    assert scope.generation == old_generation + 1
    scope.close()
    assert scope.stats()["closed"] is True


def test_window_task_scope_rejects_submissions_after_close():
    scope = WindowTaskScope(_Window(), "wclosed")
    scope.close()
    try:
        scope.submit(lambda: 1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("closed window scope accepted work")


def test_runner_installs_scode_window_host_before_constructing_main_window():
    source = (Path(__file__).resolve().parent / "run_groovebox.py").read_text(encoding="utf-8")
    host = source.index("install_scode_window_host(app)")
    construct = source.index("player = MathematiciansGrooveboxApp()")
    assert host < construct
    assert "_SCODE_WINDOW_HOST.register_window(player)" in source


def test_julia_warmup_is_deferred_and_does_not_initialize_during_module_import():
    source = (Path(__file__).resolve().parent / "julia_bridge.py").read_text(encoding="utf-8")
    assert "schedule_julia_warmup" in source
    assert "try:\n    _init_julia()" not in source
    call = source[source.index("def _call("):source.index("def jl_ot_prod(")]
    assert "if not _jl_ready" in call and "return None" in call


def test_accelerator_capability_report_is_noninvasive_and_keeps_python_fallback():
    import platform_runtime
    report = platform_runtime.accelerator_status()
    assert report["python_fallback"] is True
    assert report["selected_native"] in ("rust", "cpp", "python")
    assert "julia" in report and "scode_stage0" in report


def test_backend_diagnostics_do_not_deadlock_on_availability_lock():
    from process_policy import Backends
    report = Backends.report()
    assert set(report["available"]) == set(Backends.ORDER)


def test_optional_hardware_and_nearby_work_use_shared_bounded_lanes():
    root = Path(__file__).resolve().parent
    audio = (root / "audio_os_backend.py").read_text(encoding="utf-8")
    nearby = (root / "nearby_groovebox.py").read_text(encoding="utf-8")
    warm = audio[audio.index("def warm_hardware_parallel"):audio.index("class RenderStreamBridge")]
    sweep = nearby[nearby.index("    def sweep_subnet("):nearby.index("    def _sweep_loop(")]
    assert 'make_lane("hardware-warmup"' in warm
    assert 'make_lane("nearby-subnet-sweep"' in nearby
    assert 'ThreadPoolExecutor(' not in sweep
    assert "range(0, len(hosts), 254)" in sweep


def test_fractal_package_pools_use_the_shared_scheduler():
    source = (Path(__file__).resolve().parent / "groovebox_fractal/groovebox_fractal/concurrency.py").read_text(encoding="utf-8")
    assert 'make_lane("fractal-ui-offload"' in source
    assert 'make_lane("fractal-project"' in source
    assert 'make_lane("fractal-encode"' in source
    assert "thread_budget.bulk_workers() >= 2" in source


def test_live_recording_fallback_is_lazy_and_saturation_does_not_spawn_threads():
    source = (Path(__file__).resolve().parent / "live_player.py").read_text(encoding="utf-8")
    init = source[source.index("class LivePlayerWindow"):source.index("def _", source.index("class LivePlayerWindow"))]
    assert "self._record_local_pool = None" in source
    assert "if not submitted and lane is None" in source
    assert "Shared interactive lane saturated: skip this video frame" in source


def test_runtime_payload_sync_includes_scode_and_fractal_python_packages():
    source = (Path(__file__).resolve().parent / "scripts/sync_runtime_payload.py").read_text(encoding="utf-8")
    assert 'Path("scode")' in source
    assert 'Path("groovebox_fractal") / "groovebox_fractal"' in source
    overlay = Path(__file__).resolve().parent / "BUILD_ISO/app-overlay-v35.22zz"
    assert (overlay / "scode/window_host.py").is_file()
    assert (overlay / "groovebox_fractal/groovebox_fractal/concurrency.py").is_file()
