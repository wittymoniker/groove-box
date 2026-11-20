"""Markov Resampler editor window (GROOVEBOX_R123_MARKOV_RESAMPLER_WINDOW_20261119).

Non-modal editor for the selected instrument's selected sequence: model states, transition weights,
the polynomial preference curve, the seed, the canonical binding, a live preview with a before/after
comparison, a transition-matrix heat map, the per-step decision trace and an explanation of every
selection. Apply writes the result as a normal undoable, user-owned sequence edit.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QTimer, QEvent, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QComboBox, QDoubleSpinBox,
    QSpinBox, QCheckBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QTextBrowser,
    QScrollArea, QSplitter, QHeaderView, QAbstractItemView, QSizePolicy, QApplication,
)

import markov_resampler as mr

_BG = "#0f141b"
_STYLE = (
    f"QWidget#markovResamplerWindow {{ background:{_BG}; }}"
    "QGroupBox { color:#9fe7ff; background:#131b24; border:1px solid #2f4b5e; border-radius:7px;"
    " margin-top:8px; padding-top:10px; font-weight:900; }"
    "QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }"
    "QLabel { color:#dbe7f0; font-size:9pt; }"
    "QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit { background:#0b1118; color:#e6f3ff;"
    " border:1px solid #3c5a70; border-radius:4px; padding:2px 4px; min-height:22px; }"
    "QCheckBox { color:#dbe7f0; font-size:9pt; }"
    "QPushButton { background:#1b2a37; color:#e6f3ff; border:1px solid #4d7690; border-radius:5px;"
    " padding:5px 10px; font-weight:800; }"
    "QPushButton:hover { background:#24394a; }"
    "QPushButton#markovApply { background:#183d2a; border-color:#5fd39a; color:#c9ffe2; }"
    "QTextBrowser, QTableWidget { background:#0b1118; color:#dbe7f0; border:1px solid #2f4b5e; }"
    "QHeaderView::section { background:#16222d; color:#9fe7ff; border:0; padding:3px; }"
)


class _CurvePlot(QWidget):
    """f(y) over y ∈ [0, 1] with the destination values marked on the axis."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spec = mr.normalize_spec({})
        self.points: list[float] = []
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, spec, points):
        self.spec, self.points = spec, list(points)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(28, 8, -8, -18)
        p.fillRect(self.rect(), QColor("#0b1118"))
        p.setPen(QPen(QColor("#2f4b5e"), 1)); p.drawRect(r)
        ys = [mr.preference(self.spec, i / 100.0) for i in range(101)]
        top = max(1e-9, max(ys))
        p.setPen(QPen(QColor("#5fd3ff"), 2))
        prev = None
        for i, v in enumerate(ys):
            pt = QPointF(r.left() + r.width() * i / 100.0, r.bottom() - r.height() * v / top)
            if prev is not None:
                p.drawLine(prev, pt)
            prev = pt
        p.setPen(QPen(QColor("#ffcf5a"), 1))
        for y in self.points:
            x = r.left() + r.width() * y
            p.drawLine(QPointF(x, r.bottom()), QPointF(x, r.bottom() + 5))
        p.setPen(QColor("#8fa8ba")); p.setFont(QFont(p.font().family(), 7))
        p.drawText(QRectF(0, r.top() - 2, 26, 12), Qt.AlignmentFlag.AlignRight, f"{top:.2g}")
        p.drawText(QRectF(0, r.bottom() - 10, 26, 12), Qt.AlignmentFlag.AlignRight, "0")
        p.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 12), Qt.AlignmentFlag.AlignLeft, "y = 0")
        p.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 12), Qt.AlignmentFlag.AlignRight, "y = 1")
        p.end()


