"""groovebox_site.py — GROOVEBOX_R32_SITE_20261110

Your own Groovebox SITE plus an Internet RELAY, alongside the Nearby LAN service.

SHARING (share_config.json in state/)
  folders / files each toggled shared or not; nothing is shared until you tick it.
  Defaults offered: project exports, recordings, samples, published projects (.MCC).

SITE  (stdlib HTTP, threaded, Range streaming)
  /                      your site: name, about text, now playing, shared library, chat box
  /files                 JSON list of shared files (name, size, kind, url)
  /f/<id>                a shared file (Range requests → audio/video seek in any browser/player)
  /chat  GET/POST        public guestbook-style chat (rate-limited, 500 messages kept)
  /notes GET/POST        text-only visitor notes with bounded rolling retention (4–64 MB cap)
  /project/<id>.MCC      download a shared project (request-driven; no inbound file uploads)
                         (data only — never opened automatically)
  /peers                 Grooveboxes this site knows (LAN discovery + relay members)
  Bind to all interfaces; works over LAN, Wi-Fi, ad-hoc/hotspot, Wi-Fi Direct, IPv6, VPN.

RELAY  (for Grooveboxes behind NAT / no port forward)
  A Groovebox with a reachable port can run as RELAY HOST: members connect OUT to it
  (long-poll), so visitors browse   http://relay:port/r/<member-id>/...   and the relay forwards
  each request down the member's open poll and streams the reply back (reverse tunnel).
  RelayMember keeps that outbound connection alive and answers requests from its own site.

PORT FORWARD  (UPnP-IGD)
  upnp_forward(port) asks the router (SSDP discovery + SOAP AddPortMapping) to forward TCP
  <port> to this machine; upnp_remove(port) removes it. Public address shown when the router
  reports it.
"""
from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import os
import queue
import re
import socket
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MEDIA = (".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aiff", ".mp4", ".mkv", ".webm", ".mov", ".png", ".jpg",
         ".jpeg", ".gif", ".mcc", ".pdf", ".txt", ".md", ".seed", ".json")


def _state_dir():
    try:
        import groovebox_paths
        return groovebox_paths.state_dir()
    except Exception:
        d = os.path.join(os.path.expanduser("~"), ".groovebox", "state"); os.makedirs(d, exist_ok=True); return d


def _cfg_path():
    return os.path.join(_state_dir(), "share_config.json")


def _notes_dir():
    path = os.path.join(_state_dir(), "site_notes")
    os.makedirs(path, exist_ok=True)
    return path


def _notes_cap_bytes(cfg=None):
    cfg = cfg or load_cfg()
    try:
        mb = max(4, min(64, int(cfg.get("notes_limit_mb", 16))))
    except Exception:
        mb = 16
    return mb * 1024 * 1024


def _list_notes():
    """Return newest-first site note files; never follows symlinks."""
    root = _notes_dir()
    rows = []
    try:
        with os.scandir(root) as it:
            for ent in it:
                try:
                    if ent.is_file(follow_symlinks=False) and ent.name.endswith(".txt"):
                        st = ent.stat(follow_symlinks=False)
                        rows.append((float(st.st_mtime), ent.path, int(st.st_size)))
                except OSError:
                    continue
    except OSError:
        return []
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows


def _prune_notes(cfg=None):
    """Keep the newest notes within the configured 4–64 MiB rolling cap."""
    cap = _notes_cap_bytes(cfg)
    rows = _list_notes()  # newest first
    used = 0
    for _mtime, path, size in rows:
        used += size
        if used > cap:
            try:
                os.unlink(path)
                used -= size
            except OSError:
                pass


def _store_note(who, content, cfg=None):
    who = " ".join(str(who or "visitor").split())[:48] or "visitor"
    content = str(content or "").replace("\x00", "")
    content = content.strip()
    if not content:
        raise ValueError("note is empty")
    raw = (who + "\n" + content + "\n").encode("utf-8", "replace")
    if len(raw) > 64 * 1024:
        raise ValueError("one note is limited to 64 KiB")
    root = _notes_dir()
    name = "note-%d-%s.txt" % (int(time.time() * 1000), uuid.uuid4().hex)
    path = os.path.join(root, name)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
    except Exception:
        try: os.unlink(path)
        except OSError: pass
        raise
    _prune_notes(cfg)
    return name


