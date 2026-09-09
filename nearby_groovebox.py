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
CHUNK = 1024 * 1024

PROJECT_EXT = {".mcc", ".mgpr", ".meum", ".mg", ".mgb", ".mgproject", ".mgsynth", ".mgprofile"}
MEDIA_EXT = {".wav", ".flac", ".mp3", ".ogg", ".opus", ".aiff", ".aif", ".caf",
             ".mp4", ".webm", ".avi", ".mov", ".mkv", ".png", ".jpg", ".jpeg",
             ".webp", ".bmp", ".gif", ".tif", ".tiff"}
GAME_EXT = {".zip"}
CODE_EXT = {".py", ".pyi", ".sc", ".sC", ".jl", ".cpp", ".hpp", ".h", ".json", ".txt", ".md"}


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
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
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
        self.direct = DirectLinkManager(self.node_id) if DirectLinkManager is not None else None

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
            self.known_history[str(peer.node_id)]=row
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
                    if u.path != "/api/v1/upload": return self._json(404,{"error":"unknown endpoint"})
                    if not owner.allow_incoming: return self._json(403,{"error":"receiver has Nearby Share incoming files disabled"})
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
                    os.replace(tmp,target); owner.invalidate_catalog()
                    return self._json(201,{"ok":True,"category":category,"name":target.name,"path":str(target),"size":length,"sha256":actual})
                except Exception as e:
                    return self._json(500,{"error":str(e)})

        # Auto-select a nearby free port if another local Groovebox owns the default.
        last = None
        for p in list(range(self.port, min(65535,self.port+12))) + [0]:
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", p), Handler)
                self.httpd.daemon_threads = True
                self.port = int(self.httpd.server_address[1]); break
            except OSError as e: last=e; self.httpd=None
        if self.httpd is None: raise last or OSError("Unable to bind Nearby Share")
        self.http_thread=threading.Thread(target=self.httpd.serve_forever,name="groovebox-nearby-http",daemon=True); self.http_thread.start()
        self.beacon_thread=threading.Thread(target=self._beacon_loop,name="groovebox-nearby-beacon",daemon=True); self.beacon_thread.start()
        self.listen_thread=threading.Thread(target=self._listen_loop,name="groovebox-nearby-listen",daemon=True); self.listen_thread.start()
        if self.direct is not None:
            self.direct_thread=threading.Thread(target=self._direct_scan_loop,name="groovebox-direct-scan",daemon=True); self.direct_thread.start()
        return self.urls()

    def stop(self):
        try: self._flush_history(True)
        except Exception: pass
        self.stop_event.set()
        if self.httpd is not None:
            try: self.httpd.shutdown(); self.httpd.server_close()
            except Exception: pass
            self.httpd=None
        for t in (self.http_thread,self.beacon_thread,self.listen_thread,self.direct_thread):
            if t and t is not threading.current_thread():
                try: t.join(timeout=.7)
                except Exception: pass
        self.http_thread=self.beacon_thread=self.listen_thread=self.direct_thread=None

    def urls(self):
        return [f"http://{ip}:{self.port}/" for ip in _local_ipv4()] or [f"http://127.0.0.1:{self.port}/"]

    def info(self):
        caps=["discover","browse","download","upload","sha256","router-free-direct"]
        return {"magic":DISCOVERY_MAGIC,"api":API_VERSION,"node_id":self.node_id,"name":self.name,
                "port":self.port,"platform":platform.system(),"version":self.version,
                "catalog_id":self._catalog_id,"capabilities":caps,
                "incoming_enabled":bool(self.allow_incoming),
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
        while not self.stop_event.is_set():
            msg=self.info(); msg["ts"]=time.time()
            data=_json_bytes(msg)
            try: s.sendto(data,("255.255.255.255",DISCOVERY_PORT))
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
        s.settimeout(1.0)
        while not self.stop_event.is_set():
            try: raw,addr=s.recvfrom(65507)
            except socket.timeout: continue
            except OSError: break
            try:
                d=json.loads(raw.decode("utf-8","replace"))
                if d.get("magic")!=DISCOVERY_MAGIC or d.get("node_id")==self.node_id: continue
                port=int(d.get("port",DEFAULT_HTTP_PORT)); ip=addr[0]
                peer=Peer(str(d.get("node_id","")),str(d.get("name","Groovebox")),ip,port,
                          f"http://{ip}:{port}",str(d.get("platform","")),str(d.get("version","")),time.time(),str(d.get("catalog_id","")))
                with self.peers_lock: self.peers[peer.node_id]=peer
                self._remember_peer(peer)
            except Exception: continue
        try:s.close()
        except Exception:pass


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
        os.replace(tmp,target); self.invalidate_catalog(); return str(target)

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
        conn.putheader("X-Groovebox-SHA256",digest); conn.putheader("X-Groovebox-Filename",p.name); conn.endheaders()
        done=0; total=p.stat().st_size
        with p.open("rb") as f:
            for chunk in iter(lambda:f.read(CHUNK),b""):
                conn.send(chunk); done+=len(chunk)
                if progress: progress(done,total,"upload")
        resp=conn.getresponse(); body=resp.read(); conn.close()
        data=json.loads(body.decode("utf-8","replace") or "{}")
        if resp.status not in (200,201): raise IOError(data.get("error") or f"HTTP {resp.status}")
        return data
