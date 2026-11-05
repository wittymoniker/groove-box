import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "groovebox.py"

EXPECTED = {
    "chord_lattice", "interval_fan", "voice_leading_paths", "overtone_prisms", "harmonic_bridges", "consonance_fields",
    "particle_rivers", "depth_fold_volumes", "recursive_tunnels", "phase_vortices", "spatial_echoes", "deforming_surfaces",
    "polyrhythm_wheels", "recursive_step_mosaics", "euclidean_blooms", "phase_interference", "fractal_tessellations", "beat_contours",
    "dissolving_silhouettes", "spectral_wipes", "depth_crossfades", "motion_vector_blends", "feedback_trails", "canonical_scene_morphs",
}

class VisualElementsR2849Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_source_parses(self):
        ast.parse(self.text)

    def test_exactly_24_new_catalog_entries(self):
        self.assertIn('self.SCENOGRAPH_ITEM_CATALOG = self.SCENOGRAPH_ITEM_CATALOG[:88]', self.text)
        found = EXPECTED.intersection(set(self.text.split('self.SCENOGRAPH_ITEM_CATALOG = [', 1)[1].split(']', 1)[0].replace('"', '').replace("'", '').replace(',', ' ').split()))
        self.assertEqual(found, EXPECTED)
        self.assertEqual(len(EXPECTED), 24)

    def test_all_new_elements_have_deterministic_relevance_and_fade(self):
        for name in EXPECTED:
            self.assertIn(f'"{name}":', self.text)
        self.assertIn('delta = self._module_target[name] - old', self.text)
        self.assertIn('self._module_fade[name] = old + delta * rate', self.text)

    def test_renderer_is_called_in_shared_live_export_pipeline(self):
        self.assertIn('def _subscene_extended_24(self, img, w, h, st):', self.text)
        self.assertIn('self._subscene_extended_24, self._subscene_engine_ornaments', self.text)  # tier 3 of the tiered renderer
        self.assertIn('a = float(np.clip(self._module_fade.get(name, 0.0), 0.0, 1.0))', self.text)
        self.assertIn('if a < 0.012:', self.text)

if __name__ == "__main__":
    unittest.main()
