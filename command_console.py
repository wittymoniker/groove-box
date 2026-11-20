"""command_console.py — GROOVEBOX_R32_COMMAND_CONSOLE_20261113

Lightweight in-app console for nerds and field fixes:
  * type commands without restarting the whole appliance
  * inspect memory / swap / governor / UI scale
  * force trim, rebuild step page, reload modules that are safe to reload
  * run a one-liner under a restricted namespace (app, mm, rg helpers)

Open: Ctrl+Shift+`  or  Actions / console  or  python -c "import command_console; command_console.open_window(app)"
"""
from __future__ import annotations

import os
import traceback
from typing import Any, Callable, Dict, Optional

try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QTextCursor
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLineEdit,
        QPushButton, QLabel, QApplication,
    )
except Exception:  # headless
    QWidget = object  # type: ignore


_COMMANDS: Dict[str, Callable[..., str]] = {}


def command(name: str, help: str = "", slow: bool = False):
    def deco(fn):
        fn._help = help
        fn._slow = bool(slow)   # R123: slow commands run off the GUI thread
        _COMMANDS[name] = fn
        return fn
    return deco


@command("help", "list commands")
def _cmd_help(app=None, **_k):
    lines = ["commands:"]
    for k in sorted(_COMMANDS):
        h = getattr(_COMMANDS[k], "_help", "")
        lines.append(f"  {k:16s} {h}")
    lines.append("  :<python>         eval in a small sandbox (app, mm, rg)")
    return "\n".join(lines)


@command("mem", "RSS / soft / hard / last trim")
def _cmd_mem(app=None, **_k):
    try:
        import resource_governor as rg
        st = rg.status()
        return (
            f"rss={st.get('rss_mb')} MiB  soft={st.get('soft_mb')}  hard={st.get('hard_mb')}  "
            f"trims={st.get('trims')}  running={st.get('running')}\nlast={st.get('last')}"
        )
    except Exception as exc:
        return f"mem error: {exc}"


@command("swap", "app SSD swap + OS swap")
def _cmd_swap(app=None, **_k):
    try:
        import memory_manager as mm
        st = mm.manager().status()
        return (
            f"SSD swap {mm.fmt_bytes(st.get('swap_used', 0))}/{mm.fmt_bytes(st.get('swap_capacity', 0))}  "
            f"root={st.get('swap_root')}\n"
            f"OS swap  {mm.fmt_bytes(st.get('os_swap_used', 0))}/{mm.fmt_bytes(st.get('os_swap_total', 0))}\n"
            f"RAM free {mm.fmt_bytes(st.get('ram_avail', 0))} / {mm.fmt_bytes(st.get('ram_total', 0))}  "
            f"tracked {mm.fmt_bytes(st.get('tracked', 0))} budget {mm.fmt_bytes(st.get('budget', 0))}"
        )
    except Exception as exc:
        return f"swap error: {exc}"


@command("trim", "force resource_governor.trim(hard)")
def _cmd_trim(app=None, hard: str = "1", **kw):
    import resource_governor as rg
    args = kw.get("_args") or []
    if args and hard == "1":
        hard = str(args[0])
    return str(rg.trim(hard=str(hard).lower() not in ("0", "false", "no", "soft")))


@command("scale", "show effective UI / window scale")
def _cmd_scale(app=None, **_k):
    import compat_settings as cs
    s = cs.load()
    return (
        f"ui_scale saved={s.get('ui_scale')} effective={cs.effective_ui_scale(s)}%  "
        f"window_scale={s.get('window_scale')}%\n"
        f"QT_SCALE_FACTOR={os.environ.get('QT_SCALE_FACTOR', '(unset)')}"
    )


@command("steps", "rebuild current sequence step page")
def _cmd_steps(app=None, **_k):
    if app is None:
        return "no app"
    n = app._seq_pattern_length() if hasattr(app, "_seq_pattern_length") else 16
    app.rebuild_sequencer_steps(n)
    lo = getattr(app, "_seq_view_start", 0)
    hi = getattr(app, "_seq_view_end", lo)
    return f"rebuilt page steps {lo + 1}–{hi} of {n} (paged={getattr(app, '_seq_buttons_paged', False)})"


