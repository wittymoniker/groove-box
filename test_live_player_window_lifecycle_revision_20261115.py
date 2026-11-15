from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIVE = (ROOT / "live_player.py").read_text(encoding="utf-8")
PERF = (ROOT / "performance.py").read_text(encoding="utf-8")
GB = (ROOT / "groovebox.py").read_text(encoding="utf-8")


def test_live_player_defaults_to_main_video_rig_only():
    block = LIVE[LIVE.index("LAYERS = ("):LIVE.index("LAYER_SHORT =", LIVE.index("LAYERS = ("))]
    assert '("rig", "Main video rig / scenograph", True)' in block
    for key in ("orbit", "ring", "labels", "strip", "media", "multidim", "camera", "camera_full"):
        assert f'("{key}",' in block
        line = next(x for x in block.splitlines() if f'("{key}",' in x)
        assert line.rstrip().endswith("False),") or line.rstrip().endswith("False))")
    assert 'self.chk_rig.setChecked(True)' in LIVE
    assert 'self.chk_cam = QCheckBox("🎥 Camera capture")' in LIVE


def test_live_player_has_explicit_layer_and_canonical_randomizers():
    assert 'self.btn_randomize_layers = QPushButton("🎲 Randomize")' in LIVE
    assert 'self.btn_reset_layers = QPushButton("↺ Main rig only")' in LIVE
    assert 'self.btn_randomize_morph = QPushButton("🎲 Randomize canonical")' in LIVE
    assert 'self.btn_reset_morph = QPushButton("↺ Reset canonical")' in LIVE
    assert 'self.status.setText("Main video rig / scenograph only.")' in LIVE
    assert 'Camera and microphone capture remain off' in LIVE


def test_camera_controls_are_above_visual_layer_grid():
    assert 'self.chk_camera_layer = QCheckBox("Camera PiP")' in LIVE
    assert 'self.chk_camera_full_layer = QCheckBox("Camera full scene")' in LIVE
    assert 'self._layer_actions["camera"] = self.chk_camera_layer' in LIVE
    assert LIVE.index('lay.addLayout(ins)') < LIVE.index('lay.addLayout(mor)') < LIVE.index('lay.addLayout(layer_row)')


def test_canonical_key_sample_toggles_are_independent_of_master_switch():
    assert 'MORPH_DEFAULTS = {"enabled": False, "amount": 50, "keys": False, "samples": False, "place": 0}' in LIVE
    morph = LIVE[LIVE.index('def _apply_morph(self, eng):'):LIVE.index('def _place_window_s', LIVE.index('def _apply_morph(self, eng):'))]
    assert 'self.sld_morph.setEnabled(bool(st["enabled"]))' in morph
    assert 'self.chk_morph_keys.setEnabled(True)' in morph
    assert 'self.chk_morph_media.setEnabled(True)' in morph


def test_live_player_refresh_is_bounded_and_stops_on_session_close():
    assert 'self.timer.setInterval(33)' in LIVE
    assert 'if now - float(getattr(self, "_last_scode_visual_tick", 0.0)) < 0.1:' in LIVE
    assert 'def release_session_resources(self):' in LIVE
    assert 'self.timer.stop()' in LIVE
    assert 'def resume_session_resources(self):' in LIVE


def test_open_windows_refresh_runs_only_while_tab_active():
    assert 'self._open_windows_refresh_timer.setInterval(750)' in PERF
    assert 'self._set_open_windows_refresh_active(label == "▤ Open Windows")' in PERF
    assert 'def _set_open_windows_refresh_active(self, active):' in PERF
    assert 'def release_session_resources(self):' in PERF
    assert 'self._set_open_windows_refresh_active(False)' in PERF


def test_window_manager_close_calls_release_hook_and_restore_resumes_it():
    assert 'def _record_window_closed(self, window):' in GB
    assert 'hook = getattr(window, "release_session_resources", None)' in GB
    assert 'def _record_window_opened(self, window):' in GB
    assert 'hook = getattr(window, "resume_session_resources", None)' in GB
    close = GB[GB.index('def close_window(self, window, force=False):'):GB.index('def restore_all_windows', GB.index('def close_window(self, window, force=False):'))]
    assert 'self._record_window_closed(window)' in close
    restore = GB[GB.index('def restore_window(self, window):'):GB.index('def close_window(self, window, force=False):')]
    assert 'self._record_window_opened(window)' in restore
    assert 'if et == QEvent.Type.Show:\n                    self._record_window_opened(obj)' in GB
