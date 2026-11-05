# GROOVEBOX_V35_22ZZ_DELL_AUDIO_FALLBACK_20260926
#!/usr/bin/env python3
"""Hardware discovery for Mathematician's Groovebox appliance/desktop builds.

Read-only detection.  Qt/libinput remains responsible for keyboard, mouse,
touch and tablet events; this module reports what the OS exposes and discovers
optional audio/MIDI/gamepad/video/Bluetooth tooling without changing canonical
composition state.
"""
from __future__ import annotations
import glob, os, shutil, subprocess
from dataclasses import dataclass, asdict
from typing import List, Dict, Any


def run_bounded(args, timeout=2.0, *, env=None, text=True):
    """Run a disposable probe with a hard wall-clock bound.

    GROOVEBOX_HW_PROCESS_GROUP_20261031: helper children can spawn their own
    blocking helpers (pipewire, bluetoothctl, wpctl).  On timeout kill the whole
    process group, not just the direct child, otherwise descendants survive and
    hold device locks.  Raises subprocess.TimeoutExpired after reaping.
    """
    kwargs = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text, env=env)
    if os.name == 'posix':
        kwargs['start_new_session'] = True
    elif os.name == 'nt':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
    proc = subprocess.Popen(args, **kwargs)
    try:
        out, err = proc.communicate(timeout=max(0.05, float(timeout)))
        return subprocess.CompletedProcess(args, proc.returncode, out, err)
    except subprocess.TimeoutExpired:
        try:
            if proc.poll() is None:
                if os.name == 'posix':
                    os.killpg(proc.pid, 9)
                else:
                    proc.kill()
        except Exception:
            try: proc.kill()
            except Exception: pass
        try:
            out, err = proc.communicate(timeout=1.0)
        except Exception:
            out, err = '', ''
        raise subprocess.TimeoutExpired(args, timeout, output=out, stderr=err)


def run_probe_retry(args, timeout=2.0, *, retries=1):
    """GROOVEBOX_PROBE_CRASH_GUARD_20261102: run a disposable probe child and survive its crash.

    A probe that dies from a signal (negative return code, e.g. -3 = SIGQUIT, -6 = SIGABRT,
    -11 = SIGSEGV inside PortAudio / ALSA / JACK) is retried once in a fresh process. If it keeps
    dying, the returned CompletedProcess carries a plain-language reason in stderr (signal name and
    return code) so Performance startup can report it instead of silently listing no devices.
    JACK is told never to auto-start a server from the probe. TimeoutExpired still propagates.
    """
    import signal as _signal
    import time as _time
    env = dict(os.environ)
    env.setdefault("JACK_NO_START_SERVER", "1")
    last = None
    for attempt in range(max(0, int(retries)) + 1):
        cp = run_bounded(args, timeout=timeout, env=env)
        if cp.returncode >= 0:
            return cp
        last = cp
        _time.sleep(0.25)
    try:
        name = _signal.Signals(-last.returncode).name
    except Exception:
        name = f"signal {-last.returncode}"
    note = (f"probe child was killed by {name} (return code {last.returncode}) twice; "
            f"device list left empty and Performance keeps running\n")
    return subprocess.CompletedProcess(last.args, last.returncode, last.stdout or "", note + (last.stderr or ""))


def _cmd(args, timeout=2.0):
    try:
        p=run_bounded(args, timeout=timeout)
        return (p.stdout or p.stderr or '').strip()
    except subprocess.TimeoutExpired as exc:
        return (exc.stdout or exc.stderr or '').strip() if isinstance(exc.stdout or exc.stderr, str) else ''
    except Exception:
        return ''


def _on_qt_gui_thread() -> bool:
    """True only on the GUI thread of a live QCoreApplication.

    GROOVEBOX_HW_QT_THREAD_SAFE_20261030: QMediaDevices/QGuiApplication must never
    be touched from a worker thread (it spins up per-thread socket notifiers that
    are destroyed before the object, crashing during teardown) nor without an
    application (null QObject::connect).  Off the GUI thread we use sysfs/OS probes.
    """
    try:
        from PyQt6.QtCore import QCoreApplication, QThread
        app = QCoreApplication.instance()
        return app is not None and QThread.currentThread() == app.thread()
    except Exception:
        return False


