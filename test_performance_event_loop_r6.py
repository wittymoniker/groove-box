from pathlib import Path
p=(Path(__file__).resolve().parent/'performance.py').read_text()

def test_performance_background_is_static():
    block=p[p.index('class _PerformanceMathBackground'):p.index('def _probe_media_kind_sync')]
    assert 'self._timer.setSingleShot(True)' in block
    assert 'if not self._timer.isActive(): self._timer.start()' not in block

def test_mpv_poll_never_blocks_gui_thread():
    assert 'self._poll_timer.timeout.connect(self._schedule_player_poll)' in p
    assert 'self._player_poll_pool.start(_PoolTask(self._poll_player_worker, generation))' in p
    assert 'eof = self._deckA.query_property("eof-reached", False)' not in p
    assert 'if self._player_poll_inflight or self._manual_stop or self._paused:' in p

def test_player_has_fast_safe_clock_flags():
    assert '--hwdec=auto-safe' in p
    assert '--autosync=30' in p
    assert ('--audio-fallback-to-null=yes' in p or
            ('GROOVEBOX_V35_22ZZ_R23_PLAYBACK_OUTPUT_RECOVERY_20261001' in p
             and '--audio-fallback-to-null=no' in p
             and 'def _recover_player_output' in p
             and 'hardware recovery exhausted' in p))
    assert 'PLAYER_CLOCK_WATCHDOG_20260928' in p

def test_remix_sync_is_change_driven():
    assert 'self._sync_timer.setInterval(180)' in p
    assert 'if state == self._last_remix_sync_state:' in p
    assert 'if abs(new_speed - self.speed) < 1e-6:' in p
