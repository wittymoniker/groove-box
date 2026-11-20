"""GROOVEBOX_R124_SAFE_MODE: start safely after a crash.

A sentinel file (~/.local/share/groovebox/running.lock) is written at start and removed on a clean
quit. If it is still there at the next start, the previous run crashed: ``startup(app)`` then offers
safe mode — heavy engines off (smooth mode on, hybrid pool / Julia warm-up / autopilot / 3-D studio
deferred), and restores the last checkpoint if the user agrees. GROOVEBOX_SAFE_MODE=1 forces it.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _dir():
    d = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "groovebox"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sentinel():
    return _dir() / "running.lock"


def crashed_last_time():
    return sentinel().is_file()


def mark_running():
    sentinel().write_text(json.dumps({"pid": os.getpid(), "started": time.time()}), encoding="utf-8")


def mark_clean_exit():
    try:
        sentinel().unlink()
    except FileNotFoundError:
        pass


def enter_safe_mode(app):
    os.environ["GROOVEBOX_SAFE_MODE"] = "1"
    try:
        import compat_settings as cs
        cs.update(smooth_mode="on")
    except Exception:
        pass
    for attr in ("autopilot_timer", "_autopilot_timer", "_hybrid_pool_timer"):
        t = getattr(app, attr, None)
        try:
            t.stop()
        except Exception:
            pass
    app._r124_safe_mode = True
    try:
        app.statusBar().showMessage("SAFE MODE: heavy engines are off. Settings ▸ Science & Live ▸ Leave safe mode", 0)
    except Exception:
        pass


def latest_checkpoint():
    try:
        import project_transactions as pt
        files = pt.checkpoints()
        return files[0] if files else None
    except Exception:
        pass
    return None


def startup(app, ask=True):
    from PyQt6.QtWidgets import QApplication, QMessageBox
    crashed = crashed_last_time() or os.environ.get("GROOVEBOX_SAFE_MODE") == "1"
    mark_running()
    try:
        QApplication.instance().aboutToQuit.connect(mark_clean_exit)
    except Exception:
        pass
    if not crashed:
        return False
    if not ask:
        enter_safe_mode(app); return True
    ck = latest_checkpoint()
    box = QMessageBox(app); box.setWindowTitle("Groovebox did not close cleanly")
    box.setText("The last session ended unexpectedly.\n\nStart in safe mode (heavy engines off)?"
                + ("\nThe last checkpoint can be restored too." if ck else ""))
    b_safe = box.addButton("Safe mode", QMessageBox.ButtonRole.AcceptRole)
    b_restore = box.addButton("Safe mode + restore checkpoint", QMessageBox.ButtonRole.ActionRole) if ck else None
    box.addButton("Normal start", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    c = box.clickedButton()
    if c in (b_safe, b_restore):
        enter_safe_mode(app)
        if c is b_restore and ck:
            try:
                import project_transactions as pt
                pt.restore(app, ck)
            except Exception as exc:
                print(f"[safe mode] restore failed: {exc}")
        return True
    return False


def leave_safe_mode(app):
    os.environ.pop("GROOVEBOX_SAFE_MODE", None)
    app._r124_safe_mode = False
    try:
        app.statusBar().showMessage("Safe mode off — heavy engines may run again.", 5000)
    except Exception:
        pass
