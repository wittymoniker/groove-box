#!/usr/bin/env python3
"""Regression contract for MP4/carrier-video first-frame canonical visual metadata."""
import ast
from pathlib import Path

SRC = Path(__file__).with_name("groovebox.py")
text = SRC.read_text(encoding="utf-8", errors="replace")
tree = ast.parse(text, filename=str(SRC))
fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "canonical_visual_instrument"), None)
if fn is None:
    raise SystemExit("FAIL: canonical_visual_instrument missing")

assigned = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
loaded = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
checks = {
    "n_eng is locally assigned": "n_eng" in assigned,
    "n_eng is used by canonical visual metadata": "n_eng" in loaded and '"engines": n_eng' in text,
    "active canonical engine count is deterministic": "n5 = sum(1 for _k in _VISUAL_ENGINE_CHANNELS if eng.get(_k))" in text,
    "level-weighted influence remains separate": "total_level = sum(_lev[k] for k in _VISUAL_ENGINE_CHANNELS if eng.get(k))" in text,
    "idle visual reference remains 1/6": "if total_level > 1e-9 else (1.0 / 6.0)" in text,
}
failed = []
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + "  " + name)
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit("MP4 n_eng regression failed: " + ", ".join(failed))
print(f"PASS  {len(checks)}/{len(checks)} MP4 n_eng regression checks")
