"""makeup_audio.py — GROOVEBOX_R32_PLAYER_MAKEUP_AUDIO_20261110

Make-up audio for media that has no sound (video-only files, images, silent streams), and on
request layered under media that does ("Mk+").  Deterministic: the same file gives the same
make-up track every time (seeded by the file name + size), locked to the player's position so a
seek or pause moves it with the picture.

Generators (Compatibility ▸ "Make-up generator"):
    drone   three just-intonation partials with a slow breathing envelope (default)
    pulse   soft pitched pulses on a seeded tempo (60–120 BPM)
    bed     band-limited noise bed with seeded spectral tilt (room tone)
    chord   seeded triad that changes every 8 beats (I–vi–IV–V family)
Levels (Compatibility ▸ "Video-only make-up audio"): off · low (−16 dBFS) · high (−4 dBFS).
"""
from __future__ import annotations

import hashlib
import math
import os
import threading

import numpy as np

KINDS = ("drone", "pulse", "bed", "chord")
LEVELS = {"off": 0.0, "low": 0.15, "high": 0.6}


def seed_for(path):
    try:
        st = os.stat(path); key = "%s|%d" % (os.path.basename(path), st.st_size)
    except Exception:
        key = str(path)
    return int.from_bytes(hashlib.blake2b(key.encode("utf-8", "replace"), digest_size=8).digest(), "little")


class MakeupGenerator:
    def __init__(self, path, kind="drone", level=0.15, sr=48000):
        self.sr = int(sr); self.kind = kind if kind in KINDS else "drone"
        self.level = float(level); self.seed = seed_for(path)
        r = np.random.default_rng(self.seed)
        self.root = 55.0 * 2 ** (int(r.integers(0, 24)) / 12.0)          # A1..G#3, equal-tempered root
        self.bpm = float(r.integers(60, 121))
        self.tilt = float(r.uniform(0.2, 0.9))
        self.prog = [int(x) for x in r.choice([0, 9, 5, 7], size=4, replace=False)]
        self._pos = 0.0; self._playing = False; self._stream = None; self._lock = threading.Lock()
        self._noise_state = np.zeros(2)

    # the player calls these
    def set_position(self, seconds, playing=True):
        with self._lock:
            if abs(seconds - self._pos) > 0.25 or not playing:
                self._pos = float(seconds)
            self._playing = bool(playing)

    def set_level(self, level):
        self.level = float(level)

    def render(self, t0, n):
        t = t0 + np.arange(n) / self.sr
        k = self.kind
        if k == "pulse":
            beat = self.bpm / 60.0
            ph = (t * beat) % 1.0
            env = np.exp(-ph * 9.0)
            x = env * np.sin(2 * np.pi * self.root * 2 * t) * 0.8
        elif k == "bed":
            r = np.random.default_rng((self.seed + int(t0 * 10)) & 0xFFFFFFFF)
            w = r.standard_normal(n)
            a = self.tilt
            try:                                                          # one-pole low-pass, state kept
                from scipy.signal import lfilter
                y, zf = lfilter([1 - a], [1, -a], w, zi=self._noise_state[:1] * a)
                self._noise_state[0] = y[-1]
            except Exception:
                y = np.empty(n); s = self._noise_state[0]
                for i in range(n):
                    s = a * s + (1 - a) * w[i]; y[i] = s
                self._noise_state[0] = s
            x = y * 1.6
        elif k == "chord":
            bar = int(t0 * self.bpm / 60.0 / 8.0) % 4
            root = self.root * 2 ** (self.prog[bar] / 12.0)
            x = sum(np.sin(2 * np.pi * root * m * t) for m in (1.0, 1.25, 1.5)) / 3.0
            x *= 0.6 + 0.4 * np.sin(2 * np.pi * t / 8.0) ** 2
        else:
            x = (np.sin(2 * np.pi * self.root * t) + 0.5 * np.sin(2 * np.pi * self.root * 1.5 * t)
                 + 0.33 * np.sin(2 * np.pi * self.root * 2.0 * t)) / 1.83
            x *= 0.7 + 0.3 * np.sin(2 * np.pi * t / 11.0)
        return (x * self.level).astype(np.float32)

    def _cb(self, outdata, frames, _t, _st):
        with self._lock:
            playing, t0 = self._playing, self._pos
            if playing:
                self._pos += frames / self.sr
        if not playing or self.level <= 0.0:
            outdata.fill(0); return
        y = self.render(t0, frames)
        outdata[:, 0] = y
        if outdata.shape[1] > 1:
            outdata[:, 1] = y

    def start(self, device=None):
        if self._stream is not None or self.level <= 0.0:
            return True
        try:
            import sounddevice as sd
            self._stream = sd.OutputStream(samplerate=self.sr, channels=2, dtype="float32",
                                           callback=self._cb, device=device, latency="high")
            self._stream.start()
            return True
        except Exception:
            self._stream = None
            return False

    def stop(self):
        s, self._stream = self._stream, None
        if s is not None:
            try:
                s.stop(); s.close()
            except Exception:
                pass
