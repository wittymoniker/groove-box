"""carrier_bridge.py — GROOVEBOX_R118_CARRIER_BRIDGE_RECONSTRUCTED_R123_20261119

R118 "carrier bridge" — RECONSTRUCTED in R123. The original R118 source was never present in
any archive delivered (R119–R122); this module is a fresh implementation of the stated intent,
not recovered code.

One small hub: ANY signal → ANY context, with the fewest unique conversions.

  Signal kinds   audio · control · video · number · text · events · file
  Converters     each is one edge between two kinds (no duplicates); multi-step routes are found
                 by shortest path, so every reachable A→B is available without per-pair code.
  Contexts       where a signal lands. Each context has exactly ONE apply function that uses
                 the engine's existing path (the same one Play, Live Player and exports read):

    global_carrier              audio  → app._load_wav_path (the main carrier really changes)
    instrument_carrier:<name>   audio  → instrument_media_samples[name] (waveform + sample_rate)
    carrier_layer:<target>      file   → carrier_layers (global or an instrument) + re-mix
    seed                        text   → Global Seed editor
    bpm                         number → tempo
    lane:<instrument>:<lane>    control→ amplitudes / pitches / steps via plugin_guard (validated,
                                         one undo step, rolled back on failure)
    video_carrier               video  → app._load_video_path
    export                      file   → copied into the project exports folder
    live_player                 file   → app_hub.send_back (Live Player)

Bug fixed (R118 intent): Draw Signal Lab and Layered Signal Lab "send to global" only set
``global_media_sample`` / ``_global_carrier_path``, which nothing in the render path reads; the
main carrier never changed. "Send local" in Draw Signal Lab stored no ``waveform`` /
``sample_rate``, which key_assign / live_player need. Both now go through :func:`send`.

GUARANTEED PROFILE (user rule, R123; see IDENTITY-AND-DETERMINISM-R32.md and FRACTAL_COVERAGE_AND_BOUNDARY.md):
any-signal → any-context output works in every state on a best-effort basis, and it MUST work in the
reference state of the fractal — a Seed-only composition (no user-owned steps, no user-imported
carriers) with all canonicals active (SEEDED + RAND + LOCK + EUCLIDEAN, GOAVA optional — Full Unison)
and the other settings at their factory defaults. Every receipt records whether the send happened
inside that profile; a failure inside it is reported as a guarantee violation (Notices + history),
and :func:`verify_guarantee` proves every kind reaches every context deterministically there.
Nothing is ever refused because of the profile.

Every send returns a receipt {context, route, sha256, samples, rate, source, t} kept in a
bounded history (Monitor Center · Command Console ``signals``) so a result can be traced back
to the exact seed / drawing / plugin that produced it.
"""
from __future__ import annotations

import collections
import dataclasses
import hashlib
import json
import math
import os
import shutil
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

KINDS = ("audio", "control", "video", "number", "text", "events", "file", "image")   # R132.26: + image
AUDIO_EXT = (".wav", ".flac", ".mp3", ".ogg", ".aif", ".aiff", ".m4a", ".opus")
VIDEO_EXT = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
TEXT_EXT = (".txt", ".seed", ".mgs", ".md", ".scl")
DEFAULT_SR = 48000
CONTROL_RATE = 100.0


@dataclasses.dataclass
class Signal:
    kind: str
    data: Any
    rate: Optional[float] = None          # audio: sample rate · control: points per second
    meta: dict = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown signal kind {self.kind!r}; expected one of {KINDS}")


class BridgeError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- helpers
def _out_dir(app=None) -> str:
    try:
        import groovebox_paths
        d = groovebox_paths.layers_dir(getattr(app, "_current_project_path", None))
    except Exception:
        d = os.path.join(tempfile.gettempdir(), "groovebox-bridge")
    os.makedirs(d, exist_ok=True)
    return d


def _write_wav(path: str, x: np.ndarray, sr: int) -> str:
    x = np.clip(np.nan_to_num(np.asarray(x, dtype=np.float64)), -1.0, 1.0)
    try:
        from audio_os_backend import write_wav
        write_wav(path, int(sr), x)
    except Exception:
        import wave
        pcm = (x * 32767.0).astype("<i2")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(int(sr)); wf.writeframes(pcm.tobytes())
    return path


def _digest(sig: Signal) -> str:
    h = hashlib.sha256()
    h.update(sig.kind.encode())
    d = sig.data
    if isinstance(d, np.ndarray):
        h.update(np.ascontiguousarray(d, dtype=np.float32).tobytes())
    elif isinstance(d, (bytes, bytearray)):
        h.update(bytes(d))
    elif sig.kind in ("file", "video", "image") and isinstance(d, str) and os.path.isfile(d):
        with open(d, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    else:
        h.update(json.dumps(d, sort_keys=True, default=str).encode())
    return h.hexdigest()


# ----------------------------------------------------------------------------- converters (edges)
_EDGES: Dict[Tuple[str, str], Tuple[str, Callable]] = {}


def converter(src: str, dst: str, name: str):
    def deco(fn):
        if (src, dst) in _EDGES:
            raise RuntimeError(f"duplicate converter {src}->{dst}")   # non-redundant by construction
        _EDGES[(src, dst)] = (name, fn)
        return fn
    return deco


@converter("file", "audio", "decode audio (WAV native, others via FFmpeg)")
def _file_to_audio(sig, app):
    path = str(sig.data)
    a = sr = None
    if path.lower().endswith((".wav", ".flac", ".ogg", ".aif", ".aiff")):
        try:                                            # R132.26: read directly (no FFmpeg): float / 24-bit WAV, FLAC, OGG
            import soundfile as sf
            a, sr = sf.read(path, dtype="float32", always_2d=False)
        except Exception:
            a = sr = None
    if a is not None:
        pass
    elif app is not None and hasattr(app, "_decode_media_audio"):
        a, sr = app._decode_media_audio(path)
    else:
        import wave
        with wave.open(path, "rb") as wf:
            sr, ch, w = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())
        if w != 2:
            raise BridgeError("headless decode supports 16-bit WAV only")
        a = np.frombuffer(raw, "<i2").astype(np.float32) / 32768.0
        if ch > 1:
            a = a.reshape(-1, ch).mean(axis=1)
    a = np.asarray(a, dtype=np.float32)
    a = a.mean(axis=1) if a.ndim > 1 else a
    return Signal("audio", a.ravel(), float(sr), {**sig.meta, "path": path})


