"""GROOVEBOX_R32_WINDOW_MANAGER_20261109 — OS-like window management for every Groovebox window.

Why: Qt gives every top-level window that has a QWidget parent a *transient parent*
(the owner).  Window managers (labwc, KWin, Mutter, Windows' owned-window rule) treat
a transient window as a satellite of its owner: it has no own taskbar slot, it is
minimised together with the owner, and a "minimise" on it alone is ignored or
minimises the owner.  That is the "Live Player does not minimise without minimising
the main window" bug — and it applied to every non-modal Groovebox tool window.

What this module does (all on the GUI thread, all cheap, never waits):

* :func:`make_independent` — at the window's Show event (before it is mapped) clear
  the transient parent and give the platform window real minimise / maximise / close
  buttons and the normal-window type.  The Qt parent (lifetime, ``self.host``) stays.
  Modal dialogs keep their owner (they must stay on top of what they block).
* Geometry memory per window kind, clamped onto a live screen (hot-plug safe).
* Arrange actions: snap left / right, maximise toggle, centre, tile all, cascade,
  minimise all ("show desktop"), restore all, cycle next / previous.
* App-wide shortcuts (Meta and Ctrl+Alt variants, so they work on keyboards and
  desktops where Super is taken by the shell):

    Meta/Ctrl+Alt + ←/→   snap left / right half          Meta/Ctrl+Alt + ↑   maximise / restore
    Meta/Ctrl+Alt + ↓     minimise this window             Ctrl+Alt+D          minimise all (show desktop)
    Ctrl+Alt+R            restore all                      Ctrl+Alt+T          tile all
    Ctrl+Alt+C            cascade                          Ctrl+` / Ctrl+Shift+`  next / previous window
"""
from __future__ import annotations

import json
import os
import weakref

try:
    from PyQt6.QtCore import Qt, QObject, QEvent, QRect, QPoint, QTimer
    from PyQt6.QtGui import QKeySequence, QShortcut, QGuiApplication
    from PyQt6.QtWidgets import QApplication, QDialog, QWidget, QMainWindow, QMenu
except Exception:  # pragma: no cover - headless import
    QObject = object

_GEOM_FILE = None
_GEOM_CACHE = None
_SKIP_GEOMETRY_CLASSES = {"Performance"}   # Performance always opens on the main window's geometry


def _config_dir():
    base = os.environ.get("GROOVEBOX_DATA_DIR") or os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config"), "groovebox")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base


def _geom_path():
    global _GEOM_FILE
    if _GEOM_FILE is None:
        _GEOM_FILE = os.path.join(_config_dir(), "window-geometry.json")
    return _GEOM_FILE


def _load_geoms():
    global _GEOM_CACHE
    if _GEOM_CACHE is None:
        try:
            with open(_geom_path(), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            _GEOM_CACHE = data if isinstance(data, dict) else {}
        except Exception:
            _GEOM_CACHE = {}
    return _GEOM_CACHE


def _save_geoms():
    data = _load_geoms()
    try:
        tmp = _geom_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=0, sort_keys=True)
        os.replace(tmp, _geom_path())
    except Exception:
        pass


def window_key(w):
    """Stable kind key: class name + title without the '#n ' prefix of extra windows."""
    try:
        title = (w.windowTitle() or "").strip()
        if title.startswith("#") and " " in title:
            title = title.split(" ", 1)[1]
        title = title.split("—")[0].split(" - ")[0].strip()[:40]
        return f"{w.__class__.__name__}|{title}"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Independence (the minimise bug fix)
# ---------------------------------------------------------------------------
def is_modal(w):
    try:
        return bool(w.isModal()) or w.windowModality() != Qt.WindowModality.NonModal
    except Exception:
        return False


_TRANSIENT_KINDS = None


