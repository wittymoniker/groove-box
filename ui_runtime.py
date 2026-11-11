"""Uniform Qt UI dispatch and background-task publication for Groovebox.

Contract:
- QWidget/QObject-facing callbacks are executed only on QApplication's thread.
- Worker tasks use the bounded process-wide sCode/shared-work executor.
- UI publications are queued, bounded, and optionally coalesced by key.
- Results for obsolete UI generations are discarded before touching widgets.

Workers must receive immutable snapshots and must never read or mutate widgets.
"""
from __future__ import annotations

from collections import OrderedDict
import itertools
import threading
import traceback
import weakref

_MAX_PENDING_UI_CALLS = 2048
_DRAIN_BATCH = 64
_APP_ATTR = "_groovebox_ui_dispatcher"
_GLOBAL_LOCK = threading.RLock()
_GLOBAL_APP_REF = None
_GLOBAL_DISPATCHER = None
_TASK_LANE = None
_TASK_LANE_LOCK = threading.Lock()
_SEQUENCE = itertools.count(1)
_UNSET = object()


class _PendingQueue:
    """Thread-safe bounded FIFO with last-write-wins coalescing keys."""
    def __init__(self, max_pending=_MAX_PENDING_UI_CALLS):
        self.max_pending = max(1, int(max_pending))
        self._lock = threading.Lock()
        self._items = OrderedDict()

    def put(self, callback, args=(), kwargs=None, key=None):
        with self._lock:
            token = ("key", key) if key is not None else ("seq", next(_SEQUENCE))
            if token not in self._items and len(self._items) >= self.max_pending:
                return False
            self._items[token] = (callback, tuple(args), dict(kwargs or {}))
            self._items.move_to_end(token)
            return True

    def pop_batch(self, limit):
        out = []
        with self._lock:
            for _ in range(min(max(1, int(limit)), len(self._items))):
                _key, item = self._items.popitem(last=False)
                out.append(item)
        return out

    def __len__(self):
        with self._lock:
            return len(self._items)

    def clear(self):
        with self._lock:
            self._items.clear()


class UiDispatchUnavailable(RuntimeError):
    """Raised when a UI task is submitted without a live Qt application."""


class SharedQtPool:
    """Small QThreadPool-compatible adapter backed by sCode's shared executor.

    It intentionally implements only the methods used by Groovebox workers:
    start, setMaxThreadCount, activeThreadCount, clear and waitForDone.
    QRunnable.run executes on the shared background executor; its QObject
    signals continue to use Qt's queued cross-thread delivery semantics.
    """
    def __init__(self, name="qt-workers", max_workers=1, max_pending=128, parent=None, kind=None):
        import thread_budget
        self.name = str(name)
        self._lane = thread_budget.make_lane(self.name, max_workers=max_workers,
                                             max_pending=max_pending, kind=kind)
        self._lock = threading.RLock()
        self._futures = set()
        try:
            self._parent_ref = weakref.ref(parent) if parent is not None else None
        except TypeError:
            self._parent_ref = None

    def start(self, runnable, priority=0):
        run = getattr(runnable, "run", None)
        if not callable(run):
            raise TypeError("SharedQtPool.start expects an object with run()")
        future = self._lane.submit_prioritized(float(priority), run)
        with self._lock:
            self._futures.add(future)
        def _discard(done):
            with self._lock:
                self._futures.discard(done)
        future.add_done_callback(_discard)
        return future

    def setMaxThreadCount(self, count):
        return self._lane.set_max_workers(count)

    def maxThreadCount(self):
        return int(self._lane.stats()["max_workers"])

    def activeThreadCount(self):
        return int(self._lane.stats()["active"])

    def clear(self):
        return self._lane.cancel_pending()

    def waitForDone(self, msecs=-1):
        import time
        timeout = None if int(msecs) < 0 else float(msecs) / 1000.0
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            stats = self._lane.stats()
            if not stats["active"] and not stats["queued"]:
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.005)


def make_qt_pool(name="qt-workers", max_workers=1, max_pending=128, parent=None, kind=None):
    """Create a QThreadPool-compatible lane that shares sCode worker threads (bulk or interactive class)."""
    return SharedQtPool(name=name, max_workers=max_workers, max_pending=max_pending, parent=parent, kind=kind)


