"""SESSION_NOTES_20261112: a scratch pad that rides with the session."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer
import os

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
        with open(p, encoding="utf-8", errors="replace") as fh:     # UTF8_IO_R6
            ed.setPlainText(fh.read())
    lay.addWidget(ed, 1)
    row = QHBoxLayout()
    b = QPushButton("Save")
    def _write():
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(ed.toPlainText())
        os.replace(tmp, p)

    def save():
        _write()
        try:
            import pathway_hub as hub
            hub.stamp(app, "notes", {"chars": len(ed.toPlainText())})
        except Exception:
            pass
        b.setText("Saved")
        QTimer.singleShot(1200, lambda: b.setText("Save"))
    b.clicked.connect(save)
    # NOTES_AUTOSAVE_R6: notes are saved 1.5 s after typing stops, so closing the window never loses them.
    auto = QTimer(w); auto.setSingleShot(True); auto.setInterval(1500)
    auto.timeout.connect(lambda: (_write(), b.setText("Saved"), QTimer.singleShot(1200, lambda: b.setText("Save"))))
    ed.textChanged.connect(auto.start)
    row.addWidget(b); row.addStretch(1)
    lay.addLayout(row)
    w.show(); w.raise_()
    return w


# WINDOW_KEEPER_20261112: parentless windows used to be garbage-collected the moment they opened.
import window_keeper as _window_keeper  # noqa: E402
open_window = _window_keeper.kept(open_window)
