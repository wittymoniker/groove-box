"""Optional special-relativity projection for Mathematician's Groovebox.

This module contains original Groovebox code implementing standard textbook
special-relativity formulas. No NASA source code is copied here. NASA simulation
projects (notably Trick/cFS ecosystem material) were consulted as engineering
references for simulation architecture and are credited in THIRD_PARTY_AND_NASA_NOTES.md.

The projection is deliberately downstream of canonical identity: enabling it
changes a performance/render interpretation, never the Universal Field ID.
"""
from __future__ import annotations
import math


def sanitize_beta(beta: float) -> float:
    """Return a finite subluminal beta. This is domain validation, not audio clamping."""
    b = float(beta)
    if not math.isfinite(b):
        return 0.0
    # Physical SR requires |beta| < 1.  Preserve sign and keep a numerical gap.
    if b >= 1.0:
        return math.nextafter(1.0, 0.0)
    if b <= -1.0:
        return math.nextafter(-1.0, 0.0)
    return b


def lorentz_gamma(beta: float) -> float:
    b = sanitize_beta(beta)
    return 1.0 / math.sqrt(1.0 - b * b)


def longitudinal_doppler(beta: float) -> float:
    """Relativistic longitudinal Doppler factor sqrt((1+β)/(1-β))."""
    b = sanitize_beta(beta)
    return math.sqrt((1.0 + b) / (1.0 - b))


def project_event(event: dict, beta: float, amount: float = 1.0) -> dict:
    """Project a performance event without changing its canonical identity."""
    out = dict(event or {})
    a = float(amount)
    if not math.isfinite(a):
        a = 0.0
    # amount is intentionally free-fitting: 0 = neutral, 1 = full SR factor,
    # >1 exaggerates the logarithmic factor without hard saturation.
    d = longitudinal_doppler(beta)
    factor = math.exp(math.log(d) * a)
    out["rate"] = float(out.get("rate", 1.0)) * factor
    out["pitch_semitones"] = float(out.get("pitch_semitones", 0.0)) + 12.0 * math.log2(factor)
    out["relativity"] = {
        "beta": sanitize_beta(beta),
        "gamma": lorentz_gamma(beta),
        "doppler": d,
        "amount": a,
        "factor": factor,
        "identity_preserved": True,
    }
    return out
