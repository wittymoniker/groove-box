"""app_hub.py — 🧩 Apps & Scripts: use sOS / Groovebox as an operating system for other programs and generators.

APPS     Every installed desktop application (.desktop entries: system, user, Flatpak, AppImages installed here) can be
         searched and launched as its own process; running apps are listed with Stop. Launching never blocks the UI.
INSTALL  AppImage (copied to ~/Applications, made executable, given a menu entry — no root needed), a .deb file or
         an apt package name (apt-get via pkexec / sudo), a Flatpak (flatpak install --user). Each method is offered
         only when its tool exists on this machine. Nothing is downloaded or installed without the user's click.
SCRIPTS  Generators that make media for Groovebox to reprocess: Python or shell scripts in ~/Groovebox/Scripts, run in
         a child process with GROOVEBOX_OUT (a fresh output folder), GROOVEBOX_SEED, GROOVEBOX_BPM, GROOVEBOX_BASE_HZ
         and GROOVEBOX_PROJECT in the environment. Their log streams into the window; when a script ends, the files
         it wrote are listed and can be sent back in: audio / video → Live Player media, OBJ → the music video,
         image → window background, anything → the File Converter. Templates make a new script in one click.
"""
from __future__ import annotations

import glob
import os
import shlex
import shutil
import stat
import subprocess
import sys
import time

DESKTOP_DIRS = ("/usr/share/applications", "/usr/local/share/applications",
                os.path.expanduser("~/.local/share/applications"),
                "/var/lib/flatpak/exports/share/applications",
                os.path.expanduser("~/.local/share/flatpak/exports/share/applications"))
APPIMAGE_DIR = os.path.expanduser("~/Applications")
SCRIPTS_DIR = os.path.expanduser("~/Groovebox/Scripts")
RUNS_DIR = os.path.expanduser("~/Groovebox/Script outputs")

TEMPLATES = {
    "Python · tone from a formula (WAV)": '''#!/usr/bin/env python3
# Writes a WAV generated from a formula. Edit f(t) — Groovebox can reprocess the result.
import math, os, struct, wave
out = os.environ.get("GROOVEBOX_OUT", "."); sr = 48000; secs = 8.0
bpm = float(os.environ.get("GROOVEBOX_BPM", "120")); base = float(os.environ.get("GROOVEBOX_BASE_HZ", "432"))
def f(t):
    beat = t * bpm / 60.0
    return 0.4 * math.sin(2 * math.pi * base * t) * (0.5 + 0.5 * math.cos(2 * math.pi * beat))
with wave.open(os.path.join(out, "formula.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(b"".join(struct.pack("<h", int(32767 * max(-1, min(1, f(i / sr))))) for i in range(int(sr * secs))))
print("wrote formula.wav")
''',
    "Python · OBJ model from a seed": '''#!/usr/bin/env python3
# Writes a twisted torus OBJ whose shape follows the seed. It can be put into the music video.
import math, os, hashlib
out = os.environ.get("GROOVEBOX_OUT", "."); seed = os.environ.get("GROOVEBOX_SEED", "0")
k = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % 7 + 2
R, r, n, m = 1.0, 0.35, 64, 24
with open(os.path.join(out, "seed_torus.obj"), "w") as f:
    for i in range(n):
        u = 2 * math.pi * i / n
        for j in range(m):
            v = 2 * math.pi * j / m
            rr = r * (1 + 0.25 * math.sin(k * u))
            f.write("v %f %f %f\\n" % ((R + rr * math.cos(v)) * math.cos(u), (R + rr * math.cos(v)) * math.sin(u), rr * math.sin(v)))
    for i in range(n):
        for j in range(m):
            a = i * m + j + 1; b = ((i + 1) % n) * m + j + 1; c = ((i + 1) % n) * m + (j + 1) % m + 1; d = i * m + (j + 1) % m + 1
            f.write("f %d %d %d %d\\n" % (a, b, c, d))
print("wrote seed_torus.obj with", k, "lobes")
''',
    "Shell · process the newest export with FFmpeg": '''#!/bin/sh
# Reverses and echoes the newest audio export into the output folder (needs ffmpeg).
src=$(ls -t "$HOME"/Groovebox/Exports/*.wav 2>/dev/null | head -1)
[ -n "$src" ] || { echo "no WAV export found"; exit 1; }
ffmpeg -y -i "$src" -af "areverse,aecho=0.8:0.7:120:0.4" "$GROOVEBOX_OUT/processed.wav" && echo "wrote processed.wav"
''',
}


