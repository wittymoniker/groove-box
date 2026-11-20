"""hybrid_native.py — compiled hybrid-language backends (C and Go) for hybrid_runtime.

GROOVEBOX_R123_HYBRID_POOL_20261119

The same three reference kernels the router verifies (osc_fill, wavefold, ca_evolve, hardclip) are shipped here as
C source and Go (cgo, -buildmode=c-shared) source. They are compiled once per toolchain version, in the background,
on the sCode "programs" direction (never on the GUI thread or the audio callback), cached under the Groovebox data
directory by a hash of source + compiler version + platform, and loaded with ctypes. ctypes releases the GIL for
every call, so these kernels run in parallel on the shared sCode pool. A backend that fails to build or does not
match the NumPy reference is simply never selected (hybrid_runtime does the parity check).

Environment: GROOVEBOX_HYBRID_NATIVE=0 disables both; GROOVEBOX_HYBRID_GO=0 disables only Go (one Go runtime is
loaded into the process; Go c-shared libraries chain to the signal handlers installed before them).
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np

C_SOURCE = r"""
#include <math.h>
#include <stdint.h>
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#if defined(_WIN32)
#define GBH_EXPORT __declspec(dllexport)
#else
#define GBH_EXPORT __attribute__((visibility("default")))
#endif
static double gbh_floor_mod(double x, double m) { double r = fmod(x, m); return r < 0.0 ? r + m : r; }
GBH_EXPORT int64_t gbh_abi(void) { return 1; }
GBH_EXPORT void gbh_osc_fill(double p0, double f, int64_t n, double sr, double amp, double meum, float *out) {
    const double tau = 2.0 * M_PI;
    for (int64_t i = 0; i < n; i++) out[i] = (float)(sin(gbh_floor_mod(p0 + (double)i * f / sr, tau)) * amp * meum);
}
GBH_EXPORT void gbh_wavefold(const double *x, int64_t n, double depth, float *out) {
    for (int64_t i = 0; i < n; i++) out[i] = (float)(fabs(gbh_floor_mod(x[i] * depth + 1.0, 4.0) - 2.0) - 1.0);
}
GBH_EXPORT void gbh_hardclip(const float *x, int64_t n, double gain, float *out) {
    for (int64_t i = 0; i < n; i++) { double y = (double)x[i] * gain; out[i] = (float)(y < -1.0 ? -1.0 : (y > 1.0 ? 1.0 : y)); }
}
GBH_EXPORT void gbh_ca_evolve(int64_t rule, int64_t w, int64_t steps, int8_t *out, int8_t *row, int8_t *nxt) {
    for (int64_t i = 0; i < w; i++) row[i] = 0;
    row[w / 2] = 1;
    for (int64_t s = 0; s < steps; s++) {
        for (int64_t i = 0; i < w; i++) {
            out[s * w + i] = row[i];
            int l = row[(i - 1 + w) % w], c = row[i], r = row[(i + 1) % w];
            nxt[i] = (int8_t)((rule >> (l * 4 + c * 2 + r)) & 1);
        }
        int8_t *t = row; row = nxt; nxt = t;
    }
}
"""

GO_SOURCE = r"""
package main

// #include <stdint.h>
import "C"

import (
	"math"
	"unsafe"
)

func floorMod(x, m float64) float64 {
	r := math.Mod(x, m)
	if r < 0 {
		r += m
	}
	return r
}

//export gbh_abi
func gbh_abi() C.int64_t { return 1 }

//export gbh_osc_fill
func gbh_osc_fill(p0, f C.double, n C.int64_t, sr, amp, meum C.double, out *C.float) {
	o := unsafe.Slice((*float32)(unsafe.Pointer(out)), int(n))
	tau := 2 * math.Pi
	for i := range o {
		o[i] = float32(math.Sin(floorMod(float64(p0)+float64(i)*float64(f)/float64(sr), tau)) * float64(amp) * float64(meum))
	}
}

//export gbh_wavefold
func gbh_wavefold(x *C.double, n C.int64_t, depth C.double, out *C.float) {
	xs := unsafe.Slice((*float64)(unsafe.Pointer(x)), int(n))
	o := unsafe.Slice((*float32)(unsafe.Pointer(out)), int(n))
	for i, v := range xs {
		o[i] = float32(math.Abs(floorMod(v*float64(depth)+1, 4)-2) - 1)
	}
}

