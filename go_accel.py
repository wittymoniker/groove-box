"""Optional Go shared-library kernels for deterministic hybrid workloads.

The Go toolchain is invoked lazily and writes only to the user's cache. The
backend is selected by hybrid_runtime only after numerical parity and speed
checks against the NumPy reference. Audio callback code never compiles or waits
for Go: callers should warm/select this backend from sCode's hybrid lane.
"""
from __future__ import annotations
import ctypes
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_GO_SOURCE = r'''package main
/*
#include <stdint.h>
*/
import "C"
import ("math"; "unsafe")
//export GBOscFill
func GBOscFill(phase *C.double, output *C.float, n C.int, amp C.double, meum C.double) {
    if phase == nil || output == nil || n <= 0 { return }
    in := unsafe.Slice((*float64)(unsafe.Pointer(phase)), int(n))
    out := unsafe.Slice((*float32)(unsafe.Pointer(output)), int(n))
    a := float64(amp) * float64(meum)
    for i := range in { out[i] = float32(math.Sin(in[i]) * a) }
}
func main() {}
'''
_LIB = None
_ERROR = None


def _source_path():
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "groovebox" / "go-kernels"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / ("main-" + hashlib.sha256(_GO_SOURCE.encode()).hexdigest()[:16] + ".go")
    if not path.exists():
        path.write_text(_GO_SOURCE, encoding="utf-8")
    return path


def _library_path():
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "groovebox" / "go-kernels"
    cache.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(_GO_SOURCE.encode()).hexdigest()[:16]
    return cache / ("libgbkernels-" + digest + (".dll" if os.name == "nt" else ".dylib" if __import__("sys").platform == "darwin" else ".so"))


def ready():
    """Cheap check: report only an already-built library; never invoke Go."""
    if _LIB is not None:
        return True
    try:
        return _library_path().is_file()
    except Exception:
        return False


def available():
    global _LIB, _ERROR
    if _LIB is not None:
        return True
    if _ERROR is not None:
        return False
    go = shutil.which("go")
    if not go:
        _ERROR = "Go toolchain unavailable"
        return False
    target = _library_path()
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix="gb-go-") as td:
            env = dict(os.environ)
            env.setdefault("GOTOOLCHAIN", "local")
            source = _source_path()
            cmd = [go, "build", "-trimpath", "-buildmode=c-shared", "-o", str(target), str(source)]
            try:
                subprocess.run(cmd, cwd=td, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180, check=True)
            except Exception as exc:
                _ERROR = "Go kernel compile unavailable: %s" % exc
                return False
    try:
        lib = ctypes.CDLL(str(target))
        lib.GBOscFill.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.c_double, ctypes.c_double]
        lib.GBOscFill.restype = None
        _LIB = lib
        return True
    except Exception as exc:
        _ERROR = "Go kernel load unavailable: %s" % exc
        return False


def osc_fill(phase, freq, n, sr, amp, meum):
    """Fill a float32 oscillator block; phase vector is supplied by reference API."""
    import numpy as np
    if not available():
        raise RuntimeError(_ERROR or "Go backend unavailable")
    n = max(1, int(n)); sr = max(1, int(sr))
    ph = (float(phase) + np.arange(n, dtype=np.float64) * float(freq) / sr) % (2.0 * np.pi)
    out = np.empty(n, dtype=np.float32)
    _LIB.GBOscFill(ph.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), n, float(amp), float(meum))
    return out


def status():
    return {"available": available(), "error": _ERROR, "library": str(_library_path())}
