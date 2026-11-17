from pathlib import Path
import instrument_designer as designer

ROOT = Path(__file__).resolve().parent


def test_instrument_templates_cover_percussion_pad_keys_and_macro_bounds():
    assert set(designer.TEMPLATES) == {"Percussion", "Pad", "Keys"}
    for kind in designer.TEMPLATES:
        state = designer.macro_state(kind, 0.5, 0.5, 0.5)
        assert 1 <= state["engine"]["unison"] <= 7
        assert 0 <= state["engine"]["fold"] <= 1
        assert state["fm_depth"] >= 0


def test_sequence_fill_writes_consistent_user_sequence_lanes():
    mem = designer.fill_sequence({}, "Arpeggio", steps=24, pulses=6, note=60, seed=2)
    assert len(mem["steps"]) == len(mem["gates"]) == len(mem["amplitudes"]) == 24
    assert len(mem["pitches"]) == len(mem["probabilities"]) == 24
    assert sum(mem["steps"]) == 24
    assert mem["sequence_length_user_owned"] is True
    assert mem["instrument_designer"]["generated"] is True


def test_visualizer_no_longer_renders_audio_voice_for_panel_ring():
    src = (ROOT / "multidim_ui.py").read_text(encoding="utf-8")
    block = src.split("def _refresh_panel_wave(self):", 1)[1].split("def _host_state(self):", 1)[0]
    assert "_audition_voice" not in block
    assert "instrument_param_state" in block
    assert "synth_engine_panel" in block


def test_main_launcher_places_performance_before_patch_motion_and_has_designer():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    perf = src.index('_logo_perf_stack.addWidget(self.btn_media_hub')
    patch = src.index('_logo_perf_stack.addWidget(self.btn_patch_motion')
    designer = src.index('_logo_perf_stack.addWidget(self.btn_instrument_designer')
    assert perf < patch < designer
    assert "def _open_instrument_designer(self):" in src


def test_ssd_installer_copies_separate_usb_work_assets():
    src = (ROOT / "BUILD_ISO" / "sos-install-appliance-limine-v33a").read_text(encoding="utf-8")
    assert "GROOVEBOX_R79_COPY_USB_WORK_BOOT_ASSETS_20261116" in src
    assert 'cp -a /work/. "$MNT/work/"' in src
    assert "INSTALL_WORK_ASSETS|PASS" in src
