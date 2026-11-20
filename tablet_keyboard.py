"""tablet_keyboard.py — fixed on-screen keyboard for tablet mode.

GROOVEBOX_R123_TABLET_KEYBOARD_20261119

In tablet mode a keyboard is docked along the bottom of the main window. It has no close
button, cannot float or be dragged away, and comes back if anything hides it. Every key is a
standard key, so it drives exactly what a hardware keyboard drives:

* control row — Space, Enter (hold = record loop, as on a keyboard), Tab / Shift+Tab
  (instrument walk), Esc, Undo, Redo, Save, Find, arrows, PgUp/PgDn, Home/End, Del, Backspace,
  Menu (context menu = right-click), and latching Shift / Ctrl / Alt modifiers;
* eight custom keys — each is a label plus any standard key sequence (e.g. Ctrl+Shift+L,
  F5, Shift+F3, Alt+1). Tap ✎ to assign; saved across sessions;
* ABC page — letters, digits and punctuation for typing into text fields; F1–F12 page.

Keys never take keyboard focus, so they act on the field / window you last touched.
A key whose sequence belongs to an app shortcut (QShortcut / QAction) triggers that shortcut
directly; any other key is delivered as a real key press + release to the focused widget.

Tablet mode: Auto (on when a touchscreen is present) / On / Off — Settings menu
"📱 Tablet mode keyboard", saved in QSettings("MathematiciansGroovebox", "UI") "tablet_mode".
"""
from __future__ import annotations

import json

from PyQt6.QtCore import Qt, QSettings, QTimer, QPoint, QEvent
from PyQt6.QtGui import QKeySequence, QKeyEvent, QShortcut, QAction, QContextMenuEvent, QCursor
from PyQt6.QtWidgets import (
    QApplication, QDockWidget, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget,
    QDialog, QFormLayout, QLineEdit, QKeySequenceEdit, QDialogButtonBox, QSizePolicy, QLabel,
)

MARKER = "GROOVEBOX_R123_TABLET_KEYBOARD_20261119"
_ORG, _APP = "MathematiciansGroovebox", "UI"
N_CUSTOM = 8
DEFAULT_CUSTOM = [
    ("▶/❚❚ Play", "Alt+Space"), ("PANIC", "Alt+."), ("🔁 Loop", "Alt+L"), ("👆 Tap", "Alt+T"),
    ("⏺ Take", "Alt+R"), ("🎲 Random", "Alt+G"), ("⬇ Mixdown", "Ctrl+Shift+E"), ("⌨ Keys", "Ctrl+/"),
]

# (caption, key, text, hold-aware)
CONTROL_KEYS = [
    ("Esc", Qt.Key.Key_Escape, ""), ("Tab ⇥", Qt.Key.Key_Tab, "\t"), ("⇤ Tab", Qt.Key.Key_Backtab, ""),
    ("Space", Qt.Key.Key_Space, " "), ("Enter ⏎", Qt.Key.Key_Return, "\r"),
    ("←", Qt.Key.Key_Left, ""), ("↑", Qt.Key.Key_Up, ""), ("↓", Qt.Key.Key_Down, ""), ("→", Qt.Key.Key_Right, ""),
    ("PgUp", Qt.Key.Key_PageUp, ""), ("PgDn", Qt.Key.Key_PageDown, ""), ("Home", Qt.Key.Key_Home, ""),
    ("End", Qt.Key.Key_End, ""), ("Del", Qt.Key.Key_Delete, ""), ("⌫", Qt.Key.Key_Backspace, ""),
]
SEQ_KEYS = [("Undo", "Ctrl+Z"), ("Redo", "Ctrl+Y"), ("Save", "Ctrl+S"), ("Find", "Ctrl+F")]
ABC_ROWS = ["1234567890-=", "qwertyuiop[]", "asdfghjkl;'\\", "zxcvbnm,./`"]

SCALE_MIN, SCALE_MAX = 0.6, 2.2


def _key_css(scale=1.0):
    return ("QPushButton { background:#18222e; color:#e6eef7; border:1px solid #3c5066; border-radius:6px;"
            f" padding:{int(4 * scale)}px 6px; font-weight:800; font-size:{10 * scale:.1f}pt; min-height:{int(38 * scale)}px; }}"
            " QPushButton:pressed { background:#2c4a66; } QPushButton:checked { background:#2f6a4a; border-color:#7dffb0; }")


