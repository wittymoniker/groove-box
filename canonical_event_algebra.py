"""Canonical Event Algebra + Interaction UI Algebra for Mathematician's Groovebox.

Events are derived from invariant semantic state, never rendering decomposition.
Representation-only keys such as part/object/instrument count are excluded from
identity.  UI is a deterministic projection of canonical event identity, and
experience is calculated from semantic complexity, recurrence/novelty, and a
Meum-scaled progression curve.

Rational values are used for structural partitions and exact weights. Irrational
constants are used for non-short-repeat ordering, traversal, and progression.
"""
from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence

M = 1.1975807343
PHI = (1.0 + math.sqrt(5.0)) / 2.0

REPRESENTATION_ONLY_KEYS = {
    "parts", "part_count", "object_count", "render_count", "instrument_count",
    "n_instruments", "lod", "draw_calls", "mesh_count", "instance_count",
    "partition_count", "visual_object_count",
}

UI_PRIMITIVES = (
    "inspect", "select", "navigate", "move", "connect", "divide", "combine",
    "transform", "tune", "exchange", "negotiate", "build", "destroy", "craft",
    "cast", "signal", "temporal", "confirm", "cancel",
)

OP_TO_PRIMITIVES = {
    "interact": ("inspect", "select", "confirm"),
    "inspect": ("inspect", "select"),
    "move": ("navigate", "move", "confirm"),
    "dash": ("navigate", "move"),
    "jump": ("navigate", "move"),
    "craft": ("inspect", "combine", "craft", "confirm"),
    "build": ("inspect", "select", "build", "confirm"),
    "destroy": ("inspect", "destroy", "confirm"),
    "trade": ("inspect", "exchange", "negotiate", "confirm"),
    "negotiate": ("inspect", "negotiate", "exchange"),
    "cast": ("select", "transform", "cast", "confirm"),
    "attune": ("inspect", "tune", "transform"),
    "signal": ("signal", "connect", "tune"),
    "scan": ("inspect", "signal"),
    "throw": ("select", "move", "confirm"),
    "harvest": ("inspect", "select", "divide", "combine"),
    "temporal": ("inspect", "temporal", "transform"),
}


def _u(seed: Any, label: str) -> float:
    d = hashlib.sha256(f"{seed}|{label}".encode("utf-8", "replace")).digest()
    return int.from_bytes(d[:8], "big") / float(1 << 64)


def _canon(v: Any, drop_representation: bool = True) -> Any:
    if isinstance(v, Mapping):
        out = {}
        for k in sorted(v, key=lambda x: str(x)):
            ks = str(k)
            if drop_representation and ks in REPRESENTATION_ONLY_KEYS:
                continue
            out[ks] = _canon(v[k], drop_representation)
        return out
    if isinstance(v, (list, tuple)):
        return [_canon(x, drop_representation) for x in v]
    if isinstance(v, set):
        return sorted((_canon(x, drop_representation) for x in v), key=lambda x: json.dumps(x, sort_keys=True, default=str))
    if isinstance(v, float):
        return round(v, 14) if math.isfinite(v) else str(v)
    if v is None or isinstance(v, (str, int, bool)):
        return v
    return str(v)


def _leaf_count(v: Any) -> int:
    if isinstance(v, Mapping):
        return sum(_leaf_count(x) for x in v.values())
    if isinstance(v, (list, tuple, set)):
        return sum(_leaf_count(x) for x in v)
    return 1


def _semantic_kind(v: Any) -> str:
    if isinstance(v, Mapping):
        return str(v.get("kind") or v.get("type") or v.get("role") or v.get("class") or "entity").lower()
    return str(type(v).__name__).lower()


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    class_id: str
    field_id: str
    operation: str
    actor: Any
    target: Any
    context: Any
    consequences: Any
    temporal_stage: str
    locality: str
    magnitude: float
    direction: Sequence[float]
    complexity: float
    rarity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id, "class_id": self.class_id, "field_id": self.field_id,
            "operation": self.operation, "actor": self.actor, "target": self.target,
            "context": self.context, "consequences": self.consequences,
            "temporal_stage": self.temporal_stage, "locality": self.locality,
            "magnitude": self.magnitude, "direction": list(self.direction),
            "complexity": self.complexity, "rarity": self.rarity,
        }


