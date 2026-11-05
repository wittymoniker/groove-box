from pathlib import Path
ROOT = Path(__file__).resolve().parent
def test_project_reset_sets_master_to_72_through_shared_handler():
    src = (ROOT / "groovebox.py").read_text(errors="ignore")
    start = src.index("    def _clear_project_memory(self):")
    end = src.index("    # ------------------------------------------------------------------\n    # FINITE_INFINITY_MEUM_HYPERDRIVE_2026", start)
    reset = src[start:end]
    assert "self._on_master_vol_changed(72)" in reset
    assert "self.master_volume = 0.72" in reset
def test_master_volume_handler_mirrors_main_bridge_and_performance():
    src = (ROOT / "groovebox.py").read_text(errors="ignore")
    start = src.index("    def _on_master_vol_changed(self, val):")
    end = src.index("    def _on_clip_ratio_changed(self, val):", start)
    handler = src[start:end]
    assert 'main_slider = getattr(self, "slider_master_vol", None)' in handler
    assert "performanceMasterVolumeSlider" in handler
    assert "lbl_master_vol" in handler and "lbl_master_volume" in handler
