"""Open the folder of the most recent finished export and copy its path."""
from __future__ import annotations
import os

def open_window(app, parent=None):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QApplication
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtCore import QUrl
    win = QDialog(None)
    win.setWindowTitle("Last export")
    lay = QVBoxLayout(win)
    path = ""
    try:
        sch = getattr(app, "_export_scheduler_obj", None)
        done = [j for j in getattr(sch, "jobs", []) if j.state == "done"]
        if done:
            path = str(done[-1].result.get("file_path") or done[-1].out_file or "")
    except Exception:
        path = ""
    lab = QLabel(path or "no finished export yet")
    lab.setWordWrap(True)
    lay.addWidget(lab)
    def _open():
        folder = os.path.dirname(path) if path else ""
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
    b = QPushButton("Open folder")
    b.clicked.connect(_open)
    c = QPushButton("Copy path")
    c.clicked.connect(lambda: QApplication.clipboard().setText(path))
    lay.addWidget(b); lay.addWidget(c)
    win.show(); win.raise_(); return win


# WINDOW_KEEPER_20261112: parentless windows used to be garbage-collected the moment they opened.
import window_keeper as _window_keeper  # noqa: E402
open_window = _window_keeper.kept(open_window)


def record_mgr_preview(path, kind="audio"):
    """Remember a playable sibling so UI can open last export quickly."""
    try:
        import json, os, time
        from pathlib import Path as P
        base = P(path).with_suffix("")
        meta = {"path": str(path), "kind": kind, "ts": time.time()}
        for cand in (str(path) + ".preview.wav", str(path) + ".wav", str(path)):
            if os.path.isfile(cand):
                meta["playable"] = cand
                break
        out = P(path).parent / ".last_export_mgr.json"
        tmp = str(out) + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        os.replace(tmp, out)
        return str(out)
    except Exception:
        return ""
