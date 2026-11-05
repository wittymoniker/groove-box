from pathlib import Path

ROOT=Path(__file__).resolve().parent

def test_performance_heavy_tabs_are_lazy():
    s=(ROOT/'performance.py').read_text()
    assert 'GROOVEBOX_V35_22ZT_PERFORMANCE_LAZY_CAPTURE_20260924' in s
    init=s.split('def __init__',1)[1].split('# ------------------------------------------------------------------ lazy Performance tabs',1)[0]
    assert 'VideoClipStudio(self.host, self)' not in init
    assert 'WebBrowserTab(self)' not in init
    assert 'self._nearby_ui_timer.start()' not in init
    restore=s[s.index('    def restore_state(self, state: Dict[str, Any]):'):s.index('    def _apply_output_selection', s.index('    def restore_state(self, state: Dict[str, Any]):'))]
    assert 'self._refresh_output_devices()' not in restore
    assert "self._pending_output_restore=(dn,an)" in restore

def test_capture_enumeration_is_deferred_and_audio_independent():
    s=(ROOT/'video_clip_studio.py').read_text()
    assert 'GROOVEBOX_V35_22ZT_AUDIO_INPUT_RECORDING_20260924' in s
    ctor=s.split('class VideoClipStudio',1)[1].split('def _dispatch_worker_finished',1)[0]
    assert 'self.refresh_devices()' not in ctor
    for token in ('def activate_input_devices(self):','QMediaDevices.audioInputs()',
                  'def _toggle_audio_input_recording','Record Audio Input',
                  'External ·','wave.open(path'):
        assert token in s
