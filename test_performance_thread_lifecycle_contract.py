from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_performance_workers_are_qt_owned_and_drained_on_app_exit():
    s = (ROOT / 'performance.py').read_text(errors='replace')
    assert 'PERF_THREAD_LIFECYCLE_20260924' in s
    assert 'self._worker_pool = QThreadPool(self)' in s
    assert 'self._worker_pool.start(_PoolTask(self._kind_worker.run_batch' in s
    assert 'self._worker_pool.start(_PoolTask(self._prov_worker.lookup' in s
    assert 'self._worker_pool.start(_PoolTask(run))' in s
    assert 'def shutdown_for_application_exit(self):' in s
    shutdown = s[s.index('    def shutdown_for_application_exit(self):'):s.index('    def closeEvent(self, event):', s.index('    def shutdown_for_application_exit(self):'))]
    assert 'browser.shutdown_webengine()' in shutdown
    assert 'pool.waitForDone(15000)' in shutdown
    assert 'self._selection_token += 1' in shutdown
    assert 'self._refresh_generation += 1' in shutdown


def test_main_window_uses_real_performance_shutdown_not_hide_only_close():
    s = (ROOT / 'groovebox.py').read_text(errors='replace')
    assert 'GROOVEBOX_V35_22ZN_PERFORMANCE_THREAD_DRAIN_20260924' in s
    i = s.index('GROOVEBOX_V35_22ZN_PERFORMANCE_THREAD_DRAIN_20260924')
    frag = s[i:i+1000]
    assert 'shutdown_for_application_exit' in frag
    assert '_perf.hide()' in frag
    assert '_perf.close()' not in frag


def test_appliance_webengine_refuses_root_and_never_disables_sandbox():
    s = (ROOT / 'run_groovebox.py').read_text(errors='replace')
    assert 'GROOVEBOX_V35_22ZN_WEBENGINE_NONROOT_GUARD_20260924' in s
    assert 'os.geteuid() != 0' in s
    assert 'runuser' in s and 'groovebox' in s
    assert '--no-sandbox' not in s
    assert 'QTWEBENGINE_DISABLE_SANDBOX' not in s


def test_remote_server_thread_is_joined_before_teardown():
    s = (ROOT / 'performance.py').read_text(errors='replace')
    i = s.index('    def _stop_remote_server(self):')
    frag = s[i:i+1400]
    assert 'th.join(timeout=3.0)' in frag
    assert 'self._remote_thread = None' in frag


def test_file_manager_probe_pool_is_drained():
    s = (ROOT / 'performance.py').read_text(errors='replace')
    i = s.index('class FileManagerDialog')
    frag = s[i:]
    assert 'self._worker_pool = QThreadPool(self)' in frag
    assert 'self._worker_pool.start(_PoolTask(self._kind_worker.run_batch' in frag
    assert 'self._worker_pool.waitForDone(15000)' in frag
