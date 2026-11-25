"""carrier_generator_path.py — R138

Direct carrier + generator path for Groovebox scripts, plugins, sCode, and the
Signal Router. One stable surface so external code does not dig through
``app.instrument_media_samples`` / ``plugin_library`` / ``sample_generator``.

Routes
------
  global                  project-wide audio (and optional video) carrier
  instrument:<name>       per-instrument carrier sample
  layer:global            carrier_layers target "global"
  layer:<name>            carrier_layers target for an instrument
  plugin:<id>             plugin bound as a carrier source
  generator:<kind>        sample_generator kind (noise_white, structured, …)

Binding vector (on every route)
-------------------------------
  mode          none | file | waveform | plugin | generator | layers
  source        path, plugin id, generator kind, or ""
  amount        0..1 mix into the voice / master
  polarity      -1 | 1
  curve         linear | meum | phi | exp | log
  vector        length-N floats in [0,1) — route-specific control vector
                (pitch bias, morph, stretch, wet, …); same algebra as lenses
  rate_beats    LFO / refresh rate in beats (0 = static)
  enabled       bool
  meta          free dict (script/plugin annotations)

Scripts::

    import carrier_generator_path as cgp
    cgp.set_global_carrier(app, path="/samples/pad.wav", amount=0.8)
    cgp.bind_generator(app, "instrument:Lead", kind="structured",
                       vector=[0.2, 0.5, 0.9], amount=0.4)
    cgp.set_binding_vector(app, "global", vector=cgp.seed_vector("MEUM", n=16))
"""
from __future__ import annotations

import copy
import hashlib
import os
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import numpy as np

MEUM = 1.1975807343385265
PHI = (1.0 + 5.0 ** 0.5) / 2.0
VECTOR_N = 16

BindingVector = Dict[str, Any]
RouteKey = str

_GENERATORS: Dict[str, Callable[..., np.ndarray]] = {}


# ── binding vector schema ────────────────────────────────────────────────────

def default_binding(
    mode: str = "none",
    source: str = "",
    *,
    amount: float = 1.0,
    polarity: float = 1.0,
    curve: str = "linear",
    vector: Optional[Sequence[float]] = None,
    rate_beats: float = 0.0,
    enabled: bool = True,
    meta: Optional[dict] = None,
) -> BindingVector:
    return {
        "mode": str(mode or "none"),
        "source": str(source or ""),
        "amount": float(np.clip(amount, 0.0, 1.0)),
        "polarity": -1.0 if float(polarity) < 0 else 1.0,
        "curve": str(curve or "linear"),
        "vector": _norm_vector(vector),
        "rate_beats": float(max(0.0, rate_beats)),
        "enabled": bool(enabled),
        "meta": dict(meta or {}),
    }


def _norm_vector(vector: Optional[Sequence[float]], n: int = VECTOR_N) -> List[float]:
    if vector is None:
        return [0.5] * n
    v = [float(x) for x in list(vector)[:n]]
    while len(v) < n:
        v.append(0.5)
    return [float(np.clip(x, 0.0, 1.0)) for x in v]


def seed_vector(seed: Any, n: int = VECTOR_N, salt: str = "cgp") -> List[float]:
    """Deterministic binding vector from any seed (script-friendly)."""
    out = []
    for i in range(n):
        h = hashlib.blake2b(f"{seed}|{salt}|{i}".encode(), digest_size=8).digest()
        out.append(int.from_bytes(h, "big") / float(1 << 64))
    return out


def apply_curve(u: float, curve: str = "linear") -> float:
    u = float(np.clip(u, 0.0, 1.0))
    c = (curve or "linear").lower()
    if c == "meum":
        return float((u * MEUM) % 1.0)
    if c == "phi":
        return float((u * (PHI - 1.0)) % 1.0) if False else float((u * (1.0 / PHI)) % 1.0)
    if c == "exp":
        return float((np.exp(u * 2.0) - 1.0) / (np.exp(2.0) - 1.0))
    if c == "log":
        return float(np.log1p(u * (np.e - 1.0)))
    return u


# ── route registry on the app ────────────────────────────────────────────────

def _state(app) -> Dict[str, BindingVector]:
    st = getattr(app, "r138_carrier_generator_routes", None)
    if not isinstance(st, dict):
        st = app.r138_carrier_generator_routes = {}
    return st


