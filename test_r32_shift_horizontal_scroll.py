from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_global_wheel_filter_routes_shift_to_horizontal_scrollbars():
    source = (ROOT / "groovebox.py").read_text()
    wheel = source.split("class _NoWheelSliderFilter", 1)[1].split("class SeedScriptSyntaxHighlighter", 1)[0]
    assert "ShiftModifier" in wheel
    assert "bar = area.horizontalScrollBar()" in wheel
    assert "QAbstractScrollArea" in wheel
    assert "if bar.maximum() > bar.minimum() and amount" in wheel
    assert "No horizontal overflow in any ancestor" in wheel


def test_plain_wheel_and_control_parameter_editing_are_preserved():
    source = (ROOT / "groovebox.py").read_text()
    wheel = source.split("class _NoWheelSliderFilter", 1)[1].split("class SeedScriptSyntaxHighlighter", 1)[0]
    assert "ControlModifier" in wheel
    assert "bar = area.verticalScrollBar()" in wheel
    assert "_VALUE_WIDGETS" in wheel


def test_synth_architecture_is_explained_in_both_help_surfaces():
    standalone = (ROOT / "HELP_TEXT.md").read_text()
    app_source = (ROOT / "groovebox.py").read_text()
    assert "SYNTHESIZER ARCHITECTURE — HOW A NOTE BECOMES SOUND" in standalone
    assert "SYNTHESIZER ARCHITECTURE — HOW A NOTE BECOMES SOUND" in app_source
    for term in ("CANONICAL GENERATION LAYER", "FOUR PER-INSTRUMENT GEOMETRIC SYNTH ENGINES",
                 "SEQUENCE PROGRAMS, MORPH AND AUTOMATION", "NOTE / VOICE RENDER AND MIX",
                 "EXECUTION AND PERFORMANCE BOUNDARIES"):
        assert term in standalone and term in app_source
