"""project_schema.py — GROOVEBOX_R105_PROJECT_SCHEMA_20261118

Keeps the project document stable while the program keeps growing, and lets Groovebox describe
(reverse-engineer) its own state.

1. ONE SECTION for everything R32 adds:  doc["r32"] = {"schema": N, <key>: <state>, …}
   Every key in STATE is saved with the project and restored on load, so all engines (audio,
   video, games, panels) read the same values after a save/load or a co-edit sync.
2. SCHEMA VERSION + MIGRATIONS: documents written by older builds are upgraded in place by the
   ordered MIGRATIONS (never by guessing); unknown future keys are kept untouched (forward-safe),
   so a newer document opened in an older build loses nothing when saved again.
3. MANIFEST (self-description): manifest(app) lists every persisted key, its owner module, its
   type and a content hash — the same document a co-edit peer or the File Studio MCC editor sees.
4. SYNC CHECK: verify(app) round-trips the section (snapshot → apply → snapshot) and reports any
   key whose value does not survive, i.e. any engine that would fall out of sync.
"""
from __future__ import annotations

import copy
import hashlib
import json

SCHEMA = 4

# key: (attribute on the app, owner module, default)
STATE = {
    "fx": ("r32_fx_state", "fx_panels", None),
    "time_fx": ("r32_time_fx", "fx_panels", None),
    "synth_engine": ("r32_synth_engine", "synth_engine_panel", None),
    "canonical_mode": ("canonical_mode", "canonical_mode", "protected"),
    "canonical_owned": ("_canon_user_owned", "canonical_vector", None),   # CANON_VECTOR_R7: controls you own
    "divergence": ("seed_divergence", "seed_divergence", None),
    "divergence_user": ("_r32_divergence_user", "seed_divergence", None),
    "game_overrides": ("r32_game_overrides", "game_editor", None),
    "game_macros": ("r32_game_macros", "game_editor", None),
    "expression_matrix": ("r32_expression_matrix", "media_expression", None),
    "expression_mode": ("r32_expression_mode", "media_expression", "composition"),
    "key": ("r32_key", "r32_deck", None),
    "tuning": ("r32_tuning", "composition_tools", "linear (legacy)"),
    "playback_style": ("r32_playback_style", "composition_tools", "forward"),
    "song_form": ("r32_song_form", "composition_tools", None),
    "active_instruments": ("r32_active_instruments", "project_blueprint", None),
    "blueprint": ("project_blueprint", "project_blueprint", None),
    "post": ("blueprint_post_settings", "postprocess_window", None),
    "project_macros": ("project_macro_values", "project_blueprint", None),
    "snapshots": ("r32_snapshots", "r32_deck", None),
    "mod_osc": ("r32_mod_osc", "mod_osc", None),
    "eq": ("r32_eq", "layer_mixer", None),
    "instrument_colors": ("r32_instrument_colors", "groovebox", None),
    "predictive_fx": ("r32_predictive", "predictive_fx", None),
    "automation": ("r32_automation", "automation_bus", None),
    "step_automation": ("step_automation_state", "step_automation", None),   # STEP_AUTOMATION_R7
    "live_rig_scale": ("live_rig_scale", "live_player", None),
    "live_morph": ("live_morph_state", "live_player", None),   # CANON_MORPH_R7 + PREDICTIVE_PATHWAY_R7
    "inst_mix": ("r32_inst_mix", "instrument_mixer", None),
    "perseq": ("r32_perseq", "perseq_vars", None),
    "game_morph": ("r32_game_morph", "game_editor", None),
    "rand_source": ("rand_source", "groovebox", "fractal"),
    "convolve_tracks": ("convolve_tracks_workspace", "groovebox", True),
    "video_goava_shapes": ("video_goava_shapes", "groovebox", True),
    "video_sample_objs": ("video_sample_objs", "project_obj", True),
    "video_obj_path": ("video_obj_path", "project_obj", None),
    "video_obj_wire": ("video_obj_wire", "project_obj", True),
    "video_lsystem": ("video_lsystem", "project_obj", True),
    "video_obj_opacity": ("video_obj_opacity", "project_obj", 1.0),
    "video_context_fx": ("video_context_fx", "project_obj", False),
    "video_context_strength": ("video_context_strength", "project_obj", 0.5),
    "live_visuals_follow_canonicals": ("live_visuals_follow_canonicals", "live_player", True),
    "video_obj_paths": ("video_obj_paths", "project_obj", None),
    "video_obj_scene": ("video_obj_scene", "project_obj", None),
    "mod_matrix": ("r99_mod_matrix", "mod_matrix", None),
    "mod_matrix_canonical": ("r99_mod_matrix_canonical", "mod_matrix", 0.5),
    "mod_matrix_governor": ("r101_mm_governor", "mod_matrix", None),
    "mod_matrix_mirror": ("r101_mm_mirror", "mod_matrix", None),
    "quick_note": ("r101_quick_note", "groovebox", ""),
    "mod_matrix_fields": ("r101_mm_fields", "mod_matrix", None),       # R101 reroute + perspective fields       # R101 mirrors beside the Multidim synth   # R101 governor + fair canonical share
    "canonical_distribution": ("r99_canon_dist", "canonical_distributor", None),
    "plugin_bindings": ("r99_plugin_bindings", "plugin_library", None),
    "carrier_layers": ("r99_carrier_layers", "carrier_layers", None),
    "inst_user_synths": ("instrument_user_synth_numbers", "groovebox", None),
    "sample_routes": (None, "sample_generator", None),          # special: routes + settings per scope
    "video_obj_embed": (None, "project_obj", None),             # special: the video OBJ travels with the project
    "performance_scenes": ("groovebox_performance_scenes", "groovebox_intelligence", None),
    "parameter_registry": ("groovebox_parameter_registry", "groovebox_intelligence", None),
    "intelligence_settings": ("groovebox_intelligence_settings", "groovebox_intelligence", None),
}