def _field(text, key):
    for ln in text.splitlines():
        if ln.startswith(key + "="):
            return ln.split("=", 1)[1].strip()
    return ""


def _is_this_groovebox_entry(name: str, desktop_path: str, exec_line: str) -> bool:
    """Do not offer the running workstation as an external application.

    Desktop launchers start a fresh process (and may use a different Flatpak
    namespace), so relying only on the process single-instance endpoint is not
    sufficient for this in-app Apps list. Match our own installed desktop IDs
    and the exact product launcher names/commands, not generic audio apps.
    """
    base = os.path.basename(desktop_path).lower()
    if base in {
        "io.github.wittymoniker.mathematiciansgroovebox.desktop",
        "app.wasmer.eski19758.groovebox.desktop",
        "mathematicians-groovebox.desktop", "groovebox.desktop",
    } or ("groovebox" in base and base.endswith(".desktop") and
          any(token in base for token in ("mathematician", "matgroove", "sos", "groovebox"))):
        return True
    if str(name).strip().casefold() in {"mathematician's groovebox", "mathematician’s groovebox"}:
        return True
    try:
        argv = shlex.split(exec_line, posix=(os.name != "nt"))
    except ValueError:
        argv = []
    # Desktop field codes are not executables. Check the first executable token
    # and Flatpak app ID forms used by our two supported desktop packages.
    first = os.path.basename(argv[0]).lower() if argv else ""
    if first in {"mathematicians-groovebox", "groovebox", "groovebox.exe"}:
        return True
    # Catch desktop entries that invoke Python/uv/bash with a script path rather
    # than the product command. Use exact basenames to avoid hiding unrelated
    # applications whose arguments merely mention Groovebox media folders.
    script_names = {"run_groovebox.py", "launch_groovebox.py", "groovebox.py",
                    "LAUNCH_GROOVEBOX.sh".lower(), "launch_entry.sh"}
    if any(os.path.basename(str(token)).lower() in script_names for token in argv[1:]):
        return True
    joined = " ".join(argv).replace("\\", "/").casefold()
    return any(token in joined for token in (
        "app.wasmer.eski19758.groovebox", "io.github.wittymoniker.mathematiciansgroovebox",
        "mathematicians-groovebox", "/opt/groovebox/run_groovebox.py",
    ))


def list_apps():
    """[{name, exec, path, comment}] of external desktop apps, sorted without duplicates."""
    out, seen = [], set()
    for d in DESKTOP_DIRS:
        for p in sorted(glob.glob(os.path.join(d, "*.desktop"))):
            try:
                t = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "[Desktop Entry]" not in t or _field(t, "NoDisplay").lower() == "true" or _field(t, "Type") not in ("", "Application"):
                continue
            name, ex = _field(t, "Name"), _field(t, "Exec")
            if not name or not ex or name in seen or _is_this_groovebox_entry(name, p, ex):
                continue
            seen.add(name)
            out.append({"name": name, "exec": ex, "path": p, "comment": _field(t, "Comment")})
    return sorted(out, key=lambda a: a["name"].lower())


def _clean_exec(ex):
    parts = [x for x in shlex.split(ex) if not (x.startswith("%") and len(x) == 2)]
    return parts


