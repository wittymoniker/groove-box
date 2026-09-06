#!/usr/bin/env python3
"""Canonical MatGroovebox launcher. sCode is the authoritative studio entry language."""
import os, sys
from pathlib import Path

def _legacy_python_entry():
    from groovebox import MathematiciansGrooveboxApp, QApplication
    from mcc_filetype import project_argument, register_filetype
    app=QApplication(sys.argv); app.setApplicationName("Mathematician's Groovebox")
    player=MathematiciansGrooveboxApp(); player.show()
    register_filetype(os.path.join(os.path.dirname(__file__),"groovebox.py"))
    path=project_argument(sys.argv[1:])
    if path:
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0,lambda p=path: player.open_project_path(p))
    raise SystemExit(app.exec())

if __name__=='__main__':
    if os.environ.get('MATGROOVEBOX_LEGACY_PYTHON_ENTRY')=='1':
        _legacy_python_entry()
    else:
        from scode.runtime import run_program
        raise SystemExit(run_program(Path(__file__).with_name('MasterGrooveboxStudio.scode'),sys.argv))
