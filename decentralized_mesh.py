"""Decentralized Groovebox mesh metadata + messaging.

Design goals:
- Works LAN-first and can extend over the public Internet through remembered/bootstrap URLs.
- Peers are addressed by stable Radio IDs, not transient IPs.
- IPs/URLs are tagged/detagged associations on a Radio ID and can age out.
- Generic JSON-safe metadata can be gossiped slowly; binaries remain referenced by hashes/URLs.
- Similar old/new metadata hashes reinforce associations without replacing identity.
- Rare retry pulls stale associations back into the loop without tight polling.
- No remote code execution and no automatic file upload.
"""
from __future__ import annotations
import base64, hashlib, json, os, random, threading, time, urllib.request, urllib.error
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

M = 1.1975807343
MAX_PAYLOAD = 256 * 1024
DEFAULT_GOSSIP_INTERVAL = 61.0 / (M - 1.0)  # slow, deterministic-ish ~309s
RARE_RETRY_SECONDS = 3600.0 / (2.0 - M)    # ~74.8 min


def _base_dir() -> Path:
    try:
        import groovebox_paths
        p = Path(groovebox_paths.base_dir())
    except Exception:
        p = Path.home() / ".mathematicians_groovebox"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _mesh_path() -> Path: return _base_dir() / "decentralized_mesh.json"
def _secret_path() -> Path: return _base_dir() / "radio_node_secret.bin"


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def data_hash(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _simhash64(obj: Any) -> int:
    """Tiny content-similarity fingerprint for associative metadata, not security."""
    toks = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).lower().replace('"',' ').replace(':',' ').replace(',',' ').split()
    if not toks: return 0
    acc = [0] * 64
    for tok in toks[:4096]:
        h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")
        for i in range(64): acc[i] += 1 if ((h >> i) & 1) else -1
    out = 0
    for i, v in enumerate(acc):
        if v >= 0: out |= 1 << i
    return out


def similarity(a: Any, b: Any) -> float:
    x = _simhash64(a) ^ _simhash64(b)
    return 1.0 - (x.bit_count() / 64.0)


def _load_secret() -> bytes:
    p = _secret_path()
    if p.exists():
        try: return p.read_bytes()
        except Exception: pass
    s = os.urandom(32)
    try:
        p.write_bytes(s); os.chmod(p, 0o600)
    except Exception: pass
    return s


def radio_id() -> str:
    return "mgr-" + hashlib.sha256(_load_secret()).hexdigest()[:24]


class MeshStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.state: Dict[str, Any] = {"version": 1, "self_id": radio_id(), "peers": {}, "records": {}, "messages": [], "seen": {}}
        self.load()

    def load(self):
        try:
            x = json.loads(_mesh_path().read_text(encoding="utf-8"))
            if isinstance(x, dict): self.state.update(x)
        except Exception: pass
        self.state["self_id"] = radio_id()

    def save(self):
        with self.lock:
            tmp = _mesh_path().with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, _mesh_path())

    @property
    def self_id(self): return self.state["self_id"]

    def tag_endpoint(self, peer_id: str, url: str, ip: str = "", tags: Optional[Iterable[str]] = None, confidence: float = 1.0):
        if not peer_id or peer_id == self.self_id or not url: return
        now = time.time(); tags = sorted(set(str(x)[:64] for x in (tags or []) if str(x).strip()))
        with self.lock:
            p = self.state["peers"].setdefault(peer_id, {"endpoints": {}, "tags": [], "last_seen": 0.0, "score": 0.0})
            ep = p["endpoints"].setdefault(url, {"ip": ip, "first_seen": now, "last_seen": now, "confidence": 0.0, "tags": []})
            ep.update({"ip": ip or ep.get("ip", ""), "last_seen": now, "confidence": min(1.0, max(float(ep.get("confidence",0)), float(confidence)))})
            ep["tags"] = sorted(set(ep.get("tags", [])) | set(tags))
            p["tags"] = sorted(set(p.get("tags", [])) | set(tags)); p["last_seen"] = now
        self.save()

    def detag_endpoint(self, peer_id: str, url: str, tag: Optional[str] = None):
        with self.lock:
            p = self.state.get("peers", {}).get(peer_id, {}); ep = p.get("endpoints", {}).get(url)
            if not ep: return
            if tag:
                ep["tags"] = [x for x in ep.get("tags", []) if x != tag]
            else:
                p.get("endpoints", {}).pop(url, None)
        self.save()

    def ingest_record(self, record: Dict[str, Any], source_peer: str = "") -> bool:
        if not isinstance(record, dict): return False
        if len(_canonical(record)) > MAX_PAYLOAD: return False
        payload = record.get("data")
        rid = str(record.get("hash") or data_hash(payload))
        record = dict(record); record["hash"] = rid; record.setdefault("ts", time.time()); record.setdefault("kind", "generic")
        with self.lock:
            if rid in self.state["records"]: return False
            # associate highly similar prior records rather than overwriting them
            best_id, best_sim = "", 0.0
            for oid, old in list(self.state["records"].items())[-512:]:
                s = similarity(payload, old.get("data"))
                if s > best_sim: best_id, best_sim = oid, s
            if best_sim >= 0.82:
                record["associated_with"] = best_id; record["association_similarity"] = round(best_sim, 6)
            if source_peer: record["source_peer"] = source_peer
            self.state["records"][rid] = record
            # cap local cache while preserving newest/associated material
            if len(self.state["records"]) > 4096:
                olds = sorted(self.state["records"].items(), key=lambda kv: float(kv[1].get("ts",0)))[:512]
                for k,_ in olds: self.state["records"].pop(k, None)
        self.save(); return True

    def publish(self, kind: str, data: Any, tags: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        r = {"kind": str(kind)[:80], "data": data, "tags": sorted(set(str(x)[:64] for x in (tags or []))), "origin": self.self_id, "ts": time.time()}
        r["hash"] = data_hash(r["data"]); self.ingest_record(r, self.self_id); return r

    def queue_message(self, to_peer: str, text: str, tags: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        msg = {"id": data_hash([self.self_id,to_peer,text,time.time()]), "from": self.self_id, "to": str(to_peer), "text": str(text)[:8192], "tags": list(tags or []), "ts": time.time(), "delivered": False}
        with self.lock: self.state["messages"].append(msg); self.state["messages"] = self.state["messages"][-2048:]
        self.save(); return msg

    def accept_message(self, msg: Dict[str, Any]) -> bool:
        if not isinstance(msg, dict) or str(msg.get("to")) not in (self.self_id, "*"): return False
        mid = str(msg.get("id") or data_hash(msg))
        with self.lock:
            if mid in self.state["seen"]: return False
            msg = dict(msg); msg["id"] = mid; msg["received_at"] = time.time(); msg["delivered"] = True
            self.state["messages"].append(msg); self.state["seen"][mid] = time.time()
        self.save(); return True

    def inbox(self) -> List[Dict[str, Any]]:
        return [m for m in self.state.get("messages", []) if m.get("to") in (self.self_id,"*") and m.get("delivered")]

    def hello(self, name: str, url: str, extra: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
        return {"mesh":"MGB_MESH_V1", "radio_id":self.self_id, "name":name, "url":url, "ts":time.time(), "tags":["groovebox","radio","mesh"], "extra": extra or {}}

    def peer_endpoints(self, include_stale: bool=False) -> List[Tuple[str,str]]:
        now=time.time(); out=[]
        for pid,p in self.state.get("peers",{}).items():
            for url,ep in p.get("endpoints",{}).items():
                age=now-float(ep.get("last_seen",0)); conf=float(ep.get("confidence",0))
                if include_stale or age < RARE_RETRY_SECONDS or conf >= 0.5: out.append((pid,url))
        return out

    def export_bundle(self, limit: int=48) -> Dict[str,Any]:
        recs=sorted(self.state.get("records",{}).values(), key=lambda r:float(r.get("ts",0)), reverse=True)[:limit]
        # only public-ish endpoint metadata; no local secrets
        peers={}
        for pid,p in list(self.state.get("peers",{}).items())[:256]:
            peers[pid]={"tags":p.get("tags",[]),"endpoints":p.get("endpoints",{}),"last_seen":p.get("last_seen",0)}
        return {"mesh":"MGB_MESH_V1","from":self.self_id,"records":recs,"peers":peers,"ts":time.time()}


class MeshGossip:
    def __init__(self, store: MeshStore, name_fn, url_fn):
        self.store=store; self.name_fn=name_fn; self.url_fn=url_fn; self.stop_event=threading.Event(); self.thread=None

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear(); self.thread=threading.Thread(target=self._loop, daemon=True); self.thread.start()

    def stop(self): self.stop_event.set()

    @staticmethod
    def post_json(url: str, path: str, obj: Any, timeout: float=4.0):
        b=_canonical(obj)
        if len(b)>MAX_PAYLOAD: raise ValueError("mesh payload too large")
        req=urllib.request.Request(url.rstrip('/')+path, data=b, headers={"Content-Type":"application/json","User-Agent":"MathematiciansGroovebox-Mesh/1"}, method="POST")
        with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read(MAX_PAYLOAD).decode("utf-8","replace"))

    def touch(self, pid: str, url: str):
        hello=self.store.hello(self.name_fn(), self.url_fn())
        try:
            ans=self.post_json(url,"/api/mesh/hello",hello)
            rid=str(ans.get("radio_id") or pid); self.store.tag_endpoint(rid,str(ans.get("url") or url),tags=ans.get("tags",[]),confidence=1.0)
            return True
        except Exception: return False

    def gossip_once(self, rare: bool=False):
        peers=self.store.peer_endpoints(include_stale=rare)
        if not peers: return
        # Slow association sharing: one normal peer; rare pass can try two stale peers.
        seed=int(hashlib.sha256(f"{self.store.self_id}:{int(time.time()//DEFAULT_GOSSIP_INTERVAL)}".encode()).hexdigest()[:16],16)
        rng=random.Random(seed); rng.shuffle(peers)
        for pid,url in peers[:(2 if rare else 1)]:
            try:
                ans=self.post_json(url,"/api/mesh/gossip",self.store.export_bundle(limit=24 if rare else 8))
                if isinstance(ans,dict):
                    for r in ans.get("records",[])[:24]: self.store.ingest_record(r,str(ans.get("from",pid)))
                    for qid,p in ans.get("peers",{}).items():
                        for qurl,ep in p.get("endpoints",{}).items():
                            # learned associations begin weak and strengthen only when later seen directly
                            self.store.tag_endpoint(qid,qurl,ip=str(ep.get("ip","")),tags=set(ep.get("tags",[]))|{"gossip"},confidence=min(0.35,float(ep.get("confidence",0.2))))
                # deliver at most a few queued messages to this peer
                for m in self.store.state.get("messages",[]):
                    if not m.get("delivered") and m.get("to") in (pid,"*"):
                        try:
                            ack=self.post_json(url,"/api/mesh/message",m)
                            if ack.get("accepted"): m["delivered"]=True; self.store.save()
                        except Exception: break
            except Exception: pass

    def _loop(self):
        last_rare=0.0
        while not self.stop_event.wait(DEFAULT_GOSSIP_INTERVAL):
            now=time.time(); rare=(now-last_rare)>=RARE_RETRY_SECONDS
            self.gossip_once(rare=rare)
            if rare: last_rare=now


def tag_export(path: str, store: Optional[MeshStore]=None, extra: Optional[Dict[str,Any]]=None) -> Optional[str]:
    """Write a small decentralized sidecar for any media/data export."""
    p=Path(path)
    if not p.exists() or not p.is_file(): return None
    store=store or MeshStore(); h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    meta={"filename":p.name,"bytes":p.stat().st_size,"sha256":h.hexdigest(),"radio_id":store.self_id,"tags":["groovebox","export",p.suffix.lower().lstrip('.')],"extra":extra or {},"ts":time.time()}
    side=str(p)+".mgmesh.json"; Path(side).write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding="utf-8")
    store.publish("media_export",meta,meta["tags"]); return side
