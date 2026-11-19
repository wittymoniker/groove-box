"""manage_windows.py: 15 management windows for the Task Pad "Manage" row.

Every window is the same small machine: a gather() function that runs OFF the Qt thread (compute.run, the
"background" direction) and returns rows, and a commit that fills the table ON the Qt thread. Actions act on the
selected row. Auto-refresh only runs while a window is visible, and never stacks (a refresh in flight is skipped).

  Windows · Processes · Threads & lanes · Memory · Storage · Startup · Plugins · Provenance · Backups ·
  Protection · Network services · Devices · Logs · Shortcuts · Scheduled actions
"""
from __future__ import annotations
import gc
import glob
import os
import signal
import sys
import time

WINDOWS = []          # (key, emoji, title, tip) in display order; filled by @window


def window(key, emoji, title, tip):
    def deco(fn):
        WINDOWS.append((key, emoji, title, tip, fn)); return fn
    return deco


def _data_dir():
    try:
        import groovebox_paths
        return groovebox_paths.base_dir()
    except Exception:
        return os.path.expanduser("~")


def _mb(n):
    return "%.1f MB" % (float(n) / 1048576.0)


def _rss_kb(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except Exception:
        pass
    return 0


# ------------------------------------------------------------------ the shared window
def open_table(app, key, title, columns, gather, actions=(), interval_ms=2000, note=""):
    """gather() -> list of row tuples (runs on a worker). actions: (label, fn(row_tuple) -> str|None)."""
    from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
                                 QLabel, QLineEdit, QHeaderView, QCheckBox)
    reg = getattr(app, "_r101_manage_windows", None)
    if reg is None:
        reg = app._r101_manage_windows = {}
    w = reg.get(key)
    try:
        if w is not None:
            w.show(); w.raise_(); w.activateWindow(); return w
    except RuntimeError:
        pass

    class Bridge(QObject):
        done = pyqtSignal(object, str)

    d = QDialog(app); d.setWindowTitle(title); d.resize(980, 560); d.setWindowModality(Qt.WindowModality.NonModal)
    d.setStyleSheet("QDialog{background:rgba(10,18,26,236);} QLabel{color:#bfe3f2;} QTableWidget{background:rgba(14,26,36,210);"
                    "color:#e2f4ff;gridline-color:#24425a;} QHeaderView::section{background:#132634;color:#9fd8ee;border:0;padding:3px;}"
                    "QPushButton{background:#15293a;color:#dff4ff;border:1px solid #2f5d74;border-radius:6px;padding:4px 8px;}"
                    "QPushButton:hover{background:#1d3a50;border-color:#7fd6ee;}")
    v = QVBoxLayout(d)
    if note:
        lab = QLabel(note); lab.setWordWrap(True); v.addWidget(lab)
    top = QHBoxLayout(); v.addLayout(top)
    flt = QLineEdit(); flt.setPlaceholderText("filter…"); top.addWidget(flt, 1)
    auto = QCheckBox("auto-refresh"); auto.setChecked(interval_ms > 0); top.addWidget(auto)
    status = QLabel(""); top.addWidget(status)
    tab = QTableWidget(0, len(columns)); tab.setHorizontalHeaderLabels(columns)
    tab.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive); tab.horizontalHeader().setStretchLastSection(True)
    tab.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); tab.setSortingEnabled(True); v.addWidget(tab, 1)
    bar = QHBoxLayout(); v.addLayout(bar)
    br = Bridge(d); state = {"busy": False, "rows": []}

    def commit(rows, err):
        state["busy"] = False
        if err:
            status.setText("⚠ " + err[:120]); return
        state["rows"] = rows or []; show()

    def show():
        q = flt.text().strip().lower()
        rs = [r for r in state["rows"] if not q or q in " ".join(map(str, r)).lower()]
        tab.setSortingEnabled(False); tab.setRowCount(len(rs))
        for i, r in enumerate(rs):
            for j, c in enumerate(r[:len(columns)]):
                it = QTableWidgetItem(str(c)); it.setData(Qt.ItemDataRole.UserRole, r); tab.setItem(i, j, it)
        tab.setSortingEnabled(True); status.setText("%d · %s" % (len(rs), time.strftime("%H:%M:%S")))
    br.done.connect(commit); flt.textChanged.connect(lambda *_: show())

    def refresh():
        if state["busy"]:
            return
        state["busy"] = True

        def job():
            try:
                br.done.emit(list(gather()), "")
            except Exception as exc:
                br.done.emit([], str(exc))
        try:
            import compute
            compute.run("background", job, carrier="manage:" + key)
        except Exception:
            import threading
            threading.Thread(target=job, daemon=True).start()

    def selected():
        it = tab.item(tab.currentRow(), 0) if tab.currentRow() >= 0 else None
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    for label, fn in actions:
        b = QPushButton(label)

        def go(_=False, fn=fn):
            r = selected()
            try:
                msg = fn(r) if r is not None or getattr(fn, "no_row", False) else "select a row first"
            except Exception as exc:
                msg = "failed: %s" % exc
            if msg:
                status.setText(str(msg)[:160])
            refresh()
        b.clicked.connect(go); bar.addWidget(b)
    rb = QPushButton("⟳ Refresh"); rb.clicked.connect(refresh); bar.addStretch(1); bar.addWidget(rb)
    if interval_ms > 0:
        t = QTimer(d); t.setInterval(interval_ms)
        t.timeout.connect(lambda: refresh() if d.isVisible() and auto.isChecked() else None); t.start()
    reg[key] = d; d.show(); refresh()
    return d