DEFAULT_CFG = {"site_name": "My Groovebox", "about": "Seeded music, video and games made with Mathematician's Groovebox.",
               "port": 8765, "folders": {}, "files": {}, "chat": True, "uploads": False, "autostart": False,
               "relay_host": False, "relay_url": "", "member_id": "", "notes_limit_mb": 16}


def load_cfg():
    c = dict(DEFAULT_CFG)
    try:
        with open(_cfg_path(), encoding="utf-8") as f:
            c.update(json.load(f) or {})
    except Exception:
        pass
    # Peer-to-peer file uploads are intentionally unsupported. Old configs may
    # contain uploads=True from earlier releases; never honor that switch.
    c["uploads"] = False
    try:
        c["notes_limit_mb"] = max(4, min(64, int(c.get("notes_limit_mb", 16))))
    except Exception:
        c["notes_limit_mb"] = 16
    if not c.get("member_id"):
        c["member_id"] = uuid.uuid4().hex[:12]
        save_cfg(c)
    return c


def save_cfg(c):
    c = dict(c or {})
    c["uploads"] = False
    try:
        c["notes_limit_mb"] = max(4, min(64, int(c.get("notes_limit_mb", 16))))
    except Exception:
        c["notes_limit_mb"] = 16
    tmp = _cfg_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=1)
    os.replace(tmp, _cfg_path())


def suggested_folders(app=None):
    out = []
    try:
        import groovebox_paths as gp
        pp = getattr(app, "_current_project_path", None) if app is not None else None
        out += [gp.audio_exports_dir(pp), gp.video_exports_dir(pp), gp.recordings_dir(pp), gp.samples_dir(pp),
                gp.global_exports_dir(), gp.projects_dir()]
    except Exception:
        pass
    return [p for p in dict.fromkeys(out) if p]


def _fid(path):
    return hashlib.blake2b(os.path.abspath(path).encode(), digest_size=8).hexdigest()


def _default_export_folders():
    try:
        import groovebox_paths as gp
        return [gp.global_exports_dir()]
    except Exception:
        return []


def _is_sys(p):
    try:
        import groovebox_paths as gp
        return gp.is_system_path(p)
    except Exception:
        return False


def shared_files(cfg=None):
    """[(id, path)] of everything shared: ticked folders (recursive, media only) + ticked files,
    minus files explicitly unticked."""
    cfg = cfg or load_cfg()
    files = {}
    folders = dict(cfg.get("folders") or {})
    for d in _default_export_folders():              # export files: shared unless you untick them
        folders.setdefault(d, True)
    for folder, on in folders.items():
        if not on or not os.path.isdir(folder):
            continue
        for r, ds, fs in os.walk(folder):
            ds[:] = [d for d in ds if not d.startswith(".") and d not in ("cache", "metadata")]
            for f in fs:
                if f.lower().endswith(MEDIA):
                    p = os.path.join(r, f)
                    if not _is_sys(p):
                        files[_fid(p)] = p
    for p, on in (cfg.get("files") or {}).items():
        if on and os.path.isfile(p) and not _is_sys(p):
            files[_fid(p)] = p
        elif not on:
            files.pop(_fid(p), None)
    return sorted(files.items(), key=lambda kv: -os.path.getmtime(kv[1]) if os.path.exists(kv[1]) else 0)


def kind_of(p):
    e = os.path.splitext(p)[1].lower()
    if e in (".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aiff"):
        return "audio"
    if e in (".mp4", ".mkv", ".webm", ".mov"):
        return "video"
    if e in (".png", ".jpg", ".jpeg", ".gif"):
        return "image"
    if e == ".mcc":
        return "project"
    return "file"


