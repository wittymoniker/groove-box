"""studio_3d.py — 3D Studio.

GROOVEBOX_3D_STUDIO_20261111
Explore media in 3D: wrap an image or video onto an OBJ, tint the mesh,
compose OBJs + video + audio into a scene, view a song as a 3D model,
export a 3D video, and mesh the scene into a game.
"""
from __future__ import annotations

import json
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QFileDialog, QDoubleSpinBox, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QComboBox)


def _rgba_to_pixmap(rgba):
    h, w = rgba.shape[:2]
    img = QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(img.copy())


def open_window(app):
    w = getattr(app, "_studio_3d_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); w.activateWindow(); return w
    except RuntimeError:
        w = None
    win = QWidget(app, Qt.WindowType.Window)
    win.setWindowTitle("🧊 3D Studio · wrap · tint · scene · game")
    win.resize(920, 680)
    root = QVBoxLayout(win)
    info = QLabel("Load an OBJ, wrap an image or video onto it, tint it, and build a scene of models, video, and audio. "
                  "Export a 3D video, or mesh the scene into a game.")
    info.setWordWrap(True); root.addWidget(info)
    preview = QLabel("No model loaded"); preview.setMinimumHeight(280); preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview.setStyleSheet("background:#0d1118; color:#9ab; border:1px solid #345;")
    root.addWidget(preview, 1)

    state = {"mesh": None, "obj": "", "tex": "", "tint": (200, 220, 255), "scene": []}

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

    scene_row = QHBoxLayout()
    scene_list = QListWidget(); scene_list.setMaximumHeight(120)
    scene_row.addWidget(scene_list, 1)
    col = QVBoxLayout()
    kind = QComboBox(); kind.addItems(["obj", "video", "audio"])
    path_edit = QLineEdit(); path_edit.setPlaceholderText("path, or pick")
    b_add = QPushButton("Add to scene")
    b_pick = QPushButton("Pick file")
    b_mesh = QPushButton("Mesh into game")
    b_video = QPushButton("Make 3D video")
    for wdg in (kind, path_edit, b_pick, b_add, b_mesh, b_video):
        col.addWidget(wdg)
    scene_row.addLayout(col)
    root.addLayout(scene_row)
    status = QLabel(""); status.setWordWrap(True); root.addWidget(status)

    def params():
        return {
            "color": tuple(int(s.value()) for s in spins),
            "spin_deg_s": float(spin.value()),
            "scale": float(scale.value()),
            "tilt_deg": 15.0,
        }

    def paint(t=0.0):
        mesh = state["mesh"]
        if mesh is None:
            preview.setText("No model loaded")
            return
        try:
            import obj_scene
            tex = None
            if state["tex"] and os.path.isfile(state["tex"]):
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
        path, _ = QFileDialog.getOpenFileName(win, "OBJ", "", "OBJ (*.obj)")
        if path:
            load_obj(path)

    def on_tex():
        path, _ = QFileDialog.getOpenFileName(win, "Wrap onto the model", "", "Media (*.png *.jpg *.jpeg *.mp4 *.webm *.mov)")
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
        path, _ = QFileDialog.getOpenFileName(win, "Scene media", "", "Media (*.obj *.mp4 *.webm *.wav *.flac *.mp3)")
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
            load_obj(path)

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
            json.dump(scene, f, indent=2)
        status.setText("meshed into game scene: " + dest)
        try:
            if hasattr(app, "open_extra_window"):
                app.open_extra_window("game")
        except Exception:
            pass

    def on_video():
        if not state["obj"]:
            status.setText("Load an OBJ first.")
            return
        dest = os.path.join(str(app._exports_dir()), "studio3d.mp4")
        status.setText("rendering 3D video…")
        def work():
            import obj_scene
            mode = "image" if state["tex"] else "none"
            obj_scene.render_clip(state["obj"], dest, 640, 360, 24, 4.0,
                                  params=params(), texture_mode=mode, texture_path=state["tex"] or None)
            return dest
        try:
            from ui_runtime import submit_ui_task
            submit_ui_task(work, lambda p: status.setText("3D video: " + str(p)))
        except Exception:
            try:
                work()
                status.setText("3D video: " + dest)
            except Exception as exc:
                status.setText("3D video failed: " + str(exc))

    b_obj.clicked.connect(on_obj)
    b_tex.clicked.connect(on_tex)
    b_song.clicked.connect(on_song)
    b_clear.clicked.connect(on_clear)
    b_pick.clicked.connect(on_pick)
    b_add.clicked.connect(on_add)
    b_mesh.clicked.connect(on_mesh)
    b_video.clicked.connect(on_video)
    for s in spins:
        s.valueChanged.connect(lambda *_: paint(0.0))
    app._studio_3d_window = win
    win.show(); win.raise_(); win.activateWindow()
    return win
