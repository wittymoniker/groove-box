"""accessibility.py — GROOVEBOX_R32_ACCESSIBILITY_20261110

Compatibility ▸ Accessibility & wellbeing.  Everything here is off / neutral by default.

COLOR SCHEMES  one colour transform f(rgb) applied to EVERY colour the UI declares: the Qt palette of
               every window and each hex / rgb() / rgba() colour in every style sheet (re-applied
               to windows as they appear; originals kept, so switching back is exact).  Optional:
               the same transform on generated video (exports + the live rig), "outputs".
    normal · high contrast · protan-safe · deutan-safe · tritan-safe (daltonised, Machado 2009
    simulation matrices, severity 1) · grayscale · warm night (less blue) · inverted
TOUCH KEYBOARD an on-screen keyboard that appears when a text / number field gets focus — only on
               devices that report a touchscreen (auto), or always ("on", the no-keyboard workaround).
NO MOUSE       strong focus outlines, Tab / Shift+Tab / arrows move between controls, Space / Enter
               press, and Ctrl+K opens a command palette of every button and menu action (type,
               Enter).  Ctrl+K works for everyone.
NO KEYBOARD    the on-screen keyboard is always available (⌨ in the Quick Rack) and opens for any field.
WELLBEING      a gentle break reminder every N minutes of active use, and a listening guard that
               notices long loud playback (master level) and suggests a pause or lower volume.
"""
from __future__ import annotations

import re
import time

import numpy as np

SCHEMES = ("normal", "high contrast", "protan-safe", "deutan-safe", "tritan-safe", "grayscale", "warm night", "inverted")

# Machado et al. 2009 simulation matrices (severity 1.0), linear-ish sRGB approximation
_SIM = {
    "protan-safe": np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]),
    "deutan-safe": np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]),
    "tritan-safe": np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]),
}
_SHIFT = np.array([[0.0, 0.0, 0.0], [0.7, 1.0, 0.0], [0.7, 0.0, 1.0]])     # daltonise: move lost red/green contrast into seen channels
_SHIFT_T = np.array([[1.0, 0.0, 0.7], [0.0, 1.0, 0.7], [0.0, 0.0, 0.0]])   # tritan: lost blue/yellow contrast → red + green


def _matrix(scheme):
    if scheme in _SIM:
        S = _SIM[scheme]; I = np.eye(3)
        sh = _SHIFT_T if scheme == "tritan-safe" else _SHIFT
        return I + sh @ (I - S)                # c' = c + shift·(c − sim(c))
    if scheme == "grayscale":
        return np.tile([[0.2126, 0.7152, 0.0722]], (3, 1))
    if scheme == "warm night":
        return np.diag([1.0, 0.86, 0.62])
    return None


def transform_array(rgb, scheme):
    """uint8 (..., 3) → transformed uint8 (vectorised; used for video outputs too)."""
    if scheme in (None, "", "normal"):
        return rgb
    a = np.asarray(rgb, dtype=np.float32)
    if scheme == "inverted":
        out = 255.0 - a
    elif scheme == "high contrast":
        m = a.mean(axis=-1, keepdims=True)
        out = (a - m) * 1.35 + m                                   # saturation up
        out = (out - 128.0) * 1.55 + 128.0                         # contrast up
    else:
        M = _matrix(scheme)
        out = a @ M.T
    return np.clip(out, 0, 255).astype(np.uint8)


def transform_rgb(r, g, b, scheme):
    o = transform_array(np.array([[r, g, b]], dtype=np.uint8), scheme)[0]
    return int(o[0]), int(o[1]), int(o[2])


_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*[\d.]+\s*)?\)")


