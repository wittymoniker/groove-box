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


def _composition_vars(app):
    """CANON_VECTOR_R7: the composition / FX part of the instrument toolkit as (Var, normalized target) pairs."""
    import canonical_vector as cv
    u = {k: _seed_unit(app, k) for k in ("eqr", "fractal", "convolve", "base", "sharp", "pkp", "energy", "harmonic", "fx_global")}
    out = []

    def add(var, target):
        if var is not None:
            out.append((var, min(1.0, max(0.0, float(target)))))
    # Seed formulas are unchanged; they are expressed as fractions of each control's range (the old path wrote
    # 0–0.3 into the 0–100 EQR / fractalizer spins, i.e. almost zero).
    add(cv.widget_var(app, "slider_eqr", {"brightness": .6, "complexity": .4}), 0.3 * u["eqr"])
    add(cv.widget_var(app, "slider_fractalizer", {"complexity": 1.0, "geometry": .3}), 0.35 * u["fractal"])
    add(cv.widget_var(app, "spin_global_convolve", {"space": 1.0}), 0.2 + 0.6 * u["convolve"])
    bf = cv.widget_var(app, "spin_base_frequency", {"brightness": .5, "energy": .2}, log=True, lo=20.0, hi=20000.0)
    if bf is not None:
        add(bf, bf.norm(220.0 + 440.0 * u["base"]))
    add(cv.widget_var(app, "dial_project_sharp", {"brightness": .5, "energy": .5}), 0.30 + 0.40 * u["sharp"])
    pk = cv.widget_var(app, "slider_pkp_envelope", {"energy": .7, "motion": .5})
    if pk is not None:
        add(pk, pk.norm(400.0 * u["pkp"]))
    add(cv.widget_var(app, "dial_track_energy", {"energy": 1.0}), 0.5 + 0.3 * (u["energy"] - 0.5))
    add(cv.widget_var(app, "dial_track_harmonic", {"brightness": .4, "complexity": .6}), 0.5 + 0.3 * (u["harmonic"] - 0.5))
    st = getattr(app, "r32_fx_state", None)
    if isinstance(st, dict):
        g = st.setdefault("global", {})
        ug = u["fx_global"]
        add(cv.dict_var(g, "pkp", 0.0, 1.0, {"energy": .3, "motion": .6}, "fx.global.pkp"), 0.4 * ug)
        add(cv.dict_var(g, "fractal", 0.0, 1.0, {"complexity": .7}, "fx.global.fractal"), 0.35 * ((ug * 7) % 1))
        add(cv.dict_var(g, "eqr", 0.0, 1.0, {"brightness": .4}, "fx.global.eqr"), 0.3 * ((ug * 13) % 1))
    return out


def _geometry_vars(app, share):
    """Ball / cellular canonical numbers that have a spin: one Var each (writes the spin and the store)."""
    import canonical_vector as cv
    out = []
    fn = getattr(app, "_geometric_convolution_defaults", None)
    try:
        fac = fn() if callable(fn) else None
    except Exception:
        fac = None
    if not isinstance(fac, dict):
        return out
    for lane, store_name, prefix, tag in (("ball", "ball_synth_params", "spin_ball_", "motion"),
                                          ("cellular", "cellular_synth_params", "spin_ca_", "complexity")):
        locked = bool(getattr(app, "ball_manual_activity_locked", False)) if lane == "ball" \
            else bool(getattr(app, "ca_single_cell_activity_locked", False))
        store = getattr(app, store_name, None)
        vals = fac.get(lane)
        if locked or not isinstance(store, dict) or not isinstance(vals, dict):
            continue
        store["canonical_share"] = share
        for k, v in vals.items():
            if k in ("x", "y", "manual_cells") or not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            var = cv.widget_var(app, prefix + k, {"geometry": 1.0, tag: .5}, track=False)
            if var is None:
                store[k] = v                      # no control for it: plain store value, as before
                continue
            inner = var.set

            def _set(val, inner=inner, store=store, k=k):
                inner(val); store[k] = val
            var.set = _set
            out.append((var, var.norm(v)))
    return out


