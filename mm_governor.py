"""mm_governor.py: trigonometric response carrier-dynamic modulation GOVERNOR and carrier ROUTER for the Mod Matrix.

RESPONSE (per row): the row's 0..1 output is shaped by a trigonometric response before it reaches its target,
    linear · sine · cosine · sin² · tanh-soft · arcsin · tri-fold · harmonic
    with `resp_freq` (cycles of the curve across 0..1) and `resp_phase` (0..1 turn).

ROUTER (per row): `route` = extra targets; `spread` 0..1 gives target k the phase offset 2π·k·spread/N of the
    response, so one source fans out as a rotating trigonometric family (a "carrier ring"). Sources
    carrier:global / carrier:<instrument> follow the RMS envelope of that carrier audio at the playhead.

GOVERNOR (whole matrix): every row's deviation from centre (v − 0.5) × amount is counted against a modulation
    budget with a sine soft knee (no hard clipping), changes are slew-limited per second, and with
    carrier_follow > 0 all depth breathes with the chosen carrier's envelope (dynamic, carrier-driven).

FAIR CANONICAL CONTROL: the budget is split. Canonical rows (canonical > 0 or canonical entries) own
    `canonical_share` of it, user rows the rest, and each side is only throttled inside its own share, so
    neither can starve the other. While canonicals are active (level L), the governor's own settings
    (budget, slew, carrier follow, response phase) are steered toward their canonical (seed-curve) values by
    canonical_share × L. Live play and every export run the same code (the matrix tick).
"""
from __future__ import annotations
import math

RESPONSES = ("linear", "sine", "cosine", "sin²", "tanh-soft", "arcsin", "tri-fold", "harmonic",
             "quetta", "betta", "metta")       # R101: self-reference curves from the Eski constants
DEFAULTS = {"enabled": False, "budget": 1.5, "slew": 6.0, "carrier_follow": 0.0, "carrier": "global",
            "knee": 0.8, "canonical_share": 0.5}
_ENV = {}


def settings(app):
    g = getattr(app, "r101_mm_governor", None)
    if not isinstance(g, dict):
        g = app.r101_mm_governor = dict(DEFAULTS)
    for k, v in DEFAULTS.items():
        g.setdefault(k, v)
    return g


# ------------------------------------------------------------------ response
def respond(v, kind="linear", freq=1.0, phase=0.0):
    v = max(0.0, min(1.0, float(v))); f = max(0.0625, float(freq or 1.0)); ph = 2 * math.pi * float(phase or 0.0)
    x = 2 * math.pi * f * v + ph
    if kind == "sine":
        return 0.5 + 0.5 * math.sin(x - math.pi / 2)            # 0 → 0, 1 → 1 for f = 0.5 … S-curve family
    if kind == "cosine":
        return 0.5 + 0.5 * math.cos(x)
    if kind == "sin²":
        return math.sin(x / 2) ** 2
    if kind == "tanh-soft":
        return 0.5 + 0.5 * math.tanh(3.0 * f * (v - 0.5) + math.sin(ph))
    if kind == "arcsin":
        return 0.5 + math.asin(max(-1.0, min(1.0, 2 * v - 1))) / math.pi
    if kind == "tri-fold":
        u = (f * v + float(phase or 0.0)) % 1.0
        return 1 - abs(2 * u - 1)
    if kind in ("quetta", "betta", "metta"):
        import eski_constants as ek
        c = {"quetta": ek.Q, "betta": ek.B, "metta": ek.M}[kind]
        y = (1.0 + v * (c - 1.0)) ** (1.0 + v * (c - 1.0))            # self-power across 1 .. c
        lo, hi = 1.0, c ** c
        u = (y - lo) / (hi - lo)
        return max(0.0, min(1.0, 0.5 + 0.5 * math.sin(math.pi * (u - 0.5) * f + ph))) if (f != 1.0 or ph) else u
    if kind == "harmonic":
        return 0.5 + 0.25 * math.sin(x) + 0.15 * math.sin(2 * x) + 0.1 * math.sin(3 * x)
    return v


# ------------------------------------------------------------------ carrier envelope
def _carrier_wave(app, name):
    if name in ("global", "", None):
        return getattr(app, "imported_waveform", None), float(getattr(app, "imported_sample_rate", 48000) or 48000)
    m = (getattr(app, "instrument_media_samples", {}) or {}).get(name) or {}
    return m.get("waveform"), float(m.get("sample_rate", 48000) or 48000)


def carrier_env(app, name, beat):
    """0..1 RMS envelope of a carrier at the playhead (20 frames/s, cached per waveform object)."""
    y, sr = _carrier_wave(app, name)
    if y is None:
        return 0.0
    try:
        import numpy as np
        key = (name, id(y))
        env = _ENV.get(key)
        if env is None:
            a = np.asarray(y, dtype=np.float32)
            if a.ndim == 2:
                a = a.mean(axis=1)
            hop = max(1, int(sr / 20)); n = len(a) // hop
            if n < 1:
                return 0.0
            e = np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
            env = e / (float(e.max()) or 1.0)
            if len(_ENV) > 32:
                _ENV.clear()
            _ENV[key] = env
        bpm = float(app.spin_bpm.value()) if hasattr(app, "spin_bpm") else 120.0
        i = int(beat * 60.0 / max(1.0, bpm) * 20) % len(env)
        return float(env[i])
    except Exception:
        return 0.0


