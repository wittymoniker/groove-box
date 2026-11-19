"""font_atelier.py — draw your own bitmap fonts for in-app captions / Party / notes."""
from __future__ import annotations
import json, os
from typing import Dict, Optional
try:
    import numpy as np
except Exception:
    np = None

class BitmapFont:
    def __init__(self, name="custom", cell=16):
        self.name = name
        self.cell = int(cell)
        self.glyphs: Dict[str, list] = {}  # char -> flat 0/1 rows

    def set_glyph(self, ch: str, rows):
        ch = ch[:1]
        if np is not None:
            a = np.asarray(rows, dtype=np.uint8).reshape(-1)
            self.glyphs[ch] = a.tolist()
        else:
            self.glyphs[ch] = list(rows)

    def save(self, path: str) -> str:
        data = {"name": self.name, "cell": self.cell, "glyphs": self.glyphs}
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".part"
        __import__("safe_io").atomic_write_json(tmp, data, separators=(",", ":"), encoding="utf-8")
        os.replace(tmp, path)
        try:
            import mgr_format as mgr
            mgr_path = path + ".mgr.font_atlas"
            with open(mgr_path, "wb") as f:
                raw = json.dumps(data).encode("utf-8")
                mgr.write_header(f, mgr.TYPE["font_atlas"], {"name": self.name, "cell": self.cell})
                f.write(raw)
        except Exception:
            pass
        return path

    @classmethod
    def load(cls, path: str) -> "BitmapFont":
        data = __import__("safe_io").load_json(path, encoding="utf-8")
        font = cls(data.get("name", "custom"), data.get("cell", 16))
        font.glyphs = dict(data.get("glyphs") or {})
        return font

def render_text_bitmap(font: BitmapFont, text: str):
    if np is None:
        return None
    c = font.cell
    chars = list(text)
    if not chars:
        return np.zeros((c, c), dtype=np.uint8)
    tiles = []
    for ch in chars:
        g = font.glyphs.get(ch) or font.glyphs.get("?") or [0] * (c * c)
        tiles.append(np.asarray(g, dtype=np.uint8).reshape(c, c))
    return np.concatenate(tiles, axis=1)
