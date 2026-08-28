#!/usr/bin/env python3
"""PyInstaller-friendly entry point for Groovebox."""
from groovebox import MathematiciansGrooveboxApp, QApplication
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = MathematiciansGrooveboxApp()
    player.show()
    raise SystemExit(app.exec())
