"""GROOVEBOX_R29E_TRACKPAD_TUNER_20261104 — trackpad pinch + Ctrl-wheel pitch bend for live key triggers.

GROOVEBOX_R23R_LIVE_PLAYER_20261103 — Live Composition Player.

Watch and hear the actual composition as it happens.

* Light engine (default): every playlist row is planned from the same data the
  renderer reads (row roster from operators / sequence_refs / operator, the
  referenced sequence bank or the instrument's sequence, the canonical overlay
  when the lane has no user content, the seed-mapped fundamental × step pitch ×
  panel tuning). Each hit is the instrument's own voice — the same voice the
  keyboard / Trigger Note plays (Edit Synth panel synth + four geometrics +
  sample layer). No master FX, no video processing chains. Rows are synthesised
  just ahead of the play head on one worker thread, so playback starts at once.
* "Full process routine": the full shared mixdown (the exact buffer Play and
  Export use) is rendered first, then streamed through the same live view, so
  it sounds identical to the Play / Export output.

* "Full video rig" (size selectable — the engine is heavy, 320×180 is fastest): the real video engine (a private VideoSynthEngine bound to the
  project, as the video export uses, plus the project's video plan) renders live
  frames from the live audio on one worker thread, newest frame wins (frames are
  dropped, never queued, so the picture never lags the sound). Live view only —
  exports keep their own deterministic frame-by-frame renderer.

* "Record live play": saves exactly what you hear (composition + keys + mic) and,
  with "video", exactly what the live view shows (every enabled layer, camera
  included) — a quick take, not the high-quality export. Audio and frames stream
  to disk while you play (memory stays flat on long takes). Formats: WAV / MCC /
  FLAC / MP3 / OGG and MP4 / MCC / WEBM / MKV. Saved under "Save to:" (project
  exports folder or a USB / SD drive).
* Live inputs (GROOVEBOX_R23R_LIVE_INPUTS_20261103): 🎙 mic into the mix (level,
  optional monitor), 🎥 camera layer (corner or full screen).
* 🧅 Layers: video rig picture, instrument orbit (rosette), waveform ring, names,
  playlist strip, camera — each on / off, for the view and for video takes.
* Gray background for every Groovebox video (GROOVEBOX_R23R_GRAY_VIDEO_BG_20261103).

Click the playlist strip to jump to a row.

The keyboard (key chart) keeps working while the Live Player runs: key hits are
mixed into the live stream (one hardware stream, no device contention).
"""
from __future__ import annotations

import math
import os
import sys
import queue
import threading
import time

import numpy as np

try:
    from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QEvent, pyqtSignal
    from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QRadialGradient, QPainterPath, QFont, QImage
    from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
                                 QLabel, QSpinBox, QSlider, QSizePolicy, QToolButton, QMenu, QApplication, QComboBox)
except Exception:  # pragma: no cover - headless import of the planner only
    QDialog = QWidget = object

LIGHT_SR = 44100
LIGHT_GAIN = 0.28          # the keyboard / Trigger Note voice gain (NO_FADE_NO_LIMIT_20261102)


def pitch_bend_ratio(semitones):
    """Return a bounded equal-tempered playback ratio for live key-trigger bend."""
    try:
        st = float(semitones)
    except Exception:
        st = 0.0
    if not math.isfinite(st):
        st = 0.0
    st = max(-12.0, min(12.0, st))
    return 2.0 ** (st / 12.0)


def pitch_bend_buffer(buffer, semitones):
    """Apply a one-shot pitch bend to a pre-rendered key trigger.

    This is a playback-rate bend: pitch and trigger duration move together, just
    like a rate-controlled sampler. The backing composition is never touched.
    """
    arr = np.asarray(buffer, dtype=np.float32).ravel()
    ratio = pitch_bend_ratio(semitones)
    if arr.size < 2 or abs(ratio - 1.0) < 1e-9:
        return np.ascontiguousarray(arr)
    count = max(2, int(round(arr.size / ratio)))
    positions = np.arange(count, dtype=np.float64) * ratio
    positions = np.minimum(positions, float(arr.size - 1))
    out = np.interp(positions, np.arange(arr.size, dtype=np.float64), arr).astype(np.float32)
    return np.ascontiguousarray(out)


# ---------------------------------------------------------------------------
# Planner (GUI thread: reads widgets / project state once)
# ---------------------------------------------------------------------------
def _gb():
    import groovebox
    return groovebox


def _row_names(host, entry):
    names = []
    raw_ops = entry.get("operators", []) if isinstance(entry, dict) else []
    if isinstance(raw_ops, str):
        raw_ops = [x.strip() for x in raw_ops.split(",") if x.strip()]
    names.extend(str(x).strip() for x in (raw_ops or []) if str(x).strip())
    refs = entry.get("sequence_refs", []) if isinstance(entry, dict) else []
    if isinstance(refs, str):
        refs = [x.strip() for x in refs.split(",") if x.strip()]
    for r in refs or []:
        nm = str(r).split(":", 1)[0].strip()
        if nm:
            names.append(nm)
    if isinstance(entry, dict) and entry.get("operator"):
        names.append(str(entry.get("operator")).strip())
    roster = list(getattr(host, "instrument_names_48", []) or [])
    return [n for n in dict.fromkeys(names) if n in roster], [str(r) for r in (refs or [])]


def _row_mem(host, op, refs, row_idx):
    banks = getattr(host, "instrument_sequence_banks", {}) or {}
    for r in refs:
        if ":" not in r:
            continue
        a, sid = r.rsplit(":", 1)
        if a.strip() != op:
            continue
        try:
            m = (banks.get(op) or {}).get(int(sid))
        except Exception:
            m = None
        if isinstance(m, dict):
            return m
    mem = (getattr(host, "instrument_sequencer_memory", {}) or {}).get(op) or {}
    has_user = bool(mem.get("user_owned")) or any(bool(x) for x in (mem.get("steps") or []))
    if not has_user:
        ov = (getattr(host, "canonical_runtime_overlays", {}) or {}).get(f"{op}:{int(row_idx)}")
        seq = ov.get("sequence") if isinstance(ov, dict) else None
        if isinstance(seq, dict) and seq.get("steps"):
            return seq
    return mem


def _voice_hz(host, gb, op, op_idx, n_roster, row_t0, pitch):
    base = float(host.spin_base_frequency.value()) if hasattr(host, "spin_base_frequency") else 432.0
    slot = gb.canonical_master_slot(int(op_idx), max(2, n_roster))
    base_freq = base * gb.MEUM_POWERS_36[slot % 36]
    try:
        vseed = float(host.get_seed_value_for_index(slot, t_value=float(row_t0)))
    except Exception:
        vseed = float(host.get_numeric_seed() or 0.0)
    seed_hz = float(gb._seed_to_fundamental_hz(vseed, base_freq, slot, 0))
    st = (getattr(host, "instrument_param_state", {}) or {}).get(op, {}) or {}
    tuning = float(st.get("tuning_ratio", st.get("tuning", 1.0)) or 1.0)
    tuning = tuning if tuning >= 0.0 else 0.0
    harm = float(st.get("harmonic_freq", base_freq) or base_freq)
    ident = st.get("frequency_identity_hz")
    if ident not in (None, ""):
        try:
            ib = float(st.get("frequency_identity_base_hz", 432.0) or 432.0)
            ir = float(st.get("frequency_identity_ratio", (float(ident) / ib) if ib > 0 else 1.0))
            sr_ = float(gb._seed_to_pitch_ratio(vseed, slot, 0))
            r0 = gb._seed_to_pitch_ratio(0.0, op_idx, 0)
            hz = base_freq * ir * ((sr_ / r0) if r0 else 0.0)
        except Exception:
            hz = seed_hz * tuning
    elif harm > 20.0 and abs(harm - base_freq) > 1.0:
        hz = (0.45 * harm + 0.55 * seed_hz) * tuning
    else:
        hz = seed_hz * tuning
    return float(max(getattr(gb, "AUDIBLE_LO_HZ", 20.0), min(20000.0, hz * float(pitch))))


def build_plan(host):
    """{'row_dur', 'rows': [[(t0, dur, name, hz, amp), ...] per row], 'names', 'bpm'}"""
    gb = _gb()
    bpm = float(host.spin_bpm.value()) if hasattr(host, "spin_bpm") else 120.0
    spb = (60.0 / bpm) if bpm > 0 else 0.5      # tempo 0 is not a tempo: the 120 BPM beat
    beats = 4.0
    for attr in ("spin_row_beats", "spin_playlist_beats"):
        w = getattr(host, attr, None)
        if w is not None:
            try:
                beats = float(w.value()); break
            except Exception:
                pass
    row_dur = spb * max(0.25, min(64.0, beats))
    roster = list(getattr(host, "instrument_names_48", []) or [])
    playlist = list(getattr(host, "master_playlist_data", []) or [])
    use_pl = True
    try:
        use_pl = bool(host.chk_global_playlist.isChecked())
    except Exception:
        pass
    if not playlist or not use_pl:
        # No playlist: one row of every instrument that has steps (loops)
        mem = getattr(host, "instrument_sequencer_memory", {}) or {}
        playlist = [{"operators": [n for n in roster if any((mem.get(n) or {}).get("steps") or [])]}]
    try:
        seed_int = int(gb._safe_int_seed(host.get_numeric_seed()))
    except Exception:
        seed_int = 0
    rows_out, used = [], []
    for ri, entry in enumerate(playlist):
        names, refs = _row_names(host, entry if isinstance(entry, dict) else {})
        vel = float((entry or {}).get("velocity", 1.0) or 1.0) if isinstance(entry, dict) else 1.0
        offs_op = (entry or {}).get("operator_time_offsets") if isinstance(entry, dict) else None
        offs_op = offs_op if isinstance(offs_op, dict) else {}
        evs = []
        for op in names:
            mem = _row_mem(host, op, refs, ri)
            steps = list(mem.get("steps") or [])
            if not any(steps):
                continue
            amps = list(mem.get("amplitudes") or [])
            pits = list(mem.get("pitches") or [])
            offs = list(mem.get("offsets") or [])
            probs = list(mem.get("probabilities") or [])
            pat = max(1, int(mem.get("pattern_length", len(steps) or 1) or 1))
            sd = row_dur / pat
            oi = roster.index(op)
            try:
                op_off = float(offs_op.get(op, 0.0) or 0.0) * row_dur
            except Exception:
                op_off = 0.0
            for s in range(pat):
                if not (s < len(steps) and steps[s]):
                    continue
                # deterministic probability lattice (no random draw), as the renderer
                p = float(probs[s]) / 100.0 if s < len(probs) else 1.0
                ph_mod = max(1, min(512, pat))
                thr = float((s + ri * 3 + oi * 5 + seed_int) % ph_mod) / ph_mod
                if p < 1.0 and thr >= p:
                    continue
                off = float(np.clip(float(offs[s]) if s < len(offs) else 0.0, -1.0, 1.0))
                t0 = (s * sd + off * sd + op_off) % row_dur
                amp = float(np.clip(float(amps[s]) if s < len(amps) else 1.0, 0.0, 4.0)) * vel
                pr = float(pits[s]) if s < len(pits) else 1.0
                try:
                    hz = _voice_hz(host, gb, op, oi, len(roster), ri * row_dur, pr)
                except Exception:
                    hz = 432.0 * max(0.01, pr)
                evs.append((float(t0), float(min(sd, row_dur - t0)), op, hz, amp))
                used.append(op)
        evs.sort(key=lambda e: e[0])
        rows_out.append(evs)
    return {"row_dur": float(row_dur), "rows": rows_out, "names": list(dict.fromkeys(used)), "bpm": bpm}


# ---------------------------------------------------------------------------
# Synthesis (worker thread)
# ---------------------------------------------------------------------------
def synth_row(host, events, row_dur, sr=LIGHT_SR, cache=None):
    """One row of raw instrument voices (the keyboard voice), summed. No FX, no limiter."""
    n = max(1, int(round(row_dur * sr)))
    out = np.zeros(n, dtype=np.float64)
    gb = None
    for (t0, dur, name, hz, amp) in events:
        i0 = int(t0 * sr)
        m = min(n - i0, max(1, int(dur * sr)))
        if m <= 0 or amp <= 0.0:
            continue
        key = (name, round(hz, 4), m)
        v = cache.get(key) if cache is not None else None
        if v is None:
            t = np.arange(m, dtype=np.float64) / sr
            v = np.asarray(host._audition_voice(name, hz, t, sr), dtype=np.float64)
            rec = (getattr(host, "instrument_media_samples", {}) or {}).get(name)
            if isinstance(rec, dict) and rec.get("waveform") is not None:
                try:
                    raw = host._sample_native_layer(np.asarray(rec["waveform"], dtype=np.float32),
                                                    int(rec.get("sample_rate", sr) or sr), t)
                    v = 0.5 * v + 0.5 * np.asarray(raw, dtype=np.float64)
                except Exception:
                    pass
            v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
            if cache is not None:
                if len(cache) > 512:
                    cache.clear()
                cache[key] = v
        out[i0:i0 + m] += v[:m] * amp
    return (LIGHT_GAIN * out).astype(np.float32)



# ---------------------------------------------------------------------------
# Live inputs: microphone + camera (GROOVEBOX_R23R_LIVE_INPUTS_20261103)
# ---------------------------------------------------------------------------
class MicFeed:
    """Microphone into the live mix. Samples are resampled to the live stream rate
    (linear, only when the device cannot run at that rate) and buffered (≤ 2 s)."""

    def __init__(self, host, sr):
        self.host, self.sr = host, int(sr)
        self.gain = 1.0
        self.level = 0.0
        self.buf = []
        self.n = 0
        self.lock = threading.Lock()
        self.stream = None
        self.rate = self.sr
        self.error = ""

    def start(self):
        import audio_os_backend as aob
        pref = str(getattr(self.host, "preferred_audio_input_name", "") or "")
        try:
            st, rate, _idx = aob.open_input_stream_adaptive(samplerate=self.sr, channels=1, dtype="float32",
                                                            callback=self._cb, preferred_name=pref or None)
            self.rate = int(rate)
            st.start()
            self.stream = st
        except Exception as exc:
            self.error = f"microphone unavailable: {exc}"
            self.stream = None
        return self.stream is not None

    def _cb(self, indata, frames, time_info, status):
        try:
            x = np.asarray(indata[:, 0], dtype=np.float32).copy()
            if self.rate != self.sr and x.size > 1:
                m = max(1, int(round(x.size * self.sr / float(self.rate))))
                x = np.interp(np.linspace(0.0, x.size - 1, m), np.arange(x.size), x).astype(np.float32)
            self.level = max(float(np.max(np.abs(x))) if x.size else 0.0, self.level * 0.9)
            with self.lock:
                self.buf.append(x); self.n += x.size
                while self.n > 2 * self.sr and self.buf:
                    self.n -= self.buf[0].size; del self.buf[0]
        except Exception:
            pass

    def read(self, n):
        out = np.zeros(int(n), dtype=np.float32)
        w = 0
        with self.lock:
            while w < n and self.buf:
                b = self.buf[0]
                take = min(n - w, b.size)
                out[w:w + take] = b[:take]
                w += take
                if take < b.size:
                    self.buf[0] = b[take:]
                else:
                    del self.buf[0]
                self.n -= take
        return out * np.float32(self.gain)

    def close(self):
        st, self.stream = self.stream, None
        if st is not None:
            for fn in (st.stop, st.close):
                try:
                    fn()
                except Exception:
                    pass


