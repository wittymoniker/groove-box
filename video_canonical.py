"""VIDEO_CANONICAL_R31: pixel-domain seed ↔ video canonical (the video twin of spectral_canonical).

  literal seeds   "MGLV1:<base64>" — every frame's 2-D DCT coefficients (float32, zlib-packed).
                  analyse(frames) → seed; synthesize(seed) → the same uint8 frames (exact after rounding).
  generative      any other seed of ANY length: an extendable hash stream decides each frame's DCT
  seeds           coefficients (palette, low-frequency structure, motion, texture), so every byte matters.

frames: (T, H, W, 3) uint8. Pure NumPy + scipy.fft. Deterministic.
"""
from __future__ import annotations

import base64
import struct
import zlib

import numpy as np

from spectral_canonical import _Stream, seed_bytes

LITERAL_PREFIX = "MGLV1:"
_MAGIC = b"MGLV"
_HDR = "<4sIIIII"
_HDR_LEN = struct.calcsize(_HDR)


def _dct2(a):
    from scipy.fft import dctn
    return dctn(a, type=2, norm="ortho", axes=(0, 1))


def _idct2(a):
    from scipy.fft import idctn
    return idctn(a, type=2, norm="ortho", axes=(0, 1))


def coerce_frames(value):
    """UNIVERSAL_FRAMES_20261112: any image / video-like array → (T, H, W, 3) uint8.
    (H, W) or (T, H, W) grey · (…, 1|2|4) channels · bool · float in [0, 1] or any range · any int dtype ·
    NaN/inf · a 1-D signal or bytes (folded into a square frame)."""
    a = np.frombuffer(bytes(value), dtype=np.uint8) if isinstance(value, (bytes, bytearray, memoryview)) else np.asarray(value)
    if a.dtype == object or a.dtype.kind not in "biufc":
        a = np.frombuffer(repr(value).encode("utf-8"), dtype=np.uint8)
    if a.dtype.kind == "c":
        a = np.abs(a)
    k = a.dtype.kind
    if k == "b":
        a = a.astype(np.float64) * 255.0
    elif k in "iu" and a.dtype != np.uint8:
        info = np.iinfo(a.dtype)
        a = (a.astype(np.float64) - float(info.min)) * (255.0 / (float(info.max) - float(info.min)))
    elif k == "f" or k == "c":
        a = np.nan_to_num(a.astype(np.float64), nan=0.0, posinf=1.0, neginf=0.0)
        lo, hi = (float(a.min()), float(a.max())) if a.size else (0.0, 1.0)
        a = a * 255.0 if lo >= 0.0 and hi <= 1.0 else (a - lo) * (255.0 / ((hi - lo) or 1.0))
    a = np.clip(np.rint(a), 0, 255).astype(np.uint8) if a.dtype != np.uint8 else a
    if a.ndim <= 1:
        n = max(1, a.size); side = int(np.ceil(np.sqrt(n / 3.0)))
        flat = np.zeros(side * side * 3, dtype=np.uint8); flat[:a.size] = a.reshape(-1)
        a = flat.reshape(1, side, side, 3)
    elif a.ndim == 2:
        a = a[None, :, :, None]
    elif a.ndim == 3:
        a = a[None] if a.shape[-1] in (1, 2, 3, 4) else a[..., None]
    elif a.ndim > 4:
        a = a.reshape((-1,) + a.shape[-3:])
    c = a.shape[-1]
    if c == 1:
        a = np.repeat(a, 3, axis=-1)
    elif c == 2:                                   # grey + alpha
        a = np.repeat(a[..., :1], 3, axis=-1)
    elif c >= 4:
        a = a[..., :3]
    return np.ascontiguousarray(a)


def analyse(frames, fps=24):
    f = np.asarray(frames)
    if f.ndim != 4 or f.shape[3] != 3 or f.dtype != np.uint8:
        f = coerce_frames(f)
    f = f.astype(np.float64)
    fps = max(1, int(round(float(fps))))
    t, h, w, _ = f.shape
    coeffs = np.stack([_dct2(f[i]) for i in range(t)]).astype(np.float32)
    header = struct.pack(_HDR, _MAGIC, 1, int(t), int(h), int(w), int(fps))
    return LITERAL_PREFIX + base64.b64encode(zlib.compress(header + coeffs.tobytes(), 6)).decode("ascii")


def is_literal(seed) -> bool:
    return isinstance(seed, str) and seed.startswith(LITERAL_PREFIX)


def synthesize_literal(seed):
    try:
        raw = zlib.decompress(base64.b64decode(seed[len(LITERAL_PREFIX):].strip()))
    except Exception as exc:
        raise ValueError(f"literal video seed is damaged or truncated ({exc})") from None
    if len(raw) < _HDR_LEN:
        raise ValueError("literal video seed is truncated (no header)")
    magic, ver, t, h, w, fps = struct.unpack(_HDR, raw[:_HDR_LEN])
    if magic != _MAGIC:
        raise ValueError("not a Groovebox literal video seed")
    c = np.frombuffer(raw[_HDR_LEN:], dtype=np.float32)
    if t < 1 or h < 1 or w < 1 or c.size != t * h * w * 3:
        raise ValueError("literal video seed is truncated (coefficients missing)")
    c = c.reshape(t, h, w, 3).astype(np.float64)
    out = np.stack([_idct2(c[i]) for i in range(t)])
    return np.clip(np.rint(out), 0, 255).astype(np.uint8), int(fps)


def synthesize_generative(seed, frames=48, width=320, height=180, fps=24, detail=24):
    """Any seed → frames. The seed's bytes decide a low-frequency DCT field per frame (detail × detail
    coefficients per channel) that evolves smoothly in time, plus a seed-chosen palette bias."""
    frames, width, height = max(1, int(frames)), max(2, int(width)), max(2, int(height))
    st = _Stream(b"video|" + seed_bytes(seed))
    k = max(2, min(int(detail), min(width, height)))
    n_key = max(2, frames // 12 + 2)
    keys = (st.units(n_key * k * k * 3).reshape(n_key, k, k, 3) - 0.5)
    fall = 1.0 / (1.0 + np.add.outer(np.arange(k), np.arange(k)))[:, :, None] ** 1.3
    keys = keys * fall[None] * (width * height) ** 0.5 * 240.0     # ≈ ±60 levels of low-frequency structure
    bias = st.units(3) * 255.0 * (width * height) ** 0.5 * 0.6
    tk = np.linspace(0, frames - 1, n_key)
    out = np.empty((frames, height, width, 3), dtype=np.uint8)
    for i in range(frames):
        j = min(n_key - 2, int(np.searchsorted(tk, i, side="right")) - 1)
        a = (i - tk[j]) / max(1e-9, tk[j + 1] - tk[j])
        a = 0.5 - 0.5 * np.cos(np.pi * a)                      # smooth motion between key fields
        c = np.zeros((height, width, 3))
        c[:k, :k, :] = (1 - a) * keys[j] + a * keys[j + 1]
        c[0, 0, :] += bias
        out[i] = np.clip(np.rint(_idct2(c)), 0, 255).astype(np.uint8)
    return out, int(fps)


def synthesize(seed, **kw):
    if is_literal(seed):
        return synthesize_literal(seed)
    return synthesize_generative(seed, **kw)


def roundtrip_exact(frames, fps=24) -> bool:
    y, _ = synthesize_literal(analyse(frames, fps))
    return bool(np.array_equal(np.asarray(frames, dtype=np.uint8), y))
