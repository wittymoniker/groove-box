"""Shared full-graph script context for Mathematician's Groovebox.

This module is intentionally small and dependency-light so audio, visual, game,
canonical writers, heuristic writers, and random script authoring can share one
variable contract without each subsystem inventing its own reduced seed view.
"""
from __future__ import annotations

import ast
import inspect
import math
from typing import Any, Dict, Iterable, Mapping, Optional


class GraphView(dict):
    """Dict with read-only-style attribute access (graph.x and graph['x'])."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except Exception:
        return float(default)
    return v if math.isfinite(v) else float(default)


def _stable_numeric_id(text: Any) -> float:
    # Deterministic FNV-1a style fold represented exactly enough for script use.
    h = 2166136261
    for b in str(text or "").encode("utf-8", "replace"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return float(h)


def build_graph_context(*, t: float = 0.0, t_norm: Optional[float] = None,
                        x: float = 0.0, y: float = 0.0, z: float = 0.0,
                        seed: float = 0.0, seed_w: Optional[float] = None,
                        graph_index: int = 0, graph_count: int = 1,
                        slot: int = 0, sequence: int = 1, step: int = 0,
                        bpm: float = 120.0, sample_rate: float = 44100.0,
                        domain_value: float = 0.0, domain_weight: float = 1.0,
                        graph_id: Any = "", domain_id: Any = "",
                        canonical_context: Optional[Mapping[str, Any]] = None,
                        values: Optional[Iterable[float]] = None,
                        variables: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Create the one graph payload used by every scriptable subsystem.

    The public scalar aliases intentionally avoid requiring attribute access,
    while ``graph`` allows ergonomic ``graph.x`` / ``graph.energy`` reads.
    """
    t = _finite(t)
    tn = _finite(t if t_norm is None else t_norm)
    x, y, z = _finite(x), _finite(y), _finite(z)
    seed = _finite(seed)
    sw = abs(seed) % 1.0 if seed_w is None and abs(seed) > 1.0 else _finite(abs(seed) if seed_w is None else seed_w)
    radius = math.sqrt(x*x + y*y + z*z)
    angle = math.atan2(y, x)
    energy = math.tanh(0.5 * (x*x + y*y + z*z))
    curvature = math.tanh(abs(x*y + y*z + z*x))
    phase = math.fmod(t + angle, math.tau)
    scalar = (0.50*x + 0.35*y + 0.15*z) / (1.0 + 0.50*abs(x) + 0.35*abs(y) + 0.15*abs(z)) if (x or y or z) else seed
    count = max(1, int(graph_count or 1))
    index = int(graph_index or 0)
    graph = GraphView({
        "t": t, "t_norm": tn, "x": x, "y": y, "z": z,
        "seed": seed, "seed_w": sw, "scalar": scalar,
        "radius": radius, "angle": angle, "energy": energy,
        "curvature": curvature, "phase": phase,
        "u": 0.5 + 0.5 * math.tanh(x),
        "v": 0.5 + 0.5 * math.tanh(y),
        "w": 0.5 + 0.5 * math.tanh(z),
        "index": index, "count": count, "slot": int(slot or 0),
        "sequence": int(sequence or 1), "step": int(step or 0),
        "bpm": _finite(bpm, 120.0), "sample_rate": _finite(sample_rate, 44100.0),
        "domain_value": _finite(domain_value), "domain_weight": _finite(domain_weight, 1.0),
        "graph_id": _stable_numeric_id(graph_id), "domain_id": _stable_numeric_id(domain_id),
    })
    if values is not None:
        vv = []
        for value in values:
            fv = _finite(value, float("nan"))
            if math.isfinite(fv):
                vv.append(fv)
        graph["values"] = tuple(vv)
    if variables:
        for key, value in variables.items():
            if isinstance(key, str) and key.isidentifier() and isinstance(value, (int, float, bool)):
                graph[key] = _finite(value)
    if canonical_context:
        for key, value in canonical_context.items():
            if isinstance(key, str) and key.isidentifier() and isinstance(value, (int, float, bool)):
                graph[key] = _finite(value)
    return dict(graph)


