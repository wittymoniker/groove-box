# Capture / Scroll / Recording Layer fix — 2026-09-08

- Replaced QVideoWidget camera preview with QVideoSink -> QImage/QPixmap -> QLabel software preview so camera frames obey QScrollArea clipping and cannot paint over unrelated UI.
- Camera/capture objects remain owned by VideoClipStudio.
- Mic preview keeps readyRead handling and now also polls bytesAvailable from the meter timer for PipeWire/Qt backends that do not consistently emit readyRead.
- Stopping mic preview clears the meter immediately.
- Append Recording Layer is now render-authoritative: every appended video layer participates in final video composition.
- Multiple recording-video layers are equally weighted in an incremental FFmpeg blend.
- Audio streams from all appended recording layers are included through `amix=normalize=0`; generated Draw Sound is included the same way.
- Desktop source, Groovebox appliance staging, and sOS staging use the same video_clip_studio.py.
- Python compilation, project-media contract, video-render contract, import audit, and a live FFmpeg multi-layer filter graph smoke test passed in the build environment.
