"""theremin_sensors.py — Theremin mode, hardware sensors (gravity / magnetometer / gyroscope / light / proximity)
and raw-signal Wi-Fi projection.

Theremin   pitch and volume come from the pointer (x → pitch on an exponential scale, y → volume) or from any sensor
           axis (tilt the laptop, wave a magnet near it). The tone is synthesised in the audio callback thread
           (never on the UI thread): a sine with a Meum-ratio partial and glide (portamento); optional snapping to
           the project's key. Range 55 Hz – 1760 Hz by default.
Sensors    Linux IIO (/sys/bus/iio): accelerometer (gravity vector and |g|), magnetometer (field in µT and heading),
           gyroscope (°/s), illuminance (lux), proximity. Read on a background thread at 20 Hz; the UI only shows the
           latest values. Laptops without sensors simply list none (pointer mode still works).
Projection The raw signal (float32 PCM, 48 kHz mono, 256-sample packets with a sequence number) is sent over UDP to
           the LAN broadcast address or one host (Wi-Fi hotspot "Groovebox Direct" or any network). Any Groovebox can
           receive and play it ("📡 Receive"), with a small jitter buffer. Nothing is sent unless "Project" is on.
"""
from __future__ import annotations

import glob
import math
import os
import socket
import struct
import threading
import time

import numpy as np

MEUM = 1.1975807343385265          # Meum: the root of 2^M = M^4 + M^2 - M (ratio of the upper partial)
PORT = 47999
MAGIC = b"MGRS"                    # Mathematician's Groovebox Raw Signal
SR = 48000
BLOCK = 256


# --------------------------------------------------------------------------- sensors (background thread)
def _rf(path, default=None):
    try:
        with open(path, "r", encoding="ascii", errors="replace") as f:
            return float(f.read().strip().split()[0])
    except Exception:
        return default


def _axis(dev, prefix, ax):
    raw = _rf(os.path.join(dev, "in_%s_%s_raw" % (prefix, ax)))
    if raw is None:
        return _rf(os.path.join(dev, "in_%s_%s_input" % (prefix, ax)))
    scale = _rf(os.path.join(dev, "in_%s_%s_scale" % (prefix, ax)), _rf(os.path.join(dev, "in_%s_scale" % prefix), 1.0))
    off = _rf(os.path.join(dev, "in_%s_%s_offset" % (prefix, ax)), _rf(os.path.join(dev, "in_%s_offset" % prefix), 0.0))
    return (raw + off) * scale


def discover():
    """{kind: sysfs device dir} for the sensors present on this machine."""
    out = {}
    for dev in sorted(glob.glob("/sys/bus/iio/devices/iio:device*")):
        names = set(os.listdir(dev)) if os.path.isdir(dev) else set()
        for kind, probe in (("accel", "in_accel_x_raw"), ("magn", "in_magn_x_raw"), ("gyro", "in_anglvel_x_raw"),
                            ("light", "in_illuminance_raw"), ("light", "in_illuminance_input"),
                            ("proximity", "in_proximity_raw")):
            if probe in names and kind not in out:
                out[kind] = dev
    return out


def read_all(devs):
    """One reading of every present sensor, in physical units where the driver gives a scale."""
    r = {}
    d = devs.get("accel")
    if d:
        v = [(_axis(d, "accel", a) or 0.0) for a in "xyz"]
        r["accel"] = v                                      # m/s² (IIO scale)
        g = math.sqrt(sum(x * x for x in v))
        r["gravity_g"] = g / 9.80665
        r["tilt_x"] = math.degrees(math.atan2(v[0], math.sqrt(v[1] ** 2 + v[2] ** 2) or 1e-9))
        r["tilt_y"] = math.degrees(math.atan2(v[1], math.sqrt(v[0] ** 2 + v[2] ** 2) or 1e-9))
    d = devs.get("magn")
    if d:
        v = [(_axis(d, "magn", a) or 0.0) for a in "xyz"]
        r["magn_ut"] = [x * 100.0 for x in v]              # IIO gauss → µT
        r["field_ut"] = math.sqrt(sum(x * x for x in r["magn_ut"]))
        r["heading"] = (math.degrees(math.atan2(v[1], v[0])) + 360.0) % 360.0
    d = devs.get("gyro")
    if d:
        r["gyro_dps"] = [math.degrees(_axis(d, "anglvel", a) or 0.0) for a in "xyz"]
    d = devs.get("light")
    if d:
        r["lux"] = _rf(os.path.join(d, "in_illuminance_input"), None)
        if r["lux"] is None:
            r["lux"] = (_rf(os.path.join(d, "in_illuminance_raw"), 0.0) or 0.0) * (_rf(os.path.join(d, "in_illuminance_scale"), 1.0) or 1.0)
    d = devs.get("proximity")
    if d:
        r["proximity"] = _rf(os.path.join(d, "in_proximity_raw"), 0.0)
    return r


