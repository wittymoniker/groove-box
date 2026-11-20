"""GROOVEBOX_R124_FEATURES (UNVERIFIED): one hub for the R124 science / live / external-support features.

install(app) adds the menu "Science & Live", MIDI learn, render stamps on every export, safe mode and the
device profile. Every dialog is a thin view over a pure module (measure_core, master_chain, signal_truth,
repro_stamp, constraint_composer, param_lineage, scene_pads, av_scene_graph, game_export_check,
connect_probe, midi_learn, device_profiles, safe_mode); Ctrl+K (accessibility) opens command_palette.
"""
from __future__ import annotations

import json
import os


def _text_dialog(app, title, body, attr=None, extra=None):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QHBoxLayout, QPushButton
    d = getattr(app, attr, None) if attr else None
    if d is None:
        d = QDialog(app); d.setWindowTitle(title); d.resize(820, 560); d.setProperty("gb_no_auto_scroll", True)
        v = QVBoxLayout(d); ed = QPlainTextEdit(); ed.setReadOnly(True)
        ed.setStyleSheet("font-family:monospace; font-size:9pt;"); v.addWidget(ed, 1)
        row = QHBoxLayout(); v.addLayout(row); d._row = row
        for label, fn in (extra or []):
            b = QPushButton(label); b.clicked.connect(lambda _c=False, f=fn, dd=d: f(dd)); row.addWidget(b)
        row.addStretch(1)
        close = QPushButton("Close"); close.clicked.connect(d.hide); row.addWidget(close)
        d._edit = ed
        if attr:
            setattr(app, attr, d)
    d._edit.setPlainText(body if isinstance(body, str) else json.dumps(body, indent=2, default=str))
    d.show(); d.raise_(); d.activateWindow()
    return d


def _mix(app, max_rows=None, purpose="Measure"):
    import numpy as np
    try:
        out = app._get_shared_mixdown_buffer(max_rows, purpose)
        buf, sr = (out[0], out[1]) if isinstance(out, (tuple, list)) else (out, 48000)
        if buf is None:
            return None, 48000
        return np.asarray(buf, dtype=np.float64), int(sr or 48000)
    except Exception as exc:
        print(f"[r124] mixdown unavailable: {exc}")
        return None, 48000


def _fmt_summary(s):
    order = ("peak_dbfs", "true_peak_dbtp", "rms_dbfs", "lufs_i", "lufs", "correlation", "centroid_hz", "seconds", "sr")
    keys = [k for k in order if k in s] + [k for k in s if k not in order and not isinstance(s[k], (list, dict))]
    return "\n".join(f"{k:<16} {s[k]}" for k in keys)


# ---------------------------------------------------------------- dialogs
def measurement(app):
    import measure_core as mc
    buf, sr = _mix(app, 256, "Measure")
    if buf is None:
        return _text_dialog(app, "Measurement", "No mixdown buffer yet — play or render once.", "_r124_meas")
    s = mc.summary(buf, sr)
    body = "MEASUREMENT (shared mixdown, first 256 rows)\n\n" + _fmt_summary(s)
    try:
        import master_chain
        _y, rep = master_chain.process(buf, sr, mode="live", measure=True)
        body += "\n\nMASTER CHAIN (live) stage by stage:\n" + "\n".join(
            f"  {st['stage']:<8} in {st['in'].get('lufs_i', st['in'].get('rms_dbfs'))}  →  out {st['out'].get('lufs_i', st['out'].get('rms_dbfs'))}"
            f"   peak {st['out'].get('true_peak_dbtp')}" for st in rep["stages"])
    except Exception as exc:
        body += f"\n\nmaster chain: {exc}"
    return _text_dialog(app, "Measurement", body, "_r124_meas", [("Refresh", lambda _d: measurement(app))])


def signal_bench(app):
    import signal_truth as stt
    out = {"identity (reference)": stt.bench(stt.identity),
           "master chain · live": stt.bench(stt.master_chain_fn("live")),
           "master chain · final": stt.bench(stt.master_chain_fn("final"))}
    return _text_dialog(app, "Signal ground-truth bench", out, "_r124_bench")


def master_chain_settings(app):
    import master_chain
    from PyQt6.QtWidgets import QInputDialog
    st = master_chain.load()
    txt, ok = QInputDialog.getMultiLineText(app, "Master chain (eq → dyn → spatial → limiter → dither)",
                                            "Edit the JSON; mode is live or final:", json.dumps(st, indent=2))
    if ok:
        try:
            master_chain.save(json.loads(txt))
        except Exception as exc:
            _text_dialog(app, "Master chain", f"Not saved: {exc}")


def compose(app):
    import constraint_composer as cc
    from PyQt6.QtWidgets import QInputDialog
    txt, ok = QInputDialog.getMultiLineText(app, "Constraint composer",
                                            "Rules (JSON). Applied to the selected sequence; Ctrl+Z undoes.",
                                            json.dumps(cc.DEFAULT_RULES, indent=2))
    if not ok:
        return None
    try:
        rules = json.loads(txt)
    except Exception as exc:
        return _text_dialog(app, "Constraint composer", f"Rules are not valid JSON: {exc}")
    try:
        app._push_undo("Constraint compose")
    except Exception:
        pass
    out = cc.apply_to_selected(app, rules)
    return _text_dialog(app, "Constraint composer", out if out is not None else "No sequence selected.")


def lineage(app):
    import param_lineage as pl
    from PyQt6.QtWidgets import QInputDialog
    p, ok = QInputDialog.getText(app, "Parameter lineage", "Parameter name (e.g. cutoff, bpm, seed):")
    if ok and p.strip():
        return _text_dialog(app, f"Lineage · {p.strip()}", pl.text(app, p.strip()), "_r124_lineage")