def carrier_sources(app):
    out = ["carrier:global"]
    out += ["carrier:%s" % n for n, m in (getattr(app, "instrument_media_samples", {}) or {}).items()
            if isinstance(m, dict) and m.get("waveform") is not None][:48]
    return out


# ------------------------------------------------------------------ canonical fairness
def _canon_level(app):
    try:
        import r32_finish as rf
        return max(0.0, min(1.0, float(rf.canonical_level(app))))
    except Exception:
        return 0.0


def _canon_curve(app, key, beat):
    try:
        import automation_bus as ab
        return float(ab._canonical_curve(app, {"path": "governor:" + key, "rate": 16.0}, beat))
    except Exception:
        return 0.5


def effective(app, beat):
    """Governor settings after fair canonical steering (share × canonical level)."""
    g = dict(settings(app)); share = max(0.0, min(1.0, float(g.get("canonical_share", 0.5))))
    w = share * _canon_level(app)
    if w > 0:
        g["budget"] = (1 - w) * float(g["budget"]) + w * (0.5 + 2.5 * _canon_curve(app, "budget", beat))
        g["slew"] = (1 - w) * float(g["slew"]) + w * (1.0 + 11.0 * _canon_curve(app, "slew", beat))
        g["carrier_follow"] = (1 - w) * float(g["carrier_follow"]) + w * _canon_curve(app, "follow", beat)
        g["phase_offset"] = w * _canon_curve(app, "phase", beat)
    g["_canon_weight"] = w
    return g


def is_canonical_row(row):
    return bool(row.get("canonical_entry")) or float(row.get("canonical", 0.0) or 0.0) > 0.0


# ------------------------------------------------------------------ the governor pass
def govern(app, rows, outs, beat, now=None):
    """Shape (response) and govern (budget · slew · carrier follow) the matrix outputs. Returns new outs."""
    import time as _t
    g = effective(app, beat)
    shaped = []
    for row, v in zip(rows, outs):
        shaped.append(respond(v, str(row.get("response", "linear")), row.get("resp_freq", 1.0),
                              float(row.get("resp_phase", 0.0) or 0.0) + float(g.get("phase_offset", 0.0))))
    try:                                   # R101 fields: reroute poles (2-D) + perspective (3-D rotation, magnitude)
        import mm_fields
        shaped = mm_fields.apply(app, rows, shaped, beat, float(g.get("_canon_weight", 0.0)))
    except Exception:
        pass
    if not g.get("enabled"):
        app._r101_mm_out = list(shaped)
        return shaped
    follow = max(0.0, min(1.0, float(g.get("carrier_follow", 0.0))))
    depth = 1.0
    if follow > 0:
        depth = (1 - follow) + follow * carrier_env(app, str(g.get("carrier", "global")), beat)
    budget = max(0.05, float(g.get("budget", 1.5))); knee = max(0.05, min(1.0, float(g.get("knee", 0.8))))
    share = max(0.0, min(1.0, float(g.get("canonical_share", 0.5))))
    # fair split: canonical rows and user rows each get their own part of the budget
    groups = {True: share * budget, False: (1 - share) * budget}
    total = {True: 0.0, False: 0.0}
    dev = []
    for row, v in zip(rows, shaped):
        d = (v - 0.5) * abs(float(row.get("amount", 0.5) or 0.0)) * depth
        dev.append(d); total[is_canonical_row(row)] += abs(d)
    scale = {}
    for side in (True, False):
        b, t = max(1e-6, groups[side]), total[side]
        if t <= knee * b:
            scale[side] = 1.0
        else:                                   # sine soft knee: approaches b smoothly, never clips
            over = (t - knee * b) / max(1e-6, (1 - knee) * b + 1e-6)
            limited = knee * b + (1 - knee) * b * math.sin(min(math.pi / 2, over * math.pi / 2))
            scale[side] = limited / t
    now = _t.monotonic() if now is None else now
    out = []
    for row, v, d in zip(rows, shaped, dev):
        amt = abs(float(row.get("amount", 0.5) or 0.0)) or 1.0
        target = 0.5 + d * scale[is_canonical_row(row)] / amt
        last, tl = row.get("_gov_last"), row.get("_gov_t")
        if last is not None and tl is not None:
            dt = max(0.0, min(0.5, now - tl)); lim = float(g.get("slew", 6.0)) * dt
            target = max(last - lim, min(last + lim, target))
        row["_gov_last"], row["_gov_t"] = target, now
        out.append(max(0.0, min(1.0, target)))
    app._r101_mm_out = list(out)
    app._r101_governor_view = {"depth": depth, "scale_canonical": scale[True], "scale_user": scale[False],
                               "canonical_weight": g["_canon_weight"], "budget": budget}
    return out


def routed(row, v_raw, g_phase=0.0):
    """(target, value) for every route target of a row: rotating trigonometric family by spread."""
    extra = [t.strip() for t in (row.get("route") or []) if str(t).strip()] if isinstance(row.get("route"), list) else \
            [t.strip() for t in str(row.get("route") or "").split(",") if t.strip()]
    if not extra:
        return []
    n = len(extra) + 1; spread = float(row.get("spread", 0.25) or 0.0)
    kind = str(row.get("response", "linear"))
    if kind == "linear":
        kind = "sine"                            # a ring needs a periodic response
    out = []
    for k, t in enumerate(extra, start=1):
        ph = float(row.get("resp_phase", 0.0) or 0.0) + g_phase + k * spread / n
        out.append((t, respond(v_raw, kind, row.get("resp_freq", 1.0), ph)))
    return out
