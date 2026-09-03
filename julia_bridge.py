"""Production Python↔Julia bridge for Groovebox's canonical DSP kernels.

Python remains the public/state-management API. Julia is an optional execution
backend and must preserve the Python reference semantics.  The bridge therefore
uses persistent Julia oscillator objects, synchronizes only the canonical state
fields, and exposes an explicit parity test helper.
"""
from __future__ import annotations

import math
import os
import threading
import weakref
from typing import Any, Optional, Sequence, Tuple

import numpy as np

_JULIA_WANTED = os.environ.get("GROOVEBOX_JULIA", "1").strip().lower() not in {
    "0", "false", "no", "off"
}
_jl = None
_jl_mod = None
_jl_ready = False
_jl_error: Optional[str] = None
_jl_lock = threading.RLock()


def julia_available() -> bool:
    return _jl_ready


def julia_status() -> str:
    if _jl_ready:
        return "active"
    if _jl_error:
        return f"unavailable: {_jl_error}"
    return "not initialized" if _JULIA_WANTED else "disabled (GROOVEBOX_JULIA=0)"


def _init_julia() -> bool:
    global _jl, _jl_mod, _jl_ready, _jl_error
    if _jl_ready:
        return True
    if not _JULIA_WANTED:
        _jl_error = "disabled by env"
        return False
    with _jl_lock:
        if _jl_ready:
            return True
        try:
            from juliacall import Main as jl  # type: ignore
            root = os.path.dirname(os.path.abspath(__file__))
            julia_proj = os.path.join(root, "julia")
            jl.seval("using Pkg")
            jl.seval(f'Pkg.activate(raw"{julia_proj}")')
            jl.seval("Pkg.instantiate()")
            jl.seval("using GrooveboxMeumOT")
            _jl, _jl_mod = jl, jl.GrooveboxMeumOT
            _jl_ready, _jl_error = True, None
            return True
        except Exception as exc:
            _jl = _jl_mod = None
            _jl_ready = False
            _jl_error = f"Julia package load failed: {exc}"
            return False

try:
    _init_julia()
except Exception:
    pass


def _call(name: str, *args):
    if not _jl_ready and not _init_julia():
        return None
    try:
        return getattr(_jl_mod, name)(*args)
    except Exception:
        return None


def jl_ot_prod(a: float, b: float) -> Optional[float]:
    r = _call("ot_prod", float(a), float(b))
    return None if r is None else float(r)


def jl_eqr_isn(x: float) -> Optional[float]:
    r = _call("eqr_isn", float(x))
    return None if r is None else float(r)


def jl_eqr_ics(x: float) -> Optional[float]:
    r = _call("eqr_ics", float(x))
    return None if r is None else float(r)


def jl_eqr_tensor_audio(sample: float, d_char: float, theta_char: float, t: float = 0.0):
    r = _call("eqr_tensor_audio", float(sample), float(d_char), float(theta_char), float(t))
    if r is None:
        return None
    return tuple(float(r[i]) for i in range(4))


def jl_eqr_tensor_step(sample: float, neighbours: Sequence[float], t: float = 0.0):
    r = _call("eqr_tensor_step", float(sample), [float(v) for v in (neighbours or [])], float(t))
    if r is None:
        return None
    return tuple(float(r[i]) for i in range(4))


def set_julia_operator_theory(enabled: bool) -> bool:
    """Keep Julia's shared engine flag aligned with Python's canonical flag."""
    r = _call("set_operator_theory!", bool(enabled))
    return r is not None


class JuliaMeumOscillator:
    """Persistent Julia oscillator mirroring MeumModulatedOscillator."""

    def __init__(self, sample_rate: float = 44100.0, frequency: float = 440.0):
        if not _jl_ready and not _init_julia():
            raise RuntimeError(f"Julia not available: {_jl_error}")
        self._o = _jl_mod.MeumOscillator(float(sample_rate), float(frequency))
        self._last_params: Optional[tuple] = None

    @staticmethod
    def _params(py_osc: Any) -> tuple:
        # Values are already constrained by Python's set_params contract; clamp
        # here as a defensive boundary for callers that mutate attributes.
        return (
            float(getattr(py_osc, "sample_rate", 44100.0)),
            max(0.0, float(getattr(py_osc, "frequency", 440.0))),
            float(getattr(py_osc, "phase_shift", 0.0)),
            float(np.clip(getattr(py_osc, "am_depth", 0.0), 0.0, 1.0)),
            max(0.0, float(getattr(py_osc, "am_rate", 1.0))),
            float(np.clip(getattr(py_osc, "fm_depth", 0.0), -0.95, 0.95)),
            max(0.0, float(getattr(py_osc, "fm_rate", 1.0))),
            float(np.clip(getattr(py_osc, "pm_depth", 0.0), -math.pi, math.pi)),
            max(0.0, float(getattr(py_osc, "pm_rate", 1.0))),
            float(np.clip(getattr(py_osc, "pm_feedback", 0.0), -1.0, 1.0)),
            float(np.clip(getattr(py_osc, "meum_depth", 0.0), 0.0, 1.0)),
            str(getattr(py_osc, "waveform", "isn")).strip().lower(),
        )

    def sync(self, py_osc: Any) -> None:
        o = self._o
        params = self._params(py_osc)
        if params != self._last_params:
            (sr, freq, phase_shift, am_depth, am_rate, fm_depth, fm_rate,
             pm_depth, pm_rate, pm_feedback, meum_depth, wf) = params
            o.sample_rate = sr
            o.frequency = freq
            o.phase_shift = phase_shift
            o.am_depth = am_depth
            o.am_rate = am_rate
            o.fm_depth = fm_depth
            o.fm_rate = fm_rate
            o.pm_depth = pm_depth
            o.pm_rate = pm_rate
            o.pm_feedback = pm_feedback
            o.meum_depth = meum_depth
            o.waveform = _jl.seval(f":{wf}") if wf.isidentifier() else _jl.seval(":isn")
            self._last_params = params
        # State belongs to Python's oscillator because it is the public object.
        o.phase = float(getattr(py_osc, "phase", 0.0))
        o.sample_index = int(getattr(py_osc, "sample_index", 0))

    def pull_state(self, py_osc: Any) -> None:
        py_osc.phase = float(self._o.phase)
        py_osc.sample_index = int(self._o.sample_index)
        py_osc.frequency = float(self._o.frequency)

    def render(self, py_osc: Any, num_samples: int, amplitude: float = 1.0,
               frequency: Optional[float] = None) -> np.ndarray:
        self.sync(py_osc)
        if frequency is not None:
            self._o.frequency = max(0.0, float(frequency))
        n = int(num_samples)
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        out = np.asarray(getattr(_jl_mod, "render!")(self._o, n), dtype=np.float32)
        if amplitude != 1.0:
            out = out * float(amplitude)
        self.pull_state(py_osc)
        return np.ascontiguousarray(out, dtype=np.float32)


