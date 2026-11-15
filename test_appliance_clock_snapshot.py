"""Regression tests for safe, read-only CPU clock/boost/thermal telemetry."""
import pathlib
import tempfile
import appliance_tuning


def _put(root, rel, value):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value)


def test_clock_snapshot_reads_policy_boost_and_temperature_without_writing():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        _put(root, "devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "3200000")
        _put(root, "devices/system/cpu/cpu0/cpufreq/scaling_governor", "performance")
        _put(root, "devices/system/cpu/cpu0/cpufreq/energy_performance_preference", "performance")
        _put(root, "devices/system/cpu/cpufreq/boost", "1")
        _put(root, "devices/system/cpu/intel_pstate/no_turbo", "0")
        _put(root, "class/thermal/thermal_zone0/temp", "47000")
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        snap = appliance_tuning.clock_snapshot(str(root))
        after = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        assert snap["cpu_freq_current_khz_max"] == 3200000
        assert snap["governors"] == ["performance"]
        assert snap["epp"] == ["performance"]
        assert snap["cpufreq_boost"] == "1"
        assert snap["intel_no_turbo"] == "0"
        assert snap["thermal_zone_c"] == [47.0]
        assert before == after


def test_clock_snapshot_handles_missing_sysfs():
    with tempfile.TemporaryDirectory() as td:
        snap = appliance_tuning.clock_snapshot(td)
        assert snap["cpu_freq_current_khz_max"] is None
        assert snap["governors"] == []
        assert snap["thermal_zone_c"] == []
