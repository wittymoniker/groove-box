# Groovebox R28.4.48 — Canonical chord-budget UI/source patch

This patch adds sequence-local chord metadata defaults, a deterministic per-instrument chord-note ticker, the `floor(512 / participating instrument count)` budget calculation, and green step-cell subdivision styling. The main `groovebox.py` is copied into the `v35.22zz` active overlay to keep those two source copies synchronized. The patch includes a static contract test.

## Verification performed
- `python -m py_compile groovebox.py` passed.
- `python -m unittest test_canonical_chord_budget_r28_4_48.py -v`: 6 tests passed.
- Master-volume handler static contract: it writes the scalar gain and mirrors UI values, with no stream stop/close/start call in that handler.

## Important limits
This is a source-level patch, not a verified runtime release. No Qt GUI/audio-device integration test, physical audio test, ISO build/boot, or project round-trip test was run. The chord intervals and budget are currently stored and exposed in the sequencer UI; this patch does **not** establish that all synthesizer render paths play every chord tone. The reported master-volume stream failure is not reproduced or proven fixed by the static handler check. Do not treat these as complete until runtime audio, chord rendering, and save/load round trips are tested.
