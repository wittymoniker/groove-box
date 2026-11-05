from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_hardware_volume_defaults_to_full_level_only_when_state_is_missing():
    ui = (ROOT / 'hardware_volume.py').read_text(errors='ignore')
    helper = (ROOT / 'BUILD_ISO/v35_22zz/sos-hardware-volume-v35_22zz_r23h').read_text(errors='ignore')
    router = (ROOT / 'media_output_router.py').read_text(errors='ignore')
    assert "state={'volume':72,'muted':False,'card':'','control':''}" in ui
    assert "self.value_label=QLabel('72%')" in ui
    assert 'DEFAULT_VOLUME=72' in helper
    assert 'stale UI/helper mute flag' in router and '"unmute"' in router

def test_performance_has_no_duplicate_hardware_volume_slider():
    src = (ROOT / 'performance.py').read_text(errors='ignore')
    assert 'self.hardware_volume_performance = None' in src
    assert 'HardwareVolumeWidget(self, compact=False)' not in src
    main = (ROOT / 'groovebox.py').read_text(errors='ignore')
    assert 'self.hardware_volume_main = HardwareVolumeWidget(self, compact=True)' in main
