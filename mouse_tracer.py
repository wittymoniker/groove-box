"""GROOVEBOX_R123_MOUSE_TRACER_20261119 — subtle pointer trail, ON by default.

How it works (Wayland-safe — no global pointer grab, no screen overlay surface):
  * One application-wide event filter sees the mouse-move/press events the platform delivers to
    each Groovebox QWindow (these arrive even when no widget has mouse tracking enabled).
  * Each top-level Groovebox window gets one transparent child overlay
    (WA_TransparentForMouseEvents) that paints the fading trail. Clicks, hover and keyboard
    focus pass straight through; the overlay never takes focus.
  * Repaints are limited to the trail's bounding box and stop entirely once the trail has
    faded, so an idle pointer costs nothing.

Settings (compat_settings, persisted; System Settings and ⚙ Settings/Compat → Mouse tracer):
  mouse_tracer (bool, default True) · mouse_tracer_mode trail|ring|trail+ring ·
  mouse_tracer_length 4–256 · mouse_tracer_fade_ms 100–5000 · mouse_tracer_width 1–24 ·
  mouse_tracer_color #rrggbb · mouse_tracer_clicks (bool)
"""
from __future__ import annotations

import time
import weakref
from collections import deque

from PyQt6.QtCore import QEvent, QObject, QPointF, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QWindow
from PyQt6.QtWidgets import QApplication, QWidget

KEYS = ("mouse_tracer", "mouse_tracer_mode", "mouse_tracer_length", "mouse_tracer_fade_ms",
        "mouse_tracer_width", "mouse_tracer_color", "mouse_tracer_clicks")
_SKIP_TYPES = (Qt.WindowType.Popup, Qt.WindowType.ToolTip, Qt.WindowType.SplashScreen)


def _settings():
    try:
        import compat_settings as cs
        s = cs.load()
        return {k: s.get(k, cs.DEFAULTS.get(k)) for k in KEYS}
    except Exception:
        return {"mouse_tracer": True, "mouse_tracer_mode": "trail", "mouse_tracer_length": 48,
                "mouse_tracer_fade_ms": 600, "mouse_tracer_width": 4, "mouse_tracer_color": "#4fd1ff",
                "mouse_tracer_clicks": True}


