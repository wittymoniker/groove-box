"""sos_system_settings.py — GROOVEBOX_R32_SOS_SETTINGS_20261109

More to do in sOS, before and after boot:

* Limine boot menu options → compatibility settings.  ``compat_settings.boot_overrides`` now
  reads every ``sos.<key>=<value>`` on the kernel command line (ui_scale, window_scale,
  smooth_mode, threads, audio_rate, scene_size, play_all_outputs, startup_chime, worker_mode,
  audio_latency, native_voice, smart_process, background).  ``limine_entries()`` writes the
  matching menu entries so each preset is one keypress at boot.
* Pre-boot code update: ``sos.update=1`` (or the "Update code from USB" entry) makes the
  early-boot hook look for ``GROOVEBOX_UPDATE/MATH_GROOVEBOX*.zip|.tar.gz`` on removable
  media and unpack it over the app overlay before Groovebox starts (``preboot_update_script``
  is the shell text that the initramfs stamp copies to /usr/bin/sos-preboot-update).
* Desktop background: a custom image chosen on the startup screen (or any time from
  System Settings); applied with swaybg / labwc and remembered.
* System Settings window: background, screen scale, audio defaults (Both outputs), process
  limits, swap, autosave, update-from-USB now, show boot options.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

BOOT_KEYS = {
    "ui_scale": int, "window_scale": int, "smooth_mode": str, "threads": int, "audio_rate": str, "scene_size": str,
    "play_all_outputs": lambda v: str(v).lower() in ("1", "true", "on", "yes"),
    "startup_chime": lambda v: str(v).lower() in ("1", "true", "on", "yes"),
    "worker_mode": str, "audio_latency": str,
    "native_voice": lambda v: str(v).lower() in ("1", "true", "on", "yes"),
    "smart_process": lambda v: str(v).lower() in ("1", "true", "on", "yes"),
    "background": str, "update": lambda v: str(v).lower() in ("1", "true", "on", "yes", "auto"),
}

PRESETS = {
    "Default": {},
    "Small screen (125 %)": {"ui_scale": 125, "window_scale": 100},
    "Large screen (90 % window)": {"ui_scale": 100, "window_scale": 90},
    "Low-power laptop": {"smooth_mode": "on", "threads": 4, "scene_size": "720p", "audio_latency": "high"},
    "Studio (all threads, 1080p)": {"smooth_mode": "off", "threads": 0, "scene_size": "1080p", "audio_latency": "low"},
    "Quiet start (no chime, single output)": {"startup_chime": 0, "play_all_outputs": 0},
    "Update code from USB": {"update": 1},
}


def parse_cmdline(text):
    out = {}
    for tok in str(text or "").split():
        if not tok.startswith("sos."):
            continue
        key, _, val = tok[4:].partition("=")
        conv = BOOT_KEYS.get(key)
        if conv is None:
            continue
        try:
            out[key] = conv(val)
        except Exception:
            pass
    return out


def limine_entries(kernel="boot():/vmlinuz", initrd="boot():/initrd.img", base_cmdline="quiet splash"):
    """Limine config text with one entry per preset (appended to the ISO's limine.cfg)."""
    lines = ["# GROOVEBOX_R32_SOS_SETTINGS_20261109 — compatibility presets chosen at boot"]
    for name, opts in PRESETS.items():
        extra = " ".join("sos.%s=%s" % (k, ("1" if v is True else "0" if v is False else v)) for k, v in opts.items())
        lines += [":Groovebox sOS · %s" % name, "    PROTOCOL=linux", "    KERNEL_PATH=%s" % kernel,
                  "    MODULE_PATH=%s" % initrd, "    CMDLINE=%s %s" % (base_cmdline, extra), ""]
    return "\n".join(lines)


PREBOOT_UPDATE_SCRIPT = r"""#!/bin/sh
# sos-preboot-update — GROOVEBOX_R32_SOS_SETTINGS_20261109
# Runs before Groovebox starts when the kernel command line has sos.update=1 (or always
# when GROOVEBOX_UPDATE/ exists on a removable drive).  Unpacks the newest
# MATH_GROOVEBOX*.zip / .tar.gz over the app overlay, keeping a rollback copy.
set -u
APP="${GROOVEBOX_APP_DIR:-/opt/groovebox/app}"
WANT=0
grep -q 'sos.update=\(1\|auto\|on\|true\)' /proc/cmdline 2>/dev/null && WANT=1
for dev in /dev/sd[a-z][0-9]* /dev/mmcblk[0-9]p[0-9]* /dev/nvme[0-9]n[0-9]p[0-9]*; do
  [ -b "$dev" ] || continue
  mnt="/run/sos-update-$(basename "$dev")"; mkdir -p "$mnt"
  mount -o ro "$dev" "$mnt" 2>/dev/null || { rmdir "$mnt" 2>/dev/null; continue; }
  if [ -d "$mnt/GROOVEBOX_UPDATE" ]; then
    pkg=$(ls -t "$mnt"/GROOVEBOX_UPDATE/MATH_GROOVEBOX*.zip "$mnt"/GROOVEBOX_UPDATE/MATH_GROOVEBOX*.tar.gz 2>/dev/null | head -n1)
    if [ -n "$pkg" ] && { [ "$WANT" = 1 ] || [ -f "$mnt/GROOVEBOX_UPDATE/AUTO" ]; }; then
      # GROOVEBOX_R32_SIGNED_UPDATES_20261110: with a trusted key installed only signed packages apply
      VER=""; for v in /usr/lib/sos/update_signing.py "$APP/update_signing.py"; do [ -s "$v" ] && { VER="$v"; break; }; done
      if [ -n "$VER" ]; then
        msg=$(python3 "$VER" verify "$pkg" 2>&1); rc=$?
        echo "[sos-preboot-update] $msg"
        if [ "$rc" != 0 ]; then umount "$mnt" 2>/dev/null; rmdir "$mnt" 2>/dev/null; continue; fi
      elif [ -s /etc/groovebox/update-signing.pub ] || [ -s /var/lib/groovebox-system/update-signing.pub ]; then
        echo "[sos-preboot-update] REFUSED: a trusted update key is installed but the verifier is missing"
        umount "$mnt" 2>/dev/null; rmdir "$mnt" 2>/dev/null; continue
      fi
      echo "[sos-preboot-update] applying $pkg to $APP"
      ts=$(date +%Y%m%d-%H%M%S); RB="$APP.rollback"; mountpoint -q /var/lib/groovebox-system 2>/dev/null && RB=/var/lib/groovebox-system/rollback
      mkdir -p "$RB"; tar -C "$APP" -cf "$RB/$ts.tar" . 2>/dev/null; ls -1t "$RB"/*.tar 2>/dev/null | tail -n +4 | xargs -r rm -f
      tmp=$(mktemp -d)
      case "$pkg" in
        *.zip) unzip -q "$pkg" -d "$tmp" ;;
        *) tar -xzf "$pkg" -C "$tmp" ;;
      esac
      src=$(find "$tmp" -maxdepth 2 -type d -name 'MATH_GROOVEBOX-v3' | head -n1); [ -n "$src" ] || src="$tmp"
      cp -a "$src"/. "$APP"/ && echo "$pkg $ts" >> "$APP/.sos-updates.log"
      find "$APP" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null
      rm -rf "$tmp"
      echo "[sos-preboot-update] done (rollback: $RB/$ts.tar, newest 3 kept)"
    fi
  fi
  umount "$mnt" 2>/dev/null; rmdir "$mnt" 2>/dev/null
done
exit 0
"""


def _settings_file():
    try:
        import groovebox_paths
        return os.path.join(groovebox_paths.base_dir(), "sos-system.json")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".groovebox", "sos-system.json")


