"""GROOVEBOX_R31_MEUM_FX_CORE_20261109 — the hardcoded FX, in pure Python/NumPy.

Groovebox applies exactly five effects to its own audio tracks, in this fixed order:

    1. PKP Envelope          (book-isn step envelope / tempo gate)
    2. Fractallizer          (contextual sub/superharmonic companion)
    3. EQR                   (Equation-of-Reality origin-z contribution mix)
    4. Finite Infinity Meum ∞M HyperDrive (Meum-spaced resonant drive)
    5. Master Hard Clipper   (volume × drive → hard ceiling, no knee)

There is no soft limiter, no soft clip, no compressor, no reverb, no chorus and
no hidden filter anywhere in this module.  Everything is built from the
project's own onboard maths:

* trigonometry uses the author-series kernels (range-reduced Maclaurin sums,
  no ``math.sin`` / ``np.sin`` calls), so Trigonometry Engine ON/OFF never
  retunes a sound;
* every division goes through :func:`ot_div`, the Operator-Theory division with
  an explicit zero policy (no hidden epsilon), and 0/0 = 1 where OT mode asks;
* constants come from :mod:`meum_constants` (one binary64 source of truth).

Everything here is SciPy-free, so a sound renders bit-for-bit the same on the
sOS appliance, Fedora, Windows (.exe) and macOS.  The previous SciPy-only paths
(per-step biquad EQ, sidechain key envelope, K-weighted loudness meter and the
Live Player filter sweep) either changed sound or silently did nothing when
SciPy was absent; they now route through the functions below.

Realtime processors (:class:`MeumPerformanceRack`) are block-based, keep their
own phase/state between blocks and are exact bypasses at 0.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

import numpy as np

try:
    from meum_constants import MEUM, MEUM_INV, MEUM_MINUS_1, MEUM_NORM, PHI, PHI_INV
except Exception:  # pragma: no cover - meum_constants ships with every build
    MEUM = 1.1975807343385265
    MEUM_INV = 1.0 / MEUM
    MEUM_MINUS_1 = MEUM - 1.0
    MEUM_NORM = MEUM_MINUS_1 / MEUM
    PHI = (1.0 + math.sqrt(5.0)) / 2.0
    PHI_INV = PHI - 1.0

FX_ORDER = ("pkp_envelope", "fractallizer", "eqr", "fi_hyperdrive", "master_hardclip")
PERMITTED_FX = frozenset(FX_ORDER)
FX_LABELS = {
    "pkp_envelope": "PKP Envelope",
    "fractallizer": "Fractallizer",
    "eqr": "EQR",
    "fi_hyperdrive": "∞M HyperDrive",
    "master_hardclip": "Master Hard Clipper",
}

# Legacy effect names → the permitted effect that now does that musical job.
# (Used to migrate old Live Jam / Live Player FX settings saved in projects.)
LEGACY_FX_MAP = {
    "Filter": "fractallizer", "filter": "fractallizer",
    "Chorus": "fractallizer", "chorus": "fractallizer",
    "Delay": "pkp_envelope", "delay": "pkp_envelope", "Echo": "eqr", "echo": "eqr",
    "Reverb": "eqr", "reverb": "eqr",
    "Drive": "fi_hyperdrive", "drive": "fi_hyperdrive",
    "Crush": "fi_hyperdrive", "crush": "fi_hyperdrive",
    "Gate": "pkp_envelope", "gate": "pkp_envelope",
}

SERIES_PI = 3.14159265358979323846264338327950288419716939937510
SERIES_TAU = 2.0 * SERIES_PI
_HALF_PI = SERIES_PI / 2.0


# ---------------------------------------------------------------------------
# Onboard maths: author-series trig + Operator-Theory division
# ---------------------------------------------------------------------------
def _reduce(x):
    a = np.asarray(x, dtype=np.float64)
    with np.errstate(invalid="ignore"):
        return np.remainder(a + SERIES_PI, SERIES_TAU) - SERIES_PI


def series_sin(x, terms: int = 12):
    """Author-series sine: range reduction to [-π/2, π/2] + Maclaurin sum.

    12 terms on |x| ≤ π/2 leave a truncation error below 1e-19 (binary64-exact).
    """
    a = _reduce(x)
    a = np.where(a > _HALF_PI, SERIES_PI - a, np.where(a < -_HALF_PI, -SERIES_PI - a, a))
    a2 = a * a
    term = a.copy()
    total = a.copy()
    for n in range(1, int(terms)):
        term *= -a2 / ((2.0 * n) * (2.0 * n + 1.0))
        total += term
    return total


def series_cos(x, terms: int = 12):
    """Book identity cos(γ) = sin(γ + π/2) through the same series kernel."""
    return series_sin(np.asarray(x, dtype=np.float64) + _HALF_PI, terms)


def book_isn(x):
    """Book isn(γ) = 1 − cos(γ) (γ²/2! − γ⁴/4! + …)."""
    return 1.0 - series_cos(x)


def ot_band(x):
    """OT band function B(x)."""
    a = np.abs(np.asarray(x, dtype=np.float64))
    return np.where(a <= 1.0, 1.0, np.where(a <= 2.0, 2.0, np.where(a <= 3.0, 3.0, 1.0)))


def ot_div(a, b, zero: str = "zero"):
    """Operator-Theory division with an explicit zero policy.

    |a/b| = |a|/|b| with the sign of ``a``.  Division by zero never injects an
    epsilon; the caller picks what a zero denominator means:

    * ``"zero"``      → 0       (DSP gain contexts: no signal → no gain)
    * ``"one"``       → 1       (ratio contexts: unchanged)
    * ``"numerator"`` → a       (pass-through contexts)
    * ``"ot"``        → OT mode: 0/0 = 1, a/0 = ±inf
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    nz = b != 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.abs(a) / np.where(nz, np.abs(b), 1.0)
    q = np.copysign(q, a)
    if zero == "one":
        fill = np.ones_like(q)
    elif zero == "numerator":
        fill = a * np.ones_like(q)
    elif zero == "ot":
        fill = np.where(a == 0.0, 1.0, np.copysign(np.inf, a))
    else:
        fill = np.zeros_like(q)
    out = np.where(nz, q, fill)
    return out.item() if out.ndim == 0 else out


