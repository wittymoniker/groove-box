"""main_window_lock.py — GROOVEBOX_R32_MAIN_WINDOW_LOCK_20261110

Once launched, the main window stays put:
  * it cannot be minimised: no minimise button, and any minimise request (WM keybind, taskbar,
    window_manager "minimise all") is turned back into the previous state at once;
  * it does not move: the geometry settles for ~2 s after first show (WM placement, HiDPI),
    then it is locked and any move is undone;
  * the lock follows the *screen* it is on, so a monitor hot-plug or a resolution change re-anchors
    instead of fighting the compositor;
  * it is the LOWEST window layer: no Groovebox window can end up hidden behind it
    (Qt bottom-layer hint on X11 / Windows; labwc ToggleAlwaysOnBottom rule on sOS; and every
    time Main is activated the other visible Groovebox windows are raised back above it);
  * mirroring / broadcasting the main screen to additional hardware is unaffected
    (that is an output-level copy, not a window move).
Set GROOVEBOX_MAIN_WINDOW_UNLOCKED=1 to restore the old behaviour.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt


class _Lock(QObject):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.pos = None
        self.state = Qt.WindowState.WindowNoState
        self._busy = False
        win.setProperty("grooveboxMainLocked", True)
        try:
            win.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False)
            if os.environ.get("XDG_SESSION_TYPE") != "wayland" and not os.environ.get("WAYLAND_DISPLAY"):
                win.setWindowFlag(Qt.WindowType.WindowStaysOnBottomHint, True)
        except Exception:
            pass
        QTimer.singleShot(2000, self.anchor)
        try:
            from PyQt6.QtGui import QGuiApplication
            QGuiApplication.instance().screenAdded.connect(lambda *_: QTimer.singleShot(1500, self.anchor))
            QGuiApplication.instance().screenRemoved.connect(lambda *_: QTimer.singleShot(1500, self.anchor))
        except Exception:
            pass

    def anchor(self):
        try:
            if self.win.isVisible() and not self.win.isMinimized():
                self.pos = self.win.pos()
                self.state = self.win.windowState() & ~Qt.WindowState.WindowMinimized
                scr = self.win.screen()
                if scr is not None:
                    try:
                        scr.geometryChanged.connect(lambda *_: QTimer.singleShot(800, self.anchor), Qt.ConnectionType.UniqueConnection)
                    except Exception:
                        pass
        except RuntimeError:
            pass

    def _unminimise(self):
        w = self.win
        try:
            st = self.state
            if st & Qt.WindowState.WindowFullScreen:
                w.showFullScreen()
            elif st & Qt.WindowState.WindowMaximized:
                w.showMaximized()
            else:
                w.showNormal()
            w.raise_(); w.activateWindow()
        except RuntimeError:
            pass

    def _restore_pos(self):
        if self.pos is None or self._busy:
            return
        try:
            if self.win.windowState() & (Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen):
                return
            if self.win.pos() != self.pos:
                self._busy = True
                self.win.move(self.pos)
        except RuntimeError:
            pass
        finally:
            QTimer.singleShot(50, lambda: setattr(self, "_busy", False))

    def raise_others(self):
        """Put every other visible top-level Groovebox window back above Main (focus stays on Main)."""
        try:
            from PyQt6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if w is self.win or not w.isVisible() or w.isMinimized():
                    continue
                if w.windowType() in (Qt.WindowType.Popup, Qt.WindowType.ToolTip, Qt.WindowType.SplashScreen):
                    continue
                w.raise_()
        except Exception:
            pass

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Type.WindowActivate:
            QTimer.singleShot(0, self.raise_others)
        if t == QEvent.Type.WindowStateChange:
            try:
                if self.win.windowState() & Qt.WindowState.WindowMinimized:
                    QTimer.singleShot(0, self._unminimise)
                elif self.pos is not None:
                    self.state = self.win.windowState()
            except RuntimeError:
                pass
        elif t == QEvent.Type.Move and self.pos is not None and not self._busy:
            QTimer.singleShot(0, self._restore_pos)
        return False


def install(win):
    if os.environ.get("GROOVEBOX_MAIN_WINDOW_UNLOCKED") == "1":
        return None
    if getattr(win, "_r32_main_lock", None) is not None:
        return win._r32_main_lock
    lock = _Lock(win)
    win.installEventFilter(lock)
    win._r32_main_lock = lock
    return lock
