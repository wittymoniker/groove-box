"""scode_coordinator.py — sCode coordinates the thread directions and the process tree under the main tree.

Directions (highest priority first). Each direction is one sCode lane on the shared, CPU- and memory-aware pool
(thread_budget), so a direction never creates its own threads, and higher directions are served first when the pool
is busy:
    audio        live audio fx / analysis (never the device callback itself — that stays on its own thread)
    ui-offload   work moved off the Qt thread (results are committed back on the Qt thread)
    canonical    canonical engine and distribution work
    video        video synth, rig frames, atlas videos
    hybrid       hybrid-language kernels (NumPy / Rust / LuaJIT / Julia / native)
    scripts      Lua workspace and seed scripts
    export       in-process export preparation (the export workers themselves are processes)
    programs     Program Builder compiles and runs
    background   indexing, scans, caches
The process tree: the main process (Qt thread + lanes) → child processes registered by the spawn policy
(process_policy: engine, render, encode, media, helper, game, app, other) with pid, kind, age and CPU.
direct(direction, fn, *a)  submit work in a direction · lane(direction) the lane · tree() the whole picture
"""
from __future__ import annotations
import os, threading, time

DIRECTIONS = (("audio", "interactive", 2), ("ui-offload", "interactive", 2), ("canonical", None, 2), ("video", None, 3),
              ("hybrid", None, 2), ("scripts", None, 1), ("export", None, 2), ("programs", None, 1), ("background", None, 1))
PRIORITY = {d: i for i, (d, _k, _w) in enumerate(DIRECTIONS)}
_LANES = {}
_LOCK = threading.Lock()
_COUNT = {}


def lane(direction):
    with _LOCK:
        ln = _LANES.get(direction)
        if ln is not None:
            return ln
        kind, w = next(((k, w) for d, k, w in DIRECTIONS if d == direction), (None, 1))
        try:
            import thread_budget as tb
            w = max(1, min(w, tb.lane_workers()))
            ln = tb.make_lane("scode-" + direction, max_workers=w, max_pending=256, kind=kind)
        except Exception:
            from concurrent.futures import ThreadPoolExecutor
            ln = ThreadPoolExecutor(max_workers=w, thread_name_prefix="scode-" + direction)
        _LANES[direction] = ln
        return ln


def direct(direction, fn, *args, **kwargs):
    """Run fn in a direction; returns a future. Higher directions are submitted with higher priority."""
    _COUNT[direction] = _COUNT.get(direction, 0) + 1
    ln = lane(direction)
    sp = getattr(ln, "submit_prioritized", None)
    if callable(sp):
        return sp(PRIORITY.get(direction, 9), fn, *args, **kwargs)
    return ln.submit(fn, *args, **kwargs)


def _cpu(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            parts = f.read().rsplit(")", 1)[1].split()
        return (int(parts[11]) + int(parts[12])) / float(os.sysconf("SC_CLK_TCK"))
    except Exception:
        return None


def tree():
    """{'main': {...}, 'directions': [...], 'lanes': [...], 'children': [...]} — the whole picture, read-only."""
    out = {"main": {"pid": os.getpid(), "threads": threading.active_count(), "cpu_s": _cpu(os.getpid())}}
    out["directions"] = [{"direction": d, "priority": PRIORITY[d], "submitted": _COUNT.get(d, 0),
                          "workers": getattr(_LANES.get(d), "max_workers", getattr(_LANES.get(d), "_max_workers", None))}
                         for d, _k, _w in DIRECTIONS]
    try:
        import thread_budget as tb
        out["lanes"] = tb.lane_report(48)
        out["pool"] = {"shared": tb.lane_workers(), "engine": tb.engine_workers(), "interactive": tb.interactive_workers(),
                       "bulk": tb.bulk_workers(), "cores": tb.usable_cores()}
    except Exception:
        out["lanes"] = []
    kids = []
    try:
        import process_policy as pp
        for p in pp.children():
            kids.append({"pid": p.pid, "kind": getattr(p, "groovebox_kind", "other"),
                         "age_s": round(time.time() - float(getattr(p, "groovebox_started", time.time())), 1),
                         "cpu_s": _cpu(p.pid), "argv": " ".join(map(str, (getattr(p, "args", None) or [])[:4]))[:120]})
    except Exception:
        pass
    out["children"] = kids
    return out


def open_window(app):
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🌳 sCode tree · directions, lanes, processes"); w.resize(860, 560)
    lay = QVBoxLayout(w); lab = QLabel(""); lay.addWidget(lab); tw = QTreeWidget(); tw.setHeaderLabels(["node", "detail"]); lay.addWidget(tw)

    def fill():
        t = tree(); tw.clear()
        m = QTreeWidgetItem(["main process %d" % t["main"]["pid"], "%d threads · CPU %.1f s" % (t["main"]["threads"], t["main"]["cpu_s"] or 0)])
        tw.addTopLevelItem(m)
        dn = QTreeWidgetItem(["sCode directions", "highest priority first"]); m.addChild(dn)
        for d in t["directions"]:
            dn.addChild(QTreeWidgetItem([d["direction"], "priority %d · %d submitted · workers %s" % (d["priority"], d["submitted"], d["workers"] or "—")]))
        ln = QTreeWidgetItem(["lanes on the shared pool", str(t.get("pool", ""))]); m.addChild(ln)
        for r in t["lanes"]:
            ln.addChild(QTreeWidgetItem([str(r.get("name", r) if isinstance(r, dict) else r), str({k: v for k, v in r.items() if k != "name"}) if isinstance(r, dict) else ""]))
        ch = QTreeWidgetItem(["child processes", "%d" % len(t["children"])]); m.addChild(ch)
        for c in t["children"]:
            ch.addChild(QTreeWidgetItem(["%s · pid %d" % (c["kind"], c["pid"]), "age %.0f s · CPU %s s · %s" % (c["age_s"], c["cpu_s"], c["argv"])]))
        try:                               # R101: unified compute front door: strands (carrier/dims) and costs
            import compute
            cp = QTreeWidgetItem(["compute front door", "carrier strands · kernels · pure cache"]); m.addChild(cp)
            for line in compute.report().splitlines()[2:14]:
                if line.strip():
                    cp.addChild(QTreeWidgetItem([line.strip()[:60], line.strip()[60:]]))
        except Exception:
            pass
        tw.expandAll(); lab.setText("Updated %s" % time.strftime("%H:%M:%S"))
    t = QTimer(w); t.setInterval(2000); t.timeout.connect(lambda: fill() if w.isVisible() else None); t.start(); fill()
    w.show(); app._scode_tree = w
    return w
