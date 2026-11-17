"""resource_supervisor.py — memory / CPU / threads / audio health, runaway workers, adaptive Autopilot cadence.
Status-bar label updated every 2 s from /proc (cheap). Audio first: when the UI loop lags or the Live Player
underruns, allowed_rate() lowers the Autopilot authoring cadence until things recover."""
from __future__ import annotations
import os, threading, time

_S = {"lag": 0.0, "underruns": 0, "under_delta": 0, "cpu": 0.0, "rss": 0, "threads": 0, "t": 0.0, "cpu_t": 0.0}


def _rss():
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return 0


def sample(app):
    now = time.monotonic(); cpu = sum(os.times()[:2])
    if _S["t"]:
        _S["cpu"] = 100.0 * (cpu - _S["cpu_t"]) / max(1e-3, now - _S["t"])
        _S["lag"] = max(0.0, (now - _S["t"]) - 2.0)
    _S["t"], _S["cpu_t"] = now, cpu
    _S["rss"] = _rss(); _S["threads"] = threading.active_count()
    lp = getattr(app, "_live_player_window", None)
    eng = getattr(lp, "engine", None) if lp is not None else None
    u = int(getattr(eng, "underruns", 0) or 0)
    _S["under_delta"] = max(0, u - _S["underruns"]); _S["underruns"] = u
    # runaway / abandoned workers: a tracked child process whose job is no longer running
    stale = 0
    try:
        sch = getattr(app, "_export_scheduler_obj", None)
        running = sum(1 for j in (getattr(sch, "jobs", []) or []) if str(getattr(j, "state", "")).lower() == "running")
        procs = [p for p in (getattr(app, "_tracked_children", None) or []) if p is not None]
        from PyQt6.QtCore import QProcess
        alive = [p for p in procs if p.state() != QProcess.ProcessState.NotRunning]
        stale = max(0, len(alive) - running - (1 if getattr(app, "_export_worker_busy", False) else 0))
    except Exception:
        pass
    _S["stale_workers"] = stale
    return dict(_S)


def allowed_rate(app, wanted):
    """Autopilot cadence the system can afford now (audio and UI first)."""
    r = float(wanted)
    if _S["under_delta"] > 0:
        r = min(r, 1.0)
    if _S["lag"] > 0.25:
        r = min(r, 2.0)
    elif _S["lag"] > 0.08:
        r = min(r, 4.5)
    if _S["cpu"] > 180:
        r = min(r, 2.0)
    return max(0.333, r)


def install(app):
    if getattr(app, "_resource_supervisor", None) is not None:
        return
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QLabel
    lab = QLabel(""); lab.setStyleSheet("color:#9fd4ff;padding:0 6px;")
    t = QTimer(app); t.setInterval(2000)

    def tick():
        s = sample(app)
        warn = []
        if s["under_delta"]: warn.append("audio underrun")
        if s["lag"] > 0.25: warn.append("UI lag %.0f ms" % (s["lag"] * 1000))
        if s.get("stale_workers"): warn.append("%d idle worker(s)" % s["stale_workers"])
        lab.setText("⚙ CPU %.0f %% · RAM %.2f GB · thr %d%s" % (s["cpu"], s["rss"] / 1e9, s["threads"],
                                                               (" · ⚠ " + ", ".join(warn)) if warn else ""))
    t.timeout.connect(tick); t.start(); tick()
    try:
        app.statusBar().addPermanentWidget(lab)
    except Exception:
        pass
    app._resource_supervisor = (lab, t)
