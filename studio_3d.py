"""studio_3d.py — 3D Studio and stereoscopic video workflow.

GROOVEBOX_3D_STUDIO_R64_STEREO_VIDEO_PIPELINE
Load/texture/tint OBJ models, render mono or dual-camera stereo clips, and process
rendered 3D video assets (layout, frame rate, resolution and soundtrack).
"""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QDoubleSpinBox, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QComboBox, QCheckBox,
)


def _rgba_to_pixmap(rgba):
    h, w = rgba.shape[:2]
    img = QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(img.copy())


def _layout_code(combo: QComboBox) -> str:
    return str(combo.currentData() or "mono")


def _eye_size(combo: QComboBox) -> tuple[int, int]:
    value = str(combo.currentData() or "640x360")
    w, h = value.split("x", 1)
    return int(w), int(h)


def _submit_media_work(parent, status, label, work):
    """Run heavy rendering/encoding off the GUI thread; never fall back synchronously."""
    status.setText(label)
    try:
        from ui_runtime import submit_ui_task
        submit_ui_task(work, lambda result: status.setText(str(result)))
    except Exception as exc:
        QMessageBox.warning(parent, "Background media worker unavailable",
                            "The 3D media job was not run on the GUI thread.\n\n" + str(exc))
        status.setText("Media job not started: background worker unavailable")


