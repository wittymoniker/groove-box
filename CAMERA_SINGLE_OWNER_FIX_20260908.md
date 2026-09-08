# Camera single-owner fix — 2026-09-08

Linux/Fedora camera capture now uses exactly one V4L2 owner at a time.

- Preview: one FFmpeg/V4L2 process opens the selected /dev/video* node and streams MJPEG frames into the Qt QLabel preview.
- Record: the preview owner is released before one replacement FFmpeg process opens the same node and tees the single camera input to both H.264 recording and live preview.
- Stop: the recorder is gracefully closed, Qt microphone PCM is muxed to AAC, the MP4 is verified/indexed/appended as a recording layer, and preview resumes when it was enabled before recording.
- This prevents Device or resource busy caused by preview and recorder independently opening the camera.
