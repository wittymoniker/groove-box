"""canonical_matrix.py (R132): one deterministic seed + canonical → parameter matrix every editor and tool can use.

A "composition matrix" turns the project's seed text and the active canonical engines into a vector of numbers in
0..1. Each tool declares its parameters as (name, low, high, curve); the matrix maps the vector onto them:

    cm.params(app, "audio_editor", {"gain_db": (-12, 6, "lin"), "cutoff_hz": (200, 12000, "log")})

The same seed + canonicals always give the same parameters (sha256-derived, no global random state). Changing one
canonical engine moves only part of the vector (each engine owns a slice), so "canonicalizing" a tool is gradual and
explainable: explain(...) says which engine moved which parameter.

Reverse direction (decode): fit(app, tool, spec, values) finds the matrix position closest to given parameter values
— used to "reverse-engineer" a hand-made setting into a seed suffix that reproduces it.
"""
from __future__ import annotations

import hashlib
import math

ENGINES = ("seeded", "randomizer", "phase_lock", "euclidean", "goava", "fractal_seed")
_NUDGE = 2.0 / (3.0 + 5 ** 0.5)       # 1/φ² — an engine's pull on its slice (irrational: never re-aligns with the seed)


def _unit(*parts):
    h = hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / float(1 << 64)


def context(app=None, seed=None, engines=None):
    """(seed text, active engine names) from the app, or the given overrides."""
    if app is not None:
        _APP_FOR_OVERRIDE[0] = app
    if seed is None:
        seed = ""
        try:
            seed = app._seed_text() if hasattr(app, "_seed_text") else app.input_seed_val.toPlainText()
        except Exception:
            pass
    if engines is None:
        engines = ()
        try:
            engines = tuple(sorted(app._active_engine_sources()))
        except Exception:
            pass
    return str(seed or "MATGROOVEBOX::SUPERSEED::GENESIS"), tuple(engines)


_APP_FOR_OVERRIDE = [None]          # R132: the app whose canonical_vector_override (⇧ Use vector) applies


def vector(seed, engines, tool, n):
    """n numbers in 0..1. The seed sets the base; every active engine owns a slice of the parameters and nudges it.
    A canonical vector taken from media / a file (⇧ Use vector) blends in last."""
    v = _seed_vector(seed, engines, tool, n)
    try:
        import canonical_vector_io as _cvi
        return _cvi.apply_override(_APP_FOR_OVERRIDE[0], v)
    except Exception:
        return v


def _seed_vector(seed, engines, tool, n):
    v = [_unit(seed, tool, i) for i in range(n)]
    for k, e in enumerate(ENGINES):
        if e not in engines:
            continue
        for i in range(n):
            if i % len(ENGINES) == k:                       # the engine's slice
                v[i] = (v[i] + _NUDGE * (_unit(seed, tool, e, i) - 0.5)) % 1.0
    return v


def _map(u, lo, hi, curve):
    if curve == "log" and lo > 0 and hi > 0:
        return lo * (hi / lo) ** u
    if curve == "int":
        return int(round(lo + u * (hi - lo)))
    if curve == "bool":
        return u >= 0.5
    return lo + u * (hi - lo)


def _unmap(x, lo, hi, curve):
    if curve == "log" and lo > 0 and hi > 0:
        return math.log(max(lo, x) / lo) / math.log(hi / lo)
    if curve == "bool":
        return 0.75 if x else 0.25
    return (float(x) - lo) / ((hi - lo) or 1.0)


def params(app, tool, spec, seed=None, engines=None, amount=1.0, base=None):
    """Parameters for `tool`. amount 0..1 blends from `base` (the user's values) to the matrix values."""
    s, e = context(app, seed, engines)
    names = list(spec)
    v = vector(s, e, tool, len(names))
    out = {}
    for name, u in zip(names, v):
        lo, hi, curve = (tuple(spec[name]) + ("lin",))[:3]
        if base is not None and name in base and curve not in ("bool",) and amount < 1.0:
            ub = min(1.0, max(0.0, _unmap(base[name], lo, hi, curve)))
            u = ub + (u - ub) * float(amount)
        out[name] = _map(u, lo, hi, curve)
    return out


def explain(app, tool, spec, seed=None, engines=None):
    """Lines saying which engine drives which parameter (for tooltips / the matrix view)."""
    s, e = context(app, seed, engines)
    names = list(spec); p = params(app, tool, spec, s, e)
    lines = [f"seed {s[:40]!r} · engines: {', '.join(e) or 'none (seed only)'}"]
    for i, n in enumerate(names):
        owner = ENGINES[i % len(ENGINES)]
        val = p[n]
        shown = f"{val:.4g}" if isinstance(val, float) else str(val)
        lines.append(f"  {n:<14} = {shown:<10} ← seed" + (f" + {owner}" if owner in e else ""))
    return "\n".join(lines)


def fit(app, tool, spec, values, tries=4096, seed=None, engines=None):
    """Reverse: find a seed suffix whose matrix parameters come closest to `values`. Returns (suffix, error, params)."""
    s, e = context(app, seed, engines)
    best = (None, float("inf"), None)
    names = [n for n in spec if n in values]
    for k in range(int(tries)):
        cand = f"{s}#{k}"
        p = params(app, tool, spec, cand, e)
        err = 0.0
        for n in names:
            lo, hi, curve = (tuple(spec[n]) + ("lin",))[:3]
            err += (_unmap(p[n], lo, hi, curve) - min(1.0, max(0.0, _unmap(values[n], lo, hi, curve)))) ** 2
        if err < best[1]:
            best = (f"#{k}", err, p)
    return best
