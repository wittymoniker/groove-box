from pathlib import Path
import canonical_ownership as co

ROOT = Path(__file__).parent


def test_directional_defaults_match_requested_policy():
    p = co.default_policy()
    assert p["canonical"] == {"blend": True, "strength": 1.0}
    assert p["seed"] == {"blend": False, "strength": 1.0}
    assert p["user"] == {"blend": False, "strength": 1.0}


def test_gate_blend_is_weighted_vote_and_nonblend_overwrites():
    p = co.default_policy()
    assert co.resolve_step_probability(True, True, True, False, p) == 0.5
    p["canonical"]["blend"] = False
    assert co.resolve_step_probability(True, True, True, False, p) == 0.0


def test_numeric_blend_permission_belongs_to_incoming_writer():
    p = co.default_policy()
    assert co.blend_value(0.0, 1.0, "user", "canonical", p) == 0.5
    assert co.blend_value(0.0, 1.0, "canonical", "user", p) == 1.0


def test_task_pad_exposes_rules_panel_and_translucent_surfaces():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    ui = (ROOT / "multidim_ui.py").read_text(encoding="utf-8")
    assert "canonical_rules_panel" in src and "Canonical Rules" in src
    assert "background:rgba(11,20,28,188)" in src
    assert "WA_TranslucentBackground, True" in ui
    assert "background:rgba(21,23,47,174)" in ui


def test_obsolete_module_removed_from_runtime_and_tree():
    assert not (ROOT / "groovebox_newold.py").exists()
    for name in ("runtime_payload.py", "BUILD_ISO/app-overlay-v35.22zz/runtime_payload.py"):
        assert "groovebox_newold" not in (ROOT / name).read_text(encoding="utf-8")
