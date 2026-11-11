"""WINDOW_BAR_R31: export progress + quick actions on the window strip, and a UI-stall watchdog.

ExportsButton   "⬇ Exports" dropdown: live progress of every running / queued export job, recent finished
                exports with "Open folder", the Export Jobs window, the exports folder, leftover parts.
ActionsButton   "⚡ Actions": lock (PIN), Live Player, Export Jobs, Render Queue, Save.
UiWatchdog      a background thread watches a 100 ms UI heartbeat. While the UI thread is stalled nothing
                in Qt can repaint (every window shares that thread), so the watchdog records where the UI
                thread was stuck and the bar reports it the moment painting resumes.
"""
from __future__ import annotations

import os
import sys
import threading
import time

from PyQt6.QtCore import QTimer, QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QToolButton, QMenu, QLabel


def _open_folder(path):
    try:
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    except Exception:
        pass


class ExportsButton(QToolButton):
    def __init__(self, main_ref, parent=None):
        super().__init__(parent)
        self._main_ref = main_ref            # callable -> main window or None
        self._sch = None
        self.setText("⬇ Exports")
        self.setToolTip("Export jobs: live progress, finished files, open their folder.")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._menu = QMenu(self)
        self._menu.aboutToShow.connect(self._fill)
        self.setMenu(self._menu)
        self._poll = QTimer(self); self._poll.setInterval(1000); self._poll.timeout.connect(self._attach)
        self._poll.start()

    def _main(self):
        try:
            return self._main_ref()
        except Exception:
            return None

    def _attach(self):
        main = self._main()
        sch = getattr(main, "_export_scheduler_obj", None) if main is not None else None
        if sch is not None and sch is not self._sch:
            self._sch = sch
            sch.changed.connect(lambda *_: self._update_text())
            self._update_text()

    def _update_text(self):
        sch = self._sch
        if sch is None:
            return
        running = [j for j in sch.jobs if j.state == "running"]
        queued = [j for j in sch.jobs if j.state == "queued"]
        if running:
            pct = int(sum(j.progress for j in running) / len(running))
            self.setText(f"⬇ {len(running)} running · {pct}%" + (f" · +{len(queued)}" if queued else ""))
            self.setStyleSheet("QToolButton{color:#7fffd4;font-weight:800;}")
        elif queued:
            self.setText(f"⬇ {len(queued)} queued"); self.setStyleSheet("QToolButton{color:#f2d17a;}")
        else:
            failed = sum(1 for j in sch.jobs if j.state == "failed")
            self.setText("⬇ Exports" + (f" · {failed} failed" if failed else ""))
            self.setStyleSheet("QToolButton{color:#ff8fa3;}" if failed else "")

    def _fill(self):
        m = self._menu
        m.clear()
        main = self._main()
        sch = self._sch
        if sch is not None and sch.jobs:
            active = [j for j in sch.jobs if j.state in ("running", "queued")]
            done = [j for j in sch.jobs if j.state not in ("running", "queued")][-10:]
            if active:
                m.addSection("In progress")
                for j in active:
                    a = m.addAction(f"{j.label} · {j.state} {j.progress}% · {j.message[:40]}")
                    a.setEnabled(False)
            if done:
                m.addSection("Finished")
                for j in reversed(done):
                    path = str(j.result.get("file_path") or j.out_file or "")
                    icon = {"done": "✓", "failed": "✗", "cancelled": "–"}.get(j.state, "·")
                    sub = m.addMenu(f"{icon} {os.path.basename(path) or j.label}")
                    sub.addAction("Open folder", lambda p=path: _open_folder(os.path.dirname(p)))
                    if j.state == "done" and path and os.path.isfile(path):
                        sub.addAction("Open file", lambda p=path: _open_folder(p))
                    sub.addAction(j.message[:80]).setEnabled(False)
            m.addSeparator()
        m.addAction("📋 Export Jobs window…", lambda: main.show_export_jobs() if main is not None else None)
        for label, fn in (("📁 Audio exports folder", "_audio_exports_dir"), ("📁 Video exports folder", "_video_exports_dir"),
                          ("📁 All exports folder", "_exports_dir")):
            m.addAction(label, lambda f=fn: _open_folder(getattr(main, f)()) if main is not None else None)
        if sch is not None:
            def _parts():
                w = main.show_export_jobs()
                if hasattr(w, "_leftover_parts"):
                    w._leftover_parts()
            m.addAction("🧹 Leftover parts…", _parts)


