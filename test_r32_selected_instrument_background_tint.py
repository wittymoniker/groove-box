"""Contract test for the low-intensity selected-instrument background cue."""
from pathlib import Path

SOURCE = Path(__file__).with_name("groovebox.py").read_text(encoding="utf-8")


def test_selected_instrument_color_updates_background_layer():
    method = SOURCE.split("    def _r32_show_instrument_color(self):", 1)[1].split("\n    def ", 1)[0]
    assert "bg._instrument_tint = str(c)" in method
    assert "bg.update()" in method
    assert "setStyleSheet" in method  # existing palette swatch remains intact


def test_background_tint_is_subtle_and_painted_on_both_background_modes():
    assert "def _paint_instrument_tint(self, painter):" in SOURCE
    assert "c.setAlpha(13)" in SOURCE
    paint = SOURCE.split("    def paintEvent(self, event):", 1)[1].split("\n    def _paint_field", 1)[0]
    assert paint.count("self._paint_instrument_tint(p)") == 2
