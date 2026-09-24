#!/usr/bin/env python3
"""Basic HTML5 web browser for Groovebox Performance.

Provides a real embedded browser (QtWebEngine / Chromium) so the appliance
can reach upload pages (Google Drive, cloud storage, LAN file receivers,
etc.) directly from the laptop-facing screen, plus a small Wi-Fi / network
settings panel using nmcli so the network can be joined without leaving the
browser view.

File uploads (``<input type="file">``, drag-and-drop upload widgets) are
handled by QtWebEngine's native file-picker integration automatically --
no extra plumbing is required for a page's own upload button to work.

Styled to match the Performance panel (dark teal / gold accent theme).
"""
from __future__ import annotations

import shutil
import subprocess
import os
import html
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile, QWebEnginePage
    WEBENGINE_AVAILABLE = True
except Exception:
    QWebEngineView = None
    QWebEngineSettings = None
    QWebEngineProfile = None
    QWebEnginePage = None
    WEBENGINE_AVAILABLE = False


# Match Performance panel (performance.py) dark teal / gold theme.
_PERF_STYLE = """
    QWidget { background: transparent; color: #d9edf5; }
    QGroupBox {
        border: 1px solid #284c62; border-radius: 7px;
        margin-top: 8px; padding-top: 7px; font-weight: 700;
    }
    QGroupBox::title {
        color: #f1ce68; subcontrol-origin: margin; left: 9px; padding: 0 4px;
    }
    QPushButton {
        background: #102838; color: #d9f7ff;
        border: 1px solid #39708a; border-radius: 11px;
        padding: 8px 11px; font-weight: 700;
    }
    QPushButton:hover { background: #17405a; border-color: #62bfd0; }
    QPushButton:pressed { background: #0c1e2c; }
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QListWidget {
        background: #08141e; color: #e6f8ff;
        border: 1px solid #335b70; border-radius: 8px; padding: 6px;
    }
    QListWidget::item:selected { background: #17354a; color: #f6d46d; }
    QListWidget::item:hover { background: #122c3e; }
    QTabWidget::pane {
        background: rgba(7,16,25,232); border: 2px solid rgba(59,113,140,245);
    }
    QTabBar::tab {
        background: rgba(12,27,40,248); color: #b9d5df;
        padding: 10px 12px; margin: 2px;
        border: 2px solid rgba(53,103,127,250); border-radius: 9px; min-width: 42px;
    }
    QTabBar::tab:hover { background: #122c3e; border-color: #4b879f; }
    QTabBar::tab:selected { background: #17354a; color: #f6d46d; border-color: #6ca6ba; }
    QLabel { color: #d9edf5; }
    QSplitter::handle { background: #284c62; width: 3px; }
"""


def _run(argv: List[str], timeout: float = 8.0) -> Tuple[int, str]:
    try:
        p = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 127, str(exc)


