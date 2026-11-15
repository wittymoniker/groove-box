# Live Player and Window Lifecycle Revision — 2026-11-15

## Changes

- Performance → Open Windows now refreshes every 750 ms only while that tab is selected. Leaving the tab or closing the Performance window stops the timer; restoring the window resumes the selected workspace's appropriate resources.
- The session window manager now calls `release_session_resources()` for programmatic Close/Hide operations as well as intercepted window-close events, and calls `resume_session_resources()` when a retained window is restored. Calls are idempotent across repeated close notifications.
- Live Player provides explicit visual-layer and canonical-morph randomize/reset controls. Randomization is opt-in and never starts camera or microphone capture.
- Main video rig/scenograph is the only visual layer enabled by default. Orbit, waveform ring, names, playlist strip, media, multidimensional and camera layers default off. Camera capture itself defaults off; camera PiP/full-scene switches are surfaced above the layer grid.
- Canonical morph, keyboard participation and sample participation default off. The keys and samples checkboxes remain independently operable when master morph is disabled.
- Live Player GUI/visual refresh moves from 62.5 Hz (16 ms) to 30 Hz (33 ms). The sCode visual bridge is capped at 10 Hz, and morph target refresh is reduced to 4 Hz. Audio playback remains on its separate audio callback.
- Closing Live Player through the session manager stops its UI timer, detaches/stops audio and rig work through the existing asynchronous teardown path, closes camera capture off the UI thread, and closes pop-outs/broadcast view. Restoring the retained window restarts only its lightweight UI refresh; playback does not start by itself.

## Verification

- Python syntax compilation passed for the modified `groovebox.py`, `performance.py`, and `live_player.py`, including their synchronized ISO overlay copies.
- `scripts/sync_runtime_payload.py --check` passed for 407 runtime module/package sources.
- Added seven focused source-contract tests in `test_live_player_window_lifecycle_revision_20261115.py`.
- Existing focused window/session tests: 10 passed, 2 failed on pre-existing source-text expectations in unrelated file-browser and main-close implementations. The Live Player Qt GUI test could not be collected because PyQt6 is not installed in this environment.
- No live Qt GUI, audio callback latency, camera device, worker teardown stress, ISO build, or hardware test was run. Refresh-rate changes are source-level optimizations, not measured performance guarantees.

## Source snapshot limitation

This archive contains the v35.22zz / R23R-era `live_player.py` canonical morph and layer implementation. It does not contain the newer R64 canonical video-FX dictionary / mapped-player modules described in a separate project handoff. This revision updates the actual files present in this uploaded archive and does not claim to complete or replace those absent R64 components.
