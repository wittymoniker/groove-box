"""Edit Together — Remote Desktop / trusted screenshare.

Modes
  • lan_host  — share only while this Groovebox is LAN site/host (default)
  • anytime   — share whenever enabled, on trusted peers only

Trust is an explicit allow-list (member id / host name / IP). Frames are
downscaled JPEG/PNG-friendly QPixmap grabs for presence tiles and optional
enlarged Remote Desktop viewer — not a kernel-level RDP server.

Policy is local; peers only receive frames if they appear in the trust list
when a transport publishes them.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_LOCK = threading.RLock()
_STATE: Dict[str, Any] = {
    "enabled": False,
    "mode": "lan_host",          # lan_host | anytime
    "remote_desktop": False,     # enlarged viewer arm
    "trusted": set(),            # type: Set[str]
    "fps": 2.0,
    "max_edge": 960,
    "last_frame": None,
    "last_ts": 0.0,
    "host": None,
    "timer": None,
}


def _config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    d = Path(base) / "groovebox"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path(os.environ.get("TMPDIR", "/tmp"))
    return d / "et_remote_desktop.json"


def load() -> None:
    path = _config_path()
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    with _LOCK:
        _STATE["enabled"] = bool(data.get("enabled", False))
        _STATE["mode"] = "anytime" if data.get("mode") == "anytime" else "lan_host"
        _STATE["remote_desktop"] = bool(data.get("remote_desktop", False))
        _STATE["trusted"] = set(str(x) for x in (data.get("trusted") or []))
        _STATE["fps"] = float(data.get("fps", 2.0))
        _STATE["max_edge"] = int(data.get("max_edge", 960))


def save() -> None:
    with _LOCK:
        data = {
            "enabled": _STATE["enabled"],
            "mode": _STATE["mode"],
            "remote_desktop": _STATE["remote_desktop"],
            "trusted": sorted(_STATE["trusted"]),
            "fps": _STATE["fps"],
            "max_edge": _STATE["max_edge"],
        }
    try:
        _config_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def status() -> Dict[str, Any]:
    with _LOCK:
        return {
            "enabled": _STATE["enabled"],
            "mode": _STATE["mode"],
            "remote_desktop": _STATE["remote_desktop"],
            "trusted": sorted(_STATE["trusted"]),
            "fps": _STATE["fps"],
            "sharing_now": _should_share_unlocked(),
            "last_ts": _STATE["last_ts"],
            "has_frame": _STATE["last_frame"] is not None,
        }


def set_mode(mode: str) -> str:
    m = "anytime" if str(mode).lower().strip() == "anytime" else "lan_host"
    with _LOCK:
        _STATE["mode"] = m
    save()
    return f"screenshare mode={m}"


def set_enabled(on: bool) -> str:
    with _LOCK:
        _STATE["enabled"] = bool(on)
    save()
    return "screenshare " + ("on" if on else "off")


def set_remote_desktop(on: bool) -> str:
    with _LOCK:
        _STATE["remote_desktop"] = bool(on)
    save()
    return "remote_desktop " + ("on" if on else "off")


def trust(peer: str) -> str:
    p = str(peer).strip()
    if not p:
        return "empty peer"
    with _LOCK:
        _STATE["trusted"].add(p)
    save()
    return f"trusted +{p}"


def untrust(peer: str) -> str:
    p = str(peer).strip()
    with _LOCK:
        _STATE["trusted"].discard(p)
    save()
    return f"trusted -{p}"


def is_trusted(peer: str) -> bool:
    with _LOCK:
        return str(peer).strip() in _STATE["trusted"]


def _lan_host_active(host) -> bool:
    if host is None:
        return False
    # Site / network hub host flags used across Groovebox
    for attr in ("_site_server", "_groovebox_site", "site_httpd", "_lan_host"):
        obj = getattr(host, attr, None)
        if obj is None:
            continue
        if obj is True:
            return True
        if getattr(obj, "httpd", None) is not None:
            return True
        if getattr(obj, "active", False) or getattr(obj, "running", False):
            return True
    svc = getattr(host, "_nearby_share_service", None)
    if svc is not None and getattr(svc, "is_host", False):
        return True
    cfg = getattr(host, "_network_cfg", None) or {}
    if isinstance(cfg, dict) and cfg.get("relay_host"):
        return True
    return False


def _should_share_unlocked() -> bool:
    if not _STATE["enabled"]:
        return False
    if _STATE["mode"] == "anytime":
        return True
    return _lan_host_active(_STATE.get("host"))


def should_share(host=None) -> bool:
    with _LOCK:
        if host is not None:
            _STATE["host"] = host
        return _should_share_unlocked()


def grab_frame(host) -> Any:
    """Capture a downscaled frame of the main window (or primary screen)."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return None
    with _LOCK:
        max_edge = int(_STATE["max_edge"])
    pix = None
    try:
        if host is not None and hasattr(host, "grab"):
            pix = host.grab()
        if pix is None or pix.isNull():
            scr = QApplication.primaryScreen()
            if scr is not None:
                pix = scr.grabWindow(0)
    except Exception:
        return None
    if pix is None or pix.isNull():
        return None
    w, h = pix.width(), pix.height()
    scale = min(1.0, float(max_edge) / float(max(w, h, 1)))
    if scale < 0.999:
        from PyQt6.QtCore import Qt as _Qt
        pix = pix.scaled(int(w * scale), int(h * scale),
                         _Qt.AspectRatioMode.KeepAspectRatio,
                         _Qt.TransformationMode.SmoothTransformation)
    with _LOCK:
        _STATE["last_frame"] = pix
        _STATE["last_ts"] = time.time()
    # Stash for presence overlay + live_edit publish
    try:
        if host is not None:
            host._et_local_thumbnail = pix
            host._et_rd_frame = pix
            svc = getattr(host, "_nearby_share_service", None)
            if svc is not None:
                for name in ("set_local_thumbnail", "publish_thumbnail", "set_screenshare_frame"):
                    fn = getattr(svc, name, None)
                    if callable(fn):
                        try:
                            fn(pix)
                        except Exception:
                            pass
    except Exception:
        pass
    return pix


