"""sensor_bus.py — IIO / thermal / Wi-Fi RSSI / battery → float streams (off GUI thread)."""
from __future__ import annotations
import os, glob, threading
from typing import Dict, List
try:
    import numpy as np
except Exception:
    np = None

from hardware_source import Source, register

def _read_float(path: str, default=0.0) -> float:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return float(f.read().strip().split()[0])
    except Exception:
        return float(default)

class IIOSource(Source):
    name = "iio"
    privacy = "motion"
    def enumerate(self) -> List[dict]:
        found = []
        for base in glob.glob("/sys/bus/iio/devices/iio:device*"):
            name = os.path.basename(base)
            axes = []
            for p in glob.glob(base + "/*_raw") + glob.glob(base + "/*_input"):
                axes.append(os.path.basename(p))
            if axes:
                found.append({"id": base, "name": name, "axes": axes[:16]})
        return found
    def read(self, n: int = 32):
        devs = self.enumerate()
        if not devs or np is None:
            return None
        rows = []
        for d in devs[:4]:
            vals = []
            for ax in d.get("axes", [])[:6]:
                vals.append(_read_float(os.path.join(d["id"], ax)))
            if vals:
                rows.append(vals)
        if not rows:
            return None
        return np.asarray(rows, dtype=np.float32)

class ThermalSource(Source):
    name = "thermal"
    privacy = "environment"
    def enumerate(self) -> List[dict]:
        out = []
        for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            out.append({"id": p, "name": os.path.basename(os.path.dirname(p))})
        return out
    def read(self, n: int = 8):
        zs = self.enumerate()
        if not zs or np is None:
            return None
        return np.asarray([_read_float(z["id"]) / 1000.0 for z in zs[:8]], dtype=np.float32)

class WifiRssiSource(Source):
    name = "wifi_rssi"
    privacy = "environment"
    def enumerate(self) -> List[dict]:
        # path varies; best-effort
        if os.path.isdir("/proc/net/wireless"):
            return [{"id": "/proc/net/wireless", "name": "wireless"}]
        return []
    def read(self, n: int = 8):
        try:
            with open("/proc/net/wireless", "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[2:]
            vals = []
            for ln in lines:
                parts = ln.replace(":", " ").split()
                if len(parts) >= 4:
                    vals.append(float(parts[3]))
            if np is None:
                return vals
            return np.asarray(vals or [0.0], dtype=np.float32)
        except Exception:
            return None

def install_defaults():
    for cls in (IIOSource, ThermalSource, WifiRssiSource):
        try:
            register(cls())
        except Exception:
            pass

install_defaults()
