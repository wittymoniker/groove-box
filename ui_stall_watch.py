"""ui_stall_watch.py — GROOVEBOX_R32_UI_STALL_WATCH_20261110

Finds the work that freezes every window. All Qt windows share the GUI thread, so one long
call blocks them all. A QTimer on the GUI thread beats every 50 ms; a watcher thread checks
the beat and, when it is late by more than ``threshold_ms`` (default 250), samples the GUI
thread's Python stack (sys._current_frames) every 20 ms until it recovers. Each stall is
recorded with its duration and the *innermost Groovebox frames* it spent most time in:

    ~/.groovebox/logs/ui_stalls.jsonl   one JSON line per stall
    report()                            the worst offenders (function, file:line, total ms, count)

Cost: one tiny timer + a sleeping thread; sampling only runs during a stall.
GROOVEBOX_UI_STALL_WATCH=0 turns it off.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import threading
import time

_STATE = {"beat": time.monotonic(), "thread": None, "gui_ident": None, "stats": collections.Counter(),
          "ms": collections.Counter(), "count": 0}


def _log_path():
    try:
        import groovebox_paths
        return os.path.join(groovebox_paths.logs_dir(), "ui_stalls.jsonl")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".groovebox", "logs", "ui_stalls.jsonl")


def _frames(ident, here):
    f = sys._current_frames().get(ident)
    out = []
    while f is not None and len(out) < 40:
        co = f.f_code
        fn = co.co_filename
        if fn.startswith(here) and "ui_stall_watch" not in fn:
            out.append("%s (%s:%d)" % (co.co_name, os.path.basename(fn), f.f_lineno))
        f = f.f_back
    return out


def _watch(threshold, here):
    while True:
        time.sleep(0.05)
        late = (time.monotonic() - _STATE["beat"]) * 1000.0
        if late < threshold:
            continue
        t0 = time.monotonic() - late / 1000.0
        samples = collections.Counter()
        while (time.monotonic() - _STATE["beat"]) * 1000.0 >= 60.0:
            fr = _frames(_STATE["gui_ident"], here)
            if fr:
                samples[fr[0]] += 1
                if len(fr) > 1:
                    samples["  via " + fr[1]] += 0
            time.sleep(0.02)
            if time.monotonic() - t0 > 120:
                break
        dur = (time.monotonic() - t0) * 1000.0
        top = [k for k, _ in samples.most_common(5) if not k.startswith("  via")]
        rec = {"at": time.time(), "ms": round(dur), "top": top}
        _STATE["count"] += 1
        if top:
            _STATE["ms"][top[0]] += dur
            _STATE["stats"][top[0]] += 1
        try:
            os.makedirs(os.path.dirname(_log_path()), exist_ok=True)
            with open(_log_path(), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except Exception:
            pass
        if dur > 1000:
            print("[UI stall] %.0f ms in %s" % (dur, top[0] if top else "?"), file=sys.stderr)


def install(app=None, threshold_ms=250):
    if os.environ.get("GROOVEBOX_UI_STALL_WATCH", "1") == "0" or os.environ.get("GROOVEBOX_HEADLESS_WORKER") == "1" or _STATE["thread"] is not None:
        return
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    qa = QApplication.instance()
    if qa is None:
        return
    _STATE["gui_ident"] = threading.get_ident()
    t = QTimer(qa); t.setInterval(50)
    t.timeout.connect(lambda: _STATE.__setitem__("beat", time.monotonic()))
    t.start(); _STATE["timer"] = t
    here = os.path.dirname(os.path.abspath(__file__))
    th = threading.Thread(target=_watch, args=(float(threshold_ms), here), name="groovebox-ui-stall-watch", daemon=True)
    th.start(); _STATE["thread"] = th


def report(n=12):
    rows = sorted(_STATE["ms"].items(), key=lambda kv: -kv[1])[:n]
    return [{"where": k, "total_ms": round(v), "count": _STATE["stats"][k]} for k, v in rows]


def open_window(app):
    _old = getattr(app, "_ui_stall_window", None)          # R32.8 sweep: one window, not a new one per click
    try:
        if _old is not None:
            _old.show(); _old.raise_(); _old.activateWindow(); return _old
    except RuntimeError:
        pass
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QLabel
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🐢 UI stalls · what froze the windows"); w.resize(720, 420)
    lay = QVBoxLayout(w); lay.addWidget(QLabel("Functions that blocked the shared window thread this session (longest total first)."))
    ed = QTextEdit(); ed.setReadOnly(True); ed.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;"); lay.addWidget(ed)

    def fill():
        rows = report(40)
        ed.setPlainText("%d stall(s) · log: %s\n\n" % (_STATE["count"], _log_path()) +
                        "\n".join("%7d ms  ×%-3d %s" % (r["total_ms"], r["count"], r["where"]) for r in rows) or "no stalls ≥ 250 ms")
    b = QPushButton("Refresh"); b.clicked.connect(fill); lay.addWidget(b); fill()
    app._ui_stall_window = w; w.show(); return w