def no_row(fn):
    fn.no_row = True; return fn


# ------------------------------------------------------------------ 1 windows
@window("windows", "🪟", "Windows", "Every open Groovebox window: raise, minimise, close, tile, cascade, save / restore the layout")
def w_windows(app):
    from PyQt6.QtWidgets import QApplication

    def tops():
        return [x for x in QApplication.topLevelWidgets() if x.isWindow() and x.windowTitle() and x is not app]
    # window geometry is Qt state: gather it on the Qt thread snapshot (cheap), the table refresh is the same machine
    snap = {"rows": []}

    def gather():
        return snap["rows"]

    def snapshot():
        snap["rows"] = [(x.windowTitle(), "visible" if x.isVisible() else "hidden", "%dx%d" % (x.width(), x.height()),
                         "%d,%d" % (x.x(), x.y()), id(x)) for x in tops()]
    snapshot()

    def find(r):
        return next((x for x in tops() if id(x) == r[4]), None)

    def act(f):
        def run(r):
            x = find(r)
            if x is None: return "window closed"
            f(x); snapshot(); return None
        return run

    @no_row
    def tile(_r):
        ws = [x for x in tops() if x.isVisible()]
        scr = app.screen().availableGeometry() if app.screen() else None
        if not ws or scr is None: return "nothing to tile"
        n = len(ws); cols = int(n ** 0.5 + 0.999); rows = (n + cols - 1) // cols
        for i, x in enumerate(ws):
            x.setGeometry(scr.x() + (i % cols) * scr.width() // cols, scr.y() + (i // cols) * scr.height() // rows,
                          scr.width() // cols, scr.height() // rows)
        snapshot(); return "tiled %d" % n

    @no_row
    def cascade(_r):
        for i, x in enumerate([x for x in tops() if x.isVisible()]):
            x.move(40 + 28 * i, 60 + 28 * i)
        snapshot()

    @no_row
    def save_layout(_r):
        import safe_io
        lay = {x.windowTitle(): [x.x(), x.y(), x.width(), x.height()] for x in tops() if x.isVisible()}
        safe_io.atomic_write_json(os.path.join(_data_dir(), "window_layout.json"), lay); return "saved %d windows" % len(lay)

    @no_row
    def restore_layout(_r):
        import safe_io
        lay = safe_io.read_json(os.path.join(_data_dir(), "window_layout.json"), {}) or {}
        n = 0
        for x in tops():
            g = lay.get(x.windowTitle())
            if g: x.setGeometry(*g); n += 1
        snapshot(); return "restored %d windows" % n
    return open_table(app, "windows", "🪟 Windows", ("title", "state", "size", "position"), gather,
                      (("Raise", act(lambda x: (x.show(), x.raise_(), x.activateWindow()))), ("Minimise", act(lambda x: x.showMinimized())),
                       ("Close", act(lambda x: x.close())), ("Tile", tile), ("Cascade", cascade),
                       ("Save layout", save_layout), ("Restore layout", restore_layout)), interval_ms=0,
                      note="Window list is read on the Qt thread when you act; Refresh re-reads it.")


# ------------------------------------------------------------------ 2 processes
@window("processes", "⚙", "Processes", "Child processes (engine, render, encode, media, apps, plugins): CPU, memory, pause, resume, stop")
def w_processes(app):
    def gather():
        out = []
        try:
            import process_policy
            for p in process_policy.children():
                argv = getattr(p, "args", "")
                out.append((p.pid, getattr(p, "groovebox_kind", "other"), _mb(_rss_kb(p.pid) * 1024),
                            "%.2f" % float(getattr(p, "groovebox_share", 0.0) or 0.0),
                            (" ".join(map(str, argv)) if isinstance(argv, (list, tuple)) else str(argv))[:160]))
        except Exception as exc:
            out.append(("—", "unavailable", "", "", str(exc)))
        return out

    def sig(s):
        def run(r):
            os.kill(int(r[0]), s); return "signal sent to %s" % r[0]
        return run
    return open_table(app, "processes", "⚙ Processes", ("pid", "kind", "memory", "cpu share", "command"), gather,
                      (("⏸ Pause", sig(signal.SIGSTOP)), ("▶ Resume", sig(signal.SIGCONT)), ("■ Stop", sig(signal.SIGTERM)),
                       ("✖ Kill", sig(signal.SIGKILL))),
                      note="External apps run under the 0.19758 CPU / memory share; pausing is the same SIGSTOP the governor uses.")


# ------------------------------------------------------------------ 3 threads & lanes
@window("threads", "🧵", "Threads & lanes", "sCode directions, compute strands, lane widths, per-call costs and every Python thread")
def w_threads(app):
    def gather():
        import threading
        rows = []
        try:
            import compute
            for line in compute.report().splitlines():
                if line.strip(): rows.append(("compute", line.strip()[:70], line.strip()[70:]))
        except Exception:
            pass
        for t in threading.enumerate():
            rows.append(("thread", t.name, "daemon" if t.daemon else "foreground"))
        return rows
    return open_table(app, "threads", "🧵 Threads & lanes", ("kind", "name", "detail"), gather, interval_ms=1500)


# ------------------------------------------------------------------ 4 memory
@window("memory", "🧠", "Memory", "Process memory, caches (pure results, compilation, carrier envelopes, mixdown) and clean-up")
def w_memory(app):
    def gather():
        rows = [("process RSS", _mb(_rss_kb(os.getpid()) * 1024), "")]
        try:
            with open("/proc/meminfo") as f:
                mi = dict(l.split(":", 1) for l in f)
            rows.append(("system available", _mb(int(mi["MemAvailable"].split()[0]) * 1024), "of " + _mb(int(mi["MemTotal"].split()[0]) * 1024)))
        except Exception:
            pass
        try:
            import compute
            c = compute._cache()
            if c is not None: rows.append(("pure-result cache", str(c.stats().get("entries")), str(c.stats())))
        except Exception:
            pass
        try:
            from scode.optimization import COMPILATION_CACHE
            rows.append(("sCode compilation cache", str(COMPILATION_CACHE.stats().get("entries")), str(COMPILATION_CACHE.stats())))
        except Exception:
            pass
        try:
            import mm_governor
            rows.append(("carrier envelopes", str(len(mm_governor._ENV)), ""))
        except Exception:
            pass
        rows.append(("mixdown cache", str(len(getattr(app, "_shared_mixdown_cache", {}) or {})), ""))
        rows.append(("python objects", str(len(gc.get_objects())), "gc counts %s" % (gc.get_count(),)))
        return rows

    @no_row
    def clear(_r):
        try:
            import compute
            c = compute._cache(); c and c.clear()
        except Exception:
            pass
        try:
            import mm_governor; mm_governor._ENV.clear()
        except Exception:
            pass
        n = gc.collect(); return "caches cleared · %d objects collected" % n
    return open_table(app, "memory", "🧠 Memory", ("item", "value", "detail"), gather, (("🧹 Clear caches + collect", clear),), 3000)


# ------------------------------------------------------------------ 5 storage
@window("storage", "💾", "Storage", "Free space on every drive, the biggest files in the Groovebox folder, temp clean-up")
def w_storage(app):
    import shutil

    def gather():
        rows = []
        seen = set()
        for mp in ["/", _data_dir(), os.path.expanduser("~")] + glob.glob("/media/*/*") + glob.glob("/run/media/*/*") + glob.glob("/mnt/*"):
            try:
                st = os.statvfs(mp); key = (st.f_fsid if hasattr(st, "f_fsid") else mp)
                if key in seen: continue
                seen.add(key); u = shutil.disk_usage(mp)
                rows.append(("drive", mp, _mb(u.free) + " free", _mb(u.total) + " total", "%d%%" % (100 * u.used // max(1, u.total))))
            except Exception:
                pass
        big = []
        for dp, dn, fns in os.walk(_data_dir()):
            for fn in fns:
                p = os.path.join(dp, fn)
                try: big.append((os.path.getsize(p), p))
                except OSError: pass
        for sz, p in sorted(big, reverse=True)[:40]:
            rows.append(("file", p, _mb(sz), time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))), ""))
        return rows

    def trash(r):
        import safe_io
        if r[0] != "file": return "choose a file row"
        if safe_io.is_system_path(r[1]): return safe_io.protected_message(r[1], "delete")
        dest = os.path.join(_data_dir(), "Trash", os.path.basename(r[1]))
        os.makedirs(os.path.dirname(dest), exist_ok=True); shutil.move(r[1], dest); return "moved to Groovebox Trash"

    @no_row
    def temp(_r):
        import tempfile
        n = 0
        for p in glob.glob(os.path.join(tempfile.gettempdir(), "groovebox_job*")) + glob.glob(os.path.join(tempfile.gettempdir(), "groovebox-show-*")):
            if time.time() - os.path.getmtime(p) > 3600:
                shutil.rmtree(p, ignore_errors=True); n += 1
        return "removed %d stale temp folders" % n
    return open_table(app, "storage", "💾 Storage", ("kind", "path", "size / free", "date / total", "used"), gather,
                      (("🗑 Move file to Trash", trash), ("🧹 Clean old temp", temp)), 0)


# ------------------------------------------------------------------ 6 startup
STARTUP_LAYERS = ("edit_glow", "studio_extras", "features_r99", "mod_matrix", "panel_translucency", "experiences",
                  "plugin_library", "net_hub")


def startup_enabled(name):
    try:
        import compat_settings
        return name not in (compat_settings.load().get("startup_disabled") or [])
    except Exception:
        return True


@window("startup", "🚀", "Startup", "Which optional layers load at start (glow, extras, features, matrix, translucency, experiences, plugins, network)")
def w_startup(app):
    def gather():
        return [(n, "on" if startup_enabled(n) else "off", "loads after first paint") for n in STARTUP_LAYERS]

    def toggle(r):
        import compat_settings
        cur = set(compat_settings.load().get("startup_disabled") or [])
        cur.symmetric_difference_update({r[0]}); compat_settings.update(startup_disabled=sorted(cur))
        return "%s will be %s at next start" % (r[0], "off" if r[0] in cur else "on")
    return open_table(app, "startup", "🚀 Startup", ("layer", "state", "when"), gather, (("Toggle", toggle),), 0)


# ------------------------------------------------------------------ 7 plugins
@window("plugins", "🔌", "Plugins", "Installed plugins with version, language, last run report; run, open the output folder")
def w_plugins(app):
    def gather():
        import plugin_library as pl
        rows = []
        for p in pl.plugins():
            rep = ""
            try:
                import program_builder as pb
                outs = sorted(glob.glob(os.path.join(pb.out_dir(app, p["id"] + "-*"), "report.json")))
                rep = outs[-1] if outs else ""
            except Exception:
                pass
            rows.append((p.get("name", p.get("id")), p.get("version", 1), p.get("language", ""), p.get("category", ""), p.get("id"), rep))
        return rows

    def run(r):
        import plugin_library as pl
        p = next((x for x in pl.plugins() if x.get("id") == r[4]), None)
        if p is None: return "not found"
        pl.run(app, p); return "running %s" % r[0]
    return open_table(app, "plugins", "🔌 Plugins", ("name", "version", "language", "category", "id", "last report"), gather,
                      (("▶ Run", run),), 0)


# ------------------------------------------------------------------ 8 provenance
@window("provenance", "🧾", "Provenance", "Every export Groovebox remembers: when, seed, release; rebuild the project that made it")
def w_provenance(app):
    def gather():
        import provenance as pv, safe_io
        rows = []
        for p in sorted(glob.glob(os.path.join(pv._index_dir(), "*.mgprov")), key=os.path.getmtime, reverse=True)[:500]:
            d = safe_io.read_json(p, {}) or {}
            rows.append((d.get("file", "?"), time.strftime("%Y-%m-%d %H:%M", time.localtime(float(d.get("time") or 0))),
                         d.get("kind", ""), (d.get("seed") or "").splitlines()[0][:60] if d.get("seed") else "", d.get("release", ""), p))
        return rows

    def rebuild(r):
        import provenance as pv, safe_io, gzip, base64, hashlib
        d = safe_io.read_json(r[5], {}) or {}
        raw = gzip.decompress(base64.b64decode(d["project_gz_b64"]))
        if hashlib.sha256(raw).hexdigest() != d.get("project_sha256"): return "stored project damaged"
        out = os.path.join(_data_dir(), "Rebuilt - %s.MCC" % os.path.splitext(d.get("file", "export"))[0])
        safe_io.atomic_write_bytes(out, raw, backup=False); app.open_project_path(out); return "rebuilt → " + out
    return open_table(app, "provenance", "🧾 Provenance", ("file", "made", "kind", "seed", "release"), gather, (("↺ Rebuild project", rebuild),), 0)


# ------------------------------------------------------------------ 9 backups
@window("backups", "🛡", "Backups", "The hidden previous versions every safe save keeps: restore one, or prune them")
def w_backups(app):
    def gather():
        rows = []
        for dp, dn, fns in os.walk(_data_dir()):
            for fn in fns:
                if fn.startswith(".") and fn.endswith(".bak"):
                    p = os.path.join(dp, fn); orig = os.path.join(dp, fn[1:-4])
                    rows.append((fn[1:-4], dp, _mb(os.path.getsize(p)), time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(p))), p, orig))
        return rows

    def restore(r):
        import safe_io, shutil
        with open(r[4], "rb") as f:
            safe_io.atomic_write_bytes(r[5], f.read())
        return "restored %s from its previous version" % r[0]

    @no_row
    def prune(_r):
        n = 0
        for r in gather():
            if time.time() - os.path.getmtime(r[4]) > 30 * 86400:
                os.remove(r[4]); n += 1
        return "removed %d backups older than 30 days" % n
    return open_table(app, "backups", "🛡 Backups", ("file", "folder", "size", "saved"), gather, (("↺ Restore", restore), ("🧹 Prune > 30 days", prune)), 0)


