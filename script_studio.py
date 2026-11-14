"""SCRIPT_STUDIO_R7 — ✍ Script Studio: the OS text editor for seed-language compositions.

A composition in Groovebox is a list of numbers and logical statements (the seed program); everything
else — sound, sequences, video, games — is derived from it.  Script Studio is where you write those
programs outside the one-line seed field:

* Editor  — the same seed syntax highlighter and auto-indent as the main Seed Script field, drawn
            translucent over the window's live ParametricMathBackground (like every other script editor).
* Library — scripts are plain text files in <Groovebox data>/scripts/*.seed (New / Open / Save / Save as).
* Launcher environment (run bar) —
    ▶ Evaluate at t   runs the program once at beat t with the exact workspace namespace the engine uses
    ∿ Sweep           plots the first output over t = 0…N beats (chunked, never blocks the UI)
    ⤴ Use as seed     replaces the project's seed program (asks first);  ＋ Append adds it as new lines
* Workspace variables reference — every name a script can read (functions, constants, tensors), its kind
  and its value at the current t, plus read-only live project values and your own variables from the last
  run.  Filter by typing; double-click inserts the name at the cursor.
* Syntax — the seed language's free-syntax summary (implicit multiplication, ^, unicode maths, if/elif …).

Seed programs run in the budgeted seed sandbox (seed_lang): no imports, no files, no Python builtins, and
every loop is bounded, so evaluating here is as safe as typing in the seed field.  Python dev-overlay code
is a different thing and still runs only after Performance → 🧪 Dev Overlay → Enable for this session.

Launchers: window bar ⚡ Actions → Make → ✍ Script Studio, System Settings → Script Studio, or standalone:
    python3 script_studio.py [file.seed]
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QTextCursor
from PyQt6.QtWidgets import (QApplication, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                             QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
                             QTabWidget, QTextBrowser, QToolButton, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

import seed_lang

EXT = ".seed"
SWEEP_CHUNK = 16
_WIN = {"w": None}

TEMPLATES = (
    ("Pulse melody", "# One computation per beat t. The last bare expressions are the outputs.\n"
                     "base = 220\n"
                     "step = floor(t) % 8\n"
                     "return base * 2^(step/12), 0.5 + 0.5sin(t)\n"),
    ("Logic rhythm", "# Logical statements choose the value; every branch is a number.\n"
                     "beat = floor(t) % 4\n"
                     "if beat == 0:\n"
                     "    return 440\n"
                     "elif beat == 2:\n"
                     "    return 660\n"
                     "else:\n"
                     "    return 330 + 20sin(2t)\n"),
    ("Coordinate path", "# Coordinate DSL: x(t), y(t) become the outputs (also drives the visuals).\n"
                        "x(t) = cos(t) + 0.3cos(5t)\n"
                        "y(t) = sin(t) - 0.3sin(5t)\n"),
    ("Number list", "# A plain list of numbers is a complete composition.\n"
                    "261.63, 329.63, 392.0, 523.25\n"),
    ("Golden spiral", "# φ and π are built in; ^ is power.\n"
                      "r = φ^(t/4)\n"
                      "theta = τ * t / 8\n"
                      "return 110 * (1 + (r % 4)), theta\n"),
)

STYLE = """
QWidget#ScriptStudio { background: transparent; color: #d8e6ff; }
QPlainTextEdit#ScriptStudioEditor { background: rgba(17,26,44,185); color: #e8f1ff; border: 1px solid #2c4a74;
    border-radius: 6px; selection-background-color: #2f5d8f; }
