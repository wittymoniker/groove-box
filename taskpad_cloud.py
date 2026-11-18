"""taskpad_cloud.py: the Task Pad as a cloud. More relevant and more used buttons are bigger and brighter.

score = built-in importance (per button) + use (clicks, remembered across sessions, slowly decaying)
  -> font 7.5 .. 11.5 pt, minimum height 26 .. 46 px, border weight
Colour comes from the row's category (Make, Play, Export, Tools, Network, Studio, Manage), on a translucent
background like the other panels. Clicks are counted on the Qt thread and saved in a debounced batch.
"""
from __future__ import annotations

HUES = {"Make": (120, 220, 255), "Play": (120, 255, 170), "Export": (255, 200, 110), "Tools": (190, 170, 255),
        "Network · code": (110, 200, 255), "Studio": (255, 150, 210), "Manage": (170, 230, 210), "Manage ·2": (170, 230, 210)}
IMPORTANCE = {"Play / Stop": 1.0, "Live Player": 0.9, "Export…": 0.9, "Random seed": 0.8, "Configure project": 0.7,
              "Autopilot": 0.7, "Mixer": 0.6, "Files": 0.6, "Settings": 0.6, "Plugins": 0.6, "Mod Path Bay": 0.7,
              "Music video": 0.6, "Mixdown": 0.6, "Multidim": 0.6, "Checkpoints": 0.5, "Windows": 0.5, "Processes": 0.45,
              "Storage": 0.4, "Logs": 0.4}
_STATE = {"usage": None, "dirty": False, "timer": None, "buttons": []}


def _usage():
    if _STATE["usage"] is None:
        try:
            import compat_settings
            _STATE["usage"] = dict(compat_settings.load().get("taskpad_usage") or {})
        except Exception:
            _STATE["usage"] = {}
    return _STATE["usage"]


def _save_later(app):
    from PyQt6.QtCore import QTimer
    _STATE["dirty"] = True
    t = _STATE["timer"]
    if t is None:
        t = _STATE["timer"] = QTimer(app); t.setSingleShot(True); t.setInterval(4000)

        def flush():
            if not _STATE["dirty"]:
                return
            _STATE["dirty"] = False
            data = dict(_usage())
            try:
                import compute, compat_settings
                compute.run("background", compat_settings.update, carrier="settings", taskpad_usage=data)
            except Exception:
                pass
        t.timeout.connect(flush)
    t.start()


def _key(text):
    return "".join(ch for ch in text if ch.isalnum() or ch in " ·/+").strip()


def score(text):
    k = _key(text); imp = max([v for n, v in IMPORTANCE.items() if n.lower() in k.lower()] + [0.3])
    use = float(_usage().get(k, 0.0))
    return min(1.0, 0.65 * imp + 0.35 * min(1.0, use / 40.0))


def style(app, button, category, text, column):
    s = score(text); r, g, b = HUES.get(category, (150, 200, 230))
    pt = 7.5 + 4.0 * s; h = int(26 + 20 * s); alpha_bg = int(60 + 90 * s); border = 1 + int(s > 0.6)
    button.setMinimumHeight(h)
    button.setStyleSheet(
        "QPushButton{background:rgba(%d,%d,%d,%d);color:rgb(%d,%d,%d);border:%dpx solid rgba(%d,%d,%d,%d);"
        "border-radius:%dpx;padding:2px 4px;font-weight:%d;font-size:%.1fpt;}"
        "QPushButton:hover{background:rgba(%d,%d,%d,%d);border-color:rgba(%d,%d,%d,230);}"
        % (r // 6, g // 6, b // 6, alpha_bg, min(255, r + 40), min(255, g + 30), min(255, b + 20), border, r, g, b, int(90 + 120 * s),
           6 + int(4 * s), 900 if s > 0.6 else 700, pt, r // 4, g // 4, b // 4, min(255, alpha_bg + 60), r, g, b))
    k = _key(text)

    def count():
        u = _usage(); u[k] = float(u.get(k, 0.0)) + 1.0
        if len(u) > 400:
            for kk in list(u):
                u[kk] *= 0.9                     # slow decay keeps the cloud current
        _save_later(app)
    button.clicked.connect(count)
    _STATE["buttons"].append((button, category, text, column))
