"""TYPOGRAPHY_R7 — one small, consistent type system for every window, on every OS.

Three families, each with metric-compatible fallbacks so spacing looks the same everywhere:

* ``UI``      Arial    — the whole interface (buttons, labels, menus, panes, overlays).
                         Linux/ISO: Liberation Sans / Arimo are metric-identical to Arial.
* ``CONSOLE`` Consolas — the README window, system-information popups (health, memory, lanes), code
                         editors, logs and numeric readouts.  Fallbacks: Cascadia Mono, Menlo,
                         DejaVu Sans Mono, Liberation Mono, Noto Sans Mono.
* ``PROSE``   Georgia  — long-form guide text and the logotype.  Fallbacks: Liberation Serif, Tinos,
                         DejaVu Serif, Noto Serif.

Letter and word spacing are always the font's own (100 %, 0 px).  ``install(app)`` makes Arial the
application font and registers each fallback chain as a Qt substitution, so any style sheet or QFont
that names a family resolves to a real font with the same metrics.  Colour emoji remain the final
fallback (see emoji_fonts.py).
"""
from __future__ import annotations

UI = "Arial"
CONSOLE = "Consolas"
PROSE = "Georgia"
FALLBACKS = {
    UI: ("Liberation Sans", "Arimo", "Helvetica Neue", "Helvetica", "DejaVu Sans", "Noto Sans"),
    CONSOLE: ("Cascadia Mono", "Menlo", "DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono", "Courier New"),
    PROSE: ("Liberation Serif", "Tinos", "DejaVu Serif", "Noto Serif", "Times New Roman"),
}
# CSS stacks for style sheets (first installed family wins).
UI_CSS = "Arial, 'Liberation Sans', Arimo, Helvetica, sans-serif"
CONSOLE_CSS = "Consolas, 'Cascadia Mono', Menlo, 'DejaVu Sans Mono', 'Liberation Mono', monospace"
PROSE_CSS = "Georgia, 'Liberation Serif', Tinos, 'DejaVu Serif', serif"

_STATE = {"installed": False, "resolved": {}}


def _resolve(family, available):
    if family in available:
        return family
    for f in FALLBACKS.get(family, ()):
        if f in available:
            return f
    return family


def _normal(f):
    from PyQt6.QtGui import QFont
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100.0)
    f.setWordSpacing(0.0)
    f.setKerning(True)
    return f


def font(role="ui", point_size=None, bold=False):
    """A QFont for ``role`` ('ui' | 'console' | 'prose') at normal spacing."""
    from PyQt6.QtGui import QFont
    fam = {"ui": UI, "console": CONSOLE, "prose": PROSE}.get(role, UI)
    f = QFont(fam)
    try:
        f.setFamilies([fam] + list(FALLBACKS.get(fam, ())))
    except Exception:
        pass
    if role == "console":
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setFixedPitch(True)
    elif role == "prose":
        f.setStyleHint(QFont.StyleHint.Serif)
    else:
        f.setStyleHint(QFont.StyleHint.SansSerif)
    if point_size:
        f.setPointSizeF(float(point_size))
    if bold:
        f.setBold(True)
    return _normal(f)


def console_font(point_size=None):
    return font("console", point_size)


def apply_console(widget, point_size=None):
    """Use the console face on ``widget`` (README text, system-information popups)."""
    try:
        f = console_font(point_size or widget.font().pointSizeF() or None)
        widget.setFont(f)
        # A style-sheet font-family (own or inherited) beats setFont: add a scoped rule that wins.
        name = widget.objectName() or "gbConsoleText"
        widget.setObjectName(name)
        sheet = str(widget.styleSheet() or "")
        if sheet and "{" not in sheet:
            sheet = f"#{name} {{ {sheet} }}"
        rule = f"#{name} {{ font-family: {CONSOLE}; }}"
        if rule not in sheet:
            widget.setStyleSheet((sheet + "\n" if sheet else "") + rule)
        try:
            widget.document().setDefaultFont(f)          # QTextEdit / QPlainTextEdit
        except Exception:
            pass
    except Exception:
        pass
    return widget


def install(app=None):
    """Arial everywhere, normal spacing, real fallbacks on every OS.  Idempotent."""
    try:
        from PyQt6.QtGui import QFont, QFontDatabase
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return None
    app = app or QApplication.instance()
    if app is None:
        return None
    try:
        avail = set(QFontDatabase.families())
    except Exception:
        avail = set()
    for fam, subs in FALLBACKS.items():
        _STATE["resolved"][fam] = _resolve(fam, avail)
        have = list(QFont.substitutes(fam))
        for s in subs:
            if s not in have:
                QFont.insertSubstitution(fam, s)
    f = QFont(app.font())
    size = f.pointSizeF() if f.pointSizeF() > 0 else 10.0
    f = font("ui", size)
    extra = [x for x in (app.font().families() or []) if x not in (UI,) + FALLBACKS[UI]]
    try:
        f.setFamilies([UI] + list(FALLBACKS[UI]) + [x for x in extra if "emoji" in x.lower()])
    except Exception:
        pass
    app.setFont(f)
    _STATE["installed"] = True
    return _STATE["resolved"].get(UI, UI)


def status():
    return {"installed": _STATE["installed"], "resolved": dict(_STATE["resolved"])}