class SensorReader:
    """Polls the sensors on a daemon thread; `latest` is a plain dict the UI may read at any time."""

    def __init__(self, hz=20.0):
        self.devs = discover()
        self.latest = {}
        self._stop = threading.Event()
        self._hz = float(hz)
        self._t = threading.Thread(target=self._run, name="sensor-reader", daemon=True)
        self._t.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.latest = read_all(self.devs)
            except Exception:
                pass
            self._stop.wait(1.0 / self._hz)

    def stop(self):
        self._stop.set()


# Normalised 0..1 control sources (sensor → theremin)
SOURCES = (("pointer", "Pointer / touch"), ("tilt_x", "Tilt left–right"), ("tilt_y", "Tilt forward–back"),
           ("field_ut", "Magnet (field strength)"), ("heading", "Compass heading"), ("lux", "Light"),
           ("proximity", "Proximity"), ("gyro", "Rotation speed"))


def normalised(reading, key):
    if not reading:
        return None
    if key == "tilt_x" and "tilt_x" in reading:
        return (reading["tilt_x"] + 90.0) / 180.0
    if key == "tilt_y" and "tilt_y" in reading:
        return (reading["tilt_y"] + 90.0) / 180.0
    if key == "field_ut" and "field_ut" in reading:
        return min(1.0, max(0.0, (reading["field_ut"] - 20.0) / 400.0))   # Earth ≈ 25–65 µT; a magnet ≫ that
    if key == "heading" and "heading" in reading:
        return reading["heading"] / 360.0
    if key == "lux" and reading.get("lux") is not None:
        return min(1.0, math.log10(1.0 + max(0.0, reading["lux"])) / 4.0)
    if key == "proximity" and "proximity" in reading:
        return min(1.0, max(0.0, reading["proximity"] / 255.0))
    if key == "gyro" and "gyro_dps" in reading:
        return min(1.0, math.sqrt(sum(x * x for x in reading["gyro_dps"])) / 360.0)
    return None


# --------------------------------------------------------------------------- tone (audio thread)
class ThereminVoice:
    """Phase-continuous sine + Meum partial with glide; parameters are plain floats written by the UI."""

    def __init__(self, sr=SR):
        self.sr = int(sr)
        self.target_hz = 220.0
        self.target_amp = 0.0
        self.hz = 220.0
        self.amp = 0.0
        self.phase = 0.0
        self.phase2 = 0.0
        self.glide_s = 0.06
        self.partial = 0.18
        self.tap = None                    # callable(block) — e.g. the Wi-Fi projector

    def render(self, n):
        n = int(n)
        k = 1.0 - math.exp(-1.0 / max(1.0, self.glide_s * self.sr))
        hz = np.empty(n); amp = np.empty(n)
        h, a, th, ta = self.hz, self.amp, self.target_hz, self.target_amp
        # closed-form one-pole glide over the block
        decay = (1.0 - k) ** np.arange(1, n + 1)
        hz[:] = th + (h - th) * decay
        amp[:] = ta + (a - ta) * decay
        self.hz, self.amp = float(hz[-1]), float(amp[-1])
        ph = self.phase + np.cumsum(2.0 * np.pi * hz / self.sr)
        ph2 = self.phase2 + np.cumsum(2.0 * np.pi * hz * MEUM / self.sr)
        self.phase = float(ph[-1] % (2.0 * np.pi)); self.phase2 = float(ph2[-1] % (2.0 * np.pi))
        y = (np.sin(ph) + self.partial * np.sin(ph2)) * amp / (1.0 + self.partial)
        y = y.astype(np.float32)
        if self.tap is not None:
            try:
                self.tap(y)
            except Exception:
                pass
        return y


