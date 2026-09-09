"""Static regression contract for generated-game lag controls."""
from pathlib import Path

SRC = Path(__file__).with_name("videogame_engine.py").read_text(encoding="utf-8")


def test_generated_game_lag_contract():
    assert 'self._panel_interval = 0.10' in SRC
    assert 'self._net_per_frame = 64' in SRC
    assert 'for _ in range(self._net_per_frame):' in SRC
    assert 'if not self.isVisible() or self.isMinimized():' in SRC
    assert 'def set_active(self, active):' in SRC
    assert 'player.pause()' in SRC
    assert 'def shutdown(self):' in SRC
    assert 'media.shutdown()' in SRC
    assert 'QEvent.Type.WindowStateChange' in SRC
