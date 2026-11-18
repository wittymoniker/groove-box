"""panel_translucency.py — every panel that is not primary interactive UI gets noticeable transparency, so the
parametric math background and Party Mode show through. Group boxes, frames and scroll-area viewports have their own
background colour turned into the same colour at `alpha` (default 72 %). Buttons, inputs, sliders, combo boxes,
tables and text editors (the primary interactive UI) keep solid backgrounds. Runs once after the window is built and
again when a window opens (cheap: only stylesheet text is rewritten)."""
from __future__ import annotations
import re

ALPHA = 0.72
_HEX = re.compile(r"(background(?:-color)?\s*:\s*)#([0-9a-fA-F]{6})\b")
_BLOCK = re.compile(r"((?:QGroupBox|QFrame|QWidget|QScrollArea)[^{]*\{)([^}]*)(\})")


def _rgba(m, a):
    h = m.group(2)
    return "%srgba(%d,%d,%d,%d)" % (m.group(1), int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(255 * a))


_RGB = re.compile(r"(background(?:-color)?\s*:\s*)rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")

# R101: colour + translucency for the key working panels (title substring -> tint rgb), like the rest of the UI
TINTS = (("CANONICAL MORPH", (150, 110, 230)), ("MODULATION ROUTES", (90, 170, 230)), ("XMOD", (90, 200, 200)),
         ("WINDOW MODULATION", (90, 200, 200)), ("MODULATION", (110, 160, 220)), ("MULTIDIM", (170, 120, 240)),
         ("AUTOMATION", (220, 170, 90)), ("TASK PAD", (60, 140, 180)))


def tint_sheet(rgb, a=0.55):
    r, g, b = rgb
    return ("QGroupBox{background:rgba(%d,%d,%d,%d);border:1px solid rgba(%d,%d,%d,150);border-radius:8px;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:9px;padding:0 4px;color:rgb(%d,%d,%d);font-weight:900;}"
            % (r // 7, g // 7, b // 7, int(255 * a), r, g, b, min(255, r + 60), min(255, g + 60), min(255, b + 40)))


def soften(ss, a=ALPHA):
    if not ss or "background" not in ss:
        return ss
    rgb = lambda t: _RGB.sub(lambda m: "%srgba(%s,%s,%s,%d)" % (m.group(1), m.group(2), m.group(3), m.group(4), int(255 * a)), t)
    if "{" not in ss:                       # a plain declaration list applies to the widget itself
        return rgb(_HEX.sub(lambda m: _rgba(m, a), ss))
    return _BLOCK.sub(lambda b: b.group(1) + rgb(_HEX.sub(lambda m: _rgba(m, a), b.group(2))) + b.group(3), ss)


def apply(root, a=ALPHA):
    from PyQt6.QtWidgets import QGroupBox, QFrame, QScrollArea, QAbstractScrollArea, QTextEdit, QPlainTextEdit, QTableView, QListView, QAbstractItemView
    n = 0
    for w in [root] + root.findChildren(QFrame) + root.findChildren(QGroupBox):
        try:
            if isinstance(w, (QTextEdit, QPlainTextEdit, QAbstractItemView)) or w.property("_r99_soft"):
                continue
            ss = w.styleSheet()
            if isinstance(w, QGroupBox) and not w.property("_r101_tint"):
                ttl = (w.title() or "").upper()
                hit = next((rgb for key, rgb in TINTS if key in ttl), None)
                if hit is not None and "background" not in ss:
                    w.setStyleSheet(ss + tint_sheet(hit)); w.setProperty("_r101_tint", True); n += 1
                    ss = w.styleSheet()
            new = soften(ss, a)
            if new != ss:
                w.setStyleSheet(new); n += 1
            w.setProperty("_r99_soft", True)
            if isinstance(w, QScrollArea):
                vp = w.viewport()
                if vp is not None:
                    vp.setAutoFillBackground(False); w.setStyleSheet(w.styleSheet() + " QScrollArea{background:transparent;}")
        except RuntimeError:
            continue
    return n


def install(app):
    from PyQt6.QtCore import QTimer, QObject, QEvent
    from PyQt6.QtWidgets import QApplication, QWidget
    QTimer.singleShot(2500, lambda: apply(app))

    class F(QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow() and not obj.property("_r99_soft_win"):
                obj.setProperty("_r99_soft_win", True)
                QTimer.singleShot(0, lambda o=obj: _safe(o))
            return False
    app._soft_filter = F(app); QApplication.instance().installEventFilter(app._soft_filter)


def _safe(o):
    try:
        apply(o)
    except Exception:
        pass
