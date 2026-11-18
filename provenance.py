"""provenance.py: every finished export remembers exactly what made it, and can rebuild that project.

When an export finishes, the export scheduler hands over the frozen project document the worker rendered
from.  It is stored (compressed) with the seed, the release stamp and the export options:

* beside the file, as a hidden ``.<name>.mgprov`` (travels with the file on the same drive), and
* in the Groovebox data folder under ``provenance/<fingerprint>.mgprov``, keyed by a content fingerprint,
  so a copy of the export that was moved, renamed or sent to another machine is still recognised.

``rebuild(app, path)`` opens the project that produced an export.  Nothing here changes the export itself.
"""
import base64
import gzip
import hashlib
import json
import os
import time

FORMAT = "MATGROOVEBOX-PROVENANCE"
VERSION = 1
_EDGE = 4 << 20


def fingerprint(path):
    """Cheap content fingerprint: size + first and last 4 MiB (stable across renames and copies)."""
    st = os.stat(path)
    h = hashlib.sha256(str(st.st_size).encode())
    with open(path, "rb") as f:
        h.update(f.read(_EDGE))
        if st.st_size > 2 * _EDGE:
            f.seek(-_EDGE, os.SEEK_END)
            h.update(f.read(_EDGE))
    return h.hexdigest()


def sidecar_path(path):
    return os.path.join(os.path.dirname(os.path.abspath(path)), "." + os.path.basename(path) + ".mgprov")


def _index_dir():
    try:
        import groovebox_paths
        base = groovebox_paths.base_dir()
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".groovebox")
    d = os.path.join(base, "provenance")
    os.makedirs(d, exist_ok=True)
    return d


def _seed_of(app, doc_bytes):
    for attr in ("seed_input", "seed_edit", "line_seed"):
        w = getattr(app, attr, None)
        try:
            t = w.text() if hasattr(w, "text") else (w.toPlainText() if hasattr(w, "toPlainText") else None)
            if t:
                return str(t)[:4000]
        except Exception:
            pass
    try:
        d = json.loads(doc_bytes.decode("utf-8"))
        for k in ("seed", "seed_text", "seed_expression"):
            if isinstance(d, dict) and d.get(k):
                return str(d[k])[:4000]
    except Exception:
        pass
    return ""


def record(app, export_path, project_file=None, kind="", options=None, project_bytes=None):
    """Store provenance for a finished export. Never raises; returns the sidecar path or ''."""
    try:
        if not (export_path and os.path.isfile(export_path)):
            return ""
        raw = project_bytes
        if raw is None:
            if not (project_file and os.path.isfile(project_file)):
                return ""
            with open(project_file, "rb") as f:
                raw = f.read()
        try:
            import release_info
            release = release_info.describe(short=True)
        except Exception:
            release = ""
        doc = {"format": FORMAT, "version": VERSION, "time": time.time(), "kind": str(kind),
               "file": os.path.basename(export_path), "fingerprint": fingerprint(export_path),
               "release": release, "seed": _seed_of(app, raw),
               "options": {k: v for k, v in (options or {}).items() if isinstance(v, (str, int, float, bool))},
               "project_sha256": hashlib.sha256(raw).hexdigest(),
               "project_gz_b64": base64.b64encode(gzip.compress(raw, 6)).decode("ascii")}
        import safe_io
        side = sidecar_path(export_path)
        try:
            safe_io.atomic_write_json(side, doc, backup=False)
        except Exception:
            side = ""
        try:
            safe_io.atomic_write_json(os.path.join(_index_dir(), doc["fingerprint"] + ".mgprov"), doc, backup=False)
        except Exception:
            pass
        return side or os.path.join(_index_dir(), doc["fingerprint"] + ".mgprov")
    except Exception:
        return ""


def lookup(path):
    """Return the provenance document for an export (beside it, or by fingerprint), or None."""
    import safe_io
    side = sidecar_path(path)
    d = safe_io.read_json(side)
    if isinstance(d, dict) and d.get("format") == FORMAT:
        return d
    try:
        fp = fingerprint(path)
    except Exception:
        return None
    d = safe_io.read_json(os.path.join(_index_dir(), fp + ".mgprov"))
    return d if isinstance(d, dict) and d.get("format") == FORMAT else None


def summary(doc):
    if not doc:
        return "No Groovebox provenance for this file."
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(doc.get("time") or 0)))
    seed = (doc.get("seed") or "").strip().splitlines()
    return "Made by Groovebox %s on %s · %s%s" % (doc.get("release") or "", when, doc.get("kind") or "export",
                                                  (" · seed: " + seed[0][:80]) if seed else "")


def rebuild(app, path):
    """Write the producing project to the projects folder and open it. Returns (ok, message)."""
    doc = lookup(path)
    if not doc:
        return False, "No Groovebox provenance for %s (it was not exported by Groovebox, or before R101)." % os.path.basename(path)
    raw = gzip.decompress(base64.b64decode(doc["project_gz_b64"]))
    if hashlib.sha256(raw).hexdigest() != doc.get("project_sha256"):
        return False, "The stored project is damaged (checksum mismatch)."
    try:
        import groovebox_paths
        base = groovebox_paths.projects_dir()
    except Exception:
        base = os.path.join(os.path.expanduser("~"), "Groovebox Projects")
    stem = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(base, "Rebuilt - %s - %s.MCC" % (stem, time.strftime("%Y%m%d-%H%M%S")))
    import safe_io
    safe_io.atomic_write_bytes(out, raw, backup=False)
    if app is not None and hasattr(app, "open_project_path"):
        try:
            app.open_project_path(out)
        except TypeError:
            app.open_project_path(out, show_message=True)
    return True, "Rebuilt the project that made %s → %s" % (os.path.basename(path), out)