def _read_text(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().strip()
    except Exception:
        return ''


def _v4l_cameras():
    """Named V4L2 capture nodes from sysfs (no Qt, safe on any thread/process)."""
    out = []
    for node in sorted(glob.glob('/dev/video*'))[:64]:
        base = os.path.basename(node)
        sysd = '/sys/class/video4linux/' + base
        caps_txt = _read_text(sysd + '/device_caps')
        if caps_txt:
            try:
                caps = int(caps_txt, 16)
                # Skip metadata/output-only nodes (UVC exposes a second videoN per camera).
                if not (caps & 0x00000001 or caps & 0x00001000):
                    continue
            except ValueError:
                pass
        name = _read_text(sysd + '/name') or base
        out.append(f"{name} ({node})")
    return out[:32]


def _input_names():
    names=[]
    try:
        with open('/proc/bus/input/devices','r',encoding='utf-8',errors='replace') as f:
            for ln in f:
                if ln.startswith('N: Name='):
                    names.append(ln.split('=',1)[1].strip().strip('"'))
    except Exception:
        pass
    return names


def _classify_inputs(names):
    low=[n.lower() for n in names]
    return {
        'keyboard': [n for n,l in zip(names,low) if 'keyboard' in l or 'kbd' in l],
        'touch': [n for n,l in zip(names,low) if 'touch' in l or 'digitizer' in l],
        'mouse': [n for n,l in zip(names,low) if 'mouse' in l or 'trackpad' in l or 'touchpad' in l],
        'gamepad': [n for n,l in zip(names,low) if any(k in l for k in ('gamepad','joystick','controller'))],
    }


def scan() -> Dict[str, Any]:
    """Return a merged OS + Qt view of live hardware.

    Qt Multimedia is the authoritative source for devices Groovebox can
    actually open. OS probes remain as fallbacks/diagnostics so a missing
    PipeWire utility cannot make the Hardware page falsely report zero.
    """
    names=_input_names(); cls=_classify_inputs(names)
    usb=_cmd(['lsusb']) if shutil.which('lsusb') else ''
    bt=_cmd(['bluetoothctl','devices','Connected']) if shutil.which('bluetoothctl') else ''

    # Display discovery must not depend on X11.  sOS normally runs Wayland.
    display_summary=[]
    try:
        from PyQt6.QtGui import QGuiApplication
        app=QGuiApplication.instance() if _on_qt_gui_thread() else None
        if app is not None:
            for scr in app.screens():
                g=scr.geometry()
                label=f"{scr.name()} {g.width()}x{g.height()} @ {scr.refreshRate():.1f} Hz"
                if label not in display_summary: display_summary.append(label)
    except Exception:
        pass
    if not display_summary and shutil.which('wlr-randr') and os.environ.get('WAYLAND_DISPLAY'):
        wr=_cmd(['wlr-randr'])
        display_summary=[ln.strip() for ln in wr.splitlines() if ln and not ln[:1].isspace()][:16]
    if not display_summary and shutil.which('xrandr') and os.environ.get('DISPLAY'):
        xr=_cmd(['xrandr','--query'])
        display_summary=[ln for ln in xr.splitlines() if ' connected' in ln][:16]

    audio_status=''
    wpctl_status=''
    if shutil.which('wpctl'):
        wpctl_status=_cmd(['wpctl','status'], timeout=1.5)
        audio_status=wpctl_status
    elif shutil.which('pactl'):
        audio_status=_cmd(['pactl','info'], timeout=1.5)
    elif os.path.exists('/proc/asound/cards'):
        audio_status=_read_text('/proc/asound/cards')

    midi=[]
    try:
        import mido
        midi=list(mido.get_input_names())
    except Exception:
        pass

    audio_outputs=[]; audio_inputs=[]; video_devices=[]
    try:
        if _on_qt_gui_thread():
            from PyQt6.QtMultimedia import QMediaDevices
            audio_outputs=[d.description() or 'Unnamed output' for d in QMediaDevices.audioOutputs()]
            audio_inputs=[d.description() or 'Unnamed input' for d in QMediaDevices.audioInputs()]
            video_devices=[d.description() or 'Unnamed camera' for d in QMediaDevices.videoInputs()]
    except Exception:
        pass

    # Supplement each side independently.  R8 used an all-or-nothing fallback,
    # so one Qt microphone could suppress discovery of every ALSA/PortAudio output.
    # That made a real speaker path invisible whenever Qt published only one input.
    try:
        from audio_os_backend import sd
        for d in sd.query_devices():
            name=str(d.get('name','')).strip()
            if not name: continue
            if not audio_outputs and int(d.get('max_output_channels',0) or 0)>0:
                audio_outputs.append(name)
            if not audio_inputs and int(d.get('max_input_channels',0) or 0)>0:
                audio_inputs.append(name)
    except Exception:
        pass

    # Dell/Intel fallback: PipeWire/ALSA may see the internal speaker before
    # Qt Multimedia publishes it to QMediaDevices during early Wayland startup.
    if not audio_outputs and wpctl_status:
        section=''
        for raw in wpctl_status.splitlines():
            line=raw.strip(); low=line.lower()
            if low.startswith('sinks:'): section='sinks'; continue
            if low.startswith('sources:'): section='sources'; continue
            if section not in {'sinks','sources'}: continue
            cleaned=line.lstrip('* ').strip()
            if '. ' in cleaned: cleaned=cleaned.split('. ',1)[1]
            cleaned=cleaned.split(' [',1)[0].strip()
            if cleaned:
                (audio_outputs if section=='sinks' else audio_inputs).append(cleaned)
    if not audio_outputs and shutil.which('pactl'):
        for line in _cmd(['pactl','list','short','sinks'], timeout=1.5).splitlines():
            cols=line.split('\t')
            if len(cols)>1: audio_outputs.append(cols[1].strip())
    if not audio_inputs and shutil.which('pactl'):
        for line in _cmd(['pactl','list','short','sources'], timeout=1.5).splitlines():
            cols=line.split('\t')
            if len(cols)>1 and '.monitor' not in cols[1]: audio_inputs.append(cols[1].strip())
    if not audio_outputs and shutil.which('aplay'):
        for line in _cmd(['aplay','-l'], timeout=1.5).splitlines():
            if line.lower().startswith('card '): audio_outputs.append(line.strip())
    if not audio_inputs and shutil.which('arecord'):
        for line in _cmd(['arecord','-l'], timeout=1.5).splitlines():
            if line.lower().startswith('card '): audio_inputs.append(line.strip())
    if not audio_outputs and os.path.exists('/proc/asound/cards'):
        try:
            for line in open('/proc/asound/cards','r',encoding='utf-8',errors='replace'):
                if line.lstrip()[:1].isdigit(): audio_outputs.append('ALSA '+line.strip())
        except Exception: pass

    # /dev/video* is useful as a last-resort visibility diagnostic even if Qt
    # cannot yet name a V4L2 camera.
    if not video_devices:
        video_devices=_v4l_cameras()

    def _uniq(seq):
        return list(dict.fromkeys(x for x in seq if x))
    audio_outputs=_uniq(audio_outputs); audio_inputs=_uniq(audio_inputs); video_devices=_uniq(video_devices)
    audio_devices=_uniq([f"Output: {x}" for x in audio_outputs] + [f"Input: {x}" for x in audio_inputs])

    return {
        'input_names': names,
        'keyboard': cls['keyboard'], 'touch': cls['touch'], 'mouse': cls['mouse'], 'gamepad': cls['gamepad'],
        'event_nodes': sorted(glob.glob('/dev/input/event*')),
        'usb': usb.splitlines()[:64] if usb else [],
        'bluetooth_connected': bt.splitlines()[:32] if bt else [],
        'display_summary': display_summary[:16],
        'audio_devices': audio_devices[:64], 'audio_outputs': audio_outputs[:32], 'audio_inputs': audio_inputs[:32],
        'video_devices': video_devices[:32], 'midi_inputs': midi[:64],
        'audio_status': audio_status,
        'tools': {k: bool(shutil.which(k)) for k in ('libinput','xinput','xrandr','wlr-randr','lsusb','bluetoothctl','wpctl','pactl','aconnect')},
        'qt_input_contract': 'Keyboard + mouse/trackpad + touchscreen coexist; touch is not kiosk-exclusive.',
    }


def summary(report=None) -> str:
    r=report or scan()
    yn=lambda xs: 'yes' if xs else 'not detected'
    return (
        f"Keyboard: {yn(r['keyboard'])} · Touch: {yn(r['touch'])} · Mouse/trackpad: {yn(r['mouse'])} · "
        f"Gamepad: {yn(r['gamepad'])}\n"
        f"Audio devices: {len(r['audio_devices'])} · Video devices: {len(r.get('video_devices',[]))} · MIDI inputs: {len(r['midi_inputs'])} · "
        f"USB entries: {len(r['usb'])} · Bluetooth connected: {len(r['bluetooth_connected'])}\n"
        f"Displays: {len(r['display_summary'])} · /dev/input events: {len(r['event_nodes'])}\n"
        + r['qt_input_contract']
    )


# GROOVEBOX_V35_22ZZ_R14_TRUE_COMPONENT_SCANS_20260930
import threading, time
_COMPONENT_CACHE={}; _COMPONENT_CACHE_LOCK=threading.Lock()
_COMPONENT_INFLIGHT={}

def _tools():
    return {k: bool(shutil.which(k)) for k in ('libinput','xinput','xrandr','wlr-randr','lsusb','bluetoothctl','wpctl','pactl','aplay','arecord','aconnect')}

def _uniq(seq): return list(dict.fromkeys(x for x in seq if x))

# ---------------------------------------------------------------------------
# GROOVEBOX_R23R_DESKTOP_OS_PROBES_20261101
# The probe helper and scan lanes run without Qt, and every fallback above is
# Linux-only (/proc/bus/input, lsusb, aplay, /dev/video*). On Windows/macOS that
# left keyboards, mice, cameras, displays and USB empty in the executable
# ("no hardware detected"). One bounded, cached OS inventory now fills each
# family when the Linux probes found nothing.
# ---------------------------------------------------------------------------
_OS_INV = {'t': 0.0, 'v': None}
_OS_INV_LOCK = threading.Lock()

def _blank_inventory():
    return {k: [] for k in ('keyboard', 'mouse', 'touch', 'gamepad', 'camera', 'audio_out',
                            'audio_in', 'display', 'usb', 'bluetooth', 'midi')}

def _kind_from_name(name: str):
    low = name.casefold()
    if any(k in low for k in ('touch screen', 'touchscreen', 'touch pad', 'touchpad', 'digitizer', 'pen')):
        return 'touch' if 'pad' not in low else 'mouse'
    if any(k in low for k in ('gamepad', 'game controller', 'joystick', 'xbox', 'dualshock', 'dualsense')):
        return 'gamepad'
    if 'keyboard' in low:
        return 'keyboard'
    if any(k in low for k in ('mouse', 'trackpad', 'pointing')):
        return 'mouse'
    return None

def _windows_inventory():
    inv = _blank_inventory()
    ps = shutil.which('powershell') or shutil.which('pwsh')
    if not ps:
        return inv
    script = ("$ErrorActionPreference='SilentlyContinue';"
              "Get-PnpDevice -PresentOnly | Where-Object { $_.Status -eq 'OK' -and $_.Class -in "
              "@('Keyboard','Mouse','HIDClass','Camera','Image','AudioEndpoint','MEDIA','Monitor','USB','Bluetooth','SoftwareDevice') } | "
              "ForEach-Object { $_.Class + '|' + $_.FriendlyName + '|' + $_.InstanceId }")
    out = _cmd([ps, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script], timeout=4.5)
    for line in out.splitlines():
        parts = line.strip().split('|')
        if len(parts) < 2 or not parts[1].strip():
            continue
        cls, name = parts[0].strip(), parts[1].strip()
        iid = parts[2].strip().upper() if len(parts) > 2 else ''
        if cls == 'Keyboard':
            inv['keyboard'].append(name)
        elif cls == 'Mouse':
            inv['mouse'].append(name)
        elif cls == 'HIDClass':
            k = _kind_from_name(name)
            if k:
                inv[k].append(name)
        elif cls in ('Camera', 'Image'):
            inv['camera'].append(name)
        elif cls == 'AudioEndpoint':
            # Endpoint IDs: {0.0.0.*} render (output), {0.0.1.*} capture (input).
            (inv['audio_in'] if '{0.0.1.' in iid else inv['audio_out']).append(name)
        elif cls == 'MEDIA' and 'MIDI' in name.upper():
            inv['midi'].append(name)
        elif cls == 'Monitor':
            inv['display'].append(name)
        elif cls == 'USB':
            if not any(x in name.casefold() for x in ('root hub', 'host controller', 'generic usb hub', 'usb composite device')):
                inv['usb'].append(name)
        elif cls == 'Bluetooth':
            inv['bluetooth'].append(name)
    return inv

def _mac_inventory():
    import json as _json
    inv = _blank_inventory()
    if not shutil.which('system_profiler'):
        return inv
    out = _cmd(['system_profiler', '-json', '-detailLevel', 'mini', 'SPUSBDataType', 'SPCameraDataType',
                'SPAudioDataType', 'SPDisplaysDataType', 'SPBluetoothDataType'], timeout=6.0)
    try:
        data = _json.loads(out or '{}')
    except Exception:
        return inv
    for cam in data.get('SPCameraDataType', []) or []:
        if cam.get('_name'):
            inv['camera'].append(cam['_name'])
    for blk in data.get('SPAudioDataType', []) or []:
        for it in blk.get('_items', []) or []:
            n = it.get('_name')
            if not n:
                continue
            if it.get('coreaudio_device_output') or it.get('coreaudio_output_source'):
                inv['audio_out'].append(n)
            if it.get('coreaudio_device_input') or it.get('coreaudio_input_source'):
                inv['audio_in'].append(n)
    for gpu in data.get('SPDisplaysDataType', []) or []:
        for d in gpu.get('spdisplays_ndrvs', []) or []:
            n = d.get('_name'); res = d.get('_spdisplays_resolution') or d.get('spdisplays_resolution') or ''
            if n:
                inv['display'].append((n + ' ' + str(res)).strip())
    def _walk(items):
        for it in items or []:
            n = it.get('_name')
            if n and 'hub' not in n.lower() and not n.lower().endswith(' bus'):
                inv['usb'].append(n)
                k = _kind_from_name(n)
                if k:
                    inv[k].append(n)
            _walk(it.get('_items'))
    for bus in data.get('SPUSBDataType', []) or []:
        _walk(bus.get('_items'))
    for bt in data.get('SPBluetoothDataType', []) or []:
        for key in ('device_connected', 'devices_list'):
            for dev in bt.get(key, []) or []:
                if isinstance(dev, dict):
                    for n in dev.keys():
                        inv['bluetooth'].append(n)
                        k = _kind_from_name(n)
                        if k:
                            inv[k].append(n)
    # Built-in Mac keyboards/trackpads are SPI, not USB.
    if not inv['keyboard']:
        inv['keyboard'].append('Built-in / system keyboard')
    if not inv['mouse']:
        inv['mouse'].append('Built-in trackpad / system pointer')
    return inv

def os_inventory(ttl: float = 20.0):
    """Cached desktop OS hardware inventory (Windows PnP / macOS system_profiler); {} on Linux."""
    import sys as _sys
    if not (os.name == 'nt' or _sys.platform == 'darwin'):
        return {}
    now = time.monotonic()
    with _OS_INV_LOCK:
        if _OS_INV['v'] is not None and now - _OS_INV['t'] < ttl:
            return _OS_INV['v']
        try:
            inv = _windows_inventory() if os.name == 'nt' else _mac_inventory()
        except Exception:
            inv = _blank_inventory()
        inv = {k: _uniq(v) for k, v in inv.items()}
        _OS_INV['t'] = now; _OS_INV['v'] = inv
        return inv


def _scan_audio_only():
    outputs=[]; inputs=[]; status=''
    wp=''
    if shutil.which('wpctl'):
        wp=_cmd(['wpctl','status'],timeout=1.2); status=wp
        section=''
        for raw in wp.splitlines():
            line=raw.strip(); low=line.lower()
            if low.startswith('sinks:'): section='sinks'; continue
            if low.startswith('sources:'): section='sources'; continue
            if section not in ('sinks','sources'): continue
            cleaned=line.lstrip('* │├└─').strip()
            if '. ' in cleaned: cleaned=cleaned.split('. ',1)[1]
            cleaned=cleaned.split(' [',1)[0].strip()
            if cleaned and not any(x in cleaned.casefold() for x in ('dummy output','auto_null','.monitor')):
                (outputs if section=='sinks' else inputs).append(cleaned)
    if not outputs and shutil.which('pactl'):
        for line in _cmd(['pactl','list','short','sinks'],timeout=1.2).splitlines():
            c=line.split('\t');
            if len(c)>1 and not any(x in c[1].casefold() for x in ('dummy','auto_null')): outputs.append(c[1].strip())
    if not inputs and shutil.which('pactl'):
        for line in _cmd(['pactl','list','short','sources'],timeout=1.2).splitlines():
            c=line.split('\t');
            if len(c)>1 and '.monitor' not in c[1]: inputs.append(c[1].strip())
    # PortAudio is queried once here, not again in video/display/input lanes.
    try:
        from audio_os_backend import _device_snapshot
        for d in _device_snapshot():
            name=str(d.get('name','')).strip(); low=name.casefold()
            if not name or any(x in low for x in ('dummy','auto_null','null')): continue
            if int(d.get('max_output_channels',0) or 0)>0: outputs.append(name)
            if int(d.get('max_input_channels',0) or 0)>0 and 'monitor' not in low: inputs.append(name)
    except Exception: pass
    if not outputs and shutil.which('aplay'):
        for line in _cmd(['aplay','-l'],timeout=1.2).splitlines():
            if line.lower().startswith('card '): outputs.append(line.strip())
    if not inputs and shutil.which('arecord'):
        for line in _cmd(['arecord','-l'],timeout=1.2).splitlines():
            if line.lower().startswith('card '): inputs.append(line.strip())
    if not outputs or not inputs:
        _inv = os_inventory()
        if not outputs: outputs += _inv.get('audio_out', [])
        if not inputs: inputs += _inv.get('audio_in', [])
    outputs=_uniq(outputs); inputs=_uniq(inputs)
    return {'audio_devices':[f'Output: {x}' for x in outputs]+[f'Input: {x}' for x in inputs],
            'audio_outputs':outputs[:32],'audio_inputs':inputs[:32],'audio_status':status,'tools':_tools()}

def _scan_video_only():
    video=[]
    try:
        if _on_qt_gui_thread():  # never from workers / the Qt-less probe helper
            from PyQt6.QtMultimedia import QMediaDevices
            video=[d.description() or 'Unnamed camera' for d in QMediaDevices.videoInputs()]
    except Exception: pass
    if not video: video=_v4l_cameras()
    if not video: video=list(os_inventory().get('camera', []))
    return {'video_devices':_uniq(video),'tools':_tools()}

def _scan_display_only():
    vals=[]
    # Worker-safe sysfs/compositor probes; avoid touching QGuiApplication from a worker.
    drm=glob.glob('/sys/class/drm/card*-*/status')
    for st in sorted(drm):
        try:
            if _read_text(st)!='connected': continue
            base=os.path.basename(os.path.dirname(st)); modes=os.path.join(os.path.dirname(st),'modes'); mode=''
            if os.path.isfile(modes): mode=(_read_text(modes).splitlines() or [''])[0]
            vals.append((base + (' '+mode if mode else '')).strip())
        except Exception: pass
    if not vals and shutil.which('wlr-randr') and os.environ.get('WAYLAND_DISPLAY'):
        vals=[ln.strip() for ln in _cmd(['wlr-randr'],timeout=1.2).splitlines() if ln and not ln[:1].isspace()][:16]
    if not vals and shutil.which('xrandr') and os.environ.get('DISPLAY'):
        vals=[ln for ln in _cmd(['xrandr','--query'],timeout=1.2).splitlines() if ' connected' in ln][:16]
    if not vals: vals=list(os_inventory().get('display', []))
    return {'display_summary':_uniq(vals)[:16],'tools':_tools()}

def _scan_input_only():
    names=_input_names(); cls=_classify_inputs(names); midi=[]
    try:
        import mido; midi=list(mido.get_input_names())
    except Exception: pass
    usb=_cmd(['lsusb'],timeout=1.2) if shutil.which('lsusb') else ''
    bt=_cmd(['bluetoothctl','devices','Connected'],timeout=1.2) if shutil.which('bluetoothctl') else ''
    usb_l=usb.splitlines()[:64] if usb else []; bt_l=bt.splitlines()[:32] if bt else []
    inv=os_inventory() if not names else {}
    if inv:
        for k in ('keyboard','mouse','touch','gamepad'):
            cls[k]=_uniq(list(cls.get(k, []))+inv.get(k, []))
        names=_uniq(inv.get('keyboard', [])+inv.get('mouse', [])+inv.get('touch', [])+inv.get('gamepad', []))
        if not usb_l: usb_l=inv.get('usb', [])[:64]
        if not bt_l: bt_l=inv.get('bluetooth', [])[:32]
        if not midi: midi=inv.get('midi', [])
    return {'input_names':names,'keyboard':cls['keyboard'],'touch':cls['touch'],'mouse':cls['mouse'],'gamepad':cls['gamepad'],
            'event_nodes':sorted(glob.glob('/dev/input/event*')),'midi_inputs':midi[:64],
            'usb':usb_l,'bluetooth_connected':bt_l,
            'qt_input_contract':'Keyboard + mouse/trackpad + touchscreen coexist; touch is not kiosk-exclusive.','tools':_tools()}

def _scan_timeout():
    try:
        return max(0.25, float(os.environ.get('GROOVEBOX_HW_SCAN_TIMEOUT', '5.0')))
    except Exception:
        return 5.0


def _bounded_call(fn, timeout):
    """Run fn on a daemon lane and abandon it if it overruns."""
    box = {}; done = threading.Event()
    def _run():
        try: box['value'] = fn()
        except BaseException as exc: box['error'] = exc
        finally: done.set()
    threading.Thread(target=_run, daemon=True, name='GrooveboxHWScan').start()
    if not done.wait(max(0.05, float(timeout))):
        raise TimeoutError('hardware scan exceeded %.1f s' % float(timeout))
    if 'error' in box:
        raise box['error']
    return box.get('value')


def _cached_component(k):
    with _COMPONENT_CACHE_LOCK:
        hit = _COMPONENT_CACHE.get(k)
        return dict(hit[1]) if hit else None


def scan_component(kind: str) -> Dict[str, Any]:
    """Scan exactly one hardware family with caching, coalescing and a hard timeout."""
    k=str(kind or '').lower(); now=time.monotonic(); ttl=3.0 if k=='audio' else 0.5
    timeout=_scan_timeout(); on_gui = (k == 'video' and _on_qt_gui_thread())
    with _COMPONENT_CACHE_LOCK:
        hit=_COMPONENT_CACHE.get(k)
        if hit and now-hit[0] < ttl: return dict(hit[1])
        busy=_COMPONENT_INFLIGHT.get(k)
    if busy is not None:
        # Another lane owns this scan.  Reuse its fresh result or fail fast;
        # never stack a second unbounded enumeration on top of a hung one.
        busy.wait(min(0.25, timeout))
        hit=_cached_component(k)
        if hit is not None: return hit
        return {'_errors':['%s: scan already in progress' % k], 'tools':_tools()}
    fn={'audio':_scan_audio_only,'video':_scan_video_only,'display':_scan_display_only,'input':_scan_input_only}.get(k)
    if fn is None:
        try:
            return _bounded_call(scan, timeout)
        except Exception as exc:
            return {'_errors':['hardware: %s' % exc], 'tools':_tools()}
    event=threading.Event(); out=None
    with _COMPONENT_CACHE_LOCK:
        if _COMPONENT_INFLIGHT.get(k) is None:
            _COMPONENT_INFLIGHT[k]=event; owner=True
        else:
            owner=False
    if not owner:
        with _COMPONENT_CACHE_LOCK:
            busy=_COMPONENT_INFLIGHT.get(k)
        if busy is not None: busy.wait(min(0.25, timeout))
        hit=_cached_component(k)
        if hit is not None: return hit
        return {'_errors':['%s: scan already in progress' % k], 'tools':_tools()}
    try:
        # Qt multimedia enumeration must stay on the GUI thread; every other
        # lane is bounded because a hung CLI probe must not stall the caller.
        out = fn() if on_gui else _bounded_call(fn, timeout)
    except TimeoutError as exc:
        out=_cached_component(k)
        if out is None: out={}
        out['_errors']=list(out.get('_errors') or [])+[str(exc)]
        out.setdefault('tools', _tools())
    except Exception as exc:
        out=_cached_component(k)
        if out is None: out={}
        out['_errors']=list(out.get('_errors') or [])+['%s: %s' % (k, exc)]
        out.setdefault('tools', _tools())
    finally:
        if out is None: out={'_errors':['%s: scan aborted' % k], 'tools':_tools()}
        with _COMPONENT_CACHE_LOCK:
            _COMPONENT_CACHE[k]=(time.monotonic(),dict(out))
            _COMPONENT_INFLIGHT.pop(k, None)
        event.set()
    return out
