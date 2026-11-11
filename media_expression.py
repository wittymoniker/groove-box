"""media_expression.py — GROOVEBOX_R32_MEDIA_EXPRESSION_20261110

Every composition system expresses itself in VIDEO and GAMES as well as audio.

SOURCES (each 0..1, deterministic at a given beat t):
  seed        the seed program's value at t, rank-mapped over the song (seed_lang)
  canonical   mean active canonical level × canonical share (mode)
  geometry    ball height / cellular density proxy from the geometric mixer + ball params
  multidim    multidim share × its canonical share
  fx          max local+global FX / time-FX amount
  sample      generated-sample layer × its envelope at t

TARGETS (each source has an amount per target, editable in the Media Expression panel):
  video_brightness   → video engine region envelope (fade gain of every layer)
  video_pulse        → video engine live pulse (the same brighten that live keys add)
  game_pulse         → running game live pulse (scene / music reaction)
  game_gravity       → game playability gravity ×(0.6 … 1.6)
  game_speed         → game playability speed ×(0.7 … 1.4)

The bus ticks at 20 Hz on the GUI thread (cheap: arithmetic on cached state) while playing or
while a game / video view is open, and is idle otherwise. With all amounts at 0 nothing changes.
Because every source is a pure function of (project state, t), the video and game reaction is as
deterministic as the audio: same project + same t → same expression vector.
"""
from __future__ import annotations

import math
import time

SOURCES = ("seed", "canonical", "geometry", "multidim", "fx", "sample")
TARGETS = ("video_brightness", "video_pulse", "game_pulse", "game_gravity", "game_speed")
# R32.8 IDEAL DEFAULTS: the expression bus is OFF (stable) until a cell is set — video and games keep
# their own canonical behaviour exactly. "Suggested" fills a structural, non-artistic starting matrix.
DEFAULT = {}
SUGGESTED = {("seed", "video_brightness"): 0.5, ("canonical", "video_pulse"): 0.4, ("geometry", "game_pulse"): 0.5,
             ("seed", "game_speed"): 0.3, ("fx", "video_pulse"): 0.3, ("multidim", "game_gravity"): 0.3}


def matrix(app):
    m = getattr(app, "r32_expression_matrix", None)
    if not isinstance(m, dict):
        m = app.r32_expression_matrix = {"%s>%s" % k: v for k, v in DEFAULT.items()}
    return m


def _seed_value(app, t):
    cache = app.__dict__.setdefault("_r32_expr_seed_cache", {})
    raw = app._seed_text() if hasattr(app, "_seed_text") else ""
    key = (hash(raw), round(t * 4) / 4.0)
    if key in cache:
        return cache[key]
    try:
        import seed_lang
        gb = __import__("groovebox")
        ev = seed_lang.evaluate(raw, gb._seed_script_env(t_scalar=float(t)))
        v = ev.values[0] if ev.values else 0.0
        lo, hi = cache.get("_lo", v), cache.get("_hi", v)
        lo, hi = min(lo, v), max(hi, v)
        cache["_lo"], cache["_hi"] = lo, hi
        u = 0.5 if hi == lo else (v - lo) / (hi - lo)
    except Exception:
        u = 0.5
    if len(cache) > 4096:
        cache.clear()
    cache[key] = u
    return u


def sources(app, t):
    out = {"seed": _seed_value(app, t)}
    try:
        lv = getattr(app, "canonical_engine_levels", {}) or {}
        act = app._get_active_engine_set()
        share = float((getattr(app, "geometric_synth_mixer_state", {}) or {}).get("multidim_canon", 1.0))
        out["canonical"] = (sum(float(lv.get(k, 0)) for k in act) / max(1, len(act))) * share if act else 0.0
    except Exception:
        out["canonical"] = 0.0
    st = getattr(app, "geometric_synth_mixer_state", {}) or {}
    bl = getattr(app, "ball_synth_params", {}) or {}
    g = float(bl.get("gravity", 0.25) or 0.25)
    out["geometry"] = max(0.0, min(1.0, 0.5 * float(st.get("ball", 0.65)) * abs(math.sin(math.pi * t * (0.5 + abs(g))))
                                + 0.5 * float(st.get("cellular", 0.7)) * (0.5 + 0.5 * math.cos(2 * math.pi * t / 4))))
    out["multidim"] = float(st.get("multidim", 1.0)) * float(st.get("multidim_canon", 1.0))
    fxs = [0.0]
    for attr, keys in (("r32_fx_state", ("pkp", "fractal", "eqr", "hyper")), ("r32_time_fx", ("chorus", "flanger", "reverb"))):
        d = getattr(app, attr, {}) or {}
        for rec in [d.get("global", {})] + list((d.get("local", {}) or {}).values()):
            fxs += [float((rec or {}).get(k, 0) or 0) for k in keys]
    out["fx"] = min(1.0, max(fxs))
    sg = getattr(app, "r32_sample_global", None)
    try:
        if sg is not None and sg.layer > 0 and sg.buffer is not None:
            import sample_generator
            env = sample_generator.envelope(sg.buffer, sg.sr)
            out["sample"] = float(sg.layer) * float(env[int((t * 0.25 % 1.0) * (env.size - 1))]) / max(1e-9, float(env.max()))
        else:
            out["sample"] = 0.0
    except Exception:
        out["sample"] = 0.0
    return out