def pitch_from_unit(u, lo=55.0, hi=1760.0, snap_ratios=None, base=None):
    """Exponential map 0..1 → lo..hi Hz; optional snap to a scale (ratios against `base`)."""
    u = min(1.0, max(0.0, float(u)))
    hz = lo * (hi / lo) ** u
    if snap_ratios and base:
        octave = math.floor(math.log2(hz / base))
        cands = [base * (2.0 ** octave) * r for r in snap_ratios] + [base * (2.0 ** (octave + 1)) * r for r in snap_ratios]
        hz = min(cands, key=lambda c: abs(math.log2(c / hz)))
    return hz


# --------------------------------------------------------------------------- raw signal over UDP
class Projector:
    """Sends float32 PCM packets: MAGIC | seq u32 | sr u32 | n u16 | samples."""

    def __init__(self, host="255.255.255.255", port=PORT):
        self.addr = (host, int(port))
        self.seq = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setblocking(False)
        self.sent = 0

    def __call__(self, block):
        b = np.asarray(block, dtype=np.float32).ravel()
        for i in range(0, b.size, BLOCK):
            part = b[i:i + BLOCK]
            pkt = MAGIC + struct.pack("<IIH", self.seq & 0xFFFFFFFF, SR, part.size) + part.tobytes()
            self.seq += 1
            try:
                self.sock.sendto(pkt, self.addr)
                self.sent += 1
            except (BlockingIOError, OSError):
                pass

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class Receiver:
    """Receives projected packets on a thread into a jitter buffer; `pull(n)` feeds an output callback."""

    def __init__(self, port=PORT, buffer_s=0.08):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", int(port)))
        self.sock.settimeout(0.5)
        self.buf = np.zeros(0, dtype=np.float32)
        self.lock = threading.Lock()
        self.min_fill = int(SR * buffer_s)
        self.last_seq = None
        self.lost = 0
        self.got = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, name="raw-signal-rx", daemon=True)
        self._t.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                pkt, _a = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(pkt) < 14 or pkt[:4] != MAGIC:
                continue
            seq, _sr, n = struct.unpack("<IIH", pkt[4:14])
            data = np.frombuffer(pkt[14:14 + 4 * n], dtype=np.float32)
            if self.last_seq is not None and seq > self.last_seq + 1:
                self.lost += seq - self.last_seq - 1
            self.last_seq = seq
            self.got += 1
            with self.lock:
                self.buf = np.concatenate((self.buf[-SR:], data))

    def pull(self, n):
        with self.lock:
            if self.buf.size < max(n, self.min_fill if self.got < 4 else n):
                return np.zeros(n, dtype=np.float32)
            out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def close(self):
        self._stop.set()
        try:
            self.sock.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- window
