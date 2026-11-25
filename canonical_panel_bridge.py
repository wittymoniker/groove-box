"""canonical_panel_bridge.py — CANONICAL_PANEL_COVERAGE_R8

Canonical engines should steer ~95% of main-window *composition* controls:
  - top-pane FX / authority / resonance (EQR, Fractallizer, PKP, HyperDrive-ish,
    canonical overblend/resonance/convolve)
  - middle (main) pane instrument/sequence parameters already partly covered
  - panels *alongside* multidim that are NOT the four geometrics (ball / cellular /
    vector / wavetable geometric instances)

Geometrics keep their own write paths. Transport, export, file dialogs, and pure
window chrome stay user-only (the remaining ~5%).

Authority law matches the synth path:
  effective = (1 - strength) * user + strength * canonical_target
  strength ∈ [0.5, 1.0] from active canonical engines / strategy.
"""
from __future__ import annotations

import math
try:  # R132.10: project trig route — book isy/isx series when the Trigonometry Engine is ON (gb_trig)
    from gb_trig import sin as _tsin
except Exception:  # standalone use outside the app
    from math import sin as _tsin
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Registry: attribute on main window → metadata
# kind: "float01" | "float" | "int" | "bool" | "combo"
# scope: "top" | "main" | "side" | "fx" | "authority"
# ---------------------------------------------------------------------------

# Top pane / global FX (newest + established)
TOP_PANE: Dict[str, dict] = {
    "slider_eqr":              {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "top", "key": "eqr"},
    "slider_fractalizer":      {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "top", "key": "fractalizer"},
    "slider_pkp_envelope":     {"kind": "float", "lo": 1.0, "hi": 1000.0, "scale": 0.001, "scope": "top", "key": "pkp_envelope"},
    "slider_pkp_boost":        {"kind": "float", "lo": 0.0, "hi": 3.0, "scope": "top", "key": "pkp_boost"},
    "slider_pkp_boost_env":    {"kind": "float", "lo": 0.0, "hi": 3.0, "scope": "top", "key": "pkp_boost_env"},
    "slider_pkp_boost_mod":    {"kind": "float", "lo": 0.0, "hi": 3.0, "scope": "top", "key": "pkp_boost_mod"},
    "slider_pkp_boost_offset": {"kind": "float", "lo": 0.0, "hi": 3.0, "scope": "top", "key": "pkp_boost_offset"},
    "slider_pkp_boost_pitch":  {"kind": "float", "lo": 0.0, "hi": 3.0, "scope": "top", "key": "pkp_boost_pitch"},
    "slider_pkp_boost_prob":   {"kind": "float", "lo": 0.0, "hi": 2.0, "scope": "top", "key": "pkp_boost_responsiveness"},
    "slider_pkp_boost_steps":  {"kind": "float", "lo": 0.0, "hi": 3.0, "scope": "top", "key": "pkp_boost_steps"},
    "spin_canonical_live_overblend": {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "authority", "key": "canonical_overblend"},
    "spin_canonical_resonance":      {"kind": "float", "lo": 0.0, "hi": 200.0, "scale": 0.01, "scope": "authority", "key": "canonical_resonance"},
    "spin_canonical_convolve":       {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "authority", "key": "canonical_convolve"},
    "spin_global_convolve":          {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "top", "key": "global_convolve"},
    "slider_global_convolve":        {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "top", "key": "global_convolve_slider"},
    "slider_master_vector_drive":    {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "top", "key": "master_vector_drive"},
}

