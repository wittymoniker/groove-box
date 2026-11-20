"""GROOVEBOX_R124_CONSTRAINT_COMPOSER: rule-driven sequence writer (one randomizer, many rules).

Rules (all optional):
    key        root pitch class 0..11 + scale name (major, minor, dorian, … just, pentatonic, chromatic)
    ratios     a just-intonation ratio set; pitches are snapped to the nearest ratio (any octave)
    density    fraction of active steps 0..1
    entropy    target Shannon entropy (bits) of the pitch-class distribution
    range      lowest/highest pitch (in the sequence's own unit)
    max_leap   largest step-to-step interval
Candidates are drawn from a seeded RNG and accepted only when every rule holds (score = 0), so the
output is deterministic for (rules, seed) and always satisfies the constraints it reports.

Pitch units are detected from the existing sequence: semitone offsets (−48..48), MIDI (0..127) or Hz.
"""
from __future__ import annotations

import math
import random

SCALES = {
    "chromatic": list(range(12)), "major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10], "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10], "locrian": [0, 1, 3, 5, 6, 8, 10],
    "pentatonic": [0, 2, 4, 7, 9], "minor_pentatonic": [0, 3, 5, 7, 10], "whole_tone": [0, 2, 4, 6, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
}
JUST_RATIOS = {"5-limit": [1, 16/15, 9/8, 6/5, 5/4, 4/3, 45/32, 3/2, 8/5, 5/3, 9/5, 15/8],
               "7-limit": [1, 8/7, 7/6, 6/5, 5/4, 4/3, 7/5, 3/2, 8/5, 5/3, 7/4, 15/8],
               "pythagorean": [1, 256/243, 9/8, 32/27, 81/64, 4/3, 729/512, 3/2, 128/81, 27/16, 16/9, 243/128]}
DEFAULT_RULES = {"key_root": 0, "scale": "minor", "ratios": None, "density": 0.5, "entropy": 2.0,
                 "entropy_tol": 0.35, "range": None, "max_leap": 7, "length": 16}


def detect_unit(pitches):
    vals = [float(p) for p in (pitches or []) if isinstance(p, (int, float))]
    if not vals:
        return "semitone"
    if max(vals) > 140.0:
        return "hz"
    if min(vals) >= 0.0 and max(vals) > 48.0:
        return "midi"
    return "semitone"


def to_semis(p, unit, ref_hz=261.6255653):
    if unit == "hz":
        return 12.0 * math.log2(max(1e-6, float(p)) / ref_hz)
    if unit == "midi":
        return float(p) - 60.0
    return float(p)


def from_semis(s, unit, ref_hz=261.6255653):
    if unit == "hz":
        return round(ref_hz * 2.0 ** (s / 12.0), 4)
    if unit == "midi":
        return int(round(s + 60.0))
    return round(s, 4) if abs(s - round(s)) > 1e-9 else int(round(s))


def _allowed_semis(rules, lo=-24, hi=24):
    if rules.get("ratios"):
        rs = JUST_RATIOS.get(rules["ratios"], rules["ratios"])
        base = [12.0 * math.log2(float(r)) for r in rs]
        root = int(rules.get("key_root", 0))
        out = sorted({round(root + b + 12 * o, 4) for o in range(-3, 4) for b in base})
    else:
        sc = SCALES.get(rules.get("scale", "chromatic"), SCALES["chromatic"])
        root = int(rules.get("key_root", 0))
        out = [n for n in range(lo - 12, hi + 13) if (n - root) % 12 in sc]
    return [x for x in out if lo <= x <= hi]


