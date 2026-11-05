"""Live Edit Together — project co-management between online Grooveboxes.

GROOVEBOX_R23R_LIVE_EDIT_TOGETHER_20261101

Star topology around the session owner, who holds the authoritative version:

  member edit  -> "propose" {sections, base}  -> owner
  owner        -> applies (last writer wins per section, unless locked),
                  version += 1, broadcasts "update" {sections, version, by}
  everyone     -> applies sections it does not already have (hash compare)

A section is one top-level key of the project document (playlist, sequences,
instrument parameters, seed, global algorithm, …). Change detection hashes
each section once per tick, so only changed sections travel. Transport is the
Nearby /api/v1/coedit endpoint (works over LAN, Wi-Fi, ad hoc, Direct, IPv6
links); payloads are queued by the network thread and applied on the GUI
thread by the caller (drain()).

No Qt here: the caller provides snapshot() / apply(doc) callables.
"""
from __future__ import annotations

import hashlib
import json
import queue
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional
from urllib.request import Request, urlopen

MAX_COEDIT_BYTES = 64 * 1024 * 1024
# Sections that never travel (machine-local / volatile).
LOCAL_ONLY = {"autosave_meta", "window_geometry", "ui_window_state", "recovery", "project_path"}


def _h(value) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    except Exception:
        raw = repr(value).encode("utf-8", "replace")
    return hashlib.sha1(raw).hexdigest()