_osc_cache: weakref.WeakKeyDictionary[Any, JuliaMeumOscillator] = weakref.WeakKeyDictionary()
_osc_cache_lock = threading.RLock()


def render_meum_oscillator(py_osc: Any, num_samples: int, amplitude: float = 1.0,
                           frequency: Optional[float] = None) -> Optional[np.ndarray]:
    if not _jl_ready and not _init_julia():
        return None
    try:
        with _osc_cache_lock:
            wrapper = _osc_cache.get(py_osc)
            if wrapper is None:
                wrapper = JuliaMeumOscillator(
                    getattr(py_osc, "sample_rate", 44100.0),
                    getattr(py_osc, "frequency", 440.0),
                )
                _osc_cache[py_osc] = wrapper
        return wrapper.render(py_osc, num_samples, amplitude=amplitude, frequency=frequency)
    except Exception:
        return None


def parity_report(py_osc: Any, blocks=(1, 7, 64, 257), tolerance=3e-6) -> dict:
    """Compare Python reference rendering with Julia for deterministic blocks.

    The Python oscillator is cloned by copying its scalar state, so the check
    does not mutate the caller.  A small tolerance is used because libm/JULIA
    transcendental implementations need not be bit-identical to CPython.
    """
    if not julia_available():
        return {"available": False, "passed": False, "error": julia_status()}
    try:
        import copy
        ref = copy.copy(py_osc)
        candidate = copy.copy(py_osc)
        worst = 0.0
        rms = 0.0
        count = 0
        for n in blocks:
            a = ref.render(int(n))
            b = render_meum_oscillator(candidate, int(n))
            if b is None or len(a) != len(b):
                return {"available": True, "passed": False, "error": "Julia render unavailable"}
            d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
            if d.size:
                worst = max(worst, float(np.max(np.abs(d))))
                rms += float(np.sum(d * d))
                count += d.size
        rms = math.sqrt(rms / count) if count else 0.0
        return {"available": True, "passed": worst <= tolerance, "max_abs": worst,
                "rms": rms, "tolerance": tolerance}
    except Exception as exc:
        return {"available": True, "passed": False, "error": str(exc)}


def patch_groovebox_module(mod: Any) -> bool:
    """Install optional Julia acceleration while retaining Python as fallback."""
    if not _init_julia():
        return False
    try:
        set_julia_operator_theory(bool(getattr(mod, "OP_THEORY_ENABLED", True)))
    except Exception:
        pass

    Osc = getattr(mod, "MeumModulatedOscillator", None)
    if Osc is not None and not getattr(Osc, "_julia_patched", False):
        orig_render = Osc.render

        def _hybrid_render(self, num_samples, amplitude=1.0, frequency=None):
            out = render_meum_oscillator(self, num_samples, amplitude=amplitude, frequency=frequency)
            return out if out is not None else orig_render(self, num_samples, amplitude=amplitude, frequency=frequency)

        Osc.render = _hybrid_render
        Osc._julia_patched = True
        Osc._julia_orig_render = orig_render

    orig_eta = getattr(mod, "eqr_tensor_audio", None)
    if orig_eta is not None and not getattr(orig_eta, "_julia_wrapped", False):
        def eqr_tensor_audio_hybrid(sample, d_char, theta_char, t=0.0):
            r = jl_eqr_tensor_audio(sample, d_char, theta_char, t)
            return r if r is not None else orig_eta(sample, d_char, theta_char, t)
        eqr_tensor_audio_hybrid._julia_wrapped = True
        mod.eqr_tensor_audio = eqr_tensor_audio_hybrid

    return True
