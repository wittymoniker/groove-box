"""seed_divergence.py — GROOVEBOX_R32_SEED_DIVERGENCE_20261109

Why outputs sounded (and looked, and played) alike across seeds: per-instrument values were
``vals[i % n]`` of a short list, and when the seed program evaluated to one number every
instrument, visual and game domain received *that same number* with a tiny index offset.
Deterministic decorrelation fixes this without touching determinism:

    diverge(v, index, salt, amount)

mixes the evaluated seed value with a hash of (value, index, salt) and spreads the result
over the value's own magnitude range, so instrument 3's wavetable and instrument 3's ball
get different but reproducible numbers from the same seed program, and a change of seed
moves every domain by a different amount.  ``amount`` (0..1, default 0.6) is the
"Divergence" control on the quick rack; 0 restores the old behaviour exactly.
"""
from __future__ import annotations

import hashlib
import math
import struct

DEFAULT_AMOUNT = 0.6
DOMAINS = ("audio", "synth", "vector", "wavetable", "ball", "cellular", "multidim", "video", "game", "sequence")


def _unit(value, index, salt):
    key = struct.pack("<dq", float(value), int(index)) + str(salt).encode("utf-8", "replace")
    h = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(h, "little") / 2.0 ** 64        # [0, 1)


def diverge(value, index=0, salt="audio", amount=DEFAULT_AMOUNT):
    """Deterministically spread ``value`` for (index, salt).  amount 0 → value unchanged."""
    try:
        v = float(value)
    except Exception:
        return 0.0
    if not math.isfinite(v):
        return 0.0
    a = max(0.0, min(1.0, float(amount)))
    if a <= 0.0:
        return v
    u = _unit(v, index, salt)                              # 0..1
    span = abs(v) if abs(v) > 1e-9 else 1.0
    # ±span·amount around the value, sign-preserving, plus a sub-unit jitter so values that
    # differ only after rounding still land on distinct numbers.
    offset = (u * 2.0 - 1.0) * span * a
    out = v + offset
    if v != 0.0 and (out == 0.0 or math.copysign(1.0, out) != math.copysign(1.0, v)):
        out = math.copysign(abs(out) + 1e-6, v)
    return out


def diverge_list(values, salt="audio", amount=DEFAULT_AMOUNT, n=None):
    """A list of n values from a list of any length: cycles, then decorrelates each slot."""
    vals = [float(x) for x in (values or []) if isinstance(x, (int, float)) and math.isfinite(float(x))]
    if not vals:
        return []
    n = len(vals) if n is None else max(1, int(n))
    return [diverge(vals[i % len(vals)], i, salt, amount) for i in range(n)]


def amount_from(app):
    """R32.8 IDEAL DEFAULT: divergence follows the canonical controllers. With no explicit user value it
    is DEFAULT_AMOUNT while any canonical engine is active (structural decorrelation of the seeded
    composition) and exactly 0 (legacy, stable) when none is. A value set in the Quick Rack wins."""
    v = getattr(app, "seed_divergence", None)
    if v is not None and getattr(app, "_r32_divergence_user", False):
        try:
            return max(0.0, min(1.0, float(v)))
        except Exception:
            return DEFAULT_AMOUNT
    try:
        return DEFAULT_AMOUNT if app._get_active_engine_set() else 0.0
    except Exception:
        return 0.0


def apply_to_app(app, value, index, salt="audio"):
    """Convenience used by Groovebox's per-index seed readers."""
    return diverge(value, index, salt, amount_from(app))
