"""Typed, bounded execution adapters shared by Groovebox subsystems.

This layer unifies *scheduling contracts*, not real-time callbacks. Device callbacks
must continue to use preallocated rings and must never submit/wait on this fabric.
Workers receive immutable packet metadata and compute snapshots; commits are explicit
and must be invoked by the owning (normally Qt/UI) thread.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import threading
import time
from typing import Any, Callable, Mapping, Optional
from types import MappingProxyType

try:
    from . import thread_budget as _budget
except Exception:  # flat application import
    import thread_budget as _budget


class WorkKind(str, Enum):
    INPUT_IO = "input_io"
    PROCESS = "process"
    VECTOR = "vector"
    PROJECT = "project"
    PREVIEW = "preview"
    RENDER = "render"
    ENCODE = "encode"


class LatencyClass(str, Enum):
    INTERACTIVE = "interactive"
    FRESHNESS = "freshness"
    BATCH = "batch"


class CancellationToken:
    """Thread-safe cooperative cancellation token for long-running jobs."""
    __slots__ = ("_event",)

    def __init__(self):
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeError("Groovebox work packet cancelled")


@dataclass(frozen=True)
class BufferContract:
    """Description of a buffer crossing a subsystem boundary.

    `owner` describes the lifetime/ownership rule; this class intentionally does
    not copy or freeze the underlying array. Producers must publish immutable data
    or retain ownership until the consumer future completes.
    """
    media: str
    dtype: str
    shape: tuple[int, ...]
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    contiguous: bool = True
    owner: str = "producer-until-future-completes"

    def validate(self, value: Any) -> None:
        import numpy as np
        arr = np.asarray(value)
        if str(arr.dtype) != self.dtype:
            raise TypeError(f"{self.media} dtype mismatch: expected {self.dtype}, got {arr.dtype}")
        if tuple(arr.shape) != tuple(self.shape):
            raise ValueError(f"{self.media} shape mismatch: expected {self.shape}, got {arr.shape}")
        if self.contiguous and not arr.flags.c_contiguous:
            raise ValueError(f"{self.media} buffer must be C-contiguous")
        if self.channels is not None and (arr.ndim < 2 or int(arr.shape[-1]) != int(self.channels)):
            raise ValueError("buffer channel count does not match contract")


@dataclass(frozen=True)
class WorkPacket:
    """Portable work description. `compute` must not mutate GUI/project state."""
    kind: WorkKind
    operation: str
    compute: Callable[..., Any] = field(compare=False, repr=False)
    args: tuple[Any, ...] = field(default_factory=tuple, compare=False, repr=False)
    kwargs: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)
    latency: LatencyClass = LatencyClass.BATCH
    token: CancellationToken = field(default_factory=CancellationToken, compare=False)
    deadline_monotonic: Optional[float] = None
    buffer_contracts: tuple[BufferContract, ...] = ()
    commit: Optional[Callable[[Any], Any]] = field(default=None, compare=False, repr=False)

    def __post_init__(self):
        if not callable(self.compute):
            raise TypeError("WorkPacket.compute must be callable")
        if not str(self.operation).strip():
            raise ValueError("WorkPacket.operation must be non-empty")
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "kwargs", MappingProxyType(dict(self.kwargs)))
        object.__setattr__(self, "buffer_contracts", tuple(self.buffer_contracts))


class ExecutionFabric:
    """Named bounded lanes over the one process-wide worker executor."""
    _WIDTHS = {
        WorkKind.INPUT_IO: 2,
        WorkKind.PROCESS: 2,
        WorkKind.VECTOR: 2,
        WorkKind.PROJECT: 1,
        WorkKind.PREVIEW: 1,
        WorkKind.RENDER: 1,
        WorkKind.ENCODE: 1,
    }
    _PENDING = {
        WorkKind.INPUT_IO: 48, WorkKind.PROCESS: 48, WorkKind.VECTOR: 32,
        WorkKind.PROJECT: 24, WorkKind.PREVIEW: 8, WorkKind.RENDER: 12,
        WorkKind.ENCODE: 8,
    }

    def __init__(self):
        self.owner_thread = threading.get_ident()
        self._lanes = {}
        self._lock = threading.RLock()

    def lane(self, kind: WorkKind):
        kind = WorkKind(kind)
        with self._lock:
            lane = self._lanes.get(kind)
            if lane is None:
                lane = _budget.make_lane(
                    "fabric-" + kind.value,
                    max_workers=self._WIDTHS[kind],
                    max_pending=self._PENDING[kind],
                )
                self._lanes[kind] = lane
            return lane

    def submit(self, packet: WorkPacket):
        if not isinstance(packet, WorkPacket):
            raise TypeError("submit expects a WorkPacket")

        def _execute():
            packet.token.raise_if_cancelled()
            if packet.deadline_monotonic is not None and time.monotonic() > packet.deadline_monotonic:
                raise TimeoutError(f"{packet.operation} missed its execution deadline")
            # Validate explicitly declared input contracts before computation.
            if packet.buffer_contracts:
                if len(packet.buffer_contracts) > len(packet.args):
                    raise ValueError("more buffer contracts than positional inputs")
                for contract, value in zip(packet.buffer_contracts, packet.args):
                    contract.validate(value)
            packet.token.raise_if_cancelled()
            result = packet.compute(*packet.args, **dict(packet.kwargs))
            packet.token.raise_if_cancelled()
            return result

        return self.lane(packet.kind).submit(_execute)

    def commit_result(self, packet: WorkPacket, result: Any):
        """Apply a computed result on the fabric's owner thread only."""
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError("result commit must run on the owning/UI thread")
        packet.token.raise_if_cancelled()
        if packet.commit is None:
            return result
        return packet.commit(result)

    def stats(self):
        with self._lock:
            return {kind.value: lane.stats() for kind, lane in self._lanes.items()}


_FABRIC = None
_FABRIC_LOCK = threading.Lock()


def get_fabric() -> ExecutionFabric:
    global _FABRIC
    if _FABRIC is None:
        with _FABRIC_LOCK:
            if _FABRIC is None:
                _FABRIC = ExecutionFabric()
    return _FABRIC


def submit_work(kind: WorkKind, operation: str, compute: Callable[..., Any], *args,
                latency: LatencyClass = LatencyClass.BATCH, **kwargs):
    """Convenience API returning a Future; never call from a device callback."""
    return get_fabric().submit(WorkPacket(kind=kind, operation=operation,
                                          compute=compute, args=args,
                                          latency=latency, kwargs=kwargs))
