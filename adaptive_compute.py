"""Adaptive compute services for Groovebox.

Optional GPU dispatch, bounded reusable host buffers, deterministic incremental
result caching, and persistent backend hints. This module never creates a worker
pool and never changes CPU/GPU firmware power or thermal limits. Call expensive
operations from sCode worker lanes, not a real-time audio callback.
"""
from __future__ import annotations
import hashlib, json, os, threading, time
from collections import OrderedDict
import numpy as np

_LOCK = threading.RLock()
_BUFFERS = OrderedDict()
_RESULTS = OrderedDict()
_HINTS = {}
_STATS = {"cache_hits": 0, "cache_misses": 0, "gpu_calls": 0, "gpu_fallbacks": 0}
_MAX_BUFFER_BYTES = 64 * 1024 * 1024
_MAX_RESULT_BYTES = 128 * 1024 * 1024
_buffer_bytes = _result_bytes = 0
_MAX_ENTRIES = 128
_GPU = None
_GPU_ERROR = None


def _cache_root():
    p = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")), "groovebox")
    os.makedirs(p, exist_ok=True)
    return p


def _hint_path(): return os.path.join(_cache_root(), "adaptive_compute.json")


def load_hints():
    global _HINTS
    try:
        with open(_hint_path(), "r", encoding="utf-8") as f: data = json.load(f)
        if isinstance(data.get("hints"), dict): _HINTS = data["hints"]
    except Exception: pass
    return dict(_HINTS)


def save_hints():
    path = _hint_path(); tmp = path + ".part"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "hints": _HINTS}, f, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass


def hint(key, backend=None):
    with _LOCK:
        if backend is not None:
            _HINTS[str(key)] = str(backend); save_hints()
        return _HINTS.get(str(key))


def acquire_buffer(shape, dtype=np.float32, zero=False):
    """Borrow a bounded reusable contiguous host array; caller owns until release."""
    global _buffer_bytes
    dt = np.dtype(dtype); shp = tuple(int(x) for x in (shape if isinstance(shape, (tuple, list)) else (shape,)))
    key = (shp, dt.str); size = int(np.prod(shp, dtype=np.int64)) * dt.itemsize
    with _LOCK:
        bucket = _BUFFERS.get(key)
        arr = bucket.pop() if bucket else None
        if bucket is not None and not bucket: _BUFFERS.pop(key, None)
        if arr is not None: _buffer_bytes -= arr.nbytes
    if arr is None: arr = np.empty(shp, dtype=dt)
    if zero: arr.fill(0)
    return arr


def release_buffer(arr):
    global _buffer_bytes
    if not isinstance(arr, np.ndarray) or not arr.flags.c_contiguous or arr.nbytes > _MAX_BUFFER_BYTES // 4: return False
    key = (arr.shape, arr.dtype.str)
    with _LOCK:
        if _buffer_bytes + arr.nbytes > _MAX_BUFFER_BYTES: return False
        _BUFFERS.setdefault(key, []).append(arr); _BUFFERS.move_to_end(key); _buffer_bytes += arr.nbytes
        while _buffer_bytes > _MAX_BUFFER_BYTES and _BUFFERS:
            _k, values = _BUFFERS.popitem(last=False)
            for v in values: _buffer_bytes -= v.nbytes
    return True


def _digest(value, h):
    if isinstance(value, np.ndarray):
        a = np.ascontiguousarray(value)
        h.update(b"A" + a.dtype.str.encode() + repr(a.shape).encode()); h.update(memoryview(a).cast("B")); return
    h.update(type(value).__name__.encode() + b":" + repr(value).encode("utf-8", "replace") + b";")


def result_key(namespace, args, kwargs=None, revision="1"):
    h = hashlib.sha256((str(namespace) + "|" + str(revision)).encode())
    for value in args: _digest(value, h)
    for key, value in sorted((kwargs or {}).items()): h.update(key.encode()); _digest(value, h)
    return h.hexdigest()


def result_get(key):
    global _STATS
    with _LOCK:
        item = _RESULTS.get(str(key))
        if item is None: _STATS["cache_misses"] += 1; return None
        _RESULTS.move_to_end(str(key)); _STATS["cache_hits"] += 1
        return item.copy() if isinstance(item, np.ndarray) else item


def result_put(key, value):
    global _result_bytes
    if not isinstance(value, np.ndarray) or value.nbytes > _MAX_RESULT_BYTES // 4: return False
    arr = np.ascontiguousarray(value).copy(); k = str(key)
    with _LOCK:
        old = _RESULTS.pop(k, None)
        if isinstance(old, np.ndarray): _result_bytes -= old.nbytes
        _RESULTS[k] = arr; _result_bytes += arr.nbytes
        while _result_bytes > _MAX_RESULT_BYTES or len(_RESULTS) > _MAX_ENTRIES:
            _, gone = _RESULTS.popitem(last=False)
            if isinstance(gone, np.ndarray): _result_bytes -= gone.nbytes
    return True


def cached(namespace, args, compute, kwargs=None, revision="1"):
    key = result_key(namespace, args, kwargs, revision)
    value = result_get(key)
    if value is not None: return value
    value = compute()
    result_put(key, value)
    return value


def _cupy():
    global _GPU, _GPU_ERROR
    if _GPU is not None: return _GPU
    if _GPU_ERROR is not None: return None
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() < 1: raise RuntimeError("no CUDA device")
        _GPU = cp
        return cp
    except Exception as exc:
        _GPU_ERROR = str(exc); return None


def gpu_available(): return _cupy() is not None


def gpu_osc_fill(phase0, freq, n, sr, amp=1.0, meum=1.0):
    """GPU oscillator for large blocks only; small transfers are routed elsewhere."""
    global _STATS
    n = int(n)
    if n < 131072: raise RuntimeError("GPU dispatch threshold not met")
    cp = _cupy()
    if cp is None: raise RuntimeError(_GPU_ERROR or "CuPy unavailable")
    try:
        idx = cp.arange(n, dtype=cp.float64)
        phase = cp.remainder(float(phase0) + idx * float(freq) / float(sr), 2.0 * cp.pi)
        out = (cp.sin(phase) * float(amp) * float(meum)).astype(cp.float32)
        host = cp.asnumpy(out)
        with _LOCK: _STATS["gpu_calls"] += 1
        return host
    except Exception:
        with _LOCK: _STATS["gpu_fallbacks"] += 1
        raise


def report():
    with _LOCK:
        return {"gpu_available": gpu_available(), "gpu_error": _GPU_ERROR,
                "buffer_bytes": _buffer_bytes, "result_cache_bytes": _result_bytes,
                "buffer_entries": sum(len(v) for v in _BUFFERS.values()),
                "result_entries": len(_RESULTS), "stats": dict(_STATS), "hints": dict(_HINTS)}

load_hints()
