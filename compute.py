"""compute.py: one call for every Groovebox computation.

    compute.run(direction, work, *args, carrier=None, dims=(), pure=False, **kw)  -> Future
    compute.call(...)                                                             -> result (waits)
    compute.map(direction, work, items, carrier=None, dims=())                    -> list (in order)
    compute.report()                                                              -> text

``work`` is a Python callable, or the name of a hybrid kernel (``"osc"``, ``"fold"``, ``"ca"``, ...).
One call combines what used to be four separate decisions:

1. sCode pooling.  ``direction`` (audio, ui-offload, canonical, video, hybrid, scripts, export, programs,
   background) picks the sCode lane and its priority on the shared CPU- and memory-aware pools
   (``scode_coordinator`` on ``thread_budget``).  Nothing here creates threads of its own.
2. Multi-language optimisation.  A kernel name goes through ``hybrid_runtime``, which keeps the backend
   (NumPy / Rust / LuaJIT / Julia / native) that measured fastest *and* matched the NumPy reference.
3. CPU thread arrangement.  ``map`` splits a batch into as many slices as the lane can run now
   (``thread_budget.lane_workers``), so callers never choose thread counts.
4. Multidimensional carrier assignment.  Work with the same ``(direction, carrier, *dims)`` key forms one
   strand: it runs in submission order, one item at a time, so a carrier's state is never raced.  Different
   keys run in parallel up to the lane width.  dims is any tuple, e.g. (instrument, sequence) or
   (layer, tile).

``pure=True`` (with hashable/JSON-able arguments) reuses a bounded cache of earlier results.  Use it only for
deterministic stages: mutable app state, Qt objects and live audio buffers must never be cached.
Audio device callbacks must never call into this module (they use their preallocated rings).
"""
from __future__ import annotations

import collections
import threading
import time
from concurrent.futures import Future

_STRANDS = {}                       # key -> deque of pending (fn, args, kwargs, future)
_ACTIVE = set()                     # keys whose head item is running
_LOCK = threading.Lock()
_STATS = collections.Counter()
_TIME = collections.defaultdict(float)
_CACHE = None


def _cache():
    global _CACHE
    if _CACHE is None:
        try:
            from scode.optimization import StageCache
            _CACHE = StageCache(max_entries=1024)
        except Exception:
            _CACHE = False
    return _CACHE or None


def _resolve(work):
    if callable(work):
        return work, getattr(work, "__name__", "fn")
    name = str(work)

    def kernel(*a, **k):
        import hybrid_runtime
        return hybrid_runtime.run(name, *a, **k)
    return kernel, "kernel:" + name


def _submit_direction(direction, fn, *args, **kwargs):
    try:
        import scode_coordinator as sc
        return sc.direct(direction, fn, *args, **kwargs)
    except Exception:
        f = Future()

        def go():
            try:
                f.set_result(fn(*args, **kwargs))
            except BaseException as exc:
                f.set_exception(exc)
        threading.Thread(target=go, daemon=True, name="compute-" + str(direction)).start()
        return f


def _timed(label, fn):
    def run(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            _TIME[label] += time.perf_counter() - t0
    return run


def _pump(key):
    """Start the head of a strand (called with _LOCK held)."""
    q = _STRANDS.get(key)
    if not q or key in _ACTIVE:
        return
    fn, args, kwargs, fut, direction = q[0]
    _ACTIVE.add(key)

    def done(inner):
        with _LOCK:
            q.popleft()
            _ACTIVE.discard(key)
            if not q:
                _STRANDS.pop(key, None)
            else:
                _pump(key)
        try:
            fut.set_result(inner.result())
        except BaseException as exc:
            if not fut.done():
                fut.set_exception(exc)
    if fut.set_running_or_notify_cancel():
        _submit_direction(direction, fn, *args, **kwargs).add_done_callback(done)
    else:                                   # cancelled while waiting: skip it
        q.popleft(); _ACTIVE.discard(key)
        if not q:
            _STRANDS.pop(key, None)
        else:
            _pump(key)


def run(direction, work, *args, carrier=None, dims=(), pure=False, **kwargs):
    """Schedule work; returns a Future. See the module docstring."""
    fn, label = _resolve(work)
    label = "%s/%s" % (direction, label)
    _STATS[label] += 1
    if pure:
        c = _cache()
        if c is not None:
            try:
                from scode.optimization import stable_key
                fp = stable_key([args, kwargs])
                hit = c.get(label, fp)
                if hit is not None:
                    _STATS[label + " (cached)"] += 1
                    f = Future(); f.set_result(hit); return f
                inner = fn

                def fn(*a, **k):
                    out = inner(*a, **k)
                    try:
                        c.put(label, fp, out)
                    except Exception:
                        pass
                    return out
            except Exception:
                pass
    fn = _timed(label, fn)
    if carrier is None and not dims:
        return _submit_direction(direction, fn, *args, **kwargs)
    key = (str(direction), carrier) + tuple(dims if isinstance(dims, (tuple, list)) else (dims,))
    fut = Future()
    with _LOCK:
        _STRANDS.setdefault(key, collections.deque()).append((fn, args, kwargs, fut, direction))
        _pump(key)
    return fut


def call(direction, work, *args, timeout=None, **kwargs):
    """run(...) and wait for the result (never call from the Qt thread for long work)."""
    return run(direction, work, *args, **kwargs).result(timeout=timeout)


def width(direction="hybrid"):
    try:
        import thread_budget as tb
        return max(1, int(tb.lane_workers()))
    except Exception:
        import os
        return max(1, (os.cpu_count() or 2) - 1)


def map(direction, work, items, carrier=None, dims=(), chunks=None):
    """Apply work to every item using the lane's current width; results come back in order.

    With a carrier, slices still run in parallel but on per-slice strands (carrier, *dims, slice)."""
    items = list(items)
    if not items:
        return []
    n = max(1, min(len(items), int(chunks or width(direction))))
    size = (len(items) + n - 1) // n
    fn, _label = _resolve(work)

    def part(sl):
        return [fn(x) for x in sl]
    futs = []
    for i in range(0, len(items), size):
        sl = items[i:i + size]
        if carrier is None and not dims:
            futs.append(run(direction, part, sl))
        else:
            futs.append(run(direction, part, sl, carrier=carrier, dims=tuple(dims) + (i // size,)))
    out = []
    for f in futs:
        out.extend(f.result())
    return out


def report():
    lines = ["compute: one front door over sCode lanes · hybrid kernels · thread budget · carrier strands", ""]
    with _LOCK:
        lines.append("open strands: %d · running heads: %d" % (len(_STRANDS), len(_ACTIVE)))
    for k, n in _STATS.most_common(24):
        lines.append("  %-48s %6d calls  %8.3f s" % (k, n, _TIME.get(k, 0.0)))
    c = _cache()
    if c is not None:
        lines.append("pure-result cache: %s" % c.stats())
    try:
        import hybrid_runtime
        lines.append(""); lines.append(hybrid_runtime.report())
    except Exception:
        pass
    try:
        import thread_budget as tb
        lines.append(""); lines.append("lanes:")
        lines += ["  " + str(r) for r in tb.lane_report(12)]
    except Exception:
        pass
    return "\n".join(lines)