def ot_mul(a, b):
    """OT multiplication: |ab| magnitude, project sign rule, OT_MUL(0,0)=1."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    mag = np.abs(a * b)
    both_pos = (a > 0) & (b > 0)
    out = np.where(both_pos, mag, -mag)
    out = np.where((a == 0) & (b == 0), 1.0, np.where((a == 0) | (b == 0), 0.0, out))
    return out.item() if out.ndim == 0 else out


def _f32(x):
    return np.ascontiguousarray(np.asarray(x, dtype=np.float32).ravel())


# ---------------------------------------------------------------------------
# 1. PKP Envelope
# ---------------------------------------------------------------------------
def pkp_step_shape(u, decay: float = 0.5):
    """Book-isn step envelope over one step (u ∈ [0,1]); edges at 0, crest 1.

    decay 0 → one isn cycle; 0.5 → isn attack, flat crest, isn release;
    1 → isn attack then sustain to the step end.
    """
    u = np.clip(np.asarray(u, dtype=np.float64), 0.0, 1.0)
    d = float(np.clip(decay, 0.0, 1.0))
    cyc = 0.5 * book_isn(u * SERIES_TAU)
    edge = 0.25 + 0.25 * d  # attack/release width grows toward sustain
    att = np.clip(u / edge, 0.0, 1.0)
    rel = np.clip((1.0 - u) / edge, 0.0, 1.0)
    att_s = 0.5 * book_isn(att * SERIES_PI)
    rel_s = 0.5 * book_isn(rel * SERIES_PI)
    two = np.minimum(att_s, rel_s)
    sus = att_s
    if d <= 0.5:
        w = d / 0.5
        return (1.0 - w) * cyc + w * two
    w = (d - 0.5) / 0.5
    return (1.0 - w) * two + w * sus


def pkp_gate(n: int, sr: float, bpm: float, division_beats: float, depth: float,
             phase0: int = 0, decay: float = 0.5):
    """Tempo-synced PKP gate gain curve (replaces the old square 'Gate').

    Returns ``(gain, next_phase)``.  depth 0 → exactly 1.0 everywhere.
    """
    n = int(n)
    depth = float(np.clip(depth, 0.0, 1.0))
    per = max(32, int(60.0 / max(20.0, float(bpm)) * float(sr) * float(division_beats)))
    ph = (int(phase0) + np.arange(n)) % per
    if depth <= 0.0:
        return np.ones(n, dtype=np.float32), int((int(phase0) + n) % per)
    env = pkp_step_shape(ph / float(per), decay)
    gain = 1.0 - depth * (1.0 - env)
    return gain.astype(np.float32), int((int(phase0) + n) % per)


# ---------------------------------------------------------------------------
# 2. Fractallizer (sub ↔ super tilt) — replaces every filter sweep
# ---------------------------------------------------------------------------
FRACTAL_SUB = (1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 6)
FRACTAL_SUPER = (2.0, 3.0, 4.0, 5.0, 6.0)
FRACTAL_W = (0.14, 0.11, 0.09, 0.07, 0.05)


def fractal_tilt_weights(tilt: float):
    """Weights for the 10 Fractallizer partials at a tilt in [-1, 1].

    −1 = only the subharmonic family (darker, heavier), +1 = only the
    superharmonic family (brighter, airier), 0 = the balanced Fractallizer.
    The total weight is constant, so tilting never changes loudness on average.
    """
    t = float(np.clip(tilt, -1.0, 1.0))
    sub = 1.0 - max(0.0, t)
    sup = 1.0 + min(0.0, t)
    total = 2.0
    norm = ot_div(total, sub + sup, zero="one")
    ws = tuple(w * sub * norm for w in FRACTAL_W)
    wp = tuple(w * sup * norm for w in FRACTAL_W)
    return ws + wp, FRACTAL_SUB + FRACTAL_SUPER


def estimate_f0(block, sr: float, fallback: float = 110.0) -> float:
    """Zero-crossing f0 estimate for one block (no FFT, no filter)."""
    x = np.asarray(block, dtype=np.float64).ravel()
    if x.size < 8:
        return float(fallback)
    zc = np.flatnonzero(np.diff(np.signbit(x)))
    if zc.size < 2:
        return float(fallback)
    period = float(np.median(np.diff(zc))) * 2.0
    f0 = ot_div(float(sr), max(period, 2.0), zero="zero")
    return float(min(max(40.0, f0), float(sr) * 0.45))


def fractallize(x, sr: float, amount: float, tilt: float = 0.0, block: int = 512):
    """Offline Fractallizer with tilt.  amount 0..1 → wet 0..50 % (Fractallizer cap)."""
    x = np.asarray(x, dtype=np.float64).ravel()
    n = x.size
    wet = 0.5 * float(np.clip(amount, 0.0, 1.0))
    if n < 16 or wet <= 0.0:
        return _f32(x)
    rack = _FractalState()
    out = np.empty(n, dtype=np.float32)
    for i in range(0, n, block):
        seg = x[i:i + block]
        out[i:i + seg.size] = rack.process(seg, sr, wet, tilt)
    return out


class _FractalState:
    """Phase-continuous block Fractallizer (used offline and in realtime)."""

    def __init__(self):
        self.phase = 0.0
        self.env = 0.0
        self.f0 = 110.0

    def process(self, seg, sr, wet, tilt):
        seg = np.asarray(seg, dtype=np.float64)
        m = seg.size
        if m == 0:
            return seg.astype(np.float32)
        if wet <= 0.0:
            return seg.astype(np.float32)
        f0 = estimate_f0(seg, sr, self.f0)
        f0 = 0.7 * self.f0 + 0.3 * f0           # glide: no zipper on pitch changes
        env = float(np.mean(np.abs(seg)))
        envs = np.linspace(self.env, env, m, endpoint=False)
        ph = self.phase + SERIES_TAU * f0 / float(sr) * np.arange(1, m + 1, dtype=np.float64)
        weights, ratios = fractal_tilt_weights(tilt)
        comp = np.zeros(m, dtype=np.float64)
        for w, r in zip(weights, ratios):
            if w:
                comp += w * series_sin(ph * r)
        self.phase = float(np.remainder(ph[-1], SERIES_TAU * 60.0))  # 60 = lcm of 1..6
        self.env = env
        self.f0 = f0
        return (seg + wet * comp * envs).astype(np.float32)


# ---------------------------------------------------------------------------
# 3. EQR (origin-z contribution)
# ---------------------------------------------------------------------------
def eqr_mix(x, activation: float, z_fn: Optional[Callable] = None, t0: float = 0.0, t1: float = 1.0):
    """EQR contribution mix (activation 0..1 → wet 0..50 %).

    ``z_fn(sample, d_char, t)`` is the project closed form
    ``groovebox.eqr_tensor_audio_z_vec``; it is injected so this module stays
    import-light.  Without it a series-only reduction of the same identities
    is used (P from isn, E = isn(θ)/d via OT division, D omitted).
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    n = x.size
    wet = 0.5 * float(np.clip(activation, 0.0, 1.0))
    if n == 0 or wet <= 0.0:
        return _f32(x)
    win = max(8, min(256, n // 64 or 8))
    k = np.ones(win, dtype=np.float64) / float(win)
    d_char = np.convolve(np.abs(x), k, mode="same")
    ctrl = int(min(128, max(4, n // 128)))
    idx = np.linspace(0, n - 1, ctrl).astype(np.int64)
    tt = np.linspace(float(t0), float(t1), ctrl)
    if z_fn is not None:
        try:
            z = np.asarray(z_fn(x[idx], d_char[idx], tt), dtype=np.float64)
        except Exception:
            z = None
    else:
        z = None
    if z is None:
        P = 0.5 * (book_isn(d_char[idx]) + book_isn(tt))
        E = ot_div(book_isn(x[idx]), d_char[idx], zero="zero")
        z = P * E
    z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
    zf = np.interp(np.arange(n, dtype=np.float64), idx.astype(np.float64), z)
    return ((1.0 - wet) * x + wet * zf * x).astype(np.float32)


# ---------------------------------------------------------------------------
# 4. Finite Infinity Meum ∞M HyperDrive
# ---------------------------------------------------------------------------
FINITE_INFINITY_I = 134964356


def hyperdrive_frequency(finite_coordinate: float) -> float:
    return max(0.05, float(MEUM_MINUS_1) * (1.0 + float(finite_coordinate) * float(MEUM)))


def fi_hyperdrive(x, sr: float, drive: float, resonance: float, phase0: float = 0.0,
                  finite_coordinate: float = 0.0, ot_flip: bool = False, start_sample: int = 0):
    """Meum-spaced resonant drive.  drive 0 → exact bypass.  No clamp (the
    Master Hard Clipper downstream is the only ceiling)."""
    x = np.asarray(x, dtype=np.float64).ravel()
    drive = max(0.0, float(drive))
    res = max(0.0, float(resonance))
    if x.size == 0 or drive <= 0.0:
        return _f32(x)
    tt = (float(start_sample) + np.arange(x.size, dtype=np.float64)) / max(float(sr), 1.0)
    ph = float(phase0) + SERIES_TAU * hyperdrive_frequency(finite_coordinate) * tt
    if ot_flip:
        ph = -ph
    resonant = float(MEUM_MINUS_1) * series_sin(ph) + float(MEUM_INV) * series_cos(ph)
    y = x * (1.0 + drive * res * resonant)
    y += (drive * float(MEUM_MINUS_1) * 0.125) * (x ** 3)
    return y.astype(np.float32)


# ---------------------------------------------------------------------------
# 5. Master Hard Clipper
# ---------------------------------------------------------------------------
def hard_clip(x, volume: float = 1.0, ratio_pct: float = 0.0, ceiling: float = 1.0):
    """volume × drive(1 + 1.5·ratio) → hard ceiling.  Not a limiter: no knee,
    no lookahead, no gain riding."""
    r = float(np.clip(float(ratio_pct) / 100.0, 0.0, 1.0))
    g = np.float32(float(volume) * (1.0 + 1.5 * r))
    c = np.float32(abs(float(ceiling)))
    return np.clip(np.asarray(x, dtype=np.float32) * g, -c, c).astype(np.float32)


# ---------------------------------------------------------------------------
# Filter-free helpers that replace the old SciPy-only paths
# ---------------------------------------------------------------------------
def peak_decay_envelope(x, sr: float, release_s: float = 0.080, chunk: int = 2048):
    """Instant-attack / exponential-release key envelope, vectorised.

    rel[i] = max_{j≤i} x[j]·a^(i−j) computed chunk-wise as a^i · cummax(x·a^−j),
    re-based every chunk so a^−j never overflows.  Same on every platform.
    """
    x = np.maximum(np.asarray(x, dtype=np.float64).ravel(), 0.0)
    n = x.size
    if n == 0:
        return x.astype(np.float32)
    a = math.exp(-1.0 / max(1.0, float(release_s) * float(sr)))
    la = math.log(a)
    out = np.empty(n, dtype=np.float64)
    carry = 0.0
    j = np.arange(chunk, dtype=np.float64)
    up = np.exp(-la * j)
    down = np.exp(la * j)
    for i in range(0, n, chunk):
        seg = x[i:i + chunk]
        m = seg.size
        cm = np.maximum.accumulate(seg * up[:m]) * down[:m]
        cm = np.maximum(cm, carry * down[:m] * a)
        out[i:i + m] = cm
        carry = float(cm[-1])
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def bell_gain_db(freqs, f0: float, q: float, gain_db: float):
    """Zero-phase bell in log-frequency using the book isn window.

    Width = one octave / q either side; the isn half-cycle gives a smooth,
    finite-support bell (exactly 0 dB outside its band — no ringing tails).
    """
    f = np.maximum(np.asarray(freqs, dtype=np.float64), 1.0)
    width = max(0.05, 1.0 / max(0.1, float(q)))
    d = np.abs(np.log2(f / max(1.0, float(f0)))) / width
    shape = np.where(d < 1.0, 0.5 * book_isn((1.0 - d) * SERIES_PI), 0.0)
    return float(gain_db) * shape


def band_gain_segments(voice, segments, sr: float, fade_s: float = 0.003, pre_s: float = 0.025):
    """Per-step EQ without IIR filters (replaces the SciPy biquad path).

    ``segments`` = iterable of (i0, i1, gain_db, f0, q).  Each step's band delta
    is computed zero-phase in the FFT domain over the step + pre/post roll and
    crossfaded over ``fade_s`` at both edges, so neighbouring steps blend
    without clicks.  Identical with or without SciPy.
    """
    x = np.asarray(voice, dtype=np.float64)
    if x.size < 4:
        return np.asarray(voice, dtype=np.float32)
    mono = x.ndim == 1
    xx = x[:, None] if mono else x
    out = xx.copy()
    n = xx.shape[0]
    pre = int(pre_s * sr)
    fade = max(1, int(fade_s * sr))
    for seg in segments or ():
        try:
            i0, i1, g, f0, q = seg
        except Exception:
            continue
        i0 = max(0, int(i0))
        i1 = min(n, int(i1))
        if i1 - i0 < 2 or abs(float(g)) < 1e-6:
            continue
        p0 = max(0, i0 - pre)
        p1 = min(n, i1 + pre)
        chunk = xx[p0:p1]
        m = chunk.shape[0]
        freqs = np.fft.rfftfreq(m, 1.0 / float(sr))
        gain = np.power(10.0, bell_gain_db(freqs, f0, q, g) / 20.0)[:, None]
        spec = np.fft.rfft(chunk, axis=0)
        delta = np.fft.irfft(spec * (gain - 1.0), n=m, axis=0)[i0 - p0:i1 - p0]
        L = delta.shape[0]
        w = np.ones(L, dtype=np.float64)
        f = min(fade, L // 2)
        if f > 0:
            ramp = 0.5 * book_isn(np.linspace(0.0, SERIES_PI, f, endpoint=False))
            w[:f] = ramp
            w[L - f:] = ramp[::-1]
        out[i0:i1] += delta * w[:, None]
    out = out[:, 0] if mono else out
    return out.astype(np.float32)


def biquad_magnitude(b, a, freqs, sr: float):
    """|H(e^jω)| of a biquad, evaluated with the series kernels."""
    w = SERIES_TAU * np.asarray(freqs, dtype=np.float64) / float(sr)
    c1, s1 = series_cos(w), series_sin(w)
    c2, s2 = series_cos(2 * w), series_sin(2 * w)
    nr = b[0] + b[1] * c1 + b[2] * c2
    ni = -(b[1] * s1 + b[2] * s2)
    dr = a[0] + a[1] * c1 + a[2] * c2
    di = -(a[1] * s1 + a[2] * s2)
    return np.sqrt(ot_div(nr * nr + ni * ni, dr * dr + di * di, zero="zero"))


def apply_magnitude_response(x, mags):
    """Apply a zero-phase magnitude curve (rfft bins) along axis 0."""
    x = np.asarray(x, dtype=np.float64)
    spec = np.fft.rfft(x, axis=0)
    m = np.asarray(mags, dtype=np.float64)
    if spec.ndim == 2:
        m = m[:, None]
    return np.fft.irfft(spec * m, n=x.shape[0], axis=0)


# ---------------------------------------------------------------------------
# Realtime performance rack (Live Player): permitted FX only
# ---------------------------------------------------------------------------
class MeumPerformanceRack:
    """Block-based live rack built only from the hardcoded FX.

    Controls (all 0 = exact bypass):
      ``tilt``       −100..100  Fractallizer sub ↔ super tilt (was the filter sweep)
      ``eqr``        0..100     EQR contribution (was echo)
      ``hyper``      0..100     ∞M HyperDrive depth (was bitcrush)
      ``pkp``        0..100     tempo-synced PKP gate depth (was square gate)
      ``repeat``     beats      beat-repeat of the last division (playback, not DSP)
    Compatible with the old DJChain ``p`` dict keys so saved settings still load.
    """

    def __init__(self, sr, z_fn: Optional[Callable] = None):
        self.sr = int(sr)
        self.bpm = 120.0
        self.z_fn = z_fn
        self.p = {"enabled": True,
                  "filter_enabled": True, "echo_enabled": True, "stutter_enabled": True,
                  "crush_enabled": True, "gate_enabled": True,
                  # legacy names kept as aliases of the new controls
                  "filter": 0.0, "reso": 0.7, "echo": 0.0, "echo_div": 0.5, "echo_fb": 0.45,
                  "stutter": 0.0, "crush": 0.0, "gate": 0.0, "gate_div": 0.25,
                  "pkp_decay": 0.5, "hyper_res": float(MEUM_MINUS_1)}
        L = self.sr * 4
        self._hist = np.zeros(L, dtype=np.float32)
        self._hpos = 0
        self._stut = None
        self._spos = 0
        self._stut_key = 0.0
        self._gphase = 0
        self._samples = 0
        self._frac = _FractalState()

    def _beat(self):
        return 60.0 / max(20.0, float(self.bpm)) * self.sr

    def process(self, x):
        p = self.p
        x = np.asarray(x, dtype=np.float32).ravel()
        n = x.size
        if n == 0 or not p.get("enabled", True):
            self._samples += n
            return x
        L = self._hist.size
        idx = (self._hpos + np.arange(n)) % L
        self._hist[idx] = x
        self._hpos = int((self._hpos + n) % L)
        y = x
        if p.get("stutter_enabled", True) and float(p.get("stutter", 0.0)) > 0:
            seg = max(64, int(self._beat() * float(p["stutter"])))
            if self._stut is None or self._stut_key != p["stutter"]:
                start = (self._hpos - seg) % L
                self._stut = self._hist[(start + np.arange(seg)) % L].copy()
                self._spos = 0
                self._stut_key = p["stutter"]
            j = (self._spos + np.arange(n)) % self._stut.size
            y = self._stut[j]
            self._spos = int((self._spos + n) % self._stut.size)
        else:
            self._stut = None
        # 1. PKP gate
        g = float(p.get("gate", 0.0))
        if p.get("gate_enabled", True) and g > 0.5:
            gain, self._gphase = pkp_gate(n, self.sr, self.bpm, float(p.get("gate_div", 0.25)),
                                          g / 100.0, self._gphase, float(p.get("pkp_decay", 0.5)))
            y = y * gain
        # 2. Fractallizer tilt
        f = float(p.get("filter", 0.0))
        if p.get("filter_enabled", True) and abs(f) > 0.5:
            y = self._frac.process(y, self.sr, 0.5 * min(1.0, abs(f) / 100.0), f / 100.0)
        # 3. EQR
        e = float(p.get("echo", 0.0))
        if p.get("echo_enabled", True) and e > 0.5:
            t0 = (self._samples % self.sr) / float(self.sr)
            y = eqr_mix(y, e / 100.0, self.z_fn, t0, t0 + n / float(self.sr))
        # 4. HyperDrive
        c = float(p.get("crush", 0.0))
        if p.get("crush_enabled", True) and c > 0.5:
            y = fi_hyperdrive(y, self.sr, c / 100.0 * 2.0, float(p.get("hyper_res", MEUM_MINUS_1)) * 4.0,
                              start_sample=self._samples)
        self._samples += n
        return np.asarray(y, dtype=np.float32)

    def active(self):
        p = self.p
        return bool(p.get("enabled", True)) and (
            (p.get("filter_enabled", True) and abs(float(p.get("filter", 0))) > 0.5) or
            (p.get("echo_enabled", True) and abs(float(p.get("echo", 0))) > 0.5) or
            (p.get("crush_enabled", True) and abs(float(p.get("crush", 0))) > 0.5) or
            (p.get("gate_enabled", True) and abs(float(p.get("gate", 0))) > 0.5) or
            (p.get("stutter_enabled", True) and float(p.get("stutter", 0)) > 0))


# ---------------------------------------------------------------------------
# Post-processing toolkit (offline; for takes, clips and exports)
# ---------------------------------------------------------------------------
def measure(x, sr: float):
    """Peak / RMS / crest / DC / clip-density report (no weighting filters)."""
    a = np.asarray(x, dtype=np.float64)
    if a.size == 0:
        return {"peak": 0.0, "rms": 0.0, "crest_db": 0.0, "dc": 0.0, "clip_density": 0.0, "seconds": 0.0}
    peak = float(np.max(np.abs(a)))
    rms = float(np.sqrt(np.mean(a * a)))
    crest = 20.0 * math.log10(ot_div(peak, rms, zero="one")) if peak > 0 else 0.0
    return {"peak": peak, "rms": rms, "crest_db": crest, "dc": float(np.mean(a)),
            "clip_density": float(np.mean(np.abs(a) >= 0.999)),
            "seconds": float(a.shape[0]) / max(1.0, float(sr))}


def remove_dc(x):
    """Subtract the mean (per channel).  A constant offset, not a filter."""
    a = np.asarray(x, dtype=np.float64)
    return (a - np.mean(a, axis=0, keepdims=True)).astype(np.float32)


def peak_normalize(x, target_peak: float = 0.98):
    """One static gain so the peak lands on ``target_peak`` (no limiting)."""
    a = np.asarray(x, dtype=np.float64)
    pk = float(np.max(np.abs(a))) if a.size else 0.0
    g = ot_div(float(target_peak), pk, zero="one")
    return (a * g).astype(np.float32), float(g)


def trim_silence(x, sr: float, threshold: float = 1e-4, pad_s: float = 0.05):
    """Trim leading/trailing digital silence; returns (audio, start, end)."""
    a = np.asarray(x)
    mag = np.abs(a) if a.ndim == 1 else np.max(np.abs(a), axis=1)
    nz = np.flatnonzero(mag > threshold)
    if nz.size == 0:
        return a[:0], 0, 0
    pad = int(pad_s * sr)
    s = max(0, int(nz[0]) - pad)
    e = min(a.shape[0], int(nz[-1]) + pad + 1)
    return a[s:e], s, e


def isn_fade(x, sr: float, fade_in_s: float = 0.0, fade_out_s: float = 0.0):
    """Edit-only book-isn fades for clip edges (never applied to live keys)."""
    a = np.asarray(x, dtype=np.float64).copy()
    n = a.shape[0]
    for secs, rev in ((fade_in_s, False), (fade_out_s, True)):
        k = min(n, int(max(0.0, float(secs)) * sr))
        if k > 1:
            r = 0.5 * book_isn(np.linspace(0.0, SERIES_PI, k))
            r = r[::-1] if rev else r
            if a.ndim == 1:
                (a[n - k:] if rev else a[:k])[...] *= r
            else:
                (a[n - k:] if rev else a[:k])[...] *= r[:, None]
    return a.astype(np.float32)


def render_chain(x, sr: float, settings: dict, z_fn: Optional[Callable] = None, bpm: float = 120.0):
    """Offline pass of the five hardcoded FX in their fixed order.

    ``settings`` keys (all optional, all 0 = off): pkp (0..1), pkp_div (beats),
    pkp_decay, fractal (0..1), tilt (−1..1), eqr (0..1), hyper (0..1),
    hyper_res, volume (default 1), clip_ratio (0..100).
    """
    s = dict(settings or {})
    y = np.asarray(x, dtype=np.float32)
    stereo = y.ndim == 2
    chans = [y[:, c] for c in range(y.shape[1])] if stereo else [y]
    out = []
    for ch in chans:
        z = ch
        if float(s.get("pkp", 0.0)) > 0:
            gain, _ = pkp_gate(z.size, sr, bpm, float(s.get("pkp_div", 0.25)), float(s["pkp"]), 0,
                               float(s.get("pkp_decay", 0.5)))
            z = z * gain
        if float(s.get("fractal", 0.0)) > 0:
            z = fractallize(z, sr, float(s["fractal"]), float(s.get("tilt", 0.0)))
        if float(s.get("eqr", 0.0)) > 0:
            z = eqr_mix(z, float(s["eqr"]), z_fn)
        if float(s.get("hyper", 0.0)) > 0:
            z = fi_hyperdrive(z, sr, float(s["hyper"]), float(s.get("hyper_res", MEUM_MINUS_1)))
        out.append(np.asarray(z, dtype=np.float32))
    y = np.stack(out, axis=1) if stereo else out[0]
    return hard_clip(y, float(s.get("volume", 1.0)), float(s.get("clip_ratio", 0.0)))


def assert_permitted(name: str) -> str:
    """Map any FX name to a permitted one, or raise.  Guards new code paths."""
    key = str(name)
    if key in PERMITTED_FX:
        return key
    if key in LEGACY_FX_MAP:
        return LEGACY_FX_MAP[key]
    raise ValueError(f"{name!r} is not one of Groovebox's hardcoded FX: {', '.join(FX_ORDER)}")
