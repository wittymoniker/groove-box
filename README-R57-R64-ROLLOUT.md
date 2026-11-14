# MATGROOVEBOX R57–R64 rollout package

This is the merged source/build-kit continuation from the R56 cloud/GOAVA/hardware migration and the R56 dual-boot USB build-kit.

Start here:
- `R57-R64-IMPLEMENTATION-ROADMAP.md` — 64 work items, eight per revision, with honest status markers.
- `R57-R64-STATUS.md` and `R57-R64-COUNT-SNAPSHOT.txt` — current rollout state and exact counts.
- `DUALBOOT-ISO-DELIVERY-STATUS.md` — what the dual-policy ISO wrapper and six-partition writer do, and the remaining true dual-image boot-selector gap.
- `BUILD_ISO/build_dualboot_release.sh` — paired Secure Boot/unsigned ISO build wrapper.
- `BUILD_ISO/create_dualboot_usb.sh` — destructive six-partition UEFI USB writer; read its safeguards and warnings before any use.

Tests were intentionally deferred until R64 finalization at the user's request. This archive has not been boot-tested, installed, or hardware-certified. No completed ISO is included because the recovered source tree lacks the generated runtime initramfs and completed ISO output. The archive contains the source/build path and the USB writer, not a fabricated ISO placeholder.
