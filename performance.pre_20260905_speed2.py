#!/usr/bin/env python3
"""
performance.py — Groovebox Performance workspace and device manager.

Provides an in-app:
  • Project + render file browser (browse / rename / delete / open)
  • Media playlister (queue WAV/MP3/FLAC/OGG/OPUS/MP4/WEBM/AVI)
  • Built-in game player (live composition game + packaged .zip games)
  • Parametric live remixer (drives host LiveDJ GOAVA / RAND PARAM amounts)
  • Batch re-render from linked project provenance (scale FPS / audio bitrate)

Designed for low-power ARM (Pi 4/5): short previews, subprocess players,
and quality controls that default conservative.
"""
from __future__ import annotations

import ast
import json
import math
import os
import random
import re
import socket
import time
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

AUDIO_EXT = {".wav", ".flac", ".mp3", ".ogg", ".opus", ".aiff", ".aif", ".caf"}
VIDEO_EXT = {".mp4", ".webm", ".avi", ".mov", ".mkv"}
PROJECT_EXT = {".mgpr"}
GAME_EXT = {".zip"}
MEDIA_EXT = AUDIO_EXT | VIDEO_EXT

# Fine-grained stream classification, distinct from the AUDIO_EXT/VIDEO_EXT
# extension buckets above: a .mp4/.mkv/etc. container can hold audio-only,
# video-only (silent), or both — the extension alone can't tell you which.
KIND_AUDIO = "audio"        # audio file, or audio-only container: no video track
KIND_VIDEO = "video"        # video container with NO audio track ("audioless video")
KIND_AV = "av"              # video container WITH an audio track ("both")
KIND_UNKNOWN = "unknown"    # couldn't probe (no ffprobe, or read error)
KIND_PENDING = "pending"    # probe queued/in flight; always shown regardless of filter


class _PerformanceMathBackground(QWidget):
    """Very light deterministic ParametricMathBackground for Performance.

    Paint cost is intentionally tiny: a sparse Meum/phi lattice with two curves.
    It never consumes host/game state and therefore cannot feed back into identity.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(180)  # ~5.5 fps: visual ambience, not a render surface
        self._timer.timeout.connect(self._advance)
        self._timer.start()
    def _advance(self):
        if self.isVisible():
            self._phase = (self._phase + 0.04759) % math.tau
            self.update()
    def paintEvent(self, event):
        w,h=self.width(),self.height()
        if w < 2 or h < 2: return
        q=QPainter(self); q.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        q.setPen(QPen(QColor(68, 145, 174, 42), 1))
        step=max(48, min(w,h)//9)
        ox=int((self._phase/math.tau)*step)
        for x in range(-step+ox, w, step): q.drawLine(x,0,x,h)
        for y in range(-step+ox, h, step): q.drawLine(0,y,w,y)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.setPen(QPen(QColor(245, 211, 109, 58), 1))
        pts=[]
        for i in range(0, max(2,w), max(6,w//180 or 6)):
            t=i/max(1,w-1)
            y=h*(0.50 + 0.16*math.sin(math.tau*(1.1975807343*t)+self._phase)
                 +0.08*math.sin(math.tau*((1+5**0.5)/2)*t-self._phase*0.618))
            pts.append((i,int(y)))
        for a,b in zip(pts,pts[1:]): q.drawLine(a[0],a[1],b[0],b[1])
        q.end()


def _probe_media_kind_sync(path: str) -> str:
    """Classify a file's actual stream content (not just its extension).

    Plain audio extensions are audio by definition — no need to shell out.
    Anything with a video extension gets an ffprobe stream-type check, since
    a video container may or may not actually carry an audio track.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in AUDIO_EXT:
        return KIND_AUDIO
    if ext not in VIDEO_EXT:
        return KIND_UNKNOWN
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return KIND_UNKNOWN
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=8,
        )
        types = {line.strip() for line in (proc.stdout or "").splitlines() if line.strip()}
        has_v = "video" in types
        has_a = "audio" in types
        if has_v and has_a:
            return KIND_AV
        if has_v:
            return KIND_VIDEO
        if has_a:
            return KIND_AUDIO
        return KIND_UNKNOWN
    except Exception:
        return KIND_UNKNOWN


def _kind_icon(kind: str) -> str:
    return {
        KIND_AUDIO: "🔊", KIND_VIDEO: "🎬(mute)", KIND_AV: "🎬🔊", KIND_PENDING: "⏳",
    }.get(kind, "📄")


class _KindProbeWorker(QObject):
    """Batch stream-probing off the UI thread (see _ProvenanceWorker above
    for why: ffprobe calls must never run on the UI thread). Probes an
    entire folder listing's video files sequentially in one background
    thread and emits one signal per completed file, plus a final batch_done
    so the browser can re-apply the active Audio/Video filter once every
    file in the folder has a real (non-pending) classification."""
    progress = pyqtSignal(int, str, str)  # generation, path, kind
    batch_done = pyqtSignal(int)          # generation

    def run_batch(self, generation: int, paths: List[str]):
        for p in paths:
            kind = _probe_media_kind_sync(p)
            self.progress.emit(generation, p, kind)
        self.batch_done.emit(generation)



def _safe_size(path: str) -> str:
    try:
        n = os.path.getsize(path)
    except OSError:
        return "?"
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def _find_player() -> Optional[List[str]]:
    for cand in ("mpv", "vlc", "ffplay"):
        p = shutil.which(cand)
        if p:
            if cand == "mpv":
                return [p, "--force-window=yes", "--keep-open=yes"]
            if cand == "vlc":
                return [p, "--no-one-instance", "--no-video-title-show"]
            return [p, "-autoexit", "-nodisp"]
    return None


def _player_cmd_with_volume(volume_pct: int, want_video: bool = True) -> Optional[List[str]]:
    """Same player resolution as _find_player(), plus a per-track volume
    flag — needed so playlist "mix" mode can play several tracks at once
    with different levels instead of everything at 100%. want_video=False
    keeps ffplay's existing -nodisp behavior for audio-only mix members;
    True (video/av members) drops -nodisp so the video window still shows.
    """
    for cand in ("mpv", "vlc", "ffplay"):
        p = shutil.which(cand)
        if not p:
            continue
        vol = max(0, min(200, int(volume_pct)))
        if cand == "mpv":
            return [p, "--force-window=yes", "--keep-open=yes", f"--volume={vol}"]
        if cand == "vlc":
            return [p, "--no-one-instance", "--no-video-title-show", f"--gain={vol / 100.0:.2f}"]
        # ffplay
        args = [p, "-autoexit", "-volume", str(min(100, vol))]
        if not want_video:
            args.append("-nodisp")
        return args
    return None


def _extract_wav_eqrf(path: str) -> Optional[bytes]:
    """Read optional 'eqrf' chunk from a Groovebox WAV without importing groovebox."""
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"RIFF":
                return None
            f.read(4)
            if f.read(4) != b"WAVE":
                return None
            while True:
                hdr = f.read(8)
                if len(hdr) < 8:
                    break
                cid, sz = hdr[:4], int.from_bytes(hdr[4:8], "little")
                data = f.read(sz)
                if cid == b"eqrf":
                    return data
                if sz & 1:
                    f.read(1)
    except Exception:
        return None
    return None


