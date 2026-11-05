import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import numpy as np
import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    global _QA
    _QA = QApplication.instance() or QApplication([])
    import groovebox as g
    a = g.MathematiciansGrooveboxApp()
    for nm, v in (("spin_synth_count", 2), ("spin_seq_length", 8), ("spin_playlist_length", 1), ("spin_bpm", 240)):
        getattr(a, nm).setValue(v)
    return a


@pytest.mark.parametrize("wave", ["saw", "square", "triangle", "ics"])
def test_geometric_voice_present_and_balance_matters_for_simple_waveforms(app, wave, monkeypatch):
    import groovebox as g
    calls = []
    orig = g._ws_geometric_voice
    monkeypatch.setattr(g, "_ws_geometric_voice", lambda *a, **k: (calls.append(1), orig(*a, **k))[1])
    ps = app.instrument_param_state
    for nm in app.instrument_names_48:
        ps.setdefault(nm, {})["waveform"] = wave

    def render(mix):
        for nm in app.instrument_names_48:
            ps[nm]["geo_panel_mix"] = mix
        app._voice_phase_carry = {}
        b, _ = app._render_mixdown_buffer(max_rows=1)
        return np.asarray(b, dtype=np.float64)

    lo, hi = render(0.25), render(0.75)
    assert calls, "geometric voice was skipped for waveform " + wave
    assert not np.allclose(lo, hi)
