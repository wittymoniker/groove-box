"""media_transmuter.py — GROOVEBOX_R32_MEDIA_TRANSMUTER_20261110

SOUND · IMAGE · VIDEO · GAME → SOUND · IMAGE · VIDEO · GAME, and REVERSE-ENGINEER → .MCC project.

Every conversion is deterministic (same input → same output) and as invertible as the media allow:

  sound → image   log-frequency magnitude spectrogram (x = time, y = log f, brightness = dB); the
                  frequency map and time step are written into the PNG text chunk so image → sound
                  can invert it exactly up to phase.
  image → sound   the inverse: each column is a magnitude frame; phase is reconstructed by
                  phase-gradient integration (deterministic, no RNG), overlap-add → WAV.
  sound → video   scrolling spectrogram + level bar per frame, audio muxed in (ffmpeg).
  video → sound   the video's own audio track when present; otherwise the frames are sonified
                  (frame luminance columns → spectrum columns, as image → sound).
  image → video   deterministic zoom / pan path from the image's own luminance centroid (ffmpeg).
  video → image   contact sheet (tiled frames) or the per-pixel mean frame.
  any  → game     the media's fingerprint (signature of its feature track) becomes the game seed;
                  tempo and length come from the analysis → a playable exported game folder.
  game → sound/project  the exported game's IDENTITY (seed, bpm, genre…) becomes a seed program.
  any  → PROJECT  REVERSE ENGINEER: tempo (onset autocorrelation), base frequency (f0 histogram),
                  energy curve → a Fourier-series seed program (12 terms) that reproduces the
                  curve's shape over the song, brightness → wavetable / FX settings, onset density
                  → canonical engines, length → bars → a complete .MCC written through the app's
                  own snapshot, ready to open, play and refine.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess

import numpy as np

KINDS = ("sound", "image", "video", "game", "project")
AUDIO = (".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aiff", ".mcc")
IMAGE = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
VIDEO = (".mp4", ".mkv", ".webm", ".mov", ".avi")
N_BINS = 512
HOP = 512
F_LO, F_HI = 30.0, 16000.0


def kind_of(path):
    try:   # R32.8: midi / text / data kinds (signal_converters)
        import signal_converters as _sc
        _k = _sc.kind_of(path)
        if _k:
            return _k
    except Exception:
        pass
    e = os.path.splitext(path)[1].lower()
    if e in AUDIO:
        return "sound"
    if e in IMAGE:
        return "image"
    if e in VIDEO:
        return "video"
    if e == ".py" or os.path.isdir(path):
        return "game"
    return "sound"


def _ff():
    try:
        from groovebox_media_tools import resolve_local_tool
        return resolve_local_tool("ffmpeg") or shutil.which("ffmpeg")
    except Exception:
        return shutil.which("ffmpeg")


def _read_audio(p):
    import postprocess_window as pw
    y, sr = pw.read_audio(p)
    y = np.asarray(y, dtype=np.float64)
    return (y.mean(axis=1) if y.ndim == 2 else y), sr


def _write_audio(p, y, sr):
    import postprocess_window as pw
    return pw.write_audio(p, np.asarray(y, dtype=np.float32), sr)


# ---------------------------------------------------------------------------
# spectrogram <-> image
# ---------------------------------------------------------------------------
def _logmap(sr, nfft):
    f = np.geomspace(F_LO, min(F_HI, sr / 2 * 0.98), N_BINS)
    return f, f / (sr / nfft)


def spectrogram(y, sr, nfft=2048):
    win = np.hanning(nfft)
    n = 1 + max(0, (y.size - nfft) // HOP)
    frames = np.stack([y[i * HOP:i * HOP + nfft] * win for i in range(n)]) if y.size >= nfft else np.zeros((1, nfft))
    S = np.abs(np.fft.rfft(frames, axis=1))
    f, bins = _logmap(sr, nfft)
    M = np.stack([np.interp(bins, np.arange(S.shape[1]), s) for s in S], axis=1)  # (N_BINS, frames)
    db = 20 * np.log10(np.maximum(M, 1e-9))
    return db, f


def sound_to_image(src, dst):
    from PyQt6.QtGui import QImage
    y, sr = _read_audio(src)
    db, f = spectrogram(y, sr)
    top = float(db.max()); lo = top - 90.0
    u = np.clip((db - lo) / 90.0, 0, 1)[::-1]                       # low frequencies at the bottom
    img8 = (u * 255).astype(np.uint8)
    rgb = np.stack([img8, (img8 * 0.85).astype(np.uint8), (255 - img8 // 2).astype(np.uint8) * (img8 > 4)], axis=-1)
    h, w = img8.shape
    q = QImage(np.ascontiguousarray(rgb).data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    q.setText("groovebox_spectrogram", json.dumps({"sr": sr, "hop": HOP, "nfft": 2048, "db_top": top, "db_range": 90.0,
                                                   "f_lo": F_LO, "f_hi": float(f[-1]), "bins": N_BINS}))
    q.save(dst)
    return dst


def image_to_sound(src, dst, sr=48000, seconds=None):
    from PyQt6.QtGui import QImage
    q = QImage(src).convertToFormat(QImage.Format.Format_Grayscale8)
    meta = {}
    try:
        meta = json.loads(q.text("groovebox_spectrogram") or QImage(src).text("groovebox_spectrogram") or "{}")
    except Exception:
        meta = {}
    w, h = q.width(), q.height()
    arr = np.frombuffer(q.constBits().asstring(q.sizeInBytes()), dtype=np.uint8).reshape(h, q.bytesPerLine())[:, :w].astype(np.float64)
    arr = arr[::-1] / 255.0
    sr = int(meta.get("sr", sr)); nfft = int(meta.get("nfft", 2048)); hop = int(meta.get("hop", HOP))
    if seconds and not meta:
        hop = max(64, int(seconds * sr / max(1, w)))
    rng_db = float(meta.get("db_range", 80.0))
    mag_log = 10 ** ((arr * rng_db - rng_db) / 20.0)
    f = np.geomspace(float(meta.get("f_lo", F_LO)), float(meta.get("f_hi", min(F_HI, sr / 2 * 0.98))), arr.shape[0])
    lin = np.arange(nfft // 2 + 1) * sr / nfft
    out = np.zeros(hop * w + nfft); norm = np.zeros_like(out); win = np.hanning(nfft)
    phase = np.zeros(nfft // 2 + 1)
    omega = 2 * math.pi * np.arange(nfft // 2 + 1) * hop / nfft     # phase advance per hop (phase-gradient)
    for i in range(w):
        mag = np.interp(lin, f, arr[:, i] if arr.ndim == 2 else arr, left=0, right=0)
        mag = np.interp(lin, f, mag_log[:, i], left=0, right=0)
        phase = phase + omega
        frame = np.fft.irfft(mag * np.exp(1j * phase), nfft) * win
        out[i * hop:i * hop + nfft] += frame; norm[i * hop:i * hop + nfft] += win ** 2
    y = out / np.maximum(norm, 1e-6)
    y = y / (np.max(np.abs(y)) or 1.0) * 0.8
    return _write_audio(dst, y, sr)


# ---------------------------------------------------------------------------
# video / image with ffmpeg
# ---------------------------------------------------------------------------
def sound_to_video(src, dst, w=1280, h=720, fps=30):
    ff = _ff()
    if not ff:
        raise RuntimeError("ffmpeg is needed for video")
    vf = "[0:a]showspectrum=s=%dx%d:mode=combined:color=fruit:scale=log:slide=scroll,format=yuv420p[v]" % (w, h)
    r = subprocess.run([ff, "-y", "-v", "error", "-i", src, "-filter_complex", vf, "-map", "[v]", "-map", "0:a",
                        "-r", str(fps), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", dst], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])
    return dst


def video_to_sound(src, dst):
    ff = _ff()
    if not ff:
        raise RuntimeError("ffmpeg is needed")
    r = subprocess.run([ff, "-y", "-v", "error", "-i", src, "-vn", "-ac", "2", "-ar", "48000", dst], capture_output=True, text=True)
    if r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 1024:
        return dst
    sheet = os.path.splitext(dst)[0] + ".frames.png"
    subprocess.run([ff, "-y", "-v", "error", "-i", src, "-vf", "fps=8,scale=1:%d,tile=512x1" % N_BINS, "-frames:v", "1", sheet], capture_output=True)
    return image_to_sound(sheet, dst, seconds=None)


def image_to_video(src, dst, seconds=12, w=1280, h=720, fps=30):
    from PyQt6.QtGui import QImage
    ff = _ff()
    if not ff:
        raise RuntimeError("ffmpeg is needed for video")
    q = QImage(src).convertToFormat(QImage.Format.Format_Grayscale8)
    a = np.frombuffer(q.constBits().asstring(q.sizeInBytes()), dtype=np.uint8).reshape(q.height(), q.bytesPerLine())[:, :q.width()].astype(np.float64)
    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    cx = float((a * xs).sum() / max(1e-9, a.sum())) / max(1, a.shape[1]); cy = float((a * ys).sum() / max(1e-9, a.sum())) / max(1, a.shape[0])
    n = int(seconds * fps)
    z = "zoompan=z='1+0.35*on/%d':x='(iw-iw/zoom)*%.4f':y='(ih-ih/zoom)*%.4f':d=%d:s=%dx%d:fps=%d" % (n, cx, cy, n, w, h, fps)
    r = subprocess.run([ff, "-y", "-v", "error", "-loop", "1", "-i", src, "-vf", z + ",format=yuv420p", "-t", str(seconds),
                        "-c:v", "libx264", dst], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])
    return dst


def video_to_image(src, dst, mode="sheet"):
    ff = _ff()
    if not ff:
        raise RuntimeError("ffmpeg is needed")
    vf = "fps=1/4,scale=320:-1,tile=4x4" if mode == "sheet" else "tmix=frames=60,scale=1280:-1"
    r = subprocess.run([ff, "-y", "-v", "error", "-i", src, "-vf", vf, "-frames:v", "1", dst], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])
    return dst


# ---------------------------------------------------------------------------
# analysis → seed program / project / game
# ---------------------------------------------------------------------------
def analyse(path):
    k = kind_of(path)
    if k == "video":
        tmp = os.path.splitext(path)[0] + ".analysis.wav"
        video_to_sound(path, tmp); y, sr = _read_audio(tmp)
    elif k == "image":
        tmp = os.path.splitext(path)[0] + ".analysis.wav"
        image_to_sound(path, tmp); y, sr = _read_audio(tmp)
    else:
        y, sr = _read_audio(path)
    blk = int(sr * 0.01); n = y.size // blk
    e = np.sqrt((y[: n * blk].reshape(n, blk) ** 2).mean(axis=1)) if n else np.zeros(1)
    flux = np.maximum(0, np.diff(e, prepend=e[:1]))
    ac = np.correlate(flux - flux.mean(), flux - flux.mean(), "full")[flux.size - 1:]
    lags = np.arange(ac.size) * 0.01
    ok = (lags > 60 / 200.0) & (lags < 60 / 60.0)
    bpm = float(60.0 / lags[ok][np.argmax(ac[ok])]) if ok.any() and ac[ok].max() > 0 else 120.0
    import canonical_wavetools as cw
    f0s = [cw.detect_f0(y[i:i + sr // 2], sr) for i in range(0, max(1, y.size - sr // 2), max(1, sr))][:64]
    f0s = [f for f in f0s if f > 0]
    base = float(np.median(f0s)) if f0s else 432.0
    while base > 880:
        base /= 2
    while base < 110:
        base *= 2
    db, _f = spectrogram(y[: sr * 60], sr)
    bright = float(np.clip((np.argmax(db, axis=0).mean() / N_BINS), 0, 1))
    onset = float((flux > 3 * (np.median(flux) + 1e-12)).mean())
    sig = int.from_bytes(__import__("hashlib").blake2b(np.round(e[:: max(1, e.size // 512)], 4).tobytes(), digest_size=4).digest(), "little")
    return {"kind": k, "seconds": y.size / sr, "sr": sr, "bpm": round(bpm, 2), "base_hz": round(base, 3),
            "brightness": round(bright, 4), "onset_density": round(onset, 4), "energy": e, "signature": sig}


def fourier_seed(energy, seconds, bpm, terms=12):
    """Seed program whose value over the song follows the energy curve (least-squares Fourier fit)."""
    e = np.asarray(energy, dtype=np.float64)
    if e.size < 8:
        return "return 1.0"
    beats = seconds * bpm / 60.0
    t = np.linspace(0, 1, e.size)
    cols = [np.ones_like(t)]
    for k in range(1, terms + 1):
        cols += [np.cos(2 * math.pi * k * t), np.sin(2 * math.pi * k * t)]
    A = np.stack(cols, axis=1)
    coef, *_ = np.linalg.lstsq(A, (e - e.mean()) / (e.std() or 1.0), rcond=None)
    lines = ["# Reverse-engineered seed · energy curve as a %d-term Fourier series over %.1f beats" % (terms, beats),
             "u = clamp(t / %.4f, 0, 1)" % max(1e-6, beats), "v = %.6f" % coef[0]]
    for k in range(1, terms + 1):
        a, b = coef[2 * k - 1], coef[2 * k]
        if abs(a) + abs(b) > 1e-4:
            lines.append("v += %.6f * cos(tau * %d * u) + %.6f * sin(tau * %d * u)" % (a, k, b, k))
    lines.append("return 220 * (1 + 0.25 * tanh(v)) + 60 * isn(t * MEUM)")
    return "\n".join(lines)


def to_project(app, path, out_dir=None):
    a = analyse(path)
    import project_blueprint as pb
    energy_mean = float(np.clip(np.mean(a["energy"]) / (np.max(a["energy"]) or 1.0) * 2.0, 0, 1))
    character = "Rhythmic" if a["onset_density"] > 0.08 else ("Textural" if a["brightness"] > 0.45 else "Tonal")
    seed = fourier_seed(a["energy"], a["seconds"], a["bpm"])
    cfg = pb.build(character=character, energy=energy_mean, tempo=a["bpm"], base_hz=a["base_hz"],
                   bars=max(4, int(round(a["seconds"] * a["bpm"] / 240.0))), instruments=8, seed=seed, app=app)
    cfg["post"]["fractal"] = round(0.3 * a["brightness"], 3)
    rep = pb.apply(app, cfg)
    import groovebox_paths as gp
    name = "RE " + os.path.splitext(os.path.basename(path))[0]
    dst = gp.default_project_path(name) if out_dir is None else os.path.join(out_dir, name + ".MCC")
    app._current_project_path = dst
    app._project_uid = None
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    app._atomic_write_document(dst, app._project_snapshot())     # R32.8: written before we report it
    return dst, a, rep


def to_game(app, path, out_dir=None):
    a = analyse(path)
    import videogame_engine as vg
    ident = vg.classify_from_composition(float(a["signature"]), bpm=a["bpm"], seq_length=16,
                                         playlist_rows=max(4, int(a["seconds"] // 4)), n_instruments=8)
    import groovebox_paths as gp
    out = out_dir or os.path.join(gp.games_dir(getattr(app, "_current_project_path", None)), "from-" + os.path.splitext(os.path.basename(path))[0])
    os.makedirs(out, exist_ok=True)
    vg.export_game_files(ident, out, {"seed": float(a["signature"]), "bpm": a["bpm"], "source": os.path.basename(path)})
    return out


def _game_identity(path):
    """R32.8: identity of an exported game — game_<hash>.json (exporter output), else the IDENTITY in the .py."""
    import glob, re as _re
    d = path if os.path.isdir(path) else os.path.dirname(path)
    for jp in sorted(glob.glob(os.path.join(d, "game_*.json"))) + [os.path.join(d, "game.json")]:
        try:
            with open(jp, encoding="utf-8") as f:
                j = json.load(f)
            ident = j.get("identity", j) if isinstance(j, dict) else {}
            if isinstance(ident, dict) and ident:
                return ident
        except Exception:
            pass
    pys = [path] if path.endswith(".py") else sorted(glob.glob(os.path.join(d, "game_*.py"))) + [os.path.join(d, "game.py")]
    for py in pys:
        try:
            src = open(py, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        m = _re.search(r"IDENTITY\s*=\s*(\{.*?\})\n", src, _re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        m = _re.search(r"__IDENTITY_JSON__\s*=\s*(['\"]{1,3})(.*?)\1", src, _re.S)
        if m:
            try:
                return json.loads(m.group(2))
            except Exception:
                pass
    return {}


def game_to_seed(path):
    ident = _game_identity(path)
    seed = float(ident.get("seed", 1.0)); bpm = float(ident.get("bpm", 120.0) or 120.0)
    return ("# From game '%s' (%s · %s)\nphase = t * MEUM\nreturn %.4f + 120 * isn(phase * %.4f) + 40 * ics(t * PHI)"
            % (ident.get("title", "?"), ident.get("genre", "?"), ident.get("mood", "?"), seed % 1000, 1 + (seed % 7) / 7.0), bpm)


def convert(app, src, target, out=None):
    k = kind_of(src)
    base = os.path.splitext(out or src)[0]
    try:
        import signal_converters as _sc
        if target == "seed" or _sc.kind_of(src) == "seed":     # R32.8 seed hub
            return _sc.convert(app, src, target, base)
    except ImportError:
        pass
    if k == "game":                       # R32.8: game → seed file → anything (the seed hub)
        seed, bpm = game_to_seed(src)
        sp = base + ".seed"
        with open(sp, "w", encoding="utf-8") as f:
            f.write("# Groovebox seed program · from game %s · bpm %.3f\n%s\n" % (os.path.basename(src), bpm, seed))
        if target == "seed":
            return sp
        import signal_converters as _sc
        return _sc.convert(app, sp, target, base)
    if target in ("project", "game") and k not in ("sound", "image", "video"):
        import signal_converters as _sc     # analysis needs a signal: route midi/text/data/seed/project via sound
        snd = _sc.convert(app, src, "sound", base)
        return to_project(app, snd)[0] if target == "project" else to_game(app, snd)
    if target == "project":
        return to_project(app, src)[0]
    if target == "game":
        return to_game(app, src)
    table = {("sound", "image"): lambda: sound_to_image(src, base + ".spectrogram.png"),
             ("image", "sound"): lambda: image_to_sound(src, base + ".sonified.wav"),
             ("sound", "video"): lambda: sound_to_video(src, base + ".video.mp4"),
             ("video", "sound"): lambda: video_to_sound(src, base + ".audio.wav"),
             ("image", "video"): lambda: image_to_video(src, base + ".zoom.mp4"),
             ("video", "image"): lambda: video_to_image(src, base + ".sheet.png"),
             ("sound", "sound"): lambda: _write_audio(base + ".copy.wav", *_read_audio(src)[::-1][::-1]) if False else shutil.copy2(src, base + ".copy" + os.path.splitext(src)[1]),
             ("image", "image"): lambda: shutil.copy2(src, base + ".copy" + os.path.splitext(src)[1]),
             ("video", "video"): lambda: shutil.copy2(src, base + ".copy" + os.path.splitext(src)[1])}
    fn = table.get((k, target))
    if fn is None:
        import signal_converters as _sc            # R32.8: complete any → any matrix
        return _sc.convert(app, src, target, base)
    return fn()


def open_in_editor(app, path):
    """R32.8: the B side of A → B — every result kind opens in the editor that edits it."""
    import signal_converters as _sc
    k = _sc.kind_of(path) or kind_of(path)
    if k == "image":
        w = __import__("image_editor").open_window(app)
        for m in ("open_path", "load_path", "open_image"):
            if hasattr(w, m):
                getattr(w, m)(path); break
        return w
    if k in ("video", "sound"):
        w = app._r32_open_clip_editor(); w._add_media_paths([path]); return w
    if k == "project":
        return app.open_project_path(path, show_message=False)
    if k == "game":
        return __import__("game_editor").open_window(app)
    import media_editors as _me                    # R32.8: in-app editors for the remaining kinds
    if k == "midi":
        return _me.open_midi(app, path)
    if k in ("text", "data", "seed"):
        return _me.open_text(app, path)
    raise ValueError("no editor for %s" % k)


def open_window(app, path=None):
    _old = getattr(app, "_transmuter_window", None)          # R32.8 sweep: one window, not a new one per click
    try:
        if _old is not None:
            _old.show(); _old.raise_(); _old.activateWindow(); return _old
    except RuntimeError:
        pass
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QComboBox, QLabel, QFileDialog, QTextEdit
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🔁 Media Transmuter · sound · image · video · game · → project"); w.resize(760, 420)
    lay = QVBoxLayout(w)
    row = QHBoxLayout(); src = QLineEdit(path or ""); b = QPushButton("Choose…")
    b.clicked.connect(lambda: src.setText(QFileDialog.getOpenFileName(w, "Source", "", "Media (*.wav *.flac *.mp3 *.ogg *.opus *.m4a *.png *.jpg *.jpeg *.webp *.mp4 *.mkv *.webm *.mov *.py *.mid *.midi *.txt *.md *.csv *.tsv *.json *.seed *.MCC);;All (*)")[0] or src.text()))
    row.addWidget(QLabel("From")); row.addWidget(src, 1); row.addWidget(b); lay.addLayout(row)
    row = QHBoxLayout(); tgt = QComboBox(); tgt.addItems(["seed (the complete description)", "sound", "image", "video", "midi", "text", "data", "game", "project (reverse engineer)"])
    go = QPushButton("Transmute"); row.addWidget(QLabel("To")); row.addWidget(tgt, 1); row.addWidget(go)
    bb = QPushButton("Batch folder…"); bb.setToolTip("Convert every file in a folder to the chosen kind.")
    bd = QPushButton("Difference A − B…"); bd.setToolTip("Pick B: saves A − B as media of A's kind (sound: sample difference · "
                                                       "image/video: signed per-pixel difference · seeds render canonically first).")
    be = QPushButton("Open result in editor"); be.setToolTip("Open the last result in the editor for its kind.")
    bm = QPushButton("Project → MIDI…"); bm.setToolTip("Export this project's instruments (steps + pitches over every row) to .mid, one channel each.")
    bi = QPushButton("MIDI → this project (morph)…"); bi.setToolTip("Import a .mid: notes grouped by register go to matching instruments, quantised to 16ths.")
    row.addWidget(bb); row.addWidget(bd); row.addWidget(be); row.addWidget(bm); row.addWidget(bi); lay.addLayout(row)

    def do_midi_out():
        out, _ = QFileDialog.getSaveFileName(w, "Export MIDI", "project.mid", "MIDI (*.mid)")
        if out:
            try:
                import r32_finish as _rf
                last["path"] = _rf.project_to_midi(app, out); log.append("✓ project → %s" % out)
            except Exception as exc:
                log.append("✗ MIDI export: %s" % exc)

    def do_midi_in():
        p_, _ = QFileDialog.getOpenFileName(w, "Import MIDI", "", "MIDI (*.mid *.midi)")
        if p_:
            try:
                import r32_finish as _rf
                log.append("✓ %s" % _rf.midi_to_project(app, p_))
            except Exception as exc:
                log.append("✗ MIDI import: %s" % exc)
    bm.clicked.connect(do_midi_out); bi.clicked.connect(do_midi_in)
    # R32.9 SEED LIBRARY: favourite seed programs, kept with the user's Groovebox
    row2 = QHBoxLayout(); lib = QComboBox(); lib.setMinimumWidth(220)
    b_keep = QPushButton("★ Keep current seed"); b_use = QPushButton("Use"); b_del = QPushButton("Delete")

    def _lib_dir():
        import groovebox_paths as _gp
        d = os.path.join(_gp.base_dir(), "seed_library"); os.makedirs(d, exist_ok=True); return d

    def _lib_fill():
        lib.clear(); lib.addItems(sorted(os.path.splitext(f)[0] for f in os.listdir(_lib_dir()) if f.endswith(".seed")))

    def _keep():
        from PyQt6.QtWidgets import QInputDialog
        n_, ok = QInputDialog.getText(w, "Keep seed", "Name:")
        if ok and n_.strip():
            safe = "".join(c for c in n_.strip() if c.isalnum() or c in " -_.")[:60] or "seed"
            bpm = float(app.spin_bpm.value()) if hasattr(app, "spin_bpm") else 120.0
            with open(os.path.join(_lib_dir(), safe + ".seed"), "w", encoding="utf-8") as f:
                f.write("# Groovebox seed program · library · bpm %.3f\n%s\n" % (bpm, app._seed_text()))
            _lib_fill(); lib.setCurrentText(safe); log.append("★ kept seed '%s'" % safe)

    def _use():
        if lib.currentText():
            p_ = os.path.join(_lib_dir(), lib.currentText() + ".seed")
            import signal_converters as _sc
            seed, bpm = _sc.read_seed(p_); app.input_seed_val.setPlainText(seed)
            if bpm and hasattr(app, "spin_bpm"):
                app.spin_bpm.setValue(bpm)
            log.append("seed '%s' loaded" % lib.currentText())

    def _del():
        if lib.currentText():
            try:
                os.remove(os.path.join(_lib_dir(), lib.currentText() + ".seed"))
            except OSError:
                pass
            _lib_fill()
    b_keep.clicked.connect(_keep); b_use.clicked.connect(_use); b_del.clicked.connect(_del)
    for x in (QLabel("Seed library"), lib, b_use, b_keep, b_del):
        row2.addWidget(x)
    lay.addLayout(row2)
    try:
        _lib_fill()
    except Exception:
        pass
    last = {"path": None}
    log = QTextEdit(); log.setReadOnly(True); lay.addWidget(log)

    def run_diff():
        a = src.text().strip()
        if not os.path.isfile(a):
            log.append("choose A (the From file) first"); return
        b, _ = QFileDialog.getOpenFileName(w, "B (subtracted from A)", os.path.dirname(a))
        if b:
            try:
                import signal_converters as _sc
                r = _sc.difference(app, a, b); last["path"] = r; log.append("✓ A − B → %s" % r)
            except Exception as exc:
                log.append("✗ difference: %s" % exc)
    bd.clicked.connect(run_diff)

    def open_editor():
        p = last["path"] or src.text().strip()
        if p and os.path.exists(p):
            try:
                open_in_editor(app, p); log.append("opened %s" % os.path.basename(p))
            except Exception as exc:
                log.append("✗ open: %s" % exc)
    be.clicked.connect(open_editor)

    def run_batch():
        d = QFileDialog.getExistingDirectory(w, "Folder to convert")
        if d:
            import signal_converters as _sc
            _sc.batch(app, d, tgt.currentText().split(" ")[0], log.append)
    bb.clicked.connect(run_batch)

    def run():
        p = src.text().strip()
        if not os.path.exists(p):
            log.append("choose a source"); return
        t = tgt.currentText().split(" ")[0]
        try:
            if t == "project":
                dst, a, rep = to_project(app, p)
                log.append("✓ project %s\n  tempo %.1f BPM · base %.1f Hz · brightness %.2f · onsets %.3f · %.1f s\n  %s" % (
                    dst, a["bpm"], a["base_hz"], a["brightness"], a["onset_density"], a["seconds"], " · ".join(rep)))
            else:
                r = convert(app, p, t); last["path"] = r if isinstance(r, str) else None
                log.append("✓ %s" % r)
        except Exception as exc:
            log.append("✗ %s" % exc)
    go.clicked.connect(run)
    app._transmuter_window = w; w.show(); return w
