"""GROOVEBOX_R23R_MULTIDIM_SYNTH_20261103 — the multidimensional synth (third member of every voice).

    inner = (1 - g) · panel synth + g · four geometric synths       (g = geometric / panel balance)
    voice = (1 - w) · inner       + w · MULTIDIMENSIONAL SYNTH      (w = 33 … 66 %, default 50 %)

ONE synth that is a wavetable, a vector, a bouncing ball and a cellular automaton at once:

  WAVETABLE  dimension — a harmonic table (H partials) whose amplitudes come from the preset's
             SCRIPT (an expression in k, the partial number: "1/k", "(k % 2)/k", …).
  CELLULAR   dimension — an elementary CA (rule 0–255) with one cell per partial; it evolves one
             generation per block and gates which partials sound (the "structure" face).
  BALL       dimension — a bouncing ball (gravity, restitution) whose height h moves pitch and level
             (patch: ball→pitch, ball→amp) and re-launches when it comes to rest.
  VECTOR     dimension — a rotating 3-D direction (x, y, z) that turns the phase (vector→phase) and
             feeds the domain equation.

It runs on its own basic conditionals of AMPLITUDE, and thereby frequency and phase: its block
amplitude a (of what it just played) decides the next block —
     a > hi : frequency × up,   phase + shift        a < lo : frequency × down, phase − shift.

The DOMAIN EQUATION (expression in t, b, h, a, x, y, z, live) gives, per block, how much of the
CA-gated structure (1) versus the full table (0) sounds. The MODULAR PATCH routes the dimensions
(ball→pitch, ball→amp, vector→phase, amp→freq, amp→phase, ca→harmonics). The HARMONIC-GEOMETRIC
STRUCTURAL RULE designates FIXED RESONATORS: frequencies fixed to the project's base frequency
(harmonic / platonic / fibonacci / triangular / square / golden numbers) — they ring the same
whatever note is played.

Presets bundle all of this (script · domain · patch · resonator rule · CA rule · ball · vector ·
conditionals). Canonically programmable: an instrument without user parameters gets a canonical
programme (preset + parameters chosen from the seed and its slot); every key the user sets
overrides only that key. Scripts and domain equations run with OT division (ot_script_math).
"""
from __future__ import annotations

import hashlib
import importlib
import math

import numpy as np

# GROOVEBOX_R32_CANONICAL_100_20261109: the canonical programme may own the whole voice (0 … 100 %,
# default 100 %).  The old 33 … 66 % clamp kept half of every voice identical across seeds.
MIX_MIN, MIX_MAX, MIX_DEFAULT = 0.0, 1.0, 1.0
H = 12                                 # partials in the table (= CA cells)

RESONATOR_RULES = {
    "harmonic":   (1.0, 2.0, 3.0, 4.0, 5.0),
    "platonic":   (1.0, 1.5, 2.0, 3.0, 5.0),        # face counts 4, 6, 8, 12, 20 ÷ 4
    "fibonacci":  (1.0, 2.0, 3.0, 5.0, 8.0),
    "triangular": (1.0, 3.0, 6.0, 10.0, 15.0),
    "square":     (1.0, 4.0, 9.0, 16.0, 25.0),
    "golden":     (1.0, 1.618033988749895, 2.618033988749895, 4.23606797749979, 6.854101966249685),
    "none":       (),
}

PATCH_KEYS = ("ball->pitch", "ball->amp", "vector->phase", "amp->freq", "amp->phase", "ca->harmonics",
              # pathways IN from the main (Edit Synth panel) synth — its envelope drives this synth
              "main->freq", "main->phase", "main->amp",
              # pathways OUT to the main synth and the geometric synths
              "->main.amp", "->main.ring", "->geo.amp")
PATHWAY_KEYS = PATCH_KEYS[6:]

# Canonical-moderated global cross-modulation bindings. Sources are normalized
# block-rate control signals; targets are synth dimensions, not widgets.
XMOD_SOURCES = (
    "main_envelope", "ball_height", "vector_x", "vector_y", "vector_z",
    "cellular_density", "previous_amplitude", "domain_weight",
)
XMOD_TARGETS = (
    "pitch", "phase", "script_spectrum", "harmonics", "domain",
    "resonance", "synth_level",
)


def canonical_xmod_bindings(engines=()):
    eng = {str(e).lower() for e in (engines or ())}
    out = []
    def add(engine, routes):
        if engine in eng:
            out.extend({"source": s, "target": t, "amount": float(a), "owner": "canonical"}
                       for s, t, a in routes)
    add("goava", (("main_envelope", "script_spectrum", .16), ("main_envelope", "domain", .10),
                   ("vector_z", "phase", .06), ("main_envelope", "synth_level", .035)))
    add("euclidean", (("cellular_density", "domain", .15), ("cellular_density", "harmonics", .16),
                       ("domain_weight", "resonance", .06), ("cellular_density", "script_spectrum", .05)))
    add("phase_lock", (("vector_x", "pitch", .10), ("vector_y", "phase", .15),
                        ("vector_z", "domain", .06), ("vector_x", "synth_level", .035)))
    if eng & {"randomizer", "seeded", "seeded_randomizer", "random"}:
        out.extend(({"source": "ball_height", "target": "pitch", "amount": .14, "owner": "canonical"},
                    {"source": "ball_height", "target": "synth_level", "amount": .07, "owner": "canonical"},
                    {"source": "previous_amplitude", "target": "resonance", "amount": .06, "owner": "canonical"}))
    if eng & {"fractal_seed", "fractal"}:
        out.extend(({"source": "cellular_density", "target": "script_spectrum", "amount": .14, "owner": "canonical"},
                    {"source": "cellular_density", "target": "harmonics", "amount": .10, "owner": "canonical"},
                    {"source": "domain_weight", "target": "resonance", "amount": .05, "owner": "canonical"},
                    {"source": "previous_amplitude", "target": "phase", "amount": .04, "owner": "canonical"}))
    return out


def _clean_xmod_bindings(items):
    out = []
    for item in items or ():
        if not isinstance(item, dict):
            continue
        source, target = str(item.get("source", "")), str(item.get("target", ""))
        if source not in XMOD_SOURCES or target not in XMOD_TARGETS:
            continue
        try:
            amount = float(item.get("amount", 0.0))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(amount):
            continue
        out.append({"source": source, "target": target, "amount": float(np.clip(amount, -1.0, 1.0)),
                    "owner": str(item.get("owner", "user"))})
        if len(out) >= 32:
            break
    return out


def _merge_xmod_bindings(canonical, user, share, canonical_active):
    canonical = _clean_xmod_bindings(canonical if canonical_active else ())
    user = _clean_xmod_bindings(user)
    merged = {}
    for route in canonical:
        key = (route["source"], route["target"])
        merged[key] = {**route, "amount": route["amount"]}
    for route in user:
        key = (route["source"], route["target"])
        if key in merged and canonical_active:
            merged[key]["amount"] = _blend_num(route["amount"], merged[key]["amount"], share)
            merged[key]["owner"] = "canonical+user"
        else:
            merged[key] = {**route, "amount": route["amount"] * (1.0 - share if canonical_active else 1.0)}
    return [v for v in merged.values() if abs(float(v["amount"])) > 1e-8]