def list_routes(app) -> List[str]:
    keys = set(_state(app).keys())
    keys.add("global")
    try:
        for name in getattr(app, "instrument_names_48", []) or []:
            keys.add("instrument:" + str(name))
    except Exception:
        pass
    try:
        import carrier_layers as cl
        for t in cl.state(app).keys():
            keys.add("layer:" + str(t))
    except Exception:
        pass
    try:
        import plugin_library as pl
        for inst, pid in (pl._bindings(app).get("carrier") or {}).items():
            keys.add("instrument:" + str(inst))
            keys.add("plugin:" + str(pid))
    except Exception:
        pass
    return sorted(keys)


def get_binding(app, route: RouteKey) -> BindingVector:
    st = _state(app)
    if route in st and isinstance(st[route], dict):
        return copy.deepcopy(st[route])
    # fall back to legacy carrier_binding_* / per-instrument fields
    if route == "global":
        return default_binding(
            mode=str(getattr(app, "carrier_binding_mode", "") or "none") or "none",
            source=str(getattr(app, "carrier_binding_source", "") or ""),
        )
    if route.startswith("instrument:"):
        name = route.split(":", 1)[1]
        rec = (getattr(app, "instrument_media_samples", {}) or {}).get(name) or {}
        return default_binding(
            mode=str(rec.get("binding_mode") or ("file" if rec.get("path") else "none")),
            source=str(rec.get("binding_source") or rec.get("path") or rec.get("plugin") or ""),
            meta={"path": rec.get("path"), "plugin": rec.get("plugin")},
        )
    return default_binding()


def set_binding_vector(
    app,
    route: RouteKey,
    *,
    vector: Optional[Sequence[float]] = None,
    amount: Optional[float] = None,
    polarity: Optional[float] = None,
    curve: Optional[str] = None,
    rate_beats: Optional[float] = None,
    enabled: Optional[bool] = None,
    mode: Optional[str] = None,
    source: Optional[str] = None,
    meta: Optional[dict] = None,
) -> BindingVector:
    """Update binding-vector fields on any route (creates the route if missing)."""
    cur = get_binding(app, route)
    if mode is not None:
        cur["mode"] = str(mode)
    if source is not None:
        cur["source"] = str(source)
    if amount is not None:
        cur["amount"] = float(np.clip(amount, 0.0, 1.0))
    if polarity is not None:
        cur["polarity"] = -1.0 if float(polarity) < 0 else 1.0
    if curve is not None:
        cur["curve"] = str(curve)
    if vector is not None:
        cur["vector"] = _norm_vector(vector)
    if rate_beats is not None:
        cur["rate_beats"] = float(max(0.0, rate_beats))
    if enabled is not None:
        cur["enabled"] = bool(enabled)
    if meta is not None:
        cur["meta"] = {**cur.get("meta", {}), **dict(meta)}
    _state(app)[route] = cur
    _mirror_legacy(app, route, cur)
    return copy.deepcopy(cur)


def _mirror_legacy(app, route: RouteKey, binding: BindingVector) -> None:
    """Keep carrier_binding_* and instrument_media_samples in sync for older paths."""
    try:
        if route == "global":
            app.carrier_binding_mode = binding.get("mode") or ""
            app.carrier_binding_source = binding.get("source") or ""
        elif route.startswith("instrument:"):
            name = route.split(":", 1)[1]
            samples = getattr(app, "instrument_media_samples", None)
            if not isinstance(samples, dict):
                samples = app.instrument_media_samples = {}
            rec = dict(samples.get(name) or {})
            rec["binding_mode"] = binding.get("mode") or ""
            rec["binding_source"] = binding.get("source") or ""
            samples[name] = rec
    except Exception:
        pass


# ── carrier setters (file / waveform / plugin / generator) ───────────────────

