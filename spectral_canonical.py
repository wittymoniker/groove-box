"""SPECTRAL_CANONICAL_R31: a complete (in principle) seed ↔ signal canonical.

Any finite sampled signal is a sum of short-time spectral frames. This module maps seeds to time-varying
spectral coefficients and back, so the seed space covers every finite band-limited signal:

  literal seeds   "MGLS1:<base64>"  — the exact float32 STFT coefficients (zlib-packed). analyse(signal)
                  produces one; synthesize(seed) rebuilds the signal (perfect-reconstruction STFT: sqrt-Hann
                  analysis/synthesis windows at 50% overlap), equal up to float32 rounding.
  generative      any other text / number / bytes, of ANY length (no 64-bit collapse): the bytes drive an
  seeds           extendable hash stream that decides every frame's spectral envelope, partial structure,
                  phase and noise. Longer seeds decide more of the result directly.

Pure NumPy, deterministic, no Qt. Mono or multichannel (channels × samples).

UNIVERSAL_SIGNAL_20261112: coerce_signal(anything) turns ANY value into a valid (channels, samples) float64
signal — every numeric dtype (ints scaled by their range, unsigned centred, bool, complex → 2 channels),
NaN/±inf sanitised, (samples, ch) layouts transposed, N-D arrays flattened per channel, lists, bytes,
dicts {"samples"/"signal"/"data", "sample_rate"/"sr"} and, for text / numbers, a generative seed.  So
analyse(), synthesize() and everything built on them accept any signal sample or context sample and
always return audio.  istft is vectorised (bit-identical to the old loop); generative synthesis streams
frames in blocks (memory O(block), not O(length)) and never goes silent at low sample rates.
"""
from __future__ import annotations

import base64
import hashlib
import struct
import zlib

import numpy as np

LITERAL_PREFIX = "MGLS1:"
_MAGIC = b"MGLS"
_HDR = "<4sIIIIQ"
_HDR_LEN = struct.calcsize(_HDR)


# ---------------------------------------------------------------- perfect-reconstruction STFT
def _window(n_fft):
    # periodic sqrt-Hann: w² sums to 1 at hop = n_fft / 2  → analysis × synthesis window is COLA.
    return np.sqrt(0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n_fft) / n_fft))


def _check_fft(n_fft):
    n_fft = int(n_fft)
    if n_fft < 2 or n_fft % 2:
        raise ValueError(f"n_fft must be an even integer ≥ 2 (got {n_fft})")
    return n_fft


def _check_sr(sample_rate):
    sr = int(round(float(sample_rate)))
    if sr <= 0:
        raise ValueError(f"sample_rate must be > 0 (got {sample_rate})")
    return sr


