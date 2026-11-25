"""AUDIO_FEATURES_R7 - one measured description of the audio, shared by video and games.

Everything here is a pure, stateless function of an audio window (or of a whole track), so
live, export and game runs see the same numbers for the same audio, frame-parallel renders stay
deterministic, and nothing ever feeds back into the audio.

Per window:
    rms, peak            true level of the full-resolution window (no decimation)
    bands[8]             octave energy shares in REAL Hz, 40 Hz .. 16 kHz (sum 1)
    centroid             spectral centroid on a log-Hz scale, 0 (40 Hz) .. 1 (16 kHz)
    flux / onset         positive spectral change between the window's two halves (0..1);
                         stateless, so frame order never matters
    chroma[12], pitch_class, tonal
                         pitch-class energy (C=0), the dominant class and how tonal (vs noisy)
                         the window is (1 - spectral flatness)

Previously the visualiser linearly resampled each window to 256 points (aliasing every partial
above ~3 kHz into fake low ones), computed its 'bands' on an arbitrary 256 Hz axis and its
'centroid' in the time domain; games read |one sample| of their own internal bed.
"""
from __future__ import annotations

import math
try:  # R132.10: project trig route — book isy/isx series when the Trigonometry Engine is ON (gb_trig)
    from gb_trig import ncos as _tncos
except Exception:  # standalone use outside the app
    from numpy import cos as _tncos
from typing import Dict, Optional

import numpy as np

BAND_EDGES_HZ = np.geomspace(40.0, 16000.0, 9)
_LOG_LO, _LOG_HI = math.log(40.0), math.log(16000.0)
N_FFT_MAX = 4096


def _hann(n: int) -> np.ndarray:
    return (0.5 - 0.5 * _tncos(2.0 * np.pi * np.arange(n) / max(1, n))).astype(np.float32)


def _spectrum(x: np.ndarray, sr: float):
    n = int(x.size)
    nfft = 1 << max(6, min(int(math.log2(N_FFT_MAX)), int(math.ceil(math.log2(max(64, n))))))
    seg = x[-nfft:] if n > nfft else x
    mag = np.abs(np.fft.rfft(seg * _hann(seg.size), n=nfft)).astype(np.float64)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / float(sr))
    return mag, freqs


def _bands(mag, freqs):
    p = mag * mag
    idx = np.searchsorted(freqs, BAND_EDGES_HZ)
    out = np.array([float(np.sum(p[idx[b]:idx[b + 1]])) for b in range(8)], dtype=np.float64)
    tot = float(np.sum(out))
    return (out / tot) if tot > 0.0 and math.isfinite(tot) else np.full(8, 0.125)


def _chroma(mag, freqs):
    sel = (freqs >= 55.0) & (freqs <= 5000.0)
    f, p = freqs[sel], (mag[sel] ** 2)
    if f.size == 0 or float(np.sum(p)) <= 0.0:
        return np.full(12, 1.0 / 12.0), 0.0
    pc = np.mod(np.round(12.0 * np.log2(f / 261.6255653)), 12).astype(np.int64)
    ch = np.bincount(pc, weights=p, minlength=12)[:12]
    ch = ch / float(np.sum(ch))
    flat = float(np.exp(np.mean(np.log(p + 1e-20))) / (np.mean(p) + 1e-20))
    return ch, float(np.clip(1.0 - flat, 0.0, 1.0))


