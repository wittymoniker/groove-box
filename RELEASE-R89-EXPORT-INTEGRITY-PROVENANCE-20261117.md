# R89 — Export Integrity & Contribution Provenance

Date: 2026-11-17
Base: user-supplied `matgroovebox(2).zip` (R88 source tree)

## Completed

### Export integrity
- Added `export_integrity.py` for post-write verification of export files.
- Records file size and SHA-256, checks WAV RIFF/chunk structure (including PCM and IEEE-float WAV), validates NumPy arrays and rejects non-finite samples, checks MP4-family/Matroska/FLAC signatures, and uses `ffprobe` for media parsing when available.
- Export worker now verifies completed audio, WAV, NumPy, stem, project-object, video, video-mux, and segmented-video outputs before writing success metadata / emitting DONE. Segment outputs are individually checked.
- Verification failures fail the export job rather than being reported as successful.
- Integrity reports are included in export metadata for downstream inspection and recovery.

### Provenance display
- Extended the read-only provenance badge to show Seed (S), Canonical (C), User (U), Step (P), and effective/net (N) contributions.
- Expanded local/global FX and time-FX contribution reports to retain the source values and effective value, and attached those read-only badges to their controls.
- Preserved existing Multidim and global/step tuning provenance paths; badges remain mouse-transparent and do not alter synthesis values.
- Added a generic `attach_tree` helper for future panels to bind controls to explicitly supplied provenance records.

### ISO/runtime payload
- Synchronized `export_worker.py`, `export_integrity.py`, `parameter_provenance_ui.py`, and `fx_panels.py` into `BUILD_ISO/app-overlay-v35.22zz/`.

## Targeted validation performed
- `python -m py_compile export_integrity.py export_worker.py parameter_provenance_ui.py fx_panels.py`
- `pytest -q test_r89_export_integrity.py test_r82_provenance_ui_contract.py`
- Result: 7 passed.

## Not claimed / still requires release validation
- No full Qt GUI session, real project export across every supported codec, long-form export stress test, full ISO build/boot, or physical USB-to-SSD installation was run.
- `ffprobe` validation is performed only when `ffprobe` is installed; otherwise media container signatures, size and SHA-256 are still checked and metadata marks the decode check as unavailable.
- This release adds integrity verification after the worker writes outputs; it does not yet implement automatic repair of corrupt media or an independent second-pass audio decode for every codec.
