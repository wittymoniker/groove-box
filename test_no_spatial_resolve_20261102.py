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


def test_spatial_resolve_off_by_default_and_checkbox_unchecked(app):
    assert app.meum_spatial_resolution_enabled is False
    assert not app.chk_meum_spatial.isChecked()


def test_canonical_branch_untouched_and_silent_stays_silent(app):
    n = 2000
    t = np.arange(n) / 48000.0
    canon = (0.05 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    user = (0.9 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    out, mod, loss = app._meum_spatial_resolve_activity(canon, user, row_idx=3, seed_value=7.0)
    assert np.array_equal(out, canon)               # no smoothing, no rescale to the user's loudness
    silent, _m, _l = app._meum_spatial_resolve_activity(np.zeros(n, np.float32), user, row_idx=3, seed_value=7.0)
    assert not np.any(silent)                        # no injected sine
    app.meum_spatial_resolution_enabled = True       # even when opted in, silence stays silent
    silent2, _m, _l = app._meum_spatial_resolve_activity(np.zeros(n, np.float32), user, row_idx=3, seed_value=7.0)
    app.meum_spatial_resolution_enabled = False
    assert not np.any(silent2)


def test_dead_legacy_classes_gone():
    src = open("groovebox.py", encoding="utf-8").read()
    assert "class PlaylistWindow" not in src and "class FloatingSynthWindow" not in src