def install_ui_runtime(app=None, *, max_pending=_MAX_PENDING_UI_CALLS):
    """Install one process-wide queued dispatcher on QApplication's GUI thread.

    Safe to call repeatedly from the GUI thread. The bridge is parented to the
    application so its lifetime matches Qt's event loop.
    """
    global _GLOBAL_APP_REF, _GLOBAL_DISPATCHER
    from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
    from PyQt6.QtWidgets import QApplication

    app = app or QApplication.instance()
    if app is None:
        raise UiDispatchUnavailable("QApplication must exist before installing the UI dispatcher")
    if QThread.currentThread() != app.thread():
        raise RuntimeError("install_ui_runtime must run on QApplication's GUI thread")

    with _GLOBAL_LOCK:
        existing = getattr(app, _APP_ATTR, None)
        if existing is not None and not getattr(existing, "closed", False):
            _GLOBAL_APP_REF = weakref.ref(app)
            _GLOBAL_DISPATCHER = existing
            return existing

        class _Bridge(QObject):
            wake = pyqtSignal()

            def __init__(self, parent, capacity):
                super().__init__(parent)
                self._app_ref = weakref.ref(parent)
                self._pending = _PendingQueue(capacity)
                self._state_lock = threading.RLock()
                self._scheduled = False
                self.closed = False
                self.wake.connect(self._drain, Qt.ConnectionType.QueuedConnection)

            def post(self, callback, args=(), kwargs=None, key=None):
                if not callable(callback):
                    raise TypeError("post_to_ui requires a callable")
                with self._state_lock:
                    if self.closed:
                        return False
                    accepted = self._pending.put(callback, tuple(args), dict(kwargs or {}), key)
                    if not accepted:
                        return False
                    if not self._scheduled:
                        self._scheduled = True
                        self.wake.emit()
                return True

            @pyqtSlot()
            def _drain(self):
                app_obj = self._app_ref()
                if app_obj is None or self.closed:
                    self.close()
                    return
                if QThread.currentThread() != app_obj.thread():
                    # The queued connection should make this impossible. Keep
                    # a defensive re-queue rather than execute a widget callback
                    # on an unexpected thread.
                    self.wake.emit()
                    return
                for callback, args, kwargs in self._pending.pop_batch(_DRAIN_BATCH):
                    try:
                        callback(*args, **kwargs)
                    except RuntimeError:
                        # Qt wrappers can be deleted between scheduling and
                        # delivery (for example, a window closed during a load).
                        continue
                    except Exception:
                        traceback.print_exc()
                with self._state_lock:
                    if self.closed:
                        self._scheduled = False
                    elif len(self._pending):
                        self.wake.emit()
                    else:
                        self._scheduled = False

            def close(self):
                with self._state_lock:
                    self.closed = True
                    self._scheduled = False
                    self._pending.clear()

        bridge = _Bridge(app, max_pending)
        setattr(app, _APP_ATTR, bridge)
        app.aboutToQuit.connect(bridge.close)
        _GLOBAL_APP_REF = weakref.ref(app)
        _GLOBAL_DISPATCHER = bridge
        return bridge


def _current_dispatcher(install=False):
    global _GLOBAL_APP_REF, _GLOBAL_DISPATCHER
    with _GLOBAL_LOCK:
        app = _GLOBAL_APP_REF() if _GLOBAL_APP_REF is not None else None
        bridge = _GLOBAL_DISPATCHER
    if app is not None and bridge is not None and not getattr(bridge, "closed", False):
        return bridge
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
    except Exception:
        app = None
    if app is None:
        return None
    if install:
        return install_ui_runtime(app)
    return getattr(app, _APP_ATTR, None)


def is_ui_thread():
    """Return whether the caller is on the current QApplication thread."""
    try:
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        return app is None or QThread.currentThread() == app.thread()
    except Exception:
        return True


def assert_ui_thread(operation="Qt UI operation"):
    """Fail loudly if a caller attempts to touch widgets from a worker."""
    if not is_ui_thread():
        raise RuntimeError(f"{operation} must run on QApplication's GUI thread")
    return True


def post_to_ui(callback, *args, key=None, **kwargs):
    """Queue a callback on the Qt GUI thread; never invokes it inline."""
    bridge = _current_dispatcher(install=False)
    if bridge is None:
        return False
    return bridge.post(callback, args=args, kwargs=kwargs, key=key)


def _shared_ui_lane():
    global _TASK_LANE
    if _TASK_LANE is None:
        with _TASK_LANE_LOCK:
            if _TASK_LANE is None:
                import thread_budget
                _TASK_LANE = thread_budget.make_lane(
                    "ui-background", max_workers=max(1, min(2, thread_budget.lane_workers())),
                    max_pending=128, kind="bulk",
                )
    return _TASK_LANE


def submit_ui_task(owner, worker, /, *args, on_result=None, on_error=None,
                   lane=None, generation_attr="_ui_generation", generation=_UNSET,
                   key="task", **kwargs):
    """Submit pure work and publish its result through the GUI dispatcher.

    ``worker`` must not touch Qt widgets. ``on_result(value)`` and
    ``on_error(exception)`` always execute on the GUI thread. If ``owner`` is
    deleted or its generation changes before completion, publication is dropped.
    No UI thread waits on the returned Future.
    """
    bridge = _current_dispatcher(install=True)
    if bridge is None:
        raise UiDispatchUnavailable("no QApplication dispatcher is available")
    if owner is not None:
        try:
            owner_ref = weakref.ref(owner)
        except TypeError:
            owner_ref = lambda: owner
    else:
        owner_ref = None
    if generation is _UNSET:
        generation_value = getattr(owner, generation_attr, None) if owner is not None else None
    else:
        generation_value = generation
    work_lane = lane or _shared_ui_lane()
    future = work_lane.submit(worker, *args, **kwargs)

    def _completed(done):
        try:
            result = done.result()  # completion callback runs on a worker thread
            error = None
        except BaseException as exc:
            result, error = None, exc

        def _deliver():
            live_owner = owner_ref() if owner_ref is not None else None
            if owner_ref is not None and live_owner is None:
                return
            if (live_owner is not None and generation_value is not None and
                    getattr(live_owner, generation_attr, None) != generation_value):
                return
            if error is not None:
                if callable(on_error):
                    on_error(error)
            elif callable(on_result):
                on_result(result)

        dispatch_key = ("task", id(owner), key) if owner is not None else None
        if not post_to_ui(_deliver, key=dispatch_key):
            # The application may be shutting down; do not fall back to calling
            # UI callbacks on the worker thread.
            return

    future.add_done_callback(_completed)
    return future
