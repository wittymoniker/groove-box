import json
from pathlib import Path

import pytest

import groovebox_intelligence as gi
import project_schema


def test_registry_arbitration_is_stable_and_canonical_wins():
    reg = gi.ParameterRegistry()
    reg.register("cutoff", owner="synth", destinations=("audio", "video"))
    reg.add_route("cutoff", "step")
    reg.add_route("cutoff", "canonical")
    a = reg.resolve("cutoff", [
        {"source": "step", "value": 0.2},
        {"source": "canonical", "value": 0.8},
    ])
    b = reg.resolve("cutoff", list(reversed([
        {"source": "step", "value": 0.2},
        {"source": "canonical", "value": 0.8},
    ])))
    assert a["winner"] == b["winner"]
    assert a["winner"]["source"] == "canonical"
    assert a["conflicts"]


def test_registry_manifest_roundtrip_and_coverage():
    reg = gi.ParameterRegistry()
    reg.register("fx.mix", owner="fx", destinations=("audio", "composition"))
    assert gi.ParameterRegistry.from_manifest(reg.manifest()).manifest() == reg.manifest()
    report = gi.audit_parameter_coverage(reg)
    assert report["incomplete"] == 1
    assert report["rows"][0]["missing"] == ["game", "video"]


def test_deterministic_variation_preserves_structure_and_is_repeatable():
    pattern = {"events": [{"pitch": 60, "position": 0, "duration": 1, "velocity": .5},
                          {"pitch": 64, "position": 2, "duration": 1, "velocity": .7}]}
    a = gi.deterministic_variation(pattern, "seed-1", .4)
    b = gi.deterministic_variation(pattern, "seed-1", .4)
    assert a == b
    assert len(a["events"]) == len(pattern["events"])
    for old, new in zip(pattern["events"], a["events"]):
        for k in ("pitch", "position", "duration"):
            assert old[k] == new[k]


def test_clock_and_motif_discovery():
    clock = gi.CrossMediaClock()
    for frame in (0, 1, 100, 10000):
        ticks = clock.frame_to_ticks(frame, 30000, 1001)
        assert clock.ticks_to_frame(ticks, 30000, 1001) == frame
    motifs = gi.discover_motifs([0, 2, 5, 7, 10, 12])
    assert motifs and motifs[0]["repeats"] >= 2


def test_canonical_conformance_is_read_only():
    canonical = {"a": 1.0, "b": "x"}
    live = {"a": 1.1, "b": "x"}
    before = json.dumps(live, sort_keys=True)
    result = gi.canonical_conformance(canonical, live)
    assert not result["conformant"] and result["read_only"]
    assert json.dumps(live, sort_keys=True) == before


def test_project_schema_r105_migration_and_scene_state():
    sec = project_schema.migrate({"schema": 3})
    assert sec["schema"] == 4
    assert sec["performance_scenes"] == {}
    class App: pass
    app = App()
    app.groovebox_performance_scenes = {"A": {"fingerprint": "abc"}}
    snap = project_schema.snapshot(app)
    assert snap["performance_scenes"]["A"]["fingerprint"] == "abc"
    restored = App()
    project_schema.apply(restored, snap)
    assert restored.groovebox_performance_scenes == app.groovebox_performance_scenes


def test_app_registry_is_persistable():
    class App: pass
    app = App()
    reg = gi.registry_for_app(app)
    reg.register("osc.frequency", owner="synth", destinations=("audio", "composition"))
    gi.save_registry(app, reg)
    assert gi.registry_for_app(app).manifest() == reg.manifest()


def test_adaptive_worker_budget_obeys_cpu_and_ram():
    assert gi.adaptive_worker_budget(cpu_count=8, available_memory_bytes=3 * 1024**3) == 2
    assert gi.adaptive_worker_budget(cpu_count=2, available_memory_bytes=100 * 1024**3) == 1


def test_self_test_reports_registry_and_integrity():
    reg = gi.ParameterRegistry()
    reg.register("p", destinations=("audio", "video", "game", "composition"))
    result = gi.run_self_test({"r32": {}}, reg)
    assert result["ok"]
    assert result["checks"]["parameter_coverage"]["complete"] == 1


def test_performance_scene_capture_and_recall_uses_project_schema():
    class App: pass
    app = App()
    app.groovebox_parameter_registry = {"schema": 1, "parameters": [], "routes": {}}
    app.groovebox_intelligence_settings = {"schema": 1, "mode": "test"}
    gi.PerformanceScenes.capture(app, "Verse", {"tag": "baseline"})
    app.groovebox_intelligence_settings["mode"] = "changed"
    gi.PerformanceScenes.recall(app, "Verse")
    assert app.groovebox_intelligence_settings["mode"] == "test"
    assert gi.PerformanceScenes.list(app)[0]["name"] == "Verse"
