"""Strict project-local FFmpeg/ffprobe resolver.

Runtime codec work is deliberately pinned to the shipped/provisioned ``bin/`` pair.
A system PATH FFmpeg is never selected implicitly, preventing host codec drift from
changing import/export behavior or determinism across machines.
"""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

def _candidate_roots():
    seen=[]
    def add(p):
        try:
            p=Path(p).resolve()
            if p not in seen: seen.append(p)
        except Exception: pass
    add(Path(__file__).resolve().parent)
    if getattr(sys,'_MEIPASS',None): add(Path(sys._MEIPASS))
    try: add(Path(sys.executable).resolve().parent)
    except Exception: pass
    return seen

def local_bin_dirs():
    return [p/'bin' for p in _candidate_roots()]

def resolve_local_tool(name: str, required: bool=False):
    exe = name + ('.exe' if os.name=='nt' and not str(name).lower().endswith('.exe') else '')
    for b in local_bin_dirs():
        p=b/exe
        if p.is_file():
            if os.name!='nt' and not os.access(p,os.X_OK):
                try: p.chmod(p.stat().st_mode|0o111)
                except OSError: pass
            if os.name=='nt' or os.access(p,os.X_OK): return str(p)
    if required:
        roots=', '.join(str(x) for x in local_bin_dirs())
        raise RuntimeError(f"Required local {name} not found in Groovebox bin/. Checked: {roots}. Run scripts/provision_first_launch.py.")
    return None

def validate_local_tool(name: str) -> bool:
    p=resolve_local_tool(name,False)
    if not p: return False
    try:
        r=subprocess.run([p,'-hide_banner','-version'],capture_output=True,text=True,timeout=8,check=False)
        return r.returncode==0 and f'{name} version' in ((r.stdout or '')+'\n'+(r.stderr or '')).lower()
    except Exception: return False

def require_local_pair():
    missing=[n for n in ('ffmpeg','ffprobe') if not validate_local_tool(n)]
    if missing: raise RuntimeError('Invalid/missing project-local codec tool(s): '+', '.join(missing)+'. Run scripts/provision_first_launch.py before launching/building.')
    return resolve_local_tool('ffmpeg',True), resolve_local_tool('ffprobe',True)
