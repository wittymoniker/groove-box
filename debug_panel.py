"""🐞 Debug tools: freeze detector (main-thread stall stacks) + Debug window.

GROOVEBOX_R23R_DEBUG_TOOLS_20261103

StallMonitor   A GUI heartbeat (QTimer, 50 ms) plus a watchdog thread. When the
               GUI thread stops answering for more than `threshold` seconds the
               watchdog captures the MAIN THREAD'S CURRENT STACK and the stacks of
               every other Groovebox thread into <data>/logs/stalls.log — the exact
               line that froze the window. One entry per stall; cheap when idle.
open_debug_window(host)  Overview, threads, compat env, render stats, errors,
               stalls, open windows; copy report / open logs / clear logs.
"""
from __future__ import annotations

import os
import platform
import sys
import threading
import time
import traceback
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QTabWidget, QTextEdit,
                             QVBoxLayout)


def logs_dir() -> Path:
    try:
        import groovebox_paths
        return Path(groovebox_paths.logs_dir())
    except Exception:
        p = Path.home() / ".groovebox" / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p


def _tail(path: Path, n=12000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-n:]
    except Exception:
        return "(empty)"


class StallMonitor(QObject):
    def __init__(self, parent=None, threshold=0.5):
        super().__init__(parent)
        self.threshold = float(os.environ.get("GROOVEBOX_STALL_SECONDS", threshold) or threshold)
        self.main_ident = threading.main_thread().ident
        self.beat = time.monotonic()
        self.stalls = 0
        self.longest = 0.0
        self._in_stall = False
        self._stop = threading.Event()
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._heartbeat)
        self._timer.start()
        self._th = threading.Thread(target=self._watch, name="groovebox-stall-watchdog", daemon=True)
        self._th.start()

    def _heartbeat(self):
        now = time.monotonic()
        gap = now - self.beat
        self.beat = now
        if self._in_stall:
            self._in_stall = False
            self.longest = max(self.longest, gap)
            self._write(f"   ↳ window answered again after {gap:.2f} s\n")

    def _write(self, text):
        try:
            with open(logs_dir() / "stalls.log", "a", encoding="utf-8") as fh:
                fh.write(text)
        except Exception:
            pass

    def _watch(self):
        while not self._stop.wait(0.1):
            lag = time.monotonic() - self.beat
            if lag < self.threshold or self._in_stall:
                continue
            self._in_stall = True
            self.stalls += 1
            frames = sys._current_frames()
            out = [f"\n==== STALL #{self.stalls} · {time.strftime('%Y-%m-%d %H:%M:%S')} · window frozen > {lag:.2f} s ====\n",
                   "-- main (GUI) thread --\n"]
            mf = frames.get(self.main_ident)
            out.extend(traceback.format_stack(mf) if mf is not None else ["(no frame)\n"])
            for th in threading.enumerate():
                if th.ident in (self.main_ident, threading.get_ident()) or th.ident not in frames:
                    continue
                if not th.name.startswith(("groovebox", "ThreadPool", "Thread-")):
                    continue
                out.append(f"-- {th.name} --\n")
                out.extend(traceback.format_stack(frames[th.ident])[-6:])
            self._write("".join(out))

    def stop(self):
        self._stop.set()
        self._timer.stop()


def install(app_host=None):
    """Start the freeze detector once per process (GROOVEBOX_STALL_MONITOR=0 disables)."""
    if os.environ.get("GROOVEBOX_STALL_MONITOR", "1") == "0":
        return None
    app = QApplication.instance()
    mon = getattr(app, "_gb_stall_monitor", None) if app is not None else None
    if mon is None and app is not None:
        mon = StallMonitor(app)
        app._gb_stall_monitor = mon
    return mon


