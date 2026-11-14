"""step_automation.py — STEP_AUTOMATION_R7

Step Record also records AUTOMATION.  While STEP REC is armed, bindable inputs move automation
parameters (any numeric target of automation_bus) and every move is written as a breakpoint of a
user lane at the current step — so the take plays back in Play, Live Play and every export
(automation_bus.render_tick runs per row in the offline render).

Inputs (all rebindable in the "Bind" dialog; saved with the project):
  Arrow Up / Down     focus parameter  +/- one fine step (1/100 of its span)
  Arrow Left / Right  step cursor      -/+ one step (stopped transport)
  Ctrl (held)         coarse           x10 for arrows / wheel / numpad +/-
  Mouse wheel         focus parameter  (over the STEP AUTO pad, or anywhere with Alt held)
  Mouse X / Y         two parameters   (drag on the STEP AUTO pad)
  F1 … F12            focus select     F-key picks which parameter arrows / wheel / numpad drive
  Numpad 0 … 9        program memory   recall memory lane N at the step   (Ctrl+Numpad N = store)
  Numpad + / -        focus parameter  +/- ;  Numpad * / /  step cursor +/- ;  Numpad Enter = write
                      every bound value at the step and advance ;  Numpad .  clear focus point at step

Keys are only taken while armed and never from text fields, spin boxes, combo boxes or lists, so
typing and note keys are unaffected (note keys are letters/digits without the keypad flag).
State (bindings + program memory lanes) lives in ``app.step_automation_state`` — persisted by
project_schema like every other R32 section.
"""
from __future__ import annotations

import copy
import time

INPUTS = (["arrow_y", "arrow_x", "wheel", "mouse_x", "mouse_y", "ctrl"]
          + ["F%d" % i for i in range(1, 13)] + ["num%d" % i for i in range(10)])
CTRL_MODES = ("coarse", "fine", "write all")
CURSOR = "(step cursor)"
NONE = "(none)"
FINE = 0.01
COARSE = 10.0


def _ab():
    import automation_bus
    return automation_bus


def default_state(app=None):
    tg = []
    try:
        tg = list(_ab().targets(app))[:12] if app is not None else []
    except Exception:
        tg = []
    st = {"version": 1, "bind": {k: NONE for k in INPUTS}, "focus": "", "memories": {}}
    st["bind"]["arrow_x"] = CURSOR
    st["bind"]["ctrl"] = "coarse"
    for i, p in enumerate(tg):
        st["bind"]["F%d" % (i + 1)] = p
    if tg:
        st["focus"] = tg[0]
        st["bind"]["arrow_y"] = tg[0]
        st["bind"]["wheel"] = tg[0]
        st["bind"]["mouse_x"] = tg[0]
        st["bind"]["mouse_y"] = tg[1] if len(tg) > 1 else tg[0]
    for i in range(10):
        st["bind"]["num%d" % i] = "memory %d" % i
    return st


def state(app):
    st = getattr(app, "step_automation_state", None)
    if not isinstance(st, dict) or "bind" not in st:
        st = default_state(app)
        app.step_automation_state = st
    st.setdefault("bind", {})
    for k in INPUTS:
        st["bind"].setdefault(k, NONE)
    st.setdefault("memories", {})
    st.setdefault("focus", "")
    return st


# --------------------------------------------------------------------------- timing / steps
def _target(app):
    t = getattr(app, "_live_step_record_target", None)
    if t:
        return str(t[0]), int(t[1])
    try:
        n = str(app.instrument_selector_dropdown.currentText())
        return n, int(app._current_sequence_index(n))
    except Exception:
        return "", 1


def pattern_length(app):
    name, sid = _target(app)
    try:
        mem = (getattr(app, "instrument_sequence_banks", {}) or {}).get(name, {}).get(sid) or app._current_sequence_mem(name)
        return max(1, int(mem.get("pattern_length", len(mem.get("steps", [])) or 16) or 16))
    except Exception:
        return 16


def row_beats(app):
    for attr in ("spin_row_beats", "spin_playlist_beats"):
        w = getattr(app, attr, None)
        if w is not None:
            try:
                return max(0.25, min(64.0, float(w.value())))
            except Exception:
                pass
    return 4.0


def beats_per_step(app):
    return row_beats(app) / float(pattern_length(app))


