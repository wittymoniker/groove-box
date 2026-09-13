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
    stage0=find_scode_stage0(ROOT)
    if not stage0:
        expected = {'windows':'sCode/bootstrap/windows-x86_64/scode0.exe',
                    'darwin':f'sCode/bootstrap/macos-{m}/scode0',
                    'linux':f'sCode/bootstrap/linux-{m}/scode0'}.get(s,'sCode/bootstrap/<platform>/scode0')
        _log(f'[launcher] WARNING: native sCode stage-0 not present for this host: {expected}')
        _log('[launcher] Continuing with the supported Python/NumPy Groovebox fallback; native sCode acceleration is disabled for this run.')
    else:
        if os.name!='nt':
            try: stage0.chmod(stage0.stat().st_mode | 0o755)
            except OSError: pass
        _log(f'[launcher] sCode stage-0: {stage0}')
    return subprocess.call([sys.executable,str(ROOT/'run_groovebox.py'),*sys.argv[1:]],cwd=ROOT)

if __name__=='__main__': raise SystemExit(main())
