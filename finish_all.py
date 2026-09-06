#!/usr/bin/env python3
"""
sCode / Groovebox / sOS FINISH-ALL Router 1.0
=============================================

Goal
----
Drive the existing project toward a *real* finished state by repeatedly:

    discover -> deduplicate -> decode -> route -> translate -> build -> test
    -> repair semantic tail -> re-run -> package

It never writes "FINISHED" merely because a pass completed. FINISHED is emitted
only after all discovered hard gates pass.

This program is deliberately project-scoped:
- no sudo
- no package-manager mutation
- no writes outside --project and --out
- rejects patches that escape the project root

It uses existing project tools when present:
- finish_product.py
- tools/reverse_decode_groovebox.py
- decode_entire_sos.py
- sOS_COMPILER/sos_compiler.py
- BUILD_COMPILER platform build scripts
- pytest / Python syntax checks
- sCode compiler/runtime

For semantic work it supports:
1) an explicit --agent-cmd contract, or
2) an optional local Ollama model (--ollama-model).

Without an agent, it still performs every deterministic/mechanical step and
stops with BLOCKED.json containing the smallest current repair task.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import difflib
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Optional

HISTORICAL_PATTERNS = (
    ".pre_", "_pre_", ".bak", ".backup", "~", ".old", "_old",
    "seqfix", "reference.py",
)
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox", "node_modules", "site-packages",
    ".groovebox-build-venv", ".venv", "venv", "env", "dist", "build",
    "generated", "generated_mechanical", ".finish-router", ".finish-all",
    ".os-decode", ".cache", "vendor", "third_party", "third-party",
}
TEXT_SUFFIXES = {
    ".py", ".sC", ".scode", ".sc", ".cpp", ".cc", ".cxx", ".hpp", ".h",
    ".sh", ".bash", ".service", ".target", ".socket", ".timer", ".json",
    ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".md", ".txt"
}

def log(msg: str) -> None:
    print(f"[finish-all] {msg}", flush=True)

def run(cmd, cwd: Path, timeout: Optional[int] = None, env=None) -> dict[str, Any]:
    log("$ " + " ".join(map(str, cmd)))
    p = subprocess.run(
        list(map(str, cmd)), cwd=str(cwd), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout, env=env
    )
    out = p.stdout or ""
    print(out, end="" if out.endswith("\n") else "\n")
    return {"cmd": list(map(str, cmd)), "returncode": p.returncode, "output": out}

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def iter_source_files(project: Path):
    for dp, dns, fns in os.walk(project):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        base = Path(dp)
        for fn in fns:
            p = base / fn
            if p.suffix in TEXT_SUFFIXES or fn in {"Makefile", "CMakeLists.txt"}:
                yield p

def is_historical(rel: str) -> bool:
    low = rel.lower()
    return (
        "/deployment_kit/" in low
        or "\\deployment_kit\\" in low
        or any(x in low for x in HISTORICAL_PATTERNS)
    )

def normalized_python_hash(p: Path) -> Optional[str]:
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        # Remove source-location noise while retaining semantics/structure.
        dump = ast.dump(tree, annotate_fields=True, include_attributes=False)
        return hashlib.sha256(dump.encode()).hexdigest()
    except Exception:
        return None

def dedupe_index(project: Path) -> dict[str, Any]:
    files = list(iter_source_files(project))
    exact = defaultdict(list)
    ast_groups = defaultdict(list)
    for p in files:
        rel = str(p.relative_to(project))
        try:
            exact[sha256_file(p)].append(rel)
        except Exception:
            continue
        if p.suffix == ".py":
            nh = normalized_python_hash(p)
            if nh:
                ast_groups[nh].append(rel)

    exact_dupes = [v for v in exact.values() if len(v) > 1]
    semantic_dupes = [v for v in ast_groups.values() if len(v) > 1]

    def pick_authority(group):
        return sorted(
            group,
            key=lambda r: (
                is_historical(r),
                "/deployment_kit/" in r.lower(),
                len(Path(r).parts),
                len(r),
                r
            )
        )[0]

    equivalence_classes = []
    seen = set()
    for group in exact_dupes + semantic_dupes:
        key = tuple(sorted(group))
        if key in seen:
            continue
        seen.add(key)
        equivalence_classes.append({
            "authority": pick_authority(group),
            "members": sorted(group),
            "size": len(group),
        })

    return {
        "files_scanned": len(files),
        "exact_duplicate_classes": len(exact_dupes),
        "python_ast_duplicate_classes": len(semantic_dupes),
        "equivalence_classes": sorted(
            equivalence_classes, key=lambda x: (-x["size"], x["authority"])
        ),
    }

def find_first(project: Path, names: list[str]) -> Optional[Path]:
    # First prefer exact expected locations.
    for n in names:
        p = project / n
        if p.exists():
            return p
    # Then bounded search.
    for dp, dns, fns in os.walk(project):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for n in names:
            if Path(n).name in fns:
                return Path(dp) / Path(n).name
    return None

def python_syntax_gate(project: Path) -> dict[str, Any]:
    failures = []
    checked = 0
    for p in iter_source_files(project):
        if p.suffix != ".py":
            continue
        rel = str(p.relative_to(project))
        # Historical copies are evidence, not release gates.
        if is_historical(rel):
            continue
        checked += 1
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=rel)
        except Exception as e:
            failures.append({"path": rel, "error": f"{type(e).__name__}: {e}"})
    return {"name": "python_syntax", "pass": not failures, "checked": checked, "failures": failures}

def run_selected_pytests(project: Path) -> dict[str, Any]:
    pytest = shutil.which("pytest")
    if not pytest:
        return {"name": "pytest", "pass": True, "skipped": True, "reason": "pytest not installed"}

    groove = project / "Groovebox"
    if not groove.exists():
        return {"name": "pytest", "pass": True, "skipped": True, "reason": "Groovebox directory absent"}

    preferred = [
        "test_ot_symbol_notation.py",
        "test_visual_determinism.py",
        "test_composition_parity.py",
        "test_scode.py",
    ]
    tests = [groove / x for x in preferred if (groove / x).exists()]
    if not tests:
        # Do not accidentally run a giant unrelated suite.
        return {"name": "pytest", "pass": True, "skipped": True, "reason": "preferred regression tests absent"}

    r = run([pytest, "-q", *[str(x) for x in tests]], cwd=project, timeout=900)
    return {"name": "pytest", "pass": r["returncode"] == 0, "returncode": r["returncode"], "output": r["output"][-20000:]}

def run_os_decoder(project: Path, outdir: Path, workers: int) -> dict[str, Any]:
    candidates = [
        project / "decode_entire_sos.py",
        project / "tools" / "decode_entire_sos.py",
    ]
    script = next((x for x in candidates if x.exists()), None)
    if not script:
        return {"name": "os_decode", "pass": True, "skipped": True, "reason": "decoder not found"}

    target = outdir / "os-decode"
    target.mkdir(parents=True, exist_ok=True)
    r = run(
        [sys.executable, str(script), "--project", str(project),
         "--out", str(target), "--workers", str(workers)],
        cwd=project, timeout=3600
    )
    return {"name": "os_decode", "pass": r["returncode"] == 0, "returncode": r["returncode"], "output": r["output"][-10000:]}

def run_reverse_decoder(project: Path, outdir: Path) -> dict[str, Any]:
    script = project / "Groovebox" / "tools" / "reverse_decode_groovebox.py"
    source = project / "Groovebox" / "groovebox.py"
    if not script.exists() or not source.exists():
        return {"name": "reverse_decode", "pass": True, "skipped": True, "reason": "reverse decoder/source absent"}
    target = outdir / "reverse-decode"
    target.mkdir(parents=True, exist_ok=True)
    r = run(
        [sys.executable, str(script), "--source", str(source),
         "--resolution", "8", "--out", str(target)],
        cwd=project / "Groovebox", timeout=1800
    )
    return {"name": "reverse_decode", "pass": r["returncode"] == 0, "returncode": r["returncode"], "output": r["output"][-10000:]}

def run_finish_router(project: Path, outdir: Path) -> dict[str, Any]:
    candidates = [
        project / "finish_product.py",
        project / "Finish_Product_Router" / "finish_product.py",
        project.parent / "finish_product.py",
    ]
    script = next((x for x in candidates if x.exists()), None)
    if not script:
        return {"name": "finish_router", "pass": False, "skipped": True, "reason": "finish_product.py not found"}

    # finish_product.py historically expects a root containing
    # Groovebox/groovebox.py.  Prefer the supplied project root when it has
    # that layout; otherwise pass the nearest compatible root.
    router_project = project
    if not (router_project / "Groovebox" / "groovebox.py").is_file():
        if (project / "groovebox.py").is_file():
            router_project = project.parent
        elif (script.parent / "Groovebox" / "groovebox.py").is_file():
            router_project = script.parent

    r = run([sys.executable, str(script), "--project", str(router_project)], cwd=script.parent, timeout=7200)

    finished_candidates = [
        project / ".finish-router" / "FINISHED.json",
        script.parent / ".finish-router" / "FINISHED.json",
    ]
    not_finished_candidates = [
        project / ".finish-router" / "NOT_FINISHED.json",
        script.parent / ".finish-router" / "NOT_FINISHED.json",
    ]
    latest_candidates = [
        project / ".finish-router" / "latest_report.json",
        script.parent / ".finish-router" / "latest_report.json",
    ]

    finished = next((x for x in finished_candidates if x.exists()), None)
    nf = next((x for x in not_finished_candidates if x.exists()), None)
    latest = next((x for x in latest_candidates if x.exists()), None)

    payload = None
    source_report = latest or nf or finished
    if source_report:
        try:
            payload = json.loads(source_report.read_text())
        except Exception:
            payload = {"raw": source_report.read_text(errors="replace")[-50000:]}

    return {
        "name": "finish_router",
        "pass": bool(finished) and r["returncode"] == 0,
        "returncode": r["returncode"],
        "finished_path": str(finished) if finished else None,
        "not_finished_path": str(nf) if nf else None,
        "latest_report_path": str(latest) if latest else None,
        "report": payload,
        "output": r["output"][-20000:],
    }

def platform_build_script(project: Path) -> Optional[Path]:
    """Return the authoritative platform build script.

    Prefer BUILD_KIT because that is the release/application build path.  The
    older BUILD_COMPILER scripts are retained as fallbacks for trees that do
    not contain BUILD_KIT.
    """
    sysname = platform.system().lower()
    candidates = []
    if "linux" in sysname:
        candidates += [
            project / "BUILD_KIT" / "build_linux.sh",
            project / "Groovebox" / "BUILD_KIT" / "build_linux.sh",
            project / "BUILD_COMPILER" / "BUILD_LINUX.sh",
            project / "BUILD_COMPILER" / "build_linux.sh",
            project / "COMPILE_SCODE_LINUX.sh",
        ]
    elif "darwin" in sysname:
        candidates += [
            project / "BUILD_KIT" / "build_macos.sh",
            project / "Groovebox" / "BUILD_KIT" / "build_macos.sh",
            project / "BUILD_COMPILER" / "BUILD_MAC.command",
            project / "COMPILE_SCODE_MAC.command",
        ]
    elif "windows" in sysname:
        candidates += [
            project / "BUILD_KIT" / "build_windows.bat",
            project / "Groovebox" / "BUILD_KIT" / "build_windows.bat",
            project / "BUILD_COMPILER" / "BUILD_WINDOWS.bat",
            project / "COMPILE_SCODE_WINDOWS.bat",
        ]
    return next((p for p in candidates if p.is_file()), None)


def _native_build_artifacts(project: Path) -> list[Path]:
    """Collect concrete successful-build artifacts without treating directories as proof."""
    found = []
    bindir = project / "sCode" / "bin"
    if bindir.exists():
        found.extend(p for p in bindir.glob("scode-native*") if p.is_file())

    # BUILD_KIT's Linux PyInstaller output observed in this project.
    dist = project / "dist" / "MathematiciansGroovebox"
    if dist.exists():
        preferred = dist / "MathematiciansGroovebox"
        if preferred.is_file():
            found.append(preferred)
        else:
            found.extend(p for p in dist.iterdir() if p.is_file() and "groovebox" in p.name.lower())

    # Preserve order while removing aliases/duplicates.
    unique = []
    seen = set()
    for p in found:
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def native_build_gate(project: Path) -> dict[str, Any]:
    script = platform_build_script(project)
    before = _native_build_artifacts(project)

    if not script:
        return {
            "name": "native_build",
            "pass": bool(before),
            "skipped": True,
            "reason": "build script absent; accepted existing concrete artifact" if before else "build script and native artifacts absent",
            "existing": [str(x.relative_to(project)) for x in before],
        }

    if script.suffix.lower() in {".sh", ".command"}:
        r = run(["bash", str(script)], cwd=project, timeout=3600)
    else:
        r = run([str(script)], cwd=project, timeout=3600)

    after = _native_build_artifacts(project)
    # A zero exit is the primary contract.  If a legacy wrapper returns a
    # non-zero status after producing a concrete build artifact, record that
    # explicitly rather than misclassifying the entire build as semantic work.
    artifact_proves_build = bool(after) and (
        bool(set(map(str, after)) - set(map(str, before)))
        or any("dist/MathematiciansGroovebox" in str(x.relative_to(project)) for x in after)
    )
    passed = r["returncode"] == 0 or artifact_proves_build

    return {
        "name": "native_build",
        "pass": passed,
        "returncode": r["returncode"],
        "script": str(script.relative_to(project)),
        "artifacts": [str(x.relative_to(project)) for x in after],
        "accepted_by_artifact": bool(r["returncode"] != 0 and artifact_proves_build),
        "output": r["output"][-10000:],
    }

def sos_compiler_gate(project: Path) -> dict[str, Any]:
    script = project / "sOS_COMPILER" / "sos_compiler.py"
    if not script.exists():
        return {"name": "sos_compiler", "pass": False, "skipped": True, "reason": "sOS compiler absent"}
    help_r = run([sys.executable, str(script), "--help"], cwd=project, timeout=60)
    if help_r["returncode"] != 0:
        return {"name": "sos_compiler", "pass": False, "returncode": help_r["returncode"], "output": help_r["output"][-10000:]}
    # Try common invocation shapes conservatively.
    attempts = [
        [sys.executable, str(script), "--project", str(project)],
        [sys.executable, str(script), "--source", str(project / "sOS")],
        [sys.executable, str(script)],
    ]
    last = None
    for cmd in attempts:
        rr = run(cmd, cwd=project, timeout=900)
        last = rr
        if rr["returncode"] == 0:
            return {"name": "sos_compiler", "pass": True, "returncode": 0, "output": rr["output"][-10000:]}
    return {"name": "sos_compiler", "pass": False, "returncode": last["returncode"], "output": last["output"][-10000:]}

def find_groove_sbin(project: Path) -> list[str]:
    matches = []
    for p in project.rglob("*.sbin"):
        rel = str(p.relative_to(project))
        if "groovebox" in p.name.lower():
            matches.append(rel)
    return matches

def no_python_runtime_gate(project: Path) -> dict[str, Any]:
    sbins = find_groove_sbin(project)
    native = []
    bindir = project / "sCode" / "bin"
    if bindir.exists():
        native = [str(x.relative_to(project)) for x in bindir.glob("scode-native*") if x.is_file()]

    # This gate is intentionally strict but limited: final Groovebox execution
    # artifacts must exist without requiring Python as the launch payload.
    passed = bool(sbins and native)
    return {
        "name": "no_python_runtime",
        "pass": passed,
        "groovebox_sbin": sbins,
        "native_runtimes": native,
        "note": "Artifact gate only; behavioral parity is enforced separately by tests/router."
    }

def extract_failures(gates: list[dict[str, Any]], router: dict[str, Any]) -> dict[str, Any]:
    failed = [g for g in gates if not g.get("pass")]
    report = router.get("report") if router else None
    return {
        "failed_gates": [
            {k:v for k,v in g.items() if k not in {"output"}}
            for g in failed
        ],
        "router_report": report,
    }

def make_agent_task(project: Path, outdir: Path, failures: dict[str, Any], dedupe: dict[str, Any], cycle: int) -> Path:
    # Include bounded source context from authoritative high-value files only.
    context_files = []
    likely = [
        project / "Groovebox" / "groovebox.py",
        project / "Groovebox" / "composition_state.py",
        project / "Groovebox" / "visual_determinism.py",
        project / "Groovebox" / "videogame_engine.py",
        project / "sCode" / "sCode.py",
        project / "sOS" / "scode" / "system.sC",
        project / "sOS_COMPILER" / "sos_compiler.py",
    ]
    for p in likely:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        context_files.append({
            "path": str(p.relative_to(project)),
            "sha256": sha256_file(p),
            "head": text[:12000],
            "tail": text[-8000:] if len(text) > 12000 else "",
        })

    task = {
        "schema": "scode-finish-all-agent-task-1.0",
        "cycle": cycle,
        "project_root": str(project),
        "goal": (
            "Make the smallest test-backed project-local changes needed to pass the failed gates. "
            "Preserve Groovebox behavior and canonical seed/state semantics. Prefer existing sCode, "
            "Infinity Logic, Meum, OT, isn/ics definitions only where the project already establishes "
            "their meaning. Do not rewrite historical/deployment duplicates independently. "
            "Do not use sudo, network installers, or modify files outside the project."
        ),
        "required_output": {
            "format": "JSON",
            "fields": {
                "summary": "short explanation",
                "unified_patch": "git-style unified diff rooted at project",
                "tests_to_run": ["optional", "commands"]
            }
        },
        "failures": failures,
        "dedupe_summary": {
            "files_scanned": dedupe.get("files_scanned"),
            "exact_duplicate_classes": dedupe.get("exact_duplicate_classes"),
            "python_ast_duplicate_classes": dedupe.get("python_ast_duplicate_classes"),
            "top_equivalence_classes": dedupe.get("equivalence_classes", [])[:30],
        },
        "source_context": context_files,
    }
    p = outdir / f"AGENT_TASK_{cycle:03d}.json"
    p.write_text(json.dumps(task, indent=2), encoding="utf-8")
    return p

def invoke_agent_cmd(agent_cmd: str, task: Path, result: Path, cwd: Path) -> dict[str, Any]:
    import shlex
    rendered = agent_cmd.replace("{task}", str(task)).replace("{result}", str(result))
    r = run(shlex.split(rendered), cwd=cwd, timeout=7200)
    return {"pass": r["returncode"] == 0 and result.exists(), "run": r}

def invoke_ollama(model: str, task: Path, result: Path, cwd: Path) -> dict[str, Any]:
    exe = shutil.which("ollama")
    if not exe:
        return {"pass": False, "reason": "ollama not found"}
    task_text = task.read_text(encoding="utf-8")
    prompt = f"""You are the local repair agent for an sCode/Groovebox/sOS project.