class _Overlay(QWidget):
    def __init__(self, tracer, host):
        super().__init__(host)
        self._tracer = tracer
        self.setObjectName("grooveboxMouseTracerOverlay")
        for attr in (Qt.WidgetAttribute.WA_TransparentForMouseEvents, Qt.WidgetAttribute.WA_NoSystemBackground,
                     Qt.WidgetAttribute.WA_TranslucentBackground, Qt.WidgetAttribute.WA_NoChildEventsForParent):
            self.setAttribute(attr, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.points = deque()        # (QPointF local, t)
        self.ripples = deque()       # (QPointF local, t)
        self.setGeometry(host.rect())
        self.show()

    def add(self, pos, t):
        self.points.append((pos, t))
        while len(self.points) > self._tracer.length:
            self.points.popleft()

    def prune(self, now):
        fade = self._tracer.fade_s
        while self.points and now - self.points[0][1] > fade:
            self.points.popleft()
        while self.ripples and now - self.ripples[0][1] > 0.45:
            self.ripples.popleft()
        return bool(self.points or self.ripples)

    def dirty_rect(self):
        if not self.points and not self.ripples:
            return QRect()
        xs = [p.x() for p, _ in self.points] + [p.x() for p, _ in self.ripples]
        ys = [p.y() for p, _ in self.points] + [p.y() for p, _ in self.ripples]
        pad = self._tracer.width * 2 + (30 if self.ripples or "ring" in self._tracer.mode else 4)
        return QRect(int(min(xs) - pad), int(min(ys) - pad), int(max(xs) - min(xs) + 2 * pad), int(max(ys) - min(ys) + 2 * pad))

    def paintEvent(self, _ev):
        tr = self._tracer
        now = time.monotonic()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        base = QColor(tr.color)
        pts = list(self.points)
        if "trail" in tr.mode and len(pts) >= 2:
            n = len(pts)
            for i in range(1, n):
                (a, _), (b, tb) = pts[i - 1], pts[i]
                life = max(0.0, 1.0 - (now - tb) / tr.fade_s)
                if life <= 0.0:
                    continue
                c = QColor(base); c.setAlphaF(0.55 * life * (i / n))
                pen = QPen(c, max(1.0, tr.width * (0.35 + 0.65 * i / n)))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(a, b)
        if "ring" in tr.mode and pts:
            head, th = pts[-1]
            life = max(0.0, 1.0 - (now - th) / tr.fade_s)
            if life > 0:
                c = QColor(base); c.setAlphaF(0.5 * life)
                p.setPen(QPen(c, max(1.0, tr.width * 0.5)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                r = 9 + tr.width
                p.drawEllipse(QRectF(head.x() - r, head.y() - r, 2 * r, 2 * r))
        for pos, t in self.ripples:
            age = (now - t) / 0.45
            if 0 <= age <= 1:
                c = QColor(base); c.setAlphaF(0.6 * (1 - age))
                p.setPen(QPen(c, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
                r = 6 + 22 * age
                p.drawEllipse(QRectF(pos.x() - r, pos.y() - r, 2 * r, 2 * r))
        p.end()


class MouseTracer(QObject):
    def __init__(self, app):
        super().__init__(app)
        self._app = app
        self._overlays = weakref.WeakKeyDictionary()   # top-level QWidget -> _Overlay
        self._active = weakref.WeakSet()
        self._hosts = weakref.WeakKeyDictionary()      # QWindow -> top-level QWidget
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.enabled = False
        self.apply(_settings())

    # -- settings -----------------------------------------------------------------------
    def apply(self, s):
        self.mode = str(s.get("mouse_tracer_mode") or "trail")
        self.length = int(s.get("mouse_tracer_length") or 48)
        self.fade_s = max(0.1, int(s.get("mouse_tracer_fade_ms") or 600) / 1000.0)
        self.width = int(s.get("mouse_tracer_width") or 4)
        self.color = str(s.get("mouse_tracer_color") or "#4fd1ff")
        self.clicks = bool(s.get("mouse_tracer_clicks", True))
        on = bool(s.get("mouse_tracer", True))
        if on and not self.enabled:
            self._app.installEventFilter(self)
        elif not on and self.enabled:
            self._app.removeEventFilter(self)
            for ov in list(self._overlays.values()):
                try:
                    ov.points.clear(); ov.ripples.clear(); ov.update()
                except RuntimeError:
                    pass
        self.enabled = on

    # -- event plumbing -----------------------------------------------------------------
    def _host_for(self, qwindow):
        cached = self._hosts.get(qwindow)
        if cached is not None:
            try:
                if cached.windowHandle() is qwindow:
                    return cached
            except RuntimeError:
                pass
        for w in QApplication.topLevelWidgets():
            try:
                if w.windowHandle() is qwindow:
                    if w.windowFlags() & Qt.WindowType.WindowType_Mask in _SKIP_TYPES:
                        return None
                    if w.property("grooveboxNoMouseTracer"):
                        return None
                    self._hosts[qwindow] = w
                    return w
            except RuntimeError:
                continue
        return None

    def _overlay(self, host):
        ov = self._overlays.get(host)
        try:
            if ov is not None:
                ov.isVisible()
                return ov
        except RuntimeError:
            pass
        ov = _Overlay(self, host)
        self._overlays[host] = ov
        host.installEventFilter(self)
        return ov

    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if t in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress) and isinstance(obj, QWindow):
                host = self._host_for(obj)
                if host is not None and host.isVisible():
                    ov = self._overlay(host)
                    gp = ev.globalPosition()
                    local = QPointF(host.mapFromGlobal(gp.toPoint()))
                    now = time.monotonic()
                    if t == QEvent.Type.MouseMove:
                        ov.add(local, now)
                    elif self.clicks:
                        ov.ripples.append((local, now))
                    if ov.parent() is not None:
                        ov.raise_()
                    self._active.add(ov)
                    if not self._timer.isActive():
                        self._timer.start()
            elif t == QEvent.Type.Resize and obj in self._overlays:
                ov = self._overlays.get(obj)
                if ov is not None:
                    ov.setGeometry(obj.rect())
        except RuntimeError:
            pass
        except Exception:
            pass
        return False

    def _tick(self):
        now = time.monotonic()
        alive = False
        for ov in list(self._active):
            try:
                before = ov.dirty_rect()
                still = ov.prune(now)
                ov.update(before.united(ov.dirty_rect()) if still else before)
                if still:
                    alive = True
                else:
                    self._active.discard(ov)
            except RuntimeError:
                self._active.discard(ov)
        if not alive:
            self._timer.stop()


_TRACER = None


def install(app=None):
    """Install once at application start. Safe to call again; returns the tracer."""
    global _TRACER
    app = app or QApplication.instance()
    if app is None:
        return None
    if _TRACER is None:
        _TRACER = MouseTracer(app)
    return _TRACER


def reload_settings():
    if _TRACER is not None:
        _TRACER.apply(_settings())


def set_enabled(on):
    try:
        import compat_settings as cs
        cs.update(mouse_tracer=bool(on))
    except Exception:
        pass
    reload_settings()
