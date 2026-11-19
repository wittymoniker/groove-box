"""experiences.py — the EXPERIENCES browser: every creation and its science in one catalogue.

What it collects (indexed on open and whenever something is produced; nothing is moved or deleted):
  exports (audio / video / project OBJ / stems, with their .verify.json: checksum, format, length, audio check),
  Live Player takes, checkpoints and Autopilot projects, saved projects (project registry), Seed Atlas renders,
  carrier-layer mixes and music videos.
Per entry: kind, time, file, size, seed (text and fingerprint), canonical engines, BPM, base frequency, tuning,
the canonical distribution score J, loudness / peak (from the verify file), atlas address — plus YOUR fields:
rating (0–5), tags, notes. Lineage: entries that share a seed (or an atlas child seed) are linked.
Actions: open / play, show its science sheet, re-open its project, use its seed, compare two (project tools), export
the catalogue (JSON / CSV).
Index: ~/.local/share/groovebox/experiences.json
"""
from __future__ import annotations
import csv, hashlib, json, os, time

MEDIA = (".wav", ".flac", ".mp3", ".ogg", ".m4a", ".mp4", ".mov", ".mkv", ".webm", ".mcc", ".obj", ".png", ".json")


def _index_path():
    d = os.path.join(os.path.expanduser("~"), ".local", "share", "groovebox"); os.makedirs(d, exist_ok=True)
    return os.path.join(d, "experiences.json")


def load():
    try:
        d = __import__("safe_io").load_json(_index_path(), encoding="utf-8")
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(idx):
    tmp = _index_path() + ".part"
    __import__("safe_io").atomic_write_json(tmp, idx, indent=1, default=str, encoding="utf-8")
    os.replace(tmp, _index_path())


def _science(app):
    s = {}
    try:
        t = app._seed_text(); s["seed"] = t[:400]; s["seed_fp"] = hashlib.sha256(t.encode()).hexdigest()[:12]
    except Exception: pass
    for k, a in (("bpm", "spin_bpm"), ("base_hz", "spin_base_frequency")):
        try: s[k] = float(getattr(app, a).value())
        except Exception: pass
    try: s["canonicals"] = sorted(app._get_active_engine_set())
    except Exception: pass
    try: s["tuning"] = dict(getattr(app, "global_tuning", {}) or {})
    except Exception: pass
    try:
        import canonical_distributor as cd
        s["distribution_J"] = round(cd.objective(app, cd.current(app)), 4)
    except Exception: pass
    return s


def record(app, path, kind, extra=None):
    """Add / update one entry (called by exports, takes, checkpoints, atlas renders)."""
    if not path or not os.path.exists(path):
        return
    idx = load(); key = os.path.abspath(path)
    e = idx.get(key, {"rating": 0, "tags": [], "notes": ""})
    e.update({"kind": kind, "path": key, "time": os.path.getmtime(path), "bytes": os.path.getsize(path) if os.path.isfile(path) else 0})
    e.setdefault("science", {}).update(_science(app) if app is not None else {})
    if extra: e["science"].update(extra)
    v = key + ".verify.json"
    if os.path.isfile(v):
        try: e["verify"] = __import__("safe_io").load_json(v)
        except Exception: pass
    idx[key] = e; save(idx)


def _guess_kind(p):
    low = p.lower(); b = os.path.basename(low)
    if "checkpoints" in low: return "checkpoint"
    if "seed-atlas" in low or b.startswith("atlas-"): return "atlas"
    if "stems-" in low: return "stem"
    if "take" in b or "live" in b: return "take"
    if low.endswith((".mp4", ".mov", ".mkv", ".webm")): return "video"
    if low.endswith((".wav", ".flac", ".mp3", ".ogg", ".m4a")): return "audio"
    if low.endswith(".mcc"): return "project / media"
    if low.endswith(".obj"): return "3d"
    if low.endswith(".png"): return "image"
    return "file"


