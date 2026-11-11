"""game_playability.py — GROOVEBOX_R32_PLAYABILITY_20261109

Player-facing controls for the seeded games.  One shared settings dict (saved with the
compatibility settings) that the game loop reads every tick:

    speed          0.25..3.0   game-time multiplier (slow-motion ↔ fast)
    gravity        0.25..3.0   gravity_scale on the planetary / avatar physics
    thrust         0.25..3.0   thrust_gain multiplier
    drag           0..0.5      extra velocity damping per second
    bounce         0..1.5      restitution scale on collisions
    assist         0..1        aim / landing assist amount
    lives          1..9
    control_scheme wasd | arrows | mouse | gamepad
    invert_y       bool
    slowmo_key     one key (default "Shift") held for 0.3× time
    pause_key      default "P"
    checkpoints    bool — respawn at the last safe spot instead of the start
    screen_shake   0..1

``apply_to_world(world, settings)`` pushes the physical parameters onto any world object
that has them (PlanetaryWorld, avatars); ``dt_scaled`` is what the loop should step with.
"""
from __future__ import annotations

import json
import os

DEFAULTS = {"speed": 1.0, "gravity": 1.0, "thrust": 1.0, "drag": 0.0, "bounce": 1.0, "assist": 0.25, "lives": 3,
            "control_scheme": "wasd", "invert_y": False, "slowmo_key": "Shift", "pause_key": "P",
            "checkpoints": True, "screen_shake": 0.5}
SETTINGS = dict(DEFAULTS)
_SCHEMES = ("wasd", "arrows", "mouse", "gamepad")
_HELD = {"slowmo": False}


def _path():
    try:
        import groovebox_paths
        base = groovebox_paths.base_dir()
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".groovebox")
    return os.path.join(base, "game-playability.json")


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            SETTINGS.update(clean(raw))
    except Exception:
        pass
    return SETTINGS


def save():
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, indent=2)
    except Exception:
        pass


def clean(raw):
    out = {}
    for key, lo, hi in (("speed", 0.25, 3.0), ("gravity", 0.25, 3.0), ("thrust", 0.25, 3.0), ("drag", 0.0, 0.5),
                        ("bounce", 0.0, 1.5), ("assist", 0.0, 1.0), ("screen_shake", 0.0, 1.0)):
        if key in raw:
            try:
                out[key] = max(lo, min(hi, float(raw[key])))
            except Exception:
                pass
    if "lives" in raw:
        try:
            out["lives"] = max(1, min(9, int(raw["lives"])))
        except Exception:
            pass
    if str(raw.get("control_scheme", "")).lower() in _SCHEMES:
        out["control_scheme"] = str(raw["control_scheme"]).lower()
    for key in ("invert_y", "checkpoints"):
        if key in raw:
            out[key] = bool(raw[key])
    for key in ("slowmo_key", "pause_key"):
        if key in raw and str(raw[key]).strip():
            out[key] = str(raw[key]).strip()[:12]
    return out


def set_slowmo(held):
    _HELD["slowmo"] = bool(held)


def dt_scaled(dt):
    """The game-time step for a real-time dt."""
    s = float(SETTINGS.get("speed", 1.0))
    if _HELD["slowmo"]:
        s *= 0.3
    return float(dt) * s


def apply_to_world(world):
    """Push physics settings onto any object exposing the usual attributes (no-op otherwise)."""
    if world is None:
        return
    try:
        if hasattr(world, "gravity_scale"):
            base = getattr(world, "_base_gravity_scale", None)
            if base is None:
                base = world._base_gravity_scale = float(getattr(world, "gravity_scale", 1.0) or 1.0)
            world.gravity_scale = base * float(SETTINGS["gravity"])
        if hasattr(world, "thrust_gain"):
            base = getattr(world, "_base_thrust_gain", None)
            if base is None:
                base = world._base_thrust_gain = float(getattr(world, "thrust_gain", 8.0) or 8.0)
            world.thrust_gain = base * float(SETTINGS["thrust"])
        if hasattr(world, "drag"):
            world.drag = max(float(getattr(world, "drag", 0.0) or 0.0), float(SETTINGS["drag"]))
        if hasattr(world, "restitution"):
            base = getattr(world, "_base_restitution", None)
            if base is None:
                base = world._base_restitution = float(getattr(world, "restitution", 0.8) or 0.8)
            world.restitution = base * float(SETTINGS["bounce"])
    except Exception:
        pass


def key_map():
    """Movement keys for the chosen scheme: {'up','down','left','right','action','jump'}."""
    s = SETTINGS.get("control_scheme", "wasd")
    if s == "arrows":
        return {"up": "Up", "down": "Down", "left": "Left", "right": "Right", "action": "Space", "jump": "Return"}
    if s == "mouse":
        return {"up": "W", "down": "S", "left": "A", "right": "D", "action": "MouseLeft", "jump": "Space"}
    if s == "gamepad":
        return {"up": "PadUp", "down": "PadDown", "left": "PadLeft", "right": "PadRight", "action": "PadA", "jump": "PadB"}
    return {"up": "W", "down": "S", "left": "A", "right": "D", "action": "Space", "jump": "E"}


def assist_vector(aim, target, amount=None):
    """Blend the player's aim toward the target by the assist amount (deterministic, no RNG)."""
    a = float(SETTINGS["assist"] if amount is None else amount)
    try:
        return tuple(float(x) + (float(y) - float(x)) * a * 0.5 for x, y in zip(aim, target))
    except Exception:
        return aim


