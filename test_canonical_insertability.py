"""Contract examples for the deterministic PROB responsiveness measurement.

These tests are updated for the 0..2 response coefficient contract. They are
included as source only; they are not executed as part of this rollout handoff.
"""
import math
from canonical_insertability import measure


def test_native_response_is_unity_at_full_insertability():
    result = measure(1, 1, 1, 1)
    assert result["prob_response"] == 1.0
    assert result["response_amplitude"] == 1.0
    assert result["contract"] == "prob-0..2-linear-responsiveness-v2"


def test_response_coefficient_has_full_zero_to_two_range():
    assert measure(1, 1, 0, 1)["response_amplitude"] == 0.0
    assert measure(1, 1, 1, 1)["response_amplitude"] == 1.0
    assert measure(1, 1, 2, 1)["response_amplitude"] == 2.0


def test_situational_fit_attenuates_without_changing_response_semantics():
    result = measure(1, 1, 2, 0.4)
    assert abs(result["situational_factor"] - 0.4) < 1e-12
    assert abs(result["response_amplitude"] - 0.8) < 1e-12
    assert "event_allowed" not in result


def test_legacy_keyword_keeps_the_same_zero_to_two_response_scale():
    result = measure(1, 1, situational_insertability=1, prob_sensitivity=1.75)
    assert result["response_amplitude"] == 1.75


def test_invalid_values_remain_finite_and_bounded():
    result = measure(float("nan"), float("inf"), float("nan"), float("inf"))
    assert all(math.isfinite(result[key]) for key in ("response_amplitude", "situational_factor"))
    assert 0.0 <= result["response_amplitude"] <= 2.0
