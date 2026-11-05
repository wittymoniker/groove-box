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

EXTRA_DJ_EFFECTS = ("beat_gate", "harmonic_fold", "spectral_tilt")


def extra_dj_enabled(host):
    return any(bool(getattr(host, f"live_dj_{key}", False)) for key in EXTRA_DJ_EFFECTS)

def global_dj_enabled(host):
    boost = getattr(host, "_live_dj_boost", None) or {}
    return (getattr(host, "live_dj_goava", False) or getattr(host, "live_dj_random", False)
            or extra_dj_enabled(host) or float(boost.get("amount", 0.0)) > 1e-9)


def configure_extra_dj(engine, host):
    """Copy plain control values only; never read Qt widgets on the audio lane."""
    for key in EXTRA_DJ_EFFECTS:
        value = float(getattr(host, f"live_dj_{key}_amount", 0.0) or 0.0)
        value = max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0
        setattr(engine, f"amount_{key}", value if getattr(host, f"live_dj_{key}", False) else 0.0)


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
    """Deterministic, realtime-safe performance processors and DJ FX."""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = int(max(8000, sample_rate))
        self.seed = 0
        self.amount_goava = 0.0
        self.amount_random = 0.0
        self.amount_beat_gate = 0.0
        self.amount_harmonic_fold = 0.0
        self.amount_spectral_tilt = 0.0
        self._tilt_previous = 0.0
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
            new_rate = int(max(8000, sample_rate))
            if new_rate != self.sample_rate:
                self._tilt_previous = 0.0
            self.sample_rate = new_rate
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
        if self.boost_interval <= 0 or self.boost_amount <= 0.0 or n <= 0:
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
        if amt <= 0.0 or x.size == 0:
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

    def random_parametric(self, x: np.ndarray, *, start_sample: int, bpm: float = 120.0, random_scalar: float = 0.0, amount: float | None = None) -> np.ndarray:
        """Seeded, continuously moving DJ macro; random-looking but repeatable."""
        amt = self.amount_random if amount is None else float(amount)
        if amt <= 0.0 or x.size == 0:
            return x.astype(np.float32, copy=False)
        n = x.size
        t = (float(start_sample) + np.arange(n, dtype=np.float32)) / float(self.sample_rate)
        d = self.pair
        seed_phase = ((self.seed & 0xFFFF) / 65536.0) * math.tau
        beat = float(bpm) / 60.0
        # RAND_PARAM_GRAPH_2026: a pre-evaluated full-graph control scalar steers
        # the realtime-safe LFO family without parsing/evaluating code here.
        gs = float(np.clip(random_scalar, -4.0, 4.0))
        graph_rate = 1.0 + 0.18 * abs(gs)
        graph_phase = 0.35 * gs
        lfo1 = np.sin(math.tau * beat * (0.5 + d.spread) * graph_rate * t + d.phase + seed_phase + graph_phase)
        lfo2 = np.sin(math.tau * beat * (1.0 + d.ratio + 0.08*gs) * t + seed_phase * 0.37 + d.phase * 1.7 - graph_phase)
        # Parametric waveshaper + gated tremolo.  No RNG calls in the audio thread.
        drive = 1.0 + amt * (1.5 + 2.5 * (0.5 + 0.5 * lfo1)) * (1.0 + 0.08 * abs(gs))
        # Dual-mode drive without tanh soft-clip; scale only.
        shaped = x * drive
        trem = 0.72 + 0.28 * (0.5 + 0.5 * lfo2)
        wet = shaped * trem
        # A tiny phase-dependent bipolar component makes adjacent pair IDs audible.
        wet += x * (0.035 * amt) * np.sin(lfo1 + lfo2 + d.phase)
        return self._mix(x, wet, 0.68 * amt)


    def reset_state(self) -> None:
        """Reset chunk-continuity state at a new transport/render boundary."""
        self._tilt_previous = 0.0

    def beat_gate(self, x: np.ndarray, *, start_sample: int, bpm: float = 120.0,
                  amount: float | None = None) -> np.ndarray:
        """Tempo-locked sixteenth-note gate with soft edges and absolute phase."""
        amt = self.amount_beat_gate if amount is None else float(amount)
        if amt <= 0.0 or x.size == 0:
            return x.astype(np.float32, copy=False)
        n = int(x.size)
        rate = max(1.0, float(bpm))
        t = (float(start_sample) + np.arange(n, dtype=np.float64)) * (rate / 15.0) / float(self.sample_rate)
        phase = np.mod(t, 1.0)
        duty = 0.68
        edge = 0.055
        gate = np.ones(n, dtype=np.float32)
        gate[phase >= duty + edge] = 0.08
        fade_in = (phase >= duty - edge) & (phase < duty + edge)
        if np.any(fade_in):
            u = np.clip((phase[fade_in] - (duty - edge)) / (2.0 * edge), 0.0, 1.0)
            smooth = u * u * (3.0 - 2.0 * u)
            gate[fade_in] = (1.0 - smooth * 0.92).astype(np.float32)
        # Smoothly reopen at each sixteenth boundary.
        fade_out = phase < edge
        if np.any(fade_out):
            u = np.clip(phase[fade_out] / edge, 0.0, 1.0)
            smooth = u * u * (3.0 - 2.0 * u)
            gate[fade_out] = (0.08 + smooth * 0.92).astype(np.float32)
        wet = x * gate
        return self._mix(x, wet, 0.85 * amt)

    def harmonic_fold(self, x: np.ndarray, *, amount: float | None = None) -> np.ndarray:
        """Bounded arcsine wavefold; expands upper harmonics without runaway gain."""
        amt = self.amount_harmonic_fold if amount is None else float(amount)
        if amt <= 0.0 or x.size == 0:
            return x.astype(np.float32, copy=False)
        drive = 1.0 + 7.0 * float(np.clip(amt, 0.0, 1.0))
        wet = (2.0 / math.pi) * np.arcsin(np.sin((math.pi / 2.0) * drive * x))
        return self._mix(x, np.asarray(wet, dtype=np.float32), 0.72 * amt)

    def spectral_tilt(self, x: np.ndarray, *, amount: float | None = None) -> np.ndarray:
        """Chunk-continuous high-frequency tilt using a one-sample differentiator."""
        amt = self.amount_spectral_tilt if amount is None else float(amount)
        if amt <= 0.0 or x.size == 0:
            return x.astype(np.float32, copy=False)
        flat = np.asarray(x, dtype=np.float32).reshape(-1)
        prev = float(self._tilt_previous)
        diff = np.empty_like(flat)
        diff[0] = flat[0] - prev
        if flat.size > 1:
            diff[1:] = flat[1:] - flat[:-1]
        self._tilt_previous = float(flat[-1])
        coef = 0.12 + 0.72 * float(np.clip(amt, 0.0, 1.0))
        wet = flat + diff * coef
        wet = wet / (1.0 + 0.10 * coef)
        mixed = self._mix(flat, wet, 0.75 * amt)
        return mixed.reshape(np.asarray(x).shape)

    def process(self, x: np.ndarray, *, start_sample: int, goava_scalar: float = 0.0, random_scalar: float = 0.0, bpm: float = 120.0) -> np.ndarray:
        y = np.asarray(x, dtype=np.float32)
        if self.amount_goava > 0.0:
            y = self.goava_pair_morph(y, start_sample=start_sample, goava_scalar=goava_scalar, bpm=bpm)
        if self.amount_random > 0.0:
            y = self.random_parametric(y, start_sample=start_sample, bpm=bpm, random_scalar=random_scalar)
        if self.amount_beat_gate > 0.0:
            y = self.beat_gate(y, start_sample=start_sample, bpm=bpm)
        if self.amount_harmonic_fold > 0.0:
            y = self.harmonic_fold(y)
        if self.amount_spectral_tilt > 0.0:
            y = self.spectral_tilt(y)
        gain = self._boost_gain(y.size, start_sample)
        if gain is not None:
            y = y * gain
        # No final saturation / hard clip — return the linear mix as-is.
        return y.astype(np.float32, copy=False)
