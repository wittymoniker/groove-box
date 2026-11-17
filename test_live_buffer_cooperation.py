#!/usr/bin/env python3
"""Focused regression tests for Live Buffer scheduling cooperation."""
from __future__ import annotations
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import live_buffer


class VisibleWindow:
    def isVisible(self):
        return True


class LiveBufferBusyTests(unittest.TestCase):
    def test_visible_live_player_does_not_block_background_cache(self):
        class Host:
            _live_player_window = VisibleWindow()
        self.assertFalse(live_buffer._busy(Host()))

    def test_active_transport_still_protects_realtime_audio(self):
        class Host:
            is_playing = True
            _live_player_window = VisibleWindow()
        self.assertTrue(live_buffer._busy(Host()))

    def test_export_worker_still_serializes_full_mixdown_render(self):
        class Host:
            _export_worker_busy = True
        self.assertTrue(live_buffer._busy(Host()))

    def test_running_canonical_commit_still_defers_render(self):
        class Job:
            running = True
        class Host:
            _canonical_commit = Job()
        self.assertTrue(live_buffer._busy(Host()))

    def test_running_export_scheduler_job_still_defers_render(self):
        class Job:
            state = "running"
        class Scheduler:
            jobs = [Job()]
        class Host:
            _export_scheduler_obj = Scheduler()
        self.assertTrue(live_buffer._busy(Host()))


class SharedBufferPublicationTests(unittest.TestCase):
    def test_publishing_reuses_the_authoritative_buffer_without_rendering(self):
        import numpy as np
        old = live_buffer.cache_dir
        with tempfile.TemporaryDirectory() as td:
            live_buffer.cache_dir = lambda: td
            try:
                key = {"project": "shared", "revision": 3}
                pcm = np.linspace(-0.5, 0.5, 4096, dtype=np.float32)
                self.assertTrue(live_buffer.publish_shared_buffer(key, pcm, 48000))
                # The writer is deliberately asynchronous; wait only in this test.
                import time
                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline and live_buffer.lookup_key(key) is None:
                    time.sleep(0.01)
                hit = live_buffer.lookup_key(key)
                self.assertIsNotNone(hit)
                np.testing.assert_array_equal(hit[0], pcm)
                self.assertEqual(hit[1], 48000)
            finally:
                live_buffer.cache_dir = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