@command("pads", "count on-page pads")
def _cmd_pads(app=None, **_k):
    if app is None:
        return "no app"
    live = list(app._live_step_buttons()) if hasattr(app, "_live_step_buttons") else []
    return f"on-page pads={len(live)}  list_len={len(getattr(app, 'seq_step_buttons', []) or [])}"


@command("fit", "refit startup-like geometry helpers on focused window")
def _cmd_fit(app=None, **_k):
    import compat_settings as cs
    w = QApplication.activeWindow()
    if w is None:
        return "no active window"
    cs.fit_dialog_to_screen(w)
    return f"fit applied to {w.windowTitle()!r}"


@command("boot", "open the boot / fix switcher")
def _cmd_boot(app=None, **_k):
    import boot_switcher
    boot_switcher.open_window(app)
    return "boot switcher opened"


@command("party", "party on|off|feel=calm|classic|rave|status")
def _cmd_party(app=None, **kw):
    try:
        import party_overlay as po
    except Exception as exc:
        return f"party_overlay: {exc}"
    args = kw.get("_args") or []
    feel = kw.get("feel")
    if feel:
        return f"feel={po.set_feel(feel)}  snapshot={po.snapshot()}"
    if args:
        a = str(args[0]).lower()
        if a in ("on", "1", "true"):
            try:
                import compat_settings as cs
                cs.update(party_mode=True)
            except Exception:
                pass
            if app is not None and hasattr(app, "_apply_party_mode"):
                app._apply_party_mode()
            elif hasattr(po, "refresh"):
                po.refresh(app)
            return f"party on  {po.snapshot()}"
        if a in ("off", "0", "false"):
            try:
                import compat_settings as cs
                cs.update(party_mode=False)
            except Exception:
                pass
            if hasattr(po, "refresh"):
                po.refresh(app)
            return f"party off  {po.snapshot()}"
        if a in ("calm", "classic", "rave"):
            return f"feel={po.set_feel(a)}  {po.snapshot()}"
    return str(po.snapshot())


@command("mgr", "mgr info|types — RAW format")
def _cmd_mgr(app=None, **kw):
    import mgr_format as mgr
    args = kw.get("_args") or []
    if args and args[0] == "types":
        return "\n".join(f"{k}={v}" for k, v in sorted(mgr.TYPE.items()))
    return f"magic={mgr.MAGIC!r} version={mgr.VERSION} types={len(mgr.TYPE)}"

@command("hw", "list hardware sources")
def _cmd_hw(app=None, **kw):
    import hardware_source as hs
    import sensor_bus  # noqa: F401 — register defaults
    import rc_car  # noqa: F401
    enum = hs.enumerate_all()
    lines = [f"{k}: {len(v)} device(s)" for k, v in sorted(enum.items())]
    return "\n".join(lines) or "(none)"

@command("sensors", "snapshot sensor bus")
def _cmd_sensors(app=None, **kw):
    import sensor_bus
    import hardware_source as hs
    out = []
    for name in hs.list_sources():
        src = hs._SOURCES.get(name)
        if src is None:
            continue
        try:
            r = src.read(4)
            out.append(f"{name}: {r}")
        except Exception as exc:
            out.append(f"{name}: err {exc}")
    return "\n".join(out) or "(no readings)"


@command("panels", "canonical panel coverage report / project")
def _cmd_panels(app=None, **kw):
    if app is None:
        return "no app"
    args = kw.get("_args") or []
    if args and args[0] in ("project", "apply", "write"):
        if hasattr(app, "_canonical_project_main_panels"):
            return str(app._canonical_project_main_panels(write_ui=True))
        return "missing _canonical_project_main_panels"
    if hasattr(app, "_canonical_panel_coverage_report"):
        return str(app._canonical_panel_coverage_report())
    try:
        import canonical_panel_bridge as cpb
        return str(cpb.coverage_report(app))
    except Exception as exc:
        return str(exc)



