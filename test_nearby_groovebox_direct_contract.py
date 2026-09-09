from pathlib import Path
import tempfile

from groovebox_direct_link import SSID_PREFIX, ssid_for_node, password_for_ssid, DirectLinkManager
from nearby_groovebox import NearbyGrooveboxService, classify_destination


def test_direct_ssid_and_psk_are_deterministic_and_valid():
    ssid = ssid_for_node("node-123")
    assert ssid.startswith(SSID_PREFIX)
    assert ssid == ssid_for_node("node-123")
    psk = password_for_ssid(ssid)
    assert len(psk) >= 8
    assert psk == password_for_ssid(ssid)


def test_destination_classification():
    assert classify_destination("song.wav") == "samples"
    assert classify_destination("set.mgpr") == "projects"
    assert classify_destination("code.sC") == "modules"


def test_presence_info_does_not_force_catalog_walk():
    with tempfile.TemporaryDirectory() as td:
        svc = NearbyGrooveboxService(td)
        called = []
        svc.catalog = lambda: called.append(True) or []
        info = svc.info()
        assert info["magic"]
        assert not called, "2-second presence beacon must never walk the file catalog"
        assert "router-free-direct" in info["capabilities"]


def test_incoming_is_disabled_by_default():
    with tempfile.TemporaryDirectory() as td:
        svc = NearbyGrooveboxService(td)
        assert svc.allow_incoming is False
        assert svc.set_incoming_enabled(True) is True
        assert svc.allow_incoming is True


def test_runtime_and_ui_are_integrated():
    root = Path(__file__).resolve().parent
    gb = (root / "groovebox.py").read_text(encoding="utf-8")
    perf = (root / "performance.py").read_text(encoding="utf-8")
    near = (root / "nearby_groovebox.py").read_text(encoding="utf-8")
    assert "self._nearby_share_service.start()" in gb
    assert "_nearby_share_service" in gb and "_nearby.stop()" in gb
    assert "Nearby Grooveboxes · router-free Wi-Fi Share" in perf
    assert "Start Direct Wi-Fi" in perf and "Browse Selected Groovebox" in perf
    assert '"catalog_id":self._catalog_id' in near


def test_no_new_python_network_dependency():
    # Direct link must work through stdlib + OS network tools; no zeroconf package
    # is required for the appliance/offline build.
    text = (Path(__file__).resolve().parent / "groovebox_direct_link.py").read_text(encoding="utf-8")
    assert "import zeroconf" not in text
    assert "requests" not in text
