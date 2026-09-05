#!/usr/bin/env python3
"""Deterministic geometric/phaselocked sample cutup renderer for Groovebox Media Hub.

The engine is intentionally independent from Qt. It uses ffmpeg for decode/render and
NumPy for lightweight pitch analysis. A seed + geometric phase lattice determines
slice selection, pitch, rate, pan and reversal in a repeatable way.
"""
from __future__ import annotations

import json
import math
import os
import random
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
TAU = math.tau


@dataclass
class CutEvent:
    step: int
    start_s: float
    duration_s: float
    pitch_semitones: float
    rate: float
    gain: float
    pan: float
    reverse: bool
    phase: float
    source_index: int = 0


def _which_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for the Media Hub Cutup Lab")
    return ffmpeg


def probe_duration(path: str) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        p = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=8, check=False,
        )
        return max(0.0, float((p.stdout or "0").strip() or 0.0))
    except Exception:
        return 0.0


def decode_mono_preview(path: str, sample_rate: int = 12000, seconds: float = 8.0) -> np.ndarray:
    ffmpeg = _which_ffmpeg()
    cmd = [
        ffmpeg, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(int(sample_rate)),
        "-t", f"{float(seconds):.3f}", "-f", "f32le", "pipe:1",
    ]
    p = subprocess.run(cmd, capture_output=True, timeout=max(12, int(seconds * 3) + 8), check=False)
    if p.returncode != 0 or not p.stdout:
        raise RuntimeError((p.stderr or b"ffmpeg decode failed").decode("utf-8", errors="replace")[-600:])
    return np.frombuffer(p.stdout, dtype="<f4").astype(np.float64, copy=False)


def estimate_pitch_hz(path: str, min_hz: float = 45.0, max_hz: float = 1200.0) -> Optional[float]:
    """Estimate a stable fundamental from a short preview using normalized autocorrelation.

    This is intentionally conservative: low-confidence/noisy material returns None rather
    than pretending drums/noise have one meaningful fundamental.
    """
    sr = 12000
    x = decode_mono_preview(path, sample_rate=sr, seconds=8.0)
    if x.size < sr // 2:
        return None
    x = x - float(np.mean(x))
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak < 1e-5:
        return None
    x = x / peak

    frame = min(x.size, sr * 4)
    # Prefer the most energetic contiguous window so quiet intros don't dominate.
    win = sr
    if frame > win:
        energies = np.convolve(x[:frame] * x[:frame], np.ones(win), mode="valid")
        start = int(np.argmax(energies))
        y = x[start:start + win]
    else:
        y = x[:frame]
    if y.size < 1024:
        return None
    y = y * np.hanning(y.size)

    # FFT autocorrelation is cheap even on a Pi for a 1 s / 12 kHz window.
    nfft = 1 << int(math.ceil(math.log2(y.size * 2 - 1)))
    spec = np.fft.rfft(y, n=nfft)
    ac = np.fft.irfft(spec * np.conj(spec), n=nfft)[:y.size]
    if ac[0] <= 1e-12:
        return None
    ac /= ac[0]
    min_lag = max(1, int(sr / max_hz))
    max_lag = min(y.size - 2, int(sr / min_hz))
    if max_lag <= min_lag:
        return None
    region = ac[min_lag:max_lag + 1]
    # Prefer the earliest strong local maximum rather than the absolute maximum.
    # Periodic signals often have nearly equal autocorrelation peaks at 1x, 2x, 3x
    # the period; choosing the global maximum can therefore octave-half the pitch.
    local = []
    for i in range(1, len(region)-1):
        if region[i] >= region[i-1] and region[i] > region[i+1]:
            local.append((i, float(region[i])))
    global_peak = float(np.max(region)) if region.size else 0.0
    strong = [(i,v) for i,v in local if v >= max(0.22, 0.80*global_peak)]
    if strong:
        lag = min_lag + strong[0][0]
    else:
        lag = min_lag + int(np.argmax(region))
    confidence = float(ac[lag])
    if confidence < 0.22:
        return None
    # Parabolic lag interpolation.
    if 1 <= lag < len(ac) - 1:
        a, b, c = float(ac[lag - 1]), float(ac[lag]), float(ac[lag + 1])
        den = a - 2.0 * b + c
        if abs(den) > 1e-12:
            lag = lag + 0.5 * (a - c) / den
    hz = sr / float(lag)
    return hz if min_hz <= hz <= max_hz else None


