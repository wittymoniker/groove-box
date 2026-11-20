"""live_keys.py — live-performance and heavy-command keyboard shortcuts.

GROOVEBOX_R123_LIVE_KEYS_20261119

Live performance sits on Alt (never clashes with typing in a text field or the key chart);
heavy render / compute commands sit on Ctrl+Shift so they are hard to hit by accident.
Every binding calls an existing button / method, so it does exactly what the on-screen
control does (same undo boundaries, same guards). Ctrl+/ shows this sheet.
Heavy commands are debounced (one launch per 1.5 s) so a held key can't queue renders.
"""
from __future__ import annotations

import time

MARKER = "GROOVEBOX_R123_LIVE_KEYS_20261119"
_HEAVY_DEBOUNCE_S = 1.5


def _click(host, *path):
    def go():
        obj = host
        for p in path:
            obj = getattr(obj, p, None)
            if obj is None:
                return
        obj.click()
    return go


def _call(host, *path, args=()):
    def go():
        obj = host
        for p in path:
            obj = getattr(obj, p, None)
            if obj is None:
                return
        if callable(obj):
            obj(*args)
    return go


def _bpm(host, delta):
    def go():
        sp = getattr(host, "spin_bpm", None)
        if sp is not None:
            sp.setValue(max(sp.minimum() + 1.0, min(sp.maximum(), round(sp.value() + delta, 3))))
            _say(host, f"BPM {sp.value():g}")
    return go


def _say(host, text):
    try:
        host.statusBar().showMessage("⌨ " + text, 2500)
    except Exception:
        pass


def _smooth_toggle(host):
    def go():
        try:
            import compat_settings as cs
            cur = str(cs.load().get("smooth_mode", "auto"))
            nxt = "on" if cur != "on" else "off"
            cs.update(smooth_mode=nxt)
            _say(host, f"Smooth mode {nxt} (CPU relief {'ON' if nxt == 'on' else 'off'})")
        except Exception as exc:
            _say(host, f"smooth mode unavailable: {exc}")
    return go


def _hybrid_build(host):
    def go():
        try:
            import hybrid_native as hn
            hn.ensure_started()
            st = hn.status()
            _say(host, "Hybrid native kernels: " + ", ".join(f"{k}={v}" for k, v in (st or {}).items()))
        except Exception as exc:
            _say(host, f"hybrid kernels unavailable: {exc}")
    return go


def _slot(host, name, store):
    def go():
        row = getattr(host, "sequence_perform_row", None)
        if row is None:
            return
        (row.slot_store if store else row.slot_recall)(name)
        _say(host, f"state {name} {'stored' if store else 'recalled'}")
    return go


def bindings(host):
    """[(group, keys, label, fn, heavy)]"""
    spr = ("sequence_perform_row",)
    live = [
        ("Alt+Space", "Play / pause transport", _call(host, "toggle_playback")),
        ("Alt+.", "PANIC · stop everything", _call(host, "_perf_stop_all")),
        ("F8", "Play / pause transport (Alt+Space may belong to the window manager)", _call(host, "toggle_playback")),
        ("Media Play", "Play / pause transport", _call(host, "toggle_playback")),
        ("Pause", "PANIC · stop everything", _call(host, "_perf_stop_all")),
        ("Media Stop", "PANIC · stop everything", _call(host, "_perf_stop_all")),
        ("Alt+Return", "Play selected sequence", _call(host, "play_selected_sequence")),
        ("Alt+I", "Play selected instrument (X/Y pattern)", _call(host, "_perf_play_sel_instrument")),
        ("Alt+Shift+I", "Play selected pattern (X/Y program)", _call(host, "_perf_play_sel_pattern")),
        ("Alt+Left", "Previous sequence", _call(host, *spr, "step_sequence", args=(-1,))),
        ("Alt+Right", "Next sequence", _call(host, *spr, "step_sequence", args=(1,))),
        ("Alt+A", "Auto-play stepped sequence (toggle)", _click(host, *spr, "b_auto")),
        ("Alt+L", "Loop this sequence (toggle)", _click(host, *spr, "b_loop")),
        ("Alt+T", "Tap tempo", _call(host, *spr, "tap")),
        ("Alt+R", "Take · arm recording (toggle)", _click(host, *spr, "b_rec")),
        ("Alt+Q", "Cue: add current sequence", _call(host, *spr, "cue_add")),
        ("Alt+W", "Cue: play queue", _call(host, *spr, "cue_play")),
        ("Alt+E", "Cue: remove last", _call(host, *spr, "cue_pop")),
        ("Alt+H", "Hold note (toggle)", _click(host, "btn_perf_hold")),
        ("Alt+Shift+H", "Hold note global (toggle)", _click(host, "btn_perf_hold_global")),
        ("Alt+G", "Begin playing random (toggle)", _click(host, "btn_perf_random")),
        ("Alt+Shift+G", "Global random (toggle)", _click(host, "btn_perf_random_global")),
        ("Alt+P", "Random patch per phrase (toggle)", _click(host, "chk_perf_random_patch")),
        ("Alt+F", "Freeze bend (toggle)", _click(host, "btn_gp_freeze")),
        ("Alt+M", "Markov Resampler", _call(host, "_open_markov_resampler")),
        ("Alt+Up", "BPM +1", _bpm(host, 1.0)),
        ("Alt+Down", "BPM −1", _bpm(host, -1.0)),
        ("Alt+Shift+Up", "BPM +10", _bpm(host, 10.0)),
        ("Alt+Shift+Down", "BPM −10", _bpm(host, -10.0)),
    ]
    for i, n in enumerate(("A", "B", "C"), start=1):
        live.append((f"Alt+{i}", f"Recall state {n}", _slot(host, n, False)))
        live.append((f"Alt+Shift+{i}", f"Store state {n}", _slot(host, n, True)))
    heavy = [
        ("Ctrl+Shift+E", "Export mixdown…", _call(host, "export_mixdown_dialog")),
        ("Ctrl+Shift+V", "Export video…", _call(host, "export_video_dialog")),
        ("Ctrl+Shift+B", "Export all formats…", _call(host, "export_all_formats_dialog")),
        ("Ctrl+Shift+Q", "Render queue…", _call(host, "render_queue_dialog")),
        ("Ctrl+Shift+R", "Randomize ALL (one undo step)", _call(host, "_randomize_everything_scoped", args=(True,))),
        ("Ctrl+Shift+A", "Randomize all automation everywhere", _call(host, "_randomize_all_automation_everywhere")),
        ("Ctrl+Shift+J", "Build hybrid native kernels (C / Go) now", _hybrid_build(host)),
        ("Ctrl+Shift+M", "Smooth mode on/off (CPU relief)", _smooth_toggle(host)),
        ("Ctrl+Shift+H", "System / performance health", _call(host, "_open_system_health_panel")),
    ]
    out = [("Live performance", k, lab, fn, False) for k, lab, fn in live]
    out += [("Heavy commands", k, lab, fn, True) for k, lab, fn in heavy]
    return out


