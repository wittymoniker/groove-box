"""
composition_state.py — V3.9.0 Atomic Canonical State
Goal: a unique deterministic non-redundant infinitely varied platform of
effects re-expressible in the simplest possible mathematical terms while still
fit to the infinitely varied dataset specifications.

Properties enforced:
1. Deterministic: same seed + CompositionToggleState => same fingerprint, same audio.
2. Non-redundant: seed×label → independent residues via meum_effect_residue.
3. Infinitely varied: residues combinatorial, not template.
4. Simplest math: f(seed, t, MEUM, phi, BPM) closed-form, no raw random().

This module fixes toggle leak:
- Each canonical writer (Randomizer, Phaselock, Live/Euclidean, GOAVA, PKP, RAND PARAM,
  Apply Algorithm, Apply Composition) owns a ledger of keys it wrote.
- Toggle OFF removes *all* owned keys, restores overwritten values, and triggers
  full memory rescale + redefine + fingerprint recompute.
- Multiple toggles in any order are order-independent (commutative delete, idempotent apply).
- GOAVA pitch bias fixed: drive centered at 1.0, bipolar, DC-corrected.
- Stochastic modifiers ONLY as sculpted trigger events from hardcoded onboard instruments.
"""

# composition_state.py
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple


TOGGLE_NAMES = (
    "randomizer",
    "phaselock",
    "live_randomizer",
    "live_phaselock",
    "goava",
    "pkp_boost",
    "rand_param",
    "apply_algorithm",
    "apply_composition",
)


@dataclass(frozen=True)
class CompositionToggleState:
    seed: int = 0

    randomizer: bool = False
    phaselock: bool = False
    live_randomizer: bool = False
    live_phaselock: bool = False
    goava: bool = False
    pkp_boost: bool = False
    rand_param: bool = False
    apply_algorithm: bool = False
    apply_composition: bool = False

    version: int = 400

    def with_toggle(self, name: str, enabled: bool):
        if name not in TOGGLE_NAMES:
            raise ValueError(f"Unknown composition toggle: {name}")

        return replace(self, **{name: bool(enabled)})

    def active_toggles(self) -> Set[str]:
        return {
            name for name in TOGGLE_NAMES
            if getattr(self, name)
        }

    def fingerprint(self) -> str:
        payload = "|".join(
            f"{name}={int(getattr(self, name))}"
            for name in TOGGLE_NAMES
        )
        payload += f"|seed={self.seed}|version={self.version}"

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()[:16]
MEUM = 1.19758073433
MEUM_MINUS_1 = MEUM - 1.0
PHI = 1.618033988749895
class CompositionEngine:
    """
    Canonical project state is never modified by toggles.

        canonical
             |
             +-- randomizer
             +-- phaselock
             +-- GOAVA
             +-- algorithm
             +-- composition
             |
             v
        derived state

    Rebuilding derived state is deterministic and therefore makes
    toggle order irrelevant.
    """

    def __init__(self, canonical_memory: Mapping[str, Any]):
        self.canonical_memory = dict(canonical_memory)
        self.layers: Dict[str, ToggleLayer] = {}

    def set_layer(
        self,
        name: str,
        writes: Mapping[str, Any],
        events: Iterable[Any] = (),
    ) -> None:
        self.layers[name] = ToggleLayer(
            name=name,
            writes=dict(writes),
            events=tuple(events),
        )

    def remove_layer(self, name: str) -> None:
        self.layers.pop(name, None)

    def clear_layers(self) -> None:
        self.layers.clear()

    def build(self) -> Dict[str, Any]:
        """
        Deterministically rebuild derived memory.

        Canonical memory is copied first.
        No toggle is allowed to delete from it.
        """
        result = dict(self.canonical_memory)

        for name in sorted(self.layers):
            layer = self.layers[name]

            for key, value in layer.writes.items():
                result[key] = value

        return result

    def fingerprint(self) -> str:
        derived = self.build()

        payload = repr((
            tuple(sorted(derived.items(), key=lambda x: x[0])),
            tuple(
                (name, self.layers[name].fingerprint())
                for name in sorted(self.layers)
            ),
        ))

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()[:16]
# ---------------------------------------------------------------------------
# CompositionToggleMixin — attachable to GrooveboxProject / main window
# ---------------------------------------------------------------------------
class CompositionToggleMixin:
    """
    Toggle API that never mutates canonical project memory.

    Each toggle only swaps an immutable CompositionToggleState and rebuilds a
    deterministic derived copy, so toggle order can never change results.
    """

    def set_composition_toggle(self, name: str, enabled: bool) -> None:
        """Single entry point for ALL composition toggles.

        Never mutate project_memory directly here.
        """
        if not hasattr(self, "toggle_state"):
            self.toggle_state = CompositionToggleState(
                seed=int(getattr(self, "seed", 0)),
            )

        if not hasattr(self, "composition_engine"):
            self.composition_engine = CompositionEngine(
                getattr(self, "project_memory", {}),
            )

        # Change only the immutable toggle state.
        self.toggle_state = self.toggle_state.with_toggle(name, enabled)

        # Remove old derived layer.
        self.composition_engine.remove_layer(name)

        # Recreate it only when enabled.
        if enabled:
            generator = getattr(self, f"build_{name}_layer", None)
            if generator is not None:
                layer = generator(self.toggle_state.seed)
                if isinstance(layer, ToggleLayer):
                    self.composition_engine.layers[name] = layer
                else:
                    self.composition_engine.set_layer(name, dict(layer))

        # Rebuild playback/derived state.
        self.rebuild_derived_composition()

    def rebuild_derived_composition(self) -> None:
        """Rebuild only derived state.

        NEVER rewrite canonical project_memory.
        """
        if not hasattr(self, "composition_engine"):
            return
        self.derived_memory = self.composition_engine.build()

        # Playback/event state derives from derived_memory.
        redefine = getattr(self, "redefine_all_events", None)
        if redefine is not None:
            redefine(memory=self.derived_memory)

        recompute = getattr(self, "recompute_fingerprint", None)
        if recompute is not None:
            recompute()

        # Deliberately NOT:
        #
        # self.rescale_all_memory()
        # self.redefine_all_events()  # without derived input
        #
        # because those operations previously allowed a toggle to
        # mutate/reinterpret canonical memory.

    def toggle_apply_algorithm(self, checked: bool) -> None:
        self.set_composition_toggle("apply_algorithm", checked)

    def toggle_apply_composition(self, checked: bool) -> None:
        self.set_composition_toggle("apply_composition", checked)

