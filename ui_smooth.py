"""UI smoothness: one paint per frame, heavy work off the GUI thread.

Groovebox already has a queued UI dispatcher. This adds the two habits that
keep a Qt window smooth:

* coalesce(widget)  request a repaint; many calls in one frame become one update
* off_ui(fn, then)  run fn on the shared worker pool, deliver then() on the GUI thread
"""
from __future__ import annotations

_PENDING = set()
_INSTALLED = False


def coalesce(widget):
    """Schedule widget.update() once for this frame."""
    if widget is None:
        return
    key = id(widget)
    if key in _PENDING:
        return
    _PENDING.add(key)
    try:
        from PyQt6.QtCore import QTimer
        def _go(w=widget, k=key):
            _PENDING.discard(k)
            try:
                orig = getattr(type(w), "_gb_update", None)
                if orig is not None:
                    orig(w)
                else:
                    w.update()
            except RuntimeError:
                pass
        QTimer.singleShot(0, _go)
    except Exception:
        _PENDING.discard(key)


def off_ui(fn, then=None):
    """Run fn off the GUI thread. then(result) runs on the GUI thread."""
    def _work():
        try:
            result = fn()
        except Exception as exc:
            result = exc
        if then is None:
            return
        try:
            from ui_runtime import post_to_ui
            post_to_ui(lambda r=result: then(r))
        except Exception:
            then(result)
    try:
        import r32_pool
        class _Job:
            def run(self_):
                _work()
        r32_pool.start(_Job())
    except Exception:
        _work()


def install(app=None):
    """Coalesce QWidget.update so a burst of changes paints once per frame."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    try:
        from PyQt6.QtWidgets import QApplication, QWidget
        app = app or QApplication.instance()
        if app is not None:
            app._ui_smooth = True
        if getattr(QWidget, "_gb_smooth", False):
            return
        _orig = QWidget.update
        def _coalesced(self, *args, **kwargs):
            if args or kwargs:
                return _orig(self, *args, **kwargs)
            coalesce(self)
        QWidget.update = _coalesced
        QWidget._gb_smooth = True
        QWidget._gb_update = _orig
    except Exception:
        pass
