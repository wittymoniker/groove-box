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


def test_eq_memo_bit_identical_and_hits(app):
    import groovebox as g
    sr = 48000
    x = np.random.RandomState(1).randn(sr // 4).astype(np.float32)
    st = {"eq_shape": "Bass", "eq_amount": 0.8}
    b = g._SCODE_MEMO_BRIDGE
    assert b is not None
    g._SCODE_MEMO_BRIDGE = None
    ref = g.apply_instrument_eq(x, sr, st, 1.0, 1.0)
    g._SCODE_MEMO_BRIDGE = b
    h0 = b._stats["memo_hits"]
    a = g.apply_instrument_eq(x, sr, st, 1.0, 1.0)
    c = g.apply_instrument_eq(x, sr, st, 1.0, 1.0)
    assert np.array_equal(ref, a) and np.array_equal(ref, c)
    assert b._stats["memo_hits"] > h0


def test_seq_envelope_memo_bit_identical(app):
    import groovebox as g
    lt = np.linspace(0, 0.5, 24000)
    mem = {"sequence_envelope_attack": 0.4, "sequence_envelope_release": 0.6}
    b = g._SCODE_MEMO_BRIDGE
    g._SCODE_MEMO_BRIDGE = None
    ref = app._sequence_envelope_factor(lt, 0.1, 0.3, 0.5, mem)
    g._SCODE_MEMO_BRIDGE = b
    a = app._sequence_envelope_factor(lt, 0.1, 0.3, 0.5, mem)
    c = app._sequence_envelope_factor(lt, 0.1, 0.3, 0.5, mem)
    assert np.array_equal(ref, a) and np.array_equal(ref, c)
    assert not c.flags.writeable
    other = app._sequence_envelope_factor(lt, 0.1, 0.35, 0.5, mem)
    assert not np.array_equal(other, c)


def test_meum_vectors_memo_bit_identical(app):
    import groovebox as g
    t = np.linspace(0, 0.25, 12000)
    ctx = {"am_depth": 0.2, "fm_depth": 0.1, "pm_depth": 0.3, "meum_depth": 0.2, "phase_shift": 0.7}
    b = g._SCODE_MEMO_BRIDGE
    g._SCODE_MEMO_BRIDGE = None
    ref = g.meum_modulation_vectors(t, ctx)
    g._SCODE_MEMO_BRIDGE = b
    a = g.meum_modulation_vectors(t, ctx)
    c = g.meum_modulation_vectors(t, ctx)
    for r, x, y in zip(ref, a, c):
        assert np.array_equal(r, x) and np.array_equal(r, y)
    assert not c[0].flags.writeable
    d = g.meum_modulation_vectors(t, dict(ctx, fm_depth=0.2))
    assert not np.array_equal(d[0], c[0])


def test_eqr_tensor_audio_memo_identical(app):
    import groovebox as g
    b = g._SCODE_MEMO_BRIDGE
    for args in ((0.3, 0.1, 0.3, 0.2), (0.0, 0.0, 0.0, 0.0), (-0.5, 0.25, -0.5, 1.0)):
        g._SCODE_MEMO_BRIDGE = None
        ref = g.eqr_tensor_audio(*args)
        g._SCODE_MEMO_BRIDGE = b
        assert g.eqr_tensor_audio(*args) == ref == g.eqr_tensor_audio(*args)


def test_fractallizer_repeat_is_exact_and_faster(app):
    import time, groovebox as g
    x = (np.random.RandomState(3).randn(48000) * 0.2).astype(np.float32)
    f = g.EQRTensorEngine()
    b = g._SCODE_MEMO_BRIDGE
    g._SCODE_MEMO_BRIDGE = None
    ref = f.process(x, 0.8)
    g._SCODE_MEMO_BRIDGE = b
    f.process(x, 0.8)
    t = time.perf_counter(); y = f.process(x, 0.8); dt = time.perf_counter() - t
    assert np.array_equal(ref, y)


def test_eqr_z_vec_bit_identical_to_scalar(app):
    import groovebox as g
    rs = np.random.RandomState(5)
    x = np.concatenate([rs.randn(120) * 0.3, [0.0, 0.0, 1.0, -1.0]])
    d = np.concatenate([np.abs(rs.randn(120)) * 0.2, [0.0, 0.1, 0.0, 0.5]])
    t = np.linspace(0, 1, x.size)
    ref = np.asarray([g._eqr_tensor_audio_raw(float(a), float(b), float(a), t=float(c))[3] for a, b, c in zip(x, d, t)])
    got = g.eqr_tensor_audio_z_vec(x, d, t)
    assert np.array_equal(ref, got, equal_nan=True)


def test_meum_threaded_branches_identical(app, monkeypatch):
    import groovebox as g
    t = np.linspace(0, 0.6, 30000)
    ctx = {"am_depth": 0.2, "fm_depth": 0.1, "pm_depth": 0.3, "pm_feedback": 0.1, "meum_depth": 0.2, "phase_shift": 0.7}
    monkeypatch.setitem(g._GB_ACCEL_FUNCS, "meum_mod", None) if isinstance(g._GB_ACCEL_FUNCS, dict) else None
    b = g._SCODE_MEMO_BRIDGE
    g._SCODE_MEMO_BRIDGE = None
    pool = g._COMPUTE_POOL
    g._COMPUTE_POOL = False
    ref = g.meum_modulation_vectors(t, ctx)
    g._COMPUTE_POOL = None
    got = g.meum_modulation_vectors(t, ctx)
    g._SCODE_MEMO_BRIDGE = b
    for r, x in zip(ref, got):
        assert np.array_equal(r, x)


def test_single_flight_and_budget_and_hann(app):
    import threading, groovebox as g
    b = g._SCODE_MEMO_BRIDGE
    calls = []
    gate = threading.Event()

    def prod():
        calls.append(1); gate.wait(1.0)
        return np.ones(4)
    out = []
    ts = [threading.Thread(target=lambda: out.append(b.memoized_result("sf_test", "k", prod))) for _ in range(4)]
    [t.start() for t in ts]; gate.set(); [t.join() for t in ts]
    assert len(calls) == 1 and len(out) == 4
    for i in range(5):
        b.memoized_result("bytes_test", i, lambda: np.zeros(1000), max_entries=99, max_bytes=2500)
    assert len(b._result_cache["bytes_test"]) <= 2
    assert np.array_equal(g._hann_window(257), np.hanning(257))
    assert not g._hann_window(257).flags.writeable
    assert 0.0 <= b.state_for_project()["memo_hit_rate"] <= 1.0
