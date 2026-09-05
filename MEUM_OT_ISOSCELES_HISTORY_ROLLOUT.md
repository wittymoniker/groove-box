# Meum / OT / Isosceles + History Rollout

Added `meum_ot_math.py`, temporal seed dynamics, semantic GOAVA scribing, numerical gameplay sound identities, character/home starter compatibility, and `.MG` history compression/clear helpers.

Math from the supplied book is retained as an author-defined Groovebox dialect for deterministic creative indexing; conventional arithmetic is not globally replaced.


## 2026-09-05 — Meum + Operator Theory + Isosceles-Trig integration

Groovebox now treats the author's mathematical writing as a **selectable creative/analytic dialect** for deterministic indexing. It does not silently redefine ordinary Python/IEEE arithmetic. The implementation is designed so these transforms can be inspected, disabled, simplified and reversed.

### Meum basis
The principal constant used by the engine is `M = 1.1975807343…`. The default modulation vocabulary includes `M-1`, `1/M`, `2-M`, `(M-1)/M`, plus independent irrational traversals `e-2`, `phi-1`, `sqrt(2)-1`, and `pi-3`. Meaningful identity values `0`, `0.5`, and `1` remain unchanged when they mean OFF, symmetry, or unity.

### Isosceles trigonometry
The book defines inverse isosceles sine as `isn^-1(x) = 2 asin(x/2)`. Groovebox also exposes the inverse-pair coordinate `isn(theta)=2 sin(theta/2)` for bounded seed phase mapping. `ics/ics^-1` are kept as handedness-aware complementary coordinates for spatial/game modulation. These functions are used for *indexing and geometry*; they do not overwrite ordinary `sin/cos` globally.

### Operator Theory (OT)
For reversible transforms, Groovebox implements the book's stated symbolic inverse pairing: add↔subtract, multiply↔divide, power↔root, with operation order reversed for an inverse path. This is especially useful for the writer-toggle zero-state rule: active transforms are collected, simplified to one canonical transform, evaluated once, and their provenance is preserved separately.

### Temporal Seed Dynamics
Generated games now include deterministic **Build → Modulate → Stabilize** epochs. Their boundaries use Meum-derived proportions and their field values use the isosceles phase mapping. This adds evolving seed character without activation-history dependence.

### Numerical gameplay identity
Items, actions, events and starter-world elements now receive deterministic numeric sound signatures from seed + semantic label + Meum/isosceles indexing. Frequencies, durations and harmonic counts are inspectable, repeatable and tied to the generated identity instead of random sound assignment.

### Longitudinal .MG history
`.MGproject`, `.MGsynth` and `.MGprofile` analytics remain separate from Artifact ID. History may now be **compressed** (retain strongest companion relations and summaries) or **cleared** without changing the saved program/synth/profile identity. Clearing can preserve aggregate totals so long-term statistics can be retained without carrying detailed co-use history.

### Source framing
The in-app math help preserves the terminology and claims of the author's supplied papers as author-defined/theoretical material. Groovebox uses these ideas as deterministic compositional and geometric transforms; this software implementation is not itself an external proof of the broader mathematical or physical claims.

## Universal selective/subtractive field
`universal_field.py` centralizes the count-independent field and the rational/irrational scaling policy.  Part objects are 1/N additive shares; the game and visualizers project from the same upstream state independently.  The game is a consumer, never the source of visual identity.

History UI now includes **Export History** alongside **Compress History** and **Clear History**. Exports support JSON, CSV, and HTML and do not mutate the `.MG` artifact.
