"""GROOVEBOX_R124_SIGNAL_TRUTH: ground-truth bench — one generator set, one analysis set.

Generators: sine, impulse, log sweep (Farina), white noise. Any chain ``fn(x, sr) -> y`` can be
measured for: THD (+N) on a sine, magnitude response from a sweep (deconvolved) or noise, latency from
an impulse (cross-correlation peak), gain and DC. Pure NumPy; results are plain dicts for the UI, the
reproducibility stamp and tests.
"""
from __future__ import annotations

import math

import numpy as np


def sine(sr=48000, hz=1000.0, seconds=1.0, amp=0.5):
    t = np.arange(int(sr * seconds)) / float(sr)
    return amp * np.sin(2.0 * math.pi * hz * t)


def impulse(sr=48000, seconds=0.5, at=0, amp=1.0):
    x = np.zeros(int(sr * seconds)); x[int(at)] = amp
    return x


def log_sweep(sr=48000, seconds=2.0, f0=20.0, f1=20000.0, amp=0.5):
    n = int(sr * seconds); t = np.arange(n) / float(sr)
    f1 = min(f1, sr / 2.0 * 0.95)
    k = math.log(f1 / f0)
    return amp * np.sin(2.0 * math.pi * f0 * seconds / k * (np.exp(t * k / seconds) - 1.0))


def white_noise(sr=48000, seconds=1.0, amp=0.25, seed=1234):
    return amp * np.random.default_rng(seed).uniform(-1.0, 1.0, int(sr * seconds))


GENERATORS = {"sine": sine, "impulse": impulse, "sweep": log_sweep, "noise": white_noise}


def _mono(y):
    a = np.asarray(y, dtype=np.float64)
    return a.mean(axis=1) if a.ndim == 2 else a


def thd(y, sr, hz, harmonics=8):
    """THD (fundamental vs harmonics 2..N) and THD+N (everything that isn't the fundamental)."""
    m = _mono(y)
    n = m.shape[0]
    if n < 1024:
        return {"thd_pct": None, "thdn_pct": None}
    w = np.blackman(n)
    spec = np.abs(np.fft.rfft(m * w))
    fr = np.fft.rfftfreq(n, 1.0 / sr)
    def band(f):
        i = int(round(f / (sr / n)))
        lo, hi = max(0, i - 4), min(spec.shape[0], i + 5)
        return float(np.sqrt(np.sum(spec[lo:hi] ** 2))), lo, hi
    fund, flo, fhi = band(hz)
    if fund <= 1e-12:
        return {"thd_pct": None, "thdn_pct": None}
    h = 0.0
    for k in range(2, harmonics + 1):
        if k * hz < sr / 2.0:
            h += band(k * hz)[0] ** 2
    total = float(np.sum(spec[(fr > 10.0)] ** 2))
    noise_dist = max(0.0, total - fund ** 2)
    return {"thd_pct": round(100.0 * math.sqrt(h) / fund, 4), "thdn_pct": round(100.0 * math.sqrt(noise_dist) / fund, 4)}


def latency(chain, sr=48000):
    x = impulse(sr, 0.5, at=int(0.05 * sr))
    y = _mono(chain(x.copy(), sr))
    n = min(len(x), len(y))
    c = np.fft.irfft(np.fft.rfft(y[:n], 2 * n) * np.conj(np.fft.rfft(x[:n], 2 * n)))
    lag = int(np.argmax(np.abs(c[:n])))
    return {"latency_samples": lag, "latency_ms": round(1000.0 * lag / sr, 3)}


def response(chain, sr=48000, points=48):
    """Magnitude response by noise transfer function (H = Sxy / Sxx, Welch-averaged)."""
    x = white_noise(sr, 2.0)
    y = _mono(chain(x.copy(), sr))
    n = min(len(x), len(y)); seg = 4096
    sxx = np.zeros(seg // 2 + 1); sxy = np.zeros(seg // 2 + 1, dtype=complex)
    w = np.hanning(seg)
    for s in range(0, n - seg + 1, seg // 2):
        X = np.fft.rfft(x[s:s + seg] * w); Y = np.fft.rfft(y[s:s + seg] * w)
        sxx += np.abs(X) ** 2; sxy += Y * np.conj(X)
    h = np.abs(sxy) / np.maximum(sxx, 1e-20)
    fr = np.fft.rfftfreq(seg, 1.0 / sr)
    fs = np.geomspace(30.0, min(18000.0, sr / 2.0 * 0.9), points)
    db = [round(20.0 * math.log10(max(1e-9, float(np.interp(f, fr, h)))), 2) for f in fs]
    return {"freqs_hz": [round(float(f), 1) for f in fs], "db": db,
            "ripple_db": round(max(db) - min(db), 2)}


def bench(chain, sr=48000, hz=1000.0):
    """Full bench for any ``chain(x, sr) -> y``."""
    x = sine(sr, hz, 1.0, 0.5)
    y = _mono(chain(x.copy(), sr))
    g = float(np.sqrt(np.mean(y ** 2)) / max(1e-12, np.sqrt(np.mean(x ** 2))))
    out = {"gain_db": round(20.0 * math.log10(max(g, 1e-9)), 3), "dc": round(float(np.mean(y)), 6)}
    out.update(thd(y, sr, hz)); out.update(latency(chain, sr)); out.update(response(chain, sr))
    return out


def identity(x, _sr):
    return x


def master_chain_fn(mode="live"):
    import master_chain
    st = master_chain.load()
    return lambda x, sr: master_chain.process(x, sr, st, mode=mode, measure=False)[0]
