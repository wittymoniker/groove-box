"""GROOVEBOX_APPLIANCE_TUNING_20261102: sOS performance tuning is best effort and appliance-only."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import appliance_tuning as at


def _fake_sys(tmp_path, governors="powersave performance"):
    for i in range(2):
        d = tmp_path / "devices/system/cpu" / f"cpu{i}" / "cpufreq"
        d.mkdir(parents=True)
        (d / "scaling_governor").write_text("powersave")
        (d / "scaling_available_governors").write_text(governors)
        (d / "energy_performance_preference").write_text("balance_performance")
    return tmp_path


def test_sets_performance_governor_and_epp(tmp_path):
    root = _fake_sys(tmp_path)
    rep = at.apply(sys_root=str(root), force=True)
    assert rep["governor"] == 2 and rep["epp"] == 2
    for i in range(2):
        d = root / "devices/system/cpu" / f"cpu{i}" / "cpufreq"
        assert (d / "scaling_governor").read_text() == "performance"
        assert (d / "energy_performance_preference").read_text() == "performance"


def test_skips_governor_that_is_not_offered(tmp_path):
    root = _fake_sys(tmp_path, governors="powersave schedutil")
    assert at.apply(sys_root=str(root), force=True)["governor"] == 0


def test_not_applied_on_a_desktop(tmp_path, monkeypatch):
    monkeypatch.setattr(at, "_is_appliance", lambda: False)
    root = _fake_sys(tmp_path)
    assert at.apply(sys_root=str(root))["applied"] is False
    assert (root / "devices/system/cpu/cpu0/cpufreq/scaling_governor").read_text() == "powersave"


def test_off_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("GROOVEBOX_APPLIANCE_TUNING", "0")
    assert at.apply(sys_root=str(_fake_sys(tmp_path)), force=True)["applied"] is False


def test_missing_sysfs_never_raises(tmp_path):
    assert at.apply(sys_root=str(tmp_path / "nope"), force=True)["governor"] == 0


def test_wired_into_the_launcher_before_the_app_is_imported():
    src = (ROOT / "run_groovebox.py").read_text(encoding="utf-8")
    assert src.index("_appliance_tuning.apply()") < src.index("from groovebox import MathematiciansGrooveboxApp")