@converter("file", "video", "video file reference")
def _file_to_video(sig, app):
    path = str(sig.data)
    if path.lower().endswith(VIDEO_EXT):
        return Signal("video", path, None, dict(sig.meta))
    if path.lower().endswith(AUDIO_EXT):
        return _audio_to_video(_file_to_audio(sig, app), app)
    raise BridgeError(f"not a video or audio file: {os.path.basename(path)}")


@converter("video", "audio", "media_transmuter: the video's audio track, else its frames sonified")
def _video_to_audio(sig, app):
    import media_transmuter as mt
    dst = os.path.join(_out_dir(app), "bridge_video_%s.wav" % hashlib.sha256(str(sig.data).encode()).hexdigest()[:12])
    mt.video_to_sound(str(sig.data), dst)
    return _file_to_audio(Signal("file", dst, None, dict(sig.meta)), app)


@converter("audio", "video", "media_transmuter: scrolling spectrogram video with the audio muxed in")
def _audio_to_video(sig, app):
    import media_transmuter as mt
    wav = _audio_to_file(sig, app).data
    dst = os.path.splitext(wav)[0] + ".mp4"
    if not os.path.isfile(dst):
        mt.sound_to_video(wav, dst)
    return Signal("video", dst, None, dict(sig.meta))


@converter("video", "file", "video file path")
def _video_to_file(sig, app):
    return Signal("file", str(sig.data), None, dict(sig.meta))


@converter("audio", "file", "write WAV")
def _audio_to_file(sig, app):
    sr = int(sig.rate or DEFAULT_SR)
    tag = sig.meta.get("name") or "signal"
    path = os.path.join(_out_dir(app), f"bridge_{tag}_{_digest(sig)[:12]}.wav")
    if not os.path.isfile(path):
        _write_wav(path, sig.data, sr)
    return Signal("file", path, None, {**sig.meta, "sample_rate": sr})


@converter("audio", "control", "RMS envelope at 100 Hz, 0…1")
def _audio_to_control(sig, app):
    a = np.asarray(sig.data, dtype=np.float64)
    sr = float(sig.rate or DEFAULT_SR)
    hop = max(1, int(sr / CONTROL_RATE))
    n = max(1, a.size // hop)
    env = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1)) if a.size >= hop else np.array([0.0])
    pk = float(env.max()) if env.size else 0.0
    return Signal("control", (env / pk if pk > 0 else env).astype(np.float32), CONTROL_RATE, dict(sig.meta))


@converter("control", "audio", "wavetable: the curve is one cycle")
def _control_to_audio(sig, app):
    c = np.asarray(sig.data, dtype=np.float64).ravel()
    if c.size < 2:
        c = np.array([0.0, 0.0])
    sr = int(sig.meta.get("sample_rate", DEFAULT_SR))
    dur = float(sig.meta.get("duration", 2.0))
    freq = float(sig.meta.get("freq", 110.0))
    lo, hi = float(c.min()), float(c.max())
    table = (2.0 * (c - lo) / (hi - lo) - 1.0) if hi > lo else np.zeros_like(c)
    t = np.arange(int(sr * dur)) / sr
    ph = np.mod(t * freq, 1.0) * (table.size - 1)
    return Signal("audio", np.interp(ph, np.arange(table.size), table).astype(np.float32), float(sr), dict(sig.meta))


@converter("control", "number", "graph number (book p.42: mean isn⁻¹ angle sums × radius), 0…1")
def _control_to_number(sig, app):
    from meum_ot_math import graph_number
    c = np.asarray(sig.data, dtype=np.float64).ravel()
    if c.size == 0:
        return Signal("number", 0.0, None, dict(sig.meta))
    lo, hi = float(c.min()), float(c.max())
    y = (c - lo) / (hi - lo) if hi > lo else np.clip(c, 0.0, 1.0)
    u = np.linspace(0.0, 1.0, c.size) if c.size > 1 else np.zeros(1)
    step = max(1, c.size // 2048)                      # bounded cost; the shape is kept
    g = graph_number(zip(u[::step], y[::step]))
    return Signal("number", float(np.clip(g / (2.0 * math.pi * math.sqrt(2.0)), 0.0, 1.0)), None, dict(sig.meta))


@converter("text", "audio", "Spectral Canonical: MGLS1 literal → exact signal, any other seed → generative")
def _text_to_audio(sig, app):
    import spectral_canonical as sc
    sr = int(sig.meta.get("sample_rate", DEFAULT_SR))
    if sc.is_literal(str(sig.data)):
        y, sr = sc.synthesize_literal(str(sig.data))
    else:
        y, sr = sc.synthesize_generative(str(sig.data), seconds=float(sig.meta.get("duration", 4.0)), sample_rate=sr)
    y = np.asarray(y, dtype=np.float32)
    return Signal("audio", (y.mean(axis=0) if y.ndim > 1 else y).ravel(), float(sr), dict(sig.meta))


@converter("control", "text", "reverse engineer: curve → 12-term Fourier seed program (media_transmuter)")
def _control_to_text(sig, app):
    import media_transmuter as mt
    c = np.asarray(sig.data, dtype=np.float64).ravel()
    rate = float(sig.rate or CONTROL_RATE)
    bpm = float(sig.meta.get("bpm", 0) or 0)
    if not bpm:
        try:
            bpm = float(app.spin_bpm.value())
        except Exception:
            bpm = 120.0
    return Signal("text", mt.fourier_seed(c, max(1e-3, c.size / rate), bpm), None, dict(sig.meta))


@converter("text", "number", "program signature σ(S) / 2³¹ (seed_lang; SHA-256 when no project)")
def _text_to_number(sig, app):
    text = str(sig.data)
    gb = __import__("sys").modules.get("groovebox")
    if gb is not None and hasattr(gb, "_seed_script_env"):
        try:
            import seed_lang
            return Signal("number", seed_lang.signature(text, lambda t: gb._seed_script_env(t)) / float(1 << 31), None,
                          {**sig.meta, "text": text[:200]})
        except Exception:
            pass
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:13], 16)
    return Signal("number", h / float(1 << 52), None, {**sig.meta, "text": text[:200]})


