from sequencer_schema import normalize_sequence_memory, normalize_sequence_bank, lane_values_from_events
from mathematical_composition_lab import generate_pattern
from composition_state import CompositionEngine

def test_step_lanes_roundtrip_and_legacy_migration():
    legacy={"steps":[True,False,True],"pattern_length":3,"phase_shift":[0.1,0.2,0.3],"custom_owner":"user"}
    n=normalize_sequence_memory(legacy)
    assert n["step_controls"]["phase_shift"] == [0.1,0.2,0.3]
    assert n["step_controls"]["eq_frequency"] == [1000.0]*3
    assert n["custom_owner"] == "user"
    assert normalize_sequence_memory(n) == n

def test_bank_keeps_ids_and_normalizes_each_sequence():
    b=normalize_sequence_bank({"1":{"steps":[True,False]},"A":{"steps":[False]}})
    assert set(b)=={"1","A"}
    assert len(b["1"]["step_controls"]["phase_shift"])==2

def test_math_lab_exports_step_phase_eq_sidechain_lanes():
    p=generate_pattern("Euclidean rhythm",steps=8,pulses=3,phase_shift=.25,eq_gain_db=3,
        eq_frequency=1800,eq_q=1.2,sidechain_depth=.4,phase_mod_depth=.2)
    assert p["sequencer_schema_version"] == 2
    assert p["step_automation"]["phase_shift"] == [.25]*8
    assert p["step_automation"]["eq_gain_db"] == [3.0]*8
    assert p["events"][0]["step_controls"]["sidechain_depth"] == .4


def test_composition_helper_overlay_preserves_unmentioned_step_lanes():
    base = {"instrument": {"steps": [True, False], "step_controls": {"phase_shift": [0.2, 0.4]}, "eq_gain_db": [2, 3]}}
    engine = CompositionEngine(base)
    engine.set_layer("composition_helper", {"instrument": {"steps": [False, True]}})
    result = engine.build()["instrument"]
    assert result["steps"] == [False, True]
    assert result["step_controls"] == {"phase_shift": [0.2, 0.4]}
    assert result["eq_gain_db"] == [2, 3]

def test_active_sequence_is_reconciled_into_selected_bank_slot():
    from sequencer_schema import reconcile_sequence_state
    active, banks, selected = reconcile_sequence_state(
        {"Bass": {"pattern_length": 2, "steps": [True, False], "step_controls": {"phase_shift": [0.5, 0.25]}}},
        {"Bass": {"1": {"pattern_length": 2, "steps": [False, False]}}},
        {"Bass": 1})
    assert banks["Bass"]["1"]["steps"] == [True, False]
    assert active["Bass"]["step_controls"]["phase_shift"] == [0.5, 0.25]
    assert selected["Bass"] == 1


def test_project_snapshot_roundtrip_and_clear_randomize_contracts():
    from pathlib import Path
    src = (Path(__file__).with_name("groovebox.py")).read_text(encoding="utf-8")
    snapshot = src[src.index("def _project_snapshot(self):"):src.index("def _apply_project_snapshot(self, data):")]
    restore = src[src.index("def _apply_project_snapshot(self, data):"):src.index("def _apply_visual_view_state", src.index("def _apply_project_snapshot(self, data):"))]
    clear = src[src.index("def _clear_project_memory(self):"):src.index("# FINITE_INFINITY_MEUM_HYPERDRIVE", src.index("def _clear_project_memory(self):"))]
    assert '"instrument_sequencer_memory"' in snapshot and '"instrument_sequence_banks"' in snapshot
    assert '"math_writer_userdata"' in snapshot and '"userdata_protection"' in snapshot
    assert 'reconcile_sequence_state(' in snapshot and 'reconcile_sequence_state(' in restore
    assert 'self.math_writer_userdata = None' in clear
    assert '"phase_shift"' in clear and '"sidechain_depth"' in clear
    assert 'protect_from_canonical_overwrite", True' in src and '_writer_protection' in src