@command("canonicals", "show canonical engine states and effective levels")
def _cmd_canonicals(app=None, **_kw):
    if app is None:
        return "no app"
    rows = []
    for key, button_name in (("seeded", "btn_seeded_randomize"), ("randomizer", "btn_local_randomize"),
                             ("phase_lock", "btn_local_phase_lock"), ("euclidean", "btn_idealize_rhythm"),
                             ("goava", "btn_goava"), ("fractal_seed", "btn_fractal_seed_mode")):
        button = getattr(app, button_name, None)
        active = bool(button.isChecked()) if button is not None and hasattr(button, "isChecked") else False
        level = (getattr(app, "canonical_engine_levels", {}) or {}).get(key, 1.0)
        try:
            effective = app._canonical_level(key)
        except Exception:
            effective = level
        rows.append(f"{key:12s} active={int(active)} level={float(level):.3f} effective={float(effective):.3f}")
    return "\n".join(rows)


@command("runtime", "show prepared Program Builder language runtimes")
def _cmd_runtime(app=None, **_kw):
    try:
        import program_builder
        return "\n".join(f"{name:12s} {'READY' if ready else 'MISSING'}" for name, ready in program_builder.toolchains().items())
    except Exception as exc:
        return f"runtime diagnostics failed: {exc}"


@command("windows", "list visible top-level Qt windows")
def _cmd_windows(app=None, **_kw):
    try:
        rows = []
        for window in QApplication.topLevelWidgets():
            try:
                if window.isVisible():
                    rows.append(f"{window.windowTitle() or type(window).__name__} · {window.width()}×{window.height()}")
            except Exception:
                pass
        return "\n".join(sorted(rows)) or "(no visible windows)"
    except Exception as exc:
        return f"window enumeration failed: {exc}"


@command("status", "one-screen project, audio, canonical, and workload summary")
def _cmd_status(app=None, **_kw):
    if app is None:
        return "no app"
    try: tempo = float(app.spin_bpm.value())
    except Exception: tempo = float(getattr(app, "bpm", 0.0) or 0.0)
    rows = len(getattr(app, "master_playlist_data", []) or [])
    voices = len(getattr(app, "instrument_names_48", []) or [])
    path = getattr(app, "_current_project_path", None) or "(unsaved project)"
    active = []
    for key, attr in (("RAND", "btn_local_randomize"), ("LOCK", "btn_local_phase_lock"),
                      ("GOAVA", "btn_goava"), ("FRACTAL", "btn_fractal_seed_mode")):
        b = getattr(app, attr, None)
        if b is not None and hasattr(b, "isChecked") and b.isChecked(): active.append(key)
    return f"Project: {path}\nTempo: {tempo:.2f} BPM · playlist rows: {rows} · instruments: {voices}\nActive: {', '.join(active) or '(none)'}"


@command("project", "show current project path and save/recovery state")
def _cmd_project(app=None, **_kw):
    if app is None: return "no app"
    return (f"path={getattr(app, '_current_project_path', None) or '(unsaved)'}\n"
            f"recovered_needs_save={bool(getattr(app, '_recovered_needs_save', False))}\n"
            f"dirty={bool(getattr(app, '_project_dirty', False) or getattr(app, '_project_modified', False))}")


@command("seed", "show exact seed text and numeric interpretation")
def _cmd_seed(app=None, **_kw):
    if app is None: return "no app"
    try: numeric = app.get_numeric_seed()
    except Exception as exc: numeric = f"unavailable ({exc})"
    try: source = str(app._seed_text())
    except Exception: source = str(numeric)
    import hashlib
    digest = hashlib.sha256(source.encode("utf-8", "replace")).hexdigest()[:20]
    preview = source if len(source) <= 240 else source[:237] + "..."
    return f"numeric={numeric}\ntext={preview}\nsha256[:20]={digest}"