def scan(app):
    """Index everything the system produced (exports folder, checkpoints, registry, atlas)."""
    idx = load(); roots = []
    for fn in ("_exports_dir", "_audio_exports_dir", "_projects_dir"):
        try: roots.append(str(getattr(app, fn)()))
        except Exception: pass
    roots.append(os.path.join(os.path.expanduser("~"), ".local", "share", "groovebox", "checkpoints"))
    n = 0
    for root in roots:
        if not os.path.isdir(root): continue
        for dp, _dn, files in os.walk(root):
            for f in files:
                if not f.lower().endswith(MEDIA) or f.endswith(".verify.json") or f.endswith(".part"): continue
                p = os.path.abspath(os.path.join(dp, f))
                if p in idx and idx[p].get("time") == os.path.getmtime(p): continue
                e = idx.get(p, {"rating": 0, "tags": [], "notes": "", "science": {}})
                e.update(kind=_guess_kind(p), path=p, time=os.path.getmtime(p), bytes=os.path.getsize(p))
                if p.lower().endswith(".mcc"):
                    try:
                        with open(p, "rb") as fh:
                            head = fh.read(2_000_000)
                        if head[:1] == b"{":
                            d = json.loads(open(p, encoding="utf-8").read())
                            e["science"].update({k: d.get(k) for k in ("seed", "bpm", "base_frequency", "engines") if k in d})
                            e["science"]["seed_fp"] = hashlib.sha256(str(d.get("seed", "")).encode()).hexdigest()[:12]
                    except Exception:
                        pass
                v = p + ".verify.json"
                if os.path.isfile(v):
                    try: e["verify"] = __import__("safe_io").load_json(v)
                    except Exception: pass
                idx[p] = e; n += 1
    for p in [k for k in idx if not os.path.exists(k)]:
        idx[p]["missing"] = True
    save(idx)
    return n


def install(app):
    """Creations are recorded as they are made."""
    try:
        import studio_extras as se
        orig = se.on_export_finished
        if not getattr(orig, "_xp", False):
            def wrapped(app_, job, _o=orig):
                _o(app_, job)
                try:
                    p = str((getattr(job, "result", {}) or {}).get("file_path") or getattr(job, "out_file", "") or "")
                    if getattr(job, "state", "") == "done": record(app_, p, "export", {"job": getattr(job, "label", "")})
                except Exception: pass
            wrapped._xp = True; se.on_export_finished = wrapped
    except Exception:
        pass
    try:
        import project_transactions as pt
        o2 = pt.checkpoint
        if not getattr(o2, "_xp", False):
            def ck(app_, label="checkpoint", _o=o2):
                p = _o(app_, label)
                try: record(app_, p, "checkpoint", {"label": label})
                except Exception: pass
                return p
            ck._xp = True; pt.checkpoint = ck
    except Exception:
        pass
    try:
        import seed_atlas as sa
        o3 = sa.save
        if not getattr(o3, "_xp", False):
            def sv(node, folder, _o=o3):
                p = _o(node, folder)
                try: record(app, p, "atlas", {"atlas_address": node.get("address"), "atlas_seed": node.get("seed")})
                except Exception: pass
                return p
            sv._xp = True; sa.save = sv
    except Exception:
        pass


