#!/usr/bin/env python3
from __future__ import annotations
import os, platform, subprocess, sys
from pathlib import Path
APP_NAME="Groovebox"; TARGET_NAME="groovebox_bootstrap.py"
def package_dir(): return Path(__file__).resolve().parent
def main():
    system=platform.system()
    if system not in {"Windows","Darwin"}:
        print(f"[!] This launcher is for Windows/macOS; detected {system}.")
        print("    Use groovebox.sh on Linux."); return 2
    root=package_dir(); target=root/TARGET_NAME
    if not target.is_file(): raise FileNotFoundError(target)
    if sys.version_info < (3,10): raise RuntimeError("Groovebox requires Python 3.10+")
    try: __import__("PyQt6")
    except ImportError: print("PyQt6 is not installed."); return 2
    os.chdir(root)
    return subprocess.run([sys.executable,str(target),*sys.argv[1:]],cwd=str(root),check=False).returncode
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e: print(f"[!] {e}",file=sys.stderr); raise SystemExit(1)
