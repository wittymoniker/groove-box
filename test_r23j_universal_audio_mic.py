from pathlib import Path
ROOT=Path(__file__).resolve().parent
perf=(ROOT/'performance.py').read_text(errors='replace')
vid=(ROOT/'video_clip_studio.py').read_text(errors='replace')
hv=(ROOT/'hardware_volume.py').read_text(errors='replace')
router=(ROOT/'media_output_router.py').read_text(errors='replace')
assert 'def _launch_physical_pcm_pipeline' in perf
assert '"-map","0:a:0"' in perf and '"-ar","48000"' in perf and '"-f","s16le","pipe:1"' in perf
assert 'self._player_aux_proc=decoder' in perf
assert 'universal physical PCM fallback' in perf
assert "self.title.setText('Hardware Volume')" in hv and "request_hardware_volume('sync')" in hv
assert 'the state file is the desired user setting' in router
assert 'now-last >= 1.25' in vid
assert 'self._mic_restart_count' in vid
assert "QTimer.singleShot(0, lambda: self._ensure_live_mic_meter(force_restart=True))" in vid
print('PASS: R23j universal direct audio + saved hardware-volume reassert + continuous mic watchdog contracts')
