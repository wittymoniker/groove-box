"""editor_bridge.py (R132): the editors encode / decode into each other through media_transmuter.

Audio Editor  → 🖼 Image Editor (log-frequency spectrogram, invertible) · → 🧩 Project (reverse engineer to .MCC)
Image Editor  → 🎧 Audio Editor (the layer sonified: each column a spectrum frame)
3D Studio     ← image heightmap (mesh_tools.heightmap) — a picture becomes terrain
Every hop is deterministic, so A → B → A returns something recognisably A (phase is reconstructed for sound).
"""
from __future__ import annotations

import os
import tempfile


def _tmp(ext):
    d = os.path.join(tempfile.gettempdir(), "groovebox-bridge"); os.makedirs(d, exist_ok=True)
    return tempfile.mktemp(suffix=ext, dir=d)


def audio_to_image_file(x, sr):
    import audio_editor as ae, media_transmuter as mt
    wav = _tmp(".wav"); ae.save(wav, x, sr)
    return mt.sound_to_image(wav, os.path.splitext(wav)[0] + ".spectrogram.png")


def image_to_audio_file(qimage, sr=48000):
    import media_transmuter as mt
    png = _tmp(".png"); qimage.save(png)
    return mt.image_to_sound(png, os.path.splitext(png)[0] + ".sonified.wav", sr=sr)


def install_audio_editor(dialog, layout, app):
    from PyQt6.QtWidgets import QPushButton, QMessageBox

    def to_image():
        doc = dialog._doc.get("doc")
        if doc is None:
            return
        a, b = doc.selection()
        png = audio_to_image_file(doc.x[a:b], doc.sr)
        w = __import__("image_editor").open_window(app)
        if hasattr(w, "open_path"):
            w.open_path(png)

    def to_project():
        doc = dialog._doc.get("doc")
        if doc is None:
            return
        import audio_editor as ae, media_transmuter as mt
        wav = _tmp(".wav"); ae.save(wav, doc.x, doc.sr)
        try:
            res = mt.convert(app, wav, "project")
            QMessageBox.information(dialog, "Reverse engineer", f"Project written:\n{res}")
        except Exception as exc:
            QMessageBox.warning(dialog, "Reverse engineer", str(exc))
    for cap, tip, fn in (("→ 🖼 Image Editor", "The selection as a log-frequency spectrogram (paint on it, then → Audio)", to_image),
                         ("→ 🧩 Project", "Reverse-engineer this sound into a Groovebox project (tempo, pitch, energy → seed program)", to_project)):
        b = QPushButton(cap); b.setToolTip(tip); b.clicked.connect(lambda _c=False, f=fn: f()); layout.addWidget(b)


def install_image_editor(ed, side_layout):
    from PyQt6.QtWidgets import QPushButton

    def to_audio():
        L = ed.current()
        if not L:
            return
        wav = image_to_audio_file(ed.canvas.composite() if hasattr(ed.canvas, "composite") else L.img)
        __import__("audio_editor").open_window(ed.app, wav)
    b = QPushButton("→ 🎧 Audio Editor (sonify)"); b.setToolTip("The picture played as a spectrogram: x = time, y = pitch")
    b.clicked.connect(lambda _c=False: to_audio()); side_layout.addWidget(b)
