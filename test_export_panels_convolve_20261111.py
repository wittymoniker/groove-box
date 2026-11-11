from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_main_window_fx_panels_cannot_be_collapsed():
    source = (ROOT / "fx_panels.py").read_text(encoding="utf-8")
    start = source.index("def make_collapsible(")
    block = source[start:]
    assert "setCheckable(False)" in block
    assert "setChecked(True)" in block
    assert "box.toggled.connect" not in block
    assert "setVisible(bool(on))" not in block


def test_audio_export_setup_is_reentrancy_guarded():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    start = source.index("    def export_mixdown_dialog(self, audio_format=\"wav\"):")
    block = source[start:start + 2400]
    assert "_audio_export_dialog_active" in block
    assert "_export_mixdown_dialog_impl" in block
    assert "finally:" in block


def test_global_convolve_pipeline_remains_connected():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert "self.spin_global_convolve" in source
    assert "self._global_convolve_kernel(klen, sample_rate, gf)" in source
    assert "_native_convolve_ola_f32(master, kernel, _rust_block)" in source
    assert "[Global Convolve] skipped" in source


def test_folder_dialog_does_not_probe_removable_devices_synchronously():
    source = (ROOT / "drive_targets.py").read_text(encoding="utf-8")
    start = source.index("    def build(parent, caption, directory, filt, initial_filter, options, mode, accept):")
    end = source.index("\n    def _args", start)
    block = source[start:end]
    assert "removable_drives()" not in block
    assert "mount_places()" in block
