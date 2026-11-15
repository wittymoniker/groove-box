# MATGROOVEBOX R64 capability matrix

Status: integrated source candidate; not a release certification.
Updated: 2026-11-15

This matrix distinguishes source presence from integration, functional validation, and hardware certification. A checked-in implementation is not assumed to work on every target merely because its module imports.

## Present in the current candidate

| Capability | Source state | Evidence in this handoff | Remaining gap |
|---|---|---|---|
| Keyboard transient smoothing | Partial integration | Short raised-cosine tapers are applied to submitted key buffers | No measured key-to-sound latency, xrun, polyphony, hold/release or long-session audio test |
| Multidimensional display cadence | Partial integration | Render-loop target follows reported display refresh, with configurable cap (`GROOVEBOX_MD_MAX_FPS`, 30–240) and low-power cap | Target FPS is not achieved FPS; no GPU, compositor, thermal or monitor-specific measurement |
| Shared window chrome | Source integrated | Application-wide scrollbar/splitter styling plus matching GOAVA and synth parameter scrollbars | Visual review on Wayland/X11, detached windows, high-contrast themes and scaling not run |
| Extension process sandbox | Source foundation | Python worker uses bubblewrap namespaces, no default host-home mount, explicit project/user-data mounts, opt-in networking, `prlimit` ceilings and wall-clock timeout; fails closed without required tools | GUI/audio/MIDI/hardware brokers, extension UI permissions, signatures, crash/restart UI, adversarial review and runtime security validation remain |
| 3D video authoring | Partial integration | Selected OBJ can render mono or two-camera SBS/TB views and add an optional soundtrack | This is a single selected OBJ render, not a full multi-object scene timeline/compositor; render performance not measured |
| 3D video processing | Source integrated | ffprobe metadata, per-eye resize, SBS↔TB, stereo-to-mono left-eye extraction, trim, FPS conversion, audio keep/mute/replace, MP4/MOV/MKV output | FFmpeg execution and playback compatibility not tested; mono-to-stereo depth synthesis is not supported |
| Hierarchical memory fabric | Source foundation | Immutable ref-counted blocks, generation-aware handles, zero-copy read-only borrows, hierarchical budgets and scoped indexes | Main audio/media subsystems are not yet migrated to use it; NUMA placement and locality telemetry are not complete |
| ISO runtime overlay | Source synchronized | Runtime payload synchronizer reports 406 source/package files byte-for-byte aligned with active overlay | Full source build and initramfs/ISO packaging not run in this handoff |

## Other foundations retained from R57–R64

The current source retains foundations for local-first synchronization, three-way metadata merge, project checkpoints, GOAVA phrase planning, declarative extension metadata, resource telemetry, Ed25519 manifest verification, resumable local transfer, migration preview, hardware permission records, update transaction planning, recovery acceptance records, and the 2026-11-14 FIX6–FIX8 build corrections. These do not by themselves constitute finished cloud services, universal hardware drivers, a production updater, or a signed release.

## Not complete in this candidate

- Dedicated real-time keyboard event queue, full input-to-audio latency budget, callback allocation/lock instrumentation, and comprehensive xrun/underrun recovery.
- Integrated adaptive scheduler that actually throttles background workloads against live audio and GUI pressure; CPU governor, turbo and thermal policy integration is not implemented here.
- Full instrument/project/scene state migration into the new memory fabric, shared-media lifecycle, NUMA placement, and zero-copy audio/video/OBJ paths.
- Complete App Hub, signed extension packages, dependency resolution, GUI/device capability brokers, and per-extension fault/restart UI.
- Full Edit Together screen/video sharing, collaboration permissions, remote input consent and network stress acceptance.
- Full multi-object 3D scene timeline, animation tracks, camera timeline, GPU rendering and whole-song scene composition.
- Remaining game, sensor, GPS, magnetometer, battery/thermal, animation, export and collaboration roadmap items.
- Production installer migration, A/B slot writing, fsync/readback, watchdog rollback and recovery selector.
- Three genuinely selectable UEFI boot choices, four release ISO outputs, and an independently launchable six-partition shared Limine USB selector.
- Microsoft-trusted signing credentials, signed artifact inventory, Secure Boot enrollment/firmware acceptance and release provenance.
- QEMU/OVMF, GUI, audio, ISO, installer, rollback, firmware and physical laptop acceptance.

