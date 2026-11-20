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
        if list(d.get("backends") or []) != available():
            return
        for k, v in d.get("choices", {}).items():
            n, c = k.rsplit("|", 1); _CHOICE[(n, int(c))] = v
    except Exception:
        pass


def _save():
    try:
        __import__("safe_io").atomic_write_json(_path(), {"choices": {"%s|%d" % k: v for k, v in _CHOICE.items()}, "backends": available()}, indent=1)
    except Exception:
        pass


class lazy:
    """An alternative backend built on first use (and rebuilt when its language becomes available).
    The builder returns a callable, or None while the language is unavailable."""
    def __init__(self, builder):
        self.builder = builder


def register(name, ref, tol=1e-6, **alts):
    _K[name] = {"ref": ref, "alts": {k: v for k, v in alts.items() if v is not None}, "tol": float(tol), "built": {}}


# GROOVEBOX_R123_HYBRID_POOL_20261119: backends are probed with a short TTL. Julia warms up after first paint and the
# C / Go kernels compile in the background, so the set grows during a session; a changed set re-measures every kernel.
_AVAIL = {"t": 0.0, "v": ("numpy",)}
_ALLOW = tuple(x.strip().lower() for x in os.environ.get("GROOVEBOX_HYBRID_BACKENDS", "").split(",") if x.strip())


def _probe():
    out = ["numpy"]
    try:
        import accel_backends as ab
        out += ab.loaded()
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
    try:
        import hybrid_native as hn
        hn.ensure_started()
        out += hn.ready()
    except Exception:
        pass
    if _ALLOW:
        out = ["numpy"] + [b for b in out if b in _ALLOW and b != "numpy"]
    return tuple(dict.fromkeys(out))


def available():
    now = time.monotonic()
    if now - _AVAIL["t"] > 2.0:
        _AVAIL["v"] = _probe(); _AVAIL["t"] = now
    return list(_AVAIL["v"])


def _alt(name, be):
    """Resolve one alternative (building lazies once per backend-set signature)."""
    k = _K[name]; a = k["alts"].get(be)
    if not isinstance(a, lazy):
        return a
    sig = tuple(available())
    hit = k["built"].get(be)
    if hit is not None and (hit[1] == sig or hit[0] is not None):
        return hit[0]
    try:
        fn = a.builder()
    except Exception:
        fn = None
    k["built"][be] = (fn, sig)
    return fn


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
    avail = available()
    for be in list(k["alts"]):
        if be not in avail:
            continue
        fn = _alt(name, be)
        if fn is None:
            continue
        try:
            t0 = time.perf_counter(); out = fn(*args, **kwargs); dt = time.perf_counter() - t0
            if _close(out, ref, k["tol"]) and dt < best[1] * 0.9:
                best = (be, dt)
        except Exception:
            continue
    return best[0], ref


_SIG = {"v": None}


def run(name, *args, **kwargs):
    k = _K[name]; key = (name, _size_class(args))
    sig = tuple(available())
    if _SIG["v"] != sig:                    # the backend set changed: every kernel is measured again
        with _LOCK:
            if _SIG["v"] is None:
                _load()
            elif _SIG["v"] != sig:
                _CHOICE.clear()
            _SIG["v"] = sig
    be = _CHOICE.get(key)
    if be is None or (be != "numpy" and be not in sig):
        be, out = _choose(name, args, kwargs)
        with _LOCK:
            _CHOICE[key] = be; _save()
        return out
    fn = k["ref"] if be == "numpy" else (_alt(name, be) or k["ref"])
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


def kernel_matrix():
    """{kernel: {backend: 'chosen' | 'ready' | 'unavailable'}} — what each language does for each kernel today."""
    avail = available(); out = {}
    chosen = {}
    for (n, _c), b in _CHOICE.items():
        chosen.setdefault(n, set()).add(b)
    for n, k in sorted(_K.items()):
        row = {"numpy": "reference" + (" · chosen" if "numpy" in chosen.get(n, ()) else "")}
        for be in k["alts"]:
            fn = _alt(n, be) if be in avail else None
            row[be] = ("chosen" if be in chosen.get(n, ()) else "ready") if fn is not None else "unavailable"
        out[n] = row
    return out


