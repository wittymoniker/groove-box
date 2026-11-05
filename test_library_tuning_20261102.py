import os
import library_tuning as lt
import compat_settings as cs


def test_plan_follows_smooth_level():
    s = lt.plan(True, cores=4); n = lt.plan(False, cores=4)
    assert s["blas_threads"] == 3 and s["encode_threads"] == 2          # one thread kept free for audio / UI
    assert n["blas_threads"] >= 4 and n["encode_threads"] == 0
    assert lt.plan(True, cores=1)["blas_threads"] == 1
    assert s["omp_wait"] == "PASSIVE" and n["omp_wait"] == "PASSIVE"


def test_apply_sets_every_library_and_real_environment_wins(monkeypatch):
    for k in lt.MANAGED:
        monkeypatch.delenv(k, raising=False)
    lt.apply(True, user_env={"MKL_NUM_THREADS": "7"}, cores=4)
    assert os.environ["OMP_NUM_THREADS"] == "3" and os.environ["OPENBLAS_NUM_THREADS"] == "3"
    assert "MKL_NUM_THREADS" not in os.environ                           # user value (not in this env snapshot) untouched
    assert os.environ["OMP_WAIT_POLICY"] == "PASSIVE" and os.environ["KMP_BLOCKTIME"] == "0"
    assert os.environ["GROOVEBOX_ENCODE_THREADS"] == "2"
    assert lt.ffmpeg_threads_args() == ["-threads", "2"]
    lt.apply(False, cores=4)
    assert "GROOVEBOX_ENCODE_THREADS" not in os.environ and lt.ffmpeg_threads_args() == []


def test_compat_settings_drives_the_libraries_and_reports_them(monkeypatch):
    for k in lt.MANAGED:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(cs, "_USER_ENV", {})
    cs.apply_env({"smooth_mode": "on"})
    assert os.environ.get("GROOVEBOX_ENCODE_THREADS")
    cs.apply_env({"smooth_mode": "off"})
    assert "GROOVEBOX_ENCODE_THREADS" not in os.environ
    assert any(l.startswith("Libraries:") for l in cs.describe({"smooth_mode": "on"}))
    assert set(lt.MANAGED) <= set(cs._MANAGED)