def nearest_midi_pitch(hz: float, root_midi: int = 60, scale: Sequence[int] = (0, 2, 4, 5, 7, 9, 11)) -> Tuple[int, float]:
    midi = 69.0 + 12.0 * math.log2(max(1e-9, hz) / 440.0)
    candidates: List[int] = []
    root_pc = root_midi % 12
    for octv in range(-5, 7):
        base = (root_midi // 12 + octv) * 12
        for degree in scale:
            candidates.append(base + ((root_pc + degree) % 12))
    best = min(candidates, key=lambda m: abs(m - midi))
    target_hz = 440.0 * (2.0 ** ((best - 69) / 12.0))
    semitones = 12.0 * math.log2(target_hz / hz)
    return best, semitones


def pitch_normalization_shift(path: str, target_hz: Optional[float] = None, root_midi: int = 60) -> Tuple[Optional[float], float, str]:
    detected = estimate_pitch_hz(path)
    if detected is None:
        return None, 0.0, "No stable fundamental detected; leaving pitch unchanged."
    if target_hz and target_hz > 0:
        shift = 12.0 * math.log2(float(target_hz) / detected)
        return detected, shift, f"{detected:.2f} Hz → {float(target_hz):.2f} Hz ({shift:+.2f} st)"
    midi, shift = nearest_midi_pitch(detected, root_midi=root_midi)
    target = 440.0 * (2.0 ** ((midi - 69) / 12.0))
    return detected, shift, f"{detected:.2f} Hz → MIDI {midi} / {target:.2f} Hz ({shift:+.2f} st)"


def _geom01(seed: int, index: int, lane: int = 0) -> float:
    """Deterministic quasi-random [0,1) value from a golden-angle phase lattice."""
    # Random seed contributes only a stable phase offset; stepping stays geometric.
    rng = random.Random((int(seed) & 0x7FFFFFFF) ^ (lane * 0x9E3779B1))
    offset = rng.random() * TAU
    phase = (offset + (index + 1) * GOLDEN_ANGLE * (1.0 + lane / PHI)) % TAU
    # Fold two irrational rotations to avoid visibly linear one-lane sequences.
    u = (phase / TAU + ((index + 1) / (PHI ** (lane + 2)))) % 1.0
    return u


def generate_cut_events(
    duration_s: float,
    bpm: float = 120.0,
    bars: int = 4,
    steps_per_bar: int = 16,
    seed: int = 1975807343,
    slice_divisions: int = 32,
    pitch_range_st: float = 7.0,
    rate_depth: float = 0.20,
    reverse_probability: float = 0.12,
    normalize_shift_st: float = 0.0,
    phase_lock: int = 4,
) -> List[CutEvent]:
    duration_s = max(0.05, float(duration_s))
    bpm = max(1.0, float(bpm))
    bars = max(1, int(bars))
    steps_per_bar = max(1, int(steps_per_bar))
    slice_divisions = max(1, int(slice_divisions))
    phase_lock = max(1, int(phase_lock))
    total_steps = bars * steps_per_bar
    step_duration = 60.0 / bpm * 4.0 / steps_per_bar
    source_slice = duration_s / slice_divisions

    events: List[CutEvent] = []
    for step in range(total_steps):
        # Lock every Nth step to the same geometric family while permitting seeded
        # subphase movement inside that family.
        lock_group = step // phase_lock
        local_phase = step % phase_lock
        u_sel = _geom01(seed + lock_group * 131, local_phase + lock_group, 0)
        # Geometric map: square/cube folding biases toward structurally related slices.
        geom = (u_sel * u_sel + _geom01(seed, lock_group, 1) / PHI) % 1.0
        slice_idx = int(math.floor(geom * slice_divisions)) % slice_divisions
        start = min(max(0.0, slice_idx * source_slice), max(0.0, duration_s - 0.005))

        # Irrational but phaselocked modulation lanes.
        phase = TAU * _geom01(seed, step, 2)
        pitch = normalize_shift_st + pitch_range_st * math.sin(phase)
        # Quantize pitch to quarter-semitones: repeatable enough for musical patterns
        # while still allowing microtonal geometric modulation.
        pitch = round(pitch * 4.0) / 4.0
        rate = 1.0 + float(rate_depth) * math.sin(phase * PHI + GOLDEN_ANGLE)
        rate = max(0.25, min(4.0, rate))
        gain = 0.70 + 0.30 * (0.5 + 0.5 * math.cos(phase + math.pi / 3.0))
        pan = max(-1.0, min(1.0, math.sin(phase / PHI)))
        rev = _geom01(seed, step, 3) < max(0.0, min(1.0, reverse_probability))
        # Slightly overlap source slices if source is short, but cap to pattern step.
        cut_dur = min(max(0.025, source_slice), step_duration * 1.15)
        if start + cut_dur > duration_s:
            cut_dur = max(0.015, duration_s - start)
        events.append(CutEvent(step, start, cut_dur, pitch, rate, gain, pan, rev, phase))
    return events


def playlist_geometric_parameters(count: int, seed: int, pitch_range_st: float = 7.0, rate_depth: float = 0.2, phase_lock: int = 4) -> List[Dict[str, Any]]:
    out = []
    phase_lock = max(1, int(phase_lock))
    for i in range(max(0, int(count))):
        group = i // phase_lock
        phase = TAU * _geom01(seed + group * 17, i % phase_lock + group, 4)
        pitch = round((pitch_range_st * math.sin(phase)) * 4.0) / 4.0
        rate = max(0.25, min(4.0, 1.0 + rate_depth * math.cos(phase * PHI)))
        key = (_geom01(seed, i, 5) + group / PHI) % 1.0
        out.append({
            "index": i,
            "phase": phase,
            "pitch_semitones": pitch,
            "rate": rate,
            "resample": "tape" if (i + group) % 2 == 0 else "preserve-duration",
            "geometry_key": key,
        })
    return out


def _tempo_chain(factor: float) -> str:
    """Return an atempo chain whose product is factor (each node 0.5..2)."""
    factor = max(0.01, float(factor))
    parts: List[float] = []
    while factor > 2.0:
        parts.append(2.0); factor /= 2.0
    while factor < 0.5:
        parts.append(0.5); factor /= 0.5
    parts.append(factor)
    return ",".join(f"atempo={p:.8f}" for p in parts)


def _event_audio_filter(event: CutEvent, sample_rate: int, step_duration: float, resample_mode: str) -> str:
    ratio = 2.0 ** (float(event.pitch_semitones) / 12.0)
    # asetrate changes both pitch and duration. In preserve-duration mode compensate
    # with atempo; in tape mode rate participates directly in pitch/time behavior.
    filters = [
        f"atrim=start={event.start_s:.9f}:duration={event.duration_s:.9f}",
        "asetpts=PTS-STARTPTS",
    ]
    if event.reverse:
        filters.append("areverse")
    if resample_mode == "preserve-duration":
        filters.extend([
            f"asetrate={sample_rate}*{ratio:.12f}",
            f"aresample={sample_rate}",
            _tempo_chain(1.0 / ratio),
            _tempo_chain(event.rate),
        ])
    else:  # tape / resample: pitch and time are intentionally coupled
        combined = ratio * event.rate
        filters.extend([
            f"asetrate={sample_rate}*{combined:.12f}",
            f"aresample={sample_rate}",
        ])
    # Force every event to exactly one grid cell; apad avoids short edge slices.
    filters.extend([
        f"volume={event.gain:.8f}",
        f"apad=pad_dur={step_duration:.9f}",
        f"atrim=duration={step_duration:.9f}",
        "asetpts=PTS-STARTPTS",
    ])
    return ",".join(filters)


def render_cutup(
    source_path: str,
    output_path: str,
    events: Sequence[CutEvent],
    bpm: float,
    steps_per_bar: int,
    sample_rate: int = 48000,
    resample_mode: str = "preserve-duration",
    normalize_peak: bool = True,
) -> str:
    if not events:
        raise ValueError("No cut events to render")
    ffmpeg = _which_ffmpeg()
    sample_rate = max(8000, int(sample_rate))
    step_duration = 60.0 / max(1.0, float(bpm)) * 4.0 / max(1, int(steps_per_bar))
    parts: List[str] = []
    concat_inputs: List[str] = []
    for idx, ev in enumerate(events):
        label = f"e{idx}"
        parts.append(f"[0:a]{_event_audio_filter(ev, sample_rate, step_duration, resample_mode)}[{label}]")
        concat_inputs.append(f"[{label}]")
    parts.append("".join(concat_inputs) + f"concat=n={len(events)}:v=0:a=1[seq]")
    tail = "[seq]"
    if normalize_peak:
        parts.append(f"{tail}alimiter=limit=0.98[outa]")
        tail = "[outa]"

    out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    ext = Path(out).suffix.lower()
    codec: List[str]
    if ext == ".wav":
        codec = ["-c:a", "pcm_s16le"]
    elif ext == ".flac":
        codec = ["-c:a", "flac"]
    elif ext == ".mp3":
        codec = ["-c:a", "libmp3lame", "-b:a", "192k"]
    elif ext in {".ogg", ".oga"}:
        codec = ["-c:a", "libvorbis", "-q:a", "5"]
    elif ext == ".opus":
        codec = ["-c:a", "libopus", "-b:a", "160k"]
    else:
        out += ".wav"
        codec = ["-c:a", "pcm_s16le"]
    cmd = [ffmpeg, "-y", "-v", "error", "-i", source_path, "-filter_complex", ";".join(parts), "-map", tail, "-ar", str(sample_rate)] + codec + [out]
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "ffmpeg cutup render failed")[-1600:])
    # Sidecar makes the result reproducible/editable.
    sidecar = out + ".cutup.json"
    try:
        with open(sidecar, "w", encoding="utf-8") as f:
            json.dump({
                "source": os.path.abspath(source_path),
                "bpm": bpm,
                "steps_per_bar": steps_per_bar,
                "sample_rate": sample_rate,
                "resample_mode": resample_mode,
                "events": [asdict(e) for e in events],
            }, f, indent=2)
    except Exception:
        pass
    return out



