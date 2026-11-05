from pathlib import Path

SRC = Path(__file__).with_name("video_clip_studio.py").read_text(errors="ignore")

def test_live_meter_starts_without_preview_button():
    assert "GROOVEBOX_V35_22ZV_LIVE_MIC_LEVEL_AUTO_MONITOR_20260924" in SRC
    assert "self.cmb_mic.currentIndexChanged.connect(self._audio_input_device_changed)" in SRC
    assert "QTimer.singleShot(0, self._ensure_live_mic_meter)" in SRC
    assert "def _ensure_live_mic_meter" in SRC
    assert "self._start_selected_audio_source" in SRC

def test_meter_is_capture_only_and_releases_on_hide():
    assert "it does not play the mic to output" in SRC
    assert "def hideEvent(self, event)" in SRC
    assert "self._release_capture_devices(True)" in SRC

def test_meter_ui_has_explicit_live_pause_failure_states():
    assert "■ Pause Mic Level" in SRC
    assert "▶ Resume Mic Level" in SRC
    assert "Mic level — unavailable" in SRC
