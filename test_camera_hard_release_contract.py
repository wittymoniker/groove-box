from pathlib import Path

ROOT = Path(__file__).resolve().parent


def text(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_all_video_studios_share_camera_ownership_registry():
    s = text('video_clip_studio.py')
    assert '_capture_instances = weakref.WeakSet()' in s
    assert 'def _prepare_camera_ownership' in s
    assert 'other._release_capture_devices(True)' in s
    assert 'The camera is already active in another Groovebox media window.' in s


def test_qt_camera_graph_is_detached_and_destroyed():
    s = text('video_clip_studio.py')
    assert 'sess.setVideoSink(None)' in s
    assert 'sess.setRecorder(None)' in s
    assert 'sess.setAudioInput(None)' in s
    assert 'sess.setCamera(None)' in s
    assert 'from PyQt6 import sip' in s
    assert 'sip.delete(obj)' in s
    assert "self._camera=None; self._capture_session=None; self._recorder=None; self._record_audio_input=None" in s


def test_failed_camera_start_paths_release_device():
    s = text('video_clip_studio.py')
    assert "# Setup may have opened the OS camera before a later sink/backend step" in s
    assert "# A failed recorder/encoder setup can occur *after* QCamera.start()." in s
    assert "self._release_capture_devices(True)\n        QMessageBox.warning(self,'Camera recording could not start'" in s


def test_qt_stop_has_non_background_release_watchdog():
    s = text('video_clip_studio.py')
    assert 'def _qt_record_stop_release_watchdog' in s
    assert "QTimer.singleShot(250, lambda: self._qt_record_stop_release_watchdog(0))" in s
    assert "QTimer.singleShot(500, lambda a=attempt+1: self._qt_record_stop_release_watchdog(a))" in s


def test_main_media_dialog_uses_strong_release():
    s = text('groovebox.py')
    block = s[s.index('def _close_main_media'):s.index('dlg.closeEvent = _close_main_media')]
    assert 'st._release_capture_devices(True)' in block
