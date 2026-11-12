"""PROCESS_PREDICT_20261112: multidimensional prediction without touching processes.

Each lane of the process tree is a dimension. The model predicts every lane
from the others using only the descriptors (priority, name, pool width). It
never reads a live process, a thread, or a queue.
"""
from __future__ import annotations
import hashlib

LANES = (
    {"name": "audio callback", "priority": 5, "pool": "audio", "width": 1},
    {"name": "UI events", "priority": 4, "pool": "ui", "width": 1},
    {"name": "Live Player record writer", "priority": 3, "pool": "record", "width": 1},
    {"name": "export / mux workers", "priority": 2, "pool": "export", "width": 2},
    {"name": "sCode visual and background analysis", "priority": 1, "pool": "scode", "width": 2},
)

POOLS = (
    {"name": "r32-workers", "width": 2, "pending": 64, "kind": "shared"},
    {"name": "scode-opt", "width": 1, "pending": 128, "kind": "scode"},
    {"name": "scode-work", "width": 2, "pending": 512, "kind": "scode"},
    {"name": "scode-canon", "width": 1, "pending": 64, "kind": "scode"},
)


def _unit(text):
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def predict(lanes=LANES):
    """For each lane, a prediction of its load from the other lanes. No process access."""
    out = []
    for lane in lanes:
        others = [l for l in lanes if l["name"] != lane["name"]]
        pressure = sum(l["priority"] * l["width"] for l in others) / max(1, sum(l["width"] for l in others))
        own = lane["priority"] * lane["width"]
        load = max(0.0, min(1.0, (pressure - own * 0.4) / 10.0 + 0.3 * _unit(lane["name"])))
        out.append({
            "name": lane["name"],
            "pool": lane["pool"],
            "predicted_load": round(load, 3),
            "from_lanes": [l["name"] for l in others],
        })
    return out


def pool_matrix(pools=POOLS):
    """A multidimensional descriptor of the pools. Rows are pools, columns are width/pending/kind."""
    return [{
        "name": p["name"],
        "width": p["width"],
        "pending": p["pending"],
        "kind": p["kind"],
        "share": round(p["width"] / max(1, sum(x["width"] for x in pools)), 3),
    } for p in pools]


def describe():
    lines = ["Multidimensional prediction (no process access)", ""]
    for row in predict():
        lines.append("%s  load %.0f%%  from %d lanes" % (row["name"], row["predicted_load"] * 100, len(row["from_lanes"])))
    lines.append("")
    lines.append("Pool matrix")
    for row in pool_matrix():
        lines.append("%s  width %d  pending %d  share %.0f%%" % (row["name"], row["width"], row["pending"], row["share"] * 100))
    return "\n".join(lines)
