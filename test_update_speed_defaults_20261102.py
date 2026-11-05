"""20261102: default 48 instruments + canonical-update speedups that must not change any result."""
import copy
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
SRC = (ROOT / "groovebox.py").read_text(encoding="utf-8")


def test_new_projects_start_with_48_instruments():
    assert "DEFAULT_ACTIVE_INSTRUMENTS = 48" in SRC
    assert "self.instrument_names_48[:max(2, min(MAX_INSTRUMENTS, int(DEFAULT_ACTIVE_INSTRUMENTS)))]" in SRC
    assert "self.spin_synth_count.setValue(48)" in SRC and "self.spin_synth_count.setRange(2, 128)" in SRC   # still raisable to 128


def test_scalar_clip_is_exactly_np_clip():
    import numpy as np
    import groovebox as g
    rnd = random.Random(7)
    vals = [0.0, -1e9, 1e9, float("nan"), float("inf"), -float("inf"), 10.0, 24000.0, 0.05, 24.0, -36.0, 36.0]
    vals += [rnd.uniform(-100, 30000) for _ in range(3000)]
    for lo, hi in ((10.0, 24000.0), (-36.0, 36.0), (0.05, 24.0), (0.0, 1.0), (-18.0, 18.0)):
        for v in vals:
            a, b = float(np.clip(v, lo, hi)), g._fclip(v, lo, hi)
            assert (a != a and b != b) or a == b, (v, lo, hi, a, b)


def _eq_cases():
    import groovebox as g
    rnd = random.Random(11)
    types = list(g.EQ_POLE_TYPES)
    cases = []
    for _ in range(300):
        poles = []
        for k in range(rnd.randint(0, 9)):
            poles.append({"frequency_hz": rnd.choice([rnd.uniform(-50, 40000), 0, None, "x"]),
                          "gain_db": rnd.choice([rnd.uniform(-80, 80), None, "bad"]),
                          "q": rnd.choice([rnd.uniform(-1, 40), 0, None]),
                          "type": rnd.choice(types + ["Nope", None]),
                          "automation_depth": rnd.choice([rnd.uniform(-1, 2), None]),
                          "_mix_weight": rnd.choice([rnd.uniform(-1, 2), None]),
                          "order": rnd.choice([k, None, "z"]), "enabled": rnd.random() > 0.2})
        cases.append(poles)
    return cases


def test_eq_pole_normalisation_unchanged_by_scalar_clip_and_cache(monkeypatch):
    """New (scalar clip + content cache, cold and hot) == the original np.clip implementation."""
    import numpy as np
    import groovebox as g
    cases = _eq_cases()
    g._EQ_NORMALIZE_CACHE.clear()
    cold = [g._normalize_eq_poles(copy.deepcopy(c)) for c in cases]
    hot = [g._normalize_eq_poles(copy.deepcopy(c)) for c in cases]          # served from the cache
    curves_hot = [g._eq_legacy_curve_from_poles(copy.deepcopy(c)) for c in cases]
    monkeypatch.setattr(g, "_fclip", lambda x, lo, hi: float(np.clip(x, lo, hi)))
    original = [g._normalize_eq_poles_uncached(list(copy.deepcopy(c) or []), 128) if c else g._normalize_eq_poles(copy.deepcopy(c))
                for c in cases]
    assert cold == original and hot == original
    g._EQ_NORMALIZE_CACHE.clear()
    curves_cold = [g._eq_legacy_curve_from_poles(copy.deepcopy(c)) for c in cases]
    assert curves_cold == curves_hot


def test_cached_results_are_independent_copies():
    import groovebox as g
    poles = [{"frequency_hz": 1000.0, "gain_db": 3.0, "q": 1.0, "type": "Bell"}]
    g._EQ_NORMALIZE_CACHE.clear()
    first = g._normalize_eq_poles(copy.deepcopy(poles))
    first[0]["gain_db"] = 99.0
    first.append({"junk": 1})
    again = g._normalize_eq_poles(copy.deepcopy(poles))
    assert again[0]["gain_db"] == 3.0 and len(again) == 1


def test_fractal_projection_is_cached_by_plan_window_and_length():
    assert "_fractal_raster_cache" in SRC
    seg = SRC.split("GROOVEBOX_RASTER_CACHE_20261102")[1][:1500]
    for needle in ("event_plan_sha256", "window_steps", "identity", "int(n)", "rasterize_sequence(fractal_plan, n)"):
        assert needle in seg, needle


def test_carrier_report_names_the_reasons_and_is_wired_into_both_exports():
    for needle in ("def _carrier_stats_reset", "def _carrier_stat(", "def _carrier_report(",
                   "Carrier video file is missing", "ffmpeg is not available", "gave no frame for",
                   "appear as small tiles"):
        assert needle in SRC, needle
    assert SRC.count("self._carrier_stats_reset()") == 2                 # MCC video + MP4/WebM/AVI
    assert SRC.count("self._carrier_stat(") == 2 + 0 or SRC.count("self._carrier_stat(") >= 2
    assert SRC.count("_carrier_note = self._carrier_report(") == 2


def test_carrier_report_logic(tmp_path):
    import groovebox as g

    class Fake:
        imported_video_path = ""
        instrument_names_48 = []
        instrument_media_samples = {}
        _bound_video_sources = g.MathematiciansGrooveboxApp._bound_video_sources
        _carrier_stats_reset = g.MathematiciansGrooveboxApp._carrier_stats_reset
        _carrier_stat = g.MathematiciansGrooveboxApp._carrier_stat
        _carrier_report = g.MathematiciansGrooveboxApp._carrier_report

    f = Fake()
    f._carrier_stats_reset()
    assert f._carrier_report(10, 64, 36) == ""                                   # nothing bound: nothing to say
    f.imported_video_path = str(tmp_path / "gone.mp4")
    assert "missing" in f._carrier_report(10, 64, 36)                            # path set, file gone
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    f.imported_video_path = str(clip)
    f._carrier_stats_reset()
    for i in range(10):
        f._carrier_stat(i < 7, i)
    note = f._carrier_report(10, 64, 36)
    assert "3 of 10" in note and "frame 7" in note
    assert "ffmpeg" in f._carrier_report(10, 64, 36, ffmpeg_ok=False)
    f.imported_video_path = ""
    f.instrument_media_samples = {"Op": {"video_input_enabled": True, "video_path": str(clip)}}
    f.instrument_names_48 = ["Op"]
    assert "small tiles" in f._carrier_report(10, 64, 36)
