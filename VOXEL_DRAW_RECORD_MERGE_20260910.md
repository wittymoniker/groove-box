# Draw/Record 3D Voxel Merge — 2026-09-10

Base: groovebox_CANONICAL_USERDATA_SAFE_20260909 with the five-canonical Euclidean promotion.

## Changes
- Removed the standalone **Draw/Record 3D Voxel Kit** launch button.
- Embedded **3D Voxel Draw / Record** directly in the shared Draw / Record / Video workbench.
- Added an indexed X/Y slice grid with selectable Z slice.
- Added an always-visible isometric **Full Model Reference**; the selected Z plane is highlighted while drawing.
- Added voxel color selection and per-voxel blend/alpha.
- Preserved **Overall Alias** as the model-wide smoothing control.
- Video-to-voxel conversion now retains sampled RGB color and current blend alpha.
- Voxel records now persist as `[x,y,z,r,g,b,a]`; legacy `[x,y,z]` projects load with the previous teal/default material.
- PLY exports include RGBA properties.
- OBJ exports include an accompanying MTL with RGB and dissolve/alpha materials.
- Live/offline audiovisual voxel rendering uses stored voxel RGB + alpha.
- Color/blend voxel data participates in project save/load, Undo/Redo, export provenance and the canonical fingerprint.

## Validation
- `python -m py_compile groovebox.py` — PASS
- `test_voxel_drawrecord_merge_20260910.py` — 20/20 PASS
- `test_five_canonical_euclidean_20260910.py` — 24/24 PASS
- `test_four_canonical_voxel_20260910.py` (updated five-canonical release contract) — PASS

GUI/camera/audio hardware paths cannot be interactively exercised in the build sandbox; run normal hardware smoke tests on the target Groovebox machine.
