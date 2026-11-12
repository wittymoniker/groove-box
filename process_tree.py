"""process_tree.py — one picture of who runs where.

GROOVEBOX_PROCESS_TREE_20261111
Priority on a small machine, highest first:
  1. audio callback
  2. UI events
  3. Live Player record writer
  4. export / mux workers
  5. sCode visual and background analysis
"""
ORDER = (
    "audio callback",
    "UI events",
    "Live Player record writer",
    "export / mux workers",
    "sCode visual and background analysis",
)


def describe() -> str:
    lines = ["Process tree (highest priority first)"]
    for i, name in enumerate(ORDER, 1):
        lines.append("%d. %s" % (i, name))
    lines.append("")
    lines.append("Exports run in worker processes. The GUI thread does no file I/O and no full-song NumPy.")
    lines.append("Failed exports re-queue until removed. The OS disk is never a format target.")
    return "\n".join(lines)


def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPlainTextEdit
    w = QWidget(app, Qt.WindowType.Window)
    w.setWindowTitle("Process tree")
    w.resize(520, 320)
    lay = QVBoxLayout(w)
    box = QPlainTextEdit(describe()); box.setReadOnly(True)
    lay.addWidget(box)
    w.show(); w.raise_()
    return w