PRESETS = {
    "Prism": {"script": "1/k", "domain": "0.5 + 0.5*z", "ca_rule": 90, "resonators": "harmonic",
              "patch": {"ball->pitch": 0.0, "ball->amp": 0.3, "vector->phase": 0.5, "amp->freq": 1.0,
                        "amp->phase": 1.0, "ca->harmonics": 1.0},
              "gravity": 9.0, "restitution": 0.8, "vector": [0.6, 0.3, 0.7], "rot_hz": 0.12,
              "lo": 0.22, "hi": 0.72, "up": 1.5, "down": 0.75, "phase_shift": 1.5707963, "block_ms": 12.0,
              "res_q": 30.0, "res_mix": 0.25},
    "Crystal": {"script": "(k % 2)/k", "domain": "1 if h > 0.5 else 0.2", "ca_rule": 150, "resonators": "platonic",
                "patch": {"ball->pitch": 0.08, "ball->amp": 0.5, "vector->phase": 0.2, "amp->freq": 1.0,
                          "amp->phase": 0.5, "ca->harmonics": 1.0},
                "gravity": 14.0, "restitution": 0.9, "vector": [0.2, 0.9, 0.3], "rot_hz": 0.07,
                "lo": 0.18, "hi": 0.66, "up": 2.0, "down": 0.5, "phase_shift": 0.7853982, "block_ms": 24.0,
                "res_q": 60.0, "res_mix": 0.4},
    "Golden spiral": {"script": "1/(k**0.618)", "domain": "abs(x)", "ca_rule": 30, "resonators": "golden",
                      "patch": {"ball->pitch": 0.0, "ball->amp": 0.2, "vector->phase": 1.0, "amp->freq": 0.5,
                                "amp->phase": 1.0, "ca->harmonics": 0.6},
                      "gravity": 6.0, "restitution": 0.7, "vector": [0.9, 0.1, 0.4], "rot_hz": 0.21,
                      "lo": 0.25, "hi": 0.7, "up": 1.25, "down": 0.8, "phase_shift": 2.0943951, "block_ms": 6.0,
                      "res_q": 25.0, "res_mix": 0.3},
    "Cellular choir": {"script": "1/k if k < 8 else 0.5/k", "domain": "live", "ca_rule": 110, "resonators": "triangular",
                       "patch": {"ball->pitch": 0.0, "ball->amp": 0.0, "vector->phase": 0.3, "amp->freq": 1.0,
                                 "amp->phase": 1.0, "ca->harmonics": 1.0},
                       "gravity": 9.8, "restitution": 0.75, "vector": [0.5, 0.5, 0.5], "rot_hz": 0.1,
                       "lo": 0.2, "hi": 0.68, "up": 1.5, "down": 0.75, "phase_shift": 1.5707963, "block_ms": 48.0,
                       "res_q": 40.0, "res_mix": 0.2},
    "Bounce bell": {"script": "sin(k)/k + 1/(k*k)", "domain": "h", "ca_rule": 60, "resonators": "fibonacci",
                    "patch": {"ball->pitch": 0.25, "ball->amp": 0.8, "vector->phase": 0.1, "amp->freq": 0.5,
                              "amp->phase": 0.5, "ca->harmonics": 0.4},
                    "gravity": 20.0, "restitution": 0.85, "vector": [0.3, 0.3, 0.9], "rot_hz": 0.05,
                    "lo": 0.15, "hi": 0.75, "up": 4.0 / 3.0, "down": 0.75, "phase_shift": 3.1415927, "block_ms": 12.0,
                    "res_q": 80.0, "res_mix": 0.45},
    "Square lattice": {"script": "1/k if k in (1, 4, 9) else 0.25/k", "domain": "0.5 + 0.5*y", "ca_rule": 184,
                       "resonators": "square",
                       "patch": {"ball->pitch": 0.0, "ball->amp": 0.25, "vector->phase": 0.6, "amp->freq": 1.0,
                                 "amp->phase": 0.0, "ca->harmonics": 1.0},
                       "gravity": 9.0, "restitution": 0.6, "vector": [0.7, 0.7, 0.1], "rot_hz": 0.15,
                       "lo": 0.3, "hi": 0.7, "up": 2.0, "down": 0.5, "phase_shift": 1.5707963, "block_ms": 24.0,
                       "res_q": 35.0, "res_mix": 0.3},
}
PRESET_NAMES = tuple(PRESETS)
EDITABLE = ("preset", "script", "domain", "ca_rule", "resonators", "patch", "gravity", "restitution",
            "vector", "rot_hz", "lo", "hi", "up", "down", "phase_shift", "block_ms", "res_q", "res_mix",
            "stochastic", "variation", "fractal_depth", "lock_ms", "trigger_response", "field_rate",
            "goava_mode", "xmod_bindings", "xmod_canonical_enabled")


def clamp_mix(w):
    try:
        w = float(w)
    except (TypeError, ValueError):
        return MIX_DEFAULT
    return min(MIX_MAX, max(MIX_MIN, w))


def _u(seed_int, slot, label):
    h = hashlib.blake2b(f"{int(seed_int)}|{int(slot)}|{label}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") / float(1 << 64)


def preset_params(name):
    p = dict(PRESETS.get(name) or PRESETS["Prism"])
    p["patch"] = dict(p["patch"])
    p["vector"] = list(p["vector"])
    p["preset"] = name if name in PRESETS else "Prism"
    return p


def convolution_wet(base, density, slot=0):
    """GROOVEBOX_R23R_MULTIDIM_CONVOLUTION_DEFAULTS_20261103 — the convolution scheme the other two
    synth groups use, for this synth: ``density`` n = 0 … 1 comes from the instrument count (two
    instruments = maximal density, 128 = minimal; n = 0.5 at the scheme midpoint), and each slot is
    spread around it by the golden angle so the ensemble covers the range instead of repeating."""
    n = min(1.0, max(0.0, float(density)))
    spread = ((int(slot) * 0.6180339887498949) % 1.0) - 0.5            # −0.5 … 0.5, golden-angle spaced
    ns = min(1.0, max(0.0, n + 0.25 * spread))
    w = dict(base)
    w["patch"] = dict(base.get("patch") or {})
    w["res_mix"] = 0.12 + 0.33 * ns                    # denser ensembles ring their fixed resonators more
    w["res_q"] = 20.0 + 60.0 * ns
    w["block_ms"] = 6.0 + 42.0 * (1.0 - ns)            # dense = fast conditionals; sparse = long phrases
    w["restitution"] = 0.6 + 0.3 * ns
    w["gravity"] = 6.0 + 14.0 * ns
    w["rot_hz"] = 0.04 + 0.2 * ns
    span = 0.55 - 0.25 * ns                            # the quiet / loud band narrows as density rises
    w["lo"] = 0.5 - span / 2.0
    w["hi"] = 0.5 + span / 2.0
    w["patch"]["ca->harmonics"] = 0.4 + 0.6 * ns
    return w


def convolve_defaults(base, density, convolve, slot=0):
    """(1 − c) · preset + c · convolution density, number by number (c = Global Convolve)."""
    c = min(1.0, max(0.0, float(convolve)))
    if c <= 0.0:
        return base
    wet = convolution_wet(base, density, slot)
    out = dict(base)
    out["patch"] = dict(base.get("patch") or {})
    for k in ("res_mix", "res_q", "block_ms", "restitution", "gravity", "rot_hz", "lo", "hi"):
        try:
            out[k] = (1.0 - c) * float(base.get(k, wet[k])) + c * float(wet[k])
        except (TypeError, ValueError):
            pass
    pk = "ca->harmonics"
    out["patch"][pk] = (1.0 - c) * float(out["patch"].get(pk, wet["patch"][pk])) + c * float(wet["patch"][pk])
    out["_convolution"] = {"density": float(density), "convolve": c}
    return out


def canonical_params(seed_int, slot, engines=(), density=0.5, convolve=0.0):
    """Canonical programme: a preset and its numbers chosen from the seed and the slot, then
    shaped by every active canonical engine (the canonicals do their work through this synth):

      euclidean    → rhythmic CA (rule 184 family), domain follows CA density
      goava        → golden resonators, golden-spiral table
      phase_lock   → vector drives phase, slow rotation
      randomizer / seeded → the ball: seed-drawn gravity / bounce, ball → pitch
      fractal_seed → Sierpinski CA (rule 90), self-similar table
      two or more engines → the main-synth pathways open (main ↔ multidim modulation)
    """
    eng = set(str(e).lower() for e in (engines or ()))
    name = PRESET_NAMES[int(_u(seed_int, slot, "preset") * len(PRESET_NAMES))]
    if "goava" in eng:
        name = "Golden spiral"
    elif "euclidean" in eng or "euclid" in eng:
        name = "Cellular choir"
    p = preset_params(name)
    p["ca_rule"] = int(p["ca_rule"]) ^ (int(_u(seed_int, slot, "rule") * 8) << 1)    # neighbouring rules
    p["vector"] = [round(2.0 * _u(seed_int, slot, a) - 1.0, 4) for a in ("vx", "vy", "vz")]
    p["rot_hz"] = round(0.04 + 0.25 * _u(seed_int, slot, "rot"), 4)
    p["restitution"] = round(0.6 + 0.35 * _u(seed_int, slot, "rest"), 4)
    patch = p["patch"]
    for k in PATHWAY_KEYS:
        patch.setdefault(k, 0.0)
    if "euclidean" in eng or "euclid" in eng:
        p["ca_rule"] = (184, 226, 170, 240)[int(_u(seed_int, slot, "eu") * 4)]
        p["domain"] = "live"
    if "goava" in eng:
        p["resonators"] = "golden"
    if "phase_lock" in eng or "phaselock" in eng or "lock" in eng:
        patch["vector->phase"] = 1.0
        p["rot_hz"] = round(0.03 + 0.05 * _u(seed_int, slot, "pl"), 4)
    if eng & {"randomizer", "seeded", "seeded_randomizer", "random"}:
        p["gravity"] = round(4.0 + 20.0 * _u(seed_int, slot, "g"), 3)
        patch["ball->pitch"] = round(0.05 + 0.25 * _u(seed_int, slot, "bp"), 4)
    if eng & {"fractal_seed", "fractal"}:
        p["ca_rule"] = 90
        p["script"] = "1/k + 0.5*((k % 3) == 0)/k"
    if len(eng) >= 2:
        patch["main->amp"] = round(0.2 + 0.3 * _u(seed_int, slot, "ma"), 4)
        patch["->main.amp"] = round(0.1 + 0.2 * _u(seed_int, slot, "om"), 4)
        patch["main->freq"] = round(0.05 * _u(seed_int, slot, "mf"), 4)
    p.setdefault("stochastic", 0.0)
    p.setdefault("variation", 0.0)
    p.setdefault("fractal_depth", 0.0)
    p.setdefault("lock_ms", 0.0)
    p.setdefault("trigger_response", 0.0)
    p.setdefault("field_rate", 0.5)
    p.setdefault("goava_mode", "seeded")
    if eng & {"randomizer", "seeded", "seeded_randomizer", "random"}:
        p["stochastic"] = round(0.45 + 0.35 * _u(seed_int, slot, "stoch"), 4)
        p["variation"] = round(0.25 + 0.45 * _u(seed_int, slot, "var"), 4)
        p["field_rate"] = round(0.25 + 0.6 * _u(seed_int, slot, "fr"), 4)
        p["trigger_response"] = round(0.55 + 0.4 * _u(seed_int, slot, "tr"), 4)
    if eng & {"fractal_seed", "fractal"}:
        p["fractal_depth"] = round(0.55 + 0.4 * _u(seed_int, slot, "fd"), 4)
    if eng & {"phase_lock", "phaselock", "lock"}:
        p["lock_ms"] = round(40.0 + 180.0 * _u(seed_int, slot, "lk"), 2)
        p["trigger_response"] = round(0.65 + 0.3 * _u(seed_int, slot, "lktr"), 4)
    p["_owner"] = "canonical"
    p["_engines"] = sorted(eng)
    p["_canonical_xmod_bindings"] = canonical_xmod_bindings(eng)
    p["xmod_bindings"] = list(p["_canonical_xmod_bindings"])
    p["xmod_canonical_enabled"] = True
    # convolved defaults, like the panel and geometric synths (instrument-count density × Global Convolve)
    return convolve_defaults(p, density, convolve, slot)