# Main / middle pane sequence + step (compositional, not chrome)
MAIN_PANE: Dict[str, dict] = {
    "spin_seq_length":         {"kind": "int", "lo": 1, "hi": 65536, "scope": "main", "key": "seq_length"},
    "spin_playlist_length":    {"kind": "int", "lo": 1, "hi": 65536, "scope": "main", "key": "playlist_rows"},
    "spin_bpm":                {"kind": "float", "lo": 20.0, "hi": 400.0, "scope": "main", "key": "bpm"},
    "spin_base_frequency":     {"kind": "float", "lo": 20.0, "hi": 2000.0, "scope": "main", "key": "base_frequency"},
    "spin_track_offset":       {"kind": "float", "lo": -64.0, "hi": 64.0, "scope": "main", "key": "track_offset"},
    "slider_sequence_attack":  {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "main", "key": "seq_attack"},
    "slider_sequence_release": {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "main", "key": "seq_release"},
    "slider_step_amp":         {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "main", "key": "step_amp"},
    "slider_step_pitch":       {"kind": "float", "lo": 0.0, "hi": 200.0, "scale": 0.01, "scope": "main", "key": "step_pitch"},
    "slider_step_probability": {"kind": "float", "lo": 0.0, "hi": 100.0, "scope": "main", "key": "step_probability"},
    "slider_step_phase_shift": {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "main", "key": "step_phase"},
    "slider_step_fx_probability": {"kind": "float", "lo": 0.0, "hi": 100.0, "scope": "main", "key": "step_fx_prob"},
    "slider_step_sidechain":   {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "main", "key": "step_sidechain"},
    "slider_step_eq_gain":     {"kind": "float", "lo": -24.0, "hi": 24.0, "scope": "main", "key": "step_eq_gain"},
    "spin_step_eq_freq":       {"kind": "float", "lo": 20.0, "hi": 20000.0, "scope": "main", "key": "step_eq_freq"},
    "spin_step_eq_q":          {"kind": "float", "lo": 0.1, "hi": 40.0, "scope": "main", "key": "step_eq_q"},
    "spin_step_offset":        {"kind": "float", "lo": -1.0, "hi": 1.0, "scope": "main", "key": "step_offset"},
}

# Side panels near multidim — EXCLUDE pure geometrics (ball/cellular/vector/wavetable geo)
SIDE_NON_GEO: Dict[str, dict] = {
    "slider_geo_panel_mix":        {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "side", "key": "geo_panel_mix", "user_wins": True},
    "slider_geometric_cross_mod":  {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "side", "key": "geo_cross_mod"},
    "slider_geometric_ensemble_mod": {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "side", "key": "geo_ensemble_mod"},
    "slider_geometric_inharmonic": {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "side", "key": "geo_inharmonic"},
    "spin_heuristic_span":         {"kind": "float", "lo": 0.0, "hi": 100.0, "scope": "side", "key": "heuristic_span"},
    "combo_heuristic_bias":        {"kind": "combo", "scope": "side", "key": "heuristic_bias"},
    "combo_heuristic_family":      {"kind": "combo", "scope": "side", "key": "heuristic_family"},
    "combo_heuristic_scope":       {"kind": "combo", "scope": "side", "key": "heuristic_scope"},
    "chk_heuristic_series_lock":   {"kind": "bool", "scope": "side", "key": "heuristic_series_lock"},
    "slider_master_vol":           {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "side", "key": "master_vol"},
    "slider_master_vol_visible":   {"kind": "float", "lo": 0.0, "hi": 100.0, "scale": 0.01, "scope": "side", "key": "master_vol_vis"},
}

# Synth-parameter keys already blended in _apply_canonical_synth_controls (kept for coverage math)
SYNTH_KEYS = (
    "morph", "harmonic_freq", "chaos", "fold_depth", "harmonic_lattice",
    "drive", "filter", "tuning", "am_depth", "fm_depth", "pm_depth",
    "am_rate", "fm_rate", "pm_rate", "phase_shift", "eq_amount",
)

# Explicitly excluded from canonical rewrite (user / system chrome)
EXCLUDED_PREFIXES = (
    "btn_export", "btn_full_export", "btn_finish", "btn_help", "btn_compat",
    "btn_record", "btn_clear_memory", "btn_audio_check", "btn_audio_only",
)


def all_registry() -> Dict[str, dict]:
    out = {}
    out.update(TOP_PANE)
    out.update(MAIN_PANE)
    out.update(SIDE_NON_GEO)
    return out


def coverage_report(host=None) -> dict:
    """How many registered controls exist on the host vs theoretically listed."""
    reg = all_registry()
    present = missing = 0
    by_scope = {}
    for attr, meta in reg.items():
        scope = meta.get("scope", "?")
        by_scope.setdefault(scope, {"present": 0, "missing": 0, "attrs": []})
        ok = host is not None and getattr(host, attr, None) is not None
        if ok:
            present += 1
            by_scope[scope]["present"] += 1
            by_scope[scope]["attrs"].append(attr)
        else:
            missing += 1
            by_scope[scope]["missing"] += 1
    total = present + missing
    return {
        "registered": total,
        "present_on_host": present,
        "missing_on_host": missing,
        "coverage_of_registry": (present / total) if total else 0.0,
        "synth_keys": len(SYNTH_KEYS),
        "by_scope": by_scope,
        "target_authority": ">=0.95 of composition controls when Full Canonical",
    }


def _clamp(v: float, lo: float, hi: float) -> float:
    if not math.isfinite(v):
        return lo
    return max(lo, min(hi, v))


