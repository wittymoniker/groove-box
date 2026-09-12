#!/usr/bin/env python3
"""Static regression contract for NaN-safe video export and clean app shutdown."""
from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "groovebox.py"
OPT = ROOT / "scode_optimizer_bridge.py"
text = SRC.read_text(encoding="utf-8")
tree = ast.parse(text, filename=str(SRC))

video_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "VideoSynthEngine")
video_methods = {n.name: n for n in video_cls.body if isinstance(n, ast.FunctionDef)}
viewer_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "VideoSynthViewer")
viewer_methods = {n.name: n for n in viewer_cls.body if isinstance(n, ast.FunctionDef)}
app_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MathematiciansGrooveboxApp")
app_methods = {n.name: n for n in app_cls.body if isinstance(n, ast.FunctionDef)}

def src(methods, name):
    return ast.get_source_segment(text, methods[name]) or ""

checks = {
    "waveform sanitizes NaN/Inf": "np.nan_to_num(arr" in src(video_methods, "set_waveform"),
    "analysis never emits infinite octave boundary": "_finite_float(_oct, 1.0, 0.0, 4.0)" in src(video_methods, "_analyze"),
    "numeric seed fallback rejects NaN": "math.isfinite(_seed_fallback)" in src(video_methods, "_live_snap"),
    "line raster rejects non-finite geometry": "math.isfinite(float(v))" in src(video_methods, "_line"),
    "dot raster rejects non-finite geometry": "math.isfinite(float(x))" in src(video_methods, "_dot"),
    "triangle raster rejects non-finite geometry": "np.all(np.isfinite(pts))" in src(video_methods, "_fill_tri"),
    "degenerate triangle denominator is rejected exactly": "den != 0.0" in src(video_methods, "_fill_tri"),
    "final frame is finite": "img = np.nan_to_num(img" in src(video_methods, "render_frame"),
    "preview shutdown is idempotent": "_render_shutdown" in src(viewer_methods, "shutdown_rendering"),
    "closed preview rejects new render requests": "_render_shutdown" in src(viewer_methods, "_request_async_frame"),
    "late render completions cannot touch closed widgets": "_render_shutdown" in src(viewer_methods, "_on_async_frame_ready"),
    "export reports exact bad frame context": "render failed:" in src(app_methods, "export_video_dialog"),
    "main shutdown is idempotent": "_groovebox_shutdown_started" in src(app_methods, "closeEvent"),
    "main shutdown stops Qt timers": "findChildren(QTimer)" in src(app_methods, "closeEvent"),
    "main shutdown closes media workbench": "_main_signal_lab_dialog" in src(app_methods, "closeEvent"),
    "main shutdown closes optimizer": "_opt.shutdown(wait=False)" in src(app_methods, "closeEvent"),
}

opt_text = OPT.read_text(encoding="utf-8")
opt_tree = ast.parse(opt_text, filename=str(OPT))
opt_cls = next(n for n in opt_tree.body if isinstance(n, ast.ClassDef) and n.name == "SCodeOptimizerBridge")
opt_methods = {n.name: n for n in opt_cls.body if isinstance(n, ast.FunctionDef)}
opt_shutdown = ast.get_source_segment(opt_text, opt_methods["shutdown"]) or ""
checks.update({
    "optimizer shutdown is idempotent": "_shutdown_started" in opt_shutdown,
    "optimizer timers stop before pool shutdown": "timer.stop()" in opt_shutdown,
    "queued UI callbacks are cleared": "self._ui_callbacks.clear()" in opt_shutdown,
})

failed=[]
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + "  " + name)
    if not ok: failed.append(name)
if failed:
    raise SystemExit("NaN/exit regression failed: " + ", ".join(failed))
print(f"PASS  {len(checks)}/{len(checks)} NaN/exit regression checks")
