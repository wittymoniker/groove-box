"""File-manager tools: fast duplicate indexing and Groovebox source archives.

GROOVEBOX_R23R_FILE_TOOLS_20261101

find_duplicates(): size buckets -> 64 KiB head+tail fingerprint -> full
SHA-256, so only files that can still be identical are ever read in full.
export_source_archive(): the Mathematician's Groovebox source tree as .tar.gz,
.zip or .MCC, without caches, virtual environments, build outputs or ISOs.
No Qt here: both run on worker threads and report progress via callbacks.
"""
from __future__ import annotations

import hashlib
import os
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

PARTIAL = 64 * 1024
CHUNK = 1024 * 1024


def _iter_files(root: str, skip_dirs=(), include_hidden=False, cancel=None, errors=None):
    """Walk a selected tree without following symlinks or entering protected OS/Groovebox stores.

    The hidden-files checkbox applies only to user data. It must never turn a duplicate
    scan into a walk through Groovebox's protected state/cache/temp store or OS internals.
    """
    def _real(path):
        try:
            return os.path.normcase(os.path.realpath(os.path.abspath(path)))
        except Exception:
            return os.path.normcase(os.path.abspath(path))

    skip = {_real(d) for d in skip_dirs if d}
    protected = []
    # Groovebox's protected store may be on its own partition or in a hidden fallback.
    try:
        import groovebox_paths as _gp
        _store = _gp.system_root()
        if _store:
            protected.append(_real(str(_store)))
    except Exception:
        pass
    # Avoid recursively indexing OS-managed locations when the selected root is broad
    # (e.g. / or a mounted system drive). User libraries outside these locations remain
    # eligible, including ordinary hidden user files when include_hidden is enabled.
    if os.name == "nt":
        _base = os.environ.get("SystemDrive", "C:") + os.sep
        protected.extend(_real(os.path.join(_base, x)) for x in
                         ("Windows", "Program Files", "Program Files (x86)", "ProgramData"))
    else:
        protected.extend(_real(x) for x in
                         ("/boot", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/var/lib", "/System"))

    def _inside(path, roots):
        rp = _real(path)
        for r in roots:
            try:
                if os.path.commonpath((rp, r)) == r:
                    return True
            except (ValueError, OSError):
                continue
        return False

    def _onerror(exc):
        if errors is not None:
            errors.append({"path": getattr(exc, "filename", None) or str(root), "error": str(exc)})

    # If a user deliberately chooses a protected root, do not scan it at all.
    if _inside(root, protected) or _inside(root, skip):
        if errors is not None:
            errors.append({"path": str(root), "error": "protected system location skipped"})
        return

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=_onerror):
        if cancel is not None and cancel.is_set():
            return
        if _inside(dirpath, protected) or _inside(dirpath, skip):
            dirnames[:] = []
            continue
        keep = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            if (_inside(full, protected) or _inside(full, skip)
                    or (not include_hidden and d.startswith(".")) or os.path.islink(full)):
                continue
            keep.append(d)
        dirnames[:] = keep
        for f in filenames:
            if not include_hidden and f.startswith("."):
                continue
            p = os.path.join(dirpath, f)
            if os.path.islink(p) or _inside(p, protected):
                continue
            yield p


def _partial_hash(path: str, size: int) -> str:
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        h.update(f.read(PARTIAL))
        if size > 2 * PARTIAL:
            f.seek(size - PARTIAL)
            h.update(f.read(PARTIAL))
    return h.hexdigest()


def _full_hash(path: str, cancel=None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            if cancel is not None and cancel.is_set():
                raise InterruptedError
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def find_duplicates(root: str, min_size: int = 1, skip_dirs=(), include_hidden=False,
                    progress: Optional[Callable[[str, int, int], None]] = None, cancel=None,
                    errors=None) -> List[Dict]:
    """Groups of byte-identical files under root, biggest wasted space first.

    Each group: {"size", "sha256", "files": [{"path","mtime"}], "wasted"}.
    progress(phase, done, total) with phase in index / fingerprint / verify.
    """
    by_size: Dict[int, List[str]] = {}
    n = 0
    for p in _iter_files(root, skip_dirs, include_hidden, cancel, errors=errors):
        try:
            sz = os.path.getsize(p)
        except OSError as exc:
            if errors is not None:
                errors.append({"path": p, "error": str(exc)})
            continue
        if sz >= min_size:
            by_size.setdefault(sz, []).append(p)
        n += 1
        if progress and n % 500 == 0:
            progress("index", n, 0)
    cands = [(sz, ps) for sz, ps in by_size.items() if len(ps) > 1]
    total = sum(len(ps) for _, ps in cands)
    done = 0
    by_partial: Dict[tuple, List[str]] = {}
    for sz, ps in cands:
        for p in ps:
            if cancel is not None and cancel.is_set():
                return []
            try:
                by_partial.setdefault((sz, _partial_hash(p, sz)), []).append(p)
            except OSError as exc:
                if errors is not None:
                    errors.append({"path": p, "error": str(exc)})
            done += 1
            if progress and done % 50 == 0:
                progress("fingerprint", done, total)
    cands2 = [(k, ps) for k, ps in by_partial.items() if len(ps) > 1]
    total2 = sum(len(ps) for _, ps in cands2)
    done = 0
    groups: List[Dict] = []
    for (sz, _ph), ps in cands2:
        by_full: Dict[str, List[str]] = {}
        for p in ps:
            if cancel is not None and cancel.is_set():
                return []
            try:
                # Files up to PARTIAL bytes were read completely by the fingerprint.
                key = _full_hash(p, cancel) if sz > PARTIAL else _ph
                by_full.setdefault(key, []).append(p)
            except (OSError, InterruptedError) as exc:
                if errors is not None and not isinstance(exc, InterruptedError):
                    errors.append({"path": p, "error": str(exc)})
            done += 1
            if progress and done % 20 == 0:
                progress("verify", done, total2)
        for digest, same in by_full.items():
            if len(same) > 1:
                files = []
                for p in same:
                    try:
                        files.append({"path": p, "mtime": os.path.getmtime(p)})
                    except OSError:
                        pass
                if len(files) > 1:
                    groups.append({"size": sz, "sha256": digest, "files": files, "wasted": sz * (len(files) - 1)})
    groups.sort(key=lambda g: -g["wasted"])
    if progress:
        progress("done", len(groups), len(groups))
    return groups


def pick_keep(files: List[Dict], rule: str = "oldest") -> int:
    """Index of the copy to keep: oldest | newest | shortest (path)."""
    if rule == "newest":
        return max(range(len(files)), key=lambda i: files[i]["mtime"])
    if rule == "shortest":
        return min(range(len(files)), key=lambda i: (len(files[i]["path"]), files[i]["path"]))
    return min(range(len(files)), key=lambda i: files[i]["mtime"])


# ------------------------------------------------------------- source archive
SOURCE_EXCLUDE_DIRS = {"__pycache__", ".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache", ".ruff_cache",
                       ".groovebox-build-venv", "venv", ".venv", "env", "node_modules", "dist", "build",
                       "work", "target", ".idea", ".vscode"}
SOURCE_EXCLUDE_EXT = {".pyc", ".pyo", ".iso", ".img", ".qcow2", ".part", ".tmp"}


def source_files(app_root: str) -> List[Path]:
    root = Path(app_root)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SOURCE_EXCLUDE_DIRS and not d.endswith(".egg-info")]
        for f in filenames:
            p = Path(dirpath) / f
            if p.suffix.lower() in SOURCE_EXCLUDE_EXT or p.is_symlink():
                continue
            out.append(p)
    return sorted(out)


def export_source_archive(app_root: str, out_path: str, fmt: str = "tar.gz",
                          progress: Optional[Callable[[int, int], None]] = None) -> str:
    """Write the Groovebox source as .tar.gz / .zip / .MCC. Returns the final path."""
    root = Path(app_root).resolve()
    files = source_files(str(root))
    top = "MathematiciansGroovebox_Source_" + time.strftime("%Y%m%d")
    fmt = fmt.lower().lstrip(".")
    suffix = {"tar.gz": ".tar.gz", "tgz": ".tar.gz", "zip": ".zip", "mcc": ".MCC"}[fmt]
    if not str(out_path).lower().endswith(suffix.lower()):
        out_path = str(out_path) + suffix
    tmp = str(out_path) + ".part"
    total = len(files)
    if fmt in ("tar.gz", "tgz"):
        with tarfile.open(tmp, "w:gz", compresslevel=6) as t:
            for i, p in enumerate(files):
                t.add(str(p), arcname=f"{top}/{p.relative_to(root).as_posix()}", recursive=False)
                if progress:
                    progress(i + 1, total)
    elif fmt == "zip":
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for i, p in enumerate(files):
                z.write(str(p), f"{top}/{p.relative_to(root).as_posix()}")
                if progress:
                    progress(i + 1, total)
    else:
        import mcc_media
        mcc_media.pack_tree(str(root), tmp, level=6, files=files, progress=progress,
                            manifest={"name": "Mathematician's Groovebox source", "top": top,
                                      "created": time.strftime("%Y-%m-%d %H:%M:%S")})
    os.replace(tmp, out_path)
    return str(out_path)