class CameraFeed:
    """Camera frames (RGB) from ffmpeg (v4l2 / DirectShow / AVFoundation), newest frame wins."""

    def __init__(self, host, size=(640, 360)):
        self.host = host
        self.w, self.h = int(size[0]), int(size[1])
        self.frame = None
        self.lock = threading.Lock()
        self.proc = None
        self.thread = None
        self.error = ""

    def start(self):
        import shutil, subprocess
        ff = None
        try:
            ff = self.host._resolve_ffmpeg_binary()
        except Exception:
            pass
        ff = ff or shutil.which("ffmpeg")
        if not ff:
            self.error = "camera needs ffmpeg"; return False
        cam = ""
        try:
            cam = str((getattr(self.host, "preferred_camera_format", None) or {}).get("device_path", "") or "")
        except Exception:
            pass
        try:
            import live_stream
            args = live_stream.LiveBroadcaster._input_args(None, True, False, cam, "", False)
        except Exception as exc:
            self.error = f"camera unavailable: {exc}"; return False
        cmd = [ff, "-hide_banner", "-loglevel", "error", *args, "-an",
               "-vf", f"scale={self.w}:{self.h}:force_original_aspect_ratio=decrease,"
                      f"pad={self.w}:{self.h}:(ow-iw)/2:(oh-ih)/2:color=0x3e3f42",
               "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        except Exception as exc:
            self.error = f"camera unavailable: {exc}"; return False
        self.thread = threading.Thread(target=self._run, name="live-player-camera", daemon=True)
        self.thread.start()
        return True

    def _run(self):
        n = self.w * self.h * 3
        pr = self.proc
        while pr is not None and pr.poll() is None:
            data = b""
            try:
                while len(data) < n:
                    chunk = pr.stdout.read(n - len(data))
                    if not chunk:
                        break
                    data += chunk
            except Exception:
                break
            if len(data) < n:
                break
            fr = np.frombuffer(data, dtype=np.uint8).reshape(self.h, self.w, 3)
            with self.lock:
                self.frame = fr
        if pr is not None and pr.poll() is not None and self.frame is None:
            try:
                self.error = "camera: " + (pr.stderr.read() or b"").decode(errors="replace").strip()[-200:]
            except Exception:
                self.error = "camera stopped"

    def latest(self):
        with self.lock:
            return self.frame

    def close(self):
        pr, self.proc = self.proc, None
        if pr is not None:
            try:
                pr.terminate(); pr.wait(timeout=2)
            except Exception:
                try:
                    pr.kill()
                except Exception:
                    pass
        if self.thread is not None:
            self.thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# DJ effects for the live stream (GROOVEBOX_R23R_LIVE_DJ_FX_20261103)
# ---------------------------------------------------------------------------
class DJChain:
    """GROOVEBOX_R31_MEUM_FX_CORE_20261109: the Live Player rack now runs only the
    hardcoded FX (hardcoded_fx.MeumPerformanceRack): Fractallizer tilt replaces the
    LP/HP filter sweep, EQR replaces echo, ∞M HyperDrive replaces bitcrush and the
    PKP gate replaces the square gate. Beat-repeat (stutter) is playback, not DSP.
    SciPy-free, so it sounds identical on sOS / Fedora / Windows / macOS (the old
    filter silently did nothing without SciPy). The ``p`` keys are unchanged, so
    saved Live Player settings still load. All at 0 = exact bypass; no limiter."""

    def __init__(self, sr):
        import hardcoded_fx as _hfx
        z_fn = None
        try:
            z_fn = _gb().eqr_tensor_audio_z_vec
        except Exception:
            z_fn = None
        self._rack = _hfx.MeumPerformanceRack(sr, z_fn=z_fn)
        self.sr = self._rack.sr

    @property
    def p(self):
        return self._rack.p

    @p.setter
    def p(self, value):
        self._rack.p = value

    @property
    def bpm(self):
        return self._rack.bpm

    @bpm.setter
    def bpm(self, value):
        self._rack.bpm = float(value)

    def process(self, x):
        return self._rack.process(x)

    def active(self):
        return self._rack.active()


# ---------------------------------------------------------------------------
# Media deck (GROOVEBOX_R23R_LIVE_MEDIA_DECK_20261103)
# ---------------------------------------------------------------------------
def _ffmpeg_for(host):
    import shutil
    try:
        ff = host._resolve_ffmpeg_binary()
        if ff:
            return ff
    except Exception:
        pass
    return shutil.which("ffmpeg")


def decode_audio_file(host, path, sr):
    """Any audio/video file → mono float32 at ``sr`` (ffmpeg; .MCC media via mcc_media)."""
    import subprocess, os
    if str(path).lower().endswith(".mcc"):
        try:
            import mcc_media
            if mcc_media.media_kind(path) == "audio":
                x, r = mcc_media.decode_audio(path)
                x = np.asarray(x, dtype=np.float32)
                x = x.mean(axis=1) if x.ndim > 1 else x
                if int(r) != int(sr):
                    import audio_os_backend as aob
                    x = aob._resample_for_hardware(x, int(r), int(sr))
                return np.asarray(x, dtype=np.float32)
        except Exception:
            pass
    ff = _ffmpeg_for(host)
    if not ff:
        raise RuntimeError("loading media needs ffmpeg")
    r = subprocess.run([ff, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(int(sr)),
                        "-f", "f32le", "-"], capture_output=True, timeout=600)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError((r.stderr or b"").decode(errors="replace").strip()[-200:] or "decode failed")
    return np.frombuffer(r.stdout, dtype="<f4").astype(np.float32)


def file_has_video(host, path):
    import subprocess, shutil
    ext = str(path).lower().rsplit(".", 1)[-1]
    if ext in ("mp3", "wav", "flac", "ogg", "opus", "m4a", "aac", "aif", "aiff", "wma"):
        return False
    probe = shutil.which("ffprobe")
    ff = _ffmpeg_for(host)
    if ff:
        import os
        cand = os.path.join(os.path.dirname(ff), "ffprobe" + (".exe" if ff.lower().endswith(".exe") else ""))
        if os.path.isfile(cand):
            probe = cand
    if not probe:
        return ext in ("mp4", "mkv", "webm", "mov", "avi", "m4v")
    try:
        r = subprocess.run([probe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=20)
        return "video" in (r.stdout or "")
    except Exception:
        return False


class MediaTrack:
    """Decoded audio of a loaded file, played from the live callback (loop optional)."""

    def __init__(self, path, pcm, sr):
        self.path, self.pcm, self.sr = path, np.asarray(pcm, dtype=np.float32), int(sr)
        self.pos = 0
        self.played = 0
        self.loop = True
        self.gain = 1.0
        self.done = False

    def read(self, n):
        out = np.zeros(int(n), dtype=np.float32)
        if self.pcm.size == 0 or self.done:
            return out
        w = 0
        while w < n:
            take = min(n - w, self.pcm.size - self.pos)
            out[w:w + take] = self.pcm[self.pos:self.pos + take]
            self.pos += take; w += take
            if self.pos >= self.pcm.size:
                if self.loop:
                    self.pos = 0
                else:
                    self.done = True
                    break
        self.played += int(n)
        return out * np.float32(self.gain)

    def seconds(self):
        return self.played / float(self.sr)


class FileVideoFeed:
    """Video of the loaded media file as a layer, timed by the media audio clock."""
    FPS = 24

    def __init__(self, host, path, clock, size=(640, 360)):
        self.host, self.path, self.clock = host, path, clock
        self.w, self.h = int(size[0]), int(size[1])
        self.frame = None
        self.lock = threading.Lock()
        self.proc = None
        self.thread = None
        self.stop_evt = threading.Event()
        self.error = ""

    def start(self):
        import subprocess
        ff = _ffmpeg_for(self.host)
        if not ff:
            self.error = "media video needs ffmpeg"; return False
        cmd = [ff, "-v", "error", "-stream_loop", "-1", "-i", str(self.path), "-an",
               "-vf", f"fps={self.FPS},scale={self.w}:{self.h}:force_original_aspect_ratio=decrease,"
                      f"pad={self.w}:{self.h}:(ow-iw)/2:(oh-ih)/2:color=0x3e3f42",
               "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        except Exception as exc:
            self.error = f"media video: {exc}"; return False
        self.thread = threading.Thread(target=self._run, name="live-player-media-video", daemon=True)
        self.thread.start()
        return True

    def _run(self):
        n = self.w * self.h * 3
        idx = 0
        pr = self.proc
        while not self.stop_evt.is_set() and pr is not None and pr.poll() is None:
            target = int(self.clock() * self.FPS)
            if idx > target + 2:                 # ahead of the audio: wait
                time.sleep(0.01); continue
            data = b""
            try:
                while len(data) < n:
                    chunk = pr.stdout.read(n - len(data))
                    if not chunk:
                        break
                    data += chunk
            except Exception:
                break
            if len(data) < n:
                break
            idx += 1
            if idx >= target:                    # behind: decode on, publish only frames in time
                with self.lock:
                    self.frame = np.frombuffer(data, dtype=np.uint8).reshape(self.h, self.w, 3)

    def latest(self):
        with self.lock:
            return self.frame

    def close(self):
        self.stop_evt.set()
        pr, self.proc = self.proc, None
        if pr is not None:
            try:
                pr.kill(); pr.wait(timeout=2)
            except Exception:
                pass
        if self.thread is not None:
            self.thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# Stream engine
# ---------------------------------------------------------------------------
class LiveEngine:
    """One output stream. Feeds rows from a bounded queue; mixes keyboard hits and the
    microphone on top. The recording tap gets composition + keys + mic."""

    def __init__(self, host):
        self.host = host
        self.sr = LIGHT_SR
        self.q = queue.Queue(maxsize=3)
        self.cur = None            # (row_idx, buffer)
        self.pos = 0
        self.played = 0            # samples since start
        self.row_started_at = 0    # sample index where the current row began
        self.row_idx = -1
        self.underruns = 0
        self.keys = []             # [buf, pos]
        self.lock = threading.Lock()
        self.scope = np.zeros(1024, dtype=np.float32)
        self.stream = None
        self.stop_evt = threading.Event()
        self.finished = False
        self.rec = None            # callable(block) while recording
        self._callback_active = 0  # lock-free GIL counter; recorder drain barrier
        self.mic = None            # MicFeed
        self.mic_monitor = False   # mic also to the speakers (off: no feedback; still recorded)
        self.fx = None             # DJChain (set by the window)
        self.media = None          # MediaTrack
        self.comp_gain = 1.0       # mixer: composition / keys (media gain lives on the track)
        self.keys_gain = 1.0

    # audio thread
    def callback(self, outdata, frames, time_info, status):
        self._callback_active += 1
        try:
            frames = int(frames)
            mix = np.zeros(frames, dtype=np.float32)
            w = 0
            while w < frames:
                if self.cur is None or self.pos >= len(self.cur[1]):
                    try:
                        item = self.q.get_nowait()
                    except queue.Empty:
                        if self.cur is not None:
                            self.underruns += 1
                        self.cur = None
                        break
                    if item is None:
                        self.finished = True
                        self.cur = None
                        break
                    self.cur = item
                    self.pos = 0
                    self.row_idx = int(item[0])
                    self.row_started_at = self.played + w
                buf = self.cur[1]
                take = min(frames - w, len(buf) - self.pos)
                mix[w:w + take] = buf[self.pos:self.pos + take]
                self.pos += take
                w += take
            if self.comp_gain != 1.0:
                mix *= np.float32(self.comp_gain)
            med = self.media
            if med is not None:
                mix += med.read(frames)
            with self.lock:
                keys, self.keys = self.keys, []
            alive = []
            kg = np.float32(self.keys_gain)
            for kb, kp in keys:
                take = min(frames, len(kb) - kp)
                if take > 0:
                    mix[:take] += kb[kp:kp + take] * kg
                    kp += take
                if kp < len(kb):
                    alive.append([kb, kp])
            if alive:
                with self.lock:
                    self.keys = alive + self.keys
            self.played += frames
            fx = self.fx
            if fx is not None and fx.active():
                mix = fx.process(mix)
            mv = float(getattr(self.host, "master_volume", 0.72))
            mv = max(0.0, min(1.0, mv if math.isfinite(mv) else 1.0))
            mix = mix * np.float32(mv)
            mic = self.mic
            take_mix = mix
            if mic is not None:
                m = mic.read(frames)
                take_mix = mix + m
                if self.mic_monitor:
                    mix = take_mix
            rec = self.rec
            if rec is not None:
                rec(take_mix.copy())
            n = min(len(take_mix), len(self.scope))
            self.scope = np.roll(self.scope, -n)
            self.scope[-n:] = take_mix[-n:]
            outdata[:] = mix.reshape(-1, 1) if outdata.shape[1] == 1 else np.repeat(mix.reshape(-1, 1), outdata.shape[1], axis=1)
        except Exception:
            outdata.fill(0.0)
        finally:
            self._callback_active = max(0, self._callback_active - 1)

    def add_key(self, buf, sr):
        arr = np.asarray(buf, dtype=np.float32).ravel()
        if int(sr) != int(self.sr) and arr.size > 1:
            m = max(1, int(round(arr.size * self.sr / float(sr))))
            arr = np.interp(np.linspace(0.0, arr.size - 1, m), np.arange(arr.size), arr).astype(np.float32)
        with self.lock:
            if len(self.keys) > 64:
                del self.keys[0]
            self.keys.append([arr, 0])
        return arr

    def release_key(self, arr, release_s=0.2):
        """R32.9: held-key release inside the Live Player stream."""
        try:
            import held_sustain as _hs
        except Exception:
            return False
        with self.lock:
            for e in self.keys:
                if e[0] is arr:
                    e[0] = _hs.release_tail(arr, int(e[1]), int(self.sr), float(release_s)); return True
        return False

    def open(self, sr):
        import audio_os_backend as aob
        self.sr = int(sr)
        pref = str(getattr(self.host, "_preferred_audio_output_name", "") or "")
        # GROOVEBOX_R23R_LIVE_PLAYER_LOW_LAG_20261103: pre-decoded queue → low latency safe
        blk, lat = aob.stream_tuning("file_decoded")
        self.stream = aob.open_output_stream(samplerate=self.sr, channels=1, dtype="float32",
                                             callback=self.callback, blocksize=blk, latency=lat,
                                             preferred_name=pref)
        self.stream.start()

    def close(self):
        self.stop_evt.set()
        st, self.stream = self.stream, None
        if st is not None:
            try:
                st.stop()
            except Exception:
                pass
            try:
                st.close()
            except Exception:
                pass
        mic, self.mic = self.mic, None
        if mic is not None:
            mic.close()
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            pass

    def position_seconds(self):
        return max(0.0, (self.played - self.row_started_at) / float(self.sr))


# ---------------------------------------------------------------------------
# Full video rig (live only)
# ---------------------------------------------------------------------------
RIG_SIZES = (("320×180 (fastest)", (320, 180)), ("480×270", (480, 270)), ("640×360", (640, 360)),
             ("960×540", (960, 540)), ("1920×1080 · Full HD", (1920, 1080)),
             ("2560×1440 · QHD", (2560, 1440)), ("3840×2160 · 4K UHD (adaptive)", (3840, 2160)))


_TRANSIENT = {"set": None}


def _transient_attrs(gb):
    """R32.9 DETERMINISM: attributes the engine changes while rendering (smoothing, energy, trails, caches…).
    Found once by rendering one tiny frame on a scratch engine; clones never copy them, so every render
    starts from the same fresh state and the same seed gives the same frames."""
    if _TRANSIENT["set"] is not None:
        return _TRANSIENT["set"]
    import copy as _copy
    out = set()
    try:
        e = gb.VideoSynthEngine(8)
        before = {k: _copy.copy(v) for k, v in vars(e).items()}
        e.set_waveform(np.sin(np.linspace(0, 40, 2048)).astype(np.float32), playhead=0.3)
        e.render_frame(32, 18, export=True, frame_index=3)
        for k, v in vars(e).items():
            b = before.get(k, object())
            try:
                same = (b is v) or bool(np.array_equal(b, v)) if isinstance(v, np.ndarray) or isinstance(b, np.ndarray) else (b == v)
            except Exception:
                same = False
            if not same:
                out.add(k)
    except Exception:
        pass
    _TRANSIENT["set"] = out
    return out


def clone_export_engine(gb, host, fallback_n=48):
    """R32.8 RIG_EXPORT_PARITY: a video engine configured exactly like the one the main export uses.

    The live rig used to build VideoSynthEngine(len(active instruments)) with default settings, so it
    looked simpler than exported video. This copies the export engine's voice count and every plain
    setting (numbers, strings, arrays, dicts / lists of those) so a live frame at scale 100 % is the
    export frame for the same moment. Pools, locks, threads and Qt objects are not shared."""
    import copy as _copy
    src = getattr(host, "video_synth_engine", None)
    n = int(getattr(src, "n", 0) or 0) or (len(getattr(host, "active_instrument_memory", []) or []) or int(getattr(host, "synth_count", fallback_n) or fallback_n))
    eng = gb.VideoSynthEngine(n)
    if src is not None:
        plain = (int, float, str, bool, type(None), np.ndarray, np.generic)

        def ok(v, d=0):
            if isinstance(v, plain):
                return True
            if d < 3 and isinstance(v, (list, tuple)):
                return all(ok(x, d + 1) for x in v[:256])
            if d < 3 and isinstance(v, dict):
                return all(isinstance(k, (str, int, float)) and ok(x, d + 1) for k, x in list(v.items())[:256])
            return False
        transient = _transient_attrs(gb)
        for k, v in list(vars(src).items()):
            if k in ("app", "wave", "t", "playhead") or k.startswith("__") or k in transient:
                continue
            try:
                if ok(v):
                    setattr(eng, k, _copy.deepcopy(v))
            except Exception:
                pass
    if hasattr(eng, "bind_app"):
        eng.bind_app(host)
    return eng


class VideoRig:
    """Live frames from the real video engine; newest frame wins."""
    FPS = 30.0

    def __init__(self, host, plan, engine, size=(320, 180), workers=1, adaptive=None):
        self.host, self.plan, self.engine = host, plan, engine
        self.w, self.h = int(size[0]), int(size[1])
        self.frame = None
        self.frame_fi = -1
        self.frame_played = -1
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.thread = None
        self.threads = []
        self.fps_measured = 0.0
        self.error = ""
        # LIVE_4K_R31: frame-parallel workers (each its own engine) + adaptive internal resolution.
        self.workers = max(1, int(workers))
        self.adaptive = (self.w * self.h > 1920 * 1080) if adaptive is None else bool(adaptive)
        self.scale = 0.75 if self.adaptive else 1.0
        # R32.8 RIG_SCALE: host.live_rig_scale = 0 (auto) or a fixed 0.25..1.0 render scale;
        # 1.0 = full export-identical image at the output size.
        try:
            fs = float(getattr(host, "live_rig_scale", 0.0) or 0.0)
        except Exception:
            fs = 0.0
        if fs > 0.0:
            self.adaptive = True; self.scale = max(0.25, min(1.0, fs)); self._fixed = True
        else:
            self._fixed = False
        self._last_pub = time.monotonic()

    def effective_size(self):
        s = self.scale if self.adaptive else 1.0
        return max(16, int(self.w * s)) & ~1, max(16, int(self.h * s)) & ~1

    def start(self):
        for k in range(self.workers):
            t = threading.Thread(target=self._run_worker, args=(k,), name=f"live-player-video-rig-{k}", daemon=True)
            self.threads.append(t)
            t.start()
        self.thread = self.threads[0] if self.threads else None

    def _run_worker(self, k):
        if self.workers <= 1:
            return self._run()
        return self._run(k)

    def _run(self, k=0):
        gb = _gb()
        try:
            eng = clone_export_engine(gb, self.host)      # R32.8: same engine config as the main export
        except Exception as exc:
            self.error = f"video rig unavailable: {exc}"
            return
        total = self.plan["row_dur"] * max(1, len(self.plan["rows"]))
        n_frames = max(1, int(total * self.FPS))
        while not self.stop_evt.is_set():
            le = self.engine
            if le is None or le.row_idx < 0:
                time.sleep(0.01); continue
            t0 = time.monotonic()
            played_at = int(getattr(le, "played", 0))          # audio clock of this frame's moment
            pos = le.row_idx * self.plan["row_dur"] + le.position_seconds()
            fi = int(pos * self.FPS) % n_frames
            if self.workers > 1:
                # frame-parallel: worker k takes the frame slots k, k+W, k+2W, …
                fi = fi - (fi % self.workers) + k
                if fi <= self.frame_fi:
                    time.sleep(0.002); continue
            rw, rh = self.effective_size()
            try:
                eng.set_waveform(np.array(le.scope, copy=True), playhead=(min(1.0, pos / total) if total > 0 else 0.0))
                fr = eng.render_frame(rw, rh, export=True, frame_index=fi)
                fr = np.nan_to_num(np.asarray(fr), nan=0, posinf=255, neginf=0).astype(np.uint8, copy=False)
                try:
                    fr = self.host._apply_video_plan_to_frame(fr, fi, n_frames)
                except Exception:
                    pass
                fr = np.ascontiguousarray(np.asarray(fr)[:, :, :3], dtype=np.uint8)
                with self.lock:
                    if fi >= self.frame_fi or abs(fi - self.frame_fi) > n_frames // 2:   # newest frame wins (wrap-safe)
                        self.frame = fr
                        self.frame_fi = fi
                        self.frame_played = played_at
                        now = time.monotonic(); gap = now - self._last_pub; self._last_pub = now
                        if gap > 0:
                            inst = 1.0 / gap
                            self.fps_measured = inst if self.fps_measured <= 0 else 0.85 * self.fps_measured + 0.15 * inst
                self.error = ""
            except Exception as exc:
                self.error = f"video rig frame: {exc}"
                time.sleep(0.1)
            dt = time.monotonic() - t0
            if self.adaptive and not getattr(self, "_fixed", False) and k == 0 and dt > 0:
                # hold ~FPS: each worker has W frame periods per frame; scale area ∝ time budget.
                budget = self.workers / self.FPS
                ratio = budget / dt
                target = self.scale * math.sqrt(max(0.25, min(4.0, ratio))) * 0.97
                self.scale = max(0.5, min(1.0, 0.5 * self.scale + 0.5 * target))   # R31: never below half size (was a 300 px stretch)
            spare = (self.workers / self.FPS) - dt
            if spare > 0:
                time.sleep(min(spare, 0.03))

    def latest(self):
        with self.lock:
            return self.frame

    def stop(self):
        self.stop_evt.set()
        for t in (self.threads or ([self.thread] if self.thread is not None else [])):
            t.join(timeout=3.0)


class ProcessVideoRig:
    """LIVE_4K_PROCESS_RIG_R31: frame-parallel live video across K render PROCESSES (rig_worker.py).

    Same interface as VideoRig. A dispatcher thread sends each process the live output window and a
    frame slot; a reader thread per process collects frames; the newest frame wins. The render size
    adapts so the pool holds ~FPS, and the output is the requested size (e.g. 3840×2160)."""
    FPS = 30.0
    IN_FLIGHT = 2

    def __init__(self, host, plan, engine, size=(3840, 2160), workers=2):
        self.host, self.plan, self.engine = host, plan, engine
        self.w, self.h = int(size[0]), int(size[1])
        self.workers = max(1, int(workers))
        self.adaptive = True
        self.scale = 0.75
        try:   # R32.8 RIG_SCALE (see VideoRig)
            fs = float(getattr(host, "live_rig_scale", 0.0) or 0.0)
        except Exception:
            fs = 0.0
        self._fixed = fs > 0.0
        if self._fixed:
            self.scale = max(0.25, min(1.0, fs))
        self.frame = None
        self.frame_fi = -1
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.fps_measured = 0.0
        self.error = ""
        self.procs = []
        self.threads = []
        self.thread = None
        self._inflight = {}
        self._sent_t = {}
        self._sent_played = {}
        self.frame_played = -1
        self._last_pub = time.monotonic()
        self._tmp = None

    def effective_size(self):
        return max(16, int(self.w * self.scale)) & ~1, max(16, int(self.h * self.scale)) & ~1

    def start(self):
        import subprocess, tempfile
        try:
            self._tmp = tempfile.mkdtemp(prefix="gb-rig-")
            proj = os.path.join(self._tmp, "project.MCC")
            self.host._atomic_write_document(proj, self.host._project_snapshot())
            try:
                from groovebox_subprocess import helper_argv
                argv = helper_argv("rig_worker", proj)
            except Exception:
                argv = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "rig_worker.py"), proj]
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", GROOVEBOX_HEADLESS_WORKER="1",
                       OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
            for k in range(self.workers):
                p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
                self.procs.append(p)
                self._inflight[k] = 0
                t = threading.Thread(target=self._reader, args=(k, p), name=f"rig-proc-read-{k}", daemon=True)
                self.threads.append(t); t.start()
        except Exception as exc:
            self.error = f"process rig: {exc}"
            return
        self.thread = threading.Thread(target=self._dispatch, name="rig-proc-dispatch", daemon=True)
        self.thread.start()

    def _reader(self, k, p):
        import json as _json
        rd = p.stdout
        try:
            rd.readline()                       # {"ready": true}
            self._inflight[k] = 0
            self._ready = getattr(self, "_ready", 0) + 1
            while not self.stop_evt.is_set():
                line = rd.readline()
                if not line:
                    return
                try:
                    hdr = _json.loads(line.decode("utf-8"))
                except Exception:
                    continue                    # not a protocol line (defensive; workers print to stderr)
                if not isinstance(hdr, dict) or "fi" not in hdr:
                    continue
                if not hdr.get("ok"):
                    self.error = "rig frame: " + str(hdr.get("err", ""))
                    self._inflight[k] = max(0, self._inflight[k] - 1)
                    continue
                w, h, fi = int(hdr["w"]), int(hdr["h"]), int(hdr["fi"])
                buf = rd.read(w * h * 3)
                if len(buf) < w * h * 3:
                    return
                fr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
                self._inflight[k] = max(0, self._inflight[k] - 1)
                now = time.monotonic()
                with self.lock:
                    if fi > self.frame_fi:
                        self.frame, self.frame_fi = fr, fi
                        self.frame_played = self._sent_played.pop(fi, -1)
                        gap = now - self._last_pub; self._last_pub = now
                        if gap > 0:
                            inst = 1.0 / gap
                            self.fps_measured = inst if self.fps_measured <= 0 else 0.85 * self.fps_measured + 0.15 * inst
                # adapt: time one frame took in a worker vs the pool's frame budget
                dt = now - self._sent_t.pop(fi, now)
                if dt > 0:
                    budget = self.workers * self.IN_FLIGHT / self.FPS
                    target = self.scale * math.sqrt(max(0.25, min(4.0, budget / dt))) * 0.97
                    if not self._fixed:
                        self.scale = max(0.5, min(1.0, 0.7 * self.scale + 0.3 * target))   # engine is geometry-bound: smaller frames barely help
                self.error = ""
        except Exception as exc:
            if not self.stop_evt.is_set():
                self.error = f"rig worker {k}: {exc}"

    def _dispatch(self):
        import json as _json
        total = self.plan["row_dur"] * max(1, len(self.plan["rows"]))
        n_frames = max(1, int(total * self.FPS))
        next_k = 0
        last_fi = -1
        while not self.stop_evt.is_set():
            le = self.engine
            if le is None or le.row_idx < 0 or getattr(self, "_ready", 0) <= 0:
                time.sleep(0.01); continue
            pos = le.row_idx * self.plan["row_dur"] + le.position_seconds()
            fi = int(pos * self.FPS)
            if fi <= last_fi:
                time.sleep(0.003); continue
            # pick a worker with room (round-robin)
            k = None
            for j in range(self.workers):
                c = (next_k + j) % self.workers
                if self._inflight.get(c, 0) < self.IN_FLIGHT:
                    k = c; break
            if k is None:
                time.sleep(0.003); continue
            next_k = (k + 1) % self.workers
            rw, rh = self.effective_size()
            wave = np.ascontiguousarray(np.array(le.scope, dtype="<f4"))
            req = {"fi": fi, "w": rw, "h": rh, "ph": (min(1.0, pos / total) if total > 0 else 0.0), "t": pos,
                   "n": int(wave.size), "nf": n_frames}
            try:
                p = self.procs[k]
                p.stdin.write((_json.dumps(req) + "\n").encode("utf-8")); p.stdin.write(wave.tobytes()); p.stdin.flush()
                self._inflight[k] = self._inflight.get(k, 0) + 1
                self._sent_t[fi] = time.monotonic()
                self._sent_played[fi] = int(getattr(le, "played", 0))
                last_fi = fi
            except Exception as exc:
                self.error = f"rig dispatch: {exc}"
                time.sleep(0.05)

    def latest(self):
        with self.lock:
            return self.frame

    def stop(self):
        import shutil
        self.stop_evt.set()
        for p in self.procs:
            try:
                p.stdin.close()
            except Exception:
                pass
            try:
                p.kill(); p.wait(timeout=3)
            except Exception:
                pass
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Record live play (streamed to disk — no frames or audio piling up in memory)
# ---------------------------------------------------------------------------
class LiveRecorder:
    """Quick take of exactly what you hear (composition + keys + mic) and, optionally,
    exactly what the live view shows (every enabled layer, incl. camera), at a fixed size.

    Audio is written to a temporary float32 file as it arrives; video frames are piped
    to an encoder as they are drawn (a bounded queue — if the disk is slow a frame is
    dropped, never the audio, and memory stays flat). On stop the take is muxed into
    the chosen formats in the "Save to:" folder (project exports or a USB / SD drive).
    """
    AUDIO_FORMATS = ("WAV", "MCC", "FLAC", "MP3", "OGG")
    VIDEO_FORMATS = ("MP4", "MCC", "WEBM", "MKV")
    VIDEO_SIZE = (960, 540)
    VIDEO_FPS = 24

    def __init__(self, host, engine, audio_format="WAV", video_format="MP4", video=True):
        import os, tempfile
        self.host, self.engine = host, engine
        self.audio_format = str(audio_format or "WAV").upper()
        self.video_format = str(video_format or "MP4").upper()
        self.want_video = bool(video)
        self.video_requested = bool(video)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        try:
            d = str(host._exports_dir())
        except Exception:
            import groovebox_paths
            d = groovebox_paths.default_dir("export")
        os.makedirs(d, exist_ok=True)
        _sess = str(getattr(host, "_session_name", "") or "").strip()      # SESSION_NAME_R31
        self.base = os.path.join(d, (f"{_sess} · " if _sess else "") + f"live-take-{stamp}")
        self.tmpdir = tempfile.mkdtemp(prefix="gb-live-take-")
        self.raw_path = os.path.join(self.tmpdir, "audio.f32")
        self._audio_q = queue.Queue(maxsize=512)
        self.audio_blocks_dropped = 0
        self._video_size = tuple(getattr(type(self), "VIDEO_SIZE", (960, 540)))
        self._vq = queue.Queue(maxsize=48)
        self.frames_written = 0
        self.frames_dropped = 0
        self._first_frame = None
        self._venc = None          # ffmpeg process or MCC writer
        self._vpath = None
        self.stop_evt = threading.Event()
        self._threads = []
        self._video_setup_thread = None
        self._video_writer_thread = None
        self._video_ready = threading.Event()
        self.audio_samples = 0
        self._silence_pending = 0      # samples of dropped audio still to write as silence (in place)
        self._frame_dups = 0           # dropped video frames held as repeats (total, for reporting)
        self._dup_after = {}           # accepted-frame index → repeats to write right after that frame
        self._last_frame = None
        self.t0 = None
        self.sr = int(engine.sr)
        self.error = ""

    # -- audio (audio callback -> bounded non-blocking queue -> disk writer)
    def _on_audio(self, block):
        # The callback must never wait on disk or a mutex. Count the rendered
        # sample clock before enqueueing so video stays aligned even if the
        # bounded disk-writer queue drops an overloaded audio block.
        try:
            self.audio_samples += int(np.asarray(block).size)
        except Exception:
            pass
        # The engine already hands us an owned block; preserve that ownership.
        try:
            self._audio_q.put_nowait(block)
        except queue.Full:
            # LIVE_TAKE_SYNC_R31: keep the timeline. A dropped block becomes the same number of
            # silent samples in place, so later audio is not pulled earlier than its video.
            self.audio_blocks_dropped += 1
            try:
                self._silence_pending += int(np.asarray(block).size)
            except Exception:
                pass

    def _audio_writer(self):
        try:
            with open(self.raw_path, "wb") as raw:
                while not self.stop_evt.is_set() or not self._audio_q.empty():
                    try:
                        block = self._audio_q.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    self._write_pending_silence(raw)
                    raw.write(np.asarray(block, dtype="<f4").tobytes())
                self._write_pending_silence(raw)
                raw.flush()
        except Exception as exc:
            self.error = (self.error + " · " if self.error else "") + f"audio writer: {exc}"

    def _write_pending_silence(self, raw):
        n = int(self._silence_pending)
        if n > 0:
            self._silence_pending -= n
            raw.write(np.zeros(n, dtype="<f4").tobytes())

    # -- video (GUI thread draws → queue → encoder thread)
    def _ffmpeg(self):
        import shutil
        try:
            ff = self.host._resolve_ffmpeg_binary()
            if ff:
                return ff
        except Exception:
            pass
        return shutil.which("ffmpeg")

    def _open_video(self):
        import os, subprocess
        w, h = self._video_size
        if self.video_format == "MCC":
            import mcc_media
            self._vpath = os.path.join(self.tmpdir, "video.MCC")
            self._venc = mcc_media.VideoWriter(self._vpath, w, h, self.VIDEO_FPS, audio_rate=self.sr, audio_channels=1)
            return True
        ff = self._ffmpeg()
        if not ff:
            self.error = "video take needs ffmpeg (audio is still recorded)"
            return False
        # GROOVEBOX_R23R_LIVE_TAKE_VIDEO_FIX_20261103: the recording-time encoder is ffmpeg's
        # built-in MJPEG (present in every ffmpeg build — the bundled one has no libx264, which
        # silently left takes without video). The final file is encoded with whatever this
        # ffmpeg build supports (the same picker the video export uses).
        self._vpath = os.path.join(self.tmpdir, "video.mkv")
        self._verr_path = os.path.join(self.tmpdir, "encoder.log")
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
               "-framerate", str(self.VIDEO_FPS), "-i", "-", "-an", "-c:v", "mjpeg", "-q:v", "2",
               "-pix_fmt", "yuvj420p", "-f", "matroska", self._vpath]
        try:
            self._verr = open(self._verr_path, "wb")
            self._venc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=self._verr)
        except Exception as exc:
            self.error = f"video encoder: {exc}"
            return False
        if self._venc.poll() is not None:
            self.error = "video encoder exited: " + self._encoder_log()
            self._venc = None
            return False
        return True

    def _encoder_log(self):
        try:
            with open(self._verr_path, "rb") as f:
                return f.read().decode(errors="replace").strip()[-300:] or "no message"
        except Exception:
            return "no message"

    def _video_writer(self):
        while True:
            try:
                fr = self._vq.get(timeout=0.2)
            except queue.Empty:
                if self.stop_evt.is_set():
                    break
                continue
            if fr is None:
                break
            try:
                enc = self._venc
                # LIVE_TAKE_SYNC_R31: a frame dropped while the queue was full is written as a
                # repeat of the previous frame in place, so the picture never runs ahead of the sound.
                self._write_frame(enc, fr)
                self._last_frame = fr
                self._written_src = getattr(self, "_written_src", 0) + 1
                # repeats for frames dropped right after this one (held in place → A/V stay aligned)
                for _ in range(int(self._dup_after.pop(self._written_src, 0))):
                    self._write_frame(enc, fr)
            except Exception as exc:
                log = self._encoder_log() if not hasattr(self._venc, "write") else ""
                self.error = f"video encoder stopped: {exc} {log}".strip()
                break

    def _write_frame(self, enc, fr):
        if hasattr(enc, "write"):
            enc.write(fr)
        else:
            enc.stdin.write(fr.tobytes())
        self.frames_written += 1

    def _equalize_streams(self, enc, pcm):
        """LIVE_TAKE_SYNC_R31: before the mux, pad the shorter stream so audio and video end
        together (held last frame / trailing silence). The mux uses -shortest, which used to
        cut the end of the audio whenever the picture stream was a few frames short."""
        fps, sr = float(self.VIDEO_FPS), float(max(1, self.sr))
        want_frames = int(round(pcm.size / sr * fps))
        last = self._last_frame if self._last_frame is not None else self._first_frame
        if enc is not None and last is not None and self.frames_written < want_frames:
            pad = min(want_frames - self.frames_written, int(fps * 3600))
            for _ in range(pad):
                self._write_frame(enc, last)
        need_samples = int(round(self.frames_written / fps * sr))
        if need_samples > pcm.size:
            pcm = np.concatenate([pcm, np.zeros(need_samples - pcm.size, dtype=np.float32)])
        return pcm

    def _prepare_video_worker(self):
        """Open the encoder and start its writer without blocking the UI thread."""
        try:
            if not self._open_video():
                self.want_video = False
                return
            if self.stop_evt.is_set():
                # A very short take may stop while FFmpeg is starting. Close the
                # just-opened sink instead of leaving an orphaned process/file.
                enc = self._venc
                try:
                    if hasattr(enc, "close"):
                        enc.close()
                    elif getattr(enc, "stdin", None) is not None:
                        enc.stdin.close()
                        enc.wait(timeout=5)
                except Exception:
                    try:
                        enc.kill()
                    except Exception:
                        pass
                return
            writer = threading.Thread(target=self._video_writer, name="live-take-video", daemon=True)
            self._video_writer_thread = writer
            self._threads.append(writer)
            writer.start()
        except Exception as exc:
            self.want_video = False
            self.error = (self.error + " · " if self.error else "") + f"video startup: {exc}"
        finally:
            self._video_ready.set()

    def start(self):
        self.played0 = int(getattr(self.engine, "played", 0))   # audio clock at take start (rig-timed frames)
        self.engine.rec = self._on_audio
        self.t0 = time.monotonic()
        audio_thread = threading.Thread(target=self._audio_writer, name="live-take-audio", daemon=True)
        audio_thread.start()
        self._threads.append(audio_thread)
        if self.want_video:
            # Popen, codec negotiation, file creation and MCC writer startup can
            # block on slow media; do not perform them in the Qt event callback.
            setup = threading.Thread(target=self._prepare_video_worker,
                                     name="live-take-video-start", daemon=True)
            self._video_setup_thread = setup
            setup.start()
        else:
            self._video_ready.set()

    def frames_due(self):
        """Return frame slots from recorded audio samples, not GUI wall time."""
        if not self.want_video:
            return 0
        samples = max(0, int(self.audio_samples))
        return max(1, (samples * int(self.VIDEO_FPS)) // max(1, self.sr))

    def push_frame(self, rgb):
        if not self.want_video:
            return False
        # Own a tightly packed immutable snapshot: QImage/NumPy buffers used by
        # the GUI painter can otherwise be reused while the encoder thread reads.
        try:
            frame = np.asarray(rgb)
            w, h = self._video_size
            if frame.shape != (h, w, 3):
                raise ValueError(f"expected {(h, w, 3)} RGB frame, got {frame.shape}")
            if frame.dtype != np.uint8:
                frame = np.clip(frame, 0, 255).astype(np.uint8)
            frame = np.ascontiguousarray(frame).copy()
            if self._first_frame is None:
                self._first_frame = frame.copy()
            self._vq.put_nowait(frame)
            self._accepted = getattr(self, "_accepted", 0) + 1
            ok = True
        except queue.Full:
            self.frames_dropped += 1
            self._frame_dups += 1          # held as a repeat of the previous frame (keeps A/V in sync)
            k = int(getattr(self, "_accepted", 0))
            if k > 0:
                self._dup_after[k] = self._dup_after.get(k, 0) + 1
            ok = False
        except Exception as exc:
            self.frames_dropped += 1
            self.error = f"video frame rejected: {exc}"
            ok = False
        # Count attempts even on a full queue so the GUI catch-up loop remains bounded.
        self._pushed = getattr(self, "_pushed", 0) + 1
        return ok

    @property
    def pushed(self):
        return getattr(self, "_pushed", 0)

    def push_frame_at(self, rgb, t_seconds):
        """RIG_TIMED_RECORD_R31: put a frame at the slot of the moment it depicts (not when it arrived);
        slots in between hold the previous frame. Frames older than the last written slot are skipped."""
        if not self.want_video:
            return False
        slot = int(round(max(0.0, float(t_seconds)) * self.VIDEO_FPS))
        if slot < self.pushed:
            return False
        last = getattr(self, "_timed_last", None)
        while self.pushed < slot and last is not None:
            self.push_frame(last)
        if self.pushed < slot:                       # nothing earlier yet: fill the start with this frame
            while self.pushed < slot:
                self.push_frame(rgb)
        ok = self.push_frame(rgb)
        self._timed_last = rgb
        return ok

    def _codecs(self, ff, container):
        try:
            return self.host._ffmpeg_encoder_args(ff, container)
        except Exception:
            return ("mpeg4", ["-qscale:v", "3"], "aac", ["-b:a", "192k"])

    def _mux_video(self, ff, wav):
        """Final video file from the MJPEG intermediate + the take's audio, in the chosen
        container, using encoders this ffmpeg build has. Returns [path] or []."""
        import os, subprocess
        vf = self.video_format
        notes = []
        if vf == "MKV":                         # MJPEG + FLAC are native: no re-encode of the picture
            dst = self.base + "-video.mkv"
            vc = ["-c:v", "copy", "-c:a", "flac"]
        else:
            container = "webm" if vf == "WEBM" else "mp4"
            vcodec, vargs, acodec, aargs = self._codecs(ff, container)
            if container == "webm" and vcodec not in ("libvpx", "libvpx-vp9"):
                container, notes = "mkv", ["this ffmpeg has no VP8/VP9 encoder — saved as MKV"]
                vcodec, vargs, acodec, aargs = "copy", [], "flac", []
            dst = self.base + "-video." + container
            vc = ["-c:v", vcodec, *vargs]
            if vcodec != "copy":
                vc += ["-pix_fmt", "yuv420p"]
            vc += ["-c:a", acodec, *aargs]
            if container == "mp4":
                vc += ["-movflags", "+faststart"]
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", self._vpath, "-i", wav,
                            "-map", "0:v:0", "-map", "1:a:0", *vc, "-shortest", dst],
                           capture_output=True, timeout=3600)
        if r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 1024:
            if notes:
                self.error = "; ".join(notes)
            return [dst]
        # Last resort: keep the picture — MJPEG + FLAC in MKV needs no optional encoder.
        alt = self.base + "-video.mkv"
        r2 = subprocess.run([ff, "-y", "-loglevel", "error", "-i", self._vpath, "-i", wav, "-map", "0:v:0",
                             "-map", "1:a:0", "-c:v", "copy", "-c:a", "flac", "-shortest", alt],
                            capture_output=True, timeout=3600)
        if r2.returncode == 0 and os.path.isfile(alt):
            self.error = (f"{vf} encode failed ({(r.stderr or b'').decode(errors='replace').strip()[-160:]}) — "
                          "saved the video as MKV instead")
            return [alt]
        self.error = "video mux failed: " + (r2.stderr or r.stderr or b"").decode(errors="replace").strip()[-200:]
        return []

    def _fallback_video(self, ff, wav, duration):
        """Publish a valid visible video even if the live frame pipe wrote zero frames."""
        import os, subprocess
        if not ff:
            return []
        w, h = self._video_size
        frame = self._first_frame
        if frame is None:
            frame = np.full((h, w, 3), 118, dtype=np.uint8)
        frame_path = os.path.join(self.tmpdir, "fallback-frame.ppm")
        try:
            with open(frame_path, "wb") as fp:
                fp.write(f"P6\n{w} {h}\n255\n".encode("ascii"))
                fp.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
            dst = self.base + "-video.mkv"
            r = subprocess.run(
                [ff, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1",
                 "-framerate", str(self.VIDEO_FPS), "-i", frame_path, "-i", wav,
                 "-t", f"{max(1.0 / self.VIDEO_FPS, float(duration)):.6f}",
                 "-map", "0:v:0", "-map", "1:a:0", "-c:v", "mjpeg", "-q:v", "2",
                 "-pix_fmt", "yuvj420p", "-c:a", "flac", "-shortest", dst],
                capture_output=True, timeout=900)
            if r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 1024:
                self.error = (self.error + " · " if self.error else "") + "video pipe recovered from a first-frame fallback (MKV)"
                return [dst]
            self.error = (self.error + " · " if self.error else "") + "video fallback failed: " + (r.stderr or b"").decode(errors="replace").strip()[-180:]
        except Exception as exc:
            self.error = (self.error + " · " if self.error else "") + f"video fallback failed: {exc}"
        return []

    def finish(self):
        """Stop capturing, write the take; returns the paths written. Runs off the GUI thread."""
        import os, shutil, subprocess
        if self.engine.rec == self._on_audio:
            self.engine.rec = None
        # The callback may already have captured the recording tap. Wait for
        # those in-flight blocks before signalling the disk writer to drain.
        deadline = time.monotonic() + 1.5
        while getattr(self.engine, "_callback_active", 0) and time.monotonic() < deadline:
            time.sleep(0.002)
        if getattr(self.engine, "_callback_active", 0):
            self.error = (self.error + " · " if self.error else "") + "audio callback drain timed out"
        setup = self._video_setup_thread
        if setup is not None and setup is not threading.current_thread():
            setup.join(timeout=45.0)
            if setup.is_alive():
                self.error = (self.error + " · " if self.error else "") + "video encoder startup timed out"
                self.stop_evt.set()
        try:
            writer = self._video_writer_thread
            if self._venc is not None and writer is not None and writer.is_alive():
                # The writer owns stdin. Wait for queue space so EOF is ordered
                # after every accepted frame instead of racing a full queue.
                self._vq.put(None, timeout=15.0)
        except Exception as exc:
            self.error = (self.error + " · " if self.error else "") + f"video queue shutdown: {exc}"
        self.stop_evt.set()
        for t in self._threads:
            t.join(timeout=60)
        self._threads = []
        self._video_writer_thread = None
        enc = self._venc
        out = []
        try:
            pcm = np.fromfile(self.raw_path, dtype="<f4") if os.path.isfile(self.raw_path) else np.zeros(0, np.float32)
            if pcm.size == 0 and (self.video_requested or self.frames_written or self._first_frame is not None):
                # Preserve a video take even if the audio callback was interrupted.
                elapsed = max(1.0 / self.VIDEO_FPS, time.monotonic() - (self.t0 or time.monotonic()))
                n_silence = max(1, int(round(max(elapsed, self.frames_written / float(self.VIDEO_FPS)) * self.sr)))
                pcm = np.zeros(n_silence, dtype=np.float32)
                self.error = (self.error + " · " if self.error else "") + "audio callback supplied no samples; video retained with silence"
            if pcm.size == 0 and not self.frames_written and self._first_frame is None:
                return out
            if enc is not None and self.frames_written > 0:
                try:
                    pcm = self._equalize_streams(enc, np.asarray(pcm, dtype=np.float32))
                except Exception as _eq_exc:
                    self.error = (self.error + " · " if self.error else "") + f"A/V length match: {_eq_exc}"
            from audio_os_backend import wavfile
            wav = os.path.join(self.tmpdir, "audio.wav")
            wavfile.write(wav, self.sr, pcm)                 # 32-bit float: no clipping, no limiter
            # LIVE_PLAYER_VIDEO_GUARANTEE_R38: if the UI frame producer missed
            # every frame (e.g. a minimized/hidden player), still finalize a
            # real video stream for the full audio duration instead of silently
            # delivering audio only. Use the first captured frame when possible;
            # otherwise a neutral slate keeps the export valid and visible.
            if self.video_requested and enc is not None and self.frames_written <= 0:
                try:
                    w, h = self._video_size
                    frame = self._first_frame
                    if frame is None:
                        frame = np.full((h, w, 3), 118, dtype=np.uint8)
                    frame = np.ascontiguousarray(frame, dtype=np.uint8)
                    duration = max(1.0 / self.VIDEO_FPS, pcm.size / float(max(1, self.sr)))
                    frame_count = max(1, min(200000, int(round(duration * self.VIDEO_FPS))))
                    for _ in range(frame_count):
                        if hasattr(enc, "write"):
                            enc.write(frame)
                        else:
                            enc.stdin.write(frame.tobytes())
                        self.frames_written += 1
                    self.error = (self.error + " · " if self.error else "") + "video frame stream recovered with a held first-frame/slate fallback"
                except Exception as _vf_exc:
                    self.error = (self.error + " · " if self.error else "") + f"video frame fallback failed: {_vf_exc}"
            ff = self._ffmpeg()
            af = self.audio_format
            if af == "WAV":
                shutil.copyfile(wav, self.base + ".wav"); out.append(self.base + ".wav")
            elif af == "MCC":
                import mcc_media
                out.append(mcc_media.encode_audio(self.base + ".MCC", pcm, self.sr, extra={"source": "live take"}))
            else:
                codec = {"FLAC": ["-c:a", "flac"], "MP3": ["-c:a", "libmp3lame", "-b:a", "320k"],
                         "OGG": ["-c:a", "libvorbis", "-q:a", "8"]}[af]
                path = self.base + "." + af.lower()
                if ff and subprocess.run([ff, "-y", "-loglevel", "error", "-i", wav, *codec, path],
                                         timeout=900).returncode == 0:
                    out.append(path)
                else:
                    shutil.copyfile(wav, self.base + ".wav"); out.append(self.base + ".wav")
                    self.error = f"this ffmpeg cannot write {af} — audio saved as WAV"
            if enc is not None and self.frames_written:
                if hasattr(enc, "write"):                     # MCC: lossless video + the take's audio
                    enc.write_audio(pcm); enc.close()
                    dst = self.base + "-video.MCC"
                    shutil.move(self._vpath, dst); out.append(dst)
                else:
                    try:
                        enc.stdin.close(); enc.wait(timeout=900)
                    except Exception:
                        pass
                    try:
                        self._verr.close()
                    except Exception:
                        pass
                    if ff and os.path.isfile(self._vpath):
                        out.extend(self._mux_video(ff, wav))
            else:
                if enc is not None:
                    try:
                        enc.close() if hasattr(enc, "write") else (enc.stdin.close(), enc.wait(timeout=30))
                    except Exception:
                        pass
                    try:
                        if getattr(self, "_verr", None) is not None:
                            self._verr.close()
                    except Exception:
                        pass
                if self.video_requested:
                    duration = pcm.size / float(max(1, self.sr))
                    out.extend(self._fallback_video(ff, wav, duration))
        finally:
            # R32.8 LIVE_TAKE_SALVAGE: a recorded picture is never deleted. If no finished video
            # file came out (mux failure, missing encoder, crash in finish), the raw intermediate
            # and the take's WAV are moved next to the other exports before the temp folder goes.
            try:
                has_video = any("-video." in os.path.basename(str(p)) for p in out)
                if self.video_requested and not has_video:
                    for src, suffix in ((getattr(self, "_vpath", None), "-video-raw" + os.path.splitext(str(getattr(self, "_vpath", "") or ".mkv"))[1]),
                                        (os.path.join(self.tmpdir, "audio.wav"), "-take-audio.wav")):
                        if src and os.path.isfile(src) and os.path.getsize(src) > 0:
                            dst = self.base + suffix
                            shutil.move(src, dst); out.append(dst)
                    if any("-video-raw" in str(p) for p in out):
                        self.error = (self.error + " · " if self.error else "") + "final video encode failed — raw recording kept (*-video-raw)"
            except Exception as _salv_exc:
                self.error = (self.error + " · " if self.error else "") + f"salvage: {_salv_exc}"
            try:
                with open(os.path.join(os.path.dirname(self.base), "live-takes.log"), "a", encoding="utf-8") as _lg:
                    _lg.write("%s  frames=%d dropped=%d  %s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), int(self.frames_written),
                              int(self.frames_dropped), " | ".join(str(p) for p in out) or "(nothing written)", self.error or ""))
            except Exception:
                pass
            shutil.rmtree(self.tmpdir, ignore_errors=True)
        return out