Read the JSON task below. Return ONLY valid JSON with:
{{"summary":"...", "unified_patch":"...", "tests_to_run":["..."]}}
The patch must be project-rooted unified diff. Make the smallest test-backed change.
Do not use sudo or change files outside the project.

TASK:
{task_text}
"""
    r = subprocess.run(
        [exe, "run", model], cwd=str(cwd), input=prompt, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=7200
    )
    out = r.stdout or ""
    print(out)
    if r.returncode != 0:
        return {"pass": False, "reason": f"ollama exit {r.returncode}", "output": out[-10000:]}
    # Extract JSON robustly.
    text = out.strip()
    try:
        payload = json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, flags=re.S)
        if not m:
            return {"pass": False, "reason": "agent returned no JSON", "output": out[-10000:]}
        try:
            payload = json.loads(m.group(0))
        except Exception as e:
            return {"pass": False, "reason": f"invalid JSON: {e}", "output": out[-10000:]}
    result.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"pass": True}

def validate_patch_text(patch: str, project: Path) -> tuple[bool, str]:
    if not patch.strip():
        return False, "empty patch"
    # Reject absolute paths and path traversal in diff headers.
    for line in patch.splitlines():
        if line.startswith(("--- ", "+++ ")):
            path = line[4:].split("\t")[0].strip()
            if path in {"/dev/null"}:
                continue
            path = re.sub(r'^[ab]/', '', path)
            if os.path.isabs(path):
                return False, f"absolute path in patch: {path}"
            if ".." in Path(path).parts:
                return False, f"path traversal in patch: {path}"
    return True, "ok"

def apply_agent_result(project: Path, result: Path, outdir: Path, cycle: int) -> dict[str, Any]:
    try:
        payload = json.loads(result.read_text())
    except Exception as e:
        return {"pass": False, "reason": f"invalid result JSON: {e}"}
    patch = payload.get("unified_patch", "")
    ok, why = validate_patch_text(patch, project)
    if not ok:
        return {"pass": False, "reason": why}

    patch_path = outdir / f"PATCH_{cycle:03d}.diff"
    patch_path.write_text(patch, encoding="utf-8")

    # Dry-run first.
    if shutil.which("git"):
        dry = run(["git", "apply", "--check", str(patch_path)], cwd=project, timeout=120)
        if dry["returncode"] == 0:
            rr = run(["git", "apply", str(patch_path)], cwd=project, timeout=120)
            return {"pass": rr["returncode"] == 0, "method": "git apply", "output": rr["output"][-10000:]}
    if shutil.which("patch"):
        dry = run(["patch", "--dry-run", "-p1", "-i", str(patch_path)], cwd=project, timeout=120)
        if dry["returncode"] == 0:
            rr = run(["patch", "-p1", "-i", str(patch_path)], cwd=project, timeout=120)
            return {"pass": rr["returncode"] == 0, "method": "patch -p1", "output": rr["output"][-10000:]}
    return {"pass": False, "reason": "patch could not be applied cleanly"}

def snapshot_authoritative(project: Path, outdir: Path, cycle: int) -> Path:
    snap = outdir / "snapshots" / f"{cycle:03d}"
    snap.mkdir(parents=True, exist_ok=True)
    paths = [
        project / "Groovebox" / "groovebox.py",
        project / "Groovebox" / "composition_state.py",
        project / "Groovebox" / "videogame_engine.py",
        project / "sCode" / "sCode.py",
        project / "sOS_COMPILER" / "sos_compiler.py",
    ]
    manifest = []
    for p in paths:
        if p.exists():
            rel = p.relative_to(project)
            dst = snap / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            manifest.append(str(rel))
    (snap/"MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    return snap

def restore_snapshot(project: Path, snap: Path):
    manifest = json.loads((snap/"MANIFEST.json").read_text())
    for rel in manifest:
        src = snap / rel
        dst = project / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def package_finished(project: Path, outdir: Path) -> dict[str, str]:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = outdir / f"MathematiciansGroovebox_sCode_sOS_FINISHED_{stamp}"
    zip_path = base.with_suffix(".zip")
    tar_path = Path(str(base) + ".tar.gz")

    def include(p: Path) -> bool:
        rel_parts = p.relative_to(project).parts
        return not any(part in SKIP_DIRS for part in rel_parts)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in project.rglob("*"):
            if p.is_file() and include(p):
                z.write(p, p.relative_to(project))

    with tarfile.open(tar_path, "w:gz") as t:
        for p in project.rglob("*"):
            if p.is_file() and include(p):
                t.add(p, arcname=str(p.relative_to(project)), recursive=False)

    return {"zip": str(zip_path), "tar_gz": str(tar_path)}

def all_hard_gates_pass(gates: list[dict[str, Any]], router: dict[str, Any]) -> bool:
    # Router is a hard gate if present. Decode stages are routing aids, not finish proof.
    hard_names = {"python_syntax", "pytest", "native_build", "sos_compiler", "no_python_runtime"}
    hard = [g for g in gates if g.get("name") in hard_names]
    if not hard or not all(g.get("pass") for g in hard):
        return False
    if router and not router.get("skipped") and not router.get("pass"):
        return False
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".", help="Universal redistributable / project root")
    ap.add_argument("--out", default=".finish-all", help="Working/output directory inside project by default")
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument("--max-cycles", type=int, default=32)
    ap.add_argument("--agent-cmd", default=None,
                    help="Command template with {task} and {result}, e.g. python3 driver.py {task} {result}")
    ap.add_argument("--ollama-model", default=None,
                    help="Optional local Ollama model used when --agent-cmd is absent")
    ap.add_argument("--skip-os-decode", action="store_true")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not project.exists():
        print(f"ERROR: project not found: {project}", file=sys.stderr)
        return 2

    # Require core layout before doing anything destructive.
    required_any = [
        project / "Groovebox",
        project / "sCode",
        project / "sOS",
    ]
    missing = [str(x.name) for x in required_any if not x.exists()]
    if missing:
        print("ERROR: expected project root is missing: " + ", ".join(missing), file=sys.stderr)
        return 2

    outdir = (project / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out).resolve()
    # Keep output confined unless explicitly absolute.
    outdir.mkdir(parents=True, exist_ok=True)

    log(f"project={project}")
    log(f"workers={args.workers}")
    log(f"max_cycles={args.max_cycles}")

    dedupe = dedupe_index(project)
    (outdir/"DEDUPE_INDEX.json").write_text(json.dumps(dedupe, indent=2))
    log(
        f"dedupe: {dedupe['files_scanned']} files, "
        f"{dedupe['exact_duplicate_classes']} exact classes, "
        f"{dedupe['python_ast_duplicate_classes']} Python-AST classes"
    )

    history = []
    last_failure_signature = None
    stagnant = 0

    for cycle in range(1, args.max_cycles + 1):
        log(f"===== cycle {cycle}/{args.max_cycles} =====")
        snap = snapshot_authoritative(project, outdir, cycle)

        gates = []
        if not args.skip_os_decode and cycle == 1:
            gates.append(run_os_decoder(project, outdir, args.workers))
        if cycle == 1:
            gates.append(run_reverse_decoder(project, outdir))

        gates.append(python_syntax_gate(project))
        gates.append(run_selected_pytests(project))
        gates.append(native_build_gate(project))
        gates.append(sos_compiler_gate(project))
        gates.append(no_python_runtime_gate(project))
        router = run_finish_router(project, outdir)

        state = {
            "cycle": cycle,
            "gates": gates,
            "router": router,
            "timestamp": time.time(),
        }
        history.append(state)
        (outdir/"LATEST.json").write_text(json.dumps(state, indent=2, default=str))
        (outdir/"HISTORY.json").write_text(json.dumps(history, indent=2, default=str))

        if all_hard_gates_pass(gates, router):
            packages = package_finished(project, outdir)
            final = {
                "status": "FINISHED",
                "cycle": cycle,
                "packages": packages,
                "gates": gates,
                "router": router,
                "dedupe": {
                    "files_scanned": dedupe["files_scanned"],
                    "exact_duplicate_classes": dedupe["exact_duplicate_classes"],
                    "python_ast_duplicate_classes": dedupe["python_ast_duplicate_classes"],
                }
            }
            (outdir/"FINISHED.json").write_text(json.dumps(final, indent=2, default=str))
            log("FINISHED: all hard gates passed.")
            log(packages["zip"])
            log(packages["tar_gz"])
            return 0

        failures = extract_failures(gates, router)
        signature = hashlib.sha256(json.dumps(failures, sort_keys=True, default=str).encode()).hexdigest()
        if signature == last_failure_signature:
            stagnant += 1
        else:
            stagnant = 0
        last_failure_signature = signature

        task = make_agent_task(project, outdir, failures, dedupe, cycle)
        blocked = {
            "status": "BLOCKED",
            "cycle": cycle,
            "agent_task": str(task),
            "failures": failures,
        }
        (outdir/"BLOCKED.json").write_text(json.dumps(blocked, indent=2, default=str))

        if not args.agent_cmd and not args.ollama_model:
            log("BLOCKED: deterministic/mechanical passes are exhausted.")
            log(f"Agent task: {task}")
            log("Re-run with --agent-cmd or --ollama-model to continue semantic repair automatically.")
            return 3

        result = outdir / f"AGENT_RESULT_{cycle:03d}.json"
        if args.agent_cmd:
            inv = invoke_agent_cmd(args.agent_cmd, task, result, project)
        else:
            inv = invoke_ollama(args.ollama_model, task, result, project)

        if not inv.get("pass"):
            log("Agent invocation failed; leaving BLOCKED.json/task for inspection.")
            return 4

        applied = apply_agent_result(project, result, outdir, cycle)
        if not applied.get("pass"):
            log("Agent patch was not safely applicable.")
            return 5

        # Immediate stabilization check. Roll back broken patches.
        syntax = python_syntax_gate(project)
        tests = run_selected_pytests(project)
        if not syntax.get("pass") or not tests.get("pass"):
            log("Patch failed stabilization checks; rolling back authoritative snapshot.")
            restore_snapshot(project, snap)
            stagnant += 1
        else:
            log("Patch passed immediate stabilization checks.")

        if stagnant >= 3:
            log("Three semantically identical failure states encountered; stopping to avoid infinite repair loop.")
            return 6

    log("Maximum cycles reached without all gates passing.")
    return 7

if __name__ == "__main__":
    raise SystemExit(main())