class ActionsButton(QToolButton):
    def __init__(self, main_ref, parent=None):
        super().__init__(parent)
        self._main_ref = main_ref
        self.setText("⚡ Actions")
        self.setToolTip("Quick actions")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(self)
        for label, method in (("🔒 Lock now (PIN)", "lock_with_pin"), ("🎬 Live Player", "_open_live_player_bar"),
                              ("📁 File Manager", "_open_file_manager_from_actions"),
                              ("▤ Window Manager", "_open_window_manager_from_actions"),
                              ("📋 Export Jobs", "show_export_jobs"), ("🗂 Render Queue", "render_queue_dialog"),
                              ("💾 Save project…", "save_project_dialog"), ("🧬 Spectral & Pixel Seeds…", "open_seed_canonical_window")):
            m.addAction(label, lambda mm=method: self._call(mm))
        self.setMenu(m)

    def _call(self, method):
        main = self._main_ref()
        if main is None:
            return
        if method == "_open_live_player_bar":
            try:
                import live_player
                live_player.open_live_player(main)
            except Exception:
                pass
            return
        if method in ("_open_file_manager_from_actions", "_open_window_manager_from_actions"):
            try:
                label = "_open_file_manager" if method == "_open_file_manager_from_actions" else "▤ Open Windows"
                if method == "_open_file_manager_from_actions":
                    main._perf_call(label)
                else:
                    main._open_performance_tab(label)
            except Exception as exc:
                print(f"[Actions] {method}: {exc}")
            return
        fn = getattr(main, method, None)
        if callable(fn):
            try:
                fn()
            except TypeError:
                pass


class UiWatchdog:
    """Records UI-thread stalls (where the UI thread was stuck) and reports them once painting resumes."""
    THRESHOLD = 0.8

    def __init__(self, host):
        self.host = host
        self._beat = time.monotonic()
        self._main_ident = threading.main_thread().ident
        self._stall_start = None
        self._stall_where = ""
        self.last_report = None              # (seconds, where, wall time)
        self.listeners = []
        self._timer = QTimer(host); self._timer.setInterval(100); self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._t = threading.Thread(target=self._watch, name="ui-watchdog", daemon=True)
        self._t.start()

    def _tick(self):
        now = time.monotonic()
        if self._stall_start is not None:
            dur = now - self._stall_start
            where = self._stall_where
            self._stall_start = None
            self.last_report = (dur, where, time.strftime("%H:%M:%S"))
            print(f"[UI] busy {dur:.1f} s · {where}")
            for cb in list(self.listeners):
                try:
                    cb(dur, where)
                except Exception:
                    pass
        self._beat = now

    def _where(self):
        try:
            frame = sys._current_frames().get(self._main_ident)
            best = ""
            while frame is not None:
                code = frame.f_code
                fn = os.path.basename(code.co_filename)
                if fn not in ("threading.py", "__init__.py") and not code.co_name.startswith("<"):
                    best = f"{code.co_name} ({fn}:{frame.f_lineno})"
                    if fn not in ("qt_painting.py", "ui_runtime.py"):
                        return best
                frame = frame.f_back
            return best or "Qt event processing"
        except Exception:
            return "unknown"

    def _watch(self):
        while True:
            time.sleep(0.2)
            gap = time.monotonic() - self._beat
            if gap > self.THRESHOLD and self._stall_start is None:
                self._stall_start = self._beat
                self._stall_where = self._where()


class StallLabel(QLabel):
    def __init__(self, watchdog, parent=None):
        super().__init__("", parent)
        self.setStyleSheet("color:#ffb070;font-weight:700;")
        self._clear = QTimer(self); self._clear.setSingleShot(True); self._clear.setInterval(8000)
        self._clear.timeout.connect(lambda: self.setText(""))
        if watchdog is not None:
            watchdog.listeners.append(self._show)

    def _show(self, dur, where):
        self.setText(f"⚠ UI was busy {dur:.1f} s · {where[:48]}")
        self.setToolTip(f"The window could not repaint for {dur:.1f} s while running {where}.")
        self._clear.start()
