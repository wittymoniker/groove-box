"""plugin_library.py — browse, run, share, rate and BIND plugins. Everything goes through plugin_guard (validated
requests, one undo step, rollback) and app_limits (strictly < 0.19758 of CPU / RAM), on the sCode 'programs' direction.

Library    plugins_library/ (shipped, 70+ Groovebox plugins in Python, Lua, C, C++, Rust, Go, Julia, shell) and your
           own folder ~/.local/share/groovebox/plugins (installed / shared-in). Each plugin = a folder with plugin.json
           (id, name, language, category create | inform | recreation, description, entry, runs process | lua).
Run        lua plugins run inside the sandbox with the gb.* API; every other language is built and run as a separate
           process by the Program Builder. Their files come back into Groovebox by type; requests are applied by
           plugin_guard.
Share      "Share on LAN" packs a plugin as <id>.gbplugin into your Nearby share folder; peers see it. "LAN plugins"
           lists the .gbplugin files of nearby Grooveboxes; Install downloads, checks (zip paths, size, plugin.json) and
           unpacks into your plugin folder, marked with where it came from and that peer's trust level. Received code
           never runs by itself; blacklisted peers' plugins are hidden.
Rate       your rating (1–5) is stored with the network database (net_hub), so it is the PUBLIC rating on your site and
           across a host network; the browser shows average and count.
BINDINGS (what a plugin can drive)
  carrier    an instrument's carrier sample = the plugin's newest WAV (re-run on demand or on seed change)
  controls   a plugin may write controls.json {"name": [values 0..1 …]}; each list becomes a Mod Matrix source
             "plugin:<id>:<name>" (read over the song), so plugin output can steer any local parameter
  params     controls named after an instrument parameter set it directly (validated by plugin_guard)
  events     run a plugin on: seed change · canonical commit · export finished · project load
RANDOMIZE PROJECT   (Task pad ▸ Studio ▸ 🎲 Randomize project): random seed, then random plugins (and their app
  states: a random seed for each), and / or random samples (from a list or a disk scan) bound as instrument carriers,
  with an "original synth engine participation" percentage that keeps the rest of the instruments on the synth.
"""
from __future__ import annotations
import json, os, random, shutil, threading, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED = os.path.join(HERE, "plugins_library")


def user_dir():
    d = os.path.join(os.path.expanduser("~"), ".local", "share", "groovebox", "plugins"); os.makedirs(d, exist_ok=True); return d


def plugins():
    out = []
    for root, origin in ((SHIPPED, "shipped"), (user_dir(), "installed")):
        if not os.path.isdir(root): continue
        for name in sorted(os.listdir(root)):
            m = os.path.join(root, name, "plugin.json")
            if os.path.isfile(m):
                try:
                    d = __import__("safe_io").load_json(m); d["dir"] = os.path.join(root, name); d.setdefault("origin", origin); out.append(d)
                except Exception:
                    pass
    return out


def find(pid):
    return next((p for p in plugins() if p.get("id") == pid), None)


def _bindings(app):
    b = getattr(app, "r99_plugin_bindings", None)
    if not isinstance(b, dict):
        b = app.r99_plugin_bindings = {"carrier": {}, "events": {}, "controls": {}}
    return b


