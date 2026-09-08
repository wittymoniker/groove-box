# Draw/Record + camera capture fix — 2026-09-08

- Fixed VideoClipStudio initialization callback accessing `spin_duration` before construction.
- Camera capture no longer publishes zero-byte or unreadable MP4 placeholders.
- Linux/Qt capture prefers a temporary Matroska container when supported, then finalizes to MP4 with FFmpeg after recorder stop and container stability checks.
- Recorder startup/error state is checked shortly after Record is pressed; failed zero-byte placeholders are removed rather than indexed as project media.
- Final MP4 is verified before being appended to the recording-layer model.
- Standalone and appliance-staged VideoClipStudio copies are byte-identical.

Validation performed in packaging environment:
- Python compile: PASS
- test_project_media_contract.py: PASS
- test_video_render_contract.py: PASS
- staged VideoClipStudio parity: PASS

Hardware boundary: actual camera/microphone encoding still depends on the installed Qt Multimedia/GStreamer/PipeWire/device backend and should be tested on the target machine.
