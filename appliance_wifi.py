#!/usr/bin/env python3
"""Standalone-appliance Wi-Fi hardware selection for Groovebox.

The appliance does not hardcode a chipset.  It inventories Linux wireless
interfaces through sysfs/iw/NetworkManager, prefers a spare AP-capable radio
for Groovebox Direct, and exports a stable interface choice for the nearby
share layer.  It never starts a hotspot on its own.
"""
from __future__ import annotations
import json, os, platform, shutil, subprocess, time
from pathlib import Path
from typing import Dict, List, Optional


def _run(argv, timeout=4):
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 127, str(exc)


def _state_path() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "groovebox" / "appliance_wifi.json"


def _driver_for(iface: str) -> str:
    p = Path("/sys/class/net") / iface / "device" / "driver"
    try:
        return p.resolve().name
    except Exception:
        return ""


def _phy_for(iface: str) -> str:
    p = Path("/sys/class/net") / iface / "phy80211"
    try:
        return p.resolve().name
    except Exception:
        return ""


def _wireless_ifaces() -> List[str]:
    out = set()
    root = Path("/sys/class/net")
    if root.exists():
        for p in root.iterdir():
            if (p / "wireless").exists() or (p / "phy80211").exists():
                out.add(p.name)
    if shutil.which("iw"):
        rc, text = _run(["iw", "dev"])
        if rc == 0:
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("Interface "):
                    out.add(line.split(None, 1)[1].strip())
    return sorted(out)


def _nm_states() -> Dict[str, str]:
    states: Dict[str, str] = {}
    if not shutil.which("nmcli"):
        return states
    rc, text = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
    if rc == 0:
        for line in text.splitlines():
            parts = line.replace(r"\:", "\0").split(":")
            if len(parts) >= 3:
                dev = parts[0].replace("\0", ":")
                typ = parts[1].replace("\0", ":")
                state = ":".join(parts[2:]).replace("\0", ":")
                if typ == "wifi":
                    states[dev] = state
    return states


def _supports_ap(iface: str) -> bool:
    if not shutil.which("iw"):
        # NetworkManager will perform the authoritative check when hotspot starts.
        return False
    phy = _phy_for(iface)
    if not phy:
        return False
    rc, text = _run(["iw", "phy", phy, "info"], timeout=5)
    if rc != 0:
        return False
    in_modes = False
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("Supported interface modes:"):
            in_modes = True
            continue
        if in_modes:
            if s.startswith("*"):
                if s[1:].strip() == "AP":
                    return True
            elif s and not raw.startswith(("\t", " ")):
                break
    return False


def _hardware_fingerprint(rows: List[dict]) -> str:
    return "|".join(f"{r['iface']}:{r.get('driver','')}:{r.get('phy','')}" for r in rows)


def inventory() -> dict:
    states = _nm_states()
    rows = []
    for iface in _wireless_ifaces():
        state = states.get(iface, "unknown")
        rows.append({
            "iface": iface,
            "driver": _driver_for(iface),
            "phy": _phy_for(iface),
            "state": state,
            "connected": state.startswith("connected"),
            "ap_capable": _supports_ap(iface),
        })
    return {"platform": platform.system(), "interfaces": rows,
            "fingerprint": _hardware_fingerprint(rows)}


def choose_interfaces(info: Optional[dict] = None) -> dict:
    info = info or inventory()
    rows = list(info.get("interfaces") or [])
    connected = [r for r in rows if r.get("connected")]

    def client_score(r):
        return (100 if r.get("connected") else 0) + (10 if r.get("state") not in ("unavailable", "unmanaged") else -100)

    def direct_score(r):
        # Prefer a spare AP-capable adapter so Direct mode need not disturb the
        # user's ordinary Wi-Fi.  If there is only one radio, use it only after
        # the explicit Start Direct Wi-Fi action in the UI.
        spare = bool(connected) and not r.get("connected")
        return (300 if spare and r.get("ap_capable") else 0) + \
               (200 if r.get("ap_capable") else 0) + \
               (20 if not r.get("connected") else 0) + \
               (5 if r.get("state") not in ("unavailable", "unmanaged") else -100)

    client = max(rows, key=client_score)["iface"] if rows else ""
    direct = max(rows, key=direct_score)["iface"] if rows else ""
    selected = next((r for r in rows if r["iface"] == direct), {})
    return {
        **info,
        "preferred_client_iface": client,
        "preferred_direct_iface": direct,
        "direct_ap_capable": bool(selected.get("ap_capable")),
        "single_radio": len(rows) == 1,
        "dedicated_direct_radio": bool(direct and client and direct != client),
    }


def _enable_linux_network_stack(rows: List[dict]) -> List[str]:
    notes = []
    if platform.system().lower() != "linux":
        return notes
    # These are idempotent and intentionally do not associate to a network or
    # create a hotspot.  Privileged actions are attempted only as root.
    if os.geteuid() == 0 and shutil.which("systemctl"):
        rc, out = _run(["systemctl", "enable", "--now", "NetworkManager"], timeout=12)
        notes.append("NetworkManager enabled" if rc == 0 else "NetworkManager enable skipped: " + out.strip()[:160])
    if shutil.which("rfkill"):
        rc, _ = _run(["rfkill", "unblock", "wifi"])
        if rc == 0: notes.append("Wi-Fi rfkill unblocked")
    if shutil.which("nmcli"):
        _run(["nmcli", "radio", "wifi", "on"])
        for row in rows:
            iface = row.get("iface")
            if iface:
                # A normal user may be allowed by NetworkManager/Polkit. Failure
                # is harmless; do not prompt or block appliance boot.
                _run(["nmcli", "device", "set", iface, "managed", "yes"])
    return notes


def configure_appliance(force: bool = False) -> dict:
    info = choose_interfaces()
    notes = _enable_linux_network_stack(info.get("interfaces") or [])
    info["notes"] = notes
    info["configured_at"] = int(time.time())
    p = _state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(info, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        info.setdefault("notes", []).append("Could not persist Wi-Fi inventory: " + str(exc))
    iface = info.get("preferred_direct_iface") or info.get("preferred_client_iface") or ""
    if iface:
        os.environ["GROOVEBOX_WIFI_IFACE"] = iface
    return info


def is_appliance_profile() -> bool:
    profile = os.environ.get("GROOVEBOX_PROFILE", "").strip().lower()
    return profile in {"sos", "appliance", "standalone", "tablet"} or \
           os.environ.get("GROOVEBOX_APPLIANCE", "") == "1" or \
           Path("/etc/groovebox-appliance").exists()


def prepare_if_appliance() -> dict:
    if not is_appliance_profile() or platform.system().lower() != "linux":
        return {}
    return configure_appliance()


if __name__ == "__main__":
    print(json.dumps(configure_appliance(force=True), indent=2, sort_keys=True))
