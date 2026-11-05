#!/usr/bin/env python3
"""Nearby Groovebox LAN discovery + safe file exchange.

Every running Groovebox instance can advertise itself on the local IPv4 LAN via
small UDP beacons.  Peers expose a versioned HTTP API for browsing and moving
files.  Received files are data only: this module never imports, executes, or
opens received code/projects automatically.

The network I/O is deliberately ordinary OS sockets/HTTP (where Python delegates
to native system code).  When a Groovebox sCode optimizer is supplied, catalog
rebuild work is coalesced through its universal media work pool; transfer bytes
never pass through sCode or the realtime audio callback.
"""
from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen
import hashlib
import json
import mimetypes
import os
import platform
import shutil
import socket
import threading
import time
import uuid
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from groovebox_direct_link import DirectLinkManager
except Exception:
    DirectLinkManager = None

DISCOVERY_PORT = 37882
DISCOVERY_MAGIC = "MGB_NEARBY_SHARE_V1"
API_VERSION = 1
DEFAULT_HTTP_PORT = 8784
MAX_CATALOG_FILES = 4096
MAX_UPLOAD_BYTES = 16 * 1024 * 1024 * 1024  # explicit 16 GiB sanity ceiling
PEER_TTL = 7.0
BEACON_INTERVAL = 2.0
# GROOVEBOX_R23R_NEARBY_ROBUST_20261101: multicast + per-interface directed
# broadcast + unicast replies + subnet sweep; device-to-device messages.
MCAST_GROUP = "239.255.37.88"
SWEEP_PORTS = (DEFAULT_HTTP_PORT, DEFAULT_HTTP_PORT + 1, DEFAULT_HTTP_PORT + 2)
MAX_MESSAGE_BYTES = 16 * 1024
CHUNK = 1024 * 1024

PROJECT_EXT = {".mcc", ".mgpr", ".meum", ".mg", ".mgb", ".mgproject", ".mgsynth", ".mgprofile"}
MEDIA_EXT = {".wav", ".flac", ".mp3", ".ogg", ".opus", ".aiff", ".aif", ".caf",
             ".mp4", ".webm", ".avi", ".mov", ".mkv", ".png", ".jpg", ".jpeg",
             ".webp", ".bmp", ".gif", ".tif", ".tiff"}
GAME_EXT = {".zip"}
CODE_EXT = {".py", ".pyi", ".sc", ".sC", ".jl", ".cpp", ".hpp", ".h", ".json", ".txt", ".md"}


def _fmt_size(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024.0 or unit == "GB":
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def render_browse_html(rows, name="Groovebox", category="") -> bytes:
    """GROOVEBOX_HOTSPOT_BROWSER_20261102: read-only HTML file browser (any phone or laptop browser).

    Lists only the shared catalog roots (never an arbitrary path); every link is a plain download of
    /api/v1/file, which resolves strictly inside the shared roots.
    """
    import html as _html
    cats = {}
    for r in rows or []:
        cats.setdefault(str(r.get("category", "")), []).append(r)
    category = category if category in cats else ""
    parts = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
             f"<title>{_html.escape(name)} · files</title><style>",
             ":root{color-scheme:dark light}body{font:16px system-ui,sans-serif;margin:0;padding:16px;background:#12161c;color:#d8e6f0}",
             "h1{font-size:20px;margin:0 0 4px}p.s{color:#8da5b8;margin:0 0 12px}a{color:#7fe8ff;text-decoration:none}",
             "nav a{display:inline-block;margin:0 8px 8px 0;padding:6px 10px;border:1px solid #3d5264;border-radius:6px}",
             "nav a.on{background:#00cdb5;color:#0a1014;border-color:#00cdb5}input{width:100%;box-sizing:border-box;padding:9px;margin:6px 0 12px;",
             "border-radius:6px;border:1px solid #46566a;background:#0a0d12;color:#b8f7e6}",
             "table{width:100%;border-collapse:collapse}td{padding:7px 6px;border-bottom:1px solid #26303b;word-break:break-all}",
             "td.z{white-space:nowrap;color:#8da5b8;text-align:right}</style></head><body>",
             f"<h1>{_html.escape(name)}</h1><p class='s'>Files shared by this Groovebox. Tap a name to download.</p><nav>"]
    parts.append(f"<a href='/browse' class='{'on' if not category else ''}'>All ({sum(len(v) for v in cats.values())})</a>")
    for c in sorted(cats):
        parts.append(f"<a href='/browse?category={quote(c)}' class='{'on' if c == category else ''}'>{_html.escape(c)} ({len(cats[c])})</a>")
    parts.append("</nav><input id='f' placeholder='Filter files…' oninput=\"var q=this.value.toLowerCase();"
                 "document.querySelectorAll('tr').forEach(function(r){r.style.display=r.textContent.toLowerCase().indexOf(q)<0?'none':''})\">")
    parts.append("<table>")
    shown = 0
    for c in sorted(cats):
        if category and c != category:
            continue
        for r in cats[c]:
            href = f"/api/v1/file?category={quote(c)}&path={quote(str(r.get('path', '')))}"
            parts.append(f"<tr><td><a href='{href}' download>{_html.escape(str(r.get('path', '')))}</a>"
                         f"<br><small>{_html.escape(c)}</small></td><td class='z'>{_html.escape(_fmt_size(r.get('size', 0)))}</td></tr>")
            shown += 1
            if shown >= 5000:
                break
    if not shown:
        parts.append("<tr><td>No shared files yet.</td></tr>")
    parts.append("</table></body></html>")
    return "".join(parts).encode("utf-8")


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _safe_name(name: str) -> str:
    # basename kills traversal; replace hostile/control characters for portability.
    name = os.path.basename(str(name or "unnamed"))
    cleaned = "".join(ch if (ch.isalnum() or ch in " ._+-()[]{}@#") else "_" for ch in name).strip()
    return cleaned[:240] or "unnamed"


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for i in range(2, 10000):
        p = path.with_name(f"{stem} ({i}){suffix}")
        if not p.exists(): return p
    return path.with_name(f"{stem}-{int(time.time())}{suffix}")


def _local_ipv4() -> List[str]:
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM):
            ip = info[4][0]
            # 169.254.x.x (link-local) is kept: ad hoc / direct-cable links use it.
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    try:
        import subprocess as _sp
        if os.name != "nt" and shutil.which("ip"):
            for ln in _sp.run(["ip", "-o", "-4", "addr", "show", "up"], capture_output=True, text=True, timeout=2).stdout.splitlines():
                parts = ln.split()
                if "inet" in parts:
                    ip = parts[parts.index("inet") + 1].split("/")[0]
                    if ip and not ip.startswith("127."):
                        ips.add(ip)
    except Exception:
        pass
    # UDP connect discovers the preferred interface without sending payload.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        if ip and not ip.startswith("127."): ips.add(ip)
    except Exception: pass
    return sorted(ips)


def _host_url(host: str, port: int) -> str:
    h = str(host)
    if ":" in h and not h.startswith("["):
        h = f"[{h}]"
    return f"http://{h}:{int(port)}"


def _global_ipv6() -> List[str]:
    """Routable IPv6 addresses (internet / VPN links without NAT port forwarding)."""
    out = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6):
            ip = info[4][0].split("%")[0]
            if ip and not ip.startswith(("fe80", "::1", "fd", "fc")) and ":" in ip:
                out.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.connect(("2001:4860:4860::8888", 80)); ip = s.getsockname()[0]; s.close()
        if ip and not ip.startswith(("fe80", "::1")):
            out.add(ip)
    except Exception:
        pass
    return sorted(out)


def _iface_broadcasts() -> List[str]:
    """Directed broadcast address of every IPv4 interface (Wi-Fi, Ethernet, USB, VPN)."""
    out = set()
    try:
        import subprocess as _sp
        if os.name != "nt" and shutil.which("ip"):
            txt = _sp.run(["ip", "-o", "-4", "addr", "show", "up"], capture_output=True, text=True, timeout=2).stdout
            for ln in txt.splitlines():
                parts = ln.split()
                if "brd" in parts:
                    b = parts[parts.index("brd") + 1]
                    if not b.startswith("127."):
                        out.add(b)
    except Exception:
        pass
    try:
        import psutil  # optional
        import ipaddress
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if getattr(a, "family", None) == socket.AF_INET and a.address and a.netmask and not a.address.startswith("127."):
                    out.add(str(ipaddress.IPv4Network(f"{a.address}/{a.netmask}", strict=False).broadcast_address))
    except Exception:
        pass
    if not out:  # assume /24 per local address
        for ip in _local_ipv4():
            parts = ip.split(".")
            if len(parts) == 4:
                out.add(".".join(parts[:3] + ["255"]))
    return sorted(out)


