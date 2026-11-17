"""project_transactions.py — checkpoints, unclean-exit recovery and one restore pathway.

checkpoint(app, label)   the complete project document (_project_snapshot: playlist, every sequence bank with its
                         per-sequence panels, instrument params, automation, R32 module state, UI controls) plus the
                         session extras (selected instrument / sequence, open export jobs, live-buffer descriptor),
                         written atomically to ~/.local/share/groovebox/checkpoints/. Newest 40 kept.
restore(app, path)       always through app._apply_project_snapshot — the same loader as File ▸ Open and Studio session.
Unclean exit             a marker file is written at startup and removed on a clean quit; if it is still there at the
                         next start, the Recovery window opens with the newest checkpoints.
Hooks                    Clear Memory and the Autopilot composer call checkpoint() before (and after) they change the
                         project. Nothing here runs on a timer.
"""
from __future__ import annotations

import json
import os
import time

KEEP = 40


def _dir():
    d = os.path.join(os.path.expanduser("~"), ".local", "share", "groovebox", "checkpoints")
    os.makedirs(d, exist_ok=True)
    return d


def _marker():
    return os.path.join(_dir(), "running.marker")


def _extras(app):
    ex = {}
    try:
        name = app.instrument_selector_dropdown.currentText()
        ex["selected_instrument"] = name
        ex["selected_sequence"] = int(app._current_sequence_index(name))
    except Exception:
        pass
    try:
        sch = getattr(app, "_export_scheduler_obj", None)
        ex["export_jobs"] = [{"id": getattr(j, "id", None), "kind": getattr(j, "kind", ""), "out": getattr(j, "out_file", ""),
                              "state": str(getattr(j, "state", "")), "label": getattr(j, "label", "")}
                             for j in (getattr(sch, "jobs", []) or [])]
    except Exception:
        pass
    try:
        import live_buffer
        ex["live_buffer"] = live_buffer.current_path(app)
    except Exception:
        pass
    ex["project_path"] = str(getattr(app, "_current_project_path", "") or "")
    return ex


def checkpoint(app, label="checkpoint"):
    """Write a recoverable checkpoint. Returns its path (or None if the snapshot failed)."""
    try:
        doc = app._project_snapshot()
    except Exception as exc:
        print(f"[Checkpoint] snapshot failed: {exc}")
        return None
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(label))[:40]
    path = os.path.join(_dir(), time.strftime("%Y%m%d-%H%M%S-") + "%03d-" % int(time.time() * 1000 % 1000) + safe + ".MCC")
    payload = dict(doc) if isinstance(doc, dict) else {"document": doc}
    payload["_checkpoint"] = {"label": str(label), "time": time.time(), **_extras(app)}
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=str)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    files = sorted((os.path.join(_dir(), n) for n in os.listdir(_dir()) if n.endswith(".MCC")), key=os.path.getmtime)
    for old in files[:-KEEP]:
        try:
            os.remove(old)
        except OSError:
            pass
    app._last_checkpoint = path
    return path


def checkpoints():
    files = [os.path.join(_dir(), n) for n in os.listdir(_dir()) if n.endswith(".MCC")]
    return sorted(files, key=os.path.getmtime, reverse=True)


def restore(app, path):
    """Restore a checkpoint through the one project loader, then the selection it was taken with."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.pop("_checkpoint", {}) if isinstance(data, dict) else {}
    app._apply_project_snapshot(data)
    try:
        name = meta.get("selected_instrument")
        if name:
            app.instrument_selector_dropdown.setCurrentText(name)
        sid = meta.get("selected_sequence")
        if sid and hasattr(app, "sequence_selector"):
            i = app.sequence_selector.findData(int(sid))
            if i >= 0:
                app.sequence_selector.setCurrentIndex(i)
    except Exception:
        pass
    if meta.get("project_path"):
        app._current_project_path = meta["project_path"]
    for fn in ("reload_active_instrument_sequencer_ui", "_push_restored_playlist_to_table", "_on_live_source_changed"):
        try:
            getattr(app, fn)()
        except Exception:
            pass
    return meta


def wrap(app, method, label, after=False):
    """Make app.<method> take a checkpoint before (and optionally after) it runs."""
    orig = getattr(app, method, None)
    if not callable(orig) or getattr(orig, "_txn_wrapped", False):
        return

    def run(*a, **k):
        try:
            checkpoint(app, "before-" + label)
        except Exception as exc:
            print(f"[Checkpoint] {label}: {exc}")
        out = orig(*a, **k)
        if after:
            try:
                checkpoint(app, "after-" + label)
            except Exception:
                pass
        return out
    run._txn_wrapped = True
    setattr(app, method, run)


def install(app):
    if getattr(app, "_txn_installed", False):
        return
    app._txn_installed = True
    unclean = os.path.isfile(_marker())
    try:
        with open(_marker(), "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    try:
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(lambda: os.path.isfile(_marker()) and os.remove(_marker()))
    except Exception:
        pass
    wrap(app, "_clear_project_memory", "clear-memory")
    wrap(app, "_configure_entire_project_from_seed", "configure-project", after=True)
    if unclean and checkpoints():
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: open_window(app, unclean=True))
        except Exception:
            pass


def open_window(app, unclean=False):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout
    d = QDialog(app); d.setWindowTitle("🛟 Project recovery")
    d.setWindowModality(Qt.WindowModality.NonModal); d.resize(640, 420)
    lay = QVBoxLayout(d)
    lay.addWidget(QLabel(("The application did not close normally last time. " if unclean else "") +
                         "Checkpoints are taken before Clear Memory, around Configure Entire Project and every Autopilot "
                         "project. Restoring uses the normal project loader; the current project is checkpointed first."))
    lst = QListWidget(); lay.addWidget(lst, 1)
    files = checkpoints()
    for p in files[:KEEP]:
        lst.addItem(os.path.basename(p))
    out = QLabel(""); lay.addWidget(out)
    row = QHBoxLayout(); lay.addLayout(row)
    b_restore = QPushButton("Restore selected"); b_now = QPushButton("Checkpoint now"); b_close = QPushButton("Close")
    for b in (b_restore, b_now, b_close):
        row.addWidget(b)

    def _restore():
        i = lst.currentRow()
        if i < 0:
            out.setText("Select a checkpoint."); return
        try:
            checkpoint(app, "before-restore")
            meta = restore(app, files[i])
            out.setText("Restored · %s" % meta.get("label", ""))
        except Exception as exc:
            out.setText("Restore failed: %s" % exc)
    b_restore.clicked.connect(_restore)
    b_now.clicked.connect(lambda: out.setText("Saved " + str(checkpoint(app, "manual"))))
    b_close.clicked.connect(d.close)
    d.show(); d.raise_()
    app._recovery_window = d
    return d
