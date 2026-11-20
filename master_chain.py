"""GROOVEBOX_R124_MASTER_CHAIN: the one ordered master post-processing chain.

    EQ (3-band tilt/shelf) → dynamics (feed-forward RMS compressor) → spatial (mid/side width)
    → limiter (look-ahead peak ceiling, true-peak aware in "final" mode) → dither ("final" only)

Every stage reports before/after measurements from measure_core, so the chain is measurable end to
end. Two quality modes share the exact same stages:
    live  – no oversampling, short look-ahead (low latency)
    final – 4× oversampled limiter detection, 5 ms look-ahead, TPDF dither to the target bit depth
Settings live in compat_settings key ``master_chain`` so projects/renders are reproducible.
"""
from __future__ import annotations

import copy
import math

import numpy as np

import measure_core as mc

DEFAULTS = {
    "enabled": True,
    "mode": "live",                     # live | final
    "eq": {"low_db": 0.0, "mid_db": 0.0, "high_db": 0.0, "low_hz": 180.0, "high_hz": 4500.0},
    "dyn": {"threshold_db": -14.0, "ratio": 2.0, "attack_ms": 8.0, "release_ms": 120.0, "makeup_db": 0.0, "on": False},  # transparent by default
    "spatial": {"width": 1.0},          # 0 mono … 1 unchanged … 2 wide
    "limiter": {"ceiling_db": -1.0, "on": True},
    "dither_bits": 24,
}
STAGES = ("eq", "dyn", "spatial", "limiter", "dither")


def load():
    st = copy.deepcopy(DEFAULTS)
    try:
        import compat_settings as cs
        user = cs.load().get("master_chain") or {}
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(st.get(k), dict):
                st[k].update(v)
            else:
                st[k] = v
    except Exception:
        pass
    return st


def save(st):
    try:
        import compat_settings as cs
        cs.update(master_chain=st)
    except Exception:
        pass


def _one_pole_split(x, sr, hz):
    """Complementary low/high split (one-pole, exact reconstruction: low + high == x)."""
    a = math.exp(-2.0 * math.pi * float(hz) / float(sr))
    try:
        from scipy.signal import lfilter
        low = lfilter([1.0 - a], [1.0, -a], x, axis=0)  # FX_AUDIT_OK master chain EQ split
    except Exception:
        low = np.zeros_like(x); s = np.zeros(x.shape[1])
        for i in range(x.shape[0]):
            s = (1.0 - a) * x[i] + a * s; low[i] = s
    return low, x - low


def stage_eq(x, sr, p):
    if not any(abs(float(p.get(k, 0.0))) > 1e-6 for k in ("low_db", "mid_db", "high_db")):
        return x
    low, rest = _one_pole_split(x, sr, p.get("low_hz", 180.0))
    mid, high = _one_pole_split(rest, sr, p.get("high_hz", 4500.0))
    g = lambda db: 10.0 ** (float(db) / 20.0)
    return low * g(p["low_db"]) + mid * g(p["mid_db"]) + high * g(p["high_db"])


def stage_dyn(x, sr, p):
    if not p.get("on", True) or float(p.get("ratio", 1.0)) <= 1.0:
        return x * 10.0 ** (float(p.get("makeup_db", 0.0)) / 20.0)
    thr, ratio = float(p["threshold_db"]), float(p["ratio"])
    att = math.exp(-1.0 / max(1.0, float(p["attack_ms"]) * 1e-3 * sr))
    rel = math.exp(-1.0 / max(1.0, float(p["release_ms"]) * 1e-3 * sr))
    lvl = np.mean(x * x, axis=1)
    hop = 32                                    # control rate; gain is interpolated back to audio rate
    n = lvl.shape[0]; m = (n + hop - 1) // hop
    ctrl = np.array([float(np.mean(lvl[i * hop:(i + 1) * hop])) for i in range(m)])
    env = -200.0; gains = np.ones(m)          # start from silence (no gain dip at the first sample)
    a_c, r_c = att ** hop, rel ** hop
    for i, v in enumerate(ctrl):
        db = 10.0 * math.log10(v) if v > 1e-20 else -200.0
        coef = a_c if db > env else r_c
        env = coef * env + (1.0 - coef) * db
        over = env - thr
        gains[i] = 10.0 ** ((-(over - over / ratio) if over > 0 else 0.0) / 20.0)
    g = np.interp(np.arange(n), np.arange(m) * hop + hop / 2.0, gains)
    return x * g[:, None] * 10.0 ** (float(p.get("makeup_db", 0.0)) / 20.0)


