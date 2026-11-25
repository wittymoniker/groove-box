"""R173 · Canonical toolkit bridge

Keeps engine / composition / randomizer / shuffler / game / video surfaces
aligned with the same canonical authority that Master Mod Path uses.

Master Mod Path → audio (yes, indirectly):
  evaluate() blends sources with canonical curves (master × canonical_level).
  tick()/_apply() writes into:
    • widget:* global panel controls (spin_engine_strength, spin_canonical_*,
      slider_fractalizer, EQ, envelope, …) which the audio graph reads each block
    • automation_bus paths under ROOTS (r32_synth_engine, r32_fx_state,
      r32_inst_mix, geometric/cellular/wavetable synth states, game overrides, …)
  There is no direct sample-buffer write from the matrix; variance becomes
  parameter motion the engines sonify. Video/game read the same dict roots.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

# Surfaces that must honour canonical_owner and Master Mod authority
ANY_SIGNAL_ANY_CONTEXT = True
FRACTAL_GUIDELINE = (
    "One authority (Master×Canonical); any normalized signal may address any "
    "context-scoped target with bounded fan-out; predictive never auto-commits; "
    "canonical_owner patterns are protected under randomize/shuffle."
)

TOOLKIT_SURFACES = (
    "engine",          # cooperative kernels + synth engines
    "composition",     # composition workbench / seed programs
    "randomizer",      # deterministic randomizer engine
    "shuffler",        # sequence / playlist shuffles
    "multidim",        # multidim synth lanes
    "video",           # video_canonical / visualizers
    "game",            # r32_game_overrides / macros
    "mod_path",        # Master Mod Path Matrix itself
)


def master_mod_level(app) -> float:
    try:
        import mod_matrix as mm
        return float(mm.master(app))
    except Exception:
        try:
            return float(getattr(app, "r99_mod_matrix_canonical", 0.5))
        except Exception:
            return 0.5


def canonical_level(app) -> float:
    try:
        import r32_finish as rf
        return float(rf.canonical_level(app))
    except Exception:
        return float(getattr(app, "_canonical_level_cache", 0.0) or 0.0)


def effective_canonical_authority(app) -> float:
    """master × active canonical — same product Mod Path uses in evaluate()."""
    return max(0.0, min(1.0, master_mod_level(app) * canonical_level(app)))


def is_canonical_owned(mem: Optional[dict]) -> bool:
    if not isinstance(mem, dict):
        return False
    return str(mem.get("canonical_owner", "")).startswith("canonical:")


def randomizer_may_mutate(mem: Optional[dict], *, respect_canonical: bool = True) -> bool:
    """Randomizers / shufflers must not clobber canonical-owned patterns when respect is on."""
    if not respect_canonical:
        return True
    return not is_canonical_owned(mem)


def automation_audio_roots() -> Tuple[str, ...]:
    """Subset of automation_bus.ROOTS that the audio engines consume."""
    return (
        "r32_synth_engine",
        "r32_fx_state",
        "r32_time_fx",
        "r32_mod_osc",
        "r32_eq",
        "r32_inst_mix",
        "geometric_synth_mixer_state",
        "ball_synth_params",
        "cellular_synth_params",
        "wavetable_projector_state",
        "global_mod_state",
        "global_algo_state",
        "sidechain_state",
        "global_eq_state",
        "global_tuning",
    )


def automation_game_roots() -> Tuple[str, ...]:
    return ("r32_game_overrides", "r32_game_macros")


def automation_visual_roots() -> Tuple[str, ...]:
    return ("r32_expression_matrix", "wavetable_projector_state", "geometric_synth_mixer_state")


def audio_widget_targets() -> Tuple[str, ...]:
    """GLOBAL_WIDGETS in mod_matrix that feed the audio path."""
    return (
        "widget:spin_engine_strength",
        "widget:spin_canonical_resonance",
        "widget:spin_canonical_convolve",
        "widget:spin_canonical_live_overblend",
        "widget:slider_fractalizer",
        "widget:slider_eqr",
        "widget:slider_pkp_envelope",
        "widget:slider_pkp_boost",
        "widget:slider_pkp_boost_pitch",
        "widget:slider_pkp_boost_mod",
        "widget:slider_pkp_boost_prob",
        "widget:spin_global_convolve",
        "widget:spin_seed_reach",
    )


def routes_variance_to_audio(app) -> Dict[str, Any]:
    """Diagnostics: does Master Mod Path currently have a live path into audio?"""
    authority = effective_canonical_authority(app)
    try:
        import mod_matrix as mm
        rs = list(mm.rows(app) or [])
        targets = [str(r.get("target") or "") for r in rs if r.get("enabled", True)]
    except Exception as exc:
        return {"ok": False, "error": str(exc), "authority": authority}
    audio_hits = []
    for t in targets:
        if t in audio_widget_targets() or t.startswith("widget:spin_engine") or t.startswith("widget:slider_"):
            audio_hits.append(t)
        else:
            for root in automation_audio_roots():
                if t.startswith(root + "/") or t == root:
                    audio_hits.append(t)
                    break
    return {
        "ok": True,
        "authority": authority,
        "master": master_mod_level(app),
        "canonical_level": canonical_level(app),
        "enabled_rows": len(targets),
        "audio_bound_rows": len(audio_hits),
        "audio_targets_sample": audio_hits[:12],
        "routes_to_audio": bool(audio_hits) or authority > 0.0,
        "note": (
            "Variance is parameter modulation, not a direct PCM write. "
            "Engines sonify the modulated state each audio block."
        ),
    }


def ensure_canonical_rows_for_audio(app) -> int:
    """Major edit: ensure at least one canonical-backed row targets audio pathways."""
    try:
        import mod_matrix as mm
    except Exception:
        return 0
    have = {str(r.get("target")) for r in mm.rows(app)}
    added = 0
    prefer = [
        "widget:spin_engine_strength",
        "widget:slider_fractalizer",
        "widget:spin_canonical_resonance",
    ]
    # also first numeric path under synth engine if present
    try:
        import automation_bus as ab
        for t in ab.targets(app):
            if t.startswith("r32_synth_engine/") or t.startswith("r32_inst_mix/"):
                prefer.append(t)
            if len(prefer) > 10:
                break
    except Exception:
        pass
    for t in prefer:
        if t in have:
            continue
        mm.rows(app).append({
            "source": "seed",
            "method": "add",
            "source2": "const",
            "target": t,
            "amount": 0.18,
            "rate": 8.0,
            "canonical": 1.0,
            "enabled": True,
            "group": "audio path",
            "canonical_entry": True,
        })
        have.add(t)
        added += 1
        if added >= 4:
            break
    return added


def shuffle_indices(n: int, seed: int, *, app=None, protect_canonical_slots: Optional[List[bool]] = None) -> List[int]:
    """Canonical-aware shuffle: protected slots stay fixed."""
    import random
    rng = random.Random(int(seed) & 0xFFFFFFFF)
    idx = list(range(max(0, int(n))))
    if protect_canonical_slots is None:
        rng.shuffle(idx)
        return idx
    free = [i for i, p in enumerate(protect_canonical_slots) if i < n and not p]
    rng.shuffle(free)
    out = list(idx)
    fi = 0
    for i in range(n):
        if i < len(protect_canonical_slots) and protect_canonical_slots[i]:
            out[i] = i
        else:
            out[i] = free[fi]; fi += 1
    return out


def feature_manifest(app=None) -> Dict[str, Any]:
    """Full-feature snapshot for composition guides / doctor."""
    return {
        "toolkits": list(TOOLKIT_SURFACES),
        "master_mod_audio": routes_variance_to_audio(app) if app is not None else {"ok": False, "note": "pass app"},
        "audio_roots": automation_audio_roots(),
        "game_roots": automation_game_roots(),
        "visual_roots": automation_visual_roots(),
        "audio_widgets": audio_widget_targets(),
        "scode_lanes": ("phase", "probability", "eq", "sidechain", "envelope", "automation", "meta"),
        "predictive": True,
        "multidimensional": True,
    }
