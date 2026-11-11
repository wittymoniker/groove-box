# Mathematician's Groovebox — stability patch (2026-11-08)

## Changes made

- `multidim_ui.py`: separated the multidimensional main panel's host/model synchronization from its 40 ms animation tick. The model pull and clone-rack synchronization now run on a bounded 120 ms timer; the animation tick only advances animation and hover repaint state. The animation timer uses Qt's precise timer type.
- `groovebox.py`: project snapshot application now enters an explicit `_project_loading` guard, stops any running Boost Beats timer, and forces the transient live Boost Beats state off while the project is being restored. `_arm_pkp_boost_beats` ignores activation signals emitted during that restore window. The guard is cleared in `finally`, including exceptional loads.
- `render_queue.py`: replaced the synchronous queue loop and nested `QApplication.processEvents()` pumping with a timer-driven queue state machine. It dispatches one preset per Qt event-loop turn, restores the QMessageBox hook after each job, and reports a consolidated result. The actual audio/video render workers remain the existing worker-process/thread implementations.
- Added `test_threading_stability_patch_20261108.py` with source-level regression checks for these three changes.

## Existing off-UI export infrastructure observed

The archive already contains `export_worker.py`, which reconstructs a project in a separate process, snapshots render inputs, assembles the mixdown buffer, and writes the `.npy` buffer and metadata outside the interactive GUI process. The main application also contains QRunnable/QThreadPool and dedicated executor paths for audio/video and other background work. This patch preserves those paths rather than replacing them.

## Validation

- `py_compile` passed for `groovebox.py`, `multidim_ui.py`, `render_queue.py`, and `export_worker.py`.
- Pytest execution was attempted for the existing render-queue, export-snapshot, multidimensional, and project-state tests. Collection stopped because this environment does not have PyQt6 installed (`ModuleNotFoundError: PyQt6`). GUI/runtime, audio-device, hardware, and real project-load tests therefore remain unverified here.

## Important scope note

This is a targeted stability patch, not a claim that every UI callback and every export path in this very large application has been exhaustively proven nonblocking. In particular, the project snapshot restore still contains synchronous widget/state restoration and media decode work; safely moving that whole operation off-thread requires separating pure data preparation from Qt widget mutation. Qt widgets must remain on the GUI thread. The patch avoids an unsafe blanket thread migration that could introduce new crashes or audio regressions.

## Bottom-pane layout refresh (2026-11-08)

- Added a full-width, high-visibility **OPEN LIVE PLAYER** launcher to the lower workspace; the duplicate small Live Player entry was removed from the Play & Media list.
- Replaced the four lower launcher groups' multi-column button grids with one vertical column of full-width controls. Groups retain their colour-family headings, and the main Live Player action remains visually distinct.
- Split the previous extra-wide lower toolbar into aligned status, transport/export, and video/project-tools rows, stacked vertically. Removed the stale fixed 2400 px lower-canvas width; the monitor canvas retains its own 1600 px minimum so its intended three-monitor layout is preserved.
- Added source-level layout regression tests. Runtime visual inspection still requires Qt on the target desktop.

## ISO/runtime synchronization and verifier repair (R30.1, 2026-11-08)

- Refreshed `BUILD_ISO/app-overlay-v35.22zz` from the canonical root runtime inventory with `scripts/sync_runtime_payload.py`. The current inventory contains **140 runtime Python modules**; `scripts/sync_runtime_payload.py --check` now reports byte-for-byte equality. A SHA-256 inventory is stored at `BUILD_ISO/runtime-payload-manifest-20261108.json`.
- Fixed the nested-quote f-string in `clip_timeline_studio.py`'s FFmpeg `blend` graph expression and synchronized the corrected source into the active ISO overlay. The expression uses a distinct quote style that is compatible with the OS's Python parser baseline.
- Replaced the legacy `this device\'s address` f-string in the retained `app-overlay-v35.22zt`, `app-overlay-v35.22zu`, and `app-overlay-v35.22zy` `performance.py` files with `%` formatting, preserving the status message while avoiding the historical parser incompatibility.
- Kept the existing `verify_hardware_profile_20261108.py` invocation in `BUILD_ISO/RUN_ME_v35_22.sh` and added an explicit `PASS: Dell Latitude 3510 hardware-profile preflight` line immediately after it.

### R30.1 validation

- PASS: all 140 canonical runtime modules match the active v35.22zz ISO overlay byte-for-byte.
- PASS: Python compilation for the nine modified/synchronized source files (canonical and active files, plus retained zt/zu/zy `performance.py` inputs).
- PASS: Dell Latitude 3510 32 GB hardware-profile verifier.
- PASS: v35.22zt Performance/audio source verifier.
- PASS: v35.22zu Wayland/window-session source verifier.
- PASS: v35.22zy Qt hardware and file Move/Copy Over source verifier.
- PASS: shell syntax check for `BUILD_ISO/RUN_ME_v35_22.sh`.

These are source/build-contract checks. They do not constitute a completed ISO build, target-hardware boot test, or full Qt/audio runtime test.

## R30.2.1 Live recording and screen-recorder follow-up (2026-11-08)

- Moved the Live Recorder's FFmpeg/MCC video sink initialization to a dedicated
  startup worker. The Qt callback only requests recording; codec/process startup
  no longer executes inline on the GUI thread.
- Added an audio-sample counter to the Live Recorder tap. Scene-frame deadlines
  now follow the same rendered sample clock as the captured audio, rather than
  wall-clock time, so GUI stalls and CPU-mode changes do not change AV timebase.
- Moved screen-recorder output-directory creation into its FFmpeg worker; opening
  and starting the capture session no longer performs that filesystem operation
  on the Qt event thread.
- Updated Live Recorder regression tests to reflect the current bounded queue,
  frame ownership and DJChain toggle contracts (rather than removed private
  fields from an earlier implementation).

### R30.2.1 validation

- PASS: 23 focused tests covering screen-recorder MP4/MKV/WebM/GIF encode and
  ffprobe inspection, sCode pool/concurrency, Live Recorder sample-clock timing,
  bounded owned frames, background encoder startup, DJ filter bypass, Live Jam,
  bottom-pane layout and R30.1 stability guards.
- PASS: Python compilation for the eight changed runtime modules.
- PASS: all 142 canonical runtime modules byte-for-byte match the active
  v35.22zz ISO overlay.
- PASS: Dell Latitude 3510 32 GB hardware-profile verifier.
- PASS: retained v35.22zt Performance/audio, v35.22zu Wayland/window-session,
  and v35.22zy Qt hardware/file-action source verifiers.
- PASS: shell syntax check for BUILD_ISO/RUN_ME_v35_22.sh.
- NOT RUN: interactive Qt GUI, physical audio/video devices, target Dell runtime,
  full ISO build, recovery USB boot, and installed-OS update/rollback tests.
  PyQt6 is not installed in the packaging environment, so Qt integration
  runtime behavior must be validated on the target machine.
