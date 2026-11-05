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
    return g.MathematiciansGrooveboxApp()


def _events(a):
    ev = [{"enabled": True, "weight": 1.0, "chord_freqs": [220.0, 330.0, 440.0], "chord_amps": [0.33, 0.2, 0.1]}]
    a.goava_note_events = ev
    a._build_goava_composition = lambda **k: list(ev)


def test_spinbox_drives_attribute_and_enabled_with_goava(app):
    sg = app.slider_goava_ensemble
    app.btn_goava.setChecked(False)
    assert not sg.isEnabled()
    app.btn_goava.setChecked(True)
    assert sg.isEnabled()
    sg.setValue(0.6)
    assert abs(app.goava_ensemble_mod - 0.6) < 1e-9
    app.btn_goava.setChecked(False)


def test_no_ensemble_modulation_when_goava_off_and_separate_from_level(app):
    _events(app)
    lt = np.arange(0, 4800, dtype=np.float64) / 48000.0
    app.goava_active = False
    app.goava_ensemble_mod = 0.9
    # GOAVA off: nothing at all comes out of GOAVA, so no ensemble modulation either
    off = app._goava_mix(lt, 0, 0.25, row_start_beat=0.0)
    assert not np.any(off)
    app.goava_active = True
    app.goava_ensemble_mod = 0.0
    zero = app._goava_mix(lt, 0, 0.25, row_start_beat=0.0)
    assert np.any(zero)
    # GOAVA on: the amount changes the sound, the level slider does not alter it (level is applied later in render)
    app.goava_ensemble_mod = 0.5
    modded = app._goava_mix(lt, 0, 0.25, row_start_beat=0.0)
    assert not np.allclose(modded, zero)
    lvl = app.canonical_engine_levels["goava"]
    app.canonical_engine_levels["goava"] = 1.0
    same = app._goava_mix(lt, 0, 0.25, row_start_beat=0.0)
    app.canonical_engine_levels["goava"] = lvl
    assert np.allclose(modded, same)
    app.goava_active = False


def test_saved_and_restored(app):
    app.goava_ensemble_mod = 0.42
    state = app._collect_project_ui_state()
    assert abs(state["goava_ensemble_mod"] - 0.42) < 1e-9
    app.goava_ensemble_mod = 0.1
    app._restore_project_ui_state(state)
    assert abs(app.goava_ensemble_mod - 0.42) < 1e-9
    assert abs(app.slider_goava_ensemble.value() - 0.42) < 1e-9


def test_goava_frequencies_never_pulled_by_blend(app):
    _events(app)
    app.goava_active = True
    sr = 48000
    lt = np.arange(0, sr // 2, dtype=np.float64) / sr
    for depth in (0.0, 0.2, 0.5, 1.0):
        app.goava_ensemble_mod = depth
        y = np.asarray(app._goava_mix(lt, 0, 0.5, row_start_beat=0.0), dtype=np.float64)
        if not np.any(y):
            continue            # seeded gate closed this event
        spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
        peak = spec.max()
        for f0 in (220.0, 440.0):        # the outer chord tones would vanish if pulled to the 330 Hz mean
            band = spec[(freqs > f0 - 30) & (freqs < f0 + 30)].max()
            assert band > 0.02 * peak, (depth, f0)
    app.goava_active = False
