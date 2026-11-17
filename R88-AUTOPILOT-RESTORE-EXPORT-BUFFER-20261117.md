# MATGROOVEBOX R88 — Autopilot queue, reset and export-resume contract

- Adds a non-blocking Qt-timer-driven instrument-page queue. It visits each instrument through the existing selector and instrument-switch handler, reports progress, and never edits synth values invisibly. Composition itself remains the existing Configure Entire Project operation.
- Composer waits for the authoring pass before opening Live Player. Live Player remains one-shot with Loop OFF. In play-current-project series mode it replays without composing or clearing between plays.
- Export-after-play remains opt-in. The composer waits for a newly submitted export job before rolling memory forward; if the export dialog is left open or cancelled before submission, the current project is retained. Stop remains available.
- Clear Memory now invalidates process-local live-buffer/in-flight/render snapshot state while leaving the content-addressed disk cache and queued export snapshots intact.
- Export Resume now writes schema-3 metadata with the `groovebox-live-pcm/2` cache descriptor contract. A descriptor is reusable only when its cache file, render identity, PCM header, dimensions, sample rate and payload checksum validate. Otherwise it re-renders from the frozen MCC project snapshot.
- The ISO application overlay and runtime payload SHA-256 manifest are synchronized for every changed/new runtime module.

## Validation

This archive is the pre-test handoff. Compilation, unit tests, Qt GUI, playback, recording, export/resume, ISO build/boot, and hardware installation have not yet been run. The next step is the test pass requested by the user.

## Checks performed for this handoff

- `py_compile` passed for all six changed Python modules.
- Focused smoke checks passed for the instrument-page queue and live-buffer descriptor creation, schema/dimension/checksum validation, and checksum-tamper rejection.
- Existing Qt-dependent Live Player/recording test collection could not start because PyQt6 is not installed in this environment (`ModuleNotFoundError: PyQt6`). No playback/recording/GUI claim is made.
- Full application test suite and ISO build/boot remain outstanding.
