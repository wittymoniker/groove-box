"""seed_media_bridge.py — one seed, three media.

GROOVEBOX_SEED_MEDIA_20261111
The fractal claim: a logical numerical seed is the parent of music, video, and
game. This module is the single packet those three read.

    packet = identity_packet(app)          # or from a frozen document
    packet["audio"]   child seeds for voices / mix
    packet["video"]   child seeds for expression / spatial
    packet["game"]    the classify_from_composition fingerprint inputs
    packet["fingerprint"]  stable id of this reading

Exports stamp the packet beside the file so a take, a render, and a game
launch from the same project share one id.
"""
from __future__ import annotations

import hashlib
import json
import os


def _seed_of(app_or_doc):
    if isinstance(app_or_doc, dict):
        return app_or_doc.get("seed") or app_or_doc.get("project_seed") or 1
    for name in ("project_seed", "seed", "_project_seed"):
        v = getattr(app_or_doc, name, None)
        if v is not None:
            return v
    return 1


def _script_of(app_or_doc):
    if isinstance(app_or_doc, dict):
        return str(app_or_doc.get("seed_script") or app_or_doc.get("seed_program") or "")
    for name in ("seed_script_text", "seed_program", "_seed_script"):
        v = getattr(app_or_doc, name, None)
        if v:
            return str(v)
    try:
        ed = getattr(app_or_doc, "seed_script_edit", None)
        if ed is not None and hasattr(ed, "toPlainText"):
            return ed.toPlainText()
    except Exception:
        pass
    return ""


def identity_packet(app_or_doc) -> dict:
    """One packet for audio, video, and game from the same seed."""
    seed = _seed_of(app_or_doc)
    script = _script_of(app_or_doc)
    try:
        import groovebox as g
        audio = {
            "voice": g.seed_child(seed, "audio", "voice"),
            "mix": g.seed_child(seed, "audio", "mix"),
            "fx": g.seed_child(seed, "audio", "fx"),
        }
        video = {
            "expression": g.seed_child(seed, "video", "expression"),
            "spatial": g.seed_child(seed, "video", "spatial"),
            "rig": g.seed_child(seed, "video", "rig"),
        }
        game = {
            "world": g.seed_child(seed, "game", "world"),
            "identity": g.seed_child(seed, "game", "identity"),
        }
    except Exception:
        audio = video = game = {}
    sig = 0
    try:
        import seed_lang
        if script.strip():
            sig = int(seed_lang.signature(script, lambda t: {"t": t, "t_norm": t}))
    except Exception:
        sig = 0
    raw = json.dumps({
        "seed": str(seed), "signature": sig,
        "script": hashlib.sha256(script.encode("utf-8", "replace")).hexdigest()[:16],
        "audio": audio, "video": video, "game": game,
    }, sort_keys=True, default=str)
    fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return {
        "seed": seed,
        "signature": sig,
        "fingerprint": fp,
        "audio": audio,
        "video": video,
        "game": game,
    }


def stamp_export(path: str, packet: dict) -> str:
    """Write <file>.seed.json beside an export. Returns the sidecar path or ''."""
    if not path:
        return ""
    side = path + ".seed.json"
    try:
        with open(side, "w", encoding="utf-8") as f:
            json.dump(packet, f, indent=2, default=str)
        return side
    except Exception:
        return ""
