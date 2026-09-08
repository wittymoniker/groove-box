#!/usr/bin/env python3
"""
Mathematician's Groovebox — Mechanical Phase Audit Runner
=========================================================

Read-only audit tool. Point it at a Groovebox/sCode project folder and it will
produce a ZIP you can send back to ChatGPT.

It collects:
- Python compile/syntax results
- pytest results (if tests + pytest are available)
- AST inventory
- self.<state> read/write graph
- shared-state dependency edges
- high-leverage hub ranking
- related-hub probes
- distant/unrelated-hub probes
- concurrent semantic samples around hubs
- source excerpts for sampled scopes
- hashes + environment info
- outputs from existing project audit tools when detected

No project files are changed.

Usage:
    python3 groovebox_mechanical_audit.py /path/to/groovebox

Optional:
    python3 groovebox_mechanical_audit.py /path/to/groovebox --include-source
    python3 groovebox_mechanical_audit.py /path/to/groovebox --max-files 500
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import dataclasses
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Dict, List, Set, Tuple, Iterable, Optional


SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "node_modules", "venv", ".venv", "env", ".env",
    "dist", "build"
}

IMPORTANT_NAME_HINTS = (
    "groovebox", "video", "game", "visual", "synth", "render", "canonical",
    "seed", "playlist", "project", "export", "media", "performance",
    "scode", "runtime", "compiler", "operator", "meum", "infinity"
)


@dataclasses.dataclass
class FunctionRecord:
    file: str
    qualname: str
    class_name: str
    name: str
    lineno: int
    end_lineno: int
    reads: Set[str]
    writes: Set[str]
    calls: Set[str]
    branches: int
    try_blocks: int
    loops: int
    returns: int
    raises: int
    dynamic_calls: int

    @property
    def span(self) -> int:
        return max(1, self.end_lineno - self.lineno + 1)

    @property
    def semantic_risk(self) -> float:
        return (
            self.span * 0.015
            + self.branches * 1.2
            + self.try_blocks * 1.0
            + self.loops * 1.1
            + self.dynamic_calls * 1.8
            + len(self.writes) * 0.55
            + len(self.reads) * 0.22
        )


class FnVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.records: List[FunctionRecord] = []
        self.class_stack: List[str] = []
        self.fn_stack: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def _visit_fn(self, node):
        class_name = ".".join(self.class_stack)
        q = ".".join([p for p in [class_name, node.name] if p])
        self.fn_stack.append(q)

        reads, writes, calls = set(), set(), set()
        branches = try_blocks = loops = returns = raises = dynamic = 0

        for sub in ast.walk(node):
            if isinstance(sub, ast.If):
                branches += 1
            elif isinstance(sub, ast.Try):
                try_blocks += 1
            elif isinstance(sub, (ast.For, ast.AsyncFor, ast.While)):
                loops += 1
            elif isinstance(sub, ast.Return):
                returns += 1
            elif isinstance(sub, ast.Raise):
                raises += 1
            elif isinstance(sub, ast.Call):
                target = call_name(sub.func)
                if target:
                    calls.add(target)
                    if target in {"getattr", "setattr", "hasattr", "eval", "exec"}:
                        dynamic += 1
            elif isinstance(sub, ast.Attribute):
                if isinstance(sub.value, ast.Name) and sub.value.id == "self":
                    if isinstance(sub.ctx, ast.Store):
                        writes.add(sub.attr)
                    elif isinstance(sub.ctx, ast.Load):
                        reads.add(sub.attr)

            # setattr(self, "x", ...)
            if isinstance(sub, ast.Call) and call_name(sub.func) == "setattr":
                if len(sub.args) >= 2 and isinstance(sub.args[0], ast.Name) and sub.args[0].id == "self":
                    if isinstance(sub.args[1], ast.Constant) and isinstance(sub.args[1].value, str):
                        writes.add(sub.args[1].value)

        end = getattr(node, "end_lineno", node.lineno)
        self.records.append(FunctionRecord(
            file=self.filename,
            qualname=q,
            class_name=class_name,
            name=node.name,
            lineno=node.lineno,
            end_lineno=end,
            reads=reads,
            writes=writes,
            calls=calls,
            branches=branches,
            try_blocks=try_blocks,
            loops=loops,
            returns=returns,
            raises=raises,
            dynamic_calls=dynamic,
        ))
        self.generic_visit(node)
        self.fn_stack.pop()

    visit_FunctionDef = _visit_fn
    visit_AsyncFunctionDef = _visit_fn


def call_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def iter_python_files(project: Path, max_files: int) -> List[Path]:
    files = []
    for p in project.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        files.append(p)
    files.sort(key=lambda p: (
        0 if any(h in p.name.lower() for h in IMPORTANT_NAME_HINTS) else 1,
        len(p.parts),
        str(p).lower()
    ))
    return files[:max_files]


def run(cmd, cwd: Path, timeout: int = 300) -> dict:
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), text=True, capture_output=True,
            timeout=timeout, errors="replace"
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "seconds": round(time.time() - t0, 3),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as e:
        return {
            "cmd": cmd,
            "returncode": None,
            "seconds": round(time.time() - t0, 3),
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e}",
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_project(files: List[Path], project: Path):
    records: List[FunctionRecord] = []
    syntax_errors = []
    file_stats = []

    for p in files:
        rel = str(p.relative_to(project))
        try:
            txt = p.read_text("utf-8", errors="replace")
            tree = ast.parse(txt, filename=rel)
            v = FnVisitor(rel)
            v.visit(tree)
            records.extend(v.records)
            file_stats.append({
                "file": rel,
                "lines": txt.count("\n") + 1,
                "functions": len(v.records),
                "sha256": sha256_file(p),
            })
        except SyntaxError as e:
            syntax_errors.append({
                "file": rel,
                "line": e.lineno,
                "offset": e.offset,
                "message": e.msg,
            })
        except Exception as e:
            syntax_errors.append({
                "file": rel,
                "line": None,
                "offset": None,
                "message": f"{type(e).__name__}: {e}",
            })

    return records, syntax_errors, file_stats


def build_graph(records: List[FunctionRecord]):
    by_name = {r.qualname: r for r in records}
    short_map = defaultdict(list)
    for r in records:
        short_map[r.name].append(r.qualname)

    state_readers = defaultdict(set)
    state_writers = defaultdict(set)
    for r in records:
        for s in r.reads:
            state_readers[s].add(r.qualname)
        for s in r.writes:
            state_writers[s].add(r.qualname)

    edges = defaultdict(set)
    edge_reasons = defaultdict(list)

    # shared-state flow
    for state, writers in state_writers.items():
        readers = state_readers.get(state, set())
        for w in writers:
            for rr in readers:
                if w != rr:
                    edges[w].add(rr)
                    edge_reasons[(w, rr)].append(f"state:{state}")

    # approximate call edges
    for r in records:
        for c in r.calls:
            short = c.split(".")[-1]
            candidates = short_map.get(short, [])
            if len(candidates) == 1:
                dst = candidates[0]
                if dst != r.qualname:
                    edges[r.qualname].add(dst)
                    edge_reasons[(r.qualname, dst)].append(f"call:{c}")

    return by_name, edges, edge_reasons, state_readers, state_writers


def undirected(edges):
    g = defaultdict(set)
    for a, ds in edges.items():
        for b in ds:
            g[a].add(b)
            g[b].add(a)
    return g


def neighborhood(g, start: str, radius: int = 2) -> Set[str]:
    seen = {start}
    q = deque([(start, 0)])
    while q:
        n, d = q.popleft()
        if d >= radius:
            continue
        for m in g.get(n, ()):
            if m not in seen:
                seen.add(m)
                q.append((m, d + 1))
    return seen


def domain_tokens(r: FunctionRecord) -> Set[str]:
    text = f"{r.file} {r.class_name} {r.qualname}".lower()
    toks = set()
    domains = {
        "audio": ("audio", "synth", "wave", "render", "oscillator", "mixdown"),
        "visual": ("visual", "video", "geometry", "frame", "scene"),
        "game": ("game", "world", "npc", "quest", "player"),
        "project": ("project", "save", "load", "snapshot", "fingerprint"),
        "canonical": ("canonical", "playlist", "identity", "rebuild", "reconcile"),
        "seed": ("seed", "random", "phase", "goava", "meum"),
        "ui": ("ui", "widget", "window", "button", "dialog", "layout"),
        "media": ("media", "sample", "carrier", "wav", "ffmpeg"),
        "scode": ("scode", "sir", "sbin", "runtime", "compiler"),
    }
    for d, hints in domains.items():
        if any(h in text for h in hints):
            toks.add(d)
    return toks or {"other"}


def jaccard(a: Set[str], b: Set[str]) -> float:
    return len(a & b) / max(1, len(a | b))


def hub_rank(records, g):
    rows = []
    by = {r.qualname: r for r in records}
    for name, r in by.items():
        degree = len(g.get(name, set()))
        n2 = len(neighborhood(g, name, 2))
        leverage = degree * 2.0 + n2 * 0.12 + r.semantic_risk * 0.25
        rows.append({
            "qualname": name,
            "file": r.file,
            "line": r.lineno,
            "degree": degree,
            "radius2": n2,
            "semantic_risk": round(r.semantic_risk, 3),
            "leverage": round(leverage, 3),
            "domains": sorted(domain_tokens(r)),
        })
    rows.sort(key=lambda x: x["leverage"], reverse=True)
    return rows


def select_related_pairs(hubs, by, g, count=12):
    names = [h["qualname"] for h in hubs[:100]]
    pairs = []
    for i, a in enumerate(names):
        ra = by[a]
        for b in names[i+1:]:
            rb = by[b]
            if b not in g.get(a, set()):
                continue
            ds = jaccard(domain_tokens(ra), domain_tokens(rb))
            if ds >= 0.5:
                pairs.append((a, b, ds))
    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs[:count]


def select_distant_pairs(hubs, by, g, count=12):
    names = [h["qualname"] for h in hubs[:140]]
    pairs = []
    used = set()
    for i, a in enumerate(names):
        ra = by[a]
        for b in reversed(names):
            if a == b or (a, b) in used or (b, a) in used:
                continue
            rb = by[b]
            if b in g.get(a, set()):
                continue
            if jaccard(domain_tokens(ra), domain_tokens(rb)) > 0.0:
                continue
            na = neighborhood(g, a, 1)
            nb = neighborhood(g, b, 1)
            overlap = jaccard(na, nb)
            pairs.append((a, b, overlap))
            used.add((a, b))
            if len(pairs) >= count:
                return pairs
    return pairs[:count]


def probe_pairs(pairs, by, g, related: bool):
    out = []
    for a, b, score in pairs:
        n1a, n1b = neighborhood(g, a, 1), neighborhood(g, b, 1)
        n2a, n2b = neighborhood(g, a, 2), neighborhood(g, b, 2)
        convergence = sorted(
            (n2a & n2b),
            key=lambda n: len(g.get(n, set())),
            reverse=True
        )[:20]
        out.append({
            "kind": "related" if related else "distant",
            "a": a,
            "b": b,
            "a_domains": sorted(domain_tokens(by[a])),
            "b_domains": sorted(domain_tokens(by[b])),
            "radius1_overlap": round(jaccard(n1a, n1b), 4),
            "radius2_overlap": round(jaccard(n2a, n2b), 4),
            "selection_score": round(score, 4),
            "independent_convergence": convergence,
        })
    return out


def concurrent_semantic_samples(hubs, by, g, max_samples=24):
    """
    Sample several distant + nearby neighborhoods at once.  The goal is not to
    assert semantic equivalence, but to give the next review pass multiple
    simultaneous context anchors.
    """
    selected = []
    covered_domains = set()

    # First get domain diversity.
    for h in hubs:
        name = h["qualname"]
        ds = set(h["domains"])
        if not ds <= covered_domains:
            selected.append(name)
            covered_domains |= ds
        if len(selected) >= 10:
            break

    # Then add highest leverage not already selected.
    for h in hubs:
        if h["qualname"] not in selected:
            selected.append(h["qualname"])
        if len(selected) >= max_samples:
            break

    samples = []
    for name in selected:
        r = by[name]
        n1 = neighborhood(g, name, 1)
        neighbors = sorted(
            (x for x in n1 if x != name),
            key=lambda x: len(g.get(x, set())),
            reverse=True
        )[:10]
        samples.append({
            "entry": name,
            "file": r.file,
            "line": r.lineno,
            "end_line": r.end_lineno,
            "domains": sorted(domain_tokens(r)),
            "risk": round(r.semantic_risk, 3),
            "reads": sorted(r.reads)[:80],
            "writes": sorted(r.writes)[:80],
            "calls": sorted(r.calls)[:80],
            "neighbors": neighbors,
        })
    return samples


def write_excerpts(project: Path, samples, out_dir: Path, pad=18):
    exdir = out_dir / "semantic_samples"
    exdir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, s in enumerate(samples):
        p = project / s["file"]
        try:
            lines = p.read_text("utf-8", errors="replace").splitlines()
        except Exception:
            continue
        start = max(1, s["line"] - pad)
        end = min(len(lines), s["end_line"] + pad)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", s["entry"])[:80]
        out = exdir / f"{i:02d}_{safe}.txt"
        body = [
            f"# ENTRY: {s['entry']}",
            f"# SOURCE: {s['file']}:{start}-{end}",
            f"# DOMAINS: {', '.join(s['domains'])}",
            "",
        ]
        for ln in range(start, end + 1):
            body.append(f"{ln:06d} | {lines[ln-1]}")
        out.write_text("\n".join(body) + "\n", encoding="utf-8")
        manifest.append({
            "entry": s["entry"], "file": s["file"],
            "start": start, "end": end, "excerpt": str(out.name)
        })
    return manifest


def existing_tool_runs(project: Path, out_dir: Path, timeout: int):
    candidates = [
        "tools/scoped_accuracy_gauge.py",
        "tools/reverse_decode_groovebox.py",
        "tools/mechanical_scope.py",
        "tools/multi_hub_probe.py",
    ]
    results = []
    for rel in candidates:
        p = project / rel
        if not p.exists():
            continue

        # Prefer --help discovery first so we don't accidentally mutate anything.
        help_result = run([sys.executable, str(p), "--help"], project, timeout=min(timeout, 30))
        entry = {"tool": rel, "help": help_result}

        text = (help_result["stdout"] + "\n" + help_result["stderr"]).lower()
        # Only auto-run tools whose names imply audit/decode/gauge and which are
        # already part of this project. Run with no args only if help succeeded.
        if help_result["returncode"] == 0:
            rr = run([sys.executable, str(p)], project, timeout=timeout)
            entry["run"] = rr
            log = out_dir / (Path(rel).stem + ".log")
            log.write_text(
                "STDOUT:\n" + rr["stdout"] + "\n\nSTDERR:\n" + rr["stderr"],
                encoding="utf-8"
            )
        results.append(entry)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".", help="Groovebox project directory")
    ap.add_argument("--output", default=None, help="Output directory")
    ap.add_argument("--max-files", type=int, default=1000)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--include-source", action="store_true",
                    help="Include analyzed .py source files in the output ZIP")
    ap.add_argument("--skip-pytest", action="store_true")
    args = ap.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise SystemExit(f"Not a directory: {project}")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output).expanduser().resolve() if args.output else (
        project.parent / f"GROOVEBOX_MECHANICAL_AUDIT_{stamp}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    files = iter_python_files(project, args.max_files)
    records, syntax_errors, file_stats = parse_project(files, project)
    by, edges, edge_reasons, state_readers, state_writers = build_graph(records)
    g = undirected(edges)
    hubs = hub_rank(records, g)

    related = probe_pairs(select_related_pairs(hubs, by, g), by, g, True)
    distant = probe_pairs(select_distant_pairs(hubs, by, g), by, g, False)
    samples = concurrent_semantic_samples(hubs, by, g)
    excerpt_manifest = write_excerpts(project, samples, out_dir)

    # Compile pass
    compile_results = []
    for p in files:
        rr = run([sys.executable, "-m", "py_compile", str(p)], project, timeout=30)
        compile_results.append({
            "file": str(p.relative_to(project)),
            "ok": rr["returncode"] == 0,
            "stderr": rr["stderr"][-4000:],
        })

    # pytest pass
    pytest_result = None
    if not args.skip_pytest:
        tests_exist = any((project / n).exists() for n in ("tests", "test"))
        if tests_exist:
            pytest_result = run(
                [sys.executable, "-m", "pytest", "-q"],
                project, timeout=args.timeout
            )
            (out_dir / "pytest.log").write_text(
                "STDOUT:\n" + pytest_result["stdout"] +
                "\n\nSTDERR:\n" + pytest_result["stderr"],
                encoding="utf-8"
            )

    tool_results = existing_tool_runs(project, out_dir, args.timeout)

    # Aggregate convergence frequency from distant probes.
    convergence_counter = Counter()
    for p in distant:
        convergence_counter.update(p["independent_convergence"])

    summary = {
        "project": str(project),
        "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version,
        "platform": platform.platform(),
        "files_analyzed": len(files),
        "total_lines": sum(x["lines"] for x in file_stats),
        "classes_approx": len({
            r.class_name for r in records if r.class_name
        }),
        "functions_methods": len(records),
        "syntax_errors": len(syntax_errors),
        "compile_pass": sum(1 for r in compile_results if r["ok"]),
        "compile_fail": sum(1 for r in compile_results if not r["ok"]),
        "shared_state_variables": len(set(state_readers) | set(state_writers)),
        "directed_dependency_edges": sum(len(v) for v in edges.values()),
        "top_hubs": hubs[:30],
        "top_distant_convergence": convergence_counter.most_common(30),
        "related_probe_count": len(related),
        "distant_probe_count": len(distant),
        "semantic_sample_count": len(samples),
        "pytest": None if pytest_result is None else {
            "returncode": pytest_result["returncode"],
            "seconds": pytest_result["seconds"],
            "stdout_tail": pytest_result["stdout"][-6000:],
            "stderr_tail": pytest_result["stderr"][-3000:],
        },
    }

    # Detailed JSON
    detail = {
        "summary": summary,
        "syntax_errors": syntax_errors,
        "files": file_stats,
        "compile_results": compile_results,
        "related_probes": related,
        "distant_probes": distant,
        "semantic_samples": samples,
        "excerpt_manifest": excerpt_manifest,
        "state": {
            k: {
                "readers": sorted(state_readers.get(k, set())),
                "writers": sorted(state_writers.get(k, set())),
            }
            for k in sorted(set(state_readers) | set(state_writers))
        },
        "edges": [
            {"src": a, "dst": b, "reasons": edge_reasons[(a, b)]}
            for a, ds in edges.items() for b in sorted(ds)
        ],
        "existing_tool_runs": tool_results,
    }

    (out_dir / "MECHANICAL_AUDIT.json").write_text(
        json.dumps(detail, indent=2, default=list), encoding="utf-8"
    )

    # Human-readable summary.
    md = []
    md.append("# Mathematician's Groovebox — Mechanical Audit")
    md.append("")
    md.append(f"- Files analyzed: **{summary['files_analyzed']}**")
    md.append(f"- Lines analyzed: **{summary['total_lines']}**")
    md.append(f"- Functions/methods: **{summary['functions_methods']}**")
    md.append(f"- Dependency edges: **{summary['directed_dependency_edges']}**")
    md.append(f"- Shared-state variables: **{summary['shared_state_variables']}**")
    md.append(f"- Compile: **{summary['compile_pass']} pass / {summary['compile_fail']} fail**")
    md.append(f"- Syntax errors: **{summary['syntax_errors']}**")
    if summary["pytest"] is not None:
        md.append(f"- pytest return code: **{summary['pytest']['returncode']}**")
    md.append("")
    md.append("## Highest-leverage hubs")
    md.append("")
    for h in hubs[:25]:
        md.append(
            f"- `{h['qualname']}` — leverage {h['leverage']}, "
            f"degree {h['degree']}, R2 {h['radius2']}, "
            f"risk {h['semantic_risk']} — {h['file']}:{h['line']}"
        )
    md.append("")
    md.append("## Distant-entry convergence")
    md.append("")
    for name, count in convergence_counter.most_common(25):
        md.append(f"- `{name}` — reappeared from **{count}** distant probes")
    md.append("")
    md.append("## Related hub probes")
    md.append("")
    for p in related:
        md.append(
            f"- `{p['a']}` ↔ `{p['b']}`: "
            f"R1={p['radius1_overlap']:.3f}, R2={p['radius2_overlap']:.3f}"
        )
    md.append("")
    md.append("## Distant hub probes")
    md.append("")
    for p in distant:
        md.append(
            f"- `{p['a']}` ↔ `{p['b']}`: "
            f"R1={p['radius1_overlap']:.3f}, R2={p['radius2_overlap']:.3f}; "
            f"convergence={', '.join(p['independent_convergence'][:6]) or 'none'}"
        )
    md.append("")
    md.append("## Concurrent semantic samples")
    md.append("")
    for s in samples:
        md.append(
            f"- `{s['entry']}` — {s['file']}:{s['line']}-{s['end_line']} "
            f"({', '.join(s['domains'])}; risk {s['risk']})"
        )
    md.append("")
    md.append("Send the generated ZIP back to ChatGPT for the next mechanical pass.")
    (out_dir / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Environment
    env = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cwd": str(project),
    }
    (out_dir / "ENVIRONMENT.json").write_text(
        json.dumps(env, indent=2), encoding="utf-8"
    )

    if args.include_source:
        src_dir = out_dir / "source_snapshot"
        for p in files:
            rel = p.relative_to(project)
            dst = src_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)

    # Hashes of generated reports.
    hash_lines = []
    for p in sorted(out_dir.rglob("*")):
        if p.is_file():
            hash_lines.append(f"{sha256_file(p)}  {p.relative_to(out_dir)}")
    (out_dir / "SHA256SUMS.txt").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")

    zip_path = out_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out_dir.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(out_dir.parent))

    print()
    print("=== GROOVEBOX MECHANICAL AUDIT COMPLETE ===")
    print(f"Project:  {project}")
    print(f"Reports:  {out_dir}")
    print(f"Send this ZIP back to ChatGPT:")
    print(f"  {zip_path}")
    print()
    print(f"Functions/methods: {len(records)}")
    print(f"Dependency edges:  {sum(len(v) for v in edges.values())}")
    print(f"Compile pass/fail:  {summary['compile_pass']}/{summary['compile_fail']}")
    if pytest_result is not None:
        print(f"pytest rc:          {pytest_result['returncode']}")
    print()

if __name__ == "__main__":
    main()
