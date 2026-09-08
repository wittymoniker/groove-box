#!/usr/bin/env python3
"""Performance Record / Import / Draw Video Clip studio.

Lightweight, project-aware authoring surface for:
  * explicit camera, microphone and tablet/media-source selection
  * live camera preview and microphone level preview
  * onboard/USB camera + microphone recording through Qt Multimedia
  * tablet/removable-media video import into the active Groovebox project
  * basic RGBA painting tools and a time-varying graph/automation pane
  * optional visual->sound and sound->visual translation
  * final video mixing with optional color->sound translation detail

Color/sound translation is deliberately opt-in.  Ordinary drawing is visual-only.
No normalizer, limiter, compressor or generic clip stage is introduced here.
Generated audio is mixed with FFmpeg amix normalize=0 so project/master dynamics
remain under the existing Groovebox master path and intentional hard clipper.
"""
from __future__ import annotations

import array
import json
import math
import os
import shutil
import subprocess
import sys
import time
import wave
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from PyQt6.QtCore import Qt, QTimer, QPointF, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QTransform, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QCheckBox, QSlider, QSpinBox, QDoubleSpinBox,
    QFileDialog, QColorDialog, QMessageBox, QProgressBar, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QScrollArea, QSizePolicy,
)

from groovebox_media_tools import resolve_local_tool

try:
    from PyQt6.QtMultimedia import (
        QMediaDevices, QCamera, QMediaCaptureSession, QMediaRecorder,
        QMediaFormat, QAudioInput, QAudioSource, QAudioFormat, QVideoSink,
    )
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    QT_MULTIMEDIA = True
except Exception:
    QMediaDevices = QCamera = QMediaCaptureSession = QMediaRecorder = None
    QMediaFormat = QAudioInput = QAudioSource = QAudioFormat = QVideoSink = None
    QVideoWidget = None
    QT_MULTIMEDIA = False

VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v', '.mpeg', '.mpg'}


def _safe_stem(text: str) -> str:
    out = ''.join(c if (c.isalnum() or c in '-_ ') else '_' for c in str(text or 'clip')).strip()
    return (out or 'clip')[:90]


def _ffmpeg() -> Optional[str]:
    try:
        return resolve_local_tool('ffmpeg', required=False)
    except Exception:
        return shutil.which('ffmpeg')


def _ffprobe() -> Optional[str]:
    try:
        return resolve_local_tool('ffprobe', required=False)
    except Exception:
        return shutil.which('ffprobe')