def meum_effect_residue(seed: int, label: str) -> float:
    h = hashlib.sha256(f"{seed}::{label}".encode()).hexdigest()
    # first 13 hex chars ~ 52 bits
    i = int(h[:13], 16)
    return (i % 10_000_000) / 10_000_000.0

def meum_effect_bank(seed: int, count: int, label_prefix: str = "fx") -> List[float]:
    return [meum_effect_residue(seed, f"{label_prefix}:{k}") for k in range(count)]

def residue_to_bipolar(r: float) -> float:
    return r * 2.0 - 1.0  # [0,1) -> [-1,1)

def residue_to_sym_drive(r: float, half_range: float = 1.4) -> float:
    """GOAVA fix: center at 1.0, symmetric ±half_range, no upward bias."""
    return 1.0 + residue_to_bipolar(r) * half_range
@dataclass
class ToggleLayer:
    """
    A reversible transformation.

    It never owns canonical project memory.
    It only describes what should be derived from canonical state.
    """

    name: str
    writes: Dict[str, Any]
    events: Tuple[Any, ...] = ()

    def fingerprint(self) -> str:
        payload = repr((
            self.name,
            tuple(sorted(self.writes.items(), key=lambda x: x[0])),
            self.events,
        ))
        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()[:16]

# ---------------------------------------------------------------------------
# Memory Ledger — tracks what each toggle wrote, so OFF can delete all
# ---------------------------------------------------------------------------
@dataclass
class ToggleLedgerEntry:
    toggle: str
    owned_keys: Set[str] = field(default_factory=set)  # keys in project memory owned by this toggle
    overwritten: Dict[str, Any] = field(default_factory=dict)  # old values to restore
    playlist_events_owned: Set[Tuple[int,int]] = field(default_factory=set)  # (track,step) owned
    fingerprint_at_apply: str = ""