def report():
    rows = ["backends available: " + ", ".join(available())]
    try:
        import hybrid_native as hn
        rows.append("compiled backends: " + ", ".join("%s %s" % kv for kv in hn.status().items()))
    except Exception:
        pass
    for n, row in kernel_matrix().items():
        rows.append("%-12s " % n + " · ".join("%s %s" % kv for kv in row.items()))
    for (n, c), b in sorted(_CHOICE.items()):
        rows.append("%-24s size 2^%-2d → %s" % (n, c, b))
    for (n, b), (calls, sec) in sorted(STATS.items()):
        rows.append("%-24s %-7s %6d calls %8.3f s" % (n, b, calls, sec))
    return "\n".join(rows)


# ------------------------------------------------------------------ built-in kernels
# Every kernel has one NumPy reference; each language below is an alternative that must match it.
_TLS = threading.local()


def _lua():
    """One LuaJIT runtime per worker thread (lupa: a runtime is locked per call; separate runtimes run in parallel
    with the GIL released). Kernels are compiled once per runtime."""
    L = getattr(_TLS, "lua", None)
    if L is None:
        import lupa.luajit21 as lj
        L = _TLS.lua = lj.LuaRuntime(unpack_returned_tuples=True); _TLS.lua_fns = {}
    return L, _TLS.lua_fns


def _lua_fn(key, src):
    L, fns = _lua()
    f = fns.get(key)
    if f is None:
        f = fns[key] = L.eval(src)
    return L, f


_LUA_OSC = """function(phase0, freq, n, sr, amp, meum)
    local s, tau, out = math.sin, 2*math.pi, {}
    for i = 0, n-1 do out[i+1] = s((phase0 + i*freq/sr) % tau) * amp * meum end
    return out
end"""
_LUA_FOLD = """function(x, n, depth)
    local out = {}
    for i = 1, n do out[i] = math.abs(((x[i]*depth + 1.0) % 4.0) - 2.0) - 1.0 end
    return out
end"""
_LUA_CA = """function(rule, w, steps)
    local row, out = {}, {}
    for i = 0, w-1 do row[i] = 0 end; row[math.floor(w/2)] = 1
    for s = 0, steps-1 do
      local nr = {}
      for i = 0, w-1 do
        out[s*w + i + 1] = row[i]
        local l, c, r = row[(i-1) % w], row[i], row[(i+1) % w]
        nr[i] = bit.band(bit.rshift(rule, l*4 + c*2 + r), 1)
      end
      row = nr
    end
    return out
end"""


def _lua_list(t, n, dtype):
    return np.fromiter((t[i + 1] for i in range(int(n))), dtype=dtype, count=int(n))


def _osc_lua():
    import lupa.luajit21  # noqa: F401  (None when LuaJIT is absent)

    def osc(phase0, freq, n, sr, amp=1.0, meum=1.0):
        _L, f = _lua_fn("osc", _LUA_OSC)
        return _lua_list(f(float(phase0), float(freq), int(n), float(sr), float(amp), float(meum)), n, np.float64).astype(np.float32)
    return osc


def _fold_lua():
    import lupa.luajit21  # noqa: F401

    def fold(x, depth):
        x = np.asarray(x, dtype=np.float64).ravel()
        L, f = _lua_fn("fold", _LUA_FOLD)
        return _lua_list(f(L.table_from(x.tolist()), x.size, float(depth)), x.size, np.float64).astype(np.float32)
    return fold


def _ca_lua():
    import lupa.luajit21  # noqa: F401

    def ca(rule, width, steps):
        _L, f = _lua_fn("ca", _LUA_CA)
        w, s = int(width), int(steps)
        return _lua_list(f(int(rule), w, s), w * s, np.int8).reshape(s, w)
    return ca


def _julia_fn(src):
    """Compile one Julia function. PythonCall/JuliaCall ≥ 0.9.22 may be called from any Python thread; scalar-only
    kernels use _jl_call_nogil so Julia work runs in parallel with Python (the body never touches Python)."""
    import julia_bridge as jb
    if not jb.julia_available() or getattr(jb, "_jl", None) is None:
        return None, False
    fn = jb._jl.seval(src)
    return fn, hasattr(fn, "_jl_call_nogil")