# ------------------------------------------------------------------ run
def run(app, p, on_line=None, done=None, seed=None):
    """Run a plugin. done(files) is called on the Qt thread with the accepted output files."""
    say = on_line or (lambda s: None)
    if p.get("runs") == "lua":
        import lua_workspace as lw
        ok, txt = lw.run(app, open(os.path.join(p["dir"], p["entry"]), encoding="utf-8").read()); say(txt)
        if done: done([])
        return
    import program_builder as pb, plugin_guard as pg
    src = os.path.join(p["dir"], p["entry"])

    def job():
        try:
            ok, argv, txt = pb.build(app, src); say(txt)
            if not ok:
                return
            outd = pb.out_dir(app, p["id"] + "-" + time.strftime("%H%M%S"))
            env_seed = seed
            if env_seed is not None:
                os.environ["GROOVEBOX_PLUGIN_SEED"] = str(env_seed)
            rc, new = pb.run(app, argv, outd, say)
            os.environ.pop("GROOVEBOX_PLUGIN_SEED", None)
            say("exit %d" % rc)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: _after(app, p, outd, new, done))
        except Exception as exc:
            say("✖ %s" % exc)
    try:                                   # R101: one strand per plugin, so a plugin never races its own state
        import compute
        compute.run("programs", job, carrier="plugin:" + str(p.get("id")))
    except Exception:
        threading.Thread(target=job, daemon=True).start()


def _after(app, p, outd, new, done):
    import plugin_guard as pg
    req = os.path.join(outd, "groovebox_requests.json")
    if os.path.isfile(req):
        try:
            ops = __import__("safe_io").load_json(req); pg.apply_requests(app, ops if isinstance(ops, list) else [], who=p["name"], root=outd)
        except Exception:
            pass
    files = pg.guard_outputs(app, outd, new, p["name"])
    ctl = os.path.join(outd, "controls.json")
    if os.path.isfile(ctl):
        try:
            c = __import__("safe_io").load_json(ctl)
            if isinstance(c, dict):
                _bindings(app)["controls"][p["id"]] = {str(k)[:32]: [max(0.0, min(1.0, float(x))) for x in v[:4096]] for k, v in list(c.items())[:32] if isinstance(v, list)}
        except Exception:
            pass
    for f in files:
        try: __import__("experiences").record(app, f, "plugin", {"plugin": p["id"]})
        except Exception: pass
    if done: done(files)


# ------------------------------------------------------------------ bindings
def bind_carrier(app, instrument, pid):
    _bindings(app)["carrier"][instrument] = pid
    refresh_carrier(app, instrument)


def refresh_carrier(app, instrument):
    pid = _bindings(app)["carrier"].get(instrument); p = find(pid) if pid else None
    if not p: return

    def done(files):
        wavs = [f for f in files if f.lower().endswith((".wav", ".flac"))]
        if not wavs: return
        try:
            arr, sr = app._decode_media_audio(wavs[-1])
            import numpy as np
            prev = (getattr(app, "instrument_media_samples", {}) or {}).get(instrument, {}) or {}
            app.instrument_media_samples[instrument] = {**prev, "path": wavs[-1], "sample_rate": int(sr), "waveform": np.asarray(arr, dtype=np.float32).ravel(),
                                                        "user_owned": True, "source_kind": "audio", "plugin": pid}
            app._shared_mixdown_cache = {}; app._on_live_source_changed()
            __import__("notify_center").notify(app, "🔌 %s → carrier of %s" % (p["name"], instrument), "info")
        except Exception as exc:
            __import__("notify_center").notify(app, "carrier bind: %s" % exc, "warn")
    run(app, p, done=done)


def control_value(app, pid, name, u):
    v = ((_bindings(app)["controls"].get(pid) or {}).get(name)) or []
    if not v: return 0.5
    x = max(0.0, min(0.999999, float(u))) * (len(v) - 1); i = int(x); f = x - i
    return v[i] * (1 - f) + v[min(i + 1, len(v) - 1)] * f


def fire(app, event):
    for pid in list((_bindings(app)["events"].get(event) or [])):
        p = find(pid)
        if p: run(app, p)
    if event == "seed":
        for inst in list(_bindings(app)["carrier"]):
            refresh_carrier(app, inst)


