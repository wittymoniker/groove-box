# Final Stability / Beat-Time / Optimization Pass — 2026-09-08

## Musical-time seed semantics
- Arrangement-aware composition evaluates seed-script `t` in **absolute beats**, independent of BPM.
- Playlist row N uses `t = N * RowBeats + GlobalTrackOffset`, with local beat position added where applicable.
- GOAVA audio composition now receives row start **beat**, not row start seconds.
- GOAVA visual state converts visual wall-clock seconds to beats so audio/visual GOAVA use the same musical coordinate.
- Continuous DSP seed modulation still uses seconds at the audio-render boundary; changing BPM therefore changes playback speed but not the beat-indexed arrangement identity.
- `get_numeric_seed()` remains the deliberate static/global t=0 snapshot for RNG/fingerprint contexts; arrangement-aware callers use evaluated beat-domain seed values.

## Track offset correction
- Global Track Offset is now consistently authored/interpreted in **beats**.
- Audio converts Global Track Offset from beats to seconds only at scheduling time.
- Visual timing does the same boundary conversion.
- Legacy per-sequence `track_offset` remains row-relative for project compatibility.

## Tooltip / help audit
- Removed the stale `Composition uses t=0` wording.
- Seed Script and Random Seed Script tooltips now distinguish beat-domain composition from second-domain continuous DSP modulation.
- Global Track Offset tooltip/help now describes beat units accurately.

## Recording / GUI responsiveness
- Qt/GStreamer recording remux/final probe is no longer performed synchronously on the GUI thread.
- Qt recorder finalization uses the pooled worker path (or daemon-thread fallback) and publishes the recording only after successful positive-duration video verification.
- Removed the legacy sleep/poll recording-container wait helper.
- Capture modules contain no executable `.wait()`, `waitForStarted()`, `waitForFinished()`, `waitForBytesWritten()`, or `time.sleep()` processing path.
- V4L2 finalization remains event-driven from QProcess completion.

## Additional cleanup
- Removed explicit subprocess `.wait()` cleanup calls from the main video export error/finalization cleanup path; process state is checked/killed without unbounded wait calls.

## Validation performed in this build environment
Passed:
- Python compileall / syntax validation
- `test_composition_parity.py`
- `test_project_media_contract.py`
- `test_video_render_contract.py`
- `test_final_determinism.py` (7/7 deterministic purity groups)
- `test_algorithm_automation_parity.py`
- static stale-tooltip audit
- static blocking-wait capture audit

Not executable in this container:
- Full PyQt6 GUI/hardware launch (`PyQt6` is not installed in the test container). `test_component_usage.py` stops at the missing dependency import, not at Groovebox application code.