def _row_expression_scale(app, t):
    try:
        rows = getattr(app, "master_playlist_data", None) or []
        if not rows:
            return 1.0
        bpm = float(app.spin_bpm.value()) if hasattr(app, "spin_bpm") else 120.0
        beats_per_row = 4.0 * max(1, int(getattr(getattr(app, "spin_seq_length", None), "value", lambda: 16)()) // 4)
        r = rows[int(t / max(1e-6, beats_per_row)) % len(rows)]
        v = r.get("expression") if isinstance(r, dict) else None
        return 1.0 if v in (None, "") else max(0.0, min(2.0, float(v)))
    except Exception:
        return 1.0


def vector(app, t):
    src = sources(app, t); m = matrix(app)
    _k = _row_expression_scale(app, t)
    if _k != 1.0:
        src = {kk: max(0.0, min(1.0, vv * _k)) for kk, vv in src.items()}
    tgt = {k: 0.0 for k in TARGETS}
    for s, v in src.items():
        for k in TARGETS:
            a = float(m.get("%s>%s" % (s, k), 0.0) or 0.0)
            if a:
                tgt[k] += a * v
    return src, {k: max(0.0, min(1.0, v)) for k, v in tgt.items()}


def _now_beat(app):
    try:
        sr = float(getattr(app, "play_sample_rate", 48000) or 48000)
        sec = float(getattr(app, "play_cursor", 0) or 0) / sr
        bpm = float(app.spin_bpm.value()) if hasattr(app, "spin_bpm") else 120.0
        return sec * bpm / 60.0 if getattr(app, "is_playing", False) else time.monotonic() * bpm / 60.0
    except Exception:
        return time.monotonic() * 2.0


def tick(app):
    m = matrix(app)
    if not any(float(v or 0) for v in m.values()):
        return None
    t = _now_beat(app)
    src, tgt = vector(app, t)
    app.r32_expression_now = (t, src, tgt)
    eng = getattr(getattr(app, "video_synth_viewer", None), "engine", None) or getattr(app, "video_synth_engine", None)
    if eng is not None:
        if tgt["video_brightness"] > 0:
            eng._region_envelope = 0.55 + 0.9 * tgt["video_brightness"]
        if tgt["video_pulse"] > 0:
            eng._live_pulse = max(float(getattr(eng, "_live_pulse", 0.0) or 0.0), 0.6 * tgt["video_pulse"])
    game = getattr(app, "_live_game", None)
    if game is not None:
        if tgt["game_pulse"] > 0:
            game._live_pulse = max(float(getattr(game, "_live_pulse", 0.0) or 0.0), 0.6 * tgt["game_pulse"])
        try:
            import game_playability as gp
            base = app.__dict__.setdefault("_r32_expr_game_base", (gp.SETTINGS["gravity"], gp.SETTINGS["speed"]))
            if tgt["game_gravity"] > 0:
                gp.SETTINGS["gravity"] = base[0] * (0.6 + tgt["game_gravity"])
            if tgt["game_speed"] > 0:
                gp.SETTINGS["speed"] = base[1] * (0.7 + 0.7 * tgt["game_speed"])
        except Exception:
            pass
    return src, tgt


def install(app):
    from PyQt6.QtCore import QTimer
    if getattr(app, "_r32_expr_timer", None) is not None:
        return
    t = app._r32_expr_timer = QTimer(app); t.setInterval(50)

    def _tick():
        if getattr(app, "is_playing", False) or getattr(app, "_live_game", None) is not None or \
                getattr(app, "_r32_expr_force", False):
            try:
                tick(app)
            except Exception:
                pass
    t.timeout.connect(_tick); t.start()


# ---------------------------------------------------------------------------
# AUDIO-DERIVED expression (GROOVEBOX_R32_AUDIO_VIDEO_CORRESPONDENCE_20261110)
# ---------------------------------------------------------------------------
# The video / game reaction is computed from an AUDIO FEATURE TRACK F = Φ(x) of the signal x:
#   per quarter-beat block k:  E_k = RMS,  B_k = spectral centroid / Nyquist,  O_k = onset density
#   (positive first difference of 4 ms block energy above its median), all rank-normalised.
# Φ is a pure function of the samples (no clock, no RNG), so:
#   x_internal = render(project)  and  x_fed = the same samples played/imported
#   ⇒ Φ(x_internal) = Φ(x_fed) ⇒ identical expression vectors ⇒ identical video & game dynamics.
# In "audio" mode the six sources become: seed←E, canonical←O, geometry←B, multidim←(E+B)/2,
# fx←O·B, sample←E·(1−B); the matrix and targets are unchanged.

import numpy as _np

MODES = ("composition", "audio")


def feature_track(x, sr, bpm=120.0):
    x = _np.asarray(x, dtype=_np.float64)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if x.size < 64:
        return None
    blk = max(64, int(round(sr * 60.0 / max(20.0, float(bpm)) / 4.0)))       # quarter-beat blocks
    n = x.size // blk
    if n < 1:
        return None
    X = x[: n * blk].reshape(n, blk)
    E = _np.sqrt((X * X).mean(axis=1))
    spec = _np.abs(_np.fft.rfft(X * _np.hanning(blk), axis=1))
    fr = _np.arange(spec.shape[1]) / float(spec.shape[1])
    B = (spec * fr).sum(axis=1) / _np.maximum(1e-12, spec.sum(axis=1))
    sub = max(1, int(sr * 0.004))
    m = (blk // sub) * sub
    e4 = (X[:, :m].reshape(n, -1, sub) ** 2).mean(axis=2)
    d = _np.diff(e4, axis=1, prepend=e4[:, :1])
    thr = _np.median(_np.abs(d)) + 1e-12
    O = (d > 3 * thr).mean(axis=1)

    def rk(v):
        if v.size < 2 or _np.allclose(v, v[0]):
            return _np.full(v.size, 0.5)
        return _np.argsort(_np.argsort(v, kind="stable"), kind="stable") / float(v.size - 1)
    return {"E": rk(E), "B": rk(B), "O": rk(O), "block": blk, "sr": int(sr), "bpm": float(bpm)}


def audio_sources(track, t_beats):
    k = int(max(0, t_beats) * 4.0) % max(1, track["E"].size)
    E, B, O = float(track["E"][k]), float(track["B"][k]), float(track["O"][k])
    return {"seed": E, "canonical": O, "geometry": B, "multidim": 0.5 * (E + B), "fx": O * B, "sample": E * (1 - B)}


def set_audio(app, samples, sr):
    """Feed samples (the internal render, an import, a carrier, a live take): the video/game
    expression is then computed from these samples alone."""
    bpm = float(app.spin_bpm.value()) if hasattr(app, "spin_bpm") else 120.0
    app._r32_expr_track = feature_track(samples, sr, bpm)
    return app._r32_expr_track is not None


def _sources_dispatch(app, t, _orig=sources):
    if getattr(app, "r32_expression_mode", "composition") == "audio":
        tr = getattr(app, "_r32_expr_track", None)
        if tr is None:
            try:
                cache = getattr(app, "_shared_mixdown_cache", None) or {}
                last = next(reversed(cache.values())) if cache else None
                buf, rate = (last[0], last[1]) if isinstance(last, tuple) and len(last) >= 2 else (None, None)
                if buf is not None:
                    set_audio(app, buf, rate); tr = app._r32_expr_track
            except Exception:
                tr = None
        if tr is not None:
            return audio_sources(tr, t)
    return _orig(app, t)


sources = _sources_dispatch
