"""GOAVA_LEVEL_GAIN_20261102: the GOAVA bridge level defaults to 33% and is a linear gain (100% = its max), not a switch."""
from pathlib import Path
SRC = (Path(__file__).resolve().parent / "groovebox.py").read_text(encoding="utf-8")


def test_default_level_is_33_percent():
    assert '"goava": 1.0 / 3.0' in SRC
    assert '("goava","GOAVA",33)' in SRC


def test_level_is_linear_gain_with_unity_at_default_and_no_limiter():
    seg = SRC.split("GOAVA_LEVEL_GAIN_20261102: the GOAVA level")[1].split("canonical_bus[mask] += _goava")[0]
    assert 'self._canonical_level("goava")' in seg
    body = seg.split("No limiter, no saturation.")[1]
    for banned in ("tanh", "clip", "limit"):
        assert banned not in body
    assert "goava_bus" not in SRC          # no ensemble-peak matching
