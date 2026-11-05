"""Exact-input sCode pooling for Qt-free canonical sequence projection.

The worker owns copied numerical data. Only the GUI may publish a projection.
One running request plus one replacement request bounds work during seed typing.
"""
import copy
import hashlib
import pickle
from types import MethodType, SimpleNamespace
import weakref

from PyQt6.QtCore import QObject, QTimer

KERNEL_NAMES = (
    "_canonical_sequence_reconcile", "_instrument_seed_float",
    "_instrument_seed_int", "_fractal_seed_event_plan", "_raw_contour",
    "_write_contour_lanes",
)
LANES = ("phase", "probability", "eq", "sidechain", "envelope", "automation")


class Value:
    """A scalar captured on the GUI thread, not a reference to a spin box."""
    def __init__(self, value):
        self.number = value

    def value(self):
        return self.number


def capture(host):
    previous = bool(getattr(host, "_canonical_last_active_set", ()))
    banks = (getattr(host, "_canonical_panels_user_store", None) if previous else None)
    if banks is None:
        banks = getattr(host, "instrument_sequence_banks", {}) or {}
    user_banks = {
        name: {sid: mem for sid, mem in bank.items()
               if not str((mem or {}).get("canonical_owner", "")).startswith("canonical:")}
        for name, bank in banks.items() if isinstance(bank, dict)
    }
    payload = copy.deepcopy({
        "version": 1,
        "names": list(getattr(host, "instrument_names_48", ())),
        "sources": sorted(set(host._active_engine_sources()) - {"goava"}),
        "banks": user_banks,
        "memory": (getattr(host, "_canonical_pattern_user_store", None) if previous else None)
                  or getattr(host, "instrument_sequencer_memory", {}) or {},
        "selected": getattr(host, "instrument_selected_sequence", {}) or {},
        "params": (getattr(host, "_canonical_macro_user_store", None) if previous else None)
                  or getattr(host, "instrument_param_state", {}) or {},
        "generated": {},
        "seed_values": host.get_seed_values(),
        "seed": host.get_numeric_seed(),
        "seed_text": host._seed_text(),
        "bpm": host.spin_bpm.value(),
        "frequency": host.spin_base_frequency.value(),
        "shape": float(getattr(host, "contour_shape", 0.0)),
        "lane_shapes": {key: host._contour_lane_shape(key) for key in LANES},
    })
    # Full digest verifies exact ownership/data identity in addition to the
    # compact numeric sCode index; a pool slot is never proof of equality.
    identity = hashlib.sha256(pickle.dumps(payload, protocol=5)).hexdigest()
    kernels = {name: getattr(type(host), name) for name in KERNEL_NAMES}
    kernels["_shape_contour"] = type(host)._shape_contour
    return identity, payload, kernels


def project(identity, payload, kernels):
    """Run the incumbent numerical kernels against a widget-free data owner."""
    data = copy.deepcopy(payload)
    model = SimpleNamespace(
        _canonical_model_only=True,
        instrument_names_48=data["names"],
        instrument_sequence_banks=data["banks"],
        instrument_sequencer_memory=data["memory"],
        instrument_selected_sequence=data["selected"],
        instrument_param_state=data["params"],
        instrument_param_generated=data["generated"],
        contour_shape=data["shape"],
        spin_bpm=Value(data["bpm"]),
        spin_base_frequency=Value(data["frequency"]),
    )
    model._active_engine_sources = lambda: set(data["sources"])
    model.get_numeric_seed = lambda: data["seed"]
    model._seed_text = lambda: data["seed_text"]
    model.get_seed_values = lambda t_value=0.0: list(data["seed_values"])
    model._contour_lane_shape = lambda group: data["lane_shapes"][group]
    model._shape_contour = kernels["_shape_contour"]
    model._finish_canonical_sequence_projection = lambda sources: None
    model._engine_resize_untouched_sequences = lambda: None
    model._engine_write_sequence_panels = lambda **kwargs: None
    model._refresh_sequence_dependent_panels = lambda: None
    for name in KERNEL_NAMES:
        setattr(model, name, MethodType(kernels[name], model))
    model._canonical_sequence_reconcile("pooled_snapshot")
    generated = {
        name: {sid: mem for sid, mem in bank.items()
               if str((mem or {}).get("canonical_owner", "")).startswith("canonical:")}
        for name, bank in model.instrument_sequence_banks.items()
    }
    return {"identity": identity, "sources": data["sources"], "names": data["names"],
            "banks": generated, "params": model.instrument_param_state}


class CanonicalPool(QObject):
    def __init__(self, host):
        super().__init__(host)
        self.host = weakref.ref(host)
        self.future = None
        self.running = None
        self.latest = None
        self.ready = None
        self.failed = None
        from predictive_buffer import PredictiveBuffer
        self.predictive = PredictiveBuffer()
        self.running_packet = None
        self.activity = 0.0
        self.selected = 0.0
        self._last_edit = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(8)
        self.timer.timeout.connect(self.poll)

    def prepare(self):
        host = self.host()
        packet = capture(host)
        identity = packet[0]
        import time
        now = time.monotonic()
        self.activity = 1.0 if now - self._last_edit < 1.0 else 0.25
        self.selected = float(host.isActiveWindow())
        self._last_edit = now
        prediction = self.predictive.lookup(identity)
        if prediction is not None:
            self.ready = prediction
        if self.ready is not None and self.ready["identity"] == identity:
            host._canonical_prepared_sequence_plan = self.ready
            return True
        if self.failed == identity:
            # A computation error must remain visible. Keep the established
            # synchronous implementation available, never publish half a plan.
            host._canonical_prepared_sequence_plan = None
            return True
        self.latest = packet
        if self.future is None:
            self.submit(packet)
        return False

    def submit(self, packet):
        host = self.host()
        if host is None:
            return
        identity, payload, kernels = packet
        self.running_packet = packet
        from scheduling_weights import work_score
        self.running = identity
        self.future = host._scode_optimizer.submit_pooled(
            "canonical_projection", {"sha256": identity, "schema": 1},
            lambda: project(identity, payload, kernels),
            policy="pure", format_id=7, max_entries=4,
            priority=work_score(self.selected, self.activity, 1.0),
        )
        self.timer.start()

    def poll(self):
        if self.future is None or not self.future.done():
            return
        self.timer.stop()
        host = self.host()
        if host is None:
            return
        try:
            result = self.future.result()  # done(), never a GUI-thread wait
            if result["identity"] != self.running:
                raise RuntimeError("sCode canonical pool identity mismatch")
            self.ready = result
            if self.running_packet is not None:
                self.predictive.prefetch(self.running_packet[1], self.running_packet[2],
                                         selected=self.selected, activity=self.activity)
        except Exception as exc:
            self.failed = self.running
            print(f"[Canonical pool] {exc}; retaining synchronous ownership-safe fallback")
        self.future = None
        if self.latest is not None and self.latest[0] != self.running:
            self.submit(self.latest)
            return
        self.latest = None
        # prepare() re-captures current inputs before this result can publish.
        timer = getattr(host, "_canonical_authoring_debounce_timer", None)
        if timer is not None:
            timer.start(0)
        else:
            QTimer.singleShot(0, host._flush_live_source_update)