def playhead_beat(app):
    try:
        sr = float(getattr(app, "play_sample_rate", 48000) or 48000)
        return float(getattr(app, "play_cursor", 0) or 0) / sr * float(app.spin_bpm.value()) / 60.0
    except Exception:
        return 0.0


def current_step(app):
    L = pattern_length(app)
    if getattr(app, "is_playing", False):
        return int(playhead_beat(app) / max(1e-9, beats_per_step(app))) % L
    return int(getattr(app, "_live_step_record_cursor", 0) or 0) % L


def move_cursor(app, delta):
    L = pattern_length(app)
    app._live_step_record_cursor = (int(getattr(app, "_live_step_record_cursor", 0) or 0) + int(delta)) % L
    _status(app, "STEP %d/%d" % (app._live_step_record_cursor + 1, L))
    return app._live_step_record_cursor


# --------------------------------------------------------------------------- values / lanes
SPAN_HINTS = {}          # RECORD_STRIP_R7: path -> (lo, hi) of the control that wrote it (multidim sliders)


def _span(app, path):
    ab = _ab()
    d, k = ab._resolve(app, path)
    if d is None:
        return None, None, None, None
    hint = SPAN_HINTS.get(path)
    if hint is None:
        lane = next((l for l in ab.lanes(app) if l.get("path") == path and l.get("span")), None)
        hint = lane.get("span") if lane else None
    if hint is not None:
        return d, k, float(hint[0]), float(hint[1])
    v = d.get(k, 0) or 0
    lo, hi = ab._span(k, float(v))
    return d, k, float(lo), float(hi)


def user_lane(app, path, create=True):
    """The user lane for ``path`` (amount 1.0, base = span centre -> value = lo + c·span)."""
    ab = _ab()
    lane = next((l for l in ab.lanes(app) if l.get("path") == path and l.get("owner") == "user"), None)
    if lane is None and create:
        d, k, lo, hi = _span(app, path)
        if d is None:
            return None
        lane = {"path": path, "amount": 1.0, "rate": row_beats(app), "owner": "user",
                "base": (lo + hi) / 2.0, "points": [], "step_recorded": True}
        if path in SPAN_HINTS:
            lane["span"] = [lo, hi]                         # playback maps c back through the same span
        ab.lanes(app).append(lane)
    return lane


def write_point(app, path, value, step=None):
    """Set the parameter live and record (step beat, normalised value) into its user lane."""
    d, k, lo, hi = _span(app, path)
    if d is None:
        return False
    v = max(lo, min(hi, float(value)))
    d[k] = int(round(v)) if isinstance(d.get(k), int) and not isinstance(d.get(k), bool) else v
    lane = user_lane(app, path)
    if lane is None:
        return False
    span_b = row_beats(app)
    lane["rate"] = span_b
    step = current_step(app) if step is None else int(step)
    beat = round(step * beats_per_step(app), 6)
    c = 0.0 if hi == lo else (v - lo) / (hi - lo)
    pts = {round(float(b), 6): float(cv) for b, cv in (lane.get("points") or []) if float(b) < span_b - 1e-9}
    pts[beat] = c                                           # a later move wins at the same step
    merged = sorted(pts.items())
    merged.append((span_b, merged[0][1]))                   # close the cycle: period = one row
    lane["points"] = [list(p) for p in merged]
    lane.pop("_cache", None)
    claim(app, path)
    app._step_auto_events = int(getattr(app, "_step_auto_events", 0) or 0) + 1
    return True


def canonical_alias(path):
    """'r32_fx_state/global/pkp' -> 'fx.global.pkp' (the canonical vector's variable name)."""
    parts = str(path).split("/")
    head = parts[0]
    if head.startswith("r32_"):
        head = head[4:]
    if head.endswith("_state"):
        head = head[:-6]
    return ".".join([head] + parts[1:])


def claim(app, path):
    """A step-recorded parameter is user-owned: the canonical engine stops moving it."""
    t = getattr(app, "_canonical_field_touched", None)
    if not isinstance(t, set):
        try:
            t = set(t or ())
        except Exception:
            t = set()
        try:
            app._canonical_field_touched = t
        except Exception:
            return
    t.add(path)
    t.add(canonical_alias(path))


def clear_point(app, path, step=None):
    lane = user_lane(app, path, create=False)
    if not lane:
        return False
    beat = round((current_step(app) if step is None else int(step)) * beats_per_step(app), 6)
    span_b = row_beats(app)
    pts = [p for p in (lane.get("points") or []) if abs(float(p[0]) - beat) > 1e-6 and float(p[0]) < span_b - 1e-9]
    if pts:
        pts.append([span_b, pts[0][1]])
    lane["points"] = pts
    return True


