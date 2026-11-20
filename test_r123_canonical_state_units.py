"""R123: canonical panel projection must blend instrument state in STATE units.

Bug: apply_registry_to_state multiplied every percent-scaled key already in state by 100
(geo_panel_mix 0.25 -> 25 -> clamped to 0.75), so the Panel/Geometric balance had no effect.
"""
import canonical_panel_bridge as c


def test_untargeted_keys_unchanged():
    st = {"geo_panel_mix": 0.25, "eqr": 0.3, "master_vol": 0.8}
    assert c.apply_registry_to_state(st, {}, 1.0) == st


def test_user_balance_wins_over_neutral_default():
    for v in (0.25, 0.4, 0.75):
        assert c.apply_registry_to_state({"geo_panel_mix": v}, {"geo_panel_mix": 0.5}, 1.0)["geo_panel_mix"] == v
    assert c.apply_registry_to_state({}, {"geo_panel_mix": 0.5}, 1.0)["geo_panel_mix"] == 0.5


def test_scaled_keys_blend_in_state_units_and_accept_widget_units():
    assert abs(c.apply_registry_to_state({"master_vol": 0.2}, {"master_vol": 0.6}, 0.5)["master_vol"] - 0.4) < 1e-9
    assert abs(c.apply_registry_to_state({"master_vol": 0.2}, {"master_vol": 60.0}, 1.0)["master_vol"] - 0.6) < 1e-9
    assert c.apply_registry_to_state({"master_vol": 0.2}, {"master_vol": 5.0}, 1.0)["master_vol"] <= 1.0


def test_self_test_ok():
    r = c.self_test()
    assert r["ok"], r["errors"]
