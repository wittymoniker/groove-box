"""GROOVEBOX_R23R_PROJECT_TABS_20261103 — several projects open as main-window tabs.

A tab bar sits at the top of every main window (one Groovebox window per project, only the active
one is shown, at the same position and size). How many tabs may be open is computed by the
memory manager from the RAM budget, the sCode pool's real size and the measured footprint of a
project (memory_manager.max_tabs). Switching tabs parks the project you leave: its playback stops,
a safety autosave is written, and its large buffers move to the SSD swap — so RAM holds only the
project you are working on.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QMessageBox, QPushButton, QTabBar, QToolBar, QFileDialog

import memory_manager as mm


class ProjectTabs:
    def __init__(self):
        self.windows = []
        self.active = None
        self._bars = {}

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def name(win):
        p = str(getattr(win, "_current_project_path", "") or "")
        return os.path.splitext(os.path.basename(p))[0] if p else "Untitled"

    @staticmethod
    def pool_bytes(win):
        opt = getattr(win, "_scode_optimizer", None)
        try:
            return int(opt.pool_stats().get("bytes", 0)) if opt is not None and hasattr(opt, "pool_stats") else 0
        except Exception:
            return 0

    def max_tabs(self):
        return mm.manager().max_tabs(max(1, len(self.windows)), self.pool_bytes(self.active) if self.active else 0)

    # ---------------------------------------------------------------- UI
    def attach(self, win):
        if win in self.windows:
            return
        self.windows.append(win)
        if self.active is None:
            self.active = win
        tb = QToolBar("Projects", win)
        tb.setObjectName("projectTabsToolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea | Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea)
        bar = QTabBar(tb)
        bar.setExpanding(False); bar.setMovable(False); bar.setDocumentMode(True)
        bar.currentChanged.connect(lambda i, b=bar: self._bar_switch(b, i))
        b_new = QPushButton("＋ New"); b_new.setToolTip("Open a new, empty project in another tab")
        b_open = QPushButton("📂 Open in tab…"); b_open.setToolTip("Open a project file in a new tab")
        b_close = QPushButton("✕ Close tab")
        b_new.clicked.connect(lambda: self.new_tab())
        b_open.clicked.connect(lambda w=win: self.open_in_tab(w))
        b_close.clicked.connect(lambda w=win: self.close_tab(w))
        lbl = QLabel(""); lbl.setStyleSheet("color:#9fb3c8; padding-left:10px;")
        tb.addWidget(QLabel(" 🗂 "))
        tb.addWidget(bar); tb.addWidget(b_new); tb.addWidget(b_open); tb.addWidget(b_close); tb.addWidget(lbl)
        win.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        def _proj_side_menu(pos, t=tb, w=win):
            from PyQt6.QtWidgets import QMenu as _QM
            m = _QM(t)
            def _move(area, name, tb=t, ww=w):
                ww.addToolBar(area, tb)
                try:
                    import compat_settings as _cs
                    s = _cs.load(); s["projects_bar_side"] = name.lower(); _cs.save(s)
                except Exception:
                    pass
            for name, area in (("Top", Qt.ToolBarArea.TopToolBarArea), ("Left", Qt.ToolBarArea.LeftToolBarArea), ("Right", Qt.ToolBarArea.RightToolBarArea), ("Bottom", Qt.ToolBarArea.BottomToolBarArea)):
                m.addAction(name, lambda a=area, n=name: _move(a, n))
            m.exec(t.mapToGlobal(pos))
        tb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tb.customContextMenuRequested.connect(_proj_side_menu)
        self._bars[id(win)] = (bar, lbl, tb)
        t = QTimer(win); t.setInterval(3000); t.timeout.connect(self.refresh_status); t.start()
        win._project_tabs_timer = t
        self.refresh()

    def refresh(self):
        for win in list(self.windows):
            rec = self._bars.get(id(win))
            if rec is None:
                continue
            bar = rec[0]
            bar.blockSignals(True)
            while bar.count():
                bar.removeTab(0)
            for w in self.windows:
                bar.addTab(("● " if w is self.active else "") + self.name(w))
            try:
                bar.setCurrentIndex(self.windows.index(self.active))
            except ValueError:
                pass
            bar.blockSignals(False)
        self.refresh_status()

    def refresh_status(self):
        try:
            st = mm.manager().status(self.pool_bytes(self.active) if self.active else 0, max(1, len(self.windows)))
            txt = (f"tabs {len(self.windows)}/{st['max_tabs']} · RAM free {mm.fmt_bytes(st['ram_avail'])} of "
                   f"{mm.fmt_bytes(st['ram_total'])} · buffers {mm.fmt_bytes(st['tracked'])} (budget "
                   f"{mm.fmt_bytes(st['budget'])}) · SSD swap {mm.fmt_bytes(st['swap_used'])}/{mm.fmt_bytes(st['swap_capacity'])}")
        except Exception:
            txt = ""
        for win in list(self.windows):
            rec = self._bars.get(id(win))
            if rec is not None:
                try:
                    rec[1].setText(txt)
                except RuntimeError:
                    pass

    # ---------------------------------------------------------------- actions
    def _bar_switch(self, bar, i):
        if 0 <= i < len(self.windows):
            self.switch(self.windows[i])

    def switch(self, target):
        old = self.active
        if target is old or target not in self.windows:
            return
        geo = old.geometry() if old is not None else None
        if old is not None:
            try:
                if getattr(old, "is_playing", False):
                    old.stop_playback()
            except Exception:
                pass
            try:
                lp = getattr(old, "_live_player_window", None)
                if lp is not None:
                    lp.stop()
            except Exception:
                pass
        self.active = target
        if geo is not None:
            target.setGeometry(geo)
        target.show(); target.raise_(); target.activateWindow()
        if old is not None:
            old.hide()
            try:   # the project you leave: safety autosave, then its buffers move to the SSD swap
                old._memory_safety_autosave()
                freed = mm.manager().park(old)
                if freed:
                    old._memory_note_parked(freed)
            except Exception:
                pass
        self.refresh()

    def new_tab(self, path=None):
        mx = self.max_tabs()
        if len(self.windows) >= mx:
            QMessageBox.information(self.active, "Projects",
                                    f"Memory allows {mx} open project(s) right now (RAM budget, sCode pool and the "
                                    "measured size of a project). Close a tab or free some RAM, then try again.")
            return None
        import groovebox as gb
        rss0 = mm.process_rss()
        win = gb.MathematiciansGrooveboxApp()
        grow = mm.process_rss() - rss0
        M = mm.manager()
        if grow > 0:
            M.per_project_bytes = max(int(M.per_project_bytes or 0), int(grow))
        for fn in ("_install_background_prerender", "_install_memory_manager", "_install_keychart", "_install_hardware_follow"):
            try:
                getattr(win, fn)()
            except Exception:
                pass
        self.attach(win)
        if path:
            try:
                win.open_project_path(path)
            except Exception as exc:
                QMessageBox.warning(win, "Open project", str(exc))
        self.switch(win)
        return win

    def open_in_tab(self, parent):
        try:
            d = parent._projects_dir()
        except Exception:
            d = ""
        path, _ = QFileDialog.getOpenFileName(parent, "Open project in a new tab", d,
                                              "Mathematician's Groovebox Composition (*.MCC);;All files (*)")
        if path:
            self.new_tab(path)

    def close_tab(self, win):
        if len(self.windows) <= 1:
            QMessageBox.information(win, "Projects", "This is the only open project — use Quit to close Groovebox.")
            return
        r = QMessageBox.question(win, "Close project tab",
                                 f"Close “{self.name(win)}”? A safety autosave is written first.",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                 QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            win._memory_safety_autosave()
        except Exception:
            pass
        try:
            if getattr(win, "is_playing", False):
                win.stop_playback()
        except Exception:
            pass
        idx = self.windows.index(win)
        self.windows.remove(win)
        self._bars.pop(id(win), None)
        mm.manager().unregister_owner(win)
        try:
            mm.manager().swap_store().drop_prefix(f"{id(win)}:")
        except Exception:
            pass
        if self.active is win:
            self.active = None
            self.switch(self.windows[max(0, idx - 1)])
        win._closing_as_tab = True
        win.hide()
        win.deleteLater()
        self.refresh()


_TABS = None


def tabs():
    global _TABS
    if _TABS is None:
        _TABS = ProjectTabs()
    return _TABS
