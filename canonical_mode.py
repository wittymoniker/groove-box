"""canonical_mode.py — GROOVEBOX_R32_CANONICAL_MODE_20261109

Three canonical work-together modes for every synth (panel, vector, wavetable, ball,
cellular, multidimensional):

    "protected"   Canonical Control 100 % + Protected Userdata          (DEFAULT, everywhere)
                  the canonical programme owns every voice; user presets are kept intact
                  (never overwritten) and act as the base the programme is built from.
    "global50"    Unprotected Userdata + 50 % Canonical Global Control over presets
                  half canonical / half user, user data may be rewritten by the engine.
    "direct"      Unprotected Userdata + 100 % Canonical Control = DIRECT SEEDED mode
                  the seed/canonicals drive everything; presets are writable scratch.

apply(app, mode) sets every share in one place and syncs the sliders/checkbox; the mode is
remembered in the project (``app.canonical_mode``).  Oldest mechanisms (the per-synth
canonical_share keys, the multidim slider, the protect checkbox) are all driven through their
existing fields, so nothing that read them before changes its contract.
"""
from __future__ import annotations

MODES = (
    ("protected", "🛡 Canonical 100 % · Protected Userdata (default)", 1.0, True),
    ("global50", "⚖ Unprotected · 50 % Canonical Global Control", 0.5, False),
    ("direct", "🎯 Unprotected · 100 % Canonical = Direct Seeded", 1.0, False),
)
DEFAULT = "protected"
_SHARE_DICTS = ("ball_synth_params", "cellular_synth_params", "wavetable_projector_state")


def share_for(mode):
    for key, _label, share, _prot in MODES:
        if key == mode:
            return share
    return 1.0


def protected_for(mode):
    for key, _label, _share, prot in MODES:
        if key == mode:
            return prot
    return True


def _seed_unit(app, salt):
    try:
        import groovebox as gb
        sig = int(getattr(app, "_seed_program_signature", lambda: 0)() or gb._safe_int_seed(app.get_numeric_seed()))
        import numpy as np
        return float(np.random.default_rng(gb.seed_child(sig, salt, 0)).random())
    except Exception:
        return 0.5


def _apply_fx_and_composition(app, mode, share):
    fx_mode = {"protected": "mix", "global50": "mix", "direct": "canonical"}.get(mode, "mix")
    st = getattr(app, "r32_fx_state", None)
    if isinstance(st, dict):
        g = st.setdefault("global", {})
        g["mode"] = fx_mode
        u = _seed_unit(app, "fx_global")
        g["pkp"] = round(0.4 * u, 3)
        g["fractal"] = round(0.35 * ((u * 7) % 1), 3)
        g["eqr"] = round(0.3 * ((u * 13) % 1), 3)
        for name, store in (st.get("local") or {}).items():
            if isinstance(store, dict):
                store["mode"] = fx_mode
    for attr, val in (("slider_eqr", 0.3 * _seed_unit(app, "eqr")),
                      ("slider_fractalizer", 0.35 * _seed_unit(app, "fractal")),
                      ("spin_global_convolve", 20.0 + 60.0 * _seed_unit(app, "convolve")),
                      ("spin_base_frequency", 220.0 + 440.0 * _seed_unit(app, "base")),
                      ("dial_project_sharp", int(30 + 40 * _seed_unit(app, "sharp")))):
        w = getattr(app, attr, None)
        if w is not None and hasattr(w, "setValue"):
            try:
                w.blockSignals(True)
                w.setValue(val)
                w.blockSignals(False)
            except Exception:
                pass
    pkp = getattr(app, "slider_pkp_envelope", None)
    if pkp is not None and hasattr(pkp, "setValue"):
        try:
            pkp.blockSignals(True)
            pkp.setValue(int(400 * _seed_unit(app, "pkp")))
            pkp.blockSignals(False)
        except Exception:
            pass
    for attr, salt in (("dial_track_energy", "energy"), ("dial_track_harmonic", "harmonic")):
        d = getattr(app, attr, None)
        if d is not None and hasattr(d, "setValue"):
            try:
                d.blockSignals(True)
                d.setValue(int(50 + 30 * (_seed_unit(app, salt) - 0.5)))
                d.blockSignals(False)
            except Exception:
                pass


