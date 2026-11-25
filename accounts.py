"""accounts.py: Groovebox user accounts.

Accounts live in <data root>/accounts/accounts.json (atomic saves). Each account:
    id · name · emoji · colour · role · optional password (salted PBKDF2-SHA256, never stored in clear) ·
    created · last_login · data folder
Roles and what they may do:
    owner   everything (administrator commands, drive formatting, installs, network publishing, accounts)
    member  everything except administrator commands, drive formatting and managing accounts
    child   create, play and export; no installs, no network publishing, no administrator commands
    guest   create and play in a temporary folder; nothing is installed, published or kept system-wide
Every account has its own data folder (projects, settings, exports, plugins' outputs): GROOVEBOX_DATA_DIR is set
to it before the main window is built. The first owner keeps the original folder, so existing work never moves.
Sign-in appears at start when there is more than one account or the account has a password. Switch user saves
the session and relaunches into the other account (every module then sees the same folder from the start).

This protects people's work from each other on a shared machine; it is not disk encryption.
"""
from __future__ import annotations
import hashlib
import hmac
import os
import sys
import time
import uuid

ROLES = ("owner", "member", "child", "guest")
PERMS = {
    "admin":    {"owner"},
    "format":   {"owner"},
    "accounts": {"owner"},
    "install":  {"owner", "member"},
    "publish":  {"owner", "member"},
    "network":  {"owner", "member", "child"},
    "create":   {"owner", "member", "child", "guest"},
}
ITER = 200_000
_CURRENT = {"acc": None}


def _base_root():
    """The original data root (before any account folder override)."""
    b = os.environ.get("GROOVEBOX_BASE_DATA_DIR")
    if b:
        return b
    import groovebox_paths
    root = str(groovebox_paths._data_root())
    os.environ["GROOVEBOX_BASE_DATA_DIR"] = root
    return root


def _file():
    d = os.path.join(_base_root(), "accounts"); os.makedirs(d, exist_ok=True)
    return os.path.join(d, "accounts.json")


def load():
    import safe_io
    d = safe_io.read_json(_file(), None)
    if not isinstance(d, dict) or not d.get("accounts"):
        name = os.environ.get("USER") or os.environ.get("USERNAME") or "Owner"
        d = {"version": 1, "accounts": [{"id": "owner", "name": name.capitalize(), "emoji": "🎛", "colour": "#7fd6ee",
                                          "role": "owner", "created": time.time(), "last_login": 0, "folder": ""}],
             "last": "owner"}
        save(d)
    return d


def save(d):
    import safe_io
    safe_io.atomic_write_json(_file(), d, indent=1)


def folder_of(acc):
    """The account's data folder ('' = the original root for the first owner)."""
    if acc.get("role") == "guest":
        import tempfile
        return os.path.join(tempfile.gettempdir(), "groovebox-guest-%s" % acc["id"])
    if not acc.get("folder"):
        return _base_root()
    return os.path.join(_base_root(), "users", acc["folder"])


def _hash(pw, salt=None):
    salt = bytes.fromhex(salt) if salt else os.urandom(16)
    return salt.hex(), hashlib.pbkdf2_hmac("sha256", str(pw).encode("utf-8"), salt, ITER).hex()


def set_password(acc, pw):
    if pw:
        acc["pw_salt"], acc["pw_hash"] = _hash(pw)
    else:
        acc.pop("pw_salt", None); acc.pop("pw_hash", None)


def check_password(acc, pw):
    if not acc.get("pw_hash"):
        return True
    return hmac.compare_digest(_hash(pw or "", acc.get("pw_salt"))[1], acc["pw_hash"])


def current():
    acc = _CURRENT["acc"]
    if acc is None:
        want = os.environ.get("GROOVEBOX_ACCOUNT")
        d = load()
        acc = next((a for a in d["accounts"] if a["id"] == want), None) or \
            next((a for a in d["accounts"] if a["id"] == d.get("last")), d["accounts"][0])
        _CURRENT["acc"] = acc
    return acc



def workspacing(acc=None):
    """Per-account workspacing: local scripted env, overlay sessions, shortcut procedures.

    Returns a summary dict for the active workspace. See account_workspacing for the
    full API (create, activate, save_session, run_shortcut, …).
    """
    import account_workspacing as aw
    return aw.workspacing(acc or current())


def save_workspace_session(app, acc=None):
    """Shortcut: save overlay + session into the account's active workspace."""
    import account_workspacing as aw
    a = acc or current()
    aw.ensure(a)
    return aw.save_session(a, app)


def run_workspace_shortcut(key, app=None, acc=None):
    """Run a named workspace procedure (see account_workspacing.list_shortcuts)."""
    import account_workspacing as aw
    a = acc or current()
    aw.ensure(a)
    return aw.run_shortcut(a, key, app=app)

