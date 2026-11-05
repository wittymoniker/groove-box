import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    global _QA
    _QA = QApplication.instance() or QApplication([])
    import groovebox as g
    return g.MathematiciansGrooveboxApp()


def test_fresh_default_is_zero(app):
    app.sidechain_state = {}
    assert app._canonical_sidechain_amount_for("x") == 0.0


def test_old_saved_default_migrates_to_zero(app):
    snap = app._project_snapshot()
    snap["sidechain_state"] = {"schema": 1, "default_amount": 0.1975807343,
                               "global": {"enabled": True, "amount": 0.1975807343, "source": "master"},
                               "targets": {}, "inherit_global": True}
    app._apply_project_snapshot(snap)
    assert app.sidechain_state["global"]["amount"] == 0.0
    assert app._canonical_sidechain_amount_for("x") == 0.0


def test_user_value_is_kept(app):
    snap = app._project_snapshot()
    snap["sidechain_state"] = {"schema": 1, "default_amount": 0.0,
                               "global": {"enabled": True, "amount": 0.3, "source": "master"},
                               "targets": {}, "inherit_global": True}
    app._apply_project_snapshot(snap)
    assert abs(app._canonical_sidechain_amount_for("x") - 0.3) < 1e-9
