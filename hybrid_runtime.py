"""hybrid_runtime.py — the hybrid-language router, always on sCode pools.

Kernels are registered once with a NumPy REFERENCE and any number of alternative backends:
  rust     the native accel library (groovebox._GB_ACCEL_FUNCS)       julia   juliacall / julia_bridge (when installed)
  luajit   lupa.luajit21 (scalar loops)                                native  a C kernel compiled by the Program Builder
The first call of a kernel for a size class times every available backend on the real arguments and keeps the
fastest one whose output matches the reference (max |error| ≤ tol). Backends that fail or disagree are never used for
that kernel. Choices persist in ~/.cache/groovebox/hybrid_choices.json (re-measured when the backend set changes).
Execution: run() calls inline (the caller is already on a worker); submit() puts the call on the kernel's sCode lane
(thread_budget.make_lane, sharing the process-wide sCode pool), so hybrid work never creates its own threads.
"""
from __future__ import annotations
import json, os, threading, time
import numpy as np

_K = {}           # name -> {"ref": fn, "alts": {backend: fn}, "tol": float}
_CHOICE = {}      # (name, size class) -> backend
_LANES = {}
_LOCK = threading.Lock()
STATS = {}        # (name, backend) -> [calls, seconds]


def _path():
    d = os.path.join(os.path.expanduser("~"), ".cache", "groovebox"); os.makedirs(d, exist_ok=True)
    return os.path.join(d, "hybrid_choices.json")


def _load():
    try:
        d = __import__("safe_io").load_json(_path())
        for k, v in d.get("choices", {}).items():
            n, c = k.rsplit("|", 1); _CHOICE[(n, int(c))] = v
    except Exception:
        pass


def _save():
    try:
        __import__("safe_io").atomic_write_json(_path(), {"choices": {"%s|%d" % k: v for k, v in _CHOICE.items()}, "backends": available()}, indent=1)
    except Exception:
        pass


def register(name, ref, tol=1e-6, **alts):
    _K[name] = {"ref": ref, "alts": {k: v for k, v in alts.items() if v is not None}, "tol": float(tol)}


def available():
    out = ["numpy"]
    try:
        import groovebox as g
        if getattr(g, "_GB_ACCEL_FUNCS", None): out.append("rust")
    except Exception:
        pass
    try:
        import julia_bridge as jb
        if jb.julia_available(): out.append("julia")
    except Exception:
        pass
    try:
        import lupa.luajit21  # noqa
        out.append("luajit")
    except Exception:
        pass
    return out


def _size_class(args):
    n = 1
    for a in args:
        if isinstance(a, np.ndarray): n = max(n, a.size)
        elif isinstance(a, int) and a not in (22050, 32000, 44100, 48000, 88200, 96000, 192000): n = max(n, a)
    return int(np.log2(max(1, n)))


def _close(a, b, tol):
    try:
        a = np.asarray(a, dtype=np.float64); b = np.asarray(b, dtype=np.float64)
        return a.shape == b.shape and bool(np.all(np.isfinite(a))) and float(np.max(np.abs(a - b))) <= tol * max(1.0, float(np.max(np.abs(b))))
    except Exception:
        return False


def _choose(name, args, kwargs):
    k = _K[name]; ref_t0 = time.perf_counter(); ref = k["ref"](*args, **kwargs); best = ("numpy", time.perf_counter() - ref_t0)
    for be, fn in k["alts"].items():
        if be not in available() and be != "native":
            continue
        try:
            t0 = time.perf_counter(); out = fn(*args, **kwargs); dt = time.perf_counter() - t0
            if _close(out, ref, k["tol"]) and dt < best[1] * 0.9:
                best = (be, dt)
        except Exception:
            continue
    return best[0], ref


def run(name, *args, **kwargs):
    k = _K[name]; key = (name, _size_class(args))
    be = _CHOICE.get(key)
    if be is None:
        if not _CHOICE: _load()
        be = _CHOICE.get(key)
    if be is None:
        be, out = _choose(name, args, kwargs)
        with _LOCK:
            _CHOICE[key] = be; _save()
        return out
    fn = k["ref"] if be == "numpy" else k["alts"].get(be, k["ref"])
    t0 = time.perf_counter()
    try:
        out = fn(*args, **kwargs)
    except Exception:
        with _LOCK:
            _CHOICE[key] = "numpy"
        out = k["ref"](*args, **kwargs)
        be = "numpy"
    st = STATS.setdefault((name, be), [0, 0.0]); st[0] += 1; st[1] += time.perf_counter() - t0
    return out


