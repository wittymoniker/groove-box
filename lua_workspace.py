"""lua_workspace.py — Lua (LuaJIT via lupa) scripting workspace, sandboxed, on the sCode 'scripts' direction.

Why Lua: tiny, fast (LuaJIT), easy to sandbox, ideal for user tools that loop a lot. Python stays the seed language
(the canonicals and the seed parser are built on it); Lua scripts READ the project through a small API and WRITE only
through explicit calls that push an undo step first.

Sandbox: no io / os / package / require / load / dofile / debug; an instruction budget stops runaway loops; memory is
capped (lupa max_memory where supported).
API (global table gb):
  gb.seed()  gb.seed_values(t)  gb.bpm()  gb.base_hz()  gb.instruments()  gb.selected()
  gb.steps(name) / gb.set_steps(name, {true,false,…})   gb.pitches(name) / gb.set_pitches(name, {…})
  gb.param(name, key) / gb.set_param(name, key, value)  gb.notify(text)  gb.print(...)
  gb.render_wav(path, samples{...}, rate)   writes a mono WAV in the exports folder and sends it back (carrier)
  gb.hybrid(kernel, ...)   run a hybrid-runtime kernel (osc_fill, wavefold, ca_evolve)
Compile: "Compile" turns the script into LuaJIT bytecode (.luac, string.dump) that the workspace can run directly; the
Program Builder can make a standalone executable from any Lua file when luajit / luastatic are installed.
"""
from __future__ import annotations
import os, time

TEMPLATES = {
    "Euclidean fill": """-- fill the selected instrument with a Euclidean rhythm read from the seed
local name = gb.selected()
local st = gb.steps(name); local n = #st
local k = 3 + math.floor((gb.seed_values(0)[1] or 5) % 5)
local out = {}
for i = 1, n do out[i] = ((i * k) % n) < k end
gb.set_steps(name, out)
gb.notify("euclid " .. k .. "/" .. n .. " on " .. name)
""",
    "Seed melody": """-- pitches from the seed program over time, quantised to a major scale
local name = gb.selected(); local p = gb.pitches(name); local scale = {0,2,4,5,7,9,11}
for i = 1, #p do
  local v = gb.seed_values((i-1) / #p)[1] or 0
  local d = math.floor(math.abs(v * 7)) % 14
  p[i] = 2 ^ ((scale[d % 7 + 1] + 12 * math.floor(d / 7)) / 12)
end
gb.set_pitches(name, p)
""",
    "Render a tone": """-- render 2 s of FM to a WAV and load it as the carrier
local sr, n = 48000, 96000; local s = {}
local f = gb.base_hz()
for i = 0, n-1 do local t = i/sr; s[i+1] = math.sin(2*math.pi*f*t + 3*math.sin(2*math.pi*f*1.5*t)) * math.exp(-t*1.5) * 0.8 end
gb.render_wav("lua-fm.wav", s, sr)
""",
}


def _runtime(app, out_lines, budget=50_000_000):
    try:
        import lupa.luajit21 as lj
    except Exception:
        import lupa as lj
    try:
        L = lj.LuaRuntime(unpack_returned_tuples=True, register_eval=False, max_memory=256 << 20)
    except TypeError:
        L = lj.LuaRuntime(unpack_returned_tuples=True, register_eval=False)
    g = L.globals()
    import numpy as np

    def lst(t):
        return [t[i] for i in range(1, len(t) + 1)] if t is not None else []

    def mem(name):
        return app._current_sequence_mem(str(name))

    def undo(label):
        try: app._push_undo("Lua · " + label)
        except Exception: pass

    def changed():
        app._shared_mixdown_cache = {}
        for fn in ("reload_active_instrument_sequencer_ui", "_on_live_source_changed"):
            try: getattr(app, fn)()
            except Exception: pass

    import plugin_guard as _pg      # every write goes through the protected boundary (validation · rate · transaction)

    def _do(op):
        n, bad = _pg.apply_requests(app, [op], who="Lua")
        if bad: out_lines.append("refused: " + "; ".join(bad))
        return n

    def set_steps(name, t):
        return _do({"op": "set_steps", "instrument": str(name), "values": lst(t)})

    def set_pitches(name, t):
        return _do({"op": "set_pitches", "instrument": str(name), "values": lst(t)})

    def set_param(name, key, value):
        return _do({"op": "set_param", "instrument": str(name), "key": str(key), "value": value})

    def render_wav(fname, t, rate):
        import wave
        y = np.clip(np.array(lst(t), dtype=np.float64), -1, 1)
        d = os.path.join(str(app._exports_dir()), "lua"); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, os.path.basename(str(fname)) or "lua.wav")
        with wave.open(p, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(rate)); w.writeframes((y * 32767).astype("<i2").tobytes())
        try:
            import app_hub; out_lines.append(app_hub.send_back(app, p))
        except Exception:
            pass
        return p

    def hybrid(kernel, *a):
        import hybrid_runtime as hr
        r = hr.run(str(kernel), *a)
        return L.table_from(np.asarray(r).ravel().tolist())

    api = {
        "seed": lambda: app._seed_text(), "seed_values": lambda t=0.0: L.table_from(app.get_seed_values(float(t)) or [0.0]),
        "bpm": lambda: float(app.spin_bpm.value()), "base_hz": lambda: float(app.spin_base_frequency.value()),
        "instruments": lambda: L.table_from(list(app.instrument_names_48)), "selected": lambda: app._current_instrument_name(),
        "steps": lambda n: L.table_from([bool(x) for x in mem(n).get("steps", [])]), "set_steps": set_steps,
        "pitches": lambda n: L.table_from([float(x) for x in mem(n).get("pitches", [])]), "set_pitches": set_pitches,
        "param": lambda n, k: (app.instrument_param_state.get(str(n), {}) or {}).get(str(k)), "set_param": set_param,
        "notify": lambda txt: __import__("notify_center").notify(app, "Lua: " + str(txt), "info"),
        "print": lambda *a: out_lines.append(" ".join(str(x) for x in a)), "render_wav": render_wav, "hybrid": hybrid,
    }
    g.gb = L.table_from(api)
    L.execute("""
        local _load = load
        gb.run_bytecode = function(b) local f = assert(_load(b, "chunk", "b")); return f() end   -- your own compiled chunks
        local budget = %d
        if jit then jit.off() end   -- compiled traces skip debug hooks; the interpreter keeps the budget enforceable
        local sethook = debug and debug.sethook
        if sethook then sethook(function() error("instruction budget exceeded") end, "", budget) end
        io, os, package, require, load, loadstring, dofile, loadfile, debug = nil, nil, nil, nil, nil, nil, nil, nil, nil
        print = gb.print
    """ % int(budget))
    return L


