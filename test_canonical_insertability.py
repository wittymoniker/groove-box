import math
from canonical_insertability import measure


def test_default_111_has_no_attenuation_when_insertability_is_full():
    r = measure(1, 1, 1, 1)
    assert r["balanced_sensitivity"] == 1.0
    assert r["amplitude_multiplier"] == 1.0
    assert r["contract"] == "rand:goava:prob=1:1:1; deterministic-amplitude-v1"


def test_prob_is_sensitivity_not_switching_probability():
    # The result is always a positive amplitude multiplier; no event decision is returned.
    for prob in (0.0, 0.1, 0.5, 1.0):
        r = measure(1.0, 1.0, prob, 0.0)
        assert 0.25 <= r["amplitude_multiplier"] <= 1.0
        assert "event_allowed" not in r
        assert math.isfinite(r["amplitude_multiplier"])


def test_equal_111_weights_and_situational_attenuation():
    r = measure(1, 1, 1, 0.4)
    assert r["balanced_sensitivity"] == 1.0
    assert abs(r["amplitude_multiplier"] - 0.4) < 1e-12
    r2 = measure(0.5, 1.0, 0.0, 0.4)
    assert abs(r2["balanced_sensitivity"] - 0.5) < 1e-12
    assert abs(r2["amplitude_multiplier"] - 0.7) < 1e-12


def test_invalid_values_are_finite_and_bounded():
    r = measure(float("nan"), float("inf"), -3, 8)
    assert all(math.isfinite(r[k]) for k in ("balanced_sensitivity", "amplitude_multiplier"))
    assert 0.0 <= r["balanced_sensitivity"] <= 1.0
    assert 0.25 <= r["amplitude_multiplier"] <= 1.0


def test_sequencer_uses_prob_as_amplitude_sensitivity_not_event_gate():
    # GROOVEBOX_R23R_STOCHASTIC_POINT_DECISION_20261031: the old
    # `_insertability["amplitude_multiplier"]` / "PROB is insertability
    # sensitivity" contract was replaced by _stochastic_point_decision with
    # explicit modes (half-random / true random / PROB / GOAVA / combined).
    # User-authored hits remain inviolable; only canonical-only events use the
    # stochastic decision.
    from pathlib import Path
    source = Path(__file__).with_name("groovebox.py").read_text(encoding="utf-8")
    assert "_event_allowed = _user_step_hit or (" in source
    assert "_step_threshold < _step_prob" not in source
    assert "_canonical_only_event and self._stochastic_point_decision(row_idx, s_idx, op_idx, _step_prob)" in source
    assert "def _stochastic_point_decision(self, row_idx, step_idx, op_idx, prob):" in source
    assert 'mode == "PROB"' in source
    assert 'mode == "GOAVA"' in source