def vector_write(app, mode, share, cap=None, glide=True):
    """One minimum-norm canonical write over every composition, FX and geometry control the canonicals own."""
    import canonical_vector as cv
    fx_mode = {"protected": "mix", "global50": "mix", "direct": "canonical"}.get(mode, "mix")
    st = getattr(app, "r32_fx_state", None)
    if isinstance(st, dict):
        st.setdefault("global", {})["mode"] = fx_mode
        for _name, store in (st.get("local") or {}).items():
            if isinstance(store, dict):
                store["mode"] = fx_mode
    pairs = _composition_vars(app) + _geometry_vars(app, share)
    vars_ = [p[0] for p in pairs]
    targets = {p[0].name: p[1] for p in pairs}
    touched = set(getattr(app, "_canonical_field_touched", None) or ())

    def owner(name):                          # geometry lanes keep their own per-field ownership
        for prefix, lane in (("spin_ball_", "ball:"), ("spin_ca_", "cellular:")):
            if name.startswith(prefix):
                return (lane + name[len(prefix):]) in touched
        return name in touched                # STEP_AUTOMATION_R7: step-recorded parameters are yours
    cap = cv.CAP if cap is None else cap
    st = cv._state(app)
    try:
        sig = int(getattr(app, "_seed_program_signature", lambda: 0)() or 0)
    except Exception:
        sig = 0
    rep = cv.step(app, vars_, targets, mode, cap=cap, owner=owner)
    if sig != st.get("sig"):
        # A new seed is a new piece: walk the same small min-norm steps to the end now, so audio / video /
        # game exports always read exactly the seed's values (history never leaks into the output).
        st["sig"] = sig
        for _ in range(200):
            if rep["remaining"] <= 1e-6:
                break
            rep = cv.step(app, vars_, targets, mode, cap=cap, owner=owner)
        rep["settled"] = True
    elif rep["remaining"] > 1e-6 and glide:
        _glide(app)                          # mode change / give back: glide there in small steps
    return rep


def _glide(app):
    """Keep stepping every 30 ms until the canonical-owned controls reach the seed values (bounded)."""
    try:
        from PyQt6.QtCore import QTimer
    except Exception:
        return
    t = getattr(app, "_canon_glide_timer", None)
    if t is None:
        try:
            t = app._canon_glide_timer = QTimer(app)
        except Exception:
            return
        t.setInterval(30)

        def _tick():
            app._canon_glide_left = int(getattr(app, "_canon_glide_left", 0)) - 1
            try:
                apply(app, getattr(app, "canonical_mode", None) or DEFAULT, refresh=False, glide=False)
                rep = getattr(app, "_canon_vec_report", None) or {}
            except Exception:
                rep = None
            if not rep or rep.get("remaining", 0) <= 1e-6 or app._canon_glide_left <= 0:
                t.stop()
        t.timeout.connect(_tick)
    app._canon_glide_left = 80
    if not t.isActive():
        t.start()


def settle(app):
    """Finish any glide now (call before reading controls for a render)."""
    for _ in range(200):
        apply(app, getattr(app, "canonical_mode", None) or DEFAULT, refresh=False, glide=False)
        if (getattr(app, "_canon_vec_report", None) or {}).get("remaining", 0) <= 1e-6:
            break
    t = getattr(app, "_canon_glide_timer", None)
    if t is not None:
        t.stop()
    return getattr(app, "_canon_vec_report", None)


def _apply_fx_and_composition(app, mode, share, cap=None, glide=True):
    return vector_write(app, mode, share, cap, glide)


def apply(app, mode=DEFAULT, *, refresh=True, cap=None, glide=True):
    mode = mode if mode in {m[0] for m in MODES} else DEFAULT
    if cap is None:                                   # a mode change takes a larger (still bounded) step
        import canonical_vector as _cv
        cap = _cv.CAP_MODE if getattr(app, "canonical_mode", None) != mode else _cv.CAP
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
    # CANON_VECTOR_R7: FX, composition and geometry controls are written by one minimum-norm vector step
    # (canonical_vector): every owned control moves a little toward the seed, features first, user edits kept.
    try:
        app._canon_vec_report = rep = _apply_fx_and_composition(app, mode, share, cap, glide)
        lab = getattr(app, "lbl_canon_vec", None)
        if lab is not None:
            import canonical_vector as _cv
            lab.setText(f"{rep['written']} canonical · {rep['user_owned']} yours")
            lab.setToolTip(_cv.explain(app) + ("\nYours: " + ", ".join(_cv.owned_by_user(app)) if rep["user_owned"] else ""))
    except Exception as _exc:
        print(f"[Canonical] vector write skipped: {_exc}")
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
