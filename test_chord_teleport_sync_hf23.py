from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / 'groovebox.py').read_text(encoding='utf-8')
OVERLAY = (ROOT / 'BUILD_ISO/app-overlay-v35.22zz/groovebox.py').read_text(encoding='utf-8')

class ChordTeleportSyncHF23(unittest.TestCase):
    def test_source_parses(self):
        ast.parse(SOURCE)

    def test_teleport_popup_has_chord_count_and_both_buttons(self):
        for token in ('self.popup_chord_note_minus = QPushButton("− Note")',
                      'self.popup_chord_note_plus = QPushButton("+ Note")',
                      'self.popup_chord_note_count = QSpinBox()',
                      'self.popup_chord_note_minus.clicked.connect',
                      'self.popup_chord_note_plus.clicked.connect'):
            self.assertIn(token, SOURCE)

    def test_popup_and_main_share_same_sequence_local_handler(self):
        self.assertIn('self.popup_chord_note_count.valueChanged.connect(self._on_chord_note_count_changed)', SOURCE)
        self.assertIn('self.spin_chord_note_count.valueChanged.connect(self._on_chord_note_count_changed)', SOURCE)
        self.assertIn('def _sync_chord_note_count_controls(self, mem=None):', SOURCE)
        self.assertIn('self._sync_chord_note_count_controls(self._current_sequence_mem(self._current_instrument_name()))', SOURCE)

    def test_overlay_is_byte_identical(self):
        self.assertEqual(SOURCE, OVERLAY)

if __name__ == '__main__':
    unittest.main()
