"""Shared full-graph context for Groovebox script/writer compatibility.

This module is intentionally small and allocation-light. It gives Seed, Instrument,
Algorithm, Domain, Canonical, audio/video and game code one deterministic vocabulary
without forcing realtime paths to eval arbitrary Python.
"""
from __future__ import annotations
import hashlib, json, math

GRAPH_CONTEXT_VERSION = "full_graph_v1"
GRAPH_VARIABLES = (
    "t", "t_norm", "x", "y", "z", "seed", "seed_w",
    "graph_radius", "graph_phase", "graph_energy", "graph_index", "graph_slot",
    "graph_u", "graph_v", "graph_w",
)

def _finite(v, default=0.0):
    try:
        f=float(v)
        return f if math.isfinite(f) else float(default)
    except Exception:
        return float(default)

def build_graph_context(*, t=0.0, t_norm=None, x=0.0, y=0.0, z=0.0,
                        seed=0.0, seed_w=None, graph_index=0, graph_slot=0,
                        energy=0.0):
    t=_finite(t); tn=_finite(t if t_norm is None else t_norm)
    x=_finite(x); y=_finite(y); z=_finite(z); s=_finite(seed)
    sw=abs(s)%1.0 if seed_w is None and abs(s)>1.0 else abs(s) if seed_w is None else _finite(seed_w)
    r=math.sqrt(x*x+y*y+z*z)
    phase=math.atan2(y,x) if (x or y) else 0.0
    # bounded aliases are handy for writers that need stable parameter-space inputs
    den=max(1.0,r)
    u=x/den; v=y/den; w=z/den
    return {
        "graph_context_version": GRAPH_CONTEXT_VERSION,
        "t":t, "t_norm":tn, "x":x, "y":y, "z":z, "seed":s, "seed_w":_finite(sw),
        "graph_radius":r, "graph_phase":phase, "graph_energy":_finite(energy),
        "graph_index":int(graph_index), "graph_slot":int(graph_slot),
        "graph_u":u, "graph_v":v, "graph_w":w,
    }

def context_fingerprint(payload):
    try:
        raw=json.dumps(payload, sort_keys=True, separators=(",",":"), default=str)
    except Exception:
        raw=repr(payload)
    return hashlib.sha256(raw.encode("utf-8","replace")).hexdigest()[:16]

def coerce_graph_output(value):
    """Return scalar + optional vector/named outputs from a script result."""
    if isinstance(value, dict):
        vals=[]
        for k in ("value","x","y","z","pitch","amp","pan","filter","visual","game"):
            if k in value:
                try: vals.append((k,float(value[k])))
                except Exception: pass
        scalar=next((v for k,v in vals if k=="value"), vals[0][1] if vals else 0.0)
        return {"scalar":scalar,"named":dict(vals)}
    if isinstance(value,(list,tuple)):
        vals=[]
        for v in value:
            try: vals.append(float(v))
            except Exception: pass
        return {"scalar": vals[0] if vals else 0.0, "vector": vals}
    try: return {"scalar":float(value)}
    except Exception: return {"scalar":0.0}
