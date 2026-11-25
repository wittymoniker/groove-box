"""Edit Together presence overlay — per-peer screen tiles on the local workspace.

R135: optional GUI overlay that shows every active Edit Together / Nearby peer as a
tile. Each tile can show a name, role (owner/member), last activity, and — when the
peer publishes a frame — a downscaled screen thumbnail. Tiles are mouse-transparent
so they never steal edits from the working interface.

Integrates with:
  * live_edit_ui.LiveEditController  (session / pending)
  * nearby_groovebox.NearbyGrooveboxService.coedit
  * groovebox_runtime.collaboration.OperationLog (deterministic merge remains source of truth)

This module does not replace Live Edit section sync; it only visualizes presence.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
    from PyQt6.QtGui import QColor, QPainter, QPen, QFont, QPixmap, QImage
    from PyQt6.QtWidgets import QWidget, QApplication
except Exception:  # headless / import-time safety
    QWidget = object  # type: ignore

_STATE: Dict[str, Any] = {"overlay": None, "on": False, "host": None}


def _peers_from_host(host) -> List[Dict[str, Any]]:
    """Collect peer presence dicts from Nearby / CoEdit without raising."""
    peers: List[Dict[str, Any]] = []
    try:
        svc = getattr(host, "_nearby_share_service", None)
        if svc is None:
            return peers
        # Prefer explicit presence API when present.
        snap = getattr(svc, "presence_snapshot", None)
        if callable(snap):
            raw = snap() or []
            for row in raw:
                if isinstance(row, dict):
                    peers.append(row)
            if peers:
                return peers
        coedit = getattr(svc, "coedit", None)
        session = getattr(coedit, "session", None) if coedit is not None else None
        if session is not None and getattr(session, "active", False):
            members = getattr(session, "members", None) or getattr(session, "peers", None) or []
            owner = getattr(session, "owner", None) or getattr(session, "owner_id", "")
            for m in members:
                if isinstance(m, dict):
                    peers.append(m)
                else:
                    name = str(getattr(m, "name", None) or getattr(m, "id", m) or "?")
                    peers.append({
                        "id": str(getattr(m, "id", name)),
                        "name": name,
                        "role": "owner" if str(getattr(m, "id", "")) == str(owner) else "member",
                        "last_seen": float(getattr(m, "last_seen", time.time())),
                        "thumbnail": getattr(m, "thumbnail", None),
                    })
            if not peers and owner:
                peers.append({"id": str(owner), "name": str(owner), "role": "owner",
                              "last_seen": time.time(), "thumbnail": None})
        # Nearby discovery list (not yet in a session) as dim tiles.
        nearby = getattr(svc, "peers", None) or getattr(svc, "discovered", None) or []
        if callable(nearby):
            nearby = nearby()
        for m in nearby or []:
            if isinstance(m, dict):
                pid = str(m.get("id") or m.get("name") or "")
                if pid and not any(str(p.get("id")) == pid for p in peers):
                    peers.append({
                        "id": pid,
                        "name": str(m.get("name") or pid),
                        "role": "nearby",
                        "last_seen": float(m.get("last_seen") or time.time()),
                        "thumbnail": m.get("thumbnail"),
                    })
    except Exception:
        pass
    return peers


class PresenceOverlay(QWidget):
    """Mouse-transparent peer-tile strip docked to the host window."""

    TILE_W = 168
    TILE_H = 110
    MARGIN = 10

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.peers: List[Dict[str, Any]] = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setObjectName("EditTogetherPresenceOverlay")
        self._timer = QTimer(self)
        self._timer.setInterval(700)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.hide()

    def _tick(self):
        if not _STATE.get("on"):
            self.hide()
            return
        try:
            self.peers = _peers_from_host(self.host)
            # Ensure local tile can show our own grab when no remote thumbs exist.
            local_thumb = getattr(self.host, "_et_rd_frame", None) or getattr(self.host, "_et_local_thumbnail", None)
            try:
                import edit_together_remote_desktop as _etrd
                if _etrd.should_share(self.host):
                    _etrd.tick(self.host)
                    local_thumb = getattr(self.host, "_et_rd_frame", None) or local_thumb
            except Exception:
                pass
            if local_thumb is not None and self.peers:
                for peer in self.peers:
                    if peer.get("thumbnail") is None and peer.get("role") in ("owner", "member", None):
                        # only fill empty thumbs; do not override remote frames
                        pass
            if local_thumb is not None and not any(p.get("thumbnail") for p in self.peers):
                self.peers = list(self.peers) + [{
                    "id": "local", "name": "You", "role": "local",
                    "last_seen": time.time(), "thumbnail": local_thumb,
                }]
            self._relayout()
            self.update()
            if self.peers:
                self.show()
                self.raise_()
            else:
                # Keep a thin strip visible so the user knows overlay is armed.
                self.show()
                self.raise_()
        except Exception:
            pass

    def _relayout(self):
        try:
            parent = self.parentWidget()
            if parent is None:
                return
            pr = parent.rect()
            n = max(1, len(self.peers))
            width = min(pr.width() - 2 * self.MARGIN, n * (self.TILE_W + 6) + 12)
            height = self.TILE_H + 16
            self.setGeometry(pr.width() - width - self.MARGIN, self.MARGIN, width, height)
        except Exception:
            pass

    def paintEvent(self, _event):
        try:
            p = QPainter(self)
        except Exception:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor(8, 16, 24, 150))
        p.setPen(QPen(QColor(100, 180, 210, 180), 1))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        p.setFont(font)
        if not self.peers:
            p.setPen(QColor(180, 210, 230, 220))
            p.drawText(self.rect().adjusted(10, 8, -10, -8),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "Edit Together · no peers yet\nOpen Network → Live Edit Together")
            p.end()
            return
        x = 8
        for peer in self.peers:
            tile = QRect(x, 8, self.TILE_W, self.TILE_H - 4)
            role = str(peer.get("role") or "member")
            border = QColor(120, 210, 160, 220) if role == "owner" else (
                QColor(120, 170, 220, 200) if role != "nearby" else QColor(140, 140, 160, 160))
            p.setPen(QPen(border, 2))
            p.setBrush(QColor(16, 28, 40, 200))
            p.drawRoundedRect(tile, 6, 6)
            # Thumbnail if provided as QImage/QPixmap/bytes path.
            thumb = peer.get("thumbnail")
            thumb_rect = QRect(tile.left() + 6, tile.top() + 6, tile.width() - 12, tile.height() - 36)
            drew = False
            try:
                if isinstance(thumb, QPixmap) and not thumb.isNull():
                    p.drawPixmap(thumb_rect, thumb.scaled(thumb_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation))
                    drew = True
                elif isinstance(thumb, QImage) and not thumb.isNull():
                    pm = QPixmap.fromImage(thumb)
                    p.drawPixmap(thumb_rect, pm.scaled(thumb_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation))
                    drew = True
            except Exception:
                drew = False
            if not drew:
                p.fillRect(thumb_rect, QColor(24, 40, 56, 180))
                p.setPen(QColor(140, 170, 190, 180))
                p.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "screen")
            name = str(peer.get("name") or peer.get("id") or "?")[:22]
            p.setPen(QColor(220, 240, 255, 230))
            p.drawText(QRect(tile.left() + 6, tile.bottom() - 28, tile.width() - 12, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
            p.setPen(border)
            p.drawText(QRect(tile.left() + 6, tile.bottom() - 14, tile.width() - 12, 12),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, role)
            x += self.TILE_W + 6
        p.end()


def set_enabled(host, on: bool = True) -> str:
    """Arm or disarm the presence overlay on the main Groovebox window."""
    _STATE["host"] = host
    _STATE["on"] = bool(on)
    ov = _STATE.get("overlay")
    if on:
        if ov is None or ov.parentWidget() is not host:
            try:
                if ov is not None:
                    ov.hide(); ov.setParent(None); ov.deleteLater()
            except Exception:
                pass
            ov = PresenceOverlay(host)
            _STATE["overlay"] = ov
        ov._tick()
        return "Edit Together presence overlay ON"
    if ov is not None:
        try:
            ov.hide()
        except Exception:
            pass
    return "Edit Together presence overlay OFF"


def toggle(host) -> str:
    return set_enabled(host, not bool(_STATE.get("on")))


def status() -> str:
    on = bool(_STATE.get("on"))
    ov = _STATE.get("overlay")
    n = len(getattr(ov, "peers", []) or []) if ov is not None else 0
    return f"presence_overlay={'on' if on else 'off'} peers={n}"


def open_from_app(app) -> str:
    """Task-pad / Network Hub entry: toggle overlay and open Live Edit if possible."""
    _svc = getattr(app, "_nearby_share_service", None)   # R137: user action → LAN online
    if _svc is not None and hasattr(_svc, "ensure_online"):
        try: _svc.ensure_online("edit-together")
        except Exception: pass
    msg = toggle(app)
    try:
        le = getattr(app, "_live_edit", None)
        if le is None:
            try:
                from live_edit_ui import LiveEditController
                app._live_edit = LiveEditController(app)
                le = app._live_edit
            except Exception as exc:
                msg += f" · LiveEditController: {exc}"
        if le is not None and hasattr(le, "open_panel"):
            le.open_panel()
            svc = getattr(app, "_nearby_share_service", None)
            if svc is None:
                msg += " · Nearby service off (peers will not appear until it is running)"
        elif callable(getattr(app, "_open_live_edit", None)):
            app._open_live_edit()
        else:
            import network_hub as nh
            nh.open_window(app)
            msg += " · opened Network Hub (Live Edit controller unavailable)"
    except Exception as exc:
        msg += f" · Live Edit open: {exc}"
    return msg