class CoEditSession:
    def __init__(self, svc, session_id: str, name: str, owner: str, members: List[Dict],
                 snapshot: Callable[[], Dict], apply: Callable[[Dict], None]):
        self.svc = svc
        self.id = session_id
        self.name = name
        self.owner = owner
        self.members: Dict[str, Dict] = {m["node"]: dict(m) for m in members if m.get("node")}
        self.snapshot = snapshot
        self.apply = apply
        self.version = 0
        self.hashes: Dict[str, str] = {}
        self.locks: Dict[str, str] = {}          # section -> node allowed to edit it (owner sets)
        self.activity: List[Dict] = []
        self.shared: Dict[str, object] = {}       # last shared value per section (lock revert)
        self.active = True
        self._lock = threading.Lock()

    # ------------------------------------------------------------ helpers
    @property
    def is_owner(self) -> bool:
        return self.owner == self.svc.node_id

    def log(self, who: str, text: str):
        self.activity.append({"ts": time.time(), "who": who, "text": text})
        del self.activity[:-200]

    def _peer(self, node: str) -> Optional[Dict]:
        for p in self.svc.peer_list():
            if p.get("node_id") == node:
                return p
        return None

    def _post(self, node: str, payload: Dict, timeout: float = 20.0) -> bool:
        p = self._peer(node)
        if p is None:
            return False
        body = json.dumps(payload, default=str).encode("utf-8")
        req = Request(p["url"].rstrip("/") + "/api/v1/coedit", data=body, method="POST",
                      headers={"Content-Type": "application/json", "X-Groovebox-Node": self.svc.node_id})
        try:
            with urlopen(req, timeout=timeout) as r:
                return r.status in (200, 201)
        except Exception:
            return False

    def _send_async(self, nodes: List[str], payload: Dict):
        def run():
            for n in nodes:
                if n != self.svc.node_id:
                    ok = self._post(n, payload)
                    if n in self.members:
                        self.members[n]["online"] = ok
        threading.Thread(target=run, daemon=True, name="groovebox-coedit-send").start()

    def _envelope(self, kind: str, **extra) -> Dict:
        return {"session": self.id, "kind": kind, "name": self.name, "owner": self.owner,
                "from_node": self.svc.node_id, "from_name": self.svc.name, "ts": time.time(), **extra}

    # -------------------------------------------------------------- local
    def baseline(self):
        """Remember the current document as already shared (no send)."""
        snap = self.snapshot() or {}
        self.hashes = {k: _h(v) for k, v in snap.items() if k not in LOCAL_ONLY}
        self.shared = {k: v for k, v in snap.items() if k not in LOCAL_ONLY}

    def local_tick(self) -> List[str]:
        """Detect local edits and send them. Returns the changed section names."""
        if not self.active:
            return []
        snap = self.snapshot() or {}
        changed = {}; reverted = {}
        for k, v in snap.items():
            if k in LOCAL_ONLY:
                continue
            hv = _h(v)
            if self.hashes.get(k) != hv:
                if self.locks.get(k) not in (None, self.svc.node_id):
                    if k in self.shared:
                        reverted[k] = self.shared[k]   # locked by someone else: snap back
                    continue
                changed[k] = v
                self.hashes[k] = hv
                self.shared[k] = v
        if reverted:
            doc = dict(snap); doc.update(reverted); self.apply(doc)
            self.log("You", "locked section(s) restored: " + ", ".join(sorted(reverted)))
        if not changed:
            return []
        if self.is_owner:
            self.version += 1
            self._send_async(list(self.members), self._envelope("update", sections=changed, version=self.version,
                                                                 by=self.svc.name, locks=self.locks))
        else:
            self._send_async([self.owner], self._envelope("propose", sections=changed, base=self.version))
        self.log("You", "changed " + ", ".join(sorted(changed)))
        return sorted(changed)

    def invite(self):
        """Owner: send the full document to every member."""
        snap = {k: v for k, v in (self.snapshot() or {}).items() if k not in LOCAL_ONLY}
        self.hashes = {k: _h(v) for k, v in snap.items()}
        self.shared = dict(snap)
        self._send_async(list(self.members), self._envelope("invite", sections=snap, version=self.version,
                                                             members=list(self.members.values()), locks=self.locks))
        self.log("You", f"started “{self.name}” with {len(self.members)} member(s)")

    def set_lock(self, section: str, node: Optional[str]):
        if not self.is_owner:
            raise PermissionError("only the session owner can lock sections")
        if node:
            self.locks[section] = node
        else:
            self.locks.pop(section, None)
        self.version += 1
        self._send_async(list(self.members), self._envelope("update", sections={}, version=self.version,
                                                             by=self.svc.name, locks=self.locks))

    def leave(self):
        self.active = False
        if self.is_owner:
            self._send_async(list(self.members), self._envelope("end"))
        else:
            self._send_async([self.owner], self._envelope("leave"))

    # ------------------------------------------------------------- remote
    def _apply_sections(self, sections: Dict):
        fresh = {k: v for k, v in (sections or {}).items() if k not in LOCAL_ONLY and self.hashes.get(k) != _h(v)}
        if not fresh:
            return []
        doc = dict(self.snapshot() or {})
        doc.update(fresh)
        self.apply(doc)
        for k, v in fresh.items():
            self.hashes[k] = _h(v)
            self.shared[k] = v
        return sorted(fresh)

    def handle(self, p: Dict) -> Optional[str]:
        """Apply one received payload (GUI thread). Returns a status line or None."""
        kind = p.get("kind")
        who = p.get("from_name", "Groovebox")
        if kind == "propose" and self.is_owner:
            node = p.get("from_node", "")
            if node not in self.members:
                return None
            allowed = {k: v for k, v in (p.get("sections") or {}).items() if self.locks.get(k) in (None, node)}
            keys = self._apply_sections(allowed)
            if keys:
                self.version += 1
                self._send_async(list(self.members), self._envelope("update", sections=allowed, version=self.version,
                                                                     by=who, locks=self.locks))
                self.log(who, "changed " + ", ".join(keys))
                return f"{who} changed {', '.join(keys)} · v{self.version}"
            return None
        if kind == "update" and not self.is_owner and p.get("from_node") == self.owner:
            self.version = max(self.version, int(p.get("version", 0) or 0))
            self.locks = dict(p.get("locks") or {})
            keys = self._apply_sections(p.get("sections") or {})
            if keys:
                self.log(p.get("by", who), "changed " + ", ".join(keys))
                return f"{p.get('by', who)} changed {', '.join(keys)} · v{self.version}"
            return None
        if kind == "join" and self.is_owner:
            node = p.get("from_node", "")
            if node in self.members:
                self.members[node]["joined"] = True; self.members[node]["online"] = True
                # bring the joiner fully up to date
                snap = {k: v for k, v in (self.snapshot() or {}).items() if k not in LOCAL_ONLY}
                self._send_async([node], self._envelope("update", sections=snap, version=self.version, by=self.svc.name,
                                                        locks=self.locks))
                self.log(who, "joined")
                return f"{who} joined “{self.name}”"
        if kind == "leave" and self.is_owner:
            node = p.get("from_node", "")
            if node in self.members:
                self.members[node]["joined"] = False
                self.log(who, "left")
                return f"{who} left “{self.name}”"
        if kind == "end" and p.get("from_node") == self.owner:
            self.active = False
            self.log(who, "ended the session")
            return f"{who} ended “{self.name}”"
        return None


