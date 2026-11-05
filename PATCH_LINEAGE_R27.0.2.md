# Groovebox R27.0.2 patch lineage — HDMI audio

Date: 2026-10-16
Version: v35.22zz-R27.0.2
Base: R27.0.1 media playback patch, reconstructed on the recovered v35.22zz-R23r source archive.

## Changes
- Add explicit HDMI/DisplayPort ALSA playback endpoint discovery from `aplay -l` as a fallback when `aplay -L` lacks aliases.
- Label discovered digital outputs in the existing output picker.
- Avoid internal-speaker UCM/mixer activation for explicit HDMI/DisplayPort routes.
- Keep internal speakers as the conservative default; HDMI audio can be selected without changing the machine-wide default.
- Add regression tests for HDMI discovery, explicit PCM routing, and preserving default behavior.

## Additional useful follow-up features identified
1. Hot-plug watcher that refreshes HDMI/DP audio outputs when displays connect/disconnect, while preserving the user's selection if the device remains present.
2. A per-device diagnostic action (`wpctl status`, `pactl`, `aplay -l`) with copyable logs and clear distinctions between “device not detected”, “profile unavailable”, and “sink selected but silent”.
3. Optional “Test sound” control per output with a short low-volume PCM test and explicit confirmation, without silently changing system defaults.
4. Optional mirrored output (HDMI + speakers) only when PipeWire supports a valid combined sink; do not fake mirroring by starting two competing audio players.
5. Codec/decoder self-test surfaced in the app so recognized file extensions are not confused with codecs actually available in the installed runtime.

## Invariants and limitations
- Preserve known-good v35.22zt Performance/external-audio behavior and the R8 installer lineage; no installer, boot, or threading changes are intended.
- Preserve the R27.0.1 media playback and R27.0.0 transactional export/game-install changes.
- Keep `media_output_router.py` and its current ISO overlay copy byte-identical.
- The recovered R23r source lineage is the base. R24-R26 package payloads were unavailable in the recovery workspace; this is not represented as the original R26 FULL3 build.
- Automated endpoint/routing tests do not prove audible output on a physical TV/monitor. Real HDMI playback and bootable ISO validation remain outstanding.
