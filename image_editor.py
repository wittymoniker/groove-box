"""image_editor.py — GROOVEBOX_R32_IMAGE_EDITOR_20261110

🖌 Image Editor — layered, non-destructive image editing for covers, video titles, textures,
OBJ materials and game sprites.

  Layers     new / import image / duplicate / delete / move up-down / visibility / rename;
             per-layer OPACITY (0–100 %) and BLEND mode (normal, multiply, screen, overlay,
             darken, lighten, difference, add, colour dodge/burn, soft/hard light).
  Draw       brush (size, colour, opacity, hardness), eraser (to transparency), line, rectangle,
             ellipse, fill bucket (flood fill), eyedropper.
  Gradient   linear or radial, two colours with their own alpha — drag across the canvas.
  Adjust     translucency of the whole layer, invert, grayscale, brightness/contrast, flip.
  Seeded     "Seed texture" paints a deterministic pattern from the seed program signature.
  Export     PNG (with alpha) / JPG; "→ Clip Editor" adds it as an image clip; "→ Sample /
             project folder" saves into the project's images; open/save .gbimg (layers as PNG in
             a zip, so editing continues later).
Undo / redo (40 steps). Zoom with the wheel.
"""
from __future__ import annotations

import io
import json
import os
import zipfile

from PyQt6.QtCore import Qt, QPointF, QRectF, QPoint
from PyQt6.QtGui import (QImage, QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QPixmap, QTransform)
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QSlider,
                             QComboBox, QSpinBox, QColorDialog, QFileDialog, QScrollArea, QInputDialog, QCheckBox, QGridLayout)

BLENDS = {"normal": QPainter.CompositionMode.CompositionMode_SourceOver, "multiply": QPainter.CompositionMode.CompositionMode_Multiply,
          "screen": QPainter.CompositionMode.CompositionMode_Screen, "overlay": QPainter.CompositionMode.CompositionMode_Overlay,
          "darken": QPainter.CompositionMode.CompositionMode_Darken, "lighten": QPainter.CompositionMode.CompositionMode_Lighten,
          "difference": QPainter.CompositionMode.CompositionMode_Difference, "add": QPainter.CompositionMode.CompositionMode_Plus,
          "colour dodge": QPainter.CompositionMode.CompositionMode_ColorDodge, "colour burn": QPainter.CompositionMode.CompositionMode_ColorBurn,
          "soft light": QPainter.CompositionMode.CompositionMode_SoftLight, "hard light": QPainter.CompositionMode.CompositionMode_HardLight}
TOOLS = ("brush", "eraser", "line", "rectangle", "ellipse", "fill", "gradient (linear)", "gradient (radial)", "eyedropper")


class Layer:
    def __init__(self, img, name="Layer"):
        self.img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.name, self.opacity, self.blend, self.visible = name, 1.0, "normal", True


