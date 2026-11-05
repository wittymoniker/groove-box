import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import time
import numpy as np
import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    global _QA
    _QA = QApplication.instance() or QApplication([])
    import groovebox as g
    return g.MathematiciansGrooveboxApp()


def _capture(app, monkeypatch):
    import groovebox as g
    calls, subs = [], []
    orig = g._ws_geometric_voice
    monkeypatch.setattr(g, "_ws_geometric_voice", lambda *a, **k: (calls.append(1), orig(*a, **k))[1])
    monkeypatch.setattr(g, "HAS_SOUNDDEVICE", True)
    monkeypatch.setattr(app, "_pkp_poly_submit", lambda buf, sr: subs.append(np.asarray(buf, dtype=np.float64)))
    return calls, subs


def test_trigger_note_key_and_trigger_all_all_use_geometrics(app, monkeypatch):
    calls, subs = _capture(app, monkeypatch)
    name = app.instrument_names_48[0]
    app.trigger_selected_note()
    n1 = len(calls); assert n1 >= 1 and subs
    app._keyboard_note_hit(3)
    n2 = len(calls); assert n2 > n1
    t = time.perf_counter(); app.trigger_all_instruments_hit(); dt = time.perf_counter() - t
    assert len(calls) > n2
    assert dt < 8.0, dt


def test_balance_slider_changes_what_a_key_hit_plays(app, monkeypatch):
    calls, subs = _capture(app, monkeypatch)
    name = app.instrument_names_48[0]
    ps = app.instrument_param_state.setdefault(name, {})
    out = {}
    for mix in (0.25, 0.75):
        ps["geo_panel_mix"] = mix
        subs.clear()
        app._pkp_fire_step_hit(name, 0, 1.0, pitch_ratio=1.0, hit_seconds=0.2)
        out[mix] = subs[-1].copy()
    assert not np.allclose(out[0.25], out[0.75])


def test_geometric_algo_changes_the_audition_voice(app):
    name = app.instrument_names_48[0]
    t = np.arange(8820) / 44100.0
    gas = app.global_algo_state
    gas["apply_enabled"] = False
    base = app._audition_voice(name, 220.0, t, 44100)
    gas["apply_enabled"] = True
    gas["geometric"] = "def global_script(t, name, i):\n    return {'scalar': 2.0}\n"
    gas["params"].update({"enable_geometric": True, "geometric_amount": 1.0})
    app.instrument_param_state.setdefault(name, {})["geo_panel_mix"] = 0.75
    with_algo = app._audition_voice(name, 220.0, t, 44100)
    gas["apply_enabled"] = False
    assert not np.allclose(base, with_algo)
