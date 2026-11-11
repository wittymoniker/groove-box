"""network_hub.py — GROOVEBOX_R32_NETWORK_HUB_20261110

🌐 Network Hub: every way Groovebox talks to other Grooveboxes, in one window.

  Site        your Groovebox site: name, about text, port, chat on/off, bounded text-only notes,
              start/stop, addresses to share (LAN, IPv6, public), open in browser
  Sharing     tick folders and individual files to share (tree with checkboxes);
              nothing is shared until ticked; counts and total size shown live
  Peers       Grooveboxes found on the LAN (Nearby), through a relay, or added by URL;
              browse a peer's shared library, play/stream, download, import a project (data only)
  Chat        site chat (visitors) + Nearby messages to Grooveboxes
  Together    Live Edit Together (co-edit) start / join, and multi-Groovebox export of a
              shared project (each member renders its own copy → files collected here)
  Relay       be a relay host, or connect to one (works behind NAT without port forwarding)
  Internet    UPnP port forward / remove, public address, manual forwarding instructions
  Links       status of every networking method: LAN (IPv4/IPv6), Wi-Fi, hotspot / ad-hoc,
              Wi-Fi Direct, relay, VPN interfaces
"""
from __future__ import annotations

import json
import os
import socket
import threading
import urllib.request

from PyQt6.QtCore import Qt, QTimer, QUrl, QObject, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QLineEdit, QTextEdit, QPushButton,
                             QSpinBox, QCheckBox, QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem, QFormLayout,
                             QFileDialog)

import groovebox_site as gs


class _Sig(QObject):
    text = pyqtSignal(str)
    rows = pyqtSignal(object)


def _bg(fn, done=None):
    sig = _Sig()

    def run():
        try:
            r = fn()
        except Exception as exc:
            r = "⚠ %s" % exc
        if done is not None:
            sig.rows.emit(r)
    if done is not None:
        sig.rows.connect(done)
    threading.Thread(target=run, daemon=True).start()
    return sig


