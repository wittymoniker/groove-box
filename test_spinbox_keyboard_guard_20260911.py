from pathlib import Path

SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')


def test_global_spinbox_input_contract_is_deliberate():
    start = SRC.index('def _configure_spinbox_input_behavior(widget):')
    end = SRC.index('\n\nclass _MathSymbolSpinWatcher', start)
    block = SRC[start:end]
    assert 'setKeyboardTracking(False)' in block
    assert 'Qt.FocusPolicy.ClickFocus' in block
    assert 'setAccelerated(False)' in block
    assert 'StrongFocus' not in block


def test_scroll_guard_does_not_reenable_strong_focus_for_spinboxes():
    start = SRC.index('def _install_scroll_value_guards(self):')
    end = SRC.index('\n    def _forward_wheel_to_scroll_area', start)
    block = SRC[start:end]
    assert '_configure_spinbox_input_behavior(w)' in block
    assert 'Qt.FocusPolicy.StrongFocus' not in block
