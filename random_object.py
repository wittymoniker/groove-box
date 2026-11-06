"""Seeded Random Object generator for Groovebox.

Generates audio, still images, short rendered video clips, and voxel models
from the project's existing synthesis/render engines.  Generation is pure
with respect to the seed; host binding is explicit and opt-in.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def _seed_value(seed: Any) -> int:
    raw = str(seed if seed is not None else 0).encode("utf-8", "replace")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") & 0x7fffffff


def _samples_dir(host) -> Path:
    try:
        p = Path(host._samples_dir())
    except Exception:
        p = Path(__file__).resolve().parent / "samples"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    x = np.clip(x, -1.0, 1.0)
    pcm = np.round(x * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())


def _rgb_frame(host, width: int, height: int, frame_index: int) -> np.ndarray:
    engine = getattr(host, "video_synth_engine", None)
    if engine is None or not callable(getattr(engine, "render_frame", None)):
        raise RuntimeError("The Video Synth engine is not available")
    frame = np.asarray(engine.render_frame(int(width), int(height), export=True,
                                           frame_index=int(frame_index)))
    if frame.ndim != 3 or frame.shape[2] < 3:
        raise RuntimeError("Video Synth returned an invalid RGB frame")
    if frame.dtype != np.uint8:
        if np.issubdtype(frame.dtype, np.floating) and float(np.nanmax(frame, initial=0.0)) <= 1.5:
            frame = frame * 255.0
        frame = np.clip(np.nan_to_num(frame, nan=0.0), 0, 255).astype(np.uint8)
    return np.ascontiguousarray(frame[:, :, :3])


def generate_random_object(host, kind: str, seed: Any = 0, *, instrument: Optional[str] = None,
                            auto_bind: bool = False, layered: bool = False,
                            width: int = 640, height: int = 360, fps: int = 24,
                            duration: float = 2.0, voxel_count: int = 128) -> Dict[str, Any]:
    """Generate and optionally bind one deterministic object.

    `layered=True` preserves previous generated objects for the target
    instrument and records the new layer in the existing project media schema.
    """
    kind = str(kind).strip().lower()
    aliases = {"still": "image", "picture": "image", "movie": "video", "model": "voxel"}
    kind = aliases.get(kind, kind)
    if kind not in {"audio", "image", "video", "voxel"}:
        raise ValueError("kind must be audio, image, video, or voxel")
    seed_int = _seed_value(seed)
    rng = random.Random(seed_int)
    name = str(instrument or (host._current_instrument_name() if hasattr(host, "_current_instrument_name") else "Operator 1"))
    outdir = _samples_dir(host)
    stamp = f"{seed_int:08x}_{kind}"
    # Preserve previously bound assets when the same seed is generated again.
    outdir = Path(tempfile.mkdtemp(prefix=f"random_{stamp}_", dir=str(outdir)))
    record: Dict[str, Any] = {"kind": kind, "seed": seed_int, "instrument": name,
                              "layered": bool(layered), "created_by": "random_object"}

    if kind == "audio":
        sr = 44100
        seconds = max(0.25, min(12.0, float(duration)))
        n = int(sr * seconds)
        t = np.arange(n, dtype=np.float64) / sr
        base = float(getattr(host, "global_base_frequency_hz", 432.0) or 432.0)
        freq = base * (2.0 ** (rng.uniform(-18.0, 18.0) / 12.0))
        renderer = getattr(host, "_audition_voice", None)
        if not callable(renderer):
            raise RuntimeError("The instrument audio renderer is unavailable")
        audio = np.asarray(renderer(name, freq, t, sr), dtype=np.float32).reshape(-1)
        # deterministic, short amplitude contour; no abrupt terminal click
        fade = max(1, min(n // 8, int(sr * 0.04)))
        audio[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
        audio[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
        path = outdir / f"random_{stamp}.wav"
        _write_wav(path, audio, sr)
        record.update(path=str(path), sample_rate=sr, sample_count=n, frequency_hz=freq)
        if auto_bind:
            store = getattr(host, "instrument_media_samples", None)
            if not isinstance(store, dict):
                store = host.instrument_media_samples = {}
            old = store.get(name, {}) if layered else {}
            layers = list(old.get("layered_state", {}).get("layers", [])) if isinstance(old, dict) else []
            layers.append({"kind": "audio", "path": str(path), "seed": seed_int, "gain": 1.0})
            store[name] = {"path": str(path), "sample_rate": sr, "waveform": audio,
                           "user_owned": True, "source_kind": "audio", "video_path": "",
                           "video_input_enabled": False, "audio_present": True,
                           "layered_state": {"layers": layers, "source": "random_object"},
                           "binding_mode": "audio", "binding_source": "random_object",
                           "bound_layers_state": {"layers": layers}}

    elif kind == "image":
        frame_index = seed_int % 100000
        frame = _rgb_frame(host, width, height, frame_index)
        path = outdir / f"random_{stamp}.png"
        try:
            from PIL import Image
            Image.fromarray(frame, "RGB").save(path, format="PNG", optimize=True)
        except Exception as exc:
            raise RuntimeError(f"Could not encode generated image: {exc}") from exc
        record.update(path=str(path), width=int(width), height=int(height), frame_index=frame_index)
        if auto_bind:
            _bind_visual(host, name, path, "image", layered, seed_int)

    elif kind == "video":
        width = max(64, min(1920, int(width))); height = max(64, min(1080, int(height)))
        fps = max(1, min(60, int(fps))); frames = max(2, min(240, int(round(float(duration) * fps))))
        ffmpeg = shutil.which("ffmpeg")
        path = outdir / f"random_{stamp}.mp4"
        if ffmpeg:
            cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                   "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
                   "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", str(path)]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                start = seed_int % 100000
                for i in range(frames):
                    fr = _rgb_frame(host, width, height, start + i)
                    proc.stdin.write(fr.tobytes())
                proc.stdin.close()
                err = proc.stderr.read() if proc.stderr else b""
                code = proc.wait(timeout=90)
                if code:
                    raise RuntimeError(err.decode("utf-8", "replace")[-1000:] or f"ffmpeg exited {code}")
            except Exception:
                try: proc.kill(); proc.wait(timeout=3)
                except Exception: pass
                raise
            record.update(path=str(path), fps=fps, frames=frames, width=width, height=height)
            if auto_bind:
                _bind_visual(host, name, path, "video", layered, seed_int)
        else:
            # Preserve the generated frames losslessly as an interchange asset;
            # a real-time video encoder can consume the same RGB sequence later.
            arrays = [_rgb_frame(host, width, height, (seed_int % 100000) + i) for i in range(frames)]
            path = outdir / f"random_{stamp}.npz"
            np.savez_compressed(path, frames=np.stack(arrays), fps=np.int32(fps), seed=np.int64(seed_int))
            record.update(path=str(path), fps=fps, frames=frames, width=width, height=height,
                          encoding="NPZ RGB frame sequence (ffmpeg unavailable)")
            if auto_bind:
                raise RuntimeError("ffmpeg is unavailable; generated video frames were saved as NPZ and cannot be auto-bound")

    else:  # voxel model
        grid = max(8, min(64, int(getattr(host, "voxel_grid_size", 16) or 16)))
        count = max(8, min(1500, int(voxel_count)))
        cx = (grid - 1) * 0.5; cy = cx; cz = cx
        cells = []
        for i in range(count):
            # Deterministic clustered shell with sparse interior variation.
            theta = rng.random() * math.tau
            u = rng.uniform(-1.0, 1.0)
            rr = (grid * 0.34) * (rng.random() ** 0.25)
            z = cz + u * rr
            rxy = math.sqrt(max(0.0, rr * rr - (z - cz) ** 2))
            x = cx + math.cos(theta) * rxy
            y = cy + math.sin(theta) * rxy
            hue = (seed_int * 0.0001 + i * 137.507764) % 360.0
            h = hue / 60.0; c = 0.78; xx = c * (1.0 - abs((h % 2.0) - 1.0)); m = 0.14
            if h < 1: rgb=(c,xx,0)
            elif h < 2: rgb=(xx,c,0)
            elif h < 3: rgb=(0,c,xx)
            elif h < 4: rgb=(0,xx,c)
            elif h < 5: rgb=(xx,0,c)
            else: rgb=(c,0,xx)
            col = [int((v + m) * 255) for v in rgb]
            cells.append([int(round(x)) % grid, int(round(y)) % grid, int(round(z)) % grid,
                          col[0], col[1], col[2], 220])
        old = list(getattr(host, "voxel_cells", []) or []) if layered else []
        host.voxel_cells = (old + cells)[-1500:]
        record.update(voxels=cells, grid_size=grid, voxel_count=len(cells))
        path = outdir / f"random_{stamp}.json"
        payload = {
            "grid_size": grid,
            "voxels": cells,
            "seed": seed_int,
            "source": "random_object",
            "alias_pct": int(getattr(host, "voxel_alias_pct", 0) or 0),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        record["path"] = str(path)
        # Prefer the host's normalizer/importer when available so the editor and
        # project state stay consistent with the rest of the system.
        try:
            if hasattr(host, "_load_voxel_json"):
                host._load_voxel_json(str(path), layered=layered)
            else:
                for attr in ("_main_voxel_panel", "_perf_voxel_panel"):
                    panel = getattr(host, attr, None)
                    if panel is not None and hasattr(panel, "refresh_views"):
                        panel.refresh_views()
        except Exception:
            pass

    # Persistent lightweight layer manifest, separate from media bytes.
    layers = getattr(host, "random_object_layers", None)
    if not isinstance(layers, list):
        layers = host.random_object_layers = []
    if layered:
        layers.append({k: record.get(k) for k in ("kind", "seed", "instrument", "path", "fps", "frames", "width", "height", "voxel_count")})
    else:
        layers[:] = [{k: record.get(k) for k in ("kind", "seed", "instrument", "path", "fps", "frames", "width", "height", "voxel_count")}]
    if auto_bind:
        host.carrier_binding_source = "random_object"
        host.carrier_binding_mode = "video" if kind in {"image", "video"} else "audio" if kind == "audio" else "voxel"
        host.carrier_bound_layers_state = {"source": "random_object", "layers": list(layers)}
        try: host._refresh_operator_sample_ui()
        except Exception: pass
    try: host._on_live_source_changed()
    except Exception: pass
    return record


def _bind_visual(host, instrument: str, path: Path, kind: str, layered: bool, seed: int):
    store = getattr(host, "instrument_media_samples", None)
    if not isinstance(store, dict):
        store = host.instrument_media_samples = {}
    old = store.get(instrument, {}) if layered else {}
    layers = list(old.get("layered_state", {}).get("layers", [])) if isinstance(old, dict) else []
    layers.append({"kind": kind, "video_path": str(path), "seed": seed, "gain": 1.0})
    # `path` points at the visual asset; video_path is the existing project
    # binding endpoint used by the renderer, with audio absent by design.
    store[instrument] = {"path": str(path), "sample_rate": 44100,
                         "waveform": np.zeros(1, dtype=np.float32), "user_owned": True,
                         "source_kind": "video", "video_path": str(path),
                         "video_input_enabled": True, "audio_present": False,
                         "layered_state": {"layers": layers, "source": "random_object"},
                         "binding_mode": "video", "binding_source": "random_object",
                         "bound_layers_state": {"layers": layers}}


# Optional Qt front end; the generator above remains usable headlessly in tests.
try:
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                 QComboBox, QLineEdit, QCheckBox, QSpinBox, QMessageBox)
    from PyQt6.QtCore import Qt

    class RandomObjectDialog(QDialog):
        def __init__(self, host, parent=None):
            super().__init__(parent or host)
            self.host = host
            self.setWindowTitle("INTRODUCE RANDOM OBJECT · Seeded Engine")
            self.setMinimumWidth(440)
            self.setStyleSheet("QDialog{background:#111721;color:#e8f0ff;} QLabel{color:#dbe8fa;} QPushButton{background:#253b50;color:white;border:1px solid #4c89a6;border-radius:6px;padding:7px;font-weight:800;} QLineEdit,QComboBox,QSpinBox{background:#1b2836;color:white;padding:5px;border:1px solid #45627a;}")
            root=QVBoxLayout(self)
            title=QLabel("RANDOM OBJECT  ·  AUDIO / IMAGE / VIDEO / VOXEL")
            title.setStyleSheet("color:#75d9cf;font-size:14px;font-weight:900;")
            root.addWidget(title)
            row=QHBoxLayout(); row.addWidget(QLabel("Engine"))
            self.kind=QComboBox(); self.kind.addItems(["Audio sample","Image frame","Video clip","Voxel model"])
            row.addWidget(self.kind,1); root.addLayout(row)
            row=QHBoxLayout(); row.addWidget(QLabel("Seed"))
            self.seed=QLineEdit(str(getattr(host,"get_numeric_seed",lambda:0)() or 0)); row.addWidget(self.seed,1); root.addLayout(row)
            row=QHBoxLayout(); row.addWidget(QLabel("Carrier instrument"))
            self.carrier=QComboBox(); self.carrier.addItem("Current instrument", "")
            try:
                names=list((getattr(host,"instrument_param_state",{}) or {}).keys())
                current=str(getattr(host,"_current_instrument_name",lambda:"Operator 1")() or "Operator 1")
                for name in sorted(set(str(x) for x in names if x)):
                    self.carrier.addItem(name, name)
                pos=self.carrier.findData(current)
                if pos>=0: self.carrier.setCurrentIndex(pos)
            except Exception:
                pass
            row.addWidget(self.carrier,1); root.addLayout(row)
            row=QHBoxLayout(); self.amount_label=QLabel("Duration (seconds)"); row.addWidget(self.amount_label)
            self.amount=QSpinBox(); self.amount.setRange(1,12); self.amount.setValue(2); row.addWidget(self.amount); root.addLayout(row)
            self.kind.currentIndexChanged.connect(self._sync_amount)
            self.bind=QCheckBox("Auto-bind to selected instrument / carrier")
            self.bind.setChecked(False); root.addWidget(self.bind)
            self.layer=QCheckBox("Add as another layer (keep existing layers)")
            self.layer.setChecked(True); root.addWidget(self.layer)
            self.status=QLabel("Generated objects use the project's existing audio/video/voxel engines.")
            self.status.setWordWrap(True); root.addWidget(self.status)
            buttons=QHBoxLayout(); self.generate=QPushButton("✦ GENERATE OBJECT")
            self.generate.clicked.connect(self._generate); buttons.addWidget(self.generate)
            close=QPushButton("Close"); close.clicked.connect(self.close); buttons.addWidget(close); root.addLayout(buttons)

        def _sync_amount(self, index):
            voxel = index == 3
            self.amount_label.setText("Voxel count" if voxel else "Duration (seconds)")
            self.amount.setRange(8 if voxel else 1, 1500 if voxel else (8 if index == 2 else 12))
            self.amount.setValue(128 if voxel else 2)
            self.amount.setEnabled(index != 1)

        def _generate(self):
            keys=["audio","image","video","voxel"]
            kind=keys[self.kind.currentIndex()]
            try:
                self.generate.setEnabled(False)
                target=self.carrier.currentData()
                rec=generate_random_object(self.host, kind, self.seed.text(), instrument=(str(target) if target else None),
                                           auto_bind=self.bind.isChecked(), layered=self.layer.isChecked(),
                                           duration=float(self.amount.value()) if kind in {"audio", "video"} else 2.0,
                                           voxel_count=self.amount.value())
                self.status.setText(f"Created {rec['kind']} · seed {rec['seed']}\n{rec.get('path','')}")
            except Exception as exc:
                QMessageBox.warning(self,"Random Object",str(exc))
            finally:
                self.generate.setEnabled(True)
except Exception:
    RandomObjectDialog = None
