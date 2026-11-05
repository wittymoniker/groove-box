# Groovebox R28.4.49 — 24 deterministic visual layers

This increment builds on R28.4.48 canonical chord-budget source.

## Added
- 24 named visual layers across harmonic geometry, motion/depth, rhythm/fractal, and cinematic-transition families.
- A real raster pass for the 24 layers, invoked in the common `VideoSynthEngine.render_frame` path used by live and export rendering.
- Deterministic per-layer relevance from shared composition state and the existing asymmetric fade coordinator.
- Catalog size increased from 64 to 88 and synchronized to `BUILD_ISO/app-overlay-v35.22zz/groovebox.py`.
- Source-contract tests for the 24 names, fade scheduling, and render-pipeline wiring.

## Validation performed
- `python -m py_compile groovebox.py BUILD_ISO/app-overlay-v35.22zz/groovebox.py` — passed.
- `python -m unittest test_canonical_chord_budget_r28_4_48.py test_visual_elements_r28_4_49.py -v` — 10 tests passed.

## Not yet verified
- Runtime frame rendering / visual inspection: this environment lacks PyQt6, so the app module cannot be imported for an end-to-end render test here.
- Audio stream recovery when the master-volume slider changes.
- Full chord-tone rendering through every instrument's actual synthesis path.
- Save/load/recovery round trips and privacy/export boundaries.
- ISO build/boot and physical hardware validation.

The new layers are implemented source-level render passes; this package is not represented as a fully validated end-to-end release.
