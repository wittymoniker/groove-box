"""Lightweight, read-only Seed / Canonical / User / Step UI contribution badges.

Badges are tiny child labels over the corner of a control. They never change the
control's value, do not install polling timers, and can be refreshed on demand.
"""
from __future__ import annotations

try:
    from PyQt6.QtCore import Qt, QEvent, QObject
    from PyQt6.QtWidgets import QLabel, QWidget
except Exception:  # keep headless/build tools importable
    Qt = QEvent = QObject = QLabel = QWidget = None

_COLORS = {"seed": "#78b9ff", "canonical": "#d7a6ff", "user": "#7ee0a1", "step": "#ffc96b"}
_LETTERS = (("seed", "S"), ("canonical", "C"), ("user", "U"), ("step", "P"), ("effective", "N"))


def _present(data, key):
    if not isinstance(data, dict):
        return False
    flag = data.get("has_" + key)
    if flag is not None:
        return bool(flag)
    return data.get(key) is not None


def format_snapshot(data):
    if not isinstance(data, dict):
        return ""
    parts = []
    for key, title in (("seed", "Seed"), ("canonical", "Canonical"), ("user", "User"), ("step", "Step")):
        if _present(data, key):
            parts.append(f"{title}={data.get(key)!r}")
    if "effective" in data:
        parts.append(f"Net={data.get('effective')!r}")
    if not parts:
        return "No explicit source contribution is currently tracked for this control."
    return "Contribution detail · " + " · ".join(parts)


class _BadgeFilter(QObject):
    def __init__(self, widget, badge):
        super().__init__(widget)
        self.widget = widget
        self.badge = badge

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Move):
            _place_badge(self.widget, self.badge)
        return False



def _place_badge(widget, badge):
    """Keep provenance marks visible without covering native spinbox arrows."""
    try:
        cls = widget.metaObject().className()
    except Exception:
        cls = type(widget).__name__
    reserve = 20 if "SpinBox" in str(cls) else 3
    width = min(badge.width(), max(1, widget.width() - reserve - 2))
    x = max(1, widget.width() - width - reserve)
    badge.setGeometry(x, 1, width, badge.height())

def attach(widget, data=None, *, compact=True):
    """Attach or update a source badge for a Qt control. Safe to call repeatedly."""
    if QLabel is None or widget is None:
        return None
    try:
        if not isinstance(widget, QWidget):
            return None
        badge = getattr(widget, "_gb_provenance_badge", None)
        if badge is None:
            badge = QLabel(widget)
            badge.setObjectName("gbParameterProvenanceBadge")
            badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            badge.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedHeight(16)
            badge.setFixedWidth(72 if compact else 92)
            badge.setStyleSheet(
                "QLabel{background:rgba(5,12,22,238);border:1px solid rgba(190,218,238,210);"
                "border-radius:5px;padding:0px 3px;font-size:9px;font-weight:1000;}"
            )
            filt = _BadgeFilter(widget, badge)
            widget.installEventFilter(filt)
            widget._gb_provenance_badge = badge
            widget._gb_provenance_filter = filt
            # A subtle but clear control rim distinguishes authored/derived
            # parameters from surrounding panel chrome. Install only once.
            try:
                widget.setProperty("gbProvenanceActive", True)
                base_style = str(widget.styleSheet() or "")
                widget._gb_provenance_base_style = base_style
                rim = ("\nQDoubleSpinBox[gbProvenanceActive=\"true\"],"
                       "QSpinBox[gbProvenanceActive=\"true\"],"
                       "QComboBox[gbProvenanceActive=\"true\"],"
                       "QLineEdit[gbProvenanceActive=\"true\"],"
                       "QPushButton[gbProvenanceActive=\"true\"],"
                       "QCheckBox[gbProvenanceActive=\"true\"]{border:2px solid #6686a6;"
                       "border-radius:5px;padding:2px;}"
                       "QSlider[gbProvenanceActive=\"true\"]::groove:horizontal{height:7px;"
                       "background:#25384b;border:1px solid #6887a4;border-radius:4px;}"
                       "QSlider[gbProvenanceActive=\"true\"]::handle:horizontal{width:13px;"
                       "margin:-5px 0;background:#d8e9f7;border:2px solid #477da6;border-radius:6px;}")
                widget.setStyleSheet(base_style + rim)
                widget.style().unpolish(widget); widget.style().polish(widget)
            except Exception:
                pass
        data = dict(data or {})
        chunks = []
        title = []
        for key, letter in _LETTERS:
            if _present(data, key):
                chunks.append(f'<span style="color:{_COLORS[key]}">{letter}</span>')
                title.append(f"{letter}={data.get(key)!r}")
        badge.setText("·".join(chunks) if chunks else "")
        badge.setVisible(bool(chunks))
        badge.raise_()
        _place_badge(widget, badge)
        detail = format_snapshot(data)
        old_tip = str(widget.toolTip() or "")
        marker = "\n\n[Contribution provenance]"
        if marker in old_tip:
            old_tip = old_tip.split(marker, 1)[0]
        widget.setToolTip(old_tip + marker + "\n" + detail)
        widget.setProperty("gb_provenance", data)
        return badge
    except Exception:
        return None


def attach_tree(root, resolver=None):
    """Attach read-only contribution badges to numeric/editable controls in a panel.

    resolver(widget) may return a provenance dictionary; widgets without a source
    record are left alone rather than displaying invented ownership.
    """
    if QWidget is None or root is None:
        return 0
    try:
        from PyQt6.QtWidgets import QAbstractButton, QComboBox, QSlider, QSpinBox, QDoubleSpinBox, QLineEdit
        types = (QSlider, QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QAbstractButton)
        widgets = [root] + list(root.findChildren(QWidget))
    except Exception:
        return 0
    count = 0
    for widget in widgets:
        if not isinstance(widget, types):
            continue
        try:
            data = resolver(widget) if callable(resolver) else None
            if isinstance(data, dict) and data:
                attach(widget, data); count += 1
        except Exception:
            continue
    return count


def refresh_many(items):
    """items is an iterable of (widget, contribution dict) pairs."""
    for widget, data in items or ():
        attach(widget, data)
