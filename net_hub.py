"""net_hub.py — the Groovebox network: site pages (radio, blog, hosted files with embed players, comments, messages,
ratings), trust levels, host / repeater networks and the nearby auto-radio. One small SQLite database holds it all.

TRUST LEVELS (per Groovebox member id or IP)       what they may do on YOUR site / network
  housemate   everything incl. auto-play radio, host-to-host sync (if they also hold the network key)
  trusted     comments, messages, ratings, downloads, auto-play radio popups
  friend      comments, messages, ratings, downloads, radio popups
  public      read, listen, download shared files, comment (rate-limited)
  blacklist1  read only (no comments, messages, ratings; no popups from them)
  blacklist2  no downloads or streams either (pages only); hidden from your radio list
  blacklist3  blocked entirely (403), never shown, never synced
SITE PAGES (added to your Groovebox site)
  /radio      name, logo, now playing, the running order, live player, comments, message the host, rating
  /blog       posts (simple editor in the app: title, text with **bold**, _italic_, # headings, links, [[file:ID]] embeds)
  /hosted     hosted files with embed players (audio, video, images, .MCC projects as downloads), per-file comments
  /embed/<id> a bare player page you can put in an <iframe>
  /api/…      JSON: comments, rate, message, posts, hosted, network index / notify / sync
NETWORK (host / repeater)
  A network has a NAME and a KEY. Hosts are PRIMARY (always-on) or GIG (comes and goes). Every host keeps the same
  database rows (posts, hosted-file manifest, comments, notices, member index) and pulls changes from the other hosts
  it knows (/api/net/sync, HMAC-signed with the key, last-writer-wins by time + origin). Hosted files are fetched from
  any host that has them (SHA-256 checked). Members subscribe to one host and fail over to the next by priority, so
  the network stays online as one place. Members announce their shared catalogue (/api/net/announce) and long-poll
  notifications (/api/net/notify).
BOOT MODE   compat setting `network_mode` = off | member | host (and `network_role` = primary | gig): at start-up the
  site, relay, radio and sync run on their own; `run_groovebox.py --network-host` runs them headless.
"""
from __future__ import annotations

import hashlib, hmac, html, json, os, queue, re, shutil, sqlite3, threading, time, urllib.parse, urllib.request, uuid

LEVELS = ("housemate", "trusted", "friend", "public", "blacklist1", "blacklist2", "blacklist3")
RANK = {k: i for i, k in enumerate(LEVELS)}
_LOCK = threading.RLock()
_DB = None
_WAITERS = []
_RL = {}


def _dir():
    try:
        import groovebox_paths
        d = os.path.join(groovebox_paths.base_dir(), "network")
    except Exception:
        d = os.path.join(os.path.expanduser("~"), ".local", "share", "groovebox", "network")
    os.makedirs(d, exist_ok=True)
    return d


def hosted_dir():
    d = os.path.join(_dir(), "hosted"); os.makedirs(d, exist_ok=True); return d


def db():
    global _DB
    with _LOCK:
        if _DB is None:
            _DB = sqlite3.connect(os.path.join(_dir(), "groovebox_net.sqlite"), check_same_thread=False)
            _DB.executescript("""
            create table if not exists rows(uid text primary key, kind text, ts real, origin text, deleted int default 0, data text);
            create index if not exists rows_kind on rows(kind, ts);
            create table if not exists trust(who text primary key, level text, note text, ts real);
            create table if not exists ratings(item text, who text, stars int, ts real, primary key(item, who));
            """)
            _DB.commit()
        return _DB


def cfg():
    try:
        import compat_settings as cs
        s = cs.load()
    except Exception:
        s = {}
    return {"mode": s.get("network_mode", "off"), "role": s.get("network_role", "primary"), "name": s.get("network_name", ""),
            "key": s.get("network_key", ""), "hosts": list(s.get("network_hosts", []) or []), "radio_autoplay": s.get("radio_autoplay", "trusted"),
            "radio_popups": bool(s.get("radio_popups", True)), "origin": s.get("network_origin") or _origin()}


def _origin():
    p = os.path.join(_dir(), "origin.txt")
    if not os.path.isfile(p):
        open(p, "w").write(uuid.uuid4().hex[:12])
    return open(p).read().strip()


# ------------------------------------------------------------------ rows (replicated)
def put(kind, data, uid=None, deleted=False, ts=None, origin=None):
    if origin is None and kind in ("blog", "hosted", "radio_show"):   # R101: local publishing needs owner / member
        try:
            __import__("accounts").require("publish", kind)
        except ImportError:
            pass
    uid = uid or uuid.uuid4().hex
    with _LOCK:
        db().execute("insert or replace into rows(uid, kind, ts, origin, deleted, data) values(?,?,?,?,?,?)",
                     (uid, kind, float(ts or time.time()), origin or cfg()["origin"], 1 if deleted else 0, json.dumps(data)))
        db().commit()
    _wake({"kind": kind, "uid": uid})
    return uid


def rows(kind, limit=200, since=0.0, include_deleted=False):
    with _LOCK:
        cur = db().execute("select uid, ts, origin, deleted, data from rows where kind=? and ts>? %s order by ts desc limit ?"
                           % ("" if include_deleted else "and deleted=0"), (kind, float(since), int(limit)))
        return [dict(json.loads(d), uid=u, ts=t, origin=o, deleted=bool(x)) for u, t, o, x, d in cur.fetchall()]


def get(uid):
    with _LOCK:
        r = db().execute("select kind, ts, data, deleted from rows where uid=?", (uid,)).fetchone()
    return (dict(json.loads(r[2]), uid=uid, ts=r[1], row_kind=r[0], deleted=bool(r[3])) if r else None)


