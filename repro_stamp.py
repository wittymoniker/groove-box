"""GROOVEBOX_R124_REPRO_STAMP: reproducibility stamp for every export.

A stamp records everything needed to rebuild a render exactly:
    seed text + seed value, BPM, selected instrument, engine/module versions (SHA-256 of the runtime
    modules that shape audio), SHA-256 of every sCode kernel source, a canonical hash of the whole
    parameter state, the master-chain settings and the measured output summary.
It is written as ``<export>.stamp.json`` beside the file. ``diff(a, b)`` lists exactly what changed
between two renders; ``rebuild_hint(stamp)`` says how to restore it.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAMP_VERSION = 1
AUDIO_MODULES = ("groovebox.py", "export_worker.py", "multidim_synth.py", "master_chain.py", "measure_core.py",
                 "hardcoded_fx.py", "live_player.py", "scode_hybrid.py", "hybrid_runtime.py", "markov_resampler.py")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path) -> str | None:
    try:
        return _sha(Path(path).read_bytes())
    except Exception:
        return None


def module_hashes(root=ROOT):
    return {m: (file_hash(Path(root) / m) or "missing")[:16] for m in AUDIO_MODULES}


def kernel_hashes(root=ROOT):
    out = {}
    for base in ("scode", "sCode/scode/libs", "plugins_library", "julia"):
        d = Path(root) / base
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".scode", ".sc", ".jl", ".c", ".cpp", ".rs", ".go", ".lua") \
                    and "__pycache__" not in p.parts and "build" not in p.parts:
                out[str(p.relative_to(root))] = (file_hash(p) or "")[:16]
    return out


def _jsonable(v, depth=0):
    if depth > 8:
        return str(type(v).__name__)
    if isinstance(v, (str, int, bool)) or v is None:
        return v
    if isinstance(v, float):
        return round(v, 9)
    if isinstance(v, dict):
        return {str(k): _jsonable(x, depth + 1) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x, depth + 1) for x in v]
    try:
        import numpy as np
        if isinstance(v, np.ndarray):
            return {"ndarray": list(v.shape), "sha": _sha(np.ascontiguousarray(v).tobytes())[:16]}
        if isinstance(v, np.generic):
            return _jsonable(v.item(), depth)
    except Exception:
        pass
    return str(type(v).__name__)


def param_state(app):
    keys = ("instrument_sequence_banks", "instrument_param_state", "master_playlist_data", "instrument_routes",
            "automation_lanes", "mod_matrix", "patch_cables")
    st = {k: _jsonable(getattr(app, k, None)) for k in keys if getattr(app, k, None) is not None}
    for attr in ("spin_bpm", "slider_master_vol"):
        w = getattr(app, attr, None)
        try:
            st[attr] = w.value()
        except Exception:
            pass
    return st


def _text(app, attr):
    w = getattr(app, attr, None)
    for m in ("text", "toPlainText"):
        try:
            return str(getattr(w, m)())
        except Exception:
            continue
    return None


def build(app=None, export_path=None, buffer=None, sr=None, extra=None):
    st = param_state(app) if app is not None else {}
    stamp = {
        "stamp_version": STAMP_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "export": str(export_path) if export_path else None,
        "export_sha256": file_hash(export_path) if export_path and os.path.isfile(str(export_path)) else None,
        "seed_text": _text(app, "input_starter_patch_seed") if app is not None else None,
        "seed_script": _text(app, "input_seed_val") if app is not None else None,
        "bpm": st.get("spin_bpm"),
        "selected_instrument": None,
        "python": sys.version.split()[0], "platform": platform.platform(),
        "modules": module_hashes(), "kernels": kernel_hashes(),
        "param_state_sha256": _sha(json.dumps(st, sort_keys=True, default=str).encode()),
        "param_sections": {k: _sha(json.dumps(v, sort_keys=True, default=str).encode())[:16] for k, v in st.items()},
    }
    try:
        import panel_synth_deck as psd
        stamp["selected_instrument"] = psd._name(app)
    except Exception:
        pass
    try:
        import master_chain
        stamp["master_chain"] = master_chain.load()
    except Exception:
        pass
    if buffer is not None and sr:
        try:
            import measure_core
            stamp["measured"] = measure_core.summary(buffer, sr)
        except Exception:
            pass
    if extra:
        stamp["extra"] = _jsonable(extra)
    return stamp


def write(stamp, export_path):
    p = Path(str(export_path) + ".stamp.json")
    p.write_text(json.dumps(stamp, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return p


def read(path):
    p = Path(path)
    if not p.name.endswith(".stamp.json"):
        p = Path(str(p) + ".stamp.json")
    return json.loads(p.read_text(encoding="utf-8"))


def _flat(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flat(v, f"{prefix}{k}."))
    else:
        out[prefix[:-1]] = d
    return out


IGNORE = ("created", "export", "export_sha256")


def diff(a, b):
    """[(key, a_value, b_value)] for every field that differs (timestamps/paths ignored)."""
    fa, fb = _flat(a), _flat(b)
    keys = sorted(set(fa) | set(fb))
    return [(k, fa.get(k), fb.get(k)) for k in keys if k.split(".")[0] not in IGNORE and fa.get(k) != fb.get(k)]


def same_render(a, b):
    """True when two stamps describe a bit-identical render recipe."""
    return not [d for d in diff(a, b) if not d[0].startswith(("measured.", "python", "platform"))]


def rebuild_hint(stamp):
    lines = [f"Seed: {stamp.get('seed_text')!r}   BPM: {stamp.get('bpm')}   instrument: {stamp.get('selected_instrument')}",
             f"Parameter state SHA-256: {stamp.get('param_state_sha256')}",
             "Open the project checkpoint with this state hash, or re-seed with the seed text and re-apply the",
             "master chain settings recorded here. Module/kernel hashes must match for a bit-identical render."]
    return "\n".join(lines)


def wrap_exports(app):
    """Write a stamp beside every file that export_audio produces (idempotent)."""
    if getattr(app, "_r124_stamp_wrapped", False):
        return
    orig = getattr(app, "export_audio", None)
    if orig is None:
        return

    def export_audio(filepath, *a, **k):
        result = orig(filepath, *a, **k)
        try:
            if filepath and os.path.isfile(str(filepath)):
                write(build(app, filepath), filepath)
        except Exception as exc:
            print(f"[stamp] not written: {exc}")
        return result

    app.export_audio = export_audio
    app._r124_stamp_wrapped = True
