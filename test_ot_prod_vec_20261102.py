import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import time
import numpy as np
import groovebox as g


def _cases():
    rng = np.random.default_rng(7)
    a = rng.normal(size=4000) * 3.0
    b = rng.normal(size=4000) * 0.5
    specials = np.array([0.0, -0.0, 1.0, -1.0, np.inf, -np.inf, np.nan, 1e-300, -1e300, 5e-324])
    aa = np.concatenate([a, np.repeat(specials, specials.size), specials])
    bb = np.concatenate([b, np.tile(specials, specials.size), specials[::-1]])
    return aa, bb


def test_ot_prod_vec_is_bit_identical_to_the_scalar_everywhere():
    aa, bb = _cases()
    ref = np.array([g.ot_prod(float(x), float(y)) for x, y in zip(aa, bb)], dtype=np.float64)
    got = g.ot_prod_vec(aa, bb)
    assert got.shape == ref.shape
    assert np.array_equal(np.isnan(got), np.isnan(ref))
    ok = ~np.isnan(ref)
    assert np.array_equal(got[ok].view(np.int64), ref[ok].view(np.int64))       # exact bits, signs of zero included


def test_math_mul_vec_matches_math_mul_in_both_modes():
    aa, bb = _cases()
    prev = g.OP_THEORY_ENABLED
    try:
        for on in (True, False):
            g.set_operator_theory(on)
            ref = np.array([g.math_mul(float(x), float(y)) for x, y in zip(aa, bb)])
            got = g.math_mul_vec(aa, bb)
            ok = ~np.isnan(ref)
            assert np.array_equal(np.isnan(got), np.isnan(ref))
            assert np.array_equal(got[ok].view(np.int64), ref[ok].view(np.int64))
            # scalar drive, as the synth shapers use it
            ref2 = np.array([g.math_mul(float(x), 2.75) for x in aa])
            got2 = g.math_mul_vec(aa, 2.75)
            ok2 = ~np.isnan(ref2)
            assert np.array_equal(got2[ok2].view(np.int64), ref2[ok2].view(np.int64))
    finally:
        g.set_operator_theory(prev)


def test_it_is_much_faster_than_the_scalar_loop():
    rng = np.random.default_rng(1)
    a = rng.normal(size=48000); b = rng.normal(size=48000)
    g.math_mul_vec(a[:64], b[:64]); g.math_mul(1.0, 2.0)          # warm-up (first-call costs)
    loop = vec = float("inf")
    for _ in range(3):                                              # best of 3: robust on a busy machine
        t = time.perf_counter(); np.array([g.math_mul(float(x), float(y)) for x, y in zip(a, b)]); loop = min(loop, time.perf_counter() - t)
        t = time.perf_counter(); g.math_mul_vec(a, b); vec = min(vec, time.perf_counter() - t)
    assert vec * 20 < loop


def test_no_python_loop_of_math_mul_is_left_over_audio_buffers():
    src = open("groovebox.py", encoding="utf-8").read()
    assert "[math_mul(float(v), drive)" not in src
    assert "contrib[i] = math_mul(" not in src
