#!/usr/bin/env python3
"""
finish_product.py — sCode/Groovebox/sOS end-to-end conversion factory

Goal
----
Drive a project from a Python-backed Groovebox tree to a *gated* finished
redistributable:

    inspect
      -> reverse-decode
      -> route scopes
      -> translate
      -> resolve semantic tail
      -> differential-test
      -> build native sCode runtime/compiler
      -> build sOS payload
      -> package
      -> declare FINISHED only if every required gate passes

This script is intentionally strict. It will not call a build "finished" just
because files were emitted.

External intelligence
---------------------
If unresolved semantic regions remain, pass --agent-cmd. The command receives
one JSON task file path and must write a JSON result with a unified patch.

Example:
  python finish_product.py \
      --project /path/to/universal_bundle \
      --agent-cmd 'python local_agent.py {task} {result}'

The agent can be sAssistant, another local model, or any deterministic patch
generator. Without --agent-cmd, only mechanical conversion paths are attempted.

The script prefers existing project tools when present:
  Groovebox/tools/reverse_decode_groovebox.py
  sCode/sCode.py
  sOS_COMPILER/sos_compiler.py
  BUILD_COMPILER/*
"""

from __future__ import annotations
import argparse
import ast
import dataclasses
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Optional

MEUM = 1.1975807343385265188313261892683521394620007706106205

# -------- Utilities --------

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def run(cmd, cwd=None, timeout=900, check=False):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    p = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None,
        text=True, capture_output=True, timeout=timeout
    )
    if check and p.returncode != 0:
        raise RuntimeError(
            f"command failed ({p.returncode}): {' '.join(map(str, cmd))}\n"
            f"STDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p

def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

def load_json(p: Path, default=None):
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def copytree_clean(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    ignore = shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", ".mypy_cache", ".git",
        ".venv", "venv", ".groovebox-build-venv", "site-packages",
        "build", "dist",
        ".finish-router", ".finish-all"
    )
    shutil.copytree(src, dst, ignore=ignore)

def unified_patch_apply(root: Path, patch_text: str) -> tuple[bool, str]:
    patch_file = root / ".finish_router.patch"
    patch_file.write_text(patch_text, encoding="utf-8")
    try:
        p = run(["patch", "-p1", "-i", str(patch_file)], cwd=root)
        return p.returncode == 0, p.stdout + p.stderr
    finally:
        patch_file.unlink(missing_ok=True)

# -------- Structural decode --------

@dataclasses.dataclass
class Fn:
    qualname: str
    lineno: int
    end_lineno: int
    calls: list[str]
    reads: list[str]
    writes: list[str]
    tags: list[str]
    risk: int

TAGS = {
    "seed": ("seed", "rng", "random"),
    "canonical": ("canonical", "identity", "playlist", "fingerprint"),
    "audio": ("audio", "synth", "voice", "render", "mix", "sample"),
    "visual": ("visual", "video", "scene", "geometry", "frame"),
    "game": ("game", "world", "npc", "terrain", "player"),
    "save": ("save", "load", "serialize", "project"),
    "ui": ("ui", "widget", "window", "button", "slider", "dialog"),
    "math": ("meum", "isn", "ics", "phase", "theta", "operator", "ot_"),
}

class Visitor(ast.NodeVisitor):
    def __init__(self, source_lines):
        self.source_lines = source_lines
        self.stack = []
        self.functions = []

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        self._fn(node)

    def visit_AsyncFunctionDef(self, node):
        self._fn(node)

    def _fn(self, node):
        qual = ".".join(self.stack + [node.name])
        calls, reads, writes = set(), set(), set()
        branches = loops = raises = dynamic = 0

        class F(ast.NodeVisitor):
            def visit_Call(self, n):
                nonlocal dynamic
                name = None
                if isinstance(n.func, ast.Name):
                    name = n.func.id
                elif isinstance(n.func, ast.Attribute):
                    parts = []
                    q = n.func
                    while isinstance(q, ast.Attribute):
                        parts.append(q.attr)
                        q = q.value
                    if isinstance(q, ast.Name):
                        parts.append(q.id)
                    name = ".".join(reversed(parts))
                if name:
                    calls.add(name)
                    if name in {"eval","exec","getattr","setattr","globals","locals","__import__"}:
                        dynamic += 2
                self.generic_visit(n)

            def visit_Attribute(self, n):
                if isinstance(n.value, ast.Name) and n.value.id == "self":
                    if isinstance(n.ctx, ast.Store):
                        writes.add(n.attr)
                    else:
                        reads.add(n.attr)
                self.generic_visit(n)

            def visit_If(self, n):
                nonlocal branches
                branches += 1
                self.generic_visit(n)

            def visit_For(self, n):
                nonlocal loops
                loops += 1
                self.generic_visit(n)

            def visit_While(self, n):
                nonlocal loops
                loops += 1
                self.generic_visit(n)

            def visit_Raise(self, n):
                nonlocal raises
                raises += 1
                self.generic_visit(n)

        F().visit(node)
        text = "\n".join(self.source_lines[node.lineno-1:getattr(node, "end_lineno", node.lineno)])
        low = text.lower()
        tags = [k for k, vals in TAGS.items() if any(v.lower() in low for v in vals)]
        risk = branches + 2*loops + 3*raises + dynamic
        self.functions.append(Fn(
            qualname=qual,
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            calls=sorted(calls),
            reads=sorted(reads),
            writes=sorted(writes),
            tags=tags,
            risk=risk,
        ))
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

def decode_python(py: Path):
    src = py.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src, filename=str(py))
    v = Visitor(src.splitlines())
    v.visit(tree)
    return v.functions

