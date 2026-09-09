from pathlib import Path
from appliance_wifi import choose_interfaces


def test_prefers_spare_ap_radio_for_direct_link():
    info={"platform":"Linux","fingerprint":"x","interfaces":[
        {"iface":"wlan0","driver":"iwlwifi","phy":"phy0","state":"connected","connected":True,"ap_capable":True},
        {"iface":"wlan1","driver":"rtl8xxxu","phy":"phy1","state":"disconnected","connected":False,"ap_capable":True},
    ]}
    out=choose_interfaces(info)
    assert out["preferred_client_iface"] == "wlan0"
    assert out["preferred_direct_iface"] == "wlan1"
    assert out["dedicated_direct_radio"] is True


def test_single_radio_is_selected_but_never_auto_hotspotted():
    info={"platform":"Linux","fingerprint":"x","interfaces":[
        {"iface":"wlp2s0","driver":"iwlwifi","phy":"phy0","state":"connected","connected":True,"ap_capable":True},
    ]}
    out=choose_interfaces(info)
    assert out["preferred_direct_iface"] == "wlp2s0"
    assert out["single_radio"] is True
    src=(Path(__file__).resolve().parent/'appliance_wifi.py').read_text(encoding='utf-8')
    assert 'hotspot' not in src.lower().split('def configure_appliance',1)[1], 'first boot must not silently start a hotspot'


def test_direct_manager_respects_appliance_interface():
    src=(Path(__file__).resolve().parent/'groovebox_direct_link.py').read_text(encoding='utf-8')
    assert 'GROOVEBOX_WIFI_IFACE' in src
    assert '["ifname", self.wifi_iface]' in src


def test_sos_launcher_sets_appliance_profile():
    root=Path(__file__).resolve().parent
    assert 'GROOVEBOX_PROFILE=sos' in (root/'LAUNCH_GROOVEBOX_SOS.sh').read_text(encoding='utf-8')
    run=(root/'run_groovebox.py').read_text(encoding='utf-8')
    assert 'prepare_if_appliance' in run
