"""project_tools.py — Project health report, project comparison, batch project browser, render preview,
instrument template library and sequence morph. All read-only except Apply buttons (which push an undo first)."""
from __future__ import annotations
import copy, json, os, time


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    d.pop("_checkpoint", None)
    return d


def health(app):
    """List problems: missing media, empty playlist, broken playlist references, invalid numbers."""
    import math
    issues = []
    for k, v in (getattr(app, "instrument_media_samples", {}) or {}).items():
        p = (v or {}).get("path") if isinstance(v, dict) else None
        if p and not os.path.isfile(p): issues.append("missing sample for %s: %s" % (k, p))
    names = set(getattr(app, "instrument_names_48", []) or [])
    pl = getattr(app, "master_playlist_data", []) or []
    if not any(isinstance(r, dict) and r for r in pl): issues.append("playlist is empty")
    for i, r in enumerate(pl):
        op = str((r or {}).get("operator") or "") if isinstance(r, dict) else ""
        if op and op not in names: issues.append("row %d points at unknown instrument %r" % (i + 1, op))
    for n, st in (getattr(app, "instrument_param_state", {}) or {}).items():
        for k, v in (st or {}).items():
            if isinstance(v, float) and not math.isfinite(v): issues.append("%s.%s is not finite" % (n, k))
    for n, bank in (getattr(app, "instrument_sequence_banks", {}) or {}).items():
        for sid, m in (bank or {}).items():
            st = (m or {}).get("steps") if isinstance(m, dict) else None
            if isinstance(st, list) and isinstance(m.get("amplitudes"), list) and len(m["amplitudes"]) < len(st):
                issues.append("%s seq %s: amplitude lane shorter than steps" % (n, sid))
    vp = getattr(app, "video_obj_paths", None) or []
    for p in vp:
        if p and not os.path.isfile(p): issues.append("missing OBJ: %s" % p)
    try:
        import audio_diagnostics as ad
        ok, msg = ad.pre_export_check(app)
        if msg: issues.append(("" if ok else "⚠ ") + msg)
    except Exception:
        pass
    return issues or ["no problems found"]


