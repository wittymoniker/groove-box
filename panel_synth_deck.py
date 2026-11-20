"""Panel-synth row + inline Global Sidechain panel for the main window.

GROOVEBOX_R123_PANEL_SYNTH_ROW_20261119

* ``build_panel_synth_row(app, extra_widgets)`` — "LOCAL ▸ PANEL SYNTHS · EDITOR MODES": its own
  full-width row with the selected-instrument strip (colour, sequence, live step lane, Trigger Note),
  the four enlarged editor launchers (EDIT SYNTH · WRITE SCRIPT · PATCH MODULAR · CALC DOMAIN) as
  cards with live data about the selected instrument, and the other editor modes (Instrument
  Designer, Markov Resampler, Patch Motion, Sidechain routing, Clip editor, per-sequence tools).
  Expand mode (default ON) opens an editor as a scrollable frame inside the row; otherwise as a window.
* ``build_sidechain_panel(app)`` — "GLOBAL ▸ SIDECHAIN": the routing that used to live only in the
  modal dialog, as a panel: enable, signed global amount, source, attack / release, selected
  instrument local offset (inherit or own), effective amount, a gain-response curve and the list of
  local offsets. Writes the same ``app.sidechain_state`` schema the dialog and the renderer use.

Pure UI glue: it never changes render math. Every data read is guarded so a missing store only
shows "—".
"""

from __future__ import annotations

import copy
import math

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QCheckBox,
    QComboBox, QSlider, QSizePolicy, QFrame, QListWidget, QBoxLayout,
)

MARKER = "GROOVEBOX_R123_PANEL_SYNTH_ROW_20261119"
SIDECHAIN_SOURCES = ("master", "playlist", "kick", "selected instrument")
_OLD_DEFAULT = 0.1975807343

CARD_DEFS = (
    # key, button attr, accent, subtitle
    ("synth", "btn_edit_synth", "#3bd18a", "oscillator · Meum AM/FM/PM · wavetable"),
    ("script", "btn_script_inst", "#5aa9ff", "evaluate_wave(x, y, z, t) · OT equivalents"),
    ("patch", "btn_view_patchbay", "#e6bd45", "operator cables · mod routes · motion"),
    ("domain", "btn_domain_eq", "#c58cff", "time / space domains · logic · equations"),
)

MODE_DEFS = (
    # caption, app method, tooltip
    ("🎹 Instrument Designer", "_open_instrument_designer", "Percussion / pad / key patches with TONE · MOTION · BODY macros."),
    ("⛓ Markov Resampler", "_open_markov_resampler", "Polynomial-weighted, canonical-aware resampling of the selected sequence."),
    ("⌘ Patch Motion", "_open_patch_motion_matrix", "Canonical patch rate / direction / depth and the 8×8 sequence matrix."),
    ("↯ Sidechain Routing", "_open_canonical_sidechain_dialog", "Full global + per-instrument sidechain routing dialog."),
    ("✂ Clip Editor", "_r32_open_clip_editor", "Edit the selected clip on the deck."),
)


# --------------------------------------------------------------------------- data helpers
def _name(app):
    try:
        return str(app._current_instrument_name())
    except Exception:
        try:
            return str(app.instrument_selector_dropdown.currentText())
        except Exception:
            return ""


def _mem(app, name):
    try:
        m = app._current_sequence_mem(name)
        return m if isinstance(m, dict) else {}
    except Exception:
        return {}


def _seq(app, name):
    try:
        return int(app._current_sequence_index(name))
    except Exception:
        return 1


def _color(app, name):
    for fn in ("_instrument_color_for", "instrument_color"):
        f = getattr(app, fn, None)
        if callable(f):
            try:
                c = f(name)
                return QColor(c) if not isinstance(c, QColor) else c
            except Exception:
                pass
    try:
        names = list(getattr(app, "instrument_names_48", []) or [])
        i = names.index(name) if name in names else 0
    except Exception:
        i = 0
    return QColor.fromHsvF(((i * 0.6180339887) % 1.0), 0.62, 0.95)


def card_data(app, key, name=None):
    """One-line live facts for a launcher card (pure read)."""
    name = name if name is not None else _name(app)
    try:
        if key == "synth":
            ps = (getattr(app, "instrument_param_state", {}) or {}).get(name) or {}
            mem = _mem(app, name)
            panel = (mem.get("panels") or {}).get("synth") if isinstance(mem.get("panels"), dict) else None
            hf = ps.get("harmonic_freq")
            tr = ps.get("tuning_ratio")
            parts = []
            if isinstance(hf, (int, float)):
                parts.append(f"harmonic {float(hf):.2f} Hz")
            if isinstance(tr, (int, float)):
                parts.append(f"ratio {float(tr):.4f}")
            parts.append(f"{len(ps)} params")
            if isinstance(panel, dict) and panel:
                parts.append(f"per-seq panel {len(panel)} keys")
            cen = ps.get("reconvolve_spectral_centroid")
            if isinstance(cen, (int, float)):
                parts.append(f"centroid {float(cen):.0f} Hz")
            return " · ".join(parts)
        if key == "script":
            src = str((getattr(app, "instrument_scripts", {}) or {}).get(name) or "")
            if not src.strip():
                return "no script — the operator rules play"
            lines = [l for l in src.splitlines() if l.strip()]
            code = [l for l in lines if not l.lstrip().startswith("#")]
            ot = src.count("_equiv(")
            gen = "generated" if "# --- GENERATED" in src else "user"
            ev = "evaluate_wave ✓" if "def evaluate_wave" in src else "no evaluate_wave"
            return f"{len(code)} code lines · {ot} OT-equivalent calls · {ev} · {gen}"
        if key == "patch":
            routes = (getattr(app, "patch_motion_state", {}) or {}).get("routes") or []
            cables = 0
            dlg = getattr(app, "patch_bay_dialog", None)
            if dlg is not None:
                try:
                    for lw in dlg.findChildren(QListWidget):
                        for i in range(lw.count()):
                            t = lw.item(i).text()
                            if "==>" in t and (not name or name in t):
                                cables += 1
                except RuntimeError:
                    pass
            mod_sc = 0
            try:
                for r in routes:
                    if isinstance(r, dict) and "sidechain" in str(r).lower():
                        mod_sc += 1
            except Exception:
                pass
            return f"{cables} cables on this instrument · {len(routes)} motion routes · {mod_sc} sidechain routes"
        if key == "domain":
            eng = getattr(app, "domain_eq_engine", None)
            doms = list(getattr(eng, "domains", []) or []) if eng is not None else []
            if not doms:
                return "no domains — flat"
            axes = sorted({str(d.get("axis", "?")) for d in doms if isinstance(d, dict)})
            w = sum(float(d.get("weight", 1.0) or 0.0) for d in doms if isinstance(d, dict))
            first = str(doms[0].get("name", "")) if isinstance(doms[0], dict) else ""
            return f"{len(doms)} domains · axes {', '.join(axes)} · Σweight {w:.2f} · first “{first[:28]}”"
    except Exception as exc:  # pragma: no cover - defensive UI
        return f"— ({type(exc).__name__})"
    return "—"


