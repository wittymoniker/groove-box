"""Export render worker (EXPORT_WORKER_20261102).

The main window packs the canonical project document (the same document Save writes) and starts this
program as a separate process. The worker loads the document into its own headless engine, renders the
shared mixdown buffer, and writes it as a float32 .npy plus a small JSON note. The main window keeps its
own thread, GIL and event loop, so scrolling, editing and playing stay smooth while a long render runs.

    python export_worker.py JOB.json

JOB.json: {"project": "<project .MCC path>", "sample_rate": 48000, "out_npy": "...", "out_meta": "...",
           "kind": "audio", "purpose": "Export prepare"}

Progress lines on stdout:  PROGRESS <0-100> <text>   and finally   DONE <out_npy>   (or   FAIL <message>).
"""
from __future__ import annotations

import json
import os
import sys


def _say(*parts):
    print(" ".join(str(p) for p in parts), flush=True)


def run(job: dict) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import numpy as np
    from PyQt6.QtWidgets import QApplication
    qa = QApplication.instance() or QApplication(["export_worker"])
    _say("PROGRESS", 2, "worker starting")
    import groovebox as g
    app = g.MathematiciansGrooveboxApp()
    _say("PROGRESS", 8, "engine ready")
    if not app.open_project_path(job["project"], show_message=False):
        _say("FAIL", "project document could not be loaded")
        return 2
    _say("PROGRESS", 15, "project loaded")
    sr = int(job.get("sample_rate") or 0)
    if sr > 0:
        app.preferred_sample_rate = sr
    try:
        app._set_work_progress = lambda label, pct, text="": _say("PROGRESS", 15 + int(max(0, min(100, pct)) * 0.8), text)
    except Exception:
        pass
    # EXPORT_SNAPSHOT_20261102: the render reads its settings from this snapshot; without it the worker rendered
    # the defaults (120 bpm, 32 rows) instead of the project's own values.
    app._snapshot_render_inputs()
    mr = job.get("max_rows")
    buf, rate = app._get_shared_mixdown_buffer(max_rows=(int(mr) if mr else None),
                                               purpose=str(job.get("purpose") or "Export prepare"), force=True)
    buf = np.ascontiguousarray(np.asarray(buf, dtype=np.float32))
    if job.get("final"):
        # GROOVEBOX_R23R_EXPORT_MERGE_20261103: Batch Export — this project's own DJ bake +
        # master volume + hard clip, so each file is exactly what its project would export.
        _say("PROGRESS", 96, "master bus")
        try:
            buf = app._bake_dj_write(buf, rate)
        except Exception:
            pass
        buf, _info = app._master_hardclip(buf, rate, apply_master_vol=True)
        buf = np.ascontiguousarray(np.asarray(buf, dtype=np.float32))
    np.save(job["out_npy"], buf)
    with open(job["out_meta"], "w", encoding="utf-8") as f:
        json.dump({"sample_rate": int(rate), "frames": int(buf.shape[0]), "channels": 1 if buf.ndim == 1 else int(buf.shape[1]),
                   "final": bool(job.get("final"))}, f)
    _say("DONE", job["out_npy"])
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 64
    try:
        with open(argv[0], "r", encoding="utf-8") as f:
            job = json.load(f)
        return run(job)
    except Exception as exc:  # report, never hang the caller
        _say("FAIL", f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
