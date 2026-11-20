"""patch_bay_sync.py — GROOVEBOX_R123_PATCH_BAY_IS_PROJECT_STATE_20261119

The Advanced Modular Patch Bay used to keep its cables only in its own QListWidget: they were lost when the
window was rebuilt, never saved with the project, invisible to the render/Mod Matrix (`patch:<instrument>`
sources read app.patch_connections) and invisible to the randomizers. Now the window is a live view of
app.patch_connections — the same list Configure Entire Project, the additive Patch Bay Optimizer, per-sequence
panels, project save/load and undo already use:

  Connect     appends {"source", "target", "weight", "curve", "polarity", "normalize", "origin": "patch_bay",
              "user_defined": True}; a duplicate source→target edge updates the existing cable instead
  Select      loads that cable's settings into the Cable Settings row; editing them updates the cable
  Remove      removes the selected cable; Clear removes every cable (one undo step)
  Randomize   route-aware: serves instruments that have no input first, prefers instruments that play, never
              duplicates an edge or patches an instrument into itself; same seed + same patch → same result
  Refresh     every 600 ms the list re-reads app.patch_connections, so cables written elsewhere appear here
"""
from __future__ import annotations

import hashlib

CURVES = ("Linear", "Exponential", "Logarithmic", "S-Curve", "Step-Quantized")
POLARITIES = ("Unipolar +", "Bipolar ±", "Inverted −")


def _cables(app):
    c = getattr(app, "patch_connections", None)
    if not isinstance(c, list):
        c = app.patch_connections = []
    return c


def _strip(text, suffix):
    t = str(text or "")
    return t[: -len(suffix)] if t.endswith(suffix) else t


def label(c):
    tgt = str(c.get("target", ""))
    tgt_l = tgt if tgt in ("PKP Envelope Follower Bus", "Geometric Resonance Nullifier Core") else tgt + " In"
    return "%s Out ==[%s, %s, depth %.2f%s]==> %s%s" % (
        c.get("source", "?"), c.get("curve", "Linear"), c.get("polarity", "Unipolar +"),
        float(c.get("weight", 1.0) or 0.0), ", norm" if c.get("normalize", True) else "", tgt_l,
        "" if c.get("user_defined", True) else "   · " + str(c.get("origin", "generated")))


def _sig(app):
    return tuple((c.get("source"), c.get("target"), round(float(c.get("weight", 1.0) or 0.0), 4), c.get("curve"),
                  c.get("polarity"), c.get("normalize")) for c in _cables(app) if isinstance(c, dict))


def _undo(app, what):
    try:
        if not getattr(app, "_undo_in_flight", False):
            app._push_undo(what)
    except Exception:
        pass


def _changed(app):
    try:
        app._shared_mixdown_cache = {}
        app._invalidate_shared_mixdown()
    except Exception:
        pass
    try:
        app._sync_project_state()
    except Exception:
        pass
    refresh_open_views(app)


def bind(app, w):
    """w: dict of the patch bay widgets (source, target, depth, curve, polarity, normalize, list, log)."""
    from PyQt6.QtCore import QTimer
    views = app.__dict__.setdefault("_patch_bay_views", [])
    views.append(w)
    w["_sig"] = None
    w["_loading"] = False

    def current_from_ui():
        return {"source": _strip(w["source"].currentText(), " Out"), "target": _strip(w["target"].currentText(), " In"),
                "weight": round(float(w["depth"].value()), 4), "curve": w["curve"].currentText(),
                "polarity": w["polarity"].currentText(), "normalize": bool(w["normalize"].isChecked()),
                "origin": "patch_bay", "user_defined": True}

    def connect():
        c = current_from_ui()
        if c["source"] == c["target"]:
            w["log"].append("- refused: %s cannot patch into itself" % c["source"])
            return
        _undo(app, "Patch cable")
        for old in _cables(app):
            if isinstance(old, dict) and old.get("source") == c["source"] and old.get("target") == c["target"]:
                old.update(c)
                w["log"].append("- UPDATED: " + label(old))
                break
        else:
            _cables(app).append(c)
            w["log"].append("- " + label(c) + " (Geometric Link Established)")
        _changed(app)

    def remove():
        row = w["list"].currentRow()
        items = [c for c in _cables(app) if isinstance(c, dict)]
        if 0 <= row < len(items):
            _undo(app, "Remove patch cable")
            c = items[row]
            app.patch_connections = [x for x in _cables(app) if x is not c]
            w["log"].append("- REMOVED: " + label(c))
            _changed(app)

    def clear():
        if not _cables(app):
            return
        _undo(app, "Clear patch cables")
        app.patch_connections = []
        w["log"].append("# Patch cleared — all cables removed (Undo restores them).")
        _changed(app)

    def randomize():
        _undo(app, "Randomize patch")
        added = randomize_patch(app)
        w["log"].append("# Randomize Patch · %d route-aware cable(s): %s" % (len(added), "; ".join(
            "%s → %s" % (c["source"], c["target"]) for c in added) or "every instrument already has an input"))
        _changed(app)

    def selected():
        row = w["list"].currentRow()
        items = [c for c in _cables(app) if isinstance(c, dict)]
        if not (0 <= row < len(items)):
            return
        c = items[row]
        w["_loading"] = True
        try:
            i = w["source"].findText("%s Out" % c.get("source"))
            if i >= 0:
                w["source"].setCurrentIndex(i)
            t = str(c.get("target", ""))
            i = w["target"].findText(t + " In")
            i = i if i >= 0 else w["target"].findText(t)
            if i >= 0:
                w["target"].setCurrentIndex(i)
            w["depth"].setValue(float(c.get("weight", 1.0) or 0.0))
            for key, values in (("curve", CURVES), ("polarity", POLARITIES)):
                j = w[key].findText(str(c.get(key, values[0])))
                if j >= 0:
                    w[key].setCurrentIndex(j)
            w["normalize"].setChecked(bool(c.get("normalize", True)))
        finally:
            w["_loading"] = False

    def settings_edited(*_a):
        if w["_loading"]:
            return
        row = w["list"].currentRow()
        items = [c for c in _cables(app) if isinstance(c, dict)]
        if not (0 <= row < len(items)):
            return
        c = items[row]
        c.update({"weight": round(float(w["depth"].value()), 4), "curve": w["curve"].currentText(),
                  "polarity": w["polarity"].currentText(), "normalize": bool(w["normalize"].isChecked())})
        _changed(app)

    w["connect_fn"], w["remove_fn"], w["clear_fn"], w["randomize_fn"] = connect, remove, clear, randomize
    w["list"].currentRowChanged.connect(lambda *_: selected())
    w["depth"].valueChanged.connect(settings_edited)
    w["curve"].currentTextChanged.connect(settings_edited)
    w["polarity"].currentTextChanged.connect(settings_edited)
    w["normalize"].toggled.connect(settings_edited)
    timer = QTimer(w["list"])
    timer.setInterval(600)
    timer.timeout.connect(lambda: refresh_view(app, w))
    timer.start()
    w["timer"] = timer
    refresh_view(app, w)
    return w


