"""game_editor.py — GROOVEBOX_R32_GAME_EDITOR_20261110

🕹 Game Editor — a Performance tab and its own window (Main ▸ bottom bar ▸ 🕹 Game Editor).

  IDENTITY   the seeded game identity (genre, camera, topology, social, mood, objective,
             difficulty, level type, sigils, texture family, title) shown next to an OVERRIDE
             for each field: "seeded" keeps the canonical choice, anything else replaces it.
             Overrides live in the project (app.r32_game_overrides) and apply every time a
             game is classified, played or exported.
  MACROS     live, like the Blueprint's: CHAOS (difficulty, gravity, bounce, shake), PACE
             (game speed, thrust), DENSITY (sigils / encounters), DRIFT (camera & world motion
             via the playability drag), REWARD (assist, lives). Moving a macro updates a
             running game immediately (playability settings are read every tick).
  LIVE       Play now · Re-roll seeded identity · Lock (freeze the current identity as overrides) ·
             Reset overrides · Export the game scripts.
"""
from __future__ import annotations

import dataclasses
import os

FIELDS = (("genre", "GENRES"), ("camera", "CAMERAS"), ("topology", "TOPOLOGIES"), ("social", "SOCIAL"),
          ("mood", "MOODS"), ("objective", "OBJECTIVES"), ("difficulty", "DIFFICULTIES"), ("level_type", "LEVEL_TYPES"))
MACROS = (("CHAOS", "#ff7a90"), ("PACE", "#f6c177"), ("DENSITY", "#9ece6a"), ("DRIFT", "#7dd3fc"), ("REWARD", "#c4a7e7"))


def _vge():
    import videogame_engine
    return videogame_engine


def install(app):
    """Wrap _classify_live_game so overrides apply everywhere a game is made."""
    if getattr(app, "_r32_game_hooked", False):
        return
    orig = app._classify_live_game

    def _classify(_orig=orig):
        identity, meta = _orig()
        ov = {k: v for k, v in (getattr(app, "r32_game_overrides", {}) or {}).items() if v not in (None, "", "seeded")}
        if ov:
            try:
                fields = {f.name for f in dataclasses.fields(identity)}
                identity = dataclasses.replace(identity, **{k: v for k, v in ov.items() if k in fields})
            except Exception:
                for k, v in ov.items():
                    try:
                        setattr(identity, k, v)
                    except Exception:
                        pass
        app._r32_last_game_identity = identity
        return identity, meta
    app._classify_live_game = _classify
    app._r32_game_hooked = True


def apply_macro(app, name, v):
    import game_playability as gp
    v = max(0.0, min(1.0, float(v)))
    s = gp.SETTINGS
    if name == "CHAOS":
        s["gravity"] = 0.6 + 1.8 * v; s["bounce"] = 0.6 + 0.8 * v; s["screen_shake"] = v
        ov = app.__dict__.setdefault("r32_game_overrides", {})
        diffs = _vge().DIFFICULTIES
        ov["difficulty"] = diffs[min(len(diffs) - 1, int(v * len(diffs)))] if v > 0.05 else ov.get("difficulty", "seeded")
    elif name == "PACE":
        s["speed"] = 0.5 + 1.8 * v; s["thrust"] = 0.6 + 1.6 * v
    elif name == "DENSITY":
        app.__dict__.setdefault("r32_game_overrides", {})["sigil_count"] = int(4 + 28 * v)
    elif name == "DRIFT":
        s["drag"] = 0.4 * (1.0 - v)
    elif name == "REWARD":
        s["assist"] = v; s["lives"] = int(1 + 8 * v)
    gp.SETTINGS.update(gp.clean(s)); gp.save()
    game = getattr(app, "_live_game", None)
    if game is not None:
        try:
            gp.apply_to_world(getattr(game, "planetary", None))
        except Exception:
            pass


FEEL_PRESETS = {
    "Arcade": {"CHAOS": 0.55, "PACE": 0.75, "DENSITY": 0.6, "DRIFT": 0.4, "REWARD": 0.5},
    "Zen": {"CHAOS": 0.05, "PACE": 0.3, "DENSITY": 0.3, "DRIFT": 0.8, "REWARD": 0.9},
    "Hardcore": {"CHAOS": 0.95, "PACE": 0.9, "DENSITY": 0.85, "DRIFT": 0.2, "REWARD": 0.1},
    "Explorer": {"CHAOS": 0.25, "PACE": 0.45, "DENSITY": 0.2, "DRIFT": 0.9, "REWARD": 0.7},
    "Party": {"CHAOS": 0.7, "PACE": 0.65, "DENSITY": 0.95, "DRIFT": 0.5, "REWARD": 0.8},
    "Balanced (default)": {"CHAOS": 0.5, "PACE": 0.5, "DENSITY": 0.5, "DRIFT": 0.5, "REWARD": 0.5},
}


