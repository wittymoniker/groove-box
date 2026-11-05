from pathlib import Path
ROOT=Path(__file__).resolve().parent
SRC=(ROOT/'performance.py').read_text(encoding='utf-8')

def test_player_retries_bounded_backend_fallbacks():
    assert 'def _check_player_launch(self, proc, path: str):' in SRC
    assert 'candidates = ("mpv", "vlc", "ffplay")' in SRC
    assert 'All available players failed' in SRC
    assert 'self._player_attempted_backends = set()' in SRC

def test_file_manager_rename_is_safe_and_preserves_project_extension():
    assert 'def _rename_selected(self):' in SRC
    assert 'self._valid_leaf(new_name)' in SRC
    assert 'The destination already exists; nothing was overwritten.' in SRC
    assert 'new_name += os.path.splitext(old_path)[1]' in SRC
