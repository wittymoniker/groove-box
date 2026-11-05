"""Static regression contracts for bounded discovery and safe viewer completion."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NEARBY = (ROOT / "nearby_groovebox.py").read_text(encoding="utf-8")
GROOVEBOX = (ROOT / "groovebox.py").read_text(encoding="utf-8")


def test_nearby_sweep_has_single_flight_guard():
    assert "self._sweep_lock = threading.Lock()" in NEARBY
    assert "if not self._sweep_lock.acquire(blocking=False):" in NEARBY
    assert "self._sweep_lock.release()" in NEARBY


def test_nearby_sweep_bounds_worker_fanout_and_socket_waits():
    assert "def sweep_subnet(self, timeout: float = 0.12, workers: int = 12)" in NEARBY
    assert "worker_count = max(4, min(12, int(workers)))" in NEARBY
    assert "timeout=connect_timeout" in NEARBY
    assert "timeout=api_timeout" in NEARBY
    assert "self.stop_event.is_set()" in NEARBY


def test_viewer_pooled_completion_does_not_retain_or_touch_destroyed_widget():
    assert "self._render_lifetime = {\"dead\": False}" in GROOVEBOX
    assert "self.destroyed.connect(lambda *_args, state=_render_lifetime" in GROOVEBOX
    assert "viewer_ref = weakref.ref(self)" in GROOVEBOX
    assert "if _life.get(\"dead\")" in GROOVEBOX
    assert "if not viewer._render_shutdown:" in GROOVEBOX