def transform_stylesheet(ss, scheme):
    if not ss or scheme in (None, "", "normal"):
        return ss

    def hx(m):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % transform_rgb(r, g, b, scheme)

    def rg(m):
        r, g, b = transform_rgb(int(m.group(1)), int(m.group(2)), int(m.group(3)), scheme)
        return ("rgba(%d,%d,%d%s)" % (r, g, b, m.group(4))) if m.group(4) else "rgb(%d,%d,%d)" % (r, g, b)
    return _RGB.sub(rg, _HEX.sub(hx, ss))


# ---------------------------------------------------------------- applying to the UI ------
class _A11y:
    def __init__(self, app):
        self.app = app
        self.scheme = "normal"; self.outputs = False
        self.no_mouse = False; self.keyboard_mode = "auto"
        self.kbd = None; self._orig_palette = None; self._filter = None
        self._break_min = 0; self._active_since = time.monotonic(); self._last_input = time.monotonic()
        self._loud_s = 0.0; self._loud_warned = 0.0

    # -- colours --------------------------------------------------------------
    def apply_scheme(self, scheme):
        from PyQt6.QtWidgets import QApplication, QWidget
        qa = QApplication.instance()
        self.scheme = scheme if scheme in SCHEMES else "normal"
        if self._orig_palette is None:
            from PyQt6.QtGui import QPalette
            self._orig_palette = QPalette(qa.palette())
        qa.setPalette(self._palette(self._orig_palette))
        o = qa.property("_a11y_orig_ss")
        if o is None:
            o = qa.styleSheet() or ""; qa.setProperty("_a11y_orig_ss", o)
        qa.setStyleSheet(transform_stylesheet(o, self.scheme) + self._focus_css())
        for w in qa.allWidgets():
            self._apply_widget(w)

    def _palette(self, base):
        from PyQt6.QtGui import QPalette, QColor
        p = QPalette(base)
        if self.scheme == "normal":
            return p
        for grp in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
            for role in QPalette.ColorRole:
                if role == QPalette.ColorRole.NColorRoles:
                    continue
                try:
                    c = base.color(grp, role)
                    r, g, b = transform_rgb(c.red(), c.green(), c.blue(), self.scheme)
                    p.setColor(grp, role, QColor(r, g, b, c.alpha()))
                except Exception:
                    pass
        return p

    def _apply_widget(self, w):
        try:
            o = w.property("_a11y_orig_ss")
            if o is None:
                o = w.styleSheet() or ""
                if not o:
                    return
                w.setProperty("_a11y_orig_ss", o)
            w.setStyleSheet(transform_stylesheet(o, self.scheme))
        except RuntimeError:
            pass

    def _focus_css(self):
        if not self.no_mouse:
            return ""
        return ("\n*:focus{outline:none;border:2px solid #ffd166;}"
                "QPushButton:focus,QToolButton:focus{background:rgba(255,209,102,60);}")

    # -- event filter: new windows + touch keyboard + activity -----------------
    def eventFilter(self, obj, ev):
        from PyQt6.QtCore import QEvent
        t = ev.type()
        if t == QEvent.Type.Show and self.scheme != "normal":
            try:
                from PyQt6.QtWidgets import QWidget
                if isinstance(obj, QWidget) and obj.isWindow() and not obj.property("_a11y_done"):
                    obj.setProperty("_a11y_done", True)
                    for w in [obj] + obj.findChildren(QWidget):
                        self._apply_widget(w)
            except Exception:
                pass
        elif t in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin):
            now = time.monotonic()
            if now - self._last_input > 600:          # 10 idle minutes = a break was taken
                self._active_since = now
            self._last_input = now
        return False


_STATE = {"a": None}


def _qobj_filter(a):
    from PyQt6.QtCore import QObject

    class F(QObject):
        def eventFilter(self, obj, ev):
            return a.eventFilter(obj, ev)
    return F()


_TOUCH = {"v": None, "at": 0.0}


def has_touchscreen():
    now = time.monotonic()                       # R32.9: cached (devices change rarely; re-checked every 30 s)
    if _TOUCH["v"] is not None and now - _TOUCH["at"] < 30.0:
        return _TOUCH["v"]
    _TOUCH["at"] = now; _TOUCH["v"] = _has_touchscreen_now()
    return _TOUCH["v"]


