"""GOAVA Radio identity, LAN web radio, and peer discovery.

Radio identity/usage is deliberately outside Program/Composition/Artifact identity.
The HTTP stream is 192 kbps MP3. It cycles deterministic local audio candidates
and synthesizes a short bleep when no suitable media is available.
"""
from __future__ import annotations
import html, json, os, shutil, socket, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_HTTP_PORT = 8780
DISCOVERY_PORT = 37881
DISCOVERY_MAGIC = "MGB_GOAVA_RADIO_V1"
AUDIO_EXTS = {".wav", ".flac", ".mp3", ".ogg", ".opus", ".aiff", ".aif", ".m4a", ".aac"}


def _base_dir() -> Path:
    try:
        import groovebox_paths
        base = Path(groovebox_paths.base_dir())
    except Exception:
        base = Path.home() / ".mathematicians_groovebox"
    base.mkdir(parents=True, exist_ok=True)
    return base


def identity_path() -> Path:
    return _base_dir() / "radio_identity.json"


def load_identity() -> Dict[str, str]:
    default_logo = str(Path(__file__).resolve().parent / "assets" / "goava_radio_brand.png")
    data = {"name": "GOAVA Radio", "logo": default_logo}
    try:
        raw = json.loads(identity_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            if str(raw.get("name", "")).strip(): data["name"] = str(raw["name"]).strip()[:96]
            if str(raw.get("logo", "")).strip(): data["logo"] = str(raw["logo"]).strip()
    except Exception:
        pass
    return data


def save_identity(name: str, logo: str = "") -> Dict[str, str]:
    data = load_identity()
    if str(name).strip(): data["name"] = str(name).strip()[:96]
    if str(logo).strip():
        src = os.path.abspath(os.path.expanduser(str(logo).strip()))
        if os.path.isfile(src):
            ext = Path(src).suffix.lower() or ".png"
            dst = _base_dir() / ("radio_logo" + ext)
            try:
                if os.path.abspath(src) != os.path.abspath(str(dst)):
                    shutil.copy2(src, dst)
                data["logo"] = str(dst)
            except Exception:
                data["logo"] = src
    identity_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def local_ipv4() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _candidate_audio(roots: List[str]) -> List[str]:
    out = []
    for root in roots:
        if not root or not os.path.isdir(root): continue
        for dp, _dn, files in os.walk(root):
            for fn in files:
                p = os.path.join(dp, fn)
                if Path(fn).suffix.lower() in AUDIO_EXTS:
                    out.append(p)
            if len(out) >= 128: break
    return sorted(set(out))


class RadioStationService:
    def __init__(self, roots: Optional[List[str]] = None, port: int = DEFAULT_HTTP_PORT):
        self.roots = [str(x) for x in (roots or []) if x]
        self.port = int(port)
        self.httpd = None
        self._threads: List[threading.Thread] = []
        self._stop = threading.Event()
        self.peers: Dict[str, Dict[str, object]] = {}

    @property
    def identity(self): return load_identity()

    @property
    def url(self): return f"http://{local_ipv4()}:{self.port}/"

    def start(self):
        if self.httpd: return self.url
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): return
            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/stream.mp3": return self._stream()
                if path == "/api/peers": return self._json(owner.peer_list())
                if path == "/logo": return self._logo()
                return self._page()
            def _json(self, obj):
                b = json.dumps(obj).encode(); self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
            def _logo(self):
                p = owner.identity.get("logo", "")
                if p and os.path.isfile(p):
                    b = Path(p).read_bytes(); self.send_response(200); self.send_header("Content-Type","image/png"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
                self.send_error(404)
            def _page(self):
                ident = owner.identity; peers = owner.peer_list()
                cards = "".join(f'<a class="peer" href="{html.escape(str(p.get("url","#")))}">{html.escape(str(p.get("name","Radio")))}</a>' for p in peers)
                body = f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(ident['name'])}</title><style>body{{background:#071019;color:#eaf8ff;font-family:system-ui;margin:0;padding:24px}}.card{{max-width:760px;margin:auto;background:#0d1b28;border:1px solid #315d73;border-radius:22px;padding:22px;box-shadow:0 12px 38px #0008}}img{{max-width:100%;max-height:180px;border-radius:16px}}h1{{color:#f1ce68}}audio{{width:100%}}.peer{{display:block;color:#9fe7f5;background:#102838;border-radius:12px;padding:10px;margin:7px 0;text-decoration:none}}</style></head><body><div class="card"><img src="/logo"><h1>{html.escape(ident['name'])}</h1><p>Mathematician's Groovebox · 192 kbps local GOAVA Radio</p><audio controls autoplay src="/stream.mp3"></audio><h3>Nearby Groovebox radios</h3>{cards or '<p>No peers seen yet.</p>'}</div></body></html>'''.encode()
                self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
            def _stream(self):
                self.send_response(200); self.send_header("Content-Type","audio/mpeg"); self.send_header("Cache-Control","no-cache"); self.send_header("Connection","close"); self.end_headers()
                ffmpeg = shutil.which("ffmpeg")
                if not ffmpeg: return
                files = _candidate_audio(owner.roots)
                idx = 0
                try:
                    while not owner._stop.is_set():
                        if files:
                            src = files[idx % len(files)]; idx += 1
                            cmd = [ffmpeg,"-hide_banner","-loglevel","error","-re","-i",src,"-vn","-ac", "2","-ar","44100","-b:a","192k","-f","mp3","pipe:1"]
                        else:
                            hz = 432 + (idx % 5) * 27; idx += 1
                            cmd = [ffmpeg,"-hide_banner","-loglevel","error","-re","-f","lavfi","-i",f"sine=frequency={hz}:sample_rate=44100:duration=1.25","-af","volume=0.10","-ac","2","-b:a","192k","-f","mp3","pipe:1"]
                        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                        while proc.stdout and not owner._stop.is_set():
                            chunk = proc.stdout.read(16384)
                            if not chunk: break
                            self.wfile.write(chunk); self.wfile.flush()
                        try: proc.terminate()
                        except Exception: pass
                        if files: time.sleep(0.08)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
        self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        t = threading.Thread(target=self.httpd.serve_forever, daemon=True); t.start(); self._threads.append(t)
        for target in (self._announce_loop, self._listen_loop):
            t = threading.Thread(target=target, daemon=True); t.start(); self._threads.append(t)
        return self.url

    def stop(self):
        self._stop.set()
        if self.httpd:
            try: self.httpd.shutdown(); self.httpd.server_close()
            except Exception: pass
        self.httpd = None

    def _announce_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while not self._stop.wait(2.0):
            ident = self.identity
            msg = json.dumps({"magic":DISCOVERY_MAGIC,"name":ident["name"],"url":self.url,"ts":time.time()}).encode()
            try: s.sendto(msg, ("255.255.255.255", DISCOVERY_PORT))
            except Exception: pass
        s.close()

    def _listen_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.bind(("", DISCOVERY_PORT))
        except Exception: return
        s.settimeout(1.0)
        while not self._stop.is_set():
            try:
                raw, addr = s.recvfrom(65535); data = json.loads(raw.decode("utf-8", "replace"))
                if data.get("magic") != DISCOVERY_MAGIC: continue
                if addr[0] == local_ipv4() and int(str(data.get("url","")).split(":")[-1].rstrip("/") or -1) == self.port: continue
                data["ip"] = addr[0]; data["seen"] = time.time(); self.peers[addr[0]] = data
            except socket.timeout: pass
            except Exception: pass
        s.close()

    def peer_list(self):
        now=time.time(); self.peers={k:v for k,v in self.peers.items() if now-float(v.get("seen",0))<8.0}
        return sorted(self.peers.values(), key=lambda x: str(x.get("name","")))
