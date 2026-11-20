# R123 phase 7C — UNVERIFIED candidate

Builds on phase 7 flight B. Not accepted until the real GUI, full ISO build, boot and installer steps pass on hardware.

## Changes
- Selected-instrument dropdown (top of the main window): every row is painted in that instrument's assigned
  colour (the same colour as the playlist tint / "■ Playlist colour" button), with WCAG-contrast text; the
  closed selector's frame follows the current instrument. Works under the app stylesheet that makes item
  backgrounds transparent (custom delegate). Test: `test_r123_instrument_dropdown_colors.py`.
- ISO builder: `bootstrap_clean_tree_v33c.sh` retries the runtime container with `--network=host` when bridge
  networking cannot start (netavark/nftables failures on WSL2, nested VMs, minimal servers) unless
  `GROOVEBOX_CONTAINER_NETWORK` is set. Test: `BUILD_ISO/test_r123_container_network_fallback.py`.
- Exported-game dependency installers (videogame_engine.py, Linux + macOS): PEP 668-safe pip
  (`--break-system-packages` fallback) and a codec placement step that never relinks ffmpeg onto itself on
  merged-/usr systems or Intel Homebrew (the old `ln -sf` fallback could replace the real binary with a self-link).

## Evidence gathered in the build sandbox (QEMU TCG, OVMF with Microsoft keys, Secure Boot ON)
Test ISO = R123 shim chain + real Ubuntu 7.0 kernel + placeholder initramfs (BUILD_ISO/docs/evidence-r123/):
- Key not enrolled: shim (Microsoft-signed) runs, refuses the Groovebox-signed Limine with
  "Verification failed: (0x1A) Security Violation", then opens MokManager ("Enroll key from disk").
- Groovebox certificate trusted: firmware → shim → signed Limine → signed kernel starts (then panics on the
  placeholder initramfs, as expected).
- BUILD_ISO verify scripts: same pass/fail set as the pristine upload except 15 that now pass; remaining failures
  need built artefacts (ISO, rootfs, runtime cache) or are pre-existing stale contracts.

## Not done here
- No full ISO build: it needs 8 GB scratch plus runtime cache and five ISOs (24 GiB USB layout); this sandbox has
  about 9 GB free, 2 CPUs and no KVM. No ISOs are attached. No real-hardware boot test.
- R119 performance suite, Task Bar refresh verification, UI comfort pass remain open.
