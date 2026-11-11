"""seed_structure_dj.py — GROOVEBOX_R32_SEED_STRUCTURE_DJ_20261110

Parametric DJ / Playlist Seed that *mimics the seed's structure with real media*.

1. STRUCTURE — the seed program is evaluated at N slot times (like the wave engine samples a
   script over t): value v(t), its slope v'(t) and its curvature v''(t). Each is rank-normalised
   to 0..1, giving a target path through three musical dimensions:
        v     → ENERGY    (loudness · transient density)
        v'    → BRIGHTNESS (spectral centroid)
        v''   → PITCH     (fundamental, octave-folded)
2. SCAN — media from the Performance playlist and (optionally) the system: project exports,
   recordings, samples, shared folders, ~/Music and ~/Videos. Every file is measured with the
   real signal descriptor (reverse_engineer.describe: rms, centroid, fundamental, zcr,
   transient density) — cached by path+mtime so a rescan is instant.
3. MATCH — slot by slot, the unused file whose rank-normalised descriptor is nearest the
   target (weighted Euclidean) is chosen; repeats are allowed only when the library is smaller
   than the slot count. The result is deterministic for a given seed + library.
4. TIME — slots are laid out on a timeline: each item's start (time_s), length (from the seed's
   |v'|: busy passages → shorter cuts), and DJ parameters follow the curve — level from v,
   playback rate from v' (±8 %), pitch from v'' (±3 st), reverse on sign changes of v'.
"""
from __future__ import annotations

import math
import os

import numpy as np

MEDIA = (".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aiff", ".mp4", ".mkv", ".webm", ".mov")


def seed_curve(app, n, span_beats=64.0):
    import seed_lang
    gb = __import__("groovebox")
    raw = app._seed_text() if hasattr(app, "_seed_text") else "sin(t)"
    ts = np.linspace(0.0, span_beats, int(n))
    v = []
    for t in ts:
        ev = seed_lang.evaluate(raw, gb._seed_script_env(t_scalar=float(t)))
        v.append(ev.values[0] if ev.values else 0.0)
    v = np.asarray(v, dtype=np.float64)
    d1 = np.gradient(v) if v.size > 1 else np.zeros_like(v)
    d2 = np.gradient(d1) if v.size > 2 else np.zeros_like(v)
    return ts, v, d1, d2


def _rank(x):
    x = np.asarray(x, dtype=np.float64)
    if x.size < 2 or np.allclose(x, x[0]):
        return np.full(x.size, 0.5)
    order = np.argsort(np.argsort(x, kind="stable"), kind="stable")
    return order / float(x.size - 1)


def scan_paths(app, perf=None, system=True):
    paths = []
    if perf is not None:
        paths += [it.get("path") for it in getattr(perf, "_playlist", []) or [] if it.get("path")]
    if system:
        roots = []
        try:
            import groovebox_paths as gp
            pp = getattr(app, "_current_project_path", None)
            roots += [gp.audio_exports_dir(pp), gp.video_exports_dir(pp), gp.recordings_dir(pp), gp.samples_dir(pp),
                      gp.global_exports_dir(), gp.global_samples_dir()]
        except Exception:
            pass
        try:
            import groovebox_site as gs
            roots += [f for f, on in (gs.load_cfg().get("folders") or {}).items() if on]
        except Exception:
            pass
        home = os.path.expanduser("~")
        roots += [os.path.join(home, d) for d in ("Music", "Videos")]
        for r in dict.fromkeys(roots):
            if not os.path.isdir(r):
                continue
            for dp, ds, fs in os.walk(r):
                ds[:] = [d for d in ds if not d.startswith(".") and d not in ("cache", "metadata")]
                for f in fs:
                    if f.lower().endswith(MEDIA) and ".part" not in f:
                        paths.append(os.path.join(dp, f))
                if len(paths) > 2000:
                    break
    try:
        import groovebox_site as gs
        und = set(gs.load_cfg().get("undetectable", []))
    except Exception:
        und = set()
    try:
        import groovebox_paths as _gp
        _sys = _gp.is_system_path
    except Exception:
        _sys = lambda _p: False
    return [p for p in dict.fromkeys(paths) if p and os.path.isfile(p) and p not in und and not _sys(p)]


def describe_all(paths, cache, progress=None):
    import performance as perfmod
    out = {}
    for i, p in enumerate(paths):
        d = perfmod._analyze_signal_descriptor(p, cache)
        if d:
            out[p] = d
        if progress and i % 8 == 0:
            progress(i, len(paths))
    return out