def build_shared_state_graph(functions):
    writers = defaultdict(set)
    readers = defaultdict(set)
    for f in functions:
        for x in f.writes: writers[x].add(f.qualname)
        for x in f.reads: readers[x].add(f.qualname)

    edges = defaultdict(set)
    for state in set(writers) | set(readers):
        nodes = writers[state] | readers[state]
        for a in nodes:
            for b in nodes:
                if a != b:
                    edges[a].add(b)
    return edges

def choose_scopes(functions, edges, limit=48):
    # Intelligent routing score:
    # uncertainty/risk × shared-state leverage × semantic convergence.
    fn_by = {f.qualname:f for f in functions}
    scored = []
    for f in functions:
        leverage = len(edges.get(f.qualname, ()))
        cross = len(set(f.tags) & {"audio","visual","game","save","canonical","seed"})
        math = 1 if "math" in f.tags else 0
        score = (1 + f.risk) * (1 + leverage) * (1 + cross + math)
        scored.append((score, f.qualname))
    scored.sort(reverse=True)
    return [fn_by[name] for _, name in scored[:limit]]

# -------- Mechanical conversion hooks --------

def discover(root: Path):
    return {
        "groovebox": root / "Groovebox",
        "scode": root / "sCode",
        "sos": root / "sOS",
        "sos_compiler": root / "sOS_COMPILER" / "sos_compiler.py",
        "reverse_decoder": root / "Groovebox" / "tools" / "reverse_decode_groovebox.py",
        "groovebox_py": root / "Groovebox" / "groovebox.py",
        "groovebox_sc": root / "Groovebox" / "groovebox.sC",
        "scode_driver": root / "sCode" / "sCode.py",
    }

def run_reverse_decoder(paths, state_dir):
    tool = paths["reverse_decoder"]
    if not tool.exists():
        return {"status":"missing","tool":str(tool)}
    out = state_dir / "reverse_decode"
    out.mkdir(parents=True, exist_ok=True)
    p = run([
        sys.executable, str(tool),
        "--source", str(paths["groovebox_py"]),
        "--resolution", "8",
        "--out", str(out)
    ], cwd=paths["groovebox"])
    return {"status":"pass" if p.returncode == 0 else "fail",
            "returncode":p.returncode, "stdout":p.stdout[-10000:], "stderr":p.stderr[-10000:]}

def try_existing_translation(paths, state_dir):
    """
    Prefer project-native translation tools. We do not guess compiler CLI
    semantics beyond the existing `compile` path when available.
    """
    driver = paths["scode_driver"]
    src = paths["groovebox_sc"]
    if not driver.exists():
        return {"status":"missing","reason":"sCode.py missing"}
    if not src.exists():
        return {"status":"missing","reason":"groovebox.sC missing"}
    out = state_dir / "compile"
    out.mkdir(parents=True, exist_ok=True)
    p = run([sys.executable, str(driver), "compile", str(src)], cwd=paths["scode"])
    return {"status":"pass" if p.returncode==0 else "fail",
            "returncode":p.returncode,"stdout":p.stdout[-10000:],"stderr":p.stderr[-10000:]}

