# MATGROOVEBOX R64 RC4 consolidated source handoff

**Status:** untested source candidate; not a final/certified R64 release.  
**Date:** 2026-11-15

## Source basis

This candidate was reconstructed from the available FIX5 full-source archive, with FIX6/FIX7/FIX8 patch content integrated, followed by the R64 RC4 edits listed below. The prior RC2/RC3 full archive binaries were not present in Library at handoff time; their checksum sidecars alone are not treated as source. The active ISO overlay was regenerated from the canonical project sources.

## Included work

- **Sandboxed extension worker:** Linux bubblewrap namespace isolation, read-only extension package, no host home exposure by default, isolated temporary working directory, explicit project and user-data binds, optional explicit network sharing, `prlimit` CPU/address-space/file-descriptor/file-size/process/core ceilings, wall-clock timeout, and fail-closed behavior when bwrap/prlimit are missing. GUI/audio/MIDI/hardware permission brokers and signed third-party package loading are not included.
- **3D video:** OBJ render with independent left/right camera views in mono/SBS/TB; FFmpeg/ffprobe processing for metadata, per-eye resizing, SBS↔TB conversion, stereo-to-mono left-eye selection, trim, FPS change, soundtrack keep/replace/mute and MP4/MOV/MKV output. Mono-to-stereo duplication is deliberately refused by default because it does not create depth.
- **3D Studio controls:** layout, per-eye resolution, frame rate, render duration, soundtrack, source/output layout, output dimensions, input/output trim, and audio policy. Heavy work is submitted to the UI worker path rather than falling back to the GUI thread.
- **Memory fabric:** immutable reference-counted blocks, generation-aware handles, zero-copy read-only borrowing, inherited hierarchical scope budgets, and localized project/track/instrument/scene/frame indexes. This is a non-real-time service; the audio callback must not call it.
- **Window chrome:** shared app-wide scrollbar/splitter palette plus matching GOAVA Radio and multidimensional parameter scrollbars.
- **Display and keyboard continuity:** monitor-refresh-aware multidimensional render target (bounded by `GROOVEBOX_MD_MAX_FPS`, with low-power cap) and short raised-cosine key-buffer edge tapers. These are not substitutes for audio latency/xrun acceptance.
- **Documentation and release accounting:** README/in-app Help updates, 65-item R57–R64 roadmap, and capability matrix.
- **ISO overlay:** synchronized root Python runtime modules/package sources and updated SHA-256 runtime payload manifest.

## Static checks performed

- Syntax-only compilation passed for 12 touched Python modules.
- Runtime source synchronization passed for 406 module/package entries; `scripts/sync_runtime_payload.py --check` reports byte-for-byte agreement with the active overlay.
- Roadmap item counts reconcile to 65 items: 25 partial foundations and 40 not implemented.

## Explicitly not run

No unit/integration suite, FFmpeg render/transcode, Qt GUI session, sandbox launch, audio latency/xrun trial, ISO build, initramfs build, QEMU/OVMF boot, Secure Boot signing/enrollment, installer, rollback, USB write, or physical hardware test was run. This preserves the requested test-before-handoff sequence.

## Known functional limits

- 3D Studio renders the selected OBJ mesh, not every item in the scene list as a full animated multi-object timeline.
- The memory fabric is not yet wired through every audio/video/OBJ subsystem.
- The extension sandbox only executes the supported Python-worker permission subset. GUI, audio, MIDI and hardware capabilities are rejected until proper brokers exist.
- Keyboard edge tapers reduce abrupt sample boundaries; they do not prove low-latency or underrun-free audio.
- Display FPS is a target, not a measured/guaranteed frame rate.
- No OS overclock, voltage modification, thermal-limit bypass, or firmware manipulation is included. Supported CPU performance/boost policy and measured thermal response remain outstanding.
- The paired ISO outputs, fully functional three-choice boot selector, independent six-partition USB ISO launch selection, production A/B updates, Microsoft-trusted signing and physical boot/install acceptance remain outstanding.

See `R64-CAPABILITY-MATRIX.md` and `R57-R64-IMPLEMENTATION-ROADMAP.md` for the full status ledger.
