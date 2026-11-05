from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "groovebox.py").read_text(encoding="utf-8")
OVERLAY = (ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "groovebox.py").read_text(encoding="utf-8")


def _method(source):
    start = source.index("    def trigger_all_instruments_hit(self):")
    end = source.find("\n    def ", start + 5)
    return source[start:end if end >= 0 else None]


def test_trigger_all_uses_operator_media_and_global_carrier_fallback():
    method = _method(SOURCE)
    assert 'getattr(self, "instrument_media_samples", {})' in method
    assert 'getattr(self, "imported_waveform", None)' in method
    assert 'rec.get("waveform")' in method
    assert "media_hits += 1" in method


def test_trigger_all_keeps_safe_bounded_mix_and_existing_audio_submit_path():
    method = _method(SOURCE)
    assert "np.nan_to_num" in method
    assert "if peak > 0.92" not in method and "mix *= np.float32(0.35)" in method   # NO_FADE_NO_LIMIT_20261102: fixed headroom, no limiter
    assert "self._pkp_poly_submit(mix, sr)" in method
    assert "self.visual_oscilloscope.update_waveform" in method


def test_iso_overlay_contains_the_same_trigger_all_fix():
    assert _method(SOURCE) == _method(OVERLAY)
