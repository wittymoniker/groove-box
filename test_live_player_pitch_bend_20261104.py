import numpy as np

import live_player as lp


def test_pitch_bend_ratio_is_equal_tempered_and_bounded():
    assert abs(lp.pitch_bend_ratio(12.0) - 2.0) < 1e-12
    assert abs(lp.pitch_bend_ratio(-12.0) - 0.5) < 1e-12
    assert abs(lp.pitch_bend_ratio(0.0) - 1.0) < 1e-12
    assert lp.pitch_bend_ratio(99.0) == 2.0
    assert lp.pitch_bend_ratio(-99.0) == 0.5


def test_pitch_bend_buffer_changes_pitch_rate_and_preserves_source_order():
    src = np.sin(np.linspace(0.0, 80.0 * np.pi, 4410)).astype(np.float32)
    up = lp.pitch_bend_buffer(src, 12.0)
    down = lp.pitch_bend_buffer(src, -12.0)
    neutral = lp.pitch_bend_buffer(src, 0.0)
    assert len(up) == len(src) // 2
    assert len(down) == len(src) * 2
    assert np.array_equal(neutral, src)
    assert np.isfinite(up).all() and np.isfinite(down).all()
