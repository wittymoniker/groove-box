import math
from modulation_math import (
    MEUM, normalize_signed_amounts, signed_factor, apply_signed,
    heuristic_share, synth_shift_factor, multidim_peak_target,
    stable_weighted_mix,
)


def test_signed_normalization_preserves_direction_and_budget():
    out = normalize_signed_amounts([0.4, -0.2, 0.0, -0.4], 0.5)
    assert math.isclose(sum(abs(x) for x in out), 0.5, rel_tol=1e-12)
    assert out[0] > 0 and out[1] < 0 and out[2] == 0 and out[3] < 0


def test_reverse_gain_is_symmetric_about_unity_and_bounded():
    assert signed_factor(0.25) == 1.25
    assert signed_factor(-0.25) == 0.75
    assert signed_factor(-4.0) == 0.0
    assert signed_factor(9.0) == 1.0 + MEUM
    assert apply_signed(8.0, -0.5, 0.0, 10.0) == 4.0


def test_heuristic_share_overlap_window_and_canonical_off():
    vals = [heuristic_share(0.4, k) for k in range(100)]
    assert min(vals) >= 0.2 - 1e-12
    assert max(vals) <= 0.6 + 1e-12
    assert heuristic_share(0.9, 2, canonical_active=False) == 0.5


def test_synth_shift_affects_amplitude_scale_only_and_clamps_to_one_plus_meum():
    assert synth_shift_factor(2.0, 2.0) == 1.0
    assert synth_shift_factor(0.0, 2.0) == 0.0
    assert math.isclose(synth_shift_factor(99.0, 1.0), 1.0 + MEUM)


def test_multidim_peak_relation():
    assert math.isclose(multidim_peak_target(0.75), 0.75 * MEUM)


def test_weighted_mix_does_not_amplify_by_duplicate_sources():
    assert math.isclose(stable_weighted_mix([0.2, 0.2, 0.2], [1, 1, 1]), 0.2)
    assert math.isclose(stable_weighted_mix([1.0, -1.0], [1.0, 1.0]), 0.0)
