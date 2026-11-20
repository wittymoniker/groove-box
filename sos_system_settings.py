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

def _int_or_auto(v):
    """BOOT_AUTO_R6: sos.ui_scale=auto / sos.threads=auto mean 0 (= resolve automatically); int('auto') used to
    raise and the boot-menu choice was silently dropped."""
    return 0 if str(v).strip().lower() in ("auto", "") else int(v)


BOOT_KEYS = {
    "ui_scale": _int_or_auto, "window_scale": _int_or_auto, "smooth_mode": str, "threads": _int_or_auto, "audio_rate": str, "scene_size": str,
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
    "Tablet": {"smooth_mode": "on", "threads": 2, "scene_size": "720p", "audio_latency": "high", "ui_scale": 125},
    "Laptop": {"smooth_mode": "auto", "threads": 0, "scene_size": "720p", "audio_latency": "auto"},
    "Desktop": {"smooth_mode": "off", "threads": 0, "scene_size": "1080p", "audio_latency": "low"},
    "Low-power laptop": {"smooth_mode": "on", "threads": 8, "scene_size": "720p", "audio_latency": "high"},
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
        d = __import__("safe_io").load_json(_settings_file(), encoding="utf-8")
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d):
    try:
        os.makedirs(os.path.dirname(_settings_file()), exist_ok=True)
        __import__("safe_io").atomic_write_json(_settings_file(), d, indent=2, encoding="utf-8")
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
        if __import__("sos_tools").which("swaybg") and (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland"):
            subprocess.run(["pkill", "-x", "swaybg"], capture_output=True, timeout=2)
            subprocess.Popen(["swaybg", "-i", path, "-m", mode], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if __import__("sos_tools").which("feh"):
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


_WINDOW = None   # SYSTEM_SETTINGS_LAUNCHER_20261112: strong ref -- a parentless window opened from the startup
                 # chooser (app=None) was garbage-collected the moment the button handler returned.


def open_window(app=None, parent=None):
    """Open (or raise) the one System Settings window. Safe from the startup chooser, the main window,
    the Quick Rack, Ctrl+, and the command palette."""
    try:
        return _open_window(app, parent)
    except Exception:
        import traceback
        traceback.print_exc()
        raise


def _open_window(app=None, parent=None):
    global _WINDOW
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QPushButton, QLabel, QComboBox, QSpinBox,
                                 QCheckBox, QTextEdit, QScrollArea, QDoubleSpinBox, QHBoxLayout)
    import compat_settings as cs
    win = (getattr(app, "_sos_settings_window", None) if app is not None else None) or _WINDOW
    try:
        if win is not None:
            win.isVisible()
    except RuntimeError:
        win = None
    if win is not None:
        win.show(); win.raise_(); win.activateWindow(); return win
    # Parentless top-level window so a modal startup dialog cannot swallow it.
    win = QWidget(None, Qt.WindowType.Window); win.setWindowTitle("🖥 System Settings · sOS / desktop")
    win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    win.resize(720, 760)
    outer = QVBoxLayout(win); scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); scroll.setWidget(body)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
    cb_smooth = QComboBox(); cb_smooth.addItems(["auto", "on", "off"]); cb_smooth.setCurrentText(str(st.get("smooth_mode", "auto") or "auto"))
    sp_thr = QSpinBox(); sp_thr.setRange(0, 64); sp_thr.setSpecialValueText("auto"); sp_thr.setValue(int(st.get("threads", 0)))
    cb_rate = QComboBox(); cb_rate.addItems(["auto", "44100", "48000"]); cb_rate.setCurrentText(str(st.get("audio_rate", "auto")))
    cb_size = QComboBox(); cb_size.addItems(["auto", "720p", "1080p", "native"]); cb_size.setCurrentText(str(st.get("scene_size", "auto") or "auto"))
    cb_lat = QComboBox(); cb_lat.addItems(["auto", "low", "high"]); cb_lat.setCurrentText(str(st.get("audio_latency", "auto") or "auto"))
    cb_worker = QComboBox(); cb_worker.addItems(["adaptive", "balanced", "video", "memory"]); cb_worker.setCurrentText(str(st.get("worker_mode", "adaptive") or "adaptive"))
    sp_swap = QDoubleSpinBox(); sp_swap.setRange(0.25, 4.0); sp_swap.setSingleStep(0.25); sp_swap.setValue(float(st.get("swap_limit", 1.0)))
    chk_all = QCheckBox("Play on every output (HDMI + speakers)"); chk_all.setChecked(bool(st.get("play_all_outputs", True)))
    chk_chime = QCheckBox("Startup chime"); chk_chime.setChecked(bool(st.get("startup_chime", True)))
    chk_native = QCheckBox("Native voice kernel"); chk_native.setChecked(bool(st.get("native_voice", True)))
    chk_smart = QCheckBox("Smart process (migratory threads)"); chk_smart.setChecked(bool(st.get("smart_process", True)))
    chk_export = QCheckBox("Export in worker process"); chk_export.setChecked(bool(st.get("export_in_worker", True)))
    chk_autosave = QCheckBox("Autosave"); chk_autosave.setChecked(bool(st.get("autosave", True)))
    cb_hw = QComboBox(); cb_hw.addItems(["auto", "tablet", "laptop", "desktop"])
    cb_hw.setCurrentText(str(st.get("hardware_class", "auto")))
    cb_hw.setToolTip("auto detects tablet / laptop / desktop and applies a safe profile.")
    def _apply_hw():
        import compat_settings as _cs
        kind = cb_hw.currentText()
        kind, prof = _cs.apply_hardware_class(None if kind == "auto" else kind)
        out.setPlainText("Applied %s profile\n%s" % (kind, "\n".join("%s=%s" % kv for kv in prof.items()) if isinstance(prof, dict) else prof))
    b_hw = QPushButton("Apply hardware profile")
    b_hw.clicked.connect(_apply_hw)
    form.addRow("Hardware class", cb_hw)
    form.addRow("", b_hw)
    cb_comp = QComboBox(); cb_comp.addItems(["protected", "global50", "direct"])
    cb_comp.setToolTip("How the composition engine shares control with you. Protected keeps your edits.")
    cb_out = QComboBox(); cb_out.addItems(["all devices", "selected only", "player for files"])
    cb_out.setCurrentText("selected only" if not st.get("play_all_outputs", True) else "all devices")
    cb_out.setToolTip("Output route. All devices is safest across HDMI and speakers.")
    def _apply_style():
        if app is not None:
            try:
                import canonical_mode as cm
                cm.apply(app, cb_comp.currentText())
            except Exception:
                pass
        cur = cs.update(play_all_outputs=cb_out.currentText() != "selected only",
                        audio_via_video_player=cb_out.currentText() == "player for files") or cs.load()
        cs.apply_env(cur)
        out.setPlainText("Composition %s · output %s" % (cb_comp.currentText(), cb_out.currentText()))
    b_style = QPushButton("Apply composition / output style")
    b_style.clicked.connect(_apply_style)
    form.addRow("Composition style", cb_comp)
    form.addRow("Output style", cb_out)
    form.addRow("", b_style)
    cb_quality = QComboBox(); cb_quality.addItems(["balanced", "max", "compatibility"]); cb_quality.setCurrentText(str(st.get("thread_quality", "balanced")))
    cb_quality.setToolTip("max: all threads, low latency. compatibility: fewer threads, high latency, smooth on. balanced: automatic.")
    cb_profile = QComboBox(); cb_profile.addItems(["auto", "latitude", "tablet", "desktop", "studio"]); cb_profile.setCurrentText(str(st.get("compat_profile", "auto")))
    cb_profile.setToolTip("Hardware compatibility profile. Latitude is tuned for the Dell 3510.")
    for cap, w in (("Thread quality", cb_quality), ("Compatibility profile", cb_profile), ("UI scale %", sp_ui), ("Window scale %", sp_win), ("Smooth mode", cb_smooth), ("Threads", sp_thr),
                   ("Audio rate", cb_rate), ("Scene size", cb_size), ("Audio latency", cb_lat), ("Worker mode", cb_worker),
                   ("Swap limit × RAM", sp_swap)):
        form.addRow(cap, w)
    for w in (chk_all, chk_chime, chk_native, chk_smart, chk_export, chk_autosave):
        form.addRow("", w)
    # PARTY_MODE_SETTINGS_20261112: the toggle + intensity the docs promised (party_mode / party_intensity).
    from PyQt6.QtWidgets import QSlider
    chk_party = QCheckBox("Party Mode (contextual visuals + UI sounds that show what you are composing)")
    chk_party.setChecked(bool(st.get("party_mode", True)))
    chk_party_snd = QCheckBox("Party sounds (UI sounds tuned to the project: stochastic energy + resampling)")
    chk_party_snd.setChecked(bool(st.get("party_sounds", True)))
    # PARTY_DEFAULT_R6: 0.001 % resolution (any level is exact); PARTY_DEFAULT_R7: default 50 %.
    sl_party = QSlider(Qt.Orientation.Horizontal); sl_party.setRange(0, 100000); sl_party.setSingleStep(10); sl_party.setPageStep(1000)
    sl_party.setValue(int(round(float(st.get("party_intensity", 50.0)) * 1000)))
    sl_party.setToolTip("Party Mode level, 0-100 % in 0.001 % steps (default 50 %)")
    lbl_party = QLabel("%.3f %%" % (sl_party.value() / 1000.0))
    party_row = QHBoxLayout(); party_row.addWidget(sl_party, 1); party_row.addWidget(lbl_party)

    def _party_live(*_a):
        lbl_party.setText("%.3f %%" % (sl_party.value() / 1000.0))
        cs.update(party_mode=chk_party.isChecked(), party_intensity=sl_party.value() / 1000.0,
                  party_sounds=chk_party_snd.isChecked())
        try:
            import party_overlay
            party_overlay.refresh()
        except Exception:
            pass
        try:
            btn = getattr(app, "btn_party", None) if app is not None else None
            if btn is not None and btn.isChecked() != chk_party.isChecked():
                btn.blockSignals(True); btn.setChecked(chk_party.isChecked()); btn.blockSignals(False)
        except Exception:
            pass
    chk_party.toggled.connect(_party_live); sl_party.valueChanged.connect(_party_live); chk_party_snd.toggled.connect(_party_live)
    form.addRow("", chk_party); form.addRow("Party level", party_row); form.addRow("", chk_party_snd)
    chk_emoji = QCheckBox("Emoji labels (buttons, tabs, titles; applies to windows opened after saving)")   # EMOJI_UI_R7
    chk_emoji.setChecked(bool(st.get("emoji_labels", True)))
    form.addRow("", chk_emoji)
    chk_math_bg = QCheckBox("Window backgrounds on every window (mathematical field, or your image / GIF)")
    chk_math_bg.setChecked(bool(st.get("math_background_enabled", True)))
    chk_math_bg.setToolTip("Seeded math graphics behind every window, painted on a background thread (the UI thread only "
                           "shows finished frames). Choose an image or animated GIF below to use it instead.")
    form.addRow("", chk_math_bg)
    _bg_row = QWidget(body); _bg_l = QHBoxLayout(_bg_row); _bg_l.setContentsMargins(0, 0, 0, 0)
    _bg_lbl = QLabel(os.path.basename(str(st.get("window_background_image", "") or "")) or "mathematical field")
    _bg_pick = QPushButton("🖼 Image / GIF…"); _bg_clear = QPushButton("∑ Math field"); _bg_make = QPushButton("🎞 Make a GIF…")
    _bg_make.setToolTip("Turn any video or image sequence into a looping GIF (File Converter) and use it as the background")
    _bg_state = {"path": str(st.get("window_background_image", "") or "")}
    def _bg_apply(pth):
        _bg_state["path"] = pth or ""
        _bg_lbl.setText(os.path.basename(pth) if pth else "mathematical field")
        try:
            cs.update(window_background_image=_bg_state["path"], math_background_enabled=True)
            import groovebox as _gbm
            _gbm.refresh_window_backgrounds(app)
        except Exception as _e:
            print(f"[Background] {_e}")
    def _bg_choose():
        from PyQt6.QtWidgets import QFileDialog as _FD
        pth, _f = _FD.getOpenFileName(win, "Window background", os.path.expanduser("~"),
                                      "Images and GIFs (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if pth:
            _bg_apply(pth)
    def _bg_gif():
        try:
            import format_converter as _fc
            pth = _fc.make_background_gif_dialog(win)
            if pth:
                _bg_apply(pth)
        except Exception as _e:
            print(f"[Background] GIF maker: {_e}")
    _bg_pick.clicked.connect(_bg_choose); _bg_clear.clicked.connect(lambda: _bg_apply("")); _bg_make.clicked.connect(_bg_gif)
    for _w in (_bg_lbl, _bg_pick, _bg_make, _bg_clear):
        _bg_l.addWidget(_w)
    form.addRow("Window background", _bg_row)
    sp_wait = QDoubleSpinBox(); sp_wait.setRange(0.25, 4.0); sp_wait.setSingleStep(0.25); sp_wait.setDecimals(2)
    sp_wait.setValue(float(st.get("wait_factor", 1.0))); sp_wait.setSuffix(" ×")
    sp_wait.setToolTip("How long hardware checks (audio cards, PipeWire, devices) keep trying before giving up. Every "
                       "check still ends the moment the device is ready; raise this only for slow or unusual hardware.")
    sp_wait.valueChanged.connect(lambda v: cs.update(wait_factor=float(v)))
    form.addRow("Hardware wait", sp_wait)
    # GROOVEBOX_R123_MOUSE_TRACER_20261119: pointer trail (default ON) — saved immediately.
    def _mt_upd(**kw):
        cs.update(**kw)
        try:
            __import__("mouse_tracer").reload_settings()
        except Exception:
            pass
    _mt_row = QWidget(body); _mt_l = QHBoxLayout(_mt_row); _mt_l.setContentsMargins(0, 0, 0, 0)
    chk_mt = QCheckBox("Show"); chk_mt.setChecked(bool(st.get("mouse_tracer", True)))
    chk_mt.setToolTip("A subtle fading trail behind the pointer inside Groovebox windows. Clicks pass through.")
    cb_mt_mode = QComboBox(); cb_mt_mode.addItems(["trail", "ring", "trail+ring"])
    cb_mt_mode.setCurrentText(str(st.get("mouse_tracer_mode", "trail")))
    sp_mt_len = QSpinBox(); sp_mt_len.setRange(4, 256); sp_mt_len.setValue(int(st.get("mouse_tracer_length", 48))); sp_mt_len.setPrefix("len ")
    sp_mt_fade = QSpinBox(); sp_mt_fade.setRange(100, 5000); sp_mt_fade.setSingleStep(50); sp_mt_fade.setValue(int(st.get("mouse_tracer_fade_ms", 600))); sp_mt_fade.setSuffix(" ms")
    sp_mt_w = QSpinBox(); sp_mt_w.setRange(1, 24); sp_mt_w.setValue(int(st.get("mouse_tracer_width", 4))); sp_mt_w.setSuffix(" px")
    b_mt_col = QPushButton("Colour…")
    b_mt_col.setStyleSheet("background:%s; color:#000;" % st.get("mouse_tracer_color", "#4fd1ff"))
    def _mt_col():
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        c = QColorDialog.getColor(QColor(str(cs.load().get("mouse_tracer_color", "#4fd1ff"))), win, "Mouse tracer colour")
        if c.isValid():
            b_mt_col.setStyleSheet("background:%s; color:#000;" % c.name()); _mt_upd(mouse_tracer_color=c.name())
    b_mt_col.clicked.connect(_mt_col)
    chk_mt.toggled.connect(lambda v: _mt_upd(mouse_tracer=bool(v)))
    cb_mt_mode.currentTextChanged.connect(lambda v: _mt_upd(mouse_tracer_mode=v))
    sp_mt_len.valueChanged.connect(lambda v: _mt_upd(mouse_tracer_length=int(v)))
    sp_mt_fade.valueChanged.connect(lambda v: _mt_upd(mouse_tracer_fade_ms=int(v)))
    sp_mt_w.valueChanged.connect(lambda v: _mt_upd(mouse_tracer_width=int(v)))
    for _w in (chk_mt, cb_mt_mode, sp_mt_len, sp_mt_fade, sp_mt_w, b_mt_col):
        _mt_l.addWidget(_w)
    form.addRow("Mouse tracer", _mt_row)
    cb_scroll = QComboBox(); cb_scroll.addItems(["windows", "windows+main", "off"])
    cb_scroll.setCurrentText(str(st.get("scroll_panels", "windows")))
    cb_scroll.setToolTip("windows: tool windows scroll when their content does not fit · windows+main: compatibility mode, "
                         "the main window also scrolls across all its panels (restart) · off: never wrap")
    cb_scroll.currentTextChanged.connect(lambda v: __import__("window_scroll").set_mode(v))
    form.addRow("Scroll panels", cb_scroll)
    # UI_PANES_R6: window pane formats (sizes, order, stacked / side by side, docks) for every window.
    try:
        import ui_panels_ui as _upu
        form.addRow("Window panes", _upu.compact_row(app, body))
    except Exception as _pe:
        form.addRow("Window panes", QLabel(f"unavailable: {_pe}"))
    # SCRIPT_STUDIO_R7: the OS text editor for seed-language compositions
    _b_ss = QPushButton("✍ Open Script Studio")
    _b_ss.setToolTip("Write seed compositions with a workspace variables reference, evaluate / sweep them, "
                     "and send them to the project seed.")
    _b_ss.clicked.connect(lambda: __import__("script_studio").open_window(app))
    form.addRow("Script Studio", _b_ss)
    lay.addLayout(form)
    # LANE_READOUT_R6: what the thread pools are doing right now (busiest lanes, caller-runs count, waits).
    lbl_lanes = QLabel(""); lbl_lanes.setWordWrap(True); lbl_lanes.setStyleSheet("color:#9fb4c8; font-family:Consolas;")
    lay.addWidget(lbl_lanes)

    def _lanes_tick():
        if not win.isVisible():
            return
        try:
            import thread_budget as _tb
            rep = _tb.lane_report(5)
            b = rep["budget"]
            rows = [f"workers {b['total_workers']} (bulk {b['bulk_workers']} · interactive {b['interactive_workers']}) · "
                    f"running {rep['running'].get('bulk', 0)}/{rep['running'].get('interactive', 0)} · lanes {rep['lane_count']}"]
            for r in rep["lanes"]:
                rows.append(f"{r['name'][:22]:<22} act {r['active']} q {r['queued']} done {r.get('completed', 0)} "
                            f"inline {r.get('inline', 0)} wait {r.get('wait_s', 0.0):.2f}s run {r.get('run_s', 0.0):.2f}s")
            lbl_lanes.setText("\n".join(rows))
        except Exception as exc:
            lbl_lanes.setText(f"thread lanes: {exc}")
    from PyQt6.QtCore import QTimer as _QT
    _lt = _QT(win); _lt.setInterval(2000); _lt.timeout.connect(_lanes_tick); _lt.start(); _lanes_tick()

    def do_save():
        st2 = cs.load_saved()
        st2.update({"party_mode": chk_party.isChecked(), "party_intensity": sl_party.value() / 1000.0,
                    "party_sounds": chk_party_snd.isChecked(), "emoji_labels": chk_emoji.isChecked(),
                    "math_background_enabled": chk_math_bg.isChecked()})
        st2.update({"ui_scale": sp_ui.value(), "window_scale": sp_win.value(), "smooth_mode": cb_smooth.currentText(),
                    "thread_quality": cb_quality.currentText(), "compat_profile": cb_profile.currentText(),
                    "threads": sp_thr.value(), "audio_rate": cb_rate.currentText(), "scene_size": cb_size.currentText(),
                    "audio_latency": cb_lat.currentText(), "worker_mode": cb_worker.currentText(), "swap_limit": sp_swap.value(),
                    "play_all_outputs": chk_all.isChecked(), "startup_chime": chk_chime.isChecked(),
                    "native_voice": chk_native.isChecked(), "smart_process": chk_smart.isChecked(),
                    "export_in_worker": chk_export.isChecked(), "autosave": chk_autosave.isChecked()})
        ok = cs.save(st2)
        try:
            cs.apply_env(st2)
        except Exception:
            pass
        if not ok:
            out.setPlainText("Could NOT write the settings file:\n" + cs.settings_path())
            return
        try:
            import sys as _sys_bg
            _gb_bg = _sys_bg.modules.get("groovebox")
            if _gb_bg is not None and hasattr(_gb_bg, "set_window_backgrounds_enabled"):
                _gb_bg.set_window_backgrounds_enabled(chk_math_bg.isChecked())
        except Exception:
            pass
        out.setPlainText("Saved. Scale changes apply at the next launch.\n\n" + "\n".join(cs.describe(st2)))

    # GROOVEBOX_LID_DISPLAY_20261111
    try:
        import lid_display as _lid
        lbl_lid = QLabel(_lid.HELP_SNIPPET.replace("\n", " "))
        lbl_lid.setWordWrap(True); lbl_lid.setMinimumWidth(120)
        b_lid = QPushButton("Toggle display (Ctrl+Caps Lock)")
        b_lid.clicked.connect(lambda: b_lid.setText("Display off" if _lid.toggle_display() else "Toggle display (Ctrl+Caps Lock)"))
        form.addRow("Lid / display power", lbl_lid)
        form.addRow("", b_lid)
    except Exception:
        pass

    b_save = QPushButton("💾 Save && apply"); b_save.clicked.connect(do_save)
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
    from PyQt6.QtWidgets import QGridLayout
    row2 = QGridLayout()          # 3 columns: six buttons in one row forced horizontal scrolling
    _row2_items = [b_save, b_both, b_upd, b_boot, b_sys]
    for i, b in enumerate(_row2_items):
        row2.addWidget(b, i // 3, i % 3)
    lay.addLayout(row2)
    out = QTextEdit(); out.setReadOnly(True); out.setStyleSheet("font-family:Consolas;font-size:9pt;")
    out.setPlainText("\n".join(cs.describe(st)))
    lay.addWidget(out, 1)
    def _checklist():
        lines = ["On-device checklist"]
        try:
            from drive_guard import system_disks, assert_safe_target
            lines.append("OS disks locked: " + (", ".join(sorted(system_disks())) or "(none detected)"))
            try:
                assert_safe_target("/dev/nvme0n1")
                lines.append("WARN: nvme0n1 was not refused")
            except Exception as exc:
                lines.append("nvme0n1 refused: " + str(exc)[:80])
        except Exception as exc:
            lines.append("drive guard: " + str(exc))
        try:
            import seed_media_bridge as smb
            pkt = smb.identity_packet(app or {"seed": 1, "seed_script": "return 1"})
            lines.append("seed packet: " + str(pkt.get("fingerprint")))
        except Exception as exc:
            lines.append("seed packet: " + str(exc))
        try:
            import r32_finish as rf
            d = rf._store("export_queue")
            probe = os.path.join(d, "_checklist.json")
            with open(probe, "w", encoding="utf-8") as f:
                f.write('{"ok": true}')
            os.remove(probe)
            lines.append("export resume folder writable: " + d)
        except Exception as exc:
            lines.append("export resume: " + str(exc))
        try:
            from operation_station_transfer import verify_iso_builder
            r = verify_iso_builder()
            lines.append("ISO builder: " + ("OK" if r.get("ok") else "missing") + " · " + "; ".join(r.get("notes") or []))
        except Exception as exc:
            lines.append("ISO builder: " + str(exc))
        lines.append("Auto-retry is on by default; pause it in Export Jobs if a path keeps failing.")
        out.setPlainText("\n".join(lines))
    b_check = QPushButton("Run checklist")
    b_check.setToolTip("Confirm the OS disk is locked, the seed packet builds, and export resume can write.")
    b_check.clicked.connect(_checklist)
    row2.addWidget(b_check, len(_row2_items) // 3, len(_row2_items) % 3)
    if app is not None:
        app._sos_settings_window = win
    _WINDOW = win
    win.show(); win.raise_(); win.activateWindow(); return win


def _both_now():
    try:
        import audio_both_output as abo
        w, p, _t = abo.install()
        return ("Written to %s" % p if w else "Unchanged (%s)" % (p or "no ALSA cards")) + "\n" + \
               "\n".join("%-22s %s" % (d, l) for d, l in abo.choices())
    except Exception as exc:
        return "failed: %s" % exc
