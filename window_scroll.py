"""WINDOW_SCROLL_R7: every window scrolls.

One application-wide event filter.  The first time any top-level window is shown, its content is moved
into a transparent, frameless ``QScrollArea`` (``widgetResizable``: nothing changes visually until the
content no longer fits), and the window is clamped to the screen it is on.  Scroll bars therefore
appear only when a window is smaller than its content — every control stays reachable at any DPI,
UI scale or monitor size.

Left alone: the pinned main window (it fits the monitor and already scrolls its panes), the window
strip, standard Qt dialogs (message/file/colour/font/input/progress), menus, tooltips, popups,
splash screens, frameless overlays, and anything marked ``setProperty("gb_no_auto_scroll", True)``.
Background children that are not in the layout (math backgrounds, Party backdrops) stay where they
are, under the transparent viewport.
"""
from __future__ import annotations

_STATE = {"filter": None}
_MARK = "gb_scroll_wrapped"
_SKIP_CLASSES = ("QMessageBox", "QFileDialog", "QColorDialog", "QFontDialog", "QInputDialog",
                 "QProgressDialog", "QMenu", "QToolTip", "QSplashScreen", "QErrorMessage", "QWizard",
                 "MathematiciansGrooveboxApp", "_GrooveboxWindowStrip", "QScrollArea", "QAbstractScrollArea")
_TRANSPARENT = "QScrollArea#gbAutoScroll, QScrollArea#gbAutoScroll > QWidget > QWidget#gbAutoScrollBody " \
               "{ background: transparent; border: 0; }"


def _class_chain(w):
    try:
        mo = w.metaObject()
        while mo is not None:
            yield mo.className()
            mo = mo.superClass()
    except Exception:
        return


def eligible(w) -> bool:
    """True when ``w`` is a top-level window this module should wrap."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QScrollArea, QAbstractScrollArea
        if w is None or not w.isWindow() or w.property(_MARK) or w.property("gb_no_auto_scroll"):
            return False
        if isinstance(w, (QScrollArea, QAbstractScrollArea)):
            return False
        names = set(_class_chain(w))
        if names & set(_SKIP_CLASSES):
            return False
        t = w.windowType()
        if t in (Qt.WindowType.Popup, Qt.WindowType.ToolTip, Qt.WindowType.SplashScreen,
                 Qt.WindowType.Desktop, Qt.WindowType.SubWindow):
            return False
        fl = w.windowFlags()
        if (fl & Qt.WindowType.FramelessWindowHint) and t != Qt.WindowType.Dialog:
            return False          # overlays / HUDs / kiosk shells draw their own edges
        if w.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents):
            return False
        return True
    except Exception:
        return False


def _area(body):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QScrollArea, QFrame
    a = QScrollArea()
    a.setObjectName("gbAutoScroll")
    a.setWidgetResizable(True)
    a.setFrameShape(QFrame.Shape.NoFrame)
    a.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    a.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    a.setStyleSheet(_TRANSPARENT)
    a.viewport().setAutoFillBackground(False)
    a.setAutoFillBackground(False)
    body.setObjectName(body.objectName() or "gbAutoScrollBody")
    body.setAutoFillBackground(False)
    a.setWidget(body)
    return a


def wrap(w) -> bool:
    """Move ``w``'s content into a scroll area.  Returns True when wrapped (idempotent)."""
    if not eligible(w):
        return False
    try:
        from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QScrollArea, QAbstractScrollArea
        if isinstance(w, QMainWindow):
            c = w.centralWidget()
            if c is None or isinstance(c, (QScrollArea, QAbstractScrollArea)):
                w.setProperty(_MARK, True)
                return False
            c = w.takeCentralWidget()
            w.setCentralWidget(_area(c))
            w.setProperty(_MARK, True)
            return True
        lay = w.layout()
        if lay is None:
            w.setProperty(_MARK, True)
            return False
        if lay.count() == 1:                             # already a single scroll area / view: nothing to add
            only = lay.itemAt(0).widget()
            if isinstance(only, (QScrollArea, QAbstractScrollArea)):
                w.setProperty(_MARK, True)
                return False
        m = lay.contentsMargins()
        body = QWidget()
        body.setLayout(lay)                              # re-parents the layout and every managed child to body
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_area(body))
        lay.setContentsMargins(m)
        w.setProperty(_MARK, True)
        return True
    except Exception as exc:
        try:
            w.setProperty(_MARK, True)                   # never retry a window that refused
        except Exception:
            pass
        print(f"[Scroll] could not wrap {type(w).__name__}: {exc}")
        return False


