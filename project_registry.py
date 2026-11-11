"""project_registry.py — GROOVEBOX_R32_PROJECT_REGISTRY_20261110

A persistent record of every project this Groovebox has opened, saved or autosaved:

    id          stable identity (uuid stored inside the project document as "project_uid")
    title, path, folder, created, last_opened, last_saved, autosaves[], size, present

The record survives moves and renames (re-found by project_uid when a document shows up at a
new path in the projects folder) and is only dropped when the project's files are really gone
(prune() — after a confirmation by the caller) or the user removes it. The startup screen's
project list and the File Studio read this.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid

_LOCK = threading.Lock()


def _path():
    import groovebox_paths
    return os.path.join(groovebox_paths.state_dir(), "project_registry.json")


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d):
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, _path())


def ensure_uid(doc):
    """Give a project document a stable identity (kept on save)."""
    if isinstance(doc, dict) and not doc.get("project_uid"):
        doc["project_uid"] = uuid.uuid4().hex
    return doc.get("project_uid") if isinstance(doc, dict) else None


def touch(path, kind="opened", doc=None):
    """Record an open / save / autosave of ``path``."""
    path = os.path.abspath(str(path))
    uid = None
    if isinstance(doc, dict):
        uid = doc.get("project_uid")
    if not uid:
        try:
            with open(path, encoding="utf-8") as f:
                uid = (json.load(f) or {}).get("project_uid")
        except Exception:
            uid = None
    with _LOCK:
        d = load()
        key = uid or ("path:" + path)
        if kind == "autosave":
            # autosaves attach to the project they belong to
            proj = os.path.dirname(os.path.dirname(path))
            for k, r in d.items():
                if r.get("folder") == proj:
                    a = r.setdefault("autosaves", [])
                    if path not in a:
                        a.append(path)
                    r["last_autosave"] = time.time()
                    _save(d)
                    return k
        r = d.get(key) or {"created": time.time()}
        r.update({"path": path, "folder": os.path.dirname(path),
                  "title": (doc or {}).get("project_title") or os.path.splitext(os.path.basename(path))[0],
                  "present": True})
        r["last_" + ("saved" if kind == "saved" else "opened")] = time.time()
        try:
            r["size"] = os.path.getsize(path)
        except OSError:
            pass
        d[key] = r
        _save(d)
        return key


def refresh():
    """Re-check presence; re-find moved projects by uid. Never deletes records."""
    import groovebox_paths
    with _LOCK:
        d = load()
        missing = {k: r for k, r in d.items() if not os.path.isfile(r.get("path", ""))}
        if missing:
            uids = {k for k in missing if not k.startswith("path:")}
            for root, _ds, fs in os.walk(groovebox_paths.projects_dir()):
                for f in fs:
                    if f.lower().endswith(".mcc") and uids:
                        p = os.path.join(root, f)
                        try:
                            with open(p, encoding="utf-8") as fh:
                                u = (json.load(fh) or {}).get("project_uid")
                        except Exception:
                            continue
                        if u in uids:
                            d[u]["path"], d[u]["folder"] = p, root
                            uids.discard(u)
        for k, r in d.items():
            r["present"] = os.path.isfile(r.get("path", ""))
        _save(d)
        return d


def listing():
    rows = list(refresh().items())
    rows.sort(key=lambda kv: -max(kv[1].get("last_opened", 0), kv[1].get("last_saved", 0), kv[1].get("last_autosave", 0)))
    return rows


def prune(keys=None):
    """Drop records whose files are gone (or the given keys)."""
    with _LOCK:
        d = load()
        for k in list(d):
            if (keys is None and not d[k].get("present", True)) or (keys is not None and k in keys):
                d.pop(k, None)
        _save(d)