# -------- Agent semantic-tail loop --------

def make_agent_task(root, groovebox_py, scopes, attempt, state_dir):
    src_lines = groovebox_py.read_text(encoding="utf-8", errors="replace").splitlines()
    samples = []
    for s in scopes:
        start = max(1, s.lineno - 8)
        end = min(len(src_lines), s.end_lineno + 8)
        samples.append({
            "qualname":s.qualname,
            "lineno":s.lineno,
            "end_lineno":s.end_lineno,
            "tags":s.tags,
            "risk":s.risk,
            "reads":s.reads,
            "writes":s.writes,
            "calls":s.calls,
            "source":"\n".join(src_lines[start-1:end]),
        })

    return {
        "task":"resolve_semantic_tail_for_scode_conversion",
        "attempt":attempt,
        "project_root":str(root),
        "requirements":{
            "preserve_behavior":True,
            "seed_is_root_identity":True,
            "canonical_state_shared_across_audio_visual_game":True,
            "time_representation":"imaginary-time is user-theory representation where project specifies it",
            "preferred_math_basis":[
                "M","M-1","1/M","isn","ics","phase","OT","canonical identity"
            ],
            "rule":"do not change semantics merely to make tests pass",
            "output":"JSON containing unified_patch and explanation"
        },
        "scopes":samples,
    }

def call_agent(agent_cmd, task_path, result_path, root):
    cmd = agent_cmd.format(task=shlex.quote(str(task_path)), result=shlex.quote(str(result_path)))
    p = subprocess.run(cmd, shell=True, cwd=str(root), text=True, capture_output=True)
    if p.returncode != 0:
        return False, p.stdout + p.stderr
    if not result_path.exists():
        return False, "agent returned success but did not create result JSON"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"invalid agent JSON: {e}"
    patch = result.get("unified_patch","")
    if not patch.strip():
        return False, "agent result has no unified_patch"
    ok, detail = unified_patch_apply(root, patch)
    return ok, detail

# -------- Validation gates --------

def gate_python_syntax(paths):
    targets = [p for p in [
        paths["groovebox_py"],
        paths["groovebox"] / "run_groovebox.py",
        paths["scode_driver"],
        paths["sos_compiler"],
    ] if p.exists()]
    if not targets:
        return {"name":"python_syntax","status":"skip"}
    p = run([sys.executable, "-m", "py_compile", *map(str, targets)])
    return {"name":"python_syntax","status":"pass" if p.returncode==0 else "fail",
            "stdout":p.stdout[-5000:],"stderr":p.stderr[-5000:]}

def gate_regressions(paths):
    tests = [
        paths["groovebox"]/x for x in (
            "test_ot_symbol_notation.py",
            "test_visual_determinism.py",
            "test_composition_parity.py",
            "test_scode.py",
        )
    ]
    tests = [x for x in tests if x.exists()]
    if not tests:
        return {"name":"regressions","status":"skip","reason":"no selected tests found"}
    p = run([sys.executable,"-m","pytest","-q",*map(str,tests)],
            cwd=paths["groovebox"], timeout=1800)
    return {"name":"regressions","status":"pass" if p.returncode==0 else "fail",
            "stdout":p.stdout[-12000:],"stderr":p.stderr[-12000:]}

def gate_no_python_runtime(paths):
    """
    Final-product gate: the *shipping runtime path* must not require Python.
    Python source may remain in a SOURCE_REFERENCE directory if desired, but
    final launch path must resolve through sbin/sCode native runtime.
    """
    native_candidates = [
        paths["groovebox"]/"groovebox.sbin",
        paths["scode"]/"bin"/"scode-native",
        paths["scode"]/"bin"/"scode-native.exe",
    ]
    if (paths["groovebox"]/"groovebox.sbin").exists() and any(p.exists() for p in native_candidates[1:]):
        return {"name":"no_python_runtime","status":"pass"}
    return {"name":"no_python_runtime","status":"fail",
            "reason":"native groovebox.sbin and native sCode runtime are not both present"}

def gate_sos(paths, root):
    if not paths["sos_compiler"].exists():
        return {"name":"sos_compiler","status":"fail","reason":"missing sOS compiler"}
    p = run([sys.executable,str(paths["sos_compiler"]),"--root",str(root)])
    return {"name":"sos_compiler","status":"pass" if p.returncode==0 else "fail",
            "stdout":p.stdout[-10000:],"stderr":p.stderr[-10000:]}

