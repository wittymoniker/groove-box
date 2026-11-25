"""CANONICAL_DECISION_R31_6: one shared decision layer for every module.

Every module that needs a "decision" (a probability, a choice, a modulation depth …) asks this layer
instead of drawing its own random numbers:

  canonical mode   at least one canonical engine is active with level > 0:
                   value = canonical_value(seed, module, key, slot) × activation level.
                   Time-invariant: the same (seed, module, key, slot) always gives the same value,
                   whatever the time, block size or render order. The module's internal default is
                   disregarded.
  fallback mode    no canonical activation (or level 0):
                   value = module default × Morph Bridge mix, optionally varied in time by a
                   deterministic hash of the absolute time index (time-variant fallback).

All functions are pure (no Qt, no globals besides constants), so audio threads, export workers and
render processes reach identical decisions.
"""
from __future__ import annotations

import hashlib

import numpy as np

_MASK64 = 0xFFFFFFFFFFFFFFFF


def seed_int(seed) -> int:
    """Any seed (int, text, bytes, any length) → 64-bit integer, every byte counts."""
    if isinstance(seed, (int, np.integer)) and not isinstance(seed, bool):
        return int(seed) & _MASK64
    b = seed if isinstance(seed, bytes) else str(seed).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(b, digest_size=8).digest(), "little")


def canonical_unit(seed, module, key, slot=0) -> float:
    """Time-invariant canonical value in [0, 1) for (seed, module, key, slot)."""
    h = hashlib.blake2b(f"{seed_int(seed)}|{module}|{key}|{int(slot)}".encode("utf-8"), digest_size=8).digest()
    return (int.from_bytes(h, "little") >> 11) / float(1 << 53)


def hash_units(seed, slot, idx, salt):
    """Vectorised splitmix64 → [0, 1): pure function of (seed, slot, absolute index, salt)."""
    with np.errstate(over="ignore"):
        x = (np.asarray(idx, dtype=np.uint64) * np.uint64(0x9E3779B97F4A7C15)
             + np.uint64((int(seed_int(seed)) * 1000003 + int(slot) * 7919 + int(salt) * 104729) & _MASK64))
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        x = x ^ (x >> np.uint64(31))
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def decide(module, key, *, seed=0, slot=0, active=False, level=0.0, default=0.5, mix=1.0,
           canonical_value=None, lo=0.0, hi=1.0, time_index=None, time_variance=0.0):
    """Return (value, mode).

    canonical_value: an explicit canonical value (e.g. a module's own decision module); when None
    the shared canonical_unit(seed, module, key, slot) mapped to [lo, hi] is used.
    time_index / time_variance: the fallback's time-variant component (0 = constant fallback).
    """
    lvl = float(np.clip(float(level or 0.0), 0.0, 1.0))
    if active and lvl > 0.0:
        base = canonical_value
        if base is None or float(base) <= 0.0:
            base = lo + (hi - lo) * canonical_unit(seed, module, key, slot)
        return float(np.clip(float(base) * lvl, min(lo, 0.0), max(hi, 1.0))), "canonical"
    # MD_STOCH_R7: the mix has no upper cap (floor 0; a non-finite mix means the neutral 1).
    m = 1.0 if mix is None else float(mix)
    m = max(0.0, m) if np.isfinite(m) else 1.0
    v = float(default) * m
    if time_index is not None and time_variance:
        u = float(hash_units(seed, slot, [int(time_index)], 7)[0]) - 0.5
        v = v * (1.0 + 2.0 * float(time_variance) * u)
    return float(v), "fallback"


class DecisionContext:
    """A frozen snapshot of the app's canonical state, safe to pass to threads / processes."""

    def __init__(self, seed=0, active=False, level=0.0, mix=1.0, levels=None):
        self.seed = seed
        self.active = bool(active)
        self.level = float(level)
        self.mix = float(mix)
        self.levels = dict(levels or {})

    def decide(self, module, key, slot=0, default=0.5, **kw):
        lvl = self.levels.get(module, self.level)
        return decide(module, key, seed=self.seed, slot=slot, active=self.active and lvl > 0,
                      level=lvl, default=default, mix=self.mix, **kw)

    def as_dict(self):
        return {"seed": self.seed, "active": self.active, "level": self.level, "mix": self.mix, "levels": self.levels}

    @classmethod
    def from_dict(cls, d):
        d = dict(d or {})
        return cls(d.get("seed", 0), d.get("active", False), d.get("level", 0.0), d.get("mix", 1.0), d.get("levels"))


def context_from_app(app) -> DecisionContext:
    """Snapshot the live app (UI thread): seed text, active engines, mean deck level, Morph Bridge mix."""
    try:
        seed = app._seed_text() if hasattr(app, "_seed_text") else str(getattr(app, "global_seed", 0))
    except Exception:
        seed = 0
    try:
        engines = sorted(app._active_engine_sources())
    except Exception:
        engines = []
    levels = {}
    for e in engines:
        try:
            levels[e] = float(app._canonical_level(e))
        except Exception:
            levels[e] = 1.0
    level = float(np.mean(list(levels.values()))) if levels else 0.0
    try:
        mix = float(getattr(app, "md_stoch_default_mix", 1.0))
    except Exception:
        mix = 1.0
    return DecisionContext(seed, bool(engines), level, mix, levels)
