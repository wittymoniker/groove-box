from pathlib import Path
p=Path('/mnt/data/gfix3/videogame_engine.py')
s=p.read_text()
# template Qt imports
s=s.replace('from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF, QImage, QLinearGradient', 'from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF, QImage, QLinearGradient, QCursor')
# add sounddevice optional import in template
needle='    HAS_UI = True\nexcept Exception:\n    HAS_UI = False\n'
repl='    HAS_UI = True\nexcept Exception:\n    HAS_UI = False\ntry:\n    import sounddevice as sd\n    HAS_AUDIO = True\nexcept Exception:\n    sd = None\n    HAS_AUDIO = False\n'
s=s.replace(needle,repl,1)
# startup game state add pan/capture-related fields
needle='        self.camera_pitch_target = 0.0\n'
repl='        self.camera_pitch_target = 0.0\n        self.camera_pan_x = 0.0\n        self.camera_pan_y = 0.0\n        self.audio_enabled = True\n        self.audio_stream = None\n        self.audio_lock = threading.RLock()\n'
s=s.replace(needle,repl,1)
# stabilize cinematic camera: don't overwrite player camera for open world
old='        self._consume_inputs(dt)\n        self._update_cinematic_camera(dt, abs(sample))\n'
new='        self._consume_inputs(dt)\n        # Open-world gameplay owns the camera. Classification/mood may influence\n        # event probabilities, but never inject camera motion while the player is driving.\n        if str(self.id.get("topology") or "") not in ("open_world", "sandbox"):\n            self._update_cinematic_camera(dt, abs(sample))\n'
s=s.replace(old,new,1)
# fix aim smoothing faster but stable, and movement speed modest
s=s.replace('min(1.0, dt * 18.0)', 'min(1.0, dt * 12.0)', 2)
# add audio methods before tick
needle='    def tick(self, dt=1/30):\n'
insert='''    def start_audio(self):\n        if not HAS_AUDIO or self.audio_stream is not None:\n            return bool(self.audio_stream is not None)\n        try:\n            game=self\n            def callback(outdata, frames, time_info, status):\n                try:\n                    with game.audio_lock:\n                        vals=[game.music.step(1.0/22050.0) for _ in range(frames)]\n                        sfx=game.sfx.mix(frames)\n                    import numpy as np\n                    arr=np.asarray(vals, dtype=np.float32)+np.asarray(sfx, dtype=np.float32)\n                    arr=np.clip(arr*0.55, -1.0, 1.0)\n                    outdata[:,0]=arr\n                    if outdata.shape[1]>1: outdata[:,1]=arr\n                except Exception:\n                    outdata.fill(0)\n            self.audio_stream=sd.OutputStream(samplerate=22050, channels=2, dtype="float32", callback=callback, blocksize=256)\n            self.audio_stream.start()\n            return True\n        except Exception:\n            self.audio_stream=None\n            self.audio_enabled=False\n            return False\n\n    def stop_audio(self):\n        st=self.audio_stream\n        self.audio_stream=None\n        if st is not None:\n            try: st.stop()\n            except Exception: pass\n            try: st.close()\n            except Exception: pass\n\n'''
s=s.replace(needle,insert+needle,1)
# Qt SceneViewport init add capture state
needle='            self._held_movement = set()\n            self.setMouseTracking(True)\n'
repl='            self._held_movement = set()\n            self._mouse_captured = False\n            self._pan_drag = False\n            self._pan_last = None\n            self.setMouseTracking(True)\n'
s=s.replace(needle,repl,1)
# replace mouse methods block
start=s.index('        def mousePressEvent(self, e):', s.index('class SceneViewport'))
end=s.index('        def wheelEvent(self, e):', start)
block='''        def _set_mouse_capture(self, enabled):\n            self._mouse_captured = bool(enabled)\n            if self._mouse_captured:\n                self.setCursor(Qt.CursorShape.BlankCursor)\n                self.setMouseTracking(True)\n                center=self.mapToGlobal(self.rect().center())\n                QCursor.setPos(center)\n                self._last_mouse=self.rect().center()\n            else:\n                self.unsetCursor()\n                self._last_mouse=None\n\n        def mousePressEvent(self, e):\n            g=self.game\n            self.setFocus(Qt.FocusReason.MouseFocusReason)\n            if e.button()==Qt.MouseButton.RightButton:\n                self._set_mouse_capture(not self._mouse_captured)\n                g.push_status("MOUSE LOOK: captured" if self._mouse_captured else "MOUSE LOOK: released")\n                e.accept(); return\n            if e.button()==Qt.MouseButton.MiddleButton:\n                self._pan_drag=True; self._pan_last=e.position(); e.accept(); return\n            if e.button()==Qt.MouseButton.LeftButton:\n                g.activate(); g.sfx.trigger("click",0.5); self.update()\n                if not self._mouse_captured: self._set_mouse_capture(True)\n                e.accept(); return\n            super().mousePressEvent(e)\n\n        def mouseMoveEvent(self, e):\n            g=self.game; now=e.position()\n            if self._pan_drag and self._pan_last is not None:\n                dx=float(now.x()-self._pan_last.x()); dy=float(now.y()-self._pan_last.y())\n                g.camera_pan_x=max(-0.8,min(0.8,float(getattr(g,'camera_pan_x',0.0))+dx/max(1.0,self.width())*1.6))\n                g.camera_pan_y=max(-0.6,min(0.6,float(getattr(g,'camera_pan_y',0.0))+dy/max(1.0,self.height())*1.2))\n                self._pan_last=now; self.update(); e.accept(); return\n            if self._mouse_captured:\n                dx=float(now.x()-self._last_mouse.x()) if self._last_mouse is not None else 0.0\n                dy=float(now.y()-self._last_mouse.y()) if self._last_mouse is not None else 0.0\n                if abs(dx)+abs(dy)>0.0:\n                    g.aim_at(dyaw=dx*0.0018, dpitch=dy*0.0012)\n                    QCursor.setPos(self.mapToGlobal(self.rect().center()))\n                    self._last_mouse=self.rect().center()\n            else:\n                self._last_mouse=now\n            self.update(); super().mouseMoveEvent(e)\n\n        def mouseReleaseEvent(self,e):\n            if e.button()==Qt.MouseButton.MiddleButton:\n                self._pan_drag=False; self._pan_last=None; e.accept(); return\n            super().mouseReleaseEvent(e)\n\n'''
s=s[:start]+block+s[end:]
# projection apply camera pan
needle='                x = cx + (x2 * inv / max(f,0.05)) * R * 0.72\n                y = cy - (y2 * inv / max(f,0.05)) * R * 0.72\n'
repl='                x = cx + (x2 * inv / max(f,0.05)) * R * 0.72 + float(getattr(g,"camera_pan_x",0.0))*R\n                y = cy - (y2 * inv / max(f,0.05)) * R * 0.72 + float(getattr(g,"camera_pan_y",0.0))*R\n'
s=s.replace(needle,repl,1)
# texture generator: remove opaque rect and make irregular faceted fill
old='''            base = QColor.fromHsv(hue, 115 + int(90*self._rng(key+":s")), 95 + int(125*self._rng(key+":v")), 135)\n            pp.setBrush(base); pp.setPen(Qt.PenStyle.NoPen)\n            pp.drawRect(0, 0, int(w), int(h))\n            # Multi-scale GOAVA/fractal facets.\n'''
new='''            base = QColor.fromHsv(hue, 115 + int(90*self._rng(key+":s")), 95 + int(125*self._rng(key+":v")), 88)\n            pp.setPen(Qt.PenStyle.NoPen)\n            # Irregular material tile, never an opaque rectangle.\n            basepts=[]\n            for k in range(9):\n                aa=k*math.tau/9.0; rr=0.72+0.25*self._rng(f"{key}:base:{k}")\n                basepts.append(QPointF(w*.5+math.cos(aa)*w*.62*rr,h*.5+math.sin(aa)*h*.62*rr))\n            pp.setBrush(base); pp.drawPolygon(QPolygonF(basepts))\n            # Multi-scale GOAVA/fractal facets.\n'''
s=s.replace(old,new,1)
# UI controls label
needle='            self.fn_lbl = QLabel("Fn: —")\n'
repl='            self.fn_lbl = QLabel("Fn: —")\n            self.controls_lbl = QLabel("Controls: WASD move · mouse look · LMB interact · RMB capture/release · MMB pan · wheel zoom")\n            self.controls_lbl.setWordWrap(True)\n            self.audio_lbl = QLabel("Audio: initializing…")\n'
s=s.replace(needle,repl,1)
needle='                        self.quest_lbl, self.tags_lbl, self.kind_lbl, self.fn_lbl):\n'
repl='                        self.quest_lbl, self.tags_lbl, self.kind_lbl, self.fn_lbl, self.controls_lbl, self.audio_lbl):\n'
s=s.replace(needle,repl,1)
# GameWindow start audio and close
needle='            self.timer.start()\n            self._last = time.monotonic()\n'
repl='            self.timer.start()\n            self._last = time.monotonic()\n            audio_ok = bool(getattr(game, "start_audio", lambda: False)())\n            try: self.panel.audio_lbl.setText("Audio: LIVE" if audio_ok else "Audio: unavailable (install sounddevice/PortAudio)")\n            except Exception: pass\n'
s=s.replace(needle,repl,1)
# Add closeEvent before run_splash
needle='        def run_splash(self):\n'
repl='''        def closeEvent(self, event):\n            try: self.timer.stop()\n            except Exception: pass\n            try: self.game.stop_audio()\n            except Exception: pass\n            super().closeEvent(event)\n\n        def run_splash(self):\n'''
s=s.replace(needle,repl,1)
p.write_text(s)
