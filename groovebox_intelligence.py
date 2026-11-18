"""GROOVEBOX INTELLIGENCE LAYER — deterministic composition, state and integrity services.

This module deliberately contains no UI toolkit dependency.  UI panels can consume these
stable APIs without creating a second source of truth.  All variation is hash-derived;
there is no ambient/random probability path.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = 1


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: Any, digest_size: int = 16) -> str:
    return hashlib.blake2b(_stable(value).encode("utf-8"), digest_size=digest_size).hexdigest()


@dataclass
class Parameter:
    key: str
    owner: str = "unknown"
    value_type: str = "number"
    minimum: float | None = None
    maximum: float | None = None
    destinations: tuple[str, ...] = ()
    metadata: dict = field(default_factory=dict)


class ParameterRegistry:
    """Canonical registry for parameter identity, destinations and source arbitration."""
    SOURCE_PRIORITY = {"canonical": 100, "master_mod": 80, "auto": 60, "step": 50,
                       "performance": 40, "instrument": 30, "rand": 20, "manual": 10}

    def __init__(self, records: Iterable[Mapping] = ()):
        self.parameters: dict[str, Parameter] = {}
        self.routes: dict[str, list[dict]] = {}
        for record in records:
            self.register(**dict(record))

    def register(self, key: str, owner: str = "unknown", value_type: str = "number",
                 minimum=None, maximum=None, destinations=(), metadata=None):
        if not isinstance(key, str) or not key.strip():
            raise ValueError("parameter key must be a non-empty string")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("parameter minimum exceeds maximum")
        p = Parameter(key, owner, value_type, minimum, maximum,
                      tuple(sorted(set(destinations or ()))), copy.deepcopy(metadata or {}))
        self.parameters[key] = p
        self.routes.setdefault(key, [])
        return p

    def add_route(self, key: str, source: str, destination: str | None = None,
                  enabled: bool = True, mode: str = "replace", metadata=None):
        if key not in self.parameters:
            raise KeyError("unregistered parameter: " + str(key))
        if mode not in ("replace", "add", "multiply"):
            raise ValueError("unsupported modulation mode")
        route = {"source": str(source), "destination": destination or key,
                 "enabled": bool(enabled), "mode": mode, "metadata": copy.deepcopy(metadata or {})}
        if route not in self.routes[key]:
            self.routes[key].append(route)
        return route

    def resolve(self, key: str, candidates: Iterable[Mapping]):
        """Resolve one effective writer deterministically; ties use stable source/value order."""
        if key not in self.parameters:
            raise KeyError(key)
        valid = [dict(c) for c in candidates if c.get("enabled", True)]
        valid.sort(key=lambda c: (-self.SOURCE_PRIORITY.get(str(c.get("source", "")).lower(), 0),
                                  str(c.get("source", "")), _stable(c.get("value"))))
        return {"winner": valid[0] if valid else None, "candidates": valid,
                "conflicts": len(valid) > 1,
                "priority": self.SOURCE_PRIORITY}

    def inspect(self, key: str):
        p = self.parameters[key]
        routes = copy.deepcopy(self.routes.get(key, []))
        active = [r for r in routes if r["enabled"]]
        return {"parameter": p.__dict__.copy(), "routes": routes,
                "active_sources": sorted({r["source"] for r in active}),
                "conflict": len({r["source"] for r in active}) > 1}

    def manifest(self):
        return {"schema": SCHEMA,
                "parameters": [dict(p.__dict__) for p in sorted(self.parameters.values(), key=lambda x: x.key)],
                "routes": {k: copy.deepcopy(v) for k, v in sorted(self.routes.items())}}

    @classmethod
    def from_manifest(cls, data):
        data = data if isinstance(data, dict) else {}
        obj = cls(data.get("parameters", []))
        for key, routes in (data.get("routes") or {}).items():
            if key in obj.parameters:
                obj.routes[key] = [dict(r) for r in routes if isinstance(r, dict)]
        return obj


def deterministic_variation(pattern: Mapping, seed: str | int, amount: float = 0.15,
                            preserve: Iterable[str] = ("pitch", "position", "duration")):
    """Create a reproducible velocity/expression variation without adding/removing events.

    Event order, count, pitch, onset and duration are invariant.  Event selection and offsets
    are derived from BLAKE2 hashes, never random()/probability state.
    """
    amount = max(0.0, min(1.0, float(amount)))
    out = copy.deepcopy(dict(pattern))
    events = out.get("events", [])
    if not isinstance(events, list):
        raise ValueError("pattern.events must be a list")
    preserve = set(preserve)
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        token = fingerprint([str(seed), index, event], 8)
        n = int(token[:8], 16) / 0xFFFFFFFF
        if "velocity" not in preserve and "velocity" in event:
            base = float(event["velocity"])
            event["velocity"] = max(0.0, min(1.0, base + (2.0 * n - 1.0) * amount * 0.25))
        if "expression" not in preserve:
            event["expression"] = round(max(0.0, min(1.0, 0.5 + (n - 0.5) * amount)), 6)
    out["variation"] = {"algorithm": "blake2b-deterministic-v1", "seed": str(seed), "amount": amount}
    return out


def discover_motifs(sequence: Iterable[Any], min_repeats: int = 2, max_width: int = 8):
    """Find repeated interval/step motifs; returns deterministic, position-indexed results."""
    seq = list(sequence)
    if len(seq) < 2:
        return []
    intervals = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
    found = {}
    for width in range(1, min(max_width, len(intervals)) + 1):
        for start in range(0, len(intervals) - width + 1):
            motif = tuple(intervals[start:start + width])
            found.setdefault(motif, []).append(start)
    rows = [{"intervals": list(k), "positions": v, "repeats": len(v)}
            for k, v in found.items() if len(v) >= min_repeats]
    rows.sort(key=lambda r: (-r["repeats"], len(r["intervals"]), r["positions"][0], _stable(r["intervals"])))
    return rows


class PerformanceScenes:
    """Project-backed scene snapshots; captures/restores the authoritative project state."""
    ATTR = "groovebox_performance_scenes"

    @staticmethod
    def _store(app):
        store = getattr(app, PerformanceScenes.ATTR, None)
        if not isinstance(store, dict):
            store = {}; setattr(app, PerformanceScenes.ATTR, store)
        return store

    @staticmethod
    def capture(app, name: str, metadata=None):
        if not str(name).strip():
            raise ValueError("scene name is required")
        import project_schema
        project_snapshot = getattr(app, "_project_snapshot", None)
        if callable(project_snapshot):
            state = copy.deepcopy(project_snapshot())
            if isinstance(state, dict) and isinstance(state.get("r32"), dict):
                state["r32"].pop("performance_scenes", None)
        else:
            state = project_schema.snapshot(app)
            state.pop("performance_scenes", None)
        record = {"name": str(name), "created": int(time.time()), "state": state,
                  "fingerprint": fingerprint(state), "metadata": copy.deepcopy(metadata or {})}
        PerformanceScenes._store(app)[str(name)] = record
        return copy.deepcopy(record)

    @staticmethod
    def recall(app, name: str):
        record = PerformanceScenes._store(app).get(name)
        if not isinstance(record, dict) or not isinstance(record.get("state"), dict):
            raise KeyError("performance scene not found: " + str(name))
        state = copy.deepcopy(record["state"])
        apply_project = getattr(app, "_apply_project_snapshot", None)
        if callable(apply_project) and isinstance(state, dict) and ("r32" in state or "instruments" in state):
            return apply_project(state)
        import project_schema
        return project_schema.apply(app, state)

    @staticmethod
    def list(app):
        return [{"name": k, "fingerprint": v.get("fingerprint"), "created": v.get("created"),
                 "metadata": copy.deepcopy(v.get("metadata", {}))}
                for k, v in sorted(PerformanceScenes._store(app).items()) if isinstance(v, dict)]


class CrossMediaClock:
    """Integer/rational media clock. Converts ticks without floating-point drift."""
    def __init__(self, ticks_per_second: int = 48000):
        if int(ticks_per_second) <= 0:
            raise ValueError("ticks_per_second must be positive")
        self.ticks_per_second = int(ticks_per_second)

    def seconds_to_ticks(self, seconds) -> int:
        return int(round(Fraction(str(seconds)) * self.ticks_per_second))

    def frame_to_ticks(self, frame: int, fps_num: int, fps_den: int = 1) -> int:
        if fps_num <= 0 or fps_den <= 0:
            raise ValueError("frame rate must be positive")
        return int(round(Fraction(int(frame) * fps_den * self.ticks_per_second, fps_num)))

    def ticks_to_frame(self, ticks: int, fps_num: int, fps_den: int = 1) -> int:
        return int(round(Fraction(int(ticks) * fps_num, self.ticks_per_second * fps_den)))


def audit_parameter_coverage(registry: ParameterRegistry, required_destinations=("audio", "video", "game", "composition")):
    rows = []
    for key, p in sorted(registry.parameters.items()):
        have = set(p.destinations)
        missing = sorted(set(required_destinations) - have)
        rows.append({"parameter": key, "owner": p.owner, "destinations": sorted(have),
                     "missing": missing, "complete": not missing})
    return {"total": len(rows), "complete": sum(r["complete"] for r in rows),
            "incomplete": sum(not r["complete"] for r in rows), "rows": rows}


def canonical_conformance(canonical: Mapping, live: Mapping, tolerance: float = 1e-9):
    """Read-only comparison; never mutates live or canonical state."""
    diffs = []
    for key in sorted(set(canonical) | set(live)):
        a, b = canonical.get(key, None), live.get(key, None)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            equal = math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tolerance)
        else:
            equal = a == b
        if not equal:
            diffs.append({"key": key, "canonical": copy.deepcopy(a), "live": copy.deepcopy(b),
                          "kind": "missing_live" if key not in live else "missing_canonical" if key not in canonical else "different"})
    return {"conformant": not diffs, "difference_count": len(diffs), "differences": diffs,
            "read_only": True}


def project_integrity_report(project: Mapping, asset_paths: Iterable[str] = ()):
    issues = []
    if not isinstance(project, Mapping):
        return {"ok": False, "issues": [{"code": "project_not_mapping"}]}
    if not isinstance(project.get("r32", {}), Mapping):
        issues.append({"code": "invalid_r32_section", "severity": "error"})
    assets = list(asset_paths or [])
    for raw in assets:
        p = Path(str(raw)).expanduser()
        if not p.exists():
            issues.append({"code": "missing_asset", "path": str(raw), "severity": "error"})
    return {"ok": not any(x.get("severity") == "error" for x in issues), "issues": issues,
            "project_fingerprint": fingerprint(project)}


def adaptive_worker_budget(cpu_count=None, available_memory_bytes=None, per_worker_bytes=1536 * 1024 * 1024,
                           reserve_cores=1, hard_cap=8):
    """Conservative resource budget; callers may lower but should not silently exceed it."""
    cpu = max(1, int(cpu_count or os.cpu_count() or 1))
    cores = max(1, cpu - max(0, int(reserve_cores)))
    if available_memory_bytes is None:
        try:
            import psutil
            available_memory_bytes = psutil.virtual_memory().available
        except Exception:
            available_memory_bytes = per_worker_bytes
    ram = max(1, int(max(0, available_memory_bytes) // max(1, per_worker_bytes)))
    return max(1, min(int(hard_cap), cores, ram))


class RenderPreviewCache:
    """Content-addressed cache with atomic writes and explicit dependency fingerprints."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def key(self, stage: str, inputs: Mapping, dependencies: Iterable[str] = ()):
        return fingerprint({"stage": stage, "inputs": inputs, "dependencies": sorted(dependencies)})

    def path(self, key: str):
        if not key or any(c not in "0123456789abcdef" for c in key.lower()):
            raise ValueError("invalid cache key")
        return self.directory / (key + ".cache")

    def put(self, key: str, source_path):
        src = Path(source_path)
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = self.path(key); tmp = dst.with_suffix(".tmp")
        shutil.copyfile(src, tmp); os.replace(tmp, dst)
        return str(dst)

    def get(self, key: str):
        p = self.path(key)
        return str(p) if p.is_file() else None