def load_scale() -> float:
    st = QSettings(_ORG, _APP)
    default = 1.0
    try:
        import touch_compat
        default = 0.8 if touch_compat.small_screen() else 1.0     # small screens start with smaller keys
    except Exception:
        pass
    try:
        v = float(st.value("tablet_kb_scale", default))
    except Exception:
        v = default
    return max(SCALE_MIN, min(SCALE_MAX, v))


def size_locked() -> bool:
    return str(QSettings(_ORG, _APP).value("tablet_kb_size_lock", False)).lower() in ("1", "true", "yes")


class _Grip(QWidget):
    """Drag bar on top of the keyboard: drag up = bigger keys, down = smaller (unless the size is locked)."""

    def __init__(self, kb):
        super().__init__(); self.kb = kb; self.y0 = None
        self.setFixedHeight(14); self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Drag up / down to resize the keyboard · wheel over the keyboard also resizes (🔒 Size locks it)")

    def paintEvent(self, _e):
        from PyQt6.QtGui import QPainter, QColor
        q = QPainter(self); q.fillRect(self.rect(), QColor(16, 30, 42))
        q.setPen(QColor(120, 200, 230)); w = self.width()
        for dx in (-24, 0, 24):
            q.drawLine(w // 2 + dx - 8, 7, w // 2 + dx + 8, 7)
        q.end()

    def mousePressEvent(self, e):
        self.y0 = e.globalPosition().y()

    def mouseMoveEvent(self, e):
        if self.y0 is None or self.kb.btn_lock.isChecked():
            return
        dy = e.globalPosition().y() - self.y0
        if abs(dy) >= 6:
            self.y0 = e.globalPosition().y()
            self.kb.set_scale(self.kb.scale - dy / 160.0)

    def mouseReleaseEvent(self, _e):
        self.y0 = None


# ---------------------------------------------------------------- settings
def mode() -> str:
    v = str(QSettings(_ORG, _APP).value("tablet_mode", "auto") or "auto").lower()
    return v if v in ("auto", "on", "off") else "auto"


def set_mode(value: str) -> None:
    QSettings(_ORG, _APP).setValue("tablet_mode", value)


def has_touchscreen() -> bool:
    try:
        from PyQt6.QtGui import QInputDevice
        return any(d.type() == QInputDevice.DeviceType.TouchScreen for d in QInputDevice.devices())
    except Exception:
        return False


def enabled() -> bool:
    m = mode()
    return m == "on" or (m == "auto" and has_touchscreen())


def load_custom():
    raw = QSettings(_ORG, _APP).value("tablet_custom_keys", "")
    try:
        data = json.loads(raw) if raw else []
    except Exception:
        data = []
    out = []
    for i in range(N_CUSTOM):
        if i < len(data) and isinstance(data[i], (list, tuple)) and len(data[i]) == 2:
            out.append((str(data[i][0]), str(data[i][1])))
        else:
            out.append(DEFAULT_CUSTOM[i])
    return out


def save_custom(items) -> None:
    QSettings(_ORG, _APP).setValue("tablet_custom_keys", json.dumps([list(x) for x in items][:N_CUSTOM]))


# ---------------------------------------------------------------- delivery
def _matching_shortcut(seq: QKeySequence):
    """Find an enabled app shortcut / action bound to seq (prefer the active window)."""
    app = QApplication.instance()
    if app is None or seq.isEmpty():
        return None
    wins = []
    aw = app.activeWindow()
    if aw is not None:
        wins.append(aw)
    wins += [w for w in app.topLevelWidgets() if w is not aw and w.isVisible()]
    for w in wins:
        for sc in w.findChildren(QShortcut):
            try:
                if sc.isEnabled() and sc.key().matches(seq) == QKeySequence.SequenceMatch.ExactMatch:
                    return sc
            except Exception:
                continue
        for act in w.findChildren(QAction):
            try:
                if act.isEnabled() and any(k.matches(seq) == QKeySequence.SequenceMatch.ExactMatch for k in act.shortcuts()):
                    return act
            except Exception:
                continue
    for sc in app.findChildren(QShortcut):
        try:
            if sc.isEnabled() and sc.key().matches(seq) == QKeySequence.SequenceMatch.ExactMatch:
                return sc
        except Exception:
            continue
    return None


class _Target:
    """Remembers the last focused widget outside the keyboard."""

    def __init__(self, host, kb_root):
        self.host = host; self.kb = kb_root; self.last = None
        QApplication.instance().focusChanged.connect(self._changed)

    def _changed(self, _old, new):
        if new is None:
            return
        node = new
        while node is not None:
            if node is self.kb:
                return
            node = node.parentWidget()
        self.last = new

    def widget(self):
        w = self.last
        try:
            if w is not None and w.isVisible():
                return w
        except Exception:
            pass
        return QApplication.focusWidget() or self.host


def send_key(target, key, mods=Qt.KeyboardModifier.NoModifier, text="", press=True, release=True) -> None:
    if target is None:
        return
    if key == Qt.Key.Key_Backtab:
        mods = mods | Qt.KeyboardModifier.ShiftModifier
    if mods & ~Qt.KeyboardModifier.ShiftModifier & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
        text = ""
    elif text and mods & Qt.KeyboardModifier.ShiftModifier and len(text) == 1:
        text = text.upper()
    if press:
        QApplication.sendEvent(target, QKeyEvent(QEvent.Type.KeyPress, int(key), mods, text))
    if release:
        QApplication.sendEvent(target, QKeyEvent(QEvent.Type.KeyRelease, int(key), mods, text))


def send_sequence(target, seq_text: str, extra_mods=Qt.KeyboardModifier.NoModifier) -> str:
    """Trigger seq_text: an app shortcut if one is bound, else a key press. Returns what happened."""
    seq = QKeySequence(seq_text)
    if seq.isEmpty():
        return "empty"
    combo = seq[0]
    key, mods = combo.key(), combo.keyboardModifiers() | extra_mods
    full = QKeySequence(combo.keyboardModifiers().value | extra_mods.value | key.value) if extra_mods.value else seq
    hit = _matching_shortcut(full)
    if isinstance(hit, QShortcut):
        hit.activated.emit(); return "shortcut"
    if isinstance(hit, QAction):
        hit.trigger(); return "action"
    text = ""
    if Qt.Key.Key_Space.value <= key.value <= Qt.Key.Key_AsciiTilde.value:
        text = chr(key.value).lower()
    send_key(target, key, mods, text)
    return "key"


# ---------------------------------------------------------------- widget
class _CustomDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tablet keyboard · custom keys")
        f = QFormLayout(self)
        f.addRow(QLabel("Each custom key = a label + any standard key sequence. Tap the sequence box and press keys "
                        "(or type text like Ctrl+Shift+L, F5, Alt+1)."))
        self.rows = []
        for i, (lab, seq) in enumerate(items):
            le = QLineEdit(lab); ke = QKeySequenceEdit(QKeySequence(seq))
            try:
                ke.setMaximumSequenceLength(1)
            except Exception:
                pass
            txt = QLineEdit(seq); txt.setPlaceholderText("or type: Ctrl+Shift+L")
            ke.keySequenceChanged.connect(lambda s, t=txt: t.setText(s.toString()))
            row = QHBoxLayout(); row.addWidget(le, 2); row.addWidget(ke, 2); row.addWidget(txt, 2)
            w = QWidget(); w.setLayout(row); f.addRow(f"Key {i + 1}", w)
            self.rows.append((le, txt))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                              | QDialogButtonBox.StandardButton.RestoreDefaults)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._defaults)
        f.addRow(bb)

    def _defaults(self):
        for (le, txt), (lab, seq) in zip(self.rows, DEFAULT_CUSTOM):
            le.setText(lab); txt.setText(seq)

    def items(self):
        out = []
        for le, txt in self.rows:
            seq = QKeySequence(txt.text().strip()).toString()
            out.append((le.text().strip() or seq or "—", seq))
        return out


