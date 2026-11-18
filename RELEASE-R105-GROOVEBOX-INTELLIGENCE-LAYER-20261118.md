# R105 — Groovebox Intelligence Layer

## Added

- `groovebox_intelligence.py`: a UI-toolkit-independent service layer for a unified parameter registry, deterministic source arbitration, parameter destination coverage, deterministic pattern variation, mathematical motif discovery, read-only Canonical conformance, rational cross-media timing, project integrity checks, content-addressed preview caching, export checkpoint validation, adaptive worker budgeting, performance scene capture/recall, and side-effect-free project preflight.
- `project_schema.py` schema 4: persists performance scenes, the parameter registry manifest, and intelligence settings; migrates schema-3 projects without discarding existing or unknown state.
- `export_scheduler.py`: applies the shared conservative CPU/RAM worker budget while retaining the existing scheduler's lower caps and fallback behavior; completed prerequisite stages stamp downstream queue records with output paths and content fingerprints.
- `r32_finish.py` export queue schema 5: validates completed prerequisite outputs by content hash before allowing recovery to treat a pruned dependency record as complete. Missing or altered checkpoints keep dependent stages held for inspection; schema-4 recovery remains backward-compatible.
- Regression tests for deterministic variation, registry arbitration and round-trip, coverage reporting, clock conversion, motif discovery, Canonical read-only comparison, project-state migration, adaptive worker limits, and preflight.

## Invariants

- No ambient or true-random probability is introduced. Pattern variation derives all choices from BLAKE2 hashes and preserves event count, pitch, onset, and duration.
- Canonical conformance is diagnostic and read-only; it does not write into Canonical Result/Profile or live composition state.
- Performance scenes capture and restore through the existing `project_schema` state contract rather than a parallel project serializer.
- Cross-media clock conversion uses rational arithmetic and integer ticks.
- Export recovery dependency persistence from R104 remains intact.

## Scope and validation

This release supplies the shared backend APIs and project persistence contract. It does not claim that dedicated GUI panels for every diagnostic or scene workflow have been wired into the application, nor that full media rendering, PyQt runtime, ISO mastering, or physical hardware boot has been validated in this environment.