def _is_tool_window(w):
    """True for a top-level widget that should behave like a normal OS window."""
    global _TRANSIENT_KINDS
    if _TRANSIENT_KINDS is None:
        _TRANSIENT_KINDS = {int(Qt.WindowType.Popup), int(Qt.WindowType.ToolTip),
                            int(Qt.WindowType.SplashScreen), int(Qt.WindowType.Tool),
                            int(Qt.WindowType.Drawer), int(Qt.WindowType.Sheet),
                            int(Qt.WindowType.SubWindow)}
    try:
        if not isinstance(w, QWidget) or not w.isWindow() or isinstance(w, QMenu):
            return False
        kind = int(w.windowFlags()) & int(Qt.WindowType.WindowType_Mask)
        if kind in _TRANSIENT_KINDS:
            return False
        if w.testAttribute(Qt.WidgetAttribute.WA_X11NetWmWindowTypeCombo) or \
           w.testAttribute(Qt.WidgetAttribute.WA_X11NetWmWindowTypeToolTip):
            return False
        return True
    except Exception:
        return False


def make_independent(w):
    """Make a non-modal tool window a first-class OS window. Safe to call repeatedly.

    Must run before the native window is mapped (the Show event is sent before
    show_sys), so the compositor never sees it as a satellite of Main.
    """
    if w is None or is_modal(w):
        return False
    try:
        if bool(w.property("grooveboxExternalWindowStrip")) or bool(w.property("grooveboxKeepOwner")):
            return False
    except Exception:
        pass
    try:
        h = w.windowHandle()
        if h is None:
            return False
        if h.transientParent() is not None:
            h.setTransientParent(None)
        f = h.flags()
        want = (Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint |
                Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowTitleHint |
                Qt.WindowType.WindowSystemMenuHint)
        if bool(w.property("grooveboxMainLocked")):
            want &= ~Qt.WindowType.WindowMinimizeButtonHint   # R32: Main never minimises
        nf = f | want
        # A Dialog-type surface is "a dialog of its owner" to most WMs; a tool window
        # of Groovebox is a normal window.
        if (int(nf) & int(Qt.WindowType.WindowType_Mask)) == int(Qt.WindowType.Dialog):
            nf = (nf & ~Qt.WindowType.WindowType_Mask) | Qt.WindowType.Window
        if nf != f:
            h.setFlags(nf)
        w.setProperty("grooveboxIndependent", True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Geometry memory + screen clamping
# ---------------------------------------------------------------------------
def _available(w=None):
    try:
        scr = None
        if w is not None:
            h = w.windowHandle()
            scr = h.screen() if h is not None else None
            if scr is None:
                scr = QGuiApplication.screenAt(w.geometry().center())
        scr = scr or QGuiApplication.primaryScreen()
        return scr.availableGeometry() if scr is not None else QRect(0, 0, 1366, 768)
    except Exception:
        return QRect(0, 0, 1366, 768)


def _top_margin():
    # The appliance strip occupies the top 40 px (labwc <margin top="40"/>).
    return 40 if os.environ.get("GROOVEBOX_USER_SESSION") == "1" else 0


def clamp_on_screen(w):
    """Move/resize a window so its title bar is reachable on a connected screen."""
    if _is_external(w):
        return
    try:
        g = w.frameGeometry()
        on_any = any(s.availableGeometry().intersects(g) for s in QGuiApplication.screens())
        a = _available(w)
        a = a.adjusted(0, _top_margin(), 0, 0) if _top_margin() and a.top() < _top_margin() else a
        width = min(w.width(), a.width())
        height = min(w.height(), a.height())
        x, y = w.x(), w.y()
        # Always keep the title bar (top 36 px, first 220 px) inside the screen.
        title_off = (y < a.top() or y > a.bottom() - 36 or x < a.left() or x + min(220, width) > a.right())
        if not on_any or title_off or x + width > a.right() + 8 or y + height > a.bottom() + 8:
            x = max(a.left(), min(x, a.right() - width))
            y = max(a.top(), min(y, a.bottom() - height))
            if (width, height) != (w.width(), w.height()):
                w.resize(width, height)
            w.move(x, y)
            return True
    except Exception:
        pass
    return False


def remember_geometry(w):
    if w is None or w.__class__.__name__ in _SKIP_GEOMETRY_CLASSES:
        return
    try:
        if w.isMinimized() or w.isMaximized() or w.isFullScreen() or not w.isVisible():
            return
        g = w.geometry()
        if g.width() < 160 or g.height() < 120:
            return
        _load_geoms()[window_key(w)] = [g.x(), g.y(), g.width(), g.height()]
        _schedule_save()
    except Exception:
        pass


_save_timer = None


def _schedule_save():
    global _save_timer
    try:
        if _save_timer is None:
            _save_timer = QTimer()
            _save_timer.setSingleShot(True)
            _save_timer.setInterval(1500)
            _save_timer.timeout.connect(_save_geoms)
        _save_timer.start()
    except Exception:
        _save_geoms()


def restore_geometry(w):
    if w is None or w.__class__.__name__ in _SKIP_GEOMETRY_CLASSES:
        return False
    try:
        if bool(w.property("grooveboxGeometryRestored")):
            return False
        w.setProperty("grooveboxGeometryRestored", True)
        g = _load_geoms().get(window_key(w))
        if not (isinstance(g, list) and len(g) == 4):
            return False
        w.setGeometry(int(g[0]), int(g[1]), int(g[2]), int(g[3]))
        clamp_on_screen(w)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Arrange actions
# ---------------------------------------------------------------------------
def _normal(w):
    try:
        if w.isMinimized() or w.isMaximized() or w.isFullScreen():
            w.showNormal()
    except Exception:
        pass


def _is_external(w):
    """R32.8: proxy for another process's window (ext_windows) — listed, raised, closed, never moved."""
    try:
        return bool(w.property("grooveboxExternalProcessWindow"))
    except Exception:
        return False


def snap(w, where):
    """where: 'left' | 'right' | 'top' | 'bottom' | 'center' | 'max'."""
    if w is None or _is_external(w):
        return
    a = _available(w)
    if _top_margin() and a.top() < _top_margin():
        a = a.adjusted(0, _top_margin() - a.top(), 0, 0)
    if where == "max":
        if w.isMaximized():
            w.showNormal()
        else:
            w.showMaximized()
        return
    _normal(w)
    fw = w.frameGeometry().width() - w.geometry().width()
    fh = w.frameGeometry().height() - w.geometry().height()
    if where == "left":
        r = QRect(a.left(), a.top(), a.width() // 2, a.height())
    elif where == "right":
        r = QRect(a.left() + a.width() // 2, a.top(), a.width() - a.width() // 2, a.height())
    elif where == "top":
        r = QRect(a.left(), a.top(), a.width(), a.height() // 2)
    elif where == "bottom":
        r = QRect(a.left(), a.top() + a.height() // 2, a.width(), a.height() - a.height() // 2)
    else:
        sz = w.size()
        r = QRect(a.left() + (a.width() - sz.width()) // 2, a.top() + (a.height() - sz.height()) // 2,
                  sz.width(), sz.height())
    try:
        w.setGeometry(r.adjusted(0, 0, -fw, -fh) if where != "center" else r)
    except Exception:
        pass
    _activate(w)


def _activate(w):
    try:
        w.show()
        w.raise_()
        w.activateWindow()
    except Exception:
        pass


def tile(windows):
    ws = [w for w in windows if w is not None and not _is_external(w)]
    if not ws:
        return
    import math
    a = _available(ws[0])
    if _top_margin() and a.top() < _top_margin():
        a = a.adjusted(0, _top_margin() - a.top(), 0, 0)
    n = len(ws)
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / float(cols)))
    cw, ch = a.width() // cols, a.height() // rows
    for i, w in enumerate(ws):
        _normal(w)
        r, c = divmod(i, cols)
        try:
            fw = w.frameGeometry().width() - w.geometry().width()
            fh = w.frameGeometry().height() - w.geometry().height()
            w.setGeometry(a.left() + c * cw, a.top() + r * ch, max(200, cw - fw), max(150, ch - fh))
            w.show()
        except Exception:
            pass


def cascade(windows):
    ws = [w for w in windows if w is not None and not _is_external(w)]
    if not ws:
        return
    a = _available(ws[0])
    if _top_margin() and a.top() < _top_margin():
        a = a.adjusted(0, _top_margin() - a.top(), 0, 0)
    step = 32
    width = int(a.width() * 0.66)
    height = int(a.height() * 0.70)
    for i, w in enumerate(ws):
        _normal(w)
        off = (i * step) % max(step, (a.height() - height))
        try:
            w.setGeometry(a.left() + off, a.top() + off, width, height)
            w.show()
            w.raise_()
        except Exception:
            pass


def minimize_all(windows):
    for w in windows:
        try:
            if w is not None and w.isVisible() and not bool(w.property("grooveboxMainLocked")):
                w.showMinimized()
        except Exception:
            pass


def restore_all(windows):
    for w in windows:
        try:
            if w is not None and (w.isMinimized()):
                w.showNormal()
        except Exception:
            pass


def cycle(windows, step=1):
    ws = [w for w in windows if w is not None]
    if not ws:
        return None
    active = QApplication.activeWindow()
    try:
        i = ws.index(active)
    except ValueError:
        i = -1 if step > 0 else 0
    target = ws[(i + step) % len(ws)]
    try:
        if target.isMinimized():
            target.showNormal()
    except Exception:
        pass
    _activate(target)
    return target


# ---------------------------------------------------------------------------
# App-wide controller
# ---------------------------------------------------------------------------
class WindowManager(QObject):
    """Installed once on QApplication. ``windows_fn`` returns the session window list
    (Main first) — the window strip's own manager provides it."""

    _EVENTS = None

    def __init__(self, windows_fn, parent=None):
        super().__init__(parent)
        self._windows_fn = windows_fn
        self._shortcuts = []
        self._owner_ref = None
        WindowManager._EVENTS = frozenset((QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Move,
                                           QEvent.Type.Resize, QEvent.Type.Close))
        try:
            app = QGuiApplication.instance()
            app.screenRemoved.connect(lambda *_a: QTimer.singleShot(250, self.clamp_all))
            app.screenAdded.connect(lambda *_a: QTimer.singleShot(250, self.clamp_all))
        except Exception:
            pass

    # -- window list -------------------------------------------------------
    def windows(self, visible_only=False):
        try:
            ws = list(self._windows_fn() or [])
        except Exception:
            ws = []
        out = []
        for w in ws:
            try:
                if visible_only and not (w.isVisible() or w.isMinimized()):
                    continue
                if not visible_only and not (w.isVisible() or w.isMinimized()):
                    continue
                out.append(w)
            except RuntimeError:
                continue
        return out

    def current(self):
        w = QApplication.activeWindow()
        return w if w is not None else (self.windows() or [None])[0]

    # -- event hook --------------------------------------------------------
    def eventFilter(self, obj, event):
        try:
            et = event.type()
            if et not in self._EVENTS:
                return False
            if not isinstance(obj, QWidget) or not obj.isWindow():
                return False
            if et == QEvent.Type.Show:
                # R32.1: *every* top-level tool window qualifies, not only QDialog /
                # QMainWindow.  Plain QWidget windows (Export Jobs, Render Queue, Post-Process,
                # Batch Export ...) used to stay transient satellites of Main and were
                # minimised with it.  Popups, tooltips, splash screens, Qt.Tool palettes and
                # menus keep their native behaviour.
                if _is_tool_window(obj):
                    make_independent(obj)
                    restore_geometry(obj)
            elif et in (QEvent.Type.Move, QEvent.Type.Resize):
                if bool(obj.property("grooveboxGeometryRestored")):
                    remember_geometry(obj)
            elif et in (QEvent.Type.Hide, QEvent.Type.Close):
                if bool(obj.property("grooveboxGeometryRestored")):
                    remember_geometry(obj)
        except Exception:
            pass
        return False

    def clamp_all(self):
        for w in self.windows():
            clamp_on_screen(w)

    # -- actions -----------------------------------------------------------
    def snap_current(self, where):
        snap(self.current(), where)

    def minimize_current(self):
        w = self.current()
        try:
            if w is not None and not bool(w.property("grooveboxMainLocked")):
                w.showMinimized()
        except Exception:
            pass

    def tile_all(self):
        tile([w for w in self.windows() if not w.isMinimized()])

    def cascade_all(self):
        cascade([w for w in self.windows() if not w.isMinimized()])

    def minimize_all(self):
        minimize_all(self.windows())

    def restore_all(self):
        restore_all(self.windows())

    def next_window(self):
        cycle(self.windows(), 1)

    def prev_window(self):
        cycle(self.windows(), -1)

    def install_shortcuts(self, owner):
        """Application-context shortcuts on ``owner`` (the main window)."""
        if self._shortcuts:
            return
        self._owner_ref = weakref.ref(owner)
        combos = (
            (("Meta+Left", "Ctrl+Alt+Left"), lambda: self.snap_current("left")),
            (("Meta+Right", "Ctrl+Alt+Right"), lambda: self.snap_current("right")),
            (("Meta+Up", "Ctrl+Alt+Up"), lambda: self.snap_current("max")),
            (("Meta+Down", "Ctrl+Alt+Down"), self.minimize_current),
            (("Ctrl+Alt+D",), self.minimize_all),
            (("Ctrl+Alt+R",), self.restore_all),
            (("Ctrl+Alt+T",), self.tile_all),
            (("Ctrl+Alt+C",), self.cascade_all),
            (("Ctrl+`",), self.next_window),
            (("Ctrl+Shift+`", "Ctrl+~"), self.prev_window),
        )
        for keys, fn in combos:
            for k in keys:
                try:
                    sc = QShortcut(QKeySequence(k), owner)
                    sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
                    sc.activated.connect(fn)
                    self._shortcuts.append(sc)
                except Exception:
                    pass

    def build_arrange_menu(self, menu):
        """Fill a QMenu with the arrange actions (used by the window strip)."""
        menu.clear()
        for label, fn in (("⬅ Snap active window left\tCtrl+Alt+←", lambda: self.snap_current("left")),
                          ("➡ Snap active window right\tCtrl+Alt+→", lambda: self.snap_current("right")),
                          ("⬆ Maximise / restore\tCtrl+Alt+↑", lambda: self.snap_current("max")),
                          ("◎ Centre active window", lambda: self.snap_current("center")),
                          (None, None),
                          ("⊞ Tile all windows\tCtrl+Alt+T", self.tile_all),
                          ("❐ Cascade windows\tCtrl+Alt+C", self.cascade_all),
                          ("▁ Minimise all (show desktop)\tCtrl+Alt+D", self.minimize_all),
                          ("▣ Restore all\tCtrl+Alt+R", self.restore_all),
                          (None, None),
                          ("↻ Next window\tCtrl+`", self.next_window),
                          ("↺ Previous window\tCtrl+Shift+`", self.prev_window),
                          ("⌖ Bring every window onto this screen", self.clamp_all)):
            if label is None:
                menu.addSeparator()
            else:
                menu.addAction(label, fn)
        return menu

    def window_context_menu(self, w, parent=None, close_fn=None):
        m = QMenu(parent)
        m.addAction("▣ Restore / focus", lambda: (w.showNormal() if w.isMinimized() else None, _activate(w)))
        if not bool(w.property("grooveboxMainLocked")):
            m.addAction("▁ Minimise", w.showMinimized)
        m.addAction("⬆ Maximise / restore", lambda: snap(w, "max"))
        m.addAction("⬅ Snap left", lambda: snap(w, "left"))
        m.addAction("➡ Snap right", lambda: snap(w, "right"))
        m.addAction("◎ Centre", lambda: snap(w, "center"))
        m.addAction("⌖ Move onto this screen", lambda: clamp_on_screen(w))
        if close_fn is not None:
            m.addSeparator()
            m.addAction("✕ Close", lambda: close_fn(w))
        return m


_MANAGER = None


def install(app, windows_fn, owner=None):
    """Install (once) and return the app-wide WindowManager."""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = WindowManager(windows_fn, app)
        app.installEventFilter(_MANAGER)
    if owner is not None:
        _MANAGER.install_shortcuts(owner)
    return _MANAGER


def manager():
    return _MANAGER
