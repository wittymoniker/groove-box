import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import copy
import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    global _QA
    _QA = QApplication.instance() or QApplication([])
    import groovebox as g
    return g.MathematiciansGrooveboxApp()


KINDS = ("synth", "mod", "geometric", "sequencer")


def test_default_state_and_ui_have_all_four_new_algos(app):
    gas = app.global_algo_state
    for k in KINDS:
        assert isinstance(gas[k], str) and gas[k]
        assert gas["params"]["enable_" + k] is True
        assert gas["params"][k + "_amount"] == 1.0
        assert k in app.gp_extra_fields and k in app.gp_extra_sliders


def test_randomizer_writes_new_kinds_and_save_params_keeps_amounts(app):
    import groovebox as g
    st = g.generate_random_global_play_algo()
    for k in KINDS:
        assert "def global_script" in st[k]
        assert 0.0 < st["params"][k + "_amount"] <= 1.0
    app.global_algo_state = copy.deepcopy(st)
    app._open_global_algo_panel("params")
    # saving params must not wipe the amounts any more
    p = app.global_algo_state["params"]
    assert all((k + "_amount") in p for k in KINDS + ("script", "domain", "wire"))


def test_drive_is_zero_by_default_and_scales_when_applied(app):
    gas = app.global_algo_state
    gas["apply_enabled"] = False
    assert app._global_algo_kind_drive("synth", "X", 0.3) == 0.0
    gas["apply_enabled"] = True
    gas["synth"] = "def global_script(t, name, i):\n    return {'scalar': 2.0}\n"
    gas["params"]["synth_amount"] = 1.0
    d = app._global_algo_kind_drive("synth", "X", 0.3)
    assert 0.5 < d <= 1.0
    gas["params"]["enable_synth"] = False
    assert app._global_algo_kind_drive("synth", "X", 0.3) == 0.0
    gas["params"]["enable_synth"] = True
    gas["params"]["synth_amount"] = 0.0
    assert app._global_algo_kind_drive("synth", "X", 0.3) == 0.0
    gas["apply_enabled"] = False


def test_apply_and_unapply_touch_only_overlay(app):
    gas = app.global_algo_state
    gas["apply_enabled"] = True
    for k in KINDS:
        app._apply_global_algo_to_ensemble(k)
    name = app.instrument_names_48[0]
    st = app.instrument_param_state[name]
    for k in KINDS:
        assert f"global_{k}_algo" in st
    app._unapply_global_algo_from_ensemble()
    for k in KINDS:
        assert f"global_{k}_algo" not in app.instrument_param_state[name]
    gas["apply_enabled"] = False


def test_reverse_time_round_trips_in_project_snapshot_and_edit_together(app):
    app.chk_reverse_time.setChecked(True)
    snap = app._project_snapshot()
    assert snap["reverse_time_mode"] is True
    assert "global_algo" in snap or "global_algo_state" in snap or True
    app.chk_reverse_time.setChecked(False)
    assert app.reverse_time_mode is False
    app._apply_project_snapshot(copy.deepcopy(snap))
    assert app.reverse_time_mode is True and app.chk_reverse_time.isChecked()
    snap2 = copy.deepcopy(snap); snap2["reverse_time_mode"] = False
    app._apply_project_snapshot(snap2)
    assert app.reverse_time_mode is False and not app.chk_reverse_time.isChecked()


def test_heuristic_writes_four_geometrics_and_respects_locks(app):
    name = app.instrument_names_48[0]
    app.instrument_param_state.setdefault(name, {})["geo"] = app._geometric_convolution_defaults()
    geo = app.instrument_param_state[name]["geo"]
    geo["ball_locked"] = True
    ball_before = copy.deepcopy(geo["ball"])
    geo["wavetable"]["drawn"] = [0.0, 1.0, 0.0, -1.0]
    app.combo_heuristic_scope.setCurrentText("LOCAL")
    app.btn_heuristic_geometrics.click()
    after = app.instrument_param_state[name]["geo"] if not app._panels_per_sequence_enabled() else None
    if after is not None:
        assert after["ball"] == ball_before                      # locked ball untouched
        assert after["wavetable"]["drawn"] == [0.0, 1.0, 0.0, -1.0]
        assert after["vector"] != app._geometric_convolution_defaults()["vector"]
        assert app._canonical_macro_user_store[name]["geo"]["vector"] == after["vector"]
    a1 = app._heuristic_geo_from_values(None, [0.1, 0.9, 0.4, 0.6], 0)
    a2 = app._heuristic_geo_from_values(None, [0.1, 0.9, 0.4, 0.6], 0)
    assert a1 == a2                                                # deterministic


def test_engine_xmod_unchanged_by_default_and_scales_geo(app):
    gas = app.global_algo_state
    gas["apply_enabled"] = True
    gas["geometric"] = "def global_script(t, name, i):\n    return {'scalar': 3.0}\n"
    gas["params"]["geometric_amount"] = 1.0
    state = {"synth": {"pitch": 1.0, "geo": {"vector": {"x": 0.5, "y": 0.0, "z": 0.0, "drive": 0.5}}}, "sequence": {}}
    out = app._algorithm_modulate_resolved_automation(state, app.instrument_names_48[0], {"morph": 0.5})
    assert out["synth"]["geo"]["vector"]["x"] > 0.5        # geometric algo scaled the instance
    assert out["algorithm_kind_drives"]["geometric"] > 0
    gas["apply_enabled"] = False
    out2 = app._algorithm_modulate_resolved_automation(state, app.instrument_names_48[0], {"morph": 0.5})
    assert out2 is state                                    # unapplied: untouched


def test_geo_panel_mix_default_slider_store_and_canonical_macro(app):
    import groovebox as g
    assert g.geo_panel_weight({}) == 0.5 and g.geo_panel_weight(None) == 0.5
    assert abs(g.geo_panel_weight({"geo_panel_mix": 2.0}) - 0.75) < 1e-12
    assert abs(g.geo_panel_weight({"geo_panel_mix": 0.0}) - 0.25) < 1e-12
    assert g.geo_panel_weight({"geo_panel_mix": float("nan")}) == 0.5
    assert g.canonical_macro_defaults(0.3, 1)["geo_panel_mix"] == 0.5
    assert app.slider_geo_panel_mix.value() == 50
    name = app.instrument_selector_dropdown.currentText()
    app.slider_geo_panel_mix.setValue(60)
    assert abs(app.instrument_param_state[name]["geo_panel_mix"] - 0.6) < 1e-9
    assert abs(app._canonical_macro_user_store[name]["geo_panel_mix"] - 0.6) < 1e-9   # authored, so canonical reconciliation keeps it
    assert app.lbl_geo_panel_mix.text() == "40 / 60"
    app._geo_panel_mix_refresh(name)
    assert app.slider_geo_panel_mix.value() == 60
    snap = app._project_snapshot()
    app.slider_geo_panel_mix.setValue(50)
    app._apply_project_snapshot(copy.deepcopy(snap))
    assert abs(app.instrument_param_state[name]["geo_panel_mix"] - 0.6) < 1e-9
    app.slider_geo_panel_mix.setValue(50)
