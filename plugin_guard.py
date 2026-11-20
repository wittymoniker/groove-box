"""plugin_guard.py — the protected boundary between plugins / scripts and the workspace engine.

Layers (all of them apply to every plugin, whatever its language):
 1. ISOLATION   compiled / script plugins run as separate processes (never inside Groovebox), in their own output
                folder, with a cleaned environment (no tokens / keys), under app_limits (strictly < 0.19758 of CPU
                and RAM by default) and a wall-time limit. In-app Lua runs in a sandbox (no io / os / load / debug,
                instruction budget, memory cap).
 2. ONE DOOR    a plugin never touches engine objects. It asks: a process plugin writes <out>/groovebox_requests.json,
                in-app Lua calls gb.set_*; both go through apply_requests() below.
 3. WHITELIST   only these operations exist: set_steps, set_pitches, set_amplitudes, set_param, set_bpm, set_seed,
                notify, load_file, send_signal (carrier_bridge: any signal → any context). Anything else is refused and reported.
 4. VALIDATION  types, lengths (≤ 512 steps), ranges (pitch 1/32…32, amplitude 0…1, BPM 20…300, seed ≤ 4096 chars),
                finite numbers only, instrument must exist, set_param only on existing numeric parameters (clamped to
                ±4× their magnitude) and never on engine bookkeeping keys (anything starting with '_' or ownership /
                canonical markers).
 5. RATE        at most 256 operations per request batch, at most 8 batches per 10 s per plugin.
 6. TRANSACTION a batch is applied as ONE undo step on a deep copy of the touched state; if any operation fails, or the
                project health check finds a non-finite / broken value afterwards, everything is rolled back.
 7. OUTPUTS     returned files must be inside the plugin's folder (no symlinks out), of an allowed type, ≤ 512 MB.
Every refusal lands in 🔔 Notices with the plugin's name.
"""
from __future__ import annotations
import copy, json, math, os, time

OPS = ("set_steps", "set_pitches", "set_amplitudes", "set_param", "set_bpm", "set_seed", "notify", "load_file", "send_signal")
# send_signal (R123): {"op": "send_signal", "path": "<file in plugin folder>", "context": "global_carrier" |
#   "instrument_carrier:<name>" | "carrier_layer:<target>" | "lane:<inst>:<lane>" | "seed" | "bpm" | ...}
# Routed through carrier_bridge (any signal → any context; guaranteed in the Seed-only + all-canonicals + defaults
# profile, best effort elsewhere); every change joins this batch's transaction and is undone on failure.
OUT_EXT = (".wav", ".flac", ".mp3", ".ogg", ".obj", ".png", ".jpg", ".gif", ".mp4", ".webm", ".mkv", ".mcc", ".json", ".txt", ".csv", ".mid", ".svg", ".md")
MAX_OUT = 512 << 20
_RATE = {}
PROTECTED_KEYS = ("canonical", "owner", "user_owned", "touched", "engine_", "sequencer_schema", "panels", "geo")


class Refused(Exception):
    pass


def _say(app, who, text, kind="warn"):
    try:
        __import__("notify_center").notify(app, "%s: %s" % (who, text), kind, key="plug:%s:%s" % (who, text[:20]), every_s=5)
    except Exception:
        pass


def _num(v, lo, hi, name):
    try:
        f = float(v)
    except Exception:
        raise Refused("%s must be a number" % name)
    if not math.isfinite(f):
        raise Refused("%s must be finite" % name)
    return min(hi, max(lo, f))


def _inst(app, name):
    name = str(name)
    if name not in (getattr(app, "instrument_names_48", []) or []):
        raise Refused("unknown instrument %r" % name[:40])
    return name


def _lane(v, n_max=512):
    if not isinstance(v, (list, tuple)) or len(v) > n_max or len(v) == 0:
        raise Refused("a lane must be a list of 1…%d values" % n_max)
    return list(v)


def validate(app, op):
    if not isinstance(op, dict) or op.get("op") not in OPS:
        raise Refused("operation not allowed: %r" % (op.get("op") if isinstance(op, dict) else op))
    k = op["op"]
    if k in ("set_steps", "set_pitches", "set_amplitudes"):
        name = _inst(app, op.get("instrument") or app._current_instrument_name())
        vals = _lane(op.get("values"))
        if k == "set_steps": vals = [bool(x) for x in vals]
        elif k == "set_pitches": vals = [_num(x, 1 / 32.0, 32.0, "pitch") for x in vals]
        else: vals = [_num(x, 0.0, 1.0, "amplitude") for x in vals]
        return {"op": k, "instrument": name, "values": vals}
    if k == "set_param":
        name = _inst(app, op.get("instrument") or app._current_instrument_name()); key = str(op.get("key", ""))
        if not key or key.startswith("_") or any(p in key for p in PROTECTED_KEYS):
            raise Refused("parameter %r is protected" % key[:40])
        cur = (app.instrument_param_state.get(name, {}) or {}).get(key)
        if not isinstance(cur, (int, float)) or isinstance(cur, bool):
            raise Refused("parameter %r is not an existing numeric parameter" % key[:40])
        m = max(1.0, abs(float(cur)) * 4.0)
        return {"op": k, "instrument": name, "key": key, "value": _num(op.get("value"), -m, m, key)}
    if k == "set_bpm":
        return {"op": k, "value": _num(op.get("value"), 20.0, 300.0, "bpm")}
    if k == "set_seed":
        t = str(op.get("value", ""))
        if not t or len(t) > 4096: raise Refused("seed must be 1…4096 characters")
        return {"op": k, "value": t}
    if k == "notify":
        return {"op": k, "value": str(op.get("value", ""))[:200]}
    if k == "send_signal":
        import carrier_bridge as cb
        ctx = str(op.get("context", ""))[:120]
        try:
            c, _arg = cb._split(ctx)
        except cb.BridgeError as exc:
            raise Refused(str(exc))
        if c.name in ("export", "live_player"):
            raise Refused("send_signal cannot target %s (use load_file)" % c.name)
        if c.name == "instrument_carrier" and _arg:
            _inst(app, _arg)
        f = validate(app, {"op": "load_file", "path": op.get("path", ""), "_root": op.get("_root", "")})
        return {"op": k, "path": f["path"], "context": ctx}
    p = os.path.realpath(str(op.get("path", "")))
    root = os.path.realpath(str(op.get("_root", "")))
    if not root or not p.startswith(root + os.sep) or not os.path.isfile(p) or os.path.islink(str(op.get("path", ""))):
        raise Refused("load_file must name a file inside the plugin's folder")
    if not p.lower().endswith(OUT_EXT) or os.path.getsize(p) > MAX_OUT:
        raise Refused("file type / size not allowed")
    return {"op": k, "path": p}