@command("goava", "show GOAVA activation, three frequencies, and amplitudes")
def _cmd_goava(app=None, **_kw):
    if app is None: return "no app"
    try: settings = app._goava_voice_settings_normalized()
    except Exception: settings = getattr(app, "goava_voice_settings", {}) or {}
    events = getattr(app, "goava_note_events", []) or []
    return (f"active={bool(getattr(app, 'goava_active', False))} · events={len(events)}\n"
            f"spectrum_offset={settings.get('spectrum_offset')}\n"
            f"amplitudes={settings.get('amplitudes')}\n"
            f"sample_event={events[0] if events else '(no event cached)'}")


@command("fractal", "show Fractal Seed settings, root frequency, and plan cache")
def _cmd_fractal(app=None, **_kw):
    if app is None: return "no app"
    try: settings = app._fractal_seed_settings_normalized()
    except Exception: settings = getattr(app, "fractal_seed_settings", {}) or {}
    cache = getattr(app, "_fractal_seed_plan_cache", None)
    plan = cache.get("plan", {}) if isinstance(cache, dict) else {}
    evaluation = plan.get("evaluation", {}) if isinstance(plan, dict) else {}
    button = getattr(app, "btn_fractal_seed_mode", None)
    active = bool(button.isChecked()) if button is not None and hasattr(button, "isChecked") else False
    return f"active={active}\nsettings={settings}\nplan_status={evaluation.get('status', 'not cached')} · events={len(plan.get('events', [])) if isinstance(plan, dict) else 0}"


@command("audio", "show selected audio endpoint and playback state fields")
def _cmd_audio(app=None, **_kw):
    if app is None: return "no app"
    names = ("audio_output_device", "selected_audio_output", "audio_input_device", "selected_audio_input",
             "audio_device_name", "audio_backend_name", "audio_playing", "is_playing", "audio_running")
    rows = [f"{name}={getattr(app, name)!r}" for name in names if hasattr(app, name)]
    return "\n".join(rows) if rows else "No direct audio endpoint fields are exposed on the main window; use Performance → Hardware for live device enumeration."


@command("exports", "show export queue active and pending job counts")
def _cmd_exports(app=None, **_kw):
    if app is None: return "no app"
    try:
        scheduler = app._export_scheduler()
        return f"active={scheduler.active_count()} · pending={scheduler.pending_count()} · parallel={getattr(scheduler, 'max_parallel', 'auto')}"
    except Exception as exc:
        return f"export scheduler unavailable: {exc}"


@command("threads", "worker pools, lanes, one-shot jobs and live thread count")
def _cmd_threads(app=None, **_kw):
    try:
        import threading
        import thread_budget as tb
        lines = [f"usable_cores={tb.usable_cores()}  lane_workers={tb.lane_workers()}  bulk={tb.bulk_workers()}  "
                 f"interactive={tb.interactive_workers()}  engine={tb.engine_workers()}",
                 f"scheduler_budget={tb.scheduler_budget()}",
                 f"oneshot={tb.oneshot_report()}"]
        try:
            rep = tb.lane_report(limit=12) or {}
            for row in (rep.get("lanes") or []) if isinstance(rep, dict) else rep:
                lines.append(f"  lane {row}")
            if isinstance(rep, dict):
                lines.append(f"  running={rep.get('running')}  forecast={rep.get('forecast')}")
        except Exception:
            pass
        names = {}
        for t in threading.enumerate():
            fam = t.name.split("-")[0] if t.name.startswith("groovebox") else t.name.rstrip("0123456789-_ ")
            names[fam] = names.get(fam, 0) + 1
        lines.append(f"live threads={threading.active_count()}: " + ", ".join(f"{k}×{v}" for k, v in sorted(names.items(), key=lambda kv: -kv[1])[:20]))
        return "\n".join(lines)
    except Exception as exc:
        return f"thread budget unavailable: {exc}"


@command("abi", "native C++ runtime selection (Julia / Mesa / Z3 CXXABI)")
def _cmd_abi(app=None, **_kw):
    try:
        import json
        import native_abi_guard as g
        rep = g.report()
        rep["loaded"] = g.loaded_runtimes()
        return json.dumps(rep, indent=1, default=str)
    except Exception as exc:
        return f"abi guard unavailable: {exc}"


