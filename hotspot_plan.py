"""GROOVEBOX_HOTSPOT_TOGGLE_20261102: what starting the device hotspot would disturb (never starts anything)."""
from __future__ import annotations
import platform, shutil
from appliance_wifi import _run, choose_interfaces


def hotspot_plan() -> dict:
    """GROOVEBOX_HOTSPOT_TOGGLE_20261102: what starting the device hotspot would disturb.

    ``cancels`` lists active Wi-Fi activity that a hotspot on this radio would interrupt (empty when a
    spare AP-capable radio exists or nothing is connected). ``iface`` is the radio to use ('' = let
    NetworkManager choose). Never starts anything.
    """
    plan = {"supported": False, "iface": "", "cancels": [], "reason": ""}
    if platform.system().lower() != "linux" or not shutil.which("nmcli"):
        plan["reason"] = "The device hotspot needs Linux with NetworkManager (nmcli)."
        return plan
    plan["supported"] = True
    try:
        info = choose_interfaces()
    except Exception:
        info = {"interfaces": []}
    rows = list(info.get("interfaces") or [])
    if not rows:
        plan["supported"] = False
        plan["reason"] = "No Wi-Fi radio was found."
        return plan
    direct = str(info.get("preferred_direct_iface") or "")
    target = next((r for r in rows if r.get("iface") == direct), rows[0])
    plan["iface"] = str(target.get("iface") or "")
    if target.get("connected"):
        names = []
        rc, text = _run(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])
        if rc == 0:
            for line in text.splitlines():
                parts = line.replace(r"\:", "\0").split(":")
                if len(parts) >= 3 and parts[2].replace("\0", ":") == plan["iface"] and "wireless" in parts[1]:
                    names.append(parts[0].replace("\0", ":"))
        plan["cancels"] = [f"Wi-Fi connection {n!r} on {plan['iface']}" for n in names] or \
                          [f"the current Wi-Fi connection on {plan['iface']}"]
    return plan
