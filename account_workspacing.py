"""account_workspacing.py — R138

Per-account *workspacing*: workspace-local scripted environment, overlay session
save/restore, and shortcut procedures.

Each account owns a workspaces/ tree under its data folder::

    <account data>/workspaces/
        active.json                 # which workspace is current
        <ws_id>/
            meta.json               # name, emoji, created, shortcuts
            overlays.json           # saved workspace_overlays snapshot
            session.json            # window/session snapshot (best-effort)
            env.json                # scripted environment overlay (vars, paths)
            scripts/                # local scripts (*.py, *.sC, *.lua)
            shortcuts.json          # named procedures → action lists

API (scripts / UI / accounts)::

    import account_workspacing as aw
    aw.ensure(acc)
    aw.create(acc, "Live set")
    aw.activate(acc, ws_id, app=app)
    aw.save_session(acc, app)
    aw.run_shortcut(acc, "open-fractal-lab", app)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

SCHEMA = 1


def _acc_root(acc: Optional[dict] = None) -> Path:
    import accounts
    a = acc or accounts.current()
    root = accounts.folder_of(a)
    p = Path(root) / "workspaces"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ws_dir(acc: Optional[dict], ws_id: str) -> Path:
    d = _acc_root(acc) / str(ws_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "scripts").mkdir(exist_ok=True)
    return d


def _read(path: Path, default):
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def ensure(acc: Optional[dict] = None) -> dict:
    """Guarantee a default workspace exists; return active meta."""
    root = _acc_root(acc)
    active = _read(root / "active.json", {})
    if not active.get("id") or not (_ws_dir(acc, active["id"]) / "meta.json").is_file():
        meta = create(acc, "Default", emoji="🗂")
        active = {"id": meta["id"], "switched": time.time()}
        _write(root / "active.json", active)
    return active


def list_workspaces(acc: Optional[dict] = None) -> List[dict]:
    root = _acc_root(acc)
    out = []
    for child in sorted(root.iterdir() if root.is_dir() else []):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta = _read(child / "meta.json", None)
        if isinstance(meta, dict) and meta.get("id"):
            out.append(meta)
    return out


def create(acc: Optional[dict] = None, name: str = "Workspace", *, emoji: str = "🗂",
           clone_from: Optional[str] = None) -> dict:
    ws_id = uuid.uuid4().hex[:12]
    d = _ws_dir(acc, ws_id)
    meta = {
        "schema": SCHEMA,
        "id": ws_id,
        "name": str(name or "Workspace")[:64],
        "emoji": str(emoji or "🗂")[:4],
        "created": time.time(),
        "updated": time.time(),
        "shortcuts": {},
    }
    if clone_from:
        src = _ws_dir(acc, clone_from)
        for fname in ("overlays.json", "session.json", "env.json", "shortcuts.json"):
            data = _read(src / fname, None)
            if data is not None:
                _write(d / fname, data)
        meta["cloned_from"] = clone_from
    _write(d / "meta.json", meta)
    _write(d / "env.json", _default_env())
    _write(d / "shortcuts.json", _default_shortcuts())
    _write(d / "overlays.json", {})
    _write(d / "session.json", {})
    # first workspace becomes active if none
    root = _acc_root(acc)
    active = _read(root / "active.json", {})
    if not active.get("id"):
        _write(root / "active.json", {"id": ws_id, "switched": time.time()})
    return meta


def _default_env() -> dict:
    return {
        "schema": SCHEMA,
        "env": {
            "GROOVEBOX_WORKSPACE_SCRIPT": "1",
            "GROOVEBOX_OVERLAY_SESSION": "1",
        },
        "pythonpath_extra": [],
        "script_autoload": [],
        "notes": "",
    }


def _default_shortcuts() -> dict:
    return {
        "schema": SCHEMA,
        "procedures": {
            "open-fractal-lab": {
                "label": "Fractal lab",
                "steps": [
                    {"module": "fractal_studio_gui", "call": "open_window"},
                ],
            },
            "open-mod-matrix": {
                "label": "Mod Matrix",
                "steps": [
                    {"module": "mod_matrix", "call": "open_window"},
                ],
            },
            "save-session": {
                "label": "Save workspace session",
                "steps": [
                    {"action": "save_session"},
                ],
            },
            "carrier-generator": {
                "label": "Carrier · generator snapshot",
                "steps": [
                    {"action": "carrier_snapshot"},
                ],
            },
        },
    }


def get_meta(acc: Optional[dict], ws_id: str) -> dict:
    return _read(_ws_dir(acc, ws_id) / "meta.json", {})


def rename(acc: Optional[dict], ws_id: str, name: str) -> dict:
    meta = get_meta(acc, ws_id)
    if not meta:
        raise KeyError(ws_id)
    meta["name"] = str(name)[:64]
    meta["updated"] = time.time()
    _write(_ws_dir(acc, ws_id) / "meta.json", meta)
    return meta


def delete(acc: Optional[dict], ws_id: str) -> bool:
    import shutil
    root = _acc_root(acc)
    active = _read(root / "active.json", {})
    d = root / str(ws_id)
    if not d.is_dir():
        return False
    shutil.rmtree(d, ignore_errors=True)
    if active.get("id") == ws_id:
        remaining = list_workspaces(acc)
        if remaining:
            _write(root / "active.json", {"id": remaining[0]["id"], "switched": time.time()})
        else:
            ensure(acc)
    return True


def active_id(acc: Optional[dict] = None) -> str:
    return str(ensure(acc).get("id") or "")


def activate(acc: Optional[dict], ws_id: str, app=None, *, apply_overlays: bool = True,
             apply_env: bool = True, restore_session: bool = True) -> dict:
    """Make workspace current: env overlay, overlays, optional session restore."""
    meta = get_meta(acc, ws_id)
    if not meta:
        raise KeyError(ws_id)
    _write(_acc_root(acc) / "active.json", {"id": ws_id, "switched": time.time()})
    d = _ws_dir(acc, ws_id)
    if apply_env:
        apply_environment(acc, ws_id)
    if apply_overlays and app is not None:
        try:
            import workspace_overlays as wo
            snap = _read(d / "overlays.json", {})
            if isinstance(snap, dict) and snap.get("name"):
                # re-apply a named overlay if present in the global store
                wo.apply(app, snap["name"])
            elif isinstance(snap, dict) and snap.get("tools"):
                # ad-hoc tool list
                for mod, fn in snap.get("tools") or []:
                    try:
                        wo._open_tool(app, mod, fn)
                    except Exception:
                        pass
        except Exception:
            pass
    if restore_session and app is not None:
        restore_session_state(acc, ws_id, app)
    return meta


def apply_environment(acc: Optional[dict], ws_id: Optional[str] = None) -> dict:
    """Push workspace env.json into process environment (scripted local overlay)."""
    ws_id = ws_id or active_id(acc)
    env_doc = _read(_ws_dir(acc, ws_id) / "env.json", _default_env())
    for k, v in (env_doc.get("env") or {}).items():
        if v is None:
            os.environ.pop(str(k), None)
        else:
            os.environ[str(k)] = str(v)
    os.environ["GROOVEBOX_WORKSPACE_ID"] = str(ws_id)
    os.environ["GROOVEBOX_WORKSPACE_ROOT"] = str(_ws_dir(acc, ws_id))
    extra = env_doc.get("pythonpath_extra") or []
    if extra:
        parts = [str(p) for p in extra if p]
        cur = os.environ.get("PYTHONPATH", "")
        os.environ["PYTHONPATH"] = os.pathsep.join(parts + ([cur] if cur else []))
    for rel in env_doc.get("script_autoload") or []:
        run_local_script(acc, ws_id, rel)
    return env_doc


def set_env(acc: Optional[dict], key: str, value: Any, ws_id: Optional[str] = None) -> dict:
    ws_id = ws_id or active_id(acc)
    doc = _read(_ws_dir(acc, ws_id) / "env.json", _default_env())
    doc.setdefault("env", {})[str(key)] = value
    _write(_ws_dir(acc, ws_id) / "env.json", doc)
    if value is None:
        os.environ.pop(str(key), None)
    else:
        os.environ[str(key)] = str(value)
    return doc


def save_session(acc: Optional[dict], app, ws_id: Optional[str] = None) -> dict:
    """Best-effort session snapshot: geometry hints, open overlay name, carrier routes, seed."""
    ws_id = ws_id or active_id(acc)
    d = _ws_dir(acc, ws_id)
    snap: Dict[str, Any] = {
        "schema": SCHEMA,
        "saved_at": time.time(),
        "seed": None,
        "bpm": None,
        "overlay": None,
        "carrier_routes": None,
        "window": {},
    }
    try:
        if hasattr(app, "_seed_text"):
            snap["seed"] = str(app._seed_text())[:4000]
        elif hasattr(app, "input_seed_val"):
            snap["seed"] = str(app.input_seed_val.toPlainText())[:4000]
    except Exception:
        pass
    try:
        snap["bpm"] = float(app.spin_bpm.value())
    except Exception:
        pass
    try:
        import workspace_overlays as wo
        # remember last applied overlay name if host tracks it
        snap["overlay"] = getattr(app, "_workspace_overlay_name", None)
        wo_snap = wo.saved()
        if snap["overlay"] and snap["overlay"] in wo_snap:
            _write(d / "overlays.json", {"name": snap["overlay"], **(wo_snap.get(snap["overlay"]) or {})})
        elif snap["overlay"]:
            _write(d / "overlays.json", {"name": snap["overlay"]})
    except Exception:
        pass
    try:
        import carrier_generator_path as cgp
        snap["carrier_routes"] = cgp.snapshot(app)
    except Exception:
        pass
    try:
        geo = app.saveGeometry()
        if geo is not None:
            snap["window"]["geometry_b64"] = bytes(geo.toHex()).decode("ascii")
    except Exception:
        pass
    try:
        snap["window"]["title"] = str(app.windowTitle())
    except Exception:
        pass
    _write(d / "session.json", snap)
    meta = get_meta(acc, ws_id)
    if meta:
        meta["updated"] = time.time()
        meta["last_session"] = snap["saved_at"]
        _write(d / "meta.json", meta)
    return snap


def restore_session_state(acc: Optional[dict], ws_id: str, app) -> dict:
    snap = _read(_ws_dir(acc, ws_id) / "session.json", {})
    if not snap:
        return {}
    try:
        if snap.get("seed") and hasattr(app, "input_seed_val"):
            app.input_seed_val.setPlainText(str(snap["seed"]))
    except Exception:
        pass
    try:
        if snap.get("bpm") is not None and hasattr(app, "spin_bpm"):
            app.spin_bpm.setValue(float(snap["bpm"]))
    except Exception:
        pass
    try:
        if snap.get("carrier_routes"):
            import carrier_generator_path as cgp
            cgp.restore(app, snap["carrier_routes"])
    except Exception:
        pass
    try:
        geo = (snap.get("window") or {}).get("geometry_b64")
        if geo:
            from PyQt6.QtCore import QByteArray
            app.restoreGeometry(QByteArray.fromHex(geo.encode("ascii")))
    except Exception:
        pass
    return snap


def save_overlay_session(acc: Optional[dict], app, name: str, ws_id: Optional[str] = None) -> dict:
    """Capture current overlay layout under the workspace and the global overlay store."""
    ws_id = ws_id or active_id(acc)
    try:
        import workspace_overlays as wo
        wo.save_current(app, name)
        app._workspace_overlay_name = name
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    doc = {"name": name, "saved_at": time.time()}
    _write(_ws_dir(acc, ws_id) / "overlays.json", doc)
    save_session(acc, app, ws_id)
    return {"ok": True, **doc}


def list_shortcuts(acc: Optional[dict] = None, ws_id: Optional[str] = None) -> Dict[str, dict]:
    ws_id = ws_id or active_id(acc)
    doc = _read(_ws_dir(acc, ws_id) / "shortcuts.json", _default_shortcuts())
    return dict(doc.get("procedures") or {})


def set_shortcut(acc: Optional[dict], key: str, label: str, steps: Sequence[dict],
                 ws_id: Optional[str] = None) -> dict:
    ws_id = ws_id or active_id(acc)
    doc = _read(_ws_dir(acc, ws_id) / "shortcuts.json", _default_shortcuts())
    doc.setdefault("procedures", {})[str(key)] = {"label": str(label)[:64], "steps": list(steps)}
    _write(_ws_dir(acc, ws_id) / "shortcuts.json", doc)
    return doc["procedures"][str(key)]


def run_shortcut(acc: Optional[dict], key: str, app=None, ws_id: Optional[str] = None) -> List[str]:
    """Execute a named procedure; returns log lines."""
    ws_id = ws_id or active_id(acc)
    procs = list_shortcuts(acc, ws_id)
    proc = procs.get(str(key))
    if not proc:
        return [f"unknown shortcut: {key}"]
    log: List[str] = []
    for step in proc.get("steps") or []:
        try:
            if "action" in step:
                act = step["action"]
                if act == "save_session" and app is not None:
                    save_session(acc, app, ws_id); log.append("session saved")
                elif act == "save_overlay" and app is not None:
                    save_overlay_session(acc, app, step.get("name") or "quick", ws_id); log.append("overlay saved")
                elif act == "carrier_snapshot" and app is not None:
                    import carrier_generator_path as cgp
                    snap = cgp.snapshot(app)
                    _write(_ws_dir(acc, ws_id) / "carrier_snapshot.json", snap)
                    log.append("carrier snapshot")
                elif act == "activate_workspace":
                    activate(acc, step.get("id") or ws_id, app=app); log.append("workspace activated")
                else:
                    log.append(f"skip action {act}")
            elif "module" in step:
                import importlib
                mod = importlib.import_module(str(step["module"]))
                fn = getattr(mod, str(step.get("call") or "open_window"))
                if app is not None:
                    fn(app)
                else:
                    fn()
                log.append(f"{step['module']}.{step.get('call')}")
            elif "script" in step:
                run_local_script(acc, ws_id, step["script"], app=app)
                log.append(f"script {step['script']}")
        except Exception as exc:
            log.append(f"error: {exc}")
    return log


def run_local_script(acc: Optional[dict], ws_id: str, rel: str, app=None) -> Any:
    """Run a workspace-local script (*.py). Restricted: no shell, path must stay under scripts/."""
    base = (_ws_dir(acc, ws_id) / "scripts").resolve()
    path = (base / rel).resolve()
    if not str(path).startswith(str(base)) or not path.is_file():
        raise FileNotFoundError(rel)
    if path.suffix.lower() != ".py":
        raise ValueError("only .py scripts in workspaces/scripts for now")
    ns = {"app": app, "__name__": "__workspace_script__", "WORKSPACE": str(_ws_dir(acc, ws_id))}
    code = path.read_text(encoding="utf-8")
    exec(compile(code, str(path), "exec"), ns, ns)  # noqa: S102 — intentional local workspace script
    return ns.get("result")


def write_script(acc: Optional[dict], rel: str, source: str, ws_id: Optional[str] = None) -> str:
    ws_id = ws_id or active_id(acc)
    base = _ws_dir(acc, ws_id) / "scripts"
    path = (base / rel).resolve()
    if not str(path).startswith(str(base.resolve())):
        raise ValueError("path escapes scripts/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return str(path)


# ── accounts integration helpers ─────────────────────────────────────────────

def workspacing(acc: Optional[dict] = None) -> dict:
    """Account-facing summary: active workspace, list, env, shortcut keys."""
    import accounts
    a = acc or accounts.current()
    ensure(a)
    aid = active_id(a)
    return {
        "account_id": a.get("id"),
        "account_name": a.get("name"),
        "active": aid,
        "meta": get_meta(a, aid),
        "workspaces": list_workspaces(a),
        "shortcuts": list(list_shortcuts(a, aid).keys()),
        "env": _read(_ws_dir(a, aid) / "env.json", _default_env()),
        "root": str(_ws_dir(a, aid)),
    }
