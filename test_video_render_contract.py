#!/usr/bin/env python3
"""Static regression checks for the deterministic Meum video-render contract."""
from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "groovebox.py"
text = SRC.read_text(encoding="utf-8")
tree = ast.parse(text)

video_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "VideoSynthEngine")
methods = {n.name: n for n in video_cls.body if isinstance(n, ast.FunctionDef)}

def source(fn):
    return ast.get_source_segment(text, methods[fn]) or ""

# Alpha must remain caller-authoritative; no hidden global 1.65x density boost.
assert "* 1.65" not in source("_line")
assert "* 1.65" not in source("_dot")

# The canonical entropy lane must not be addressed by mutable repaint count.
canon = source("_build_canonical_ctx_and_layers")
assert "_visual_frame) % len(self._canonical)" not in canon
assert "_render_frame_index" in canon

# Offline render accepts an explicit frame index.
render = source("render_frame")
assert "frame_index=None" in render
assert "self._render_frame_index" in render

# GOAVA video reads the evaluated seed list at current render time.
assert "_current_goava_events" in text
cur = source("_current_goava_events")
assert "_parse_goava_seed_values" in cur
assert "cache=False" in cur

# Export uses a fresh engine and explicit frame timing, then streams raw RGB.
export_start = text.index("    def export_video_dialog")
export = text[export_start:]
assert "eng = VideoSynthEngine(_nmem)" in export
assert "frame_index=fi" in export
assert '"-f", "rawvideo"' in export
assert "part_frames_dir" not in export
assert "frames_root" not in export

# Executable playlist hashing must use the process-stable helper.
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "hash":
        raise AssertionError("executable built-in hash() remains; use _stable_hash()")

print("PASS: caller-authoritative alpha")
print("PASS: explicit deterministic render frame identity")
print("PASS: live GOAVA seed-list evaluation contract")
print("PASS: fresh-engine rawvideo export pipeline")
print("PASS: no process-salted hash in numeric fractal path")