# ------------------------------------------------------------------ trust
def set_trust(who, level, note=""):
    if level not in LEVELS: raise ValueError(level)
    with _LOCK:
        db().execute("insert or replace into trust(who, level, note, ts) values(?,?,?,?)", (str(who), level, note, time.time())); db().commit()


def trust(who):
    if not who: return "public"
    with _LOCK:
        r = db().execute("select level from trust where who=?", (str(who),)).fetchone()
    return r[0] if r else "public"


def trust_list():
    with _LOCK:
        return [dict(who=a, level=b, note=c, ts=d) for a, b, c, d in db().execute("select who, level, note, ts from trust order by level, who")]


def allowed(level, action):
    r = RANK.get(level, 3)
    if r >= RANK["blacklist3"]: return False
    if action in ("comment", "message", "rate"): return r <= RANK["public"]
    if action in ("download", "stream"): return r <= RANK["blacklist1"]
    if action == "sync": return r <= RANK["housemate"]
    if action == "autoplay": return r <= RANK["trusted"]
    if action == "popup": return r <= RANK["public"]
    return r <= RANK["blacklist2"]       # read pages


def _rate_ok(who, n=12, per=60.0):
    now = time.time(); h = [t for t in _RL.get(who, []) if now - t < per]
    if len(h) >= n: return False
    _RL[who] = h + [now]; return True


# ------------------------------------------------------------------ ratings
def rate(item, who, stars):
    stars = max(1, min(5, int(stars)))
    with _LOCK:
        db().execute("insert or replace into ratings(item, who, stars, ts) values(?,?,?,?)", (str(item), str(who), stars, time.time())); db().commit()


def rating(item):
    with _LOCK:
        r = db().execute("select avg(stars), count(*) from ratings where item=?", (str(item),)).fetchone()
    return {"avg": round(r[0], 2) if r[0] else 0.0, "count": int(r[1] or 0)}


# ------------------------------------------------------------------ notifications (long-poll)
def _wake(ev):
    for q in list(_WAITERS):
        try: q.put_nowait(ev)
        except Exception: pass


def notify_all(text, kind="notice"):
    return put("notice", {"text": str(text)[:500], "kind": kind})


# ------------------------------------------------------------------ hosted files
KIND = {".wav": "audio", ".flac": "audio", ".mp3": "audio", ".ogg": "audio", ".opus": "audio", ".m4a": "audio",
        ".mp4": "video", ".webm": "video", ".mov": "video", ".mkv": "video", ".png": "image", ".jpg": "image",
        ".jpeg": "image", ".gif": "image", ".mcc": "project", ".obj": "3d", ".json": "data", ".txt": "text", ".md": "text"}


