"""SEQUENCE_PERFORM_R31: six live tools under the green/purple transport (sequence select / This Sequence).

  ⏮ ⏭  sequence stepper (optional auto-play)      🔁  loop This Sequence
  🎼  cue chain of selected sequence entries        👆  tap tempo
  ⏺  live take: key-chart notes write steps          📸  state slots A/B/C (store / recall / queue export)

Everything is event driven on the UI thread with QTimers: no waits, no nested event
loops. Note audio still goes through the normal key path (audio lane).
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QMenu, QToolButton, QComboBox

_STYLE = ("QPushButton, QToolButton { background:#101a14; color:#b9ffcf; border:1px solid #3fae6a; border-radius:5px;"
          " padding:3px 8px; font-weight:800; }"
          " QPushButton:checked { background:#3fae6a; color:#06140b; }"
          " QPushButton#slot, QToolButton#slot { background:#160f22; color:#e0c8ff; border-color:#9b6cff; }"
          " QPushButton#slot:checked { background:#9b6cff; color:#0d0716; }"
          " QPushButton#rec:checked { background:#d0304a; color:#fff; border-color:#ff8090; }"
          " QLabel { color:#9fd4ff; }")


class SequencePerformRow(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setStyleSheet(_STYLE)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 2, 0, 2); lay.setSpacing(4)

        # 1. stepper
        self.b_prev = self._btn("⏮", "Previous sequence of this instrument")
        self.b_next = self._btn("⏭", "Next sequence of this instrument")
        self.b_auto = self._btn("▶auto", "Auto-play the sequence you step to", checkable=True)
        self.b_prev.clicked.connect(lambda: self.step_sequence(-1))
        self.b_next.clicked.connect(lambda: self.step_sequence(+1))
        # 2. loop
        self.b_loop = self._btn("🔁 Loop", "Loop This Sequence until Stop", checkable=True)
        self.b_loop.toggled.connect(self._loop_toggled)
        # 3. cue chain
        self.cue = []
        self.b_cue = QToolButton(); self.b_cue.setText("🎼 Cue 0 ▾")
        self.b_cue.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.b_cue.setToolTip("Click: add the selected instrument + sequence to the cue. Menu: play / clear the cue.")
        self.b_cue.clicked.connect(self.cue_add)
        m = QMenu(self.b_cue)
        m.addAction("▶ Play cue in order", self.cue_play)
        m.addAction("Remove last", self.cue_pop)
        m.addAction("Clear cue", self.cue_clear)
        self.b_cue.setMenu(m)
        # 4. tap tempo
        self.b_tap = self._btn("👆 Tap", "Tap 3+ times to set the BPM")
        self.b_tap.clicked.connect(self.tap)
        self._taps = []
        # 5. live take
        self.b_rec = self._btn("⏺ Take", "Arm: notes you play on the key chart are written into the selected "
                               "sequence at the step under the running clock (undoable)", checkable=True)
        self.b_rec.setObjectName("rec")
        self.b_rec.toggled.connect(self._rec_toggled)
        # R32.6 recording styles
        self.rec_style = QComboBox()
        self.rec_style.addItems(["Overdub", "Replace", "Punch (steps In–Out)", "Step record", "Loop layers",
                                 "Automation · write", "Automation · latch", "Automation · touch"])
        self.rec_style.setToolTip(
            "Overdub: notes add to the sequence · Replace: the sequence is cleared when the take starts · "
            "Punch: only steps between the In/Out markers are written · Step record: every note writes the next "
            "step (no clock) · Loop layers: each pass of the bar writes into the next sequence slot · "
            "Automation write/latch/touch: note timing writes the amplitude lane (write = every step of the "
            "pass, latch = from the first note until stop, touch = only the steps you play)")
        self.rec_quant = QComboBox(); self.rec_quant.addItems(["grid 100 %", "grid 50 %", "free"])
        self.rec_quant.setToolTip("How strongly a note snaps to its step (free keeps the micro-offset in 'offsets')")
        self.punch_in = 1; self.punch_out = 16
        # 6. state slots
        self.slots = {}
        self.slot_btns = {}
        for name in ("A", "B", "C"):
            b = QToolButton(); b.setObjectName("slot"); b.setText("📸" + name)
            b.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            b.setToolTip("Click: recall state %s (empty: store). Menu: store / export / clear." % name)
            b.clicked.connect(lambda _c=False, n=name: self.slot_click(n))
            sm = QMenu(b)
            sm.addAction("Store current state in %s" % name, lambda n=name: self.slot_store(n))
            sm.addAction("⬇ Queue WAV export of %s" % name, lambda n=name: self.slot_export(n))
            sm.addAction("Clear %s" % name, lambda n=name: self.slot_clear(n))
            b.setMenu(sm)
            self.slot_btns[name] = b
        self.status = QLabel("")
        for w in (self.b_prev, self.b_next, self.b_auto, self.b_loop, self.b_cue, self.b_tap, self.b_rec, self.rec_style, self.rec_quant,
                  *self.slot_btns.values(), self.status):
            lay.addWidget(w)
        lay.addStretch(1)

        self._watch = QTimer(self); self._watch.setInterval(200); self._watch.timeout.connect(self._poll)
        self._was_playing = False
        self._cue_pos = -1
        self._take_t0 = 0.0
        self._hook_stop()

    def _btn(self, text, tip, checkable=False):
        b = QPushButton(text); b.setToolTip(tip); b.setCheckable(checkable)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return b

    def _say(self, text):
        self.status.setText(text)

    # -- stop button means "really stop": cancels loop and cue ------------------------
    def _hook_stop(self):
        b = getattr(self.app, "btn_stop", None)
        if b is not None:
            b.clicked.connect(self._user_stop)

    def _user_stop(self):
        self._cue_pos = -1
        if self.b_loop.isChecked():
            self.b_loop.setChecked(False)
        self._watch.stop()

    # 1 -----------------------------------------------------------------------
    def step_sequence(self, delta):
        sel = getattr(self.app, "sequence_selector", None)
        if sel is None or sel.count() == 0:
            return
        sel.setCurrentIndex((sel.currentIndex() + delta) % sel.count())
        self._say("Sequence %s" % sel.currentText())
        if self.b_auto.isChecked():
            self.app.play_selected_sequence(); self._arm_watch()

    # 2 -----------------------------------------------------------------------
    def _loop_toggled(self, on):
        if on:
            if not getattr(self.app, "is_playing", False):
                self.app.play_selected_sequence()
            self._arm_watch()
            self._say("Looping %s" % self._current_label())

    # 3 -----------------------------------------------------------------------
    def _current_label(self):
        try:
            return "%s · %s" % (self.app.instrument_selector_dropdown.currentText(), self.app.sequence_selector.currentText())
        except Exception:
            return "?"

    def _cue_text(self):
        self.b_cue.setText("🎼 Cue %d ▾" % len(self.cue))

    def cue_add(self):
        try:
            inst = self.app.instrument_selector_dropdown.currentText()
            sid = int(self.app.sequence_selector.currentData() or 1)
        except Exception:
            return
        self.cue.append((inst, sid)); self._cue_text()
        self._say("Cued %s" % self._current_label())

    def cue_pop(self):
        if self.cue:
            self.cue.pop(); self._cue_text()

    def cue_clear(self):
        self.cue.clear(); self._cue_pos = -1; self._cue_text()

    def cue_play(self):
        if not self.cue:
            self._say("Cue is empty: click 🎼 to add the selected sequence"); return
        self._cue_pos = 0
        self._play_cue_entry()

    def _play_cue_entry(self):
        inst, sid = self.cue[self._cue_pos]
        try:
            dd = self.app.instrument_selector_dropdown
            i = dd.findText(inst)
            if i >= 0:
                dd.setCurrentIndex(i)
            sel = self.app.sequence_selector
            j = sel.findData(sid)
            if j >= 0:
                sel.setCurrentIndex(j)
        except Exception:
            pass
        self._say("Cue %d/%d · %s" % (self._cue_pos + 1, len(self.cue), self._current_label()))
        self.app.play_selected_sequence()
        self._arm_watch()

    # loop + cue share one poller: when playback ends on its own, play the next thing.
    def _arm_watch(self):
        self._was_playing = True
        self._watch.start()

    def _poll(self):
        playing = bool(getattr(self.app, "is_playing", False)) or bool(getattr(self.app, "_play_begin_busy", False))
        if playing:
            self._was_playing = True
            return
        if not self._was_playing:
            return
        self._was_playing = False
        if self._cue_pos >= 0:
            self._cue_pos += 1
            if self._cue_pos < len(self.cue):
                self._play_cue_entry(); return
            if self.b_loop.isChecked() and self.cue:
                self._cue_pos = 0; self._play_cue_entry(); return
            self._cue_pos = -1
            self._say("Cue finished")
        elif self.b_loop.isChecked():
            self.app.play_selected_sequence(); self._was_playing = True; return
        self._watch.stop()

    # 4 -----------------------------------------------------------------------
    def tap(self):
        now = time.monotonic()
        self._taps = [t for t in self._taps if now - t < 3.0] + [now]
        if len(self._taps) >= 3:
            gaps = [b - a for a, b in zip(self._taps, self._taps[1:])]
            bpm = max(20.0, min(400.0, 60.0 / (sum(gaps) / len(gaps))))
            spin = getattr(self.app, "spin_bpm", None)
            if spin is not None:
                spin.setValue(round(bpm, 1))
            self._say("Tempo %.1f BPM" % bpm)
        else:
            self._say("Tap %d…" % len(self._taps))

    # 5 -----------------------------------------------------------------------
    def _rec_toggled(self, on):
        if on:
            try:
                self.app._push_undo("Live take")
            except Exception:
                pass
            self._take_t0 = time.monotonic()
            self._step_cursor = 0
            self._latched = False
            self._layer_pass = -1
            style = self.rec_style.currentText()
            try:
                mem = self.app._current_sequence_mem()
                n = max(1, int(mem.get("pattern_length") or len(mem.get("steps") or []) or 16))
                self.app._ensure_seq_mem_length(mem, n)
                if style.startswith("Replace"):
                    mem["steps"] = [False] * n
                if style.startswith("Punch"):
                    sel = getattr(self.app, "_pad_selection", None) or []
                    if sel:
                        self.punch_in, self.punch_out = min(sel) + 1, max(sel) + 1
                    else:
                        self.punch_in, self.punch_out = 1, max(1, n // 2)
                if style == "Automation · write":
                    mem["amplitudes"] = [0.0] * n
            except Exception:
                pass
            self.app._live_take = self
            self._say("Take armed: play key-chart notes")
        else:
            self.app._live_take = None
            try:
                name = self.app._current_instrument_name()
                self.app._canonical_write_sequence_runtime(name, self.app._current_sequence_index(name))
            except Exception:
                pass
            self._say("Take stored")

    def record_note(self, degree):
        """Called on the UI thread from _keychart_trigger while armed."""
        try:
            app = self.app
            mem = app._current_sequence_mem()
            n = max(1, int(mem.get("pattern_length") or len(mem.get("steps") or []) or 16))
            app._ensure_seq_mem_length(mem, n)
            bpm = float(app.spin_bpm.value()) if hasattr(app, "spin_bpm") else 120.0
            step_dur = (60.0 / max(1.0, bpm)) * 4.0 / n            # one sequence = one 4-beat bar
            style = self.rec_style.currentText()
            pos = (time.monotonic() - self._take_t0) / step_dur
            if style.startswith("Step record"):
                step = self._step_cursor % n
                self._step_cursor += 1
            else:
                q = self.rec_quant.currentIndex()
                step = (int(round(pos)) if q == 0 else (int(pos + 0.25) if q == 1 else int(pos))) % n
                if q == 2:
                    try:
                        mem.setdefault("offsets", [0.0] * n)
                        app._ensure_seq_mem_length(mem, n)
                        mem["offsets"][step] = float(pos - int(pos))
                    except Exception:
                        pass
            if style.startswith("Punch") and not (self.punch_in - 1 <= step <= self.punch_out - 1):
                self._say("Take · step %d outside punch %d–%d" % (step + 1, self.punch_in, self.punch_out)); return
            if style.startswith("Loop layers"):
                bar = int(pos // n)
                if bar != self._layer_pass and bar > 0:
                    self._layer_pass = bar
                    try:
                        self.step_sequence(+1)
                        mem = app._current_sequence_mem(); app._ensure_seq_mem_length(mem, n)
                    except Exception:
                        pass
            if style.startswith("Automation"):
                vel = max(0.05, 1.0 - abs(pos - round(pos)) * 1.6)     # on-beat = louder
                try:
                    amps = mem.setdefault("amplitudes", [1.0] * n)
                    app._ensure_seq_mem_length(mem, n)
                    if style == "Automation · latch":
                        self._latched = True
                        for k in range(step, n):
                            mem["amplitudes"][k] = vel
                    else:
                        mem["amplitudes"][step] = vel
                except Exception:
                    pass
                if hasattr(app, "_refresh_pad_playhead"):
                    app._refresh_pad_playhead()
                self._say("Automation · step %d ← %.2f" % (step + 1, vel)); return
            mem["steps"][step] = True
            try:
                mem["pitches"][step] = float(app._keychart_ratio(degree))
            except Exception:
                pass
            if hasattr(app, "_refresh_pad_playhead"):
                app._refresh_pad_playhead()
            self._say("Take · step %d ← degree %d" % (step + 1, degree))
        except Exception as exc:
            self._say("Take error: %s" % exc)

    # 6 -----------------------------------------------------------------------
    def slot_click(self, name):
        if name in self.slots:
            self.slot_recall(name)
        else:
            self.slot_store(name)

    def slot_store(self, name):
        try:
            self.slots[name] = self.app._project_snapshot()
        except Exception as exc:
            self._say("Store failed: %s" % exc); return
        self.slot_btns[name].setText("📸%s●" % name)
        self._say("State %s stored" % name)

    def slot_recall(self, name):
        doc = self.slots.get(name)
        if doc is None:
            return
        try:
            self.app._push_undo("Recall state %s" % name)
        except Exception:
            pass
        try:
            self.app._apply_project_snapshot(doc)
            self.app.reload_active_instrument_sequencer_ui()
        except Exception as exc:
            self._say("Recall failed: %s" % exc); return
        self._say("State %s recalled (Undo restores the previous one)" % name)

    def slot_clear(self, name):
        self.slots.pop(name, None)
        self.slot_btns[name].setText("📸" + name)

    def slot_export(self, name):
        doc = self.slots.get(name)
        if doc is None:
            self._say("Slot %s is empty" % name); return
        app = self.app
        try:
            path = app._export_name("state %s" % name, ".wav", app._audio_exports_dir())
            job = app._export_scheduler().submit_audio(path, {
                "audio_format": "wav", "render_sample_rate": 48000, "output_sample_rate": 48000, "bit_depth": 24,
                "n_parts": 1, "stitch_parts": True,
                "clip_ratio_pct": float(app.spin_clip_ratio.value()) if hasattr(app, "spin_clip_ratio") else 50.0,
                "master_volume": float(getattr(app, "master_volume", 0.72)),
            }, label="State %s · WAV" % name, project_doc=doc)
            app.show_export_jobs()
            self._say("State %s queued as export #%d" % (name, job.id))
        except Exception as exc:
            self._say("Export failed: %s" % exc)
