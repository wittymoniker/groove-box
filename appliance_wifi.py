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


def _wireless_ifaces(nm_wifi=None) -> List[str]:
    out = set()
    root = Path("/sys/class/net")
    if root.exists():
        for p in root.iterdir():
            if (p / "wireless").exists() or (p / "phy80211").exists():
                out.add(p.name)
    if __import__("sos_tools").which("iw"):
        rc, text = _run(["iw", "dev"])
        if rc == 0:
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("Interface "):
                    out.add(line.split(None, 1)[1].strip())
    # NetworkManager is an independent source of device type.  Include only
    # rows it explicitly identifies as Wi-Fi; never infer wireless from the
    # default route, the first device, or an Ethernet connection.
    try:
        out.update((nm_wifi if nm_wifi is not None else _nm_states()).keys())
    except Exception:
        pass
    return sorted(name for name in out if name and name.lower() not in {"lo", "loopback"})


def _nm_states() -> Dict[str, str]:
    states: Dict[str, str] = {}
    if not __import__("sos_tools").which("nmcli"):
        return states
    rc, text = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
    if rc != 0:
        return states
    # Prefer the shared escaped-terse parser when available; fall back locally.
    try:
        split = __import__("network_manager_utils").split_terse_record
    except Exception:
        def split(line: str):
            fields, current, escaped = [], [], False
            for char in str(line):
                if escaped:
                    current.append(char); escaped = False
                elif char == "\\":
                    escaped = True
                elif char == ":":
                    fields.append("".join(current)); current = []
                else:
                    current.append(char)
            if escaped:
                current.append("\\")
            fields.append("".join(current))
            return fields
    for line in text.splitlines():
        fields = split(line)
        if len(fields) >= 3 and fields[1].strip().lower() in {"wifi", "802-11-wireless"}:
            device = fields[0].strip()
            if device and device.lower() not in {"lo", "loopback"}:
                states[device] = fields[2]
    return states


def _supports_ap(iface: str) -> bool:
    if not __import__("sos_tools").which("iw"):
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
    for iface in _wireless_ifaces(states):
        state = states.get(iface, "unknown")
        rows.append({
            "iface": iface,
            "type": "wifi",
            "driver": _driver_for(iface),
            "phy": _phy_for(iface),
            "state": state,
            "connected": state.startswith("connected"),
            "ap_capable": _supports_ap(iface),
        })
    return {"platform": platform.system(), "interfaces": rows,
            "fingerprint": _hardware_fingerprint(rows)}


def _state_usable(state: str) -> bool:
    """NetworkManager states that can accept a connection activation request."""
    value = str(state or "unknown").strip().lower()
    return value not in {"unknown", "unavailable", "unmanaged", "unavailable (firmware missing)"}


def choose_interfaces(info: Optional[dict] = None) -> dict:
    """Choose only radios NetworkManager can currently manage.

    A sysfs/iw-visible interface is not necessarily an activatable NM device.
    In particular, selecting an `unavailable` radio and exporting it as a fixed
    GROOVEBOX_WIFI_IFACE makes both hotspot and IBSS activation fail before NM
    can try another usable adapter.
    """
    info = info or inventory()
    rows = list(info.get("interfaces") or [])
    # Inventory is Wi-Fi-only, but keep this boundary defensive: injected,
    # cached, or older inventory rows marked Ethernet must never be selected.
    rows = [r for r in rows
            if str(r.get("type", r.get("nm_type", "wifi"))).strip().lower()
            in {"wifi", "802-11-wireless"}
            and str(r.get("iface", "")).strip().lower() not in {"", "lo", "loopback"}]
    usable = [r for r in rows if _state_usable(r.get("state", "unknown"))]
    connected = [r for r in usable if r.get("connected")]

    def client_score(r):
        return (100 if r.get("connected") else 0) + (10 if r.get("state") != "unknown" else 0)

    def direct_score(r):
        spare = bool(connected) and not r.get("connected")
        return (300 if spare and r.get("ap_capable") else 0) + \
               (200 if r.get("ap_capable") else 0) + \
               (20 if not r.get("connected") else 0) + \
               (5 if r.get("state") != "unknown" else 0)

    client = max(usable, key=client_score)["iface"] if usable else ""
    direct = max(usable, key=direct_score)["iface"] if usable else ""
    selected = next((r for r in usable if r["iface"] == direct), {})
    return {
        **info,
        "preferred_client_iface": client,
        "preferred_direct_iface": direct,
        "direct_ap_capable": bool(selected.get("ap_capable")),
        "single_radio": len(usable) == 1,
        "dedicated_direct_radio": bool(direct and client and direct != client),
        "unusable_interfaces": [
            {"iface": r.get("iface", ""), "state": r.get("state", "unknown")}
            for r in rows if not _state_usable(r.get("state", "unknown"))
        ],
    }


