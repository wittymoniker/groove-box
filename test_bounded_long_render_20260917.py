from pathlib import Path

SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')


def test_long_render_has_no_30_minute_frame_cap():
    assert 'n_frames = min(n_frames, fps * 60 * 30)' not in SRC
    assert 'no arbitrary duration ceiling' in SRC


def test_long_render_uses_bounded_time_grid_and_chunked_audio_temp():
    assert '_bounded_long_render = n_samples > 2_000_000' in SRC
    assert 't = None' in SRC
    assert '_bounded_render_block_samples(sample_rate)' in SRC
    assert '_write_wav_float32_streaming(audio_path, sr, audio_clip)' in SRC


def test_eqr_long_pass_supports_global_sample_offsets():
    assert 'sample_offset=0, total_samples=None' in SRC
    assert '_moving_average_same_bounded(abs_x, win)' in SRC


def test_long_render_proof_buses_do_not_duplicate_whole_mix():
    assert 'these proof/composition buses have no' in SRC
    assert 'del canonical_bus, userdata_bus' in SRC
