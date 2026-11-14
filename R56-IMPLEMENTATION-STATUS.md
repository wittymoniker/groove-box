# MATGROOVEBOX R56 implementation status

- Base: R55.6.2 ISO staging sync source archive.
- Worktree: additive R56 developer/cloud/GOAVA/hardware/migration sweep.
- Scope: 126-part register in `R56-126-EXPANSION-CATALOG.md`.
- Implementation detail: `R56-DEVELOPER-CLOUD-GOAVA-HARDWARE-MIGRATION-PLAN.md`.

## Source changes in this archive

- `groovebox_runtime/command_center.py` — top toolbar and command dialogs.
- `groovebox_runtime/goava_autopilot.py` — bounded stochastic response and self-reinterpolation.
- `groovebox_runtime/hardware_broker.py` — read-only sysfs discovery and explicit-approval broker.
- `groovebox_runtime/hardware_adapters.py` — protocol facades for common creative hardware.
- `groovebox_runtime/extension_api.py` — reusable extension/GUI-item/launcher metadata pool.
- `groovebox_runtime/userdata_migration.py` — checksummed backup, verify and safe restore.
- `groovebox_runtime/update_manager.py` — ZIP-checked user-space update staging.
- `BUILD_ISO/gpt_disk_v32q.py` — separate user-data partition plan.
- `BUILD_ISO/sos-install-appliance-limine-v33a` — preserve/migrate `/home` copyover option.
- `sCode/scode/libs/groovebox/{gui,extensions,autopilot}.sC` and `hardware/{access,devices}.sC` — declarative sCode contracts.
- `tests/test_r56_expansion.py` — focused regression tests.

## Verified in this environment

- 8 focused R56 unit tests passed.
- Python byte-compilation passed for changed modules and the main application entrypoint.
- Shell syntax checks passed for the modified installer, final initramfs stamp scripts and release runner.
- Existing Install-to-SSD, Secure Boot, VFAT copyover, R15 installer and I/O-safety source verifiers passed.
- GPT layout planning passed arithmetic checks at 8, 16, 32, 64, 256 and 1024 GiB.
- 380 runtime module/package sources synchronized byte-for-byte with the active ISO overlay.
- Root and active-overlay `groovebox.py` SHA-256 values match.

## Pending

- PyQt6 is not installed here: no live GUI test.
- The bundled sCode stage-0 binary was not executable in this environment, so the new `.sC` library contracts were not interpreter-tested.
- No full R56 initramfs or ISO build.
- No QEMU/OVMF boot or Secure Boot test.
- No disk installation, copyover, data migration or rollback test on a VM or physical SSD.
- No physical hardware tests; protocol facades require compatible injected backends.
- Update bundles are staged but not signature-authenticated or activated.

**Do not treat R56 as a bootable or installer-certified release yet.** The user should retain an external backup before testing any installer copyover on real storage.


## Dual-mode Limine / six-partition USB integration (source kit)

- Added `BUILD_ISO/build_dualboot_release.sh` to require the direct-sign Limine Secure Boot toolchain, build the Secure Boot and unsigned companion ISOs, verify the signed ISO's ON/OFF menu markers, and publish a named dual-mode ISO copy with SHA-256 manifests.
- Added `BUILD_ISO/create_dualboot_usb.sh` for a shared signed Limine ESP, separate Secure Boot and unsigned ISO archive partitions, and three independent exFAT data partitions. The writer has whole-removable-disk/root-disk/mounted-target guards and two destructive-operation confirmations.
- Added `BUILD_ISO/README-R56-DUALBOOT-SIX-PARTITION-USB.md`.
- Static shell syntax and layout-contract checks passed; the existing eight focused R56 unit tests passed. The complete source preflight also passed: 380 runtime files byte-identical between ISO/BUILD_KIT, release stamps current, Python syntax (687 files), shell syntax (123 files), and 13 release source/boot contract commands.
- **Not yet generated here:** no R56 kernel/initramfs build cache or `BUILD_ISO/dist` ISO artifacts were present in the recovered archive. Therefore no dual-mode ISO file is included in this source-kit revision yet. The release wrapper is the reproducible build entry point on the complete build host.
- **Not tested:** no physical USB write, QEMU/OVMF boot, firmware Secure Boot enrollment, SSD installation, or physical hardware acceptance.
