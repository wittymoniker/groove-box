"""GROOVEBOX_R124_PARAM_LINEAGE: "why did this change?" — every influence on one parameter.

``lineage(app, param)`` walks the shared state and lists every source that touches a parameter name:
route handles, patch cables, mod-matrix rows, automation lanes, Mod Path (mm_fields) poles, morph
bridge, constraint rules and the instrument's own stored value. Matching is by name fragment
(case-insensitive), so "cutoff" finds "filter_cutoff", "cutoff_hz", …
"""
from __future__ import annotations


def _walk(obj, path="", depth=0):
    if depth > 7:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            yield p, k, v
            yield from _walk(v, p, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj[:512]):
            p = f"{path}[{i}]"
            yield p, i, v
            yield from _walk(v, p, depth + 1)


SOURCES = (
    ("route handles", "route_handles"), ("patch cables", "patch_cables"), ("instrument routes", "instrument_routes"),
    ("mod matrix", "mod_matrix"), ("automation lanes", "automation_lanes"), ("automation bus", "automation_bus_state"),
    ("parameter state", "instrument_param_state"), ("morph bridge", "global_morph_state"),
)


def lineage(app, param, instrument=None, limit=200):
    q = str(param).lower().strip()
    out = []
    if not q:
        return out
    for label, attr in SOURCES:
        root = getattr(app, attr, None)
        if root is None:
            continue
        for path, key, val in _walk(root):
            hit = q in str(key).lower() or (isinstance(val, str) and q in val.lower())
            if not hit:
                continue
            if instrument and instrument not in path and not (isinstance(val, str) and instrument in val):
                if attr not in ("mod_matrix", "global_morph_state"):
                    continue
            shown = val if isinstance(val, (int, float, str, bool)) or val is None else type(val).__name__
            out.append({"source": label, "path": f"{attr}.{path}", "value": shown})
            if len(out) >= limit:
                return out
    try:
        import mm_fields
        st = mm_fields.settings(app)
        tgt = str(st.get("target", "")).lower()
        if q in tgt or q in str(st.get("param", "")).lower():
            out.append({"source": "Mod Path", "path": "mm_fields.settings", "value": f"{len(st.get('points', []))} poles · mag {st.get('mag')}"})
    except Exception:
        pass
    try:
        bank = (getattr(app, "instrument_sequence_banks", {}) or {}).get(instrument or "") or {}
        for idx, seq in bank.items():
            if isinstance(seq, dict) and "constraint_rules" in seq and q in ("pitch", "pitches", "steps", "density", "key"):
                out.append({"source": "constraint composer", "path": f"sequence {idx}", "value": seq["constraint_rules"]})
    except Exception:
        pass
    return out


def text(app, param, instrument=None):
    rows = lineage(app, param, instrument)
    if not rows:
        return f"No source touches “{param}”."
    w = max(len(r["source"]) for r in rows)
    return "\n".join(f"{r['source']:<{w}}  {r['path']}  =  {r['value']}" for r in rows)
