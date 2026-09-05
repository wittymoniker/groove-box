"""Canonical deterministic visual view-space kernel for Groovebox.

No mutable RNG is used. Camera directions come from an equal-area Fibonacci
sphere; coverage selection is deterministic greedy max-min. Scene fingerprints
are order-independent and projection IDs are cryptographic identities of the
canonical scene/view tuple.
"""
from __future__ import annotations
import hashlib, json, math
from typing import Iterable, Mapping, Sequence
from universal_field import canonical_field, partition_field, reconstruct_parts, projection as universal_projection, all_projections, invariant_report

PHI = (1.0 + math.sqrt(5.0)) / 2.0
GOLDEN_ANGLE = 2.0 * math.pi * (1.0 - 1.0 / PHI)


# Operator Theory video/game trig via isn · ics · arcisn · arcics.
# book: isn(θ)=2·sin(θ/2) ⇒ sin(θ)=isn(2θ)/2 ; ics similarly for cos.
# Always runs through the isn/ics family (numeric-identical to math.sin/cos).
def _book_isn(x):
    return 2.0 * math.sin(0.5 * float(x))
def _book_ics(x):
    return 2.0 * math.cos(0.5 * float(x))
def _book_isn_inv(y):
    a = max(-1.0, min(1.0, 0.5 * float(y)))
    return 2.0 * math.asin(a)
def _book_ics_inv(y):
    a = max(-1.0, min(1.0, 0.5 * float(y)))
    return 2.0 * math.acos(a)
def vg_sin(x):
    return 0.5 * _book_isn(2.0 * float(x))
def vg_cos(x):
    return 0.5 * _book_ics(2.0 * float(x))
def vg_asin(x):
    x = max(-1.0, min(1.0, float(x)))
    return 0.5 * _book_isn_inv(2.0 * x)
def vg_acos(x):
    x = max(-1.0, min(1.0, float(x)))
    return 0.5 * _book_ics_inv(2.0 * x)


def _seed_int(seed):
    try: return int(float(seed))
    except Exception: return int.from_bytes(hashlib.sha256(str(seed).encode()).digest()[:8], 'big')

def _u(seed, label):
    d = hashlib.sha256(f"{_seed_int(seed)}|{label}".encode()).digest()
    return int.from_bytes(d[:8], 'big') / float(1 << 64)

def fibonacci_view(index: int, count: int, seed=0):
    n = max(1, int(count)); i = max(0, int(index)) % n
    # Equal-area sphere, then deterministic seed rotation.
    z = 1.0 - 2.0 * ((i + 0.5) / n)
    r = math.sqrt(max(0.0, 1.0 - z*z))
    phase = 2.0 * math.pi * _u(seed, "view_phase")
    theta = i * GOLDEN_ANGLE + phase
    x, y = r * vg_cos(theta), r * vg_sin(theta)
    yaw = math.atan2(x, z)
    pitch = vg_asin(max(-1.0, min(1.0, y)))
    return {
        "index": i, "count": n,
        "x": x, "y": y, "z": z,
        "yaw_deg": math.degrees(yaw), "pitch_deg": math.degrees(pitch),
        "roll_deg": 0.0,
        "distance": 1.0,
        "fov_deg": 48.0,
    }

def _vec(v):
    return (float(v.get("x",0)), float(v.get("y",0)), float(v.get("z",1)))

def _ang(a,b):
    ax,ay,az=_vec(a); bx,by,bz=_vec(b)
    na=math.sqrt(ax*ax+ay*ay+az*az) or 1; nb=math.sqrt(bx*bx+by*by+bz*bz) or 1
    c=max(-1,min(1,(ax*bx+ay*by+az*bz)/(na*nb)))
    return vg_acos(c)

def camera_distance(a, b):
    """Angular distance between two canonical camera/view vectors (radians).

    Compatibility helper retained for older visual tests and downstream
    exporters; the canonical implementation is the same spherical metric
    used by ``select_views``.
    """
    return _ang(a, b)


def select_views(count=32, seed=0, existing=()):
    n=max(1,int(count)); pool=[fibonacci_view(i,max(n*2,32),seed) for i in range(max(n*2,32))]
    chosen=list(existing or [])
    out=[]
    while len(out)<n:
        candidates=[v for v in pool if all(v["index"] != e.get("index") for e in chosen+out)]
        if not candidates: break
        if not chosen and not out:
            # deterministic first point, not a random choice
            best=candidates[0]
        else:
            selected=chosen+out
            best=max(candidates, key=lambda v: (min(_ang(v,e) for e in selected), -v["index"]))
        out.append(best)
    return out

def _canon(obj):
    if isinstance(obj, Mapping): return {str(k): _canon(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list,tuple)): return [_canon(x) for x in obj]
    if isinstance(obj,float): return round(obj,12)
    return obj