QTreeWidget, QTextBrowser { background: rgba(14,22,38,170); color: #cfe0ff; border: 1px solid #263f63; border-radius: 6px; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: rgba(22,39,66,170); color: #b8f7e6; padding: 4px 10px; border-radius: 4px; margin: 1px; }
QTabBar::tab:selected { background: rgba(40,72,118,210); }
QPushButton, QToolButton { background: rgba(28,46,76,200); color: #e1ecff; border: 1px solid #3c6597; border-radius: 4px;
    padding: 3px 9px; font-weight: 700; }
QPushButton:hover, QToolButton:hover { background: rgba(48,82,130,220); }
QLabel { background: transparent; color: #b8cdf0; }
QLineEdit, QSpinBox, QDoubleSpinBox { background: rgba(14,22,38,200); color: #e8f1ff; border: 1px solid #2c4a74; border-radius: 4px; }
"""


# ------------------------------------------------------------------------------------------- environment
def _host_module(app):
    """The module that defines the engine's seed namespace (groovebox.py, or __main__ when run as a script)."""
    if app is not None:
        mod = sys.modules.get(type(app).__module__)
        if mod is not None and hasattr(mod, "_seed_script_env"):
            return mod
    for name in ("groovebox", "__main__"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "_seed_script_env"):
            return mod
    try:
        import groovebox as mod          # standalone: same namespace as the engine (heavier import, once)
        return mod
    except Exception:
        return None


def env_at(app, t):
    """The exact namespace the engine gives a seed program at beat t (canonical context when the app is live)."""
    mod = _host_module(app)
    if mod is None:
        return {"t": float(t), "pi": math.pi, "sin": math.sin, "cos": math.cos, "sqrt": math.sqrt,
                "floor": math.floor, "abs": abs, "min": min, "max": max}
    ctx = None
    if app is not None:
        try:
            ctx = getattr(app, "_canonical_render_input_context", None) or app._canonical_input_context()
        except Exception:
            ctx = None
    try:
        return mod._seed_script_env(t_scalar=float(t), canonical_context=ctx)
    except TypeError:
        return mod._seed_script_env(float(t))


def _kind(v):
    if callable(v):
        return "function"
    if isinstance(v, bool):
        return "logic"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, (list, tuple)):
        return "list"
    try:
        import numpy as np
        if isinstance(v, np.ndarray):
            return "tensor %s" % "×".join(str(int(s)) for s in v.shape)
        if isinstance(v, np.generic):
            return "number"
    except Exception:
        pass
    return type(v).__name__


def _preview(v):
    if callable(v):
        doc = (getattr(v, "__doc__", None) or "").strip().splitlines()
        return doc[0][:90] if doc else ""
    try:
        if isinstance(v, float):
            return "%.6g" % v
        if isinstance(v, (list, tuple)):
            return "[" + ", ".join(_preview(x) for x in list(v)[:6]) + (", …]" if len(v) > 6 else "]")
        s = repr(v)
        return s if len(s) <= 90 else s[:87] + "…"
    except Exception:
        return ""


def project_values(app):
    """Read-only live project values a composer usually wants beside the script (never written from here)."""
    out = []
    if app is None:
        return out

    def _v(label, getter):
        try:
            out.append((label, getter()))
        except Exception:
            pass
    _v("bpm", lambda: float(app.spin_bpm.value()))
    _v("sequence_length", lambda: int(app.spin_seq_length.value()))
    _v("base_frequency", lambda: float(app.spin_base_frequency.value()))
    _v("seed_values_t0", lambda: list(app.get_seed_values(t_value=0.0) or [])[:8])
    _v("seed_signature", lambda: int(app._seed_program_signature()))
    try:
        import seed_divergence as _sd
        _v("divergence", lambda: float(_sd.amount_from(app)))
    except Exception:
        pass
    return out


def workspace_reference(app, t=0.0, last_locals=None):
    """[(section, name, kind, preview)] — everything a script can read at beat t."""
    env = env_at(app, t)
    rows = []
    for name in sorted(env, key=lambda s: (not callable(env[s]), s.lower())):
        if name.startswith("_") or name == "__builtins__":
            continue
        v = env[name]
        rows.append(("Functions" if callable(v) else "Values & constants", name, _kind(v), _preview(v)))
    for name, v in project_values(app):
        rows.append(("Live project (read-only)", name, _kind(v), _preview(v)))
    for name, v in sorted((last_locals or {}).items()):
        if not name.startswith("_"):
            rows.append(("Your variables (last run)", name, _kind(v), _preview(v)))
    return rows


def library_dir():
    try:
        import groovebox_paths as _gp
        d = Path(_gp.base_dir()) / "scripts"
    except Exception:
        d = Path.home() / ".groovebox" / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------------------------------------- widgets
class SweepPlot(QWidget):
    """Translucent polyline of the program's first output over t; NaN-free (seed_lang drops non-finite)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.pts = []
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_points(self, pts):
        self.pts = list(pts)
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            r = self.rect().adjusted(6, 6, -6, -6)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(14, 22, 38, 150))
            p.drawRoundedRect(self.rect(), 6, 6)
            pts = [(t, v) for t, v in self.pts if v is not None and math.isfinite(v)]
            if len(pts) < 2:
                p.setPen(QColor(150, 175, 210)); p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), "∿ Sweep plots output 1 over t")
                return
            t0, t1 = pts[0][0], pts[-1][0]
            lo = min(v for _t, v in pts); hi = max(v for _t, v in pts)
            span = (hi - lo) or 1.0; tspan = (t1 - t0) or 1.0
            poly = QPolygonF([QPointF(r.left() + (t - t0) / tspan * r.width(), r.bottom() - (v - lo) / span * r.height())
                              for t, v in pts])
            pen = QPen(QColor(127, 255, 212, 220)); pen.setWidthF(1.6); p.setPen(pen); p.drawPolyline(poly)
            p.setPen(QColor(160, 190, 230))
            p.drawText(r.adjusted(2, 0, 0, 0), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft), "%.5g" % hi)
            p.drawText(r.adjusted(2, 0, 0, 0), int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft), "%.5g" % lo)
        finally:
            p.end()


class ScriptStudio(QWidget):
    def __init__(self, app=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.app = app
        self.path = None
        self._last_locals = {}
        self._sweep = None
        self.setObjectName("ScriptStudio")
        self.setWindowTitle("✍ Script Studio — seed compositions")
        self.resize(1180, 760)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self); root.setContentsMargins(10, 10, 10, 10); root.setSpacing(6)

        # library / file row
        top = QHBoxLayout()
        for text, tip, slot in (("🆕 New", "Start an empty script", self.new_file),
                                ("📂 Open…", "Open a .seed script", self.open_dialog),
                                ("💾 Save", "Save (Ctrl+S)", self.save),
                                ("💾 Save as…", "Save under a new name", self.save_as)):
            b = QPushButton(text); b.setToolTip(tip); b.clicked.connect(slot); top.addWidget(b)
        self.btn_lib = QToolButton(); self.btn_lib.setText("📚 Library"); self.btn_lib.setToolTip(str(library_dir()))
        self.btn_lib.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_lib.setMenu(QMenu(self.btn_lib)); self.btn_lib.menu().aboutToShow.connect(self._fill_library)
        top.addWidget(self.btn_lib)
        self.btn_tpl = QToolButton(); self.btn_tpl.setText("✨ Templates")
        self.btn_tpl.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(self.btn_tpl)
        for name, text in TEMPLATES:
            m.addAction(name, lambda _c=False, tx=text: self._insert_template(tx))
        self.btn_tpl.setMenu(m); top.addWidget(self.btn_tpl)
        top.addStretch(1)
        self.lbl_file = QLabel("untitled"); top.addWidget(self.lbl_file)
        root.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        self.editor = QPlainTextEdit(); self.editor.setObjectName("ScriptStudioEditor")
        f = QFont("Consolas"); f.setStyleHint(QFont.StyleHint.TypeWriter); f.setPointSizeF(11.0)
        self.editor.setFont(f)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))
        self.editor.setPlaceholderText("Write a seed program: numbers and logical statements. t is the beat.\n"
                                       "Try ✨ Templates, then ▶ Evaluate or ∿ Sweep.")
        ll.addWidget(self.editor, 1)
        self._install_editor_support()
        self.lbl_lint = QLabel(""); self.lbl_lint.setWordWrap(True); ll.addWidget(self.lbl_lint)
        split.addWidget(left)

        self.tabs = QTabWidget()
        varw = QWidget(); vl = QVBoxLayout(varw); vl.setContentsMargins(0, 0, 0, 0)
        self.var_filter = QLineEdit(); self.var_filter.setPlaceholderText("Filter variables… (double-click inserts)")
        self.var_filter.textChanged.connect(self._apply_filter); vl.addWidget(self.var_filter)
        self.vars = QTreeWidget(); self.vars.setHeaderLabels(["Name", "Kind", "Value at t / about"])
        self.vars.setColumnWidth(0, 170); self.vars.setColumnWidth(1, 90)
        self.vars.itemDoubleClicked.connect(self._insert_var); vl.addWidget(self.vars, 1)
        self.tabs.addTab(varw, "🔣 Workspace variables")
        self.syntax = QTextBrowser()
        self.syntax.setPlainText("Seed language — free syntax\n\n" + seed_lang.help_text()
                                 + "\n\nResult policy: an explicit return; else every bare top-level expression in order;"
                                   " else coordinate variables (x, y[, z] / r, theta[, phi]); else the last assignment."
                                 + "\n\nSafety: every loop and call is budgeted; non-finite numbers are dropped.")
        self.tabs.addTab(self.syntax, "📖 Syntax")
        self.out = QTextBrowser(); self.tabs.addTab(self.out, "▶ Output")
        split.addWidget(self.tabs)
        split.setStretchFactor(0, 3); split.setStretchFactor(1, 2)
        root.addWidget(split, 1)

        # run bar: the launcher environment
        run = QHBoxLayout()
        run.addWidget(QLabel("t (beats)"))
        self.spin_t = QDoubleSpinBox(); self.spin_t.setRange(-1e6, 1e6); self.spin_t.setDecimals(3)
        self.spin_t.setSingleStep(0.25); self.spin_t.valueChanged.connect(lambda *_a: self._refresh_vars_soon())
        run.addWidget(self.spin_t)
        b = QPushButton("▶ Evaluate at t"); b.setToolTip("Run once at beat t (Ctrl+Enter)"); b.clicked.connect(self.evaluate)
        run.addWidget(b)
        run.addWidget(QLabel("sweep to"))
        self.spin_n = QSpinBox(); self.spin_n.setRange(1, 4096); self.spin_n.setValue(32); run.addWidget(self.spin_n)
        b = QPushButton("∿ Sweep"); b.setToolTip("Plot output 1 over t = 0…N beats"); b.clicked.connect(self.sweep)
        run.addWidget(b)
        run.addStretch(1)
        b = QPushButton("＋ Append to seed"); b.setToolTip("Add this script after the project's seed program")
        b.clicked.connect(lambda: self.send_to_seed(append=True)); run.addWidget(b)
        b = QPushButton("⤴ Use as project seed"); b.setToolTip("Replace the project's seed program with this script")
        b.clicked.connect(lambda: self.send_to_seed(append=False)); run.addWidget(b)
        root.addLayout(run)
        self.plot = SweepPlot(); root.addWidget(self.plot)
        self.status = QLabel(""); root.addWidget(self.status)

        self._lint_timer = QTimer(self); self._lint_timer.setSingleShot(True); self._lint_timer.setInterval(300)
        self._lint_timer.timeout.connect(self.lint)
        self.editor.textChanged.connect(self._lint_timer.start)
        self._var_timer = QTimer(self); self._var_timer.setSingleShot(True); self._var_timer.setInterval(250)
        self._var_timer.timeout.connect(self.refresh_vars)
        self._attach_background()
        self.refresh_vars()

    # ------------------------------------------------------------------ setup helpers
    def _install_editor_support(self):
        mod = _host_module(self.app) if self.app is not None else sys.modules.get("groovebox")
        hl = getattr(mod, "SeedScriptSyntaxHighlighter", None) if mod is not None else None
        if hl is not None:
            try:
                self._hl = hl(self.editor.document())
            except Exception:
                self._hl = None
        try:
            import seed_editor_support as _ses
            _ses.install_auto_indent(self.editor)
        except Exception:
            pass

    def _attach_background(self):
        """Same live mathematical field as every Groovebox window (falls back to the light module copy)."""
        mod = _host_module(self.app) if self.app is not None else sys.modules.get("groovebox")
        try:
            if mod is not None and hasattr(mod, "attach_math_background"):
                mod.attach_math_background(self, self.app)
                return
        except Exception:
            pass
        try:
            from parametric_math_background import ParametricMathBackground
            self._bg = ParametricMathBackground(self); self._bg.lower(); self._bg.show()
        except Exception:
            self._bg = None

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        bg = getattr(self, "_bg", None)
        if bg is not None:
            try:
                bg.setGeometry(self.rect()); bg.lower()
            except RuntimeError:
                pass

    def keyPressEvent(self, ev):
        mods = ev.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier and ev.key() == Qt.Key.Key_S:
            self.save(); return
        if mods & Qt.KeyboardModifier.ControlModifier and ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.evaluate(); return
        super().keyPressEvent(ev)

    # ------------------------------------------------------------------ files
    def _set_path(self, path):
        self.path = str(path) if path else None
        self.lbl_file.setText(Path(self.path).name if self.path else "untitled")
        self.setWindowTitle("✍ Script Studio — " + (Path(self.path).name if self.path else "seed compositions"))

    def new_file(self):
        self.editor.clear(); self._set_path(None)

    def load(self, path):
        try:
            self.editor.setPlainText(Path(path).read_text(encoding="utf-8"))
            self._set_path(path)
            self.status.setText(f"Opened {path}")
        except Exception as exc:
            self.status.setText(f"Could not open {path}: {exc}")

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open seed script", str(library_dir()),
                                              f"Seed scripts (*{EXT} *.txt);;All files (*)")
        if path:
            self.load(path)

    def save(self):
        if not self.path:
            return self.save_as()
        tmp = self.path + ".part"
        try:
            Path(tmp).write_text(self.editor.toPlainText(), encoding="utf-8")
            os.replace(tmp, self.path)                    # atomic: a crash never leaves half a script
            self.status.setText(f"Saved {self.path}")
            return self.path
        except Exception as exc:
            self.status.setText(f"Save failed: {exc}")
            return None

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save seed script", str(library_dir() / f"untitled{EXT}"),
                                              f"Seed scripts (*{EXT});;All files (*)")
        if not path:
            return None
        if not Path(path).suffix:
            path += EXT
        self._set_path(path)
        return self.save()

    def _fill_library(self):
        m = self.btn_lib.menu(); m.clear()
        files = sorted(library_dir().glob(f"*{EXT}"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]
        if not files:
            a = m.addAction("(no scripts yet — 💾 Save as… puts them here)"); a.setEnabled(False)
        for f in files:
            m.addAction(f.name, lambda _c=False, p=str(f): self.load(p))
        m.addSeparator()
        m.addAction("📁 Open library folder", lambda: self._open_folder(library_dir()))

    @staticmethod
    def _open_folder(path):
        try:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception:
            pass

    def _insert_template(self, text):
        if self.editor.toPlainText().strip():
            self.editor.moveCursor(QTextCursor.MoveOperation.End)
            self.editor.insertPlainText("\n\n" + text)
        else:
            self.editor.setPlainText(text)

    # ------------------------------------------------------------------ variables reference
    def _refresh_vars_soon(self):
        self._var_timer.start()

    def refresh_vars(self):
        try:
            rows = workspace_reference(self.app, float(self.spin_t.value()), self._last_locals)
        except Exception as exc:
            rows = [("Errors", "environment", "", str(exc))]
        self.vars.setUpdatesEnabled(False)
        try:
            self.vars.clear()
            sections = {}
            for sec, name, kind, prev in rows:
                parent = sections.get(sec)
                if parent is None:
                    parent = sections[sec] = QTreeWidgetItem(self.vars, [sec, "", ""])
                    parent.setFirstColumnSpanned(True)
                    parent.setExpanded(sec != "Functions" or len(rows) < 120)
                it = QTreeWidgetItem(parent, [name, kind, prev])
                it.setToolTip(2, prev)
            self._apply_filter(self.var_filter.text())
        finally:
            self.vars.setUpdatesEnabled(True)
        self._allowed = {name for _s, name, _k, _p in rows}

    def _apply_filter(self, text):
        q = str(text or "").strip().lower()
        for i in range(self.vars.topLevelItemCount()):
            sec = self.vars.topLevelItem(i); shown = 0
            for j in range(sec.childCount()):
                ch = sec.child(j)
                hit = not q or q in ch.text(0).lower() or q in ch.text(2).lower()
                ch.setHidden(not hit); shown += hit
            sec.setHidden(shown == 0)
            if q and shown:
                sec.setExpanded(True)

    def _insert_var(self, item, _col=0):
        if item is None or item.parent() is None:
            return
        name = item.text(0)
        sec = item.parent().text(0)
        if sec.startswith("Live project"):
            name = item.text(2)               # read-only project values are inserted as their number
        elif item.text(1) == "function":
            name += "()"
        self.editor.insertPlainText(name)
        if name.endswith("()"):
            self.editor.moveCursor(QTextCursor.MoveOperation.Left)
        self.editor.setFocus()

    # ------------------------------------------------------------------ run
    def lint(self):
        text = self.editor.toPlainText()
        if not text.strip():
            self.lbl_lint.setText(""); return
        try:
            res = seed_lang.analyze(text, getattr(self, "_allowed", set()))
        except Exception as exc:
            res = (str(exc), 0, 0, 0, "error")
        if res is None:
            self.lbl_lint.setText("<span style='color:#7ee787'>✓ looks valid</span>")
        else:
            msg, line, col = res[0], res[1], res[2]
            sev = res[4] if len(res) > 4 else "error"
            colr = "#ffb070" if sev == "warning" else "#ff8fa3"
            self.lbl_lint.setText(f"<span style='color:{colr}'>{'⚠' if sev == 'warning' else '✗'} line {line}"
                                  f"{', col ' + str(col) if col else ''}: {msg}</span>")

    def evaluate(self):
        t = float(self.spin_t.value())
        ev = seed_lang.evaluate(self.editor.toPlainText(), env_at(self.app, t))
        self._last_locals = dict(getattr(ev, "locals", None) or {})
        if ev.error:
            self.out.setHtml(f"<b style='color:#ff8fa3'>Error</b> (line {ev.line}): {ev.error}")
            self.status.setText(f"t={t:g}: error on line {ev.line}")
        else:
            vals = ", ".join("%.6g" % v for v in ev.values[:64]) + (" …" if len(ev.values) > 64 else "")
            self.out.setHtml(f"<b>t = {t:g}</b> · {len(ev.values)} value(s) from <i>{ev.source}</i><br>"
                             f"<span style='color:#7fffd4'>{vals or '(no numbers)'}</span>")
            self.status.setText(f"t={t:g}: {len(ev.values)} value(s)")
        self.tabs.setCurrentWidget(self.out)
        self._refresh_vars_soon()
        return ev

    def sweep(self):
        """Evaluate t = 0…N in chunks of SWEEP_CHUNK per event-loop turn (the UI never freezes)."""
        n = int(self.spin_n.value())
        steps = min(512, max(8, n * 8))
        text = self.editor.toPlainText()
        self._sweep = {"text": text, "i": 0, "steps": steps, "n": n, "pts": [], "errors": 0}
        self.status.setText("∿ sweeping…")
        QTimer.singleShot(0, self._sweep_tick)

    def _sweep_tick(self):
        sw = self._sweep
        if sw is None:
            return
        end = min(sw["steps"] + 1, sw["i"] + SWEEP_CHUNK)
        for i in range(sw["i"], end):
            t = sw["n"] * i / float(sw["steps"])
            ev = seed_lang.evaluate(sw["text"], env_at(self.app, t))
            if ev.error or not ev.values:
                sw["errors"] += 1; sw["pts"].append((t, None))
            else:
                sw["pts"].append((t, float(ev.values[0])))
        sw["i"] = end
        self.plot.set_points(sw["pts"])
        if end <= sw["steps"]:
            QTimer.singleShot(0, self._sweep_tick)
        else:
            self.status.setText(f"∿ swept t = 0…{sw['n']} ({sw['steps'] + 1} points"
                                + (f", {sw['errors']} without a value" if sw["errors"] else "") + ")")
            self._sweep = None

    def send_to_seed(self, append=False):
        app = self.app
        box = getattr(app, "input_seed_val", None) if app is not None else None
        if box is None:
            self.status.setText("Open Groovebox to send a script to the project seed (standalone mode edits files only).")
            return False
        text = self.editor.toPlainText().strip()
        if not text:
            return False
        if not append:
            ans = QMessageBox.question(self, "Replace project seed?",
                                       "Replace the project's seed program with this script?\n"
                                       "Everything derived from the seed will recompose. (Undo restores the old seed.)")
            if ans != QMessageBox.StandardButton.Yes:
                return False
        try:
            if hasattr(app, "_push_undo"):
                app._push_undo("Script Studio → seed")
        except Exception:
            pass
        old = box.toPlainText()
        box.setPlainText(text if not append else (old.rstrip() + "\n" + text if old.strip() else text))
        self.status.setText("Project seed " + ("extended" if append else "replaced") + " from Script Studio.")
        return True


def open_window(app=None, path=None):
    """Singleton Script Studio window (one per process)."""
    w = _WIN["w"]
    try:
        if w is not None:
            w.isVisible()
    except RuntimeError:
        w = None
    if w is None:
        w = _WIN["w"] = ScriptStudio(app)
    if path:
        w.load(path)
    w.show(); w.raise_(); w.activateWindow()
    return w


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    qa = QApplication.instance() or QApplication(argv)
    try:
        import emoji_fonts
        emoji_fonts.install(qa)
        import window_scroll
        window_scroll.install(qa)
    except Exception:
        pass
    open_window(None, argv[1] if len(argv) > 1 and os.path.isfile(argv[1]) else None)
    return qa.exec()


if __name__ == "__main__":
    sys.exit(main())
