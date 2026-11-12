"""quick_rack.py — GROOVEBOX_R32_QUICK_RACK_20261109

The R32 interactive strip for the main window's green / purple top panel.  Eight live
controls, each a real feature in one widget:

    1. Canonical mode        🛡 / ⚖ / 🎯  (canonical_mode)
    2. Divergence            per-instrument seed decorrelation 0..1 (seed_divergence)
    3. Seed Dissect          evaluates the seed program now and shows every stage's value
    4. Post-Process          opens the finishing window (postprocess_window)
    5. Blueprint             Project Blueprint (project_blueprint)
    6. Playability           game feel (game_playability)
    7. Arrange ⊞             window manager menu (tile / cascade / snap / cycle)
    8. Both outputs 🔊       HDMI + speakers status / re-install (audio_both_output)
plus a RESOURCES readout (RSS, child processes, backends) refreshed off the GUI thread.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer, QThreadPool, QRunnable, QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QDoubleSpinBox, QMenu, QFrame, QTextEdit, QVBoxLayout

GREEN, PURPLE = "#2ecc71", "#6c4bb3"


class _Stats(QObject):
    ready = pyqtSignal(str)


class _StatsJob(QRunnable):
    def __init__(self, sig):
        super().__init__(); self.sig = sig; self.setAutoDelete(True)

    def run(self):
        parts = []
        try:
            import resource_governor as rg
            parts.append("RSS %d MB" % int(rg.rss_mb()))
        except Exception:
            pass
        try:
            import process_policy as pp
            st = pp.status()
            parts.append("%d child proc" % st["live"])
            av = [b for b, ok in pp.Backends.report()["available"].items() if ok]
            parts.append("backends " + "+".join(av))
        except Exception:
            pass
        try:
            import seed_lang
            cs = seed_lang.cache_stats()
            parts.append("seed cache %d (%d hits)" % (cs["size"], cs["hits"]))
        except Exception:
            pass
        self.sig.ready.emit(" · ".join(parts))


class QuickRack(QFrame):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setObjectName("R32QuickRack")
        self._css = ("#R32QuickRack{background:rgba(20,30,40,140);border:1px solid %s;border-bottom:2px solid %s;border-radius:6px;}"
                     "QPushButton{padding:3px 8px;font-weight:700;border-radius:5px;}"
                     "QPushButton:hover{background:rgba(46,204,113,70);border:1px solid #2ecc71;}"     # R32.8 hover glow
                     "QPushButton:pressed{background:rgba(108,75,179,150);}")
        self.setStyleSheet(self._css % (GREEN, PURPLE))
        lay = QHBoxLayout(self); lay.setContentsMargins(6, 3, 6, 3); lay.setSpacing(6)
        self._lay = lay
        self.setMinimumHeight(40)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._dock_menu)
        # 1 canonical mode
        try:
            import canonical_mode
            canonical_mode.ensure_default(app)
            lay.addWidget(canonical_mode.make_combo(app, self))
        except Exception as exc:
            lay.addWidget(QLabel("canonical mode n/a: %s" % exc))
        # 2 divergence
        lay.addWidget(QLabel("Divergence"))
        sp = QDoubleSpinBox(); sp.setRange(0.0, 1.0); sp.setSingleStep(0.05); sp.setDecimals(2)
        sp.setValue(float(getattr(app, "seed_divergence", 0.6) or 0.6)); sp.setKeyboardTracking(False)
        sp.setToolTip("How strongly instruments, visuals and games receive *different* numbers from the same seed program. 0 = old behaviour (everything shares one value).")
        sp.valueChanged.connect(self._div_changed)
        app.spin_seed_divergence = sp
        lay.addWidget(sp)
        # 3..8 buttons
        for cap, tip, fn in (("🔬 Dissect", "Evaluate the seed program now and list every variable's value", self.dissect),
                             ("🧰 Post", "Post-Process window: offline hardcoded-FX finishing, batch, loudness compare", self.post),
                             ("📐 Blueprint", "Master project configuration from a few precise inputs + project macros", self.blueprint),
                             ("🎮 Play", "Game playability: speed, gravity, controls, assist, lives", self.play),
                             ("📂 Files", "File Studio: projects · MCC editor · samples · exports · seeds · presets · recordings · versions", self.files),
                             ("🌐 Network", "Network Hub: your site · sharing toggles · peers · chat · co-edit · relay · port forward · links", lambda: __import__("network_hub").open_window(self.app)),
                             ("🔌 Hardware", "MIDI (USB, learn, clock) · audio devices · input devices & tester · printers · USB / drives / cameras", lambda: __import__("hardware_tools").open_window(self.app)),
                             ("🗺 Context", "Context Map of every local / global context + ownership matrix", lambda: __import__("context_visualizer").open_window(self.app)),
                             ("🧊 OBJ", "Project ⇄ OBJ: export the song as a 3D model with the exact audio and project inside; import any OBJ as sound; show an OBJ in the video", lambda: __import__("project_obj").open_window(self.app)),
                             ("🧊 3D Studio", "Wrap media onto OBJs, tint, build scenes of models + video + audio, mesh into a game, make 3D video", lambda: __import__("studio_3d").open_window(self.app)),
                             ("🎯 Canonical", "Canonical values: what the engines change at render time (shown value vs the value the render uses)", lambda: __import__("canonical_view").open_window(self.app)),
                             ("🗂 Playlist", "Graphical playlist: lanes, overlap, coverage, blend partners, all columns", lambda: __import__("playlist_view").open_window(self.app)),
                             ("📈 Automate", "Automation lanes for every module parameter (canonical = the seed program)", lambda: __import__("automation_bus").open_window(self.app)),
                             ("🎚 Mixer", "Instrument Mixer: per-instrument gain · mute · solo · canonical balance", lambda: __import__("instrument_mixer").open_window(self.app)),
                             ("🔁 Transmute", "Sound · image · video · game ⇄ each other · reverse-engineer → project", lambda: __import__("media_transmuter").open_window(self.app)),
                             ("🎚 Layer sweep", "Layer an export with another or a random one; use one file as the remix recipe of another", lambda: __import__("media_layers").open_window(self.app)),
                             ("🌲 Process tree", "Who runs where: audio, UI, record, export, sCode", lambda: __import__("process_tree").open_window(self.app)),
                             ("🌊 Wave", "Wave syncer · folder · resampler", lambda: __import__("canonical_wavetools").open_window(self.app)),
                             ("🖌 Image", "Image editor: layers · draw · opacity · gradients", lambda: __import__("image_editor").open_window(self.app)),
                             ("🧬 Compose", "Seed Morph · Song Form · Tuning Lattice · Diversity Meter · Playback styles", lambda: __import__("composition_tools").open_window(self.app)),
                             ("🐢 Stalls", "What froze the windows this session (function, total ms)", lambda: __import__("ui_stall_watch").open_window(self.app)),
                             ("👤 Userdata", "List / revert every field recorded as your data", lambda: __import__("userdata_tool").open_window(self.app)),
                             ("⌨", "On-screen keyboard (touch / no-keyboard). Ctrl+K: command palette of every button", lambda: (__import__("accessibility").keyboard(self.app).show())),
                             ("⌘", "Command palette: type to find any button or menu action, Enter to run (Ctrl+K)", lambda: __import__("accessibility").command_palette(self.app)),
                             ("🧭 Flow", "Flow labels: plain-language flags on every visible panel (what it controls, where it routes) "
                              "+ the per-sequence wires and blue global glows when those modes are on", self.flow),
                             ("⏱ Tap", "Tap tempo: tap 2+ times in rhythm; the BPM follows the average of the last taps", self.tap),
                             ("⏹ Panic", "Stop everything that sounds: transport, external players, make-up audio", self.panic),
                             ("⊞ Arrange", "Tile / cascade / snap / cycle every Groovebox window", self.arrange),
                             ("🔊 Both", "HDMI and speakers together: status and re-install the combined device", self.both),
                             ("📝 Notes", "Session scratch pad, saved with the project", lambda: __import__("session_notes").open_window(self.app)),
                             ("📊 Meter", "Live CPU and memory", lambda: __import__("perf_meter").open_window(self.app)),
                             ("⌨ Keys", "The shortcuts that matter", lambda: __import__("shortcut_card").open_window(self.app)),
                             ("🔖 Marks", "Save and recall a composition snapshot", lambda: __import__("state_bookmark").open_window(self.app)),
                             ("📦 Jobs", "Plain view of every export job", lambda: __import__("export_dashboard").open_window(self.app)),
                             ("🎨 Theme", "Flip the color scheme", lambda: __import__("theme_switch").open_window(self.app)),
                             ("💾 Backup", "Copy the project folder to a dated backup", lambda: __import__("backup_tool").open_window(self.app)),
                             ("🔗 Paths", "What the tools have written, with the seed fingerprint", lambda: __import__("pathway_view").open_window(self.app))):
            b = QPushButton(cap); b.setToolTip(tip); b.clicked.connect(fn); lay.addWidget(b)
        lay.addStretch(1)
        self.lbl = QLabel("…"); self.lbl.setStyleSheet("color:#b8f7e6;font-size:8pt;")
        lay.addWidget(self.lbl)
        self._sig = _Stats(self); self._sig.ready.connect(self.lbl.setText)
        self._timer = QTimer(self); self._timer.setInterval(4000); self._timer.timeout.connect(self._refresh)
        self._timer.start(); QTimer.singleShot(500, self._refresh)
        # R32.8: the rack's lower edge pulses with the beat while playing (cheap: 8 Hz, only when visible + playing)
        self._pulse = QTimer(self); self._pulse.setInterval(125); self._pulse.timeout.connect(self._beat_pulse); self._pulse.start()
        self._pulse_on = False

    def _beat_pulse(self):
        app = self.app
        playing = bool(getattr(app, "is_playing", False)) and self.isVisible()
        if not playing:
            if self._pulse_on:
                self._pulse_on = False; self.setStyleSheet(self._css % (GREEN, PURPLE))
            return
        try:
            sr = float(getattr(app, "play_sample_rate", 48000) or 48000)
            beat = float(getattr(app, "play_cursor", 0) or 0) / sr * float(app.spin_bpm.value()) / 60.0
        except Exception:
            return
        on = (beat % 1.0) < 0.18
        if on != self._pulse_on:
            self._pulse_on = on
            self.setStyleSheet(self._css % (GREEN, "#ffd166" if on else PURPLE))

    def hideEvent(self, ev):
        self._timer.stop(); super().hideEvent(ev)

    def showEvent(self, ev):
        self._timer.start(); super().showEvent(ev)

    def _refresh(self):
        try:
            __import__("r32_pool").start(_StatsJob(self._sig))
        except Exception:
            pass

    def _div_changed(self, v):
        self.app.seed_divergence = float(v)
        self.app._r32_divergence_user = True
        f = getattr(self.app, "_on_live_source_changed", None)
        if callable(f):
            try:
                f()
            except Exception:
                pass

    # -- actions -------------------------------------------------------------
    def dissect(self):
        app = self.app
        try:
            import seed_lang
            gb = __import__("groovebox")
            raw = app._seed_text()
            try:
                ctx = app._canonical_input_context()
            except Exception:
                ctx = None
            env = gb._seed_script_env(t_scalar=0.0, canonical_context=ctx if isinstance(ctx, dict) else None)
            ev = seed_lang.evaluate(raw, env)
            lines = ["seed program · %d lines · result from: %s" % (len(raw.split("\n")), ev.source)]
            if ev.error:
                lines.append("error: %s (line %d)" % (ev.error, ev.line))
            lines.append("values: " + ", ".join("%.6g" % v for v in ev.values[:16]) + (" …" if len(ev.values) > 16 else ""))
            lines.append("")
            for name, nums in ev.dissect():
                lines.append("%-18s %s" % (name, ", ".join("%.6g" % v for v in nums[:6])))
            for tt in (0.5, 1.25, 4.0):
                e2 = seed_lang.evaluate(raw, gb._seed_script_env(t_scalar=tt, canonical_context=ctx if isinstance(ctx, dict) else None))
                lines.append("t=%-5g → %s" % (tt, ", ".join("%.6g" % v for v in e2.values[:6])))
            self._show_text("🔬 Seed dissect", "\n".join(lines))
        except Exception as exc:
            self._show_text("🔬 Seed dissect", "failed: %s" % exc)

    def _show_text(self, title, text):
        win = getattr(self.app, "_dissect_window", None)
        try:
            if win is not None:
                win.isVisible()
        except RuntimeError:
            win = None
        if win is None:
            win = QWidget(self.app, Qt.WindowType.Window); win.setWindowTitle(title); win.resize(640, 480)
            lay = QVBoxLayout(win); ed = QTextEdit(); ed.setReadOnly(True)
            ed.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;"); lay.addWidget(ed); win._ed = ed
            self.app._dissect_window = win
        win._ed.setPlainText(text); win.show(); win.raise_()

    def files(self):
        import file_studio
        menu = QMenu(self)
        for tab in file_studio.TABS:
            menu.addAction(tab, lambda _t=tab: file_studio.open_window(self.app, _t))
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def post(self):
        import postprocess_window
        w = postprocess_window.open_window(self.app)
        post = getattr(self.app, "blueprint_post_settings", None)
        if isinstance(post, dict) and post:
            w.set_settings(post)

    def blueprint(self):
        import project_blueprint
        project_blueprint.open_window(self.app)

    def play(self):
        import game_playability
        game_playability.open_window(self.app)

    def flow(self):
        try:
            import perseq_vars as _psv
            ov = _psv.overlay(self.app); ov.flow = not ov.flow; ov._tick()
            self.lbl.setText("Flow labels " + ("on" if ov.flow else "off"))
        except Exception as exc:
            self.lbl.setText("flow n/a: %s" % exc)

    def tap(self):
        import time as _t
        now = _t.monotonic(); taps = [x for x in getattr(self, "_taps", []) if now - x < 3.0] + [now]
        self._taps = taps[-8:]
        if len(self._taps) >= 2:
            d = (self._taps[-1] - self._taps[0]) / (len(self._taps) - 1)
            if d > 0:
                bpm = max(20.0, min(400.0, 60.0 / d))
                try:
                    self.app.spin_bpm.setValue(round(bpm, 1)); self.lbl.setText("Tap tempo: %.1f BPM" % bpm)
                except Exception:
                    pass

    def panic(self):
        app = self.app; n = 0
        for fn in ("stop_playback", "stop_audio_playback"):
            try:
                getattr(app, fn)(); n += 1
            except Exception:
                pass
        try:
            import ext_windows
            for w in ext_windows.windows():
                w.close(); n += 1
        except Exception:
            pass
        try:
            from PyQt6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if hasattr(w, "_mk_gen") and getattr(w, "_mk_gen", None) is not None:
                    w._mk_gen.stop(); w._mk_gen = None; n += 1
                if hasattr(w, "player") and hasattr(w.player, "stop"):
                    w.player.stop()
        except Exception:
            pass
        try:
            import sounddevice as _sd
            _sd.stop()
        except Exception:
            pass
        self.lbl.setText("Panic: everything stopped (%d sources)" % n)

    def arrange(self):
        try:
            import window_manager
            m = window_manager.manager()
            menu = QMenu(self)
            m.build_arrange_menu(menu)
            menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
        except Exception as exc:
            self.lbl.setText("arrange n/a: %s" % exc)

    def both(self):
        try:
            import audio_both_output as abo

            def done(res):
                written, path, _t = res
                QTimer.singleShot(0, lambda: self.lbl.setText("Both outputs: %s%s · %s" % (
                    "installed" if written else "already set", (" at " + path) if path else " (no ALSA cards)",
                    " / ".join(l for _d, l in abo.choices()) or "no outputs")))
            abo.ensure_background(done)
        except Exception as exc:
            self.lbl.setText("both outputs n/a: %s" % exc)


    def _dock_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Horizontal", lambda: self.set_vertical(False))
        menu.addAction("Vertical", lambda: self.set_vertical(True))
        menu.exec(self.mapToGlobal(pos))

    def contextMenuEvent(self, event):
        self._dock_menu(event.pos())
        event.accept()

    def set_vertical(self, vertical):
        """Stack the buttons in a column when the bar is docked on a side."""
        from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout
        lay = getattr(self, "_lay", self.layout())
        if lay is None:
            return
        widgets = []
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                widgets.append(w)
        # Drop the old layout by reparenting widgets, then apply a new one.
        QWidget().setLayout(lay)
        self._lay = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        self._lay.setContentsMargins(6, 3, 6, 3)
        self._lay.setSpacing(6)
        for w in widgets:
            self._lay.addWidget(w)
        if vertical:
            self.setMinimumWidth(180)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
        else:
            self.setMinimumWidth(0)
            self.setMinimumHeight(40)
        self.updateGeometry()

def install(app, layout, index=0):
    """Insert the rack into a layout (top of the main window)."""
    rack = QuickRack(app, app)
    try:
        layout.insertWidget(index, rack)
    except Exception:
        layout.addWidget(rack)
    app.quick_rack = rack
    return rack
