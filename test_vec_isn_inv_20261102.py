import os, sys, math
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import groovebox as g


def _ref_arcisn(ph):
    return np.array([float(g.eqr_isn_inv(float(v) if abs(float(v)) <= 1.5 else math.copysign(1.0, float(v)))) for v in ph], np.float32)


def _ref_arcics(ph):
    out = []
    for v in ph:
        y = float(v)
        y = max(-1.0, min(1.0, y if abs(y) <= 1.0 else g.series_cos(y)))
        out.append(float(g.eqr_isn_inv(y)))
    return np.array(out, np.float32)


def test_arcisn_matches_scalar_exactly():
    ph = np.random.default_rng(5).uniform(-9, 9, 300)
    assert np.array_equal(g.meum_waveform_from_phase(ph, "arcisn"), _ref_arcisn(ph))


def test_arcics_matches_scalar_exactly():
    ph = np.random.default_rng(6).uniform(-9, 9, 300)
    assert np.array_equal(g.meum_waveform_from_phase(ph, "arcics"), _ref_arcics(ph))


def test_every_waveform_finite_and_nonsilent():
    ph = np.linspace(0, 40, 2000)
    for wf in ("isn", "ics", "saw", "square", "triangle", "arcisn", "arcics", "sine", "cos", "pulse"):
        v = np.asarray(g.meum_waveform_from_phase(ph, wf), dtype=np.float64)
        assert np.all(np.isfinite(v)) and float(np.abs(v).max()) > 0.1, wf
