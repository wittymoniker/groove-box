import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class CanonicalSeedAudioUIContract(unittest.TestCase):
 def test_seed_handles(self):
  s=(ROOT/"groovebox.py").read_text()
  for token in ("vector_x", "wavetable_phase", "ball_gravity", "cell_width", "sidechain_depth", "eq_poles", "goava_canonical_amplitude"):
   self.assertIn('"'+token+'"',s)
 def test_spatial_controls(self):
  s=(ROOT/"groovebox.py").read_text()
  for token in ("spin_ball_", "spin_ca_", "combo_ca_neighborhood", "ball_synth_params", "cellular_synth_params"):
   self.assertIn(token,s)
 def test_audio_guard_and_master_sync(self):
  s=(ROOT/"groovebox.py").read_text()
  self.assertIn("np.nan_to_num(arr",s)
  self.assertIn("self.master_volume = val / 100.0",s)
  self.assertIn("performanceMasterVolumeSlider",s)
 def test_help_guide(self):
  s=(ROOT/"README-HELP-R28.4.35.md").read_text()
  self.assertIn("Seed Script canonical variable handles",s)
  self.assertIn("0.19758",s)
if __name__=="__main__": unittest.main()
