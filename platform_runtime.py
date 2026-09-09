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

def find_scode_stage0(root: Path|None=None):
    return next((p for p in scode_stage0_candidates(root) if p.is_file()), None)

def accel_candidates(root: Path|None=None):
    root=Path(root or ROOT); s,_=platform_key()
    if s=='windows': names=['groovebox_accel.dll']
    elif s=='darwin': names=['libgroovebox_accel.dylib']
    else: names=['libgroovebox_accel.so']
    return [root/d/n for d in ('native','cpp','') for n in names]

def find_accel(root: Path|None=None):
    return next((p for p in accel_candidates(root) if p.is_file()), None)

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
