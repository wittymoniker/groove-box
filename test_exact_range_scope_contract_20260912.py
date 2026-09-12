#!/usr/bin/env python3
"""Static contract: mathematical range scope uses exact zero/min/max handling."""
from pathlib import Path
import ast

ROOT=Path(__file__).parent
files={name:(ROOT/name).read_text(encoding="utf-8") for name in (
    "groovebox.py","videogame_engine.py","video_clip_studio.py","media_layer_engine.py",
    "media_cutup_engine.py","meum_ot_math.py","dj_effects.py","performance.py",
    "parametric_file_remix.py","reverse_engineer.py","signal_lab.py","canonical_cross_media.py",
)}
for name,text in files.items(): ast.parse(text, filename=name)

gb=files["groovebox.py"]
vg=files["videogame_engine.py"]
ml=files["media_layer_engine.py"]
vc=files["video_clip_studio.py"]
checks={
    "spatial singularity tests r==0": "if r == 0.0:" in gb,
    "bounded wave tests exact zero lengths": "if lx == 0.0 or ly == 0.0 or lz == 0.0:" in gb,
    "EQR distance has exact zero branch": "if dn != 0.0 else 0.0" in gb,
    "EQR P gate is exact": "if P != 0.0:" in gb,
    "OT tangent checks exact zero": "if c == 0.0:" in gb,
    "triangle denominator checks exact zero": "den != 0.0" in gb,
    "signal presence uses exact nonzero": "np.any(safe != 0.0)" in gb,
    "vector norm uses exact zero": "if norm == 0.0:" in gb,
    "media weights preserve zero": "if raw_total == 0.0:" in ml,
    "media span checks exact zero": "if span == 0.0: continue" in ml,
    "open video layer end is truly unbounded": "math.inf" in vc and "1e9" not in vc,
    "game nearest-distance sentinel is infinity": "best=math.inf" in vg and "bd=math.inf" in vg,
    "game vector normalization exact": "if n != 0.0 else" in vg,
    "game fractal no ±1e6 display clamp": "math.copysign(1e6" not in vg,
    "temporal zero period exact": "if per == 0.0:" in files["meum_ot_math.py"],
    "transform identity exact": "if mul == 1.0" in files["meum_ot_math.py"],
    "DJ off gate exact": "amt <= 0.0" in files["dj_effects.py"],
    "remix speed identity exact": "if speed != 1.0" in files["parametric_file_remix.py"],
}
failed=[]
for name,ok in checks.items():
    print(("PASS" if ok else "FAIL")+"  "+name)
    if not ok: failed.append(name)
if failed: raise SystemExit("exact range scope contract failed: "+", ".join(failed))
print(f"PASS  {len(checks)}/{len(checks)} exact range scope checks")
