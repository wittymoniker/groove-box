"""Deterministic canonical response measurement.

PROB is a bounded 0..2 responsiveness coefficient. It is not a probability,
chance, percentage, distribution, or statistical estimate. It scales the
measured canonical response amplitude directly. RAND and GOAVA remain separate
bounded contribution controls; situational fit attenuates their base response.
"""
from __future__ import annotations
import math


def _bounded(value, lo, hi, fallback):
    try:
        x = float(value)
        if math.isfinite(x):
            return max(lo, min(hi, x))
    except Exception:
        pass
    return float(fallback)


def measure(rand_level=1.0, goava_level=1.0, prob_response=1.0,
            situational_insertability=1.0, **legacy):
    """Measure canonical response and return an explicit amplitude multiplier.

    ``prob_sensitivity`` is accepted as a compatibility keyword only; its value
    is interpreted on the same 0..2 response-coefficient scale. No random draw,
    event omission, normalization to a unit interval, or statistical operation
    occurs here. The output multiplier is allowed to reach 2.0.
    """
    if "prob_sensitivity" in legacy:
        prob_response = legacy.pop("prob_sensitivity")
    if legacy:
        raise TypeError("unexpected arguments: " + ", ".join(sorted(legacy)))
    rand = _bounded(rand_level, 0.0, 1.0, 1.0)
    goava = _bounded(goava_level, 0.0, 1.0, 1.0)
    response = _bounded(prob_response, 0.0, 2.0, 1.0)
    situation = _bounded(situational_insertability, 0.0, 1.0, 0.5)
    base_response = (rand + goava) * 0.5
    # Situational mismatch attenuates the base response. PROB then scales the
    # resulting response linearly, preserving its full 0..2 range.
    situational_factor = 1.0 - (1.0 - situation) * base_response
    amplitude = response * situational_factor
    return {
        "rand": rand,
        "goava": goava,
        "prob_response": response,
        "situational_insertability": situation,
        "base_response": base_response,
        "situational_factor": situational_factor,
        "response_amplitude": amplitude,
        "amplitude_multiplier": amplitude,
        "contract": "prob-0..2-linear-responsiveness-v2",
        "interpretation": "response amplitude coefficient; not statistical",
    }
