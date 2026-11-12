"""PATHWAY_HUB_20261112: one packet the tools share.

Notes, bookmarks, the meter, the theme, the backup, and the export dashboard
all read and write through this. The packet carries the seed fingerprint so a
note, a mark, and an export from the same session share one id.
"""
from __future__ import annotations
import hashlib, json, os, time

def fingerprint(app):
    seed = getattr(app, "project_seed", None) or getattr(app, "seed", None) or 1
    script = str(getattr(app, "seed_script_text", "") or getattr(app, "seed_program", "") or "")
    raw = "%s|%s" % (seed, script)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def packet(app):
    return {
        "fingerprint": fingerprint(app),
        "seed": getattr(app, "project_seed", None) or getattr(app, "seed", None) or 1,
        "time": time.time(),
        "theme": _setting(app, "color_scheme", "normal"),
        "quality": _setting(app, "thread_quality", "balanced"),
        "profile": _setting(app, "compat_profile", "auto"),
    }

def _setting(app, key, default):
    try:
        import compat_settings as cs
        return cs.load().get(key, default)
    except Exception:
        return default

def stamp(app, kind, data):
    """Attach the packet to a tool's record and keep a session log."""
    p = packet(app)
    record = {"kind": kind, "packet": p, "data": data, "time": p["time"]}
    base = getattr(app, "project_dir", None) or os.path.expanduser("~/.groovebox")
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "pathway-log.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record

def recent(app, limit=20):
    base = getattr(app, "project_dir", None) or os.path.expanduser("~/.groovebox")
    path = os.path.join(base, "pathway-log.jsonl")
    if not os.path.isfile(path):
        return []
    lines = open(path).read().splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out
