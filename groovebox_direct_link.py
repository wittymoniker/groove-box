#!/usr/bin/env python3
"""Router-free Groovebox proximity link helpers.

This module does *not* require Internet.  It provides a best-effort cross-platform
transport layer underneath nearby_groovebox.py:

1. Grooveboxes already sharing any reachable IPv4 network discover each other by
   UDP beacons (handled by nearby_groovebox.py).
2. With no common network, one Groovebox may explicitly create a temporary
   ``Groovebox-Direct-XXXXXXXX`` Wi-Fi hotspot.  Other Grooveboxes can scan for
   that SSID and join it.  After association, the exact same UDP + HTTP file API
   works over the self-hosted LAN.

Starting an AP is explicit because many single-radio adapters must disconnect
from their current Wi-Fi to become an access point.  Scanning is safe/read-only.
No received file is executed by this module.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from typing import List, Optional, Tuple

SSID_PREFIX = "Groovebox-Direct-"
PROFILE_NAME = "MathematiciansGrooveboxDirect"
SCAN_TIMEOUT = 7.0


def _run(cmd, timeout=12.0) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                          if os.name == "nt" else 0))
        return int(p.returncode), (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 127, str(e)


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def token_from_node(node_id: str) -> str:
    return hashlib.sha256(("MGB-DIRECT-V1:" + str(node_id)).encode()).hexdigest()[:8].upper()


def ssid_for_node(node_id: str) -> str:
    return SSID_PREFIX + token_from_node(node_id)


def password_for_ssid(ssid: str) -> str:
    """Protocol PSK for automatic Groovebox-to-Groovebox joining.

    This is transport privacy, not identity authentication: the application file
    service separately controls whether incoming writes are accepted.
    """
    token = str(ssid).split(SSID_PREFIX, 1)[-1]
    return hashlib.sha256(("MGB-DIRECT-PSK-V1:" + token).encode()).hexdigest()[:16]


@dataclass
class DirectCandidate:
    ssid: str
    signal: int = 0
    transport: str = "wifi-ap"
    seen: float = 0.0
    def as_dict(self): return asdict(self)


class DirectLinkManager:
    def __init__(self, node_id: str):
        self.node_id = str(node_id)
        self.ssid = ssid_for_node(self.node_id)
        self.password = password_for_ssid(self.ssid)
        self._started = False
        self._linux_connection = PROFILE_NAME + "-" + token_from_node(self.node_id)
        # Standalone appliance hardware selector exports the preferred radio.
        # Empty means let NetworkManager choose, preserving desktop behavior.
        self.wifi_iface = os.environ.get("GROOVEBOX_WIFI_IFACE", "").strip()

    def capabilities(self):
        sysname = platform.system().lower()
        scan = join = host = False
        reason = ""
        if sysname == "linux":
            scan = join = host = bool(_which("nmcli"))
            if not scan: reason = "NetworkManager nmcli is not installed."
        elif sysname == "windows":
            scan = join = bool(_which("netsh"))
            # Legacy hostednetwork remains the only dependency-free CLI path;
            # newer Windows hardware may report it unsupported.
            host = bool(_which("netsh"))
            if not host: reason = "Windows netsh is unavailable."
        elif sysname == "darwin":
            scan = bool(self._airport_binary())
            join = bool(_which("networksetup"))
            host = False
            reason = "macOS does not expose a stable unprivileged CLI for starting Internet Sharing; create a hotspot in System Settings, then Groovebox discovery works normally."
        else:
            reason = "Direct Wi-Fi control is not implemented for this OS; ordinary nearby discovery still works on any shared IP link."
        return {"platform": platform.system(), "scan": scan, "join": join, "host": host,
                "ssid": self.ssid, "reason": reason}

    @staticmethod
    def _airport_binary():
        candidates = [
            "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
            "/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport",
        ]
        return next((p for p in candidates if os.path.isfile(p) and os.access(p, os.X_OK)), None)

    def scan(self) -> List[dict]:
        sysname = platform.system().lower(); rows = {}
        if sysname == "linux" and _which("nmcli"):
            cmd = ["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"]
            if self.wifi_iface: cmd += ["ifname", self.wifi_iface]
            cmd += ["--rescan", "auto"]
            rc, out = _run(cmd, SCAN_TIMEOUT)
            if rc == 0:
                for line in out.splitlines():
                    # nmcli escapes ':' as '\:'; split on final colon because signal is numeric.
                    m = re.match(r"^(.*):([0-9]{1,3})$", line.strip())
                    if not m: continue
                    ssid = m.group(1).replace(r"\:", ":").strip()
                    if ssid.startswith(SSID_PREFIX): rows[ssid] = max(rows.get(ssid, 0), int(m.group(2)))
        elif sysname == "windows" and _which("netsh"):
            rc, out = _run(["netsh", "wlan", "show", "networks", "mode=bssid"], SCAN_TIMEOUT)
            if rc == 0:
                current = None
                for line in out.splitlines():
                    m = re.match(r"\s*SSID\s+\d+\s*:\s*(.*)$", line, re.I)
                    if m:
                        current = m.group(1).strip()
                        if current.startswith(SSID_PREFIX): rows.setdefault(current, 0)
                        else: current = None
                        continue
                    if current:
                        m = re.match(r"\s*Signal\s*:\s*(\d+)%", line, re.I)
                        if m: rows[current] = max(rows.get(current, 0), int(m.group(1)))
        elif sysname == "darwin":
            airport = self._airport_binary()
            if airport:
                rc, out = _run([airport, "-s"], SCAN_TIMEOUT)
                if rc == 0:
                    for line in out.splitlines()[1:]:
                        # SSID can contain spaces. Locate BSSID column (xx:xx:xx:xx:xx:xx),
                        # then parse RSSI immediately after it.
                        m = re.search(r"\s([0-9a-f]{2}:){5}[0-9a-f]{2}\s+(-?\d+)", line, re.I)
                        if not m: continue
                        ssid = line[:m.start()].strip()
                        if ssid.startswith(SSID_PREFIX):
                            rssi = int(m.group(2)); rows[ssid] = max(0, min(100, 2 * (rssi + 100)))
        now = time.time()
        return [DirectCandidate(k, v, seen=now).as_dict() for k, v in sorted(rows.items(), key=lambda kv:(-kv[1], kv[0]))]

    def join(self, ssid: str) -> Tuple[bool, str]:
        ssid = str(ssid).strip()
        if not ssid.startswith(SSID_PREFIX): return False, "Not a Groovebox Direct network."
        password = password_for_ssid(ssid); sysname = platform.system().lower()
        if sysname == "linux" and _which("nmcli"):
            cmd = ["nmcli", "device", "wifi", "connect", ssid, "password", password]
            if self.wifi_iface: cmd += ["ifname", self.wifi_iface]
            rc, out = _run(cmd, 25)
            return rc == 0, out.strip()
        if sysname == "windows" and _which("netsh"):
            # Create a temporary WPA2 profile; no shell interpolation.
            xml = f'''<?xml version="1.0"?><WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1"><name>{ssid}</name><SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig><connectionType>ESS</connectionType><connectionMode>auto</connectionMode><MSM><security><authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption><useOneX>false</useOneX></authEncryption><sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>{password}</keyMaterial></sharedKey></security></MSM></WLANProfile>'''
            path = None
            try:
                fd, path = tempfile.mkstemp(suffix=".xml", prefix="mgb-direct-"); os.close(fd)
                with open(path, "w", encoding="utf-8") as f: f.write(xml)
                rc1, out1 = _run(["netsh", "wlan", "add", "profile", f"filename={path}", "user=current"], 12)
                rc2, out2 = _run(["netsh", "wlan", "connect", f"name={ssid}", f"ssid={ssid}"], 15)
                return rc1 == 0 and rc2 == 0, (out1 + "\n" + out2).strip()
            finally:
                if path:
                    try: os.unlink(path)
                    except Exception: pass
        if sysname == "darwin" and _which("networksetup"):
            rc, out = _run(["networksetup", "-listallhardwareports"], 8)
            dev = None
            blocks = out.split("\n\n")
            for block in blocks:
                if "Wi-Fi" in block or "AirPort" in block:
                    m = re.search(r"Device:\s*(\S+)", block); dev = m.group(1) if m else None; break
            if not dev: return False, "Could not identify the macOS Wi-Fi device."
            rc, out = _run(["networksetup", "-setairportnetwork", dev, ssid, password], 25)
            return rc == 0, out.strip()
        return False, "This platform cannot join Direct Wi-Fi through the available command-line interface."

    def start_hotspot(self) -> Tuple[bool, str]:
        sysname = platform.system().lower()
        if sysname == "linux" and _which("nmcli"):
            # Let NetworkManager choose the Wi-Fi interface.  Explicit AP creation
            # may replace the current Wi-Fi association; UI warns before calling.
            _run(["nmcli", "connection", "delete", self._linux_connection], 5)
            cmd = ["nmcli", "device", "wifi", "hotspot"]
            if self.wifi_iface: cmd += ["ifname", self.wifi_iface]
            cmd += ["con-name", self._linux_connection, "ssid", self.ssid, "password", self.password]
            rc, out = _run(cmd, 30)
            self._started = rc == 0
            return self._started, out.strip()
        if sysname == "windows" and _which("netsh"):
            # Supported only on adapters/drivers that still expose hostednetwork.
            rc1, out1 = _run(["netsh", "wlan", "set", "hostednetwork", "mode=allow",
                              f"ssid={self.ssid}", f"key={self.password}", "keyUsage=persistent"], 12)
            rc2, out2 = _run(["netsh", "wlan", "start", "hostednetwork"], 15)
            self._started = rc1 == 0 and rc2 == 0
            return self._started, (out1 + "\n" + out2).strip()
        if sysname == "darwin":
            return False, "macOS requires creating Internet Sharing / Personal Hotspot in System Settings. Name it " + self.ssid + ". Groovebox will discover peers after association."
        return False, "Direct hotspot hosting is not available on this platform."

    def stop_hotspot(self) -> Tuple[bool, str]:
        sysname = platform.system().lower()
        if sysname == "linux" and _which("nmcli"):
            rc, out = _run(["nmcli", "connection", "down", self._linux_connection], 15)
            self._started = False
            return rc == 0, out.strip()
        if sysname == "windows" and _which("netsh"):
            rc, out = _run(["netsh", "wlan", "stop", "hostednetwork"], 12)
            self._started = False
            return rc == 0, out.strip()
        return False, "No Groovebox-managed hotspot is active on this platform."
