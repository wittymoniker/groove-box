"""Deterministic GOAVA three-sine voice configuration.

Voice 1 is the root reference (ratio 1). Voice 2 is multiplied by the shared
spectrum factor; voice 3 is divided by the same factor. The pair is therefore
mirrored around 1 in log-frequency space. Amplitudes are independent and
bounded, with the historic GOAVA mix as the factory default.
"""
from __future__ import annotations

import math
from typing import Any

DEFAULT_SETTINGS = {
    "schema": 1,
    "spectrum_offset": 0.5,
    "amplitudes": [0.33, 0.22, 0.15],
}
MIN_SPECTRUM_FACTOR = 1.01
MAX_SPECTRUM_FACTOR = 5.0


def normalize_settings(value: Any = None) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    try:
        offset = float(raw.get("spectrum_offset", DEFAULT_SETTINGS["spectrum_offset"]))
        if not math.isfinite(offset):
            raise ValueError
    except Exception:
        offset = float(DEFAULT_SETTINGS["spectrum_offset"])
    factor = min(MAX_SPECTRUM_FACTOR, max(MIN_SPECTRUM_FACTOR, 1.0 + offset))
    offset = factor - 1.0
    raw_amps = raw.get("amplitudes", DEFAULT_SETTINGS["amplitudes"])
    amps = []
    for i, default in enumerate(DEFAULT_SETTINGS["amplitudes"]):
        try:
            amp = float(raw_amps[i])
            if not math.isfinite(amp):
                raise ValueError
        except Exception:
            amp = float(default)
        amps.append(min(1.0, max(0.0, amp)))
    return {"schema": 1, "spectrum_offset": offset, "amplitudes": amps}


def relative_pitches(settings: Any = None) -> list[float]:
    cfg = normalize_settings(settings)
    multiplier = 1.0 + cfg["spectrum_offset"]
    return [1.0, multiplier, 1.0 / multiplier]


def voice_parameters(base_frequency: float, settings: Any = None) -> dict[str, list[float]]:
    cfg = normalize_settings(settings)
    try:
        base = float(base_frequency)
        if not math.isfinite(base) or base <= 0.0:
            raise ValueError
    except Exception:
        base = 432.0
    ratios = relative_pitches(cfg)
    amplitudes = list(cfg["amplitudes"])
    return {
        "relative_pitches": ratios,
        "frequencies": [base * ratio for ratio in ratios],
        "amplitudes": amplitudes,
    }
