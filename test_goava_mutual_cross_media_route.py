"""Regression tests for deterministic GOAVA mutual modulation and media routing."""
from pathlib import Path
import videogame_engine as ve

ROOT = Path(__file__).resolve().parent

def _render(activation):
    bed = ve.MusicBed(123, dj_goava=activation > 0.0, goava_activation=activation)
    samples = [bed.step(1.0 / 22050.0) for _ in range(4096)]
    return samples, dict(bed.last_cross_media)

def test_goava_pairwise_coupling_is_deterministic_and_bounded():
    off, f0 = _render(0.0)
    half, fhalf = _render(0.5)
    full, ffull = _render(1.0)
    half_again, fhalf_again = _render(0.5)
    assert half == half_again
    assert fhalf == fhalf_again
    assert f0["mutual_coupling"] == 0.0
    assert 0.0 < fhalf["mutual_coupling"] < ffull["mutual_coupling"]
    assert off != half and half != full
    assert max(abs(v) for v in full) <= 1.0
    assert fhalf["partial_count"] == 3

def test_game_runtime_carries_live_cross_media_features_to_visual_field():
    src = (ROOT / "videogame_engine.py").read_text(encoding="utf-8")
    assert 'self._xcorr_snap["cross_media"] = trace' in src
    assert 'field["goava_coupling"]' in src
    assert 'self._xcorr_snap["hue"]' in src

def test_host_video_frame_consumes_analyzed_audio_trace():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert "CANONICAL_CROSS_MEDIA_ROUTE_20261023" in src
    assert "_last_cross_media_wave_analysis" in src
    assert "spectral_centroid_norm" in src
    assert '"goava_activation"' in src
