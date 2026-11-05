"""Deterministic amplitude sensitivity for canonical event insertability.

PROB is a sensitivity/control amplitude, never a stochastic switch. The three
canonical contributors RAND, GOAVA, and PROB are equally weighted (1:1:1) at
canonical-only insertion points. Situational insertability determines attenuation.
"""
from __future__ import annotations
import math


def _unit(value, fallback=1.0):
    try:
        x = float(value)
        if math.isfinite(x):
            return max(0.0, min(1.0, x))
    except Exception:
        pass
    return max(0.0, min(1.0, float(fallback)))


def measure(rand_level=1.0, goava_level=1.0, prob_sensitivity=1.0, situational_insertability=1.0):
    """Return normalized 1:1:1 sensitivity and bounded amplitude multiplier."""
    rand = _unit(rand_level)
    goava = _unit(goava_level)
    prob = _unit(prob_sensitivity)
    situation = _unit(situational_insertability, 0.5)
    sensitivity = (rand + goava + prob) / 3.0
    # At sensitivity 1, poor situational fit attenuates more; at 0 it does not.
    amplitude = max(0.25, min(1.0, 1.0 - sensitivity * (1.0 - situation)))
    return {"rand": rand, "goava": goava, "prob_sensitivity": prob,
            "situational_insertability": situation,
            "balanced_sensitivity": sensitivity,
            "amplitude_multiplier": amplitude,
            "contract": "rand:goava:prob=1:1:1; deterministic-amplitude-v1"}
