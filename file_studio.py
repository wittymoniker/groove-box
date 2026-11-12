"""file_studio.py — GROOVEBOX_R32_FILE_STUDIO_20261110

App-wide file motility AND editing: eight launchers in one window (each tab can also be
opened alone from the Quick Rack ▸ 📂 menu). Every action goes through the project path
helpers, so files stay inside their project workspace (no nested folders).

  1 📁 Projects     open · rename (folder + document together) · duplicate · move to drive ·
                    delete to Trash · repair nested workspaces (flattens …/X/X/X/)
  2 🧾 MCC editor   the project document as a validated JSON tree: edit a value, add/remove
                    keys, diff against the saved file, save (atomic, .prev kept) and reload
  3 🎚 Samples      preview · trim (start/end s) · normalize · reverse · fade · rename ·
                    send to: selected instrument / sample generator / clip editor
  4 🎬 Exports      play · reveal · convert (ffmpeg: wav/flac/mp3/ogg/mp4/webm) · send to
                    Post-Process / Clip Editor / Live Player / drive
  5 🌱 Seeds        a library of seed programs (.seed text files): save current, load,
                    edit in place with live analysis, morph two (Compose)
  6 🎛 Presets      FX / time FX / synth engine / playability / blueprint presets as JSON:
                    capture from the app, edit, apply
  7 🎙 Recordings   live takes: play · finish (Post-Process take finisher) · move to exports
  8 🕘 Versions     .prev generations, before-autosave copies and autosaves of the open
                    project: compare sizes/dates, restore any (Undo-safe: current saved first)
Drag files from the OS onto any list to import them into the right project folder.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QListWidget, QListWidgetItem, QPushButton,
                             QLabel, QLineEdit, QTextEdit, QFileDialog, QInputDialog, QMessageBox, QTreeWidget,
                             QTreeWidgetItem, QDoubleSpinBox, QComboBox, QSplitter)

AUDIO = (".wav", ".flac", ".aiff", ".aif", ".mp3", ".ogg", ".opus", ".m4a")
VIDEO = (".mp4", ".mkv", ".webm", ".mov", ".avi")


def _gp():
    import groovebox_paths
    return groovebox_paths


def _root(app):
    return str(_gp().project_root(getattr(app, "_current_project_path", None)))


def _ls(folder, exts=None, recursive=True):
    out = []
    if not os.path.isdir(folder):
        return out
    for r, ds, fs in os.walk(folder):
        ds[:] = [d for d in ds if not d.startswith(".") and d != "cache"]
        for f in fs:
            if exts is None or f.lower().endswith(exts):
                out.append(os.path.join(r, f))
        if not recursive:
            break
    return sorted(out, key=lambda p: -os.path.getmtime(p))


def _open_os(path):
    from PyQt6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def _trash(path):
    from drive_guard import assert_safe_path
    path = assert_safe_path(path)
    dst = os.path.join(_gp().trash_dir(), "%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), os.path.basename(path)))
    shutil.move(path, dst)
    return dst


def _safe(path):
    from drive_guard import assert_safe_path
    return assert_safe_path(path)


class _DropList(QListWidget):
    def __init__(self, on_drop):
        super().__init__(); self.on_drop = on_drop; self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, e):
        self.on_drop([u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()])


def _fill(lst, paths, base):
    lst.clear()
    for p in paths:
        it = QListWidgetItem(os.path.relpath(p, base) if p.startswith(base) else p)
        it.setData(Qt.ItemDataRole.UserRole, p)
        try:
            it.setToolTip("%s · %.1f KB · %s" % (p, os.path.getsize(p) / 1024, time.ctime(os.path.getmtime(p))))
        except OSError:
            pass
        lst.addItem(it)


def _sel(lst):
    return [i.data(Qt.ItemDataRole.UserRole) for i in lst.selectedItems()]


def _buttons(lay, spec):
    row = QHBoxLayout()
    for cap, fn in spec:
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    lay.addLayout(row)


# ---------------------------------------------------------------------------
# audio helpers (numpy + soundfile / ffmpeg; no filters)
# ---------------------------------------------------------------------------
def _read(path):
    import postprocess_window as pw
    return pw.read_audio(path)


def _write(path, y, sr):
    import postprocess_window as pw
    return pw.write_audio(path, y, sr)


def edit_audio(path, op, **kw):
    import numpy as np
    import hardcoded_fx as hfx
    y, sr = _read(path)
    if op == "trim":
        a, b = int(kw.get("start", 0) * sr), int(kw.get("end", 0) * sr) or y.shape[0]
        y = y[max(0, a):max(a + 1, min(y.shape[0], b))]
    elif op == "normalize":
        y, _ = hfx.peak_normalize(y, 0.97)
    elif op == "reverse":
        y = y[::-1].copy()
    elif op == "fade":
        y = hfx.isn_fade(y, sr, kw.get("fade_in", 0.01), kw.get("fade_out", 0.25))
    out = os.path.splitext(path)[0] + ("." + op if kw.get("copy", True) else "") + ".wav"
    return _write(out, y, sr)


def ffmpeg_convert(path, ext):
    ff = shutil.which("ffmpeg")
    if not ff:
        return "ffmpeg not found"
    out = os.path.splitext(path)[0] + "." + ext.lstrip(".")
    if os.path.abspath(out) == os.path.abspath(path):
        out = os.path.splitext(path)[0] + ".converted." + ext.lstrip(".")
    r = subprocess.run([ff, "-y", "-v", "error", "-i", path, out], capture_output=True, text=True, timeout=1800)
    return out if r.returncode == 0 else ("ffmpeg failed: " + r.stderr[-300:])


def repair_nested(root_dir):
    """Flatten …/Name/Name/…: move documents up into the outermost workspace with that name."""
    moved = []
    for r, ds, fs in os.walk(root_dir, topdown=False):
        name = os.path.basename(r)
        parent = os.path.dirname(r)
        if os.path.basename(parent) == name or os.path.basename(parent) == "metadata":
            tgt = parent if os.path.basename(parent) == name else os.path.dirname(parent)
            for f in fs:
                if f.lower().endswith(".mcc"):
                    src, dst = os.path.join(r, f), os.path.join(tgt, f)
                    if not os.path.exists(dst):
                        shutil.move(src, dst); moved.append(dst)
    return moved


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------
TABS = ("Projects", "MCC editor", "Samples", "Exports", "Seeds", "Presets", "Recordings", "Versions", "Caches")


def open_window(app, tab=None):
    w = getattr(app, "_file_studio_window", None)
    try:
        if w is not None:
            w.show(); w.raise_()
            if tab in TABS:
                w._tabs.setCurrentIndex(TABS.index(tab))
            return w
    except RuntimeError:
        pass
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("📂 File Studio · move and edit everything")
    w.resize(980, 680); root = QVBoxLayout(w)
    banner = QLabel("System drive is locked. Format, partition, and file moves cannot touch the OS disk or /boot /usr /opt /etc.")
    banner.setWordWrap(True); banner.setStyleSheet("color:#f5d97d;")
    root.addWidget(banner)
    tabs = QTabWidget(); root.addWidget(tabs); w._tabs = tabs
    status = QLabel(""); root.addWidget(status)
    say = status.setText

    def guard(fn):
        def _g(*_a):
            try:
                r = fn()
                if isinstance(r, str):
                    say(r)
            except Exception as exc:
                say("⚠ %s" % exc)
        return _g

    # 1 Projects ---------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "📁 Projects")
    base = _gp().projects_dir()
    projs = _DropList(lambda ps: [shutil.copy2(p, _gp().canonical_project_path(os.path.join(base, os.path.basename(p)))) for p in ps if p.lower().endswith(".mcc")] and refresh_projects())
    l.addWidget(projs)

    def refresh_projects():
        _fill(projs, _ls(base, (".mcc", ".MCC")), base)

    def p_open():
        for p in _sel(projs)[:1]:
            app.open_project_path(p); return "opened " + p

    def p_rename():
        for p in _sel(projs)[:1]:
            new, ok = QInputDialog.getText(w, "Rename project", "New name:", text=os.path.splitext(os.path.basename(p))[0])
            if not ok or not new.strip():
                return
            safe = _gp()._safe_project_name(new)
            folder = os.path.dirname(p)
            tgt_folder = os.path.join(os.path.dirname(folder), safe) if os.path.basename(folder) == os.path.splitext(os.path.basename(p))[0] else folder
            if tgt_folder != folder:
                shutil.move(folder, tgt_folder)
            old_doc = os.path.join(tgt_folder, os.path.basename(p))
            new_doc = os.path.join(tgt_folder, safe + ".MCC")
            os.replace(old_doc, new_doc)
            if os.path.abspath(str(getattr(app, "_current_project_path", ""))) == os.path.abspath(p):
                app._current_project_path = new_doc
            refresh_projects(); return "renamed → " + new_doc

    def p_dup():
        for p in _sel(projs)[:1]:
            stem = os.path.splitext(os.path.basename(p))[0]
            n = 2
            while os.path.exists(os.path.join(base, "%s %d" % (stem, n))):
                n += 1
            src = os.path.dirname(p); dst = os.path.join(base, "%s %d" % (stem, n))
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("cache", "*.lock"))
            os.replace(os.path.join(dst, os.path.basename(p)), os.path.join(dst, "%s %d.MCC" % (stem, n)))
            refresh_projects(); return "duplicated → " + dst

    def p_drive():
        try:
            from drive_targets import removable_drives
            drives = removable_drives()
        except Exception:
            drives = []
        if not drives:
            return "no removable drive mounted — plug in a USB or SD stick"
        labels = ["%s  (%s free)" % (d.get("path"), d.get("free", "?")) for d in drives]
        d, ok = QInputDialog.getItem(w, "Copy to removable drive", "USB / SD only. The OS disk is not listed.", labels, 0, False)
        if not ok:
            return None
        dest = drives[labels.index(d)]["path"]
        from drive_guard import assert_safe_path
        dest = assert_safe_path(dest)
        for pth in _sel(projs):
            shutil.copytree(os.path.dirname(pth), os.path.join(dest, os.path.basename(os.path.dirname(pth))), dirs_exist_ok=True)
        return "copied to " + dest

    def p_trash():
        ps = _sel(projs)
        if ps and QMessageBox.question(w, "Move to Trash", "Move %d project folder(s) to the Groovebox Trash?" % len(ps)) == QMessageBox.StandardButton.Yes:
            for p in ps:
                _trash(os.path.dirname(p))
            refresh_projects(); return "moved to Trash: %d" % len(ps)

    _buttons(l, (("Open", guard(p_open)), ("Rename", guard(p_rename)), ("Duplicate", guard(p_dup)),
                 ("Copy to drive…", guard(p_drive)), ("Move to Trash", guard(p_trash)),
                 ("Repair nested folders", guard(lambda: (refresh_projects(), "repaired: %d" % len(repair_nested(base)))[1])),
                 ("Refresh", guard(refresh_projects))))
    refresh_projects()

    # 2 MCC editor ---------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🧾 MCC editor")
    tree = QTreeWidget(); tree.setHeaderLabels(["key", "value"]); tree.setColumnWidth(0, 320)
    l.addWidget(tree)
    state = {"path": None, "data": None}

    def _build(parent, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                it = QTreeWidgetItem(parent, [str(k), "" if isinstance(v, (dict, list)) else json.dumps(v)[:400]])
                it.setData(0, Qt.ItemDataRole.UserRole, k)
                if not isinstance(v, (dict, list)):
                    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
                _build(it, v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:500]):
                it = QTreeWidgetItem(parent, ["[%d]" % i, "" if isinstance(v, (dict, list)) else json.dumps(v)[:400]])
                it.setData(0, Qt.ItemDataRole.UserRole, i)
                if not isinstance(v, (dict, list)):
                    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
                _build(it, v)

    def m_load(path=None):
        path = path or getattr(app, "_current_project_path", None)
        if not path:
            path, _ = QFileDialog.getOpenFileName(w, "MCC document", base, "MCC (*.MCC *.mcc)")
        if not path:
            return
        with open(path, encoding="utf-8") as f:
            state["data"] = json.load(f)
        state["path"] = path
        tree.clear(); _build(tree.invisibleRootItem(), state["data"]); return "loaded " + path

    def _path_of(it):
        keys = []
        while it is not None:
            keys.append(it.data(0, Qt.ItemDataRole.UserRole)); it = it.parent()
        return keys[::-1]

    def on_edit(it, col):
        if col != 1 or state["data"] is None:
            return
        keys = _path_of(it); obj = state["data"]
        for k in keys[:-1]:
            obj = obj[k]
        try:
            obj[keys[-1]] = json.loads(it.text(1))
            it.setForeground(1, Qt.GlobalColor.darkGreen)
        except Exception:
            it.setForeground(1, Qt.GlobalColor.red); say("not valid JSON: %s" % it.text(1))
    tree.itemChanged.connect(on_edit)

    def m_save():
        if state["data"] is None:
            return "nothing loaded"
        app._atomic_write_document(state["path"], state["data"])
        return "saved %s (previous kept as .prev)" % state["path"]

    def m_apply():
        if state["data"] is None:
            return
        app._push_undo("MCC editor apply") if hasattr(app, "_push_undo") else None
        app._apply_project_snapshot(state["data"]); return "applied to the running project (Undo restores)"

    def m_diff():
        if state["data"] is None:
            return
        with open(state["path"], encoding="utf-8") as f:
            disk = json.load(f)
        ch = [k for k in set(disk) | set(state["data"]) if disk.get(k) != state["data"].get(k)]
        return "changed top-level keys: " + (", ".join(sorted(ch)) or "none")
    _buttons(l, (("Load open project", guard(m_load)), ("Load file…", guard(lambda: m_load(QFileDialog.getOpenFileName(w, "MCC", base, "MCC (*.MCC *.mcc)")[0] or None))),
                 ("Diff vs disk", guard(m_diff)), ("Apply to app", guard(m_apply)), ("Save", guard(m_save))))

    # 3 Samples -----------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🎚 Samples")
    sdir = lambda: _gp().samples_dir(getattr(app, "_current_project_path", None))
    samples = _DropList(lambda ps: ([_gp().ingest_file(p, "sample", getattr(app, "_current_project_path", None)) for p in ps], refresh_samples()))
    l.addWidget(samples)

    def refresh_samples():
        _fill(samples, _ls(sdir(), AUDIO) + _ls(_gp().global_samples_dir(), AUDIO), _root(app))
    tr_a = QDoubleSpinBox(); tr_a.setRange(0, 3600); tr_a.setPrefix("start "); tr_a.setSuffix(" s")
    tr_b = QDoubleSpinBox(); tr_b.setRange(0, 3600); tr_b.setPrefix("end "); tr_b.setSuffix(" s")
    row = QHBoxLayout(); row.addWidget(tr_a); row.addWidget(tr_b); l.addLayout(row)

    def s_op(op):
        def _f():
            outs = [edit_audio(p, op, start=tr_a.value(), end=tr_b.value()) for p in _sel(samples)]
            refresh_samples(); return "%s → %s" % (op, ", ".join(os.path.basename(o) for o in outs))
        return _f

    def s_preview():
        for p in _sel(samples)[:1]:
            import sounddevice as sd
            y, sr = _read(p); sd.stop(); sd.play(y, sr); return "playing " + os.path.basename(p)

    def s_to_instrument():
        for p in _sel(samples)[:1]:
            for fn in ("_load_sample_for_instrument", "load_sample_to_selected_instrument", "_assign_sample_to_instrument"):
                f = getattr(app, fn, None)
                if callable(f):
                    f(p); return "sample → selected instrument"
            return "no sample loader found on this build"

    def s_to_generator():
        for p in _sel(samples)[:1]:
            import sample_generator as sg, numpy as np
            y, sr = _read(p)
            gen = app.r32_sample_global if hasattr(app, "r32_sample_global") else None
            if gen is None:
                return "sample generator not installed"
            gen.buffer = (y if y.ndim == 1 else y.mean(axis=1)).astype("float32"); gen.sr = sr
            return "sample → global sample generator (set Layer to hear it)"

    def s_rename():
        for p in _sel(samples)[:1]:
            new, ok = QInputDialog.getText(w, "Rename", "New file name:", text=os.path.basename(p))
            if ok and new.strip():
                os.replace(p, os.path.join(os.path.dirname(p), new.strip())); refresh_samples()
    _buttons(l, (("▶ Preview", guard(s_preview)), ("Trim", guard(s_op("trim"))), ("Normalize", guard(s_op("normalize"))),
                 ("Reverse", guard(s_op("reverse"))), ("Fade", guard(s_op("fade"))), ("Rename", guard(s_rename)),
                 ("→ instrument", guard(s_to_instrument)), ("→ sample generator", guard(s_to_generator)), ("Refresh", guard(refresh_samples))))
    refresh_samples()

    # 4 Exports -----------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🎬 Exports")
    exps = _DropList(lambda ps: None); l.addWidget(exps)

    def refresh_exports():
        _fill(exps, _ls(os.path.join(_root(app), "exports"), AUDIO + VIDEO + (".mcc", ".MCC")) +
              _ls(_gp().global_exports_dir(), AUDIO + VIDEO), _root(app))
    fmt = QComboBox(); fmt.addItems(["wav", "flac", "mp3", "ogg", "mp4", "webm"])
    row = QHBoxLayout(); row.addWidget(QLabel("Convert to")); row.addWidget(fmt); l.addLayout(row)

    def e_convert():
        outs = [ffmpeg_convert(p, fmt.currentText()) for p in _sel(exps)]; refresh_exports(); return " · ".join(outs)

    def e_post():
        import postprocess_window as pw
        win = pw.open_window(app); win.add_paths(_sel(exps)); return "sent to Post-Process"

    def e_clip():
        for fn in ("_r32_open_clip_editor", "open_clip_timeline_studio", "_open_clip_studio"):
            f = getattr(app, fn, None)
            if callable(f):
                win = f()
                if win is not None and hasattr(win, "_add_media_paths"):
                    win._add_media_paths(_sel(exps))
                return "sent to Clip Editor"
        return "Clip Editor opener not found"

    def e_live():
        lp = getattr(app, "_live_player_window", None)
        if lp is not None and hasattr(lp, "load_paths"):
            lp.load_paths(_sel(exps)); return "sent to Live Player"
        return "open the Live Player first"
    _buttons(l, (("▶ Play", guard(lambda: [_open_os(p) for p in _sel(exps)][:0] or "opened")),
                 ("Reveal folder", guard(lambda: [_open_os(os.path.dirname(p)) for p in _sel(exps)][:0] or "")),
                 ("Convert", guard(e_convert)), ("→ Post-Process", guard(e_post)), ("→ Clip Editor", guard(e_clip)),
                 ("→ Live Player", guard(e_live)), ("Refresh", guard(refresh_exports))))
    refresh_exports()

    # 5 Seeds -----------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🌱 Seeds")
    seed_dir = os.path.join(_gp().state_dir(), "seeds"); os.makedirs(seed_dir, exist_ok=True)
    sp = QSplitter(); seeds = QListWidget(); sed = QTextEdit(); sed.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;")
    sp.addWidget(seeds); sp.addWidget(sed); sp.setSizes([260, 680]); l.addWidget(sp, 1)
    sdiag = QLabel(""); l.addWidget(sdiag)

    def refresh_seeds():
        _fill(seeds, _ls(seed_dir, (".seed",)), seed_dir)
    seeds.currentItemChanged.connect(lambda it, _p: sed.setPlainText(open(it.data(Qt.ItemDataRole.UserRole), encoding="utf-8").read()) if it else None)

    def _analyse():
        try:
            import seed_lang, groovebox as gb
            d = seed_lang.analyze(sed.toPlainText(), set(gb._seed_script_env(0.0).keys()))
            sdiag.setText(d[0] if d else "✓ %d lines · valid" % (sed.toPlainText().count("\n") + 1))
        except Exception as exc:
            sdiag.setText(str(exc))
    sed.textChanged.connect(_analyse)

    def seed_save_current():
        name, ok = QInputDialog.getText(w, "Save seed", "Name:", text=time.strftime("seed %Y-%m-%d %H%M"))
        if ok and name.strip():
            with open(os.path.join(seed_dir, _gp()._safe_project_name(name) + ".seed"), "w", encoding="utf-8") as f:
                f.write(app._seed_text())
            refresh_seeds()

    def seed_save_edit():
        it = seeds.currentItem()
        if it:
            with open(it.data(Qt.ItemDataRole.UserRole), "w", encoding="utf-8") as f:
                f.write(sed.toPlainText())
            return "saved"

    def seed_load():
        app.input_seed_val.setPlainText(sed.toPlainText()); return "loaded into the seed field"
    _buttons(l, (("Save current seed", guard(seed_save_current)), ("Save edits", guard(seed_save_edit)),
                 ("Load into project", guard(seed_load)), ("Morph… (Compose)", guard(lambda: __import__("composition_tools").open_window(app) and "")),
                 ("Delete", guard(lambda: [_trash(p) for p in [seeds.currentItem().data(Qt.ItemDataRole.UserRole)]] and refresh_seeds()))))
    refresh_seeds()

    # 6 Presets -----------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🎛 Presets")
    pdir = os.path.join(_gp().state_dir(), "presets"); os.makedirs(pdir, exist_ok=True)
    sp = QSplitter(); plist = QListWidget(); ped = QTextEdit(); ped.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;")
    sp.addWidget(plist); sp.addWidget(ped); sp.setSizes([260, 680]); l.addWidget(sp, 1)
    SOURCES = {"fx": "r32_fx_state", "time_fx": "r32_time_fx", "synth_engine": "r32_synth_engine",
               "post": "blueprint_post_settings", "blueprint": "project_blueprint", "geo_mixer": "geometric_synth_mixer_state"}
    kind = QComboBox(); kind.addItems(list(SOURCES)); l.addWidget(kind)

    def refresh_presets():
        _fill(plist, _ls(pdir, (".json",)), pdir)
    plist.currentItemChanged.connect(lambda it, _p: ped.setPlainText(open(it.data(Qt.ItemDataRole.UserRole), encoding="utf-8").read()) if it else None)

    def pr_capture():
        k = kind.currentText(); val = getattr(app, SOURCES[k], None)
        name, ok = QInputDialog.getText(w, "Capture preset", "Name:", text="%s %s" % (k, time.strftime("%H%M%S")))
        if ok and name.strip():
            with open(os.path.join(pdir, _gp()._safe_project_name(name) + ".json"), "w", encoding="utf-8") as f:
                json.dump({"kind": k, "value": val}, f, indent=1, default=str)
            refresh_presets()

    def pr_apply():
        d = json.loads(ped.toPlainText())
        attr = SOURCES.get(d.get("kind"))
        if not attr:
            return "unknown preset kind"
        cur = getattr(app, attr, None)
        if isinstance(cur, dict) and isinstance(d.get("value"), dict):
            cur.clear(); cur.update(d["value"])
        else:
            setattr(app, attr, d.get("value"))
        getattr(app, "_on_live_source_changed", lambda: None)(); return "applied %s preset" % d.get("kind")

    def pr_save():
        it = plist.currentItem()
        if it:
            json.loads(ped.toPlainText())
            with open(it.data(Qt.ItemDataRole.UserRole), "w", encoding="utf-8") as f:
                f.write(ped.toPlainText())
            return "saved"
    _buttons(l, (("Capture from app", guard(pr_capture)), ("Save edits", guard(pr_save)), ("Apply", guard(pr_apply)), ("Refresh", guard(refresh_presets))))
    refresh_presets()

    # 7 Recordings ---------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🎙 Recordings")
    recs = _DropList(lambda ps: None); l.addWidget(recs)

    def refresh_recs():
        _fill(recs, _ls(_gp().recordings_dir(getattr(app, "_current_project_path", None)), AUDIO + VIDEO + (".mcc", ".MCC")), _root(app))

    def r_finish():
        import postprocess_window as pw
        outs = [pw.finish_take(p)[0] for p in _sel(recs) if p.lower().endswith(AUDIO)]
        refresh_recs(); return "finished: " + ", ".join(os.path.basename(o) for o in outs)

    def r_move():
        dst = _gp().audio_exports_dir(getattr(app, "_current_project_path", None))
        for p in _sel(recs):
            shutil.move(p, os.path.join(dst, os.path.basename(p)))
        refresh_recs(); return "moved to exports"
    _buttons(l, (("▶ Play", guard(lambda: [_open_os(p) for p in _sel(recs)][:0] or "")), ("Finish take", guard(r_finish)),
                 ("Move to exports", guard(r_move)), ("Refresh", guard(refresh_recs))))
    refresh_recs()

    # 8 Versions ---------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🕘 Versions")
    vers = QListWidget(); l.addWidget(vers)

    def refresh_versions():
        cur = getattr(app, "_current_project_path", None)
        items = []
        if cur:
            r = os.path.dirname(cur)
            for p in (cur, cur + ".prev", os.path.join(r, "metadata", "before-autosave.MCC"), os.path.join(r, "metadata", "autosave.MCC")):
                if os.path.isfile(p):
                    items.append(p)
        _fill(vers, items, os.path.dirname(cur) if cur else "")

    def v_restore():
        for p in _sel(vers)[:1]:
            cur = getattr(app, "_current_project_path", None)
            if hasattr(app, "_push_undo"):
                app._push_undo("Restore version")
            if cur and os.path.isfile(cur):
                shutil.copy2(cur, cur + ".before-restore")
            with open(p, encoding="utf-8") as f:
                app._apply_project_snapshot(json.load(f))
            return "restored %s (your current file kept as .before-restore)" % os.path.basename(p)
    _buttons(l, (("Restore selected", guard(v_restore)), ("Refresh", guard(refresh_versions))))
    refresh_versions()

    # 9 Caches -------------------------------------------------------------------
    try:
        import site_directory
        tabs.addTab(site_directory.make_cache_page(app), "🧹 Caches")
    except Exception as exc:
        tabs.addTab(QLabel("caches unavailable: %s" % exc), "🧹 Caches")

    if tab in TABS:
        tabs.setCurrentIndex(TABS.index(tab))
    app._file_studio_window = w; w.show(); return w
