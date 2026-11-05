from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mathematical_composition_lab import generate_pattern, apply_pattern_to_memory
from sequencer_schema import STEP_LANES, normalize_sequence_memory, lane_values_from_events


def test_math_lab_generates_all_canonical_step_lanes_with_probability_and_spread():
    pattern = generate_pattern(
        kind="Euclidean rhythm", steps=16, pulses=8, seed=17,
        phase_shift=0.2, eq_gain_db=-3.0, sidechain_depth=0.4,
        probability_min=0.2, probability_max=0.8,
        eq_gain_spread_db=2.0, sidechain_spread=0.15,
    )
    lanes = pattern["step_automation"]
    assert set(STEP_LANES).issubset(lanes)
    assert all(len(lanes[name]) == 16 for name in STEP_LANES)
    # GROOVEBOX_R23R_DETERMINISTIC_TRIGGER_20261031: trigger_probability is now
    # always 1.0 (deterministic, no chance gate). The historical sine-based
    # probability profile moved to the deterministic_trigger_profile lane.
    assert all(value == 1.0 for value in lanes["trigger_probability"])
    assert all(0.2 <= value <= 0.8 for value in lanes["deterministic_trigger_profile"])
    assert all(-5.0 <= value <= -1.0 for value in lanes["eq_gain_db"])
    assert all(0.25 <= value <= 0.55 for value in lanes["sidechain_depth"])
    for event in pattern["events"]:
        i = event["step"] - 1
        assert event["step_controls"]["trigger_probability"] == lanes["trigger_probability"][i]
        assert event["probability"] == lanes["trigger_probability"][i]


def test_schema_normalizes_probability_lane_and_legacy_probability_array():
    memory = {"steps": [True, False], "probabilities": [35, 100], "pattern_length": 2}
    normalized = normalize_sequence_memory(memory)
    assert normalized["step_controls"]["trigger_probability"] == [0.35, 1.0]
    assert normalized["probabilities"] == [35, 100]
    projected = lane_values_from_events({"parameters": {"steps": 2}, "events": [
        {"step": 1, "step_controls": {"trigger_probability": 0.25, "eq_gain_db": 3.0}},
        {"step": 2, "step_controls": {"trigger_probability": 0.75, "sidechain_depth": 0.5}},
    ]})
    assert projected["trigger_probability"] == [0.25, 0.75]
    assert projected["eq_gain_db"] == [3.0, 0.0]
    assert projected["sidechain_depth"] == [0.0, 0.5]


def test_video_capture_finalizers_bound_duration_and_do_not_shortest_truncate():
    source = (ROOT / "video_clip_studio.py").read_text()
    start = source.index("    def _finish_software_recording(self):")
    end = source.index("    def _record_format_candidates(self, recdir: str, stamp: str):", start)
    software = source[start:end]
    assert "capture_duration=max(0.05,elapsed)" in software
    assert "'-t',f'{capture_duration:.6f}'" in software
    assert "'shortest'" not in software
    assert "self._sw_audio_accepting=False" in software
    assert "self._stop_mic_capture_pump()" in software


def test_step_controls_are_canonical_and_consumed_by_shared_render():
    source = (ROOT / "groovebox.py").read_text()
    assert 'self.slider_step_phase_shift.valueChanged.connect(self._on_step_phase_shift_slider)' in source
    assert 'self.slider_step_probability.valueChanged.connect(lambda v: self._on_step_control_slider("trigger_probability", v / 100.0))' in source
    assert 'self._canonical_write_sequence_runtime(curr_i, self._current_sequence_index(curr_i))' in source
    assert 'step_eq_gain_track[s_mask]' in source
    assert 'step_sidechain_track[s_mask]' in source
    # GROOVEBOX_R23R_STOCHASTIC_POINT_DECISION_20261031: the old
    # `_step_threshold < _step_prob` comparison was replaced by the deterministic
    # `_stochastic_point_decision` helper.
    assert '_canonical_only_event and self._stochastic_point_decision(row_idx, s_idx, op_idx, _step_prob)' in source
    assert 'Evenly phased deterministic lattice' in source
    assert 'voice = (voice * np.power(10.0, step_eq_gain_track / 20.0)).astype(np.float32)' in source
    assert 'voice = (voice * (1.0 - 0.85 * np.clip(step_sidechain_track, 0.0, 1.0))).astype(np.float32)' in source


