#!/usr/bin/env python3
"""self_update.py — GROOVEBOX_SELF_UPDATE_20261112

Live "update from another Groovebox on a drive", then rebuild in place.

  find_update_sources()   look on every mounted removable drive / disc (and any extra
                          folders) for another Groovebox version: an unpacked source tree,
                          a MATH_GROOVEBOX*/MATGROOVEBOX*.zip|.tar.gz archive (also inside
                          GROOVEBOX_UPDATE/), or a *.mgbclone.zip Operation Station clone.
  stage(source)           copy / unpack it into a private staging folder (path-traversal and
                          symlink safe; clone bundles are SHA-256 checked; when a trusted
                          update key is installed archives must carry a valid signature).
  verify_staged(dir)      byte-compiles every module in a separate interpreter and imports
                          the core modules there, so a broken update never touches the app.
  apply(dir)              rollback zip of every file that will change → per-file atomic
                          replace (tmp + os.replace).  Files that only exist locally, user
                          data and caches are left alone.  Newest 3 rollbacks are kept.
  rebuild()               refresh the ISO payload copy, byte-compile, rebuild native pieces
                          (optional; never fatal), so the next launch / ISO is the new code.
  rollback()              restore the newest rollback zip.
  update_from(source)     stage → verify → apply → rebuild, with one progress callback.

The whole module is deterministic and stdlib-only.  Nothing is executed from the drive:
the staged code is only byte-compiled / imported in a child interpreter.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

APP_ROOT = Path(__file__).resolve().parent
MARKERS = ("groovebox.py", "run_groovebox.py", "compat_settings.py")
CORE_IMPORTS = ("compat_settings", "thread_budget", "groovebox_paths", "operation_station_transfer", "self_update")
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".venv", "venv", "node_modules", "exports", "renders",
             "projects", "samples", "modules", "user_data"}
ARCHIVE_RE = re.compile(r"^(MATH_GROOVEBOX|MATGROOVEBOX|MathematiciansGroovebox).*\.(zip|tar\.gz|tgz)$", re.I)
KEEP_ROLLBACKS = 3
Progress = Optional[Callable[[str, int, int], None]]


def _say(progress: Progress, phase: str, done: int = 0, total: int = 0) -> None:
    if progress:
        try:
            progress(phase, int(done), int(total))
        except Exception:
            pass


def _data_dir() -> Path:
    try:
        import groovebox_paths
        return Path(groovebox_paths.base_dir())
    except Exception:
        return Path(os.path.expanduser("~")) / ".groovebox"


def updates_dir() -> Path:
    p = _data_dir() / "updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _is_tree(p: Path) -> bool:
    return all((p / m).is_file() for m in MARKERS)


def version_of_tree(root: Path) -> str:
    """Human version string: first line of CURRENT-RELEASE.txt, else the newest release note name."""
    root = Path(root)
    cur = root / "CURRENT-RELEASE.txt"
    try:
        line = cur.read_text(encoding="utf-8", errors="replace").strip().splitlines()[0].strip()
        if line:
            return line[:120]
    except Exception:
        pass
    names = sorted(n.name for n in root.glob("CURRENT-RELEASE-*.txt"))
    return names[-1][len("CURRENT-RELEASE-"):-4] if names else "unknown"


def fingerprint(root: Path) -> str:
    """Order-independent SHA-256 over every *.py path + content (identity of a code tree)."""
    root = Path(root); h = hashlib.sha256()
    for p in sorted(root.glob("*.py")):
        try:
            h.update(p.name.encode()); h.update(hashlib.sha256(p.read_bytes()).digest())
        except OSError:
            pass
    return h.hexdigest()


def removable_roots() -> List[str]:
    roots: List[str] = []
    try:
        from operation_station_transfer import detect_removable_mounts
        roots.extend(detect_removable_mounts())
    except Exception:
        pass
    user = os.environ.get("USER", "")
    for base in ([f"/media/{user}", f"/run/media/{user}"] if user else []) + ["/media", "/mnt", "/Volumes", "/run/sos-update"]:
        try:
            for p in Path(base).iterdir():
                if p.is_dir():
                    roots.append(str(p))
        except OSError:
            pass
    out, seen = [], set()
    for r in roots:            # optical discs are read-only: they count too (source discs)
        k = os.path.realpath(r)
        if k not in seen:
            seen.add(k); out.append(r)
    return out


def _walk_limited(root: Path, depth: int):
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError:
        return
    for p in entries:
        yield p
        if depth > 0 and p.is_dir() and not p.is_symlink() and p.name not in SKIP_DIRS and not p.name.startswith("."):
            yield from _walk_limited(p, depth - 1)


def find_update_sources(extra_roots=(), depth: int = 3) -> List[Dict]:
    """Every other Groovebox version reachable on drives/discs; newest first."""
    me = os.path.realpath(APP_ROOT)
    found: List[Dict] = []; seen = set()
    for r in list(extra_roots) + removable_roots():
        root = Path(r)
        if not root.is_dir():
            continue
        cands = [root] + list(_walk_limited(root, depth))
        for p in cands:
            try:
                rp = os.path.realpath(p)
                if rp in seen or rp == me or rp.startswith(me + os.sep):
                    continue
                kind = None
                if p.is_dir() and _is_tree(p):
                    kind = "tree"
                elif p.is_file() and p.name.lower().endswith(".mgbclone.zip"):
                    kind = "clone"
                elif p.is_file() and ARCHIVE_RE.match(p.name):
                    kind = "archive"
                if not kind:
                    continue
                seen.add(rp)
                st = p.stat()
                found.append({"path": str(p), "kind": kind, "mtime": st.st_mtime,
                              "size": st.st_size if p.is_file() else 0,
                              "version": version_of_tree(p) if kind == "tree" else p.name,
                              "drive": str(root)})
            except OSError:
                continue
    found.sort(key=lambda d: (-d["mtime"], d["path"]))
    return found


# --------------------------------------------------------------------------- staging
def _safe_member(name: str) -> Optional[str]:
    n = name.replace("\\", "/").lstrip("/")
    parts = [x for x in n.split("/") if x not in ("", ".")]
    if not parts or any(x == ".." for x in parts) or re.match(r"^[A-Za-z]:", parts[0]):
        return None
    return "/".join(parts)


def _extract_zip(path: Path, dest: Path, progress: Progress, prefix: str = "") -> None:
    with zipfile.ZipFile(path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        for k, info in enumerate(infos):
            name = info.filename
            if prefix:
                if not name.startswith(prefix):
                    continue
                name = name[len(prefix):]
            rel = _safe_member(name)
            if rel is None or ((info.external_attr >> 16) & 0o170000) == 0o120000:   # skip traversal / symlinks
                continue
            out = dest / rel; out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            if k % 200 == 0:
                _say(progress, "unpacking", k, len(infos))


def _extract_tar(path: Path, dest: Path, progress: Progress) -> None:
    with tarfile.open(path, "r:*") as t:
        members = [m for m in t.getmembers() if m.isfile()]
        for k, m in enumerate(members):
            rel = _safe_member(m.name)
            if rel is None:
                continue
            out = dest / rel; out.parent.mkdir(parents=True, exist_ok=True)
            src = t.extractfile(m)
            if src is None:
                continue
            with src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            if k % 200 == 0:
                _say(progress, "unpacking", k, len(members))


def _copy_tree(src: Path, dest: Path, progress: Progress) -> None:
    files = []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(filenames):
            files.append(Path(dirpath) / f)
    for k, p in enumerate(files):
        if p.is_symlink():
            continue
        out = dest / p.relative_to(src); out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        if k % 200 == 0:
            _say(progress, "copying", k, len(files))


def _find_root(d: Path) -> Optional[Path]:
    if _is_tree(d):
        return d
    for p in sorted(d.rglob("groovebox.py"), key=lambda q: len(q.parts)):
        if _is_tree(p.parent):
            return p.parent
    return None


def _check_signature(path: Path) -> None:
    """With a trusted key installed only signed archives are accepted (same rule as pre-boot)."""
    keys = [Path("/etc/groovebox/update-signing.pub"), Path("/var/lib/groovebox-system/update-signing.pub")]
    if not any(k.is_file() and k.stat().st_size for k in keys):
        return
    ver = APP_ROOT / "update_signing.py"
    r = subprocess.run([sys.executable, str(ver), "verify", str(path)], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise PermissionError("update signature refused: " + (r.stdout + r.stderr).strip()[-300:])


def stage(source, progress: Progress = None) -> Path:
    """Copy / unpack the source into updates/staging-<ts>/ and return the Groovebox root in it."""
    src = Path(source["path"] if isinstance(source, dict) else source)
    base = updates_dir() / ("staging-" + time.strftime("%Y%m%d-%H%M%S"))
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    _say(progress, "staging", 0, 1)
    name = src.name.lower()
    if src.is_dir():
        if not _is_tree(src):
            raise ValueError(f"{src} is not a Groovebox source folder")
        _copy_tree(src, base / "tree", progress)
    elif name.endswith(".mgbclone.zip"):
        from operation_station_transfer import verify_clone_bundle
        r = verify_clone_bundle(str(src))
        if not r.get("ok"):
            raise ValueError("clone bundle checksum failed: " + ", ".join(r.get("bad", [])[:3]))
        _extract_zip(src, base / "tree", progress, prefix="payload/")
    elif name.endswith(".zip"):
        _check_signature(src); _extract_zip(src, base / "tree", progress)
    elif name.endswith((".tar.gz", ".tgz")):
        _check_signature(src); _extract_tar(src, base / "tree", progress)
    else:
        raise ValueError(f"unsupported update source: {src}")
    root = _find_root(base / "tree")
    if root is None:
        shutil.rmtree(base, ignore_errors=True)
        raise ValueError("no Groovebox (groovebox.py + run_groovebox.py + compat_settings.py) inside " + str(src))
    (base / "SOURCE.json").write_text(json.dumps({"source": str(src), "root": str(root), "time": time.time()}), encoding="utf-8")
    return root


def verify_staged(root: Path, timeout: float = 600.0) -> Dict:
    """Compile + import the staged code in a child interpreter. Never imports into this process."""
    root = Path(root)
    py = sorted(str(p.name) for p in root.glob("*.py"))
    code = (
        "import sys, importlib, os\n"
        "os.environ.setdefault('QT_QPA_PLATFORM','offscreen')\n"
        "bad=[]\n"
        "for f in sys.argv[2:]:\n"
        "    try: compile(open(f,'rb').read(), f, 'exec', dont_inherit=True)\n"
        "    except Exception as e: bad.append(f+': '+str(e).splitlines()[-1][:160])\n"
        "for m in sys.argv[1].split(','):\n"
        "    if not os.path.isfile(m+'.py'): continue\n"
        "    try: importlib.import_module(m)\n"
        "    except Exception as e: bad.append('import '+m+': '+repr(e)[:160])\n"
        "print('\\n'.join(bad)); sys.exit(1 if bad else 0)\n"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", QT_QPA_PLATFORM="offscreen",
               GROOVEBOX_DATA_DIR=tempfile.mkdtemp(prefix="gb-verify-"))
    env.pop("PYTHONPATH", None)
    r = subprocess.run([sys.executable, "-c", code, ",".join(CORE_IMPORTS)] + py, cwd=str(root),
                       capture_output=True, text=True, timeout=timeout, env=env)
    problems = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    if r.returncode not in (0, 1):
        problems.append((r.stderr or "verifier crashed").strip()[-300:])
    return {"ok": r.returncode == 0 and not problems, "problems": problems[:40], "files": len(py),
            "version": version_of_tree(root), "fingerprint": fingerprint(root)}


# --------------------------------------------------------------------------- apply / rollback
def _changed_files(new_root: Path, app_root: Path) -> List[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(new_root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(filenames):
            src = Path(dirpath) / f; rel = src.relative_to(new_root); dst = app_root / rel
            try:
                if dst.is_file() and dst.stat().st_size == src.stat().st_size and \
                        hashlib.sha256(dst.read_bytes()).digest() == hashlib.sha256(src.read_bytes()).digest():
                    continue
            except OSError:
                pass
            out.append(rel)
    return out


def _writable(app_root: Path) -> bool:
    try:
        fd, p = tempfile.mkstemp(prefix=".gb-wtest-", dir=str(app_root)); os.close(fd); os.unlink(p)
        return True
    except OSError:
        return False


def apply(new_root: Path, app_root: Path = APP_ROOT, progress: Progress = None) -> Dict:
    new_root = Path(new_root); app_root = Path(app_root)
    if not _writable(app_root):
        raise PermissionError(f"{app_root} is read-only here. Put the archive in GROOVEBOX_UPDATE/ on the drive "
                              "and reboot with the 'Update code from USB' boot entry (sos.update=1).")
    changed = _changed_files(new_root, app_root)
    rb_dir = updates_dir() / "rollback"; rb_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    rb = rb_dir / f"{stamp}.zip"
    added = []
    with zipfile.ZipFile(rb, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for rel in changed:
            old = app_root / rel
            if old.is_file():
                z.write(old, str(rel))
            else:
                added.append(str(rel).replace("\\", "/"))
        z.writestr("ROLLBACK.json", json.dumps({"app_root": str(app_root), "added": added,
                                                 "version_before": version_of_tree(app_root),
                                                 "version_after": version_of_tree(new_root)}, indent=1))
    for k, rel in enumerate(changed):
        src = new_root / rel; dst = app_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(f".{dst.name}.gbupd-{os.getpid()}")
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
        if k % 100 == 0:
            _say(progress, "installing", k, len(changed))
    for old in sorted(rb_dir.glob("*.zip"))[:-KEEP_ROLLBACKS]:
        try:
            old.unlink()
        except OSError:
            pass
    with open(app_root / ".sos-updates.log", "a", encoding="utf-8") as f:
        f.write(f"{stamp} live update {len(changed)} files from {new_root} -> {version_of_tree(new_root)}\n")
    _say(progress, "installed", len(changed), len(changed))
    return {"changed": len(changed), "rollback": str(rb), "version": version_of_tree(app_root)}


def rollbacks() -> List[str]:
    return [str(p) for p in sorted((updates_dir() / "rollback").glob("*.zip"), reverse=True)]


def rollback(path: Optional[str] = None, app_root: Path = APP_ROOT) -> Dict:
    items = [path] if path else rollbacks()[:1]
    if not items or not items[0]:
        raise FileNotFoundError("no rollback saved yet")
    rb = Path(items[0]); n = 0
    with zipfile.ZipFile(rb) as z:
        meta = json.loads(z.read("ROLLBACK.json").decode("utf-8"))
        for info in z.infolist():
            rel = _safe_member(info.filename)
            if rel is None or rel == "ROLLBACK.json" or info.is_dir():
                continue
            dst = Path(app_root) / rel; dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(f".{dst.name}.gbrb-{os.getpid()}")
            with z.open(info) as s, open(tmp, "wb") as d:
                shutil.copyfileobj(s, d)
            os.replace(tmp, dst); n += 1
    for rel in meta.get("added", []):
        r = _safe_member(rel)
        if r:
            try:
                (Path(app_root) / r).unlink()
            except OSError:
                pass
    _clear_pycache(Path(app_root))
    return {"restored": n, "removed": len(meta.get("added", [])), "version": meta.get("version_before", "")}


def _clear_pycache(root: Path) -> None:
    for d in root.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def rebuild(app_root: Path = APP_ROOT, progress: Progress = None, native: bool = True) -> Dict:
    """Make the installed tree consistent after an update. Optional steps never fail the update."""
    app_root = Path(app_root); steps = []
    _clear_pycache(app_root)
    plan = [("ISO payload sync", [sys.executable, "scripts/sync_runtime_payload.py"]),
            ("byte-compile", [sys.executable, "-m", "compileall", "-q", "-x", r"(BUILD_ISO|V3_REFERENCE|release-tests)", "."])]
    if native and (app_root / "scripts" / "native_rebuild.py").is_file():
        plan.append(("native rebuild", [sys.executable, "scripts/native_rebuild.py", "--profile", "kit"]))
    for k, (label, cmd) in enumerate(plan):
        _say(progress, label, k, len(plan))
        if not (app_root / cmd[1]).exists() and cmd[1].endswith(".py"):
            steps.append({"step": label, "ok": None, "note": "not present"}); continue
        try:
            r = subprocess.run(cmd, cwd=str(app_root), capture_output=True, text=True, timeout=1800)
            steps.append({"step": label, "ok": r.returncode == 0, "note": (r.stdout + r.stderr).strip()[-240:]})
        except Exception as exc:
            steps.append({"step": label, "ok": False, "note": str(exc)[:240]})
    _say(progress, "rebuilt", len(plan), len(plan))
    return {"steps": steps}


def update_from(source, progress: Progress = None, native: bool = True, app_root: Path = APP_ROOT) -> Dict:
    root = stage(source, progress)
    try:
        _say(progress, "verifying", 0, 1)
        v = verify_staged(root)
        if not v["ok"]:
            return {"ok": False, "stage": "verify", "problems": v["problems"], "version": v["version"]}
        res = apply(root, app_root, progress)
        res["rebuild"] = rebuild(app_root, progress, native=native)
        res.update(ok=True, verified_files=v["files"], fingerprint=v["fingerprint"])
        return res
    finally:
        for p in updates_dir().glob("staging-*"):
            shutil.rmtree(p, ignore_errors=True)


def restart_command() -> List[str]:
    """argv that relaunches Groovebox the way it was started."""
    runner = APP_ROOT / "run_groovebox.py"
    return [sys.executable, str(runner)] if runner.is_file() else [sys.executable] + sys.argv


if __name__ == "__main__":   # CLI: list | apply <path> | rollback
    a = sys.argv[1:] or ["list"]
    if a[0] == "list":
        print(json.dumps(find_update_sources(a[1:]), indent=1))
    elif a[0] == "apply" and len(a) > 1:
        print(json.dumps(update_from(a[1], lambda p, d, t: print(f"[{p}] {d}/{t}", flush=True)), indent=1, default=str))
    elif a[0] == "rollback":
        print(json.dumps(rollback(a[1] if len(a) > 1 else None), indent=1))
    else:
        print(__doc__)
