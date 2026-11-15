"""GROOVEBOX_APPLIANCE_TUNING_20261102: standalone-OS (sOS) machine tuning.

When Groovebox runs as the appliance it is the only workload on the machine, so it
should get the whole CPU instead of a laptop power-saving profile:

  * CPU frequency governor -> performance (and the Intel EPP hint -> performance),
    so the live audio callback is never caught by a slow clock ramp.
  * Process priority raised (nice -5) before any worker thread exists, so every
    thread the app starts inherits it over background helpers.

Everything is best effort: a missing sysfs file, a read-only filesystem or a
non-root user just skips that step. It never runs on a normal desktop, and
GROOVEBOX_APPLIANCE_TUNING=0 turns it off.
"""
import glob
import os
import sys


def _read(path):
    try:
        return open(path, "r", encoding="ascii").read().strip()
    except Exception:
        return None


def clock_snapshot(sys_root="/sys"):
    """Read firmware-governed CPU clock/boost/thermal state; never changes limits."""
    cpu_root = os.path.join(sys_root, "devices", "system", "cpu")
    freqs = []
    governors = set()
    epps = set()
    for name in sorted(os.listdir(cpu_root)) if os.path.isdir(cpu_root) else []:
        if not name.startswith("cpu") or not name[3:].isdigit():
            continue
        base = os.path.join(cpu_root, name, "cpufreq")
        cur = _read(os.path.join(base, "scaling_cur_freq"))
        if cur and cur.isdigit():
            freqs.append(int(cur))
        gov = _read(os.path.join(base, "scaling_governor"))
        epp = _read(os.path.join(base, "energy_performance_preference"))
        if gov: governors.add(gov)
        if epp: epps.add(epp)
    boost = _read(os.path.join(cpu_root, "cpufreq", "boost"))
    no_turbo = _read(os.path.join(cpu_root, "intel_pstate", "no_turbo"))
    thermal = []
    thermal_root = os.path.join(sys_root, "class", "thermal")
    if os.path.isdir(thermal_root):
        for name in os.listdir(thermal_root):
            if name.startswith("thermal_zone"):
                raw = _read(os.path.join(thermal_root, name, "temp"))
                if raw and raw.lstrip("-").isdigit():
                    value = int(raw)
                    thermal.append(round(value / 1000.0 if abs(value) >= 1000 else float(value), 1))
    return {"cpu_freq_current_khz_min": min(freqs) if freqs else None,
            "cpu_freq_current_khz_max": max(freqs) if freqs else None,
            "governors": sorted(governors), "epp": sorted(epps),
            "cpufreq_boost": boost, "intel_no_turbo": no_turbo,
            "thermal_zone_c": thermal,
            "firmware_controls_clock_ceiling": True}

NICE_TARGET = -5


def _is_appliance():
    try:
        from appliance_wifi import is_appliance_profile
        return bool(is_appliance_profile())
    except Exception:
        profile = os.environ.get("GROOVEBOX_PROFILE", "").strip().lower()
        return (profile in {"sos", "appliance", "standalone", "tablet"}
                or os.environ.get("GROOVEBOX_APPLIANCE", "") == "1"
                or os.path.exists("/etc/groovebox-appliance"))


def _write(path, value):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(value)
        return True
    except Exception:
        return False


def apply(sys_root="/sys", force=False):
    """Returns a small report dict; never raises."""
    report = {"applied": False, "governor": 0, "epp": 0, "nice": None, "clock": {}}
    try:
        if os.environ.get("GROOVEBOX_APPLIANCE_TUNING", "1").strip().lower() in ("0", "false", "no", "off"):
            return report
        if not force and (not sys.platform.startswith("linux") or not _is_appliance()):
            return report
        report["applied"] = True
        cpu = os.path.join(sys_root, "devices", "system", "cpu")
        for path in glob.glob(os.path.join(cpu, "cpu[0-9]*", "cpufreq", "scaling_governor")):
            try:
                avail = open(os.path.join(os.path.dirname(path), "scaling_available_governors")).read().split()
            except Exception:
                avail = ["performance"]
            if "performance" in avail and _write(path, "performance"):
                report["governor"] += 1
        for path in glob.glob(os.path.join(cpu, "cpu[0-9]*", "cpufreq", "energy_performance_preference")):
            if _write(path, "performance"):
                report["epp"] += 1
        try:
            if hasattr(os, "nice") and os.nice(0) > NICE_TARGET:
                report["nice"] = os.nice(NICE_TARGET - os.nice(0))
        except Exception:
            pass
    except Exception:
        pass
    try:
        report["clock"] = clock_snapshot(sys_root)
    except Exception:
        report["clock"] = {}
    return report
