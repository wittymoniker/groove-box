from pathlib import Path

SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')


def test_project_schema_bumped():
    assert '"version": "3.9.0-project-state-integrated"' in SRC


def test_new_project_controls_share_ui_state_contract():
    for name in (
        'spin_track_offset', 'spin_canonical_convolve', 'spin_canonical_live_overblend',
        'global_xmod_slider', 'global_input_xmod_slider',
    ):
        assert f'"{name}"' in SRC


def test_history_includes_recent_feature_families():
    required = (
        'automation_patterns', 'master_vector_state', 'wavetable_projector_state',
        'sample_morph_state', 'global_mod_state', 'algorithm_xmod_local',
        'algorithm_xmod_global', 'media_carrier_slot', 'carrier_binding_mode',
        'carrier_bound_layers_state', 'live_dj_random_script',
        '_live_dj_random_generation', 'canonical_continuation_enabled',
        'canonical_resonance_factor', '_canonical_user_blend_ledger',
        '_canonical_activity_ledger', '_last_videogame_identity',
        '_last_videogame_path', 'media_workbench_state',
        'instrument_media_samples_state', 'visual_view_state', 'project_notes',
    )
    start = SRC.index('def _project_history_snapshot')
    end = SRC.index('def _push_undo', start)
    block = SRC[start:end]
    for key in required:
        assert key in block


def test_history_media_excludes_raw_waveform_snapshot():
    start = SRC.index('def _project_history_media_samples')
    end = SRC.index('def _restore_project_history_media_samples', start)
    block = SRC[start:end]
    assert '"waveform"' not in block
    assert 'video_path' in block
    assert 'layered_state' in block
    assert 'bound_layers_state' in block


def test_redo_pushes_pre_redo_state_to_undo():
    start = SRC.index('def _do_redo')
    end = SRC.index('def _sync_undo_buttons', start)
    block = SRC[start:end]
    assert 'prior = self._project_history_snapshot()' in block
    assert 'self._undo_stack.append((clean_label, prior))' in block
    assert 'self._undo_stack.append((label, snap))' not in block
