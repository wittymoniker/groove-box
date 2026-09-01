"""Low-latency live-DJ effect and commutative pair utilities.

Pure NumPy/Python module: no Qt, sounddevice, or application imports.  The
pair space is intentionally unordered: (A, B) == (B, A), so every distinct
pair has exactly one stable index and one deterministic parameter signature.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class PairDescriptor:
    a: int
    b: int
    index: int
    signature: int
    phase: float
    ratio: float
    spread: float


class CommutativePairSpace:
    """Stable non-redundant unordered pair space for N sound/visual identities."""

    def __init__(self, size: int):
        self.size = max(2, int(size))
        self.count = self.size * (self.size - 1) // 2

    def normalize(self, a: int, b: int) -> tuple[int, int]:
        a = int(a) % self.size
        b = int(b) % self.size
        if a == b:
            b = (b + 1) % self.size
        return (a, b) if a < b else (b, a)

    def index(self, a: int, b: int) -> int:
        """Lexicographic rank of an unordered pair, 0 <= rank < C(N,2)."""
        a, b = self.normalize(a, b)
        # Number of pairs beginning before a + offset within a's row.
        return a * (2 * self.size - a - 1) // 2 + (b - a - 1)

    def descriptor(self, a: int, b: int) -> PairDescriptor:
        a, b = self.normalize(a, b)
        idx = self.index(a, b)
        raw = hashlib.blake2b(f"eqr-pair|{self.size}|{a}|{b}".encode(), digest_size=16).digest()
        u0 = int.from_bytes(raw[0:8], "big") / 2**64
        u1 = int.from_bytes(raw[8:16], "big") / 2**64
        return PairDescriptor(
            a=a,
            b=b,
            index=idx,
            signature=int.from_bytes(raw[:8], "big"),
            phase=math.tau * u0,
            ratio=0.5 + 1.5 * u1,
            spread=0.15 + 0.85 * ((idx + 1) / max(1, self.count)),
        )

    def all_pairs(self) -> Iterable[PairDescriptor]:
        for a in range(self.size):
            for b in range(a + 1, self.size):
                yield self.descriptor(a, b)


class LiveDJEffects:
    """Two deterministic, realtime-safe performance processors."""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = int(max(8000, sample_rate))
        self.seed = 0
        self.amount_goava = 0.0
        self.amount_random = 0.0
        self.pair_space = CommutativePairSpace(48)
        self.pair = self.pair_space.descriptor(0, 1)
        # DJ Boost Hit: a periodic raised window with period = interval samples.
        # The FIRST trigger sits at `boost_phase` (randomized per engagement), so
        # the hit lands at a different position inside each interval every time
        # the effect is armed.  interval <= 0 disables the envelope entirely.
        self.boost_interval = 0
        self.boost_phase = 0.0
        self.boost_amount = 0.0

    def set_context(self, *, seed: float = 0.0, pair: tuple[int, int] = (0, 1), sample_rate: int | None = None) -> None:
        self.seed = int(abs(float(seed)) * 1000003) & 0xFFFFFFFF
        if sample_rate is not None:
            self.sample_rate = int(max(8000, sample_rate))
        self.pair = self.pair_space.descriptor(*pair)

    def set_boost(self, interval: int = 0, phase: float = 0.0, amount: float = 0.0) -> None:
        """Arm the periodic Boost Hit envelope (interval in samples).

        The first trigger fires at absolute-sample `phase`; afterwards it repeats
        every `interval` samples.  Callers pick a fresh `phase` (random) whenever
        the boost is re-armed so each engagement lands differently.
        """
        self.boost_interval = max(0, int(interval))
        self.boost_phase = float(phase)
        self.boost_amount = float(np.clip(amount, 0.0, 1.0))

    def _boost_gain(self, n: int, start_sample: int) -> np.ndarray | None:
        if self.boost_interval <= 0 or self.boost_amount <= 1e-6 or n <= 0:
            return None
        t = float(start_sample) + np.arange(n, dtype=np.float32)
        pos = (t - self.boost_phase) % float(self.boost_interval)
        width = max(1.0, float(self.boost_interval) * 0.06)
        gain = 1.0 + self.boost_amount * np.exp(-0.5 * ((pos / width) ** 2))
        return gain.astype(np.float32, copy=False)

    @staticmethod
    def _mix(dry: np.ndarray, wet: np.ndarray, amount: float) -> np.ndarray:
        a = float(np.clip(amount, 0.0, 1.0))
        return (dry * (1.0 - a) + wet * a).astype(np.float32, copy=False)

    def goava_pair_morph(self, x: np.ndarray, *, start_sample: int, goava_scalar: float = 0.0, bpm: float = 120.0, amount: float | None = None) -> np.ndarray:
        """GOAVA-derived ring/drive morph; the unordered pair selects its timbre."""
        amt = self.amount_goava if amount is None else float(amount)
        if amt <= 1e-6 or x.size == 0:
            return x.astype(np.float32, copy=False)
        n = x.size
        t = (float(start_sample) + np.arange(n, dtype=np.float32)) / float(self.sample_rate)
        d = self.pair
        raw = float(goava_scalar)
        mod_hz = abs(raw) * (float(bpm) / 60.0) * (0.5 + d.spread)
        mod = np.sin(math.tau * mod_hz * t + d.phase).astype(np.float32)
        drive = 1.0 + 2.8 * (0.25 + 0.75 * d.ratio) * amt
        # Dual-mode drive, no tanh saturation.
        wet = (x * drive) * (0.78 + 0.22 * mod)
        # Preserve polarity while giving the GOAVA scalar a musically obvious sideband.
        wet += x * (0.16 * amt) * mod
        return self._mix(x, wet, 0.55 * amt)

    def random_parametric(self, x: np.ndarray, *, start_sample: int, bpm: float = 120.0, amount: float | None = None) -> np.ndarray:
        """Seeded, continuously moving DJ macro; random-looking but repeatable."""
        amt = self.amount_random if amount is None else float(amount)
        if amt <= 1e-6 or x.size == 0:
            return x.astype(np.float32, copy=False)
        n = x.size
        t = (float(start_sample) + np.arange(n, dtype=np.float32)) / float(self.sample_rate)
        d = self.pair
        seed_phase = ((self.seed & 0xFFFF) / 65536.0) * math.tau
        beat = float(bpm) / 60.0
        lfo1 = np.sin(math.tau * beat * (0.5 + d.spread) * t + d.phase + seed_phase)
        lfo2 = np.sin(math.tau * beat * (1.0 + d.ratio) * t + seed_phase * 0.37 + d.phase * 1.7)
        # Parametric waveshaper + gated tremolo.  No RNG calls in the audio thread.
        drive = 1.0 + amt * (1.5 + 2.5 * (0.5 + 0.5 * lfo1))
        # Dual-mode drive without tanh soft-clip; scale only.
        shaped = x * drive
        trem = 0.72 + 0.28 * (0.5 + 0.5 * lfo2)
        wet = shaped * trem
        # A tiny phase-dependent bipolar component makes adjacent pair IDs audible.
        wet += x * (0.035 * amt) * np.sin(lfo1 + lfo2 + d.phase)
        return self._mix(x, wet, 0.68 * amt)

    def process(self, x: np.ndarray, *, start_sample: int, goava_scalar: float = 0.0, bpm: float = 120.0) -> np.ndarray:
        y = np.asarray(x, dtype=np.float32)
        if self.amount_goava > 1e-6:
            y = self.goava_pair_morph(y, start_sample=start_sample, goava_scalar=goava_scalar, bpm=bpm)
        if self.amount_random > 1e-6:
            y = self.random_parametric(y, start_sample=start_sample, bpm=bpm)
        gain = self._boost_gain(y.size, start_sample)
        if gain is not None:
            y = y * gain
        # No final saturation / hard clip — return the linear mix as-is.
        return y.astype(np.float32, copy=False)