def install(app):
    _bindings(app)
    try:   # events
        import groovebox_runtime  # noqa
    except Exception:
        pass
    try:
        app.input_seed_val.textChanged.connect(lambda: _debounce(app, "seed", 3000))
    except Exception:
        pass
    for meth, ev in (("_ensure_perfect_unison", "canonical"), ("open_project_path", "load")):
        f = getattr(app, meth, None)
        if callable(f) and not getattr(f, "_r99_pl", False):
            def w(*a, _f=f, _ev=ev, **k):
                r = _f(*a, **k)
                try:
                    if (_bindings(app)["events"].get(_ev) or []): fire(app, _ev)
                except Exception: pass
                return r
            w._r99_pl = True; setattr(app, meth, w)
    try:
        import studio_extras as se
        o = se.on_export_finished
        if not getattr(o, "_r99_pl", False):
            def ex(app_, job, _o=o):
                _o(app_, job)
                if getattr(job, "state", "") == "done" and (_bindings(app_)["events"].get("export") or []): fire(app_, "export")
            ex._r99_pl = True; se.on_export_finished = ex
    except Exception:
        pass
    try:   # mod-matrix sources "plugin:<id>:<name>"
        import mod_matrix as mm
        if not getattr(mm, "_r99_pl", False):
            orig_src, orig_sources = mm._src, mm.sources

            def _src(app_, name, beat, outs, row):
                if name.startswith("plugin:"):
                    _, pid, nm = (name.split(":", 2) + ["", ""])[:3]
                    try:
                        n = max(1, len([r for r in app_.master_playlist_data if r])); rb = float(app_.spin_row_beats.value())
                        u = (beat / max(1e-6, n * rb)) % 1.0
                    except Exception:
                        u = 0.0
                    return control_value(app_, pid, nm, u)
                return orig_src(app_, name, beat, outs, row)

            def sources(app_):
                out = orig_sources(app_)
                for pid, ctl in (_bindings(app_)["controls"] or {}).items():
                    out += ["plugin:%s:%s" % (pid, n) for n in ctl]
                return out
            mm._src = _src; mm.sources = sources; mm._r99_pl = True
    except Exception:
        pass


def _debounce(app, ev, ms):
    from PyQt6.QtCore import QTimer
    t = getattr(app, "_r99_pl_timer", None)
    if t is None:
        t = app._r99_pl_timer = QTimer(app); t.setSingleShot(True); t.timeout.connect(lambda: fire(app, "seed"))
    t.start(ms)


# ------------------------------------------------------------------ LAN share / install
def share_dir(app):
    svc = getattr(app, "_nearby_share_service", None)
    root = str(svc.roots.get("modules")) if svc is not None and "modules" in getattr(svc, "roots", {}) else os.path.join(user_dir(), "_shared")
    d = os.path.join(root, "plugins"); os.makedirs(d, exist_ok=True); return d


def pack(app, p):
    out = os.path.join(share_dir(app), p["id"] + ".gbplugin")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _dn, fn in os.walk(p["dir"]):
            for f in fn:
                if "__pycache__" in dp or f.endswith(".pyc"): continue
                full = os.path.join(dp, f); z.write(full, os.path.join(p["id"], os.path.relpath(full, p["dir"])))
    try:
        svc = getattr(app, "_nearby_share_service", None)
        svc and svc.invalidate_catalog()
    except Exception:
        pass
    return out


def install_zip(app, path, origin="file", level="public"):
    try:
        __import__("accounts").require("install", os.path.basename(str(path)))   # R101 account roles
    except ImportError:
        pass
    """Validate and unpack a .gbplugin. Returns the plugin dict. Never runs anything."""
    if os.path.getsize(path) > 64 << 20: raise ValueError("plugin archive larger than 64 MB")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if not names or len(names) > 400: raise ValueError("bad plugin archive")
        top = names[0].split("/")[0]
        for n in names:
            if n.startswith("/") or ".." in n.split("/") or not n.startswith(top + "/"): raise ValueError("unsafe path in archive: %s" % n)
        meta = json.loads(z.read(top + "/plugin.json"))
        for k in ("id", "name", "language", "entry"):
            if k not in meta: raise ValueError("plugin.json lacks %s" % k)
        dst = os.path.join(user_dir(), "".join(c for c in str(meta["id"]) if c.isalnum() or c in "-_")[:48])
        if os.path.isdir(dst): shutil.rmtree(dst)
        z.extractall(user_dir() + "/.tmp_install"); shutil.move(os.path.join(user_dir(), ".tmp_install", top), dst)
        shutil.rmtree(os.path.join(user_dir(), ".tmp_install"), ignore_errors=True)
    meta.update(origin=origin, trust=level, installed=time.time(), reviewed=False)
    __import__("safe_io").atomic_write_json(os.path.join(dst, "plugin.json"), meta, indent=1)
    return meta


