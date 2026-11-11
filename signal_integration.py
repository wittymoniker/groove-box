"""signal_integration.py — GROOVEBOX_R32_DATAFORM_20261109

The synth's rule for anything it cannot predict: *integrate it into a predictable
dataform first*.  Stochastic or unpredictable inputs (live audio RMS, a camera, a mic,
an RNG, a user wiggling a control) never reach the compositional maths raw.  They pass
through one of these mechanisms, each deterministic and dissectable:

    integrate(x, tau)            leaky integrator (continuous-time low-pass, tau seconds)
    quantize(x, lattice)         snap to a lattice (musical values: semitones, steps, MEUM powers)
    converge(x, target, rate)    rate-limited approach — the value can only move so fast
    predict(series, horizon)     AR(2) one-step-ahead extrapolation of a short history
    det_rand(seed, index)        deterministic "noise": a hash, never time or OS randomness
    dataform(x, mode)            the whole policy in one call

Everything is pure Python / NumPy, stateless, and usable from a seed program, a render
worker or the UI thread.  ``Integrator`` / ``Predictor`` keep state for streaming use.
"""
from __future__ import annotations

import hashlib
import math
import struct

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None

MEUM_DEFAULT = 2.0 ** (1.0 / 12.0)


# ---------------------------------------------------------------------------
# stateless helpers (seed-program vocabulary)
# ---------------------------------------------------------------------------
def integrate(x, tau=0.25, prev=None, dt=1.0 / 60.0):
    """One step of a leaky integrator: prev + (x - prev) * (1 - exp(-dt / tau)).

    With no ``prev`` the input is returned unchanged (the integrator starts *at* the
    signal, so the first value is never a transient).
    """
    x = float(x)
    if prev is None:
        return x
    tau = max(1e-6, float(tau))
    a = 1.0 - math.exp(-max(0.0, float(dt)) / tau)
    return float(prev) + (x - float(prev)) * a


def quantize(x, lattice=1.0, origin=0.0):
    """Snap ``x`` to the nearest ``origin + k * lattice`` (lattice 0 → unchanged)."""
    x, lattice, origin = float(x), float(lattice), float(origin)
    if lattice == 0.0 or not math.isfinite(lattice):
        return x
    return origin + lattice * math.floor((x - origin) / lattice + 0.5)


def quantize_log(x, base=MEUM_DEFAULT, ref=1.0):
    """Snap a ratio to the nearest power of ``base`` (semitones by default)."""
    x, base, ref = float(x), float(base), float(ref)
    if x <= 0.0 or ref <= 0.0 or base <= 0.0 or base == 1.0:
        return x
    k = math.floor(math.log(x / ref) / math.log(base) + 0.5)
    return ref * base ** k


def converge(x, target, rate=0.1):
    """Move ``x`` toward ``target`` by at most ``rate`` (a slew limiter)."""
    x, target, rate = float(x), float(target), abs(float(rate))
    d = target - x
    if abs(d) <= rate:
        return target
    return x + math.copysign(rate, d)


def predict(series, horizon=1):
    """AR(2) extrapolation of the last three samples; falls back gracefully.

    series: sequence of numbers (oldest first).  horizon: steps ahead (≥1).
    Constant / short histories return the last value; a 2-sample history is linear.
    """
    vals = [float(v) for v in (series or []) if isinstance(v, (int, float)) and math.isfinite(float(v))]
    if not vals:
        return 0.0
    h = max(1, int(horizon))
    if len(vals) == 1:
        return vals[-1]
    if len(vals) == 2:
        return vals[-1] + (vals[-1] - vals[-2]) * h
    y0, y1, y2 = vals[-3], vals[-2], vals[-1]
    # Fit y[n] = a*y[n-1] + b*y[n-2] on the last three points (least squares with two eqns).
    den = y1 * y1 + y0 * y0
    if den < 1e-18:
        return y2
    a = (y2 * y1 + y1 * y0) / den
    b = (y2 * y0 - y1 * y1) / den if abs(y0) > 1e-12 else 0.0
    # Stability: keep the roots inside the unit circle, otherwise damp toward linear.
    if abs(a) + abs(b) > 1.999:
        s = 1.999 / (abs(a) + abs(b))
        a *= s
        b *= s
    p1, p2 = y1, y2
    out = y2
    for _ in range(h):
        out = a * p2 + b * p1
        p1, p2 = p2, out
    return float(out) if math.isfinite(out) else y2


