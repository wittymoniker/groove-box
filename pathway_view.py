"""PATHWAY_VIEW_20261112: show the shared packet log."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QLabel

def open_window(app, parent=None):
    w = QWidget(parent)
    w.setWindowTitle("Pathways")
    w.setMinimumSize(460, 320)
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel("What the tools have written, with the seed fingerprint."))
    ed = QTextEdit(); ed.setReadOnly(True)
    lay.addWidget(ed, 1)
    def refresh():
        try:
            import pathway_hub as hub
            rows = hub.recent(app)
            if not rows:
                ed.setPlainText("Nothing yet. Save a note, a bookmark, or a theme.")
                return
            lines = []
            for r in rows:
                p = r.get("packet", {})
                lines.append("%s  %s  seed %s" % (r.get("kind", "?"), p.get("fingerprint", ""), p.get("seed", "")))
            ed.setPlainText("\n".join(lines))
        except Exception as exc:
            ed.setPlainText(str(exc))
    b = QPushButton("Refresh")
    b.clicked.connect(refresh)
    lay.addWidget(b)
    refresh()
    w.show(); w.raise_()
    return w