def _has_touchscreen_now():
    try:
        from PyQt6.QtGui import QInputDevice
        return any(d.type() == QInputDevice.DeviceType.TouchScreen for d in QInputDevice.devices())
    except Exception:
        return False


# ---------------------------------------------------------------- on-screen keyboard -------
ROWS = (("1234567890-=", "⌫"), ("qwertyuiop[]", "↵"), ("asdfghjkl;'", "⇥"), ("⇧zxcvbnm,./", "⇧"), ("⎋", "← → ↑ ↓", "␣", "⌨✕"))


def keyboard(app):
    a = _STATE["a"]
    if a is not None and a.kbd is not None:
        return a.kbd
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QApplication
    w = QWidget(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus |
                Qt.WindowType.FramelessWindowHint)
    w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    w.setWindowTitle("Groovebox touch keyboard"); w.setProperty("grooveboxTouchKeyboard", True)
    w.setStyleSheet("QWidget{background:#14202e;} QPushButton{color:#eaf6ff;background:#22344a;border:1px solid #2ecc71;"
                    "border-radius:6px;font-size:14pt;min-width:44px;min-height:44px;} QPushButton:pressed{background:#2ecc71;color:#000;}")
    lay = QVBoxLayout(w); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(4)
    shift = {"on": False}; keys = []
    special = {"⌫": Qt.Key.Key_Backspace, "↵": Qt.Key.Key_Return, "⇥": Qt.Key.Key_Tab, "⎋": Qt.Key.Key_Escape,
               "←": Qt.Key.Key_Left, "→": Qt.Key.Key_Right, "↑": Qt.Key.Key_Up, "↓": Qt.Key.Key_Down, "␣": Qt.Key.Key_Space}

    def send(label):
        if label == "⇧":
            shift["on"] = not shift["on"]
            for b, ch in keys:
                if len(ch) == 1 and ch.isalpha():
                    b.setText(ch.upper() if shift["on"] else ch)
            return
        if label == "⌨✕":
            w.hide(); return
        tgt = QApplication.focusWidget()
        if tgt is None:
            return
        if label in special:
            k = special[label]; txt = " " if label == "␣" else ("\r" if label == "↵" else "")
        else:
            txt = label.upper() if (shift["on"] and label.isalpha()) else label
            k = Qt.Key(ord(txt.upper())) if len(txt) == 1 and txt.isalnum() else Qt.Key.Key_unknown
        for et in (QKeyEvent.Type.KeyPress, QKeyEvent.Type.KeyRelease):
            QApplication.postEvent(tgt, QKeyEvent(et, k, Qt.KeyboardModifier.NoModifier, txt))
        if shift["on"] and label.isalpha():
            send("⇧")
    for row in ROWS:
        h = QHBoxLayout(); h.setSpacing(4)
        for part in row:
            for ch in (part.split(" ") if " " in part else ([part] if len(part) <= 2 or part in special else list(part))):
                b = QPushButton(ch); b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                if ch == "␣":
                    b.setMinimumWidth(260)
                b.clicked.connect(lambda _c=False, ch=ch: send(ch)); h.addWidget(b); keys.append((b, ch))
        lay.addLayout(h)
    try:
        scr = QApplication.primaryScreen().availableGeometry()
        w.resize(min(scr.width(), 900), 270); w.move(scr.x() + (scr.width() - w.width()) // 2, scr.bottom() - w.height())
    except Exception:
        w.resize(900, 270)
    if a is not None:
        a.kbd = w
    return w


def _on_focus(old, new):
    a = _STATE["a"]
    if a is None or new is None:
        return
    from PyQt6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox
    wants = isinstance(new, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)) or (isinstance(new, QComboBox) and new.isEditable())
    if not wants:
        return
    try:
        if new.window().property("grooveboxTouchKeyboard"):
            return
    except Exception:
        pass
    if a.keyboard_mode == "on" or (a.keyboard_mode == "auto" and has_touchscreen()):
        k = keyboard(a.app); k.show(); k.raise_()