class Canvas(QWidget):
    def __init__(self, ed):
        super().__init__(); self.ed = ed; self.zoom = 1.0; self._p0 = None; self._last = None
        self.setMouseTracking(True)

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(int(self.ed.w * self.zoom), int(self.ed.h * self.zoom))

    def composite(self):
        out = QImage(self.ed.w, self.ed.h, QImage.Format.Format_ARGB32_Premultiplied); out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        for L in self.ed.layers:
            if L.visible:
                p.setOpacity(L.opacity); p.setCompositionMode(BLENDS.get(L.blend, BLENDS["normal"])); p.drawImage(0, 0, L.img)
        p.end(); return out

    def paintEvent(self, _e):
        p = QPainter(self)
        s = 12
        for y in range(0, self.height(), s):          # transparency checkerboard
            for x in range(0, self.width(), s):
                p.fillRect(x, y, s, s, QColor("#2a2a2a") if (x // s + y // s) % 2 else QColor("#3a3a3a"))
        p.scale(self.zoom, self.zoom); p.drawImage(0, 0, self.composite())
        if self._p0 is not None and self._last is not None and self.ed.tool.currentText() not in ("brush", "eraser"):
            p.setPen(QPen(QColor(255, 255, 255, 160), 1 / self.zoom, Qt.PenStyle.DashLine)); p.drawLine(self._p0, self._last)
        p.end()

    def _pt(self, ev):
        return QPointF(ev.position().x() / self.zoom, ev.position().y() / self.zoom)

    def mousePressEvent(self, ev):
        L = self.ed.current()
        if L is None:
            return
        self.ed.push_undo(); self._p0 = self._last = self._pt(ev)
        t = self.ed.tool.currentText()
        if t == "fill":
            self.ed.flood(L, self._p0.toPoint()); self._p0 = None; self.update()
        elif t == "eyedropper":
            self.ed.color = QColor(self.composite().pixelColor(self._p0.toPoint())); self.ed.sync_color(); self._p0 = None
        elif t in ("brush", "eraser"):
            self._stroke(self._p0, self._p0)

    def mouseMoveEvent(self, ev):
        if self._p0 is None:
            return
        cur = self._pt(ev)
        if self.ed.tool.currentText() in ("brush", "eraser"):
            self._stroke(self._last, cur)
        self._last = cur; self.update()

    def mouseReleaseEvent(self, ev):
        if self._p0 is None:
            return
        L = self.ed.current(); t = self.ed.tool.currentText(); a, b = self._p0, self._pt(ev)
        if L is not None and t not in ("brush", "eraser"):
            p = QPainter(L.img); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            c = QColor(self.ed.color); c.setAlphaF(self.ed.alpha.value() / 100.0)
            if t.startswith("gradient"):
                c2 = QColor(self.ed.color2); c2.setAlphaF(self.ed.alpha2.value() / 100.0)
                if "radial" in t:
                    g = QRadialGradient(a, max(1.0, ((b.x() - a.x()) ** 2 + (b.y() - a.y()) ** 2) ** 0.5))
                else:
                    g = QLinearGradient(a, b)
                g.setColorAt(0, c); g.setColorAt(1, c2)
                p.fillRect(QRectF(0, 0, self.ed.w, self.ed.h), QBrush(g))
            else:
                p.setPen(QPen(c, self.ed.size.value(), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                if self.ed.filled.isChecked() and t != "line":
                    p.setBrush(QBrush(c))
                r = QRectF(a, b).normalized()
                {"line": lambda: p.drawLine(a, b), "rectangle": lambda: p.drawRect(r), "ellipse": lambda: p.drawEllipse(r)}[t]()
            p.end()
        self._p0 = self._last = None; self.update()

    def _stroke(self, a, b):
        L = self.ed.current()
        p = QPainter(L.img); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.ed.tool.currentText() == "eraser":
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            p.setPen(QPen(Qt.GlobalColor.transparent, self.ed.size.value(), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        else:
            c = QColor(self.ed.color); c.setAlphaF(self.ed.alpha.value() / 100.0 * (0.4 + 0.6 * self.ed.hard.value() / 100.0))
            p.setPen(QPen(c, self.ed.size.value(), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(a, b); p.end(); self.update()

    def wheelEvent(self, ev):
        self.zoom = max(0.1, min(8.0, self.zoom * (1.15 if ev.angleDelta().y() > 0 else 1 / 1.15)))
        self.setMinimumSize(self.sizeHint()); self.resize(self.sizeHint()); self.update()


class ImageEditor(QWidget):
    def __init__(self, app=None, w=1280, h=720):
        super().__init__(app, Qt.WindowType.Window)
        self.app = app; self.w, self.h = w, h; self.layers = []; self.undo = []; self.redo = []
        self.color, self.color2 = QColor("#ffd85a"), QColor("#7dd3fc")
        self.setWindowTitle("🖌 Image Editor · layers · draw · opacity · gradients"); self.resize(1280, 800)
        root = QHBoxLayout(self)
        side = QVBoxLayout(); root.addLayout(side, 0)
        self.tool = QComboBox(); self.tool.addItems(TOOLS); side.addWidget(QLabel("Tool")); side.addWidget(self.tool)
        g = QGridLayout()
        self.size = QSpinBox(); self.size.setRange(1, 400); self.size.setValue(18)
        self.alpha = QSpinBox(); self.alpha.setRange(0, 100); self.alpha.setValue(100); self.alpha.setSuffix(" %")
        self.hard = QSpinBox(); self.hard.setRange(0, 100); self.hard.setValue(80); self.hard.setSuffix(" %")
        self.alpha2 = QSpinBox(); self.alpha2.setRange(0, 100); self.alpha2.setValue(0); self.alpha2.setSuffix(" %")
        self.filled = QCheckBox("Filled shapes")
        self.b_c1 = QPushButton("Colour"); self.b_c2 = QPushButton("Colour 2")
        self.b_c1.clicked.connect(lambda: self._pick(1)); self.b_c2.clicked.connect(lambda: self._pick(2))
        for r, (cap, wd) in enumerate((("Size", self.size), ("Opacity", self.alpha), ("Hardness", self.hard), ("Colour 2 α", self.alpha2))):
            g.addWidget(QLabel(cap), r, 0); g.addWidget(wd, r, 1)
        g.addWidget(self.b_c1, 4, 0); g.addWidget(self.b_c2, 4, 1); g.addWidget(self.filled, 5, 0, 1, 2)
        side.addLayout(g)
        side.addWidget(QLabel("Layers (top first)"))
        self.list = QListWidget(); self.list.setMaximumWidth(260); side.addWidget(self.list, 1)
        self.list.currentRowChanged.connect(self._sync_layer_controls)
        self.list.itemChanged.connect(self._item_changed)
        self.l_op = QSlider(Qt.Orientation.Horizontal); self.l_op.setRange(0, 100); self.l_op.valueChanged.connect(self._set_opacity)
        self.l_bl = QComboBox(); self.l_bl.addItems(list(BLENDS)); self.l_bl.currentTextChanged.connect(self._set_blend)
        side.addWidget(QLabel("Layer opacity / translucency")); side.addWidget(self.l_op); side.addWidget(self.l_bl)
        lg = QGridLayout()
        for i, (cap, fn) in enumerate((("＋ New", self.new_layer), ("Import…", self.import_layer), ("Duplicate", self.dup_layer),
                                        ("Delete", self.del_layer), ("▲", lambda: self.move(1)), ("▼", lambda: self.move(-1)),
                                        ("Merge down", self.merge_down), ("Seed texture", self.seed_texture),
                                        ("Invert", lambda: self.adjust("invert")), ("Grayscale", lambda: self.adjust("gray")),
                                        ("Flip H", lambda: self.adjust("flip")), ("Undo", self.do_undo), ("Redo", self.do_redo),
                                        ("Export…", self.export), ("→ Clip Editor", self.to_clip), ("Save .gbimg…", self.save_doc),
                                        ("Open .gbimg…", self.open_doc))):
            b = QPushButton(cap); b.clicked.connect(fn); lg.addWidget(b, i // 2, i % 2)
        side.addLayout(lg)
        self.canvas = Canvas(self); sc = QScrollArea(); sc.setWidget(self.canvas); root.addWidget(sc, 1)
        bg = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor("#05070b"))
        self.layers.append(Layer(bg, "Background")); self.new_layer(); self.sync_color(); self._refresh()

    # -- layers --------------------------------------------------------------
    def current(self):
        i = self.list.currentRow()
        idx = len(self.layers) - 1 - i if i >= 0 else len(self.layers) - 1
        return self.layers[idx] if 0 <= idx < len(self.layers) else None

    def _refresh(self, keep=None):
        self.list.blockSignals(True); self.list.clear()
        for L in reversed(self.layers):
            it = QListWidgetItem(L.name); it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(Qt.CheckState.Checked if L.visible else Qt.CheckState.Unchecked); self.list.addItem(it)
        self.list.blockSignals(False)
        self.list.setCurrentRow(0 if keep is None else keep)
        self.canvas.setMinimumSize(self.canvas.sizeHint()); self.canvas.resize(self.canvas.sizeHint()); self.canvas.update()

    def _item_changed(self, it):
        L = self.layers[len(self.layers) - 1 - self.list.row(it)]
        L.visible = it.checkState() == Qt.CheckState.Checked; L.name = it.text(); self.canvas.update()

    def _sync_layer_controls(self, *_):
        L = self.current()
        if L:
            self.l_op.blockSignals(True); self.l_op.setValue(int(L.opacity * 100)); self.l_op.blockSignals(False)
            self.l_bl.blockSignals(True); self.l_bl.setCurrentText(L.blend); self.l_bl.blockSignals(False)

    def _set_opacity(self, v):
        L = self.current()
        if L:
            L.opacity = v / 100.0; self.canvas.update()

    def _set_blend(self, b):
        L = self.current()
        if L:
            L.blend = b; self.canvas.update()

    def new_layer(self):
        img = QImage(self.w, self.h, QImage.Format.Format_ARGB32_Premultiplied); img.fill(Qt.GlobalColor.transparent)
        self.layers.append(Layer(img, "Layer %d" % len(self.layers))); self._refresh()

    def import_layer(self):
        p, _ = QFileDialog.getOpenFileName(self, "Image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if p:
            self.open_path(p)

    def open_path(self, p):
        """R32.8: add an image file as a new layer (used by the Transmuter's "Open result in editor")."""
        if p:
            src = QImage(p).scaled(self.w, self.h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            img = QImage(self.w, self.h, QImage.Format.Format_ARGB32_Premultiplied); img.fill(Qt.GlobalColor.transparent)
            q = QPainter(img); q.drawImage((self.w - src.width()) // 2, (self.h - src.height()) // 2, src); q.end()
            self.push_undo(); self.layers.append(Layer(img, os.path.basename(p))); self._refresh()

    def dup_layer(self):
        L = self.current()
        if L:
            self.push_undo(); n = Layer(L.img.copy(), L.name + " copy"); n.opacity, n.blend = L.opacity, L.blend
            self.layers.insert(self.layers.index(L) + 1, n); self._refresh()

    def del_layer(self):
        L = self.current()
        if L and len(self.layers) > 1:
            self.push_undo(); self.layers.remove(L); self._refresh()

    def move(self, d):
        L = self.current()
        if not L:
            return
        i = self.layers.index(L); j = max(0, min(len(self.layers) - 1, i + d))
        self.layers[i], self.layers[j] = self.layers[j], self.layers[i]; self._refresh(len(self.layers) - 1 - j)

    def merge_down(self):
        L = self.current()
        i = self.layers.index(L) if L else 0
        if i <= 0:
            return
        self.push_undo(); B = self.layers[i - 1]
        q = QPainter(B.img); q.setOpacity(L.opacity); q.setCompositionMode(BLENDS[L.blend]); q.drawImage(0, 0, L.img); q.end()
        self.layers.pop(i); self._refresh()

    # -- tools --------------------------------------------------------------------
    def _pick(self, which):
        c = QColorDialog.getColor(self.color if which == 1 else self.color2, self, "Colour",
                                  QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if c.isValid():
            if which == 1:
                self.color = c
            else:
                self.color2 = c
            self.sync_color()

    def sync_color(self):
        self.b_c1.setStyleSheet("background:%s;color:#000;" % self.color.name())
        self.b_c2.setStyleSheet("background:%s;color:#000;" % self.color2.name())

    def flood(self, L, pt):
        img = L.img
        if not img.rect().contains(pt):
            return
        target = img.pixel(pt); c = QColor(self.color); c.setAlphaF(self.alpha.value() / 100.0); rgb = c.rgba()
        if target == rgb:
            return
        stack = [(pt.x(), pt.y())]; w, h = img.width(), img.height(); seen = 0
        while stack and seen < 4_000_000:
            x, y = stack.pop()
            if 0 <= x < w and 0 <= y < h and img.pixel(x, y) == target:
                img.setPixel(x, y, rgb); seen += 1
                stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

    def adjust(self, kind):
        L = self.current()
        if not L:
            return
        self.push_undo()
        if kind == "invert":
            L.img.invertPixels(QImage.InvertMode.InvertRgb)
        elif kind == "gray":
            a = L.img.convertToFormat(QImage.Format.Format_Grayscale8).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            L.img = a
        elif kind == "flip":
            L.img = L.img.mirrored(True, False)
        self.canvas.update()

    def seed_texture(self):
        import math
        try:
            sig = int(self.app._seed_program_signature() or 1) if self.app is not None else 1
        except Exception:
            sig = 1
        self.new_layer(); L = self.layers[-1]; L.name = "Seed texture %08x" % sig; L.blend = "screen"
        q = QPainter(L.img); q.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = 3 + sig % 9; a = (sig % 997) / 997.0
        for i in range(360):
            t = i / 360.0 * 2 * math.pi
            r = 0.42 * min(self.w, self.h) * (0.6 + 0.4 * math.sin(k * t + a * 6.283))
            x = self.w / 2 + r * math.cos(t); y = self.h / 2 + r * math.sin(t)
            c = QColor.fromHsvF((a + i / 360.0) % 1.0, 0.7, 1.0, 0.35); q.setPen(QPen(c, 2)); q.drawLine(QPointF(self.w / 2, self.h / 2), QPointF(x, y))
        q.end(); self._refresh()

    # -- undo -------------------------------------------------------------------------
    def _state(self):
        return [(L.img.copy(), L.name, L.opacity, L.blend, L.visible) for L in self.layers]

    def _restore(self, st):
        self.layers = []
        for img, n, o, b, v in st:
            L = Layer(img, n); L.opacity, L.blend, L.visible = o, b, v; self.layers.append(L)
        self._refresh()

    def push_undo(self):
        self.undo.append(self._state()); del self.undo[:-40]; self.redo.clear()

    def do_undo(self):
        if self.undo:
            self.redo.append(self._state()); self._restore(self.undo.pop())

    def do_redo(self):
        if self.redo:
            self.undo.append(self._state()); self._restore(self.redo.pop())

    # -- files ---------------------------------------------------------------------------
    def _images_dir(self):
        try:
            import groovebox_paths as gp
            d = os.path.join(str(gp.project_root(getattr(self.app, "_current_project_path", None))), "exports", "frames")
        except Exception:
            d = os.path.expanduser("~")
        os.makedirs(d, exist_ok=True); return d

    def export(self, path=None):
        path = path or QFileDialog.getSaveFileName(self, "Export image", os.path.join(self._images_dir(), "image.png"), "PNG (*.png);;JPEG (*.jpg)")[0]
        if path:
            self.canvas.composite().save(path)
        return path

    def to_clip(self):
        p = self.export(os.path.join(self._images_dir(), "image-%d.png" % len(os.listdir(self._images_dir()))))
        try:
            ed = self.app._r32_open_clip_editor(); ed._add_media_paths([p])
        except Exception:
            pass

    def save_doc(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save layered image", os.path.join(self._images_dir(), "image.gbimg"), "Groovebox image (*.gbimg)")
        if not p:
            return
        with zipfile.ZipFile(p, "w") as z:
            meta = []
            for i, L in enumerate(self.layers):
                buf = io.BytesIO()
                from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
                ba = QByteArray(); qb = QBuffer(ba); qb.open(QIODevice.OpenModeFlag.WriteOnly); L.img.save(qb, "PNG")
                z.writestr("layer%03d.png" % i, bytes(ba)); meta.append({"name": L.name, "opacity": L.opacity, "blend": L.blend, "visible": L.visible})
            z.writestr("layers.json", json.dumps({"w": self.w, "h": self.h, "layers": meta}))

    def open_doc(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open layered image", self._images_dir(), "Groovebox image (*.gbimg)")
        if not p:
            return
        with zipfile.ZipFile(p) as z:
            meta = json.loads(z.read("layers.json")); self.w, self.h = meta["w"], meta["h"]; self.layers = []
            for i, m in enumerate(meta["layers"]):
                img = QImage(); img.loadFromData(z.read("layer%03d.png" % i), "PNG")
                L = Layer(img, m["name"]); L.opacity, L.blend, L.visible = m["opacity"], m["blend"], m["visible"]; self.layers.append(L)
        self._refresh()


def open_window(app):
    w = getattr(app, "_image_editor_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); return w
    except RuntimeError:
        pass
    w = app._image_editor_window = ImageEditor(app); w.show(); return w