def det_rand(seed, index=0, lo=0.0, hi=1.0):
    """Deterministic pseudo-random number in [lo, hi) from (seed, index): a hash, so the
    same composition gives the same 'noise' on every machine and every run."""
    try:
        s = float(seed)
    except Exception:
        s = 0.0
    key = struct.pack("<dq", s, int(index))
    h = hashlib.blake2b(key, digest_size=8).digest()
    u = int.from_bytes(h, "little") / 2.0 ** 64
    return float(lo) + (float(hi) - float(lo)) * u


def det_noise(seed, t, rate=1.0):
    """Value-continuous deterministic noise over time (linear interpolation of det_rand)."""
    x = float(t) * float(rate)
    i = math.floor(x)
    f = x - i
    a, b = det_rand(seed, i, -1.0, 1.0), det_rand(seed, i + 1, -1.0, 1.0)
    f = f * f * (3.0 - 2.0 * f)
    return a + (b - a) * f


def dataform(x, mode="integrate", **kw):
    """The policy in one call: 'integrate' | 'quantize' | 'quantize_log' | 'converge' | 'predict'."""
    mode = str(mode or "integrate").lower()
    if mode == "quantize":
        return quantize(x, kw.get("lattice", 1.0), kw.get("origin", 0.0))
    if mode == "quantize_log":
        return quantize_log(x, kw.get("base", MEUM_DEFAULT), kw.get("ref", 1.0))
    if mode == "converge":
        return converge(x, kw.get("target", 0.0), kw.get("rate", 0.1))
    if mode == "predict":
        return predict(x if isinstance(x, (list, tuple)) else [x], kw.get("horizon", 1))
    return integrate(x, kw.get("tau", 0.25), kw.get("prev"), kw.get("dt", 1.0 / 60.0))


# ---------------------------------------------------------------------------
# streaming (stateful) forms for the Live Player / carrier / camera inputs
# ---------------------------------------------------------------------------
class Integrator:
    """Leaky integrator with separate attack / release — an envelope follower."""
    __slots__ = ("value", "attack", "release", "_init")

    def __init__(self, attack=0.01, release=0.2):
        self.value = 0.0
        self.attack = max(1e-6, float(attack))
        self.release = max(1e-6, float(release))
        self._init = False

    def step(self, x, dt):
        x = abs(float(x))
        if not self._init:
            self.value, self._init = x, True
            return x
        tau = self.attack if x > self.value else self.release
        self.value = integrate(x, tau, self.value, dt)
        return self.value

    def block(self, samples, sr):
        """Envelope of a block (numpy array) → one value per sample (vectorised recurrence)."""
        if np is None or samples is None:
            return None
        x = np.abs(np.asarray(samples, dtype=np.float64)).ravel()
        if x.size == 0:
            return x
        dt = 1.0 / max(1.0, float(sr))
        aa = 1.0 - math.exp(-dt / self.attack)
        ar = 1.0 - math.exp(-dt / self.release)
        out = np.empty_like(x)
        v = self.value if self._init else float(x[0])
        for i in range(x.size):        # recurrence; blocks are short (≤ a few thousand samples)
            xi = x[i]
            v += (xi - v) * (aa if xi > v else ar)
            out[i] = v
        self.value, self._init = float(v), True
        return out


class Predictor:
    """Keeps a short history and predicts ahead (for look-ahead gain / scene changes)."""
    __slots__ = ("hist", "size")

    def __init__(self, size=8):
        self.size = max(3, int(size))
        self.hist = []

    def push(self, x):
        try:
            x = float(x)
        except Exception:
            return
        if math.isfinite(x):
            self.hist.append(x)
            if len(self.hist) > self.size:
                del self.hist[0]

    def ahead(self, horizon=1):
        return predict(self.hist, horizon)

    def trend(self):
        if len(self.hist) < 2:
            return 0.0
        return self.hist[-1] - self.hist[-2]


SEED_VOCABULARY = {
    "integrate": integrate, "quantize": quantize, "quantize_log": quantize_log, "converge": converge,
    "predict": predict, "det_rand": det_rand, "det_noise": det_noise, "dataform": dataform,
}