def instrument_facts(app, name=None):
    name = name if name is not None else _name(app)
    mem = _mem(app, name)
    steps = list(mem.get("steps") or [])
    amps = list(mem.get("amplitudes") or [])
    n = int(mem.get("pattern_length", len(steps)) or len(steps) or 0)
    on = sum(1 for s in steps[:n] if s)
    owner = "user" if mem.get("user_owned") else ("canonical" if str(mem.get("canonical_owner") or "").startswith("canonical:") else "default")
    pk = max((float(a) for a in amps[:n] if isinstance(a, (int, float))), default=0.0)
    return {"name": name, "sequence": _seq(app, name), "length": n, "active": on, "owner": owner,
            "peak": pk, "steps": steps[:n], "amplitudes": amps[:n]}


# --------------------------------------------------------------------------- small painted views
class StepLane(QWidget):
    """Gate/amplitude bars of the selected sequence (read-only)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps, self.amps, self.color = [], [], QColor("#5aa9ff")
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, steps, amps, color):
        self.steps, self.amps, self.color = list(steps), list(amps), QColor(color)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.fillRect(r, QColor("#0d141d"))
        n = max(1, len(self.steps))
        w = r.width() / n
        for i in range(n):
            on = bool(self.steps[i]) if i < len(self.steps) else False
            a = float(self.amps[i]) if i < len(self.amps) and isinstance(self.amps[i], (int, float)) else 0.0
            h = (r.height() - 4) * (max(0.12, min(1.0, a)) if on else 0.08)
            col = QColor(self.color) if on else QColor("#2a3646")
            if i % 4 == 0:
                p.fillRect(QRectF(r.left() + i * w, r.top(), 1, r.height()), QColor("#1f2c3b"))
            p.fillRect(QRectF(r.left() + i * w + 1, r.bottom() - h - 1, max(1.0, w - 2), h), col)
        p.end()


class SidechainCurve(QWidget):
    """Gain the renderer applies: 1 − amount·env, env from attack/release on a 4-pulse detector."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.amount, self.attack_ms, self.release_ms, self.enabled = 0.0, 5.0, 120.0, True
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_params(self, amount, attack_ms, release_ms, enabled):
        self.amount, self.attack_ms, self.release_ms, self.enabled = float(amount), float(attack_ms), float(release_ms), bool(enabled)
        self.update()

    @staticmethod
    def gain_curve(amount, attack_ms, release_ms, points=240, span_s=2.0, pulses=4):
        """Same one-pole detector + clamp as the renderer (sidechain block in the mixdown)."""
        sr = points / span_s
        a = math.exp(-1.0 / max(1.0, max(0.001, attack_ms / 1000.0) * sr))
        rl = math.exp(-1.0 / max(1.0, max(0.005, release_ms / 1000.0) * sr))
        prev, out = 0.0, []
        beat = points / max(1, pulses)
        for i in range(points):
            ph = (i % beat) / beat
            src = 1.0 if ph < 0.06 else 0.0
            c = a if src > prev else rl
            prev = c * prev + (1.0 - c) * src
            out.append(max(0.05, min(2.0, 1.0 - amount * min(1.0, prev))))
        return out

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.fillRect(r, QColor("#14110a"))
        y_of = lambda g: r.bottom() - (g / 2.0) * r.height()
        p.setPen(QPen(QColor("#4d4220"), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(r.left(), y_of(1.0)), QPointF(r.right(), y_of(1.0)))
        g = self.gain_curve(self.amount if self.enabled else 0.0, self.attack_ms, self.release_ms)
        path = QPainterPath()
        for i, v in enumerate(g):
            x = r.left() + r.width() * i / (len(g) - 1)
            (path.moveTo if i == 0 else path.lineTo)(QPointF(x, y_of(v)))
        p.setPen(QPen(QColor("#ffd85a") if self.enabled else QColor("#6b6040"), 2))
        p.drawPath(path)
        p.setPen(QColor("#e8d8a0"))
        f = QFont(p.font()); f.setPointSizeF(7.5); p.setFont(f)
        lo = min(g); hi = max(g)
        p.drawText(r.adjusted(6, 2, -6, -2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                   f"gain {lo:.2f}…{hi:.2f} · {'duck' if self.amount > 0 else ('expand' if self.amount < 0 else 'flat')}")
        p.drawText(r.adjusted(6, 2, -6, -2), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, "1.0")
        p.end()


# --------------------------------------------------------------------------- panel synth row
def _style_launcher(btn, accent):
    btn.setMinimumSize(300, 128)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    btn.setStyleSheet(
        f"QPushButton {{ background-color:#101820; color:{accent}; border:3px solid {accent}; border-radius:12px;"
        f" padding:10px; font-weight:1000; font-size:17pt; }}"
        f" QPushButton:hover {{ background-color:#1b2a36; }}"
        f" QPushButton:pressed {{ background-color:{accent}; color:#0b0d12; }}"
    )


class _SquareHost(QWidget):
    """Holds one child as a large square on the left half of the panel.

    GROOVEBOX_R123_PANEL_SQUARE_FIT_20261119: side = min(half the panel width, the main window height
    minus its chrome), so the whole square — editor tabs, page and its scroll bars — fits on one
    screen instead of becoming a 2,000+ px column you have to scroll through. The right column takes the
    rest of the width.
    """

    MIN_SIDE = 360

    def __init__(self, child, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(child)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(560, 560)
        self._watched = []

    def _viewport(self):
        from PyQt6.QtWidgets import QAbstractScrollArea
        w, best = self.parentWidget(), None
        while w is not None:
            if isinstance(w, QAbstractScrollArea):
                best = w
            w = w.parentWidget()
        return best.viewport() if best is not None else None

    def _watch(self):
        for w in (self.parentWidget(), self.window()):
            if w is not None and w not in self._watched:
                w.installEventFilter(self); self._watched.append(w)

    def fit(self):
        par = self.parentWidget()
        if par is None:
            return
        half = max(self.MIN_SIDE, (par.width() - 30) // 2)
        # Cap by the main window height (the workspace pane itself is only one split of it, often < 500 px).
        win = self.window()
        cap = (win.height() - 160) if win is not None and win.height() > 400 else half
        side = int(max(self.MIN_SIDE, min(half, cap)))
        if self.width() != side or self.height() != side:
            self.setFixedSize(side, side)

    def showEvent(self, ev):
        super().showEvent(ev)
        self._watch(); self.fit()

    def eventFilter(self, obj, ev):
        from PyQt6.QtCore import QEvent
        if ev.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.fit)
        return False


class _CycleTile(QFrame):
    """One editor in the Expand overview: click opens it inside the square."""

    def __init__(self, app, key, accent, subtitle, parent=None):
        super().__init__(parent)
        self.app, self.key, self.accent = app, key, accent
        self.setObjectName("panelCycleTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Open {TITLE_FOR[key]} here (Expand mode)")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        v = QVBoxLayout(self); v.setContentsMargins(14, 12, 14, 12); v.setSpacing(6)
        self.head = QLabel(TITLE_FOR[key]); self.head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.head.setStyleSheet(f"color:{accent}; font-size:16pt; font-weight:900; background:transparent; border:0;")
        sub = QLabel(subtitle); sub.setAlignment(Qt.AlignmentFlag.AlignCenter); sub.setWordWrap(True)
        sub.setStyleSheet("color:#9fb4c8; font-size:9pt; background:transparent; border:0;")
        self.body = QLabel(""); self.body.setAlignment(Qt.AlignmentFlag.AlignCenter); self.body.setWordWrap(True)
        self.body.setStyleSheet("color:#e8f1fb; font-size:10pt; font-weight:700; background:transparent; border:0;")
        hint = QLabel("click to open here"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color:#6f8aa3; font-size:8pt; background:transparent; border:0;")
        for wdg in (self.head, sub, self.body, hint):
            wdg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        v.addStretch(1); v.addWidget(self.head); v.addWidget(sub); v.addWidget(self.body, 1); v.addWidget(hint); v.addStretch(1)
        self.set_active(False)

    def set_active(self, on):
        bw, bg = (3, "#13202e") if on else (1, "#0e1822")
        self.setStyleSheet(f"QFrame#panelCycleTile {{ background:{bg}; border:{bw}px solid {self.accent}; border-radius:10px; }}"
                           f" QFrame#panelCycleTile:hover {{ background:#1a2b3d; border:3px solid {self.accent}; }}")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            launch_card(self.app, self.key, force_embed=True)
        super().mouseReleaseEvent(e)


def build_panel_synth_row(app, extra_widgets=()):
    """Return the full-width panel-synth group. Reparents the existing launcher buttons."""
    group = QGroupBox("LOCAL ▸ PANEL SYNTHS · EDITOR MODES")
    group.setObjectName("panelSynthRow")
    group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    outer = QHBoxLayout()
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(10)

    # left: selected instrument strip
    left = QVBoxLayout(); left.setSpacing(5)
    app.lbl_panel_synth_instrument = QLabel("—")
    app.lbl_panel_synth_instrument.setStyleSheet("font-size:12pt; font-weight:900; color:#e8f1fb;")
    app.lbl_panel_synth_instrument.setWordWrap(True)
    app.lbl_panel_synth_facts = QLabel("—")
    app.lbl_panel_synth_facts.setWordWrap(True)
    app.lbl_panel_synth_facts.setStyleSheet("color:#b8c8da; font-size:8.5pt;")
    app.panel_synth_step_lane = StepLane()
    left.addWidget(app.lbl_panel_synth_instrument)
    left.addWidget(app.lbl_panel_synth_facts)
    left.addWidget(app.panel_synth_step_lane)
    trig = QHBoxLayout(); trig.setSpacing(6)
    for attr in ("trigger_note_freq", "btn_trigger_note"):
        w = getattr(app, attr, None)
        if w is not None:
            trig.addWidget(w, 2 if attr == "trigger_note_freq" else 0)
    left.addLayout(trig)
    left.addStretch(1)
    lw = QWidget(); lw.setLayout(left); lw.setMinimumWidth(320)
    outer.addWidget(lw, 2)

    # middle: four launcher cards
    cards = QGridLayout(); cards.setHorizontalSpacing(10); cards.setVerticalSpacing(4)
    app._panel_synth_card_labels = {}
    for col, (key, attr, accent, sub) in enumerate(CARD_DEFS):
        btn = getattr(app, attr, None)
        if btn is None:
            continue
        _style_launcher(btn, accent)
        cards.addWidget(btn, 0, col)
        s = QLabel(sub); s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet(f"color:{accent}; font-size:8pt; font-weight:800;")
        d = QLabel("—"); d.setAlignment(Qt.AlignmentFlag.AlignCenter); d.setWordWrap(True)
        d.setMinimumHeight(34)
        d.setStyleSheet("color:#dfe8f2; font-size:8.5pt; background:#0d141d; border:1px solid #263244; border-radius:5px; padding:3px;")
        cards.addWidget(s, 1, col); cards.addWidget(d, 2, col)
        cards.setColumnStretch(col, 1)
        app._panel_synth_card_labels[key] = d
    cw = QWidget(); cw.setLayout(cards)
    outer.addWidget(cw, 6)

    # right: other editor modes + per-sequence tools
    right = QGridLayout(); right.setHorizontalSpacing(6); right.setVerticalSpacing(6)
    hdr = QLabel("OTHER EDITOR MODES"); hdr.setStyleSheet("color:#9fb4c9; font-weight:900; font-size:8pt;")
    right.addWidget(hdr, 0, 0, 1, 2)
    app._panel_synth_mode_buttons = {}
    i = 0
    for caption, meth, tip in MODE_DEFS:
        fn = getattr(app, meth, None)
        if not callable(fn):
            continue
        b = QPushButton(caption); b.setToolTip(tip); b.setMinimumHeight(40)
        b.setStyleSheet("QPushButton { background:#162230; color:#d8e6f4; border:2px solid #3a5470; border-radius:7px;"
                        " padding:5px 8px; font-weight:900; } QPushButton:hover { background:#20334a; border-color:#6f97c0; }")
        b.clicked.connect(lambda _c=False, m=meth, cap=caption: _launch(app, m, cap))
        right.addWidget(b, 1 + i // 2, i % 2)
        app._panel_synth_mode_buttons[meth] = b
        i += 1
    r0 = 1 + (i + 1) // 2
    for j, w in enumerate(w for w in extra_widgets if w is not None):
        right.addWidget(w, r0 + j // 2, j % 2)
    rw = QWidget(); rw.setLayout(right); rw.setMinimumWidth(360)
    outer.addWidget(rw, 3)

    # Expand mode switch + the frame area under the row
    app.chk_panel_expand_mode = QCheckBox("Expand mode · open editors inside this panel")
    app.chk_panel_expand_mode.setToolTip("ON (default): launchers open their editor as a frame here. OFF: separate windows.")
    app.chk_panel_expand_mode.setChecked(expand_mode(app))
    app.chk_panel_expand_mode.toggled.connect(lambda on: set_expand_mode(app, on))
    right.addWidget(app.chk_panel_expand_mode, r0 + 2, 0, 1, 2)
    right.setRowStretch(r0 + 3, 1)
    # GROOVEBOX_R123_PANEL_SQUARE_20261119: the panel synth (expand frame area) is a large
    # square on the left half; strip, launcher cards and editor modes stretch over the right half.
    outer.setDirection(QBoxLayout.Direction.TopToBottom)
    wrap = QHBoxLayout(); wrap.setContentsMargins(8, 14, 8, 8); wrap.setSpacing(10)
    square = _SquareHost(build_expand_area(app))
    app.panel_synth_square = square
    wrap.addWidget(square, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    top = QWidget(); top.setLayout(outer)
    top.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    rcol = QVBoxLayout(); rcol.setSpacing(8); rcol.setContentsMargins(0, 0, 0, 0)
    rcol.addWidget(top)
    # GROOVEBOX_R123_MOD_PATH_ON_SIDES_20261119: no Mod Path field copy here — the Mod Path Bay stays on the
    # ring view's side rails next to the Multidim sphere (Reroute field left, Perspective field right).
    rcol.addStretch(1)
    rw2 = QWidget(); rw2.setLayout(rcol)
    wrap.addWidget(rw2, 1)
    group.setLayout(wrap)
    app.panel_synth_row_group = group
    _install_refresh(app)
    return group


def _launch(app, meth, caption):
    try:
        getattr(app, meth)()
    except Exception as exc:
        try:
            import error_report as _er
            _er.report(app, caption, exc)
        except Exception:
            pass


def refresh_panel_synth_row(app):
    try:
        f = instrument_facts(app)
        col = _color(app, f["name"])
        lab = getattr(app, "lbl_panel_synth_instrument", None)
        if lab is not None:
            lab.setText(f"● {f['name']} · sequence {f['sequence']}")
            lab.setStyleSheet(f"font-size:12pt; font-weight:900; color:{col.name()};")
        fl = getattr(app, "lbl_panel_synth_facts", None)
        if fl is not None:
            dens = (f["active"] / f["length"]) if f["length"] else 0.0
            fl.setText(f"{f['active']}/{f['length']} steps on ({dens:.0%}) · peak amp {f['peak']:.2f} · {f['owner']} pattern"
                       f" · sidechain {_effective_for(app, f['name']):+.3f}")
        lane = getattr(app, "panel_synth_step_lane", None)
        if lane is not None:
            lane.set_data(f["steps"], f["amplitudes"], col)
        for key, d in (getattr(app, "_panel_synth_card_labels", {}) or {}).items():
            d.setText(card_data(app, key, f["name"]))
    except Exception:
        pass


# --------------------------------------------------------------------------- sidechain panel
def _sc_state(app):
    st = copy.deepcopy(getattr(app, "sidechain_state", {}) or {})
    if not isinstance(st.get("global"), dict):
        st["global"] = {}
    if not isinstance(st.get("targets"), dict):
        st["targets"] = {}
    g = st["global"]
    g.setdefault("enabled", True)
    a = float(g.get("amount", 0.0) or 0.0)
    g["amount"] = 0.0 if abs(a - _OLD_DEFAULT) < 1e-9 else a
    g.setdefault("source", "master")
    g.setdefault("attack_ms", 5.0)
    g.setdefault("release_ms", 120.0)
    return st


def _effective_for(app, name):
    f = getattr(app, "_canonical_sidechain_amount_for", None)
    if callable(f):
        try:
            return float(f(name))
        except Exception:
            pass
    return 0.0


def _labelled_slider(lo, hi, val, tip):
    s = QSlider(Qt.Orientation.Horizontal); s.setRange(lo, hi); s.setValue(val); s.setToolTip(tip)
    s.setMaximumWidth(520)
    v = QLabel(""); v.setMinimumWidth(64); v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return s, v


def build_sidechain_panel(app):
    group = QGroupBox("GLOBAL ▸ SIDECHAIN · signed duck / expand")
    group.setObjectName("globalSidechainPanel")
    group.setStyleSheet(
        "QGroupBox#globalSidechainPanel { color:#ffe58a; border:2px solid #8c7330; border-radius:8px; margin-top:8px; padding-top:10px; font-weight:900; }"
        "QGroupBox#globalSidechainPanel::title { subcontrol-origin:margin; left:10px; padding:0 5px; }"
        "QLabel { color:#f3e3b0; } QCheckBox { color:#ffe58a; font-weight:800; }"
        "QSlider::groove:horizontal { background:#3a3218; height:5px; border-radius:2px; }"
        "QSlider::handle:horizontal { background:#e6bd45; width:13px; margin:-5px 0; border-radius:6px; }"
    )
    lay = QHBoxLayout(group); lay.setContentsMargins(8, 14, 8, 8); lay.setSpacing(12)
    ctl = QGridLayout(); ctl.setHorizontalSpacing(8); ctl.setVerticalSpacing(4)
    app.chk_sidechain_enabled = QCheckBox("Enable global sidechain")
    app.chk_sidechain_enabled.setToolTip("Turns the global contribution on/off. Per-instrument offsets still compose with it.")
    app.combo_sidechain_source = QComboBox(); app.combo_sidechain_source.addItems(list(SIDECHAIN_SOURCES))
    app.combo_sidechain_source.setToolTip("Detector: master mix, playlist sum, kick, or the selected instrument. A source never ducks itself.")
    app.slider_sidechain_amount, app.lbl_sidechain_amount = _labelled_slider(-1000, 1000, 0, "Signed global amount −1…+1. Positive ducks, negative expands (bounded gain 0.05…2.0).")
    app.slider_sidechain_attack, app.lbl_sidechain_attack = _labelled_slider(1, 250, 5, "Detector attack, 1–250 ms.")
    app.slider_sidechain_release, app.lbl_sidechain_release = _labelled_slider(5, 2000, 120, "Detector release, 5–2000 ms.")
    app.chk_sidechain_local_own = QCheckBox("Selected instrument has its own offset")
    app.chk_sidechain_local_own.setToolTip("OFF: inherits the global amount. ON: global + this local signed offset (clamped −1…+1).")
    app.slider_sidechain_local, app.lbl_sidechain_local = _labelled_slider(-1000, 1000, 0, "Local signed offset for the selected instrument, −1…+1.")
    rows = (
        (app.chk_sidechain_enabled, None, None),
        (QLabel("Source"), app.combo_sidechain_source, None),
        (QLabel("Global amount"), app.slider_sidechain_amount, app.lbl_sidechain_amount),
        (QLabel("Attack"), app.slider_sidechain_attack, app.lbl_sidechain_attack),
        (QLabel("Release"), app.slider_sidechain_release, app.lbl_sidechain_release),
        (app.chk_sidechain_local_own, None, None),
        (QLabel("Local offset"), app.slider_sidechain_local, app.lbl_sidechain_local),
    )
    for r, (a, b, c) in enumerate(rows):
        if b is None:
            ctl.addWidget(a, r, 0, 1, 3)
        else:
            ctl.addWidget(a, r, 0); ctl.addWidget(b, r, 1)
            if c is not None:
                ctl.addWidget(c, r, 2)
    ctl.setColumnStretch(1, 1)
    cw = QWidget(); cw.setLayout(ctl)
    lay.addWidget(cw, 3)

    info = QVBoxLayout(); info.setSpacing(4)
    app.sidechain_curve = SidechainCurve()
    app.lbl_sidechain_effective = QLabel("—"); app.lbl_sidechain_effective.setWordWrap(True)
    app.lbl_sidechain_effective.setStyleSheet("color:#ffe58a; font-weight:900;")
    app.lbl_sidechain_targets = QLabel("—"); app.lbl_sidechain_targets.setWordWrap(True)
    app.lbl_sidechain_targets.setStyleSheet("color:#d9c98f; font-size:8pt;")
    info.addWidget(app.sidechain_curve)
    info.addWidget(app.lbl_sidechain_effective)
    info.addWidget(app.lbl_sidechain_targets)
    canon = getattr(app, "lbl_sidechain_canonical", None)
    if canon is not None:
        info.addWidget(canon)
    btns = QHBoxLayout()
    b_full = QPushButton("Full routing…"); b_full.setToolTip("Open the routing dialog (every instrument).")
    b_full.clicked.connect(lambda: (_launch(app, "_open_canonical_sidechain_dialog", "Sidechain Routing"), sync_sidechain_panel(app)))
    b_reset = QPushButton("Reset sidechain"); b_reset.setToolTip("Global amount 0, attack 5 ms, release 120 ms, source master; local offsets removed.")
    b_reset.clicked.connect(lambda: reset_sidechain(app))
    btns.addWidget(b_full); btns.addWidget(b_reset); btns.addStretch(1)
    info.addLayout(btns)
    info.addStretch(1)
    iw = QWidget(); iw.setLayout(info)
    lay.addWidget(iw, 2)

    app._sidechain_panel_syncing = False
    for sig in (app.chk_sidechain_enabled.toggled, app.combo_sidechain_source.currentTextChanged,
                app.slider_sidechain_amount.valueChanged, app.slider_sidechain_attack.valueChanged,
                app.slider_sidechain_release.valueChanged, app.chk_sidechain_local_own.toggled,
                app.slider_sidechain_local.valueChanged):
        sig.connect(lambda *_: _sidechain_from_ui(app))
    app.global_sidechain_group = group
    sync_sidechain_panel(app)
    return group


def _write_state(app, st):
    st["schema"] = 1
    st["default_amount"] = 0.0
    st["inherit_global"] = True
    g = st["global"]
    st["effective_amounts"] = {
        str(n): max(-1.0, min(1.0, float(g.get("amount", 0.0)) + (0.0 if not isinstance(r, dict) or r.get("inherit_global", True) or not r.get("enabled", True) else float(r.get("amount", 0.0)))))
        for n, r in st["targets"].items()}
    app.sidechain_state = st
    try:
        app._sync_project_state()
    except Exception:
        pass


def _sidechain_from_ui(app):
    if getattr(app, "_sidechain_panel_syncing", False):
        return
    st = _sc_state(app)
    g = st["global"]
    g["enabled"] = bool(app.chk_sidechain_enabled.isChecked())
    g["source"] = str(app.combo_sidechain_source.currentText())
    g["amount"] = app.slider_sidechain_amount.value() / 1000.0
    g["attack_ms"] = float(app.slider_sidechain_attack.value())
    g["release_ms"] = float(app.slider_sidechain_release.value())
    name = _name(app)
    if name:
        if app.chk_sidechain_local_own.isChecked():
            st["targets"][name] = {"enabled": True, "inherit_global": False, "amount": app.slider_sidechain_local.value() / 1000.0,
                                   "source": g["source"], "attack_ms": g["attack_ms"], "release_ms": g["release_ms"]}
        else:
            st["targets"].pop(name, None)
    _write_state(app, st)
    _sidechain_labels(app, st)


def reset_sidechain(app):
    st = {"global": {"enabled": True, "amount": 0.0, "source": "master", "attack_ms": 5.0, "release_ms": 120.0}, "targets": {}}
    _write_state(app, st)
    sync_sidechain_panel(app)


def sync_sidechain_panel(app):
    """State → widgets (after load, undo, the dialog, or an instrument change)."""
    if not hasattr(app, "slider_sidechain_amount"):
        return
    st = _sc_state(app)
    g = st["global"]
    name = _name(app)
    rec = st["targets"].get(name) if name else None
    own = isinstance(rec, dict) and not rec.get("inherit_global", True)
    app._sidechain_panel_syncing = True
    try:
        app.chk_sidechain_enabled.setChecked(bool(g.get("enabled", True)))
        i = app.combo_sidechain_source.findText(str(g.get("source", "master")))
        app.combo_sidechain_source.setCurrentIndex(max(0, i))
        app.slider_sidechain_amount.setValue(int(round(float(g.get("amount", 0.0)) * 1000)))
        app.slider_sidechain_attack.setValue(int(round(float(g.get("attack_ms", 5.0)))))
        app.slider_sidechain_release.setValue(int(round(float(g.get("release_ms", 120.0)))))
        app.chk_sidechain_local_own.setText(f"{name or 'Selected instrument'} has its own offset")
        app.chk_sidechain_local_own.setChecked(bool(own))
        app.slider_sidechain_local.setValue(int(round(float(rec.get("amount", 0.0)) * 1000)) if own else 0)
        app.slider_sidechain_local.setEnabled(bool(own))
    finally:
        app._sidechain_panel_syncing = False
    _sidechain_labels(app, st)


def _sidechain_labels(app, st):
    g = st["global"]
    app.lbl_sidechain_amount.setText(f"{float(g.get('amount', 0.0)):+.3f}")
    app.lbl_sidechain_attack.setText(f"{float(g.get('attack_ms', 5.0)):.0f} ms")
    app.lbl_sidechain_release.setText(f"{float(g.get('release_ms', 120.0)):.0f} ms")
    app.lbl_sidechain_local.setText(f"{app.slider_sidechain_local.value() / 1000.0:+.3f}")
    app.slider_sidechain_local.setEnabled(app.chk_sidechain_local_own.isChecked())
    name = _name(app)
    eff = _effective_for(app, name)
    app.sidechain_curve.set_params(eff, float(g.get("attack_ms", 5.0)), float(g.get("release_ms", 120.0)), bool(g.get("enabled", True)) or abs(eff) > 0)
    mode = "ducks" if eff > 0 else ("expands" if eff < 0 else "passes unchanged")
    app.lbl_sidechain_effective.setText(f"{name or '—'}: effective {eff:+.3f} — {mode} on the {g.get('source', 'master')} detector")
    tg = st["targets"]
    if tg:
        items = sorted(tg.items())[:8]
        txt = " · ".join(f"{n} {float(r.get('amount', 0.0)):+.2f}" for n, r in items if isinstance(r, dict))
        more = f" (+{len(tg) - 8} more)" if len(tg) > 8 else ""
        app.lbl_sidechain_targets.setText(f"Local offsets: {txt}{more}")
    else:
        app.lbl_sidechain_targets.setText("Local offsets: none — every instrument inherits the global amount.")


# --------------------------------------------------------------------------- refresh plumbing
def _install_refresh(app):
    if getattr(app, "_panel_synth_refresh_timer", None) is not None:
        return
    t = QTimer(app); t.setInterval(900)

    def tick():
        try:
            grp = getattr(app, "panel_synth_row_group", None)
            if grp is not None and grp.isVisible():
                refresh_panel_synth_row(app)
            sc = getattr(app, "global_sidechain_group", None)
            if sc is not None and sc.isVisible():
                cur = (_name(app), repr(getattr(app, "sidechain_state", None)))
                if cur != getattr(app, "_sidechain_panel_seen", None):
                    app._sidechain_panel_seen = cur
                    sync_sidechain_panel(app)
        except RuntimeError:
            t.stop()

    t.timeout.connect(tick)
    t.start()
    app._panel_synth_refresh_timer = t
    dd = getattr(app, "instrument_selector_dropdown", None)
    if dd is not None:
        try:
            dd.currentTextChanged.connect(lambda *_: QTimer.singleShot(0, lambda: (refresh_panel_synth_row(app), sync_sidechain_panel(app), schedule_follow(app))))
        except Exception:
            pass
    QTimer.singleShot(0, lambda: refresh_panel_synth_row(app))


# --------------------------------------------------------------------------- Expand frames
# GROOVEBOX_R123_PANEL_EXPAND_FRAMES_20261119
# Expand mode (default ON, remembered): a launcher shows its editor as a frame inside the panel-synth row
# instead of a separate window. Until one is chosen the frame area cycles through the four editors' live
# summaries at 2.295 Hz; a chosen editor becomes a scrollable region. "Pop out" turns it back into its own
# window. Every editor follows the selected instrument (no relaunch needed).
CYCLE_HZ = 2.295
WINDOW_FOR = {"synth": ("synth_editor_window", "Synth Settings & Wavetable Interface"),
              "script": ("script_editor_window", "Instrument Script Editor"),
              "patch": ("patch_bay_dialog", "Advanced Modular Patch Bay & Visualizer"),
              "domain": ("domain_eq_dialog", "Domain Equation Editor")}
TITLE_FOR = {"synth": "EDIT SYNTH", "script": "WRITE SCRIPT", "patch": "PATCH MODULAR", "domain": "CALC DOMAIN"}


def expand_mode(app):
    v = getattr(app, "_panel_expand_mode", None)
    if v is None:
        try:
            from PyQt6.QtCore import QSettings
            v = str(QSettings("MathematiciansGroovebox", "UI").value("panel_expand_mode", "1")) not in ("0", "false", "False")
        except Exception:
            v = True
        app._panel_expand_mode = v
    return bool(v)


def set_expand_mode(app, on):
    app._panel_expand_mode = bool(on)
    try:
        from PyQt6.QtCore import QSettings
        QSettings("MathematiciansGroovebox", "UI").setValue("panel_expand_mode", "1" if on else "0")
    except Exception:
        pass
    area = getattr(app, "_panel_expand", None)
    if area is not None:
        area["frame"].setVisible(bool(on))
        if not on:
            for key in list(area["embedded"]):
                pop_out(app, key)


def build_expand_area(app):
    from PyQt6.QtWidgets import QStackedWidget, QScrollArea
    frame = QFrame(); frame.setObjectName("panelExpandFrame")
    frame.setStyleSheet("QFrame#panelExpandFrame { background:#0b121a; border:1px solid #2f4760; border-radius:8px; }")
    v = QVBoxLayout(frame); v.setContentsMargins(6, 6, 6, 6); v.setSpacing(4)
    head = QHBoxLayout()
    title = QLabel("EXPAND · cycling the four editors — pick one to open it here")
    title.setStyleSheet("color:#cfe3f7; font-weight:900;"); title.setWordWrap(True); title.setMinimumWidth(40)
    head.addWidget(title, 1)
    tabs = {}
    # GROOVEBOX_R124_EXPAND_TABS_ROW_20261119: the four editor tabs get their own row (equal widths). In
    # one row with the title they were squeezed out of a narrow square and PATCH MODULAR could not be hit.
    tab_row = QHBoxLayout(); tab_row.setSpacing(4)
    for key in ("synth", "script", "patch", "domain"):
        b = QPushButton(TITLE_FOR[key]); b.setCheckable(True); b.setMinimumHeight(28)
        b.setMinimumWidth(60)
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b.setStyleSheet("QPushButton { background:#142030; color:#cfe3f7; border:1px solid #3a5470; border-radius:5px; padding:3px 9px; font-weight:900; }"
                        " QPushButton:checked { background:#2e5f8a; color:#ffffff; border-color:#9fd0ff; }")
        b.clicked.connect(lambda _c=False, k=key: launch_card(app, k, force_embed=True))
        tab_row.addWidget(b, 1); tabs[key] = b
    b_cycle = QPushButton("⟳ Cycle"); b_cycle.setToolTip(f"Back to the {CYCLE_HZ} Hz overview of all four editors.")
    b_cycle.clicked.connect(lambda: show_cycle(app))
    b_pop = QPushButton("⧉ Pop out"); b_pop.setToolTip("Turn the shown editor into its own window (it still follows the selected instrument).")
    b_pop.clicked.connect(lambda: pop_out(app, (getattr(app, "_panel_expand", {}) or {}).get("current")))
    head.addWidget(b_cycle); head.addWidget(b_pop)
    v.addLayout(head)
    v.addLayout(tab_row)
    stack = QStackedWidget(); stack.setMinimumHeight(240)
    # GROOVEBOX_R123_PANEL_OVERVIEW_GRID_20261119: the overview is a 2×2 grid of the four editors (live
    # summary + click to open), with the cycle highlight moving across it, instead of one big text label.
    from PyQt6.QtWidgets import QGridLayout
    cyc = QWidget(); cyc.setObjectName("panelCycleGrid")
    grid = QGridLayout(cyc); grid.setContentsMargins(4, 4, 4, 4); grid.setSpacing(8)
    tiles = {}
    for i, (key, _attr, accent, subtitle) in enumerate(CARD_DEFS):
        t = _CycleTile(app, key, accent, subtitle); tiles[key] = t
        grid.addWidget(t, i // 2, i % 2)
    stack.addWidget(cyc)
    pages = {}
    for key in ("synth", "script", "patch", "domain"):
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame)
        stack.addWidget(sa); pages[key] = sa
    v.addWidget(stack, 1)
    timer = QTimer(frame); timer.setInterval(int(round(1000.0 / CYCLE_HZ)))
    area = {"frame": frame, "title": title, "stack": stack, "cycle": cyc, "tiles": tiles, "pages": pages, "tabs": tabs,
            "timer": timer, "i": 0, "current": None, "embedded": set()}
    app._panel_expand = area

    def tick():
        try:
            if area["current"] is not None or not frame.isVisible():
                return
            keys = [k for k, *_ in CARD_DEFS]
            k = keys[area["i"] % len(keys)]; area["i"] += 1
            for kk, t in tiles.items():
                t.set_active(kk == k)
                if kk == k or not t.body.text():
                    t.body.setText(card_data(app, kk))
            for kk, b in tabs.items():
                b.setChecked(kk == k)
        except RuntimeError:
            timer.stop()
    timer.timeout.connect(tick); timer.start()
    # GROOVEBOX_R123_NO_STRAY_WINDOW_20261119: the frame has no parent yet; setVisible(True) here made it a
    # top-level window for an instant, which the app-wide window-scroll filter then wrapped in a scroll
    # area (and kept wrapped after embedding), breaking hover and wheel inside the panel. Only hide it here.
    frame.setProperty("gb_no_auto_scroll", True)
    if not expand_mode(app):
        frame.hide()
    return frame


def show_cycle(app):
    area = getattr(app, "_panel_expand", None)
    if area is None:
        return
    area["current"] = None
    area["stack"].setCurrentWidget(area["cycle"])
    area["title"].setText(f"EXPAND · cycling the four editors at {CYCLE_HZ} Hz — pick one to open it here")


def _build_editor(app, key, embed):
    """Build (or rebuild) the editor for the selected instrument. Returns the window widget."""
    attr, title = WINDOW_FOR[key]
    if key == "domain":
        old = getattr(app, "domain_eq_dialog", None)
        app.open_domain_equation_editor()
        win = getattr(app, "domain_eq_dialog", None)
        if old is not None and old is not win:
            try:
                old.close(); old.deleteLater()
            except RuntimeError:
                pass
        return win
    old = getattr(app, attr, None)
    if old is not None:
        try:
            old.setProperty("r123Embedded", False)
            old.hide()          # spawn_floating_window rebuilds a hidden window
        except RuntimeError:
            setattr(app, attr, None)
    app._r123_embed_build = attr if embed else None
    try:
        app.spawn_floating_window(attr, title)
    finally:
        app._r123_embed_build = None
    return getattr(app, attr, None)


def _embed(app, key, win):
    area = getattr(app, "_panel_expand", None)
    if area is None or win is None:
        return None
    sa = area["pages"][key]
    prev = sa.takeWidget()
    if prev is not None and prev is not win:
        try:
            prev.deleteLater()
        except RuntimeError:
            pass
    win.setProperty("gb_no_auto_scroll", True)
    win.setWindowFlags(Qt.WindowType.Widget)
    win.setProperty("r123Embedded", True)
    sa.setWidget(win)
    win.show()
    area["embedded"].add(key)
    area["current"] = key
    area["stack"].setCurrentWidget(sa)
    for kk, b in area["tabs"].items():
        b.setChecked(kk == key)
    area["title"].setText(f"EXPAND · {TITLE_FOR[key]} · {_name(app)} — scroll inside; ⧉ Pop out for its own window")
    try:
        app._refresh_per_seq_styling()
    except Exception:
        pass
    return win


def show_embedded(app, attr):
    """Bring the Expand page of an embedded editor window (by app attribute) to the front."""
    area = getattr(app, "_panel_expand", None)
    for key, (a, _t) in WINDOW_FOR.items():
        if a == attr and area is not None and key in area["embedded"]:
            area["current"] = key
            area["stack"].setCurrentWidget(area["pages"][key])
            for kk, b in area["tabs"].items():
                b.setChecked(kk == key)
            return True
    return False


def pop_out(app, key):
    area = getattr(app, "_panel_expand", None)
    if area is None or key not in (area.get("embedded") or set()):
        return None
    sa = area["pages"][key]
    win = sa.takeWidget()
    area["embedded"].discard(key)
    if area.get("current") == key:
        show_cycle(app)
    if win is None:
        return None
    win.setProperty("r123Embedded", False)
    win.setParent(None)
    win.setWindowFlags(Qt.WindowType.Window)
    win.resize(max(640, win.sizeHint().width()), max(520, min(1000, win.sizeHint().height())))
    win.show(); win.raise_(); win.activateWindow()
    return win


def launch_card(app, key, force_embed=False):
    """Launcher action: Expand frame (default) or the editor's own window."""
    try:
        embed = force_embed or expand_mode(app)
        area = getattr(app, "_panel_expand", None)
        if embed and area is not None:
            sa = area["pages"][key]
            cur = sa.widget()
            if cur is not None and key in area["embedded"] and _built_for(app, key) == _name(app):
                area["current"] = key; area["stack"].setCurrentWidget(sa)
                for kk, b in area["tabs"].items():
                    b.setChecked(kk == key)
                return cur
            win = _build_editor(app, key, embed=True)
            _mark_built(app, key)
            return _embed(app, key, win)
        win = _build_editor(app, key, embed=False)
        _mark_built(app, key)
        return win
    except Exception as exc:
        try:
            import error_report as _er
            _er.report(app, TITLE_FOR.get(key, key), exc)
        except Exception:
            pass
        return None


def _built_for(app, key):
    return (getattr(app, "_panel_editor_built_for", {}) or {}).get(key)


def _mark_built(app, key):
    app.__dict__.setdefault("_panel_editor_built_for", {})[key] = _name(app)


# --------------------------------------------------------------------------- follow the selected instrument
def _script_dirty(app, key):
    """True when the open script editor holds text that differs from the stored script of its instrument."""
    if key != "script":
        return False
    win = getattr(app, "script_editor_window", None)
    owner = _built_for(app, "script")
    if win is None or not owner:
        return False
    try:
        from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit
        stored = str((getattr(app, "instrument_scripts", {}) or {}).get(owner) or "")
        for ed in win.findChildren(QPlainTextEdit) + win.findChildren(QTextEdit):
            t = ed.toPlainText()
            if "def evaluate_wave" in t or (stored and t.strip() and t.strip()[:40] == stored.strip()[:40]):
                return t.strip() != stored.strip()
    except RuntimeError:
        return False
    return False


def follow_instrument(app):
    """Bring every open editor to the selected instrument (debounced by the caller)."""
    name = _name(app)
    area = getattr(app, "_panel_expand", None)
    for key in ("synth", "script"):
        attr = WINDOW_FOR[key][0]
        win = getattr(app, attr, None)
        embedded = area is not None and key in area["embedded"]
        try:
            open_ = win is not None and (embedded or win.isVisible())
        except RuntimeError:
            open_ = False
        if not open_ or _built_for(app, key) == name:
            continue
        if _script_dirty(app, key):
            try:
                win.setWindowTitle(f"{WINDOW_FOR[key][1]} · UNSAVED for {_built_for(app, key)} — Save to follow {name}")
            except RuntimeError:
                pass
            continue
        geo = None
        if not embedded:
            try:
                geo = win.geometry()
            except RuntimeError:
                geo = None
        new = _build_editor(app, key, embed=embedded)
        _mark_built(app, key)
        if embedded:
            cur = area.get("current")
            _embed(app, key, new)
            if cur != key:
                if cur is None:
                    show_cycle(app)
                else:
                    area["current"] = cur; area["stack"].setCurrentWidget(area["pages"][cur])
        elif new is not None and geo is not None:
            new.setGeometry(geo)
    # Patch bay: global cables stay; point the source picker at the selected instrument.
    pb = getattr(app, "patch_bay_dialog", None)
    if pb is not None:
        try:
            for cb in pb.findChildren(QComboBox):
                i = cb.findText(f"{name} Out")
                if i >= 0:
                    cb.setCurrentIndex(i); break
        except RuntimeError:
            pass
    # Domain editor: reload its table from the (possibly per-sequence) live domains.
    dd = getattr(app, "domain_eq_dialog", None)
    if dd is not None:
        try:
            if hasattr(dd, "_reload_table"):
                dd._reload_table()
            t = dd.windowTitle().split(" · ")[0]
            dd.setWindowTitle(f"{t} · {name}")
        except RuntimeError:
            pass
    # Markov Resampler re-previews; Instrument Designer just names its target.
    mk = getattr(app, "_markov_resampler_window", None)
    if mk is not None:
        try:
            mk._schedule()
        except Exception:
            pass
    idd = getattr(app, "_instrument_designer_dialog", None)
    if idd is not None:
        try:
            idd.setWindowTitle(f"Instrument Designer · {name}")
        except RuntimeError:
            pass
    # Any other window that opts in.
    for w in list(getattr(app, "_instrument_follow_windows", []) or []):
        try:
            w.on_host_instrument_changed(name)
        except Exception:
            pass
    try:
        app._refresh_per_seq_styling()
    except Exception:
        pass
    if area is not None and area.get("current"):
        area["title"].setText(f"EXPAND · {TITLE_FOR[area['current']]} · {name} — scroll inside; ⧉ Pop out for its own window")


def schedule_follow(app):
    t = getattr(app, "_panel_follow_timer", None)
    if t is None:
        t = QTimer(app); t.setSingleShot(True); t.setInterval(220)
        t.timeout.connect(lambda: follow_instrument(app))
        app._panel_follow_timer = t
    t.start()
