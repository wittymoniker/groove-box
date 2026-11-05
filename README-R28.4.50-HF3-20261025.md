# Groovebox R28.4.50 HF3 — zero-state runner entry-point packaging repair

**Date:** 2026-10-25  
**Base:** R28.4.50 HF2 source candidate with corrected volume-verifier contracts.  
**Change in HF3:** make the sOS build runner easy to find and reliably executable after ZIP extraction.

## Builder entry points

The complete builder remains at `BUILD_ISO/RUN_ME_ZERO_STATE.sh`. This edition also provides a project-root convenience launcher at `RUN_ME_ZERO_STATE.sh`. The root launcher forwards to the maintained `BUILD_ISO` script. Both entry points are stored with executable permission in the ZIP.

From the extracted `groovebox_rebuild_work` project root, run:

```bash
bash RUN_ME_ZERO_STATE.sh
```

You can also invoke the maintained builder directly:

```bash
bash BUILD_ISO/RUN_ME_ZERO_STATE.sh
```

Keep the entire extracted project tree together; the launcher is not a standalone ISO builder without the other source files. Run it on a supported build host with the required system dependencies and Rust/Cargo toolchain. It may install or provision toolchain components as defined by the existing builder; inspect the script before running it in a restricted environment.

## Included source baseline

HF3 preserves the R28.4.50 HF2 source content: Fractal Seed, deterministic Composition Lab behavior, 72% fresh Master Volume default, saved-volume restoration including explicit 0%, audio routing and verifier-contract fixes, and CRC32C/ext4 installer source lineage. HF3 changes packaging/entry-point discoverability only; it does not claim a newly built ISO.

## Validation performed

- `BUILD_ISO/RUN_ME_ZERO_STATE.sh` exists in the source archive.
- Project-root `RUN_ME_ZERO_STATE.sh` exists and forwards to `BUILD_ISO/RUN_ME_ZERO_STATE.sh`.
- Both entry points carry executable mode 0755 in the archive.
- `bash -n` passes for both entry points.
- ZIP archive integrity check passes and extracted ZIP contains both paths.

No fresh ISO was built or booted in this packaging step. SSD installation, sCode/sOS terminal behavior, physical speakers, and microphone still require target-hardware validation.
