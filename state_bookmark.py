"""STATE_BOOKMARK_20261112: save and recall a composition snapshot."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QInputDialog
import os, json, time

def _path(app):
    base = getattr(app, "project_dir", None) or os.path.expanduser("~/.groovebox")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "bookmarks.json")

def _load(app):
    p = _path(app)
    if os.path.isfile(p):
        try:
            return json.load(open(p))
        except Exception:
            pass
    return []

def _save(app, items):
    json.dump(items, open(_path(app), "w"), indent=1)

def open_window(app, parent=None):
    w = QWidget(parent)
    w.setWindowTitle("Bookmarks")
    w.setMinimumSize(320, 280)
    lay = QVBoxLayout(w)
    lst = QListWidget()
    def refresh():
        lst.clear()
        for b in _load(app):
            lst.addItem(b.get("name", "bookmark"))
    refresh()
    lay.addWidget(lst, 1)
    row = QHBoxLayout()
    b_add = QPushButton("Save current")
    def add():
        name, ok = QInputDialog.getText(w, "Bookmark", "Name:")
        if not ok or not name.strip():
            return
        items = _load(app)
        fp = ""
        try:
            import pathway_hub as hub
            fp = hub.fingerprint(app)
            hub.stamp(app, "bookmark", {"name": name.strip()})
        except Exception:
            pass
        items.append({"name": name.strip(), "time": time.time(), "fingerprint": fp,
                      "bpm": float(getattr(getattr(app, "spin_bpm", None), "value", lambda: 120)())})
        _save(app, items); refresh()
    b_add.clicked.connect(add)
    b_del = QPushButton("Delete")
    def delete():
        row_i = lst.currentRow()
        if row_i < 0:
            return
        items = _load(app)
        items.pop(row_i)
        _save(app, items); refresh()
    b_del.clicked.connect(delete)
    row.addWidget(b_add); row.addWidget(b_del)
    lay.addLayout(row)
    w.show(); w.raise_()
    return w
