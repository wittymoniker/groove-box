"""GROOVEBOX_UNIFIED_EXPORT_20261101: one Export dialog for every format.

Pure UI: it collects a settings dict (``result_preset``) and never renders or
writes anything itself.  The host app feeds the preset to the existing export
pipelines (audio parts/stitch, video parts, MCC save), so all file output stays
on the proven, already-threaded code paths.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

# key -> (label, family, extension, include_audio, container/audio_format)
FORMATS = [
    ("wav",      "Audio — WAV (lossless PCM)",        "audio",   ".wav",  None),
    ("flac",     "Audio — FLAC (lossless)",           "audio",   ".flac", None),
    ("mp3",      "Audio — MP3 (lossy)",               "audio",   ".mp3",  None),
    ("ogg",      "Audio — Ogg Vorbis (lossy)",        "audio",   ".ogg",  None),
    ("opus",     "Audio — Opus (lossy)",              "audio",   ".opus", None),
    ("aiff",     "Audio — AIFF (PCM)",                "audio",   ".aiff", None),
    ("caf",      "Audio — CAF (PCM)",                 "audio",   ".caf",  None),
    ("mcc-audio","Audio — MCC lossless (bit-exact)",  "audio",   ".MCC",  None),
    ("mp4+a",    "Video + Audio — MP4",               "video",   ".mp4",  True),
    ("webm+a",   "Video + Audio — WebM",              "video",   ".webm", True),
    ("avi+a",    "Video + Audio — AVI",               "video",   ".avi",  True),
    ("mp4",      "Video only — MP4",                  "video",   ".mp4",  False),
    ("webm",     "Video only — WebM",                 "video",   ".webm", False),
    ("avi",      "Video only — AVI",                  "video",   ".avi",  False),
    ("image",    "Image frame (.png / .jpg / .webp / MCC)", "image", "",  None),
    ("mcc-video","Video + Audio — MCC lossless",      "mccvideo", "",     None),
    ("mcc",      "Project — MCC (composition)",       "project", ".MCC",  None),
    ("meum",     "Project — MEUM (compressed)",       "project", ".MEUM", None),
]
LOSSY_AUDIO = {"mp3", "ogg", "opus"}
_FMT = {k: (label, fam, ext, inc) for k, label, fam, ext, inc in FORMATS}


def format_info(key):
    return _FMT.get(key)


def _g(host, name, default):
    try:
        v = getattr(host, name, None)
        return default if v in (None, "") else v
    except Exception:
        return default


class ExportAllDialog(QDialog):
    """Pick a format, then see (and edit) only the settings that format has."""

    def __init__(self, host, parent=None, initial_format="wav", default_dir=""):
        super().__init__(parent if isinstance(parent, QWidget) else (host if isinstance(host, QWidget) else None))
        self.host = host
        self.setWindowTitle("Export — all formats")
        self.setMinimumWidth(520)
        self._default_dir = default_dir or os.path.expanduser("~")
        root = QVBoxLayout(self)

        top = QFormLayout()
        self.combo_format = QComboBox()
        for key, label, *_ in FORMATS:
            self.combo_format.addItem(label, key)
        top.addRow("Format", self.combo_format)
        row = QHBoxLayout()
        self.edit_path = QLineEdit()
        self.edit_path.setPlaceholderText("Choose where to save…")
        btn = QPushButton("Browse…")
        btn.clicked.connect(self._browse)
        row.addWidget(self.edit_path, 1)
        row.addWidget(btn)
        top.addRow("Save as", row)
        root.addLayout(top)

        # ---------------- audio ----------------
        self.grp_audio = QWidget()
        fa = QFormLayout(self.grp_audio)
        fa.setContentsMargins(0, 0, 0, 0)
        self.combo_quality = QComboBox()
        self.combo_quality.addItems([
            "Radio / Broadcast — 48 kHz / 24-bit", "Studio HQ — 96 kHz / 24-bit",
            "Ultra HQ — 128 kHz / 24-bit", "CD-compatible — 44.1 kHz / 16-bit", "Custom"])
        fa.addRow("Quality preset", self.combo_quality)
        self.combo_sr = QComboBox()
        for sr in (44100, 48000, 88200, 96000, 128000, 176400, 192000):
            self.combo_sr.addItem(f"{sr / 1000.0:g} kHz", sr)
        self._select(self.combo_sr, int(_g(host, "_last_export_sample_rate", 48000)), 48000)
        fa.addRow("Render sample rate", self.combo_sr)
        self.combo_out_sr = QComboBox()
        self.combo_out_sr.addItem("Same as render", 0)
        for sr in (44100, 48000, 88200, 96000):
            self.combo_out_sr.addItem(f"Output at {sr / 1000.0:g} kHz", sr)
        fa.addRow("Output file sample rate", self.combo_out_sr)
        self.combo_bits = QComboBox()
        self.combo_bits.addItem("16-bit PCM", 16)
        self.combo_bits.addItem("24-bit PCM", 24)
        self.combo_bits.setCurrentIndex(1 if int(_g(host, "_last_export_bit_depth", 24)) >= 24 else 0)
        fa.addRow("Render bit depth", self.combo_bits)
        root.addWidget(self.grp_audio)

        # ---------------- video ----------------
        self.grp_video = QWidget()
        fv = QFormLayout(self.grp_video)
        fv.setContentsMargins(0, 0, 0, 0)
        try:
            dw, dh = host._export_frame_size()
        except Exception:
            dw, dh = 1280, 720
        self.spin_w = QSpinBox(); self.spin_w.setRange(160, 7680); self.spin_w.setSingleStep(2); self.spin_w.setValue(int(dw))
        self.spin_h = QSpinBox(); self.spin_h.setRange(120, 4320); self.spin_h.setSingleStep(2); self.spin_h.setValue(int(dh))
        self.spin_fps = QSpinBox(); self.spin_fps.setRange(1, 120)
        self.spin_fps.setValue(max(1, min(120, int(_g(host, "_last_export_fps", 24)))))
        fv.addRow("Width (px)", self.spin_w)
        fv.addRow("Height (px)", self.spin_h)
        fv.addRow("FPS", self.spin_fps)
        self.chk_integrity = QCheckBox("Integrity gate (reject black video / silent audio)")
        self.chk_integrity.setChecked(bool(_g(host, "_last_integrity_check", True)))
        fv.addRow(self.chk_integrity)
        root.addWidget(self.grp_video)

        # ---------------- shared: bitrate + parts ----------------
        self.grp_common = QWidget()
        fc = QFormLayout(self.grp_common)
        fc.setContentsMargins(0, 0, 0, 0)
        self.spin_br = QSpinBox(); self.spin_br.setRange(32, 512); self.spin_br.setSingleStep(16)
        self.spin_br.setSuffix(" kbps")
        self.spin_br.setValue(max(32, min(512, int(_g(host, "_last_audio_bitrate_kbps", 192)))))
        self.lbl_br = QLabel("Audio bitrate")
        fc.addRow(self.lbl_br, self.spin_br)
        self.spin_parts = QSpinBox(); self.spin_parts.setRange(1, 128)
        try:
            self.spin_parts.setValue(int(host._default_export_part_count()))
        except Exception:
            self.spin_parts.setValue(int(_g(host, "_last_export_part_count", 8)))
        self.spin_parts.setToolTip("Recoverable .part segments (1–128).")
        self.lbl_parts = QLabel("Part Count (1–128)")
        fc.addRow(self.lbl_parts, self.spin_parts)
        self.chk_stitch = QCheckBox("Stitch .part files into final output")
        self.chk_stitch.setChecked(bool(_g(host, "_last_stitch_parts", True)))
        fc.addRow(self.chk_stitch)
        root.addWidget(self.grp_common)

        # ---------------- project ----------------
        self.grp_project = QWidget()
        fp = QFormLayout(self.grp_project)
        fp.setContentsMargins(0, 0, 0, 0)
        self.chk_make_current = QCheckBox("Make the exported file the current project")
        self.chk_make_current.setChecked(False)
        self.chk_make_current.setToolTip("Off: saves a copy and keeps working on the current project.")
        fp.addRow(self.chk_make_current)
        self.chk_confirm = QCheckBox("Show a confirmation when finished")
        self.chk_confirm.setChecked(True)
        fp.addRow(self.chk_confirm)
        root.addWidget(self.grp_project)

        self.lbl_note = QLabel("")
        self.lbl_note.setWordWrap(True)
        root.addWidget(self.lbl_note)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.combo_quality.currentIndexChanged.connect(self._apply_quality)
        self.combo_format.currentIndexChanged.connect(self._on_format)
        self._apply_quality()
        i = self.combo_format.findData(initial_format)
        self.combo_format.setCurrentIndex(max(0, i))
        self._on_format()

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _select(combo, data, fallback):
        i = combo.findData(data)
        combo.setCurrentIndex(i if i >= 0 else max(0, combo.findData(fallback)))

    def current_key(self):
        return str(self.combo_format.currentData() or "wav")

    def _apply_quality(self, _=None):
        txt = self.combo_quality.currentText()
        preset = ((48000, 24) if txt.startswith("Radio") else (96000, 24) if txt.startswith("Studio")
                  else (128000, 24) if txt.startswith("Ultra") else (44100, 16) if txt.startswith("CD") else None)
        if preset:
            self._select(self.combo_sr, preset[0], 48000)
            self.combo_bits.setCurrentIndex(1 if preset[1] == 24 else 0)

    def _on_format(self, _=None):
        key = self.current_key()
        _label, fam, ext, include_audio = _FMT[key]
        self.grp_audio.setVisible(fam == "audio")
        self.grp_video.setVisible(fam == "video")
        self.grp_project.setVisible(fam == "project")
        self.grp_common.setVisible(fam in ("audio", "video"))
        self.chk_stitch.setVisible(fam in ("audio", "video"))
        _own_dialog = fam in ("image", "mccvideo")
        if key == "mcc-audio":
            self.spin_br.setEnabled(False)
            self.lbl_br.setText("Bitrate")
            self.lbl_note.setText("Lossless MCC audio: exact final PCM, no bitrate. Parts and sample rate still apply.")
        elif fam == "audio":
            lossy = key in LOSSY_AUDIO
            self.spin_br.setEnabled(lossy)
            self.lbl_br.setText("Bitrate")
            self.lbl_note.setText("Bitrate applies to MP3 / Opus / OGG only." if not lossy
                                  else f"{key.upper()} encodes from the render master at the chosen bitrate.")
        elif fam == "video":
            self.spin_br.setEnabled(bool(include_audio))
            self.lbl_br.setText("Audio bitrate")
            self.lbl_note.setText("Video parts and matching audio parts stay recoverable while rendering."
                                  if include_audio else "Video only: no audio track is written.")
        elif fam == "image":
            self.lbl_note.setText("Opens the image-frame exporter (format incl. MCC, size and frame choice) next.")
        elif fam == "mccvideo":
            self.lbl_note.setText("Opens the MCC lossless video exporter (file, size, FPS) next.")
        elif key == "mcc":
            self.lbl_note.setText("Saves the full composition document (.MCC).")
        else:
            self.lbl_note.setText("Exact-reconstructing Meum compressed project (.MEUM).")
        self.edit_path.setEnabled(not _own_dialog)
        if not _own_dialog:
            base = self._basename()
            self.edit_path.setText(os.path.join(self._default_dir, base + ext))
        else:
            self.edit_path.setText("")
        self.adjustSize()

    def _basename(self):
        cur = self.edit_path.text().strip()
        if cur:
            return os.path.splitext(os.path.basename(cur))[0] or "groovebox_export"
        try:
            return f"groovebox_export_{int(getattr(self.host, 'export_counter', 0)):03d}"
        except Exception:
            return "groovebox_export"

    def _browse(self):
        key = self.current_key()
        label, fam, ext, _ = _FMT[key]
        if fam in ("image", "mccvideo"):
            return
        path, _f = QFileDialog.getSaveFileName(self, "Save as", self.edit_path.text() or self._default_dir,
                                               f"{label} (*{ext});;All Files (*)")
        if path:
            self.edit_path.setText(path)

    def _accept(self):
        key = self.current_key()
        _label, fam, ext, _ = _FMT[key]
        if fam not in ("image", "mccvideo"):
            p = self.edit_path.text().strip()
            if not p or os.path.isdir(p):
                self.lbl_note.setText("Choose a file name to save as.")
                return
            if not p.lower().endswith(ext.lower()):
                self.edit_path.setText(p + ext)
        if fam == "audio":
            sr = int(self.combo_sr.currentData() or 48000)
            osr = int(self.combo_out_sr.currentData() or 0) or sr
            if osr > sr:
                self.lbl_note.setText("Output sample rate cannot exceed the render rate; choose a lower output rate.")
                return
        self.accept()

    # -- result ------------------------------------------------------------
    def result_preset(self):
        key = self.current_key()
        _label, fam, ext, include_audio = _FMT[key]
        w = self.spin_w.value() - self.spin_w.value() % 2
        h = self.spin_h.value() - self.spin_h.value() % 2
        sr = int(self.combo_sr.currentData() or 48000)
        return {
            "key": key, "family": fam, "ext": ext, "include_audio": include_audio,
            "path": self.edit_path.text().strip() if fam not in ("image", "mccvideo") else "",
            "parts": int(self.spin_parts.value()), "stitch": bool(self.chk_stitch.isChecked()),
            "bitrate": int(self.spin_br.value()),
            "render_sr": sr, "output_sr": int(self.combo_out_sr.currentData() or 0) or sr,
            "bit_depth": int(self.combo_bits.currentData() or 24),
            "width": max(160, w), "height": max(120, h), "fps": int(self.spin_fps.value()),
            "integrity": bool(self.chk_integrity.isChecked()),
            "make_current": bool(self.chk_make_current.isChecked()),
            "confirm": bool(self.chk_confirm.isChecked()),
        }
