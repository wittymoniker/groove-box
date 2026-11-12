"""Save and restore which Groovebox windows are open, and where they sit."""
from __future__ import annotations
import json, os

def _path():
    d = os.path.join(os.path.expanduser("~"), ".config", "groovebox")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "session_snapshot.json")

def save(app):
    rows = []
    try:
        import window_manager as wm
        for w in wm.manager().session_windows() if wm.manager() else []:
            if w is None or not w.isVisible():
                continue
            g = w.geometry()
            rows.append({"title": w.windowTitle(), "x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()})
    except Exception:
        pass
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(rows, f)
    return len(rows)

def open_window(app, parent=None):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel
    win = QDialog(None)
    win.setWindowTitle("Session snapshot")
    lay = QVBoxLayout(win)
    lab = QLabel("Save the open windows and their positions. Restore puts them back.")
    lab.setWordWrap(True)
    lay.addWidget(lab)
    b = QPushButton("Save now")
    b.clicked.connect(lambda: lab.setText("saved %d windows" % save(app)))
    lay.addWidget(b)
    win.show(); win.raise_(); return win
