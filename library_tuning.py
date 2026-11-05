"""GROOVEBOX_LIBRARY_TUNING_20261102: the low-level libraries follow the Smooth level.

NumPy's BLAS, the OpenMP voice kernel, the video encoder and the optional PortAudio / threadpool
layers each have their own "how many threads, how do idle workers wait" default, and each assumes it
owns the machine. This module is the one place that chooses those modes from the Compatibility /
Smooth setting, so changing Smooth mode moves every library together instead of each guessing.

  smooth ON   leave one logical thread free for the audio callback and the UI, idle workers sleep
              at once, the video encoder is capped to half the threads.
  smooth OFF  every usable thread plus one spare for maths (the thread budget), idle workers sleep,
              the encoder chooses for itself.

Nothing here changes any DSP maths. A variable set in the real environment always wins. Thread counts
read by BLAS / OpenMP at import need a restart; the optional threadpoolctl hook applies them live.
"""
import os

# Variables this module may set (the compat layer treats real-environment values as authoritative).
MANAGED = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "OMP_WAIT_POLICY", "KMP_BLOCKTIME", "GROOVEBOX_ENCODE_THREADS")
_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS")


def _cores():
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except Exception:
        return max(1, int(os.cpu_count() or 1))


def plan(smooth, cores=None):
    """The mode every library should run in for this Smooth state."""
    cores = _cores() if cores is None else max(1, int(cores))
    try:
        forced = int(os.environ.get("GROOVEBOX_THREADS", "0") or 0)
    except ValueError:
        forced = 0
    # Same rule as thread_budget.compute_threads(), evaluated for the given core count.
    budget = forced if forced > 0 else max(1, min(16, cores + 1 if cores >= 2 else cores))
    if smooth:
        blas = max(1, min(budget, cores - 1)) if cores >= 2 else 1
        encode = max(1, cores // 2)
    else:
        blas = budget
        encode = 0                      # 0 = let the encoder decide
    return {"blas_threads": blas, "omp_wait": "PASSIVE", "kmp_blocktime": "0", "encode_threads": encode,
            "smooth": bool(smooth), "cores": cores}


def env_for(smooth, cores=None):
    p = plan(smooth, cores)
    env = {name: str(p["blas_threads"]) for name in _THREAD_VARS}
    env["OMP_WAIT_POLICY"] = p["omp_wait"]
    env["KMP_BLOCKTIME"] = p["kmp_blocktime"]
    env["GROOVEBOX_ENCODE_THREADS"] = str(p["encode_threads"]) if p["encode_threads"] > 0 else None
    return env


def apply(smooth, user_env=None, cores=None):
    """Set the library modes. ``user_env`` = variables the real environment already defined (kept)."""
    user_env = user_env or {}
    wanted = env_for(smooth, cores)
    # An explicit GROOVEBOX_THREADS or per-library variable in the real environment always wins.
    for key, value in wanted.items():
        if key in user_env:
            continue
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    apply_live(plan(smooth, cores)["blas_threads"])
    return wanted


def apply_live(blas_threads):
    """Change BLAS / OpenMP pools of the running process when threadpoolctl is available."""
    try:
        from threadpoolctl import threadpool_limits
    except Exception:
        return False
    try:
        threadpool_limits(limits=int(blas_threads))
        return True
    except Exception:
        return False


def ffmpeg_threads_args():
    """['-threads', 'N'] when the Smooth level caps the encoder, else [] (encoder default)."""
    try:
        n = int(os.environ.get("GROOVEBOX_ENCODE_THREADS", "0") or 0)
    except ValueError:
        n = 0
    return ["-threads", str(n)] if n > 0 else []


def describe(smooth, cores=None):
    p = plan(smooth, cores)
    enc = f"{p['encode_threads']} threads" if p["encode_threads"] else "encoder default"
    return (f"Libraries: maths (BLAS / OpenMP) {p['blas_threads']} threads, idle workers sleep at once; "
            f"video encoder {enc}" + (" · one thread kept free for audio and UI" if p["smooth"] else ""))
