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
    lines.append("  !<command>        shell command (bash), output streams here · ⏹ Stop ends it")
    lines.append("  sudo <command>    the same as root (asks for the password once per 10 min)")
    lines.append("  run <file> [args] run a script: .sh with bash, .py with this console's Python")
    lines.append("  py <code>         full Python, variables kept (app, sh(), sudo(), run()) · 🐍 Python… = editor")
    lines.append("  passwd            change the password sudo asks for")
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


@command("signals", "any-signal → any-context: kinds, converters, contexts, recent sends · signals test · signals matrix · "
                    "signals route <kind> <context> · signals send <context[:arg]> <value>")
def _cmd_signals(app=None, args="", **_kw):
    import carrier_bridge as cb
    # R132.26: the dispatcher passes words as _args; `args` was never set, so `signals test` only ever printed the summary
    raw = (" ".join(str(x) for x in (_kw.get("_args") or [])) or str(args or "")).strip()
    a = raw.lower()
    if a.startswith("test"):
        import monitor_center
        return "\n".join(f"[{'ok' if ok else '!!'}] {n}: {d}" for n, ok, d in monitor_center.engine_self_tests(force=True))
    if a.startswith("matrix"):                 # R132.26: kinds × contexts, number of conversion steps
        names = list(cb._CONTEXTS)
        rows = ["kind     " + " ".join(n[:6].rjust(6) for n in names)]
        for k in cb.KINDS:
            cells = []
            for n in names:
                try:
                    cells.append(str(len(cb.route_steps(k, n))).rjust(6))
                except Exception:
                    cells.append("     ✗")
            rows.append(k.ljust(8) + " " + " ".join(cells))
        return "\n".join(rows)
    if a.startswith("route"):                  # signals route KIND CONTEXT
        parts = raw.split()
        if len(parts) < 3:
            return "usage: signals route <kind> <context>   kinds: " + ", ".join(cb.KINDS)
        try:
            return "\n".join(cb.route_steps(parts[1], parts[2])) or "direct (no conversion)"
        except Exception as exc:
            return f"no route: {exc}"
    if a.startswith("send"):                   # signals send CONTEXT[:arg] VALUE  (a number, a file path or text)
        parts = raw.split(None, 2)
        if len(parts) < 3:
            return "usage: signals send <context[:arg]> <value>   e.g. signals send bpm 0.5 · signals send lens:cellular my seed"
        val = parts[2]
        try:
            val = float(val)
        except ValueError:
            val = os.path.expanduser(val) if os.path.isfile(os.path.expanduser(val)) else val
        try:
            rec = cb.send(app, val, parts[1], source="console")
        except Exception as exc:
            return f"⚠ {type(exc).__name__}: {exc}"
        return (f"sent {rec['from']} → {rec['context']}\n  " + "\n  ".join(rec.get("route") or ["direct"]) +
                (f"\n  {rec['path']}" if rec.get("path") else "") + (f"\n  outputs {rec['outputs']}" if rec.get("outputs") else ""))
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

