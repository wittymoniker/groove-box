# R76 — Applications launcher, integrated deck, and deterministic OBJ scene controls

## Included source updates

- Added a taskbar **Apps** launcher that opens the existing Applications / Plugin Library browser. The browser reports the discovered shipped plugin count and Lua entries, and continues to expose source review, run, Program Builder handoff, LAN sharing, carrier binding, event binding, and rating workflows.
- Expanded **＋ New window** from three entries to sixteen major workspace launch targets: Performance, Media Player, Live Player, Multidim Synth, 3D/Scenograph, Video Synth, Game Scene Studio, Composition Lab, Seed Atlas, Script Studio, Plugin Library, Lua Workspace, Program Builder, File Studio, Experiences, and Project/Science Tools.
- Reworked the R32 Deck so it is a persistent Main Window-owned surface rather than a floating/closable independent window. Its visibility is controlled by a Main Window toolbar toggle; splitter reparenting no longer re-shows the dock shell as a separate window.
- Extended the shared OBJ frame renderer with deterministic geometric distortion, roll, pan, zoom, opacity, fade-in/fade-out, and optional soft ground shadow. These are renderer parameters, so the 3D Studio preview and its chunked mono/stereo export use the same scene math.
- Added corresponding controls to 3D Studio and connected them to its common render parameter snapshot.
- Synchronized runtime payload copies/manifests for the updated runtime sources.

## Scope and verification

No tests, syntax checks, static checks, GUI runs, audio/video renders, hardware checks, or ISO builds were run, as requested. This archive is a source update and has not been runtime-validated. The Game Scene Studio launcher intentionally opens 3D Studio's scene/OBJ-to-game workflow rather than starting a standalone game session with network/asset-install side effects.


## Applications taskbar launcher refinement

- Replaced the generic Apps taskbar control with a prominent, GOAVA-toned **PLUGINS** launcher tile.
- Added a compact **Programs** shortcut inset in the tile's upper-right corner; it opens Program Builder directly without taking a second taskbar slot.
- The New Window menu retains the independent Plugin Library and Program Builder entries.
- This is a source-only UI change. No tests, checks, or builds were run, as requested.