@command("toolchains", "compilers/runtimes for Program Builder; Go GOROOT + telemetry state", slow=True)
def _cmd_toolchains(app=None, **_kw):
    try:
        import json
        import program_builder, toolchain_env
        return json.dumps({"available": program_builder.toolchains(), "env": toolchain_env.describe()}, indent=1, default=str)
    except Exception as exc:
        return f"toolchains unavailable: {exc}"


@command("env", "low-level environment that shapes rendering, audio and threads")
def _cmd_env(app=None, **_kw):
    keys = ("QT_QPA_PLATFORM", "QT_SCALE_FACTOR", "WAYLAND_DISPLAY", "DISPLAY", "XDG_SESSION_TYPE", "PULSE_SERVER",
            "PIPEWIRE_LATENCY", "LD_PRELOAD", "LD_LIBRARY_PATH", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
            "PYTHON_JULIACALL_LIB", "JULIA_NUM_THREADS", "JULIA_DEPOT_PATH", "GROOVEBOX_DATA_DIR", "LIBGL_ALWAYS_SOFTWARE",
            "MESA_LOADER_DRIVER_OVERRIDE", "GOROOT", "GOTOOLCHAIN")
    return "\n".join(f"{k}={os.environ.get(k, '')}" for k in keys)


@command("doctor", "self-diagnostics: ABI, toolchains, Task Bar entry points, Qt platform", slow=True)
def _cmd_doctor(app=None, **_kw):
    out = []
    def chk(label, fn):
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"{type(exc).__name__}: {exc}"
        out.append(f"[{'ok' if ok else '!!'}] {label}: {msg}")
    def _abi():
        import native_abi_guard as g
        r = g.report(); loaded = g.loaded_runtimes()
        libs = [p for p in loaded if "libstdc++" in p]
        return len(set(os.path.realpath(p) for p in libs)) <= 1, f"libstdc++ mapped={libs or 'none yet'}"
    def _go():
        import toolchain_env, shutil
        if not shutil.which("go"):
            return True, "Go not installed (optional)"
        return toolchain_env.go_env() is not None, f"GOROOT={toolchain_env.go_root()}"
    def _julia():
        import shutil
        j = shutil.which("julia")
        return True, (j or "Julia not on PATH (optional; Program Builder .jl disabled)")
    def _taskbar():
        import taskbar_launch
        bad = [f"{k}: {why}" for k, (ok, why) in taskbar_launch.audit().items() if not ok]
        return not bad, "all entry points resolve" if not bad else "; ".join(bad)
    def _qpa():
        try:
            from PyQt6.QtGui import QGuiApplication
            return True, QGuiApplication.platformName() or "(no app)"
        except Exception as exc:
            return False, str(exc)
    chk("C++ runtime", _abi); chk("Go toolchain", _go); chk("Julia", _julia)
    chk("Task Bar launchers", _taskbar); chk("Qt platform", _qpa)
    try:
        import monitor_center
        for name, ok, detail in monitor_center.engine_self_tests(force=True):
            out.append(f"[{'ok' if ok else '!!'}] {name}: {detail}")
    except Exception as exc:
        out.append(f"[!!] engine self-tests: {exc}")
    return "\n".join(out)


@command("signals", "any-signal → any-context: kinds, converters, contexts, recent sends; 'signals test' runs self-tests")
def _cmd_signals(app=None, args="", **_kw):
    import carrier_bridge as cb
    a = str(args or "").strip().lower()
    if a.startswith("test"):
        import monitor_center
        return "\n".join(f"[{'ok' if ok else '!!'}] {n}: {d}" for n, ok, d in monitor_center.engine_self_tests(force=True))
    d = cb.describe()
    lines = ["rule: " + d["rule"], "kinds: " + ", ".join(d["kinds"]), "converters:"]
    lines += [f"  {k}  ({v})" for k, v in d["converters"].items()]
    lines.append("contexts:")
    lines += [f"  {k}: {v}" for k, v in d["contexts"].items()]
    try:
        ok, why = cb.seed_only(app) if app is not None else (False, "no app")
        lines.append(f"guaranteed profile active: {'yes' if ok else 'no'} ({why})")
    except Exception:
        pass
    if d["recent"]:
        lines.append("recent:")
        lines += ["  " + str(h)[:160] for h in d["recent"]]
    return "\n".join(lines)


