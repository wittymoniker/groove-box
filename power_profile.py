"""Adaptive power / battery / thermal profile for Groovebox.

Detects AC vs battery, charge level, and (when available) thermal pressure,
then recommends a performance tier that keeps audio smooth on any laptop
without changing the musical result.

Tiers
  high   plugged in, cool, plenty of cores — full visual quality
  mid    mixed or moderate — balanced
  low    on battery, hot, or few cores — reduced visual load, audio protected

Nothing here touches DSP maths. It only advises quality knobs
(visual FPS, particle scale, default export resolution, background work).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional


def _read(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception:
        return None


def _linux_battery() -> Dict[str, Any]:
    """Best-effort /sys/class/power_supply read."""
    base = "/sys/class/power_supply"
    info: Dict[str, Any] = {"source": "linux", "on_battery": False, "percent": None, "status": "unknown"}
    try:
        if not os.path.isdir(base):
            return info
        for name in os.listdir(base):
            p = os.path.join(base, name)
            typ = (_read(os.path.join(p, "type")) or "").lower()
            if typ == "battery":
                cap = _read(os.path.join(p, "capacity"))
                st = (_read(os.path.join(p, "status")) or "").lower()
                try:
                    info["percent"] = int(cap) if cap is not None else None
                except Exception:
                    info["percent"] = None
                info["status"] = st or "unknown"
                info["on_battery"] = st in ("discharging", "not charging")
            elif typ in ("mains", "usb", "ups"):
                online = _read(os.path.join(p, "online"))
                if online == "1":
                    info["ac"] = True
                elif online == "0" and "ac" not in info:
                    info["ac"] = False
        if info.get("ac") is True:
            info["on_battery"] = False
        elif info.get("ac") is False and info["percent"] is not None:
            info["on_battery"] = True
    except Exception:
        pass
    return info


def _windows_battery() -> Dict[str, Any]:
    info: Dict[str, Any] = {"source": "windows", "on_battery": False, "percent": None, "status": "unknown"}
    try:
        import ctypes
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("Reserved1", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]
        s = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            info["on_battery"] = (s.ACLineStatus == 0)
            if 0 <= s.BatteryLifePercent <= 100:
                info["percent"] = int(s.BatteryLifePercent)
            info["status"] = "discharging" if info["on_battery"] else "charging"
    except Exception:
        pass
    return info


def _macos_battery() -> Dict[str, Any]:
    info: Dict[str, Any] = {"source": "macos", "on_battery": False, "percent": None, "status": "unknown"}
    try:
        import subprocess
        out = subprocess.check_output(["pmset", "-g", "batt"], text=True, timeout=2, stderr=subprocess.DEVNULL)
        low = out.lower()
        info["on_battery"] = "discharging" in low or "battery power" in low
        # e.g. "87%;"
        for tok in out.replace(";", " ").split():
            if tok.endswith("%"):
                try:
                    info["percent"] = int(tok[:-1])
                except Exception:
                    pass
                break
        info["status"] = "discharging" if info["on_battery"] else "charging"
    except Exception:
        pass
    return info


def battery_state() -> Dict[str, Any]:
    """Return {on_battery, percent, status, source}."""
    if os.name == "nt":
        return _windows_battery()
    if os.uname().sysname == "Darwin":
        return _macos_battery()
    return _linux_battery()


def thermal_hot() -> bool:
    """True if any thermal zone is critically hot (Linux)."""
    base = "/sys/class/thermal"
    try:
        if not os.path.isdir(base):
            return False
        for name in os.listdir(base):
            if not name.startswith("thermal_zone"):
                continue
            t = _read(os.path.join(base, name, "temp"))
            if t is None:
                continue
            try:
                # millidegrees
                if int(t) >= 85000:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def usable_cores() -> int:
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except Exception:
        return max(1, int(os.cpu_count() or 1))


def ram_gb() -> float:
    try:
        if os.path.exists("/proc/meminfo"):
            for line in open("/proc/meminfo", "r", encoding="utf-8", errors="replace"):
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb / (1024.0 * 1024.0)
    except Exception:
        pass
    return 0.0


def compute_profile(force: Optional[str] = None) -> Dict[str, Any]:
    """Return a profile dict used by the rest of Groovebox.

    Keys: tier, on_battery, percent, status, cores, ram_gb, hot,
          visual_fps, particle_scale, export_scale, background_ok, label
    """
    batt = battery_state()
    cores = usable_cores()
    ram = ram_gb()
    hot = thermal_hot()
    on_batt = bool(batt.get("on_battery"))
    pct = batt.get("percent")

    if force in ("low", "mid", "high"):
        tier = force
    else:
        score = 0
        if cores <= 4:
            score -= 2
        elif cores >= 8:
            score += 1
        if ram and ram < 8:
            score -= 1
        if on_batt:
            score -= 2
            if isinstance(pct, int) and pct < 25:
                score -= 1
        if hot:
            score -= 2
        if score <= -2:
            tier = "low"
        elif score >= 1:
            tier = "high"
        else:
            tier = "mid"

    presets = {
        "low":  dict(visual_fps=12, particle_scale=0.45, export_scale=0.6, background_ok=False),
        "mid":  dict(visual_fps=24, particle_scale=0.75, export_scale=0.85, background_ok=True),
        "high": dict(visual_fps=30, particle_scale=1.0, export_scale=1.0, background_ok=True),
    }
    p = dict(presets[tier])
    p.update(
        tier=tier,
        on_battery=on_batt,
        percent=pct,
        status=batt.get("status") or "unknown",
        cores=cores,
        ram_gb=round(ram, 1) if ram else None,
        hot=hot,
    )
    pct_s = f"{pct}%" if isinstance(pct, int) else "—"
    power = "battery" if on_batt else "AC"
    p["label"] = f"{tier.upper()} · {power} {pct_s} · {cores} threads" + (" · hot" if hot else "")
    return p


def summary_line() -> str:
    return compute_profile().get("label") or "profile unknown"