# ---------------------------------------------------------------------------
# site server
# ---------------------------------------------------------------------------
class Site:
    def __init__(self, app=None):
        self.app = app
        self.httpd = None
        self.chat = []
        self._chat_ip = {}
        self.relay_members = {}          # member_id -> {"q": Queue of requests, "replies": {rid: Queue}, "seen": t, "name"}
        self.now_playing = ""

    @property
    def cfg(self):
        return load_cfg()

    def urls(self):
        port = self.httpd.server_address[1] if self.httpd else self.cfg["port"]
        ips = []
        try:
            import nearby_groovebox as nb
            ips = nb._local_ipv4()
        except Exception:
            pass
        if not ips:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("10.255.255.255", 1)); ips = [s.getsockname()[0]]; s.close()
            except Exception:
                ips = ["127.0.0.1"]
        return ["http://%s:%d/" % (ip, port) for ip in ips]

    def start(self, port=None):
        if self.httpd is not None:
            return self.urls()
        port = int(port or self.cfg["port"])
        site = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                site._handle(self, "GET")

            def do_HEAD(self):
                site._handle(self, "HEAD")

            def do_POST(self):
                site._handle(self, "POST")

        ThreadingHTTPServer.allow_reuse_address = True
        try:
            self.httpd = ThreadingHTTPServer(("::", port), H)
        except OSError:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", port), H)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="groovebox-site").start()
        return self.urls()

    def stop(self):
        if self.httpd is not None:
            try:
                self.httpd.shutdown(); self.httpd.server_close()
            except Exception:
                pass
        self.httpd = None

    # -- handlers -------------------------------------------------------------
    def _send(self, h, code, body, ctype="text/html; charset=utf-8", extra=None, head=False):
        if isinstance(body, str):
            body = body.encode("utf-8")
        h.send_response(code)
        h.send_header("Content-Type", ctype); h.send_header("Content-Length", str(len(body)))
        h.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            h.send_header(k, v)
        h.end_headers()
        if not head:
            h.wfile.write(body)

    def _handle(self, h, method):
        u = urllib.parse.urlsplit(h.path)
        path = urllib.parse.unquote(u.path)
        try:
            if path.startswith("/r/"):
                return self._relay_forward(h, method, path, u.query)
            if path.startswith("/relay/"):
                return self._relay_api(h, method, path, u.query)
            if path == "/" and method in ("GET", "HEAD"):
                return self._send(h, 200, self._index(), head=method == "HEAD")
            if path == "/files":
                rows = [{"id": i, "name": os.path.basename(p), "size": os.path.getsize(p), "kind": kind_of(p),
                         "url": "/f/" + i} for i, p in shared_files()]
                return self._send(h, 200, json.dumps(rows), "application/json")
            if path.startswith("/f/") or (path.startswith("/project/") and path.lower().endswith(".mcc")):
                fid = path.split("/")[2].split(".")[0]
                return self._file(h, fid, method)
            if path == "/chat":
                return self._chat(h, method)
            if path == "/notes":
                return self._notes(h, method)
            if path == "/inbox":
                return self._send(h, 410, "file uploads are permanently disabled; request a download from the owner's shared library", "text/plain")
            if path == "/peers":
                return self._send(h, 200, json.dumps(self._peers()), "application/json")
            if path == "/info":
                c = self.cfg
                return self._send(h, 200, json.dumps({"name": c["site_name"], "member_id": c["member_id"], "groovebox": True,
                                                      "files": len(shared_files(c)), "now_playing": self.now_playing}), "application/json")
            self._send(h, 404, "not found", "text/plain")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            try:
                self._send(h, 500, "error: %s" % exc, "text/plain")
            except Exception:
                pass

    def _file(self, h, fid, method):
        m = dict(shared_files())
        p = m.get(fid)
        if not p:
            return self._send(h, 404, "not shared", "text/plain")
        size = os.path.getsize(p)
        ctype = mimetypes.guess_type(p)[0] or ("application/json" if p.lower().endswith(".mcc") else "application/octet-stream")
        rng = h.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            start = int(a) if a else max(0, size - int(b))
            end = int(b) if (a and b) else size - 1
            code = 206
        length = max(0, end - start + 1)
        h.send_response(code)
        h.send_header("Content-Type", ctype); h.send_header("Accept-Ranges", "bytes")
        h.send_header("Content-Length", str(length)); h.send_header("Access-Control-Allow-Origin", "*")
        h.send_header("Content-Disposition", 'inline; filename="%s"' % os.path.basename(p).replace('"', ""))
        if code == 206:
            h.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        h.end_headers()
        if method == "HEAD":
            return
        with open(p, "rb") as f:
            f.seek(start); left = length
            while left > 0:
                chunk = f.read(min(256 * 1024, left))
                if not chunk:
                    break
                h.wfile.write(chunk); left -= len(chunk)

    def _chat(self, h, method):
        if not self.cfg.get("chat", True):
            return self._send(h, 403, "chat off", "text/plain")
        if method == "POST":
            n = min(4096, int(h.headers.get("Content-Length") or 0))
            raw = h.rfile.read(n).decode("utf-8", "replace")
            try:
                d = json.loads(raw)
            except Exception:
                d = dict(urllib.parse.parse_qsl(raw))
            ip = h.client_address[0]
            if time.time() - self._chat_ip.get(ip, 0) < 1.5:
                return self._send(h, 429, "slow down", "text/plain")
            self._chat_ip[ip] = time.time()
            msg = {"t": time.time(), "who": str(d.get("who") or "guest")[:32], "text": str(d.get("text") or "")[:500]}
            if msg["text"].strip():
                self.chat.append(msg); del self.chat[:-500]
            if "text/html" in (h.headers.get("Accept") or ""):
                h.send_response(303); h.send_header("Location", "/"); h.send_header("Content-Length", "0"); h.end_headers(); return
            return self._send(h, 200, json.dumps({"ok": True}), "application/json")
        return self._send(h, 200, json.dumps(self.chat[-100:]), "application/json")

    def _notes(self, h, method):
        if method == "GET" or method == "HEAD":
            rows = []
            for mtime, path, size in _list_notes()[:100]:
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        body = f.read(64 * 1024)
                    who, _, text = body.partition("\n")
                    rows.append({"time": mtime, "who": who[:48], "text": text.strip()[:64 * 1024]})
                except OSError:
                    continue
            return self._send(h, 200, json.dumps(rows), "application/json", head=method == "HEAD")
        if method != "POST":
            return self._send(h, 405, "method not allowed", "text/plain", {"Allow": "GET, HEAD, POST"})
        ip = h.client_address[0]
        now = time.time()
        if now - getattr(self, "_notes_ip", {}).get(ip, 0) < 2.0:
            return self._send(h, 429, "please wait before posting another note", "text/plain")
        try:
            n = int(h.headers.get("Content-Length") or 0)
        except Exception:
            n = 0
        if n <= 0 or n > 64 * 1024:
            return self._send(h, 413 if n > 64 * 1024 else 400, "one text note is limited to 64 KiB", "text/plain")
        raw = h.rfile.read(n)
        if len(raw) != n:
            return self._send(h, 400, "incomplete note", "text/plain")
        ctype = (h.headers.get("Content-Type") or "").lower()
        who = h.headers.get("X-Note-Name", "visitor")
        if "application/x-www-form-urlencoded" in ctype:
            form = urllib.parse.parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
            who = (form.get("who") or [who])[0]
            content = (form.get("text") or [""])[0]
        elif "text/plain" in ctype or "application/json" in ctype:
            if "application/json" in ctype:
                try:
                    obj = json.loads(raw.decode("utf-8", "replace"))
                    who, content = obj.get("who", who), obj.get("text", "")
                except Exception:
                    return self._send(h, 400, "invalid note JSON", "text/plain")
            else:
                content = raw.decode("utf-8", "replace")
        else:
            return self._send(h, 415, "notes accept text only", "text/plain")
        try:
            name = _store_note(who, content, self.cfg)
        except ValueError as exc:
            return self._send(h, 400, str(exc), "text/plain")
        except Exception as exc:
            return self._send(h, 500, "could not store note: %s" % exc, "text/plain")
        if not hasattr(self, "_notes_ip"):
            self._notes_ip = {}
        self._notes_ip[ip] = now
        if "text/html" in (h.headers.get("Accept") or ""):
            h.send_response(303); h.send_header("Location", "/"); h.send_header("Content-Length", "0"); h.end_headers(); return
        return self._send(h, 201, json.dumps({"ok": True, "saved": name}), "application/json")

    def _peers(self):
        out = []
        try:
            nb = getattr(self.app, "_nearby_share_service", None)
            for p in (nb.peer_list() if nb is not None else []):
                out.append({"name": p.get("name"), "url": p.get("url") or p.get("base_url"), "via": "lan"})
        except Exception:
            pass
        for mid, m in self.relay_members.items():
            if time.time() - m["seen"] < 60:
                out.append({"name": m.get("name", mid), "url": "/r/%s/" % mid, "via": "relay"})
        return out

    def _index(self):
        c = self.cfg
        e = html.escape
        rows = []
        for i, p in shared_files(c)[:500]:
            k = kind_of(p); name = e(os.path.basename(p)); url = "/f/" + i
            player = ""
            if k == "audio":
                player = '<audio controls preload="none" src="%s"></audio>' % url
            elif k == "video":
                player = '<video controls preload="none" width="360" src="%s"></video>' % url
            elif k == "image":
                player = '<img src="%s" style="max-width:240px">' % url
            rows.append('<div class="f"><a href="%s">%s</a> <span>%s · %.1f MB</span><br>%s</div>' % (
                url, name, k, os.path.getsize(p) / 1e6, player))
        chat = "".join('<p><b>%s</b> %s</p>' % (e(m["who"]), e(m["text"])) for m in self.chat[-40:])
        peers = "".join('<li><a href="%s">%s</a> (%s)</li>' % (e(p["url"] or "#"), e(str(p["name"])), p["via"]) for p in self._peers())
        notes = []
        for _t, npth, _sz in _list_notes()[:30]:
            try:
                with open(npth, "r", encoding="utf-8", errors="replace") as nf:
                    entry = nf.read(64 * 1024)
                who, _, body = entry.partition("\n")
                notes.append('<article><b>%s</b><pre>%s</pre></article>' % (e(who), e(body.strip())))
            except OSError:
                continue
        return """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>%s</title><style>body{background:#05070b;color:#e6edf3;font-family:sans-serif;max-width:980px;margin:auto;padding:16px}
a{color:#7dd3fc}.f{border-bottom:1px solid #1d2a33;padding:8px 0}.f span{color:#8b98a5;font-size:12px}
h1{color:#2ecc71}input,textarea{background:#101820;color:#fff;border:1px solid #31577a}textarea{display:block;width:95%%;min-height:90px}</style></head><body>
<h1>%s</h1><p>%s</p><p><i>%s</i></p><h2>Library (%d)</h2>%s
<h2>Chat</h2>%s<form method=post action=/chat><input name=who placeholder=name size=12> <input name=text placeholder=message size=50> <button>Send</button></form>
<h2>Visitor notes (text only · rolling %d MB limit)</h2>%s
<form method=post action=/notes><input name=who placeholder=name maxlength=48 size=12>
<textarea name=text placeholder="Leave a note" maxlength=60000 required></textarea><button>Post note</button></form>
<h2>Other Grooveboxes</h2><ul>%s</ul></body></html>""" % (
            e(c["site_name"]), e(c["site_name"]), e(c["about"]), ("Now playing: " + e(self.now_playing)) if self.now_playing else "",
            len(rows), "".join(rows) or "<p>Nothing shared yet.</p>", chat if c.get("chat", True) else "<p>Chat is off.</p>",
            int(c.get("notes_limit_mb", 16)), "".join(notes) or "<p>No notes yet.</p>", peers or "<li>none yet</li>")

    # -- relay host -------------------------------------------------------------
    def _relay_api(self, h, method, path, query):
        if not self.cfg.get("relay_host"):
            return self._send(h, 403, "this Groovebox is not a relay host", "text/plain")
        q = dict(urllib.parse.parse_qsl(query))
        mid = re.sub(r"[^\w]", "", q.get("id", ""))[:32]
        if not mid:
            return self._send(h, 400, "id required", "text/plain")
        m = self.relay_members.setdefault(mid, {"q": queue.Queue(), "replies": {}, "seen": 0, "name": mid})
        m["seen"] = time.time(); m["name"] = q.get("name", m["name"])[:48]
        if path == "/relay/poll":
            try:
                req = m["q"].get(timeout=25)
            except queue.Empty:
                return self._send(h, 204, b"", "text/plain")
            return self._send(h, 200, json.dumps(req), "application/json")
        if path == "/relay/reply" and method == "POST":
            rid = q.get("rid", "")
            n = int(h.headers.get("Content-Length") or 0)
            body = h.rfile.read(n)
            rq = m["replies"].get(rid)
            if rq is not None:
                rq.put((int(q.get("code", 200)), q.get("ctype", "application/octet-stream"), body))
            return self._send(h, 200, b"ok", "text/plain")
        return self._send(h, 404, "unknown relay call", "text/plain")

    def _relay_forward(self, h, method, path, query):
        parts = path.split("/", 3)
        mid = parts[2] if len(parts) > 2 else ""
        rest = "/" + (parts[3] if len(parts) > 3 else "")
        # Relay is for browsing/downloading. POST is allowed only for the
        # intentionally text-only chat/notes endpoints; no file transfer API.
        if method not in ("GET", "HEAD", "POST") or (method == "POST" and rest.split("?", 1)[0] not in ("/chat", "/notes")):
            return self._send(h, 403, "relay accepts downloads and text notes only; file uploads are disabled", "text/plain")
        m = self.relay_members.get(mid)
        if m is None or time.time() - m["seen"] > 60:
            return self._send(h, 502, "that Groovebox is not connected to this relay", "text/plain")
        rid = uuid.uuid4().hex
        rq = queue.Queue(); m["replies"][rid] = rq
        body = b""
        if method == "POST":
            body = h.rfile.read(min(8 * 1024 * 1024, int(h.headers.get("Content-Length") or 0)))
        m["q"].put({"rid": rid, "method": method, "path": rest + (("?" + query) if query else ""),
                    "range": h.headers.get("Range", ""), "body": body.decode("latin-1")})
        try:
            code, ctype, data = rq.get(timeout=60)
        except queue.Empty:
            return self._send(h, 504, "relay member did not answer", "text/plain")
        finally:
            m["replies"].pop(rid, None)
        if ctype.startswith("text/html"):
            data = data.replace(b'href="/', ('href="/r/%s/' % mid).encode()).replace(b'src="/', ('src="/r/%s/' % mid).encode()) \
                       .replace(b'action=/', ('action=/r/%s/' % mid).encode())
        return self._send(h, code, data, ctype)