def shlex_split_safe(text):
    import shlex
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _run_line(line: str, app=None) -> str:
    line = (line or "").strip()
    if not line:
        return ""
    import console_shell as _cs
    low = line.lower()
    if line.startswith("!"):
        return _cs.sh(line[1:].strip())
    if low.startswith(("py ", ">>> ")) or low == "py":
        return _cs.run_python(line.split(" ", 1)[1] if " " in line else "", app)
    if low == "run" or low.startswith("run "):
        parts = shlex_split_safe(line[4:])
        return _cs.run(parts[0], *parts[1:]) if parts else "usage: run <file> [args]"
    if low.startswith("sudo "):
        return _cs.sudo(line[5:].strip())
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
        line = pyqtSignal(str)          # R132: streamed shell output
        job_done = pyqtSignal(int)
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
        self.inp.setPlaceholderText("help · !ls -l · sudo apt update · run ~/x.sh · py 2**10 · doctor · status   (↑/↓ history, Tab completes)")
        self.inp.returnPressed.connect(self._submit)
        self.inp.installEventFilter(self)
        self._history, self._hpos = [], 0
        self._bridge = _ResultBridge() if _ResultBridge else None
        if self._bridge is not None:
            self._bridge.done.connect(self._finish)
            self._bridge.line.connect(lambda t: self.out.appendPlainText(t))
            self._bridge.job_done.connect(self._job_finished)
        self._job = None
        self._sudo_hint_shown = False
        row = QHBoxLayout()
        go = QPushButton("Run")
        go.clicked.connect(lambda _checked=False: self._submit())
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setToolTip("Stop the running shell command or script (and everything it started)")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(lambda _checked=False: self._stop_job())
        py = QPushButton("🐍 Python…")
        py.setToolTip("Multi-line Python editor: Ctrl+Enter runs the whole block in this console")
        py.clicked.connect(lambda _checked=False: self._open_python_editor())
        sh_b = QPushButton("🐚 Shell…")
        sh_b.setToolTip("Multi-line bash script editor: Ctrl+Enter runs it (tick 'as administrator' for sudo)")
        sh_b.clicked.connect(lambda _checked=False: self._open_shell_editor())
        clr = QPushButton("Clear")
        clr.clicked.connect(lambda _checked=False: self.out.clear())
        row.addWidget(self.inp, 1)
        for b in (go, self.btn_stop, py, sh_b, clr):
            row.addWidget(b)
        lay.addWidget(QLabel("Field console — commands · !shell · sudo · run script · py Python. Long jobs never block audio. Type help."))
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
        if self._shell_dispatch(line.strip()):
            return
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

    # ------------------------------------------------------------ R132 shell / sudo / Python
    def _ask_password(self, prompt=None):
        from PyQt6.QtWidgets import QInputDialog, QLineEdit as _QLE
        import console_shell as cs
        if not self._sudo_hint_shown:
            self._println(cs.DEFAULT_PASSWORD_HINT); self._sudo_hint_shown = True
        text, ok = QInputDialog.getText(self, "sudo", prompt or "Password for sudo:", _QLE.EchoMode.Password)
        return text if ok else None

    def _start_job(self, argv, stdin_text=None, label=""):
        import console_shell as cs
        if self._job is not None and self._job.running():
            self._println("  a command is still running — ⏹ Stop it first"); return
        b = self._bridge
        self._job = cs.Job(argv, stdin_text,
                           on_line=(b.line.emit if b is not None else None),
                           on_done=(b.job_done.emit if b is not None else None))
        try:
            self._job.start()
        except Exception as exc:
            self._println(f"  could not start: {exc}"); self._job = None; return
        self.btn_stop.setEnabled(True)
        if label:
            self._println(f"  … {label}")

    def _job_finished(self, rc):
        self.btn_stop.setEnabled(False)
        self._println(f"  [{'done' if rc == 0 else 'exit %d' % rc}]")

    def _stop_job(self):
        if self._job is not None and self._job.running():
            self._job.stop(); self._println("  stopping…")

    def _shell_dispatch(self, line):
        """True when the line was a shell / sudo / script / Python / passwd line (handled here)."""
        import console_shell as cs
        low = line.lower()
        try:
            if line.startswith("!"):
                cmd = line[1:].strip()
                if cmd:
                    self._start_job(cs.shell_argv(cmd)[0])
                return True
            if low.startswith("sudo "):
                cmd = line[5:].strip()
                mode = cs.sudo_mode()
                pw = None
                if mode == "password":
                    pw = self._ask_password()
                    if pw is None:
                        self._println("  sudo cancelled"); return True
                argv, stdin = cs.shell_argv(cmd, privileged=True, password=pw)
                self._start_job(argv, stdin, "as root")
                return True
            if low == "run" or low.startswith("run "):
                parts = shlex_split_safe(line[4:])
                if not parts:
                    self._println("usage: run <file> [args]"); return True
                path = os.path.expanduser(parts[0])
                if path.endswith(".py"):
                    self._println(cs.run(path, *parts[1:]))
                else:
                    self._start_job(cs.script_argv(path, parts[1:]), label=os.path.basename(path))
                return True
            if low == "py" or low.startswith(("py ", ">>> ")):
                cs.namespace(self.app)["_ask_password"] = self._ask_password
                self._println(cs.run_python(line.split(" ", 1)[1] if " " in line else "", self.app))
                return True
            if low == "passwd":
                self._change_password(); return True
        except Exception as exc:
            self._println(f"  {type(exc).__name__}: {exc}"); return True
        return False

    def _change_password(self):
        from PyQt6.QtWidgets import QInputDialog, QLineEdit as _QLE
        import console_shell as cs
        old = None
        if cs.sudo_mode() == "password":
            old = self._ask_password("Current password:")
            if old is None:
                return
        new, ok = QInputDialog.getText(self, "passwd", "New password:", _QLE.EchoMode.Password)
        if not ok or not new:
            return
        again, ok = QInputDialog.getText(self, "passwd", "New password again:", _QLE.EchoMode.Password)
        if not ok or again != new:
            self._println("  passwords differ — nothing changed"); return
        b = self._bridge
        job = cs.passwd_job(new, old, on_line=(b.line.emit if b else None), on_done=(b.job_done.emit if b else None))
        if self._job is not None and self._job.running():
            self._println("  a command is still running — ⏹ Stop it first"); return
        self._job = job; job.start(); self.btn_stop.setEnabled(True)
        self._println("  changing password…")

    def _open_shell_editor(self):
        """R132.17: multi-line bash (real Linux) — runs as one script, streamed into this console; optional sudo."""
        from PyQt6.QtWidgets import (QDialog, QPlainTextEdit as _PTE, QVBoxLayout as _VL, QHBoxLayout as _HL,
                                     QPushButton as _PB, QCheckBox as _CB)
        import console_shell as cs
        d = getattr(self, "_sh_editor", None)
        if d is not None:
            d.show(); d.raise_(); d.activateWindow(); return
        d = self._sh_editor = QDialog(self); d.setWindowTitle("🐚 Shell script · runs in the Command Console"); d.resize(680, 440)
        ed = _PTE(); ed.setFont(QFont("monospace", 10))
        ed.setPlainText("# bash — every line runs in one script (set -e stops at the first error)\n"
                        "set -e\nlsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS\ndf -h /home\n")
        root = _CB("as administrator (sudo)")
        v = _VL(d); v.addWidget(ed, 1); r = _HL()

        def go():
            script = ed.toPlainText()
            try:
                pw = None
                if root.isChecked() and cs.sudo_mode() == "password":
                    pw = self._ask_password()
                    if pw is None:
                        return
                argv, stdin_text = cs.shell_argv(script, privileged=root.isChecked(), password=pw)
            except Exception as exc:
                self._println(f"  {exc}"); return
            self._println("› (shell script%s)" % (" as administrator" if root.isChecked() else ""))
            self._start_job(argv, stdin_text)
        b = _PB("▶ Run  (Ctrl+Enter)"); b.clicked.connect(lambda _checked=False: go())
        r.addWidget(root); r.addStretch(1); r.addWidget(b); v.addLayout(r)
        QShortcut(QKeySequence("Ctrl+Return"), d).activated.connect(go)
        d.show()

    def _open_python_editor(self):
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit as _PTE, QVBoxLayout as _VL, QHBoxLayout as _HL, QPushButton as _PB
        import console_shell as cs
        d = getattr(self, "_py_editor", None)
        if d is not None:
            d.show(); d.raise_(); d.activateWindow(); return
        d = self._py_editor = QDialog(self); d.setWindowTitle("🐍 Python · runs in the Command Console"); d.resize(640, 420)
        ed = _PTE(); ed.setFont(QFont("monospace", 10))
        ed.setPlainText("# Full Python. app = the Groovebox window; sh(), sudo(), run() run shell commands.\n"
                        "print(sh('uname -a'))\n")
        v = _VL(d); v.addWidget(ed, 1); r = _HL()
        def go():
            cs.namespace(self.app)["_ask_password"] = self._ask_password
            self._println("› (python block)"); self._println(cs.run_python(ed.toPlainText(), self.app, "<editor>"))
        b = _PB("▶ Run  (Ctrl+Enter)"); b.clicked.connect(lambda _checked=False: go()); r.addWidget(b)
        r.addStretch(1); v.addLayout(r)
        QShortcut(QKeySequence("Ctrl+Return"), d).activated.connect(go)
        d.show()

    def _finish(self, line, result):
        self._println(result)
        try:
            controller = getattr(self.app, "_live_composition_controller", None)
            if controller is not None:
                controller.ingest_console_command(line, result, success=not str(result).startswith(("usage error", "unknown command", "Traceback")))
        except Exception:
            pass



