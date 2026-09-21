#!/usr/bin/env python3
from __future__ import annotations
import os, platform, subprocess, sys
from pathlib import Path
from datetime import datetime
from platform_runtime import find_scode_stage0, find_accel, build_accel, platform_key

ROOT=Path(__file__).resolve().parent

def _is_fedora_host():
    try:
        text=Path('/etc/os-release').read_text(errors='ignore').lower()
    except Exception:
        return False
    return 'id=fedora' in text or 'id_like=fedora' in text or ' fedora' in text

def _ensure_fedora_qt_isolation():
    if not (sys.platform.startswith('linux') and _is_fedora_host()):
        return
    if os.environ.get('GROOVEBOX_FEDORA_QT_ISOLATED') == '1':
        return
    env=os.environ.copy()
    env['PYTHONNOUSERSITE']='1'
    env['GROOVEBOX_FEDORA_QT_ISOLATED']='1'
    env.pop('PYTHONPATH',None)
    os.execve(sys.executable,[sys.executable,'-s',str(Path(__file__).resolve()),*sys.argv[1:]],env)

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
    _ensure_fedora_qt_isolation()
    s,m=platform_key()
    _log(f'[launcher] detected {platform.system()} {platform.machine()}')

    # V35.22b_RUNTIME_MANIFEST: direct Python launches get the same dependency
    # verification/repair as the platform launchers. If the checker selects a
    # project-local interpreter, restart this launcher under that exact Python.
    runtime_check = ROOT/'scripts'/'ensure_runtime_dependencies.py'
    rr = subprocess.run([sys.executable, str(runtime_check)], cwd=ROOT, text=True, capture_output=True, check=False)
    if rr.stderr:
        for line in rr.stderr.splitlines(): _log(line)
    if rr.returncode:
        _log(f'[launcher] ERROR: runtime dependency provisioning failed ({rr.returncode})')
        return rr.returncode
    selected = (rr.stdout or '').strip().splitlines()[-1] if (rr.stdout or '').strip() else ''
    if not selected:
        _log('[launcher] ERROR: runtime checker returned no Python interpreter')
        return 12
    try:
        same = Path(selected).resolve() == Path(sys.executable).resolve()
    except Exception:
        same = os.path.abspath(selected) == os.path.abspath(sys.executable)
    if not same:
        _log(f'[launcher] switching to provisioned runtime: {selected}')
        os.execv(selected, [selected, str(Path(__file__).resolve()), *sys.argv[1:]])
    # Always finish local runtime provisioning before verifying/starting sCode.
    # Platform launchers also invoke dependency installers on first launch; this
    # common pass keeps direct launch_groovebox.py use consistent on every OS.
    provision=ROOT/'scripts'/'provision_first_launch.py'
    pr=subprocess.run([sys.executable,str(provision)],cwd=ROOT,check=False)
    if pr.returncode:
        _log(f'[launcher] ERROR: local runtime provisioning failed ({pr.returncode})')
        return pr.returncode

    # V35.22a_SCODE_POOL_CATALOG: direct Python launches get the same
    # native stage-0 repair/compatibility preflight as platform launchers.
    scode_check=ROOT/'scripts'/'ensure_native_scode_stage0.py'
    sr=subprocess.run([sys.executable,str(scode_check)],cwd=ROOT,check=False)
    if sr.returncode:
        _log(f'[launcher] ERROR: native sCode ABI preflight failed ({sr.returncode})')
        return sr.returncode

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