def lan_plugins(app):
    svc = getattr(app, "_nearby_share_service", None); out = []
    if svc is None: return out
    try:
        import net_hub as nh
    except Exception:
        nh = None
    for peer in list(getattr(svc, "peers", {}).values()):
        lv = nh.trust(peer.ip) if nh else "public"
        if nh and not nh.allowed(lv, "download"): continue
        try:
            for f in svc.fetch_files({"url": peer.url}):
                if str(f.get("name", "")).endswith(".gbplugin"): out.append((peer, f, lv))
        except Exception:
            continue
    return out


# ------------------------------------------------------------------ randomize project
def randomize_project(app, use_plugins=True, use_samples=False, samples=None, synth_pct=50.0, n_plugins=4):
    """New random seed, then random plugins (each with its own random seed = app state) and / or random samples as
    instrument carriers; synth_pct of the instruments keep the original synth engine only."""
    r = random.Random()
    try: app._push_undo("Randomize project")
    except Exception: pass
    try: app._on_random_seed_clicked()
    except Exception: pass
    names = [n for n in (getattr(app, "instrument_names_48", []) or [])]
    r.shuffle(names)
    keep = int(round(len(names) * max(0.0, min(100.0, synth_pct)) / 100.0))
    free = names[keep:]
    creators = [p for p in plugins() if p.get("category") == "create" and p.get("runs") != "lua" and p.get("origin") == "shipped"]
    pool_samples = list(samples or [])
    plan = []
    for i, inst in enumerate(free):
        if use_plugins and use_samples:
            choice = "plugin" if i % 2 == 0 else "sample"
        else:
            choice = "plugin" if use_plugins else ("sample" if use_samples else None)
        if choice == "plugin" and creators and len([x for x in plan if x[1] == "plugin"]) < n_plugins:
            p = r.choice(creators); plan.append((inst, "plugin", p["id"]))
            _bindings(app)["carrier"][inst] = p["id"]
            run(app, p, seed=r.randrange(1, 10 ** 9), done=lambda files, inst=inst, p=p: _assign_wav(app, inst, files, p["id"]))
        elif choice == "sample" and pool_samples:
            f = r.choice(pool_samples); plan.append((inst, "sample", f)); _assign_wav(app, inst, [f], None)
    return plan, keep


def _assign_wav(app, inst, files, pid):
    wavs = [f for f in files if f.lower().endswith((".wav", ".flac", ".mp3", ".ogg", ".m4a"))]
    if not wavs: return
    try:
        import numpy as np
        arr, sr = app._decode_media_audio(wavs[-1])
        app.instrument_media_samples[inst] = {"path": wavs[-1], "sample_rate": int(sr), "waveform": np.asarray(arr, dtype=np.float32).ravel(),
                                              "user_owned": True, "source_kind": "audio", "plugin": pid}
        app._shared_mixdown_cache = {}; app._on_live_source_changed()
    except Exception:
        pass


def scan_samples(root, limit=2000):
    out = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith((".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aiff")):
                out.append(os.path.join(dp, f))
                if len(out) >= limit: return out
    return out


