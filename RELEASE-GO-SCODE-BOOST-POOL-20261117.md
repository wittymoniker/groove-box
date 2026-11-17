# Go + sCode workload acceleration — 2026-11-17

- Fixed executable-builder Lua provisioning: the dedicated build virtual environment now installs `lupa` and invokes the Lua runtime preflight before PyInstaller packaging. The old late-stage missing-`lupa` exception now gives a targeted provisioning diagnostic.
- Added Go compiler packages to Linux builder dependency installation and the Debian-based ISO runtime.
- Added a Go `c-shared` oscillator kernel and a Python loader that builds into the per-user cache. Go is exposed to the hybrid router and is eligible only after the existing NumPy parity and speed gate selects it. NumPy remains the reference/fallback.
- Go kernel warm-up is submitted to sCode's hybrid lane during application startup; it does not compile on the Qt event thread or audio callback.
- sCode's diagnostic tree now reports Go accelerator availability and status.
- Retained firmware-managed CPU boost behavior in `performance_governor.py`; no thermal, electrical, firmware, or over-temperature protections are disabled or bypassed.
- Shared thread budgeting remains governed by `thread_budget.py`; Go does not create a competing Python worker pool.

No tests, syntax checks, builds, benchmarks, GUI/audio checks, or hardware validation were run, as requested. Runtime performance and Go toolchain availability on the target machine remain unverified.

## Adaptive compute extension

See `RELEASE-ADAPTIVE-COMPUTE-ENGINE-20261117.md` for the optional GPU dispatcher, bounded memory reuse, content-addressed incremental kernel cache, sCode block-buffer caching, and packaging integration added in the same source pass.