def render_av_cutup(
    audio_source: str,
    video_source: str,
    output_path: str,
    events: Sequence[CutEvent],
    bpm: float,
    steps_per_bar: int,
    sample_rate: int = 48000,
    resample_mode: str = "preserve-duration",
    video_fps: int = 30,
) -> str:
    """Render synchronized audio + video cutups from the same phaselocked event list.

    Video uses each event's source start/duration, reversal and playback-rate lane;
    audio additionally applies pitch/resampling. The resulting MP4 is therefore a
    deterministic audiovisual replay of exactly the same geometric pattern.
    """
    if not events:
        raise ValueError("No cut events to render")
    ffmpeg = _which_ffmpeg()
    sample_rate = max(8000, int(sample_rate))
    video_fps = max(1, min(120, int(video_fps)))
    step_duration = 60.0 / max(1.0, float(bpm)) * 4.0 / max(1, int(steps_per_bar))
    parts: List[str] = []
    alabs: List[str] = []
    vlabs: List[str] = []
    for idx, ev in enumerate(events):
        al = f"a{idx}"
        vl = f"v{idx}"
        parts.append(f"[0:a]{_event_audio_filter(ev, sample_rate, step_duration, resample_mode)}[{al}]")
        alabs.append(f"[{al}]")

        # Video intentionally follows rate and reverse but not audio-only pitch shift.
        # setpts normalizes each cut to one grid cell so A/V stays phase locked.
        vfilters = [
            f"trim=start={ev.start_s:.9f}:duration={ev.duration_s:.9f}",
            "setpts=PTS-STARTPTS",
        ]
        if ev.reverse:
            vfilters.append("reverse")
        vfilters.extend([
            f"setpts=PTS/{max(0.05, float(ev.rate)):.12f}",
            f"tpad=stop_mode=clone:stop_duration={step_duration:.9f}",
            f"trim=duration={step_duration:.9f}",
            "setpts=PTS-STARTPTS",
            f"fps={video_fps}",
            "format=yuv420p",
        ])
        parts.append(f"[1:v]{','.join(vfilters)}[{vl}]")
        vlabs.append(f"[{vl}]")
    parts.append("".join(alabs) + f"concat=n={len(events)}:v=0:a=1[aout]")
    parts.append("".join(vlabs) + f"concat=n={len(events)}:v=1:a=0[vout]")
    out = os.path.abspath(output_path)
    if Path(out).suffix.lower() != ".mp4":
        out += ".mp4"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-v", "error", "-i", audio_source, "-i", video_source,
        "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(sample_rate), "-shortest", out,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "ffmpeg audiovisual cutup render failed")[-1800:])
    try:
        with open(out + ".cutup.json", "w", encoding="utf-8") as f:
            json.dump({
                "audio_source": os.path.abspath(audio_source),
                "video_source": os.path.abspath(video_source),
                "bpm": bpm, "steps_per_bar": steps_per_bar, "sample_rate": sample_rate,
                "video_fps": video_fps, "resample_mode": resample_mode,
                "events": [asdict(e) for e in events],
            }, f, indent=2)
    except Exception:
        pass
    return out

def render_pitch_normalized(source_path: str, output_path: str, semitone_shift: float, sample_rate: int = 48000, preserve_duration: bool = True) -> str:
    ffmpeg = _which_ffmpeg()
    ratio = 2.0 ** (float(semitone_shift) / 12.0)
    filt = [f"asetrate={sample_rate}*{ratio:.12f}", f"aresample={sample_rate}"]
    if preserve_duration:
        filt.append(_tempo_chain(1.0 / ratio))
    filt.append("alimiter=limit=0.98")
    out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    cmd = [ffmpeg, "-y", "-v", "error", "-i", source_path, "-vn", "-af", ",".join(filt), "-ar", str(sample_rate), out]
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "ffmpeg pitch normalization failed")[-1200:])
    return out
