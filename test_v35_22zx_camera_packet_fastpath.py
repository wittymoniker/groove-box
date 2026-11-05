from pathlib import Path
ROOT=Path(__file__).resolve().parent
VC=(ROOT/'video_clip_studio.py').read_text(errors='ignore')
BI=ROOT/'BUILD_ISO'

def test_linux_camera_packets_bypass_full_rate_qimage_decode():
    assert 'GROOVEBOX_V35_22ZX_CAMERA_PACKET_FASTPATH_20260924' in VC
    assert 'def _on_shared_v4l2_jpeg' in VC
    assert "st._on_shared_v4l2_jpeg(jpg)" in VC
    assert "mj.write(encoded_jpeg); self._sw_frame_index += 1" in VC
    shared=VC.split('class _SharedV4L2Capture',1)[1].split('class VideoClipStudio',1)[0]
    assert "image=QImage.fromData(jpg,'JPG')" not in shared

def test_native_mjpeg_copy_has_compatibility_fallback():
    assert "'-input_format','mjpeg'" in VC
    assert "'-c:v','copy','-f','mjpeg','pipe:1'" in VC
    assert 'Native MJPEG mode unavailable; using compatibility camera stream' in VC
    assert "'-c:v','mjpeg','-q:v','5'" in VC

def test_preview_is_ten_hz_but_recording_rate_remains_independent():
    assert 'self._preview_interval_s = 1.0 / 10.0' in VC
    assert "fps=max(1,min(60,int(self.spin_fps.value())" in VC
    assert 'Qt.TransformationMode.FastTransformation' in VC

def test_current_builder_overlay_is_zz():
    # v35.22zx is a historical snapshot; R28.4.12 ships from the zz overlay.
    ov=BI/'app-overlay-v35.22zz'/'video_clip_studio.py'
    assert ov.is_file()
    assert ov.read_bytes()==(ROOT/'video_clip_studio.py').read_bytes()
    verify=(BI/'verify_v35_22zz.py').read_text(errors='ignore')
    assert 'async hardware' in verify
    assert (BI/'master_final_iso_v35_22zz.sh').is_file()
