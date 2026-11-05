"""Bounded concurrent PCM source mixer for Groovebox realtime output.

Publish immutable mono float32 buffers from non-audio threads. The PortAudio
callback only snapshots a tuple, sums bounded slices, and advances cursors; it
never opens/closes hardware, performs resampling, or waits on a mutex. All sources
share the host output stream and therefore the same final master gain/EQ path.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import threading
import numpy as np

@dataclass
class _Source:
    name: str
    samples: np.ndarray
    gain: float = 1.0
    loop: bool = False
    cursor: int = 0

class ConcurrentAudioBus:
    def __init__(self, max_sources: int = 32):
        self.max_sources=max(1,int(max_sources))
        self._sources=()  # immutable tuple snapshot read by callback
        self._publish_lock=threading.Lock()  # publisher-side only; never callback-side
        self.last_error=''

    def publish(self, name, samples, gain=1.0, loop=False):
        """Register/replace a mono float32 PCM source; safe to call from UI/workers."""
        key=str(name).strip()
        if not key: raise ValueError('source name must be nonempty')
        arr=np.asarray(samples,dtype=np.float32).reshape(-1).copy()
        if not arr.size: raise ValueError('source buffer must not be empty')
        if not np.all(np.isfinite(arr)): raise ValueError('source buffer contains non-finite samples')
        g=float(gain)
        if not math.isfinite(g): raise ValueError('gain must be finite')
        src=_Source(key,arr,max(0.0,min(4.0,g)),bool(loop),0)
        with self._publish_lock:
            current=[s for s in self._sources if s.name != key]
            if len(current)>=self.max_sources: raise RuntimeError('concurrent audio source limit reached')
            current.append(src); self._sources=tuple(current)
        return key

    def remove(self,name):
        key=str(name)
        with self._publish_lock: self._sources=tuple(s for s in self._sources if s.name != key)

    def clear(self):
        with self._publish_lock: self._sources=()

    def source_names(self):
        return tuple(s.name for s in self._sources)

    def mix_into(self, destination, frames=None):
        """Add active sources to mono float destination; never clips or opens devices."""
        out=np.asarray(destination).reshape(-1)
        n=min(out.size, int(frames) if frames is not None else out.size)
        # tuple assignment/read is atomic under CPython; no lock on audio callback.
        sources=self._sources
        for src in sources:
            pos=src.cursor; remaining=n; offset=0; size=src.samples.size
            while remaining>0:
                if pos>=size:
                    if not src.loop: break
                    pos=0
                take=min(remaining,size-pos)
                if take<=0: break
                out[offset:offset+take] += src.samples[pos:pos+take] * np.float32(src.gain)
                pos+=take; offset+=take; remaining-=take
            if src.loop: src.cursor=pos % size
            else: src.cursor=min(pos,size)
        return n
