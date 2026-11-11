"""process_planner.py — GROOVEBOX_R32_PROCESS_PLANNER_20261110

Predictive process planning for exports: how many worker processes and how to split a video
into parts, from (a) usable cores, (b) free memory, (c) measured history of this machine
(seconds per part per kind, EMA) — so a long export is split into enough parts to keep every
worker busy to the end (no idle tail where one worker renders while the others wait).

plan(kind, n_parts, parallel) -> {"workers", "groups": [[part indices]...], "eta_s"}
    Longest-processing-time-first grouping: parts are interleaved by predicted cost so each
    worker's group finishes at about the same time (the part tree's leaves are balanced).
record(kind, part_seconds) feeds the history after each finished job.
"""
from __future__ import annotations

import json
import os
import time

_HIST = {}


def _path():
    try:
        import groovebox_paths
        return os.path.join(groovebox_paths.state_dir(), "process_planner.json")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".groovebox", "process_planner.json")


def _load():
    global _HIST
    if not _HIST:
        try:
            with open(_path(), encoding="utf-8") as f:
                _HIST = json.load(f) or {}
        except Exception:
            _HIST = {}
    return _HIST


def record(kind, seconds, parts=1):
    h = _load()
    per = float(seconds) / max(1, int(parts))
    prev = h.get(kind)
    h[kind] = per if prev is None else 0.7 * float(prev) + 0.3 * per
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(h, f)
    except Exception:
        pass


def capacity():
    try:
        cores = len(os.sched_getaffinity(0))
    except Exception:
        cores = os.cpu_count() or 2
    try:
        import memory_guard
        free_gb = float(memory_guard.snapshot(force=True).get("available", 0)) / 2 ** 30
        if free_gb <= 0:
            raise RuntimeError("effective available memory unavailable")
    except Exception:
        try:
            free_gb = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2 ** 30
        except Exception:
            free_gb = 4.0
    return max(1, cores - 1), max(1, int(free_gb // 1.5))


def plan(kind, n_parts, parallel=None):
    cores, by_ram = capacity()
    workers = max(1, min(int(parallel or 6), cores, by_ram, int(n_parts)))
    per = float(_load().get(kind, 20.0))
    # last part is usually shorter (remainder); predict cost 1.0 for full parts, 0.6 for the last
    costs = [(1.0 if i < n_parts - 1 else 0.6) * per for i in range(int(n_parts))]
    groups = [[] for _ in range(workers)]
    load = [0.0] * workers
    for i in sorted(range(len(costs)), key=lambda i: -costs[i]):
        w = min(range(workers), key=lambda k: load[k])
        groups[w].append(i); load[w] += costs[i]
    for g in groups:
        g.sort()
    return {"workers": workers, "groups": [g for g in groups if g], "eta_s": max(load) if load else 0.0,
            "per_part_s": per, "at": time.time()}


def suggest_parts(duration_s, parallel=None):
    """Enough parts for every worker to get ≥ 3 (smooth tail), ≤ 128."""
    cores, by_ram = capacity()
    w = max(1, min(int(parallel or 6), cores, by_ram))
    return int(max(w * 3, min(128, round(float(duration_s) / 20.0))))
