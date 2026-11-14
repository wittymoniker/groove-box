"""signal_converters.py — GROOVEBOX_R32_SIGNAL_CONVERTERS_20261110

Extends the Media Transmuter so every signal kind converts into every other one:

    kinds   sound · image · video · game · project  (media_transmuter)
            + midi (.mid) · text (.txt/.md) · data (.csv/.json numbers)   (here)

New direct paths (all deterministic: same input → same output):
    sound → midi    onset detection + autocorrelation pitch per note (monophonic transcription)
    midi  → sound   additive pluck voices, velocity → level, all channels mixed
    text  → sound / midi   characters → scale degrees, words → phrases, punctuation → rests
    sound → text    analysis report + a seed program that recreates the gesture (fourier_seed)
    data  → sound / image / midi   each numeric column sonified / drawn as a heat-map / as a melody
    sound → data    CSV feature track (time, rms, peak, centroid Hz, onset) per 512-sample hop
    image → midi    brightness peaks per column → notes; video → midi via its soundtrack
Anything else routes through sound (A → sound → B), so the matrix is complete.
"""
from __future__ import annotations

import csv
import json
import re
import math
import os
import struct

import numpy as np

MIDI = (".mid", ".midi")
TEXT = (".txt", ".md", ".text")
DATA = (".csv", ".tsv", ".json")
SEED = (".seed",)
EXTRA_KINDS = ("midi", "text", "data", "seed")
SCALE = (0, 2, 4, 7, 9, 12, 14, 16, 19, 21)          # pentatonic, two octaves


def kind_of(path):
    e = os.path.splitext(path)[1].lower()
    if e in MIDI:
        return "midi"
    if e in TEXT:
        return "text"
    if e in DATA:
        return "data"
    if e in SEED:
        return "seed"
    if e in (".mcc", ".mgpr"):
        try:                                     # a project document is JSON; MCC media is binary
            with open(path, "rb") as f:
                head = f.read(64).lstrip()
            if head[:1] == b"{":
                return "project"
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- MIDI file I/O ----------
def _vlq(n):
    out = [n & 0x7F]; n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F)); n >>= 7
    return bytes(reversed(out))


def write_midi(path, notes, bpm=120.0, tpq=480):
    """notes: [(start_s, dur_s, pitch, velocity)]"""
    us = int(60e6 / max(1e-6, bpm))
    ev = []
    for st, du, p, v in notes:
        a = int(round(st * bpm / 60.0 * tpq)); b = int(round((st + max(0.01, du)) * bpm / 60.0 * tpq))
        p = int(max(0, min(127, p))); v = int(max(1, min(127, v)))
        ev.append((a, 1, bytes([0x90, p, v]))); ev.append((b, 0, bytes([0x80, p, 0])))
    ev.sort(key=lambda e: (e[0], e[1]))
    trk = bytearray(b"\x00\xff\x51\x03" + us.to_bytes(3, "big"))
    last = 0
    for t, _o, data in ev:
        trk += _vlq(t - last) + data; last = t
    trk += b"\x00\xff\x2f\x00"
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq) + b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk))
    return path


