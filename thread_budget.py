"""Shared CPU / worker budget for Groovebox.

The app uses one process-wide Python executor instead of creating a separate
16–32 thread executor for every subsystem.  On an 8-core Dell Latitude the
shared executor may keep up to 32 tasks in flight, while each subsystem lane
limits its own active work.  This is a concurrency ceiling, not a claim that
32 CPU-bound tasks execute faster than 8 cores.
"""
from __future__ import annotations

import os
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, wait

_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
         "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
_SHARED = None
_SHARED_LOCK = threading.Lock()


def usable_cores():
    """Available CPUs, bounded by affinity.

    THREAD_FLOOR_20261106: a tight cgroup quota (common in containers and some
    laptop power profiles) no longer crushes the count below the machine's
    real cores. We still respect affinity, but we keep at least half the
    physical cores so hardware threads stay usable for audio/video work.
    """
    limits = [max(1, int(os.cpu_count() or 1))]
    try:
        limits.append(max(1, len(os.sched_getaffinity(0))))
    except Exception:
        pass
    n = max(1, min(limits))
    # Floor: don't drop below half the reported cores (min 2 when the machine has them).
    floor = max(1, (max(limits) + 1) // 2)
    return max(n, floor) if n < floor else n


def physical_cores():
    """Best-effort physical core count; fall back conservatively to half logical."""
    try:
        import psutil
        n = psutil.cpu_count(logical=False)
        if n:
            return max(1, min(usable_cores(), int(n)))
    except Exception:
        pass
    return max(1, min(usable_cores(), (usable_cores() + 1) // 2))


def compute_threads():
    """Width for math libraries: one spare worker, capped at 16.

    The process-wide task pool has its own bounded width.  Math libraries get
    a modest oversubscription allowance because several operations release the
    GIL and otherwise spend time waiting on I/O or native kernels.
    """
    try:
        forced = int(os.environ.get("GROOVEBOX_THREADS", "0") or 0)
    except ValueError:
        forced = 0
    if forced > 0:
        return max(1, min(16, forced))
    cores = usable_cores()
    return max(1, min(16, cores + (1 if cores > 1 else 0)))


def lane_workers():
    """Maximum process-wide task concurrency (up to 32 bounded slots).

    On an 8-logical-core Latitude this supplies 32 in-flight task slots for
    I/O, video, audio preparation, games and sCode. Individual compute lanes
    remain narrower, while the real-time audio callback never waits on this pool.
    """
    try:
        forced = int(os.environ.get("GROOVEBOX_WORKERS", "0") or 0)
    except ValueError:
        forced = 0
    if forced > 0:
        return max(8, min(32, forced))
    return max(8, min(32, 4 * usable_cores()))


def _shared_executor():
    global _SHARED
    if _SHARED is None:
        with _SHARED_LOCK:
            if _SHARED is None:
                _SHARED = ThreadPoolExecutor(max_workers=lane_workers(), thread_name_prefix="groovebox-work")
    return _SHARED


class SharedWorkLane:
    """Ordered, bounded-concurrency lane scheduled on the shared executor.

    It preserves single-worker semantics for project saves/canonical commits
    without allocating another OS thread.  Queued submissions are bounded so
    an overloaded preview/game producer cannot consume unbounded RAM.
    """
    def __init__(self, name="work", max_workers=1, max_pending=256):
        self.name = str(name)
        self.max_workers = max(1, min(lane_workers(), int(max_workers)))
        self.max_pending = max(1, int(max_pending))
        self._lock = threading.RLock()
        self._queue = deque()
        self._active = 0
        self._closed = False
        self._draining = False
        self._active_futures = set()

    def submit(self, fn, /, *args, **kwargs):
        return self.submit_prioritized(0.0, fn, *args, **kwargs)

    def submit_prioritized(self, priority, fn, /, *args, **kwargs):
        """Stable priority for queued work only; never interrupt an active job."""
        if not callable(fn):
            raise TypeError("submit requires a callable")
        public = Future()
        public._groovebox_priority = float(priority)
        with self._lock:
            if self._closed:
                raise RuntimeError(f"work lane {self.name} is shut down")
            if len(self._queue) >= self.max_pending:
                raise RuntimeError(f"work lane {self.name} is saturated; producer must apply backpressure")
            item = (public, fn, args, kwargs)
            for index, pending in enumerate(self._queue):
                if getattr(pending[0], "_groovebox_priority", 0.0) < public._groovebox_priority:
                    self._queue.insert(index, item)
                    break
            else:
                self._queue.append(item)
            self._pump_locked()
        return public

    def _pump_locked(self):
        while (not self._closed or self._draining) and self._active < self.max_workers and self._queue:
            public, fn, args, kwargs = self._queue.popleft()
            if public.cancelled():
                continue
            self._active += 1
            self._active_futures.add(public)
            try:
                worker = _shared_executor().submit(self._execute, public, fn, args, kwargs)
            except BaseException as exc:
                self._active -= 1
                self._active_futures.discard(public)
                if not public.done():
                    public.set_exception(exc)
                continue
            worker.add_done_callback(lambda wf, pf=public: self._complete(pf, wf))

    @staticmethod
    def _execute(public, fn, args, kwargs):
        if not public.set_running_or_notify_cancel():
            return None
        return fn(*args, **kwargs)

    def _complete(self, public, worker):
        try:
            if worker.cancelled():
                public.cancel()
            else:
                exc = worker.exception()
                if exc is not None:
                    if not public.done():
                        public.set_exception(exc)
                elif not public.done():
                    public.set_result(worker.result())
        except BaseException as exc:
            if not public.done():
                try:
                    public.set_exception(exc)
                except Exception:
                    pass
        finally:
            with self._lock:
                self._active = max(0, self._active - 1)
                self._active_futures.discard(public)
                self._pump_locked()

    def shutdown(self, wait=False, cancel_futures=False):
        with self._lock:
            self._closed = True
            if cancel_futures:
                while self._queue:
                    fut, *_ = self._queue.popleft()
                    fut.cancel()
            else:
                self._draining = True
                self._pump_locked()
            pending = list(self._active_futures)
            pending.extend(fut for fut, *_ in self._queue)
        if wait and pending:
            wait_futures(pending)

    def set_max_workers(self, count):
        """Change this lane's active concurrency without resizing the shared pool."""
        with self._lock:
            self.max_workers = max(1, min(lane_workers(), int(count)))
            self._pump_locked()
            return self.max_workers

    def stats(self):
        with self._lock:
            return {"name": self.name, "active": self._active, "queued": len(self._queue),
                    "max_workers": self.max_workers, "max_pending": self.max_pending,
                    "closed": self._closed}


def wait_futures(futures, timeout=None):
    return wait(futures, timeout=timeout)


def make_lane(name, max_workers=1, max_pending=256):
    return SharedWorkLane(name, max_workers=max_workers, max_pending=max_pending)


def apply():
    """Set math-library thread counts before NumPy is imported."""
    n = str(compute_threads())
    for name in _VARS:
        os.environ.setdefault(name, n)
    os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
    return int(n)


def shutdown_shared_executor(wait=False, cancel_futures=True):
    """Final process shutdown hook; call only after all lanes have been closed."""
    global _SHARED
    with _SHARED_LOCK:
        ex, _SHARED = _SHARED, None
    if ex is not None:
        ex.shutdown(wait=bool(wait), cancel_futures=bool(cancel_futures))
