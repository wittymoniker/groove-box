# Groovebox sCode Full Acceleration — ABI 5

This appliance requires the bundled sCode runtime. sCode is not a decorative sidecar: ABI 5 supplies deterministic logic/number casting, pool routing, dirty-state gates, coalescing, cadence lanes, work identities, and reusable result/array pools that are consumed by Groovebox host hot paths.

## Integrated consumers

- Canonical recomposition: duplicate mathematical/project identities are rejected before deep-copy/reconciliation work; project load/recompose explicitly invalidates the claim.
- Canonical sequence runtime: identical sequence payloads are coalesced before document/fingerprint rewrites.
- Scenograph: the 15 FPS acceptance gate now occurs before waveform resampling/analysis; sCode cadence routes accepted visual work.
- Math background and monitors: editing QoS suppresses decorative repaint pressure and sCode lanes stagger spectrum/scenograph/HUD work.
- Author numeric symbols: per-field cached glyph adapters no longer force-regenerate unchanged glyphs during global refresh.
- Layered Draw/Record/Sample media: sCode memoizes deterministic reconstruction and spectrum results; decoded source media has a bounded cache keyed by path, modification time, size, sample rate, and target length.
- Parametric Remix: validated expressions compile once per script text and control updates coalesce into one host remix push per tick.
- Game identity: deterministic classification is memoized by complete game-composition payload.
- Audio render/export: deterministic time grids and row scratch buffers are reused; row scheduling uses index slices instead of allocating a full-song Boolean mask for every playlist row.

## Realtime audio rule

No sCode subprocess, parser, or IPC is placed inside the per-sample/realtime audio callback. sCode removes redundant work around the callback and routes deterministic render/scheduling work. Existing NumPy/native C++ kernels remain the hot DSP execution path where they are faster.

## Measured isolated hot-path benchmark in the release container

See `FULL_SCODE_ACCEL_BENCHMARK.txt`. The measured examples include cached optimizer planning, repeated layered-media reconstruction reuse, and playlist-row scheduling setup. These are microbenchmarks of specific paths, not a claim that the complete GUI/application has the same multiplier.

Whole-application FPS, audio underrun rate, UI latency, and export time should be benchmarked on the target Fedora/sOS hardware because GPU, display server, PortAudio/PipeWire, storage, and project complexity materially affect end-to-end speed.

## Validation scope

The release performs Python static compilation and executes bundled sCode ABI/runtime/parity tests. The build environment used for release packaging does not have PyQt6 installed, so the complete GUI was not interactively executed there. The appliance installer verifies PyQt6 and the remaining runtime dependencies in the target rootfs before finalizing the image.


## Author-number codec acceleration

ABI 5 makes `base16-squiggle-subscale-v4` part of the required sCode contract. The runtime verifies base 16, semantic full-cycle cell 16, in-cell half/squiggle denominator 2, 4 bits of subscale per added cell, and all 68 precomputed value/squiggle/spacing variants. Groovebox memoizes immutable value-spelling packets in the sCode-selected symbol pool, dirty-gates unchanged fields before the codec, and composes cached Qt cell faces rather than re-running vector semantics per field. `gb_symbol_fraction_cell()` and the weight/spacing helpers expose the same `2^-4k` and spaced `1/1` versus unspaced `1/2` rules natively in sCode.
