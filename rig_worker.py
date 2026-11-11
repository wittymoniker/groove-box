"""LIVE_4K_PROCESS_RIG_R31: one video-rig render process (frame-parallel live video).

    python rig_worker.py PROJECT.MCC

Loads the frozen project into its own headless engine, then serves frames over stdin/stdout:

  request  (stdin):  JSON line {"fi": int, "w": int, "h": int, "ph": float, "t": float, "n": samples}
                     followed by n float32 little-endian samples (the live output window)
  reply    (stdout): JSON line {"fi": int, "w": int, "h": int, "ok": bool, "err": str}
                     followed by w*h*3 RGB bytes when ok

Each process has its own interpreter and GIL, so K workers render K frames truly in parallel.
"""
from __future__ import annotations

import json
import os
import sys

_QAPP = None
_APP = None
_PROTO = None


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import parent_watch
        parent_watch.start()               # PARENT_WATCH_R31: no orphan renders after a crash
    except Exception:
        pass
    if not argv:
        print(__doc__, file=sys.stderr)
        return 64
    # The frame protocol owns the real stdout. Everything else the app prints (Python or C level)
    # goes to stderr, so a status line can never corrupt a frame header.
    global _PROTO
    _PROTO = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["GROOVEBOX_HEADLESS_WORKER"] = "1"
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        os.nice(5)                                   # below the UI / audio of the live player
    except Exception:
        pass
    import numpy as np
    from PyQt6.QtWidgets import QApplication
    global _QAPP, _APP
    _QAPP = QApplication.instance() or QApplication(["rig_worker"])
    import groovebox as g
    app = _APP = g.MathematiciansGrooveboxApp()
    try:
        t = getattr(app, "_autosave_timer", None)
        if t is not None:
            t.stop()
    except Exception:
        pass
    if not app.open_project_path(argv[0], show_message=False):
        sys.stderr.write("rig_worker: project could not be loaded\n")
        return 2
    _aim = getattr(app, "active_instrument_memory", None)
    nmem = len(_aim) if hasattr(_aim, "__len__") else int(getattr(app, "synth_count", 48) or 48)
    try:   # R32.8 RIG_EXPORT_PARITY: same engine configuration as the main export
        import live_player as _lp
        eng = _lp.clone_export_engine(g, app, nmem)
    except Exception:
        eng = g.VideoSynthEngine(nmem)
        if hasattr(eng, "bind_app"):
            eng.bind_app(app)
    eng.fps = 30.0
    norm = float(getattr(g, "MEUM_NORM", 1.0))
    inp = sys.stdin.buffer
    out = _PROTO
    out.write(b'{"ready": true}\n'); out.flush()
    while True:
        line = inp.readline()
        if not line:
            return 0
        try:
            req = json.loads(line.decode("utf-8"))
        except Exception:
            continue
        n = int(req.get("n", 0) or 0)
        raw = inp.read(4 * n) if n > 0 else b""
        fi, w, h = int(req.get("fi", 0)), int(req.get("w", 320)), int(req.get("h", 180))
        try:
            wave = np.frombuffer(raw, dtype="<f4") if raw else np.zeros(1024, np.float32)
            eng.set_waveform(np.array(wave, dtype=np.float32), playhead=float(req.get("ph", 0.0)))
            eng.t = float(req.get("t", 0.0)) * norm
            fr = eng.render_frame(w, h, export=True, frame_index=fi)
            fr = np.nan_to_num(np.asarray(fr), nan=0, posinf=255, neginf=0).astype(np.uint8, copy=False)
            try:
                fr = app._apply_video_plan_to_frame(fr, fi, max(1, int(req.get("nf", 1))))
            except Exception:
                pass
            fr = np.ascontiguousarray(np.asarray(fr)[:, :, :3], dtype=np.uint8)
            hdr = {"fi": fi, "w": int(fr.shape[1]), "h": int(fr.shape[0]), "ok": True, "err": ""}
            out.write((json.dumps(hdr) + "\n").encode("utf-8")); out.write(fr.tobytes()); out.flush()
        except Exception as exc:
            out.write((json.dumps({"fi": fi, "w": 0, "h": 0, "ok": False, "err": str(exc)[:300]}) + "\n").encode("utf-8"))
            out.flush()


if __name__ == "__main__":
    sys.exit(main())