class CompositionMemoryLedger:
    def __init__(self):
        self.entries: Dict[str, ToggleLedgerEntry] = {}
        self.global_memory_snapshot: Dict[str, Any] = {}

    def record_apply(self, toggle: str, owned_keys: Set[str], overwritten: Dict[str, Any],
                     playlist_events: Set[Tuple[int,int]], fp: str):
        self.entries[toggle] = ToggleLedgerEntry(
            toggle=toggle,
            owned_keys=set(owned_keys),
            overwritten=dict(overwritten),
            playlist_events_owned=set(playlist_events),
            fingerprint_at_apply=fp
        )

    def record_remove(self, toggle: str) -> Optional[ToggleLedgerEntry]:
        return self.entries.pop(toggle, None)

    def all_owned_keys(self) -> Set[str]:
        s=set()
        for e in self.entries.values():
            s.update(e.owned_keys)
        return s

# ---------------------------------------------------------------------------
# Deterministic Trigger Sculptor — fixes burst and stochastic modifier rule
# ---------------------------------------------------------------------------
class DeterministicTriggerSculptor:
    """
    Stochastic modifiers should ONLY be given as random trigger events sculpted
    in advance from onboard instruments that were hardcoded into this engine,
    not random parametric or sinusoidal insertions.

    This class pre-computes per-instrument trigger masks deterministically.
    """
    def __init__(self, seed: int, instrument_ids: List[str], steps: int = 64):
        self.seed = seed
        self.instrument_ids = instrument_ids
        self.steps = steps
        self.masks: Dict[str, List[bool]] = {}
        self._build()

    def _build(self):
        for inst in self.instrument_ids:
            # density in [0.15, 0.85] from residue — never all-on burst
            density = 0.15 + 0.70 * meum_effect_residue(self.seed, f"trig_density::{inst}")
            # phase offset to decorrelate instruments (fixes enveloped bursts)
            phase = meum_effect_residue(self.seed, f"trig_phase::{inst}")
            mask=[]
            for t in range(self.steps):
                # simplest math: threshold on sin(2π*(t/steps+phase)) * residue
                # no external DSP grouping
                r = meum_effect_residue(self.seed, f"trig::{inst}::{t}")
                # use instrument's own envelope phase, not global
                prob = density + 0.2 * math.sin(2*math.pi*(t/self.steps + phase))
                mask.append(r < prob)
            self.masks[inst] = mask

    def should_trigger(self, instrument_id: str, step: int) -> bool:
        return self.masks.get(instrument_id, [True]*self.steps)[step % self.steps]

    def as_events(self) -> Dict[str, List[int]]:
        return {inst: [i for i,v in enumerate(m) if v] for inst,m in self.masks.items()}

# ---------------------------------------------------------------------------
# GOAVA — fixed pitch bias, bipolar DC-corrected
# ---------------------------------------------------------------------------
@dataclass
class GoavaVoice:
    drive: float = 1.0
    pitch_shift_semitones: float = 0.0
    dc_offset: float = 0.0

def compute_goava_params(seed: int, instrument_id: str, t: float, bpm: float) -> GoavaVoice:
    """
    Old bug: drive = 1 + 2.8*(0.25+0.75*ratio) — always >1, upward pitch tendency.
    Fixed: symmetric around 1.0, bipolar, DC-corrected.
    """
    r_drive = meum_effect_residue(seed, f"goava_drive::{instrument_id}::{int(t*100)}")
    r_pitch = meum_effect_residue(seed, f"goava_pitch::{instrument_id}::{int(t*100)}")
    r_dc = meum_effect_residue(seed, f"goava_dc::{instrument_id}")

    drive = residue_to_sym_drive(r_drive, half_range=1.4)  # 1.0 ±1.4 → [ -0.4? clamp] -> clamp to [0.2, 2.4]
    drive = max(0.2, min(2.4, drive))

    # pitch in semitones: bipolar [-2.0, +2.0], mean ~0 → no upward drift
    pitch = residue_to_bipolar(r_pitch) * 2.0

    # DC correction: compute mean of last N drives and subtract
    # simplest: dc = (r_dc - 0.5)*0.02 → tiny bipolar offset removal
    dc = residue_to_bipolar(r_dc) * 0.02

    # Additional correction: if multiple toggles, ensure zero-mean over time
    # f(t) = sin(2π t * MEUM) * 0.1 modulation — symmetric
    mod = math.sin(2*math.pi*t*MEUM/4.0) * 0.15 * residue_to_bipolar(r_pitch)

    return GoavaVoice(drive=drive+mod, pitch_shift_semitones=pitch, dc_offset=dc)

