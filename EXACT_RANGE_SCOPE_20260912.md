# Exact Range Scope — 2026-09-12

Groovebox mathematical/domain scope now follows these rules:

- Test exact zero as `x == 0` / `x != 0` when zero is the mathematical boundary.
- Check lower and upper bounds independently against the real domain minimum/maximum.
- Do not promote zero to epsilon (`1e-9`, `1e-12`, etc.) merely to avoid a branch.
- Do not use huge finite numbers (`1e9`, `1e99`) to mean unbounded; use `math.inf`/explicit state.
- Preserve exact zero weights, durations, vectors, carrier activity, and modulation amounts.
- Numerical solver convergence tolerances and deliberate signal-analysis confidence thresholds remain tolerances; they are not range-scope substitutes.
- Display floors (for example -120 dBFS) remain display policy only and never alter the underlying signal.
