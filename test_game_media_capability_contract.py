"""Regression tests for audio/video-to-game generation contracts."""
import json
import os
import tempfile
import unittest
from videogame_engine import (
    classify_from_composition, export_game_files, build_game_media_capability_contract
)

class GameMediaCapabilityContractTests(unittest.TestCase):
    def test_contract_covers_media_to_game_paths(self):
        c = build_game_media_capability_contract(42, {"bpm": 120})
        self.assertTrue(c["deterministic"])
        self.assertTrue(c["interaction"]["audio_to_visual"] and c["interaction"]["visual_to_audio"])
        self.assertTrue(c["interaction"]["game_event_to_audio_visual"])
        self.assertTrue({"rms", "onset", "pitch", "chord_intervals"}.issubset(c["audio"]["analysis_channels"]))
        self.assertTrue({"rgb24", "rgba32", "motion_vectors", "masks"}.issubset(set(c["video"]["frame_outputs"] + c["video"]["visual_channels"])))
        self.assertTrue({"ui_components", "sprites", "meshes", "materials", "objects", "environments"}.issubset(c["game_objects"]["supports"]))
        self.assertFalse(c["data_protection"]["source_project_mutated"])
        self.assertFalse(c["interaction"]["random_probability"])

    def test_export_writes_media_contract(self):
        with tempfile.TemporaryDirectory(prefix="gb_media_contract_") as d:
            identity = classify_from_composition(seed=43, bpm=100, seq_length=16, playlist_rows=8, n_instruments=4)
            export_game_files(identity, d, {"bpm": 100})
            p = os.path.join(d, "game_media_capabilities.json")
            self.assertTrue(os.path.isfile(p))
            with open(p, encoding="utf-8") as f:
                obj = json.load(f)
            self.assertEqual(obj["schema"], "groovebox.game-media-bridge.v1")
            self.assertEqual(obj["composition_fingerprint"], identity.composition_fingerprint)

if __name__ == "__main__":
    unittest.main(verbosity=2)
