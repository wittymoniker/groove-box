import os
"""GROOVEBOX_HW_QT_THREAD_SAFE_20261030 / GROOVEBOX_NO_GUI_STALL_20261030 / GROOVEBOX_LOCAL_BUILD_TMP_20261030"""
import subprocess, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
OVERLAY = ROOT / "BUILD_ISO" / "app-overlay-v35.22zz"


def test_qmediadevices_never_touched_off_gui_thread(monkeypatch):
    import hardware_hub
    calls = []
    monkeypatch.setattr(hardware_hub, "_on_qt_gui_thread", lambda: calls.append(1) or False)
    out = {}
    t = threading.Thread(target=lambda: out.update(hardware_hub.scan_component("video")))
    t.start(); t.join(5)
    assert calls and "video_devices" in out


def test_probe_helper_has_no_qt_without_application():
    # Fresh interpreter: earlier suites in the same pytest process create a QApplication.
    import subprocess, sys
    r = subprocess.run([sys.executable, "-c", "import hardware_hub; print(hardware_hub._on_qt_gui_thread())"],
                       capture_output=True, text=True, timeout=60, cwd=os.path.dirname(os.path.abspath(__file__)))
    assert r.stdout.strip().splitlines()[-1] == "False", r.stderr[-400:]  # no QCoreApplication in this process


def test_device_snapshot_does_not_stall_behind_inflight_query(monkeypatch):
    import audio_os_backend as a
    # Always our own slow stand-in: an earlier suite may have left a fake ``sd`` installed.
    class _SD:
        @staticmethod
        def query_devices(*_a, **_k): time.sleep(1.5); return [{"name": "x", "max_output_channels": 2}]
    monkeypatch.setattr(a, "sd", _SD); monkeypatch.setattr(a, "HAS_SOUNDDEVICE", True)
    a.invalidate_device_cache()
    with a._DEVICE_CACHE_LOCK:
        a._DEVICE_CACHE = [{"name": "old"}]; a._DEVICE_CACHE_AT = 0.0   # stale but present
    snap = getattr(a, "_device_snapshot_orig", a._device_snapshot)   # the real one (another suite may stub it)
    slow = threading.Thread(target=lambda: snap(force=True)); slow.start()
    time.sleep(0.2)
    t0 = time.monotonic(); rows = snap(force=True); dt = time.monotonic() - t0
    slow.join(5)
    assert dt < 0.5 and rows == [{"name": "old"}]


def test_shipped_overlay_matches_fixed_sources():
    for f in ("hardware_hub.py", "device_probe_helper.py", "performance.py",
              "hardware_runtime.py", "audio_os_backend.py", "groovebox.py"):
        assert (OVERLAY / f).read_bytes() == (ROOT / f).read_bytes(), f"overlay stale: {f}"


def test_build_scratch_is_next_to_dist_not_tmp():
    lib = ROOT / "BUILD_ISO" / "initrd_lib.sh"
    r = subprocess.run(["bash", "-c", f'. "{lib}"; echo "$TMPDIR"'], capture_output=True, text=True)
    tmp = r.stdout.strip().splitlines()[-1]
    assert tmp == str(ROOT / "BUILD_ISO" / "build_tmp") and not tmp.startswith("/tmp")
    import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_health_actions_do_not_block_gui_thread():
    src = (ROOT / "groovebox.py").read_text()
    body = src.split("def _health_recover_audio", 1)[1].split("def _rename_file_dialog", 1)[0]
    gui_part = body.split("def work()", 1)[0]
    assert "subprocess.run" not in gui_part
    assert "_live_portaudio_streams()" in body and "_run_health_job" in body


def test_bounded_probe_runner_times_out_and_kills_group():
    import hardware_hub, inspect, subprocess, time
    src = inspect.getsource(hardware_hub.run_bounded)
    assert "start_new_session" in src and "os.killpg(proc.pid, 9)" in src
    t0 = time.monotonic()
    try:
        hardware_hub.run_bounded([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)
    except subprocess.TimeoutExpired:
        pass
    else:
        assert False, "bounded runner did not time out"
    assert time.monotonic() - t0 < 2.0


def test_probe_helper_scans_lanes_in_parallel():
    src = (ROOT / "device_probe_helper.py").read_text()
    assert "threading.Thread(target=_lane" in src
    assert "GROOVEBOX_HW_LANE_TIMEOUT" in src and "_emit_checkpoint" in src
