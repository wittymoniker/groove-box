#!/usr/bin/env python3
"""Required-sCode entry point for Mathematician's Groovebox appliance build."""
import sys, subprocess, os, time, traceback, threading, faulthandler
from pathlib import Path

# A spawned predictive helper must dispatch before provisioning, WebEngine,
# codec checks or QApplication construction, especially in PyInstaller builds.
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

# GROOVEBOX_FROZEN_HELPER_DISPATCH_20261031: in the packaged executable, helper
# processes (device probe, exported games) re-enter this binary with a dispatch
# flag. Handle that before any GUI/provisioning/appliance code so a helper never
# starts a second Groovebox window.
if len(sys.argv) > 2 and sys.argv[1] in ("--groovebox-helper", "--groovebox-run-script"):
    from groovebox_subprocess import dispatch as _gb_dispatch
    _gb_dispatch(sys.argv)

# WINDOWS_QT_WARNING_HARDENING_20260913: Qt warnings (including a malformed QSS
# warning) are diagnostic, not a reason for the application to abort. Some
# developer/CI shells export QT_FATAL_WARNINGS=1; do not inherit that into a
# normal Groovebox desktop launch. Clear it before importing PyQt/Groovebox.
os.environ.pop("QT_FATAL_WARNINGS", None)

# GROOVEBOX_COMPAT_SETTINGS_20261102: saved Compatibility settings -> environment, before anything else reads it.
try:
    import compat_settings as _compat_settings
    _compat_settings.apply_env()
except Exception:
    pass

# GROOVEBOX_THREAD_BUDGET_20261102: cap math-library threads before NumPy is imported.
try:
    import thread_budget as _thread_budget
    _thread_budget.apply()
except Exception:
    pass

# GROOVEBOX_APPLIANCE_TUNING_20261102: on the standalone OS the app owns the machine -
# performance CPU governor and raised priority, before any worker thread is started.
try:
    import appliance_tuning as _appliance_tuning
    _appliance_tuning.apply()
except Exception:
    pass


# GROOVEBOX_R23R_RESILIENT_STDIO_20261031: on sOS, stdout/stderr are redirected
# to log files on RAM filesystems or to the console. If that target is full,
# hung up or closed, print() raises OSError (EIO/ENOSPC/EPIPE) from whatever
# code path happened to log - a Qt slot, an audio worker, the excepthook itself.
# Diagnostics must never be able to crash the application, so failed writes are
# dropped (and counted) instead of propagating.
class _ResilientStream:
    def __init__(self, stream):
        self._stream = stream
        self.dropped_writes = 0

    def write(self, data):
        try:
            return self._stream.write(data)
        except (OSError, ValueError):
            self.dropped_writes += 1
            return len(data) if isinstance(data, str) else 0

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        try:
            self._stream.flush()
        except (OSError, ValueError):
            self.dropped_writes += 1

    def __getattr__(self, name):
        return getattr(self._stream, name)


for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and not isinstance(_stream, _ResilientStream):
        setattr(sys, _stream_name, _ResilientStream(_stream))

# V3 runtime: fractal package + seeded video assembly rules
try:
    import groovebox_v3_runtime  # noqa: F401
except Exception:
    pass