# ---------------------------------------------------------------------------
# Visual
# ---------------------------------------------------------------------------
LAYERS = (("rig", "Video rig picture", True), ("orbit", "Instrument orbit (rosette)", True),
          ("ring", "Waveform ring", True), ("labels", "Instrument names", True),
          ("strip", "Playlist strip", True), ("media", "Loaded media video", True),
          ("multidim", "🌀 Multidimensional world", True),
          ("camera", "Camera (picture-in-picture)", True),
          ("camera_full", "Camera full scene (blends with the rig — Tweaks ▸ camera blend, default 50 %)", False))


def _qimage_rgb(arr):
    a = np.ascontiguousarray(arr[:, :, :3], dtype=np.uint8)
    h, w = a.shape[:2]
    img = QImage(a.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return img.copy()          # own the pixels (the numpy buffer can go away)


def qimage_to_rgb(img):
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    ptr = img.constBits(); ptr.setsize(bpl * h)
    return np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl)[:, :w * 3].reshape(h, w, 3).copy()


# GROOVEBOX_R23R_VISUAL_TWEAKS_20261103: every look parameter of the add-on visualizer.
# (key, label, min, max, default) — integer slider units; see LiveVisual.paint_to for meaning.
TWEAKS = (
    ("orbit_radius", "Orbit radius %", 5, 100, 38),
    ("node_size", "Node size", 1, 40, 6),
    ("node_glow", "Hit glow size", 0, 60, 10),
    ("glow_decay", "Glow decay %/frame", 1, 60, 14),
    ("glow_boost", "Hit brightness %", 10, 300, 100),
    ("spokes", "Spoke width (0 = off)", 0, 20, 3),
    ("spin", "Orbit spin °/s", -360, 360, 0),
    ("ring_radius", "Ring radius % of orbit", 5, 200, 55),
    ("ring_amp", "Ring amplitude %", 0, 400, 35),
    ("ring_width", "Ring line width ×10", 2, 120, 16),
    ("ring_detail", "Ring detail (samples)", 32, 1024, 256),
    ("ring_hue", "Ring hue °", 0, 359, 195),
    ("ring_sat", "Ring saturation %", 0, 100, 40),
    ("ring_fill", "Ring fill alpha", 0, 255, 0),
    ("ring_spin", "Ring spin °/s", -360, 360, 0),
    ("symmetry", "Ring symmetry (copies)", 1, 16, 1),
    ("mirror", "Mirror copies (0/1)", 0, 1, 0),
    ("pitch_colors", "Pitch colours (0/1)", 0, 1, 1),
    ("node_hue", "Node hue ° (pitch colours off)", 0, 359, 280),
    ("saturation", "Node saturation %", 0, 150, 100),
    ("trails", "Trails %", 0, 97, 0),
    ("overlay_alpha", "Over video opacity %", 0, 100, 60),
    ("label_size", "Name size", 5, 24, 7),
    ("bg_light", "Background brightness %", 0, 100, 46),
    ("bg_hue", "Background hue °", 0, 359, 0),
    ("bg_sat", "Background saturation %", 0, 100, 0),
    ("vignette", "Vignette %", 0, 100, 35),
    ("strip_h", "Playlist strip height", 8, 80, 26),
    # R32.8 LIVE_CAMERA_BLEND: full-scene camera ⇄ generated rig (view AND recordings)
    ("camera_blend", "Camera full scene blend with rig %", 0, 100, 50),
    # R32.8 visualizer modes: 0 ring · 1 Lissajous · 2 radial spectrum · 3 spiral · 4 bars
    ("ring_mode", "Visualizer mode (0 ring 1 lissajous 2 spectrum 3 spiral 4 bars)", 0, 4, 0),
    ("spectrum_bands", "Spectrum bands", 8, 256, 64),
    ("lissajous_lag", "Lissajous lag (samples)", 1, 256, 23),
)
TWEAK_PRESETS = {
    "Default": {},
    "Minimal": {"spokes": 0, "node_size": 4, "node_glow": 4, "ring_width": 8, "label_size": 6, "vignette": 0},
    "Kaleidoscope": {"symmetry": 8, "mirror": 1, "ring_amp": 120, "ring_spin": 20, "spin": 12, "ring_sat": 90,
                     "ring_fill": 30, "trails": 60},
    "Neon trails": {"trails": 85, "glow_boost": 220, "node_glow": 30, "spokes": 6, "ring_width": 30,
                    "ring_sat": 100, "ring_hue": 300, "bg_light": 12},
    "Big bloom": {"orbit_radius": 46, "node_size": 12, "node_glow": 50, "glow_decay": 6, "ring_amp": 200},
}