def _blend_num(u, c, share=0.5):
    return (1.0 - share) * float(u) + share * float(c)


def merge_params(canonical, user, canonical_active=True, canon_share=1.0):
    """Ownership like the sequencer: while canonical engines are active every control the user
    has set mixes 50 / 50 with the canonical programme ("U50"); untouched controls stay fully
    canonical; with canonicals off the user's values own their controls outright.

      numbers / vector / patch  : ½ user + ½ canonical
      CA rule                   : half the rule bits from each (even bits user, odd bits canonical)
      script / domain equation  : 0.5·(user) + 0.5·(canonical)  — the two expressions' outputs mixed
      resonator rule            : both rules' fixed resonators ring ("user+canonical")
      preset                    : the user's preset replaces the canonical programme's base,
                                  which then mixes 50 / 50 with the canonical numbers as above
    """
    user = dict(user or {})
    canon = dict(canonical)
    cs = min(MIX_MAX, max(MIX_MIN, float(canon_share)))          # canonical share 0 … 100 % (default 100 %)
    if user.get("preset") in PRESETS:
        upre = preset_params(user["preset"])
        for k, v in upre.items():
            if k not in user and k in EDITABLE and k != "preset":
                user[k] = v
    base = dict(canon)
    # Canonical binding defaults remain active unless explicitly disabled; user
    # routes are merged on matching source/target pairs with the same ownership
    # share as other multidimensional controls.
    canonical_routes = canon.get("_canonical_xmod_bindings", ())
    user_routes = user.get("xmod_bindings", ())
    base["xmod_bindings"] = _merge_xmod_bindings(canonical_routes, user_routes, cs, bool(canonical_active))
    base["xmod_canonical_enabled"] = bool(user.get("xmod_canonical_enabled", True))
    if not base["xmod_canonical_enabled"]:
        base["xmod_bindings"] = _clean_xmod_bindings(user_routes)
    owned = []
    for k, v in user.items():
        if k not in EDITABLE or v is None or k == "preset":
            continue
        owned.append(k)
        if k in ("xmod_bindings", "xmod_canonical_enabled"):
            continue  # already merged above with explicit route ownership semantics
        cv = canon.get(k)
        if not canonical_active or cv is None:
            base[k] = v
            continue
        try:
            if k == "patch" and isinstance(v, dict):
                pc = dict(cv or {}); pm = dict(pc)
                for pk, pv in v.items():
                    pm[pk] = _blend_num(pv, pc.get(pk, pv), cs)
                base[k] = pm
            elif k == "vector":
                uv = (list(v) + [0.0, 0.0, 0.0])[:3]; cvv = (list(cv) + [0.0, 0.0, 0.0])[:3]
                base[k] = [_blend_num(a, b, cs) for a, b in zip(uv, cvv)]
            elif k == "ca_rule":
                base[k] = (int(v) & 0b01010101) | (int(cv) & 0b10101010)
            elif k in ("script", "domain"):
                base[k] = v if str(v) == str(cv) else f"{1.0 - cs:.4g}*({v}) + {cs:.4g}*({cv})"
            elif k == "resonators":
                base[k] = v if v == cv else f"{v}+{cv}"
            elif k == "goava_mode":
                base[k] = "io" if str(v).lower() in ("io", "input", "signal") else "seeded"
            elif k == "ca_rule":
                pass
            else:
                base[k] = _blend_num(v, cv, cs)
        except (TypeError, ValueError):
            base[k] = v
    if user.get("preset") in PRESETS:
        owned.append("preset")
    base["_user_keys"] = owned
    base["_mode"] = (f"U{int(round((1.0 - cs) * 100))}" if (canonical_active and owned) else ("user" if owned else "canonical"))
    return base


_SCRIPT_CACHE = {}


def _compile(expr, mode="eval"):
    key = (expr, mode)
    code = _SCRIPT_CACHE.get(key)
    if code is None:
        import ot_script_math
        code = ot_script_math.compile_script(str(expr), "<multidim-synth>", mode)
        if len(_SCRIPT_CACHE) > 512:
            _SCRIPT_CACHE.clear()
        _SCRIPT_CACHE[key] = code
    return code


def _env():
    import ot_script_math
    env = {"__builtins__": {}, "sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
           "sqrt": math.sqrt, "abs": abs, "min": min, "max": max, "pi": math.pi, "tau": math.tau,
           "e": math.e, "phi": 1.618033988749895, "floor": math.floor, "log": math.log}
    return ot_script_math.install(env)


def table_amplitudes(script):
    """Partial amplitudes from the preset script (k = 1 … H). Non-finite results count as 0."""
    code = _compile(script or "1/k")
    env = _env()
    out = np.zeros(H, dtype=np.float64)
    for k in range(1, H + 1):
        env["k"] = k
        try:
            v = float(eval(code, env))
        except Exception:
            v = 0.0
        out[k - 1] = v if math.isfinite(v) else 0.0
    return out


# ---------------------------------------------------------------------------
# Finite-infinity certified shortcuts (GROOVEBOX_R23R_FI_SHORTCUTS_20261103)
# ---------------------------------------------------------------------------
# Only EXACT shortcuts are taken (finite_infinity's rule): a deterministic state that provably
# repeats. Nothing is skipped on a "looks periodic" guess.
_ORBIT_CACHE = {}
FI_STATS = {"ca_orbits": 0, "ca_period": 0, "ball_cycles": 0, "memo_hits": 0, "memo_misses": 0, "memo_bytes": 0}


def _ca_orbit(rule, seed_cells):
    """The CA's whole future as (states, preperiod, period). 12 cells = at most 4 096 states, so the
    orbit always closes; finite_infinity.transition_jump's orbit decomposition, done once per
    (rule, seed) and cached."""
    rule = int(rule) & 255
    seed = tuple(int(x) for x in np.asarray(seed_cells, dtype=np.uint8))
    key = (rule, seed)
    hit = _ORBIT_CACHE.get(key)
    if hit is not None:
        return hit
    table = np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)
    seen, states = {}, []
    cur = np.asarray(seed, dtype=np.uint8)
    while True:
        if not cur.any():                          # a dead world re-seeds from the instrument's cells
            cur = np.asarray(seed, dtype=np.uint8)
        k = cur.tobytes()
        if k in seen:
            mu = seen[k]
            break
        seen[k] = len(states)
        states.append(cur.copy())
        idx = (np.roll(cur, 1) << 2) | (cur << 1) | np.roll(cur, -1)
        cur = table[idx]
    orbit = (np.array(states, dtype=np.uint8), mu, len(states) - mu)
    if len(_ORBIT_CACHE) > 1024:
        _ORBIT_CACHE.clear()
    _ORBIT_CACHE[key] = orbit
    FI_STATS["ca_orbits"] += 1
    FI_STATS["ca_period"] = orbit[2]
    return orbit


def _ca_rows(rule, nb, seed_cells):
    """Rows 0 … nb−1, read from the certified orbit (identical to stepping the CA nb times)."""
    states, mu, period = _ca_orbit(rule, seed_cells)
    b = np.arange(int(nb))
    idx = np.where(b < len(states), b, mu + (b - mu) % max(1, period))
    return states[np.minimum(idx, len(states) - 1)]