//export gbh_hardclip
func gbh_hardclip(x *C.float, n C.int64_t, gain C.double, out *C.float) {
	xs := unsafe.Slice((*float32)(unsafe.Pointer(x)), int(n))
	o := unsafe.Slice((*float32)(unsafe.Pointer(out)), int(n))
	for i, v := range xs {
		o[i] = float32(math.Max(-1, math.Min(1, float64(v)*float64(gain))))
	}
}

//export gbh_ca_evolve
func gbh_ca_evolve(rule, w, steps C.int64_t, out, row, nxt *C.int8_t) {
	W := int(w)
	o := unsafe.Slice((*int8)(unsafe.Pointer(out)), W*int(steps))
	r := unsafe.Slice((*int8)(unsafe.Pointer(row)), W)
	nx := unsafe.Slice((*int8)(unsafe.Pointer(nxt)), W)
	for i := range r {
		r[i] = 0
	}
	r[W/2] = 1
	for s := 0; s < int(steps); s++ {
		for i := 0; i < W; i++ {
			o[s*W+i] = r[i]
			l, c, rr := int(r[(i-1+W)%W]), int(r[i]), int(r[(i+1)%W])
			nx[i] = int8((int64(rule) >> (l*4 + c*2 + rr)) & 1)
		}
		r, nx = nx, r
	}
}