class CoEditManager:
    """Owns the inbox the network thread fills and the (single) active session."""

    def __init__(self, svc):
        self.svc = svc
        self.inbox: "queue.Queue[Dict]" = queue.Queue(maxsize=256)
        self.session: Optional[CoEditSession] = None
        self.pending_invites: Dict[str, Dict] = {}
        self.pending_requests: Dict[str, Dict] = {}     # node -> request payload
        self.requested_from: Dict[str, float] = {}      # nodes we asked (auto-join their invite)

    def receive(self, payload: Dict):
        try:
            self.inbox.put_nowait(payload)
        except queue.Full:
            pass

    def start(self, name: str, members: List[Dict], snapshot, apply) -> CoEditSession:
        sid = "edit-" + uuid.uuid4().hex[:12]
        mem = [m for m in members if m.get("node") and m.get("node") != self.svc.node_id]
        self.session = CoEditSession(self.svc, sid, name, self.svc.node_id, mem, snapshot, apply)
        self.session.invite()
        return self.session

    def join(self, invite: Dict, snapshot, apply) -> CoEditSession:
        mem = [m for m in (invite.get("members") or []) if m.get("node") != self.svc.node_id]
        if all(m.get("node") != invite.get("owner") for m in mem):
            mem.append({"node": invite.get("owner"), "name": invite.get("from_name", "Owner")})
        s = CoEditSession(self.svc, invite["session"], invite.get("name", "Shared project"), invite["owner"], mem,
                          snapshot, apply)
        s.version = int(invite.get("version", 0) or 0)
        s.locks = dict(invite.get("locks") or {})
        s._apply_sections(invite.get("sections") or {})
        s.baseline()
        s._send_async([s.owner], s._envelope("join"))
        s.log("You", f"joined “{s.name}”")
        self.session = s
        self.pending_invites.pop(invite["session"], None)
        return s

    # ---------------------------------------------------------- requests
    def _post_peer(self, node: str, payload: Dict) -> bool:
        tmp = CoEditSession(self.svc, payload.get("session", "req"), "", node, [], lambda: {}, lambda d: None)
        return tmp._post(node, payload)

    def request(self, peer_node: str, note: str = "") -> bool:
        """Ask a Groovebox to Edit Together on its project."""
        self.requested_from[peer_node] = time.time()
        return self._post_peer(peer_node, {"session": "req-" + uuid.uuid4().hex[:8], "kind": "request", "note": note,
                                           "from_node": self.svc.node_id, "from_name": self.svc.name, "ts": time.time()})

    def deny(self, kind: str, key: str):
        p = (self.pending_invites if kind == "invite" else self.pending_requests).pop(key, None)
        if p:
            target = p.get("owner") if kind == "invite" else p.get("from_node")
            self._post_peer(target, {"session": p.get("session", "req"), "kind": "deny", "what": kind,
                                     "from_node": self.svc.node_id, "from_name": self.svc.name, "ts": time.time()})

    def approve_request(self, node: str, snapshot, apply, name: str = "Shared project") -> CoEditSession:
        """Owner side: add the requester to the running session (or start one)."""
        p = self.pending_requests.pop(node, {})
        member = {"node": node, "name": p.get("from_name", "Groovebox")}
        s = self.session
        if s is not None and s.active and s.is_owner:
            if node not in s.members:
                s.members[node] = member
            s._send_async([node], s._envelope("invite", sections=dict(s.shared or {}), version=s.version,
                                               members=list(s.members.values()), locks=s.locks))
            s.log("You", f"approved {member['name']}")
            return s
        return self.start(name, [member], snapshot, apply)

    def drain(self) -> List[str]:
        """GUI thread: process queued payloads. Returns status lines (and new invites)."""
        out = []
        while True:
            try:
                p = self.inbox.get_nowait()
            except queue.Empty:
                break
            kind = p.get("kind")
            if kind == "invite" and (self.session is None or self.session.id != p.get("session")):
                if p.get("owner") in self.requested_from:
                    self.requested_from.pop(p.get("owner"), None)
                    self.pending_invites[p.get("session", "")] = p
                    out.append(f"AUTOJOIN:{p.get('session', '')}")
                else:
                    self.pending_invites[p.get("session", "")] = p
                    out.append(f"INVITE:{p.get('session', '')}")
                continue
            if kind == "request":
                self.pending_requests[p.get("from_node", "")] = p
                out.append(f"REQUEST:{p.get('from_node', '')}")
                continue
            if kind == "deny":
                self.requested_from.pop(p.get("from_node", ""), None)
                out.append(f"DENIED:{p.get('from_name', 'Groovebox')} declined your Edit Together {p.get('what', 'request')}")
                continue
            if self.session is not None and p.get("session") == self.session.id:
                line = self.session.handle(p)
                if line:
                    out.append(line)
        return out
