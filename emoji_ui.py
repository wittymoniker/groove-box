"""EMOJI_UI_R7: emoji on every window, decided once per widget, centrally.

An application event filter decorates buttons, check boxes, radio buttons, group-box titles, tabs,
menu actions, window titles and short static labels the first time they are shown. The first keyword
of the text picks the emoji. Text that already starts with an emoji or symbol is left alone. A widget
is decorated at most once, so later setText() calls (status readouts) are never fought.

Code that compares a widget's text keeps working: `plain(text)` strips the prefix, and widgets listed
in SKIP_NAMES (texts compared in code) are never touched.
Off switch: System Settings ▸ "Emoji labels", or GROOVEBOX_EMOJI=0.
"""
from __future__ import annotations

import os
import re
import unicodedata

KEYWORDS = (
    ("canonical", "🧬"), ("morph", "🧬"), ("seed", "🌱"), ("fractal", "🌀"), ("teleport", "🌀"),
    ("random", "🎲"), ("stochastic", "🎲"), ("probability", "🎲"), ("dice", "🎲"),
    ("play", "▶️"), ("stop", "⏹️"), ("pause", "⏸️"), ("record", "⏺️"), ("rec", "⏺️"),
    ("save", "💾"), ("load", "📂"), ("open", "📂"), ("export", "📤"), ("import", "📥"),
    ("download", "⬇️"), ("upload", "⬆️"), ("settings", "⚙️"), ("setting", "⚙️"), ("options", "⚙️"),
    ("preferences", "⚙️"), ("config", "⚙️"), ("system", "🖥️"),
    ("synth", "🎹"), ("keyboard", "🎹"), ("keys", "🎹"), ("piano", "🎹"), ("drum", "🥁"), ("beat", "🥁"),
    ("bass", "🎸"), ("guitar", "🎸"), ("instrument", "🎺"), ("chord", "🎼"), ("note", "🎵"), ("notes", "🎵"),
    ("music", "🎵"), ("song", "🎵"), ("melody", "🎵"), ("harmonic", "🎶"), ("harmony", "🎶"),
    ("sample", "🎛️"), ("samples", "🎛️"), ("patch", "🎛️"), ("mixer", "🎚️"), ("mix", "🎚️"),
    ("level", "🎚️"), ("gain", "🎚️"), ("volume", "🔊"), ("master", "🔊"), ("audio", "🔊"),
    ("sound", "🔊"), ("sounds", "🔊"), ("mute", "🔇"), ("mic", "🎙️"), ("microphone", "🎙️"),
    ("camera", "🎥"), ("video", "🎬"), ("render", "🎬"), ("movie", "🎬"), ("clip", "🎞️"),
    ("frame", "🖼️"), ("image", "🖼️"), ("party", "🎉"), ("light", "💡"), ("color", "🎨"),
    ("colour", "🎨"), ("paint", "🎨"), ("palette", "🎨"), ("loop", "🔁"), ("repeat", "🔁"),
    ("shuffle", "🔀"), ("clear", "🧹"), ("delete", "🗑️"), ("remove", "🗑️"), ("reset", "↩️"),
    ("undo", "↩️"), ("redo", "↪️"), ("help", "❓"), ("readme", "📖"), ("guide", "📖"),
    ("info", "ℹ️"), ("about", "ℹ️"), ("file", "📁"), ("files", "📁"), ("folder", "📁"),
    ("project", "📁"), ("lock", "🔒"), ("locked", "🔒"), ("unlock", "🔓"), ("search", "🔍"),
    ("find", "🔍"), ("zoom", "🔍"), ("tempo", "⏱️"), ("bpm", "⏱️"), ("time", "⏱️"),
    ("timing", "⏱️"), ("step", "👣"), ("steps", "👣"), ("automation", "🤖"), ("auto", "🤖"),
    ("script", "📜"), ("scripts", "📜"), ("playlist", "📜"), ("code", "💻"), ("scode", "💻"),
    ("game", "🎮"), ("games", "🎮"), ("math", "➗"), ("equation", "➗"), ("formula", "➗"),
    ("fx", "✨"), ("effect", "✨"), ("effects", "✨"), ("filter", "🌊"), ("wave", "🌊"),
    ("waveform", "🌊"), ("eq", "📊"), ("scope", "📈"), ("graph", "📈"), ("chart", "📈"),
    ("analysis", "📈"), ("geometry", "📐"), ("geometric", "📐"), ("geometrics", "📐"),
    ("shape", "🔷"), ("shapes", "🔷"), ("3d", "🧊"), ("voxel", "🧊"), ("cube", "🧊"),
    ("live", "🔴"), ("stream", "📡"), ("broadcast", "📡"), ("network", "🌐"), ("web", "🌐"),
    ("pool", "🧵"), ("thread", "🧵"), ("threads", "🧵"), ("process", "🧵"), ("memory", "🧠"),
    ("cpu", "🧠"), ("window", "🪟"), ("layer", "🗂️"), ("layers", "🗂️"), ("preset", "⭐"),
    ("presets", "⭐"), ("favorite", "⭐"), ("copy", "📋"), ("paste", "📋"), ("add", "➕"),
    ("new", "🆕"), ("close", "✖️"), ("quit", "🚪"), ("exit", "🚪"), ("ok", "✅"), ("apply", "✅"),
    ("done", "✅"), ("cancel", "❌"), ("compat", "🧩"), ("compatibility", "🧩"), ("plugin", "🧩"),
    ("module", "🧩"), ("modules", "🧩"), ("pattern", "🧱"), ("grid", "🔲"), ("pad", "🔲"),
    ("pads", "🔲"), ("gravity", "🪐"), ("physics", "🪐"), ("ball", "⚽"), ("spatial", "🛰️"),
    ("space", "🌌"), ("noise", "📻"), ("signal", "📶"), ("trigger", "⚡"), ("triggers", "⚡"),
    ("action", "⚡"), ("actions", "⚡"), ("performance", "⚡"), ("speed", "⚡"), ("test", "🧪"),
    ("debug", "🐞"), ("log", "📝"), ("text", "📝"), ("edit", "✏️"), ("editor", "✏️"),
    ("write", "✏️"), ("font", "🔤"), ("name", "🏷️"), ("label", "🏷️"), ("tag", "🏷️"),
    ("modulation", "〰️"), ("mod", "〰️"), ("lfo", "〰️"), ("oscillator", "〰️"), ("osc", "〰️"),
    ("envelope", "📉"), ("sidechain", "🔗"), ("link", "🔗"), ("bind", "🔗"), ("route", "🔀"),
    ("routing", "🔀"), ("matrix", "🔢"), ("number", "🔢"), ("numbers", "🔢"), ("vector", "➡️"),
    ("fullscreen", "🖥️"), ("snapshot", "📸"), ("snapshots", "📸"), ("memory", "🧠"),
    ("multidim", "🧊"), ("multidimensional", "🧊"), ("divergence", "🌗"), ("phase", "🌗"),
    ("euclidean", "⭕"), ("ring", "⭕"), ("circle", "⭕"), ("arc", "🌈"), ("rainbow", "🌈"),
)
_MAP = {}
for _k, _e in KEYWORDS:
    _MAP.setdefault(_k, _e)