def coerce_signal(value, sample_rate=48000, seconds=2.0):
    """ANY value → ((channels, samples) float64 in about [-1, 1], sample_rate). Never raises for data."""
    sr = sample_rate
    if isinstance(value, dict):
        for k in ("sample_rate", "sr", "rate"):
            if k in value:
                sr = value[k]; break
        for k in ("samples", "signal", "data", "audio", "x"):
            if k in value:
                value = value[k]; break
        else:
            value = repr(sorted(value.items(), key=lambda kv: str(kv[0])))
    try:
        sr = _check_sr(sr)
    except (TypeError, ValueError):
        sr = 48000
    if isinstance(value, (str, int, float)) and not isinstance(value, bool) and not (
            isinstance(value, str) and is_literal(value)):
        # a scalar / text is a seed: the canonical meaning of "a number as a signal"
        return synthesize_generative(value, seconds=seconds, sample_rate=sr)[0].astype(np.float64), sr
    if isinstance(value, str):
        x, sr = synthesize_literal(value)
        return x.astype(np.float64), sr
    if isinstance(value, (bytes, bytearray, memoryview)):
        a = np.frombuffer(bytes(value), dtype=np.uint8)
    else:
        try:
            a = np.asarray(value)
        except Exception:
            a = np.frombuffer(repr(value).encode("utf-8"), dtype=np.uint8)
        if a.dtype == object:
            try:
                a = np.asarray(a.tolist(), dtype=np.complex128)
            except Exception:
                a = np.frombuffer(repr(value).encode("utf-8"), dtype=np.uint8)
    k = a.dtype.kind
    if k == "b":
        a = a.astype(np.float64) * 2.0 - 1.0
    elif k == "u":
        info = np.iinfo(a.dtype); half = (float(info.max) + 1.0) / 2.0
        a = (a.astype(np.float64) - half) / half
    elif k == "i":
        a = a.astype(np.float64) / (float(np.iinfo(a.dtype).max) + 1.0)
    elif k == "c":
        a = np.stack([a.real, a.imag], axis=0).astype(np.float64) if a.ndim <= 1 else \
            np.concatenate([a.real, a.imag], axis=0).astype(np.float64)
    elif k == "f":
        a = a.astype(np.float64)
    else:                                                       # strings, datetimes, void … → their bytes
        a = (np.frombuffer(a.tobytes(), dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    a = np.nan_to_num(a, nan=0.0, posinf=1.0, neginf=-1.0)
    if a.ndim == 0:
        a = a.reshape(1, 1)
    elif a.ndim == 1:
        a = a[None, :]
    elif a.ndim == 2:
        if a.shape[1] <= 64 < a.shape[0]:                       # (samples, channels) file layout
            a = a.T
    else:
        if a.shape[0] <= 64:                                    # (channels, …) → (channels, samples)
            a = a.reshape(a.shape[0], -1)
        elif a.shape[-1] <= 64:                                 # (…, channels) → (channels, samples)
            a = np.moveaxis(a, -1, 0).reshape(a.shape[-1], -1)
        else:
            a = a.reshape(1, -1)
    if a.shape[1] == 0:
        a = np.zeros((a.shape[0] or 1, 1))
    pk = float(np.max(np.abs(a))) if a.size else 0.0
    if pk > 1.0:                                                # float data outside ±1 is scaled, never clipped
        a = a / pk
    return np.ascontiguousarray(a), sr


def stft(x, n_fft=1024):
    n_fft = _check_fft(n_fft)
    x = np.asarray(x, dtype=np.float64)
    hop = n_fft // 2
    w = _window(n_fft)
    pad = n_fft
    xp = np.concatenate([np.zeros(pad), x, np.zeros(pad + n_fft)])
    n_frames = 1 + (len(xp) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
    return np.fft.rfft(xp[idx] * w[None, :], axis=1)


def _overlap_add(frames, hop):
    """50 % overlap-add without a Python loop: frame i's halves land in blocks i and i+1.
    Every sample is the sum of exactly two terms, so the result is bit-identical to the loop."""
    n_frames = frames.shape[0]
    blocks = np.zeros((n_frames + 1, hop))
    blocks[:-1] += frames[:, :hop]
    blocks[1:] += frames[:, hop:]
    return blocks.reshape(-1)


def istft(spec, n_samples, n_fft=1024):
    n_fft = _check_fft(n_fft)
    hop = n_fft // 2
    w = _window(n_fft)
    frames = np.fft.irfft(np.asarray(spec), n=n_fft, axis=1) * w[None, :]
    out = _overlap_add(frames, hop)
    pad = n_fft
    return out[pad:pad + int(n_samples)]


# ---------------------------------------------------------------- literal seeds (analysis ↔ synthesis)
def analyse(signal, sample_rate, n_fft=1024):
    """Signal (samples,) or (channels, samples) → literal seed text."""
    n_fft = _check_fft(n_fft)
    x = np.asarray(signal)
    if x.dtype.kind != "f" or x.ndim not in (1, 2) or not np.all(np.isfinite(x)):
        x, sample_rate = coerce_signal(x, sample_rate)
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[None, :]
    elif x.shape[1] <= 64 < x.shape[0]:
        x = x.T
    sample_rate = _check_sr(sample_rate)
    ch, n = x.shape
    specs = [stft(x[c], n_fft) for c in range(ch)]
    coeffs = np.stack(specs).astype(np.complex64)                 # (ch, frames, bins)
    header = struct.pack(_HDR, _MAGIC, 1, int(sample_rate), int(ch), int(n_fft), int(n))
    payload = header + coeffs.tobytes()
    return LITERAL_PREFIX + base64.b64encode(zlib.compress(payload, 6)).decode("ascii")


def is_literal(seed) -> bool:
    return isinstance(seed, str) and seed.startswith(LITERAL_PREFIX)


def synthesize_literal(seed):
    """Literal seed → (signal (channels, samples) float32, sample_rate)."""
    try:
        raw = zlib.decompress(base64.b64decode(seed[len(LITERAL_PREFIX):].strip(), validate=False))
    except Exception as exc:
        raise ValueError(f"literal spectral seed is damaged or truncated ({exc})") from None
    if len(raw) < _HDR_LEN:
        raise ValueError("literal spectral seed is truncated (no header)")
    magic, ver, sr, ch, n_fft, n = struct.unpack(_HDR, raw[:_HDR_LEN])
    if magic != _MAGIC:
        raise ValueError("not a Groovebox literal spectral seed")
    if ch < 1 or sr < 1 or n_fft < 2 or n_fft % 2:
        raise ValueError("literal spectral seed header is invalid")
    bins = n_fft // 2 + 1
    coeffs = np.frombuffer(raw[_HDR_LEN:], dtype=np.complex64)
    frames = coeffs.size // (ch * bins)
    if frames < 1 or coeffs.size != frames * ch * bins:
        raise ValueError("literal spectral seed is truncated (coefficients missing)")
    coeffs = coeffs.reshape(ch, frames, bins)
    out = np.stack([istft(coeffs[c].astype(np.complex128), n, n_fft) for c in range(ch)]).astype(np.float32)
    return out, int(sr)


# ---------------------------------------------------------------- generative seeds (any length)
class _Stream:
    """Deterministic, extendable byte stream from a seed of any length (SHAKE-256)."""

    def __init__(self, seed_bytes):
        self._x = hashlib.shake_256(b"groovebox-spectral|" + seed_bytes)
        self._buf = b""
        self._pos = 0

    def units(self, count):
        need = 8 * int(count)
        if self._pos + need > len(self._buf):
            self._buf = self._x.digest(max(len(self._buf) * 2, self._pos + need + 4096))
        v = np.frombuffer(self._buf[self._pos:self._pos + need], dtype="<u8")
        self._pos += need
        return (v >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def seed_bytes(seed) -> bytes:
    if isinstance(seed, bytes):
        return seed
    return str(seed).encode("utf-8")


def synthesize_generative(seed, seconds=8.0, sample_rate=48000, channels=1, n_fft=2048, level=1.0):
    """Any seed → signal. The seed's bytes (all of them) decide every frame's spectrum:
    envelope shape, harmonic family, inharmonicity, noise share, phase evolution and dynamics."""
    n_fft = _check_fft(n_fft); sample_rate = _check_sr(sample_rate); channels = max(1, int(channels))
    st = _Stream(seed_bytes(seed))
    n = max(1, int(round(float(seconds) * sample_rate)))
    bins = n_fft // 2 + 1
    hop = n_fft // 2
    frames = 1 + (n + 3 * n_fft) // hop
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
    # global decisions
    g = st.units(16)
    f0 = 40.0 * (2.0 ** (g[0] * 6.0))                         # 40 Hz … 2.56 kHz
    nyq = 0.5 * sample_rate
    if f0 >= 0.45 * nyq:                                       # low sample rates: fold the pitch down by octaves
        f0 = f0 / (2.0 ** np.ceil(np.log2(f0 / (0.45 * nyq))))  # (unchanged at ≥ 11.4 kHz rates) — never silent
    n_part = 1 + int(g[1] * 63)
    inharm = g[2] ** 2 * 0.08
    tilt = 0.5 + 2.5 * g[3]
    noise = g[4] ** 1.5
    vib = g[5] * 0.03
    vib_rate = 0.1 + 6.0 * g[6]
    # time-varying decisions: one control row per 8 frames, interpolated
    n_ctl = frames // 8 + 2
    ctl = st.units(n_ctl * 4).reshape(n_ctl, 4)
    t_ctl = np.linspace(0, frames - 1, n_ctl)
    fr = np.arange(frames)
    amp = np.interp(fr, t_ctl, 0.2 + 0.8 * ctl[:, 0])
    bright = np.interp(fr, t_ctl, ctl[:, 1])
    nmix = np.interp(fr, t_ctl, ctl[:, 2]) * noise
    shift = np.interp(fr, t_ctl, ctl[:, 3] - 0.5)
    out = np.zeros((channels, n), dtype=np.float32)
    w = _window(n_fft); block = 256
    for c in range(channels):
        sig_full = np.zeros(hop * (frames + 1))
        spec = np.zeros((min(block, frames), bins), dtype=np.complex128)
        ph = st.units(bins) * 2 * np.pi
        k = np.arange(1, n_part + 1)
        pw = st.units(n_part)                                    # per-partial weights from the seed
        carry = np.zeros(hop)
        for i in range(frames):
            t = i * hop / sample_rate
            fi = f0 * (1.0 + vib * np.sin(2 * np.pi * vib_rate * t)) * (2.0 ** (shift[i] * 0.25))
            pf = fi * k * np.sqrt(1.0 + inharm * k * k)
            pa = pw / (k ** (tilt * (1.2 - bright[i])))
            mag = np.zeros(bins)
            pos = pf / (sample_rate / n_fft)
            ok = pos < bins - 1
            lo = pos[ok].astype(int)
            frac = pos[ok] - lo
            np.add.at(mag, lo, pa[ok] * (1 - frac))
            np.add.at(mag, lo + 1, pa[ok] * frac)
            env = 1.0 / (1.0 + (freqs / (500.0 + 8000.0 * bright[i])) ** 2)
            mag = (1 - nmix[i]) * mag + nmix[i] * env * 0.05
            ph = ph + 2 * np.pi * freqs * hop / sample_rate
            if nmix[i] > 0:
                ph = ph + nmix[i] * 2 * np.pi * (st.units(bins) - 0.5)
            spec[i % block] = amp[i] * mag * np.exp(1j * ph)
            if i % block == block - 1 or i == frames - 1:          # stream: inverse-FFT this block, overlap-add
                b0 = i - (i % block); m = i - b0 + 1
                fr_ = np.fft.irfft(spec[:m], n=n_fft, axis=1) * w[None, :]
                ola = _overlap_add(fr_, hop)                    # (m + 1) * hop samples
                ola[:hop] += carry
                sig_full[b0 * hop:(b0 + m) * hop] = ola[:m * hop]
                carry = ola[m * hop:].copy()
        sig_full[frames * hop:] = carry
        sig = sig_full[n_fft:n_fft + n]
        pk = float(np.max(np.abs(sig))) or 1.0
        out[c] = (sig / pk * 0.8 * float(level)).astype(np.float32)
    return out, int(sample_rate)


def synthesize(seed, **kw):
    """Literal → exact signal; anything else → generative signal. Returns ((channels, samples), sr)."""
    if is_literal(seed):
        return synthesize_literal(seed)
    return synthesize_generative(seed, **kw)


def roundtrip_error(signal, sample_rate, n_fft=1024):
    """Max abs difference after analyse → synthesize (proof of reach for this signal)."""
    x = np.asarray(signal, dtype=np.float64)
    y, _ = synthesize_literal(analyse(x, sample_rate, n_fft))
    x2 = x[None, :] if x.ndim == 1 else x
    return float(np.max(np.abs(x2 - y)))
