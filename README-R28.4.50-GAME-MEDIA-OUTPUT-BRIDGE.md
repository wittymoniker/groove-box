# Groovebox R28.4.50 — Game Media Output Bridge

## Purpose
Every exported game package now carries `game_media_capabilities.json`, a deterministic manifest describing the audio/video output channels available to game-interface and object generation. It makes the cross-modal contract inspectable by tools and downstream game builders rather than relying on undocumented assumptions.

## Contract coverage
- Audio analysis/control channels: RMS, peak, onset, beat phase, tempo, pitch, chord roots/intervals, spectral descriptors, stereo width, and per-instrument envelopes.
- Audio render outputs: PCM/WAV, music bed, live SFX, and per-instrument stems.
- Video outputs: live frames, RGB/RGBA frame data, video files, layer weights, opacity, hue, depth/parallax, motion vectors, masks, scene phase, and canonical identity.
- Game targets: HUD/UI, sprites, meshes, materials, world objects, environments, animation, particles, camera, transitions, and audio events.
- Bidirectional relationships: audio-to-visual, visual-to-audio, and game-event-to-audio/visual.
- Data protection: source project is not mutated; only explicitly bound media is staged; paths are package-relative; package-local userdata uses the `ProtectedFS` boundary.

This is an extensible capability contract, not a claim that every arbitrary third-party codec, engine API, or asset format is natively implemented. Individual output adapters still need runtime validation against the target renderer/engine.

## Tests
Run `python -m unittest test_game_media_capability_contract.py -v`. Runtime graphics/audio-device and external-engine tests remain separate.
