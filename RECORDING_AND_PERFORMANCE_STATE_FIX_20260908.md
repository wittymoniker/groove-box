# Performance state + recording reliability pass — 2026-09-08

## Project save/load
- Normal project state now includes `_performance_profile_state` as `media_workbench_state.target_profile`.
- Normal project state now includes `_signal_lab_reference_profile` as `media_workbench_state.reference_profile`.
- Both are restored before the Performance panel restores its visible controls, so downstream consumers see the restored identity immediately.
- Existing Performance playlist, output routing, Video Clip Studio, and Parametric Remix state remain unchanged and continue to round-trip through `performance.export_state()` / `restore_state()`.

## Audio recording
- Removed `sd.rec(...); sd.wait()` from Layered Draw/Record capture.
- Audio is read in bounded blocks with `sounddevice.InputStream.read()` and streamed directly to PCM WAV.
- Long recordings no longer require allocating the complete take in RAM.
- Audio layer duration ceiling increased from 1 hour UI / 10 minute capture clamp to 24 hours per take.
- Empty/no-frame recordings fail explicitly rather than being silently accepted.

## Linux camera / V4L2 recording
- Removed blocking `QProcess.waitForStarted`, `waitForBytesWritten`, and `waitForFinished` from capture ownership/shutdown.
- V4L2 ownership transitions are serialized through `QProcess.finished`, preventing old/new FFmpeg camera owners from racing for `/dev/video*`.
- Stop uses event-driven q -> terminate -> kill escalation timers without blocking the GUI thread.
- Final mux starts only after the capture process has actually emitted `finished`.
- Final mux runs off the GUI thread through the sCode pooled side-effect executor.
- Final recording is accepted only after FFmpeg succeeds and ffprobe sees a positive-duration video stream.
- Video authoring duration control increased to 24 hours; camera recording itself remains manual Stop-controlled, so it is not tied to a fixed recording duration.

## Verification
- Python syntax compilation passed for the complete source tree.
- AST capture-path audit found no executable `.wait()`, `waitForStarted()`, `waitForFinished()`, or `waitForBytesWritten()` calls in `video_clip_studio.py` or `layered_signal_lab.py`.
- Static round-trip checks confirm both new Performance profile keys have matching save and load paths.