# widgets whose text is compared in code (never decorated)
SKIP_NAMES = {"btn_edit_panels_per_sequence", "chk_rig", "btn_audio_record", "lbl_status"}
_WORD = re.compile(r"[A-Za-z0-9]+")
_DONE = "_emoji_ui_done"


def enabled():
    if str(os.environ.get("GROOVEBOX_EMOJI", "1")).strip().lower() in ("0", "false", "off", "no"):
        return False
    try:
        import compat_settings as _cs
        return bool(_cs.load().get("emoji_labels", True))
    except Exception:
        return True


def _starts_with_symbol(text):
    for ch in text.lstrip():
        cat = unicodedata.category(ch)
        return cat.startswith("S") or ord(ch) >= 0x2190 and not ch.isalnum()
    return True


def pick(text):
    """The emoji for a text, or '' (no keyword / already decorated / not a plain label)."""
    t = str(text or "")
    if not t.strip() or len(t) > 48 or "<" in t or _starts_with_symbol(t):
        return ""
    for w in _WORD.findall(t.replace("&", "")):
        e = _MAP.get(w.lower())
        if e:
            return e
    return ""


def decorate(text):
    e = pick(text)
    return f"{e} {text}" if e else text


def plain(text):
    """Text without a leading emoji prefix (for code that compares texts)."""
    t = str(text or "")
    for _k, e in KEYWORDS:
        if t.startswith(e + " "):
            return t[len(e) + 1:]
    return t


def apply_widget(w):
    from PyQt6.QtWidgets import (QAbstractButton, QGroupBox, QTabWidget, QLabel, QMenu, QWidget)
    from PyQt6.QtCore import Qt
    if w is None or w.property(_DONE):
        return
    w.setProperty(_DONE, True)
    if (w.objectName() or "") in SKIP_NAMES:
        return
    try:
        if isinstance(w, QAbstractButton):
            t = w.text()
            if t and "\n" not in t:
                n = decorate(t)
                if n != t:
                    w.setText(n)
        elif isinstance(w, QGroupBox):
            n = decorate(w.title())
            if n != w.title():
                w.setTitle(n)
        elif isinstance(w, QTabWidget):
            for i in range(w.count()):
                t = w.tabText(i); n = decorate(t)
                if n != t:
                    w.setTabText(i, n)
        elif isinstance(w, QMenu):
            for a in w.actions():
                t = a.text()
                if t and not a.isSeparator():
                    n = decorate(t)
                    if n != t:
                        a.setText(n)
        elif isinstance(w, QLabel):
            t = w.text()
            if t and "\n" not in t and len(t) <= 32 and w.textFormat() != Qt.TextFormat.RichText and not any(c.isdigit() for c in t):
                n = decorate(t)
                if n != t:
                    w.setText(n)
        if w.isWindow():
            t = w.windowTitle(); n = decorate(t)
            if t and n != t:
                w.setWindowTitle(n)
    except Exception:
        pass


def _bind_names(host):
    """objectName = attribute name for attributes in SKIP_NAMES, so skips work without per-site edits."""
    try:
        for name in SKIP_NAMES:
            w = getattr(host, name, None)
            if w is not None and hasattr(w, "setObjectName") and not w.objectName():
                w.setObjectName(name)
    except Exception:
        pass


class _Filter:
    def __init__(self):
        from PyQt6.QtCore import QObject, QEvent

        class F(QObject):
            def eventFilter(self, obj, ev):
                try:
                    if ev.type() == QEvent.Type.Show:
                        from PyQt6.QtWidgets import QWidget
                        if isinstance(obj, QWidget) and obj.isWindow():
                            _bind_names(obj)
                            for c in [obj] + obj.findChildren(QWidget):
                                apply_widget(c)
                        elif isinstance(obj, QWidget):
                            apply_widget(obj)
                except Exception:
                    pass
                return False
        self.obj = F()


_INSTALLED = []


def install(app=None):
    """Install once on the QApplication (no-op when disabled)."""
    if _INSTALLED or not enabled():
        return False
    try:
        from PyQt6.QtWidgets import QApplication
        app = app or QApplication.instance()
        if app is None:
            return False
        f = _Filter()
        app.installEventFilter(f.obj)
        _INSTALLED.append(f)
        return True
    except Exception:
        return False
