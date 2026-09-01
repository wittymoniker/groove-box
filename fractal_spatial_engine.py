"""Audio-immutable fractal spatial kernel for Groovebox 2026.2.

This module does not alter or call the audio engine. It creates a deterministic
spatial realization of the project's seed/phase/stochastic/topology grammar.
Five independent seed-derived channels (position, phase, scale, topology,
complexity) are phase-locked to a parent point and recursively expanded.
"""
from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple

MEUM = 1.1975807343385265
PHI = 1.618033988749895
GOLDEN_ANGLE = math.tau * (1.0 - 1.0 / PHI)


def _seed_int(seed: Any) -> int:
    try:
        return int(float(seed))
    except Exception:
        return int.from_bytes(hashlib.sha256(str(seed).encode()).digest()[:8], "big")




# Operator Theory video/game trig via isn · ics · arcisn · arcics.
# book: isn(θ)=2·sin(θ/2) ⇒ sin(θ)=isn(2θ)/2 ; ics similarly for cos.
# Always runs through the isn/ics family (numeric-identical to math.sin/cos).
def _book_isn(x):
    return 2.0 * math.sin(0.5 * float(x))
def _book_ics(x):
    return 2.0 * math.cos(0.5 * float(x))
def _book_isn_inv(y):
    a = max(-1.0, min(1.0, 0.5 * float(y)))
    return 2.0 * math.asin(a)
def _book_ics_inv(y):
    a = max(-1.0, min(1.0, 0.5 * float(y)))
    return 2.0 * math.acos(a)
def vg_sin(x):
    return 0.5 * _book_isn(2.0 * float(x))
def vg_cos(x):
    return 0.5 * _book_ics(2.0 * float(x))
def vg_asin(x):
    x = max(-1.0, min(1.0, float(x)))
    return 0.5 * _book_isn_inv(2.0 * x)
def vg_acos(x):
    x = max(-1.0, min(1.0, float(x)))
    return 0.5 * _book_ics_inv(2.0 * x)


def residue(seed: Any, label: str) -> float:
    d = hashlib.sha256(f"{_seed_int(seed)}|{label}".encode()).digest()
    return int.from_bytes(d[:8], "big") / float(1 << 64)


def bipolar(x: float) -> float:
    return 2.0 * float(x) - 1.0


def _hash_id(payload: Dict[str, Any], n=24) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()[:n]


@dataclass(frozen=True)
class SpatialPoint:
    id: str
    parent: str
    depth: int
    index: int
    x: float
    y: float
    z: float
    phase: float
    scale: float
    topology_class: int
    complexity: float
    harmonic: int

    def to_dict(self):
        return asdict(self)


