import json
from fractal_spatial_engine import FractalSpatialEngine, build_spatial_state


def test_same_seed_same_state():
    assert build_spatial_state(12345, "abc", depth=4, roots=7) == build_spatial_state(12345, "abc", depth=4, roots=7)


def test_seed_divergence():
    a = build_spatial_state(12345, "abc", depth=3, roots=5)
    b = build_spatial_state(12346, "abc", depth=3, roots=5)
    assert a["fingerprint"] != b["fingerprint"]


def test_native_four_engine_sculpting_frame():
    e = FractalSpatialEngine(42, "fp", goava=False)
    s = e.snapshot(depth=3, roots=6)
    assert s["core_engines"] == ["randomizer", "phase_lock", "euclidean", "seeded"]
    assert s["goava_required"] is False
    assert s["channels"] == ["position", "phase", "scale", "topology", "complexity"]


def test_goava_is_optional_adapter_not_generator():
    native = FractalSpatialEngine(42, "fp", goava=False)
    adapted = FractalSpatialEngine(42, "fp", goava=True)
    a = native.generate(3, 6)
    b = adapted.generate(3, 6)
    assert [p.to_dict() for p in a] == [p.to_dict() for p in b]
    assert adapted.apply_goava_adapter(a) != a
    assert native.apply_goava_adapter(a) == a


def test_topology_is_goava_independent():
    a = FractalSpatialEngine(99, "fp", goava=False).snapshot(3, 5)
    b = FractalSpatialEngine(99, "fp", goava=True).snapshot(3, 5)
    assert a["edges"] == b["edges"]


def test_order_independent_window():
    e = FractalSpatialEngine(99, "fp")
    p = e.generate(2, 4)
    assert sorted(e.topology_edges(p)) == sorted(e.topology_edges(list(reversed(p))))


def test_json_serializable():
    json.dumps(build_spatial_state("seed-text", "fp", depth=2, roots=3), sort_keys=True)
