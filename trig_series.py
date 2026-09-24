"""Author/book trigonometry series for Mathematician's Groovebox.

Forward trigonometry for the Trigonometry Engine is defined from the author's
cyclic isn series and its X/Y components, not by calling libm/NumPy sin/cos or
by using the legacy 2*func(x/2) chord shortcut:

    isn(gamma) = gamma^2/2! - gamma^4/4! + gamma^6/6! - ...
    isx(gamma) = 1 - isn(gamma)
    isy(gamma) = 1 - isn(gamma - pi/2)
    cos(gamma) = isx(gamma)
    sin(gamma) = isy(gamma)
    tan(gamma) = isy(gamma) / isx(gamma)

The inverse-isosceles helpers remain separate and are evaluated from the
corresponding Maclaurin/binomial series; no circular/inverse trig library call
is used in this module.
"""
from __future__ import annotations

import math
from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover - scalar fallback for bootstrap tools
    np = None

PI = 3.14159265358979323846264338327950288419716939937510
TAU = 2.0 * PI
FORWARD_TERMS = 32
INVERSE_TERMS = 48


def _reduce_scalar(x: float) -> float:
    if not math.isfinite(x):
        return x
    return (x + PI) % TAU - PI


def cyclic_isn_scalar(x: float, terms: int = FORWARD_TERMS) -> float:
    """Direct real cyclic isn series: x²/2! - x⁴/4! + x⁶/6! - ..."""
    a = _reduce_scalar(float(x))
    if not math.isfinite(a):
        return math.nan
    term = a * a / 2.0
    total = term
    for n in range(2, max(2, int(terms)) + 1):
        term *= -(a * a) / ((2.0 * n - 1.0) * (2.0 * n))
        total += term
    return total


def isx_scalar(x: float) -> float:
    return 1.0 - cyclic_isn_scalar(float(x))


def isy_scalar(x: float) -> float:
    return 1.0 - cyclic_isn_scalar(float(x) - PI / 2.0)


def tan_scalar(x: float) -> float:
    c = isx_scalar(float(x))
    s = isy_scalar(float(x))
    if c == 0.0:
        return math.copysign(math.inf, s if s != 0.0 else 1.0)
    return s / c


def chord_isn_scalar(x: float, terms: int = FORWARD_TERMS) -> float:
    """Legacy inverse-isosceles forward coordinate, evaluated as its own series.

    This helper exists only for compatibility/EQR coordinates; it is not used
    by forward Trigonometry Engine sin/cos/tan equivalence.
    """
    a=float(x); term=a; total=a
    for n in range(1, max(1, int(terms)) + 1):
        nf=float(n)
        term *= -(a*a)/(4.0*(2.0*nf)*(2.0*nf+1.0))
        total += term
    return total


def chord_ics_scalar(x: float, terms: int = FORWARD_TERMS) -> float:
    a=float(x); term=2.0; total=2.0
    for n in range(1, max(1, int(terms)) + 1):
        nf=float(n)
        term *= -(a*a)/(4.0*(2.0*nf-1.0)*(2.0*nf))
        total += term
    return total


def _asin_series_unit_scalar(z: float, terms: int = INVERSE_TERMS) -> float:
    """arcsin(z) from its Maclaurin series with a series-preserving reduction."""
    z = float(z)
    if math.isnan(z) or abs(z) > 1.0:
        return math.nan
    sign = -1.0 if z < 0.0 else 1.0
    a = abs(z)
    reduce = a > 0.5
    if reduce:
        a = math.sqrt(max(0.0, (1.0 - a) / 2.0))
    term = a
    total = a
    for n in range(1, max(1, int(terms)) + 1):
        k = 2.0 * n - 1.0
        term *= (a * a * k * k) / ((2.0 * n) * (2.0 * n + 1.0))
        total += term
    if reduce:
        total = PI / 2.0 - 2.0 * total
    return sign * total


def inverse_isn_scalar(x: float) -> float:
    """Author inverse-isosceles Maclaurin series: 2*asin(x/2), series-evaluated."""
    y = max(-2.0, min(2.0, float(x)))
    return 2.0 * _asin_series_unit_scalar(y / 2.0)


def inverse_ics_scalar(x: float) -> float:
    """Complementary inverse series from the book relation: pi - isn^-1(x)."""
    return PI - inverse_isn_scalar(float(x))


def _arr(x: Any):
    if np is None:
        raise RuntimeError("NumPy is unavailable for vector book-series evaluation")
    return np.asarray(x, dtype=np.float64)


def _out(v: Any):
    if np is None:
        return v
    a = np.asarray(v)
    return a.item() if a.ndim == 0 else a


def cyclic_isn(x: Any, terms: int = FORWARD_TERMS):
    if np is None:
        return cyclic_isn_scalar(float(x), terms)
    a = _arr(x)
    with np.errstate(invalid="ignore"):
        a = np.remainder(a + PI, TAU) - PI
    term = a * a / 2.0
    total = term.copy()
    for n in range(2, max(2, int(terms)) + 1):
        term *= -(a * a) / ((2.0 * n - 1.0) * (2.0 * n))
        total += term
    total = np.where(np.isfinite(a), total, np.nan)
    return _out(total)


def isx(x: Any):
    if np is None:
        return isx_scalar(float(x))
    return _out(1.0 - np.asarray(cyclic_isn(x), dtype=np.float64))


def isy(x: Any):
    if np is None:
        return isy_scalar(float(x))
    a = _arr(x)
    return _out(1.0 - np.asarray(cyclic_isn(a - PI / 2.0), dtype=np.float64))


def tan(x: Any):
    if np is None:
        return tan_scalar(float(x))
    s = np.asarray(isy(x), dtype=np.float64)
    c = np.asarray(isx(x), dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = s / c
    return _out(out)


# Explicit semantic aliases used by host/game code.
book_sin = isy
book_cos = isx
book_tan = tan
book_isn = cyclic_isn
book_sin_scalar = isy_scalar
book_cos_scalar = isx_scalar
book_tan_scalar = tan_scalar
book_isn_scalar = cyclic_isn_scalar
