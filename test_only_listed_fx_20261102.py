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


def test_default_off_effects(app, monkeypatch):
    for k in ("GROOVEBOX_CANONICAL_SIDECHAIN", "GROOVEBOX_ROW_CROSSFADE", "GROOVEBOX_MASTER_VECTOR_FX"):
        monkeypatch.delenv(k, raising=False)
    assert app.spin_canonical_convolve.value() == 0.0
    assert app._canonical_step_sidechain(3, 2, 1, 16, growth=1.0) == 0.0


def test_source_gates():
    src = open("groovebox.py", encoding="utf-8").read()
    assert 'os.environ.get("GROOVEBOX_ROW_CROSSFADE", "") == "1"' in src
    assert 'os.environ.get("GROOVEBOX_MASTER_VECTOR_FX", "") == "1"' in src
    assert "CANONICAL_CONVOLVE_DEFAULT_PCT = 0.0" in src