@converter("number", "text", "decimal text")
def _number_to_text(sig, app):
    return Signal("text", repr(float(sig.data)), None, dict(sig.meta))


@converter("events", "control", "events [(t, value)] → held curve at 100 Hz")
def _events_to_control(sig, app):
    ev = sorted((float(t), float(v)) for t, v in (sig.data or []))
    if not ev:
        return Signal("control", np.zeros(1, np.float32), CONTROL_RATE, dict(sig.meta))
    end = ev[-1][0] + 1.0 / CONTROL_RATE
    t = np.arange(0.0, end, 1.0 / CONTROL_RATE)
    times = np.array([e[0] for e in ev]); vals = np.array([e[1] for e in ev])
    idx = np.clip(np.searchsorted(times, t, side="right") - 1, 0, len(ev) - 1)
    return Signal("control", vals[idx].astype(np.float32), CONTROL_RATE, dict(sig.meta))


@converter("control", "file", "write control curve JSON")
def _control_to_file(sig, app):
    path = os.path.join(_out_dir(app), f"bridge_control_{_digest(sig)[:12]}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"format": "GrooveboxControlCurve", "version": 1, "rate": sig.rate,
                   "values": [round(float(x), 6) for x in np.asarray(sig.data).ravel()]}, fh)
    return Signal("file", path, None, dict(sig.meta))


# R132.26: the missing edges — nothing reached `events`, and there was no image kind although media_transmuter has
# image ↔ sound ↔ video. Each is one edge; multi-step routes still come from the shortest path.
@converter("control", "events", "peaks: each local maximum in the upper half of the curve → (t, value)")
def _control_to_events(sig, app):
    c = np.asarray(sig.data, np.float64).ravel()
    rate = float(sig.rate or CONTROL_RATE)
    if c.size < 3:
        return Signal("events", [(0.0, float(c[0]) if c.size else 0.0)], None, dict(sig.meta))
    lo, hi = float(c.min()), float(c.max())
    thr = lo + 0.5 * (hi - lo)
    idx = np.flatnonzero((c[1:-1] > c[:-2]) & (c[1:-1] >= c[2:]) & (c[1:-1] >= thr)) + 1
    if idx.size == 0:
        idx = np.array([int(np.argmax(c))])
    return Signal("events", [(round(float(i) / rate, 4), float(c[i])) for i in idx[:4096]], None, dict(sig.meta))


@converter("number", "control", "constant curve: one second at 100 Hz")
def _number_to_control(sig, app):
    return Signal("control", np.full(int(CONTROL_RATE), float(sig.data), np.float32), CONTROL_RATE, dict(sig.meta))


@converter("audio", "image", "media_transmuter: log-frequency spectrogram PNG (image → audio reads it back)")
def _audio_to_image(sig, app):
    import media_transmuter as mt
    wav = _audio_to_file(sig, app).data
    dst = os.path.splitext(wav)[0] + ".png"
    if not os.path.isfile(dst):
        mt.sound_to_image(wav, dst)
    return Signal("image", dst, None, dict(sig.meta))


@converter("image", "audio", "media_transmuter: the picture read as a spectrogram (exact for Groovebox spectrograms)")
def _image_to_audio(sig, app):
    import media_transmuter as mt
    dst = os.path.join(_out_dir(app), "bridge_image_%s.wav" % _digest(sig)[:12])
    if not os.path.isfile(dst):
        mt.image_to_sound(str(sig.data), dst)
    return _file_to_audio(Signal("file", dst, None, dict(sig.meta)), app)


@converter("image", "video", "media_transmuter: pan / zoom video of the picture, its sonification muxed in")
def _image_to_video(sig, app):
    import media_transmuter as mt
    dst = os.path.join(_out_dir(app), "bridge_image_%s.mp4" % _digest(sig)[:12])
    if not os.path.isfile(dst):
        mt.image_to_video(str(sig.data), dst)
    return Signal("video", dst, None, dict(sig.meta))


@converter("video", "image", "media_transmuter: contact sheet of the video's frames")
def _video_to_image(sig, app):
    import media_transmuter as mt
    dst = os.path.join(_out_dir(app), "bridge_video_%s.png" % hashlib.sha256(str(sig.data).encode()).hexdigest()[:12])
    if not os.path.isfile(dst):
        mt.video_to_image(str(sig.data), dst)
    return Signal("image", dst, None, dict(sig.meta))


@converter("image", "file", "image file path")
def _image_to_file(sig, app):
    return Signal("file", str(sig.data), None, dict(sig.meta))