def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
                                 QPushButton, QLabel, QPlainTextEdit, QSpinBox, QSplitter, QHeaderView, QFileDialog)
    d = QDialog(app); d.setWindowTitle("🗺 Experiences · creations, their science, projects and files"); d.resize(1240, 720)
    d.setWindowModality(Qt.WindowModality.NonModal); lay = QVBoxLayout(d)
    top = QHBoxLayout(); lay.addLayout(top)
    q = QLineEdit(); q.setPlaceholderText("search: file, seed, tag, note, canonical, kind…"); kind = QComboBox(); kind.addItem("all kinds")
    minr = QSpinBox(); minr.setRange(0, 5); minr.setPrefix("rating ≥ ")
    b_scan = QPushButton("⟳ Scan creations"); b_csv = QPushButton("Export catalogue…")
    for w in (q, kind, minr, b_scan, b_csv): top.addWidget(w)
    split = QSplitter(); lay.addWidget(split, 1)
    cols = ("when", "kind", "file", "rating", "tags", "seed", "BPM", "canonicals", "J", "audio check")
    tab = QTableWidget(0, len(cols)); tab.setHorizontalHeaderLabels(cols); tab.setSortingEnabled(True)
    tab.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive); tab.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    split.addWidget(tab)
    side = QPlainTextEdit(); side.setReadOnly(True); split.addWidget(side); split.setSizes([860, 380])
    ed = QHBoxLayout(); lay.addLayout(ed)
    rate = QSpinBox(); rate.setRange(0, 5); rate.setPrefix("★ "); tags = QLineEdit(); tags.setPlaceholderText("tags, comma separated")
    notes = QLineEdit(); notes.setPlaceholderText("notes"); b_keep = QPushButton("Save rating / tags / notes")
    for w in (rate, tags, notes, b_keep): ed.addWidget(w)
    act = QHBoxLayout(); lay.addLayout(act)
    b_open = QPushButton("▶ Open / play"); b_proj = QPushButton("↺ Re-open its project"); b_seed = QPushButton("🌱 Use its seed")
    b_cmp = QPushButton("⚖ Compare two selected"); b_line = QPushButton("🧬 Lineage (same seed)")
    for w in (b_open, b_proj, b_seed, b_cmp, b_line): act.addWidget(w)
    state = {"rows": []}

    def fill():
        idx = load(); kinds = sorted({e.get("kind", "?") for e in idx.values()})
        cur = kind.currentText(); kind.blockSignals(True); kind.clear(); kind.addItem("all kinds"); kind.addItems(kinds)
        kind.setCurrentText(cur if cur in kinds else "all kinds"); kind.blockSignals(False)
        s = q.text().lower().strip(); rows = []
        for e in sorted(idx.values(), key=lambda e: -float(e.get("time", 0))):
            if kind.currentText() != "all kinds" and e.get("kind") != kind.currentText(): continue
            if int(e.get("rating", 0)) < minr.value(): continue
            if s and s not in json.dumps(e, default=str).lower(): continue
            rows.append(e)
        state["rows"] = rows; tab.setSortingEnabled(False); tab.setRowCount(len(rows))
        for i, e in enumerate(rows):
            sc = e.get("science", {}) or {}; v = e.get("verify", {}) or {}
            vals = (time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("time", 0))), e.get("kind", ""),
                    os.path.basename(e["path"]) + (" (missing)" if e.get("missing") else ""), "★" * int(e.get("rating", 0)),
                    ", ".join(e.get("tags", [])), str(sc.get("seed", ""))[:40].replace("\n", " "), str(sc.get("bpm", "")),
                    ",".join(sc.get("canonicals", []) or []), str(sc.get("distribution_J", "")), str(v.get("audio_check", "")))
            for c, val in enumerate(vals):
                it = QTableWidgetItem(val); it.setData(Qt.ItemDataRole.UserRole, i); tab.setItem(i, c, it)
        tab.setSortingEnabled(True)

    def sel():
        out = []
        for it in tab.selectedItems():
            r = it.data(Qt.ItemDataRole.UserRole)
            if r is not None and state["rows"][r] not in out: out.append(state["rows"][r])
        return out

    def show_sheet():
        s = sel()
        if not s: return
        e = s[0]; rate.setValue(int(e.get("rating", 0))); tags.setText(", ".join(e.get("tags", []))); notes.setText(e.get("notes", ""))
        side.setPlainText("SCIENCE SHEET\n" + json.dumps({k: e.get(k) for k in ("kind", "path", "bytes", "science", "verify")}, indent=1, default=str))

    def keep():
        idx = load()
        for e in sel():
            k = e["path"]; idx.setdefault(k, e)
            idx[k].update(rating=rate.value(), tags=[t.strip() for t in tags.text().split(",") if t.strip()], notes=notes.text())
        save(idx); fill()

    def open_it():
        for e in sel()[:1]:
            p = e["path"]
            if p.lower().endswith(".mcc") and "checkpoints" in p:
                __import__("project_transactions").restore(app, p)
            elif p.lower().endswith(".mcc"):
                try:
                    import mcc_media as mm
                    if mm.media_kind(p) in ("audio", "video"):
                        import media_visualizer as mv; mv.MccVideoPlayer(p, app, host=app).show(); return
                except Exception: pass
                app.open_project_path(p, show_message=False)
            else:
                import subprocess, shutil as sh
                opener = sh.which("xdg-open") or sh.which("open")
                if opener: subprocess.Popen([opener, p], start_new_session=True)

    def reopen():
        for e in sel()[:1]:
            p = e["path"]
            if p.lower().endswith(".mcc"):
                (__import__("project_transactions").restore(app, p) if "checkpoints" in p else app.open_project_path(p, show_message=False))

    def use_seed():
        for e in sel()[:1]:
            sd = (e.get("science", {}) or {}).get("atlas_seed") or (e.get("science", {}) or {}).get("seed")
            if sd and hasattr(app, "input_seed_val"):
                app._push_undo("Seed from Experiences"); app.input_seed_val.setPlainText(str(sd))

    def compare():
        s = [e for e in sel() if e["path"].lower().endswith((".mcc", ".json"))][:2]
        if len(s) == 2:
            import project_tools as pt
            try:
                diff = pt.compare(pt._load(s[0]["path"]), pt._load(s[1]["path"]))
                side.setPlainText("COMPARE\n%s\n%s\n\n" % (s[0]["path"], s[1]["path"]) + ("\n".join(diff) or "identical"))
            except Exception as exc:
                side.setPlainText("compare: %s" % exc)
        else:
            side.setPlainText("select two projects / checkpoints")

    def lineage():
        s = sel()
        if not s: return
        fp = (s[0].get("science", {}) or {}).get("seed_fp") or (s[0].get("science", {}) or {}).get("atlas_seed")
        q.setText(str(fp or "")); fill()

    def to_csv():
        p, _ = QFileDialog.getSaveFileName(d, "Catalogue", os.path.expanduser("~/experiences.csv"), "CSV (*.csv);;JSON (*.json)")
        if not p: return
        idx = load()
        if p.endswith(".json"):
            __import__("safe_io").atomic_write_json(p, idx, indent=1, default=str); return
        with open(p, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["time", "kind", "path", "rating", "tags", "notes", "seed", "bpm", "canonicals", "J", "audio_check"])
            for e in idx.values():
                sc = e.get("science", {}) or {}
                w.writerow([e.get("time"), e.get("kind"), e.get("path"), e.get("rating"), ";".join(e.get("tags", [])), e.get("notes"),
                            sc.get("seed"), sc.get("bpm"), ";".join(sc.get("canonicals", []) or []), sc.get("distribution_J"),
                            (e.get("verify") or {}).get("audio_check")])

    q.textChanged.connect(lambda *_: fill()); kind.currentIndexChanged.connect(lambda *_: fill()); minr.valueChanged.connect(lambda *_: fill())
    b_scan.clicked.connect(lambda: (scan(app), fill())); tab.itemSelectionChanged.connect(show_sheet); b_keep.clicked.connect(keep)
    b_open.clicked.connect(open_it); b_proj.clicked.connect(reopen); b_seed.clicked.connect(use_seed); b_cmp.clicked.connect(compare)
    b_line.clicked.connect(lineage); b_csv.clicked.connect(to_csv)
    try: scan(app)
    except Exception: pass
    fill(); d.show(); app._experiences = d
    return d
