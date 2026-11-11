"""midi_io.py — GROOVEBOX_R32_MIDI_20261110

USB-MIDI (and any MIDI) for Groovebox, with or without python libraries:

  * backends: ``mido`` (+ python-rtmidi) when installed — every OS; otherwise Linux raw ALSA
    devices /dev/snd/midiC*D* read in a thread (works on sOS with no extra packages).
  * NOTE ON  → plays the key chart (degree = note − base_note, via _keychart_trigger), velocity
    scales the voice; NOTE OFF → releases the held-key sustain (held_sustain).
  * CONTROL CHANGE → MIDI LEARN: click "Learn", move any slider/spin box/dial in any window, then
    turn a knob on the controller; the mapping is saved (~/.groovebox/state/midi_map.json).
  * PITCH BEND → live pitch bend (±12 st, the Live Player / jam bend value).
  * PROGRAM CHANGE → selects the instrument with that index.
  * CLOCK / START / STOP → follow an external transport (optional), and sends MIDI clock out
    when a mido output is chosen.
Every message is delivered to the GUI thread through a queued signal (no widget is touched
from the reader thread).
"""
from __future__ import annotations

import glob
import json
import os
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QEvent
from PyQt6.QtWidgets import QApplication, QAbstractSlider, QAbstractSpinBox, QSpinBox, QDoubleSpinBox

_MAP_FILE = None


def _map_path():
    try:
        import groovebox_paths
        return os.path.join(groovebox_paths.state_dir(), "midi_map.json")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".groovebox", "midi_map.json")


def list_inputs():
    names = []
    try:
        import mido
        names += ["mido:" + n for n in mido.get_input_names()]
    except Exception:
        pass
    for dev in sorted(glob.glob("/dev/snd/midiC*D*")):
        label = dev
        try:
            card = dev.split("midiC")[1].split("D")[0]
            with open("/proc/asound/card%s/id" % card) as f:
                label = "%s (%s)" % (dev, f.read().strip())
        except Exception:
            pass
        names.append("raw:" + label)
    return names


def list_outputs():
    try:
        import mido
        return ["mido:" + n for n in mido.get_output_names()]
    except Exception:
        return []


class _Bridge(QObject):
    message = pyqtSignal(list)


