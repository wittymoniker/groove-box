"""toolbar_fit.py — R33: wide toolbar strips scroll sideways instead of widening the window.

A QToolBar whose content is ONE wide widget (Quick Rack, Cloud Command Center, the window bar) cannot move
items into its » overflow menu, so its minimum width is the widget's full width. Three such toolbars on one
row made the main window's minimum width 6,344 px: on a 1366 / 1920 px screen most of the window was off the
monitor (buttons unreachable) and the main-window pin kept fighting the layout (the window froze in a resize
loop). Wrapping the widget in a frameless scroll area gives the toolbar a small minimum width; the strip
scrolls sideways (wheel or Shift+wheel over it, or its thin scrollbar) when the window is narrower.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QObject, QEvent
from PyQt6.QtWidgets import QScrollArea, QFrame

MIN_STRIP_WIDTH = 160
_BAR = 8   # thin horizontal scrollbar height (px)


class _WheelSideways(QObject):
    """A vertical wheel over a strip scrolls it sideways (there is nothing to scroll vertically)."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Wheel:
            area = self.parent()
            bar = area.horizontalScrollBar()
            if bar.maximum() > 0:
                d = ev.angleDelta()
                bar.setValue(bar.value() - (d.y() or d.x()))
                return True
        return False


class _Strip(QScrollArea):
    """Asks for its content's full width (so a wide screen shows everything) but can shrink to MIN_STRIP_WIDTH."""

    def sizeHint(self):
        w = self.widget()
        h = super().sizeHint()
        if w is not None:
            h.setWidth(w.sizeHint().width() + 2)
        return h


def scroll_strip(widget, parent=None, height=None):
    """Return a frameless, sideways-scrolling container holding `widget`, for QToolBar.addWidget()."""
    area = _Strip(parent)
    area.setObjectName("toolbarFitStrip")
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    h = int(height or max(widget.sizeHint().height(), widget.minimumSizeHint().height(), 20))
    area.setFixedHeight(h + _BAR)
    area.setMinimumWidth(MIN_STRIP_WIDTH)
    area.horizontalScrollBar().setStyleSheet("QScrollBar:horizontal{height:%dpx;}" % _BAR)
    f = _WheelSideways(area)
    area.viewport().installEventFilter(f)
    area._toolbar_fit_filter = f
    return area


def fit_toolbars(main, max_ratio=0.9):
    """Report toolbars that still force the window wider than its screen (for diagnostics / tests)."""
    from PyQt6.QtWidgets import QToolBar
    out = []
    try:
        avail = main.screen().availableGeometry().width()
    except Exception:
        return out
    for tb in main.findChildren(QToolBar):
        if tb.isVisible() and tb.minimumSizeHint().width() > max_ratio * avail:
            out.append((tb.objectName(), tb.minimumSizeHint().width()))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Tabs and windows that would not fit the screen.
# Every QTabWidget gets a "▾" corner button listing all its tabs (visible only when the tabs overflow the bar), and
# a top-level window that opens larger than the screen's free area is shrunk and moved inside it.
class _FitFilter(QObject):
    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if t == QEvent.Type.Show:
                from PyQt6.QtWidgets import QTabWidget, QWidget
                if isinstance(obj, QTabWidget):
                    _tab_menu(obj)
                elif isinstance(obj, QWidget) and obj.isWindow():
                    _clamp_window(obj)
            elif t == QEvent.Type.Resize:
                from PyQt6.QtWidgets import QTabWidget
                if isinstance(obj, QTabWidget):
                    _sync_tab_menu(obj)
        except Exception:
            pass
        return False


def _tab_menu(tw):
    from PyQt6.QtWidgets import QToolButton, QMenu
    if getattr(tw, "_fit_tab_menu", None) is not None:
        _sync_tab_menu(tw)
        return
    b = QToolButton(tw)
    b.setText("▾")
    b.setToolTip("All tabs")
    b.setAutoRaise(True)
    b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    m = QMenu(b)

    def _fill():
        m.clear()
        for i in range(tw.count()):
            a = m.addAction(tw.tabText(i).replace("&", "") or ("Tab %d" % (i + 1)))
            a.setCheckable(True)
            a.setChecked(i == tw.currentIndex())
            a.setEnabled(tw.isTabEnabled(i))
            a.triggered.connect(lambda _c=False, k=i: tw.setCurrentIndex(k))
    m.aboutToShow.connect(_fill)
    b.setMenu(m)
    if tw.cornerWidget(Qt.Corner.TopRightCorner) is None:
        tw.setCornerWidget(b, Qt.Corner.TopRightCorner)
    tw._fit_tab_menu = b
    tw.tabBar().setUsesScrollButtons(True)
    tw.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
    _sync_tab_menu(tw)


def _sync_tab_menu(tw):
    b = getattr(tw, "_fit_tab_menu", None)
    if b is None:
        return
    bar = tw.tabBar()
    need = bar.sizeHint().width() > max(1, tw.width() - 40) or tw.count() > 12
    if b.isVisible() != need and tw.cornerWidget(Qt.Corner.TopRightCorner) is b:
        b.setVisible(need)


def _clamp_window(w):
    try:
        if w.isMaximized() or w.isFullScreen():
            return
        scr = w.screen() or (w.windowHandle().screen() if w.windowHandle() else None)
        if scr is None:
            return
        av = scr.availableGeometry()
        g = w.frameGeometry()
        nw, nh = min(w.width(), int(av.width() * 0.98)), min(w.height(), int(av.height() * 0.96))
        if (nw, nh) != (w.width(), w.height()):
            w.setMinimumSize(min(w.minimumWidth(), nw), min(w.minimumHeight(), nh))
            w.resize(nw, nh)
        g = w.frameGeometry()
        x = min(max(av.left(), g.left()), av.right() - g.width() + 1)
        y = min(max(av.top(), g.top()), av.bottom() - g.height() + 1)
        if (x, y) != (g.left(), g.top()):
            w.move(x, y)
    except Exception:
        pass


_FIT = [None]


def install_fit_filter(app=None):
    """App-wide (Show / Resize only, cheap): tab overflow dropdowns + windows clamped to the screen."""
    from PyQt6.QtWidgets import QApplication
    qa = QApplication.instance()
    if qa is None or _FIT[0] is not None:
        return _FIT[0]
    _FIT[0] = _FitFilter(qa)
    qa.installEventFilter(_FIT[0])
    return _FIT[0]