# ------------------------------------------------------------------ 10 protection
@window("protection", "🔒", "Protection", "System-file protection: protected and user roots, and a path checker")
def w_protection(app):
    def gather():
        import safe_io
        rows = [("protected", r, "view only") for r in safe_io._system_roots()]
        rows += [("user", r, "full access") for r in safe_io._user_roots()]
        q = getattr(app, "_r101_protect_probe", "")
        if q:
            rows.insert(0, ("check", q, "PROTECTED (view only)" if safe_io.is_system_path(q) else "user file (full access)"))
        return rows

    @no_row
    def probe(_r):
        from PyQt6.QtWidgets import QInputDialog
        t, ok = QInputDialog.getText(app, "Check a path", "Path:")
        if ok: app._r101_protect_probe = t.strip()
    return open_table(app, "protection", "🔒 Protection", ("kind", "path", "rule"), gather, (("🔍 Check a path…", probe),), 0,
                      note="Groovebox never edits, deletes, renames, moves, copies or pastes system files; plugins are held to the same rule.")


# ------------------------------------------------------------------ 11 network services
@window("network", "📡", "Network services", "Radio, site, LAN discovery, nearby stations and the ports in use")
def w_network(app):
    def gather():
        rows = []
        try:
            import net_hub
            st = net_hub.radio_status()
            rows.append(("radio", "on air" if st["on_air"] else "off", st.get("url", ""), st.get("now", "")))
            for r in net_hub.rows("radio_show", 20):
                rows.append(("show", r.get("name", ""), "hosted" if r.get("hosted") else "recording", time.strftime("%Y-%m-%d %H:%M", time.localtime(r.get("started", 0)))))
        except Exception as exc:
            rows.append(("radio", "unavailable", str(exc), ""))
        try:
            import radio_station as rs
            rows.append(("discovery", "udp %d" % rs.DISCOVERY_PORT, "http %d" % rs.DEFAULT_HTTP_PORT, ""))
        except Exception:
            pass
        try:
            with open("/proc/net/tcp") as f:
                for line in f.readlines()[1:]:
                    p = line.split()
                    if p[3] == "0A":
                        rows.append(("listening", "tcp %d" % int(p[1].split(":")[1], 16), "", ""))
        except Exception:
            pass
        return rows

    @no_row
    def stop(_r):
        import net_hub; net_hub.radio_stop(); return "radio stopped (show archived when enabled)"
    return open_table(app, "network", "📡 Network services", ("service", "state", "address", "detail"), gather, (("■ Stop radio", stop),), 3000)


