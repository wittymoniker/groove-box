"""ui_panels.py — UI_PANES_R6: user pane formats for every Groovebox window.

Every pane in Groovebox scrolls on both axes, so any pane size is a valid layout: a format only has to say how
the panes of each window are arranged. Panes are found, not declared — the children of each QSplitter in a
window, plus the window's dock widgets.

Format (only what differs from the program's own layout is stored)::

    {"windows": {"<window key>": {
        "splitters": {"<splitter key>": {"orientation": "v" | "h",
                                         "order":  ["<pane key>", …],          # first = top / left
                                         "sizes":  {"<pane key>": fraction},   # of the splitter's length
                                         "hidden": ["<pane key>", …]}},
        "docks": {"<dock key>": {"area": "top|bottom|left|right|float", "visible": bool}}}}}

Keys are stable: objectName when set, else a position ("splitter#0", "pane#1") or the dock title folded to words.
The main window's key is "main". Rules: reversible ("Default" restores the program layout exactly, from what
was recorded on first touch); one pane per splitter always stays visible; built-in presets are read-only; user
presets live in <data dir>/ui_panels.json (UTF-8, atomic); imported files are sanitised.
"""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import weakref

AREAS = ("top", "bottom", "left", "right", "float")
MIN_FRACTION = 0.03

_MAIN_SPLIT = "grooveboxRenderSplitter"
_TOP, _BOTTOM = "grooveboxWorkstationScroll", "grooveboxVisualExportScroll"


def _main_split(**kw):
    return {"windows": {"main": {"splitters": {_MAIN_SPLIT: kw}}}}


BUILTIN = {
    "Default": {},
    "Workspace tall": _main_split(sizes={_TOP: 0.8, _BOTTOM: 0.2}),
    "Visuals tall": _main_split(sizes={_TOP: 0.3, _BOTTOM: 0.7}),
    "Side by side": _main_split(orientation="h", sizes={_TOP: 0.55, _BOTTOM: 0.45}),
    "Side by side · visuals left": _main_split(orientation="h", order=[_BOTTOM, _TOP], sizes={_TOP: 0.55, _BOTTOM: 0.45}),
    "Workspace only": _main_split(hidden=[_BOTTOM]),
    "Visuals only": _main_split(hidden=[_TOP]),
    "Deck on the left": {"windows": {"main": {"docks": {"*": {"area": "left"}}}}},
    "Deck hidden": {"windows": {"main": {"docks": {"*": {"visible": False}}}}},
}


# ------------------------------------------------------------------ store
def store_path() -> str:
    try:
        import groovebox_paths
        base = groovebox_paths.base_dir()
    except Exception:
        base = os.environ.get("GROOVEBOX_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".groovebox")
    return os.path.join(base, "ui_panels.json")


def clean_name(name) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip()[:60]


def load_store() -> dict:
    try:
        with open(store_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    presets = {}
    for name, fmt in (raw.get("presets") or {}).items() if isinstance(raw.get("presets"), dict) else ():
        name = clean_name(name)
        if name and name not in BUILTIN:
            presets[name] = sanitize(fmt)
    active = str(raw.get("active", "Default"))
    if active not in BUILTIN and active not in presets:
        active = "Default"
    return {"active": active, "presets": presets}


def save_store(store: dict) -> bool:
    path = store_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".ui_panels.", dir=os.path.dirname(path))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"active": store.get("active", "Default"), "presets": store.get("presets", {})}, fh,
                      indent=1, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def preset_names() -> list:
    return list(BUILTIN) + sorted(load_store()["presets"])


def is_builtin(name) -> bool:
    return name in BUILTIN


def get_preset(name) -> dict:
    if name in BUILTIN:
        return copy.deepcopy(BUILTIN[name])
    return copy.deepcopy(load_store()["presets"].get(name, {}))


