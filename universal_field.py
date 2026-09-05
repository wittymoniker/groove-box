"""Decomposition-invariant Universal Field for Mathematician's Groovebox.

The canonical field is computed *before* any instrument/object partition.  Part
objects are weighted factorizations of the same field, so N is a rendering /
work-distribution choice rather than an identity input.  Audio, visualizer and
game code may project the same field independently; the game is never the
source of visual identity.

Rational anchors are reserved for identity/symmetry/partitioning. Irrational
ratios are used only for traversal, phase coverage and non-short-repeat index
selection.
"""
from __future__ import annotations
import hashlib, json, math
from functools import lru_cache
from typing import Any, Dict, Iterable, Mapping, Sequence
from meum_constants import (
    M, PHI, MEUM_MINUS_1, MEUM_INV, MEUM_TWO_MINUS, MEUM_NORM,
)
SCALE_BASIS = {
    "zero": 0.0,
    "half": 0.5,
    "unity": 1.0,
    "M-1": MEUM_MINUS_1,
    "1/M": MEUM_INV,
    "2-M": MEUM_TWO_MINUS,
    "(M-1)/M": MEUM_NORM,
    "sqrt2-1": math.sqrt(2.0) - 1.0,
    "phi-1": PHI - 1.0,
    "e-2": math.e - 2.0,
    "pi-3": math.pi - 3.0,
}

PROJECTION_TYPES = (
    "canonical_geometry", "meum_field", "isosceles_scope", "ot_transform_graph",
    "phase_torus", "lissajous_orbit", "spectrogram", "partial_constellation",
    "canonical_delta", "sequence_geometry", "playlist_timeline_terrain",
    "number_theory_scope", "fractal_lsystem", "complex_plane", "wave_surface",
    "vector_flow_field", "seed_fingerprint", "network_radio_constellation",
    "game_world_map", "avg_correspondence",
)

_FIELD_NAMES = (
    "identity", "symmetry", "energy", "phase_x", "phase_y", "phase_z",
    "spectral_centroid", "spectral_spread", "partial_density", "rhythm",
    "sequence_curvature", "automation_slope", "modulation", "canonical_delta",
    "prime_residue", "farey_balance", "lattice_x", "lattice_y", "lattice_z",
    "fractal_depth", "complex_real", "complex_imag", "flow", "temporal_stage",
)


def _canon(obj: Any) -> Any:
    if isinstance(obj, Mapping): return {str(k): _canon(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)): return [_canon(x) for x in obj]
    if isinstance(obj, float): return round(obj, 14)
    return obj


def _u(seed: Any, label: str) -> float:
    d = hashlib.sha256(f"{seed}|{label}".encode("utf-8", "replace")).digest()
    return int.from_bytes(d[:8], "big") / float(1 << 64)


def _finite_values(values: Iterable[Any]) -> list[float]:
    out=[]
    for x in values or ():
        try:
            v=float(x)
            if math.isfinite(v): out.append(v)
        except Exception: pass
    return out