# Ordered upgrades: (from_version, function(section) -> section)
def _m1_to_2(sec):
    # R32.1–R32.4 kept FX in a flat dict; R32.5 split global / local
    fx = sec.get("fx")
    if isinstance(fx, dict) and "global" not in fx:
        sec["fx"] = {"global": fx, "local": {}}
    return sec


def _m3_to_4(sec):
    # R105: unified intelligence layer state; absent keys remain backward-compatible.
    sec.setdefault("performance_scenes", {})
    sec.setdefault("parameter_registry", {"schema": 1, "parameters": [], "routes": {}})
    sec.setdefault("intelligence_settings", {"schema": 1})
    return sec


def _m2_to_3(sec):
    # R32.6: canonical share defaults moved to 100 % — documents without a mode get the default
    sec.setdefault("canonical_mode", "protected")
    return sec


MIGRATIONS = ((1, _m1_to_2), (2, _m2_to_3), (3, _m3_to_4))


def _jsonable(v):
    try:
        return json.loads(json.dumps(v, default=str))
    except Exception:
        return None


def _sample_state(app):
    out = {}
    try:
        g = getattr(app, "r32_sample_global", None)
        if g is not None:
            out["global"] = {"kind": g.kind, "seconds": g.seconds, "layer": g.layer, "ratio_set": g.ratio_set, "routes": list(g.routes)}
        loc = {}
        for name, gen in (getattr(app, "r32_sample_local", {}) or {}).items():
            loc[name] = {"kind": gen.kind, "seconds": gen.seconds, "layer": gen.layer, "ratio_set": gen.ratio_set, "routes": list(gen.routes)}
        out["local"] = loc
    except Exception:
        pass
    return out


def _restore_samples(app, st):
    if not isinstance(st, dict):
        return
    try:
        import sample_generator as sg
        sg.install_hooks(app)

        def _mk(d):
            gen = sg.SampleGenerator()
            for k in ("kind", "seconds", "layer", "ratio_set"):
                if k in d:
                    setattr(gen, k, d[k])
            gen.routes = list(d.get("routes") or [])
            if gen.layer > 0:
                gen.render(app)                 # deterministic: same seed → same buffer
            return gen
        if isinstance(st.get("global"), dict):
            app.r32_sample_global = _mk(st["global"])
        app.r32_sample_local = {n: _mk(d) for n, d in (st.get("local") or {}).items() if isinstance(d, dict)}
    except Exception:
        pass


def snapshot(app):
    sec = {"schema": SCHEMA}
    for key, (attr, _owner, default) in STATE.items():
        if key == "sample_routes":
            sec[key] = _sample_state(app); continue
        if key == "video_obj_embed":
            try:
                import project_obj as _po
                v = _po.embed_state(app)
                if v is not None:
                    sec[key] = v
            except Exception:
                pass
            continue
        v = getattr(app, attr, default)
        if v is not None:
            sec[key] = _jsonable(v)
    extra = getattr(app, "_r32_unknown_keys", None)
    if isinstance(extra, dict):
        for k, v in extra.items():
            sec.setdefault(k, v)                 # keep keys a newer build wrote
    return sec


def migrate(sec):
    sec = dict(sec or {})
    v = int(sec.get("schema", 1) or 1)
    for frm, fn in MIGRATIONS:
        if v <= frm < SCHEMA:
            sec = fn(sec); v = frm + 1
    sec["schema"] = max(v, SCHEMA)
    return sec


def apply(app, sec):
    if not isinstance(sec, dict):
        return []
    sec = migrate(sec)
    unknown = {k: v for k, v in sec.items() if k != "schema" and k not in STATE}
    app._r32_unknown_keys = unknown
    restored = []
    for key, (attr, _owner, default) in STATE.items():
        if key not in sec:
            continue
        if key == "sample_routes":
            _restore_samples(app, sec[key]); restored.append(key); continue
        if key == "video_obj_embed":
            try:
                import project_obj as _po
                _po.restore_embed(app, sec[key]); restored.append(key)
            except Exception:
                pass
            continue
        v = copy.deepcopy(sec[key])
        cur = getattr(app, attr, None)
        if isinstance(cur, dict) and isinstance(v, dict):
            cur.clear(); cur.update(v)
        else:
            setattr(app, attr, v)
        restored.append(key)
    # engines that keep derived state re-read it
    try:
        import canonical_mode
        canonical_mode.apply(app, getattr(app, "canonical_mode", "protected"), refresh=False)
    except Exception:
        pass
    for fn in ("_r32_geo_refresh_soon",):
        f = getattr(app, fn, None)
        if callable(f):
            try:
                f()
            except Exception:
                pass
    return restored


def manifest(app):
    sec = snapshot(app)
    rows = []
    for key, (attr, owner, _d) in STATE.items():
        v = sec.get(key)
        h = hashlib.blake2b(json.dumps(v, sort_keys=True, default=str).encode(), digest_size=6).hexdigest()
        rows.append({"key": key, "attribute": attr or "(computed)", "owner": owner, "type": type(v).__name__,
                     "present": v is not None, "hash": h})
    return {"schema": SCHEMA, "keys": rows}


def verify(app):
    """Round-trip the section and report keys that do not survive (an engine out of sync)."""
    a = json.dumps(snapshot(app), sort_keys=True, default=str)
    apply(app, json.loads(a))
    b = json.dumps(snapshot(app), sort_keys=True, default=str)
    if a == b:
        return True, []
    da, db = json.loads(a), json.loads(b)
    return False, sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k))
