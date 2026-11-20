"""GROOVEBOX_R124_DEVICE_PROFILES: desktop / laptop / tablet / small-screen layout profiles.

``detect(app)`` picks a profile from the screen (logical size, DPI) and input devices (touch screen,
stylus); ``apply(app, name)`` sets the shared knobs every surface already reads:
    tablet_mode (tablet keyboard), tablet_kb_scale, touch_alt_drag, ui_scale hint, smooth_mode
The choice is stored in QSettings key ``device_profile`` ("auto" = detect on every start).
"""
from __future__ import annotations

PROFILES = {
    "desktop": {"tablet_mode": "off", "tablet_kb_scale": 1.0, "touch_alt_drag": False, "ui_scale": 1.0, "smooth_mode": None},
    "laptop": {"tablet_mode": "auto", "tablet_kb_scale": 1.0, "touch_alt_drag": False, "ui_scale": 1.0, "smooth_mode": None},
    "tablet": {"tablet_mode": "on", "tablet_kb_scale": 1.15, "touch_alt_drag": True, "ui_scale": 1.15, "smooth_mode": "on"},
    "small": {"tablet_mode": "auto", "tablet_kb_scale": 0.85, "touch_alt_drag": False, "ui_scale": 0.9, "smooth_mode": "on"},
}


def _settings():
    from PyQt6.QtCore import QSettings
    return QSettings("MathematiciansGroovebox", "UI")


def has_touch():
    try:
        from PyQt6.QtGui import QInputDevice
        return any(d.type() in (QInputDevice.DeviceType.TouchScreen,) for d in QInputDevice.devices())
    except Exception:
        return False


def detect(app=None):
    try:
        from PyQt6.QtWidgets import QApplication
        scr = (app.screen() if app is not None else None) or QApplication.primaryScreen()
        g = scr.availableGeometry(); w, h = g.width(), g.height()
        dpi = float(scr.logicalDotsPerInch() or 96.0)
    except Exception:
        return "desktop"
    if has_touch() and min(w, h) <= 1200:
        return "tablet"
    if w < 1280 or h < 720:
        return "small"
    if has_touch() or dpi >= 120 or w <= 1920:
        return "laptop"
    return "desktop"


def chosen():
    return str(_settings().value("device_profile", "auto") or "auto")


def apply(app, name=None, persist=False):
    name = name or chosen()
    if name == "auto":
        name = detect(app)
    p = PROFILES.get(name, PROFILES["desktop"])
    s = _settings()
    s.setValue("tablet_mode", p["tablet_mode"]); s.setValue("tablet_kb_scale", p["tablet_kb_scale"])
    s.setValue("touch_alt_drag", "1" if p["touch_alt_drag"] else "0"); s.setValue("ui_scale_hint", p["ui_scale"])
    if persist:
        s.setValue("device_profile", name)
    if p.get("smooth_mode"):
        try:
            import compat_settings as cs
            if cs.load().get("smooth_mode") in (None, "", "auto"):
                cs.update(smooth_mode=p["smooth_mode"])
        except Exception:
            pass
    try:
        import tablet_keyboard as tk
        kb = getattr(app, "tablet_keyboard", None)
        if kb is not None and hasattr(kb, "apply_mode"):
            kb.apply_mode()
        elif kb is None and p["tablet_mode"] == "on":
            tk.install(app)
    except Exception:
        pass
    app._r124_device_profile = name
    return name