# ------------------------------------------------------------------ 12 devices
@window("devices", "🎧", "Devices", "Audio outputs / inputs, cameras, MIDI ports and removable drives")
def w_devices(app):
    snap = {"qt": []}
    try:
        from PyQt6.QtMultimedia import QMediaDevices
        snap["qt"] = ([("audio out", d.description(), "default" if d == QMediaDevices.defaultAudioOutput() else "") for d in QMediaDevices.audioOutputs()]
                      + [("audio in", d.description(), "") for d in QMediaDevices.audioInputs()]
                      + [("camera", d.description(), "") for d in QMediaDevices.videoInputs()])
    except Exception:
        pass

    def gather():
        rows = list(snap["qt"])
        for p in sorted(glob.glob("/dev/snd/midi*")): rows.append(("midi", p, ""))
        for b in sorted(glob.glob("/sys/block/*")):
            try:
                if open(os.path.join(b, "removable")).read().strip() == "1":
                    sz = int(open(os.path.join(b, "size")).read()) * 512
                    rows.append(("removable", "/dev/" + os.path.basename(b), _mb(sz)))
            except Exception:
                pass
        return rows
    return open_table(app, "devices", "🎧 Devices", ("kind", "device", "detail"), gather, (), 0,
                      note="Qt devices are read on the Qt thread when the window opens; drives and MIDI on every refresh.")