@command("wifi", "Wi-Fi / NetworkManager / elevation diagnostics (no shell)")
def _cmd_wifi(app=None, **_k):
    lines = []
    try:
        import network_manager_utils as nm
        lines.append(nm.elevation_diagnostics())
    except Exception as exc:
        lines.append(f"network_manager_utils: {exc}")
    try:
        import shutil, subprocess, os
        nmcli = shutil.which("nmcli")
        lines.append(f"nmcli={nmcli or 'missing'}")
        if nmcli:
            env = dict(os.environ); env["LC_ALL"] = "C"
            p = subprocess.run([nmcli, "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=6, env=env)
            lines.append((p.stdout or p.stderr or "").strip()[:800] or "(no nmcli output)")
    except Exception as exc:
        lines.append(f"nmcli status: {exc}")
    return "\n".join(lines)


@command("presence", "Edit Together presence overlay on|off|status|toggle")
def _cmd_presence(app=None, **kw):
    args = kw.get("_args") or []
    arg = (args[0] if args else kw.get("arg") or "").strip().lower()
    try:
        import edit_together_presence as etp
    except Exception as exc:
        return f"presence module unavailable: {exc}"
    if arg in ("", "status"):
        return etp.status()
    if arg in ("on", "1", "true"):
        return etp.set_enabled(app, True)
    if arg in ("off", "0", "false"):
        return etp.set_enabled(app, False)
    if arg in ("toggle", "t"):
        return etp.toggle(app)
    return "usage: presence on|off|toggle|status"


@command("taskpad", "list Task Pad launch targets and whether modules import")
def _cmd_taskpad(app=None, **_k):
    targets = [
        "script_studio", "live_player", "theremin_sensors", "instrument_mixer", "studio_3d",
        "network_hub", "net_hub", "file_studio", "runtime_tools_ui", "sos_system_settings",
        "audio_tools", "app_hub", "plugin_library", "lua_workspace", "program_builder",
        "scode_coordinator", "project_transactions", "project_tools", "experiences",
        "seed_atlas", "mod_matrix", "carrier_layers", "notify_center", "features_r99",
        "studio_extras", "session_snapshot", "edit_together_presence", "live_edit_ui",
        "command_console", "multidim_ui", "canonical_rules_panel",
    ]
    lines = ["Task Pad / related modules:"]
    for name in targets:
        try:
            m = __import__(name, fromlist=["_"])
            has = "open_window" if hasattr(m, "open_window") else (
                "open_from_app" if hasattr(m, "open_from_app") else "imported")
            lines.append(f"  OK   {name:28s} {has}")
        except Exception as exc:
            lines.append(f"  FAIL {name:28s} {type(exc).__name__}: {exc}")
    lines.append("Shell: !<command> · sudo <command> · run <script> · py <python>  (type help)")
    return "\n".join(lines)


@command("et", "Edit Together: open presence overlay + Network Live Edit path")
def _cmd_et(app=None, **_k):
    try:
        import edit_together_presence as etp
        return etp.open_from_app(app)
    except Exception as exc:
        return f"Edit Together: {exc}"



@command("accel", "predictive multilanguage accel status|warm|rank")
def _cmd_accel(app=None, **kw):
    args = kw.get("_args") or []
    arg = (args[0] if args else "status").lower()
    try:
        import predictive_accel_runtime as par
        rt = par.get_runtime()
    except Exception as exc:
        return f"accel unavailable: {exc}"
    if arg in ("status", ""):
        return rt.status_text()
    if arg == "warm":
        return par.predictive_warm_languages()
    if arg == "rank":
        cands = list(args[1:]) or ["python", "c", "cpp", "rustc", "go", "julia"]
        # normalize rustc->rust style
        rows = rt.rank_languages(cands)
        return "\n".join("%s  cost=%.3f  warm=%s" % (a, b, c) for a, b, c in rows)
    return "usage: accel status|warm|rank [langs…]"


@command("pool", "sCode / predictive pool diagnostics")
def _cmd_pool(app=None, **_k):
    lines = []
    try:
        import predictive_accel_runtime as par
        lines.append(par.get_runtime().status_text())
    except Exception as exc:
        lines.append(f"predictive: {exc}")
    try:
        from scode_optimizer_bridge import get_bridge
        b = get_bridge()
        if b is None:
            lines.append("scode bridge: none")
        else:
            st = getattr(b, "_stats", {}) or {}
            lines.append("scode pool hits=%s misses=%s evictions=%s" % (
                st.get("pool_hits"), st.get("pool_misses"), st.get("pool_evictions")))
            if hasattr(b, "lease_vector"):
                lines.append("scode leases: available")
    except Exception as exc:
        lines.append(f"scode: {exc}")
    return "\n".join(lines)


@command("migrate", "multidimensional migration score window= activity= tedious=")
def _cmd_migrate(app=None, **kw):
    def f(name, default=0.0):
        if name in kw:
            try: return float(kw[name])
            except Exception: return default
        return default
    try:
        import predictive_accel_runtime as par
        sc = par.migration_score(f("window"), f("activity"), f("tedious", 0.5))
        admit = par.predict_admission_ok(sc)
        return "class=%s raw=%.4f norm=%.4f admit_predictive=%s\nshares window=%.3f activity=%.3f tedious=%.3f" % (
            sc["suggest_class"], sc["raw"], sc["normalized"], admit,
            sc["window_share"], sc["activity_share"], sc["tedious_share"])
    except Exception as exc:
        return str(exc)


@command("hwprog", "hardware / OS snapshot for appliance programming (no shell)")
def _cmd_hwprog(app=None, **_k):
    try:
        import predictive_accel_runtime as par
        import json
        return json.dumps(par.get_runtime().hardware_snapshot(), indent=2, default=str)
    except Exception as exc:
        return str(exc)



@command("scifractal", "scientific fractal: node|bundle|hw  [seed]  [address]")
def _cmd_scifractal(app=None, **kw):
    args = list(kw.get("_args") or [])
    action = (args[0] if args else "node").lower()
    try:
        import scientific_fractal_compose as sfc
    except Exception as exc:
        return f"scifractal unavailable: {exc}"
    seed = args[1] if len(args) > 1 else sfc.DEFAULT_SEED
    address = args[2] if len(args) > 2 else sfc.DEFAULT_ADDRESS
    if action in ("hw", "hardware"):
        import json
        return json.dumps(sfc.discover_hardware(), indent=2, default=str)[:4000]
    if action == "bundle":
        b = sfc.compose_bundle(seed, use_hardware=False)
        return "nodes=%d audio=%s sr=%s seed=%s" % (
            len(b["nodes"]),
            0 if not b.get("audio") else len(b["audio"]),
            b.get("sample_rate"),
            b.get("seed"),
        )
    node = sfc.compose(seed, address, use_hardware=False)
    return "domain=%s method=%s reading=%s audio=%s params=%d" % (
        node.domain, node.method, node.reading,
        None if node.audio is None else tuple(node.audio.shape),
        int(node.params.size),
    )



@command("fractalcore", "perfect fractal: engine|post|perfect|ext  [seed] [address|ops]")
def _cmd_fractalcore(app=None, **kw):
    args = list(kw.get("_args") or [])
    act = (args[0] if args else "perfect").lower()
    try:
        import scientific_fractal_core as f
    except Exception as exc:
        return str(exc)
    seed = args[1] if len(args) > 1 else f.DEFAULT_SEED
    if act == "ext":
        mgr = f.ExtensionManager(); n = mgr.scan()
        slots = mgr.as_vst_slots()
        lines = ["%d extensions, %d vst-like slots" % (n, sum(1 for s in slots if s["vst_like"]))]
        for s in slots[:24]:
            lines.append("%s  %s  roles=%s" % (s["id"], "VST" if s["vst_like"] else "tool", s["roles"]))
        return "\n".join(lines)
    if act == "engine":
        addr = args[2] if len(args) > 2 else "value/sound/fm"
        s = f.engine(seed, addr)
        return "kind=%s samples/meta=%s" % (s.kind, s.meta)
    if act == "post":
        addr = args[2] if len(args) > 2 else "value/sound/fm"
        ops = args[3] if len(args) > 3 else "reverb/phi_smooth"
        s = f.postprocess(f.engine(seed, addr), ops)
        return "kind=%s pp=%s" % (s.kind, s.meta.get("pp"))
    b = f.compose_perfect(seed)
    return "perfect audio=%d video=%s game=%s control=%d" % (
        len(b["audio"].data), b["video"].data.shape, bool(b["game"].data), len(b["control"].data))



@command("devkit", "fractal dev: doctor|ops|slots|scaffold <id>|preview")
def _cmd_devkit(app=None, **kw):
    args = list(kw.get("_args") or [])
    act = (args[0] if args else "doctor").lower()
    try:
        import fractal_devkit as d
    except Exception as exc:
        return str(exc)
    if act == "ops":
        return "\n".join(d.list_ops())
    if act == "slots":
        import json
        return json.dumps(d.list_slots()[:30], indent=2)
    if act == "scaffold":
        pid = args[1] if len(args) > 1 else "my-fractal-tool"
        return str(d.scaffold_plugin(pid))
    if act == "preview":
        import json
        return json.dumps(d.render_preview(), indent=2)
    return d.doctor()



@command("studio", "open Fractal Studio GUI")
def _cmd_studio(app=None, **_k):
    try:
        import fractal_studio_gui as s
        s.open_window(app)
        return "Fractal Studio opened"
    except Exception as exc:
        return str(exc)



@command("screenshare", "ET screenshare: status|on|off|mode lan_host|anytime|trust <id>|untrust <id>|rd")
def _cmd_screenshare(app=None, **kw):
    args = list(kw.get("_args") or [])
    act = (args[0] if args else "status").lower()
    try:
        import edit_together_remote_desktop as rd
    except Exception as exc:
        return str(exc)
    if act == "on":
        return rd.set_enabled(True) + " · " + rd.start_timer(app)
    if act == "off":
        return rd.stop_timer()
    if act == "mode" and len(args) > 1:
        return rd.set_mode(args[1])
    if act == "trust" and len(args) > 1:
        return rd.trust(args[1])
    if act == "untrust" and len(args) > 1:
        return rd.untrust(args[1])
    if act == "rd":
        rd.set_remote_desktop(True)
        rd.open_remote_viewer(app)
        return "remote desktop viewer opened"
    import json
    return json.dumps(rd.status(), indent=2)


@command("vst", "VST/LV2 binaries: list|install <path>|move <path>|gui")
def _cmd_vst(app=None, **kw):
    args = list(kw.get("_args") or [])
    act = (args[0] if args else "list").lower()
    try:
        import vst_binary_tools as v
    except Exception as exc:
        return str(exc)
    if act == "gui":
        v.open_window(app)
        return "VST install window opened"
    if act in ("install", "move") and len(args) > 1:
        import json
        return json.dumps(v.install_binary(args[1], move=(act == "move")), indent=2)
    import json
    return json.dumps(v.list_installed()[:40], indent=2)



@command("resources", "CPU/RAM pool governor: status|rebalance|warm|lang")
def _cmd_resources(app=None, **kw):
    args = list(kw.get("_args") or [])
    act = (args[0] if args else "status").lower()
    try:
        import resource_pool_governor as g
        import predictive_accel_runtime as p
    except Exception as exc:
        return str(exc)
    if act == "rebalance":
        return str(p.get_runtime().rebalance())
    if act == "warm":
        return p.predictive_warm_languages()
    if act == "lang":
        cands = args[1:] or ["python", "c", "cpp", "go", "rustc"]
        return g.preferred_lang(cands)
    return g.status_text()


def _ufs_args(kw):
    return [a for a in (kw.get("_args") or []) if a]


def _sudo_hint():
    try:
        import sos_tools
        if not sos_tools.sudo_ready():
            return "\n  (needs administrator: run  sudo -v  first — password 'groovebox' by default — or use File Studio ▸ 💽 Drives)"
    except Exception:
        pass
    return ""


@command("drives", "list every disk / partition: file system, label, size, mount point (lsblk)")
def _cmd_drives(app=None, **kw):
    import unified_fs as u
    rows = [f"  {b.get('path',''):<16} {str(b.get('fstype') or ''):<12} {str(b.get('label') or ''):<16} "
            f"{int(b.get('size') or 0)/1e9:7.1f} GB  {', '.join(m for m in (b.get('mountpoints') or []) if m)}"
            for b in u.blockdevs() if b.get("type") in ("disk", "part", "crypt", "lvm", "rom", "loop")]
    return "\n".join(rows) or "no block devices"


@command("mount", "mount a partition with the right driver: mount /dev/sdb1 [ro]")
def _cmd_mount(app=None, **kw):
    import unified_fs as u
    a = _ufs_args(kw)
    if not a:
        return "usage: mount /dev/sdXN [ro]   (see: drives)"
    ok, msg = u.mount(a[0], read_only=("ro" in a[1:]))
    return ("✔ mounted at " if ok else "⚠ ") + str(msg) + ("" if ok else _sudo_hint())


@command("umount", "unmount a partition or mount point and sync: umount /dev/sdb1")
def _cmd_umount(app=None, **kw):
    import unified_fs as u
    a = _ufs_args(kw)
    if not a:
        return "usage: umount /dev/sdXN | /media/groovebox/NAME"
    ok, msg = u.unmount(a[0])
    return ("✔ " if ok else "⚠ ") + str(msg) + ("" if ok else _sudo_hint())


@command("unlock", "open an encrypted (LUKS / BitLocker) partition, then mount it: unlock /dev/sdb2")
def _cmd_unlock(app=None, **kw):
    import unified_fs as u
    a = _ufs_args(kw)
    if not a:
        return "usage: unlock /dev/sdXN   (asks for the passphrase in a dialog)"
    from PyQt6.QtWidgets import QInputDialog, QLineEdit
    pw, ok = QInputDialog.getText(None, "Unlock", f"Passphrase for {a[0]}:", QLineEdit.EchoMode.Password)
    if not ok:
        return "cancelled"
    good, mp = u.unlock(a[0], pw)
    if not good:
        return "⚠ " + str(mp) + _sudo_hint()
    ok2, msg = u.mount(mp)
    return f"✔ unlocked {mp}" + (f" · mounted at {msg}" if ok2 else f" · mount: {msg}")


@command("mountimage", "loop-mount a disk image read-only: mountimage ~/file.iso")
def _cmd_mountimage(app=None, **kw):
    import unified_fs as u
    a = _ufs_args(kw)
    if not a:
        return "usage: mountimage PATH(.iso/.img/.squashfs)"
    ok, msg = u.mount_image(a[0])
    return ("✔ mounted: " if ok else "⚠ ") + str(msg) + ("" if ok else _sudo_hint())


@command("lvm", "activate LVM volumes so their logical volumes can be mounted")
def _cmd_lvm(app=None, **kw):
    import unified_fs as u
    ok, msg = u.activate_lvm()
    return ("✔ " if ok else "⚠ ") + str(msg)


@command("repairusb", "repair a stuck/corrupted USB or SD: repairusb /dev/sdX [fat32|exfat|ext4|ntfs] — erases it")
def _cmd_repairusb(app=None, **kw):
    a = _ufs_args(kw)
    if not a or not a[0].startswith("/dev/"):
        return "usage: repairusb /dev/sdX [fat32|exfat|ext4|ntfs]   (see: drives — the whole stick, not a partition)"
    fs = {"fat32": "FAT32", "exfat": "exFAT", "ext4": "ext4", "ntfs": "NTFS"}.get((a[1] if len(a) > 1 else "fat32").lower(), "FAT32")
    import drive_formatter as dfm, drive_guard
    try:
        dev = drive_guard.assert_safe_target(a[0])           # refuses the system disk and the boot drive
    except Exception as exc:
        return f"⚠ refused: {exc}"
    from PyQt6.QtWidgets import QInputDialog
    txt, ok = QInputDialog.getText(None, "Repair USB", f"EVERYTHING on {dev} will be erased and it becomes one {fs} partition.\n"
                                   f"Type the device name to confirm ({dev}):")
    if not ok or txt.strip() != dev:
        return "cancelled (confirmation did not match)"
    try:
        import sos_tools
        if not sos_tools.ensure_sudo(None, "Formatting needs administrator rights (default password: groovebox)."):
            return "cancelled (no administrator password)"
        log = []
        dfm.format_drive(dev, fs, "GROOVEBOX", progress=log.append)
        return "✔ repaired: " + " → ".join(log)
    except Exception as exc:
        return f"⚠ {exc}\n  last resort, one line at a time:\n  sudo umount -l {dev}1\n  sudo wipefs -a {dev}\n" \
               f"  sudo parted -s {dev} mklabel msdos mkpart primary fat32 1MiB 100%\n  sudo mkfs.vfat -F 32 -n GROOVEBOX {dev}1"


@command("isojoin", "join NAME.iso.part00… into NAME.iso and check its .sha256 (isojoin [folder | part file])", slow=True)
def _cmd_isojoin(app=None, **kw):
    import iso_parts
    where = (kw.get("_args") or [None])[0]
    r = iso_parts.join_newest(where)
    head = "✔ " if r["ok"] else "⚠ "
    tail = ("\n  " + r["iso"] + ("\n  sha256 " + r["sha256"] if r.get("sha256") else "")) if r.get("iso") else ""
    nxt = "\n  next: Drives ▸ Write ISO (USB stick) or Drive / Clone ▸ Burn (disc)" if r["ok"] else ""
    return head + r["message"] + tail + nxt


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