def open_randomizer(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QSpinBox, QDoubleSpinBox, QPushButton, QLabel, QListWidget, QFileDialog)
    d = QDialog(app); d.setWindowTitle("🎲 Randomize project"); d.resize(620, 520); d.setWindowModality(Qt.WindowModality.NonModal); lay = QVBoxLayout(d)
    cp = QCheckBox("Random plugins (each with its own random app state)"); cp.setChecked(True); cs_ = QCheckBox("Random samples"); np_ = QSpinBox(); np_.setRange(0, 48); np_.setValue(4)
    syn = QDoubleSpinBox(); syn.setRange(0, 100); syn.setValue(50); syn.setSuffix(" %"); syn.setPrefix("Original synth engine participation ")
    row = QHBoxLayout(); [row.addWidget(w) for w in (cp, QLabel("max plugins"), np_)]; lay.addLayout(row); lay.addWidget(cs_); lay.addWidget(syn)
    lst = QListWidget(); lay.addWidget(QLabel("Sample list (add files or scan a folder)")); lay.addWidget(lst, 1)
    row = QHBoxLayout(); lay.addLayout(row); ba = QPushButton("＋ Files…"); bsc = QPushButton("Scan folder…"); bc = QPushButton("Clear")
    for w in (ba, bsc, bc): row.addWidget(w)
    out = QLabel(""); out.setWordWrap(True); lay.addWidget(out); go = QPushButton("🎲 Randomize now"); lay.addWidget(go)
    ba.clicked.connect(lambda: [lst.addItem(f) for f in QFileDialog.getOpenFileNames(d, "Samples", os.path.expanduser("~"), "Audio (*.wav *.flac *.mp3 *.ogg *.m4a *.aiff)")[0]])
    bsc.clicked.connect(lambda: (lambda f: f and [lst.addItem(x) for x in scan_samples(f)])(QFileDialog.getExistingDirectory(d, "Scan for samples", os.path.expanduser("~"))))
    bc.clicked.connect(lst.clear)

    def doit():
        plan, keep = randomize_project(app, cp.isChecked(), cs_.isChecked(), [lst.item(i).text() for i in range(lst.count())], syn.value(), np_.value())
        out.setText("%d instruments stay on the original synth · %s" % (keep, "; ".join("%s ← %s %s" % (a, b, os.path.basename(str(c))) for a, b, c in plan[:12]) or "no plugin / sample assignments"))
    go.clicked.connect(doit); d.show(); app._randomizer_dialog = d
    return d