def nudge(app, path, units):
    d, k, lo, hi = _span(app, path)
    if d is None:
        return False
    v = float(d.get(k, 0) or 0) + float(units) * FINE * (hi - lo)
    ok = write_point(app, path, v)
    if ok:
        _status(app, "%s = %.4g · STEP %d" % (path.split("/")[-1], max(lo, min(hi, v)), current_step(app) + 1))
    return ok


def set_normalised(app, path, c):
    d, k, lo, hi = _span(app, path)
    if d is None:
        return False
    return write_point(app, path, lo + max(0.0, min(1.0, float(c))) * (hi - lo))


def bound_paths(app):
    b = state(app)["bind"]
    out = []
    for k in INPUTS:
        p = b.get(k)
        if p and p not in (NONE, CURSOR) and not str(p).startswith("memory") and p not in CTRL_MODES and p not in out:
            out.append(p)
    return out


def write_all(app):
    n = 0
    ab = _ab()
    for p in bound_paths(app):
        d, k = ab._resolve(app, p)
        if d is not None and write_point(app, p, d.get(k, 0) or 0):
            n += 1
    _status(app, "wrote %d bound value(s) · STEP %d" % (n, current_step(app) + 1))
    return n


def md_path(name, key):
    """RECORD_STRIP_R7: automation path of a multidim parameter of instrument ``name`` ('patch/x' allowed)."""
    return "instrument_param_state/%s/multidim/%s" % (str(name), str(key))


def record_param(app, path, value, lo, hi):
    """A user move of a control with span [lo, hi]: written at the current step while STEP REC is armed
    (and "record control moves" is on). Returns True when a point was written."""
    if not armed(app) or not state(app).get("capture_moves", True):
        return False
    if "/" in str(path).split("/multidim/")[0].replace("instrument_param_state/", "", 1):
        return False                                        # an instrument name with '/' cannot be a path
    SPAN_HINTS[path] = (float(lo), float(hi))
    ok = write_point(app, path, value)
    if ok:
        _status(app, "%s = %.4g · STEP %d" % (path.split("/")[-1], float(value), current_step(app) + 1))
    return ok


def clear_prefix(app, prefix):
    """Remove the user (step-recorded) lanes whose path starts with ``prefix``; returns how many."""
    ab = _ab()
    keep = [l for l in ab.lanes(app) if not (l.get("owner") == "user" and str(l.get("path", "")).startswith(prefix))]
    n = len(ab.lanes(app)) - len(keep)
    ab.lanes(app)[:] = keep
    return n


def take_summary(app, prefix=""):
    """(user lanes, lanes under prefix, points under prefix) for readouts."""
    ab = _ab()
    user = [l for l in ab.lanes(app) if l.get("owner") == "user"]
    mine = [l for l in user if str(l.get("path", "")).startswith(prefix)] if prefix else user
    return len(user), len(mine), sum(max(0, len(l.get("points") or []) - 1) for l in mine)


def take_map(app, prefix="", width=64):
    """One character per step of the pattern: '●' a recorded point at that step (any lane under prefix),
    '▲' the current step, '·' empty. Long patterns are folded to ``width`` cells."""
    ab = _ab()
    L = pattern_length(app)
    bps = beats_per_step(app)
    span_b = row_beats(app)
    hit = set()
    for l in ab.lanes(app):
        if l.get("owner") != "user" or (prefix and not str(l.get("path", "")).startswith(prefix)):
            continue
        for b, _c in (l.get("points") or []):
            if float(b) < span_b - 1e-9:
                hit.add(int(round(float(b) / max(1e-9, bps))) % L)
    cur = current_step(app)
    cells = min(L, max(1, int(width)))
    out = []
    for c in range(cells):
        lo, hi = c * L // cells, max(c * L // cells + 1, (c + 1) * L // cells)
        if lo <= cur < hi:
            out.append("▲")
        elif any(lo <= k < hi for k in hit):
            out.append("●")
        else:
            out.append("·")
    return "".join(out)


# --------------------------------------------------------------------------- program memory lanes
def store_memory(app, idx):
    ab = _ab()
    vals = {}
    for p in bound_paths(app):
        d, k = ab._resolve(app, p)
        if d is not None:
            vals[p] = float(d.get(k, 0) or 0)
    state(app)["memories"][str(int(idx))] = vals
    _status(app, "memory %d stored (%d values)" % (int(idx), len(vals)))
    return vals