def compare(a, b, path="", out=None, limit=400):
    out = [] if out is None else out
    if len(out) >= limit: return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k in ("ui_auto", "ui_state", "project_uid"): continue
            if k not in a: out.append("+ %s/%s" % (path, k))
            elif k not in b: out.append("- %s/%s" % (path, k))
            else: compare(a[k], b[k], "%s/%s" % (path, k), out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and len(a) < 2048:
        for i, (x, y) in enumerate(zip(a, b)): compare(x, y, "%s[%d]" % (path, i), out, limit)
    elif a != b:
        sa, sb = str(a)[:60], str(b)[:60]
        out.append("~ %s: %s → %s" % (path, sa, sb))
    return out


def morph_sequences(m1, m2, u):
    """Mathematical morph of two sequence memories: numeric lanes interpolate, steps switch at their own threshold."""
    out = copy.deepcopy(m1)
    n = min(len(m1.get("steps", [])), len(m2.get("steps", [])))
    for k in ("amplitudes", "pitches", "offsets"):
        a, b = m1.get(k, []), m2.get(k, [])
        for i in range(min(n, len(a), len(b))):
            out[k][i] = (1 - u) * float(a[i]) + u * float(b[i]) if k != "pitches" else float(a[i]) ** (1 - u) * float(b[i]) ** u
    for i in range(n):
        thr = ((i * 0.6180339887) % 1.0)
        out["steps"][i] = bool(m2["steps"][i]) if u > thr else bool(m1["steps"][i])
    return out


def _tpl_dir():
    d = os.path.join(os.path.expanduser("~"), ".local", "share", "groovebox", "instrument_templates")
    os.makedirs(d, exist_ok=True); return d


def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QPlainTextEdit, QPushButton,
                                 QFileDialog, QListWidget, QSpinBox, QLabel, QComboBox, QDoubleSpinBox, QLineEdit)
    d = QDialog(app); d.setWindowTitle("🩺 Project tools"); d.resize(820, 560); d.setWindowModality(Qt.WindowModality.NonModal)
    tabs = QTabWidget(); QVBoxLayout(d).addWidget(tabs)

    def page(title):
        w = QWidget(); l = QVBoxLayout(w); tabs.addTab(w, title); return l
    # health
    l = page("Health"); txt = QPlainTextEdit(); txt.setReadOnly(True); b = QPushButton("Run health report")
    b.clicked.connect(lambda: txt.setPlainText("\n".join(health(app)))); l.addWidget(b); l.addWidget(txt)
    # compare
    l = page("Compare"); ctx = QPlainTextEdit(); ctx.setReadOnly(True)
    row = QHBoxLayout(); l.addLayout(row)
    bc = QPushButton("Current project vs file…"); bf = QPushButton("File vs file…")
    row.addWidget(bc); row.addWidget(bf); l.addWidget(ctx)

    def cur_vs():
        p, _ = QFileDialog.getOpenFileName(d, "Compare with", os.path.expanduser("~"), "Projects (*.MCC *.mcc *.json)")
        if p: ctx.setPlainText("\n".join(compare(app._project_snapshot(), _load(p))) or "identical")

    def f_vs():
        a, _ = QFileDialog.getOpenFileName(d, "First project", os.path.expanduser("~"), "Projects (*.MCC *.mcc *.json)")
        b2, _ = QFileDialog.getOpenFileName(d, "Second project", os.path.expanduser("~"), "Projects (*.MCC *.mcc *.json)")
        if a and b2: ctx.setPlainText("\n".join(compare(_load(a), _load(b2))) or "identical")
    bc.clicked.connect(cur_vs); bf.clicked.connect(f_vs)
    # batch browser (checkpoints + folder)
    l = page("Batch browser"); lst = QListWidget(); l.addWidget(lst)
    row = QHBoxLayout(); l.addLayout(row)
    bfold = QPushButton("Folder…"); bck = QPushButton("Checkpoints / Autopilot projects"); bopen = QPushButton("Open selected")
    bexp = QPushButton("Open + export mixdown")
    for x in (bfold, bck, bopen, bexp): row.addWidget(x)
    files = []

    def fill(paths):
        files[:] = paths; lst.clear()
        for p in paths: lst.addItem(time.strftime("%Y-%m-%d %H:%M ", time.localtime(os.path.getmtime(p))) + os.path.basename(p))
    bfold.clicked.connect(lambda: (lambda f: f and fill(sorted((os.path.join(f, n) for n in os.listdir(f) if n.lower().endswith(".mcc")), key=os.path.getmtime, reverse=True)))(
        QFileDialog.getExistingDirectory(d, "Project folder", os.path.expanduser("~"))))
    bck.clicked.connect(lambda: fill(__import__("project_transactions").checkpoints()))

    def _open(export=False):
        i = lst.currentRow()
        if i < 0: return
        p = files[i]
        if "checkpoints" in p: __import__("project_transactions").restore(app, p)
        else: app.open_project_path(p, show_message=False)
        if export: app.export_mixdown_dialog()
    bopen.clicked.connect(lambda: _open()); bexp.clicked.connect(lambda: _open(True))
    # render preview
    l = page("Render preview"); row = QHBoxLayout(); l.addLayout(row)
    rows = QSpinBox(); rows.setRange(1, 4096); rows.setValue(4); rows.setPrefix("first rows ")
    bp = QPushButton("Render + play preview"); info = QLabel("")
    row.addWidget(rows); row.addWidget(bp); l.addWidget(info); l.addStretch(1)

    def prev():
        info.setText("rendering…")

        def done(buf, sr, err=""):
            if err or buf is None: info.setText("preview failed: %s" % err); return
            try:
                import audio_diagnostics as ad
                info.setText(ad.check_buffer(buf, sr, "preview")[1])
                import sounddevice as sd, numpy as np
                b2 = np.asarray(buf, dtype=np.float32); sd.play(b2.mean(axis=1) if b2.ndim > 1 else b2, int(sr))
            except Exception as exc:
                info.setText("preview rendered; playback unavailable: %s" % exc)
        app._render_in_process_async("Preview", done, max_rows=int(rows.value()))
    bp.clicked.connect(prev)
    # instrument templates
    l = page("Instrument templates"); tl = QListWidget(); l.addWidget(tl)
    row = QHBoxLayout(); l.addLayout(row); nm = QLineEdit(); nm.setPlaceholderText("template name")
    bs = QPushButton("Save selected instrument"); ba = QPushButton("Apply to selected instrument"); bm = QPushButton("Combine two (50/50)")
    for x in (nm, bs, ba, bm): row.addWidget(x)

    def tfill():
        tl.clear(); [tl.addItem(n[:-5]) for n in sorted(os.listdir(_tpl_dir())) if n.endswith(".json")]

    def tsave():
        name = app._current_instrument_name()
        data = {"params": (app.instrument_param_state or {}).get(name, {}), "script": (app.instrument_scripts or {}).get(name, "")}
        with open(os.path.join(_tpl_dir(), (nm.text().strip() or name).replace("/", "_") + ".json"), "w") as f: json.dump(data, f, default=str)
        tfill()

    def tload(n):
        with open(os.path.join(_tpl_dir(), n + ".json")) as f: return json.load(f)

    def tapply():
        it = tl.currentItem()
        if it is None: return
        app._push_undo("Apply instrument template"); name = app._current_instrument_name(); t = tload(it.text())
        app.instrument_param_state.setdefault(name, {}).update(t.get("params", {}))
        if t.get("script"): app.instrument_scripts[name] = t["script"]
        app._on_live_source_changed()

    def tmix():
        sel = tl.selectedItems() or ([tl.currentItem()] if tl.currentItem() else [])
        if len(sel) < 2 and tl.count() >= 2: sel = [tl.item(0), tl.item(1)]
        if len(sel) < 2: return
        a, b2 = tload(sel[0].text())["params"], tload(sel[1].text())["params"]
        mix = {k: (0.5 * a[k] + 0.5 * b2[k]) if isinstance(a.get(k), (int, float)) and isinstance(b2.get(k), (int, float)) else a.get(k, b2.get(k)) for k in set(a) | set(b2)}
        with open(os.path.join(_tpl_dir(), "%s+%s.json" % (sel[0].text(), sel[1].text())), "w") as f: json.dump({"params": mix}, f, default=str)
        tfill()
    tl.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    bs.clicked.connect(tsave); ba.clicked.connect(tapply); bm.clicked.connect(tmix); tfill()
    # sequence morph
    l = page("Sequence morph"); row = QHBoxLayout(); l.addLayout(row)
    sa, sb = QSpinBox(), QSpinBox(); sa.setRange(1, 256); sb.setRange(1, 256); sb.setValue(2)
    u = QDoubleSpinBox(); u.setRange(0, 1); u.setSingleStep(0.05); u.setValue(0.5)
    bmo = QPushButton("Write morph into a new sequence")
    for x in (QLabel("from seq"), sa, QLabel("to seq"), sb, QLabel("amount"), u, bmo): row.addWidget(x)
    mo = QLabel(""); l.addWidget(mo); l.addStretch(1)

    def morph():
        name = app._current_instrument_name(); bank = app.instrument_sequence_banks.get(name) or {}
        m1, m2 = bank.get(sa.value()), bank.get(sb.value())
        if not m1 or not m2: mo.setText("both sequences must exist"); return
        app._push_undo("Sequence morph")
        new = morph_sequences(m1, m2, u.value()); nid = max(bank) + 1; new["sequence_id"] = nid; new["user_owned"] = True
        bank[nid] = new; mo.setText("written as SEQ #%d" % nid)
        try: app._refresh_sequence_selector() if hasattr(app, "_refresh_sequence_selector") else None
        except Exception: pass
        app._on_live_source_changed()
    bmo.clicked.connect(morph)
    d.show(); app._project_tools = d; return d