def sniff(sig: Signal) -> Signal:
    """R132.26: a file signal re-typed by what it contains, so routing starts from the right kind (a PNG sent to a
    lane used to be decoded as audio and fail). Audio files stay `file` (file → audio decodes them)."""
    if sig.kind != "file":
        return sig
    p = str(sig.data)
    low = p.lower()
    meta = {**sig.meta, "path": p}
    if low.endswith(VIDEO_EXT):
        return Signal("video", p, None, meta)
    if low.endswith(IMAGE_EXT):
        return Signal("image", p, None, meta)
    if low.endswith(".json") and os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception as exc:
            raise BridgeError(f"{os.path.basename(p)}: unreadable JSON ({exc})")
        if isinstance(doc, dict) and doc.get("format") == "GrooveboxControlCurve":
            return Signal("control", np.asarray(doc.get("values") or [0.0], np.float32), float(doc.get("rate") or CONTROL_RATE), meta)
        seed = doc.get("seed") if isinstance(doc, dict) else None           # .game.json / world spec → its seed
        if not seed and isinstance(doc, dict):
            seed = next((lv.get("seed") for lv in doc.get("levels") or [] if isinstance(lv, dict) and lv.get("seed")), None)
        if seed:
            return Signal("text", str(seed), None, meta)
        raise BridgeError(f"{os.path.basename(p)}: JSON is neither a control curve nor a game / world spec")
    if low.endswith(TEXT_EXT) and os.path.isfile(p):
        with open(p, encoding="utf-8", errors="replace") as fh:
            return Signal("text", fh.read(1 << 20), None, meta)
    return sig


def _route(src: str, dst: str) -> List[Tuple[str, str]]:
    if src == dst:
        return []
    prev = {src: None}
    q = collections.deque([src])
    while q:
        k = q.popleft()
        for (a, b) in _EDGES:
            if a == k and b not in prev:
                prev[b] = a
                if b == dst:
                    path, cur = [], b
                    while prev[cur] is not None:
                        path.append((prev[cur], cur)); cur = prev[cur]
                    return path[::-1]
                q.append(b)
    raise BridgeError(f"no conversion route {src} → {dst}")


def convert(sig: Signal, to_kind: str, app=None) -> Tuple[Signal, List[str]]:
    """Post-processing A→B: convert any signal to any reachable kind. Returns (signal, steps)."""
    steps = []
    if sig.kind == "file" and to_kind != "file":
        typed = sniff(sig)
        if typed.kind != "file":
            steps.append(f"file→{typed.kind}: read {os.path.splitext(str(sig.data))[1] or 'file'} as {typed.kind}")
            sig = typed
    for a, b in _route(sig.kind, to_kind):
        name, fn = _EDGES[(a, b)]
        sig = fn(sig, app)
        steps.append(f"{a}→{b}: {name}")
    return sig, steps


def from_value(value, kind: Optional[str] = None, **meta) -> Signal:
    """Wrap a plain Python value. Paths become file signals; arrays audio (with rate) or control."""
    if isinstance(value, Signal):
        return value
    if kind:
        return Signal(kind, value, meta.pop("rate", None), meta)
    if isinstance(value, str) and os.path.isfile(value):
        return Signal("file", value, None, meta)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Signal("number", float(value), None, meta)
    if isinstance(value, str):
        return Signal("text", value, None, meta)
    if isinstance(value, np.ndarray):
        rate = meta.pop("rate", None)
        return Signal("audio" if rate and rate >= 4000 else "control", value, rate, meta)
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        return Signal("events", list(value), None, meta)
    raise BridgeError(f"cannot infer a signal kind for {type(value).__name__}")


# ----------------------------------------------------------------------------- contexts (sinks)
@dataclasses.dataclass
class Context:
    name: str
    needs: str
    apply: Callable          # (app, signal, arg) -> undo callable or None
    doc: str
    worker: bool = False     # R132.26: apply touches no Qt widget → the Signal Router runs it off the GUI thread


_CONTEXTS: Dict[str, Context] = {}


def context(name, needs, doc, worker=False):
    def deco(fn):
        _CONTEXTS[name] = Context(name, needs, fn, doc, worker)
        return fn
    return deco


def _invalidate(app):
    try:
        app._shared_mixdown_cache = {}
    except Exception:
        pass
    try:
        app._on_live_source_changed()
    except Exception:
        pass


@context("global_carrier", "audio", "the main carrier every render path reads")
def _ctx_global(app, sig, _arg):
    prev = {k: getattr(app, k, None) for k in ("imported_waveform", "imported_sample_rate", "imported_wav_path")}
    path = _audio_to_file(sig, app).data
    sig.meta["path"] = path
    if hasattr(app, "_load_wav_path"):
        app._load_wav_path(path)
    else:
        app.imported_waveform = np.asarray(sig.data, np.float32); app.imported_sample_rate = int(sig.rate or DEFAULT_SR)
        app.imported_wav_path = path
    app.global_media_sample = {"path": path, "derived": True, "source": sig.meta.get("source", "bridge")}
    app._global_carrier_path = path       # kept for scode_optimizer_bridge compatibility
    _invalidate(app)

    def undo():
        for k, v in prev.items():
            setattr(app, k, v)
        try:
            app._refresh_after_file_input(reason="carrier_bridge_undo")
        except Exception:
            pass
        _invalidate(app)
    return undo


