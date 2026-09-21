# v35.22a — native sCode pool-catalog startup fix

- Fixes Linux `run_hybrid.sh` failure: `sCode pool catalog execution failed ... usage:`.
- Stage-0 now executes both `groovebox_optimizer.sC` and `pool_catalog.sC`.
- Linux launcher verifies/repairs stage-0 before starting Groovebox.
- Direct launcher receives the same preflight.
- Bridge has an exact deterministic 18-format compatibility catalog for stale Windows/macOS ABI-9 binaries when no C compiler is available.
- No composition, canonical, sequence, DSP, or randomization behavior changes.
- Stage-0 now also executes `pool_request_probe.sC`; host/native universal-pool descriptor parity tests pass.
