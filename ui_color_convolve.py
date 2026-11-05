"""Whole-UI colour convolve: the Video Planner's channel order + mix applied to every stylesheet colour
and the application palette. Custom-painted canvases keep their own colours."""
from __future__ import annotations

import re

from PyQt6.QtCore import QObject, QEvent, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QWidget

_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*[\d.]+\s*)?\)")
_ORIG = "_gbConvolveOrigSheet"
_DONE = "_gbConvolveSheet"
_STATE = {"order": "RGB", "mix": 0.0, "palette": None, "app_sheet": None, "filter": None, "timer": None}


def _rgb(r, g, b, order, mix):
    src = {"R": r, "G": g, "B": b}
    sw = [src[c] for c in order]
    return [max(0, min(255, int(round((1.0 - mix) * a + mix * s)))) for a, s in zip((r, g, b), sw)]


def convolve_sheet(css, order, mix):
    def hx(m):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % tuple(_rgb(r, g, b, order, mix))

    def rg(m):
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        nr, ng, nb = _rgb(r, g, b, order, mix)
        a = m.group(4)
        return f"rgba({nr}, {ng}, {nb}{a})" if a else f"rgb({nr}, {ng}, {nb})"

    return _RGB.sub(rg, _HEX.sub(hx, css))


def _active():
    return _STATE["order"] != "RGB" and _STATE["mix"] > 0.0


def _apply_widget(w):
    cur = w.styleSheet()
    orig = w.property(_ORIG)
    if orig is None or cur != (w.property(_DONE) or orig):
        orig = cur                      # first sight, or the app restyled it since: new original
        w.setProperty(_ORIG, orig)
    if not orig:
        return
    new = convolve_sheet(orig, _STATE["order"], _STATE["mix"]) if _active() else orig
    w.setProperty(_DONE, new)
    if new != cur:
        w.setStyleSheet(new)


def _apply_all():
    app = QApplication.instance()
    if app is None:
        return
    if _STATE["app_sheet"] is None:
        _STATE["app_sheet"] = app.styleSheet()
    base = _STATE["app_sheet"]
    app.setStyleSheet(convolve_sheet(base, _STATE["order"], _STATE["mix"]) if (_active() and base) else base)
    if _STATE["palette"] is None:
        _STATE["palette"] = QPalette(app.palette())
    pal = QPalette(_STATE["palette"])
    if _active():
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
            for role in QPalette.ColorRole:
                if role == QPalette.ColorRole.NColorRoles:
                    continue
                try:
                    c = pal.color(group, role)
                    r, g, b = _rgb(c.red(), c.green(), c.blue(), _STATE["order"], _STATE["mix"])
                    pal.setColor(group, role, QColor(r, g, b, c.alpha()))
                except Exception:
                    pass
    app.setPalette(pal)
    for w in app.allWidgets():
        try:
            _apply_widget(w)
        except Exception:
            pass


class _ShowFilter(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Show and _active():
            try:
                if obj.isWindow():
                    for w in [obj] + obj.findChildren(QWidget):
                        _apply_widget(w)
            except Exception:
                pass
        return False


def set_convolve(order="RGB", mix=0.0):
    """Apply (or with RGB / 0 remove) the colour convolve across the whole UI."""
    order = str(order or "RGB").upper()
    _STATE["order"] = order if sorted(order) == ["B", "G", "R"] else "RGB"
    _STATE["mix"] = max(0.0, min(1.0, float(mix or 0.0)))
    app = QApplication.instance()
    if app is None:
        return
    if _STATE["filter"] is None:
        _STATE["filter"] = _ShowFilter(app)
        app.installEventFilter(_STATE["filter"])
    _apply_all()
    t = _STATE["timer"]
    if _active():
        if t is None:
            t = _STATE["timer"] = QTimer(app)
            t.setInterval(2000)          # widgets the app restyles later are re-convolved
            t.timeout.connect(_apply_all)
        t.start()
    elif t is not None:
        t.stop()
