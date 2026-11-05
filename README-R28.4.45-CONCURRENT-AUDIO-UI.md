# R28.4.45 Concurrent Audio + Compact UI

- Main window has no visible master-volume control; Performance remains the sole visible master gain and defaults to 100%.
- Zero percent remains literal zero gain; no master mute toggle is introduced.
- `ConcurrentAudioBus` accepts named mono PCM buffers from worker/UI code and sums up to 32 sources into the existing transport callback before final master gain. It never opens or reinitializes the audio device. The main callback performs no bus mutex acquisition.
- Call `window.concurrent_audio_bus.publish(name, pcm, gain=1.0, loop=False)` to join a concurrent PCM source; `remove(name)` to remove it. Samples must already match the active hardware sample rate; resampling is deliberately outside the realtime callback.
- Global EQ is kept at the top of the main master-processing container and retains draw/reset/persistence/mixdown paths. Main global layout and Ball panel spacing were tightened. Clip-management controls/logic were not changed.

## Verification boundary
Source compilation and deterministic bus tests verify buffer summation, independent removal, looping, and gain handling. This does not prove physical-device playback, arbitrary-rate source alignment, mpv/VLC stream coexistence, or hardware recovery; those require runtime testing on the target machine. Existing direct `sounddevice.play` callers are not automatically converted by this bus, so they must be migrated to `publish` for guaranteed shared-stream coexistence.
