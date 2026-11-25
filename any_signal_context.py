"""R173 · Any-signal · any-context routing

Rule: every numeric (or normalizable) signal can modulate every automation /
widget target in every toolkit context (audio, video, game, multidim, network
presence), under the same Master×Canonical authority product.

Contexts are not separate buses — they are views of one fractal parameter space.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---- Context taxonomy (scientifically organized) ----
CONTEXTS = (
    "audio",          # engines, FX, mix, tuning
    "video",          # expression, projector, geometric visual
    "game",           # overrides, macros, playability
    "multidim",       # multidim macros / instrument_param_state
    "composition",    # seed, arrangement, pattern memory
    "network",        # presence / collab bias (non-destructive)
    "predictive",     # marginal forecasts only (no auto-commit)
)

SIGNAL_KINDS = (
    "seed",           # seed program curve
    "canonical",      # cooperative engine level
    "lfo",            # periodic
    "random",         # hash-stable noise
    "audio_feature",  # RMS, brightness, onset (normalized)
    "game_state",     # score, threat, position
    "video_feature",  # motion, hue energy
    "user",           # explicit UI / MIDI
    "predictive",     # marginal bias vector component
)

# Context → preferred automation root prefixes / widget prefixes
CONTEXT_PREFIXES: Dict[str, Tuple[str, ...]] = {
    "audio": (
        "r32_synth_engine/", "r32_fx_state/", "r32_time_fx/", "r32_inst_mix/",
        "r32_eq/", "r32_mod_osc/", "global_eq_state/", "sidechain_state/",
        "global_tuning/", "widget:spin_engine", "widget:slider_", "widget:spin_canonical",
        "widget:spin_global", "geometric_synth_mixer_state/", "ball_synth_params/",
        "cellular_synth_params/", "wavetable_projector_state/",
        # R138: canonical engine contribution levels + phase-lock characteristics
        "canonical_engine_levels/", "phase_lock_characteristics/",
    ),
    "video": (
        "r32_expression_matrix/", "wavetable_projector_state/",
        "geometric_synth_mixer_state/", "sample_morph_state/",
    ),
    "game": (
        "r32_game_overrides/", "r32_game_macros/",
    ),
    "multidim": (
        "instrument_param_state/", "master_vector_state/", "hyperdrive_state/",
        "patch_motion_state/",
    ),
    "composition": (
        "r32_perseq/", "global_algo_state/", "global_mod_state/",
    ),
    "network": (),  # presence only — bridge may no-op write
    "predictive": (),  # never writes through this context alone
}


def normalize_signal(value: Any, *, lo: float = 0.0, hi: float = 1.0) -> float:
    """Any signal → unit interval. Non-numeric → 0.5."""
    try:
        x = float(value)
    except Exception:
        return 0.5
    if hi == lo:
        return 0.5
    # already unit?
    if 0.0 <= x <= 1.0 and lo == 0.0 and hi == 1.0:
        return max(0.0, min(1.0, x))
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def classify_target(path: str) -> str:
    """Infer primary context from a target path."""
    p = str(path or "")
    for ctx, prefixes in CONTEXT_PREFIXES.items():
        for pre in prefixes:
            if p.startswith(pre) or (pre.startswith("widget:") and p.startswith(pre)):
                return ctx
    if p.startswith("widget:"):
        return "audio"
    return "composition"


def list_targets_for_context(app, context: str) -> List[str]:
    context = str(context or "audio")
    prefixes = CONTEXT_PREFIXES.get(context, ())
    out: List[str] = []
    try:
        import automation_bus as ab
        for t in ab.targets(app):
            if not prefixes or any(t.startswith(pre.rstrip("/")) or t.startswith(pre) for pre in prefixes if not pre.startswith("widget:")):
                if context == "audio" or any(t.startswith(pre.split("/")[0]) for pre in prefixes if "/" in pre or not pre.startswith("widget:")):
                    out.append(t)
            for pre in prefixes:
                if not pre.startswith("widget:") and (t.startswith(pre) or t.startswith(pre.rstrip("/"))):
                    if t not in out:
                        out.append(t)
    except Exception:
        pass
    try:
        import mod_matrix as mm
        for w in getattr(mm, "GLOBAL_WIDGETS", ()):
            path = "widget:" + w
            if classify_target(path) == context or context == "audio":
                if path not in out and context in ("audio", "composition"):
                    out.append(path)
    except Exception:
        pass
    # tighter filter by prefix
    if prefixes:
        filtered = []
        for t in out:
            if any(t.startswith(pre) for pre in prefixes):
                filtered.append(t)
            elif any(t.startswith(pre.rstrip("/")) for pre in prefixes if "/" in pre):
                filtered.append(t)
        if filtered:
            out = filtered
    return out


def route(
    app,
    *,
    signal: float,
    target: str,
    amount: float = 0.25,
    source_name: str = "user",
    method: str = "add",
    rate: float = 8.0,
    canonical: float = 0.0,
    enabled: bool = True,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """Any-signal → any-target: append or update a Master Mod Path row.

    Returns a result dict; does not touch the audio thread directly.
    """
    v = normalize_signal(signal)
    ctx = context or classify_target(target)
    if ctx == "predictive":
        return {"ok": False, "reason": "predictive context is display-only", "context": ctx}
    if ctx == "network":
        return {"ok": True, "reason": "network context recorded as soft bias only", "context": ctx, "value": v}

    try:
        import mod_matrix as mm
        rs = mm.rows(app)
    except Exception as exc:
        return {"ok": False, "reason": f"mod_matrix unavailable: {exc}"}

    # update existing row for same target+source if present
    for row in rs:
        if str(row.get("target")) == target and str(row.get("source")) == source_name:
            row["amount"] = float(amount)
            row["rate"] = float(rate)
            row["canonical"] = float(canonical)
            row["enabled"] = bool(enabled)
            row["method"] = method
            row["context"] = ctx
            row["_last_signal"] = v
            return {"ok": True, "updated": True, "target": target, "context": ctx, "value": v}

    rs.append({
        "source": source_name,
        "method": method,
        "source2": "const",
        "target": target,
        "amount": float(amount),
        "rate": float(rate),
        "canonical": float(canonical),
        "enabled": bool(enabled),
        "group": ctx,
        "context": ctx,
        "_last_signal": v,
    })
    return {"ok": True, "updated": False, "target": target, "context": ctx, "value": v}


def route_signal_to_context(
    app,
    signal: float,
    context: str,
    *,
    amount: float = 0.2,
    limit: int = 6,
    source_name: str = "user",
    prefer_canonical: bool = False,
) -> List[Dict[str, Any]]:
    """Fan out one signal into up to `limit` targets of a context."""
    targets = list_targets_for_context(app, context)[: max(1, int(limit))]
    canon = 1.0 if prefer_canonical else 0.0
    return [
        route(app, signal=signal, target=t, amount=amount, source_name=source_name, canonical=canon, context=context)
        for t in targets
    ]


def fanout_any_to_any(
    app,
    signal: float,
    contexts: Sequence[str] = ("audio", "video", "game", "multidim"),
    *,
    amount: float = 0.15,
    per_context: int = 3,
    source_name: str = "seed",
) -> Dict[str, List[Dict[str, Any]]]:
    """Ideal fractal fan-out: one signal, many contexts, bounded fan-in per context."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for ctx in contexts:
        if ctx in ("predictive", "network"):
            continue
        out[ctx] = route_signal_to_context(
            app, signal, ctx, amount=amount, limit=per_context, source_name=source_name, prefer_canonical=True
        )
    return out