def launch(app_entry_or_argv):
    """Start an application detached from Groovebox's process group; returns the Popen."""
    argv = app_entry_or_argv if isinstance(app_entry_or_argv, list) else _clean_exec(app_entry_or_argv["exec"])
    import app_limits   # external apps stay strictly under the share of CPU / memory (default 0.19758)
    return app_limits.popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True, close_fds=True)


def _priv(cmd):
    __import__("sos_tools").check_privileged(cmd)   # R101: never hand a system file to a root command
    try:
        __import__("accounts").require("install")    # R101: installs need an owner / member account
    except ImportError:
        pass
    return __import__("sos_tools").root_prefix() + list(cmd)   # R132: sudo first (sOS has no polkit session)


def install_methods():
    w = __import__("sos_tools").which
    m = ["auto", "appimage", "url", "tarball", "run"]          # R132.10: auto detects URL / file / package / Flatpak ID
    if w("apt-get"):
        m += ["deb", "apt", "flatpak-setup"]
    if w("flatpak"):
        m += ["flatpak"]
    if w("pipx") or w("pip3") or w("pip"):
        m += ["pipx"]
    if w("snap"):
        m += ["snap"]
    if w("rpm") or w("alien"):
        m += ["rpm"]
    return m


DOWNLOAD_DIR = os.path.expanduser("~/Downloads/groovebox-installs")
_FLATPAK_ID = r"[A-Za-z][A-Za-z0-9_\-]*(\.[A-Za-z0-9_\-]+){2,}"


def looks_like_url(t):
    t = str(t).strip()
    return t.startswith(("http://", "https://", "ftp://")) or (("/" in t) and not os.path.exists(os.path.expanduser(t))
                                                               and "." in t.split("/")[0] and " " not in t)


def download(url, log=None):
    """R132.10: fetch a URL (bare host/path gets https://) into ~/Downloads/groovebox-installs; returns the file."""
    import urllib.request, urllib.parse
    url = str(url).strip()
    if "://" not in url:
        url = "https://" + url
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "groovebox-installer"})
    with urllib.request.urlopen(req, timeout=60) as r:
        name = os.path.basename(urllib.parse.urlparse(r.geturl()).path) or "download"
        cd = r.headers.get("Content-Disposition") or ""
        if "filename=" in cd:
            name = cd.split("filename=")[-1].strip('"; ')
        dst = os.path.join(DOWNLOAD_DIR, os.path.basename(name))
        with open(dst, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
    if log:
        log("downloaded %s → %s" % (url, dst))
    return dst


def detect_method(target):
    """auto: which installer handles this target."""
    import re as _re
    t = str(target).strip(); low = t.lower()
    if looks_like_url(t) and not low.endswith((".flatpakref", ".flatpakrepo")):
        return "url"
    if low.endswith(".appimage"):
        return "appimage"
    if low.endswith(".deb"):
        return "deb"
    if low.endswith(".rpm"):
        return "rpm"
    if low.endswith((".flatpakref", ".flatpak", ".flatpakrepo")):
        return "flatpak"
    if low.endswith((".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar.zst", ".zip")):
        return "tarball"
    if low.endswith((".run", ".sh", ".bin")):
        return "run"
    if low.endswith(".whl") or low.startswith(("pip:", "pypi:")):
        return "pipx"
    if low.startswith("snap:"):
        return "snap"
    if _re.fullmatch(_FLATPAK_ID, t):
        return "flatpak"
    return "apt"


def install_tarball(path):
    """Unpack into ~/.local/opt/<name>; link executables found at the top / bin into ~/.local/bin."""
    name = os.path.basename(path)
    for ext in (".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar.zst", ".zip"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
    dst = os.path.expanduser("~/.local/opt/" + name)
    os.makedirs(dst, exist_ok=True)
    shutil.unpack_archive(path, dst)
    bindir = os.path.expanduser("~/.local/bin"); os.makedirs(bindir, exist_ok=True)
    linked = []
    for root, _d, files in os.walk(dst):
        if root.count(os.sep) - dst.count(os.sep) > 2:
            continue
        for f in files:
            fp = os.path.join(root, f)
            if os.access(fp, os.X_OK) and not f.endswith((".so", ".sh.in")) and ".so." not in f:
                ln = os.path.join(bindir, f)
                if not os.path.exists(ln):
                    os.symlink(fp, ln); linked.append(ln)
    return dst, linked


def install_appimage(path):
    os.makedirs(APPIMAGE_DIR, exist_ok=True)
    dst = os.path.join(APPIMAGE_DIR, os.path.basename(path))
    shutil.copy2(path, dst)
    os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    name = os.path.splitext(os.path.basename(path))[0]
    d = os.path.expanduser("~/.local/share/applications")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "groovebox-appimage-%s.desktop" % name.replace(" ", "_")), "w", encoding="utf-8") as f:
        f.write("[Desktop Entry]\nType=Application\nName=%s\nExec=%s\nCategories=Groovebox;\n" % (name, shlex.quote(dst)))
    return dst