def canonical_field(seed: Any, composition_fingerprint: str = "0", sequential_nums: Sequence[Any] = (), feature_vector: Sequence[Any] = ()) -> Dict[str, Any]:
    """Return the canonical Universal Field. Never accepts part/instrument count."""
    seq=_finite_values(sequential_nums); feat=_finite_values(feature_vector)
    payload={"seed":str(seed),"composition":str(composition_fingerprint),"seq":[round(v,14) for v in seq],"features":[round(v,14) for v in feat]}
    source_hash=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    vals: Dict[str,float]={}
    scale_cycle=(1.0, 0.5, MEUM_MINUS_1, MEUM_INV, MEUM_TWO_MINUS, MEUM_NORM, math.sqrt(2)-1, PHI-1, math.e-2, math.pi-3)
    seq_mean=sum(seq)/len(seq) if seq else 0.0
    feat_mean=sum(feat)/len(feat) if feat else 0.0
    for i,name in enumerate(_FIELD_NAMES):
        base=_u(source_hash, name)
        # Irrational scale rotates coverage; rational 1/2 and 1 remain anchors.
        s=scale_cycle[i % len(scale_cycle)]
        coupled=(base + (seq_mean*MEUM_MINUS_1 + feat_mean*(PHI-1.0))*s) % 1.0
        vals[name]=coupled
    # exact structural anchors, kept distinct from traversal coordinates
    vals["identity"] = _u(source_hash, "identity")
    vals["symmetry"] = 0.5 + 0.5 * (2.0 * _u(source_hash,"symmetry") - 1.0)
    field={"version":"universal-field-v1","source_hash":source_hash,"composition_fingerprint":str(composition_fingerprint),"seed":str(seed),"scales":dict(SCALE_BASIS),"coords":vals}
    field["field_id"]=hashlib.sha256(json.dumps(_canon(field),sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()[:24]
    return field


@lru_cache(maxsize=1)
def _load_native_meum_space():
    """Load the optional canonical C++ Meum traversal kernel once."""
    try:
        import ctypes
        from pathlib import Path
        root=Path(__file__).resolve().parent
        candidates=(
            root/'native'/'libgroovebox_accel.so', root/'cpp'/'libgroovebox_accel.so',
            root/'native'/'groovebox_accel.dll', root/'native'/'libgroovebox_accel.dylib',
        )
        libpath=next((p for p in candidates if p.is_file()), None)
        if libpath is None: return None
        lib=ctypes.CDLL(str(libpath)); Pd=ctypes.POINTER(ctypes.c_double)
        fn=lib.gb_meum_space_f64
        fn.argtypes=[ctypes.c_size_t,ctypes.c_size_t,ctypes.c_double,Pd,Pd,Pd,Pd]
        fn.restype=None
        return fn
    except Exception:
        return None


def _meum_space_python_reference(start: int, count: int) -> Dict[str, list[float]]:
    """Portable multiplication reference used when no native kernel is present."""
    basis=(MEUM_MINUS_1,MEUM_INV,PHI-1.0,math.sqrt(2.0)-1.0)
    cols=[ [((i*b) % 1.0) for i in range(start,start+count)] for b in basis ]
    return dict(zip(("meum_minus_1","meum_inverse","phi_minus_1","sqrt2_minus_1"),cols))


def meum_space(start: int, count: int) -> Dict[str, list[float]]:
    """Deterministic irrational traversal; identity/conservation remain rational.

    Large traversals use the optional C++ recurrence kernel: the starting phase is
    formed once at long-double precision and subsequent points advance additively.
    This is both faster and less vulnerable to large-index multiply precision loss.
    The portable multiplication reference remains authoritative when native code is
    unavailable, so generated/project identity never depends on having the library.
    """
    start=max(0,int(start)); count=max(0,int(count))
    if count == 0:
        return {k:[] for k in ("meum_minus_1","meum_inverse","phi_minus_1","sqrt2_minus_1")}
    fn=_load_native_meum_space() if count >= 128 else None
    if fn is not None:
        try:
            import ctypes
            import numpy as np
            Pd=ctypes.POINTER(ctypes.c_double)
            cols=[np.empty(count,dtype=np.float64) for _ in range(4)]
            fn(start,count,M,*[a.ctypes.data_as(Pd) for a in cols])
            return dict(zip(("meum_minus_1","meum_inverse","phi_minus_1","sqrt2_minus_1"),
                            [a.tolist() for a in cols]))
        except Exception:
            pass
    return _meum_space_python_reference(start,count)


def partition_field(field: Mapping[str,Any], count: int) -> list[Dict[str,Any]]:
    """Factor a field into N additive part objects without changing identity."""
    n=max(1,int(count)); coords=dict(field.get("coords") or {})
    # Exact rational partition bounds; irrational ratios do not belong here.
    return [{"index":i,"count":n,"lo":i/n,"hi":(i+1)/n,"weight":1.0/n,
             "field_id":field.get("field_id"),
             "coords":{k:float(v)/n for k,v in coords.items()}}
            for i in range(n)]


def reconstruct_parts(parts: Sequence[Mapping[str,Any]]) -> Dict[str,float]:
    out: Dict[str,float]={}
    # math.fsum minimizes partition-count-dependent accumulation error.
    keys=sorted({k for p in parts or () for k in (p.get("coords") or {})})
    for k in keys:
        out[k]=math.fsum(float((p.get("coords") or {}).get(k,0.0)) for p in parts)
    return out


def decomposition_error(field: Mapping[str,Any], count: int) -> float:
    original={k:float(v) for k,v in (field.get("coords") or {}).items()}
    rec=reconstruct_parts(partition_field(field,count))
    return max([abs(original[k]-rec.get(k,0.0)) for k in original] or [0.0])


_PROJECTION_CACHE: Dict[tuple, Dict[str,Any]] = {}

def clear_projection_cache() -> None:
    """Drop representation caches without changing any canonical identity."""
    _PROJECTION_CACHE.clear()

def projection(field: Mapping[str,Any], kind: str) -> Dict[str,Any]:
    """Selective/subtractive projection of one invariant field.

    `selected` + `complement` reconstructs the original coordinate dictionary;
    projections therefore reveal different views without inventing new state.
    """
    kind=str(kind).strip().lower()
    if kind not in PROJECTION_TYPES: raise ValueError(f"unknown projection: {kind}")
    fid=str(field.get("field_id", ""))
    key=(fid, kind)
    cached=_PROJECTION_CACHE.get(key)
    if cached is not None:
        return cached
    coords={k:float(v) for k,v in (field.get("coords") or {}).items()}
    selected={}; complement={}
    for name,v in coords.items():
        # Stable 2/3-ish selection using a Meum-indexed hash. No mutable RNG.
        gate=_u(field.get("field_id","0"), f"{kind}|{name}")
        if gate < MEUM_INV: selected[name]=v
        else: complement[name]=v
    if not selected and coords:
        k=sorted(coords)[0]; selected[k]=coords[k]; complement.pop(k,None)
    pid=hashlib.sha256(f"{field.get('field_id')}|{kind}".encode()).hexdigest()[:24]
    result={"kind":kind,"projection_id":pid,"field_id":field.get("field_id"),"selected":selected,"complement":complement,
            "selected_scale":MEUM_MINUS_1,"complement_scale":MEUM_TWO_MINUS}
    # Representation cache only: never enters field_id or correspondence identity.
    if len(_PROJECTION_CACHE) >= 512:
        _PROJECTION_CACHE.pop(next(iter(_PROJECTION_CACHE)))
    _PROJECTION_CACHE[key]=result
    return result


def all_projections(field: Mapping[str,Any]) -> Dict[str,Dict[str,Any]]:
    return {k:projection(field,k) for k in PROJECTION_TYPES}


def game_projection(field: Mapping[str,Any]) -> Dict[str,Any]:
    """Game-facing interpretation. This consumes the field; it does not create it."""
    c=field.get("coords") or {}
    def g(k,d=0.5): return float(c.get(k,d))
    return {
        "field_id":field.get("field_id"),
        "world_scale":0.5 + g("lattice_x"),
        "terrain":(g("sequence_curvature"),g("lattice_y"),g("lattice_z")),
        "motion":(g("flow"),g("phase_x"),g("phase_y"),g("phase_z")),
        "activity":g("rhythm"), "event_density":g("partial_density"),
        "npc_variation":g("modulation"), "lighting":g("energy"),
        "temporal_stage":g("temporal_stage"), "canonical_delta":g("canonical_delta"),
        "map_projection":projection(field,"game_world_map"),
        "avg_projection":projection(field,"avg_correspondence"),
    }


def invariant_report(field: Mapping[str,Any], counts=(1,2,4,8,16,32,64,128)) -> Dict[str,Any]:
    errors={int(n):decomposition_error(field,int(n)) for n in counts}
    return {"field_id":field.get("field_id"),"errors":errors,"max_error":max(errors.values()) if errors else 0.0,
            "pass":all(e <= 1e-12 for e in errors.values())}

# =============================================================================
# TOTAL CORRESPONDENCE + SELF-PROCEDURE 2026
# =============================================================================
def projection_reconstruct(projected: Mapping[str,Any]) -> Dict[str,float]:
    """Reconstruct one selective/subtractive projection back to field coords."""
    sel={k:float(v) for k,v in (projected.get("selected") or {}).items()}
    comp={k:float(v) for k,v in (projected.get("complement") or {}).items()}
    out=dict(comp); out.update(sel)
    return out


def _coord_error(a: Mapping[str,Any], b: Mapping[str,Any]) -> float:
    keys=sorted(set(a)|set(b))
    return max([abs(float(a.get(k,0.0))-float(b.get(k,0.0))) for k in keys] or [0.0])


def minimal_projection_cover(field: Mapping[str,Any]) -> Dict[str,Any]:
    """Greedy minimal-ish cover of visible/selective coordinates.

    This is a representation optimization only. It never changes field identity.
    The complement remains available for exact selective/subtractive recovery.
    """
    coords=set((field.get("coords") or {}).keys())
    projections={k:projection(field,k) for k in PROJECTION_TYPES}
    remaining=set(coords); chosen=[]
    while remaining:
        best=None; gain=set()
        for k,p in projections.items():
            if k in chosen: continue
            g=set(p.get("selected",{})) & remaining
            if len(g)>len(gain) or (len(g)==len(gain) and g and (best is None or k<best)):
                best, gain=k,g
        if not best or not gain: break
        chosen.append(best); remaining-=gain
    # Any coordinate missed by all display selections is still represented by the
    # canonical geometry/complement path. This does not invent new data.
    if remaining and "canonical_geometry" not in chosen: chosen.append("canonical_geometry")
    return {
        "field_id":field.get("field_id"), "chosen":chosen,
        "covered":sorted(coords-remaining), "fallback":sorted(remaining),
        "coordinate_count":len(coords), "projection_count":len(chosen),
    }


def intrinsic_complexity(field: Mapping[str,Any]) -> Dict[str,float]:
    """Count-independent information/structure descriptors for self-procedure."""
    vals=[float(v) for v in (field.get("coords") or {}).values()]
    if not vals: return {"entropy":0.0,"spread":0.0,"activity":0.0,"score":0.0}
    # Fixed 16-bin Shannon entropy; independent of part/object decomposition.
    bins=[0]*16
    for v in vals: bins[min(15,max(0,int((v%1.0)*16.0)))]+=1
    n=float(len(vals)); ent=0.0
    for c in bins:
        if c:
            p=c/n; ent-=p*math.log2(p)
    ent/=4.0 # normalize max 16-bin entropy to [0,1]
    mean=math.fsum(vals)/n
    spread=math.sqrt(math.fsum((v-mean)**2 for v in vals)/n)
    activity=math.fsum(abs(v-0.5) for v in vals)/n*2.0
    # Rational structural average; irrational values are not used to define identity.
    score=max(0.0,min(1.0,(ent+min(1.0,spread*math.sqrt(12.0))+activity)/3.0))
    return {"entropy":ent,"spread":spread,"activity":activity,"score":score}


def self_procedure(field: Mapping[str,Any], max_parts: int=128) -> Dict[str,Any]:
    """Choose a sufficient representation from the field itself.

    Counts are *downstream* rendering resolutions. They can be replaced by any N
    without changing canonical identity; invariant errors are reported explicitly.
    """
    c=intrinsic_complexity(field); s=float(c["score"])
    max_parts=max(1,int(max_parts))
    # structural powers-of-two keep exact hierarchy/coarsening relationships.
    levels=[1,2,4,8,16,32,64,128]
    levels=[n for n in levels if n<=max_parts] or [1]
    idx=min(len(levels)-1,int(math.floor(s*len(levels))))
    base=levels[idx]
    # Domain detail differs, but every count factors the same field.
    counts={
        "audio":base,
        "visual":levels[min(len(levels)-1,idx+1 if s>0.5 else idx)],
        "game":levels[min(len(levels)-1,idx+1 if s>0.66 else idx)],
        "ui":levels[max(0,idx-1)],
        "network":levels[max(0,idx-2)],
    }
    cover=minimal_projection_cover(field)
    errors={k:decomposition_error(field,n) for k,n in counts.items()}
    return {
        "version":"self-procedure-v1", "field_id":field.get("field_id"),
        "intrinsic_complexity":c, "part_counts":counts,
        "visual_projection_cover":cover,
        "invariance_errors":errors, "max_invariance_error":max(errors.values()) if errors else 0.0,
        "invariant":all(e<=1e-12 for e in errors.values()),
        "policy":{
            "identity_partition":"rational", "hierarchy":"powers-of-two",
            "irrational_use":"phase/traversal/index differentiation only",
        },
    }


def correspondence_manifest(field: Mapping[str,Any], event: Mapping[str,Any] | None=None) -> Dict[str,Any]:
    """Trace one canonical identity through A/V/G/UI/Network sibling domains.

    'Total correspondence' here means exact provenance/identity correspondence,
    not a claim that every lossy domain is mathematically invertible.
    """
    fid=str(field.get("field_id") or "")
    event_id=str((event or {}).get("event_id") or "")
    plan=self_procedure(field)
    cover=plan["visual_projection_cover"]["chosen"]
    domains={}
    for name in ("audio","visual","game","ui","network"):
        payload={"field_id":fid,"domain":name,"event_id":event_id,"parts":plan["part_counts"][name]}
        if name=="visual": payload["projection_cover"]=cover
        if name=="game": payload["projection_id"]=game_projection(field).get("map_projection",{}).get("projection_id")
        did=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        domains[name]={**payload,"domain_id":did,"source_field_id":fid}
    ok=bool(fid) and all(d.get("source_field_id")==fid for d in domains.values()) and plan["invariant"]
    return {
        "version":"total-correspondence-v1", "field_id":fid, "event_id":event_id,
        "domains":domains, "self_procedure":plan,
        "identity_correspondence":ok,
        "correspondence_score":1.0 if ok else 0.0,
        "note":"Identity/provenance correspondence; lossy projections need not be invertible.",
    }


def correspondence_verify(field: Mapping[str,Any], manifest: Mapping[str,Any]) -> Dict[str,Any]:
    fid=str(field.get("field_id") or ""); domains=manifest.get("domains") or {}
    mismatches=[k for k,v in domains.items() if str((v or {}).get("source_field_id") or "")!=fid]
    # Every selective/subtractive visual projection can be reconstructed exactly.
    projection_errors={}
    for kind in PROJECTION_TYPES:
        p=projection(field,kind)
        projection_errors[kind]=_coord_error(field.get("coords") or {},projection_reconstruct(p))
    max_pe=max(projection_errors.values()) if projection_errors else 0.0
    ok=bool(fid) and not mismatches and max_pe<=1e-12 and bool((manifest.get("self_procedure") or {}).get("invariant",False))
    return {"field_id":fid,"pass":ok,"mismatches":mismatches,"projection_errors":projection_errors,"max_projection_error":max_pe}
