"""EMOJI_FONTS_R7 — colour emoji on every button, on every OS (Windows, macOS, Linux, the ISO).

Qt draws an emoji with whatever font the widget asks for; when that font has no emoji glyph it falls
back to the platform's choice, which on a bare Linux/ISO session is often a monochrome or missing glyph
(the "tofu" box).  install(app) makes a colour emoji family an explicit fallback everywhere:

1. Fonts shipped next to the app in fonts/ (or $GROOVEBOX_FONTS_DIR) are registered first, so a
   dropped-in NotoColorEmoji / Twemoji file works even with no system font package.
2. The best available colour family is chosen per platform:
   Windows "Segoe UI Emoji", macOS "Apple Color Emoji", Linux "Noto Color Emoji" (the ISO installs
   fonts-noto-color-emoji), then Twemoji / JoyPixels / EmojiOne / Symbola (monochrome, last resort).
3. The application font becomes [ui family, emoji family], and every family used in style sheets gets
   the emoji family as a substitution, so QSS `font-family:` overrides keep their emoji too.

Pure Qt, no platform hooks; safe to call more than once.  status() reports what was chosen.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PREFERRED = {
    "win": ("Segoe UI Emoji", "Segoe UI Symbol"),
    "darwin": ("Apple Color Emoji",),
    "linux": ("Noto Color Emoji",),
}
COMMON = ("Noto Color Emoji", "Twemoji", "Twemoji Mozilla", "JoyPixels", "EmojiOne Color", "Segoe UI Emoji",
          "Apple Color Emoji", "OpenMoji Color", "Noto Emoji", "Symbola")
# Families the app's style sheets name explicitly (plus the generic aliases Qt resolves them through).
QSS_FAMILIES = ("Sans Serif", "sans-serif", "Monospace", "monospace", "Serif", "DejaVu Sans", "DejaVu Sans Mono",
                "Liberation Sans", "Liberation Mono", "Segoe UI", "Arial", "Helvetica", "Helvetica Neue",
                "Consolas", "Courier New", "Menlo", "Monaco", "SF Pro Text", "Ubuntu", "Cantarell", "Inter",
                "Fira Sans", "Fira Code", "JetBrains Mono", "Source Code Pro", "Noto Sans", "Noto Sans Mono",
                "Georgia", "Liberation Serif", "Tinos", "DejaVu Serif", "Cascadia Mono", "Arimo")

_STATUS = {"family": None, "registered": [], "installed": False}


def _platform():
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def font_dirs():
    here = Path(__file__).resolve().parent
    dirs = [here / "fonts", here / "resources" / "fonts"]
    env = os.environ.get("GROOVEBOX_FONTS_DIR")
    if env:
        dirs.insert(0, Path(env))
    try:
        import groovebox_paths as _gp
        dirs.append(Path(_gp.base_dir()) / "fonts")
    except Exception:
        pass
    return [d for d in dirs if d.is_dir()]


def register_bundled():
    """Register every .ttf/.otf/.ttc in the app font folders.  Returns the families they provide."""
    from PyQt6.QtGui import QFontDatabase
    fams = []
    for d in font_dirs():
        for f in sorted(d.iterdir()):
            if f.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            try:
                fid = QFontDatabase.addApplicationFont(str(f))
            except Exception:
                fid = -1
            if fid >= 0:
                got = list(QFontDatabase.applicationFontFamilies(fid))
                fams.extend(got)
                _STATUS["registered"].append((f.name, got))
    return fams


def choose_family(available=None):
    """Best colour emoji family present (bundled fonts count).  None if the system has none at all."""
    if available is None:
        from PyQt6.QtGui import QFontDatabase
        available = set(QFontDatabase.families())
    else:
        available = set(available)
    for fam in PREFERRED.get(_platform(), ()) + COMMON:
        if fam in available:
            return fam
    for fam in sorted(available):                 # any other installed family that calls itself emoji
        if "emoji" in fam.lower():
            return fam
    return None


def install(app=None):
    """Make the colour emoji family the fallback for the whole application.  Idempotent."""
    try:
        from PyQt6.QtGui import QFont
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return None
    app = app or QApplication.instance()
    if app is None:
        return None
    try:                                   # TYPOGRAPHY_R7: Arial everywhere at normal spacing, then emoji fallback
        import typography as _ty
        _ty.install(app)
    except Exception as exc:
        print(f"[Fonts] typography skipped: {exc}")
    if not _STATUS["installed"]:
        try:
            register_bundled()
        except Exception as exc:
            print(f"[Emoji] bundled fonts skipped: {exc}")
    fam = choose_family()
    _STATUS["family"] = fam
    if fam is None:
        print("[Emoji] no colour emoji font found; install fonts-noto-color-emoji or drop one in fonts/")
        _STATUS["installed"] = True
        return None
    try:
        f = QFont(app.font())
        base = [x for x in (f.families() or [f.family()]) if x and x != fam]
        f.setFamilies(base + [fam])
        app.setFont(f)
        for name in set(QSS_FAMILIES) | set(base):
            subs = list(QFont.substitutes(name))
            if fam not in subs:
                QFont.insertSubstitution(name, fam)
    except Exception as exc:
        print(f"[Emoji] fallback not applied: {exc}")
    _STATUS["installed"] = True
    return fam


def status():
    return dict(_STATUS)
