"""time_fx.py — GROOVEBOX_R32_TIME_FX_20261110

Post-process TIME effects for the right-hand "POST ▸ TIME FX" panel (local or global,
non-canonical by default, canonical when the panel's mode says so).  Built only from
delays, grains and isn windows — no IIR filters — so they stay inside the hardcoded,
deterministic direction.

  granular_chorus(x, sr, depth, rate, voices, grain_ms, seed)
      overlapping isn-windowed grains read at slowly modulated delays (5–25 ms) per voice.
  granular_flanger(x, sr, depth, rate, feedback)
      one modulated short delay (0.2–8 ms) with feedback, sample-accurate linear interp.
  time_reverb(x, sr, size, decay, direction, density, seed)
      a deterministic cloud of delayed taps (Meum-spaced, decaying); direction +1 = forward
      reverb, −1 = REVERSE reverb (taps swell *into* each onset), 0 = both.
"""
from __future__ import annotations

import math

import numpy as np

MEUM = 2.0 ** (1.0 / 12.0)


def _isn_window(n):
    if n <= 1:
        return np.ones(max(1, n), dtype=np.float32)
    return (np.sin(np.linspace(0.0, math.pi, n)) ** 2).astype(np.float32)


def _frac_delay(x, d):
    """y[i] = x[i - d[i]] with linear interpolation; d in samples (array)."""
    n = x.size
    idx = np.arange(n, dtype=np.float64) - d
    i0 = np.floor(idx).astype(np.int64)
    f = (idx - i0).astype(np.float32)
    i0c = np.clip(i0, 0, n - 1)
    i1c = np.clip(i0 + 1, 0, n - 1)
    y = x[i0c] * (1.0 - f) + x[i1c] * f
    y[idx < 0] = 0.0
    return y


def _mono(fn, x, *a, **k):
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 2:
        return np.stack([fn(x[:, c], *a, **k) for c in range(x.shape[1])], axis=1)
    return fn(x, *a, **k)


def granular_chorus(x, sr, depth=0.5, rate=0.6, voices=3, grain_ms=40.0, seed=0, mix=0.5):
    def _one(v):
        n = v.size
        t = np.arange(n, dtype=np.float64) / sr
        out = np.zeros(n, dtype=np.float32)
        rng = np.random.default_rng(int(seed) & 0x7FFFFFFF)
        for k in range(max(1, int(voices))):
            ph = rng.random() * 2 * math.pi
            r = rate * (MEUM ** (k - voices / 2.0))
            d = (0.005 + 0.020 * depth * (0.5 + 0.5 * np.sin(2 * math.pi * r * t + ph))) * sr
            out += _frac_delay(v, d)
        out /= max(1, int(voices))
        # grain the wet signal: isn windows at 50 % overlap re-phase the voices (granular texture)
        g = max(64, int(grain_ms * 1e-3 * sr))
        w = _isn_window(g)
        wet = np.zeros(n, dtype=np.float32)
        for s in range(0, n, g // 2):
            seg = out[s:s + g]
            wet[s:s + seg.size] += seg * w[:seg.size]
        return (1.0 - mix) * v + mix * wet
    return _mono(_one, x)


def granular_flanger(x, sr, depth=0.5, rate=0.25, feedback=0.4, mix=0.5):
    def _one(v):
        n = v.size
        t = np.arange(n, dtype=np.float64) / sr
        d = (0.0002 + 0.0078 * depth * (0.5 + 0.5 * np.sin(2 * math.pi * rate * t))) * sr
        y = v.copy()
        fb = max(0.0, min(0.95, float(feedback)))
        for _ in range(3):                     # three feedback passes approximate the recursive comb
            y = v + fb * _frac_delay(y, d)
        return (1.0 - mix) * v + mix * (y * (1.0 - 0.5 * fb))
    return _mono(_one, x)


def time_reverb(x, sr, size=0.5, decay=0.5, direction=1, density=24, seed=0, mix=0.35):
    """Tap-cloud reverb; direction −1 renders the reversed tail before each sound."""
    def _one(v):
        n = v.size
        rng = np.random.default_rng(int(seed) & 0x7FFFFFFF)
        span = (0.03 + 1.8 * size) * sr
        taps = int(max(4, density))
        delays = np.sort(span * (rng.random(taps) ** 1.6))
        gains = np.exp(-delays / max(1.0, span * (0.15 + 0.85 * decay))) * (rng.random(taps) * 0.5 + 0.5)
        gains *= np.where(rng.random(taps) > 0.5, 1.0, -1.0)
        gains /= max(1e-9, np.sqrt(np.sum(gains ** 2)))
        out = np.zeros(n, dtype=np.float32)
        dirs = (1, -1) if direction == 0 else (int(np.sign(direction)) or 1,)
        for dsign in dirs:
            src = v if dsign > 0 else v[::-1]
            acc = np.zeros(n, dtype=np.float32)
            for dl, g in zip(delays.astype(np.int64), gains):
                if dl < n:
                    acc[dl:] += src[:n - dl] * np.float32(g)
            out += acc if dsign > 0 else acc[::-1]
        out /= len(dirs)
        return (1.0 - mix) * v + mix * out
    return _mono(_one, x)


def process(x, sr, s, seed=0):
    """Panel dict → processed audio. Keys: chorus, chorus_rate, flanger, flanger_rate,
    flanger_fb, reverb, reverb_size, reverb_decay, reverb_dir (−1/0/1). All 0 = bypass."""
    y = np.asarray(x, dtype=np.float32)
    if float(s.get("chorus", 0)) > 0:
        y = granular_chorus(y, sr, depth=float(s.get("chorus", 0)), rate=float(s.get("chorus_rate", 0.6)), seed=seed,
                            mix=min(1.0, 0.3 + 0.5 * float(s.get("chorus", 0))))
    if float(s.get("flanger", 0)) > 0:
        y = granular_flanger(y, sr, depth=float(s.get("flanger", 0)), rate=float(s.get("flanger_rate", 0.25)),
                             feedback=float(s.get("flanger_fb", 0.4)), mix=min(1.0, 0.3 + 0.5 * float(s.get("flanger", 0))))
    if float(s.get("reverb", 0)) > 0:
        y = time_reverb(y, sr, size=float(s.get("reverb_size", 0.5)), decay=float(s.get("reverb_decay", 0.5)),
                        direction=int(round(float(s.get("reverb_dir", 1)))), seed=seed, mix=float(s.get("reverb", 0)))
    return y.astype(np.float32)
