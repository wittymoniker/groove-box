from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_hardware_volume_widget_has_no_mute_button():
    for rel in ("hardware_volume.py", "BUILD_ISO/app-overlay-v35.22zz/hardware_volume.py", "BUILD_ISO/app-overlay-v35.22zt/hardware_volume.py"):
        src=(ROOT/rel).read_text(errors="ignore")
        assert "QPushButton" not in src
        assert "self.mute" not in src
        assert "toggle-mute" not in src

def test_playback_route_ignores_stale_mute_flag():
    router=(ROOT/"media_output_router.py").read_text(errors="ignore")
    assert "stale UI/helper mute flag" in router
    assert '\"unmute\"' in router
    helper=(ROOT/"BUILD_ISO/v35_22zz/sos-hardware-volume-v35_22zz_r23h").read_text(errors="ignore")
    assert "mute=0" in helper
    assert 'mirror_session "$pct" 0' in helper