def canonical_event(
    field_id: str,
    operation: str,
    actor: Any = None,
    target: Any = None,
    context: Any = None,
    consequences: Any = None,
    temporal_stage: str = "build",
    locality: str = "local",
    magnitude: float = 1.0,
    direction: Sequence[float] = (0.0, 0.0, 0.0),
) -> CanonicalEvent:
    """Build an event identity invariant to part/object/instrument factorization."""
    op = str(operation or "interact").strip().lower()
    actor_c, target_c = _canon(actor), _canon(target)
    ctx_c, con_c = _canon(context), _canon(consequences)
    try: mag = float(magnitude)
    except Exception: mag = 1.0
    d = []
    for x in list(direction or ())[:4]:
        try: d.append(round(float(x), 14))
        except Exception: d.append(0.0)
    while len(d) < 3: d.append(0.0)
    structural = {
        "field_id": str(field_id or "0"), "operation": op,
        "actor": actor_c, "target": target_c,
        "context": ctx_c, "consequences": con_c,
        "temporal_stage": str(temporal_stage or "build").lower(),
        "locality": str(locality or "local").lower(),
        "magnitude": round(mag, 14), "direction": d,
    }
    raw = json.dumps(structural, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    event_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    event_class = {
        "field_id": structural["field_id"], "operation": op,
        "actor_kind": _semantic_kind(actor_c), "target_kind": _semantic_kind(target_c),
        "consequence_kind": _semantic_kind(con_c),
        "temporal_stage": structural["temporal_stage"], "locality": structural["locality"],
    }
    class_id = hashlib.sha256(json.dumps(event_class, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    leaves = _leaf_count(actor_c) + _leaf_count(target_c) + _leaf_count(ctx_c) + _leaf_count(con_c)
    # Rational structural complexity: exact semantic leaf count compressed logarithmically.
    complexity = math.log2(2.0 + float(leaves))
    # Rarity is deterministic but not claimed as physical probability. It is a
    # seed-space recurrence index; endpoint proximity yields rare signatures.
    ru = _u(event_id, "recurrence")
    tail_p = max(2.0 ** -32, min(1.0, 2.0 * min(ru, 1.0 - ru)))
    rarity = -math.log2(tail_p)
    return CanonicalEvent(event_id, class_id, structural["field_id"], op, actor_c, target_c,
                          ctx_c, con_c, structural["temporal_stage"], structural["locality"],
                          round(mag, 14), tuple(d), complexity, rarity)


def interaction_ui(event: CanonicalEvent) -> Dict[str, Any]:
    """Project a canonical event into a deterministic, event-specific UI grammar."""
    base = list(OP_TO_PRIMITIVES.get(event.operation, ("inspect", "select", "transform", "confirm")))
    # Context can activate semantically relevant primitives without special-case widgets.
    text = json.dumps({"target": event.target, "context": event.context, "consequences": event.consequences}, sort_keys=True, default=str).lower()
    semantic = []
    for needle, primitive in (
        ("time", "temporal"), ("signal", "signal"), ("audio", "tune"), ("frequency", "tune"),
        ("trade", "exchange"), ("npc", "negotiate"), ("build", "build"), ("craft", "craft"),
        ("link", "connect"), ("split", "divide"), ("merge", "combine"), ("destroy", "destroy"),
    ):
        if needle in text: semantic.append(primitive)
    controls = []
    for p in base + semantic + ["cancel"]:
        if p in UI_PRIMITIVES and p not in controls: controls.append(p)
    # Rational grid is structural; irrational phase is only tie-breaking/order/traversal.
    n = len(controls)
    cols = max(1, int(math.ceil(math.sqrt(n))))
    rows = max(1, int(math.ceil(n / cols)))
    phase = (M - 1.0) * _u(event.event_id, "ui-phase")
    ordered = sorted(controls, key=lambda p: ((_u(event.event_id, "order|" + p) + phase) % 1.0, p))
    cells = []
    for i, p in enumerate(ordered):
        cells.append({
            "primitive": p, "row": i // cols, "column": i % cols,
            "row_share": 1.0 / rows, "column_share": 1.0 / cols,
            "phase": ((i * (M - 1.0)) + phase) % 1.0,
            "weight": 1.0 / n,
        })
    ui_id = hashlib.sha256((event.event_id + "|ui-v1").encode()).hexdigest()[:24]
    return {
        "version": "interaction-ui-algebra-v1", "ui_id": ui_id, "event_id": event.event_id,
        "class_id": event.class_id, "operation": event.operation,
        "layout": {"rows": rows, "columns": cols, "rational_partition": True},
        "controls": cells, "irrational_traversal": {"M-1": M - 1.0, "phase": phase},
    }


@dataclass
class ExperienceLedger:
    """Deterministic event experience with unbounded total and Meum progression."""
    total: float = 0.0
    event_counts: MutableMapping[str, int] = field(default_factory=dict)
    class_counts: MutableMapping[str, int] = field(default_factory=dict)

    def level_for(self, total: float | None = None) -> int:
        x = max(0.0, self.total if total is None else float(total))
        # Geometric Meum progression. There is no hard maximum level.
        if x <= 0.0: return 1
        return max(1, int(math.floor(math.log(1.0 + x * (M - 1.0), M))) + 1)

    def threshold_for_level(self, level: int) -> float:
        l = max(1, int(level))
        return ((M ** max(0, l - 1)) - 1.0) / (M - 1.0)

    def award(self, event: CanonicalEvent) -> Dict[str, Any]:
        exact_seen = int(self.event_counts.get(event.event_id, 0))
        class_seen = int(self.class_counts.get(event.class_id, 0))
        # Rational recurrence discount preserves exact compositional meaning.
        recurrence = 1.0 / (1.0 + exact_seen)
        class_novelty = 1.0 / (1.0 + class_seen)
        # Irrational scales affect progression/differentiation, not event identity.
        gain = recurrence * (
            1.0
            + (M - 1.0) * event.complexity
            + (1.0 / M) * event.rarity
            + (PHI - 1.0) * class_novelty
        )
        before = self.total
        level_before = self.level_for(before)
        self.total = math.fsum((self.total, gain))
        self.event_counts[event.event_id] = exact_seen + 1
        self.class_counts[event.class_id] = class_seen + 1
        level_after = self.level_for(self.total)
        return {
            "event_id": event.event_id, "gain": gain, "total": self.total,
            "level_before": level_before, "level": level_after,
            "leveled_up": level_after > level_before,
            "exact_recurrence": exact_seen, "class_recurrence": class_seen,
            "next_threshold": self.threshold_for_level(level_after + 1),
        }

    def snapshot(self) -> Dict[str, Any]:
        return {"total": self.total, "level": self.level_for(), "events": dict(self.event_counts), "classes": dict(self.class_counts)}
