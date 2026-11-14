"""site_directory.py — GROOVEBOX_R32_MEDIA_NETWORK_20261110

The Groovebox Media Network directory: automatic contact + cached pages + homepage ads.

  * Every 90 s (worker thread) every Groovebox known by LAN discovery, the relay or manual
    links is contacted: /info and its site page are fetched and cached under
    cache/sites/<member>/ (index.html, info.json, seen time). Offline sites stay browsable
    from the cache, marked with when they were last seen.
  * ads(): one card per site — your own first, then every Groovebox you have been in contact
    with (name, about line, file count, now playing, live/cached).
  * homepage_cards() feeds the in-app browser's home page (web_browser_tab).
  * Cache manager: sizes and clearing for every Groovebox cache (site pages, render mixdowns,
    thumbnails, seed/graph compile caches, Qt pixmaps, temp, logs, recording scratch), with
    automatic trimming of the site cache to 200 MB / 60 days.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import threading
import time
import urllib.request

_STATE = {"thread": None, "stop": False, "last": 0.0}
SITE_CACHE_MB = 200
SITE_CACHE_DAYS = 60


def _cache_root():
    import groovebox_paths
    d = os.path.join(groovebox_paths.cache_dir(), "sites"); os.makedirs(d, exist_ok=True); return d


def _safe(s):
    return re.sub(r"[^\w.-]", "_", str(s))[:64] or "site"


def _targets(app):
    out = []
    nb = getattr(app, "_nearby_share_service", None)
    try:
        for p in (nb.peer_list() if nb is not None else []):
            u = p.get("url") or p.get("base_url") or ""
            host = re.match(r"https?://([^/:]+)", u)
            if host:
                # the site runs on the site port, the Nearby API on its own port
                import groovebox_site as gs
                out.append(("lan", p.get("node_id") or host.group(1), "http://%s:%d" % (host.group(1), int(gs.load_cfg()["port"]))))
    except Exception:
        pass
    try:
        import groovebox_site as gs
        s = getattr(app, "_groovebox_site", None)
        if s is not None:
            for mid, m in s.relay_members.items():
                if time.time() - m["seen"] < 120 and s.httpd:
                    out.append(("relay", mid, s.urls()[0].rstrip("/") + "/r/" + mid))
        c = gs.load_cfg()
        if c.get("relay_url"):
            pass
    except Exception:
        pass
    for u in getattr(app, "r32_manual_sites", []) or []:
        out.append(("link", u, u.rstrip("/")))
    return out


def contact_all(app):
    got = 0
    for via, key, base in _targets(app):
        d = os.path.join(_cache_root(), _safe(key))
        try:
            with urllib.request.urlopen(base + "/info", timeout=4) as r:
                info = json.loads(r.read().decode("utf-8", "replace"))
            if not info.get("groovebox"):
                continue
            with urllib.request.urlopen(base + "/", timeout=6) as r:
                page = r.read(2 * 1024 * 1024)
            os.makedirs(d, exist_ok=True)
            info.update({"base": base, "via": via, "seen": time.time()})
            with open(os.path.join(d, "info.json"), "w", encoding="utf-8") as f:
                json.dump(info, f)
            with open(os.path.join(d, "index.html"), "wb") as f:
                f.write(page)
            got += 1
        except Exception:
            continue
    _STATE["last"] = time.time()
    trim_site_cache()
    return got


def _loop(app, interval):
    while not _STATE["stop"]:
        try:
            contact_all(app)
        except Exception:
            pass
        for _ in range(int(interval)):
            if _STATE["stop"]:
                return
            time.sleep(1)


def start(app, interval=90):
    if _STATE["thread"] is None:
        _STATE["stop"] = False
        th = threading.Thread(target=_loop, args=(app, interval), daemon=True, name="groovebox-site-directory")
        th.start(); _STATE["thread"] = th


def ads(app=None):
    rows = []
    try:
        import groovebox_site as gs
        c = gs.load_cfg(); s = getattr(app, "_groovebox_site", None) if app is not None else None
        rows.append({"name": c["site_name"], "about": c["about"], "files": len(gs.shared_files(c)),
                     "url": (s.urls()[0] if s is not None and s.httpd else ""), "mine": True, "live": bool(s and s.httpd),
                     "cached": "", "now_playing": getattr(s, "now_playing", "") if s else ""})
    except Exception:
        pass
    root = _cache_root()
    for d in sorted(os.listdir(root)):
        try:
            with open(os.path.join(root, d, "info.json"), encoding="utf-8") as f:
                info = json.load(f)
        except Exception:
            continue
        live = time.time() - float(info.get("seen", 0)) < 300
        rows.append({"name": info.get("name", d), "about": "via %s · %d shared" % (info.get("via", "?"), int(info.get("files", 0))),
                     "files": int(info.get("files", 0)), "url": info.get("base", "") + "/" if live else
                     "file://" + os.path.join(root, d, "index.html").replace(os.sep, "/"),
                     "mine": False, "live": live, "cached": time.strftime("%Y-%m-%d %H:%M", time.localtime(info.get("seen", 0))),
                     "now_playing": info.get("now_playing", "")})
    return rows


def homepage_cards(app=None):
    out = []
    for a in ads(app):
        title = ("★ " if a["mine"] else "") + a["name"]
        note = a["about"][:90] + (" · ▶ " + a["now_playing"] if a.get("now_playing") else "") + \
            ("" if a["live"] else (" · cached %s" % a["cached"] if a["cached"] else " · not running (Network Hub ▸ Start site)"))
        if a["url"]:
            out.append((title, a["url"], note))
    return out


# ---------------------------------------------------------------------------
# cache manager
# ---------------------------------------------------------------------------
def _size(path):
    tot = 0
    for r, _ds, fs in os.walk(path):
        for f in fs:
            try:
                tot += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return tot


def cache_inventory(app=None):
    import groovebox_paths as gp
    items = [("Site pages (Media Network)", _cache_root(), "dir"),
             ("Global cache", gp.cache_dir(), "dir"), ("Temp", gp.temp_dir(), "dir"), ("Logs", gp.logs_dir(), "dir"),
             ("Web browser cache", os.path.join(os.path.expanduser("~"), ".groovebox-browser", "cache"), "dir")]
    pp = getattr(app, "_current_project_path", None) if app is not None else None
    try:
        items.append(("Project cache", os.path.join(str(gp.project_root(pp)), "cache"), "dir"))
    except Exception:
        pass
    items += [("Render mixdown cache (memory)", "mixdown", "mem"), ("Seed / graph compile cache (memory)", "compile", "mem"),
              ("Multidim voice memo (memory)", "multidim", "mem"), ("Image cache (memory)", "pixmap", "mem")]
    out = []
    for label, path, kind in items:
        out.append({"label": label, "path": path, "kind": kind, "bytes": _size(path) if kind == "dir" and os.path.isdir(path) else 0})
    return out


def clear(item, app=None):
    kind, path = item["kind"], item["path"]
    if kind == "dir":
        if not os.path.isdir(path):
            return 0
        n = 0
        for name in os.listdir(path):
            p = os.path.join(path, name)
            try:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p); n += 1
            except Exception:
                pass
        return n
    if path == "mixdown" and app is not None:
        try:
            app._shared_mixdown_cache.clear()
        except Exception:
            pass
    elif path == "compile":
        try:
            import seed_lang, graph_script_context
            seed_lang.clear_cache(); graph_script_context._CODE_CACHE.clear()
        except Exception:
            pass
    elif path == "multidim":
        try:
            import multidim_synth
            multidim_synth.memo_clear(); multidim_synth.world_clear()
        except Exception:
            pass
    elif path == "pixmap":
        try:
            from PyQt6.QtGui import QPixmapCache
            QPixmapCache.clear()
        except Exception:
            pass
    return 1


def trim_site_cache():
    root = _cache_root(); now = time.time(); dirs = []
    for d in os.listdir(root):
        p = os.path.join(root, d)
        try:
            with open(os.path.join(p, "info.json"), encoding="utf-8") as fh:
                seen = json.load(fh).get("seen", os.path.getmtime(p))
        except Exception:
            seen = os.path.getmtime(p)
        if now - seen > SITE_CACHE_DAYS * 86400:
            shutil.rmtree(p, ignore_errors=True)
        else:
            dirs.append((seen, p))
    total = sum(_size(p) for _s, p in dirs)
    for _s, p in sorted(dirs):
        if total <= SITE_CACHE_MB * 1024 * 1024:
            break
        total -= _size(p); shutil.rmtree(p, ignore_errors=True)


def make_cache_page(app=None):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QLabel
    w = QWidget(); lay = QVBoxLayout(w)
    lay.addWidget(QLabel("🧹 Groovebox caches — clearing never touches projects, samples, exports or recordings."))
    tab = QTableWidget(0, 3); tab.setHorizontalHeaderLabels(["cache", "size", "location"]); tab.setColumnWidth(0, 260); tab.setColumnWidth(2, 380)
    lay.addWidget(tab)
    info = QLabel(""); lay.addWidget(info)
    rows = []

    def fill():
        rows[:] = cache_inventory(app); tab.setRowCount(len(rows))
        for i, r in enumerate(rows):
            tab.setItem(i, 0, QTableWidgetItem(r["label"]))
            tab.setItem(i, 1, QTableWidgetItem("%.1f MB" % (r["bytes"] / 1e6) if r["kind"] == "dir" else "in memory"))
            tab.setItem(i, 2, QTableWidgetItem(r["path"]))
        info.setText("Total on disk: %.1f MB · site cache auto-trims to %d MB / %d days" % (
            sum(r["bytes"] for r in rows) / 1e6, SITE_CACHE_MB, SITE_CACHE_DAYS))

    def clear_sel():
        for idx in sorted({i.row() for i in tab.selectedIndexes()}):
            clear(rows[idx], app)
        fill()

    def clear_all():
        for r in rows:
            clear(r, app)
        fill()
    row = QHBoxLayout()
    for cap, fn in (("Clear selected", clear_sel), ("Clear all caches", clear_all), ("Refresh", fill),
                    ("Contact Grooveboxes now", lambda: threading.Thread(target=lambda: contact_all(app), daemon=True).start())):
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    lay.addLayout(row); fill()
    return w


def open_cache_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget, QVBoxLayout
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🧹 Groovebox caches"); w.resize(780, 420)
    QVBoxLayout(w).addWidget(make_cache_page(app)); app._cache_window = w; w.show(); return w
