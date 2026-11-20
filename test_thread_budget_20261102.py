"""GROOVEBOX_THREAD_BUDGET_20261102: one CPU budget for math libraries and worker pools."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import thread_budget as tb


def _with_env(**kw):
    old = {k: os.environ.get(k) for k in kw}
    try:
        for k, v in kw.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return tb.compute_threads()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# GROOVEBOX_R123_THREAD_BUDGET_TESTS_20261119: realigned with the current policy in
# thread_budget.py (overrides are clamped to real capacity; laptops/tablets keep one CPU for
# the UI + audio callback; math width cap 8, tablets 4; shared lanes keep one CPU, two on 3 cores).
def test_override_wins(monkeypatch):
    monkeypatch.setattr(tb, "usable_cores", lambda: 8)
    assert _with_env(GROOVEBOX_THREADS="3") == 3
    monkeypatch.setattr(tb, "usable_cores", lambda: 2)
    assert _with_env(GROOVEBOX_THREADS="3") == 2          # never more than the machine has


def test_maths_never_exceeds_the_usable_cpu_budget(monkeypatch):
    import compat_settings as cs
    monkeypatch.delenv("GROOVEBOX_THREADS", raising=False)
    table = {"laptop": ((1, 1), (2, 2), (4, 3), (8, 7), (64, 8)),
             "tablet": ((1, 1), (2, 2), (4, 3), (8, 4)),
             "desktop": ((1, 1), (4, 4), (8, 8), (64, 8))}
    for kind, rows in table.items():
        monkeypatch.setattr(cs, "hardware_class", lambda k=kind: k)
        for cores, want in rows:
            monkeypatch.setattr(tb, "usable_cores", lambda c=cores: c)
            assert tb.compute_threads() == want, (kind, cores, want)


def test_shared_lane_leaves_one_cpu_for_ui_and_audio(monkeypatch):
    monkeypatch.delenv("GROOVEBOX_WORKERS", raising=False)
    monkeypatch.setattr(tb, "_memory_headroom_cap", lambda n: n)   # RAM headroom is machine-specific
    for cores, want in ((1, 1), (2, 1), (3, 1), (4, 3), (8, tb._MAX_SHARED_WORKERS), (64, tb._MAX_SHARED_WORKERS)):
        monkeypatch.setattr(tb, "usable_cores", lambda c=cores: c)
        assert tb.lane_workers() == want, (cores, want)
        assert tb.lane_workers() < max(2, cores)


def test_apply_respects_existing_environment():
    code = ("import os,sys; sys.path.insert(0, %r); os.environ['OMP_NUM_THREADS']='5'; "
            "import thread_budget as t; t.apply(); "
            "print(os.environ['OMP_NUM_THREADS'], os.environ['OMP_WAIT_POLICY'], os.environ['OPENBLAS_NUM_THREADS'])") % str(ROOT)
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True).stdout.split()
    assert out[0] == "5" and out[1] == "PASSIVE" and out[2].isdigit()


def test_wired_before_numpy_and_into_the_pools():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert src.index("_thread_budget.apply()") < src.index("import numpy as np")
    assert "_thread_budget.lane_workers()" in src and "_thread_budget.compute_threads()" in src
    assert "_thread_budget.apply()" in (ROOT / "run_groovebox.py").read_text(encoding="utf-8")
