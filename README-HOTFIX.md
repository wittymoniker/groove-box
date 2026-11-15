# R64 RC6 R56 builder sync hotfix

This is a targeted patch, **not a complete MATGROOVEBOX source distribution**.

## Change

`BUILD_ISO/RUN_ME_v35_22.sh` now explicitly runs the following in the required order:

1. `bash "$BI/sync_overlay_to_root.sh"` (existing conditional overlay import)
2. `python3 "$ROOT/scripts/sync_runtime_payload.py"` (new explicit runtime refresh)
3. `python3 "$BI/verify_r56_expansion.py"` (existing source-contract preflight)

The new runtime refresh is placed immediately after the overlay-sync guard and before hardware/source preflights. The verifier is retained; no checks are bypassed. The existing opt-in R56 unit-test behavior is unchanged.

## Apply

Extract this hotfix archive, then run:

```bash
/path/to/MATGROOVEBOX-R64-RC6-R56-SYNC-HOTFIX/apply-hotfix.sh \\
  "$HOME/Downloads/MATH_GROOVEBOX-v3"
```

The script creates a `.before-r56-sync-hotfix` backup before replacing the runner.

This replacement was reconstructed from the user's supplied 180-line `sed` output. No syntax tests, unit tests, ISO build, or hardware tests were run, per request. A full refreshed RC6 ZIP/TAR requires the original complete RC6 archive; it was not present in this working session.