def host_file(path, title="", note=""):
    """Copy a file into the hosted folder (content-addressed) and publish it on the site (replicated manifest)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    sha = h.hexdigest(); ext = os.path.splitext(path)[1].lower()
    dst = os.path.join(hosted_dir(), sha + ext)
    if not os.path.isfile(dst): shutil.copy2(path, dst)
    return put("hosted", {"sha": sha, "ext": ext, "name": os.path.basename(path), "title": title or os.path.basename(path),
                          "note": note, "file_kind": KIND.get(ext, "file"), "size": os.path.getsize(dst)})


def hosted_path(item):
    p = os.path.join(hosted_dir(), item["sha"] + item.get("ext", ""))
    return p if os.path.isfile(p) else None


# ------------------------------------------------------------------ markup (blog)
def render_text(t):
    t = html.escape(str(t))
    t = re.sub(r"^### (.+)$", r"<h4>\1</h4>", t, flags=re.M); t = re.sub(r"^## (.+)$", r"<h3>\1</h3>", t, flags=re.M)
    t = re.sub(r"^# (.+)$", r"<h2>\1</h2>", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t); t = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\[\[file:([0-9a-f]{8,32})\]\]", lambda m: embed_html(m.group(1)), t)
    return "<p>" + t.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"


def embed_html(uid):
    it = get(uid)
    if not it or it.get("deleted"): return "<em>(missing file)</em>"
    return _player(it)


def _player(it):
    src = "/hostedfile/%s" % it["uid"]
    k = KIND.get(it.get("ext", ""), "file")
    t = html.escape(it.get("title") or it.get("name") or "")
    if k == "audio": return '<figure><figcaption>%s</figcaption><audio controls preload="none" src="%s"></audio></figure>' % (t, src)
    if k == "video": return '<figure><figcaption>%s</figcaption><video controls preload="metadata" src="%s"></video></figure>' % (t, src)
    if k == "image": return '<figure><img loading="lazy" src="%s" alt="%s"><figcaption>%s</figcaption></figure>' % (src, t, t)
    return '<p>📦 <a href="%s" download>%s</a> (%d KB)</p>' % (src, t, int(it.get("size", 0)) // 1024)


CSS = ("body{background:#071019;color:#eaf8ff;font-family:system-ui,Arial;margin:0}main{max-width:900px;margin:auto;padding:18px}"
       "nav a{color:#f1ce68;margin-right:16px;text-decoration:none;font-weight:700}h1{color:#f1ce68}.card{background:#0d1b28;"
       "border:1px solid #315d73;border-radius:16px;padding:16px;margin:12px 0}audio,video,img{width:100%;border-radius:10px}"
       "textarea,input{width:100%;background:#091b2a;color:#e6f5ff;border:1px solid #35627d;border-radius:8px;padding:6px}"
       "button{background:#12344b;color:#e8faff;border:1px solid #39768e;border-radius:8px;padding:6px 14px}.c{color:#9fc9dc;font-size:90%}")


def page(title, body, site_name="Groovebox"):
    return ("<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s · %s</title><style>%s</style></head><body><main><nav><a href='/'>🏠 %s</a><a href='/radio'>📻 Radio</a>"
            "<a href='/blog'>📝 Blog</a><a href='/hosted'>📦 Files</a></nav>%s</main></body></html>"
            % (html.escape(title), html.escape(site_name), CSS, html.escape(site_name), body))


def comments_html(item):
    cs = [c for c in rows("comment", 500) if c.get("item") == item][:200]
    lst = "".join("<div class=c><b>%s</b> · %s<br>%s</div>" % (html.escape(c.get("author", "?")[:40]), time.strftime("%Y-%m-%d %H:%M", time.localtime(c["ts"])),
                                                              html.escape(c.get("text", ""))[:2000]) for c in reversed(cs))
    r = rating(item)
    form = ("<form method=post action='/api/comment'><input type=hidden name=item value='%s'><input name=author placeholder='name'>"
            "<textarea name=text rows=3 placeholder='comment'></textarea><button>Comment</button></form>"
            "<form method=post action='/api/rate'><input type=hidden name=item value='%s'>%s</form>"
            % (html.escape(item), html.escape(item), "".join("<button name=stars value=%d>%s</button>" % (i, "★" * i) for i in range(1, 6))))
    return "<div class=card><h3>Comments · rating %.1f★ (%d)</h3>%s%s</div>" % (r["avg"], r["count"], lst or "<p class=c>No comments yet.</p>", form)


# ------------------------------------------------------------------ site hook
def _who(h):
    mid = h.headers.get("X-Groovebox-Member") or ""
    ip = (h.client_address[0] if h.client_address else "") or ""
    lv = min((trust(mid), trust(ip)), key=lambda l: -RANK.get(l, 3)) if mid else trust(ip)
    return (mid or ip), lv


def _form(h):
    n = min(int(h.headers.get("Content-Length") or 0), 1 << 20)
    raw = h.rfile.read(n).decode("utf-8", "replace") if n else ""
    if (h.headers.get("Content-Type") or "").startswith("application/json"):
        try: return json.loads(raw or "{}")
        except Exception: return {}
    return dict(urllib.parse.parse_qsl(raw))


def handle(site, h, method, path, query):
    """Called first by the site. Returns True when it answered."""
    who, lv = _who(h)
    if lv == "blacklist3":
        site._send(h, 403, "blocked", "text/plain"); return True
    name = (getattr(site, "cfg", {}) or {}).get("site_name", "Groovebox")
    q = dict(urllib.parse.parse_qsl(query or ""))
    if path == "/radio":
        try:
            import radio_station as rs
            ident = rs.load_identity()
        except Exception:
            ident = {"name": "Groovebox Radio"}
        st = radio_status()
        order = "".join("<li>%s</li>" % html.escape(os.path.basename(x)) for x in st.get("order", [])[:64])
        body = ("<div class=card><img src='%slogo' style='max-height:160px;width:auto' onerror=\"this.style.display='none'\"><h1>%s</h1>"
                "<p>%s</p>%s<h3>Running order</h3><ol>%s</ol></div>"
                % (st.get("url", ""), html.escape(ident.get("name", "Groovebox Radio")), html.escape(st.get("now", "")),
                   ("<audio controls autoplay src='%sstream.mp3'></audio>" % st["url"]) if st.get("on_air") and allowed(lv, "stream") else "<p>Off air.</p>", order))
        body += ("<div class=card><h3>Message the host</h3><form method=post action='/api/message'><input name=author placeholder='name'>"
                 "<textarea name=text rows=3></textarea><button>Send</button></form></div>") + comments_html("radio")
        site._send(h, 200, page("Radio", body, name)); return True
    if path == "/blog":
        posts = rows("post", 50)
        body = "<h1>📝 Blog</h1>" + "".join("<div class=card><h2>%s</h2><p class=c>%s</p>%s<p><a href='/blog/%s'>comments</a></p></div>" % (
            html.escape(p.get("title", "")), time.strftime("%Y-%m-%d", time.localtime(p["ts"])), render_text(p.get("text", ""))[:20000], p["uid"]) for p in posts)
        site._send(h, 200, page("Blog", body or "<p>No posts yet.</p>", name)); return True
    if path.startswith("/blog/"):
        p = get(path.split("/")[2])
        if not p or p.get("row_kind") != "post" or p.get("deleted"): site._send(h, 404, "no such post", "text/plain"); return True
        site._send(h, 200, page(p.get("title", ""), "<div class=card><h1>%s</h1>%s</div>%s" % (html.escape(p.get("title", "")), render_text(p.get("text", "")), comments_html(p["uid"])), name)); return True
    if path == "/hosted":
        items = rows("hosted", 500)
        body = "<h1>📦 Files</h1>" + "".join("<div class=card>%s<p class=c>%s · %.1f★ · <a href='/hosted/%s'>page</a> · embed: <code>&lt;iframe src=\"/embed/%s\"&gt;</code></p></div>"
                                            % (_player(it), html.escape(it.get("note", "")), rating(it["uid"])["avg"], it["uid"], it["uid"]) for it in items)
        site._send(h, 200, page("Files", body, name)); return True
    if path.startswith("/hosted/"):
        it = get(path.split("/")[2])
        if not it or it.get("deleted"): site._send(h, 404, "no such file", "text/plain"); return True
        site._send(h, 200, page(it.get("title", ""), "<div class=card>%s<p>%s</p></div>%s" % (_player(it), html.escape(it.get("note", "")), comments_html(it["uid"])), name)); return True
    if path.startswith("/embed/"):
        it = get(path.split("/")[2])
        body = _player(it) if it else "missing"
        site._send(h, 200, "<!doctype html><meta charset=utf-8><style>body{margin:0;background:#000;color:#fff}audio,video,img{width:100%%}</style>%s" % body); return True
    if path.startswith("/hostedfile/"):
        if not allowed(lv, "download"): site._send(h, 403, "not allowed", "text/plain"); return True
        it = get(path.split("/")[2]); p = hosted_path(it) if it else None
        if not p: site._send(h, 404, "missing", "text/plain"); return True
        return _serve_range(site, h, p, method)
    if path == "/api/comment" and method == "POST":
        f = _form(h)
        if not allowed(lv, "comment") or not _rate_ok(who): site._send(h, 429 if allowed(lv, "comment") else 403, "not now", "text/plain"); return True
        put("comment", {"item": str(f.get("item", ""))[:64], "author": str(f.get("author", "") or who)[:40], "text": str(f.get("text", ""))[:2000], "who": who})
        _back(site, h); return True
    if path == "/api/rate" and method == "POST":
        f = _form(h)
        if allowed(lv, "rate"): rate(str(f.get("item", ""))[:64], who, f.get("stars", 5))
        _back(site, h); return True
    if path == "/api/message" and method == "POST":
        f = _form(h)
        if allowed(lv, "message") and _rate_ok(who, 6):
            put("message", {"author": str(f.get("author", "") or who)[:40], "text": str(f.get("text", ""))[:2000], "who": who, "level": lv})
            try: __import__("notify_center").notify(_APP.get("app"), "📨 message from %s" % str(f.get("author") or who)[:30], "info")
            except Exception: pass
        _back(site, h); return True
    if path == "/api/posts":
        site._send(h, 200, json.dumps(rows("post", 100)), "application/json"); return True
    if path == "/api/hosted":
        site._send(h, 200, json.dumps(rows("hosted", 500)), "application/json"); return True
    if path == "/api/rating":
        site._send(h, 200, json.dumps(rating(q.get("item", ""))), "application/json"); return True
    if path.startswith("/api/net/"):
        return _net_api(site, h, method, path, q, who, lv)
    return False


def _back(site, h):
    ref = h.headers.get("Referer") or "/"
    site._send(h, 303, "", "text/plain", extra={"Location": ref})


def _serve_range(site, h, p, method):
    import mimetypes
    size = os.path.getsize(p); ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
    rng = h.headers.get("Range"); start, end = 0, size - 1
    if rng and rng.startswith("bytes="):
        a, _, b = rng[6:].partition("-")
        start = int(a or 0); end = int(b) if b else size - 1
    end = min(end, size - 1); n = max(0, end - start + 1)
    h.send_response(206 if rng else 200)
    h.send_header("Content-Type", ctype); h.send_header("Accept-Ranges", "bytes"); h.send_header("Content-Length", str(n))
    if rng: h.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
    h.end_headers()
    if method != "HEAD":
        with open(p, "rb") as f:
            f.seek(start); left = n
            while left > 0:
                c = f.read(min(1 << 16, left))
                if not c: break
                h.wfile.write(c); left -= len(c)
    return True


# ------------------------------------------------------------------ network API (index, notify, sync)
def _sig(body, key):
    return hmac.new(str(key).encode(), body, hashlib.sha256).hexdigest()


def _net_api(site, h, method, path, q, who, lv):
    c = cfg()
    if path == "/api/net/info":
        site._send(h, 200, json.dumps({"network": c["name"], "role": c["role"], "origin": c["origin"], "mode": c["mode"]}), "application/json"); return True
    if path == "/api/net/announce" and method == "POST":
        f = _form(h)
        if allowed(lv, "comment"):
            put("member", {"name": str(f.get("name", ""))[:48], "url": str(f.get("url", ""))[:200], "files": list(f.get("files", []))[:500], "who": who},
                uid="member:" + hashlib.sha1(str(who).encode()).hexdigest()[:16])
        site._send(h, 200, "ok", "text/plain"); return True
    if path == "/api/net/index":
        site._send(h, 200, json.dumps({"members": rows("member", 500), "hosted": rows("hosted", 500), "posts": rows("post", 100)}), "application/json"); return True
    if path == "/api/net/notify":
        since = float(q.get("since", "0") or 0)
        got = rows("notice", 50, since=since) + [r for r in rows("post", 20, since=since)] + [r for r in rows("hosted", 20, since=since)]
        if not got:
            qq = queue.Queue(); _WAITERS.append(qq)
            try: qq.get(timeout=25)
            except queue.Empty: pass
            finally: _WAITERS.remove(qq)
            got = rows("notice", 50, since=since) + rows("post", 20, since=since) + rows("hosted", 20, since=since)
        site._send(h, 200, json.dumps(sorted(got, key=lambda r: r["ts"])), "application/json"); return True
    if path == "/api/net/sync":
        body = json.dumps({k: rows(k, 2000, since=float(q.get("since", "0") or 0), include_deleted=True)
                           for k in ("post", "hosted", "comment", "notice", "member")}).encode()
        if not c["key"] or not hmac.compare_digest(q.get("sig", ""), _sig(("%s|%s" % (q.get("since", "0"), q.get("net", ""))).encode(), c["key"])) or q.get("net") != c["name"]:
            site._send(h, 403, "wrong network key", "text/plain"); return True
        site._send(h, 200, body, "application/json", extra={"X-Groovebox-Sig": _sig(body, c["key"])}); return True
    site._send(h, 404, "unknown network call", "text/plain"); return True


def sync_from(host_url):
    """Pull rows (last writer wins) and missing hosted files from another host of the same network."""
    c = cfg(); since = float(_state().get("since:" + host_url, 0.0))
    qs = urllib.parse.urlencode({"since": since, "net": c["name"], "sig": _sig(("%s|%s" % (since, c["name"])).encode(), c["key"])})
    with urllib.request.urlopen(host_url.rstrip("/") + "/api/net/sync?" + qs, timeout=20) as r:
        body = r.read()
        if not hmac.compare_digest(r.headers.get("X-Groovebox-Sig", ""), _sig(body, c["key"])):
            raise RuntimeError("signature mismatch")
    data = json.loads(body); newest = since; n = 0
    for kind, lst in data.items():
        for row in lst:
            cur = get(row["uid"])
            if cur is None or (row["ts"], row.get("origin", "")) > (cur["ts"], cur.get("origin", "")):
                d = {k: v for k, v in row.items() if k not in ("uid", "ts", "origin", "deleted")}
                put(kind, d, uid=row["uid"], deleted=row.get("deleted"), ts=row["ts"], origin=row.get("origin")); n += 1
                if kind == "hosted" and not row.get("deleted") and not hosted_path(row):
                    _fetch_file(host_url, row)
            newest = max(newest, float(row["ts"]))
    st = _state(); st["since:" + host_url] = newest; _save_state(st)
    return n


def _fetch_file(host_url, row):
    dst = os.path.join(hosted_dir(), row["sha"] + row.get("ext", "")); tmp = dst + ".part"; h = hashlib.sha256()
    with urllib.request.urlopen(host_url.rstrip("/") + "/hostedfile/" + row["uid"], timeout=60) as r, open(tmp, "wb") as f:
        for c in iter(lambda: r.read(1 << 16), b""): h.update(c); f.write(c)
    if h.hexdigest() == row["sha"]: os.replace(tmp, dst)
    else: os.remove(tmp)


def _state():
    try: return __import__("safe_io").load_json(os.path.join(_dir(), "state.json"))
    except Exception: return {}


def _save_state(s):
    __import__("safe_io").atomic_write_json(os.path.join(_dir(), "state.json"), s)


# ------------------------------------------------------------------ radio (broadcast + nearby auto-radio)
_RADIO = {"svc": None, "order": [], "now": ""}
_APP = {}


def radio_status():
    s = _RADIO["svc"]
    return {"on_air": s is not None and s.httpd is not None, "url": s.url if s is not None else "", "order": list(_RADIO["order"]), "now": _RADIO["now"]}


def radio_start(order):
    """Broadcast the running order (files in order) on the LAN with the radio name and logo."""
    import radio_station as rs
    d = os.path.join(_dir(), "radio_order"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for i, p in enumerate(order):
        try: os.symlink(os.path.abspath(p), os.path.join(d, "%04d-%s" % (i, os.path.basename(p))))
        except Exception: shutil.copy2(p, os.path.join(d, "%04d-%s" % (i, os.path.basename(p))))
    radio_stop()
    svc = rs.RadioStationService(roots=[d]); svc.start(); _RADIO.update(svc=svc, order=list(order), now=os.path.basename(order[0]) if order else "")
    try:   # R101 radio show archive: the running order is recorded; radio_stop() renders and hosts the show
        ident = rs.load_identity()
        _RADIO["show"] = put("radio_show", {"name": ident.get("name", "Groovebox Radio"), "started": time.time(),
                                             "order": [os.path.basename(p) for p in order][:500], "hosted": ""})
        _RADIO["show_files"] = [os.path.abspath(p) for p in order]
    except Exception:
        _RADIO["show"] = None
    notify_all("📻 on air: %s" % rs.load_identity().get("name", "Groovebox Radio"), "radio")
    return svc.url


def radio_stop():
    s = _RADIO.get("svc")
    if s is not None:
        try: s.stop()
        except Exception: pass
        if cfg().get("archive_shows", True) and _RADIO.get("show"):
            threading.Thread(target=_archive_show, args=(_RADIO.get("show"), list(_RADIO.get("show_files") or [])),
                             daemon=True, name="radio-show-archive").start()
    _RADIO["svc"] = None
    _RADIO["show"] = None


def _archive_show(show_uid, files):
    """Render the show's running order into one MP3 and host it on the site (embed player, comments, ratings)."""
    try:
        files = [f for f in files if os.path.isfile(f)][:200]
        ff = __import__("sos_tools").which("ffmpeg")
        if not files or not ff:
            return
        import tempfile
        tmp = tempfile.mkdtemp(prefix="groovebox-show-")
        import subprocess
        row = get(show_uid) or {}
        data = {k: v for k, v in row.items() if k not in ("uid", "ts", "row_kind", "deleted", "origin")}
        name = str(data.get("name") or "Groovebox Radio")
        out = os.path.join(tmp, "%s - %s.mp3" % (name.replace("/", "-")[:60], time.strftime("%Y-%m-%d %H%M")))
        cmd = [ff, "-hide_banner", "-loglevel", "error", "-y"]
        for f in files:
            cmd += ["-i", f]
        cmd += ["-filter_complex", "".join("[%d:a]" % i for i in range(len(files))) + "concat=n=%d:v=0:a=1[a]" % len(files),
                "-map", "[a]", "-ac", "2", "-ar", "44100", "-b:a", "192k", out]
        import app_limits
        p = app_limits.popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.wait(timeout=3600) == 0 and os.path.isfile(out):
            hosted = host_file(out, title="📻 %s · %s" % (name, time.strftime("%Y-%m-%d %H:%M")),
                               note="Radio show · %d tracks" % len(files))
            data.update(hosted=hosted, ended=time.time())
            put("radio_show", data, uid=show_uid)
            notify_all("📻 show archived on the site: %s" % name, "radio")
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass


def install(app):
    """Nearby auto-radio (popups / auto-play by trust level) and boot network mode."""
    _APP["app"] = app
    c = cfg()
    if os.environ.get("GROOVEBOX_NETWORK_HOST") == "1":     # headless / boot host mode
        c["mode"] = "host"
    try:
        from PyQt6.QtCore import QObject, pyqtSignal

        class _Br(QObject):
            found = pyqtSignal()
        br = _Br(app); br.found.connect(lambda: radio_popup(app)); _APP["bridge"] = br
    except Exception:
        pass
    if c["mode"] == "host":
        try:
            import groovebox_site as gs
            st = gs.site(app)
            st.cfg["relay_host"] = True
            if st.httpd is None: st.start()
        except Exception as exc:
            print("[Network] host site: %s" % exc)
    try:
        import groovebox_site as gs
        if not getattr(gs.Site, "_r99_net", False):
            orig = gs.Site._handle

            def _handle(self, h, method, _o=orig):
                u = urllib.parse.urlsplit(h.path)
                try:
                    if handle(self, h, method, urllib.parse.unquote(u.path), u.query):
                        return
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    try: self._send(h, 500, "error: %s" % exc, "text/plain"); return
                    except Exception: return
                return _o(self, h, method)
            gs.Site._handle = _handle; gs.Site._r99_net = True
    except Exception:
        pass
    threading.Thread(target=_listen_radios, args=(app,), daemon=True, name="net-radio-listen").start()
    if c["mode"] in ("host", "member"):
        threading.Thread(target=_network_loop, args=(app,), daemon=True, name="net-loop").start()