def allowed(action):
    try:
        return current().get("role", "owner") in PERMS.get(action, {"owner"})
    except Exception:
        return True                       # accounts unavailable: behave like the single-owner Groovebox


def require(action, what=""):
    if not allowed(action):
        a = current()
        raise PermissionError("%s (%s) may not %s%s" % (a.get("name"), a.get("role"), {"admin": "run administrator commands",
                              "format": "format drives", "accounts": "manage accounts", "install": "install software",
                              "publish": "publish to the network", "network": "use the network"}.get(action, action),
                              (": " + what) if what else ""))


def activate(acc):
    """Point every Groovebox path at this account's folder (call before the main window is built)."""
    d = load(); acc["last_login"] = time.time(); d["last"] = acc["id"]
    for i, a in enumerate(d["accounts"]):
        if a["id"] == acc["id"]:
            d["accounts"][i] = acc
    save(d)
    folder = folder_of(acc); os.makedirs(folder, exist_ok=True)
    os.environ["GROOVEBOX_DATA_DIR"] = folder
    os.environ["GROOVEBOX_ACCOUNT"] = acc["id"]
    os.environ["GROOVEBOX_USER_NAME"] = acc.get("name", "")
    try:
        import groovebox_paths
        groovebox_paths._ROOT_DONE.clear()
    except Exception:
        pass
    _CURRENT["acc"] = acc
    return folder


def add(name, role="member", emoji="🎵", colour="#a0e0ff", pw=""):
    require("accounts")
    if role not in ROLES:
        raise ValueError("role must be one of %s" % ", ".join(ROLES))
    d = load(); aid = uuid.uuid4().hex[:10]
    acc = {"id": aid, "name": str(name)[:40] or "User", "emoji": emoji, "colour": colour, "role": role,
           "created": time.time(), "last_login": 0, "folder": "" if False else aid}
    set_password(acc, pw); d["accounts"].append(acc); save(d)
    return acc


def update(aid, **fields):
    d = load(); acc = next(a for a in d["accounts"] if a["id"] == aid)
    if aid != current()["id"]:
        require("accounts")
    if "role" in fields:
        require("accounts")
        owners = [a for a in d["accounts"] if a["role"] == "owner" and a["id"] != aid]
        if acc["role"] == "owner" and fields["role"] != "owner" and not owners:
            raise PermissionError("the last owner cannot be demoted")
    if "password" in fields:
        set_password(acc, fields.pop("password"))
    acc.update({k: v for k, v in fields.items() if k in ("name", "emoji", "colour", "role")})
    save(d); return acc


def remove(aid):
    require("accounts")
    d = load(); acc = next(a for a in d["accounts"] if a["id"] == aid)
    if acc["role"] == "owner" and len([a for a in d["accounts"] if a["role"] == "owner"]) == 1:
        raise PermissionError("the last owner cannot be removed")
    if aid == current()["id"]:
        raise PermissionError("sign in as someone else to remove this account")
    d["accounts"] = [a for a in d["accounts"] if a["id"] != aid]; save(d)
    return "removed %s (their folder is kept: %s)" % (acc["name"], folder_of(acc))


def needs_sign_in():
    d = load()
    return len(d["accounts"]) > 1 or any(a.get("pw_hash") for a in d["accounts"])


