from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _handler(path):
    src = path.read_text()
    start = src.index('    def _keychart_handle_key(self, obj, event):')
    end = src.index('    def _keychart_trigger(', start)
    return src[start:end]


def test_live_keyboard_accepts_any_active_top_level_window():
    for rel in ('groovebox.py', 'BUILD_ISO/app-overlay-v35.22zz/groovebox.py'):
        body = _handler(ROOT / rel)
        assert '_win.isActiveWindow()' in body
        assert '_app.activeWindow() is not _win' in body
        assert '_ok_windows' not in body
        assert 'activePopupWidget' in body and 'activeModalWidget' in body
        assert '_keychart_text_entry_focused(obj)' in body


def test_keychart_pitch_bend_is_not_live_player_focus_dependent():
    for rel in ('groovebox.py', 'BUILD_ISO/app-overlay-v35.22zz/groovebox.py'):
        src = (ROOT / rel).read_text()
        start = src.index('    def _keychart_trigger(')
        end = src.index('    def _show_drive_copy_dialog(', start)
        body = src[start:end]
        assert 'elif _lp is not None:' in body
        assert 'elif _lp is not None and _lp.isActiveWindow()' not in body


def test_help_mentions_application_wide_keyboard_and_realtime_limits():
    for rel in ('groovebox.py', 'HELP_TEXT.md'):
        src = (ROOT / rel).read_text()
        assert 'LIVE KEYBOARD — APPLICATION-WIDE' in src
        assert '1080p/3D' in src
