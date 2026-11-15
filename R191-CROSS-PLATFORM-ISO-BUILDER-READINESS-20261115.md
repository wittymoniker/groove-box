# R191 Cross-platform and ISO Builder Readiness — 2026-11-15

## Result

The source-level release preflight and Linux-native accelerator checks pass. A full native desktop executable build and the appliance ISO build cannot be marked passed in this execution environment because required host dependencies are unavailable and package installation cannot resolve the Debian mirror. This report deliberately separates successful structural/synthetic checks from blocked full builds.

## Passed checks

- Runtime source/active ISO overlay: **425/425 files byte-for-byte synchronized**.
- Release markers: **PASS**, R7v / v35.22zz, source fingerprint `7b41b54cc1c2`.
- Active ISO source preflight: **PASS** — 696 Python files parsed, 127 shell files parsed, Dell/Acer hardware-profile contracts passed, and 13 release/source/boot-contract commands passed.
- Bundled Limine 12.9.0 host tool ran successfully. The synthetic x86_64 hybrid ISO fixture was created, BIOS-installed, and re-verified; the EFI FAT payload, UEFI PE architecture, El Torito catalog and hybrid MBR layout passed.
- Linux native C++ accelerator: `scripts/build_linux.sh canonical` **built** `native/libgroovebox_accel.so`; the resulting shared object loaded successfully through `ctypes`.
- Existing Rust accelerator shared object also loaded successfully.
- Linux x86_64 sCode stage-0 executed the Groovebox optimizer and reported `scode_optimizer_abi=9`.
- All six bundled sCode stage-0 binaries were checked against their declared executable formats and CPU architectures:
  - Linux x86_64 and ARM64 ELF
  - macOS x86_64 and ARM64 Mach-O
  - Windows x86_64 and ARM64 PE
- Unix stage-0 files and shell/command launch/build scripts now have executable mode bits. This fixes a real archive-extraction defect that made the Linux optimizer fail with `Permission denied`.
- 167 `.sh`/`.command` files passed `bash -n` and were confirmed executable.
- `BUILD_KIT/build_linux.sh --help` and `BUILD_KIT/build_macos.sh --help` successfully reached the shared builder CLI.
- Windows PowerShell and Batch entrypoints passed static dispatch/exit-code contract inspection on Linux. They were not executed by Windows PowerShell or `cmd.exe`.
- `SKIP_APP_BUILD=1 SKIP_ISO=1 ./BUILD_ALL_V3.sh` passed the top-level overlay-sync, Python syntax/fractal-import, and build-orchestrator path with both expensive build stages explicitly skipped.

## Blocked full builds (not passed)

- The full `BUILD_KIT/build.py --doctor` check stops because `.groovebox-build-venv` has not been provisioned. PyQt6, PyInstaller, and sounddevice are not installed in the provided Python environment. The application executable was **not** packaged.
- `scripts/check_iso_build.py --host-only` stops because `cargo` and `rustc` are missing. The ISO host prerequisite installer attempted `apt-get update`, but package-index retrieval timed out; direct DNS lookup for `deb.debian.org` fails in this sandbox.
- No usable Podman/Docker engine is installed. The zero-state ISO pipeline requires a functioning root container engine.
- The environment also lacks the full image/firmware acceptance tools including xorriso, mksquashfs, mformat, QEMU/OVMF, and Secure Boot signing/verifying utilities.
- Therefore the real appliance image, paired signed/unsigned ISO, independent USB boot paths, QEMU/OVMF boot, installation, and rollback were **not** built or validated.
- This host is Debian Linux x86_64. Actual macOS and Windows executable packaging cannot be executed here; only their bundled stage-0 payloads and builder entrypoint contracts were statically checked.

## Required next action on a properly provisioned host

Run the documented platform dependency installer and `BUILD_KIT/build.py --doctor` on each native OS (Linux, macOS, Windows); then run `BUILD_KIT/build_{linux,macos,windows}` on those native hosts. On an x86_64 Linux release host with Cargo/Rust, Podman or Docker, the ISO toolchain, sufficient scratch space, and required firmware/signing setup, run `python3 scripts/check_iso_build.py --host` followed by `bash BUILD_ISO/RUN_ME_ZERO_STATE.sh` and `bash BUILD_ISO/build_both.sh`. Physical/QEMU/firmware gates must be recorded separately from a successful file build.

## Package ordering

This report and the updated source archive are created **before the post-package unit/regression test pass**. The validations above are builder/readiness checks only; they are not a substitute for the test suite or actual target-OS builds.
