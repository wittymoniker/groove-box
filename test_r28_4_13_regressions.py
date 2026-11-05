from pathlib import Path
from mathematical_composition_lab import generate_pattern

ROOT = Path(__file__).resolve().parent

def test_math_lab_controls_are_inside_scroll_area_and_deterministic():
    src=(ROOT/'mathematical_composition_lab.py').read_text(errors='ignore')
    assert 'QScrollArea(dlg)' in src and 'scroll.setWidgetResizable(True)' in src
    assert 'content.setMinimumWidth(0)' in src and 'scroll.setVerticalScrollBarPolicy' in src
    # GROOVEBOX_R23R_MATH_LAB_WORDING_20261031: the old "All generated structures
    # and STEP control curves are deterministic" was reworded to the shorter
    # deterministic tooltip contract.
    assert 'All structures are deterministic' in src
    assert 'Apply to Selected Sequence' in src and 'root.addLayout(row)' in src
    a=generate_pattern('Seeded deterministic density', steps=16, density=.4, seed=7, bars=2)
    b=generate_pattern('Seeded deterministic density', steps=16, density=.4, seed=7, bars=2)
    assert a == b
    assert a['step_automation']['trigger_probability'] == b['step_automation']['trigger_probability']

def test_master_volume_has_dedicated_visible_row():
    # GROOVEBOX_R28_4_24_MASTER_VOLUME_PERFORMANCE_20261031: the only visible synth
    # Master Volume control lives in Performance. The Main window keeps one
    # parentless, permanently hidden compatibility slider (slider_master_vol with
    # WA_DontShowOnScreen) for legacy project serialization. No Master Volume
    # title/value widgets or row are attached to the Main window.
    src=(ROOT/'groovebox.py').read_text(errors='ignore')
    perf=(ROOT/'performance.py').read_text(errors='ignore')
    assert 'self.slider_master_vol = QSlider(None)' in src
    assert 'WA_DontShowOnScreen' in src
    assert 'self.lbl_master_volume_title = None' in src
    assert 'the only visible synth Master Volume control lives in Performance' in src
    # The Performance tab owns the visible Master Volume row.
    assert 'Master Volume' in perf

def test_user_authored_steps_are_not_probability_dropped():
    src=(ROOT/'groovebox.py').read_text(errors='ignore')
    assert '_user_step_hit = bool(s_idx < len(steps) and steps[s_idx])' in src
    # GROOVEBOX_R23R_STOCHASTIC_POINT_DECISION_20261031: the old
    # `_step_threshold < _step_prob` comparison was replaced by the deterministic
    # `_stochastic_point_decision` helper (canonical-only events).
    assert '_event_allowed = _user_step_hit or (' in src
    assert '_canonical_only_event and self._stochastic_point_decision(row_idx, s_idx, op_idx, _step_prob)' in src
    assert '_step_roll' not in src[src.index('_step_controls_for_prob ='):src.index('if _event_allowed:', src.index('_step_controls_for_prob ='))]
    assert 'if not active:' in src[src.index('def _multinode_step_trigger'):src.index('def _apply_canonical_synth_controls')]

def test_video_mic_meter_visible_near_record_controls_and_saves_path():
    src=(ROOT/'video_clip_studio.py').read_text(errors='ignore')
    assert 'self.mic_record_meter = QProgressBar()' in src
    assert 'self.lbl_mic_record_status = QLabel(' in src
    assert "has_input_route = bool(getattr(self, '_audio_devices', None) or getattr(self, '_pa_audio_devices', None))" in src
    assert 'saving to {self._record_final_path}' in src
    assert 'self._append_recording_path(path)' in src

def test_hardware_volume_sync_prepares_and_reconciles_all_playback_controls():
    src=(ROOT/'BUILD_ISO/v35_22zz/sos-hardware-volume-v35_22zz_r23h').read_text(errors='ignore')
    sync=src[src.index('  sync)'):src.index('  *) echo')]
    # GROOVEBOX_R23R_SYNC_NO_ROUTE_PREP_20261031: sync reasserts the persisted
    # desired level to the currently selected mixer but never runs alsactl init
    # and never does route/UCM prep (that is only done by `init`). This avoids
    # overwriting the desired state by sampling a temporarily stale/zero mixer.
    assert 'prepare_route "$c"' not in sync
    assert 'Route/UCM prep is only done by `init`' in sync
    assert 'apply_volume "$c" "$pct"' in sync
    assert 'apply_mute "$c" 0' in sync
