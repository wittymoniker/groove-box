"""R28.4.50 HF1 regression tests for bounded deterministic Fractal Seed mode."""
from __future__ import annotations
from groovebox_v3.fractal_seed_engine import (
    DEFAULT_FRACTAL_SEED_MODE,
    evaluate_seed,
    migrate_project,
    project_seed_config,
    rasterize_sequence,
)


def test_seed_plan_is_deterministic_and_bounded():
    config = project_seed_config("R28-HF1 seed: alpha / beta", tempo=123, depth=6)
    one = evaluate_seed(config)
    two = evaluate_seed(config)
    assert one["seed"]["identity"] == two["seed"]["identity"]
    assert one["event_plan_sha256"] == two["event_plan_sha256"]
    assert one["events"] == two["events"]
    assert one["evaluation"]["symbols_evaluated"] <= one["evaluation"]["symbol_budget"]
    assert one["evaluation"]["truncated"] is False
    assert one["seed"]["depth_completed"] <= config["depth"]


def test_rasterized_sequence_has_certain_gates_and_bounded_arrays():
    plan = evaluate_seed(project_seed_config("raster test", tempo=110, depth=5))
    raster = rasterize_sequence(plan, 32)
    for key in ("steps", "pitches", "amplitudes", "gates", "probabilities", "offsets"):
        assert len(raster[key]) == 32
    assert all(isinstance(v, bool) for v in raster["gates"])
    assert raster["gates"] == [True] * 32
    assert raster["probabilities"] == [100] * 32
    assert all(0.0 <= float(v) <= 1.0 for v in raster["amplitudes"])
    assert all(1.0 / 32.0 <= float(v) <= 32.0 for v in raster["pitches"])


def test_preview_scenarios_require_mode_and_canonical_controls():
    base = project_seed_config("scenario test", tempo=110, depth=4)
    base["scenario"] = "omit_every_third"
    base["canonical_controls"] = False
    blocked = evaluate_seed(base)
    assert blocked["interpretation"]["scenario_applied"] == "none"

    enabled = dict(base, canonical_controls=True)
    allowed = evaluate_seed(enabled)
    assert allowed["interpretation"]["scenario_applied"] == "omit_every_third"
    assert len(allowed["events"]) <= len(blocked["events"])

    off = dict(enabled, mode_enabled=False)
    paused = evaluate_seed(off)
    assert paused["interpretation"]["scenario_applied"] == "none"
    assert paused["events"] == []


def test_project_migration_defaults_on_but_preserves_explicit_off():
    assert DEFAULT_FRACTAL_SEED_MODE is True
    old = {"project_title": "legacy"}
    migrated_old = migrate_project(old)
    assert migrated_old["composition"]["fractalSeedMode"]["enabled"] is True
    assert old == {"project_title": "legacy"}  # migration is non-mutating
    explicit_off = {"composition": {"fractalSeedMode": {"enabled": False, "level": 0.2}}}
    migrated_off = migrate_project(explicit_off)
    assert migrated_off["composition"]["fractalSeedMode"]["enabled"] is False
    assert migrated_off["composition"]["fractalSeedMode"]["level"] == 0.2
