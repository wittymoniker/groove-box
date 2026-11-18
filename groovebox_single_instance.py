"""Single-instance handoff for normal Groovebox GUI launches.

A second desktop/ISO launch sends ACTIVATE to the first process and exits before
constructing QApplication's main window. Helper/game dispatch remains upstream
of this module and is intentionally unaffected.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


def _server_name(root: str | os.PathLike = "") -> str:
    """Stable per-user/per-desktop-session endpoint, independent of install path.

    A desktop icon, Apps & Scripts entry, direct script invocation, or alternate
    release directory must all reach the same running Groovebox window. Session
    scoping avoids stealing focus across separate logged-in graphical sessions.
    """
    uid = str(os.getuid()) if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
    session_parts = [
        os.environ.get("XDG_SESSION_ID", ""),
        os.environ.get("XDG_RUNTIME_DIR", ""),
        os.environ.get("WAYLAND_DISPLAY", ""),
        os.environ.get("DISPLAY", ""),
    ]
    # If the graphical session variables are absent (some launchers do not pass
    # them through), the per-user endpoint remains stable rather than forking by
    # current working directory / installation path.
    identity = "|".join([uid] + [p for p in session_parts if p])
    digest = hashlib.sha256(identity.encode("utf-8", "replace")).hexdigest()[:24]
    safe_uid = "".join(ch for ch in uid if ch.isalnum())[:20] or "user"
    return f"matgroovebox-{safe_uid}-{digest}"


class SingleInstanceGuard:
    def __init__(self, app, server, name: str):
        self.app = app
        self.server = server
        self.name = name
        self._main_window = None
        self._sockets = set()
        self._pending_activation = False
        server.newConnection.connect(self._accept_connections)

    def set_main_window(self, window) -> None:
        self._main_window = window
        if self._pending_activation:
            self._pending_activation = False
            self.activate()

    def _accept_connections(self) -> None:
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            if sock is None:
                continue
            self._sockets.add(sock)
            sock.readyRead.connect(lambda s=sock: self._read_request(s))
            sock.disconnected.connect(lambda s=sock: self._drop_socket(s))
            # A client may have written before nextPendingConnection returned.
            self._read_request(sock)

    def _drop_socket(self, sock) -> None:
        self._sockets.discard(sock)
        try:
            sock.deleteLater()
        except Exception:
            pass

    def _read_request(self, sock) -> None:
        try:
            payload = bytes(sock.readAll())
        except Exception:
            payload = b""
        if b"ACTIVATE" in payload:
            self.activate()

    def activate(self) -> None:
        window = self._main_window
        if window is None:
            self._pending_activation = True
            return

        def show_existing():
            try:
                if window.isMinimized():
                    window.showNormal()
                else:
                    window.show()
                window.raise_()
                window.activateWindow()
            except Exception:
                pass

        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, show_existing)
        except Exception:
            show_existing()


def acquire_or_activate(app, root: str | os.PathLike):
    """Return a live guard for the primary process, or None in a second launch."""
    from PyQt6.QtCore import QLockFile
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket

    name = _server_name(root)

    def notify_existing(timeout_ms=500) -> bool:
        sock = QLocalSocket()
        sock.connectToServer(name)
        if not sock.waitForConnected(timeout_ms):
            sock.abort()
            return False
        sock.write(b"ACTIVATE\n")
        sock.waitForBytesWritten(timeout_ms)
        sock.disconnectFromServer()
        return True

    # Fast path: the normal primary server already exists.
    if notify_existing(300):
        return None

    # Serialize stale-endpoint cleanup and listen() so simultaneous launches
    # cannot remove a live server created by the other contender.
    lock_path = Path(tempfile.gettempdir()) / (name + ".lock")
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(0)
    if not lock.tryLock(1500):
        if notify_existing(900):
            return None
        # Do not create a second UI if another process may still be claiming
        # the endpoint. Fail visibly rather than silently duplicating state.
        raise RuntimeError("another Groovebox launch is initializing; retry in a moment")

    try:
        if notify_existing(300):
            return None
        QLocalServer.removeServer(name)  # only while holding the startup lock
        server = QLocalServer(app)
        if not server.listen(name):
            if notify_existing(700):
                return None
            raise RuntimeError(f"could not establish Groovebox single-instance endpoint: {server.errorString()}")
        return SingleInstanceGuard(app, server, name)
    finally:
        lock.unlock()