def recall_memory(app, idx):
    vals = state(app)["memories"].get(str(int(idx))) or {}
    n = sum(1 for p, v in vals.items() if write_point(app, p, v))
    _status(app, ("memory %d → STEP %d (%d values)" % (int(idx), current_step(app) + 1, n)) if vals
             else "memory %d is empty (Ctrl+Numpad %d stores)" % (int(idx), int(idx)))
    return n


# --------------------------------------------------------------------------- input routing
def armed(app):
    return bool(getattr(app, "_live_step_record_enabled", False))


def _status(app, text):
    lbl = getattr(app, "lbl_live_step_record", None)
    if lbl is not None:
        try:
            lbl.setText("AUTO · " + str(text)[:60])
        except Exception:
            pass


def _ctrl_scale(app, mods_ctrl):
    mode = state(app)["bind"].get("ctrl", "coarse")
    if not mods_ctrl:
        return 1.0
    return COARSE if mode == "coarse" else (0.1 if mode == "fine" else 1.0)


def _focus(app):
    st = state(app)
    return st.get("focus") or st["bind"].get("arrow_y") or ""


def _drive(app, binding, units):
    if binding == CURSOR:
        return move_cursor(app, int(round(units)) or (1 if units > 0 else -1)) is not None
    if not binding or binding == NONE:
        return False
    return nudge(app, binding, units)


def handle_key(app, key_name, ctrl=False, keypad=False):
    """Route one key (Qt-independent names, for tests and the event filter). True = consumed."""
    st = state(app)
    b = st["bind"]
    sc = _ctrl_scale(app, ctrl)
    if key_name in ("Up", "Down") and not keypad:
        tgt = b.get("arrow_y")
        tgt = _focus(app) if tgt in (NONE, "") else tgt
        if tgt == CURSOR:
            return _drive(app, CURSOR, -1 if key_name == "Up" else 1)
        return _drive(app, tgt, sc if key_name == "Up" else -sc)
    if key_name in ("Left", "Right") and not keypad:
        return _drive(app, b.get("arrow_x"), (1 if key_name == "Right" else -1) * (1 if b.get("arrow_x") == CURSOR else sc))
    if key_name.startswith("F") and key_name[1:].isdigit():
        p = b.get(key_name)
        if p and p not in (NONE, CURSOR):
            st["focus"] = p
            _status(app, "focus %s (%s)" % (p.split("/")[-1], key_name))
            return True
        return False
    if keypad:
        if key_name.isdigit():
            idx = int(key_name)
            bind = str(b.get("num%d" % idx, ""))
            if bind.startswith("memory"):
                try:
                    mi = int(bind.split()[-1])
                except Exception:
                    mi = idx
                return bool(store_memory(app, mi) is not None) if ctrl else (recall_memory(app, mi) >= 0)
            if bind and bind not in (NONE, CURSOR):           # numpad key bound to a parameter: focus it
                st["focus"] = bind
                _status(app, "focus %s (Numpad %d)" % (bind.split("/")[-1], idx))
                return True
            return False
        if key_name in ("+", "-"):
            f = _focus(app)
            return bool(f) and nudge(app, f, sc if key_name == "+" else -sc)
        if key_name in ("*", "/"):
            move_cursor(app, 1 if key_name == "*" else -1)
            return True
        if key_name == "Enter":
            write_all(app)
            if not getattr(app, "is_playing", False):
                move_cursor(app, 1)
            return True
        if key_name == ".":
            f = _focus(app)
            return bool(f) and clear_point(app, f)
    if key_name == "Control" and b.get("ctrl") == "write all":
        write_all(app)
        return True
    return False


def handle_wheel(app, notches, ctrl=False):
    tgt = state(app)["bind"].get("wheel")
    tgt = _focus(app) if tgt in (NONE, "") else tgt
    return _drive(app, tgt, float(notches) * _ctrl_scale(app, ctrl))


def handle_pad(app, x01, y01):
    b = state(app)["bind"]
    n = 0
    for inp, val in (("mouse_x", x01), ("mouse_y", 1.0 - y01)):
        p = b.get(inp)
        if p and p not in (NONE, CURSOR) and set_normalised(app, p, val):
            n += 1
    if n:
        _status(app, "pad %.2f, %.2f · STEP %d" % (x01, 1.0 - y01, current_step(app) + 1))
    return n


