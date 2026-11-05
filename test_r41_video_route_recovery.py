from pathlib import Path

ROOT = Path(__file__).resolve().parent
VC = (ROOT / 'video_clip_studio.py').read_text(encoding='utf-8')
PROBE = (ROOT / 'device_probe_helper.py').read_text(encoding='utf-8')
PERF = (ROOT / 'performance.py').read_text(encoding='utf-8')


def section(source, start, end):
    a = source.index(start)
    b = source.index(end, a + len(start))
    return source[a:b]


def test_v4l2_shared_stream_keeps_preview_intent_and_reconnects():
    shared = section(VC, 'class _SharedV4L2Capture', 'class VideoClipStudio')
    assert 'def _schedule_reconnect' in shared
    assert 'def _reconnect_if_current' in shared
    assert 'self._reconnect_delays=(350,800,1600,3200,5000,8000)' in shared
    assert 'Camera temporarily unavailable; keeping the route armed' in shared
    assert "self._broadcast_status(detail[-1200:],True)" not in shared


def test_camera_stream_watchdog_detects_a_live_but_stalled_device():
    shared = section(VC, 'class _SharedV4L2Capture', 'class VideoClipStudio')
    assert 'self._last_frame_at=time.monotonic()' in shared
    assert 'stale_for >= 6.0' in shared
    assert 'Camera disconnected or stalled; preserving the selected route' in shared


def test_probe_prefers_stable_camera_identity_and_keeps_node_fallback():
    assert "glob.glob('/dev/v4l/by-id/*-video-index0')" in PROBE
    assert "'stable_id':Path(stable).name" in PROBE
    assert "glob.glob('/dev/video*')" in PROBE
    assert "'node':real" in PROBE


def test_studio_reprobes_and_rebinds_without_silent_camera_switch():
    assert 'def _schedule_camera_device_reprobe' in VC
    assert 'def _resume_camera_preview_after_probe' in VC
    assert 'stream is None or current_key != new_key' in VC
    assert 'A selected route that disappeared must not silently fall back' in VC
    assert 'Camera is not currently present. Preview remains armed' in VC


def test_performance_camera_preference_restores_by_path_or_label():
    quick = section(PERF, 'def _on_quick_devices_ready', 'def _quick_audio_output_changed')
    assert '_preferred_video_device_path' in quick
    assert '_preferred_video_device_name' in quick
    assert 'pref_name.casefold() in str(row.get(\'name\',\'\')).casefold()' in quick
    assert "setattr(self.host,'_preferred_video_device_name',name)" in PERF


def test_active_iso_overlay_is_exactly_synchronized():
    overlay = ROOT / 'BUILD_ISO' / 'app-overlay-v35.22zz' / 'video_clip_studio.py'
    assert overlay.is_file()
    assert overlay.read_bytes() == (ROOT / 'video_clip_studio.py').read_bytes()


def test_failed_to_start_retires_generation_and_keeps_preview_recoverable():
    failed = section(VC, 'def _process_error', 'def _watchdog')
    assert 'QProcess.ProcessError.FailedToStart' in failed
    assert 'self._generation += 1' in failed
    assert 'self._schedule_reconnect(retry_generation' in failed


def test_all_delayed_camera_retries_are_cancelled_by_explicit_stop():
    shared = section(VC, 'class _SharedV4L2Capture', 'class VideoClipStudio')
    assert 'QTimer.singleShot(60,lambda g=generation:self._reconnect_if_current(g))' in shared
    assert 'QTimer.singleShot(delay,lambda g=generation:self._reconnect_if_current(g))' in shared
    assert 'if generation != self._generation or self._stopping or not list(self.subscribers):' in shared
    assert 'QTimer.singleShot(60,self.start)' not in shared
    assert 'QTimer.singleShot(delay,self.start)' not in shared


def test_all_changed_iso_runtime_modules_match_root_sources():
    for name in ('groovebox.py','performance.py','video_clip_studio.py',
                 'device_probe_helper.py','multidim_synth.py','multidim_ui.py'):
        overlay = ROOT / 'BUILD_ISO' / 'app-overlay-v35.22zz' / name
        assert overlay.is_file(), name
        assert overlay.read_bytes() == (ROOT / name).read_bytes(), name