# ------------------------------------------------------------------ 13 logs
@window("logs", "📜", "Logs", "Boot report, sOS logs and Groovebox logs: newest lines, filter, open")
def w_logs(app):
    def gather():
        files = glob.glob("/var/log/sos/*.log") + glob.glob("/var/log/sos/*.txt") + glob.glob("/run/sos/boot-report.txt")
        try:
            import groovebox_paths
            files += glob.glob(os.path.join(groovebox_paths.logs_dir(), "*"))
        except Exception:
            pass
        rows = []
        for f in sorted(set(files), key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)[:30]:
            try:
                with open(f, "rb") as fh:
                    fh.seek(max(0, os.path.getsize(f) - 6000)); tail = fh.read().decode("utf-8", "replace").splitlines()[-12:]
                for line in tail:
                    rows.append((os.path.basename(f), time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(f))), line[:220], f))
            except Exception:
                pass
        return rows

    def open_file(r):
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(r[3])); return None
    return open_table(app, "logs", "📜 Logs", ("log", "modified", "line"), gather, (("Open file", open_file),), 4000)


# ------------------------------------------------------------------ 14 shortcuts
@window("shortcuts", "⌨", "Shortcuts", "Every keyboard shortcut in the open windows, searchable")
def w_shortcuts(app):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QAction, QShortcut
    rows = []
    for top in QApplication.topLevelWidgets():
        for a in top.findChildren(QAction):
            if not a.shortcut().isEmpty():
                rows.append((a.shortcut().toString(), a.text().replace("&", ""), top.windowTitle()[:40]))
        for s in top.findChildren(QShortcut):
            rows.append((s.key().toString(), s.whatsThis() or s.objectName() or "shortcut", top.windowTitle()[:40]))
    return open_table(app, "shortcuts", "⌨ Shortcuts", ("keys", "action", "window"), lambda: rows, (), 0)


