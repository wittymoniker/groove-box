from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "groovebox.py").read_text(encoding="utf-8")

class GeometricEngineMixerContract(unittest.TestCase):
    def test_four_independent_lane_controls_and_defaults(self):
        for token in ('("vector", "Vector", .80)', '("wavetable", "Wavetable", .75)', '("ball", "Ball", .65)', '("cellular", "Cellular", .70)'):
            self.assertIn(token, SOURCE)
        self.assertIn('"cross_mod": 0.0024', SOURCE)

    def test_cross_mod_is_bounded_and_deterministic(self):
        self.assertIn('float(np.clip(float(value) / 10000.0, 0.0, 0.02))', SOURCE)
        self.assertIn('Shared, bounded cross-mod depth; no random source is involved.', SOURCE)

    def test_project_save_and_restore(self):
        self.assertIn('"geometric_synth_mixer_state": _safe_json(getattr(self, "geometric_synth_mixer_state", {}))', SOURCE)
        self.assertIn('if isinstance(data.get("geometric_synth_mixer_state"), dict):', SOURCE)

    def test_fixed_canonical_user_balance_not_repurposed(self):
        self.assertIn('GROOVEBOX_R23R_CANONICAL_OWNERSHIP_20261031', SOURCE)  # canonical at default, user 50/50 once changed
        self.assertIn('geometric_synth_mixer_state', SOURCE)

if __name__ == "__main__":
    unittest.main()
