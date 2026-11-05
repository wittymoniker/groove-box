import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcc_media as m


def test_convert_audio_and_image_and_no_overwrite(tmp_path):
    a = tmp_path / "a.MCC"
    m.encode_audio(str(a), (np.sin(np.arange(4800) / 20.0) * 0.3).astype(np.float32), 48000)
    out = m.convert_mcc_file(str(a))
    assert out.endswith(".wav") and os.path.getsize(out) > 1000
    out2 = m.convert_mcc_file(str(a))
    assert out2 != out and out2.endswith("_converted.wav")
    img = tmp_path / "i.MCC"
    m.encode_image(str(img), (np.random.RandomState(1).rand(20, 30, 3) * 255).astype(np.uint8))
    assert m.convert_mcc_file(str(img)).endswith(".png")


def test_convert_video_to_mp4(tmp_path):
    import shutil
    if not shutil.which("ffmpeg"):
        return
    v = tmp_path / "v.MCC"
    w = m.VideoWriter(str(v), 64, 48, 12, keyframe=24, audio_rate=8000, audio_channels=1)
    for i in range(12):
        w.write(np.full((48, 64, 3), i * 20, dtype=np.uint8))
    w.write_audio(np.zeros((8000, 1), dtype=np.float32)); w.close()
    out = m.convert_mcc_file(str(v))
    assert out.endswith(".mp4") and os.path.getsize(out) > 500


def test_project_mcc_is_refused(tmp_path):
    p = tmp_path / "p.MCC"; p.write_bytes(b"not media")
    try:
        m.convert_mcc_file(str(p))
    except ValueError:
        return
    raise AssertionError("project MCC should be refused")
