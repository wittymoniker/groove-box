"""Focused regressions for the safe-V3 merge, not the alternate GUI layouts."""
import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent


def test_process_cpu_count_is_an_integer(monkeypatch):
    import thread_budget as budget
    monkeypatch.setattr(budget.os, "sched_getaffinity",
                        lambda _: (_ for _ in ()).throw(OSError()), raising=False)
    monkeypatch.setattr(budget.os, "process_cpu_count", lambda: 3, raising=False)
    monkeypatch.setattr(budget.os, "cpu_count", lambda: 99)
    assert budget.usable_cores() == 3


def test_running_lane_job_cannot_claim_cancellation():
    from thread_budget import make_lane
    lane = make_lane("cancel-regression", max_workers=1, max_pending=3)
    started, release = Event(), Event()
    touched = []

    def job():
        started.set()
        release.wait(3)
        return 42

    first = lane.submit(job)
    try:
        assert started.wait(2)
        assert not first.cancel()
        queued = lane.submit(lambda: touched.append("should not run"))
        assert queued.cancel()
        release.set()
        assert first.result(timeout=2) == 42
        lane.shutdown(wait=True)
        assert touched == []
    finally:
        release.set()


def test_scode_foreground_requests_never_wait_and_latest_snapshot_wins():
    from scode_optimizer_bridge import SCodeOptimizerBridge
    optimizer = object.__new__(SCodeOptimizerBridge)
    optimizer._worker = ThreadPoolExecutor(max_workers=1)
    optimizer._frame = 0
    optimizer._last_plan = {"run_canonical": 0}
    optimizer._host_categories = lambda host: {"version": host.version}
    optimizer.editing_active = lambda host: False
    started, release = Event(), Event()
    calls = []

    def optimize(cats, *args, **kwargs):
        calls.append(cats["version"])
        if cats["version"] == 1:
            started.set()
            assert release.wait(3)
        return {"run_canonical": 1, "version": cats["version"]}

    optimizer.optimize_sync = optimize
    host = SimpleNamespace(version=1, master_playlist_data=[])
    try:
        before = perf_counter()
        plan = optimizer.request_host_plan(host)
        assert perf_counter() - before < 0.25
        assert plan["run_canonical"] == 1
        assert started.wait(2)
        first = optimizer._foreground_plan_pending[1]
        host.version = 2
        optimizer.request_host_plan(host)
        host.version = 3
        optimizer.request_host_plan(host)
        release.set()
        first.result(timeout=2)
        optimizer._collect_requested_plan(host)
        assert optimizer._last_plan.get("version") != 1
        optimizer._foreground_plan_pending[1].result(timeout=2)
        optimizer._collect_requested_plan(host)
        assert optimizer._last_plan["version"] == 3
        assert calls == [1, 3]
    finally:
        release.set()
        optimizer._worker.shutdown(wait=True)


def test_canonical_rng_preparation_preserves_sorted_private_streams():
    source = (ROOT / "groovebox.py").read_text()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "MathematiciansGrooveboxApp")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_prepare_active_canonical_engines_threaded")
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in ("submit", "result") for n in ast.walk(method))
    namespace = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "<rng-method>", "exec"), namespace)
    seed = lambda engine: sum(map(ord, engine)) % (2**32)
    host = SimpleNamespace(
        _canonical_seed_for_source=seed,
        _prepare_canonical_engine_rng=lambda engine, value: (value, np.random.default_rng(value)))
    result = namespace[method.name](host, ["seeded", "euclidean", "goava"])
    assert list(result) == ["euclidean", "goava", "seeded"]
    for engine, (value, generator) in result.items():
        assert value == seed(engine)
        assert np.array_equal(generator.random(32), np.random.default_rng(value).random(32))


def test_random_asset_generation_is_nondestructive(tmp_path, monkeypatch):
    import random_object
    monkeypatch.setattr(random_object, "_samples_dir", lambda host: tmp_path)
    host = SimpleNamespace()
    a = random_object.generate_random_object(host, "voxel", seed="repeatable", voxel_count=12)
    original = Path(a["path"]).read_bytes()
    b = random_object.generate_random_object(host, "voxel", seed="repeatable", voxel_count=12)
    assert a["path"] != b["path"]
    assert Path(a["path"]).read_bytes() == original
    assert Path(b["path"]).read_bytes() == original


def test_pooled_frame_callback_does_not_retain_the_viewer():
    import gc
    import weakref
    tree = ast.parse((ROOT / "groovebox.py").read_text())
    viewer_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                      and n.name == "VideoSynthViewer")
    method = next(n for n in viewer_cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_request_async_frame")
    namespace = {"weakref": weakref}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "<viewer-method>", "exec"), namespace)
    jobs = []
    optimizer = SimpleNamespace(submit_pooled=lambda *args, **kwargs: jobs.append((args, kwargs)))
    engine = SimpleNamespace(app=SimpleNamespace(_scode_optimizer=optimizer), export_mode=False,
                             render_frame=lambda *args, **kwargs: "frame")

    class Viewer:
        _request_async_frame = namespace["_request_async_frame"]
        def __init__(self):
            self.engine = engine
            self._render_shutdown = False
            self._render_lifetime = {"dead": False}
            self._render_generation = 0
            self._render_inflight = False
        def width(self):
            return 320
        def height(self):
            return 240
        def _on_async_frame_ready(self, *args):
            raise AssertionError("destroyed/dead viewer was touched")

    viewer = Viewer()
    viewer._request_async_frame()
    callback = jobs[0][1]["callback"]
    viewer._render_lifetime["dead"] = True
    callback(None, None)
    ref = weakref.ref(viewer)
    del viewer
    gc.collect()
    assert ref() is None
    callback(None, None)
    assert jobs[0][0][2]() == "frame"
