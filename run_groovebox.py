#!/usr/bin/env python3
"""Required-sCode entry point for Mathematician's Groovebox appliance build."""
import sys, subprocess
from pathlib import Path
from groovebox_media_tools import require_local_pair

# STORAGE_LAYOUT_20260909: make every writable application path exist before
# FFmpeg, camera, networking, project autosave, or the Qt UI starts. Appliance
# builds set GROOVEBOX_DATA_DIR=/var/lib/groovebox; desktop builds use the
# platform-native per-user data location.
try:
    import groovebox_paths
    _GROOVEBOX_PATHS = groovebox_paths.ensure_app_layout()
    print(f"[Groovebox] writable data root: {_GROOVEBOX_PATHS['base']}")
except Exception as _path_exc:
    raise SystemExit(f"Groovebox cannot initialize its writable data directories: {_path_exc}")

# Standalone/sOS appliances select the best installed Wi-Fi radio before the
# nearby-share service is imported. Desktop installs are left untouched.
try:
    from appliance_wifi import prepare_if_appliance
    _APPLIANCE_WIFI = prepare_if_appliance()
    if _APPLIANCE_WIFI:
        _wi = _APPLIANCE_WIFI.get("preferred_direct_iface") or "auto"
        print(f"[Groovebox Appliance] Wi-Fi Direct radio: {_wi}")
except Exception as _wifi_exc:
    _APPLIANCE_WIFI = {}
    print(f"[Groovebox Appliance] Wi-Fi auto-config fallback: {_wifi_exc}")

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
