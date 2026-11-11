"""hardware_tools.py — GROOVEBOX_R32_HARDWARE_TOOLS_20261110

One window for every piece of hardware, plus app-wide input support.

INPUT SUPPORT (install_input_support, at startup)
  * every mouse / keyboard / trackpad / touchscreen libinput or the OS exposes reaches Qt;
    Groovebox adds: touch → mouse synthesis for widgets that only handle mouse events,
    long-press (550 ms) = right-click (context menus on touch), two-finger pinch on any
    scroll area = zoom (Ctrl+wheel), two-finger pan = scroll, larger hit targets on touch
    devices (min 34 px buttons/sliders), smooth high-resolution trackpad wheel deltas.
  * an input tester (live events with device type) in the Hardware window.

HARDWARE WINDOW tabs
  MIDI       inputs/outputs (USB-MIDI, raw ALSA or mido), open all, MIDI learn, base note,
             follow external clock, send clock out, mappings list / clear
  Audio      USB audio and every playback device; Both outputs (HDMI + speakers) install;
             test tone on a chosen device
  Input      detected input devices (/proc/bus/input/devices or OS list) and a live tester
  Printers   available printers; print a PROJECT SHEET (title, seed program, tempo, canonical
             mode, engines, rows) or save it as PDF
  USB / storage   lsusb list, removable drives (mount state), cameras (V4L2)
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time

from PyQt6.QtCore import Qt, QObject, QEvent, QTimer, QPointF
from PyQt6.QtGui import QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QApplication, QAbstractScrollArea, QAbstractButton, QAbstractSlider


# ---------------------------------------------------------------------------
# input support
# ---------------------------------------------------------------------------
class _TouchHelper(QObject):
    LONG_MS = 550

    def __init__(self, app):
        super().__init__(app)
        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.timeout.connect(self._long_press)
        self._press = None
        self._pinch0 = None

    def eventFilter(self, obj, ev):
        t = ev.type()
        try:
            if t == QEvent.Type.TouchBegin:
                pts = ev.points()
                if len(pts) == 1:
                    self._press = (obj, pts[0].position(), pts[0].globalPosition())
                    self._timer.start(self.LONG_MS)
                return False
            if t == QEvent.Type.TouchUpdate:
                pts = ev.points()
                if len(pts) == 1 and self._press is not None:
                    if (pts[0].position() - self._press[1]).manhattanLength() > 12:
                        self._timer.stop()
                elif len(pts) == 2:
                    self._timer.stop()
                    a, b = pts[0].position(), pts[1].position()
                    d = ((a.x() - b.x()) ** 2 + (a.y() - b.y()) ** 2) ** 0.5
                    area = self._scroll_area(obj)
                    if area is not None:
                        if self._pinch0 is None:
                            self._pinch0 = d
                        elif abs(d - self._pinch0) > 24:     # pinch → Ctrl+wheel zoom
                            self._wheel(area, 120 if d > self._pinch0 else -120, Qt.KeyboardModifier.ControlModifier)
                            self._pinch0 = d
                return False
            if t in (QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
                self._timer.stop(); self._press = None; self._pinch0 = None
        except Exception:
            pass
        return False

    @staticmethod
    def _scroll_area(w):
        while w is not None and not isinstance(w, QAbstractScrollArea):
            w = w.parent() if hasattr(w, "parent") else None
        return w

    @staticmethod
    def _wheel(target, delta, mods):
        vp = target.viewport() if hasattr(target, "viewport") else target
        c = QPointF(vp.width() / 2, vp.height() / 2)
        ev = QWheelEvent(c, vp.mapToGlobal(c.toPoint()).toPointF(), QPointF(0, 0).toPoint(),
                         QPointF(0, delta).toPoint(), Qt.MouseButton.NoButton, mods, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(vp, ev)

    def _long_press(self):
        if self._press is None:
            return
        obj, pos, gpos = self._press
        self._press = None
        try:
            for et in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                QApplication.sendEvent(obj, QMouseEvent(et, pos, gpos, Qt.MouseButton.RightButton,
                                                        Qt.MouseButton.RightButton if et == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton,
                                                        Qt.KeyboardModifier.NoModifier))
            if hasattr(obj, "contextMenuEvent"):
                from PyQt6.QtGui import QContextMenuEvent
                QApplication.sendEvent(obj, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos.toPoint(), gpos.toPoint()))
        except Exception:
            pass


def touch_present():
    try:
        from PyQt6.QtGui import QInputDevice
        return any(d.type() == QInputDevice.DeviceType.TouchScreen for d in QInputDevice.devices())
    except Exception:
        return any("touch" in n.lower() for n in input_devices())


def install_input_support(app=None):
    qa = QApplication.instance()
    if qa is None or getattr(qa, "_r32_touch_helper", None) is not None:
        return
    try:
        qa.setAttribute(Qt.ApplicationAttribute.AA_SynthesizeMouseForUnhandledTouchEvents, True)
        qa.setAttribute(Qt.ApplicationAttribute.AA_SynthesizeTouchForUnhandledMouseEvents, False)
        qa.setAttribute(Qt.ApplicationAttribute.AA_CompressHighFrequencyEvents, True)
    except Exception:
        pass
    h = _TouchHelper(qa); qa.installEventFilter(h); qa._r32_touch_helper = h
    if touch_present() and os.environ.get("GROOVEBOX_TOUCH_TARGETS", "1") != "0":
        qa.setStyleSheet(qa.styleSheet() + "\nQPushButton, QToolButton { min-height: 34px; } "
                         "QSlider::handle { min-width: 22px; min-height: 22px; } QScrollBar { min-width: 18px; }")


def input_devices():
    names = []
    try:
        with open("/proc/bus/input/devices", encoding="utf-8", errors="replace") as f:
            cur = {}
            for ln in f:
                if ln.startswith("N: Name="):
                    cur["name"] = ln.split("=", 1)[1].strip().strip('"')
                elif ln.startswith("H: Handlers="):
                    cur["h"] = ln.split("=", 1)[1].strip()
                elif not ln.strip() and cur:
                    names.append("%s  [%s]" % (cur.get("name", "?"), cur.get("h", ""))); cur = {}
    except Exception:
        pass
    if not names:
        try:
            from PyQt6.QtGui import QInputDevice
            names = ["%s  [%s]" % (d.name(), d.type().name) for d in QInputDevice.devices()]
        except Exception:
            pass
    return names


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------
def project_sheet_html(app):
    import html
    rows = getattr(app, "master_playlist_data", None) or []
    seed = app._seed_text() if hasattr(app, "_seed_text") else ""
    try:
        engines = ", ".join(sorted(app._get_active_engine_set())) or "none"
    except Exception:
        engines = "?"
    bpm = getattr(getattr(app, "spin_bpm", None), "value", lambda: getattr(app, "global_bpm", 120))()
    title = os.path.basename(str(getattr(app, "_current_project_path", "") or "Untitled project"))
    body = ["<h2>%s</h2>" % html.escape(title),
            "<p>Tempo %.1f BPM · canonical mode %s · engines %s · %d playlist rows</p>" % (
                float(bpm), html.escape(str(getattr(app, "canonical_mode", "protected"))), html.escape(engines), len(rows)),
            "<h3>Seed program</h3><pre style='font-size:8pt'>%s</pre>" % html.escape(seed[:12000])]
    body.append("<h3>Playlist</h3><table border=1 cellspacing=0 cellpadding=2 style='font-size:8pt'><tr><th>#</th><th>section</th><th>content</th></tr>")
    for i, r in enumerate(rows[:256]):
        if isinstance(r, dict):
            body.append("<tr><td>%d</td><td>%s</td><td>%s</td></tr>" % (i + 1, html.escape(str(r.get("section", ""))),
                        html.escape(", ".join("%s=%s" % (k, r[k]) for k in list(r)[:6] if k != "section"))[:160]))
    body.append("</table>")
    return "\n".join(body)


def print_project(app, parent=None, pdf_path=None):
    from PyQt6.QtGui import QTextDocument
    from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
    doc = QTextDocument(); doc.setHtml(project_sheet_html(app))
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    if pdf_path:
        pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat); pr.setOutputFileName(pdf_path)
        doc.print(pr); return pdf_path
    dlg = QPrintDialog(pr, parent)
    dlg.setWindowModality(Qt.WindowModality.WindowModal)
    dlg.accepted.connect(lambda: doc.print(pr))
    dlg.open()
    parent._r32_print_keep = (dlg, doc, pr) if parent is not None else None
    return None


def printers():
    try:
        from PyQt6.QtPrintSupport import QPrinterInfo
        return [p.printerName() for p in QPrinterInfo.availablePrinters()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# misc probes
# ---------------------------------------------------------------------------
def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return ""


def usb_list():
    out = _run(["lsusb"]).strip().splitlines()
    if not out:
        for d in sorted(glob.glob("/sys/bus/usb/devices/*/product")):
            try:
                out.append(open(d).read().strip())
            except Exception:
                pass
    return out


def audio_devices():
    out = []
    try:
        import sounddevice as sd
        try:
            apis = [a.get("name", "") for a in sd.query_hostapis()]
        except Exception:
            apis = []
        import device_labels as _dl
        for i, d in enumerate(sd.query_devices()):
            kind = ("out" if d["max_output_channels"] else "") + ("/in" if d["max_input_channels"] else "")
            row = dict(d); row["meta"] = dict(d)
            try:
                row["meta"]["hostapi_name"] = apis[int(d.get("hostapi", 0))]
            except Exception:
                pass
            text, _tip = _dl.label(row, "out" if d["max_output_channels"] else "in", d["name"])
            out.append("%2d  %s  (%s)" % (i, text, kind.strip("/")))
    except Exception:
        out = _run(["aplay", "-l"]).splitlines()
    return out


def test_tone(device=None, hz=440.0, seconds=0.6):
    try:
        import numpy as np, sounddevice as sd
        t = np.arange(int(48000 * seconds)) / 48000.0
        y = (0.2 * np.sin(2 * np.pi * hz * t) * np.minimum(1, np.minimum(t, seconds - t) * 40)).astype("float32")
        sd.play(y, 48000, device=device)
        return "tone on %s" % (device if device is not None else "default")
    except Exception as exc:
        return "tone failed: %s" % exc


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------
def open_window(app):
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QListWidget, QPushButton, QHBoxLayout, QLabel,
                                 QSpinBox, QCheckBox, QComboBox, QTextEdit, QFileDialog)
    import midi_io
    w = getattr(app, "_hardware_tools_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); return w
    except RuntimeError:
        pass
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🔌 Hardware · MIDI · audio · input · printers · USB")
    w.resize(820, 620); root = QVBoxLayout(w); tabs = QTabWidget(); root.addWidget(tabs)
    status = QLabel(""); root.addWidget(status)
    hub = midi_io.hub(app); hub.status.connect(status.setText)

    # MIDI
    m = QWidget(); ml = QVBoxLayout(m); tabs.addTab(m, "🎹 MIDI")
    lst_in = QListWidget(); lst_in.addItems(midi_io.list_inputs() or ["(no MIDI inputs found)"])
    ml.addWidget(QLabel("Inputs (USB-MIDI, ALSA raw, or mido)")); ml.addWidget(lst_in)
    r = QHBoxLayout()
    b_open = QPushButton("Open all inputs"); b_open.clicked.connect(hub.open_all)
    b_learn = QPushButton("MIDI learn"); b_learn.clicked.connect(hub.learn)
    base = QSpinBox(); base.setRange(0, 127); base.setValue(hub.base_note); base.setPrefix("base note ")
    base.valueChanged.connect(lambda v: setattr(hub, "base_note", int(v)))
    clk = QCheckBox("Follow external clock (start/stop)"); clk.toggled.connect(lambda v: setattr(hub, "follow_clock", bool(v)))
    for x in (b_open, b_learn, base, clk):
        r.addWidget(x)
    ml.addLayout(r)
    outs = QComboBox(); outs.addItems(["(no output)"] + midi_io.list_outputs())
    outs.currentTextChanged.connect(hub.set_output)
    b_clock = QPushButton("Send clock at project tempo")
    b_clock.clicked.connect(lambda: hub.send_clock(getattr(getattr(app, "spin_bpm", None), "value", lambda: 120)()))
    r2 = QHBoxLayout(); r2.addWidget(QLabel("Output")); r2.addWidget(outs); r2.addWidget(b_clock); ml.addLayout(r2)
    maps = QListWidget(); ml.addWidget(QLabel("Learned mappings (CC → control)")); ml.addWidget(maps)

    def _fill_maps():
        maps.clear(); maps.addItems(["CC %s → %s" % (k, v) for k, v in sorted(hub.map.items())])
    b_clear = QPushButton("Clear mappings"); b_clear.clicked.connect(lambda: (hub.map.clear(), hub._save_map(), _fill_maps()))
    b_ref = QPushButton("Refresh"); b_ref.clicked.connect(lambda: (lst_in.clear(), lst_in.addItems(midi_io.list_inputs() or ["(none)"]), _fill_maps()))
    r3 = QHBoxLayout(); r3.addWidget(b_clear); r3.addWidget(b_ref); ml.addLayout(r3); _fill_maps()

    # Audio
    a = QWidget(); al = QVBoxLayout(a); tabs.addTab(a, "🔊 Audio")
    lst_a = QListWidget(); lst_a.addItems(audio_devices()); al.addWidget(lst_a)
    r = QHBoxLayout()
    b_tone = QPushButton("Test tone on selected")

    def _tone():
        it = lst_a.currentItem()
        dev = int(it.text().split()[0]) if it and it.text().split()[0].isdigit() else None
        status.setText(test_tone(dev))
    b_tone.clicked.connect(_tone)
    b_both = QPushButton("Install Both outputs (HDMI + speakers)")

    def _both():
        import audio_both_output as abo
        wr, p, _t = abo.install(); status.setText(("written " if wr else "unchanged ") + (p or "(no ALSA cards)"))
    b_both.clicked.connect(_both)
    r.addWidget(b_tone); r.addWidget(b_both); al.addLayout(r)

    # Input
    i = QWidget(); il = QVBoxLayout(i); tabs.addTab(i, "🖱 Input")
    lst_i = QListWidget(); lst_i.addItems(input_devices()); il.addWidget(QLabel("Mice · keyboards · trackpads · touchscreens · pens · gamepads")); il.addWidget(lst_i)
    pad = QTextEdit(); pad.setReadOnly(True); pad.setPlaceholderText("Input tester: click, scroll, type, touch or pinch here")
    pad.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

    class _Tester(QObject):
        def eventFilter(self, obj, ev):
            names = {QEvent.Type.MouseButtonPress: "mouse press", QEvent.Type.Wheel: "wheel", QEvent.Type.KeyPress: "key",
                     QEvent.Type.TouchBegin: "touch", QEvent.Type.TabletPress: "pen"}
            n = names.get(ev.type())
            if n:
                dev = ""
                try:
                    d = ev.device(); dev = "%s (%s)" % (d.name(), d.type().name)
                except Exception:
                    pass
                extra = ""
                if ev.type() == QEvent.Type.Wheel:
                    extra = " Δ%s px%s" % (ev.angleDelta().y(), " (hi-res trackpad)" if not ev.pixelDelta().isNull() else "")
                if ev.type() == QEvent.Type.KeyPress:
                    extra = " %r" % ev.text()
                pad.append("%s%s · %s" % (n, extra, dev))
            return False
    tester = _Tester(pad); pad.viewport().installEventFilter(tester); pad.installEventFilter(tester); w._tester = tester
    il.addWidget(pad)
    il.addWidget(QLabel("Touch: long-press = right-click · two-finger pinch = zoom · two-finger drag = scroll"))

    # Printers
    p = QWidget(); pl = QVBoxLayout(p); tabs.addTab(p, "🖨 Printers")
    lst_p = QListWidget(); lst_p.addItems(printers() or ["(no printers — use Save as PDF)"]); pl.addWidget(lst_p)
    r = QHBoxLayout()
    b_print = QPushButton("Print project sheet…"); b_print.clicked.connect(lambda: print_project(app, w))
    b_pdf = QPushButton("Save project sheet as PDF…")

    def _pdf():
        path, _ = QFileDialog.getSaveFileName(w, "Project sheet PDF", "project-sheet.pdf", "PDF (*.pdf)")
        if path:
            status.setText("saved " + print_project(app, w, path))
    b_pdf.clicked.connect(_pdf)
    r.addWidget(b_print); r.addWidget(b_pdf); pl.addLayout(r)

    # USB / storage
    u = QWidget(); ul = QVBoxLayout(u); tabs.addTab(u, "🔌 USB / storage / cameras")
    txt = QTextEdit(); txt.setReadOnly(True); txt.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;"); ul.addWidget(txt)

    def _usb():
        drives = _run(["lsblk", "-o", "NAME,SIZE,RM,TYPE,MOUNTPOINT,LABEL"]).strip()
        cams = "\n".join(sorted(glob.glob("/dev/video*"))) or "(none)"
        txt.setPlainText("USB devices\n" + "\n".join(usb_list() or ["(lsusb unavailable)"]) +
                         "\n\nDrives\n" + (drives or "(lsblk unavailable)") + "\n\nCameras\n" + cams)
    b_u = QPushButton("Refresh"); b_u.clicked.connect(_usb); ul.addWidget(b_u); _usb()

    app._hardware_tools_window = w; w.show(); return w
