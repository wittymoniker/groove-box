# R123 phase 7D — UNVERIFIED (shipped before tests on request)

Status: code-complete, NOT test-verified. GUI, export, target-rootfs, full ISO build and boot/installer
acceptance have not been re-run for this phase.

Changes
- Global Convolve: full Meum geometric lattice (about 160 Hz–20 kHz, flat within about 3 dB; the old kernel passed 320–640 Hz).
- Multidim: equidistant ensemble-slot spread (count-aware canonical params).
- harmonic_spacing_ratios: first 48 unchanged; beyond 48 folds into the 6-octave window (512 unique ratios).
- Polynomial Markov: prepared once per run (about 10× faster, identical traces).
- New Markov Resampler: markov_resampler.py (core) + markov_resampler_window.py (editor);
  main-window panel "⛓ MARKOV RESAMPLER"; canonical binding; Apply/Undo; spec saved in the project.
- Canonical Morph Bridge split in two halves and centred in the row [Geometric Mixer | Bridge | Markov].
- Long sliders shortened (Play Patcher amounts in one row of four; top Geometrics slider capped and centred).
- Every pane, including the r32 deck, takes the workspace pane colour (default blue_gray #53677a).
- FIX (pre-existing): canonical rebuild wiped user-edited sequences (randomize/clear/undo) back to the boot
  slate while any canonical engine was active; undo of sequence edits therefore failed too.
- HELP_TEXT (in-app + HELP_TEXT.md) updated; ISO overlay payload re-synced.

Smoke-checked by hand only: Markov window preview/apply/undo, determinism, canonical LOCK binding,
rebuild keeps randomized sequence, slider widths ≤ 1300 px on the main pane.
