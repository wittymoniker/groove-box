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
    if refresh:
        for fn in ("_sync_canonical_widgets_from_state", "_geo_buffer_store", "_on_live_source_changed", "_r32_geo_refresh_soon"):
            f = getattr(app, fn, None)
            if callable(f):
                try:
                    f()
                except Exception:
                    pass
    return mode


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
