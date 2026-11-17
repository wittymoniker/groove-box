"""Global workload precedence and multidimensional pool/thread admission.

The planner is advisory: it never creates threads or changes canonical project
state. 'sniff' is a cheap pressure observation; 'huff' is a bounded admission
request for non-real-time work. Audio/GUI responsiveness always wins.
"""
from __future__ import annotations
import os
import threading
import time

_LOCK = threading.RLock()
_LAST = {"at": 0.0, "cpu": None, "memory": None}
_PRIORITY = {
    "audio_rt": 100, "gui": 95, "device_io": 90, "visual_preview": 75,
    "edit_together": 65, "interactive": 60, "export": 35, "background": 20,
}


def sniff(force=False):
    """Low-cost, cached system pressure sample; optional psutil, never required."""
    now = time.monotonic()
    with _LOCK:
        if not force and now - _LAST["at"] < 1.0:
            return dict(_LAST)
    cpu = memory = None
    try:
        import psutil
        cpu = float(psutil.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        memory = {"available": int(vm.available), "percent": float(vm.percent)}
    except Exception:
        try:
            from memory_guard import snapshot
            m = snapshot()
            memory = {"available": int(m.get("available", 0) or 0),
                      "percent": None}
        except Exception:
            pass
    sample = {"at": now, "cpu": cpu, "memory": memory}
    with _LOCK:
        _LAST.update(sample)
    return dict(sample)


def plan(pending=None):
    """Return one shared precedence plan; widths are ceilings, not promises."""
    pending = dict(pending or {})
    try:
        import thread_budget as tb
        total = max(1, int(tb.lane_workers()))
        heavy = max(1, int(tb.memory_worker_cap(total, heavy=True)))
        light = max(1, int(tb.memory_worker_cap(total, heavy=False)))
    except Exception:
        total = max(1, min(4, (os.cpu_count() or 1) - 1))
        heavy, light = 1, total
    pressure = sniff()
    cpu = pressure.get("cpu")
    constrained = (cpu is not None and cpu >= 88.0)
    # Reserve the one available lane for UI/audio on tiny machines. Visual and
    # collaboration share the remaining interactive budget, never oversubscribe.
    interactive = max(1, total - (1 if total > 1 else 0))
    visual = 1 if not constrained else 1
    collaboration = 1 if pending.get("edit_together", 0) else 0
    bulk = max(1, min(heavy, total - 1)) if total > 1 else 1
    return {
        "policy": "global-intelligence-precedence-v1",
        "workers_total_ceiling": total,
        "workers_light_ceiling": light,
        "workers_heavy_ceiling": heavy,
        "interactive_ceiling": interactive,
        "visual_preview_ceiling": visual,
        "edit_together_ceiling": collaboration,
        "bulk_ceiling": bulk,
        "priority": dict(_PRIORITY),
        "pressure": pressure,
        "pending": pending,
        "admission": "nonblocking-latest-wins",
    }


def huff(lane, pending=0):
    """Admission gate for bounded work; never blocks and never creates a pool."""
    lane = str(lane or "background")
    if lane in ("audio_rt", "gui", "device_io"):
        return True
    p = plan({lane: max(0, int(pending or 0))})
    pressure = p["pressure"]
    cpu = pressure.get("cpu")
    if lane == "visual_preview":
        return True  # latest-frame replacement is safer than stalling preview
    if lane == "edit_together":
        return True  # collaboration remains live; payload queues are bounded upstream
    if cpu is not None and cpu >= 96.0 and lane in ("export", "background"):
        return False
    return True


def describe_objectives():
    return {
        "sniff": "sample CPU and memory pressure cheaply and cache it",
        "huff": "admit bounded work without waiting or spawning workers",
        "repool": "recompute safe pool-width ceilings from current hardware headroom",
        "rethread": "reuse existing managed lanes; never add unbounded threads",
        "precedence": ["audio_rt", "gui", "device_io", "visual_preview", "edit_together", "interactive", "export", "background"],
    }