def _listen_radios(app):
    import json as _j, socket
    try:
        import radio_station as rs
        port, magic = rs.DISCOVERY_PORT, rs.DISCOVERY_MAGIC
    except Exception:
        return
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except Exception: pass
    try: s.bind(("", port))
    except Exception: return
    seen = {}
    while True:
        try:
            raw, addr = s.recvfrom(65535); d = _j.loads(raw.decode("utf-8", "replace"))
            if d.get("magic") != magic: continue
            url = str(d.get("url", "")); key = addr[0]
            mine = _RADIO.get("svc")
            if mine is not None and url == mine.url: continue
            lv = trust(key)
            if not allowed(lv, "popup") or time.time() - seen.get(key, 0) < 600: continue
            seen[key] = time.time()
            app._net_radio_found = {"name": d.get("name", "Groovebox Radio"), "url": url, "level": lv}
            br = _APP.get("bridge")
            if br is not None:
                br.found.emit()
            __import__("notify_center").notify(app, "📻 %s is on air nearby (%s)" % (d.get("name", "radio"), lv), "info")
        except Exception:
            time.sleep(1)


def radio_popup(app):
    """Non-modal popup; trusted / housemates start playing at once (setting radio_autoplay)."""
    info = getattr(app, "_net_radio_found", None)
    if not info: return
    from PyQt6.QtWidgets import QMessageBox
    c = cfg()
    auto = allowed(info["level"], "autoplay") and c["radio_autoplay"] in ("trusted", "all") or c["radio_autoplay"] == "all"
    if auto:
        play_stream(app, info["url"] + "stream.mp3"); return
    if not c["radio_popups"]: return
    m = QMessageBox(app); m.setWindowTitle("📻 Nearby radio"); m.setText("%s is on air nearby. Listen?" % info["name"])
    m.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No); m.setModal(False)
    m.buttonClicked.connect(lambda b: m.buttonRole(b) == QMessageBox.ButtonRole.YesRole and play_stream(app, info["url"] + "stream.mp3"))
    m.show(); app._radio_msg = m