def _enable_linux_network_stack(rows: List[dict]) -> List[str]:
    notes = []
    if platform.system().lower() != "linux":
        return notes
    # These are idempotent and intentionally do not associate to a network or
    # create a hotspot.  Privileged actions are attempted only as root.
    if os.geteuid() == 0 and __import__("sos_tools").which("systemctl"):
        rc, out = _run(["systemctl", "enable", "--now", "NetworkManager"], timeout=12)
        notes.append("NetworkManager enabled" if rc == 0 else "NetworkManager enable skipped: " + out.strip()[:160])
    if __import__("sos_tools").which("rfkill"):
        rc, _ = _run(["rfkill", "unblock", "wifi"])
        if rc == 0: notes.append("Wi-Fi rfkill unblocked")
    if __import__("sos_tools").which("nmcli"):
        _run(["nmcli", "radio", "wifi", "on"])
        for row in rows:
            iface = row.get("iface")
            if iface:
                # A normal user may be allowed by NetworkManager/Polkit. Failure
                # is harmless; do not prompt or block appliance boot.
                _run(["nmcli", "device", "set", iface, "managed", "yes"])
    return notes


def refresh_inventory(enable_stack: bool = True) -> dict:
    """Refresh NetworkManager/radio state after bringing Wi-Fi online."""
    notes = []
    initial = inventory()
    if enable_stack:
        notes.extend(_enable_linux_network_stack(initial.get("interfaces") or []))
        # Deep recovery: pull radios out of unavailable/unmanaged before selection.
        try:
            from network_manager_utils import prepare_wifi_for_activation
            iface, diag, prep_notes = prepare_wifi_for_activation(timeout=10.0)
            notes.extend(prep_notes or [])
            if iface:
                notes.append(f"prepared {iface}")
            elif diag:
                notes.append(diag)
        except Exception as exc:
            notes.append(f"prepare_wifi_for_activation: {exc}")
        # NM can take a short moment to publish devices after radio enable/unblock.
        for delay in (0.25, 0.5, 0.75, 1.0):
            time.sleep(delay)
            latest = inventory()
            if any(_state_usable(r.get("state")) for r in latest.get("interfaces", [])):
                initial = latest
                break
            initial = latest
    selected = choose_interfaces(initial)
    selected["notes"] = notes
    return selected


def configure_appliance(force: bool = False, enable_stack: bool = True) -> dict:
    # Enable/unblock first, then inventory again.  The previous order selected
    # an interface while NM still reported it unavailable and pinned that stale
    # choice into GROOVEBOX_WIFI_IFACE for the whole application session.
    info = refresh_inventory(enable_stack=bool(enable_stack))
    info["configured_at"] = int(time.time())
    p = _state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        __import__("safe_io").atomic_write_text(p, json.dumps(info, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        info.setdefault("notes", []).append("Could not persist Wi-Fi inventory: " + str(exc))
    iface = info.get("preferred_direct_iface") or info.get("preferred_client_iface") or ""
    if iface:
        os.environ["GROOVEBOX_WIFI_IFACE"] = iface
    else:
        # Never retain a stale device choice when all radios are unavailable.
        os.environ.pop("GROOVEBOX_WIFI_IFACE", None)
    return info


def is_appliance_profile() -> bool:
    profile = os.environ.get("GROOVEBOX_PROFILE", "").strip().lower()
    return profile in {"sos", "appliance", "standalone", "tablet"} or \
           os.environ.get("GROOVEBOX_APPLIANCE", "") == "1" or \
           Path("/etc/groovebox-appliance").exists()


def prepare_if_appliance(enable_stack: bool = False) -> dict:
    # R137: boot default is read-only (no rfkill / radio cycle / disconnect).
    if not is_appliance_profile() or platform.system().lower() != "linux":
        return {}
    if os.environ.get("GROOVEBOX_NETWORK_AUTOSTART", "") == "1":
        enable_stack = True
    return configure_appliance(enable_stack=enable_stack)


if __name__ == "__main__":
    print(json.dumps(configure_appliance(force=True), indent=2, sort_keys=True))
