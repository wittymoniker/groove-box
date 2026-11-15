# MATGROOVEBOX R57–R64 rollout package

This is the merged source/build-kit continuation from the R56 cloud/GOAVA/hardware migration and the R56 dual-boot USB build-kit.

Start here:
- `R57-R64-IMPLEMENTATION-ROADMAP.md` — 65 work items (eight per revision plus the added R64 3D-video item), with current status markers.
- `R57-R64-STATUS.md` and `R57-R64-COUNT-SNAPSHOT.txt` — current 191-entry combined register state and exact counts.
- `DUALBOOT-ISO-DELIVERY-STATUS.md` — what the dual-policy ISO wrapper and six-partition writer do, and the remaining true dual-image boot-selector gap.
- `BUILD_ISO/build_dualboot_release.sh` — paired Secure Boot/unsigned ISO build wrapper.
- `BUILD_ISO/create_dualboot_usb.sh` — destructive six-partition UEFI USB writer; read its safeguards and warnings before any use.

Tests were intentionally deferred until R64 finalization at the user's request. This archive has not been boot-tested, installed, or hardware-certified. No completed ISO is included because the recovered source tree lacks the generated runtime initramfs and completed ISO output. The archive contains the source/build path and the USB writer, not a fabricated ISO placeholder.


2026-11-15: See `R57-R64-STATUS.md` for the added source foundations and the explicit untested / unaccepted status of this handoff. Combined register status is 46 implemented with evidence, 81 partial, and 64 planned (191 tracked entries across R56 and R57–R64; not deduplicated).


## R191 completion-services follow-up (2026-11-15)

The project includes headless service models and source helpers for the remaining software-only tracks. Current aggregate ledger status is 46 implemented with evidence, 143 partial foundations, and 2 unstarted external physical-acceptance items. Partial is not release-complete; see `R191-COMPLETION-PASS-20261115.md`.

Run the read-only source preflight with:

```bash
python3 scripts/run_release_preflight.py
```

The optional `scripts/qemu_ovmf_smoke.py` starts QEMU with an ISO and copied OVMF variable store, but it explicitly does not declare a boot pass.
