from pathlib import Path

ROOT = Path(__file__).resolve().parent
BI = ROOT / "BUILD_ISO"

def test_r23h_verifier_uses_72_percent_contract():
    verifier = (BI / "verify_v35_22zz_r23h.py").read_text()
    helper = (BI / "v35_22zz" / "sos-hardware-volume-v35_22zz_r23h").read_text()
    media = (BI / "sos-system-media-ready-v35_22zs").read_text()
    assert "helper defaults to 72 percent on first launch" in verifier
    assert "DEFAULT_VOLUME=72" in helper
    assert "BOOT_VOLUME=72" in media
    assert 'sos-hardware-volume init "${BOOT_VOLUME:-72}"' in media
    assert "DEFAULT_VOLUME=100" not in verifier

def test_pipewire_volume_init_is_after_sink_discovery():
    verifier = (BI / "verify_v35_22zz_r23h.py").read_text()
    media = (BI / "sos-system-media-ready-v35_22zs").read_text()
    assert "PipeWire post-start volume init at 72 percent" in verifier
    assert media.find('if [ "$REAL_SINKS" -gt 0 ]; then') < media.find('/usr/bin/sos-hardware-volume init "${BOOT_VOLUME:-72}"')

def test_router_verifier_matches_real_unmute_call_and_protects_capture():
    verifier = (BI / "verify_v35_22zz_r23h.py").read_text()
    router = (ROOT / "media_output_router.py").read_text()
    assert '\"sset\", name, \"unmute\"' in verifier
    assert 'qrun(["amixer", "-c", str(card), "sset", name, "unmute"], 1.0)' in router
    assert "0 <= raw_pct <= 100" in router
    assert "Capture controls are never changed" in router
    assert 'sset\",name,\"unmute\"' not in verifier

def test_r23j_saved_volume_assertion_uses_same_current_syntax():
    verifier = (BI / "verify_v35_22zz_r23j.py").read_text()
    assert '\"sset\", name, \"unmute\"' in verifier
    assert 'sset\",name,\"unmute\"' not in verifier
