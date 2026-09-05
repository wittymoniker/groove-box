# Groovebox Performance Box

`Media Hub` is now **Performance**. Performance owns media browsing, playlist execution, deterministic geometric/phaselocked cutups, live replay, device routing, LAN/Wi-Fi-TV delivery, game-state broadcast, and batch rendering. Groovebox remains the canonical composition authority.

## Appliance target
- HDMI/DisplayPort/VGA-via-adapter/OS-exposed USB displays
- PipeWire/Pulse audio sinks including USB, HDMI and already-paired Bluetooth
- mpv for responsive playback and live rate control
- FFmpeg/ffprobe for render, cutup, normalization and compatibility transcodes
- Ethernet/Wi-Fi HTTP output and token-gated remote control
- optional Chromecast handoff through `catt`

## Architecture
`seed + canonical clock -> CanonicalEditList -> audio | video | game -> Device Manager -> local / LAN / TV / record`

Routing must not alter the canonical composition. Performance keeps old `pi_media_hub` imports as compatibility aliases.
