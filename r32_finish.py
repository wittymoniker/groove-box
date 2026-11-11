"""r32_finish.py — GROOVEBOX_R32_FINISH_20261110

* SAVE HISTORY   the last N (default 64) autosaves / project saves, chronological, copied into the system
                 store; N shrinks with free disk space (< 2 GB → 16, < 0.5 GB → 4). Compatibility
                 "save_history_max" (0 = off). Shown on the startup screen with the resumed-export count.
* EXPORT RESUME  queued / running exports are persisted (frozen project + options) and re-queued after a
                 reboot; finished parts are reused by the exporters' own .part resume.
* LIVE AUTOSAVE  every edit (live source change) schedules a project autosave 20 s later (debounced).
* CANONICAL MIX  while a canonical engine is active the canonicals drive the master + local mixers
                 (seeded balance) and — unless "Bind to Modulation Levels" is unchecked — scale the
                 modulation depth by the canonical level.
* STRUCTURAL MAP one pathway per part of the wave structure (level → Drive, brightness → High,
                 low energy → Low, pitch motion → Tilt, texture → Fractal, rhythm → Mod): Auto-map adds all
                 six canonical lanes in one step (most features, fewest changes).
* WEB            the browser reads pages; downloads are limited to media / project types Groovebox opens.
* MIDI           project → .mid (every instrument's steps + pitches over every playlist row, one channel each)
                 and .mid → project with instrument morph (each track → the instrument whose register fits).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import time

MEDIA_EXT = {".wav", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aiff", ".aif", ".mid", ".midi", ".png", ".jpg",
             ".jpeg", ".webp", ".bmp", ".gif", ".mp4", ".mkv", ".webm", ".mov", ".avi", ".mcc", ".txt", ".csv",
             ".json", ".seed", ".obj", ".mtl"}


def _store(*p):
    import groovebox_paths as gp
    d = os.path.join(gp.system_root(), "state", *p)
    os.makedirs(d, exist_ok=True)
    return d


def _setting(key, default):
    try:
        import compat_settings as cs
        return cs.load().get(key, default)
    except Exception:
        return default


# ---------------------------------------------------------------- save history ------------
def history_limit():
    n = int(_setting("save_history_max", 64) or 0)
    try:
        free = shutil.disk_usage(_store("history")).free / 2 ** 30
        if free < 0.5:
            n = min(n, 4)
        elif free < 2.0:
            n = min(n, 16)
    except Exception:
        pass
    return max(0, n)


_LAST_AUTO = {"t": 0.0}
_SEQ = {"n": 0}


def record_save(path, kind="save"):
    n = history_limit()
    if n <= 0 or not path or not os.path.isfile(path):
        return
    if kind == "autosave":                      # R32.9: live autosave writes often — keep one copy per 5 minutes
        if time.time() - _LAST_AUTO["t"] < 300:
            return
        _LAST_AUTO["t"] = time.time()
    d = _store("history")
    _SEQ["n"] += 1      # R32.9: ms + counter — two saves in the same second no longer overwrite each other
    ts = time.strftime("%Y%m%d-%H%M%S") + "-%03d-%04d" % (int(time.time() * 1000) % 1000, _SEQ["n"] % 10000)
    dst = os.path.join(d, "%s__%s__%s" % (ts, kind, os.path.basename(path)))
    try:
        shutil.copy2(path, dst)
        with open(dst + ".json", "w", encoding="utf-8") as f:
            json.dump({"source": path, "kind": kind, "time": time.time(), "bytes": os.path.getsize(path)}, f)
    except Exception:
        return
    items = history()
    for p, _m in items[:-n] if len(items) > n else []:
        for x in (p, p + ".json"):
            try:
                os.remove(x)
            except Exception:
                pass


def history():
    out = []
    for p in sorted(glob.glob(os.path.join(_store("history"), "*"))):
        if p.endswith(".json"):
            continue
        try:
            with open(p + ".json", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {"time": os.path.getmtime(p), "kind": "save", "source": p}
        out.append((p, meta))
    return out                                          # chronological (timestamped names)


# ---------------------------------------------------------------- export resume ------------
def persist_job(job):
    try:
        d = _store("export_queue")
        shutil.copy2(job.project, os.path.join(d, "%d.MCC" % job.id))
        with open(os.path.join(d, "%d.json" % job.id), "w", encoding="utf-8") as f:
            json.dump({"kind": job.kind, "out_file": job.out_file, "options": job.options, "label": job.label}, f, default=str)
    except Exception:
        pass


def forget_job(job):
    d = _store("export_queue")
    for x in ("%d.MCC" % job.id, "%d.json" % job.id):
        try:
            os.remove(os.path.join(d, x))
        except Exception:
            pass


def resume_exports(app):
    """Re-queue exports that were waiting or running when Groovebox stopped. Returns how many."""
    d = _store("export_queue"); n = 0
    files = sorted(glob.glob(os.path.join(d, "*.json")))
    if not files:
        return 0
    sch = app._export_scheduler()
    for jp in files:
        mp = jp[:-5] + ".MCC"
        try:
            meta = json.load(open(jp, encoding="utf-8"))
            doc = json.load(open(mp, encoding="utf-8"))
            opts = dict(meta.get("options") or {})
            pre = dict(opts.get("preset") or {}); pre["resume"] = True; opts["preset"] = pre
            sch.submit_job(meta["kind"], meta["out_file"], opts, label="↻ " + str(meta.get("label") or ""), project_doc=doc)
            for x in (jp, mp):                   # R32.9: only after it is safely queued again (it re-persists itself)
                try:
                    os.remove(x)
                except OSError:
                    pass
            n += 1
        except Exception as exc:
            print("[Exports] could not resume %s: %s" % (os.path.basename(jp), exc))
    return n


# ---------------------------------------------------------------- live autosave ------------
def install_live_autosave(app):
    from PyQt6.QtCore import QTimer
    if getattr(app, "_r32_live_autosave", None) is not None or not bool(_setting("live_autosave", True)):
        return
    t = app._r32_live_autosave = QTimer(app); t.setSingleShot(True); t.setInterval(20000)
    st = {"last": 0.0, "dirty": False}

    def _fire():
        # R32.9: at most one live autosave per 2 minutes, and only when something really changed
        if not st["dirty"]:
            return
        wait = 120.0 - (time.monotonic() - st["last"])
        if wait > 0:
            t.start(int(wait * 1000) + 50); return
        st["dirty"] = False; st["last"] = time.monotonic()
        getattr(app, "_autosave_project", lambda: None)()
    t.timeout.connect(_fire)
    orig = getattr(app, "_on_live_source_changed", None)
    if callable(orig):
        def _changed(*a, _o=orig, **k):
            r = _o(*a, **k)
            if not getattr(app, "is_playing", False) or getattr(app, "_r32_user_edit", True):
                st["dirty"] = True
                if not t.isActive():          # no restart storm: the first edit schedules, later ones ride along
                    t.start(20000)
            return r
        app._on_live_source_changed = _changed


# ---------------------------------------------------------------- canonical mixing ---------
_CL = {"t": -1.0, "v": 0.0, "app": None}


def canonical_level(app):
    """0..1: how strongly the canonicals are acting now (mean level of the active engines). Cached 0.5 s:
    it is read once per rendered voice."""
    now = time.monotonic()
    if _CL["app"] is app and now - _CL["t"] < 0.5:
        return _CL["v"]
    _CL.update(t=now, app=app, v=_canonical_level_now(app))
    return _CL["v"]


def _canonical_level_now(app):
    try:
        act = app._get_active_engine_set()
        if not act:
            return 0.0
        return max(0.0, min(1.0, sum(float(app._canonical_level(k)) for k in act) / len(act)))
    except Exception:
        return 0.0


def bind_mod_levels(app):
    st = getattr(app, "r32_inst_mix", None) or {}
    return bool(st.get("bind_mod", True))


STRUCTURE_MAP = (("level / envelope", "r32_fx_state/global/hyper"), ("brightness", "r32_eq/global/high"),
                 ("low-band energy", "r32_eq/global/low"), ("pitch motion", "r32_fx_state/global/tilt"),
                 ("texture / roughness", "r32_fx_state/global/fractal"), ("rhythm / pulse", "r32_mod_osc/global/depth"))


def auto_map(app, amount=0.25, rate=16.0):
    """One canonical lane per part of the wave structure (adds only the missing ones)."""
    import automation_bus as ab
    have = {l.get("path") for l in ab.lanes(app) if l.get("owner") == "canonical"}
    n = 0
    for i, (_part, path) in enumerate(STRUCTURE_MAP):
        if path not in have and ab.add_lane(app, path, amount=amount, rate=rate * (1 + i % 3), owner="canonical") is not None:
            n += 1
    return n


# ---------------------------------------------------------------- web downloads -------------
def allowed_download(name):
    return os.path.splitext(str(name or ""))[1].lower() in MEDIA_EXT


# ---------------------------------------------------------------- MIDI ----------------------
def _names(app):
    v = getattr(app, "instrument_names_48", None) or list((getattr(app, "instrument_sequencer_memory", {}) or {}).keys())
    return list(v)


def project_to_midi(app, path):
    """Every instrument's step pattern + pitch ratios over every playlist row → one SMF, one channel each."""
    import math, signal_converters as sc
    bpm = float(app.spin_bpm.value()) if hasattr(app, "spin_bpm") else 120.0
    base = float(app.spin_base_frequency.value()) if hasattr(app, "spin_base_frequency") else 440.0
    rows = max(1, len(getattr(app, "master_playlist_data", []) or []) or 1)
    mem = getattr(app, "instrument_sequencer_memory", {}) or {}
    notes = []
    for ci, name in enumerate(_names(app)):
        m = mem.get(name) or {}
        steps = list(m.get("steps") or [])
        if not any(steps):
            continue
        L = int(m.get("pattern_length", len(steps)) or len(steps))
        pitches = list(m.get("pitches") or [1.0] * L)
        step_s = 60.0 / bpm / 4.0
        for r in range(rows):
            for s in range(L):
                if s < len(steps) and steps[s]:
                    ratio = float(pitches[s] if s < len(pitches) else 1.0) or 1.0
                    hz = base * ratio
                    p = int(round(69 + 12 * math.log2(max(1e-6, hz) / 440.0)))
                    notes.append(((r * L + s) * step_s, step_s * 0.9, max(0, min(127, p)), 96, ci % 16))
    return write_midi_multi(path, notes, bpm)


