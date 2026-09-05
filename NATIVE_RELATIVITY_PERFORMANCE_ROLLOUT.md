# Native / Relativity / Performance rollout — 2026-09-05

## What changed

- Added a fused C++ phase builder (`gb_phase_build_f64`) for the live/offline voice path.
  It combines FM scaling, cumulative phase integration, PM offset and static phase
  in one allocation-free pass. The NumPy implementation remains the reference fallback.
- Added `gb_accumulate_f32` for allocation-free future/master bus accumulation.
- Added `gb_ot_div_f64` with explicit zero-denominator policies: zero, one, signed
  infinity, numerator, or caller-supplied solved/fallback value. No epsilon substitution.
- Removed the hidden ±1.5 per-voice ceiling. Closed-form voice amplitude now reaches
  the explicit master hard-clip stage unchanged.
- Removed FM/AM output floors. Negative FM ratio is phase-direction reversal and
  negative AM gain is polarity inversion rather than a silent clamp.
- Native oscillator-bank rendering is AUTO for substantial buffers when the C++
  library is present; `GROOVEBOX_NATIVE_VOICE=off` forces the NumPy reference path.
- Performance has a low-rate deterministic ParametricMathBackground, more opaque
  tab/pane surfaces and a visible `Engine QoS: AUTO` chip.
- Relativity Projection is downstream of canonical identity. It uses original
  Groovebox code implementing standard special-relativity formulas.

## NASA credit and licensing

NASA Trick, cFS and CML were reviewed only as simulation-engineering references for
multi-rate execution, component boundaries, telemetry/state separation and reusable
C/C++ model organization. No NASA source is vendored in this rollout. This avoids
bringing unrelated simulator mass into the realtime audio path and avoids ambiguous
license inheritance. cFS's public distribution is Apache-2.0; Trick uses NOSA 1.3;
any future vendoring must preserve the exact upstream license/notice for that component.

Suggested credit line:

> Relativity projection uses standard special-relativity mathematics. NASA Trick,
> cFS and CML are credited as simulation-engineering inspiration; no NASA source
> code is copied in this release.

## Fidelity contract

Canonical Resonance's legal 0–200% overwrite range remains distinguishable until the
explicit master hard-clip boundary. Domain checks (finite values, valid physical beta,
array bounds, etc.) are not considered musical clamps and remain where required.
