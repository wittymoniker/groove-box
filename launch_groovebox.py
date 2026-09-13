#!/usr/bin/env python3
from __future__ import annotations
import os, platform, subprocess, sys
from pathlib import Path
from datetime import datetime
from platform_runtime import find_scode_stage0, find_accel, build_accel, platform_key

ROOT=Path(__file__).resolve().parent

def _launcher_log_path():
    base = Path(os.environ.get('APPDATA') or (Path.home()/'.local'/'share')) / 'MathematiciansGroovebox' / 'logs'
    base.mkdir(parents=True, exist_ok=True)
    return base / 'launcher.log'

def _log(msg):
    line=f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(msg)
    try:
        with _launcher_log_path().open('a', encoding='utf-8') as f: f.write(line+'\n')
    except Exception:
        pass

def main():
    s,m=platform_key()
    _log(f'[launcher] detected {platform.system()} {platform.machine()}')
    # Always finish local runtime provisioning before verifying/starting sCode.
    # Platform launchers also invoke dependency installers on first launch; this
    # common pass keeps direct launch_groovebox.py use consistent on every OS.
    provision=ROOT/'scripts'/'provision_first_launch.py'
    pr=subprocess.run([sys.executable,str(provision)],cwd=ROOT,check=False)
    if pr.returncode:
        _log(f'[launcher] ERROR: local runtime provisioning failed ({pr.returncode})')
        return pr.returncode

    accel=find_accel(ROOT)
    if accel:
        _log(f'[launcher] native accelerator: {accel.name}')
    else:
        built=build_accel(ROOT)
        if built: _log(f'[launcher] built native accelerator: {built.name}')
        else: _log('[launcher] no matching native accelerator; NumPy/Python fallback will be used')
    # Native sCode stage-0 is mandatory on every supported desktop OS.
    sp=ROOT/'scripts'/'provision_scode_stage0.py'
    sr=subprocess.run([sys.executable,str(sp)],cwd=ROOT,check=False)
    if sr.returncode:
        _log(f'[launcher] ERROR: native sCode stage-0 provisioning/ABI verification failed ({sr.returncode})')
        return sr.returncode
    stage0=find_scode_stage0(ROOT)
    if not stage0:
        _log('[launcher] ERROR: native sCode stage-0 provisioner returned success without an installed runtime')
        return 11
    if os.name!='nt':
        try: stage0.chmod(stage0.stat().st_mode | 0o755)
        except OSError: pass
    _log(f'[launcher] verified native sCode stage-0: {stage0}')
    return subprocess.call([sys.executable,str(ROOT/'run_groovebox.py'),*sys.argv[1:]],cwd=ROOT)

if __name__=='__main__': raise SystemExit(main())
