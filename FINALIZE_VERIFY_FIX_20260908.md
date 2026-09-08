# Camera Stop / MP4 Finalization Verification Fix — 2026-09-08

- Kept the restored camera acquisition path unchanged.
- Fixed the Stop/finalize verification boundary that could reject a valid MP4 on its first size-stability check.
- Finalization now waits briefly for file size stability and retries ffprobe.
- A capture is accepted when ffprobe sees a real video stream with positive duration.
- Container/codec names are not over-constrained.
- V4L2/FFmpeg and Qt-recorder finalization share the same robust verification helper.
- Only verified recordings are indexed/appended as layers.