def entropy_bits(semis):
    if not semis:
        return 0.0
    counts = {}
    for s in semis:
        k = int(round(s)) % 12
        counts[k] = counts.get(k, 0) + 1
    n = float(len(semis))
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def check(seq_semis, steps, rules):
    """List of violated rules (empty = all satisfied)."""
    bad = []
    allowed = set(round(a, 4) for a in _allowed_semis(rules, -60, 60))
    act = [s for s, on in zip(seq_semis, steps) if on]
    if any(round(s, 4) not in allowed for s in act):
        bad.append("key/ratios")
    if rules.get("density") is not None and steps:
        d = sum(1 for x in steps if x) / float(len(steps))
        if abs(d - float(rules["density"])) > 0.5 / len(steps) + 1e-9:
            bad.append("density")
    if rules.get("entropy") is not None and len(act) >= 2:
        if abs(entropy_bits(act) - float(rules["entropy"])) > float(rules.get("entropy_tol", 0.35)):
            bad.append("entropy")
    if rules.get("max_leap") is not None:
        for a, b in zip(act, act[1:]):
            if abs(b - a) > float(rules["max_leap"]) + 1e-9:
                bad.append("max_leap"); break
    if rules.get("range"):
        lo, hi = rules["range"]
        if any(s < lo or s > hi for s in act):
            bad.append("range")
    return bad


def compose(rules=None, seed=0, tries=4000):
    """Return {"steps", "pitches_semis", "violations", "tries"} satisfying the rules if possible."""
    r = dict(DEFAULT_RULES); r.update(rules or {})
    n = int(r.get("length", 16))
    rng = random.Random(f"constraint:{seed}:{sorted((k, str(v)) for k, v in r.items())}")
    lo, hi = (r["range"] if r.get("range") else (-12, 12))
    pool = _allowed_semis(r, int(math.floor(lo)), int(math.ceil(hi))) or [0]
    k_on = max(1 if (r.get("density") or 0) > 0 else 0, int(round(float(r.get("density", 0.5)) * n)))
    best = None
    for t in range(1, tries + 1):
        on_idx = set(rng.sample(range(n), min(n, k_on)))
        steps = [1 if i in on_idx else 0 for i in range(n)]
        # pitch-class palette size from the entropy target (2^H classes, roughly uniform)
        h = float(r.get("entropy") or 2.0)
        classes = max(1, min(len(pool), int(round(2 ** h))))
        palette = rng.sample(pool, classes) if classes < len(pool) else list(pool)
        cur = rng.choice(palette); seq = []
        for i in range(n):
            if steps[i]:
                near = [p for p in palette if r.get("max_leap") is None or abs(p - cur) <= float(r["max_leap"])] or [cur]
                cur = rng.choice(near)
            seq.append(cur)
        bad = check(seq, steps, r)
        if best is None or len(bad) < len(best["violations"]):
            best = {"steps": steps, "pitches_semis": seq, "violations": bad, "tries": t}
        if not bad:
            break
    return best


def apply_to_sequence(seq, rules=None, seed=0):
    """Write a composed pattern into a sequence dict (steps / pitches / amplitudes), keeping its unit."""
    unit = detect_unit(seq.get("pitches"))
    r = dict(rules or {})
    r.setdefault("length", int(seq.get("pattern_length") or len(seq.get("steps") or []) or 16))
    out = compose(r, seed)
    seq["steps"] = list(out["steps"])
    seq["pitches"] = [from_semis(s, unit) for s in out["pitches_semis"]]
    amps = list(seq.get("amplitudes") or [])
    seq["amplitudes"] = [(amps[i] if i < len(amps) and amps[i] else 0.8) for i in range(len(out["steps"]))]
    seq["pattern_length"] = len(out["steps"])
    seq["constraint_rules"] = {k: v for k, v in r.items()}
    return out


def apply_to_selected(app, rules=None, seed=None):
    try:
        import panel_synth_deck as psd
        name = psd._name(app)
        bank = (getattr(app, "instrument_sequence_banks", {}) or {}).get(name) or {}
        idx = getattr(app, "current_sequence_index", None)
        if idx not in bank:
            idx = sorted(bank)[0] if bank else None
        if idx is None:
            return None
        if seed is None:
            seed = hash((name, idx)) & 0xFFFFFFFF
        out = apply_to_sequence(bank[idx], rules, seed)
        for m in ("_refresh_sequencer_from_bank", "refresh_sequencer_ui", "_refresh_all_sequence_views"):
            fn = getattr(app, m, None)
            if callable(fn):
                try:
                    fn(); break
                except Exception:
                    pass
        return out
    except Exception as exc:
        print(f"[constraint composer] {exc}")
        return None
