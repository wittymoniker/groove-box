"""GROOVEBOX_R124_ERROR_REPORT: one way to show a failure — exception type, message and the code location,
with the full traceback in the session log (run_groovebox.py tees stdout/stderr into it).

A bare "-3" (str(KeyError(-3))) told the user nothing; this always says e.g.
"KeyError: -3 — markov_resampler.py:212 in resample".
"""
from __future__ import annotations

import os
import sys
import traceback


def describe(exc):
    tb = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    where = ""
    if tb:
        f = tb[-1]
        where = f" — {os.path.basename(f.filename)}:{f.lineno} in {f.name}"
    return f"{type(exc).__name__}: {exc}{where}"


def log(title, exc):
    print(f"\n[Error] {title}: {describe(exc)}", file=sys.stderr)
    traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)


def report(parent, title, exc, modal=True):
    log(title, exc)
    msg = f"{title} failed:\n{describe(exc)}\n\nThe full traceback is in the session log (Help ▸ logs)."
    try:
        if modal:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(parent, title, msg)
        else:
            parent.statusBar().showMessage(msg.replace("\n", "  "), 12000)
    except Exception:
        pass


def install_slot_hook(app):
    """Uncaught exceptions inside Qt slots (e.g. a randomizer button) also show in the status bar, with
    the type and location, instead of failing silently. The previous hook still runs (crash log)."""
    prev = sys.excepthook
    if getattr(prev, "_gb_r124", False):
        return

    def hook(t, v, tb, _prev=prev):
        try:
            _prev(t, v, tb)
        except Exception:
            pass
        try:
            v.__traceback__ = tb
            app.statusBar().showMessage("Action failed: " + describe(v) + "  (details in the session log)", 15000)
        except Exception:
            pass
    hook._gb_r124 = True
    sys.excepthook = hook
