"""Compact Qt surface for the jam-only LiveJamController."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QEvent, Qt, QTimer
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QPushButton, QLineEdit, QSlider,
                             QCheckBox, QGroupBox, QWidget, QMessageBox, QProgressBar, QScrollArea)

from live_jam import LiveJamController, MACRO_KEYS


class _JamInputFilter(QObject):
    """Global filter, active only during Live Jam and never while editing text."""
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.host = dialog.host

    def _inside(self, widget, parent):
        try:
            cur = widget
            while cur is not None:
                if cur is parent:
                    return True
                cur = cur.parentWidget() if hasattr(cur, "parentWidget") else None
        except Exception:
            pass
        return False

    def eventFilter(self, watched, event):
        d = self.dialog
        c = d.controller
        if not c.enabled:
            return False
        try:
            active = d.window().isActiveWindow() or self.host.isActiveWindow()
            if not active:
                return False
            if event.type() == QEvent.Type.KeyPress:
                if event.isAutoRepeat():
                    return False
                if isinstance(watched, (QLineEdit,)) or getattr(watched, "isReadOnly", lambda: False)():
                    return False
                key = int(event.key())
                f1 = int(Qt.Key.Key_F1)
                if f1 <= key < f1 + 12:
                    macro = f"F{key-f1+1}"
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        d._play_pattern_macro(macro)
                    else:
                        d._dispatch(c.nudge_macro(macro, 0.05, timestamp=0.0))
                        d._sync_from_controller()
                    return True
                arrows = {
                    int(Qt.Key.Key_Left): "LEFT", int(Qt.Key.Key_Right): "RIGHT",
                    int(Qt.Key.Key_Up): "UP", int(Qt.Key.Key_Down): "DOWN",
                }
                if key in arrows:
                    out = c.key(arrows[key], timestamp=0.0)
                    d._dispatch(out)
                    d._sync_from_controller()
                    return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                if self._inside(watched, d):
                    return False
                btn = event.button()
                mapping = {Qt.MouseButton.LeftButton: "MOUSE_1",
                           Qt.MouseButton.MiddleButton: "MOUSE_2",
                           Qt.MouseButton.RightButton: "MOUSE_3"}
                if btn in mapping:
                    out = c.mouse(mapping[btn], timestamp=0.0)
                    d._dispatch(out)
                    d._sync_from_controller()
                    return False
        except Exception:
            return False
        return False


class LiveJamDialog(QDialog):
    def __init__(self, host, parent=None):
        super().__init__(parent or host)
        self.host = host
        self.controller = getattr(host, "_live_jam_controller", None)
        if not isinstance(self.controller, LiveJamController):
            self.controller = LiveJamController(seed=getattr(host, "get_numeric_seed", lambda: 0)(), seeded_mode=True)
            host._live_jam_controller = self.controller
        self.setWindowTitle("LIVE JAM · Canonical Performance")
        self.setMinimumWidth(760)
        self.resize(1040, 820)
        self.setStyleSheet("""
            QDialog { background:#0b1020; color:#edf5ff; }
            QGroupBox { border:1px solid #5540a8; border-radius:10px; margin-top:10px; padding:9px; color:#c7a6ff; font-weight:900; background:#121a30; }
            QPushButton { background:#203b62; color:#f2f7ff; border:1px solid #3e8bc5; border-radius:7px; padding:7px 11px; font-weight:800; }
            QPushButton:hover { background:#315a91; border-color:#69d8ff; }
            QPushButton:checked { background:#8b234d; border:2px solid #ff6c9c; }
            QLineEdit { background:#111f38; border:1px solid #3980a8; border-radius:5px; color:#fff; padding:6px; }
            QSlider::groove:horizontal { height:7px; background:#293d60; border-radius:3px; }
            QSlider::handle:horizontal { width:16px; margin:-5px 0; border-radius:7px; background:#55e0d0; border:1px solid #c0fff4; }
            QLabel { color:#e3edfa; }
            QProgressBar { background:#111a2c; border:1px solid #315b83; border-radius:5px; text-align:center; color:#fff; height:14px; }
            QProgressBar::chunk { background:#27c7ae; border-radius:4px; }
        """)
        root = QVBoxLayout(self)
        self._scroll_area = QScrollArea(self); self._scroll_area.setWidgetResizable(True)
        self._scroll_body = QWidget(); self._scroll_area.setWidget(self._scroll_body)
        outer_root = root; root = QVBoxLayout(self._scroll_body)
        outer_root.addWidget(self._scroll_area)
        head = QHBoxLayout()
        title = QLabel("LIVE JAM  ·  F1–F12 MORPH  ·  ARROWS ENVELOPE  ·  MOUSE FX")
        title.setStyleSheet("color:#8be2d7;font-weight:900;font-size:14px;")
        head.addWidget(title, 1)
        self.status = QLabel("STOPPED")
        self.status.setStyleSheet("color:#ffbd69;font-weight:900;")
        head.addWidget(self.status)
        root.addLayout(head)
        meter_box = QGroupBox("LIVE AUDIO TELEMETRY · MASTER OUTPUT")
        meter_grid = QGridLayout(meter_box)
        self.level_meter = QProgressBar(); self.level_meter.setRange(0, 1000); self.level_meter.setFormat("LEVEL  %p‰")
        self.peak_meter = QProgressBar(); self.peak_meter.setRange(0, 1000); self.peak_meter.setFormat("PEAK  %p‰")
        self.audio_info = QLabel("Waiting for master audio…")
        meter_grid.addWidget(QLabel("RMS"), 0, 0); meter_grid.addWidget(self.level_meter, 0, 1)
        meter_grid.addWidget(QLabel("Peak"), 1, 0); meter_grid.addWidget(self.peak_meter, 1, 1)
        meter_grid.addWidget(self.audio_info, 2, 0, 1, 2)
        root.addWidget(meter_box)
        self._meter_timer = QTimer(self); self._meter_timer.setInterval(80); self._meter_timer.timeout.connect(self._refresh_audio_meter); self._meter_timer.start()
        row = QHBoxLayout()
        self.seed = QLineEdit(str(self.controller.seed))
        self.seed.setPlaceholderText("Seed")
        row.addWidget(QLabel("Seed")); row.addWidget(self.seed, 1)
        self.btn_seeded = QCheckBox("Seeded mode")
        self.btn_seeded.setChecked(self.controller.seeded_mode)
        row.addWidget(self.btn_seeded)
        self.btn_start = QPushButton("▶ START JAM")
        self.btn_start.clicked.connect(self._start)
        row.addWidget(self.btn_start)
        self.btn_stop = QPushButton("■ STOP")
        self.btn_stop.clicked.connect(self._stop)
        row.addWidget(self.btn_stop)
        root.addLayout(row)

        macros = QGroupBox("SYSTEM MORPH MACROS · press F1–F12 while jamming")
        grid = QGridLayout(macros)
        self.macro_sliders = {}
        self.macro_labels = {}
        for i, key in enumerate(MACRO_KEYS):
            lab = QLabel(key); lab.setStyleSheet("color:%s;font-weight:1000;font-size:10pt;" % ("#ff7ca8" if i < 4 else "#6ee7d8" if i < 8 else "#c39cff"))
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, 100); sl.setValue(50)
            value = QLabel("0.50"); value.setMinimumWidth(34)
            sl.valueChanged.connect(lambda v, k=key, o=value: self._macro_changed(k, v, o))
            col, rr = (i // 4), (i % 4)
            grid.addWidget(lab, rr, col * 3)
            grid.addWidget(sl, rr, col * 3 + 1)
            grid.addWidget(value, rr, col * 3 + 2)
            self.macro_sliders[key] = sl; self.macro_labels[key] = value
        root.addWidget(macros)

        controls = QGroupBox("LIVE INPUTS · randomized bindings are jam-only")
        cr = QGridLayout(controls)
        cr.addWidget(QLabel("← / →  release · ↑ / ↓  attack"), 0, 0, 1, 2)
        cr.addWidget(QLabel("Mouse 1 filter · Mouse 2 damping · Mouse 3 FX"), 1, 0, 1, 2)
        self.randomize = QPushButton("🎲 Randomize jam bindings")
        self.randomize.clicked.connect(self._randomize)
        cr.addWidget(self.randomize, 0, 2, 2, 1)
        root.addWidget(controls)

        seq = QGroupBox("JAM SEQUENCER · sequence the sequences")
        sg = QGridLayout(seq)
        self.seq_name = QLineEdit("Jam A")
        self.seq_ids = QLineEdit("1,2,3,4")
        self.seq_load = QPushButton("SET BANK")
        self.seq_load.clicked.connect(self._set_sequence)
        self.seq_next = QPushButton("TRIGGER NEXT")
        self.seq_next.clicked.connect(self._trigger_sequence)
        sg.addWidget(QLabel("Bank"), 0, 0); sg.addWidget(self.seq_name, 0, 1)
        sg.addWidget(QLabel("Sequence IDs"), 1, 0); sg.addWidget(self.seq_ids, 1, 1)
        sg.addWidget(self.seq_load, 0, 2, 1, 1); sg.addWidget(self.seq_next, 1, 2, 1, 1)
        self.fx_checks = {}
        for i, fx in enumerate(("Delay", "Reverb", "Chorus", "Drive")):
            cb = QCheckBox(fx)
            cb.toggled.connect(lambda on, name=fx: self._set_fx(name, on))
            sg.addWidget(cb, 2, i)
            self.fx_checks[fx] = cb
        # LIVE_JAM_RECORDABLE_20261104: capture event log + snapshot for post-record video render
        self.btn_record = QPushButton("⏺ RECORD SESSION")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self._toggle_record)
        sg.addWidget(self.btn_record, 3, 0, 1, 2)
        self.btn_save_snap = QPushButton("💾 SAVE SNAPSHOT FOR RENDER")
        self.btn_save_snap.clicked.connect(self._save_for_render)
        sg.addWidget(self.btn_save_snap, 3, 2, 1, 2)
        root.addWidget(seq)

        patterns = QGroupBox("MULTI-SAMPLE / JAM PATTERNS · record notes + bend as timed entries")
        pg = QGridLayout(patterns)
        self.pattern_name = QLineEdit("Jam Pattern 1")
        self.pattern_macro_key = QLineEdit("F1")
        self.btn_save_pattern = QPushButton("SAVE TAKE AS PATTERN")
        self.btn_save_pattern.clicked.connect(self._save_pattern)
        self.btn_assign_pattern = QPushButton("ASSIGN MACRO")
        self.btn_assign_pattern.clicked.connect(self._assign_pattern_macro)
        self.btn_play_pattern = QPushButton("▶ PLAY PATTERN")
        self.btn_play_pattern.clicked.connect(lambda: self._play_pattern(self.pattern_name.text().strip()))
        pg.addWidget(QLabel("Pattern"), 0, 0); pg.addWidget(self.pattern_name, 0, 1)
        pg.addWidget(QLabel("Macro key"), 0, 2); pg.addWidget(self.pattern_macro_key, 0, 3)
        pg.addWidget(self.btn_save_pattern, 1, 0, 1, 2)
        pg.addWidget(self.btn_assign_pattern, 1, 2)
        pg.addWidget(self.btn_play_pattern, 1, 3)
        pg.addWidget(QLabel("Record Session captures multiple key/sample hits and pitch-bend moves. The take duration defines the pattern envelope."), 2, 0, 1, 4)
        root.addWidget(patterns)
        self._pattern_timers = []
        foot = QLabel("Jam input never changes normal keyboard, mouse, or editor bindings. Shift+F1–F12 plays its assigned pattern; plain F1–F12 still nudges morph macros. Stop Jam to restore normal controls.")
        foot.setStyleSheet("color:#94a7bc;font-size:10px;")
        root.addWidget(foot)
        self._filter = _JamInputFilter(self)
        app = self.host.window().windowHandle() if False else None
        from PyQt6.QtWidgets import QApplication
        self._qapp = QApplication.instance()
        self._filter_installed = False
        self._install_jam_filter()
        self._refresh_button_state()

    def _install_jam_filter(self):
        try:
            if self._qapp is not None and not self._filter_installed:
                self._qapp.installEventFilter(self._filter)
                self._filter_installed = True
        except Exception:
            pass

    def showEvent(self, event):
        self._install_jam_filter()
        super().showEvent(event)

    def _dispatch(self, event):
        if not event:
            return
        # Every live control change is timestamped into the same take as notes.
        try:
            if getattr(self.host, "_live_jam_recording", False):
                self.controller.record_performance_event(str(event.get("kind", "control")),
                    **{k: v for k, v in event.items() if k not in ("kind", "timestamp")})
        except Exception:
            pass
        fn = getattr(self.host, "_handle_live_jam_event", None)
        if callable(fn):
            fn(event)

    def _macro_changed(self, key, value, label):
        try:
            event = self.controller.key(key, float(value) / 100.0)
            self._dispatch(event)
            label.setText(f"{float(value)/100.0:.2f}")
        except Exception:
            pass

    def _sync_from_controller(self):
        snap = self.controller.snapshot()
        for key, slider in self.macro_sliders.items():
            v = int(round(float(snap["macros"].get(key, 0.5)) * 100))
            slider.blockSignals(True); slider.setValue(v); slider.blockSignals(False)
            self.macro_labels[key].setText(f"{v/100:.2f}")
        self._refresh_button_state()

    def _refresh_button_state(self):
        running = bool(self.controller.enabled)
        self.status.setText("JAM ACTIVE" if running else "STOPPED")
        self.status.setStyleSheet("color:#62e1b2;font-weight:900;" if running else "color:#ffbd69;font-weight:900;")
        self.btn_start.setEnabled(not running); self.btn_stop.setEnabled(running)

    def _start(self):
        self.controller.seed = self.seed.text().strip() or "0"
        self.controller.seeded_mode = self.btn_seeded.isChecked()
        self.controller.start(); self._refresh_button_state()

    def _stop(self):
        self.controller.stop(); self._refresh_button_state()

    def _randomize(self):
        try:
            self.controller.seed = self.seed.text().strip() or "0"
            self.controller.randomize_jam_bindings(self.controller.seed)
            QMessageBox.information(self, "Jam Bindings", "Jam-only keyboard and mouse bindings randomized deterministically from the seed.")
        except Exception as exc:
            QMessageBox.warning(self, "Randomize Jam", str(exc))

    def _set_sequence(self):
        ids = [x.strip() for x in self.seq_ids.text().split(",") if x.strip()]
        self.controller.set_sequence(self.seq_name.text().strip() or "Jam A", ids)
        self.status.setText(f"BANK · {len(ids)} items")

    def _trigger_sequence(self):
        ev = self.controller.trigger_sequence(self.seq_name.text().strip() or "Jam A")
        self._dispatch(ev)

    def _set_fx(self, name, on):
        self.controller.set_fx(name, on)
        self._dispatch({"kind":"fx","target":name,"enabled":bool(on),"timestamp":0.0})

    def closeEvent(self, event):
        try:
            if self._qapp is not None and self._filter_installed:
                self._qapp.removeEventFilter(self._filter)
                self._filter_installed = False
        except Exception:
            pass
        self.controller.stop()
        self._refresh_button_state()
        super().closeEvent(event)

    def _save_pattern(self):
        name = self.pattern_name.text().strip() or "Jam Pattern"
        try:
            take = self.controller.finish_performance_recording()
            saved = self.controller.save_pattern(name, take)
            self.host._live_jam_render_snapshot = self.controller.snapshot()
            self.host._live_jam_render_log = take.get("events", [])
            self.status.setText(f"PATTERN · {saved['entries']} entries · {saved['duration']:.2f}s")
        except Exception as exc:
            QMessageBox.warning(self, "Save Jam Pattern", str(exc))

    def _assign_pattern_macro(self):
        try:
            self.controller.assign_pattern_macro(self.pattern_macro_key.text().strip(), self.pattern_name.text().strip())
            self.status.setText(f"{self.pattern_macro_key.text().strip().upper()} → {self.pattern_name.text().strip()}")
        except Exception as exc:
            QMessageBox.warning(self, "Assign Pattern Macro", str(exc))

    def _play_pattern_macro(self, key):
        name = self.controller.pattern_for_macro(key)
        if name:
            self._play_pattern(name)
        else:
            self._dispatch(self.controller.nudge_macro(key, 0.05, timestamp=0.0))
            self._sync_from_controller()

    def _play_pattern(self, name):
        pattern = self.controller.pattern_bank.get(str(name))
        if not pattern:
            self.status.setText(f"NO PATTERN: {name}")
            return
        events = sorted(pattern.get("events", []), key=lambda e: float(e.get("timestamp", 0.0)))
        self.host._jam_pattern_replaying = True
        if getattr(self, "_pattern_end_timer", None) is not None:
            self._pattern_end_timer.stop()
        for timer in self._pattern_timers:
            try: timer.stop()
            except Exception: pass
        self._pattern_timers = []
        for ev in events:
            if ev.get("kind") != "jam_note":
                continue
            delay = max(0, int(round(float(ev.get("timestamp", 0.0)) * 1000)))
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda item=dict(ev): self._dispatch({"kind": "jam_note", **item, "pattern_replay": True}))
            timer.start(delay)
            self._pattern_timers.append(timer)
        duration_ms = max(0, int(round(float(pattern.get("duration", 0.0)) * 1000)))
        self._pattern_end_timer = QTimer(self)
        self._pattern_end_timer.setSingleShot(True)
        self._pattern_end_timer.timeout.connect(lambda: setattr(self.host, "_jam_pattern_replaying", False))
        self._pattern_end_timer.start(duration_ms + 25)
        self.status.setText(f"PLAYING {name} · {len(events)} entries · {float(pattern.get('duration', 0.0)):.2f}s")

    def _toggle_record(self):
        """Record real post-master audio to WAV plus the synchronized event log."""
        import os, time
        from live_jam import LiveJamAudioRecorder
        recording = self.btn_record.isChecked()
        if recording:
            try:
                base = self.host._exports_dir() if callable(getattr(self.host, "_exports_dir", None)) else os.path.join(os.getcwd(), "exports")
                os.makedirs(base, exist_ok=True)
                path = os.path.join(base, time.strftime("LiveJam_%Y%m%d_%H%M%S.wav"))
                sr = int(getattr(self.host, "play_sample_rate", 44100) or 44100)
                self.host._live_jam_audio_recorder = LiveJamAudioRecorder(path, sample_rate=sr, channels=1)
                self.host._live_jam_audio_record_path = path
                self.controller.begin_performance_recording()
                self.host._live_jam_recording = True
                self.status.setText("RECORDING AUDIO + PERFORMANCE")
                self.status.setStyleSheet("color:#ff6c9c;font-weight:900;")
                self.audio_info.setText("WAV capture armed · final master output · " + os.path.basename(path))
            except Exception as exc:
                self.btn_record.blockSignals(True); self.btn_record.setChecked(False); self.btn_record.blockSignals(False)
                self.status.setText(f"RECORD START FAILED: {exc}")
        else:
            self.host._live_jam_recording = False
            take = self.controller.finish_performance_recording()
            recorder = getattr(self.host, "_live_jam_audio_recorder", None)
            result = recorder.finish() if recorder is not None else {"error":"No audio recorder was active"}
            self.host._live_jam_audio_recorder = None
            self.host._live_jam_render_snapshot = self.controller.snapshot()
            self.host._live_jam_render_log = take.get("events", [])
            self.host._live_jam_render_snapshot["record_duration"] = float(take.get("duration", 0.0))
            self.status.setText("WAV SAVED" if not result.get("error") else "WAV ERROR")
            self.status.setStyleSheet("color:#65e8b5;font-weight:900;")
            self.audio_info.setText(f"Audio: {result.get('path', '')} · {result.get('duration', 0):.1f}s · dropped blocks {result.get('dropped_blocks', 0)}")

    def _refresh_audio_meter(self):
        try:
            import numpy as np
            chunk = getattr(self.host, "_last_scope_chunk", None)
            if chunk is None: return
            a = np.asarray(chunk, dtype=np.float32).reshape(-1)
            if not a.size: return
            rms = float(np.sqrt(np.mean(a * a))); peak = float(np.max(np.abs(a)))
            self.level_meter.setValue(int(max(0, min(1000, rms * 1000))))
            self.peak_meter.setValue(int(max(0, min(1000, peak * 1000))))
            self.audio_info.setText(f"MASTER OUT  ·  RMS {rms:.3f}  ·  PEAK {peak:.3f}  ·  {int(getattr(self.host, 'play_sample_rate', 44100) or 44100)} Hz")
        except Exception:
            pass

    def _save_for_render(self):
        """Store the current jam snapshot + event log on the host for post-record video."""
        try:
            take = self.controller.finish_performance_recording()
            recorder = getattr(self.host, "_live_jam_audio_recorder", None)
            if recorder is not None:
                recorder.finish(); self.host._live_jam_audio_recorder = None
            snap = self.controller.snapshot()
            log = take.get("events", self.controller.event_log())
            snap["record_duration"] = float(take.get("duration", 0.0))
            self.host._live_jam_render_snapshot = snap
            self.host._live_jam_render_log = log
            self.host._live_jam_recording = False
            self.btn_record.setChecked(False)
            self.status.setText(f"SAVED {len(log)} EVENTS")
            self.status.setStyleSheet("color:#65d7d0;font-weight:900;")
        except Exception as e:
            self.status.setText(f"SAVE FAILED: {e}")
