"""Central filesystem/workspace locations for Mathematician's Groovebox.

Every project owns one self-contained folder.  Project documents, imported samples,
recordings, layered Draw/Record material, renders, frames and game exports live under
that folder so Performance and the main window index the same data without scanning
unrelated global buckets.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, time
from pathlib import Path
from typing import Optional

APP_DIRNAME = "MathematiciansGroovebox"
PROJECT_LAYOUT = (
    "samples/imports", "samples/global", "samples/operators",
    "recordings", "layers", "exports/audio", "exports/video", "exports/frames",
    "games", "metadata", "cache",
)

def _data_root() -> Path:
    override = os.environ.get("GROOVEBOX_DATA_DIR", "").strip()
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home())) / APP_DIRNAME
    elif __import__('sys').platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / APP_DIRNAME
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root

def base_dir() -> str:
    return str(_data_root())

def projects_dir() -> str:
    p = _data_root() / "projects"; p.mkdir(parents=True, exist_ok=True); return str(p)

def _safe_project_name(value: object) -> str:
    s = str(value or "Untitled").strip()
    s = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s or "Untitled")[:120]

def project_name(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    if project_name:
        return _safe_project_name(project_name)
    if project_path:
        p = Path(os.path.abspath(os.path.expanduser(str(project_path))))
        stem = p.stem
        if stem.lower().endswith('.mgpr'):
            stem = Path(stem).stem
        return _safe_project_name(stem)
    return "Untitled"

def project_root(project_path: Optional[str]=None, project_name: Optional[str]=None) -> Path:
    name = globals()['project_name'](project_path, project_name)
    if project_path:
        p = Path(os.path.abspath(os.path.expanduser(str(project_path))))
        # New layout: .../<Project>/<Project>.MCC.  Legacy/external documents keep
        # their document in place but receive a sibling project workspace.
        root = p.parent if p.parent.name == name else p.parent / name
    else:
        root = Path(projects_dir()) / name
    root.mkdir(parents=True, exist_ok=True)
    for rel in PROJECT_LAYOUT:
        (root / rel).mkdir(parents=True, exist_ok=True)
    return root

def canonical_project_path(path: str) -> str:
    p = Path(os.path.abspath(os.path.expanduser(str(path))))
    suffix = p.suffix or '.MCC'
    name = _safe_project_name(p.stem)
    root = p.parent if p.parent.name == name else p.parent / name
    root.mkdir(parents=True, exist_ok=True)
    for rel in PROJECT_LAYOUT: (root/rel).mkdir(parents=True, exist_ok=True)
    return str(root / f"{name}{suffix}")

def default_project_path(name: str='Untitled') -> str:
    name = _safe_project_name(name)
    root = project_root(project_name=name)
    return str(root / f"{name}.MCC")

def samples_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'samples')

def recordings_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'recordings')

def layers_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'layers')

def renders_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'exports')

def audio_exports_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'exports' / 'audio')

def video_exports_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'exports' / 'video')

def frame_exports_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'exports' / 'frames')

def games_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'games')

def metadata_dir(project_path: Optional[str]=None, project_name: Optional[str]=None) -> str:
    return str(project_root(project_path, project_name) / 'metadata')

def index_path(project_path: Optional[str]=None, project_name: Optional[str]=None) -> Path:
    return project_root(project_path, project_name) / 'metadata' / 'project_index.json'

def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def index_file(path: str, role: str, project_path: Optional[str]=None, project_name: Optional[str]=None) -> None:
    try:
        root=project_root(project_path, project_name); p=Path(path).resolve()
        try: rel=str(p.relative_to(root.resolve()))
        except Exception: rel=str(p)
        ip=index_path(project_path, project_name)
        try: doc=json.loads(ip.read_text(encoding='utf-8'))
        except Exception: doc={"version":2,"project":globals()['project_name'](project_path,project_name),"files":{}}
        if not isinstance(doc,dict): doc={"version":2,"files":{}}
        files=doc.setdefault('files',{})
        st=p.stat() if p.is_file() else None
        files[rel]={"role":str(role),"size":int(st.st_size) if st else 0,"sha256":_sha256(p) if st else ""}
        tmp=ip.with_suffix('.json.tmp'); tmp.write_text(json.dumps(doc,indent=2,sort_keys=True),encoding='utf-8'); os.replace(tmp,ip)
    except Exception:
        pass

def unindex_file(path: str, project_path: Optional[str]=None, project_name: Optional[str]=None) -> bool:
    """Remove a file reference from the project index without deleting the file."""
    try:
        root=project_root(project_path, project_name); p=Path(path).resolve()
        try: rel=str(p.relative_to(root.resolve()))
        except Exception: rel=str(p)
        ip=index_path(project_path, project_name)
        if not ip.is_file(): return False
        try: doc=json.loads(ip.read_text(encoding='utf-8'))
        except Exception: return False
        files=doc.get('files',{}) if isinstance(doc,dict) else {}
        changed=False
        if isinstance(files,dict):
            for key in list(files):
                try:
                    kabs=(root/key).resolve() if not os.path.isabs(str(key)) else Path(key).resolve()
                    if str(key)==rel or kabs==p:
                        files.pop(key,None); changed=True
                except Exception:
                    if str(key)==rel:
                        files.pop(key,None); changed=True
        if changed:
            tmp=ip.with_suffix('.json.tmp'); tmp.write_text(json.dumps(doc,indent=2,sort_keys=True),encoding='utf-8'); os.replace(tmp,ip)
        return changed
    except Exception:
        return False

def ingest_file(source: str, role: str='sample', project_path: Optional[str]=None, project_name: Optional[str]=None, instrument: str='') -> str:
    src=Path(os.path.abspath(os.path.expanduser(str(source))))
    if not src.is_file(): raise FileNotFoundError(str(src))
    root=project_root(project_path, project_name)
    if role == 'recording': dest_dir=root/'recordings'
    elif role == 'layer': dest_dir=root/'layers'
    elif role == 'global_sample': dest_dir=root/'samples'/'global'
    elif role == 'operator_sample': dest_dir=root/'samples'/'operators'
    else: dest_dir=root/'samples'/'imports'
    dest_dir.mkdir(parents=True,exist_ok=True)
    stem=_safe_project_name(src.stem); suffix=src.suffix
    dst=dest_dir/(stem+suffix); n=2
    while dst.exists() and src.resolve()!=dst.resolve():
        try:
            if src.stat().st_size==dst.stat().st_size and _sha256(src)==_sha256(dst):
                index_file(str(dst),role,project_path,project_name); return str(dst)
        except Exception: pass
        dst=dest_dir/f"{stem}_{n}{suffix}"; n+=1
    if src.resolve()!=dst.resolve(): shutil.copy2(src,dst)
    index_file(str(dst),role,project_path,project_name)
    return str(dst)

# ---------------------------------------------------------------------------
# GROOVEBOX_STORAGE_MAINTENANCE_20260909
# Central, auto-created writable application layout used by desktop and sOS
# appliance builds.  Project folders remain self-contained; these are only the
# global/support directories that must exist before file/network/media workers
# start touching disk.
APP_LAYOUT = (
    "projects", "samples", "games", "modules",
    "exports", "exports/audio", "exports/video", "exports/games", "exports/clones",
    "cache", "temp", "logs", "state",
    "Nearby Grooveboxes", "Nearby Grooveboxes/Inbox",
)

def ensure_app_layout() -> dict:
    root = _data_root()
    out = {"base": str(root)}
    for rel in APP_LAYOUT:
        p = root / rel
        p.mkdir(parents=True, exist_ok=True)
        out[rel] = str(p)
    # A tiny write/delete probe catches read-only appliance/media errors early
    # while leaving no persistent scratch file behind.
    probe = root / "temp" / ".write_probe"
    try:
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        raise OSError(f"Groovebox data directory is not writable: {root}: {exc}") from exc
    return out

def _global_dir(rel: str) -> str:
    root = _data_root() / rel
    root.mkdir(parents=True, exist_ok=True)
    return str(root)

def cache_dir() -> str: return _global_dir("cache")
def temp_dir() -> str: return _global_dir("temp")
def logs_dir() -> str: return _global_dir("logs")
def state_dir() -> str: return _global_dir("state")
def nearby_dir() -> str: return _global_dir("Nearby Grooveboxes")
def nearby_inbox_dir() -> str: return _global_dir("Nearby Grooveboxes/Inbox")
def global_samples_dir() -> str: return _global_dir("samples")
def global_games_dir() -> str: return _global_dir("games")
def global_modules_dir() -> str: return _global_dir("modules")
def global_exports_dir() -> str: return _global_dir("exports")
def clones_dir() -> str: return _global_dir("exports/clones")
def known_grooveboxes_path() -> Path: return Path(state_dir()) / "known_grooveboxes.json"

def _tree_stats(path: Path) -> tuple[int, int]:
    total = 0; count = 0
    if not path.exists(): return 0, 0
    if path.is_file():
        try: return int(path.stat().st_size), 1
        except OSError: return 0, 0
    for base, dirs, files in os.walk(path, followlinks=False):
        # Never traverse symlinked directories outside Groovebox's data root.
        dirs[:] = [d for d in dirs if not Path(base, d).is_symlink()]
        for name in files:
            p = Path(base, name)
            try:
                if p.is_symlink(): continue
                total += int(p.stat().st_size); count += 1
            except OSError: pass
    return total, count

def autosave_candidates() -> list[dict]:
    """Return recoverable Groovebox autosaves/interrupted project saves.

    This function is metadata-only and does not open or mutate project files.
    """
    ensure_app_layout()
    root = Path(projects_dir())
    paths = set(root.glob("**/metadata/autosave.MCC"))
    paths.update(root.glob("**/*.MCC.part"))
    paths.update(root.glob("**/*.mcc.part"))
    paths.update(root.glob("**/*.mgpr.part"))
    rows = []
    for p in paths:
        if not p.is_file(): continue
        title = p.parent.parent.name if p.name == "autosave.MCC" and p.parent.name == "metadata" else p.stem.replace(".MCC", "").replace(".mgpr", "")
        notes = ""; source_project = ""
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                title = str(data.get("project_title") or title or "Untitled Project")
                notes = str(data.get("project_notes") or "")
                source_project = str(data.get("project_path") or "")
        except Exception:
            pass
        try:
            st = p.stat(); mtime = float(st.st_mtime); size = int(st.st_size)
        except OSError:
            mtime = 0.0; size = 0
        rows.append({"path": str(p), "title": title or "Untitled Project", "notes": notes,
                     "project_path": source_project, "mtime": mtime, "size": size,
                     "kind": "autosave" if p.name == "autosave.MCC" else "interrupted"})
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows

def storage_report() -> dict:
    """Storage totals used by the File Manager maintenance panel."""
    ensure_app_layout(); root = _data_root()
    category_paths = {
        "projects": root / "projects",
        "samples": root / "samples",
        "games": root / "games",
        "exports": root / "exports",
        "nearby_inbox": root / "Nearby Grooveboxes" / "Inbox",
        "cache": root / "cache",
        "temp": root / "temp",
        "logs": root / "logs",
        "network_state": root / "state" / "known_grooveboxes.json",
    }
    cats = {}
    for key, p in category_paths.items():
        b, n = _tree_stats(p); cats[key] = {"bytes": b, "files": n, "path": str(p)}
    auto = autosave_candidates()
    try:
        du = shutil.disk_usage(root)
        disk = {"total": int(du.total), "used": int(du.used), "free": int(du.free)}
    except OSError:
        disk = {"total": 0, "used": 0, "free": 0}
    own_b, own_n = _tree_stats(root)
    return {"base": str(root), "groovebox_bytes": own_b, "groovebox_files": own_n,
            "disk": disk, "categories": cats,
            "autosaves": {"bytes": sum(int(r.get("size",0)) for r in auto), "files": len(auto), "items": auto}}

def _empty_dir(path: Path) -> tuple[int, int]:
    deleted_b = 0; deleted_n = 0
    if not path.exists(): return 0, 0
    for child in list(path.iterdir()):
        try:
            if child.is_symlink() or child.is_file():
                try: deleted_b += int(child.stat().st_size)
                except OSError: pass
                child.unlink(missing_ok=True); deleted_n += 1
            elif child.is_dir():
                b, n = _tree_stats(child); shutil.rmtree(child); deleted_b += b; deleted_n += n
        except OSError: pass
    path.mkdir(parents=True, exist_ok=True)
    return deleted_b, deleted_n

def cleanup_disposable(kinds=("cache", "temp", "logs", "recording_scratch")) -> dict:
    """Delete only regenerable/scratch data. Never removes projects/imports/exports."""
    ensure_app_layout(); root = _data_root(); allowed = set(kinds or ())
    removed_b = 0; removed_n = 0; details = {}
    for key, p in (("cache", root/"cache"), ("temp", root/"temp"), ("logs", root/"logs")):
        if key in allowed:
            b,n = _empty_dir(p); removed_b += b; removed_n += n; details[key] = {"bytes":b,"files":n}
    if "cache" in allowed:
        pb=pn=0
        for p in (root/"projects").glob("*/cache"):
            b,n=_empty_dir(p); pb+=b; pn+=n
        removed_b+=pb; removed_n+=pn; details["project_cache"]={"bytes":pb,"files":pn}
    if "recording_scratch" in allowed:
        rb=rn=0
        patterns=("*.part","*.tmp","*.partial","*.incomplete")
        for rec in (root/"projects").glob("*/recordings"):
            for pat in patterns:
                for p in rec.rglob(pat):
                    try:
                        if p.is_file() and not p.is_symlink():
                            rb += int(p.stat().st_size); p.unlink(); rn += 1
                    except OSError: pass
        removed_b+=rb; removed_n+=rn; details["recording_scratch"]={"bytes":rb,"files":rn}
    return {"bytes":removed_b,"files":removed_n,"details":details}

def delete_autosave(path: str) -> bool:
    p = Path(path).expanduser().resolve(); root = Path(projects_dir()).resolve()
    try: p.relative_to(root)
    except ValueError: raise ValueError("Refusing to delete autosave outside Groovebox projects")
    if not (p.name == "autosave.MCC" or p.name.lower().endswith((".mcc.part", ".mgpr.part"))):
        raise ValueError("Not a recognized Groovebox autosave/recovery file")
    if p.is_file(): p.unlink(); return True
    return False

def delete_project_exports(project_path: Optional[str]=None, project_name: Optional[str]=None) -> dict:
    root = project_root(project_path, project_name) / "exports"
    b,n = _tree_stats(root); _empty_dir(root)
    for rel in ("audio","video","frames"): (root/rel).mkdir(parents=True, exist_ok=True)
    return {"bytes":b,"files":n}

def delete_all_global_exports() -> dict:
    p = Path(global_exports_dir()); b,n=_tree_stats(p); _empty_dir(p)
    for rel in ("audio","video","games","clones"): (p/rel).mkdir(parents=True, exist_ok=True)
    return {"bytes":b,"files":n}

def _collect_string_values(obj, out: set[str]):
    if isinstance(obj, str): out.add(obj)
    elif isinstance(obj, dict):
        for v in obj.values(): _collect_string_values(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj: _collect_string_values(v, out)

def find_unreferenced_project_media(project_path: Optional[str]=None, project_name: Optional[str]=None) -> list[dict]:
    """Conservative candidate finder; never deletes anything by itself."""
    root = project_root(project_path, project_name).resolve()
    doc = Path(project_path).resolve() if project_path else None
    strings:set[str] = set()
    if doc is not None and doc.is_file():
        try: _collect_string_values(json.loads(doc.read_text(encoding="utf-8")), strings)
        except Exception: return []  # safest answer when document cannot be inspected
    else:
        return []
    normalized = {os.path.normcase(os.path.abspath(os.path.expanduser(s))) for s in strings if s}
    raw = set(strings)
    rows=[]
    for relroot in ("samples", "recordings", "layers"):
        d=root/relroot
        if not d.exists(): continue
        for p in d.rglob("*"):
            if not p.is_file() or p.is_symlink(): continue
            ap=os.path.normcase(str(p.resolve())); rel=p.relative_to(root).as_posix()
            # Match absolute paths, project-relative paths, or exact basename values.
            used = ap in normalized or rel in raw or str(p) in raw
            if not used:
                try: size=int(p.stat().st_size)
                except OSError: size=0
                rows.append({"path":str(p),"relative":rel,"size":size})
    rows.sort(key=lambda r:(r["relative"].lower(),r["path"]))
    return rows

def delete_unreferenced_project_media(candidates: list[dict], project_path: Optional[str]=None, project_name: Optional[str]=None) -> dict:
    root=project_root(project_path,project_name).resolve(); b=n=0
    for row in candidates or []:
        p=Path(str(row.get("path",""))).expanduser().resolve()
        try: p.relative_to(root)
        except ValueError: continue
        if not any(part in ("samples","recordings","layers") for part in p.relative_to(root).parts[:1]): continue
        try:
            if p.is_file() and not p.is_symlink():
                b+=int(p.stat().st_size); p.unlink(); n+=1
        except OSError: pass
    return {"bytes":b,"files":n}