def _osc_julia():
    fn, nogil = _julia_fn("(p0, f, n, sr, a, m) -> Float32[sin(mod(p0 + i*f/sr, 2pi))*a*m for i in 0:n-1]")
    if fn is None:
        return None
    call = fn._jl_call_nogil if nogil else fn

    def osc(phase0, freq, n, sr, amp=1.0, meum=1.0):
        return np.asarray(call(float(phase0), float(freq), int(n), float(sr), float(amp), float(meum)), dtype=np.float32)
    return osc


def _fold_julia():
    fn, _nogil = _julia_fn("(x, d) -> Float32[abs(mod(v*d + 1.0, 4.0) - 2.0) - 1.0 for v in x]")
    if fn is None:
        return None

    def fold(x, depth):                      # array argument: called with the GIL held (the wrapper reads Python memory)
        return np.asarray(fn(np.ascontiguousarray(np.asarray(x, dtype=np.float64).ravel()), float(depth)), dtype=np.float32)
    return fold


def _clip_julia():
    fn, _nogil = _julia_fn("(x, g) -> Float32[clamp(Float64(v)*g, -1.0, 1.0) for v in x]")
    if fn is None:
        return None

    def clip(x, gain=1.0):
        return np.asarray(fn(np.ascontiguousarray(np.asarray(x, dtype=np.float32).ravel()), float(gain)), dtype=np.float32)
    return clip


def _ca_julia():
    fn, nogil = _julia_fn("""(rule, w, steps) -> begin
        row = zeros(Int8, w); row[div(w, 2) + 1] = 1; out = zeros(Int8, steps, w)
        for s in 1:steps
            out[s, :] = row
            nr = similar(row)
            for i in 1:w
                l = row[mod(i - 2, w) + 1]; c = row[i]; r = row[mod(i, w) + 1]
                nr[i] = Int8((rule >> (4l + 2c + r)) & 1)
            end
            row = nr
        end
        out
    end""")
    if fn is None:
        return None
    call = fn._jl_call_nogil if nogil else fn

    def ca(rule, width, steps):
        return np.ascontiguousarray(np.asarray(call(int(rule), int(width), int(steps)), dtype=np.int8))
    return ca


def _compiled(lang, kernel):
    import hybrid_native as hn
    return hn.kernels(lang).get(kernel)


def _accel(lib, kernel):
    import accel_backends as ab
    return ab.kernel(lib, kernel)


def _osc_ref(phase0, freq, n, sr, amp=1.0, meum=1.0):
    ph = (phase0 + np.arange(int(n)) * float(freq) / float(sr)) % (2 * np.pi)
    return (np.sin(ph) * float(amp) * float(meum)).astype(np.float32)


def _fold_ref(x, depth):
    x = np.asarray(x, dtype=np.float64).ravel() * float(depth)
    return (np.abs(((x + 1.0) % 4.0) - 2.0) - 1.0).astype(np.float32)


def _clip_ref(x, gain=1.0):
    return np.clip(np.asarray(x, dtype=np.float32).ravel().astype(np.float64) * float(gain), -1.0, 1.0).astype(np.float32)


def _ca_ref(rule, width, steps):
    row = np.zeros(int(width), dtype=np.int64); row[int(width) // 2] = 1; out = np.zeros((int(steps), int(width)), dtype=np.int8)
    for i in range(int(steps)):
        out[i] = row; idx = (np.roll(row, 1) << 2) | (row << 1) | np.roll(row, -1); row = (int(rule) >> idx) & 1
    return out


def _langs(kernel, lua=None, julia=None, accel=False):
    alts = {"c": lazy(lambda: _compiled("c", kernel)), "go": lazy(lambda: _compiled("go", kernel))}
    if lua is not None:
        alts["luajit"] = lazy(lua)
    if julia is not None:
        alts["julia"] = lazy(julia)
    if accel:
        alts["rust"] = lazy(lambda: _accel("rust", kernel))
        alts["cpp"] = lazy(lambda: _accel("cpp", kernel))
    return alts


register("osc_fill", _osc_ref, tol=1e-5, **_langs("osc_fill", _osc_lua, _osc_julia))
register("wavefold", _fold_ref, tol=1e-6, **_langs("wavefold", _fold_lua, _fold_julia))
register("hardclip", _clip_ref, tol=1e-6, **_langs("hardclip", None, _clip_julia, accel=True))
register("ca_evolve", _ca_ref, tol=0.0, **_langs("ca_evolve", _ca_lua, _ca_julia))
