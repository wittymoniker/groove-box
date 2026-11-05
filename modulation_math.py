"""Stable, reversible modulation arithmetic shared by Groovebox domains.

Amounts are signed: positive and negative modulation are equally addressable.
Mixing is normalized by absolute weight so adding routes cannot inflate the
aggregate modulation budget.  No pitch transformation is implied here.
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping

MEUM = 1.197580734338526518831326189268352139462000770610620512690713161173612434527857961133371127128476968476
MEUM_GAIN = 1.0 + MEUM


def finite(value: float, default: float = 0.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return value if math.isfinite(value) else float(default)


def normalize_signed_amounts(amounts: Iterable[float], budget: float) -> list[float]:
    """Preserve signs and relative proportions; L1 sum equals abs(budget)."""
    vals = [finite(v) for v in amounts]
    b = abs(finite(budget))
    total = sum(abs(v) for v in vals)
    if not vals:
        return []
    if total <= 1e-15:
        return [0.0] * len(vals)
    scale = b / total
    return [v * scale for v in vals]


def signed_factor(amount: float, limit: float = MEUM_GAIN) -> float:
    """Convert signed depth to a non-negative, bounded gain factor around unity."""
    a = finite(amount)
    return min(max(1.0 + a, 0.0), max(0.0, finite(limit, MEUM_GAIN)))


def apply_signed(value: float, amount: float, low: float | None = None,
                 high: float | None = None) -> float:
    """Apply signed relative modulation; clamp only when a range is supplied."""
    v = finite(value)
    out = v * signed_factor(amount)
    if low is not None:
        out = max(finite(low), out)
    if high is not None:
        out = min(finite(high), out)
    return out


def heuristic_share(overlap: float, pattern_index: int, meum: float = MEUM,
                    canonical_active: bool = True) -> float:
    """0.5×–1.5× playlist overlap; canonical-off is a plain 50/50 blend."""
    if not canonical_active:
        return 0.5
    u = ((int(pattern_index) / finite(meum, MEUM)) % 1.0)
    return min(0.95, max(0.05, finite(overlap, 0.5) * (0.5 + u)))


def synth_shift_factor(instrument_level: float, ensemble_mean: float,
                       meum: float = MEUM) -> float:
    """Optional 0…(1+M) amplitude/probability scale; caller must not apply to pitch."""
    level = max(0.0, finite(instrument_level))
    mean = max(0.0, finite(ensemble_mean))
    ratio = level / mean if mean > 1e-15 else 1.0
    return min(max(ratio, 0.0), 1.0 + finite(meum, MEUM))


def multidim_peak_target(panel_geo_peak: float, meum: float = MEUM) -> float:
    """The multidimensional peak target is exactly M times the combined panel/geo peak."""
    return abs(finite(panel_geo_peak)) * finite(meum, MEUM)


def stable_weighted_mix(values: Iterable[float], weights: Iterable[float],
                        fallback: float = 0.0) -> float:
    """Bounded signed weighted mean; avoids growth from stacking parallel sources."""
    pairs = [(finite(v), finite(w)) for v, w in zip(values, weights)]
    den = sum(abs(w) for _, w in pairs)
    if den <= 1e-15:
        return finite(fallback)
    return sum(v * w for v, w in pairs) / den