def arrange(app, descs, n_slots=None, span_beats=64.0, bpm=120.0):
    """Return a list of playlist item dicts that follow the seed's structure."""
    paths = list(descs)
    if not paths:
        return []
    n = int(n_slots or min(32, max(4, len(paths))))
    ts, v, d1, d2 = seed_curve(app, n, span_beats)
    tgt = np.stack([_rank(v), _rank(d1), _rank(np.abs(d2))], axis=1)
    rms = np.array([descs[p].get("rms", 0) + 0.5 * descs[p].get("transient_density", 0) for p in paths])
    cen = np.array([descs[p].get("centroid_hz", 0) for p in paths])
    f0 = np.array([math.log2(max(20.0, descs[p].get("fundamental_hz", 0) or 20.0)) % 1.0 for p in paths])
    feat = np.stack([_rank(rms), _rank(cen), _rank(f0)], axis=1)
    w = np.array([1.0, 0.8, 0.5])
    used = set(); items = []
    sec_per_beat = 60.0 / max(20.0, float(bpm))
    slot_beats = span_beats / n
    t_cursor = 0.0
    dmax = float(np.max(np.abs(d1))) or 1.0
    for k in range(n):
        dist = np.sqrt((((feat - tgt[k]) * w) ** 2).sum(axis=1))
        order = np.argsort(dist, kind="stable")
        pick = next((int(i) for i in order if int(i) not in used), int(order[0]))
        used.add(pick)
        if len(used) >= len(paths):
            used.clear()
        busy = abs(d1[k]) / dmax
        length = max(1.0, slot_beats * (1.5 - busy)) * sec_per_beat
        p = paths[pick]
        items.append({
            "path": p, "kind": "audio" if p.lower().endswith((".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aiff")) else "video",
            "time_s": round(t_cursor, 3), "duration_s": round(length, 3),
            "volume": int(round(70 + 45 * tgt[k][0])), "rate": round(1.0 + 0.08 * (2 * tgt[k][1] - 1), 4),
            "pitch_semitones": round(3.0 * (2 * tgt[k][2] - 1), 3),
            "direction": "reverse" if k and np.sign(d1[k]) != np.sign(d1[k - 1]) and abs(d1[k]) > 0.5 * dmax else "forward",
            "resample": "preserve-duration", "mix": False,
            "seed_structure": {"slot": k, "beat": round(float(ts[k]), 3), "target": [round(float(x), 3) for x in tgt[k]],
                               "match_distance": round(float(dist[pick]), 4)},
        })
        t_cursor += length
    return items


def apply_to_performance(perf, system=True, n_slots=None):
    """Scan → measure (worker thread) → arrange → write into the Performance playlist (GUI thread)."""
    import threading
    from PyQt6.QtCore import QObject, pyqtSignal
    app = perf.host
    if getattr(perf, "_seed_dj_busy", False):
        perf.lbl_status.setText("Seed-structure DJ is already measuring…"); return 0
    perf._seed_dj_busy = True
    bpm = float(getattr(getattr(app, "spin_bpm", None), "value", lambda: 120.0)())

    class _B(QObject):
        done = pyqtSignal(object)
        prog = pyqtSignal(str)
    b = _B(perf); perf._seed_dj_bridge = b
    b.prog.connect(perf.lbl_status.setText)
    b.done.connect(lambda items: _finish(perf, items))
    perf.lbl_status.setText("Seed-structure DJ: scanning media…")

    def work():
        try:
            paths = scan_paths(app, perf, system=system)
            descs = describe_all(paths, perf._analysis_cache,
                                 progress=lambda i, n: b.prog.emit("Seed-structure DJ: measuring %d / %d…" % (i, n)))
            items = arrange(app, descs, n_slots=n_slots, bpm=bpm)
            b.done.emit((items, len(descs)))
        except Exception as exc:
            b.done.emit(("error", str(exc)))
    threading.Thread(target=work, daemon=True, name="seed-structure-dj").start()
    return -1


def _finish(perf, result):
    perf._seed_dj_busy = False
    if result and result[0] == "error":
        perf.lbl_status.setText("Seed-structure DJ error: %s" % result[1]); return 0
    items, n_desc = result
    descs = range(n_desc)
    if not items:
        perf.lbl_status.setText("Seed-structure DJ: no measurable media found (add files or share folders).")
        return 0
    perf._playlist_randomize_undo = [dict(it) for it in perf._playlist]
    perf._playlist = items
    perf._playlist_index = 0
    perf._refresh_playlist_widget()
    try:
        perf._sync_project_state()
    except Exception:
        pass
    perf.lbl_status.setText("Seed-structure DJ: %d slot(s) from %d measured file(s) follow the seed's energy / "
                            "brightness / pitch path · Undo Randomize restores the previous playlist." % (len(items), len(descs)))
    return len(items)
