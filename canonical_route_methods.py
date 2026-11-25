"""R173 · Canonical automation routing methods & procedures

Procedures are pure recipes the UI / sCode / doctor can call. They never block
the audio callback; they only edit Mod Path rows and automation lanes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
try:  # R132.10: project trig route — book isy/isx series when the Trigonometry Engine is ON (gb_trig)
    from gb_trig import sin as _tsin
except Exception:  # standalone use outside the app
    from math import sin as _tsin

from any_signal_context import (
    CONTEXTS,
    fanout_any_to_any,
    list_targets_for_context,
    normalize_signal,
    route,
    route_signal_to_context,
)


PROCEDURES = {
    "ensure_audio_spine": "Guarantee Master×Canonical rows on core audio targets",
    "seed_fanout_fractal": "Route seed signal into audio/video/game/multidim",
    "protect_canonical_patterns": "Mark randomizer/shuffle policy for canonical slots",
    "bind_feature_to_fx": "Map any normalized feature to FX/EQ paths",
    "bind_game_to_engine": "Map game macros into engine strength / mix",
    "bind_video_to_spectral": "Map video energy into spectral/expression roots",
    "install_canonical_lanes": "automation_bus canonical owner lanes for top targets",
    "doctor_snapshot": "Full routing + authority snapshot",
}


def ensure_audio_spine(app) -> Dict[str, Any]:
    try:
        from canonical_toolkit_bridge import ensure_canonical_rows_for_audio, routes_variance_to_audio
        n = ensure_canonical_rows_for_audio(app)
        return {"ok": True, "added": n, "audio": routes_variance_to_audio(app)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def seed_fanout_fractal(app, seed_value: Optional[float] = None) -> Dict[str, Any]:
    if seed_value is None:
        try:
            seed_value = float(app.get_numeric_seed())
        except Exception:
            seed_value = 0.5
    sig = normalize_signal(seed_value, lo=0.0, hi=1e9) if seed_value > 1.0 else normalize_signal(seed_value)
    # better: use fractional part of scaled seed
    try:
        import math
        sig = abs(_tsin(float(seed_value) * 0.001))
    except Exception:
        sig = 0.5
    fan = fanout_any_to_any(app, sig, source_name="seed", amount=0.18, per_context=4)
    return {"ok": True, "signal": sig, "fanout": {k: len(v) for k, v in fan.items()}, "detail": fan}


def bind_feature_to_fx(app, feature: float, *, amount: float = 0.3) -> List[Dict[str, Any]]:
    return route_signal_to_context(app, feature, "audio", amount=amount, limit=8, source_name="audio_feature")


def bind_game_to_engine(app, game_signal: float, *, amount: float = 0.25) -> List[Dict[str, Any]]:
    results = route_signal_to_context(app, game_signal, "game", amount=amount, limit=4, source_name="game_state")
    # also push into engine strength if present
    results.append(route(app, signal=game_signal, target="widget:spin_engine_strength",
                         amount=amount, source_name="game_state", context="audio"))
    return results


def bind_video_to_spectral(app, video_signal: float, *, amount: float = 0.25) -> List[Dict[str, Any]]:
    return route_signal_to_context(app, video_signal, "video", amount=amount, limit=6, source_name="video_feature")


def install_canonical_lanes(app, limit: int = 12) -> Dict[str, Any]:
    """Add automation_bus lanes owned by canonical for top audio targets."""
    try:
        import automation_bus as ab
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    targets = list_targets_for_context(app, "audio")[:limit]
    added = 0
    for path in targets:
        if path.startswith("widget:"):
            continue
        try:
            ab.add_lane(app, path, amount=0.22, rate=16.0, owner="canonical")
            added += 1
        except Exception:
            pass
    return {"ok": True, "lanes_added": added, "targets": targets[:added]}


def protect_canonical_patterns(app) -> Dict[str, Any]:
    """Return policy object for randomizers/shufflers."""
    try:
        from canonical_toolkit_bridge import is_canonical_owned, effective_canonical_authority
        auth = effective_canonical_authority(app)
    except Exception:
        auth = 0.0
        def is_canonical_owned(m):  # type: ignore
            return str((m or {}).get("canonical_owner", "")).startswith("canonical:")
    return {
        "authority": auth,
        "rule": "skip_mutate_if_canonical_owner",
        "may_mutate": lambda mem: not is_canonical_owned(mem),
    }


def doctor_snapshot(app) -> Dict[str, Any]:
    from canonical_toolkit_bridge import feature_manifest, effective_canonical_authority
    snap = {
        "authority": effective_canonical_authority(app),
        "manifest": feature_manifest(app),
        "procedures": list(PROCEDURES),
        "contexts": list(CONTEXTS),
    }
    try:
        import mod_matrix as mm
        snap["mod_rows"] = len(mm.rows(app))
        snap["mod_targets"] = len(mm.all_targets(app))
    except Exception as exc:
        snap["mod_error"] = str(exc)
    try:
        import automation_bus as ab
        snap["automation_targets"] = len(ab.targets(app))
        snap["automation_lanes"] = len(ab.lanes(app))
    except Exception as exc:
        snap["automation_error"] = str(exc)
    return snap


def run_procedure(app, name: str, **kwargs) -> Any:
    name = str(name or "")
    table = {
        "ensure_audio_spine": lambda: ensure_audio_spine(app),
        "seed_fanout_fractal": lambda: seed_fanout_fractal(app, kwargs.get("seed_value")),
        "protect_canonical_patterns": lambda: protect_canonical_patterns(app),
        "bind_feature_to_fx": lambda: bind_feature_to_fx(app, float(kwargs.get("feature", 0.5)), amount=float(kwargs.get("amount", 0.3))),
        "bind_game_to_engine": lambda: bind_game_to_engine(app, float(kwargs.get("game_signal", 0.5)), amount=float(kwargs.get("amount", 0.25))),
        "bind_video_to_spectral": lambda: bind_video_to_spectral(app, float(kwargs.get("video_signal", 0.5)), amount=float(kwargs.get("amount", 0.25))),
        "install_canonical_lanes": lambda: install_canonical_lanes(app, limit=int(kwargs.get("limit", 12))),
        "doctor_snapshot": lambda: doctor_snapshot(app),
    }
    fn = table.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown procedure {name}", "known": list(PROCEDURES)}
    return fn()
