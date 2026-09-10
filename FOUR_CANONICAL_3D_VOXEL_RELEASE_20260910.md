# Four Canonical / 3D Voxel Forward-Port — 2026-09-10

Authoritative base: `groovebox_CANONICAL_USERDATA_SAFE_20260909.zip`

This release is a forward-port onto that full tree, not a replacement from an older standalone `groovebox.py`.

## Integrated

- Four independent canonical toggles: SEEDED / RAND / LOCK / GOAVA.
- Restored distinct colors; all four use the same 168×52 footprint.
- RAND captures fresh OS entropy via `secrets.randbits(64)` on activation, then freezes the token for deterministic replay/export.
- Four canonical level sliders in the bottom CANONICAL MORPH BRIDGE.
- LOCK characteristic sliders with tuned defaults: Coupling 62, Timing Pull 50, Pitch/Detune Link 62, Velocity Link 65, Phase Spread 20.
- Slider changes participate in Undo/Redo for mouse drag plus keyboard/wheel actions.
- Save/load and export provenance include canonical levels, LOCK characteristics, RAND token/counter, and 3D voxel state.
- WAV/MP3 share the canonical audio mixdown path; MP4 uses the same canonical state plus voxel/scenograph rendering.
- Draw/Record 3D Voxel Kit with Z-slice editing and Overall Alias.
- 3D import: OBJ, PLY, STL; glTF/GLB retained as project model references when direct vertex decoding is unavailable.
- 3D export: OBJ and PLY; voxel scene also participates in rendered video output.
- Euclidean Rhythm Assist remains separate and does not count as a fifth public canonical.

## Validation performed

- `python -m py_compile groovebox.py` — PASS
- `python test_four_canonical_voxel_20260910.py` — PASS
- `python test_project_state_integration_20260909.py` — PASS
- `python test_project_media_contract.py` — PASS
- `python test_video_render_contract.py` — PASS
- `python test_full_graph_script_compat.py` — PASS
- `python test_heuristic_writer_split.py` — PASS

Full GUI/device execution is not performed in this build container because PyQt6/hardware devices are unavailable here; run the normal hardware smoke test after unpacking on the target Groovebox system.
