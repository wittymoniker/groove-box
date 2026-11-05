from universal_field import (
    canonical_field, concentric_sample, concentric_medium_projection,
    correspondence_manifest, correspondence_verify,
)


def _field():
    return canonical_field(42, "project-fingerprint", [0, 1, 2, 3], [0.2, 0.7, 0.4])


def test_concentric_sample_is_deterministic_and_nested():
    f = _field()
    a = concentric_sample(f, level=3, index=7, count=32)
    b = concentric_sample(f, level=3, index=7, count=32)
    assert a == b
    assert a["schema"] == "direct-concentric-v1"
    assert abs((a["x"] ** 2 + a["y"] ** 2) ** 0.5 - a["radius"]) < 1e-12
    assert concentric_sample(f, 4, 7, 32)["radius"] == a["radius"] / 2


def test_medium_adapters_share_field_and_shaping_identity():
    f = _field()
    adapters = [concentric_medium_projection(f, m) for m in ("audio", "video", "game")]
    assert {x["field_id"] for x in adapters} == {f["field_id"]}
    assert len({x["shaping_id"] for x in adapters}) == 1
    assert len({x["adapter_id"] for x in adapters}) == 3
    assert all(x["identity_source"] == "canonical_field" for x in adapters)


def test_correspondence_manifest_carries_one_shared_concentric_rule():
    f = _field()
    manifest = correspondence_manifest(f, {"event_id": "evt-1"})
    assert manifest["shaping_schema"] == "direct-concentric-v1"
    assert manifest["identity_correspondence"] is True
    assert {d["shaping_id"] for d in manifest["domains"].values()} == {manifest["shaping_id"]}
    assert correspondence_verify(f, manifest)["pass"] is True
