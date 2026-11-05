#!/usr/bin/env python3
"""Compatibility entry point; all launch paths share the hardened runner."""
import runpy
import os
from pathlib import Path

if __name__ == "__main__":
    os.chdir(Path(__file__).absolute().parent)
    runpy.run_path(str(Path(__file__).resolve().with_name("run_groovebox.py")),
                   run_name="__main__")
