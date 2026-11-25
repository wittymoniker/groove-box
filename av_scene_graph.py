"""GROOVEBOX_R124_AV_SCENE_GRAPH: audio-reactive visual/game scene graph, routed like audio.

Nodes are visual parameters of the existing engines (geometric vector/wavetable/ball/cellular, fractal,
Multidim sphere, camera). Edges map an audio feature (rms, peak, centroid, band energies, onset, beat
phase) through gain/offset/curve onto a node parameter — the same route-handle shape the audio side
uses. ``evaluate(graph, features)`` is pure; ``features_from_buffer`` computes the inputs from audio.
``export_scene(graph, path, frames)`` writes a JSON scene that the video export and the game engine can
both play back deterministically.
"""
from __future__ import annotations

import json
try:  # R132.10: project trig route — book isy/isx series when the Trigonometry Engine is ON (gb_trig)
    from gb_trig import cos as _tcos
except Exception:  # standalone use outside the app
    from math import cos as _tcos
import math

import numpy as np

FEATURES = ("rms", "peak", "centroid", "low", "mid", "high", "onset", "beat_phase")
NODES = {
    "vector.x": (-1.0, 1.0), "vector.y": (-1.0, 1.0), "vector.z": (-1.0, 1.0),
    "wavetable.twist": (0.0, 1.0), "wavetable.fold": (0.0, 1.0),
    "ball.gravity": (0.0, 40.0), "ball.elasticity": (0.0, 1.0),
    "cellular.rule": (0.0, 255.0), "fractal.depth": (0.0, 1.0),
    "sphere.yaw": (0.0, 2 * math.pi), "sphere.pitch": (-1.5, 1.5), "camera.zoom": (0.25, 4.0),
    "color.hue": (0.0, 1.0), "color.brightness": (0.0, 1.0),
}
CURVES = {"linear": lambda v: v, "square": lambda v: v * v, "sqrt": lambda v: math.sqrt(max(0.0, v)),
          "sine": lambda v: 0.5 - 0.5 * _tcos(math.pi * v)}

DEFAULT_GRAPH = {"edges": [
    {"src": "low", "dst": "ball.gravity", "gain": 1.0, "offset": 0.0, "curve": "linear"},
    {"src": "centroid", "dst": "color.hue", "gain": 1.0, "offset": 0.0, "curve": "linear"},
    {"src": "rms", "dst": "camera.zoom", "gain": 0.6, "offset": 0.2, "curve": "sqrt"},
    {"src": "beat_phase", "dst": "sphere.yaw", "gain": 1.0, "offset": 0.0, "curve": "linear"},
    {"src": "high", "dst": "fractal.depth", "gain": 1.0, "offset": 0.0, "curve": "square"},
]}


def features_from_buffer(x, sr, bpm=120.0, t=0.0, prev_rms=0.0):
    """All features normalized to 0..1."""
    a = np.asarray(x, dtype=np.float64)
    m = a.mean(axis=1) if a.ndim == 2 else a
    if m.size == 0:
        return {k: 0.0 for k in FEATURES}
    rms = float(np.sqrt(np.mean(m * m))); peak = float(np.max(np.abs(m)))
    spec = np.abs(np.fft.rfft(m * np.hanning(m.size))); fr = np.fft.rfftfreq(m.size, 1.0 / sr)
    tot = float(np.sum(spec)) + 1e-12
    band = lambda lo, hi: float(np.sum(spec[(fr >= lo) & (fr < hi)])) / tot
    cen = float(np.sum(fr * spec)) / tot
    return {"rms": min(1.0, rms * 2.0), "peak": min(1.0, peak), "centroid": min(1.0, math.log2(max(cen, 20.0) / 20.0) / 10.0),
            "low": band(20, 250), "mid": band(250, 4000), "high": band(4000, sr / 2.0),
            "onset": 1.0 if rms > prev_rms * 1.5 + 0.02 else 0.0,
            "beat_phase": (t * float(bpm) / 60.0) % 1.0}


def evaluate(graph, features):
    """{node: value} — several edges on one node add, then clamp to the node range."""
    out = {}
    for e in (graph or DEFAULT_GRAPH).get("edges", []):
        if e.get("dst") not in NODES:
            continue
        v = float(features.get(e.get("src"), 0.0))
        v = CURVES.get(e.get("curve", "linear"), CURVES["linear"])(max(0.0, min(1.0, v)))
        lo, hi = NODES[e["dst"]]
        out[e["dst"]] = out.get(e["dst"], 0.0) + lo + (hi - lo) * (float(e.get("offset", 0.0)) + float(e.get("gain", 1.0)) * v)
    for k, v in out.items():
        lo, hi = NODES[k]; out[k] = max(lo, min(hi, v))
    return out


def render_frames(graph, audio, sr, fps=30, bpm=120.0):
    a = np.asarray(audio, dtype=np.float64)
    hop = int(sr / fps); frames = []; prev = 0.0
    for i in range(0, max(1, (a.shape[0] - hop) // hop + 1)):
        seg = a[i * hop:(i + 1) * hop]
        f = features_from_buffer(seg, sr, bpm, i / float(fps), prev); prev = f["rms"] / 2.0
        frames.append({"t": round(i / float(fps), 4), "values": {k: round(v, 5) for k, v in evaluate(graph, f).items()}})
    return frames


def export_scene(graph, path, frames, fps=30, meta=None):
    doc = {"format": "groovebox-av-scene", "version": 1, "fps": fps, "graph": graph, "frames": frames, "meta": meta or {}}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return path


def load_graph(app=None):
    try:
        import compat_settings as cs
        return cs.load().get("av_scene_graph") or json.loads(json.dumps(DEFAULT_GRAPH))
    except Exception:
        return json.loads(json.dumps(DEFAULT_GRAPH))


def save_graph(graph):
    try:
        import compat_settings as cs
        cs.update(av_scene_graph=graph)
    except Exception:
        pass
