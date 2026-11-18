"""power_clock.py — battery level and system time in the main window, setting the clock, battery protection.

Status bar item "🔋 82 % · 14:05" (⚡ while charging). Click it to set the date / time (timedatectl, or date -s;
through pkexec / sudo when not root) and the battery thresholds (System Settings keys battery_warn_pct = 20,
battery_critical_pct = 8, battery_action = notify | autosave | autosave+export).

While discharging:  ≤ warn      → a notice in the status line (once per discharge);
                    ≤ critical  → the project is autosaved, and with autosave+export an export of it is queued at once,
                                  so it finishes while there is still charge (once per discharge).
The battery is read from /sys/class/power_supply every 30 s (a few tiny file reads); nothing else runs.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import time


def battery():
    """(percent | None, charging bool, present bool)."""
    for b in sorted(glob.glob("/sys/class/power_supply/BAT*")):
        try:
            cap = int(open(os.path.join(b, "capacity")).read().strip())
            st = open(os.path.join(b, "status")).read().strip().lower()
            return cap, st in ("charging", "full", "not charging"), True
        except Exception:
            continue
    return None, True, False


def _settings():
    try:
        import compat_settings as cs
        s = cs.load()
    except Exception:
        s = {}
    return (int(s.get("battery_warn_pct", 20) or 20), int(s.get("battery_critical_pct", 8) or 8),
            str(s.get("battery_action", "autosave+export") or "autosave+export"))


def set_system_time(text):
    """text 'YYYY-MM-DD HH:MM[:SS]' → set the clock. Returns (ok, message)."""
    t = text.strip()
    if len(t) == 16:
        t += ":00"
    cmds = []
    if __import__("sos_tools").which("timedatectl"):
        cmds.append(["timedatectl", "set-ntp", "false"])
        cmds.append(["timedatectl", "set-time", t])
    else:
        cmds.append(["date", "-s", t])
    pre = [] if (hasattr(os, "geteuid") and os.geteuid() == 0) else (["pkexec"] if __import__("sos_tools").which("pkexec") else ["sudo", "-n"])
    for c in cmds:
        __import__("sos_tools").check_privileged(c)
        r = subprocess.run(pre + c, capture_output=True, text=True, timeout=30)
        if r.returncode != 0 and c[1] != "set-ntp":
            return False, (r.stderr or r.stdout or "could not set the time").strip()[-200:]
    if __import__("sos_tools").which("hwclock"):
        subprocess.run(pre + ["hwclock", "--systohc"], capture_output=True, timeout=30)
    return True, "clock set to " + t


def install(app):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QToolButton
    if getattr(app, "_power_clock", None) is not None:
        return app._power_clock
    btn = QToolButton(app)
    btn.setAutoRaise(True)
    btn.setToolTip("Battery and system time · click to set the clock and the battery protection")
    btn.setStyleSheet("QToolButton{color:#d8f3ff;font-weight:800;padding:0 8px;}")
    state = {"warned": False, "acted": False}

    def tick():
        cap, charging, present = battery()
        clock = time.strftime("%H:%M")
        if present and cap is not None:
            btn.setText("%s %d %% · %s" % ("⚡" if charging else ("🪫" if cap <= 15 else "🔋"), cap, clock))
        else:
            btn.setText("🔌 · " + clock)
        if not present or cap is None:
            return
        if charging:
            state["warned"] = state["acted"] = False
            return
        warn, crit, action = _settings()
        lbl = getattr(app, "scope_status_label", None)
        if cap <= crit and not state["acted"]:
            state["acted"] = True
            msg = "🪫 Battery %d %% — " % cap
            if action in ("autosave", "autosave+export"):
                try:
                    app._autosave_project(); msg += "project autosaved"
                except Exception as exc:
                    msg += "autosave failed (%s)" % exc
            if action == "autosave+export":
                try:
                    import os as _os
                    out = app._export_name("battery-save", ".wav", app._exports_dir())
                    app._export_scheduler().submit_job("audio_file", out, {"audio_format": "wav"},
                                                       label="battery save · %s" % _os.path.basename(out))
                    msg += " · export queued"
                except Exception as exc:
                    msg += " · export not queued (%s)" % exc
            if lbl is not None:
                lbl.setText(msg)
            print("[Power] " + msg)
        elif cap <= warn and not state["warned"]:
            state["warned"] = True
            if lbl is not None:
                lbl.setText("🔋 Battery %d %% — plug in soon (at %d %% the project is saved%s)" % (
                    cap, crit, " and exported" if action == "autosave+export" else ""))

    def dialog():
        from PyQt6.QtWidgets import (QComboBox, QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
                                     QVBoxLayout)
        warn, crit, action = _settings()
        d = QDialog(app); d.setWindowTitle("🕒 Time · 🔋 Battery")
        lay = QVBoxLayout(d); f = QFormLayout(); lay.addLayout(f)
        when = QLineEdit(time.strftime("%Y-%m-%d %H:%M:%S")); f.addRow("Date and time", when)
        b_set = QPushButton("Set the clock"); out = QLabel(""); f.addRow("", b_set); f.addRow("", out)
        sw = QSpinBox(); sw.setRange(5, 60); sw.setValue(warn); sw.setSuffix(" %")
        sc = QSpinBox(); sc.setRange(2, 30); sc.setValue(crit); sc.setSuffix(" %")
        ac = QComboBox(); ac.addItems(["notify", "autosave", "autosave+export"]); ac.setCurrentText(action)
        f.addRow("Warn at", sw); f.addRow("Protect at", sc); f.addRow("Protection", ac)
        b_set.clicked.connect(lambda: out.setText(set_system_time(when.text())[1]))

        def _save():
            try:
                import compat_settings as cs
                cs.update(battery_warn_pct=int(sw.value()), battery_critical_pct=int(sc.value()),
                          battery_action=ac.currentText())
            except Exception:
                pass
            d.accept()
        ok = QPushButton("Save"); ok.clicked.connect(_save); lay.addWidget(ok)
        d.open()
    btn.clicked.connect(dialog)
    t = QTimer(app); t.setInterval(30000); t.timeout.connect(tick); t.start()
    tick()
    try:
        app.statusBar().addPermanentWidget(btn)
        app.statusBar().show()
    except Exception:
        pass
    app._power_clock = (btn, t)
    return app._power_clock