def _taken(host):
    from PyQt6.QtGui import QShortcut, QAction, QKeySequence
    keys = set()
    for sc in host.findChildren(QShortcut):
        keys.add(sc.key().toString())
    for a in host.findChildren(QAction):
        for k in a.shortcuts():
            keys.add(k.toString())
    try:
        from PyQt6.QtWidgets import QApplication
        for sc in QApplication.instance().findChildren(QShortcut):
            keys.add(sc.key().toString())
    except Exception:
        pass
    keys.discard("")
    return keys


def install(host):
    """Create the shortcuts once (skipping any sequence another feature already owns)."""
    if getattr(host, "_r123_live_keys", None) is not None:
        return host._r123_live_keys
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QShortcut, QKeySequence
    taken = _taken(host)
    made, skipped = [], []
    last = {"t": 0.0}

    def wrap(fn, label, heavy):
        def go():
            if heavy:
                now = time.monotonic()
                if now - last["t"] < _HEAVY_DEBOUNCE_S:
                    return
                last["t"] = now
            try:
                fn()
            except Exception as exc:
                _say(host, f"{label}: {exc}")
        return go

    for group, key, label, fn, heavy in bindings(host):
        ks = QKeySequence(key).toString()
        if ks in taken:
            skipped.append(key); continue
        sc = QShortcut(QKeySequence(key), host)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.setAutoRepeat(not heavy and "BPM" in label)
        sc.activated.connect(wrap(fn, label, heavy))
        sc.setProperty("gbLabel", f"{group}: {label}")
        made.append(sc); taken.add(ks)
    sheet = QShortcut(QKeySequence("Ctrl+/"), host)
    sheet.setContext(Qt.ShortcutContext.ApplicationShortcut)
    sheet.activated.connect(lambda: show_sheet(host))
    made.append(sheet)
    host._r123_live_keys = made
    host._r123_live_keys_skipped = skipped
    return made


def sheet_text(host) -> str:
    lines = ["LIVE PERFORMANCE & HEAVY-COMMAND SHORTCUTS (Ctrl+/)", ""]
    group = None
    skipped = set(getattr(host, "_r123_live_keys_skipped", ()) or ())
    for g, key, label, _fn, _h in bindings(host):
        if g != group:
            lines.append(f"— {g} —"); group = g
        lines.append(f"  {key:<16} {label}" + ("   (taken by another feature)" if key in skipped else ""))
    lines += ["", "Also: Tab / Shift+Tab instrument walk · hold Enter = record loop · Shift+F1–F12 and keypad = "
              "intelligence studios · Ctrl+K command palette · Ctrl+Z / Ctrl+Y undo / redo · Ctrl+Alt+1–4 geometrics."]
    return "\n".join(lines)


def show_sheet(host):
    from PyQt6.QtWidgets import QMessageBox
    box = QMessageBox(host)
    box.setWindowTitle("Keyboard shortcuts")
    box.setText("<pre style='font-size:9pt'>" + sheet_text(host).replace("<", "&lt;") + "</pre>")
    box.exec()