def set_global_carrier(
    app,
    *,
    path: Optional[str] = None,
    waveform: Optional[np.ndarray] = None,
    sample_rate: int = 48000,
    amount: float = 1.0,
    vector: Optional[Sequence[float]] = None,
    binding: Optional[BindingVector] = None,
) -> BindingVector:
    """Direct global carrier from a file path or float array."""
    if path:
        try:
            arr, sr = app._decode_media_audio(path)
            waveform = np.asarray(arr, dtype=np.float32).ravel()
            sample_rate = int(sr)
        except Exception as exc:
            raise RuntimeError(f"decode failed: {exc}") from exc
        try:
            app.imported_wav_path = path
            app.imported_waveform = waveform
            app.imported_sample_rate = int(sample_rate)
            app._global_carrier_path = path
        except Exception:
            pass
        b = binding or default_binding("file", path, amount=amount, vector=vector)
    elif waveform is not None:
        y = np.asarray(waveform, dtype=np.float32).ravel()
        try:
            app.imported_waveform = y
            app.imported_sample_rate = int(sample_rate)
            app.imported_wav_path = "script://global"
            app._global_carrier_path = "script://global"
        except Exception:
            pass
        b = binding or default_binding("waveform", "script://global", amount=amount, vector=vector)
    else:
        raise ValueError("path or waveform required")
    _state(app)["global"] = b
    _mirror_legacy(app, "global", b)
    try:
        app._shared_mixdown_cache = {}
        app._on_live_source_changed()
    except Exception:
        pass
    return copy.deepcopy(b)


def set_instrument_carrier(
    app,
    instrument: str,
    *,
    path: Optional[str] = None,
    waveform: Optional[np.ndarray] = None,
    sample_rate: int = 48000,
    plugin_id: Optional[str] = None,
    amount: float = 1.0,
    vector: Optional[Sequence[float]] = None,
) -> BindingVector:
    """Direct per-instrument carrier: file, array, or plugin id."""
    name = str(instrument)
    samples = getattr(app, "instrument_media_samples", None)
    if not isinstance(samples, dict):
        samples = app.instrument_media_samples = {}
    prev = dict(samples.get(name) or {})

    if plugin_id:
        try:
            import plugin_library as pl
            pl.bind_carrier(app, name, plugin_id)
        except Exception as exc:
            raise RuntimeError(f"plugin bind failed: {exc}") from exc
        b = default_binding("plugin", str(plugin_id), amount=amount, vector=vector)
    elif path:
        try:
            arr, sr = app._decode_media_audio(path)
            y = np.asarray(arr, dtype=np.float32).ravel()
            sample_rate = int(sr)
        except Exception as exc:
            raise RuntimeError(f"decode failed: {exc}") from exc
        samples[name] = {**prev, "path": path, "sample_rate": sample_rate, "waveform": y,
                         "user_owned": True, "source_kind": "audio"}
        b = default_binding("file", path, amount=amount, vector=vector)
    elif waveform is not None:
        y = np.asarray(waveform, dtype=np.float32).ravel()
        samples[name] = {**prev, "path": "script://" + name, "sample_rate": int(sample_rate),
                         "waveform": y, "user_owned": True, "source_kind": "audio"}
        b = default_binding("waveform", "script://" + name, amount=amount, vector=vector)
    else:
        raise ValueError("path, waveform, or plugin_id required")

    route = "instrument:" + name
    _state(app)[route] = b
    _mirror_legacy(app, route, b)
    try:
        app._shared_mixdown_cache = {}
        app._on_live_source_changed()
    except Exception:
        pass
    return copy.deepcopy(b)


def bind_generator(
    app,
    route: RouteKey,
    kind: str = "structured",
    *,
    seconds: float = 2.0,
    sample_rate: int = 48000,
    seed: Any = 0,
    base_hz: float = 432.0,
    amount: float = 0.5,
    vector: Optional[Sequence[float]] = None,
    ratio_set: str = "meum",
) -> BindingVector:
    """Generate a sample and bind it to a carrier route (global or instrument:…)."""
    y = generate(kind, seconds=seconds, sr=sample_rate, seed=seed,
                 vector=vector, base_hz=base_hz, ratio_set=ratio_set)
    b = default_binding(
        "generator", kind, amount=amount, vector=vector or seed_vector(seed),
        meta={"seconds": seconds, "sr": sample_rate, "base_hz": base_hz, "ratio_set": ratio_set},
    )
    if route == "global":
        set_global_carrier(app, waveform=y, sample_rate=sample_rate, amount=amount, vector=b["vector"], binding=b)
    elif route.startswith("instrument:"):
        set_instrument_carrier(app, route.split(":", 1)[1], waveform=y, sample_rate=sample_rate,
                               amount=amount, vector=b["vector"])
        _state(app)[route] = b
        _mirror_legacy(app, route, b)
    else:
        _state(app)[route] = b
    return copy.deepcopy(b)


