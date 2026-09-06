#!/usr/bin/env python3
"""
sOS Whole-System Reverse Decoder 1.0
------------------------------------
Static structural decoder for the full sOS/sCode/Groovebox tree.

What it does:
- Scans Groovebox, sCode, sOS, sOS_COMPILER, BUILD_COMPILER (or whole project).
- Excludes venv/build/cache/vendor noise by default.
- Parses Python with AST.
- Indexes sCode/.sC declarations and dependency statements.
- Indexes shell scripts, systemd units, JSON/TOML/YAML-ish configs.
- Builds a cross-file dependency graph.
- Finds shared hubs and high-leverage unresolved regions.
- Runs in parallel across CPU cores.
- Emits deterministic JSON + Markdown reports for the Finish Product Router / sAssistant.

This is a structural/semantic-routing decoder, not a proof that every OS behavior
has been understood or translated correctly. Use the generated priority list to
drive deeper behavioral tests and conversion.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_ROOTS = ["Groovebox", "sCode", "sOS", "sOS_COMPILER", "BUILD_COMPILER"]

SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox", "node_modules", "site-packages",
    ".groovebox-build-venv", ".venv", "venv", "env",
    "dist", "build", "generated", "generated_mechanical",
    ".finish-router", ".cache", "vendor", "third_party", "third-party",
}

TEXT_SUFFIXES = {
    ".py", ".scode", ".sc", ".sC", ".sh", ".bash", ".zsh", ".fish",
    ".service", ".target", ".socket", ".timer", ".path", ".mount",
    ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf",
    ".md", ".txt", ".desktop",
}

DEP_PATTERNS = [
    re.compile(r'^\s*(?:use|import|include|connect|requires)\s+["\']?([^"\';\s]+)', re.I),
    re.compile(r'^\s*source\s+["\']?([^"\';\s]+)', re.I),
    re.compile(r'^\s*\.\s+["\']?([^"\';\s]+)', re.I),
]

SCODE_DECL = re.compile(
    r'^\s*(?P<kind>struct|class|fn|func|function|theorem|rule|operator|let|const|state|domain)\s+'
    r'(?P<name>[A-Za-z_][A-Za-z0-9_:.<>-]*)',
    re.I
)

SHELL_FUNC = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)\s*\{')
SYSTEMD_KEY = re.compile(r'^\s*([A-Za-z][A-Za-z0-9]+)\s*=\s*(.*?)\s*$')

MATH_TOKENS = re.compile(
    r'\b(?:MEUM|MEUM_MINUS_1|MEUM_INV|isn|ics|OT|operator|seed|phase|canonical|'
    r'infinity|finite_infinity|tensor|phi|nyquist|fft|sin|cos)\b',
    re.I
)
STATE_TOKENS = re.compile(
    r'\b(?:state|config|project|playlist|instrument|voice|slot|service|daemon|'
    r'process|device|audio|video|game|runtime|compiler|kernel|boot|mount)\b',
    re.I
)

@dataclass
class FileRecord:
    path: str
    suffix: str
    size: int
    sha256: str
    lines: int
    kind: str
    symbols: list[str]
    deps: list[str]
    calls: list[str]
    reads: list[str]
    writes: list[str]
    tags: list[str]
    risk: float
    parse_error: Optional[str] = None

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def classify_file(p: Path) -> str:
    s = p.suffix
    name = p.name.lower()
    if s == ".py":
        return "python"
    if s.lower() in {".scode", ".sc"} or s == ".sC":
        return "scode"
    if s in {".sh", ".bash", ".zsh", ".fish"}:
        return "shell"
    if s in {".service", ".target", ".socket", ".timer", ".path", ".mount"}:
        return "systemd"
    if s in {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf"}:
        return "config"
    if name in {"makefile", "cmakelists.txt"}:
        return "build"
    return "text"

def py_attr_name(node: ast.AST) -> Optional[str]:
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None

class PyVisitor(ast.NodeVisitor):
    def __init__(self):
        self.symbols, self.deps, self.calls, self.reads, self.writes = [], [], [], [], []
        self.branches = self.tries = self.raises = self.dynamic = 0

    def visit_Import(self, node):
        for a in node.names:
            self.deps.append(a.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.deps.append(node.module)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.symbols.append(f"class:{node.name}")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.symbols.append(f"fn:{node.name}")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = py_attr_name(node.func)
        if name:
            self.calls.append(name)
            if name in {"eval", "exec", "compile", "__import__", "getattr", "setattr"}:
                self.dynamic += 1
        self.generic_visit(node)

    def visit_Attribute(self, node):
        name = py_attr_name(node)
        if name and name.startswith("self."):
            if isinstance(node.ctx, ast.Store):
                self.writes.append(name)
            elif isinstance(node.ctx, ast.Load):
                self.reads.append(name)
        self.generic_visit(node)

    def visit_If(self, node): self.branches += 1; self.generic_visit(node)
    def visit_For(self, node): self.branches += 1; self.generic_visit(node)
    def visit_While(self, node): self.branches += 1; self.generic_visit(node)
    def visit_Try(self, node): self.tries += 1; self.generic_visit(node)
    def visit_Raise(self, node): self.raises += 1; self.generic_visit(node)

def parse_python(text: str):
    v = PyVisitor()
    tree = ast.parse(text)
    v.visit(tree)
    risk = (
        min(v.branches / 20.0, 2.0)
        + min(v.tries / 8.0, 1.5)
        + min(v.raises / 8.0, 1.0)
        + min(v.dynamic / 4.0, 2.0)
        + min(len(set(v.writes)) / 40.0, 2.0)
    )
    return v.symbols, v.deps, v.calls, v.reads, v.writes, risk

def parse_textual(kind: str, text: str):
    symbols, deps, calls, reads, writes = [], [], [], [], []
    risk = 0.0

    for line in text.splitlines():
        if kind == "scode":
            m = SCODE_DECL.match(line)
            if m:
                symbols.append(f"{m.group('kind').lower()}:{m.group('name')}")
        elif kind == "shell":
            m = SHELL_FUNC.match(line)
            if m:
                symbols.append(f"fn:{m.group(1)}")
        elif kind == "systemd":
            m = SYSTEMD_KEY.match(line)
            if m:
                key, value = m.groups()
                symbols.append(f"unit:{key}")
                if key in {"ExecStart", "ExecStartPre", "ExecStartPost", "Requires", "Wants", "After", "Before"}:
                    deps.extend(re.findall(r'[A-Za-z0-9_./@:+-]+', value))

        for pat in DEP_PATTERNS:
            m = pat.match(line)
            if m:
                deps.append(m.group(1))

    # Heuristic structural risk only.
    risk += min(text.count(" if ") / 30.0, 1.0)
    risk += min(text.count("while ") / 20.0, 1.0)
    risk += min(text.count("TODO") / 5.0, 1.0)
    risk += min(text.count("FIXME") / 5.0, 1.0)
    return symbols, deps, calls, reads, writes, risk

def analyze_one(path_str: str) -> FileRecord:
    p = Path(path_str)
    try:
        data = p.read_bytes()
        text = data.decode("utf-8", errors="replace")
        kind = classify_file(p)
        parse_error = None
        try:
            if kind == "python":
                symbols, deps, calls, reads, writes, risk = parse_python(text)
            else:
                symbols, deps, calls, reads, writes, risk = parse_textual(kind, text)
        except Exception as e:
            symbols, deps, calls, reads, writes, risk = [], [], [], [], [], 3.0
            parse_error = f"{type(e).__name__}: {e}"

        tags = []
        if MATH_TOKENS.search(text): tags.append("math")
        if STATE_TOKENS.search(text): tags.append("state")
        low = str(p).lower()
        for tag, needles in {
            "groovebox": ("groovebox",),
            "runtime": ("runtime", "native"),
            "compiler": ("compiler", "translator", "sir", "sbin"),
            "os": ("/sos/", "\\sos\\", "systemd", "rootfs", "boot"),
            "assistant": ("assistant", "agent"),
            "ui": ("ui", "qt", "widget"),
            "audio": ("audio", "synth", "sound"),
            "visual": ("visual", "video", "render"),
            "game": ("game", "world", "npc"),
        }.items():
            if any(n in low for n in needles):
                tags.append(tag)

        return FileRecord(
            path=str(p), suffix=p.suffix, size=len(data), sha256=sha256_bytes(data),
            lines=text.count("\n") + 1, kind=kind,
            symbols=sorted(set(symbols)), deps=sorted(set(deps)),
            calls=sorted(set(calls)), reads=sorted(set(reads)), writes=sorted(set(writes)),
            tags=sorted(set(tags)), risk=round(float(risk), 5), parse_error=parse_error
        )
    except Exception as e:
        return FileRecord(
            path=str(p), suffix=p.suffix, size=0, sha256="", lines=0, kind="error",
            symbols=[], deps=[], calls=[], reads=[], writes=[], tags=[],
            risk=5.0, parse_error=f"{type(e).__name__}: {e}"
        )

def walk_files(project: Path, roots: list[str], whole_tree: bool) -> list[Path]:
    start_points = [project] if whole_tree else [project / r for r in roots if (project / r).exists()]
    seen = []
    for root in start_points:
        if root.is_file():
            seen.append(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".venv")]
            dp = Path(dirpath)
            for fn in filenames:
                p = dp / fn
                if p.suffix in TEXT_SUFFIXES or fn in {"Makefile", "CMakeLists.txt"}:
                    seen.append(p)
    return sorted(set(seen), key=lambda p: str(p))

def resolve_dep(src: Path, dep: str, project: Path, path_index: dict[str, str]) -> Optional[str]:
    dep_norm = dep.strip().strip('"\'')
    candidates = []
    if dep_norm:
        candidates.extend([
            src.parent / dep_norm,
            project / dep_norm,
            src.parent / (dep_norm + ".py"),
            src.parent / (dep_norm + ".sC"),
            src.parent / (dep_norm + ".scode"),
        ])
        module_path = dep_norm.replace(".", "/")
        candidates.extend([
            project / (module_path + ".py"),
            project / module_path / "__init__.py",
            project / (module_path + ".sC"),
            project / (module_path + ".scode"),
        ])
    for c in candidates:
        try:
            r = str(c.resolve())
        except Exception:
            r = str(c)
        if r in path_index:
            return r
    # basename fallback
    base = Path(dep_norm).name
    for k in path_index:
        if Path(k).name == base:
            return k
    return None

def graph_metrics(records: list[FileRecord], project: Path):
    paths = [str(Path(r.path).resolve()) for r in records]
    index = {p: p for p in paths}
    rec_by_path = {str(Path(r.path).resolve()): r for r in records}
    adj = defaultdict(set)
    unresolved = defaultdict(list)

    for p, rec in rec_by_path.items():
        src = Path(p)
        for dep in rec.deps:
            dst = resolve_dep(src, dep, project, index)
            if dst and dst != p:
                adj[p].add(dst)
                adj[dst].add(p)
            elif dep:
                unresolved[p].append(dep)

    degree = {p: len(adj[p]) for p in rec_by_path}
    top_hubs = sorted(
        rec_by_path,
        key=lambda p: (
            degree.get(p, 0),
            len(rec_by_path[p].writes),
            rec_by_path[p].risk,
            rec_by_path[p].lines
        ),
        reverse=True
    )[:50]

    # Radius-2 neighborhood sizes for hub convergence.
    hub_rows = []
    for p in top_hubs:
        r1 = set(adj[p])
        r2 = set(r1)
        for q in r1:
            r2.update(adj[q])
        r2.discard(p)
        rec = rec_by_path[p]
        leverage = degree.get(p, 0) + 0.25 * len(r2) + 0.2 * len(rec.writes)
        semantic = rec.risk + (1.0 if "math" in rec.tags else 0) + (1.0 if "state" in rec.tags else 0)
        priority = (1.0 + semantic) * (1.0 + leverage)
        hub_rows.append({
            "path": os.path.relpath(p, project),
            "degree": degree.get(p, 0),
            "radius2": len(r2),
            "risk": rec.risk,
            "tags": rec.tags,
            "priority": round(priority, 4),
        })
    hub_rows.sort(key=lambda x: x["priority"], reverse=True)

    return adj, unresolved, hub_rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".", help="Project root")
    ap.add_argument("--out", default=".os-decode", help="Output directory")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--whole-tree", action="store_true",
                    help="Scan entire project instead of canonical roots only")
    ap.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS)
    args = ap.parse_args()

    project = Path(args.project).resolve()
    out = (project / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    files = walk_files(project, args.roots, args.whole_tree)
    if not files:
        print("ERROR: no decodable source files found", file=sys.stderr)
        return 2

    print(f"[decode] project: {project}")
    print(f"[decode] files:   {len(files)}")
    print(f"[decode] workers: {args.workers}")

    records = []
    with cf.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, rec in enumerate(ex.map(analyze_one, map(str, files), chunksize=16), 1):
            records.append(rec)
            if i % 100 == 0 or i == len(files):
                print(f"[decode] analyzed {i}/{len(files)}")

    records.sort(key=lambda r: r.path)
    adj, unresolved, hubs = graph_metrics(records, project)

    kind_counts = Counter(r.kind for r in records)
    tag_counts = Counter(t for r in records for t in r.tags)
    parse_errors = [r for r in records if r.parse_error]

    # High-value routing queue: structural risk x connectivity x cross-domain tags.
    route = []
    abs_by_rel = {os.path.relpath(str(Path(r.path).resolve()), project): r for r in records}
    deg = {p: len(adj[p]) for p in adj}
    for r in records:
        p = str(Path(r.path).resolve())
        cross_domain = len(set(r.tags) & {"math","state","runtime","compiler","os","groovebox","audio","visual","game","ui"})
        leverage = deg.get(p, 0) + len(r.writes) * 0.15 + len(r.symbols) * 0.05
        uncertainty = r.risk + (2.0 if r.parse_error else 0.0)
        score = (1 + uncertainty) * (1 + leverage) * (1 + 0.25 * cross_domain)
        if score > 1.0:
            route.append({
                "path": os.path.relpath(p, project),
                "score": round(score, 4),
                "risk": r.risk,
                "degree": deg.get(p, 0),
                "tags": r.tags,
                "symbols": len(r.symbols),
                "writes": len(r.writes),
                "unresolved_deps": unresolved.get(p, [])[:20],
            })
    route.sort(key=lambda x: x["score"], reverse=True)

    payload = {
        "schema": "sos-whole-system-reverse-decode-1.0",
        "project": str(project),
        "files_analyzed": len(records),
        "total_lines": sum(r.lines for r in records),
        "workers": args.workers,
        "kind_counts": dict(kind_counts),
        "tag_counts": dict(tag_counts),
        "parse_error_count": len(parse_errors),
        "edge_count": sum(len(v) for v in adj.values()) // 2,
        "top_hubs": hubs[:30],
        "priority_route": route[:250],
        "records": [
            {
                **asdict(r),
                "path": os.path.relpath(str(Path(r.path).resolve()), project),
            }
            for r in records
        ],
    }

    json_path = out / "OS_DECODE.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    md = []
    md.append("# sOS Whole-System Reverse Decode 1.0\n")
    md.append(f"- Files analyzed: **{payload['files_analyzed']}**")
    md.append(f"- Lines: **{payload['total_lines']}**")
    md.append(f"- Dependency edges: **{payload['edge_count']}**")
    md.append(f"- Parse errors: **{payload['parse_error_count']}**")
    md.append(f"- Workers: **{payload['workers']}**\n")
    md.append("## Highest-leverage hubs\n")
    for h in hubs[:20]:
        md.append(
            f"- `{h['path']}` — priority {h['priority']}, degree {h['degree']}, "
            f"R2 {h['radius2']}, risk {h['risk']}, tags={','.join(h['tags'])}"
        )
    md.append("\n## First 50 routing targets\n")
    for q in route[:50]:
        md.append(
            f"- `{q['path']}` — score {q['score']}, degree {q['degree']}, "
            f"risk {q['risk']}, tags={','.join(q['tags'])}"
        )
    md_path = out / "OS_DECODE.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    # Small task file for an agent/router.
    task = {
        "schema": "sos-decode-routing-task-1.0",
        "goal": (
            "Resolve the highest-leverage whole-system semantic scopes, preserve behavior, "
            "prefer canonical sCode/Infinity-Logic/Meum/OT identities where verified, "
            "and return only test-backed changes."
        ),
        "top_targets": route[:40],
        "hub_context": hubs[:20],
        "required_checks": [
            "cross-resolution agreement",
            "cross-struct agreement",
            "reference behavior where available",
            "no-Python-runtime final gate",
            "native sCode build",
            "sOS service/runtime/compiler wiring",
        ],
    }
    (out / "OS_AGENT_TASK.json").write_text(json.dumps(task, indent=2), encoding="utf-8")

    print(f"[decode] wrote: {json_path}")
    print(f"[decode] wrote: {md_path}")
    print(f"[decode] wrote: {out / 'OS_AGENT_TASK.json'}")
    print("[decode] done")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
