"""Regression contracts for high-rate / radio-quality audio export."""
from pathlib import Path
import ast
import numpy as np
import wave

SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')


def _helpers():
    tree = ast.parse(SRC)
    names = {'_write_wav_with_provenance', '_read_wav_mono_pcm'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = {'np': np}
    exec(compile(ast.Module(nodes, type_ignores=[]), 'radio_helpers', 'exec'), ns)
    return ns


def test_requested_high_sample_rates_are_exposed():
    for sr in ('96000', '128000', '192000'):
        assert sr in SRC
    assert 'Radio / Broadcast — 48 kHz / 24-bit' in SRC
    assert 'Studio HQ — 96 kHz / 24-bit' in SRC
    assert 'Ultra HQ — 128 kHz / 24-bit' in SRC


def test_96k_and_128k_are_real_pcm24_roundtrips(tmp_path):
    ns = _helpers()
    pcm = np.rint(np.linspace(-1.0, 1.0, 1001) * 8388607.0).astype(np.int32)
    for sr in (96000, 128000):
        out = tmp_path / f'{sr}_24.wav'
        ns['_write_wav_with_provenance'](out, sr, pcm, b'test', bit_depth=24)
        with wave.open(str(out), 'rb') as wf:
            assert wf.getframerate() == sr
            assert wf.getsampwidth() == 3
            assert wf.getnchannels() == 1
        rsr, bits, back = ns['_read_wav_mono_pcm'](str(out))
        assert rsr == sr
        assert bits == 24
        assert np.array_equal(back, pcm)


def test_export_render_rate_is_applied_before_mixdown():
    assert 'self.preferred_sample_rate = export_sample_rate' in SRC
    assert 'master, sample_rate = self._render_mixdown_buffer()' in SRC
    assert 'self.preferred_sample_rate = _prior_sr' in SRC
