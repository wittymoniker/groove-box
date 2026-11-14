"""ui_panels_ui.py — UI_PANES_R6: the "🧩 Window panes" manager (own window + a compact row in System Settings).

Pick a window, then arrange its panes: stacked or side by side, order, size share, shown / hidden, and where its
docks sit. Every change applies live. Save the arrangement of every window as a named format; the active format
is applied at launch and to windows opened later. Every pane scrolls on both axes, so any size share works.
"""
from __future__ import annotations

import copy
import weakref

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, QPushButton, QLabel,
                             QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QSpinBox, QInputDialog,
                             QFileDialog, QMessageBox, QAbstractItemView, QGroupBox, QScrollArea)

import ui_panels as up

_WINDOW = {"ref": None}
_ORIENT = (("Stacked (top → bottom)", "v"), ("Side by side (left → right)", "h"))


class PaneManager(QWidget):
    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self._app_ref = weakref.ref(app) if app is not None else (lambda: None)
        self._fmt = {}
        self._busy = False
        self._wins = []
        self._live = QTimer(self); self._live.setSingleShot(True); self._live.setInterval(120)
        self._live.timeout.connect(self._push)
        v = QVBoxLayout(self); v.setContentsMargins(6, 6, 6, 6)
        top = QHBoxLayout(); top.addWidget(QLabel("Format"))
        self.cb = QComboBox(); self.cb.setMinimumWidth(220); top.addWidget(self.cb, 1)
        v.addLayout(top)
        g = QGridLayout()
        self.b_save = QPushButton("💾 Save as…"); self.b_del = QPushButton("🗑 Delete")
        self.b_reset = QPushButton("↺ Program layout"); self.b_cap = QPushButton("📐 Use the current arrangement")
        self.b_imp = QPushButton("Import…"); self.b_exp = QPushButton("Export…")
        for i, b in enumerate((self.b_save, self.b_del, self.b_reset, self.b_cap, self.b_imp, self.b_exp)):
            g.addWidget(b, i // 3, i % 3)
        self.b_cap.setToolTip("Take the selected window's panes exactly as they are now (after dragging splitters "
                              "or docks by hand) into this format.")
        self.b_reset.setToolTip("Every window back to the program's own pane layout (the Default format).")
        v.addLayout(g)
        wr = QHBoxLayout(); wr.addWidget(QLabel("Window"))
        self.cb_win = QComboBox(); wr.addWidget(self.cb_win, 1)
        self.b_refresh = QPushButton("⟳"); self.b_refresh.setMaximumWidth(34); self.b_refresh.setToolTip("Re-read open windows")
        wr.addWidget(self.b_refresh)
        v.addLayout(wr)
        self.body = QWidget(); self.body_lay = QVBoxLayout(self.body); self.body_lay.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(self.body)
        v.addWidget(sc, 1)
        self.status = QLabel(""); self.status.setWordWrap(True); self.status.setStyleSheet("color:#9fb4c8;")
        v.addWidget(self.status)
        self.cb.activated.connect(lambda _i: self._choose(self.cb.currentData()))
        self.cb_win.activated.connect(lambda _i: self._build())
        self.b_refresh.clicked.connect(self._fill_windows)
        self.b_save.clicked.connect(self._save_as); self.b_del.clicked.connect(self._delete)
        self.b_reset.clicked.connect(self._reset); self.b_cap.clicked.connect(self._capture)
        self.b_imp.clicked.connect(self._import); self.b_exp.clicked.connect(self._export)
        self._fill_presets(up.active_name())
        self._fmt = up.get_preset(up.active_name())
        self.b_del.setEnabled(not up.is_builtin(up.active_name()))
        self._fill_windows()

    # ---------------------------------------------------------- lists
    def _say(self, t):
        self.status.setText(t)

    def _fill_presets(self, select=None):
        self.cb.blockSignals(True); self.cb.clear()
        for n in up.preset_names():
            self.cb.addItem(n + ("   · built-in" if up.is_builtin(n) else ""), n)
        self.cb.setCurrentIndex(max(0, self.cb.findData(select)) if select else 0)
        self.cb.blockSignals(False)

    def _name(self):
        return self.cb.currentData() or "Default"

    def _fill_windows(self):
        cur = self._win()
        self._wins = [weakref.ref(w) for w in up.open_windows()]
        app = self._app_ref()
        if app is not None and all(r() is not app for r in self._wins):
            self._wins.insert(0, weakref.ref(app))
        self.cb_win.clear()
        for r in self._wins:
            w = r()
            n_sp, n_dk = len(up.splitters(w)), len(up.docks(w))
            self.cb_win.addItem(f"{(w.windowTitle() or up.window_key(w))[:48]}  ·  {n_sp} split, {n_dk} dock")
        if cur is not None:
            for i, r in enumerate(self._wins):
                if r() is cur:
                    self.cb_win.setCurrentIndex(i)
        self._build()

    def _win(self):
        i = self.cb_win.currentIndex() if hasattr(self, "cb_win") else -1
        if 0 <= i < len(self._wins):
            return self._wins[i]()
        return None

    # ---------------------------------------------------------- editor
    def _build(self):
        while self.body_lay.count():
            it = self.body_lay.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        self._editors = []
        win = self._win()
        if win is None:
            self.body_lay.addWidget(QLabel("No Groovebox window with panes is open.")); return
        d = up.describe(win)
        self._busy = True
        for s in d["splitters"]:
            box = QGroupBox(f"Splitter · {s['key']}"); bl = QVBoxLayout(box)
            orient = QComboBox()
            for lab, val in _ORIENT:
                orient.addItem(lab, val)
            orient.setCurrentIndex(0 if s["orientation"] == "v" else 1)
            bl.addWidget(orient)
            t = QTableWidget(len(s["panes"]), 5)
            t.setHorizontalHeaderLabels(["Pane", "Shown", "Size %", "", ""])
            t.verticalHeader().setVisible(False); t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            hh = t.horizontalHeader(); hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for c in range(1, 5):
                hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
            ed = {"key": s["key"], "orient": orient, "table": t, "rows": []}
            for r, p in enumerate(s["panes"]):
                self._row(ed, r, p["key"], p["label"], p["shown"], int(round(100 * p["size"])) if p["shown"] else 25)
            t.setMinimumHeight(min(260, 36 + 34 * len(s["panes"])))
            bl.addWidget(t)
            orient.currentIndexChanged.connect(lambda _i: self._live.start())
            self._editors.append(ed); self.body_lay.addWidget(box)
        self._docks = []
        if d["docks"]:
            box = QGroupBox("Docks"); bl = QGridLayout(box)
            for i, dk in enumerate(d["docks"]):
                bl.addWidget(QLabel(dk["title"][:60] or dk["key"]), i, 0)
                ca = QComboBox(); ca.addItems(list(up.AREAS)); ca.setCurrentText(dk["area"]); bl.addWidget(ca, i, 1)
                ch = QCheckBox("shown"); ch.setChecked(dk["visible"]); bl.addWidget(ch, i, 2)
                ca.currentTextChanged.connect(lambda _t: self._live.start()); ch.toggled.connect(lambda _b: self._live.start())
                self._docks.append((dk["key"], ca, ch))
            self.body_lay.addWidget(box)
        if not d["splitters"] and not d["docks"]:
            self.body_lay.addWidget(QLabel("This window has a single pane."))
        self.body_lay.addStretch(1)
        self._busy = False
        self._say(f"“{self._name()}” · window key “{d['key']}” · {len(d['splitters'])} splitter(s), {len(d['docks'])} dock(s). "
                  "Every pane scrolls both ways, so any size share works.")

    def _row(self, ed, r, key, label, shown, pct):
        t = ed["table"]
        it = QTableWidgetItem(label); it.setToolTip("pane key: " + key); it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        it.setData(Qt.ItemDataRole.UserRole, key)
        t.setItem(r, 0, it)
        ch = QCheckBox(); ch.setChecked(bool(shown)); ch.toggled.connect(lambda _b: self._live.start())
        t.setCellWidget(r, 1, ch)
        sp = QSpinBox(); sp.setRange(int(100 * up.MIN_FRACTION), 97); sp.setSuffix(" %"); sp.setValue(max(3, min(97, pct)))
        sp.valueChanged.connect(lambda _n: self._live.start())
        t.setCellWidget(r, 2, sp)
        bu = QPushButton("↑"); bd = QPushButton("↓")
        bu.setMaximumWidth(30); bd.setMaximumWidth(30)
        bu.clicked.connect(lambda _=False, e=ed, k=key: self._move(e, k, -1))
        bd.clicked.connect(lambda _=False, e=ed, k=key: self._move(e, k, +1))
        t.setCellWidget(r, 3, bu); t.setCellWidget(r, 4, bd)

    def _rows_of(self, ed):
        t = ed["table"]; out = []
        for r in range(t.rowCount()):
            out.append((t.item(r, 0).data(Qt.ItemDataRole.UserRole), t.item(r, 0).text(),
                        t.cellWidget(r, 1).isChecked(), t.cellWidget(r, 2).value()))
        return out

    def _move(self, ed, key, step):
        rows = self._rows_of(ed)
        i = next(j for j, r in enumerate(rows) if r[0] == key)
        j = i + step
        if not 0 <= j < len(rows):
            return
        rows[i], rows[j] = rows[j], rows[i]
        self._busy = True
        for r, (k, lab, sh, pct) in enumerate(rows):
            self._row(ed, r, k, lab, sh, pct)
        self._busy = False
        self._live.start()

    def _entry(self):
        sp = {}
        for ed in self._editors:
            rows = self._rows_of(ed)
            shown = [r for r in rows if r[2]]
            if not shown:                             # one pane always stays
                rows[0] = (rows[0][0], rows[0][1], True, rows[0][3]); shown = [rows[0]]
            tot = float(sum(r[3] for r in shown)) or 1.0
            e = {"orientation": ed["orient"].currentData(), "order": [r[0] for r in rows],
                 "sizes": {r[0]: round(r[3] / tot, 4) for r in shown}}
            hid = [r[0] for r in rows if not r[2]]
            if hid:
                e["hidden"] = hid
            sp[ed["key"]] = e
        dk = {k: {"area": ca.currentText(), "visible": ch.isChecked()} for k, ca, ch in getattr(self, "_docks", [])}
        w = {}
        if sp:
            w["splitters"] = sp
        if dk:
            w["docks"] = dk
        return w

    def _push(self):
        if self._busy:
            return
        win = self._win()
        if win is None:
            return
        fmt = copy.deepcopy(self._fmt)
        fmt.setdefault("windows", {})[up.window_key(win)] = self._entry()
        self._fmt = up.sanitize(fmt)
        rep = up.apply_window(win, self._fmt)
        self._say(f"Applied to “{rep['window']}”: {rep['panes']} panes in {rep['splitters']} splitter(s)"
                  + (f", {rep['hidden']} hidden" if rep["hidden"] else "") + (f", {rep['docks']} dock(s)" if rep["docks"] else "")
                  + ("  · not saved yet — Save as… to keep it" if up.is_builtin(self._name()) else "  · Save as… to keep it"))

    # ---------------------------------------------------------- formats
    def _choose(self, name):
        self._fmt = up.get_preset(name)
        up.set_active(name)
        self.b_del.setEnabled(not up.is_builtin(name))
        reps = up.apply(self._fmt, [r() for r in self._wins if r() is not None])
        self._build()
        miss = sorted({m for r in reps for m in r["missing"]})
        self._say(f"“{name}” applied to {len(reps)} window(s)" + (" · not found: " + ", ".join(miss) if miss else ""))

    def _save_as(self):
        cur = self._name()
        name, ok = QInputDialog.getText(self, "Save pane format", "Format name:", text="" if up.is_builtin(cur) else cur)
        if not ok or not name.strip():
            return
        try:
            name = up.save_preset(name, self._fmt)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Save pane format", str(exc)); return
        self._fill_presets(name); self.b_del.setEnabled(True)
        self._say(f"Saved “{name}” — applied at every launch and to windows opened later.")

    def _delete(self):
        name = self._name()
        if up.is_builtin(name) or QMessageBox.question(self, "Delete format", f"Delete “{name}”?") != QMessageBox.StandardButton.Yes:
            return
        up.delete_preset(name); self._fill_presets("Default"); self._choose("Default")

    def _reset(self):
        self._fill_presets("Default"); self._choose("Default")
        self._say("Every window is back to the program's own pane layout.")

    def _capture(self):
        win = self._win()
        if win is not None:
            self._fmt = up.merge(self._fmt, up.capture(win))
            self._build(); self._say("Took the current arrangement of this window — Save as… to keep it.")

    def _import(self):
        p, _ = QFileDialog.getOpenFileName(self, "Import pane format", "", "Pane format (*.json)")
        if not p:
            return
        try:
            name = up.import_preset(p)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import pane format", str(exc)); return
        self._fill_presets(name); self._choose(name)

    def _export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Export pane format", f"{self._name()}.json", "Pane format (*.json)")
        if p:
            up.export_format(self._name(), self._fmt, p); self._say("Exported to " + p)


def compact_row(app, parent=None):
    """System Settings row: format picker + Apply + "Arrange panes…"."""
    w = QWidget(parent); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
    cb = QComboBox()
    for n in up.preset_names():
        cb.addItem(n, n)
    cb.setCurrentIndex(max(0, cb.findData(up.active_name())))
    b_apply = QPushButton("Apply"); b_open = QPushButton("🧩 Arrange panes…")

    def _apply():
        name = cb.currentData(); up.set_active(name); up.apply(up.get_preset(name))
    b_apply.clicked.connect(_apply)
    b_open.clicked.connect(lambda: open_window(app))
    h.addWidget(cb, 1); h.addWidget(b_apply); h.addWidget(b_open)
    return w


def open_window(app=None):
    w = _WINDOW["ref"]() if _WINDOW["ref"] else None
    try:
        if w is not None:
            w._mgr._fill_windows(); w.show(); w.raise_(); w.activateWindow(); return w
    except RuntimeError:
        w = None
    w = QWidget(None, Qt.WindowType.Window)
    w.setObjectName("grooveboxPaneManager")
    w.setWindowTitle("🧩 Window panes · your pane formats")
    w.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    w.resize(720, 640)
    lay = QVBoxLayout(w)
    w._mgr = PaneManager(app, w)
    lay.addWidget(w._mgr)
    _WINDOW["ref"] = weakref.ref(w)
    try:
        import window_keeper
        window_keeper.keep(w)
    except Exception:
        pass
    w.show(); w.raise_(); w.activateWindow()
    return w
