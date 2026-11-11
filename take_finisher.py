"""take_finisher.py — offline finish for a Live Player take.

GROOVEBOX_TAKE_FINISHER_20261111
  After a take is written, optionally:
    * remove DC
    * trim leading/trailing silence
    * peak-normalize
    * apply a short fade in/out
    * report before/after loudness (simple RMS / peak dBFS)

  Runs off the GUI thread. Never raises into the caller; returns the paths it wrote.
"""
from __future__ import annotations

import os
import numpy as np


def _rms_db(x: np.ndarray) -> float:
    if x.size == 0:
        return -120.0
    r = float(np.sqrt(np.mean(np.square(x.astype(np.float64)))))
    return 20.0 * np.log10(max(r, 1e-12))


def _peak_db(x: np.ndarray) -> float:
    if x.size == 0:
        return -120.0
    p = float(np.max(np.abs(x)))
    return 20.0 * np.log10(max(p, 1e-12))


def finish_wav(path: str, *, trim: bool = True, dc: bool = True, normalize: bool = True,
               fade_ms: float = 15.0, target_peak: float = 0.89) -> dict:
    """Process a float/PCM WAV in place (writes a sibling *-finished.wav).

    Returns {"path", "before", "after", "error"}.
    """
    out = {"path": "", "before": {}, "after": {}, "error": ""}
    try:
        from scipy.io import wavfile
    except Exception:
        try:
            import soundfile as sf
            data, sr = sf.read(path, always_2d=False)
            x = np.asarray(data, dtype=np.float32)
            if x.ndim > 1:
                x = x.mean(axis=1)
            sr = int(sr)
        except Exception as exc:
            out["error"] = f"no wav reader: {exc}"
            return out
    else:
        try:
            sr, data = wavfile.read(path)
            x = np.asarray(data)
            if x.dtype.kind == "i":
                x = x.astype(np.float32) / float(np.iinfo(x.dtype).max or 1)
            elif x.dtype == np.float64:
                x = x.astype(np.float32)
            if x.ndim > 1:
                x = x.mean(axis=1)
            sr = int(sr)
        except Exception as exc:
            out["error"] = f"read failed: {exc}"
            return out

    out["before"] = {"rms_db": round(_rms_db(x), 2), "peak_db": round(_peak_db(x), 2)}
    if dc and x.size:
        x = x - float(np.mean(x))
    if trim and x.size:
        thr = 0.001
        nz = np.where(np.abs(x) > thr)[0]
        if nz.size:
            a = max(0, int(nz[0]) - int(sr * 0.01))
            b = min(x.size, int(nz[-1]) + int(sr * 0.02))
            x = x[a:b]
    if fade_ms > 0 and x.size:
        n = min(x.size // 4, max(1, int(sr * fade_ms / 1000.0)))
        env = np.ones(x.size, dtype=np.float32)
        env[:n] = np.linspace(0.0, 1.0, n, dtype=np.float32)
        env[-n:] = np.linspace(1.0, 0.0, n, dtype=np.float32)
        x = x * env
    if normalize and x.size:
        peak = float(np.max(np.abs(x))) or 1.0
        x = x * (float(target_peak) / peak)
    out["after"] = {"rms_db": round(_rms_db(x), 2), "peak_db": round(_peak_db(x), 2)}

    base, ext = os.path.splitext(path)
    dst = base + "-finished" + (ext or ".wav")
    try:
        from scipy.io import wavfile
        wavfile.write(dst, sr, x.astype(np.float32))
    except Exception:
        try:
            import soundfile as sf
            sf.write(dst, x.astype(np.float32), sr)
        except Exception as exc:
            out["error"] = f"write failed: {exc}"
            return out
    out["path"] = dst
    return out


def finish_paths(paths: list[str]) -> list[dict]:
    """Finish every WAV in the list. Safe to call from a worker thread."""
    done = []
    for p in paths or []:
        if str(p).lower().endswith(".wav") and os.path.isfile(p):
            done.append(finish_wav(p))
    return done