## Checks performed for this handoff

- Python syntax-only compilation passed for the 12 edited Python modules listed in the handoff note.
- Runtime payload synchronization check passed for 406 root/package source files against the active ISO overlay.
- The R57–R64 roadmap contains 65 tracked items: after the 2026-11-15 completion-services follow-up, 64 have partial source foundations and the physical target-hardware acceptance item remains unstarted.

No functional test suite, FFmpeg job, GUI session, ISO build, QEMU/OVMF run, firmware operation or physical hardware test was run. This preserves the requested test-before-handoff order.

## Additional source foundations added 2026-11-15

| Capability | Source state | Remaining gap |
|---|---|---|
| OS secret store / cloud connector slots | Partial | OS keyring backend must be present; provider OAuth, UI consent, provider-specific sync transports and integration are not supplied. |
| Local notification center | Partial | Service API exists; application notification UI and event-source integration remain. |
| Extension fault/restart policy | Partial | Restart budget/backoff and fault records exist; GUI reporting, sandbox process supervision and user-approved relaunch integration remain. |
| Adaptive background admission | Partial | Resource-governed admission uses bounded worker priority; live audio/GUI telemetry wiring and measured workload tuning remain. |
| Diagnostic bundle privacy preview | Partial | Selected text files are filtered/redacted; one-click GUI collection and user review workflow remain. |
| Artifact SHA-256 inventory | Partial | Roles and source/toolchain metadata are recorded; release signing, detached-signature verification and complete paired-image inputs remain. |
| Secure Boot diagnostics | Read-only source integration | Report is informational; firmware mode/trust acceptance, key enrollment and target hardware checks remain. |
| Hot-plug monitor | Polling source foundation | Native udev integration and GUI approval/revocation surface remain. |
| Migration / transfer budgets | Partial | Preview capacity, collision report, cancellation, bandwidth cap and progress hooks exist; installer UI and interrupted whole-migration recovery remain. |

These are source foundations and are not promoted to completed acceptance rows. The 2026-11-15 package was handed off before testing as requested.


## 2026-11-15 completion-services follow-up

The follow-up added simple, dependency-light services for extension authoring/reload, layout undo/redo and docking metadata, theme-pack validation, package signing and explicit trust decisions, offline trust-key rotation, deterministic GOAVA replay, vectorized feature extraction with a portable fallback, memory profiles/caches, latency summaries, migration journaling, chunk deltas, update policy, health watchdog/recovery selector, A/B storage arithmetic and regular-file-only slot staging, peer advertisement tracking, clone-restore preview/selection, device-permission/hot-plug surfaces, and injected hardware acceptance. See `R191-COMPLETION-PASS-20261115.md` for the acceptance boundary.

This does **not** complete the GUI, real-time audio integration, production block-device updater, independent dual-image USB launch, actual paired ISO generation, Secure Boot trust enrollment, QEMU/OVMF boot validation, physical hardware acceptance, or certified ILDA/laser interlock procedure. The source preflight and smoke scripts report those as separate gates; they do not count them as passes.


## Corrected source validation snapshot — 2026-11-15

- Python parsing: 1,219 files passed.
- Shell syntax: 164 scripts passed.
- Runtime payload parity: 423 files passed byte-for-byte.
- Focused tests: 28 passed across new completion-service and existing window-lifecycle tests.
- Full test collection exceeded 120 seconds; no complete suite result is claimed.
- Paired ISO build, QEMU/OVMF, Qt GUI, firmware, installer, rollback, hardware and laser acceptance remain not run.

See `R191-VALIDATION-REPORT-20261115.md` for the evidence and exact limitations.