class _MatrixView(QWidget):
    """Row-normalised base transition matrix heat map (≤ 64 × 64 shown, evenly subsampled)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[list[float]] = []
        self.labels: list[int] = []
        self.mark = None
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, positions, rows, mark=None):
        m = len(rows)
        if m > 64:
            idx = [int(round(i * (m - 1) / 63)) for i in range(64)]
            rows = [[rows[a][b] for b in idx] for a in idx]
            positions = [positions[a] for a in idx]
        self.rows, self.labels, self.mark = rows, list(positions), mark
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0b1118"))
        m = len(self.rows)
        if not m:
            p.setPen(QColor("#8fa8ba")); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "no states")
            p.end(); return
        side = min(self.width() - 30, self.height() - 22)
        cell = side / m
        ox, oy = 26.0, 4.0
        top = max(max(r) for r in self.rows) or 1.0
        for a, row in enumerate(self.rows):
            for b, v in enumerate(row):
                t = math.sqrt(max(0.0, v) / top)
                p.fillRect(QRectF(ox + b * cell, oy + a * cell, cell + 0.5, cell + 0.5),
                           QColor(int(20 + 235 * t), int(30 + 150 * t), int(60 + 60 * (1 - t))))
        if self.mark is not None and self.mark in self.labels:
            a = self.labels.index(self.mark)
            p.setPen(QPen(QColor("#ffffff"), 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(ox, oy + a * cell, side, cell))
        p.setPen(QColor("#8fa8ba")); p.setFont(QFont(p.font().family(), 7))
        p.drawText(QRectF(0, oy, 24, 12), Qt.AlignmentFlag.AlignRight, f"{self.labels[0] + 1}")
        p.drawText(QRectF(0, oy + side - 12, 24, 12), Qt.AlignmentFlag.AlignRight, f"{self.labels[-1] + 1}")
        p.drawText(QRectF(ox, oy + side + 2, side, 14), Qt.AlignmentFlag.AlignCenter,
                   "from (rows) → to (columns) · brighter = likelier")
        p.end()


class _CompareView(QWidget):
    """Before / after step lanes; lines connect each output step to the source step it took."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result = None
        self.mark = None
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_result(self, result, mark=None):
        self.result, self.mark = result, mark
        self.update()

    @staticmethod
    def _color(lanes, i):
        try:
            x = 0.5 + 0.5 * math.log2(max(1e-6, float(lanes["pitches"][i])))
        except (TypeError, ValueError):
            x = 0.5
        x = min(1.0, max(0.0, x))
        return QColor.fromHsvF(0.55 - 0.45 * x, 0.75, 0.95)

    def _row(self, p, lanes, y0, h, label):
        n = len(lanes["steps"])
        w = (self.width() - 60) / max(1, n)
        p.setPen(QColor("#8fa8ba")); p.drawText(QRectF(2, y0, 54, h), Qt.AlignmentFlag.AlignVCenter, label)
        for i in range(n):
            x = 58 + i * w
            p.fillRect(QRectF(x + 1, y0, max(1.0, w - 2), h), QColor("#16222d"))
            if lanes["steps"][i]:
                try:
                    a = min(1.0, max(0.05, float(lanes["amplitudes"][i])))
                except (TypeError, ValueError):
                    a = 1.0
                p.fillRect(QRectF(x + 1, y0 + h * (1 - a), max(1.0, w - 2), h * a), self._color(lanes, i))
        return w

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b1118"))
        if not self.result:
            p.setPen(QColor("#8fa8ba")); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Preview to compare")
            p.end(); return
        h = (self.height() - 46) / 2.0
        w = self._row(p, self.result["before"], 4, h, "Before")
        self._row(p, self.result["after"], 42 + h, h, "After")
        for out_i, src_i in zip(self.result["positions"], self.result["sources"]):
            if out_i == src_i and self.mark is None:
                continue
            sel = self.mark == out_i
            p.setPen(QPen(QColor("#ffffff" if sel else "#5fd3ff"), 2 if sel else 1))
            p.drawLine(QPointF(58 + (src_i + 0.5) * w, 4 + h + 1), QPointF(58 + (out_i + 0.5) * w, 42 + h - 1))
        p.end()