def instruments_handler(index: int, count: int, seed=0, sequential_nums=()):
    """Pure numeric instrument→visual translator.

    The instrument count changes *sampling density*, not identity placement.
    Slots are fixed on the canonical 64-point lattice; adding/removing an
    instrument therefore adds/removes samples instead of moving existing ones.
    ``compensation`` is inverse-count weighting: fewer instruments get more
    contribution, more instruments get less.  No audio, harmonic, gameplay,
    wall-clock, mutable-RNG, or UI state participates in this mapping.
    """
    n = max(1, min(64, int(count)))
    i = max(0, min(n - 1, int(index)))
    master_slot = i  # fixed identity: existing slots never move when N changes
    identity = (master_slot + 0.5) / 64.0
    seq = []
    for value in sequential_nums or ():
        try:
            v = float(value)
            if math.isfinite(v):
                seq.append(v)
        except Exception:
            continue
    units = []
    if seq:
        lo, hi = min(seq), max(seq)
        units = [0.5 if hi == lo else (v - lo) / (hi - lo) for v in seq]
    numeric_unit = units[i % len(units)] if units else _u(seed, f"instrument_numeric:{master_slot}")
    # Inverse-count compensation preserves the aggregate scale while N changes.
    compensation = 1.0 / float(n)
    # Continuous sample coordinate is fixed to the master lattice; N is only
    # allowed to alter weight, never phase, hue, geometry, or identity.
    phase = 2.0 * math.pi * identity + 2.0 * math.pi * numeric_unit
    # UNIVERSAL_FIELD_2026: part count is factorization only. The underlying
    # field is computed without N; each part carries exactly 1/N of it.
    _uf = canonical_field(seed, "visual-instrument-map", sequential_nums=sequential_nums)
    _upart = partition_field(_uf, n)[i]
    return {
        "index": i,
        "count": n,
        "master_slot": master_slot,
        "identity": identity,
        "numeric_unit": numeric_unit,
        "compensation": compensation,
        "phase": phase,
        "universal_field_id": _uf["field_id"],
        "universal_share": _upart["weight"],
        "universal_coords": _upart["coords"],
    }


def instrument_translation(index: int, count: int, seed=0, sequential_nums=()):
    """Named alias for the canonical instrument→visual translation contract."""
    return instruments_handler(index, count, seed=seed, sequential_nums=sequential_nums)


def instrument_population(count: int, seed=0, sequential_nums=()):
    """Return a complete deterministic population with no external state."""
    n = max(1, min(64, int(count)))
    return [instrument_translation(i, n, seed, sequential_nums) for i in range(n)]


def quantization_error(unit, pixels):
    """Absolute normalized error introduced by mapping a unit interval to pixels."""
    u = float(unit)
    p = max(1, int(pixels))
    q = round(u * p) / float(p)
    return abs(q - u)


def pure_visual_object(index: int, count: int, seed=0, sequential_nums=()):
    """A harmonic/audio/gameplay-free visual object projection.

    This is deliberately boring: identity, normalized numeric position, phase,
    and inverse-count compensation are the only ingredients. It is the audit
    reference for the richer renderer, not an effects generator.
    """
    m = instrument_translation(index, count, seed, sequential_nums)
    return {
        "master_slot": m["master_slot"],
        "identity": m["identity"],
        "numeric_unit": m["numeric_unit"],
        "phase_unit": (m["phase"] / math.tau) % 1.0,
        "compensation": m["compensation"],
    }


def pure_visual_population(count: int, seed=0, sequential_nums=()):
    return [pure_visual_object(i, count, seed, sequential_nums)
            for i in range(max(1, min(64, int(count))))]


def golden_composition_fingerprint(count: int, seed=0, sequential_nums=()):
    """Stable structural render hash used by the regression suite."""
    return composition_fingerprint(
        pure_visual_population(count, seed, sequential_nums), seed=seed,
        abstraction="pure-instrument-visual-v1"
    )


def composition_fingerprint(objects: Iterable[Mapping], seed=0, abstraction="structural"):
    rows=[]
    for o in objects or []: rows.append(_canon(dict(o)))
    rows.sort(key=lambda x: json.dumps(x,sort_keys=True,separators=(",",":")))
    payload={"seed":_seed_int(seed),"abstraction":abstraction,"objects":rows}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()[:16]

def visual_signal_id(seed, composition_fp, view):
    payload={"seed":_seed_int(seed),"composition":str(composition_fp),"view":_canon(view)}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()[:24]


def universal_visual_field(seed=0, composition_fp="0", sequential_nums=(), feature_vector=()):
    """Public visualizer entry point. It does not depend on instrument count."""
    return canonical_field(seed, composition_fp, sequential_nums, feature_vector)

def universal_visual_projection(seed=0, composition_fp="0", kind="canonical_geometry", sequential_nums=(), feature_vector=()):
    return universal_projection(universal_visual_field(seed, composition_fp, sequential_nums, feature_vector), kind)

def universal_visual_invariance(seed=0, composition_fp="0", sequential_nums=(), feature_vector=(), counts=(1,2,4,8,16,32,64)):
    return invariant_report(universal_visual_field(seed, composition_fp, sequential_nums, feature_vector), counts)
