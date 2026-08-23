#!/usr/bin/env python3
"""Cross-platform Groovebox launcher for Windows and macOS.

Always launches the groovebox.py bundled beside this launcher, never a copy
found through PATH or the caller's current working directory.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "Groovebox"
TARGET_NAME = "groovebox.py"


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def target_script() -> Path:
    target = package_dir() / TARGET_NAME
    if not target.is_file():
        raise FileNotFoundError(f"Bundled {TARGET_NAME} not found: {target}")
    return target


def check_python() -> None:
    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"{APP_NAME} requires Python 3.10 or newer; "
            f"found {platform.python_version()}."
        )


def check_pyqt() -> None:
    try:
        __import__("PyQt6")
    except ImportError:
        print("[!] PyQt6 is not installed in this Python environment.")
        print(f"    Python: {sys.executable}")
        print("    Install with: python -m pip install PyQt6")
        raise SystemExit(2)


def main() -> int:
    system = platform.system()
    if system not in {"Windows", "Darwin"}:
        print(f"[!] This launcher is for Windows/macOS; detected {system}.")
        print("    Use groovebox.sh on Linux.")
        return 2

    root = package_dir()
    target = target_script()
    check_python()
    check_pyqt()

    # Make the bundled package the working directory so relative resources,
    # presets, exports, and support files always resolve inside this package.
    os.chdir(root)

    print(f"[*] {APP_NAME} launcher")
    print(f"    OS       : {system}")
    print(f"    Python   : {sys.executable}")
    print(f"    Package  : {root}")
    print(f"    Target   : {target}")

    # Use the exact interpreter that launched this file. This avoids PATH
    # selecting a different Python installation on Windows or macOS.
    command = [sys.executable, str(target), *sys.argv[1:]]

    # subprocess.run is intentional here: it behaves consistently on both
    # Windows and macOS and preserves the application's exit status.
    try:
        completed = subprocess.run(command, cwd=str(root), check=False)
    except KeyboardInterrupt:
        return 130
    return completed.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        raise SystemExit(1)
    except RuntimeError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        raise SystemExit(1)
