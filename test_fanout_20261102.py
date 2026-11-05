import numpy as np
import audio_os_backend as a
import media_output_router as m
import multi_output as mo


class FakeStream:
    log = []
    def __init__(self, device=None, samplerate=48000, channels=1, dtype="float32", callback=None,
                 blocksize=0, latency="low", **kw):
        if device in FakeStream.refuse:
            raise RuntimeError("busy")
        self.device = device; self.cb = callback; self.active = False; self.blocksize = blocksize
        FakeStream.log.append(("open", device))
    def start(self): self.active = True
    def stop(self): self.active = False
    def close(self): self.active = False
FakeStream.refuse = set()


class FakeSD:
    OutputStream = FakeStream
    @staticmethod
    def check_output_settings(device=None, samplerate=48000, channels=1, dtype="float32"):
        if device in FakeSD.bad_format:
            raise RuntimeError("bad rate")
    bad_format = set()


ROWS = [
    {"name": "HDA Intel PCH: ALC3204 Analog (hw:0,0)", "max_output_channels": 2},
    {"name": "HDA Intel PCH: HDMI 0 (hw:0,3)", "max_output_channels": 2},
    {"name": "HDA Intel PCH: HDMI 1 (hw:0,7)", "max_output_channels": 2},
    {"name": "pipewire", "max_output_channels": 2},
    {"name": "default", "max_output_channels": 2},
]


def _setup(monkeypatch, sink=""):
    FakeStream.log.clear(); FakeStream.refuse = set(); FakeSD.bad_format = set()
    monkeypatch.setattr(a, "sd", FakeSD, raising=False)
    monkeypatch.setattr(a, "HAS_SOUNDDEVICE", True)
    monkeypatch.setattr(a, "_device_snapshot", lambda force=False: ROWS)
    monkeypatch.setattr(a, "_log_audio_failure", lambda *x, **k: None)
    monkeypatch.setattr(a, "_proven_speaker_pcm", lambda force=False, ttl=15.0: "plughw:0,0")
    monkeypatch.setattr(m, "_ensure_all_pulse_outputs_sink", lambda: sink)
    monkeypatch.setattr(m, "_prepare_physical_alsa_output", lambda d: True)
    a._ALL_ROUTE["ready"].clear(); a._ALL_ROUTE.update({"sink": "", "started": 0.0, "running": False})


def test_physical_targets_skip_virtual_and_dedupe():
    ok = lambda i: True
    assert mo.physical_targets(ROWS, ok) == [0, 1, 2]


def test_fanout_opens_every_physical_output_and_mirrors_audio(monkeypatch):
    _setup(monkeypatch)
    seen = []
    def cb(outdata, frames, t, s):
        outdata[:, 0] = np.arange(frames, dtype=np.float32)[: frames] / 100.0
        seen.append(frames)
    st = a._try_fanout_stream(samplerate=48000, channels=1, dtype="float32", callback=cb,
                              blocksize=256, latency="low", kwargs={})
    assert st is not None and sorted(st.devices) == [0, 1, 2] and st.devices[0] == 0
    st.start()
    out = np.zeros((256, 1), dtype=np.float32)
    for _ in range(3):
        st.primary.cb(out, 256, None, None)       # primary clocks the user callback
    sec = st.secondaries[0]
    o2 = np.zeros((256, 1), dtype=np.float32)
    sec.cb(o2, 256, None, None)
    assert np.allclose(o2[:, 0], np.arange(256) / 100.0)
    st.stop(); st.close()


def test_failed_or_wrong_format_device_is_skipped_not_fatal(monkeypatch):
    _setup(monkeypatch)
    FakeStream.refuse = {1}; FakeSD.bad_format = {2}
    st = a._try_fanout_stream(samplerate=48000, channels=1, dtype="float32", callback=lambda *x: None,
                              blocksize=256, latency="low", kwargs={})
    assert st is None                              # only one device usable -> normal single path
    FakeStream.refuse = {1}; FakeSD.bad_format = set()
    st = a._try_fanout_stream(samplerate=48000, channels=1, dtype="float32", callback=lambda *x: None,
                              blocksize=256, latency="low", kwargs={})
    assert st is not None and st.devices == [0, 2] and any(d == 1 for d, _m in st.skipped)


