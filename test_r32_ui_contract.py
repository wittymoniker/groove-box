"""Source-contract checks for the R32 workstation layout and user help."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GROOVEBOX = (ROOT / "groovebox.py").read_text(encoding="utf-8")
HELP = (ROOT / "HELP_TEXT.md").read_text(encoding="utf-8")
SCODE = (ROOT / "scode_optimizer_bridge.py").read_text(encoding="utf-8")


def test_main_studio_split_is_horizontal_and_full_height():
    assert 'QSplitter(Qt.Orientation.Horizontal)' in GROOVEBOX
    assert 'grooveboxWorkstationScroll' in GROOVEBOX
    assert 'grooveboxVisualExportScroll' in GROOVEBOX


def test_shift_wheel_targets_horizontal_scroll_range():
    assert 'shift_horizontal = bool(mods & Qt.KeyboardModifier.ShiftModifier)' in GROOVEBOX
    assert 'area.horizontalScrollBar()' in GROOVEBOX
    assert 'fallback to the nearest vertical scroll range' in GROOVEBOX


def test_main_surface_is_not_compositor_transparent():
    assert 'central_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)' in GROOVEBOX
    assert 'central_widget.setAutoFillBackground(True)' in GROOVEBOX


def test_help_explains_signal_architecture_and_scroll_controls():
    for phrase in (
        "R32 SYNTHESIZER ARCHITECTURE",
        "one complete operator voice",
        "SEQUENCE-LEVEL SYNTH STATE",
        "MODULATION AND ROUTING ORDER",
        "AUDIO, VISUAL AND GAME ARE THREE VIEWS",
        "Shift + wheel",
        "GROOVEBOX_SCODE_RAM_BUDGET",
    ):
        assert phrase in HELP


def test_scode_uses_shared_bounded_lanes_and_private_copies():
    assert '_thread_budget.make_lane("scode-opt"' in SCODE
    assert '_thread_budget.make_lane("scode-work"' in SCODE
    assert 'return out' in SCODE and 'out = arr[:n].copy()' in SCODE
    assert 'out = arr.copy()' in SCODE
    assert 'budget_bytes' in SCODE and 'pool_evictions' in SCODE
