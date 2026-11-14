"""Bounded latest-frame tap for real-time scenograph consumers.

This is a non-blocking in-process handoff point for preview/stream encoders.
It deliberately retains one immutable frame rather than queuing stale video.
Network transport and encoding remain the responsibility of an explicit consumer.
"""
from __future__ import annotations
import threading
import time


class LatestFrameTap:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._sequence = 0
        self._published_at = 0.0
        self._dropped = 0

    def publish(self, frame):
        if frame is None:
            return False
        try:
            # The renderer hands off a fresh array that the viewer only reads.
            # A read-only view avoids an extra full-frame copy on the GUI thread.
            snapshot = frame.view()
            snapshot.setflags(write=False)
        except Exception:
            return False
        with self._lock:
            if self._frame is not None:
                self._dropped += 1
            self._frame = snapshot
            self._sequence += 1
            self._published_at = time.monotonic()
        return True

    def latest(self, *, max_age_s=None):
        """Return the newest immutable frame; optionally reject stale frames."""
        with self._lock:
            if self._frame is None:
                return None
            if max_age_s is not None and (time.monotonic() - self._published_at) > max(0.0, float(max_age_s)):
                return None
            return self._sequence, self._published_at, self._frame

    def stats(self):
        with self._lock:
            return {"sequence": self._sequence, "published_at": self._published_at,
                    "replaced_frames": self._dropped, "has_frame": self._frame is not None}
