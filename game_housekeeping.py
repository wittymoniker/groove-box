"""game_housekeeping.py — GROOVEBOX_R32_GAME_HOUSEKEEPING_20261110

* watch(proc, folder): the unpacked game folder (groovebox_game_*) is deleted when the game exits.
* sweep(): routine removal of stale extracts — game folders, live-take temp, rig temp, Qt playable
  copies — older than their age limit and not in use (run at start and every 30 minutes).
* savestates: one per game per Groovebox in <system store>/state/games/<fingerprint>.json;
  list / delete one / delete all (Game Editor buttons).
"""
from __future__ import annotations

import glob
import os
import shutil
import tempfile
import time

_WATCH = []
PATTERNS = (("groovebox_game_*", 3600), ("gb-live-take-*", 86400), ("gb-rig-*", 3600), ("groovebox_qt_play", 3 * 86400))


def _in_use():
    return {f for _p, f in _WATCH}


_TIMER = {"t": None}


def watch(proc, folder):
    """One shared 2 s timer for every running game (a second game no longer replaces the first one's timer)."""
    from PyQt6.QtCore import QTimer
    _WATCH.append((proc, folder))
    if _TIMER["t"] is not None:
        return
    t = _TIMER["t"] = QTimer(); t.setInterval(2000)

    def tick():
        for p, f in list(_WATCH):
            if p.poll() is not None:
                _WATCH.remove((p, f)); shutil.rmtree(f, ignore_errors=True)
        if not _WATCH:
            t.stop(); _TIMER["t"] = None
    t.timeout.connect(tick); t.start()


def sweep():
    removed = 0; now = time.time(); busy = _in_use()
    for pat, age in PATTERNS:
        for p in glob.glob(os.path.join(tempfile.gettempdir(), pat)):
            try:
                if p in busy or now - os.path.getmtime(p) < age:
                    continue
                if os.path.isdir(p):
                    if pat == "groovebox_qt_play":
                        for f in os.listdir(p):
                            fp = os.path.join(p, f)
                            if now - os.path.getmtime(fp) > age:
                                os.remove(fp); removed += 1
                        continue
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
                removed += 1
            except Exception:
                pass
    return removed


def start(app):
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(20000, sweep)
    t = QTimer(app); t.setInterval(30 * 60 * 1000); t.timeout.connect(sweep); t.start(); app._game_sweep_timer = t


def savestate_dir():
    import groovebox_paths as gp
    return os.path.join(gp.system_root(), "state", "games")


def savestates():
    return sorted(glob.glob(os.path.join(savestate_dir(), "*.json")))


def delete_savestate(fingerprint=None):
    """Delete one game's savestate (fingerprint) or all (None). Returns how many were removed."""
    n = 0
    for p in savestates():
        if fingerprint is None or os.path.basename(p) == "%s.json" % fingerprint:
            try:
                os.remove(p); n += 1
            except Exception:
                pass
    return n
