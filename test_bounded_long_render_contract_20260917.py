from pathlib import Path
SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

def test_bounded_long_render_contract():
    assert 'BOUNDED_LONG_RENDER_20260917' in SRC
    assert 'fps * 60 * 30' not in SRC
    assert '_write_wav_float32_streaming(audio_path' in SRC
    assert '_fft_convolve_prefix_bounded(master, kernel' in SRC
    assert '_eqr_spatial_block' in SRC
    assert '_chunked_rms(canonical_bus)' in SRC
    assert 'row_idx * n_samples + rows - 1' in SRC
