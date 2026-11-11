"""ext_windows.py — GROOVEBOX_R32_EXTERNAL_WINDOWS_20261110

Windows owned by *other processes* that Groovebox starts (the file media player = mpv / VLC /
ffplay, decks, stream viewers) cannot be Qt widgets, so the windows bar never listed them.
Each one is registered here as a lightweight proxy that answers the same calls the bar makes on
a real window (windowTitle / isVisible / isMinimized / show / showNormal / raise_ /
activateWindow / close), so it appears in the bar and in Arrange like any other window.

  * raise / focus: mpv IPC  ontop=yes → ontop=no  (puts it above every window, then normal)
  * close: mpv IPC "quit", otherwise terminate the process
  * entries disappear when the process exits (polled lazily by the bar, no timer)
"""
from __future__ import annotations

import json
import os
import socket
import threading
import weakref

from PyQt6.QtCore import QObject, QTimer, Qt

_REG: "list[ExternalWindow]" = []
_LOCK = threading.Lock()


def _ipc(path, cmd, timeout=0.25):
    if not path or not os.path.exists(path):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(timeout)
        s.connect(path); s.sendall((json.dumps({"command": cmd}) + "\n").encode()); s.close()
        return True
    except Exception:
        return False


class ExternalWindow(QObject):
    def __init__(self, proc, title, ipc_path=None, kind="player"):
        super().__init__()
        self.proc = proc
        self._title = str(title or "External window")
        self.ipc_path = ipc_path
        self.kind = kind
        self.setProperty("grooveboxExternalProcessWindow", True)

    # the subset of the QWidget API the windows bar / manager use
    def alive(self):
        try:
            return self.proc is not None and self.proc.poll() is None
        except Exception:
            return False

    def windowTitle(self):
        return "↗ " + self._title

    def setTitle(self, t):
        self._title = str(t)

    def isVisible(self):
        return self.alive()

    def isMinimized(self):
        return False

    def isWindow(self):
        return True

    def windowHandle(self):
        return None

    def windowState(self):
        return Qt.WindowState.WindowNoState

    def setWindowState(self, *_a):
        pass

    def raise_(self):
        if _ipc(self.ipc_path, ["set_property", "ontop", True]):
            QTimer.singleShot(250, lambda: _ipc(self.ipc_path, ["set_property", "ontop", False]))

    show = showNormal = activateWindow = raise_

    def hide(self):
        _ipc(self.ipc_path, ["set_property", "pause", True])

    def close(self):
        if not _ipc(self.ipc_path, ["quit"]):
            try:
                self.proc.terminate()
            except Exception:
                pass
        unregister(self)
        return True

    def width(self):
        return 640

    def height(self):
        return 360


def register(proc, title, ipc_path=None, kind="player"):
    """Track an external window process; returns the proxy (kept until the process exits)."""
    if proc is None:
        return None
    w = ExternalWindow(proc, title, ipc_path, kind)
    with _LOCK:
        _REG[:] = [x for x in _REG if x.alive()]
        _REG.append(w)
    _notify()
    _ensure_reaper()
    return w


_REAPER = {"t": None, "n": 0}


def _ensure_reaper():
    """While any external window is tracked, check every 1.5 s whether one exited (cheap poll())."""
    if _REAPER["t"] is not None:
        return
    t = QTimer(); t.setInterval(1500)

    def tick():
        n = len(windows())
        if n != _REAPER["n"]:
            _REAPER["n"] = n; _notify()
        if n == 0:
            t.stop(); _REAPER["t"] = None
    t.timeout.connect(tick); t.start(); _REAPER["t"] = t; _REAPER["n"] = len(_REG)


def unregister(w):
    with _LOCK:
        if w in _REG:
            _REG.remove(w)
    _notify()


def windows():
    with _LOCK:
        _REG[:] = [x for x in _REG if x.alive()]
        return list(_REG)


_listeners: "list[weakref.ref]" = []


def on_change(fn):
    try:
        _listeners.append(weakref.WeakMethod(fn))
    except TypeError:
        _listeners.append(lambda f=fn: f)


def _notify():
    for r in list(_listeners):
        f = r()
        if f is None:
            continue
        try:
            QTimer.singleShot(0, f)
        except Exception:
            pass
