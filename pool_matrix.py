"""POOL_MATRIX_20261112: install sCode pool structures as descriptors, never as live pools.

Builds the multidimensional pool matrix and writes it where the engines can
read it. Does not create a thread, a process, or a queue.
"""
from __future__ import annotations
import json, os

def _current(app):
    """Read the settings that change the picture. No process, no queue."""
    import process_predict as pp
    lanes, pools = list(pp.LANES), list(pp.POOLS)
    try:
        import compat_settings as cs
        s = cs.load()
        quality = s.get("thread_quality", "balanced")
        threads = int(s.get("threads", 0) or 0)
        if quality == "max":
            for p in pools:
                p["width"] = p["width"] + 1
        elif quality == "compatibility":
            for p in pools:
                p["width"] = max(1, p["width"] - 1)
        if threads > 0:
            for lane in lanes:
                if lane["pool"] in ("export", "scode"):
                    lane["width"] = max(1, min(threads, 4))
    except Exception:
        pass
    return lanes, pools


def refresh(app):
    import process_predict as pp
    lanes, pools = _current(app)
    app._pool_matrix = pp.pool_matrix(pools)
    app._lane_predictions = pp.predict(lanes)
    base = getattr(app, "project_dir", None) or os.path.expanduser("~/.groovebox")
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "pool-matrix.json")
    with open(path, "w") as f:
        json.dump({"pools": app._pool_matrix, "predictions": app._lane_predictions}, f, indent=1)
    return app._pool_matrix


def install(app):
    refresh(app)
    try:
        from PyQt6.QtCore import QTimer
        timer = QTimer(app)
        timer.setInterval(8000)
        timer.timeout.connect(lambda: refresh(app))
        timer.start()
        app._pool_matrix_timer = timer
    except Exception:
        pass
    return app._pool_matrix
