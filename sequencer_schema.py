"""Versioned compatibility helpers for Groovebox STEP and automation data."""
from __future__ import annotations
import copy, math

SEQUENCER_SCHEMA_VERSION = 2
STEP_LANES = {
    "phase_shift": 0.0,
    "eq_gain_db": 0.0,
    "eq_frequency": 1000.0,
    "eq_q": 0.707,
    "sidechain_depth": 0.0,
    "phase_mod_depth": 0.0,
    "trigger_probability": 1.0,
}
# Phase Propagation Mode: per-step choice of how the oscillator phase accumulator
# behaves at step boundaries.  Not a modulation source; pure state propagation.
# "retrigger"  — reset phase to the voice phase0 / seed lattice at step start
# "longitudinal" — continue the phase accumulator from the previous step's end
PHASE_PROPAGATION_MODES = ("retrigger", "longitudinal")
PHASE_PROPAGATION_DEFAULT = "retrigger"

def _finite(value, fallback):
    try:
        value = float(value)
        return value if math.isfinite(value) else float(fallback)
    except (TypeError, ValueError, OverflowError):
        return float(fallback)

def normalize_sequence_memory(memory, target_length=None):
    """Return a deep-copied, schema-v2 sequence with aligned per-step control lanes.

    Legacy top-level lane arrays and nested ``step_controls``/``automation`` lanes
    are accepted. Existing values are retained; missing positions use neutral values.
    Unknown keys and engine ownership metadata pass through untouched.
    """
    out = copy.deepcopy(memory) if isinstance(memory, dict) else {}
    length = target_length
    if length is None:
        try: length = int(out.get("pattern_length", 0) or 0)
        except (TypeError, ValueError): length = 0
    if not length:
        for key in ("steps", "gates", "amplitudes", "pitches", "probabilities", "offsets"):
            if isinstance(out.get(key), list) and out[key]:
                length = len(out[key]); break
    try: length = max(1, min(512, int(length or 16)))
    except (TypeError, ValueError): length = 16
    out["pattern_length"] = length
    lanes = out.get("step_controls")
    lanes = copy.deepcopy(lanes) if isinstance(lanes, dict) else {}
    legacy_auto = out.get("automation") if isinstance(out.get("automation"), dict) else {}
    for key, default in STEP_LANES.items():
        candidates = [(lanes.get(key), "lane"), (out.get(key), "top"), (legacy_auto.get(key), "automation")]
        if key == "trigger_probability":
            candidates.append((out.get("probabilities"), "legacy_percent"))
        chosen = next(((v, source) for v, source in candidates if isinstance(v, list)), (None, "default"))
        values, source = chosen
        if values is not None and source == "legacy_percent":
            clean = [_finite(v, 100.0) / 100.0 for v in values[:length]]
        else:
            clean = [_finite(v, default) for v in (values[:length] if values is not None else [])]
        if len(clean) < length: clean.extend([float(default)] * (length-len(clean)))
        lanes[key] = clean
        # Preserve a legacy top-level lane if it already existed; don't create
        # duplicate authorities for older project files.
        if isinstance(out.get(key), list): out[key] = list(clean)
    # Phase Propagation Mode lane (string enum, not a float control).
    # Default preserves the named existing behavior (retrigger at step start).
    _pp_raw = lanes.get("phase_propagation")
    if not isinstance(_pp_raw, list):
        _pp_raw = out.get("phase_propagation") if isinstance(out.get("phase_propagation"), list) else []
    _pp_clean = []
    for v in (_pp_raw or [])[:length]:
        s = str(v).strip().lower() if v is not None else ""
        _pp_clean.append(s if s in PHASE_PROPAGATION_MODES else PHASE_PROPAGATION_DEFAULT)
    while len(_pp_clean) < length:
        _pp_clean.append(PHASE_PROPAGATION_DEFAULT)
    lanes["phase_propagation"] = _pp_clean
    out["step_controls"] = lanes
    out["sequencer_schema_version"] = SEQUENCER_SCHEMA_VERSION
    return out

def normalize_sequence_bank(bank):
    """Normalize each sequence in a bank, preserving string/int sequence IDs."""
    if not isinstance(bank, dict): return {}
    result = {}
    for key, value in bank.items():
        if isinstance(value, dict): result[key] = normalize_sequence_memory(value)
    return result

def lane_values_from_events(pattern, lane_defaults=None):
    """Project math-lab events into aligned STEP automation arrays."""
    params = pattern.get("parameters", {}) if isinstance(pattern, dict) else {}
    length = max(1, min(512, int(params.get("steps", 16) or 16)))
    lanes = {k: [float(v)] * length for k, v in STEP_LANES.items()}
    overrides = lane_defaults if isinstance(lane_defaults, dict) else {}
    for key, default in STEP_LANES.items():
        try: value = float(overrides.get(key, default))
        except (TypeError, ValueError): value = float(default)
        if not math.isfinite(value): value = float(default)
        lanes[key] = [value] * length
    # Events may carry explicit automation. Multiple events on a STEP resolve
    # deterministically in source order, with the last explicit value winning.
    for event in (pattern.get("events", []) if isinstance(pattern, dict) else []):
        if not isinstance(event, dict): continue
        try: idx = int(event.get("step", 1)) - 1
        except (TypeError, ValueError): continue
        if not 0 <= idx < length: continue
        controls = event.get("step_controls", event.get("automation", {}))
        if not isinstance(controls, dict): continue
        for key in STEP_LANES:
            if key in controls: lanes[key][idx] = _finite(controls[key], STEP_LANES[key])
    return lanes


def reconcile_sequence_state(active_memory, sequence_banks, selected_sequences):
    """Return mutually consistent active memory, banks, and selected IDs.

    The active edit buffer is authoritative for the selected bank slot on save;
    on load, this reconstructs that same relationship so edits cannot disappear
    merely because JSON decoded two copies of a formerly shared dictionary.
    """
    active_in = active_memory if isinstance(active_memory, dict) else {}
    banks_in = sequence_banks if isinstance(sequence_banks, dict) else {}
    selected_in = selected_sequences if isinstance(selected_sequences, dict) else {}
    active = {str(name): normalize_sequence_memory(mem) for name, mem in active_in.items() if isinstance(mem, dict)}
    banks = {}
    selected = {}
    names = set(active) | {str(k) for k in banks_in}
    for name in sorted(names):
        raw_bank = banks_in.get(name, {})
        bank = {}
        if isinstance(raw_bank, dict):
            for key, mem in raw_bank.items():
                if not isinstance(mem, dict): continue
                try: sid = str(int(key))
                except (TypeError, ValueError): sid = str(key)
                bank[sid] = normalize_sequence_memory(mem)
        raw_sid = selected_in.get(name, selected_in.get(str(name), 1))
        try: sid = str(int(raw_sid))
        except (TypeError, ValueError): sid = str(raw_sid)
        if not bank and name in active:
            bank[sid] = copy.deepcopy(active[name])
        if sid not in bank and bank:
            numeric = sorted((int(k), k) for k in bank if str(k).lstrip("-").isdigit())
            sid = numeric[0][1] if numeric else sorted(bank)[0]
        if name in active and sid in bank:
            bank[sid] = copy.deepcopy(active[name])
        elif sid in bank:
            active[name] = copy.deepcopy(bank[sid])
        elif name in active:
            bank[sid] = copy.deepcopy(active[name])
        if sid in bank:
            active[name] = bank[sid]
        banks[name] = bank
        try: selected[name] = int(sid)
        except (TypeError, ValueError): selected[name] = sid
    return active, banks, selected
