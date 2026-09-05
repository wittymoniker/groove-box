"""Small appliance helpers for Groovebox Performance boxes."""
from __future__ import annotations
import os, shutil, subprocess
from dataclasses import dataclass
from typing import List
@dataclass
class BoxStatus:
    ffmpeg: bool; ffprobe: bool; mpv: bool; pipewire: bool; bluetoothctl: bool; free_gb: float; cpu_count: int

def status(path:str='.') -> BoxStatus:
    du=shutil.disk_usage(os.path.abspath(path))
    return BoxStatus(bool(shutil.which('ffmpeg')),bool(shutil.which('ffprobe')),bool(shutil.which('mpv')),bool(shutil.which('pw-cli') or shutil.which('pactl')),bool(shutil.which('bluetoothctl')),du.free/1e9,os.cpu_count() or 1)

def systemd_unit(repo_dir:str)->str:
    runner=os.path.join(os.path.abspath(repo_dir),'run_groovebox.py')
    return f'''[Unit]\nDescription=Groovebox Performance Box\nAfter=graphical.target network-online.target sound.target\n\n[Service]\nType=simple\nWorkingDirectory={os.path.abspath(repo_dir)}\nExecStart=/usr/bin/env python3 {runner}\nRestart=on-failure\nRestartSec=2\nEnvironment=GROOVEBOX_BOX_MODE=1\n\n[Install]\nWantedBy=graphical.target\n'''
