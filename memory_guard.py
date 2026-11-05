# GROOVEBOX_R28_4_50_HF27_MEMORY_GUARD_20261028
"""Bounded-memory guards for Groovebox exports and heavy activities.

Aborts or refuses work that would realistically exhaust host RAM rather than
letting the kernel OOM-killer take down the whole appliance session.
"""
from __future__ import annotations

import os
import threading
from typing import Optional, Tuple

_LOCK = threading.Lock()
_LAST_AVAIL = 0
_LAST_TOTAL = 0
_LAST_AT = 0.0

# Keep a floor free so the GUI, PipeWire, and compositor survive an export.
_RESERVE_BYTES = 384 * 1024 * 1024  # 384 MiB
_MIN_AVAIL_FRACTION = 0.12  # also refuse if free < 12% of total


def _read_meminfo() -> Tuple[int, int]:
    """Return (MemAvailable, MemTotal) in bytes. Zeros on failure."""
    avail = total = 0
    try:
        with open("/proc/meminfo", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    avail = int(line.split()[1]) * 1024
                elif line.startswith("MemTotal:"):
                    total = int(line.split()[1]) * 1024
                if avail and total:
                    break
    except Exception:
        pass
    if total <= 0:
        try:
            import resource  # noqa: F401
            page = os.sysconf("SC_PAGE_SIZE")
            total = int(os.sysconf("SC_PHYS_PAGES")) * page
            # No portable MemAvailable; approximate with 40% of total as free budget.
            avail = max(0, total // 2)
        except Exception:
            pass
    return max(0, avail), max(0, total)


def snapshot(force: bool = False) -> dict:
    """Cached memory snapshot (TTL ~0.75s) for UI/status without thrashing."""
    import time
    global _LAST_AVAIL, _LAST_TOTAL, _LAST_AT
    now = time.monotonic()
    with _LOCK:
        if (not force) and _LAST_AT and (now - _LAST_AT) < 0.75:
            avail, total = _LAST_AVAIL, _LAST_TOTAL
        else:
            avail, total = _read_meminfo()
            _LAST_AVAIL, _LAST_TOTAL, _LAST_AT = avail, total, now
    return {
        "available": avail,
        "total": total,
        "reserve": _RESERVE_BYTES,
        "usable": max(0, avail - _RESERVE_BYTES),
    }


def estimate_pcm_bytes(frames: int, channels: int = 2, sample_width: int = 2, copies: int = 2) -> int:
    """Rough peak RAM for a PCM buffer plus intermediate copies/resamples."""
    frames = max(0, int(frames))
    channels = max(1, int(channels))
    sample_width = max(1, int(sample_width))
    copies = max(1, int(copies))
    return frames * channels * sample_width * copies


def estimate_video_frame_bytes(width: int, height: int, channels: int = 4, copies: int = 3) -> int:
    w, h = max(1, int(width)), max(1, int(height))
    return w * h * max(1, int(channels)) * max(1, int(copies))


def would_exceed(needed_bytes: int, *, label: str = "activity") -> Optional[str]:
    """Return a human error string if *needed_bytes* is unsafe, else None."""
    snap = snapshot(force=True)
    avail, total, usable = snap["available"], snap["total"], snap["usable"]
    needed = max(0, int(needed_bytes))
    if total > 0 and avail < int(total * _MIN_AVAIL_FRACTION):
        return (
            f"CANCELLED: low system memory ({avail // (1024*1024)} MiB free of "
            f"{total // (1024*1024)} MiB); refused {label} to avoid OOM."
        )
    if needed > 0 and needed > usable:
        return (
            f"CANCELLED: {label} needs ~{needed // (1024*1024)} MiB but only "
            f"{usable // (1024*1024)} MiB is safely available "
            f"({avail // (1024*1024)} MiB free, reserve {_RESERVE_BYTES // (1024*1024)} MiB). "
            f"Reduce resolution, length, or close other apps."
        )
    return None


def guard_or_raise(needed_bytes: int, *, label: str = "activity", cancel_event=None) -> None:
    """Raise RuntimeError(CANCELLED:...) if memory is insufficient or cancel set."""
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        raise RuntimeError(f"CANCELLED: {label} cancelled by user.")
    msg = would_exceed(needed_bytes, label=label)
    if msg:
        raise RuntimeError(msg)


def adaptive_workers(preferred: int, *, heavy: bool = False) -> int:
    """Scale thread-pool size down on low-RAM / low-CPU hosts."""
    preferred = max(1, int(preferred))
    try:
        cpus = max(1, int(os.cpu_count() or 1))
    except Exception:
        cpus = 1
    snap = snapshot()
    total = snap["total"] or (2 * 1024 * 1024 * 1024)
    avail = snap["available"]
    # Cap by CPU
    cap = max(1, min(preferred, cpus if heavy else max(1, cpus - 1)))
    # Cap by RAM: ~1 worker per 512 MiB available beyond reserve on heavy work
    if heavy and avail > 0:
        ram_cap = max(1, int(max(0, avail - _RESERVE_BYTES) // (512 * 1024 * 1024)))
        cap = min(cap, ram_cap)
    elif avail > 0 and avail < 768 * 1024 * 1024:
        cap = 1
    return max(1, min(preferred, cap))