class MarkovResamplerWindow(QWidget):
    def __init__(self, host=None):
        super().__init__(None, Qt.WindowType.Window)
        self.host = host
        self.setObjectName("markovResamplerWindow")
        self.setWindowTitle("Markov Resampler · polynomial-weighted · canonical-aware")
        self.setStyleSheet(_STYLE)
        self.resize(1180, 760)
        self._result = None
        self._loading = False
        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.setInterval(220)
        self._timer.timeout.connect(self.preview)
        self._explain_for: dict = {}
        self._build()
        self._load_spec(getattr(host, "markov_resampler_spec", None))
        try:
            host.instrument_selector_dropdown.currentTextChanged.connect(lambda *_: self._schedule())
        except Exception:
            pass

    # ---------- construction ----------
    def _ctl(self, widget, key):
        widget.setToolTip(mr.EXPLAIN.get(key, ""))
        widget.installEventFilter(self)
        self._explain_for[widget] = key
        return widget

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(8, 8, 8, 8); root.setSpacing(6)
        head = QLabel("<b>MARKOV RESAMPLER</b> — rebuilds the selected sequence by walking a deterministic, "
                      "polynomial-weighted Markov chain over its steps. Same seed + same settings = same result; "
                      "every decision is listed below. Apply is undoable (Ctrl+Z).")
        head.setWordWrap(True); head.setStyleSheet("color:#c9f3ff; font-size:10pt;")
        root.addWidget(head)
        split = QSplitter(Qt.Orientation.Horizontal); root.addWidget(split, 1)

        # Left: settings (scrollable on small screens).
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 4, 0); ll.setSpacing(6)
        src = QGroupBox("SOURCE · MODEL STATES"); sl = QGridLayout(src)
        self.lbl_source = QLabel("—"); self.lbl_source.setWordWrap(True)
        sl.addWidget(QLabel("Sequence"), 0, 0); sl.addWidget(self.lbl_source, 0, 1)
        self.combo_states = self._ctl(QComboBox(), "states")
        self.combo_states.addItem("All steps", "all_steps"); self.combo_states.addItem("Active steps only", "active_steps")
        sl.addWidget(QLabel("States"), 1, 0); sl.addWidget(self.combo_states, 1, 1)
        ll.addWidget(src)

        tw = QGroupBox("TRANSITION WEIGHTS"); tl = QGridLayout(tw)
        self.spin_locality = self._ctl(QDoubleSpinBox(), "locality"); self.spin_locality.setRange(0, 16); self.spin_locality.setSingleStep(0.25)
        self.combo_advance = self._ctl(QComboBox(), "advance")
        for t, v in (("+1 forward", 1), ("0 hold", 0), ("−1 reverse", -1)):
            self.combo_advance.addItem(t, v)
        self.spin_self = self._ctl(QDoubleSpinBox(), "self_weight"); self.spin_self.setRange(0, 16); self.spin_self.setSingleStep(0.1)
        self.chk_wrap = self._ctl(QCheckBox("Wrap around the loop"), "wrap")
        self.combo_decay = self._ctl(QComboBox(), "decay")
        self.combo_decay.addItem("Power 1/(1+d^p)", "power"); self.combo_decay.addItem("Meum geometric M^(−p·d²)", "meum")
        self.spin_euclid = self._ctl(QDoubleSpinBox(), "euclid_bonus"); self.spin_euclid.setRange(0, 16); self.spin_euclid.setSingleStep(0.1)
        self.spin_pulses = self._ctl(QSpinBox(), "euclid_pulses"); self.spin_pulses.setRange(1, mr.MAX_STEPS)
        self.spin_fractal = self._ctl(QDoubleSpinBox(), "fractal_bonus"); self.spin_fractal.setRange(0, 16); self.spin_fractal.setSingleStep(0.1)
        rows = (("Locality p", self.spin_locality), ("Advance", self.combo_advance), ("Self weight", self.spin_self),
                ("Distance law", self.combo_decay), ("Euclid bonus", self.spin_euclid), ("Euclid pulses", self.spin_pulses),
                ("Fractal bonus", self.spin_fractal))
        for r, (t, w) in enumerate(rows):
            tl.addWidget(QLabel(t), r, 0); tl.addWidget(w, r, 1)
        tl.addWidget(self.chk_wrap, len(rows), 0, 1, 2)
        ll.addWidget(tw)

        pg = QGroupBox("POLYNOMIAL CURVE · P_j(x) = (1−k)·f(x_j) + k·x_j·x"); pl = QGridLayout(pg)
        self.combo_lane = self._ctl(QComboBox(), "input_lane")
        for t, v in (("Amplitude", "amplitudes"), ("Gate", "gates"), ("Pitch (±1 oct)", "pitches"),
                     ("Probability", "probabilities"), ("Offset", "offsets")):
            self.combo_lane.addItem(t, v)
        pl.addWidget(QLabel("Input lane"), 0, 0); pl.addWidget(self.combo_lane, 0, 1, 1, 3)
        self.spin_c = []
        for i in range(4):
            s = self._ctl(QDoubleSpinBox(), "coefficients"); s.setRange(-16, 16); s.setDecimals(3); s.setSingleStep(0.05)
            self.spin_c.append(s)
            pl.addWidget(QLabel(f"c{i}"), 1 + i // 2, (i % 2) * 2); pl.addWidget(s, 1 + i // 2, (i % 2) * 2 + 1)
        self.spin_k = self._ctl(QDoubleSpinBox(), "coupling"); self.spin_k.setRange(0, 1); self.spin_k.setDecimals(3); self.spin_k.setSingleStep(0.05)
        pl.addWidget(QLabel("Coupling k"), 3, 0); pl.addWidget(self.spin_k, 3, 1)
        self.lbl_expr = QLabel(""); self.lbl_expr.setStyleSheet("color:#5fd3ff; font-family:monospace;")
        pl.addWidget(self.lbl_expr, 4, 0, 1, 4)
        self.curve = _CurvePlot(); pl.addWidget(self.curve, 5, 0, 1, 4)
        ll.addWidget(pg)

        sg = QGroupBox("SEED · CANONICALS"); sgl = QGridLayout(sg)
        self.combo_seed = self._ctl(QComboBox(), "seed_source")
        self.combo_seed.addItem("Canonical (project seed)", "canonical"); self.combo_seed.addItem("Custom text", "custom")
        self.edit_seed = self._ctl(QLineEdit(), "seed_source"); self.edit_seed.setPlaceholderText("custom seed text")
        self.chk_follow = self._ctl(QCheckBox("Follow canonicals"), "follow_canonicals")
        self.lbl_canon = QLabel(""); self.lbl_canon.setWordWrap(True); self.lbl_canon.setStyleSheet("color:#ffe58a;")
        sgl.addWidget(QLabel("Seed"), 0, 0); sgl.addWidget(self.combo_seed, 0, 1); sgl.addWidget(self.edit_seed, 1, 0, 1, 2)
        sgl.addWidget(self.chk_follow, 2, 0, 1, 2); sgl.addWidget(self.lbl_canon, 3, 0, 1, 2)
        ll.addWidget(sg)

        lg = QGroupBox("CARRIED LANES"); lgl = QGridLayout(lg)
        self.chk_lanes = {}
        for i, ln in enumerate(mr.LANES):
            c = self._ctl(QCheckBox(ln.capitalize()), "lanes"); self.chk_lanes[ln] = c
            lgl.addWidget(c, i // 3, i % 3)
        ll.addWidget(lg)
        ll.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(left)
        scroll.setMinimumWidth(360); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        split.addWidget(scroll)

        # Right: preview, comparison, matrix, trace, explanation.
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(4, 0, 0, 0); rl.setSpacing(6)
        cg = QGroupBox("BEFORE / AFTER"); cgl = QVBoxLayout(cg)
        self.compare = _CompareView(); cgl.addWidget(self.compare)
        self.lbl_summary = QLabel("—"); self.lbl_summary.setWordWrap(True); cgl.addWidget(self.lbl_summary)
        rl.addWidget(cg)
        mid = QHBoxLayout()
        mg = QGroupBox("TRANSITION MATRIX (base weights)"); mgl = QVBoxLayout(mg)
        self.matrix = _MatrixView(); mgl.addWidget(self.matrix)
        mid.addWidget(mg, 2)
        tg = QGroupBox("DECISION TRACE"); tgl = QVBoxLayout(tg)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Out step", "Source", "p", "u", "Why"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_trace_selected)
        tgl.addWidget(self.table)
        mid.addWidget(tg, 3)
        rl.addLayout(mid, 1)
        eg = QGroupBox("EXPLANATION"); egl = QVBoxLayout(eg)
        self.explain = QTextBrowser(); self.explain.setMinimumHeight(110); egl.addWidget(self.explain)
        rl.addWidget(eg)
        split.addWidget(right)
        split.setStretchFactor(0, 0); split.setStretchFactor(1, 1)

        btns = QHBoxLayout()
        self.btn_preview = QPushButton("Preview"); self.btn_preview.clicked.connect(self.preview)
        self.btn_apply = QPushButton("Apply to sequence"); self.btn_apply.setObjectName("markovApply")
        self.btn_apply.clicked.connect(self.apply)
        self.btn_undo = QPushButton("Undo last apply"); self.btn_undo.clicked.connect(self.undo_last)
        self.btn_reset = QPushButton("Reset defaults"); self.btn_reset.clicked.connect(lambda: self._load_spec({}))
        self.btn_close = QPushButton("Close"); self.btn_close.clicked.connect(self.close)
        self.lbl_status = QLabel(""); self.lbl_status.setWordWrap(True)
        for b in (self.btn_preview, self.btn_apply, self.btn_undo, self.btn_reset):
            btns.addWidget(b)
        btns.addWidget(self.lbl_status, 1); btns.addWidget(self.btn_close)
        root.addLayout(btns)

        for w in (self.combo_states, self.combo_advance, self.combo_decay, self.combo_lane, self.combo_seed):
            w.currentIndexChanged.connect(self._changed)
        for w in [self.spin_locality, self.spin_self, self.spin_euclid, self.spin_pulses, self.spin_fractal, self.spin_k] + self.spin_c:
            w.valueChanged.connect(self._changed)
        for w in [self.chk_wrap, self.chk_follow] + list(self.chk_lanes.values()):
            w.toggled.connect(self._changed)
        self.edit_seed.textChanged.connect(self._changed)

    # ---------- spec <-> widgets ----------
    def _load_spec(self, spec):
        s = mr.normalize_spec(spec)
        self._loading = True
        try:
            self.combo_states.setCurrentIndex(self.combo_states.findData(s["states"]))
            self.combo_advance.setCurrentIndex(self.combo_advance.findData(s["advance"]))
            self.combo_decay.setCurrentIndex(self.combo_decay.findData(s["decay"]))
            self.combo_lane.setCurrentIndex(self.combo_lane.findData(s["input_lane"]))
            self.combo_seed.setCurrentIndex(self.combo_seed.findData(s["seed_source"]))
            self.spin_locality.setValue(s["locality"]); self.spin_self.setValue(s["self_weight"])
            self.spin_euclid.setValue(s["euclid_bonus"]); self.spin_pulses.setValue(s["euclid_pulses"])
            self.spin_fractal.setValue(s["fractal_bonus"]); self.spin_k.setValue(s["coupling"])
            for sp, c in zip(self.spin_c, s["coefficients"]):
                sp.setValue(c)
            self.chk_wrap.setChecked(s["wrap"]); self.chk_follow.setChecked(s["follow_canonicals"])
            self.edit_seed.setText(s["custom_seed"])
            for ln, c in self.chk_lanes.items():
                c.setChecked(ln in s["lanes"])
        finally:
            self._loading = False
        self._changed()

    def spec(self) -> dict:
        return mr.normalize_spec({
            "states": self.combo_states.currentData(), "advance": self.combo_advance.currentData(),
            "decay": self.combo_decay.currentData(), "input_lane": self.combo_lane.currentData(),
            "seed_source": self.combo_seed.currentData(), "locality": self.spin_locality.value(),
            "self_weight": self.spin_self.value(), "euclid_bonus": self.spin_euclid.value(),
            "euclid_pulses": self.spin_pulses.value(), "fractal_bonus": self.spin_fractal.value(),
            "coupling": self.spin_k.value(), "coefficients": [s.value() for s in self.spin_c],
            "wrap": self.chk_wrap.isChecked(), "follow_canonicals": self.chk_follow.isChecked(),
            "custom_seed": self.edit_seed.text(),
            "lanes": [ln for ln, c in self.chk_lanes.items() if c.isChecked()],
        })

    def _changed(self, *_):
        if self._loading:
            return
        spec = self.spec()
        try:
            self.host.markov_resampler_spec = spec
            self.host._markov_resampler_status_refresh()
        except Exception:
            pass
        self.edit_seed.setEnabled(spec["seed_source"] == "custom")
        c = spec["coefficients"]
        self.lbl_expr.setText(f"f(y) = {c[0]:g} + {c[1]:g}·y + {c[2]:g}·y² + {c[3]:g}·y³   k = {spec['coupling']:g}")
        self._schedule()

    def _schedule(self):
        self._timer.start()

    # ---------- host context ----------
    def _context(self):
        h = self.host
        name, seq, mem = h._selected_sequence_context()
        try:
            active = set(h._active_engine_sources())
        except Exception:
            active = set()
        levels = dict(getattr(h, "canonical_engine_levels", {}) or {})
        try:
            numeric = h.get_numeric_seed()
        except Exception:
            numeric = 0
        return name, seq, mem, active, levels, numeric, getattr(h, "_rand_instance_seed", None)

    def _effective(self):
        name, seq, mem, active, levels, numeric, token = self._context()
        eff, notes = mr.canonical_adjust(self.spec(), active, levels)
        use_active = active if eff["follow_canonicals"] else set()
        seed = mr.chain_seed(eff, numeric_seed=numeric, instrument=name, sequence=seq,
                             rand_token=token, active=use_active)
        return name, seq, mem, eff, notes, seed

    # ---------- actions ----------
    def preview(self):
        if self.host is None:
            return None
        try:
            name, seq, mem, eff, notes, seed = self._effective()
        except Exception as exc:
            self.lbl_status.setText(f"No sequence available: {exc}")
            return None
        lanes = mr.lanes_from_mem(mem)
        self.lbl_source.setText(f"{name} · sequence {seq} · {len(lanes['steps'])} steps · "
                                f"{sum(1 for s in lanes['steps'] if s)} active")
        self.lbl_canon.setText("\n".join(notes))
        self.curve.set_data(eff, [mr.lane_value(lanes, eff["input_lane"], i) for i in mr.state_positions(lanes, eff)])
        pos, rows = mr.transition_matrix(lanes, eff)
        self.matrix.set_data(pos, rows)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._result = mr.resample(mem, eff, seed=seed)
        except Exception as exc:
            self._result = None
            self.compare.set_result(None); self.table.setRowCount(0)
            self.lbl_summary.setText(f"Cannot resample: {exc}")
            self.btn_apply.setEnabled(False)
            return None
        finally:
            QApplication.restoreOverrideCursor()
        r = self._result
        self.btn_apply.setEnabled(bool(r["spec"]["lanes"]))
        self.compare.set_result(r)
        self.lbl_summary.setText(
            f"{r['changed_steps']} of {len(r['positions'])} output steps take another step's contents · "
            f"seed “{seed}” · model {r['model_fingerprint'][:12]} · lanes: {', '.join(r['spec']['lanes']) or 'none'}")
        self.table.setRowCount(len(r["traces"]))
        for row, (t, out_i, src_i) in enumerate(zip(r["traces"], r["positions"], r["sources"])):
            chosen = next(c for c in t["transition_candidates"] if c["state"] == t["selected_state"])
            vals = (str(out_i + 1), str(src_i + 1), f"{chosen['probability']:.3f}", f"{t['sample_coordinate']:.4f}",
                    "kept" if out_i == src_i else f"moved from step {src_i + 1}")
            for col, v in enumerate(vals):
                self.table.setItem(row, col, QTableWidgetItem(v))
        self._explain_text(None)
        return r

    def apply(self):
        r = self.preview()
        if not r:
            return False
        h = self.host
        name, seq, mem = h._selected_sequence_context()
        try:
            h._push_undo(f"Markov resample sequence {seq}")
        except Exception:
            pass
        mr.apply_to_mem(mem, r)
        for fn in ("_sequence_action_finish",):
            try:
                getattr(h, fn)("markov resample")
            except Exception:
                pass
        try:
            h.reload_active_instrument_sequencer_ui()
        except Exception:
            pass
        self._last_applied = (name, seq)
        self.lbl_status.setText(f"Applied to {name} · sequence {seq}: {r['changed_steps']} steps moved. Ctrl+Z or "
                                "“Undo last apply” restores the previous sequence.")
        try:
            h._markov_resampler_status_refresh()
        except Exception:
            pass
        self._schedule()
        return True

    def undo_last(self):
        h = self.host
        stack = getattr(h, "_undo_stack", []) or []
        if not stack or not str(stack[-1][0]).startswith("Markov resample"):
            self.lbl_status.setText("The most recent undo step is not a Markov resample — nothing undone.")
            return False
        try:
            h._do_undo()
        except Exception as exc:
            self.lbl_status.setText(f"Undo failed: {exc}")
            return False
        self.lbl_status.setText("Previous sequence restored.")
        self._schedule()
        return True

    # ---------- explanations ----------
    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.Enter) and obj in self._explain_for:
            self._explain_text(self._explain_for[obj])
        return super().eventFilter(obj, event)

    def _explain_text(self, key):
        parts = []
        if key:
            parts.append(f"<b>{key.replace('_', ' ').title()}</b> — {mr.EXPLAIN.get(key, '')}")
        if self._result:
            s = self._result["spec"]
            parts.append(
                f"<b>Effective model</b>: {len(self._result['positions'])} states ({s['states'].replace('_', ' ')}), "
                f"advance {s['advance']:+d}, p = {s['locality']:g}, {s['decay']} decay, self ×{s['self_weight']:g}, "
                f"Euclid +{s['euclid_bonus']:g} on n/{s['euclid_pulses']}, fractal +{s['fractal_bonus']:g}, "
                f"input lane {s['input_lane']}, k = {s['coupling']:g}.")
        if self.lbl_canon.text():
            parts.append("<b>Canonicals</b>: " + self.lbl_canon.text().replace("\n", " · "))
        self.explain.setHtml("<br><br>".join(parts))

    def _on_trace_selected(self):
        rows = sorted({i.row() for i in self.table.selectedItems()})
        if not rows or not self._result:
            return
        k = rows[0]
        t = self._result["traces"][k]
        out_i = self._result["positions"][k]
        self.compare.set_result(self._result, mark=out_i)
        self.matrix.set_data(*mr.transition_matrix(self._result["before"], self._result["spec"]),
                             mark=int(t["source_state"].split(":", 1)[1]))
        self.explain.setPlainText(mr.explain_trace(t))


def open_window(host=None):
    win = getattr(host, "_markov_resampler_window", None) if host is not None else None
    if win is None:
        win = MarkovResamplerWindow(host)
        if host is not None:
            try:
                host._markov_resampler_window = win
            except Exception:
                pass
    win.show(); win.raise_(); win.activateWindow()
    win.preview()
    return win
