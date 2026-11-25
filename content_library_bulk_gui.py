
"""Minimal Content Library bulk actions GUI (move/rename/trash placeholders wired to catalog)."""
from __future__ import annotations

def open_window(app=None):
    try:
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
            QLineEdit, QMessageBox, QFileDialog,
        )
        from PyQt6.QtCore import Qt
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    dlg = QDialog(app if app is not None else None)
    dlg.setWindowTitle("Content Library · bulk")
    dlg.resize(640, 480)
    dlg.setStyleSheet("QDialog{background:#0a1218;color:#c8e6d8;} QPushButton{background:#123040;color:#5cf2b0;padding:6px;border-radius:4px;}")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Multi-select style list · rename / trash mark · open folder"))
    lst = QListWidget()
    lst.setSelectionMode(lst.SelectionMode.ExtendedSelection)
    lay.addWidget(lst, 1)
    # populate from content_library if present
    items = []
    try:
        import content_library as cl
        for name in ("catalog", "list_items", "iter_entries", "scan"):
            fn = getattr(cl, name, None)
            if callable(fn):
                try:
                    items = list(fn() or [])
                except TypeError:
                    items = list(fn(None) or [])
                break
    except Exception as exc:
        lay.addWidget(QLabel(f"catalog: {exc}"))
    if not items:
        items = ["(no catalog entries — library modules optional)", "sample-project", "seed-pack"]
    for it in items[:200]:
        lst.addItem(str(it if not isinstance(it, dict) else it.get("name") or it.get("path") or it))

    rename = QLineEdit()
    rename.setPlaceholderText("rename selected to…")
    lay.addWidget(rename)

    def do_rename():
        sel = lst.selectedItems()
        if not sel or not rename.text().strip():
            QMessageBox.information(dlg, "Rename", "Select one item and type a new name.")
            return
        sel[0].setText(rename.text().strip())
        QMessageBox.information(dlg, "Rename", "UI rename applied (persist via Content Library save when available).")

    def do_trash():
        for it in lst.selectedItems():
            t = it.text()
            if not t.startswith("[trash] "):
                it.setText("[trash] " + t)

    def do_open():
        try:
            folder = str(getattr(app, "_exports_dir", lambda: ".")())
        except Exception:
            folder = "."
        QMessageBox.information(dlg, "Folder", folder)

    row = QHBoxLayout()
    for lab, fn in (("Rename", do_rename), ("Mark trash", do_trash), ("Exports folder", do_open)):
        b = QPushButton(lab); b.clicked.connect(fn); row.addWidget(b)
    lay.addLayout(row)
    dlg.setModal(False); dlg.show()
    return dlg
