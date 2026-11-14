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
import time
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


_MEM_CAP_CACHE = {"t": -1e9, "safe": None}
_MEM_CAP_TTL_S = 2.0


def _safe_memory_bytes():
    """Available RAM above the memory_guard reserve, cached for 2 s (lanes are built in bursts; probing
    /proc/meminfo per lane cost ~1 ms each and added nothing)."""
    now = time.monotonic()
    if now - _MEM_CAP_CACHE["t"] < _MEM_CAP_TTL_S:
        return _MEM_CAP_CACHE["safe"]
    safe = None
    try:
        from memory_guard import snapshot
        snap = snapshot()
        safe = max(0, int(snap.get("available", 0) or 0) - int(snap.get("reserve", 0) or 0))
    except Exception:
        safe = None
    _MEM_CAP_CACHE.update(t=now, safe=safe)
    return safe


HEAVY_WORKER_BYTES = 1536 * 1024 * 1024      # one heavy (render/export) worker per 1.5 GiB of safe RAM


def memory_worker_cap(preferred, *, heavy=False):
    """WORKER_RULE_R7: THE one memory rule for every pool width in the app (lanes, math threads,
    render/export pools via memory_guard.adaptive_workers).  It used to exist three times with
    different thresholds, so two pools could each think the same free RAM was theirs.
      heavy work  : one worker per HEAVY_WORKER_BYTES of safe RAM (render/export buffers)
      light work  : 1 worker under 768 MiB safe, 2 under 2 GiB, otherwise uncapped"""
    cap = max(1, int(preferred))
    safe = _safe_memory_bytes()
    if safe is None:
        return cap
    if heavy:
        return max(1, min(cap, int(safe // HEAVY_WORKER_BYTES)))
    if safe < 768 * 1024 * 1024:
        return 1
    if safe < 2 * 1024 * 1024 * 1024:
        return min(cap, 2)
    return cap


def _memory_headroom_cap(preferred):
    """Reduce background concurrency when effective available RAM is tight."""
    return memory_worker_cap(preferred, heavy=False)


def _memory_headroom_cap_uncached(preferred):
    """The original probe (kept for diagnostics)."""
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
        return max(1, min(cores, forced))
    # 4c/8t Latitude: use the logical threads (8), not the physical count (4).
    # Tablets and small laptops keep one core for the UI and audio callback.
    try:
        import compat_settings as cs
        kind = cs.hardware_class()
    except Exception:
        kind = "laptop"
    cap = 4 if kind == "tablet" else 8
    spare = 1 if kind in ("tablet", "laptop") and cores > 2 else 0
    return max(1, min(cap, cores - spare))


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
                _SHARED = ThreadPoolExecutor(max_workers=bulk_threads(), thread_name_prefix="groovebox-work")
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


_RUNNING = {"bulk": 0, "interactive": 0}      # jobs currently executing per executor class
import weakref as _weakref
_LANES = _weakref.WeakSet()                    # LANE_REGISTRY_R6: every live lane, for lane_report()


def lane_report(limit=8):
    """Busiest live lanes first: [{name, kind, active, queued, submitted, inline, wait_s, run_s, ...}]."""
    rows = []
    for lane in list(_LANES):
        try:
            rows.append(lane.stats())
        except Exception:
            pass
    rows.sort(key=lambda r: (r.get("active", 0) + r.get("queued", 0), r.get("run_s", 0.0)), reverse=True)
    out = {"running": dict(_RUNNING), "budget": scheduler_budget(), "lanes": rows[: max(1, int(limit))],
           "lane_count": len(rows)}
    try:
        out["forecast"] = forecast()
    except Exception:
        pass
    return out
_RUNNING_LOCK = threading.Lock()

# POOL_FORECAST_R7: one predictive model for the whole pool. Dimensions: executor class (bulk / interactive)
# x lane family (lane name with window / instance ids removed) x task signature (callable qualname). Every
# finished job updates an exponentially-weighted mean and variance of its run time (alpha = 0.2, i.e. ~the
# last 10 runs). From those, forecast() predicts for each class the backlog seconds still to run (queued
# jobs at their predicted cost + running jobs' predicted remainder) and the drain time over that class's
# workers, and each lane's expected wait for a newly submitted job. Producers of optional / idle work ask
# should_defer() before submitting, so speculative jobs never pile in front of real work. The model only
# observes and advises: lane order, priorities and concurrency limits are unchanged.
import re as _re
_FAMILY_RE = _re.compile(r"(?:[-_ ]?w\d{2,}|[-_ ]?\d+|[-_ ]?0x[0-9a-f]+)", _re.I)
_COST = {}                 # (kind, family, sig) -> [mean_s, var_s2, n]
_COST_LOCK = threading.Lock()
_COST_ALPHA = 0.2
_COST_MAX = 2048
_DEFAULT_COST_S = 0.05


def lane_family(name):
    return _FAMILY_RE.sub("", str(name)).strip("-_ ") or str(name)


def _task_sig(fn):
    try:
        f = getattr(fn, "func", fn)              # functools.partial
        return f"{getattr(f, '__module__', '')}.{getattr(f, '__qualname__', type(f).__name__)}"
    except Exception:
        return "?"


def _cost_key(lane, fn):
    return (lane.kind, lane_family(lane.name), _task_sig(fn))


def observe_cost(key, seconds, cpu_seconds=None):
    """Wall seconds (+ optional CPU seconds of the running thread: the 'how much of this job is waiting on
    I/O / locks / GIL-free native code' dimension used by the pool sizer)."""
    if key is None or seconds is None or seconds < 0:
        return
    cpu = float(seconds) if cpu_seconds is None else max(0.0, min(float(seconds), float(cpu_seconds)))
    with _COST_LOCK:
        row = _COST.get(key)
        if row is None:
            if len(_COST) >= _COST_MAX:
                _COST.pop(next(iter(_COST)))
            _COST[key] = [float(seconds), 0.0, 1, cpu]
            return
        m, v, n = row[0], row[1], row[2]
        d = float(seconds) - m
        m += _COST_ALPHA * d
        v = (1.0 - _COST_ALPHA) * (v + _COST_ALPHA * d * d)
        row[0], row[1], row[2] = m, v, n + 1
        row[3] += _COST_ALPHA * (cpu - row[3])


def _cpu_share(key):
    with _COST_LOCK:
        row = _COST.get(key)
        if row is None or row[0] <= 1e-6:
            return 1.0
        return max(0.0, min(1.0, row[3] / row[0]))


def predicted_cost(key, *, pessimism=1.0):
    """Expected run seconds (+ pessimism x std-dev). Unknown signatures fall back to their lane family."""
    with _COST_LOCK:
        row = _COST.get(key)
        if row is None and key is not None:
            fam = [r for k, r in _COST.items() if k[0] == key[0] and k[1] == key[1]]
            if fam:
                row = [sum(r[0] for r in fam) / len(fam), sum(r[1] for r in fam) / len(fam), 0]
    if row is None:
        return _DEFAULT_COST_S
    return max(0.0, row[0] + pessimism * (row[1] ** 0.5))


def forecast():
    """{'classes': {kind: {workers, running, queued, backlog_s, drain_s}}, 'lanes': [{name, family, wait_s}]}"""
    now = time.monotonic()
    budget = scheduler_budget()
    workers = {"bulk": max(1, bulk_threads()), "interactive": max(1, budget["interactive_workers"] or 1)}
    classes = {k: {"workers": workers[k], "running": 0, "queued": 0, "backlog_s": 0.0} for k in workers}
    lanes = []
    for lane in list(_LANES):
        try:
            with lane._lock:
                queued = [(getattr(it[0], "_groovebox_cost_key", None)) for it in lane._queue]
                running = [(getattr(f, "_groovebox_cost_key", None), getattr(f, "_groovebox_started_at", None))
                           for f in lane._active_futures]
                slots = lane.max_workers
                kind = lane.kind if (lane.kind == "bulk" or budget["interactive_workers"]) else "bulk"
        except Exception:
            continue
        q_s = sum(predicted_cost(k) for k in queued)
        r_s = sum(max(0.0, predicted_cost(k) - (now - t0 if t0 else 0.0)) for k, t0 in running)
        c = classes[kind]
        c["running"] += len(running); c["queued"] += len(queued); c["backlog_s"] += q_s + r_s
        if queued or running:
            lanes.append({"name": lane.name, "family": lane_family(lane.name), "kind": kind,
                          "wait_s": round((q_s + r_s) / max(1, slots), 4)})
    for c in classes.values():
        c["drain_s"] = round(c["backlog_s"] / c["workers"], 4)
        c["backlog_s"] = round(c["backlog_s"], 4)
    lanes.sort(key=lambda r: r["wait_s"], reverse=True)
    return {"classes": classes, "lanes": lanes, "signatures": len(_COST)}


# POOL_SIZER_R7: predictive, multidimensional pool width. Two controls, both driven by the forecast model:
#  1. Class width (bulk executor threads). Threads that are mostly waiting (I/O, subprocess pipes, sleeps,
#     GIL-releasing native/Rust/NumPy code) do not consume a core. From the backlog-weighted CPU share s of
#     the work that is queued or running, the bulk executor may grow to  base / s  threads (Amdahl-style
#     occupancy), at most 2 x base and never past the shared memory rule. Pure CPU work (s = 1) keeps base.
#     Growth only: idle extra threads cost nothing and leave on process exit.
#  2. Lane width. A lane created with max_workers >= 2 (unordered by contract) is resized between 1 and
#     the class width by Little's law: workers = ceil(arrival rate x expected cost), +1 while its predicted
#     wait exceeds LANE_TARGET_WAIT_S; it shrinks back once its offered load falls. Ordered (1-worker)
#     lanes are never widened. Retuning runs at most every RETUNE_INTERVAL_S, inline in a finishing job's
#     bookkeeping (no extra thread). GROOVEBOX_POOL_ADAPT=0 disables both controls.
RETUNE_INTERVAL_S = 0.5
LANE_TARGET_WAIT_S = 0.10
_RETUNE_LOCK = threading.Lock()
_LAST_RETUNE = [0.0]
_BULK_WIDTH = [0]


def _adapt_enabled():
    return os.environ.get("GROOVEBOX_POOL_ADAPT", "1") != "0"


def bulk_threads():
    """Current bulk executor width (>= bulk_workers())."""
    return max(bulk_workers(), _BULK_WIDTH[0])


def _class_width_target(fc=None):
    base = bulk_workers()
    if not _adapt_enabled():
        return base
    num = den = 0.0
    for lane in list(_LANES):
        if lane.kind != "bulk":
            continue
        try:
            with lane._lock:
                keys = [getattr(it[0], "_groovebox_cost_key", None) for it in lane._queue]
                keys += [getattr(f, "_groovebox_cost_key", None) for f in lane._active_futures]
        except Exception:
            continue
        for k in keys:
            c = predicted_cost(k)
            num += c * _cpu_share(k); den += c
    if den <= 0.0:
        return base
    share = max(0.5, num / den)                     # never more than 2 x base
    return max(base, memory_worker_cap(int(base / share + 1e-9), heavy=False))


def _lane_width_target(lane, now):
    req = int(getattr(lane, "_requested_workers", 1) or 1)
    if req < 2:
        return lane.max_workers
    cap = max(1, min(bulk_threads() if lane.kind == "bulk" else (interactive_workers() or 1), memory_worker_cap(req * 2)))
    ia = getattr(lane, "_ia_mean", None)
    last = getattr(lane, "_last_submit", None)
    if not ia or last is None:
        return min(cap, max(1, min(req, lane.max_workers)))
    rate = 1.0 / max(ia, now - last, 1e-3)
    with lane._lock:
        keys = [getattr(it[0], "_groovebox_cost_key", None) for it in lane._queue]
        active = [getattr(f, "_groovebox_cost_key", None) for f in lane._active_futures]
    mean = predicted_cost(keys[0] if keys else (active[0] if active else None), pessimism=0.0)
    try:                      # MATH_INVARIANTS_R7: Little's law L = λ·W, one shared definition
        from math_invariants import littles_width as _lw
        want = _lw(rate, mean, 1 << 30)
    except Exception:
        import math as _m
        want = max(1, _m.ceil(rate * mean - 1e-9))
    wait = (sum(predicted_cost(k) for k in keys) + sum(predicted_cost(k) for k in active)) / max(1, lane.max_workers)
    if keys and wait > LANE_TARGET_WAIT_S:
        want = max(want, lane.max_workers + 1)
    out = max(1, min(cap, want))
    try:
        from math_invariants import guard as _g
        _g("littles_law", 1 <= out <= max(1, cap), "lane %s width %s cap %s" % (getattr(lane, "name", "?"), out, cap))
    except Exception:
        pass
    return out


def retune(force=False):
    """Apply both sizing controls now (rate-limited unless ``force``). Returns {'bulk_threads', 'resized'}."""
    if not _adapt_enabled():
        return {"bulk_threads": bulk_workers(), "resized": 0}
    now = time.monotonic()
    if not force and now - _LAST_RETUNE[0] < RETUNE_INTERVAL_S:
        return None
    if not _RETUNE_LOCK.acquire(False):
        return None
    try:
        _LAST_RETUNE[0] = now
        width = _class_width_target()
        if width > _BULK_WIDTH[0]:
            _BULK_WIDTH[0] = width
            ex = _SHARED
            if ex is not None:
                try:
                    if width > ex._max_workers:
                        ex._max_workers = width          # ThreadPoolExecutor spawns lazily up to this
                except Exception:
                    pass
        resized = 0
        for lane in list(_LANES):
            try:
                if lane._closed or int(getattr(lane, "_requested_workers", 1) or 1) < 2:
                    continue
                tgt = _lane_width_target(lane, now)
                if tgt != lane.max_workers:
                    lane._set_width(tgt); resized += 1
            except Exception:
                continue
        return {"bulk_threads": bulk_threads(), "resized": resized}
    finally:
        _RETUNE_LOCK.release()


def predicted_drain_s(kind="bulk"):
    try:
        return float(forecast()["classes"].get(kind, {}).get("drain_s", 0.0))
    except Exception:
        return 0.0


def resolve_horizon(key, q=0.9):
    """VIRTUAL_HORIZON_R7: a probabilistic resolve time. From the measured mean μ and variance σ² of this job
    signature, Cantelli's one-sided inequality  P(T ≥ μ + kσ) ≤ 1/(1 + k²)  with k = √(q/(1−q)) gives a horizon
    h = μ + kσ that the job finishes within with probability ≥ q, for ANY run-time distribution."""
    q = min(0.999, max(0.0, float(q)))
    with _COST_LOCK:
        row = _COST.get(key)
    if row is None:
        return predicted_cost(key)
    k = (q / (1.0 - q)) ** 0.5
    return max(0.0, row[0] + k * max(0.0, row[1]) ** 0.5)


def virtual_blocks(key, block_s, q=0.9):
    """How many control blocks a synth is better off modulating a virtual (closed-form / cached) state for
    while that job resolves: ceil(horizon / block). 0 when the job is predicted to land inside one block."""
    b = max(1e-6, float(block_s))
    h = resolve_horizon(key, q)
    n = int(math.ceil(h / b - 1e-9)) if h > b else 0
    return n


def should_defer(kind="bulk", budget_s=0.25):
    """True when that executor class is predicted to stay busy longer than ``budget_s``: optional / idle /
    speculative work should wait for the next opportunity instead of queueing behind real work."""
    return predicted_drain_s(kind) > float(budget_s)



_TLS = threading.local()   # POOL_HELP_R7: lanes whose job this thread is running


def _run_claimed(lane, public, fn, args, kwargs):
    """Run a claimed lane job in the current thread; True on success."""
    if not public.set_running_or_notify_cancel():
        return False
    lanes = _TLS.__dict__.setdefault("lanes", [])
    lanes.append(lane)
    public._groovebox_started_at = time.monotonic()
    try:
        public.set_result(fn(*args, **kwargs))
        return True
    except BaseException as exc:
        public.set_exception(exc)
        return False
    finally:
        public._groovebox_finished_at = time.monotonic()
        lanes.pop()


class _LaneFuture(Future):
    """POOL_HELP_R7: a lane future whose waiter helps. When a managed worker waits on a job that is
    still queued at the HEAD of its lane and the lane has a free slot, the waiter runs it itself
    (exactly what a lane worker would do next): no worker sits blocked, nested waits cannot deadlock,
    and lane order and concurrency limits are unchanged."""
    _lane = None

    def _help(self):
        lane = self._lane
        if lane is not None and not self.done() and is_managed_worker_thread():
            try:
                lane._steal(self)
            except Exception:
                pass

    def result(self, timeout=None):
        self._help()
        return super().result(timeout)

    def exception(self, timeout=None):
        self._help()
        return super().exception(timeout)


class SharedWorkLane:
    """Ordered, bounded-concurrency lane backed by a process-wide executor of its class (bulk / interactive)."""
    def __init__(self, name="work", max_workers=1, max_pending=256, kind=None):
        self.name = str(name)
        self.kind = classify(name, kind)
        self._executor = _interactive_executor if self.kind == "interactive" else _shared_executor
        cap = (interactive_workers() or 1) if self.kind == "interactive" else bulk_workers()
        self._requested_workers = max(1, int(max_workers))   # POOL_SIZER_R7: >= 2 means unordered, resizable
        self.max_workers = max(1, min(cap, int(max_workers)))
        self.max_pending = max(1, int(max_pending))
        self._ia_mean = None
        self._last_submit = None
        self._lock = threading.RLock()
        self._queue = deque()
        self._active = 0
        self._closed = False
        self._draining = False
        self._active_futures = set()
        self._stats = {"submitted": 0, "completed": 0, "failed": 0, "cancelled": 0, "inline": 0,
                       "wait_s": 0.0, "run_s": 0.0}
        _LANES.add(self)

    def _caller_would_deadlock(self):
        """True when the caller is a worker of the same executor class and every worker of that class is busy:
        a job queued now could only start after one of them returns — if the caller waits on it, nothing ever
        returns (nested-submit deadlock)."""
        if not is_managed_worker_thread():
            return False
        name = threading.current_thread().name
        mine = "interactive" if name.startswith("groovebox-interactive") else "bulk"
        target = self.kind if (self.kind == "bulk" or interactive_workers() > 0) else "bulk"
        if mine != target:
            return False
        cap = interactive_workers() if target == "interactive" else bulk_threads()
        return _RUNNING.get(target, 0) >= max(1, cap)

    def submit(self, fn, /, *args, **kwargs):
        return self.submit_prioritized(0.0, fn, *args, **kwargs)

    def submit_prioritized(self, priority, fn, /, *args, **kwargs):
        if not callable(fn):
            raise TypeError("submit requires a callable")
        public = _LaneFuture()
        public._lane = self
        public._claim = threading.Lock()   # POOL_HELP_R7: exactly one runner (worker or helping waiter)
        public._groovebox_priority = float(priority)
        public._groovebox_cost_key = _cost_key(self, fn)     # POOL_FORECAST_R7
        with self._lock:
            if self._closed:
                raise RuntimeError(f"work lane {self.name} is shut down")
            if len(self._queue) >= self.max_pending:
                raise RuntimeError(f"work lane {self.name} is saturated; producer must apply backpressure")
            self._stats["submitted"] += 1
            _now = time.monotonic()                          # POOL_SIZER_R7: inter-arrival EWMA
            if self._last_submit is not None:
                _dt = max(1e-4, _now - self._last_submit)
                self._ia_mean = _dt if self._ia_mean is None else self._ia_mean + 0.2 * (_dt - self._ia_mean)
            self._last_submit = _now
            # THREAD_CALLER_RUNS_R6: run in the caller instead of queueing behind ourselves.
            if not self._queue and self._active < self.max_workers and self._caller_would_deadlock():
                self._active += 1
                self._stats["inline"] += 1
                inline = True
            else:
                inline = False
        if inline:
            t0 = time.monotonic()
            try:
                if public.set_running_or_notify_cancel():
                    try:
                        public.set_result(fn(*args, **kwargs))
                        _ok = True
                    except BaseException as exc:
                        public.set_exception(exc)
                        _ok = False
                    with self._lock:        # POOL_HELP_R7: stats under the lock (was a race)
                        self._stats["completed" if _ok else "failed"] += 1
            finally:
                _dt = time.monotonic() - t0
                observe_cost(public._groovebox_cost_key, _dt)
                with self._lock:
                    self._stats["run_s"] += _dt
                    self._active = max(0, self._active - 1)
                    self._pump_locked()
            return public
        with self._lock:
            if self._closed:
                raise RuntimeError(f"work lane {self.name} is shut down")
            public._groovebox_queued_at = time.monotonic()
            item = (public, fn, args, kwargs)
            for index, pending in enumerate(self._queue):
                if getattr(pending[0], "_groovebox_priority", 0.0) < public._groovebox_priority:
                    self._queue.insert(index, item)
                    break
            else:
                self._queue.append(item)
            self._pump_locked()
        return public

    def _steal(self, public):
        """POOL_HELP_R7: run ``public`` in the calling (waiting) worker when that keeps lane semantics:
        (a) it was already granted a slot (sitting in the executor FIFO); (b) the caller holds a slot of this
        lane (its slot is blocked anyway); (c) it is the head job and a slot is free."""
        claim = getattr(public, "_claim", None)
        if claim is None:
            return False
        if getattr(public, "_granted", False):
            if not claim.acquire(False):
                return False
            _run_claimed(self, public, *public._call)      # _complete accounts when the executor no-op ends
            return True
        with self._lock:
            # (b) the caller holds a slot of THIS lane: the job can only ever run after the caller returns,
            # so running it now (from anywhere in the queue) is the one schedule that completes.
            # (c) otherwise only the head job, and only into a free slot (plain FIFO, no reordering).
            mine = self in getattr(_TLS, "lanes", ())
            if (self._closed and not self._draining) or not self._queue:
                return False
            idx = next((k for k, it in enumerate(self._queue) if it[0] is public), -1)
            if idx < 0 or not (mine or (idx == 0 and self._active < self.max_workers)) or not claim.acquire(False):
                return False
            _pub, fn, args, kwargs = self._queue[idx]
            del self._queue[idx]
            self._active += 1
            self._active_futures.add(public)
            self._stats["inline"] += 1
        t0 = time.monotonic()
        try:
            ok = _run_claimed(self, public, fn, args, kwargs)
            with self._lock:
                self._stats["completed" if ok else ("cancelled" if public.cancelled() else "failed")] += 1
        finally:
            with self._lock:
                q = getattr(public, "_groovebox_queued_at", None)
                if q is not None:
                    self._stats["wait_s"] += max(0.0, t0 - q)
                _dt = time.monotonic() - t0
                self._stats["run_s"] += _dt
                self._active = max(0, self._active - 1)
                self._active_futures.discard(public)
                self._pump_locked()
            observe_cost(getattr(public, "_groovebox_cost_key", None), _dt)
        return True

    def _pump_locked(self):
        while (not self._closed or self._draining) and self._active < self.max_workers and self._queue:
            public, fn, args, kwargs = self._queue.popleft()
            if public.cancelled():
                continue
            self._active += 1
            self._active_futures.add(public)
            public._call = (fn, args, kwargs)
            public._granted = True             # POOL_HELP_R7: holds a slot; a waiting worker may run it
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
        claim = getattr(public, "_claim", None)
        if claim is not None and not claim.acquire(False):
            return None                        # POOL_HELP_R7: a waiting worker already ran it
        if not public.set_running_or_notify_cancel():
            return None
        lanes = _TLS.__dict__.setdefault("lanes", [])
        lanes.append(getattr(public, "_lane", None))
        name = threading.current_thread().name
        cls = "interactive" if name.startswith("groovebox-interactive") else "bulk"
        with _RUNNING_LOCK:
            _RUNNING[cls] = _RUNNING.get(cls, 0) + 1
        public._groovebox_started_at = time.monotonic()
        _c0 = time.thread_time()
        try:
            return fn(*args, **kwargs)
        finally:
            public._groovebox_cpu_s = time.thread_time() - _c0
            try:
                lanes.pop()
            except Exception:
                pass
            public._groovebox_finished_at = time.monotonic()
            with _RUNNING_LOCK:
                _RUNNING[cls] = max(0, _RUNNING.get(cls, 1) - 1)

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
                st = self._stats
                q, b, e = (getattr(public, "_groovebox_queued_at", None), getattr(public, "_groovebox_started_at", None),
                           getattr(public, "_groovebox_finished_at", None))
                if q is not None and b is not None:
                    st["wait_s"] += max(0.0, b - q)
                if b is not None and e is not None:
                    st["run_s"] += max(0.0, e - b)
                    if not public.cancelled():
                        observe_cost(getattr(public, "_groovebox_cost_key", None), max(0.0, e - b),
                                     getattr(public, "_groovebox_cpu_s", None))
                if public.cancelled():
                    st["cancelled"] += 1
                elif public.done() and public.exception() is not None:
                    st["failed"] += 1
                else:
                    st["completed"] += 1
                self._active = max(0, self._active - 1)
                self._active_futures.discard(public)
                self._pump_locked()
            try:
                retune()                                    # POOL_SIZER_R7 (rate-limited, outside the lane lock)
            except Exception:
                pass

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
        """Explicit width from the owner; also becomes the lane's request for the predictive sizer."""
        self._requested_workers = max(1, int(count))
        return self._set_width(count)

    def _set_width(self, count):
        with self._lock:
            cap = (interactive_workers() or 1) if self.kind == "interactive" else bulk_threads()
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
                    "closed": self._closed, **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in self._stats.items()}}


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


def gentle_collect():
    try:
        import gc
        gc.collect(0)
    except Exception:
        pass