def build_native_scode(root, paths):
    host = platform.system()
    if host == "Linux":
        script = root/"BUILD_COMPILER"/"build_linux.sh"
        cmd = ["bash",str(script)]
    elif host == "Darwin":
        script = root/"BUILD_COMPILER"/"build_macos.sh"
        cmd = ["bash",str(script)]
    elif host == "Windows":
        script = root/"BUILD_COMPILER"/"build_windows.ps1"
        cmd = ["powershell","-ExecutionPolicy","Bypass","-File",str(script)]
    else:
        return {"name":"native_scode_build","status":"fail","reason":f"unsupported host {host}"}
    if not script.exists():
        return {"name":"native_scode_build","status":"fail","reason":f"missing {script}"}
    p = run(cmd, cwd=root, timeout=1800)
    return {"name":"native_scode_build","status":"pass" if p.returncode==0 else "fail",
            "stdout":p.stdout[-10000:],"stderr":p.stderr[-10000:]}

# -------- Packaging --------

def manifest_tree(root: Path):
    m = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".finish-router" not in p.parts:
            m[str(p.relative_to(root))] = sha256_file(p)
    return m

def package_finished(root: Path, dist: Path):
    dist.mkdir(parents=True, exist_ok=True)
    name = "MathematiciansGroovebox_sCode_sOS_FINISHED"
    zip_path = dist / f"{name}.zip"
    tar_path = dist / f"{name}.tar.gz"
    manifest = dist / f"{name}.sha256.json"

    write_json(manifest, manifest_tree(root))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file() and ".finish-router" not in p.parts:
                z.write(p, Path(name)/p.relative_to(root))

    with tarfile.open(tar_path, "w:gz") as t:
        for p in sorted(root.rglob("*")):
            if ".finish-router" not in p.parts:
                t.add(p, arcname=Path(name)/p.relative_to(root), recursive=False)

    return {
        "zip":str(zip_path),"zip_sha256":sha256_file(zip_path),
        "tar_gz":str(tar_path),"tar_sha256":sha256_file(tar_path),
        "manifest":str(manifest),
    }