def _health(app, names):
    for n in names:
        m = app._current_sequence_mem(n)
        for lane in ("pitches", "amplitudes"):
            for v in m.get(lane, []) or []:
                if not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                    raise Refused("health check: %s.%s has a broken value" % (n, lane))
        for k, v in (app.instrument_param_state.get(n, {}) or {}).items():
            if isinstance(v, float) and not math.isfinite(v):
                raise Refused("health check: %s.%s is not finite" % (n, k))


def apply_requests(app, ops, who="plugin", root=None):
    """Validate and apply a batch as one transaction. Returns (applied, refused list)."""
    now = time.time(); hist = [t for t in _RATE.get(who, []) if now - t < 10.0]
    if len(hist) >= 8:
        _say(app, who, "too many request batches (8 per 10 s)"); return 0, ["rate limit"]
    _RATE[who] = hist + [now]
    ops = list(ops or [])[:256]
    good, bad = [], []
    for op in ops:
        try:
            if isinstance(op, dict) and root: op = dict(op, _root=root)
            good.append(validate(app, op))
        except Refused as exc:
            bad.append(str(exc))
    for b in bad[:6]:
        _say(app, who, "refused · " + b)
    if not good:
        return 0, bad
    names = sorted({g["instrument"] for g in good if "instrument" in g})
    snap = {"mems": {n: copy.deepcopy(app._current_sequence_mem(n)) for n in names},
            "params": {n: copy.deepcopy(app.instrument_param_state.get(n, {})) for n in names},
            "bpm": float(app.spin_bpm.value()), "seed": app._seed_text()}
    try: app._push_undo("Plugin · %s" % who)
    except Exception: pass
    undos = []
    try:
        for g in good:
            k = g["op"]
            if k in ("set_steps", "set_pitches", "set_amplitudes"):
                m = app._current_sequence_mem(g["instrument"]); lane = {"set_steps": "steps", "set_pitches": "pitches", "set_amplitudes": "amplitudes"}[k]
                app._ensure_seq_mem_length(m, len(g["values"])); m[lane][:len(g["values"])] = g["values"]; m["user_owned"] = True
            elif k == "set_param":
                app.instrument_param_state[g["instrument"]][g["key"]] = g["value"]
            elif k == "set_bpm":
                app.spin_bpm.setValue(g["value"])
            elif k == "set_seed":
                app.input_seed_val.setPlainText(g["value"])
            elif k == "notify":
                _say(app, who, g["value"], "info")
            elif k == "load_file":
                import app_hub; _say(app, who, str(app_hub.send_back(app, g["path"])), "info")
            elif k == "send_signal":
                import carrier_bridge as cb
                try:
                    rec = cb.send(app, g["path"], g["context"], source="plugin:" + str(who))
                except cb.BridgeError as exc:
                    raise Refused(str(exc))
                if rec.get("undo"): undos.append(rec["undo"])
        _health(app, names)
    except Exception as exc:
        for u in reversed(undos):
            try: u()
            except Exception: pass
        for n, m in snap["mems"].items():                     # roll back everything this batch touched
            cur = app._current_sequence_mem(n); cur.clear(); cur.update(m)
        for n, p in snap["params"].items():
            app.instrument_param_state[n] = p
        try:
            app.spin_bpm.setValue(snap["bpm"])
            if app._seed_text() != snap["seed"]: app.input_seed_val.setPlainText(snap["seed"])
        except Exception:
            pass
        _say(app, who, "rolled back: %s" % exc, "error")
        return 0, bad + [str(exc)]
    app._shared_mixdown_cache = {}
    for fn in ("reload_active_instrument_sequencer_ui", "_on_live_source_changed"):
        try: getattr(app, fn)()
        except Exception: pass
    return len(good), bad


def clean_env(env):
    """Strip credentials and session tokens from a plugin's environment."""
    out = {}
    for k, v in (env or {}).items():
        ku = k.upper()
        if any(t in ku for t in ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY", "APIKEY", "AUTH", "CREDENTIAL", "SSH_", "GPG_", "AWS_", "PRIVATE")):
            continue
        out[k] = v
    return out


def guard_outputs(app, root, files, who="plugin"):
    ok = []
    rr = os.path.realpath(root)
    for f in files or []:
        p = os.path.realpath(f)
        if os.path.islink(f) or not p.startswith(rr + os.sep) or not os.path.isfile(p):
            _say(app, who, "output outside its folder ignored: %s" % os.path.basename(f)); continue
        if not p.lower().endswith(OUT_EXT) or os.path.getsize(p) > MAX_OUT:
            _say(app, who, "output type / size not allowed: %s" % os.path.basename(f)); continue
        if os.path.basename(p) == "groovebox_requests.json":
            continue
        ok.append(p)
    return ok
