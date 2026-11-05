"""Small deterministic probes for live recording time and imported DJ routing."""
from types import SimpleNamespace
import queue
import shutil
import time

import numpy as np
import pytest

from live_player import LiveRecorder, LiveEngine
from dj_effects import LiveDJEffects, configure_extra_dj


class FrameSink:
    def __init__(self):
        self.values = []

    def write(self, frame):
        self.values.append(int(frame[0, 0, 0]))


@pytest.fixture
def recorder(tmp_path):
    engine = SimpleNamespace(sr=48000, rec=None)
    host = SimpleNamespace(_exports_dir=lambda: str(tmp_path))
    rec = LiveRecorder(host, engine)
    rec.VIDEO_SIZE = (16, 12)
    rec._venc = FrameSink()
    rec.t0 = time.monotonic()
    yield rec
    if not rec._raw.closed:
        rec._raw.close()
    shutil.rmtree(rec.tmpdir, ignore_errors=True)


def frame(value):
    return np.full((12, 16, 3), value, dtype=np.uint8)


def test_audio_samples_not_wall_time_are_the_clock(recorder):
    recorder.t0 -= 600
    recorder._on_audio(np.zeros(24000, np.float32))
    assert recorder.frames_due() == 12


def test_ui_stall_holds_previous_picture_without_time_compression(recorder):
    assert recorder.push_frame(frame(10))
    recorder._on_audio(np.zeros(48000, np.float32))
    assert recorder.push_frame(frame(200))
    recorder._final_video_frames = 24
    recorder._vq.put(None)
    recorder._video_writer()
    assert recorder._venc.values == [10] * 23 + [200]
    assert recorder.frames_written == 24


def test_full_queue_preserves_tail_duration_and_owns_pixels(recorder):
    recorder._vq = queue.Queue(maxsize=2)
    image = frame(10)
    recorder.push_frame(image)
    image.fill(99)
    recorder._on_audio(np.zeros(24000, np.float32))
    recorder.push_frame(frame(50))
    recorder._on_audio(np.zeros(24000, np.float32))
    assert not recorder.push_frame(frame(200))
    assert recorder.frames_dropped == 1
    pending = [recorder._vq.get_nowait(), recorder._vq.get_nowait(), None]
    recorder._vq = queue.Queue()
    for item in pending:
        recorder._vq.put(item)
    recorder._final_video_frames = 24
    recorder._video_writer()
    assert recorder._venc.values == [10] * 11 + [50] * 13


@pytest.mark.parametrize("key", ("beat_gate", "harmonic_fold", "spectral_tilt"))
def test_imported_effect_reaches_live_output_and_recording(key):
    host = SimpleNamespace(master_volume=1.0)
    engine = LiveEngine(host)
    engine.q.put((0, np.linspace(-0.3, 0.3, 2048, dtype=np.float32)))
    amounts = tuple(0.6 if k == key else 0.0 for k in
                    ("goava", "random", "beat_gate", "harmonic_fold", "spectral_tilt"))
    engine.global_fx_state = (amounts, (0.5, (0, 1)), 120.0, 0.0, 0.0, (0, 0.0, 0.0))
    captured = []
    engine.rec = lambda block: captured.append(block)
    output = np.zeros((2048, 1), np.float32)
    engine.callback(output, 2048, None, None)
    assert np.array_equal(captured[0], output[:, 0])
    assert not np.allclose(output[:, 0], np.linspace(-0.3, 0.3, 2048, dtype=np.float32))
    assert np.isfinite(output).all()


def test_disabled_imported_effects_are_exact_bypass():
    host = SimpleNamespace(live_dj_beat_gate=False, live_dj_beat_gate_amount=0.8)
    fx = LiveDJEffects()
    configure_extra_dj(fx, host)
    source = np.linspace(-0.5, 0.5, 4096, dtype=np.float32)
    assert np.array_equal(fx.process(source, start_sample=0), source)
