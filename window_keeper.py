"""WINDOW_KEEPER_20261112: keep parentless tool windows alive while they are open.

A top-level PyQt widget with no parent is destroyed as soon as its last Python reference goes away, so
`lambda: module.open_window(app)` used to flash a window and lose it. kept() wraps an open_window factory:
the returned top-level widget is held in a module set until Qt destroys it, and is set to delete on close so
the set never grows."""
from __future__ import annotations

import functools

_LIVE = set()


def keep(w):
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QWidget
    except Exception:
        return w
    if not isinstance(w, QWidget) or w in _LIVE:
        return w
    try:
        if w.parent() is not None and not w.isWindow():
            return w
        _LIVE.add(w)
        w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        w.destroyed.connect(lambda *_a, ref=w: _LIVE.discard(ref))
    except RuntimeError:
        _LIVE.discard(w)
    return w


def kept(factory):
    @functools.wraps(factory)
    def open_window(*a, **k):
        return keep(factory(*a, **k))
    open_window.__wrapped_keeper__ = True
    return open_window


def live_count() -> int:
    return len(_LIVE)