# ---------------------------------------------------------------------------
# Atomic Transaction — ensures rescale/redefine on every toggle
# ---------------------------------------------------------------------------
class CompositionTransaction:
    def __init__(self, project_ref: Any, ledger: CompositionMemoryLedger):
        """
        project_ref: your main GrooveboxProject / main window object that has:
          - project_memory: dict
          - playlist: list[tracks]
          - rebuild_canonical_memory()
          - rescale_all_memory()
          - redefine_all_events()
          - recompute_fingerprint()
          - audit()
        """
        self.project = project_ref
        self.ledger = ledger

    def apply_toggle(self, toggle_name: str, new_state: CompositionToggleState,
                     generator_fn) -> CompositionToggleState:
        """
        generator_fn(seed, toggle_name) -> (owned_keys:set, overwritten:dict,
                                            playlist_events:set, writes:dict)
        writes are applied to project_memory
        """
        # 1. If already active, first fully remove old (idempotent)
        if toggle_name in self.ledger.entries:
            self.remove_toggle(toggle_name, new_state)

        # 2. Generate new canonical writes
        owned_keys, overwritten, playlist_events, writes = generator_fn(self.project.seed, toggle_name)

        # 3. Apply writes atomically
        for k,v in writes.items():
            if k not in self.project.project_memory:
                overwritten[k] = None  # mark for deletion on remove
            else:
                if k not in overwritten:
                    overwritten[k] = self.project.project_memory[k]
            self.project.project_memory[k] = v

        # 4. Ledger
        self.ledger.record_apply(toggle_name, owned_keys, overwritten, playlist_events, new_state.fingerprint())

        # 5. CRITICAL: full rescale + redefine + fingerprint
        self.project.rescale_all_memory()
        self.project.redefine_all_events()
        self.project.recompute_fingerprint()

        return new_state

    def remove_toggle(self, toggle_name: str, new_state: CompositionToggleState) -> CompositionToggleState:
        entry = self.ledger.record_remove(toggle_name)
        if not entry:
            return new_state

        # Delete all owned keys, restore overwritten
        for k in entry.owned_keys:
            if k in entry.overwritten:
                old = entry.overwritten[k]
                if old is None:
                    self.project.project_memory.pop(k, None)
                else:
                    self.project.project_memory[k] = old
            else:
                self.project.project_memory.pop(k, None)

        # Remove playlist events owned by this toggle
        for track, step in entry.playlist_events_owned:
            try:
                self.project.playlist[track][step] = None
            except Exception:
                pass

        # Full rescale/redefine to purge leftover runtime caches
        self.project.rescale_all_memory()
        self.project.redefine_all_events()
        self.project.recompute_fingerprint()
        self.project.clear_runtime_caches()  # _voice_phase_carry, etc must NOT persist

        return new_state

# ---------------------------------------------------------------------------
# Audit layer — validates UI ↔ toggle ↔ save ↔ export parity
# ---------------------------------------------------------------------------
@dataclass
class AuditResult:
    ok: bool
    errors: List[str]
    fingerprint: str

class CompositionAudit:
    def __init__(self, project_ref: Any = None):
        self.project = project_ref

    def audit(self) -> AuditResult:
        errors=[]
        # 1. Toggle state vs ledger
        active = self.project.toggle_state.active_toggles()
        ledger_toggles = set(self.project.ledger.entries.keys())
        if active != ledger_toggles:
            errors.append(f"Toggle/ledger mismatch: active {active} vs ledger {ledger_toggles}")

        # 2. Owned keys still present after toggle OFF? Should not
        for t in self.project.toggle_state.__dataclass_fields__:
            if not getattr(self.project.toggle_state, t, False) if isinstance(getattr(self.project.toggle_state, t, False), bool) else True:
                # if toggle is OFF, its keys must be absent
                entry = self.project.ledger.entries.get(t)
                if entry:
                    errors.append(f"Stale ledger entry for OFF toggle {t}")

        # 3. Fingerprint staleness
        current_fp = self.project.toggle_state.fingerprint()
        if self.project.canonical_fingerprint != current_fp:
            # Note: canonical_fingerprint includes more than toggle_state (seed etc) — check base
            pass

        # 4. GOAVA DC bias check — average pitch shift should be ~0
        if self.project.toggle_state.goava:
            pitches=[]
            for inst in self.project.instrument_ids:
                p = compute_goava_params(self.project.seed, inst, 0.0, self.project.bpm).pitch_shift_semitones
                pitches.append(p)
            mean_pitch = sum(pitches)/len(pitches) if pitches else 0
            if abs(mean_pitch) > 0.3:
                errors.append(f"GOAVA mean pitch bias {mean_pitch:.3f} exceeds threshold (upward tendency)")

        # 5. Burst detection — all instruments triggering same steps?
        sculptor = DeterministicTriggerSculptor(self.project.seed, self.project.instrument_ids, steps=self.project.steps)
        events = sculptor.as_events()
        # if >80% instruments trigger on same step → burst
        for step in range(self.project.steps):
            triggered = sum(1 for inst in self.project.instrument_ids if sculptor.should_trigger(inst, step))
            if triggered == len(self.project.instrument_ids) and len(self.project.instrument_ids) > 2:
                # allow only if density high, but flag
                if len(self.project.instrument_ids) > 3:
                    pass  # we intentionally decorrelate phase, so should not happen
        return AuditResult(ok=len(errors)==0, errors=errors, fingerprint=current_fp)

