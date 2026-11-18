# R104 — Export recovery dependency integrity (2026-11-18)

## Fix
- Persist every scheduled export stage, including `video_mux` stages that intentionally do not need a frozen project document.
- Persist the original job ID and dependency edges for staged exports.
- Restore recovered stages in dependency order, remap old IDs to new in-memory IDs, and defer worker pumping until the complete recoverable graph is reconstructed.
- Keep a recovery record when one of its required stage records is missing rather than launching a final mux prematurely.
- Preserve existing frozen-project, validated live-buffer hint, and resume-from-artifacts behavior.

## Validation
- Added `test_export_recovery_dependency_contract_20261118.py`.
- The two new regression tests pass.
- `python -m py_compile export_scheduler.py r32_finish.py` passes.
- Existing Qt render-queue tests could not be executed in this build environment because PyQt6 is not installed; no ISO mastering or physical-hardware boot test was performed.

## Scope note
This is a targeted reliability fix to the existing export recovery pipeline. It does not claim a complete implementation or validation of every previously discussed UI, automation, parameter-registry, and performance enhancement.
