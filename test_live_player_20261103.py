"""Live Player (GROOVEBOX_R23R_LIVE_PLAYER_20261103).

Light engine: the playlist plan follows the composition (rows, roster, steps), every hit is the
instrument's own audition voice, the stream is audible, keys join the live stream (no second
stream). Full process routine: the streamed audio is exactly the shared Play / Export mixdown.
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PyQt6.QtWidgets import QApplication

import groovebox as g
import audio_os_backend as aob
import live_player as lp

_qa = QApplication.instance() or QApplication([])


import pytest


@pytest.fixture(autouse=True)
def _close_live_windows():
    """Stop + delete every Live Player window a test opened (no Qt objects or threads left for teardown)."""
    made = []
    orig = lp.open_live_player

    def track(host):
        w = orig(host); made.append((host, w)); return w
    lp.open_live_player = track
    yield
    lp.open_live_player = orig
    for host, w in made:
        try:
            w.stop(); w.close(); w.deleteLater()
        except RuntimeError:
            pass
        host._live_player_window = None
    _qa.processEvents()


class _FakeStream:
    def __init__(self, cb, sr):
        self.callback = cb; self.samplerate = sr; self.active = False; self.closed = False

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def close(self):
        self.closed = True; self.active = False


def _app(monkeypatch):
    opened = []

    def fake_open(**kw):
        st = _FakeStream(kw["callback"], kw["samplerate"]); opened.append(st); return st

    monkeypatch.setattr(g, "HAS_SOUNDDEVICE", True)
    monkeypatch.setattr(g, "open_output_stream", fake_open)
    monkeypatch.setattr(aob, "open_output_stream", fake_open)
    monkeypatch.setattr(aob, "prepare_output_buffer", lambda b, sr, preferred_name="": (b, sr, None))
    app = g.MathematiciansGrooveboxApp()
    name = app.instrument_names_48[0]
    mem = app.instrument_sequencer_memory.setdefault(name, {})
    n = int(mem.get("pattern_length", 16) or 16)
    mem["steps"] = [i % 4 == 0 for i in range(n)]
    mem["amplitudes"] = [1.0] * n
    mem["pitches"] = [1.0] * n
    app.master_playlist_data = [{"operator": name, "operators": [name]} for _ in range(2)]
    return app, opened, name


def _pull(stream, frames=2048, blocks=40):
    out = np.zeros((frames, 1), np.float32)
    peak = 0.0
    for _ in range(blocks):
        stream.callback(out, frames, None, None)
        peak = max(peak, float(np.max(np.abs(out))))
    return peak


def test_plan_follows_composition(monkeypatch):
    app, _o, name = _app(monkeypatch)
    plan = lp.build_plan(app)
    assert len(plan["rows"]) == 2 and plan["row_dur"] > 0
    assert plan["names"] == [name]
    assert len(plan["rows"][0]) == sum(1 for s in app.instrument_sequencer_memory[name]["steps"] if s)
    t0s = [e[0] for e in plan["rows"][0]]
    assert t0s == sorted(t0s) and all(0.0 <= t < plan["row_dur"] for t in t0s)


def test_light_row_is_the_keyboard_voice(monkeypatch):
    app, _o, name = _app(monkeypatch)
    plan = lp.build_plan(app)
    t0, dur, nm, hz, amp = plan["rows"][0][0]
    buf = lp.synth_row(app, [plan["rows"][0][0]], plan["row_dur"])
    m = int(dur * lp.LIGHT_SR)
    t = np.arange(m, dtype=np.float64) / lp.LIGHT_SR
    ref = (lp.LIGHT_GAIN * amp * app._audition_voice(nm, hz, t, lp.LIGHT_SR)).astype(np.float32)
    i0 = int(t0 * lp.LIGHT_SR)
    assert np.allclose(buf[i0:i0 + m], ref, atol=1e-6)


def test_light_stream_audible_and_keys_join(monkeypatch):
    app, opened, _ = _app(monkeypatch)
    win = lp.open_live_player(app)
    win.chk_full.setChecked(False)
    win.start()
    assert len(opened) == 1 and opened[0].active
    assert _pull(opened[0]) > 1e-3, "live stream is silent"
    app._pkp_poly_submit(np.ones(4410, np.float32) * 0.1, 44100)
    assert len(opened) == 1, "a key hit must join the live stream, not open another"
    win.stop()
    assert opened[0].closed


def test_full_process_routine_streams_the_shared_mixdown(monkeypatch):
    app, opened, _ = _app(monkeypatch)
    # The full mixdown itself is covered by the render suites (and takes minutes headless);
    # this pins that the Live Player streams exactly the buffer the shared mixdown returns.
    sr = 48000
    ref = (0.4 * np.sin(np.linspace(0.0, 900.0 * np.pi, int(sr * 2.5)))).astype(np.float32)
    calls = []
    monkeypatch.setattr(app, "_get_shared_mixdown_buffer",
                        lambda max_rows=None, purpose="Render", force=False: (calls.append(purpose) or (ref, sr)))
    win = lp.open_live_player(app)
    win.chk_full.setChecked(True)
    win.chk_loop.setChecked(False)
    master = float(getattr(app, "master_volume", 0.72))
    win.start()
    t_end = time.monotonic() + 120
    while not opened and time.monotonic() < t_end:
        _qa.processEvents(); time.sleep(0.02)
    assert opened and opened[0].samplerate == sr
    got = []
    out = np.zeros((4096, 1), np.float32)
    for _ in range(int(len(ref) / 4096) + 4):
        if win.engine is None:
            break
        time.sleep(0.002)
        opened[0].callback(out, 4096, None, None)
        got.append(out[:, 0].copy())
    got = np.concatenate(got)[:len(ref)]
    mv = np.float32(max(0.0, min(1.0, master)))
    exp = np.asarray(ref, np.float32)
    exp = exp.mean(axis=1) if exp.ndim > 1 else exp
    assert calls == ["Live player"]
    assert np.allclose(got, exp[:len(got)] * mv, atol=1e-6)
    win.stop()


def test_save_to_drive_redirects_every_export_dir(monkeypatch, tmp_path):
    """GROOVEBOX_R23R_SAVE_TO_DRIVE_20261103: one choice redirects exports, batch and live takes."""
    app, _o, _n = _app(monkeypatch)
    import drive_targets as dt
    monkeypatch.setattr(dt, "removable_drives", lambda *a, **k: [{"path": str(tmp_path), "label": "STICK",
                                                                    "free": 8e9, "total": 16e9, "kind": "usb"}])
    picker = app._make_export_target_picker()
    from PyQt6.QtWidgets import QComboBox
    cmb = picker.findChild(QComboBox)
    assert cmb.count() == 2 and cmb.itemData(1) == str(tmp_path)
    cmb.setCurrentIndex(1)
    base = tmp_path / "Groovebox Exports"
    for d in (app._exports_dir(), app._audio_exports_dir(), app._video_exports_dir(), app._frame_exports_dir()):
        assert str(d).startswith(str(base)) and os.path.isdir(d)
    cmb.setCurrentIndex(0)
    assert not str(app._exports_dir()).startswith(str(base))
    app.export_target = str(tmp_path / "unplugged")                 # drive gone -> project folder again
    assert not str(app._audio_exports_dir()).startswith(str(tmp_path)) and app.export_target == ""