def open_window(app):
    w = getattr(app, "_network_hub_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); return w
    except RuntimeError:
        pass
    site = gs.site(app)
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🌐 Network Hub · site · sharing · peers · chat · relay · Internet")
    w.resize(960, 700); root = QVBoxLayout(w); tabs = QTabWidget(); root.addWidget(tabs)
    status = QLabel(""); root.addWidget(status); w._keep = []
    cfg = gs.load_cfg()

    # Site ----------------------------------------------------------------------
    t = QWidget(); f = QFormLayout(t); tabs.addTab(t, "🏠 Site")
    name = QLineEdit(cfg["site_name"]); about = QTextEdit(cfg["about"]); about.setMaximumHeight(90)
    port = QSpinBox(); port.setRange(1024, 65535); port.setValue(int(cfg["port"]))
    chat_on = QCheckBox("Visitors can chat"); chat_on.setChecked(bool(cfg["chat"]))
    note_cap = QSpinBox(); note_cap.setRange(4, 64); note_cap.setSuffix(" MB"); note_cap.setValue(int(cfg.get("notes_limit_mb", 16)))
    note_help = QLabel("Visitors can post text notes only. No visitor file uploads are accepted. The newest notes are retained within this rolling size cap.")
    note_help.setWordWrap(True)
    auto = QCheckBox("Start the site when Groovebox starts"); auto.setChecked(bool(cfg["autostart"]))
    urls = QLabel(""); urls.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); urls.setWordWrap(True)
    for cap, wd in (("Site name", name), ("About", about), ("Port", port), ("", chat_on),
                    ("Visitor note retention", note_cap), ("", note_help), ("", auto), ("Addresses", urls)):
        f.addRow(cap, wd)

    def save_site():
        c = gs.load_cfg(); c.update({"site_name": name.text(), "about": about.toPlainText(), "port": port.value(),
                                     "chat": chat_on.isChecked(), "uploads": False,
                                     "notes_limit_mb": note_cap.value(), "autostart": auto.isChecked()})
        gs.save_cfg(c)

    def start_site():
        save_site(); u = site.start(port.value()); urls.setText("\n".join(u)); status.setText("site running")

    def stop_site():
        site.stop(); urls.setText("(stopped)"); status.setText("site stopped")
    row = QHBoxLayout()
    for cap, fn in (("Save", save_site), ("▶ Start site", start_site), ("■ Stop", stop_site),
                    ("Open in browser", lambda: __import__("PyQt6.QtGui", fromlist=["QDesktopServices"]).QDesktopServices.openUrl(QUrl(site.urls()[0])))):
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    f.addRow(row)
    if site.httpd:
        urls.setText("\n".join(site.urls()))

    # Sharing ------------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "📤 Sharing")
    tree = QTreeWidget(); tree.setHeaderLabels(["shared", "size"]); tree.setColumnWidth(0, 640); l.addWidget(tree)
    summary = QLabel(""); l.addWidget(summary)

    def build_tree():
        tree.blockSignals(True); tree.clear(); c = gs.load_cfg()
        folders = list(dict.fromkeys(list(c.get("folders", {})) + gs.suggested_folders(app)))
        for folder in folders:
            top = QTreeWidgetItem(tree, [folder, ""]); top.setData(0, Qt.ItemDataRole.UserRole, ("folder", folder))
            top.setCheckState(0, Qt.CheckState.Checked if c["folders"].get(folder) else Qt.CheckState.Unchecked)
            n = 0
            for r, ds, fs in os.walk(folder):
                ds[:] = [d for d in ds if not d.startswith(".") and d not in ("cache", "metadata")]
                for fn in fs:
                    if fn.lower().endswith(gs.MEDIA) and n < 400:
                        p = os.path.join(r, fn); n += 1
                        it = QTreeWidgetItem(top, [os.path.relpath(p, folder), "%.1f MB" % (os.path.getsize(p) / 1e6)])
                        it.setData(0, Qt.ItemDataRole.UserRole, ("file", p))
                        st = c["files"].get(p)
                        on = st if st is not None else bool(c["folders"].get(folder))
                        it.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        tree.blockSignals(False); upd_summary()

    def upd_summary():
        sh = gs.shared_files()
        summary.setText("%d file(s) shared · %.1f MB" % (len(sh), sum(os.path.getsize(p) for _i, p in sh if os.path.exists(p)) / 1e6))

    def on_check(it, _col):
        kind, p = it.data(0, Qt.ItemDataRole.UserRole); c = gs.load_cfg(); on = it.checkState(0) == Qt.CheckState.Checked
        if kind == "folder":
            c["folders"][p] = on
            for i in range(it.childCount()):
                c["files"].pop(it.child(i).data(0, Qt.ItemDataRole.UserRole)[1], None)
        else:
            c["files"][p] = on
        gs.save_cfg(c)
        if kind == "folder":
            build_tree()
        else:
            upd_summary()
    tree.itemChanged.connect(on_check)
    row = QHBoxLayout()
    b_add = QPushButton("Add folder…")
    b_add.clicked.connect(lambda: (lambda d: (gs.save_cfg({**gs.load_cfg(), "folders": {**gs.load_cfg()["folders"], d: True}}), build_tree()) if d else None)(
        QFileDialog.getExistingDirectory(w, "Share a folder")))
    b_none = QPushButton("Share nothing"); b_none.clicked.connect(lambda: (gs.save_cfg({**gs.load_cfg(), "folders": {}, "files": {}}), build_tree()))
    b_ref = QPushButton("Refresh"); b_ref.clicked.connect(build_tree)
    for b in (b_add, b_none, b_ref):
        row.addWidget(b)
    l.addLayout(row); build_tree()

    # Peers ----------------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "👥 Peers")
    peers = QListWidget(); files = QListWidget(); l.addWidget(QLabel("Grooveboxes (LAN · relay · added)")); l.addWidget(peers)
    l.addWidget(QLabel("Their shared library")); l.addWidget(files)
    add = QLineEdit(); add.setPlaceholderText("http://address:port/  or  http://relay:port/r/<member>/")
    w._manual = []

    def list_peers():
        peers.clear()
        rows = site._peers() + [{"name": u, "url": u, "via": "added"} for u in w._manual]
        for p in rows:
            it = QListWidgetItem("%s  ·  %s  (%s)" % (p["name"], p["url"], p["via"])); it.setData(Qt.ItemDataRole.UserRole, p["url"]); peers.addItem(it)

    def browse():
        it = peers.currentItem()
        if not it:
            return
        base = it.data(Qt.ItemDataRole.UserRole) or ""
        if base.startswith("/"):
            base = site.urls()[0].rstrip("/") + base
        base = base.rstrip("/")
        w._base = base

        def fetch():
            with urllib.request.urlopen(base + "/files", timeout=8) as r:
                return json.loads(r.read().decode())

        def show(rows):
            files.clear()
            if isinstance(rows, str):
                status.setText(rows); return
            for d in rows:
                x = QListWidgetItem("%s  ·  %s  ·  %.1f MB" % (d["name"], d["kind"], d["size"] / 1e6)); x.setData(Qt.ItemDataRole.UserRole, d)
                files.addItem(x)
            status.setText("%d shared file(s) at %s" % (len(rows), base))
        w._keep.append(_bg(fetch, show))

    def play():
        it = files.currentItem()
        if it:
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(w._base + it.data(Qt.ItemDataRole.UserRole)["url"]))

    def download():
        it = files.currentItem()
        if not it:
            return
        d = it.data(Qt.ItemDataRole.UserRole)
        import groovebox_paths as gp
        dst = os.path.join(gp.downloads_dir(), d["name"])

        def get():
            urllib.request.urlretrieve(w._base + d["url"], dst); return "downloaded → " + dst
        w._keep.append(_bg(get, status.setText))
    row = QHBoxLayout()
    for cap, fn in (("Refresh", list_peers), ("Browse", browse), ("▶ Stream", play), ("⬇ Download", download),
                    ("Add URL", lambda: (w._manual.append(add.text().strip()), list_peers()) if add.text().strip() else None)):
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    l.addWidget(add); l.addLayout(row); list_peers()

    # Chat --------------------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "💬 Chat")
    log = QTextEdit(); log.setReadOnly(True); l.addWidget(log)
    msg = QLineEdit(); msg.setPlaceholderText("Message (site visitors and nearby Grooveboxes)")
    l.addWidget(msg)

    def refresh_chat():
        lines = ["[site] %s: %s" % (m["who"], m["text"]) for m in site.chat[-60:]]
        nb = getattr(app, "_nearby_share_service", None)
        try:
            for m in (nb.messages()[-60:] if nb is not None else []):
                lines.append("[nearby] %s: %s" % (m.get("from_name", "?"), m.get("text", "")))
        except Exception:
            pass
        log.setPlainText("\n".join(lines))

    def send():
        text = msg.text().strip()
        if not text:
            return
        site.chat.append({"t": __import__("time").time(), "who": gs.load_cfg()["site_name"], "text": text})
        nb = getattr(app, "_nearby_share_service", None)
        try:
            if nb is not None:
                nb.send_text(text)
        except Exception:
            pass
        msg.clear(); refresh_chat()
    msg.returnPressed.connect(send)
    ct = QTimer(w); ct.setInterval(2000); ct.timeout.connect(lambda: refresh_chat() if tabs.currentIndex() == 3 else None); ct.start()

    # Together ------------------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🤝 Together")
    l.addWidget(QLabel("Live Edit Together: one owner holds the project; members propose section edits; everyone stays in sync."))
    row = QHBoxLayout()
    for cap, fn in (("Open Live Edit Together…", lambda: getattr(app, "_open_live_edit", getattr(app, "open_live_edit_together", lambda: status.setText("Live Edit opener not found")))()),
                    ("Share this project on my site", lambda: (_share_project(app), build_tree(), status.setText("project shared")))):
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    l.addLayout(row)
    l.addWidget(QLabel("Multi-Groovebox export: share the project, then each peer opens it (Peers ▸ Download ▸ open) and exports;\n"
                       "each Groovebox downloads only the files it explicitly requests. Files are never pushed into another Groovebox.\n"
                       "Visitors may leave text-only site notes; notes roll over within the configured 4–64 MB limit."))
    l.addStretch(1)

    # Relay --------------------------------------------------------------------------
    t = QWidget(); f = QFormLayout(t); tabs.addTab(t, "🛰 Relay")
    host = QCheckBox("Be a relay host for Grooveboxes behind routers (needs a reachable port)"); host.setChecked(bool(cfg["relay_host"]))
    host.toggled.connect(lambda v: gs.save_cfg({**gs.load_cfg(), "relay_host": bool(v)}))
    rurl = QLineEdit(cfg.get("relay_url", "")); rurl.setPlaceholderText("http://relay-groovebox:8765")
    mid = QLabel(cfg["member_id"]); rstate = QLabel("")
    f.addRow("", host); f.addRow("Relay to join", rurl); f.addRow("My member id", mid); f.addRow("State", rstate)

    def join():
        gs.save_cfg({**gs.load_cfg(), "relay_url": rurl.text().strip()})
        if not site.httpd:
            start_site()
        old = getattr(app, "_relay_member", None)
        if old:
            old.stop()
        m = app._relay_member = gs.RelayMember(site, rurl.text().strip(), gs.load_cfg()["member_id"], gs.load_cfg()["site_name"])
        m.start()
        rstate.setText("connecting… visitors use %s/r/%s/" % (rurl.text().strip().rstrip("/"), gs.load_cfg()["member_id"]))
    b = QPushButton("Join relay"); b.clicked.connect(join); f.addRow(b)
    rt = QTimer(w); rt.setInterval(2000); rt.timeout.connect(lambda: getattr(app, "_relay_member", None) and rstate.setText(app._relay_member.state)); rt.start()

    # Internet ------------------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🌍 Internet")
    out = QLabel("Forward the site port on your router so anyone can browse your Groovebox site from the Internet."); out.setWordWrap(True)
    l.addWidget(out)
    row = QHBoxLayout()
    for cap, fn in (("UPnP forward port", lambda: w._keep.append(_bg(lambda: gs.upnp_forward(port.value())[1], out.setText))),
                    ("Remove forward", lambda: w._keep.append(_bg(lambda: gs.upnp_remove(port.value())[1], out.setText)))):
        bb = QPushButton(cap); bb.clicked.connect(fn); row.addWidget(bb)
    l.addLayout(row)
    l.addWidget(QLabel("Manual: router admin page ▸ Port forwarding ▸ TCP %d → this computer's LAN address (see Site ▸ Addresses).\n"
                       "No router access? Join a relay instead (Relay tab)." % port.value()))
    l.addStretch(1)

    # Wi-Fi: host / join a Groovebox network (R32.11.4) -------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "📶 Wi-Fi")
    _wi = QLabel("Host this Groovebox's own Wi-Fi network so other Grooveboxes, phones and laptops can join "
                 "without a router, then render together, Edit Together and share media over it. Other "
                 "Grooveboxes join with one click (the password comes from the network name); phones and laptops "
                 "type the password shown and open the address in a browser. It is WPA2: anyone in range who "
                 "has the password can join, so files you share are visible to them (incoming files stay off "
                 "unless you allow them).")
    _wi.setWordWrap(True); l.addWidget(_wi)
    wi_out = QLabel("Not hosting."); wi_out.setWordWrap(True)
    wi_out.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    wi_out.setStyleSheet("font-size:11pt;font-weight:700;color:#9be7ff;padding:6px;border:1px solid #2a4a5a;border-radius:6px;")
    wi_list = QListWidget()

    def _svc():
        svc = getattr(app, "_nearby_share_service", None)
        if svc is None or getattr(svc, "direct", None) is None:
            wi_out.setText("The Nearby service is not running, so Wi-Fi hosting is unavailable on this computer.")
            return None
        return svc

    def _hosted(res):
        svc = _svc()
        ok, msg = (res if isinstance(res, tuple) else (False, str(res)))
        if ok and svc is not None:
            try:
                svc.set_web_browse(True)
            except Exception:
                pass
            ssid, pw = svc.direct.ssid, svc.direct.password
            urls = ", ".join(svc.urls())
            wi_out.setText(f"📶 Hosting  {ssid}\nPassword  {pw}\nIn a browser on the joined device:  {urls}\n"
                           f"Wi-Fi QR text (for a QR generator):  WIFI:T:WPA;S:{ssid};P:{pw};;")
        else:
            wi_out.setText("Could not start the Groovebox Wi-Fi: " + (msg or "unknown error"))

    def host():
        svc = _svc()
        if svc is None:
            return
        try:
            import hotspot_plan
            plan = hotspot_plan.hotspot_plan()
        except Exception as exc:
            plan = {"supported": False, "reason": str(exc), "cancels": [], "iface": ""}
        if not plan.get("supported"):
            wi_out.setText(str(plan.get("reason") or "Hosting Wi-Fi is not available here.")); return
        if plan.get("cancels"):
            from PyQt6.QtWidgets import QMessageBox
            what = "\n".join("• " + c for c in plan["cancels"])
            if QMessageBox.question(w, "Host Groovebox Wi-Fi?", "Hosting will interrupt Wi-Fi activity on this radio:\n\n"
                                    + what + "\n\nContinue?") != QMessageBox.StandardButton.Yes:
                return
        if plan.get("iface") and not getattr(svc.direct, "wifi_iface", ""):
            svc.direct.wifi_iface = str(plan["iface"])
        wi_out.setText("Starting the Groovebox Wi-Fi…")
        w._keep.append(_bg(svc.start_direct_hotspot, _hosted))

    def stop():
        svc = _svc()
        if svc is not None:
            w._keep.append(_bg(svc.stop_direct_hotspot, lambda r: wi_out.setText("Stopped hosting." if (isinstance(r, tuple) and r[0]) else "Stop: %s" % (r[1] if isinstance(r, tuple) else r))))

    def scan():
        svc = _svc()
        if svc is None:
            return
        wi_list.clear(); wi_list.addItem("Scanning…")
        def fill(rows):
            wi_list.clear()
            rows = rows if isinstance(rows, list) else []
            for r in rows:
                it = QListWidgetItem("📶 %s   (%d %%)" % (r.get("ssid"), int(r.get("signal", 0)))); it.setData(Qt.ItemDataRole.UserRole, r.get("ssid"))
                wi_list.addItem(it)
            if not rows:
                wi_list.addItem("No Groovebox Wi-Fi in range.")
        w._keep.append(_bg(svc.direct.scan, fill))

    def join():
        svc = _svc(); it = wi_list.currentItem()
        ssid = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        if svc is None or not ssid:
            wi_out.setText("Scan, then pick a Groovebox Wi-Fi to join."); return
        wi_out.setText("Joining %s…" % ssid)
        w._keep.append(_bg(lambda: svc.join_direct(ssid), lambda r: wi_out.setText(
            ("✔ Joined %s — nearby Grooveboxes appear in Edit Together / Nearby." % ssid) if (isinstance(r, tuple) and r[0])
            else "Join failed: %s" % (r[1] if isinstance(r, tuple) else r))))

    def adhoc():
        svc = _svc()
        if svc is not None:
            w._keep.append(_bg(svc.direct.start_adhoc, lambda r: wi_out.setText(r[1] if isinstance(r, tuple) else str(r))))

    row = QHBoxLayout()
    for cap, fn in (("📶 Host Groovebox Wi-Fi", host), ("⏹ Stop hosting", stop),
                    ("🔎 Find Groovebox Wi-Fi", scan), ("➜ Join selected", join), ("🕸 Open ad hoc cell (no host)", adhoc)):
        bb = QPushButton(cap); bb.clicked.connect(fn); row.addWidget(bb)
    l.addLayout(row); l.addWidget(wi_out); l.addWidget(wi_list, 1)

    # Links ------------------------------------------------------------------------------
    t = QWidget(); l = QVBoxLayout(t); tabs.addTab(t, "🔗 Links")
    lk = QTextEdit(); lk.setReadOnly(True); lk.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;"); l.addWidget(lk)

    def links():
        lines = []
        try:
            import nearby_groovebox as nb
            lines.append("IPv4: " + ", ".join(nb._local_ipv4()))
            lines.append("IPv6: " + ", ".join(nb._global_ipv6() or ["none"]))
            lines.append("Broadcast: " + ", ".join(nb._iface_broadcasts()))
        except Exception as exc:
            lines.append("nearby: %s" % exc)
        try:
            import psutil
            for n, st in psutil.net_if_stats().items():
                lines.append("%-14s %s %s Mb/s" % (n, "up" if st.isup else "down", st.speed))
        except Exception:
            for n in os.listdir("/sys/class/net") if os.path.isdir("/sys/class/net") else []:
                try:
                    lines.append("%-14s %s" % (n, open("/sys/class/net/%s/operstate" % n).read().strip()))
                except Exception:
                    pass
        svc = getattr(app, "_nearby_share_service", None)
        lines.append("Nearby LAN service: %s" % ("running" if svc is not None else "off"))
        lines.append("Site: %s" % (", ".join(site.urls()) if site.httpd else "off"))
        rm = getattr(app, "_relay_member", None)
        lines.append("Relay: %s" % (rm.state if rm else "not joined"))
        try:
            import hotspot_plan
            hp = hotspot_plan.hotspot_plan(); lines.append("Hotspot / ad-hoc: %s" % ("possible on " + hp["iface"] if hp.get("supported") else hp.get("reason", "n/a")))
        except Exception:
            pass
        lk.setPlainText("\n".join(lines))
    bl = QPushButton("Refresh"); bl.clicked.connect(links); l.addWidget(bl); links()

    app._network_hub_window = w; w.show(); return w


def _share_project(app):
    p = getattr(app, "_current_project_path", None)
    if p and os.path.isfile(p):
        c = gs.load_cfg(); c["files"][p] = True; gs.save_cfg(c)


def autostart(app):
    try:
        if gs.load_cfg().get("autostart"):
            gs.site(app).start()
        c = gs.load_cfg()
        if c.get("relay_url"):
            m = app._relay_member = gs.RelayMember(gs.site(app), c["relay_url"], c["member_id"], c["site_name"])
            m.start()
    except Exception as exc:
        print(f"[Site] autostart: {exc}")