_SYSINFO_WORDS = ("system", "memory", "health", "diagnos", "info", "about", "status", "hardware", "thread")


def style_system_popup(w) -> None:
    """TYPOGRAPHY_R7: system-information popups (message boxes titled System / Memory / Health / Info …)
    show their text in the console face; everything else stays Arial."""
    try:
        if w.property("gb_console_styled") or "QMessageBox" not in set(_class_chain(w)):
            return
        title = str(w.windowTitle() or "").lower()
        if not any(k in title for k in _SYSINFO_WORDS):
            return
        import typography as _ty
        from PyQt6.QtWidgets import QLabel
        for lab in w.findChildren(QLabel):
            if lab.objectName() in ("qt_msgbox_label", "qt_msgbox_informativelabel"):
                _ty.apply_console(lab)
        w.setProperty("gb_console_styled", True)
    except Exception:
        pass


def clamp_to_screen(w) -> None:
    """Keep a window no larger than its screen's available area and fully on it."""
    try:
        scr = w.screen()
        if scr is None:
            return
        area = scr.availableGeometry()
        fr = w.frameGeometry(); g = w.geometry()
        fw, fh = fr.width() - g.width(), fr.height() - g.height()
        mw, mh = max(120, area.width() - fw), max(80, area.height() - fh)
        if w.minimumWidth() > mw or w.minimumHeight() > mh:
            w.setMinimumSize(min(w.minimumWidth(), mw), min(w.minimumHeight(), mh))
        if g.width() > mw or g.height() > mh:
            w.resize(min(g.width(), mw), min(g.height(), mh))
        fr = w.frameGeometry()
        x = min(max(fr.x(), area.left()), area.right() - fr.width() + 1)
        y = min(max(fr.y(), area.top()), area.bottom() - fr.height() + 1)
        if (x, y) != (fr.x(), fr.y()):
            w.move(x, y)
    except Exception:
        pass


def uninstall(app=None) -> None:
    """Remove the stand-alone filter (window_manager's filter performs the same wrap once installed)."""
    try:
        from PyQt6.QtWidgets import QApplication
        app = app or QApplication.instance()
        f = _STATE["filter"]
        if app is not None and f is not None:
            app.removeEventFilter(f)
        _STATE["filter"] = None
    except Exception:
        pass


def install(app=None) -> bool:
    """Install the app-wide filter (idempotent).  Stand-alone use only: once window_manager installs its
    filter it calls ``uninstall`` and wraps windows itself, so there is never a second per-event filter."""
    try:
        from PyQt6.QtCore import QObject, QEvent
        from PyQt6.QtWidgets import QApplication, QWidget
        app = app or QApplication.instance()
        try:
            import window_manager as _wm
            if _wm.manager() is not None:            # the manager already wraps on Show
                for w in app.topLevelWidgets():
                    if w.isVisible() and wrap(w):
                        clamp_to_screen(w)
                return True
        except Exception:
            pass
        if app is None or _STATE["filter"] is not None:
            return _STATE["filter"] is not None

        class _ScrollFilter(QObject):
            def eventFilter(self, obj, ev):
                try:
                    if ev.type() != QEvent.Type.Show:
                        return False
                    if isinstance(obj, QWidget) and obj.isWindow():
                        style_system_popup(obj)
                    if isinstance(obj, QWidget) and isinstance(obj, QWidget) and obj.isWindow():
                        if wrap(obj) or obj.property(_MARK):
                            clamp_to_screen(obj)
                except Exception:
                    pass
                return False

        f = _ScrollFilter(app)
        app.installEventFilter(f)
        _STATE["filter"] = f
        for w in app.topLevelWidgets():                  # windows already open
            if w.isVisible() and wrap(w):
                clamp_to_screen(w)
        return True
    except Exception as exc:
        print(f"[Scroll] install skipped: {exc}")
        return False