def apply(app, mode=DEFAULT, *, refresh=True):
    mode = mode if mode in {m[0] for m in MODES} else DEFAULT
    share = share_for(mode)
    prot = protected_for(mode)
    app.canonical_mode = mode
    st = getattr(app, "geometric_synth_mixer_state", None)
    if isinstance(st, dict):
        st["multidim_canon"] = share
        st["multidim"] = max(float(st.get("multidim", share)), share) if mode != "global50" else 0.5
    for name in _SHARE_DICTS:
        d = getattr(app, name, None)
        if isinstance(d, dict):
            d["canonical_share"] = share
    vs = getattr(app, "vector_synth_params", None)
    if isinstance(vs, dict):
        vs["canonical_share"] = share
    gas = getattr(app, "global_algo_state", None)
    if isinstance(gas, dict):
        gas["user_data"] = bool(prot)
        gas["canonical_superwrite"] = bool(prot)
    chk = getattr(app, "chk_algo_protect_userdata", None)
    if chk is not None:
        try:
            chk.blockSignals(True)
            chk.setChecked(bool(prot))
            chk.blockSignals(False)
        except Exception:
            pass
    # FX and composition controls. Canonical mode sets the FX mode and writes
    # seed-derived numbers into the global FX and the composition spins.
    _apply_fx_and_composition(app, mode, share)
    # Push computed canonical numbers into the geometrics (ball, cellular, wavetable).
    # A manual lock on a lane keeps that lane's numbers.
    if not bool(getattr(app, "ball_manual_activity_locked", False)):
        fac = None
        fn = getattr(app, "_geometric_convolution_defaults", None)
        if callable(fn):
            try:
                fac = fn()
            except Exception:
                fac = None
        if isinstance(fac, dict):
            for lane, store_name in (("ball", "ball_synth_params"), ("cellular", "cellular_synth_params")):
                locked = bool(getattr(app, "ball_manual_activity_locked", False)) if lane == "ball" else bool(getattr(app, "ca_single_cell_activity_locked", False))
                if locked:
                    continue
                store = getattr(app, store_name, None)
                lane_vals = fac.get(lane)
                if isinstance(store, dict) and isinstance(lane_vals, dict):
                    for k, v in lane_vals.items():
                        if k in ("x", "y", "manual_cells"):
                            continue
                        store[k] = v
                    store["canonical_share"] = share
                    prefix = "spin_ball_" if lane == "ball" else "spin_ca_"
                    for k, v in lane_vals.items():
                        sp = getattr(app, prefix + k, None)
                        if sp is not None and hasattr(sp, "setValue"):
                            try:
                                sp.blockSignals(True)
                                sp.setValue(v)
                                sp.blockSignals(False)
                            except Exception:
                                pass
    # sliders that mirror the shares
    for sattr, lattr, key in (("slider_multidim_canon", "lbl_multidim_canon", "multidim_canon"),
                              ("slider_multidim_mix", "lbl_multidim_mix", "multidim")):
        sl = getattr(app, sattr, None)
        if sl is not None and isinstance(st, dict):
            try:
                sl.blockSignals(True)
                sl.setValue(int(round(float(st.get(key, share)) * 100)))
                sl.blockSignals(False)
                lab = getattr(app, lattr, None)
                if lab is not None:
                    lab.setText("%d%%" % sl.value())
            except Exception:
                pass
    for key in ("ball", "cellular", "wavetable"):
        sp = getattr(app, "spin_%s_canonical_share" % key, None)
        if sp is not None:
            try:
                sp.blockSignals(True)
                sp.setValue(share)
                sp.blockSignals(False)
            except Exception:
                pass
    # Mode combo and protect checkbox, wherever they live.
    cb = getattr(app, "combo_canonical_mode", None)
    if cb is not None:
        try:
            cb.blockSignals(True)
            idx = cb.findData(mode)
            if idx >= 0:
                cb.setCurrentIndex(idx)
            cb.blockSignals(False)
        except Exception:
            pass
    for name in ("chk_canonical_protect", "chk_algo_protect_userdata"):
        chk = getattr(app, name, None)
        if chk is not None:
            try:
                chk.blockSignals(True)
                chk.setChecked(bool(prot))
                chk.setToolTip("Protected userdata: your edits are kept. Canonical fills everything you have not touched.")
                chk.blockSignals(False)
            except Exception:
                pass
    if refresh:
        for fn in ("refresh_controls", "_sync_canonical_widgets_from_state", "_geo_buffer_store",
                   "_on_live_source_changed", "_r32_geo_refresh_soon", "_refresh_canonical_ownership_labels"):
            f = getattr(app, fn, None)
            if callable(f):
                try:
                    f()
                except Exception:
                    pass
    return mode


def refresh_controls(app):
    """Push current user + canonical state into every mirror widget. Safe to call often."""
    mode = getattr(app, "canonical_mode", None) or DEFAULT
    apply(app, mode, refresh=False)
    for fn in ("_sync_canonical_widgets_from_state", "_refresh_canonical_ownership_labels",
               "_refresh_canonical_fingerprint", "_refresh_canonical_explain"):
        f = getattr(app, fn, None)
        if callable(f):
            try:
                f()
            except Exception:
                pass


def ensure_default(app):
    """Called once at startup / project load: a project without a stored mode gets the default."""
    mode = getattr(app, "canonical_mode", None)
    if mode not in {m[0] for m in MODES}:
        apply(app, DEFAULT, refresh=False)
    return app.canonical_mode


def make_combo(app, parent=None):
    """A QComboBox bound to apply(); safe to put on any panel."""
    from PyQt6.QtWidgets import QComboBox
    cb = QComboBox(parent)
    for key, label, _s, _p in MODES:
        cb.addItem(label, key)
    cur = getattr(app, "canonical_mode", DEFAULT)
    idx = max(0, cb.findData(cur))
    cb.setCurrentIndex(idx)
    cb.setToolTip("How every synth works together with the canonical engines.\n"
                  "Protected Userdata: your presets are never rewritten.\n"
                  "Direct Seeded: the seed owns every parameter.")
    cb.currentIndexChanged.connect(lambda i: apply(app, cb.itemData(i)))
    app.combo_canonical_mode = cb
    return cb
