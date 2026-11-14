"""Static contract checks for R55.5; intentionally not run in this handoff."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_quality_profiles_are_preview_only_and_bounded():
    from scenograph_quality import profile
    assert profile("Fine")["scale"] == 1.0
    assert profile("Balanced")["fps"] == 24
    assert profile("Draft")["scale"] < profile("Balanced")["scale"]
    assert 12 <= profile("Auto", 200, 4.0)["fps"] <= 30
    assert 0.60 <= profile("Auto", 24, 0.1)["scale"] <= 1.0

def test_latest_frame_tap_is_bounded_and_immutable():
    import numpy as np
    from scenograph_stream import LatestFrameTap
    tap = LatestFrameTap()
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    assert tap.publish(frame)
    assert tap.publish(frame + 1)
    seq, _when, latest = tap.latest()
    assert seq == 2
    assert not latest.flags.writeable
    assert tap.stats()["replaced_frames"] == 1
