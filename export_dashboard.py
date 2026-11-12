"""EXPORT_DASHBOARD_20261112: a plain view of every export job."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLabel

def open_window(app, parent=None):
    w = QWidget(parent)
    w.setWindowTitle("Export Dashboard")
    w.setMinimumSize(420, 300)
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel("Running, queued, and finished export jobs."))
    lst = QListWidget()
    lay.addWidget(lst, 1)
    def refresh():
        lst.clear()
        try:
            import pathway_hub as hub
            hub.stamp(app, "export_view", {})
        except Exception:
            pass
        sch = getattr(app, "_export_scheduler_obj", None)
        jobs = getattr(sch, "jobs", []) if sch is not None else []
        if not jobs:
            lst.addItem("No jobs.")
            return
        for j in jobs:
            lst.addItem("%s  %s  %d%%" % (getattr(j, "state", "?"), getattr(j, "name", "job"), int(getattr(j, "progress", 0))))
    row = QHBoxLayout()
    b = QPushButton("Refresh")
    b.clicked.connect(refresh)
    row.addWidget(b); row.addStretch(1)
    lay.addLayout(row)
    refresh()
    w.show(); w.raise_()
    return w
