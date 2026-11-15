# MATGROOVEBOX R64 finalization checkpoint — 2026-11-14

## Candidate status

This is an updated **R64 source release candidate**, not a certified final
appliance release. The last Fedora-host report stopped before ISO construction
because `BUILD_ISO/RUN_ME_v35_22.sh` invoked a helper omitted from the FIX7
apply-ready patch. FIX8 repairs that packaging defect.

## Changes present in the source tree

1. `BUILD_ISO/secure_boot_v1.sh` avoids copying the live EFI loader onto itself.
   It reads the loader back from the Limine FAT image, compares it byte-for-byte
   with the signed standalone loader, and verifies the read-back signature.
2. `BUILD_ISO/RUN_ME_v35_22.sh` invokes
   `BUILD_ISO/sync_overlay_to_root.sh` before build stages, refreshes the
   403-file runtime payload from canonical root sources before source preflight,
   and retains the later root-to-overlay synchronization before remastering.
3. `BUILD_ISO/sync_overlay_to_root.sh` safely imports overlay-only source files
   into the project root; existing root files win conflicts and are not
   overwritten. FIX8 ensures the helper is included by the apply-ready patch.
4. R56 unit tests remain opt-in (`GROOVEBOX_RUN_R56_TESTS=1`) and are skipped by
   default, consistent with the instruction to defer the comprehensive suite
   until the R64 finalization pass.
5. The active 403-file runtime payload includes the canonical versions of
   `dev_overlay.py`, `groovebox_subprocess.py`, and `import_fabric.py`.
6. The six-partition USB writer extracts the signed and standard kernel/initramfs
   pairs, generates its own three-choice Limine menu, pins all four boot files
   with BLAKE2b-512, enrolls the USB menu hash, signs and verifies the USB EFI
   loader, then asks for two explicit erase confirmations before partitioning.
   The menu distinguishes signed Deployment/Enforcing boot, signed boot with
   firmware Audit Mode already selected, and standard boot with firmware Secure
   Boot disabled. The menu does not change firmware policy.
7. `build_dualboot_release.sh` documentation now points to the separate USB
   writer rather than claiming that no USB selector exists.

## Checks completed for this candidate

- Python byte-compilation: 1,185 source files.
- Shell syntax: 165 shell scripts passed `bash -n`.
- Secure Boot source contract: 21/21 checks passed.
- Shared USB selector source contract: 14/14 checks passed.
- Exact-range / zero-handling source contract: 18/18 checks passed.
- R56 source/overlay verifier passed, including byte-for-byte parity of the
  403-file runtime payload.
- FIX8 was applied successfully to a disposable full-project copy after the
  `sync_overlay_to_root.sh` helper was deliberately removed; the installer
  restored it at the exact path invoked by the release runner.
- Overlay import fixture passed: an overlay-only file was imported and an
  existing conflicting root file was preserved.
- ZIP/TAR.GZ archive integrity and SHA-256 sidecars are generated for FIX8.

The comprehensive project test suite was not run. This preserves the prior
instruction to defer it until the R64 finalization phase; the checks above are
syntax, static-contract, and focused regression checks only.

## Remaining gates — not certified here

- No new signed or unsigned ISO was built in this environment. The build still
  requires the actual Fedora host's compiler/container/image utilities,
  initramfs inputs, Secure Boot signing key/certificate, and firmware tooling.
- No final ISO signature, Limine hash pins, ISO9660/FAT contents, or paired
  artifact hashes have been verified from a post-FIX8 build.
- No QEMU/OVMF boot, Secure Boot key enrollment, firmware Audit Mode test,
  Deployment/Enforcing Mode test, installer/migration/rollback test, or physical
  Dell Latitude 3510 / Acer Nitro 5 test was performed here.
- The USB selector has static source-contract coverage but has not been run on
  a physical USB disk or booted on target hardware. It is destructive and must
  only be run after the host has produced and verified both ISO inputs.
- The R57–R64 register still contains 64 planned items: 21 foundations marked
  partial and 43 marked not implemented at the current planning cut. The
  broader application roadmap is not complete merely because this build-chain
  packaging defect is fixed.

## Fedora host action

Apply `MATGROOVEBOX-R64-RC1-FIX8-PATCH` to the existing project, verify that
`BUILD_ISO/sync_overlay_to_root.sh` exists, and then retry `sudo bash
./build_both.sh`. Retain the full log and generated artifact hashes. If the next
run fails, diagnose that new failure from its exact output rather than
re-running the same command repeatedly.