def _node_id(root: Path) -> str:
    marker = root / ".groovebox_nearby_id"
    try:
        if marker.is_file():
            val = marker.read_text(encoding="utf-8").strip()
            if val: return val
        val = uuid.uuid4().hex
        marker.write_text(val, encoding="utf-8")
        return val
    except Exception:
        # Stable enough for one process if directory is read-only.
        return hashlib.sha256((socket.gethostname()+str(root)).encode()).hexdigest()[:32]


def classify_destination(name: str) -> str:
    low = name.lower()
    if low.endswith(".mgbclone.zip"): return "clones"
    ext = Path(name).suffix.lower()
    if ext in PROJECT_EXT: return "projects"
    if ext in MEDIA_EXT: return "samples"
    if ext in GAME_EXT: return "games"
    if ext in CODE_EXT: return "modules"
    return "inbox"


@dataclass
class Peer:
    node_id: str
    name: str
    ip: str
    port: int
    url: str
    platform: str
    version: str
    seen: float
    catalog_id: str = ""
    live: bool = False          # camera/mic stream on (GROOVEBOX_R23R_LIVE_AV_20261101)
    live_mode: str = ""

    def as_dict(self): return dict(self.__dict__)


class NearbyGrooveboxService:
    def __init__(self, app_root: str, roots: Optional[Dict[str, str]] = None,
                 port: int = DEFAULT_HTTP_PORT, name: Optional[str] = None,
                 optimizer=None):
        self.app_root = Path(app_root).expanduser().resolve()
        self.app_root.mkdir(parents=True, exist_ok=True)
        self.node_id = _node_id(self.app_root)
        self.name = str(name or f"{socket.gethostname()} Groovebox")
        self.version = "2026.09 Nearby Share v1"
        self.optimizer = optimizer
        self.roots: Dict[str, Path] = {}
        self._set_roots(roots or {})
        self.port = int(port)
        self.httpd = None
        self.http_thread = None
        self.stop_event = threading.Event()
        self.peers: Dict[str, Peer] = {}
        self.peers_lock = threading.Lock()
        # KNOWN_GROOVEBOX_HISTORY_20260909: persistent discovery history is
        # metadata only and lives in the writable Groovebox data root, never
        # beside received files. It is bounded and rate-limited so discovery
        # cannot turn into a write-amplification source.
        self.history_lock = threading.Lock()
        self.history_path = self.app_root / "state" / "known_grooveboxes.json"
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.known_history: Dict[str, Dict] = self._load_history()
        self._history_last_flush = 0.0
        self.catalog_lock = threading.Lock()
        self._catalog_cache: List[Dict] = []
        self._catalog_stamp = 0.0
        self._catalog_id = ""
        self.beacon_thread = None
        self.listen_thread = None
        self.direct_thread = None
        self.direct_candidates: List[Dict] = []
        self.direct_lock = threading.Lock()
        self.allow_incoming = False
        self.web_browse_enabled = False   # GROOVEBOX_HOTSPOT_BROWSER_20261102: HTML file browser on this Groovebox's address
        self.direct = DirectLinkManager(self.node_id) if DirectLinkManager is not None else None
        # GROOVEBOX_R23R_PEER_LINKS_20261101: automatic LAN in/out switches and
        # manual IP links, persisted next to the history.
        self.settings_path = self.app_root / "state" / "nearby_settings.json"
        try:
            _st = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            _st = {}
        self.announce_enabled = bool(_st.get("announce", True))     # LAN out: send beacons
        self.discover_enabled = bool(_st.get("discover", True))     # LAN in: accept beacons
        self.manual_thread = None
        self.sweep_thread = None
        self.allow_messages = bool(_st.get("messages", True))
        self.messages_path = self.app_root / "state" / "nearby_messages.jsonl"
        self.messages_lock = threading.Lock()
        self._replied: Dict[str, float] = {}
        try:
            from live_stream import LiveBroadcaster
            self.live = LiveBroadcaster()
        except Exception:
            self.live = None
        self.recorders: Dict[str, object] = {}
        self.jam_latest: Dict[str, Dict] = {}
        try:
            from coedit import CoEditManager
            self.coedit = CoEditManager(self)      # GROOVEBOX_R23R_LIVE_EDIT_TOGETHER_20261101
        except Exception:
            self.coedit = None
        self._last_sweep = 0.0
        # One subnet sweep at a time. A previous implementation launched 64
        # blocking socket probes per sweep (up to three ports each), which
        # could leave dozens of GrooveboxSweep threads parked in connect().
        self._sweep_lock = threading.Lock()

    # ------------------------------------------------ messages (device-to-device)
    def _log_message(self, row: Dict):
        with self.messages_lock:
            try:
                with self.messages_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def messages(self, limit: int = 500) -> List[Dict]:
        with self.messages_lock:
            try:
                lines = self.messages_path.read_text(encoding="utf-8").splitlines()[-int(limit):]
            except Exception:
                return []
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
        return out

    def clear_messages(self):
        with self.messages_lock:
            try:
                self.messages_path.unlink()
            except Exception:
                pass

    # GROOVEBOX_R23R_GROUP_TRACE_MESSAGING_20261101 --------------------------
    # Message v2: {"v":2,"id","from_node","from_name","to":[node ids],"group":{id,name,
    # members:[{node,name}]}|None,"text","ts","ttl","trace":[{node,name}]}.
    # Delivery is direct when a recipient is a visible peer; otherwise the message
    # is relayed hop by hop to neighbours not yet in its trace (bounded by ttl,
    # de-duplicated by id). The trace is the route and is shown to the reader.
    MSG_TTL = 4

    def _groups_path(self):
        return self.app_root / "state" / "nearby_groups.json"

    def groups(self) -> Dict[str, Dict]:
        with self.messages_lock:
            try:
                return json.loads(self._groups_path().read_text(encoding="utf-8"))
            except Exception:
                return {}

    def _save_groups(self, groups: Dict[str, Dict]):
        with self.messages_lock:
            try:
                tmp = self._groups_path().with_suffix(".json.tmp")
                tmp.write_text(json.dumps(groups, indent=2, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self._groups_path())
            except Exception:
                pass

    def create_group(self, name: str, members: List[Dict]) -> Dict:
        import uuid
        mem = [{"node": self.node_id, "name": self.name}]
        for m in members or []:
            node = str(m.get("node") or m.get("node_id") or "")
            if node and node != self.node_id and all(x["node"] != node for x in mem):
                mem.append({"node": node, "name": str(m.get("name") or m.get("nickname") or "Groovebox")})
        g = {"id": "grp-" + uuid.uuid4().hex[:12], "name": str(name or "Group").strip()[:60] or "Group",
             "members": mem, "created": time.time(), "owner": self.node_id}
        groups = self.groups(); groups[g["id"]] = g; self._save_groups(groups)
        return g

    def set_group_members(self, group_id: str, members: List[Dict]) -> Dict:
        groups = self.groups(); g = groups.get(group_id)
        if not g:
            raise KeyError("unknown group")
        mem = [{"node": self.node_id, "name": self.name}]
        for m in members or []:
            node = str(m.get("node") or m.get("node_id") or "")
            if node and node != self.node_id and all(x["node"] != node for x in mem):
                mem.append({"node": node, "name": str(m.get("name") or "Groovebox")})
        g["members"] = mem; groups[group_id] = g; self._save_groups(groups)
        return g

    def leave_group(self, group_id: str):
        groups = self.groups(); groups.pop(group_id, None); self._save_groups(groups)

    def _seen_ids(self):
        if not hasattr(self, "_msg_seen"):
            from collections import OrderedDict
            self._msg_seen = OrderedDict()
            for m in self.messages(2000):
                if m.get("id"):
                    self._msg_seen[m["id"]] = True
                    if m.get("dir") == "in":
                        self._msg_seen["mid:" + m["id"]] = True
        return self._msg_seen

    def _mark_seen(self, mid: str) -> bool:
        """True when the id is new (and remembers it, bounded)."""
        seen = self._seen_ids()
        with self.messages_lock:
            if mid in seen:
                return False
            seen[mid] = True
            while len(seen) > 5000:
                seen.popitem(last=False)
        return True

    def _post_message(self, peer: Dict, msg: Dict, timeout=6.0) -> Dict:
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        if len(body) > MAX_MESSAGE_BYTES:
            raise ValueError("message too long (16 KB max)")
        req = Request(peer["url"].rstrip("/") + "/api/v1/message", data=body, method="POST",
                      headers={"Content-Type": "application/json", "X-Groovebox-Node": self.node_id})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace") or "{}")

    def _route(self, msg: Dict) -> Dict:
        """Deliver to visible recipients directly; relay the rest through neighbours."""
        traced = {t.get("node") for t in msg.get("trace", [])}
        peers = {p["node_id"]: p for p in self.peer_list() if not self.is_blocked(p.get("node_id", ""))}
        want = [n for n in msg.get("to", []) if n and n != self.node_id and n not in traced]
        sent, failed = [], []
        for n in want:
            if n in peers:
                try:
                    self._post_message(peers[n], msg); sent.append(n)
                except Exception:
                    failed.append(n)
            else:
                failed.append(n)
        relays = []
        if failed and int(msg.get("ttl", 0)) > 1:
            for nid, p in peers.items():
                if nid in traced or nid in sent:
                    continue
                try:
                    self._post_message(p, msg); relays.append(nid)
                except Exception:
                    pass
        return {"direct": sent, "relayed_via": relays, "unreached": [n for n in failed if not relays]}

    def send_text(self, text: str, to_nodes: List[str] = None, group_id: str = None) -> Dict:
        """Send to one/many Grooveboxes or a group, with direct delivery + traced relaying."""
        import uuid
        text = str(text or "").strip()
        if not text:
            raise ValueError("empty message")
        group = None
        if group_id:
            group = self.groups().get(group_id)
            if not group:
                raise KeyError("unknown group")
            to_nodes = [m["node"] for m in group.get("members", []) if m.get("node") != self.node_id]
        to_nodes = [n for n in (to_nodes or []) if n and n != self.node_id]
        if not to_nodes:
            raise ValueError("no recipients")
        mid = uuid.uuid4().hex
        msg = {"v": 2, "type": "chat", "id": uuid.uuid4().hex, "mid": mid, "from_node": self.node_id, "from_name": self.name,
               "to": to_nodes, "group": group, "text": text, "ts": time.time(), "ttl": self.MSG_TTL,
               "trace": [{"node": self.node_id, "name": self.name}]}
        self._mark_seen(msg["id"])
        res = self._route(msg)
        # GROOVEBOX_R23R_OUTBOX_ACK_20261101: keep it until every recipient acknowledges.
        self._outbox_add(msg)
        names = {p["node_id"]: p.get("name", "Groovebox") for p in self.peer_list()}
        for h in self.known_history.items():
            names.setdefault(h[0], h[1].get("nickname") or h[1].get("name", "Groovebox"))
        self._log_message({"dir": "out", "id": mid, "group_id": (group or {}).get("id", ""),
                           "group_name": (group or {}).get("name", ""),
                           "peer_node": to_nodes[0] if len(to_nodes) == 1 else "",
                           "peer_name": (group or {}).get("name") or ", ".join(names.get(n, "Groovebox") for n in to_nodes),
                           "to": to_nodes, "text": text, "ts": msg["ts"], "route": res})
        return res

    # ---------------------------------------------------- outbox + receipts
    def _outbox_path(self):
        return self.app_root / "state" / "nearby_outbox.json"

    def _outbox_load(self) -> Dict[str, Dict]:
        try:
            return json.loads(self._outbox_path().read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _outbox_save(self, box: Dict[str, Dict]):
        try:
            tmp = self._outbox_path().with_suffix(".json.tmp")
            tmp.write_text(json.dumps(box, ensure_ascii=False), encoding="utf-8"); os.replace(tmp, self._outbox_path())
        except Exception:
            pass

    def _outbox_add(self, msg: Dict):
        with self.messages_lock:
            box = self._outbox_load()
            box[msg["mid"]] = {"msg": msg, "pending": list(msg.get("to", [])), "created": time.time(), "tries": 0}
            self._outbox_save(box)

    def _outbox_acked(self, mid: str, node: str):
        with self.messages_lock:
            box = self._outbox_load(); e = box.get(mid)
            if e is None:
                return
            e["pending"] = [n for n in e.get("pending", []) if n != node]
            if e["pending"]:
                box[mid] = e
            else:
                box.pop(mid, None)
            self._outbox_save(box)

    def outbox_pending(self) -> Dict[str, List[str]]:
        return {k: list(v.get("pending", [])) for k, v in self._outbox_load().items()}

    def delivery_status(self) -> Dict[str, List[str]]:
        """mid -> nodes that acknowledged."""
        out: Dict[str, List[str]] = {}
        for m in self.messages(5000):
            if m.get("dir") == "ack" and m.get("ref"):
                out.setdefault(m["ref"], []).append(m.get("peer_node", ""))
        return out

    def _send_ack(self, mid: str, to_node: str):
        import uuid
        if not to_node or to_node == self.node_id:
            return
        ack = {"v": 2, "type": "ack", "id": uuid.uuid4().hex, "ref": mid, "from_node": self.node_id,
               "from_name": self.name, "to": [to_node], "ts": time.time(), "ttl": self.MSG_TTL,
               "trace": [{"node": self.node_id, "name": self.name}]}
        self._mark_seen(ack["id"])
        threading.Thread(target=self._route, args=(ack,), daemon=True, name="groovebox-msg-ack").start()

    def _outbox_loop(self):
        """Retry unacknowledged messages (store-and-forward for offline members), 7-day expiry."""
        while not self.stop_event.wait(15.0):
            self._outbox_pass()

    def _outbox_pass(self, force=False):
        import uuid
        if True:
            try:
                if not self.peer_list():
                    return
                with self.messages_lock:
                    box = self._outbox_load()
                changed = False
                for mid, e in list(box.items()):
                    if time.time() - float(e.get("created", 0)) > 7 * 86400 or not e.get("pending"):
                        box.pop(mid, None); changed = True; continue
                    if not force and time.time() - float(e.get("last", 0)) < min(600.0, 15.0 * (2 ** min(6, int(e.get("tries", 0))))):
                        continue
                    m = dict(e["msg"]); m["id"] = uuid.uuid4().hex; m["to"] = list(e["pending"])
                    m["trace"] = [{"node": self.node_id, "name": self.name}]
                    self._mark_seen(m["id"]); self._route(m)
                    e["tries"] = int(e.get("tries", 0)) + 1; e["last"] = time.time(); box[mid] = e; changed = True
                if changed:
                    with self.messages_lock:
                        cur = self._outbox_load()
                        for mid in list(cur):           # keep acks that arrived meanwhile
                            if mid in box:
                                box[mid]["pending"] = [n for n in box[mid]["pending"] if n in cur[mid].get("pending", [])]
                        self._outbox_save({k: v for k, v in box.items() if v.get("pending")})
            except Exception:
                pass

    # ----------------------------------------------------------- jam sync
    def send_jam(self, to_nodes: List[str], state: Dict):
        """Leader -> followers: {bpm, playing, pos_s, sent}; direct only (timing)."""
        import uuid
        msg = {"v": 2, "type": "jam", "id": uuid.uuid4().hex, "from_node": self.node_id, "from_name": self.name,
               "to": [n for n in to_nodes if n != self.node_id], "jam": dict(state, sent=time.time()),
               "ts": time.time(), "ttl": 1, "trace": [{"node": self.node_id, "name": self.name}]}
        self._mark_seen(msg["id"])
        return self._route(msg)

    def clock_offset(self, peer: Dict) -> float:
        """peer_clock - my_clock in seconds (NTP-style midpoint; 0.0 when unknown)."""
        best = None
        for _ in range(3):
            t0 = time.time()
            try:
                with urlopen(peer["url"].rstrip("/") + "/api/v1/time", timeout=2.0) as r:
                    pt = float(json.loads(r.read().decode()).get("t", 0))
            except Exception:
                continue
            t1 = time.time()
            cand = (t1 - t0, pt - (t0 + t1) / 2.0)
            if best is None or cand[0] < best[0]:
                best = cand
        return best[1] if best else 0.0

    # ------------------------------------------------------- push-to-talk
    def ptt(self, on: bool) -> Dict:
        """Hold-to-talk: microphone-only live stream while held."""
        if self.live is None:
            raise RuntimeError("live streaming unavailable")
        if on:
            if not self.live.live:
                self.live.start(video=False, audio=True)
                self.live.mode = "ptt mic"
        elif self.live.live and self.live.mode.startswith("ptt"):
            self.live.stop()
        return self.live.status()

    def send_message(self, peer: Dict, text: str, timeout=6.0) -> Dict:
        """Direct message to one peer (kept for callers of the v1 API)."""
        return self.send_text(text, to_nodes=[peer.get("node_id", "")])

    def _receive_message(self, d: Dict, ip: str) -> Dict:
        """Handle an incoming v1/v2 message: log if for us, relay if for others."""
        if int(d.get("v", 1) or 1) < 2:   # legacy direct message
            text = str(d.get("text", "")).strip()[:8000]
            if not text:
                raise ValueError("empty")
            self._log_message({"dir": "in", "peer_node": str(d.get("from_node", ""))[:64],
                               "peer_name": str(d.get("from_name", "Groovebox"))[:80], "ip": ip, "text": text, "ts": time.time()})
            return {"ok": True}
        eid = str(d.get("id", ""))[:64]
        if not eid or not self._mark_seen(eid):
            return {"ok": True, "duplicate": True}
        if self.is_blocked(str(d.get("from_node", ""))):
            return {"ok": True, "dropped": "blocked sender"}
        mid = str(d.get("mid") or eid)[:64]
        mtype = str(d.get("type") or "chat")
        trace = [t for t in (d.get("trace") or []) if isinstance(t, dict)][:16]
        to = [str(n) for n in (d.get("to") or [])][:64]
        group = d.get("group") if isinstance(d.get("group"), dict) else None
        if self.node_id in to and mtype == "ack":
            self._outbox_acked(str(d.get("ref", "")), str(d.get("from_node", "")))
            self._log_message({"dir": "ack", "ref": str(d.get("ref", "")), "peer_node": str(d.get("from_node", ""))[:64],
                               "peer_name": str(d.get("from_name", "Groovebox"))[:80], "ts": time.time()})
        elif self.node_id in to and mtype == "jam":
            st = d.get("jam") if isinstance(d.get("jam"), dict) else {}
            self.jam_latest[str(d.get("from_node", ""))] = {"state": st, "name": str(d.get("from_name", "Groovebox")),
                                                            "recv": time.time()}
        elif self.node_id in to and mtype == "chat" and not self._mark_seen("mid:" + mid):
            self._send_ack(mid, str(d.get("from_node", "")))     # retry of something we already have
        elif self.node_id in to and mtype == "chat":
            self._send_ack(mid, str(d.get("from_node", "")))
            if group and group.get("id"):
                groups = self.groups()
                if group["id"] not in groups:          # first message auto-adds the group
                    groups[group["id"]] = {"id": group["id"], "name": str(group.get("name", "Group"))[:60],
                                           "members": list(group.get("members") or [])[:64], "created": time.time(),
                                           "owner": str(d.get("from_node", ""))}
                    self._save_groups(groups)
            self._log_message({"dir": "in", "id": mid, "group_id": (group or {}).get("id", ""),
                               "group_name": (group or {}).get("name", ""),
                               "peer_node": str(d.get("from_node", ""))[:64], "peer_name": str(d.get("from_name", "Groovebox"))[:80],
                               "ip": ip, "text": str(d.get("text", ""))[:8000], "ts": float(d.get("ts", time.time()) or time.time()),
                               "trace": [t.get("name", "?") for t in trace]})
        ttl = int(d.get("ttl", 0) or 0) - 1
        others = [n for n in to if n != self.node_id]
        if ttl >= 1 and others:
            fwd = dict(d); fwd["ttl"] = ttl
            fwd["trace"] = trace + [{"node": self.node_id, "name": self.name}]
            threading.Thread(target=self._route, args=(fwd,), daemon=True, name="groovebox-msg-relay").start()
        return {"ok": True}

    # ---------------------------------------------------- live camera / mic
    def start_live(self, video=True, audio=True, camera="", mic="", test=False, *,
                   resolution="1080p", fps=30, video_bitrate="6M", encoder="auto") -> Dict:
        if self.live is None:
            raise RuntimeError("live streaming module unavailable")
        return self.live.start(video=video, audio=audio, camera=camera, mic=mic, test=test,
                               resolution=resolution, fps=fps, video_bitrate=video_bitrate, encoder=encoder)

    def stop_live(self):
        if self.live is not None:
            self.live.stop()

    def my_live_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/v1/live"

    @staticmethod
    def live_url(peer: Dict) -> str:
        return peer["url"].rstrip("/") + "/api/v1/live"

    def start_recording(self, key: str, url: str, out_dir: str, label: str) -> str:
        from live_stream import StreamRecorder
        self.stop_recording(key)
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, f"{_safe_name(label)} {time.strftime('%Y-%m-%d %H-%M-%S')}.mkv")
        rec = StreamRecorder(url, out); rec.start(); self.recorders[key] = rec
        return out

    def stop_recording(self, key: str = None) -> List[str]:
        keys = [key] if key else list(self.recorders)
        done = []
        for k in keys:
            rec = self.recorders.pop(k, None)
            if rec is not None:
                done.append(rec.stop())
        return done

    def conversation_transcript(self, group_id: str = "", peer_node: str = "") -> str:
        rows = []
        for m in self.messages(5000):
            if group_id and m.get("group_id") != group_id:
                continue
            if peer_node and (m.get("group_id") or (m.get("peer_node") != peer_node and peer_node not in (m.get("to") or []))):
                continue
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(m.get("ts", 0) or 0)))
            who = "You" if m.get("dir") == "out" else m.get("peer_name", "Groovebox")
            via = f" (via {' → '.join(m.get('trace') or [])})" if len(m.get("trace") or []) > 1 else ""
            rows.append(f"**{who}** · {when}{via}  \n{m.get('text','')}\n")
        return "\n".join(rows)

    def _load_history(self) -> Dict[str, Dict]:
        try:
            doc=json.loads(self.history_path.read_text(encoding="utf-8"))
            rows=doc.get("peers", {}) if isinstance(doc,dict) else {}
            return {str(k):dict(v) for k,v in rows.items() if isinstance(v,dict)}
        except Exception:
            return {}

    def _flush_history(self, force: bool=False):
        now=time.monotonic()
        if not force and now-self._history_last_flush < 8.0: return
        with self.history_lock:
            rows=sorted(self.known_history.items(), key=lambda kv: float(kv[1].get("last_seen",0)), reverse=True)[:512]
            self.known_history=dict(rows)
            doc={"version":1,"updated":time.time(),"peers":self.known_history}
            tmp=self.history_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(doc,indent=2,sort_keys=True),encoding="utf-8")
            os.replace(tmp,self.history_path); self._history_last_flush=now

    def _remember_peer(self, peer: Peer):
        row=peer.as_dict(); row["last_seen"]=float(peer.seen); row.pop("seen",None)
        with self.history_lock:
            # Merge: user organisation (nickname, favourite, group, blocked, manual
            # link) survives every beacon refresh.
            merged=dict(self.known_history.get(str(peer.node_id), {}) or {}); merged.update(row)
            self.known_history[str(peer.node_id)]=merged
        try: self._flush_history(False)
        except Exception: pass

    def history_list(self) -> List[Dict]:
        with self.history_lock:
            rows=[dict(v, node_id=k) for k,v in self.known_history.items()]
        rows.sort(key=lambda r: float(r.get("last_seen",0)), reverse=True)
        return rows

    def forget_peer(self, node_id: str) -> bool:
        node_id=str(node_id or "")
        with self.history_lock:
            existed=self.known_history.pop(node_id,None) is not None
        if existed:
            try: self._flush_history(True)
            except Exception: pass
        return existed

    def reset_history(self) -> int:
        with self.history_lock:
            count=len(self.known_history); self.known_history.clear()
        try:
            if self.history_path.exists(): self.history_path.unlink()
            self._history_last_flush=time.monotonic()
        except Exception: pass
        return count

    def _set_roots(self, roots: Dict[str, str]):
        defaults = {
            "projects": self.app_root / "projects",
            "samples": self.app_root / "samples",
            "games": self.app_root / "games",
            "exports": self.app_root / "exports",
            "modules": self.app_root / "modules",
            "clones": self.app_root / "exports" / "clones",
            "inbox": self.app_root / "Nearby Grooveboxes" / "Inbox",
        }
        for key, default in defaults.items():
            p = Path(roots.get(key, default)).expanduser().resolve()
            p.mkdir(parents=True, exist_ok=True)
            self.roots[key] = p

    def start(self):
        if self.httpd is not None: return self.urls()
        self.stop_event.clear()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "GrooveboxNearby/1"
            def log_message(self, *_): pass
            def _json(self, code, obj):
                data = _json_bytes(obj); self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                try:
                    u = urlparse(self.path); path = u.path; q = parse_qs(u.query)
                    if path == "/api/v1/info":
                        return self._json(200, owner.info())
                    if path == "/api/v1/files":
                        return self._json(200, {"files": owner.catalog(), "catalog_id": owner.catalog_id})
                    if path == "/api/v1/file":
                        cat = (q.get("category") or [""])[0]; rel = (q.get("path") or [""])[0]
                        p = owner.resolve_shared(cat, rel)
                        if p is None or not p.is_file(): return self._json(404, {"error":"not found"})
                        size = p.stat().st_size; self.send_response(200)
                        self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "application/octet-stream")
                        self.send_header("Content-Length", str(size))
                        self.send_header("Content-Disposition", f'attachment; filename="{_safe_name(p.name)}"')
                        self.send_header("X-Groovebox-SHA256", owner.sha256_file(p))
                        self.end_headers()
                        with p.open("rb") as f:
                            for chunk in iter(lambda: f.read(CHUNK), b""):
                                self.wfile.write(chunk)
                        return
                    if path == "/api/v1/time":
                        return self._json(200,{"t":time.time()})
                    if path == "/api/v1/live":
                        lv=owner.live
                        if lv is None or not lv.live: return self._json(404,{"error":"not live"})
                        if owner.is_blocked_ip(str(self.client_address[0]).replace("::ffff:","")):
                            return self._json(403,{"error":"blocked"})
                        q=lv.add_viewer()
                        self.send_response(200); self.send_header("Content-Type","video/mp2t")
                        self.send_header("Cache-Control","no-store"); self.send_header("Connection","close"); self.end_headers()
                        try:
                            while True:
                                try: b=q.get(timeout=10)
                                except Exception: b=None
                                if b is None: break
                                self.wfile.write(b)
                        except (BrokenPipeError,ConnectionResetError,OSError):
                            pass
                        finally:
                            lv.remove_viewer(q)
                        self.close_connection=True
                        return
                    if path in ("/", "/browse") and owner.web_browse_enabled:
                        if owner.is_blocked_ip(str(self.client_address[0]).replace("::ffff:", "")):
                            return self._json(403, {"error": "blocked"})
                        data = render_browse_html(owner.catalog(), owner.name, (q.get("category") or [""])[0])
                        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
                    if path in ("/", "/nearby"):
                        data = ("Groovebox Nearby Share is running. Open Drive / Clone > Nearby Grooveboxes in Groovebox.\n").encode()
                        self.send_response(200); self.send_header("Content-Type","text/plain; charset=utf-8")
                        self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
                    return self._json(404, {"error":"unknown endpoint"})
                except (BrokenPipeError, ConnectionResetError): return
                except Exception as e: return self._json(500, {"error":str(e)})
            def do_POST(self):
                try:
                    u=urlparse(self.path); q=parse_qs(u.query)
                    if u.path == "/api/v1/coedit":
                        if owner.coedit is None: return self._json(404,{"error":"live edit unavailable"})
                        if owner.is_blocked_ip(str(self.client_address[0]).replace("::ffff:","")) or owner.is_blocked(self.headers.get("X-Groovebox-Node","")):
                            return self._json(403,{"error":"blocked"})
                        length=int(self.headers.get("Content-Length","0") or 0)
                        from coedit import MAX_COEDIT_BYTES
                        if length<=0 or length>MAX_COEDIT_BYTES: return self._json(413,{"error":"invalid/too large"})
                        d=json.loads(self.rfile.read(length).decode("utf-8","replace"))
                        if not isinstance(d,dict) or not d.get("session"): return self._json(400,{"error":"bad payload"})
                        d["from_node"]=str(self.headers.get("X-Groovebox-Node") or d.get("from_node",""))
                        owner.coedit.receive(d)
                        return self._json(201,{"ok":True})
                    if u.path == "/api/v1/ptt":
                        if str(self.client_address[0]).replace("::ffff:","") not in ("127.0.0.1","::1"):
                            return self._json(403,{"error":"local only"})
                        try:
                            return self._json(200, owner.ptt(((q.get("on") or ["0"])[0]) in ("1","true","on")))
                        except Exception as _e:
                            return self._json(500,{"error":str(_e)})
                    if u.path == "/api/v1/message":
                        if not owner.allow_messages: return self._json(403,{"error":"receiver has messages turned off"})
                        if owner.is_blocked_ip(str(self.client_address[0]).replace("::ffff:","")) or owner.is_blocked(self.headers.get("X-Groovebox-Node","")):
                            return self._json(403,{"error":"this Groovebox is blocked by the receiver"})
                        length=int(self.headers.get("Content-Length","0") or 0)
                        if length<=0 or length>MAX_MESSAGE_BYTES: return self._json(413,{"error":"invalid/too large message"})
                        d=json.loads(self.rfile.read(length).decode("utf-8","replace"))
                        try:
                            res=owner._receive_message(d,str(self.client_address[0]).replace("::ffff:",""))
                        except ValueError as _e:
                            return self._json(400,{"error":str(_e)})
                        return self._json(201,res)
                    if u.path != "/api/v1/upload": return self._json(404,{"error":"unknown endpoint"})
                    if not owner.allow_incoming: return self._json(403,{"error":"receiver has Nearby Share incoming files disabled"})
                    if owner.is_blocked_ip(str(self.client_address[0]).replace("::ffff:","")) or owner.is_blocked(self.headers.get("X-Groovebox-Node","")):
                        return self._json(403,{"error":"this Groovebox is blocked by the receiver"})
                    length = int(self.headers.get("Content-Length","0") or 0)
                    if length <= 0 or length > MAX_UPLOAD_BYTES: return self._json(413,{"error":"invalid/too large body"})
                    name = _safe_name((q.get("name") or [self.headers.get("X-Groovebox-Filename", "unnamed")])[0])
                    category = (q.get("category") or ["auto"])[0].lower()
                    if category == "auto": category = classify_destination(name)
                    target = owner.receive_target(category, name)
                    tmp = target.with_name(target.name + ".part")
                    h=hashlib.sha256(); remaining=length
                    with tmp.open("wb") as f:
                        while remaining:
                            chunk=self.rfile.read(min(CHUNK,remaining))
                            if not chunk: raise IOError("upload ended early")
                            f.write(chunk); h.update(chunk); remaining-=len(chunk)
                    expected=(self.headers.get("X-Groovebox-SHA256") or "").lower().strip()
                    actual=h.hexdigest()
                    if expected and actual != expected:
                        try: tmp.unlink()
                        except Exception: pass
                        return self._json(422,{"error":"SHA-256 mismatch","sha256":actual})
                    os.replace(tmp,target)
                    target, category = owner._route_received(target, category)
                    owner.invalidate_catalog()
                    return self._json(201,{"ok":True,"category":category,"name":target.name,"path":str(target),"size":length,"sha256":actual})
                except Exception as e:
                    return self._json(500,{"error":str(e)})

        # Auto-select a nearby free port if another local Groovebox owns the default.
        last = None
        class _DualStack(ThreadingHTTPServer):
            # GROOVEBOX_R23R_ADHOC_20261101: IPv6 + IPv4 on one socket so
            # groovebox://[ipv6]:port links work over the internet/VPNs.
            address_family = socket.AF_INET6
            def server_bind(self):
                try: self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                except Exception: pass
                super().server_bind()
        self._dual_stack = False
        for p in list(range(self.port, min(65535,self.port+12))) + [0]:
            try:
                try:
                    if not socket.has_ipv6: raise OSError("no IPv6")
                    self.httpd = _DualStack(("::", p), Handler); self._dual_stack = True
                except OSError:
                    self.httpd = ThreadingHTTPServer(("0.0.0.0", p), Handler)
                self.httpd.daemon_threads = True
                self.port = int(self.httpd.server_address[1]); break
            except OSError as e: last=e; self.httpd=None
        if self.httpd is None: raise last or OSError("Unable to bind Nearby Share")
        self.http_thread=threading.Thread(target=self.httpd.serve_forever,name="groovebox-nearby-http",daemon=True); self.http_thread.start()
        self.beacon_thread=threading.Thread(target=self._beacon_loop,name="groovebox-nearby-beacon",daemon=True); self.beacon_thread.start()
        self.listen_thread=threading.Thread(target=self._listen_loop,name="groovebox-nearby-listen",daemon=True); self.listen_thread.start()
        self.manual_thread=threading.Thread(target=self._manual_loop,name="groovebox-nearby-links",daemon=True); self.manual_thread.start()
        self.sweep_thread=threading.Thread(target=self._sweep_loop,name="groovebox-nearby-sweep",daemon=True); self.sweep_thread.start()
        threading.Thread(target=self._outbox_loop,name="groovebox-nearby-outbox",daemon=True).start()
        if self.direct is not None:
            self.direct_thread=threading.Thread(target=self._direct_scan_loop,name="groovebox-direct-scan",daemon=True); self.direct_thread.start()
        return self.urls()

    def stop(self):
        try:
            self.stop_live(); self.stop_recording()
        except Exception:
            pass
        try: self._flush_history(True)
        except Exception: pass
        self.stop_event.set()
        if self.httpd is not None:
            try: self.httpd.shutdown(); self.httpd.server_close()
            except Exception: pass
            self.httpd=None
        for t in (self.http_thread,self.beacon_thread,self.listen_thread,
                  self.direct_thread,self.manual_thread,self.sweep_thread):
            if t and t is not threading.current_thread():
                try: t.join(timeout=.7)
                except Exception: pass
        self.http_thread=self.beacon_thread=self.listen_thread=self.direct_thread=None
        self.manual_thread=self.sweep_thread=None

    def urls(self):
        return [f"http://{ip}:{self.port}/" for ip in _local_ipv4()] or [f"http://127.0.0.1:{self.port}/"]

    def set_web_browse(self, enabled: bool):
        """Turn the read-only HTML file browser on or off (the Performance hotspot toggle drives this)."""
        self.web_browse_enabled = bool(enabled)
        return self.web_browse_enabled

    def info(self):
        caps=["discover","browse","download","upload","sha256","router-free-direct","multicast","sweep","message","message-v2","groups","relay","adhoc","ipv6","live-av","record","ack","outbox","jam","ptt","project-bundle","live-edit"]
        return {"magic":DISCOVERY_MAGIC,"api":API_VERSION,"node_id":self.node_id,"name":self.name,
                "port":self.port,"platform":platform.system(),"version":self.version,
                "catalog_id":self._catalog_id,"capabilities":caps,
                "incoming_enabled":bool(self.allow_incoming),
                "live":bool(self.live is not None and self.live.live),
                "live_mode":(self.live.mode if self.live is not None and self.live.live else ""),
                "direct":(self.direct.capabilities() if self.direct is not None else {})}

    @property
    def catalog_id(self):
        self.catalog()
        return self._catalog_id

    def invalidate_catalog(self):
        with self.catalog_lock: self._catalog_stamp=0.0

    def _scan_catalog(self):
        rows=[]
        for category, root in self.roots.items():
            if category == "inbox": continue
            try:
                for p in root.rglob("*"):
                    if not p.is_file(): continue
                    try:
                        rel=p.relative_to(root).as_posix(); st=p.stat()
                    except Exception: continue
                    rows.append({"category":category,"path":rel,"name":p.name,"size":int(st.st_size),
                                 "mtime":float(st.st_mtime),"kind":classify_destination(p.name)})
                    if len(rows) >= MAX_CATALOG_FILES: break
            except Exception: pass
            if len(rows) >= MAX_CATALOG_FILES: break
        rows.sort(key=lambda x:(x["category"],x["path"].lower()))
        compact=[(r["category"],r["path"],r["size"],int(r["mtime"])) for r in rows]
        self._catalog_id=hashlib.sha256(_json_bytes(compact)).hexdigest()[:16]
        return rows

    def catalog(self):
        now=time.monotonic()
        with self.catalog_lock:
            if self._catalog_cache and now-self._catalog_stamp < 3.0: return list(self._catalog_cache)
        # Scan outside lock. If sCode is present, its media pool coalesces duplicate
        # scan requests from UI/network consumers. Never block audio on this path.
        rows=None
        opt=self.optimizer
        if opt is not None:
            try:
                payload={"nearby_catalog":True,"roots":{k:str(v) for k,v in self.roots.items()},"bucket":int(now//3)}
                fut=opt.submit_pooled("media",payload,self._scan_catalog,policy="generation",format_id="object",max_entries=4)
                rows=fut.result(timeout=8.0)
            except Exception: rows=None
        if rows is None: rows=self._scan_catalog()
        with self.catalog_lock:
            self._catalog_cache=list(rows); self._catalog_stamp=time.monotonic(); return list(self._catalog_cache)

    def resolve_shared(self, category: str, rel: str) -> Optional[Path]:
        root=self.roots.get(str(category).lower())
        if root is None: return None
        try:
            p=(root/unquote(rel)).resolve()
            if p == root or root not in p.parents: return None
            return p
        except Exception: return None

    def receive_target(self, category: str, name: str) -> Path:
        category=str(category).lower()
        if category not in self.roots: category=classify_destination(name)
        if category not in self.roots: category="inbox"
        root=self.roots[category] / "Incoming Groovebox"
        root.mkdir(parents=True,exist_ok=True)
        return _dedupe_path(root/_safe_name(name))

    def _route_received(self, target: Path, category: str):
        """.MCC is a game package, media or a project: file it where Groovebox looks."""
        try:
            if target.suffix.lower() == ".mcc":
                import mcc_media as _mm
                kind = _mm.media_kind(str(target))
                want = {"package": "games", "audio": "samples", "video": "samples", "image": "samples"}.get(kind)
                if kind == "package":
                    try:
                        if ((_mm.read_header(str(target)) or {}).get("manifest") or {}).get("kind") == "project-bundle":
                            want = "projects"     # shared project session (project + samples)
                    except Exception:
                        pass
                if want and want != category and want in self.roots:
                    dest = self.receive_target(want, target.name)
                    os.replace(target, dest)
                    return dest, want
        except Exception:
            pass
        return target, category

    @staticmethod
    def sha256_file(path: Path, progress=None) -> str:
        h=hashlib.sha256(); done=0; total=path.stat().st_size
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(CHUNK),b""):
                h.update(chunk); done+=len(chunk)
                if progress: progress(done,total,"hash")
        return h.hexdigest()

    def _beacon_loop(self):
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try: s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
        except Exception: pass
        try: s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,1)
        except Exception: pass
        targets=[]; refreshed=0.0
        while not self.stop_event.is_set():
            if self.announce_enabled:
                now=time.time()
                if now-refreshed>30.0:   # interfaces come and go (Wi-Fi join, USB tether)
                    targets=["255.255.255.255"]+[b for b in _iface_broadcasts() if b!="255.255.255.255"]+[MCAST_GROUP]
                    refreshed=now
                msg=self.info(); msg["ts"]=now
                data=_json_bytes(msg)
                for t in targets:
                    try: s.sendto(data,(t,DISCOVERY_PORT))
                    except Exception: pass
            self.stop_event.wait(BEACON_INTERVAL)
        try:s.close()
        except Exception:pass

    def _listen_loop(self):
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try: s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        except Exception: pass
        try:
            if hasattr(socket,"SO_REUSEPORT"): s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEPORT,1)
        except Exception: pass
        try: s.bind(("",DISCOVERY_PORT))
        except OSError:
            try: s.bind(("0.0.0.0",0))
            except Exception: return
        try:
            mreq=socket.inet_aton(MCAST_GROUP)+socket.inet_aton("0.0.0.0")
            s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,mreq)
        except Exception:
            pass
        s.settimeout(1.0)
        while not self.stop_event.is_set():
            try: raw,addr=s.recvfrom(65507)
            except socket.timeout: continue
            except OSError: break
            try:
                if not self.discover_enabled: continue
                d=json.loads(raw.decode("utf-8","replace"))
                if d.get("magic")!=DISCOVERY_MAGIC or d.get("node_id")==self.node_id: continue
                if self.is_blocked(str(d.get("node_id",""))): continue
                port=int(d.get("port",DEFAULT_HTTP_PORT)); ip=addr[0]
                peer=Peer(str(d.get("node_id","")),str(d.get("name","Groovebox")),ip,port,
                          f"http://{ip}:{port}",str(d.get("platform","")),str(d.get("version","")),time.time(),str(d.get("catalog_id","")))
                peer.live=bool(d.get('live')); peer.live_mode=str(d.get('live_mode',''))
                with self.peers_lock: self.peers[peer.node_id]=peer
                self._remember_peer(peer)
                # Unicast hello back so a peer whose broadcasts are filtered
                # still finds us within one beacon interval.
                if self.announce_enabled and not d.get("reply") and time.time()-self._replied.get(peer.node_id,0.0)>10.0:
                    self._replied[peer.node_id]=time.time()
                    try:
                        hello=self.info(); hello["ts"]=time.time(); hello["reply"]=True
                        s.sendto(_json_bytes(hello),(ip,DISCOVERY_PORT))
                    except Exception:
                        pass
            except Exception: continue
        try:s.close()
        except Exception:pass

    def sweep_subnet(self, timeout: float = 0.12, workers: int = 12) -> List[Dict]:
        """Bounded fallback scan for Groovebox peers on local /24 networks.

        Discovery beacons are the primary path. This fallback is deliberately
        conservative: at most 12 simultaneous probes, short per-port connect
        timeouts, and no overlapping sweeps. It must never starve audio/UI work.
        """
        from concurrent.futures import ThreadPoolExecutor
        if self.stop_event.is_set() or not self.discover_enabled:
            return []
        if not self._sweep_lock.acquire(blocking=False):
            return []
        try:
            mine = set(_local_ipv4())
            hosts = []
            for ip in mine:
                parts = ip.split(".")
                if len(parts) != 4:
                    continue
                base = ".".join(parts[:3])
                hosts.extend(f"{base}.{i}" for i in range(1, 255)
                             if f"{base}.{i}" not in mine)
            self._last_sweep = time.time()
            connect_timeout = max(0.05, min(0.20, float(timeout)))
            api_timeout = max(0.15, min(0.50, connect_timeout * 2.0))

            def probe(host):
                if self.stop_event.is_set():
                    return None
                for port in SWEEP_PORTS:
                    if self.stop_event.is_set():
                        return None
                    try:
                        with socket.create_connection((host, port), timeout=connect_timeout):
                            pass
                    except (OSError, TimeoutError):
                        continue
                    try:
                        with urlopen(f"http://{host}:{port}/api/v1/info", timeout=api_timeout) as r:
                            d = json.loads(r.read().decode())
                        if (d.get("magic") == DISCOVERY_MAGIC
                                and d.get("node_id") != self.node_id
                                and not self.is_blocked(str(d.get("node_id", "")))):
                            peer = Peer(str(d.get("node_id", "")), str(d.get("name", "Groovebox")),
                                        host, port, f"http://{host}:{port}",
                                        str(d.get("platform", "")), str(d.get("version", "")),
                                        time.time(), str(d.get("catalog_id", "")))
                            peer.live = bool(d.get("live"))
                            peer.live_mode = str(d.get("live_mode", ""))
                            with self.peers_lock:
                                self.peers[peer.node_id] = peer
                            self._remember_peer(peer)
                            return peer.as_dict()
                    except Exception:
                        continue
                return None

            found = []
            # Explicit cap prevents caller-provided values from creating a
            # large blocking thread fan-out on high-core-count machines.
            worker_count = max(4, min(12, int(workers)))
            with ThreadPoolExecutor(max_workers=worker_count,
                                    thread_name_prefix="GrooveboxSweep") as ex:
                for result in ex.map(probe, hosts):
                    if result:
                        found.append(result)
                    if self.stop_event.is_set():
                        break
            return found
        finally:
            self._sweep_lock.release()

    def _sweep_loop(self):
        """Automatic fallback: sweep shortly after start and then every 90 s while no peer is visible."""
        self.stop_event.wait(6.0)
        while not self.stop_event.is_set():
            try:
                if self.discover_enabled and not self.peer_list():
                    self.sweep_subnet()
            except Exception:
                pass
            self.stop_event.wait(90.0)


    def _direct_scan_loop(self):
        # Radio scans are intentionally low-rate and live outside the GUI/audio
        # threads. Performance can request an immediate scan when its Nearby tab
        # is visible. This keeps the Pokemon-Go-style nearby presence without a
        # high-frequency battery/CPU poll.
        while not self.stop_event.is_set():
            try:
                self.scan_direct_now()
            except Exception:
                pass
            self.stop_event.wait(12.0)

    def scan_direct_now(self) -> List[Dict]:
        rows = self.direct.scan() if self.direct is not None else []
        # Never list our own AP as a candidate.
        own = getattr(self.direct, "ssid", None) if self.direct is not None else None
        rows = [r for r in rows if r.get("ssid") != own]
        with self.direct_lock:
            self.direct_candidates = list(rows)
        return list(rows)

    def direct_candidate_list(self) -> List[Dict]:
        with self.direct_lock:
            return list(self.direct_candidates)

    def start_direct_hotspot(self):
        if self.direct is None: return False, "Direct Wi-Fi is unavailable."
        return self.direct.start_hotspot()

    def stop_direct_hotspot(self):
        if self.direct is None: return False, "Direct Wi-Fi is unavailable."
        return self.direct.stop_hotspot()

    def join_direct(self, ssid: str):
        if self.direct is None: return False, "Direct Wi-Fi is unavailable."
        ok, msg = self.direct.join(ssid)
        if ok:
            # Give DHCP a moment; UDP discovery will populate peers naturally.
            time.sleep(1.0)
        return ok, msg

    # ---------------------------------------------- links, LAN switches, organising
    def _save_settings(self):
        try:
            tmp=self.settings_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"announce":self.announce_enabled,"discover":self.discover_enabled,
                                       "messages":bool(getattr(self,"allow_messages",True))},indent=2),encoding="utf-8")
            os.replace(tmp,self.settings_path)
        except Exception:
            pass

    def set_lan(self, announce=None, discover=None):
        """Automatic LAN out (announce beacons) / in (accept beacons)."""
        if announce is not None: self.announce_enabled=bool(announce)
        if discover is not None:
            self.discover_enabled=bool(discover)
            if not self.discover_enabled:
                with self.peers_lock:
                    self.peers={k:v for k,v in self.peers.items() if (self.known_history.get(k) or {}).get("manual")}
        self._save_settings()
        return {"announce":self.announce_enabled,"discover":self.discover_enabled}

    def my_links(self) -> List[str]:
        links = [f"groovebox://{ip}:{self.port}" for ip in _local_ipv4()]
        if getattr(self, "_dual_stack", False):
            links += [f"groovebox://[{ip}]:{self.port}" for ip in _global_ipv6()]
        return links

    def start_adhoc(self):
        if self.direct is None or not hasattr(self.direct, "start_adhoc"):
            return False, "Ad hoc control unavailable."
        r = self.direct.start_adhoc()
        self._last_sweep = 0.0
        # One subnet sweep at a time. A previous implementation launched 64
        # blocking socket probes per sweep (up to three ports each), which
        # could leave dozens of GrooveboxSweep threads parked in connect().
        self._sweep_lock = threading.Lock()
        return r

    def stop_adhoc(self):
        if self.direct is None or not hasattr(self.direct, "stop_adhoc"):
            return False, "Ad hoc control unavailable."
        return self.direct.stop_adhoc()

    @staticmethod
    def parse_link(link: str):
        t=str(link or "").strip()
        for pre in ("groovebox://","http://","https://"):
            if t.lower().startswith(pre): t=t[len(pre):]
        t=t.split("/",1)[0]
        if not t: raise ValueError("enter an IP address, host:port or groovebox:// link")
        if t.startswith("["):       # [ipv6]:port
            host,_,rest=t[1:].partition("]"); port=int(rest.lstrip(":") or DEFAULT_HTTP_PORT)
        elif t.count(":")==1:
            host,port=t.split(":"); port=int(port)
        else:
            host,port=t,DEFAULT_HTTP_PORT
        if not (0 < int(port) < 65536): raise ValueError("port out of range")
        return host,int(port)

    def add_link(self, link: str, timeout=4.0) -> Dict:
        """Connect to a Groovebox by IP / host:port / groovebox:// link (verified via its info API)."""
        host,port=self.parse_link(link)
        url=_host_url(host,port)
        with urlopen(url+"/api/v1/info",timeout=timeout) as r: d=json.loads(r.read().decode())
        if d.get("magic")!=DISCOVERY_MAGIC: raise ValueError("that address is not a Groovebox")
        if d.get("node_id")==self.node_id: raise ValueError("that is this Groovebox")
        peer=Peer(str(d.get("node_id","")),str(d.get("name","Groovebox")),host,port,url,
                  str(d.get("platform","")),str(d.get("version","")),time.time(),str(d.get("catalog_id","")))
        peer.live=bool(d.get('live')); peer.live_mode=str(d.get('live_mode',''))
        with self.peers_lock: self.peers[peer.node_id]=peer
        self._remember_peer(peer)
        self.set_peer_meta(peer.node_id, manual=True, link="groovebox://"+_host_url(host,port)[len("http://"):])
        return peer.as_dict()

    def _manual_loop(self):
        """Keep manually linked peers alive (they are not on the beacon LAN)."""
        while not self.stop_event.is_set():
            with self.history_lock:
                rows=[(k,dict(v)) for k,v in self.known_history.items() if v.get("manual") and not v.get("blocked")]
            for node_id,row in rows:
                if self.stop_event.is_set(): break
                try:
                    host,port=self.parse_link(row.get("link") or f"{row.get('ip')}:{row.get('port')}")
                    with urlopen(_host_url(host,port)+"/api/v1/info",timeout=2.5) as r: d=json.loads(r.read().decode())
                    if d.get("node_id")==node_id:
                        peer=Peer(node_id,str(d.get("name","Groovebox")),host,port,_host_url(host,port),
                                  str(d.get("platform","")),str(d.get("version","")),time.time(),str(d.get("catalog_id","")))
                        peer.live=bool(d.get('live')); peer.live_mode=str(d.get('live_mode',''))
                        with self.peers_lock: self.peers[node_id]=peer
                        self._remember_peer(peer)
                except Exception:
                    pass
            self.stop_event.wait(max(2.0, PEER_TTL * 0.6))

    def set_peer_meta(self, node_id: str, **meta) -> Dict:
        """Organise the peer list: nickname, favorite, group, blocked, manual/link."""
        node_id=str(node_id or "")
        allowed={"nickname","favorite","group","blocked","manual","link","ip"}
        with self.history_lock:
            row=dict(self.known_history.get(node_id, {"name":"Groovebox","last_seen":0.0}))
            for k,v in meta.items():
                if k in allowed:
                    if v is None: row.pop(k,None)
                    else: row[k]=v
            self.known_history[node_id]=row
        if meta.get("blocked"):
            with self.peers_lock: self.peers.pop(node_id,None)
        try: self._flush_history(True)
        except Exception: pass
        return row

    def is_blocked(self, node_id: str) -> bool:
        with self.history_lock:
            return bool((self.known_history.get(str(node_id)) or {}).get("blocked"))

    def is_blocked_ip(self, ip: str) -> bool:
        with self.history_lock:
            return any(v.get("blocked") and str(v.get("ip"))==str(ip) for v in self.known_history.values())

    def organised_list(self) -> List[Dict]:
        """History rows sorted: favourites, then group, then nickname/name; online flag added."""
        online=set()
        with self.peers_lock: online=set(self.peers)
        rows=self.history_list()
        for r in rows: r["online"]=r.get("node_id") in online
        rows.sort(key=lambda r:(not r.get("favorite"),bool(r.get("blocked")),str(r.get("group") or "~"),
                                str(r.get("nickname") or r.get("name") or "").lower()))
        return rows

    def set_incoming_enabled(self, enabled: bool):
        self.allow_incoming = bool(enabled)
        return self.allow_incoming

    def peer_list(self) -> List[Dict]:
        now=time.time()
        with self.peers_lock:
            self.peers={k:v for k,v in self.peers.items() if now-v.seen < PEER_TTL}
            return [p.as_dict() for p in sorted(self.peers.values(),key=lambda p:(p.name.lower(),p.ip,p.port))]

    # ------------------------------- client helpers (call from worker threads)
    @staticmethod
    def fetch_info(peer: Dict, timeout=3.0):
        with urlopen(peer["url"].rstrip("/")+"/api/v1/info",timeout=timeout) as r: return json.loads(r.read().decode())

    @staticmethod
    def fetch_files(peer: Dict, timeout=8.0):
        with urlopen(peer["url"].rstrip("/")+"/api/v1/files",timeout=timeout) as r: return json.loads(r.read().decode()).get("files",[])

    def download(self, peer: Dict, item: Dict, destination="auto", progress=None) -> str:
        category=item.get("category",""); rel=item.get("path",""); name=_safe_name(item.get("name") or Path(rel).name)
        destcat=classify_destination(name) if destination=="auto" else str(destination)
        target=self.receive_target(destcat,name); tmp=target.with_name(target.name+".part")
        url=peer["url"].rstrip("/")+f"/api/v1/file?category={quote(str(category))}&path={quote(str(rel))}"
        req=Request(url,headers={"User-Agent":"Groovebox-Nearby/1"})
        with urlopen(req,timeout=30.0) as r:
            total=int(r.headers.get("Content-Length","0") or 0); expected=(r.headers.get("X-Groovebox-SHA256") or "").lower(); done=0; h=hashlib.sha256()
            with tmp.open("wb") as f:
                while True:
                    chunk=r.read(CHUNK)
                    if not chunk: break
                    f.write(chunk); h.update(chunk); done+=len(chunk)
                    if progress: progress(done,total,"download")
        actual=h.hexdigest()
        if expected and actual!=expected:
            try:tmp.unlink()
            except Exception:pass
            raise IOError("Downloaded file SHA-256 did not match sender")
        os.replace(tmp,target); target,_c=self._route_received(target,destcat); self.invalidate_catalog(); return str(target)

    def upload(self, peer: Dict, local_path: str, destination="auto", progress=None) -> Dict:
        p=Path(local_path).expanduser().resolve()
        if not p.is_file(): raise FileNotFoundError(str(p))
        digest=self.sha256_file(p,progress)
        # HTTPConnection is used directly so progress is reported without buffering the whole file.
        import http.client
        u=urlparse(peer["url"]); conn=http.client.HTTPConnection(u.hostname,u.port,timeout=30.0)
        category=str(destination or "auto")
        path=f"/api/v1/upload?category={quote(category)}&name={quote(p.name)}"
        conn.putrequest("POST",path); conn.putheader("Content-Length",str(p.stat().st_size)); conn.putheader("Content-Type","application/octet-stream")
        conn.putheader("X-Groovebox-SHA256",digest); conn.putheader("X-Groovebox-Filename",p.name)
        conn.putheader("X-Groovebox-Node",self.node_id); conn.endheaders()
        done=0; total=p.stat().st_size
        with p.open("rb") as f:
            for chunk in iter(lambda:f.read(CHUNK),b""):
                conn.send(chunk); done+=len(chunk)
                if progress: progress(done,total,"upload")
        resp=conn.getresponse(); body=resp.read(); conn.close()
        data=json.loads(body.decode("utf-8","replace") or "{}")
        if resp.status not in (200,201): raise IOError(data.get("error") or f"HTTP {resp.status}")
        return data
