import audio_os_backend as a, media_output_router as m

ROWS = [
    {"name": "HDA Intel PCH: HDMI 0 (hw:0,3)", "max_output_channels": 2},
    {"name": "HDA Intel PCH: ALC3204 Analog (hw:0,0)", "max_output_channels": 2},
    {"name": "HDA Intel PCH: ALC3204 Alt Analog (hw:0,2)", "max_output_channels": 2},
    {"name": "pipewire", "max_output_channels": 2},
]
ROWS_WITH_DEFAULT = ROWS + [{"name": "default", "max_output_channels": 2}]

def _setup(monkeypatch, pcm):
    monkeypatch.setattr(a, "_device_snapshot", lambda force=False: ROWS)
    monkeypatch.setattr(m, "_running_on_sos", lambda: True)
    monkeypatch.setattr(m, "_preferred_alsa_output_device", lambda: pcm)
    a._PROVEN_PCM_CACHE.update({"t": 0.0, "v": ""})
    monkeypatch.setattr(m, "_ensure_all_pulse_outputs_sink", lambda: "")
    monkeypatch.setattr(m, "_prepare_physical_alsa_output", lambda d: True)
    a._ALL_ROUTE["ready"].clear(); a._ALL_ROUTE.update({"sink": "", "started": 0.0, "running": False})

def test_proven_speaker_wins_on_sos(monkeypatch):
    _setup(monkeypatch, "plughw:0,2")
    assert a.resolve_output_device_index(None, force=True) == 2

def test_falls_back_to_scoring_when_no_match(monkeypatch):
    _setup(monkeypatch, "plughw:9,9")
    assert a.resolve_output_device_index(None, force=True) in (1, 2)

def test_not_applied_off_sos(monkeypatch):
    _setup(monkeypatch, "plughw:0,2")
    monkeypatch.setattr(m, "_running_on_sos", lambda: False)
    monkeypatch.setattr(a, "sd", type("S", (), {"default": type("D", (), {"device": (0, 3)})()})(), raising=False)
    assert a.resolve_output_device_index(None, force=True) == 3


def test_all_outputs_route_preferred_when_combined_sink_exists(monkeypatch):
    _setup(monkeypatch, "plughw:0,2")
    monkeypatch.setattr(m, "_ensure_all_pulse_outputs_sink", lambda: "groovebox_all_outputs")
    monkeypatch.setattr(m, "_prepare_physical_alsa_output", lambda d: True)
    a._ALL_ROUTE["ready"].clear(); a._ALL_ROUTE.update({"sink": "", "started": 0.0, "running": False})
    monkeypatch.delenv("PULSE_SINK", raising=False)
    idx = a.resolve_output_device_index("Some specific speaker", force=True)
    assert ROWS[idx]["name"] == "pipewire"          # no 'default' row here -> pipewire; explicit choice does not override
    import os
    assert os.environ.get("PULSE_SINK") == "groovebox_all_outputs"
    os.environ.pop("PULSE_SINK", None)

def test_no_combined_sink_falls_back_to_proven_speaker(monkeypatch):
    _setup(monkeypatch, "plughw:0,2")
    monkeypatch.setattr(m, "_ensure_all_pulse_outputs_sink", lambda: "")
    monkeypatch.setattr(m, "_prepare_physical_alsa_output", lambda d: True)
    a._ALL_ROUTE["ready"].clear(); a._ALL_ROUTE.update({"sink": "", "started": 0.0, "running": False})
    assert a.resolve_output_device_index(None, force=True) == 2


def test_default_row_wins_over_direct_hw_on_sos(monkeypatch):
    _setup(monkeypatch, "plughw:0,2")
    monkeypatch.setattr(a, "_device_snapshot", lambda force=False: ROWS_WITH_DEFAULT)
    assert ROWS_WITH_DEFAULT[a.resolve_output_device_index(None, force=True)]["name"] == "default"
    assert ROWS_WITH_DEFAULT[a.resolve_output_device_index("groovebox_all_outputs", force=True)]["name"] == "default"

def test_combined_route_prefers_default_row(monkeypatch):
    _setup(monkeypatch, "plughw:0,2")
    monkeypatch.setattr(a, "_device_snapshot", lambda force=False: ROWS_WITH_DEFAULT)
    monkeypatch.setattr(m, "_ensure_all_pulse_outputs_sink", lambda: "groovebox_all_outputs")
    a._ALL_ROUTE["ready"].clear(); a._ALL_ROUTE.update({"sink": "", "started": 0.0, "running": False})
    import os
    assert ROWS_WITH_DEFAULT[a.resolve_output_device_index(None, force=True)]["name"] == "default"
    os.environ.pop("PULSE_SINK", None)