def install_cmd(method, target):
    if method == "deb":
        return _priv(["apt-get", "install", "-y", os.path.abspath(target)])
    if method == "apt":
        _pkg = str(target).strip()
        import re as _re
        if not _re.fullmatch(r"[a-z0-9][a-z0-9+.\-]{0,127}(=[A-Za-z0-9.+:~\-]+)?", _pkg):   # R101: a package name, nothing else
            raise ValueError("not a valid package name: %r" % _pkg)
        return _priv(["apt-get", "install", "-y", _pkg])
    if method == "flatpak":
        t = str(target).strip()
        if os.path.isfile(t):
            return ["flatpak", "install", "--user", "-y", ("--from" if t.endswith((".flatpakref", ".flatpakrepo")) else "--bundle"), t]
        return ["flatpak", "install", "--user", "-y", "--noninteractive", "flathub", t]
    if method == "flatpak-setup":          # flatpak + Flathub remote, so Flatpak IDs (e.g. net.agalwood.Motrix) work
        return ["sh", "-c", " ".join(_priv(["apt-get", "install", "-y", "flatpak"])) +
                " && flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"]
    if method == "rpm":
        return _priv(["sh", "-c", "cd /tmp && alien -i --scripts " + shlex.quote(os.path.abspath(target))])
    if method == "pipx":
        t = str(target).strip().split(":", 1)[-1] if str(target).lower().startswith(("pip:", "pypi:")) else str(target).strip()
        w = __import__("sos_tools").which
        return (["pipx", "install", t] if w("pipx") else [("pip3" if w("pip3") else "pip"), "install", "--user", "--break-system-packages", t])
    if method == "snap":
        return _priv(["snap", "install", str(target).strip().split(":", 1)[-1]])
    if method == "run":
        os.chmod(target, os.stat(target).st_mode | stat.S_IXUSR)
        return [os.path.abspath(target)]
    raise ValueError(method)


def new_script(template_name):
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    body = TEMPLATES[template_name]
    ext = ".sh" if body.startswith("#!/bin/sh") else ".py"
    base = template_name.split("·")[-1].strip().split(" ")[0].lower()
    p = os.path.join(SCRIPTS_DIR, "%s-%s%s" % (base, time.strftime("%Y%m%d-%H%M%S"), ext))
    with open(p, "w", encoding="utf-8") as f:
        f.write(body)
    os.chmod(p, 0o755)
    return p


def script_env(app, outdir):
    env = dict(os.environ)
    env["GROOVEBOX_OUT"] = outdir
    for key, get in (("GROOVEBOX_SEED", lambda: app._seed_text()), ("GROOVEBOX_BPM", lambda: app.spin_bpm.value()),
                     ("GROOVEBOX_BASE_HZ", lambda: app.spin_base_frequency.value()),
                     ("GROOVEBOX_PROJECT", lambda: getattr(app, "_current_project_path", "") or "")):
        try:
            env[key] = str(get())
        except Exception:
            pass
    return env