# ── generators (built-in + plugin-registered) ────────────────────────────────

def register_generator(name: str, fn: Callable[..., np.ndarray]) -> None:
    """Plugins/scripts: register a named generator ``fn(**kwargs) -> float32 mono``."""
    _GENERATORS[str(name)] = fn


def list_generators() -> List[str]:
    builtin = []
    try:
        import sample_generator as sg
        builtin = list(getattr(sg, "KINDS", ()))
    except Exception:
        builtin = ["noise_white", "noise_pink", "noise_brown", "static", "structured"]
    return sorted(set(builtin) | set(_GENERATORS))


def generate(
    kind: str,
    *,
    seconds: float = 2.0,
    sr: int = 48000,
    seed: Any = 0,
    slot: int = 0,
    base_hz: float = 432.0,
    vector: Optional[Sequence[float]] = None,
    ratio_set: str = "meum",
    source: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Run a built-in or registered generator → float32 mono."""
    if kind in _GENERATORS:
        y = _GENERATORS[kind](seconds=seconds, sr=sr, seed=seed, slot=slot,
                              base_hz=base_hz, vector=_norm_vector(vector), source=source)
        return np.asarray(y, dtype=np.float32).ravel()
    try:
        import sample_generator as sg
        return np.asarray(
            sg.generate(kind, seconds, sr, seed=seed, slot=slot, base_hz=base_hz,
                        source=source, ratio_set=ratio_set),
            dtype=np.float32,
        ).ravel()
    except Exception:
        # minimal deterministic fallback
        n = max(16, int(seconds * sr))
        r = np.random.default_rng(int(hashlib.blake2b(str(seed).encode(), digest_size=8).hexdigest(), 16) & 0x7FFFFFFF)
        t = np.arange(n) / float(sr)
        v = _norm_vector(vector)
        f0 = float(base_hz) * (0.5 + v[0])
        y = np.sin(2 * np.pi * f0 * t) * (0.3 + 0.4 * v[1])
        return y.astype(np.float32)


# ── modulation helper using binding vector ───────────────────────────────────

def modulate(binding: BindingVector, t_norm: float = 0.0) -> Dict[str, float]:
    """Map a binding vector + curve + amount to named modulation depths.

    Returns keys usable by sample_generator destinations / Mod Matrix amounts:
    pitch, amp, morph, stretch, wet, bias.
    """
    if not binding.get("enabled", True):
        return {k: 0.0 for k in ("pitch", "amp", "morph", "stretch", "wet", "bias")}
    v = _norm_vector(binding.get("vector"))
    amt = float(binding.get("amount", 1.0)) * float(binding.get("polarity", 1.0))
    curve = str(binding.get("curve") or "linear")
    rate = float(binding.get("rate_beats") or 0.0)
    phase = (t_norm * rate) % 1.0 if rate > 0 else 0.0
    u = [apply_curve((x + phase) % 1.0, curve) for x in v]
    return {
        "pitch": amt * (u[0] - 0.5) * 2.0,
        "amp": amt * u[1],
        "morph": amt * u[2],
        "stretch": amt * (0.5 + u[3]),
        "wet": amt * u[4],
        "bias": amt * (u[5] - 0.5) * 2.0,
    }


def snapshot(app) -> Dict[str, Any]:
    """Serializable snapshot of every route binding (for projects / scripts)."""
    return {
        "schema": "carrier_generator_path/1",
        "routes": {k: copy.deepcopy(v) for k, v in _state(app).items()},
        "generators": list_generators(),
    }


def restore(app, snap: dict) -> int:
    n = 0
    for route, binding in (snap.get("routes") or {}).items():
        if isinstance(binding, dict):
            _state(app)[str(route)] = default_binding(
                binding.get("mode", "none"),
                binding.get("source", ""),
                amount=float(binding.get("amount", 1.0)),
                polarity=float(binding.get("polarity", 1.0)),
                curve=str(binding.get("curve", "linear")),
                vector=binding.get("vector"),
                rate_beats=float(binding.get("rate_beats", 0.0)),
                enabled=bool(binding.get("enabled", True)),
                meta=binding.get("meta") if isinstance(binding.get("meta"), dict) else {},
            )
            _mirror_legacy(app, str(route), _state(app)[str(route)])
            n += 1
    return n
