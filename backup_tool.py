"""BACKUP_TOOL_20261112: copy the project folder to a timestamped backup."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog
import os, shutil, time

def open_window(app, parent=None):
    w = QWidget(parent)
    w.setWindowTitle("Backup")
    w.setMinimumSize(360, 160)
    lay = QVBoxLayout(w)
    lbl = QLabel("Copy the project folder to a dated backup.")
    lbl.setWordWrap(True)
    lay.addWidget(lbl)
    def run():
        src = getattr(app, "project_dir", None) or os.getcwd()
        dest = QFileDialog.getExistingDirectory(w, "Backup into")
        if not dest:
            return
        name = "groovebox-backup-%s" % time.strftime("%Y%m%d-%H%M%S")
        target = os.path.join(dest, name)
        shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
        lbl.setText("Saved to %s" % target)
    b = QPushButton("Choose folder and back up")
    b.clicked.connect(run)
    lay.addWidget(b)
    lay.addStretch(1)
    w.show(); w.raise_()
    return w