# VISUAL_PRESETS_R31: 8 motion styles × 6 palettes (48) + broadcast looks, on top of the originals.
_MOTION_STYLES = {
    "Still": {"spin": 0, "ring_spin": 0, "trails": 0, "symmetry": 1, "mirror": 0, "spokes": 2, "glow_decay": 18},
    "Orbit": {"spin": 24, "ring_spin": -12, "trails": 30, "symmetry": 1, "spokes": 3, "orbit_radius": 40},
    "Kaleido": {"symmetry": 8, "mirror": 1, "ring_amp": 120, "ring_spin": 20, "spin": 12, "ring_fill": 30, "trails": 60},
    "Mandala": {"symmetry": 12, "mirror": 1, "ring_amp": 80, "ring_radius": 90, "ring_spin": 6, "ring_fill": 60,
                "spokes": 1, "node_size": 4},
    "Trails": {"trails": 88, "glow_boost": 220, "node_glow": 30, "spokes": 6, "ring_width": 30, "spin": 40},
    "Bloom": {"orbit_radius": 46, "node_size": 12, "node_glow": 50, "glow_decay": 6, "ring_amp": 200, "trails": 40},
    "Pulse": {"glow_decay": 40, "glow_boost": 300, "node_glow": 44, "ring_amp": 300, "ring_detail": 512, "vignette": 60},
    "Minimal": {"spokes": 0, "node_size": 4, "node_glow": 4, "ring_width": 8, "label_size": 6, "vignette": 0,
                "ring_detail": 128},
}
_PALETTES = {
    "Ice": {"ring_hue": 195, "ring_sat": 70, "node_hue": 200, "pitch_colors": 0, "bg_hue": 210, "bg_sat": 40, "bg_light": 10},
    "Ember": {"ring_hue": 18, "ring_sat": 90, "node_hue": 30, "pitch_colors": 0, "bg_hue": 10, "bg_sat": 50, "bg_light": 8},
    "Neon": {"ring_hue": 300, "ring_sat": 100, "node_hue": 285, "pitch_colors": 0, "bg_hue": 270, "bg_sat": 60, "bg_light": 6},
    "Aurora": {"ring_hue": 140, "ring_sat": 80, "pitch_colors": 1, "bg_hue": 180, "bg_sat": 45, "bg_light": 9},
    "Gold": {"ring_hue": 45, "ring_sat": 85, "node_hue": 42, "pitch_colors": 0, "bg_hue": 30, "bg_sat": 30, "bg_light": 7},
    "Mono": {"ring_sat": 0, "saturation": 0, "pitch_colors": 0, "bg_sat": 0, "bg_light": 4},
}
for _m, _mv in _MOTION_STYLES.items():
    for _c, _cv in _PALETTES.items():
        TWEAK_PRESETS[f"{_m} · {_c}"] = {**_mv, **_cv}
# R32.8: new visualizer modes, palettes and camera looks
_MOTION_STYLES.update({
    "Lissajous": {"ring_mode": 1, "lissajous_lag": 23, "ring_amp": 140, "trails": 70, "ring_spin": 8, "spokes": 0},
    "Spectrum": {"ring_mode": 2, "spectrum_bands": 96, "ring_amp": 160, "ring_radius": 60, "ring_spin": 4, "pitch_colors": 1},
    "Spiral": {"ring_mode": 3, "ring_amp": 120, "ring_spin": 30, "trails": 55, "symmetry": 2},
    "Bars": {"ring_mode": 4, "spectrum_bands": 48, "ring_amp": 140, "mirror": 1, "pitch_colors": 1, "spokes": 0},
    "Tunnel": {"symmetry": 16, "mirror": 1, "trails": 92, "ring_spin": 45, "ring_amp": 60, "ring_radius": 140},
    "Halo": {"ring_mode": 2, "spectrum_bands": 180, "symmetry": 2, "ring_radius": 110, "ring_amp": 70, "trails": 50, "vignette": 70},
})
_PALETTES.update({
    "Ocean": {"ring_hue": 190, "ring_sat": 85, "node_hue": 170, "pitch_colors": 0, "bg_hue": 215, "bg_sat": 70, "bg_light": 9},
    "Sunset": {"ring_hue": 330, "ring_sat": 85, "node_hue": 25, "pitch_colors": 0, "bg_hue": 300, "bg_sat": 45, "bg_light": 8},
    "Forest": {"ring_hue": 110, "ring_sat": 70, "node_hue": 85, "pitch_colors": 0, "bg_hue": 130, "bg_sat": 40, "bg_light": 6},
})
for _m in ("Lissajous", "Spectrum", "Spiral", "Bars", "Tunnel", "Halo"):
    for _c, _cv in _PALETTES.items():
        TWEAK_PRESETS[f"{_m} · {_c}"] = {**_MOTION_STYLES[_m], **_cv}
for _c in ("Ocean", "Sunset", "Forest"):
    for _m, _mv in _MOTION_STYLES.items():
        TWEAK_PRESETS[f"{_m} · {_c}"] = {**_mv, **_PALETTES[_c]}
TWEAK_PRESETS.update({
    "Camera · stage blend 50/50": {"camera_blend": 50, "overlay_alpha": 70, "bg_light": 0, "vignette": 30, "label_size": 5, "strip_h": 8},
    "Camera · mostly camera": {"camera_blend": 75, "overlay_alpha": 55, "ring_mode": 2, "spectrum_bands": 96, "label_size": 5, "strip_h": 8},
    "Camera · mostly rig": {"camera_blend": 25, "overlay_alpha": 70, "trails": 40, "label_size": 5, "strip_h": 8},
    "Camera · spectrum frame": {"camera_blend": 60, "ring_mode": 4, "mirror": 1, "spectrum_bands": 64, "pitch_colors": 1, "strip_h": 8},
})
TWEAK_PRESETS.update({
    "Broadcast · clean": {"label_size": 5, "strip_h": 8, "vignette": 20, "bg_light": 4, "spokes": 1, "trails": 35},
    "Broadcast · dark stage": {"bg_light": 0, "vignette": 70, "glow_boost": 180, "label_size": 5, "strip_h": 8},
    "Broadcast · bright": {"bg_light": 80, "bg_sat": 10, "ring_sat": 100, "saturation": 120, "vignette": 0, "label_size": 5},
    "Club strobe": {"glow_decay": 60, "glow_boost": 300, "node_glow": 60, "trails": 0, "ring_amp": 400, "bg_light": 0},
})


def tweak_defaults():
    return {k: d for k, _l, _a, _b, d in TWEAKS}


def _user_presets_path():
    import os
    try:
        import groovebox_paths
        return os.path.join(groovebox_paths.base_dir(), "live-visual-presets.json")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".groovebox-live-visual-presets.json")


