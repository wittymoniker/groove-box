"""🔊 Hardware & Master — one window for everything between the mix and the speakers.

GROOVEBOX_R23R_HARDWARE_MASTER_PANEL_20261103

* Master Volume (the final gain; canonicals never touch it) with a dB readout,
  kept in sync both ways with the main window's Master Volume slider.
* Live output meter: peak + RMS in dBFS from the shared scope feed.
* Hardware volume (ALSA / PipeWire / laptop media keys) with mute and re-sync.
* Output device: "All detected outputs (default)" or one device; mic level prep.
* 432 Hz test tone through the same output path as Trigger Note.
"""
from __future__ import annotations

import math

import numpy as np
from qt_painting import owned_painter
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import (QComboBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout,
                             QWidget)

ALL_OUTPUTS = "All detected outputs (default)"


class _Meter(QWidget):
    """Horizontal peak / RMS meter in dBFS (−60 … 0)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(26)
        self.peak_db = -90.0
        self.rms_db = -90.0
        self.hold_db = -90.0

    def set_levels(self, peak, rms):
        self.peak_db = 20.0 * math.log10(peak) if peak > 0 else -math.inf   # silence = -inf dB (exact)
        self.rms_db = 20.0 * math.log10(rms) if rms > 0 else -math.inf
        self.hold_db = max(self.peak_db, self.hold_db - 0.6)
        self.update()

    def paintEvent(self, _e):
        with owned_painter(self) as p:
            if p is None:
                return
            r = self.rect()
            p.fillRect(r, QColor("#0b0f14"))
            x = lambda db: r.width() * (max(-60.0, min(0.0, db)) + 60.0) / 60.0
            g = QLinearGradient(0, 0, r.width(), 0)
            g.setColorAt(0.0, QColor("#0d6e8a")); g.setColorAt(0.75, QColor("#00ffaa"))
            g.setColorAt(0.9, QColor("#ffd166")); g.setColorAt(1.0, QColor("#ff4d4d"))
            p.fillRect(0, 3, int(x(self.rms_db)), r.height() // 2 - 3, g)
            p.fillRect(0, r.height() // 2 + 1, int(x(self.peak_db)), r.height() // 2 - 4, g)
            p.setPen(QColor("#ffffff")); p.drawLine(int(x(self.hold_db)), 2, int(x(self.hold_db)), r.height() - 2)
            p.setPen(QColor("#4a5560"))
            for db in (-48, -36, -24, -12, -6, -3, 0):
                xx = int(x(db)); p.drawLine(xx, r.height() - 5, xx, r.height())
            p.setPen(QColor("#c9d6e2"))
            p.drawText(r.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       f"peak {self.peak_db:5.1f} dBFS · rms {self.rms_db:5.1f}")
            p.end()


class MasterHardwarePanel(QDialog):
    def __init__(self, host, parent=None):
        super().__init__(parent or host)
        self.host = host
        self.setWindowTitle("🔊 Hardware & Master")
        self.setModal(False)
        self.resize(760, 720)
        self.setStyleSheet(
            "QDialog { background:#0f141a; color:#dfe8f0; }"
            "QGroupBox { border:1px solid #2c3a48; border-radius:8px; margin-top:10px; padding-top:8px; font-weight:800; color:#f5a623; }"
            "QGroupBox::title { subcontrol-origin: margin; left:10px; padding:0 4px; }"
            "QSlider::groove:horizontal { background:#3a2a12; height:12px; border-radius:6px; }"
            "QSlider::sub-page:horizontal { background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #8a5a12, stop:1 #ffb347); height:12px; border-radius:6px; }"
            "QSlider::handle:horizontal { background:#ffe2b0; border:2px solid #f5a623; width:22px; margin:-6px 0; border-radius:11px; }"
            "QPushButton { background:#16212c; color:#d9f1ff; border:1px solid #33586b; border-radius:8px; padding:6px 10px; font-weight:700; }"
            "QPushButton:checked { background:#5a1f1f; border-color:#ff6b6b; }")
        lay = QVBoxLayout(self)

        # --- master
        gm = QGroupBox("Master Volume — final gain (canonicals never change it)")
        lm = QVBoxLayout(gm)
        row = QHBoxLayout()
        self.sld_master = QSlider(Qt.Orientation.Horizontal); self.sld_master.setRange(0, 100)
        self.lbl_master = QLabel(""); self.lbl_master.setMinimumWidth(130)
        self.lbl_master.setStyleSheet("color:#f5a623; font-weight:900; font-size:14pt;")
        row.addWidget(self.sld_master, 1); row.addWidget(self.lbl_master)
        lm.addLayout(row)
        self.meter = _Meter(); lm.addWidget(self.meter)
        self.lbl_clip = QLabel(""); self.lbl_clip.setStyleSheet("color:#8da5b8;"); lm.addWidget(self.lbl_clip)
        lay.addWidget(gm)

        # --- hardware
        gh = QGroupBox("Hardware volume — speakers / headphones (ALSA · PipeWire · media keys)")
        lh = QVBoxLayout(gh)
        try:
            from hardware_volume import HardwareVolumeWidget
            self.hw = HardwareVolumeWidget(self, compact=False)
            lh.addWidget(self.hw)
        except Exception as exc:
            self.hw = None
            lh.addWidget(QLabel(f"Hardware volume control unavailable here ({exc})."))
        hr = QHBoxLayout()
        self.btn_mute = QPushButton("🔇 Mute"); self.btn_mute.setCheckable(True)
        self.btn_sync = QPushButton("↻ Re-sync hardware")
        self.btn_mic = QPushButton("🎤 Prepare mic level")
        for b in (self.btn_mute, self.btn_sync, self.btn_mic):
            hr.addWidget(b)
        lh.addLayout(hr)
        lay.addWidget(gh)

        # --- outputs
        go = QGroupBox("Output")
        lo = QHBoxLayout(go)
        self.cmb_out = QComboBox(); self.cmb_out.setMinimumWidth(300)
        self.btn_rescan = QPushButton("↻"); self.btn_rescan.setToolTip("Rescan output devices")
        self.btn_tone = QPushButton("▶ 432 Hz test tone")
        lo.addWidget(self.cmb_out, 1); lo.addWidget(self.btn_rescan); lo.addWidget(self.btn_tone)
        lay.addWidget(go)
        # --- devices (GROOVEBOX_R23R_DEVICE_PROFILES_20261103)
        gd = QGroupBox("Devices — set each output once; every stream matches it")
        ld = QVBoxLayout(gd)
        from PyQt6.QtWidgets import QTableWidget, QHeaderView, QCheckBox, QTableWidgetItem
        self.tbl_dev = QTableWidget(0, 5)
        self.tbl_dev.setHorizontalHeaderLabels(["On", "Device", "Sample rate", "Bit depth", "Supports"])
        self.tbl_dev.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_dev.verticalHeader().setVisible(False)
        self.tbl_dev.setMinimumHeight(170)
        ld.addWidget(self.tbl_dev)
        rowb = QHBoxLayout()
        self.btn_probe = QPushButton("🔍 Probe formats")
        self.btn_probe.setToolTip("Ask every output which sample rates / bit depths it accepts (no sound is played)")
        self.lbl_dev = QLabel("On = part of 'All outputs'. Rate / depth: Auto lets the app negotiate.")
        self.lbl_dev.setWordWrap(True); self.lbl_dev.setStyleSheet("color:#8da5b8;")
        rowb.addWidget(self.btn_probe); rowb.addWidget(self.lbl_dev, 1)
        ld.addLayout(rowb)
        lay.addWidget(gd)
        self.btn_probe.clicked.connect(self._probe_devices)
        self._dev_probe = {}
        self.lbl_status = QLabel(""); self.lbl_status.setWordWrap(True); self.lbl_status.setStyleSheet("color:#8da5b8;")
        lay.addWidget(self.lbl_status)

        # wiring
        self.sld_master.valueChanged.connect(self._on_master)
        self.btn_mute.toggled.connect(self._on_mute)
        self.btn_sync.clicked.connect(self._on_sync)
        self.btn_mic.clicked.connect(self._on_mic)
        self.btn_rescan.clicked.connect(self._fill_outputs)
        self.btn_tone.clicked.connect(self._test_tone)
        self.cmb_out.currentTextChanged.connect(self._on_output)
        vis = getattr(host, "slider_master_vol_visible", None)
        if vis is not None:
            vis.valueChanged.connect(self._from_main)
        self._fill_outputs()
        self._fill_devices()
        self._from_main()
        self._timer = QTimer(self); self._timer.setInterval(50); self._timer.timeout.connect(self._tick); self._timer.start()

    # ---------------------------------------------------------------- master
    def _db_text(self, v):
        return "−∞ dB" if v <= 0 else f"{20.0 * math.log10(v / 100.0):+.1f} dB"

    def _from_main(self, *_a):
        vis = getattr(self.host, "slider_master_vol_visible", None)
        v = int(vis.value()) if vis is not None else int(round(float(getattr(self.host, "master_volume", 0.72)) * 100))
        self.sld_master.blockSignals(True); self.sld_master.setValue(v); self.sld_master.blockSignals(False)
        self.lbl_master.setText(f"{v}%  {self._db_text(v)}")

    def _on_master(self, v):
        vis = getattr(self.host, "slider_master_vol_visible", None)
        if vis is not None and vis.value() != int(v):
            vis.setValue(int(v))           # one source of truth: the main Master Volume
        elif hasattr(self.host, "_on_master_vol_changed"):
            self.host._on_master_vol_changed(int(v))
        self.lbl_master.setText(f"{int(v)}%  {self._db_text(int(v))}")

    def _tick(self):
        if not self.isVisible():
            return
        chunk = getattr(self.host, "_last_scope_chunk", None)
        try:
            a = np.asarray(chunk, dtype=np.float64) if chunk is not None else np.zeros(1)
            peak = float(np.max(np.abs(a))) if a.size else 0.0
            rms = float(np.sqrt(np.mean(a * a))) if a.size else 0.0
        except Exception:
            peak = rms = 0.0
        self.meter.set_levels(peak, rms)
        try:
            cr = getattr(self.host, "spin_clip_ratio", None)
            self.lbl_clip.setText(f"Master hard clip: {cr.value():.1f}" if cr is not None else "Master hard clip: on")
        except Exception:
            pass

    # -------------------------------------------------------------- hardware
    def _on_mute(self, on):
        try:
            from hardware_volume import request_hardware_volume
            ok = request_hardware_volume("mute" if on else "unmute")
        except Exception:
            ok = False
        self.btn_mute.setText("🔇 Muted" if on else "🔇 Mute")
        self.lbl_status.setText(("Hardware muted" if on else "Hardware unmuted") + ("" if ok else " (no hardware helper on this system — desktop mixer controls the speakers)"))

    def _on_sync(self):
        try:
            from hardware_volume import request_hardware_volume, read_hardware_volume_state
            ok = request_hardware_volume("sync")
            st = read_hardware_volume_state()
            self.lbl_status.setText(f"Re-sync {'requested' if ok else 'not available here'} · card {st.get('card') or '—'} · "
                                    f"control {st.get('control') or '—'} · {st.get('volume')}%{' · muted' if st.get('muted') else ''}")
        except Exception as exc:
            self.lbl_status.setText(f"Re-sync failed: {exc}")

    def _on_mic(self):
        try:
            from audio_os_backend import prepare_capture_level
            r = prepare_capture_level()
            self.lbl_status.setText(f"Mic capture level prepared: {r}")
        except Exception as exc:
            self.lbl_status.setText(f"Mic level prep failed: {exc}")

    # ---------------------------------------------------------------- output
    def _fill_outputs(self):
        cur = str(getattr(self.host, "_preferred_audio_output_name", "") or "") or ALL_OUTPUTS
        names = [ALL_OUTPUTS]
        try:
            from audio_os_backend import sd, HAS_SOUNDDEVICE
            if HAS_SOUNDDEVICE:
                for d in sd.query_devices():
                    if int(d.get("max_output_channels", 0) or 0) > 0 and d.get("name") not in names:
                        names.append(str(d.get("name")))
        except Exception:
            pass
        self.cmb_out.blockSignals(True)
        self.cmb_out.clear(); self.cmb_out.addItems(names)
        self.cmb_out.setCurrentText(cur if cur in names else ALL_OUTPUTS)
        self.cmb_out.blockSignals(False)
        self.lbl_status.setText(f"{len(names) - 1} output device(s) detected · using: {self.cmb_out.currentText()}")

    # ---------------------------------------------------------------- devices
    def _device_rows(self):
        """(profile key, label, portaudio index or None) for every output: PortAudio devices and
        sound-server sinks (keys "pulse:<sink>")."""
        rows = []
        try:
            from audio_os_backend import sd, HAS_SOUNDDEVICE
            if HAS_SOUNDDEVICE:
                for i, d in enumerate(sd.query_devices()):
                    if int(d.get("max_output_channels", 0) or 0) > 0:
                        rows.append((str(d.get("name")), str(d.get("name")), i))
        except Exception:
            pass
        try:
            import shutil, subprocess
            if shutil.which("pactl"):
                out = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, text=True, timeout=2).stdout
                for line in out.splitlines():
                    parts = line.split("\t") if "\t" in line else line.split()
                    if len(parts) >= 2 and "groovebox_all_outputs" not in parts[1]:
                        rows.append(("pulse:" + parts[1], "🔈 " + parts[1], None))
        except Exception:
            pass
        return rows

    def _fill_devices(self):
        import audio_device_profiles as adp
        from PyQt6.QtWidgets import QCheckBox, QTableWidgetItem
        rows = self._device_rows()
        t = self.tbl_dev
        t.setRowCount(len(rows))
        self._dev_keys = []
        for r, (key, label, idx) in enumerate(rows):
            prof = adp.get(key)
            sup = self._dev_probe.get(key)
            chk = QCheckBox(); chk.setChecked(bool(prof["enabled"]))
            chk.toggled.connect(lambda on, k=key: self._dev_set(k, enabled=bool(on)))
            t.setCellWidget(r, 0, chk)
            it = QTableWidgetItem(label); it.setToolTip(key); t.setItem(r, 1, it)
            cr = QComboBox(); cr.addItem("Auto", 0)
            for rate in (sup["rates"] if sup else adp.RATES):
                cr.addItem(f"{rate / 1000:g} kHz", rate)
            i = cr.findData(int(prof["rate"])); cr.setCurrentIndex(max(0, i))
            cr.currentIndexChanged.connect(lambda _i, k=key, c=cr: self._dev_set(k, rate=int(c.currentData() or 0)))
            cb = QComboBox()
            for b in (sup["bits"] if sup else adp.BITS):
                cb.addItem({0: "32-bit float", 16: "16-bit", 24: "24-bit", 32: "32-bit"}[b], b)
            if cb.findData(0) < 0:
                cb.insertItem(0, "32-bit float", 0)
            i = cb.findData(int(prof["bits"])); cb.setCurrentIndex(max(0, i))
            cb.currentIndexChanged.connect(lambda _i, k=key, c=cb: self._dev_set(k, bits=int(c.currentData() or 0)))
            if idx is None:            # sound-server sinks: on / off only (the server picks their format)
                cr.setEnabled(False); cb.setEnabled(False)
            t.setCellWidget(r, 2, cr); t.setCellWidget(r, 3, cb)
            t.setItem(r, 4, QTableWidgetItem(
                (", ".join(f"{x / 1000:g}k" for x in sup["rates"]) + " · " +
                 "/".join({0: "f32", 16: "16", 24: "24", 32: "32"}[b] for b in sup["bits"])) if sup else
                ("sound server" if idx is None else "not probed")))
            self._dev_keys.append((key, idx))

    def _dev_set(self, key, **kw):
        import audio_device_profiles as adp
        adp.set_profile(key, **kw)
        try:
            self.host._close_audition_stream()          # next note / play opens with the new format
        except Exception:
            pass
        if "enabled" in kw and key.startswith("pulse:"):
            try:    # rebuild the All-outputs sink on a worker (never on this thread)
                import threading, media_output_router as mor
                threading.Thread(target=mor.prewarm_all_outputs, daemon=True).start()
            except Exception:
                pass
        self.lbl_status.setText(f"{key}: {kw} — applies to the next stream that opens")

    def _probe_devices(self):
        import threading
        self.btn_probe.setEnabled(False); self.lbl_dev.setText("Probing…")
        keys = [(k, i) for k, i in getattr(self, "_dev_keys", []) if i is not None]

        def work():
            res = {}
            try:
                import audio_device_profiles as adp
                from audio_os_backend import sd
                for k, i in keys:
                    try:
                        res[k] = adp.probe(sd, i)
                    except Exception:
                        pass
            finally:
                self._probe_result = res
        self._probe_result = None
        threading.Thread(target=work, daemon=True).start()
        QTimer.singleShot(150, self._probe_poll)

    def _probe_poll(self):
        if self._probe_result is None:
            QTimer.singleShot(150, self._probe_poll); return
        self._dev_probe.update(self._probe_result)
        self.btn_probe.setEnabled(True)
        self.lbl_dev.setText(f"Probed {len(self._probe_result)} device(s). Choose a rate / depth per device, or Auto.")
        self._fill_devices()

    def _on_output(self, name):
        self.host._preferred_audio_output_name = "" if name == ALL_OUTPUTS else str(name)
        try:
            self.host._close_audition_stream()
        except Exception:
            pass
        self.lbl_status.setText(f"Output → {name} (applies to the next note / playback start)")

    def _test_tone(self):
        try:
            sr = 44100; t = np.arange(int(sr * 0.6)) / sr
            env = np.minimum(1.0, t / 0.01) * np.minimum(1.0, (0.6 - t) / 0.05)
            tone = (0.25 * np.sin(2 * np.pi * 432.0 * t) * env).astype(np.float32)
            self.host._pkp_poly_submit(tone, sr)
            self.lbl_status.setText("432 Hz test tone sent through the Trigger Note output path")
        except Exception as exc:
            self.lbl_status.setText(f"Test tone failed: {exc}")

    def closeEvent(self, e):
        self._timer.stop()
        super().closeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        self._timer.start()
        self._from_main()
