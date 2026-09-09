from pathlib import Path


def test_return_to_main_reserves_layout_space():
    text = (Path(__file__).with_name("groovebox.py")).read_text(encoding="utf-8")
    start = text.index("class _MainWindowRelaunchFilter")
    end = text.index("class MathematiciansGrooveboxApp", start)
    block = text[start:end]

    assert "Return to Main Window" in block
    assert "def _reserve_button_space" in block
    assert "layout.setContentsMargins(left, required_top, right, bottom)" in block
    assert "required_top = max(top, int(margin + button.height() + 8))" in block
    assert "_grooveboxRelaunchOriginalMargins" in block
    assert "_grooveboxRelaunchHeightReserved" in block

    # Space must be reserved before the overlay button is placed.
    pos = block.index("def _position_button")
    pos_block = block[pos:]
    assert pos_block.index("self._reserve_button_space") < pos_block.index("button.move")