def report(host=None) -> str:
    L = [f"Groovebox debug report · {time.strftime('%Y-%m-%d %H:%M:%S')}",
         f"Python {sys.version.split()[0]} · {platform.platform()} · frozen={getattr(sys, 'frozen', False)}"]
    try:
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        L.append(f"Qt {QT_VERSION_STR} · PyQt {PYQT_VERSION_STR} · platform {QGuiApplication.platformName()}")
    except Exception:
        pass
    try:
        import groovebox_paths
        L.append(f"data dir: {groovebox_paths.base_dir()}")
    except Exception:
        pass
    L.append(f"CPU threads: {os.cpu_count()} · live Python threads: {threading.active_count()}")
    for th in threading.enumerate():
        L.append(f"   · {th.name}{' (daemon)' if th.daemon else ''}")
    try:
        import compat_settings as cs
        s = cs.load()
        L.append("compat: " + ", ".join(f"{k}={v}" for k, v in s.items()))
        L.append("compat env: " + ", ".join(f"{k}={os.environ.get(k)}" for k in cs._MANAGED if os.environ.get(k)))
    except Exception:
        pass
    for k in sorted(os.environ):
        if k.startswith(("GROOVEBOX_", "QT_")):
            L.append(f"env {k}={os.environ[k]}")
    mon = getattr(QApplication.instance(), "_gb_stall_monitor", None)
    if mon is not None:
        L.append(f"freeze detector: {mon.stalls} stall(s), longest {mon.longest:.2f} s, threshold {mon.threshold:.2f} s")
    if host is not None:
        st = getattr(host, "_render_pipeline_stats", None)
        if st:
            L.append("render pipeline: " + ", ".join(f"{k}={v}" for k, v in dict(st).items()))
        for attr in ("is_playing", "_audio_owner", "_preferred_audio_output_name", "master_volume", "_keychart_enabled"):
            L.append(f"host.{attr} = {getattr(host, attr, None)!r}")
        try:
            L.append(f"instruments: {len(host.instrument_names_48)} · playlist rows: {len(host.master_playlist_data or [])}")
        except Exception:
            pass
    try:
        L.append("open windows: " + ", ".join(w.windowTitle() or w.__class__.__name__ for w in QApplication.topLevelWidgets()
                                             if w.isVisible()))
    except Exception:
        pass
    return "\n".join(L)


def open_debug_window(host=None):
    dlg = QDialog(host)
    dlg.setWindowTitle("🐞 Debug")
    dlg.resize(900, 640)
    lay = QVBoxLayout(dlg)
    tabs = QTabWidget(); lay.addWidget(tabs, 1)
    views = {}
    for name in ("Overview", "Errors", "Freezes (stalls)", "Audio check"):
        t = QTextEdit(); t.setReadOnly(True); t.setStyleSheet("font-family: monospace; font-size: 9pt;")
        tabs.addTab(t, name); views[name] = t

    def refresh():
        views["Overview"].setPlainText(report(host))
        views["Errors"].setPlainText(_tail(logs_dir() / "errors.log"))
        views["Freezes (stalls)"].setPlainText(_tail(logs_dir() / "stalls.log") +
                                               "\n\nEach entry shows the exact code line the window was stuck on.")
        checks = sorted(logs_dir().glob("audio-check-*.txt"))
        views["Audio check"].setPlainText(_tail(checks[-1]) if checks else "Run 🩺 Audio check to create a report.")
    row = QHBoxLayout()
    for text, fn in (("↻ Refresh", refresh),
                     ("📋 Copy report", lambda: QGuiApplication.clipboard().setText(report(host) + "\n\n" + _tail(logs_dir() / "stalls.log", 6000))),
                     ("📂 Open logs folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir())))),
                     ("🧹 Clear stall log", lambda: ((logs_dir() / "stalls.log").write_text("", encoding="utf-8"), refresh()))):
        b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
    chk = QCheckBox("Freeze detector")
    chk.setChecked(getattr(QApplication.instance(), "_gb_stall_monitor", None) is not None)
    def _toggle(on):
        app = QApplication.instance()
        mon = getattr(app, "_gb_stall_monitor", None)
        if on and mon is None:
            install(host)
        elif not on and mon is not None:
            mon.stop(); app._gb_stall_monitor = None
    chk.toggled.connect(_toggle)
    row.addWidget(chk); row.addStretch(1)
    lay.addLayout(row)
    lay.addWidget(QLabel("Freeze detector: when the window stops answering for more than half a second, the line it was stuck on "
                         "is written to logs/stalls.log. Send that file with a bug report."))
    refresh()
    dlg.show(); dlg.raise_()
    return dlg
