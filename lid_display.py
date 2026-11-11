"""lid_display.py — laptop lid blanks the panel; Ctrl+Caps Lock is the manual fallback.

GROOVEBOX_LID_DISPLAY_20261111
  * Closing the lid turns the built-in display off (saves power).
  * Opening the lid turns it back on.
  * Ctrl+Caps Lock toggles the same blank/unblank at any time (works even if the
    ACPI lid node is missing).
  * Display control tries, in order: wlr-randr (labwc/wlroots), wlopm, xset dpms,
    then the backlight sysfs. Failures are logged and never raise into the UI.
"""
from __future__ import annotations

import glob
import os
import subprocess
import threading
import time

_LOCK = threading.Lock()
_STATE = {"blanked": False, "last_lid": None, "watcher": None}
_APP_FILTER = None


def _lid_state_path() -> str | None:
    for p in sorted(glob.glob("/proc/acpi/button/lid/*/state")):
        if os.path.isfile(p):
            return p
    return None


def lid_is_closed() -> bool | None:
    """True = closed, False = open, None = unknown (no ACPI lid node)."""
    path = _lid_state_path()
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read().lower()
        if "closed" in text:
            return True
        if "open" in text:
            return False
    except Exception:
        pass
    return None


def _outputs() -> list[str]:
    """Best-effort list of display outputs. Empty means 'let the tool pick the default'."""
    names = []
    try:
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            r = subprocess.run(["wlr-randr"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                for line in (r.stdout or "").splitlines():
                    line = line.strip()
                    if line and not line.startswith(" ") and " " not in line[:1]:
                        # wlr-randr prints the output name as the first token of a non-indented line
                        tok = line.split()[0]
                        if tok and tok not in names:
                            names.append(tok)
    except Exception:
        pass
    return names


def _run(cmd: list[str], timeout: float = 2.0) -> bool:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


def _set_backlight(on: bool) -> bool:
    for path in sorted(glob.glob("/sys/class/backlight/*/brightness")):
        maxp = os.path.join(os.path.dirname(path), "max_brightness")
        try:
            with open(maxp, "r", encoding="ascii") as f:
                mx = max(1, int(f.read().strip() or "1"))
            val = mx if on else 0
            # brightness is often root-only; try and ignore failure
            with open(path, "w", encoding="ascii") as f:
                f.write(str(val))
            return True
        except Exception:
            continue
    return False


def set_display(on: bool) -> bool:
    """Turn the panel on (True) or off (False). Returns True if any method succeeded."""
    ok = False
    outputs = _outputs()
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        if outputs:
            for name in outputs:
                if on:
                    ok = _run(["wlr-randr", "--output", name, "--on"]) or ok
                else:
                    ok = _run(["wlr-randr", "--output", name, "--off"]) or ok
        else:
            # No parsed names: still try the common laptop panel name
            for name in ("eDP-1", "eDP-2", "LVDS-1"):
                if on:
                    if _run(["wlr-randr", "--output", name, "--on"]):
                        ok = True
                        break
                else:
                    if _run(["wlr-randr", "--output", name, "--off"]):
                        ok = True
                        break
        # wlopm (if present) is a simple on/off helper
        if not ok:
            if on:
                ok = _run(["wlopm", "--on", "*"]) or _run(["wlopm", "--on"])
            else:
                ok = _run(["wlopm", "--off", "*"]) or _run(["wlopm", "--off"])
    # X11 / hybrid fallback
    if not ok and os.environ.get("DISPLAY"):
        ok = _run(["xset", "dpms", "force", "on" if on else "off"])
    # Last resort: backlight sysfs (may need permissions)
    if not ok:
        ok = _set_backlight(on)
    with _LOCK:
        _STATE["blanked"] = not on
    return ok


def is_blanked() -> bool:
    with _LOCK:
        return bool(_STATE["blanked"])


def toggle_display() -> bool:
    """Manual toggle (Ctrl+Caps Lock). Returns the new blanked state."""
    blank = not is_blanked()
    set_display(not blank)
    return is_blanked()


def _watch_loop(stop: threading.Event):
    while not stop.is_set():
        closed = lid_is_closed()
        if closed is not None:
            with _LOCK:
                prev = _STATE["last_lid"]
                _STATE["last_lid"] = closed
            if prev is not None and closed != prev:
                # closed → blank; open → unblank
                set_display(not closed)
        stop.wait(0.4)


def start_watcher() -> None:
    """Start the background lid watcher (idempotent)."""
    with _LOCK:
        if _STATE["watcher"] is not None:
            return
        stop = threading.Event()
        t = threading.Thread(target=_watch_loop, args=(stop,), name="lid-display", daemon=True)
        _STATE["watcher"] = (t, stop)
        t.start()


class _CtrlCapsFilter:
    """Application-wide filter: Ctrl+Caps Lock toggles the panel."""
    def __init__(self, app):
        self.app = app

    def eventFilter(self, obj, event):
        try:
            from PyQt6.QtCore import QEvent, Qt
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                mods = event.modifiers()
                if key == Qt.Key.Key_CapsLock and (mods & Qt.KeyboardModifier.ControlModifier):
                    toggle_display()
                    return True
        except Exception:
            pass
        return False


def install(app) -> None:
    """Install the lid watcher and the Ctrl+Caps Lock fallback on a QApplication."""
    if app is None:
        return
    start_watcher()
    global _APP_FILTER
    if _APP_FILTER is None:
        try:
            _APP_FILTER = _CtrlCapsFilter(app)
            app.installEventFilter(_APP_FILTER)
        except Exception:
            _APP_FILTER = None


# Help / UI strings (single source so the README and the button stay in sync)
HELP_SNIPPET = (
    "Laptop lid & display power\n"
    "  Closing the lid blanks the built-in display (saves power). Opening the lid\n"
    "  turns it back on. Ctrl+Caps Lock toggles the same blank/unblank at any time\n"
    "  (works even if the ACPI lid switch is not visible). The button next to Help\n"
    "  shows the current state and the same shortcut."
)

BUTTON_LABEL = "💻 Lid / Ctrl+Caps"
BUTTON_TOOLTIP = (
    "Laptop lid blanks the display to save power. "
    "Ctrl+Caps Lock toggles the same blank/unblank. "
    "Click to toggle now."
)