def graph_context_env(context: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten graph context into script variables plus the ``graph`` view."""
    c = dict(context or {})
    env = dict(c)
    env.update({
        "graph": GraphView(c),
        "graph_x": _finite(c.get("x")), "graph_y": _finite(c.get("y")), "graph_z": _finite(c.get("z")),
        "graph_scalar": _finite(c.get("scalar")), "graph_radius": _finite(c.get("radius")),
        "graph_angle": _finite(c.get("angle")), "graph_energy": _finite(c.get("energy")),
        "graph_curvature": _finite(c.get("curvature")), "graph_phase": _finite(c.get("phase")),
        "graph_u": _finite(c.get("u")), "graph_v": _finite(c.get("v")), "graph_w": _finite(c.get("w")),
        "graph_index": int(c.get("index", 0) or 0), "graph_count": max(1, int(c.get("count", 1) or 1)),
        "graph_slot": int(c.get("slot", 0) or 0),
        "sequence_index": int(c.get("sequence", 1) or 1), "step_index": int(c.get("step", 0) or 0),
        "domain_value": _finite(c.get("domain_value")), "domain_weight": _finite(c.get("domain_weight"), 1.0),
        "graph_id": _finite(c.get("graph_id")), "domain_id": _finite(c.get("domain_id")),
        "graph_vector": (_finite(c.get("x")), _finite(c.get("y")), _finite(c.get("z"))),
    })
    return env


def coerce_graph_result(result: Any) -> Dict[str, float]:
    """Normalize scalar/vector/named script outputs into finite channels."""
    out: Dict[str, float] = {}
    if isinstance(result, Mapping):
        for key, value in result.items():
            if isinstance(key, str) and isinstance(value, (int, float, bool)):
                fv = _finite(value, float("nan"))
                if math.isfinite(fv):
                    out[key] = fv
    elif isinstance(result, (list, tuple)):
        vals = [_finite(v, float("nan")) for v in result]
        vals = [v for v in vals if math.isfinite(v)]
        if vals:
            out["scalar"] = vals[0]
        if len(vals) >= 2:
            out["x"], out["y"] = vals[0], vals[1]
        if len(vals) >= 3:
            out["z"] = vals[2]
    elif isinstance(result, (int, float, bool)):
        out["scalar"] = _finite(result)
    for alias in ("wave", "value", "drive"):
        if "scalar" not in out and alias in out:
            out["scalar"] = out[alias]
            break
    return out



def _ot_rewrite_graph_ast(tree, scope):
    """Graph/seed expression trees are not rewritten.

    Author text is evaluated as written.  Named math_* / ot_* in the env
    follow their own OT-toggle definitions at call time.
    """
    return tree



def evaluate_graph_script(script: str, context: Mapping[str, Any], *,
                          function_names=("evaluate_wave", "global_script", "evaluate", "main"),
                          extra_env: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    """Evaluate an authored graph script at one shared graph coordinate.

    Existing 3-argument ``evaluate_wave(x,y,z)`` and 3-argument
    ``global_script(t,name,i)`` forms remain valid. New writers may request any
    named graph-context variable or ``graph`` itself.
    """
    raw = str(script or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return {}
    env = graph_context_env(context)
    env.update({"abs": abs, "min": min, "max": max, "sum": sum, "len": len, "range": range,
                "float": float, "int": int, "bool": bool, "round": round,
                "sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt,
                "exp": math.exp, "log": math.log, "log2": math.log2, "atan2": math.atan2,
                "floor": math.floor, "ceil": math.ceil, "pi": math.pi, "tau": math.tau, "e": math.e})
    if extra_env:
        env.update(dict(extra_env))
    scope = {"__builtins__": {}}
    scope.update(env)
    local = scope
    try:
        tree = ast.parse(raw, mode="exec")
        tree = _ot_rewrite_graph_ast(tree, scope)
        exec(compile(tree, "<groovebox-graph-script>", "exec"), scope, scope)
    except Exception:
        # Expression-only compatibility.
        try:
            etree = _ot_rewrite_graph_ast(ast.parse(raw, mode="eval"), scope)
            return coerce_graph_result(eval(compile(etree, "<groovebox-graph-expr>", "eval"), scope, scope))
        except Exception:
            return {}
    for fname in function_names:
        fn = local.get(fname)
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
            args = []
            kwargs = {}
            for name, param in sig.parameters.items():
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                if name == "name":
                    value = context.get("name", "")
                elif name == "i":
                    value = int(context.get("slot", context.get("index", 0)) or 0)
                elif name in local:
                    value = local[name]
                elif name in context:
                    value = context[name]
                elif param.default is not inspect._empty:
                    continue
                else:
                    raise KeyError(name)
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    args.append(value)
                else:
                    kwargs[name] = value
            return coerce_graph_result(fn(*args, **kwargs))
        except Exception:
            continue
    # If the script assigned a conventional result variable, honor it.
    for key in ("result", "output", "value", "wave", "scalar"):
        if key in local:
            result = coerce_graph_result(local[key])
            if result:
                return result
    return {}


GRAPH_SCRIPT_VARIABLES = (
    "t", "t_norm", "x", "y", "z", "seed", "seed_w", "graph",
    "graph_x", "graph_y", "graph_z", "graph_scalar", "graph_radius", "graph_angle",
    "graph_energy", "graph_curvature", "graph_phase", "graph_u", "graph_v", "graph_w",
    "graph_index", "graph_count", "graph_slot", "sequence_index", "step_index",
    "domain_value", "domain_weight", "graph_id", "domain_id", "bpm", "sample_rate",
    "graph_vector",
)
