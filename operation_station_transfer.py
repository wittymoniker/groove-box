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
from typing import Dict, List, Optional

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
                        include_dependencies=True, include_user_content=False, app_version='V3 Operation Station') -> str:
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