def frame_features(window, sr: float = 44100.0) -> Dict[str, object]:
    x = np.nan_to_num(np.asarray(window, dtype=np.float32).ravel(), nan=0.0, posinf=0.0, neginf=0.0)
    sr = float(sr) if sr and math.isfinite(float(sr)) and float(sr) > 0 else 44100.0
    if x.size < 16:
        x = np.zeros(64, dtype=np.float32)
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(x)))
    mag, freqs = _spectrum(x, sr)
    bands = _bands(mag, freqs)
    p = mag * mag
    sel = (freqs >= 40.0) & (freqs <= 16000.0)
    tot = float(np.sum(p[sel]))
    if tot > 0.0:
        c_hz = float(np.sum(freqs[sel] * p[sel]) / tot)
        centroid = float(np.clip((math.log(max(40.0, c_hz)) - _LOG_LO) / (_LOG_HI - _LOG_LO), 0.0, 1.0))
    else:
        centroid = 0.5
    half = x.size // 2
    if half >= 32:
        b1 = _bands(*_spectrum(x[:half], sr))
        b2 = _bands(*_spectrum(x[half:], sr))
        e1 = float(np.sqrt(np.mean(x[:half].astype(np.float64) ** 2)))
        e2 = float(np.sqrt(np.mean(x[half:].astype(np.float64) ** 2)))
        flux = float(np.sum(np.maximum(0.0, b2 * e2 - b1 * e1)))
        onset = float(np.clip(flux / (rms + 1e-6), 0.0, 1.0)) if rms > 1e-5 else 0.0
    else:
        flux, onset = 0.0, 0.0
    chroma, tonal = _chroma(mag, freqs)
    return {"rms": rms, "peak": peak, "bands": bands.astype(np.float32), "centroid": centroid,
            "flux": flux, "onset": onset, "chroma": chroma.astype(np.float32),
            "pitch_class": int(np.argmax(chroma)) if float(np.max(chroma)) > (1.0 / 12.0 + 1e-6) else -1,
            "tonal": tonal}


