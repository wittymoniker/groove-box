from pathlib import Path

SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

def test_teleport_outside_click_dismiss_contract():
    required = [
        'GROOVEBOX_V35_22ZN_TELEPORT_OUTSIDE_CLICK_DISMISS_20260924',
        'app.installEventFilter(self)',
        'def _teleport_popup_hit(',
        'def _dismiss_teleport_popups_for_click(',
        'QEvent.Type.MouseButtonPress',
        '("step_editor_popup", "automator_teleport_popup")',
        'popup.hide()',
        'popup.findChildren(QComboBox)',
    ]
    missing = [x for x in required if x not in SRC]
    assert not missing, f'missing teleport-dismiss contract(s): {missing}'