# GROOVEBOX_V35_22ZN_WEBENGINE_NONROOT_GUARD_20260924
# The outer appliance launcher already drops to the dedicated ``groovebox``
# account.  Keep a second guard here because stale/direct wrappers can otherwise
# reach QtWebEngine as uid 0; Chromium then aborts its zygote and tears worker
# thread-local state down noisily.  Never disable Chromium's sandbox to mask it.
def _reexec_appliance_as_groovebox_if_root():
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    if os.environ.get("GROOVEBOX_APPLIANCE") != "1" and os.environ.get("GROOVEBOX_USER_SESSION") != "1":
        return
    if os.environ.get("GROOVEBOX_ROOT_REEXEC_GUARD") == "1":
        raise SystemExit("Groovebox appliance refused recursive root launch; dedicated groovebox user is required")
    import pwd
    try:
        pw = pwd.getpwnam("groovebox")
    except KeyError:
        raise SystemExit("Groovebox appliance cannot start QtWebEngine as root and user 'groovebox' is missing")
    runuser = "/usr/sbin/runuser"
    if not os.path.exists(runuser):
        raise SystemExit("Groovebox appliance cannot drop root: /usr/sbin/runuser is missing")
    env = dict(os.environ)
    env.update({
        "GROOVEBOX_ROOT_REEXEC_GUARD": "1",
        "GROOVEBOX_USER_SESSION": "1",
        "HOME": pw.pw_dir, "USER": "groovebox", "LOGNAME": "groovebox",
        "XDG_RUNTIME_DIR": env.get("XDG_RUNTIME_DIR") or f"/run/user/{pw.pw_uid}",
    })
    argv = [runuser, "-u", "groovebox", "--", "/usr/bin/env"]
    argv += [f"{k}={v}" for k, v in env.items()]
    argv += [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    os.execv(runuser, argv)

_reexec_appliance_as_groovebox_if_root()

def _ensure_qt_webengine_runtime():
    """Check required source deps; optional WebEngine is never a launch gate."""
    import subprocess
    if getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None):
        return
    root = Path(__file__).absolute().parent
    env = os.environ.copy()
    dirty = any(name in env for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONPYCACHEPREFIX"))
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONPYCACHEPREFIX"):
        env.pop(name, None)
    try:
        fields = {}
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key.strip()] = value.strip().strip("\"'")
        fedora = fields.get("ID") == "fedora" or "fedora" in fields.get("ID_LIKE", "").split()
    except OSError:
        fedora = False
    if fedora:
        env["PYTHONNOUSERSITE"] = "1"
        dirty = dirty or not sys.flags.no_user_site
    if dirty and env.get("GROOVEBOX_RUNTIME_CLEAN_REEXEC") != "1":
        env["GROOVEBOX_RUNTIME_CLEAN_REEXEC"] = "1"
        os.execve(sys.executable, [sys.executable, str(Path(__file__).absolute()), *sys.argv[1:]], env)
    verified = os.environ.get("GROOVEBOX_RUNTIME_VERIFIED_PYTHON")
    if verified and os.path.abspath(verified) == os.path.abspath(sys.executable):
        return
    from scripts.runtime_dependencies import REQUIRED
    modules = [module for module, _package in REQUIRED]
    try:
        probe = subprocess.run(
            [sys.executable, "-c", "import importlib; "
             "[importlib.import_module(m) for m in " + repr(modules) + "]"],
            cwd=str(root), env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True, timeout=45,
        )
        if probe.returncode == 0:
            return
        print("[Runtime] required import probe failed:\n" + (probe.stderr or "")[-4000:], file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[Runtime] required import probe failed: {exc}", file=sys.stderr)
    if os.environ.get("GROOVEBOX_APPLIANCE") == "1":
        raise SystemExit("Preinstalled appliance Python runtime is incomplete; repair the ISO/runtime rather than installing desktop packages at boot.")
    if os.environ.get("GROOVEBOX_RUNTIME_DEPS_REEXEC") == "1":
        raise SystemExit("Required runtime is still unavailable after repair; run the platform dependency installer.")
    checker = root / "scripts" / "ensure_runtime_dependencies.py"
    result = subprocess.run([sys.executable, str(checker)], cwd=str(root), env=env,
                            text=True, stdout=subprocess.PIPE)
    if result.returncode:
        raise SystemExit(f"Required runtime provisioning failed with exit {result.returncode}")
    target = result.stdout.strip()
    if not target or not Path(target).is_file():
        raise SystemExit("Dependency checker did not return a ready Python interpreter")
    env["GROOVEBOX_RUNTIME_DEPS_REEXEC"] = "1"
    env["GROOVEBOX_RUNTIME_VERIFIED_PYTHON"] = target
    os.execve(target, [target, str(Path(__file__).absolute()), *sys.argv[1:]], env)


_ensure_qt_webengine_runtime()

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
        # GROOVEBOX_FROZEN_FFMPEG_PROVISION_20261030: sys.executable is the
        # Groovebox binary in a PyInstaller build. Re-running it as a script
        # would relaunch the GUI instead of provisioning the local codec pair,
        # so call the provisioner in-process when frozen.
        if getattr(sys, "frozen", False):
            try:
                from scripts.provision_first_launch import main as _provision_main
                _provision_main()
            except Exception as exc:
                print(f"[Provision] in-process codec provisioning failed: {exc}", file=sys.stderr)
        else:
            subprocess.run([sys.executable, str(provision)], cwd=str(provision.parent.parent), check=False)
        return require_local_pair()

_LOCAL_FFMPEG = _require_local_ffmpeg()

def _provision_native_scode_stage0():
    """Repair a missing/incompatible stage-0 before the required-sCode gate.

    Every supported desktop now ships a prebuilt seed. Source checkouts and
    damaged/unpacked builds can still rebuild from the bundled public-domain C
    bootstrap when zig or a host compiler is available. This runs before the
    Qt import so macOS/Windows first launch is not blocked by a seed that was
    never staged.
    """
    try:
        from platform_runtime import find_scode_stage0, stage0_binary_matches_host
        root = Path(__file__).resolve().parent
        stage0 = find_scode_stage0(root)
        if stage0 is not None and stage0_binary_matches_host(stage0):
            return stage0
        from scripts.ensure_native_scode_stage0 import ensure as _ensure_stage0
        rc = int(_ensure_stage0() or 0)
        if rc != 0:
            print(f"[sCode] stage-0 auto-provision failed rc={rc}", file=sys.stderr)
            return None
        stage0 = find_scode_stage0(root)
        print(f"[sCode] stage-0 auto-provisioned: {stage0}")
        return stage0
    except Exception as exc:
        print(f"[sCode] stage-0 auto-provision unavailable: {exc}", file=sys.stderr)
        return None

_provision_native_scode_stage0()

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
    _qt_paint_seen = {}
    _qt_paint_dumping = threading.local()

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
        elif ("QPainter::" in text or "QBackingStore::" in text):
            # Record the drawing call site while Qt is still emitting the
            # warning. Bound keys and dumps so repeated paint faults cannot
            # turn diagnosis into an event-loop stall or fill the log disk.
            key = text[:240]
            if key not in _qt_paint_seen and len(_qt_paint_seen) >= 32:
                return
            count = _qt_paint_seen.get(key, 0) + 1
            _qt_paint_seen[key] = count
            if count <= 2:
                print(f"[QtPaintWarning #{count}] {text}", file=sys.stderr)
                if not getattr(_qt_paint_dumping, "active", False):
                    _qt_paint_dumping.active = True
                    try:
                        traceback.print_stack(limit=24, file=sys.stderr)
                    finally:
                        _qt_paint_dumping.active = False
                _write_latest("qt-paint-warning", text)
            elif count in (10, 100, 1000):
                print(f"[QtPaintWarning #{count}] {text}", file=sys.stderr)
        else:
            print(f"[Qt] {text}", file=sys.stderr)

    _qt_prev_handler = qInstallMessageHandler(_groovebox_qt_message_handler)
except Exception as _qt_handler_exc:
    print(f"[CrashLog] Qt message handler unavailable: {_qt_handler_exc}", file=sys.stderr)

# GROOVEBOX_R28_4_3_STARTUP_SELECTOR_RUNNER_20261017
from groovebox import MathematiciansGrooveboxApp, QApplication, launch_startup_mode_selector

if __name__ == "__main__":
    _exit_code = 1
    try:
        print("[Startup] creating QApplication")
        # WEBENGINE_GL_SHARE_2026: QtWebEngine (used by the Performance "Web
        # Browser" tab) requires AA_ShareOpenGLContexts set before the very
        # first QApplication/QGuiApplication instance is created, or it
        # raises ImportError the first time it's imported later. Setting it
        # here is a no-op if WebEngine is never used.
        try:
            from PyQt6.QtCore import Qt as _Qt, QCoreApplication as _QCoreApplication
            _QCoreApplication.setAttribute(_Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
        except Exception:
            pass
        app = QApplication(sys.argv)
        # R28.4.50-HF14: let PipeWire/Wayland and Qt Multimedia finish session
        # initialization before enumerating endpoints. This is diagnostic-only
        # and bounded; it must never block window construction or audio rendering.
        try:
            from scripts.media_runtime_bootstrap import schedule as _schedule_media_bootstrap
            _schedule_media_bootstrap(app)
        except Exception as _media_bootstrap_exc:
            print(f"[MediaBootstrap] could not schedule startup probe: {_media_bootstrap_exc}", file=sys.stderr)
        if sys.platform.startswith("win"):
            try:
                app.setStyle("Fusion")
                print("[Startup] Windows Qt style: Fusion")
            except Exception as exc:
                print(f"[Startup] Fusion style unavailable: {exc}")
        print("[Startup] constructing main window")
        player = MathematiciansGrooveboxApp()
        print("[Startup] main window constructed")
        _mcc_path = None
        try:
            from mcc_filetype import project_argument, register_filetype
            # Register the direct script entry so existing desktop associations
            # remain stable, while both entry paths share the selector below.
            register_filetype(str(Path(__file__).resolve().with_name("groovebox.py")))
            _mcc_path = project_argument(sys.argv[1:])
        except Exception as _mcc_exc:
            print(f"[MCC] file association startup: {_mcc_exc}")
        _startup_choice = launch_startup_mode_selector(
            player, app,
            project_path=_mcc_path,
            skip=("--skip-startup-launcher" in sys.argv[1:]),
        )
        print(f"[Startup] selector complete ({_startup_choice}); entering event loop")
        if "--restore-windows" in sys.argv[1:]:
            try:
                player._restore_windows_after_crash()
            except Exception as exc:
                print(f"[relaunch] window restore skipped: {exc}")
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
        # QT_TEARDOWN_20261103: background appliance/nearby/optimizer threads keep
        # Python objects alive while PyQt is destroying its C++ side; a normal
        # interpreter exit then faults inside sip_api_get_address.  closeEvent
        # already stopped every Qt timer/worker, so flush and leave through the
        # OS instead of re-entering the broken interpreter teardown.
        try: sys.stdout.flush()
        except Exception: pass
        try: sys.stderr.flush()
        except Exception: pass
        os._exit(int(_exit_code))


# GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103: no dialog may block other windows.
try:
    import nonmodal_dialogs as _gb_nonmodal
    _gb_nonmodal.install()
except Exception:
    pass
