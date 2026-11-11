"""held_sustain.py — GROOVEBOX_R32_HELD_SUSTAIN_20261109

Holding a key extends the envelope's SUSTAIN for as long as it is held; releasing it
starts the release.  A pre-rendered key buffer has attack · decay · sustain · release
regions; for a held key the voice is built as

    attack+decay  →  sustain region looped seamlessly (book-isn crossfaded)  → …

up to ``MAX_HOLD_S``.  On key release the playing voice is cut at its current position
with an isn-shaped release of ``release_s`` (from the key's envelope), so a short tap
sounds exactly as before and a long press sustains.

Pure NumPy; no filters (hardcoded-FX direction).
"""
from __future__ import annotations

import math

import numpy as np

MAX_HOLD_S = 16.0
XFADE_S = 0.012


def _isn_ramp(n):
    if n <= 1:
        return np.ones(max(0, n), dtype=np.float32)
    x = np.linspace(0.0, math.pi / 2.0, n, dtype=np.float64)
    return np.sin(x).astype(np.float32) ** 2


def sustain_region(buf, sr):
    """(start, end) of the steadiest stretch after the attack: the 40 %..75 % window by default,
    moved to where the block RMS changes least."""
    n = int(buf.size)
    if n < sr * 0.05:
        return None
    a, b = int(n * 0.40), int(n * 0.75)
    blk = max(64, int(sr * 0.01))
    if b - a > 4 * blk:
        env = np.sqrt(np.add.reduceat(buf[a:b].astype(np.float64) ** 2, np.arange(0, b - a, blk)) / blk)
        if env.size > 3:
            d = np.abs(np.diff(env))
            k = int(np.argmin(np.convolve(d, np.ones(3), mode="valid"))) if d.size > 3 else 0
            a2 = a + k * blk
            b2 = min(b, a2 + max(4 * blk, (b - a) // 2))
            if b2 - a2 > 4 * blk:
                a, b = a2, b2
    if b - a < int(sr * 0.02):
        return None
    return a, b


def extend_for_hold(buf, sr, max_s=MAX_HOLD_S):
    """The held-key voice: attack/decay then the sustain region looped up to max_s seconds."""
    x = np.asarray(buf, dtype=np.float32).ravel()
    reg = sustain_region(x, sr)
    if reg is None:
        return x
    a, b = reg
    loop = x[a:b].copy()
    xf = min(int(sr * XFADE_S), loop.size // 4)
    if xf > 2:
        r = _isn_ramp(xf)
        loop[:xf] = loop[:xf] * r + x[b - xf:b] * (1.0 - r)
    total = int(max_s * sr)
    reps = max(1, int(math.ceil(max(0, total - a) / float(loop.size))))
    body = np.tile(loop, reps)[: max(0, total - a)]
    return np.concatenate([x[:a], body]).astype(np.float32)


def release_tail(buf, pos, sr, release_s=0.2):
    """Cut ``buf`` at ``pos`` and append an isn release of ``release_s`` from that point."""
    x = np.asarray(buf, dtype=np.float32)
    pos = max(0, min(int(pos), x.size))
    n = max(1, int(float(release_s) * sr))
    seg = x[pos:pos + n]
    if seg.size < n:
        seg = np.concatenate([seg, np.zeros(n - seg.size, dtype=np.float32)])
    fade = _isn_ramp(n)[::-1]
    return np.concatenate([x[:pos], seg * fade]).astype(np.float32)


class HeldKeys:
    """Tracks which keys are held and which voice buffer belongs to each."""

    def __init__(self):
        self.held = {}          # ch -> monotonic press time
        self.voice = {}         # ch -> extended buffer object (identity) in the poly mixer

    def press(self, ch, t):
        self.held[ch] = t

    def is_held(self, ch):
        return ch in self.held

    def bind(self, ch, buf):
        self.voice[ch] = buf

    def release(self, ch):
        self.held.pop(ch, None)
        return self.voice.pop(ch, None)


def release_in_mixer(voices, lock, target, sr, release_s):
    """Replace the voice whose buffer *is* ``target`` with its released version."""
    if target is None:
        return False
    with lock:
        for i, v in enumerate(voices):
            try:
                buf, pos = v[0], v[1]
            except Exception:
                continue
            if buf is target:
                new = release_tail(buf, pos, sr, release_s)
                voices[i] = (new,) + tuple(v[1:])
                return True
    return False