@command("ui", "show active window geometry and screen work area")
def _cmd_ui(app=None, **_kw):
    try:
        window = QApplication.activeWindow() or app
        if window is None: return "no active window"
        g = window.geometry()
        screen = window.screen() if hasattr(window, "screen") else QApplication.primaryScreen()
        ag = screen.availableGeometry() if screen is not None else None
        return (f"window={window.windowTitle()!r} geometry=({g.x()},{g.y()},{g.width()},{g.height()})\n"
                f"available={None if ag is None else (ag.x(), ag.y(), ag.width(), ag.height())}")
    except Exception as exc:
        return f"UI geometry unavailable: {exc}"


@command("caches", "show sizes of major in-memory analysis and canonical caches")
def _cmd_caches(app=None, **_kw):
    if app is None: return "no app"
    names = ("_fractal_seed_plan_cache", "_fractal_raster_cache", "_canonical_ctx_cache",
             "_analysis_cache", "_kind_cache", "_preview_cache", "_export_preview_cache")
    rows = []
    for name in names:
        value = getattr(app, name, None)
        if value is None: continue
        try: size = len(value)
        except Exception: size = "n/a"
        rows.append(f"{name}={size}")
    return "\n".join(rows) if rows else "(no tracked caches present)"


@command("focus", "raise a visible window by title substring: focus Performance")
def _cmd_focus(app=None, **kw):
    args = kw.get("_args") or []
    query = " ".join(str(x) for x in args).strip().casefold()
    if not query: return "usage: focus <window title substring>"
    try:
        matches = [w for w in QApplication.topLevelWidgets() if query in str(w.windowTitle()).casefold()]
        if not matches: return f"no window title contains {query!r}"
        window = next((w for w in matches if w.isVisible()), matches[0])
        window.show(); window.raise_(); window.activateWindow()
        return f"focused {window.windowTitle()!r}"
    except Exception as exc:
        return f"focus failed: {exc}"


@command("save", "save the current project to its existing path")
def _cmd_save(app=None, **_kw):
    if app is None: return "no app"
    path = getattr(app, "_current_project_path", None)
    if not path: return "project has no path yet; use the application's Save As action first"
    try:
        app._save_project_document(path, show_saved=True)
        return f"save requested: {path}"
    except Exception as exc:
        return f"save failed: {exc}"

def _run_line(line: str, app=None) -> str:
    line = (line or "").strip()
    if not line:
        return ""
    if line.startswith(":"):
        expr = line[1:].strip()
        ns = {"app": app, "os": os}
        try:
            import memory_manager as mm
            ns["mm"] = mm
        except Exception:
            pass
        try:
            import resource_governor as rg
            ns["rg"] = rg
        except Exception:
            pass
        try:
            return repr(eval(expr, {"__builtins__": {"len": len, "min": min, "max": max, "int": int, "float": float, "str": str, "bool": bool, "list": list, "dict": dict, "round": round}}, ns))
        except Exception:
            return traceback.format_exc()
    import shlex
    try:
        parts = shlex.split(line)
    except ValueError as exc:
        return f"parse error: {exc}"
    if not parts:
        return ""
    cmd, args = parts[0].lower(), parts[1:]
    fn = _COMMANDS.get(cmd)
    if not fn:
        return f"unknown command {cmd!r} — try help"
    kwargs: Dict[str, Any] = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            kwargs[k] = v
        else:
            kwargs.setdefault("_args", []).append(a)
    try:
        return fn(app=app, **kwargs)
    except TypeError:
        return f"usage error for {cmd}: {getattr(fn, '_help', 'check help')}"
    except Exception:
        return traceback.format_exc()


try:
    from PyQt6.QtCore import QObject, pyqtSignal

    class _ResultBridge(QObject):
        done = pyqtSignal(str, str)
except Exception:  # headless
    _ResultBridge = None


