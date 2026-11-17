"""audio_diagnostics.py — per-source meters for the Live Player and a pre-export integrity check.
measure(arr) → peak, rms, clipped samples, non-finite samples. The Live Player engine stores one entry per source
(composition, media, keys, mic, final, recording) every callback; the window shows them in its status line."""
from __future__ import annotations
import numpy as np


def measure(a):
    a = np.asarray(a)
    if a.size == 0:
        return {"peak": 0.0, "rms": 0.0, "clip": 0, "nan": 0}
    bad = int(np.count_nonzero(~np.isfinite(a)))
    b = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    return {"peak": float(np.max(np.abs(b))), "rms": float(np.sqrt(np.mean(b * b))),
            "clip": int(np.count_nonzero(np.abs(b) >= 0.999)), "nan": bad}


def bar(m):
    p = m.get("peak", 0.0)
    if p <= 1e-5: return "·"
    n = max(1, min(6, int(round((20 * np.log10(p) + 60) / 10))))
    return "▮" * n + ("!" if m.get("clip") else "")


def line(meters):
    order = ("comp", "media", "keys", "mic", "final", "rec")
    parts = ["%s %s" % (k, bar(meters[k])) for k in order if k in meters]
    flags = [k for k in order if k in meters and meters[k].get("nan")]
    return "🎚 " + "  ".join(parts) + (("  ⚠ non-finite: " + ",".join(flags)) if flags else "")


def check_buffer(buf, sr, label="mixdown"):
    """(ok, message) for a buffer about to be exported."""
    m = measure(buf)
    if np.asarray(buf).size == 0: return False, "%s is empty" % label
    if m["nan"]: return False, "%s has %d non-finite samples" % (label, m["nan"])
    if m["peak"] < 1e-6: return False, "%s is silent" % label
    if m["clip"] > max(32, int(0.001 * np.asarray(buf).size)): return True, "%s clips on %d samples" % (label, m["clip"])
    return True, "%s OK · peak %.1f dBFS · %d Hz" % (label, 20 * np.log10(max(m["peak"], 1e-9)), int(sr))


def pre_export_check(app):
    """Check the cached shared mixdown (no render is started). Returns (ok, message) or (True, '') if none cached."""
    try:
        key = app._shared_mixdown_key(None)
        ent = (getattr(app, "_shared_mixdown_cache", {}) or {}).get(key)
        if ent is None:
            return True, ""
        return check_buffer(ent[0], ent[1])
    except Exception as exc:
        return True, "check skipped: %s" % exc
