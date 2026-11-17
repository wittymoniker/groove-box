"""Directional ownership and overwrite/blend rules for canonical project data.

The *incoming writer* controls whether it may blend with the current owner.
Defaults intentionally favour canonical generation while keeping user and seed
writes as explicit overwrites:

* canonical: blend ON, 100% strength
* user:      blend OFF, 100% strength
* seed:      blend OFF, 100% strength

A blend is a strength-weighted mean.  A non-blending writer replaces the old
owner; a strength below 100% scales the replacement against the neutral value
(0 for numeric controls).  Gate resolution is separate and uses weighted votes
so simultaneous active/inactive writers can produce a fractional probability.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping

SOURCES = ("canonical", "seed", "user")
DEFAULT_POLICY = {
    "canonical": {"blend": True, "strength": 1.0},
    "seed": {"blend": False, "strength": 1.0},
    "user": {"blend": False, "strength": 1.0},
}


def default_policy() -> dict:
    return deepcopy(DEFAULT_POLICY)


def normalize_policy(value: Any = None) -> dict:
    out = default_policy()
    if not isinstance(value, Mapping):
        return out
    for source in SOURCES:
        raw = value.get(source)
        if not isinstance(raw, Mapping):
            continue
        out[source]["blend"] = bool(raw.get("blend", out[source]["blend"]))
        try:
            strength = float(raw.get("strength", out[source]["strength"]))
            if not math.isfinite(strength):
                strength = out[source]["strength"]
        except (TypeError, ValueError, OverflowError):
            strength = out[source]["strength"]
        out[source]["strength"] = min(1.0, max(0.0, strength))
    return out


def blend_value(previous: Any, incoming: Any, previous_owner: str,
                incoming_owner: str, policy: Any = None, *, neutral: float = 0.0):
    """Resolve a numeric value using the incoming owner's blend permission.

    With blend enabled, both owners contribute in proportion to configured
    strength.  With blend disabled, the incoming source replaces prior
    provenance; partial strength is measured against ``neutral``.
    With blending disabled, strength is a bounded overwrite (0% retains the
    prior value, 100% fully replaces it); with blending enabled, source
    strengths form a weighted mean. Non-finite values safely fall back.
    """
    cfg = normalize_policy(policy)
    src = incoming_owner if incoming_owner in SOURCES else "canonical"
    prev_src = previous_owner if previous_owner in SOURCES else "user"
    inc_strength = cfg[src]["strength"]
    try:
        new = float(incoming)
        if not math.isfinite(new):
            return incoming
        old = float(previous)
        if not math.isfinite(old):
            old = float(neutral)
    except (TypeError, ValueError, OverflowError):
        return incoming
    if previous is None:
        return float(neutral) + inc_strength * (new - float(neutral))
    old_strength = cfg[prev_src]["strength"]
    if not cfg[src]["blend"]:
        # Blend permission OFF means provenance is replaced, not combined as
        # two peers. A sub-100% write is still bounded: retain the unwritten
        # fraction of the previous value, without claiming it as a second owner.
        return old * (1.0 - inc_strength) + new * inc_strength
    total = old_strength + inc_strength
    if total <= 1e-12:
        return old
    share = inc_strength / total
    return old * (1.0 - share) + new * share



def apply_write(previous: Any, incoming: Any, previous_owner: str,
                incoming_owner: str, policy: Any = None, *, neutral: float = 0.0):
    """Apply one source write to a previously resolved value.

    Containers are resolved recursively; numeric leaves use weighted source
    strengths, while enums/strings use deterministic winner selection. The
    caller retains the original source dictionaries and stores only this
    derived result.
    """
    if isinstance(incoming, Mapping):
        old = previous if isinstance(previous, Mapping) else {}
        out = dict(old)
        for key, value in incoming.items():
            if key in old:
                out[key] = apply_write(old[key], value, previous_owner, incoming_owner,
                                       policy, neutral=neutral)
            else:
                out[key] = deepcopy(value)
        return out
    if isinstance(incoming, (list, tuple)):
        old = list(previous) if isinstance(previous, (list, tuple)) else []
        result = []
        for index, value in enumerate(incoming):
            if index < len(old):
                result.append(apply_write(old[index], value, previous_owner, incoming_owner,
                                          policy, neutral=neutral))
            else:
                result.append(deepcopy(value))
        return result if isinstance(incoming, list) else tuple(result)
    if isinstance(incoming, (int, float)) and not isinstance(incoming, bool):
        # Integer fields are categorical/discrete (e.g. cellular rules), not
        # continuous sliders. Do not create invalid fractional enum values.
        if isinstance(incoming, int) and isinstance(previous, int) and not isinstance(previous, bool):
            cfg = normalize_policy(policy)
            src = incoming_owner if incoming_owner in SOURCES else "canonical"
            prev = previous_owner if previous_owner in SOURCES else "seed"
            strength = cfg[src]["strength"]
            if strength <= 0.0:
                return previous
            wins = (strength >= cfg[prev]["strength"]) if cfg[src]["blend"] else (strength >= 0.5)
            return incoming if wins else previous
        return blend_value(previous, incoming, previous_owner, incoming_owner,
                           policy, neutral=neutral)
    cfg = normalize_policy(policy)
    src = incoming_owner if incoming_owner in SOURCES else "canonical"
    prev = previous_owner if previous_owner in SOURCES else "seed"
    strength = cfg[src]["strength"]
    if previous is None:
        return deepcopy(incoming) if strength >= 0.5 else previous
    if strength <= 0.0:
        return previous
    wins = (strength >= cfg[prev]["strength"]) if cfg[src]["blend"] else (strength >= 0.5)
    return deepcopy(incoming) if wins else previous

def gate_probability(votes, policy: Any = None) -> float:
    """Return the active probability from ``[(owner, active), ...]`` votes.

    When the latest/incoming owner is blend-enabled, active and inactive votes
    compete by their configured strengths.  Otherwise its latest vote wins,
    attenuated by its strength.  Votes must be supplied in write order.
    """
    cfg = normalize_policy(policy)
    clean = [(str(owner), bool(active)) for owner, active in (votes or [])
             if str(owner) in SOURCES]
    if not clean:
        return 0.0
    owner, active = clean[-1]
    source_cfg = cfg[owner]
    if not source_cfg["blend"] or len(clean) == 1:
        return source_cfg["strength"] if active else 0.0
    active_weight = inactive_weight = 0.0
    for src, on in clean:
        weight = cfg[src]["strength"]
        if on:
            active_weight += weight
        else:
            inactive_weight += weight
    total = active_weight + inactive_weight
    return min(1.0, max(0.0, active_weight / total)) if total > 1e-12 else 0.0


def resolve_step_probability(user_touched: bool, user_active: bool,
                             canonical_present: bool, canonical_active: bool,
                             policy: Any = None) -> float:
    """Resolve user/canonical step votes without modifying authored step data."""
    votes = []
    if user_touched:
        votes.append(("user", bool(user_active)))
    if canonical_present:
        votes.append(("canonical", bool(canonical_active)))
    return gate_probability(votes, policy)


def policy_summary(value: Any = None) -> str:
    cfg = normalize_policy(value)
    return " | ".join(
        f"{name.title()}: {'blend' if cfg[name]['blend'] else 'overwrite'} / {cfg[name]['strength']:.0%}"
        for name in ("canonical", "seed", "user")
    )
