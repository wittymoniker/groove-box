# Euclidean Canonical Update — 2026-09-10

Authoritative base: `groovebox_CANONICAL_USERDATA_SAFE_20260909` plus the 2026-09-10 true-RAND / 3D voxel forward port.

## Canonical set

The public composition canonicals are now:

`SEEDED | RAND | LOCK | EUCLIDEAN | GOAVA`

Euclidean is promoted from Rhythm Assist to a full canonical because its deterministic rhythm/structure transform can reshape both generated composition data and protected user-entered material.

## UI

- Playlist now occupies Euclidean Rhythm Assist's former upper transport-row position.
- EUCLIDEAN moves into the canonical row with SEEDED / RAND / LOCK / GOAVA.
- All five canonical buttons share the same 168×52 footprint and retain distinct colors.
- Canonical Morph Bridge contains level controls for all five engines, including EUCLIDEAN.

## State / output integration

Euclidean toggle + level participate in canonical active-set logic, canonical sequence reconciliation, fingerprints, project save/load, Undo/Redo, export provenance, audiovisual rendering, and cross-media node/visual structure. WAV, MP3, and MP4 therefore resolve the same saved Euclidean canonical state.

## Compatibility

The new project schema writes `canonical_engines` with schema version 5 while retaining the legacy `four_canonical` compatibility payload so earlier 2026-09-10 builds can recover shared level/LOCK/RAND fields.

## Validation

- `python -m py_compile groovebox.py` — PASS
- `test_five_canonical_euclidean_20260910.py` — 24/24 PASS
- `test_four_canonical_voxel_20260910.py` (updated compatibility contract) — PASS
- canonical userdata ownership — PASS
- full graph script compatibility — PASS
- project media contract — PASS
- project state integration — PASS
- radio-quality export contract — PASS
- video render contract — PASS