def refresh_view(app, w):
    try:
        sig = _sig(app)
        if sig == w.get("_sig"):
            return
        lst = w["list"]
        row = lst.currentRow()
        lst.blockSignals(True)
        lst.clear()
        for c in _cables(app):
            if isinstance(c, dict):
                lst.addItem(label(c))
        if 0 <= row < lst.count():
            lst.setCurrentRow(row)
        lst.blockSignals(False)
        w["_sig"] = sig
    except RuntimeError:
        try:
            app._patch_bay_views.remove(w)
        except Exception:
            pass


def refresh_open_views(app):
    for w in list(getattr(app, "_patch_bay_views", []) or []):
        refresh_view(app, w)


def _active(app, name):
    try:
        mem = app._current_sequence_mem(name)
    except Exception:
        mem = (getattr(app, "instrument_sequencer_memory", {}) or {}).get(name, {})
    return any(bool(s) for s in (mem or {}).get("steps", []) or [])


def randomize_patch(app, n_cables=None, seed=None):
    """Route-aware deterministic cables. Returns the cables added."""
    names = list(getattr(app, "instrument_names_48", []) or [])
    if len(names) < 2:
        return []
    cables = _cables(app)
    edges = {(c.get("source"), c.get("target")) for c in cables if isinstance(c, dict)}
    served = {t for _s, t in edges}
    if seed is None:
        try:
            seed = app.get_numeric_seed()
        except Exception:
            seed = 0
    base = "patchmodular-routes|%s|%d" % (seed, len(cables))

    def u(*parts):
        d = hashlib.sha256(("%s|%s" % (base, "|".join(map(str, parts)))).encode("utf-8", "replace")).digest()
        return int.from_bytes(d[:8], "little") / 2.0 ** 64

    active = {n for n in names if _active(app, n)}
    targets = [n for n in names if n not in served] or list(names)
    targets.sort(key=lambda n: (n not in active, u("t", n)))
    k = int(n_cables) if n_cables else max(1, min(4, len(targets)))
    added = []
    fam = {n: i // 6 for i, n in enumerate(names)}
    for tgt in targets[:k]:
        best = None
        for src in names:
            if src == tgt or (src, tgt) in edges:
                continue
            score = (2.0 if src in active else 0.0) + max(0.0, 1.5 - 0.5 * abs(fam[src] - fam[tgt])) + u("s", src, tgt)
            if best is None or score > best[0]:
                best = (score, src)
        if best is None:
            continue
        c = {"source": best[1], "target": tgt, "weight": round(0.2 + 0.8 * u("w", tgt), 2),
             "curve": CURVES[int(u("c", tgt) * len(CURVES)) % len(CURVES)],
             "polarity": POLARITIES[int(u("p", tgt) * len(POLARITIES)) % len(POLARITIES)],
             "normalize": True, "origin": "patch_bay_randomize", "user_defined": True}
        cables.append(c)
        edges.add((c["source"], tgt))
        added.append(c)
    return added
