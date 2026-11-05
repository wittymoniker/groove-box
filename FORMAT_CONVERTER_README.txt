Groovebox Format Converter (companion utility added 2026-10-21)
================================================================

format_converter.py is a lightweight, FFmpeg-backed helper for converting
audio, video and image files. It lives alongside the main Groovebox
composition and export pipeline; it does not replace the canonical renderer,
sidechain, or the R28.4.x async export path.

Why it is useful
----------------
Users frequently need quick container/codec changes (WAV↔MP3, MP4↔WebM,
PNG↔JPEG, etc.) outside a full composition export. This tool provides a
simple, documented CLI that re-uses the same FFmpeg binary already fetched
by get_ffmpeg_linux.sh (or any system FFmpeg on PATH).

Quick start
-----------
  # list built-in presets
  python format_converter.py --list-formats

  # audio
  python format_converter.py song.wav -o song.mp3
  python format_converter.py song.flac -o song.opus

  # video
  python format_converter.py clip.mp4 -o clip.webm
  python format_converter.py clip.mov -o clip.mp4 --video-codec libx264

  # image
  python format_converter.py photo.png -o photo.jpg --quality 90

  # dry-run (print the ffmpeg command only)
  python format_converter.py in.wav -o out.mp3 -n

Requirements
------------
- ffmpeg + ffprobe (local ./bin preferred, otherwise system PATH)
- Python 3.8+

This utility is intentionally thin. All heavy lifting stays with FFmpeg so
that the converter stays maintainable and does not diverge from the project's
existing media toolchain.
