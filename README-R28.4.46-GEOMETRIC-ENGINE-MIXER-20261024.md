# Groovebox R28.4.46 — Geometric Engine Mixer

Adds a compact mixer deck directly beneath the geometric synth/engine row:
- Vector gain default 0.80
- Wavetable gain default 0.75
- Bouncing Ball gain default 0.65
- Cellular Automata gain default 0.70
- Shared deterministic cross-mod depth default **0.0024** (range 0.0000–0.0200)

The four synths retain their existing 50% canonical / 50% user balance contract; these are separate lane-trim controls. Values are included in project state and restored on project load. Changes participate in the canonical live-source update/debounce. `MainWindow._geometric_mixer_snapshot()` provides a normalized bounded snapshot for synthesis/mixer consumers.

Validation: `groovebox.py` passes Python bytecode compilation. UI launch, sound-device playback, and actual per-synth gain/cross-mod DSP integration were not runtime-tested. The current application source does not yet route all four geometric synths through a single rendered PCM output path, so this patch establishes the controls, persistence, and consumer snapshot API without claiming end-to-end audible lane mixing is verified.
