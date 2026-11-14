# Dual-boot ISO delivery status — R57/R64

## What is present

- `BUILD_ISO/build_both.sh` builds the Secure Boot and unsigned ISO variants from the source build pipeline.
- `BUILD_ISO/build_dualboot_release.sh` wraps that paired build and produces a signed-Limine ISO carrying the current dual-policy menu (`sos.secureboot=on` and `sos.secureboot=off`). The standard/NSB path still requires firmware Secure Boot to be disabled manually; software cannot toggle the firmware setting.
- `BUILD_ISO/create_dualboot_usb.sh` defines a six-partition GPT UEFI USB layout: shared Limine ESP, Secure Boot ISO archive, unsigned ISO archive, and three independent exFAT data volumes.

## What is not present in this archive

- No completed R57 paired ISO image is included. The recovered Library source tree has no `BUILD_ISO/dist` output and no `BUILD_ISO/runtime-base/initramfs.img`; it has only the initramfs checksum sidecar. The sidecar points to a path on the original developer machine and cannot recreate the missing binary.
- The current six-partition writer copies the signed ISO's Limine boot payload to the ESP and stores the two ISO files on partitions 2 and 3. It does **not yet configure Limine to launch each stored ISO as an independent boot choice**. Therefore the writer is a shared boot-platform and ISO-archive writer, not yet a certified dual-image boot selector.
- No QEMU/OVMF or physical firmware boot was performed.

## R64 completion requirement

Build both ISOs from a complete runtime staging tree, design and implement the Limine selection/launch mechanism for both payloads, validate the six GPT partitions and payload checksums, then test UEFI and Secure Boot behavior. Never label the USB or ISO pair fully dual-bootable before those gates pass.
