import copy
import hashlib
import pickle
import threading
from types import SimpleNamespace

import pytest
from canonical_pool import project, KERNEL_NAMES
from scheduling_weights import work_score, predictive_fraction, TOTAL
from thread_budget import make_lane


@pytest.fixture
def packet():
    from groovebox import MathematiciansGrooveboxApp as C
    kernels = {name: getattr(C, name) for name in KERNEL_NAMES}
    kernels["_shape_contour"] = C._shape_contour
    payload = {
        "version": 1, "names": ["one", "two"],
        "sources": ["euclidean", "phase_lock", "seeded"],
        "banks": {name: {1: {"pattern_length": 16, "user_owned": True,
                            "steps": [True, False] * 8, "user_note": "keep exactly"}}
                  for name in ("one", "two")},
        "memory": {}, "selected": {"one": 1, "two": 1}, "params": {},
        "generated": {}, "seed_values": [1.19758, 0.048], "seed": 1.19758,
        "seed_text": "1.19758", "bpm": 120, "frequency": 432, "shape": 0.0,
        "lane_shapes": {key: 0.0 for key in
                        ("phase", "probability", "eq", "sidechain", "envelope", "automation")},
    }
    identity = hashlib.sha256(pickle.dumps(payload, protocol=5)).hexdigest()
    return identity, payload, kernels


def test_weight_factors_and_one_third_cap():
    assert work_score(1, 1, 1) == pytest.approx(1.24558)
    assert TOTAL == pytest.approx(1.24558)
    assert predictive_fraction(1, 1, 1) == pytest.approx(1 / 3)
    assert work_score(1, 0, 0) == 0.048
    assert work_score(0, 1, 0) == 0.19758
    assert work_score(0, 0, 1) == 1.0
    assert work_score(float("nan"), -1, 8) == 1.0


def test_queue_priorities_do_not_interrupt_active_work():
    lane = make_lane("weighted-check", max_workers=1)
    started = threading.Event()
    release = threading.Event()
    order = []
    running = lane.submit(lambda: (started.set(), release.wait(3)))
    assert started.wait(2)
    low = lane.submit_prioritized(0.048, lambda: order.append("window"))
    high = lane.submit_prioritized(1.24558, lambda: order.append("active-tedious"))
    middle = lane.submit_prioritized(0.19758, lambda: order.append("activity"))
    release.set()
    for future in (running, low, high, middle):
        future.result(5)
    lane.shutdown(wait=True)
    assert order == ["active-tedious", "activity", "window"]


def test_pure_projection_is_repeatable_and_does_not_mutate_input(packet):
    identity, payload, kernels = packet
    original = copy.deepcopy(payload)
    first = project(identity, payload, kernels)
    assert project(identity, payload, kernels) == first
    assert payload == original
    assert all(len(bank) == 3 for bank in first["banks"].values())
    assert all(mem["canonical_owner"].startswith("canonical:")
               for bank in first["banks"].values() for mem in bank.values())


def test_gui_commit_keeps_user_sequences_and_does_not_alias_pool(packet):
    from groovebox import MathematiciansGrooveboxApp as C
    identity, payload, kernels = packet
    plan = project(identity, payload, kernels)
    model = SimpleNamespace(
        _canonical_prepared_sequence_plan=plan, _unison_composition_guard=True,
        instrument_sequence_banks=copy.deepcopy(payload["banks"]),
        instrument_sequencer_memory={}, instrument_names_48=payload["names"],
        instrument_selected_sequence=copy.deepcopy(payload["selected"]),
        instrument_param_state={}, instrument_param_generated={},
        _active_engine_sources=lambda: set(payload["sources"]),
        _finish_canonical_sequence_projection=lambda sources: None,
    )
    user_sequence = model.instrument_sequence_banks["one"][1]
    C._canonical_sequence_reconcile(model, "test")
    assert model.instrument_sequence_banks["one"][1] is user_sequence
    assert user_sequence["user_note"] == "keep exactly"
    for name, bank in plan["banks"].items():
        for sid, memory in bank.items():
            assert model.instrument_sequence_banks[name][sid] == memory
            assert model.instrument_sequence_banks[name][sid] is not memory


def test_predictive_process_returns_exact_packet_and_shuts_down(packet):
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context
    from predictive_buffer import _predict, _low_priority_worker
    identity, payload, kernels = packet
    with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn"),
                             initializer=_low_priority_worker) as pool:
        predicted = pool.submit(_predict, identity, payload, kernels).result(30)
    expected = project(identity, payload, kernels)
    predicted.pop("predictive_cpu_seconds")
    assert predicted == expected
