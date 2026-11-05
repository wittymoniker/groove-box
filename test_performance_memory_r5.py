from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=(ROOT/'performance.py').read_text()
g=(ROOT/'groovebox.py').read_text()
v=(ROOT/'video_clip_studio.py').read_text()

def test_secondary_tabs_are_lazy():
    assert 'self._add_lazy_performance_tab(right, "⌨ Hardware"' in p
    assert 'self._add_lazy_performance_tab(right, "▣ Device Manager"' in p
    assert 'self._add_lazy_performance_tab(right, "🧹 Storage"' in p
    assert 'self._add_lazy_performance_tab(right, "📦 Batch Export"' in p

def test_hidden_performance_suspends_before_reuse():
    assert 'def suspend_for_hide(self):' in p
    assert 'btn_close.clicked.connect(self.close)' in p
    assert 'if hasattr(_panel, "suspend_for_hide")' in g
    assert '_panel.suspend_for_hide()' in g

def test_default_browse_avoids_probe_storm():
    assert 'need_stream_probe = (kind_filter != "All" or sort_mode.startswith("Kind"))' in p
    assert 'elif need_stream_probe:' in p

def test_record_inputs_suspend_off_tab():
    assert 'def suspend_inactive_inputs(self) -> bool:' in v
    assert 'studio.suspend_inactive_inputs()' in p

def test_caches_and_background_are_bounded():
    assert '_bounded_cache_put(self._kind_cache' in p
    assert '_bounded_cache_put(cache, path, (key[0], key[1], result), 128)' in p
    assert 'self._timer.setInterval(400)' in p
    assert 'self._worker_pool.setMaxThreadCount(2)' in p

def test_player_idle_poll_is_not_started_in_constructor():
    block=p[p.index('self._poll_timer = QTimer(self)'):p.index('self._sync_timer = QTimer(self)',p.index('self._poll_timer = QTimer(self)'))]
    assert 'self._poll_timer.start()' not in block
