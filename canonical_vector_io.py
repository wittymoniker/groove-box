"""canonical_vector_io.py (R132): ⇩ Give / ⇧ Use the canonical vector — export it, or take it from media or a file.

The canonical vector is the 32 numbers (0..1) the canonical composition matrix derives from seed + active engines;
every tool that uses canonical_matrix reads it. Give writes it as JSON (seed, engines, values, source). Use sets an
override: from a vector file exported earlier, or derived from any media (sound / image / video) through
media_transmuter.analyse — tempo, base pitch, brightness, onset density, and the energy envelope's shape folded into
the remaining values. The override blends with the seed vector by `amount` (1 = media only). Saved with the project
(attribute canonical_vector_override); Clear returns to seed + engines.
"""
from __future__ import annotations

import json
import math
import os
import time

N = 32


def current(app, n=N):
    import canonical_matrix as cm
    seed, engines = cm.context(app)
    return cm.vector(seed, engines, "global", n), seed, engines


def give(app, path):
    v, seed, engines = current(app)
    data = {"format": "groovebox-canonical-vector/1", "values": [round(x, 6) for x in v], "seed": seed[:4000],
            "engines": list(engines), "written": time.strftime("%Y-%m-%d %H:%M:%S"),
            "override": getattr(app, "canonical_vector_override", None)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return path


def from_file(path):
    d = json.load(open(path, encoding="utf-8"))
    vals = d.get("values") if isinstance(d, dict) else d
    vals = [min(1.0, max(0.0, float(x))) for x in vals][:N]
    if not vals:
        raise ValueError("no values in %s" % path)
    return vals


def from_media(path):
    """32 values from a sound / image / video file (deterministic)."""
    import numpy as np
    import media_transmuter as mt
    a = mt.analyse(path)
    e = np.asarray(a.get("energy", np.zeros(1)), dtype=float)
    if e.size < 2:
        e = np.zeros(32)
    e = e / (e.max() + 1e-12)
    shape = np.interp(np.linspace(0, e.size - 1, N - 6), np.arange(e.size), e)       # the energy envelope, resampled
    head = [min(1.0, a.get("bpm", 120) / 240.0), min(1.0, math.log2(max(55.0, a.get("base_hz", 432))) / 11.0),
            a.get("brightness", 0.5), min(1.0, a.get("onset_density", 0.0) * 4), (a.get("signature", 0) % 1000) / 999.0,
            min(1.0, a.get("seconds", 0) / 600.0)]
    return [round(float(x), 6) for x in list(head) + list(shape)][:N]


def use(app, values, amount=1.0, source=""):
    app.canonical_vector_override = {"values": list(values)[:N], "amount": float(amount), "source": str(source)}
    app._shared_mixdown_cache = {}
    return app.canonical_vector_override


def clear(app):
    app.canonical_vector_override = None
    app._shared_mixdown_cache = {}


def apply_override(app, v):
    """Used by canonical_matrix.vector: blend the seed vector with the override when one is set."""
    ov = getattr(app, "canonical_vector_override", None) if app is not None else None
    if not ov or not ov.get("values"):
        return v
    vals, a = ov["values"], max(0.0, min(1.0, float(ov.get("amount", 1.0))))
    return [(1 - a) * x + a * vals[i % len(vals)] for i, x in enumerate(v)]


def install_buttons(app, layout):
    """⇩ Give vector · ⇧ Use vector ▾ next to the canonical toggles."""
    from PyQt6.QtWidgets import QPushButton, QToolButton, QMenu, QFileDialog, QInputDialog
    css = "QPushButton,QToolButton{background:#10233a;color:#bfe3ff;border:1px solid #3a7aaa;border-radius:5px;padding:3px 8px;font-weight:800;}"
    give_b = QPushButton("⇩ Give vector"); give_b.setStyleSheet(css)
    give_b.setToolTip("Export the canonical vector (seed + engines → 32 numbers) as JSON for other projects, plugins, media")

    def do_give():
        p, _f = QFileDialog.getSaveFileName(app, "Export canonical vector", "canonical-vector.json", "Canonical vector (*.json)")
        if p:
            give(app, p); app.statusBar().showMessage("canonical vector → " + p, 6000)
    give_b.clicked.connect(lambda _c=False: do_give())
    use_b = QToolButton(); use_b.setText("⇧ Use vector ▾"); use_b.setStyleSheet(css)
    use_b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    use_b.setToolTip("Drive the canonical matrix from an exported vector or from any sound / image / video")
    m = QMenu(use_b)

    def amount():
        a, ok = QInputDialog.getDouble(app, "Blend", "How much of the input vector (0 = seed only, 1 = input only):", 1.0, 0.0, 1.0, 2)
        return a if ok else None

    def from_media_ui():
        p, _f = QFileDialog.getOpenFileName(app, "Media for the canonical vector", "", "Media (*.wav *.flac *.ogg *.mp3 *.png *.jpg *.jpeg *.webp *.mp4 *.mkv *.webm *.mov);;All files (*)")
        if p:
            a = amount()
            if a is not None:
                use(app, from_media(p), a, p); app.statusBar().showMessage("canonical vector from " + os.path.basename(p), 6000)

    def from_file_ui():
        p, _f = QFileDialog.getOpenFileName(app, "Exported canonical vector", "", "Canonical vector (*.json)")
        if p:
            a = amount()
            if a is not None:
                use(app, from_file(p), a, p); app.statusBar().showMessage("canonical vector from " + os.path.basename(p), 6000)
    m.addAction("🎞 From media (sound · image · video)…").triggered.connect(lambda _c=False: from_media_ui())
    m.addAction("📄 From an exported vector…").triggered.connect(lambda _c=False: from_file_ui())
    m.addAction("✖ Clear (seed + engines only)").triggered.connect(lambda _c=False: (clear(app), app.statusBar().showMessage("canonical vector: seed + engines", 4000)))
    use_b.setMenu(m)
    layout.addWidget(give_b); layout.addWidget(use_b)
    return give_b, use_b
