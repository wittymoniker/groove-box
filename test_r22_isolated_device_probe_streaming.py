from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=(ROOT/'performance.py').read_text()
v=(ROOT/'video_clip_studio.py').read_text()
h=(ROOT/'device_probe_helper.py').read_text()

def test_record_open_is_paint_only():
    body=v.split('def activate_input_devices',1)[1].split('@staticmethod',1)[0]
    assert '_refresh_audio_inputs' not in body
    assert 'QMediaDevices.audioInputs' not in body
    assert 'hardware remains asleep' in body

def test_expensive_probe_is_disposable_subprocess():
    assert 'GrooveboxIsolatedDeviceProbe' in v
    # Frozen-safe disposable helper (sys.executable is the app binary when packaged).
    assert "helper_argv('device_probe_helper','record')" in v
    assert 'timeout=7.0' in v
    assert "helper_argv('device_probe_helper','hardware')" in p
    assert 'timeout=8.0' in p
    assert "self._hardware_component_pending={'bundle'}" in p

def test_linux_camera_does_not_require_qt_enumeration_first():
    preview=v.split('def _toggle_camera_preview',1)[1].split('def _finish_camera_preview_after_probe',1)[0]
    assert preview.index('_start_v4l2_capture(False)') < preview.index('_ensure_camera_devices(force=True)')
    record=v.split('def _toggle_record',1)[1].split('def _finish_video_record_after_probe',1)[0]
    assert record.index('_start_v4l2_capture(True') < record.index('_ensure_camera_devices(force=True)')

def test_streaming_player_nonregression():
    for token in ('--hwdec=auto-safe','--cache-secs=1','--demuxer-readahead-secs=1','--cache-pause=no','PLAYER_CLOCK_STALLED'):
        assert token in p
    assert ('--audio-fallback-to-null=yes' in p or
            ('GROOVEBOX_V35_22ZZ_R23_PLAYBACK_OUTPUT_RECOVERY_20261001' in p
             and '--audio-fallback-to-null=no' in p
             and 'def _recover_player_output' in p
             and 'hardware recovery exhausted' in p))
    assert 'subprocess.Popen(cmd + [path]' in p

def test_helper_is_low_priority_and_bounded():
    assert 'os.nice(10)' in h
    assert "scan_component(kind)" in h