@dataclass
class ExportCheckpoint:
    job_id: str
    stage: str
    output: str
    input_fingerprint: str
    dependencies: tuple[str, ...] = ()
    completed: bool = False
    output_fingerprint: str | None = None

    def valid(self):
        if not self.completed or not self.output or not Path(self.output).is_file():
            return False
        return self.output_fingerprint == file_fingerprint(self.output)


def file_fingerprint(path: str, chunk_size: int = 1024 * 1024):
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_checkpoint_graph(checkpoints: Iterable[ExportCheckpoint]):
    rows = {c.job_id: c for c in checkpoints}
    missing = [{"job": c.job_id, "dependency": d} for c in rows.values() for d in c.dependencies if d not in rows]
    cycles = []
    visiting, visited = set(), set()
    def visit(node, trail):
        if node in visiting:
            cycles.append(trail + [node]); return
        if node in visited: return
        visiting.add(node)
        for dep in rows[node].dependencies:
            if dep in rows: visit(dep, trail + [node])
        visiting.remove(node); visited.add(node)
    for node in sorted(rows): visit(node, [])
    return {"ok": not missing and not cycles, "missing_dependencies": missing, "cycles": cycles,
            "invalidated": [c.job_id for c in rows.values() if c.completed and not c.valid()]}


def run_self_test(project: Mapping, registry: ParameterRegistry | None = None,
                  canonical: Mapping | None = None, live: Mapping | None = None):
    """Fast, side-effect-free preflight suitable for a project diagnostics panel."""
    checks = {"project_integrity": project_integrity_report(project)}
    if registry is not None:
        checks["parameter_coverage"] = audit_parameter_coverage(registry)
        checks["parameter_registry_roundtrip"] = ParameterRegistry.from_manifest(registry.manifest()).manifest() == registry.manifest()
    if canonical is not None and live is not None:
        checks["canonical_conformance"] = canonical_conformance(canonical, live)
    checks["clock_roundtrip"] = all(CrossMediaClock().ticks_to_frame(CrossMediaClock().frame_to_ticks(f, 30000, 1001), 30000, 1001) == f for f in (0, 1, 100, 10000))
    failed = [k for k, v in checks.items() if (isinstance(v, dict) and v.get("ok") is False) or v is False]
    return {"ok": not failed, "failed": failed, "checks": checks, "read_only": True}


def registry_for_app(app) -> ParameterRegistry:
    """Return the app's persisted registry, repairing only absent/invalid in-memory containers."""
    data = getattr(app, "groovebox_parameter_registry", None)
    if isinstance(data, ParameterRegistry):
        return data
    reg = ParameterRegistry.from_manifest(data) if isinstance(data, dict) else ParameterRegistry()
    app.groovebox_parameter_registry = reg.manifest()
    return reg


def save_registry(app, registry: ParameterRegistry):
    if not isinstance(registry, ParameterRegistry):
        raise TypeError("registry must be a ParameterRegistry")
    app.groovebox_parameter_registry = registry.manifest()
    return app.groovebox_parameter_registry


def intelligence_report(app, required_destinations=("audio", "video", "game", "composition")):
    """One read-only diagnostics packet for panels, project preflight and support reports."""
    import project_schema
    reg = registry_for_app(app)
    project = {"r32": project_schema.snapshot(app)}
    return {"project_fingerprint": fingerprint(project),
            "parameter_coverage": audit_parameter_coverage(reg, required_destinations),
            "parameter_count": len(reg.parameters),
            "scene_count": len(PerformanceScenes._store(app)),
            "state_manifest": project_schema.manifest(app),
            "read_only": True}