# --------------------------------------------------------------------------- Qt glue
_KEYPAD_NAMES = {"Plus": "+", "Minus": "-", "Asterisk": "*", "Slash": "/", "Enter": "Enter", "Return": "Enter",
                 "Period": ".", "Comma": ".", "Delete": "."}


def _kv(x):
    return int(x.value) if hasattr(x, "value") else int(x)


def _qt_key_name(ev):
    from PyQt6.QtCore import Qt
    k = _kv(ev.key())
    for nm in ("Up", "Down", "Left", "Right", "Control"):
        if k == _kv(getattr(Qt.Key, "Key_" + nm)):
            return nm
    for i in range(1, 13):
        if k == _kv(getattr(Qt.Key, "Key_F%d" % i)):
            return "F%d" % i
    if _kv(Qt.Key.Key_0) <= k <= _kv(Qt.Key.Key_9):
        return str(k - _kv(Qt.Key.Key_0))
    for nm, out in _KEYPAD_NAMES.items():
        q = getattr(Qt.Key, "Key_" + nm, None)
        if q is not None and k == _kv(q):
            return out
    return ""


def _typing_widget(w):
    from PyQt6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox, QAbstractItemView
    return isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox, QAbstractItemView))


class _Filter:
    """QApplication event filter, active only while STEP REC is armed."""

    def __init__(self, app):
        from PyQt6.QtCore import QObject

        outer = self

        class F(QObject):
            def eventFilter(self, obj, ev):
                try:
                    return outer.filter(obj, ev)
                except Exception:
                    return False
        self.app = app
        from PyQt6.QtCore import QObject as _Q
        self.obj = F(app if isinstance(app, _Q) else None)

    def filter(self, obj, ev):
        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtWidgets import QApplication, QWidget
        app = self.app
        if not armed(app):
            return False
        t = ev.type()
        if t == QEvent.Type.KeyPress:
            if _typing_widget(QApplication.focusWidget()):
                return False
            mods = ev.modifiers()
            keypad = bool(mods & Qt.KeyboardModifier.KeypadModifier)
            name = _qt_key_name(ev)
            if not name:
                return False
            if name.isdigit() and not keypad:
                return False                                  # top-row digits stay note keys
            if name == "Control" and ev.isAutoRepeat():
                return False
            # Consumed on its first delivery, so it never propagates to a parent twice.
            return bool(handle_key(app, name, ctrl=bool(mods & Qt.KeyboardModifier.ControlModifier), keypad=keypad))
        if t == QEvent.Type.Wheel:
            mods = ev.modifiers()
            if not (mods & Qt.KeyboardModifier.AltModifier):
                return False                                  # plain wheel keeps scrolling windows
            d = ev.angleDelta()
            notches = (d.y() or d.x()) / 120.0
            return bool(handle_wheel(app, notches, ctrl=bool(mods & Qt.KeyboardModifier.ControlModifier)))
        return False


def install(app):
    from PyQt6.QtWidgets import QApplication
    if getattr(app, "_step_auto_filter", None) is not None:
        return app._step_auto_filter
    f = _Filter(app)
    qa = QApplication.instance()
    if qa is not None:
        qa.installEventFilter(f.obj)
    app._step_auto_filter = f
    state(app)
    return f


def make_pad(app):
    """The STEP AUTO pad: drag = mouse X/Y bindings, wheel = wheel binding (no Alt needed here)."""
    from PyQt6.QtWidgets import QFrame
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPainter, QColor, QPen

    class Pad(QFrame):
        def __init__(self):
            super().__init__()
            self.setFixedSize(64, 40)
            self.setToolTip("STEP AUTO pad — while STEP REC is armed: drag = Mouse X / Y parameters, wheel = "
                            "Wheel parameter (Ctrl = coarse). Elsewhere use Alt+wheel.")
            self.setProperty("gb_no_auto_scroll", True)
            self.pt = (0.5, 0.5)

        def _xy(self, ev):
            p = ev.position()
            return (max(0.0, min(1.0, p.x() / max(1, self.width()))), max(0.0, min(1.0, p.y() / max(1, self.height()))))

        def mousePressEvent(self, ev):
            self.mouseMoveEvent(ev)

        def mouseMoveEvent(self, ev):
            if not armed(app):
                return
            self.pt = self._xy(ev)
            handle_pad(app, *self.pt)
            self.update()

        def wheelEvent(self, ev):
            if not armed(app):
                return super().wheelEvent(ev)
            d = ev.angleDelta()
            handle_wheel(app, (d.y() or d.x()) / 120.0,
                         ctrl=bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier))
            ev.accept()

        def paintEvent(self, ev):
            qp = QPainter(self)
            on = armed(app)
            qp.fillRect(self.rect(), QColor("#2a1820" if on else "#1b2027"))
            qp.setPen(QPen(QColor("#ff8ba8" if on else "#55606c"), 1))
            qp.drawRect(self.rect().adjusted(0, 0, -1, -1))
            x = int(self.pt[0] * self.width()); y = int(self.pt[1] * self.height())
            qp.drawLine(x, 0, x, self.height()); qp.drawLine(0, y, self.width(), y)
            qp.end()
    return Pad()