def _ball(nb, dt, gravity, restitution):
    """Block heights (0 … 1) of a ball dropped from 1, bouncing with restitution; when it comes
    to rest it is thrown again from the floor (h = 0, v = √(2g)) — the identical state every time, so
    from the first relaunch on the motion is EXACTLY periodic. The period is certified the first time
    the relaunch state recurs and the rest of the row is copied from it (bit-identical)."""
    nb = int(nb)
    hs = np.zeros(nb)
    h, v = 1.0, 0.0
    g = abs(float(gravity)); e = min(0.99, max(0.0, float(restitution)))
    launch_at = None
    for b in range(nb):
        v -= g * dt
        h += v * dt
        relaunched = False
        if h <= 0.0:
            h = 0.0
            v = -v * e
            if v < 0.05 * g * dt * 10:             # at rest: thrown again
                v = math.sqrt(2.0 * g * 1.0) if g > 0 else 0.0
                relaunched = True
        hs[b] = min(1.0, h)
        if relaunched:
            if launch_at is None:
                launch_at = b
            else:                                  # same state (h=0, v=√2g) again: certified cycle
                period = b - launch_at
                rest = nb - (b + 1)
                if rest > 0 and period > 0:
                    src = hs[launch_at + 1: launch_at + 1 + period]
                    reps = np.resize(src, rest)
                    hs[b + 1:] = reps
                    FI_STATS["ball_cycles"] += 1
                return hs
    return hs


_BALL_ORBITS = {}


def ball_at(b, dt, gravity, restitution, horizon=200000):
    """Ball height at block b — exact O(1) lookup in the certified orbit (pre-cycle + cycle that
    starts at the first relaunch). Identical to _ball(b + 1, …)[-1]."""
    key = (float(dt), float(gravity), float(restitution))
    orb = _BALL_ORBITS.get(key)
    if orb is None:
        hs = []
        h, v = 1.0, 0.0
        g = abs(float(gravity)); e = min(0.99, max(0.0, float(restitution)))
        first = None
        mu = period = None
        for i in range(int(horizon)):
            v -= g * dt
            h += v * dt
            relaunched = False
            if h <= 0.0:
                h = 0.0
                v = -v * e
                if v < 0.05 * g * dt * 10:
                    v = math.sqrt(2.0 * g * 1.0) if g > 0 else 0.0
                    relaunched = True
            hs.append(min(1.0, h))
            if relaunched:
                if first is None:
                    first = i
                else:
                    mu, period = first + 1, i - first
                    break
        orb = (np.asarray(hs), mu, period)
        if len(_BALL_ORBITS) > 256:
            _BALL_ORBITS.clear()
        _BALL_ORBITS[key] = orb
    hs, mu, period = orb
    b = int(b)
    if b < len(hs):
        return float(hs[b])
    if mu is not None and period:
        return float(hs[mu + (b - mu) % period])
    return float(hs[-1])           # no certified cycle within the horizon (g = 0): it rests


# Playlist-pattern memo: a voice's multidimensional output depends only on its phase STEPS (not the
# absolute phase), its programme, seed, slot, rate, base frequency and — when a main-synth pathway is
# open — the main synth's signal. A later row that repeats those inputs repeats the output exactly.
_MEMO = {}
_MEMO_ORDER = []
_MEMO_BYTES_MAX = 96 * 1024 * 1024


def _memo_key(step, params, sr, base_hz, seed_int, slot, main, em_used):
    import json as _json
    h = hashlib.blake2b(digest_size=32)
    h.update(np.ascontiguousarray(step, dtype=np.float64).tobytes())
    h.update(_json.dumps({k: v for k, v in params.items() if not str(k).startswith("_")},
                         sort_keys=True, default=str).encode())
    h.update(repr((float(sr), float(base_hz), int(seed_int), int(slot))).encode())
    if em_used and main is not None:
        h.update(np.ascontiguousarray(main, dtype=np.float64).tobytes())
    return h.digest()


def _memo_get(key):
    out = _MEMO.get(key)
    if out is not None:
        FI_STATS["memo_hits"] += 1
        return out.copy()
    FI_STATS["memo_misses"] += 1
    return None


def _memo_put(key, y):
    if key in _MEMO:
        return
    _MEMO[key] = y.copy()
    _MEMO_ORDER.append(key)
    FI_STATS["memo_bytes"] += int(y.nbytes)
    while FI_STATS["memo_bytes"] > _MEMO_BYTES_MAX and _MEMO_ORDER:
        old = _MEMO.pop(_MEMO_ORDER.pop(0), None)
        if old is not None:
            FI_STATS["memo_bytes"] -= int(old.nbytes)


def memo_clear():
    world_clear()
    _MEMO.clear(); _MEMO_ORDER.clear(); FI_STATS["memo_bytes"] = 0


# ---------------------------------------------------------------------------- world record
# GROOVEBOX_R23R_WORLD_RECORD_20261103 — render once, read everywhere.
# The audio render records each voice’s per-block world (loud/quiet decisions, domain weight,
# amplitude, ball, CA row, vector, live). Video and games read the record so the picture shows
# exactly the events the sound just decided — no second simulation.
_WORLD = {}
_WORLD_ORDER = []
_WORLD_BYTES = 0
_WORLD_MAX = 64 * 1024 * 1024


def _world_key(params, seed_int, slot):
    import json as _json
    h = hashlib.blake2b(digest_size=16)
    clean = {k: v for k, v in (params or {}).items() if not str(k).startswith("_")}
    h.update(_json.dumps(clean, sort_keys=True, default=str).encode())
    h.update(repr((int(seed_int), int(slot))).encode())
    return h.digest()


def _rec_bytes(rec) -> int:
    n = 0
    for v in rec.values():
        if isinstance(v, np.ndarray):
            n += int(v.nbytes)
    return n


def _world_put(key, rec):
    global _WORLD_BYTES
    old = _WORLD.get(key)
    if old is not None:
        _WORLD_BYTES -= _rec_bytes(old)
        try:
            _WORLD_ORDER.remove(key)
        except ValueError:
            pass
    _WORLD[key] = rec
    _WORLD_ORDER.append(key)
    _WORLD_BYTES += _rec_bytes(rec)
    while _WORLD_BYTES > _WORLD_MAX and _WORLD_ORDER:
        oldk = _WORLD_ORDER.pop(0)
        oldr = _WORLD.pop(oldk, None)
        if oldr is not None:
            _WORLD_BYTES -= _rec_bytes(oldr)


def world_at(params, seed_int, slot, block):
    """Return the recorded per-block world for this voice at absolute block, or None.
    Used by video / games so they read the decisions the audio render already made."""
    key = _world_key(params, seed_int, slot)
    rec = _WORLD.get(key)
    if rec is None:
        return None
    local = int(block) - int(rec.get("start_block", 0))
    nb = int(rec.get("nb", 0))
    if not (0 <= local < nb):
        return None
    try:
        return {
            "domain": float(rec["dom"][local]),
            "loud": bool(rec["loud"][local]),
            "quiet": bool(rec["quiet"][local]),
            "amp": float(rec["amp"][local]),
            "ball": float(rec["ball"][local]),
            "ca_row": rec["ca"][local].copy() if "ca" in rec else None,
            "vector": tuple(float(x) for x in rec["vec"][local]),
            "live": float(rec["live"][local]),
        }
    except Exception:
        return None


def world_clear():
    global _WORLD_BYTES
    _WORLD.clear()
    _WORLD_ORDER.clear()
    _WORLD_BYTES = 0


def _resonate(y, sr, base_hz, rule, q, mix):
    """Canonical fixed resonators on the local instrument signal (always mixable).

    ``mix`` is the single wet control (0–1).  Rules may be combined with ``+``.
    When scipy is unavailable a pure-NumPy one-pole resonator approximates the ring.
    """
    ratios = ()
    for part in str(rule or "harmonic").split("+"):
        ratios = ratios + tuple(r for r in RESONATOR_RULES.get(part.strip(), ()) if r not in ratios)
    mix = float(max(0.0, min(1.0, float(mix or 0.0))))
    y = np.asarray(y, dtype=np.float64)
    if not ratios or mix <= 0.0 or y.size == 0:
        return y.astype(np.float32, copy=False) if y.dtype != np.float32 else y
    # R32.6 SPEED: every resonator is the same 2-pole band-pass biquad; its exact impulse
    # response has a closed form (poles r·e^{±jθ}: g[n] = rⁿ·sin((n+1)θ)/sin θ). All
    # resonators' responses are summed and applied with ONE FFT convolution, truncated where
    # rⁿ < 1e-10. Identical (to ~1e-10) to running the recurrences, without the per-sample
    # Python loop that ran whenever SciPy was absent (the main cost of a multidim render).
    n = y.size
    h_sum = None
    n_ok = 0
    for r in ratios:
        f = float(base_hz) * float(r)
        if not (0.0 < f < 0.45 * float(sr)):
            continue
        w0 = 2.0 * math.pi * f / float(sr)
        qv = max(0.5, float(q or 30.0))
        alpha = math.sin(w0) / (2.0 * qv)
        a0 = 1.0 + alpha
        b0, b2 = alpha / a0, -alpha / a0
        a1, a2 = -2.0 * math.cos(w0) / a0, (1.0 - alpha) / a0
        rad = math.sqrt(max(1e-300, a2))
        cth = max(-1.0, min(1.0, -a1 / (2.0 * rad)))
        th = math.acos(cth)
        sth = math.sin(th) or 1e-12
        L = int(min(n, max(8, math.log(1e-10) / math.log(min(rad, 1.0 - 1e-12)))))
        k = np.arange(L + 2, dtype=np.float64)
        g = (rad ** k) * np.sin((k + 1.0) * th) / sth
        h = b0 * g[:L].copy()
        h[2:] += b2 * g[:L - 2]
        if h_sum is None or h_sum.size < L:
            hs = np.zeros(L); hs[: (0 if h_sum is None else h_sum.size)] = (0 if h_sum is None else h_sum); h_sum = hs
        h_sum[:L] += h
        n_ok += 1
    if n_ok:
        N = 1 << int(math.ceil(math.log2(n + h_sum.size)))
        out = np.fft.irfft(np.fft.rfft(y, N) * np.fft.rfft(h_sum, N), N)[:n]
    else:
        out = np.zeros_like(y)
    if n_ok == 0:
        return y.astype(np.float32, copy=False)
    wet = out / float(n_ok)
    return ((1.0 - mix) * y + mix * wet).astype(np.float32)