def seed_feel(app):
    """Deterministic macro set from the seed program (blake2b of the seed text)."""
    import hashlib
    try:
        raw = app._seed_text()
    except Exception:
        raw = str(getattr(app, "seed", "0"))
    h = hashlib.blake2b(str(raw).encode("utf-8", "replace"), digest_size=10).digest()
    return {name: 0.1 + 0.8 * (h[i] / 255.0) for i, (name, _c) in enumerate(MACROS)}


def _presets_path():
    import os
    try:
        import groovebox_paths
        return os.path.join(groovebox_paths.base_dir(), "game-feel-presets.json")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".groovebox", "game-feel-presets.json")


def _user_presets():
    import json
    try:
        with open(_presets_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_user_presets(d):
    import json, os
    try:
        os.makedirs(os.path.dirname(_presets_path()), exist_ok=True)
        with open(_presets_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    except Exception:
        pass


def morph_identities(sources):
    """R32.9 MULTI-GAME MORPH. sources = [(identity dict, weight ≥ 0), …] → (overrides, macros, report).
    Categorical fields (genre, camera, topology, social, mood, objective, difficulty, level type) are a weighted
    vote — ties broken deterministically by the vote's hash; sigil count and every numeric field are weighted
    means; the morph's seed is the weighted mean of the source seeds, so the same mix always recreates the same
    game."""
    import hashlib
    src = [(i, float(w)) for i, w in sources if isinstance(i, dict) and float(w) > 0]
    tot = sum(w for _i, w in src) or 1.0
    over, rep = {}, []
    for field, _const in FIELDS:
        votes = {}
        for ident, w in src:
            v = ident.get(field)
            if v not in (None, ""):
                votes[str(v)] = votes.get(str(v), 0.0) + w
        if votes:
            best = max(votes.items(), key=lambda kv: (round(kv[1], 9), hashlib.blake2b(kv[0].encode(), digest_size=4).digest()))
            over[field] = best[0]; rep.append("%s=%s (%.0f%%)" % (field, best[0], 100 * best[1] / tot))
    sig = [float(i.get("sigil_count", 0) or 0) for i, _w in src]
    if any(sig):
        over["sigil_count"] = int(round(sum(float(i.get("sigil_count", 0) or 0) * w for i, w in src) / tot))
    names = [str(i.get("title", "?")).strip("◆ ").split(" [")[0] for i, _w in src]
    over["title"] = "◆ Morph of " + " × ".join(n[:18] for n in names[:3]) + " ◆"
    seed = sum(float(i.get("seed", 0) or 0) * w for i, w in src) / tot
    # macros follow the mix: chaos ← difficulty spread, density ← sigils, pace / drift / reward ← seed digits
    u = [(int(seed * 1000) >> s) % 97 / 96.0 for s in (0, 7, 13)]
    macros = {"CHAOS": min(1.0, 0.2 + 0.8 * (len({i.get("difficulty") for i, _w in src}) - 1) / max(1, len(src) - 1)) if len(src) > 1 else 0.5,
              "DENSITY": min(1.0, (over.get("sigil_count", 16) - 4) / 28.0), "PACE": u[0], "DRIFT": u[1], "REWARD": u[2]}
    return over, macros, rep, seed


def make_page(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QComboBox, QSlider, QPushButton,
                                 QHBoxLayout, QSpinBox, QLineEdit)
    install(app)
    vg = _vge()
    w = QWidget(); lay = QVBoxLayout(w)
    idg = QGroupBox("Identity · seeded ↔ override"); g = QGridLayout(idg)
    seeded_lbl = {}; combos = {}
    ov = app.__dict__.setdefault("r32_game_overrides", {})
    for r, (field, const) in enumerate(FIELDS):
        g.addWidget(QLabel(field.replace("_", " ")), r, 0)
        sl = QLabel("…"); sl.setStyleSheet("color:#9ab;"); seeded_lbl[field] = sl; g.addWidget(sl, r, 1)
        cb = QComboBox(); cb.addItems(["seeded"] + list(getattr(vg, const, ()))); cb.setCurrentText(str(ov.get(field, "seeded")))
        cb.currentTextChanged.connect(lambda v, f=field: ov.__setitem__(f, v)); combos[field] = cb; g.addWidget(cb, r, 2)
    r = len(FIELDS)
    g.addWidget(QLabel("sigils"), r, 0); sig = QSpinBox(); sig.setRange(0, 64); sig.setSpecialValueText("seeded")
    sig.setValue(int(ov.get("sigil_count", 0) or 0)); sig.valueChanged.connect(lambda v: ov.__setitem__("sigil_count", int(v) or "seeded"))
    g.addWidget(sig, r, 2)
    g.addWidget(QLabel("title"), r + 1, 0); title = QLineEdit(str(ov.get("title", "") if ov.get("title") not in (None, "seeded") else ""))
    title.setPlaceholderText("seeded title"); title.editingFinished.connect(lambda: ov.__setitem__("title", title.text().strip() or "seeded"))
    g.addWidget(title, r + 1, 1, 1, 2)
    lay.addWidget(idg)

    mg = QGroupBox("Live macros"); ml = QGridLayout(mg)
    vals = app.__dict__.setdefault("r32_game_macros", {})
    sliders = {}
    for i, (name, col) in enumerate(MACROS):
        lab = QLabel(name); lab.setStyleSheet("color:%s;font-weight:900;" % col)
        s = QSlider(Qt.Orientation.Horizontal); s.setRange(0, 1000); s.setValue(int(1000 * float(vals.get(name, 0.5))))
        vl = QLabel("%.2f" % float(vals.get(name, 0.5))); vl.setMinimumWidth(34)
        s.valueChanged.connect(lambda v, n=name, vl=vl: (vals.__setitem__(n, v / 1000.0), apply_macro(app, n, v / 1000.0), vl.setText("%.2f" % (v / 1000.0))))
        ml.addWidget(lab, i, 0); ml.addWidget(s, i, 1); ml.addWidget(vl, i, 2); sliders[name] = s
    # R32.8: feel presets, a seed-derived feel, and saved presets
    prow = QHBoxLayout(); pc = QComboBox(); pc.addItems(["Feel preset…"] + list(FEEL_PRESETS) + sorted(_user_presets()))

    def set_macros(d):
        for n, v in d.items():
            if n in sliders:
                sliders[n].setValue(int(1000 * max(0.0, min(1.0, float(v)))))

    def pick(name):
        d = FEEL_PRESETS.get(name) or _user_presets().get(name)
        if d:
            set_macros(d)
    pc.currentTextChanged.connect(pick)

    def from_seed():
        set_macros(seed_feel(app))

    def save_preset():
        from PyQt6.QtWidgets import QInputDialog
        n, ok = QInputDialog.getText(w, "Save game feel", "Preset name:")
        if ok and n.strip():
            up = _user_presets(); up[n.strip()] = {k: float(vals.get(k, 0.5)) for k, _c in MACROS}; _save_user_presets(up)
            pc.addItem(n.strip())
    for cap, fn, tip in (("🎲 Feel from seed", from_seed, "Deterministic macros from the seed program signature (same seed → same feel)."),
                         ("💾 Save feel", save_preset, "Save the five macros as a named preset.")):
        b = QPushButton(cap); b.setToolTip(tip); b.clicked.connect(fn); prow.addWidget(b)
    prow.insertWidget(0, pc, 1)
    ml.addLayout(prow, len(MACROS), 0, 1, 3)
    lay.addWidget(mg)

    try:
        import game_playability as gpl
        lay.addWidget(gpl.make_panel(w))
    except Exception:
        pass

    # R32.9 MULTI-GAME MORPH -----------------------------------------------------------------------------
    mo = QGroupBox("🧬 Multi-game morph · recreate a game from a weighted mix of games"); mlay = QGridLayout(mo)
    morph_src = app.__dict__.setdefault("r32_game_morph", [])      # [{"label", "path"|None, "weight"}]
    if not morph_src:
        morph_src.append({"label": "This project (seeded)", "path": None, "weight": 1.0})
    mrows = QWidget(); mrl = QGridLayout(mrows); mlay.addWidget(mrows, 0, 0, 1, 3)

    def ident_of(entry):
        if entry.get("path"):
            import media_transmuter as _mt
            return _mt._game_identity(entry["path"])
        try:
            saved = dict(ov); ov.clear(); ident, _m = app._classify_live_game(); ov.update(saved)
            return dataclasses.asdict(ident) if dataclasses.is_dataclass(ident) else dict(vars(ident))
        except Exception:
            return {}

    def draw_rows():
        while mrl.count():
            it = mrl.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for r_, e in enumerate(morph_src):
            mrl.addWidget(QLabel(e["label"][:40]), r_, 0)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, 100); sl.setValue(int(100 * float(e["weight"])))
            sl.valueChanged.connect(lambda v, e=e: e.__setitem__("weight", v / 100.0)); mrl.addWidget(sl, r_, 1)
            if r_:
                rm = QPushButton("✕"); rm.setMaximumWidth(28)
                rm.clicked.connect(lambda _c=False, e=e: (morph_src.remove(e), draw_rows())); mrl.addWidget(rm, r_, 2)
    draw_rows()

    def add_game():
        from PyQt6.QtWidgets import QFileDialog
        p, _ = QFileDialog.getOpenFileName(w, "Game to mix in (game_*.json or game_*.py of an exported game)", "",
                                           "Groovebox games (game_*.json game_*.py);;All files (*)")
        if p:
            morph_src.append({"label": os.path.basename(os.path.dirname(p)) or os.path.basename(p), "path": p, "weight": 0.5}); draw_rows()

    def recreate():
        sources = [(ident_of(e), e["weight"]) for e in morph_src]
        over_, macros, rep_, seed = morph_identities(sources)
        for f, cb in combos.items():
            if f in over_:
                cb.setCurrentText(str(over_[f]))
        ov.update(over_)
        if "sigil_count" in over_:
            sig.setValue(int(over_["sigil_count"]))
        title.setText(over_.get("title", ""))
        for n, v in macros.items():
            if n in sliders:
                sliders[n].setValue(int(1000 * max(0.0, min(1.0, v))))
        status.setText("morph of %d game(s) · seed %.3f · %s" % (len(sources), seed, " · ".join(rep_)))
    b_add = QPushButton("＋ Add game…"); b_add.clicked.connect(add_game)
    b_go = QPushButton("🧬 Recreate morph"); b_go.setToolTip("Weighted vote of every identity field + mixed macros → overrides of the next game.")
    b_go.clicked.connect(recreate)
    b_play = QPushButton("▶ Play the morph"); b_play.clicked.connect(lambda: (recreate(), app._on_play_videogame()))
    for c_, b_ in enumerate((b_add, b_go, b_play)):
        mlay.addWidget(b_, 1, c_)
    lay.addWidget(mo)

    status = QLabel(""); status.setWordWrap(True)

    def refresh_seeded():
        try:
            saved = dict(ov); ov.clear()
            ident, _m = app._classify_live_game()
            ov.update(saved)
            for f, lbl in seeded_lbl.items():
                lbl.setText(str(getattr(ident, f, "?")))
            status.setText("seeded: %s" % getattr(ident, "title", ""))
            return ident
        except Exception as exc:
            status.setText("classify failed: %s" % exc)

    def lock():
        ident = refresh_seeded()
        if ident is None:
            return
        for f, cb in combos.items():
            cb.setCurrentText(str(getattr(ident, f, "seeded")))
        status.setText("current identity locked as overrides")

    def reset():
        ov.clear()
        for cb in combos.values():
            cb.setCurrentText("seeded")
        sig.setValue(0); title.clear(); status.setText("overrides cleared — the seed decides")
    row = QHBoxLayout()
    for cap, fn in (("▶ Play now", lambda: app._on_play_videogame()), ("↻ Show seeded identity", refresh_seeded),
                    ("🔒 Lock identity", lock), ("Reset overrides", reset),
                    ("Export game scripts", lambda: app._on_export_videogame_scripts()),
                    ("🗑 Delete this game's save", lambda: status.setText("removed %d savestate(s)" % __import__("game_housekeeping").delete_savestate(
                        getattr(getattr(app, "_r32_last_game_identity", None), "composition_fingerprint", "") or "-"))),
                    ("🗑 Delete all game saves", lambda: status.setText("removed %d savestate(s)" % __import__("game_housekeeping").delete_savestate(None)))):
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    lay.addLayout(row); lay.addWidget(status); lay.addStretch(1)
    refresh_seeded()
    return w


def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
    win = getattr(app, "_game_editor_window", None)
    try:
        if win is not None:
            win.show(); win.raise_(); return win
    except RuntimeError:
        pass
    win = QWidget(app, Qt.WindowType.Window); win.setWindowTitle("🕹 Game Editor · identity overrides · live macros · playability")
    win.resize(760, 820); sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(make_page(app))
    QVBoxLayout(win).addWidget(sc); app._game_editor_window = win; win.show(); return win
