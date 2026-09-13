# Carrier Clear / Silent MP3 Fix — 2026-09-12

Changes:
- Added **Clear Global Carrier** beside the global carrier controls.
- Added **Clear Local Carrier** beside the selected-operator sample controls.
- Local clear only detaches the currently selected operator media/sample.
- Global clear detaches decoded audio, video reference, carrier bindings, carrier slot state, and stale render caches without deleting source media.
- Both clear actions are covered by project Undo/Redo state.
- Video-only carrier imports no longer manufacture a duration-sized silent PCM buffer. They remain visual-only carriers.
- A video that advertises an audio stream but decodes to zero samples now reports an error instead of silently substituting zeros.
- Project load clears stale global-carrier state before applying the saved project's carrier state.
- Saved video carriers restore through the video loader first so both visual identity and embedded audio are preserved.
- Exact-silence audio exports now surface an explicit warning; encoded file size is no longer presented as evidence that audible content exists.

Validation:
- `python -m py_compile groovebox.py` PASS
- `test_carrier_clear_regression_20260912.py` 6/6 PASS
- `test_project_media_contract.py` PASS
- `test_nan_video_exit_regression_20260912.py` 19/19 PASS
- Full GUI launch was not exercised in the packaging sandbox because PyQt6 is not installed there.
