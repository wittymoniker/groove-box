import pathlib
import unittest

SRC = pathlib.Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

class CarrierClearRegression(unittest.TestCase):
    def test_clear_buttons_and_handlers_exist(self):
        self.assertIn('QPushButton("Clear Global Carrier")', SRC)
        self.assertIn('clicked.connect(self.clear_global_carrier)', SRC)
        self.assertIn('QPushButton("Clear Local Carrier")', SRC)
        self.assertIn('clicked.connect(self.clear_local_carrier)', SRC)

    def test_global_clear_resets_audio_video_and_bindings(self):
        start = SRC.index('    def _clear_global_carrier_state')
        end = SRC.index('    def clear_global_carrier', start)
        body = SRC[start:end]
        for token in (
            'self.imported_waveform = None',
            'self.imported_wav_path = ""',
            'self.imported_video_path = ""',
            'self.imported_video_meta = {}',
            'self.media_carrier_slot = {}',
            'self.carrier_binding_mode = ""',
            'self.carrier_binding_source = ""',
            'self.carrier_bound_layers_state = {}',
            '"play_buffer"',
        ):
            self.assertIn(token, body)

    def test_local_clear_only_removes_selected_operator_media(self):
        start = SRC.index('    def clear_local_carrier')
        end = SRC.index('    def _clear_global_carrier_state', start)
        body = SRC[start:end]
        self.assertIn('store.pop(name, None)', body)
        self.assertNotIn('self.imported_waveform = None', body)

    def test_video_only_import_is_not_synthetic_silent_audio(self):
        start = SRC.index('    def _load_video_path')
        end = SRC.index('    def _update_imported_media_ui', start)
        body = SRC[start:end]
        self.assertIn('self.imported_waveform = None', body)
        self.assertIn('self.imported_wav_path = ""', body)
        self.assertNotIn('duration * 44100.0', body)

    def test_project_load_clears_stale_carrier_and_prefers_video(self):
        self.assertIn('self._clear_global_carrier_state(refresh=False, update_ui=True)', SRC)
        self.assertIn('project_carrier_cleared', SRC)
        self.assertIn('media_carrier_state', SRC)

    def test_exact_silence_is_visible_during_export(self):
        self.assertIn('_export_peak == 0.0', SRC)
        self.assertIn('rendered master is exactly silent', SRC)

if __name__ == '__main__':
    unittest.main()