# ------------------------------------------------------------------ UI
def sign_in(parent=None):
    """Blocking sign-in at start (before the main window). Returns the chosen account (never None)."""
    d = load()
    if os.environ.get("GROOVEBOX_ACCOUNT"):
        acc = next((a for a in d["accounts"] if a["id"] == os.environ["GROOVEBOX_ACCOUNT"]), None)
        if acc is not None and not acc.get("pw_hash"):
            return acc
    if not needs_sign_in():
        return d["accounts"][0]
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QButtonGroup, QGridLayout)
    dlg = QDialog(parent); dlg.setWindowTitle("Mathematician's Groovebox · Sign in"); dlg.resize(560, 360)
    dlg.setStyleSheet("QDialog{background:#0b141c;} QLabel{color:#cfeeff;} QLineEdit{background:#132634;color:#fff;border:1px solid #2f5d74;"
                      "border-radius:6px;padding:6px;} QPushButton{color:#eaf8ff;border-radius:10px;padding:10px;font-weight:800;}")
    v = QVBoxLayout(dlg); v.addWidget(QLabel("Who is making music?"))
    grid = QGridLayout(); v.addLayout(grid); grp = QButtonGroup(dlg); grp.setExclusive(True)
    pick = {"acc": next((a for a in d["accounts"] if a["id"] == d.get("last")), d["accounts"][0])}
    for i, a in enumerate(d["accounts"]):
        b = QPushButton("%s\n%s · %s" % (a.get("emoji", "🎵"), a.get("name"), a.get("role"))); b.setCheckable(True)
        b.setStyleSheet("QPushButton{background:rgba(20,40,56,220);border:2px solid %s;} QPushButton:checked{background:%s;color:#081018;}"
                        % (a.get("colour", "#7fd6ee"), a.get("colour", "#7fd6ee")))
        b.setChecked(a is pick["acc"]); grp.addButton(b); grid.addWidget(b, i // 3, i % 3)
        b.clicked.connect(lambda _=False, a=a: (pick.__setitem__("acc", a), pw.setVisible(bool(a.get("pw_hash"))), pw.setFocus()))
    pw = QLineEdit(); pw.setEchoMode(QLineEdit.EchoMode.Password); pw.setPlaceholderText("password")
    pw.setVisible(bool(pick["acc"].get("pw_hash"))); v.addWidget(pw)
    msg = QLabel(""); v.addWidget(msg)
    row = QHBoxLayout(); v.addLayout(row)
    ok = QPushButton("Sign in"); ok.setStyleSheet("background:#1f6f8b;"); row.addStretch(1); row.addWidget(ok)
    tries = {"n": 0}

    def go():
        a = pick["acc"]
        if check_password(a, pw.text()):
            dlg.accept(); return
        tries["n"] += 1; pw.clear(); msg.setText("wrong password"); ok.setEnabled(False)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(min(30000, 500 * 2 ** tries["n"]), lambda: ok.setEnabled(True))   # back-off, never sleep
    ok.clicked.connect(go); pw.returnPressed.connect(go)
    while True:
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return pick["acc"]
        guest = next((a for a in d["accounts"] if a["role"] == "guest"), None)   # closing = guest if one exists
        if guest is not None:
            return guest


def switch_user(app):
    """Save the session and relaunch Groovebox; the sign-in screen opens first."""
    try:
        __import__("session_snapshot").save(app)
    except Exception:
        pass
    os.environ.pop("GROOVEBOX_ACCOUNT", None); os.environ.pop("GROOVEBOX_DATA_DIR", None)
    os.environ["GROOVEBOX_FORCE_SIGN_IN"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)


def open_window(app):
    import manage_windows as mw
    d = {"x": None}

    def gather():
        acc = current()
        return [("%s %s" % (a.get("emoji", ""), a.get("name")), a.get("role"), "password" if a.get("pw_hash") else "—",
                 time.strftime("%Y-%m-%d %H:%M", time.localtime(a.get("last_login") or 0)) if a.get("last_login") else "never",
                 folder_of(a), "● signed in" if a["id"] == acc["id"] else "", a["id"]) for a in load()["accounts"]]

    def ask(title, label, text="", pw=False):
        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        t, ok = QInputDialog.getText(app, title, label, QLineEdit.EchoMode.Password if pw else QLineEdit.EchoMode.Normal, text)
        return t if ok else None

    @mw.no_row
    def new(_r):
        from PyQt6.QtWidgets import QInputDialog
        name = ask("New account", "Name:")
        if not name: return None
        role, ok = QInputDialog.getItem(app, "New account", "Role:", list(ROLES[1:]) + ["owner"], 0, False)
        if not ok: return None
        pw = ask("New account", "Password (empty = none):", pw=True) or ""
        a = add(name, role, pw=pw); return "added %s (%s)" % (a["name"], a["role"])

    def rename(r):
        n = ask("Rename", "Name:", r[0].split(" ", 1)[-1])
        return n and (update(r[6], name=n) and "renamed")

    def role(r):
        from PyQt6.QtWidgets import QInputDialog
        ro, ok = QInputDialog.getItem(app, "Role", "Role:", list(ROLES), ROLES.index(r[1]), False)
        return ok and (update(r[6], role=ro) and "role set to %s" % ro)

    def password(r):
        pw = ask("Password", "New password (empty = remove):", pw=True)
        return pw is not None and (update(r[6], password=pw) and ("password set" if pw else "password removed"))

    def emoji(r):
        e = ask("Emoji", "Emoji:", r[0].split(" ", 1)[0])
        return e and (update(r[6], emoji=e[:2]) and "emoji set")

    def delete(r):
        return remove(r[6])

    @mw.no_row
    def switch(_r):
        switch_user(app)
    return mw.open_table(app, "accounts", "👤 Accounts", ("account", "role", "sign-in", "last sign-in", "data folder", ""), gather,
                         (("＋ New…", new), ("Rename", rename), ("Role", role), ("Password", password), ("Emoji", emoji),
                          ("✖ Remove", delete), ("⇄ Switch user", switch)), 0,
                         note="Each account keeps its own projects, settings and exports. Roles: owner (everything) · member "
                              "(no admin / format / accounts) · child (no installs or publishing) · guest (temporary folder). "
                              "This protects people's work from each other; it is not disk encryption.")
