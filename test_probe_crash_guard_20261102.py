import subprocess
import sys
import hardware_hub as h


def test_signal_death_is_retried_and_reported_not_raised():
    cp = h.run_probe_retry([sys.executable, "-c", "import os,signal;os.kill(os.getpid(),signal.SIGQUIT)"], timeout=5)
    assert cp.returncode == -3
    assert "SIGQUIT" in cp.stderr and "Performance keeps running" in cp.stderr


def test_healthy_probe_untouched_and_retry_recovers():
    cp = h.run_probe_retry([sys.executable, "-c", "print('ok')"], timeout=5)
    assert cp.returncode == 0 and cp.stdout.strip() == "ok"
    code = ("import os,signal,sys,tempfile\n"
            "p=os.path.join(tempfile.gettempdir(),'gb_probe_once_%d' % os.getppid())\n"
            "if not os.path.exists(p):\n open(p,'w').close(); os.kill(os.getpid(),signal.SIGQUIT)\n"
            "os.remove(p); print('second try')\n")
    cp = h.run_probe_retry([sys.executable, "-c", code], timeout=5)
    assert cp.returncode == 0 and "second try" in cp.stdout


def test_performance_uses_the_guard_for_both_probes():
    src = open("performance.py", encoding="utf-8").read()
    assert src.count("run_probe_retry(helper_argv('device_probe_helper'") == 2
