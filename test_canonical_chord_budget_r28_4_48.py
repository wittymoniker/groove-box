from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / 'groovebox.py').read_text(encoding='utf-8')

class CanonicalChordBudgetContract(unittest.TestCase):
    def test_source_parses(self):
        ast.parse(SOURCE)

    def test_budget_formula_is_integer_floor(self):
        self.assertIn('return max(1, 512 // self._canonical_chord_instrument_count())', SOURCE)

    def test_chord_state_is_sequence_local_and_backward_compatible(self):
        self.assertIn('mem.setdefault("chord_note_count", 3)', SOURCE)
        self.assertIn('mem.setdefault("chord_intervals", [0, 4, 7])', SOURCE)
        self.assertIn('mem.setdefault("chord_user_owned", False)', SOURCE)

    def test_ticker_and_deterministic_extension_exist(self):
        self.assertIn('self.btn_chord_note_minus.clicked.connect', SOURCE)
        self.assertIn('self.btn_chord_note_plus.clicked.connect', SOURCE)
        self.assertIn('(0, 4, 7, 12, 16, 19, 24)', SOURCE)
        self.assertNotIn('random.', SOURCE[SOURCE.index('def _on_chord_note_count_changed'):SOURCE.index('def reload_active_instrument_sequencer_ui')])

    def test_step_visuals_have_green_subdivisions(self):
        self.assertIn('def _style_chord_subdivisions', SOURCE)
        self.assertIn('#174b32', SOURCE)
        self.assertIn('self._style_chord_subdivisions(step_btn, mem)', SOURCE)

    def test_volume_handler_does_not_reopen_stream(self):
        start = SOURCE.index('    def _on_master_vol_changed(self, val):')
        end = SOURCE.find('\n    def ', start + 5)
        handler = SOURCE[start:end]
        for forbidden in ('stream.stop(', 'stream.close(', 'stream.start(', 'sd.OutputStream('):
            self.assertNotIn(forbidden, handler)
        self.assertIn('self.master_volume = val / 100.0', handler)

if __name__ == '__main__':
    unittest.main()
