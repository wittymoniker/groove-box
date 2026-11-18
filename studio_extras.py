"""studio_extras.py — export verification, provenance inspector, mutation history, stem export, global search and
crash report bundle.

export verification   every finished export gets <file>.verify.json: size, SHA-256, duration, sample rate, channels
                      and bit depth (WAV read directly; other formats through ffprobe when installed), plus a
                      silent / clipped / non-finite check of the audio.
provenance inspector  Alt + right-click any control: read-only card with the Seed, Canonical, User, per-sequence and
                      final effective values that are known for it. Never writes anything.
mutation history      every undo step (labels from Autopilot, randomizers, edits) listed; jump to any one.
stem export           one WAV job per instrument (each a frozen project with only that instrument soloed).
global search         Ctrl+Shift+F: find any control by its text or tooltip and scroll to it, highlighted.
crash bundle          one ZIP with logs, the current project, the newest checkpoint and system info.
"""
from __future__ import annotations

import copy, hashlib, json, os, platform, shutil, subprocess, sys, time, wave, zipfile


# ---------------------------------------------------------------- export verification
def verify_file(path):
    info = {"path": path, "time": time.time()}
    try:
        info["bytes"] = os.path.getsize(path)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        info["sha256"] = h.hexdigest()
    except OSError as exc:
        info["error"] = str(exc); return info
    if path.lower().endswith(".wav"):
        try:
            import numpy as np
            with wave.open(path, "rb") as w:
                sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
                raw = w.readframes(min(n, sr * 600))
            info.update(sample_rate=sr, channels=ch, bit_depth=sw * 8, frames=n, duration_s=n / float(sr or 1))
            if sw == 2:
                a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            elif sw == 4:
                a = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
            elif sw == 3:
                b = np.frombuffer(raw[: len(raw) // 3 * 3], dtype=np.uint8).reshape(-1, 3)
                v = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)
                a = ((v ^ 0x800000) - 0x800000).astype(np.float32) / 8388608.0
            else:
                a = None
            if a is not None:
                import audio_diagnostics as ad
                ok, msg = ad.check_buffer(a, sr, "export")
                info["audio_ok"], info["audio_check"] = ok, msg
        except Exception as exc:
            info["probe_error"] = str(exc)
    elif __import__("sos_tools").which("ffprobe"):
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,sample_rate,channels,width,height,r_frame_rate",
                                "-of", "json", path], capture_output=True, text=True, timeout=60)
            info["ffprobe"] = json.loads(r.stdout or "{}")
        except Exception as exc:
            info["probe_error"] = str(exc)
    try:
        __import__("safe_io").atomic_write_json(path + ".verify.json", info, indent=1, encoding="utf-8")
    except OSError:
        pass
    return info


def on_export_finished(app, job):
    try:
        path = str((getattr(job, "result", {}) or {}).get("file_path") or getattr(job, "out_file", "") or "")
        if getattr(job, "state", "") != "done" or not os.path.isfile(path):
            return
        import threading

        def run():
            info = verify_file(path)
            if info.get("audio_ok") is False:
                job.message = (getattr(job, "message", "") or "") + " · ⚠ " + str(info.get("audio_check"))
                try: __import__("notify_center").notify(app, "Export %s: %s" % (os.path.basename(path), info.get("audio_check")), "export")
                except Exception: pass
        threading.Thread(target=run, name="export-verify", daemon=True).start()
    except Exception:
        pass


# ---------------------------------------------------------------- provenance inspector
def _attr_name(app, w):
    for k, v in app.__dict__.items():
        if v is w:
            return k
    return w.objectName() or type(w).__name__


def _widget_value(w):
    for m in ("value", "isChecked", "currentText", "text", "toPlainText"):
        f = getattr(w, m, None)
        if callable(f):
            try:
                return f()
            except Exception:
                pass
    return None


