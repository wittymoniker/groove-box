"""features_r99.py — the R99 feature set, one window (Task pad ▸ ✨ Features), one tab each.

Composition: piano roll · arrangement timeline · clip launcher · MIDI clock in/out · MIDI learn · scale lock ·
groove templates · sample slicer · audio → sequence · sidechain / FX matrix view.
Video / 3D / games: cut list from playlist rows · title layer · colour grade / LUT · camera path keys · standalone
game export · game input mapping.
Workflow: panel presets · project templates · A/B snapshots + morph · what changed (last canonical commit).
System: hardware video encoder · render profiler · audio plugins (pedalboard, when installed) · folder sync ·
first-run tour · accessibility names.
Every edit pushes an undo step first.
"""
from __future__ import annotations

import copy, hashlib, json, math, os, shutil, subprocess, threading, time

import numpy as np


def _cur(app):
    name = app.instrument_selector_dropdown.currentText()
    return name, app._current_sequence_mem(name)


def _changed(app, label):
    for fn in ("reload_active_instrument_sequencer_ui", "_push_restored_playlist_to_table", "_on_live_source_changed"):
        try: getattr(app, fn)()
        except Exception: pass
    try: app.scope_status_label.setText("✨ " + label)
    except Exception: pass


def _undo(app, label):
    try: app._push_undo(label)
    except Exception: pass


def _data_dir(sub):
    d = os.path.join(os.path.expanduser("~"), ".local", "share", "groovebox", sub)
    os.makedirs(d, exist_ok=True); return d


def _settings():
    try:
        import compat_settings as cs; return cs
    except Exception:
        return None


# ------------------------------------------------------------------ scale lock / groove
SCALES = {"chromatic": list(range(12)), "major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10],
          "dorian": [0, 2, 3, 5, 7, 9, 10], "pentatonic": [0, 2, 4, 7, 9], "minor pentatonic": [0, 3, 5, 7, 10],
          "blues": [0, 3, 5, 6, 7, 10], "harmonic minor": [0, 2, 3, 5, 7, 8, 11], "whole tone": [0, 2, 4, 6, 8, 10]}

# Fixed, authored templates: groove variation is intentional and repeatable,
# never sampled from a probability source.
GROOVE_TEMPLATES = {
    "Straight": (0.0, 0.0),
    "Light 8th swing": (0.0, 0.12),
    "Deep 8th swing": (0.0, 0.22),
    "Shuffle": (0.0, 0.32),
    "Laid back": (0.0, 0.06, 0.0, 0.12),
    "Push / pull": (0.0, -0.06, 0.04, 0.08),
}


def named_groove_template(name, steps):
    """Return an exact per-step offset pattern for a named built-in groove."""
    pattern = GROOVE_TEMPLATES.get(str(name), GROOVE_TEMPLATES["Straight"])
    try:
        count = max(1, min(512, int(steps)))
    except (TypeError, ValueError, OverflowError):
        count = 16
    return [float(pattern[i % len(pattern)]) for i in range(count)]


def quantize_ratio(r, root=0, scale="major"):
    """Quantize a positive finite frequency ratio without propagating bad input."""
    try:
        ratio = float(r)
    except (TypeError, ValueError, OverflowError):
        return r
    if not math.isfinite(ratio) or ratio <= 0.0:
        return r
    try:
        root = int(root) % 12
    except (TypeError, ValueError, OverflowError):
        root = 0
    scale_key = str(scale or "chromatic").strip().lower()
    degrees = SCALES.get(scale_key)
    if not degrees:
        raise ValueError("Unknown scale: %s" % scale)
    st = 12.0 * math.log2(ratio) - root
    k = math.floor(st / 12.0)
    deg = st - 12.0 * k
    best = min(list(degrees) + [12], key=lambda d: (abs(d - deg), d))
    return 2.0 ** ((12.0 * k + best + root) / 12.0)


def scale_lock(app, root, scale, all_instruments=True):
    root = int(root) % 12
    scale = str(scale or "chromatic").strip().lower()
    if scale not in SCALES:
        raise ValueError("Unknown scale: %s" % scale)
    names = list(app.instrument_names_48) if all_instruments else [_cur(app)[0]]
    # Include each instrument's active edit buffer as well as its bank. After
    # project load these can be distinct dictionaries; editing only the bank
    # silently left the visible sequence unchanged until the next bank switch.
    _undo(app, "Scale lock")
    n = 0
    banks = getattr(app, "instrument_sequence_banks", {}) or {}
    active = getattr(app, "instrument_sequencer_memory", {}) or {}
    for name in names:
        seen = set()
        bank = banks.get(name, {}) if isinstance(banks, dict) else {}
        memories = list(bank.values()) if isinstance(bank, dict) else []
        current = active.get(name) if isinstance(active, dict) else None
        if isinstance(current, dict):
            memories.append(current)
        for mem in memories:
            if not isinstance(mem, dict) or id(mem) in seen:
                continue
            seen.add(id(mem))
            ps = mem.get("pitches")
            if not isinstance(ps, list):
                continue
            for i, value in enumerate(ps):
                try:
                    original = float(value)
                    if not math.isfinite(original) or original <= 0.0:
                        continue
                except (TypeError, ValueError, OverflowError):
                    continue
                q = quantize_ratio(original, root, scale)
                if not math.isclose(float(q), original, rel_tol=1e-12, abs_tol=1e-12):
                    ps[i] = q
                    n += 1
    app.scale_lock = {"root": root, "scale": scale}
    _changed(app, "scale lock %s %s · %d notes moved" % (["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"][root], scale, n))
    return n


