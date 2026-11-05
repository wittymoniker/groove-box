"""GROOVEBOX_R23R_DEVICE_PROFILES_20261103 — one audio setup for the whole app.

Each output device (as PortAudio or the sound server names it) can carry:

  enabled  — part of "All outputs" (the combined sink / fan-out) or not
  rate     — sample rate the app opens it at (0 = automatic negotiation)
  bits     — 16 / 24 / 32 integer or 0 = 32-bit float (PortAudio converts)

Set once in 🔊 Hardware & Master → Devices; every stream the app opens (transport,
keys, Live Player, players via mpv) then matches that device's format — no
per-window device menus. Stored in state/audio_device_profiles.json.
"""
from __future__ import annotations

import json
import os
import threading

RATES = (44100, 48000, 88200, 96000, 176400, 192000)
BITS = (0, 16, 24, 32)          # 0 = float32
_LOCK = threading.Lock()
_CACHE = {"data": None, "mtime": None}


def _path():
    try:
        import groovebox_paths
        d = groovebox_paths.state_dir()
    except Exception:
        d = os.path.join(os.path.expanduser("~"), ".groovebox")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "audio_device_profiles.json")


def load():
    p = _path()
    with _LOCK:
        try:
            mt = os.path.getmtime(p)
        except OSError:
            mt = None
        if _CACHE["data"] is not None and _CACHE["mtime"] == mt:
            return dict(_CACHE["data"])
        data = {}
        if mt is not None:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = dict(json.load(f) or {})
            except Exception:
                data = {}
        _CACHE.update(data=data, mtime=mt)
        return dict(data)


def save(data):
    p = _path()
    tmp = p + ".tmp"
    with _LOCK:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, sort_keys=True)
        os.replace(tmp, p)
        _CACHE.update(data=dict(data), mtime=os.path.getmtime(p))


def get(name):
    d = {"enabled": True, "rate": 0, "bits": 0}
    if name:
        d.update(load().get(str(name), {}) or {})
    return d


def set_profile(name, **kw):
    data = load()
    cur = get(name)
    cur.update({k: v for k, v in kw.items() if k in ("enabled", "rate", "bits")})
    data[str(name)] = cur
    save(data)


def enabled(name):
    return bool(get(name).get("enabled", True))


def rate(name):
    try:
        return int(get(name).get("rate", 0) or 0)
    except Exception:
        return 0


def bits(name):
    try:
        b = int(get(name).get("bits", 0) or 0)
    except Exception:
        b = 0
    return b if b in BITS else 0


def probe(sd, index, channels=2):
    """Rates and bit depths this device accepts (PortAudio check, no stream opened)."""
    rates, depths = [], []
    for r in RATES:
        try:
            sd.check_output_settings(device=int(index), samplerate=r, channels=int(channels), dtype="float32")
            rates.append(r)
        except Exception:
            pass
    r0 = rates[0] if rates else 48000
    for b, dt in ((16, "int16"), (24, "int24"), (32, "int32"), (0, "float32")):
        try:
            sd.check_output_settings(device=int(index), samplerate=r0, channels=int(channels), dtype=dt)
            depths.append(b)
        except Exception:
            pass
    return {"rates": rates, "bits": depths}


def wrap_params(params, name):
    """Apply a device's bit depth to an OutputStream parameter dict (float callbacks keep
    working: the samples are converted to the integer format right at the device).
    24-bit is sent in a 32-bit integer container."""
    b = bits(name)
    if b not in (16, 24, 32) or params.get("dtype", "float32") != "float32" or params.get("callback") is None:
        return params
    import numpy as np
    user_cb = params["callback"]
    dt = "int16" if b == 16 else "int32"
    scale = 32767.0 if b == 16 else 2147483647.0
    if b == 24:
        scale = 8388607.0 * 256.0          # 24 significant bits, left-aligned in 32
    p = dict(params)
    p["dtype"] = dt
    buf = {"f": None}

    def cb(outdata, frames, time_info, status):
        f = buf["f"]
        if f is None or f.shape != outdata.shape:
            f = buf["f"] = np.zeros(outdata.shape, dtype=np.float32)
        user_cb(f, frames, time_info, status)
        # integer formats have a fixed range: values beyond full scale cannot be represented
        # (the same thing the device does to float input); no limiter / gain change otherwise
        np.clip(f, -1.0, 1.0, out=f)
        if b == 24:
            outdata[:] = (np.round(f * 8388607.0).astype(np.int32) << 8)
        else:
            outdata[:] = np.round(f * scale).astype(dt)
    p["callback"] = cb
    return p