func main() {}
"""

_LOCK = threading.Lock()
_LIBS: dict[str, ctypes.CDLL] = {}
_ERR: dict[str, str] = {}
_STARTED: set[str] = set()


def _enabled(lang):
    if os.environ.get("GROOVEBOX_HYBRID_NATIVE", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    if lang == "go" and os.environ.get("GROOVEBOX_HYBRID_GO", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    return True


def _suffix():
    return ".dll" if sys.platform.startswith("win") else (".dylib" if sys.platform == "darwin" else ".so")


def _cache_dir():
    try:
        import toolchain_env
        base = toolchain_env.data_dir()
    except Exception:
        base = Path(tempfile.gettempdir()) / "groovebox"
    d = Path(base) / "hybrid-native"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tool_version(argv, env=None):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=30, env=env).stdout.strip()[:200]
    except Exception:
        return ""


def _toolchain(lang):
    """(argv builder, env, version string) or None if the language is not installed."""
    if lang == "c":
        cc = os.environ.get("CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not cc:
            return None
        try:
            import toolchain_env
            env = toolchain_env.native_env()
        except Exception:
            env = dict(os.environ)
        ver = _tool_version([cc, "--version"], env)

        def argv(src, out):
            flags = ["-O2", "-shared", "-fPIC", "-fvisibility=hidden"]
            if sys.platform.startswith("win"):
                flags = ["-O2", "-shared"]
            return [cc, *flags, "-o", str(out), str(src), "-lm"] if not sys.platform.startswith("win") else [cc, *flags, "-o", str(out), str(src)]
        return argv, env, ver
    if lang == "go":
        try:
            import toolchain_env
            env = toolchain_env.go_env()
        except Exception:
            env = None
        go = shutil.which("go")
        if env is None or not go:
            return None
        env = dict(env)
        env["CGO_ENABLED"] = "1"
        env["GO111MODULE"] = "off"            # one self-contained file; no module or network resolution
        if not (env.get("CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")):
            return None                       # cgo needs a C compiler
        ver = _tool_version([go, "version"], env)

        def argv(src, out):
            return [go, "build", "-buildmode=c-shared", "-trimpath", "-o", str(out), str(src)]
        return argv, env, ver
    return None


def _build(lang):
    tc = _toolchain(lang)
    if tc is None:
        _ERR[lang] = "toolchain not installed"
        return None
    argv, env, ver = tc
    src_text = C_SOURCE if lang == "c" else GO_SOURCE
    key = hashlib.sha256(("%s|%s|%s|%s" % (lang, src_text, ver, platform.platform())).encode()).hexdigest()[:20]
    d = _cache_dir() / ("%s-%s" % (lang, key))
    lib = d / ("libgbh_%s%s" % (lang, _suffix()))
    if not lib.is_file():
        d.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(d)) as tmp:
            src = Path(tmp) / ("kernels.c" if lang == "c" else "kernels.go")
            src.write_text(src_text, encoding="utf-8")
            out = Path(tmp) / lib.name
            try:
                r = subprocess.run(argv(src, out), capture_output=True, text=True, timeout=600, env=env, cwd=tmp)
            except Exception as exc:
                _ERR[lang] = "compile failed: %s" % exc
                return None
            if r.returncode != 0 or not out.is_file():
                _ERR[lang] = "compile failed: " + (r.stderr or r.stdout)[-400:]
                return None
            os.replace(out, lib)                # atomic publish; a half-written library is never loaded
    try:
        h = ctypes.CDLL(str(lib))
        h.gbh_abi.restype = ctypes.c_int64
        if h.gbh_abi() != 1:
            raise OSError("unexpected ABI")
    except OSError as exc:
        _ERR[lang] = "load failed: %s" % exc
        return None
    P_f = ctypes.POINTER(ctypes.c_float); P_d = ctypes.POINTER(ctypes.c_double); P_b = ctypes.POINTER(ctypes.c_int8)
    i64, dbl = ctypes.c_int64, ctypes.c_double
    h.gbh_osc_fill.argtypes = [dbl, dbl, i64, dbl, dbl, dbl, P_f]; h.gbh_osc_fill.restype = None
    h.gbh_wavefold.argtypes = [P_d, i64, dbl, P_f]; h.gbh_wavefold.restype = None
    h.gbh_hardclip.argtypes = [P_f, i64, dbl, P_f]; h.gbh_hardclip.restype = None
    h.gbh_ca_evolve.argtypes = [i64, i64, i64, P_b, P_b, P_b]; h.gbh_ca_evolve.restype = None
    _ERR.pop(lang, None)
    return h


def _build_into_cache(lang):
    h = _build(lang)
    if h is not None:
        with _LOCK:
            _LIBS[lang] = h
    return h is not None


def ensure_started(langs=("c", "go")):
    """Schedule each compile once per process on the sCode 'programs' direction. Never blocks."""
    for lang in langs:
        with _LOCK:
            if lang in _STARTED or not _enabled(lang):
                continue
            _STARTED.add(lang)
        try:
            import scode_coordinator as sc
            sc.direct("programs", _build_into_cache, lang)
        except Exception:
            threading.Thread(target=_build_into_cache, args=(lang,), daemon=True, name="hybrid-build-" + lang).start()


def build_now(lang):
    """Synchronous build (tests / command console)."""
    with _LOCK:
        _STARTED.add(lang)
    return _build_into_cache(lang) if _enabled(lang) else False


def ready():
    with _LOCK:
        return sorted(_LIBS)


def status():
    return {lang: ("ready" if lang in _LIBS else _ERR.get(lang, "building" if lang in _STARTED else "not started"))
            for lang in ("c", "go")}


def _ptr(a, t):
    return a.ctypes.data_as(ctypes.POINTER(t))


def kernels(lang):
    """{kernel name: callable} for a ready backend, else {}."""
    h = _LIBS.get(lang)
    if h is None:
        return {}

    def osc(phase0, freq, n, sr, amp=1.0, meum=1.0):
        out = np.empty(int(n), dtype=np.float32)
        h.gbh_osc_fill(float(phase0), float(freq), int(n), float(sr), float(amp), float(meum), _ptr(out, ctypes.c_float))
        return out

    def fold(x, depth):
        x = np.ascontiguousarray(np.asarray(x, dtype=np.float64).ravel())
        out = np.empty(x.size, dtype=np.float32)
        h.gbh_wavefold(_ptr(x, ctypes.c_double), x.size, float(depth), _ptr(out, ctypes.c_float))
        return out

    def clip(x, gain=1.0):
        x = np.ascontiguousarray(np.asarray(x, dtype=np.float32).ravel())
        out = np.empty(x.size, dtype=np.float32)
        h.gbh_hardclip(_ptr(x, ctypes.c_float), x.size, float(gain), _ptr(out, ctypes.c_float))
        return out

    def ca(rule, width, steps):
        w, s = int(width), int(steps)
        out = np.empty((s, w), dtype=np.int8); row = np.empty(w, dtype=np.int8); nxt = np.empty(w, dtype=np.int8)
        h.gbh_ca_evolve(int(rule), w, s, _ptr(out, ctypes.c_int8), _ptr(row, ctypes.c_int8), _ptr(nxt, ctypes.c_int8))
        return out
    return {"osc_fill": osc, "wavefold": fold, "hardclip": clip, "ca_evolve": ca}
