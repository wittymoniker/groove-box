from pathlib import Path

ROOT=Path(__file__).resolve().parent
PERF=(ROOT/'performance.py').read_text(errors='ignore')
GB=(ROOT/'groovebox.py').read_text(errors='ignore')


def test_open_windows_tab_and_restore_controls_present():
    assert 'GROOVEBOX_V35_22ZU_WAYLAND_WINDOW_SESSION_FAST_LAUNCH_20260924' in PERF
    assert '"▤ Open Windows"' in PERF
    assert 'def _restore_selected_window' in PERF
    assert 'def _restore_all_windows' in PERF
    assert 'closed/hidden' in PERF


def test_session_manager_retains_and_restores_wayland_windows():
    assert 'GROOVEBOX_V35_22ZU_WAYLAND_WINDOW_SESSION_MANAGER_20260924' in GB
    assert 'self._managed_windows = {}' in GB
    assert 'WA_DeleteOnClose, False' in GB
    assert 'def managed_windows' in GB
    assert 'def restore_window' in GB
    assert 'window.showNormal()' in GB
    assert 'requestActivate' in GB


def test_file_browser_and_player_launch_non_modal():
    a=PERF.index('# ------------------------------------------------------------------ Browse Files menu / Player Window')
    b=PERF.index('    def _routed_player',a)
    seg=PERF[a:b]
    assert '.exec()' not in seg
    assert 'def _show_session_window' in seg
    assert 'self._file_manager_window' in seg
    assert 'self._media_player_window' in seg


def test_file_browser_listing_is_deferred_and_backgrounded():
    fm=PERF[PERF.index('class FileManagerDialog'):]
    assert 'QTimer.singleShot(0, self.refresh)' in fm
    assert 'def _scan_directory_worker' in fm
    assert 'os.scandir(directory)' in fm
    assert 'Loading directory in background' in fm
    assert 'self._worker_pool.start(_PoolTask(self._scan_directory_worker' in fm


def test_player_device_scan_is_not_constructor_blocking():
    mp=PERF[PERF.index('class MediaPlayerWindow'):PERF.index('class FileManagerDialog')]
    ctor=mp[mp.index('    def __init__'):mp.index('    # -- FX row builder')]
    assert 'self._refresh_devices()' not in ctor
    assert 'System default' in ctor or 'system-default' in ctor, "constructor must use a clear system-default label"
    assert 'def _scan_devices_worker' in mp
    assert 'self._device_scan_pool.start' in mp


def test_close_hides_live_file_and_dj_sessions_until_app_exit():
    mp=PERF[PERF.index('class MediaPlayerWindow'):PERF.index('class FileManagerDialog')]
    fm=PERF[PERF.index('class FileManagerDialog'):]
    assert 'self.hide()\n        event.ignore()' in mp
    assert 'self.hide()\n        event.ignore()' in fm
    assert 'def shutdown_for_application_exit' in mp
    assert 'def shutdown_for_application_exit' in fm
    assert 'prepare_for_application_exit' in GB