def _extract_json_comment(path: str) -> Optional[dict]:
    """Best-effort provenance from WAV eqrf chunk or ffmpeg comment / sidecars."""
    try:
        raw = _extract_wav_eqrf(path)
        if raw:
            text = raw.decode("utf-8", errors="replace")
            if text.strip().startswith("{"):
                return json.loads(text)
    except Exception:
        pass
    # Sidecar .mgpr / .json next to media
    for suffix in (".mgpr", ".json", ".provenance.json"):
        side = path + suffix
        if os.path.isfile(side):
            try:
                with open(side, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        base, _ = os.path.splitext(path)
        side2 = base + suffix
        if os.path.isfile(side2):
            try:
                with open(side2, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    # ffprobe comment
    ffprobe = shutil.which("ffprobe")
    if ffprobe and os.path.isfile(path):
        try:
            proc = subprocess.run(
                [ffprobe, "-v", "quiet", "-show_entries", "format_tags=comment",
                 "-of", "json", path],
                capture_output=True, text=True, timeout=12,
            )
            data = json.loads(proc.stdout or "{}")
            comment = (
                (data.get("format") or {}).get("tags") or {}
            ).get("comment") or ""
            if isinstance(comment, str) and comment.strip().startswith("{"):
                return json.loads(comment)
        except Exception:
            pass
    return None


class _ProvenanceWorker(QObject):
    """Runs the (potentially slow, ffprobe-shelling) provenance lookup off
    the UI thread.

    PERF_2026: `_extract_json_comment` can invoke `ffprobe` with up to a
    12-second timeout. It used to run directly inside
    `_on_selection_changed`, so clicking or arrow-keying through a folder of
    samples/videos froze the whole Performance for however long each ffprobe
    call took — the exact "lag while using the app" complaint on slower
    storage (SD cards, network shares). One QThread does the shelling out;
    results come back via a signal so Qt marshals them onto the UI thread
    safely, and a token lets the UI drop stale results if the user has
    already moved on to a different file.
    """
    done = pyqtSignal(int, str, object)  # token, path, provenance dict-or-None

    def lookup(self, token: int, path: str):
        prov = _extract_json_comment(path) if os.path.isfile(path) else None
        self.done.emit(token, path, prov)


class Performance(QDialog):
    """In-app file browser, playlister, game player, DJ remixer, batch re-render."""

    def __init__(self, host, parent=None):
        super().__init__(parent or host)
        self.host = host
        self.setWindowTitle("Groovebox Performance — Media · Devices · Cutups · Game · Broadcast · Batch")
        self.setStyleSheet("""
            QDialog { background:rgba(7,16,25,232); color:#d9edf5; }
            QGroupBox { border:1px solid #284c62; border-radius:7px; margin-top:8px; padding-top:7px; font-weight:700; }
            QGroupBox::title { color:#f1ce68; subcontrol-origin:margin; left:9px; padding:0 4px; }
            QPushButton { background:#102838; color:#d9f7ff; border:1px solid #39708a; border-radius:11px; padding:8px 11px; font-weight:700; }
            QPushButton:hover { background:#17405a; border-color:#62bfd0; }
            QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit { background:#08141e; color:#e6f8ff; border:1px solid #335b70; border-radius:8px; padding:6px; }
            QTabWidget::pane { background:rgba(7,16,25,218); border:2px solid #3b718c; }
            QTabBar::tab { background:rgba(12,27,40,238); color:#b9d5df; padding:10px 12px; margin:2px; border:2px solid #35677f; border-radius:9px; min-width:42px; }
            QTabBar::tab:hover { background:#122c3e; border-color:#4b879f; }
            QTabBar::tab:selected { background:#17354a; color:#f6d46d; border-color:#6ca6ba; }
        """)
        self.resize(920, 640)
        self.setMinimumSize(720, 480)
        # PERFORMANCE_MATH_BG_20260905: ambient, sparse, low-refresh background.
        self._math_background = _PerformanceMathBackground(self)
        self._math_background.lower()
        self._player_proc: Optional[subprocess.Popen] = None
        self._playlist: List[Dict[str, Any]] = []
        self._playlist_index = -1
        self._batch_cancel = False
        self._mix_procs: List[subprocess.Popen] = []
        # LIVE_MEDIA_2026: mpv JSON-IPC gives instant speed changes without
        # killing/restarting a file. One socket is reused for the active player.
        self._mpv_ipc_path: Optional[str] = None
        self._live_speed = 1.0
        # CONTINUOUS_PATTERN_2026: cheap deterministic control-rate scripting.
        self._pattern_phase = 0.0
        self._pattern_step = 0
        self._pattern_rng = random.Random(0)
        self._pattern_timer = QTimer(self)
        self._pattern_timer.setInterval(50)
        self._pattern_timer.timeout.connect(self._pattern_tick)
        # PERFORMANCE_BROADCAST_2026: one phaselocked clock fans the same event
        # state to replay, video/game state and optional Ethernet clients.
        self._performance_timer = QTimer(self)
        self._performance_timer.timeout.connect(self._performance_tick)
        self._performance_step = 0
        self._performance_media_path: Optional[str] = None
        self._performance_loop = False
        self._broadcast_state: Dict[str, Any] = {"active": False}
        self._remote_server = None
        self._remote_thread = None
        self._remote_token = secrets.token_urlsafe(12)
        self._remote_commands: List[Dict[str, Any]] = []
        self._remote_lock = threading.Lock()
        self._remote_timer = QTimer(self)
        self._remote_timer.setInterval(50)
        self._remote_timer.timeout.connect(self._drain_remote_commands)
        self._remote_timer.start()

        # OUTPUT_ROUTER_2026: optional local display/audio routing plus LAN/Wi-Fi TV
        # sharing. Hardware discovery is refreshed on demand so hot-plugged HDMI,
        # VGA adapters, USB displays/audio and Bluetooth sinks can appear live.
        self._output_displays = []
        self._output_audio = []
        self._output_display = None
        self._output_audio_target = None
        self._media_share_server = None
        self._last_shared_game_url = None
        self._clone_share_server = None
        self._last_clone_bundle = None
        self._goava_radio_service = None
        self._radio_peer_timer = QTimer(self)
        self._radio_peer_timer.setInterval(1800)
        self._radio_peer_timer.timeout.connect(self._refresh_radio_peers)

        # Fine-grained (audio/video/av) stream-kind cache, keyed by path:
        # (mtime, size, kind) so a probe is only redone if the file changed.
        self._kind_cache: Dict[str, Tuple[float, int, str]] = {}
        self._refresh_generation = 0
        self._kind_worker = _KindProbeWorker()
        self._kind_worker.progress.connect(self._on_kind_probe_progress)
        self._kind_worker.batch_done.connect(self._on_kind_probe_batch_done)

        # PERF_2026: provenance lookups (ffprobe) happen on a worker thread,
        # debounced so rapid arrow-key/click movement through a file list
        # doesn't queue up a subprocess call per keystroke. `_selection_token`
        # invalidates results for a selection the user has already left.
        self._selection_token = 0
        self._prov_worker = _ProvenanceWorker()
        self._prov_worker.done.connect(self._on_provenance_ready)
        self._selection_debounce = QTimer(self)
        self._selection_debounce.setSingleShot(True)
        self._selection_debounce.setInterval(150)
        self._selection_debounce.timeout.connect(self._start_provenance_lookup)

        projects = self._host_projects_dir()
        renders = self._host_exports_dir()
        games = self._host_games_dir()
        samples = self._host_samples_dir()
        self._roots = {
            "Projects": projects,
            "Renders": renders,
            "Games": games,
            "Samples": samples,
            "Both": None,
        }
        self._cwd = projects if os.path.isdir(projects) else renders

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        brand_row = QHBoxLayout()
        self.lbl_perf_brand = QLabel()
        try:
            bp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "goava_radio_brand.png")
            pm = QPixmap(bp)
            if not pm.isNull():
                self.lbl_perf_brand.setPixmap(pm.scaled(310, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass
        self.lbl_perf_brand.setStyleSheet("background:#030a10; border:1px solid #8b6b2c; border-radius:7px; padding:2px;")
        brand_row.addWidget(self.lbl_perf_brand)
        brand_title = QLabel("<b style='font-size:16pt;color:#f1ce68'>GOAVA RADIO · PERFORMANCE</b><br><span style='color:#77d8ef'>Live seeds · media · hardware · networked game state</span>")
        brand_row.addWidget(brand_title, 1)
        root.addLayout(brand_row)

        # --- top bar: path + roots ---
        top = QHBoxLayout()
        self.cmb_root = QComboBox()
        self.cmb_root.addItems(["Projects", "Renders", "Games", "Samples", "Custom…"])
        self.cmb_root.currentIndexChanged.connect(self._on_root_changed)
        top.addWidget(QLabel("Root:"))
        top.addWidget(self.cmb_root)
        self.lbl_cwd = QLabel(self._cwd)
        self.lbl_cwd.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        self.lbl_cwd.setWordWrap(True)
        top.addWidget(self.lbl_cwd, stretch=1)
        btn_up = QPushButton("⬆ Up")
        btn_up.clicked.connect(self._go_up)
        btn_refresh = QPushButton("↻")
        btn_refresh.clicked.connect(self.refresh)
        top.addWidget(btn_up)
        top.addWidget(btn_refresh)
        root.addLayout(top)

        # --- filter/sort bar: audio vs video, audioless/videoless vs both ---
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Kind:"))
        self.cmb_kind_filter = QComboBox()
        self.cmb_kind_filter.addItems([
            "All",
            "Audio only (videoless)",
            "Video only (audioless)",
            "Audio + Video (both)",
        ])
        self.cmb_kind_filter.currentIndexChanged.connect(lambda _i: self.refresh())
        filt.addWidget(self.cmb_kind_filter)
        filt.addWidget(QLabel("Sort:"))
        self.cmb_sort = QComboBox()
        self.cmb_sort.addItems(["Name", "Kind (Audio first)", "Kind (Video first)", "Size"])
        self.cmb_sort.currentIndexChanged.connect(lambda _i: self.refresh())
        filt.addWidget(self.cmb_sort)
        filt.addStretch(1)
        self.lbl_probe_status = QLabel("")
        self.lbl_probe_status.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        filt.addWidget(self.lbl_probe_status)
        root.addLayout(filt)

        split = QSplitter(Qt.Orientation.Horizontal)

        # --- left: file list ---
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.itemDoubleClicked.connect(self._on_double_click)
        self.file_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_l.addWidget(self.file_list, stretch=1)
        file_btns = QHBoxLayout()
        for text, slot in (
            ("Open", self._open_selected),
            ("Play", self._play_selected),
            ("→ Playlist", self._add_to_playlist),
            ("Delete", self._delete_selected),
            ("Reveal", self._reveal_selected),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            file_btns.addWidget(b)
        left_l.addLayout(file_btns)
        split.addWidget(left)

        # --- right: tabs ---
        right = QTabWidget()
        # PERFORMANCE_NAV_V38: vertical rail prevents tabs from running beyond margins.
        right.setTabPosition(QTabWidget.TabPosition.West)
        right.setUsesScrollButtons(True)
        right.tabBar().setExpanding(False)
        right.addTab(self._build_playlist_tab(), "♫ Playlist")
        right.addTab(self._build_game_tab(), "🎮 Game / Wi‑Fi")
        right.addTab(self._build_remix_tab(), "∿ Parametric Remix")
        right.addTab(self._build_cutup_tab(), "✂ Cutup Lab")
        try:
            from signal_lab import SignalLab
            right.addTab(SignalLab(self.host, self), "✎ Draw / Signal Lab")
        except Exception as e:
            fallback = QWidget(); fl = QVBoxLayout(fallback); msg = QLabel(f"Signal Lab unavailable: {e}"); msg.setWordWrap(True); fl.addWidget(msg); fl.addStretch(1); right.addTab(fallback, "✎ Draw / Signal Lab")
        right.addTab(self._build_performance_tab(), "◉ Live Broadcast")
        right.addTab(self._build_outputs_tab(), "▣ Device Manager")
        right.addTab(self._build_hardware_tab(), "⌨ Hardware")
        right.addTab(self._build_transfer_tab(), "⇄ Drive / Clone")
        right.addTab(self._build_mg_library_tab(), "⌬ .MG Related")
        right.addTab(self._build_box_tab(), "⚙ Box Mode")
        right.addTab(self._build_batch_tab(), "Batch Re-render")
        right.addTab(self._build_info_tab(), "Info")
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, stretch=1)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setStyleSheet("color:#9dffb0; font-size:9pt;")
        root.addWidget(self.lbl_status)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        root.addLayout(close_row)

        self.refresh()

    def resizeEvent(self, event):
        try:
            self._math_background.setGeometry(self.rect())
            self._math_background.lower()
        except Exception:
            pass
        return super().resizeEvent(event)

    # ------------------------------------------------------------------ host paths
    def _host_projects_dir(self) -> str:
        if hasattr(self.host, "_projects_dir"):
            try:
                return self.host._projects_dir()
            except Exception:
                pass
        import groovebox_paths
        return groovebox_paths.projects_dir()

    def _host_exports_dir(self) -> str:
        if hasattr(self.host, "_exports_dir"):
            try:
                return self.host._exports_dir()
            except Exception:
                pass
        import groovebox_paths
        return groovebox_paths.renders_dir()

    def _host_games_dir(self) -> str:
        if hasattr(self.host, "_games_dir"):
            try:
                return self.host._games_dir()
            except Exception:
                pass
        import groovebox_paths
        return groovebox_paths.games_dir()

    def _host_samples_dir(self) -> str:
        if hasattr(self.host, "_samples_dir"):
            try:
                return self.host._samples_dir()
            except Exception:
                pass
        import groovebox_paths
        return groovebox_paths.samples_dir()

    # ------------------------------------------------------------------ browser
    def _on_root_changed(self, idx: int):
        text = self.cmb_root.currentText()
        if text == "Projects":
            self._cwd = self._host_projects_dir()
        elif text == "Renders":
            self._cwd = self._host_exports_dir()
        elif text == "Games":
            self._cwd = self._host_games_dir()
        elif text == "Samples":
            self._cwd = self._host_samples_dir()
        else:
            path = QFileDialog.getExistingDirectory(self, "Choose folder", self._cwd or "")
            if path:
                self._cwd = path
            else:
                self.cmb_root.blockSignals(True)
                self.cmb_root.setCurrentIndex(0)
                self.cmb_root.blockSignals(False)
                return
        self.refresh()

    def _go_up(self):
        parent = os.path.dirname(self._cwd.rstrip(os.sep))
        if parent and parent != self._cwd:
            self._cwd = parent
            self.refresh()

    def _cached_kind(self, path: str) -> Optional[str]:
        """Return a cached fine-grained kind if the file hasn't changed since
        it was probed, else None (caller should treat as pending/needs-probe)."""
        try:
            st = os.stat(path)
        except OSError:
            return None
        cached = self._kind_cache.get(path)
        if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
            return cached[2]
        return None

    def refresh(self):
        self.file_list.clear()
        self.lbl_cwd.setText(self._cwd or "")
        if not self._cwd or not os.path.isdir(self._cwd):
            self.lbl_status.setText("Folder missing.")
            return
        try:
            entries = sorted(os.listdir(self._cwd), key=str.lower)
        except OSError as e:
            self.lbl_status.setText(f"List error: {e}")
            return
        # dirs first
        dirs = [e for e in entries if os.path.isdir(os.path.join(self._cwd, e)) and not e.startswith(".")]
        files = [e for e in entries if os.path.isfile(os.path.join(self._cwd, e))]

        kind_filter = self.cmb_kind_filter.currentText() if hasattr(self, "cmb_kind_filter") else "All"
        sort_mode = self.cmb_sort.currentText() if hasattr(self, "cmb_sort") else "Name"

        self._refresh_generation += 1
        generation = self._refresh_generation
        pending_probe: List[str] = []

        rows = []  # (name, full, ext, coarse_kind, fine_kind, size_bytes)
        for f in files:
            full = os.path.join(self._cwd, f)
            ext = os.path.splitext(f)[1].lower()
            coarse_kind = "file"
            if ext in PROJECT_EXT:
                coarse_kind = "project"
            elif ext in AUDIO_EXT:
                coarse_kind = "audio"
            elif ext in VIDEO_EXT:
                coarse_kind = "video"
            elif ext in GAME_EXT:
                coarse_kind = "game"

            fine_kind = KIND_UNKNOWN
            if ext in AUDIO_EXT:
                fine_kind = KIND_AUDIO
            elif ext in VIDEO_EXT:
                cached = self._cached_kind(full)
                if cached is not None:
                    fine_kind = cached
                else:
                    fine_kind = KIND_PENDING
                    pending_probe.append(full)
            try:
                size_bytes = os.path.getsize(full)
            except OSError:
                size_bytes = 0
            rows.append((f, full, ext, coarse_kind, fine_kind, size_bytes))

        # --- filter: audio-only vs audioless-video vs both, videoless-audio ---
        def _passes_filter(fine_kind: str, coarse_kind: str) -> bool:
            if kind_filter == "All":
                return True
            if coarse_kind not in ("audio", "video"):
                return True  # never hide dirs/projects/games behind a media filter
            if fine_kind == KIND_PENDING:
                return True  # show until probed, so files don't flicker away
            if kind_filter.startswith("Audio only"):
                return fine_kind == KIND_AUDIO
            if kind_filter.startswith("Video only"):
                return fine_kind == KIND_VIDEO
            if kind_filter.startswith("Audio + Video"):
                return fine_kind == KIND_AV
            return True

        rows = [r for r in rows if _passes_filter(r[4], r[3])]

        # --- sort ---
        if sort_mode == "Size":
            rows.sort(key=lambda r: r[5], reverse=True)
        elif sort_mode.startswith("Kind (Audio"):
            order = {KIND_AUDIO: 0, KIND_AV: 1, KIND_VIDEO: 2, KIND_PENDING: 3, KIND_UNKNOWN: 4}
            rows.sort(key=lambda r: (order.get(r[4], 5) if r[3] in ("audio", "video") else 5, r[0].lower()))
        elif sort_mode.startswith("Kind (Video"):
            order = {KIND_VIDEO: 0, KIND_AV: 1, KIND_AUDIO: 2, KIND_PENDING: 3, KIND_UNKNOWN: 4}
            rows.sort(key=lambda r: (order.get(r[4], 5) if r[3] in ("audio", "video") else 5, r[0].lower()))
        else:
            rows.sort(key=lambda r: r[0].lower())

        for d in dirs:
            item = QListWidgetItem(f"📁 {d}/")
            item.setData(Qt.ItemDataRole.UserRole, os.path.join(self._cwd, d))
            item.setData(Qt.ItemDataRole.UserRole + 1, "dir")
            self.file_list.addItem(item)
        for (f, full, ext, coarse_kind, fine_kind, size_bytes) in rows:
            if coarse_kind == "project":
                icon = "🎛"
            elif coarse_kind == "game":
                icon = "🕹"
            elif coarse_kind in ("audio", "video"):
                icon = _kind_icon(fine_kind)
            else:
                icon = "📄"
            item = QListWidgetItem(f"{icon} {f}  ({_safe_size(full)})")
            item.setData(Qt.ItemDataRole.UserRole, full)
            item.setData(Qt.ItemDataRole.UserRole + 1, coarse_kind)
            item.setData(Qt.ItemDataRole.UserRole + 2, fine_kind)
            self.file_list.addItem(item)
        self.lbl_status.setText(f"{len(dirs)} folders · {len(rows)} files")

        if pending_probe:
            self.lbl_probe_status.setText(f"Classifying {len(pending_probe)} video file(s)…")
            threading.Thread(
                target=self._kind_worker.run_batch, args=(generation, pending_probe), daemon=True
            ).start()
        else:
            self.lbl_probe_status.setText("")

    def _on_kind_probe_progress(self, generation: int, path: str, kind: str):
        if generation != self._refresh_generation:
            return  # user navigated away / re-sorted before this finished
        try:
            st = os.stat(path)
            self._kind_cache[path] = (st.st_mtime, st.st_size, kind)
        except OSError:
            self._kind_cache[path] = (0.0, 0, kind)
        # Update the visible row in place if it's still on screen — avoids a
        # full relist (and a fresh disk stat pass) for every single result.
        for i in range(self.file_list.count()):
            it = self.file_list.item(i)
            if it and it.data(Qt.ItemDataRole.UserRole) == path:
                coarse_kind = it.data(Qt.ItemDataRole.UserRole + 1)
                if coarse_kind in ("audio", "video"):
                    it.setData(Qt.ItemDataRole.UserRole + 2, kind)
                    name = os.path.basename(path)
                    it.setText(f"{_kind_icon(kind)} {name}  ({_safe_size(path)})")
                break

    def _on_kind_probe_batch_done(self, generation: int):
        if generation != self._refresh_generation:
            return
        self.lbl_probe_status.setText("")
        # If an Audio/Video-only filter is active, files that were shown as
        # "pending" may need to drop out (or newly-revealed ones appear) now
        # that every file in the folder has a real classification.
        kind_filter = self.cmb_kind_filter.currentText() if hasattr(self, "cmb_kind_filter") else "All"
        if kind_filter != "All":
            self.refresh()

    def _selected_paths(self) -> List[str]:
        out = []
        for item in self.file_list.selectedItems():
            p = item.data(Qt.ItemDataRole.UserRole)
            if p:
                out.append(str(p))
        return out

    def _on_double_click(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        kind = item.data(Qt.ItemDataRole.UserRole + 1)
        if kind == "dir" and path:
            self._cwd = path
            self.refresh()
            return
        if kind == "project":
            self._open_project(path)
        elif kind in ("audio", "video"):
            self._play_path(path)
        elif kind == "game":
            self._play_game_package(path)

    def _on_selection_changed(self):
        # Fast path only: show path + size immediately (both cheap, local
        # stat calls). The slow provenance/ffprobe part is debounced and
        # run off-thread in _start_provenance_lookup / _on_provenance_ready.
        self._selection_token += 1
        paths = self._selected_paths()
        if not paths:
            self.info_view.setPlainText("")
            self._selection_debounce.stop()
            return
        path = paths[0]
        self.info_view.setPlainText(f"{path}\nsize: {_safe_size(path)}\n(reading details…)")
        self._selection_debounce.start()

    def _start_provenance_lookup(self):
        paths = self._selected_paths()
        if not paths:
            return
        path = paths[0]
        token = self._selection_token
        threading.Thread(
            target=self._prov_worker.lookup, args=(token, path), daemon=True
        ).start()

    def _on_provenance_ready(self, token: int, path: str, prov: Optional[dict]):
        if token != self._selection_token:
            return  # user already moved on to a different selection
        lines = [path, f"size: {_safe_size(path)}"]
        if prov:
            lines.append("--- provenance ---")
            for k in ("seed", "bpm", "source_project_path", "sample_rate", "fps",
                      "audio_bitrate_kbps", "fingerprint", "doc"):
                if k in prov:
                    lines.append(f"{k}: {prov[k]}")
            sp = prov.get("source_project_path")
            if sp:
                lines.append(f"linked project exists: {os.path.isfile(str(sp))}")
        self.info_view.setPlainText("\n".join(lines))

    def _open_selected(self):
        for path in self._selected_paths():
            kind = "file"
            for i in range(self.file_list.count()):
                it = self.file_list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == path:
                    kind = it.data(Qt.ItemDataRole.UserRole + 1)
                    break
            if kind == "dir":
                self._cwd = path
                self.refresh()
            elif kind == "project":
                self._open_project(path)
            elif kind == "game":
                self._play_game_package(path)
            elif kind in ("audio", "video"):
                self._play_path(path)

    def _open_project(self, path: str):
        try:
            if hasattr(self.host, "load_project_dialog"):
                # Direct load if host supports path-based apply
                pass
            if hasattr(self.host, "_apply_project_snapshot") or hasattr(self.host, "load_project_dialog"):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Prefer apply_project_snapshot / restore path
                applied = False
                for name in ("_apply_project_snapshot", "apply_project_snapshot",
                             "_project_history_restore"):
                    fn = getattr(self.host, name, None)
                    if callable(fn):
                        try:
                            fn(data)
                            applied = True
                            break
                        except Exception:
                            continue
                if not applied:
                    # Fallback: set as current and ask user to use host Load
                    QMessageBox.information(
                        self, "Project",
                        f"Opened path recorded:\n{path}\n\n"
                        "Use host Load Project if auto-apply is unavailable."
                    )
                setattr(self.host, "_current_project_path", path)
                self.lbl_status.setText(f"Loaded project: {os.path.basename(path)}")
                self.cmb_game_status.setText(f"Project: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Open project failed", str(e))

    def _play_selected(self):
        paths = [p for p in self._selected_paths() if os.path.isfile(p)]
        if not paths:
            return
        self._play_path(paths[0])

    def _routed_player(self, cmd: list, want_video: bool = True):
        """Apply selected per-process display/audio routing without changing OS defaults."""
        env = os.environ.copy()
        try:
            from media_output_router import player_routing
            extra, overlay = player_routing(self._output_display, self._output_audio_target, want_video=want_video)
            if cmd and os.path.basename(cmd[0]).lower().startswith("mpv"):
                cmd = list(cmd) + list(extra)
            env.update(overlay)
        except Exception:
            pass
        return cmd, env

    def _play_path(self, path: str, volume_pct: int = 100):
        self._stop_player()
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXT and hasattr(self.host, "play_buffer"):
            # Prefer host buffer play for dry 1× WAV. At any other speed use
            # mpv so rate changes remain live/responsive through IPC.
            if ext == ".wav" and abs(self._live_speed - 1.0) < 1e-9:
                try:
                    self._play_wav_on_host(path)
                    self.lbl_status.setText(f"Playing on host: {os.path.basename(path)}")
                    return
                except Exception as e:
                    self.lbl_status.setText(f"Host play failed ({e}); external player…")
        cmd = _player_cmd_with_volume(volume_pct, want_video=(ext in VIDEO_EXT)) or _find_player()
        if not cmd:
            QMessageBox.warning(
                self, "No player",
                "Install mpv, vlc, or ffplay for media playback on this Pi."
            )
            return
        try:
            # Prefer mpv with IPC so live speed/pitch-independent time changes are
            # responsive while the file is already running. Other players retain
            # the existing fallback behavior.
            if cmd and os.path.basename(cmd[0]).startswith("mpv"):
                self._mpv_ipc_path = os.path.join(tempfile.gettempdir(), f"groovebox_mpv_{os.getpid()}_{id(self)}.sock")
                try:
                    os.unlink(self._mpv_ipc_path)
                except OSError:
                    pass
                cmd = list(cmd) + [f"--input-ipc-server={self._mpv_ipc_path}", f"--speed={self._live_speed:.6f}"]
            else:
                self._mpv_ipc_path = None
            cmd, penv = self._routed_player(cmd, want_video=(ext in VIDEO_EXT))
            self._player_proc = subprocess.Popen(cmd + [path], env=penv)
            try:
                if self._media_share_server is not None:
                    self._media_share_server.set_current(path)
            except Exception:
                pass
            self.lbl_status.setText(f"External play: {os.path.basename(path)} @{volume_pct}% · {self._live_speed:.2f}×")
        except Exception as e:
            QMessageBox.warning(self, "Play failed", str(e))

    def _check_player_launch(self, proc, path: str):
        try:
            rc = proc.poll()
            if rc is not None and proc is getattr(self, "_player_proc", None):
                self.lbl_status.setText(f"Player exited immediately (code {rc}): {os.path.basename(path)}")
        except Exception:
            pass

    def _play_wav_on_host(self, path: str):
        import numpy as np
        try:
            import scipy.io.wavfile as wavfile
            sr, data = wavfile.read(path)
            if data.ndim > 1:
                data = data.mean(axis=1)
            if data.dtype == np.int16:
                buf = (data.astype(np.float32) / 32768.0)
            else:
                buf = np.asarray(data, dtype=np.float32)
                peak = float(np.max(np.abs(buf))) or 1.0
                buf = buf / peak
            with getattr(self.host, "play_lock", threading.Lock()):
                self.host.play_buffer = buf
                self.host.play_sample_rate = int(sr)
                self.host.play_cursor = 0
                self.host.is_playing = True
                self.host.is_paused = False
                self.host._audio_only_mode = True
            if hasattr(self.host, "audio_stream") and getattr(self.host, "HAS_SOUNDDEVICE", True):
                try:
                    import sounddevice as sd
                    if self.host.audio_stream is not None:
                        try:
                            self.host.audio_stream.stop()
                            self.host.audio_stream.close()
                        except Exception:
                            pass
                    self.host.audio_stream = sd.OutputStream(
                        samplerate=int(sr), channels=1, dtype="float32",
                        callback=self.host._audio_callback, blocksize=1024, latency="low",
                    )
                    self.host.audio_stream.start()
                except Exception:
                    pass
            if hasattr(self.host, "_scope_update_timer"):
                self.host._scope_update_timer.start()
        except Exception:
            raise

    def _stop_player(self):
        if self._player_proc is not None:
            try:
                self._player_proc.terminate()
            except Exception:
                pass
            self._player_proc = None
        if self._mpv_ipc_path:
            try:
                os.unlink(self._mpv_ipc_path)
            except OSError:
                pass
            self._mpv_ipc_path = None
        try:
            if getattr(self.host, "is_playing", False) and getattr(self.host, "_audio_only_mode", False):
                if hasattr(self.host, "stop_audio_playback"):
                    self.host.stop_audio_playback()
        except Exception:
            pass

    def _add_to_playlist(self):
        for path in self._selected_paths():
            if os.path.isfile(path) and not any(it["path"] == path for it in self._playlist):
                ext = os.path.splitext(path)[1].lower()
                if ext in MEDIA_EXT:
                    fine_kind = self._cached_kind(path)
                    if fine_kind is None:
                        fine_kind = _probe_media_kind_sync(path)
                        try:
                            st = os.stat(path)
                            self._kind_cache[path] = (st.st_mtime, st.st_size, fine_kind)
                        except OSError:
                            pass
                    self._playlist.append({"path": path, "volume": 100, "mix": False, "kind": fine_kind})
                elif ext in GAME_EXT:
                    self._playlist.append({"path": path, "volume": 100, "mix": False, "kind": KIND_UNKNOWN})
        self._refresh_playlist_widget()
        self.lbl_status.setText(f"Playlist: {len(self._playlist)} items")

    def _delete_selected(self):
        paths = self._selected_paths()
        if not paths:
            return
        reply = QMessageBox.question(
            self, "Delete",
            f"Delete {len(paths)} item(s)?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for path in paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception as e:
                QMessageBox.warning(self, "Delete failed", f"{path}\n{e}")
        self.refresh()

    def _reveal_selected(self):
        paths = self._selected_paths()
        if not paths:
            return
        path = paths[0]
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        for cmd in (
            ["xdg-open", folder],
            ["pcmanfm", folder],
            ["thunar", folder],
            ["explorer.exe", folder],
        ):
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(cmd)
                    return
                except Exception:
                    continue
        self.lbl_status.setText(folder)

    # ------------------------------------------------------------------ playlist tab
    def _build_playlist_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.playlist_widget = QListWidget()
        self.playlist_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.playlist_widget.itemSelectionChanged.connect(self._on_playlist_selection_changed)
        lay.addWidget(self.playlist_widget, stretch=1)

        row = QHBoxLayout()
        btn_play = QPushButton("▶ Play")
        btn_next = QPushButton("⏭ Next")
        btn_stop = QPushButton("⏹ Stop")
        btn_clear = QPushButton("Clear")
        btn_play.clicked.connect(self._playlist_play)
        btn_next.clicked.connect(self._playlist_next)
        btn_stop.clicked.connect(self._stop_player)
        btn_clear.clicked.connect(self._playlist_clear)
        for b in (btn_play, btn_next, btn_stop, btn_clear):
            row.addWidget(b)
        lay.addLayout(row)

        arrange_row = QHBoxLayout()
        self.cmb_playlist_arrange = QComboBox()
        self.cmb_playlist_arrange.addItems([
            "Energy arc (size)", "Interleave A/V", "Deterministic shuffle", "Geometric phaselock seeded", "Name order",
        ])
        self.spin_playlist_arrange_seed = QSpinBox()
        self.spin_playlist_arrange_seed.setRange(0, 2147483647)
        self.spin_playlist_arrange_seed.setValue(1975807343)
        btn_arrange = QPushButton("Arrange playlist")
        btn_arrange.clicked.connect(self._arrange_media_playlist)
        arrange_row.addWidget(QLabel("Arrange:"))
        arrange_row.addWidget(self.cmb_playlist_arrange, stretch=1)
        arrange_row.addWidget(QLabel("Seed"))
        arrange_row.addWidget(self.spin_playlist_arrange_seed)
        arrange_row.addWidget(btn_arrange)
        lay.addLayout(arrange_row)

        # --- per-item volume + mix flag, and simultaneous "mix" playback ---
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume (selected):"))
        self.sld_playlist_volume = QSlider(Qt.Orientation.Horizontal)
        self.sld_playlist_volume.setRange(0, 150)
        self.sld_playlist_volume.setValue(100)
        self.sld_playlist_volume.setEnabled(False)
        self.sld_playlist_volume.valueChanged.connect(self._on_playlist_volume_changed)
        vol_row.addWidget(self.sld_playlist_volume, stretch=1)
        self.lbl_playlist_volume = QLabel("100%")
        self.lbl_playlist_volume.setMinimumWidth(40)
        vol_row.addWidget(self.lbl_playlist_volume)
        lay.addLayout(vol_row)

        mix_row = QHBoxLayout()
        btn_toggle_mix = QPushButton("Toggle Mix on selected")
        btn_toggle_mix.setToolTip(
            "Flag/unflag the selected rows for simultaneous playback via "
            "'Play Mix' — lets you layer audio + video + game audio at once "
            "instead of playing the queue one at a time."
        )
        btn_toggle_mix.clicked.connect(self._toggle_mix_selected)
        btn_play_mix = QPushButton("▶▶ Play Mix (simultaneous)")
        btn_play_mix.clicked.connect(self._playlist_play_mix)
        btn_stop_mix = QPushButton("⏹ Stop Mix")
        btn_stop_mix.clicked.connect(self._stop_mix)
        mix_row.addWidget(btn_toggle_mix)
        mix_row.addWidget(btn_play_mix)
        mix_row.addWidget(btn_stop_mix)
        lay.addLayout(mix_row)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Live file speed:"))
        self.sld_live_speed = QSlider(Qt.Orientation.Horizontal)
        self.sld_live_speed.setRange(25, 400)
        self.sld_live_speed.setValue(100)
        self.sld_live_speed.setToolTip("0.25×–4× live playback rate. With mpv this updates in-place through JSON IPC, without restarting the file.")
        self.sld_live_speed.valueChanged.connect(self._on_live_speed_changed)
        speed_row.addWidget(self.sld_live_speed, stretch=1)
        self.lbl_live_speed = QLabel("1.00×")
        self.lbl_live_speed.setMinimumWidth(52)
        speed_row.addWidget(self.lbl_live_speed)
        btn_speed_reset = QPushButton("1×")
        btn_speed_reset.clicked.connect(lambda: self.sld_live_speed.setValue(100))
        speed_row.addWidget(btn_speed_reset)
        lay.addLayout(speed_row)

        hint = QLabel(
            "Queue projects' renders here for sequential playback, or flag rows "
            "'[MIX]' and use Play Mix to layer several tracks (each at its own "
            "volume) at the same time — one OS-mixed output, e.g. a DJ backing "
            "track + a video's audio + a game's soundtrack together."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        lay.addWidget(hint)
        return w

    def _refresh_playlist_widget(self):
        """Rebuild playlist row text from self._playlist without losing the
        current selection (called after any volume/mix/add/remove change)."""
        selected_rows = {i.row() for i in self.playlist_widget.selectedIndexes()}
        self.playlist_widget.blockSignals(True)
        self.playlist_widget.clear()
        for it in self._playlist:
            name = os.path.basename(it["path"])
            ext = os.path.splitext(it["path"])[1].lower()
            if ext in GAME_EXT:
                icon = "🕹"
            else:
                icon = _kind_icon(it.get("kind", KIND_UNKNOWN))
            mix_tag = "  [MIX]" if it.get("mix") else ""
            mod_tag = ""
            if "pitch_semitones" in it or "rate" in it:
                mod_tag = f"  [P {float(it.get('pitch_semitones',0.0)):+.2f} st · R {float(it.get('rate',1.0)):.2f}× · {it.get('resample','preserve-duration')}]"
            self.playlist_widget.addItem(f"{icon} {name}  {it.get('volume', 100)}%{mix_tag}{mod_tag}")
        self.playlist_widget.blockSignals(False)
        for row in selected_rows:
            if 0 <= row < self.playlist_widget.count():
                self.playlist_widget.item(row).setSelected(True)
        # If a TV host is active, playlist edits/seeded rearrangements become live
        # immediately without another explicit publish click.
        try:
            if self._media_share_server is not None:
                self._media_share_server.set_playlist(self._playlist)
        except Exception:
            pass

    def _arrange_media_playlist(self):
        if len(self._playlist) < 2:
            return
        mode = self.cmb_playlist_arrange.currentText()
        if mode == "Name order":
            self._playlist.sort(key=lambda it: os.path.basename(it["path"]).lower())
        elif mode == "Deterministic shuffle":
            rng = random.Random(int(self.spin_playlist_arrange_seed.value()))
            rng.shuffle(self._playlist)
        elif mode == "Geometric phaselock seeded":
            try:
                from media_cutup_engine import playlist_geometric_parameters
                seed = int(self.spin_playlist_arrange_seed.value())
                params = playlist_geometric_parameters(len(self._playlist), seed, pitch_range_st=7.0, rate_depth=0.24, phase_lock=4)
                decorated = []
                for item, param in zip(self._playlist, params):
                    item.update(param)
                    decorated.append((float(param["geometry_key"]), item))
                decorated.sort(key=lambda pair: pair[0])
                self._playlist = [item for _key, item in decorated]
            except Exception as e:
                self.lbl_status.setText(f"Geometric playlist error: {e}")
                return
        elif mode == "Interleave A/V":
            aud = [it for it in self._playlist if it.get("kind") == KIND_AUDIO]
            vis = [it for it in self._playlist if it.get("kind") in (KIND_VIDEO, KIND_AV)]
            other = [it for it in self._playlist if it not in aud and it not in vis]
            out = []
            while aud or vis:
                if aud: out.append(aud.pop(0))
                if vis: out.append(vis.pop(0))
            self._playlist = out + other
        else:
            # A deterministic low→high→low file-size arc: useful as a simple
            # media-intensity proxy on boxes where full analysis would be costly.
            seq = sorted(self._playlist, key=lambda it: os.path.getsize(it["path"]) if os.path.isfile(it["path"]) else 0)
            lo, hi, out = 0, len(seq) - 1, []
            take_low = True
            while lo <= hi:
                if take_low:
                    out.append(seq[lo]); lo += 1
                else:
                    out.append(seq[hi]); hi -= 1
                take_low = not take_low
            self._playlist = out
        self._playlist_index = 0
        self._refresh_playlist_widget()
        self.lbl_status.setText(f"Playlist arranged: {mode}")

    def _on_playlist_selection_changed(self):
        rows = [i.row() for i in self.playlist_widget.selectedIndexes()]
        if not rows:
            self.sld_playlist_volume.setEnabled(False)
            return
        self.sld_playlist_volume.setEnabled(True)
        # Show the first selected row's volume as the slider starting point.
        vol = self._playlist[rows[0]].get("volume", 100) if 0 <= rows[0] < len(self._playlist) else 100
        self.sld_playlist_volume.blockSignals(True)
        self.sld_playlist_volume.setValue(int(vol))
        self.sld_playlist_volume.blockSignals(False)
        self.lbl_playlist_volume.setText(f"{int(vol)}%")

    def _on_playlist_volume_changed(self, value: int):
        self.lbl_playlist_volume.setText(f"{value}%")
        for row in {i.row() for i in self.playlist_widget.selectedIndexes()}:
            if 0 <= row < len(self._playlist):
                self._playlist[row]["volume"] = int(value)
        self._refresh_playlist_widget()

    def _toggle_mix_selected(self):
        rows = {i.row() for i in self.playlist_widget.selectedIndexes()}
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._playlist):
                self._playlist[row]["mix"] = not self._playlist[row].get("mix", False)
        self._refresh_playlist_widget()

    def _mpv_command(self, command: list) -> bool:
        path = self._mpv_ipc_path
        if not path or not os.path.exists(path):
            return False
        payload = (json.dumps({"command": command}) + "\n").encode("utf-8")
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.06)
            sock.connect(path)
            sock.sendall(payload)
            sock.close()
            return True
        except Exception:
            return False

    def _on_live_speed_changed(self, value: int):
        self._live_speed = max(0.25, min(4.0, float(value) / 100.0))
        if hasattr(self, "lbl_live_speed"):
            self.lbl_live_speed.setText(f"{self._live_speed:.2f}×")
        if self._mpv_command(["set_property", "speed", self._live_speed]):
            self.lbl_status.setText(f"Live playback speed: {self._live_speed:.2f}×")

    def _playlist_clear(self):
        self._stop_mix()
        self._playlist.clear()
        self._playlist_index = -1
        self.playlist_widget.clear()

    def _playlist_play(self):
        if not self._playlist:
            return
        if self._playlist_index < 0:
            self._playlist_index = 0
        self._playlist_index = max(0, min(self._playlist_index, len(self._playlist) - 1))
        entry = self._playlist[self._playlist_index]
        path = entry["path"]
        self.playlist_widget.setCurrentRow(self._playlist_index)
        ext = os.path.splitext(path)[1].lower()
        if ext in GAME_EXT:
            self._play_game_package(path)
        else:
            if "rate" in entry and hasattr(self, "sld_live_speed"):
                self.sld_live_speed.setValue(max(25, min(400, int(round(float(entry.get("rate", 1.0)) * 100.0)))))
            self._play_path(path, volume_pct=entry.get("volume", 100))

    def _playlist_next(self):
        if not self._playlist:
            return
        self._playlist_index = (self._playlist_index + 1) % len(self._playlist)
        self._playlist_play()

    def _playlist_prev(self):
        if not self._playlist:
            return
        self._playlist_index = (self._playlist_index - 1) % len(self._playlist)
        self._playlist_play()

    def _set_live_speed(self, value: float):
        value = max(0.25, min(4.0, float(value)))
        if hasattr(self, "sld_live_speed"):
            self.sld_live_speed.setValue(int(round(value * 100.0)))
        else:
            self._live_speed = value
            self._mpv_command(["set_property", "speed", self._live_speed])

    def _playlist_play_mix(self):
        """Launch every [MIX]-flagged playlist row simultaneously, each in
        its own player process at its own volume. Real mixing happens at the
        OS audio layer (ALSA/Pulse), which is what actually lets a DJ track,
        a video's audio, and a game's soundtrack sound together on one HDMI
        output — no single subprocess player can do that alone."""
        self._stop_mix()
        mixed = [it for it in self._playlist if it.get("mix") and os.path.isfile(it["path"])]
        if not mixed:
            QMessageBox.information(
                self, "Play Mix",
                "No playlist rows are flagged for Mix.\n"
                "Select one or more rows and click 'Toggle Mix on selected' first."
            )
            return
        started = []
        for it in mixed:
            ext = os.path.splitext(it["path"])[1].lower()
            if ext in GAME_EXT:
                continue  # games launch through _play_game_package, not a media player
            want_video = it.get("kind") in (KIND_VIDEO, KIND_AV, KIND_UNKNOWN) and ext in VIDEO_EXT
            cmd = _player_cmd_with_volume(it.get("volume", 100), want_video=want_video)
            if not cmd:
                continue
            try:
                cmd, penv = self._routed_player(cmd, want_video=want_video)
                proc = subprocess.Popen(cmd + [it["path"]], env=penv)
                self._mix_procs.append(proc)
                started.append(f"{os.path.basename(it['path'])} @{it.get('volume', 100)}%")
            except Exception:
                continue
        if not started:
            QMessageBox.warning(
                self, "Play Mix",
                "Install mpv, vlc, or ffplay for media playback on this Pi."
            )
            return
        self.lbl_status.setText("Mixing: " + " · ".join(started))

    def _stop_mix(self):
        for proc in self._mix_procs:
            try:
                proc.terminate()
            except Exception:
                pass
        self._mix_procs = []

    # ------------------------------------------------------------------ game tab
    def _build_game_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>🎮 Built-in game player · local Wi‑Fi multiplayer</b>"))
        self.cmb_game_status = QLabel("Uses live composition identity, or a packaged .zip game. LAN mode can be forced even when the seed classified the game as single-player.")
        self.cmb_game_status.setWordWrap(True); lay.addWidget(self.cmb_game_status)
        row = QHBoxLayout()
        btn_live = QPushButton("▶ Play Live Composition Game"); btn_live.clicked.connect(self._play_live_game)
        btn_pkg = QPushButton("🕹 Play Selected Package"); btn_pkg.clicked.connect(self._play_selected_game)
        row.addWidget(btn_live); row.addWidget(btn_pkg); lay.addLayout(row)

        net = QGroupBox("📶 Local Wi‑Fi / Ethernet game session")
        nf = QFormLayout(net)
        self.cmb_game_net_mode = QComboBox(); self.cmb_game_net_mode.addItems(["Solo", "Host on local network", "Join local network"]); nf.addRow("Mode", self.cmb_game_net_mode)
        self.spin_game_port = QSpinBox(); self.spin_game_port.setRange(1024,65535); self.spin_game_port.setValue(27777); nf.addRow("Port", self.spin_game_port)
        self.edit_game_connect = QLineEdit(); self.edit_game_connect.setPlaceholderText("host-ip:port  e.g. 192.168.1.42:27777"); nf.addRow("Join address", self.edit_game_connect)
        self.lbl_game_lan = QLabel(f"This box: {self._lan_ip()} · same Wi‑Fi/LAN required unless your router/firewall forwards the port.")
        self.lbl_game_lan.setWordWrap(True); self.lbl_game_lan.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); nf.addRow("Local address", self.lbl_game_lan)
        lay.addWidget(net)
        hint = QLabel("Host and Join use the game engine's authoritative TCP snapshot/input transport. This is live game-state networking—not merely sharing a .zip. Keyboard, mouse/gamepad and touch input remain local on each machine.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#8ab4c8; font-size:9pt;"); lay.addWidget(hint)
        lay.addStretch(1); return w

    def _play_live_game(self):
        if hasattr(self.host, "_on_play_videogame"):
            try:
                mode = self.cmb_game_net_mode.currentIndex() if hasattr(self, "cmb_game_net_mode") else 0
                setattr(self.host, "_preferred_game_net_mode", int(mode))
                setattr(self.host, "_preferred_game_net_port", int(self.spin_game_port.value()) if hasattr(self, "spin_game_port") else 27777)
                setattr(self.host, "_preferred_game_connect", self.edit_game_connect.text().strip() if hasattr(self, "edit_game_connect") else "")
                self.host._on_play_videogame()
                self.lbl_status.setText("Live game dialog opened.")
            except Exception as e:
                QMessageBox.warning(self, "Game", str(e))
        else:
            QMessageBox.warning(self, "Game", "Host has no video-game player.")

    def _play_selected_game(self):
        for path in self._selected_paths():
            if path.lower().endswith(".zip"):
                self._play_game_package(path)
                return
        QMessageBox.information(self, "Game", "Select a .zip game package in the browser.")

    def _play_game_package(self, path: str):
        try:
            td = tempfile.mkdtemp(prefix="gb_game_pkg_")
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(td)
            script = None
            for root, _dirs, files in os.walk(td):
                for f in files:
                    if f.endswith(".py") and ("game" in f.lower() or f.startswith("play")):
                        script = os.path.join(root, f)
                        break
                if script:
                    break
            if script is None:
                # any .py
                for root, _dirs, files in os.walk(td):
                    for f in files:
                        if f.endswith(".py"):
                            script = os.path.join(root, f)
                            break
                    if script:
                        break
            if not script:
                raise RuntimeError("No Python game script found inside the package.")
            args = [sys.executable, script]
            mode = self.cmb_game_net_mode.currentIndex() if hasattr(self, "cmb_game_net_mode") else 0
            port = int(self.spin_game_port.value()) if hasattr(self, "spin_game_port") else 27777
            if mode == 1:
                args += ["--host", f"--port={port}"]
            elif mode == 2:
                addr = self.edit_game_connect.text().strip() if hasattr(self, "edit_game_connect") else ""
                if not addr:
                    raise RuntimeError("Enter the host IP:port before joining a local-network game.")
                if ":" not in addr:
                    addr = f"{addr}:{port}"
                args.append(f"--connect={addr}")
            subprocess.Popen(args, cwd=os.path.dirname(script))
            self.lbl_status.setText(f"Game launched: {os.path.basename(path)}")
            self.cmb_game_status.setText(f"Running: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Game package", str(e))

    # ------------------------------------------------------------------ remix tab
    def _build_remix_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Parametric live remixer</b>"))
        lay.addWidget(QLabel(
            "Drives the host Live DJ GOAVA morph + RAND PARAM macro on the play buffer."
        ))

        form = QFormLayout()
        self.sld_goava = QSlider(Qt.Orientation.Horizontal)
        self.sld_goava.setRange(0, 100)
        self.sld_goava.setValue(0)
        self.sld_goava.valueChanged.connect(self._push_remix)
        form.addRow("GOAVA morph %", self.sld_goava)

        self.sld_rand = QSlider(Qt.Orientation.Horizontal)
        self.sld_rand.setRange(0, 100)
        self.sld_rand.setValue(0)
        self.sld_rand.valueChanged.connect(self._push_remix)
        form.addRow("RAND PARAM %", self.sld_rand)

        self.spin_remix_pair_a = QSpinBox()
        self.spin_remix_pair_a.setRange(0, 47)
        self.spin_remix_pair_b = QSpinBox()
        self.spin_remix_pair_b.setRange(0, 47)
        self.spin_remix_pair_b.setValue(1)
        pair_row = QHBoxLayout()
        pair_row.addWidget(self.spin_remix_pair_a)
        pair_row.addWidget(QLabel("↔"))
        pair_row.addWidget(self.spin_remix_pair_b)
        form.addRow("Pair (A↔B)", pair_row)
        self.spin_remix_pair_a.valueChanged.connect(self._push_remix)
        self.spin_remix_pair_b.valueChanged.connect(self._push_remix)

        self.sld_boost = QSlider(Qt.Orientation.Horizontal)
        self.sld_boost.setRange(0, 100)
        self.sld_boost.setValue(0)
        self.sld_boost.valueChanged.connect(self._push_remix)
        form.addRow("Boost hit %", self.sld_boost)

        lay.addLayout(form)

        row = QHBoxLayout()
        btn_apply = QPushButton("Apply to Live DJ")
        btn_apply.clicked.connect(self._push_remix)
        btn_arm = QPushButton("Arm GOAVA + RAND on host toggles")
        btn_arm.clicked.connect(self._arm_host_dj_toggles)
        row.addWidget(btn_apply)
        row.addWidget(btn_arm)
        lay.addLayout(row)

        self.lbl_remix = QLabel("Remix amounts at 0 — dry.")
        self.lbl_remix.setStyleSheet("color:#f5d97d;")
        lay.addWidget(self.lbl_remix)

        script_group = QGroupBox("Continuous Pattern Script")
        sg = QVBoxLayout(script_group)
        self.txt_pattern_script = QTextEdit()
        self.txt_pattern_script.setMaximumHeight(122)
        self.txt_pattern_script.setPlainText(
            "goava = 50 + 45*sin(t*0.73)\n"
            "rand = 25 + 25*sin(t*1.31 + 1.2)\n"
            "boost = 18 + 18*(sin(t*2.0)>0.72)\n"
            "speed = 1.0 + 0.22*sin(t*0.41)\n"
            "advance = (step % 64 == 0)"
        )
        self.txt_pattern_script.setToolTip(
            "Control-rate expressions. Available: t, step, sin/cos/tan, abs/min/max, "
            "sqrt, pi, rand(). Assign goava/rand/boost (0..100), speed (0.25..4), "
            "advance (true to go to next media-playlist item), and host (0..1 automation value)."
        )
        sg.addWidget(self.txt_pattern_script)
        sr = QHBoxLayout()
        self.spin_pattern_hz = QSpinBox()
        self.spin_pattern_hz.setRange(1, 60)
        self.spin_pattern_hz.setValue(20)
        self.spin_pattern_hz.setSuffix(" Hz")
        self.spin_pattern_hz.valueChanged.connect(self._set_pattern_rate)
        self.spin_pattern_seed = QSpinBox()
        self.spin_pattern_seed.setRange(0, 2147483647)
        self.spin_pattern_seed.setValue(1975807343)
        btn_pattern = QPushButton("▶ Run Pattern")
        btn_pattern.setCheckable(True)
        btn_pattern.toggled.connect(self._toggle_pattern_script)
        btn_pattern_once = QPushButton("Step once")
        btn_pattern_once.clicked.connect(self._pattern_tick)
        sr.addWidget(QLabel("Rate")); sr.addWidget(self.spin_pattern_hz)
        sr.addWidget(QLabel("Seed")); sr.addWidget(self.spin_pattern_seed)
        sr.addWidget(btn_pattern); sr.addWidget(btn_pattern_once)
        sg.addLayout(sr)
        self.chk_pattern_host_playlist = QCheckBox("Write continuous host playlist automation pattern")
        self.chk_pattern_host_playlist.setChecked(True)
        sg.addWidget(self.chk_pattern_host_playlist)
        self.lbl_pattern = QLabel("Pattern stopped.")
        self.lbl_pattern.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        sg.addWidget(self.lbl_pattern)
        lay.addWidget(script_group)
        lay.addStretch(1)
        return w

    def _push_remix(self, *_args):
        host = self.host
        goava = self.sld_goava.value() / 100.0
        rand = self.sld_rand.value() / 100.0
        boost = self.sld_boost.value() / 100.0
        a = int(self.spin_remix_pair_a.value())
        b = int(self.spin_remix_pair_b.value())
        try:
            eng = getattr(host, "_live_dj_engine", None)
            if eng is None:
                from dj_effects import LiveDJEffects
                sr = int(getattr(host, "play_sample_rate", 48000) or 48000)
                eng = LiveDJEffects(sample_rate=sr)
                host._live_dj_engine = eng
            seed = 0.0
            try:
                if hasattr(host, "get_numeric_seed"):
                    seed = float(host.get_numeric_seed())
            except Exception:
                pass
            eng.set_context(seed=seed, pair=(a, b),
                            sample_rate=int(getattr(host, "play_sample_rate", 48000) or 48000))
            eng.amount_goava = float(goava)
            eng.amount_random = float(rand)
            if boost > 1e-6:
                # ~1 bar at 120 BPM default
                sr = float(getattr(host, "play_sample_rate", 48000) or 48000)
                interval = int(sr * 2.0)
                eng.set_boost(interval=interval, phase=0.0, amount=boost)
            else:
                eng.set_boost(0, 0.0, 0.0)
            host._live_dj_pair_ids = (a, b)
            self.lbl_remix.setText(
                f"GOAVA {goava*100:.0f}% · RAND {rand*100:.0f}% · boost {boost*100:.0f}% · pair {a}↔{b}"
            )
            self.lbl_status.setText("Parametric remix pushed to Live DJ engine.")
        except Exception as e:
            self.lbl_remix.setText(f"Remix error: {e}")

    @staticmethod
    def _safe_pattern_eval(expr: str, env: Dict[str, Any]) -> Any:
        node = ast.parse(expr, mode="eval")
        allowed = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
                   ast.BoolOp, ast.Compare, ast.Call, ast.Add, ast.Sub, ast.Mult, ast.Div,
                   ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.And, ast.Or, ast.Not,
                   ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
        for n in ast.walk(node):
            if not isinstance(n, allowed):
                raise ValueError(f"unsupported script syntax: {type(n).__name__}")
            if isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or n.func.id not in env):
                raise ValueError("only listed math functions may be called")
        return eval(compile(node, "<media-pattern>", "eval"), {"__builtins__": {}}, env)

    def _set_pattern_rate(self, hz: int):
        self._pattern_timer.setInterval(max(16, int(round(1000.0 / max(1, hz)))))

    def _toggle_pattern_script(self, on: bool):
        if on:
            self._pattern_phase = 0.0
            self._pattern_step = 0
            self._pattern_rng.seed(int(self.spin_pattern_seed.value()))
            self._set_pattern_rate(self.spin_pattern_hz.value())
            self._pattern_timer.start()
            self.lbl_pattern.setText("Pattern running.")
        else:
            self._pattern_timer.stop()
            self.lbl_pattern.setText("Pattern stopped.")

    def _pattern_tick(self):
        hz = max(1, int(getattr(self, "spin_pattern_hz", None).value() if hasattr(self, "spin_pattern_hz") else 20))
        t = self._pattern_phase
        step = self._pattern_step
        env = {
            "t": t, "step": step, "pi": math.pi, "e": math.e,
            "sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt,
            "abs": abs, "min": min, "max": max,
            "rand": self._pattern_rng.random,
        }
        values: Dict[str, Any] = {}
        try:
            for raw in self.txt_pattern_script.toPlainText().splitlines():
                line = raw.split("#", 1)[0].strip()
                if not line or "=" not in line:
                    continue
                key, expr = line.split("=", 1)
                key = key.strip().lower()
                if key not in {"goava", "rand", "boost", "speed", "advance", "host"}:
                    continue
                values[key] = self._safe_pattern_eval(expr.strip(), dict(env, **values))
            if "goava" in values:
                self.sld_goava.setValue(max(0, min(100, int(round(float(values["goava"]))))))
            if "rand" in values:
                self.sld_rand.setValue(max(0, min(100, int(round(float(values["rand"]))))))
            if "boost" in values:
                self.sld_boost.setValue(max(0, min(100, int(round(float(values["boost"]))))))
            if "speed" in values and hasattr(self, "sld_live_speed"):
                self.sld_live_speed.setValue(max(25, min(400, int(round(float(values["speed"]) * 100.0)))))
            if bool(values.get("advance", False)) and self._playlist:
                self._playlist_next()
            if self.chk_pattern_host_playlist.isChecked():
                self._write_host_pattern_value(values.get("host", values.get("goava", 0.0) / 100.0), step)
            self.lbl_pattern.setText(
                f"t={t:.2f} · step={step} · G={self.sld_goava.value()} R={self.sld_rand.value()} "
                f"B={self.sld_boost.value()} · speed={self._live_speed:.2f}×"
            )
        except Exception as e:
            self.lbl_pattern.setText(f"Pattern error: {e}")
            self._pattern_timer.stop()
        self._pattern_step += 1
        self._pattern_phase += 1.0 / float(hz)

    def _write_host_pattern_value(self, value: Any, step: int):
        """Write sparse, bounded control-rate data into the host playlist automation.
        This is intentionally tiny: one scalar per playlist row, refreshed in-place."""
        try:
            rows = getattr(self.host, "master_playlist_data", None) or []
            if not rows:
                return
            row = int(step) % len(rows)
            entry = rows[row]
            if not isinstance(entry, dict):
                entry = {}; rows[row] = entry
            v = max(0.0, min(1.0, float(value)))
            entry["media_hub_pattern"] = v
            entry["media_hub_pattern_step"] = int(step)
            # Also expose through playlist_automation without replacing canonical fields.
            pa = getattr(self.host, "playlist_automation", None)
            if isinstance(pa, list):
                while len(pa) <= row:
                    pa.append({})
                if not isinstance(pa[row], dict):
                    pa[row] = {}
                pa[row]["media_hub_pattern"] = v
        except Exception:
            pass

    def _arm_host_dj_toggles(self):
        self._push_remix()
        try:
            if hasattr(self.host, "btn_live_dj_goava") and self.sld_goava.value() > 0:
                self.host.btn_live_dj_goava.setChecked(True)
            if hasattr(self.host, "btn_live_dj_random") and self.sld_rand.value() > 0:
                self.host.btn_live_dj_random.setChecked(True)
        except Exception:
            pass

    # ------------------------------------------------------------------ cutup lab
    def _build_cutup_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Geometric Phaselocked Cutup Lab</b>"))
        intro = QLabel(
            "Load an audio file, optionally normalize its detected pitch, then create a deterministic beat/cutup. "
            "Slice choice, pitch, rate, reversal and resampling are generated from one seed on a phaselocked geometric lattice."
        )
        intro.setWordWrap(True)
        lay.addWidget(intro)

        src_row = QHBoxLayout()
        self.lbl_cutup_source = QLabel("No sample loaded")
        self.lbl_cutup_source.setWordWrap(True)
        btn_sel = QPushButton("Use selected audio")
        btn_sel.clicked.connect(self._cutup_use_selected)
        btn_browse = QPushButton("Load sample…")
        btn_browse.clicked.connect(self._cutup_browse)
        src_row.addWidget(self.lbl_cutup_source, stretch=1)
        src_row.addWidget(btn_sel)
        src_row.addWidget(btn_browse)
        lay.addLayout(src_row)
        self._cutup_source_path = None
        self._cutup_video_path = None
        self._cutup_events = []
        self._cutup_pitch_shift = 0.0

        vrow = QHBoxLayout()
        self.lbl_cutup_video = QLabel("No video source (optional)")
        self.lbl_cutup_video.setWordWrap(True)
        btn_vsel = QPushButton("Use selected video")
        btn_vsel.clicked.connect(self._cutup_use_selected_video)
        btn_vbrowse = QPushButton("Load video…")
        btn_vbrowse.clicked.connect(self._cutup_browse_video)
        vrow.addWidget(self.lbl_cutup_video, stretch=1); vrow.addWidget(btn_vsel); vrow.addWidget(btn_vbrowse)
        lay.addLayout(vrow)

        norm = QGroupBox("Pitch normalization")
        nf = QFormLayout(norm)
        self.spin_cutup_target_hz = QDoubleSpinBox()
        self.spin_cutup_target_hz.setRange(0.0, 20000.0)
        self.spin_cutup_target_hz.setDecimals(3)
        self.spin_cutup_target_hz.setValue(0.0)
        self.spin_cutup_target_hz.setSpecialValueText("Nearest C-major pitch")
        self.spin_cutup_target_hz.setToolTip("0 = detect a stable fundamental and move it to the nearest C-major pitch. Enter Hz for an exact target.")
        nf.addRow("Target pitch", self.spin_cutup_target_hz)
        nrow = QHBoxLayout()
        btn_an = QPushButton("Analyze pitch")
        btn_an.clicked.connect(self._cutup_analyze_pitch)
        btn_nr = QPushButton("Render normalized copy…")
        btn_nr.clicked.connect(self._cutup_render_normalized)
        nrow.addWidget(btn_an); nrow.addWidget(btn_nr)
        nf.addRow(nrow)
        self.lbl_cutup_pitch = QLabel("Pitch not analyzed.")
        self.lbl_cutup_pitch.setWordWrap(True)
        nf.addRow(self.lbl_cutup_pitch)
        lay.addWidget(norm)

        gen = QGroupBox("Seeded beat / file cutup")
        form = QFormLayout(gen)
        self.spin_cutup_bpm = QDoubleSpinBox(); self.spin_cutup_bpm.setRange(20.0, 400.0); self.spin_cutup_bpm.setValue(120.0); self.spin_cutup_bpm.setDecimals(2)
        self.spin_cutup_bars = QSpinBox(); self.spin_cutup_bars.setRange(1, 256); self.spin_cutup_bars.setValue(4)
        self.spin_cutup_steps = QSpinBox(); self.spin_cutup_steps.setRange(1, 64); self.spin_cutup_steps.setValue(16)
        self.spin_cutup_divs = QSpinBox(); self.spin_cutup_divs.setRange(1, 1024); self.spin_cutup_divs.setValue(32)
        self.spin_cutup_phase = QSpinBox(); self.spin_cutup_phase.setRange(1, 64); self.spin_cutup_phase.setValue(4)
        self.spin_cutup_seed = QSpinBox(); self.spin_cutup_seed.setRange(0, 2147483647); self.spin_cutup_seed.setValue(1975807343)
        self.spin_cutup_pitch_range = QDoubleSpinBox(); self.spin_cutup_pitch_range.setRange(0.0, 48.0); self.spin_cutup_pitch_range.setValue(7.0); self.spin_cutup_pitch_range.setSuffix(" st")
        self.spin_cutup_rate_depth = QDoubleSpinBox(); self.spin_cutup_rate_depth.setRange(0.0, 3.0); self.spin_cutup_rate_depth.setSingleStep(0.05); self.spin_cutup_rate_depth.setValue(0.20)
        self.spin_cutup_reverse = QDoubleSpinBox(); self.spin_cutup_reverse.setRange(0.0, 1.0); self.spin_cutup_reverse.setSingleStep(0.05); self.spin_cutup_reverse.setValue(0.12)
        self.cmb_cutup_resample = QComboBox(); self.cmb_cutup_resample.addItems(["preserve-duration", "tape"])
        form.addRow("BPM", self.spin_cutup_bpm)
        form.addRow("Bars", self.spin_cutup_bars)
        form.addRow("Steps / bar", self.spin_cutup_steps)
        form.addRow("Source slice divisions", self.spin_cutup_divs)
        form.addRow("Phase-lock group", self.spin_cutup_phase)
        form.addRow("Seed", self.spin_cutup_seed)
        form.addRow("Pitch modulation", self.spin_cutup_pitch_range)
        form.addRow("Rate depth", self.spin_cutup_rate_depth)
        form.addRow("Reverse probability", self.spin_cutup_reverse)
        form.addRow("Resampling", self.cmb_cutup_resample)
        lay.addWidget(gen)

        crow = QHBoxLayout()
        btn_gen = QPushButton("Generate cut pattern")
        btn_gen.clicked.connect(self._cutup_generate)
        btn_render = QPushButton("Render cutup / beat…")
        btn_render.clicked.connect(self._cutup_render)
        btn_playlist = QPushButton("Seed playlist from same geometry")
        btn_playlist.clicked.connect(self._cutup_seed_playlist)
        btn_av = QPushButton("Render A/V cutup…")
        btn_av.clicked.connect(self._cutup_render_av)
        btn_auto = QPushButton("▶ Auto render + replay/broadcast")
        btn_auto.clicked.connect(self._cutup_auto_perform)
        crow.addWidget(btn_gen); crow.addWidget(btn_render); crow.addWidget(btn_playlist); crow.addWidget(btn_av); crow.addWidget(btn_auto)
        lay.addLayout(crow)
        self.lbl_cutup_pattern = QLabel("No cut pattern generated.")
        self.lbl_cutup_pattern.setWordWrap(True)
        self.lbl_cutup_pattern.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        lay.addWidget(self.lbl_cutup_pattern)
        lay.addStretch(1)
        return w

    def _cutup_use_selected(self):
        for path in self._selected_paths():
            if os.path.isfile(path) and os.path.splitext(path)[1].lower() in AUDIO_EXT:
                self._cutup_set_source(path)
                return
        QMessageBox.information(self, "Cutup Lab", "Select an audio file in the Performance browser first.")

    def _cutup_browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load sample", self._host_samples_dir(), "Audio (*.wav *.flac *.mp3 *.ogg *.opus *.aiff *.aif *.caf);;All files (*)")
        if path:
            self._cutup_set_source(path)

    def _cutup_use_selected_video(self):
        for path in self._selected_paths():
            if os.path.isfile(path) and os.path.splitext(path)[1].lower() in VIDEO_EXT:
                self._cutup_video_path = os.path.abspath(path)
                self.lbl_cutup_video.setText(os.path.basename(path))
                return
        QMessageBox.information(self, "Cutup Lab", "Select a video file in the Performance browser first.")

    def _cutup_browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load video source", self._host_exports_dir(), "Video (*.mp4 *.webm *.avi *.mov *.mkv);;All files (*)")
        if path:
            self._cutup_video_path = os.path.abspath(path)
            self.lbl_cutup_video.setText(os.path.basename(path))

    def _cutup_set_source(self, path: str):
        self._cutup_source_path = os.path.abspath(path)
        self._cutup_events = []
        self._cutup_pitch_shift = 0.0
        self.lbl_cutup_source.setText(os.path.basename(path))
        self.lbl_cutup_pitch.setText("Pitch not analyzed.")
        self.lbl_cutup_pattern.setText("Source loaded. Generate a pattern or analyze pitch.")

    def _cutup_analyze_pitch(self):
        path = self._cutup_source_path
        if not path or not os.path.isfile(path):
            self._cutup_use_selected(); path = self._cutup_source_path
        if not path:
            return
        try:
            from media_cutup_engine import pitch_normalization_shift
            target = float(self.spin_cutup_target_hz.value())
            detected, shift, msg = pitch_normalization_shift(path, target_hz=(target if target > 0 else None), root_midi=60)
            self._cutup_pitch_shift = float(shift)
            self.lbl_cutup_pitch.setText(msg)
            self.lbl_status.setText("Pitch analysis complete." if detected is not None else msg)
        except Exception as e:
            QMessageBox.warning(self, "Pitch analysis", str(e))

    def _cutup_render_normalized(self):
        path = self._cutup_source_path
        if not path or not os.path.isfile(path):
            self._cutup_use_selected(); path = self._cutup_source_path
        if not path:
            return
        self._cutup_analyze_pitch()
        base = os.path.splitext(os.path.basename(path))[0] + "_pitch_normalized.wav"
        out, _ = QFileDialog.getSaveFileName(self, "Render normalized sample", os.path.join(self._host_exports_dir(), base), "WAV (*.wav);;FLAC (*.flac)")
        if not out:
            return
        try:
            from media_cutup_engine import render_pitch_normalized
            out = render_pitch_normalized(path, out, self._cutup_pitch_shift, preserve_duration=True)
            self.lbl_status.setText(f"Pitch-normalized sample rendered: {os.path.basename(out)}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Pitch normalization", str(e))

    def _cutup_generate(self):
        path = self._cutup_source_path
        if not path or not os.path.isfile(path):
            self._cutup_use_selected(); path = self._cutup_source_path
        if not path:
            return
        try:
            from media_cutup_engine import generate_cut_events, probe_duration
            dur = probe_duration(path)
            if dur <= 0:
                raise RuntimeError("Could not determine sample duration")
            self._cutup_events = generate_cut_events(
                dur,
                bpm=float(self.spin_cutup_bpm.value()), bars=int(self.spin_cutup_bars.value()),
                steps_per_bar=int(self.spin_cutup_steps.value()), seed=int(self.spin_cutup_seed.value()),
                slice_divisions=int(self.spin_cutup_divs.value()), pitch_range_st=float(self.spin_cutup_pitch_range.value()),
                rate_depth=float(self.spin_cutup_rate_depth.value()), reverse_probability=float(self.spin_cutup_reverse.value()),
                normalize_shift_st=float(self._cutup_pitch_shift), phase_lock=int(self.spin_cutup_phase.value()),
            )
            ev = self._cutup_events[:4]
            preview = " · ".join(f"#{e.step}: {e.start_s:.2f}s {e.pitch_semitones:+.2f}st {e.rate:.2f}×{' REV' if e.reverse else ''}" for e in ev)
            self.lbl_cutup_pattern.setText(f"{len(self._cutup_events)} phaselocked events generated. {preview}")
            self.lbl_status.setText("Cutup pattern generated deterministically from seed.")
        except Exception as e:
            QMessageBox.warning(self, "Cutup pattern", str(e))

    def _cutup_render(self):
        if not self._cutup_events:
            self._cutup_generate()
        if not self._cutup_events or not self._cutup_source_path:
            return
        base = os.path.splitext(os.path.basename(self._cutup_source_path))[0] + f"_cutup_{int(self.spin_cutup_seed.value())}.wav"
        out, _ = QFileDialog.getSaveFileName(self, "Render cutup / beat", os.path.join(self._host_exports_dir(), base), "WAV (*.wav);;FLAC (*.flac);;MP3 (*.mp3);;Opus (*.opus);;OGG (*.ogg)")
        if not out:
            return
        try:
            from media_cutup_engine import render_cutup
            out = render_cutup(
                self._cutup_source_path, out, self._cutup_events,
                bpm=float(self.spin_cutup_bpm.value()), steps_per_bar=int(self.spin_cutup_steps.value()),
                sample_rate=int(getattr(self.host, "play_sample_rate", 48000) or 48000),
                resample_mode=self.cmb_cutup_resample.currentText(), normalize_peak=True,
            )
            self.lbl_status.setText(f"Cutup rendered: {os.path.basename(out)}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Cutup render", str(e))

    def _cutup_seed_playlist(self):
        if not self._playlist:
            self._add_to_playlist()
        if not self._playlist:
            QMessageBox.information(self, "Cutup Lab", "Add media to the Performance playlist first.")
            return
        try:
            from media_cutup_engine import playlist_geometric_parameters
            params = playlist_geometric_parameters(
                len(self._playlist), int(self.spin_cutup_seed.value()),
                pitch_range_st=float(self.spin_cutup_pitch_range.value()),
                rate_depth=float(self.spin_cutup_rate_depth.value()), phase_lock=int(self.spin_cutup_phase.value()),
            )
            decorated = []
            for item, param in zip(self._playlist, params):
                item.update(param)
                decorated.append((float(param["geometry_key"]), item))
            decorated.sort(key=lambda pair: pair[0])
            self._playlist = [item for _key, item in decorated]
            self._playlist_index = 0
            self._refresh_playlist_widget()
            self.lbl_status.setText("Playlist selection/pitch/rate/resampling seeded from Cutup Lab geometry.")
        except Exception as e:
            QMessageBox.warning(self, "Seed playlist", str(e))

    def _cutup_render_av(self, output_path: Optional[str] = None):
        if not self._cutup_events:
            self._cutup_generate()
        if not self._cutup_events or not self._cutup_source_path:
            return None
        if not self._cutup_video_path or not os.path.isfile(self._cutup_video_path):
            self._cutup_use_selected_video()
        if not self._cutup_video_path:
            return None
        if output_path is None:
            base = os.path.splitext(os.path.basename(self._cutup_source_path))[0] + f"_avcutup_{int(self.spin_cutup_seed.value())}.mp4"
            output_path, _ = QFileDialog.getSaveFileName(self, "Render audiovisual cutup", os.path.join(self._host_exports_dir(), base), "MP4 (*.mp4)")
            if not output_path:
                return None
        try:
            from media_cutup_engine import render_av_cutup
            out = render_av_cutup(
                self._cutup_source_path, self._cutup_video_path, output_path, self._cutup_events,
                bpm=float(self.spin_cutup_bpm.value()), steps_per_bar=int(self.spin_cutup_steps.value()),
                sample_rate=int(getattr(self.host, "play_sample_rate", 48000) or 48000),
                resample_mode=self.cmb_cutup_resample.currentText(),
                video_fps=int(getattr(self.host, "_last_export_fps", 30) or 30),
            )
            self.lbl_status.setText(f"A/V cutup rendered: {os.path.basename(out)}")
            self.refresh()
            return out
        except Exception as e:
            QMessageBox.warning(self, "A/V cutup render", str(e))
            return None

    def _cutup_auto_perform(self):
        """One-click deterministic render -> replay -> game/network broadcast."""
        if not self._cutup_events:
            self._cutup_generate()
        if not self._cutup_events:
            return
        os.makedirs(self._host_exports_dir(), exist_ok=True)
        seed = int(self.spin_cutup_seed.value())
        if self._cutup_video_path and os.path.isfile(self._cutup_video_path):
            out = os.path.join(self._host_exports_dir(), f"auto_avcutup_{seed}.mp4")
            rendered = self._cutup_render_av(out)
        else:
            out = os.path.join(self._host_exports_dir(), f"auto_cutup_{seed}.wav")
            try:
                from media_cutup_engine import render_cutup
                rendered = render_cutup(
                    self._cutup_source_path, out, self._cutup_events,
                    bpm=float(self.spin_cutup_bpm.value()), steps_per_bar=int(self.spin_cutup_steps.value()),
                    sample_rate=int(getattr(self.host, "play_sample_rate", 48000) or 48000),
                    resample_mode=self.cmb_cutup_resample.currentText(), normalize_peak=True,
                )
            except Exception as e:
                QMessageBox.warning(self, "Auto performance", str(e)); return
        if rendered:
            self._start_performance(rendered, loop=True)

    # ------------------------------------------------------------------ live performance / ethernet
    def _build_performance_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Phaselocked Live Broadcast</b>"))
        txt = QLabel("Replays the generated beat/A/V cutup while broadcasting the exact same step, phase, pitch, rate and slice state to the game runtime and optional Ethernet clients.")
        txt.setWordWrap(True); lay.addWidget(txt)
        self.chk_perf_loop = QCheckBox("Loop replay continuously"); self.chk_perf_loop.setChecked(True); lay.addWidget(self.chk_perf_loop)
        self.chk_perf_game = QCheckBox("Broadcast canonical cutup state to game runtime"); self.chk_perf_game.setChecked(True); lay.addWidget(self.chk_perf_game)
        row = QHBoxLayout()
        bstart = QPushButton("▶ Start current cutup broadcast"); bstart.clicked.connect(lambda: self._start_performance(self._performance_media_path, self.chk_perf_loop.isChecked()))
        bstop = QPushButton("■ Stop broadcast"); bstop.clicked.connect(self._stop_performance)
        row.addWidget(bstart); row.addWidget(bstop); lay.addLayout(row)
        qos = QGroupBox("Live quality / canonical projection")
        qf = QFormLayout(qos)
        self.cmb_perf_qos = QComboBox(); self.cmb_perf_qos.addItems(["Auto (recommended)", "Low-latency", "Full detail"]); qf.addRow("Performance QoS", self.cmb_perf_qos)
        self.chk_relativity = QCheckBox("Relativity projection (downstream; preserves canonical ID)"); self.chk_relativity.setChecked(False); qf.addRow(self.chk_relativity)
        self.spin_relativity_beta = QDoubleSpinBox(); self.spin_relativity_beta.setRange(-0.99,0.99); self.spin_relativity_beta.setDecimals(4); self.spin_relativity_beta.setSingleStep(0.01); self.spin_relativity_beta.setValue(0.0); qf.addRow("β = v/c", self.spin_relativity_beta)
        self.spin_relativity_amount = QDoubleSpinBox(); self.spin_relativity_amount.setRange(0.0,8.0); self.spin_relativity_amount.setDecimals(3); self.spin_relativity_amount.setValue(1.0); qf.addRow("Projection amount", self.spin_relativity_amount)
        self.lbl_relativity_credit = QLabel("Standard SR math · NASA Trick/cFS/CML credited as simulation-engineering inspiration · no NASA code copied")
        self.lbl_relativity_credit.setWordWrap(True); self.lbl_relativity_credit.setStyleSheet("color:#91b9c9;font-size:8pt;"); qf.addRow(self.lbl_relativity_credit)
        lay.addWidget(qos)
        net = QGroupBox("Ethernet host"); nf = QFormLayout(net)
        self.spin_remote_port = QSpinBox(); self.spin_remote_port.setRange(1024, 65535); self.spin_remote_port.setValue(8765); nf.addRow("Port", self.spin_remote_port)
        self.lbl_remote = QLabel("Stopped"); self.lbl_remote.setWordWrap(True); nf.addRow("Status", self.lbl_remote)
        nr = QHBoxLayout(); bon = QPushButton("Start LAN host"); bon.clicked.connect(self._start_remote_server); boff = QPushButton("Stop LAN host"); boff.clicked.connect(self._stop_remote_server); nr.addWidget(bon); nr.addWidget(boff); nf.addRow(nr)
        lay.addWidget(net)
        radio = QGroupBox("◉ GOAVA LAN Radio · 192 kbps MP3")
        rf = QVBoxLayout(radio)
        self.lbl_radio_status = QLabel("Radio stopped")
        self.lbl_radio_status.setWordWrap(True); rf.addWidget(self.lbl_radio_status)
        rr = QHBoxLayout()
        rstart = QPushButton("▶ Start Radio + discovery"); rstart.clicked.connect(self._start_goava_radio)
        rstop = QPushButton("■ Stop Radio"); rstop.clicked.connect(self._stop_goava_radio)
        rrefresh = QPushButton("↻ Nearby Radios"); rrefresh.clicked.connect(self._refresh_radio_peers)
        rr.addWidget(rstart); rr.addWidget(rstop); rr.addWidget(rrefresh); rf.addLayout(rr)
        self.lst_radio_peers = QListWidget(); self.lst_radio_peers.setMaximumHeight(132); rf.addWidget(self.lst_radio_peers)
        hint = QLabel("OS/appliance helper can redirect TCP/80 → Radio :8780 so nearby devices can open http://device/ directly.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#8ab4c8;font-size:9pt;"); rf.addWidget(hint)
        lay.addWidget(radio); lay.addStretch(1); return w

    def _start_goava_radio(self):
        try:
            from radio_station import RadioStationService
            if self._goava_radio_service is None:
                roots = [self._host_projects_dir(), self._host_exports_dir(), self._host_samples_dir()]
                self._goava_radio_service = RadioStationService(roots=roots, port=8780)
            url = self._goava_radio_service.start()
            self.lbl_radio_status.setText(f"Broadcasting: {url} · 192 kbps MP3")
            self._radio_peer_timer.start(); self._refresh_radio_peers()
        except Exception as e:
            QMessageBox.warning(self, "GOAVA Radio", str(e))

    def _stop_goava_radio(self):
        try:
            if self._goava_radio_service is not None: self._goava_radio_service.stop()
        except Exception: pass
        self._goava_radio_service = None
        self._radio_peer_timer.stop()
        if hasattr(self, "lbl_radio_status"): self.lbl_radio_status.setText("Radio stopped")

    def _refresh_radio_peers(self):
        if not hasattr(self, "lst_radio_peers"): return
        self.lst_radio_peers.clear()
        svc = self._goava_radio_service
        peers = svc.peer_list() if svc is not None else []
        if not peers:
            self.lst_radio_peers.addItem("No nearby Groovebox radios discovered yet.")
            return
        for p in peers:
            self.lst_radio_peers.addItem(f"{p.get('name','Radio')}  ·  {p.get('url','')}")

    def _start_performance(self, media_path: Optional[str] = None, loop: bool = True):
        if not self._cutup_events:
            self._cutup_generate()
        if not self._cutup_events:
            return
        if media_path and os.path.isfile(media_path):
            self._performance_media_path = media_path
            self._stop_player()
            cmd = _find_player()
            if cmd:
                player_name = os.path.basename(cmd[0]).lower()
                if player_name.startswith("mpv") and loop:
                    cmd = list(cmd) + ["--loop-file=inf"]
                elif player_name.startswith("vlc") and loop:
                    cmd = list(cmd) + ["--loop"]
                try:
                    cmd, penv = self._routed_player(cmd, want_video=(os.path.splitext(media_path)[1].lower() in VIDEO_EXT))
                    self._player_proc = subprocess.Popen(cmd + [media_path], env=penv)
                    # VLC can otherwise hand a file to an existing instance and make
                    # the child disappear immediately. --no-one-instance above avoids
                    # that; a short deferred poll still surfaces real launch failures.
                    QTimer.singleShot(450, lambda p=self._player_proc, mp=media_path: self._check_player_launch(p, mp))
                    try:
                        if self._media_share_server is not None:
                            self._media_share_server.set_current(media_path)
                    except Exception:
                        pass
                except Exception:
                    pass
        self._performance_loop = bool(loop)
        self._performance_step = 0
        step_ms = max(10, int(round((60.0 / float(self.spin_cutup_bpm.value()) * 4.0 / int(self.spin_cutup_steps.value())) * 1000.0)))
        self._performance_timer.setInterval(step_ms)
        self._performance_timer.start()
        self._broadcast_state = {"active": True, "step": 0, "seed": int(self.spin_cutup_seed.value())}
        self.lbl_status.setText("Phaselocked replay/game/Ethernet broadcast active.")

    def _performance_tick(self):
        if not self._cutup_events:
            self._stop_performance(); return
        idx = self._performance_step % len(self._cutup_events)
        ev = self._cutup_events[idx]
        state = {
            "active": True, "event_index": idx, "step": int(ev.step), "phase": float(ev.phase),
            "pitch_semitones": float(ev.pitch_semitones), "rate": float(ev.rate), "gain": float(ev.gain),
            "pan": float(ev.pan), "reverse": bool(ev.reverse), "source_start_s": float(ev.start_s),
            "source_duration_s": float(ev.duration_s), "seed": int(self.spin_cutup_seed.value()),
            "bpm": float(self.spin_cutup_bpm.value()), "timestamp": time.time(),
        }
        if getattr(self, "chk_relativity", None) is not None and self.chk_relativity.isChecked():
            try:
                from relativity_projection import project_event
                state = project_event(state, self.spin_relativity_beta.value(), self.spin_relativity_amount.value())
            except Exception as exc:
                state["relativity_error"] = str(exc)
        # QoS is representational only; receivers may skip expensive visuals, never audio/state.
        try:
            _q = self.cmb_perf_qos.currentText() if hasattr(self, "cmb_perf_qos") else "Auto (recommended)"
            state["performance_qos"] = "low" if _q.startswith("Low") else ("full" if _q.startswith("Full") else "auto")
        except Exception:
            state["performance_qos"] = "auto"
        self._broadcast_state = state
        if getattr(self, "chk_perf_game", None) is None or self.chk_perf_game.isChecked():
            try:
                setattr(self.host, "_performance_broadcast_state", dict(state))
                setattr(self.host, "_media_hub_broadcast_state", dict(state))
                cb = getattr(self.host, "on_media_hub_broadcast", None) or getattr(self.host, "_on_media_hub_broadcast", None)
                if callable(cb): cb(dict(state))
            except Exception:
                pass
        self._performance_step += 1
        if self._performance_step >= len(self._cutup_events) and not self._performance_loop:
            self._stop_performance()

    def _stop_performance(self):
        self._performance_timer.stop()
        self._broadcast_state = {"active": False, "timestamp": time.time()}
        try: setattr(self.host, "_performance_broadcast_state", dict(self._broadcast_state)); setattr(self.host, "_media_hub_broadcast_state", dict(self._broadcast_state))
        except Exception: pass
        self.lbl_status.setText("Live broadcast stopped.")

    def _lan_ip(self) -> str:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.connect(("8.8.8.8", 80)); ip = sock.getsockname()[0]; sock.close(); return ip
        except Exception:
            return "127.0.0.1"

    def _start_remote_server(self):
        if self._remote_server is not None:
            return
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def _json(self, code, payload):
                raw = json.dumps(payload).encode("utf-8"); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_GET(self):
                if self.path.split("?",1)[0] == "/status": self._json(200, dict(owner._broadcast_state)); return
                self._json(404, {"error":"not found"})
            def do_POST(self):
                if self.headers.get("X-Groovebox-Token", "") != owner._remote_token:
                    self._json(403, {"error":"bad token"}); return
                try:
                    n = min(4096, int(self.headers.get("Content-Length", "0") or 0)); payload = json.loads(self.rfile.read(n) or b"{}")
                except Exception:
                    self._json(400, {"error":"bad json"}); return
                with owner._remote_lock: owner._remote_commands.append(payload if isinstance(payload, dict) else {})
                self._json(202, {"queued": True})
            def log_message(self, *_args): pass
        try:
            self._remote_server = ThreadingHTTPServer(("0.0.0.0", int(self.spin_remote_port.value())), Handler)
            self._remote_thread = threading.Thread(target=self._remote_server.serve_forever, daemon=True); self._remote_thread.start()
            self.lbl_remote.setText(f"http://{self._lan_ip()}:{self.spin_remote_port.value()}/status · control token: {self._remote_token}")
        except Exception as e:
            self._remote_server = None; QMessageBox.warning(self, "Ethernet host", str(e))

    def _stop_remote_server(self):
        srv = self._remote_server; self._remote_server = None
        if srv is not None:
            try: srv.shutdown(); srv.server_close()
            except Exception: pass
        if hasattr(self, "lbl_remote"): self.lbl_remote.setText("Stopped")

    def _drain_remote_commands(self):
        with self._remote_lock:
            cmds = self._remote_commands[:]; self._remote_commands.clear()
        for cmd in cmds:
            action = str(cmd.get("action", "")).lower()
            if action == "start": self._start_performance(self._performance_media_path, bool(cmd.get("loop", True)))
            elif action == "stop": self._stop_performance()
            elif action == "next": self._playlist_next()
            elif action == "previous": self._playlist_prev()
            elif action == "speed":
                try: self._set_live_speed(float(cmd.get("value", 1.0)))
                except Exception: pass

    # ------------------------------------------------------------------ outputs / Wi-Fi TV
    def _build_outputs_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Device Outputs · Wi-Fi TV · Game Share</b>"))
        intro = QLabel(
            "Route the same Performance stream to hot-plugged HDMI/VGA/USB displays and "
            "PipeWire/Pulse audio sinks (including paired Bluetooth/USB/HDMI audio). A local "
            "Wi-Fi/LAN TV page can play the programmed mixed-type playlist; game .zip packages "
            "can be shared to another box without executing them on the receiver."
        )
        intro.setWordWrap(True); lay.addWidget(intro)

        dev = QGroupBox("Local device routing"); df = QFormLayout(dev)
        self.cmb_output_display = QComboBox(); df.addRow("Display", self.cmb_output_display)
        self.cmb_output_audio = QComboBox(); df.addRow("Audio sink", self.cmb_output_audio)
        drow = QHBoxLayout()
        bref = QPushButton("↻ Detect HDMI/VGA/USB/Bluetooth"); bref.clicked.connect(self._refresh_output_devices)
        bapply = QPushButton("Apply to new playback"); bapply.clicked.connect(self._apply_output_routing)
        drow.addWidget(bref); drow.addWidget(bapply); df.addRow(drow)
        self.lbl_output_devices = QLabel("Not scanned yet."); self.lbl_output_devices.setWordWrap(True); df.addRow("Detected", self.lbl_output_devices)
        lay.addWidget(dev)

        tv = QGroupBox("Wi-Fi / Ethernet TV output"); tf = QFormLayout(tv)
        self.spin_tv_port = QSpinBox(); self.spin_tv_port.setRange(1024, 65535); self.spin_tv_port.setValue(8780); tf.addRow("TV host port", self.spin_tv_port)
        self.lbl_tv_url = QLabel("Stopped"); self.lbl_tv_url.setWordWrap(True); self.lbl_tv_url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); tf.addRow("TV URL", self.lbl_tv_url)
        trow = QHBoxLayout()
        btvon = QPushButton("Start TV host + publish playlist"); btvon.clicked.connect(self._start_tv_host)
        bpub = QPushButton("Republish playlist"); bpub.clicked.connect(self._publish_tv_playlist)
        btvoff = QPushButton("Stop TV host"); btvoff.clicked.connect(self._stop_tv_host)
        trow.addWidget(btvon); trow.addWidget(bpub); trow.addWidget(btvoff); tf.addRow(trow)
        crow = QHBoxLayout()
        bcast = QPushButton("Cast TV URL (catt/Chromecast)"); bcast.clicked.connect(self._cast_tv_url)
        bgame = QPushButton("Share selected game .zip"); bgame.clicked.connect(self._share_selected_game)
        crow.addWidget(bcast); crow.addWidget(bgame); tf.addRow(crow)
        self.lbl_game_share = QLabel("No game package shared."); self.lbl_game_share.setWordWrap(True); self.lbl_game_share.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); tf.addRow("Game share", self.lbl_game_share)
        lay.addWidget(tv)

        note = QLabel(
            "Display routing is per new mpv process; USB DisplayLink/VGA adapters appear when the OS exposes them as displays. "
            "Bluetooth must already be paired/connected by the OS. The TV page uses normal HTTP media with byte-range support, "
            "so it works without a proprietary receiver app when the TV/browser supports the file codecs."
        )
        note.setWordWrap(True); note.setStyleSheet("color:#8ab4c8; font-size:9pt;"); lay.addWidget(note)
        lay.addStretch(1)
        QTimer.singleShot(0, self._refresh_output_devices)
        return w

    def _refresh_output_devices(self):
        try:
            from media_output_router import detect_displays, detect_audio_targets
            self._output_displays = detect_displays(); self._output_audio = detect_audio_targets()
            self.cmb_output_display.clear()
            for d in self._output_displays:
                tags = []
                if d.primary: tags.append("primary")
                if d.geometry: tags.append(d.geometry)
                self.cmb_output_display.addItem(d.name + (" · " + ", ".join(tags) if tags else ""))
            self.cmb_output_audio.clear()
            for a in self._output_audio:
                tag = f" [{a.kind}]" if a.kind and a.kind != "default" else ""
                self.cmb_output_audio.addItem(a.description + tag)
            self.lbl_output_devices.setText(f"{len(self._output_displays)} display target(s) · {max(0, len(self._output_audio)-1)} explicit audio sink(s)")
            self._apply_output_routing()
        except Exception as e:
            self.lbl_output_devices.setText(f"Device scan unavailable: {e}")

    def _apply_output_routing(self):
        di = self.cmb_output_display.currentIndex() if hasattr(self, "cmb_output_display") else -1
        ai = self.cmb_output_audio.currentIndex() if hasattr(self, "cmb_output_audio") else -1
        self._output_display = self._output_displays[di] if 0 <= di < len(self._output_displays) else None
        self._output_audio_target = self._output_audio[ai] if 0 <= ai < len(self._output_audio) else None
        dname = getattr(self._output_display, "name", "default") if self._output_display else "default"
        aname = getattr(self._output_audio_target, "description", "System default") if self._output_audio_target else "System default"
        self.lbl_status.setText(f"Output routing: display={dname} · audio={aname}")

    def _start_tv_host(self):
        try:
            from media_output_router import MediaShareServer
            if self._media_share_server is not None:
                self._media_share_server.stop()
            self._media_share_server = MediaShareServer(int(self.spin_tv_port.value()))
            self._media_share_server.start()
            self._publish_tv_playlist()
            self.lbl_tv_url.setText(self._media_share_server.tv_url())
            self.lbl_status.setText("Wi-Fi/LAN TV host active; open the TV URL in a browser/network player.")
        except Exception as e:
            self._media_share_server = None
            QMessageBox.warning(self, "TV host", str(e))

    def _publish_tv_playlist(self):
        if self._media_share_server is None:
            return
        try:
            self._media_share_server.set_playlist(self._playlist)
            if self._performance_media_path and os.path.isfile(self._performance_media_path):
                self._media_share_server.set_current(self._performance_media_path)
            self.lbl_tv_url.setText(self._media_share_server.tv_url())
            self.lbl_status.setText(f"TV playlist published: {len(self._media_share_server.playlist)} media item(s).")
        except Exception as e:
            QMessageBox.warning(self, "Publish TV playlist", str(e))

    def _stop_tv_host(self):
        srv, self._media_share_server = self._media_share_server, None
        if srv is not None:
            try: srv.stop()
            except Exception: pass
        if hasattr(self, "lbl_tv_url"): self.lbl_tv_url.setText("Stopped")

    def _cast_tv_url(self):
        if self._media_share_server is None:
            self._start_tv_host()
        if self._media_share_server is None:
            return
        try:
            from media_output_router import cast_with_catt
            ok, msg = cast_with_catt(self._media_share_server.tv_url())
            if ok: self.lbl_status.setText(msg)
            else: QMessageBox.information(self, "Chromecast handoff", msg + "\n\nThe TV URL remains usable directly in a smart-TV browser.")
        except Exception as e:
            QMessageBox.warning(self, "Chromecast handoff", str(e))

    def _share_selected_game(self):
        path = None
        for p in self._selected_paths():
            if os.path.isfile(p) and os.path.splitext(p)[1].lower() in GAME_EXT:
                path = p; break
        if path is None:
            QMessageBox.information(self, "Game share", "Select a packaged .zip game in the Performance browser first.")
            return
        if self._media_share_server is None:
            self._start_tv_host()
        if self._media_share_server is None:
            return
        try:
            key = self._media_share_server.share_game(path)
            self._last_shared_game_url = self._media_share_server.game_url(key)
            self.lbl_game_share.setText(self._last_shared_game_url)
            self.lbl_status.setText(f"Game package shared on LAN: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Game share", str(e))

    # ------------------------------------------------------------------ drive / cloning
    def _build_transfer_tab(self) -> QWidget:
        w=QWidget(); lay=QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Operation Station Drive · Clone · Transfer</b>"))
        note=QLabel("Move projects/modules/samples/exports or clone this Operation Station build over Wi-Fi, Ethernet, or mounted USB storage. Clone bundles carry SHA-256 manifests and do not auto-execute on the receiving machine.")
        note.setWordWrap(True); lay.addWidget(note)
        grp=QGroupBox("Version clone"); f=QFormLayout(grp)
        self.chk_clone_source=QCheckBox("Source code"); self.chk_clone_source.setChecked(True); f.addRow(self.chk_clone_source)
        self.chk_clone_exec=QCheckBox("Build/executable kit"); self.chk_clone_exec.setChecked(True); f.addRow(self.chk_clone_exec)
        self.chk_clone_deps=QCheckBox("Dependency/offline install assets"); self.chk_clone_deps.setChecked(True); f.addRow(self.chk_clone_deps)
        self.chk_clone_content=QCheckBox("Include my projects/samples/modules"); self.chk_clone_content.setChecked(False); f.addRow(self.chk_clone_content)
        row=QHBoxLayout(); b=QPushButton("Create V3 Clone Bundle"); b.clicked.connect(self._create_clone_bundle); row.addWidget(b)
        b=QPushButton("Verify Bundle"); b.clicked.connect(self._verify_clone_bundle); row.addWidget(b); f.addRow(row)
        self.lbl_clone=QLabel("No clone bundle yet."); self.lbl_clone.setWordWrap(True); self.lbl_clone.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); f.addRow("Bundle",self.lbl_clone)
        lay.addWidget(grp)
        net=QGroupBox("Wi-Fi / Ethernet share"); nf=QFormLayout(net)
        self.spin_clone_port=QSpinBox(); self.spin_clone_port.setRange(1024,65535); self.spin_clone_port.setValue(8783); nf.addRow("Port",self.spin_clone_port)
        nr=QHBoxLayout(); b=QPushButton("Start Clone Share"); b.clicked.connect(self._start_clone_share); nr.addWidget(b); b=QPushButton("Stop"); b.clicked.connect(self._stop_clone_share); nr.addWidget(b); nf.addRow(nr)
        self.lbl_clone_url=QLabel("Stopped"); self.lbl_clone_url.setWordWrap(True); self.lbl_clone_url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); nf.addRow("Network URL",self.lbl_clone_url)
        lay.addWidget(net)
        usb=QGroupBox("USB / mounted drive"); uf=QFormLayout(usb)
        self.cmb_clone_mount=QComboBox(); uf.addRow("Destination",self.cmb_clone_mount)
        ur=QHBoxLayout(); b=QPushButton("↻ Detect Drives"); b.clicked.connect(self._refresh_clone_mounts); ur.addWidget(b); b=QPushButton("Copy Clone to Drive"); b.clicked.connect(self._copy_clone_to_mount); ur.addWidget(b); uf.addRow(ur)
        lay.addWidget(usb); lay.addStretch(1); QTimer.singleShot(0,self._refresh_clone_mounts); return w

    def _create_clone_bundle(self):
        try:
            from operation_station_transfer import create_clone_bundle
            outdir=Path(os.path.dirname(__file__))/"exports"/"clones"; outdir.mkdir(parents=True,exist_ok=True)
            stamp=time.strftime('%Y%m%d-%H%M%S'); out=outdir/f"MathematiciansGroovebox_V3_OperationStation_{stamp}.mgbclone.zip"
            self._last_clone_bundle=create_clone_bundle(os.path.dirname(__file__),str(out),include_source=self.chk_clone_source.isChecked(),include_executables=self.chk_clone_exec.isChecked(),include_dependencies=self.chk_clone_deps.isChecked(),include_user_content=self.chk_clone_content.isChecked())
            self.lbl_clone.setText(self._last_clone_bundle); self.lbl_status.setText("Versioned Operation Station clone created with SHA-256 manifest.")
        except Exception as e: QMessageBox.warning(self,"Create clone",str(e))

    def _verify_clone_bundle(self):
        path=self._last_clone_bundle
        if not path:
            path,_=QFileDialog.getOpenFileName(self,"Verify Operation Station clone",os.path.dirname(__file__),"Groovebox clone (*.mgbclone.zip *.zip)")
        if not path: return
        try:
            from operation_station_transfer import verify_clone_bundle
            r=verify_clone_bundle(path); self.lbl_status.setText("Clone verified OK." if r['ok'] else "Clone verification failed: "+', '.join(r['bad'][:3]))
        except Exception as e: QMessageBox.warning(self,"Verify clone",str(e))

    def _start_clone_share(self):
        try:
            if not self._last_clone_bundle or not os.path.isfile(self._last_clone_bundle): self._create_clone_bundle()
            if not self._last_clone_bundle: return
            from operation_station_transfer import CloneShareServer
            self._stop_clone_share(); self._clone_share_server=CloneShareServer(os.path.dirname(self._last_clone_bundle),int(self.spin_clone_port.value()))
            urls=self._clone_share_server.start(); self.lbl_clone_url.setText('\n'.join(urls)); self.lbl_status.setText("Clone share active on Wi-Fi/Ethernet.")
        except Exception as e: QMessageBox.warning(self,"Clone share",str(e))

    def _stop_clone_share(self):
        srv,self._clone_share_server=self._clone_share_server,None
        if srv:
            try: srv.stop()
            except Exception: pass
        if hasattr(self,'lbl_clone_url'): self.lbl_clone_url.setText('Stopped')

    def _refresh_clone_mounts(self):
        try:
            from operation_station_transfer import detect_removable_mounts
            vals=detect_removable_mounts(); self.cmb_clone_mount.clear(); self.cmb_clone_mount.addItems(vals)
            if not vals: self.cmb_clone_mount.addItem(str(Path.home()))
        except Exception as e: self.lbl_status.setText(f"Drive detection: {e}")

    def _copy_clone_to_mount(self):
        if not self._last_clone_bundle or not os.path.isfile(self._last_clone_bundle): self._create_clone_bundle()
        if not self._last_clone_bundle: return
        try:
            from operation_station_transfer import copy_bundle
            dest=self.cmb_clone_mount.currentText().strip(); out=copy_bundle(self._last_clone_bundle,dest); self.lbl_status.setText(f"Clone copied: {out}")
        except Exception as e: QMessageBox.warning(self,"Copy clone",str(e))

    # ------------------------------------------------------------------ hardware
    def _build_hardware_tab(self) -> QWidget:
        w=QWidget(); lay=QVBoxLayout(w)
        lay.addWidget(QLabel("<b>⌨ Hardware · keyboard · touch · controllers · audio · MIDI</b>"))
        intro=QLabel("Groovebox OS is intentionally dual-input: keyboard/mouse and touchscreen work together. This scanner reports the OS-visible devices; it never changes canonical composition state.")
        intro.setWordWrap(True); lay.addWidget(intro)
        self.txt_hardware=QTextEdit(); self.txt_hardware.setReadOnly(True); lay.addWidget(self.txt_hardware,1)
        row=QHBoxLayout(); b=QPushButton("↻ Rescan hardware"); b.clicked.connect(self._refresh_hardware); row.addWidget(b)
        b2=QPushButton("▣ Refresh media outputs"); b2.clicked.connect(self._refresh_output_devices); row.addWidget(b2); row.addStretch(1); lay.addLayout(row)
        QTimer.singleShot(0,self._refresh_hardware); return w

    def _refresh_hardware(self):
        try:
            from hardware_hub import scan, summary
            r=scan(); lines=[summary(r), "", "INPUT DEVICES"] + [f"  • {x}" for x in r.get("input_names",[])]
            lines += ["", "DISPLAYS"] + [f"  • {x}" for x in r.get("display_summary",[])]
            lines += ["", "AUDIO"] + [f"  • {x}" for x in r.get("audio_devices",[])[:24]]
            lines += ["", "MIDI"] + [f"  • {x}" for x in r.get("midi_inputs",[])[:24]]
            lines += ["", "BLUETOOTH"] + [f"  • {x}" for x in r.get("bluetooth_connected",[])[:24]]
            lines += ["", "TOOLS", "  " + " · ".join(f"{k}={'yes' if v else 'no'}" for k,v in r.get("tools",{}).items())]
            self.txt_hardware.setPlainText("\n".join(lines))
        except Exception as e:
            self.txt_hardware.setPlainText(f"Hardware scan failed: {e}")

    # ------------------------------------------------------------------ box mode
    def _build_box_tab(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Performance Box / Installation Mode</b>"))
        note = QLabel("Checks the small-PC/Pi runtime and generates a systemd service template. Device routing stays separate from canonical composition, so reconnecting HDMI/Bluetooth/LAN cannot change the seed result.")
        note.setWordWrap(True); lay.addWidget(note)
        self.lbl_box_status = QLabel("Not checked yet."); self.lbl_box_status.setWordWrap(True); lay.addWidget(self.lbl_box_status)
        row=QHBoxLayout()
        b=QPushButton("Check box readiness"); b.clicked.connect(self._check_box_readiness); row.addWidget(b)
        b2=QPushButton("Save systemd service template"); b2.clicked.connect(self._save_box_service); row.addWidget(b2)
        lay.addLayout(row)
        self.chk_box_autorecover=QCheckBox("Prefer automatic playback/device recovery after hot-plug"); self.chk_box_autorecover.setChecked(True); lay.addWidget(self.chk_box_autorecover)
        self.chk_box_preview_shed=QCheckBox("Protect audio first: shed preview/video quality before audio/event timing"); self.chk_box_preview_shed.setChecked(True); lay.addWidget(self.chk_box_preview_shed)
        lay.addStretch(1); QTimer.singleShot(0,self._check_box_readiness); return w

    def _check_box_readiness(self):
        try:
            from performance_box import status
            st=status(self._cwd or '.')
            self.lbl_box_status.setText(f"CPU threads: {st.cpu_count} · free storage: {st.free_gb:.1f} GB\nFFmpeg: {st.ffmpeg} · ffprobe: {st.ffprobe} · mpv: {st.mpv} · PipeWire/Pulse: {st.pipewire} · Bluetooth tools: {st.bluetoothctl}")
        except Exception as e: self.lbl_box_status.setText(f"Readiness check failed: {e}")

    def _save_box_service(self):
        try:
            from performance_box import systemd_unit
            path,_=QFileDialog.getSaveFileName(self,"Save Performance Box service",os.path.join(os.path.dirname(__file__),"groovebox-performance.service"),"systemd service (*.service)")
            if not path: return
            with open(path,'w',encoding='utf-8') as f: f.write(systemd_unit(os.path.dirname(__file__)))
            self.lbl_status.setText(f"Saved box service template: {path}")
        except Exception as e: QMessageBox.warning(self,"Box Mode",str(e))

    # ------------------------------------------------------------------ batch tab
    def _build_batch_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>Batch re-render from linked project</b>"))
        lay.addWidget(QLabel(
            "Select exported media carrying source-project provenance OR select .mgpr projects directly. "
            "Project sets are rendered along an FPS/bitrate trend curve from the first item to the last."
        ))
        form = QFormLayout()
        self.spin_batch_fps = QSpinBox()
        self.spin_batch_fps.setRange(1, 120)
        self.spin_batch_fps.setValue(int(getattr(self.host, "_last_export_fps", 24) or 24))
        form.addRow("Target video FPS", self.spin_batch_fps)
        self.spin_batch_br = QSpinBox()
        self.spin_batch_br.setRange(32, 512)
        self.spin_batch_br.setValue(int(getattr(self.host, "_last_audio_bitrate_kbps", 192) or 192))
        self.spin_batch_br.setSuffix(" kbps")
        form.addRow("Target audio bitrate", self.spin_batch_br)
        self.spin_batch_fps_end = QSpinBox()
        self.spin_batch_fps_end.setRange(1, 120)
        self.spin_batch_fps_end.setValue(self.spin_batch_fps.value())
        form.addRow("Trend end FPS", self.spin_batch_fps_end)
        self.spin_batch_br_end = QSpinBox()
        self.spin_batch_br_end.setRange(32, 512)
        self.spin_batch_br_end.setValue(self.spin_batch_br.value())
        self.spin_batch_br_end.setSuffix(" kbps")
        form.addRow("Trend end bitrate", self.spin_batch_br_end)
        self.cmb_batch_curve = QComboBox()
        self.cmb_batch_curve.addItems(["Linear trend", "Ease-in", "Ease-out", "Smoothstep"])
        form.addRow("Project-set trend", self.cmb_batch_curve)
        self.cmb_batch_kind = QComboBox()
        self.cmb_batch_kind.addItems([
            "Audio WAV", "Audio MP3", "Audio Opus", "Audio OGG",
            "Video+Audio MP4", "Video-only MP4",
        ])
        form.addRow("Re-render as", self.cmb_batch_kind)
        self.chk_batch_preview = QCheckBox("Pi-safe: use preview rows for audio (faster)")
        self.chk_batch_preview.setChecked(True)
        form.addRow(self.chk_batch_preview)
        lay.addLayout(form)

        row = QHBoxLayout()
        btn_run = QPushButton("▶ Batch re-render selected")
        btn_run.clicked.connect(self._batch_rerender)
        btn_cancel = QPushButton("Cancel batch")
        btn_cancel.clicked.connect(lambda: setattr(self, "_batch_cancel", True))
        row.addWidget(btn_run)
        row.addWidget(btn_cancel)
        lay.addLayout(row)

        self.batch_log = QTextEdit()
        self.batch_log.setReadOnly(True)
        self.batch_log.setMaximumHeight(160)
        lay.addWidget(self.batch_log)
        return w

    def _batch_log(self, msg: str):
        self.batch_log.append(msg)
        self.lbl_status.setText(msg)

    def _batch_rerender(self):
        paths = [p for p in self._selected_paths() if os.path.isfile(p)]
        if not paths:
            QMessageBox.information(self, "Batch", "Select exported media or one/more .mgpr project files.")
            return
        self._batch_cancel = False
        fps0 = int(self.spin_batch_fps.value())
        br0 = int(self.spin_batch_br.value())
        fps1 = int(self.spin_batch_fps_end.value())
        br1 = int(self.spin_batch_br_end.value())
        kind = self.cmb_batch_kind.currentText()
        def trend(x: float) -> float:
            mode = self.cmb_batch_curve.currentText()
            x = max(0.0, min(1.0, x))
            if mode == "Ease-in": return x * x
            if mode == "Ease-out": return 1.0 - (1.0 - x) * (1.0 - x)
            if mode == "Smoothstep": return x * x * (3.0 - 2.0 * x)
            return x

        for idx, path in enumerate(paths):
            u = trend(0.0 if len(paths) <= 1 else idx / float(len(paths) - 1))
            fps = int(round(fps0 + (fps1 - fps0) * u))
            br = int(round(br0 + (br1 - br0) * u))
            setattr(self.host, "_last_export_fps", fps)
            setattr(self.host, "_last_audio_bitrate_kbps", br)
            if self._batch_cancel:
                self._batch_log("Batch cancelled.")
                break
            self._batch_log(f"→ {os.path.basename(path)}")
            project_path = path if os.path.splitext(path)[1].lower() in PROJECT_EXT else None
            prov = None if project_path else _extract_json_comment(path)
            if isinstance(prov, dict):
                project_path = prov.get("source_project_path") or prov.get("project_path")
            if not project_path or not os.path.isfile(str(project_path)):
                # Try same stem .mgpr beside media or in projects dir
                stem = os.path.splitext(os.path.basename(path))[0]
                candidates = [
                    os.path.splitext(path)[0] + ".mgpr",
                    os.path.join(self._host_projects_dir(), stem + ".mgpr"),
                    getattr(self.host, "_current_project_path", None),
                ]
                for c in candidates:
                    if c and os.path.isfile(c):
                        project_path = c
                        break
            if not project_path or not os.path.isfile(str(project_path)):
                self._batch_log(f"  skip: no linked project for {os.path.basename(path)}")
                continue
            try:
                with open(project_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                applied = False
                for name in ("_apply_project_snapshot", "apply_project_snapshot"):
                    fn = getattr(self.host, name, None)
                    if callable(fn):
                        fn(data)
                        applied = True
                        break
                if not applied:
                    self._batch_log(f"  skip: cannot apply project snapshot")
                    continue
                setattr(self.host, "_current_project_path", project_path)
                self._batch_log(f"  loaded {os.path.basename(project_path)} · trend fps={fps} bitrate={br}k")
            except Exception as e:
                self._batch_log(f"  load error: {e}")
                continue

            # Pi-safe preview rows for faster audio batch
            if self.chk_batch_preview.isChecked() and "Audio" in kind:
                if hasattr(self.host, "spin_preview_rows"):
                    try:
                        if self.host.spin_preview_rows.value() == 0:
                            self.host.spin_preview_rows.setValue(8)
                    except Exception:
                        pass

            try:
                if kind.startswith("Audio"):
                    fmt = kind.split()[-1].lower()
                    if hasattr(self.host, "export_mixdown_dialog"):
                        # Non-interactive path: render + write
                        self._batch_audio_export(fmt, br, path)
                    else:
                        self._batch_log("  no export_mixdown_dialog on host")
                elif "Video" in kind:
                    include_audio = "Video+Audio" in kind
                    if hasattr(self.host, "export_video_dialog"):
                        self._batch_log(
                            f"  opening video export UI (fps={fps}) — confirm path when prompted"
                        )
                        self.host.export_video_dialog(include_audio=include_audio, container="mp4")
                    else:
                        self._batch_log("  no export_video_dialog on host")
            except Exception as e:
                self._batch_log(f"  render error: {e}")

        self._batch_log("Batch finished.")
        self.refresh()

    def _batch_audio_export(self, fmt: str, bitrate_kbps: int, source_media: str):
        """Render mixdown and write next to source with quality suffix."""
        host = self.host
        max_rows = None
        if self.chk_batch_preview.isChecked() and hasattr(host, "_live_preview_max_rows"):
            max_rows = host._live_preview_max_rows()
        master, sr = host._render_mixdown_buffer(max_rows=max_rows)
        import numpy as np
        master = np.nan_to_num(np.asarray(master, dtype=np.float32), nan=0.0, posinf=1.0, neginf=-1.0)
        if hasattr(host, "_bake_dj_write"):
            master = host._bake_dj_write(master, sr)
        if hasattr(host, "_master_hardclip"):
            master, _ = host._master_hardclip(master, sr, apply_master_vol=True)
        pcm = (np.clip(master, -1.0, 1.0) * 32767.0).astype(np.int16)
        stem = os.path.splitext(os.path.basename(source_media))[0]
        dest_dir = self._host_exports_dir()
        out = os.path.join(dest_dir, f"{stem}_r{bitrate_kbps}k.{fmt}")
        prov = None
        try:
            prov = host._export_provenance_payload()
            if isinstance(prov, str):
                prov = prov.encode("utf-8")
        except Exception:
            prov = None
        host._write_audio_parts_and_final(
            out, sr, pcm, n_parts=1, provenance_bytes=prov,
            audio_format=fmt, audio_bitrate_kbps=bitrate_kbps if fmt in ("mp3", "opus", "ogg") else None,
        )
        self._batch_log(f"  wrote {out}")

    # ------------------------------------------------------------------ info tab
    def _mg_library_roots(self):
        roots=[]
        for fn in (self._host_projects_dir,self._host_samples_dir,self._host_exports_dir):
            try:
                p=fn()
                if p and p not in roots: roots.append(p)
            except Exception: pass
        return roots

    def _scan_mg_paths(self):
        out=[]
        for root in self._mg_library_roots():
            if not root or not os.path.isdir(root): continue
            for base,_,files in os.walk(root):
                for fn in files:
                    if fn.lower().endswith(('.mgproject','.mgsynth','.mgprofile','.mg')):
                        out.append(os.path.join(base,fn))
        return sorted(set(out),key=lambda x:os.path.basename(x).lower())

    def _build_mg_library_tab(self) -> QWidget:
        w=QWidget(); lay=QVBoxLayout(w)
        hdr=QLabel("<b style='color:#f1ce68'>.MG ID + Relationship Library</b><br>Project · Synth · Profile artifacts keep stable IDs while usage statistics and software-discovered relationships evolve separately.")
        hdr.setWordWrap(True); lay.addWidget(hdr)
        self.mg_list=QListWidget(); lay.addWidget(self.mg_list,1)
        row=QHBoxLayout()
        b_refresh=QPushButton("↻ Scan .MG"); b_refresh.clicked.connect(self._refresh_mg_library); row.addWidget(b_refresh)
        b_load=QPushButton("⬇ Load to relevant slot"); b_load.clicked.connect(self._load_selected_mg); row.addWidget(b_load)
        b_rel=QPushButton("⌬ Find Related"); b_rel.clicked.connect(self._show_related_mg); row.addWidget(b_rel)
        b_exp=QPushButton("⇧ Export History"); b_exp.setToolTip("Export .MG provenance and analytics as JSON, CSV, or HTML without changing the artifact."); b_exp.clicked.connect(self._export_selected_mg_history); row.addWidget(b_exp)
        b_cmp=QPushButton("⇣ Compress History"); b_cmp.setToolTip("Keep longitudinal totals and strongest companion relationships while reducing detailed history."); b_cmp.clicked.connect(self._compress_selected_mg_history); row.addWidget(b_cmp)
        b_clr=QPushButton("⌫ Clear History"); b_clr.setToolTip("Clear mutable use/co-use/outcome history without changing the .MG Artifact ID or payload."); b_clr.clicked.connect(self._clear_selected_mg_history); row.addWidget(b_clr)
        lay.addLayout(row)
        self.mg_info=QTextEdit(); self.mg_info.setReadOnly(True); self.mg_info.setMaximumHeight(180); lay.addWidget(self.mg_info)
        self.mg_list.itemSelectionChanged.connect(self._mg_selection_changed)
        QTimer.singleShot(0,self._refresh_mg_library)
        return w

    def _refresh_mg_library(self):
        if not hasattr(self,'mg_list'): return
        self.mg_list.clear()
        try:
            from mg_artifacts import load
            for path in self._scan_mg_paths():
                try:
                    d=load(path,record_use=False); a=d.get('analytics',{}) or {}
                    text=f"{d.get('kind','?').upper()} · {d.get('title') or os.path.basename(path)} · uses {int(a.get('use_count',0))} · {d.get('artifact_id','')}"
                    it=QListWidgetItem(text); it.setData(Qt.ItemDataRole.UserRole,path); self.mg_list.addItem(it)
                except Exception: pass
            self.mg_info.setPlainText(f"{self.mg_list.count()} .MG artifact(s) found across Projects / Samples / Exports.")
        except Exception as e: self.mg_info.setPlainText(str(e))

    def _selected_mg_path(self):
        its=self.mg_list.selectedItems() if hasattr(self,'mg_list') else []
        return str(its[0].data(Qt.ItemDataRole.UserRole)) if its else ''

    def _mg_selection_changed(self):
        path=self._selected_mg_path()
        if not path: return
        try:
            from mg_artifacts import load
            d=load(path,record_use=False); a=d.get('analytics',{}) or {}; p=d.get('provenance',{}) or {}
            self.mg_info.setPlainText(
                f"{path}\nArtifact ID: {d.get('artifact_id')}\nProgram ID: {p.get('program_id')}\nComposition ID: {p.get('composition_id')}\n"
                f"uses: {a.get('use_count',0)} · loads: {a.get('load_count',0)} · saves: {a.get('save_count',0)}\n"
                f"first used: {a.get('first_used')} · last used: {a.get('last_used')}\ncompanions: {json.dumps(a.get('companions',{}),sort_keys=True)}")
        except Exception as e: self.mg_info.setPlainText(str(e))

    def _load_selected_mg(self):
        path=self._selected_mg_path()
        if not path: return
        try:
            fn=getattr(self.host,'_load_mg_path',None)
            if not callable(fn): raise RuntimeError('Host .MG loader unavailable')
            d=fn(path); self.lbl_status.setText(f"Loaded .MG {d.get('kind')} → relevant slot")
            self._refresh_mg_library(); self._show_related_mg()
        except Exception as e: QMessageBox.warning(self,".MG load failed",str(e))

    def _show_related_mg(self):
        path=self._selected_mg_path() or str(getattr(self.host,'_last_mg_artifact_path','') or '')
        if not path or not os.path.isfile(path): return
        try:
            from mg_artifacts import find_related
            rel=find_related(path,self._mg_library_roots(),limit=12)
            if not rel: self.mg_info.append("\nRelated: no comparable history yet."); return
            lines=["\nRelated / common results:"]
            for r in rel:
                a=r.get('analytics',{}) or {}
                lines.append(f"{r['score']:.3f} · {r['kind']} · {r['title']} · uses {a.get('use_count',0)} · {os.path.basename(r['path'])}")
            self.mg_info.append("\n".join(lines))
        except Exception as e: self.mg_info.append(f"\nRelated error: {e}")

    def _export_selected_mg_history(self):
        path=self._selected_mg_path()
        if not path: return
        base=os.path.splitext(os.path.basename(path))[0] + "_history"
        out,flt=QFileDialog.getSaveFileName(self,"Export .MG History",os.path.join(os.path.dirname(path),base+".json"),"JSON (*.json);;CSV (*.csv);;HTML (*.html)")
        if not out: return
        low=out.lower(); fmt='csv' if low.endswith('.csv') else ('html' if low.endswith(('.html','.htm')) else 'json')
        if not low.endswith(('.json','.csv','.html','.htm')): out += '.'+fmt
        try:
            from mg_artifacts import export_history
            final=export_history(path,out,fmt)
            self.mg_info.append(f"\nHistory exported: {final}")
        except Exception as e: QMessageBox.warning(self,"History export failed",str(e))

    def _compress_selected_mg_history(self):
        path=self._selected_mg_path()
        if not path: return
        try:
            from mg_artifacts import compress_history
            result=compress_history(path)
            self.mg_info.append(f"\nHistory compressed; Artifact ID unchanged: {result.get('artifact_id')}")
            self._refresh_mg_library()
        except Exception as e: QMessageBox.warning(self,"History compression failed",str(e))

    def _clear_selected_mg_history(self):
        path=self._selected_mg_path()
        if not path: return
        ans=QMessageBox.question(self,"Clear .MG History","Clear detailed usage/co-use/outcome history?\n\nThe .MG payload and Artifact ID will not change.")
        if ans != QMessageBox.StandardButton.Yes: return
        try:
            from mg_artifacts import clear_history
            result=clear_history(path,preserve_totals=True)
            self.mg_info.append(f"\nHistory cleared; Artifact ID unchanged: {result.get('artifact_id')}")
            self._refresh_mg_library()
        except Exception as e: QMessageBox.warning(self,"History clear failed",str(e))

    def _build_info_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.info_view = QTextEdit()
        self.info_view.setReadOnly(True)
        lay.addWidget(self.info_view)
        tip = QLabel(
            "Pi tips: set GROOVEBOX_SAMPLE_RATE=48000, enable UI lite, use Preview rows, "
            "batch-re-render at lower FPS/bitrate for field copies, full quality at home."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        lay.addWidget(tip)
        return w

    def closeEvent(self, event):
        try: self._stop_goava_radio()
        except Exception: pass
        try: self._stop_performance()
        except Exception: pass
        try: self._stop_remote_server()
        except Exception: pass
        try: self._stop_tv_host()
        except Exception: pass
        self._stop_player()
        super().closeEvent(event)


def open_performance(host) -> Performance:
    """Compatibility standalone opener; main Groovebox embeds Performance as a dock."""
    dlg = Performance(host, parent=host)
    dlg.setModal(False)
    dlg.show()
    return dlg


PiMediaHub = Performance

def open_pi_media_hub(host):
    return open_performance(host)
