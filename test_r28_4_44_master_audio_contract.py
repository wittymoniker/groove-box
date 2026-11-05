"""Source-contract regressions for the R28.4.44 audio/master-control pass."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent

class MasterAudioContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT / 'groovebox.py').read_text(encoding='utf-8')
        cls.performance = (ROOT / 'performance.py').read_text(encoding='utf-8')

    def test_performance_master_defaults_to_72_percent(self):
        self.assertIn('initial_master_pct = 72', self.performance)
        self.assertNotIn('initial_master_pct = 50', self.performance)

    def test_zero_volume_is_not_replaced_by_fallback(self):
        self.assertNotIn('getattr(self, "master_volume", 0.5) or 0.5', self.main)
        self.assertIn('vol = float(getattr(self, "master_volume", 0.72))', self.main)
        self.assertIn('master_volume_snapshot = max(0.0, min(1.0, master_volume_snapshot))', self.main)

    def test_main_window_has_no_visible_master_volume_widgets(self):
        self.assertIn('self.lbl_master_volume_title = None', self.main)
        self.assertIn('self.lbl_master_vol = None', self.main)
        self.assertIn('self.slider_master_vol.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)', self.main)

    def test_global_eq_is_saved_restored_and_in_mixdown(self):
        self.assertIn('"master_global_eq": copy.deepcopy(getattr(self, "master_global_eq_points"', self.main)
        self.assertIn('self.master_global_eq_curve.set_points(data.get("master_global_eq"', self.main)
        self.assertIn('master = self._apply_master_global_eq(master, sample_rate)', self.main)

    def test_live_transport_and_audition_paths_apply_shared_gain(self):
        self.assertIn('np.float32(vol * drive)', self.main)
        self.assertIn('np.float32(max(0.0, min(1.0, master)))', self.main)
        self.assertIn('master = float(getattr(self, "master_volume", 0.72))', self.main)

    def test_ball_ca_ui_and_fixed_share_are_present(self):
        self.assertIn('self.ball_synth_preview.positionChanged.connect', self.main)
        self.assertIn('self.ball_synth_params = {"gravity":0.25', self.main)
        self.assertIn('canonical_share":0.5', self.main)
        self.assertIn('self.master_global_eq_curve.curveChanged.connect(self._on_master_global_eq_changed)', self.main)

if __name__ == '__main__':
    unittest.main()