def av_scene_export(app):
    import av_scene_graph as av
    from PyQt6.QtWidgets import QFileDialog
    buf, sr = _mix(app, None, "AV scene")
    if buf is None:
        return _text_dialog(app, "AV scene", "No mixdown buffer yet — play or render once.")
    path, _ = QFileDialog.getSaveFileName(app, "Export audio-reactive scene", os.path.expanduser("~/scene.gbscene.json"),
                                          "Scene JSON (*.json)")
    if not path:
        return None
    g = av.load_graph(app)
    bpm = float(getattr(getattr(app, "spin_bpm", None), "value", lambda: 120.0)())
    frames = av.render_frames(g, buf, sr, 30, bpm)
    av.export_scene(g, path, frames, 30, {"bpm": bpm, "sr": sr})
    return _text_dialog(app, "AV scene", f"{len(frames)} frames → {path}")


def game_check(app):
    import game_export_check as gx
    from PyQt6.QtWidgets import QFileDialog
    d = QFileDialog.getExistingDirectory(app, "Game folder to check", os.path.expanduser("~"))
    if d:
        return _text_dialog(app, "Game export check", gx.check(d, 8.0), "_r124_game")


def connect_panel(app):
    import connect_probe as cp
    return _text_dialog(app, "Connect", "CONNECT — every external link, with the fix for anything missing\n\n" + cp.text(),
                        "_r124_connect", [("Re-check", lambda _d: connect_panel(app)),
                                          ("MIDI learn", lambda _d: midi_learn_arm(app))])


def stamp_diff(app):
    import repro_stamp as rs
    from PyQt6.QtWidgets import QFileDialog
    a, _ = QFileDialog.getOpenFileName(app, "First render stamp", os.path.expanduser("~"), "Stamps (*.stamp.json)")
    if not a:
        return None
    b, _ = QFileDialog.getOpenFileName(app, "Second render stamp", os.path.dirname(a), "Stamps (*.stamp.json)")
    if not b:
        return None
    sa, sb = rs.read(a), rs.read(b)
    body = {"same_render": rs.same_render(sa, sb), "differences": rs.diff(sa, sb), "rebuild": rs.rebuild_hint(sa)}
    return _text_dialog(app, "Render stamp diff", body, "_r124_stamp")


def device_profile(app):
    import device_profiles as dp
    from PyQt6.QtWidgets import QInputDialog
    names = ["auto"] + list(dp.PROFILES)
    cur = dp.chosen()
    name, ok = QInputDialog.getItem(app, "Device profile", f"Detected: {dp.detect(app)}", names,
                                    names.index(cur) if cur in names else 0, False)
    if ok:
        dp.apply(app, name, persist=True)
        try:
            app.statusBar().showMessage(f"Device profile: {name} → {app._r124_device_profile}", 5000)
        except Exception:
            pass


def midi_learn_arm(app):
    import midi_learn as ml
    ml.arm(app, not ml._STATE["armed"])


def leave_safe(app):
    import safe_mode as sm
    sm.leave_safe_mode(app)


def commands(app):
    return [("Measurement overlay", "", lambda: measurement(app)),
            ("Signal ground-truth bench", "", lambda: signal_bench(app)),
            ("Master chain settings", "", lambda: master_chain_settings(app)),
            ("Constraint composer", "", lambda: compose(app)),
            ("Parameter lineage", "", lambda: lineage(app)),
            ("Export audio-reactive AV scene", "", lambda: av_scene_export(app)),
            ("Game export check", "", lambda: game_check(app)),
            ("Connect panel", "", lambda: connect_panel(app)),
            ("MIDI learn (toggle)", "Ctrl+Alt+L", lambda: midi_learn_arm(app)),
            ("Render stamp diff", "", lambda: stamp_diff(app)),
            ("Device profile", "", lambda: device_profile(app)),
            ("Leave safe mode", "", lambda: leave_safe(app))]


def install(app):
    if getattr(app, "_r124_installed", False):
        return True
    app._r124_installed = True
    from PyQt6.QtGui import QShortcut, QKeySequence
    from PyQt6.QtCore import Qt
    try:
        menu = app.menuBar().addMenu("Science && Live")
        for title, keys, fn in commands(app):
            act = menu.addAction(title); act.triggered.connect(lambda _c=False, f=fn: f())
            if keys:
                act.setShortcut(QKeySequence(keys)); act.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        app._r124_menu = menu
    except Exception as exc:
        print(f"[r124] menu: {exc}")
    for name, fn in (("error_report", lambda: __import__("error_report").install_slot_hook(app)),
                     ("repro_stamp", lambda: __import__("repro_stamp").wrap_exports(app)),
                     ("midi_learn", lambda: __import__("midi_learn").install(app)),
                     ("device_profiles", lambda: __import__("device_profiles").apply(app)),
                     ("safe_mode", lambda: __import__("safe_mode").startup(app, ask=os.environ.get("QT_QPA_PLATFORM") != "offscreen" and os.environ.get("GROOVEBOX_NO_SAFE_PROMPT") != "1"))):
        try:
            fn()
        except Exception as exc:
            print(f"[r124] {name}: {exc}")
    try:  # scene pads join the LIVE DECK
        box = getattr(app, "live_deck_group", None)
        if box is not None and not getattr(app, "_r124_scene_row", None):
            import scene_pads
            row = scene_pads.build_row(app)
            box.layout().addWidget(row); app._r124_scene_row = row
    except Exception as exc:
        print(f"[r124] scene pads: {exc}")
    return True
