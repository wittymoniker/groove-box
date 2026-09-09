from pathlib import Path

ROOT = Path(__file__).resolve().parent

def text(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_camera_snapshot_and_release_contract():
    s = text('video_clip_studio.py')
    assert "Take Picture From Camera" in s
    assert "def _take_picture_from_camera" in s
    assert "def _release_capture_devices" in s
    assert "def _release_camera_stream_only" in s
    assert "self._release_camera_stream_only()" in s
    # The old V4L2 behavior restarted preview after recording; it must stay gone.
    assert "QTimer.singleShot(120,lambda:self._start_v4l2_capture(False))" not in s


def test_idle_performance_timers_are_demand_driven():
    s = text('performance.py')
    # Remote polling begins only when the server really exists.
    init = s[s.index('self._remote_timer = QTimer(self)'):s.index('# OUTPUT_ROUTER_2026')]
    assert 'self._remote_timer.start()' not in init
    assert 'if not self._remote_timer.isActive(): self._remote_timer.start()' in s
    # Parametric slider drags are coalesced rather than applying every event.
    assert 'self.sld_goava.valueChanged.connect(self._queue_remix)' in s
    assert 'self.sld_rand.valueChanged.connect(self._queue_remix)' in s
    assert 'self.sld_boost.valueChanged.connect(self._queue_remix)' in s


def test_idle_mic_meter_not_started_at_construction():
    s = text('video_clip_studio.py')
    block = s[s.index('# LAG_AUDIT_20260909: the mic meter'):s.index('self._set_color_button()', s.index('# LAG_AUDIT_20260909: the mic meter'))]
    assert 'self._mic_timer.start()' not in block


def test_scode_completion_thread_blocks_when_idle():
    s = text('scode_optimizer_bridge.py')
    assert 'record = self._completion_queue.get()' in s
    assert 'get(timeout=0.1)' not in s
    assert 'completion_timer.setInterval(100)' in s