def save_preset(name, fmt, make_active=True) -> str:
    name = clean_name(name)
    if not name:
        raise ValueError("a preset needs a name")
    if name in BUILTIN:
        raise ValueError(f"“{name}” is a built-in preset; save under another name")
    st = load_store()
    st["presets"][name] = sanitize(fmt)
    if make_active:
        st["active"] = name
    if not save_store(st):
        raise OSError("could not write " + store_path())
    return name


def delete_preset(name) -> bool:
    st = load_store()
    if name in BUILTIN or name not in st["presets"]:
        return False
    st["presets"].pop(name)
    if st["active"] == name:
        st["active"] = "Default"
    return save_store(st)


def set_active(name) -> None:
    st = load_store()
    st["active"] = name if (name in BUILTIN or name in st["presets"]) else "Default"
    save_store(st)


def active_name() -> str:
    return load_store()["active"]


def export_format(name, fmt, path) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"groovebox_ui_panes": 1, "name": name, "format": sanitize(fmt)}, fh, indent=1, ensure_ascii=False)
    return path


def import_preset(path) -> str:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    raw = raw if isinstance(raw, dict) else {}
    fmt = raw.get("format", raw)
    name = clean_name(raw.get("name")) or os.path.splitext(os.path.basename(path))[0]
    if name in BUILTIN:
        name += " (imported)"
    return save_preset(name, fmt)


# ------------------------------------------------------------------ validation
def _keylist(v):
    return [str(x)[:120] for x in v if isinstance(x, str) and x.strip()][:64] if isinstance(v, list) else []


def sanitize(fmt) -> dict:
    fmt = fmt if isinstance(fmt, dict) else {}
    wins = {}
    for wk, wv in (fmt.get("windows") or {}).items() if isinstance(fmt.get("windows"), dict) else ():
        if not isinstance(wv, dict):
            continue
        sp = {}
        for sk, sv in (wv.get("splitters") or {}).items() if isinstance(wv.get("splitters"), dict) else ():
            if not isinstance(sv, dict):
                continue
            e = {}
            if sv.get("orientation") in ("v", "h"):
                e["orientation"] = sv["orientation"]
            if _keylist(sv.get("order")):
                e["order"] = _keylist(sv["order"])
            sizes = {}
            for pk, f in (sv.get("sizes") or {}).items() if isinstance(sv.get("sizes"), dict) else ():
                try:
                    f = float(f)
                except (TypeError, ValueError):
                    continue
                if f == f and f > 0:
                    sizes[str(pk)[:120]] = max(MIN_FRACTION, min(1.0, f))
            if sizes:
                e["sizes"] = sizes
            if _keylist(sv.get("hidden")):
                e["hidden"] = _keylist(sv["hidden"])
            if e:
                sp[str(sk)[:120]] = e
        dk = {}
        for k, dv in (wv.get("docks") or {}).items() if isinstance(wv.get("docks"), dict) else ():
            if not isinstance(dv, dict):
                continue
            e = {}
            if dv.get("area") in AREAS:
                e["area"] = dv["area"]
            if "visible" in dv:
                e["visible"] = bool(dv["visible"])
            if e:
                dk[str(k)[:120]] = e
        w = {}
        if sp:
            w["splitters"] = sp
        if dk:
            w["docks"] = dk
        if w:
            wins[str(wk)[:120]] = w
    return {"windows": wins} if wins else {}


# ------------------------------------------------------------------ discovery
def _words(text) -> str:
    return " ".join(w.lower() for w in re.findall(r"[0-9A-Za-z]+", re.split(r"\s+[·—:|]\s+", str(text or ""))[0]))


def window_key(win) -> str:
    if type(win).__name__ == "MathematiciansGrooveboxApp":
        return "main"
    n = win.objectName()
    return n if n and not n.startswith("qt_") else type(win).__name__


