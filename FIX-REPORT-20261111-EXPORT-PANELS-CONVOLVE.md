# Mathematician's Groovebox — export, panel and dependency repair

## Changes

1. **Export dialog re-entrancy guard**
   - `export_mixdown_dialog()` now serializes interactive setup using an instance guard.
   - A second click while a Save/Options dialog is already active is ignored with a status message.
   - The guard is always released in `finally`, including cancel and exception paths.
   - The guard applies only to dialog setup. After a job is submitted, intentional later exports remain independently queueable.

2. **Main-window panel visibility**
   - `fx_panels.make_collapsible()` remains as a compatibility shim for existing callers but no longer creates a checkable/collapsible group box.
   - FX, time-FX, sample-generator and synth-engine panels installed through this helper remain expanded; parent layouts retain control of visibility.

3. **Save-folder dialog responsiveness**
   - `drive_targets.install_file_dialog_support()` no longer probes removable devices or calls `disk_usage()` synchronously while constructing a file dialog.
   - Dialog sidebars expose stable mount roots (`/media`, `/run/media`, `/mnt`, `/Volumes`) instead. Drive detection/validation remains in the dedicated save-target picker and write path.
   - This removes potentially blocking filesystem probes from Live Player / export folder selection.

4. **Global Convolve dependency preserved**
   - The existing `spin_global_convolve` render-stage control, deterministic kernel path, native OLA convolution, FFT fallback and exception isolation remain intact.
   - Neutral default remains 0% (no unintended coloration at startup); explicit user settings activate the stage.
   - No panel-visibility condition was added to the DSP path.

5. **ISO overlay synchronized**
   - Updated `groovebox.py`, `fx_panels.py` and `drive_targets.py` in `BUILD_ISO/app-overlay-v35.22zz/` to match their root sources.

## Validation

- `python -m py_compile groovebox.py fx_panels.py drive_targets.py export_window.py`: PASS.
- New source-contract tests: 4 tests, PASS.
- Broader pytest attempts did not complete within the execution timeout in this environment; no passing result is claimed for those suites.
- Qt GUI interaction, USB hardware, actual audio rendering, PyInstaller and ISO boot were not exercised here.