def play_stream(app, url):
    from PyQt6.QtCore import QUrl
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    p = getattr(app, "_net_radio_player", None)
    if p is None:
        p = app._net_radio_player = QMediaPlayer(app); o = QAudioOutput(app); p.setAudioOutput(o); app._net_radio_out = o
    p.setSource(QUrl(url)); p.play()
    __import__("notify_center").notify(app, "📻 listening: %s" % url, "info")


def _network_loop(app):
    """Member: announce + subscribe (fail over by host priority). Host: also pull from the other hosts."""
    since = 0.0
    while True:
        c = cfg(); hosts = c["hosts"]
        if c["mode"] == "host":
            for hu in hosts:
                try:
                    n = sync_from(hu)
                    if n: __import__("notify_center").notify(app, "🔁 synced %d rows from %s" % (n, hu), "info", key="sync:" + hu, every_s=60)
                except Exception:
                    pass
            time.sleep(30 if c["role"] == "primary" else 90); continue
        for hu in hosts:                         # member: first reachable host by priority
            try:
                files = []
                try:
                    import groovebox_site as gs
                    files = [os.path.basename(p) for _i, p in gs.shared_files()][:300]
                except Exception:
                    pass
                body = json.dumps({"name": c["name"] or "Groovebox", "url": "", "files": files}).encode()
                urllib.request.urlopen(urllib.request.Request(hu.rstrip("/") + "/api/net/announce", data=body,
                                                              headers={"Content-Type": "application/json", "X-Groovebox-Member": c["origin"]}), timeout=10).read()
                with urllib.request.urlopen(urllib.request.Request(hu.rstrip("/") + "/api/net/notify?since=%f" % since,
                                                                   headers={"X-Groovebox-Member": c["origin"]}), timeout=35) as r:
                    for ev in json.loads(r.read() or b"[]"):
                        since = max(since, float(ev.get("ts", 0)))
                        txt = ev.get("text") or ev.get("title") or ev.get("name") or "update"
                        __import__("notify_center").notify(app, "🌐 %s" % str(txt)[:80], "info")
                break
            except Exception:
                continue
        else:
            time.sleep(10)


