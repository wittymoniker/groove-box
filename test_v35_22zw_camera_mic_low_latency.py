from pathlib import Path

ROOT=Path(__file__).resolve().parent
VC=(ROOT/'video_clip_studio.py').read_text(errors='ignore')
BI=ROOT/'BUILD_ISO'


def test_record_page_audio_first_camera_deferred():
    assert 'GROOVEBOX_V35_22ZW_CAMERA_MIC_LOW_LATENCY_20260924' in VC
    assert "Camera loads on Preview / Record" in VC
    assert 'QTimer.singleShot(90, lambda: self._refresh_audio_inputs(force=True))' in VC
    activation=VC[VC.index('    def activate_input_devices'):VC.index('    @staticmethod\n    def _audio_input_label')]
    assert '_ensure_camera_devices(' not in activation


def test_camera_probe_only_on_camera_actions_or_refresh():
    assert 'def _ensure_camera_devices' in VC
    for fn in ('_toggle_camera_preview','_toggle_record','_take_picture_from_camera'):
        seg=VC[VC.index(f'    def {fn}'):]
        seg=seg[:seg.find('\n    def ',10) if seg.find('\n    def ',10)>0 else len(seg)]
        # Current R28.4.11+ paths use an isolated asynchronous probe first;
        # the legacy synchronous ensure call remains only as a fallback.
        assert ('self._request_device_probe_async' in seg or 'self._ensure_camera_devices()' in seg)


def test_preview_repaint_bounded_and_fast():
    if 'GROOVEBOX_V35_22ZX_CAMERA_PACKET_FASTPATH_20260924' in VC:
        assert 'self._preview_interval_s = 1.0 / 10.0' in VC
        old=(BI/'app-overlay-v35.22zw'/'video_clip_studio.py').read_text(errors='ignore')
        assert 'self._preview_interval_s = 1.0 / 12.0' in old
    else:
        assert 'self._preview_interval_s = 1.0 / 12.0' in VC
    assert 'def _paint_camera_preview' in VC
    assert 'Qt.TransformationMode.FastTransformation' in VC
    paint=VC[VC.index('    def _paint_camera_preview'):VC.index('    def _consume_camera_image')]
    assert '_preview_last_paint_t' in paint


def test_recording_cadence_independent_of_preview_cadence():
    consume=VC[VC.index('    def _consume_camera_image'):VC.index('    def _on_video_frame')]
    assert '1.0/fps' in consume
    assert 'self._paint_camera_preview(image,now)' in consume
    assert consume.index('1.0/fps') < consume.index('self._paint_camera_preview(image,now)')


def test_mic_level_uses_one_timer_not_backend_burst_callbacks():
    assert 'LOW_LATENCY_MIC_20260924' in VC
    assert 'readyRead.connect(self._read_mic_level)' not in VC
    assert 'self._mic_timer.setInterval(50)' in VC
    assert 'if self._mic_io is not None and self._mic_io.bytesAvailable() > 0' in VC


def test_builder_current_overlay_is_zw_and_zv_is_historical_compatible():
    zw=(BI/'verify_v35_22zw.py').read_text(errors='ignore')
    zv=(BI/'verify_v35_22zv.py').read_text(errors='ignore')
    assert "app-overlay-v35.22zw'/'video_clip_studio.py" in zw
    assert 'stale v35.22zw video/audio overlay' in zw
    assert 'GROOVEBOX_V35_22ZW_CAMERA_MIC_LOW_LATENCY_20260924' in zv
    if 'GROOVEBOX_V35_22ZX_CAMERA_PACKET_FASTPATH_20260924' not in VC:
        assert (BI/'app-overlay-v35.22zw'/'video_clip_studio.py').read_bytes()==(ROOT/'video_clip_studio.py').read_bytes()
    else:
        assert 'GROOVEBOX_V35_22ZW_CAMERA_MIC_LOW_LATENCY_20260924' in (BI/'app-overlay-v35.22zw'/'video_clip_studio.py').read_text(errors='ignore')