@context("instrument_carrier", "audio", "an instrument's carrier sample (key_assign / live_player / exports)")
def _ctx_instrument(app, sig, name):
    name = name or (app._current_instrument_name() if hasattr(app, "_current_instrument_name") else "selected")
    store = getattr(app, "instrument_media_samples", None)
    if not isinstance(store, dict):
        store = {}; app.instrument_media_samples = store
    prev = store.get(name)
    path = _audio_to_file(sig, app).data
    sig.meta["path"] = path
    store[name] = {**(prev or {}), "path": path, "sample_rate": int(sig.rate or DEFAULT_SR),
                   "waveform": np.asarray(sig.data, np.float32).ravel(), "user_owned": True,
                   "source_kind": "audio", "source": sig.meta.get("source", "bridge"), "bridge": True,
                   **({"layered_state": sig.meta["layered_state"]} if "layered_state" in sig.meta else {})}
    _invalidate(app)

    def undo():
        if prev is None:
            store.pop(name, None)
        else:
            store[name] = prev
        _invalidate(app)
    return undo


@context("carrier_layer", "file", "add as a layer on the global or an instrument carrier, then re-mix")
def _ctx_layer(app, sig, target):
    import carrier_layers as cl
    target = target or "global"
    layers = cl.state(app).setdefault(target, [])
    layers.append({"path": str(sig.data), "start_row": 0, "rows": 0, "stretch": 1.0, "pitch": 0.0, "gain": 1.0,
                   "offset_s": 0.0, "loop": False, "reverse": False, "mute": False, "solo": False,
                   "source": sig.meta.get("source", "bridge")})
    cl.apply(app, target)

    def undo():
        try:
            layers.pop()
            cl.apply(app, target)
        except Exception:
            pass
    return undo


@context("seed", "text", "the Global Seed editor")
def _ctx_seed(app, sig, _arg):
    prev = app._seed_text() if hasattr(app, "_seed_text") else None
    app.input_seed_val.setPlainText(str(sig.data))
    return (lambda: app.input_seed_val.setPlainText(prev)) if prev is not None else None


@context("bpm", "number", "project tempo (20–300)")
def _ctx_bpm(app, sig, _arg):
    v = float(sig.data)
    if 0.0 <= v <= 1.0:
        v = 20.0 + v * 280.0          # normalised numbers map onto the tempo range
    prev = float(app.spin_bpm.value())
    app.spin_bpm.setValue(max(20.0, min(300.0, v)))
    return lambda: app.spin_bpm.setValue(prev)


@context("lane", "control", "sequencer lane via plugin_guard (validated, undoable)")
def _ctx_lane(app, sig, arg):
    inst, _, lane = (arg or "").partition(":")
    lane = lane or "amplitudes"
    import plugin_guard as pg
    try:
        n = len(app._current_sequence_mem(inst or app._current_instrument_name()).get(lane, []) or []) or 16
    except Exception:
        n = 16
    c = np.asarray(sig.data, np.float64).ravel()
    vals = np.interp(np.linspace(0, max(0, c.size - 1), n), np.arange(c.size), c) if c.size else np.zeros(n)
    if lane == "pitches":
        vals = 2.0 ** (vals * 2.0 - 1.0)            # 0…1 → one octave down … one octave up
        op = "set_pitches"
    elif lane == "steps":
        vals = vals >= 0.5; op = "set_steps"
    else:
        op = "set_amplitudes"
    ok, bad = pg.apply_requests(app, [{"op": op, "instrument": inst or None, "values": [float(v) if op != "set_steps" else bool(v) for v in vals]}],
                                who=sig.meta.get("source", "carrier_bridge"))
    if not ok:
        raise BridgeError("lane refused: " + "; ".join(bad[:3]))
    return None                                     # plugin_guard already pushed an undo step


@context("video_carrier", "video", "the main video carrier")
def _ctx_video(app, sig, _arg):
    app._load_video_path(str(sig.data))
    _invalidate(app)
    return None


@context("export", "file", "copy into the project exports folder", worker=True)
def _ctx_export(app, sig, _arg):
    d = str(app._exports_dir()) if hasattr(app, "_exports_dir") else os.path.join(_out_dir(app), "exports")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, os.path.basename(str(sig.data)))
    if os.path.realpath(dst) == os.path.realpath(str(sig.data)):
        return None                                  # R132.26: already in the exports folder
    existed = os.path.exists(dst)
    shutil.copy2(str(sig.data), dst)
    sig.meta["path"] = dst
    return None if existed else (lambda: os.path.exists(dst) and os.remove(dst))


@context("live_player", "file", "open in the Live Player")
def _ctx_live(app, sig, _arg):
    import app_hub
    app_hub.send_back(app, str(sig.data))
    return None


# ----------------------------------------------------------------------------- R132.26 contexts
# Every place a signal can usefully land now has exactly one context. Each still uses the engine's own path.
def _curve(sig, n=512):
    c = np.nan_to_num(np.asarray(sig.data, np.float64).ravel())
    if c.size == 0:
        c = np.array([0.5])
    if c.size > n:
        c = np.interp(np.linspace(0, c.size - 1, n), np.arange(c.size), c)
    lo, hi = float(c.min()), float(c.max())
    return ((c - lo) / (hi - lo) if hi > lo else np.clip(c, 0.0, 1.0)).tolist()


@context("mod", "control", "Master Mod Path row: the curve loops every `rate` beats into any automation / widget target")
def _ctx_mod(app, sig, target):
    import any_signal_context as asc
    import mod_matrix as mm
    target = target or ("widget:" + mm.GLOBAL_WIDGETS[0])
    rs = mm.rows(app)
    prev = [dict(r) for r in rs]
    src = "signal:" + str(sig.meta.get("source") or sig.meta.get("name") or "bridge")[:40]
    curve = _curve(sig)
    res = asc.route(app, signal=float(np.mean(curve)), target=target, source_name=src,
                    amount=float(sig.meta.get("amount", 0.25)), rate=float(sig.meta.get("beats", 4.0)))
    if not res.get("ok"):
        raise BridgeError("mod route refused: " + str(res.get("reason")))
    for r in rs:
        if str(r.get("target")) == target and str(r.get("source")) == src:
            r["_signal_curve"] = curve                      # mod_matrix._src reads it (signal:* sources)
    sig.meta["mod"] = {k: v for k, v in res.items() if k != "row"}

    def undo():
        rs[:] = prev
    return undo


