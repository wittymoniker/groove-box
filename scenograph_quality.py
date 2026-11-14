"""Canonical preview-quality profiles for the live Meum scenograph.

Preview-only controls: they never alter canonical audio, project data, or exports.
The viewer keeps a latest-only render queue and scales the finished preview to its
visible viewport, so quality changes cannot accumulate stale frames.
"""
from __future__ import annotations

PROFILES = {
    # label: (render scale, target fps, monitor stride)
    "Fine": (1.00, 30, 1),
    "Balanced": (0.90, 24, 1),
    "Draft": (0.68, 18, 1),
    "Auto": (1.00, 30, 1),  # resolved from the hardware/power profile
}


def profile(name: str, auto_fps: int = 24, auto_scale: float = 0.9):
    key = str(name or "Auto").strip().title()
    if key not in PROFILES:
        key = "Auto"
    scale, fps, stride = PROFILES[key]
    if key == "Auto":
        fps = max(12, min(30, int(auto_fps or 24)))
        scale = max(0.60, min(1.0, float(auto_scale or 0.9)))
    return {"name": key, "scale": float(scale), "fps": int(fps), "stride": int(stride)}