def _stable_groove_seed(app, instrument_name, memory, length):
    """Stable cross-process seed; never uses Python's process-randomized hash()."""
    project_seed = None
    signature = getattr(app, "_seed_program_signature", None)
    if callable(signature):
        try:
            project_seed = signature()
        except Exception:
            project_seed = None
    if project_seed is None:
        for attr in ("project_seed", "seed", "current_seed", "canonical_seed"):
            value = getattr(app, attr, None)
            if value is not None and not callable(value):
                project_seed = value
                break
    if project_seed is None:
        project_seed = memory.get("seed", memory.get("seed_int", 0))
    try:
        selected = (getattr(app, "instrument_selected_sequence", {}) or {}).get(instrument_name, 1)
    except Exception:
        selected = 1
    payload = json.dumps({"project_seed": project_seed, "instrument": str(instrument_name),
                          "sequence": selected, "length": int(length)},
                         sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _stable_groove_unit(seed, index):
    """SplitMix64-derived [0,1) value, a pure function of seed and step index."""
    mask = (1 << 64) - 1
    x = (int(seed) + (int(index) + 1) * 0x9E3779B97F4A7C15) & mask
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & mask
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & mask
    x ^= x >> 31
    return (x >> 11) / float(1 << 53)


def apply_groove(app, swing=0.33, humanize=0.0, template=None):
    """Apply a reproducible groove; humanize is deterministic per project/sequence/step.

    Swing moves odd steps by swing × half a step. Template offsets, when supplied,
    replace the swing pattern. Humanize adds bounded deterministic variation.
    """
    name, mem = _cur(app)
    try:
        swing = float(swing)
    except (TypeError, ValueError, OverflowError):
        swing = 0.33
    try:
        humanize = float(humanize)
    except (TypeError, ValueError, OverflowError):
        humanize = 0.0
    swing = max(0.0, min(1.0, swing if math.isfinite(swing) else 0.33))
    humanize = max(0.0, min(1.0, humanize if math.isfinite(humanize) else 0.0))
    try:
        length = max(1, min(512, int(mem.get("pattern_length", len(mem.get("steps", [])) or 16))))
    except (TypeError, ValueError, OverflowError):
        length = 16
    ensure = getattr(app, "_ensure_seq_mem_length", None)
    if callable(ensure):
        ensure(mem, length)
    off = mem.setdefault("offsets", [])
    if not isinstance(off, list):
        off = mem["offsets"] = []
    if len(off) < length:
        off.extend([0.0] * (length - len(off)))
    elif len(off) > length:
        del off[length:]
    clean_template = []
    if isinstance(template, (list, tuple, np.ndarray)):
        for value in template:
            try:
                v = float(value)
                clean_template.append(max(-0.5, min(0.5, v)) if math.isfinite(v) else 0.0)
            except (TypeError, ValueError, OverflowError):
                clean_template.append(0.0)
    seed = _stable_groove_seed(app, name, mem, length)
    _undo(app, "Groove")
    for i in range(length):
        base = (clean_template[i % len(clean_template)] if clean_template
                else (0.5 * swing if i % 2 == 1 else 0.0))
        jitter = (2.0 * _stable_groove_unit(seed, i) - 1.0) * 0.15 * humanize
        off[i] = float(max(-0.5, min(0.5, base + jitter)))
    mem["user_owned"] = True
    _changed(app, "groove applied deterministically to %s" % name)


# ------------------------------------------------------------------ audio helpers
def _load(path):
    import live_master as lm
    sr, a = lm._load_audio(path)
    a = np.asarray(a, dtype=np.float32)
    return (a.mean(axis=1) if a.ndim > 1 else a), int(sr)


def onsets(y, sr, hop=512):
    n = y.size // hop
    if n < 4: return []
    e = np.array([float(np.sum(y[i * hop:(i + 1) * hop] ** 2)) for i in range(n)])
    flux = np.maximum(0.0, np.diff(np.log1p(e * 1e3), prepend=0.0))
    thr = flux.mean() + 1.5 * flux.std()
    out, last = [], -99
    for i, f in enumerate(flux):
        if f > thr and i - last > 3: out.append(i * hop); last = i
    return out


def slice_to_steps(app, path, steps=None):
    """Chop an audio file at its onsets, write each slice next to it and switch on the steps they fall on."""
    y, sr = _load(path)
    ons = onsets(y, sr) or [0]
    name, mem = _cur(app)
    n = int(steps or mem.get("pattern_length", len(mem.get("steps", [])) or 16))
    _undo(app, "Sample slicer")
    folder = os.path.splitext(path)[0] + "-slices"; os.makedirs(folder, exist_ok=True)
    import wave
    bounds = list(ons) + [y.size]
    for k in range(len(ons)):
        seg = np.clip(y[bounds[k]:bounds[k + 1]], -1, 1)
        with wave.open(os.path.join(folder, "slice-%03d.wav" % (k + 1)), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((seg * 32767).astype("<i2").tobytes())
    app._ensure_seq_mem_length(mem, n)
    for i in range(n): mem["steps"][i] = False
    for o in ons:
        s = min(n - 1, int(o / float(y.size) * n)); mem["steps"][s] = True
    mem["user_owned"] = True
    _changed(app, "%d slices → %s, %d steps on" % (len(ons), folder, sum(mem["steps"][:n])))
    return folder


def audio_to_sequence(app, path):
    import signal_converters as sc
    y, sr = _load(path)
    notes, bpm = sc.transcribe(y, sr)
    name, mem = _cur(app)
    n = int(mem.get("pattern_length", len(mem.get("steps", [])) or 16))
    _undo(app, "Audio → sequence")
    app._ensure_seq_mem_length(mem, n)
    dur = y.size / float(sr)
    for i in range(n): mem["steps"][i] = False
    base = None
    for nt in notes:
        t0 = float(nt[0] if isinstance(nt, (list, tuple)) else nt.get("t", 0))
        hz = float(nt[2] if isinstance(nt, (list, tuple)) and len(nt) > 2 else (nt.get("hz", 0) if isinstance(nt, dict) else 0))
        s = min(n - 1, int(t0 / max(dur, 1e-6) * n))
        mem["steps"][s] = True
        if hz > 0:
            base = base or hz
            mem["pitches"][s] = float(max(1 / 32, min(32, hz / base)))
    mem["user_owned"] = True
    _changed(app, "audio → %s: %d notes, ~%.0f BPM detected" % (name, len(notes), float(bpm or 0)))
    return len(notes), bpm


# ------------------------------------------------------------------ MIDI clock + learn
class MidiClock:
    """Clock out: 24 PPQN at the project tempo while playing (mido port, or a raw /dev/snd/midi device).
    Clock in: incoming 0xF8 sets the project tempo (averaged over one beat); 0xFA / 0xFC start / stop."""
    def __init__(self, app):
        self.app = app; self.out_on = False; self.in_on = False; self._stop = threading.Event(); self._ticks = []
        self.port = None

    def _send(self, b):
        try:
            if self.port is None:
                try:
                    import mido
                    names = mido.get_output_names()
                    if names: self.port = ("mido", mido.open_output(names[0]))
                except Exception:
                    pass
                if self.port is None:
                    import glob
                    devs = sorted(glob.glob("/dev/snd/midiC*D*"))
                    if devs: self.port = ("raw", open(devs[0], "wb", buffering=0))
            if self.port is None: return
            if self.port[0] == "mido":
                import mido; self.port[1].send(mido.Message.from_bytes([b]))
            else:
                self.port[1].write(bytes([b]))
        except Exception:
            self.port = None

    def start_out(self):
        if self.out_on: return
        self.out_on = True; self._stop.clear()

        def run():
            was = False; nxt = time.perf_counter()
            while not self._stop.is_set():
                playing = bool(getattr(self.app, "is_playing", False)) or bool(getattr(getattr(self.app, "_live_player_window", None), "engine", None))
                if playing and not was: self._send(0xFA)
                if was and not playing: self._send(0xFC)
                was = playing
                try: bpm = float(self.app.spin_bpm.value())
                except Exception: bpm = 120.0
                dt = 60.0 / max(20.0, bpm) / 24.0
                if playing: self._send(0xF8)
                nxt += dt; time.sleep(max(0.0, nxt - time.perf_counter()))
                if time.perf_counter() - nxt > 0.1: nxt = time.perf_counter()
        threading.Thread(target=run, name="midi-clock-out", daemon=True).start()

    def stop_out(self):
        self.out_on = False; self._stop.set()

    def start_in(self):
        if self.in_on: return
        self.in_on = True
        import midi_io
        h = midi_io.hub(self.app)
        try: h.bridge.message.connect(self._on_msg)
        except Exception: pass

    def _on_msg(self, msg):
        if not self.in_on or not msg: return
        b = msg[0]
        if b == 0xF8:
            now = time.perf_counter(); self._ticks.append(now); self._ticks = self._ticks[-25:]
            if len(self._ticks) == 25:
                bpm = 60.0 / (self._ticks[-1] - self._ticks[0])
                if 20 <= bpm <= 300 and abs(self.app.spin_bpm.value() - bpm) > 0.5:
                    self.app.spin_bpm.setValue(round(bpm, 1))
        elif b == 0xFA and not getattr(self.app, "is_playing", False):
            self.app.toggle_playback()
        elif b == 0xFC and getattr(self.app, "is_playing", False):
            self.app.stop_playback()


class MidiLearn:
    """Arm → click (focus) any slider / spin box / dial → move a hardware CC: it is bound. Bindings persist."""
    def __init__(self, app):
        self.app = app; self.armed = False; self.target = None
        cs = _settings(); st = cs.load() if cs else {}
        self.map = dict(st.get("midi_learn", {}) or {})
        import midi_io
        try: midi_io.hub(app).bridge.message.connect(self._on_msg)
        except Exception: pass

    def _widget(self, name):
        return getattr(self.app, name, None)

    def arm(self):
        from PyQt6.QtWidgets import QApplication
        self.armed = True
        QApplication.instance().focusChanged.connect(self._focus)

    def _focus(self, _old, new):
        if self.armed and new is not None and hasattr(new, "setValue"):
            for k, v in self.app.__dict__.items():
                if v is new: self.target = k; break

    def _on_msg(self, msg):
        if not msg or len(msg) < 3 or (msg[0] & 0xF0) != 0xB0: return
        key = "%d:%d" % (msg[0] & 0x0F, msg[1])
        if self.armed and self.target:
            self.map[key] = self.target; self.armed = False
            cs = _settings()
            if cs: cs.update(midi_learn=self.map)
            try: self.app.scope_status_label.setText("🎛 CC %s → %s" % (key, self.target))
            except Exception: pass
            return
        w = self._widget(self.map.get(key, ""))
        if w is not None and hasattr(w, "minimum"):
            lo, hi = w.minimum(), w.maximum()
            v = lo + (hi - lo) * msg[2] / 127.0
            w.setValue(type(w.value())(v) if not isinstance(w.value(), float) else v)


# ------------------------------------------------------------------ video
def cut_list(app, path=None):
    """Cut list (CSV + CMX-style EDL) with one cut per playlist row, at the project tempo."""
    try: bpm = float(app.spin_bpm.value())
    except Exception: bpm = 120.0
    try: rb = float(app.spin_row_beats.value())
    except Exception: rb = 4.0
    row_s = rb * 60.0 / bpm
    rows = app.master_playlist_data or []
    path = path or os.path.join(str(app._exports_dir()), time.strftime("cuts-%Y%m%d-%H%M%S"))
    def tc(t, fps=30):
        f = int(round(t * fps)); return "%02d:%02d:%02d:%02d" % (f // (3600 * fps), f // (60 * fps) % 60, f // fps % 60, f % fps)
    with open(path + ".csv", "w") as f:
        f.write("row,start_s,end_s,operator,shot\n")
        for i, r in enumerate(rows):
            r = r if isinstance(r, dict) else {}
            f.write("%d,%.3f,%.3f,%s,%s\n" % (i + 1, i * row_s, (i + 1) * row_s, r.get("operator", ""), r.get("shot", "")))
    with open(path + ".edl", "w") as f:
        f.write("TITLE: Groovebox cuts\nFCM: NON-DROP FRAME\n\n")
        for i in range(len(rows)):
            f.write("%03d  AX       V     C        %s %s %s %s\n" % (i + 1, tc(i * row_s), tc((i + 1) * row_s), tc(i * row_s), tc((i + 1) * row_s)))
    return path + ".csv"


def _ff():
    try:
        import format_converter as fc
        return fc.find_ffmpeg() or __import__("sos_tools").which("ffmpeg")
    except Exception:
        return __import__("sos_tools").which("ffmpeg")


def video_post(src, title="", sub="", grade=None, lut=None, start=0.5, dur=4.0):
    """Title layer and / or colour grade on a finished video (new file next to it)."""
    ff = _ff()
    if not ff: raise RuntimeError("FFmpeg not found")
    vf = []
    if grade:
        vf.append("eq=brightness=%.3f:contrast=%.3f:saturation=%.3f:gamma=%.3f" % (
            grade.get("brightness", 0.0), grade.get("contrast", 1.0), grade.get("saturation", 1.0), grade.get("gamma", 1.0)))
    if lut:
        vf.append("lut3d='%s'" % lut.replace("'", "\\'"))
    def esc(t): return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
    if title:
        vf.append("drawtext=text='%s':fontcolor=white:fontsize=h/12:x=(w-tw)/2:y=h*0.42:borderw=3:enable='between(t,%g,%g)'" % (esc(title), start, start + dur))
    if sub:
        vf.append("drawtext=text='%s':fontcolor=white@0.85:fontsize=h/24:x=(w-tw)/2:y=h*0.55:borderw=2:enable='between(t,%g,%g)'" % (esc(sub), start, start + dur))
    out = os.path.splitext(src)[0] + "-post.mp4"
    cmd = [ff, "-y", "-i", src, "-vf", ",".join(vf) or "null", "-c:v", "libx264", "-preset", "faster", "-crf", "17", "-c:a", "copy", out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if r.returncode != 0: raise RuntimeError(r.stderr[-400:])
    return out


def camera_key(app, t, zoom, angle_deg):
    import scene3d as s3
    sc = s3.scene(app)
    keys = [k for k in sc.setdefault("camera_keys", []) if abs(k["t"] - t) > 1e-6]
    keys.append({"t": float(t), "zoom": float(zoom), "angle": math.radians(float(angle_deg))})
    sc["camera_keys"] = sorted(keys, key=lambda k: k["t"]); app.video_obj_scene = sc
    return len(sc["camera_keys"])


# ------------------------------------------------------------------ games
def export_game(app, folder=None):
    """Standalone game folder: level JSON + the project + a launcher script that runs the Groovebox game engine."""
    import scene3d as s3
    folder = folder or os.path.join(str(app._exports_dir()), time.strftime("game-%Y%m%d-%H%M%S"))
    os.makedirs(folder, exist_ok=True)
    __import__("safe_io").atomic_write_json(os.path.join(folder, "level.json"), s3.game_scene(app), indent=1)
    __import__("safe_io").atomic_write_json(os.path.join(folder, "project.MCC"), app._project_snapshot(), default=str)
    cs = _settings(); mapping = (cs.load().get("game_input_map") if cs else None) or {}
    __import__("safe_io").atomic_write_json(os.path.join(folder, "input_map.json"), mapping, indent=1)
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(folder, "run_game.py"), "w") as f:
        f.write("import os, sys, subprocess\nHERE=os.path.dirname(os.path.abspath(__file__))\n"
                "GB=os.environ.get('GROOVEBOX_HOME', %r)\nsys.path.insert(0, GB)\n"
                "sys.exit(subprocess.call([sys.executable, os.path.join(GB, 'run_groovebox.py'), '--game', os.path.join(HERE, 'level.json'), os.path.join(HERE, 'project.MCC')]))\n" % here)
    return folder


GAME_ACTIONS = ("left", "right", "up", "down", "jump", "action", "pause")


# ------------------------------------------------------------------ presets / templates / A-B
def panel_values(box):
    from PyQt6.QtWidgets import QAbstractSlider, QAbstractSpinBox, QCheckBox, QComboBox
    out = {}
    for w in box.findChildren(QAbstractSlider) + box.findChildren(QAbstractSpinBox) + box.findChildren(QCheckBox) + box.findChildren(QComboBox):
        name = w.objectName() or ("%s#%d" % (type(w).__name__, len(out)))
        if hasattr(w, "value"): out[name] = w.value()
        elif isinstance(w, QCheckBox): out[name] = w.isChecked()
        elif isinstance(w, QComboBox): out[name] = w.currentText()
    return out


def panel_apply(box, vals):
    from PyQt6.QtWidgets import QAbstractSlider, QAbstractSpinBox, QCheckBox, QComboBox
    i = 0
    for w in box.findChildren(QAbstractSlider) + box.findChildren(QAbstractSpinBox) + box.findChildren(QCheckBox) + box.findChildren(QComboBox):
        name = w.objectName() or ("%s#%d" % (type(w).__name__, i)); i += 1
        if name not in vals: continue
        v = vals[name]
        try:
            if isinstance(w, QCheckBox): w.setChecked(bool(v))
            elif isinstance(w, QComboBox): w.setCurrentText(str(v))
            else: w.setValue(v)
        except Exception: pass


def _numeric_morph(a, b, u):
    if isinstance(a, bool) or isinstance(b, bool): return b if u >= 0.5 else a
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        v = (1 - u) * a + u * b; return int(round(v)) if isinstance(a, int) and isinstance(b, int) else v
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _numeric_morph(a.get(k), b.get(k), u) if k in a and k in b else (b.get(k) if u >= 0.5 else a.get(k, b.get(k))) for k in set(a) | set(b)}
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [_numeric_morph(x, y, u) for x, y in zip(a, b)]
    return b if u >= 0.5 else a


def ab_morph(app, A, B, u):
    _undo(app, "A/B morph %.0f %%" % (u * 100))
    doc = _numeric_morph(A, B, float(u))
    app._apply_project_snapshot(doc); _changed(app, "A/B morph %.0f %%" % (u * 100))


# ------------------------------------------------------------------ what changed
def install_change_tracker(app):
    orig = getattr(app, "_ensure_perfect_unison", None)
    if not callable(orig) or getattr(orig, "_r99", False): return

    def snap():
        # R101: flat snapshot instead of deepcopy (nested dicts are ignored by the comparison below anyway)
        def _flat(b):
            return {k2: (tuple(v2) if isinstance(v2, list) else v2) for k2, v2 in (b or {}).items()
                    if not isinstance(v2, dict)} if isinstance(b, dict) else {}
        return {"params": {n: _flat(b) for n, b in (getattr(app, "instrument_param_state", {}) or {}).items()},
                "steps": {n: {s: sum(bool(x) for x in (m or {}).get("steps", [])) for s, m in (b or {}).items() if isinstance(m, dict)}
                          for n, b in (getattr(app, "instrument_sequence_banks", {}) or {}).items()},
                "rows": sum(1 for r in (getattr(app, "master_playlist_data", []) or []) if r)}

    def run(*a, **k):
        before = snap(); t0 = time.perf_counter()
        r = orig(*a, **k)
        try:
            after = snap(); ch = []
            for n in set(before["params"]) | set(after["params"]):
                pa, pb = before["params"].get(n, {}) or {}, after["params"].get(n, {}) or {}
                d = [k2 for k2 in set(pa) | set(pb) if pa.get(k2) != pb.get(k2) and not isinstance(pb.get(k2), dict)]
                if d: ch.append("%s: %d params (%s)" % (n, len(d), ", ".join(sorted(d)[:5])))
            for n in set(before["steps"]) | set(after["steps"]):
                if before["steps"].get(n) != after["steps"].get(n):
                    ch.append("%s: steps %s → %s" % (n, before["steps"].get(n), after["steps"].get(n)))
            if before["rows"] != after["rows"]: ch.append("playlist rows %d → %d" % (before["rows"], after["rows"]))
            app._last_canonical_changes = {"time": time.time(), "seconds": time.perf_counter() - t0, "changes": ch}
        except Exception:
            pass
        return r
    run._r99 = True
    app._ensure_perfect_unison = run


# ------------------------------------------------------------------ profiler
_PROF = {}


def install_profiler(app):
    for meth in ("_render_mixdown_buffer", "_ensure_perfect_unison", "_project_snapshot", "_apply_project_snapshot",
                 "reload_active_instrument_sequencer_ui", "_refresh_status_frame", "_canonical_playlist_paint"):
        f = getattr(app, meth, None)
        if not callable(f) or getattr(f, "_prof", False): continue

        def wrap(f=f, meth=meth):
            def run(*a, **k):
                t0 = time.perf_counter()
                try: return f(*a, **k)
                finally:
                    dt = time.perf_counter() - t0; e = _PROF.setdefault(meth, [0, 0.0, 0.0])
                    e[0] += 1; e[1] += dt; e[2] = max(e[2], dt)
            run._prof = True; return run
        setattr(app, meth, wrap())


def profile_report(app):
    lines = ["%-40s %6s %9s %9s" % ("stage", "calls", "total s", "worst s")]
    for k, (n, tot, worst) in sorted(_PROF.items(), key=lambda kv: -kv[1][1]):
        lines.append("%-40s %6d %9.3f %9.3f" % (k, n, tot, worst))
    try:
        import thread_budget as tb
        lines.append(""); lines.append("worker lanes:")
        for row in tb.lane_report(16): lines.append("  " + str(row))
    except Exception:
        pass
    return "\n".join(lines)


# ------------------------------------------------------------------ plugins / sync / tour / accessibility
def plugin_process(path, plugin_path):
    try:
        import pedalboard
    except ImportError:
        raise RuntimeError("audio plugins need the 'pedalboard' package (pip install pedalboard) — VST3 / LV2 / AU")
    from pedalboard.io import AudioFile
    plug = pedalboard.load_plugin(plugin_path)
    with AudioFile(path) as f:
        audio = f.read(f.frames); sr = f.samplerate
    out = plug(audio, sr)
    dst = os.path.splitext(path)[0] + "-fx.wav"
    with AudioFile(dst, "w", sr, out.shape[0]) as f: f.write(out)
    return dst


def sync_folder(src, dst):
    """One-way mirror of projects / exports to a folder (USB, NAS mount, cloud-synced folder). Newer files win."""
    n = 0
    for dp, _dn, fn in os.walk(src):
        rel = os.path.relpath(dp, src)
        for f in fn:
            a = os.path.join(dp, f); b = os.path.join(dst, rel, f)
            if not os.path.exists(b) or os.path.getmtime(a) > os.path.getmtime(b) + 1:
                os.makedirs(os.path.dirname(b), exist_ok=True); shutil.copy2(a, b); n += 1
    return n


def tour(app):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QToolTip
    steps = [("input_seed_val", "① The Global Seed: any number, word or program — the project's identity."),
             ("btn_seeded_randomize", "② Canonical engines: turn them on and the seed writes the composition."),
             ("instrument_selector_dropdown", "③ Pick an instrument to see and edit its sequence."),
             ("sequence_selector", "④ Each instrument has numbered sequences; 🎨 sets a sequence's glow colour."),
             ("btn_play", "⑤ Play the composition."),
             ("task_pad", "⑥ The Task pad: Live Player, Export, 3D Studio, Autopilot, tools."),
             ("btn_export", "⑦ Export audio, video, projects and games.")]
    steps = [(getattr(app, a, None), t) for a, t in steps if getattr(app, a, None) is not None]

    def show(i):
        if i >= len(steps): return
        w, t = steps[i]
        try:
            QToolTip.showText(w.mapToGlobal(w.rect().center()), t + "\n(next in 4 s)", w)
        except RuntimeError:
            pass
        QTimer.singleShot(4000, lambda: show(i + 1))
    show(0)
    cs = _settings()
    if cs: cs.update(tour_done=True)


def accessibility_pass(app):
    from PyQt6.QtWidgets import QWidget
    n = 0
    for w in app.findChildren(QWidget):
        if w.accessibleName(): continue
        t = ""
        for m in ("text", "title"):
            f = getattr(w, m, None)
            if callable(f):
                try: t = f() or ""
                except Exception: t = ""
            if t: break
        t = (t or w.toolTip() or "").replace("\n", " ").strip()[:80]
        if t:
            w.setAccessibleName(t); n += 1
            if w.toolTip(): w.setAccessibleDescription(w.toolTip()[:300])
    return n


def accessibility_pass_chunked(app, chunk=300, gap_ms=15):
    """Same result as accessibility_pass, spread over event-loop turns (chunk widgets per turn)."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QWidget
    todo = list(app.findChildren(QWidget))

    def name_one(w):
        try:
            if w.accessibleName(): return
            t = ""
            for m in ("text", "title"):
                f = getattr(w, m, None)
                if callable(f):
                    try: t = f() or ""
                    except Exception: t = ""
                if t: break
            t = (t or w.toolTip() or "").replace("\n", " ").strip()[:80]
            if t:
                w.setAccessibleName(t)
                if w.toolTip(): w.setAccessibleDescription(w.toolTip()[:300])
        except RuntimeError:
            pass                                  # widget deleted meanwhile

    def step():
        for _ in range(min(chunk, len(todo))):
            name_one(todo.pop())
        if todo:
            QTimer.singleShot(gap_ms, step)
    QTimer.singleShot(gap_ms, step)


# ------------------------------------------------------------------ the window
def install(app):
    if getattr(app, "_r99_installed", False): return
    app._r99_installed = True
    install_change_tracker(app); install_profiler(app)
    try: accessibility_pass_chunked(app)        # R101: in slices so the first frames never stall
    except Exception: pass
    cs = _settings()
    try:
        if cs and not cs.load().get("tour_done"):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(6000, lambda: tour(app))
    except Exception:
        pass


def open_window(app):
    from PyQt6.QtCore import Qt, QRectF, pyqtSignal
    from PyQt6.QtGui import QPainter, QColor, QPen
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QPushButton, QLabel, QComboBox,
                                 QSpinBox, QDoubleSpinBox, QFileDialog, QPlainTextEdit, QLineEdit, QListWidget, QGridLayout,
                                 QCheckBox, QSlider, QGroupBox)
    d = QDialog(app); d.setWindowTitle("✨ Features"); d.resize(980, 640); d.setWindowModality(Qt.WindowModality.NonModal)
    tabs = QTabWidget(); QVBoxLayout(d).addWidget(tabs)
    say = QLabel(""); say.setWordWrap(True); d.layout().addWidget(say)

    def page(title):
        w = QWidget(); l = QVBoxLayout(w); tabs.addTab(w, title); return l

    def safe(fn):
        def go(*a):
            try:
                r = fn()
                if r is not None: say.setText(str(r))
            except Exception as exc:
                say.setText("⚠ %s" % exc)
        return go

    def pick(title, filt="All (*)"):
        p, _ = QFileDialog.getOpenFileName(d, title, os.path.expanduser("~"), filt); return p

    # --- piano roll
    class Roll(QWidget):
        def __init__(self):
            super().__init__(); self.setMinimumHeight(320); self.rows = 25
        def _mem(self): return _cur(app)[1]
        def paintEvent(self, _e):
            p = QPainter(self); mem = self._mem(); n = max(1, len(mem.get("steps", [])))
            W, H = self.width(), self.height(); cw, rh = W / n, H / self.rows
            for r in range(self.rows):
                p.fillRect(QRectF(0, r * rh, W, rh), QColor("#101a24" if (self.rows - 1 - r) % 12 in (1, 3, 6, 8, 10) else "#16222e"))
            p.setPen(QPen(QColor("#22384a")))
            for i in range(n + 1): p.drawLine(int(i * cw), 0, int(i * cw), H)
            for i, on in enumerate(mem.get("steps", [])):
                if not on: continue
                r = float(mem["pitches"][i]) if i < len(mem.get("pitches", [])) else 1.0
                st = int(round(12 * math.log2(max(1e-6, r)))) + 12
                st = max(0, min(self.rows - 1, st)); a = float(mem["amplitudes"][i]) if i < len(mem.get("amplitudes", [])) else 1.0
                p.fillRect(QRectF(i * cw + 1, (self.rows - 1 - st) * rh + 1, cw - 2, rh - 2), QColor.fromHsv(int(200 - 160 * a), 200, 240))
            p.end()
        def mousePressEvent(self, e):
            mem = self._mem(); n = max(1, len(mem.get("steps", []))); i = int(e.position().x() / self.width() * n)
            st = self.rows - 1 - int(e.position().y() / self.height() * self.rows) - 12
            _undo(app, "Piano roll"); name = _cur(app)[0]
            try: app._adopt_canonical_for_edit(mem, name)
            except Exception: pass
            if e.button() == Qt.MouseButton.RightButton: mem["steps"][i] = False
            else:
                mem["steps"][i] = True; mem["pitches"][i] = 2 ** (st / 12.0)
            mem["user_owned"] = True
            try: app._mark_step_touched(mem, i)
            except Exception: pass
            self.update(); _changed(app, "piano roll · step %d" % (i + 1))
    l = page("Piano roll"); l.addWidget(QLabel("Left-click: place a note (row = semitone around the step pitch 1×). Right-click: remove. Edits the selected instrument's sequence."))
    roll = Roll(); l.addWidget(roll, 1); b = QPushButton("Refresh"); b.clicked.connect(roll.update); l.addWidget(b)

    # --- arrangement timeline
    l = page("Arrangement"); l.addWidget(QLabel("Playlist rows as blocks. Select one or more, then move or duplicate them."))
    arr = QListWidget(); arr.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection); arr.setFlow(QListWidget.Flow.LeftToRight); arr.setWrapping(True)
    l.addWidget(arr, 1); row = QHBoxLayout(); l.addLayout(row)

    def fill_arr():
        arr.clear()
        for i, r in enumerate(app.master_playlist_data or []):
            r = r if isinstance(r, dict) else {}
            arr.addItem("%d\n%s" % (i + 1, (app.instrument_label(r.get("operator")) if r.get("operator") else "·")[:16]))

    def move(delta):
        idx = sorted(i.row() for i in arr.selectedIndexes())
        if not idx: return
        pl = app.master_playlist_data
        if (delta < 0 and idx[0] == 0) or (delta > 0 and idx[-1] >= len(pl) - 1):
            return
        _undo(app, "Arrangement move")
        for i in (idx if delta < 0 else reversed(idx)): pl[i], pl[i + delta] = pl[i + delta], pl[i]
        _changed(app, "rows moved"); fill_arr()
    def dup():
        idx = sorted(i.row() for i in arr.selectedIndexes())
        if not idx: return
        _undo(app, "Arrangement duplicate"); pl = app.master_playlist_data
        block = [copy.deepcopy(pl[i]) for i in idx]; pl[idx[-1] + 1:idx[-1] + 1] = block
        try: app.spin_playlist_length.setValue(len(pl))
        except Exception: pass
        _changed(app, "%d rows duplicated" % len(block)); fill_arr()
    for t, f in (("◀ Move earlier", lambda: move(-1)), ("Move later ▶", lambda: move(1)), ("⧉ Duplicate", dup), ("Refresh", fill_arr)):
        bb = QPushButton(t); bb.clicked.connect(f); row.addWidget(bb)
    fill_arr()

    # --- clip launcher
    l = page("Clip launcher"); l.addWidget(QLabel("Each button switches an instrument to that sequence, live (applied at the next render / Live Player row)."))
    gw = QWidget(); grid = QGridLayout(gw); l.addWidget(gw, 1)

    def fill_launch():
        while grid.count():
            it = grid.takeAt(0); it.widget() and it.widget().deleteLater()
        names = [n for n in app.instrument_names_48 if app.instrument_sequence_banks.get(n)][:16]
        for r, n in enumerate(names):
            grid.addWidget(QLabel(app.instrument_label(n)[:20]), r, 0)
            for c, sid in enumerate(sorted(int(k) for k in app.instrument_sequence_banks[n] if str(k).isdigit())[:8]):
                bb = QPushButton("▶ %d" % sid); bb.setCheckable(True)
                bb.setChecked(int((app.instrument_selected_sequence or {}).get(n, 1)) == sid)
                def launch(_=False, n=n, sid=sid):
                    app.instrument_selected_sequence[n] = sid
                    app.instrument_sequencer_memory[n] = app.instrument_sequence_banks[n][sid]
                    _changed(app, "%s → SEQ %d" % (n, sid)); fill_launch()
                bb.clicked.connect(launch); grid.addWidget(bb, r, 1 + c)
    b = QPushButton("Refresh"); b.clicked.connect(fill_launch); l.addWidget(b); fill_launch()

    # --- MIDI
    l = page("MIDI"); clock = app.__dict__.setdefault("_r99_clock", MidiClock(app))
    learn = app.__dict__.get("_r99_learn") or app.__dict__.setdefault("_r99_learn", MidiLearn(app))
    c1 = QCheckBox("Send MIDI clock (24 PPQN, start / stop)"); c2 = QCheckBox("Follow incoming MIDI clock (tempo, start / stop)")
    c1.setChecked(clock.out_on); c2.setChecked(clock.in_on)
    c1.toggled.connect(lambda on: clock.start_out() if on else clock.stop_out())
    c2.toggled.connect(lambda on: clock.start_in() if on else setattr(clock, "in_on", False))
    l.addWidget(c1); l.addWidget(c2)
    bl = QPushButton("🎛 MIDI learn: arm, click a control, then move a knob on your controller")
    bl.clicked.connect(lambda: (learn.arm(), say.setText("MIDI learn armed — click a slider / spin box, then move a CC")))
    l.addWidget(bl); mlist = QPlainTextEdit(); mlist.setReadOnly(True); l.addWidget(mlist)
    bshow = QPushButton("Show bindings"); bshow.clicked.connect(lambda: mlist.setPlainText("\n".join("CC %s → %s" % kv for kv in learn.map.items()) or "none"))
    bclr = QPushButton("Clear bindings"); bclr.clicked.connect(lambda: (learn.map.clear(), (_settings() and _settings().update(midi_learn={})), mlist.setPlainText("none")))
    l.addWidget(bshow); l.addWidget(bclr); l.addStretch(1)

    # --- scale / groove
    l = page("Scale & groove"); row = QHBoxLayout(); l.addLayout(row)
    root = QComboBox(); root.addItems(["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]); sc = QComboBox(); sc.addItems(list(SCALES))
    allc = QCheckBox("all instruments"); allc.setChecked(True); bsl = QPushButton("Lock pitches to scale")
    for w in (QLabel("Root"), root, QLabel("Scale"), sc, allc, bsl): row.addWidget(w)
    bsl.clicked.connect(safe(lambda: "%d notes moved" % scale_lock(app, root.currentIndex(), sc.currentText(), allc.isChecked())))
    row = QHBoxLayout(); l.addLayout(row)
    sw = QDoubleSpinBox(); sw.setRange(0, 1); sw.setSingleStep(0.05); sw.setValue(0.33); hu = QDoubleSpinBox(); hu.setRange(0, 1); hu.setSingleStep(0.05)
    bg = QPushButton("Apply swing to selected sequence"); bga = QPushButton("Groove from audio file…")
    for w in (QLabel("Swing"), sw, QLabel("Humanize"), hu, bg, bga): row.addWidget(w)
    bg.clicked.connect(safe(lambda: apply_groove(app, sw.value(), hu.value())))
    row = QHBoxLayout(); l.addLayout(row)
    groove_name = QComboBox(); groove_name.addItems(list(GROOVE_TEMPLATES))
    groove_apply = QPushButton("Apply built-in groove")
    row.addWidget(QLabel("Groove library")); row.addWidget(groove_name, 1); row.addWidget(groove_apply)
    def apply_named_groove():
        _name, _mem = _cur(app)
        _steps = len(_mem.get("steps", [])) or int(_mem.get("pattern_length", 16) or 16)
        apply_groove(app, template=named_groove_template(groove_name.currentText(), _steps))
        return "groove preset applied · %s" % groove_name.currentText()
    groove_apply.clicked.connect(safe(apply_named_groove))

    def groove_audio():
        p = pick("Groove source", "Audio (*.wav *.flac *.mp3 *.ogg)")
        if not p: return
        y, sr = _load(p); ons = onsets(y, sr); name, mem = _cur(app); n = len(mem.get("steps", [])) or 16
        step = y.size / float(n); tpl = [0.0] * n
        for o in ons:
            i = int(round(o / step)) % n; tpl[i] = max(-0.5, min(0.5, (o - i * step) / step))
        apply_groove(app, template=tpl); return "groove from %d onsets" % len(ons)
    bga.clicked.connect(safe(groove_audio)); l.addStretch(1)

    # --- audio tools
    l = page("Slicer · audio → sequence")
    b1 = QPushButton("✂ Slice an audio file into the selected sequence's steps…")
    b1.clicked.connect(safe(lambda: (lambda p: p and "slices: " + slice_to_steps(app, p))(pick("Audio to slice", "Audio (*.wav *.flac *.mp3 *.ogg)"))))
    b2 = QPushButton("🎼 Audio → sequence (onsets + pitch into the selected sequence)…")
    b2.clicked.connect(safe(lambda: (lambda p: p and "%d notes, %.0f BPM" % audio_to_sequence(app, p))(pick("Audio to transcribe", "Audio (*.wav *.flac *.mp3 *.ogg)"))))
    l.addWidget(b1); l.addWidget(b2); l.addStretch(1)

    # --- routing view
    l = page("Sidechain & FX matrix"); mat = QPlainTextEdit(); mat.setReadOnly(True); l.addWidget(mat)

    def fill_mat():
        lines = ["SIDECHAIN"]
        for k, v in sorted((getattr(app, "sidechain_state", {}) or {}).items(), key=lambda kv: str(kv[0]))[:200]: lines.append("  %s: %s" % (k, str(v)[:120]))
        lines.append("\nPATCH (source → target · weight)")
        for c in (getattr(app, "patch_connections", []) or [])[:300]:
            if isinstance(c, dict): lines.append("  %s → %s · %.2f%s" % (c.get("source"), c.get("target"), float(c.get("weight", c.get("gain", 1)) or 0), "" if c.get("user_defined", True) else " (canonical)"))
        lines.append("\nPER-SEQUENCE FX (playlist rows)")
        for i, r in enumerate(app.master_playlist_data or []):
            if isinstance(r, dict) and any(k for k in r if "fx" in k.lower()):
                lines.append("  row %d: %s" % (i + 1, {k: r[k] for k in r if "fx" in k.lower()}))
        mat.setPlainText("\n".join(lines))
    b = QPushButton("Refresh"); b.clicked.connect(fill_mat); l.addWidget(b); fill_mat()

    # --- video
    l = page("Video post")
    bcut = QPushButton("🎞 Cut list from playlist rows (CSV + EDL)"); bcut.clicked.connect(safe(lambda: "written " + cut_list(app))); l.addWidget(bcut)
    gb = QGroupBox("Title layer + colour grade on a finished video"); gl = QGridLayout(gb); l.addWidget(gb)
    tt = QLineEdit(); st2 = QLineEdit(); br = QDoubleSpinBox(); br.setRange(-1, 1); br.setSingleStep(0.02)
    co = QDoubleSpinBox(); co.setRange(0, 3); co.setValue(1); co.setSingleStep(0.05); sa = QDoubleSpinBox(); sa.setRange(0, 3); sa.setValue(1); sa.setSingleStep(0.05)
    ga = QDoubleSpinBox(); ga.setRange(0.1, 3); ga.setValue(1); ga.setSingleStep(0.05); lut = QLineEdit(); lut.setPlaceholderText("optional .cube LUT path")
    for r_, (lab, w) in enumerate((("Title", tt), ("Subtitle", st2), ("Brightness", br), ("Contrast", co), ("Saturation", sa), ("Gamma", ga), ("LUT", lut))):
        gl.addWidget(QLabel(lab), r_, 0); gl.addWidget(w, r_, 1)
    bv = QPushButton("Choose video and render")
    bv.clicked.connect(safe(lambda: (lambda p: p and "written " + video_post(p, tt.text(), st2.text(),
        {"brightness": br.value(), "contrast": co.value(), "saturation": sa.value(), "gamma": ga.value()}, lut.text().strip() or None))(pick("Video", "Video (*.mp4 *.mov *.mkv *.webm)"))))
    gl.addWidget(bv, 8, 0, 1, 2)
    gb2 = QGroupBox("3D Studio camera path (keyframes over the song)"); cl = QHBoxLayout(gb2); l.addWidget(gb2)
    ct = QSpinBox(); ct.setRange(0, 100); ct.setSuffix(" %"); cz = QDoubleSpinBox(); cz.setRange(0.2, 4); cz.setValue(1); cz.setSingleStep(0.05)
    ca = QDoubleSpinBox(); ca.setRange(-720, 720); ca.setSuffix("°"); bk = QPushButton("◆ Camera key"); bck = QPushButton("Clear keys")
    for w in (QLabel("at"), ct, QLabel("zoom"), cz, QLabel("angle"), ca, bk, bck): cl.addWidget(w)
    bk.clicked.connect(safe(lambda: "%d camera keys" % camera_key(app, ct.value() / 100.0, cz.value(), ca.value())))
    def _clear_cam():
        import scene3d as s3
        sc3 = s3.scene(app); sc3["camera_keys"] = []; app.video_obj_scene = sc3; return "camera keys cleared"
    bck.clicked.connect(safe(_clear_cam))
    enc = QComboBox(); enc.addItems(["software", "auto", "nvenc", "qsv"])
    cs = _settings()
    if cs: enc.setCurrentText(str(cs.load().get("video_encoder", "software")))
    enc.currentTextChanged.connect(lambda v: cs and cs.update(video_encoder=v))
    row = QHBoxLayout(); row.addWidget(QLabel("Video encoder (hardware falls back to software when the encoder is missing)")); row.addWidget(enc); l.addLayout(row)
    l.addStretch(1)

    # --- games
    l = page("Games")
    bgx = QPushButton("🎮 Export standalone game folder (level, project, input map, launcher)"); bgx.clicked.connect(safe(lambda: "written " + export_game(app)))
    l.addWidget(bgx); gm = QGroupBox("Input mapping"); gml = QGridLayout(gm); l.addWidget(gm)
    mapping = dict((cs.load().get("game_input_map") if cs else None) or {"left": "A", "right": "D", "up": "W", "down": "S", "jump": "Space", "action": "J", "pause": "Esc"})
    edits = {}
    for i, act in enumerate(GAME_ACTIONS):
        e = QLineEdit(str(mapping.get(act, ""))); edits[act] = e; gml.addWidget(QLabel(act), i, 0); gml.addWidget(e, i, 1)
    bm = QPushButton("Save mapping"); bm.clicked.connect(lambda: (cs and cs.update(game_input_map={k: e.text().strip() for k, e in edits.items()}), say.setText("input mapping saved")))
    gml.addWidget(bm, len(GAME_ACTIONS), 0, 1, 2); l.addStretch(1)

    # --- presets / templates / A-B
    l = page("Presets · templates · A/B")
    boxes = [g for g in app.findChildren(QGroupBox) if g.title()][:200]
    pb = QComboBox(); [pb.addItem(g.title()[:60]) for g in boxes]; pn = QLineEdit(); pn.setPlaceholderText("preset name")
    plist = QComboBox(); row = QHBoxLayout(); l.addLayout(row)
    bps = QPushButton("Save panel preset"); bpl = QPushButton("Load")
    for w in (QLabel("Panel"), pb, pn, bps, plist, bpl): row.addWidget(w)
    pdir = _data_dir("panel_presets")

    def pfill():
        plist.clear(); t = pb.currentText().replace("/", "_")
        [plist.addItem(f[len(t) + 2:-5]) for f in sorted(os.listdir(pdir)) if f.startswith(t + "__")]
    def psave():
        g = boxes[pb.currentIndex()]; t = pb.currentText().replace("/", "_")
        __import__("safe_io").atomic_write_json(os.path.join(pdir, "%s__%s.json" % (t, pn.text().strip() or time.strftime("%H%M%S"))), panel_values(g))
        pfill(); return "preset saved"
    def pload():
        g = boxes[pb.currentIndex()]; t = pb.currentText().replace("/", "_")
        _undo(app, "Panel preset")
        with open(os.path.join(pdir, "%s__%s.json" % (t, plist.currentText()))) as f: panel_apply(g, json.load(f))
        return "preset loaded"
    pb.currentIndexChanged.connect(lambda *_: pfill()); bps.clicked.connect(safe(psave)); bpl.clicked.connect(safe(pload)); pfill()
    tdir = _data_dir("project_templates"); row = QHBoxLayout(); l.addLayout(row)
    tn = QLineEdit(); tn.setPlaceholderText("template name"); tl = QComboBox(); bts = QPushButton("Save project as template"); btn = QPushButton("New from template")
    for w in (tn, bts, tl, btn): row.addWidget(w)
    def tfill(): tl.clear(); [tl.addItem(f[:-4]) for f in sorted(os.listdir(tdir)) if f.endswith(".MCC")]
    def tsave():
        __import__("safe_io").atomic_write_json(os.path.join(tdir, (tn.text().strip() or time.strftime("template-%Y%m%d-%H%M%S")) + ".MCC"), app._project_snapshot(), default=str)
        tfill(); return "template saved"
    def tnew():
        _undo(app, "New from template")
        with open(os.path.join(tdir, tl.currentText() + ".MCC")) as f: app._apply_project_snapshot(json.load(f))
        app._current_project_path = None; _changed(app, "new project from template " + tl.currentText())
    bts.clicked.connect(safe(tsave)); btn.clicked.connect(safe(tnew)); tfill()
    row = QHBoxLayout(); l.addLayout(row); slots = app.__dict__.setdefault("_r99_ab", {})
    ba = QPushButton("Store A"); bb2 = QPushButton("Store B"); mo = QSlider(Qt.Orientation.Horizontal); mo.setRange(0, 100); bmo = QPushButton("Apply morph")
    for w in (ba, bb2, QLabel("A ↔ B"), mo, bmo): row.addWidget(w)
    ba.clicked.connect(lambda: (slots.__setitem__("A", app._project_snapshot()), say.setText("A stored")))
    bb2.clicked.connect(lambda: (slots.__setitem__("B", app._project_snapshot()), say.setText("B stored")))
    bmo.clicked.connect(safe(lambda: ab_morph(app, slots["A"], slots["B"], mo.value() / 100.0) if "A" in slots and "B" in slots else "store A and B first"))
    l.addStretch(1)

    # --- what changed / profiler
    l = page("What changed · profiler"); wc = QPlainTextEdit(); wc.setReadOnly(True); l.addWidget(wc)
    def fill_wc():
        c = getattr(app, "_last_canonical_changes", None)
        txt = ("Last canonical commit (%s, %.2f s):\n" % (time.strftime("%H:%M:%S", time.localtime(c["time"])), c["seconds"]) + "\n".join(c["changes"] or ["no changes"])) if c else "No canonical commit since launch."
        wc.setPlainText(txt + "\n\nPROFILER\n" + profile_report(app))
    b = QPushButton("Refresh"); b.clicked.connect(fill_wc); l.addWidget(b); fill_wc()

    # --- system
    l = page("Plugins · sync · help")
    bpl2 = QPushButton("🔌 Process an audio file through a VST3 / LV2 / AU plugin…")
    bpl2.clicked.connect(safe(lambda: (lambda a, p: a and p and "written " + plugin_process(a, p))(pick("Audio", "Audio (*.wav *.flac *.aiff)"), pick("Plugin", "Plugins (*.vst3 *.lv2 *.component *.so)"))))
    l.addWidget(bpl2)
    bsy = QPushButton("🔁 Mirror projects + exports to a folder (USB / NAS / cloud-synced)…")
    def do_sync():
        dst = QFileDialog.getExistingDirectory(d, "Sync to", os.path.expanduser("~"))
        if not dst: return
        n = 0
        for src in (str(app._projects_dir()), str(app._exports_dir())):
            if os.path.isdir(src): n += sync_folder(src, os.path.join(dst, os.path.basename(src.rstrip("/")) or "groovebox"))
        cs and cs.update(sync_folder=dst); return "%d files copied to %s" % (n, dst)
    bsy.clicked.connect(safe(do_sync)); l.addWidget(bsy)
    btour = QPushButton("🧭 Guided tour"); btour.clicked.connect(lambda: tour(app)); l.addWidget(btour)
    bacc = QPushButton("♿ Name every control for screen readers"); bacc.clicked.connect(safe(lambda: "%d controls named" % accessibility_pass(app))); l.addWidget(bacc)
    l.addStretch(1)
    d.show(); app._r99_window = d
    return d