def _user_presets():
    import json
    try:
        with open(_user_presets_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return {str(k): {str(a): int(b) for a, b in v.items()} for k, v in d.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _save_user_presets(d):
    import json, os
    path = _user_presets_path()
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
        os.replace(tmp, path)
    except Exception:
        pass


def load_tweaks():
    t = tweak_defaults()
    try:
        import compat_settings as _cs
        saved = _cs.load().get("live_visual_tweaks") or {}
        for k, v in dict(saved).items():
            if k in t:
                t[k] = int(v)
    except Exception:
        pass
    return t


def save_tweaks(t):
    try:
        import compat_settings as _cs
        st = dict(_cs.load()); st["live_visual_tweaks"] = {k: int(v) for k, v in t.items()}; _cs.save(st)
    except Exception:
        pass


class LiveVisual(QWidget):
    """Live view. Layers (each switchable): video rig picture, camera (corner / full),
    instrument orbit lit per hit (colour = pitch), waveform ring, names, playlist strip.
    Gray background (GROOVEBOX_R23R_GRAY_VIDEO_BG_20261103)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.plan = None
        self.engine = None
        self.glow = {}
        self.colors = {}
        self._last_ev = {}
        self.rig = None
        self.camera = None
        self.media_video = None
        self.host = None
        self._md_img = None
        self._md_key = None
        self.layers = {k: v for k, _t, v in LAYERS}
        self.tw = load_tweaks()          # shared dict (window + pop-outs)
        self._spin = 0.0
        self._ring_rot = 0.0
        self._t_last = time.monotonic()
        self._trail = {}                 # (w, h) -> QImage accumulating the moving layers
        self.on_seek = None

    def mousePressEvent(self, ev):
        p = self.plan
        rows = len((p or {}).get("rows") or [])
        if rows and self.on_seek is not None and self.layers.get("strip", True) and ev.position().y() >= self.height() - 30:
            bw = (self.width() - 16) / rows
            r = int((ev.position().x() - 8) // max(1.0, bw))
            if 0 <= r < rows:
                self.on_seek(r)
                return
        super().mousePressEvent(ev)

    def set_plan(self, plan, engine):
        self.plan, self.engine = plan, engine
        self.glow = {n: 0.0 for n in plan["names"]}
        self.colors = {}
        self._last_ev = {}

    def _color(self, hz):
        try:
            return QColor(_gb().frequency_color(hz)[0])
        except Exception:
            return QColor.fromHsv(int((math.log2(max(20.0, hz) / 20.0) * 36) % 360), 200, 255)

    def tick(self):
        now = time.monotonic()
        dt = min(0.2, max(0.0, now - self._t_last)); self._t_last = now
        tw = self.tw
        self._spin = (self._spin + math.radians(tw["spin"]) * dt) % (2 * math.pi)
        self._ring_rot = (self._ring_rot + math.radians(tw["ring_spin"]) * dt) % (2 * math.pi)
        p, e = self.plan, self.engine
        if not p or not e:
            self.update(); return
        ri = e.row_idx
        pos = e.position_seconds()
        decay = 1.0 - tw["glow_decay"] / 100.0
        for k in list(self.glow):
            self.glow[k] *= decay
        boost = tw["glow_boost"] / 100.0
        if 0 <= ri < len(p["rows"]):
            last = self._last_ev.get(ri, -1.0)
            for (t0, dur, name, hz, amp) in p["rows"][ri]:
                if last < t0 <= pos:
                    self.glow[name] = min(3.0, self.glow.get(name, 0.0) + boost * (0.6 + 0.6 * min(1.0, amp)))
                    self.colors[name] = self._color(hz)
            self._last_ev = {ri: pos}
        self.update()

    def paintEvent(self, _ev):
        qp = QPainter(self)
        try:
            self.paint_to(qp, self.width(), self.height())
        finally:
            qp.end()

    def render_rgb(self, w, h):
        """The live view drawn at exactly w×h (used by Record live play)."""
        img = QImage(int(w), int(h), QImage.Format.Format_RGB888)
        # Initialize every output pixel before painting. This protects recorded
        # frames from uninitialized/black buffers if an optional overlay fails.
        img.fill(QColor("#77797d"))
        qp = QPainter(img)
        try:
            qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            self.paint_to(qp, int(w), int(h))
        finally:
            qp.end()
        return qimage_to_rgb(img)

    def record_snapshot(self):
        """Capture all QWidget-owned visual state on the GUI thread.

        The returned painter model contains copied frames/arrays and no QWidget
        or host references; its render_rgb() is safe on the record worker lane.
        """
        p = self.plan or {}
        e = self.engine
        if e is None:
            raise RuntimeError("live visual has no active engine")
        row_idx = int(e.row_idx)
        position = float(e.position_seconds())
        scope = np.array(e.scope, dtype=np.float32, copy=True)

        def capture_feed(feed):
            if feed is None:
                return None
            try:
                frame = feed.latest()
                if frame is None:
                    return None
                if isinstance(frame, QImage):
                    return frame.copy()
                return np.array(frame, copy=True)
            except Exception:
                return None

        captured_plan = {
            "names": list(p.get("names") or []),
            # A playing plan is immutable for the lifetime of one engine.
            "rows": p.get("rows") or [],
            "row_dur": float(p.get("row_dur", 0.0) or 0.0),
        }
        return _LiveVisualRenderSnapshot(
            captured_plan, row_idx, position, scope,
            dict(self.layers), dict(self.tw), dict(self.glow),
            {k: QColor(v) for k, v in self.colors.items()},
            float(self._spin), float(self._ring_rot),
            capture_feed(self.rig), capture_feed(self.camera),
            capture_feed(self.media_video),
            self._md_img.copy() if isinstance(self._md_img, QImage) else None,
        )

    @staticmethod
    def _fit(qp, img, x, y, w, h):
        iw, ih = img.width(), img.height()
        if iw <= 0 or ih <= 0:
            return
        sc = min(w / iw, h / ih)
        dw, dh = iw * sc, ih * sc
        qp.drawImage(QRectF(x + (w - dw) / 2, y + (h - dh) / 2, dw, dh), img)

    def _node_color(self, nm):
        tw = self.tw
        if tw["pitch_colors"]:
            c = QColor(self.colors.get(nm, QColor("#8a97ad")))
        else:
            c = QColor.fromHsv(int(tw["node_hue"]) % 360, 200, 255)
        if tw["saturation"] != 100:
            h_, s_, v_, a_ = c.getHsv()
            c = QColor.fromHsv(max(0, h_), max(0, min(255, int(s_ * tw["saturation"] / 100.0))), v_, a_)
        return c

    def _paint_mode(self, qp, mode, sc, cx, cy, R, w, area_h):
        """R32.8 visualizer modes (all driven by the same live scope buffer, deterministic per frame)."""
        tw = self.tw
        if sc.size < 8:
            return
        sc = np.clip(np.nan_to_num(sc), -1.0, 1.0)
        col = QColor.fromHsv(int(tw["ring_hue"]) % 360, int(255 * tw["ring_sat"] / 100.0), 255, 220)
        pen = QPen(col, tw["ring_width"] / 10.0)
        qp.setBrush(Qt.BrushStyle.NoBrush)
        amp = R * tw["ring_amp"] / 100.0 + 1.0
        copies = max(1, int(tw["symmetry"]))
        rot = self._ring_rot
        if mode == 1:                                    # Lissajous: x = s[t], y = s[t - lag]
            lag = max(1, min(sc.size - 1, int(tw.get("lissajous_lag", 23))))
            n = max(16, min(sc.size - lag, int(tw["ring_detail"])))
            idx = np.linspace(lag, sc.size - 1, n).astype(int)
            xs, ys = sc[idx], sc[idx - lag]
            for c in range(copies):
                a = rot + 2 * math.pi * c / copies
                ca, sa = math.cos(a), math.sin(a)
                path = QPainterPath()
                for i in range(n):
                    x, y = float(xs[i]) * amp, float(ys[i]) * amp
                    pt = QPointF(cx + x * ca - y * sa, cy + x * sa + y * ca)
                    path.moveTo(pt) if i == 0 else path.lineTo(pt)
                qp.setPen(pen); qp.drawPath(path)
            return
        bands = max(8, min(256, int(tw.get("spectrum_bands", 64))))
        mag = np.abs(np.fft.rfft(sc * np.hanning(sc.size)))[1:]
        if mag.size < 2:
            return
        edges = np.unique(np.geomspace(1, mag.size, bands + 1).astype(int))
        vals = np.array([mag[edges[i] - 1:max(edges[i], edges[i + 1] - 1)].mean() for i in range(len(edges) - 1)])
        vals = np.log1p(vals * 4.0); vals = vals / (vals.max() + 1e-9)
        nb = len(vals)
        if mode == 2:                                    # radial spectrum
            r0 = R * tw["ring_radius"] / 100.0
            for c in range(copies):
                for i, v in enumerate(vals):
                    a = rot + 2 * math.pi * (i / nb / copies + c / copies) - math.pi / 2
                    hue = (int(tw["ring_hue"]) + i * 270 // max(1, nb)) % 360 if tw["pitch_colors"] else int(tw["ring_hue"]) % 360
                    qp.setPen(QPen(QColor.fromHsv(hue, int(255 * tw["ring_sat"] / 100.0), 255, 220), max(1.0, tw["ring_width"] / 10.0)))
                    r1 = r0 + float(v) * amp
                    qp.drawLine(QPointF(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), QPointF(cx + r1 * math.cos(a), cy + r1 * math.sin(a)))
        elif mode == 3:                                  # spiral: scope wound outward
            n = max(32, min(sc.size, int(tw["ring_detail"]) * 2))
            s2 = sc[np.linspace(0, sc.size - 1, n).astype(int)]
            for c in range(copies):
                path = QPainterPath()
                for i in range(n):
                    f = i / n
                    a = rot + 6 * math.pi * f + 2 * math.pi * c / copies
                    r = R * 0.1 + f * R + float(s2[i]) * amp * 0.35
                    pt = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
                    path.moveTo(pt) if i == 0 else path.lineTo(pt)
                qp.setPen(pen); qp.drawPath(path)
        else:                                            # bars along the bottom
            bw = w / nb
            for i, v in enumerate(vals):
                hue = (int(tw["ring_hue"]) + i * 270 // max(1, nb)) % 360 if tw["pitch_colors"] else int(tw["ring_hue"]) % 360
                c = QColor.fromHsv(hue, int(255 * tw["ring_sat"] / 100.0), 255, 200)
                bh = float(v) * area_h * 0.6 * tw["ring_amp"] / 100.0
                qp.fillRect(QRectF(i * bw + 1, area_h - bh, max(1.0, bw - 2), bh), c)
                if tw["mirror"]:
                    qp.fillRect(QRectF(i * bw + 1, 0, max(1.0, bw - 2), bh * 0.5), c)

    def _paint_moving(self, qp, w, area_h):
        """Ring + orbit (the parts that trails / spin / symmetry act on)."""
        tw, L, p, e = self.tw, self.layers, self.plan, self.engine
        cx, cy = w / 2, area_h / 2
        R = min(w, area_h) * tw["orbit_radius"] / 100.0
        mode = int(tw.get("ring_mode", 0))
        if e is not None and L.get("ring", True) and mode != 0:
            self._paint_mode(qp, mode, np.asarray(e.scope, dtype=np.float32), cx, cy, R, w, area_h)
        elif e is not None and L.get("ring", True):
            sc = np.asarray(e.scope, dtype=np.float32)
            n = max(16, min(len(sc), int(tw["ring_detail"])))
            sc = sc[np.linspace(0, len(sc) - 1, n).astype(int)]
            r0 = R * tw["ring_radius"] / 100.0
            ramp = R * tw["ring_amp"] / 100.0
            col = QColor.fromHsv(int(tw["ring_hue"]) % 360, int(255 * tw["ring_sat"] / 100.0), 255, 220)
            copies = max(1, int(tw["symmetry"]))
            for c in range(copies):
                for mir in ((1, -1) if tw["mirror"] else (1,)):
                    path = QPainterPath()
                    for i in range(n):
                        a = mir * (2 * math.pi * i / n / copies) + 2 * math.pi * c / copies + self._ring_rot - math.pi / 2
                        r = r0 + float(np.clip(sc[i], -1, 1)) * ramp
                        pt = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
                        path.moveTo(pt) if i == 0 else path.lineTo(pt)
                    if copies == 1 and not tw["mirror"]:
                        path.closeSubpath()
                    qp.setPen(QPen(col, tw["ring_width"] / 10.0))
                    if tw["ring_fill"] > 0:
                        fc = QColor(col); fc.setAlpha(int(tw["ring_fill"])); qp.setBrush(QBrush(fc))
                    else:
                        qp.setBrush(Qt.BrushStyle.NoBrush)
                    qp.drawPath(path)
        names = (p or {}).get("names") or []
        if L.get("orbit", True):
            for i, nm in enumerate(names):
                a = 2 * math.pi * i / max(1, len(names)) - math.pi / 2 + self._spin
                x, y = cx + R * math.cos(a), cy + R * math.sin(a)
                gl = float(self.glow.get(nm, 0.0))
                col = self._node_color(nm)
                if gl > 0.05 and tw["spokes"] > 0:
                    lc = QColor(col); lc.setAlpha(int(min(255, 90 * gl)))
                    qp.setPen(QPen(lc, 0.5 + tw["spokes"] * 0.8 * min(2.0, gl)))
                    qp.drawLine(QPointF(cx, cy), QPointF(x, y))
                rad = tw["node_size"] + tw["node_glow"] * min(2.0, gl)
                fill = QColor(col); fill.setAlpha(int(70 + min(185, 150 * gl)))
                qp.setPen(QPen(col.lighter(130), 1.4))
                qp.setBrush(QBrush(fill))
                qp.drawEllipse(QPointF(x, y), rad, rad)
                if L.get("labels", True) and len(names) <= 24:
                    qp.setPen(QColor(230, 235, 245, 170 + int(min(85, 60 * gl))))
                    qp.setFont(QFont("Sans", int(tw["label_size"])))
                    qp.drawText(QRectF(x - 70, y + rad + 1, 140, tw["label_size"] + 6),
                                Qt.AlignmentFlag.AlignHCenter, nm[:18])

    def paint_to(self, qp, w, h):
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        L, tw = self.layers, self.tw
        bgc = QColor.fromHsv(int(tw["bg_hue"]) % 360, int(255 * tw["bg_sat"] / 100.0), int(255 * tw["bg_light"] / 100.0))
        edge = QColor.fromHsv(int(tw["bg_hue"]) % 360, int(255 * tw["bg_sat"] / 100.0),
                              int(255 * tw["bg_light"] / 100.0 * (1.0 - 0.8 * tw["vignette"] / 100.0)))
        g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.7)
        g.setColorAt(0.0, bgc.lighter(115)); g.setColorAt(1.0, edge)
        qp.fillRect(QRectF(0, 0, w, h), QBrush(g))
        p, e = self.plan, self.engine
        strip_h = int(tw["strip_h"]) if L.get("strip", True) else 0
        area_h = max(10, h - strip_h)
        cam = self.camera.latest() if (self.camera is not None) else None
        if cam is not None and L.get("camera_full"):
            self._fit(qp, _qimage_rgb(cam), 0, 0, w, area_h)
        mv = self.media_video.latest() if (self.media_video is not None and L.get("media", True)) else None
        if mv is not None:
            if cam is not None and L.get("camera_full"):
                qp.setOpacity(1.0 - float(tw.get("camera_blend", 50)) / 100.0)
            self._fit(qp, _qimage_rgb(mv), 0, 0, w, area_h)
            qp.setOpacity(1.0)
        rig_frame = self.rig.latest() if (self.rig is not None and L.get("rig", True)) else None
        if rig_frame is not None:
            op = 0.5 if mv is not None else 1.0
            if cam is not None and L.get("camera_full"):
                # R32.8 LIVE_CAMERA_BLEND: the whole-scene camera and the generated rig mix
                # (camera_blend % camera, the rest rig) instead of the rig covering the camera.
                op = min(op, 1.0 - float(tw.get("camera_blend", 50)) / 100.0)
            if op > 0.0:
                qp.setOpacity(op)
                self._fit(qp, _qimage_rgb(rig_frame), 0, 0, w, area_h)
            qp.setOpacity(1.0)
        if cam is not None and L.get("camera", True) and not L.get("camera_full"):
            cw, ch = w * 0.30, area_h * 0.30
            qp.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
            qp.setBrush(Qt.BrushStyle.NoBrush)
            qp.drawRect(QRectF(w - cw - 10, area_h - ch - 10, cw, ch))
            self._fit(qp, _qimage_rgb(cam), w - cw - 10, area_h - ch - 10, cw, ch)
        # GROOVEBOX_R23R_MULTIDIM_SCENE_20261103: the multidimensional world on the composition clock
        if L.get("multidim", True) and self.host is not None and e is not None and p and e.row_idx >= 0:
            try:
                import multidim_scene as _mds
                tq = e.row_idx * float(p["row_dur"]) + e.position_seconds()
                key = (int(w), int(area_h), int(tq * 15))          # redrawn 15× a second
                if key != self._md_key:
                    W, Hh = max(16, int(w) // 2), max(16, int(area_h) // 2)
                    img = np.zeros((Hh, W, 3), dtype=np.float32)
                    _mds.render_layer(img, _mds.states_for_host(self.host, tq, max_programmes=2), tq, opacity=1.0)
                    self._md_img = _qimage_rgb(np.clip(img, 0, 255).astype(np.uint8))
                    self._md_key = key
                if self._md_img is not None:
                    qp.save()
                    qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
                    qp.drawImage(QRectF(0, 0, w, area_h), self._md_img)
                    qp.restore()
            except Exception:
                pass
        over = (tw["overlay_alpha"] / 100.0) if (rig_frame is not None or mv is not None
                                                  or (cam is not None and L.get("camera_full"))) else 1.0
        trails = tw["trails"] / 100.0
        if trails > 0.0:
            key = (int(w), int(area_h))
            acc = self._trail.get(key)
            if acc is None:
                if len(self._trail) > 4:
                    self._trail.clear()
                acc = QImage(int(w), int(area_h), QImage.Format.Format_ARGB32_Premultiplied)
                acc.fill(Qt.GlobalColor.transparent)
                self._trail[key] = acc
            tp = QPainter(acc)
            tp.setRenderHint(QPainter.RenderHint.Antialiasing)
            tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            tp.fillRect(QRectF(0, 0, w, area_h), QColor(0, 0, 0, int(255 * trails)))
            tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            self._paint_moving(tp, w, area_h)
            tp.end()
            qp.setOpacity(over)
            qp.drawImage(0, 0, acc)
        else:
            self._trail.clear()
            qp.setOpacity(over)
            self._paint_moving(qp, w, area_h)
        qp.setOpacity(1.0)
        rows = len((p or {}).get("rows") or [])
        if rows and strip_h:
            bw = (w - 16) / rows
            ri = e.row_idx if e is not None else -1
            for i in range(rows):
                busy = len(p["rows"][i])
                c = QColor.fromHsv((200 + i * 23) % 360, 120 if busy else 30, 120 + min(100, busy * 4))
                if i == ri:
                    c = QColor("#ffd166")
                qp.fillRect(QRectF(8 + i * bw, h - strip_h + 6, max(1.0, bw - 1), max(2, strip_h - 10)), c)
            if e is not None and 0 <= ri < rows and p["row_dur"] > 0:
                fx = 8 + (ri + min(1.0, e.position_seconds() / p["row_dur"])) * bw
                qp.setPen(QPen(QColor("#ffffff"), 2))
                qp.drawLine(QPointF(fx, h - strip_h + 2), QPointF(fx, h - 2))


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

class _CapturedFrameSource:
    def __init__(self, frame):
        self._frame = frame

    def latest(self):
        return self._frame


class _CapturedEngineState:
    def __init__(self, row_idx, position, scope):
        self.row_idx = int(row_idx)
        self._position = float(position)
        self.scope = scope

    def position_seconds(self):
        return self._position


class _LiveVisualRenderSnapshot:
    """Qt painter facade with no QWidget/host ownership, used by worker threads."""
    _fit = staticmethod(LiveVisual._fit)
    _node_color = LiveVisual._node_color
    _paint_moving = LiveVisual._paint_moving
    _paint_mode = LiveVisual._paint_mode
    paint_to = LiveVisual.paint_to

    def __init__(self, plan, row_idx, position, scope, layers, tw, glow, colors,
                 spin, ring_rot, rig, camera, media_video, md_image):
        self.plan = plan
        self.engine = _CapturedEngineState(row_idx, position, scope)
        self.layers = layers
        self.tw = tw
        self.glow = glow
        self.colors = colors
        self._spin = spin
        self._ring_rot = ring_rot
        self.rig = _CapturedFrameSource(rig) if rig is not None else None
        self.camera = _CapturedFrameSource(camera) if camera is not None else None
        self.media_video = _CapturedFrameSource(media_video) if media_video is not None else None
        self.host = None
        self._md_img = md_image
        self._md_key = None
        self._trail = {}

    def render_rgb(self, w, h):
        img = QImage(int(w), int(h), QImage.Format.Format_RGB888)
        img.fill(QColor("#77797d"))
        qp = QPainter(img)
        try:
            qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            self.paint_to(qp, int(w), int(h))
        finally:
            qp.end()
        return qimage_to_rgb(img)


# ---------------------------------------------------------------------------
# FULL CPU LIVE PLAY modes (Latitude 3510 class: 4c/8t, ~15 W)
# Real-time pool is affinity-aware and capped; recording is optional + isolated.
# ---------------------------------------------------------------------------
FULL_CPU_LIVE_PLAY_MODES = {
    # Minimal path: play only. No sCode visual pooling, no recorder.
    "play": {
        "label": "Just play (no pool, no record)",
        "pool_workers": 4,
        "record": False,
        "scode_pool_visual": False,
        "force_1080": False,
        "export_mcc": False,
        "description": "Lightest live path. Lowest latency. Best fallback on 15 W CPUs.",
    },
    # Practical "can it run?": sCode pools video against audio, no recording thread.
    "pool": {
        "label": "sCode pool (audio+visual, no record)",
        "pool_workers": 6,
        "record": False,
        "scode_pool_visual": True,
        "force_1080": True,
        "export_mcc": False,
        "description": "Canonical engine drives audio + 1080×1080 visual together. No recorder.",
    },
    # LIVE_4K_R31: 4K output with frame-parallel rig workers and adaptive internal resolution.
    "stream_4k": {
        "label": "4K stream (adaptive, all cores)",
        "pool_workers": 8,
        "record": False,
        "scode_pool_visual": True,
        "force_1080": False,
        "export_mcc": False,
        "rig_size": (3840, 2160),
        "rig_workers": 0,          # 0 = cores − 2
        "rig_processes": True,     # one render process per worker (own interpreter / GIL)
        "description": "3840×2160 output; render resolution adapts to hold ~30 fps; one rig worker per spare core.",
    },
    # Heaviest: pool + isolated single recording thread + MCC export after track.
    "record_pool": {
        "label": "sCode pool + record → MCC",
        "pool_workers": 5,
        "record": True,
        "scode_pool_visual": True,
        "force_1080": True,
        "export_mcc": True,
        "description": "Pooled audio/visual + 1 isolated record thread; stop exports MCC at 1080×1080.",
    },
}


def _live_play_cpu_count():
    try:
        import thread_budget
        return max(1, int(thread_budget.usable_cores()))
    except Exception:
        try:
            import os
            return max(1, len(os.sched_getaffinity(0)))
        except Exception:
            return max(1, int(os.cpu_count() or 1))


def _apply_live_play_thread_budget(mode_key, recording=None):
    """Cap live workers for the selected FULL CPU mode and actual take state."""
    cfg = dict(FULL_CPU_LIVE_PLAY_MODES.get(mode_key) or FULL_CPU_LIVE_PLAY_MODES["play"])
    ncpu = _live_play_cpu_count()
    record_requested = bool(cfg.get("record")) or bool(recording)
    # Recording adds an audio writer, a frame renderer and an encoder. Preserve
    # two logical processors for GUI/audio/OS when a take is active.
    max_pool = max(1, min(6, ncpu - (2 if record_requested else 1)))
    cfg["pool_workers"] = max(1, min(int(cfg.get("pool_workers", 4)), max_pool))
    cfg["record_requested"] = record_requested
    cfg["record_worker_reserve"] = 1 if record_requested else 0
    cfg["ncpu"] = ncpu
    # Never mutate process-wide CPU affinity here. sched_setaffinity(0, ...)
    # changes the GUI, PortAudio callback helpers, sCode and every other thread
    # in this process—not just the Live Player pool. Concurrency is capped above;
    # the OS scheduler remains free to migrate each worker as load changes.
    return cfg


def _scode_pool_visual_tick(host, visual, eng, force_1080=True):
    """Drive the live visual from the same canonical/sCode graph as audio (shared phase).

    Video yields under load: newest frame wins; intermediate frames may be skipped.
    SCODE_HYBRID_20261111: visual reads the control-rate vector; it does not re-evaluate.
    """
    try:
        import scode_hybrid as _hy
        seed = getattr(host, "project_seed", None) or getattr(host, "seed", 1)
        block = int(getattr(eng, "play_pos", 0.0) or 0)
        vec, _buf = _hy.pool_block(seed, "visual", block // 1024, float(getattr(eng, "play_pos", 0.0) or 0.0), 64)
        if visual is not None and hasattr(visual, "tw") and isinstance(visual.tw, dict):
            visual.tw["scode_vector"] = vec
            visual.tw["scode_pooled"] = True
    except Exception:
        pass
    try:
        opt = getattr(host, "_scode_optimizer", None)
        if opt is not None and hasattr(opt, "tick_visual_against_audio"):
            opt.tick_visual_against_audio(visual, eng)
            return True
        # Fallback: pull shared mixdown scope chunk / playhead into visual phase
        if visual is None or eng is None:
            return False
        pos = float(getattr(eng, "play_pos", 0.0) or 0.0)
        if hasattr(visual, "set_shared_phase"):
            visual.set_shared_phase(pos)
        elif hasattr(visual, "tw") and isinstance(visual.tw, dict):
            visual.tw["shared_phase"] = pos
            visual.tw["scode_pooled"] = True
            if force_1080:
                visual.tw["force_size"] = (1080, 1080)
        return True
    except Exception:
        return False


class ScenographBroadcast(QWidget):
    """LIVE_BROADCAST_EXPORT_LOOK_R31: full-screen output drawn by the same VideoSynthEngine that video
    exports use (render_frame(..., export=True)), fed with the Live Player's latest output audio.
    Frames are drawn on a render thread (≤1280×720, ≤30 fps); the GUI thread only blits them."""
    _frame_ready = pyqtSignal()

    def __init__(self, player):
        super().__init__(None)
        self.player = player
        self.setWindowTitle("Groovebox Broadcast")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._img = None
        self._stop = False
        self._frame_ready.connect(self.update)
        host = player.host
        try:
            import groovebox as _g
            _aim = getattr(host, "active_instrument_memory", None)
            nmem = len(_aim) if hasattr(_aim, "__len__") else int(getattr(host, "synth_count", 48) or 48)
            self.eng = _g.VideoSynthEngine(nmem)
            if hasattr(self.eng, "bind_app"):
                self.eng.bind_app(host)
            self.eng.fps = 30.0
            self._norm = float(getattr(_g, "MEUM_NORM", 1.0))
        except Exception as exc:
            self.eng = None
            self._err = str(exc)
        self._t0 = time.monotonic()
        self._thread = threading.Thread(target=self._loop, name="broadcast-render", daemon=True)
        self._thread.start()

    def _loop(self):
        fi = 0
        while not self._stop:
            t0 = time.monotonic()
            try:
                W, H = self.width(), self.height()
                k = min(1.0, 1280.0 / max(1, W), 720.0 / max(1, H))
                w, h = max(16, int(W * k)) & ~1, max(16, int(H * k)) & ~1
                eng = self.player.engine
                wave_ = np.array(eng.scope, dtype=np.float32) if eng is not None else np.zeros(1024, np.float32)
                if self.eng is not None:
                    self.eng.set_waveform(wave_, playhead=0.5)
                    self.eng.t = (time.monotonic() - self._t0) * self._norm
                    rgb = np.ascontiguousarray(np.asarray(self.eng.render_frame(w, h, export=True, frame_index=fi), dtype=np.uint8)[:, :, :3])
                    img = QImage(rgb.data, rgb.shape[1], rgb.shape[0], 3 * rgb.shape[1], QImage.Format.Format_RGB888).copy()
                    self._img = img
                    fi += 1
                    self._frame_ready.emit()
            except RuntimeError:
                return                       # widget deleted
            except Exception as exc:
                self._err = str(exc)
            spare = (1.0 / 30.0) - (time.monotonic() - t0)
            time.sleep(spare if spare > 0 else 0.005)

    def paintEvent(self, _e):
        qp = QPainter(self)
        try:
            img = self._img
            if img is not None:
                qp.drawImage(self.rect(), img)
            else:
                qp.fillRect(self.rect(), QColor(0, 0, 0))
                qp.setPen(QColor(200, 220, 240))
                qp.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, getattr(self, "_err", "") or "Starting broadcast…")
        finally:
            qp.end()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.close()

    def mouseDoubleClickEvent(self, _ev):
        self.close()

    def closeEvent(self, ev):
        self._stop = True
        super().closeEvent(ev)


class LivePlayerWindow(QDialog):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setWindowTitle("🎬 Live Player — watch the composition happen")
        self.setModal(False)
        self.resize(820, 680)
        self.engine = None
        self.rig = None
        self.camera = None
        self.recorder = None
        self._worker = None
        self._gen = 0
        self._record_frame_future = None
        self._record_frame_owner = None
        try:
            import thread_budget
            # Interactive so bulk sCode / export workers cannot starve the take.
            self._record_render_lane = thread_budget.make_lane(
                "live-player-record-frames", max_workers=1, max_pending=4, kind="interactive")
        except Exception:
            self._record_render_lane = None
        # Compatibility fallback is created lazily only when the shared lane
        # is unavailable. Saturation drops a video frame rather than creating
        # an unbudgeted thread or adding latency to the live take.
        self._record_local_pool = None
        self._popouts = []
        self._pending_msg = None
        self.visual = None   # guard: assigned later after all signals are connected
        lay = QVBoxLayout(self)

        # Row 1: transport
        top = QHBoxLayout()
        self.btn_play = QPushButton("▶ Play live")
        self.btn_stop = QPushButton("⏹ Stop")
        self.chk_loop = QCheckBox("Loop"); self.chk_loop.setChecked(True)
        self.spin_start = QSpinBox(); self.spin_start.setPrefix("from row "); self.spin_start.setRange(1, 9999)
        self.sld_key_bend = QSlider(Qt.Orientation.Horizontal)
        self.sld_key_bend.setRange(-12, 12); self.sld_key_bend.setValue(0); self.sld_key_bend.setFixedWidth(116)
        self.sld_key_bend.setToolTip("Live keyboard trigger pitch bend: ±12 semitones. Ctrl+wheel over the Live Player also bends; backing tracks are unaffected.")
        self.lbl_key_bend = QLabel("Key bend 0 st")
        self.sld_key_bend.valueChanged.connect(self._set_key_bend)
        self.btn_screens = QToolButton(); self.btn_screens.setText("🖥 Show on display ▾")
        self.btn_screens.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._screens_menu = QMenu(self.btn_screens)
        self._screens_menu.aboutToShow.connect(self._fill_screens_menu)
        self.btn_screens.setMenu(self._screens_menu)
        for wdg in (self.btn_play, self.btn_stop, self.chk_loop, self.spin_start):
            top.addWidget(wdg)
        top.addWidget(self.lbl_key_bend); top.addWidget(self.sld_key_bend)
        top.addStretch(1)
        # LIVE_FULLSCREEN_R31: broadcast to HDMI, window fullscreen, visual-only.
        self.btn_broadcast = QPushButton("📡 Broadcast to HDMI")
        self.btn_broadcast.setCheckable(True)
        self.btn_broadcast.setToolTip("Clean full-screen live view on the HDMI / external display (no cursor, no controls). "
                                      "Reconnects when the cable is plugged back in. Esc or double-click on it ends.")
        self.btn_broadcast.toggled.connect(self._broadcast_toggled)
        self.btn_fullscreen = QPushButton("⛶ Fullscreen")
        self.btn_fullscreen.setToolTip("Full-screen this player (F11). Esc leaves. F10 or double-click the view hides the controls.")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        self.cmb_broadcast_src = QComboBox()
        self.cmb_broadcast_src.addItem("Live view", "live")
        self.cmb_broadcast_src.addItem("Export look", "export")
        self.cmb_broadcast_src.setToolTip("What the HDMI broadcast shows: this player's live view, or the scenograph drawn by "
                                          "the same engine video exports use (driven by the live audio).")
        top.addWidget(self.cmb_broadcast_src)
        top.addWidget(self.btn_broadcast); top.addWidget(self.btn_fullscreen)
        top.addWidget(self.btn_screens)
        lay.addLayout(top)

        # Row 2: sound + picture
        opts = QHBoxLayout()
        self.chk_full = QCheckBox("Full process routine")
        self.chk_full.setToolTip("Render the full mixdown first (every engine, FX and master stage — the exact "
                                 "buffer Play / Export use) and stream that, so it sounds identical. Off = light "
                                 "engine: the instruments' own voices (as the keyboard plays them), starts instantly.")
        self.chk_rig = QCheckBox("Full video rig")
        self.chk_rig.setToolTip("Live frames from the real video engine (scenograph + the project's video plan), "
                                "newest frame wins so the picture never lags the sound. Live view only — exports "
                                "keep their own frame-exact renderer. Smaller rig size = more frames per second.")
        self.chk_rig.toggled.connect(self._rig_toggled)
        self.chk_rig.setChecked(True)  # visible video-synth/scenograph layer is part of the default live take
        self.cmb_rig_size = QComboBox()
        for lab, _sz in RIG_SIZES:
            self.cmb_rig_size.addItem(lab)
        self.cmb_rig_size.setToolTip("Live video rig resolution. Full HD 1080p and QHD 1440p are available; frame rate depends on engine load and hardware. Latest-frame delivery drops stale frames rather than building latency.")
        self.cmb_rig_size.currentIndexChanged.connect(lambda *_a: self._rig_toggled(self.chk_rig.isChecked()))
        # R32.8 RIG_SCALE: auto (holds frame rate) or a fixed render scale; 100 % = the full export image
        self.cmb_rig_scale = QComboBox()
        for lab in ("Scale auto", "Scale 100 % (export-identical)", "Scale 75 %", "Scale 50 %", "Scale 25 %"):
            self.cmb_rig_scale.addItem(lab)
        self.cmb_rig_scale.setToolTip("Render scale of the live video rig. The rig now uses the export engine's own settings, "
                                      "so at 100 % each live frame is the exported frame for that moment; lower scales trade "
                                      "detail for frame rate. Auto adapts to hold ~30 fps.")
        _rs = float(getattr(self.host, "live_rig_scale", 0.0) or 0.0)
        self.cmb_rig_scale.setCurrentIndex({1.0: 1, 0.75: 2, 0.5: 3, 0.25: 4}.get(_rs, 0))

        def _scale_changed(i):
            self.host.live_rig_scale = (0.0, 1.0, 0.75, 0.5, 0.25)[max(0, min(4, int(i)))]
            self._rig_toggled(self.chk_rig.isChecked())
        self.cmb_rig_scale.currentIndexChanged.connect(_scale_changed)
        self.btn_layers = QToolButton(); self.btn_layers.setText("🧅 Layers ▾")
        self.btn_layers.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_layers.setToolTip("Switch each layer of the live view (and of video takes) on / off")
        lm = QMenu(self.btn_layers)
        self._layer_actions = {}
        for key, title, default in LAYERS:
            act = lm.addAction(title); act.setCheckable(True); act.setChecked(default)
            act.toggled.connect(lambda on, k=key: self._set_layer(k, on))
            self._layer_actions[key] = act
        self.btn_layers.setMenu(lm)
        self.btn_tweak = QToolButton(); self.btn_tweak.setText("🎛 Tweak visuals ▾")
        self.btn_tweak.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_tweak.setToolTip("Every look parameter of the add-on visualizer (saved). Applies to pop-outs and video takes.")
        self.btn_tweak.setMenu(self._build_tweak_menu())
        for wdg in (self.chk_full, self.chk_rig, self.cmb_rig_size, self.cmb_rig_scale, self.btn_layers, self.btn_tweak):
            opts.addWidget(wdg)
        opts.addStretch(1)
        lay.addLayout(opts)

        # Row 3: live inputs
        ins = QHBoxLayout()
        self.chk_mic = QCheckBox("🎙 Mic into the mix")
        self.chk_mic.setToolTip("Your microphone joins the live mix and every take (recorded even when not monitored).")
        self.chk_mic.toggled.connect(lambda *_a: self._sync_mic())
        self.sld_mic = QSlider(Qt.Orientation.Horizontal); self.sld_mic.setRange(0, 200); self.sld_mic.setValue(100)
        self.sld_mic.setFixedWidth(110); self.sld_mic.setToolTip("Mic level (100 % = as captured; no limiter)")
        self.sld_mic.valueChanged.connect(self._mic_gain)
        self.chk_mic_mon = QCheckBox("monitor")
        self.chk_mic_mon.setToolTip("Also play the mic through the speakers (use headphones to avoid feedback)")
        self.chk_mic_mon.toggled.connect(lambda on: setattr(self.engine, "mic_monitor", bool(on)) if self.engine else None)
        self.lbl_mic = QLabel("")
        self.lbl_mic.setFixedWidth(70)
        self.chk_cam = QCheckBox("🎥 Camera layer")
        self.chk_cam.setToolTip("Layer your camera onto the live view and video takes (corner or full screen in Layers ▾).")
        self.chk_cam.toggled.connect(self._cam_toggled)
        for wdg in (self.chk_mic, self.sld_mic, self.chk_mic_mon, self.lbl_mic, self.chk_cam):
            ins.addWidget(wdg)
        ins.addStretch(1)
        lay.addLayout(ins)

        # Media deck + mixer (GROOVEBOX_R23R_LIVE_MEDIA_DECK_20261103)
        med = QHBoxLayout()
        self.btn_media = QPushButton("📂 Load media…")
        self.btn_media.setToolTip("Any audio or video file (MP3 / WAV / FLAC / MP4 / MKV / .MCC …) plays under the "
                                  "composition; video becomes a layer. Keys, mic, DJ FX and Record work on top.")
        self.btn_media.clicked.connect(self._load_media_dialog)
        self.btn_media_clear = QPushButton("✕"); self.btn_media_clear.setFixedWidth(30)
        self.btn_media_clear.setToolTip("Unload the media"); self.btn_media_clear.clicked.connect(self._clear_media)
        self.lbl_media = QLabel("no media"); self.lbl_media.setMinimumWidth(140)
        self.chk_media_loop = QCheckBox("loop"); self.chk_media_loop.setChecked(True)
        self.chk_media_loop.toggled.connect(lambda on: setattr(self._media, "loop", bool(on)) if self._media else None)
        self.chk_comp = QCheckBox("Composition"); self.chk_comp.setChecked(True)
        self.chk_comp.setToolTip("Off = play only the media (+ keys / mic) — e.g. jam over a track")
        for wdg in (self.btn_media, self.btn_media_clear, self.lbl_media, self.chk_media_loop, self.chk_comp):
            med.addWidget(wdg)
        med.addStretch(1)
        lay.addLayout(med)
        mixr = QHBoxLayout()
        mixr.addWidget(QLabel("Mix:"))
        self._mix_sliders = {}
        for key, label, tip in (("comp", "comp", "Composition level"), ("media", "media", "Loaded media level"),
                                ("keys", "keys", "Keyboard notes level")):
            mixr.addWidget(QLabel(label))
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, 200); sl.setValue(100); sl.setFixedWidth(90)
            sl.setToolTip(tip + " (100 % = unity; no limiter)")
            sl.valueChanged.connect(lambda v, k=key: self._mix_changed(k, v))
            mixr.addWidget(sl); self._mix_sliders[key] = sl
        mixr.addWidget(QLabel("master"))
        self.sld_master = QSlider(Qt.Orientation.Horizontal); self.sld_master.setRange(0, 100); self.sld_master.setFixedWidth(90)
        try:
            self.sld_master.setValue(int(round(float(getattr(host, "master_volume", 0.72)) * 100)))
        except Exception:
            self.sld_master.setValue(72)
        self.sld_master.setToolTip("Master volume (the same master as the main window)")
        self.sld_master.valueChanged.connect(self._master_changed)
        mixr.addWidget(self.sld_master)
        mixr.addStretch(1)
        lay.addLayout(mixr)

        # DJ FX rack (master bus) (GROOVEBOX_R23R_LIVE_DJ_FX_20261103)
        djr = QHBoxLayout()
        djr.addWidget(QLabel("🎚 Meum FX:"))
        self._fx_params = DJChain(LIGHT_SR).p      # template; each engine gets its own chain with these values
        self.chk_fx_master = QCheckBox("FX on"); self.chk_fx_master.setChecked(True)
        self.chk_fx_master.toggled.connect(lambda on: self._fx_set("enabled", bool(on)))
        djr.addWidget(self.chk_fx_master)
        self._fx_bypass_checks = {}
        for _fxkey, _fxlabel in (("filter_enabled", "Fractal"), ("echo_enabled", "EQR"),
                                 ("stutter_enabled", "Repeat"), ("crush_enabled", "∞M Drive"),
                                 ("gate_enabled", "PKP")):
            _cb = QCheckBox(_fxlabel); _cb.setChecked(True)
            _cb.toggled.connect(lambda on, key=_fxkey: self._fx_set(key, bool(on)))
            djr.addWidget(_cb); self._fx_bypass_checks[_fxkey] = _cb
        self.sld_filter = QSlider(Qt.Orientation.Horizontal); self.sld_filter.setRange(-100, 100); self.sld_filter.setValue(0)
        self.sld_filter.setFixedWidth(120)
        self.sld_filter.setToolTip("Fractallizer tilt: left = subharmonic family (darker), right = superharmonic family (brighter), centre = off (double-click resets). Replaces the old LP/HP filter.")
        self.sld_filter.valueChanged.connect(lambda v: self._fx_set("filter", float(v)))
        self.sld_filter.mouseDoubleClickEvent = lambda _e: self.sld_filter.setValue(0)
        djr.addWidget(QLabel("tilt")); djr.addWidget(self.sld_filter)
        self.sld_echo = QSlider(Qt.Orientation.Horizontal); self.sld_echo.setRange(0, 100); self.sld_echo.setFixedWidth(80)
        self.sld_echo.setToolTip("EQR origin-z contribution (0–50 % wet). The division menu is kept for saved settings.")
        self.sld_echo.valueChanged.connect(lambda v: self._fx_set("echo", float(v)))
        self.cmb_echo = QComboBox(); self.cmb_echo.addItems(["1/16", "1/8", "3/16", "1/4", "3/8", "1/2", "1"])
        self.cmb_echo.setCurrentText("1/8")
        self.cmb_echo.currentTextChanged.connect(lambda t: self._fx_set("echo_div", self._beats(t)))
        djr.addWidget(QLabel("EQR")); djr.addWidget(self.sld_echo); djr.addWidget(self.cmb_echo)
        self._stutter_btns = []
        for lab in ("1/4", "1/8", "1/16"):
            b = QPushButton(f"⟲{lab}"); b.setCheckable(True); b.setFixedWidth(52)
            b.setToolTip(f"Stutter: repeat the last {lab} note while on")
            b.toggled.connect(lambda on, bb=b, t=lab: self._stutter(bb, t, on))
            djr.addWidget(b); self._stutter_btns.append(b)
        self.sld_crush = QSlider(Qt.Orientation.Horizontal); self.sld_crush.setRange(0, 100); self.sld_crush.setFixedWidth(70)
        self.sld_crush.setToolTip("∞M HyperDrive depth (Meum-spaced resonant drive; the master hard clipper is the only ceiling)")
        self.sld_crush.valueChanged.connect(lambda v: self._fx_set("crush", float(v)))
        djr.addWidget(QLabel("∞M")); djr.addWidget(self.sld_crush)
        self.sld_gate = QSlider(Qt.Orientation.Horizontal); self.sld_gate.setRange(0, 100); self.sld_gate.setFixedWidth(70)
        self.sld_gate.setToolTip("PKP gate depth: tempo-synced book-isn envelope (click-free, no square edges)")
        self.sld_gate.valueChanged.connect(lambda v: self._fx_set("gate", float(v)))
        self.cmb_gate = QComboBox(); self.cmb_gate.addItems(["1/16", "1/8", "1/4", "1/2"]); self.cmb_gate.setCurrentText("1/16")
        self.cmb_gate.currentTextChanged.connect(lambda t: self._fx_set("gate_div", self._beats(t)))
        djr.addWidget(QLabel("PKP")); djr.addWidget(self.sld_gate); djr.addWidget(self.cmb_gate)
        b_reset = QPushButton("reset FX"); b_reset.clicked.connect(self._fx_reset)
        djr.addWidget(b_reset)
        djr.addStretch(1)
        lay.addLayout(djr)

        # Row 4: record
        recr = QHBoxLayout()
        self.chk_rec = QCheckBox("⏺ Record live play")
        self.chk_finish = QCheckBox("finish take")
        self.chk_finish.setChecked(True)
        self.chk_finish.setToolTip("After the take: trim silence, remove DC, peak-normalize, short fade, and report before/after loudness.")
        self.chk_rec.setToolTip("Save exactly what you hear (composition + keys + mic) and, with 'video', exactly "
                                "what the live view shows (all enabled layers incl. camera). A quick take — use "
                                "Export for the high-quality file.")
        self.chk_rec.toggled.connect(self._rec_toggled)
        self.chk_rec_video = QCheckBox("with video"); self.chk_rec_video.setChecked(True)
        self.cmb_rec_audio = QComboBox(); self.cmb_rec_audio.addItems(LiveRecorder.AUDIO_FORMATS)
        self.cmb_rec_audio.setToolTip("Audio take format (WAV = 32-bit float, MCC = lossless Groovebox media)")
        self.cmb_rec_video = QComboBox(); self.cmb_rec_video.addItems(LiveRecorder.VIDEO_FORMATS)
        self.cmb_rec_video.setToolTip("Video take format (MCC = lossless RGB + audio)")
        self.lbl_rec = QLabel("")
        for wdg in (self.chk_rec, self.chk_finish, QLabel("audio"), self.cmb_rec_audio, self.chk_rec_video, self.cmb_rec_video, self.lbl_rec):
            recr.addWidget(wdg)
        recr.addStretch(1)
        lay.addLayout(recr)
        try:   # GROOVEBOX_R23R_SAVE_TO_DRIVE_20261103: takes can go straight onto a USB / SD drive
            lay.addWidget(host._make_export_target_picker(self))
        except Exception:
            pass

        # FULL CPU LIVE PLAY mode row (Latitude 3510-aware)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("FULL CPU LIVE PLAY:"))
        self.cmb_full_cpu_mode = QComboBox()
        for key, cfg in FULL_CPU_LIVE_PLAY_MODES.items():
            self.cmb_full_cpu_mode.addItem(cfg["label"], key)
        self.cmb_full_cpu_mode.setToolTip(
            "Three variants for 4c/8t CPUs:\n"
            "• Just play — no pool, no record (lightest)\n"
            "• sCode pool — audio+visual share canonical phase, no record\n"
            "• sCode pool + record → MCC — pooled + isolated record thread, then export"
        )
        try:
            self.cmb_full_cpu_mode.setCurrentIndex(1)  # default: pool (practical)
        except Exception:
            pass
        self.cmb_full_cpu_mode.currentIndexChanged.connect(self._on_full_cpu_mode_changed)
        mode_row.addWidget(self.cmb_full_cpu_mode, 1)
        self.lbl_full_cpu_info = QLabel("")
        self.lbl_full_cpu_info.setStyleSheet("color:#9fd4ff;font-size:9pt;")
        mode_row.addWidget(self.lbl_full_cpu_info, 2)
        lay.addLayout(mode_row)
        try:
            self._on_full_cpu_mode_changed()
        except Exception:
            pass

        self.visual = LiveVisual(self)
        self.visual.host = host
        self.visual.on_seek = self.seek
        lay.addWidget(self.visual, 1)
        self.visual.installEventFilter(self)       # double-click → visual-only toggle
        self._broadcast_view = None
        self._controls_hidden = False
        try:
            QApplication.instance().screenAdded.connect(self._on_screen_added)
            QApplication.instance().screenRemoved.connect(self._on_screen_removed)
        except Exception:
            pass
        self.status = QLabel("Light engine: the composition's own instrument voices + live view. "
                             "Keys keep playing on top. Space = play / stop.")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self._format_like_performance(lay)
        self.btn_play.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_play.setToolTip("Play the composition live (Space toggles play / stop)")
        for b in (self.btn_play, self.btn_stop):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # Space = play / stop, never "click the focused button"
        for b, c in ((self.btn_play, "#3ddc84"), (self.btn_stop, "#ff6b6b")):
            b.setStyleSheet("QPushButton{background:%s22;color:%s;border:1px solid %s;border-radius:8px;"
                            "padding:5px 12px;font-weight:700}" % (c, c, c))
        self._media = None
        self._media_video = None
        self._media_pending = None
        self._media_load_generation = 0
        self._record_finish_generation = 0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.timer.start()              # the view stays live (camera) even while stopped
        # Ctrl+wheel is reserved here for live-key pitch bend, not UI zoom. Plain
        # wheel events continue to scroll normally through child scroll areas.
        for _widget in [self] + list(self.findChildren(QWidget)):
            try: _widget.installEventFilter(self)
            except Exception: pass
        self._set_key_bend(int(self.sld_key_bend.value()))

    def _set_key_bend(self, value):
        st = max(-12, min(12, int(value)))
        self.host._live_player_pitch_bend_semitones = float(st)
        try:
            _jam = getattr(self.host, "_live_jam_controller", None)
            if _jam is not None:
                _jam.record_performance_event("pitch_bend", semitones=float(st), source="live_player")
        except Exception:
            pass
        if hasattr(self, "lbl_key_bend"):
            self.lbl_key_bend.setText(f"Key bend {st:+d} st")

    def eventFilter(self, watched, event):
        try:
            if watched is getattr(self, "visual", None) and event.type() == QEvent.Type.MouseButtonDblClick:
                self.toggle_controls(); return True
        except Exception:
            pass
        try:
            # Trackpad pinch/zoom gestures are a continuous live-key tuner.
            # Qt reports the gesture delta; map it to semitone movement.
            if event.type() == QEvent.Type.NativeGesture:
                gesture = event.gestureType()
                zoom_gesture = getattr(Qt.NativeGestureType, "ZoomNativeGesture", None)
                if zoom_gesture is not None and gesture == zoom_gesture:
                    delta = float(event.value() or 0.0)
                    if abs(delta) > 1e-6:
                        step = max(-3, min(3, int(round(delta * 12.0))))
                        if step == 0:
                            step = 1 if delta > 0 else -1
                        self.sld_key_bend.setValue(max(-12, min(12, self.sld_key_bend.value() + step)))
                    event.accept()
                    return True
            if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = int(event.angleDelta().y() or event.angleDelta().x())
                if delta:
                    steps = max(1, int(round(abs(delta) / 120.0)))
                    direction = 1 if delta > 0 else -1
                    self.sld_key_bend.setValue(max(-12, min(12, self.sld_key_bend.value() + direction * steps)))
                    event.accept()
                    return True
        except Exception:
            pass
        return False

    # -- layers / displays --------------------------------------------------
    def _set_layer(self, key, on):
        for v in self._views():
            v.layers[key] = bool(on)
            v.update()

    def _fill_screens_menu(self):
        m = self._screens_menu
        m.clear()
        for i, scr in enumerate(QApplication.screens()):
            g = scr.geometry()
            act = m.addAction(f"Display {i + 1}: {scr.name()} · {g.width()}×{g.height()}")
            act.triggered.connect(lambda _c=False, sc=scr: self._popout(sc))
        m.addSeparator()
        m.addAction("Close all pop-out views").triggered.connect(self._close_popouts)

    def _popout(self, screen):
        v = LiveVisual(None)
        v.setWindowTitle("Groovebox Live")
        v.on_seek = self.seek
        v.rig, v.camera = self.rig, self.camera
        v.layers = dict(self.visual.layers)
        v.host = self.host
        v.tw = self.visual.tw                     # same tweak dict: live edits apply everywhere
        v.media_video = getattr(self, "_media_video", None)
        if self.visual.plan is not None:
            v.set_plan(self.visual.plan, self.engine)
        v.setGeometry(screen.geometry())
        v.keyPressEvent = lambda ev, vv=v: vv.close() if ev.key() == Qt.Key.Key_Escape else None
        v.mouseDoubleClickEvent = lambda ev, vv=v: vv.close()
        v.show()
        try:
            v.windowHandle().setScreen(screen)
        except Exception:
            pass
        v.showFullScreen()
        self._popouts.append(v)

    # -- LIVE_PLAYER_STYLE_R31: dark deck like Performance / Live Jam -------------------
    _ACCENTS = ("#3fae6a", "#9b6cff", "#f2d17a", "#35b8ad", "#ff7a9c", "#5aa8ff", "#ffa94d", "#8ef07a", "#d07aff")

    def _format_like_performance(self, lay):
        from PyQt6.QtWidgets import QFrame
        self.setObjectName("livePlayer")
        self.setStyleSheet(
            "#livePlayer { background:#07111d; }"
            " #livePlayer QLabel { color:#cfe8f5; background:transparent; }"
            " #livePlayer QCheckBox { color:#d9f2ff; background:transparent; }"
            " #livePlayer QPushButton, #livePlayer QToolButton { background:#12334a; color:#e8faff; border:1px solid #39768e;"
            "   border-radius:7px; padding:4px 10px; font-weight:700; }"
            " #livePlayer QPushButton:hover, #livePlayer QToolButton:hover { background:#1a4c65; }"
            " #livePlayer QPushButton:checked { background:#3fae6a; color:#06140b; border-color:#9dffb0; }"
            " #livePlayer QComboBox, #livePlayer QSpinBox, #livePlayer QDoubleSpinBox, #livePlayer QLineEdit {"
            "   background:#091b2a; color:#e6f5ff; border:1px solid #35627d; border-radius:5px; padding:2px 6px; }"
            " #livePlayer QSlider::groove:horizontal { background:#1b3446; height:5px; border-radius:2px; }"
            " #livePlayer QSlider::handle:horizontal { background:#f2d17a; width:14px; margin:-5px 0; border-radius:7px; }"
            " QFrame#liveRow { background:rgba(10,28,44,225); border:1px solid #1f4459; border-radius:8px; }")
        title = QLabel("🎬 LIVE PLAYER  ·  live composition · keys · media · camera · broadcast")
        title.setStyleSheet("color:#f2d17a; font-size:15pt; font-weight:900; letter-spacing:0.6px; padding:2px 4px;")
        lay.insertWidget(0, title)
        rows = []
        for i in range(lay.count()):
            item = lay.itemAt(i)
            if item is not None and item.layout() is not None:
                rows.append(item.layout())
        for n, row in enumerate(rows):
            idx = lay.indexOf(row)
            if idx < 0:
                continue
            lay.takeAt(idx)
            frame = QFrame(); frame.setObjectName("liveRow")
            accent = self._ACCENTS[n % len(self._ACCENTS)]
            frame.setStyleSheet("QFrame#liveRow { border-left:4px solid %s; }" % accent)
            row.setContentsMargins(8, 3, 8, 3)
            frame.setLayout(row)
            lay.insertWidget(idx, frame)
        lay.setSpacing(4)
        self.status.setStyleSheet("color:#9fd4ff; padding:2px 6px;")

    # -- LIVE_FULLSCREEN_R31 -------------------------------------------------------
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            if self._controls_hidden:
                self.toggle_controls()
        else:
            self.showFullScreen()

    def _control_widgets(self):
        out = []
        lay = self.layout()

        def walk(item):
            w = item.widget()
            if w is not None:
                if w is not self.visual:
                    out.append(w)
                return
            sub = item.layout()
            if sub is not None:
                for i in range(sub.count()):
                    walk(sub.itemAt(i))
        for i in range(lay.count()):
            walk(lay.itemAt(i))
        return out

    def toggle_controls(self):
        """Visual-only mode: hide every control row, keep the live view (F10 / double-click)."""
        self._controls_hidden = not self._controls_hidden
        if self._controls_hidden:
            self._hidden_controls = [w for w in self._control_widgets() if w.isVisible()]
            for w in self._hidden_controls:
                w.hide()
            self.layout().setContentsMargins(0, 0, 0, 0)
        else:
            for w in getattr(self, "_hidden_controls", []):
                try: w.show()
                except RuntimeError: pass
            self._hidden_controls = []
            self.layout().setContentsMargins(9, 9, 9, 9)

    @staticmethod
    def _broadcast_screen():
        """HDMI / external display: a screen whose name says HDMI/DP/DVI, else any non-primary one."""
        app = QApplication.instance()
        prim = app.primaryScreen()
        screens = list(app.screens())
        for scr in screens:
            n = (scr.name() or "").upper()
            if scr is not prim and any(k in n for k in ("HDMI", "DP", "DISPLAYPORT", "DVI")):
                return scr
        for scr in screens:
            if scr is not prim:
                return scr
        return None

    def _broadcast_toggled(self, on):
        if not on:
            v, self._broadcast_view = self._broadcast_view, None
            if v is not None:
                try: v.close()
                except Exception: pass
            self.btn_broadcast.setText("📡 Broadcast to HDMI")
            return
        scr = self._broadcast_screen()
        if scr is None:
            self.status.setText("No HDMI / external display found. Plug one in: the broadcast starts by itself.")
            self.btn_broadcast.setText("📡 Waiting for HDMI…")
            return
        self._start_broadcast(scr)

    def _start_broadcast(self, scr):
        if self._broadcast_view is not None:
            try: self._broadcast_view.close()
            except Exception: pass
        if getattr(self, "cmb_broadcast_src", None) is not None and self.cmb_broadcast_src.currentData() == "export":
            v = ScenographBroadcast(self)            # not a LiveVisual: kept out of self._popouts
            v.setGeometry(scr.geometry()); v.show()
            try:
                v.windowHandle().setScreen(scr)
            except Exception:
                pass
        else:
            self._popout(scr)
            v = self._popouts[-1] if self._popouts else None
        if v is None:
            return
        v.setCursor(Qt.CursorShape.BlankCursor)
        v.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        v.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)   # keys stay with the player
        v.showFullScreen()
        def _ended(*_a, vv=v):
            if self._broadcast_view is vv:
                self._broadcast_view = None
                self.btn_broadcast.blockSignals(True); self.btn_broadcast.setChecked(False); self.btn_broadcast.blockSignals(False)
                self.btn_broadcast.setText("📡 Broadcast to HDMI")
        v.destroyed.connect(_ended)
        v.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._broadcast_view = v
        self.btn_broadcast.setText("📡 On air: %s" % (scr.name() or "display"))
        self.status.setText("Broadcasting the live view on %s (%d×%d)." % (scr.name(), scr.geometry().width(), scr.geometry().height()))

    def _on_screen_added(self, scr):
        if self.btn_broadcast.isChecked() and self._broadcast_view is None:
            QTimer.singleShot(600, lambda: self._broadcast_toggled(True))   # let the mode settle

    def _on_screen_removed(self, scr):
        v = self._broadcast_view
        if v is None:
            return
        try:
            gone = v.windowHandle() is not None and v.windowHandle().screen() is scr
        except Exception:
            gone = True
        if gone:
            self._broadcast_view = None
            try: v.close()
            except Exception: pass
            if self.btn_broadcast.isChecked():
                self.btn_broadcast.setText("📡 Waiting for HDMI…")
                self.status.setText("HDMI display disconnected; the broadcast resumes when it is back.")

    def _close_popouts(self):
        for v in self._popouts:
            try:
                v.close()
            except Exception:
                pass
        self._popouts = []

    # -- visual tweaks --------------------------------------------------------
    def _build_tweak_menu(self):
        from PyQt6.QtWidgets import QWidgetAction, QScrollArea, QFormLayout
        menu = QMenu(self)
        box = QWidget(); outer = QVBoxLayout(box); outer.setContentsMargins(8, 6, 8, 6)
        top = QHBoxLayout()
        self.cmb_tweak_preset = QComboBox(); self.cmb_tweak_preset.addItems(list(TWEAK_PRESETS))
        b_apply = QPushButton("apply preset"); b_reset = QPushButton("reset all")
        self.cmb_tweak_preset.addItems([n for n in _user_presets() if n not in TWEAK_PRESETS])
        self.cmb_tweak_preset.setMaxVisibleItems(24)
        b_next = QPushButton("next ▶"); b_rand = QPushButton("🎲"); b_save = QPushButton("save as…")
        b_next.setToolTip("Apply the next preset (also Ctrl+Right)"); b_rand.setToolTip("Random preset")
        top.addWidget(QLabel("Preset")); top.addWidget(self.cmb_tweak_preset, 1); top.addWidget(b_apply)
        top.addWidget(b_next); top.addWidget(b_rand); top.addWidget(b_save); top.addWidget(b_reset)
        outer.addLayout(top)
        b_next.clicked.connect(lambda: self._tweak_step(1))
        b_rand.clicked.connect(self._tweak_random)
        b_save.clicked.connect(self._tweak_save_as)
        self.cmb_tweak_preset.activated.connect(lambda _i: self._tweak_preset(self.cmb_tweak_preset.currentText()))
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setMinimumSize(380, 420)
        inner = QWidget(); form = QFormLayout(inner)
        self._tweak_sliders = {}
        # The menu is built before LiveVisual exists; seed sliders from the same saved tweaks it loads.
        tw = self.visual.tw if self.visual is not None else load_tweaks()
        for key, label, lo, hi, _d in TWEAKS:
            row = QHBoxLayout(); w = QWidget(); w.setLayout(row); row.setContentsMargins(0, 0, 0, 0)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(lo, hi); sl.setValue(int(tw.get(key, _d)))
            val = QLabel(str(sl.value())); val.setFixedWidth(36)
            sl.valueChanged.connect(lambda v, k=key, lab=val: self._tweak_set(k, v, lab))
            row.addWidget(sl, 1); row.addWidget(val)
            form.addRow(label, w)
            self._tweak_sliders[key] = sl
        sc.setWidget(inner); outer.addWidget(sc)
        b_apply.clicked.connect(lambda: self._tweak_preset(self.cmb_tweak_preset.currentText()))
        b_reset.clicked.connect(lambda: self._tweak_preset("Default"))
        wa = QWidgetAction(menu); wa.setDefaultWidget(box); menu.addAction(wa)
        return menu

    def _tweak_set(self, key, v, lab=None):
        self.visual.tw[key] = int(v)
        if lab is not None:
            lab.setText(str(int(v)))
        if not getattr(self, "_tweak_save_pending", False):
            self._tweak_save_pending = True
            QTimer.singleShot(600, self._tweak_save)

    def _tweak_save(self):
        self._tweak_save_pending = False
        save_tweaks(self.visual.tw)

    def _tweak_step(self, d):
        c = self.cmb_tweak_preset
        if c.count():
            c.setCurrentIndex((c.currentIndex() + d) % c.count())
            self._tweak_preset(c.currentText())
            self.status.setText("Visual preset: " + c.currentText())

    def _tweak_random(self):
        import random as _r
        c = self.cmb_tweak_preset
        if c.count():
            c.setCurrentIndex(_r.randrange(c.count())); self._tweak_preset(c.currentText())
            self.status.setText("Visual preset: " + c.currentText())

    def _tweak_save_as(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save visual preset", "Preset name:")
        name = str(name or "").strip()[:48]
        if not (ok and name):
            return
        presets = _user_presets()
        presets[name] = {k: int(v) for k, v in self.visual.tw.items()}
        _save_user_presets(presets)
        if self.cmb_tweak_preset.findText(name) < 0:
            self.cmb_tweak_preset.addItem(name)
        self.cmb_tweak_preset.setCurrentText(name)

    def _tweak_preset(self, name):
        vals = tweak_defaults(); vals.update(TWEAK_PRESETS.get(name, _user_presets().get(name, {})))
        for k, v in vals.items():
            sl = self._tweak_sliders.get(k)
            if sl is not None:
                sl.setValue(int(v))
            else:
                self.visual.tw[k] = int(v)

    # -- media deck / mixer / DJ FX -------------------------------------------
    def _load_media_dialog(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Load media into the Live Player", "",
                                              "Media (*.mp3 *.wav *.flac *.ogg *.opus *.m4a *.aac *.aif *.aiff "
                                              "*.mp4 *.mkv *.webm *.mov *.avi *.m4v *.MCC *.mcc);;All files (*)")
        if path:
            self.load_media(path)

    def load_media(self, path):
        """Decode media on the shared worker lane; publish only on the GUI thread."""
        import os
        from ui_runtime import submit_ui_task
        self._media_load_generation = int(getattr(self, "_media_load_generation", 0)) + 1
        generation = self._media_load_generation
        path = str(path)
        self.lbl_media.setText(f"loading {os.path.basename(path)}…")
        sr = self.engine.sr if self.engine is not None else LIGHT_SR

        def work():
            pcm = decode_audio_file(self.host, path, sr)
            vid = file_has_video(self.host, path)
            return (path, pcm, sr, bool(vid), "")

        def failed(exc):
            self.lbl_media.setText("load failed")
            self.status.setText(f"Media: {exc}")

        try:
            self._media_load_future = submit_ui_task(
                self, work, on_result=self._media_loaded, on_error=failed,
                generation_attr="_media_load_generation", generation=generation,
                key="media-load",
            )
        except Exception as exc:
            failed(exc)

    def _media_loaded(self, payload):
        import os
        from ui_runtime import assert_ui_thread
        assert_ui_thread("Live Player media publication")
        path, pcm, sr, vid, err = payload
        if err or pcm is None:
            self.lbl_media.setText("load failed"); self.status.setText(f"Media: {err}"); return
        self._clear_media()
        tr = MediaTrack(path, pcm, sr)
        tr.loop = self.chk_media_loop.isChecked()
        tr.gain = self._mix_sliders["media"].value() / 100.0
        self._media = tr
        self._media_has_video = bool(vid)
        self.lbl_media.setText(f"🎵 {os.path.basename(path)} · {pcm.size / float(sr):.0f} s" + (" · video" if vid else ""))
        if self.engine is not None and self.engine.stream is not None:
            self._attach_media(self.engine)
        else:
            self.status.setText("Media loaded — press Play (untick Composition to play only the media).")

    def _attach_media(self, eng):
        tr = getattr(self, "_media", None)
        if tr is None:
            return
        if tr.sr != eng.sr:
            try:
                import audio_os_backend as aob
                tr.pcm = aob._resample_for_hardware(tr.pcm, tr.sr, eng.sr); tr.sr = eng.sr
            except Exception:
                pass
        tr.pos = 0; tr.played = 0; tr.done = False
        eng.media = tr
        self._stop_media_video()
        if getattr(self, "_media_has_video", False):
            fv = FileVideoFeed(self.host, tr.path, tr.seconds)
            if fv.start():
                self._media_video = fv
                for v in self._views():
                    v.media_video = fv

    def _stop_media_video(self):
        fv = getattr(self, "_media_video", None)
        self._media_video = None
        for v in self._views():
            v.media_video = None
        if fv is not None:
            fv.close()

    def _clear_media(self):
        self._stop_media_video()
        if self.engine is not None:
            self.engine.media = None
        self._media = None
        self.lbl_media.setText("no media")

    def _mix_changed(self, key, v):
        g = float(v) / 100.0
        eng = self.engine
        if key == "media" and getattr(self, "_media", None) is not None:
            self._media.gain = g
        elif eng is not None and key == "comp":
            eng.comp_gain = g
        elif eng is not None and key == "keys":
            eng.keys_gain = g

    def _master_changed(self, v):
        try:
            self.host.master_volume = float(v) / 100.0
            vis = getattr(self.host, "slider_master_vol_visible", None)
            if vis is not None:
                vis.blockSignals(True)
                vis.setValue(int(round(float(v) * vis.maximum() / 100.0)) if vis.maximum() != 100 else int(v))
                vis.blockSignals(False)
        except Exception:
            pass

    @staticmethod
    def _beats(t):
        a, b = (t.split("/") + ["1"])[:2] if "/" in t else (t, "1")
        return float(a) / float(b) * 4.0 if "/" in t else float(a) * 4.0

    def _fx_set(self, key, val):
        self._fx_params[key] = val
        eng = self.engine
        if eng is not None and eng.fx is not None:
            eng.fx.p[key] = val
        if key == "enabled":
            enabled = bool(val)
            for widget in (getattr(self, "sld_filter", None), getattr(self, "sld_echo", None),
                           getattr(self, "cmb_echo", None), getattr(self, "sld_crush", None),
                           getattr(self, "sld_gate", None), *getattr(self, "_stutter_btns", [])):
                if widget is not None: widget.setEnabled(enabled)

    def _stutter(self, btn, lab, on):
        if on:
            for b in self._stutter_btns:
                if b is not btn and b.isChecked():
                    b.blockSignals(True); b.setChecked(False); b.blockSignals(False)
            self._fx_set("stutter", self._beats(lab))
        elif not any(b.isChecked() for b in self._stutter_btns):
            self._fx_set("stutter", 0.0)

    def _fx_reset(self):
        for sl in (self.sld_filter, self.sld_echo, self.sld_crush, self.sld_gate):
            sl.setValue(0)
        for b in self._stutter_btns:
            b.setChecked(False)

    def _views(self):
        alive = []
        for v in (self._popouts or []):
            try:
                if v.isVisible():
                    alive.append(v)
            except RuntimeError:
                pass
        self._popouts = alive
        return ([self.visual] if self.visual is not None else []) + alive

    # -- rig / camera / mic -------------------------------------------------
    def _rig_size(self):
        i = max(0, min(len(RIG_SIZES) - 1, self.cmb_rig_size.currentIndex()))
        return RIG_SIZES[i][1]

    def _rig_toggled(self, on):
        if self.rig is not None:
            self.rig.stop(); self.rig = None
            for v in self._views():
                v.rig = None
        if on and self.engine is not None and self.visual is not None and self.visual.plan is not None:
            self._start_rig(self.visual.plan, self.engine)

    def _start_rig(self, plan, eng):
        cfg = getattr(self, "_full_cpu_cfg", {}) or {}
        size = tuple(cfg.get("rig_size") or self._rig_size())
        workers = int(cfg.get("rig_workers", 1 if not cfg.get("scode_pool_visual") else 2))
        try:   # R32.8 DYNAMIC_RAM: each rig worker holds its own engine — cap by the memory tier
            import resource_governor as _rg
            _cap_w = int(_rg.recommend()["rig_workers"])
        except Exception:
            _cap_w = 8
        if workers <= 0:
            try:
                workers = max(1, len(os.sched_getaffinity(0)) - 2)
            except Exception:
                workers = max(1, (os.cpu_count() or 4) - 2)
        if cfg.get("rig_processes"):
            self.rig = ProcessVideoRig(self.host, plan, eng, size=size, workers=min(8, _cap_w, workers))   # true parallel
        else:
            self.rig = VideoRig(self.host, plan, eng, size=size, workers=min(8, _cap_w, workers))
        for v in self._views():
            v.rig = self.rig
        self.rig.start()

    def _cam_toggled(self, on):
        if self.camera is not None:
            self.camera.close(); self.camera = None
        if on:
            cam = CameraFeed(self.host)
            if cam.start():
                self.camera = cam
            else:
                self.status.setText(cam.error or "camera unavailable")
                self.chk_cam.blockSignals(True); self.chk_cam.setChecked(False); self.chk_cam.blockSignals(False)
        for v in self._views():
            v.camera = self.camera

    def _mic_gain(self, v):
        eng = self.engine
        if eng is not None and eng.mic is not None:
            eng.mic.gain = float(v) / 100.0

    def _sync_mic(self):
        eng = self.engine
        if eng is None or eng.stream is None:
            return
        want = self.chk_mic.isChecked()
        if want and eng.mic is None:
            mic = MicFeed(self.host, eng.sr)
            mic.gain = self.sld_mic.value() / 100.0
            if mic.start():
                eng.mic_monitor = self.chk_mic_mon.isChecked()
                eng.mic = mic
            else:
                self.status.setText(mic.error)
        elif not want and eng.mic is not None:
            mic, eng.mic = eng.mic, None
            mic.close()

    def _after_open(self):
        """Stream is running: DJ rack, media, mic, a pending take."""
        eng = self.engine
        if eng is not None:
            fx = DJChain(eng.sr); fx.p.update(self._fx_params)
            try:
                fx.bpm = float(self.visual.plan.get("bpm", 120.0)) if (self.visual is not None and self.visual.plan) else 120.0
            except Exception:
                pass
            eng.fx = fx
            self._attach_media(eng)
        self._sync_mic()
        if self.chk_rec.isChecked() and self.recorder is None:
            self._start_rec()

    # -- record --------------------------------------------------------------
    def _rec_toggled(self, on):
        if on and self.engine is not None and self.engine.stream is not None and self.recorder is None:
            self._start_rec()
        elif not on:
            self._finish_rec()

    def _start_rec(self):
        try:
            self.recorder = LiveRecorder(self.host, self.engine, self.cmb_rec_audio.currentText(),
                                         self.cmb_rec_video.currentText(), self.chk_rec_video.isChecked())
            if getattr(self, "_full_cpu_cfg", {}).get("force_1080"):
                self.recorder._video_size = (1080, 1080)
            if self.visual is not None:
                self._record_bg_tweaks = (int(self.visual.tw.get("bg_light", 46)), int(self.visual.tw.get("bg_sat", 0)))
                self.visual.tw["bg_light"] = 46
                self.visual.tw["bg_sat"] = 0
            self.recorder.start()
            # Prime the take with its first actual live-view frame rather than
            # waiting for the next 16 ms UI tick (important for short takes).
            self._record_frames()
            self.lbl_rec.setText("● REC")
            self.lbl_rec.setStyleSheet("color:#ff5470;font-weight:800;")
        except Exception as exc:
            self.recorder = None
            self.status.setText(f"Could not start the take: {exc}")

    def _record_frames(self):
        rec = self.recorder
        if rec is not None:
            self._update_rec_badge(rec)
        if rec is None or not rec.want_video or self.visual is None:
            return
        rig = self.rig
        if rig is not None and getattr(rig, "frame_fi", -1) >= 0 and getattr(self.visual, "layers", {}).get("rig", True):
            # RIG_TIMED_RECORD_R31: record rig frames at their own content time (exact A/V alignment).
            fi = int(rig.frame_fi)
            if fi != getattr(self, "_rec_rig_fi", -1):
                fr = rig.latest()
                if fr is not None:
                    self._rec_rig_fi = fi
                    w, h = rec._video_size
                    img = _qimage_rgb(fr)
                    if img.width() != w or img.height() != h:
                        img = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    pa = int(getattr(rig, "frame_played", -1))
                    if pa >= 0:
                        t_take = (pa - int(getattr(rec, "played0", 0))) / float(max(1, rec.sr))
                        rec.push_frame_at(qimage_to_rgb(img), t_take)
            return
        due = rec.frames_due()
        future = self._record_frame_future
        if future is not None:
            if not future.done():
                return
            self._record_frame_future = None
            owner, self._record_frame_owner = self._record_frame_owner, None
            try:
                fr = future.result()
                if owner is rec and self.recorder is rec:
                    # One current frame can cover at most four elapsed frame
                    # slots per UI tick; if the system is overloaded, skip video
                    # frames rather than blocking audio or growing latency.
                    pushed = 0
                    while rec.pushed < due and pushed < 4:
                        rec.push_frame(fr); pushed += 1
            except Exception as exc:
                rec.error = f"view capture: {exc}"
        if self.recorder is not rec or rec.pushed >= due:
            return
        try:
            snapshot = self.visual.record_snapshot()  # all QWidget reads/copies on GUI thread
            self._record_frame_owner = rec
            submitted = False
            lane = self._record_render_lane
            if lane is not None:
                try:
                    self._record_frame_future = lane.submit(
                        snapshot.render_rgb, *rec._video_size)
                    submitted = True
                except RuntimeError:
                    # Shared interactive lane saturated: skip this video frame
                    # rather than oversubscribing the global worker budget.
                    pass
            local = getattr(self, "_record_local_pool", None)
            if not submitted and lane is None:
                if local is None:
                    try:
                        from concurrent.futures import ThreadPoolExecutor
                        local = self._record_local_pool = ThreadPoolExecutor(
                            max_workers=1, thread_name_prefix="live-rec-frames-fallback")
                    except Exception:
                        local = None
                if local is not None:
                    self._record_frame_future = local.submit(
                        snapshot.render_rgb, *rec._video_size)
                    submitted = True
            if not submitted:
                rec.frames_dropped += 1
                # Do not set a sticky error; a later frame may still succeed.
        except Exception as exc:
            rec.error = f"view capture: {exc}"

    def _update_rec_badge(self, rec):
        """LIVE_REC_UI_R31: live take badge: elapsed · frames written · skipped (throttled to ~4 Hz)."""
        now = time.monotonic()
        if now - getattr(self, "_rec_badge_t", 0.0) < 0.25:
            return
        self._rec_badge_t = now
        try:
            el = max(0.0, now - float(rec.t0 or now))
            m, sec = divmod(int(el), 60)
            txt = "● REC %d:%02d" % (m, sec)
            if rec.want_video:
                txt += " · %d fr" % int(getattr(rec, "frames_written", 0) or getattr(rec, "pushed", 0) or 0)
                if rec.frames_dropped:
                    txt += " · %d skipped" % int(rec.frames_dropped)
            blink = int(el * 2) % 2 == 0
            self.lbl_rec.setText(txt)
            self.lbl_rec.setStyleSheet("color:%s;font-weight:800;" % ("#ff5470" if blink else "#ff9aac"))
        except Exception:
            pass

    def _export_mcc_after_take(self, paths):
        """After a full-track record_pool take, encourage MCC at 1080×1080."""
        try:
            if not getattr(self, "_export_mcc_after", False):
                return
            host = self.host
            if hasattr(host, "export_project_mcc"):
                QTimer.singleShot(400, lambda: host.export_project_mcc())
                self.status.setText((self.status.text() or "") + " · MCC export queued")
            elif paths:
                self.status.setText((self.status.text() or "") + " · take saved: " + ", ".join(str(p) for p in paths[:3]))
        except Exception as exc:
            print(f"[LivePlayer] MCC export: {exc}")

    def _finish_rec(self):
        rec, self.recorder = self.recorder, None
        self.lbl_rec.setText("")
        if rec is None:
            return
        if self.visual is not None and hasattr(self, "_record_bg_tweaks"):
            try:
                self.visual.tw["bg_light"], self.visual.tw["bg_sat"] = self._record_bg_tweaks
                del self._record_bg_tweaks
                self.visual.update()
            except Exception:
                pass
        self.status.setText("Saving live take…")
        from ui_runtime import submit_ui_task
        self._record_finish_generation = int(getattr(self, "_record_finish_generation", 0)) + 1
        generation = self._record_finish_generation

        def completed(paths):
            # This callback is delivered by ui_runtime on QApplication's thread.
            try:
                self._export_mcc_after_take(paths)
            except Exception:
                pass
            # GROOVEBOX_TAKE_FINISHER_20261111
            if getattr(self, "chk_finish", None) is not None and self.chk_finish.isChecked() and paths:
                try:
                    import take_finisher as _tf
                    reports = _tf.finish_paths(list(paths))
                    for r in reports:
                        if r.get("path"):
                            paths.append(r["path"])
                        b, a = r.get("before") or {}, r.get("after") or {}
                        if b and a:
                            msg_extra = f" · finished {b.get('rms_db')}→{a.get('rms_db')} dB RMS"
                            self.status.setText((self.status.text() or "") + msg_extra)
                except Exception as exc:
                    print(f"[LivePlayer] take finisher: {exc}")
            msg = ("● Saved live take: " + " + ".join(paths)) if paths else "Live take was empty."
            if rec.frames_dropped:
                msg += f" ({rec.frames_dropped} video frames held as repeats — disk was busy; sync kept)"
            if rec.error:
                msg += f" · {rec.error}"
            self.status.setText(msg)

        def failed(exc):
            self.status.setText(f"Live take could not be saved: {exc}")

        try:
            self._record_finish_future = submit_ui_task(
                self, rec.finish, on_result=completed, on_error=failed,
                generation_attr="_record_finish_generation", generation=generation,
                key="record-finish",
            )
        except Exception as exc:
            failed(exc)

    # -- control -----------------------------------------------------------
    def seek(self, row):
        self.spin_start.setValue(int(row) + 1)
        self.start()

    def is_active(self):
        return self.engine is not None and self.engine.stream is not None

    def start(self):
        self.stop()
        if self._teardown_busy():
            # The previous engine still owns the audio device; start once it is released.
            if not getattr(self, "_start_pending", False):
                self._start_pending = True
                self.status.setText("Releasing the previous audio stream…")
                def _retry():
                    if self._teardown_busy():
                        QTimer.singleShot(40, _retry); return
                    self._start_pending = False
                    self.start()
                QTimer.singleShot(40, _retry)
            return
        h = self.host
        self._gen += 1
        gen = self._gen
        # Apply FULL CPU LIVE PLAY budget before opening audio
        try:
            mode_key = self.cmb_full_cpu_mode.currentData() if hasattr(self, "cmb_full_cpu_mode") else "play"
            self._full_cpu_cfg = _apply_live_play_thread_budget(
                str(mode_key or "play"), recording=bool(getattr(self, "chk_rec", None) and self.chk_rec.isChecked()))
            cfg = self._full_cpu_cfg
            # FULL CPU choices select compute strategy only. Recording is an
            # independent user choice and must remain available in every mode.
            if cfg.get("rig_size") and hasattr(self, "chk_rig") and not self.chk_rig.isChecked():
                self.chk_rig.blockSignals(True); self.chk_rig.setChecked(True); self.chk_rig.blockSignals(False)   # 4K stream needs the rig
            if hasattr(self, "chk_rec") and cfg.get("record"):
                self.chk_rec.blockSignals(True); self.chk_rec.setChecked(True); self.chk_rec.blockSignals(False)
                if hasattr(self, "chk_rec_video"):
                    self.chk_rec_video.setChecked(True)
                if hasattr(self, "cmb_rec_video"):
                    for i in range(self.cmb_rec_video.count()):
                        if "MCC" in str(self.cmb_rec_video.itemText(i)).upper():
                            self.cmb_rec_video.setCurrentIndex(i); break
            self._scode_pool_visual = bool(cfg.get("scode_pool_visual"))
            self._export_mcc_after = bool(cfg.get("export_mcc"))
        except Exception as _fc_exc:
            print(f"[LivePlayer] full-cpu mode: {_fc_exc}")
            self._full_cpu_cfg = FULL_CPU_LIVE_PLAY_MODES["play"]
            self._scode_pool_visual = False
            self._export_mcc_after = False
        try:
            if getattr(h, "is_playing", False):
                h.stop_playback()
        except Exception:
            pass
        try:
            h._close_audition_stream()
        except Exception:
            pass
        try:
            h._geo_buffer_store()
        except Exception:
            pass
        try:
            plan = build_plan(h)
        except Exception as exc:
            self.status.setText(f"Could not read the composition: {exc}")
            return
        has_media = getattr(self, "_media", None) is not None
        if not self.chk_comp.isChecked():
            plan = dict(plan); plan["rows"] = [[] for _ in (plan["rows"] or [[]])]; plan["names"] = []
        if not plan["rows"]:
            if not has_media:
                self.status.setText("Nothing to play: the playlist is empty (load media to play that instead).")
                return
            plan = dict(plan); plan["rows"] = [[]]
        start = min(len(plan["rows"]) - 1, self.spin_start.value() - 1)
        self.spin_start.setMaximum(len(plan["rows"]))
        eng = LiveEngine(h)
        eng.mic_monitor = self.chk_mic_mon.isChecked()
        eng.comp_gain = self._mix_sliders["comp"].value() / 100.0
        eng.keys_gain = self._mix_sliders["keys"].value() / 100.0
        self.engine = eng
        for v in self._views():
            v.set_plan(plan, eng)
        # R32.10.3: the light engine plays only user-entered notes. With none (a fresh project, or one whose
        # music is all canonical/seeded), it would be silent while Play / Export render music — so play the
        # full mixdown instead, the same buffer Export uses.
        _auto_full = (self.chk_comp.isChecked() and not self.chk_full.isChecked()
                      and not any(plan.get("rows") or []) and len(getattr(h, "master_playlist_data", []) or []) > 0)
        if (self.chk_full.isChecked() or _auto_full) and self.chk_comp.isChecked():
            self._start_full(plan, eng, start, gen)
            self._auto_full_note_keep = bool(_auto_full)
        else:
            self._start_light(plan, eng, start)
        if self.chk_rig.isChecked():
            self._start_rig(plan, eng)

    def _start_light(self, plan, eng, start):
        loop = self.chk_loop.isChecked()
        h = self.host

        def work():
            cache = {}
            ri = start
            try:
                while not eng.stop_evt.is_set():
                    buf = synth_row(h, plan["rows"][ri], plan["row_dur"], LIGHT_SR, cache)
                    while not eng.stop_evt.is_set():
                        try:
                            eng.q.put((ri, buf), timeout=0.1); break
                        except queue.Full:
                            continue
                    ri += 1
                    if ri >= len(plan["rows"]):
                        if not loop:
                            eng.q.put(None); return
                        ri = 0
            except Exception as exc:          # never leave the stream waiting forever
                self._pending_msg = f"Light engine stopped: {exc}"
                try:
                    eng.q.put(None, timeout=1.0)
                except Exception:
                    pass
        self._worker = threading.Thread(target=work, name="live-player-synth", daemon=True)
        self._worker.start()
        try:
            eng.open(LIGHT_SR)
            self.status.setText(f"▶ Light engine · {len(plan['names'])} instruments · {len(plan['rows'])} rows · "
                                f"{plan['bpm']:.0f} BPM")
            self._after_open()
        except Exception as exc:
            self.status.setText(f"Audio output unavailable: {exc}")

    def _start_full(self, plan, eng, start, gen):
        """Stream the full mixdown (the buffer Export uses).

        R32.10.4 QUICK START: rendering the whole song first could take minutes. The first rows are rendered
        on their own and start playing at once; the full song keeps rendering in the background and takes
        over at the next row boundary. If playback reaches the end of the preview before the full render is
        ready, it waits there (silence) rather than jumping.
        """
        h = self.host
        n_rows = len(plan["rows"])
        quick_rows = 2 if (n_rows > 3 and start < 2) else 0
        self.status.setText("Full process routine: rendering the first rows…" if quick_rows else
                            "Full process routine: rendering the full mixdown (same buffer as Play / Export)…")
        try:
            h._snapshot_render_inputs()
            def _render(max_rows):
                def run():
                    buf, sr = h._get_shared_mixdown_buffer(max_rows, "Live player")
                    import audio_os_backend as aob
                    pref = str(getattr(h, "_preferred_audio_output_name", "") or "")
                    buf, sr, _hw = aob.prepare_output_buffer(buf, sr, preferred_name=pref)
                    buf = np.asarray(buf, dtype=np.float32)
                    if buf.ndim > 1:
                        buf = buf.mean(axis=1).astype(np.float32)
                    return buf, int(sr)
                return run
            fut_quick = h._live_audio_fx_lane.submit(_render(quick_rows)) if quick_rows else None
            fut = h._live_audio_fx_lane.submit(_render(None))
        except Exception as exc:
            self.status.setText(f"Render lane unavailable: {exc}")
            return
        loop = self.chk_loop.isChecked()
        holder = {"chunks": None, "sr": None, "full": False, "total": n_rows}

        def _chunks(buf, sr, limit):
            per = max(1, int(round(plan["row_dur"] * sr)))
            return [(i, buf[i * per:(i + 1) * per]) for i in range(limit) if i * per < len(buf)]

        def feed():
            i = min(start, max(0, len(holder["chunks"]) - 1))
            while not eng.stop_evt.is_set():
                chunks = holder["chunks"]
                if i >= len(chunks):
                    if not holder["full"]:
                        time.sleep(0.02); continue         # preview played out: wait for the full song
                    if not loop:
                        eng.q.put(None); return
                    i = 0
                    continue
                try:
                    eng.q.put(chunks[i], timeout=0.1)
                except queue.Full:
                    continue
                i += 1

        def finish():
            if gen != self._gen or self.engine is not eng:
                return
            first = fut_quick if (fut_quick is not None and not fut.done()) else fut
            if not first.done():
                QTimer.singleShot(50, finish); return
            try:
                buf, sr = first.result()
            except Exception as exc:
                if first is fut_quick:                     # preview failed: wait for the full render
                    holder_fallback()
                    return
                self.status.setText(f"Render failed: {exc}"); return
            holder["sr"] = sr
            if first is fut:
                holder["chunks"] = _chunks(buf, sr, n_rows); holder["full"] = True
            else:
                holder["chunks"] = _chunks(buf, sr, quick_rows)
                QTimer.singleShot(50, upgrade)
            if not holder["chunks"]:
                self.status.setText("Render produced no audio."); return
            self._worker = threading.Thread(target=feed, name="live-player-feed", daemon=True)
            self._worker.start()
            try:
                eng.open(sr)
                self._full_status(sr)
                self._after_open()
            except Exception as exc:
                self.status.setText(f"Audio output unavailable: {exc}")

        def holder_fallback():
            if gen != self._gen or self.engine is not eng:
                return
            if not fut.done():
                QTimer.singleShot(50, holder_fallback); return
            finish_full_only()

        def finish_full_only():
            try:
                buf, sr = fut.result()
            except Exception as exc:
                self.status.setText(f"Render failed: {exc}"); return
            holder["sr"] = sr; holder["chunks"] = _chunks(buf, sr, n_rows); holder["full"] = True
            self._worker = threading.Thread(target=feed, name="live-player-feed", daemon=True)
            self._worker.start()
            try:
                eng.open(sr)
                self._full_status(sr)
                self._after_open()
            except Exception as exc:
                self.status.setText(f"Audio output unavailable: {exc}")

        def upgrade():
            if gen != self._gen or self.engine is not eng:
                return
            if not fut.done():
                QTimer.singleShot(100, upgrade); return
            try:
                buf, sr = fut.result()
            except Exception as exc:
                holder["full"] = True                      # play the preview to its end, then stop / loop it
                self.status.setText(f"Full render failed ({exc}); playing the first rows only")
                return
            if sr != holder["sr"]:
                holder["full"] = True
                return
            holder["chunks"] = _chunks(buf, sr, n_rows)
            holder["full"] = True
            self._full_status(sr)

        finish()

    def _full_status(self, sr):
        rows = len(self.visual.plan.get("rows") or []) if (self.visual is not None and self.visual.plan) else 0
        self.status.setText(f"▶ Full process routine · identical to Play / Export · {sr} Hz · {rows} rows"
                            + (" · (no hand-entered notes, so the seeded composition plays)"
                               if getattr(self, "_auto_full_note_keep", False) else ""))

    def _on_full_cpu_mode_changed(self, *_args):
        try:
            key = self.cmb_full_cpu_mode.currentData()
            cfg = FULL_CPU_LIVE_PLAY_MODES.get(str(key), FULL_CPU_LIVE_PLAY_MODES["play"])
            ncpu = _live_play_cpu_count()
            rec = "available" + (" · default ON" if cfg.get("record") else " · user controlled")
            pool = "ON" if cfg.get("scode_pool_visual") else "off"
            self.lbl_full_cpu_info.setText(
                f"{cfg.get('description', '')}  ·  pool≤{cfg.get('pool_workers')}  ·  "
                f"record {rec}  ·  sCode visual {pool}  ·  CPUs {ncpu}"
            )
            # Reflect recording checkbox for clarity
            if hasattr(self, "chk_rec"):
                self.chk_rec.setEnabled(True)
                self.chk_rec.setToolTip("Recording is independent of FULL CPU mode; audio capture uses a bounded non-blocking queue and a dedicated writer.")
        except Exception:
            pass

    def _tick_scode_pool_visual(self):
        if not getattr(self, "_scode_pool_visual", False):
            return
        # While a take is recording, keep the sCode visual tick light so the
        # record-frame and audio-writer threads are not starved on Latitude-class CPUs.
        recording = getattr(self, "recorder", None) is not None
        try:
            cfg = getattr(self, "_full_cpu_cfg", {}) or {}
            force = False if recording else bool(cfg.get("force_1080"))
            _scode_pool_visual_tick(self.host, self.visual, self.engine, force_1080=force)
        except Exception:
            pass

    def stop(self):
        """LIVE_TEARDOWN_R31: detach everything on the UI thread (instant), then close the
        rig / audio engine / worker on a background thread. Their joins and process waits
        (up to several seconds) used to freeze the window on Stop and Close."""
        self._gen += 1
        self._finish_rec()
        self._stop_media_video()
        closers = []
        if self.rig is not None:
            rig, self.rig = self.rig, None
            for v in self._views():
                v.rig = None
            closers.append(rig.stop)
        eng, self.engine = self.engine, None
        if eng is not None:
            closers.append(eng.close)
        if self._worker is not None:
            w, self._worker = self._worker, None
            closers.append(lambda w=w: w.join(timeout=1.0))
        self._teardown_off_ui(closers)

    def _teardown_off_ui(self, closers):
        if not closers:
            return
        prev = getattr(self, "_teardown_thread", None)

        def run():
            if prev is not None:
                prev.join(timeout=10.0)          # keep device release ordered
            for fn in closers:
                try:
                    fn()
                except Exception as exc:
                    print(f"[LivePlayer] teardown: {exc}")
        t = threading.Thread(target=run, name="live-player-teardown", daemon=True)
        self._teardown_thread = t
        t.start()

    def _teardown_busy(self):
        t = getattr(self, "_teardown_thread", None)
        return t is not None and t.is_alive()

    def add_key(self, buf, sr):
        if self.is_active():
            arr = self.engine.add_key(buf, sr)
            return arr if arr is not None else True      # R32.9: the stored array (held-key release)
        return False

    def release_key(self, arr, release_s=0.2):
        return bool(self.is_active() and self.engine.release_key(arr, release_s))

    def _tick(self):
        for v in self._views():
            v.tick()
        eng = self.engine
        if eng is not None and eng.mic is not None:
            lv = eng.mic.level
            self.lbl_mic.setText("▮" * max(0, min(8, int(lv * 8 + 0.5))) or "·")
        elif self.lbl_mic.text():
            self.lbl_mic.setText("")
        self._record_frames()
        try:
            self._tick_scode_pool_visual()
        except Exception:
            pass
        for src in (self.rig, self.camera):
            if src is not None and getattr(src, "error", ""):
                self.status.setText(src.error)
        if self.rig is not None and self.rig.fps_measured > 0 and self.chk_rig.isChecked() and eng is not None:
            _ew, _eh = self.rig.effective_size()
            _sz = f" · {self.rig.w}×{self.rig.h}" + (f" (render {_ew}×{_eh})" if self.rig.adaptive else "")
            _wk = f" · {self.rig.workers} workers" if self.rig.workers > 1 else ""
            self.chk_rig.setText(f"Full video rig · {self.rig.fps_measured:.1f} fps{_sz}{_wk}")
        elif self.chk_rig.text() != "Full video rig":
            self.chk_rig.setText("Full video rig")
        if eng is not None and eng.finished:
            self.status.setText("■ End of composition")
            self.stop()
        if self._pending_msg and self.engine is None and self.recorder is None and "Light engine stopped" in self._pending_msg:
            self.status.setText(self._pending_msg); self._pending_msg = None

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen(); return
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier and ev.key() in (Qt.Key.Key_Right, Qt.Key.Key_Left):
            self._tweak_step(1 if ev.key() == Qt.Key.Key_Right else -1); return
        if ev.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen(); return
        if ev.key() == Qt.Key.Key_F10 and not ev.isAutoRepeat():   # letters play notes, so F10
            self.toggle_controls(); return
        if ev.key() == Qt.Key.Key_Space and not ev.isAutoRepeat():
            self.stop() if self.is_active() else self.start()
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev):
        self.stop()
        pool = getattr(self, "_record_local_pool", None)
        if pool is not None:
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._record_local_pool = None
        if self.camera is not None:
            cam, self.camera = self.camera, None
            self._teardown_off_ui([cam.close])
        bv, self._broadcast_view = self._broadcast_view, None
        if bv is not None:
            try: bv.close()
            except Exception: pass
        self._close_popouts()
        super().closeEvent(ev)


def open_live_player(host):
    win = getattr(host, "_live_player_window", None)
    try:
        if win is not None:
            win.isVisible()
    except RuntimeError:
        win = None
    if win is None:
        win = LivePlayerWindow(host)
        host._live_player_window = win
    win.show(); win.raise_(); win.activateWindow()
    return win
