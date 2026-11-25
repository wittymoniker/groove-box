"""Performance → 🧪 Dev Overlay page. DEV_OVERLAY_UI_20261112

Browse the installed source (read-only), write your own overlay files (.py .cpp .sC .jl .rs) that override or
append to the core, compile them, enable the overlay for THIS session, and use the scratchpad to run any single
script in an isolated process.  The watchdog (module-level, survives the page) rolls back to the core.
"""
from __future__ import annotations

import os
import re

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
                             QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                             QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget)

import dev_overlay as d

_KW = {
    ".py": r"\b(def|class|return|import|from|as|if|elif|else|for|while|try|except|finally|with|lambda|yield|in|not|and|or|is|None|True|False|pass|break|continue|global|raise)\b",
    ".cpp": r"\b(int|double|float|void|char|bool|auto|const|static|struct|class|return|if|else|for|while|include|define|extern|namespace|std|size_t|template)\b",
    ".rs": r"\b(fn|let|mut|pub|use|mod|struct|impl|enum|match|if|else|for|while|loop|return|unsafe|extern|const|static|as|in)\b",
    ".jl": r"\b(function|end|module|using|import|return|if|elseif|else|for|while|let|struct|mutable|begin|const|in)\b",
    ".sC": r"\b(program|print|setting|permit|numerals|module|use|fn|let|return|if|else|for)\b",
}
_COMMENT = {".py": r"#[^\n]*", ".jl": r"#[^\n]*", ".sC": r"#[^\n]*", ".cpp": r"//[^\n]*", ".rs": r"//[^\n]*"}


class _Highlighter(QSyntaxHighlighter):
    def __init__(self, doc, ext):
        super().__init__(doc)
        self.rules = []
        kw = QTextCharFormat(); kw.setForeground(QColor("#7fb4ff")); kw.setFontWeight(QFont.Weight.Bold)
        st = QTextCharFormat(); st.setForeground(QColor("#c3e88d"))
        cm = QTextCharFormat(); cm.setForeground(QColor("#7a8794")); cm.setFontItalic(True)
        nm = QTextCharFormat(); nm.setForeground(QColor("#f78c6c"))
        if ext in _KW:
            self.rules.append((re.compile(_KW[ext]), kw))
        self.rules += [(re.compile(r"\b\d+(\.\d+)?\b"), nm), (re.compile(r"\"[^\"\n]*\"|'[^'\n]*'"), st)]
        if ext in _COMMENT:
            self.rules.append((re.compile(_COMMENT[ext]), cm))

    def highlightBlock(self, text):
        for rx, fmt in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class _Bridge(QObject):
    line = pyqtSignal(str)
    done = pyqtSignal(object)
    event = pyqtSignal(str, str)


# ---------------------------------------------------------------- watchdog (one per process, outlives the page)
_DOG = {"timer": None, "dog": None}


def _ensure_watchdog():
    if _DOG["timer"] is not None:
        return _DOG["dog"]
    app = QApplication.instance()
    dog = d.Watchdog()
    t = QTimer(app); t.setInterval(int(d.Watchdog.INTERVAL * 1000))
    t.timeout.connect(dog.tick); t.start()
    _DOG.update(timer=t, dog=dog)
    return dog


