"""accel_backends.py — the Rust and C++ accelerator libraries as two separate hybrid backends.

GROOVEBOX_R123_HYBRID_POOL_20261119: groovebox.py loads one of them (GROOVEBOX_NATIVE_BACKEND, Rust first) for its
own hot paths. The hybrid router loads each one that exists under its own name ("rust", "cpp") so both are measured
and parity-checked independently; before, the C++ library was reported as "rust" and neither was ever selected.
Both libraries release the GIL in ctypes calls.
"""
from __future__ import annotations

import ctypes
import threading

import numpy as np

_LOCK = threading.Lock()
_LIBS = {}
_DONE = False


def _load():
    global _DONE
    with _LOCK:
        if _DONE:
            return
        _DONE = True
        try:
            import platform_runtime as pr
        except Exception:
            return
        for name, cands in (("rust", pr.rust_accel_candidates()), ("cpp", pr.cpp_accel_candidates())):
            for c in cands:
                if c.is_file():
                    try:
                        h = ctypes.CDLL(str(c))
                        f = h.gb_hardclip_f32
                        P = ctypes.POINTER(ctypes.c_float)
                        f.argtypes = [P, P, ctypes.c_size_t, ctypes.c_float, P]; f.restype = None
                        _LIBS[name] = h
                        break
                    except (OSError, AttributeError):
                        continue


def loaded():
    _load()
    return sorted(_LIBS)


def kernel(lib, name):
    _load()
    h = _LIBS.get(lib)
    if h is None:
        return None
    if name == "hardclip":
        P = ctypes.POINTER(ctypes.c_float)

        def clip(x, gain=1.0):
            x = np.ascontiguousarray(np.asarray(x, dtype=np.float32).ravel())
            out = np.empty_like(x); m = np.zeros(3, dtype=np.float32)
            h.gb_hardclip_f32(x.ctypes.data_as(P), out.ctypes.data_as(P), x.size, float(gain), m.ctypes.data_as(P))
            return out
        return clip
    return None