class FractalSpatialEngine:
    """Lazy, deterministic spatial universe generated from one master seed.

    The audio engine is deliberately absent from this dependency graph.
    ``snapshot`` is pure data and can be used by a renderer, game, exporter,
    or test harness without changing the audio implementation.
    """
    CHANNELS = ("position", "phase", "scale", "topology", "complexity")
    VERSION = "spatial/2026.3-native-four-engine"

    # The four canonical non-GOAVA engines are the sculpting frame.
    CORE_ENGINES = ("randomizer", "phase_lock", "euclidean", "seeded")

    def __init__(self, seed: Any, composition_fingerprint: str = "0" * 16,
                 goava: bool = False):
        self.seed = _seed_int(seed)
        self.composition_fingerprint = str(composition_fingerprint)
        # GOAVA is an adapter/lens only. It cannot be required to construct the field.
        self.goava = bool(goava)

    def engine_residue(self, engine: str, depth: int, index: int) -> float:
        if engine not in self.CORE_ENGINES:
            raise ValueError(engine)
        return residue(self.seed, f"fse/core/{engine}/{depth}/{index}/{self.composition_fingerprint}")

    def channel(self, depth: int, index: int, channel: str) -> float:
        if channel not in self.CHANNELS:
            raise ValueError(channel)
        # Every visual channel is a deterministic projection of ALL FOUR core engines.
        vals = [self.engine_residue(e, depth, index) for e in self.CORE_ENGINES]
        weights = {
            "position": (0.46, 0.14, 0.18, 0.22),
            "phase":    (0.12, 0.50, 0.18, 0.20),
            "scale":    (0.24, 0.18, 0.18, 0.40),
            "topology": (0.20, 0.20, 0.44, 0.16),
            "complexity":(0.30, 0.18, 0.26, 0.26),
        }[channel]
        x = sum(v*w for v,w in zip(vals, weights))
        # Nonlinear folding keeps the field bounded while preserving seed identity.
        return (vg_sin(math.tau * (x + MEUM * self.seed * 1e-9)) + 1.0) * 0.5

    def phase_lock(self, parent_phase: float, depth: int, index: int) -> float:
        r = self.channel(depth, index, "phase")
        eu = self.engine_residue("euclidean", depth, index)
        pl = self.engine_residue("phase_lock", depth, index)
        # Euclidean residue supplies interval geometry; phase-lock residue supplies
        # bounded stochastic deviation. Neither requires GOAVA.
        child = parent_phase + GOLDEN_ANGLE * (1 + index) + math.tau * (eu - 0.5) * 0.5
        child += math.tau * bipolar(pl) * 0.125 + math.tau * bipolar(r) * 0.0625
        return child % math.tau

    def child_count(self, depth: int, index: int) -> int:
        c = self.channel(depth, index, "complexity")
        eu = self.engine_residue("euclidean", depth, index)
        seeded = self.engine_residue("seeded", depth, index)
        # Stochastic harmonic introduction is bounded and seed-derived.
        return 1 + int((0.55*c + 0.25*eu + 0.20*seeded) * (2 if depth < 2 else 3))

    def point(self, depth: int, index: int, parent: SpatialPoint | None = None,
              harmonic: int | None = None) -> SpatialPoint:
        depth = max(0, int(depth)); index = max(0, int(index))
        p = parent
        parent_id = p.id if p else "ROOT"
        pp = p.phase if p else residue(self.seed, "fse/root_phase") * math.tau
        phase = self.phase_lock(pp, depth, index)
        pos_r = self.channel(depth, index, "position")
        scale_r = self.channel(depth, index, "scale")
        topo = int(self.channel(depth, index, "topology") * 8) % 8
        complexity = self.channel(depth, index, "complexity")
        h = int(harmonic if harmonic is not None else 1 + (depth % 7))
        radius = (0.22 + 0.78 * scale_r) * (0.72 ** depth)
        # Phase-locked spherical offset. The topology channel selects a stable
        # permutation of the axes rather than injecting unrelated geometry.
        a = phase + topo * GOLDEN_ANGLE * 0.5
        elev = bipolar(pos_r) * (0.22 + 0.12 * (topo % 3))
        if p is None:
            bx, by, bz = 0.0, 0.0, 0.0
        else:
            bx, by, bz = p.x, p.y, p.z
        dx = radius * vg_cos(a) * vg_cos(elev)
        dy = radius * vg_sin(elev)
        dz = radius * vg_sin(a) * vg_cos(elev)
        if topo & 1:
            dx, dz = dz, -dx
        sid = _hash_id({"s": self.seed, "fp": self.composition_fingerprint,
                        "d": depth, "i": index, "p": parent_id, "h": h})
        return SpatialPoint(sid, parent_id, depth, index, bx + dx, by + dy, bz + dz,
                            phase, 0.35 + 1.65 * scale_r, topo, complexity, h)

    def generate(self, depth: int = 3, roots: int = 5) -> List[SpatialPoint]:
        """Generate a finite window of the infinite lazy universe."""
        depth = max(0, int(depth)); roots = max(1, int(roots))
        out: List[SpatialPoint] = []
        frontier = [self.point(0, i, None, harmonic=1) for i in range(roots)]
        out.extend(frontier)
        for d in range(1, depth + 1):
            nxt = []
            for parent in frontier:
                n = self.child_count(d, parent.index)
                for j in range(n):
                    child = self.point(d, j, parent, harmonic=1 + d + j)
                    nxt.append(child)
            frontier = nxt
            out.extend(frontier)
        return out

    def topology_edges(self, points: List[SpatialPoint]) -> List[Tuple[str, str]]:
        ids = {p.id for p in points}
        edges = [(p.parent, p.id) for p in points if p.parent in ids]
        # Add deterministic phase-locked sibling links only when the topology
        # residue calls for them. This preserves graph identity without random edges.
        by_parent: Dict[str, List[SpatialPoint]] = {}
        for p in points:
            by_parent.setdefault(p.parent, []).append(p)
        for siblings in by_parent.values():
            siblings.sort(key=lambda p: p.index)
            for a, b in zip(siblings, siblings[1:]):
                if a.topology_class % 3 == 0:
                    edges.append((a.id, b.id))
        return edges

    def snapshot(self, depth=3, roots=5) -> Dict[str, Any]:
        points = self.generate(depth, roots)
        edges = self.topology_edges(points)
        # GOAVA is explicitly post-projection; topology comes entirely from the native field.
        return {
            "version": self.VERSION,
            "seed": self.seed,
            "composition_fingerprint": self.composition_fingerprint,
            "goava_adapter": self.goava,
            "goava_required": False,
            "core_engines": list(self.CORE_ENGINES),
            "channels": list(self.CHANNELS),
            "principles": ["phase_lock", "stochastic_harmonic_expansion"],
            "points": [p.to_dict() for p in points],
            "edges": [list(e) for e in edges],
            "infinite": True,
            "window": {"depth": int(depth), "roots": int(roots)},
            "fingerprint": _hash_id({"seed": self.seed, "fp": self.composition_fingerprint,
                                     "depth": int(depth), "roots": int(roots),
                                     "points": [p.to_dict() for p in points], "edges": edges}, 16),
        }

    def apply_goava_adapter(self, points: List[SpatialPoint]) -> List[SpatialPoint]:
        """Optional GOAVA lens. Native spatial generation never calls this.

        The adapter changes presentation metadata/phase only; it does not create
        topology or supply the base coordinate field. With GOAVA disabled, the
        exact same native universe remains complete and deterministic.
        """
        if not self.goava:
            return list(points)
        out = []
        for p in points:
            g = residue(self.seed, f"fse/goava-adapter/{p.depth}/{p.index}/{p.id}")
            out.append(SpatialPoint(p.id, p.parent, p.depth, p.index, p.x, p.y, p.z,
                                    (p.phase + math.tau * 0.125 * bipolar(g)) % math.tau,
                                    p.scale, p.topology_class, p.complexity, p.harmonic))
        return out


def build_spatial_state(seed: Any, composition_fingerprint="0" * 16,
                        depth=3, roots=5, goava=False):
    return FractalSpatialEngine(seed, composition_fingerprint, goava).snapshot(depth, roots)