def pane_label(w) -> str:
    for t in (w.accessibleName(), w.windowTitle(), w.toolTip()):
        if t and t.strip():
            return t.strip()[:60]
    try:
        from PyQt6.QtWidgets import QScrollArea, QGroupBox
        inner = w.widget() if isinstance(w, QScrollArea) else w
        if inner is not None:
            for b in inner.findChildren(QGroupBox):
                if b.title().strip():
                    return "pane with " + b.title().strip()[:44]
    except Exception:
        pass
    return w.objectName() or type(w).__name__


def splitters(win) -> list:
    """[(key, splitter)] owned by ``win`` (not by a nested top-level window)."""
    from PyQt6.QtWidgets import QSplitter
    out, i = [], 0
    for s in win.findChildren(QSplitter):
        if s.window() is not win:
            continue
        name = s.objectName()
        out.append((name if name and not name.startswith("qt_") else f"splitter#{i}", s))
        i += 1
    return out


def panes(split) -> list:
    """[(key, widget)] in the splitter's current order; keys survive reordering (recorded once)."""
    out = []
    for i in range(split.count()):
        w = split.widget(i)
        k = w.property("_uipKey")
        if not k:
            n = w.objectName()
            k = n if n and not n.startswith("qt_") else f"pane#{_orig_index(split, w, i)}"
            w.setProperty("_uipKey", k)
        out.append((str(k), w))
    return out


def _orig_index(split, w, i):
    order = split.property("_uipOrder")
    return order.index(id(w)) if isinstance(order, list) and id(w) in order else i


def docks(win) -> list:
    from PyQt6.QtWidgets import QDockWidget
    out, seen = [], {}
    for d in win.findChildren(QDockWidget):
        if d.parentWidget() is not win:
            continue
        base = d.objectName() if d.objectName() and not d.objectName().startswith("qt_") else (_words(d.windowTitle()) or "dock")
        n = seen.get(base, 0) + 1; seen[base] = n
        out.append((base if n == 1 else f"{base}#{n}", d))
    return out


def describe(win) -> dict:
    """What can be arranged in ``win``: {"key", "splitters": [{key, orientation, panes: [{key, label, size, shown}]}],
    "docks": [{key, title, area, visible}]}."""
    from PyQt6.QtCore import Qt
    res = {"key": window_key(win), "title": win.windowTitle(), "splitters": [], "docks": []}
    for sk, s in splitters(win):
        _remember_splitter(s)
        sizes = s.sizes(); tot = float(sum(sizes)) or 1.0
        res["splitters"].append({"key": sk, "orientation": "h" if s.orientation() == Qt.Orientation.Horizontal else "v",
                                 "panes": [{"key": pk, "label": pane_label(w), "size": sizes[i] / tot if i < len(sizes) else 0.0,
                                            "shown": not w.isHidden()} for i, (pk, w) in enumerate(panes(s))]})
    for dk, d in docks(win):
        res["docks"].append({"key": dk, "title": d.windowTitle(), "area": _dock_area(win, d), "visible": not d.isHidden()})
    return res


# ------------------------------------------------------------------ apply / reset
_AREA_QT = None


def _areas():
    global _AREA_QT
    if _AREA_QT is None:
        from PyQt6.QtCore import Qt
        A = Qt.DockWidgetArea
        _AREA_QT = {"top": A.TopDockWidgetArea, "bottom": A.BottomDockWidgetArea, "left": A.LeftDockWidgetArea,
                    "right": A.RightDockWidgetArea}
    return _AREA_QT


def _dock_area(win, d) -> str:
    if d.isFloating():
        return "float"
    try:
        a = win.dockWidgetArea(d)
        for k, v in _areas().items():
            if v == a:
                return k
    except Exception:
        pass
    return "top"


