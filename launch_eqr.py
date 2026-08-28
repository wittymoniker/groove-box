#!/usr/bin/env python3
"""Launch Groovebox V1 (desktop)."""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# Prefer same-dir groovebox.py
os.chdir(ROOT)

def main() -> int:
    from PyQt6.QtWidgets import QApplication
    import groovebox
    app = QApplication(sys.argv)
    win = groovebox.MathematiciansGrooveboxApp()
    win.show()
    return int(app.exec())

if __name__ == "__main__":
    raise SystemExit(main())