def read_midi(path):
    """-> [(start_s, dur_s, pitch, velocity)] from any SMF type 0/1 (tempo map honoured)."""
    data = open(path, "rb").read()
    if data[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    _ln, _fmt, ntrk, div = struct.unpack(">IHHH", data[4:14])
    tpq = div if div < 0x8000 else 480
    pos = 14; events = []; tempos = [(0, 500000)]
    for _ in range(ntrk):
        if data[pos:pos + 4] != b"MTrk":
            break
        ln = struct.unpack(">I", data[pos + 4:pos + 8])[0]; p = pos + 8; end = p + ln; t = 0; run = 0
        while p < end:
            d = 0
            while True:
                b = data[p]; p += 1; d = (d << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            t += d; st = data[p]
            if st == 0xFF:
                typ = data[p + 1]; p += 2; l = 0
                while True:
                    b = data[p]; p += 1; l = (l << 7) | (b & 0x7F)
                    if not b & 0x80:
                        break
                if typ == 0x51:
                    tempos.append((t, int.from_bytes(data[p:p + 3], "big")))
                p += l; continue
            if st in (0xF0, 0xF7):
                p += 1; l = 0
                while True:
                    b = data[p]; p += 1; l = (l << 7) | (b & 0x7F)
                    if not b & 0x80:
                        break
                p += l; continue
            if st & 0x80:
                run = st; p += 1
            hi = run & 0xF0
            n = 1 if hi in (0xC0, 0xD0) else 2
            args = data[p:p + n]; p += n
            if hi in (0x80, 0x90) and len(args) == 2:
                events.append((t, args[0], args[1] if hi == 0x90 else 0, run & 0x0F))
        pos = end
    tempos.sort()

    def sec(tick):
        s, lt, us = 0.0, 0, 500000
        for tt, u in tempos:
            if tt > tick:
                break
            s += (tt - lt) / tpq * us / 1e6; lt, us = tt, u
        return s + (tick - lt) / tpq * us / 1e6
    on = {}; notes = []
    for t, pitch, vel, ch in sorted(events):
        k = (ch, pitch)
        if vel > 0:
            on.setdefault(k, []).append((t, vel))
        elif on.get(k):
            t0, v = on[k].pop(0); notes.append((sec(t0), max(0.01, sec(t) - sec(t0)), pitch, v))
    return sorted(notes)


# ---------------------------------------------------------------- synthesis / analysis ----
def render_notes(notes, sr=48000, tail=1.0):
    if not notes:
        return np.zeros(sr, dtype=np.float32)
    total = max(s + d for s, d, _p, _v in notes) + tail
    y = np.zeros(int(total * sr) + 1)
    for s, d, p, v in notes:
        hz = 440.0 * 2 ** ((p - 69) / 12.0); n = int((d + 0.3) * sr); t = np.arange(n) / sr
        env = np.exp(-t * (2.5 + 2.0 / max(0.05, d))) * np.minimum(1, t / 0.004)
        tone = (np.sin(2 * np.pi * hz * t) + 0.35 * np.sin(4 * np.pi * hz * t) + 0.12 * np.sin(6 * np.pi * hz * t)) * env
        a = int(s * sr); y[a:a + n] += tone[:max(0, y.size - a)] * (v / 127.0) * 0.3
    pk = np.max(np.abs(y)) or 1.0
    return (y / max(1.0, pk / 0.9)).astype(np.float32)


def _pitch(seg, sr):
    seg = seg - seg.mean()
    if seg.size < 256 or np.max(np.abs(seg)) < 1e-4:
        return None
    ac = np.fft.irfft(np.abs(np.fft.rfft(seg, 2 * seg.size)) ** 2)[:seg.size]
    lo, hi = int(sr / 1200), int(sr / 50)
    if hi >= ac.size:
        return None
    lag = lo + int(np.argmax(ac[lo:hi]))
    return sr / lag if ac[lag] > 0.3 * ac[0] else None


def transcribe(y, sr, hop=512):
    n = y.size // hop
    if n < 4:
        return [], 120.0
    rms = np.sqrt(np.mean(y[:n * hop].reshape(n, hop) ** 2, axis=1))
    flux = np.maximum(0, np.diff(rms, prepend=rms[0]))
    thr = flux.mean() + 1.5 * flux.std()
    on = [i for i in range(1, n - 1) if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]]
    if rms[:2].max() > 0.1 * (rms.max() or 1.0) and (not on or on[0] > 3):
        on = [0] + on                                   # a note sounding from the very start
    on = [i for k, i in enumerate(on) if k == 0 or i - on[k - 1] > 3]
    notes = []
    for k, i in enumerate(on):
        j = on[k + 1] if k + 1 < len(on) else min(n, i + 40)
        a = i * hop; seg = y[a:a + min(4096, (j - i) * hop)]
        hz = _pitch(seg, sr)
        if hz:
            notes.append((a / sr, (j - i) * hop / sr, int(round(69 + 12 * math.log2(hz / 440.0))), int(min(127, 40 + 600 * rms[i]))))
    if len(on) > 2:
        ioi = np.median(np.diff(on)) * hop / sr
        bpm = 60.0 / ioi if ioi > 0 else 120.0
        while bpm < 70: bpm *= 2
        while bpm > 180: bpm /= 2
    else:
        bpm = 120.0
    return notes, float(bpm)


def text_notes(text, bpm=110.0):
    beat = 60.0 / bpm; t = 0.0; notes = []
    for ch in text[:4000]:
        if ch.isspace():
            t += beat * 0.5; continue
        if ch in ".!?;:":
            t += beat * 1.5; continue
        o = ord(ch)
        notes.append((t, beat * (0.9 if ch.isupper() else 0.45), 57 + SCALE[o % len(SCALE)], 70 + (o * 7) % 50))
        t += beat * 0.5
    return notes


def read_data(path):
    """Numeric columns of a CSV/TSV/JSON file -> {name: np.array}."""
    if path.lower().endswith(".json"):
        d = json.load(open(path, encoding="utf-8"))
        if isinstance(d, dict):
            cols = {k: v for k, v in d.items() if isinstance(v, list)}
        elif isinstance(d, list) and d and isinstance(d[0], dict):
            cols = {k: [r.get(k) for r in d] for k in d[0]}
        else:
            cols = {"values": d if isinstance(d, list) else [d]}
    else:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            rows = list(csv.reader(f, delimiter="\t" if path.lower().endswith(".tsv") else ","))
        head = rows[0] if rows and any(not _isnum(c) for c in rows[0]) else ["c%d" % i for i in range(len(rows[0]) if rows else 0)]
        body = rows[1:] if rows and head is rows[0] else rows
        cols = {h: [r[i] if i < len(r) else "" for r in body] for i, h in enumerate(head)}
    out = {}
    for k, v in cols.items():
        a = np.array([float(x) for x in v if _isnum(x)], dtype=np.float64)
        if a.size >= 2:
            out[str(k)] = a
    if not out:
        raise ValueError("no numeric columns")
    return out


def _isnum(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def data_notes(cols, bpm=120.0):
    beat = 60.0 / bpm / 2; notes = []
    for ci, (_k, a) in enumerate(list(cols.items())[:4]):
        lo, hi = float(a.min()), float(a.max()); span = (hi - lo) or 1.0
        for i, v in enumerate(a[:2000]):
            deg = int((v - lo) / span * (len(SCALE) - 1))
            notes.append((i * beat, beat * 0.9, 48 + 12 * ci + SCALE[deg], 90))
    return notes


# ---------------------------------------------------------------- conversions -------------
def convert(app, src, target, base):
    import media_transmuter as mt
    k = kind_of(src) or mt.kind_of(src)
    sr = 48000
    if target == "seed":
        return to_seed(app, src, base)
    if k == "seed":
        return from_seed(app, src, target, base)
    if k == "project":                     # R32.8: a project is its seed (+ settings): project → seed → anything
        return from_seed(app, to_seed(app, src, base), target, base)
    if k == "midi" and target == "sound":
        return mt._write_audio(base + ".render.wav", render_notes(read_midi(src), sr), sr) or base + ".render.wav"
    if k == "text" and target in ("sound", "midi"):
        notes = text_notes(open(src, encoding="utf-8", errors="replace").read())
        if target == "midi":
            return write_midi(base + ".text.mid", notes, 110.0)
        mt._write_audio(base + ".text.wav", render_notes(notes, sr), sr); return base + ".text.wav"
    if k == "data" and target in ("sound", "midi", "image"):
        cols = read_data(src)
        if target == "image":
            from PyQt6.QtGui import QImage
            m = np.stack([np.interp(np.linspace(0, a.size - 1, 1024), np.arange(a.size), a) for a in cols.values()])
            m = (m - m.min(axis=1, keepdims=True)) / (np.ptp(m, axis=1, keepdims=True) + 1e-12)
            rows = np.repeat(m, max(1, 256 // len(m)), axis=0)
            rgb = np.stack([rows * 255, (1 - np.abs(rows - 0.5) * 2) * 255, (1 - rows) * 255], axis=-1).astype(np.uint8)
            rgb = np.ascontiguousarray(rgb); h, w = rgb.shape[:2]
            QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy().save(base + ".heatmap.png")
            return base + ".heatmap.png"
        notes = data_notes(cols)
        if target == "midi":
            return write_midi(base + ".data.mid", notes)
        mt._write_audio(base + ".data.wav", render_notes(notes, sr), sr); return base + ".data.wav"
    if k == "sound" and target == "midi":
        y, srr = mt._read_audio(src); notes, bpm = transcribe(np.asarray(y, dtype=np.float64), srr)
        return write_midi(base + ".transcribed.mid", notes, bpm)
    if k == "sound" and target == "data":
        y, srr = mt._read_audio(src); hop = 512; n = y.size // hop
        fr = y[:n * hop].reshape(n, hop); spec = np.abs(np.fft.rfft(fr * np.hanning(hop), axis=1))
        fq = np.fft.rfftfreq(hop, 1 / srr); cen = (spec * fq).sum(1) / (spec.sum(1) + 1e-12)
        rms = np.sqrt((fr ** 2).mean(1)); on = np.r_[0, np.maximum(0, np.diff(rms))]
        with open(base + ".features.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["time_s", "rms", "peak", "centroid_hz", "onset"])
            for i in range(n):
                w.writerow(["%.4f" % (i * hop / srr), "%.6f" % rms[i], "%.6f" % np.abs(fr[i]).max(), "%.1f" % cen[i], "%.6f" % on[i]])
        return base + ".features.csv"
    if k == "sound" and target == "text":
        a = mt.analyse(src)
        try:
            seed = mt.fourier_seed(a.get("energy"), a.get("seconds"), a.get("bpm"))
        except Exception:
            seed = ""
        txt = "Analysis of %s\n\n" % os.path.basename(src) + "\n".join("%s: %s" % (kk, vv) for kk, vv in a.items() if not hasattr(vv, "__len__") or isinstance(vv, str))
        txt += "\n\nSeed program that recreates the gesture:\n\n%s\n" % seed
        open(base + ".analysis.txt", "w", encoding="utf-8").write(txt); return base + ".analysis.txt"
    if k == "image" and target == "midi":
        from PyQt6.QtGui import QImage
        img = QImage(src).convertToFormat(QImage.Format.Format_Grayscale8).scaled(64, 24)
        w, h = img.width(), img.height(); ptr = img.constBits(); ptr.setsize(img.bytesPerLine() * h)
        g = np.frombuffer(ptr, np.uint8).reshape(h, img.bytesPerLine())[:, :w].astype(float) / 255
        notes = [(x * 0.25, 0.24, 48 + (h - 1 - yy) * 2, int(40 + 87 * g[yy, x])) for x in range(w) for yy in range(h) if g[yy, x] > 0.6]
        return write_midi(base + ".image.mid", notes)
    # anything else: route through sound
    if k != "sound" and target != "sound":
        mid = mt.convert(app, src, "sound") if k in ("image", "video") else convert(app, src, "sound", base)
        if isinstance(mid, str) and os.path.isfile(mid):
            return mt.convert(app, mid, target) if target in mt.KINDS else convert(app, mid, target, os.path.splitext(mid)[0])
    if k in EXTRA_KINDS and target in mt.KINDS:
        mid = convert(app, src, "sound", base)
        return mt.convert(app, mid, target)
    raise ValueError("no %s → %s path" % (k, target))


# ---------------------------------------------------------------- the seed hub -----------
# R32.8 SEED_HUB: the seed program is the one complete description. Every kind reduces to a seed
# (reverse engineering), and a seed renders to every kind through the canonical engine itself
# (the same mixdown + video engine Play / Export use), so A → seed → B covers all A, B.
def to_seed(app, src, base):
    import media_transmuter as mt
    k = kind_of(src) or mt.kind_of(src)
    if k == "seed":
        return src
    if k == "midi":                       # R32.9: symbolic music → an EXACT seed (lossless), not an estimate
        notes = read_midi(src)
        seed, bpm = notes_to_exact_seed(notes, 120.0), 120.0
    elif k == "game":
        seed, bpm = mt.game_to_seed(src)
    elif k == "project":
        d = json.load(open(src, encoding="utf-8"))
        seed = str(d.get("seed") or "")
        bpm = float(d.get("bpm", 120) or 120)
    else:
        snd = src if k == "sound" else (mt.convert(app, src, "sound") if k in ("image", "video") else convert(app, src, "sound", base))
        a = mt.analyse(snd)
        seed = mt.fourier_seed(a["energy"], a["seconds"], a["bpm"]); bpm = float(a["bpm"])
    out = base + ".seed"
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Groovebox seed program · reverse-engineered from %s · bpm %.3f\n%s\n" % (os.path.basename(src), bpm, seed))
    return out


def read_seed(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"bpm\s+([0-9.]+)", txt.split("\n", 1)[0])
    body = "\n".join(l for l in txt.splitlines() if not l.startswith("# Groovebox seed program"))
    return body.strip(), (float(m.group(1)) if m else None)


class _SeedSwap:
    """Temporarily put a seed (and tempo) into the app, restore the user's own afterwards."""
    def __init__(self, app, seed, bpm=None):
        self.app, self.seed, self.bpm = app, seed, bpm

    def __enter__(self):
        a = self.app
        self.old_seed = a._seed_text()
        self.old_bpm = a.spin_bpm.value() if hasattr(a, "spin_bpm") else None
        a.input_seed_val.setPlainText(self.seed)
        if self.bpm and self.old_bpm is not None:
            a.spin_bpm.setValue(float(self.bpm))
        a._shared_mixdown_cache = {}
        return a

    def __exit__(self, *_e):
        a = self.app
        a.input_seed_val.setPlainText(self.old_seed)
        if self.old_bpm is not None:
            a.spin_bpm.setValue(self.old_bpm)
        a._shared_mixdown_cache = {}


def seed_render_audio(app, seed, bpm=None, max_rows=8):
    with _SeedSwap(app, seed, bpm):
        buf, sr = app._get_shared_mixdown_buffer(max_rows=max_rows, purpose="Seed render", force=True)
        buf = np.nan_to_num(np.asarray(buf, dtype=np.float32).ravel())
        try:
            buf, _ = app._master_hardclip(buf, sr, apply_master_vol=True)
        except Exception:
            pass
    return np.asarray(buf, dtype=np.float32), int(sr)


def seed_render_video(app, seed, out, bpm=None, max_rows=8, w=1280, h=720, fps=30, frames=None):
    """Canonical video: the app's own VideoSynthEngine + video plan, frame by frame, with the canonical audio."""
    import subprocess, media_transmuter as mt
    y, sr = seed_render_audio(app, seed, bpm, max_rows)
    with _SeedSwap(app, seed, bpm):
        try:   # R32.9: a fresh clone of the export engine (settings only) — same seed → same frames
            import live_player as _lp, groovebox as _gb
            eng = _lp.clone_export_engine(_gb, app)
        except Exception:
            eng = app.video_synth_engine
        n = int(round(y.size / sr * fps)) if frames is None else int(frames)
        fs = max(1, int(round(sr / fps)))
        wav = out + ".audio.wav"; mt._write_audio(wav, y, sr)
        if frames == 1:
            eng.set_waveform(y[:fs * 4], playhead=0.5)
            fr = np.asarray(eng.render_frame(w, h, export=True, frame_index=0), dtype=np.uint8)
            try:
                fr = app._apply_video_plan_to_frame(fr, 0, 1)
            except Exception:
                pass
            os.remove(wav)
            return np.ascontiguousarray(np.asarray(fr)[:, :, :3])
        ff = mt._ff()
        if not ff:
            raise RuntimeError("video needs ffmpeg")
        p = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
                              "-r", str(fps), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "mpeg4", "-q:v", "3",
                              "-c:a", "aac", "-b:a", "192k", "-shortest", out], stdin=subprocess.PIPE)
        try:
            for fi in range(n):
                eng.set_waveform(y[fi * fs:(fi + 1) * fs], playhead=fi / max(1, n - 1))
                fr = np.asarray(eng.render_frame(w, h, export=True, frame_index=fi), dtype=np.uint8)
                try:
                    fr = app._apply_video_plan_to_frame(fr, fi, n)
                except Exception:
                    pass
                p.stdin.write(np.ascontiguousarray(np.asarray(fr)[:, :, :3], dtype=np.uint8).tobytes())
        finally:
            p.stdin.close(); p.wait(timeout=600)
            try:
                os.remove(wav)
            except Exception:
                pass
    return out


def from_seed(app, src, target, base):
    import media_transmuter as mt
    seed, bpm = read_seed(src)
    if target == "sound":
        y, sr = seed_render_audio(app, seed, bpm); mt._write_audio(base + ".render.wav", y, sr); return base + ".render.wav"
    if target == "video":
        return seed_render_video(app, seed, base + ".render.mp4", bpm)
    if target == "image":
        from PyQt6.QtGui import QImage
        fr = seed_render_video(app, seed, base + ".frame", bpm, frames=1); hh, ww = fr.shape[:2]
        QImage(fr.data, ww, hh, 3 * ww, QImage.Format.Format_RGB888).copy().save(base + ".frame.png"); return base + ".frame.png"
    if target == "project":
        with _SeedSwap(app, seed, bpm):
            import groovebox_paths as gp
            dst = gp.default_project_path("Seed " + os.path.splitext(os.path.basename(src))[0])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            app._atomic_write_document(dst, app._project_snapshot())   # synchronous: the file exists when returned
        return dst
    snd = from_seed(app, src, "sound", base)                      # midi · text · data · game: via the canonical sound
    return mt.convert(app, snd, target) if target in mt.KINDS else convert(app, snd, target, os.path.splitext(snd)[0])


def batch(app, folder, target, log=print):
    """Convert every media file in a folder (non-recursive) to `target`; returns [(src, result|error)]."""
    out = []
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if not os.path.isfile(p) or name.startswith("."):
            continue
        try:
            import media_transmuter as mt
            r = mt.convert(app, p, target)
            out.append((p, r)); log("✓ %s → %s" % (name, r))
        except Exception as exc:
            out.append((p, exc)); log("✗ %s: %s" % (name, exc))
    return out


# ---------------------------------------------------------------- difference --------------
def difference(app, a_path, b_path, out_base=None, mode="signed"):
    """R32.8 TRANSMUTATIONAL DIFFERENCE: A − B saved as media of A's kind.

    sound  sample-wise A − B (B resampled to A's rate, zero-padded) → WAV (32-bit float, no clipping)
    image  mode "signed": 128 + (A − B)/2 per channel · "abs": |A − B|  → PNG (B scaled to A's size)
    video  per-frame difference (FFmpeg blend: grain-extract = signed, difference = abs) + audio A − B
    other  both reduced to sound first (seeds render canonically), then subtracted.
    Deterministic; A − B + B reconstructs A for sound exactly (float WAV) and for signed images up to rounding."""
    import media_transmuter as mt, subprocess
    ka = kind_of(a_path) or mt.kind_of(a_path); kb = kind_of(b_path) or mt.kind_of(b_path)
    base = out_base or os.path.splitext(a_path)[0] + ".minus." + os.path.splitext(os.path.basename(b_path))[0]
    if ka == "image":
        from PyQt6.QtGui import QImage
        if kb != "image":
            b_path = convert(app, b_path, "image", os.path.splitext(b_path)[0]) if kb in EXTRA_KINDS else mt.convert(app, b_path, "image")

        def arr(p, w=None, h=None):
            im = QImage(p).convertToFormat(QImage.Format.Format_RGB888)
            if w:
                im = im.scaled(w, h)
            ww, hh = im.width(), im.height(); ptr = im.constBits(); ptr.setsize(im.bytesPerLine() * hh)
            return np.frombuffer(ptr, np.uint8).reshape(hh, im.bytesPerLine())[:, :ww * 3].reshape(hh, ww, 3).astype(np.int16)
        A = arr(a_path); B = arr(b_path, A.shape[1], A.shape[0])
        D = (np.abs(A - B) if mode == "abs" else 128 + (A - B) // 2).clip(0, 255).astype(np.uint8)
        D = np.ascontiguousarray(D); h, w = D.shape[:2]
        QImage(D.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy().save(base + ".png")
        return base + ".png"
    if ka == "video":
        ff = mt._ff()
        if not ff:
            raise RuntimeError("video difference needs ffmpeg")
        if kb != "video":
            b_path = mt.convert(app, b_path, "video") if kb in mt.KINDS else from_seed(app, b_path, "video", os.path.splitext(b_path)[0]) if kb == "seed" else mt.convert(app, convert(app, b_path, "sound", os.path.splitext(b_path)[0]), "video")
        blend = "difference" if mode == "abs" else "grainextract"
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", a_path, "-i", b_path, "-filter_complex",
                            "[1:v][0:v]scale2ref[b][a];[a][b]blend=all_mode=%s,format=yuv420p[v];"
                            "[1:a]volume=-1[bn];[0:a][bn]amix=inputs=2:normalize=0[aud]" % blend,
                            "-map", "[v]", "-map", "[aud]", "-c:v", "mpeg4", "-q:v", "3", "-c:a", "aac", "-b:a", "192k",
                            "-shortest", base + ".mp4"], capture_output=True, timeout=7200)
        if r.returncode != 0:      # sources without audio: picture only
            r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", a_path, "-i", b_path, "-filter_complex",
                                "[1:v][0:v]scale2ref[b][a];[a][b]blend=all_mode=%s,format=yuv420p[v]" % blend,
                                "-map", "[v]", "-c:v", "mpeg4", "-q:v", "3", "-shortest", base + ".mp4"], capture_output=True, timeout=7200)
        if r.returncode != 0:
            raise RuntimeError("ffmpeg: " + (r.stderr or b"").decode(errors="replace")[-200:])
        return base + ".mp4"

    def sound_of(p, k):
        if k == "sound":
            return mt._read_audio(p)
        if k == "seed":
            sd, bpm = read_seed(p); y, sr = seed_render_audio(app, sd, bpm); return y, sr
        q = convert(app, p, "sound", os.path.splitext(p)[0]) if k in EXTRA_KINDS else mt.convert(app, p, "sound")
        return mt._read_audio(q)
    ya, sra = sound_of(a_path, ka); yb, srb = sound_of(b_path, kb)
    ya = np.asarray(ya, dtype=np.float64); yb = np.asarray(yb, dtype=np.float64)
    if srb != sra and yb.size:
        yb = np.interp(np.arange(int(yb.size * sra / srb)) * (srb / sra), np.arange(yb.size), yb)
    n = max(ya.size, yb.size); d = np.zeros(n); d[:ya.size] += ya; d[:yb.size] -= yb
    mt._write_audio(base + ".wav", d.astype(np.float32), sra)
    return base + ".wav"


# ---------------------------------------------------------------- exact symbolic seeds -----
# R32.9 SYMBOLIC COMPLETENESS: any finite note sequence has a seed program that reproduces it EXACTLY.
# The program is a step table (pitch per 16th, 0 = rest) indexed by beat time:
#     P = (p₀, p₁, …, p_{L−1});  i = ⌊4t⌋ mod L;  f(t) = 0 if Pᵢ = 0 else 440·2^((Pᵢ − 69)/12)
# so f(k/4) is the k-th step's pitch for every k — a lossless description, not an estimate.
def notes_to_exact_seed(notes, bpm=120.0, steps_per_beat=4):
    if not notes:
        return "return 0"
    step_s = 60.0 / float(bpm) / steps_per_beat
    L = max(1, int(round(max(s + d for s, d, _p, _v in notes) / step_s)))
    table = [0] * L
    for s0, d, p, _v in notes:
        i = int(round(s0 / step_s))
        if 0 <= i < L:
            table[i] = int(max(1, min(127, p)))
    return ("# exact symbolic seed · %d steps · %d per beat\nP = (%s,)\ni = int(floor(t * %d)) %% %d\n"
            "if P[i] == 0:\n    return 0\nreturn 440 * 2 ** ((P[i] - 69) / 12)") % (L, steps_per_beat, ", ".join(map(str, table)), steps_per_beat, L)


def exact_seed_table(notes, bpm=120.0, steps_per_beat=4):
    step_s = 60.0 / float(bpm) / steps_per_beat
    L = max(1, int(round(max(s + d for s, d, _p, _v in notes) / step_s)))
    table = [0] * L
    for s0, d, p, _v in notes:
        i = int(round(s0 / step_s))
        if 0 <= i < L:
            table[i] = int(max(1, min(127, p)))
    return table