# ------------------------------------------------------------------ 15 scheduled actions
SCHED_ACTIONS = {"Save session": lambda app: __import__("session_snapshot").save(app),
                 "Play / stop": lambda app: app.toggle_playback(),
                 "Checkpoint": lambda app: __import__("project_transactions").checkpoint(app, "scheduled"),
                 "Stop radio": lambda app: __import__("net_hub").radio_stop(),
                 "Export mixdown": lambda app: app.export_mixdown_dialog()}


@window("schedule", "⏰", "Scheduled actions", "Run an action at a time or every N minutes (this session)")
def w_schedule(app):
    from PyQt6.QtCore import QTimer
    jobs = app.__dict__.setdefault("_r101_sched", [])

    def gather():
        return [(j["action"], j["when"], j["every"] or "once", j["runs"], id(j)) for j in jobs]

    @no_row
    def add(_r):
        from PyQt6.QtWidgets import QInputDialog
        act, ok = QInputDialog.getItem(app, "Schedule", "Action:", list(SCHED_ACTIONS), 0, False)
        if not ok: return None
        mins, ok = QInputDialog.getInt(app, "Schedule", "In how many minutes?", 10, 1, 24 * 60)
        if not ok: return None
        rep, ok2 = QInputDialog.getInt(app, "Schedule", "Repeat every N minutes (0 = once)", 0, 0, 24 * 60)
        j = {"action": act, "when": time.strftime("%H:%M", time.localtime(time.time() + mins * 60)), "every": rep if ok2 else 0, "runs": 0}
        t = QTimer(app); t.setSingleShot(not j["every"]); j["timer"] = t

        def fire():
            j["runs"] += 1
            try: SCHED_ACTIONS[act](app)
            except Exception as exc: print("[Schedule]", act, exc)
            if j["every"]:
                t.setInterval(j["every"] * 60000)
            else:
                jobs.remove(j) if j in jobs else None
        t.timeout.connect(fire); t.start(mins * 60000); jobs.append(j); return "scheduled %s" % act

    def cancel(r):
        j = next((x for x in jobs if id(x) == r[4]), None)
        if j: j["timer"].stop(); jobs.remove(j)
        return "cancelled"
    return open_table(app, "schedule", "⏰ Scheduled actions", ("action", "first at", "repeat (min)", "runs"), gather,
                      (("＋ Schedule…", add), ("✖ Cancel", cancel)), 5000)


@window("accounts", "👤", "Accounts", "User accounts: add, roles (owner · member · child · guest), passwords, switch user")
def w_accounts(app):
    return __import__("accounts").open_window(app)


def entries(app):
    """(text, tip, callable) for the Task Pad Manage row."""
    return [("%s %s" % (e, t), tip, (lambda fn=fn: fn(app))) for _k, e, t, tip, fn in WINDOWS]
