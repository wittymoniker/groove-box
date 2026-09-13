import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

import numpy as np

from audio_export_integrity import (
    quantize_float_master,
    normalized_pcm_peak,
    decoded_peak_db,
    verify_encoded_level,
)


def _write_pcm24_wav(path, sr, pcm):
    vals = np.asarray(pcm, dtype=np.int64).reshape(-1)
    vals = np.clip(vals, -8388608, 8388607).astype(np.int32, copy=False)
    u = vals.astype(np.uint32, copy=False) & np.uint32(0xFFFFFF)
    packed = np.empty((u.size, 3), dtype=np.uint8)
    packed[:, 0] = (u & 0xFF).astype(np.uint8)
    packed[:, 1] = ((u >> 8) & 0xFF).astype(np.uint8)
    packed[:, 2] = ((u >> 16) & 0xFF).astype(np.uint8)
    data = packed.tobytes()
    fmt = struct.pack('<HHIIHH', 1, 1, sr, sr * 3, 3, 24)
    body = b'fmt ' + struct.pack('<I', len(fmt)) + fmt
    body += b'data' + struct.pack('<I', len(data)) + data
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 4 + len(body)) + b'WAVE' + body)


class MP3ExportIntegrityTests(unittest.TestCase):
    def test_24bit_quantization_uses_full_24bit_scale(self):
        master = np.array([-1.0, -0.5, 0.0, 0.5, 1.0], dtype=np.float32)
        pcm = quantize_float_master(master, 24)
        self.assertEqual(pcm.dtype, np.int32)
        self.assertEqual(int(pcm[-1]), 8388607)
        self.assertGreater(abs(int(pcm[1])), 4_000_000)
        self.assertAlmostEqual(normalized_pcm_peak(pcm, 24), 1.0, places=6)

    def test_16bit_quantization_stays_16bit(self):
        master = np.array([-1.0, 0.5, 1.0], dtype=np.float32)
        pcm = quantize_float_master(master, 16)
        self.assertEqual(pcm.dtype, np.int16)
        self.assertEqual(int(pcm[-1]), 32767)

    def test_old_bug_would_be_about_48db_quiet(self):
        old_peak = 32767.0 / 8388607.0
        attenuation = -20.0 * math.log10(old_peak)
        self.assertGreater(attenuation, 48.0)
        self.assertLess(attenuation, 48.3)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg unavailable')
    def test_24bit_master_survives_real_mp3_encode(self):
        ffmpeg = shutil.which('ffmpeg')
        sr = 48000
        t = np.arange(sr * 2, dtype=np.float32) / sr
        master = 0.55 * np.sin(2.0 * np.pi * 440.0 * t)
        pcm = quantize_float_master(master, 24)
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, 'master24.wav')
            mp3 = os.path.join(td, 'master.mp3')
            _write_pcm24_wav(wav, sr, pcm)
            proc = subprocess.run(
                [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-i', wav,
                 '-c:a', 'libmp3lame', '-b:a', '192k', mp3],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertGreater(os.path.getsize(mp3), 1000)
            db = decoded_peak_db(ffmpeg, mp3)
            self.assertIsNotNone(db)
            self.assertGreater(db, -12.0)  # 0.55 ~= -5.2 dBFS; allow codec margin.
            ok, note = verify_encoded_level(ffmpeg, mp3, float(np.max(np.abs(master))))
            self.assertTrue(ok, note)

    def test_groovebox_export_calls_depth_aware_quantizer(self):
        text = Path('groovebox.py').read_text(encoding='utf-8')
        self.assertIn('pcm = quantize_float_master(master, export_bit_depth)', text)
        self.assertIn('expected_float_peak=_export_peak', text)
        self.assertIn('verify_encoded_level(', text)
        self.assertNotIn('pcm = (np.clip(master, -1.0, 1.0) * 32767.0).astype(np.int16)', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