def test_all_detected_outputs_is_default_and_refresh_is_async():
    source = (ROOT / "performance.py").read_text()
    router = (ROOT / "media_output_router.py").read_text()
    assert 'AudioTarget("__all_detected__", "All detected outputs (default)"' in source
    assert "self._output_refresh_timer.setInterval(10000)" in source
    assert 'set-default-sink", _combined' in source or 'set-default-sink", combined' in router
    assert 'def _on_output_devices_ready' in source
    # GROOVEBOX_R23R_ALL_DETECTED_EXPLICIT_20261031: the old
    # `if audio and audio.name == "__all_detected__":` was refactored to the
    # explicit_all flag pattern.
    assert 'explicit_all = audio_name == "__all_detected__"' in router


def test_storage_does_not_overwrite_missing_block_device_status():
    source = (ROOT / "performance.py").read_text()
    start = source.index("        rows.append({", source.index("node_present=os.path.exists(dev)"))
    end = source.index("        })", start)
    row = source[start:end]
    assert "'status_code': status_code if node_present else 'DEVICE_NODE_MISSING'" in row
    assert "'status_code': status_code," not in row
    assert "'formattable': '1' if (node_present and is_partition and not protected) else '0'" in row


def test_math_lab_apply_projects_pattern_into_canonical_memory():
    pattern = generate_pattern(
        kind="Euclidean rhythm", steps=8, pulses=4, bars=2, seed=9,
        probability_min=0.3, probability_max=0.7,
        eq_gain_db=2.0, eq_gain_spread_db=1.0,
        sidechain_depth=0.5, sidechain_spread=0.2,
    )
    memory = apply_pattern_to_memory(pattern, {"pattern_length": 16, "steps": [False] * 16})
    assert memory["pattern_length"] == 16
    assert len(memory["steps"]) == len(memory["step_controls"]["trigger_probability"]) == 16
    assert len(memory["step_controls"]["eq_gain_db"]) == 16
    assert len(memory["step_controls"]["sidechain_depth"]) == 16
    assert memory["user_owned_pattern_source"] == "mathematical_composition_lab"
    assert memory["probabilities"] == [round(v * 100) for v in memory["step_controls"]["trigger_probability"]]
    assert sum(memory["steps"]) == pattern["event_count"]


def test_trigger_all_has_no_separate_volume_control():
    source = (ROOT / "groovebox.py").read_text()
    assert "slider_trigger_all_volume" not in source
    assert "lbl_trigger_all_volume" not in source
    assert "trigger_all_volume" not in source
    # GROOVEBOX_R23R_TRIGGER_ALL_COEFF_20261031: the trigger-all additive
    # coefficient changed from 0.15 to np.float32(0.055) (rebalanced mix).
    assert 'mix += (np.float32(0.055) * env * _v).astype(np.float32)' in source


def test_math_lab_dialog_is_scrollable():
    src=(ROOT/'mathematical_composition_lab.py').read_text(errors='ignore')
    assert 'QScrollArea' in src and 'mathCompositionScrollArea' in src
    assert 'setWidgetResizable(True)' in src


def test_video_spool_enqueues_each_frame_once_and_meter_shows_signal_state():
    src=(ROOT/'video_clip_studio.py').read_text(errors='ignore')
    start=src.index('    def _queue_video_spool(')
    end=src.index('    def _on_shared_v4l2_jpeg(', start)
    body=src[start:end]
    assert body.count('self._video_spool_queue.put(') == 1
    assert 'Mic level %p% · LIVE' in src
    assert 'Mic level %p% · NO SIGNAL' in src


def test_audio_only_recording_drains_pcm_writer_before_closing_wave():
    src=(ROOT/'video_clip_studio.py').read_text(errors='ignore')
    start=src.index('    def _stop_audio_input_recording(')
    end=src.index('    def _update_mic_meter(', start)
    body=src[start:end]
    assert body.index('self._stop_mic_source()') < body.index('if wf is not None: wf.close()')
    assert "self._notify_media_created(path, 'recording')" in body
    assert 'self._append_recording_path(path)' in body


def test_hardware_volume_ui_labels_and_session_sync_preserves_real_level():
    ui=(ROOT/'hardware_volume.py').read_text(errors='ignore')
    helper=(ROOT/'BUILD_ISO/v35_22zz/sos-hardware-volume-v35_22zz_r23h').read_text(errors='ignore')
    # GROOVEBOX_R23R_HW_VOLUME_TITLE_20261031: the title changed from
    # 'System Volume:' to 'Hardware Volume' (the sOS helper owns the real
    # ALSA + PipeWire state; UI instances only write through that helper).
    assert "self.title.setText('Hardware Volume')" in ui
    assert "request_hardware_volume('sync')" in ui
    assert 'mirror_session "$pct" "$mute"' in helper