def open_bind_dialog(app, parent=None):
    """Rebind every input; shows program memory lanes."""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QLabel, QComboBox, QPushButton,
                                 QHBoxLayout, QPlainTextEdit)
    st = state(app)
    try:
        tg = list(_ab().targets(app))
    except Exception:
        tg = []
    dlg = QDialog(parent or app)
    dlg.setWindowTitle("Step Record · automation bindings")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("While STEP REC is armed these inputs write automation at the current step "
                         "(user lanes; they play in Play, Live Play and exports)."))
    grid = QGridLayout()
    combos = {}
    labels = {"arrow_y": "Arrow Up / Down", "arrow_x": "Arrow Left / Right", "wheel": "Mouse wheel (pad / Alt+wheel)",
              "mouse_x": "Mouse X (pad drag)", "mouse_y": "Mouse Y (pad drag)", "ctrl": "Ctrl key"}
    for i, inp in enumerate(INPUTS):
        lab = labels.get(inp) or (("Numpad %s" % inp[3:]) if inp.startswith("num") else inp)
        grid.addWidget(QLabel(lab), i % 14, (i // 14) * 2)
        cb = QComboBox()
        if inp == "ctrl":
            cb.addItems(list(CTRL_MODES))
        elif inp.startswith("num"):
            cb.addItems(["memory %d" % k for k in range(10)] + [NONE] + tg)
        else:
            cb.addItems([NONE, CURSOR] + tg)
        cur = st["bind"].get(inp, NONE)
        if cb.findText(cur) < 0:
            cb.addItem(cur)
        cb.setCurrentText(cur)
        cb.setMaximumWidth(300)
        combos[inp] = cb
        grid.addWidget(cb, i % 14, (i // 14) * 2 + 1)
    lay.addLayout(grid)
    mem = QPlainTextEdit(); mem.setReadOnly(True); mem.setMaximumHeight(120)
    try:
        import typography
        typography.apply_console(mem)
    except Exception:
        pass

    def show_mem():
        lines = []
        for k in sorted(st["memories"], key=lambda x: int(x)):
            vals = st["memories"][k]
            lines.append("memory %s: " % k + ", ".join("%s=%.4g" % (p.split("/")[-1], v) for p, v in list(vals.items())[:8]))
        mem.setPlainText("\n".join(lines) or "No program memory yet — Ctrl+Numpad N stores the bound values in memory N.")
    show_mem()
    lay.addWidget(QLabel("Program memory lanes"))
    lay.addWidget(mem)
    row = QHBoxLayout()
    b_def = QPushButton("Defaults"); b_ok = QPushButton("Apply"); b_close = QPushButton("Close")
    row.addWidget(b_def); row.addStretch(1); row.addWidget(b_ok); row.addWidget(b_close)
    lay.addLayout(row)

    def apply():
        for inp, cb in combos.items():
            st["bind"][inp] = cb.currentText()
        if st["bind"].get("arrow_y") not in (NONE, CURSOR):
            st["focus"] = st["bind"]["arrow_y"]
        _status(app, "bindings applied")

    def defaults():
        d = default_state(app)
        for inp, cb in combos.items():
            v = d["bind"].get(inp, NONE)
            if cb.findText(v) < 0:
                cb.addItem(v)
            cb.setCurrentText(v)
    b_ok.clicked.connect(apply); b_def.clicked.connect(defaults); b_close.clicked.connect(dlg.close)
    dlg.resize(760, 560)
    dlg.show()
    app._step_auto_dialog = dlg
    return dlg