def tick(host) -> None:
    if not should_share(host):
        return
    grab_frame(host)


def start_timer(host) -> str:
    load()
    with _LOCK:
        _STATE["host"] = host
        _STATE["enabled"] = True
    save()
    try:
        from PyQt6.QtCore import QTimer
    except Exception:
        return "screenshare enabled (no Qt timer)"
    with _LOCK:
        t = _STATE.get("timer")
        if t is not None:
            try:
                t.stop()
            except Exception:
                pass
        interval = max(200, int(1000.0 / max(0.5, float(_STATE["fps"]))))
        timer = QTimer(host if host is not None else None)
        timer.setInterval(interval)
        timer.timeout.connect(lambda: tick(host))
        timer.start()
        _STATE["timer"] = timer
    return f"screenshare timer {interval}ms mode={_STATE['mode']}"


def stop_timer() -> str:
    with _LOCK:
        t = _STATE.get("timer")
        _STATE["timer"] = None
        _STATE["enabled"] = False
        if t is not None:
            try:
                t.stop()
            except Exception:
                pass
    save()
    return "screenshare stopped"


def open_remote_viewer(app, peer_name: str = "Peer") -> Any:
    """Enlarged Remote Desktop-style viewer for the latest trusted frame."""
    try:
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt, QTimer
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    dlg = QDialog(app if app is not None else None)
    dlg.setWindowTitle(f"Edit Together · Remote Desktop — {peer_name}")
    dlg.resize(960, 600)
    dlg.setStyleSheet("QDialog{background:#071018;color:#c8e6d8;} QLabel{color:#9fdcca;}")
    lay = QVBoxLayout(dlg)
    lab = QLabel("Waiting for frames…")
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(lab, 1)
    info = QLabel("")
    lay.addWidget(info)

    def refresh():
        with _LOCK:
            pix = _STATE.get("last_frame")
            ts = _STATE.get("last_ts")
        # Prefer peer frame on host if published
        peer_pix = getattr(app, "_et_peer_rd_frame", None) if app is not None else None
        use = peer_pix if peer_pix is not None else pix
        if use is not None and hasattr(use, "isNull") and not use.isNull():
            lab.setPixmap(use.scaled(920, 540, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
            info.setText(f"frame age {time.time() - float(ts or time.time()):.1f}s · trusted screenshare")
        else:
            info.setText("no frame yet · enable screenshare on the source Groovebox")

    t = QTimer(dlg)
    t.setInterval(500)
    t.timeout.connect(refresh)
    t.start()
    refresh()
    dlg.setModal(False)
    dlg.show()
    return dlg


def open_panel(app=None) -> Any:
    """Control surface: trust list, mode, remote desktop toggle."""
    load()
    try:
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
            QListWidget, QCheckBox, QComboBox, QMessageBox,
        )
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    dlg = QDialog(app if app is not None else None)
    dlg.setWindowTitle("Edit Together · Remote Desktop & trusted screenshare")
    dlg.resize(520, 420)
    dlg.setStyleSheet(
        "QDialog{background:#071018;color:#c8e6d8;}"
        "QPushButton{background:#123040;color:#5cf2b0;padding:6px;border-radius:4px;}"
        "QLineEdit,QComboBox,QListWidget{background:#0d1a24;color:#e0fff0;border:1px solid #1e3a4c;}"
    )
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel(
        "Share this screen with trusted Grooveboxes. "
        "LAN host = only while site/host is active. Anytime = whenever enabled."
    ))
    st = QLabel()
    lay.addWidget(st)

    def refresh_status():
        s = status()
        st.setText(
            f"enabled={s['enabled']}  mode={s['mode']}  rd={s['remote_desktop']}  "
            f"sharing_now={s['sharing_now']}  trusted={len(s['trusted'])}"
        )

    mode = QComboBox()
    mode.addItems(["lan_host", "anytime"])
    mode.setCurrentText(status()["mode"])
    mode.currentTextChanged.connect(lambda t: (set_mode(t), refresh_status()))
    lay.addWidget(QLabel("Share when"))
    lay.addWidget(mode)

    en = QCheckBox("Enable screenshare")
    en.setChecked(status()["enabled"])
    en.toggled.connect(lambda v: (set_enabled(v), start_timer(app) if v else stop_timer(), refresh_status()))
    lay.addWidget(en)

    rd = QCheckBox("Remote Desktop viewer option (Edit Together)")
    rd.setChecked(status()["remote_desktop"])
    rd.toggled.connect(lambda v: (set_remote_desktop(v), refresh_status()))
    lay.addWidget(rd)

    lay.addWidget(QLabel("Trusted computers (id / name / IP)"))
    lst = QListWidget()
    lay.addWidget(lst, 1)

    def fill():
        lst.clear()
        for p in status()["trusted"]:
            lst.addItem(p)

    peer_edit = QLineEdit()
    peer_edit.setPlaceholderText("peer id or hostname")
    lay.addWidget(peer_edit)
    row = QHBoxLayout()

    def add_trust():
        trust(peer_edit.text())
        peer_edit.clear()
        fill()
        refresh_status()

    def del_trust():
        it = lst.currentItem()
        if it:
            untrust(it.text())
            fill()
            refresh_status()

    for lab, fn in (("Trust", add_trust), ("Remove", del_trust),
                    ("Open RD viewer", lambda: open_remote_viewer(app)),
                    ("Grab now", lambda: grab_frame(app))):
        b = QPushButton(lab)
        b.clicked.connect(fn)
        row.addWidget(b)
    lay.addLayout(row)
    fill()
    refresh_status()
    if status()["enabled"] and app is not None:
        start_timer(app)
    dlg.setModal(False)
    dlg.show()
    return dlg


# load persisted policy on import
try:
    load()
except Exception:
    pass
