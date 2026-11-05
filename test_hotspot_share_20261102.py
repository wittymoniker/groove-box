import json
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import hotspot_plan as appliance_wifi
import nearby_groovebox as nb


def _svc(tmp):
    root = Path(tmp)
    (root / "projects").mkdir(parents=True, exist_ok=True)
    (root / "projects" / "My <Song>.mcc").write_bytes(b"data123")
    svc = nb.NearbyGrooveboxService(str(root))
    return svc


def test_html_browser_lists_escapes_and_links_only_catalog_files():
    rows = [{"category": "projects", "path": "My <Song>.mcc", "name": "x", "size": 2048},
            {"category": "samples", "path": "a/b.wav", "name": "b.wav", "size": 10}]
    page = nb.render_browse_html(rows, "Gb <1>").decode()
    assert "My &lt;Song&gt;.mcc" in page and "<Song>" not in page
    assert "Gb &lt;1&gt;" in page
    assert "/api/v1/file?category=projects&path=My%20%3CSong%3E.mcc" in page
    assert "2.0 KB" in page
    assert "category=samples" in page


def test_browser_is_off_until_the_hotspot_enables_it_and_serves_downloads():
    with tempfile.TemporaryDirectory() as tmp:
        svc = _svc(tmp)
        try:
            svc.start()
            base = f"http://127.0.0.1:{svc.port}"
            body = urllib.request.urlopen(base + "/", timeout=5).read().decode()
            assert "Nearby Share is running" in body            # default: no file browser
            svc.set_web_browse(True)
            body = urllib.request.urlopen(base + "/", timeout=5).read().decode()
            assert "<table>" in body and "My &lt;Song&gt;.mcc" in body
            data = urllib.request.urlopen(base + "/api/v1/file?category=projects&path=My%20%3CSong%3E.mcc", timeout=5).read()
            assert data == b"data123"
            for bad in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd"):
                try:
                    urllib.request.urlopen(base + f"/api/v1/file?category=projects&path={bad}", timeout=5)
                    assert False, "traversal must fail"
                except urllib.error.HTTPError as e:
                    assert e.code == 404
            svc.set_web_browse(False)
            body = urllib.request.urlopen(base + "/", timeout=5).read().decode()
            assert "Nearby Share is running" in body
        finally:
            svc.stop()


def test_hotspot_plan_names_what_would_be_cancelled(monkeypatch):
    monkeypatch.setattr(appliance_wifi.platform, "system", lambda: "Linux")
    monkeypatch.setattr(appliance_wifi.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(appliance_wifi, "choose_interfaces", lambda info=None: {
        "interfaces": [{"iface": "wlan0", "connected": True, "ap_capable": True}], "preferred_direct_iface": "wlan0"})
    monkeypatch.setattr(appliance_wifi, "_run", lambda argv, timeout=4: (0, "HomeNet:802-11-wireless:wlan0\nEth:802-3-ethernet:eth0\n"))
    plan = appliance_wifi.hotspot_plan()
    assert plan["supported"] and plan["iface"] == "wlan0"
    assert len(plan["cancels"]) == 1 and "HomeNet" in plan["cancels"][0]
    monkeypatch.setattr(appliance_wifi, "choose_interfaces", lambda info=None: {
        "interfaces": [{"iface": "wlan1", "connected": False, "ap_capable": True}], "preferred_direct_iface": "wlan1"})
    assert appliance_wifi.hotspot_plan()["cancels"] == []        # nothing active: no prompt needed
    monkeypatch.setattr(appliance_wifi.shutil, "which", lambda n: None)
    assert appliance_wifi.hotspot_plan()["supported"] is False


def test_performance_toggle_is_wired():
    src = open("performance.py", encoding="utf-8").read()
    assert "btn_hotspot_share" in src and "_on_hotspot_share_toggled" in src
    assert "will cancel active Wi-Fi activity" in src
    assert "set_web_browse(True)" in src and "set_web_browse(False)" in src