class RelayMember:
    """Keeps an outbound long-poll to a relay host and answers from the local site."""

    def __init__(self, site, relay_url, member_id, name):
        self.site, self.relay = site, relay_url.rstrip("/"),
        self.relay = relay_url.rstrip("/")
        self.mid, self.name = member_id, name
        self.stop_ev = threading.Event()
        self.state = "idle"

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="groovebox-relay-member").start()

    def stop(self):
        self.stop_ev.set()

    def _loop(self):
        base = "%s/relay/poll?id=%s&name=%s" % (self.relay, self.mid, urllib.parse.quote(self.name))
        while not self.stop_ev.is_set():
            try:
                with urllib.request.urlopen(base, timeout=35) as r:
                    self.state = "connected"
                    if r.status == 204:
                        continue
                    req = json.loads(r.read().decode("utf-8"))
                threading.Thread(target=self._answer, args=(req,), daemon=True).start()
            except Exception as exc:
                self.state = "retrying (%s)" % exc.__class__.__name__
                self.stop_ev.wait(5)

    def _answer(self, req):
        port = self.site.httpd.server_address[1] if self.site.httpd else self.site.cfg["port"]
        local = "http://127.0.0.1:%d%s" % (port, req["path"])
        hdr = {"Range": req["range"]} if req.get("range") else {}
        data = req.get("body", "").encode("latin-1") if req.get("method") == "POST" else None
        try:
            with urllib.request.urlopen(urllib.request.Request(local, data=data, headers=hdr, method=req["method"]), timeout=30) as r:
                code, ctype, body = r.status, r.headers.get("Content-Type", "application/octet-stream"), r.read(64 * 1024 * 1024)
        except urllib.error.HTTPError as e:
            code, ctype, body = e.code, "text/plain", e.read()
        except Exception as exc:
            code, ctype, body = 502, "text/plain", str(exc).encode()
        url = "%s/relay/reply?id=%s&rid=%s&code=%d&ctype=%s" % (self.relay, self.mid, req["rid"], code, urllib.parse.quote(ctype))
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=body, method="POST"), timeout=60).read()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# UPnP port forwarding
# ---------------------------------------------------------------------------
def _ssdp_location(timeout=2.0):
    msg = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\n"
           "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n").encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP); s.settimeout(timeout)
    try:
        s.sendto(msg, ("239.255.255.250", 1900))
        while True:
            data, _ = s.recvfrom(4096)
            m = re.search(rb"(?im)^location:\s*(\S+)", data)
            if m:
                return m.group(1).decode()
    except Exception:
        return None
    finally:
        s.close()


