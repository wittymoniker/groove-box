#!/usr/bin/env python3
from __future__ import annotations
import os, platform, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def platform_key():
    s=platform.system().lower(); m=platform.machine().lower()
    if m=='amd64': m='x86_64'
    if m=='aarch64': m='arm64'
    return s,m

def scode_stage0_candidates(root: Path|None=None):
    root=Path(root or ROOT)/'sCode'/'bootstrap'; s,m=platform_key()
    if s=='windows': names=[root/f'windows-{m}'/'scode0.exe']
    elif s=='darwin': names=[root/f'macos-{m}'/'scode0']
    elif s=='linux': names=[root/f'linux-{m}'/'scode0']
    else: names=[]
    return names

def stage0_binary_matches_host(path: Path) -> bool:
    try: head=Path(path).read_bytes()[:8]
    except Exception: return False
    s,m=platform_key()
    if s=='windows': return head[:2]==b'MZ'
    if s=='linux': return head[:4]==b'\x7fELF'
    if s=='darwin': return head[:4] in (b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf')
    return False

def find_scode_stage0(root: Path|None=None):
    return next((p for p in scode_stage0_candidates(root) if p.is_file() and stage0_binary_matches_host(p)), None)

def cpp_accel_candidates(root: Path|None=None):
    root=Path(root or ROOT); s,_=platform_key()
    if s=='windows': names=['groovebox_accel.dll']
    elif s=='darwin': names=['libgroovebox_accel.dylib']
    else: names=['libgroovebox_accel.so']
    return [root/d/n for d in ('native','cpp','') for n in names]

def rust_accel_candidates(root: Path|None=None):
    root=Path(root or ROOT); s,_=platform_key()
    if s=='windows': names=['groovebox_rust_accel.dll']
    elif s=='darwin': names=['libgroovebox_rust_accel.dylib']
    else: names=['libgroovebox_rust_accel.so']
    # Crate-local target/ is intentionally excluded: sudo ISO builds used to leave
    # it root-owned and poison later desktop launches. Only installed runtime
    # artifacts are candidates.
    return [root/d/n for d in ('native','') for n in names]

def accel_candidates(root: Path|None=None):
    # GROOVEBOX_NATIVE_BACKEND=rust|cpp|auto.  v35.22z makes Rust the
    # preferred auto backend now that it implements the complete accelerator ABI;
    # C++ and NumPy remain deterministic fallbacks.
    pref=os.environ.get('GROOVEBOX_NATIVE_BACKEND','auto').strip().lower()
    cpp=cpp_accel_candidates(root); rust=rust_accel_candidates(root)
    if pref=='rust': return rust+cpp
    if pref=='cpp': return cpp+rust
    return rust+cpp

def find_accel(root: Path|None=None):
    return next((p for p in accel_candidates(root) if p.is_file()), None)

def find_rust_accel(root: Path|None=None):
    return next((p for p in rust_accel_candidates(root) if p.is_file()), None)

def build_rust_accel(root: Path|None=None):
    root=Path(root or ROOT); helper=root/'scripts'/'build_rust_accel.py'
    if not helper.is_file(): return None
    try:
        subprocess.run([os.fspath(shutil.which('python3') or shutil.which('python') or os.sys.executable),str(helper)],cwd=root,check=True)
    except Exception:
        return None
    return find_rust_accel(root)

def build_accel(root: Path|None=None):
    root=Path(root or ROOT); src=root/'cpp'/'groovebox_accel.cpp'; outdir=root/'native'; outdir.mkdir(exist_ok=True)
    if not src.is_file(): return None
    s,_=platform_key()
    try:
        if s=='windows':
            cl=shutil.which('cl'); gxx=shutil.which('g++')
            out=outdir/'groovebox_accel.dll'
            if cl: subprocess.run([cl,'/nologo','/std:c++17','/O2','/DNDEBUG','/LD',str(src),f'/Fe:{out}'],cwd=root,check=True)
            elif gxx: subprocess.run([gxx,'-std=c++17','-O3','-DNDEBUG','-shared',str(src),'-o',str(out)],cwd=root,check=True)
            else: return None
        elif s=='darwin':
            c=shutil.which('clang++') or shutil.which('c++'); out=outdir/'libgroovebox_accel.dylib'
            if not c: return None
            subprocess.run([c,'-std=c++17','-O3','-DNDEBUG','-dynamiclib',str(src),'-o',str(out)],cwd=root,check=True)
        elif s=='linux':
            c=shutil.which('g++') or shutil.which('c++'); out=outdir/'libgroovebox_accel.so'
            if not c: return None
            subprocess.run([c,'-std=c++17','-O3','-DNDEBUG','-fPIC','-shared',str(src),'-o',str(out)],cwd=root,check=True)
        else: return None
        return out if out.is_file() else None
    except Exception:
        return None


def accelerator_status(root: Path|None=None):
    """Non-invasive capability snapshot; never builds or initializes a backend."""
    root=Path(root or ROOT)
    try:
        cpp=next((p for p in cpp_accel_candidates(root) if p.is_file()), None)
    except Exception:
        cpp=None
    try:
        rust=next((p for p in rust_accel_candidates(root) if p.is_file()), None)
    except Exception:
        rust=None
    try:
        stage0=find_scode_stage0(root)
    except Exception:
        stage0=None
    try:
        import julia_bridge
        julia=julia_bridge.julia_status()
    except Exception as exc:
        julia=f"unavailable: {exc}"
    preferred=os.environ.get("GROOVEBOX_NATIVE_BACKEND","auto").strip().lower()
    selected="rust" if preferred in ("auto","rust") and rust else ("cpp" if cpp else "python")
    if preferred == "cpp" and cpp:
        selected="cpp"
    elif preferred == "rust" and not rust:
        selected="cpp" if cpp else "python"
    return {"selected_native":selected, "rust":str(rust) if rust else None,
            "cpp":str(cpp) if cpp else None, "scode_stage0":str(stage0) if stage0 else None,
            "julia":julia, "python_fallback":True}