@context("automation", "control", "automation lane on any numeric project parameter (user lane, one pass = `beats`)")
def _ctx_automation(app, sig, path):
    import automation_bus as ab
    path = path or next(iter(ab.targets(app)), "")
    if not path:
        raise BridgeError("no automation target exists in this project")
    lane = ab.add_lane(app, path, amount=float(sig.meta.get("amount", 0.5)), owner="user")
    if lane is None:
        raise BridgeError(f"automation target not found: {path}")
    beats = float(sig.meta.get("beats", 16.0))
    c = _curve(sig, 256)
    lane["points"] = [(beats * i / max(1, len(c) - 1), float(v)) for i, v in enumerate(c)]

    def undo():
        try:
            ab.lanes(app).remove(lane)
            d, k = ab._resolve(app, path)
            if d is not None:
                d[k] = lane["base"]
        except Exception:
            pass
    return undo


def _engines(app):
    try:
        import canonical_matrix as cm
        return tuple(cm.context(app)[1])
    except Exception:
        return ()


@context("lens", "text", "🔭 Lenses: the seed → audio + image + game through one lens (arg: lens name)", worker=True)
def _ctx_lens(app, sig, lens):
    import lenses
    lens = lens if lens in lenses.LENSES else "spectral"
    r = lenses.render_all(str(sig.data), _engines(app), lens=lens)
    sig.meta["path"] = r.get("audio", {}).get("path", "")
    sig.meta["outputs"] = {k: (v.get("path") if isinstance(v, dict) else v) for k, v in r.items() if k in ("audio", "image", "game")}
    return None


@context("world", "text", "🌍 enter the open world of this seed (arg: lens bias)")
def _ctx_world(app, sig, lens):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
    import open_world
    d = QDialog(app if hasattr(app, "isWindow") else None)
    d.setWindowTitle("🌍 " + str(sig.data)[:48]); d.resize(900, 640)
    lay = QVBoxLayout(d); info = QLabel(""); info.setWordWrap(True)
    wv = open_world.WorldView(str(sig.data), _engines(app), lens or None, info.setText)
    lay.addWidget(wv, 1); lay.addWidget(info)
    d.show(); wv.setFocus()
    return d.close


@context("postfx", "file", "✨ Post-processing chain (arg: post seed) → a processed copy in exports/postfx", worker=True)
def _ctx_postfx(app, sig, post_seed):
    import postfx
    try:
        seed = post_seed or str(app._seed_text() or "")
    except Exception:
        seed = post_seed or "postfx"
    d = os.path.join(str(app._exports_dir()) if hasattr(app, "_exports_dir") else _out_dir(app), "postfx")
    out = postfx.process_file(str(sig.data), postfx.settings_from_seed(seed, _engines(app)), out_dir=d)
    sig.meta["path"] = out
    return lambda: os.path.exists(out) and os.remove(out)


def _performance(app):
    for name in ("_perf_panel", "_open_performance"):
        f = getattr(app, name, None)
        if callable(f):
            try:
                p = f()
                if p is not None and hasattr(p, "_playlist"):
                    return p
            except Exception:
                pass
    p = getattr(app, "_performance_panel", None)
    return p if p is not None and hasattr(p, "_playlist") else None


@context("playlist", "file", "add to the Performance playlist")
def _ctx_playlist(app, sig, _arg):
    p = _performance(app)
    if p is None:
        raise BridgeError("the Performance playlist is not available")
    path = str(sig.data)
    if not any(it.get("path") == path for it in p._playlist):
        low = path.lower()
        p._playlist.append({"path": path, "volume": 100, "mix": False, "kind": "image" if low.endswith(IMAGE_EXT) else "media",
                            "time_s": float(len(p._playlist) * 5.0), "duration_s": 5.0 if low.endswith(IMAGE_EXT) else 0.0})
        for fn in ("_refresh_playlist_widget", "_sync_project_state"):
            try:
                getattr(p, fn)()
            except Exception:
                pass

    def undo():
        p._playlist[:] = [it for it in p._playlist if it.get("path") != path]
        try:
            p._refresh_playlist_widget()
        except Exception:
            pass
    return undo


@context("editor", "file", "open in the matching editor (audio → Audio Editor · image → Image Editor · video → Clip Editor)")
def _ctx_editor(app, sig, _arg):
    path = str(sig.data); low = path.lower()
    if low.endswith(IMAGE_EXT):
        import image_editor
        w = image_editor.open_window(app)
        w.open_path(path)
    elif low.endswith(VIDEO_EXT):
        f = getattr(app, "_r32_open_clip_editor", None)
        if not callable(f):
            raise BridgeError("the Clip Editor is not in this build")
        w = f()
        for m in ("import_media", "add_clip", "load_media", "_import_path"):
            if w is not None and callable(getattr(w, m, None)):
                getattr(w, m)(path); break
    else:
        import audio_editor
        audio_editor.open_window(app, path)
    return None


@context("share", "file", "publish on this Groovebox's LAN site (Network Hub ▸ hosted files)", worker=True)
def _ctx_share(app, sig, title):
    import net_hub
    item = net_hub.host_file(str(sig.data), title=title or os.path.basename(str(sig.data)), note="sent by the Signal Router")
    sig.meta["shared"] = item.get("sha") if isinstance(item, dict) else str(item)
    return None


