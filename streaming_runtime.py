"""Bounded, timestamp-aware audio/video streaming primitives.

Audio uses a single-producer/single-consumer preallocated ring: the producer
never waits for the device callback, and the callback never waits for a lock.
Video uses a tiny latest-frame queue so a slow renderer drops stale frames
instead of accumulating latency.  These primitives are intentionally small
and independent of Qt / sounddevice so they can also serve game playback.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np


class AudioRingBuffer:
    """Preallocated float32 SPSC PCM ring with nonblocking callback reads."""
    def __init__(self, capacity_frames: int = 65536, channels: int = 1):
        self.capacity = max(256, int(capacity_frames))
        self.channels = max(1, int(channels))
        self._data = np.zeros((self.capacity, self.channels), dtype=np.float32)
        self._read = 0
        self._write = 0
        self._producer_lock = threading.Lock()
        self.underruns = 0
        self.overruns = 0
        self.dropped_frames = 0
        self.total_written = 0
        self.total_read = 0
        self._last_read_clock = 0

    @property
    def available_read(self):
        return max(0, min(self.capacity, int(self._write - self._read)))

    @property
    def available_write(self):
        return max(0, self.capacity - self.available_read)

    def write(self, samples, *, drop_oldest=False) -> int:
        src = np.asarray(samples, dtype=np.float32)
        if src.ndim == 1:
            src = src.reshape(-1, 1)
        if src.ndim != 2:
            raise ValueError("PCM samples must be a 1D or 2D array")
        if src.shape[1] != self.channels:
            if src.shape[1] == 1 and self.channels > 1:
                src = np.repeat(src, self.channels, axis=1)
            elif self.channels == 1:
                src = np.mean(src, axis=1, keepdims=True, dtype=np.float32)
            else:
                raise ValueError(f"expected {self.channels} channels, got {src.shape[1]}")
        src = np.nan_to_num(src, nan=0.0, posinf=1.0, neginf=-1.0)
        with self._producer_lock:
            count = int(src.shape[0])
            if count > self.capacity:
                src = src[-self.capacity:]
                self.dropped_frames += count - self.capacity
                count = self.capacity
            free = self.available_write
            if count > free and drop_oldest:
                drop = count - free
                self._read += drop
                self.dropped_frames += drop
                self.overruns += 1
                free += drop
            n = min(count, free)
            if n <= 0:
                self.overruns += 1
                self.dropped_frames += count
                return 0
            start = int(self._write % self.capacity)
            first = min(n, self.capacity - start)
            np.copyto(self._data[start:start + first], src[:first], casting="unsafe")
            if first < n:
                np.copyto(self._data[:n - first], src[first:n], casting="unsafe")
            # Publish after copy. The PortAudio reader snapshots _write once.
            self._write += n
            self.total_written += n
            if n < count:
                self.overruns += 1
                self.dropped_frames += count - n
            return n

    def read_into(self, out) -> int:
        """Fill output with available PCM and zero-fill underrun; never blocks."""
        dst = np.asarray(out)
        if dst.ndim == 1:
            if self.channels != 1:
                raise ValueError("1D output only supports mono rings")
            frames = int(dst.shape[0])
        elif dst.ndim == 2 and dst.shape[1] == self.channels:
            frames = int(dst.shape[0])
        else:
            raise ValueError("output buffer has incompatible channel shape")
        dst.fill(0)
        write_snapshot = int(self._write)
        available = max(0, min(self.capacity, write_snapshot - int(self._read)))
        n = min(frames, available)
        if n:
            start = int(self._read % self.capacity)
            first = min(n, self.capacity - start)
            if dst.ndim == 1:
                np.copyto(dst[:first], self._data[start:start + first, 0])
                if first < n:
                    np.copyto(dst[first:n], self._data[:n - first, 0])
            else:
                np.copyto(dst[:first], self._data[start:start + first])
                if first < n:
                    np.copyto(dst[first:n], self._data[:n - first])
            self._read += n
            self.total_read += n
        if n < frames:
            self.underruns += 1
        self._last_read_clock += frames
        return n

    def clear(self):
        # Intended for producer/UI control only, never the audio callback.
        with self._producer_lock:
            self._read = self._write

    def stats(self):
        return {"capacity_frames": self.capacity, "buffered_frames": self.available_read,
                "underruns": int(self.underruns), "overruns": int(self.overruns),
                "dropped_frames": int(self.dropped_frames),
                "total_written": int(self.total_written), "total_read": int(self.total_read)}


@dataclass(frozen=True)
class VideoFrame:
    pts: float
    frame: np.ndarray
    sequence: int = 0


class VideoFrameQueue:
    """Small latest-only frame queue with monotonic PTS and bounded memory."""
    def __init__(self, max_frames: int = 3):
        self.max_frames = max(1, int(max_frames))
        self._items = deque()
        self._lock = threading.Lock()
        self._seq = 0
        self.dropped = 0
        self.delivered = 0
        self.last_pts = -1.0

    def push(self, frame, pts: Optional[float] = None):
        arr = np.asarray(frame)
        if arr.ndim not in (2, 3):
            raise ValueError("video frame must be a 2D or 3D array")
        if arr.ndim == 3 and arr.shape[2] not in (3, 4):
            raise ValueError("video frames must have 3 or 4 channels")
        if arr.dtype != np.uint8:
            arr = np.clip(np.nan_to_num(arr, nan=0.0), 0, 255).astype(np.uint8)
        arr = np.ascontiguousarray(arr)
        ts = time.monotonic() if pts is None else float(pts)
        with self._lock:
            if ts < self.last_pts:
                self.dropped += 1
                return False
            self._seq += 1
            self._items.append(VideoFrame(ts, arr, self._seq))
            self.last_pts = ts
            while len(self._items) > self.max_frames:
                self._items.popleft()
                self.dropped += 1
        return True

    def pop_latest(self, not_after: Optional[float] = None):
        with self._lock:
            if not self._items:
                return None
            if not_after is None:
                chosen = self._items[-1]
                self.dropped += max(0, len(self._items) - 1)
                self._items.clear()
            else:
                eligible = [x for x in self._items if x.pts <= float(not_after)]
                if not eligible:
                    return None
                chosen = eligible[-1]
                self.dropped += sum(1 for x in self._items if x.sequence <= chosen.sequence) - 1
                self._items = deque(x for x in self._items if x.sequence > chosen.sequence)
            self.delivered += 1
            return chosen

    def stats(self):
        with self._lock:
            return {"queued": len(self._items), "max_frames": self.max_frames,
                    "dropped": int(self.dropped), "delivered": int(self.delivered),
                    "last_pts": float(self.last_pts)}


class StreamClock:
    """Maps audio sample indices to video presentation times without drift."""
    def __init__(self, sample_rate=48000, fps=30.0):
        self.sample_rate = max(1, int(sample_rate))
        self.fps = max(0.1, float(fps))
        self.origin_sample = 0
        self.origin_time = 0.0

    def reset(self, sample_index=0, time_seconds=0.0):
        self.origin_sample = max(0, int(sample_index))
        self.origin_time = float(time_seconds)

    def sample_time(self, sample_index):
        return self.origin_time + (int(sample_index) - self.origin_sample) / float(self.sample_rate)

    def frame_index(self, sample_index):
        return max(0, int(round(self.sample_time(sample_index) * self.fps)))

    def frame_time(self, frame_index):
        return self.origin_time + max(0, int(frame_index)) / self.fps
