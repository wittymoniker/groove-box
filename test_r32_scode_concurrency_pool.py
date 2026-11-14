"""R32 regression tests for private sCode scratch buffers and bounded lanes."""
from collections import OrderedDict
import threading

import numpy as np

from scode_optimizer_bridge import SCodeOptimizerBridge
import thread_budget


def _bare_bridge(budget=256 * 1024 * 1024):
    bridge = object.__new__(SCodeOptimizerBridge)
    bridge._pool = OrderedDict()
    bridge._pool_lock = threading.Lock()
    bridge._ram_budget_bytes = int(budget)
    bridge._pool_max_entries = 256
    bridge._pool_evictions = 0
    bridge._stats = {"pool_hits": 0, "pool_misses": 0, "pool_evictions": 0}
    return bridge


def test_vector_borrows_are_private_and_do_not_alias():
    bridge = _bare_bridge()
    first = bridge.borrow_vector("render", 32, np.float32, fill=1.0)
    first[0] = 99.0
    second = bridge.borrow_vector("render", 32, np.float32, fill=2.0)
    assert not np.shares_memory(first, second)
    assert second[0] == 2.0
    assert first[0] == 99.0
    assert bridge._stats["pool_hits"] == 1


def test_array_borrows_are_private_and_zeroed_on_request():
    bridge = _bare_bridge()
    first = bridge.borrow_array("matrix", (8, 8), np.float64, zero=True)
    first[0, 0] = 7.0
    second = bridge.borrow_array("matrix", (8, 8), np.float64, zero=True)
    assert not np.shares_memory(first, second)
    assert second[0, 0] == 0.0


def test_byte_budget_evicts_old_lru_templates_and_reports_metrics():
    # Each 1-D size class is 1024 float32 values = 4096 bytes.
    bridge = _bare_bridge(4096)
    bridge.borrow_vector("one", 8, np.float32, fill=0.0)
    bridge.borrow_vector("two", 8, np.float32, fill=0.0)
    assert len(bridge._pool) == 1
    assert next(iter(bridge._pool))[1] == "two"
    assert bridge._stats["pool_evictions"] == 1
    assert sum(a.nbytes for a in bridge._pool.values()) <= bridge._ram_budget_bytes


def test_oversized_template_is_not_retained_when_budget_is_zero():
    bridge = _bare_bridge(0)
    out = bridge.borrow_array("large", (64, 64), np.float32, zero=True)
    assert out.shape == (64, 64)
    assert not bridge._pool


def test_shared_work_lane_executes_and_honors_lane_width():
    lane = thread_budget.make_lane("r32-test", max_workers=2, max_pending=8)
    futures = [lane.submit(lambda n=n: n * n) for n in range(6)]
    assert [f.result(timeout=5) for f in futures] == [0, 1, 4, 9, 16, 25]
    stats = lane.stats()
    # The effective CPU/cgroup budget may be narrower than this requested
    # lane width; the lane must clamp rather than oversubscribe.
    assert 1 <= stats["max_workers"] <= 2
    lane.shutdown(wait=True, cancel_futures=True)
    assert lane.stats()["closed"] is True