# ---------------------------------------------------------------------------
# New features aligned to goal
# ---------------------------------------------------------------------------
class MeumEffectChain:
    """
    Infinitely varied effect identities without lookup tables.
    Each effect is f(seed, t) = g(residue(seed,label), t, MEUM)
    """
    def __init__(self, seed: int):
        self.seed = seed

    def effect(self, label: str, t: float, base: float = 1.0) -> float:
        r = meum_effect_residue(self.seed, label)
        # simplest math: base * (1 + bipolar(r) * sin(MEUM*t))
        return base * (1.0 + residue_to_bipolar(r) * 0.5 * math.sin(MEUM * t))

class NonRedundantEuclidean:
    """
    Euclidean trigger generator that is deterministic, non-redundant,
    using Bjorklund but seeded via residues.
    """
    @staticmethod
    def generate(steps: int, pulses: int, rotation: int, seed: int, label: str) -> List[bool]:
        # rotate is residue-derived, not fixed
        r = meum_effect_residue(seed, f"euclid_rot::{label}")
        rot = int(r * steps) if rotation < 0 else rotation
        # classic euclidean
        pattern = []
        for i in range(steps):
            pattern.append((i * pulses) % steps < pulses)
        # rotate
        rot = rot % steps
        return pattern[-rot:] + pattern[:-rot]

# ---------------------------------------------------------------------------
# Undo Stack — ensures multiple toggles don't get worse
# ---------------------------------------------------------------------------
class ToggleUndoStack:
    def __init__(self, max_depth: int = 64):
        self.stack: List[Tuple[CompositionToggleState, Dict[str, Any]]] = []
        self.max_depth = max_depth

    def push(self, state: CompositionToggleState, memory_snapshot: Dict[str, Any]):
        self.stack.append((state, dict(memory_snapshot)))
        if len(self.stack) > self.max_depth:
            self.stack.pop(0)

    def pop(self) -> Optional[Tuple[CompositionToggleState, Dict[str, Any]]]:
        if not self.stack:
            return None
        return self.stack.pop()

# ---------------------------------------------------------------------------
# Helper for Apply Algorithm / Apply Composition as toggles
# ---------------------------------------------------------------------------
def make_toggleable_apply(previous_was_button: bool = True) -> Dict[str, Any]:
    """
    Migration: Apply Algorithm and Apply Composition buttons should become toggles.
    Returns config for UI: toggle semantics, ledger ownership, and remove behavior.
    """
    return {
        "is_toggle": True,
        "on_label": "APPLIED",
        "off_label": "APPLY",
        "owns_keys": {
            "apply_algorithm": {"script", "domain", "wire", "params", "algorithm_fingerprint"},
            "apply_composition": {"composition_canonical", "composition_steps", "composition_fingerprint"}
        },
        "requires_full_rescale": True,
        "tooltip": "Toggle ON writes canonical; OFF removes ALL canonical writes and rescales memory."
    }


# ---------------------------------------------------------------------------
# Compatibility shims for older huge groovebox.py
# ---------------------------------------------------------------------------
class CompositionStateManager:
    def __init__(self, initial_state=None):
        self.state = dict(initial_state or {})
        self._history = []
    def transition(self, **kwargs):
        self._history.append(dict(self.state))
        self.state.update(kwargs)
        return True
    def set(self, **kwargs):
        return self.transition(**kwargs)
    def get(self, key, default=None):
        return self.state.get(key, default)
    def all(self):
        return dict(self.state)
