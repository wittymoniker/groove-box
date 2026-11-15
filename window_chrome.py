"""Shared, non-invasive window chrome for MATGROOVEBOX Qt windows."""
from __future__ import annotations

SCROLLBAR_STYLESHEET = r"""
QScrollBar:vertical {
    background: #09131e; width: 11px; margin: 3px 2px 3px 2px;
    border: 1px solid #263c51; border-radius: 5px;
}
QScrollBar:horizontal {
    background: #09131e; height: 11px; margin: 2px 3px 2px 3px;
    border: 1px solid #263c51; border-radius: 5px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #267e83; border: 1px solid #51c6c2; border-radius: 4px;
    min-height: 28px; min-width: 28px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #35b9b0; border: 1px solid #8af1dc;
}
QScrollBar::handle:vertical:pressed, QScrollBar::handle:horizontal:pressed {
    background: #b18a3e; border: 1px solid #f0d18a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 9px; background: #172738; border: 1px solid #304a61; border-radius: 3px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 9px; background: #172738; border: 1px solid #304a61; border-radius: 3px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: #0d1a27;
}
QSplitter::handle {
    background: #245b68; border: 1px solid #347e86; border-radius: 2px;
}
QSplitter::handle:hover { background: #36aaa7; border-color: #82e7d8; }
"""


def install(app=None) -> bool:
    """Append shared scrollbar/splitter styling without replacing app styling."""
    if app is None:
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
        except Exception:
            app = None
    if app is None:
        return False
    try:
        current = app.styleSheet() or ""
        marker = "/* MATGROOVEBOX_SHARED_WINDOW_CHROME */"
        if marker not in current:
            app.setStyleSheet(current + "\n" + marker + "\n" + SCROLLBAR_STYLESHEET)
        return True
    except Exception:
        return False
