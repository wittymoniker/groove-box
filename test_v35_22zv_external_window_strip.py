from pathlib import Path
ROOT=Path(__file__).resolve().parent
GB=(ROOT/'groovebox.py').read_text(errors='replace')

def test_external_strip_is_parentless_and_always_on_top():
    assert 'class _GrooveboxWindowStrip(QWidget)' in GB
    assert 'super().__init__(None, flags)' in GB
    assert 'WindowStaysOnTopHint' in GB
    assert 'QTabBar' in GB
    assert 'Quit Groovebox' in GB

def test_main_and_tools_close_hide_not_destroy():
    assert 'event.ignore(); main.hide()' in GB
    assert 'event.ignore(); obj.hide()' in GB
    assert 'def request_application_exit' in GB

def test_main_is_always_recoverable_from_strip():
    assert 'def session_windows' in GB
    assert 'out.append(main)' in GB
    assert 'QTimer.singleShot(0, self._main_window_relaunch_filter.ensure_window_strip)' in GB

def test_return_main_breaks_modal_loop_without_deleting_dialog():
    assert 'modal.done(0)' in GB
    assert 'self.restore_window(main)' in GB
