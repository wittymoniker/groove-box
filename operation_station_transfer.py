#!/usr/bin/env python3
"""Operation Station transfer/clone helpers.

Provides versioned, checksum-manifested bundles that can be copied to USB/mounted
storage or served over Wi-Fi/Ethernet. The receiver still chooses whether to run
or install the cloned code; this module never executes received content.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib, json, os, platform, shutil, socket, tempfile, threading, time, zipfile
from typing import Callable, Dict, List, Optional

FORMAT = "MathematiciansGrooveboxOperationStationClone"
VERSION = 3
DEFAULT_EXCLUDES = {"__pycache__", ".git", ".pytest_cache", "build", "dist", ".venv", "venv"}

@dataclass
class CloneManifest:
    format: str
    version: int
    created_utc: str
    machine: str
    python: str
    payload_kind: str
    app_version: str
    files: List[Dict]


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _wanted(rel: Path, include_source=True, include_executables=True, include_dependencies=True):
    parts=set(rel.parts)
    if parts & DEFAULT_EXCLUDES: return False
    s=str(rel).replace('\\','/')
    if s.startswith('exports/') or s.startswith('renders/'): return False
    if not include_source and rel.suffix.lower() in {'.py','.pyi','.cpp','.hpp','.h','.jl'}: return False
    if not include_executables and ('BUILD_KIT' in parts or 'dist' in parts): return False
    if not include_dependencies and ('wheelhouse' in parts or rel.name.lower().startswith(('ffmpeg','ffprobe'))): return False
    return True


def create_clone_bundle(root: str, out_path: str, *, include_source=True, include_executables=True,
                        include_dependencies=True, include_user_content=False, user_data_root: Optional[str]=None,
                        app_version='V3 Operation Station') -> str:
    rootp=Path(root).resolve(); out=Path(out_path).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
    files=[]
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(rootp.rglob('*')):
            if not p.is_file(): continue
            rel=p.relative_to(rootp)
            if not _wanted(rel,include_source,include_executables,include_dependencies): continue
            if not include_user_content and rel.parts and rel.parts[0] in {'projects','samples','modules'}:
                # preserve folder contracts through README/keep files only; don't clone private creative content by default
                continue
            if p.resolve()==out: continue
            z.write(p, arcname=str(Path('payload')/rel))
            files.append({'path':str(rel).replace('\\','/'),'size':p.stat().st_size,'sha256':sha256_file(p)})
        if include_user_content and user_data_root:
            udp=Path(user_data_root).expanduser().resolve()
            # User content is stored separately from executable source so an
            # appliance clone never confuses mutable projects with /opt code.
            for top in ('projects','samples','modules','games'):
                base=udp/top
                if not base.exists(): continue
                for p in sorted(base.rglob('*')):
                    if not p.is_file() or p.is_symlink(): continue
                    rel=Path('user_data')/p.relative_to(udp)
                    arc=Path('payload')/rel
                    z.write(p,arcname=str(arc))
                    files.append({'path':str(rel).replace('\\','/'),'size':p.stat().st_size,'sha256':sha256_file(p)})
        manifest=CloneManifest(FORMAT,VERSION,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            platform.platform(),platform.python_version(),'operation-station-clone',app_version,files)
        z.writestr('manifest.json',json.dumps(asdict(manifest),indent=2))
    return str(out)


def verify_clone_bundle(path: str) -> Dict:
    p=Path(path)
    with zipfile.ZipFile(p,'r') as z:
        m=json.loads(z.read('manifest.json').decode('utf-8'))
        if m.get('format')!=FORMAT: raise ValueError('Not an Operation Station clone bundle')
        bad=[]
        for f in m.get('files',[]):
            arc='payload/'+f['path']
            try: data=z.read(arc)
            except KeyError: bad.append(f['path']+': missing'); continue
            if hashlib.sha256(data).hexdigest()!=f['sha256']: bad.append(f['path']+': checksum')
        return {'ok':not bad,'bad':bad,'manifest':m}


def detect_removable_mounts() -> List[str]:
    roots=[]
    user=os.environ.get('USER','')
    for base in ['/media/'+user if user else '', '/run/media/'+user if user else '', '/mnt', '/Volumes']:
        if base and os.path.isdir(base):
            for p in Path(base).iterdir():
                if p.is_dir() and os.access(p,os.W_OK): roots.append(str(p.resolve()))
    return sorted(set(roots))


def copy_bundle(bundle: str, destination: str) -> str:
    dst=Path(destination).expanduser().resolve(); dst.mkdir(parents=True,exist_ok=True)
    target=dst/Path(bundle).name
    shutil.copy2(bundle,target)
    shutil.copy2(bundle,str(target)+'.sha256.tmp') if False else None
    Path(str(target)+'.sha256').write_text(sha256_file(target)+'  '+target.name+'\n',encoding='utf-8')
    return str(target)


def _iso_candidates(roots) -> List[Path]:
    """Return real .iso files reachable from the supplied roots.

    The search is deliberately shallow.  The finished Groovebox image lives in
    ``BUILD_ISO/dist`` beside the source tree, or next to a packaged executable;
    it is never buried in a random project subdirectory.  Keeping the walk
    shallow also avoids touching a slow USB stick while the GUI is starting.
    """
    seen=set(); out=[]
    for root in roots:
        if not root: continue
        try: p=Path(root).expanduser()
        except Exception: continue
        try:
            if p.is_file():
                candidates=[p] if p.suffix.lower()=='.iso' else []
            elif p.is_dir():
                candidates=[]
                for pattern in ('*.iso','*/*.iso','*/*/*.iso'):
                    try: candidates.extend(p.glob(pattern))
                    except Exception: pass
            else:
                continue
        except OSError:
            continue
        for c in candidates:
            try:
                r=c.resolve()
                if r in seen or not r.is_file() or r.suffix.lower()!='.iso': continue
                seen.add(r); out.append(r)
            except OSError:
                pass
    return out


def find_finished_iso(*extra_roots, prefer_name: Optional[str]=None) -> Optional[Path]:
    """Locate the newest finished Groovebox ISO without prompting the user.

    Search order covers the source tree, the packaged executable, the installed
    appliance and the usual Downloads folder.  Set ``GROOVEBOX_ISO`` (or
    ``GROOVEBOX_ISO_PATH``) to point at a specific image when running from a
    read-only live medium.
    """
    roots=[]
    env=os.environ.get('GROOVEBOX_ISO') or os.environ.get('GROOVEBOX_ISO_PATH')
    if env: roots.append(env)
    roots.extend(extra_roots)
    here=Path(__file__).resolve().parent
    roots.extend([here, here/'BUILD_ISO'/'dist', here/'dist'])
    for parent in list(here.parents)[:4]:
        roots.extend([parent/'BUILD_ISO'/'dist', parent/'dist'])
    roots.extend([
        Path('/opt/groovebox/BUILD_ISO/dist'), Path('/opt/groovebox/dist'),
        Path.home()/'Downloads', Path.cwd(),
    ])
    candidates=_iso_candidates(roots)
    if prefer_name:
        named=[c for c in candidates if prefer_name.lower() in c.name.lower()]
        if named: candidates=named
    if not candidates: return None
    try: return max(candidates,key=lambda p:p.stat().st_mtime)
    except OSError: return candidates[0]


def copy_iso_to_mount(iso: str, destination: str, *, subdir: str='Groovebox/ISO',
                      progress: Optional[Callable[[int,int,str],None]]=None) -> Dict:
    """Copy a finished ISO into a mounted drive without disturbing its contents.

    This is the OS-update style path: the image is placed in a subdirectory,
    every existing file/folder beside it is preserved, and an existing image of
    the same name is replaced atomically through a ``.part`` file.  A SHA-256
    sidecar is written after the copy so the receiving machine can verify it.

    ``destination`` is a mounted directory (USB/SD/another disk), not a raw
    block device.  Raw ``dd`` writing is intentionally not used here because it
    would destroy the files the user asked us to preserve.
    """
    src=Path(iso).expanduser().resolve()
    if not src.is_file(): raise FileNotFoundError(f'ISO not found: {src}')
    if src.suffix.lower()!='.iso': raise ValueError(f'Not an ISO image: {src}')
    dst=Path(destination).expanduser().resolve()
    if not dst.is_dir(): raise NotADirectoryError(f'Destination is not a mounted directory: {dst}')
    if not os.access(dst,os.W_OK): raise PermissionError(f'Destination is not writable: {dst}')
    target_dir=dst/subdir
    target_dir.mkdir(parents=True,exist_ok=True)
    target=target_dir/src.name
    if target.resolve()==src:
        return {'path':str(target),'sha256':sha256_file(target),'bytes':target.stat().st_size,
                'source':str(src),'subdir':subdir,'skipped':True}
    total=src.stat().st_size
    try:
        free=shutil.disk_usage(dst).free
    except OSError:
        free=total
    if free < total:
        raise OSError(f'Not enough free space on {dst}: need {total} bytes, have {free}')
    part=target.with_name(target.name+'.part')
    try:
        with src.open('rb') as rf, part.open('wb') as wf:
            done=0
            if progress: progress(0,total,'copying')
            while True:
                chunk=rf.read(8*1024*1024)
                if not chunk: break
                wf.write(chunk); done+=len(chunk)
                if progress: progress(done,total,'copying')
            wf.flush(); os.fsync(wf.fileno())
        shutil.copystat(src,part)
        os.replace(part,target)
        digest=sha256_file(target)
        Path(str(target)+'.sha256').write_text(f'{digest}  {target.name}\n',encoding='utf-8')
    finally:
        try:
            if part.exists(): part.unlink()
        except OSError:
            pass
    if progress: progress(total,total,'verified')
    return {'path':str(target),'sha256':digest,'bytes':total,'source':str(src),
            'subdir':subdir,'skipped':False}


def local_addresses(port:int) -> List[str]:
    ips=set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
            ip=info[4][0]
            if not ip.startswith('127.'): ips.add(ip)
    except Exception: pass
    return [f'http://{ip}:{port}/' for ip in sorted(ips)] or [f'http://127.0.0.1:{port}/']

class CloneShareServer:
    def __init__(self, directory:str, port:int=8783):
        self.directory=str(Path(directory).resolve()); self.port=int(port); self.httpd=None; self.thread=None
    def start(self):
        directory=self.directory
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self,*a,**kw): super().__init__(*a,directory=directory,**kw)
            def log_message(self,fmt,*args): pass
        self.httpd=ThreadingHTTPServer(('0.0.0.0',self.port),Handler)
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True); self.thread.start(); return self.urls()
    def urls(self): return local_addresses(self.port)
    def stop(self):
        if self.httpd:
            self.httpd.shutdown(); self.httpd.server_close(); self.httpd=None
