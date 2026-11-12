"""SESSION_NOTES_20261112: a scratch pad that rides with the session."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer
import os, json

def _path(app):
    base = getattr(app, "project_dir", None) or os.path.expanduser("~/.groovebox")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "session-notes.txt")

def open_window(app, parent=None):
    w = QWidget(parent)
    w.setWindowTitle("Session Notes")
    w.setMinimumSize(420, 300)
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel("Notes for this session. Saved next to the project."))
    ed = QTextEdit()
    p = _path(app)
    if os.path.isfile(p):
        ed.setPlainText(open(p).read())
    lay.addWidget(ed, 1)
    row = QHBoxLayout()
    b = QPushButton("Save")
    def save():
        open(p, "w").write(ed.toPlainText())
        try:
            import pathway_hub as hub
            hub.stamp(app, "notes", {"chars": len(ed.toPlainText())})
        except Exception:
            pass
        b.setText("Saved")
        QTimer.singleShot(1200, lambda: b.setText("Save"))
    b.clicked.connect(save)
    row.addWidget(b); row.addStretch(1)
    lay.addLayout(row)
    w.show(); w.raise_()
    return w