# ---------------------------------------------------------------- command palette (no mouse) --
def command_palette(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QApplication,
                                 QAbstractButton)
    from PyQt6.QtGui import QAction
    entries = []
    seen = set()
    for top in QApplication.topLevelWidgets():
        if not top.isVisible() or top.property("grooveboxTouchKeyboard"):
            continue
        for b in top.findChildren(QAbstractButton):
            try:
                t = (b.text() or b.toolTip() or "").strip().replace("&", "")
                if t and b.isVisible() and b.isEnabled() and (t, top.windowTitle()) not in seen:
                    seen.add((t, top.windowTitle())); entries.append((t, top.windowTitle(), b.click))
            except RuntimeError:
                pass
        for act in top.findChildren(QAction):
            try:
                t = (act.text() or "").replace("&", "").strip()
                if t and act.isEnabled() and not act.isSeparator() and (t, "menu") not in seen:
                    seen.add((t, "menu")); entries.append((t, "menu · " + top.windowTitle(), act.trigger))
            except RuntimeError:
                pass
    d = QDialog(app); d.setWindowTitle("⌘ Command palette — type, ↑↓, Enter"); d.resize(640, 460)
    lay = QVBoxLayout(d); q = QLineEdit(); q.setPlaceholderText("Search every button and menu action…"); lay.addWidget(q)
    lst = QListWidget(); lay.addWidget(lst, 1)

    def fill(text=""):
        lst.clear(); tl = text.casefold().split()
        for t, where, fn in entries:
            hay = (t + " " + where).casefold()
            if all(x in hay for x in tl):
                it = QListWidgetItem("%s   ·   %s" % (t[:90], where[:40])); it.setData(Qt.ItemDataRole.UserRole, fn); lst.addItem(it)
                if lst.count() >= 300:
                    break
        lst.setCurrentRow(0)

    def run(*_):
        it = lst.currentItem()
        if it is not None:
            fn = it.data(Qt.ItemDataRole.UserRole); d.accept()
            try:
                fn()
            except Exception:
                pass
    q.textChanged.connect(fill); q.returnPressed.connect(run); lst.itemActivated.connect(run)

    class _Nav(__import__("PyQt6.QtCore", fromlist=["QObject"]).QObject):
        def eventFilter(self, o, e):
            from PyQt6.QtCore import QEvent
            if e.type() == QEvent.Type.KeyPress and e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                lst.setCurrentRow(max(0, min(lst.count() - 1, lst.currentRow() + (1 if e.key() == Qt.Key.Key_Down else -1)))); return True
            return False
    d._nav = _Nav(d); q.installEventFilter(d._nav)
    fill(); d.setModal(False); d.show(); q.setFocus()
    return d