def _remember_splitter(s):
    if s.property("_uipOrig") is None:
        from PyQt6.QtCore import Qt
        s.setProperty("_uipOrig", True)
        s.setProperty("_uipOrient", "h" if s.orientation() == Qt.Orientation.Horizontal else "v")
        s.setProperty("_uipOrder", [id(s.widget(i)) for i in range(s.count())])
        s.setProperty("_uipSizes", [int(x) for x in s.sizes()])
        s.setProperty("_uipCollapsible", bool(s.childrenCollapsible()))
        s._uip_widgets = [weakref.ref(s.widget(i)) for i in range(s.count())]
        panes(s)                                   # fix the pane keys while the order is the original one


def _match(pattern, key):
    import fnmatch
    return pattern == key or (any(c in pattern for c in "*?[") and fnmatch.fnmatchcase(key, pattern))


def _entries(table, key):
    eff = {}
    for pat, e in (table or {}).items():
        if pat != key and _match(pat, key):
            eff.update(e)
    eff.update((table or {}).get(key, {}))
    return eff


def _restore_splitter(s):
    from PyQt6.QtCore import Qt
    if s.property("_uipOrig") is None:
        return
    s.setOrientation(Qt.Orientation.Horizontal if s.property("_uipOrient") == "h" else Qt.Orientation.Vertical)
    for i, ref in enumerate(getattr(s, "_uip_widgets", [])):
        w = ref()
        if w is not None and s.indexOf(w) >= 0 and s.indexOf(w) != i:
            s.insertWidget(i, w)
    for i in range(s.count()):
        w = s.widget(i)
        if bool(w.property("_uipHidden")):
            w.setProperty("_uipHidden", False); w.show()
    sizes = s.property("_uipSizes")
    if isinstance(sizes, list) and len(sizes) == s.count() and sum(sizes) > 0:
        s.setSizes([int(x) for x in sizes])
    s.setChildrenCollapsible(bool(s.property("_uipCollapsible")))


def apply_window(win, fmt) -> dict:
    """Arrange one window's panes. Returns {"window", "splitters", "panes", "hidden", "docks", "missing"}."""
    from PyQt6.QtCore import Qt
    fmt = sanitize(fmt)
    wk = window_key(win)
    wf = _entries(fmt.get("windows"), wk)
    rep = {"window": wk, "splitters": 0, "panes": 0, "hidden": 0, "docks": 0, "missing": []}
    found = splitters(win)
    for sk in (wf.get("splitters") or {}):
        if not any(_match(sk, k) for k, _ in found):
            rep["missing"].append(sk)
    for sk, s in found:
        _remember_splitter(s)
        _restore_splitter(s)                       # every apply starts from the program's own layout
        e = _entries(wf.get("splitters"), sk)
        if not e:
            continue
        rep["splitters"] += 1
        if "orientation" in e:
            s.setOrientation(Qt.Orientation.Horizontal if e["orientation"] == "h" else Qt.Orientation.Vertical)
        cur = dict(panes(s))
        order = [k for k in e.get("order", []) if k in cur]
        for i, k in enumerate(order + [k for k, _ in panes(s) if k not in order]):
            if s.indexOf(cur[k]) != i:
                s.insertWidget(i, cur[k])
        plist = panes(s)
        hidden = [k for k in e.get("hidden", []) if k in cur]
        if len(hidden) >= len(plist):              # one pane always stays
            hidden = hidden[:-1] if hidden else hidden
        for k, w in plist:
            if k in hidden and not w.isHidden():
                w.setProperty("_uipHidden", True); w.hide(); rep["hidden"] += 1
        if e.get("sizes"):
            # panes scroll on both axes, so any fraction is valid: let small fractions really be small
            s.setChildrenCollapsible(False)
            base = s.sizes(); tot = float(sum(base)) or 1.0
            weights = []
            for i, (k, w) in enumerate(plist):
                f = e["sizes"].get(k)
                weights.append(0 if w.isHidden() else int(10000 * (f if f is not None else (base[i] / tot if i < len(base) else 0.2))))
            if sum(weights) > 0:
                s.setSizes(weights)
        rep["panes"] += len(plist)
    for dk, d in docks(win):
        if d.property("_uipOrig") is None:
            d.setProperty("_uipOrig", True)
            d.setProperty("_uipArea", _dock_area(win, d))
            d.setProperty("_uipVis", not d.isHidden())
        e = _entries(wf.get("docks"), dk)
        area = e.get("area", d.property("_uipArea"))
        vis = e.get("visible", bool(d.property("_uipVis")))
        if area == "float":
            d.setFloating(True)
        else:
            if d.isFloating():
                d.setFloating(False)
            if hasattr(win, "addDockWidget") and _dock_area(win, d) != area:
                win.addDockWidget(_areas()[area], d)
        if vis != (not d.isHidden()):
            d.setVisible(vis)
        if e:
            rep["docks"] += 1
    win.setProperty("_uipApplied", True)
    return rep


