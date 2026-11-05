"""Source contracts: offline/game generation must not stop live transport."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def _method(source, signature, next_signature):
    start = source.index(signature)
    end = source.index(next_signature, start + len(signature))
    return source[start:end]

def test_game_launch_does_not_stop_main_transport():
    src = (ROOT / 'groovebox.py').read_text(errors='replace')
    method = _method(src, '    def _on_play_videogame(self):', '    def ')
    assert 'self.stop_playback()' not in method
    assert 'Do not tear down the main audio stream' in method

def test_bake_compare_generation_does_not_stop_main_transport():
    src = (ROOT / 'groovebox.py').read_text(errors='replace')
    render = _method(src, '    def _bake_compare_render(self, payload):', '    def bake_compare_export_dialog(self):')
    dialog = _method(src, '    def bake_compare_export_dialog(self):', '    def ')
    assert 'self.stop_playback()' not in render
    assert 'self.stop_playback()' not in dialog

def test_root_and_active_overlay_sources_are_synchronized():
    for name in ('groovebox.py', 'performance.py', 'shared_synth_context.py'):
        assert (ROOT / name).read_bytes() == (ROOT / 'BUILD_ISO' / 'app-overlay-v35.22zz' / name).read_bytes()