def script_argv(path):
    return [sys.executable, path] if path.endswith(".py") else ["/bin/sh", path]


def send_back(app, path):
    """Route a generated file back into Groovebox by type. Returns a description."""
    low = path.lower()
    if low.endswith(".obj"):
        paths = list(getattr(app, "video_obj_paths", None) or [])
        if path not in paths:
            paths.append(path)
        app.video_obj_paths = paths[:9]
        if not getattr(app, "video_obj_path", ""):
            app.video_obj_path = path
        return "OBJ added to the music video"
    if low.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        import compat_settings as cs
        cs.update(window_background_image=path, math_background_enabled=True)
        try:
            import groovebox as gb
            gb.refresh_window_backgrounds(app)
        except Exception:
            pass
        return "image set as the window background"
    if low.endswith((".wav", ".flac", ".mp3", ".ogg", ".mgr", ".mp4", ".mkv", ".webm", ".mov")):
        import live_player as lp
        w = lp.open_live_player(app)
        try:
            w.load_media(path)
        except Exception:
            pass
        return "loaded into the Live Player"
    try:
        import format_converter  # noqa: F401
    except Exception:
        pass
    return "kept in " + os.path.dirname(path)


def open_window(app=None):
    from PyQt6.QtCore import QProcess, Qt, QTimer
    from PyQt6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                                 QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget)
    old = getattr(app, "_app_hub_window", None) if app is not None else None
    try:
        if old is not None:
            old.show(); old.raise_(); return old
    except RuntimeError:
        pass
    w = QWidget(app, Qt.WindowType.Window) if app is not None else QWidget()
    w.setWindowTitle("🧩 Apps & Scripts · launch, install, generate"); w.resize(860, 560)
    tabs = QTabWidget(); QVBoxLayout(w).addWidget(tabs)
    running = []

    # --- Apps ---------------------------------------------------------------------------------------------------------
    ta = QWidget(); la = QVBoxLayout(ta); tabs.addTab(ta, "Apps")
    flt = QLineEdit(); flt.setPlaceholderText("search applications…"); la.addWidget(flt)
    lst = QListWidget(); la.addWidget(lst, 1)
    ra = QHBoxLayout(); la.addLayout(ra)
    b_launch, b_refresh = QPushButton("▶ Launch"), QPushButton("Refresh")
    run_lst = QListWidget(); run_lst.setMaximumHeight(120)
    b_stop = QPushButton("■ Stop selected")
    for x in (b_launch, b_refresh, b_stop):
        ra.addWidget(x)
    la.addWidget(QLabel("Running")); la.addWidget(run_lst)
    apps = {"all": []}

    def fill():
        apps["all"] = list_apps(); show(flt.text())

    def show(q):
        lst.clear(); q = (q or "").lower()
        for a in apps["all"]:
            if q in a["name"].lower() or q in a["comment"].lower():
                it = QListWidgetItem(a["name"] + ("  ·  " + a["comment"] if a["comment"] else "")); it.setData(Qt.ItemDataRole.UserRole, a)
                lst.addItem(it)

    def do_launch():
        it = lst.currentItem()
        if it is None:
            return
        a = it.data(Qt.ItemDataRole.UserRole)
        try:
            p = launch(a); running.append((a["name"], p)); refresh_running()
        except Exception as exc:
            QMessageBox.warning(w, "Launch", str(exc))

    def refresh_running():
        run_lst.clear()
        for name, p in list(running):
            if p.poll() is not None:
                running.remove((name, p)); continue
            run_lst.addItem("%s · pid %d" % (name, p.pid))

    def do_stop():
        i = run_lst.currentRow()
        live = [(n, p) for n, p in running if p.poll() is None]
        if 0 <= i < len(live):
            try:
                live[i][1].terminate()
            except Exception:
                pass
        QTimer.singleShot(500, refresh_running)
    flt.textChanged.connect(show); b_refresh.clicked.connect(fill); b_launch.clicked.connect(do_launch)
    lst.itemDoubleClicked.connect(lambda _it: do_launch()); b_stop.clicked.connect(do_stop)
    tick = QTimer(w); tick.setInterval(3000); tick.timeout.connect(refresh_running); tick.start()

    # --- Install ------------------------------------------------------------------------------------------------------
    ti = QWidget(); li = QVBoxLayout(ti); tabs.addTab(ti, "Install")
    li.addWidget(QLabel("Install other Linux software. Methods offered on this machine: " + ", ".join(install_methods())))
    ri = QHBoxLayout(); li.addLayout(ri)
    meth = QComboBox(); meth.addItems(install_methods()); target = QLineEdit(); target.setPlaceholderText("auto: URL, file (.AppImage .deb .rpm .tar.gz .run .whl), apt package, Flatpak ID, pip:name, snap:name")
    b_pick, b_inst = QPushButton("File…"), QPushButton("Install")
    for x in (meth, target, b_pick, b_inst):
        ri.addWidget(x)
    ilog = QPlainTextEdit(); ilog.setReadOnly(True); li.addWidget(ilog, 1)
    iproc = {"p": None}

    def pick():
        p, _f = QFileDialog.getOpenFileName(w, "Package", os.path.expanduser("~"), "Packages (*.AppImage *.appimage *.deb *.flatpakref *.flatpak);;All files (*)")
        if p:
            target.setText(p)
            meth.setCurrentText("appimage" if p.lower().endswith(".appimage") else ("deb" if p.endswith(".deb") else meth.currentText()))

    def do_install():
        m, t = meth.currentText(), target.text().strip()
        if not t:
            return
        if m == "auto":
            m = detect_method(t); ilog.appendPlainText("auto → %s" % m)
        if m == "url" or (m in ("appimage", "deb", "tarball", "run", "rpm") and looks_like_url(t)):
            try:
                t = download(t, ilog.appendPlainText)
            except Exception as exc:
                ilog.appendPlainText("⚠ download failed: %s" % exc); return
            m = detect_method(t); m = "appimage" if m in ("apt", "url") else m
            target.setText(t)
        if m == "flatpak" and not __import__("sos_tools").which("flatpak"):
            ilog.appendPlainText("Flatpak is not installed — choose 'flatpak-setup' first (installs flatpak + Flathub)."); return
        if m == "tarball":
            try:
                d, ln = install_tarball(t); ilog.appendPlainText("unpacked into %s; linked %s" % (d, ", ".join(ln) or "nothing")); fill()
            except Exception as exc:
                ilog.appendPlainText("⚠ %s" % exc)
            return
        if m == "appimage":
            try:
                ilog.appendPlainText("installed " + install_appimage(t)); fill()
            except Exception as exc:
                ilog.appendPlainText("⚠ %s" % exc)
            return
        if m in ("deb", "apt", "rpm", "snap", "flatpak-setup") and not __import__("sos_tools").ensure_sudo(w, "Installing a system package needs administrator rights."):
            ilog.appendPlainText("not installed (no administrator password)"); return
        try:
            cmd = install_cmd(m, t)
        except Exception as exc:
            ilog.appendPlainText("⚠ %s" % exc); return
        if QMessageBox.question(w, "Install", "Run:\n" + " ".join(cmd)) != QMessageBox.StandardButton.Yes:
            return
        pr = QProcess(w); pr.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        pr.readyReadStandardOutput.connect(lambda: ilog.appendPlainText(bytes(pr.readAllStandardOutput()).decode("utf-8", "replace").rstrip()))
        pr.finished.connect(lambda code, _st: (ilog.appendPlainText("exit %d" % code), fill()))
        pr.start(cmd[0], cmd[1:]); iproc["p"] = pr
    b_pick.clicked.connect(pick); b_inst.clicked.connect(do_install)

    # --- Scripts ------------------------------------------------------------------------------------------------------
    ts = QWidget(); ls = QVBoxLayout(ts); tabs.addTab(ts, "Scripts → media")
    rs = QHBoxLayout(); ls.addLayout(rs)
    tmpl = QComboBox(); tmpl.addItems(list(TEMPLATES)); b_new = QPushButton("New from template")
    b_open = QPushButton("Open folder"); b_run = QPushButton("▶ Run selected")
    for x in (tmpl, b_new, b_open, b_run):
        rs.addWidget(x)
    slst = QListWidget(); ls.addWidget(slst, 1)
    edit = QPlainTextEdit(); edit.setPlaceholderText("select a script to edit it here"); ls.addWidget(edit, 2)
    b_save = QPushButton("💾 Save script"); ls.addWidget(b_save)
    slog = QPlainTextEdit(); slog.setReadOnly(True); slog.setMaximumHeight(120); ls.addWidget(slog)
    outs = QListWidget(); outs.setMaximumHeight(100); ls.addWidget(QLabel("Files it made (double-click: send back into Groovebox)")); ls.addWidget(outs)
    cur = {"path": None, "proc": None}

    def sfill():
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        slst.clear()
        for p in sorted(glob.glob(os.path.join(SCRIPTS_DIR, "*.py")) + glob.glob(os.path.join(SCRIPTS_DIR, "*.sh"))):
            slst.addItem(p)

    def sel(it):
        cur["path"] = it.text()
        try:
            edit.setPlainText(open(cur["path"], encoding="utf-8").read())
        except OSError as exc:
            edit.setPlainText(str(exc))

    def save():
        if cur["path"]:
            with open(cur["path"], "w", encoding="utf-8") as f:
                f.write(edit.toPlainText())
            slog.appendPlainText("saved " + cur["path"])

    def run():
        if not cur["path"]:
            return
        save()
        outdir = os.path.join(RUNS_DIR, "%s-%s" % (os.path.splitext(os.path.basename(cur["path"]))[0], time.strftime("%Y%m%d-%H%M%S")))
        os.makedirs(outdir, exist_ok=True)
        pr = QProcess(w); pr.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        from PyQt6.QtCore import QProcessEnvironment
        env = QProcessEnvironment()
        for k, v in script_env(app, outdir).items():
            env.insert(k, v)
        pr.setProcessEnvironment(env); pr.setWorkingDirectory(outdir)
        pr.readyReadStandardOutput.connect(lambda: slog.appendPlainText(bytes(pr.readAllStandardOutput()).decode("utf-8", "replace").rstrip()))

        def done(code, _st):
            slog.appendPlainText("exit %d · %s" % (code, outdir)); outs.clear()
            for f in sorted(os.listdir(outdir)):
                outs.addItem(os.path.join(outdir, f))
        pr.finished.connect(done)
        argv = script_argv(cur["path"])
        pr.start(argv[0], argv[1:]); cur["proc"] = pr
        slog.appendPlainText("running %s …" % os.path.basename(cur["path"]))

    def back(it):
        try:
            slog.appendPlainText("%s → %s" % (os.path.basename(it.text()), send_back(app, it.text())))
        except Exception as exc:
            slog.appendPlainText("⚠ %s" % exc)
    b_new.clicked.connect(lambda: (sfill(), slst.addItem(new_script(tmpl.currentText())), sfill()))
    b_open.clicked.connect(lambda: launch(["xdg-open", SCRIPTS_DIR]) if __import__("sos_tools").which("xdg-open") else None)
    slst.itemClicked.connect(sel); b_save.clicked.connect(save); b_run.clicked.connect(run); outs.itemDoubleClicked.connect(back)
    fill(); sfill()
    w.show()
    if app is not None:
        app._app_hub_window = w
    return w
