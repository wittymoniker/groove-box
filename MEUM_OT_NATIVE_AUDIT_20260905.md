# Meum / OT Native Audit — 2026-09-05

Production paths were audited for duplicate Meum literals, OT default state, hot trigonometric transforms, native fallbacks, and canonical-vs-representation separation.

## Changes
- OT remains enabled by default.
- Canonical Meum and derived constants remain centralized in `meum_constants.py` with exact binary64 parity in the C++ kernel.
- Added `gb_meum_trig_f64`, a fused native contiguous transform for the project Meum-normalized isn/ics families and book isn/ics transforms.
- `isn_vec`, `ics_vec`, and `book_isn_vec` now automatically use the native transform for buffers >=64 samples when the packaged binary is available, with the exact NumPy formulas retained as the reference fallback.
- Rebuilt and packaged the Linux native binary from the current C++ source.
- Kept ordinary Euclidean trig where it is semantically required (coordinate transforms, conventional waveform definitions, test references). Replacing mathematically non-equivalent operations merely because Meum/OT exists would change the project rather than optimize it.

## Correctness policy
Optimization is allowed only when it preserves the owning formula/canonical identity. Meum-family irrational values are used for phase/traversal/index differentiation; rational quantities remain authoritative for exact partition/conservation. No claim is made that Meum makes a CPU instruction intrinsically faster.

## Validation
The unified suite passes 19/19 available checks with one optional PyQt6 skip. Native trig was separately compared against the reference formulas over 200,000 samples per mode.