# ---------------------------------------------------------------- wellbeing ----------------
def _toast(app, text):
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QLabel
    lab = QLabel(text, None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
    lab.setStyleSheet("QLabel{background:#14202e;color:#eaf6ff;border:2px solid #2ecc71;border-radius:10px;padding:12px;font-size:11pt;}")
    lab.setWordWrap(True); lab.setMaximumWidth(420); lab.adjustSize()
    try:
        g = app.geometry(); lab.move(g.right() - lab.width() - 24, g.top() + 64)
    except Exception:
        pass
    lab.show(); QTimer.singleShot(9000, lab.deleteLater)
    return lab


def _wellbeing_tick():
    a = _STATE["a"]
    if a is None:
        return
    app = a.app; now = time.monotonic()
    if a._break_min > 0 and now - a._last_input < 120 and now - a._active_since > a._break_min * 60:
        _toast(app, "🌿 You've been creating for %d minutes. Stand up, stretch, rest your eyes for a minute — the project will wait."
               % int((now - a._active_since) / 60))
        a._active_since = now
    try:
        if getattr(app, "is_playing", False) and getattr(app, "play_buffer", None) is not None:
            buf = app.play_buffer; c = int(getattr(app, "play_cursor", 0) or 0)
            seg = np.asarray(buf[c:c + 4800], dtype=np.float32)
            vol = float(getattr(app, "master_volume", 0.72) or 0.72)
            if seg.size:
                db = 20 * np.log10(max(1e-9, float(np.sqrt(np.mean(seg ** 2))) * vol))
                a._loud_s = a._loud_s + 5.0 if db > -12.0 else max(0.0, a._loud_s - 2.5)
                if a._loud_s > 45 * 60 and now - a._loud_warned > 1800:
                    a._loud_warned = now
                    _toast(app, "👂 Loud playback for a long stretch. Your ears recover with a short quiet break or a few dB less volume.")
    except Exception:
        pass


# ---------------------------------------------------------------- install / settings -------
def apply_settings(app, d):
    a = _STATE["a"]
    if a is None:
        return
    a.no_mouse = bool(d.get("no_mouse", False))
    a.keyboard_mode = str(d.get("touch_keyboard", "auto"))
    if bool(d.get("no_keyboard", False)):
        a.keyboard_mode = "on"
    a.outputs = bool(d.get("color_scheme_outputs", False))
    a._break_min = int(d.get("break_reminder_min", 0) or 0)
    from PyQt6.QtWidgets import QApplication
    qa = QApplication.instance()
    want_filter = str(d.get("color_scheme", "normal")) != "normal" or a._break_min > 0
    if want_filter and not getattr(a, "_filter_on", False):
        qa.installEventFilter(a._filter); a._filter_on = True
    elif not want_filter and getattr(a, "_filter_on", False):
        qa.removeEventFilter(a._filter); a._filter_on = False
    if a.scheme != "normal" or str(d.get("color_scheme", "normal")) != "normal" or a.no_mouse:
        a.apply_scheme(str(d.get("color_scheme", "normal")))
    if a.keyboard_mode == "off" and a.kbd is not None:
        a.kbd.hide()


def install(app):
    if _STATE["a"] is not None:
        return _STATE["a"]
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QShortcut, QKeySequence
    from PyQt6.QtWidgets import QApplication
    a = _STATE["a"] = _A11y(app)
    qa = QApplication.instance()
    a._filter = _qobj_filter(a)          # installed only while a scheme / break reminder needs it (see apply_settings)
    qa.focusChanged.connect(_on_focus)
    sc = QShortcut(QKeySequence("Ctrl+K"), app); sc.setContext(__import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ShortcutContext.ApplicationShortcut)
    sc.activated.connect(lambda: command_palette(app)); app._a11y_palette_shortcut = sc
    t = QTimer(app); t.setInterval(5000); t.timeout.connect(_wellbeing_tick); t.start(); app._a11y_timer = t
    # outputs: the same colour transform on generated video (exports + live rig)
    orig = getattr(app, "_apply_video_plan_to_frame", None)
    if callable(orig) and not getattr(app, "_a11y_frame_hooked", False):
        def _frame(frame, fi, n, _o=orig):
            out = _o(frame, fi, n)
            if a.outputs and a.scheme != "normal":
                try:
                    arr = np.asarray(out)
                    out = np.concatenate([transform_array(arr[..., :3], a.scheme), arr[..., 3:]], axis=-1) if arr.shape[-1] > 3 else transform_array(arr, a.scheme)
                except Exception:
                    pass
            return out
        app._apply_video_plan_to_frame = _frame; app._a11y_frame_hooked = True
    try:
        import compat_settings as cs
        QTimer.singleShot(800, lambda: apply_settings(app, cs.load()))
    except Exception:
        pass
    return a
