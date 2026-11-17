import os, struct, tempfile
import pytest

import export_integrity as ei


def _wav(path, code=1, bits=16, frames=128, rate=48000):
    channels = 1; width = bits // 8; align = channels * width
    payload = b'\0' * (frames * align)
    fmt = struct.pack('<HHIIHH', code, channels, rate, rate * align, align, bits)
    body = b'WAVE' + b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(payload)) + payload
    with open(path, 'wb') as f: f.write(b'RIFF' + struct.pack('<I', len(body)) + body)


def test_wav_pcm_and_float_are_verified(tmp_path):
    for code, bits in ((1, 16), (3, 32)):
        p = tmp_path / f'a{code}.wav'; _wav(p, code, bits)
        r = ei.verify_file(p)
        assert r['frames'] == 128 and r['sample_rate'] == 48000
        assert r['encoding'] == ('float' if code == 3 else 'pcm')
        assert len(r['sha256']) == 64


def test_truncated_or_invalid_wav_fails(tmp_path):
    p = tmp_path / 'bad.wav'; p.write_bytes(b'RIFF' + b'\0' * 100)
    with pytest.raises(ei.ExportIntegrityError): ei.verify_file(p)


def test_npy_finite_check_and_nonfinite_rejection(tmp_path):
    np = pytest.importorskip('numpy')
    good = tmp_path / 'good.npy'; np.save(good, np.arange(100, dtype=np.float32))
    assert ei.verify_file(good)['finite'] is True
    bad = tmp_path / 'bad.npy'; np.save(bad, np.array([0.0, np.nan], dtype=np.float32))
    with pytest.raises(ei.ExportIntegrityError): ei.verify_file(bad)


def test_empty_output_list_fails():
    with pytest.raises(ei.ExportIntegrityError): ei.verify_outputs([])
