"""GROOVEBOX_R124_MIDI_LEARN: hold a control, move a hardware knob, it's bound.

Learn: press and hold any slider / dial / spin box / checkable button / LIVE DECK pad for 600 ms with
MIDI learn armed (Ctrl+Alt+L or the Science & Live menu); the next MIDI CC or note binds to it.
Bindings live with the tablet keyboard's custom keys in QSettings ("MathematiciansGroovebox", "UI")
under ``midi_bindings`` as {"cc:<ch>:<num>" | "note:<ch>:<num>": "<widget object path>"}.
Incoming messages are read on a background thread (mido) and applied on the GUI thread.
Without mido everything stays inert (the Connect panel shows the fix).
"""
from __future__ import annotations

import json
import threading

_KEY = "midi_bindings"
_STATE = {"armed": False, "target": None, "thread": None, "stop": None, "bridge": None}


def _settings():
    from PyQt6.QtCore import QSettings
    return QSettings("MathematiciansGroovebox", "UI")


def load():
    try:
        return json.loads(str(_settings().value(_KEY, "{}") or "{}"))
    except Exception:
        return {}


def save(b):
    _settings().setValue(_KEY, json.dumps(b))


def widget_path(w):
    """Stable path: objectName or class[index] chain up to the window."""
    parts = []
    while w is not None and not w.isWindow():
        name = w.objectName()
        if name:
            parts.append(name)
        else:
            par = w.parentWidget()
            sibs = [c for c in (par.children() if par else []) if type(c) is type(w)]
            parts.append(f"{type(w).__name__}[{sibs.index(w) if w in sibs else 0}]")
        w = w.parentWidget()
    return "/".join(reversed(parts))


def resolve(root, path):
    from PyQt6.QtWidgets import QWidget
    cur = root
    for part in path.split("/"):
        nxt = None
        if "[" in part and part.endswith("]"):
            cls, idx = part[:-1].split("[")
            kids = [c for c in cur.children() if isinstance(c, QWidget) and type(c).__name__ == cls]
            i = int(idx)
            nxt = kids[i] if i < len(kids) else None
        else:
            kids = [c for c in cur.children() if isinstance(c, QWidget) and c.objectName() == part]
            nxt = kids[0] if kids else cur.findChild(QWidget, part)
        if nxt is None:
            return None
        cur = nxt
    return cur


def msg_key(msg):
    t = getattr(msg, "type", "")
    if t == "control_change":
        return f"cc:{msg.channel}:{msg.control}", msg.value / 127.0
    if t in ("note_on", "note_off"):
        return f"note:{msg.channel}:{msg.note}", (msg.velocity / 127.0 if t == "note_on" else 0.0)
    return None, None


def apply_value(w, v01, is_note=False):
    from PyQt6.QtWidgets import QAbstractSlider, QAbstractSpinBox, QAbstractButton
    try:
        if isinstance(w, QAbstractSlider):
            w.setValue(int(round(w.minimum() + (w.maximum() - w.minimum()) * v01)))
        elif isinstance(w, QAbstractSpinBox) and hasattr(w, "maximum"):
            val = w.minimum() + (w.maximum() - w.minimum()) * v01
            w.setValue(type(w.value())(val))
        elif isinstance(w, QAbstractButton):
            if is_note and v01 <= 0.0:
                return
            if w.isCheckable() and not is_note:
                w.setChecked(v01 >= 0.5)
            else:
                w.click()
    except Exception:
        pass


def arm(app, on=True):
    _STATE["armed"] = bool(on); _STATE["target"] = None
    try:
        app.statusBar().showMessage("MIDI learn: hold a control, then move a knob / hit a pad" if on else "MIDI learn off", 4000)
    except Exception:
        pass


def _bridge(app):
    if _STATE["bridge"] is None:
        from PyQt6.QtCore import QObject, pyqtSignal

        class Bridge(QObject):
            msg = pyqtSignal(str, float)
        b = Bridge(app)

        def on_msg(key, v):
            binds = load()
            if _STATE["armed"] and _STATE["target"] is not None:
                binds[key] = widget_path(_STATE["target"]); save(binds)
                try:
                    app.statusBar().showMessage(f"MIDI learn: {key} → {binds[key]}", 5000)
                except Exception:
                    pass
                _STATE["armed"] = False; _STATE["target"] = None
                return
            path = binds.get(key)
            if path:
                w = resolve(app, path)
                if w is not None:
                    apply_value(w, v, key.startswith("note:"))
        b.msg.connect(on_msg)
        _STATE["bridge"] = b
    return _STATE["bridge"]


def start(app):
    try:
        import mido
    except Exception:
        return False
    if _STATE["thread"] is not None:
        return True
    b = _bridge(app); stop = threading.Event()

    def run():
        ports = []
        try:
            for n in mido.get_input_names():
                try:
                    ports.append(mido.open_input(n))
                except Exception:
                    pass
            while not stop.is_set():
                for p in ports:
                    for m in p.iter_pending():
                        k, v = msg_key(m)
                        if k:
                            b.msg.emit(k, float(v))
                stop.wait(0.004)
        except Exception:
            pass
        finally:
            for p in ports:
                try:
                    p.close()
                except Exception:
                    pass
    t = threading.Thread(target=run, name="gb-midi-learn", daemon=True); t.start()
    _STATE["thread"], _STATE["stop"] = t, stop
    return True


class _HoldFilter:
    pass


def install(app):
    """App-wide hold detection for learn targets (only active while armed)."""
    from PyQt6.QtCore import QObject, QEvent, QTimer
    from PyQt6.QtWidgets import QApplication, QAbstractSlider, QAbstractSpinBox, QAbstractButton

    class Hold(QObject):
        def __init__(self):
            super().__init__(app); self.t = QTimer(self); self.t.setSingleShot(True); self.t.setInterval(600); self.w = None
            self.t.timeout.connect(self.fire)

        def fire(self):
            if _STATE["armed"] and self.w is not None:
                _STATE["target"] = self.w
                try:
                    app.statusBar().showMessage(f"MIDI learn target: {widget_path(self.w)} — now move a knob", 6000)
                except Exception:
                    pass

        def eventFilter(self, obj, ev):
            if not _STATE["armed"]:
                return False
            et = ev.type()
            if et == QEvent.Type.MouseButtonPress and isinstance(obj, (QAbstractSlider, QAbstractSpinBox, QAbstractButton)):
                self.w = obj; self.t.start()
            elif et == QEvent.Type.MouseButtonRelease:
                self.t.stop()
            return False
    h = Hold(); QApplication.instance().installEventFilter(h); app._r124_midi_hold = h
    start(app)
    return h