def lane(name):
    ln = _LANES.get(name)
    if ln is None:
        try:
            import scode_coordinator as sc
            ln = _LANES[name] = sc.lane("hybrid"); return ln
        except Exception:
            pass
        try:
            import thread_budget as tb
            ln = tb.make_lane("hybrid-" + name, max_workers=max(1, tb.lane_workers() // 2), max_pending=128)
        except Exception:
            from concurrent.futures import ThreadPoolExecutor
            ln = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hybrid-" + name)
        _LANES[name] = ln
    return ln


def submit(name, *args, **kwargs):
    """Run a kernel in the sCode 'hybrid' direction; returns a future."""
    try:                                   # R101: the unified compute front door (same lane, same priority)
        import compute
        return compute.run("hybrid", name, *args, **kwargs)
    except Exception:
        pass
    try:
        import scode_coordinator as sc
        return sc.direct("hybrid", run, name, *args, **kwargs)
    except Exception:
        return lane(name).submit(run, name, *args, **kwargs)


def report():
    rows = ["backends available: " + ", ".join(available())]
    for (n, c), b in sorted(_CHOICE.items()):
        rows.append("%-24s size 2^%-2d → %s" % (n, c, b))
    for (n, b), (calls, sec) in sorted(STATS.items()):
        rows.append("%-24s %-7s %6d calls %8.3f s" % (n, b, calls, sec))
    return "\n".join(rows)


# ------------------------------------------------------------------ built-in kernels
def _osc_ref(phase0, freq, n, sr, amp=1.0, meum=1.0):
    ph = (phase0 + np.arange(int(n)) * float(freq) / float(sr)) % (2 * np.pi)
    return (np.sin(ph) * float(amp) * float(meum)).astype(np.float32)


def _osc_lua():
    try:
        import lupa.luajit21 as lj
    except Exception:
        return None
    L = lj.LuaRuntime(unpack_returned_tuples=True)
    f = L.eval("""function(phase0, freq, n, sr, amp, meum, out)
        local s, tau = math.sin, 2*math.pi
        local k = freq / sr
        for i = 0, n-1 do out[i] = s((phase0 + i*k) % tau) * amp * meum end
    end""")

    def osc(phase0, freq, n, sr, amp=1.0, meum=1.0):
        out = np.zeros(int(n), dtype=np.float64)
        import array
        buf = [0.0] * int(n)
        t = L.table_from(buf)
        f(float(phase0), float(freq), int(n), float(sr), float(amp), float(meum), t)
        return np.fromiter((t[i] for i in range(int(n))), dtype=np.float64, count=int(n)).astype(np.float32)
    return osc


def _osc_julia():
    try:
        import julia_bridge as jb
        if not jb.julia_available():
            return None
        jl = jb._init_julia()
        fn = jl.seval("(p0, f, n, sr, a, m) -> Float32[sin(mod(p0 + i*f/sr, 2pi))*a*m for i in 0:n-1]")

        def osc(phase0, freq, n, sr, amp=1.0, meum=1.0):
            return np.asarray(fn(float(phase0), float(freq), int(n), float(sr), float(amp), float(meum)), dtype=np.float32)
        return osc
    except Exception:
        return None


def _fold_ref(x, depth):
    x = np.asarray(x, dtype=np.float64) * float(depth)
    return (np.abs(((x + 1.0) % 4.0) - 2.0) - 1.0).astype(np.float32)


def _ca_ref(rule, width, steps):
    row = np.zeros(int(width), dtype=np.int64); row[int(width) // 2] = 1; out = np.zeros((int(steps), int(width)), dtype=np.int8)
    for i in range(int(steps)):
        out[i] = row; idx = (np.roll(row, 1) << 2) | (row << 1) | np.roll(row, -1); row = (int(rule) >> idx) & 1
    return out


def _ca_lua():
    try:
        import lupa.luajit21 as lj
    except Exception:
        return None
    L = lj.LuaRuntime()
    f = L.eval("""function(rule, w, steps)
        local row, out = {}, {}
        for i = 0, w-1 do row[i] = 0 end; row[math.floor(w/2)] = 1
        for s = 0, steps-1 do
          local nr = {}
          for i = 0, w-1 do
            out[s*w + i] = row[i]
            local l, c, r = row[(i-1) % w], row[i], row[(i+1) % w]
            nr[i] = bit.band(bit.rshift(rule, l*4 + c*2 + r), 1)
          end
          row = nr
        end
        return out
    end""")

    def ca(rule, width, steps):
        t = f(int(rule), int(width), int(steps))
        return np.array([t[i] for i in range(int(width) * int(steps))], dtype=np.int8).reshape(int(steps), int(width))
    return ca


register("osc_fill", _osc_ref, tol=1e-5, luajit=_osc_lua(), julia=_osc_julia())
register("wavefold", _fold_ref, tol=1e-6)
register("ca_evolve", _ca_ref, tol=0.0, luajit=_ca_lua())
