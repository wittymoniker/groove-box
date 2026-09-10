#!/usr/bin/env python3
"""Static release contract for the 2026-09-10 canonical/voxel forward port (Euclidean promoted to fifth canonical).

Does not import PyQt, so it can run on build/CI hosts before GUI dependencies exist.
"""
from pathlib import Path

SRC = Path(__file__).with_name("groovebox.py")
text = SRC.read_text(encoding="utf-8", errors="replace")

checks = {
    "five public canonical buttons": all(x in text for x in (
        'QPushButton("SEEDED")', '"RAND"', '"LOCK"', 'QPushButton("EUCLIDEAN")', '"GOAVA"')),
    "matched canonical button footprint": '_canon_button_size = (168, 52)' in text,
    "restored five-color canonical identity": all(x in text for x in (
        '#e6a800', '#41d17a', '#12e0c4', '#66ffaa', '#ff8a42')),
    "RAND uses OS entropy": 'secrets.randbits(64)' in text,
    "RAND token is frozen project state": 'rand_instance_seed' in text,
    "five canonical level sliders": all(x in text for x in (
        'slider_level_seeded', 'slider_level_rand', 'slider_level_lock', 'slider_level_euclidean', 'slider_level_goava')),
    "LOCK character sliders": all(x in text for x in (
        'slider_lock_coupling', 'slider_lock_timing_pull', 'slider_lock_detune_link',
        'slider_lock_velocity_link', 'slider_lock_phase_spread')),
    "slider undo keyboard/wheel support": '_on_canonical_slider_action' in text,
    "undo snapshot persists canonical state": all(x in text for x in (
        'state["canonical_engine_levels"]', 'state["phase_lock_characteristics"]',
        'state["rand_instance_seed"]')),
    "project save/load persists canonical and 3D": all(x in text for x in (
        '"canonical_engines"', '"draw_record_3d"')),
    "export provenance persists canonical controls": all(x in text for x in (
        '"canonical_levels": _safe_json(self._canonical_levels())',
        '"phase_lock_characteristics": _safe_json(self._lock_characteristics())')),
    "3D model import": 'def import_3d_model_dialog' in text,
    "voxel Draw/Record kit": 'class VoxelDrawKitDialog' in text,
    "overall voxel alias": 'Overall Alias:' in text,
    "OBJ/PLY model export": 'def export_3d_model_dialog' in text,
    "voxel video renderer": 'def _subscene_voxel_model' in text,
    "public canonical count is max five": 'Number of active public canonical engines (max five).' in text,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + "  " + name)
if failed:
    raise SystemExit("release contract failed: " + ", ".join(failed))
print("PASS  five-canonical + 3D voxel release contract")
