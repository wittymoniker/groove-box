"""resource_governor.py — GROOVEBOX_R32_RESOURCE_GOVERNOR_20261109

Keeps process, memory and resource storage healthy for a long session:

  * watches this process's RSS (no psutil needed) every ``interval`` seconds, off the GUI
    thread; when it passes the soft limit it trims the caches that are safe to drop —
    compiled seed programs, the multidim voice memo and world records, the graph-context
    cache, Qt pixmap cache — and runs a generation-2 gc; at the hard limit it also asks
    long-lived windows to release their offscreen buffers (``release_resources()`` if they
    have it);
  * reaps finished child processes (process_policy.reap) so no zombie lingers;
  * records a small rolling history for the debug panel (``history()``).

Limits default to a share of physical memory (soft 55 %, hard 75 %) and can be overridden
with GROOVEBOX_MEM_SOFT_MB / GROOVEBOX_MEM_HARD_MB.
"""
from __future__ import annotations

import gc
import os
import sys
import threading
import time

_STATE = {"thread": None, "stop": False, "hist": [], "trims": 0, "last": {}}
_TRIMMERS = []           # callables run on soft trim
_RELEASERS = []          # weakrefs to objects with release_resources()


def rss_mb():
    """Resident set size in MB (Linux /proc first; resource module elsewhere)."""
    try:
        with open("/proc/self/statm") as f:
            pages = int(f.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / 2.0 ** 20
    except Exception:
        pass
    try:
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return r / 1024.0 if sys.platform.startswith("linux") else r / 2.0 ** 20
    except Exception:
        return 0.0


def total_mb():
    """Effective memory ceiling (container/cgroup limit when one is active)."""
    try:
        import memory_guard
        snap = memory_guard.snapshot(force=True)
        if snap.get("total", 0) > 0:
            return float(snap["total"]) / 2.0 ** 20
    except Exception:
        pass
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2.0 ** 20
    except Exception:
        return 8192.0


# R32.8 DYNAMIC_RAM: an adjustable budget (Monitor panel / compat "mem_budget_pct": 0 = auto) and
# a tier that sizes exports, video chunks, live-rig workers and caches, so small rigs (4–8 GB)
# stay responsive and large ones use their headroom. Re-read on every governor tick.
_BUDGET = {"pct": None}


def budget_pct():
    if _BUDGET["pct"] is None:
        try:
            import compat_settings as _cs
            _BUDGET["pct"] = int(_cs.load().get("mem_budget_pct", 0) or 0)
        except Exception:
            _BUDGET["pct"] = 0
    return int(_BUDGET["pct"] or 0)


def set_budget_pct(pct):
    pct = 0 if not pct else max(25, min(90, int(pct)))
    _BUDGET["pct"] = pct
    try:
        import compat_settings as _cs
        d = _cs.load(); d["mem_budget_pct"] = pct; _cs.save(d)
    except Exception:
        pass
    return pct


def available_mb():
    """Effective available memory, respecting cgroup ceilings as well as host RAM."""
    try:
        import memory_guard
        snap = memory_guard.snapshot(force=True)
        if snap.get("total", 0) > 0:
            return float(snap["available"]) / 2.0 ** 20
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    try:
        import psutil
        return psutil.virtual_memory().available / 2.0 ** 20
    except Exception:
        return total_mb() * 0.5


def tier():
    t = total_mb()
    return "small" if t < 6144 else ("medium" if t < 14336 else "large")


def recommend():
    """Sizes the rest of the program reads (tier × budget × current pressure)."""
    t = tier(); pct = budget_pct() or {"small": 50, "medium": 60, "large": 70}[t]
    budget = total_mb() * pct / 100.0
    pressure = available_mb() < total_mb() * 0.12
    rec = {"small": {"export_parallel": 1, "video_chunk": 6, "rig_workers": 1, "mixdown_cache": 1},
           "medium": {"export_parallel": 2, "video_chunk": 12, "rig_workers": 2, "mixdown_cache": 2},
           "large": {"export_parallel": 4, "video_chunk": 24, "rig_workers": 4, "mixdown_cache": 3}}[t].copy()
    rec["export_parallel"] = max(1, min(rec["export_parallel"], int(budget // 1500)))   # ~1.5 GB per export worker
    if pressure:
        rec = {k: max(1, v // 2) for k, v in rec.items()}
    rec.update({"tier": t, "budget_mb": int(budget), "budget_pct": pct, "pressure": pressure,
                "available_mb": int(available_mb())})
    return rec


def limits():
    tot = total_mb()
    pct = budget_pct()
    if pct:
        soft_d, hard_d = tot * pct / 100.0 * 0.8, tot * pct / 100.0
    else:
        soft_d, hard_d = tot * (0.45 if tier() == "small" else 0.55), tot * (0.65 if tier() == "small" else 0.75)
    soft = float(os.environ.get("GROOVEBOX_MEM_SOFT_MB", 0) or soft_d)
    hard = float(os.environ.get("GROOVEBOX_MEM_HARD_MB", 0) or hard_d)
    return soft, max(soft + 64, hard)


def register_trimmer(fn):
    """fn() is called on every soft trim (must be cheap and thread-safe)."""
    if callable(fn) and fn not in _TRIMMERS:
        _TRIMMERS.append(fn)


def register_releaser(obj):
    import weakref
    try:
        _RELEASERS.append(weakref.ref(obj))
    except TypeError:
        pass


def _default_trims():
    out = {}
    try:
        import seed_lang
        n = seed_lang.cache_stats().get("size", 0)
        seed_lang.clear_cache()
        out["seed_programs"] = n
    except Exception:
        pass
    try:
        import multidim_synth
        multidim_synth.memo_clear()
        multidim_synth.world_clear()
        out["multidim_memo"] = 1
    except Exception:
        pass
    gb = sys.modules.get("groovebox")
    if gb is not None:
        for w in list(getattr(gb, "_LIVE_APPS", []) or []):
            try:
                w._graph_context_cache = {}
                out["graph_context"] = 1
            except Exception:
                pass
    try:
        from PyQt6.QtGui import QPixmapCache
        QPixmapCache.clear()
        out["pixmap_cache"] = 1
    except Exception:
        pass
    for fn in list(_TRIMMERS):
        try:
            fn()
            out[getattr(fn, "__name__", "trimmer")] = 1
        except Exception:
            pass
    return out


def trim(hard=False):
    """Run the trims now (any thread).  Returns a report dict."""
    rep = {"rss_before": round(rss_mb(), 1), "hard": bool(hard)}
    rep.update(_default_trims())
    if hard:
        for ref in list(_RELEASERS):
            obj = ref()
            if obj is None:
                _RELEASERS.remove(ref)
                continue
            try:
                obj.release_resources()
                rep["released"] = rep.get("released", 0) + 1
            except Exception:
                pass
    try:
        gc.collect(2)
    except Exception:
        pass
    try:
        import process_policy
        rep["reaped"] = process_policy.reap()
    except Exception:
        pass
    rep["rss_after"] = round(rss_mb(), 1)
    _STATE["trims"] += 1
    _STATE["last"] = rep
    return rep


def _loop(interval):
    last_trim = 0.0
    while not _STATE["stop"]:
        time.sleep(interval)
        try:
            soft, hard = limits()                       # R32.8: follows the live budget
            r = rss_mb()
            if available_mb() < total_mb() * 0.06:      # whole-system pressure: trim even below our limits
                r = max(r, hard + 1)
            h = _STATE["hist"]
            h.append((time.time(), r))
            if len(h) > 360:
                del h[: len(h) - 360]
            try:
                import process_policy
                process_policy.reap()
            except Exception:
                pass
            now = time.monotonic()
            if r > hard and now - last_trim > 5.0:
                trim(hard=True)
                last_trim = now
            elif r > soft and now - last_trim > 20.0:
                trim(hard=False)
                last_trim = now
        except Exception:
            pass


def start(interval=10.0):
    """Start the governor thread (idempotent)."""
    if _STATE["thread"] is not None and _STATE["thread"].is_alive():
        return _STATE["thread"]
    _STATE["stop"] = False
    th = threading.Thread(target=_loop, args=(float(interval),), name="groovebox-resource-governor", daemon=True)
    th.start()
    _STATE["thread"] = th
    return th


def stop():
    _STATE["stop"] = True


def history():
    return list(_STATE["hist"])


def status():
    soft, hard = limits()
    return {"rss_mb": round(rss_mb(), 1), "soft_mb": round(soft), "hard_mb": round(hard), "trims": _STATE["trims"],
            "last": dict(_STATE["last"]), "running": bool(_STATE["thread"] and _STATE["thread"].is_alive())}


# ---------------------------------------------------------------------------
# HOUSEKEEPING (GROOVEBOX_R32_SELF_CLEAN_20261110) — runs once at startup on a worker thread
# ---------------------------------------------------------------------------
def housekeeping(max_temp_days=3, max_log_mb=10, part_days=14):
    """Self-cleaning: temp files older than 3 days, logs rotated past 10 MB, orphaned .lock /
    .tmp / .part.<pid>.tmp files, empty cache folders, stale analysis WAVs and __pycache__ of the
    app folder. Never touches projects, samples, exports or recordings themselves."""
    import shutil
    rep = {"removed": 0, "bytes": 0}
    now = time.time()

    def rm(p):
        try:
            n = os.path.getsize(p) if os.path.isfile(p) else 0
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            rep["removed"] += 1; rep["bytes"] += n
        except Exception:
            pass
    try:
        import groovebox_paths as gp
        for root in (gp.temp_dir(),):
            for dp, ds, fs in os.walk(root):
                for f in fs:
                    p = os.path.join(dp, f)
                    if now - os.path.getmtime(p) > max_temp_days * 86400:
                        rm(p)
        for dp, ds, fs in os.walk(gp.logs_dir()):
            for f in fs:
                p = os.path.join(dp, f)
                if os.path.getsize(p) > max_log_mb * 2 ** 20:
                    try:
                        os.replace(p, p + ".1")
                    except Exception:
                        pass
                elif f.endswith(".1") and now - os.path.getmtime(p) > 30 * 86400:
                    rm(p)
        for dp, ds, fs in os.walk(gp.projects_dir()):
            for f in fs:
                p = os.path.join(dp, f)
                if (f.endswith((".lock", ".tmp")) or ".part." in f and f.endswith(".tmp")) and now - os.path.getmtime(p) > 3600:
                    rm(p)
                elif f.endswith(".analysis.wav") and now - os.path.getmtime(p) > 86400:
                    rm(p)
            for d in list(ds):
                full = os.path.join(dp, d)
                if d == "cache" and os.path.isdir(full) and not os.listdir(full):
                    pass
    except Exception:
        pass
    try:
        import tempfile, glob
        for p in glob.glob(os.path.join(tempfile.gettempdir(), "groovebox_analyze_*.wav")) + \
                glob.glob(os.path.join(tempfile.gettempdir(), "gb-master-*")):
            if now - os.path.getmtime(p) > 86400:
                rm(p)
    except Exception:
        pass
    try:
        import site_directory
        site_directory.trim_site_cache()
    except Exception:
        pass
    _STATE["housekeeping"] = rep
    return rep


def start_housekeeping():
    threading.Thread(target=housekeeping, daemon=True, name="groovebox-housekeeping").start()