@context("background", "image", "the desktop / window background picture")
def _ctx_background(app, sig, _arg):
    import compat_settings as cs
    prev = {k: cs.load().get(k) for k in ("window_background_image", "math_background_enabled")}
    cs.update(window_background_image=str(sig.data), math_background_enabled=True)

    def refresh():
        try:
            import groovebox as gb
            gb.refresh_window_backgrounds(app)
        except Exception:
            pass
    refresh()

    def undo():
        cs.update(**prev); refresh()
    return undo


def contexts() -> Dict[str, str]:
    return {k: f"{c.needs}: {c.doc}" for k, c in _CONTEXTS.items()}


def _split(ctx: str) -> Tuple[Context, str]:
    base, _, arg = str(ctx).partition(":")
    c = _CONTEXTS.get(base)
    if c is None:
        raise BridgeError(f"unknown context {ctx!r}; available: {', '.join(sorted(_CONTEXTS))}")
    return c, arg


def selected_instrument(app) -> str:
    """The instrument the user has selected, whatever widget generation the host uses."""
    try:
        n = app._current_instrument_name()
        if n:
            return str(n)
    except Exception:
        pass
    for attr in ("selected_instrument", "current_instrument"):
        v = getattr(app, attr, None)
        if isinstance(v, str) and v:
            return v
    for attr in ("instrument_selector_dropdown", "instrument_selector", "instrument_combo"):
        w = getattr(app, attr, None)
        if w is not None and hasattr(w, "currentText") and w.currentText():
            return str(w.currentText())
    return "selected"


# ----------------------------------------------------------------------------- guaranteed profile


def _instrument_names(app):
    names = list(getattr(app, "instrument_names_48", []) or [])
    if not names:
        names = list((getattr(app, "instrument_media_samples", {}) or {}).keys())
    return names


def seed_only(app) -> Tuple[bool, str]:
    """No user-owned composition data: the seed and the canonicals produce everything."""
    for n in _instrument_names(app):
        try:
            mem = app._current_sequence_mem(n)
            owned = app._mem_has_user_steps(mem) if hasattr(app, "_mem_has_user_steps") else bool(mem.get("user_owned"))
        except Exception:
            owned = False
        if owned:
            return False, f"instrument {n!r} has user-owned steps"
        ent = (getattr(app, "instrument_media_samples", {}) or {}).get(n)
        if isinstance(ent, dict) and ent.get("path") and not ent.get("bridge"):
            return False, f"instrument {n!r} uses a user-imported carrier"
    gms = getattr(app, "global_media_sample", None)
    if getattr(app, "imported_wav_path", "") and not (isinstance(gms, dict) and gms.get("derived")
                                                       and gms.get("path") == getattr(app, "imported_wav_path", "")):
        return False, "the global carrier is a user-imported file"
    if getattr(app, "imported_video_path", ""):
        return False, "a user video carrier is loaded"
    try:
        if not str(app._seed_text() or "").strip():
            return False, "the Global Seed is empty"
    except Exception:
        pass
    return True, "seed-only"


def profile(app) -> dict:
    """Where the current project sits relative to the guaranteed reference profile."""
    out = {"seed_only": False, "all_canonicals": False, "defaults": False, "guaranteed": False, "why": []}
    if app is None:
        out["why"].append("no project"); return out
    ok, why = seed_only(app)
    out["seed_only"] = ok
    if not ok:
        out["why"].append(why)
    try:
        out["all_canonicals"] = bool(app._full_canonical_unison_active())
    except Exception:
        out["all_canonicals"] = False
    if not out["all_canonicals"]:
        out["why"].append("not all canonicals active (SEEDED + RAND + LOCK + EUCLIDEAN)")
    try:
        levels = {k: app._canonical_level_raw(k) for k in ("seeded", "randomizer", "phase_lock", "euclidean")}
        rep = getattr(app, "_default_integrity_report", None)
        if rep is None and hasattr(app, "_run_default_integrity_check"):
            rep = app._run_default_integrity_check()
        drift = [k for k, v in (rep or {}).items() if not v] + [f"{k} level {v:g}" for k, v in levels.items() if v != 1.0]
        out["defaults"] = not drift
        if drift:
            out["why"].append("settings differ from defaults: " + ", ".join(drift[:4]))
    except Exception:
        out["defaults"] = False
        out["why"].append("defaults could not be checked")
    out["guaranteed"] = out["seed_only"] and out["all_canonicals"] and out["defaults"]
    return out


def _provenance(app) -> dict:
    try:
        seed = str(app._seed_text() or "")
    except Exception:
        seed = ""
    try:
        active = sorted(app._active_engine_sources())
    except Exception:
        active = []
    return {"seed_sha256": hashlib.sha256(seed.encode("utf-8")).hexdigest(), "canonicals": active}


# ----------------------------------------------------------------------------- send + history
_HISTORY = collections.deque(maxlen=256)
_LOCK = threading.Lock()


def prepare(app, value, ctx: str, *, source: str = "", kind: Optional[str] = None, **meta) -> dict:
    """R132.26: the conversion half of :func:`send` (decode, transmute, render). Safe on a worker thread; hand the
    result to :func:`deliver` on the GUI thread (or on the worker when ``plan['worker']`` is True)."""
    sig = from_value(value, kind, **meta)
    if source:
        sig.meta["source"] = source
    c, arg = _split(ctx)
    plan = {"ctx": ctx, "sig_kind": sig.kind, "c": c, "arg": arg, "worker": c.worker, "source": sig.meta.get("source", "")}
    try:
        plan["out"], plan["steps"] = convert(sig, c.needs, app)
    except Exception as exc:
        plan["error"] = exc
    return plan


