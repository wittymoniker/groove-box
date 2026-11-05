# Fractal Coverage and Design Boundary
## Mathematician's Groovebox — R28.4.9 lineage (2026-10-21)

### What the system is

Groovebox is a **deterministic generative fractal** inside a defined mathematical dialect (Meum / Operator Theory / GOAVA coordinates, five canonical engines, shared renderer, source-driven sidechain, variable EQ, local/global parameter ownership).

From a numeric seed (plus explicit settings) it produces coherent, reproducible:

- music (notes, rhythm, synthesis, automation, sidechain, EQ)
- visuals (scenograph, spectrum, voxel, wavetable projector, etc.)
- interactive game state (planetary kernel, sprite grammar, numerical identity)

The five canonicals (SEEDED · RAND · LOCK · EUCLIDEAN · GOAVA) are order-independent. Their contributions are mixed through the Canonical Morph Bridge. The composition fingerprint is the single source of truth for save / load / export / game classification.

This yields a large, organized, largely non-redundant family of outputs. The structure is self-similar across audio, visual, and game domains.

### What the system is not

It is **not** a universal covering of every possible piece of music, every possible music video, or every possible interactive experience.

- The reachable set is exactly the set of outputs the current engines, oscillators, envelopes, sidechain curves, EQ poles, and morph weights can produce.
- There is no inverse solver that maps an arbitrary target sound (or video, or game) back to “the” unique seed + parameter vector.
- “Any sound given the right seed” is not a claim this architecture makes or can make; a finite parameter space cannot index the continuum of all audio.

### Accurate description

> An organized, deterministic, non-redundant fractal of the musical, audiovisual, and game possibilities that its five canonicals and associated DSP can express from a numeric seed.

That statement is strong, true, and useful. Stronger universal claims are not supported by the implementation.

### Practical implications for further work

Useful directions stay inside the dialect:

- measure and document density of the reachable set
- keep audio / video / game paths on the same shared renderer
- expand vocabulary (oscillators, morph axes) while preserving uniqueness guarantees
- improve transport robustness under long Parametric DJ / automation sessions
- visual layering / transparency only where it improves readability of the existing fractal structure (never as a substitute for stacking policy)

Do not treat “add another engine” or “turn all canonicals on” as steps toward completeness. They expand the dialect; they do not complete it.

### Relation to R28.4.9 work

Source-driven sidechain, shared renderer placement, and the format-converter companion are consistent with the fractal above. They improve coherence and practicality; they do not change the coverage boundary.

This document is the authoritative statement of generative scope for the R28.4.9 lineage.
