"""Seeded Live Jam control core.

Jam-only input mapping and deterministic macro/sequence state.  This module is
intentionally independent of Qt/audio callbacks: the host can consume emitted
immutable event dictionaries on its existing live-audio lane.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import random
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

MACRO_KEYS = tuple(f"F{i}" for i in range(1, 13))
ARROW_KEYS = ("LEFT", "RIGHT", "UP", "DOWN")
MOUSE_FUNCTIONS = ("MOUSE_1", "MOUSE_2", "MOUSE_3")


def _seed_int(seed: Any) -> int:
    raw = str(seed if seed is not None else "").encode("utf-8", "replace")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


@dataclass
class JamEvent:
    kind: str
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self):
        return {"kind": self.kind, "timestamp": float(self.timestamp), **self.payload}


class LiveJamController:
    """Deterministic jam-only macro, envelope and nested-sequence controller.

    Randomized bindings are opt-in and scoped to this controller. Normal app
    editing/playback bindings are never modified. F1-F12 produce normalized
    macro values; hosts map those values to synth parameters of their choice.
    """
    def __init__(self, seed: Any = 0, *, seeded_mode: bool = True):
        self._lock = threading.RLock()
        self.seed = seed
        self.seeded_mode = bool(seeded_mode)
        self.randomize_bindings = False
        self.enabled = False
        self.macros = {k: 0.5 for k in MACRO_KEYS}
        self.envelope = {"attack": 0.5, "release": 0.5, "filter": 0.5, "damping": 0.5,
                         "resonance": 0.5, "drive": 0.5, "fx_send": 0.5}
        self.fx_enabled: Dict[str, bool] = {}
        self.sequence_bank: Dict[str, List[str]] = {}
        self.sequence_cursor: Dict[str, int] = {}
        self.bindings = self._default_bindings()
        self._events: List[dict] = []
        self._record_started_at: Optional[float] = None
        self._record_duration = 0.0
        self.pattern_bank: Dict[str, dict] = {}
        self.pattern_macros: Dict[str, str] = {}

    @staticmethod
    def _default_bindings():
        macro_targets = ("tuning", "amplitude", "filter", "resonance", "drive", "pan",
                         "geometric_flux", "triad_exchange", "canonical_mix", "attack", "release", "damping")
        return {
            **{key: {"kind": "macro", "target": target} for key, target in zip(MACRO_KEYS, macro_targets)},
            "LEFT": {"kind": "envelope", "target": "release", "direction": -1},
            "RIGHT": {"kind": "envelope", "target": "release", "direction": 1},
            "UP": {"kind": "envelope", "target": "attack", "direction": 1},
            "DOWN": {"kind": "envelope", "target": "attack", "direction": -1},
            "MOUSE_1": {"kind": "envelope", "target": "filter"},
            "MOUSE_2": {"kind": "envelope", "target": "damping"},
            "MOUSE_3": {"kind": "fx_toggle", "target": "jam_fx"},
        }

    def start(self):
        with self._lock:
            self.enabled = True
        return self.snapshot()

    def stop(self):
        with self._lock:
            self.enabled = False
        return self.snapshot()

    def randomize_jam_bindings(self, seed: Any = None):
        """Randomize only jam-local controls; stable for a given seed."""
        with self._lock:
            if not self.enabled:
                raise RuntimeError("Live Jam must be active to randomize jam bindings")
            use_seed = self.seed if seed is None else seed
            rng = random.Random(_seed_int(use_seed))
            targets = ["tuning", "filter", "resonance", "amplitude", "attack", "release",
                       "pan", "drive", "geometric_flux", "triad_exchange", "canonical_mix"]
            rng.shuffle(targets)
            self.bindings = self._default_bindings()
            for key, target in zip(MACRO_KEYS, targets):
                self.bindings[key] = {"kind": "macro", "target": target}
            # Keep four envelope directions and three distinct mouse functions,
            # but permit reproducible permutations of their destinations.
            env_targets = ["attack", "release", "filter", "damping"]
            rng.shuffle(env_targets)
            for key, target in zip(ARROW_KEYS, env_targets):
                self.bindings[key] = {"kind": "envelope", "target": target,
                                      "direction": -1 if key in ("LEFT", "DOWN") else 1}
            mouse_targets = ["filter", "damping", "resonance", "drive", "fx_send"]
            rng.shuffle(mouse_targets)
            for key, target in zip(MOUSE_FUNCTIONS, mouse_targets[:3]):
                self.bindings[key] = {"kind": "mouse", "target": target}
            self.randomize_bindings = True
            return self.snapshot()

    def key(self, key: str, value: Optional[float] = None, timestamp: float = 0.0):
        key = str(key).upper().replace(" ", "_")
        with self._lock:
            if not self.enabled:
                return None
            binding = self.bindings.get(key)
            if not binding:
                return None
            kind, target = binding["kind"], binding["target"]
            if kind == "macro":
                v = self.macros.get(key, 0.5) if value is None else float(value)
                self.macros[key] = max(0.0, min(1.0, v))
                event = JamEvent("macro", timestamp, {"key": key, "target": target, "value": self.macros[key]})
            elif kind == "envelope":
                step = float(value if value is not None else 0.05) * float(binding.get("direction", 1))
                old = float(self.envelope.get(target, 0.5))
                self.envelope[target] = max(0.0, min(1.0, old + step))
                event = JamEvent("envelope", timestamp, {"key": key, "target": target, "value": self.envelope[target]})
            else:
                old = float(self.envelope.get(target, 0.5))
                step = float(value if value is not None else 0.05)
                self.envelope[target] = max(0.0, min(1.0, old + step))
                event = JamEvent(kind, timestamp, {"key": key, "target": target, "value": self.envelope[target]})
            out = event.as_dict()
            if self._record_started_at is not None:
                out["timestamp"] = max(0.0, time.monotonic() - self._record_started_at)
                self._record_duration = max(self._record_duration, out["timestamp"])
            self._events.append(out)
            return out

    def nudge_macro(self, key: str, delta: float = 0.05, timestamp: float = 0.0):
        key = str(key).upper()
        with self._lock:
            if not self.enabled:
                return None
            binding = self.bindings.get(key)
            if not binding or binding.get("kind") != "macro":
                return None
            value = max(0.0, min(1.0, float(self.macros.get(key, 0.5)) + float(delta)))
            return self.key(key, value, timestamp)

    def mouse(self, function: str, amount: float = 0.05, timestamp: float = 0.0):
        return self.key(function, amount, timestamp)

    def set_fx(self, name: str, enabled: bool):
        with self._lock:
            self.fx_enabled[str(name)] = bool(enabled)
            return dict(self.fx_enabled)

    def set_sequence(self, name: str, sequence_ids: Iterable[str]):
        with self._lock:
            self.sequence_bank[str(name)] = [str(x) for x in sequence_ids]
            self.sequence_cursor[str(name)] = 0

    def trigger_sequence(self, name: str, timestamp: float = 0.0):
        with self._lock:
            if not self.enabled:
                return None
            name = str(name)
            seq = self.sequence_bank.get(name, [])
            if not seq:
                return None
            i = self.sequence_cursor.get(name, 0) % len(seq)
            item = seq[i]
            self.sequence_cursor[name] = (i + 1) % len(seq)
            event = JamEvent("sequence", timestamp, {"sequence": name, "item": item, "index": i})
            out = event.as_dict()
            self._events.append(out)
            return out

    def snapshot(self):
        with self._lock:
            return {"seed": self.seed, "seeded_mode": self.seeded_mode,
                    "enabled": self.enabled, "randomize_bindings": self.randomize_bindings,
                    "bindings": {k: dict(v) for k, v in self.bindings.items()},
                    "macros": dict(self.macros), "envelope": dict(self.envelope),
                    "fx_enabled": dict(self.fx_enabled),
                    "sequence_bank": {k: list(v) for k, v in self.sequence_bank.items()},
                    "sequence_cursor": dict(self.sequence_cursor),
                    "pattern_bank": {k: {"duration": float(v.get("duration", 0.0)), "events": [dict(e) for e in v.get("events", [])]} for k, v in self.pattern_bank.items()},
                    "record_duration": float(self._record_duration),
                    "pattern_macros": dict(self.pattern_macros)}

    def begin_performance_recording(self):
        """Start a timestamped performance take; notes and pitch bends share one clock."""
        with self._lock:
            self._events.clear()
            self._record_started_at = time.monotonic()
            self._record_duration = 0.0
            return self._record_started_at

    def record_performance_event(self, kind: str, **payload):
        """Append a note/bend or other live-performance event to the jam take."""
        with self._lock:
            if self._record_started_at is None:
                return None
            now = time.monotonic()
            elapsed = max(0.0, now - self._record_started_at)
            self._record_duration = max(self._record_duration, elapsed)
            event = JamEvent(str(kind), elapsed, dict(payload)).as_dict()
            self._events.append(event)
            return dict(event)

    def finish_performance_recording(self):
        with self._lock:
            if self._record_started_at is not None:
                self._record_duration = max(self._record_duration, time.monotonic() - self._record_started_at)
            self._record_started_at = None
            return {"duration": float(self._record_duration), "events": self.event_log()}

    def save_pattern(self, name: str, events=None):
        """Save a take as a pattern; its envelope is exactly the take duration."""
        with self._lock:
            take = self.finish_performance_recording() if events is None else events
            clean = [dict(e) for e in (take.get("events", []) or []) if isinstance(e, dict)]
            duration = max(0.0, float(take.get("duration", 0.0)))
            self.pattern_bank[str(name)] = {"duration": duration, "events": clean}
            return {"name": str(name), "duration": duration, "entries": len(clean)}

    def assign_pattern_macro(self, key: str, pattern_name: str):
        key = str(key).upper()
        if key not in MACRO_KEYS:
            raise ValueError("Pattern macro must be F1–F12")
        with self._lock:
            if pattern_name not in self.pattern_bank:
                raise KeyError(f"Unknown Jam pattern: {pattern_name}")
            self.pattern_macros[key] = str(pattern_name)
            return dict(self.pattern_macros)

    def pattern_for_macro(self, key: str):
        with self._lock:
            return self.pattern_macros.get(str(key).upper())

    def event_log(self):
        with self._lock:
            return [dict(e) for e in self._events]

    def replay_state(self):
        """Serializable deterministic state sufficient to resume jam mapping."""
        return self.snapshot()

    def load_snapshot(self, state):
        """Restore a saved jam state, always stopped until explicitly started."""
        if not isinstance(state, dict):
            return self.snapshot()
        with self._lock:
            self.seed = state.get("seed", 0)
            self.seeded_mode = bool(state.get("seeded_mode", True))
            self.enabled = False
            bindings = state.get("bindings")
            if isinstance(bindings, dict):
                allowed = set(MACRO_KEYS + ARROW_KEYS + MOUSE_FUNCTIONS)
                clean = {}
                for key, value in bindings.items():
                    if key in allowed and isinstance(value, dict) and value.get("kind") in ("macro", "envelope", "mouse", "fx_toggle"):
                        clean[key] = {k: v for k, v in value.items() if k in ("kind", "target", "direction")}
                if clean:
                    self.bindings = clean
            for key, value in (state.get("macros", {}) or {}).items():
                if key in MACRO_KEYS:
                    try: self.macros[key] = max(0.0, min(1.0, float(value)))
                    except Exception: pass
            for key, value in (state.get("envelope", {}) or {}).items():
                if key in self.envelope:
                    try: self.envelope[key] = max(0.0, min(1.0, float(value)))
                    except Exception: pass
            self.fx_enabled = {str(k): bool(v) for k, v in (state.get("fx_enabled", {}) or {}).items()}
            self.sequence_bank = {str(k): [str(x) for x in v] for k, v in (state.get("sequence_bank", {}) or {}).items() if isinstance(v, (list, tuple))}
            self.sequence_cursor = {str(k): max(0, int(v)) for k, v in (state.get("sequence_cursor", {}) or {}).items()}
            self.pattern_bank = {str(k): {"duration": max(0.0, float(v.get("duration", 0.0))), "events": [dict(e) for e in v.get("events", []) if isinstance(e, dict)]} for k, v in (state.get("pattern_bank", {}) or {}).items() if isinstance(v, dict)}
            self._record_duration = max(0.0, float(state.get("record_duration", 0.0) or 0.0))
            self.pattern_macros = {str(k): str(v) for k, v in (state.get("pattern_macros", {}) or {}).items() if str(k) in MACRO_KEYS and str(v) in self.pattern_bank}
            self.randomize_bindings = bool(state.get("randomize_bindings", False))
        return self.snapshot()


class LiveJamAudioRecorder:
    """Bounded, disk-streamed WAV recorder fed by the final master audio callback.

    The PortAudio callback only copies one bounded block into a queue; a writer
    thread performs all file I/O so recording cannot stall the audio device.
    """
    def __init__(self, path, sample_rate=44100, channels=1, queue_blocks=256):
        import queue, threading, wave
        self.path = str(path)
        self.sample_rate = int(sample_rate or 44100)
        self.channels = int(channels or 1)
        self._queue = queue.Queue(maxsize=max(8, int(queue_blocks)))
        self._stop = threading.Event()
        self._error = None
        self.dropped_blocks = 0
        self.frames_written = 0
        self._wave_module = wave
        self._thread = threading.Thread(target=self._writer, name="live-jam-wav-writer", daemon=True)
        self._thread.start()

    def push(self, samples):
        try:
            import numpy as np
            a = np.asarray(samples, dtype=np.float32).reshape(-1)
            if a.size == 0 or self._stop.is_set():
                return
            # Realtime callback only copies a bounded float block. PCM packing and
            # disk writes happen on the dedicated writer thread.
            self._queue.put_nowait(a.copy())
        except Exception:
            self.dropped_blocks += 1

    def _writer(self):
        try:
            with self._wave_module.open(self.path, 'wb') as wf:
                wf.setnchannels(self.channels); wf.setsampwidth(2); wf.setframerate(self.sample_rate)
                while not self._stop.is_set() or not self._queue.empty():
                    try: block = self._queue.get(timeout=0.1)
                    except Exception: continue
                    import numpy as np
                    pcm=(np.clip(np.asarray(block,dtype=np.float32),-1.0,1.0)*32767.0).astype('<i2',copy=False).tobytes()
                    wf.writeframesraw(pcm)
                    self.frames_written += len(pcm) // (2 * self.channels)
        except Exception as exc:
            self._error = str(exc)

    def finish(self, timeout=8.0):
        self._stop.set()
        self._thread.join(max(0.1, float(timeout)))
        return {"path": self.path, "frames": int(self.frames_written),
                "duration": self.frames_written / max(1, self.sample_rate),
                "dropped_blocks": int(self.dropped_blocks), "error": self._error,
                "complete": not self._thread.is_alive()}
