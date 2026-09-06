# External engineering references / NASA credit

Mathematician's Groovebox contains **no copied NASA simulator source code** in the
relativity/native-performance additions in this release. The implementation is
original Groovebox code built from standard mathematical formulas and general
simulation-engineering techniques.

NASA projects consulted as engineering references:

- NASA Trick Simulation Environment — C/C++ simulation jobs, multi-rate execution,
  logging and real-time performance engineering.
- NASA Core Flight System (cFS) — component boundaries, message-oriented state,
  health/telemetry style separation. The public cFS distribution is Apache-2.0.
- NASA Common Model Library (CML) — reusable C++ simulation model organization.

The optional `relativity_projection.py` uses standard special-relativity formulas
(Lorentz gamma and longitudinal relativistic Doppler factor). It is a downstream
Performance projection and **does not alter the canonical Universal Field ID**.

Credit line for UI/docs when Relativity Projection is enabled:

> Relativity projection: standard special-relativity mathematics; NASA simulation
> ecosystems (Trick/cFS/CML) credited as engineering inspiration. No NASA code copied.

Always inspect the license of any future NASA repository before vendoring code.
Government-authored U.S. works can be public domain domestically, but NASA software
may also contain contractor/third-party material or be distributed under a specific
license such as Apache-2.0 or NOSA.

## Math-notation display convention

Math Symbols defaults ON. Author glyphs use 4×3 directional strokes, U/R/D/L pathways, straight=full count, missing=skip, and context-sensitive squiggles (imaginary/decimal/half/doubling); operation/continued/multiplicity enclosures and semantic role colors carry additional context. Math Symbols OFF exposes conventional/base-10 notation; Operator Theory is an independent backend toggle. See `HELP_TEXT.md` → **Author Symbol Language — literal reading guide** for the literal and ASCII grammar and equation-by-equation examples.

