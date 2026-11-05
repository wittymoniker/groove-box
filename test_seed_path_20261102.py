import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import groovebox as g


def test_deterministic_and_known_values():
    a = g.seed_child64(7, "synth", 3, "wavetable")
    assert a == g.seed_child64(7, "synth", 3, "wavetable") == g.seed_child64(7.0, "synth", 3, "wavetable")
    assert 0 < g.seed_child(7, "x") <= 0x7FFFFFFF


def test_labels_and_order_matter_and_streams_are_unrelated():
    base = g.seed_child64(42)
    outs = {g.seed_child64(42, "a"), g.seed_child64(42, "b"), g.seed_child64(42, "a", "b"), g.seed_child64(42, "b", "a"),
            g.seed_child64(42, 1), g.seed_child64(42, "1"), g.seed_child64(43, "a"), base}
    assert len(outs) == 8
    x = g.seed_rng(5, "synth", 0).random(4000); y = g.seed_rng(5, "synth", 1).random(4000)
    assert abs(float(np.corrcoef(x, y)[0, 1])) < 0.06


def test_avalanche_and_spread():
    ks = [g.seed_child64(1, "k", i) for i in range(2048)]
    assert len(set(ks)) == 2048
    flips = [bin(ks[i] ^ ks[i + 1]).count("1") for i in range(2047)]
    assert 28 < sum(flips) / len(flips) < 36                 # ~32 of 64 bits flip between neighbouring labels
    top = [k >> 60 for k in ks]
    assert min(np.bincount(top, minlength=16)) > 80           # no hole in the output range


def test_app_method_uses_project_seed():
    from PyQt6.QtWidgets import QApplication
    _qa = QApplication.instance() or QApplication([])
    app = g.MathematiciansGrooveboxApp()
    assert app.seed_child("synth", 2) == g.seed_child(app.get_numeric_seed(), "synth", 2)
