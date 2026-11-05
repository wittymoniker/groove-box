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


def test_override_wins():
    assert _with_env(GROOVEBOX_THREADS="3") == 3


def test_maths_uses_every_usable_thread_plus_one_spare(monkeypatch):
    monkeypatch.delenv("GROOVEBOX_THREADS", raising=False)
    for cores, want in ((1, 1), (2, 3), (4, 5), (8, 9), (64, 16)):
        monkeypatch.setattr(tb, "usable_cores", lambda c=cores: c)
        assert tb.compute_threads() == want, (cores, want)


def test_shared_lane_budget_is_four_slots_per_core_capped_at_32(monkeypatch):
    monkeypatch.delenv("GROOVEBOX_THREADS", raising=False)
    for cores, want in ((1, 8), (2, 8), (4, 16), (8, 32), (64, 32)):
        monkeypatch.setattr(tb, "usable_cores", lambda c=cores: c)
        assert tb.lane_workers() == want, (cores, want)


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
