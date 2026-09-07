#!/usr/bin/env python3
"""Required-sCode entry point for Mathematician's Groovebox appliance build."""
import sys, subprocess
from pathlib import Path
from groovebox_media_tools import require_local_pair

def _require_local_ffmpeg():
    try:
        return require_local_pair()
    except Exception:
        provision = Path(__file__).resolve().parent / "scripts" / "provision_first_launch.py"
        subprocess.run([sys.executable, str(provision)], cwd=str(provision.parent.parent), check=False)
        return require_local_pair()

_LOCAL_FFMPEG = _require_local_ffmpeg()

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