# ------------------------------------------------------------------ browser
def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QLabel,
                                 QComboBox, QLineEdit, QSpinBox, QTabWidget, QWidget, QFileDialog)
    catalog = plugins()
    shipped_count = sum(1 for p in catalog if p.get("origin") == "shipped")
    lua_count = sum(1 for p in catalog if str(p.get("language", "")).lower() == "lua" or p.get("runs") == "lua")
    d = QDialog(app); d.setWindowTitle(f"🔌 Applications · {shipped_count} shipped plugins · Lua / hybrid / native"); d.resize(1120, 700); d.setWindowModality(Qt.WindowModality.NonModal)
    lay = QVBoxLayout(d)
    summary = QLabel(f"APPLICATIONS LAUNCHER  ·  {shipped_count} shipped plugins  ·  {lua_count} Lua entries  ·  installed plugins included  ·  external apps remain separately permissioned")
    summary.setWordWrap(True); summary.setStyleSheet("color:#9fe6d5;background:rgba(10,24,31,150);border:1px solid rgba(73,150,139,130);border-radius:6px;padding:6px;font-weight:800;")
    lay.addWidget(summary)
    top = QHBoxLayout(); lay.addLayout(top)
    q = QLineEdit(); q.setPlaceholderText("search"); cat = QComboBox(); cat.addItems(["all", "create", "inform", "recreation"])
    lang = QComboBox(); lang.addItems(["all languages", "py", "lua", "c", "cpp", "rs", "go", "jl", "sh"])
    for w in (q, cat, lang): top.addWidget(w)
    split = QSplitter(); lay.addWidget(split, 1); lst = QListWidget(); split.addWidget(lst)
    right = QTabWidget(); split.addWidget(right); split.setSizes([380, 740])
    w1 = QWidget(); l1 = QVBoxLayout(w1); right.addTab(w1, "Plugin")
    info = QLabel(""); info.setWordWrap(True); l1.addWidget(info)
    src = QPlainTextEdit(); src.setReadOnly(True); src.setFont(QFont("Monospace", 9)); l1.addWidget(src, 2)
    log = QPlainTextEdit(); log.setReadOnly(True); log.setMaximumHeight(150); l1.addWidget(log)
    row = QHBoxLayout(); l1.addLayout(row)
    b_run = QPushButton("▶ Run"); b_edit = QPushButton("✎ Open in Program Builder"); b_share = QPushButton("📶 Share on LAN"); rate = QSpinBox(); rate.setRange(1, 5); rate.setPrefix("★ ")
    b_rate = QPushButton("Rate")
    for w in (b_run, b_edit, b_share, rate, b_rate): row.addWidget(w)
    row2 = QHBoxLayout(); l1.addLayout(row2)
    inst = QComboBox(); [inst.addItem(app.instrument_label(n) if hasattr(app, "instrument_label") else n, n) for n in (getattr(app, "instrument_names_48", []) or [])]
    b_bind = QPushButton("🔗 Bind as carrier of"); ev = QComboBox(); ev.addItems(["seed change", "canonical commit", "export finished", "project load"])
    b_ev = QPushButton("⚡ Run on event"); b_unbind = QPushButton("Unbind")
    for w in (b_bind, inst, b_ev, ev, b_unbind): row2.addWidget(w)
    w2 = QWidget(); l2 = QVBoxLayout(w2); right.addTab(w2, "📶 LAN plugins")
    lanl = QListWidget(); l2.addWidget(lanl, 1); r2 = QHBoxLayout(); l2.addLayout(r2)
    b_scan = QPushButton("⟳ Look on the LAN"); b_inst = QPushButton("⬇ Install selected"); b_file = QPushButton("Install .gbplugin file…")
    for w in (b_scan, b_inst, b_file): r2.addWidget(w)
    l2.addWidget(QLabel("Installed plugins never run by themselves. Read the source (Plugin tab) before you press Run."))
    st = {"rows": [], "lan": []}

    def fill():
        s = q.text().lower(); lst.clear(); st["rows"] = []
        for p in plugins():
            if cat.currentText() != "all" and p.get("category") != cat.currentText(): continue
            if lang.currentText() != "all languages" and p.get("language") != lang.currentText(): continue
            if s and s not in json.dumps(p).lower(): continue
            try:
                import net_hub as nh; rt = nh.rating("plugin:" + p["id"])
            except Exception:
                rt = {"avg": 0, "count": 0}
            icon = {"create": "🎨", "inform": "📘", "recreation": "🎮"}.get(p.get("category"), "🔌")
            it = QListWidgetItem("%s %s  · %s%s%s" % (icon, p["name"], p.get("language"), "  ★%.1f (%d)" % (rt["avg"], rt["count"]) if rt["count"] else "",
                                                      "  ⚠ from %s" % p.get("origin") if p.get("origin") not in ("shipped", None) else ""))
            lst.addItem(it); st["rows"].append(p)

    def cur():
        i = lst.currentRow(); return st["rows"][i] if 0 <= i < len(st["rows"]) else None

    def show():
        p = cur()
        if not p: return
        info.setText("<b>%s</b> · %s · %s<br>%s<br><i>%s</i>" % (p["name"], p.get("category"), p.get("language"), p.get("description", ""),
                     "runs inside the Lua sandbox" if p.get("runs") == "lua" else "runs as its own process, under the external share limit"))
        try: src.setPlainText(open(os.path.join(p["dir"], p["entry"]), encoding="utf-8").read())
        except Exception as exc: src.setPlainText(str(exc))

    from PyQt6.QtCore import QObject, pyqtSignal

    class Br(QObject):
        line = pyqtSignal(str)
    br = Br(d); br.line.connect(log.appendPlainText)

    def run_it():
        p = cur()
        if not p: return
        log.clear(); run(app, p, br.line.emit, done=lambda files: [log.appendPlainText("→ " + str(__import__("app_hub").send_back(app, f))) for f in files])

    def rate_it():
        p = cur()
        if not p: return
        try:
            import net_hub as nh; nh.rate("plugin:" + p["id"], "me", rate.value()); fill()
        except Exception as exc:
            log.appendPlainText(str(exc))

    def bind():
        p = cur()
        if p: bind_carrier(app, inst.currentData(), p["id"]); log.appendPlainText("bound %s → carrier of %s" % (p["name"], inst.currentText()))

    def on_ev():
        p = cur()
        if not p: return
        k = {"seed change": "seed", "canonical commit": "canonical", "export finished": "export", "project load": "load"}[ev.currentText()]
        lst_ = _bindings(app)["events"].setdefault(k, [])
        if p["id"] not in lst_: lst_.append(p["id"])
        log.appendPlainText("%s runs on %s" % (p["name"], ev.currentText()))

    def unbind():
        p = cur()
        if not p: return
        b = _bindings(app)
        for k in list(b["carrier"]):
            if b["carrier"][k] == p["id"]: b["carrier"].pop(k)
        for k in b["events"]: b["events"][k] = [x for x in b["events"][k] if x != p["id"]]
        b["controls"].pop(p["id"], None); log.appendPlainText("unbound")

    def scan():
        lanl.clear(); st["lan"] = lan_plugins(app)
        for peer, f, lv in st["lan"]: lanl.addItem("%s · from %s (%s) · %d KB" % (f["name"], peer.name, lv, int(f.get("size", 0)) // 1024))
        if not st["lan"]: lanl.addItem("(no shared plugins found nearby)")

    def inst_lan():
        i = lanl.currentRow()
        if not (0 <= i < len(st["lan"])): return
        peer, f, lv = st["lan"][i]
        try:
            svc = app._nearby_share_service; path = svc.download({"url": peer.url}, f, destination="modules")
            meta = install_zip(app, path, origin=peer.name, level=lv); log.appendPlainText("installed %s from %s — review its source before running" % (meta["name"], peer.name)); fill()
        except Exception as exc:
            log.appendPlainText("✖ %s" % exc)

    def inst_file():
        pth, _ = QFileDialog.getOpenFileName(d, "Plugin", os.path.expanduser("~"), "Groovebox plugin (*.gbplugin)")
        if pth:
            try: meta = install_zip(app, pth, origin="file"); log.appendPlainText("installed " + meta["name"]); fill()
            except Exception as exc: log.appendPlainText("✖ %s" % exc)
    q.textChanged.connect(lambda *_: fill()); cat.currentIndexChanged.connect(lambda *_: fill()); lang.currentIndexChanged.connect(lambda *_: fill())
    lst.currentRowChanged.connect(lambda *_: show()); b_run.clicked.connect(run_it); b_rate.clicked.connect(rate_it)
    b_edit.clicked.connect(lambda: cur() and __import__("program_builder").open_window(app, os.path.join(cur()["dir"], cur()["entry"])))
    b_share.clicked.connect(lambda: cur() and log.appendPlainText("shared: " + pack(app, cur())))
    b_bind.clicked.connect(bind); b_ev.clicked.connect(on_ev); b_unbind.clicked.connect(unbind)
    b_scan.clicked.connect(scan); b_inst.clicked.connect(inst_lan); b_file.clicked.connect(inst_file)
    fill(); d.show(); app._plugin_window = d
    return d
