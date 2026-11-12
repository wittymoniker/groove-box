"""scode_hybrid.py — two-tier sCode and an identity pool.

GROOVEBOX_SCODE_HYBRID_20261111
Control rate evaluates the seed once per block and emits a small parameter
vector. Audio rate fills the buffer from that vector (Rust when the accel
library is loaded, NumPy otherwise). Julia is used only after a parity check.

The pool is keyed by (seed fingerprint, instrument, block). Unchanged blocks
are not recomputed. Visual reads the cached vector; it does not re-evaluate.
"""
from __future__ import annotations

import hashlib
import os
from collections import OrderedDict

import numpy as np

_CACHE = OrderedDict()
_CACHE_MAX = 256
_JULIA_OK = None


def fingerprint(seed, script: str = "") -> str:
    raw = ("%s|%s" % (seed, script or "")).encode("utf-8", "replace")
    return hashlib.sha256(raw).hexdigest()[:16]


def control_vector(seed, t: float, script: str = "", env_fn=None) -> dict:
    """One control-rate reading of the seed. Finite numbers only."""
    vals = []
    if script and env_fn is not None:
        try:
            import seed_lang
            vals = list(seed_lang.values(script, env_fn(t)))[:8]
        except Exception:
            vals = []
    if not vals:
        s = float(seed or 1)
        vals = [s % 1.0, (s * 0.618) % 1.0, t]
    while len(vals) < 4:
        vals.append(0.0)
    freq = 40.0 + abs(vals[0]) % 2000.0
    amp = min(1.0, abs(vals[1]) % 1.0)
    phase = float(vals[2])
    meum = 1.0 + (abs(vals[3]) % 0.2)
    return {"freq": freq, "amp": amp, "phase": phase, "meum": meum, "raw": vals[:4]}


def _julia_parity(vec: dict) -> bool:
    """Julia is allowed only if one operator matches the Python reference."""
    global _JULIA_OK
    if _JULIA_OK is not None:
        return _JULIA_OK
    try:
        import julia_bridge as jb
        if not jb.julia_available():
            _JULIA_OK = False
            return False
        py = float(np.sin(vec["phase"]))
        jl = jb.jl_eqr_isn(vec["phase"])
        _JULIA_OK = jl is not None and abs(float(jl) - py) < 1e-6
    except Exception:
        _JULIA_OK = False
    return _JULIA_OK


def fill_block(vec: dict, n: int, sr: int = 48000) -> np.ndarray:
    """Audio-rate fill from a control vector. Rust if present, else NumPy."""
    n = max(1, int(n))
    sr = max(1, int(sr))
    phase = (vec["phase"] + np.arange(n) * vec["freq"] / sr) % (2 * np.pi)
    try:
        import groovebox as g
        fn = getattr(g, "_GB_ACCEL_FUNCS", {}).get("voice")
        if fn is not None:
            out = np.zeros(n, dtype=np.float32)
            ph = phase.astype(np.float64)
            fn(ph.ctypes.data_as(__import__("ctypes").POINTER(__import__("ctypes").c_double)),
               n, float(vec["meum"]), 1.0, 0.0, 0.0, 1, 1, 0, 0, 0.2,
               1, 0, 1.0, 1.0, out.ctypes.data_as(__import__("ctypes").POINTER(__import__("ctypes").c_float)))
            return out * float(vec["amp"])
    except Exception:
        pass
    if _julia_parity(vec):
        # Experimental operators only; the fill itself stays local.
        pass
    return (np.sin(phase) * float(vec["amp"]) * float(vec["meum"])).astype(np.float32)


def pool_block(seed, instrument: str, block: int, t: float, n: int, sr: int = 48000,
               script: str = "", env_fn=None):
    """Return (vector, buffer), using the identity cache."""
    fp = fingerprint(seed, script)
    key = (fp, str(instrument), int(block))
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        return hit, fill_block(hit, n, sr)
    vec = control_vector(seed, t, script, env_fn)
    buf = fill_block(vec, n, sr)
    _CACHE[key] = vec
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return vec, buf


def visual_vector(seed, instrument: str, block: int):
    """What the visual pool should read. None if the audio block is not cached yet."""
    fp = fingerprint(seed, "")
    return _CACHE.get((fp, str(instrument), int(block)))