# ------------------------------------------------------------------ the window
def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLineEdit, QPlainTextEdit, QPushButton, QListWidget,
                                 QLabel, QFileDialog, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView)
    import compat_settings as cs
    d = QDialog(app); d.setWindowTitle("🌐 Network · radio · blog · files · trust"); d.resize(1040, 680); d.setWindowModality(Qt.WindowModality.NonModal)
    tabs = QTabWidget(); QVBoxLayout(d).addWidget(tabs); say = QLabel(""); d.layout().addWidget(say)

    def page_(t):
        w = QWidget(); l = QVBoxLayout(w); tabs.addTab(w, t); return l
    # radio
    l = page_("📻 Radio")
    try:
        import radio_station as rs
        ident = rs.load_identity()
    except Exception:
        rs = None; ident = {"name": "Groovebox Radio"}
    nm = QLineEdit(ident.get("name", "")); logo = QLineEdit(ident.get("logo", "")); bl = QPushButton("Logo…")
    row = QHBoxLayout(); [row.addWidget(w) for w in (QLabel("Radio name"), nm, QLabel("Logo"), logo, bl)]; l.addLayout(row)
    bl.clicked.connect(lambda: (lambda p: p and logo.setText(p))(QFileDialog.getOpenFileName(d, "Logo", os.path.expanduser("~"), "Images (*.png *.jpg)")[0]))
    order = QListWidget(); order.setDragDropMode(QListWidget.DragDropMode.InternalMove); l.addWidget(QLabel("Running order (drag to arrange)")); l.addWidget(order, 1)
    row = QHBoxLayout(); l.addLayout(row)
    ba = QPushButton("＋ Add audio…"); bx = QPushButton("＋ From Experiences (rated ≥ 3★)"); br = QPushButton("− Remove"); bs = QPushButton("🎲 Shuffle")
    bon = QPushButton("📡 Go on air"); boff = QPushButton("⏹ Off air"); auto = QComboBox(); auto.addItems(["trusted", "all", "none"])
    auto.setCurrentText(cfg()["radio_autoplay"]); auto.currentTextChanged.connect(lambda v: cs.update(radio_autoplay=v))
    for w in (ba, bx, br, bs, bon, boff, QLabel("Auto-play nearby"), auto): row.addWidget(w)

    def add_files():
        ps, _ = QFileDialog.getOpenFileNames(d, "Audio", os.path.expanduser("~"), "Audio (*.wav *.flac *.mp3 *.ogg *.m4a)")
        for p in ps: order.addItem(p)

    def add_xp():
        try:
            import experiences as xp
            for e in xp.load().values():
                if int(e.get("rating", 0)) >= 3 and e["path"].lower().endswith((".wav", ".flac", ".mp3", ".ogg", ".m4a")) and os.path.isfile(e["path"]): order.addItem(e["path"])
        except Exception as exc:
            say.setText(str(exc))

    def shuffle():
        import random
        items = [order.item(i).text() for i in range(order.count())]; random.shuffle(items); order.clear(); [order.addItem(x) for x in items]

    def on_air():
        if rs is not None:
            idt = rs.load_identity(); idt.update(name=nm.text().strip() or "Groovebox Radio", logo=logo.text().strip()); rs.save_identity(idt)
        url = radio_start([order.item(i).text() for i in range(order.count())]); say.setText("on air · " + url + " · site page /radio")
    ba.clicked.connect(add_files); bx.clicked.connect(add_xp); br.clicked.connect(lambda: [order.takeItem(order.row(i)) for i in order.selectedItems()])
    bs.clicked.connect(shuffle); bon.clicked.connect(on_air); boff.clicked.connect(lambda: (radio_stop(), say.setText("off air")))
    msgs = QPlainTextEdit(); msgs.setReadOnly(True); msgs.setMaximumHeight(120); l.addWidget(QLabel("Messages to the host")); l.addWidget(msgs)
    bm = QPushButton("Refresh messages"); bm.clicked.connect(lambda: msgs.setPlainText("\n".join("%s · %s (%s): %s" % (time.strftime("%m-%d %H:%M", time.localtime(m["ts"])), m.get("author"), m.get("level"), m.get("text")) for m in rows("message", 100))))
    l.addWidget(bm)
    # blog
    l = page_("📝 Blog")
    posts = QListWidget(); l.addWidget(posts, 1); title = QLineEdit(); title.setPlaceholderText("title")
    text = QPlainTextEdit(); text.setPlaceholderText("# heading\n**bold** _italic_ [link](https://…)  embed a hosted file: [[file:ID]]")
    l.addWidget(title); l.addWidget(text, 2); row = QHBoxLayout(); l.addLayout(row)
    bp = QPushButton("Publish / update"); bn = QPushButton("New"); bd = QPushButton("Delete"); state = {"uid": None}
    for w in (bn, bp, bd): row.addWidget(w)

    def pfill():
        posts.clear()
        for p in rows("post", 200):
            posts.addItem("%s · %s" % (time.strftime("%Y-%m-%d", time.localtime(p["ts"])), p.get("title", ""))); posts.item(posts.count() - 1).setData(Qt.ItemDataRole.UserRole, p["uid"])

    def pick(it):
        p = get(it.data(Qt.ItemDataRole.UserRole)); state["uid"] = p["uid"]; title.setText(p.get("title", "")); text.setPlainText(p.get("text", ""))
    posts.itemClicked.connect(pick)
    bn.clicked.connect(lambda: (state.__setitem__("uid", None), title.clear(), text.clear()))
    bp.clicked.connect(lambda: (put("post", {"title": title.text(), "text": text.toPlainText()}, uid=state["uid"]), pfill(), say.setText("published · /blog")))
    bd.clicked.connect(lambda: state["uid"] and (put("post", {"title": "", "text": ""}, uid=state["uid"], deleted=True), pfill()))
    pfill()
    # hosted files
    l = page_("📦 Files")
    ft = QTableWidget(0, 5); ft.setHorizontalHeaderLabels(("title", "kind", "size KB", "rating", "id (embed)")); ft.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    l.addWidget(ft, 1); row = QHBoxLayout(); l.addLayout(row)
    bh = QPushButton("＋ Host files…"); bhx = QPushButton("＋ Host from Experiences (selected ≥ 4★)"); brm = QPushButton("− Unpublish selected")
    for w in (bh, bhx, brm): row.addWidget(w)

    def ffill():
        items = rows("hosted", 1000); ft.setRowCount(len(items))
        for i, it in enumerate(items):
            for c_, v in enumerate((it.get("title", ""), it.get("file_kind") or KIND.get(it.get("ext", ""), "file"), str(int(it.get("size", 0)) // 1024), "%.1f" % rating(it["uid"])["avg"], it["uid"])):
                ft.setItem(i, c_, QTableWidgetItem(v))

    def host():
        ps, _ = QFileDialog.getOpenFileNames(d, "Host files", os.path.expanduser("~"), "All (*)")
        for p in ps: host_file(p)
        ffill()

    def host_xp():
        try:
            import experiences as xp
            for e in xp.load().values():
                if int(e.get("rating", 0)) >= 4 and os.path.isfile(e["path"]): host_file(e["path"], note="from Experiences")
        except Exception as exc:
            say.setText(str(exc))
        ffill()

    def unpub():
        for r in sorted({i.row() for i in ft.selectedIndexes()}):
            uid = ft.item(r, 4).text(); it = get(uid); put("hosted", {k: v for k, v in it.items() if k not in ("uid", "ts", "deleted", "row_kind")}, uid=uid, deleted=True)
        ffill()
    bh.clicked.connect(host); bhx.clicked.connect(host_xp); brm.clicked.connect(unpub); ffill()
    # trust
    l = page_("🛡 Trust")
    tt = QTableWidget(0, 3); tt.setHorizontalHeaderLabels(("Groovebox (member id or IP)", "level", "note")); tt.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    l.addWidget(tt, 1); row = QHBoxLayout(); l.addLayout(row)
    who = QLineEdit(); who.setPlaceholderText("member id or IP"); lvl = QComboBox(); lvl.addItems(list(LEVELS)); note = QLineEdit(); note.setPlaceholderText("note")
    bt = QPushButton("Set level")
    for w in (who, lvl, note, bt): row.addWidget(w)
    near = QPushButton("Add Grooveboxes seen nearby (as public)"); l.addWidget(near)

    def tfill():
        lst = trust_list(); tt.setRowCount(len(lst))
        for i, t in enumerate(lst):
            for c_, v in enumerate((t["who"], t["level"], t["note"])): tt.setItem(i, c_, QTableWidgetItem(v))

    def add_near():
        svc = getattr(app, "_nearby_share_service", None)
        for p in (list(getattr(svc, "peers", {}).values()) if svc else []):
            if trust(p.ip) == "public": set_trust(p.ip, "public", p.name)
        tfill()
    bt.clicked.connect(lambda: (who.text().strip() and set_trust(who.text().strip(), lvl.currentText(), note.text()), tfill())); near.clicked.connect(add_near); tfill()
    # network
    l = page_("🌐 Host network")
    c = cfg()
    mode = QComboBox(); mode.addItems(["off", "member", "host"]); mode.setCurrentText(c["mode"])
    role = QComboBox(); role.addItems(["primary", "gig"]); role.setCurrentText(c["role"])
    net = QLineEdit(c["name"]); net.setPlaceholderText("network name"); key = QLineEdit(c["key"]); key.setPlaceholderText("network key (hosts sync only with the same key)")
    key.setEchoMode(QLineEdit.EchoMode.Password)
    hosts = QPlainTextEdit("\n".join(c["hosts"])); hosts.setPlaceholderText("other hosts, one URL per line, in priority order (primary first)")
    for lab, w in (("Boot mode", mode), ("Host role", role), ("Network", net), ("Key", key)):
        r_ = QHBoxLayout(); r_.addWidget(QLabel(lab)); r_.addWidget(w, 1); l.addLayout(r_)
    l.addWidget(QLabel("Hosts (members fail over in this order; hosts sync with every one)")); l.addWidget(hosts, 1)
    bsave = QPushButton("Save · applies at the next start (or Start now)"); bnow = QPushButton("Start now"); bsync = QPushButton("Sync now")
    note2 = QLabel("Host mode also turns on your site with relay hosting, so members behind NAT reach the network through you.")
    for w in (bsave, bnow, bsync, note2): l.addWidget(w)

    def save_net():
        cs.update(network_mode=mode.currentText(), network_role=role.currentText(), network_name=net.text().strip(), network_key=key.text(),
                  network_hosts=[x.strip() for x in hosts.toPlainText().splitlines() if x.strip()])
        say.setText("network settings saved")

    def start_now():
        save_net()
        try:
            import groovebox_site as gs
            s = gs.site(app) if hasattr(gs, "site") else None
            if s is not None and mode.currentText() == "host":
                s.cfg["relay_host"] = True; gs.save_cfg(s.cfg) if hasattr(gs, "save_cfg") else None
                if s.httpd is None: s.start()
        except Exception as exc:
            say.setText("site: %s" % exc)
        threading.Thread(target=_network_loop, args=(app,), daemon=True, name="net-loop").start(); say.setText("network running")

    def sync_now():
        out = []
        for hu in [x.strip() for x in hosts.toPlainText().splitlines() if x.strip()]:
            try: out.append("%s: %d rows" % (hu, sync_from(hu)))
            except Exception as exc: out.append("%s: %s" % (hu, exc))
        say.setText(" · ".join(out) or "no hosts")
    bsave.clicked.connect(save_net); bnow.clicked.connect(start_now); bsync.clicked.connect(sync_now)
    d.show(); app._net_window = d
    return d
