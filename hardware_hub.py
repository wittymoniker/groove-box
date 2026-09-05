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


def _cmd(args, timeout=2.0):
    try:
        p=subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return (p.stdout or p.stderr or '').strip()
    except Exception:
        return ''


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
    names=_input_names(); cls=_classify_inputs(names)
    usb=_cmd(['lsusb']) if shutil.which('lsusb') else ''
    bt=_cmd(['bluetoothctl','devices','Connected']) if shutil.which('bluetoothctl') else ''
    displays=_cmd(['xrandr','--query']) if shutil.which('xrandr') and os.environ.get('DISPLAY') else ''
    audio=''
    if shutil.which('wpctl'):
        audio=_cmd(['wpctl','status'])
    elif shutil.which('pactl'):
        audio=_cmd(['pactl','info'])
    midi=[]
    try:
        import mido
        midi=list(mido.get_input_names())
    except Exception:
        pass
    sound=[]
    try:
        import sounddevice as sd
        sound=[str(d.get('name','')) for d in sd.query_devices()]
    except Exception:
        pass
    return {
        'input_names': names,
        'keyboard': cls['keyboard'], 'touch': cls['touch'], 'mouse': cls['mouse'], 'gamepad': cls['gamepad'],
        'event_nodes': sorted(glob.glob('/dev/input/event*')),
        'usb': usb.splitlines()[:64] if usb else [],
        'bluetooth_connected': bt.splitlines()[:32] if bt else [],
        'display_summary': [ln for ln in displays.splitlines() if ' connected' in ln][:16],
        'audio_devices': sound[:64], 'midi_inputs': midi[:64],
        'tools': {k: bool(shutil.which(k)) for k in ('libinput','xinput','xrandr','lsusb','bluetoothctl','wpctl','pactl','aconnect')},
        'qt_input_contract': 'Keyboard + mouse/trackpad + touchscreen coexist; touch is not kiosk-exclusive.',
    }


def summary(report=None) -> str:
    r=report or scan()
    yn=lambda xs: 'yes' if xs else 'not detected'
    return (
        f"Keyboard: {yn(r['keyboard'])} · Touch: {yn(r['touch'])} · Mouse/trackpad: {yn(r['mouse'])} · "
        f"Gamepad: {yn(r['gamepad'])}\n"
        f"Audio devices: {len(r['audio_devices'])} · MIDI inputs: {len(r['midi_inputs'])} · "
        f"USB entries: {len(r['usb'])} · Bluetooth connected: {len(r['bluetooth_connected'])}\n"
        f"Displays: {len(r['display_summary'])} · /dev/input events: {len(r['event_nodes'])}\n"
        + r['qt_input_contract']
    )
