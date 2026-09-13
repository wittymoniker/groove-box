"""Audio-export integrity helpers for Mathematician's Groovebox.

Qt-free on purpose so the numerical/codec path can be regression-tested in
headless build/ISO environments.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
from typing import Tuple

import numpy as np


def quantize_float_master(master, bit_depth: int = 16):
    """Quantize float audio in [-1, 1] at the *actual* requested PCM depth.

    24-bit PCM uses int32 storage with the meaningful range ±8388607; callers
    then pack the low 24 bits into a PCM24 container.  This avoids the old bug
    where a 16-bit-scaled signal (±32767) was written as PCM24, attenuating the
    source by ~48.16 dB before MP3/other lossy encoding.
    """
    arr = np.nan_to_num(np.asarray(master, dtype=np.float32).reshape(-1),
                        nan=0.0, posinf=1.0, neginf=-1.0)
    arr = np.clip(arr, -1.0, 1.0)
    bits = 24 if int(bit_depth or 16) >= 24 else 16
    if bits == 24:
        return np.rint(arr * 8388607.0).astype(np.int32)
    return np.rint(arr * 32767.0).astype(np.int16)


def normalized_pcm_peak(pcm, bit_depth: int = 16) -> float:
    arr = np.asarray(pcm).reshape(-1)
    if arr.size == 0:
        return 0.0
    bits = 24 if int(bit_depth or 16) >= 24 else 16
    denom = 8388607.0 if bits == 24 else 32767.0
    return float(np.max(np.abs(arr.astype(np.float64)))) / denom


def decoded_peak_db(ffmpeg: str, path: str, timeout: int = 240):
    """Return FFmpeg volumedetect max_volume dB, or None if unavailable."""
    if not ffmpeg or not path or not os.path.exists(path):
        return None
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", path,
         "-vn", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=timeout,
    )
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    m = re.search(r"max_volume:\s*(-?(?:\d+(?:\.\d*)?|\.\d+)|-?inf)\s*dB", text, re.I)
    if not m:
        return None
    raw = m.group(1).lower()
    if "inf" in raw:
        return -math.inf
    try:
        return float(raw)
    except Exception:
        return None


def verify_encoded_level(ffmpeg: str, path: str, expected_peak: float,
                         max_attenuation_db: float = 18.0) -> Tuple[bool, str]:
    """Verify that a non-silent source did not become effectively silent.

    This is not normalization and does not modify the file.  It only compares
    the encoded artifact's measured peak with the already-rendered master peak.
    Intentional exact silence remains valid.
    """
    expected_peak = float(expected_peak or 0.0)
    if expected_peak == 0.0:
        return True, "source is exact silence"
    if expected_peak < 0.0 or not math.isfinite(expected_peak):
        return False, "invalid expected source peak"
    got_db = decoded_peak_db(ffmpeg, path)
    if got_db is None:
        # Verification unavailable is not itself an export failure.
        return True, "encoded level probe unavailable"
    if got_db == -math.inf:
        return False, "encoded artifact decodes to exact silence"
    expected_db = 20.0 * math.log10(expected_peak)
    attenuation = expected_db - got_db
    if attenuation > float(max_attenuation_db):
        return False, (
            f"encoded artifact is {attenuation:.1f} dB quieter than the rendered master "
            f"(master {expected_db:.1f} dBFS, encoded {got_db:.1f} dBFS)"
        )
    return True, (
        f"encoded level verified (master {expected_db:.1f} dBFS, "
        f"encoded {got_db:.1f} dBFS)"
    )