def open_windows() -> list:
    from PyQt6.QtWidgets import QApplication
    out = []
    for w in QApplication.topLevelWidgets():
        try:
            if w.isWindow() and (w.isVisible() or type(w).__name__ == "MathematiciansGrooveboxApp") and \
                    not w.property("grooveboxExternalWindowStrip") and (splitters(w) or docks(w)):
                out.append(w)
        except RuntimeError:
            pass
    return out


def apply(fmt, windows=None) -> list:
    return [apply_window(w, fmt) for w in (windows if windows is not None else open_windows())]


def reset(windows=None) -> list:
    return apply({}, windows)


def capture(win) -> dict:
    """The window's arrangement as it is now, as a format fragment {"windows": {key: {...}}}."""
    d = describe(win)
    sp = {}
    for s in d["splitters"]:
        sp[s["key"]] = {"orientation": s["orientation"], "order": [p["key"] for p in s["panes"]],
                        "sizes": {p["key"]: round(max(MIN_FRACTION, p["size"]), 4) for p in s["panes"] if p["shown"]},
                        "hidden": [p["key"] for p in s["panes"] if not p["shown"]]}
        if not sp[s["key"]]["hidden"]:
            sp[s["key"]].pop("hidden")
    dk = {x["key"]: {"area": x["area"], "visible": x["visible"]} for x in d["docks"]}
    w = {}
    if sp:
        w["splitters"] = sp
    if dk:
        w["docks"] = dk
    return sanitize({"windows": {d["key"]: w}}) if w else {}


def merge(fmt, fragment) -> dict:
    out = copy.deepcopy(sanitize(fmt))
    for wk, wv in (sanitize(fragment).get("windows") or {}).items():
        out.setdefault("windows", {})[wk] = wv
    return out


# ------------------------------------------------------------------ startup + windows opened later
_FILTER = {"obj": None}


def apply_active(win=None) -> dict:
    """Apply the active preset now (to ``win`` or every open window) and to Groovebox windows opened later."""
    name = active_name()
    fmt = get_preset(name)
    _install_show_hook()
    if not fmt:
        return {"preset": name, "windows": []}
    return {"preset": name, "windows": apply(fmt, [win] if win is not None else None)}


def _install_show_hook():
    if _FILTER["obj"] is not None:
        return
    from PyQt6.QtCore import QObject, QEvent
    from PyQt6.QtWidgets import QApplication, QWidget
    qa = QApplication.instance()
    if qa is None:
        return

    class _ShowHook(QObject):
        """A window that appears later gets the active pane format once (per window instance)."""
        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow() \
                    and obj.property("_uipApplied") is None and not obj.property("grooveboxExternalWindowStrip"):
                obj.setProperty("_uipApplied", False)
                try:
                    fmt = get_preset(active_name())
                    wins = (fmt or {}).get("windows") or {}
                    if wins and any(_match(k, window_key(obj)) for k in wins):
                        apply_window(obj, fmt)
                except Exception:
                    pass
            return False
    _FILTER["obj"] = _ShowHook(qa)
    qa.installEventFilter(_FILTER["obj"])
