"""Play must be audible with the key-audition stream around (PLAY_KEYS_ON_TRANSPORT_20261102).

A fake output device records every stream that is opened. The audition stream is opened first (a key
hit), then the transport; the audition stream must be closed, the transport callback must produce sound,
and later key hits must join the transport through the concurrent bus without opening a second stream.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PyQt6.QtWidgets import QApplication

import groovebox as g

_qa = QApplication.instance() or QApplication([])


class _FakeStream:
    def __init__(self, cb, sr):
        self.callback = cb; self.samplerate = sr; self.active = False; self.closed = False

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def close(self):
        self.closed = True; self.active = False


def _run(monkeypatch):
    opened = []

    def fake_open(**kw):
        st = _FakeStream(kw["callback"], kw["samplerate"]); opened.append(st); return st

    monkeypatch.setattr(g, "HAS_SOUNDDEVICE", True)
    monkeypatch.setattr(g, "open_output_stream", fake_open)
    monkeypatch.setattr(g, "prepare_output_buffer", lambda b, sr, preferred_name="": (b, sr, None))
    app = g.MathematiciansGrooveboxApp()
    return app, opened


def _block(app, frames=1024):
    out = np.zeros((frames, 1), np.float32)
    app._audio_callback(out, frames, None, None)
    return out


def test_transport_audible_and_keys_join_it(monkeypatch):
    app, opened = _run(monkeypatch)
    tone = (0.3 * np.sin(np.linspace(0, 400 * np.pi, 48000))).astype(np.float32)
    hit = (0.5 * np.sin(np.linspace(0, 80 * np.pi, 4410))).astype(np.float32)

    app._pkp_poly_submit(hit, 44100)                      # key audition opens its own stream
    assert len(opened) == 1 and opened[0].active
    audition = opened[0]

    app._open_play_stream(tone, 48000, audio_only=True)   # transport must take over the device
    assert audition.closed, "audition stream must be closed before the transport opens"
    assert len(opened) == 2 and opened[1].active
    assert float(np.max(np.abs(_block(app)))) > 0.01, "transport is silent"

    n_before = len(opened)
    app._pkp_poly_submit(hit, 44100)                      # key during playback: no second stream
    assert len(opened) == n_before
    assert any(nm.startswith("key") for nm in app.concurrent_audio_bus.source_names())
    app.stop_playback()
