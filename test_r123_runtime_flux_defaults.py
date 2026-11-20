"""GROOVEBOX_R123_RUNTIME_FLUX_DEFAULTS_20261119: thread env + appliance sustained-throughput tuning."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import appliance_tuning as at


def _w(p: Path, v: str):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(v)


def _fake(tmp, *, ac=True, temp=50000):
    sysr = tmp / "sys"; proc = tmp / "proc"
    _w(sysr / "devices/system/cpu/intel_pstate/no_turbo", "1")
    _w(sysr / "devices/system/cpu/cpu0/cpufreq/energy_performance_preference", "performance")
    _w(sysr / "devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences", "default performance balance_performance power")
    _w(sysr / "firmware/acpi/platform_profile", "balanced")
    _w(sysr / "firmware/acpi/platform_profile_choices", "low-power balanced performance")
    _w(sysr / "class/thermal/thermal_zone0/type", "x86_pkg_temp"); _w(sysr / "class/thermal/thermal_zone0/temp", str(temp))
    _w(sysr / "class/power_supply/AC/type", "Mains"); _w(sysr / "class/power_supply/AC/online", "1" if ac else "0")
    _w(sysr / "class/power_supply/BAT0/type", "Battery"); _w(sysr / "class/power_supply/BAT0/status", "Charging" if ac else "Discharging")
    _w(sysr / "kernel/mm/transparent_hugepage/enabled", "always [madvise] never")
    _w(sysr / "kernel/mm/transparent_hugepage/defrag", "always")
    _w(sysr / "block/nvme0n1/queue/scheduler", "[none] mq-deadline")
    _w(sysr / "block/mmcblk0/queue/scheduler", "[none] mq-deadline bfq")
    for k in at.FLUX_VM:
        _w(proc / "sys" / k, "60")
    return sysr, proc


def test_flux_on_ac(tmp_path):
    sysr, proc = _fake(tmp_path)
    r = at.apply_flux(str(sysr), str(proc))
    assert r["ac"] and r["turbo"] and r["platform_profile"] == "performance"
    assert (sysr / "devices/system/cpu/intel_pstate/no_turbo").read_text() == "0"
    assert (proc / "sys/vm/swappiness").read_text() == "10" and r["vm"] == 4
    assert (sysr / "block/nvme0n1/queue/scheduler").read_text() == "none"
    assert (sysr / "block/mmcblk0/queue/scheduler").read_text() == "mq-deadline"
    assert r["thp"] and r["epp_battery"] == 0


def test_flux_on_battery_and_hot(tmp_path):
    sysr, proc = _fake(tmp_path, ac=False)
    r = at.apply_flux(str(sysr), str(proc))
    assert not r["ac"] and r["platform_profile"] == "balanced" and r["epp_battery"] == 1
    sysr2, proc2 = _fake(tmp_path / "hot", temp=95000)
    assert at.apply_flux(str(sysr2), str(proc2))["platform_profile"] == "balanced"


def test_thread_env_defaults_cover_every_runtime():
    code = ("import os,sys; sys.path.insert(0,%r); [os.environ.pop(k,None) for k in list(os.environ) if 'THREAD' in k or k in ('GOMAXPROCS','MALLOC_ARENA_MAX')]; "
            "import thread_budget as t; n=t.apply(); "
            "print(n, os.environ['JULIA_NUM_THREADS'], os.environ['PYTHON_JULIACALL_THREADS'], os.environ['RAYON_NUM_THREADS'], os.environ['GOMAXPROCS'], os.environ['OMP_WAIT_POLICY'])") % str(ROOT)
    n, jl, jc, ray, go, wait = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True).stdout.split()
    assert jl == f"{n},1" and jc == n and ray == n and int(go) >= 1 and wait == "PASSIVE"


def test_user_override_wins():
    code = ("import os,sys; sys.path.insert(0,%r); os.environ['JULIA_NUM_THREADS']='1'; "
            "import thread_budget as t; t.apply(); print(os.environ['JULIA_NUM_THREADS'])") % str(ROOT)
    assert subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True).stdout.strip() == "1"
