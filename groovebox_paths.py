"""Central filesystem locations for Groovebox user data.

Kept deliberately small so source, PyInstaller, RPM and Flatpak builds can all
redirect writable state without writing into the application installation tree.
"""
from __future__ import annotations
import os
from pathlib import Path

APP_DIRNAME = "MathematiciansGroovebox"

def _data_root() -> Path:
    override = os.environ.get("GROOVEBOX_DATA_DIR", "").strip()
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home())) / APP_DIRNAME
    elif __import__('sys').platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / APP_DIRNAME
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root

def _sub(name: str) -> Path:
    p = _data_root() / name
    p.mkdir(parents=True, exist_ok=True)
    return p

def projects_dir() -> str:
    return str(_sub("projects"))

def games_dir() -> str:
    return str(_sub("games"))

def samples_dir() -> str:
    return str(_sub("samples"))

def renders_dir() -> str:
    return str(_sub("renders"))
