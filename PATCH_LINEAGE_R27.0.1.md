# Groovebox R27.0.1 patch lineage — media playback

Date: 2026-10-16
Version: v35.22zz-R27.0.1
Base: reconstructed R27.0.0 on recovered v35.22zz-R23r source lineage

## Patch scope
- Broaden supported audio/video container extension routing in Performance.
- Expand Record/Draw video import/append dialogs to match the wider video set.
- Resolve media player executables from the provisioned local toolchain, PATH, or app-local tools folders.
- Retain mpv -> VLC -> FFplay fallback ordering; maintain audio-only behavior without suppressing video on video formats.
- Add FFmpeg encode/probe/decode regression smoke tests for common audio and A/V containers.

## Invariants
- No change to canonical composition/DSP behavior or known-good Performance threading/audio-device logic.
- Keep root application files and ISO overlay copies byte-identical for the changed player and recording modules.
- R27.0.1 is a patch release over the reconstructed R27.0.0 line. It does not imply recovery of missing R24-R26 patches or a verified bootable ISO.
