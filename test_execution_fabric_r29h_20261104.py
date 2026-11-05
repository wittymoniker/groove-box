from concurrent.futures import Future
import threading
import numpy as np
import pytest

from execution_fabric import (
    BufferContract, CancellationToken, ExecutionFabric, LatencyClass,
    WorkKind, WorkPacket,
)


def test_packet_executes_on_shared_bounded_lane_and_returns_future():
    fabric = ExecutionFabric()
    packet = WorkPacket(WorkKind.VECTOR, "sum", lambda x: float(np.sum(x)),
                        args=(np.arange(8, dtype=np.float32),),
                        buffer_contracts=(BufferContract("vector", "float32", (8,)),),
                        latency=LatencyClass.INTERACTIVE)
    future = fabric.submit(packet)
    assert isinstance(future, Future)
    assert future.result(timeout=3) == 28.0
    assert fabric.stats()["vector"]["max_workers"] == 2


def test_commit_is_explicit_and_owner_thread_only():
    fabric = ExecutionFabric()
    committed = []
    packet = WorkPacket(WorkKind.PROCESS, "normalize", lambda: 4,
                        commit=lambda value: committed.append(value))
    result = fabric.submit(packet).result(timeout=3)
    assert committed == []
    assert fabric.commit_result(packet, result) is None
    assert committed == [4]
    errors = []
    t = threading.Thread(target=lambda: _capture(errors, fabric, packet, result))
    t.start(); t.join()
    assert errors and isinstance(errors[0], RuntimeError)


def _capture(errors, fabric, packet, result):
    try:
        fabric.commit_result(packet, result)
    except Exception as exc:
        errors.append(exc)


def test_cancellation_prevents_work_from_starting():
    token = CancellationToken(); token.cancel()
    ran = []
    packet = WorkPacket(WorkKind.PROJECT, "cancelled", lambda: ran.append(True), token=token)
    with pytest.raises(RuntimeError, match="cancelled"):
        ExecutionFabric().submit(packet).result(timeout=3)
    assert ran == []


def test_buffer_contract_rejects_noncontiguous_or_wrong_dtype():
    contract = BufferContract("pcm", "float32", (8, 2), channels=2)
    with pytest.raises(TypeError):
        contract.validate(np.zeros((8, 2), dtype=np.float64))
    with pytest.raises(ValueError):
        contract.validate(np.zeros((8, 4), dtype=np.float32)[:, ::2])
