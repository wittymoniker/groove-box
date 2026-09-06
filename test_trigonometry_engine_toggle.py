from pathlib import Path
def test_trig_toggle_present_and_persisted():
    s=Path("groovebox.py").read_text(encoding="utf-8")
    assert 'QPushButton("Trigonometry Engine: ON")' in s
    assert "def _trigonometry_engine_enabled" in s
    assert "def _on_trigonometry_engine_toggled" in s
    assert "def _trig_engine_transform" in s
    assert '"trigonometry_engine_enabled"' in s
