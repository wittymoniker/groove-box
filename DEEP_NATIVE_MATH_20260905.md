# Deep Native Math pass — 2026-09-05

This pass keeps Groovebox mathematics authoritative while reducing representation work.

- Added native Meum-family low-discrepancy traversal using M-1, 1/M, phi-1 and sqrt(2)-1.
- Irrational coordinates remain traversal/phase/index choices only; rational partition weights preserve identity and conservation.
- Added fused native OT add/subtract/multiply/divide/power primitives with explicit zero policy and no epsilon substitution.
- Added a bounded Universal Field projection cache keyed by (field_id, projection kind). Camera/UI repaint work can reuse the same mathematical projection without changing field identity.
- Added explicit cache invalidation helper.
- Added regression parity between portable Python Meum traversal and the C++ kernel.

Performance note: the mathematical constants themselves are not assumed to make a CPU faster. The speed gain comes from their deterministic structure making caching, progressive refinement, precomputation and fused SIMD/native evaluation possible. Whether Meum-family traversal improves an artistic/statistical objective is a separate empirical question and must be benchmarked against rational, golden-ratio and random baselines.

External framework policy: Groovebox does not vendor NASA Trick/cFS or SLEEF code in this pass. NASA simulation architecture remains credited as inspiration. This avoids unnecessary runtime weight and licensing coupling while keeping the native ABI ready for optional vector-math backends.
