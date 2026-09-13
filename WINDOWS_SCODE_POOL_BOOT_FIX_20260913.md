# Windows/macOS native sCode pool bootstrap fix — 2026-09-13

This build fixes the startup failure where the native ABI-9 `scode0` executable
was correctly detected and verified, then Groovebox exited while trying to run
`apps/groovebox/pool_catalog.sC` through the deliberately minimal native stage-0.

The native stage-0 remains the required optimizer bootstrap. Its ABI-9 optimizer
plan is verified first. If that compact stage-0 reports its usage message for the
auxiliary pool-catalog program, Groovebox now uses an exact host mirror of the
18-entry sCode pool ABI-3 catalog defined in `sCode/scode/libs/runtime/pool.sC`.
This keeps pool sizes, buffering, streaming and persistence flags identical to
sCode while avoiding a false fatal startup error on Windows/macOS.

The change does not disable sCode and does not replace optimizer execution with
Python. It only mirrors static pool metadata when the native stage-0 does not
expose the auxiliary catalog program as a command.
