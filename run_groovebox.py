#!/usr/bin/env python3
"""Required-sCode entry point for Mathematician's Groovebox appliance build."""
import sys
from scode_optimizer_bridge import require_scode_runtime, SCodeRequiredError

# Fail before constructing a large Qt UI if the bundled native optimizer is absent.
try:
    _SCODE_PREFLIGHT = require_scode_runtime()
except Exception as exc:
    raise SystemExit(f"Groovebox appliance requires bundled sCode optimizer: {exc}")

from groovebox import MathematiciansGrooveboxApp, QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = MathematiciansGrooveboxApp()
    player.show()
    raise SystemExit(app.exec())
