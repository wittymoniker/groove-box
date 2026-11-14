# MATGROOVEBOX R57–R64 implementation roadmap

Date: 2026-11-14  
Baseline: R56 Cloud/GOAVA/Hardware/Migration + R56 dual-boot USB build-kit  
Scope: **64 sequenced feature work items: 8 per revision across R57–R64.**  
Policy: implementation may proceed before validation; comprehensive tests and acceptance are deferred until the R64 tierization/finalization pass, as requested. No test pass, ISO build, boot, installer, or hardware acceptance is implied by this roadmap.

## How to read the status

- `[~]` = source foundation exists in the merged worktree; GUI, runtime integration, security review, or acceptance remains.
- `[ ]` = not yet implemented in this roadmap.
- A source foundation is not a completed or certified feature. In particular, process separation is not a security sandbox, adapter facades are not universal hardware drivers, and an update transaction planner is not a production A/B updater.

## R57 — Cloud continuity, project safety, and GOAVA intelligence

1. [~] Persistent local-first sync job queue with pause/resume and crash recovery.
2. [~] Explicit three-way workspace metadata merge with path-level conflicts.
3. [~] Selective user-data migration preview with byte/file estimates.
4. [~] Beat/bar-aware GOAVA phrase and crossfade planning (planning only; no autonomous playback).
5. [~] Content-addressed project checkpoints with bounded retention.
6. [ ] Cloud connector authentication and secret-service-backed credential storage.
7. [ ] GUI sync queue, conflict resolver, and per-workspace status surface.
8. [ ] Project restore preview and user-confirmed selective restore workflow.

## R58 — Extension safety and real-time resource governance

9. [~] Isolated extension worker process with conservative CPU, memory, file-descriptor, and timeout limits; explicitly not a sandbox.
10. [~] Extension lifecycle foundation with cleanup hooks.
11. [~] Declarative extension panel-composition model.
12. [~] CPU, RSS, thread, queue, and extension-call telemetry foundation.
13. [ ] OS-enforced filesystem/network sandbox profile and permission broker integration.
14. [ ] Extension crash containment, restart policy, and fault-report UI.
15. [ ] Adaptive background worker/cadence governor connected to live workload telemetry.
16. [ ] Audio-thread allocation and callback isolation instrumentation across all GOAVA/DJ paths.

## R59 — Signed releases, rollback resistance, and reliable transfer

17. [~] Detached Ed25519 release-manifest verification foundation.
18. [~] Trusted-key and monotonic release-version policy foundation in update staging.
19. [~] Resumable chunked local transfer with SHA-256 verification and atomic final rename.
20. [ ] Signed artifact inventory covering both paired ISO images, boot files, and USB payloads.
21. [ ] Key rotation, revocation, and offline trust-bundle update workflow.
22. [ ] Delta payload generation and patch application with full-image fallback.
23. [ ] Interrupted transfer GUI, retry/backoff, bandwidth budget, and disk-space preflight.
24. [ ] Release provenance report binding source revision, toolchain, artifacts, and signatures.

## R60 — Recovery, migration provenance, and device continuity

25. [~] Evidence ledger separating source, unit, GUI, ISO, VM, firmware, installation, and hardware gates.
26. [~] Persistent device-permission profile and hot-plug event-buffer foundations.
27. [~] Content-addressed project/user-state checkpoint foundation.
28. [ ] Selective settings, project, sample, preset, and plugin migration profiles in the installer UI.
29. [ ] Migration dry-run with conflict, capacity, ownership, and filesystem compatibility report.
30. [ ] Interrupted migration journal and idempotent resume/rollback workflow.
31. [ ] Hardware hot-plug UI with explicit per-device approval and revocation.
32. [ ] One-click diagnostic bundle with privacy preview and redaction controls.

## R61 — Visual sCode and extension authoring

