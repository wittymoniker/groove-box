from pathlib import Path

ROOT = Path(__file__).resolve().parent


def text(name='video_clip_studio.py'):
    return (ROOT / name).read_text(encoding='utf-8')


def test_linux_v4l2_is_shared_per_physical_device():
    s=text()
    assert '_SHARED_V4L2_STREAMS = {}' in s
    assert 'class _SharedV4L2Capture(QObject)' in s
    assert 'self._attach_shared_v4l2_stream(dev)' in s
    assert 'self._detach_shared_v4l2_stream()' in s
    assert 'permits multiple simultaneous Groovebox recordings from one webcam' in s


def test_shared_recording_does_not_open_second_v4l2_input():
    s=text()
    block=s[s.index('def _start_v4l2_capture'):s.index('def _v4l2_watchdog', s.index('def _start_v4l2_capture'))]
    assert 'self._start_software_recording(recdir,stamp)' in block
    assert "args=['-hide_banner'" not in block
    assert 'self._v4l_recording=False' in block


def test_simultaneous_recordings_get_distinct_paths_and_compressed_spool():
    s=text()
    assert 'def _recording_stamp' in s
    assert 'time.time_ns()' in s
    assert "f'_{frac:03d}_{id(self)&0xffff:04x}'" in s
    assert "self._sw_mjpeg_path=os.path.join(d,'video.mjpeg')" in s
    assert "'-f','mjpeg','-framerate'" in s


def test_stopping_one_recording_releases_only_its_subscription():
    s=text()
    block=s[s.index('def _finish_software_recording'):s.index('def _record_format_candidates')]
    assert 'self._detach_shared_v4l2_stream()' in block
    assert 'if this was the final subscriber the physical' in block
    assert 'if not list(self.subscribers):' in s


def test_busy_device_has_retry_and_holder_diagnostics_without_killing_other_apps():
    s=text()
    assert 'def _linux_camera_holders' in s
    assert 'def _reclaim_own_v4l2_holders' in s
    assert 'not _pid_is_descendant(pid,me)' in s
    assert "'device or resource busy' in low" in s
    assert "Device currently held by:" in s