def _igd_control(loc):
    xml = urllib.request.urlopen(loc, timeout=3).read().decode("utf-8", "replace")
    for svc in ("WANIPConnection:1", "WANIPConnection:2", "WANPPPConnection:1"):
        m = re.search(r"<serviceType>urn:schemas-upnp-org:service:%s</serviceType>.*?<controlURL>(.*?)</controlURL>" % svc, xml, re.S)
        if m:
            return urllib.parse.urljoin(loc, m.group(1).strip()), "urn:schemas-upnp-org:service:" + svc
    raise RuntimeError("router has no WAN IP service")


def _soap(ctrl, svc, action, args):
    body = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:%s xmlns:u="%s">%s</u:%s></s:Body></s:Envelope>'
            % (action, svc, "".join("<%s>%s</%s>" % (k, html.escape(str(v)), k) for k, v in args), action))
    req = urllib.request.Request(ctrl, data=body.encode(), headers={"Content-Type": 'text/xml; charset="utf-8"',
                                                                    "SOAPAction": '"%s#%s"' % (svc, action)})
    return urllib.request.urlopen(req, timeout=4).read().decode("utf-8", "replace")


def _lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    finally:
        s.close()


def upnp_forward(port, desc="Groovebox site"):
    loc = _ssdp_location()
    if not loc:
        return False, "no UPnP router answered (enable UPnP on the router, or forward TCP %d by hand)" % port
    ctrl, svc = _igd_control(loc)
    _soap(ctrl, svc, "AddPortMapping", [("NewRemoteHost", ""), ("NewExternalPort", port), ("NewProtocol", "TCP"),
                                         ("NewInternalPort", port), ("NewInternalClient", _lan_ip()), ("NewEnabled", 1),
                                         ("NewPortMappingDescription", desc), ("NewLeaseDuration", 0)])
    ext = ""
    try:
        r = _soap(ctrl, svc, "GetExternalIPAddress", [])
        m = re.search(r"<NewExternalIPAddress>(.*?)</NewExternalIPAddress>", r)
        ext = m.group(1) if m else ""
    except Exception:
        pass
    return True, ("forwarded TCP %d → %s:%d" % (port, _lan_ip(), port)) + (" · public: http://%s:%d/" % (ext, port) if ext else "")


def upnp_remove(port):
    loc = _ssdp_location()
    if not loc:
        return False, "no UPnP router"
    ctrl, svc = _igd_control(loc)
    _soap(ctrl, svc, "DeletePortMapping", [("NewRemoteHost", ""), ("NewExternalPort", port), ("NewProtocol", "TCP")])
    return True, "removed TCP %d" % port


def site(app=None):
    s = getattr(app, "_groovebox_site", None) if app is not None else None
    if s is None:
        s = Site(app)
        if app is not None:
            app._groovebox_site = s
    return s
