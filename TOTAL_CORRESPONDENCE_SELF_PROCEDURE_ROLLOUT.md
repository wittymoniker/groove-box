# Total Correspondence + Self-Procedure Rollout

This build formalizes the Groovebox design rule that representation count is downstream of canonical identity.

## Total correspondence

A single Universal Field is the common source for Audio, Visual, Game, UI, and Network projections. Each domain manifest stores the same `source_field_id`. `correspondence_verify()` rejects a manifest if a domain is re-pointed or if a selective/subtractive visual projection fails to reconstruct the source coordinates.

This is an identity/provenance correspondence guarantee inside the software architecture. It is not a claim that lossy audio/video/network encodings are mathematically invertible.

## Self-procedure

`self_procedure()` measures count-independent intrinsic field structure and chooses downstream representation resolutions for audio, visual, game, UI, and network work. The chosen counts are powers of two for clean hierarchical coarsening/refinement, but any positive part count remains a valid factorization of the same field.

Rational scaling is reserved for identity, exact partitions, conservation, hierarchy, and symmetry. Meum and the other irrational basis values are used for phase, traversal, ordering, coverage, and differentiation rather than defining canonical identity.

The visual self-procedure computes a minimal-ish greedy cover of the Universal Field's displayed coordinate dimensions. Every visual projection remains selective/subtractive: `selected + complement` reconstructs the original field coordinates.

## Diagnostics

The extended live visualizer now shows the Universal Field prefix, self-procedure projection-cover count, and correspondence percentage. Generated games carry `self_procedure_state` and `correspondence_state` in identity data and expose them in runtime reports. Canonical game interactions retain the same upstream field identity while their event-specific UI and experience are generated downstream.

## Tests

The unified test suite includes part-count reconstruction checks at non-power-of-two and power-of-two counts, projection reconstruction, exact domain-source identity checks, and a deliberate tamper test. The current container run reports 17 checks: 16 passed, 1 skipped (optional PyQt6 GUI registry), 0 failed.
