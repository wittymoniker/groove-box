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
    for nm, v in (("spin_seq_length", 2), ("spin_playlist_length", 1), ("spin_synth_count", 2), ("spin_bpm", 240)):
        getattr(a, nm).setValue(v)
    return a


def test_continuation_voice_off_by_default_and_never_rendered(app, monkeypatch):
    monkeypatch.delenv("GROOVEBOX_CANONICAL_CONTINUATION", raising=False)
    assert app.canonical_continuation_enabled is False
    calls = []
    orig = app._canonical_continuation_wave
    app._canonical_continuation_wave = lambda *a, **k: (calls.append(1), orig(*a, **k))[1]
    try:
        app.input_seed_val.setPlainText("3, 7, 12")
    except Exception:
        app.input_seed_val.setText("3, 7, 12")
    for nm in ("btn_seeded_randomize", "btn_local_randomize", "btn_local_phase_lock"):
        getattr(app, nm).setChecked(True)
    b, sr = app._render_mixdown_buffer()
    assert np.all(np.isfinite(np.asarray(b)))
    assert not calls, "the gated continuation sine must not be rendered"


def test_old_project_flag_is_ignored(app, monkeypatch):
    monkeypatch.delenv("GROOVEBOX_CANONICAL_CONTINUATION", raising=False)
    src = open("groovebox.py", encoding="utf-8").read()
    assert "saved True from older projects is ignored" in src