33. [~] Extension lifecycle and composition model foundations.
34. [~] GUI-item/launcher metadata contracts retained from R56.
35. [~] Extension worker execution contract with bounded process resources.
36. [ ] Visual panel composer with dockable/floating layouts and undo/redo.
37. [ ] sCode debugger event stream: breakpoints, variables, stack, and event inspection.
38. [ ] Hot reload with deterministic teardown, resource cleanup, and state handoff.
39. [ ] Signed extension package format with dependency lockfile and trust UI.
40. [ ] Extension package builder, compatibility matrix, and theme/icon pack pipeline.

## R62 — Transactional updates and boot recovery

41. [~] Inactive-slot update transaction state machine foundation; no disk writer or activation is implied.
42. [~] Release verification precondition before update transaction preparation.
43. [ ] Production A/B slot layout and installer migration with explicit capacity/backup checks.
44. [ ] Atomic slot write, fsync/readback verification, and boot-success confirmation protocol.
45. [ ] Watchdog-driven rollback after failed boot or failed health confirmation.
46. [ ] Limine recovery selector with last-known-good entry and repair environment.
47. [ ] Delta update application with signed base-image identity and fallback to full payload.
48. [ ] Update policy UI for maintenance windows, metered links, storage budgets, and user approval.

## R63 — Performance, determinism, and hardware-in-loop readiness

49. [~] Resource/performance telemetry foundations for CPU, memory, queue pressure, and extension cost.
50. [ ] GOAVA render-vs-live deterministic replay harness and drift report.
51. [ ] Latency dashboard for audio, MIDI, input, display, and control event paths.
52. [ ] Defined 8 GiB / 16 GiB / 32 GiB workload profiles and graceful degradation policy.
53. [ ] SIMD/native acceleration for measured hot paths, gated by portable reference implementations.
54. [ ] Adaptive background scheduling that yields to audio and interactive workloads.
55. [ ] Hardware-in-loop runner for MIDI, audio, HID, serial, camera, OSC, Art-Net, and sACN.
56. [ ] Certified laser/ILDA interlock and scan-fail acceptance procedure; no generic laser enablement.

## R64 — Release tierization and paired-image delivery

57. [~] Release acceptance ledger with explicit independent gate states.
58. [ ] R64 capability matrix separating implemented, partially integrated, validated, and hardware-certified features.
59. [ ] Reproducible paired Secure Boot / standard-mode ISO build from one pinned source and toolchain.
60. [ ] Real shared Limine six-partition UEFI USB layout that carries both ISO payloads and a tested selection/launch design.
61. [ ] Correct firmware trust documentation and boot-menu behavior that does not pretend software can toggle firmware Secure Boot.
62. [ ] Signed release manifest and SHA-256 inventory for ZIP, TAR.GZ, both ISOs, and USB payload set.
63. [ ] R64 final validation sweep: source, GUI, ISO structure, QEMU/OVMF UEFI, Secure Boot, installer, migration, and rollback.
64. [ ] Physical UEFI installation, upgrade, data-preservation, audio/MIDI, and target-hardware acceptance before release declaration.

## Count and completion rule

- R56 expansion register: 126 tracked items (46 `[x]`, 29 `[~]`, 51 `[ ]` at the recorded baseline).
- R57–R64 roadmap: 64 additional sequenced items (8 per revision); 21 have source foundations `[~]`, 43 remain `[ ]` at this planning cut.
- The two registers are separate scopes. Do not add their counts as a unique-feature total until overlap with the earlier 472-item historical register is reconciled.
- **64 is the fixed planned scope for R57–R64, not a claim that no additional defects or acceptance work will be discovered.** Any additions must be numbered, justified against the sOS/sCode/MATGROOVEBOX goal, and deduplicated before changing the count.
- R64 is not complete until all required gates have evidence. A source file or successful package operation alone cannot certify GUI behavior, bootability, Secure Boot trust, installation safety, or physical hardware support.