def write_midi_multi(path, notes, bpm=120.0, tpq=480):
    """notes: (start_s, dur_s, pitch, vel, channel) → SMF type 0."""
    import struct
    from signal_converters import _vlq
    ev = []
    for st, du, p, v, ch in notes:
        a = int(round(st * bpm / 60 * tpq)); b = int(round((st + du) * bpm / 60 * tpq))
        ev.append((a, 1, bytes([0x90 | ch, p, v]))); ev.append((b, 0, bytes([0x80 | ch, p, 0])))
    ev.sort(key=lambda e: (e[0], e[1]))
    trk = bytearray(b"\x00\xff\x51\x03" + int(60e6 / bpm).to_bytes(3, "big")); last = 0
    for t, _o, d in ev:
        trk += _vlq(t - last) + d; last = t
    trk += b"\x00\xff\x2f\x00"
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq) + b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk))
    return path


def midi_to_project(app, path, morph=True):
    """.mid → this project's sequencer. Notes are grouped by register (instrument morph): the lowest group goes to
    the first instrument, and so on; each note lands on its nearest 16th step and its pitch becomes a ratio of the
    base frequency. Returns a report."""
    import math, signal_converters as sc
    notes = sc.read_midi(path)
    if not notes:
        return "no notes"
    bpm = float(app.spin_bpm.value()) if hasattr(app, "spin_bpm") else 120.0
    base = float(app.spin_base_frequency.value()) if hasattr(app, "spin_base_frequency") else 440.0
    names = _names(app); mem = app.instrument_sequencer_memory
    k = max(1, min(len(names), 8))
    ps = sorted(p for _s, _d, p, _v in notes)
    edges = [ps[min(len(ps) - 1, int(len(ps) * i / k))] for i in range(1, k)] if morph else []
    step_s = 60.0 / bpm / 4.0
    used = {}
    for st, _du, p, v in notes:
        g = sum(1 for e in edges if p > e)
        name = names[g]; m = mem.setdefault(name, {})
        L = int(m.get("pattern_length", 16) or 16)
        s = int(round(st / step_s)) % L
        steps = list(m.get("steps") or [False] * L); steps += [False] * (L - len(steps))
        pit = list(m.get("pitches") or [1.0] * L); pit += [1.0] * (L - len(pit))
        steps[s] = True; pit[s] = round(440.0 * 2 ** ((p - 69) / 12.0) / base, 6)
        m["steps"], m["pitches"] = steps, pit
        used[name] = used.get(name, 0) + 1
    try:
        app.reload_active_instrument_sequencer_ui()
    except Exception:
        pass
    getattr(app, "_on_live_source_changed", lambda: None)()
    return "%d notes → %s" % (len(notes), ", ".join("%s (%d)" % kv for kv in used.items()))