def blend(user: float, target: float, strength: float, lo: float, hi: float) -> float:
    s = _clamp(float(strength), 0.0, 1.0)
    # floor at 0.5 when caller already applied engine law; still safe if passed raw
    out = (1.0 - s) * float(user) + s * float(target)
    return _clamp(out, lo, hi)


def target_from_context(key: str, ctx: float, index: int = 0) -> float:
    """Deterministic canonical target in ~0..1 (or domain-ish) from numerology context."""
    c = float(ctx) if math.isfinite(ctx) else 0.5
    # stable hash-ish without RNG
    x = _tsin((c + 0.17 * (index + 1)) * (1.0 + 0.03 * len(key))) * 0.5 + 0.5
    x = _clamp(x, 0.0, 1.0)
    # mild key bias
    if "pkp" in key:
        x = 0.35 + 0.45 * x
    elif "eqr" in key or "fractal" in key:
        x = 0.25 + 0.55 * x
    elif "resonance" in key:
        x = 0.5 + 0.4 * x
    elif "bpm" in key:
        return 60.0 + 100.0 * x
    elif "base_frequency" in key:
        return 220.0 + 400.0 * x
    elif "seq_length" in key or "playlist" in key:
        return float(int(8 + 24 * x))
    return x


def read_widget(host, attr: str, meta: dict) -> Optional[float]:
    w = getattr(host, attr, None)
    if w is None:
        return None
    kind = meta.get("kind", "float")
    try:
        if kind == "bool":
            return 1.0 if bool(w.isChecked()) else 0.0
        if kind == "combo":
            return float(w.currentIndex())
        if kind == "int":
            return float(int(w.value()))
        return float(w.value())
    except Exception:
        return None


def write_widget(host, attr: str, meta: dict, value: float, *, block: bool = True) -> bool:
    w = getattr(host, attr, None)
    if w is None:
        return False
    kind = meta.get("kind", "float")
    try:
        if block and hasattr(w, "blockSignals"):
            w.blockSignals(True)
        if kind == "bool":
            w.setChecked(bool(value >= 0.5))
        elif kind == "combo":
            w.setCurrentIndex(int(round(value)))
        elif kind == "int":
            w.setValue(int(round(value)))
        else:
            w.setValue(float(value))
        if block and hasattr(w, "blockSignals"):
            w.blockSignals(False)
        return True
    except Exception:
        try:
            if block and hasattr(w, "blockSignals"):
                w.blockSignals(False)
        except Exception:
            pass
        return False


def apply_registry_to_state(state: dict, generated: dict, strength: float, registry: Optional[dict] = None) -> dict:
    """Blend dict state keys (no widgets).

    GROOVEBOX_R123_STATE_UNITS_20261119: instrument state stores percent widgets in STATE units
    (widget value x scale, e.g. geo_panel_mix 0.25 for a slider at 25). The blend therefore runs in
    state units: lo/hi are scaled, targets already in state units are used as-is, and a target given
    in widget units (above the state range) is converted down. Previously every scaled key already in
    state was multiplied by 1/scale (0.25 -> 25), so the geometric balance clamped to 75 % and EQR-like
    keys were inflated 100x. A key with no canonical target is left untouched, and keys marked
    ``user_wins`` keep a user-authored value (their canonical value is only a neutral default).
    """
    reg = registry or all_registry()
    st = dict(state or {})
    gen = generated if isinstance(generated, dict) else {}
    s = _clamp(float(strength), 0.0, 1.0)
    for attr, meta in reg.items():
        key = meta.get("key") or attr
        if key not in gen:
            continue
        if meta.get("user_wins") and key in st:
            continue
        try:
            gv = float(gen[key])
            uv = float(st.get(key, gv))
            lo = float(meta.get("lo", 0.0))
            hi = float(meta.get("hi", 1.0))
            scale = meta.get("scale")
            if scale:
                sc = float(scale)
                lo, hi = lo * sc, hi * sc
                if gv > hi and gv * sc <= hi:
                    gv = gv * sc
                if uv > hi and uv * sc <= hi:
                    uv = uv * sc
            if not (math.isfinite(gv) and math.isfinite(uv)):
                continue
            st[key] = blend(uv, gv, s, lo, hi)
        except Exception:
            pass
    return st


