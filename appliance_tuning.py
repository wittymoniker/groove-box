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


# GROOVEBOX_R123_RUNTIME_FLUX_DEFAULTS_20261119: sustained-throughput ("continuous flux") baseline
# for the appliance. All of these use only limits the firmware already allows; nothing raises a
# voltage, multiplier or power limit (Dell Latitude / Acer Nitro firmware locks those anyway).
#   turbo/boost on                   intel_pstate/no_turbo=0, cpufreq/boost=1
#   firmware platform profile        "performance" on AC power when no CPU zone is >= 90 C;
#                                    "balanced" on battery (sustained clocks without a thermal cliff)
#   EPP on battery                   balance_performance (the AC value stays "performance")
#   transparent huge pages           madvise + defer+madvise (big NumPy buffers, no compaction stalls)
#   VM writeback                     64 MB background / 256 MB hard dirty limit: long renders and
#                                    exports stream to disk steadily instead of stalling in bursts
#   swappiness 10, vfs_cache_pressure 50: keep the working set (samples, projects) resident
#   I/O scheduler                    none for NVMe, mq-deadline for SATA/eMMC/SD
FLUX_HOT_C = 90.0
FLUX_VM = {"vm/swappiness": "10", "vm/vfs_cache_pressure": "50",
           "vm/dirty_background_bytes": str(64 * 1024 * 1024), "vm/dirty_bytes": str(256 * 1024 * 1024)}


def on_ac_power(sys_root="/sys"):
    """True on mains power or when no battery is present (desktops, unknown = AC)."""
    supplies = glob.glob(os.path.join(sys_root, "class", "power_supply", "*"))
    mains = [p for p in supplies if (_read(os.path.join(p, "type")) or "") in ("Mains", "USB_C", "USB")]
    batteries = [p for p in supplies if (_read(os.path.join(p, "type")) or "") == "Battery"]
    if not batteries:
        return True
    if any((_read(os.path.join(p, "online")) or "0") == "1" for p in mains):
        return True
    return not any((_read(os.path.join(p, "status")) or "") == "Discharging" for p in batteries)


def _hottest_cpu_c(sys_root="/sys"):
    hot = 0.0
    for zone in glob.glob(os.path.join(sys_root, "class", "thermal", "thermal_zone*")):
        kind = (_read(os.path.join(zone, "type")) or "").lower()
        if not any(k in kind for k in ("x86_pkg", "cpu", "tcpu", "k10temp", "acpitz")):
            continue
        t = _read(os.path.join(zone, "temp"))
        if t and t.lstrip("-").isdigit():
            hot = max(hot, int(t) / 1000.0)
    return hot


def apply_flux(sys_root="/sys", proc_root=None):
    """Best-effort sustained-throughput settings; returns what was written. Never raises."""
    if proc_root is None:
        proc_root = "/proc" if os.path.abspath(sys_root) == "/sys" else os.path.join(os.path.dirname(os.path.abspath(sys_root)), "proc")
    out = {"ac": True, "turbo": False, "platform_profile": None, "thp": False, "vm": 0, "io": 0, "epp_battery": 0}
    try:
        ac = on_ac_power(sys_root); out["ac"] = ac
        cpu = os.path.join(sys_root, "devices", "system", "cpu")
        if _write(os.path.join(cpu, "intel_pstate", "no_turbo"), "0") | _write(os.path.join(cpu, "cpufreq", "boost"), "1"):
            out["turbo"] = True
        pp = os.path.join(sys_root, "firmware", "acpi", "platform_profile")
        choices = (_read(pp + "_choices") or "").split()
        if choices:
            hot = _hottest_cpu_c(sys_root)
            want = None
            if ac and hot < FLUX_HOT_C:
                want = next((c for c in ("performance", "balanced-performance") if c in choices), None)
            elif "balanced" in choices:
                want = "balanced"
            if want and _write(pp, want):
                out["platform_profile"] = want
        if not ac:
            for path in glob.glob(os.path.join(cpu, "cpu[0-9]*", "cpufreq", "energy_performance_preference")):
                avail = (_read(path.replace("energy_performance_preference", "energy_performance_available_preferences")) or "").split()
                if (not avail or "balance_performance" in avail) and _write(path, "balance_performance"):
                    out["epp_battery"] += 1
        thp = os.path.join(sys_root, "kernel", "mm", "transparent_hugepage")
        out["thp"] = _write(os.path.join(thp, "enabled"), "madvise") and _write(os.path.join(thp, "defrag"), "defer+madvise")
        for key, value in FLUX_VM.items():
            if _write(os.path.join(proc_root, "sys", key), value):
                out["vm"] += 1
        for q in glob.glob(os.path.join(sys_root, "block", "*", "queue", "scheduler")):
            dev = q.split(os.sep)[-3]
            if dev.startswith(("loop", "ram", "zram", "dm-", "sr")):
                continue
            avail = _read(q) or ""
            want = "none" if dev.startswith("nvme") else "mq-deadline"
            if want in avail.replace("[", " ").replace("]", " ").split() and _write(q, want):
                out["io"] += 1
    except Exception:
        pass
    return out


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
        if os.environ.get("GROOVEBOX_FLUX", "1").strip().lower() not in ("0", "false", "no", "off"):
            report["flux"] = apply_flux(sys_root)
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
