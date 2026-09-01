"""Canonical deterministic visual view-space kernel for Groovebox.

No mutable RNG is used. Camera directions come from an equal-area Fibonacci
sphere; coverage selection is deterministic greedy max-min. Scene fingerprints
are order-independent and projection IDs are cryptographic identities of the
canonical scene/view tuple.
"""
from __future__ import annotations
import hashlib, json, math
from typing import Iterable, Mapping, Sequence

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

def composition_fingerprint(objects: Iterable[Mapping], seed=0, abstraction="structural"):
    rows=[]
    for o in objects or []: rows.append(_canon(dict(o)))
    rows.sort(key=lambda x: json.dumps(x,sort_keys=True,separators=(",",":")))
    payload={"seed":_seed_int(seed),"abstraction":abstraction,"objects":rows}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()[:16]

def visual_signal_id(seed, composition_fp, view):
    payload={"seed":_seed_int(seed),"composition":str(composition_fp),"view":_canon(view)}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()[:24]