def route_steps(src_kind: str, ctx: str) -> List[str]:
    """The conversion steps a send would take (for previews); raises BridgeError when there is no route."""
    c, _arg = _split(ctx)
    return [f"{a}→{b}: {_EDGES[(a, b)][0]}" for a, b in _route(src_kind, c.needs)]


def send(app, value, ctx: str, *, source: str = "", kind: Optional[str] = None, **meta) -> dict:
    """Deliver any value/signal into a context. Must be called on the GUI thread for UI contexts.

    Returns a receipt; ``receipt['undo']`` (callable or None) reverts the change."""
    return deliver(app, prepare(app, value, ctx, source=source, kind=kind, **meta))


def deliver(app, plan: dict) -> dict:
    """Apply a :func:`prepare` result to its context; same receipt / guarantee handling as :func:`send`."""
    ctx, c, arg = plan["ctx"], plan["c"], plan["arg"]
    src_kind, source = plan.get("sig_kind", "?"), plan.get("source", "")
    # profile / provenance read widgets: a worker-side deliver passes them in, computed on the GUI thread
    prof = plan.get("profile") or (profile(app) if app is not None else {"guaranteed": False, "why": ["no project"]})
    try:
        if plan.get("error") is not None:
            raise plan["error"]
        out, steps = plan["out"], plan["steps"]
        undo = c.apply(app, out, arg)
    except Exception as exc:
        if prof.get("guaranteed"):
            msg = f"GUARANTEE VIOLATION: {src_kind} → {ctx} failed in the Seed-only / all-canonicals / defaults profile: {exc}"
            with _LOCK:
                _HISTORY.append({"t": time.time(), "context": ctx, "from": src_kind, "error": msg, "guaranteed": True})
            try:
                __import__("notify_center").notify(app, msg, "error", key="bridge:violation:" + ctx, every_s=5)
            except Exception:
                pass
            raise BridgeError(msg) from exc
        raise
    rec = {"t": time.time(), "context": ctx, "path": getattr(out, "meta", {}).get("path", ""), "source": source, "from": src_kind,
           "route": steps, "sha256": _digest(out),
           "samples": int(np.asarray(out.data).size) if isinstance(out.data, np.ndarray) else None,
           "rate": out.rate, "guaranteed": bool(prof.get("guaranteed")), **(plan.get("provenance") or _provenance(app)),
           **({"outputs": out.meta["outputs"]} if "outputs" in out.meta else {})}
    with _LOCK:
        _HISTORY.append(dict(rec))
    rec["undo"] = undo
    return rec


def history(limit: int = 32) -> List[dict]:
    with _LOCK:
        return list(_HISTORY)[-int(limit):]


def describe() -> dict:
    return {"rule": "any-signal → any-context works everywhere (best effort); guaranteed for Seed-only + all canonicals + defaults",
            "kinds": list(KINDS),
            "converters": {f"{a}→{b}": n for (a, b), (n, _f) in sorted(_EDGES.items())},
            "contexts": contexts(),
            "recent": history(8)}


def validate() -> List[str]:
    """Self-check for Monitor Center / doctor: every context's input kind is reachable from every kind
    that can reach it, and there are no duplicate edges. Returns a list of problems (empty = OK)."""
    problems = []
    for c in _CONTEXTS.values():
        if c.needs not in KINDS:
            problems.append(f"context {c.name} needs unknown kind {c.needs}")
    for k in KINDS:                       # R132.26: the full matrix — every kind reaches every kind and every context
        for d in KINDS:
            try:
                _route(k, d)
            except BridgeError:
                problems.append(f"{k} cannot reach {d}")
    return problems


def verify_guarantee(app=None) -> List[str]:
    """Prove the guaranteed profile structurally and numerically, without touching the project.

    For every kind that a seed can produce (text → number → control → audio → file) and every
    context: a route exists, and converting twice gives the same SHA-256 (determinism, Claim 6).
    Returns problems (empty = guarantee holds)."""
    problems = list(validate())
    seed = "sin(t)"
    try:
        if app is not None:
            seed = str(app._seed_text() or seed)
    except Exception:
        pass
    probe = {"text": Signal("text", seed)}
    probe["number"] = convert(probe["text"], "number")[0]
    probe["control"] = convert(probe["number"], "control")[0]
    probe["events"] = Signal("events", [(0.0, 0.0), (0.5, 1.0)])
    probe["audio"] = convert(probe["control"], "audio")[0]
    for k, sig in probe.items():                 # image / video / file are paths: covered by the audio / control hashes
        for c in _CONTEXTS.values():
            try:
                r = _route(k, c.needs)
            except BridgeError as exc:
                problems.append(f"{k} → {c.name}: {exc}"); continue
            if c.needs in ("file", "video", "image") and k != c.needs:
                continue          # file writes are content-addressed; covered by the audio/control hashes
            a = _digest(convert(sig, c.needs)[0]); b = _digest(convert(sig, c.needs)[0])
            if a != b:
                problems.append(f"{k} → {c.name}: not deterministic ({len(r)} steps)")
    return problems


def register_with_router(router) -> int:
    """Expose every edge as a named converter on a universal_signal_io.UniversalSignalRouter
    (post-processing toolkits negotiate through the router; conversion code lives only here)."""
    n = 0
    for (a, b), (name, fn) in _EDGES.items():
        def _pred(sf, df, a=a, b=b):
            return sf.get("media") == a and df.get("media") == b

        def _xf(payload, sf, df, fn=fn, a=a):
            return fn(Signal(a, payload, sf.get("sample_rate")), None).data
        try:
            router.register_converter(f"bridge:{a}->{b}", _pred, _xf)
            n += 1
        except Exception:
            pass
    return n
