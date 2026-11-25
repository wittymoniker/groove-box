"""CANON_MORPH_R7: canonical morph for Live Play keys and samples.

One mechanism: spectral-envelope transfer. The composition that is sounding
gives a target timbre (its cepstral spectral envelope). Keys and samples are
reshaped toward it by an amount a in [0, 1]:  G = (T / E) ** a, clamped to
[1/8, 8], then renormalised so each frame keeps its energy (loudness kept).

Streaming uses sqrt-periodic-Hann analysis and synthesis windows at 50 %
overlap (N=512, hop 256), which reconstruct exactly when G == 1. The stream
delay is a constant N-1 samples for any block size. Keys are
morphed once per note, offline, with the same transform and no latency.

PREDICTIVE_PATHWAY_R7: place a trigger on the predictive time-invariant
process pathway. Each Live Play row is a fixed schedule of onsets, so the next
onset after any instant is known exactly from the current and next row (and
from the beat grid when a row is empty). A trigger waits for that onset when
it is within the window, otherwise it plays at once.
"""
from __future__ import annotations

import numpy as np
try:  # R132.10: project trig route — book isy/isx series when the Trigonometry Engine is ON (gb_trig)
    from gb_trig import ncos as _tncos
except Exception:  # standalone use outside the app
    from numpy import cos as _tncos

N_FFT = 512      # 94 Hz bins at 48 kHz; constant stream latency N-1 = 511 samples (10.6 ms)
HOP = N_FFT // 2
N_CEPS = 20
G_MIN, G_MAX = 1.0 / 8.0, 8.0
_EPS = 1e-9


def _window(n=N_FFT):
    k = np.arange(n)
    return np.sqrt(0.5 - 0.5 * _tncos(2.0 * np.pi * k / n)).astype(np.float64)


def cepstral_envelope(mag, n_ceps=N_CEPS):
    """Smooth spectral envelope of a magnitude spectrum (rfft bins)."""
    mag = np.asarray(mag, dtype=np.float64)
    logm = np.log(np.maximum(mag, _EPS))
    c = np.fft.irfft(logm)
    n = c.shape[0]
    k = max(1, min(int(n_ceps), n // 2))
    lift = np.zeros(n)
    lift[:k] = 1.0
    lift[n - k + 1:] = 1.0
    env = np.exp(np.fft.rfft(c * lift).real)
    return env[: mag.shape[0]]


class EnvelopeMorph:
    def __init__(self, n_fft=N_FFT):
        self.n = int(n_fft)
        self.hop = self.n // 2
        self.win = _window(self.n)
        self.amount = 0.5
        self.target = None          # envelope over rfft bins
        self.target_level = 0.0
        self.reset()

    # ---- target -------------------------------------------------------
    def set_target(self, signal, smooth=0.3):
        x = np.asarray(signal, dtype=np.float64).ravel()
        if x.size < self.n:
            x = np.concatenate([np.zeros(self.n - x.size), x])
        x = x[-self.n:]
        rms = float(np.sqrt(np.mean(x * x)))
        self.target_level = rms
        if not np.isfinite(rms) or rms < 1e-5:
            self.target = None       # silent target -> bypass
            return
        env = cepstral_envelope(np.abs(np.fft.rfft(x * self.win)))
        env = env / max(float(np.mean(env)), _EPS)
        if self.target is None or smooth <= 0:
            self.target = env
        else:                        # smooth in the log domain
            self.target = np.exp((1.0 - smooth) * np.log(self.target) + smooth * np.log(env))

    def active(self):
        return self.target is not None and self.amount > 1e-6

    # ---- core ---------------------------------------------------------
    def _frame(self, frame):
        X = np.fft.rfft(frame * self.win)
        if self.active():
            mag = np.abs(X)
            e0 = float(np.sum(mag * mag))
            if e0 > 1e-12:
                env = cepstral_envelope(mag)
                env = env / max(float(np.mean(env)), _EPS)
                G = np.clip((self.target / np.maximum(env, _EPS)) ** self.amount, G_MIN, G_MAX)
                Y = X * G
                e1 = float(np.sum(np.abs(Y) ** 2))
                if e1 > 1e-12:
                    X = Y * np.sqrt(e0 / e1)
        return np.fft.irfft(X, self.n) * self.win

    LATENCY = N_FFT - 1

    def reset(self):
        # Constant delay N-1 for ANY block size: a frame needs N inputs and completes `hop` outputs,
        # so output k is ready once input k + N - 1 arrived; the FIFO starts with N-1 zeros.
        self._in = np.zeros(0)
        self._ola = np.zeros(self.n)
        self._out = np.zeros(self.n - 1)
        self._started = False

    def process(self, block):
        """Streaming transform; returns exactly len(block) samples (latency = hop)."""
        x = np.asarray(block, dtype=np.float64).ravel()
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)
        self._in = np.concatenate([self._in, x])
        outs = [self._out]
        while self._in.size >= self.n:
            y = self._frame(self._in[: self.n])
            self._in = self._in[self.hop:]
            self._ola += y
            outs.append(self._ola[: self.hop].copy())
            self._ola = np.concatenate([self._ola[self.hop:], np.zeros(self.hop)])
        out = np.concatenate(outs)
        if out.size < x.size:      # cannot happen with the N-1 prefill; kept as a guard
            out = np.concatenate([out, np.zeros(x.size - out.size)])
        self._out = out[x.size:]
        return out[: x.size].astype(np.float32)

    def offline(self, signal):
        """Whole-buffer transform, time aligned, same length (for key notes)."""
        x = np.asarray(signal, dtype=np.float64).ravel()
        if x.size == 0 or not self.active():
            return np.asarray(signal, dtype=np.float32)
        lat = self.n - self.hop
        pad = np.concatenate([np.zeros(lat), x, np.zeros(self.n)])
        win, n, hop = self.win, self.n, self.hop
        out = np.zeros(pad.size + n)
        for s in range(0, pad.size - n + 1, hop):
            out[s:s + n] += self._frame(pad[s:s + n])
        y = out[lat: lat + x.size]
        return y.astype(np.float32)


# ---- predictive time-invariant pathway --------------------------------

def row_onsets(row):
    out = []
    for ev in row or ():
        try:
            out.append(float(ev[0]))
        except Exception:
            pass
    return sorted(set(round(t, 6) for t in out if t >= 0))


def next_onset_delay(plan, row_idx, pos_s, window_s, beat_s=0.5):
    """Seconds to wait until the next predicted onset, or 0.0 if none within window."""
    if window_s <= 0:
        return 0.0
    rows = (plan or {}).get("rows") or []
    row_dur = float((plan or {}).get("row_dur") or 0.0)
    cand = []
    if rows and row_dur > 0:
        ri = int(row_idx) % len(rows)
        cand += row_onsets(rows[ri])
        cand += [t + row_dur for t in row_onsets(rows[(ri + 1) % len(rows)])]
    if not cand:                      # the trivial time-invariant process: the beat
        b = beat_s if beat_s > 0 else 0.5
        k = np.floor(pos_s / b)
        cand = [k * b, (k + 1) * b, (k + 2) * b]
    tol = 0.002                       # within 2 ms counts as "on" the onset
    for t in sorted(cand):
        d = t - pos_s
        if d >= -tol:
            return float(d) if 0 < d <= window_s else 0.0
    return 0.0