def _probe_duration(path: str) -> float:
    p = _ffprobe()
    if not p or not path or not os.path.isfile(path):
        return 0.0
    try:
        cp = subprocess.run(
            [p, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nk=1:nw=1', path],
            capture_output=True, text=True, timeout=8,
        )
        return max(0.0, float((cp.stdout or '0').strip() or 0.0))
    except Exception:
        return 0.0


def _probe_has_audio(path: str) -> bool:
    p = _ffprobe()
    if not p or not path or not os.path.isfile(path):
        return False
    try:
        cp = subprocess.run(
            [p, '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=index', '-of', 'csv=p=0', path],
            capture_output=True, text=True, timeout=8,
        )
        return bool((cp.stdout or '').strip())
    except Exception:
        return False


def _mounted_media_sources() -> List[Tuple[str, str]]:
    """Return user-visible tablet/removable/media roots without requiring MTP libs."""
    found: List[Tuple[str, str]] = []
    candidates: List[Path] = []
    home = Path.home()
    if sys.platform == 'darwin':
        candidates.append(Path('/Volumes'))
    elif os.name == 'nt':
        for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
            p = Path(f'{letter}:/')
            if p.exists():
                found.append((f'{letter}: removable/media', str(p)))
    else:
        candidates.extend([Path('/run/media') / home.name, Path('/media') / home.name, Path('/media')])
        try:
            uid = os.getuid()
            candidates.append(Path(f'/run/user/{uid}/gvfs'))  # includes gvfs MTP mounts
        except Exception:
            pass
    seen = set()
    for parent in candidates:
        try:
            if not parent.is_dir():
                continue
            for child in sorted(parent.iterdir(), key=lambda x: x.name.lower()):
                if not child.is_dir():
                    continue
                rp = str(child.resolve())
                if rp in seen:
                    continue
                seen.add(rp)
                label = child.name
                if 'mtp:' in label.lower():
                    label = 'MTP tablet/phone — ' + label
                found.append((label, rp))
        except Exception:
            pass
    return found


class PaintCanvas(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None, width=640, height=360):
        super().__init__(parent)
        self.setMinimumSize(480, 270)
        self.setMouseTracking(True)
        self.image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.GlobalColor.transparent)
        self.tool = 'Brush'
        self.color = QColor('#ffcc33')
        self.brush_size = 12
        self._last: Optional[QPointF] = None
        self._start: Optional[QPointF] = None
        self._undo: List[QImage] = []

    def set_tool(self, tool: str):
        self.tool = str(tool)

    def set_color(self, color: QColor):
        if color.isValid():
            self.color = QColor(color)
            self.update()

    def set_brush_size(self, size: int):
        self.brush_size = max(1, int(size))

    def clear(self):
        self._snapshot()
        self.image.fill(Qt.GlobalColor.transparent)
        self.changed.emit(); self.update()

    def undo(self):
        if self._undo:
            self.image = self._undo.pop()
            self.changed.emit(); self.update()

    def _snapshot(self):
        self._undo.append(self.image.copy())
        if len(self._undo) > 20:
            del self._undo[0]

    def _to_image(self, pos) -> QPointF:
        x = float(pos.x()) * self.image.width() / max(1, self.width())
        y = float(pos.y()) * self.image.height() / max(1, self.height())
        return QPointF(max(0.0, min(self.image.width()-1.0, x)), max(0.0, min(self.image.height()-1.0, y)))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._snapshot()
        p = self._to_image(event.position())
        self._last = p; self._start = p
        if self.tool in ('Brush', 'Eraser'):
            self._draw_segment(p, p)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._last is None:
            return
        p = self._to_image(event.position())
        if self.tool in ('Brush', 'Eraser'):
            self._draw_segment(self._last, p)
        self._last = p

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        p = self._to_image(event.position())
        if self.tool not in ('Brush', 'Eraser'):
            q = QPainter(self.image)
            q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(self.color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            q.setPen(pen)
            if self.tool == 'Line':
                q.drawLine(self._start, p)
            elif self.tool == 'Rectangle':
                q.drawRect(int(min(self._start.x(),p.x())), int(min(self._start.y(),p.y())), int(abs(p.x()-self._start.x())), int(abs(p.y()-self._start.y())))
            elif self.tool == 'Ellipse':
                q.drawEllipse(int(min(self._start.x(),p.x())), int(min(self._start.y(),p.y())), int(abs(p.x()-self._start.x())), int(abs(p.y()-self._start.y())))
            q.end()
            self.changed.emit(); self.update()
        self._last = None; self._start = None

    def _draw_segment(self, a: QPointF, b: QPointF):
        q = QPainter(self.image)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.tool == 'Eraser':
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            pen = QPen(QColor(0,0,0,0), self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        else:
            pen = QPen(self.color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        q.setPen(pen); q.drawLine(a, b); q.end()
        self.changed.emit(); self.update()

    def paintEvent(self, event):
        q = QPainter(self)
        q.fillRect(self.rect(), QColor(12, 18, 24))
        tile = max(10, min(self.width(), self.height()) // 24)
        for y in range(0, self.height(), tile):
            for x in range(0, self.width(), tile):
                if ((x//tile)+(y//tile)) & 1:
                    q.fillRect(x, y, tile, tile, QColor(27,34,40))
        q.drawImage(self.rect(), self.image)
        q.setPen(QPen(QColor(80,130,150), 1)); q.drawRect(self.rect().adjusted(0,0,-1,-1))
        q.end()


class GraphLane(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.values = [0.5] * 128
        self._drawing = False

    def set_values(self, values: List[float]):
        if isinstance(values, list) and values:
            vals = [max(0.0, min(1.0, float(v))) for v in values]
            if len(vals) != 128:
                xp = np.linspace(0, 1, len(vals)); x = np.linspace(0, 1, 128)
                vals = np.interp(x, xp, vals).tolist()
            self.values = vals
        self.update()

    def reset(self, value=0.5):
        self.values = [max(0.0, min(1.0, float(value)))] * 128
        self.changed.emit(); self.update()

    def value_at(self, t01: float) -> float:
        x = max(0.0, min(1.0, float(t01))) * (len(self.values)-1)
        i = int(x); f = x-i
        if i >= len(self.values)-1: return float(self.values[-1])
        return float(self.values[i]*(1-f) + self.values[i+1]*f)

    def _write(self, pos):
        x01 = max(0.0, min(1.0, float(pos.x()) / max(1, self.width()-1)))
        y01 = 1.0 - max(0.0, min(1.0, float(pos.y()) / max(1, self.height()-1)))
        idx = int(round(x01*(len(self.values)-1)))
        self.values[idx] = y01
        # soft-connect neighbors to avoid single-bin spikes during fast tablet drawing
        for d,w in ((1,.66),(2,.33)):
            for j in (idx-d, idx+d):
                if 0 <= j < len(self.values): self.values[j] = self.values[j]*(1-w) + y01*w
        self.changed.emit(); self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True; self._write(event.position())
    def mouseMoveEvent(self, event):
        if self._drawing and (event.buttons() & Qt.MouseButton.LeftButton): self._write(event.position())
    def mouseReleaseEvent(self, event):
        self._drawing = False

    def paintEvent(self, event):
        q = QPainter(self); q.fillRect(self.rect(), QColor(7,15,22))
        q.setPen(QPen(QColor(40,70,84), 1))
        for n in range(1,8):
            x = int(n*self.width()/8); q.drawLine(x,0,x,self.height())
        for n in range(1,4):
            y = int(n*self.height()/4); q.drawLine(0,y,self.width(),y)
        q.setPen(QPen(QColor(245,211,109), 2))
        prev = None
        for i,v in enumerate(self.values):
            p = QPointF(i*(self.width()-1)/(len(self.values)-1), (1-v)*(self.height()-1))
            if prev is not None: q.drawLine(prev,p)
            prev = p
        q.end()


class VideoClipStudio(QWidget):
    """Project-aware Record / Import / Draw Video Clip workspace."""

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self.base_clip = ''
        self._camera_devices = []
        self._audio_devices = []
        self._camera = None
        self._capture_session = None
        self._video_sink = None
        self._recorder = None
        self._record_audio_input = None
        self._record_path = ''
        self._record_final_path = ''
        self._record_container = 'mp4'
        self._recorder_error_text = ''
        self._mic_source = None
        self._mic_io = None
        self._mic_level = 0.0
        self._sw_recording = False
        self._sw_record_dir = ''
        self._sw_frame_index = 0
        self._sw_last_frame_t = 0.0
        self._sw_audio_fh = None
        self._sw_audio_rate = 48000
        self._sw_audio_channels = 1
        self._sw_started_mic = False
        self.last_rendered_video = ''
        self.recording_layers: List[str] = []
        self.draw_layers: List[Dict[str, Any]] = []
        self.draw_canvases: List[PaintCanvas] = []
        self._curves: Dict[str, List[float]] = {}
        self._current_curve_target = 'Layer Opacity'
        self._build_ui()
        self.refresh_devices()

    # --------------------------- project paths
    def _project_path(self) -> Optional[str]:
        return getattr(self.host, '_current_project_path', None)

    def _recordings_dir(self) -> str:
        import groovebox_paths
        return groovebox_paths.recordings_dir(self._project_path())

    def _layers_dir(self) -> str:
        import groovebox_paths
        return groovebox_paths.layers_dir(self._project_path())

    def _video_exports_dir(self) -> str:
        import groovebox_paths
        return groovebox_paths.video_exports_dir(self._project_path())

    # --------------------------- UI
    def _build_ui(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        whole_scroll = QScrollArea(); whole_scroll.setWidgetResizable(True)
        whole_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        whole_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        whole_body = QWidget(); whole_body.setMinimumWidth(760)
        root = QVBoxLayout(whole_body); root.setContentsMargins(5,5,5,5); root.setSpacing(5)
        whole_scroll.setWidget(whole_body); outer.addWidget(whole_scroll)
        devices = QGroupBox('Input devices · explicit selection')
        dg = QGridLayout(devices)
        self.cmb_camera = QComboBox(); self.cmb_mic = QComboBox(); self.cmb_tablet = QComboBox()
        dg.addWidget(QLabel('Camera'),0,0); dg.addWidget(self.cmb_camera,0,1)
        dg.addWidget(QLabel('Microphone'),1,0); dg.addWidget(self.cmb_mic,1,1)
        dg.addWidget(QLabel('Tablet / media source'),2,0); dg.addWidget(self.cmb_tablet,2,1)
        brefresh = QPushButton('↻ Refresh devices'); brefresh.clicked.connect(self.refresh_devices); dg.addWidget(brefresh,0,2)
        self.btn_camera_preview = QPushButton('▶ Camera Preview'); self.btn_camera_preview.setCheckable(True); self.btn_camera_preview.toggled.connect(self._toggle_camera_preview); dg.addWidget(self.btn_camera_preview,1,2)
        self.btn_mic_preview = QPushButton('▶ Mic Preview'); self.btn_mic_preview.setCheckable(True); self.btn_mic_preview.toggled.connect(self._toggle_mic_preview); dg.addWidget(self.btn_mic_preview,2,2)
        for _w in (self.cmb_camera, self.cmb_mic, self.cmb_tablet, brefresh, self.btn_camera_preview, self.btn_mic_preview):
            _w.setMinimumHeight(32)
        root.addWidget(devices)

        # Compatibility-first layout: stack capture and drawing vertically.
        # This avoids wide splitter/native-surface geometry escaping the Performance tab.
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(7)
        left = QWidget(); left.setMinimumWidth(560); ll = QVBoxLayout(left); ll.setContentsMargins(4,4,4,4); ll.setSpacing(7)
        preview_group = QGroupBox('Camera / clip preview')
        pl = QVBoxLayout(preview_group)
        # Use a software QLabel preview fed by QVideoSink rather than QVideoWidget.
        # Some Qt/GStreamer backends implement QVideoWidget with a native overlay
        # surface that ignores QScrollArea clipping and can paint over controls.
        # A QVideoSink -> QImage -> QLabel path remains a normal child widget, so
        # scrolling/maximizing can never render camera pixels outside the viewport.
        self.video_preview = QLabel('Camera preview idle')
        self.video_preview.setWordWrap(True)
        self.video_preview.setMinimumSize(480,270)
        self.video_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_preview.setStyleSheet('background:#050708; border:1px solid #29404a;')
        pl.addWidget(self.video_preview,1)
        if QT_MULTIMEDIA and QVideoSink is not None:
            try:
                self._video_sink = QVideoSink(self)
                self._video_sink.videoFrameChanged.connect(self._on_video_frame)
            except Exception:
                self._video_sink = None
        self.mic_meter = QProgressBar(); self.mic_meter.setRange(0,100); self.mic_meter.setValue(0); self.mic_meter.setFormat('Mic level %p%'); pl.addWidget(self.mic_meter)
        ll.addWidget(preview_group)

        capture = QGroupBox('Record / Import')
        cl = QGridLayout(capture)
        self.btn_record = QPushButton('● Record Camera + Mic'); self.btn_record.setCheckable(True); self.btn_record.toggled.connect(self._toggle_record)
        bimport = QPushButton('Import Video…'); bimport.clicked.connect(lambda: self.import_video(False))
        btablet = QPushButton('Import from Tablet…'); btablet.clicked.connect(lambda: self.import_video(True))
        bclearbase = QPushButton('Draw-only clip'); bclearbase.clicked.connect(self._clear_base_clip)
        cl.addWidget(self.btn_record,0,0); cl.addWidget(bimport,0,1); cl.addWidget(btablet,1,0); cl.addWidget(bclearbase,1,1)
        self.lbl_source = QLabel('Source: draw-only (black background)'); self.lbl_source.setWordWrap(True); self.lbl_source.setStyleSheet('color:#8ab4c8;'); cl.addWidget(self.lbl_source,2,0,1,2)
        self.recording_tabs=QTabWidget(); self.recording_tabs.currentChanged.connect(self._recording_tab_changed); cl.addWidget(self.recording_tabs,3,0,1,2)
        self.recordings_table=QTableWidget(0,2); self.recordings_table.setHorizontalHeaderLabels(['Recording Layer','File']); cl.addWidget(self.recordings_table,4,0,1,2)
        rrow=QHBoxLayout()
        self.btn_append_recording=QPushButton('＋ Append Recording Layer…'); self.btn_append_recording.clicked.connect(self._append_recording_layer_dialog); rrow.addWidget(self.btn_append_recording)
        self.btn_remove_recording=QPushButton('− Remove Recording Layer Tab'); self.btn_remove_recording.clicked.connect(self._remove_recording_layer_tab); rrow.addWidget(self.btn_remove_recording)
        self.btn_clear_recordings=QPushButton('Clear Recordings Table'); self.btn_clear_recordings.clicked.connect(self._clear_recordings_table); rrow.addWidget(self.btn_clear_recordings)
        cl.addLayout(rrow,5,0,1,2)
        self.recording_tabs.setMinimumHeight(100)
        self.recordings_table.setMinimumHeight(125)
        self.recordings_table.horizontalHeader().setStretchLastSection(True)
        for _b in (self.btn_record, bimport, btablet, bclearbase, self.btn_append_recording, self.btn_remove_recording, self.btn_clear_recordings):
            _b.setMinimumHeight(34)
            _b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ll.addWidget(capture)
        ll.addStretch(1)

        # Each major pane owns its own two-axis scroll viewport. The camera
        # preview is a software QLabel (QVideoSink -> QImage), so unlike the old
        # native QVideoWidget path it remains clipped correctly inside this viewport.
        left_scroll = QScrollArea(); left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setMinimumWidth(420); left_scroll.setWidget(left)
        split.addWidget(left_scroll)

        right = QWidget(); right.setMinimumWidth(680); rl = QVBoxLayout(right); rl.setContentsMargins(4,4,4,4); rl.setSpacing(7)
        paint_group = QGroupBox('Image paint layer')
        pgl = QVBoxLayout(paint_group)
        tools = QHBoxLayout()
        self.cmb_tool = QComboBox(); self.cmb_tool.addItems(['Brush','Eraser','Line','Rectangle','Ellipse']); self.cmb_tool.currentTextChanged.connect(lambda t:self.canvas.set_tool(t)); tools.addWidget(self.cmb_tool)
        self.btn_color = QPushButton('Color'); self.btn_color.clicked.connect(self._choose_color); tools.addWidget(self.btn_color)
        tools.addWidget(QLabel('Size'))
        self.sld_brush = QSlider(Qt.Orientation.Horizontal); self.sld_brush.setRange(1,80); self.sld_brush.setValue(12); self.sld_brush.valueChanged.connect(lambda v:self.canvas.set_brush_size(v)); tools.addWidget(self.sld_brush,1)
        bund = QPushButton('Undo'); bund.clicked.connect(lambda:self.canvas.undo()); tools.addWidget(bund)
        bclear = QPushButton('Clear'); bclear.clicked.connect(lambda:self.canvas.clear()); tools.addWidget(bclear)
        pgl.addLayout(tools)
        layerrow=QHBoxLayout()
        self.btn_append_draw_layer=QPushButton('＋ Append Drawing Layer'); self.btn_append_draw_layer.clicked.connect(self._append_draw_layer); layerrow.addWidget(self.btn_append_draw_layer)
        self.btn_remove_draw_layer=QPushButton('− Remove Drawing Layer'); self.btn_remove_draw_layer.clicked.connect(self._remove_draw_layer); layerrow.addWidget(self.btn_remove_draw_layer)
        layerrow.addWidget(QLabel('Start s')); self.spin_layer_start=QDoubleSpinBox(); self.spin_layer_start.setRange(0,3600); self.spin_layer_start.setDecimals(3); self.spin_layer_start.valueChanged.connect(self._update_draw_layer_controls); layerrow.addWidget(self.spin_layer_start)
        layerrow.addWidget(QLabel('End s')); self.spin_layer_end=QDoubleSpinBox(); self.spin_layer_end.setRange(0,3600); self.spin_layer_end.setDecimals(3); self.spin_layer_end.setValue(5); self.spin_layer_end.valueChanged.connect(self._update_draw_layer_controls); layerrow.addWidget(self.spin_layer_end)
        layerrow.addWidget(QLabel('Fade in/out s')); self.spin_layer_fade=QDoubleSpinBox(); self.spin_layer_fade.setRange(0,600); self.spin_layer_fade.setDecimals(3); self.spin_layer_fade.valueChanged.connect(self._update_draw_layer_controls); layerrow.addWidget(self.spin_layer_fade)
        pgl.addLayout(layerrow)
        self.draw_tabs=QTabWidget(); self.draw_tabs.currentChanged.connect(self._draw_tab_changed); pgl.addWidget(self.draw_tabs,1)
        self.canvas = None
        self._append_draw_layer()
        rl.addWidget(paint_group,3)
        right_scroll = QScrollArea(); right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll.setMinimumWidth(420); right_scroll.setWidget(right)
        split.addWidget(right_scroll)
        split.setStretchFactor(0, 1); split.setStretchFactor(1, 1)
        split.setSizes([620, 760])
        split.setMinimumWidth(1160)
        split.setStretchFactor(0,5); split.setStretchFactor(1,6)
        split.setSizes([560, 640])
        root.addWidget(split,4)

        graph_group = QGroupBox('Time-varying graph layer · draw left→right across clip time')
        gl = QVBoxLayout(graph_group)
        gr = QHBoxLayout(); gr.addWidget(QLabel('Graph target'))
        self.cmb_graph_target = QComboBox(); self.cmb_graph_target.addItems([
            'Layer Opacity','Layer X','Layer Y','Layer Scale','Layer Rotation',
            'Drawn Sound Pitch','Drawn Sound Gain','Sound→Color Amount'
        ]); self.cmb_graph_target.currentTextChanged.connect(self._switch_curve); gr.addWidget(self.cmb_graph_target)
        breset = QPushButton('Reset lane'); breset.clicked.connect(self._reset_curve); gr.addWidget(breset)
        gr.addStretch(1); gl.addLayout(gr)
        self.graph = GraphLane(); self.graph.changed.connect(self._capture_curve); gl.addWidget(self.graph)
        root.addWidget(graph_group,2)

        mix = QGroupBox('Final video mix · translations are optional')
        mg = QGridLayout(mix)
        self.chk_draw_sound = QCheckBox('Draw Sound from graph lane'); self.chk_draw_sound.setChecked(False)
        self.chk_color_sound = QCheckBox('Enable Color→Sound'); self.chk_color_sound.setChecked(False)
        self.chk_sound_color = QCheckBox('Enable Sound→Color'); self.chk_sound_color.setChecked(False)
        self.cmb_color_detail = QComboBox(); self.cmb_color_detail.addItems(['Off','Basic','Detailed']); self.cmb_color_detail.setCurrentText('Off')
        self.cmb_color_detail.setToolTip('FINAL-MIX option. Off performs no color→sound calculations. Basic maps global hue/saturation/value; Detailed maps multiple color regions as a deterministic partial bank.')
        self.spin_duration = QDoubleSpinBox(); self.spin_duration.setRange(.25,3600.0); self.spin_duration.setDecimals(2); self.spin_duration.setValue(5.0); self.spin_duration.setSuffix(' s')
        self.spin_fps = QSpinBox(); self.spin_fps.setRange(1,120); self.spin_fps.setValue(30); self.spin_fps.setSuffix(' fps')
        self.spin_width = QSpinBox(); self.spin_width.setRange(160,3840); self.spin_width.setValue(1280)
        self.spin_height = QSpinBox(); self.spin_height.setRange(90,2160); self.spin_height.setValue(720)
        mg.addWidget(self.chk_draw_sound,0,0); mg.addWidget(self.chk_color_sound,0,1); mg.addWidget(self.chk_sound_color,0,2)
        mg.addWidget(QLabel('Color→Sound Translation Detail'),1,0); mg.addWidget(self.cmb_color_detail,1,1)
        mg.addWidget(QLabel('Duration'),2,0); mg.addWidget(self.spin_duration,2,1); mg.addWidget(self.spin_fps,2,2)
        mg.addWidget(QLabel('Frame'),3,0); wh=QHBoxLayout(); wh.addWidget(self.spin_width); wh.addWidget(QLabel('×')); wh.addWidget(self.spin_height); mg.addLayout(wh,3,1)
        bsave = QPushButton('Save Paint/Graph Layer'); bsave.clicked.connect(lambda:self._persist_layer(False)); mg.addWidget(bsave,3,2)
        mg.addWidget(QLabel('Bind All Layers to Instrument'),4,0)
        self.cmb_bind_all=QComboBox(); self.cmb_bind_all.addItems(['Video','Audio','Both','Unbound']); mg.addWidget(self.cmb_bind_all,4,1)
        self.btn_bind_all=QPushButton('Bind All Layers to Selected Instrument'); self.btn_bind_all.clicked.connect(self._bind_all_layers_to_instrument); mg.addWidget(self.btn_bind_all,4,2)
        self.btn_bind_carrier=QPushButton('Bind All Layers to Carrier'); self.btn_bind_carrier.clicked.connect(self._bind_all_layers_to_carrier); mg.addWidget(self.btn_bind_carrier,5,0,1,3)
        self.btn_render = QPushButton('Render / Mix Video Clip…'); self.btn_render.clicked.connect(self.render_video); mg.addWidget(self.btn_render,6,0,1,2)
        self.lbl_render = QLabel('Visual drawing is independent of sound drawing. Color↔sound translation is OFF by default.'); self.lbl_render.setWordWrap(True); self.lbl_render.setStyleSheet('color:#9dffb0;'); mg.addWidget(self.lbl_render,6,2)
        root.addWidget(mix)

        self._mic_timer = QTimer(self); self._mic_timer.setInterval(50); self._mic_timer.timeout.connect(self._update_mic_meter); self._mic_timer.start()
        self._set_color_button()
        self._reset_curve()

    def _append_recording_path(self,path:str):
        path=os.path.abspath(str(path or ''))
        if not path or not os.path.isfile(path):return
        if path not in self.recording_layers:self.recording_layers.append(path)
        page=QWidget(); lay=QVBoxLayout(page); q=QLabel(path); q.setWordWrap(True); q.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(q)
        idx=self.recording_tabs.addTab(page,Path(path).stem[:32]); self.recording_tabs.setCurrentIndex(idx)
        self.base_clip=path; self.lbl_source.setText('Source: '+path); self._refresh_recordings_table()
    def _append_recording_layer_dialog(self):
        p,_=QFileDialog.getOpenFileName(self,'Append recording layer',self._recordings_dir(),'Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v *.mpeg *.mpg);;All files (*)')
        if p:self._append_recording_path(p); self._save_host_state()
    def _recording_tab_changed(self,i):
        if 0<=i<len(self.recording_layers):
            self.base_clip=self.recording_layers[i]; self.lbl_source.setText('Source: '+self.base_clip)
    def _remove_recording_layer_tab(self):
        i=self.recording_tabs.currentIndex()
        if i<0:return
        self.recording_tabs.removeTab(i)
        if i<len(self.recording_layers):self.recording_layers.pop(i)
        if self.recording_layers:
            j=max(0,min(i,len(self.recording_layers)-1)); self.recording_tabs.setCurrentIndex(j); self.base_clip=self.recording_layers[j]
        else:self.base_clip=''; self.lbl_source.setText('Source: draw-only (black background)')
        self._refresh_recordings_table(); self._save_host_state()
    def _clear_recordings_table(self):
        self.recordings_table.setRowCount(0); self.lbl_render.setText('Recordings Table cleared. Recording files and layer tabs were not deleted.')
    def _refresh_recordings_table(self):
        self.recordings_table.setRowCount(len(self.recording_layers))
        for r,p in enumerate(self.recording_layers):
            self.recordings_table.setItem(r,0,QTableWidgetItem(Path(p).stem)); self.recordings_table.setItem(r,1,QTableWidgetItem(p))
    def _append_draw_layer(self):
        c=PaintCanvas(); c.set_tool(self.cmb_tool.currentText() if hasattr(self,'cmb_tool') else 'Brush'); c.set_brush_size(self.sld_brush.value() if hasattr(self,'sld_brush') else 12)
        rec={'name':f'Drawing {len(self.draw_layers)+1}','start':0.0,'end':float(self.spin_duration.value()) if hasattr(self,'spin_duration') else 5.0,'fade':0.0}
        self.draw_layers.append(rec); self.draw_canvases.append(c); idx=self.draw_tabs.addTab(c,rec['name']); self.draw_tabs.setCurrentIndex(idx); self.canvas=c; self._set_color_button()
    def _remove_draw_layer(self):
        i=self.draw_tabs.currentIndex()
        if i<0:return
        self.draw_tabs.removeTab(i)
        if i<len(self.draw_layers):self.draw_layers.pop(i); self.draw_canvases.pop(i)
        if not self.draw_layers:self._append_draw_layer()
        else:self._draw_tab_changed(max(0,min(i,len(self.draw_layers)-1)))
    def _draw_tab_changed(self,i):
        if not (0<=i<len(self.draw_layers)):return
        self.canvas=self.draw_canvases[i]; r=self.draw_layers[i]
        for w in (self.spin_layer_start,self.spin_layer_end,self.spin_layer_fade):w.blockSignals(True)
        default_end = float(self.spin_duration.value()) if hasattr(self, 'spin_duration') else 5.0
        self.spin_layer_start.setValue(float(r.get('start',0))); self.spin_layer_end.setValue(float(r.get('end', default_end))); self.spin_layer_fade.setValue(float(r.get('fade',0)))
        for w in (self.spin_layer_start,self.spin_layer_end,self.spin_layer_fade):w.blockSignals(False)
        self._set_color_button()
    def _update_draw_layer_controls(self,*_):
        i=self.draw_tabs.currentIndex() if hasattr(self,'draw_tabs') else -1
        if 0<=i<len(self.draw_layers):
            self.draw_layers[i].update(start=float(self.spin_layer_start.value()),end=float(self.spin_layer_end.value()),fade=float(self.spin_layer_fade.value()))
    def _draw_layer_time_gain(self,rec,tsec):
        start=float(rec.get('start',0)); end=float(rec.get('end',1e9)); fade=max(0.0,float(rec.get('fade',0)))
        if tsec<start or tsec>end:return 0.0
        g=1.0
        if fade>0:g=min(g,max(0.0,min(1.0,(tsec-start)/fade)),max(0.0,min(1.0,(end-tsec)/fade)))
        return g

    # --------------------------- devices
    def refresh_devices(self):
        oldc = self.cmb_camera.currentText() if self.cmb_camera.count() else ''
        oldm = self.cmb_mic.currentText() if self.cmb_mic.count() else ''
        oldt = self.cmb_tablet.currentData() if self.cmb_tablet.count() else ''
        self.cmb_camera.clear(); self.cmb_mic.clear(); self.cmb_tablet.clear()
        self._camera_devices=[]; self._audio_devices=[]
        if QT_MULTIMEDIA:
            try:
                self._camera_devices = list(QMediaDevices.videoInputs())
                for d in self._camera_devices: self.cmb_camera.addItem(d.description())
            except Exception: pass
            try:
                self._audio_devices = list(QMediaDevices.audioInputs())
                for d in self._audio_devices: self.cmb_mic.addItem(d.description())
            except Exception: pass
        if not self._camera_devices: self.cmb_camera.addItem('No Qt camera detected')
        if not self._audio_devices: self.cmb_mic.addItem('No Qt microphone detected')
        self.cmb_tablet.addItem('Browse filesystem…', '')
        for label,path in _mounted_media_sources(): self.cmb_tablet.addItem(label,path)
        for combo,old in ((self.cmb_camera,oldc),(self.cmb_mic,oldm)):
            if old:
                idx=combo.findText(old)
                if idx>=0: combo.setCurrentIndex(idx)
        if oldt:
            for i in range(self.cmb_tablet.count()):
                if self.cmb_tablet.itemData(i)==oldt: self.cmb_tablet.setCurrentIndex(i); break
        self.lbl_render.setText(f'Devices refreshed · {len(self._camera_devices)} camera(s), {len(self._audio_devices)} mic(s), {max(0,self.cmb_tablet.count()-1)} mounted tablet/media source(s).')

    def _on_video_frame(self, frame):
        """Paint camera frames inside the normal Qt widget hierarchy."""
        try:
            if frame is None or not frame.isValid():
                return
            image = frame.toImage()
            if image.isNull():
                return
            target = self.video_preview.size()
            pix = QPixmap.fromImage(image).scaled(
                target, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.video_preview.setPixmap(pix)
            if getattr(self, '_sw_recording', False):
                fps = max(1, min(60, int(self.spin_fps.value()) if hasattr(self, 'spin_fps') else 24))
                now = time.monotonic()
                if now - float(getattr(self, '_sw_last_frame_t', 0.0)) >= (1.0 / fps):
                    self._sw_last_frame_t = now
                    d = str(getattr(self, '_sw_record_dir', '') or '')
                    if d:
                        fn = os.path.join(d, f'frame_{self._sw_frame_index:08d}.jpg')
                        im = image.convertToFormat(QImage.Format.Format_RGB888)
                        if im.save(fn, 'JPG', 88):
                            self._sw_frame_index += 1
        except Exception:
            pass

    def _toggle_camera_preview(self, on: bool):
        if not on:
            try:
                if self._camera: self._camera.stop()
            except Exception: pass
            self._camera=None; self._capture_session=None
            try: self.video_preview.clear(); self.video_preview.setText('Camera preview idle')
            except Exception: pass
            self.btn_camera_preview.setText('▶ Camera Preview'); return
        if not QT_MULTIMEDIA or not self._camera_devices:
            self.btn_camera_preview.setChecked(False); QMessageBox.information(self,'Camera preview','No Qt Multimedia camera is available.'); return
        try:
            idx=max(0,min(self.cmb_camera.currentIndex(),len(self._camera_devices)-1))
            self._capture_session=QMediaCaptureSession(self)
            self._camera=QCamera(self._camera_devices[idx], self)
            self._capture_session.setCamera(self._camera)
            if self._video_sink is None:
                raise RuntimeError('Qt video sink is unavailable for scroll-safe camera preview.')
            self._capture_session.setVideoOutput(self._video_sink)
            self._camera.start(); self.btn_camera_preview.setText('■ Stop Camera Preview')
        except Exception as e:
            self.btn_camera_preview.setChecked(False); QMessageBox.warning(self,'Camera preview',str(e))

    def _toggle_mic_preview(self, on: bool):
        self._stop_mic_source()
        if not on:
            self.btn_mic_preview.setText('▶ Mic Preview'); return
        if not QT_MULTIMEDIA or not self._audio_devices:
            self.btn_mic_preview.setChecked(False); QMessageBox.information(self,'Mic preview','No Qt Multimedia microphone is available.'); return
        try:
            idx=max(0,min(self.cmb_mic.currentIndex(),len(self._audio_devices)-1)); dev=self._audio_devices[idx]
            fmt=dev.preferredFormat(); self._mic_source=QAudioSource(dev,fmt,self); self._mic_format=fmt
            self._mic_io=self._mic_source.start(); self._mic_io.readyRead.connect(self._read_mic_level)
            self.btn_mic_preview.setText('■ Stop Mic Preview')
        except Exception as e:
            self._stop_mic_source(); self.btn_mic_preview.setChecked(False); QMessageBox.warning(self,'Mic preview',str(e))

    def _stop_mic_source(self):
        try:
            if self._mic_source: self._mic_source.stop()
        except Exception: pass
        self._mic_source=None; self._mic_io=None; self._mic_level=0.0
        try: self.mic_meter.setValue(0)
        except Exception: pass

    def _read_mic_level(self):
        try:
            raw=bytes(self._mic_io.readAll())
            if not raw: return
            sf=self._mic_format.sampleFormat()
            if sf == QAudioFormat.SampleFormat.Float:
                a=np.frombuffer(raw,dtype=np.float32)
                peak=float(np.max(np.abs(a))) if a.size else 0.0
            elif sf == QAudioFormat.SampleFormat.Int16:
                a=np.frombuffer(raw,dtype=np.int16); peak=float(np.max(np.abs(a.astype(np.int32))))/32768.0 if a.size else 0.0
            elif sf == QAudioFormat.SampleFormat.Int32:
                a=np.frombuffer(raw,dtype=np.int32); peak=float(np.max(np.abs(a.astype(np.float64))))/2147483648.0 if a.size else 0.0
            elif sf == QAudioFormat.SampleFormat.UInt8:
                a=np.frombuffer(raw,dtype=np.uint8); peak=float(np.max(np.abs(a.astype(np.int16)-128)))/128.0 if a.size else 0.0
            else: peak=0.0
            self._mic_level=max(0.0,min(1.0,peak))
            fh = getattr(self, '_sw_audio_fh', None)
            if fh is not None and raw:
                try:
                    if sf == QAudioFormat.SampleFormat.Float:
                        pcm = (np.clip(np.frombuffer(raw,dtype=np.float32),-1,1)*32767.0).astype('<i2').tobytes()
                    elif sf == QAudioFormat.SampleFormat.Int16:
                        pcm = raw
                    elif sf == QAudioFormat.SampleFormat.Int32:
                        pcm = (np.frombuffer(raw,dtype=np.int32).astype(np.int64)//65536).astype('<i2').tobytes()
                    elif sf == QAudioFormat.SampleFormat.UInt8:
                        pcm = ((np.frombuffer(raw,dtype=np.uint8).astype(np.int16)-128)<<8).astype('<i2').tobytes()
                    else:
                        pcm = b''
                    if pcm: fh.write(pcm)
                except Exception:
                    pass
        except Exception: pass

    def _update_mic_meter(self):
        # Poll as well as listening to readyRead: some PipeWire/Qt backends do not
        # emit readyRead reliably when the UI hierarchy is reparented or hidden.
        try:
            if self._mic_io is not None and self._mic_io.bytesAvailable() > 0:
                self._read_mic_level()
        except Exception:
            pass
        self.mic_meter.setValue(int(round(self._mic_level*100)))

    # --------------------------- import / record
    def import_video(self, tablet=False):
        start=''
        if tablet:
            start=str(self.cmb_tablet.currentData() or '')
        filt='Video files (*.mp4 *.mov *.mkv *.webm *.avi *.m4v *.mpeg *.mpg);;All files (*)'
        src,_=QFileDialog.getOpenFileName(self,'Import video from tablet/media' if tablet else 'Import video',start,filt)
        if not src: return
        try:
            import groovebox_paths
            dst=groovebox_paths.ingest_file(src,role='recording',project_path=self._project_path())
            self._append_recording_path(dst)
            dur=_probe_duration(dst)
            if dur>0: self.spin_duration.setValue(min(3600.0,dur))
            self.lbl_source.setText('Source: '+dst)
            self.lbl_render.setText('Imported into project recordings: '+os.path.basename(dst))
        except Exception as e: QMessageBox.warning(self,'Import video',str(e))

    def _clear_base_clip(self):
        self.base_clip=''; self.lbl_source.setText('Source: draw-only (black background)')

    def _start_software_recording(self, recdir: str, stamp: str) -> bool:
        """Linux/Fedora fallback: capture QVideoSink frames + mic PCM, encode with bundled FFmpeg.

        This deliberately avoids QMediaRecorder/GStreamer encoders, which may advertise
        formats but still fail with `Could not initialize encoder`.
        """
        if not _ffmpeg() or self._video_sink is None:
            return False
        d = tempfile.mkdtemp(prefix=f'groovebox_camera_{stamp}_', dir=recdir)
        self._sw_record_dir=d; self._sw_frame_index=0; self._sw_last_frame_t=0.0
        self._record_final_path=os.path.join(recdir,f'camera_{stamp}.mp4')
        self._record_path=self._record_final_path
        self._sw_started_mic=False
        try:
            if self._mic_io is None and self._audio_devices:
                mi=max(0,min(self.cmb_mic.currentIndex(),len(self._audio_devices)-1))
                dev=self._audio_devices[mi]; fmt=dev.preferredFormat()
                self._mic_source=QAudioSource(dev,fmt,self); self._mic_format=fmt
                self._mic_io=self._mic_source.start(); self._mic_io.readyRead.connect(self._read_mic_level)
                self._sw_started_mic=True
            if self._mic_io is not None:
                try:
                    self._sw_audio_rate=int(self._mic_format.sampleRate()) or 48000
                    self._sw_audio_channels=max(1,int(self._mic_format.channelCount()))
                except Exception:
                    self._sw_audio_rate=48000; self._sw_audio_channels=1
                self._sw_audio_fh=open(os.path.join(d,'audio.s16le'),'wb')
        except Exception:
            self._sw_audio_fh=None
        self._sw_recording=True
        self.lbl_render.setText('Recording camera + microphone with FFmpeg software fallback…')
        return True

    def _finish_software_recording(self):
        if not getattr(self,'_sw_recording',False) and not getattr(self,'_sw_record_dir',''):
            return
        self._sw_recording=False
        try:
            if self._sw_audio_fh:
                self._sw_audio_fh.flush(); self._sw_audio_fh.close()
        except Exception: pass
        self._sw_audio_fh=None
        if getattr(self,'_sw_started_mic',False):
            try:
                if self._mic_source: self._mic_source.stop()
            except Exception: pass
            self._mic_source=None; self._mic_io=None; self._sw_started_mic=False
        d=str(getattr(self,'_sw_record_dir','') or ''); self._sw_record_dir=''
        final=str(getattr(self,'_record_final_path','') or '')
        n=int(getattr(self,'_sw_frame_index',0)); ff=_ffmpeg()
        if not d or not ff or n < 1:
            self.lbl_render.setText('Camera recording produced no frames.')
            return
        fps=max(1,min(60,int(self.spin_fps.value()) if hasattr(self,'spin_fps') else 24))
        audio=os.path.join(d,'audio.s16le')
        tmp=final+'.part.mp4'
        cmd=[ff,'-y','-v','error','-framerate',str(fps),'-i',os.path.join(d,'frame_%08d.jpg')]
        if os.path.isfile(audio) and os.path.getsize(audio)>0:
            cmd += ['-f','s16le','-ar',str(self._sw_audio_rate),'-ac',str(self._sw_audio_channels),'-i',audio]
        cmd += ['-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p']
        if os.path.isfile(audio) and os.path.getsize(audio)>0:
            cmd += ['-c:a','aac','-b:a','192k','-shortest']
        cmd += ['-movflags','+faststart',tmp]
        try:
            cp=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
            if cp.returncode!=0 or not os.path.isfile(tmp) or os.path.getsize(tmp)<1024:
                raise RuntimeError((cp.stderr or 'FFmpeg software recording failed').strip())
            os.replace(tmp,final)
            try: shutil.rmtree(d,ignore_errors=True)
            except Exception: pass
            try:
                import groovebox_paths; groovebox_paths.index_file(final,'recording',self._project_path())
            except Exception: pass
            self._append_recording_path(final); dur=_probe_duration(final)
            if dur>0: self.spin_duration.setValue(min(3600.0,dur))
            self.lbl_source.setText('Source: '+final); self.lbl_render.setText('Recorded: '+os.path.basename(final))
        except Exception as e:
            self.lbl_render.setText('Software recording failed: '+str(e))
            QMessageBox.warning(self,'Camera recording failed',str(e))
        finally:
            self._record_path=''; self._record_final_path=''

    def _record_format_candidates(self, recdir: str, stamp: str):
        """Return backend-supported live recorder candidates in preference order.

        Qt Multimedia/GStreamer availability differs by Fedora installation.  Never
        assume that choosing a container implies that an encoder for its default
        codecs exists.  Ask QMediaFormat to resolve a real Encode profile, then try
        the supported containers one-by-one.  The final project asset is still MP4;
        non-MP4 live captures are remuxed/transcoded after the recorder is stopped.
        """
        if not QT_MULTIMEDIA or QMediaFormat is None:
            return []
        mode = QMediaFormat.ConversionMode.Encode
        supported = []
        try:
            supported = list(QMediaFormat().supportedFileFormats(mode))
        except Exception:
            pass
        FF = QMediaFormat.FileFormat
        prefs = []
        for enum_name, ext, label in (
            ('MPEG4', '.mp4', 'MP4'),
            ('Matroska', '.mkv', 'Matroska'),
            ('WebM', '.webm', 'WebM'),
            ('QuickTime', '.mov', 'QuickTime'),
        ):
            v = getattr(FF, enum_name, None)
            if v is not None and (not supported or v in supported):
                prefs.append((v, ext, label))
        # Include any backend-advertised formats we did not know by name.
        for v in supported:
            if any(v == x[0] for x in prefs):
                continue
            name = getattr(v, 'name', str(v))
            ext = '.mkv'
            low = str(name).lower()
            if 'mpeg4' in low or low == 'mp4': ext = '.mp4'
            elif 'webm' in low: ext = '.webm'
            elif 'quick' in low or 'mov' in low: ext = '.mov'
            prefs.append((v, ext, str(name)))

        out = []
        for filefmt, ext, label in prefs:
            try:
                fmt = QMediaFormat()
                fmt.setFileFormat(filefmt)
                # Let Qt choose codecs that the active backend can truly encode.
                resolver = getattr(fmt, 'resolveForEncoding', None)
                if callable(resolver):
                    flags_cls = getattr(QMediaFormat, 'ResolveFlags', None)
                    rv = getattr(flags_cls, 'RequiresVideo', None) if flags_cls else None
                    ra = getattr(flags_cls, 'RequiresAudio', None) if flags_cls else None
                    flags = rv
                    if self._audio_devices and rv is not None and ra is not None:
                        try: flags = rv | ra
                        except Exception: flags = rv
                    if flags is not None:
                        resolver(flags)
                try:
                    if not fmt.isSupported(mode):
                        continue
                except Exception:
                    pass
                live = os.path.join(recdir, f'.camera_{stamp}.recording{ext}')
                # If MP4 is directly supported it can still be written to a hidden
                # temporary name; final publication only happens after probe/stability.
                out.append((fmt, live, label))
            except Exception:
                continue
        return out

    def _start_recorder_candidate(self, index: int) -> bool:
        cands = list(getattr(self, '_record_candidates', []) or [])
        if index < 0 or index >= len(cands) or self._capture_session is None:
            return False
        fmt, record_out, label = cands[index]
        try:
            old = getattr(self, '_recorder', None)
            if old is not None:
                try: old.stop()
                except Exception: pass
                try: self._capture_session.setRecorder(None)
                except Exception: pass
            self._recorder = QMediaRecorder(self)
            self._capture_session.setRecorder(self._recorder)
            self._recorder.setMediaFormat(fmt)
            self._recorder_error_text = ''
            self._record_candidate_index = int(index)
            self._record_path = record_out
            try:
                self._recorder.recorderStateChanged.connect(self._on_recorder_state_changed)
            except Exception:
                pass
            try:
                self._recorder.errorOccurred.connect(self._on_recorder_error)
            except Exception:
                try: self._recorder.errorChanged.connect(lambda: self._on_recorder_error())
                except Exception: pass
            try:
                if os.path.isfile(record_out): os.remove(record_out)
            except Exception:
                pass
            self._recorder.setOutputLocation(QUrl.fromLocalFile(record_out))
            self._recorder.record()
            self.lbl_render.setText(f'Recording selected camera + microphone… encoder profile: {label}')
            QTimer.singleShot(1200, self._verify_recorder_started)
            return True
        except Exception as e:
            self._recorder_error_text = str(e)
            return False

    def _try_next_recorder_candidate(self, failure_text: str = '') -> bool:
        cands = list(getattr(self, '_record_candidates', []) or [])
        start = int(getattr(self, '_record_candidate_index', -1)) + 1
        for i in range(start, len(cands)):
            try:
                oldpath = str(getattr(self, '_record_path', '') or '')
                if oldpath and os.path.isfile(oldpath) and os.path.getsize(oldpath) == 0:
                    os.remove(oldpath)
            except Exception:
                pass
            if self._start_recorder_candidate(i):
                self.lbl_render.setText(
                    f'Previous camera encoder was unavailable; trying backend profile {i+1}/{len(cands)}…')
                return True
        return False

    def _toggle_record(self,on:bool):
        if not on:
            self._stop_recording(); return
        if not QT_MULTIMEDIA or not self._camera_devices:
            self.btn_record.setChecked(False); QMessageBox.information(self,'Record','Qt Multimedia camera support is unavailable.'); return
        try:
            # Keep the selected camera visible while recording.
            if self._camera is None or self._capture_session is None:
                idx=max(0,min(self.cmb_camera.currentIndex(),len(self._camera_devices)-1))
                self._capture_session=QMediaCaptureSession(self); self._camera=QCamera(self._camera_devices[idx],self)
                self._capture_session.setCamera(self._camera)
                if self._video_sink is not None:
                    self._capture_session.setVideoOutput(self._video_sink)
                self._camera.start()
            self._record_audio_input=None
            if self._audio_devices:
                mi=max(0,min(self.cmb_mic.currentIndex(),len(self._audio_devices)-1))
                self._record_audio_input=QAudioInput(self._audio_devices[mi],self); self._capture_session.setAudioInput(self._record_audio_input)

            stamp=time.strftime('%Y%m%d_%H%M%S')
            recdir=self._recordings_dir(); os.makedirs(recdir, exist_ok=True)
            self._record_final_path=os.path.join(recdir,f'camera_{stamp}.mp4')
            self._record_container='auto'
            self._record_finalize_attempts=0
            self._record_last_size=-1
            self._record_stable_size_count=0
            # Fedora/Linux: bypass fragile Qt/GStreamer encode plugins and use the
            # bundled FFmpeg encoder while Qt continues to provide camera frames.
            if sys.platform.startswith('linux') and self._start_software_recording(recdir, stamp):
                self.btn_record.setText('■ Stop Recording')
                return
            self._record_candidates=self._record_format_candidates(recdir, stamp)
            self._record_candidate_index=-1
            if not self._record_candidates:
                raise RuntimeError(
                    'Qt Multimedia reports no usable video-encoding profile. '
                    'Install/enable the Fedora GStreamer codec plugins or use Import Video until a backend encoder is available.')
            if not self._try_next_recorder_candidate('initial encoder selection'):
                raise RuntimeError('Could not initialize any camera encoder advertised by Qt Multimedia.')
            self.btn_record.setText('■ Stop Recording')
        except Exception as e:
            self.btn_record.blockSignals(True); self.btn_record.setChecked(False); self.btn_record.blockSignals(False)
            self.btn_record.setText('● Record Camera + Mic')
            QMessageBox.warning(self,'Record',str(e))

    def _on_recorder_error(self, *args):
        try:
            self._recorder_error_text = str(self._recorder.errorString() or 'Qt Multimedia recorder error') if self._recorder else 'Qt Multimedia recorder error'
        except Exception:
            self._recorder_error_text = 'Qt Multimedia recorder error'

    def _verify_recorder_started(self):
        """Do not silently continue when Qt created a zero-byte placeholder but never started encoding."""
        if not self._recorder or not self.btn_record.isChecked():
            return
        try:
            state=self._recorder.recorderState()
            active=(state == QMediaRecorder.RecorderState.RecordingState)
        except Exception:
            active=True
        if active and not self._recorder_error_text:
            return
        msg=self._recorder_error_text or 'The Qt camera recorder did not enter RecordingState.'
        try: self._recorder.stop()
        except Exception: pass
        # Qt/GStreamer can advertise a container whose default encoder plugin is
        # missing. Retry every backend-supported resolved profile before failing.
        if self._try_next_recorder_candidate(msg):
            return
        try:
            if self._record_path and os.path.isfile(self._record_path) and os.path.getsize(self._record_path) == 0:
                os.remove(self._record_path)
        except Exception: pass
        self.btn_record.blockSignals(True); self.btn_record.setChecked(False); self.btn_record.blockSignals(False)
        self.btn_record.setText('● Record Camera + Mic')
        self.lbl_render.setText('Camera recording could not start: '+msg)
        QMessageBox.warning(self,'Camera recording could not start',
            msg+'\n\nGroovebox tried every encoding profile Qt reports as available on this system.')

    def _finalize_recording_to_mp4(self, src: str) -> str:
        """Return a verified MP4 path; never publish a zero-byte placeholder."""
        final=str(getattr(self,'_record_final_path','') or src)
        if not src or not os.path.isfile(src) or os.path.getsize(src) < 1024:
            return ''
        if os.path.abspath(src) == os.path.abspath(final):
            return src if self._recording_container_ready(src) else ''
        ff=_ffmpeg()
        if not ff:
            return ''
        tmp=final+'.part.mp4'
        for cmd in (
            [ff,'-y','-v','error','-i',src,'-map','0:v:0','-map','0:a?','-c','copy','-movflags','+faststart',tmp],
            [ff,'-y','-v','error','-i',src,'-map','0:v:0','-map','0:a?','-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',tmp],
        ):
            try:
                cp=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
                if cp.returncode==0 and os.path.isfile(tmp) and os.path.getsize(tmp)>1024:
                    os.replace(tmp,final)
                    try: os.remove(src)
                    except Exception: pass
                    return final if self._recording_container_ready(final) else ''
            except Exception:
                pass
            try:
                if os.path.isfile(tmp): os.remove(tmp)
            except Exception: pass
        return ''

    def _stop_recording(self):
        if getattr(self, '_sw_recording', False):
            self.lbl_render.setText('Finalizing camera recording…')
            self.btn_record.setText('● Record Camera + Mic')
            QTimer.singleShot(10, self._finish_software_recording)
            return
        try:
            if self._recorder:
                self.lbl_render.setText('Finalizing camera recording…')
                self._recorder.stop()
            else:
                self._schedule_record_finalize_check()
        except Exception:
            self._schedule_record_finalize_check()
        self.btn_record.setText('● Record Camera + Mic')

    def _on_recorder_state_changed(self, state):
        """Finalize only after QMediaRecorder confirms the backend is stopped."""
        try:
            stopped = (state == QMediaRecorder.RecorderState.StoppedState)
        except Exception:
            stopped = ('Stopped' in str(state))
        if stopped and self._record_path:
            self._schedule_record_finalize_check()

    def _schedule_record_finalize_check(self):
        if self._record_path:
            QTimer.singleShot(250, self._finish_recording)

    def _recording_container_ready(self, path: str) -> bool:
        """Return True only after the recorded container is parseable and stable.

        MP4 writes their index (`moov`) during finalization.  Merely seeing a file on
        disk is not enough; require a successful media probe and a stable non-trivial
        size before publishing it to Groovebox.
        """
        if not path or not os.path.isfile(path):
            return False
        try:
            size = os.path.getsize(path)
        except Exception:
            return False
        if size < 1024:
            return False
        last = int(getattr(self, '_record_last_size', -1))
        if size == last:
            self._record_stable_size_count = int(getattr(self, '_record_stable_size_count', 0)) + 1
        else:
            self._record_stable_size_count = 0
            self._record_last_size = size
        probe = _ffprobe()
        if probe:
            try:
                cp = subprocess.run(
                    [probe, '-v', 'error', '-show_entries', 'format=format_name,duration',
                     '-of', 'default=nk=1:nw=1', path],
                    capture_output=True, text=True, timeout=4,
                )
                if cp.returncode != 0:
                    return False
            except Exception:
                return False
        # Two equal-size observations prevent racing a backend that has created the
        # moov atom but is still completing the final filesystem write.
        return int(getattr(self, '_record_stable_size_count', 0)) >= 1

    def _finish_recording(self):
        path=self._record_path
        # Qt backends can choose a sibling extension; prefer reported actual location.
        try:
            if self._recorder:
                loc=self._recorder.actualLocation()
                if loc and loc.isLocalFile() and os.path.isfile(loc.toLocalFile()):
                    path=loc.toLocalFile()
                    self._record_path=path
        except Exception:
            pass

        attempts = int(getattr(self, '_record_finalize_attempts', 0)) + 1
        self._record_finalize_attempts = attempts
        if not self._recording_container_ready(path):
            # Give slow camera/GStreamer backends ample opportunity to close the MP4.
            # Do not index, probe, render, or hand the half-written file to FFmpeg.
            if attempts < 40:
                self.lbl_render.setText('Finalizing camera recording…')
                QTimer.singleShot(250, self._finish_recording)
                return
            self.lbl_render.setText('Recording did not finalize into a readable video container.')
            QMessageBox.warning(
                self, 'Recording finalize failed',
                'The camera backend stopped, but the video container is still not readable. '
                'The incomplete file was left in the project recordings folder for inspection; '
                'it was not loaded into the project.'
            )
            try:
                if path and os.path.isfile(path) and os.path.getsize(path) == 0:
                    os.remove(path)
            except Exception: pass
            self._record_path=''
            self._record_final_path=''
            self._recorder=None; self._record_audio_input=None
            return

        path=self._finalize_recording_to_mp4(path)
        self._record_path=''
        self._record_final_path=''
        if path and os.path.isfile(path):
            try:
                import groovebox_paths; groovebox_paths.index_file(path,'recording',self._project_path())
            except Exception: pass
            self._append_recording_path(path); d=_probe_duration(path)
            if d>0:self.spin_duration.setValue(min(3600.0,d))
            self.lbl_source.setText('Source: '+path); self.lbl_render.setText('Recorded: '+os.path.basename(path))
        self._recorder=None; self._record_audio_input=None

    # --------------------------- paint / graph state
    def _set_color_button(self):
        c=self.canvas.color if hasattr(self,'canvas') else QColor('#ffcc33')
        self.btn_color.setStyleSheet(f'background:{c.name()}; color:{"#000" if c.lightness()>150 else "#fff"}; font-weight:800;')

    def _choose_color(self):
        c=QColorDialog.getColor(self.canvas.color,self,'Paint color')
        if c.isValid(): self.canvas.set_color(c); self._set_color_button()

    def _neutral_for_target(self,target:str)->float:
        if target=='Layer Opacity': return 1.0
        if target=='Drawn Sound Gain': return 0.5
        if target=='Sound→Color Amount': return 0.5
        return 0.5

    def _capture_curve(self):
        self._curves[self._current_curve_target]=list(self.graph.values)

    def _switch_curve(self,target:str):
        self._capture_curve(); self._current_curve_target=str(target)
        vals=self._curves.get(self._current_curve_target)
        if vals is None: vals=[self._neutral_for_target(target)]*128; self._curves[self._current_curve_target]=list(vals)
        self.graph.set_values(vals)

    def _reset_curve(self):
        v=self._neutral_for_target(self.cmb_graph_target.currentText() if hasattr(self,'cmb_graph_target') else 'Layer Opacity')
        self.graph.reset(v); self._capture_curve()

    def _curve(self,target:str,t01:float,default:float)->float:
        vals=self._curves.get(target)
        if not vals: return default
        x=max(0.0,min(1.0,float(t01)))*(len(vals)-1); i=int(x); f=x-i
        if i>=len(vals)-1:return float(vals[-1])
        return float(vals[i]*(1-f)+vals[i+1]*f)

    def _persist_layer(self,silent=True):
        try:
            self._capture_curve(); d=Path(self._layers_dir()); d.mkdir(parents=True,exist_ok=True)
            png=d/'video_clip_paint.png'; js=d/'video_clip_graph.json'
            self.canvas.image.save(str(png),'PNG')
            draw_meta=[]
            for i,(rec,canvas) in enumerate(zip(self.draw_layers,self.draw_canvases)):
                lp=d/f'video_clip_paint_{i:02d}.png'; canvas.image.save(str(lp),'PNG'); draw_meta.append(dict(rec,image=str(lp)))
                try: groovebox_paths.index_file(str(lp),'layer',self._project_path())
                except Exception: pass
            data={'version':2,'base_clip':self.base_clip,'curves':self._curves,'drawing_layers':draw_meta,'recording_layers':list(self.recording_layers),'color_sound':self.chk_color_sound.isChecked(),'sound_color':self.chk_sound_color.isChecked(),'draw_sound':self.chk_draw_sound.isChecked(),'color_detail':self.cmb_color_detail.currentText()}
            js.write_text(json.dumps(data,indent=2),encoding='utf-8')
            import groovebox_paths; groovebox_paths.index_file(str(png),'layer',self._project_path()); groovebox_paths.index_file(str(js),'layer',self._project_path())
            if not silent:self.lbl_render.setText('Saved paint + graph layer in project layers/.')
            return str(png),str(js)
        except Exception as e:
            if not silent: QMessageBox.warning(self,'Save layer',str(e))
            return '',''

    def export_state(self)->Dict[str,Any]:
        png,js=self._persist_layer(True)
        draw_state=[dict(r) for r in self.draw_layers]
        try:
            saved=json.loads(Path(js).read_text(encoding='utf-8')) if js and os.path.isfile(js) else {}
            if isinstance(saved.get('drawing_layers'),list):draw_state=saved['drawing_layers']
        except Exception:pass
        return {'version':3,'base_clip':self.base_clip,'paint_layer':png,'graph_state':js,'camera':self.cmb_camera.currentText(),'microphone':self.cmb_mic.currentText(),'tablet_source':self.cmb_tablet.currentData() or '','duration':float(self.spin_duration.value()),'fps':int(self.spin_fps.value()),'width':int(self.spin_width.value()),'height':int(self.spin_height.value()),'draw_sound':self.chk_draw_sound.isChecked(),'color_sound':self.chk_color_sound.isChecked(),'sound_color':self.chk_sound_color.isChecked(),'color_detail':self.cmb_color_detail.currentText(),'bind_all_mode':self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Video','last_rendered_video':self.last_rendered_video,'recording_layers':list(self.recording_layers),'drawing_layers':draw_state}

    def restore_state(self,state:Dict[str,Any]):
        if not isinstance(state,dict):return
        self.base_clip=str(state.get('base_clip') or '')
        if self.base_clip:self.lbl_source.setText('Source: '+self.base_clip)
        for combo,key in ((self.cmb_camera,'camera'),(self.cmb_mic,'microphone')):
            text=str(state.get(key) or ''); idx=combo.findText(text)
            if idx>=0:combo.setCurrentIndex(idx)
        tpath=str(state.get('tablet_source') or '')
        if tpath:
            for i in range(self.cmb_tablet.count()):
                if str(self.cmb_tablet.itemData(i) or '')==tpath:self.cmb_tablet.setCurrentIndex(i);break
        self.spin_duration.setValue(max(.25,min(3600,float(state.get('duration',5.0)))))
        self.spin_fps.setValue(max(1,min(120,int(state.get('fps',30)))))
        self.spin_width.setValue(max(160,min(3840,int(state.get('width',1280)))))
        self.spin_height.setValue(max(90,min(2160,int(state.get('height',720)))))
        self.chk_draw_sound.setChecked(bool(state.get('draw_sound',False))); self.chk_color_sound.setChecked(bool(state.get('color_sound',False))); self.chk_sound_color.setChecked(bool(state.get('sound_color',False)))
        detail=str(state.get('color_detail') or 'Off'); self.cmb_color_detail.setCurrentText(detail if detail in ('Off','Basic','Detailed') else 'Off')
        mode=str(state.get('bind_all_mode') or 'Video')
        if hasattr(self,'cmb_bind_all') and mode in ('Video','Audio','Both','Unbound'):self.cmb_bind_all.setCurrentText(mode)
        self.last_rendered_video=str(state.get('last_rendered_video') or '')
        for rp in state.get('recording_layers',[]) or []:
            if isinstance(rp,str) and os.path.isfile(rp):self._append_recording_path(rp)
        saved_draw=state.get('drawing_layers',[]) or []
        if saved_draw:
            while self.draw_tabs.count():self.draw_tabs.removeTab(0)
            self.draw_layers=[]; self.draw_canvases=[]
            for rec in saved_draw:
                if not isinstance(rec,dict):continue
                c=PaintCanvas(); ip=str(rec.get('image') or '')
                if ip and os.path.isfile(ip):
                    im=QImage(ip)
                    if not im.isNull():c.image=im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                rr={k:rec.get(k) for k in ('name','start','end','fade')}; rr['name']=str(rr.get('name') or f'Drawing {len(self.draw_layers)+1}')
                self.draw_layers.append(rr); self.draw_canvases.append(c); self.draw_tabs.addTab(c,rr['name'])
            if self.draw_layers:self.draw_tabs.setCurrentIndex(0); self._draw_tab_changed(0)
        png=str(state.get('paint_layer') or ''); js=str(state.get('graph_state') or '')
        try:
            if png and os.path.isfile(png):
                im=QImage(png)
                if not im.isNull():self.canvas.image=im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied);self.canvas.update()
            if js and os.path.isfile(js):
                data=json.loads(Path(js).read_text(encoding='utf-8')); curves=data.get('curves')
                if isinstance(curves,dict):self._curves={str(k):[float(v) for v in vals] for k,vals in curves.items() if isinstance(vals,list)}
                self._switch_curve(self.cmb_graph_target.currentText())
        except Exception:pass

    def _save_host_state(self):
        try:
            state=getattr(self.host,'media_workbench_state',None)
            if not isinstance(state,dict):state={};setattr(self.host,'media_workbench_state',state)
            state['video_clip_studio']=self.export_state()
        except Exception:pass

    def _selected_instrument_name(self):
        h=self.host
        try:
            if h is not None and hasattr(h,'_current_instrument_name'):return str(h._current_instrument_name())
        except Exception:pass
        try:
            c=getattr(h,'instrument_selector_dropdown',None)
            if c is not None:return str(c.currentText())
        except Exception:pass
        return 'selected'

    def _bind_all_layers_to_instrument(self):
        mode=self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Video'
        name=self._selected_instrument_name(); h=self.host
        store=getattr(h,'instrument_media_samples',None)
        if not isinstance(store,dict):store={};setattr(h,'instrument_media_samples',store)
        if mode=='Unbound':
            rec=store.get(name)
            if isinstance(rec,dict) and rec.get('binding_source')=='video_clip_studio_all_layers':store.pop(name,None)
            self._save_host_state(); self.lbl_render.setText(f'Unbound Video Clip Studio layers from {name}.'); return
        video=str(self.last_rendered_video or '')
        if not video or not os.path.isfile(video):
            auto_name=_safe_stem(name or 'selected_operator')+'_all_layers_bound.mp4'
            auto_path=os.path.join(self._video_exports_dir(), auto_name)
            self.lbl_render.setText('Materializing editable layers for selected operator…')
            video=str(self.render_video(output_path=auto_path, quiet=True) or '')
            if not video or not os.path.isfile(video):
                QMessageBox.warning(self,'Bind All Layers','Could not materialize the current recording/drawing layers for the selected operator. See the render status for details.')
                return
        arr=np.zeros(1,dtype=np.float32); sr=44100; has_audio=False
        if mode in ('Audio','Both'):
            try:
                if h is not None and hasattr(h,'_decode_media_audio'):
                    arr,sr=h._decode_media_audio(video); has_audio=bool(np.asarray(arr).size)
                else:
                    raise RuntimeError('host media decoder unavailable')
            except Exception as e:
                if mode=='Audio':QMessageBox.warning(self,'Bind All Layers',f'The rendered video has no decodable audio to bind: {e}'); return
        # Video-only bindings retain a tiny silent runtime waveform; project restore
        # preserves the video path even when the container has no audio stream.
        path=video if mode in ('Video','Both') else video
        store[name]={'path':path,'sample_rate':int(sr),'waveform':np.asarray(arr,dtype=np.float32).reshape(-1),'user_owned':True,'source_kind':'video' if mode in ('Video','Both') else 'audio','video_path':video if mode in ('Video','Both') else '','video_input_enabled':mode in ('Video','Both'),'layered_state':self.export_state(),'binding_mode':mode.lower(),'binding_source':'video_clip_studio_all_layers','bound_layers_state':self.export_state(),'audio_present':bool(has_audio)}
        self._save_host_state(); self.lbl_render.setText(f'Bound ALL video/draw layers → {name} as {mode}.')
        try:
            if hasattr(h,'_refresh_operator_sample_ui'):h._refresh_operator_sample_ui()
            if hasattr(h,'_on_live_source_changed'):h._on_live_source_changed()
        except Exception:pass


    def _bind_all_layers_to_carrier(self):
        mode=self.cmb_bind_all.currentText() if hasattr(self,'cmb_bind_all') else 'Both'
        h=self.host
        if mode=='Unbound':
            setattr(h,'carrier_binding_source',''); setattr(h,'carrier_binding_mode','unbound'); setattr(h,'carrier_bound_layers_state',{})
            self._save_host_state(); self.lbl_render.setText('Unbound video/draw layers from carrier provenance. Current carrier media is left intact.'); return
        video=str(getattr(self,'last_render_path','') or getattr(self,'_last_render_path','') or self.last_rendered_video or '')
        if not video or not os.path.isfile(video):
            auto_path=os.path.join(self._video_exports_dir(), 'carrier_all_layers_bound.mp4')
            self.lbl_render.setText('Materializing editable layers for carrier…')
            video=str(self.render_video(output_path=auto_path, quiet=True) or '')
            if not video or not os.path.isfile(video):
                QMessageBox.warning(self,'Bind All Layers to Carrier','Could not materialize the current recording/drawing layers for the carrier. See the render status for details.')
                return
        old_audio=(getattr(h,'imported_waveform',None),getattr(h,'imported_sample_rate',44100),str(getattr(h,'imported_wav_path','') or ''))
        old_video=(str(getattr(h,'imported_video_path','') or ''),getattr(h,'imported_video_meta',{}) or {})
        if mode=='Both':
            h._load_video_path(video)
        elif mode=='Video':
            h._load_video_path(video)
            # Keep the prior audio carrier while replacing only the visual carrier.
            if old_audio[0] is not None:
                h.imported_waveform=old_audio[0]; h.imported_sample_rate=old_audio[1]; h.imported_wav_path=old_audio[2]
        elif mode=='Audio':
            # Decode this render as audio carrier while retaining the prior visual carrier.
            arr,sr=h._decode_media_audio(video)
            arr=np.asarray(arr,dtype=np.float32).reshape(-1)
            h.imported_waveform=arr; h.imported_sample_rate=int(sr); h.imported_wav_path=video
            h.imported_video_path=old_video[0]; h.imported_video_meta=old_video[1]
            try: h._refresh_after_file_input(reason='video_render_audio_carrier')
            except Exception: pass
        setattr(h,'carrier_binding_source','video_clip_studio_all_layers')
        setattr(h,'carrier_binding_mode',mode.lower())
        setattr(h,'carrier_bound_layers_state',self.export_state())
        self._save_host_state(); self.lbl_render.setText(f'Bound ALL video/draw layers → Carrier {mode}: {os.path.basename(video)}')

    # --------------------------- translation + render
    def _paint_color_regions(self,detail:str)->List[Tuple[float,float,float]]:
        im=self.canvas.image.scaled(48,27,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGBA8888)
        ptr=im.bits(); ptr.setsize(im.sizeInBytes()); a=np.frombuffer(ptr,dtype=np.uint8).reshape(im.height(),im.width(),4)
        alpha=a[:,:,3].astype(np.float64)/255.0
        if float(alpha.sum())<1e-9:return []
        def region_stats(block):
            aa=block[:,:,3].astype(np.float64)/255.0; denom=max(1e-9,float(aa.sum())); rgb=(block[:,:,:3].astype(np.float64)*aa[:,:,None]).sum(axis=(0,1))/denom
            c=QColor(int(rgb[0]),int(rgb[1]),int(rgb[2])); h,s,v,_=c.getHsvF(); return (0.0 if h<0 else h,s,v)
        if detail!='Detailed':return [region_stats(a)]
        out=[]
        for yy in np.array_split(np.arange(im.height()),3):
            for xx in np.array_split(np.arange(im.width()),4):
                b=a[np.ix_(yy,xx)]
                if b[:,:,3].sum()>0:out.append(region_stats(b))
        return out[:12]

    def _extract_audio_envelope(self,path:str,duration:float,fps:int)->np.ndarray:
        n=max(1,int(round(duration*fps))); out=np.zeros(n,dtype=np.float64); ff=_ffmpeg()
        if not ff or not path or not os.path.isfile(path) or not _probe_has_audio(path):return out
        try:
            cp=subprocess.run([ff,'-v','error','-t',f'{duration:.6f}','-i',path,'-vn','-ac','1','-ar',str(max(100,fps*4)),'-f','f32le','pipe:1'],capture_output=True,timeout=max(15,int(duration)+10))
            x=np.frombuffer(cp.stdout,dtype=np.float32).astype(np.float64)
            if not x.size:return out
            sr=max(100,fps*4); chunk=max(1,int(sr/fps))
            vals=[]
            for i in range(n):
                seg=x[i*chunk:min(x.size,(i+1)*chunk)]
                vals.append(float(np.sqrt(np.mean(seg*seg))) if seg.size else 0.0)
            out=np.asarray(vals,dtype=np.float64); mx=float(out.max()) if out.size else 0.0
            if mx>1e-12:out/=mx
        except Exception:pass
        return out

    def _generate_sound(self,path:str,duration:float,sr=48000)->bool:
        detail=self.cmb_color_detail.currentText()
        use_color=self.chk_color_sound.isChecked() and detail!='Off'
        use_draw=self.chk_draw_sound.isChecked()
        if not (use_color or use_draw):return False
        n=max(1,int(round(duration*sr))); t=np.arange(n,dtype=np.float64)/float(sr); u=np.linspace(0,1,n,endpoint=False)
        pitch_curve=np.interp(u,np.linspace(0,1,128),np.asarray(self._curves.get('Drawn Sound Pitch',[.5]*128),dtype=np.float64))
        gain_curve=np.interp(u,np.linspace(0,1,128),np.asarray(self._curves.get('Drawn Sound Gain',[.5]*128),dtype=np.float64))
        y=np.zeros(n,dtype=np.float64)
        if use_draw:
            freq=220.0*np.power(2.0,2.0*(pitch_curve-.5)); phase=2*np.pi*np.cumsum(freq)/sr; y += np.sin(phase)*(0.24*gain_curve)
        if use_color:
            regs=self._paint_color_regions(detail)
            if regs:
                color_gain=0.16/max(1,math.sqrt(len(regs)))
                for j,(h,s,v) in enumerate(regs):
                    base=110.0*pow(2.0,4.0*h); freq=base*np.power(2.0,1.0*(pitch_curve-.5)); phase=2*np.pi*np.cumsum(freq)/sr + j*0.37
                    amp=color_gain*(0.15+0.85*s)*(0.2+0.8*v)*(0.35+0.65*gain_curve)
                    y += np.sin(phase)*amp
                    if detail=='Detailed': y += np.sin(phase*2.0+0.13*j)*(amp*0.23)
        # No normalization/limiting. Keep synthesis coefficients conservative; final master behavior is external.
        # Coefficients above are bounded below full scale, so integer conversion needs no extra limiter/clip.
        pcm=np.asarray(y*32767.0,dtype=np.int16)
        with wave.open(path,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(pcm.tobytes())
        return True

    def _render_frame(self,w:int,h:int,t01:float,sound_amp:float,transparent:bool)->QImage:
        frame=QImage(w,h,QImage.Format.Format_ARGB32_Premultiplied)
        frame.fill(Qt.GlobalColor.transparent if transparent else QColor(0,0,0))
        opacity=self._curve('Layer Opacity',t01,1.0)
        xcurve=self._curve('Layer X',t01,.5); ycurve=self._curve('Layer Y',t01,.5); sc=self._curve('Layer Scale',t01,.5); rot=self._curve('Layer Rotation',t01,.5)
        scale=0.25 + sc*1.75; angle=(rot-.5)*720.0; dx=(xcurve-.5)*w; dy=(ycurve-.5)*h
        q=QPainter(frame); q.setRenderHint(QPainter.RenderHint.Antialiasing,True); q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True)
        tsec=t01*float(self.spin_duration.value())
        pairs=list(zip(self.draw_layers,self.draw_canvases)) or [({'start':0,'end':1e9,'fade':0},self.canvas)]
        for rec,canvas in pairs:
            tg=self._draw_layer_time_gain(rec,tsec)
            if tg<=0:continue
            layer=canvas.image.scaled(w,h,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
            q.setOpacity(max(0,min(1,opacity*tg))); q.save(); q.translate(w/2+dx,h/2+dy); q.rotate(angle); q.scale(scale,scale); q.translate(-w/2,-h/2); q.drawImage(0,0,layer); q.restore()
        q.resetTransform(); q.setOpacity(1.0)
        if self.chk_sound_color.isChecked() and sound_amp>0:
            amt=self._curve('Sound→Color Amount',t01,.5)*sound_amp
            c=QColor.fromHsvF((0.02+0.80*sound_amp)%1.0,0.75,0.9,max(0.0,min(.65,amt*.65)))
            q.fillRect(frame.rect(),c)
        q.end(); return frame

    def render_video(self, output_path=None, quiet=False):
        ff=_ffmpeg()
        if not ff: QMessageBox.warning(self,'Render video','FFmpeg is not available in the local Groovebox bin/PATH.'); return
        self._capture_curve(); self._persist_layer(True)
        duration=float(self.spin_duration.value()); fps=int(self.spin_fps.value()); w=int(self.spin_width.value()); h=int(self.spin_height.value())

        # RECORDING_LAYER_RENDER_2026: every appended recording layer participates
        # in the render. Older builds only switched base_clip, so the layer tabs were
        # state/UI without true multi-layer composition.
        video_layers=[]
        for candidate in list(self.recording_layers) + ([self.base_clip] if self.base_clip else []):
            candidate=os.path.abspath(str(candidate or ''))
            if candidate and os.path.isfile(candidate) and candidate not in video_layers:
                video_layers.append(candidate)

        default=os.path.join(self._video_exports_dir(),_safe_stem(Path(video_layers[0]).stem if video_layers else 'drawn_video')+'_mixed.mp4')
        if output_path:
            out=os.path.abspath(str(output_path))
            os.makedirs(os.path.dirname(out), exist_ok=True)
        else:
            out,_=QFileDialog.getSaveFileName(self,'Render / Mix Video Clip',default,'MP4 video (*.mp4);;WebM video (*.webm)')
            if not out:return None
        if not os.path.splitext(out)[1]:out += '.mp4'
        tmp=Path(self._layers_dir())/'_video_clip_render_tmp'; shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True,exist_ok=True)
        try:
            n=max(1,int(math.ceil(duration*fps)))
            envelope_source = self.base_clip if self.base_clip and os.path.isfile(self.base_clip) else (video_layers[0] if video_layers else '')
            env=self._extract_audio_envelope(envelope_source,duration,fps) if self.chk_sound_color.isChecked() else np.zeros(n)
            transparent=bool(video_layers)
            self.lbl_render.setText(f'Rendering {n} paint/graph frame(s) over {len(video_layers)} recording layer(s)…'); self.repaint()
            for i in range(n):
                fr=self._render_frame(w,h,i/max(1,n-1),float(env[min(i,len(env)-1)]) if len(env) else 0.0,transparent)
                fr.save(str(tmp/f'frame_{i:06d}.png'),'PNG')
            sound=str(tmp/'drawn_sound.wav'); has_generated=self._generate_sound(sound,duration)
            seq=str(tmp/'frame_%06d.png'); ext=Path(out).suffix.lower(); codec='libvpx-vp9' if ext=='.webm' else 'libx264'
            cmd=[ff,'-y']
            for src in video_layers:
                cmd += ['-i',src]
            paint_idx=len(video_layers)
            cmd += ['-framerate',str(fps),'-i',seq]
            sound_idx=paint_idx+1
            if has_generated: cmd += ['-i',sound]

            filters=[]
            if video_layers:
                # Fit each recording to the target frame and hold its last frame to
                # the requested project duration. Blend incrementally with weights
                # chosen so N layers contribute equally rather than hiding each other.
                for j in range(len(video_layers)):
                    filters.append(
                        f'[{j}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,'
                        f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,'
                        f'tpad=stop_mode=clone:stop_duration={duration:.6f},trim=duration={duration:.6f},setpts=PTS-STARTPTS[rv{j}]')
                comp='rv0'
                for j in range(1,len(video_layers)):
                    k=j+1; outtag=f'rmix{j}'
                    filters.append(f'[{comp}][rv{j}]blend=all_expr=\'A*{k-1}/{k}+B/{k}\':shortest=1[{outtag}]')
                    comp=outtag
                filters.append(f'[{comp}][{paint_idx}:v]overlay=0:0:shortest=1[v]')
            else:
                filters.append(f'[{paint_idx}:v]format=rgba[v]')

            audio_refs=[]
            for j,src in enumerate(video_layers):
                if _probe_has_audio(src):
                    filters.append(f'[{j}:a]apad=whole_dur={duration:.6f},atrim=duration={duration:.6f},asetpts=PTS-STARTPTS[ra{j}]')
                    audio_refs.append(f'[ra{j}]')
            if has_generated:
                filters.append(f'[{sound_idx}:a]apad=whole_dur={duration:.6f},atrim=duration={duration:.6f},asetpts=PTS-STARTPTS[rgen]')
                audio_refs.append('[rgen]')
            audio_map=None
            if len(audio_refs)>1:
                filters.append(''.join(audio_refs)+f'amix=inputs={len(audio_refs)}:normalize=0:dropout_transition=0[a]')
                audio_map='[a]'
            elif len(audio_refs)==1:
                audio_map=audio_refs[0]

            cmd += ['-filter_complex',';'.join(filters),'-map','[v]']
            if audio_map: cmd += ['-map',audio_map]
            cmd += ['-t',f'{duration:.6f}','-r',str(fps),'-c:v',codec]
            if codec=='libx264':cmd += ['-pix_fmt','yuv420p','-crf','18','-preset','veryfast']
            else:cmd += ['-pix_fmt','yuv420p','-b:v','0','-crf','30']
            if audio_map: cmd += ['-c:a','aac' if ext!='.webm' else 'libopus','-b:a','192k']
            cmd += [out]
            cp=subprocess.run(cmd,capture_output=True,text=True,timeout=max(60,int(duration*8)+30))
            if cp.returncode!=0: raise RuntimeError((cp.stderr or cp.stdout or 'FFmpeg failed')[-5000:])
            try:
                import groovebox_paths; groovebox_paths.index_file(out,'video_export',self._project_path())
            except Exception:pass
            self.last_rendered_video=str(out)
            self.last_render_path=str(out)
            self._last_render_path=str(out)
            self._save_host_state()
            self.lbl_render.setText(f'Rendered {len(video_layers)} recording layer(s): '+out)
            try:
                if hasattr(self.parent(),'refresh'):self.parent().refresh()
            except Exception:pass
            return str(out)
        except Exception as e:
            if not quiet: QMessageBox.warning(self,'Render video',str(e))
            self.lbl_render.setText('Render failed: '+str(e))
            return None
        finally: shutil.rmtree(tmp,ignore_errors=True)