def provenance_text(app, w):
    name = _attr_name(app, w)
    lines = ["Control: %s" % name, "Shown value: %s" % (_widget_value(w),)]
    key = name.split("_", 1)[-1] if "_" in name else name
    try:
        inst = app._current_instrument_name()
        sid = app._current_sequence_index(inst)
        lines.append("Instrument: %s · SEQ #%s" % (app.instrument_label(inst) if hasattr(app, "instrument_label") else inst, sid))
        user = (getattr(app, "_canonical_macro_user_store", {}) or {}).get(inst, {}) or {}
        live = (getattr(app, "instrument_param_state", {}) or {}).get(inst, {}) or {}
        gen = (getattr(app, "instrument_param_generated", {}) or {}).get(inst, {}) or {}
        panel = {}
        try:
            panel = (app._sequence_panel_slot(inst, sid) or {}).get("synth", {}) or {}
        except Exception:
            pass
        cands = [k for k in set(live) | set(gen) | set(user) | set(panel) if k == key or k.endswith(key) or key.endswith(k)]
        for k in sorted(cands)[:6]:
            lines.append("· %s — user %s · canonical %s · per-seq %s · live %s" % (
                k, user.get(k, "—"), gen.get(k, "—"), panel.get(k, "—"), live.get(k, "—")))
        snap = (getattr(app, "_parameter_provenance_snapshot", {}) or {}).get(inst, {}) or {}
        for k in sorted(snap)[:4]:
            if k == key or key in k or k in key:
                lines.append("· final effective (render) %s: %s" % (k, str(snap[k])[:160]))
    except Exception:
        pass
    try:
        lines.append("Seed: %s" % (", ".join("%.4g" % v for v in (app.get_seed_values(0.0) or [])[:6]) or "—"))
        lines.append("Active canonicals: %s" % (", ".join(sorted(app._get_active_engine_set())) or "none"))
    except Exception:
        pass
    lines.append("Display only — nothing is changed.")
    return "\n".join(lines)


class _ProvFilter:
    pass


def install(app):
    if getattr(app, "_studio_extras", False):
        return
    app._studio_extras = True
    from PyQt6.QtCore import QObject, QEvent, Qt
    from PyQt6.QtGui import QShortcut, QKeySequence
    from PyQt6.QtWidgets import QApplication, QToolTip

    class F(QObject):
        def eventFilter(self, obj, ev):
            try:
                if ev.type() == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.RightButton \
                        and ev.modifiers() & Qt.KeyboardModifier.AltModifier and hasattr(obj, "mapToGlobal"):
                    QToolTip.showText(ev.globalPosition().toPoint(), provenance_text(app, obj), obj)
                    return True
            except Exception:
                pass
            return False
    app._prov_filter = F(app)
    QApplication.instance().installEventFilter(app._prov_filter)
    sc = QShortcut(QKeySequence("Ctrl+Shift+F"), app); sc.activated.connect(lambda: open_search(app))
    app._search_shortcut = sc


# ---------------------------------------------------------------- global search
def open_search(app):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QListWidget, QAbstractButton, QLabel, QGroupBox,
                                 QAbstractSlider, QAbstractSpinBox, QComboBox, QScrollArea)
    from PyQt6.QtCore import QTimer
    d = QDialog(app); d.setWindowTitle("🔎 Find a control"); d.resize(560, 460)
    lay = QVBoxLayout(d); q = QLineEdit(); q.setPlaceholderText("type part of a label or tooltip"); lst = QListWidget()
    lay.addWidget(q); lay.addWidget(lst)
    items = []
    for cls in (QAbstractButton, QLabel, QGroupBox, QAbstractSlider, QAbstractSpinBox, QComboBox):
        for w in app.findChildren(cls):
            t = (w.title() if isinstance(w, QGroupBox) else (w.text() if hasattr(w, "text") and callable(w.text) else "")) or ""
            tip = w.toolTip() or ""
            if (t or tip).strip():
                items.append((("%s %s" % (t, tip)).lower(), (t or tip).replace("\n", " ")[:90], w))

    def fill():
        s = q.text().lower().strip(); lst.clear(); d._hits = []
        if len(s) < 2: return
        for low, show, w in items:
            if s in low:
                lst.addItem(show); d._hits.append(w)
                if len(d._hits) >= 200: break

    def go(i):
        w = d._hits[i]
        try:
            p = w.parentWidget()
            while p is not None:
                if isinstance(p, QScrollArea):
                    p.ensureWidgetVisible(w, 60, 60); break
                p = p.parentWidget()
            old = w.styleSheet(); w.setStyleSheet(old + ";border:3px solid #ffd166;")
            QTimer.singleShot(1800, lambda: w.setStyleSheet(old)); w.setFocus()
        except RuntimeError:
            pass
    q.textChanged.connect(fill); lst.currentRowChanged.connect(lambda i: i >= 0 and go(i))
    d.show(); app._search_dialog = d