def apply_to_host_panels(host, strength: float, ctx: float = 0.5, instrument_index: int = 0,
                         scopes: Sequence[str] = ("top", "side", "authority"),
                         write_ui: bool = False) -> dict:
    """
    Project canonical targets onto registered panels.
    Default: compute only (write_ui=False) so audio thread never touches Qt.
    UI ticks may pass write_ui=True on the GUI thread.
    """
    s = _clamp(float(strength), 0.0, 1.0)
    reg = all_registry()
    report = {"written": 0, "skipped": 0, "strength": s, "scopes": list(scopes)}
    for attr, meta in reg.items():
        if meta.get("scope") not in scopes:
            continue
        if any(attr.startswith(p) for p in EXCLUDED_PREFIXES):
            report["skipped"] += 1
            continue
        key = meta.get("key") or attr
        lo = float(meta.get("lo", 0.0))
        hi = float(meta.get("hi", 1.0))
        tgt = target_from_context(key, ctx, instrument_index)
        # map 0..1 targets into widget domain
        if meta.get("kind") in ("float", "int") and hi > 1.0 and tgt <= 1.0 and key not in ("bpm", "base_frequency", "seq_length", "playlist_rows"):
            if meta.get("scale"):
                tgt = tgt / float(meta["scale"])
            else:
                tgt = lo + (hi - lo) * tgt
        tgt = _clamp(tgt, lo, hi)
        user = read_widget(host, attr, meta)
        if user is None:
            report["skipped"] += 1
            continue
        effective = blend(user, tgt, s, lo, hi)
        if write_ui:
            if write_widget(host, attr, meta, effective, block=True):
                report["written"] += 1
            else:
                report["skipped"] += 1
        else:
            report["written"] += 1  # counted as projected
    return report


def extend_synth_apply(st: dict, generated: dict, strength: float) -> dict:
    """Called from _apply_canonical_synth_controls to also blend panel-level keys in state."""
    return apply_registry_to_state(st, generated, strength, all_registry())


# ---------------------------------------------------------------------------
# Self-check (no Qt required)
# ---------------------------------------------------------------------------
def self_test() -> dict:
    errs: List[str] = []
    # blend endpoints
    if abs(blend(0.0, 1.0, 0.0, 0.0, 1.0) - 0.0) > 1e-9:
        errs.append("blend strength 0")
    if abs(blend(0.0, 1.0, 1.0, 0.0, 1.0) - 1.0) > 1e-9:
        errs.append("blend strength 1")
    if abs(blend(0.0, 1.0, 0.5, 0.0, 1.0) - 0.5) > 1e-9:
        errs.append("blend strength 0.5")
    # clamp non-finite
    if not math.isfinite(blend(float("nan"), 1.0, 0.5, 0.0, 1.0)):
        errs.append("nan user")
    # registry non-empty scopes
    reg = all_registry()
    if len(reg) < 40:
        errs.append(f"registry too small: {len(reg)}")
    scopes = {m["scope"] for m in reg.values()}
    for need in ("top", "main", "side", "authority"):
        if need not in scopes:
            errs.append(f"missing scope {need}")
    # geometrics not in side as dedicated ball/cellular widget attrs
    for bad in ("slider_ball", "slider_cellular", "spin_wavetable"):
        if any(bad in a for a in reg):
            errs.append(f"geo leak {bad}")
    # deterministic targets
    a = target_from_context("eqr", 0.3, 1)
    b = target_from_context("eqr", 0.3, 1)
    if a != b:
        errs.append("target not deterministic")
    # state blend
    st = apply_registry_to_state({"eqr": 0.0}, {"eqr": 1.0}, 0.5, {"x": {"key": "eqr", "lo": 0.0, "hi": 1.0}})
    if abs(st.get("eqr", -1) - 0.5) > 1e-9:
        errs.append("state blend")
    st = apply_registry_to_state({"geo_panel_mix": 0.25, "eqr": 0.3}, {}, 1.0)
    if st != {"geo_panel_mix": 0.25, "eqr": 0.3}:
        errs.append("state units: untargeted keys must stay untouched")
    st = apply_registry_to_state({"geo_panel_mix": 0.25}, {"geo_panel_mix": 0.5}, 1.0)
    if abs(st["geo_panel_mix"] - 0.25) > 1e-12:
        errs.append("user-authored geo_panel_mix must win")
    st = apply_registry_to_state({"master_vol": 0.2}, {"master_vol": 0.6}, 0.5)
    if abs(st["master_vol"] - 0.4) > 1e-9:
        errs.append("scaled key must blend in state units")
    cov = coverage_report(None)
    return {
        "ok": not errs,
        "errors": errs,
        "registry_size": len(reg),
        "scopes": sorted(scopes),
        "coverage_without_host": cov,
        "ts": time.time(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2, sort_keys=True))