def open_window(app=None):
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QColor, QPainter
    from PyQt6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                                 QWidget)
    old = getattr(app, "_theremin_window", None) if app is not None else None
    try:
        if old is not None:
            old.show(); old.raise_(); return old
    except RuntimeError:
        pass

    voice = ThereminVoice()
    sensors = SensorReader()
    state = {"stream": None, "proj": None, "rx": None, "u": 0.5, "v": 0.0}

    class Pad(QWidget):
        def __init__(self):
            super().__init__()
            self.setMinimumSize(320, 220)
            self.setMouseTracking(True)

        def _set(self, ev):
            p = ev.position()
            state["u"] = max(0.0, min(1.0, p.x() / max(1, self.width())))
            state["v"] = max(0.0, min(1.0, 1.0 - p.y() / max(1, self.height())))
            self.update()

        def mouseMoveEvent(self, ev):
            self._set(ev)

        def mousePressEvent(self, ev):
            self._set(ev)

        def leaveEvent(self, ev):
            state["v"] = 0.0
            self.update()

        def paintEvent(self, ev):
            p = QPainter(self)
            p.fillRect(self.rect(), QColor(8, 14, 28))
            for i in range(1, 6):
                x = int(self.width() * i / 6)
                p.setPen(QColor(40, 70, 110)); p.drawLine(x, 0, x, self.height())
            x = int(state["u"] * self.width()); y = int((1.0 - state["v"]) * self.height())
            p.setBrush(QColor(255, 200, 120, 200)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(x - 9, y - 9, 18, 18)
            p.setPen(QColor(180, 220, 255))
            p.drawText(8, 16, "%.1f Hz · vol %d %%" % (voice.target_hz, int(100 * voice.target_amp)))
            p.end()

    w = QWidget(app, Qt.WindowType.Window) if app is not None else QWidget()
    w.setWindowTitle("🎵 Theremin · 🧲 sensors · 📡 raw-signal projection")
    lay = QVBoxLayout(w)
    pad = Pad(); lay.addWidget(pad, 1)
    row = QHBoxLayout(); lay.addLayout(row)
    on = QCheckBox("🔊 Sound"); row.addWidget(on)
    src_p = QComboBox(); src_v = QComboBox()
    for key, label in SOURCES:
        src_p.addItem(label, key); src_v.addItem(label, key)
    row.addWidget(QLabel("pitch from")); row.addWidget(src_p); row.addWidget(QLabel("volume from")); row.addWidget(src_v)
    snap = QCheckBox("snap to key"); row.addWidget(snap)
    row.addStretch(1)
    net = QHBoxLayout(); lay.addLayout(net)
    proj = QCheckBox("📡 Project raw signal to"); host = QLineEdit("255.255.255.255"); host.setFixedWidth(140)
    host.setToolTip("LAN broadcast (every Groovebox on this Wi-Fi) or one IP address")
    rx = QCheckBox("📥 Receive + play projected signal")
    stat = QLabel("")
    for x in (proj, host, rx, stat):
        net.addWidget(x)
    net.addStretch(1)
    # MAP TO…: any sensor (or the pointer) drives any parameter of the project through the automation targets
    mrow = QHBoxLayout(); lay.addLayout(mrow)
    map_on = QCheckBox("🔗 Map"); map_src = QComboBox(); map_dst = QComboBox(); map_dst.setMinimumWidth(260)
    for key, label in SOURCES:
        map_src.addItem(label, key)
    try:
        import automation_bus as _ab
        for tgt in (_ab.targets(app) if app is not None else [])[:2000]:
            pth = tgt[0] if isinstance(tgt, (tuple, list)) else str(tgt)
            map_dst.addItem(pth, pth)
    except Exception:
        _ab = None
    map_dst.setEditable(True)
    map_dst.setToolTip("Parameter to drive (every numeric control of the project: FX, synth engine, mixer, EQ, Mod Osc …)")
    for x in (map_on, map_src, QLabel("→"), map_dst):
        mrow.addWidget(x)
    mrow.addStretch(1)
    sens = QLabel(""); sens.setWordWrap(True); sens.setStyleSheet("font-family:monospace; color:#9fd7ff;")
    lay.addWidget(sens)
    if not sensors.devs:
        sens.setText("No IIO sensors on this machine (accelerometer / magnetometer / gyroscope / light); "
                     "the pointer pad works everywhere.")

    def _ratios():
        try:
            import groovebox as gb
            return list(getattr(gb, "KEY_RATIOS_MAJOR", None) or [1, 9 / 8, 5 / 4, 4 / 3, 3 / 2, 5 / 3, 15 / 8])
        except Exception:
            return [1, 9 / 8, 5 / 4, 4 / 3, 3 / 2, 5 / 3, 15 / 8]

    def _base():
        try:
            return float(app.spin_base_frequency.value())
        except Exception:
            return 432.0

    def _cb(outdata, frames, _t, _status):
        y = voice.render(frames)
        rxo = state["rx"]
        if rxo is not None:
            y = y + rxo.pull(frames)
        outdata[:, 0] = np.clip(y, -1.0, 1.0)

    def _sound(enabled):
        if enabled and state["stream"] is None:
            try:
                import audio_os_backend as ab
                st = ab.open_output_stream(samplerate=SR, channels=1, dtype="float32", callback=_cb, blocksize=256)
                st.start(); state["stream"] = st
            except Exception as exc:
                stat.setText("audio: %s" % exc)
        elif not enabled and state["stream"] is not None:
            try:
                state["stream"].stop(); state["stream"].close()
            except Exception:
                pass
            state["stream"] = None
    on.toggled.connect(_sound)

    def _proj(enabled):
        if enabled:
            try:
                state["proj"] = Projector(host.text().strip() or "255.255.255.255")
                voice.tap = state["proj"]
            except Exception as exc:
                stat.setText("projection: %s" % exc); proj.setChecked(False)
        else:
            voice.tap = None
            if state["proj"] is not None:
                state["proj"].close(); state["proj"] = None
    proj.toggled.connect(_proj)

    def _rx(enabled):
        if enabled:
            try:
                state["rx"] = Receiver()
                if not on.isChecked():
                    on.setChecked(True)
            except Exception as exc:
                stat.setText("receive: %s" % exc); rx.setChecked(False)
        elif state["rx"] is not None:
            state["rx"].close(); state["rx"] = None
    rx.toggled.connect(_rx)

    def _tick():
        r = sensors.latest
        pu = state["u"] if src_p.currentData() == "pointer" else normalised(r, src_p.currentData())
        pv = state["v"] if src_v.currentData() == "pointer" else normalised(r, src_v.currentData())
        if map_on.isChecked() and _ab is not None and app is not None:
            mu = state["u"] if map_src.currentData() == "pointer" else normalised(r, map_src.currentData())
            if mu is not None:
                try:
                    d, k = _ab._resolve(app, str(map_dst.currentText()))
                    if d is not None and k in d and isinstance(d[k], (int, float)) and not isinstance(d[k], bool):
                        lo, hi = state.setdefault(("span", map_dst.currentText()), _ab._span(k, d[k]))
                        d[k] = type(d[k])(lo + float(mu) * (hi - lo)) if isinstance(d[k], float) else int(round(lo + float(mu) * (hi - lo)))
                except Exception:
                    pass
        if pu is not None:
            voice.target_hz = pitch_from_unit(pu, snap_ratios=_ratios() if snap.isChecked() else None, base=_base())
        if pv is not None:
            voice.target_amp = 0.5 * float(pv)
        bits = []
        if "gravity_g" in r:
            bits.append("gravity %.3f g · tilt %+.1f° / %+.1f°" % (r["gravity_g"], r["tilt_x"], r["tilt_y"]))
        if "field_ut" in r:
            bits.append("magnetic field %.1f µT · heading %.0f°" % (r["field_ut"], r["heading"]))
        if "gyro_dps" in r:
            bits.append("rotation %s °/s" % ", ".join("%+.1f" % x for x in r["gyro_dps"]))
        if r.get("lux") is not None:
            bits.append("light %.1f lux" % r["lux"])
        if "proximity" in r:
            bits.append("proximity %.0f" % r["proximity"])
        if bits:
            sens.setText("  ·  ".join(bits))
        p = state["proj"]; q = state["rx"]
        stat.setText(("sent %d packets" % p.sent if p else "") + ("  received %d (lost %d)" % (q.got, q.lost) if q else ""))
        pad.update()
    tm = QTimer(w); tm.setInterval(50); tm.timeout.connect(_tick); tm.start()

    def _closed(*_a):
        tm.stop(); sensors.stop(); _sound(False); _proj(False); _rx(False)
    w.destroyed.connect(_closed)
    orig_close = w.closeEvent

    def closeEvent(ev):
        _closed()
        orig_close(ev)
    w.closeEvent = closeEvent
    w.resize(760, 460)
    if app is not None:
        app._theremin_window = w
    w.show()
    return w