# ---------------------------------------------------------------- startup panel -------------
def startup_panel(on_open):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
    from PyQt6.QtCore import Qt
    w = QWidget(); lay = QVBoxLayout(w)
    t = QLabel("🕘 Last saves (newest first)"); t.setStyleSheet("font-size:12pt;font-weight:800;"); lay.addWidget(t)
    lst = QListWidget(); lay.addWidget(lst, 1)
    for p, m in reversed(history()):
        it = QListWidgetItem("%s · %s · %s" % (time.strftime("%Y-%m-%d %H:%M", time.localtime(m.get("time", 0))),
                                               m.get("kind", "save"), os.path.basename(str(m.get("source", p)))))
        it.setData(Qt.ItemDataRole.UserRole, p); lst.addItem(it)
    lst.itemActivated.connect(lambda it: on_open(it.data(Qt.ItemDataRole.UserRole)))
    q = len(glob.glob(os.path.join(_store("export_queue"), "*.json")))
    info = QLabel("%d export(s) will resume into the queue · %d saves kept (limit %d)" % (q, len(history()), history_limit()))
    info.setWordWrap(True); lay.addWidget(info)
    return w


def start(app):
    from PyQt6.QtCore import QTimer
    install_live_autosave(app)

    def _resume():
        n = resume_exports(app)
        if n:
            print("[Exports] %d unfinished export(s) resumed" % n)
            try:
                app._r32_resumed_exports = n
            except Exception:
                pass
    QTimer.singleShot(6000, _resume)
