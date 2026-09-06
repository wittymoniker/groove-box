"""OS/standalone audio compatibility layer for Mathematician's Groovebox.

Goals:
- zero SciPy dependency for PCM WAV I/O;
- one lazy/optional sounddevice import for realtime PortAudio access;
- keep NumPy as the buffer/interchange layer while native C++ handles hot DSP.
"""
from __future__ import annotations

import wave
from pathlib import Path
import numpy as np

try:
    import sounddevice as sd  # optional realtime backend, bundled in standalone builds
    HAS_SOUNDDEVICE = True
except Exception:
    sd = None
    HAS_SOUNDDEVICE = False


def read_wav(path):
    """Read PCM WAV into a NumPy array, scipy.io.wavfile-compatible ordering.

    Supports unsigned 8-bit and signed 16/24/32-bit PCM. 24-bit is expanded to
    int32 with sign extension. Multi-channel data is returned shape (frames, ch).
    """
    path = str(Path(path))
    with wave.open(path, "rb") as wf:
        channels = int(wf.getnchannels())
        sr = int(wf.getframerate())
        width = int(wf.getsampwidth())
        frames = int(wf.getnframes())
        raw = wf.readframes(frames)
    if width == 1:
        arr = np.frombuffer(raw, dtype=np.uint8).copy()
    elif width == 2:
        arr = np.frombuffer(raw, dtype="<i2").copy()
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        vals = (b[:, 0].astype(np.int32)
                | (b[:, 1].astype(np.int32) << 8)
                | (b[:, 2].astype(np.int32) << 16))
        vals = (vals ^ 0x800000) - 0x800000
        arr = vals
    elif width == 4:
        arr = np.frombuffer(raw, dtype="<i4").copy()
    else:
        raise RuntimeError(f"Unsupported PCM WAV sample width: {width} bytes")
    if channels > 1:
        arr = arr.reshape(-1, channels)
    return sr, arr


def write_wav(path, sample_rate, data):
    """Write integer or float PCM WAV without SciPy.

    Float arrays are clipped to [-1,1] and encoded as signed 16-bit PCM.
    Integer arrays preserve 8/16/32-bit width; int64 is safely narrowed to 32-bit.
    """
    arr = np.asarray(data)
    if arr.ndim == 1:
        channels = 1
    elif arr.ndim == 2:
        channels = int(arr.shape[1])
    else:
        raise ValueError("WAV data must be 1-D mono or 2-D frames×channels")

    if np.issubdtype(arr.dtype, np.floating):
        out = (np.clip(arr, -1.0, 1.0) * 32767.0).astype("<i2")
        width = 2
    elif arr.dtype == np.uint8:
        out = np.ascontiguousarray(arr)
        width = 1
    elif arr.dtype.itemsize <= 2:
        out = np.ascontiguousarray(arr.astype("<i2", copy=False))
        width = 2
    else:
        out = np.ascontiguousarray(np.clip(arr, -2147483648, 2147483647).astype("<i4"))
        width = 4

    with wave.open(str(Path(path)), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(int(sample_rate))
        wf.writeframes(out.tobytes(order="C"))


class _WavfileCompat:
    read = staticmethod(read_wav)
    write = staticmethod(write_wav)


wavfile = _WavfileCompat()
