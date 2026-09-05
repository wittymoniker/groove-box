"""Meum / Operator-Theory / Isosceles-Trig helpers for Mathematician's Groovebox.

These functions intentionally preserve the author's book terminology as a *Groovebox
math dialect*. They are not advertised as replacements for conventional arithmetic or
trigonometry. Signal/game engines use them as deterministic seed-indexing transforms,
where their role is creative/structural and reversible.
"""
from __future__ import annotations
import hashlib, math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence
from meum_constants import (
    MEUM, M, PHI, MEUM_BASIS, MEUM_MINUS_1, MEUM_INV, MEUM_TWO_MINUS,
    MEUM_NORM, meum_power,
)

def isn_inv(x: float) -> float:
    """Book inverse-isosceles-sine: 2*asin(x/2), clamped to real domain."""
    x=max(-2.0,min(2.0,float(x)))
    return 2.0*math.asin(x/2.0)

def isn(theta: float) -> float:
    """Analytic inverse pair used by Groovebox: 2*sin(theta/2)."""
    return 2.0*math.sin(float(theta)/2.0)

def ics(theta: float) -> float:
    """Isosceles complementary coordinate used for symmetric phase indexing.

    The book discusses ics/ics^-1 as a complementary, handedness-relative geometry.
    Groovebox uses this conservative companion definition rather than claiming an
    externally-standard identity: 2*cos(theta/2).
    """
    return 2.0*math.cos(float(theta)/2.0)

def ics_inv(x: float, handedness: float=1.0) -> float:
    x=max(-2.0,min(2.0,float(x)))
    a=2.0*math.acos(x/2.0)
    return a if handedness >= 0 else -a

def _u(seed, label):
    h=hashlib.sha256(f"{seed}|{label}".encode()).digest()
    return int.from_bytes(h[:8],'big')/float(2**64)

def meum_index(seed, label, *, center=True):
    """History-free irrational seed index built from Meum + isosceles phase."""
    u=_u(seed,label)
    # Irrationally separated traversal with bounded isosceles coordinate.
    phase=math.tau*((u*M + MEUM_MINUS_1) % 1.0)
    v=0.5 + 0.5*(isn(phase)/2.0)
    return (2.0*v-1.0) if center else v

def modulation_basis(seed, label):
    keys=tuple(MEUM_BASIS)
    u=_u(seed, label+':basis')
    k=keys[min(len(keys)-1,int(u*len(keys)))]
    return k, MEUM_BASIS[k]

def temporal_stage(t: float, period: float=64.0):
    """Build → modulate → stabilize over each deterministic seed epoch."""
    p=(max(0.0,float(t)) % max(1e-9,float(period)))/float(period)
    if p < MEUM_MINUS_1: return 'build', p/MEUM_MINUS_1
    if p < MEUM_INV: return 'modulate', (p-MEUM_MINUS_1)/(MEUM_INV-MEUM_MINUS_1)
    return 'stabilize', (p-MEUM_INV)/(1.0-MEUM_INV)


def ot_divide(a: float, b: float, *, zero="auto", fallback=0.0, solved=None) -> float:
    """Project OT division with an explicit zero-denominator resolution.

    zero may be: auto, zero, one, inf, numerator/n, fallback, or solved.
    In auto mode 0/0 -> 1 and nonzero/0 -> signed infinity.  Callers that
    mathematically own a different useful result must say so explicitly.
    """
    a=float(a); b=float(b)
    if b != 0.0:
        return a / b
    mode=str(zero or "auto").strip().lower()
    if mode == "auto":
        return 1.0 if a == 0.0 else math.copysign(math.inf, a)
    if mode in ("zero","0"): return 0.0
    if mode in ("one","1"): return 1.0
    if mode in ("inf","infinity"): return math.copysign(math.inf, a if a != 0.0 else 1.0)
    if mode in ("numerator","n"): return a
    if mode in ("solved","x/y","solution"):
        if solved is None: return float(fallback)
        return float(solved)
    return float(fallback)

def ot_inverse_operations(ops: Sequence[tuple]):
    """Symbolic Operator-Theory inverse path: reverse order and paired operator.

    This implements the book's stated add↔subtract, multiply↔divide,
    power↔root transform rule as a symbolic simplifier. It does not globally
    redefine Python arithmetic.
    """
    pair={'+':'-','-':'+','*':'/','/':'*','pow':'root','root':'pow'}
    return [(pair.get(op,op), value) for op,value in reversed(tuple(ops))]

def simplify_transforms(transforms: Iterable[Mapping]):
    """Canonical, history-free reduction of common reversible transforms."""
    mul=1.0; add=0.0; phase=0.0; provenance=[]
    for tr in transforms:
        if not tr or not tr.get('enabled',True): continue
        typ=str(tr.get('type','')).lower(); val=float(tr.get('value',0.0) or 0.0)
        provenance.append(str(tr.get('id',typ)))
        if typ in ('mul','multiply','gain','ratio'): mul*=val
        elif typ in ('div','divide'): mul=ot_divide(mul, val, zero=str(tr.get('zero_policy','auto')), fallback=float(tr.get('zero_fallback',0.0) or 0.0), solved=tr.get('zero_solved'))
        elif typ in ('add','offset'): add+=val
        elif typ in ('sub','subtract'): add-=val
        elif typ in ('phase','phase_offset'): phase+=val
    # exact-ish identity snapping without throwing away provenance
    if abs(mul-1.0)<1e-12: mul=1.0
    if abs(add)<1e-12: add=0.0
    phase=math.fmod(phase, math.tau)
    if abs(phase)<1e-12: phase=0.0
    return {'multiply':mul,'add':add,'phase':phase,'sources':tuple(sorted(provenance))}

def numeric_signature(seed, label, values=()):
    """Meum/OT/isosceles-derived deterministic audiovisual identity."""
    vals=tuple(float(v) for v in values if isinstance(v,(int,float)) and math.isfinite(float(v)))
    q=abs(meum_index(seed, 'sig:'+str(label), center=True))
    geom=abs(isn_inv(2.0*(q-0.5))) / math.pi
    base=108.0*(M**(1.0+4.0*q))
    influence=sum(abs(v) for v in vals[:8])/(1.0+len(vals[:8])) if vals else 0.0
    freq=max(20.0,min(18000.0,base*(1.0+MEUM_MINUS_1*math.tanh(influence))))
    dur=0.04+MEUM_MINUS_1*0.55+(math.e-2.0)*0.18*geom
    harmonics=1+int(7*((q*MEUM_INV + geom*MEUM_MINUS_1)%1.0))
    return {'freq':freq,'duration':dur,'harmonics':harmonics,'meum_index':q,'isn_angle':geom*math.pi}
