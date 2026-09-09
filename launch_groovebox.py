#!/usr/bin/env python3
from __future__ import annotations
import os, platform, subprocess, sys
from pathlib import Path
from platform_runtime import find_scode_stage0, find_accel, build_accel, platform_key

ROOT=Path(__file__).resolve().parent

def main():
    s,m=platform_key()
    print(f'[launcher] detected {platform.system()} {platform.machine()}')
    accel=find_accel(ROOT)
    if accel:
        print(f'[launcher] native accelerator: {accel.name}')
    else:
        built=build_accel(ROOT)
        if built: print(f'[launcher] built native accelerator: {built.name}')
        else: print('[launcher] no matching native accelerator; NumPy/Python fallback will be used')
    stage0=find_scode_stage0(ROOT)
    if not stage0:
        expected = {'windows':'sCode/bootstrap/windows-x86_64/scode0.exe',
                    'darwin':f'sCode/bootstrap/macos-{m}/scode0',
                    'linux':f'sCode/bootstrap/linux-{m}/scode0'}.get(s,'sCode/bootstrap/<platform>/scode0')
        print(f'[launcher] ERROR: verified sCode stage-0 missing for this host: {expected}', file=sys.stderr)
        print('[launcher] This package will not load the Linux sCode runtime on Windows/macOS.', file=sys.stderr)
        return 2
    if os.name!='nt':
        try: stage0.chmod(stage0.stat().st_mode | 0o755)
        except OSError: pass
    print(f'[launcher] sCode stage-0: {stage0}')
    provision=ROOT/'scripts'/'provision_first_launch.py'
    subprocess.run([sys.executable,str(provision)],cwd=ROOT,check=False)
    return subprocess.call([sys.executable,str(ROOT/'run_groovebox.py'),*sys.argv[1:]],cwd=ROOT)

if __name__=='__main__': raise SystemExit(main())
