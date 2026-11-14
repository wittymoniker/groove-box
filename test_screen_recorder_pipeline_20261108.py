"""Headless integration tests for the onboard FFmpeg screen recorder."""
from pathlib import Path
import shutil
import time

import pytest

from screen_recorder import ScreenRecorderSession

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not FFMPEG or not FFPROBE, reason="FFmpeg/ffprobe unavailable")


def _rgba_frame(width, height, index):
    # Solid but changing frame data; tightly packed RGBA, no Qt dependency.
    row = bytes((index * 37 % 256, index * 71 % 256, index * 19 % 256, 255)) * width
    return row * height


@pytest.mark.parametrize("ext", ["mp4", "mkv", "webm", "gif"])
def test_screen_recorder_encodes_valid_video_for_each_format(tmp_path, ext):
    width, height, fps = 160, 96, 10
    output = tmp_path / f"screen-test.{ext}"
    session = ScreenRecorderSession(str(output), width, height, fps=fps, ffmpeg=FFMPEG,
                                    include_microphone=False, queue_depth=3)
    session.start()
    deadline = time.monotonic() + 5
    while session.state == "starting" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert session.state == "recording", session.stats()
    for i in range(8):
        session.submit_frame(_rgba_frame(width, height, i))
        time.sleep(0.11)
    session.stop()
    assert session.wait(30), "encoder worker did not finish"
    stats = session.stats()
    assert stats["state"] == "finished", stats
    assert output.is_file() and output.stat().st_size > 64
    probe = shutil.which("ffprobe")
    result = __import__("subprocess").run(
        [probe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height", "-of", "default=noprint_wrappers=1", str(output)],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert f"width={width}" in result.stdout
    assert f"height={height}" in result.stdout
    assert "codec_name=" in result.stdout
    assert stats["frames_written"] >= 1


def test_screen_recorder_rejects_wrong_frame_size(tmp_path):
    session = ScreenRecorderSession(str(tmp_path / "bad.mp4"), 64, 64, ffmpeg=FFMPEG)
    # Model the active state without launching a child process; this isolates
    # the input contract from FFmpeg startup and checks malformed frames are
    # rejected and counted while capture is active.
    session._set_state("recording", "Recording")
    assert not session.submit_frame(b"bad")
    assert session.frames_dropped == 1
    assert "bad frame size" in session.error
