"""touch_compat.py — touchscreen fallbacks for mouse-only gestures.

GROOVEBOX_R123_TOUCH_FALLBACKS_20261119

* Right-drag (Mod Path Bay stages / reroute / perspective pads) has two touch fallbacks:
    - touch-and-hold (450 ms without moving) then drag = right-drag;
    - a sticky "Alt drag" toggle (app._r123_alt_drag) that makes every plain drag a right-drag.
* Wheel-only controls (pole spin, perspective magnitude) are reachable by right-drag, so they
  work by touch through the same fallbacks.
* Page scrolling: one-finger kinetic flick scrolling on every page scroll area (QScroller
  TouchGesture), so the page scrolls on tablets without a wheel. Mouse behaviour is unchanged.
"""
from __future__ import annotations

HOLD_MS = 450
HOLD_SLOP_PX = 8


def alt_drag(app) -> bool:
    return bool(getattr(app, "_r123_alt_drag", False))


def set_alt_drag(app, on: bool) -> None:
    app._r123_alt_drag = bool(on)
    try:
        from PyQt6.QtCore import QSettings
        QSettings("MathematiciansGroovebox", "UI").setValue("touch_alt_drag", bool(on))
    except Exception:
        pass


def load_alt_drag(app) -> bool:
    try:
        from PyQt6.QtCore import QSettings
        v = QSettings("MathematiciansGroovebox", "UI").value("touch_alt_drag", False)
        app._r123_alt_drag = str(v).lower() in ("1", "true", "yes")
    except Exception:
        app._r123_alt_drag = False
    return app._r123_alt_drag


def is_touch(event) -> bool:
    try:
        from PyQt6.QtGui import QInputDevice
        dev = event.device()
        return dev is not None and dev.type() in (QInputDevice.DeviceType.TouchScreen,
                                                  QInputDevice.DeviceType.TouchPad)
    except Exception:
        return False


class HoldGesture:
    """Per-widget helper: becomes 'alt' after a still press of HOLD_MS (or at once in Alt-drag mode)."""

    def __init__(self, widget, app=None, on_alt=None):
        from PyQt6.QtCore import QTimer
        self.w = widget; self.app = app; self.on_alt = on_alt
        self.alt = False; self.start = None
        self.timer = QTimer(widget); self.timer.setSingleShot(True); self.timer.setInterval(HOLD_MS)
        self.timer.timeout.connect(self._fire)

    def press(self, event) -> bool:
        """Call on a left press. Returns True when the drag is already 'alt' (sticky Alt-drag mode)."""
        self.start = event.position(); self.alt = False
        if self.app is not None and alt_drag(self.app):
            self.alt = True
            return True
        self.timer.start()
        return False

    def move(self, event) -> None:
        if self.start is not None and not self.alt and (event.position() - self.start).manhattanLength() > HOLD_SLOP_PX:
            self.timer.stop()

    def release(self) -> None:
        self.timer.stop(); self.start = None; self.alt = False

    def _fire(self):
        if self.start is None:
            return
        self.alt = True
        try:
            self.w.update()
        except Exception:
            pass
        if callable(self.on_alt):
            try:
                self.on_alt(self.start)
            except Exception:
                pass


def alt_toggle_button(app):
    """A checkable '⇄ Alt drag' button (touch fallback for right-drag); shared state across panels."""
    from PyQt6.QtWidgets import QPushButton
    if not hasattr(app, "_r123_alt_drag"):
        load_alt_drag(app)
    b = QPushButton("⇄ Alt drag")
    b.setCheckable(True); b.setChecked(alt_drag(app)); b.setMinimumHeight(30)
    b.setToolTip("Touchscreen fallback for right-drag: while ON, a plain drag does what right-drag does. "
                 "Touch-and-hold (½ s) then drag also works without this switch.")
    b.toggled.connect(lambda on: set_alt_drag(app, on))
    buttons = getattr(app, "_r123_alt_buttons", None)
    if buttons is None:
        buttons = app._r123_alt_buttons = []
    buttons.append(b)

    def _sync(on):
        for o in list(buttons):
            try:
                if o is not b and o.isChecked() != on:
                    o.blockSignals(True); o.setChecked(on); o.blockSignals(False)
            except Exception:
                try: buttons.remove(o)
                except ValueError: pass
    b.toggled.connect(_sync)
    return b


def enable_touch_scrolling(root) -> int:
    """Grab one-finger kinetic touch scrolling on every scroll area under root (idempotent)."""
    try:
        from PyQt6.QtWidgets import QScroller, QScrollArea
    except Exception:
        return 0
    n = 0
    try:
        areas = [root] if isinstance(root, QScrollArea) else []
        areas += root.findChildren(QScrollArea)
        for a in areas:
            vp = a.viewport()
            if vp is None or vp.property("_gb_touch_scroll"):
                continue
            QScroller.grabGesture(vp, QScroller.ScrollerGestureType.TouchGesture)
            vp.setProperty("_gb_touch_scroll", True)
            n += 1
    except Exception:
        pass
    return n


def right_like(event) -> bool:
    """Right button, or its stand-ins on other devices: macOS Ctrl+click (Qt reports Meta+Left there),
    a stylus barrel button (already Right) or the stylus eraser end."""
    try:
        from PyQt6.QtCore import Qt
        b = event.button()
        if b == Qt.MouseButton.RightButton:
            return True
        if b != Qt.MouseButton.LeftButton:
            return False
        import sys
        if sys.platform == "darwin" and event.modifiers() & Qt.KeyboardModifier.MetaModifier:
            return True
        try:
            from PyQt6.QtGui import QPointingDevice
            dev = event.pointingDevice()
            if dev is not None and dev.pointerType() == QPointingDevice.PointerType.Eraser:
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def small_screen(host=None) -> bool:
    """True on screens under 1366×800 logical px (netbooks, small tablets, phones in desktop mode)."""
    try:
        from PyQt6.QtWidgets import QApplication
        scr = (host.screen() if host is not None else None) or QApplication.primaryScreen()
        g = scr.availableGeometry()
        return g.width() < 1366 or g.height() < 800
    except Exception:
        return False
