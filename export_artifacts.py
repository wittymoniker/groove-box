"""export_artifacts.py — every export stage yields something to hear/see/play."""
from __future__ import annotations
import os, gc
from typing import Optional
import numpy as np

def stage_audio_part(dest_dir, stem, index, sr, pcm, bit_depth=16):
    """Write MGR + preview WAV for one audio part; release large temps."""
    import mgr_format as mgr
    path = mgr.part_path(dest_dir, stem, index, "audio_pcm_f32")
    arr = np.asarray(pcm, dtype=np.float32).reshape(-1)
    mgr.write_audio_f32(path, int(sr), arr, {"part": int(index), "stem": stem})
    preview = mgr.ensure_playable_sibling(path, int(sr), arr)
    del arr
    return {"mgr": path, "preview": preview}

def stage_synth_row(dest_dir, stem, row_index, row: dict, pcm=None, sr=44100):
    import mgr_format as mgr
    path = os.path.join(dest_dir, f"{stem}.row{int(row_index):03d}.mgr.synth_row")
    mgr.write_synth_row(path, row, pcm=pcm, sr=int(sr))
    out = {"mgr": path}
    if pcm is not None:
        out["preview"] = path + ".preview.wav"
    return out

def stage_preview_frame_stub(dest_dir, stem, index, rgb_bytes=None, w=0, h=0):
    """If a video frame buffer exists, write a tiny preview PPM/JPG path record."""
    path = os.path.join(dest_dir, f"{stem}.part{int(index):02d}.mgr.preview_frame")
    try:
        import mgr_format as mgr
        meta = {"w": int(w), "h": int(h), "part": int(index)}
        with open(path, "wb") as f:
            mgr.write_header(f, mgr.TYPE["preview_frame"], meta)
            if rgb_bytes:
                f.write(bytes(rgb_bytes)[: max(0, int(w) * int(h) * 3)])
        return path
    except Exception:
        return ""

def release_export_temps(*objs):
    for o in objs:
        try:
            del o
        except Exception:
            pass
    try:
        gc.collect(0)
    except Exception:
        pass