def test_not_used_when_combined_sink_exists(monkeypatch):
    _setup(monkeypatch, sink="groovebox_all_outputs")
    assert a._try_fanout_stream(samplerate=48000, channels=1, dtype="float32", callback=lambda *x: None,
                                blocksize=256, latency="low", kwargs={}) is None
    import os; os.environ.pop("PULSE_SINK", None)


def test_ring_is_bounded():
    r = mo._Ring(1, 1000)
    for _ in range(50):
        r.write(np.ones((256, 1), dtype=np.float32))
    assert r.n <= 1000


def test_combined_sink_name_as_preferred_does_not_raise(monkeypatch):
    _setup(monkeypatch)
    monkeypatch.setattr(m, "_running_on_sos", lambda: True)
    monkeypatch.setattr(a, "_prepare_sos_output_route", lambda *x, **k: None, raising=False)
    monkeypatch.setattr(a, "_first_audio_use", lambda *x, **k: None, raising=False)
    monkeypatch.setattr(a, "_hardware_volume_post_open_sync", lambda *x, **k: None, raising=False)
    monkeypatch.setenv("GROOVEBOX_OUTPUT_SINGLE", "1")      # exercise the single-device chain
    st = a.open_output_stream(samplerate=48000, channels=1, callback=lambda *x: None,
                              preferred_name="groovebox_all_outputs")
    assert st is not None


def test_single_path_falls_through_every_candidate(monkeypatch):
    _setup(monkeypatch)
    monkeypatch.setattr(m, "_running_on_sos", lambda: True)
    monkeypatch.setattr(a, "_prepare_sos_output_route", lambda *x, **k: None, raising=False)
    monkeypatch.setattr(a, "_first_audio_use", lambda *x, **k: None, raising=False)
    monkeypatch.setattr(a, "_hardware_volume_post_open_sync", lambda *x, **k: None, raising=False)
    monkeypatch.setenv("GROOVEBOX_OUTPUT_SINGLE", "1")
    FakeStream.refuse = {3, 4, 0, 1}                           # default, pipewire, analog, hdmi0 all refuse
    st = a.open_output_stream(samplerate=48000, channels=1, callback=lambda *x: None, preferred_name=None)
    assert st.device == 2                                      # last real output still works
    FakeStream.refuse = {0, 1, 2, 3, 4}
    import pytest
    with pytest.raises(RuntimeError):
        a.open_output_stream(samplerate=48000, channels=1, callback=lambda *x: None, preferred_name=None,
                             silent_fallback=False)
    a._OPEN_FAIL_UNTIL = 0.0


def test_busy_output_joins_live_when_it_frees_up(monkeypatch):
    _setup(monkeypatch)
    FakeStream.refuse = {1}
    st = a._try_fanout_stream(samplerate=48000, channels=1, dtype="float32", callback=lambda *x: None,
                              blocksize=256, latency="low", kwargs={})
    assert st.devices == [0, 2]
    st.start()
    st._dead.clear()
    FakeStream.refuse = set()                       # the HDMI output is free now
    st.refresh_outputs()
    assert sorted(st.devices) == [0, 1, 2] and len(st.secondaries) == len(st.rings) == 2
    st.stop(); st.close()


def test_stopped_secondary_restarts_and_unrestartable_one_is_dropped(monkeypatch):
    _setup(monkeypatch)
    st = a._try_fanout_stream(samplerate=48000, channels=1, dtype="float32", callback=lambda *x: None,
                              blocksize=256, latency="low", kwargs={})
    st.start()
    s1, s2 = st.secondaries
    s1.active = False                               # device hiccup: restart works
    st.refresh_outputs()
    assert s1.active is True and len(st.secondaries) == 2
    s2.active = False
    def boom(): raise RuntimeError("unplugged")
    s2.start = boom
    st.refresh_outputs()
    assert s2 not in st.secondaries and len(st.rings) == 1
    st._dead.clear()
    st.stop(); st.close()


def test_joining_output_triggers_volume_sync(monkeypatch):
    _setup(monkeypatch)
    FakeStream.refuse = {1}
    calls = []
    st = mo.FanOutStream(FakeSD, lambda *x: None, device_ids=[0, 2], samplerate=48000, channels=1, dtype="float32",
                         blocksize=256, latency="low", extra={}, rescan=lambda: [0, 1, 2], on_join=lambda: calls.append(1))
    st.start(); FakeStream.refuse = set(); st._dead.clear()
    st.refresh_outputs()
    assert calls == [1] and 1 in st.devices
    st.stop(); st.close()
