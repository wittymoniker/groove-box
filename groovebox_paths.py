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