def load():
    try:
        with open(_settings_file(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d):
    try:
        os.makedirs(os.path.dirname(_settings_file()), exist_ok=True)
        with open(_settings_file(), "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass


def set_background(path, mode="fill"):
    """Remember and apply a desktop background image (labwc/wlroots via swaybg; X11 via feh)."""
    d = load()
    if path:
        d["background"] = str(path)
        d["background_mode"] = mode
    save(d)
    return apply_background()


def apply_background():
    d = load()
    path = d.get("background") or os.environ.get("GROOVEBOX_BACKGROUND", "")
    if not path or not os.path.isfile(path) or not sys.platform.startswith("linux"):
        return False
    mode = d.get("background_mode", "fill")
    try:
        if shutil.which("swaybg") and (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland"):
            subprocess.run(["pkill", "-x", "swaybg"], capture_output=True, timeout=2)
            subprocess.Popen(["swaybg", "-i", path, "-m", mode], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if shutil.which("feh"):
            subprocess.Popen(["feh", "--bg-%s" % ("fill" if mode == "fill" else "center"), path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception:
        return False
    return False


def pick_background(parent=None):
    from PyQt6.QtWidgets import QFileDialog
    p, _ = QFileDialog.getOpenFileName(parent, "Desktop background image", os.path.expanduser("~"),
                                       "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
    if p:
        set_background(p)
    return p


def run_update_now():
    """Apply a GROOVEBOX_UPDATE package from a mounted removable drive right now (sOS)."""
    script = "/usr/bin/sos-preboot-update"
    head = ""
    try:
        import update_signing
        head = update_signing.status() + "\n"
    except Exception:
        pass
    if os.path.isfile(script):
        r = subprocess.run(["sudo", "-n", script], capture_output=True, text=True, timeout=600)
        return head + (r.stdout or "") + (r.stderr or "")
    return head + "sos-preboot-update is not installed on this system (desktop build)."


def open_window(app=None, parent=None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QPushButton, QLabel, QComboBox, QSpinBox,
                                 QCheckBox, QTextEdit, QScrollArea, QDoubleSpinBox, QHBoxLayout)
    import compat_settings as cs
    win = getattr(app, "_sos_settings_window", None) if app is not None else None
    try:
        if win is not None:
            win.isVisible()
    except RuntimeError:
        win = None
    if win is not None:
        win.show(); win.raise_(); return win
    win = QWidget(parent or app, Qt.WindowType.Window); win.setWindowTitle("🖥 System Settings · sOS / desktop")
    win.resize(720, 760)
    outer = QVBoxLayout(win); scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); scroll.setWidget(body)
    outer.addWidget(scroll); lay = QVBoxLayout(body)
    st = cs.load(); sysd = load()
    form = QFormLayout()
    lbl_bg = QLabel(sysd.get("background") or "(default)"); lbl_bg.setWordWrap(True)
    b_bg = QPushButton("Choose desktop background…")
    b_bg.clicked.connect(lambda: (lbl_bg.setText(pick_background(win) or lbl_bg.text())))
    b_bg_clear = QPushButton("Default background"); b_bg_clear.clicked.connect(lambda: (save({**load(), "background": ""}), lbl_bg.setText("(default)")))
    row = QHBoxLayout(); row.addWidget(b_bg); row.addWidget(b_bg_clear)
    form.addRow("Background", lbl_bg); form.addRow("", row)
    sp_ui = QSpinBox(); sp_ui.setRange(0, 300); sp_ui.setSpecialValueText("auto"); sp_ui.setValue(int(st.get("ui_scale", 100)))
    sp_win = QSpinBox(); sp_win.setRange(50, 100); sp_win.setValue(int(st.get("window_scale", 100)))
    cb_smooth = QComboBox(); cb_smooth.addItems(["auto", "on", "off"]); cb_smooth.setCurrentText(st.get("smooth_mode", "auto"))
    sp_thr = QSpinBox(); sp_thr.setRange(0, 64); sp_thr.setSpecialValueText("auto"); sp_thr.setValue(int(st.get("threads", 0)))
    cb_rate = QComboBox(); cb_rate.addItems(["auto", "44100", "48000"]); cb_rate.setCurrentText(str(st.get("audio_rate", "auto")))
    cb_size = QComboBox(); cb_size.addItems(["auto", "720p", "1080p", "native"]); cb_size.setCurrentText(st.get("scene_size", "auto"))
    cb_lat = QComboBox(); cb_lat.addItems(["auto", "low", "high"]); cb_lat.setCurrentText(st.get("audio_latency", "auto"))
    cb_worker = QComboBox(); cb_worker.addItems(["adaptive", "balanced", "video", "memory"]); cb_worker.setCurrentText(st.get("worker_mode", "adaptive"))
    sp_swap = QDoubleSpinBox(); sp_swap.setRange(0.25, 4.0); sp_swap.setSingleStep(0.25); sp_swap.setValue(float(st.get("swap_limit", 1.0)))
    chk_all = QCheckBox("Play on every output (HDMI + speakers)"); chk_all.setChecked(bool(st.get("play_all_outputs", True)))
    chk_chime = QCheckBox("Startup chime"); chk_chime.setChecked(bool(st.get("startup_chime", True)))
    chk_native = QCheckBox("Native voice kernel"); chk_native.setChecked(bool(st.get("native_voice", True)))
    chk_smart = QCheckBox("Smart process (migratory threads)"); chk_smart.setChecked(bool(st.get("smart_process", True)))
    chk_export = QCheckBox("Export in worker process"); chk_export.setChecked(bool(st.get("export_in_worker", True)))
    chk_autosave = QCheckBox("Autosave"); chk_autosave.setChecked(bool(st.get("autosave", True)))
    for cap, w in (("UI scale %", sp_ui), ("Window scale %", sp_win), ("Smooth mode", cb_smooth), ("Threads", sp_thr),
                   ("Audio rate", cb_rate), ("Scene size", cb_size), ("Audio latency", cb_lat), ("Worker mode", cb_worker),
                   ("Swap limit × RAM", sp_swap)):
        form.addRow(cap, w)
    for w in (chk_all, chk_chime, chk_native, chk_smart, chk_export, chk_autosave):
        form.addRow("", w)
    lay.addLayout(form)

    def do_save():
        st2 = cs.load()
        st2.update({"ui_scale": sp_ui.value(), "window_scale": sp_win.value(), "smooth_mode": cb_smooth.currentText(),
                    "threads": sp_thr.value(), "audio_rate": cb_rate.currentText(), "scene_size": cb_size.currentText(),
                    "audio_latency": cb_lat.currentText(), "worker_mode": cb_worker.currentText(), "swap_limit": sp_swap.value(),
                    "play_all_outputs": chk_all.isChecked(), "startup_chime": chk_chime.isChecked(),
                    "native_voice": chk_native.isChecked(), "smart_process": chk_smart.isChecked(),
                    "export_in_worker": chk_export.isChecked(), "autosave": chk_autosave.isChecked()})
        cs.save(st2)
        try:
            cs.apply_env(st2)
        except Exception:
            pass
        out.setPlainText("Saved. Scale changes apply at the next launch.\n\n" + cs.describe(st2))

    # GROOVEBOX_LID_DISPLAY_20261111
    try:
        import lid_display as _lid
        lbl_lid = QLabel(_lid.HELP_SNIPPET.replace("\n", " "))
        lbl_lid.setWordWrap(True)
        b_lid = QPushButton("Toggle display (Ctrl+Caps Lock)")
        b_lid.clicked.connect(lambda: b_lid.setText("Display off" if _lid.toggle_display() else "Toggle display (Ctrl+Caps Lock)"))
        form.addRow("Lid / display power", lbl_lid)
        form.addRow("", b_lid)
    except Exception:
        pass

    b_save = QPushButton("💾 Save & apply"); b_save.clicked.connect(do_save)
    b_both = QPushButton("🔊 Install Both-outputs device now")
    b_both.clicked.connect(lambda: out.setPlainText(_both_now()))
    b_upd = QPushButton("⬆ Update code from USB now"); b_upd.clicked.connect(lambda: out.setPlainText(run_update_now()))
    b_boot = QPushButton("Show Limine boot options"); b_boot.clicked.connect(lambda: out.setPlainText(limine_entries()))
    b_sys = QPushButton("🔒 Protected system store…")

    def _sysstore():
        import groovebox_paths as gp
        st = gp.system_store_status()
        msg = "System files (state, caches, logs, temp) live in:\n  %s\n%s\nThey are hidden from every in-app file picker, share and scan." % (
            st["path"], "on the protected sOS System partition" if st["partition"] else "in a hidden, owner-only folder")
        tool = "/usr/bin/sos-add-system-partition"
        if not st["partition"] and os.path.isfile(tool):
            r = subprocess.run(["sudo", "-n", tool, "--check"], capture_output=True, text=True, timeout=20)
            msg += "\n\nPartition check: " + (r.stdout or r.stderr).strip()
            if r.returncode == 0 and "can add" in r.stdout:
                from PyQt6.QtWidgets import QMessageBox
                if QMessageBox.question(win, "Add protected partition", r.stdout.strip() + "\n\nOnly unallocated space is used; nothing is moved or shrunk. Add it?") == QMessageBox.StandardButton.Yes:
                    r2 = subprocess.run(["sudo", "-n", tool], capture_output=True, text=True, timeout=300)
                    msg += "\n" + (r2.stdout or r2.stderr).strip()
        out.setPlainText(msg)
    b_sys.clicked.connect(_sysstore)
    row2 = QHBoxLayout()
    for b in (b_save, b_both, b_upd, b_boot, b_sys):
        row2.addWidget(b)
    lay.addLayout(row2)
    out = QTextEdit(); out.setReadOnly(True); out.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;")
    out.setPlainText(cs.describe(st))
    lay.addWidget(out, 1)
    if app is not None:
        app._sos_settings_window = win
    win.show(); win.raise_(); return win


def _both_now():
    try:
        import audio_both_output as abo
        w, p, _t = abo.install()
        return ("Written to %s" % p if w else "Unchanged (%s)" % (p or "no ALSA cards")) + "\n" + \
               "\n".join("%-22s %s" % (d, l) for d, l in abo.choices())
    except Exception as exc:
        return "failed: %s" % exc