class CommandConsole(QWidget):
    HISTORY_MAX = 200

    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Groovebox · Command Console")
        self.resize(720, 420)
        try:
            import window_manager as wm
            wm.make_independent(self)
        except Exception:
            pass
        lay = QVBoxLayout(self)
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setFont(QFont("monospace", 10))
        self.out.setMaximumBlockCount(5000)   # R123: bounded scrollback
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("help · doctor · threads · abi · toolchains · env · status · :app.spin_bpm.value()   (↑/↓ history, Tab completes)")
        self.inp.returnPressed.connect(self._submit)
        self.inp.installEventFilter(self)
        self._history, self._hpos = [], 0
        self._bridge = _ResultBridge() if _ResultBridge else None
        if self._bridge is not None:
            self._bridge.done.connect(self._finish)
        row = QHBoxLayout()
        go = QPushButton("Run")
        go.clicked.connect(self._submit)
        clr = QPushButton("Clear")
        clr.clicked.connect(self.out.clear)
        row.addWidget(self.inp, 1)
        row.addWidget(go)
        row.addWidget(clr)
        lay.addWidget(QLabel("Field console — never blocks audio; slow commands run in the background. Type help."))
        lay.addWidget(self.out, 1)
        lay.addLayout(row)
        self._println(_run_line("help", app))

    def eventFilter(self, obj, ev):
        try:
            from PyQt6.QtCore import QEvent
            if obj is self.inp and ev.type() == QEvent.Type.KeyPress:
                k = ev.key()
                if k == Qt.Key.Key_Up and self._history:
                    self._hpos = max(0, self._hpos - 1); self.inp.setText(self._history[self._hpos]); return True
                if k == Qt.Key.Key_Down and self._history:
                    self._hpos = min(len(self._history), self._hpos + 1)
                    self.inp.setText(self._history[self._hpos] if self._hpos < len(self._history) else ""); return True
                if k == Qt.Key.Key_Tab:
                    t = self.inp.text().strip().lower()
                    hits = sorted(c for c in _COMMANDS if c.startswith(t))
                    if len(hits) == 1:
                        self.inp.setText(hits[0] + " ")
                    elif hits:
                        self._println("  ".join(hits))
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, ev)

    def _println(self, text: str):
        self.out.appendPlainText(text.rstrip() + "\n")
        self.out.moveCursor(QTextCursor.MoveOperation.End)

    def _submit(self):
        line = self.inp.text()
        self.inp.clear()
        if line.strip():
            if not self._history or self._history[-1] != line:
                self._history.append(line)
                del self._history[:-self.HISTORY_MAX]
            self._hpos = len(self._history)
        self._println(f"› {line}")
        name = (line.strip().split() or [""])[0].lower()
        fn = _COMMANDS.get(name)
        if fn is not None and getattr(fn, "_slow", False) and self._bridge is not None:
            self._println(f"  … {name} running in the background")
            def work(line=line):
                self._bridge.done.emit(line, _run_line(line, self.app))
            try:
                import thread_budget
                thread_budget.spawn("console-" + name, work)
            except Exception:
                import threading
                threading.Thread(target=work, name="console-" + name, daemon=True).start()
            return
        self._finish(line, _run_line(line, self.app))

    def _finish(self, line, result):
        self._println(result)
        try:
            controller = getattr(self.app, "_live_composition_controller", None)
            if controller is not None:
                controller.ingest_console_command(line, result, success=not str(result).startswith(("usage error", "unknown command", "Traceback")))
        except Exception:
            pass


def open_window(app=None):
    win = getattr(app, "_command_console", None) if app is not None else None
    if win is None:
        win = CommandConsole(app)
        if app is not None:
            try:
                app._command_console = win
            except Exception:
                pass
    win.show()
    win.raise_()
    win.activateWindow()
    return win


def install_shortcut(app, host_widget):
    """Ctrl+Shift+` opens the console."""
    try:
        sc = QShortcut(QKeySequence("Ctrl+Shift+`"), host_widget)
        sc.activated.connect(lambda: open_window(app))
        return sc
    except Exception as exc:
        print(f"[console] shortcut: {exc}")
        return None