def stage_spatial(x, _sr, p):
    w = float(p.get("width", 1.0))
    if x.shape[1] < 2 or abs(w - 1.0) < 1e-6:
        return x
    mid = (x[:, 0] + x[:, 1]) * 0.5; side = (x[:, 0] - x[:, 1]) * 0.5 * w
    out = x.copy(); out[:, 0] = mid + side; out[:, 1] = mid - side
    return out


def stage_limiter(x, sr, p, mode="live"):
    if not p.get("on", True):
        return x
    ceil = 10.0 ** (float(p.get("ceiling_db", -1.0)) / 20.0)
    look = int(sr * (0.005 if mode == "final" else 0.0015))
    det = np.max(np.abs(x), axis=1)
    if mode == "final" and x.shape[0] >= 8:
        n = x.shape[0]
        up = np.fft.irfft(np.fft.rfft(x, axis=0), n=n * 4, axis=0) * 4.0
        det = np.max(np.abs(up).reshape(n, 4, -1), axis=(1, 2))
    need = np.minimum(1.0, ceil / np.maximum(det, 1e-12))
    if look > 1:
        # running minimum over the look-ahead window so gain is down before the peak arrives
        pad = np.concatenate([need, np.ones(look)])
        win = np.lib.stride_tricks.sliding_window_view(pad, look + 1)[: need.shape[0]]
        need = win.min(axis=1)
    rel = math.exp(-1.0 / max(1.0, 0.05 * sr))
    g = np.empty_like(need); cur = 1.0
    for i, v in enumerate(need):
        cur = v if v < cur else rel * cur + (1.0 - rel) * v
        g[i] = cur
    y = x * g[:, None]
    return np.clip(y, -ceil, ceil)


def stage_dither(x, bits, seed=0):
    bits = int(bits)
    if bits >= 32 or bits < 8:
        return x
    q = 1.0 / (2 ** (bits - 1))
    rng = np.random.default_rng(seed)
    tpdf = (rng.random(x.shape) - rng.random(x.shape)) * q
    return np.round((x + tpdf) / q) * q


def process(x, sr, st=None, mode=None, measure=True):
    """Run the chain. Returns (y, report) where report[stage] = {"in": summary, "out": summary}."""
    st = st or load()
    mode = mode or st.get("mode", "live")
    y = mc.as_2d(x).copy()
    report = {"mode": mode, "stages": []}
    if not st.get("enabled", True):
        return y, report
    for name in STAGES:
        before = mc.summary(y, sr) if measure else None
        if name == "eq":
            y = stage_eq(y, sr, st["eq"])
        elif name == "dyn":
            y = stage_dyn(y, sr, st["dyn"])
        elif name == "spatial":
            y = stage_spatial(y, sr, st["spatial"])
        elif name == "limiter":
            y = stage_limiter(y, sr, st["limiter"], mode)
        elif name == "dither":
            if mode != "final":
                continue
            y = stage_dither(y, st.get("dither_bits", 24))
        if measure:
            report["stages"].append({"stage": name, "in": before, "out": mc.summary(y, sr)})
    return y, report


def latency_samples(sr, mode="live"):
    return int(sr * (0.005 if mode == "final" else 0.0015))