# ---------------------------------------------------------------- mutation history
def open_history(app):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QLabel
    d = QDialog(app); d.setWindowTitle("🕘 Project history"); d.resize(520, 520)
    lay = QVBoxLayout(d); lay.addWidget(QLabel("Every undo step, newest first. Jump restores that step (the current state becomes a redo)."))
    lst = QListWidget(); lay.addWidget(lst)
    stack = list(getattr(app, "_undo_stack", []) or [])
    for i, (label, _snap) in enumerate(reversed(stack)):
        lst.addItem("%d · %s" % (len(stack) - i, label))
    b = QPushButton("Jump to selected"); lay.addWidget(b)

    def jump():
        i = lst.currentRow()
        if i < 0: return
        for _ in range(i + 1):
            try: app._do_undo()
            except Exception: break
        d.close()
    b.clicked.connect(jump); d.show(); app._history_dialog = d


# ---------------------------------------------------------------- stem export
def export_stems(app, folder=None):
    names = list(getattr(app, "instrument_names_48", []) or [])
    used = set()
    for r in getattr(app, "master_playlist_data", []) or []:
        if isinstance(r, dict):
            for k in ("operator", "operators_csv", "operators"):
                for part in str(r.get(k) or "").replace(";", ",").split(","):
                    part = part.split("@", 1)[0].strip()
                    if part: used.add(part)
    names = [n for n in names if n in used] or names
    folder = folder or os.path.join(str(app._audio_exports_dir()), time.strftime("stems-%Y%m%d-%H%M%S"))
    os.makedirs(folder, exist_ok=True)
    base = app._project_snapshot()
    sch = app._export_scheduler()
    n = 0
    for name in names:
        doc = copy.deepcopy(base)
        r32 = doc.setdefault("r32", {})
        mix = r32.get("inst_mix") or copy.deepcopy(getattr(app, "r32_inst_mix", {}) or {}) or {"mode": "user", "depth": 0.5, "strips": {}}
        strips = mix.setdefault("strips", {})
        for s in strips.values(): s["solo"] = False
        strips.setdefault(name, {"db": 0.0, "mute": False, "solo": False})["solo"] = True
        r32["inst_mix"] = mix
        out = os.path.join(folder, "".join(c if c.isalnum() or c in " -_" else "_" for c in app.instrument_label(name))[:60] + ".wav")
        sch.submit_job("audio_file", out, {"audio_format": "wav"}, label="stem · %s" % name, project_doc=doc); n += 1
    return n, folder


# ---------------------------------------------------------------- crash bundle
def crash_bundle(app):
    d = os.path.join(os.path.expanduser("~"), "groovebox-reports"); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, time.strftime("groovebox-report-%Y%m%d-%H%M%S.zip"))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.json", json.dumps({"python": sys.version, "platform": platform.platform(), "cpus": os.cpu_count(),
                                              "argv": sys.argv, "time": time.ctime()}, indent=1))
        try: z.writestr("project.MCC", json.dumps(app._project_snapshot(), default=str))
        except Exception as exc: z.writestr("project-error.txt", str(exc))
        try:
            import project_transactions as pt
            c = pt.checkpoints()
            if c: z.write(c[0], "newest-checkpoint.MCC")
        except Exception: pass
        for root in (os.path.join(os.path.expanduser("~"), ".cache", "groovebox"), os.path.join(os.path.expanduser("~"), ".local", "share", "groovebox", "logs"),
                     os.path.join(os.path.expanduser("~"), ".config", "groovebox")):
            if os.path.isdir(root):
                for dp, _dn, fn in os.walk(root):
                    for f in fn:
                        if f.endswith((".log", ".txt", ".json")) and os.path.getsize(os.path.join(dp, f)) < 8 << 20:
                            z.write(os.path.join(dp, f), os.path.relpath(os.path.join(dp, f), os.path.dirname(root)))
    return out


def open_window(app):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel
    d = QDialog(app); d.setWindowTitle("🧰 Studio extras"); lay = QVBoxLayout(d)
    out = QLabel("Alt + right-click any control shows where its value comes from (display only).\nCtrl+Shift+F finds any control.")
    out.setWordWrap(True); lay.addWidget(out)
    for text, fn in (("🔎 Find a control", lambda: open_search(app)), ("🕘 Project history", lambda: open_history(app)),
                     ("🎚 Export stems (one WAV per instrument)", lambda: out.setText("queued %d stems → %s" % export_stems(app))),
                     ("🧾 Crash report bundle", lambda: out.setText("saved " + crash_bundle(app)))):
        b = QPushButton(text); b.clicked.connect(fn); lay.addWidget(b)
    d.show(); app._extras_dialog = d