class TabletKeyboard(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("tabletKeyboard")
        self.scale = load_scale()
        self.target = _Target(host, self)
        self.latch = {}
        v = QVBoxLayout(self); v.setContentsMargins(6, 0, 6, 4); v.setSpacing(4)
        v.addWidget(_Grip(self))
        # row 1: control keys + latches
        r1 = QHBoxLayout(); r1.setSpacing(4)
        for cap, mod in (("⇧ Shift", Qt.KeyboardModifier.ShiftModifier), ("Ctrl", Qt.KeyboardModifier.ControlModifier),
                         ("Alt", Qt.KeyboardModifier.AltModifier)):
            b = self._btn(cap, checkable=True)
            b.setToolTip("Latching modifier: applies to the next key, then releases. Double-tap to lock.")
            self.latch[mod] = b; r1.addWidget(b)
        for cap, key, text in CONTROL_KEYS:
            b = self._btn(cap)
            b.pressed.connect(lambda k=key, t=text: self._key_down(k, t))
            b.released.connect(lambda k=key, t=text: self._key_up(k, t))
            r1.addWidget(b)
        menu = self._btn("☰ Menu"); menu.setToolTip("Context menu (= right-click) on the touched control")
        menu.clicked.connect(self._context_menu); r1.addWidget(menu)
        v.addLayout(r1)
        # row 2: app sequences, touch modes, custom keys, pages
        r2 = QHBoxLayout(); r2.setSpacing(4)
        for cap, seq in SEQ_KEYS:
            b = self._btn(cap); b.setToolTip(seq); b.clicked.connect(lambda _c=False, s=seq: self._seq(s)); r2.addWidget(b)
        try:
            import touch_compat
            alt = touch_compat.alt_toggle_button(host); alt.setFocusPolicy(Qt.FocusPolicy.NoFocus); r2.addWidget(alt)
        except Exception:
            pass
        self.custom_buttons = []
        for i in range(N_CUSTOM):
            b = self._btn("—"); b.clicked.connect(lambda _c=False, i=i: self._custom(i))
            self.custom_buttons.append(b); r2.addWidget(b)
        edit = self._btn("✎ Keys"); edit.setToolTip("Assign the eight custom keys"); edit.clicked.connect(self._edit_custom)
        r2.addWidget(edit)
        self.btn_abc = self._btn("ABC", checkable=True); self.btn_fn = self._btn("F1–F12", checkable=True)
        self.btn_abc.toggled.connect(lambda on: self._page(1 if on else 0, self.btn_fn))
        self.btn_fn.toggled.connect(lambda on: self._page(2 if on else 0, self.btn_abc))
        r2.addWidget(self.btn_abc); r2.addWidget(self.btn_fn)
        self.btn_lock = self._btn("🔒 Size", checkable=True)
        self.btn_lock.setToolTip("Scroll lock for the keyboard size: OFF (default) = wheel / drag bar resize the keyboard; "
                                 "ON = size is fixed and the wheel passes through.")
        self.btn_lock.setChecked(size_locked())
        self.btn_lock.toggled.connect(lambda on: QSettings(_ORG, _APP).setValue("tablet_kb_size_lock", bool(on)))
        r2.addWidget(self.btn_lock)
        v.addLayout(r2)
        # pages: none / ABC / F-keys
        self.pages = QStackedWidget(); self.pages.addWidget(QWidget())
        abc = QWidget(); av = QVBoxLayout(abc); av.setContentsMargins(0, 0, 0, 0); av.setSpacing(3)
        for row in ABC_ROWS:
            h = QHBoxLayout(); h.setSpacing(3)
            for ch in row:
                b = self._btn(ch); b.clicked.connect(lambda _c=False, ch=ch: self._char(ch)); h.addWidget(b)
            av.addLayout(h)
        self.pages.addWidget(abc)
        fk = QWidget(); fh = QHBoxLayout(fk); fh.setContentsMargins(0, 0, 0, 0); fh.setSpacing(3)
        for i in range(1, 13):
            b = self._btn(f"F{i}"); b.clicked.connect(lambda _c=False, i=i: self._seq(f"F{i}")); fh.addWidget(b)
        self.pages.addWidget(fk)
        self.pages.setVisible(False)
        v.addWidget(self.pages)
        self.refresh_custom()
        self.set_scale(self.scale, save=False)

    def set_scale(self, value, save=True):
        self.scale = round(max(SCALE_MIN, min(SCALE_MAX, float(value))), 3)
        self.setStyleSheet("#tabletKeyboard { background:#0b1118; border-top:2px solid #2f6a80; }" + _key_css(self.scale))
        if save:
            QSettings(_ORG, _APP).setValue("tablet_kb_scale", self.scale)

    def event(self, e):
        # touchpad / trackpad pinch resizes too (macOS, Wayland, Windows precision touchpads)
        try:
            if e.type() == QEvent.Type.NativeGesture and not self.btn_lock.isChecked():
                if e.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                    self.set_scale(self.scale * (1.0 + float(e.value()))); return True
        except Exception:
            pass
        return super().event(e)

    def wheelEvent(self, e):
        if self.btn_lock.isChecked():
            e.ignore(); return
        step = 0.05 if e.angleDelta().y() > 0 else -0.05
        self.set_scale(self.scale + step); e.accept()

    # -- helpers
    def _btn(self, cap, checkable=False):
        b = QPushButton(cap); b.setFocusPolicy(Qt.FocusPolicy.NoFocus); b.setCheckable(checkable)
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return b

    def _mods(self, consume=True):
        m = Qt.KeyboardModifier.NoModifier
        for mod, b in self.latch.items():
            if b.isChecked():
                m |= mod
        if consume:
            QTimer.singleShot(0, lambda: [b.setChecked(False) for b in self.latch.values()])
        return m

    def _page(self, idx, other):
        if idx:
            other.blockSignals(True); other.setChecked(False); other.blockSignals(False)
        self.pages.setCurrentIndex(idx); self.pages.setVisible(bool(idx))

    def _key_down(self, key, text):
        self._held_mods = self._mods(consume=False)
        mods = self._held_mods
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            self._held_seq = True
            return
        self._held_seq = False
        send_key(self.target.widget(), key, mods, text, press=True, release=False)

    def _key_up(self, key, text):
        mods = getattr(self, "_held_mods", Qt.KeyboardModifier.NoModifier)
        if getattr(self, "_held_seq", False):
            send_sequence(self.target.widget(), QKeySequence(key.value).toString(), mods)
        else:
            send_key(self.target.widget(), key, mods, text, press=False, release=True)
        self._mods(consume=True)

    def _seq(self, seq):
        return send_sequence(self.target.widget(), seq, self._mods())

    def _char(self, ch):
        mods = self._mods()
        key = Qt.Key(ord(ch.upper())) if ch.isalpha() else Qt.Key(ord(ch))
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            send_sequence(self.target.widget(), QKeySequence(key.value).toString(), mods)
        else:
            send_key(self.target.widget(), key, mods, ch)

    def _custom(self, i):
        lab, seq = self.custom[i]
        return send_sequence(self.target.widget(), seq, self._mods())

    def _context_menu(self):
        w = self.target.widget()
        if w is None:
            return
        pos = w.mapFromGlobal(QCursor.pos())
        if not w.rect().contains(pos):
            pos = w.rect().center()
        QApplication.sendEvent(w, QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, pos, w.mapToGlobal(pos)))

    def refresh_custom(self):
        self.custom = load_custom()
        for b, (lab, seq) in zip(self.custom_buttons, self.custom):
            b.setText(lab); b.setToolTip(f"{lab} = {seq or 'unassigned'} · ✎ Keys to change")

    def _edit_custom(self):
        d = _CustomDialog(self.custom, self.host)
        if d.exec():
            save_custom(d.items()); self.refresh_custom()


