"""Atomic composition state management, toggle consistency, and audit layer.

Ensures that every toggle state transition is deterministic, reproducible,
and produces consistent save/load/export fingerprints across all modules.

Credits: GitHub Copilot (toggle state design, audit patterns)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass(frozen=True)
class CompositionToggleState:
    """Atomic, hashable composition toggle configuration.
    
    frozen=True ensures this dataclass is hashable and immutable,
    so it can be used as a dictionary key or in sets.
    """
    live_dj_goava: bool = False
    live_dj_random: bool = False
    goava_active: bool = False
    apply_algorithm: bool = False
    apply_composition: bool = False
    randomizer_enabled: bool = False
    phaselock_enabled: bool = False
    seed: float = 0.0
    bpm: float = 120.0
    base_hz: float = 432.0
    
    def fingerprint(self) -> str:
        """Canonical hash of toggle state + parameters.
        
        Same state always produces the same fingerprint (deterministic).
        Different states spread across hash space (non-redundant).
        """
        blob = json.dumps(asdict(self), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @staticmethod
    def from_dict(d: dict) -> CompositionToggleState:
        """Reconstruct from dictionary (used in load)."""
        return CompositionToggleState(**d)


class CompositionStateManager:
    """Manages toggle state transitions, undo history, and consistency audits.
    
    Every toggle must:
      1. Invalidate all runtime-only caches
      2. Recompute the canonical fingerprint
      3. Update all dependent UI and audio state atomically
    """
    
    def __init__(self, max_undo_depth: int = 64):
        self.state = CompositionToggleState()
        self.undo_stack: List[CompositionToggleState] = []
        self.max_undo_depth = max(1, int(max_undo_depth))
    
    def transition(self, **updates) -> bool:
        """Atomically transition to a new toggle state.
        
        Returns True if state changed, False if new state == current state.
        """
        new_state = CompositionToggleState(**{**asdict(self.state), **updates})
        
        if new_state.fingerprint() == self.state.fingerprint():
            return False  # No change; skip update
        
        # Push current state to undo stack before transition
        self.undo_stack.append(self.state)
        if len(self.undo_stack) > self.max_undo_depth:
            self.undo_stack.pop(0)  # FIFO discard oldest
        
        self.state = new_state
        return True
    
    def undo(self) -> bool:
        """Revert to previous toggle state.
        
        Returns True if undo was performed, False if stack is empty.
        """
        if not self.undo_stack:
            return False
        self.state = self.undo_stack.pop()
        return True
    
    def to_dict(self) -> dict:
        """Serialize state for save/export."""
        return {
            "toggle_state": self.state.to_dict(),
            "fingerprint": self.state.fingerprint(),
        }
    
    @staticmethod
    def from_dict(d: dict) -> CompositionStateManager:
        """Reconstruct from serialized dict (used in load)."""
        mgr = CompositionStateManager()
        if "toggle_state" in d:
            mgr.state = CompositionToggleState.from_dict(d["toggle_state"])
        return mgr


class CompositionAudit:
    """Verifies consistency across all modules (save/load/export agreement)."""
    
    def __init__(self):
        self.last_fingerprint: Optional[str] = None
        self.last_audit_issues: List[str] = []
    
    def audit(self, toggle_state: CompositionToggleState, ui_state: dict, export_state: dict) -> List[str]:
        """Perform full consistency check.
        
        Args:
            toggle_state: Current CompositionToggleState
            ui_state: Dict of UI widget states (e.g., {"btn_live_dj_goava": True, ...})
            export_state: Last exported game/audio state
        
        Returns:
            List of consistency issues (empty = all good)
        """
        issues: List[str] = []
        fp = toggle_state.fingerprint()
        
        # Check 1: Fingerprint consistency
        if self.last_fingerprint and self.last_fingerprint != fp:
            issues.append(f"Fingerprint changed from {self.last_fingerprint} to {fp}")
        self.last_fingerprint = fp
        
        # Check 2: UI toggle sync
        expected_ui = {
            "live_dj_goava": toggle_state.live_dj_goava,
            "live_dj_random": toggle_state.live_dj_random,
            "goava_active": toggle_state.goava_active,
            "apply_algorithm": toggle_state.apply_algorithm,
            "apply_composition": toggle_state.apply_composition,
            "randomizer_enabled": toggle_state.randomizer_enabled,
            "phaselock_enabled": toggle_state.phaselock_enabled,
        }
        for key, expected in expected_ui.items():
            actual = ui_state.get(key)
            if actual is not None and actual != expected:
                issues.append(f"UI sync mismatch: {key} (expected {expected}, got {actual})")
        
        # Check 3: Export fingerprint freshness
        if export_state and "composition_fingerprint" in export_state:
            if export_state["composition_fingerprint"] != fp:
                issues.append(
                    f"Export fingerprint stale: {export_state['composition_fingerprint']} != {fp}"
                )
        
        # Check 4: Parameter bounds
        if not (0.0 <= toggle_state.bpm <= 600.0):
            issues.append(f"BPM out of bounds: {toggle_state.bpm}")
        if not (1.0 <= toggle_state.base_hz <= 10000.0):
            issues.append(f"Base Hz out of bounds: {toggle_state.base_hz}")
        if not (-1e6 <= toggle_state.seed <= 1e6):
            issues.append(f"Seed out of bounds: {toggle_state.seed}")
        
        self.last_audit_issues = issues
        return issues
    
    def is_healthy(self) -> bool:
        """Quick check: True if last audit found no issues."""
        return len(self.last_audit_issues) == 0
    
    def summary(self) -> str:
        """Human-readable audit summary."""
        if self.is_healthy():
            return "[OK] Composition state is consistent."
        return "[WARN] Issues found:\n" + "\n".join(
            f"  • {issue}" for issue in self.last_audit_issues
        )