class MidiHub(QObject):
    status = pyqtSignal(str)

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.bridge = _Bridge(self)
        self.bridge.message.connect(self._on_message)
        self.threads = []
        self.ports = []
        self.stop = threading.Event()
        self.base_note = 48
        self.follow_clock = False
        self.map = {}
        self.learning = None        # widget waiting for a CC
        self._last_touched = None
        self.out = None
        self._load_map()
        QApplication.instance().installEventFilter(self)

    # -- learn: remember the last control the user touched -------------------
    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.Wheel, QEvent.Type.KeyPress) and \
                isinstance(obj, (QAbstractSlider, QAbstractSpinBox)):
            self._last_touched = obj
        return False

    def learn(self):
        self.learning = True
        self.status.emit("MIDI learn: touch a control in any window, then move a knob/fader")

    def _widget_key(self, w):
        names = [w.objectName() or ""]
        p = w.parent()
        while p is not None and len(names) < 4:
            names.append(p.objectName() or type(p).__name__)
            p = p.parent()
        attr = next((k for k, v in vars(self.app).items() if v is w), "")
        return attr or "/".join(n for n in names if n)

    def _find_widget(self, key):
        w = getattr(self.app, key, None)
        if isinstance(w, (QAbstractSlider, QAbstractSpinBox)):
            return w
        return None

    def _load_map(self):
        try:
            with open(_map_path(), encoding="utf-8") as f:
                self.map = json.load(f) or {}
        except Exception:
            self.map = {}

    def _save_map(self):
        try:
            os.makedirs(os.path.dirname(_map_path()), exist_ok=True)
            with open(_map_path(), "w", encoding="utf-8") as f:
                json.dump(self.map, f, indent=1)
        except Exception:
            pass

    # -- ports --------------------------------------------------------------
    def open_all(self):
        self.close()
        self.stop.clear()
        for name in list_inputs():
            self.open(name)
        self.status.emit("MIDI: %d input(s) open" % len(self.ports))

    def open(self, name):
        if name.startswith("mido:"):
            try:
                import mido
                port = mido.open_input(name[5:], callback=lambda m: self.bridge.message.emit(list(m.bytes())))
                self.ports.append(port)
            except Exception as exc:
                self.status.emit("MIDI open failed: %s" % exc)
        elif name.startswith("raw:"):
            dev = name[4:].split(" ")[0]
            th = threading.Thread(target=self._raw_reader, args=(dev,), daemon=True, name="midi-" + os.path.basename(dev))
            th.start(); self.threads.append(th); self.ports.append(dev)

    def _raw_reader(self, dev):
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            self.bridge.message.emit([-1, str(exc)]); return
        status, data, need = 0, [], 0
        try:
            while not self.stop.is_set():
                try:
                    chunk = os.read(fd, 256)
                except BlockingIOError:
                    time.sleep(0.002); continue
                except OSError:
                    break
                if not chunk:
                    time.sleep(0.002); continue
                for b in chunk:
                    if b >= 0xF8:                       # realtime: clock/start/stop
                        self.bridge.message.emit([b]); continue
                    if b & 0x80:
                        status, data = b, []
                        hi = b & 0xF0
                        need = 1 if hi in (0xC0, 0xD0) else (2 if hi < 0xF0 else 0)
                        continue
                    if status:
                        data.append(b)
                        if len(data) >= need:
                            self.bridge.message.emit([status] + data); data = []   # running status kept
        finally:
            os.close(fd)

    def close(self):
        self.stop.set()
        for p in self.ports:
            try:
                p.close()
            except Exception:
                pass
        self.ports, self.threads = [], []

    def set_output(self, name):
        try:
            import mido
            self.out = mido.open_output(name[5:]) if name.startswith("mido:") else None
        except Exception as exc:
            self.out = None; self.status.emit("MIDI out failed: %s" % exc)

    # -- messages (GUI thread) ---------------------------------------------------
    def _on_message(self, msg):
        if not msg:
            return
        st = msg[0]
        if st == -1:
            self.status.emit("MIDI device error: %s" % msg[1]); return
        app = self.app
        hi, ch = st & 0xF0, st & 0x0F
        try:
            if hi == 0x90 and len(msg) > 2 and msg[2] > 0:
                self._note_on(msg[1], msg[2])
            elif hi == 0x80 or (hi == 0x90 and len(msg) > 2 and msg[2] == 0):
                self._note_off(msg[1])
            elif hi == 0xB0 and len(msg) > 2:
                self._cc(ch, msg[1], msg[2])
            elif hi == 0xE0 and len(msg) > 2:
                bend = ((msg[2] << 7) | msg[1]) - 8192
                app._jam_replay_bend = 12.0 * bend / 8192.0 if bend else 0.0
                if not bend:
                    try: del app._jam_replay_bend
                    except Exception: pass
            elif hi == 0xC0 and len(msg) > 1:
                dd = getattr(app, "instrument_selector_dropdown", None)
                if dd is not None and msg[1] < dd.count():
                    dd.setCurrentIndex(msg[1])
            elif st == 0xFA and self.follow_clock:
                getattr(app, "start_playback", lambda: None)()
            elif st == 0xFC and self.follow_clock:
                getattr(app, "stop_playback", lambda: None)()
        except Exception as exc:
            self.status.emit("MIDI: %s" % exc)

    def _degree_char(self, note):
        try:
            import groovebox as gb
            order = gb.KEYCHART_ORDER
        except Exception:
            return int(note - self.base_note), ""
        d = int(note) - int(self.base_note)
        return d, (order[d % len(order)] if 0 <= d < len(order) else "")

    def _note_on(self, note, vel):
        d, ch = self._degree_char(note)
        hk = getattr(self.app, "_held_keys", None)
        if hk is None:
            try:
                import held_sustain
                hk = self.app._held_keys = held_sustain.HeldKeys()
            except Exception:
                hk = None
        tag = ch or ("midi%d" % note)
        if hk is not None:
            hk.press(tag, time.monotonic())
        self.app._r32_midi_velocity = vel / 127.0
        self.app._keychart_trigger(d, ch)

    def _note_off(self, note):
        d, ch = self._degree_char(note)
        try:
            self.app._held_key_release(ch or ("midi%d" % note))
        except Exception:
            pass

    def _cc(self, ch, cc, val):
        key = "%d:%d" % (ch, cc)
        if self.learning and self._last_touched is not None:
            wkey = self._widget_key(self._last_touched)
            if wkey:
                self.map[key] = wkey; self._save_map()
                self.status.emit("MIDI learn: CC %d (ch %d) → %s" % (cc, ch + 1, wkey))
            self.learning = None
        target = self.map.get(key)
        w = self._find_widget(target) if target else None
        if w is None:
            return
        u = val / 127.0
        if isinstance(w, QAbstractSlider):
            w.setValue(int(round(w.minimum() + u * (w.maximum() - w.minimum()))))
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            w.setValue(w.minimum() + u * (w.maximum() - w.minimum()))

    # -- clock out ------------------------------------------------------------
    def send_clock(self, bpm):
        if self.out is None:
            return
        t = getattr(self, "_clock_timer", None)
        if t is None:
            t = self._clock_timer = QTimer(self)
            t.timeout.connect(lambda: self.out.send(__import__("mido").Message("clock")) if self.out else None)
        t.start(max(1, int(round(60000.0 / max(20.0, float(bpm)) / 24.0))))


def hub(app):
    h = getattr(app, "_midi_hub", None)
    if h is None:
        h = app._midi_hub = MidiHub(app)
    return h
