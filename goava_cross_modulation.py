"""Deterministic GOAVA residual and cross AM/FM/PM field.

The field is a control signal, not an extra audible note. It can continue
through note rests and only scales the existing mix, so exact digital silence
remains silence. All state is derived from the numeric seed and saved params.
"""
from __future__ import annotations
import hashlib, math
import numpy as np

DEFAULTS = {
    "enabled": True,
    "am_enabled": True,
    "fm_enabled": True,
    "pm_enabled": True,
    "mutual_coupling": 0.18,
    "residual_level": 0.025,
    "am_depth": 0.06,
    "fm_depth": 0.025,
    "pm_index": 0.12,
    "composition_coupling": 0.12,
    "field_rate_hz": 0.37,
}

def _seed_unit(seed, lane):
    h = hashlib.sha256((str(seed) + "|GOAVA-XMOD|" + str(lane)).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / float(2**64)

def normalized_config(config=None):
    d = dict(DEFAULTS)
    if isinstance(config, dict): d.update(config)
    for k in ("mutual_coupling", "residual_level", "am_depth", "fm_depth", "pm_index", "composition_coupling"):
        try: d[k] = float(d[k]) if math.isfinite(float(d[k])) else DEFAULTS[k]
        except Exception: d[k] = DEFAULTS[k]
        d[k] = max(0.0, min(0.30 if k in ("residual_level", "am_depth", "fm_depth") else 0.50, d[k]))
    try: d["field_rate_hz"] = max(0.03, min(8.0, float(d["field_rate_hz"])))
    except Exception: d["field_rate_hz"] = DEFAULTS["field_rate_hz"]
    d["enabled"] = bool(d["enabled"])
    return d

def residual_field(n_samples, sample_rate, seed, bpm=120.0, config=None):
    """Return a deterministic bounded control field and trace; never uses RNG."""
    c = normalized_config(config)
    n = max(0, int(n_samples)); sr = max(1, int(sample_rate))
    if not n: return np.zeros(0, dtype=np.float32), {"enabled": c["enabled"], "samples": 0, "mutual_coupling": 0.0}
    t = np.arange(n, dtype=np.float64) / sr
    root = c["field_rate_hz"] * (0.75 + 0.5 * _seed_unit(seed, "rate"))
    rates = np.array([root, root * (1.5 + _seed_unit(seed, "ratio1")), root * (2.0 + _seed_unit(seed, "ratio2"))])
    phases = np.array([_seed_unit(seed, f"phase{i}") * math.tau for i in range(3)])
    waves = np.sin(math.tau * rates[:, None] * t[None, :] + phases[:, None])
    mutual = c["mutual_coupling"]
    coupled = waves + mutual * (np.roll(waves, 1, axis=0) + np.roll(waves, -1, axis=0)) * 0.5
    # FM is integrated into phase (frequency deviation / modulator rate); PM is
    # a direct phase offset. Both are bounded and seed-phased.
    mod = np.mean(coupled, axis=0)
    mod_rate = max(0.03, rates[0])
    fm_phase = ((c["fm_depth"] / mod_rate) * np.sin(math.tau * mod_rate * t + phases[1])) if c.get("fm_enabled", True) else 0.0
    pm_phase = (c["pm_index"] * mod) if c.get("pm_enabled", True) else 0.0
    carrier_phase = math.tau * rates[0] * t + phases[0] + fm_phase + pm_phase
    field = np.sin(carrier_phase + mutual * (coupled[1] + coupled[2]) * 0.5)
    field = np.clip(field, -1.0, 1.0)
    trace = {"enabled": c["enabled"], "samples": n, "mutual_coupling": mutual,
             "residual_level": c["residual_level"], "am_depth": c["am_depth"],
             "fm_depth": c["fm_depth"], "pm_index": c["pm_index"],
             "composition_coupling": c["composition_coupling"],
             "field_rms": float(np.sqrt(np.mean(field * field))),
             "field_rate_hz": float(root), "seed_lane": "sha256-seed-derivation-v1"}
    return field.astype(np.float32), trace

def apply_to_mix(master, sample_rate, seed, bpm=120.0, config=None):
    """Bounded multiplicative residual AM; zero input remains exactly zero."""
    x = np.asarray(master, dtype=np.float32).ravel()
    c = normalized_config(config)
    if not c["enabled"] or x.size == 0 or (c["residual_level"] <= 0 and c["am_depth"] <= 0):
        return x, {"enabled": c["enabled"], "samples": int(x.size), "applied": False}
    field, trace = residual_field(x.size, sample_rate, seed, bpm, c)
    # GOAVA field controls the extant composition only: no independent tone is
    # added. Low default depth prevents blips and never creates sound from zero.
    depth = min(0.12, c["residual_level"] + (c["am_depth"] * c["composition_coupling"] if c.get("am_enabled", True) else 0.0))
    gain = 1.0 + depth * field
    y = (x.astype(np.float64) * gain.astype(np.float64)).astype(np.float32)
    if not np.all(np.isfinite(y)): y = np.nan_to_num(y, nan=0.0, posinf=1.0, neginf=-1.0).astype(np.float32)
    trace.update({"applied": True, "effective_am_depth": depth,
                  "input_rms": float(np.sqrt(np.mean(x.astype(np.float64)**2))) if x.size else 0.0,
                  "output_rms": float(np.sqrt(np.mean(y.astype(np.float64)**2))) if y.size else 0.0})
    return y, trace