class _FixedDock(QDockWidget):
    """Bottom dock without close / float / move; re-shows itself while tablet mode is on."""

    def hideEvent(self, ev):
        super().hideEvent(ev)
        if getattr(self, "_keep", False):
            QTimer.singleShot(0, self.show)


def install(host):
    """Create (once) and show/hide the keyboard per tablet mode. Returns the dock or None."""
    dock = getattr(host, "tablet_keyboard_dock", None)
    on = enabled()
    if dock is None:
        if not on:
            return None
        dock = _FixedDock("Tablet keyboard", host)
        dock.setObjectName("tabletKeyboardDock")
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        dock.setTitleBarWidget(QWidget())
        dock.toggleViewAction().setVisible(False)
        host.tablet_keyboard = TabletKeyboard(host)
        dock.setWidget(host.tablet_keyboard)
        host.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        host.tablet_keyboard_dock = dock
    dock._keep = on
    dock.setVisible(on)
    return dock


def add_menu(host, menu):
    """Settings-menu entry: Tablet mode keyboard ▸ Auto / On / Off + custom keys."""
    from PyQt6.QtGui import QActionGroup
    sub = menu.addMenu("📱 Tablet mode keyboard")
    grp = QActionGroup(sub); grp.setExclusive(True)
    cur = mode()
    for val, cap in (("auto", "Auto (on with a touchscreen)"), ("on", "On — fixed keyboard"), ("off", "Off")):
        a = sub.addAction(cap); a.setCheckable(True); a.setChecked(cur == val); grp.addAction(a)
        a.triggered.connect(lambda _c=False, v=val: (set_mode(v), install(host)))
    sub.addSeparator()
    sub.addAction("✎ Custom keys…", lambda: (install(host), getattr(host, "tablet_keyboard", None)
                                              and host.tablet_keyboard._edit_custom()))
    return sub
