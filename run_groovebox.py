#!/usr/bin/env python3
"""Required-sCode entry point for Mathematician's Groovebox appliance build."""
import sys, subprocess, os, time, traceback, threading, faulthandler
from pathlib import Path

# WINDOWS_QT_WARNING_HARDENING_20260913: Qt warnings (including a malformed QSS
# warning) are diagnostic, not a reason for the application to abort. Some
# developer/CI shells export QT_FATAL_WARNINGS=1; do not inherit that into a
# normal Groovebox desktop launch. Clear it before importing PyQt/Groovebox.
os.environ.pop("QT_FATAL_WARNINGS", None)

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

# WINDOWS_CRASH_FORENSICS_20260913: persist stdout/stderr and Python/native crash
# diagnostics before media, sCode, workers, or Qt are initialized.  A Windows
# double-click launch must never make the only traceback disappear with the console.
_LOG_DIR = Path(_GROOVEBOX_PATHS["logs"])
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_STAMP = time.strftime("%Y%m%d-%H%M%S")
_SESSION_LOG = _LOG_DIR / f"groovebox-session-{_STAMP}-{os.getpid()}.log"
_NATIVE_LOG = _LOG_DIR / f"groovebox-native-{_STAMP}-{os.getpid()}.log"
_LATEST_PTR = _LOG_DIR / "LATEST_CRASH_LOG.txt"

class _Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, data):
        for st in self.streams:
            try:
                st.write(data); st.flush()
            except Exception:
                pass
        return len(data)
    def flush(self):
        for st in self.streams:
            try: st.flush()
            except Exception: pass
    def isatty(self):
        return any(getattr(st, "isatty", lambda: False)() for st in self.streams)

_session_fp = _SESSION_LOG.open("a", encoding="utf-8", buffering=1)
_native_fp = _NATIVE_LOG.open("a", encoding="utf-8", buffering=1)
_orig_stdout, _orig_stderr = sys.stdout, sys.stderr
sys.stdout = _Tee(_orig_stdout, _session_fp)
sys.stderr = _Tee(_orig_stderr, _session_fp)
try:
    faulthandler.enable(file=_native_fp, all_threads=True)
except Exception as _fh_exc:
    print(f"[CrashLog] faulthandler unavailable: {_fh_exc}", file=sys.stderr)

def _write_latest(kind: str, detail: str = ""):
    try:
        _LATEST_PTR.write_text(
            f"kind={kind}\nsession={_SESSION_LOG}\nnative={_NATIVE_LOG}\ndetail={detail}\n",
            encoding="utf-8",
        )
    except Exception:
        pass

def _uncaught(exc_type, exc_value, exc_tb):
    _write_latest("uncaught-python", repr(exc_value))
    print("\n[CrashLog] UNCAUGHT PYTHON EXCEPTION", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)

sys.excepthook = _uncaught
try:
    def _thread_uncaught(args):
        _write_latest("uncaught-thread", repr(args.exc_value))
        print(f"\n[CrashLog] UNCAUGHT THREAD EXCEPTION in {args.thread.name}", file=sys.stderr)
        traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=sys.stderr)
    threading.excepthook = _thread_uncaught
except Exception:
    pass

_write_latest("running")
print(f"[CrashLog] session log: {_SESSION_LOG}")
print(f"[CrashLog] native crash log: {_NATIVE_LOG}")

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

# Capture Qt diagnostics with a Python stack. Qt's stock message only says
# "Could not parse stylesheet of object QPushButton(...)" and omits the caller.
# This handler makes the next occurrence actionable while preserving normal Qt
# warning behavior. It also throttles identical stylesheet warnings so a bad
# repaint loop cannot flood the log or materially degrade the UI thread.
try:
    from PyQt6.QtCore import qInstallMessageHandler
    _qt_prev_handler = None
    _qt_style_seen = {}

    def _groovebox_qt_message_handler(msg_type, context, message):
        text = str(message)
        is_style = ("stylesheet" in text.lower() and "parse" in text.lower())
        if is_style:
            key = text
            count = _qt_style_seen.get(key, 0) + 1
            _qt_style_seen[key] = count
            if count <= 5 or count in (10, 25, 50, 100):
                print(f"[QtStyleWarning #{count}] {text}", file=sys.stderr)
                print("[QtStyleWarning] Python stack at warning:", file=sys.stderr)
                traceback.print_stack(file=sys.stderr)
            if count == 6:
                print("[QtStyleWarning] suppressing duplicate stack dumps; counts continue", file=sys.stderr)
            _write_latest("qt-stylesheet-warning", text)
        else:
            print(f"[Qt] {text}", file=sys.stderr)

    _qt_prev_handler = qInstallMessageHandler(_groovebox_qt_message_handler)
except Exception as _qt_handler_exc:
    print(f"[CrashLog] Qt message handler unavailable: {_qt_handler_exc}", file=sys.stderr)

from groovebox import MathematiciansGrooveboxApp, QApplication

if __name__ == "__main__":
    _exit_code = 1
    try:
        print("[Startup] creating QApplication")
        app = QApplication(sys.argv)
        if sys.platform.startswith("win"):
            try:
                app.setStyle("Fusion")
                print("[Startup] Windows Qt style: Fusion")
            except Exception as exc:
                print(f"[Startup] Fusion style unavailable: {exc}")
        print("[Startup] constructing main window")
        player = MathematiciansGrooveboxApp()
        print("[Startup] main window constructed")
        player.show()
        print("[Startup] player.show() returned; entering event loop")
        _exit_code = int(app.exec())
        print(f"[CrashLog] Qt event loop returned {_exit_code}")
        if _exit_code == 0:
            _write_latest("clean-exit", "Qt event loop returned 0")
        else:
            _write_latest("qt-nonzero-exit", str(_exit_code))
    except BaseException as exc:
        _write_latest("main-thread-exception", repr(exc))
        print("\n[CrashLog] MAIN-THREAD FAILURE", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        _exit_code = 1
    finally:
        try: _session_fp.flush()
        except Exception: pass
        try: _native_fp.flush()
        except Exception: pass
    raise SystemExit(_exit_code)
