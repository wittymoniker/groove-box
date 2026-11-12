"""Tests for R30.3 Python/runtime and uniform UI publication contracts."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from ui_runtime import _PendingQueue, make_qt_pool
from runtime_contract import MIN_PYTHON, interpreter_is_supported


def test_runtime_baseline_is_explicit_and_supported_by_this_source():
    assert MIN_PYTHON == (3, 10)
    assert sys.version_info >= MIN_PYTHON
    assert interpreter_is_supported("cpython", (3, 10, 0))
    assert not interpreter_is_supported("pypy", (3, 12, 0))
    assert not interpreter_is_supported("cpython", (3, 9, 18))


def test_ui_queue_is_bounded():
    q = _PendingQueue(max_pending=2)
    assert q.put(lambda: None, key=None)
    assert q.put(lambda: None, key=None)
    assert not q.put(lambda: None, key=None)
    assert len(q) == 2


def test_ui_queue_coalesces_latest_value_for_same_key():
    q = _PendingQueue(max_pending=2)
    values = []
    assert q.put(values.append, (1,), key="meter")
    assert q.put(values.append, (2,), key="meter")
    assert len(q) == 1
    callback, args, kwargs = q.pop_batch(4)[0]
    callback(*args, **kwargs)
    assert values == [2]


def test_ui_queue_keeps_distinct_events_and_fifo_order():
    q = _PendingQueue(max_pending=4)
    seen = []
    q.put(seen.append, ("a",), key="a")
    q.put(seen.append, ("b",), key="b")
    for callback, args, kwargs in q.pop_batch(4):
        callback(*args, **kwargs)
    assert seen == ["a", "b"]


def test_main_and_direct_entrypoints_install_one_gui_dispatcher_before_windows():
    main = (ROOT / "run_groovebox.py").read_text(encoding="utf-8")
    assert main.index("app = QApplication(sys.argv)") < main.index("_install_ui_runtime(app)")
    assert main.index("_install_ui_runtime(app)") < main.index("player = MathematiciansGrooveboxApp()")
    direct = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert "from ui_runtime import install_ui_runtime" in direct
    assert "interpreter_error()" in direct
    assert direct.index("interpreter_error()") < direct.index("import numpy as np")
    assert "interpreter_error()" in main
    assert main.index("interpreter_error()") < main.index("from groovebox import")


def test_live_player_uses_non_polling_ui_publication_for_io_tasks():
    source = (ROOT / "live_player.py").read_text(encoding="utf-8")
    assert "submit_ui_task(" in source
    assert "def _media_loaded(self, payload):" in source
    assert "QTimer.singleShot(100, self._media_loaded)" not in source
    assert "def _poll_msg(self):" not in source
    # Recorder finalization runs in the worker; MCC export/status update happen in the UI callback.
    finish = source[source.index("    def _finish_rec(self):"):source.index("    # -- control", source.index("    def _finish_rec(self):"))]
    assert "submit_ui_task(" in finish
    assert "rec.finish" in finish
    assert "self._export_mcc_after_take(paths)" in finish


def test_clip_timeline_uses_shared_ui_task_lane_instead_of_private_qthreadpool():
    source = (ROOT / "clip_timeline_studio.py").read_text(encoding="utf-8")
    assert "submit_ui_task(" in source
    assert "QThreadPool(" not in source
    assert "job.signals" not in source


def test_main_application_lanes_are_shared_and_bounded():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    block = source[source.index("# R30.3_SHARED_SCODE_SCHEDULER"):source.index("self._project_memory_bridge", source.index("# R30.3_SHARED_SCODE_SCHEDULER"))]
    assert block.count("_make_lane(") >= 6
    assert "max_pending=" in block
    assert 'ThreadPoolExecutor(max_workers=_par' not in block


def test_legacy_blocking_export_helper_is_explicitly_identified_for_followup():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    method = source[source.index("    def _run_off_gui(self, fn):"):source.index("    # ------------------------------------------------------------------", source.index("    def _run_off_gui(self, fn):"))]
    assert "return fut.result()" in method  # retained, and must remain visible in the audit report
    assert "legacy" in (ROOT / "RUNTIME-UI-CONTRACT-R30.3.md").read_text(encoding="utf-8").lower()


def test_performance_window_pools_are_shared_scode_lanes_not_private_qt_pools():
    source = (ROOT / "performance.py").read_text(encoding="utf-8")
    assert "QThreadPool(" not in source
    assert source.count("make_qt_pool(") >= 4
    assert "performance-file-manager" in source
    assert "performance-probes" in source


def test_shared_qt_pool_adapter_runs_qrunnable_style_tasks():
    from threading import Event
    completed = Event()
    class Task:
        def run(self):
            completed.set()
    pool = make_qt_pool("test-ui-pool-adapter", max_workers=1, max_pending=4)
    future = pool.start(Task())
    assert pool.waitForDone(3000)
    assert future.done() and future.exception() is None
    assert completed.is_set()


def test_shared_qt_pool_clear_cancels_queued_work():
    from threading import Event
    entered, release, second_ran = Event(), Event(), Event()
    class Blocker:
        def run(self):
            entered.set()
            assert release.wait(3)
    class Second:
        def run(self):
            second_ran.set()
    pool = make_qt_pool("test-ui-pool-clear", max_workers=1, max_pending=4)
    first = pool.start(Blocker())
    assert entered.wait(2)
    second = pool.start(Second())
    assert pool.clear() == 1
    release.set()
    assert pool.waitForDone(3000)
    assert first.done()
    assert second.cancelled()
    assert not second_ran.is_set()


def test_core_window_worker_pool_constructors_are_unified():
    for name in ("groovebox.py", "performance.py", "video_clip_studio.py", "clip_timeline_studio.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "= QThreadPool(" not in source, name


def test_usb_worker_completions_publish_through_the_ui_dispatcher():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert 'make_lane("usb-storage"' in source
    assert 'post_to_ui(_apply, result, key=("usb-drive-detect", id(self)))' in source
    assert 'post_to_ui(_done, result, key=("usb-drive-flush", id(self)))' in source
    assert 'QTimer.singleShot(0, lambda: _apply(f.result()))' not in source


def test_video_object_and_canonical_engine_work_use_bounded_shared_lanes():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert 'make_lane("video-object"' in source
    assert 'make_lane(f"canonical-engine-{key[:24]}"' in source
