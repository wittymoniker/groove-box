"""startup_panels.py — GROOVEBOX_R32_STARTUP_PANELS_20261110

Two panels for the Startup Mode window:

  LEFT  (wide)  📁 Projects — every project from the project registry: title, folder, last
                opened / saved, autosave count, present / missing. Double-click (or Open)
                opens it; "Recover autosave" opens its newest autosave; "Forget missing"
                drops records whose files are gone (after asking).
  RIGHT (small) ▶ Quick Launch — the files you share (Network Hub ▸ Sharing): audio and video
                play right here with a built-in player, images show, before the PIN lock
                (only SHARED files are listed, so nothing private is exposed pre-PIN).
"""
from __future__ import annotations

import os
import time

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSlider


def _ago(t):
    if not t:
        return "—"
    d = time.time() - t
    return "%d min ago" % (d // 60) if d < 3600 else ("%d h ago" % (d // 3600) if d < 86400 else time.strftime("%Y-%m-%d", time.localtime(t)))


def projects_panel(on_open, on_recover=None):
    import project_registry as pr
    box = QWidget(); box.setMinimumWidth(340)
    lay = QVBoxLayout(box); lay.setContentsMargins(6, 6, 6, 6)
    t = QLabel("📁 Your projects"); t.setStyleSheet("font-size:13pt;font-weight:800;"); lay.addWidget(t)
    lst = QListWidget(); lay.addWidget(lst, 1)
    info = QLabel(""); info.setWordWrap(True); info.setStyleSheet("color:#9ab;"); lay.addWidget(info)

    def fill():
        lst.clear()
        for key, r in pr.listing():
            it = QListWidgetItem("%s%s\n   %s · %s%s" % ("" if r.get("present", True) else "⚠ ", r.get("title", "?"),
                                                     _ago(max(r.get("last_opened", 0), r.get("last_saved", 0))),
                                                     os.path.basename(r.get("folder", "")),
                                                     (" · %d autosave(s)" % len(r.get("autosaves", []))) if r.get("autosaves") else ""))
            it.setData(Qt.ItemDataRole.UserRole, (key, r))
            if not r.get("present", True):
                it.setForeground(Qt.GlobalColor.gray)
            lst.addItem(it)
        info.setText("%d project(s) known" % lst.count() if lst.count() else "No projects yet — start with Main Groovebox or Project Blueprint.")

    def cur():
        it = lst.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else (None, None)

    def do_open(*_):
        k, r = cur()
        if r and r.get("present", True):
            on_open(r["path"])

    def do_recover():
        k, r = cur()
        a = [p for p in (r or {}).get("autosaves", []) if os.path.isfile(p)]
        if a and on_recover:
            on_recover(max(a, key=os.path.getmtime))

    def do_forget():
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(box, "Forget missing projects", "Remove records of projects whose files are gone?") == QMessageBox.StandardButton.Yes:
            pr.prune(); fill()
    lst.itemDoubleClicked.connect(do_open)
    lst.currentItemChanged.connect(lambda it, _p: info.setText(it.data(Qt.ItemDataRole.UserRole)[1].get("path", "")) if it else None)
    row = QHBoxLayout()
    for cap, fn in (("Open", do_open), ("Recover autosave", do_recover), ("Forget missing", do_forget), ("↻", fill)):
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    lay.addLayout(row)
    fill()
    return box


def quick_launch_panel():
    import groovebox_site as gs
    box = QWidget(); box.setMinimumWidth(240); box.setMaximumWidth(360)
    lay = QVBoxLayout(box); lay.setContentsMargins(6, 6, 6, 6)
    t = QLabel("▶ Quick Launch"); t.setStyleSheet("font-size:13pt;font-weight:800;"); lay.addWidget(t)
    lay.addWidget(QLabel("Shared files — watch, listen, play"))
    lst = QListWidget(); lay.addWidget(lst, 1)
    for _i, p in gs.shared_files()[:300]:
        k = gs.kind_of(p)
        if k in ("audio", "video", "image"):
            it = QListWidgetItem({"audio": "🎵 ", "video": "🎬 ", "image": "🖼 "}[k] + os.path.basename(p)); it.setData(Qt.ItemDataRole.UserRole, p)
            lst.addItem(it)
    if not lst.count():
        lst.addItem("(nothing shared yet — Network Hub ▸ Sharing)")
    view_holder = QVBoxLayout(); lay.addLayout(view_holder)
    state = {"player": None, "video": None, "audio": None, "img": None}
    try:
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        pl = QMediaPlayer(box); ao = QAudioOutput(box); pl.setAudioOutput(ao)
        vw = QVideoWidget(); vw.setMinimumHeight(140); pl.setVideoOutput(vw); view_holder.addWidget(vw)
        state.update(player=pl, video=vw, audio=ao)
    except Exception as exc:
        view_holder.addWidget(QLabel("player unavailable: %s" % exc))
    img = QLabel(); img.setAlignment(Qt.AlignmentFlag.AlignCenter); img.hide(); view_holder.addWidget(img); state["img"] = img
    vol = QSlider(Qt.Orientation.Horizontal); vol.setRange(0, 100); vol.setValue(70); lay.addWidget(vol)
    if state["audio"] is not None:
        vol.valueChanged.connect(lambda v: state["audio"].setVolume(v / 100.0)); state["audio"].setVolume(0.7)

    def play(it):
        p = it.data(Qt.ItemDataRole.UserRole)
        if not p:
            return
        if gs.kind_of(p) == "image":
            from PyQt6.QtGui import QPixmap
            img.setPixmap(QPixmap(p).scaledToWidth(220, Qt.TransformationMode.SmoothTransformation)); img.show()
            if state["video"] is not None:
                state["video"].hide()
            return
        img.hide()
        if state["player"] is not None:
            state["video"].setVisible(gs.kind_of(p) == "video")
            state["player"].setSource(QUrl.fromLocalFile(p)); state["player"].play()
    lst.itemDoubleClicked.connect(play); lst.itemActivated.connect(play)
    row = QHBoxLayout()
    for cap, fn in (("▶", lambda: lst.currentItem() and play(lst.currentItem())), ("⏸", lambda: state["player"] and state["player"].pause()),
                    ("■", lambda: state["player"] and state["player"].stop())):
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    lay.addLayout(row)
    box._state = state
    return box