def apply_geometrics_fx(y, sr, amount, *, eqr=None, fractalizer=None, pkp=None):
    """Hardcoded PKP / EQR / Fractallizer on the multidim signal at onboard default ratios.

    ``amount`` is the single mixable slider (0–1).  At amount=0.5 the three effects
    sit at EQR_DEFAULT : FRACTALLIZER_DEFAULT : PKP_ENVELOPE_DEFAULT relative weights
    (same ratio family as the main-window Global FX defaults).
    """
    y = np.asarray(y, dtype=np.float64)
    if y.size == 0:
        return y.astype(np.float32)
    amount = float(max(0.0, min(1.0, float(amount))))
    # Onboard defaults (mirrored from groovebox constants)
    _EQR = 0.4014 if eqr is None else float(eqr)
    _FR  = 0.5995 if fractalizer is None else float(fractalizer)
    _PKP = 0.5000 if pkp is None else float(pkp)
    # Centre amount=0.5 at the default absolute levels
    scale = amount * 2.0  # 0.5 → 1.0× defaults
    eqr_w = max(0.0, min(1.0, _EQR * scale))
    fr_w  = max(0.0, min(1.0, _FR * scale))
    pkp_w = max(0.0, min(1.0, _PKP * scale))
    out = y.copy()
    n = out.size
    # --- EQR: gentle spectral tilt via first-order shelf (low vs high emphasis) ---
    if eqr_w > 1e-6 and n > 4:
        # one-pole lowpass residual blend
        alpha = math.exp(-2.0 * math.pi * (200.0 + 3800.0 * eqr_w) / max(1.0, float(sr)))
        lp = np.empty(n, dtype=np.float64)
        acc = 0.0
        for i in range(n):
            acc = alpha * acc + (1.0 - alpha) * out[i]
            lp[i] = acc
        # high shelf emphasis proportional to eqr_w
        out = out + eqr_w * (out - lp)
    # --- Fractallizer: octave-up self-similar layer (half-rate readout) ---
    if fr_w > 1e-6 and n > 8:
        idx = np.linspace(0.0, n - 1, n // 2)
        half = np.interp(idx, np.arange(n), out)
        # stretch back to n samples
        layer = np.interp(np.linspace(0.0, half.size - 1, n), np.arange(half.size), half)
        out = (1.0 - 0.5 * fr_w) * out + (0.5 * fr_w) * layer
    # --- PKP envelope: percussive shape on the block (pluck → solid at mid → swell) ---
    if pkp_w > 1e-6 and n > 4:
        t = np.linspace(0.0, 1.0, n, endpoint=False)
        # at low pkp: pluck (fast decay); mid: solid; high: swell
        pluck = np.exp(-6.0 * t)
        solid = np.ones_like(t)
        swell = 0.2 + 0.8 * t
        # blend along pkp_w: 0→pluck, 0.5→solid, 1→swell (using default-centred scale)
        if pkp_w <= 0.5:
            u = pkp_w * 2.0
            env = (1.0 - u) * pluck + u * solid
        else:
            u = (pkp_w - 0.5) * 2.0
            env = (1.0 - u) * solid + u * swell
        # wet-mix the envelope so amount=0 leaves signal alone
        out = out * ((1.0 - amount) + amount * env)
    # soft peak guard
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 1.5:
        out *= 1.5 / peak
    return out.astype(np.float32)


def block_envelope(x, blk):
    """Peak per block of |x|, normalised to its own maximum (exact; silence = zeros)."""
    x = np.abs(np.asarray(x, dtype=np.float64))
    n = x.size
    nb = (n + blk - 1) // blk
    e = np.concatenate([x, np.zeros(nb * blk - n)]).reshape(nb, blk).max(axis=1)
    m = float(e.max()) if e.size else 0.0
    return e / m if m > 0 else e


class _WhereRewrite(__import__("ast").NodeTransformer):
    """`A if C else B` → __where__(C, A, B); `and` / `or` → element-wise — so a domain equation can
    be evaluated for every block at once (GROOVEBOX_R23R_MULTIDIM_VECTORIZED_20261103)."""
    def visit_IfExp(self, node):
        import ast
        self.generic_visit(node)
        return ast.copy_location(ast.Call(func=ast.Name(id="__where__", ctx=ast.Load()),
                                          args=[node.test, node.body, node.orelse], keywords=[]), node)

    def visit_BoolOp(self, node):
        import ast
        self.generic_visit(node)
        fn = "__land__" if isinstance(node.op, ast.And) else "__lor__"
        out = node.values[0]
        for v in node.values[1:]:
            out = ast.Call(func=ast.Name(id=fn, ctx=ast.Load()), args=[out, v], keywords=[])
        return ast.copy_location(out, node)


_VEC_CACHE = {}


def _domain_vector(expr, nb, values):
    """Evaluate the domain equation for all blocks at once; None if it needs per-block evaluation."""
    import ast
    code = _VEC_CACHE.get(expr)
    if code is None:
        try:
            import ot_script_math
            tree = _WhereRewrite().visit(ast.parse(str(expr), mode="eval"))
            tree = ot_script_math.rewrite(ast.fix_missing_locations(tree))
            code = compile(tree, "<multidim-domain-vec>", "eval")
        except Exception:
            code = False
        if len(_VEC_CACHE) > 256:
            _VEC_CACHE.clear()
        _VEC_CACHE[expr] = code
    if code is False:
        return None
    import ot_script_math
    env = {"__builtins__": {}, "sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "sqrt": np.sqrt,
           "abs": np.abs, "pi": math.pi, "tau": math.tau, "e": math.e, "phi": 1.618033988749895,
           "floor": np.floor, "log": np.log, "__where__": np.where, "__land__": np.logical_and,
           "__lor__": np.logical_or}
    ot_script_math.install(env)
    env.update(values)
    try:
        with np.errstate(all="ignore"):
            v = np.asarray(eval(code, env), dtype=np.float64)
        v = np.broadcast_to(v, (nb,)).copy()
    except Exception:
        return None
    v = np.where(np.isfinite(v), v, 0.5)
    return np.clip(v, 0.0, 1.0)


MD_NET_MOD_DEFAULT = 0.5      # MD_NET_MOD_R31: default ceiling on the summed cross-mod per target
MD_STOCH_DEFAULT_PROBABILITY = 0.19758   # MD_STOCH_R31: internal default (no canonical probability / activation)


def _hash_unit(seed_int, slot, idx, salt):
    """Vectorised splitmix64 → [0, 1): a pure function of (seed, slot, absolute block, salt)."""
    with np.errstate(over="ignore"):
        x = (np.asarray(idx, dtype=np.uint64) * np.uint64(0x9E3779B97F4A7C15)
             + np.uint64((int(seed_int) * 1000003 + int(slot) * 7919 + int(salt) * 104729) & 0xFFFFFFFFFFFFFFFF))
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        x = x ^ (x >> np.uint64(31))
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def stochastic_probability(p, seed_int, slot):
    """MD_STOCH_R31: (probability, mode).

    canonical  — any canonical active with level > 0: the canonical decision module's seed/slot value
                 scaled by the activation level; the internal default is disregarded.
    fallback   — no canonical probability / activation: MD_STOCH_DEFAULT_PROBABILITY × the Morph
                 Bridge mix (0–1), time-variant."""
    # CANONICAL_DECISION_R31_6: the same shared decision layer every module uses.
    from canonical_decision import decide
    lvl = float(np.clip(float(p.get("stoch_canon_level", 0.0) or 0.0), 0.0, 1.0))
    active = bool(p.get("stoch_canon_active", bool(p.get("_engines"))))
    base = float(p.get("stochastic", 0.0) or 0.0)
    if active and lvl > 0.0 and base <= 0.0:
        base = 0.45 + 0.35 * _u(seed_int, slot, "stoch")           # same decision module as canonical_params
    mix = p.get("stoch_default_mix")
    return decide("multidim", "stoch", seed=seed_int, slot=slot, active=active, level=lvl,
                  default=MD_STOCH_DEFAULT_PROBABILITY, mix=(1.0 if mix is None else mix), canonical_value=base)


def _xmod_target_delta(bindings, target, sources, n, cap=1.0):
    delta = np.zeros(int(n), dtype=np.float64)
    for route in bindings:
        if route.get("target") != target:
            continue
        src = sources.get(route.get("source"))
        if src is None:
            continue
        arr = np.asarray(src, dtype=np.float64).reshape(-1)
        if arr.size == 1:
            arr = np.full(n, float(arr[0]), dtype=np.float64)
        elif arr.size != n:
            arr = np.resize(arr, n)
        amount = float(route.get("amount", 0.0))
        delta += amount * (2.0 * np.clip(arr, 0.0, 1.0) - 1.0)
    cap = float(np.clip(cap, 0.0, 1.0))        # Max Net Modulation (Canonical Morph Bridge)
    return np.clip(delta, -cap, cap)


def voice(phase, sr, params, t=None, base_hz=432.0, seed_int=0, slot=0, main=None, pool=None, step=None):
    """Render the multidimensional synth over the voice's phase track (radians). float32 (a new array).

    ``main``: the main synth's signal for this voice (pathways main → this synth).
    ``pool``: the sCode optimizer (borrow_vector) — all large scratch arrays come from its pool.
    Work happens on a (blocks × block-length) grid: per-block amplitudes broadcast over their block
    (no samples × partials array), the partial sum uses one complex exponential and its powers."""
    import threading as _th
    phase = np.asarray(phase, dtype=np.float64)
    n = int(phase.size)
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    sr = float(sr)
    if t is None:
        t = np.arange(n, dtype=np.float64) / sr
    p = params
    patch = dict(p.get("patch") or {})
    gmod = p.get("global_mod_state") or {}
    try:
        _net_cap = float(np.clip(float(p.get("xmod_net_max", 1.0)), 0.0, 1.0))
    except (TypeError, ValueError):
        _net_cap = 1.0
    try:
        gx = float(np.clip(float(gmod.get("xmod", 1.0)), 0.0, 2.0))
        gi = float(np.clip(float(gmod.get("input_xmod", 1.0)), 0.0, 2.0))
        gp = float(np.clip(float(gmod.get("patch", 1.0)), 0.0, 2.0))
        gscript = float(np.clip(float(gmod.get("script", 1.0)), 0.0, 2.0))
        gdomain = float(np.clip(float(gmod.get("domain", 1.0)), 0.0, 2.0))
        gsynth = float(np.clip(float(gmod.get("synth", 1.0)), 0.0, 2.0))
    except (TypeError, ValueError):
        gx = gi = gp = gscript = gdomain = gsynth = 1.0
    patch_scale = gx * gp
    for _key in tuple(patch):
        patch[_key] = float(patch[_key]) * patch_scale
        if _key in ("main->freq", "main->phase", "main->amp"):
            patch[_key] *= gi
    blk = max(16, int(round(float(p.get("block_ms", 12.0)) * 1e-3 * sr)))
    nb = (n + blk - 1) // blk
    N = nb * blk
    tid = _th.get_ident()

    def scratch(kind, dtype):
        if pool is not None and hasattr(pool, "borrow_vector"):
            return pool.borrow_vector(f"md_{kind}_{tid}", N, dtype)
        return np.empty(N, dtype=dtype)

    tb = (np.arange(nb) * blk) / sr                                  # block start times
    # dimensions
    flow = table_amplitudes(p.get("script", "1/k"))
    if abs(gscript - 1.0) > 1e-12:
        # Unity is an exact no-op; away from unity, tilt the harmonic spectrum
        # smoothly without changing phase or introducing nondeterministic noise.
        harmonic_axis = np.linspace(-0.5, 0.5, H, dtype=np.float64)
        flow *= np.clip(1.0 + (gscript - 1.0) * harmonic_axis, 0.0, 2.0)
    seed_cells = np.array([((int(seed_int) >> (k % 31)) & 1) ^ ((int(slot) + k) % 2) for k in range(H)], dtype=np.uint8)
    if not seed_cells.any():
        seed_cells[H // 2] = 1
    ca = _ca_rows(p.get("ca_rule", 90), nb, seed_cells).astype(np.float64)
    cah = float(patch.get("ca->harmonics", 1.0))
    hb = _ball(nb, blk / sr, p.get("gravity", 9.8), p.get("restitution", 0.8))
    vx, vy, vz = (list(p.get("vector") or [0.5, 0.5, 0.5]) + [0.5, 0.5, 0.5])[:3]
    rot = float(p.get("rot_hz", 0.1)) * math.tau
    xb = vx * np.cos(rot * tb) - vy * np.sin(rot * tb)
    yb = vx * np.sin(rot * tb) + vy * np.cos(rot * tb)
    zb = vz * np.cos(0.5 * rot * tb)
    live_early = ca.mean(axis=1)
    binding_enabled = bool(p.get("xmod_canonical_enabled", True))
    xmod_bindings = _clean_xmod_bindings(p.get("xmod_bindings") or ()) if binding_enabled else ()
    early_sources = {
        "main_envelope": np.clip(block_envelope(main, blk), 0.0, 1.0)
                          if main is not None and np.size(main) == n else np.full(nb, 0.5),
        "ball_height": np.clip(hb, 0.0, 1.0),
        "vector_x": np.clip(0.5 + 0.5 * xb, 0.0, 1.0),
        "vector_y": np.clip(0.5 + 0.5 * yb, 0.0, 1.0),
        "vector_z": np.clip(0.5 + 0.5 * zb, 0.0, 1.0),
        "cellular_density": np.clip(live_early, 0.0, 1.0),
    }
    if xmod_bindings:
        spectrum_delta = _xmod_target_delta(xmod_bindings, "script_spectrum", early_sources, nb, cap=_net_cap)
        harmonic_delta = _xmod_target_delta(xmod_bindings, "harmonics", early_sources, nb, cap=_net_cap)
        # Each route is low-depth and normalized; use per-partial profile tilt.
        _haxis = np.linspace(-0.5, 0.5, H, dtype=np.float64)
        flow *= np.clip(1.0 + 0.25 * float(np.mean(spectrum_delta)) * _haxis, 0.0, 2.0)
        _hshape = (np.arange(H, dtype=np.float64) + 1.0) / float(H)
        # Harmonically scoped influence is combined with the per-block CA gate below.
        _xmod_harmonic_profile = np.clip(1.0 + harmonic_delta[:, None] * _hshape[None, :] * 0.25, 0.0, 2.0)
    else:
        _xmod_harmonic_profile = 1.0
    structure = flow * (cah * ca + (1.0 - cah))                       # (nb, H)
    if isinstance(_xmod_harmonic_profile, np.ndarray):
        structure *= _xmod_harmonic_profile
    _src_step = step
    step = scratch("step", np.float64)
    if _src_step is not None and np.size(_src_step) == n:
        # the increments the phase track was built from (independent of where the previous row
        # ended) — exact, and identical for repeated rows, so the playlist memo can certify them
        step[:n] = np.asarray(_src_step, dtype=np.float64)
    else:
        step[:n] = np.diff(phase, prepend=phase[0] - (phase[1] - phase[0] if n > 1 else 0.0))
    step[n:] = 0.0
    step2 = step.reshape(nb, blk)
    kk = np.arange(1, H + 1, dtype=np.float64)
    psi = (kk * 2.399963229728653) % math.tau
    cpsi, spsi = np.cos(psi), np.sin(psi)
    ramp = np.arange(blk, dtype=np.float64) / float(blk)
    ba = float(patch.get("ball->amp", 0.0))

    def render(mult_b, turn_b, dom_b):
        """Returns a view of pooled scratch (valid until the next render on this thread)."""
        amps_b = dom_b[:, None] * structure + (1.0 - dom_b[:, None]) * flow[None, :]       # (nb, H)
        theta = scratch("theta", np.float64)
        th2 = theta.reshape(nb, blk)
        np.multiply(step2, mult_b[:, None], out=th2)
        np.cumsum(theta, out=theta)
        cum = np.concatenate([[0.0], np.cumsum(turn_b)])
        th2 += cum[:-1, None] + turn_b[:, None] * ramp[None, :]        # phase turns spread over their block
        z = scratch("z", np.complex128)
        np.cos(theta, out=z.real); np.sin(theta, out=z.imag)
        zk = scratch("zk", np.complex128); zk.fill(1.0)
        Y = scratch("Y", np.float64); Y.fill(0.0)
        tmp = scratch("tmp", np.float64); tmp2 = scratch("tmp2", np.float64)
        Y2, tmp_2 = Y.reshape(nb, blk), tmp.reshape(nb, blk)
        for k in range(H):
            np.multiply(zk, z, out=zk)
            # Im(zk · e^{iψ}) = Im(zk)·cos ψ + Re(zk)·sin ψ
            np.multiply(zk.imag, cpsi[k], out=tmp); np.multiply(zk.real, spsi[k], out=tmp2); tmp += tmp2
            tmp_2 *= amps_b[:, k, None]
            Y += tmp
        S_b = np.sum(np.abs(amps_b), axis=1)
        np.divide(Y2, S_b[:, None], out=Y2, where=S_b[:, None] != 0)  # exact; empty table = silence (0)
        if ba:
            Y2 *= (1.0 - ba + ba * hb)[:, None]
        return Y

    # pathways IN from the main synth (its block envelope em, 0 … 1)
    em = None
    goava_io = (
        str(p.get("goava_mode", "seeded")).lower() in ("io", "input", "signal")
        and "goava" in {str(e).lower() for e in (p.get("_engines") or ())}
    )
    if main is not None and np.size(main) == n and (
        any(float(patch.get(k, 0.0)) for k in ("main->freq", "main->phase", "main->amp")) or goava_io
    ):
        em = block_envelope(main, blk)
    # finite-infinity: the same inputs as an earlier row → the same output (exact reuse)
    _mkey = _memo_key(step[:n], p, sr, base_hz, seed_int, slot, main, em is not None)
    _hit = _memo_get(_mkey)
    if _hit is not None:
        return _hit
    # pass 1: no conditionals (ball → pitch and vector → phase only) to hear its own amplitude
    bp = float(patch.get("ball->pitch", 0.0))
    mult0 = 1.0 + bp * (hb - 0.5)
    if xmod_bindings:
        _pitch_delta = _xmod_target_delta(xmod_bindings, "pitch", early_sources, nb, cap=_net_cap)
        mult0 *= 1.0 + 0.14 * _pitch_delta
    # vector → phase: the UNWRAPPED rotation angle (the raw arctan2 difference jumped by 2π at every wrap,
    # i.e. a phase jump — a click — once per rotation)
    _ang = np.unwrap(np.arctan2(yb, xb)) if nb > 0 else np.zeros(0)
    turn0 = float(patch.get("vector->phase", 0.0)) * np.diff(np.concatenate([[_ang[0] if nb else 0.0], _ang]))
    if xmod_bindings:
        _phase_delta = _xmod_target_delta(xmod_bindings, "phase", early_sources, nb, cap=_net_cap)
        turn0 += 0.10 * math.pi * _phase_delta
    if em is not None:
        mult0 = mult0 * (1.0 + float(patch.get("main->freq", 0.0)) * (em - 0.5))
        turn0 = turn0 + float(patch.get("main->phase", 0.0)) * math.pi * np.diff(np.concatenate([[0.0], em]))
    y0 = render(mult0, turn0, np.full(nb, 0.5))
    y0[n:] = 0.0
    a = np.abs(y0.reshape(nb, blk)).max(axis=1)
    # domain equation (t, b, h, a, x, y, z, live) — all blocks at once when it is element-wise
    live = ca.mean(axis=1)
    dexpr = str(p.get("domain", "0.5"))
    dom = _domain_vector(dexpr, nb, {"t": tb, "b": np.arange(nb, dtype=np.float64), "h": hb, "a": a,
                                     "x": xb, "y": yb, "z": zb, "live": live})
    if dom is None:                                    # per-block fallback (min / max / chained comparisons …)
        dom = np.zeros(nb)
        code = _compile(dexpr)
        env = _env()
        for b in range(nb):
            env.update(t=float(tb[b]), b=b, h=float(hb[b]), a=float(a[b]), x=float(xb[b]), y=float(yb[b]),
                       z=float(zb[b]), live=float(live[b]))
            try:
                v = float(eval(code, env))
            except Exception:
                v = 0.5
            dom[b] = min(1.0, max(0.0, v)) if math.isfinite(v) else 0.5
    if abs(gdomain - 1.0) > 1e-12:
        dom = np.clip(0.5 + (dom - 0.5) * gdomain, 0.0, 1.0)
    if xmod_bindings:
        _domain_sources = dict(early_sources)
        _domain_sources["previous_amplitude"] = np.clip(np.r_[0.5, a[:-1]], 0.0, 1.0)
        _domain_sources["domain_weight"] = np.clip(dom, 0.0, 1.0)
        dom_delta = _xmod_target_delta(xmod_bindings, "domain", _domain_sources, nb, cap=_net_cap)
        dom = np.clip(dom + 0.12 * dom_delta, 0.0, 1.0)
        _res_delta = _xmod_target_delta(xmod_bindings, "resonance", _domain_sources, nb, cap=_net_cap)
        _synth_delta = _xmod_target_delta(xmod_bindings, "synth_level", _domain_sources, nb, cap=_net_cap)
        _prev_pitch = _xmod_target_delta(xmod_bindings, "pitch", _domain_sources, nb, cap=_net_cap)
        _prev_phase = _xmod_target_delta(xmod_bindings, "phase", _domain_sources, nb, cap=_net_cap)
    else:
        _res_delta = np.zeros(nb); _synth_delta = np.zeros(nb)
        _prev_pitch = np.zeros(nb); _prev_phase = np.zeros(nb)
    # conditionals on its own amplitude → frequency and phase of the NEXT block
    lo, hi = float(p.get("lo", 0.25)), float(p.get("hi", 0.7))
    up, down = float(p.get("up", 1.5)), float(p.get("down", 0.75))
    sh = float(p.get("phase_shift", math.pi / 2))
    af, ap = float(patch.get("amp->freq", 1.0)), float(patch.get("amp->phase", 1.0))
    cm = np.ones(nb); ct = np.zeros(nb)
    loud, quiet = a > hi, a < lo
    cm[1:] = np.where(loud[:-1], up, np.where(quiet[:-1], down, 1.0))
    ct[1:] = np.where(loud[:-1], sh, np.where(quiet[:-1], -sh, 0.0))
    if xmod_bindings:
        cm *= 1.0 + 0.10 * _prev_pitch
        ct += 0.08 * math.pi * _prev_phase

    # GOAVA has deterministic project-seed/slot and live-I/O bases. The I/O
    # mode bends the Golden field from the measured main-synth envelope; it
    # never uses a true/random probability or stochastic draw.
    if goava_io and em is not None and em.size == nb:
        io_env = np.clip(np.nan_to_num(em, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)
        io_delta = np.diff(np.concatenate([[io_env[0]], io_env])) if io_env.size else np.zeros(nb)
        golden_inverse = 0.6180339887498949
        dom = np.clip(dom + 0.22 * (io_env - 0.5), 0.0, 1.0)
        cm *= 1.0 + 0.12 * (io_env - 0.5)
        ct += io_delta * (math.tau * golden_inverse)

    # STOCHASTIC / FRACTAL FIELD / TRIGGER LOCK — canonical-style behaviour exposed
    # on the bottom rack. All zero/neutral values are exact no-ops.
    try:
        stoch = min(1.0, max(0.0, float(p.get("stochastic", 0.0) or 0.0)))
        variation = min(1.0, max(0.0, float(p.get("variation", 0.0) or 0.0)))
        fractal_depth = min(1.0, max(0.0, float(p.get("fractal_depth", 0.0) or 0.0)))
        lock_ms = max(0.0, float(p.get("lock_ms", 0.0) or 0.0))
        trigger_response = min(1.0, max(0.0, float(p.get("trigger_response", 0.0) or 0.0)))
        field_rate = min(1.0, max(0.0, float(p.get("field_rate", 0.5) or 0.0)))
        # MD_STOCH_R31: absolute timeline blocks → the same moment gets the same response however the
        # render is chunked (rows / voices / live blocks): time-invariant.
        _t0 = float(t[0]) if t is not None and getattr(t, "size", 0) else 0.0
        _abs0 = max(0, int(round(_t0 * sr)) // max(1, blk))
        _abs_idx = np.arange(_abs0, _abs0 + nb, dtype=np.int64)
        _prob, _mode = stochastic_probability(p, seed_int, slot)
        if _prob > 0.0 and nb > 0:
            if _mode == "canonical":
                # time-invariant decisions: pure hash of (seed, slot, absolute block)
                fire = _hash_unit(seed_int, slot, _abs_idx, 1) < _prob
                mag = 2.0 * _hash_unit(seed_int, slot, _abs_idx, 2) - 1.0
                depth = 0.10 + 0.25 * float(np.clip(variation if variation > 0.0 else 0.5, 0.0, 1.0))
            else:
                # time-variant fallback: the probability itself drifts along the timeline (golden-rate
                # low-discrepancy sequence), still deterministic so play and export match.
                g = 0.6180339887498949
                pt = _prob * (0.5 + 0.5 * np.sin(_abs_idx * (g * 0.05) + float(slot) * 0.37))
                u_ = np.mod(_abs_idx * g + (float(int(seed_int) % 9973) * 1e-4) + float(slot) * 0.37, 1.0)
                fire = u_ < pt
                mag = np.sin(_abs_idx * 2.399963229728653 + float(slot))
                depth = 0.12
            if np.any(fire):
                f = fire.astype(np.float64)
                cm *= 1.0 + depth * f * mag
                ct += 0.5 * depth * f * mag * sh
                dom = np.clip(dom + 0.25 * depth * f * mag, 0.0, 1.0)
        if stoch > 0.0 or fractal_depth > 0.0 or lock_ms > 0.0:
            bidx = _abs_idx.astype(np.float64)
            phase0 = (float(int(seed_int) % 1048576) * 1e-6) + float(slot) * 0.37
            rate = 0.6180339887498949 + 0.9 * field_rate
            r1 = 0.5 + 0.5 * np.sin((bidx + 1.0) * rate * math.tau + phase0)
            r2 = 0.5 + 0.5 * np.sin((bidx + 1.0) * rate * 2.399963229728653 + phase0 * 1.7)
            if stoch > 0.0:
                cm *= 1.0 + stoch * variation * (r1 * 2.0 - 1.0)
                ct += stoch * (r2 - 0.5) * sh
                dom = np.clip(dom + stoch * 0.35 * (r2 - 0.5), 0.0, 1.0)
            if fractal_depth > 0.0:
                fb = 0.5 + 0.5 * np.sin((bidx + 1.0) * (1.0 + 3.0 * fractal_depth) * 2.399963229728653 + phase0)
                dom = (1.0 - 0.5 * fractal_depth) * dom + 0.5 * fractal_depth * fb
            if lock_ms > 0.0 and trigger_response > 0.0 and nb > 0:
                lock_blocks = min(nb, int(round((lock_ms / 1000.0 * sr / max(1, blk)) * trigger_response)))
                if lock_blocks > 0:
                    cm[:lock_blocks] = cm[0]
                    ct[:lock_blocks] = ct[0]
                    dom[:lock_blocks] = dom[0]
    except Exception:
        pass

    # GROOVEBOX_R23R_WORLD_RECORD_20261103: record this voice's per-block world
    # (loud/quiet decisions, domain weight, and the dimensions) so video reads the same events.
    try:
        start_t = float(t[0]) if t is not None and getattr(t, "size", 0) else 0.0
        start_b = max(0, int(start_t * sr) // blk)
        rec = {
            "start_block": start_b,
            "nb": int(nb),
            "dom": np.asarray(dom, dtype=np.float32).copy(),
            "loud": np.asarray(loud, dtype=bool).copy(),
            "quiet": np.asarray(quiet, dtype=bool).copy(),
            "amp": np.asarray(a, dtype=np.float32).copy(),
            "ball": np.asarray(hb, dtype=np.float32).copy(),
            "ca": np.asarray(ca, dtype=np.float32).copy(),
            "vec": np.stack([xb, yb, zb], axis=1).astype(np.float32).copy(),
            "live": np.asarray(live, dtype=np.float32).copy(),
        }
        _world_put(_world_key(p, seed_int, slot), rec)
    except Exception:
        pass
    y = render(mult0 * (1.0 + af * (cm - 1.0)), turn0 + ap * ct, dom)[:n]
    if em is not None and float(patch.get("main->amp", 0.0)):
        ma = float(patch.get("main->amp", 0.0))
        y = y * (1.0 - ma + ma * np.repeat(em, blk)[:n])
    res_delta = float(np.mean(_res_delta)) if np.size(_res_delta) else 0.0
    res_q = float(p.get("res_q", 30.0)) * (1.0 + 0.25 * res_delta)
    res_mix = float(np.clip(float(p.get("res_mix", 0.25)) + 0.08 * res_delta, 0.0, 1.0))
    y = _resonate(y, sr, base_hz, p.get("resonators", "harmonic"), res_q, res_mix)
    synth_delta = float(np.mean(_synth_delta)) if np.size(_synth_delta) else 0.0
    y *= gsynth * float(np.clip(1.0 + 0.16 * synth_delta, 0.0, 2.0))
    out = np.array(y, dtype=np.float32, copy=True)       # never hand out pooled memory
    _memo_put(_mkey, out)
    return out


_MEUM = 1.1975807343385265188


def _norm(x):
    p = float(np.max(np.abs(x))) if x.size else 0.0
    return x / p if p > 0.0 else np.zeros_like(x)


def exchange(main, geo, md_out, ex, sr, blk):
    """Second stage after the panel (main) and geometric waveforms are complete: they cross-modulate.

    ex (all neutral at their centre / 0):
      talk    0..1  triad knob — 0 = they talk only while the master synth is silent,
                    1 = only while it sounds, 0.5 = always equally
      amount  0..1  modulation depth
      g2m    -1..1  geometric → panel (sign = positive / negative exchange)
      m2g    -1..1  panel → geometric
      bi     -1..1  bidirectional exchange ratio (signals trade a share of each other)
      flux   0..1   Meum geometric-flux indexing of the depth over time (0 = linear only)
    """
    amt = float(ex.get("amount", 0.0) or 0.0)
    if geo is None or amt <= 0.0:
        return main, geo
    g2m, m2g, bi = (float(ex.get(k, 0.0) or 0.0) for k in ("g2m", "m2g", "bi"))
    if not (g2m or m2g or bi):
        return main, geo
    n = main.size
    talk = float(np.clip(ex.get("talk", 0.5), 0.0, 1.0))
    env = np.repeat(block_envelope(md_out, blk), blk)[:n]
    a = amt * 2.0 * (talk * env + (1.0 - talk) * (1.0 - env))       # centre knob → constant amt
    flux = float(np.clip(ex.get("flux", 0.0) or 0.0, 0.0, 1.0))
    if flux > 0.0:
        k = np.arange(n, dtype=np.float64) // blk
        a = a * (1.0 - flux + flux * 2.0 * ((k / _MEUM) % 1.0))     # Meum phyllotaxis index per block
    mn, gn = _norm(main), _norm(geo)
    pm = float(np.max(np.abs(main))) if n else 0.0
    pg = float(np.max(np.abs(geo))) if n else 0.0
    main2 = main * (1.0 + a * g2m * gn)
    geo2 = geo * (1.0 + a * m2g * mn)
    if bi:
        s = 0.5 * a * abs(bi) * (1.0 if bi > 0 else -1.0)
        main2, geo2 = (main2 + s * gn * pm), (geo2 + s * mn * pg)
    return main2, geo2


def lead_io(md_out, inputs, blk):
    """Master-synth lead inputs: each (mode, value 0..1, amount) mixes into or sustains the lead."""
    if not inputs:
        return md_out
    out = md_out
    env = None
    for mode, s, a in inputs:
        if a == 0.0:
            continue
        if mode == "mix":
            # Signed modulation is reversible: negative depth attenuates where
            # positive depth boosts, with the same normalized route budget.
            out = out * np.clip(1.0 + a * (2.0 * s - 1.0), 0.0, 1.0 + _MEUM)
        elif mode == "sustain":
            if env is None:
                env = np.repeat(block_envelope(md_out, blk), blk)[:md_out.size]
            # Signed sustain raises the low-envelope region for positive depth;
            # negative depth reverses that contour. Centre at zero difference.
            out = out * np.clip(1.0 + a * (s - env), 0.0, 1.0 + _MEUM)
    return out


def triad(main, geo, gpw, mix, md_out, params, sr):
    """The voice: (panel × geometrics) against the multidimensional synth, with the pathways
    OUT of this synth applied to the main / geometric synths first:
        ->main.amp  : main × (1 − v + v · env_md)
        ->main.ring : main ← (1 − v) · main + v · main · md      (ring modulation)
        ->geo.amp   : geo  × (1 − v + v · env_md)
    """
    main = np.asarray(main, dtype=np.float64)
    md_out = np.asarray(md_out, dtype=np.float64)
    patch = dict(params.get("patch") or {})
    blk = max(16, int(round(float(params.get("block_ms", 12.0)) * 1e-3 * float(sr))))
    n = main.size
    md_out = lead_io(md_out, params.get("lead_inputs") or (), blk)
    if geo is not None and params.get("exchange"):
        main, geo = exchange(main, np.asarray(geo, dtype=np.float64), md_out, params["exchange"], sr, blk)
    em = None
    if any(float(patch.get(k, 0.0)) for k in ("->main.amp", "->geo.amp")):
        em = np.repeat(block_envelope(md_out, blk), blk)[:n]
    v = float(patch.get("->main.amp", 0.0))
    if v and em is not None:
        main = main * (1.0 - v + v * em)
    v = float(patch.get("->main.ring", 0.0))
    if v:
        main = (1.0 - v) * main + v * main * md_out
    if geo is not None:
        geo = np.asarray(geo, dtype=np.float64)
        v = float(patch.get("->geo.amp", 0.0))
        if v and em is not None:
            geo = geo * (1.0 - v + v * em)
        inner = (1.0 - gpw) * main + gpw * geo
    else:
        inner = main
    # The master synth sits at M × the combined peak of the panel + geometric groups.
    pi = float(np.max(np.abs(inner))) if inner.size else 0.0
    pmd = float(np.max(np.abs(md_out))) if md_out.size else 0.0
    if pi > 0.0 and pmd > 0.0:
        md_out = md_out * (_MEUM * pi / pmd)
    return (1.0 - mix) * inner + mix * md_out


def _register_world_spill():
    """Register the world record with the memory manager so it spills under RAM pressure."""
    try:
        import memory_manager as _mm
        def _spill(need: int) -> int:
            freed = 0
            while _WORLD_ORDER and freed < need:
                k = _WORLD_ORDER.pop(0)
                r = _WORLD.pop(k, None)
                if r is not None:
                    freed += _rec_bytes(r)
                    global _WORLD_BYTES
                    _WORLD_BYTES -= _rec_bytes(r)
            return freed
        def _size() -> int:
            return int(_WORLD_BYTES)
        _mm.manager().register_spill(None, "multidim_world", priority=40, spill=_spill, size=_size)
    except Exception:
        pass


_register_world_spill()