def open_window(app):
    w = getattr(app, "_studio_3d_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); w.activateWindow(); return w
    except RuntimeError:
        w = None

    win = QWidget(app, Qt.WindowType.Window)
    win.setWindowTitle("🧊 3D Studio · scene · stereo video · processing")
    win.resize(1040, 820)
    root = QVBoxLayout(win)
    info = QLabel(
        "Create 3D video from OBJ geometry with independently rendered left/right camera views, "
        "or process an existing rendered 3D clip. Stereo layout changes preserve eye views; "
        "mono-to-stereo duplication is explicitly marked as 2D duplication, not depth creation."
    )
    info.setWordWrap(True); root.addWidget(info)
    preview = QLabel("No model loaded")
    preview.setMinimumHeight(250)
    preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview.setStyleSheet("background:#0d1118; color:#9ab; border:1px solid #345;")
    root.addWidget(preview, 1)

    state = {"mesh": None, "obj": "", "tex": "", "tint": (200, 220, 255),
             "scene": [], "audio": "", "process_input": "", "process_output": ""}

    row = QHBoxLayout()
    b_obj = QPushButton("Load OBJ")
    b_tex = QPushButton("Wrap image/video")
    b_song = QPushButton("Song as 3D")
    b_clear = QPushButton("Clear wrap")
    for b in (b_obj, b_tex, b_song, b_clear):
        row.addWidget(b)
    root.addLayout(row)

    tint_row = QHBoxLayout()
    tint_row.addWidget(QLabel("Tint R,G,B"))
    spins = []
    for val in (200, 220, 255):
        sp = QDoubleSpinBox(); sp.setRange(0, 255); sp.setDecimals(0); sp.setValue(val)
        spins.append(sp); tint_row.addWidget(sp)
    tint_row.addWidget(QLabel("Spin °/s"))
    spin = QDoubleSpinBox(); spin.setRange(-180, 180); spin.setValue(30); tint_row.addWidget(spin)
    tint_row.addWidget(QLabel("Scale"))
    scale = QDoubleSpinBox(); scale.setRange(0.1, 3.0); scale.setSingleStep(0.1); scale.setValue(0.8)
    tint_row.addWidget(scale)
    root.addLayout(tint_row)

    # Unified deterministic scene treatment: these values are consumed by the
    # same obj_scene.render_frame path used for preview and chunked video export.
    motion_row = QHBoxLayout()
    motion_controls = {}
    for label, key, lo, hi, value, step in (
        ("Opacity", "opacity", 0.0, 1.0, 1.0, 0.05),
        ("Fade in s", "fade_in", 0.0, 600.0, 0.0, 0.1),
        ("Fade out s", "fade_out", 0.0, 600.0, 0.0, 0.1),
        ("Distort", "distortion", 0.0, 1.0, 0.0, 0.05),
        ("Roll °", "roll_deg", -180.0, 180.0, 0.0, 2.0),
        ("Pan X", "pan_x", -1.0, 1.0, 0.0, 0.05),
        ("Pan Y", "pan_y", -1.0, 1.0, 0.0, 0.05),
        ("Zoom", "zoom", 0.05, 4.0, 1.0, 0.05),
    ):
        motion_row.addWidget(QLabel(label))
        sp = QDoubleSpinBox(); sp.setRange(lo, hi); sp.setDecimals(2); sp.setSingleStep(step); sp.setValue(value)
        motion_controls[key] = sp; motion_row.addWidget(sp)
    shadow_toggle = QCheckBox("Shadow"); motion_row.addWidget(shadow_toggle)
    root.addLayout(motion_row)

    scene_row = QHBoxLayout()
    scene_list = QListWidget(); scene_list.setMaximumHeight(100)
    scene_row.addWidget(scene_list, 1)
    col = QVBoxLayout()
    kind = QComboBox(); kind.addItems(["obj", "video", "audio"])
    path_edit = QLineEdit(); path_edit.setPlaceholderText("scene asset path")
    b_add = QPushButton("Add to scene")
    b_pick = QPushButton("Pick scene asset")
    b_mesh = QPushButton("Mesh into game")
    for widget in (kind, path_edit, b_pick, b_add, b_mesh):
        col.addWidget(widget)
    scene_row.addLayout(col)
    root.addLayout(scene_row)

    render_row = QHBoxLayout()
    render_row.addWidget(QLabel("Render layout"))
    render_layout = QComboBox()
    render_layout.addItem("Mono", "mono")
    render_layout.addItem("Stereo · side-by-side", "sbs")
    render_layout.addItem("Stereo · top-bottom", "tb")
    render_row.addWidget(render_layout)
    render_row.addWidget(QLabel("Per-eye size"))
    render_size = QComboBox()
    render_size.addItem("640 × 360", "640x360")
    render_size.addItem("960 × 540", "960x540")
    render_size.addItem("1280 × 720", "1280x720")
    render_row.addWidget(render_size)
    render_row.addWidget(QLabel("FPS"))
    render_fps = QComboBox()
    for value in (24, 30, 48, 60):
        render_fps.addItem(str(value), value)
    render_row.addWidget(render_fps)
    render_row.addWidget(QLabel("Duration s"))
    render_duration = QDoubleSpinBox(); render_duration.setRange(1.0, 600.0)
    render_duration.setValue(4.0); render_duration.setSingleStep(1.0)
    render_row.addWidget(render_duration)
    root.addLayout(render_row)

    audio_row = QHBoxLayout()
    audio_path = QLineEdit(); audio_path.setReadOnly(True)
    audio_path.setPlaceholderText("Optional soundtrack for the rendered 3D video")
    b_audio = QPushButton("Choose soundtrack…")
    b_clear_audio = QPushButton("Clear")
    audio_row.addWidget(audio_path, 1); audio_row.addWidget(b_audio); audio_row.addWidget(b_clear_audio)
    root.addLayout(audio_row)

    process_row = QHBoxLayout()
    process_input = QLineEdit(); process_input.setReadOnly(True)
    process_input.setPlaceholderText("Existing rendered 3D video to process")
    b_process_pick = QPushButton("Choose 3D video…")
    b_process = QPushButton("Process / convert")
    process_row.addWidget(process_input, 1); process_row.addWidget(b_process_pick); process_row.addWidget(b_process)
    root.addLayout(process_row)

    process_opts = QHBoxLayout()
    process_opts.addWidget(QLabel("Input layout"))
    process_source_layout = QComboBox()
    for title, code in (("Mono", "mono"), ("Side-by-side", "sbs"), ("Top-bottom", "tb")):
        process_source_layout.addItem(title, code)
    process_opts.addWidget(process_source_layout)
    process_opts.addWidget(QLabel("Output layout"))
    process_output_layout = QComboBox()
    for title, code in (("Mono", "mono"), ("Side-by-side", "sbs"), ("Top-bottom", "tb")):
        process_output_layout.addItem(title, code)
    process_opts.addWidget(process_output_layout)
    process_opts.addWidget(QLabel("Size"))
    process_size = QComboBox()
    process_size.addItem("1280 × 720", "1280x720")
    process_size.addItem("1920 × 1080", "1920x1080")
    process_size.addItem("2560 × 1440", "2560x1440")
    process_opts.addWidget(process_size)
    process_opts.addWidget(QLabel("FPS"))
    process_fps = QComboBox()
    for value in (24, 30, 48, 60):
        process_fps.addItem(str(value), value)
    process_opts.addWidget(process_fps)
    process_opts.addWidget(QLabel("Start s"))
    process_start = QDoubleSpinBox(); process_start.setRange(0.0, 86400.0); process_start.setDecimals(2); process_start.setValue(0.0)
    process_opts.addWidget(process_start)
    process_opts.addWidget(QLabel("End s · 0 = full"))
    process_end = QDoubleSpinBox(); process_end.setRange(0.0, 86400.0); process_end.setDecimals(2); process_end.setValue(0.0)
    process_opts.addWidget(process_end)
    process_opts.addWidget(QLabel("Audio"))
    process_audio = QComboBox()
    process_audio.addItem("Keep source", "keep")
    process_audio.addItem("Mute", "mute")
    process_audio.addItem("Replace with selected soundtrack", "replace")
    process_opts.addWidget(process_audio)
    root.addLayout(process_opts)

    status = QLabel("")
    status.setWordWrap(True); root.addWidget(status)

    def params():
        return {
            "color": tuple(int(s.value()) for s in spins),
            "spin_deg_s": float(spin.value()),
            "scale": float(scale.value()),
            "tilt_deg": 15.0,
            **{k: float(v.value()) for k, v in motion_controls.items()},
            "shadow": bool(shadow_toggle.isChecked()),
            "duration": float(render_duration.value()),
        }

    def paint(t=0.0):
        mesh = state["mesh"]
        if mesh is None:
            preview.setText("No model loaded")
            return
        try:
            import obj_scene
            tex = None
            if state["tex"] and Path(state["tex"]).suffix.lower() not in {
                ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"
            } and os.path.isfile(state["tex"]):
                tex = obj_scene.load_image_rgb(state["tex"])
            rgba = obj_scene.render_frame(mesh, 480, 270, t, params=params(), tex=tex)
            preview.setPixmap(_rgba_to_pixmap(rgba))
        except Exception as exc:
            preview.setText("preview: " + str(exc))

    def load_obj(path):
        import obj_scene
        state["mesh"] = obj_scene.load_obj(path)
        state["obj"] = path
        status.setText("loaded %s · %d tris" % (os.path.basename(path), len(state["mesh"]["t"])))
        paint(0.0)

    def on_obj():
        path, _ = QFileDialog.getOpenFileName(win, "OBJ model", "", "OBJ (*.obj)")
        if path:
            try: load_obj(path)
            except Exception as exc: QMessageBox.warning(win, "OBJ load failed", str(exc))

    def on_tex():
        path, _ = QFileDialog.getOpenFileName(
            win, "Wrap onto the model", "", "Media (*.png *.jpg *.jpeg *.mp4 *.mkv *.webm *.mov)"
        )
        if path:
            state["tex"] = path
            status.setText("wrap: " + os.path.basename(path))
            paint(0.0)

    def on_song():
        try:
            path = os.path.join(str(app._exports_dir()), "project-video.obj")
            if not os.path.isfile(path):
                status.setText("No song OBJ yet. Use Project ⇄ OBJ to export one, then open it here.")
                return
            load_obj(path)
        except Exception as exc:
            status.setText(str(exc))

    def on_clear():
        state["tex"] = ""
        paint(0.0)

    def on_pick():
        path, _ = QFileDialog.getOpenFileName(
            win, "Scene media", "", "Media (*.obj *.mp4 *.webm *.mov *.mkv *.wav *.flac *.mp3)"
        )
        if path:
            path_edit.setText(path)

    def on_add():
        path = path_edit.text().strip()
        if not path:
            return
        item = {"kind": kind.currentText(), "path": path, "tint": params()["color"]}
        state["scene"].append(item)
        scene_list.addItem(QListWidgetItem("%s · %s" % (item["kind"], os.path.basename(path))))
        if item["kind"] == "obj" and state["mesh"] is None and os.path.isfile(path):
            try: load_obj(path)
            except Exception as exc: status.setText("scene OBJ failed: " + str(exc))

    def on_video_objs():
        """🎥 Every OBJ of the scene (and the loaded model) goes into the music video: the first is the centrepiece,
        the others are placed by the scene (arrangement, keyframes, instrument binding, shots, lights, material)."""
        objs = [it["path"] for it in state["scene"] if it.get("kind") == "obj" and os.path.isfile(it.get("path", ""))]
        if state.get("obj") and state["obj"] not in objs:
            objs.insert(0, state["obj"])
        if not objs:
            status.setText("Add OBJ models to the scene first.")
            return
        app.video_obj_paths = objs[:13]
        app.video_obj_path = objs[0]
        import scene3d as _s3
        sc = _s3.scene(app)
        have = {str(it.get("path")): it for it in sc["items"]}
        sc["items"] = [have.get(p, {"path": p}) for p in objs[1:13]]
        app.video_obj_scene = sc
        status.setText("🎥 %d OBJ(s) in the video: %s" % (len(objs[:9]), ", ".join(os.path.basename(p) for p in objs[:9])))

    def on_mesh():
        if not state["scene"] and not state["obj"]:
            status.setText("Add an OBJ or media to the scene first.")
            return
        scene = {"title": "3D Studio scene", "obj": state["obj"], "wrap": state["tex"],
                 "tint": params()["color"], "items": list(state["scene"])}
        try:
            import seed_media_bridge as smb
            scene["seed"] = smb.identity_packet(app)
        except Exception:
            pass
        dest = os.path.join(str(app._exports_dir()), "studio3d-scene.json")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            import json
            json.dump(scene, f, indent=2)
        status.setText("meshed into game scene: " + dest)
        try:
            if hasattr(app, "open_extra_window"):
                app.open_extra_window("game")
        except Exception:
            pass

    def on_choose_audio():
        path, _ = QFileDialog.getOpenFileName(
            win, "Choose soundtrack", "", "Audio (*.wav *.flac *.mp3 *.m4a *.aac *.ogg *.opus)"
        )
        if path:
            state["audio"] = path
            audio_path.setText(path)

    def on_clear_audio():
        state["audio"] = ""
        audio_path.clear()

    def on_video():
        if not state["obj"]:
            status.setText("Load an OBJ first.")
            return
        exports = Path(str(app._exports_dir())).expanduser()
        exports.mkdir(parents=True, exist_ok=True)
        dest = exports / "studio3d.mp4"
        raw = exports / ".studio3d-render-alpha.mov"
        layout = _layout_code(render_layout)
        eye_w, eye_h = _eye_size(render_size)
        fps = int(render_fps.currentData())
        duration = float(render_duration.value())
        audio = state["audio"] or None
        obj_path = state["obj"]
        tex_path = state["tex"] or None
        render_params = params()

        def work():
            import obj_scene
            from media3d_pipeline import process_video
            suffix = Path(tex_path).suffix.lower() if tex_path else ""
            tex_mode = "video" if suffix in {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"} else ("image" if tex_path else "none")
            obj_scene.render_clip(obj_path, str(raw), eye_w, eye_h, fps, duration,
                                  params=render_params, texture_mode=tex_mode,
                                  texture_path=tex_path, stereo_layout=layout,
                                  eye_separation=0.065)
            full_w = eye_w * (2 if layout == "sbs" else 1)
            full_h = eye_h * (2 if layout == "tb" else 1)
            process_video(str(raw), str(dest), source_layout=layout, output_layout=layout,
                          width=full_w, height=full_h, fps=fps,
                          audio_path=audio, audio_policy="replace" if audio else "mute")
            try: raw.unlink(missing_ok=True)
            except OSError: pass
            return "3D render complete: " + str(dest)

        _submit_media_work(win, status, "Rendering independent stereo camera views and encoding…", work)

    def on_process_pick():
        path, _ = QFileDialog.getOpenFileName(
            win, "Choose rendered 3D video", "", "Video (*.mp4 *.m4v *.mov *.mkv *.webm *.avi)"
        )
        if path:
            state["process_input"] = path
            process_input.setText(path)
            try:
                from media3d_pipeline import probe_video
                meta = probe_video(path)
                status.setText("Video: %sx%s · %s fps · %s · audio=%s" % (
                    meta["width"], meta["height"], meta["frame_rate"],
                    meta["video_codec"], "yes" if meta["has_audio"] else "no"))
                # Preserve a conventional mono default; stereo is selectable.
            except Exception as exc:
                status.setText("Probe unavailable: " + str(exc))

    def on_process():
        src = state["process_input"]
        if not src:
            status.setText("Choose a rendered video first.")
            return
        src_path = Path(src)
        default_name = src_path.stem + ".processed.mp4"
        dest, _ = QFileDialog.getSaveFileName(win, "Save processed 3D video",
                                              str(Path(str(app._exports_dir())) / default_name),
                                              "MP4 (*.mp4);;MOV (*.mov);;MKV (*.mkv)")
        if not dest:
            return
        source_layout = _layout_code(process_source_layout)
        target_layout = _layout_code(process_output_layout)
        full_w, full_h = _eye_size(process_size)
        if target_layout == "sbs": full_w *= 2
        if target_layout == "tb": full_h *= 2
        fps = int(process_fps.currentData())
        audio_mode = str(process_audio.currentData())
        trim_start = float(process_start.value())
        trim_end_value = float(process_end.value())
        trim_end = trim_end_value if trim_end_value > 0 else None
        if trim_end is not None and trim_end <= trim_start:
            status.setText("End time must be later than start time, or 0 for the full clip.")
            return
        audio = state["audio"] if audio_mode == "replace" else None
        if audio_mode == "replace" and not audio:
            status.setText("Choose a soundtrack first or use Keep source audio.")
            return

        def work():
            from media3d_pipeline import process_video
            result = process_video(src, dest, source_layout=source_layout,
                                   output_layout=target_layout, width=full_w, height=full_h,
                                   fps=fps, start_seconds=trim_start, end_seconds=trim_end,
                                   audio_policy=audio_mode, audio_path=audio)
            return "Processed 3D video: %s · %s → %s · %s fps" % (
                dest, source_layout, target_layout, fps)

        _submit_media_work(win, status, "Processing stereoscopic video…", work)

    for _control in list(motion_controls.values()) + [shadow_toggle, spin, scale] + list(spins):
        try:
            if hasattr(_control, "valueChanged"):
                _control.valueChanged.connect(lambda *_: paint(getattr(app, "_studio3d_preview_time", 0.0)))
            elif hasattr(_control, "toggled"):
                _control.toggled.connect(lambda *_: paint(getattr(app, "_studio3d_preview_time", 0.0)))
        except Exception:
            pass
    b_obj.clicked.connect(on_obj)
    b_tex.clicked.connect(on_tex)
    b_song.clicked.connect(on_song)
    b_clear.clicked.connect(on_clear)
    b_pick.clicked.connect(on_pick)
    b_add.clicked.connect(on_add)
    b_mesh.clicked.connect(on_mesh)
    b_video_objs = QPushButton("🎥 Use scene OBJs in the video"); b_video_objs.clicked.connect(on_video_objs)
    # --- scene controls: arrangement · shots · lights · material · per-OBJ transform / binding / keyframes ---------
    import scene3d as _s3
    from PyQt6.QtWidgets import QCheckBox as _QCB, QSpinBox as _QSB
    sc_row = QHBoxLayout(); root.addLayout(sc_row)
    c_arr = QComboBox(); c_arr.addItems(list(_s3.ARRANGEMENTS)); c_lit = QComboBox(); c_lit.addItems(list(_s3.LIGHTS))
    c_mat = QComboBox(); c_mat.addItems(list(_s3.MATERIALS)); k_shots = _QCB("🎬 Shot per playlist row"); k_shots.setChecked(True)
    _sc0 = _s3.scene(app)
    c_arr.setCurrentText(str(_sc0.get("arrangement", "ring"))); c_lit.setCurrentText(str(_sc0.get("lights", "studio")))
    c_mat.setCurrentText(str(_sc0.get("material", "glossy"))); k_shots.setChecked(bool(_sc0.get("shots", True)))
    for _lab, _w in (("Arrangement", c_arr), ("Lights", c_lit), ("Material", c_mat), ("", k_shots)):
        if _lab:
            sc_row.addWidget(QLabel(_lab))
        sc_row.addWidget(_w)

    def _sc_set(**kw):
        sc = _s3.scene(app); sc.update(kw); app.video_obj_scene = sc
    c_arr.currentTextChanged.connect(lambda v: _sc_set(arrangement=v)); c_lit.currentTextChanged.connect(lambda v: _sc_set(lights=v))
    c_mat.currentTextChanged.connect(lambda v: _sc_set(material=v)); k_shots.toggled.connect(lambda v: _sc_set(shots=bool(v)))
    it_row = QHBoxLayout(); root.addLayout(it_row)
    sx, sy, ss, sp = (QDoubleSpinBox() for _ in range(4))
    for _w, _lo, _hi, _v, _st in ((sx, 0, 1, 0.5, 0.05), (sy, 0, 1, 0.5, 0.05), (ss, 0.05, 0.8, 0.22, 0.02), (sp, -360, 360, 30, 10)):
        _w.setRange(_lo, _hi); _w.setValue(_v); _w.setSingleStep(_st)
    c_bind = QComboBox(); c_bind.addItem("(no instrument)", "")
    for _n in list(getattr(app, "instrument_names_48", []) or [])[:128]:
        c_bind.addItem(app.instrument_label(_n) if hasattr(app, "instrument_label") else _n, _n)
    c_mode = QComboBox(); c_mode.addItems(["loudness", "pitch"])
    k_t = _QSB(); k_t.setRange(0, 100); k_t.setSuffix(" % of song")
    b_apply = QPushButton("Apply to selected OBJ"); b_key = QPushButton("◆ Keyframe")
    for _lab, _w in (("x", sx), ("y", sy), ("size", ss), ("spin", sp), ("follows", c_bind), ("", c_mode), ("at", k_t), ("", b_apply), ("", b_key)):
        if _lab:
            it_row.addWidget(QLabel(_lab))
        it_row.addWidget(_w)

    def _sel_item():
        r = scene_list.currentRow()
        if not (0 <= r < len(state["scene"])) or state["scene"][r].get("kind") != "obj":
            status.setText("Select an OBJ in the scene list (and press 🎥 Use scene OBJs in the video)."); return None
        pth = state["scene"][r]["path"]
        for it in _s3.scene(app)["items"]:
            if str(it.get("path")) == pth:
                return it
        status.setText("This OBJ is the centrepiece or not yet in the video — press 🎥 first."); return None

    def _apply():
        it = _sel_item()
        if it is not None:
            it.update(x=sx.value(), y=sy.value(), scale=ss.value(), spin=sp.value(), bind=c_bind.currentData() or "",
                      bind_mode=c_mode.currentText())
            status.setText("OBJ updated: %s" % os.path.basename(str(it["path"])))

    def _key():
        it = _sel_item()
        if it is not None:
            keys = [k for k in it.setdefault("keys", []) if abs(float(k.get("t", -1)) - k_t.value() / 100.0) > 1e-6]
            keys.append({"t": k_t.value() / 100.0, "x": sx.value(), "y": sy.value(), "scale": ss.value(), "spin": sp.value()})
            it["keys"] = sorted(keys, key=lambda k: k["t"])
            status.setText("◆ keyframe at %d %% (%d keys)" % (k_t.value(), len(it["keys"])))
    b_apply.clicked.connect(_apply); b_key.clicked.connect(_key)
    tl_row = QHBoxLayout(); root.addLayout(tl_row)
    b_draw = QPushButton("✏ Draw OBJ"); b_draw.setToolTip("Open the Draw / Record 3D voxel kit to draw a model")
    b_draw.clicked.connect(lambda: getattr(app, "open_voxel_draw_kit", lambda: status.setText("voxel kit unavailable"))())
    b_game = QPushButton("🎮 Scene → game level")

    def _game():
        import json as _json
        dest = os.path.join(str(app._exports_dir()), "studio3d-multi-obj-level.json")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        __import__("safe_io").atomic_write_json(dest, _s3.game_scene(app), indent=2, encoding="utf-8")
        status.setText("🎮 level written: " + dest)
        try:
            if hasattr(app, "open_extra_window"):
                app.open_extra_window("game")
        except Exception:
            pass
    b_game.clicked.connect(_game)
    for _w in (b_draw, b_game):
        tl_row.addWidget(_w)
    tl_row.addStretch(1)
    b_mesh.parentWidget().layout().addWidget(b_video_objs) if b_mesh.parentWidget() is not None and b_mesh.parentWidget().layout() is not None else root.addWidget(b_video_objs)
    b_audio.clicked.connect(on_choose_audio)
    b_clear_audio.clicked.connect(on_clear_audio)
    b_process_pick.clicked.connect(on_process_pick)
    b_process.clicked.connect(on_process)
    for s in spins:
        s.valueChanged.connect(lambda *_: paint(0.0))

    b_video = QPushButton("Render 3D video")
    b_video.clicked.connect(on_video)
    render_row.addWidget(b_video)

    app._studio_3d_window = win
    win.show(); win.raise_(); win.activateWindow()
    return win