class FeatureTrack:
    """Features for a whole track at a fixed frame rate (computed once, then O(1) lookups).
    Games load this from the composition they ship with and read it at the music clock."""

    def __init__(self, fps: float, rms, onset, centroid, bands, pitch_class, tonal, duration: float):
        self.fps = float(fps)
        self.rms, self.onset, self.centroid = rms, onset, centroid
        self.bands, self.pitch_class, self.tonal = bands, pitch_class, tonal
        self.duration = float(duration)
        pk = float(np.percentile(rms, 95)) if rms.size else 0.0
        self.level = np.clip(rms / pk, 0.0, 1.5) if pk > 0 else np.zeros_like(rms)   # loudness relative to the track
        self.beats = self._pick_beats()

    @classmethod
    def from_audio(cls, samples, sr: float, fps: float = 30.0, window_s: float = 0.0464):
        a = np.asarray(samples, dtype=np.float32)
        if a.ndim == 2:
            a = a.mean(axis=1 if a.shape[1] <= 8 else 0)
        a = a.ravel()
        if not np.isfinite(a).all():           # STREAM_LOAD_R7: copy only when there is something to clean
            a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
        sr = float(sr) if sr else 44100.0
        hop = max(1, int(round(sr / float(fps))))
        win = max(256, int(round(sr * window_s)))
        n = max(1, int(math.ceil(a.size / hop)))
        R, O, C, T = (np.zeros(n, np.float32) for _ in range(4))
        B = np.zeros((n, 8), np.float32)
        P = np.full(n, -1, np.int16)
        for i in range(n):
            c = i * hop
            seg = a[max(0, c - win // 2): c + win // 2]
            f = frame_features(seg if seg.size >= 16 else np.zeros(64, np.float32), sr)
            R[i], O[i], C[i], T[i] = f["rms"], f["onset"], f["centroid"], f["tonal"]
            B[i], P[i] = f["bands"], f["pitch_class"]
        return cls(fps, R, O, C, B, P, T, a.size / sr)

    def _pick_beats(self):
        """Onset peaks above a local mean (at most ~8 per second) -> times in seconds."""
        o = self.onset
        if o.size < 3:
            return np.zeros(0, np.float32)
        k = max(1, int(self.fps * 0.25))
        pad = np.pad(o, k, mode="edge")
        local = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
        gap = max(1, int(self.fps / 8.0))
        out, last = [], -gap
        for i in range(1, o.size - 1):
            if o[i] >= o[i - 1] and o[i] > o[i + 1] and o[i] > local[i] * 1.3 and o[i] > 0.08 and i - last >= gap:
                out.append(i / self.fps); last = i
        return np.asarray(out, np.float32)

    def at(self, t: float) -> Dict[str, object]:
        if self.rms.size == 0:
            return {"rms": 0.0, "level": 0.0, "onset": 0.0, "centroid": 0.5, "bands": np.full(8, 0.125, np.float32),
                    "pitch_class": -1, "tonal": 0.0, "beat_phase": 0.0, "to_next_beat": 1.0}
        t = float(t) % max(1e-6, self.duration) if self.duration > 0 else 0.0
        i = int(min(self.rms.size - 1, max(0, round(t * self.fps))))
        phase, to_next = 0.0, 1.0
        if self.beats.size:
            j = int(np.searchsorted(self.beats, t, side="right"))
            prev = float(self.beats[j - 1]) if j > 0 else 0.0
            nxt = float(self.beats[j]) if j < self.beats.size else self.duration
            span = max(1e-3, nxt - prev)
            phase, to_next = (t - prev) / span, nxt - t
        return {"rms": float(self.rms[i]), "level": float(self.level[i]), "onset": float(self.onset[i]),
                "centroid": float(self.centroid[i]), "bands": self.bands[i], "pitch_class": int(self.pitch_class[i]),
                "tonal": float(self.tonal[i]), "beat_phase": float(phase), "to_next_beat": float(to_next)}


def _pcm_to_float(raw, sw):
    if sw == 2:
        return np.frombuffer(raw, "<i2").astype(np.float32) * (1.0 / 32768.0)
    if sw == 4:
        return np.frombuffer(raw, "<i4").astype(np.float32) * (1.0 / 2147483648.0)
    if sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        v = (b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16))
        return (np.where(v >= 1 << 23, v - (1 << 24), v)).astype(np.float32) * (1.0 / 8388608.0)
    return None


def load_track(path: str, fps: float = 30.0) -> Optional[FeatureTrack]:
    """FeatureTrack from a PCM wav (16/24/32-bit int or float32); None if unreadable.

    STREAM_LOAD_R7: read in chunks straight into one mono float32 buffer (peak memory ≈ one mono copy
    instead of raw + float + mono copies: a long 32-bit stereo take no longer risks running out of RAM)."""
    CH = 1 << 20
    try:
        import wave
        with wave.open(path, "rb") as w:
            sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
            if sw not in (2, 3, 4) or ch < 1:
                return None
            mono = np.empty(n, np.float32)
            got = 0
            while got < n:
                raw = w.readframes(min(CH, n - got))
                if not raw:
                    break
                a = _pcm_to_float(raw, sw)
                k = a.size // ch
                if k <= 0:
                    break
                a = a[:k * ch]
                mono[got:got + k] = a.reshape(-1, ch).mean(axis=1) if ch > 1 else a
                got += k
        return FeatureTrack.from_audio(mono[:got], sr, fps)
    except Exception:
        try:          # float wav (WAVE_FORMAT_IEEE_FLOAT) is not readable by the wave module
            import soundfile as sf
            with sf.SoundFile(path) as f:
                sr, n = f.samplerate, f.frames
                mono = np.empty(max(0, n), np.float32)
                got = 0
                for blk in f.blocks(blocksize=CH, dtype="float32", always_2d=True):
                    k = min(blk.shape[0], mono.size - got)
                    mono[got:got + k] = blk[:k].mean(axis=1)
                    got += k
            return FeatureTrack.from_audio(mono[:got], sr, fps)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# ANALOGY_R7 - what happens in the music -> what happens in the seeded world.
#
# One fixed, physically motivated pairing (the analogy) shared by video and games, so the same
# musical event always means the same kind of thing on screen:
#
#     music                      world channel   meaning in games / video
#     level   (loudness)      -> energy          activity, camera push, gate pressure
#     onset   (attack)        -> pulse           impacts, spawns, bloom flashes
#     beat_phase              -> phase           the gate / camera clock (0..1 between beats)
#     centroid (brightness)   -> altitude        height, light, how "airy" the scene is
#     tonal  (pitched vs noise)-> order          low entropy = study/score; noise = arcade/combat
#     low bands (40-320 Hz)   -> weight          gravity / mass / ground shake
#     high bands (2.5-16 kHz) -> sparkle         particles, glints, small detail
#     pitch class             -> element, hue    one of 12 seeded elements, circle-of-fifths hue
#
# The SEED never changes which musical quantity drives which channel (that would break the
# analogy); it sets how strongly each channel responds (gain 0.5..1.0), which of the world's 12
# seeded elements a pitch class stands for (a seeded rotation of the circle of fifths, so related
# keys stay neighbours), and a seeded hue origin.  Pure and deterministic: same audio + same seed
# -> the same world reaction, in a live game, a live view or an export.
# ---------------------------------------------------------------------------
ANALOGY_CHANNELS = ("energy", "pulse", "phase", "altitude", "order", "weight", "sparkle")
ANALOGY_TEXT = {
    "energy": "loudness drives activity and camera push",
    "pulse": "note attacks drive impacts, spawns and flashes",
    "phase": "the beat clock drives the activity gate and camera sway",
    "altitude": "spectral brightness drives height and light",
    "order": "pitched sound favours study/score; noise favours arcade/combat",
    "weight": "bass drives gravity, mass and ground shake",
    "sparkle": "treble drives particles and glints",
}


def _seed_unit(seed, tag: str) -> float:
    import zlib
    try:
        s = repr(round(float(seed), 9))
    except Exception:
        s = str(seed)
    return (zlib.crc32((s + "|" + tag).encode("utf-8")) & 0xFFFFFFFF) / 4294967296.0


def analogy_profile(seed) -> Dict[str, object]:
    """The seed's fixed reading of the music (gains, element rotation, hue origin)."""
    gains = {c: 0.5 + 0.5 * _seed_unit(seed, "gain/" + c) for c in ANALOGY_CHANNELS}
    return {"gains": gains, "element_offset": int(_seed_unit(seed, "element") * 12) % 12,
            "hue_origin": 360.0 * _seed_unit(seed, "hue")}


def analogy(features: Dict[str, object], seed=0.0, profile: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    """Map one feature dict (frame_features or FeatureTrack.at) onto the world channels (all 0..1,
    plus 'element' 0..11 or -1 and 'hue' in degrees)."""
    p = profile or analogy_profile(seed)
    g = p["gains"]
    f = features or {}

    def num(k, d=0.0):
        try:
            v = float(f.get(k, d))
            return v if math.isfinite(v) else d
        except Exception:
            return d
    b = np.nan_to_num(np.asarray(f.get("bands", np.full(8, 0.125)), dtype=np.float64).ravel(), nan=0.125)
    if b.size != 8:
        b = np.full(8, 0.125)
    level = num("level", -1.0)
    if level < 0.0:                                   # live window: no track-relative level, use rms
        level = min(1.5, 4.0 * num("rms"))
    raw = {"energy": min(1.0, level), "pulse": num("onset"), "phase": num("beat_phase") % 1.0,
           "altitude": num("centroid", 0.5), "order": num("tonal"),
           "weight": float(np.clip(np.sum(b[:3]) * 2.0, 0.0, 1.0)),
           "sparkle": float(np.clip(np.sum(b[5:]) * 3.0, 0.0, 1.0))}
    out = {c: (raw[c] if c == "phase" else float(np.clip(raw[c] * g[c], 0.0, 1.0))) for c in ANALOGY_CHANNELS}
    for c in ANALOGY_CHANNELS:                         # MATH_INVARIANTS_R7: A(f, s) ∈ [0,1]; NaN never reaches a world
        if not math.isfinite(out[c]):
            out[c] = 0.0
    pc = int(f.get("pitch_class", -1) if f.get("pitch_class", -1) is not None else -1)
    if 0 <= pc < 12:
        fifth = (pc * 7) % 12                         # circle of fifths: related keys are neighbours
        out["element"] = (fifth + int(p["element_offset"])) % 12
        out["hue"] = (float(p["hue_origin"]) + 30.0 * fifth) % 360.0
    else:
        out["element"], out["hue"] = -1, float(p["hue_origin"])
    return out


def describe_analogy(seed) -> list:
    """Human-readable lines for the seed's analogy (shown in games and the visualiser)."""
    p = analogy_profile(seed)
    lines = ["%s (x%.2f): %s" % (c, p["gains"][c], ANALOGY_TEXT[c]) for c in ANALOGY_CHANNELS]
    lines.append("pitch: each note class names one of 12 seeded elements (rotation %d), hue origin %.0f deg"
                 % (p["element_offset"], p["hue_origin"]))
    return lines
