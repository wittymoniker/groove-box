"""GROOVEBOX_R124_MEASURE_CORE: one measurement core for every output (no GUI, NumPy only).

Used by the measurement overlay, the master chain stage meters, the signal ground-truth bench and the
reproducibility stamp, so each number is computed exactly one way in the whole program.

All functions accept mono (N,) or multi-channel (N, C) float arrays in −1…+1.
"""
from __future__ import annotations

import math

import numpy as np


def as_2d(x):
    a = np.asarray(x, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    elif a.ndim > 2:
        a = a.reshape(a.shape[0], -1)
    return np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)


def mono(x):
    return as_2d(x).mean(axis=1)


def peak_dbfs(x):
    p = float(np.max(np.abs(as_2d(x)))) if np.size(x) else 0.0
    return 20.0 * math.log10(p) if p > 1e-12 else -120.0


def rms_dbfs(x):
    a = as_2d(x)
    r = float(np.sqrt(np.mean(a * a))) if a.size else 0.0
    return 20.0 * math.log10(r) if r > 1e-12 else -120.0


def true_peak_dbtp(x, oversample=4):
    """Inter-sample peak by band-limited FFT oversampling (ITU-R BS.1770 style estimate)."""
    a = as_2d(x)
    n = a.shape[0]
    if n < 4:
        return peak_dbfs(a)
    n = min(n, 1 << 18)
    seg = a[:n]
    spec = np.fft.rfft(seg, axis=0)
    up = np.fft.irfft(spec, n=n * oversample, axis=0) * oversample
    p = float(np.max(np.abs(up)))
    return 20.0 * math.log10(p) if p > 1e-12 else -120.0


def _k_weight(x, sr):
    """K-weighting (BS.1770 pre-filter + RLB high-pass) via two biquads, direct form I."""
    def biquad(sig, b, a):
        y = np.zeros_like(sig)
        x1 = x2 = y1 = y2 = 0.0
        b0, b1, b2 = b; _a0, a1, a2 = a
        for i in range(sig.shape[0]):
            v = sig[i]
            out = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1, y2, y1 = x1, v, y1, out
            y[i] = out
        return y
    # Coefficients from BS.1770-4, re-derived for arbitrary sample rate (bilinear transform).
    f0, g, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / sr); vh = 10 ** (g / 20.0); vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / q + k * k
    b_shelf = ((vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0)
    a_shelf = (1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0)
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / sr)
    a0 = 1.0 + k / q + k * k
    b_hp = (1.0, -2.0, 1.0)
    a_hp = (1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0)
    return biquad(biquad(x, b_shelf, a_shelf), b_hp, a_hp)


def lufs_integrated(x, sr, max_seconds=30.0):
    """Integrated loudness (BS.1770 gating, mono/stereo sum). Long inputs are decimated to max_seconds."""
    a = as_2d(x)
    n = int(min(a.shape[0], max_seconds * sr))
    if n < int(0.4 * sr):
        return -120.0
    a = a[:n]
    try:
        from scipy.signal import lfilter  # fast path
        def kw(sig):
            f0, g, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
            k = math.tan(math.pi * f0 / sr); vh = 10 ** (g / 20.0); vb = vh ** 0.4996667741545416
            a0 = 1.0 + k / q + k * k
            b1 = [(vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0]
            a1 = [1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0]
            f0, q = 38.13547087602444, 0.5003270373238773
            k = math.tan(math.pi * f0 / sr); a0 = 1.0 + k / q + k * k
            b2 = [1.0, -2.0, 1.0]; a2 = [1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0]
            return lfilter(b2, a2, lfilter(b1, a1, sig, axis=0), axis=0)  # FX_AUDIT_OK measurement only
        y = kw(a)
    except Exception:
        y = np.stack([_k_weight(a[:, c], sr) for c in range(a.shape[1])], axis=1)
    block, hop = int(0.4 * sr), int(0.1 * sr)
    zs = []
    for s in range(0, y.shape[0] - block + 1, hop):
        seg = y[s:s + block]
        zs.append(float(np.sum(np.mean(seg * seg, axis=0))))
    if not zs:
        return -120.0
    z = np.asarray(zs)
    lk = -0.691 + 10.0 * np.log10(np.maximum(z, 1e-20))
    z = z[lk > -70.0]
    if z.size == 0:
        return -120.0
    rel = -0.691 + 10.0 * math.log10(float(np.mean(z))) - 10.0
    lk2 = -0.691 + 10.0 * np.log10(np.maximum(z, 1e-20))
    z2 = z[lk2 > rel]
    if z2.size == 0:
        return -120.0
    return round(-0.691 + 10.0 * math.log10(float(np.mean(z2))), 2)


def phase_correlation(x):
    a = as_2d(x)
    if a.shape[1] < 2:
        return 1.0
    l, r = a[:, 0], a[:, 1]
    d = math.sqrt(float(np.sum(l * l)) * float(np.sum(r * r)))
    return round(float(np.sum(l * r)) / d, 4) if d > 1e-20 else 1.0


def spectrum(x, sr, bins=256, fmin=20.0, fmax=20000.0):
    """Log-spaced magnitude spectrum in dBFS: (freqs, db)."""
    m = mono(x)
    n = min(m.shape[0], 1 << 16)
    if n < 64:
        f = np.geomspace(fmin, fmax, bins)
        return f, np.full(bins, -120.0)
    seg = m[-n:] * np.hanning(n)
    mag = np.abs(np.fft.rfft(seg)) / (n / 4.0)
    fr = np.fft.rfftfreq(n, 1.0 / sr)
    edges = np.geomspace(fmin, min(fmax, sr / 2.0), bins + 1)
    out = np.full(bins, -120.0)
    for i in range(bins):
        sel = (fr >= edges[i]) & (fr < edges[i + 1])
        v = float(np.max(mag[sel])) if np.any(sel) else 0.0
        out[i] = 20.0 * math.log10(v) if v > 1e-12 else -120.0
    return np.sqrt(edges[:-1] * edges[1:]), out


def spectral_centroid(x, sr):
    m = mono(x)
    n = min(m.shape[0], 1 << 16)
    if n < 64:
        return 0.0
    mag = np.abs(np.fft.rfft(m[-n:] * np.hanning(n)))
    fr = np.fft.rfftfreq(n, 1.0 / sr)
    s = float(np.sum(mag))
    return round(float(np.sum(fr * mag)) / s, 1) if s > 1e-12 else 0.0


def summary(x, sr):
    """Every overlay number in one dict (rounded for display and stamping)."""
    return {
        "peak_dbfs": round(peak_dbfs(x), 2),
        "true_peak_dbtp": round(true_peak_dbtp(x), 2),
        "rms_dbfs": round(rms_dbfs(x), 2),
        "lufs_i": lufs_integrated(x, sr),
        "correlation": phase_correlation(x),
        "centroid_hz": spectral_centroid(x, sr),
        "samples": int(as_2d(x).shape[0]),
        "sample_rate": int(sr),
    }
