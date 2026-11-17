"""Studio session: save and restore the working state — the Global Seed, Superseed and Starter Patch seed, the
session name, BPM, base frequency, the open project, and which windows are open and where they sit. Saved on quit
(and with "Save now"); "Restore last session" puts it all back."""
from __future__ import annotations
import json, os

FIELDS = (("input_seed_val", "seed"), ("input_superseed", "superseed"), ("input_starter_patch_seed", "starter_seed"))


def _path():
    d = os.path.join(os.path.expanduser("~"), ".config", "groovebox")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "session_snapshot.json")


def _text(w):
    try:
        return w.toPlainText() if hasattr(w, "toPlainText") else w.text()
    except Exception:
        return None


def _set_text(w, v):
    try:
        (w.setPlainText if hasattr(w, "setPlainText") else w.setText)(str(v))
    except Exception:
        pass


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
    state = {"version": 2, "windows": rows}
    for attr, key in FIELDS:
        w = getattr(app, attr, None)
        if w is not None:
            v = _text(w)
            if v is not None:
                state[key] = v
    for attr, key in (("spin_bpm", "bpm"), ("spin_base_frequency", "base_frequency")):
        try:
            state[key] = float(getattr(app, attr).value())
        except Exception:
            pass
    state["session_name"] = str(getattr(app, "_session_name", "") or "")
    state["project"] = str(getattr(app, "_current_project_path", "") or "")
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, _path())
    return len(rows)


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {"windows": st if isinstance(st, list) else []}
    except Exception:
        return {}


def restore(app, open_project=True):
    """Put the last session back: project (if it still exists), seeds, tempo, base frequency, name, window places."""
    st = load()
    if not st:
        return "no saved session"
    done = []
    pth = st.get("project") or ""
    try:
        import project_transactions as _pt
        _pt.checkpoint(app, "before-session-restore")
    except Exception:
        pass
    if open_project and pth and os.path.isfile(pth) and pth != str(getattr(app, "_current_project_path", "") or ""):
        try:
            app.open_project_path(pth, show_message=False); done.append("project")
        except Exception:
            pass
    for attr, key in FIELDS:
        w = getattr(app, attr, None)
        if w is not None and isinstance(st.get(key), str):
            _set_text(w, st[key]); done.append(key)
    for attr, key in (("spin_bpm", "bpm"), ("spin_base_frequency", "base_frequency")):
        try:
            if key in st:
                getattr(app, attr).setValue(float(st[key])); done.append(key)
        except Exception:
            pass
    if st.get("session_name") and hasattr(app, "set_session_name"):
        try:
            app.set_session_name(st["session_name"]); done.append("name")
        except Exception:
            pass
    try:
        from PyQt6.QtWidgets import QApplication
        by_title = {r.get("title"): r for r in st.get("windows", []) if isinstance(r, dict)}
        for w in QApplication.topLevelWidgets():
            r = by_title.get(w.windowTitle())
            if r and w.isVisible():
                w.setGeometry(int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"]))
    except Exception:
        pass
    return "restored " + ", ".join(done) if done else "nothing to restore"


def install_autosave(app):
    """Save the studio session when the application quits."""
    try:
        from PyQt6.QtWidgets import QApplication
        if not getattr(app, "_session_autosave_hooked", False):
            QApplication.instance().aboutToQuit.connect(lambda: save(app))
            app._session_autosave_hooked = True
    except Exception:
        pass


def open_window(app, parent=None):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel
    win = QDialog(None)
    win.setWindowTitle("Studio session")
    lay = QVBoxLayout(win)
    lab = QLabel("Saves the seeds, Superseed, Starter Patch seed, session name, BPM, base frequency, the open project "
                 "and the window layout (also automatically when Groovebox quits). Restore puts them back.")
    lab.setWordWrap(True)
    lay.addWidget(lab)
    b = QPushButton("💾 Save now")
    b.clicked.connect(lambda: lab.setText("saved (%d windows)" % save(app)))
    r = QPushButton("↺ Restore last session")
    r.clicked.connect(lambda: lab.setText(restore(app)))
    lay.addWidget(b); lay.addWidget(r)
    win.show(); win.raise_(); return win


# WINDOW_KEEPER_20261112: parentless windows used to be garbage-collected the moment they opened.
import window_keeper as _window_keeper  # noqa: E402
open_window = _window_keeper.kept(open_window)