# ---------------------------------------------------------------------------
# Qt panel
# ---------------------------------------------------------------------------
def make_panel(parent=None, on_change=None):
    from PyQt6.QtWidgets import (QGroupBox, QGridLayout, QLabel, QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox,
                                 QLineEdit, QPushButton)
    load()
    box = QGroupBox("🎮 Playability", parent)
    g = QGridLayout(box)
    widgets = {}

    def changed(*_):
        save()
        if on_change:
            try:
                on_change(dict(SETTINGS))
            except Exception:
                pass

    r = 0
    for key, cap, lo, hi, step in (("speed", "Game speed ×", 0.25, 3.0, 0.05), ("gravity", "Gravity ×", 0.25, 3.0, 0.05),
                                   ("thrust", "Thrust ×", 0.25, 3.0, 0.05), ("drag", "Drag", 0.0, 0.5, 0.01),
                                   ("bounce", "Bounce ×", 0.0, 1.5, 0.05), ("assist", "Assist", 0.0, 1.0, 0.05),
                                   ("screen_shake", "Screen shake", 0.0, 1.0, 0.05)):
        sp = QDoubleSpinBox(); sp.setRange(lo, hi); sp.setSingleStep(step); sp.setValue(float(SETTINGS[key])); sp.setKeyboardTracking(False)
        sp.valueChanged.connect(lambda v, k=key: (SETTINGS.__setitem__(k, float(v)), changed()))
        g.addWidget(QLabel(cap), r // 2, (r % 2) * 2); g.addWidget(sp, r // 2, (r % 2) * 2 + 1)
        widgets[key] = sp; r += 1
    lives = QSpinBox(); lives.setRange(1, 9); lives.setValue(int(SETTINGS["lives"]))
    lives.valueChanged.connect(lambda v: (SETTINGS.__setitem__("lives", int(v)), changed()))
    g.addWidget(QLabel("Lives"), r // 2, (r % 2) * 2); g.addWidget(lives, r // 2, (r % 2) * 2 + 1); r += 1
    scheme = QComboBox(); scheme.addItems([s.upper() for s in _SCHEMES]); scheme.setCurrentIndex(_SCHEMES.index(SETTINGS["control_scheme"]))
    scheme.currentIndexChanged.connect(lambda i: (SETTINGS.__setitem__("control_scheme", _SCHEMES[i]), changed()))
    g.addWidget(QLabel("Controls"), r // 2, (r % 2) * 2); g.addWidget(scheme, r // 2, (r % 2) * 2 + 1); r += 1
    row = (r + 1) // 2
    inv = QCheckBox("Invert Y"); inv.setChecked(bool(SETTINGS["invert_y"])); inv.toggled.connect(lambda v: (SETTINGS.__setitem__("invert_y", bool(v)), changed()))
    chk = QCheckBox("Checkpoints"); chk.setChecked(bool(SETTINGS["checkpoints"])); chk.toggled.connect(lambda v: (SETTINGS.__setitem__("checkpoints", bool(v)), changed()))
    g.addWidget(inv, row, 0); g.addWidget(chk, row, 1)
    slow = QLineEdit(SETTINGS["slowmo_key"]); slow.setMaximumWidth(80); slow.setToolTip("Hold for 0.3× time")
    slow.editingFinished.connect(lambda: (SETTINGS.__setitem__("slowmo_key", slow.text().strip() or "Shift"), changed()))
    pause = QLineEdit(SETTINGS["pause_key"]); pause.setMaximumWidth(60)
    pause.editingFinished.connect(lambda: (SETTINGS.__setitem__("pause_key", pause.text().strip() or "P"), changed()))
    g.addWidget(QLabel("Slow-mo key"), row, 2); g.addWidget(slow, row, 3)
    g.addWidget(QLabel("Pause key"), row + 1, 2); g.addWidget(pause, row + 1, 3)
    reset = QPushButton("Reset playability")
    reset.clicked.connect(lambda: (SETTINGS.update(DEFAULTS), save(), _refresh(widgets, lives, scheme, inv, chk, slow, pause), changed()))
    g.addWidget(reset, row + 1, 0, 1, 2)
    return box


def _refresh(widgets, lives, scheme, inv, chk, slow, pause):
    for k, sp in widgets.items():
        sp.blockSignals(True); sp.setValue(float(SETTINGS[k])); sp.blockSignals(False)
    lives.setValue(int(SETTINGS["lives"])); scheme.setCurrentIndex(_SCHEMES.index(SETTINGS["control_scheme"]))
    inv.setChecked(bool(SETTINGS["invert_y"])); chk.setChecked(bool(SETTINGS["checkpoints"]))
    slow.setText(SETTINGS["slowmo_key"]); pause.setText(SETTINGS["pause_key"])


def open_window(app=None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
    win = getattr(app, "_playability_window", None) if app is not None else None
    try:
        if win is not None:
            win.isVisible()
    except RuntimeError:
        win = None
    if win is None:
        win = QWidget(app, Qt.WindowType.Window)
        win.setWindowTitle("🎮 Game Playability")
        lay = QVBoxLayout(win)
        lay.addWidget(QLabel("Settings apply to every seeded game immediately and are saved for next time."))
        lay.addWidget(make_panel(win))
        lay.addStretch(1)
        win.resize(640, 360)
        if app is not None:
            app._playability_window = win
    win.show(); win.raise_(); win.activateWindow()
    return win


load()
