"""explain_tools.py (R132.22, untested): why does it sound / look / vote like this?

explain_at(app, seconds, lens)  — "Explain this sound": which composition section is playing at that time, its
                                   vector hash, which canonical engine owns each of its parameters, its tuning field.
explain_vote(app, item)         — playlist voting explanation: the item's vector features that drove the vote.
open_lineage(app)               — seed lineage view: the fractal address tree (fractal_engine_core.address_tree)
                                   + recent seeds, each with a one-click "render all three" thumbnail.
"""
from __future__ import annotations

import os


def explain_at(app, seconds, lens="spectral", bars=4):
    import lenses, canonical_matrix as cm
    secs, seed, engines = lenses.composition_sections(app)
    bpm = secs[0][2]["bpm"] or 120.0
    sec_s = max(1.0, min(16.0, bars * 4 * 60.0 / bpm))
    i = min(len(secs) - 1, max(0, int(float(seconds) // sec_s)))
    label, v, meta = secs[i]
    lines = [f"t = {seconds:.2f} s → section {i + 1}/{len(secs)}: {label}  (section length {sec_s:.2f} s at {bpm:g} BPM)",
             f"vector {lenses.vector_hash(v)[:16]} · content {meta['content_sha256'][:12]} · seed '{str(seed)[:40]}'"]
    owners = cm.ENGINES
    for k in range(min(12, len(v))):
        own = owners[k % len(owners)]
        lines.append(f"  dim {k:2d} = {v[k]:.3f}  ← seed" + (f" + {own}" if own in engines else ""))
    try:
        import tuning_field
        lines.append("tuning: " + tuning_field.for_app(app, meta.get("name")).describe())
    except Exception:
        pass
    lines.append(f"lens '{lens}': " + lenses.LENSES[lens]["about"])
    return "\n".join(lines)


def explain_vote(app, item, score=None):
    """Turn a playlist item into the features a vote favoured (deterministic from its vector)."""
    import lenses
    seed = item.get("seed") if isinstance(item, dict) else str(item)
    v = lenses.vector(seed)
    feats = {"brightness (partials)": v[5:17].mean(), "tempo pull": v[3], "chaos (orbit k)": v[6], "density (CA rule)": v[9],
             "resonance": v[13], "inharmonicity": v[4]}
    top = sorted(feats.items(), key=lambda kv: -kv[1])[:3]
    return (f"{(score if score is not None else '')} vote for '{str(seed)[:40]}': favoured " +
            ", ".join(f"{k} {val:.2f}" for k, val in top))


def open_lineage(app=None):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QLineEdit, QLabel
    import fractal_engine_core as fec
    d = QDialog(app); d.setWindowTitle("🌳 Seed lineage · fractal addresses"); d.resize(640, 520)
    lay = QVBoxLayout(d); row = QHBoxLayout(); lay.addLayout(row)
    try:
        import canonical_matrix as cm; s0, eng = cm.context(app)
    except Exception:
        s0, eng = "MATGROOVEBOX::SUPERSEED::GENESIS", ()
    seed = QLineEdit(s0); row.addWidget(QLabel("Seed")); row.addWidget(seed, 1)
    tree = QTreeWidget(); tree.setHeaderLabels(["Address", "Vector hash"]); lay.addWidget(tree, 1)
    msg = QLabel(""); msg.setWordWrap(True); lay.addWidget(msg)

    def build():
        tree.clear(); nodes = {}
        addr = fec.address_tree(seed.text(), depth=2, width=4, engines=eng)
        for path, h in addr.items():                      # parents come before children in address_tree order
            it = QTreeWidgetItem([path if path != "root" else seed.text()[:40], h])
            if path == "root":
                tree.addTopLevelItem(it)
            else:
                parent = "/".join(path.split("/")[:-1]) or "root"
                (nodes.get(parent) or nodes["root"]).addChild(it)
            nodes[path] = it
        tree.expandToDepth(0)

    def render_sel():
        it = tree.currentItem()
        if it is None:
            return
        path = it.text(0); sd = seed.text() if path == seed.text()[:40] else f"{seed.text()}/{path}"
        try:
            import lenses
            r = lenses.render_all(sd, eng, lens="spectral")
            msg.setText(f"rendered {sd[:50]} → {os.path.basename(r['audio']['path'])}, image, game")
        except Exception as exc:
            msg.setText(f"⚠ {exc}")

    def use_sel():
        it = tree.currentItem()
        if it is not None and app is not None:
            path = it.text(0); sd = seed.text() if path == seed.text()[:40] else f"{seed.text()}/{path}"
            try:
                app.input_seed_val.setPlainText(sd); msg.setText("seed set in the main window")
            except Exception as exc:
                msg.setText(str(exc))
    for t, fn in (("↻ Build tree", build), ("▶ Render selected", render_sel), ("⇧ Use as seed", use_sel)):
        b = QPushButton(t); b.clicked.connect(lambda _c=False, f=fn: f()); row.addWidget(b)
    build(); d.show(); return d


def open_explain(app=None):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QDoubleSpinBox, QPushButton, QPlainTextEdit, QComboBox
    import lenses
    d = QDialog(app); d.setWindowTitle("❓ Explain this sound"); d.resize(640, 460)
    lay = QVBoxLayout(d); row = QHBoxLayout(); lay.addLayout(row)
    t = QDoubleSpinBox(); t.setRange(0, 36000); t.setSuffix(" s"); t.setDecimals(2)
    try:
        sr = float(getattr(app, "play_sample_rate", 48000) or 48000); t.setValue(float(getattr(app, "play_cursor", 0.0)) / sr)
    except Exception:
        pass
    ln = QComboBox(); ln.addItems(sorted(lenses.LENSES)); out = QPlainTextEdit(); out.setReadOnly(True)
    b = QPushButton("❓ Explain"); b.clicked.connect(lambda: out.setPlainText(explain_at(app, t.value(), ln.currentText())))
    for w in (t, ln, b):
        row.addWidget(w)
    lay.addWidget(out, 1); out.setPlainText(explain_at(app, t.value(), ln.currentText())); d.show(); return d