class NetworkSettingsPanel(QWidget):
    """Wi-Fi / network settings using nmcli, embedded next to the browser
    so a fresh appliance can be connected without a separate desktop."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(_PERF_STYLE)
        self._webengine_shutting_down = False
        # Performance is intentionally hidden/reused on normal close, so do not
        # tear WebEngine down on the parent dialog's closeEvent.  Tear it down
        # only when the owning dialog/application is actually being destroyed.
        try:
            if parent is not None:
                parent.destroyed.connect(self.shutdown_webengine)
        except Exception:
            pass
        try:
            from PyQt6.QtCore import QCoreApplication
            app = QCoreApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self.shutdown_webengine)
        except Exception:
            pass
        root = QVBoxLayout(self)

        status_box = QGroupBox("Current connection")
        sf = QFormLayout(status_box)
        self.lbl_current = QLabel("Unknown")
        self.lbl_ip = QLabel("Unknown")
        sf.addRow("Network", self.lbl_current)
        sf.addRow("IP address", self.lbl_ip)
        root.addWidget(status_box)

        scan_box = QGroupBox("Available Wi-Fi networks")
        sb = QVBoxLayout(scan_box)
        self.list_networks = QListWidget()
        sb.addWidget(self.list_networks)
        scan_row = QHBoxLayout()
        btn_scan = QPushButton("↻ Scan")
        btn_scan.clicked.connect(self.refresh)
        scan_row.addWidget(btn_scan)
        sb.addLayout(scan_row)
        root.addWidget(scan_box)

        connect_box = QGroupBox("Connect")
        cf = QFormLayout(connect_box)
        self.edit_ssid = QLineEdit()
        self.edit_ssid.setPlaceholderText("Selected network SSID")
        self.edit_password = QLineEdit()
        self.edit_password.setPlaceholderText("Password (leave blank for open networks)")
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        cf.addRow("SSID", self.edit_ssid)
        cf.addRow("Password", self.edit_password)
        btn_connect = QPushButton("Connect")
        btn_connect.clicked.connect(self._connect)
        btn_disconnect = QPushButton("Disconnect current")
        btn_disconnect.clicked.connect(self._disconnect)
        crow = QHBoxLayout()
        crow.addWidget(btn_connect)
        crow.addWidget(btn_disconnect)
        cf.addRow(crow)
        root.addWidget(connect_box)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color:#8ab4c8; font-size:9pt;")
        root.addWidget(self.lbl_status)
        root.addStretch(1)

        self.list_networks.itemDoubleClicked.connect(self._on_network_double_click)
        QTimer.singleShot(0, self.refresh)

    def _have_nmcli(self) -> bool:
        return bool(shutil.which("nmcli"))

    def refresh(self):
        if not self._have_nmcli():
            self.lbl_status.setText(
                "nmcli not found on this system; Wi-Fi scanning/connecting is unavailable here."
            )
            return
        rc, out = _run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"]
        )
        self.list_networks.clear()
        current = None
        if rc == 0:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) < 4:
                    continue
                active, ssid, signal, security = parts[0], parts[1], parts[2], ":".join(parts[3:])
                if not ssid:
                    continue
                if active == "yes":
                    current = ssid
                label = f"{ssid}  ·  {signal}%  ·  {security or 'open'}"
                item = QListWidgetItem(("🔒 " if security else "📶 ") + label)
                item.setData(Qt.ItemDataRole.UserRole, ssid)
                self.list_networks.addItem(item)
        self._refresh_current_status(current)

    def _refresh_current_status(self, current_hint: Optional[str] = None):
        rc, out = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
        conn_name = current_hint or "Not connected"
        if rc == 0:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 4 and parts[1] == "wifi" and parts[2] == "connected":
                    conn_name = parts[3] or conn_name
        self.lbl_current.setText(conn_name or "Not connected")
        rc_ip, out_ip = _run(["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show"])
        ip = "Unknown"
        if rc_ip == 0:
            for line in out_ip.splitlines():
                if line.startswith("IP4.ADDRESS"):
                    val = line.split(":", 1)[1] if ":" in line else ""
                    if val:
                        ip = val.split("/")[0]
                        break
        self.lbl_ip.setText(ip)

    def _on_network_double_click(self, item: QListWidgetItem):
        ssid = item.data(Qt.ItemDataRole.UserRole)
        if ssid:
            self.edit_ssid.setText(ssid)

    def _connect(self):
        ssid = self.edit_ssid.text().strip()
        if not ssid:
            QMessageBox.information(self, "Connect", "Enter or select an SSID first.")
            return
        if not self._have_nmcli():
            QMessageBox.warning(self, "Connect", "nmcli is not available on this system.")
            return
        password = self.edit_password.text()
        argv = ["nmcli", "dev", "wifi", "connect", ssid]
        if password:
            argv += ["password", password]
        self.lbl_status.setText(f"Connecting to {ssid}…")
        rc, out = _run(argv, timeout=25.0)
        if rc == 0:
            self.lbl_status.setText(f"Connected to {ssid}.")
        else:
            self.lbl_status.setText(f"Connection failed: {out.strip()[:200]}")
        self.refresh()

    def _disconnect(self):
        if not self._have_nmcli():
            return
        rc, out = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
        wifi_dev = None
        if rc == 0:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
                    wifi_dev = parts[0]
                    break
        if not wifi_dev:
            self.lbl_status.setText("No active Wi-Fi connection to disconnect.")
            return
        rc2, out2 = _run(["nmcli", "device", "disconnect", wifi_dev])
        self.lbl_status.setText(
            "Disconnected." if rc2 == 0 else f"Disconnect failed: {out2.strip()[:200]}"
        )
        self.refresh()


class WebBrowserTab(QWidget):
    """Persistent appliance browser with explicit downloads and permissions.

    Browser state is isolated under Groovebox's writable data root, so cookies,
    local storage, logins and downloads survive reboot without polluting or
    depending on a conventional desktop home directory.
    """
    HOME_URL = "groovebox://home"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(_PERF_STYLE)
        root = QVBoxLayout(self); root.setContentsMargins(4,4,4,4)
        if not WEBENGINE_AVAILABLE:
            msg=QLabel("Web Browser unavailable: PyQt6-WebEngine is missing.\n\nThis runtime is incomplete for the v35.22 appliance; run the platform dependency installer or rebuild BUILD_ISO.")
            msg.setWordWrap(True); msg.setStyleSheet("color:#f1ce68; padding:12px;"); root.addWidget(msg); root.addWidget(NetworkSettingsPanel(self)); root.addStretch(1); return
        try:
            import groovebox_paths
            state_root=Path(groovebox_paths.state_dir())/"browser"
            cache_root=Path(groovebox_paths.cache_dir())/"browser"
            download_root=Path(groovebox_paths.downloads_dir())
        except Exception:
            base=Path.home()/".groovebox-browser"; state_root=base/"state"; cache_root=base/"cache"; download_root=base/"downloads"
        for d in (state_root,cache_root,download_root): d.mkdir(parents=True,exist_ok=True)
        self._download_root=str(download_root)

        split=QSplitter(Qt.Orientation.Horizontal)
        browser_side=QWidget(); bl=QVBoxLayout(browser_side); bl.setContentsMargins(0,0,0,0)
        nav=QHBoxLayout(); btn_back=QPushButton("◀"); btn_fwd=QPushButton("▶"); btn_reload=QPushButton("↻"); btn_home=QPushButton("⌂")
        self.edit_url=QLineEdit(); self.edit_url.setPlaceholderText("Enter URL or search…"); self.edit_url.returnPressed.connect(self._navigate_to_typed_url)
        for b in (btn_back,btn_fwd,btn_reload,btn_home): b.setFixedWidth(34)
        for b in (btn_back,btn_fwd,btn_reload,btn_home): nav.addWidget(b)
        nav.addWidget(self.edit_url,stretch=1); bl.addLayout(nav)

        # Keep explicit ownership so the page is torn down before its profile.
        # QtWebEngine can otherwise warn/crash when profile destruction races a
        # still-live QWebEnginePage/request object during Performance shutdown.
        self.profile=QWebEngineProfile("Groovebox",self)
        try:
            self.profile.setPersistentStoragePath(str(state_root/"storage"))
            self.profile.setCachePath(str(cache_root))
            self.profile.setDownloadPath(self._download_root)
            pol=getattr(QWebEngineProfile,"PersistentCookiesPolicy",None)
            if pol is not None: self.profile.setPersistentCookiesPolicy(pol.ForcePersistentCookies)
            cache_type=getattr(QWebEngineProfile,"HttpCacheType",None)
            if cache_type is not None: self.profile.setHttpCacheType(cache_type.DiskHttpCache)
        except Exception: pass
        self.view=QWebEngineView(); self.page=QWebEnginePage(self.profile,self.view); self.view.setPage(self.page)
        try:
            settings=self.view.settings()
            for attr in ("LocalStorageEnabled","JavascriptEnabled","FullScreenSupportEnabled"):
                enum=getattr(QWebEngineSettings.WebAttribute,attr,None)
                if enum is not None: settings.setAttribute(enum,True)
            # Chromium plug-ins are disabled by default in the appliance. HTML5
            # media does not need them; enabling arbitrary plugins widens attack surface.
            plugins=getattr(QWebEngineSettings.WebAttribute,"PluginsEnabled",None)
            if plugins is not None: settings.setAttribute(plugins,False)
        except Exception: pass
        self.view.urlChanged.connect(self._on_url_changed); self.view.loadFinished.connect(self._on_load_finished); bl.addWidget(self.view,stretch=1)
        btn_back.clicked.connect(self.view.back); btn_fwd.clicked.connect(self.view.forward); btn_reload.clicked.connect(self.view.reload); btn_home.clicked.connect(self._load_home)
        self.lbl_browser_status=QLabel(""); self.lbl_browser_status.setWordWrap(True); self.lbl_browser_status.setStyleSheet("color:#8ab4c8; font-size:9pt;"); bl.addWidget(self.lbl_browser_status)
        split.addWidget(browser_side)
        tabs=QTabWidget(); tabs.addTab(NetworkSettingsPanel(),"📶 Network"); tabs.setMaximumWidth(360); split.addWidget(tabs); split.setStretchFactor(0,3); split.setStretchFactor(1,1); root.addWidget(split)

        try: self.profile.downloadRequested.connect(self._on_download_requested)
        except Exception: pass
        try: self.page.permissionRequested.connect(self._on_permission_requested)
        except Exception: pass
        try: self.page.fullScreenRequested.connect(self._on_fullscreen_requested)
        except Exception: pass
        try: self.page.newWindowRequested.connect(self._on_new_window_requested)
        except Exception: pass
        self._load_home()


    def shutdown_webengine(self):
        """Synchronously detach page/request objects before profile teardown.

        QWebEngineProfile must outlive every QWebEnginePage using it.  Performance
        can be closed while download/permission/new-window requests are being
        destroyed, so merely relying on QObject parent order/deleteLater() is not
        deterministic enough here.
        """
        if getattr(self, "_webengine_shutting_down", False):
            return
        self._webengine_shutting_down = True
        page = getattr(self, "page", None)
        profile = getattr(self, "profile", None)
        view = getattr(self, "view", None)
        # First disconnect request-producing signals so no Python callback can
        # retain/use a request wrapper after Chromium destroys the request.
        for obj, signal_name, slot in (
            (profile, "downloadRequested", self._on_download_requested),
            (page, "permissionRequested", self._on_permission_requested),
            (page, "fullScreenRequested", self._on_fullscreen_requested),
            (page, "newWindowRequested", self._on_new_window_requested),
        ):
            try:
                if obj is not None:
                    getattr(obj, signal_name).disconnect(slot)
            except Exception:
                pass
        try:
            if view is not None:
                view.stop()
                view.setHtml("", QUrl("about:blank"))
        except Exception:
            pass
        # Detach the custom page before deleting it; this breaks view->page->
        # profile references before the profile QObject starts destruction.
        try:
            if view is not None:
                view.setPage(None)
        except Exception:
            pass
        try:
            if page is not None:
                page.deleteLater()
        except Exception:
            pass
        self.page = None
        # Flush deferred page deletion while the profile is still guaranteed
        # alive. Avoid a nested long event loop; one Qt turn is sufficient.
        try:
            from PyQt6.QtCore import QCoreApplication, QEvent
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        except Exception:
            pass
        try:
            if profile is not None:
                profile.deleteLater()
        except Exception:
            pass
        self.profile = None

    def closeEvent(self, event):
        self.shutdown_webengine()
        super().closeEvent(event)

    def _home_html(self)->str:
        cards=[
            ("eski-web.org","https://eski-web.org","Math · physics · arts · software"),
            ("Tabletime","https://eski19758.wasmer.app/tabletime/","Tabletime network / calls"),
            ("Groovebox on Itch","https://eski19758.itch.io/mathematicians-groovebox","Releases and ISO distribution"),
            ("Local files","file://"+self._download_root.replace(os.sep,"/"),"Browser downloads / transfer inbox"),
        ]
        body=''.join(f"<a class=card href='{html.escape(url,quote=True)}'><b>{html.escape(title)}</b><small>{html.escape(note)}</small></a>" for title,url,note in cards)
        return f"""<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'><title>Groovebox Home</title><style>body{{background:#071019;color:#d9edf5;font:16px sans-serif;margin:0;padding:28px}}h1{{color:#f1ce68}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}.card{{display:block;text-decoration:none;color:#d9f7ff;background:#102838;border:1px solid #39708a;border-radius:14px;padding:18px}}.card:hover{{background:#17405a}}small{{display:block;color:#8ab4c8;margin-top:8px}}</style><h1>Mathematician's Groovebox · sOS</h1><p>Browser, files, media, games and network tools without leaving the appliance.</p><div class=grid>{body}</div>"""

    def _load_home(self):
        self.edit_url.setText(self.HOME_URL); self.view.setHtml(self._home_html(),QUrl("https://eski-web.org/"))

    def _on_url_changed(self,u):
        txt=u.toString()
        if txt and txt!="about:blank": self.edit_url.setText(txt)

    def _navigate_to_typed_url(self):
        text=self.edit_url.text().strip()
        if not text:return
        if text==self.HOME_URL:self._load_home();return
        if "://" not in text and " " not in text and "." in text:text="https://"+text
        elif " " in text or "." not in text:text="https://www.google.com/search?q="+text.replace(" ","+")
        self.view.setUrl(QUrl(text))

    def _on_download_requested(self,item):
        try:
            if hasattr(item,"setDownloadDirectory"): item.setDownloadDirectory(self._download_root)
            item.accept(); name=item.downloadFileName() if hasattr(item,"downloadFileName") else "download"
            self.lbl_browser_status.setText(f"Downloading {name} → {self._download_root}")
        except Exception as exc:self.lbl_browser_status.setText(f"Download failed to start: {exc}")

    def _on_permission_requested(self,permission):
        try: label=str(permission.permissionType()).split('.')[-1]
        except Exception: label="site permission"
        origin="this site"
        try: origin=permission.origin().toString()
        except Exception: pass
        yes=QMessageBox.question(self,"Browser permission",f"Allow {label} for:\n{origin}?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes
        try: permission.grant() if yes else permission.deny()
        except Exception: pass

    def _on_fullscreen_requested(self,req):
        try:
            req.accept(); self.view.setWindowFlag(Qt.WindowType.Window,req.toggleOn()); self.view.showFullScreen() if req.toggleOn() else self.view.showNormal()
        except Exception: pass

    def _on_new_window_requested(self,req):
        try: self.view.setUrl(req.requestedUrl())
        except Exception: pass

    def _on_load_finished(self,ok:bool):
        self.lbl_browser_status.setText("Loaded." if ok else "Failed to load page.")