def run(app, code, bytecode=None):
    """Run Lua source (or compiled bytecode) in the sandbox. Returns (ok, output text)."""
    lines = []
    t0 = time.perf_counter()
    try:
        L = _runtime(app, lines)
        if bytecode is not None:
            L.globals().gb.run_bytecode(bytecode)
        else:
            L.execute(code)
        return True, "\n".join(lines + ["✓ %.1f ms" % ((time.perf_counter() - t0) * 1000)])
    except Exception as exc:
        return False, "\n".join(lines + ["✖ %s" % exc])


def compile_lua(code, path):
    try:
        import lupa.luajit21 as lj
    except Exception:
        import lupa as lj
    L = lj.LuaRuntime()
    dump = L.eval("function(src) local f, e = load(src, 'script', 't'); if not f then error(e) end; return string.dump(f, true) end")
    b = dump(code)
    with open(path, "wb") as f:
        f.write(b if isinstance(b, bytes) else str(b).encode("latin-1"))
    return path


def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QComboBox, QLabel, QFileDialog)
    d = QDialog(app); d.setWindowTitle("🌙 Lua workspace (LuaJIT, sandboxed)"); d.resize(900, 640); d.setWindowModality(Qt.WindowModality.NonModal)
    lay = QVBoxLayout(d); row = QHBoxLayout(); lay.addLayout(row)
    tpl = QComboBox(); tpl.addItems(list(TEMPLATES)); b_tpl = QPushButton("Insert template")
    b_run = QPushButton("▶ Run"); b_comp = QPushButton("⚙ Compile (.luac)"); b_open = QPushButton("Open…"); b_save = QPushButton("Save…")
    b_build = QPushButton("🛠 Program Builder…")
    for w in (tpl, b_tpl, b_run, b_comp, b_open, b_save, b_build): row.addWidget(w)
    ed = QPlainTextEdit(); ed.setFont(QFont("Monospace", 10)); ed.setPlainText(TEMPLATES["Euclidean fill"]); lay.addWidget(ed, 3)
    out = QPlainTextEdit(); out.setReadOnly(True); lay.addWidget(out, 1)
    lay.addWidget(QLabel("Instruction budget stops runaway loops; heavy maths goes to gb.hybrid (sCode pool); writes go through gb.set_* (each pushes an undo step)."))
    state = {"path": None}

    def go():
        code = ed.toPlainText(); out.setPlainText("running…")
        ok, txt = run(app, code)        # project writes touch Qt state, so scripts run on the Qt thread with a budget
        out.setPlainText(txt)

    def comp():
        p, _ = QFileDialog.getSaveFileName(d, "Compiled Lua", os.path.join(str(app._exports_dir()), "script.luac"), "Lua bytecode (*.luac)")
        if p:
            try: out.setPlainText("compiled → " + compile_lua(ed.toPlainText(), p))
            except Exception as exc: out.setPlainText("✖ %s" % exc)

    def opn():
        p, _ = QFileDialog.getOpenFileName(d, "Lua script", os.path.expanduser("~"), "Lua (*.lua *.luac)")
        if not p: return
        if p.endswith(".luac"):
            ok, txt = run(app, None, bytecode=open(p, "rb").read()); out.setPlainText(txt)
        else:
            ed.setPlainText(open(p, encoding="utf-8").read()); state["path"] = p

    def sav():
        p, _ = QFileDialog.getSaveFileName(d, "Save Lua", state["path"] or os.path.expanduser("~/script.lua"), "Lua (*.lua)")
        if p and __import__("safe_io").is_system_path(p):              # R101: view-only system files
            out.setPlainText(__import__("safe_io").protected_message(p, "save over")); return
        if p: open(p, "w", encoding="utf-8").write(ed.toPlainText()); state["path"] = p
    b_tpl.clicked.connect(lambda: ed.setPlainText(TEMPLATES[tpl.currentText()])); b_run.clicked.connect(go)
    b_comp.clicked.connect(comp); b_open.clicked.connect(opn); b_save.clicked.connect(sav)
    b_build.clicked.connect(lambda: __import__("program_builder").open_window(app))
    d.show(); app._lua_ws = d
    return d
