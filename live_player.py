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
import queue
import threading
import time

import numpy as np
from dj_effects import LiveDJEffects, EXTRA_DJ_EFFECTS

try:
    from qt_painting import owned_painter
    from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QEvent
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
    """Realtime, block-based DJ rack on the live mix: filter sweep (LP ↔ HP), tempo-synced
    echo, stutter (beat repeat), bitcrush, tempo-synced gate. All at 0 = bypassed exactly.
    No limiter anywhere; echo feedback is capped below 1 so it always decays."""

    def __init__(self, sr):
        self.sr = int(sr)
        self.bpm = 120.0
        self.p = {"filter": 0.0, "reso": 0.7, "echo": 0.0, "echo_div": 0.5, "echo_fb": 0.45,
                  "stutter": 0.0, "crush": 0.0, "gate": 0.0, "gate_div": 0.25}
        self._zi = None
        self._coef_key = None
        self._ba = None
        L = self.sr * 4
        self._echo = np.zeros(L, dtype=np.float32); self._epos = 0
        self._hist = np.zeros(L, dtype=np.float32); self._hpos = 0
        self._stut = None; self._spos = 0; self._stut_key = 0.0
        self._gphase = 0
        self._crush_hold = 0.0

    def _beat(self):
        return 60.0 / max(20.0, float(self.bpm)) * self.sr

    def _biquad(self, f):
        import math as _m
        fc = 20000.0 * 2.0 ** (f / 100.0 * 9.5) if f < 0 else 20.0 * 2.0 ** (f / 100.0 * 9.5)
        fc = max(20.0, min(0.45 * self.sr, fc))
        q = max(0.3, float(self.p["reso"]))
        w0 = 2 * _m.pi * fc / self.sr
        al = _m.sin(w0) / (2 * q); cw = _m.cos(w0)
        if f < 0:
            b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        else:
            b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + al, -2 * cw, 1 - al]
        return np.array(b) / a[0], np.array(a) / a[0]

    def process(self, x):
        p = self.p
        n = len(x)
        # history (for stutter capture)
        idx = (self._hpos + np.arange(n)) % len(self._hist)
        self._hist[idx] = x
        self._hpos = (self._hpos + n) % len(self._hist)
        y = x
        # stutter: loop the last <div> beats while engaged
        if p["stutter"] > 0:
            seg = max(64, int(self._beat() * p["stutter"]))
            if self._stut is None or self._stut_key != p["stutter"]:
                start = (self._hpos - seg) % len(self._hist)
                self._stut = self._hist[(start + np.arange(seg)) % len(self._hist)].copy()
                self._spos = 0; self._stut_key = p["stutter"]
            j = (self._spos + np.arange(n)) % len(self._stut)
            y = self._stut[j]
            self._spos = int((self._spos + n) % len(self._stut))
        else:
            self._stut = None
        # filter sweep
        f = float(p["filter"])
        if abs(f) > 0.5:
            try:
                from scipy.signal import lfilter, lfilter_zi
                key = (round(f, 1), round(float(p["reso"]), 2), int(f > 0))
                if key != self._coef_key:
                    self._ba = self._biquad(f)
                    if self._zi is None or (self._coef_key or (0, 0, -1))[2] != key[2]:
                        self._zi = lfilter_zi(*self._ba) * 0.0
                    self._coef_key = key
                y, self._zi = lfilter(self._ba[0], self._ba[1], y, zi=self._zi)
                y = y.astype(np.float32)
            except Exception:
                pass
        else:
            self._zi = None; self._coef_key = None
        # bitcrush
        c = float(p["crush"])
        if c > 0.5:
            hold = 1 + int(c / 100.0 * 15)
            bits = 16 - c / 100.0 * 12
            q = 2.0 ** (bits - 1)
            if hold > 1:
                y = np.repeat(y[::hold], hold)[:n]
            y = (np.round(y * q) / q).astype(np.float32)
        # gate (tempo-synced chop)
        g = float(p["gate"])
        if g > 0.5:
            per = max(32, int(self._beat() * p["gate_div"]))
            ph = (self._gphase + np.arange(n)) % per
            edge = max(1, int(0.002 * self.sr))
            on = np.clip(np.minimum(ph, per // 2 - ph) / edge, 0.0, 1.0)      # 2 ms click-free edges
            on = np.where(ph < per // 2, on, 0.0)
            y = (y * (1.0 - g / 100.0 * (1.0 - on))).astype(np.float32)
            self._gphase = int((self._gphase + n) % per)
        # echo (tempo-synced, feedback < 1)
        e = float(p["echo"])
        d = max(1, int(self._beat() * p["echo_div"]))
        L = len(self._echo)
        out = np.empty(n, dtype=np.float32)
        w = 0
        while w < n:
            take = min(n - w, d)
            ri = (self._epos - d + np.arange(take)) % L
            wi = (self._epos + np.arange(take)) % L
            dly = self._echo[ri]
            out[w:w + take] = y[w:w + take] + (e / 100.0) * dly
            self._echo[wi] = y[w:w + take] + min(0.92, float(p["echo_fb"])) * dly if e > 0.5 else 0.0
            self._epos = (self._epos + take) % L
            w += take
        return out if e > 0.5 else np.asarray(y, dtype=np.float32)

    def active(self):
        p = self.p
        return any(abs(float(p[k])) > 0.5 for k in ("filter", "echo", "crush", "gate")) or p["stutter"] > 0 \
            or bool(np.any(self._echo))


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
        self.mic = None            # MicFeed
        self.mic_monitor = False   # mic also to the speakers (off: no feedback; still recorded)
        self.fx = None             # DJChain (set by the window)
        self.global_fx = LiveDJEffects(LIGHT_SR)
        self.global_fx_state = None
        self._global_fx_context = None
        self.media = None          # MediaTrack
        self.comp_gain = 1.0       # mixer: composition / keys (media gain lives on the track)
        self.keys_gain = 1.0

    # audio thread
    def callback(self, outdata, frames, time_info, status):
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
            # Immutable GUI-published controls, audio-owned DSP/history. These
            # effects are captured by the same recording tap as the heard mix.
            state = self.global_fx_state
            if state is not None:
                amounts, context, bpm, goava, random_scalar, boost = state
                if context != self._global_fx_context:
                    self.global_fx.set_context(seed=context[0], pair=context[1], sample_rate=self.sr)
                    self._global_fx_context = context
                for key, amount in zip(("goava", "random", *EXTRA_DJ_EFFECTS), amounts):
                    setattr(self.global_fx, f"amount_{key}", amount)
                self.global_fx.set_boost(*boost)
                if any(amounts) or boost[2] > 0:
                    mix = self.global_fx.process(mix, start_sample=self.played - frames,
                                                 goava_scalar=goava, random_scalar=random_scalar, bpm=bpm)
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

    def add_key(self, buf, sr):
        arr = np.asarray(buf, dtype=np.float32).ravel()
        if int(sr) != int(self.sr) and arr.size > 1:
            m = max(1, int(round(arr.size * self.sr / float(sr))))
            arr = np.interp(np.linspace(0.0, arr.size - 1, m), np.arange(arr.size), arr).astype(np.float32)
        with self.lock:
            if len(self.keys) > 64:
                del self.keys[0]
            self.keys.append([arr, 0])

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
             ("2560×1440 · QHD", (2560, 1440)))


class VideoRig:
    """Live frames from the real video engine; newest frame wins."""
    FPS = 30.0

    def __init__(self, host, plan, engine, size=(320, 180)):
        self.host, self.plan, self.engine = host, plan, engine
        self.w, self.h = int(size[0]), int(size[1])
        self.frame = None
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.thread = None
        self.fps_measured = 0.0
        self.error = ""

    def start(self):
        self.thread = threading.Thread(target=self._run, name="live-player-video-rig", daemon=True)
        self.thread.start()

    def _run(self):
        gb = _gb()
        try:
            n = len(getattr(self.host, "active_instrument_memory", []) or []) or int(getattr(self.host, "synth_count", 48) or 48)
            eng = gb.VideoSynthEngine(n)
            if hasattr(eng, "bind_app"):
                eng.bind_app(self.host)
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
            pos = le.row_idx * self.plan["row_dur"] + le.position_seconds()
            fi = int(pos * self.FPS) % n_frames
            try:
                eng.set_waveform(np.array(le.scope, copy=True), playhead=(min(1.0, pos / total) if total > 0 else 0.0))
                fr = eng.render_frame(self.w, self.h, export=True, frame_index=fi)
                fr = np.nan_to_num(np.asarray(fr), nan=0, posinf=255, neginf=0).astype(np.uint8, copy=False)
                try:
                    fr = self.host._apply_video_plan_to_frame(fr, fi, n_frames)
                except Exception:
                    pass
                fr = np.ascontiguousarray(np.asarray(fr)[:, :, :3], dtype=np.uint8)
                with self.lock:
                    self.frame = fr
                self.error = ""
            except Exception as exc:
                self.error = f"video rig frame: {exc}"
                time.sleep(0.1)
            dt = time.monotonic() - t0
            if dt > 0:
                inst = 1.0 / dt
                self.fps_measured = inst if self.fps_measured <= 0 else 0.8 * self.fps_measured + 0.2 * inst
            spare = (1.0 / self.FPS) - dt
            if spare > 0:
                time.sleep(min(spare, 0.03))

    def latest(self):
        with self.lock:
            return self.frame

    def stop(self):
        self.stop_evt.set()
        if self.thread is not None:
            self.thread.join(timeout=3.0)


# ---------------------------------------------------------------------------
# Record live play (streamed to disk — no frames or audio piling up in memory)
# ---------------------------------------------------------------------------
class LiveRecorder:
    """Quick take of exactly what you hear (composition + keys + mic) and, optionally,
    exactly what the live view shows (every enabled layer, incl. camera), at a fixed size.

    Audio samples are the recording clock. Timestamped RGB snapshots use a bounded
    queue; missing snapshots hold the preceding picture, never compress time.
    On stop the take is muxed into
    the chosen formats in the "Save to:" folder (project exports or a USB / SD drive).
    """
    AUDIO_FORMATS = ("WAV", "MCC", "FLAC", "MP3", "OGG")
    VIDEO_FORMATS = ("MP4", "MCC", "WEBM", "MKV")
    VIDEO_SIZE = (960, 540)
    VIDEO_FPS = 24

    def __init__(self, host, engine, audio_format="WAV", video_format="MP4", video=True):
        import os, tempfile, uuid
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
        # Two short takes in the same second must not overwrite one another.
        self.base = os.path.join(d, f"live-take-{stamp}-{uuid.uuid4().hex}")
        self.tmpdir = tempfile.mkdtemp(prefix="gb-live-take-")
        self.raw_path = os.path.join(self.tmpdir, "audio.f32")
        self._raw = open(self.raw_path, "wb")
        self._ablocks = []
        self._alock = threading.Lock()
        self._vq = queue.Queue(maxsize=48)
        self.frames_written = 0
        self.frames_dropped = 0
        self._first_frame = None
        self._audio_samples = 0
        self._final_video_frames = None
        self._closing = False
        self._pushed = 0
        self._last_frame_index = -1
        self._venc = None          # ffmpeg process or MCC writer
        self._verr = None
        self._audio_failed = False
        self._vpath = None
        self.stop_evt = threading.Event()
        self._threads = []
        self.t0 = None
        self.sr = int(engine.sr)
        self.error = ""

    # -- audio (audio thread → list → disk thread)
    def _on_audio(self, block):
        with self._alock:
            if self._closing:
                return
            self._ablocks.append(block)
            self._audio_samples += int(np.asarray(block).size)

    def _audio_writer(self):
        try:
            while True:
                stop = self.stop_evt.is_set()
                with self._alock:
                    blocks, self._ablocks = self._ablocks, []
                for b in blocks:
                    self._raw.write(np.asarray(b, dtype="<f4").tobytes())
                if stop:
                    break
                self.stop_evt.wait(0.2)
            self._raw.flush()
        except Exception as exc:
            self._audio_failed = True
            self.error = f"audio recording write failed: {exc}"
            with self._alock:
                self._closing = True
        finally:
            try:
                self._raw.close()
            except Exception as exc:
                self._audio_failed = True
                self.error = f"audio recording close failed: {exc}"

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
        w, h = self.VIDEO_SIZE
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
            if self._verr is not None:
                self._verr.close()
                self._verr = None
            return False
        # Do not sleep on the GUI thread. Later pipe failures are reported by
        # the video writer; only check for an already-failed process here.
        if self._venc.poll() is not None:
            self.error = "video encoder exited: " + self._encoder_log()
            self._venc.stdin.close()
            self._venc = None
            self._verr.close()
            self._verr = None
            return False
        return True

    def _encoder_log(self):
        try:
            with open(self._verr_path, "rb") as f:
                return f.read().decode(errors="replace").strip()[-300:] or "no message"
        except Exception:
            return "no message"

    def _video_writer(self):
        held = None

        def write(frame):
            enc = self._venc
            if hasattr(enc, "write"):
                enc.write(frame)
            else:
                enc.stdin.write(frame.tobytes())
            self.frames_written += 1

        while True:
            try:
                item = self._vq.get(timeout=0.2)
            except queue.Empty:
                if self.stop_evt.is_set():
                    break
                continue
            if item is None:
                break
            try:
                index, fr = item
                # A missed GUI tick or a full queue costs motion detail, not
                # duration. Never backfill a later image into earlier time.
                if held is None and self.frames_written < index:
                    w, h = self.VIDEO_SIZE
                    held = np.full((h, w, 3), 118, dtype=np.uint8)
                while self.frames_written < index:
                    write(held)
                if self.frames_written == index:
                    write(fr)
                    held = fr
            except Exception as exc:
                log = self._encoder_log() if not hasattr(self._venc, "write") else ""
                self.error = f"video encoder stopped: {exc} {log}".strip()
                return
        target = self._final_video_frames
        if target is not None:
            try:
                if held is None:
                    held = self._first_frame
                if held is None:
                    w, h = self.VIDEO_SIZE
                    held = np.full((h, w, 3), 118, dtype=np.uint8)
                    self.error = (self.error + " · " if self.error else "") + "no live images captured; video uses a neutral slate"
                while self.frames_written < target:
                    write(held)
            except Exception as exc:
                self.error = f"video tail could not be completed: {exc}"

    def start(self):
        # Encoder setup must not become dead time at the front of the take.
        opened = self.want_video and self._open_video()
        if not opened:
            self.want_video = False
        t = threading.Thread(target=self._audio_writer, name="live-take-audio", daemon=True)
        t.start(); self._threads.append(t)
        if opened:
            t = threading.Thread(target=self._video_writer, name="live-take-video", daemon=True)
            t.start(); self._threads.append(t)
        self.t0 = time.monotonic()
        self.engine.rec = self._on_audio

    def frames_due(self):
        """CFR extent on the captured-audio clock, including the priming image."""
        if not self.want_video or self.t0 is None:
            return 0
        return max(1, (self._audio_samples * self.VIDEO_FPS + self.sr - 1) // self.sr)

    def push_frame(self, rgb):
        if not self.want_video or self._closing:
            return False
        index = self.frames_due() - 1
        if index <= self._last_frame_index:
            return False
        # Own a tightly packed immutable snapshot: QImage/NumPy buffers used by
        # the GUI painter can otherwise be reused while the encoder thread reads.
        try:
            frame = np.asarray(rgb)
            w, h = self.VIDEO_SIZE
            if frame.shape != (h, w, 3):
                raise ValueError(f"expected {(h, w, 3)} RGB frame, got {frame.shape}")
            if frame.dtype != np.uint8:
                frame = np.clip(frame, 0, 255).astype(np.uint8)
            frame = np.ascontiguousarray(frame).copy()
            if self._first_frame is None:
                self._first_frame = frame.copy()
            self._vq.put_nowait((index, frame))
            self._accepted = getattr(self, "_accepted", 0) + 1
            ok = True
        except queue.Full:
            self.frames_dropped += 1
            ok = False
        except Exception as exc:
            self.frames_dropped += 1
            self.error = f"video frame rejected: {exc}"
            ok = False
        # One immutable snapshot per GUI tick, regardless of the size of a gap.
        self._last_frame_index = index
        self._pushed = index + 1
        return ok

    @property
    def pushed(self):
        return getattr(self, "_pushed", 0)

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
        w, h = self.VIDEO_SIZE
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

    def _stop_capture(self):
        """Drain all accepted data before any encoding finalization or cleanup."""
        if self.engine.rec == self._on_audio:
            self.engine.rec = None
        self._stopped_at = time.monotonic()
        with self._alock:
            self._closing = True
            samples = self._audio_samples
        elapsed = max(1.0 / self.VIDEO_FPS, self._stopped_at - (self.t0 or self._stopped_at))
        self._final_video_frames = (
            max(1, (samples * self.VIDEO_FPS + self.sr - 1) // self.sr)
            if samples else max(1, int(math.ceil(elapsed * self.VIDEO_FPS)))
        )
        try:
            if self._venc is not None:
                # The writer owns stdin. Wait for queue space so EOF is ordered
                # after every accepted frame instead of racing a full queue.
                self._vq.put(None, timeout=15.0)
        except Exception as exc:
            self.error = (self.error + " · " if self.error else "") + f"video queue shutdown: {exc}"
        self.stop_evt.set()
        for t in self._threads:
            t.join(timeout=60)
        if any(t.is_alive() for t in self._threads):
            # Never finalize or delete files while a writer still owns them.
            raise RuntimeError(f"Recording writer did not stop; recovery files retained in {self.tmpdir}")

    def _close_video_encoder(self):
        """Close only after writers stop; do not leave encoder children behind."""
        import subprocess
        enc, self._venc = self._venc, None
        try:
            if enc is None:
                return
            if hasattr(enc, "write"):
                enc.close()
                return
            pipe_error = None
            try:
                if enc.stdin is not None and not enc.stdin.closed:
                    enc.stdin.close()
            except OSError as exc:
                pipe_error = exc
            try:
                code = enc.wait(timeout=120)
            except subprocess.TimeoutExpired as exc:
                enc.terminate()
                try:
                    enc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    enc.kill()
                    enc.wait(timeout=3)
                raise RuntimeError("video encoder did not finalize in time") from exc
            if code or pipe_error is not None:
                raise RuntimeError(
                    "video encoder failed: " + self._encoder_log()
                    + (f" ({pipe_error})" if pipe_error is not None else "")
                )
        finally:
            if self._verr is not None:
                self._verr.close()
                self._verr = None

    def finish(self):
        """Stop capturing, write the take; returns the paths written. Runs off the GUI thread."""
        import os, shutil, subprocess
        self._stop_capture()
        elapsed = max(1.0 / self.VIDEO_FPS, self._stopped_at - (self.t0 or self._stopped_at))
        enc = self._venc
        out = []
        completed = False
        try:
            if self._audio_failed:
                raise RuntimeError(self.error or "The audio recording writer failed")
            pcm = np.fromfile(self.raw_path, dtype="<f4") if os.path.isfile(self.raw_path) else np.zeros(0, np.float32)
            if pcm.size == 0 and (self.video_requested or self.frames_written or self._first_frame is not None):
                # Preserve a video take even if the audio callback was interrupted.
                n_silence = max(1, int(round(max(elapsed, self.frames_written / float(self.VIDEO_FPS)) * self.sr)))
                pcm = np.zeros(n_silence, dtype=np.float32)
                self.error = (self.error + " · " if self.error else "") + "audio callback supplied no samples; video retained with silence"
            if pcm.size == 0 and not self.frames_written and self._first_frame is None:
                completed = True
                return out
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
                    w, h = self.VIDEO_SIZE
                    frame = self._first_frame
                    if frame is None:
                        frame = np.full((h, w, 3), 118, dtype=np.uint8)
                    frame = np.ascontiguousarray(frame, dtype=np.uint8)
                    duration = max(1.0 / self.VIDEO_FPS, pcm.size / float(max(1, self.sr)))
                    frame_count = max(1, int(math.ceil(duration * self.VIDEO_FPS)))
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
                    enc.write_audio(pcm)
                    self._close_video_encoder()
                    dst = self.base + "-video.MCC"
                    shutil.move(self._vpath, dst); out.append(dst)
                else:
                    self._close_video_encoder()
                    if ff and os.path.isfile(self._vpath):
                        out.extend(self._mux_video(ff, wav))
            else:
                self._close_video_encoder()
                if self.video_requested:
                    duration = pcm.size / float(max(1, self.sr))
                    out.extend(self._fallback_video(ff, wav, duration))
            completed = bool(out) and (
                not self.video_requested or any("-video." in path for path in out)
            )
        except Exception as exc:
            raise RuntimeError(f"{exc}; recovery files retained in {self.tmpdir}") from exc
        finally:
            try:
                self._close_video_encoder()
            except Exception as exc:
                completed = False
                self.error = (self.error + " · " if self.error else "") + str(exc)
            if completed:
                shutil.rmtree(self.tmpdir, ignore_errors=True)
            else:
                self.error = (self.error + " · " if self.error else "") + f"recovery files retained in {self.tmpdir}"
        return out


# ---------------------------------------------------------------------------
# Visual
# ---------------------------------------------------------------------------
LAYERS = (("rig", "Video rig picture", True), ("orbit", "Instrument orbit (rosette)", True),
          ("ring", "Waveform ring", True), ("labels", "Instrument names", True),
          ("strip", "Playlist strip", True), ("media", "Loaded media video", True),
          ("multidim", "🌀 Multidimensional world", True),
          ("camera", "Camera (picture-in-picture)", True),
          ("camera_full", "Camera full screen (behind)", False))


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


def tweak_defaults():
    return {k: d for k, _l, _a, _b, d in TWEAKS}


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
        with owned_painter(self) as qp:
            if qp is None:
                return
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
        with owned_painter(img) as qp:
            if qp is None:
                return
            try:
                qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                self.paint_to(qp, int(w), int(h))
            finally:
                qp.end()
            return qimage_to_rgb(img)

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

    def _paint_moving(self, qp, w, area_h):
        """Ring + orbit (the parts that trails / spin / symmetry act on)."""
        tw, L, p, e = self.tw, self.layers, self.plan, self.engine
        cx, cy = w / 2, area_h / 2
        R = min(w, area_h) * tw["orbit_radius"] / 100.0
        if e is not None and L.get("ring", True):
            sc = np.asarray(e.scope, dtype=np.float32)
            n = max(16, min(sc.size, int(tw["ring_detail"])))
            sc = (sc.ravel()[np.linspace(0, sc.size - 1, n).astype(int)]
                  if sc.size else np.zeros(n, dtype=np.float32))
            sc = np.nan_to_num(sc, nan=0.0, posinf=1.0, neginf=-1.0)
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
            self._fit(qp, _qimage_rgb(mv), 0, 0, w, area_h)
        rig_frame = self.rig.latest() if (self.rig is not None and L.get("rig", True)) else None
        if rig_frame is not None:
            if mv is not None:
                qp.setOpacity(0.5)
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
            with owned_painter(acc) as tp:
                if tp is None:
                    return
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
        for wdg in (self.chk_full, self.chk_rig, self.cmb_rig_size, self.btn_layers, self.btn_tweak):
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
        djr.addWidget(QLabel("🎚 DJ FX:"))
        self._fx_params = DJChain(LIGHT_SR).p      # template; each engine gets its own chain with these values
        self.sld_filter = QSlider(Qt.Orientation.Horizontal); self.sld_filter.setRange(-100, 100); self.sld_filter.setValue(0)
        self.sld_filter.setFixedWidth(120)
        self.sld_filter.setToolTip("Filter sweep: left = low-pass, right = high-pass, centre = off (double-click resets)")
        self.sld_filter.valueChanged.connect(lambda v: self._fx_set("filter", float(v)))
        self.sld_filter.mouseDoubleClickEvent = lambda _e: self.sld_filter.setValue(0)
        djr.addWidget(QLabel("filter")); djr.addWidget(self.sld_filter)
        self.sld_echo = QSlider(Qt.Orientation.Horizontal); self.sld_echo.setRange(0, 100); self.sld_echo.setFixedWidth(80)
        self.sld_echo.setToolTip("Echo amount (tempo-synced)")
        self.sld_echo.valueChanged.connect(lambda v: self._fx_set("echo", float(v)))
        self.cmb_echo = QComboBox(); self.cmb_echo.addItems(["1/16", "1/8", "3/16", "1/4", "3/8", "1/2", "1"])
        self.cmb_echo.setCurrentText("1/8")
        self.cmb_echo.currentTextChanged.connect(lambda t: self._fx_set("echo_div", self._beats(t)))
        djr.addWidget(QLabel("echo")); djr.addWidget(self.sld_echo); djr.addWidget(self.cmb_echo)
        self._stutter_btns = []
        for lab in ("1/4", "1/8", "1/16"):
            b = QPushButton(f"⟲{lab}"); b.setCheckable(True); b.setFixedWidth(52)
            b.setToolTip(f"Stutter: repeat the last {lab} note while on")
            b.toggled.connect(lambda on, bb=b, t=lab: self._stutter(bb, t, on))
            djr.addWidget(b); self._stutter_btns.append(b)
        self.sld_crush = QSlider(Qt.Orientation.Horizontal); self.sld_crush.setRange(0, 100); self.sld_crush.setFixedWidth(70)
        self.sld_crush.setToolTip("Bitcrush / sample-rate reduction")
        self.sld_crush.valueChanged.connect(lambda v: self._fx_set("crush", float(v)))
        djr.addWidget(QLabel("crush")); djr.addWidget(self.sld_crush)
        self.sld_gate = QSlider(Qt.Orientation.Horizontal); self.sld_gate.setRange(0, 100); self.sld_gate.setFixedWidth(70)
        self.sld_gate.setToolTip("Tempo-synced gate depth")
        self.sld_gate.valueChanged.connect(lambda v: self._fx_set("gate", float(v)))
        self.cmb_gate = QComboBox(); self.cmb_gate.addItems(["1/16", "1/8", "1/4", "1/2"]); self.cmb_gate.setCurrentText("1/16")
        self.cmb_gate.currentTextChanged.connect(lambda t: self._fx_set("gate_div", self._beats(t)))
        djr.addWidget(QLabel("gate")); djr.addWidget(self.sld_gate); djr.addWidget(self.cmb_gate)
        b_reset = QPushButton("reset FX"); b_reset.clicked.connect(self._fx_reset)
        djr.addWidget(b_reset)
        djr.addStretch(1)
        lay.addLayout(djr)

        # Row 4: record
        recr = QHBoxLayout()
        self.chk_rec = QCheckBox("⏺ Record live play")
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
        for wdg in (self.chk_rec, QLabel("audio"), self.cmb_rec_audio, self.chk_rec_video, self.cmb_rec_video, self.lbl_rec):
            recr.addWidget(wdg)
        recr.addStretch(1)
        lay.addLayout(recr)
        try:   # GROOVEBOX_R23R_SAVE_TO_DRIVE_20261103: takes can go straight onto a USB / SD drive
            lay.addWidget(host._make_export_target_picker(self))
        except Exception:
            pass

        self.visual = LiveVisual(self)
        self.visual.host = host
        self.visual.on_seek = self.seek
        lay.addWidget(self.visual, 1)
        self.status = QLabel("Light engine: the composition's own instrument voices + live view. "
                             "Keys keep playing on top. Space = play / stop.")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
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
        top.addWidget(QLabel("Preset")); top.addWidget(self.cmb_tweak_preset); top.addWidget(b_apply); top.addWidget(b_reset)
        outer.addLayout(top)
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

    def _tweak_preset(self, name):
        vals = tweak_defaults(); vals.update(TWEAK_PRESETS.get(name, {}))
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
        import os
        self.lbl_media.setText(f"loading {os.path.basename(path)}…")
        sr = self.engine.sr if self.engine is not None else LIGHT_SR

        def work():
            try:
                pcm = decode_audio_file(self.host, path, sr)
                vid = file_has_video(self.host, path)
                self._media_pending = (path, pcm, sr, vid, "")
            except Exception as exc:
                self._media_pending = (path, None, sr, False, str(exc))
        self._media_pending = None
        threading.Thread(target=work, name="live-player-media-load", daemon=True).start()
        QTimer.singleShot(100, self._media_loaded)

    def _media_loaded(self):
        import os
        if self._media_pending is None:
            QTimer.singleShot(100, self._media_loaded); return
        path, pcm, sr, vid, err = self._media_pending
        self._media_pending = None
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
        self.rig = VideoRig(self.host, plan, eng, size=self._rig_size())
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
            self._sync_global_dj()
            self._attach_media(eng)
        self._sync_mic()
        if self.chk_rec.isChecked() and self.recorder is None:
            self._start_rec()

    def _sync_global_dj(self):
        """Publish a value snapshot; no live-player DSP state is shared with export."""
        eng = self.engine
        if eng is None:
            return
        host = self.host
        keys = ("goava", "random", *EXTRA_DJ_EFFECTS)
        amounts = tuple(
            max(0.0, min(1.0, float(getattr(host, f"live_dj_{key}_amount", 0.0) or 0.0)))
            if getattr(host, f"live_dj_{key}", False) else 0.0 for key in keys
        )
        context = (float(getattr(host, "_rt_numeric_seed", 0.0) or 0.0),
                   tuple(getattr(host, "_live_dj_pair_ids", (0, 1))))
        bpm = float(getattr(host, "_rt_bpm", 120.0) or 120.0)
        goava = host._live_dj_goava_scalar(eng.played) if amounts[0] else 0.0
        random_scalar = host._live_dj_random_scalar(eng.played) if amounts[1] else 0.0
        boost = getattr(host, "_live_dj_boost", None) or {}
        eng.global_fx_state = (
            amounts, context, bpm, goava, random_scalar,
            (int(boost.get("interval", 0)), float(boost.get("phase", 0.0)), float(boost.get("amount", 0.0))),
        )

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
        if rec is None or not rec.want_video or self.visual is None:
            return
        due = rec.frames_due()
        if rec.pushed >= due:
            return
        try:
            fr = self.visual.render_rgb(*LiveRecorder.VIDEO_SIZE)
        except Exception as exc:
            rec.error = f"view capture: {exc}"
            return
        rec.push_frame(fr)  # The encoder thread fills timeline gaps, not the GUI.

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

        def work():
            try:
                paths = rec.finish()
                msg = ("● Saved live take: " + " + ".join(paths)) if paths else "Live take was empty."
                if rec.frames_dropped:
                    msg += f" ({rec.frames_dropped} snapshots missed; preceding frames held to preserve timing)"
                if rec.error:
                    msg += f" · {rec.error}"
            except Exception as exc:
                msg = f"Live take could not be saved: {exc}"
            self._pending_msg = msg
        self._pending_msg = None
        threading.Thread(target=work, name="live-player-rec-save", daemon=True).start()
        QTimer.singleShot(200, self._poll_msg)

    def _poll_msg(self):
        if self._pending_msg is None:
            QTimer.singleShot(200, self._poll_msg); return
        self.status.setText(self._pending_msg)

    # -- control -----------------------------------------------------------
    def seek(self, row):
        self.spin_start.setValue(int(row) + 1)
        self.start()

    def is_active(self):
        return self.engine is not None and self.engine.stream is not None

    def start(self):
        self.stop()
        h = self.host
        self._gen += 1
        gen = self._gen
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
        if self.chk_full.isChecked() and self.chk_comp.isChecked():
            self._start_full(plan, eng, start, gen)
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
        t_end = time.monotonic() + 3.0      # let the first row land before the stream starts
        while eng.q.empty() and time.monotonic() < t_end and self._worker.is_alive():
            time.sleep(0.005)
        try:
            eng.open(LIGHT_SR)
            self.status.setText(f"▶ Light engine · {len(plan['names'])} instruments · {len(plan['rows'])} rows · "
                                f"{plan['bpm']:.0f} BPM")
            self._after_open()
        except Exception as exc:
            self.status.setText(f"Audio output unavailable: {exc}")

    def _start_full(self, plan, eng, start, gen):
        h = self.host
        self.status.setText("Full process routine: rendering the full mixdown (same buffer as Play / Export)…")
        try:
            h._snapshot_render_inputs()
            fut = h._live_audio_fx_lane.submit(h._get_shared_mixdown_buffer, None, "Live player")
        except Exception as exc:
            self.status.setText(f"Render lane unavailable: {exc}")
            return
        loop = self.chk_loop.isChecked()

        def finish():
            if gen != self._gen or self.engine is not eng:
                return
            if not fut.done():
                QTimer.singleShot(50, finish); return
            try:
                buf, sr = fut.result()
                import audio_os_backend as aob
                pref = str(getattr(h, "_preferred_audio_output_name", "") or "")
                buf, sr, _hw = aob.prepare_output_buffer(buf, sr, preferred_name=pref)
                buf = np.asarray(buf, dtype=np.float32)
                if buf.ndim > 1:
                    buf = buf.mean(axis=1).astype(np.float32)
            except Exception as exc:
                self.status.setText(f"Render failed: {exc}"); return
            per = max(1, int(round(plan["row_dur"] * sr)))
            chunks = [(i, buf[i * per:(i + 1) * per]) for i in range(len(plan["rows"])) if i * per < len(buf)]
            first = min(start, max(0, len(chunks) - 1))

            def feed():
                i = first
                while not eng.stop_evt.is_set() and chunks:
                    try:
                        eng.q.put(chunks[i], timeout=0.1)
                    except queue.Full:
                        continue
                    i += 1
                    if i >= len(chunks):
                        if not loop:
                            eng.q.put(None); return
                        i = 0
            self._worker = threading.Thread(target=feed, name="live-player-feed", daemon=True)
            self._worker.start()
            try:
                eng.open(sr)
                self.status.setText(f"▶ Full process routine · identical to Play / Export · {sr} Hz · "
                                    f"{len(chunks)} rows")
                self._after_open()
            except Exception as exc:
                self.status.setText(f"Audio output unavailable: {exc}")
        QTimer.singleShot(0, finish)

    def stop(self):
        self._gen += 1
        self._finish_rec()
        self._stop_media_video()
        if self.rig is not None:
            self.rig.stop(); self.rig = None
            for v in self._views():
                v.rig = None
        eng, self.engine = self.engine, None
        if eng is not None:
            eng.close()
        if self._worker is not None:
            self._worker.join(timeout=1.0)
            self._worker = None

    def add_key(self, buf, sr):
        if self.is_active():
            self.engine.add_key(buf, sr)
            return True
        return False

    def _tick(self):
        self._sync_global_dj()
        for v in self._views():
            v.tick()
        eng = self.engine
        if eng is not None and eng.mic is not None:
            lv = eng.mic.level
            self.lbl_mic.setText("▮" * max(0, min(8, int(lv * 8 + 0.5))) or "·")
        elif self.lbl_mic.text():
            self.lbl_mic.setText("")
        self._record_frames()
        for src in (self.rig, self.camera):
            if src is not None and getattr(src, "error", ""):
                self.status.setText(src.error)
        if self.rig is not None and self.rig.fps_measured > 0 and self.chk_rig.isChecked() and eng is not None:
            self.chk_rig.setText(f"Full video rig · {self.rig.fps_measured:.1f} fps")
        elif self.chk_rig.text() != "Full video rig":
            self.chk_rig.setText("Full video rig")
        if eng is not None and eng.finished:
            self.status.setText("■ End of composition")
            self.stop()
        if self._pending_msg and self.engine is None and self.recorder is None and "Light engine stopped" in self._pending_msg:
            self.status.setText(self._pending_msg); self._pending_msg = None

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Space and not ev.isAutoRepeat():
            self.stop() if self.is_active() else self.start()
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev):
        self.stop()
        if self.camera is not None:
            self.camera.close(); self.camera = None
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
