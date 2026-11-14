"""SHORTCUT_CARD_20261112: the keys that matter, in one place."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

KEYS = """
Ctrl+K            command palette
Ctrl+,            System Settings
Ctrl+Caps Lock    toggle display
Ctrl+Alt+Left     snap window left
Ctrl+Alt+Right    snap window right
Ctrl+Alt+Up       maximise / restore
Ctrl+Alt+T        tile all windows
Ctrl+Alt+C        cascade windows
Ctrl+Alt+D        minimise all
Ctrl+Alt+R        restore all
Ctrl+`            next window
Tab / Shift+Tab   change instrument
"""

def open_window(app, parent=None):
    w = QWidget(parent)
    w.setWindowTitle("Shortcuts")
    w.setMinimumSize(360, 320)
    lay = QVBoxLayout(w)
    ed = QTextEdit(); ed.setReadOnly(True); ed.setPlainText(KEYS.strip())
    lay.addWidget(ed)
    w.show(); w.raise_()
    return w


# WINDOW_KEEPER_20261112: parentless windows used to be garbage-collected the moment they opened.
import window_keeper as _window_keeper  # noqa: E402
open_window = _window_keeper.kept(open_window)
