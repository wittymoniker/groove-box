# Meum Precision / Native Rollout — 2026-09-05

This pass makes the project-defined Meum root a single numerical source of truth across the Python and C++ runtime.

## Canonical definition and theorem

Mathematical Meum is defined as the unique root `M in (1,2)` of:

`2^M = M^4 + M^2 - M`.

The Help documentation now records `MEUM-T1 — Existence, Uniqueness, and Irrationality`, including the IVT existence proof, strict-decrease uniqueness proof, and unique-prime-factorization contradiction for rational `p/q`.

## Precision implementation

New module: `meum_constants.py`.

It stores:
- a 100+ digit decimal reference for M;
- exact hexadecimal IEEE-754 binary64 M (`0x1.3294a6a84dbb1p+0`);
- pre-rounded binary64 `M-1`, `1/M`, `2-M`, `(M-1)/M`, `M^2`, `M^3`, `M^4`, `2^M`, and the bounded Meum power lattice;
- Decimal references for offline verification;
- cached integer Meum powers and a precision report.

The goal is consistency and speed: no module should independently truncate `1.1975807343...` or recompute hot divisions/powers when a canonical value already exists.

## Native C++

`cpp/groovebox_accel.cpp` now contains matching hexadecimal binary64 Meum constants and exports `gb_meum_constants_f64` for exact Python/native parity tests.

The native Meum traversal kernel uses a long-double start phase followed by additive modular recurrence. This avoids a large-index multiply for every generated coordinate and reduces phase precision loss during progressive traversal.

## Integration

The central constants are now consumed by the main Groovebox engine, Universal Field, Meum/OT math helpers, Signal Lab, canonical event algebra, fractal spatial engine, decentralized mesh, composition state, generated game system, Performance background, and legacy reference entry points.

## Tests

Unified suite after rollout:

`checks=20 passed=19 skipped=1 failed=0`

The only skip is the optional PyQt6 component-registry test in the current test environment. Dedicated precision/native and deep-native tests pass.
