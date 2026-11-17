"""Deterministic global → instrument → step tuning inheritance.

Tuning is a pitch transform, not an audio effect.  The resolver copies and
sanitizes input dictionaries; callers may safely pass mutable project state.
All values are expressed in cents except ``system``.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Mapping

SYSTEMS = ("equal", "just", "pythagorean", "meantone", "meum")
DEFAULT_TUNING = {"system": "equal", "detune": 0.0, "stretch": 0.0}

# Ratios within an octave, ordered by chromatic pitch class.  Equal temperament
# is computed exactly; the other tables provide conventional, bounded presets.
_RATIOS = {
    "just": (1.0, 16/15, 9/8, 6/5, 5/4, 4/3, 45/32, 3/2, 8/5, 5/3, 9/5, 15/8),
    "pythagorean": (1.0, 256/243, 9/8, 32/27, 81/64, 4/3, 729/512, 3/2, 128/81, 27/16, 16/9, 243/128),
    "meantone": (1.0, 1.0449067, 1.1180340, 1.1962790, 1.25, 1.3374806,
                 1.3975425, 1.4953488, 1.6, 1.6718508, 1.7888544, 1.8691859),
    # Meum is a smooth hybrid: geometric mean between equal and just ratios.
    "meum": tuple(math.sqrt((2.0 ** (i / 12.0)) * r) for i, r in enumerate(
        (1.0, 16/15, 9/8, 6/5, 5/4, 4/3, 45/32, 3/2, 8/5, 5/3, 9/5, 15/8))),
}


def sanitize_layer(layer: Any) -> Dict[str, Any]:
    """Return only valid tuning keys; absent keys continue to inherit."""
    if not isinstance(layer, Mapping):
        return {}
    out: Dict[str, Any] = {}
    if "system" in layer:
        system = str(layer.get("system") or "equal").strip().lower()
        out["system"] = system if system in SYSTEMS else "equal"
    for key, lo, hi in (("detune", -2400.0, 2400.0), ("stretch", -100.0, 100.0)):
        if key not in layer:
            continue
        try:
            value = float(layer[key])
            if math.isfinite(value):
                out[key] = min(hi, max(lo, value))
        except (TypeError, ValueError, OverflowError):
            continue
    return out


def resolve_tuning(global_layer=None, instrument_layer=None, step_layer=None) -> Dict[str, Any]:
    """Resolve layers in precedence order: global, then instrument, then step."""
    result = dict(DEFAULT_TUNING)
    sources = {}
    for label, raw in (("global", global_layer), ("instrument", instrument_layer), ("step", step_layer)):
        layer = sanitize_layer(raw)
        for key, value in layer.items():
            result[key] = value
            sources[key] = label
    result["sources"] = sources
    return result


def apply_to_hz(hz: float, base_hz: float = 432.0, global_layer=None,
                instrument_layer=None, step_layer=None) -> float:
    """Apply the resolved temperament, fixed detune and octave stretch to Hz.

    The transform is relative to ``base_hz`` so global tuning remains coherent
    across octave registers. Invalid/non-positive frequencies pass through.
    """
    try:
        frequency = float(hz)
        base = float(base_hz)
        if not (math.isfinite(frequency) and math.isfinite(base) and frequency > 0.0 and base > 0.0):
            return frequency
        cfg = resolve_tuning(global_layer, instrument_layer, step_layer)
        semitones = 12.0 * math.log2(frequency / base)
        nearest = math.floor(semitones)
        octave, pc = divmod(int(nearest), 12)
        fraction = semitones - nearest
        system = cfg["system"]
        if system == "equal":
            scale_ratio = 2.0 ** (semitones / 12.0)
        else:
            table = _RATIOS[system]
            r0 = table[pc]
            r1 = table[(pc + 1) % 12] * (2.0 if pc == 11 else 1.0)
            octave_ratio = 2.0 ** octave
            scale_ratio = octave_ratio * r0 * ((r1 / r0) ** fraction)
        detune = float(cfg["detune"])
        stretch = float(cfg["stretch"])
        cents = detune + stretch * (semitones / 12.0)
        return frequency * (scale_ratio / (2.0 ** (semitones / 12.0))) * (2.0 ** (cents / 1200.0))
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        try:
            return float(hz)
        except Exception:
            return 0.0



def apply_to_hz_array(hz_values, base_hz: float = 432.0, global_layer=None,
                      instrument_layer=None, step_layer=None):
    """Vectorized counterpart to ``apply_to_hz`` for render blocks.

    It allocates only the result and the bounded pitch-class work arrays; it is
    intended for one audio render block, not a per-sample Python loop.
    """
    try:
        import numpy as np
        values = np.asarray(hz_values, dtype=np.float64)
        out = values.copy()
        base = float(base_hz)
        if not (math.isfinite(base) and base > 0.0):
            return out
        valid = np.isfinite(values) & (values > 0.0)
        if not np.any(valid):
            return out
        cfg = resolve_tuning(global_layer, instrument_layer, step_layer)
        hz = values[valid]
        semitones = 12.0 * np.log2(hz / base)
        nearest = np.floor(semitones).astype(np.int64)
        pc = np.mod(nearest, 12)
        octave = np.floor_divide(nearest, 12)
        frac = semitones - nearest
        if cfg["system"] == "equal":
            scale_ratio = np.ones_like(hz)
        else:
            table = np.asarray(_RATIOS[cfg["system"]], dtype=np.float64)
            r0 = table[pc]
            r1 = table[(pc + 1) % 12] * np.where(pc == 11, 2.0, 1.0)
            scale_ratio = (2.0 ** octave) * r0 * ((r1 / r0) ** frac) / (2.0 ** (semitones / 12.0))
        cents = float(cfg["detune"]) + float(cfg["stretch"]) * (semitones / 12.0)
        out[valid] = hz * scale_ratio * (2.0 ** (cents / 1200.0))
        return out
    except Exception:
        try:
            return np.asarray(hz_values, dtype=np.float64).copy()
        except Exception:
            return hz_values

def set_instrument_tuning(project_state: dict, instrument: str, values: Mapping[str, Any]) -> dict:
    """Write instrument-local tuning into the existing instrument parameter map."""
    states = project_state.setdefault("instrument_param_state", {})
    inst = states.setdefault(str(instrument), {})
    inst["tuning"] = sanitize_layer(values)
    return inst["tuning"]


def set_step_tuning(sequence_memory: dict, step: int, values: Mapping[str, Any]) -> dict:
    """Write one step-local override without touching gates, pitches or automation."""
    idx = max(0, int(step))
    overrides = sequence_memory.setdefault("tuning_overrides", {})
    if not isinstance(overrides, dict):
        overrides = sequence_memory["tuning_overrides"] = {}
    key = str(idx)
    if values:
        overrides[key] = sanitize_layer(values)
    else:
        overrides.pop(key, None)
    return overrides.get(key, {})


def step_tuning(sequence_memory: Mapping[str, Any], step: int) -> dict:
    overrides = sequence_memory.get("tuning_overrides", {}) if isinstance(sequence_memory, Mapping) else {}
    if not isinstance(overrides, Mapping):
        return {}
    return sanitize_layer(overrides.get(str(max(0, int(step))), overrides.get(max(0, int(step)), {})))


def merge_tuning_layer(user_layer=None, canonical_layer=None, ownership_policy=None, seed_layer=None) -> Dict[str, Any]:
    """Resolve seed baseline → explicit user write → canonical write.

    The incoming writer owns the blend permission. The user's OFF default means
    an explicit user write replaces the seed baseline; canonical's ON default
    then lets its own write blend with that prior value. The stored source layers
    are never mutated.
    """
    seed = sanitize_layer(seed_layer)
    user = sanitize_layer(user_layer)
    canonical = sanitize_layer(canonical_layer)
    try:
        import canonical_ownership as _ownership
        policy = _ownership.normalize_policy(ownership_policy)
    except Exception:
        policy = {"canonical": {"blend": True, "strength": 1.0},
                  "user": {"blend": False, "strength": 1.0},
                  "seed": {"blend": False, "strength": 1.0}}

    result = {}
    owners = {}
    # Seed layer is the first deterministic baseline writer.
    for key, value in seed.items():
        strength = policy["seed"]["strength"]
        if key == "system":
            result[key] = value if strength >= 0.5 else "equal"
        else:
            result[key] = float(value) * strength
        owners[key] = "seed"

    def apply_layer(layer, incoming_owner):
        for key, value in layer.items():
            if key not in result:
                result[key] = value
                owners[key] = incoming_owner
                continue
            previous_owner = owners.get(key, "seed")
            if key == "system":
                src_cfg = policy[incoming_owner]
                prev_cfg = policy.get(previous_owner, policy["seed"])
                if src_cfg["strength"] <= 0.0:
                    continue
                if src_cfg["blend"]:
                    if src_cfg["strength"] >= prev_cfg["strength"]:
                        result[key] = value
                elif src_cfg["strength"] >= 0.5:
                    result[key] = value
                owners[key] = incoming_owner
            else:
                try:
                    result[key] = _ownership.blend_value(
                        result[key], value, previous_owner, incoming_owner, policy, neutral=0.0
                    )
                    owners[key] = incoming_owner
                except Exception:
                    result[key] = value
                    owners[key] = incoming_owner

    apply_layer(user, "user")
    apply_layer(canonical, "canonical")
    return sanitize_layer(result)