# -------- Main pipeline --------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True,
                    help="Root containing Groovebox/, sCode/, sOS/, BUILD_COMPILER/")
    ap.add_argument("--work", default=None,
                    help="Work copy destination; default <project>/.finish-router/work")
    ap.add_argument("--dist", default=None,
                    help="Distribution output; default <project>/dist")
    ap.add_argument("--agent-cmd", default=None,
                    help="External patch agent command template with {task} and {result}")
    ap.add_argument("--max-agent-attempts", type=int, default=12)
    ap.add_argument("--scope-limit", type=int, default=48)
    ap.add_argument("--allow-source-reference-python", action="store_true",
                    help="Keep Python only as non-runtime SOURCE_REFERENCE material")
    ap.add_argument("--in-place", action="store_true",
                    help="Operate directly on project instead of a work copy")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    state = project / ".finish-router"
    state.mkdir(parents=True, exist_ok=True)

    if args.in_place:
        work = project
    else:
        work = Path(args.work).resolve() if args.work else state/"work"
        # The work tree is a cache, not authority.  Older interrupted router
        # runs may have created an incomplete/stale work directory.  Refresh
        # it whenever the canonical Groovebox source is absent there.
        canonical_source = project / "Groovebox" / "groovebox.py"
        cached_source = work / "Groovebox" / "groovebox.py"
        if not work.exists() or (canonical_source.is_file() and not cached_source.is_file()):
            copytree_clean(project, work)

    dist = Path(args.dist).resolve() if args.dist else project/"dist"
    paths = discover(work)

    if not paths["groovebox_py"].exists():
        print("ERROR: Groovebox/groovebox.py not found", file=sys.stderr)
        return 2

    report = {
        "started":time.time(),
        "project":str(project),
        "work":str(work),
        "phases":[],
    }

    # 1. Decode.
    funcs = decode_python(paths["groovebox_py"])
    edges = build_shared_state_graph(funcs)
    scopes = choose_scopes(funcs, edges, args.scope_limit)

    decode_summary = {
        "functions":len(funcs),
        "shared_state_edges":sum(len(v) for v in edges.values()),
        "priority_scopes":[
            {"qualname":s.qualname,"risk":s.risk,"tags":s.tags,
             "reads":s.reads[:12],"writes":s.writes[:12]}
            for s in scopes
        ],
    }
    write_json(state/"decode_summary.json", decode_summary)
    report["phases"].append({"decode":decode_summary})

    # 2. Existing reverse decoder.
    rev = run_reverse_decoder(paths, state)
    report["phases"].append({"reverse_decoder":rev})

    # 3. Existing translator/compiler attempt.
    trans = try_existing_translation(paths, state)
    report["phases"].append({"existing_translation":trans})

    # 4. Build native runtime/compiler.
    native = build_native_scode(work, paths)
    report["phases"].append({"native_build":native})

    # 5. Iterate validation + semantic repair.
    for attempt in range(args.max_agent_attempts + 1):
        gates = [
            gate_python_syntax(paths),
            gate_regressions(paths),
            gate_sos(paths, work),
            gate_no_python_runtime(paths),
        ]

        failed = [g for g in gates if g["status"] == "fail"]
        report["phases"].append({"attempt":attempt,"gates":gates})
        write_json(state/"latest_report.json", report)

        if not failed:
            # Optional source-only archival move. Runtime path is already native.
            if args.allow_source_reference_python:
                ref = work/"SOURCE_REFERENCE"
                ref.mkdir(exist_ok=True)
                for p in [paths["groovebox_py"], paths["groovebox"]/"run_groovebox.py"]:
                    if p.exists():
                        shutil.copy2(p, ref/p.name)

            pkg = package_finished(work, dist)
            finished = {
                "status":"FINISHED",
                "finished_at":time.time(),
                "gates":gates,
                "artifacts":pkg,
            }
            write_json(state/"FINISHED.json", finished)
            print(json.dumps(finished, indent=2))
            return 0

        # If only missing native sbin is the blocker, retry native translation.
        trans = try_existing_translation(paths, state)
        report["phases"].append({"translation_retry":trans})

        # Re-run gate after translation retry on next loop.
        if not args.agent_cmd:
            break

        # Ask agent to resolve the highest-leverage semantic regions.
        task = make_agent_task(work, paths["groovebox_py"], scopes, attempt, state)
        task_path = state/f"agent_task_{attempt:02d}.json"
        result_path = state/f"agent_result_{attempt:02d}.json"
        write_json(task_path, task)

        # Snapshot source before applying external patch.
        checkpoint = state/f"checkpoint_{attempt:02d}"
        if checkpoint.exists():
            shutil.rmtree(checkpoint)
        checkpoint.mkdir()
        for p in [paths["groovebox_py"], paths["groovebox_sc"]]:
            if p.exists():
                shutil.copy2(p, checkpoint/p.name)

        ok, detail = call_agent(args.agent_cmd, task_path, result_path, work)
        report["phases"].append({"agent_attempt":attempt,"applied":ok,"detail":detail[-8000:]})
        if not ok:
            break

        # Fail-fast syntax after patch; rollback if damaged.
        py_gate = gate_python_syntax(paths)
        if py_gate["status"] == "fail":
            for saved in checkpoint.iterdir():
                if saved.name == "groovebox.py":
                    shutil.copy2(saved, paths["groovebox_py"])
                elif saved.name == "groovebox.sC":
                    shutil.copy2(saved, paths["groovebox_sc"])
            report["phases"].append({"rollback":attempt,"reason":"syntax failure"})
            break

        # Re-decode after every semantic patch so routing follows new structure.
        funcs = decode_python(paths["groovebox_py"])
        edges = build_shared_state_graph(funcs)
        scopes = choose_scopes(funcs, edges, args.scope_limit)

    # Not finished.
    gates = [
        gate_python_syntax(paths),
        gate_regressions(paths),
        gate_sos(paths, work),
        gate_no_python_runtime(paths),
    ]
    unfinished = {
        "status":"NOT_FINISHED",
        "reason":"one or more required gates remain unresolved",
        "failed_gates":[g for g in gates if g["status"]=="fail"],
        "next_action":"supply --agent-cmd or extend mechanical translation rules, then rerun",
        "work_tree":str(work),
        "state_dir":str(state),
    }
    write_json(state/"NOT_FINISHED.json", unfinished)
    print(json.dumps(unfinished, indent=2))
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
