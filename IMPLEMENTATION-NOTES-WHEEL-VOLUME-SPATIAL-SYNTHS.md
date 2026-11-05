# Groovebox spatial synth / slider / volume patch (work-in-progress)

## Implemented in this patch
- Added `spatial_synth_engines.py`: deterministic polynomial gravity, circular bouncing-ball simulation, and multi-state cellular automaton generation with explicit transition rules. The engines return structured, repeatable data suitable for canonical/playlist adapters.
- Added regression tests for deterministic output, polynomial evaluation, circular bounds, and multi-state rules.
- Added an application-level Qt event filter to consume wheel/trackpad wheel events on QSlider and QDial controls while preserving normal scrolling and direct dragging.
- Changed main logical master-volume defaults to 100%, and synchronizes the visible Performance slider/label immediately when the main scalar is updated. The hidden compatibility slider remains hidden and is not a second visible master control.
- Mirrored source changes into the v35.22zz build overlay.

## Not yet complete / not claimed
- The new synth engines are not yet wired into the two Performance diagnostic panels, canonical persistence, UI drawing/throw gestures, Math Lab, Composer Lab, Heuristics, Algorithms, or playlist playback.
- Audio/video/game integration and end-to-end playback regressions have not been verified.
- No ISO was built by this patch.

## Validation performed
- `python -m py_compile groovebox.py performance.py spatial_synth_engines.py` passed.
- `python -m unittest -v test_spatial_synth_engines.py` passed (3 tests).
- Hardware playback, recording, MicroSD mounting, UI interaction, and ISO boot/install were not tested here.
