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


def _julia_parity(vec: dict | None = None) -> bool:
    """True when the router has a Julia kernel that matched the NumPy reference (R123: the old check compared the
    Meum-normalized eqr_isn with a plain sine, so a working Julia could never pass)."""
    try:
        import hybrid_runtime as hr
        return hr.kernel_matrix().get("osc_fill", {}).get("julia", "unavailable") != "unavailable"
    except Exception:
        return False


def fill_block(vec: dict, n: int, sr: int = 48000) -> np.ndarray:
    """Audio-rate fill from a control vector. Rust if present, else NumPy."""
    n = max(1, int(n))
    sr = max(1, int(sr))
    phase = (vec["phase"] + np.arange(n) * vec["freq"] / sr) % (2 * np.pi)
    # R123: the unchecked native voice path is gone — it produced a different waveform than the NumPy fallback, so
    # the same seed sounded different on machines with and without the accel library. Every backend (Rust, C++, C,
    # Go, LuaJIT, Julia) now goes through the router, which only uses one that matches the reference.
    try:   # R99: the hybrid router picks NumPy / LuaJIT / Julia for this fill, parity-checked against NumPy
        import hybrid_runtime as hr
        return hr.run("osc_fill", float(vec["phase"]), float(vec["freq"]), n, sr, float(vec["amp"]), float(vec["meum"]))
    except Exception:
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
