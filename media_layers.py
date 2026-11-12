"""media_layers.py — layer and remix exports in one sweep.

GROOVEBOX_MEDIA_LAYERS_20261111
A minimal toolkit on top of the minimal generator:
  * layer A with B (or a random other export)
  * add a layer from another file
  * use one file as the recipe that remixes / distorts the reverse-engineer of another
"""
from __future__ import annotations

import os
import random
import shutil
import subprocess

AUDIO = (".wav", ".flac", ".mp3", ".ogg")
VIDEO = (".mp4", ".webm", ".mov", ".mkv")


def _ffmpeg():
    return shutil.which("ffmpeg")


def list_exports(folder: str):
    out = []
    if not os.path.isdir(folder):
        return out
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        if os.path.isfile(p) and name.lower().endswith(AUDIO + VIDEO):
            out.append(p)
    return sorted(out, key=os.path.getmtime, reverse=True)


def layer(a: str, b: str, dest: str, gain_b: float = 0.5) -> str:
    """Layer B onto A. Audio is mixed; video is overlaid. Returns dest."""
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg is required to layer media")
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    if a.lower().endswith(AUDIO) and b.lower().endswith(AUDIO):
        cmd = [ff, "-y", "-i", a, "-i", b, "-filter_complex",
               "[1:a]volume=%s[b];[0:a][b]amix=inputs=2:duration=longest" % gain_b,
               dest]
    else:
        cmd = [ff, "-y", "-i", a, "-i", b, "-filter_complex",
               "[1:v]format=rgba,colorchannelmixer=aa=%s[b];[0:v][b]overlay" % gain_b,
               "-shortest", dest]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "ffmpeg failed")[-200:])
    return dest


def recipe_remix(source: str, recipe: str, dest: str) -> str:
    """Use recipe's energy to distort source. Audio: sidechain-like drive. Video: blend."""
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg is required")
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    if source.lower().endswith(AUDIO):
        cmd = [ff, "-y", "-i", source, "-i", recipe, "-filter_complex",
               "[1:a]aformat=channel_layouts=stereo,volume=0.4[r];[0:a][r]amix=inputs=2:duration=first,atempo=1.0",
               dest]
    else:
        cmd = [ff, "-y", "-i", source, "-i", recipe, "-filter_complex",
               "[1:v]scale=iw:ih,format=rgba,colorchannelmixer=aa=0.35[r];[0:v][r]overlay",
               "-shortest", dest]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "ffmpeg failed")[-200:])
    return dest


def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                 QListWidget, QFileDialog, QDoubleSpinBox)
    w = getattr(app, "_media_layers_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); return w
    except RuntimeError:
        w = None
    win = QWidget(app, Qt.WindowType.Window)
    win.setWindowTitle("🎚 Layer sweep · remix · reverse-engineer recipe")
    win.resize(720, 480)
    root = QVBoxLayout(win)
    root.addWidget(QLabel("Pick an export, layer another (or a random one) onto it, or use one file as the recipe that remixes another."))
    lst = QListWidget(); root.addWidget(lst, 1)
    status = QLabel(""); status.setWordWrap(True); root.addWidget(status)
    gain = QDoubleSpinBox(); gain.setRange(0.05, 1.0); gain.setSingleStep(0.05); gain.setValue(0.5)

    def folder():
        try:
            return str(app._exports_dir())
        except Exception:
            return os.path.expanduser("~")

    def refresh():
        lst.clear()
        for p in list_exports(folder()):
            lst.addItem(p)
    refresh()

    def selected():
        it = lst.currentItem()
        return it.text() if it else ""

    def on_layer():
        a = selected()
        others = [p for p in list_exports(folder()) if p != a]
        if not a or not others:
            status.setText("Need at least two exports.")
            return
        b = random.choice(others)
        dest = os.path.join(folder(), "layered-" + os.path.basename(a))
        try:
            layer(a, b, dest, gain.value())
            status.setText("layered %s + %s → %s" % (os.path.basename(a), os.path.basename(b), os.path.basename(dest)))
            refresh()
        except Exception as exc:
            status.setText(str(exc))

    def on_add():
        a = selected()
        b, _ = QFileDialog.getOpenFileName(win, "Layer from", folder(), "Media (*.wav *.flac *.mp3 *.mp4 *.webm)")
        if not a or not b:
            return
        dest = os.path.join(folder(), "layered-" + os.path.basename(a))
        try:
            layer(a, b, dest, gain.value())
            status.setText("added layer → " + os.path.basename(dest))
            refresh()
        except Exception as exc:
            status.setText(str(exc))

    def on_recipe():
        source = selected()
        recipe, _ = QFileDialog.getOpenFileName(win, "Recipe file (remix / distort)", folder(), "Media (*.wav *.flac *.mp3 *.mp4 *.webm *.seed *.json)")
        if not source or not recipe:
            return
        dest = os.path.join(folder(), "remix-" + os.path.basename(source))
        try:
            if recipe.lower().endswith((".seed", ".json", ".txt")):
                # A text recipe: reverse-engineer note, then distort by mixing a generated tone from its length.
                status.setText("recipe is text — open Transmute to reverse-engineer it, then layer the result.")
                return
            recipe_remix(source, recipe, dest)
            status.setText("remixed with recipe → " + os.path.basename(dest))
            refresh()
        except Exception as exc:
            status.setText(str(exc))

    row = QHBoxLayout()
    b1 = QPushButton("Layer + random"); b1.clicked.connect(on_layer)
    b2 = QPushButton("Add layer from…"); b2.clicked.connect(on_add)
    b3 = QPushButton("Recipe remix…"); b3.clicked.connect(on_recipe)
    b4 = QPushButton("Refresh"); b4.clicked.connect(refresh)
    for b in (b1, b2, b3, b4):
        row.addWidget(b)
    row.addWidget(QLabel("layer gain")); row.addWidget(gain)
    root.addLayout(row)
    app._media_layers_window = win
    win.show(); win.raise_()
    return win
