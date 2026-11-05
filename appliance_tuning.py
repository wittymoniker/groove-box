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
        with open(path, "w") as f:
            f.write(value)
        return True
    except Exception:
        return False


def apply(sys_root="/sys", force=False):
    """Returns a small report dict; never raises."""
    report = {"applied": False, "governor": 0, "epp": 0, "nice": None}
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
    return report
