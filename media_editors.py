"""media_editors.py — GROOVEBOX_R32_MEDIA_EDITORS_20261110

The last two in-app editors of the A → B toolkit (every kind now has one):

  MidiNoteEditor   a .mid as an editable note table (start s · length s · pitch · velocity):
                   add / delete / transpose / quantise / audition (renders through signal_converters) · save.
  TextDataEditor   .txt / .md / .csv / .tsv / .json / .seed in a plain editor with a live check
                   (CSV numeric columns, JSON validity, seed program evaluation) · save · "→ seed field".
Both are non-modal, one window per file.
"""
from __future__ import annotations

import json
import os

_OPEN = {}


def _reuse(key, make):
    w = _OPEN.get(key)
    try:
        if w is not None:
            w.show(); w.raise_(); return w
    except RuntimeError:
        pass
    w = _OPEN[key] = make()
    w.show(); return w


def open_midi(app, path):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
                                 QLabel, QSpinBox, QDoubleSpinBox, QHeaderView)
    import signal_converters as sc

    def make():
        w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🎼 MIDI notes · %s" % os.path.basename(path)); w.resize(640, 520)
        lay = QVBoxLayout(w); tab = QTableWidget(0, 4); tab.setHorizontalHeaderLabels(["start (s)", "length (s)", "pitch", "velocity"])
        tab.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); lay.addWidget(tab, 1)
        info = QLabel(""); lay.addWidget(info)

        def put(notes):
            tab.setRowCount(len(notes))
            for r, (s, d, p, v) in enumerate(notes):
                for c, x in enumerate(("%.4f" % s, "%.4f" % d, str(int(p)), str(int(v)))):
                    tab.setItem(r, c, QTableWidgetItem(x))
            info.setText("%d notes" % len(notes))

        def get():
            out = []
            for r in range(tab.rowCount()):
                try:
                    out.append((float(tab.item(r, 0).text()), float(tab.item(r, 1).text()),
                                int(float(tab.item(r, 2).text())), int(float(tab.item(r, 3).text()))))
                except Exception:
                    pass
            return sorted(out)
        try:
            put(sc.read_midi(path))
        except Exception as exc:
            info.setText("could not read: %s" % exc)
        row = QHBoxLayout()
        semis = QSpinBox(); semis.setRange(-24, 24); grid = QDoubleSpinBox(); grid.setRange(0.01, 2.0); grid.setValue(0.125); grid.setSuffix(" s")

        def add():
            n = get(); last = n[-1] if n else (0.0, 0.25, 60, 90)
            n.append((last[0] + last[1], 0.25, last[2], last[3])); put(n)

        def delete():
            rows = sorted({i.row() for i in tab.selectedIndexes()}, reverse=True)
            for r in rows:
                tab.removeRow(r)

        def transpose():
            put([(s, d, max(0, min(127, p + semis.value())), v) for s, d, p, v in get()])

        def quantise():
            g = grid.value(); put([(round(s / g) * g, max(g, round(d / g) * g), p, v) for s, d, p, v in get()])

        def audition():
            import media_transmuter as mt
            out = os.path.splitext(path)[0] + ".audition.wav"
            mt._write_audio(out, sc.render_notes(get()), 48000)
            try:
                import performance
                performance._gb_inapp_fallback(w, out)
            except Exception:
                info.setText("audition written: %s" % out)

        def save():
            sc.write_midi(path, get()); info.setText("saved %d notes → %s" % (len(get()), os.path.basename(path)))
        for cap, fn in (("＋ note", add), ("Delete", delete), ("Transpose", transpose), ("Quantise", quantise),
                        ("▶ Audition", audition), ("💾 Save", save)):
            b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
        row.insertWidget(3, semis); row.insertWidget(5, grid)
        lay.addLayout(row)
        return w
    return _reuse(("midi", os.path.abspath(path)), make)


def check_text(path, text):
    e = os.path.splitext(path)[1].lower()
    try:
        if e == ".json":
            json.loads(text); return "valid JSON"
        if e in (".csv", ".tsv"):
            import signal_converters as sc, tempfile
            with tempfile.NamedTemporaryFile("w", suffix=e, delete=False) as f:
                f.write(text)
            cols = sc.read_data(f.name); os.unlink(f.name)
            return "numeric columns: " + ", ".join("%s (%d)" % (k, v.size) for k, v in cols.items())
        if e == ".seed":
            import seed_lang
            body = "\n".join(l for l in text.splitlines() if not l.startswith("# Groovebox seed program"))
            ev = seed_lang.evaluate(body, {"t": 0.0})
            return ("seed error: %s (line %d)" % (ev.error, ev.line)) if ev.error else "seed program OK · value(t=0) = %s" % (
                ", ".join("%.6g" % v for v in ev.values[:4]))
    except Exception as exc:
        return "check: %s" % exc
    return "%d characters · %d lines" % (len(text), text.count("\n") + 1)


def open_text(app, path):
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit, QLabel

    def make():
        w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("📝 %s" % os.path.basename(path)); w.resize(720, 560)
        lay = QVBoxLayout(w); ed = QPlainTextEdit(); ed.setStyleSheet("font-family:Consolas,monospace;font-size:10pt;")
        try:
            ed.setPlainText(open(path, encoding="utf-8", errors="replace").read())
        except Exception:
            pass
        lay.addWidget(ed, 1); st = QLabel(""); lay.addWidget(st)
        t = QTimer(w); t.setSingleShot(True); t.setInterval(400); t.timeout.connect(lambda: st.setText(check_text(path, ed.toPlainText())))
        ed.textChanged.connect(t.start); t.start()
        row = QHBoxLayout()

        def save():
            with open(path, "w", encoding="utf-8") as f:
                f.write(ed.toPlainText())
            st.setText("saved · " + check_text(path, ed.toPlainText()))

        def to_seed():
            import signal_converters as sc
            save(); seed, bpm = sc.read_seed(path) if path.lower().endswith(".seed") else (ed.toPlainText(), None)
            app.input_seed_val.setPlainText(seed)
            if bpm and hasattr(app, "spin_bpm"):
                app.spin_bpm.setValue(bpm)
            st.setText("seed field updated")
        for cap, fn in (("💾 Save", save), ("→ seed field", to_seed)):
            b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
        if not path.lower().endswith(".seed"):
            row.itemAt(1).widget().setVisible(False)
        row.addStretch(1); lay.addLayout(row)
        return w
    return _reuse(("text", os.path.abspath(path)), make)
