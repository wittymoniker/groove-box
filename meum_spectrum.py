"""meum_spectrum.py — GROOVEBOX_R123_MEUM_IRRATIONAL_SPECTRUM_20261119

Meum irrational-phase real spectrum (a corrected form of the "irrational phase + Meum scaling +
real-signal folding" proposal).

  X'_k = X_k · e^{-i θ_k},   θ_k = 2π α {M φ² k},   θ_0 = θ_{N/2} = 0

  * X = the real FFT of x (length N). Real-signal folding is exact: the N real samples are packed
    into N/2 complex samples z_m = x_{2m} + i x_{2m+1}, transformed, then UNPACKED with
        X_k = ½(Z_k + Z*_{N/2-k}) − ½ i e^{-2πik/N}(Z_k − Z*_{N/2-k})
    (the unpack step is required; reusing Z_k directly gives a wrong spectrum).
  * The irrational phase is diagonal (one value per bin), so the transform stays O(N log N),
    keeps every magnitude, and is exactly invertible: multiply by e^{+iθ_k} and inverse-FFT.
    {u} = u − ⌊u⌋ keeps the phase bounded for any N; M φ² = M (1 + φ) is irrational, so no two
    bins share a phase pattern (no periodic aliasing across bins). DC and Nyquist stay real.
  * α = 0 is exactly the ordinary real FFT; α > 0 disperses phase non-commensurably.
  * The twiddle and irrational-modulator tables are precomputed once per (N, α, route), so the
    inner loops are pure multiply-accumulate with no trig calls.

OPERATOR THEORY (the main window's "Use OT" toggle, groovebox.OP_THEORY_ENABLED):
  Like isn / ics / sin / cos elsewhere in the engine, the transform keeps one fixed formula and OT
  only changes its EXECUTION ROUTE (see OT_EXPRESSION_ROUTE_20260911.md, groovebox "DUAL MATH MODE"):
    OT ON   every twiddle and phase factor comes from the author's series kernels
            (trig_series.isx = cos, trig_series.isy = sin, from the cyclic isn series), and the FFT
            is the book-route radix-2 transform below (power-of-two N; other N use the exact
            Bluestein-free direct table — still book trig, O(N²), only for short frames).
    OT OFF  NumPy's FFT and libm cos / sin.
  Both routes agree to ~1e-12 relative. OT products (ot_prod: −·− = −) are NOT applied inside the
  butterflies: that would break linearity, i.e. the transform would stop being a transform.
  Canonical DSP paths are semantics-preserving under OT, exactly as for the rest of the engine.

Pure NumPy, deterministic, no Qt.
"""
from __future__ import annotations

import functools
import math
import sys

import numpy as np

from meum_constants import MEUM, PHI

MEUM_PHI2 = MEUM * PHI * PHI          # M (1 + φ) = M φ²


def ot_enabled(ot=None) -> bool:
    """The main window's Use OT state (default ON, matching groovebox.OP_THEORY_ENABLED)."""
    if ot is not None:
        return bool(ot)
    gb = sys.modules.get("groovebox")
    if gb is not None:
        try:
            return bool(gb.operator_theory_enabled())
        except Exception:
            return bool(getattr(gb, "OP_THEORY_ENABLED", True))
    return True


def _cos_sin(theta, ot: bool):
    theta = np.asarray(theta, dtype=np.float64)
    if ot:
        import trig_series as ts
        return np.asarray(ts.isx(theta), np.float64), np.asarray(ts.isy(theta), np.float64)
    return np.cos(theta), np.sin(theta)


def _expi(theta, ot: bool, sign=-1.0):
    c, s = _cos_sin(theta, ot)
    return c + 1j * sign * s


@functools.lru_cache(maxsize=64)
def _phase_table(n_bins: int, alpha: float, ot: bool) -> np.ndarray:
    k = np.arange(n_bins, dtype=np.float64)
    frac = np.mod(MEUM_PHI2 * k, 1.0)
    theta = 2.0 * math.pi * float(alpha) * frac
    theta[0] = 0.0
    if n_bins > 1:
        theta[-1] = 0.0                    # Nyquist (even N) stays real → exact inverse
    w = _expi(theta, ot)
    w.setflags(write=False)
    return w


@functools.lru_cache(maxsize=64)
def _stage_twiddles(n: int, ot: bool):
    """Twiddles for each radix-2 stage (book route)."""
    out = []
    size = 2
    while size <= n:
        half = size // 2
        w = _expi(2.0 * math.pi * np.arange(half) / size, ot)
        w.setflags(write=False)
        out.append(w)
        size <<= 1
    return tuple(out)


@functools.lru_cache(maxsize=64)
def _bitrev(n: int) -> np.ndarray:
    bits = n.bit_length() - 1
    idx = np.arange(n)
    rev = np.zeros(n, dtype=np.int64)
    for b in range(bits):
        rev |= ((idx >> b) & 1) << (bits - 1 - b)
    rev.setflags(write=False)
    return rev


