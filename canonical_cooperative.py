"""Bounded ordered GUI commits. Worker threads never receive Qt objects."""
import time
from types import FunctionType, MethodType
from PyQt6.QtCore import QObject, QTimer, QEvent
from PyQt6.QtWidgets import QApplication, QWidget, QScrollBar, QAbstractScrollArea


class CanonicalCommit(QObject):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.generator = None
        self.restart_requested = False
        self._bindings_ready = False
        self.timer = QTimer(self)
        self.timer.setInterval(2)
        self.timer.timeout.connect(self.advance)

    @property
    def running(self):
        return self.generator is not None

    def _bind(self):
        if self._bindings_ready:
            return
        import canonical_cooperative_kernels as kernels
        namespace = type(self.host)._ensure_perfect_unison.__globals__
        for name, function in vars(kernels).items():
            if name.startswith("_cooperative_") and callable(function):
                f = FunctionType(function.__code__, namespace, name,
                                 function.__defaults__, function.__closure__)
                f.__kwdefaults__ = function.__kwdefaults__
                setattr(self.host, name, MethodType(f, self.host))
        self._bindings_ready = True

    def start(self):
        if self.running:
            self.restart_requested = True
            return
        self._bind()
        self.restart_requested = False
        self.host._composition_generation_guard = True
        self.generator = self.host._cooperative__ensure_perfect_unison()
        QApplication.instance().installEventFilter(self)
        action = getattr(self.host, "_cancel_canonical_action", None)
        if action is not None:
            action.setEnabled(True)
        self.timer.start()

    def eventFilter(self, target, event):
        if not self.running:
            return False
        if isinstance(target, QScrollBar):
            return False
        seed = getattr(self.host, "input_seed_val", None)
        if target is seed or (seed is not None and isinstance(target, QWidget) and seed.isAncestorOf(target)):
            return False
        if event.type() == QEvent.Type.Wheel:
            if isinstance(target, QAbstractScrollArea) or isinstance(getattr(target, "parent", lambda: None)(), QAbstractScrollArea):
                return False
        kinds = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick,
                 QEvent.Type.KeyPress, QEvent.Type.Wheel)
        if event.type() in kinds and isinstance(target, QWidget):
            if target is getattr(self.host, "_cancel_canonical_button", None):
                return False
            if target is self.host or self.host.isAncestorOf(target):
                return True  # No unrelated edits during a partial ordered commit.
        return False

    def request_restart(self):
        if self.running:
            self.restart_requested = True

    def cancel(self, *, restart=False, shutdown=False):
        self.restart_requested = bool(restart)
        generator, self.generator = self.generator, None
        if generator is not None:
            generator.close()
        self.finish(restart=restart, refresh=not shutdown)

    def advance(self):
        if not self.running:
            self.timer.stop()
            return
        if self.restart_requested:
            self.cancel(restart=True)
            return
        deadline = time.monotonic() + 0.006
        try:
            while time.monotonic() < deadline:
                next(self.generator)
        except StopIteration:
            self.generator = None
            self.finish()
        except Exception as exc:
            print(f"[Canonical commit] stopped safely: {exc}")
            self.cancel()

    def finish(self, *, restart=False, refresh=True):
        self.timer.stop()
        QApplication.instance().removeEventFilter(self)
        self.host._composition_generation_guard = False
        self.host._unison_composition_guard = False
        self.host._canonical_prepared_sequence_plan = None
        action = getattr(self.host, "_cancel_canonical_action", None)
        if action is not None:
            action.setEnabled(False)
        if restart:
            self.host._live_source_update_pending = True
            timer = getattr(self.host, "_canonical_authoring_debounce_timer", None)
            if timer is not None:
                timer.start(0)
        elif refresh:
            self.host._live_source_update_pending = False
            self.host._live_source_update_dirty = False
            self.host._cache_realtime_control_state()
            self.host._refresh_canonical_fingerprint()
            self.host._gui_refresh(
                "cooperative_canonical_complete",
                lambda: self.host._ui_after_canonical_write("cooperative_canonical_complete"),
            )
