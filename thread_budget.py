"""Shared CPU/memory budget for Groovebox and sOS.

Worker migration is a scheduling policy, not a request to create more threads
than the machine can actually run.  The budget respects process affinity,
cgroup CPU quotas and memory ceilings, and keeps explicit headroom for the
GUI, the audio callback and the operating system.
"""
from __future__ import annotations

import math
import os
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, wait

_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
         "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
_SHARED = None
_SHARED_LOCK = threading.Lock()
_MAX_SHARED_WORKERS = 4


def _read_int(path):
    try:
        with open(path, "r", encoding="ascii") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _cpu_quota_cores():
    """Return the fractional cgroup CPU quota, or 0 if it is unlimited."""
    try:
        fields = open("/sys/fs/cgroup/cpu.max", "r", encoding="ascii").read().split()
        if len(fields) >= 2 and fields[0] != "max":
            quota, period = int(fields[0]), int(fields[1])
            if quota > 0 and period > 0:
                return float(quota) / float(period)
    except Exception:
        pass
    quota = _read_int("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    period = _read_int("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    if quota > 0 and period > 0:
        return float(quota) / float(period)
    return 0.0


def _affinity_count():
    try:
        n = len(os.sched_getaffinity(0))
        return max(1, int(n))
    except Exception:
        pass
    try:
        n = os.process_cpu_count()
        if n:
            return max(1, int(n))
    except Exception:
        pass
    try:
        return max(1, int(os.cpu_count() or 1))
    except Exception:
        return 1


def usable_cores():
    """Integer CPU budget respecting affinity and fractional cgroup quotas."""
    n = _affinity_count()
    quota = _cpu_quota_cores()
    if quota > 0:
        # Ceiling expresses the maximum count of runnable workers under a
        # fractional quota; lane sizing below reserves additional headroom.
        n = min(n, max(1, int(math.ceil(quota - 1e-9))))
    return max(1, int(n))


def physical_cores():
    """Best-effort physical core count, bounded by the effective CPU budget."""
    try:
        import psutil
        n = psutil.cpu_count(logical=False)
        if n:
            return max(1, min(usable_cores(), int(n)))
    except Exception:
        pass
    return max(1, min(usable_cores(), (usable_cores() + 1) // 2))


def _memory_headroom_cap(preferred):
    """Reduce background concurrency when effective available RAM is tight."""
    cap = max(1, int(preferred))
    try:
        from memory_guard import snapshot
        snap = snapshot()
        avail = int(snap.get("available", 0) or 0)
        reserve = int(snap.get("reserve", 0) or 0)
        safe = max(0, avail - reserve)
        if safe < 768 * 1024 * 1024:
            return 1
        if safe < 2 * 1024 * 1024 * 1024:
            return min(cap, 2)
    except Exception:
        pass
    return cap


def compute_threads():
    """Math-library width; user overrides are always clamped to actual capacity."""
    try:
        forced = int(os.environ.get("GROOVEBOX_THREADS", "0") or 0)
    except ValueError:
        forced = 0
    cores = usable_cores()
    if forced > 0:
        return max(1, min(8, cores, forced))
    return max(1, min(6, cores))


_STREAMABLE = True
_MIGRATORY_CAP = 4


def set_streamable(on: bool):
    """Enable scheduling migration within the safe shared worker budget."""
    global _STREAMABLE
    _STREAMABLE = bool(on)


def migratory_threads():
    """Return a safe advisory width; Streamable never overrides hardware caps."""
    if not _STREAMABLE:
        return 1
    return max(1, min(_MIGRATORY_CAP, lane_workers()))


def lane_workers():
    """Global worker-pool width, leaving CPU time for UI/audio/OS service."""
    try:
        forced = int(os.environ.get("GROOVEBOX_WORKERS", "0") or 0)
    except ValueError:
        forced = 0
    cores = usable_cores()
    # One logical CPU is kept for GUI/audio, a second is reserved when possible
    # for the OS/compositor and bursty driver callbacks.
    safe = max(1, min(_MAX_SHARED_WORKERS, cores - (2 if cores >= 3 else 1)))
    safe = _memory_headroom_cap(safe)
    if forced > 0:
        safe = min(safe, forced)
    return max(1, int(safe))


def bulk_workers():
    """Bulk worker allowance after reserving one worker for interactive work.

    The reservation is carved out of the same process-wide ceiling; it is not
    an additional pool allowance. On one-worker systems there is no separate
    reservation and both classes share the sole worker.
    """
    total = lane_workers()
    reserve = interactive_workers()
    return max(1, total - reserve)


def is_managed_worker_thread():
    """True when called from one of Groovebox's shared executor workers.

    Native kernels use this to avoid nested parallelism: the outer scheduler
    already distributes independent jobs across its bounded worker budget.
    """
    try:
        name = threading.current_thread().name
    except Exception:
        return False
    return name.startswith(("groovebox-work", "groovebox-interactive"))


def scheduler_budget():
    """Describe the aggregate executor budget without creating any threads."""
    total = lane_workers()
    interactive = interactive_workers()
    bulk = bulk_workers()
    # The single-core fallback intentionally aliases both classes to one pool.
    effective_total = total if interactive else bulk
    return {"total_workers": effective_total, "bulk_workers": bulk,
            "interactive_workers": interactive, "reserved_interactive": bool(interactive)}


def _shared_executor():
    global _SHARED
    if _SHARED is None:
        with _SHARED_LOCK:
            if _SHARED is None:
                _SHARED = ThreadPoolExecutor(max_workers=bulk_workers(), thread_name_prefix="groovebox-work")
    return _SHARED


# R32.9 TWO WORK CLASSES: every lane used to feed ONE process-wide executor with ONE FIFO queue, so a short
# interactive job (a folder listing, a preview, a media probe) waited behind every long bulk job (canonical
# rebuilds, renders) once the shared threads were busy. Interactive lanes now run on their own small executor.
_INTERACTIVE = None
INTERACTIVE_NAME_HINTS = ("file-manager", "file-browser", "browser", "preview", "thumbnail", "media-load", "probe",
                          "dialog", "ui-", "-ui", "picker", "listing")


def interactive_workers():
    # Reserve exactly one worker when the aggregate budget can support it.
    # This prevents file/dialog/preview work from waiting behind long bulk jobs
    # without increasing total process concurrency.
    return 1 if lane_workers() >= 2 else 0


def _interactive_executor():
    global _INTERACTIVE
    if interactive_workers() <= 0:
        return _shared_executor()
    if _INTERACTIVE is None:
        with _SHARED_LOCK:
            if _INTERACTIVE is None:
                _INTERACTIVE = ThreadPoolExecutor(max_workers=interactive_workers(), thread_name_prefix="groovebox-interactive")
    return _INTERACTIVE


def classify(name, kind=None):
    if kind in ("interactive", "bulk"):
        return kind
    n = str(name).lower()
    return "interactive" if any(h in n for h in INTERACTIVE_NAME_HINTS) else "bulk"


class SharedWorkLane:
    """Ordered, bounded-concurrency lane backed by a process-wide executor of its class (bulk / interactive)."""
    def __init__(self, name="work", max_workers=1, max_pending=256, kind=None):
        self.name = str(name)
        self.kind = classify(name, kind)
        self._executor = _interactive_executor if self.kind == "interactive" else _shared_executor
        cap = (interactive_workers() or 1) if self.kind == "interactive" else bulk_workers()
        self.max_workers = max(1, min(cap, int(max_workers)))
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
                worker = self._executor().submit(self._execute, public, fn, args, kwargs)
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
        with self._lock:
            cap = (interactive_workers() or 1) if self.kind == "interactive" else bulk_workers()
            self.max_workers = max(1, min(cap, int(count)))
            self._pump_locked()
            return self.max_workers

    def cancel_pending(self):
        """Cancel queued (not running) work without closing this logical lane."""
        cancelled = 0
        with self._lock:
            while self._queue:
                fut, *_ = self._queue.popleft()
                if fut.cancel():
                    cancelled += 1
        return cancelled

    def stats(self):
        with self._lock:
            return {"name": self.name, "kind": self.kind, "active": self._active, "queued": len(self._queue),
                    "max_workers": self.max_workers, "max_pending": self.max_pending,
                    "closed": self._closed}


def wait_futures(futures, timeout=None):
    return wait(futures, timeout=timeout)


def make_lane(name, max_workers=1, max_pending=256, kind=None):
    return SharedWorkLane(name, max_workers=max_workers, max_pending=max_pending, kind=kind)


def apply():
    """Set math-library thread counts before NumPy is imported."""
    n = str(compute_threads())
    for name in _VARS:
        os.environ.setdefault(name, n)
    os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
    return int(n)


def shutdown_shared_executor(wait=False, cancel_futures=True):
    """Final process shutdown hook; call only after all lanes have been closed."""
    global _SHARED, _INTERACTIVE
    with _SHARED_LOCK:
        ex, _SHARED = _SHARED, None
        ix, _INTERACTIVE = _INTERACTIVE, None
    seen = set()
    for e in (ex, ix):
        if e is not None and id(e) not in seen:
            seen.add(id(e))
            e.shutdown(wait=bool(wait), cancel_futures=bool(cancel_futures))