def _book_fft(z: np.ndarray, ot: bool = True) -> np.ndarray:
    """Iterative radix-2 Cooley–Tukey, vectorised per stage, twiddles from the chosen trig route."""
    z = np.asarray(z, dtype=np.complex128)
    n = z.shape[-1]
    if n <= 1:
        return z.copy()
    if n & (n - 1):
        w = _expi(2.0 * math.pi * np.outer(np.arange(n), np.arange(n)) / n, ot)   # direct (short frames)
        return z @ w.T
    a = z[..., _bitrev(n)].copy()
    size = 2
    for w in _stage_twiddles(n, ot):
        half = size // 2
        a = a.reshape(a.shape[:-1] + (n // size, size))
        even = a[..., :half].copy()
        odd = a[..., half:] * w
        a[..., :half] = even + odd
        a[..., half:] = even - odd
        a = a.reshape(a.shape[:-2] + (n,))
        size <<= 1
    return a


@functools.lru_cache(maxsize=64)
def _unpack_twiddle(n: int, ot: bool) -> np.ndarray:
    w = _expi(2.0 * math.pi * np.arange(n // 2 + 1) / n, ot)
    w.setflags(write=False)
    return w


def rfft(x, ot=None) -> np.ndarray:
    """Real FFT (N/2 + 1 bins) through the OT-selected route. N must be even on the book route."""
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[-1]
    if not ot_enabled(ot):
        return np.fft.rfft(x)
    if n % 2:
        return _book_fft(x.astype(np.complex128), True)[..., : n // 2 + 1]
    h = n // 2
    z = x[..., 0::2] + 1j * x[..., 1::2]                     # real-signal folding: N reals → N/2 complex
    Z = _book_fft(z, True)
    Zk = np.concatenate([Z, Z[..., :1]], axis=-1)            # Z_{N/2} = Z_0 (period N/2)
    Zc = np.conj(Zk[..., ::-1])                              # Z*_{N/2-k}
    W = _unpack_twiddle(n, True)
    return 0.5 * (Zk + Zc) - 0.5j * W * (Zk - Zc)


def irfft(X, n: int, ot=None) -> np.ndarray:
    """Inverse of :func:`rfft` (same route)."""
    X = np.asarray(X, dtype=np.complex128)
    if not ot_enabled(ot):
        return np.fft.irfft(X, n)
    full = np.concatenate([X, np.conj(X[..., 1:(n + 1) // 2][..., ::-1])], axis=-1)
    if full.shape[-1] != n:                                  # even n: Nyquist bin present once
        full = np.concatenate([X, np.conj(X[..., 1:n // 2][..., ::-1])], axis=-1)
    return np.real(np.conj(_book_fft(np.conj(full), True))) / n


def forward(x, alpha: float = 0.25, ot=None) -> np.ndarray:
    """Meum irrational-phase spectrum of a real signal: X'_k = X_k e^{-iθ_k}."""
    x = np.asarray(x, dtype=np.float64)
    use_ot = ot_enabled(ot)
    X = rfft(x, use_ot)
    return X * _phase_table(X.shape[-1], float(alpha), use_ot)


def inverse(Xp, n: int, alpha: float = 0.25, ot=None) -> np.ndarray:
    """Exact inverse of :func:`forward`."""
    use_ot = ot_enabled(ot)
    Xp = np.asarray(Xp, dtype=np.complex128)
    return irfft(Xp * np.conj(_phase_table(Xp.shape[-1], float(alpha), use_ot)), n, use_ot)


def phase_disperse(x, alpha: float = 0.25, n_fft: int = 2048, ot=None) -> np.ndarray:
    """Post-processing effect: per-frame Meum irrational all-pass (magnitudes kept, phases dispersed
    non-commensurably) on the perfect-reconstruction sqrt-Hann STFT used by spectral_canonical.
    α = 0 returns the input (up to float rounding); output length = input length."""
    x = np.asarray(x, dtype=np.float64).ravel()
    if float(alpha) == 0.0 or x.size == 0:
        return x.copy()
    n_fft = max(16, int(n_fft) // 2 * 2)
    hop = n_fft // 2
    w = np.sqrt(0.5 - 0.5 * np.cos(2.0 * math.pi * np.arange(n_fft) / n_fft))
    pad = np.concatenate([np.zeros(n_fft), x, np.zeros(n_fft + hop)])
    frames = (pad.size - n_fft) // hop + 1
    idx = np.arange(n_fft)[None, :] + hop * np.arange(frames)[:, None]
    use_ot = ot_enabled(ot)
    spec = forward(pad[idx] * w, alpha, use_ot)
    seg = np.fft.irfft(spec, n_fft) if not use_ot else irfft(spec, n_fft, True)
    seg *= w
    out = np.zeros(pad.size)
    np.add.at(out, idx, seg)
    return out[n_fft:n_fft + x.size]


def self_test() -> dict:
    """Route agreement, exact inverse, α = 0 identity. Used by Monitor Center / doctor and tests."""
    rng = np.random.default_rng(1975807343)
    res = {}
    for n in (16, 1024, 4096):
        x = rng.standard_normal(n)
        ref = np.fft.rfft(x)
        res[f"rfft_book_vs_numpy_{n}"] = float(np.max(np.abs(rfft(x, True) - ref)) / (np.max(np.abs(ref)) or 1.0))
        for ot in (False, True):
            y = inverse(forward(x, 0.3, ot), n, 0.3, ot)
            res[f"roundtrip_{'ot' if ot else 'ieee'}_{n}"] = float(np.max(np.abs(y - x)))
        res[f"alpha0_identity_{n}"] = float(np.max(np.abs(forward(x, 0.0, False) - ref)))
        res[f"magnitude_kept_{n}"] = float(np.max(np.abs(np.abs(forward(x, 0.5, True)) - np.abs(ref))))
    res["ok"] = all(v < 1e-9 for k, v in res.items() if k != "ok")
    return res


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=1))
