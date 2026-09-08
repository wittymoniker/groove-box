# Video Clip Studio validation — 2026-09-07

Implemented in both normal Groovebox tree and staged sOS `/opt/groovebox` tree.

## Entry points
- Performance → `🎥 Record / Import / Draw Clip`
- Main Window → `✎🎙🎥 Draw / Record / Video` → Video tab

Both entry points use project-shared Video Clip Studio state during save/load.

## Devices and previews
- Explicit camera selection + refresh
- Explicit microphone selection + refresh
- Explicit mounted tablet/media-source selection + filesystem browse
- Live camera preview via Qt Multimedia when available
- Live microphone level preview/meter
- Selected camera + microphone recording to project recordings
- Tablet/removable-media video import into project recordings

## Creation
- Draw-only video clips
- Imported or recorded base video
- RGBA painting tools: Brush, Eraser, Line, Rectangle, Ellipse, color and brush size
- Time-varying graph lanes: layer opacity, X, Y, scale, rotation, drawn-sound pitch/gain, Sound→Color amount
- Optional Draw Sound, Color→Sound and Sound→Color; all OFF by default
- Final Color→Sound Translation Detail: Off / Basic / Detailed
- Final audio mix uses FFmpeg `amix normalize=0`; no new normalizer, compressor or limiter is introduced
- Existing intentional Groovebox master hard clip / 50% Clip-Gain design is not changed by this feature

## Canonical live mix
- Canonical Live Overblend default: 50% (net 50/50 user/canonical waveform blend)
- 50% still reproduces the legacy 50/50 waveform boundary
- Canonical transforms/activity remain independent of the optional waveform overblend

## Checks
- Python AST parse / bytecode compile: PASS for groovebox.py, performance.py, video_clip_studio.py
- Main Window shared-state contract: PASS
- Performance Video Clip tab contract: PASS
- Camera / microphone / tablet selectors: PASS
- Camera and mic preview code paths: PASS
- Color↔sound optional-default contract: PASS
- `amix normalize=0`: PASS
- Staged sOS copies byte-identical to normal tree: PASS
- Standalone import audit: 774 import rows, 0 unresolved/review imports
- test_project_media_contract.py: PASS
- test_video_render_contract.py: PASS
- test_algorithm_automation_parity.py: PASS

Runtime camera/microphone behavior ultimately depends on the tablet/PC kernel, Qt Multimedia backend, permissions, and device drivers.