class DevOverlayPage(QWidget):
    def __init__(self, host=None, parent=None):
        super().__init__(parent)
        self.host = host
        self.cur = None            # {"path", "mode": core|overlay|scratch, "rel", "ext"}
        self.run = None
        self.br = _Bridge(self)
        self.br.line.connect(self._out)
        self.br.done.connect(lambda cb: cb())
        self.br.event.connect(self._on_event)
        d.add_listener(lambda ev, det: self.br.event.emit(ev, det))
        self.dog = _ensure_watchdog()
        self._build()
        self._refresh_all()
        self.health = QTimer(self); self.health.setInterval(1000); self.health.timeout.connect(self._health); self.health.start()

    # ---------------------------------------------------------------- layout
    def _build(self):
        v = QVBoxLayout(self); v.setContentsMargins(6, 6, 6, 6)
        self.lbl_state = QLabel(); self.lbl_state.setWordWrap(True); self.lbl_state.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(self.lbl_state)
        top = QGridLayout(); top.setHorizontalSpacing(6)
        self.b_compile = QPushButton("🔨 Compile overlay"); self.b_compile.clicked.connect(self._compile)
        self.b_enable = QPushButton("▶ Enable for this session"); self.b_enable.clicked.connect(self._enable)
        self.b_disable = QPushButton("⏹ Back to core"); self.b_disable.clicked.connect(lambda: self._show_report(d.disable("manual")))
        b_folder = QPushButton("📂 Overlay folder"); b_folder.clicked.connect(self._open_folder)
        b_share = QPushButton("📤 Share…"); b_share.clicked.connect(self._share)
        b_share.setToolTip("Pack your overlay (src + append, with SHA-256 manifest) into a .mgoverlay file to send to anyone")
        b_imp = QPushButton("📥 Import…"); b_imp.clicked.connect(self._import_share)
        b_imp.setToolTip("Install a .mgoverlay package (validated; your current overlay is backed up first; nothing runs "
                         "until you Compile and Enable it)")
        for i, b in enumerate((self.b_compile, self.b_enable, self.b_disable, b_folder, b_share, b_imp)):
            top.addWidget(b, 0, i); top.setColumnStretch(i, 1)
        v.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal); v.addWidget(split, 1)
        # left: browse
        self.tabs = QTabWidget(); self.tabs.setMinimumWidth(270); self.tabs.setUsesScrollButtons(False)
        core = QWidget(); cl = QVBoxLayout(core)
        self.core_filter = QLineEdit(); self.core_filter.setPlaceholderText("Filter installed source (e.g. seed, .cpp, scode/)")
        self.core_filter.textChanged.connect(self._fill_core); cl.addWidget(self.core_filter)
        self.core_list = QListWidget(); self.core_list.itemActivated.connect(self._open_core_item)
        self.core_list.itemClicked.connect(self._open_core_item); cl.addWidget(self.core_list, 1)
        self.tabs.addTab(core, "📖 Source")
        mine = QWidget(); ml = QVBoxLayout(mine)
        self.ov_list = QListWidget(); self.ov_list.itemClicked.connect(self._open_overlay_item); ml.addWidget(self.ov_list, 1)
        g = QGridLayout()
        for i, (t, fn) in enumerate((("New file…", self._new_file), ("Delete", self._delete_overlay))):
            b = QPushButton(t); b.clicked.connect(fn); g.addWidget(b, 0, i)
        ml.addLayout(g)
        self.tabs.addTab(mine, "🧩 Overlay")
        scr = QWidget(); sl = QVBoxLayout(scr)
        self.scr_list = QListWidget(); self.scr_list.itemClicked.connect(self._open_scratch_item); sl.addWidget(self.scr_list, 1)
        g2 = QGridLayout()
        self.scr_lang = QComboBox(); [self.scr_lang.addItem(e) for e in d.RUN_LANGS]
        b_new = QPushButton("New scratch"); b_new.clicked.connect(self._new_scratch)
        b_del = QPushButton("Delete"); b_del.clicked.connect(self._delete_scratch)
        g2.addWidget(QLabel("Language"), 0, 0); g2.addWidget(self.scr_lang, 0, 1)
        g2.addWidget(b_new, 1, 0); g2.addWidget(b_del, 1, 1)
        sl.addLayout(g2)
        try:                                     # TOOLCHAIN_REPORT_R6: say up front which languages can run
            tc = d.toolchains()
            self.lbl_tools = QLabel("Can run: " + d.toolchain_summary()); self.lbl_tools.setWordWrap(True)
            self.lbl_tools.setToolTip("\n".join(f"{k}: {v['note']}" + (f"  ({v['tool']})" if v.get("tool") else "") for k, v in tc.items()))
            sl.addWidget(self.lbl_tools)
            for i in range(self.scr_lang.count()):
                info = tc.get(self.scr_lang.itemText(i))
                if info is not None and not info["ok"]:
                    self.scr_lang.setItemText(i, self.scr_lang.itemText(i))
                    self.scr_lang.setItemData(i, info["note"], Qt.ItemDataRole.ToolTipRole)
        except Exception:
            pass
        self.tabs.addTab(scr, "🧪 Scratch")
        split.addWidget(self.tabs)

        # right: editor + output
        right = QSplitter(Qt.Orientation.Vertical)
        ed = QWidget(); el = QVBoxLayout(ed); el.setContentsMargins(0, 0, 0, 0)
        self.lbl_file = QLabel("Pick a file on the left, or start a scratch script."); self.lbl_file.setWordWrap(True)
        el.addWidget(self.lbl_file)
        self.editor = QPlainTextEdit(); self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        f = QFont("Consolas"); f.setStyleHint(QFont.StyleHint.Monospace); f.setPointSize(10); self.editor.setFont(f)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))
        el.addWidget(self.editor, 1)
        row = QGridLayout(); row.setHorizontalSpacing(6)
        self.find = QLineEdit(); self.find.setPlaceholderText("Find (Enter)"); self.find.returnPressed.connect(self._find)
        self.goto = QSpinBox(); self.goto.setRange(1, 10_000_000); self.goto.setPrefix("line "); self.goto.editingFinished.connect(self._goto)
        self.b_save = QPushButton("💾 Save"); self.b_save.clicked.connect(self._save)
        self.b_run = QPushButton("▶ Run script"); self.b_run.clicked.connect(self._run)
        self.b_stop = QPushButton("■ Stop"); self.b_stop.clicked.connect(self._stop); self.b_stop.setEnabled(False)
        self.b_over = QPushButton("Override in overlay"); self.b_over.clicked.connect(lambda: self._derive("src"))
        self.b_app = QPushButton("Append in overlay"); self.b_app.clicked.connect(lambda: self._derive("append"))
        self.chk_hooks = QCheckBox("scripts see my overlay"); self.chk_hooks.setChecked(True)
        for i, w in enumerate((self.find, self.goto, self.b_save, self.b_run, self.b_stop)):
            row.addWidget(w, 0, i)
        row.addWidget(self.b_over, 1, 0); row.addWidget(self.b_app, 1, 1); row.addWidget(self.chk_hooks, 1, 2, 1, 3)
        row.setColumnStretch(0, 3)
        el.addLayout(row)
        right.addWidget(ed)
        bottom = QWidget(); bl = QVBoxLayout(bottom); bl.setContentsMargins(0, 0, 0, 0)
        self.out = QPlainTextEdit(); self.out.setReadOnly(True); self.out.setFont(f); self.out.setMaximumBlockCount(20000)
        bl.addWidget(self.out, 1)
        self.lbl_health = QLabel(""); self.lbl_health.setWordWrap(True); bl.addWidget(self.lbl_health)
        bl.addWidget(self._settings_box())
        right.addWidget(bottom)
        right.setStretchFactor(0, 3); right.setStretchFactor(1, 2)
        split.addWidget(right); split.setStretchFactor(0, 1); split.setStretchFactor(1, 4)
        QShortcut(QKeySequence.StandardKey.Save, self.editor, activated=self._save)
        QShortcut(QKeySequence("Ctrl+Return"), self.editor, activated=self._run)
        self._set_mode(None)

    def _settings_box(self):
        box = QGroupBox("Fall back to the installed core when…"); g = QFormLayout(box)
        try:
            import compat_settings as cs
            s = cs.load()
        except Exception:
            cs, s = None, {}
        self.s_policy = QComboBox(); self.s_policy.addItem("automatically (heat · RAM · freeze · errors)", "auto")
        self.s_policy.addItem("only when I press ⏹ Back to core", "manual")
        self.s_policy.setCurrentIndex(0 if s.get("dev_overlay_rollback", "auto") == "auto" else 1)
        self.s_temp = QSpinBox(); self.s_temp.setRange(50, 120); self.s_temp.setSuffix(" °C"); self.s_temp.setValue(int(s.get("dev_overlay_max_temp_c", 90)))
        self.s_ram = QSpinBox(); self.s_ram.setRange(64, 65536); self.s_ram.setSuffix(" MB free"); self.s_ram.setValue(int(s.get("dev_overlay_min_free_mb", 512)))
        self.s_stall = QDoubleSpinBox(); self.s_stall.setRange(0.5, 60); self.s_stall.setSuffix(" s freeze"); self.s_stall.setValue(float(s.get("dev_overlay_stall_s", 3.0)))
        self.s_err = QSpinBox(); self.s_err.setRange(1, 1000); self.s_err.setSuffix(" errors"); self.s_err.setValue(int(s.get("dev_overlay_max_errors", 3)))
        self.s_to = QSpinBox(); self.s_to.setRange(5, 86400); self.s_to.setSuffix(" s"); self.s_to.setValue(int(s.get("dev_overlay_script_timeout_s", 600)))
        g.addRow("Rollback", self.s_policy)
        h = QHBoxLayout()
        for w in (self.s_temp, self.s_ram, self.s_stall, self.s_err):
            h.addWidget(w)
        g.addRow("Thresholds", h); g.addRow("Script time limit", self.s_to)

        def save(*_):
            if cs is None:
                return
            cs.update(dev_overlay_rollback=self.s_policy.currentData(), dev_overlay_max_temp_c=self.s_temp.value(),
                      dev_overlay_min_free_mb=self.s_ram.value(), dev_overlay_stall_s=self.s_stall.value(),
                      dev_overlay_max_errors=self.s_err.value(), dev_overlay_script_timeout_s=self.s_to.value()) \
                if hasattr(cs, "update") else None
        self.s_policy.currentIndexChanged.connect(save)
        for w in (self.s_temp, self.s_ram, self.s_err, self.s_to, self.s_stall):
            w.editingFinished.connect(save)
        return box

    # ---------------------------------------------------------------- lists
    def _refresh_all(self):
        self._core_cache = d.core_files()
        self._fill_core(); self._fill_overlay(); self._fill_scratch(); self._state()

    def _fill_core(self, *_):
        q = self.core_filter.text().strip().lower()
        self.core_list.setUpdatesEnabled(False); self.core_list.clear()
        for rel in self._core_cache:
            if not q or q in rel.lower():
                self.core_list.addItem(rel)
        self.core_list.setUpdatesEnabled(True)

    def _fill_overlay(self):
        self.ov_list.clear()
        for f in d.files():
            it = QListWidgetItem(f"{'＋' if f['kind'] == 'append' else ('⟳' if f['core'] else '★')} {f['kind']}/{f['rel']}")
            it.setData(Qt.ItemDataRole.UserRole, f); it.setToolTip(
                {"append": "runs / compiles after the core file", "src": "overrides the core file" if f["core"] else "new file"}[f["kind"]])
            self.ov_list.addItem(it)

    def _fill_scratch(self):
        self.scr_list.clear()
        base = d.overlay_root() / "scratch"
        for p in sorted(base.iterdir(), key=lambda p: -p.stat().st_mtime):
            if p.suffix in d.RUN_LANGS:
                it = QListWidgetItem(p.name); it.setData(Qt.ItemDataRole.UserRole, str(p)); self.scr_list.addItem(it)

    # ---------------------------------------------------------------- editor
    def _load(self, path, mode, rel=""):
        if not self._maybe_save():
            return
        ext = os.path.splitext(path)[1]
        text = d.read_core(rel) if mode == "core" else open(path, encoding="utf-8", errors="replace").read()
        self._hl = None
        self.editor.setPlainText(text)
        if len(text) < 400_000:
            self._hl = _Highlighter(self.editor.document(), ext)
        self.editor.document().setModified(False)
        self.cur = {"path": path, "mode": mode, "rel": rel, "ext": ext}
        self._set_mode(mode)

    def _set_mode(self, mode):
        ro = mode in (None, "core")
        self.editor.setReadOnly(ro)
        self.b_save.setEnabled(not ro)
        self.b_run.setEnabled(mode in ("scratch", "overlay", "core") and bool(self.cur) and self.cur["ext"] in d.RUN_LANGS)
        self.b_over.setVisible(mode == "core"); self.b_app.setVisible(mode == "core")
        if mode == "core":
            self.lbl_file.setText(f"📖 <b>{self.cur['rel']}</b> — installed system file · read-only (it is never edited, "
                                  "moved or copied). Make an override or append to change it in your overlay.")
        elif mode == "overlay":
            self.lbl_file.setText(f"🧩 <b>{os.path.relpath(self.cur['path'], d.overlay_root())}</b> — your overlay file")
        elif mode == "scratch":
            self.lbl_file.setText(f"🧪 <b>{os.path.basename(self.cur['path'])}</b> — scratchpad · Ctrl+Enter runs it")
        self.lbl_file.setTextFormat(Qt.TextFormat.RichText)

    def _maybe_save(self) -> bool:
        if self.cur and self.cur["mode"] != "core" and self.editor.document().isModified():
            r = QMessageBox.question(self, "Unsaved changes", "Save changes to %s?" % os.path.basename(self.cur["path"]),
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                     QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel:
                return False
            if r == QMessageBox.StandardButton.Save:
                self._save()
        return True

    def _save(self):
        if not self.cur or self.cur["mode"] == "core":
            return
        try:
            d.save_file(self.cur["path"], self.editor.toPlainText())
            self.editor.document().setModified(False)
            self._out(f"saved {os.path.basename(self.cur['path'])}"); self._state()
        except Exception as exc:
            QMessageBox.warning(self, "Save", str(exc))

    def _open_core_item(self, it):
        rel = it.text(); p = d.core_path(rel)
        if p:
            self._load(str(p), "core", rel)

    def _open_overlay_item(self, it):
        f = it.data(Qt.ItemDataRole.UserRole); self._load(f["path"], "overlay", f["rel"])

    def _open_scratch_item(self, it):
        self._load(it.data(Qt.ItemDataRole.UserRole), "scratch")

    def _derive(self, kind):
        if not self.cur or self.cur["mode"] != "core":
            return
        try:
            p = d.new_file(kind, self.cur["rel"])
        except Exception as exc:
            QMessageBox.warning(self, "Overlay", str(exc)); return
        self._fill_overlay(); self.tabs.setCurrentIndex(1)
        self._load(str(p), "overlay", self.cur["rel"])

    def _new_file(self):
        rel, ok = QInputDialog.getText(self, "New overlay file", "Path inside the Groovebox tree (e.g. my_engine.py, "
                                       "cpp/my_kernel.cpp, sCode/apps/mine.sC, julia/Mine.jl, rust/mine.rs):")
        if not ok or not rel.strip():
            return
        kind = "src"
        try:
            if d.core_path(rel.strip()) is not None:
                ans = QMessageBox.question(self, "Installed file exists",
                                           "This path is an installed file. Yes = override it, No = append to it.",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                                           QMessageBox.StandardButton.Cancel)
                if ans == QMessageBox.StandardButton.Cancel:
                    return
                kind = "src" if ans == QMessageBox.StandardButton.Yes else "append"
            p = d.new_file(kind, rel.strip())
        except Exception as exc:
            QMessageBox.warning(self, "Overlay", str(exc)); return
        self._fill_overlay(); self._load(str(p), "overlay", rel.strip()); self._state()

    def _delete_overlay(self):
        it = self.ov_list.currentItem()
        if it is None:
            return
        f = it.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete your overlay file {f['kind']}/{f['rel']}?") == QMessageBox.StandardButton.Yes:
            d.delete_file(f["path"]); self._fill_overlay(); self._state()
            if self.cur and self.cur["path"] == f["path"]:
                self.cur = None; self.editor.clear(); self._set_mode(None)

    def _new_scratch(self):
        p = d.scratch_path(self.scr_lang.currentText())
        starter = {".py": "# Scratchpad — import any Groovebox module (read from the core in place) and solve anything.\n"
                          "import numpy as np\nimport spectral_canonical as sc\n\nx, sr = sc.synthesize_generative('scratch', seconds=1.0)\n"
                          "print(x.shape, sr, float(np.abs(x).max()))\n",
                   ".cpp": "#include <cstdio>\nint main() {\n    std::printf(\"hello from C++\\n\");\n}\n",
                   ".rs": "fn main() {\n    println!(\"hello from Rust\");\n}\n",
                   ".jl": "println(\"hello from Julia\")\n",
                   ".sC": "program Scratch\nprint \"hello from sCode\"\n"}[p.suffix]
        d.save_file(p, starter); self._fill_scratch(); self._load(str(p), "scratch")

    def _delete_scratch(self):
        it = self.scr_list.currentItem()
        if it is not None:
            d.delete_file(it.data(Qt.ItemDataRole.UserRole)); self._fill_scratch()

    def _find(self):
        t = self.find.text()
        if t and not self.editor.find(t):
            self.editor.moveCursor(QTextCursor.MoveOperation.Start); self.editor.find(t)

    def _goto(self):
        b = self.editor.document().findBlockByNumber(self.goto.value() - 1)
        if b.isValid():
            c = self.editor.textCursor(); c.setPosition(b.position()); self.editor.setTextCursor(c); self.editor.centerCursor()

    # ---------------------------------------------------------------- run
    def _run(self):
        if not self.cur or (self.run is not None and self.run.running()):
            return
        if self.cur["mode"] != "core":
            self._save()
        path = self.cur["path"]
        self.out.appendPlainText("")
        self.b_run.setEnabled(False); self.b_stop.setEnabled(True)
        self.run = d.ScriptRun(path, self.br.line.emit,
                               lambda c, t: self.br.done.emit(lambda: (self.b_run.setEnabled(True), self.b_stop.setEnabled(False))),
                               use_overlay=self.chk_hooks.isChecked()).start()

    def _stop(self):
        if self.run is not None:
            self.run.stop()

    def _out(self, text):
        self.out.appendPlainText(text)

    # ---------------------------------------------------------------- compile / enable
    def _compile(self):
        self.b_compile.setEnabled(False); self.out.appendPlainText("— compiling overlay —")
        import threading

        def work():
            try:
                r = d.compile_all(self.br.line.emit)
            except Exception as exc:
                r = {"ok": False, "report": [f"✗ {type(exc).__name__}: {exc}"]}
            self.br.done.emit(lambda: (self.b_compile.setEnabled(True), self._out("compile " + ("OK" if r["ok"] else "FAILED")),
                                       self._state()))
        threading.Thread(target=work, name="overlay-compile", daemon=True).start()

    def _enable(self):
        if not d.compile_is_current():
            QMessageBox.information(self, "Dev Overlay", "Compile the overlay first (it changed since the last good compile).")
            return
        r = d.enable(confirm_session=True)
        self._show_report(r)

    def _show_report(self, r):
        for line in r.get("report", []):
            self._out(line)
        self._state()

    def _on_event(self, ev, detail):
        if ev == "enabled":           # the enable report is already printed line by line
            self._state(); return
        self._out(f"overlay {ev}: {detail}")
        self._state()
        if ev == "disabled" and detail.startswith("auto rollback"):
            QMessageBox.warning(self, "Dev Overlay — back on the core", detail)

    def _state(self):
        st = d.status()
        if st["active"]:
            html = "<b style='color:#7ee787'>● OVERLAY ACTIVE (this session only)</b> — your code is running on top of the installed core."
        else:
            html = "<b style='color:#9ab'>○ Installed core</b> — every launch starts here; enable your overlay below for this session."
        html += f" · {st['files']} overlay file(s) · compile: " + (
            "<span style='color:#7ee787'>current</span>" if st["compile_current"] else "<span style='color:#f0b072'>needed</span>")
        lr = st.get("last_rollback")
        if lr:
            html += f"<br><small>last return to core: {lr.get('reason', '')}</small>"
        self.lbl_state.setText(html)
        self.b_enable.setEnabled(not st["active"]); self.b_disable.setEnabled(st["active"])

    def _health(self):
        s = self.dog.sample or {}
        t, m = s.get("temp_c"), s.get("free_mb")
        txt = "Health · temp " + (f"{t:.0f} °C" if t is not None else "n/a") + " · free RAM " + (
            f"{m:,.0f} MB" if m is not None else "n/a") + f" · overlay errors {s.get('errors', 0)}"
        if s.get("trouble"):
            txt += " · ⚠ " + s["trouble"]
        self.lbl_health.setText(txt)

    def _share(self):
        from PyQt6.QtWidgets import QFileDialog, QInputDialog
        name, ok = QInputDialog.getText(self, "Share overlay", "Name of this overlay:", text="My Groovebox overlay")
        if not ok:
            return
        path, _f = QFileDialog.getSaveFileName(self, "Save overlay package",
                                               os.path.expanduser("~/%s.mgoverlay" % name.strip().replace(" ", "_")),
                                               "Groovebox overlay (*.mgoverlay)")
        if path:
            try:
                r = d.export_share(path, name=name)
                self._show_report("📤 %d files → %s" % (r["files"], r["path"]))
            except Exception as exc:
                self._show_report("⚠ share failed: %s" % exc)

    def _import_share(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        path, _f = QFileDialog.getOpenFileName(self, "Import overlay package", os.path.expanduser("~"),
                                               "Groovebox overlay (*.mgoverlay)")
        if not path:
            return
        try:
            man = d.inspect_share(path)
        except Exception as exc:
            self._show_report("⚠ refused: %s" % exc)
            return
        files = "\n".join(e["path"] for e in man.get("files", [])[:30])
        q = ("Install \"%s\" by %s (%d files)?\n\n%s\n\nYour overlay is backed up first. Nothing runs until you "
             "Compile and Enable it." % (man.get("name"), man.get("author") or "unknown", len(man.get("files", [])), files))
        if QMessageBox.question(self, "Import overlay", q) != QMessageBox.StandardButton.Yes:
            return
        try:
            r = d.import_share(path)
            self._show_report("📥 imported %s (%d files) · backup %s" % (r["name"], r["files"], r["backup"]))
        except Exception as exc:
            self._show_report("⚠ import failed: %s" % exc)

    def _open_folder(self):
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(d.overlay_root())))
        except Exception:
            pass
        self._out(f"overlay folder: {d.overlay_root()}")


def make_page(host=None):
    return DevOverlayPage(host)
