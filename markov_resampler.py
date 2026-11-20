"""Markov Resampler — sequence-level editor core (GROOVEBOX_R123_MARKOV_RESAMPLER_WINDOW_20261119).

Pure, Qt-free and deterministic. It turns a step sequence (steps / gates / amplitudes / pitches /
probabilities / offsets lanes) into a polynomial-weighted Markov chain whose states are step positions,
walks that chain with seed-derived sample coordinates (no ambient RNG), and returns the resampled
lanes plus a complete, replayable decision trace for every output step.

Model, in one line per term:
  * states        — the step positions of the selected sequence (all steps, or only the active ones);
  * base weight   — W(i→j) = decay(d) · (self weight if i = j) · (1 + Euclid bonus if d is on the Euclid
                    grid) · (1 + fractal bonus if d is a power of two), with d the (circular) state distance
                    between j and the expected next state i + advance (advance +1 = forward playback);
                    decay(d) = 1 / (1 + d^p) (power, p = locality) or M^(−p·d²) (Meum geometric, M = 1.19758…);
  * polynomial    — for destination j with lane value x_j ∈ [0, 1] and the current event's input value x:
                    P_j(x) = (1 − k)·f(x_j) + k·x_j·x, where f(y) = c0 + c1·y + c2·y² + c3·y³ is the
                    destination-preference curve and k the input coupling;
  * score         — W(i→j) · P_j(x); probabilities are scores normalised over the row;
  * decision      — first candidate whose cumulative probability exceeds u, u = SHA-256(seed, event, model)
                    mapped to [0, 1) (see polynomial_markov.PolynomialMarkovModel).

Canonical binding ("Follow canonicals"): the active canonicals adjust the model additively and every
adjustment is listed in the explanation —
  SEEDED     the chain seed is the project's canonical seed (custom seed text is ignored);
  RAND       the captured RAND instance token is appended to the seed (re-activation = new walk);
  LOCK       locality p += 2 · LOCK level (stronger step-to-step continuity);
  EUCLIDEAN  Euclid bonus ≥ EUCLIDEAN level (jumps on the n/pulses grid are preferred);
  GOAVA      decay switches to the Meum geometric law M^(−p·d²);
  FRACTAL    fractal bonus ≥ FRACTAL level (scale-invariant power-of-two jumps are preferred).
With no canonical active (or Follow off) the user's settings are used exactly as shown.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

from polynomial_markov import Polynomial, PolynomialMarkovModel

try:
    from meum_constants import MEUM
except Exception:  # pragma: no cover - meum_constants ships with the app
    MEUM = 1.1975807343385265

MARKER = "GROOVEBOX_R123_MARKOV_RESAMPLER_WINDOW_20261119"
LANES = ("steps", "gates", "amplitudes", "pitches", "probabilities", "offsets")
INPUT_LANES = ("amplitudes", "gates", "pitches", "probabilities", "offsets")
LANE_DEFAULTS = {"steps": False, "gates": False, "amplitudes": 1.0, "pitches": 1.0,
                 "probabilities": 100, "offsets": 0.0}
MAX_STEPS = 512

DEFAULT_SPEC: dict[str, Any] = {
    "version": 1,
    "states": "all_steps",          # all_steps | active_steps
    "input_lane": "amplitudes",
    "locality": 3.0,                # p ≥ 0
    "advance": 1,                   # expected move per output step: 1 forward, 0 hold, −1 reverse
    "self_weight": 1.0,             # multiplier on i→i, ≥ 0
    "wrap": True,                   # circular step distance
    "decay": "power",               # power | meum
    "euclid_bonus": 0.0,            # ≥ 0
    "euclid_pulses": 4,             # ≥ 1
    "fractal_bonus": 0.0,           # ≥ 0
    "coefficients": [0.25, 0.75, 0.0, 0.0],
    "coupling": 0.5,                # k ∈ [0, 1]
    "lanes": list(LANES),
    "seed_source": "canonical",     # canonical | custom
    "custom_seed": "",
    "follow_canonicals": True,
}

EXPLAIN = {
    "states": "Model states. 'All steps' makes every step position a state, so the walk may place any "
              "step's contents at any output position. 'Active steps only' keeps silent steps where they "
              "are and resamples only among the steps that play.",
    "input_lane": "Input lane. Its value at each step (normalised to 0…1) is both the destination "
                  "value x_j fed to the preference curve f and the current input x used by the coupling term.",
    "locality": "Locality p. Base weight falls with the distance d between a destination and the expected next "
                "state (current + advance) as 1/(1+d^p), or M^(−p·d²) in Meum mode. 0 = every jump equally likely; "
                "higher = the walk mostly follows the original order.",
    "advance": "Advance is the expected move per output step: +1 plays forward (high locality ≈ the original "
               "sequence), 0 holds/stutters around the current step, −1 plays backwards.",
    "self_weight": "Self weight multiplies the i→i transition. 0 forbids repeating a step immediately; "
                   "values above 1 favour repeats (stutter/hold).",
    "wrap": "Wrap measures distance around the loop (step 1 is next to the last step). Off = linear distance.",
    "decay": "Distance law. Power: 1/(1+d^p). Meum geometric: M^(−p·d²) with M = 1.19758…, the same "
             "ratio that spaces the Global Convolve lattice; GOAVA selects it automatically.",
    "euclid_bonus": "Euclid bonus adds (1+bonus) to jumps whose distance lies on the n/pulses grid, so "
                    "the walk prefers even rhythmic subdivisions. EUCLIDEAN raises it to its level.",
    "euclid_pulses": "Pulses defines the Euclid grid n/pulses used by the Euclid bonus.",
    "fractal_bonus": "Fractal bonus adds (1+bonus) to jumps of 1, 2, 4, 8 … steps (scale-invariant). "
                     "FRACTAL SEED raises it to its level.",
    "coefficients": "Preference curve f(y) = c0 + c1·y + c2·y² + c3·y³ over a destination's lane value y. "
                    "Rising curves favour loud/high steps, falling curves favour quiet/low ones; c0 keeps "
                    "every destination reachable. Values are clamped at 0.",
    "coupling": "Input coupling k blends the static preference with the current event: "
                "P_j(x) = (1−k)·f(x_j) + k·x_j·x. 0 = static, 1 = the current step's value decides.",
    "lanes": "Carried lanes. Checked lanes move with the selected source step; unchecked lanes stay as they "
             "were at each output position (e.g. resample rhythm but keep the pitch line).",
    "seed_source": "Seed. Canonical uses the project seed + instrument + sequence, so the same project always "
                   "gives the same walk. Custom uses your text verbatim.",
    "follow_canonicals": "Follow canonicals. Active SEEDED/RAND/LOCK/EUCLIDEAN/GOAVA/FRACTAL engines adjust "
                         "the model as listed in the canonical summary; off = your settings exactly.",
}


def normalize_spec(spec: dict | None) -> dict:
    out = copy.deepcopy(DEFAULT_SPEC)
    for key, value in dict(spec or {}).items():
        if key in out:
            out[key] = copy.deepcopy(value)
    out["states"] = out["states"] if out["states"] in ("all_steps", "active_steps") else "all_steps"
    out["input_lane"] = out["input_lane"] if out["input_lane"] in INPUT_LANES else "amplitudes"
    out["decay"] = out["decay"] if out["decay"] in ("power", "meum") else "power"
    out["seed_source"] = out["seed_source"] if out["seed_source"] in ("canonical", "custom") else "canonical"

    def _f(key, lo, hi, default):
        try:
            v = float(out[key])
        except (TypeError, ValueError):
            v = default
        if not math.isfinite(v):
            v = default
        out[key] = min(hi, max(lo, v))
    _f("locality", 0.0, 16.0, 3.0)
    _f("self_weight", 0.0, 16.0, 1.0)
    try:
        out["advance"] = max(-1, min(1, int(out["advance"])))
    except (TypeError, ValueError):
        out["advance"] = 1
    _f("euclid_bonus", 0.0, 16.0, 0.0)
    _f("fractal_bonus", 0.0, 16.0, 0.0)
    _f("coupling", 0.0, 1.0, 0.5)
    try:
        out["euclid_pulses"] = max(1, min(MAX_STEPS, int(out["euclid_pulses"])))
    except (TypeError, ValueError):
        out["euclid_pulses"] = 4
    coeffs = list(out.get("coefficients") or [])[:4]
    coeffs = [float(c) if isinstance(c, (int, float)) and math.isfinite(float(c)) else 0.0 for c in coeffs]
    out["coefficients"] = (coeffs + [0.0] * 4)[:4]
    out["lanes"] = [l for l in LANES if l in set(out.get("lanes") or [])]
    out["wrap"] = bool(out["wrap"])
    out["follow_canonicals"] = bool(out["follow_canonicals"])
    out["custom_seed"] = str(out.get("custom_seed") or "")
    return out


def lanes_from_mem(mem: dict) -> dict:
    """Equal-length copies of the six step lanes (missing values take their neutral defaults)."""
    steps = list((mem or {}).get("steps") or [])
    try:
        n = int((mem or {}).get("pattern_length") or len(steps) or 16)
    except (TypeError, ValueError):
        n = len(steps) or 16
    n = max(1, min(MAX_STEPS, n))
    out = {}
    for lane in LANES:
        src = list((mem or {}).get(lane) or [])
        if lane == "gates" and not src:
            src = list(steps)
        vals = (src + [LANE_DEFAULTS[lane]] * n)[:n]
        out[lane] = [bool(v) for v in vals] if lane in ("steps", "gates") else list(vals)
    return out


def lane_value(lanes: dict, lane: str, i: int) -> float:
    """Normalised 0…1 value of one lane at step i."""
    v = lanes.get(lane, [])[i] if i < len(lanes.get(lane, [])) else LANE_DEFAULTS.get(lane, 0.0)
    try:
        if lane == "gates":
            x = 1.0 if bool(v) and bool(lanes["steps"][i]) else 0.0
        elif lane == "amplitudes":
            x = float(v) if bool(lanes["steps"][i]) else 0.0
        elif lane == "pitches":
            x = 0.5 + 0.5 * math.log2(max(1e-6, float(v)))        # ±1 octave → 0…1
        elif lane == "probabilities":
            x = float(v) / 100.0
        else:  # offsets, −0.5…0.5 beats → 0…1
            x = float(v) + 0.5
    except (TypeError, ValueError, KeyError):
        x = 0.0
    return min(1.0, max(0.0, x)) if math.isfinite(x) else 0.0


def canonical_adjust(spec: dict, active=(), levels: dict | None = None) -> tuple[dict, list[str]]:
    """Effective spec under the active canonicals, plus one explanation line per adjustment."""
    eff = normalize_spec(spec)
    notes: list[str] = []
    if not eff["follow_canonicals"]:
        return eff, ["Follow canonicals is off — the model uses your settings exactly."]
    active = {str(a) for a in (active or ())}
    levels = dict(levels or {})
    if not active:
        return eff, ["No canonical engine is active — the model uses your settings exactly."]

    def lv(key, default=1.0):
        try:
            return max(0.0, min(1.0, float(levels.get(key, default))))
        except (TypeError, ValueError):
            return default
    if "seeded" in active:
        eff["seed_source"] = "canonical"
        notes.append("SEEDED: the chain seed is the project's canonical seed (custom seed ignored).")
    if "randomizer" in active:
        notes.append("RAND: the captured RAND instance token joins the seed — re-activating RAND gives a new walk.")
    if "phase_lock" in active:
        add = 2.0 * lv("phase_lock", 0.5)
        eff["locality"] = min(16.0, eff["locality"] + add)
        notes.append(f"LOCK: locality p += 2 × level = +{add:.3g} → p = {eff['locality']:.3g} (stronger continuity).")
    if "euclidean" in active:
        eff["euclid_bonus"] = max(eff["euclid_bonus"], lv("euclidean"))
        notes.append(f"EUCLIDEAN: Euclid bonus ≥ level → {eff['euclid_bonus']:.3g} on the n/{eff['euclid_pulses']} grid.")
    if "goava" in active:
        eff["decay"] = "meum"
        notes.append("GOAVA: distance law = Meum geometric M^(−p·d²), M = 1.19758…")
    if "fractal_seed" in active:
        eff["fractal_bonus"] = max(eff["fractal_bonus"], lv("fractal_seed"))
        notes.append(f"FRACTAL: fractal bonus ≥ level → {eff['fractal_bonus']:.3g} on 1, 2, 4, 8 … step jumps.")
    return eff, notes


def chain_seed(spec: dict, *, numeric_seed: Any = 0, instrument: str = "", sequence: int = 1,
               rand_token: Any = None, active=()) -> str:
    """Deterministic seed text for the walk."""
    if spec.get("seed_source") == "custom" and spec.get("custom_seed") and "seeded" not in set(active or ()):
        base = str(spec["custom_seed"])
    else:
        base = f"{numeric_seed}|{instrument}|{int(sequence)}|markov-resampler"
    if "randomizer" in set(active or ()) and rand_token not in (None, ""):
        base += f"|rand:{rand_token}"
    return base


def _distance(i: int, j: int, n: int, wrap: bool) -> int:
    d = abs(i - j)
    return min(d, n - d) if wrap and n > 0 else d


def base_weight(i: int, j: int, n: int, spec: dict) -> float:
    """Base weight from state index i to state index j among n states (distance from i + advance)."""
    target = i + int(spec.get("advance", 1))
    if spec["wrap"]:
        target %= n
    else:
        target = min(n - 1, max(0, target))
    d = _distance(target, j, n, spec["wrap"])
    p = float(spec["locality"])
    w = (MEUM ** (-p * d * d)) if spec["decay"] == "meum" else 1.0 / (1.0 + float(d) ** p)
    if i == j:
        w *= float(spec["self_weight"])
    if d and spec["euclid_bonus"] > 0:          # d ≠ 0: a jump away from the expected next state
        grid = n / float(spec["euclid_pulses"])
        if grid < 1.0 or abs(d / grid - round(d / grid)) < 1e-9:
            w *= 1.0 + float(spec["euclid_bonus"])
    if d and spec["fractal_bonus"] > 0 and (d & (d - 1)) == 0:
        w *= 1.0 + float(spec["fractal_bonus"])
    return w


def state_positions(lanes: dict, spec: dict) -> list[int]:
    n = len(lanes["steps"])
    if spec["states"] == "active_steps":
        pos = [i for i in range(n) if lanes["steps"][i]]
        return pos if len(pos) >= 2 else []
    return list(range(n))


def transition_matrix(lanes: dict, spec: dict) -> tuple[list[int], list[list[float]]]:
    """Row-normalised base transition matrix (before the polynomial) over the state positions."""
    pos = state_positions(lanes, spec)
    m = len(pos)
    rows = []
    for a in range(m):
        row = [base_weight(a, b, m, spec) for b in range(m)]
        s = sum(row) or 1.0
        rows.append([v / s for v in row])
    return pos, rows


def preference(spec: dict, y: float) -> float:
    c0, c1, c2, c3 = spec["coefficients"]
    return max(0.0, c0 + y * (c1 + y * (c2 + y * c3)))


def build_model(lanes: dict, spec: dict) -> tuple[PolynomialMarkovModel, list[int]]:
    pos = state_positions(lanes, spec)
    if len(pos) < 2:
        raise ValueError("the Markov Resampler needs at least two states (two steps, or two active steps)")
    m = len(pos)
    states = tuple(f"step:{i}" for i in pos)
    lane = spec["input_lane"]
    k = float(spec["coupling"])
    transition, weights = {}, {}
    for a, i in enumerate(pos):
        row = {}
        raw = [base_weight(a, b, m, spec) for b in range(m)]
        top = max(raw) or 1.0
        for b, j in enumerate(pos):
            if raw[b] > top * 1e-9:            # negligible far jumps are dropped (keeps 512-step models fast)
                row[states[b]] = raw[b]
        transition[states[a]] = row
    for b, j in enumerate(pos):
        y = lane_value(lanes, lane, j)
        weights[states[b]] = Polynomial(f"pref-step-{j}", ((1.0 - k) * preference(spec, y), k * y),
                                        domain=(0.0, 1.0), clamp=(0.0, 1.0e6))
    digest = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]
    return PolynomialMarkovModel(f"markov-resampler-{digest}", states, transition, weights, model_version="1"), pos


def resample(mem: dict, spec: dict | None = None, *, seed: str = "0") -> dict:
    """Walk the chain once per output position; returns before/after lanes and the full trace."""
    spec = normalize_spec(spec)
    lanes = lanes_from_mem(mem)
    model, pos = build_model(lanes, spec)
    lane = spec["input_lane"]
    events = [{"event_id": f"step-{i}", "value": lane_value(lanes, lane, i), "output_step": i} for i in pos]
    # Start "before" the first state so that advance = +1 lands on it first (−1 / 0: start on it).
    first = pos[-1] if (spec["advance"] == 1 and spec["wrap"]) else pos[0]
    traces = model.rearrange(events, seed=seed, initial_state=f"step:{first}")
    sources = [int(t["selected_state"].split(":", 1)[1]) for t in traces]
    after = copy.deepcopy(lanes)
    carried = set(spec["lanes"])
    for out_i, src_i in zip(pos, sources):
        for ln in carried:
            after[ln][out_i] = copy.deepcopy(lanes[ln][src_i])
    return {"marker": MARKER, "spec": spec, "seed": str(seed), "positions": pos, "sources": sources,
            "before": lanes, "after": after, "traces": traces, "model_id": model.model_id,
            "model_fingerprint": model.fingerprint(),
            "changed_steps": sum(1 for o, s in zip(pos, sources) if o != s)}


def apply_to_mem(mem: dict, result: dict) -> dict:
    """Write the resampled lanes into a sequence memory (user-owned edit)."""
    after = result["after"]
    n = len(after["steps"])
    for ln in result["spec"]["lanes"]:
        mem[ln] = copy.deepcopy(after[ln])
    mem["pattern_length"] = n
    mem["user_owned"] = True
    mem["user_touched_steps"] = [True] * n
    mem["markov_resampler_last"] = {"seed": result["seed"], "model_fingerprint": result["model_fingerprint"],
                                    "sources": list(result["sources"]), "positions": list(result["positions"])}
    return mem


def explain_trace(trace: dict, top: int = 8) -> str:
    cands = sorted(trace.get("transition_candidates", []), key=lambda c: -c["probability"])[:top]
    lines = [f"Output {trace['event_id']}: from {trace['source_state']} → {trace['selected_state']}",
             f"u = {trace['sample_coordinate']:.6f} (SHA-256 of seed/event/model; rule: {trace['selection_rule']})",
             f"Why: {trace['attribution']}", "Top candidates (probability · base weight × P_j(x)):"]
    for c in cands:
        lines.append(f"  {c['state']:<9} p={c['probability']:.4f}  W={c['base_weight']:.4g} × "
                     f"P={c['polynomial_value']:.4g}  [{c['polynomial']}]")
    return "\n".join(lines)
