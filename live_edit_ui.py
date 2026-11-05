"""Edit Together (ET) — approve / deny / request UI and main-window indicator.

GROOVEBOX_R23R_LIVE_EDIT_TOGETHER_20261101

LiveEditController lives on the main window for the whole session:
  * drains Live Edit Together traffic on the GUI thread (coedit.CoEditManager),
  * applies remote project sections and sends local edits (1 s tick),
  * lights the main window's PERFORMANCE button while ET requests/invites wait,
  * pops an Approve / Deny dialog while Performance is open,
  * backs Performance's "📥 Access ET Requests" list.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                             QVBoxLayout)

_BTN_BASE_TEXT = "🎛  PERFORMANCE · LIVE OPERATION STATION"


class LiveEditController(QObject):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self._btn_style = None
        self._popup = None
        self._last_lines = []
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._last_local = 0.0

    # ---------------------------------------------------------- plumbing
    @property
    def svc(self):
        return getattr(self.host, "_nearby_share_service", None)

    @property
    def mgr(self):
        s = self.svc
        return getattr(s, "coedit", None) if s is not None else None

    def snapshot(self):
        try:
            return self.host._project_snapshot()
        except Exception:
            return {}

    def apply(self, doc):
        h = self.host
        h._coedit_applying = True
        try:
            h._apply_project_snapshot(doc)
            try:
                h._refresh_after_file_input(reason="edit_together")
            except Exception:
                pass
        finally:
            h._coedit_applying = False

    def pending_count(self) -> int:
        m = self.mgr
        return 0 if m is None else len(m.pending_invites) + len(m.pending_requests)

    def performance_visible(self) -> bool:
        p = getattr(self.host, "_performance_panel", None)
        try:
            return p is not None and p.isVisible() and not p.isMinimized()
        except Exception:
            return False

    def status_text(self) -> str:
        m = self.mgr
        s = m.session if m is not None else None
        if s is None or not s.active:
            n = self.pending_count()
            return "Edit Together: not in a session" + (f" · {n} request(s) waiting" if n else "")
        names = []
        for node, mem in s.members.items():
            dot = "●" if mem.get("online", True) and mem.get("joined", not s.is_owner) else "○"
            names.append(f"{dot} {mem.get('name', 'Groovebox')}")
        role = "owner" if s.is_owner else "member"
        lk = f" · locks: {', '.join(f'{k}' for k in s.locks)}" if s.locks else ""
        return f"🤝 “{s.name}” · v{s.version} · you are {role} · " + ", ".join(names) + lk

    # ----------------------------------------------------------- the tick
    def _tick(self):
        m = self.mgr
        if m is None:
            return
        lines = m.drain()
        for ln in lines:
            if ln.startswith("AUTOJOIN:"):
                inv = m.pending_invites.get(ln.split(":", 1)[1])
                if inv:
                    m.join(inv, self.snapshot, self.apply)
                    self._status(f"🤝 Joined “{inv.get('name', 'shared project')}” (your request was approved)")
            elif ln.startswith(("INVITE:", "REQUEST:")):
                self._status("📥 New Edit Together " + ("invite" if ln.startswith("INVITE") else "request"))
            elif ln.startswith("DENIED:"):
                self._status("⛔ " + ln.split(":", 1)[1])
            else:
                self._status("🤝 " + ln)
        s = m.session
        if s is not None and s.active and time.time() - self._last_local >= 1.0:
            self._last_local = time.time()
            if not getattr(self.host, "_coedit_applying", False):
                try:
                    s.local_tick()
                except Exception as exc:
                    self._status(f"Edit Together send failed: {exc}")
        self._update_indicator()
        keys = set(m.pending_invites) | set(m.pending_requests)
        new = keys - getattr(self, "_seen_keys", set())
        if new and self.performance_visible() and self._popup is None:
            self._seen_keys = getattr(self, "_seen_keys", set()) | keys
            self.show_requests(auto=True)

    def _status(self, text):
        self._last_lines = (self._last_lines + [text])[-50:]
        for target in (getattr(self.host, "scope_status_label", None),
                       getattr(getattr(self.host, "_performance_panel", None), "lbl_status", None)):
            try:
                if target is not None:
                    target.setText(text)
            except Exception:
                pass

    def _update_indicator(self):
        btn = getattr(self.host, "btn_media_hub", None)
        if btn is None:
            return
        if self._btn_style is None:
            self._btn_style = btn.styleSheet()
        n = self.pending_count()
        m = self.mgr
        live = m is not None and m.session is not None and m.session.active
        if n:
            pulse = int(time.time() * 2) % 2 == 0
            btn.setText(f"{_BTN_BASE_TEXT}\n📥 {n} Edit Together request{'s' if n > 1 else ''} — open to approve")
            btn.setStyleSheet(self._btn_style + (" QPushButton { border:3px solid #ffb703; background:#3a2a05; color:#ffe9a8; }"
                                                 if pulse else " QPushButton { border:3px solid #fb8500; }"))
        elif live:
            btn.setText(f"{_BTN_BASE_TEXT}\n🤝 Editing together · “{m.session.name}” v{m.session.version}")
            btn.setStyleSheet(self._btn_style + " QPushButton { border:3px solid #3bd18a; }")
        else:
            if btn.text() != _BTN_BASE_TEXT:
                btn.setText(_BTN_BASE_TEXT)
            btn.setStyleSheet(self._btn_style)

    # -------------------------------------------------------- user actions
    def start_with(self, members, name):
        m = self.mgr
        if m is None:
            raise RuntimeError("Nearby service unavailable")
        s = m.start(name, members, self.snapshot, self.apply)
        self._status(f"🤝 Edit Together “{name}” started — invites sent to {len(s.members)} Groovebox(es)")
        return s

    def request(self, peer):
        m = self.mgr
        if m is None:
            raise RuntimeError("Nearby service unavailable")
        ok = m.request(peer["node_id"])
        self._status(("🙋 Edit Together requested from " if ok else "Request could not reach ") + peer.get("name", "Groovebox"))
        return ok

    def leave(self):
        m = self.mgr
        if m is not None and m.session is not None:
            m.session.leave()
            self._status(f"Left “{m.session.name}”")

    def show_requests(self, parent=None, auto=False):
        """Approve / Deny dialog for every waiting invite and request."""
        m = self.mgr
        if m is None:
            return
        if not (m.pending_invites or m.pending_requests):
            if not auto:
                QMessageBox.information(parent or getattr(self.host, "_performance_panel", None) or self.host,
                                        "Edit Together requests", "No Edit Together requests or invites are waiting.")
            return
        parent = parent or getattr(self.host, "_performance_panel", None) or self.host
        dlg = QDialog(parent)
        dlg.setWindowTitle("Edit Together — requests & invites")
        dlg.resize(560, 360)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("<b>Approve</b> to edit the project together live, <b>Deny</b> to decline. "
                             "Approving an invite replaces your open project with the shared one (autosave keeps yours)."))
        lst = QListWidget(); lay.addWidget(lst, 1)

        def fill():
            lst.clear()
            for sid, p in m.pending_invites.items():
                it = QListWidgetItem(f"✉ Invite · {p.get('from_name', 'Groovebox')} invites you to edit “{p.get('name', 'project')}” "
                                     f"({len(p.get('members') or [])} member(s))")
                it.setData(256, ("invite", sid)); lst.addItem(it)
            for node, p in m.pending_requests.items():
                it = QListWidgetItem(f"🙋 Request · {p.get('from_name', 'Groovebox')} asks to edit your project together"
                                     + (f" — “{p.get('note')}”" if p.get("note") else ""))
                it.setData(256, ("request", node)); lst.addItem(it)
            if lst.count():
                lst.setCurrentRow(0)
            else:
                dlg.accept()

        def chosen():
            it = lst.currentItem()
            return it.data(256) if it is not None else None

        def approve():
            c = chosen()
            if not c:
                return
            kind, key = c
            try:
                if kind == "invite":
                    inv = m.pending_invites.get(key)
                    try:
                        self.host._autosave_project()        # keep the user's own project safe first
                    except Exception:
                        pass
                    m.join(inv, self.snapshot, self.apply)
                    self._status(f"🤝 Joined “{inv.get('name', 'shared project')}”")
                else:
                    import groovebox_paths
                    name = groovebox_paths.project_name(getattr(self.host, "_current_project_path", None))
                    m.approve_request(key, self.snapshot, self.apply, name=name)
                    self._status("🤝 Request approved — invite sent")
            except Exception as exc:
                QMessageBox.warning(dlg, "Edit Together", str(exc))
            fill()

        def deny():
            c = chosen()
            if not c:
                return
            m.deny(*c)
            self._status("Edit Together " + ("invite" if c[0] == "invite" else "request") + " denied")
            fill()

        br = QHBoxLayout()
        for text, fn in (("✅ Approve", approve), ("⛔ Deny", deny), ("Later", dlg.reject)):
            b = QPushButton(text); b.clicked.connect(fn); br.addWidget(b)
        lay.addLayout(br)
        fill()
        self._popup = dlg
        dlg.finished.connect(lambda *_: setattr(self, "_popup", None))
        dlg.setModal(False); dlg.show(); dlg.raise_()
        if auto:
            # Re-pop later only for requests that arrive after this dialog closes.
            pass
        return dlg


# GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103: no dialog may block other windows.
try:
    import nonmodal_dialogs as _gb_nonmodal
    _gb_nonmodal.install()
except Exception:
    pass
