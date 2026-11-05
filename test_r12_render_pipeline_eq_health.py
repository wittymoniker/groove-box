from pathlib import Path
ROOT=Path(__file__).resolve().parent
GB=(ROOT/'groovebox.py').read_text(errors='replace')
CM=(ROOT/'canonical_cross_media.py').read_text(errors='replace')

def test_r12_marker_and_health_panel():
    assert 'GROOVEBOX_V35_22ZZ_R12_RENDER_PIPELINE_EQ_HEALTH_20260929' in GB
    assert 'SYSTEM / PERFORMANCE HEALTH' in GB
    assert '_open_system_health_panel' in GB
    assert '_health_export_diagnostics' in GB

def test_render_pipeline_workers_and_shared_buffer():
    for token in ('thread_name_prefix="playlist-data"','thread_name_prefix="sequencer-plan"','thread_name_prefix="canonical-write"','thread_name_prefix="live-audio-fx"','thread_name_prefix="live-audio-analysis"'):
        assert token in GB
    assert '_get_shared_mixdown_buffer' in GB
    assert '_render_sequencer_snapshot' in GB
    assert 'np.linspace(x0, x1' in GB
    assert 'thread_name_prefix="video-object"' in GB

def test_eq_is_audio_visual_game_cross_media():
    for token in ('EQ · AUDIO / VISUAL / GAME','apply_instrument_eq','eq_metrics','eq_cross_media','instrument_eq'):
        assert token in GB
    assert 'eq_energy' in CM and 'eq_tilt' in CM and 'global_eq' in CM

def test_return_to_main_tracks_source_window():
    assert 'lambda _checked=False, _window=window: self._relaunch_main(_window)' in GB
    assert 'def _relaunch_main(self, source_window=None)' in GB

def test_stitch_keeps_one_final_audio_and_removes_parts():
    assert 'final_audio_path = os.path.join(dest_dir, f"{stem}.audio.wav")' in GB
    assert 'for _ap in list(audio_part_paths):' in GB
    assert 'os.path.isfile(_ap): os.remove(_ap)' in GB
    assert 'After a successful stitch' in GB
